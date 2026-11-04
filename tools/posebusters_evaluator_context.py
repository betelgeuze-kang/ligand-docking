"""Explicit, one-case PoseBusters strategies for the real redocking runner.

This context preserves the runner's batch/Top5 outcome-cache policy and the
upstream energy-reference LRU lifetime. It never clears that LRU, changes the
global PoseBusters module registry, or serializes full reports unless a caller
requests a report observer. The public frozen CLI does not select this context.
"""

from __future__ import annotations

from contextlib import nullcontext
from functools import wraps
import hashlib
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable

from tools import posebusters_replay_evaluator as replay


SCHEMA_ID = "betelgeuze.posebusters_evaluator_context/1.0.0"
REPORT_SCHEMA_ID = "betelgeuze.posebusters_runner_report/1.0.0"
MODES = frozenset({"reference", "prepared_receptor", "prepared_subset"})


class PoseBustersContextError(RuntimeError):
    """A case, evaluator, input, or context lifetime contract was violated."""


def strategy_source_paths(mode: str) -> tuple[str, ...]:
    """Additional implementation bytes that must bind an opt-in receipt."""
    if not isinstance(mode, str) or mode not in MODES:
        raise PoseBustersContextError("unknown PoseBusters context mode")
    paths = (
        "tools/posebusters_evaluator_context.py",
        "tools/posebusters_replay_evaluator.py",
    )
    if mode == "prepared_subset":
        paths += ("tools/posebusters_subset.py",)
    return paths


def _pipeline_identity(mode: str) -> str:
    # Lazy so structural/lifetime tests do not require the molecular runtime.
    from tools import run_engine_v2_public_redocking_300 as runner

    return runner._evaluation_pipeline_sha256(
        Path(runner.__file__).resolve().parents[1], evaluator_mode=mode
    )


class _NoMeasurements:
    """The ordinary opt-in path needs no per-module profiling records."""

    @staticmethod
    def stage(label: str, stage: str):
        return nullcontext()

    @staticmethod
    def volume_document() -> list:
        return []


class _RebindableCategories(replay._PreparedReceptorCategories):
    """Keep prototypes while giving every batch its freshly decoded receptor."""

    def rebind(self, receptor: Any) -> None:
        self.verify()
        if replay._molecule_sha256(receptor, self._Chem) != self._source_sha256:
            raise PoseBustersContextError(
                "the same receptor bytes decoded to a different molecule"
            )
        self._receptor = receptor


def _prepared_class(runtime: Any, *, cache: Any, context: tuple[str, ...],
                    measurements: Any, distance_filter: Callable | None) -> type:
    """Replace only instance-local volume callbacks; other modules stay intact."""

    class PreparedPoseBusters(runtime.PoseBusters):
        def _initialize_modules(self) -> None:
            super()._initialize_modules()
            for index, (label, function, original) in enumerate(
                zip(self.module_name, self.fname, self.module_func)
            ):
                if function != "volume_overlap":
                    continue
                parameters = dict(
                    self.config["modules"][index].get("parameters", {})
                )

                def make_wrapper(label: str, original: Callable,
                                 parameters: dict) -> Callable:
                    @wraps(original)
                    def prepared(**kwargs: Any) -> Any:
                        additional = (
                            {"distance_filter": distance_filter}
                            if distance_filter is not None else {}
                        )
                        return replay._prepared_volume_overlap(
                            **kwargs, **parameters, cache=cache, context=context,
                            volume=runtime.volume, measurements=measurements,
                            label=label, **additional,
                        )
                    return prepared

                self.module_func[index] = make_wrapper(label, original, parameters)

    return PreparedPoseBusters


