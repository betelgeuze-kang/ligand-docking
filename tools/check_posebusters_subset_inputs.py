"""Frozen native admission on retained Top5 inputs, not a benchmark.

Old immutable inputs and current candidate source have separate identities.
Every actual distance subset is evaluated twice through an instance callback.
The resulting audit timings cannot establish a performance improvement.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import math
from pathlib import Path
import sys
import time
import traceback
from typing import Any

from tools import posebusters_evaluator_context as contexts
from tools import posebusters_replay_evaluator as replay
from tools import posebusters_subset as subset
from tools import run_posebusters_integration as integration

SCHEMA_ID = "betelgeuze.posebusters_subset_input_admission/1.0.0"
EXPECTED_BUNDLE_SHA256 = "85458df79ce784c2c74f775dab2da5893bd42f147e27c16c47f2de6ccbfdf4c2"
INPUT_ARTIFACT_RUN_ID = 41790605433
INPUT_SOURCE_COMMIT = "cdf26c0bfd5885dabba855ed17ef722d2abc8320"
CASES = ("6T88_MWQ", "6YSP_PAL")
MODES = ("reference", "prepared_subset")
require, equal = integration.require, integration.equal


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def mask_metadata(mask: Any) -> dict:
    return {"shape": list(mask.shape), "dtype": mask.dtype.str, "strides": list(mask.strides),
            "writeable": bool(mask.flags.writeable)}


def molecule_inventory(mol: Any, Chem: Any) -> dict:
    """Record feature names/counts without coercing native property values."""
    def props(obj, computed):
        return list(obj.GetPropNames(includePrivate=True, includeComputed=computed))
    return {
        "atoms": mol.GetNumAtoms(), "bonds": mol.GetNumBonds(),
        "molecule_properties": props(mol, True), "persistent_molecule_properties": props(mol, False),
        "atom_chiral_tags": dict(sorted(Counter(str(a.GetChiralTag()) for a in mol.GetAtoms()).items())),
        "query_atoms": sum(bool(a.HasQuery()) for a in mol.GetAtoms()),
        "query_bonds": sum(bool(b.HasQuery()) for b in mol.GetBonds()),
        "atom_property_names": dict(sorted(Counter(name for a in mol.GetAtoms() for name in props(a, True)).items())),
        "bond_property_names": dict(sorted(Counter(name for b in mol.GetBonds() for name in props(b, True)).items())),
        "bond_types": dict(sorted(Counter(str(b.GetBondType()) for b in mol.GetBonds()).items())),
        "bond_stereo": dict(sorted(Counter(str(b.GetStereo()) for b in mol.GetBonds()).items())),
        "bond_directions": dict(sorted(Counter(str(b.GetBondDir()) for b in mol.GetBonds()).items())),
        "bond_stereo_references": sum(bool(len(b.GetStereoAtoms())) for b in mol.GetBonds()),
        "stereo_groups": len(mol.GetStereoGroups()), "substance_groups": len(Chem.GetMolSubstanceGroups(mol)),
        "conformers": [{"id": c.GetId(), "atoms": c.GetNumAtoms(), "is_3d": c.Is3D(),
                         "properties": props(c, True)} for c in mol.GetConformers()],
    }


class AuditedSubsetFilter:
    """Compare the original and candidate for every actual callback."""
    def __init__(self, runtime: Any, rows: list[dict]):
        self.runtime, self.rows = runtime, rows
        self.delegate = subset.ExactSubsetFilter(Chem=runtime.Chem, reference_filter=runtime.volume._filter_by_mask)
        self.flags = int(runtime.Chem.PropertyPickleOptions.AllProps) | int(runtime.Chem.PropertyPickleOptions.CoordsAsDouble)

    def binary(self, mol: Any) -> bytes:
        return bytes(mol.ToBinary(self.flags))

    def __call__(self, mol: Any, mask: Any) -> Any:
        import numpy as np
        require(type(mask) is np.ndarray and mask.dtype == np.dtype(bool) and mask.ndim == 1
                and len(mask) == mol.GetNumAtoms(), "unexpected actual distance mask")
        original_bytes, mask_bytes = self.binary(mol), mask.tobytes(order="C")
        original_mask_metadata = mask_metadata(mask)
        row = {"ordinal": len(self.rows) + 1, "status": "running",
               "source": molecule_inventory(mol, self.runtime.Chem),
               "source_binary_sha256": sha(original_bytes), "source_binary_size": len(original_bytes),
               "mask_size": len(mask), "mask_sha256": sha(mask_bytes), "mask_metadata": original_mask_metadata,
               "retained_atom_indices": np.flatnonzero(mask).tolist(), "pickle_policy": "AllProps|CoordsAsDouble"}
        self.rows.append(row)
        try:
            before = self.delegate.document()
            started = time.perf_counter_ns()
            expected = self.runtime.volume._filter_by_mask(mol, mask)
            row["reference_filter_ns"] = time.perf_counter_ns() - started
            require(self.binary(mol) == original_bytes, "reference subset mutated source molecule")
            require(mask.tobytes(order="C") == mask_bytes, "reference subset mutated distance mask")
            equal(mask_metadata(mask), original_mask_metadata, "reference distance mask metadata mutation")
            started = time.perf_counter_ns()
            observed = self.delegate(mol, mask)
            row["candidate_filter_ns"] = time.perf_counter_ns() - started
            expected_bytes, observed_bytes = self.binary(expected), self.binary(observed)
            row.update(reference_binary_sha256=sha(expected_bytes), candidate_binary_sha256=sha(observed_bytes),
                       reference_binary_size=len(expected_bytes), candidate_binary_size=len(observed_bytes),
                       retained_atoms=observed.GetNumAtoms(), retained_bonds=observed.GetNumBonds())
            require(expected_bytes == observed_bytes, "candidate subset binary differs from original")
            require(self.binary(mol) == original_bytes, "candidate subset mutated source molecule")
            require(mask.tobytes(order="C") == mask_bytes, "candidate subset mutated distance mask")
            equal(mask_metadata(mask), original_mask_metadata, "candidate distance mask metadata mutation")
            after = self.delegate.document()
            row["routing_delta"] = {key: after[key] - before[key] for key in
                                    ("calls", "identity_calls", "fast_path_calls", "fallback_calls",
                                     "bonded_fast_path_calls", "bondless_fast_path_calls")}
            row.update(status="passed", binary_equal=True, source_unchanged=True, mask_unchanged=True)
            return observed
        except BaseException as exc:
            row.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)})
            raise

    def document(self) -> dict:
        return self.delegate.document()


def validate_audit(rows: list[dict], stats: dict, *, expected_calls: int = 20) -> None:
    require(len(rows) == expected_calls and stats["calls"] == expected_calls, "distance subset denominator differs")
    require(all(row["status"] == "passed" and row["binary_equal"] is True and row["source_unchanged"] is True
                and row["mask_unchanged"] is True for row in rows), "a native subset comparison did not pass")
    for key in ("bonded_fast_path_calls", "retained_bonds_fast_path"):
        require(type(stats[key]) is int and stats[key] > 0, "no actual bonded optimization: " + key)
    require(stats["fast_path_errors"] == stats["fallback_errors"] == 0, "subset errors recorded")
    require(stats["calls"] == stats["identity_calls"] + stats["fast_path_calls"] + stats["fallback_calls"], "subset call accounting differs")
    require(stats["fast_path_calls"] == stats["bonded_fast_path_calls"] + stats["bondless_fast_path_calls"], "subset graph routing accounting differs")
    for feature in ("atoms", "bonds"):
        require(stats[f"source_{feature}_fast_path"] == stats[f"retained_{feature}_fast_path"] +
                stats[f"removed_{feature}_fast_path"], "subset " + feature + " accounting differs")
    require(sum(stats["fallback_reasons"].values()) == stats["fallback_calls"], "fallback reason accounting differs")


def validate_observation(document: dict, *, selected: dict, bundle: dict, mode: str,
                         current_identity: str, outcomes: tuple) -> None:
    # Current source owns candidate evaluator identity. Never replace the old
    # bundle identity or mock production source_identity to admit a new result.
    equal({key: document[key] for key in ("schema_id", "case_id", "mode", "evaluator_identity", "evaluation_call", "record_count")},
          {"schema_id": contexts.REPORT_SCHEMA_ID, "case_id": selected["case"]["case_id"], "mode": mode,
           "evaluator_identity": current_identity, "evaluation_call": 1, "record_count": 5}, "current report identity")
    equal(document["input_ids"], selected["input_ids"], "pinned report input bytes")
    equal(document["evaluator_versions"], bundle["evaluator_versions"], "frozen report versions")
    equal(document["upstream_source_sha256"], bundle["upstream_source_sha256"], "frozen report source")
    legacy = document["legacy_outcomes"]
    equal(legacy, integration._legacy_return(outcomes), "runner return/report outcomes")
    require(all(type(value) is float and math.isfinite(value) and value >= 0 for value in legacy["rmsds"]), "invalid RMSD scalar")
    equal([value.hex() for value in legacy["rmsds"]], legacy["rmsds_binary64_hex"], "RMSD bits")
    historical = integration.common.legacy_projection(selected["expected"])
    equal({key: legacy[key] for key in historical}, historical, "historical legacy outcomes")
    integration.common.validate_full_report(document["fullReport"], selected=selected)
    require(len(document["fullReport"]["columns"]) == 126, "fullReport column denominator differs")
    immutable = document["input_immutability"]
    require(immutable["verified"] is True and immutable["pickle_policy"] == "AllProps|CoordsAsDouble", "molecule immutability not verified")
    equal(immutable["before"], immutable["after"], "input molecule mutation")


def inspect_inputs(root: Path, bundle_sha256: str) -> tuple[dict, dict, list[dict]]:
    equal(bundle_sha256, EXPECTED_BUNDLE_SHA256, "admission input bundle pin")
    bundle, manifest = integration.load_bundle(root, bundle_sha256)
    equal(bundle["source"]["commit"], INPUT_SOURCE_COMMIT, "original input preparation source")
    selected = [integration.selected_inputs(root, bundle, manifest, case_id, "replay") for case_id in CASES]
    return bundle, manifest, selected


def run_probe(*, input_root: Path, bundle_sha256: str, runtime_root: Path, report: dict) -> None:
    input_root = integration.inputs.frozen._no_symlink_path(input_root)
    bundle, manifest, selected_cases = inspect_inputs(input_root, bundle_sha256)
    current_source = integration.source_identity()
    report.update(input_artifact_run_id=INPUT_ARTIFACT_RUN_ID, input_bundle_sha256=bundle_sha256,
                  input_manifest_sha256=bundle["manifest_sha256"], input_preparation_source=bundle["source"],
                  input_evaluator_identities=bundle["evaluator_identities"], executing_source=current_source,
                  source_identity_relationship="old immutable inputs; current candidate execution")
    environment = integration.capture_environment(runtime_root)
    report["executing_environment_before"] = environment
    require("tools/check_posebusters_subset_inputs.py" in {row["path"] for row in environment["source_files"]},
            "executing probe is missing from tracked source snapshot")
    runtime = replay._load_runtime()
    equal(dict(runtime.versions), bundle["evaluator_versions"], "actual frozen evaluator versions")
    equal(dict(runtime.source_hashes), bundle["upstream_source_sha256"], "actual frozen upstream source")
    require(replay._cache_info_document(runtime.energy.get_average_energy.cache_info())["maxsize"] is None, "frozen energy LRU policy differs")
    for selected in selected_cases:
        case_id = selected["case"]["case_id"]
        case = {"case_id": case_id, "status": "running", "input_ids": selected["input_ids"],
                "descriptors": {role: selected["case"][role] for role in ("receptor", "reference", "native", "seed", "top5", "source_row")},
                "modes": {}, "distance_masks": []}
        report["cases"].append(case)
        documents = {}
        for mode in MODES:
            observed = []
            ctx = contexts.PoseBustersEvaluatorContext(case_id, mode=mode, report_observer=observed.append, collect_metrics=True)
            if mode == "prepared_subset":
                # Existing per-instance callback; no class/module/global patch.
                ctx._distance_filter = AuditedSubsetFilter(runtime, case["distance_masks"])
            mode_result = {"current_evaluator_identity": ctx.evaluator_identity,
                           "energy_before": replay._cache_info_document(runtime.energy.get_average_energy.cache_info())}
            case["modes"][mode] = mode_result
            started = time.perf_counter_ns()
            try:
                with ctx:
                    outcomes = runtime.runner._posebusters_outcomes(b"".join(selected["records"]),
                        native_payload=selected["native"], receptor_payload=selected["receptor"],
                        expected_pose_count=5, evaluation_context=ctx)
            finally:
                mode_result.update(audited_runner_call_ns=time.perf_counter_ns() - started, context=ctx.summary(),
                                   energy_after=replay._cache_info_document(runtime.energy.get_average_energy.cache_info()))
            require(len(observed) == 1, "runner did not emit exactly one full report")
            document = observed[0]
            mode_result["report"] = document
            validate_observation(document, selected=selected, bundle=bundle, mode=mode,
                                 current_identity=ctx.evaluator_identity, outcomes=outcomes)
            require(ctx.summary()["healthy"] is True and ctx.summary()["closed"] is True, "context did not close healthy")
            require(ctx.summary()["energy_cache"]["cleared_by_context"] is False, "energy LRU was cleared")
            documents[mode] = document
        equal(documents["reference"]["fullReport"], documents["prepared_subset"]["fullReport"], "paired fullReport")
        equal(documents["reference"]["legacy_outcomes"], documents["prepared_subset"]["legacy_outcomes"], "paired legacy outcomes")
        validate_audit(case["distance_masks"], case["modes"]["prepared_subset"]["context"]["subset_filter"])
        reselected = integration.selected_inputs(input_root, bundle, manifest, case_id, "replay")
        equal(reselected["input_ids"], selected["input_ids"], "post-evaluation input identities")
        require(reselected["records"] == selected["records"] and reselected["native"] == selected["native"]
                and reselected["receptor"] == selected["receptor"], "pinned input bytes changed")
        case.update(status="passed", full_report_equal=True, legacy_equal=True, input_bytes_unchanged=True)
    inspect_inputs(input_root, bundle_sha256)
    equal(integration.source_identity(), current_source, "executing source changed during admission")
    after = integration.capture_environment(runtime_root)
    integration.evidence.require_matching_environment(environment, after)
    report["executing_environment_after"] = after
    require(len(report["cases"]) == 2 and all(case["status"] == "passed" for case in report["cases"]), "pilot denominator differs")
    report.update(status="passed", all_passed=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = {"schema_id": SCHEMA_ID, "status": "failed", "all_passed": False, "cases": [],
              "case_ids": list(CASES), "record_count_per_case": 5, "modes": list(MODES),
              "new_docking_performed": False, "performance_claim_eligible": False,
              "timing_scope": "doubled subset audit; sequential same-process modes; not a benchmark",
              "energy_lru_cleared_by_probe": False, "implementation_id": subset.IMPLEMENTATION_ID}
    try:
        output = integration.inputs.frozen._no_symlink_path(args.output)
        require(not output.is_relative_to(args.input_root.resolve()), "output must be outside immutable input artifact")
        require(not output.exists(), "admission output must be fresh")
    except BaseException:
        # An unsafe or existing output is never an acceptable failure-report
        # destination; do not mutate the immutable input or previous evidence.
        traceback.print_exc(file=sys.stderr)
        return 1
    try:
        run_probe(input_root=args.input_root, bundle_sha256=args.bundle_sha256, runtime_root=args.runtime_root, report=report)
    except BaseException as exc:
        report.update(status="failed", all_passed=False, error={"type": type(exc).__name__, "message": str(exc)})
        traceback.print_exc(file=sys.stderr)
    try:
        report["report_sha256"] = integration.digest(report)
        integration.isolation.atomic_json(output, report, replace=False)
    except BaseException:
        traceback.print_exc(file=sys.stderr)
        return 1
    print(f"subset input admission: {report['status']}; report={output}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
