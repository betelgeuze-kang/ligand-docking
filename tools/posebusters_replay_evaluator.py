# The adapted volume-overlap routine derives from PoseBusters 0.3.1.
# BSD 3-Clause License
#
# Copyright (c) 2023, Martin Buttenschoen
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Opt-in, source-pinned PoseBusters replay; never called by docking/search.

``baseline`` calls the frozen evaluator unchanged. ``profile`` observes those
same functions. ``prepared_receptor`` changes only the repeated, pose-independent
atom-category selection at the start of the volume-overlap module. Every call
owns its decoded inputs, evaluator, and bounded preparation cache.

Run each arm in a fresh worker. The upstream energy-reference LRU is cleared at
entry and exit; its state must not make an AB comparison accidentally warm.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
import hashlib
from importlib import import_module, metadata
import math
from pathlib import Path
import platform
import struct
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable, Iterator


SCHEMA_ID = "betelgeuze.posebusters_same_pose_replay/1.0.0"
MODES = frozenset({"baseline", "profile", "prepared_receptor"})
_RUN_LOCK = threading.Lock()

# From the frozen 0.3.1 wheel, SHA256
# a6d1437d0eb3e0fe13ad73b5c4efdc8c0914ceadd904cde55b2a9835bf591a9d.
# Pin all scientific modules/helpers, including the private helpers used below.
UPSTREAM_SOURCE_SHA256 = {
    "__init__.py": "f9369696c3a5c76f055da09a532fb6221e2c4a59a592a985ff62e65d0b817158",
    "posebusters.py": "a054d78eddd79b70b18d960aeb518f1e797421ea0f62119efe4894e0235d72b0",
    "config/redock.yml": "3cc1d43aec480e77abea92c9a7d652cf76194719059e9c4a87ca8cb35cd5665d",
    "modules/__init__.py": "d5c3f7ca7336851a691707ac80161c94c73eeef942b274863a20fdc88a71a5d9",
    "modules/distance_geometry.py": "da51961279f1ab30506647555ab4c112a6e96d1b687971951a705f6570dc5cec",
    "modules/energy_ratio.py": "0ca424becd1ca9048cbdf2511294f2bf09cb4cf4d5d31ebc9b86088fecf5fda5",
    "modules/flatness.py": "c12dc3338cd382dd76d1cdb6d5a35a86eef97e6f03caee1419ed64174a96f8c0",
    "modules/identity.py": "32f12dc7661eed90083cae7cae64894c7365e91b08308dff32090ac09b71008e",
    "modules/intermolecular_distance.py": "9b6ab7a1361254df3b8479af46bbd7817dd04457c114b2fc1c8f891f145eae10",
    "modules/loading.py": "c3bbd411bb27988d0e537fd234bb1aefe121ac2045b863ccee2c3249a63c9d72",
    "modules/rmsd.py": "de37b33b762430df44cfc4971e059863d6123ea7ed637e61661dda533bd117d6",
    "modules/sanity.py": "ca0e7c0b0fbd29221b570bef9608e422c957f7554224321aedf18895454dda02",
    "modules/sucos.py": "85bd2ed7bb8a2ec02787e524a76559236be81090fdc456418c78d18b532bf5cb",
    "modules/volume_overlap.py": "07b4a3259f49b7d98cda27404ed30f0de230862035e8d1e29152735381afa70e",
    "tools/__init__.py": "d10a324ec1488ed8c41fd76775c06ef39714d0a75d5817cd54c2c1f555cfd036",
    "tools/inchi.py": "95fa026d41168a7c535ba065daa0c73711ffd9190e02191f4fa5ec4cee06fdc0",
    "tools/loading.py": "ed0e18ed402d021b01a8ee3e6ea42aaff87101e0ba6b0e7b1361af6f8b8d8939",
    "tools/logging.py": "2cbf3bdee666bea6fda3f95063302ab88c46d18bb43cfac05d94d8a664afc44b",
    "tools/molecules.py": "123c5d4e7371bc884e2a9a93a819de6d64be26d350ef32765fc4f5d993571322",
    "tools/protein.py": "e67b3092ec193a627a9a4ab0267bc0abcf998c02246bd03dff8cc6c720afb079",
}