class PoseBustersEvaluatorContext:
    """One explicit evaluator strategy bound to one case and input byte pair.

    Construct one context per worker/case. Pass its ``evaluator_identity`` to
    DevelopmentObservation and the context itself as ``evaluation_context`` to
    the runner. Reusing outcome rows still bypasses PoseBusters completely.
    ``report_observer`` receives detached typed report data after normal runner
    result validation; it receives no live RDKit molecules or pandas objects.
    """

    def __init__(
        self,
        case_id: str,
        *,
        mode: str = "prepared_receptor",
        report_observer: Callable[[dict], None] | None = None,
        collect_metrics: bool = False,
    ) -> None:
        if not isinstance(case_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_.-]+", case_id
        ):
            raise PoseBustersContextError("invalid evaluator context case identity")
        strategy_source_paths(mode)
        if report_observer is not None and not callable(report_observer):
            raise PoseBustersContextError("report observer must be callable")
        if type(collect_metrics) is not bool:
            raise PoseBustersContextError("collect_metrics must be boolean")
        identity = _pipeline_identity(mode)
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise PoseBustersContextError("evaluator identity is not a SHA256")
        self._case_id = case_id
        self._mode = mode
        self._evaluator_identity = identity
        self._report_observer = report_observer
        self._collect_metrics = collect_metrics
        self._runtime = None
        self._inputs: tuple[str, str] | None = None
        self._cache = None
        self._released_cache_document = None
        self._distance_filter = None
        self._measurements = replay._Measurements() if collect_metrics else _NoMeasurements()
        self._lock = threading.Lock()
        self._owner_thread = threading.get_ident()
        self._failure: BaseException | None = None
        self._closed = False
        self._bust_calls = 0
        self._record_evaluations = 0
        self._reports_observed = 0
        self._posebusters_ns = 0
        self._input_identity_check_ns = 0
        self._report_observer_ns = 0
        self._first_energy = None
        self._last_energy = None
        self._energy_hits_added = 0
        self._energy_misses_added = 0
        self._verified_input_batches = 0
        self._last_input_immutability = None

    @property
    def case_id(self) -> str:
        return self._case_id

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def evaluator_identity(self) -> str:
        return self._evaluator_identity

    def assert_healthy(self) -> None:
        if self._failure is not None:
            raise PoseBustersContextError("evaluator context has failed") from self._failure
        if self._closed:
            raise PoseBustersContextError("evaluator context is closed")
        if threading.get_ident() != self._owner_thread:
            self._reject("evaluator context belongs to another thread")

    def mark_failed(self, error: BaseException) -> None:
        if self._failure is None:
            self._failure = error

    def _reject(self, message: str) -> None:
        error = PoseBustersContextError(message)
        self.mark_failed(error)
        raise error

    def assert_case(self, case_id: str) -> None:
        self.assert_healthy()
        if self.case_id != case_id:
            self._reject("evaluator context is bound to another case")

    def assert_observation(self, observation: Any) -> None:
        self.assert_healthy()
        if observation is None:
            return
        try:
            observation.assert_case(self.case_id)
        except BaseException as exc:
            self.mark_failed(exc)
            raise
        if observation.evaluator_identity != self.evaluator_identity:
            self._reject("observation evaluator identity does not match context")

    def assert_inputs(self, *, native_payload: bytes, receptor_payload: bytes) -> None:
        self.assert_healthy()
        if type(native_payload) is not bytes or not native_payload:
            self._reject("native evaluator input must be nonempty pinned bytes")
        if type(receptor_payload) is not bytes or not receptor_payload:
            self._reject("receptor evaluator input must be nonempty pinned bytes")
        identity = (
            hashlib.sha256(native_payload).hexdigest(),
            hashlib.sha256(receptor_payload).hexdigest(),
        )
        if self._inputs is None:
            self._inputs = identity
        elif self._inputs != identity:
            self._reject("evaluator context is bound to another input byte pair")

    def bust(self, predicted: tuple, native: Any, receptor: Any, *,
             records: tuple[bytes, ...], native_payload: bytes,
             receptor_payload: bytes, expected_pose_count: int,
             PoseBusters: Any) -> Any:
        self.assert_inputs(native_payload=native_payload, receptor_payload=receptor_payload)
        if (type(expected_pose_count) is not int or not 1 <= expected_pose_count <= 64
                or len(predicted) != expected_pose_count or len(records) != expected_pose_count
                or any(type(record) is not bytes or not record.endswith(b"$$$$\n")
                       for record in records)):
            self._reject("evaluator context input denominator is invalid")
        if not self._lock.acquire(blocking=False):
            self._reject("concurrent evaluator context use is forbidden")
        try:
            if self._runtime is None:
                self._runtime = replay._load_runtime()
            runtime = self._runtime
            if PoseBusters is not runtime.PoseBusters:
                self._reject("runner and context PoseBusters identities differ")
            checked = time.perf_counter_ns()
            before = replay._input_fingerprints(predicted, native, receptor, runtime.Chem)
            self._input_identity_check_ns += time.perf_counter_ns() - checked
            energy_before = replay._cache_info_document(
                runtime.energy.get_average_energy.cache_info()
            )
            if self._first_energy is None:
                self._first_energy = energy_before
            context = (
                self.evaluator_identity, self.case_id, *self._inputs,
                replay.UPSTREAM_SOURCE_SHA256["config/redock.yml"],
                replay.UPSTREAM_SOURCE_SHA256["modules/volume_overlap.py"],
            )
            started = time.perf_counter_ns()
            evaluator_class = PoseBusters
            if self.mode != "reference":
                if self._cache is None:
                    self._cache = _RebindableCategories(
                        receptor, context=context, Chem=runtime.Chem,
                        volume=runtime.volume, measurements=self._measurements,
                    )
                else:
                    self._cache.rebind(receptor)
                if self.mode == "prepared_subset" and self._distance_filter is None:
                    from tools.posebusters_subset import ExactSubsetFilter

                    self._distance_filter = ExactSubsetFilter(
                        Chem=runtime.Chem, reference_filter=runtime.volume._filter_by_mask
                    )
                evaluator_class = _prepared_class(
                    runtime, cache=self._cache, context=context,
                    measurements=self._measurements, distance_filter=self._distance_filter,
                )
            report = evaluator_class(config="redock", top_n=expected_pose_count).bust(
                predicted, native, receptor, full_report=True
            )
            self._posebusters_ns += time.perf_counter_ns() - started
            self._bust_calls += 1
            self._record_evaluations += expected_pose_count
            energy_after = replay._cache_info_document(
                runtime.energy.get_average_energy.cache_info()
            )
            self._last_energy = energy_after
            self._energy_hits_added += energy_after["hits"] - energy_before["hits"]
            self._energy_misses_added += energy_after["misses"] - energy_before["misses"]
            checked = time.perf_counter_ns()
            after = replay._input_fingerprints(predicted, native, receptor, runtime.Chem)
            if before != after:
                self._reject("PoseBusters mutated input molecule state")
            if self._cache is not None:
                self._cache.verify()
            self._last_input_immutability = {
                "verified": True, "before": before, "after": after,
                "pickle_policy": "AllProps|CoordsAsDouble",
            }
            self._verified_input_batches += 1
            self._input_identity_check_ns += time.perf_counter_ns() - checked
            return report
        except BaseException as exc:
            self.mark_failed(exc)
            raise
        finally:
            self._lock.release()

    def observe_report(self, report: Any, *, predicted: tuple,
                       records: tuple[bytes, ...], outcomes: tuple) -> None:
        self.assert_healthy()
        if self._report_observer is None:
            return
        if self._runtime is None or self._inputs is None:
            self._reject("report observation has no evaluated batch")
        started = time.perf_counter_ns()
        try:
            rmsds, geometric, chemical, failed = outcomes
            document = {
                "schema_id": REPORT_SCHEMA_ID,
                "case_id": self.case_id,
                "mode": self.mode,
                "evaluator_identity": self.evaluator_identity,
                "evaluation_call": self._bust_calls,
                "record_count": len(records),
                "upstream_source_sha256": dict(self._runtime.source_hashes),
                "evaluator_versions": dict(self._runtime.versions),
                "input_immutability": self._last_input_immutability,
                "input_ids": {
                    "record_sha256s": [hashlib.sha256(record).hexdigest() for record in records],
                    "native_sha256": self._inputs[0],
                    "receptor_sha256": self._inputs[1],
                },
                "fullReport": replay._canonical_report(
                    report, predicted=predicted, records=records,
                    PoseBusters=self._runtime.PoseBusters,
                ),
                "legacy_outcomes": {
                    "rmsds": list(rmsds),
                    "rmsds_binary64_hex": [value.hex() for value in rmsds],
                    "geometric_valid": list(geometric),
                    "chemical_valid": list(chemical),
                    "failed_check_ids": [list(row) for row in failed],
                },
            }
            self._report_observer(document)
            self._reports_observed += 1
        except BaseException as exc:
            self.mark_failed(exc)
            raise
        finally:
            self._report_observer_ns += time.perf_counter_ns() - started

    def summary(self) -> dict:
        return {
            "schema_id": SCHEMA_ID,
            "case_id": self.case_id,
            "mode": self.mode,
            "evaluator_identity": self.evaluator_identity,
            "input_ids": None if self._inputs is None else {
                "native_sha256": self._inputs[0], "receptor_sha256": self._inputs[1]
            },
            "closed": self._closed,
            "healthy": self._failure is None,
            "bust_calls": self._bust_calls,
            "record_evaluations": self._record_evaluations,
            "full_reports_observed": self._reports_observed,
            "input_immutability_verified_batches": self._verified_input_batches,
            "receptor_preparation": (
                self._cache.document() if self._cache is not None
                else self._released_cache_document
            ),
            "subset_filter": (
                None if self._distance_filter is None else self._distance_filter.document()
            ),
            "energy_cache": {
                "first_observed": self._first_energy,
                "last_observed": self._last_energy,
                "hits_added": self._energy_hits_added,
                "misses_added": self._energy_misses_added,
                "cleared_by_context": False,
            },
            "timings": {
                "posebusters_ns": self._posebusters_ns,
                "input_identity_check_ns": self._input_identity_check_ns,
                "report_observer_ns": self._report_observer_ns,
                "volume_substages": self._measurements.volume_document(),
                "collect_metrics": self._collect_metrics,
            },
        }

    def close(self) -> None:
        if self._closed:
            return
        if not self._lock.acquire(blocking=False):
            self._reject("cannot close an active evaluator context")
        try:
            if self._cache is not None:
                try:
                    if self._failure is None:
                        self._cache.verify()
                except BaseException as exc:
                    self.mark_failed(exc)
                    raise
                finally:
                    self._released_cache_document = self._cache.document()
                    self._cache = None
        finally:
            self._closed = True
            self._lock.release()

    def __enter__(self):
        self.assert_healthy()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc is not None:
            self.mark_failed(exc)
        self.close()