class ReplayEvaluationError(RuntimeError):
    """Replay admission, identity, or immutability failed."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _verify_sources(root: Path) -> dict[str, str]:
    observed = {}
    for relative, expected in UPSTREAM_SOURCE_SHA256.items():
        try:
            actual = _sha256((root / relative).read_bytes())
        except OSError as exc:
            raise ReplayEvaluationError(f"missing frozen PoseBusters source: {relative}") from exc
        if actual != expected:
            raise ReplayEvaluationError(f"frozen PoseBusters source mismatch: {relative}: {actual}")
        observed[relative] = actual
    return observed


def _load_runtime() -> SimpleNamespace:
    # Lazy: byte/JSON unit tests must run without chemistry dependencies.
    from tools import run_engine_v2_public_redocking_300 as runner

    Chem, _, _ = runner._load_rdkit_modules()
    PoseBusters = runner._load_posebusters()
    versions = {name: metadata.version(name) for name in runner.EVALUATOR_DISTRIBUTION_VERSIONS}
    if versions != runner.EVALUATOR_DISTRIBUTION_VERSIONS:
        raise ReplayEvaluationError(f"frozen evaluator distribution mismatch: {versions}")
    core = import_module("posebusters.posebusters")
    volume = import_module("posebusters.modules.volume_overlap")
    energy = import_module("posebusters.modules.energy_ratio")
    protein = import_module("posebusters.tools.protein")
    molecules = import_module("posebusters.tools.molecules")
    root = Path(core.__file__).resolve().parent
    source_hashes = _verify_sources(root)
    if (
        PoseBusters is not core.PoseBusters
        or core.module_dict["volume_overlap"] is not volume.check_volume_overlap
        or volume.get_atom_type_mask is not protein.get_atom_type_mask
        or volume.delete_atoms is not molecules.delete_atoms
        or Path(volume.__file__).resolve() != root / "modules/volume_overlap.py"
    ):
        raise ReplayEvaluationError("frozen PoseBusters callable identity mismatch")
    return SimpleNamespace(
        runner=runner, Chem=Chem, PoseBusters=PoseBusters, volume=volume,
        energy=energy, versions=versions, source_hashes=source_hashes,
    )


@dataclass
class _Aggregate:
    calls: int = 0
    total_ns: int = 0
    min_ns: int | None = None
    max_ns: int = 0

    def add(self, elapsed: int) -> None:
        self.calls += 1
        self.total_ns += elapsed
        self.min_ns = elapsed if self.min_ns is None else min(self.min_ns, elapsed)
        self.max_ns = max(self.max_ns, elapsed)

    def document(self) -> dict[str, int | None]:
        return dict(calls=self.calls, total_ns=self.total_ns, min_ns=self.min_ns, max_ns=self.max_ns)


class _Measurements:
    def __init__(self) -> None:
        self.modules: dict[tuple[str, str], _Aggregate] = {}
        self.volume: dict[tuple[str, str], _Aggregate] = {}

    @contextmanager
    def stage(self, label: str, stage: str) -> Iterator[None]:
        start = time.perf_counter_ns()
        try:
            yield
        finally:
            self.record_volume(label, stage, time.perf_counter_ns() - start)

    def record_volume(self, label: str, stage: str, elapsed: int) -> None:
        self.volume.setdefault((label, stage), _Aggregate()).add(elapsed)

    def module_document(self) -> list[dict]:
        return [dict(name=name, function=function, **value.document())
                for (name, function), value in self.modules.items()]

    def volume_document(self) -> list[dict]:
        return [dict(module=module, stage=stage, **value.document())
                for (module, stage), value in self.volume.items()]


class _VolumeTrace:
    """Observe original helpers without replacing third-party functions.

    sys.setprofile is thread-local and used only by the diagnostic profile arm.
    Some Boost.Python builds omit c_call events: missing shape observations are
    reported as missing coverage, never as zero shape cost.
    """

    def __init__(self, volume: Any, measurements: _Measurements, label: str) -> None:
        self.volume = volume
        self.measurements = measurements
        self.label = label
        self.filter_count = 0
        self.pending: dict[tuple[str, int], tuple[str, int]] = {}
        self.shape_observed = False

    def _event(self, frame: Any, event: str, arg: Any) -> None:
        stage = None
        if event == "call":
            code = frame.f_code
            if code is self.volume.get_atom_type_mask.__code__:
                stage = "category_mask"
            elif code is self.volume._pairwise_distance.__code__:
                stage = "pairwise_distance"
            elif code is self.volume._filter_by_mask.__code__:
                self.filter_count += 1
                stage = "static_filter" if self.filter_count == 1 else "distance_filter"
            if stage is not None:
                self.pending[("py", id(frame))] = (stage, time.perf_counter_ns())
        elif event == "return":
            entry = self.pending.pop(("py", id(frame)), None)
            if entry is not None:
                self.measurements.record_volume(self.label, entry[0], time.perf_counter_ns() - entry[1])
        elif event == "c_call" and arg is self.volume.ShapeTverskyIndex:
            self.shape_observed = True
            self.pending[("c", id(frame))] = ("shape_tversky", time.perf_counter_ns())
        elif event in {"c_return", "c_exception"} and arg is self.volume.ShapeTverskyIndex:
            entry = self.pending.pop(("c", id(frame)), None)
            if entry is not None:
                self.measurements.record_volume(self.label, entry[0], time.perf_counter_ns() - entry[1])

    def __enter__(self) -> _VolumeTrace:
        if sys.getprofile() is not None:
            raise ReplayEvaluationError("volume profiling requires a worker without another active profiler")
        sys.setprofile(self._event)
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        sys.setprofile(None)


def _molecule_sha256(mol: Any, Chem: Any) -> str:
    # Include private/computed properties, atom/PDB metadata, bonds, and double
    # coordinates. No SMILES conversion or sanitization is allowed here.
    flags = int(Chem.PropertyPickleOptions.AllProps) | int(Chem.PropertyPickleOptions.CoordsAsDouble)
    return _sha256(bytes(mol.ToBinary(flags)))


class _PreparedReceptorCategories:
    """One receptor, one invocation, at most four redock category prototypes."""

    def __init__(self, receptor: Any, *, context: tuple[str, ...], Chem: Any,
                 volume: Any, measurements: _Measurements) -> None:
        self._receptor = receptor
        self._context = context
        self._Chem = Chem
        self._volume = volume
        self._measurements = measurements
        self._source_sha256 = _molecule_sha256(receptor, Chem)
        self._entries: dict[tuple[str, ...], tuple[Any, str]] = {}
        self.hits = 0
        self.misses = 0

    def select(self, receptor: Any, ignore_types: Any, *, context: tuple[str, ...], label: str) -> Any:
        with self._measurements.stage(label, "preparation_identity_check"):
            if context != self._context or receptor is not self._receptor:
                raise ReplayEvaluationError("receptor preparation context changed")
            if _molecule_sha256(receptor, self._Chem) != self._source_sha256:
                raise ReplayEvaluationError("receptor input mutated during replay")
        key = tuple(sorted(set(ignore_types)))
        entry = self._entries.get(key)
        if entry is None:
            if len(self._entries) >= 4:
                raise ReplayEvaluationError("redock receptor category cache exceeded its bound")
            # Cache only after both original upstream operations succeed.
            with self._measurements.stage(label, "category_mask"):
                keep_mask = self._volume.np.array(self._volume.get_atom_type_mask(receptor, ignore_types))
            with self._measurements.stage(label, "static_filter"):
                selected = self._volume._filter_by_mask(receptor, keep_mask)
            with self._measurements.stage(label, "preparation_store"):
                prototype = self._Chem.Mol(selected)
                entry = (prototype, _molecule_sha256(prototype, self._Chem))
                self._entries[key] = entry
                self.misses += 1
        else:
            self.hits += 1
        with self._measurements.stage(label, "preparation_clone"):
            prototype, fingerprint = entry
            if _molecule_sha256(prototype, self._Chem) != fingerprint:
                raise ReplayEvaluationError("receptor category prototype mutated")
            return self._Chem.Mol(prototype)

    def verify(self) -> None:
        if _molecule_sha256(self._receptor, self._Chem) != self._source_sha256:
            raise ReplayEvaluationError("receptor input mutated during replay")
        for prototype, fingerprint in self._entries.values():
            if _molecule_sha256(prototype, self._Chem) != fingerprint:
                raise ReplayEvaluationError("receptor category prototype mutated")

    def document(self) -> dict[str, int]:
        return dict(hits=self.hits, misses=self.misses, entries=len(self._entries), max_entries=4)


def _prepared_volume_overlap(
    mol_pred: Any, mol_cond: Any, *, cache: _PreparedReceptorCategories,
    context: tuple[str, ...], volume: Any, measurements: _Measurements,
    label: str, clash_cutoff: float = 0.05, vdw_scale: float = 0.8,
    ignore_types: Any = frozenset({"hydrogens"}), search_distance: float = 6.0,
) -> dict:
    # Only the first category-selection block of pinned volume_overlap.py is
    # replaced. Keep the remaining operation order, helper implementations,
    # distance comparison, hydrogens flag, shape parameters, and cutoff exact.
    assert isinstance(mol_pred, volume.Mol)
    assert isinstance(mol_cond, volume.Mol)
    mol_cond = cache.select(mol_cond, ignore_types, context=context, label=label)
    if mol_cond.GetNumAtoms() == 0:
        return {"results": {"volume_overlap": volume.np.nan, "no_volume_clash": True}}

    with measurements.stage(label, "pairwise_distance"):
        distances = volume._pairwise_distance(
            mol_pred.GetConformer().GetPositions(), mol_cond.GetConformer().GetPositions()
        )
    keep_mask = distances.min(axis=0) <= search_distance * vdw_scale
    with measurements.stage(label, "distance_filter"):
        mol_cond = volume._filter_by_mask(mol_cond, keep_mask)
    if mol_cond.GetNumAtoms() == 0:
        return {"results": {"volume_overlap": volume.np.nan, "no_volume_clash": True}}

    ignore_hydrogens = "hydrogens" in ignore_types
    with measurements.stage(label, "shape_tversky"):
        overlap = volume.ShapeTverskyIndex(
            mol_pred, mol_cond, alpha=1, beta=0, vdwScale=vdw_scale, ignoreHs=ignore_hydrogens
        )
    return {"results": {"volume_overlap": overlap, "no_volume_clash": overlap <= clash_cutoff}}


def _instrumented_class(runtime: Any, *, mode: str, cache: Any,
                        context: tuple[str, ...], measurements: _Measurements,
                        trace_coverage: dict[str, dict[str, int]], energy_events: list[dict]) -> type:
    class ObservedPoseBusters(runtime.PoseBusters):
        def _initialize_modules(self) -> None:
            super()._initialize_modules()
            for index, (label, function, original) in enumerate(zip(self.module_name, self.fname, self.module_func)):
                parameters = dict(self.config["modules"][index].get("parameters", {}))

                def make_wrapper(label: str, function: str, original: Callable, parameters: dict) -> Callable:
                    @wraps(original)
                    def observed(**kwargs: Any) -> Any:
                        start = time.perf_counter_ns()
                        before_energy = runtime.energy.get_average_energy.cache_info() if function == "energy_ratio" else None
                        try:
                            if function == "volume_overlap" and mode == "prepared_receptor":
                                return _prepared_volume_overlap(
                                    **kwargs, **parameters, cache=cache, context=context,
                                    volume=runtime.volume, measurements=measurements, label=label,
                                )
                            if function == "volume_overlap" and mode == "profile":
                                with _VolumeTrace(runtime.volume, measurements, label) as trace:
                                    result = original(**kwargs)
                                coverage = trace_coverage.setdefault(label, dict(calls=0, shape_event_observed_calls=0))
                                coverage["calls"] += 1
                                coverage["shape_event_observed_calls"] += int(trace.shape_observed)
                                return result
                            return original(**kwargs)
                        finally:
                            measurements.modules.setdefault((label, function), _Aggregate()).add(time.perf_counter_ns() - start)
                            if before_energy is not None:
                                after_energy = runtime.energy.get_average_energy.cache_info()
                                energy_events.append(dict(
                                    candidate_ordinal=len(energy_events) + 1,
                                    hits=after_energy.hits - before_energy.hits,
                                    misses=after_energy.misses - before_energy.misses,
                                    current_size=after_energy.currsize,
                                ))
                    return observed

                self.module_func[index] = make_wrapper(label, function, original, parameters)

    return ObservedPoseBusters


def _typed_scalar(value: Any) -> dict[str, Any]:
    import numpy as np
    import pandas as pd

    kind = f"{type(value).__module__}.{type(value).__qualname__}"
    if value is pd.NA:
        return {"type": kind, "missing": "pandas.NA"}
    if value is pd.NaT:
        return {"type": kind, "missing": "pandas.NaT"}
    if value is None:
        return {"type": kind, "missing": "None"}
    if isinstance(value, (bool, np.bool_)):
        return {"type": kind, "value": bool(value)}
    if isinstance(value, (float, np.floating)):
        if isinstance(value, np.floating) and value.dtype.itemsize > 8:
            raise ReplayEvaluationError("unsupported floating precision in full report")
        number = float(value)
        return {
            "type": kind, "binary64_be": struct.pack(">d", number).hex(),
            "hex": number.hex(), "missing": "NaN" if math.isnan(number) else None,
        }
    if isinstance(value, (int, np.integer)):
        return {"type": kind, "decimal": str(int(value))}
    if isinstance(value, (str, np.str_)):
        return {"type": kind, "value": str(value)}
    raise ReplayEvaluationError(f"unsupported full-report scalar type: {kind}")


def _canonical_report(report: Any, *, predicted: tuple[Any, ...], records: tuple[bytes, ...], PoseBusters: Any) -> dict:
    if len(report) != len(records) or len(predicted) != len(records):
        raise ReplayEvaluationError("full-report denominator mismatch")
    if list(report.index.names) != ["file", "molecule"]:
        raise ReplayEvaluationError("unexpected full-report index schema")
    rows = []
    for index, (mol, record) in enumerate(zip(predicted, records)):
        name = PoseBusters._get_name(mol, 0)
        # Validate the address-bearing index before replacing it. A reordered
        # or incorrectly bound report is never silently canonicalized.
        if report.index[index] != (str(mol), name):
            raise ReplayEvaluationError("full-report row identity/order mismatch")
        rows.append(dict(
            record_ordinal=index + 1, record_sha256=_sha256(record), molecule_name=name,
            cells=[_typed_scalar(report.iat[index, column]) for column in range(len(report.columns))],
        ))
    return dict(
        index_policy="validated_original_mol_identity_replaced_by_record_sha256_and_ordinal",
        index_names=list(report.index.names), columns=list(report.columns),
        dtypes=[dict(name=str(dtype), type=f"{type(dtype).__module__}.{type(dtype).__qualname__}")
                for dtype in report.dtypes], rows=rows,
    )


def _input_fingerprints(predicted: tuple[Any, ...], native: Any, receptor: Any, Chem: Any) -> dict:
    return dict(predicted=[_molecule_sha256(mol, Chem) for mol in predicted],
                native=_molecule_sha256(native, Chem), receptor=_molecule_sha256(receptor, Chem))


def _cache_info_document(info: Any) -> dict:
    return dict(hits=info.hits, misses=info.misses, maxsize=info.maxsize, current_size=info.currsize)


def run_evaluation(*, records: tuple[bytes, ...], native_payload: bytes,
                   receptor_payload: bytes, mode: str) -> dict:
    """Evaluate admitted exact SDF records in a fresh, source-pinned worker.

    No input is rescored, aligned, relaxed, reordered, or sent into search. The
    controller must separately admit record SHA256s against the sealed run.
    Results are JSON-safe and contain no RDKit memory-address index strings.
    """
    if mode not in MODES:
        raise ReplayEvaluationError(f"unsupported replay mode: {mode}")
    if type(records) is not tuple or not 1 <= len(records) <= 64:
        raise ReplayEvaluationError("replay requires a tuple of 1..64 SDF records")
    if any(type(record) is not bytes or not record for record in records):
        raise ReplayEvaluationError("each replay record must be nonempty bytes")
    if type(native_payload) is not bytes or not native_payload or type(receptor_payload) is not bytes or not receptor_payload:
        raise ReplayEvaluationError("native and receptor payloads must be nonempty bytes")
    if not _RUN_LOCK.acquire(blocking=False):
        raise ReplayEvaluationError("concurrent replay evaluations in one worker are not supported")
    try:
        return _run_evaluation(records, native_payload, receptor_payload, mode)
    finally:
        _RUN_LOCK.release()


def _run_evaluation(records: tuple[bytes, ...], native_payload: bytes, receptor_payload: bytes, mode: str) -> dict:
    start_total = time.perf_counter_ns()
    runtime = _load_runtime()
    if runtime.runner._split_sdf_records(b"".join(records)) != records:
        raise ReplayEvaluationError("replay records do not match the frozen SDF splitting policy")
    energy_before = _cache_info_document(runtime.energy.get_average_energy.cache_info())
    runtime.energy.get_average_energy.cache_clear()
    try:
        start = time.perf_counter_ns()
        predicted, native, receptor = runtime.runner._posebusters_molecules(
            output_payload=b"".join(records), native_payload=native_payload,
            receptor_payload=receptor_payload, expected_pose_count=len(records),
        )
        decode_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        before = _input_fingerprints(predicted, native, receptor, runtime.Chem)
        identity_check_ns = time.perf_counter_ns() - start
        measurements = _Measurements()
        input_ids = dict(record_sha256s=[_sha256(record) for record in records],
                         native_sha256=_sha256(native_payload), receptor_sha256=_sha256(receptor_payload))
        context = (input_ids["receptor_sha256"], input_ids["native_sha256"],
                   UPSTREAM_SOURCE_SHA256["config/redock.yml"], UPSTREAM_SOURCE_SHA256["modules/volume_overlap.py"])
        cache = None
        trace_coverage: dict[str, dict[str, int]] = {}
        energy_events: list[dict] = []
        start = time.perf_counter_ns()
        evaluator_class = runtime.PoseBusters
        if mode == "prepared_receptor":
            cache = _PreparedReceptorCategories(receptor, context=context, Chem=runtime.Chem,
                                                volume=runtime.volume, measurements=measurements)
        if mode != "baseline":
            evaluator_class = _instrumented_class(
                runtime, mode=mode, cache=cache, context=context, measurements=measurements,
                trace_coverage=trace_coverage, energy_events=energy_events,
            )
        report = evaluator_class(config="redock", top_n=len(records)).bust(
            predicted, native, receptor, full_report=True
        )
        posebusters_ns = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        after = _input_fingerprints(predicted, native, receptor, runtime.Chem)
        if before != after:
            changed = [key for key in before if before[key] != after[key]]
            raise ReplayEvaluationError(f"evaluation mutated input molecule state: {changed}")
        if cache is not None:
            cache.verify()
        identity_check_ns += time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        rmsds, geometric, chemical, failed = runtime.runner._posebusters_report_outcomes(
            report, expected_pose_count=len(records)
        )
        full_report = _canonical_report(report, predicted=predicted, records=records, PoseBusters=runtime.PoseBusters)
        report_ns = time.perf_counter_ns() - start
        energy_after = _cache_info_document(runtime.energy.get_average_energy.cache_info())
        result = dict(
            schema_id=SCHEMA_ID, mode=mode, record_count=len(records), input_ids=input_ids,
            upstream_source_sha256=runtime.source_hashes, evaluator_versions=runtime.versions,
            python_version=platform.python_version(), fullReport=full_report,
            legacy_outcomes=dict(rmsds=list(rmsds), rmsds_binary64_hex=[value.hex() for value in rmsds],
                                 geometric_valid=list(geometric), chemical_valid=list(chemical),
                                 failed_check_ids=[list(value) for value in failed]),
            input_immutability=dict(verified=True, before=before, after=after,
                                    pickle_policy="AllProps|CoordsAsDouble"),
            receptor_preparation=cache.document() if cache is not None else None,
            energy_cache=dict(before_clear=energy_before, after_evaluation=energy_after,
                              cleared_at_entry=True, cleared_at_exit=True, per_candidate=energy_events),
            timings=dict(decode_ns=decode_ns, posebusters_ns=posebusters_ns,
                         input_identity_check_ns=identity_check_ns, report_serialization_ns=report_ns,
                         modules=measurements.module_document(), volume_substages=measurements.volume_document(),
                         volume_trace_coverage=trace_coverage, instrumented=mode != "baseline",
                         profile_timing_is_diagnostic=mode == "profile",
                         lightweight_module_and_stage_timers=mode == "prepared_receptor"),
        )
    finally:
        runtime.energy.get_average_energy.cache_clear()
    result["timings"]["end_to_end_ns"] = time.perf_counter_ns() - start_total
    return result
