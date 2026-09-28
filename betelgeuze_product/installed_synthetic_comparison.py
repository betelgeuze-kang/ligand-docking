"""Installed-wheel, budgeted four-arm comparison on bounded development inputs.

Synthetic and native v4 fit sources use distinct versioned checkpoints. Native
v4 has no prepared-structure identity link yet, so every request must be null.
Neither route opens checkout ``tools`` modules or evaluation outcomes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import fcntl
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
import uuid

from .comparison_receipts import (
    ARMS, HEX, MAX_JSON_BYTES, MAX_POOL, _canonical, _digest, _entry,
    _finite, _json, _load, _private_dir, _regular_file, _require, _sha,
)
from .prepared_cross_numeric_reference import MAX_BYTES as MAX_POSE_BYTES, check_report

PROTOCOL = "installed_synthetic_prepared_comparison_protocol_v1"
FROZEN = "installed_synthetic_prepared_comparison_frozen_v1"
RESULT = "installed_synthetic_prepared_comparison_result_v1"
NATIVE_PROTOCOL = "installed_native_v4_fit_comparison_protocol_v1"
NATIVE_FROZEN = "installed_native_v4_fit_comparison_frozen_v1"
NATIVE_RESULT = "installed_native_v4_fit_comparison_result_v1"
NATIVE_SOURCE_KIND = "native_chembl_receptor_research_v4_fit"
MAX_BUDGET_SECONDS = 3600.0
BOUND_ENVIRONMENT = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                     "CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES")


def _publish(path: Path, value, *, deadline=None, max_bytes=MAX_JSON_BYTES) -> bool:
    """Create an immutable canonical JSON file, without replacing a prior file."""
    raw = _canonical(value) + b"\n"
    _require(len(raw) <= max_bytes, "comparison_json_capacity_exceeded")
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex)
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if deadline is not None and time.monotonic() >= deadline:
            return False
        os.link(temporary, path, follow_symlinks=False)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return True
    finally:
        temporary.unlink(missing_ok=True)


def _committed(path: Path):
    raw = _regular_file(path, MAX_JSON_BYTES)
    value = _json(raw)
    _require(raw == _canonical(value) + b"\n", "noncanonical_installed_receipt")
    return value


def _bound_json(ref: dict):
    _require(type(ref) is dict and set(ref) == {"path", "sha256"}
             and type(ref["path"]) is str and Path(ref["path"]).is_absolute()
             and type(ref["sha256"]) is str and HEX.fullmatch(ref["sha256"]) is not None,
             "invalid_bound_request_reference")
    raw = _regular_file(Path(ref["path"]), MAX_JSON_BYTES)
    _require(_digest(raw) == ref["sha256"], "comparison_request_hash_mismatch")
    return _json(raw)


def _rows(source: dict) -> list[dict]:
    _require(type(source) is dict and set(source) == {"kind", "rows"}
             and source["kind"] == "synthetic_constants"
             and type(source["rows"]) is list and 1 <= len(source["rows"]) <= MAX_POOL,
             "only_bounded_synthetic_source_supported")
    return _validate_rows(copy.deepcopy(source["rows"]))


def _validate_rows(result: list[dict]) -> list[dict]:
    from rdkit import Chem

    seen_ids, component_roles, chemical_roles = set(), {}, {}
    for row in result:
        _require(type(row) is dict and set(row) == {
            "record_id", "role", "component_id", "smiles", "fit_value", "assay_id",
        }, "invalid_synthetic_row_fields")
        _require(all(type(row[key]) is str and row[key]
                     for key in ("record_id", "component_id", "assay_id"))
                 and row["record_id"] not in seen_ids
                 and row["role"] in {"fit", "calibration", "development_test"},
                 "invalid_synthetic_row_identity")
        seen_ids.add(row["record_id"])
        component = row["component_id"]
        _require(component not in component_roles or component_roles[component] == row["role"],
                 "cross_role_component_leakage")
        component_roles[component] = row["role"]
        value = row["fit_value"]
        _require(value is None or (row["role"] == "fit" and _finite(value)),
                 "evaluation_label_before_freeze")
        smiles = row["smiles"]
        _require(smiles is None or (type(smiles) is str and smiles), "invalid_smiles")
        if smiles is not None:
            molecule = Chem.MolFromSmiles(smiles)
            _require(molecule is not None and molecule.GetNumAtoms() > 0,
                     "invalid_synthetic_smiles")
            _require(not any(group.GetGroupType() != Chem.StereoGroupType.STEREO_ABSOLUTE
                             for group in molecule.GetStereoGroups()),
                     "unresolved_enhanced_stereochemistry")
            canonical = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            _require(canonical not in chemical_roles or chemical_roles[canonical] == row["role"],
                     "cross_role_chemical_identity_leakage")
            chemical_roles[canonical] = row["role"]
            row["smiles"] = canonical
    _require(any(r["role"] == "fit" and r["smiles"] and r["fit_value"] is not None
                 for r in result)
             and any(r["role"] == "development_test" for r in result),
             "missing_fit_or_candidate_pool")
    return result


def _native_rows(reference: dict) -> tuple[list[dict], dict]:
    """Project only source-derived fit labels and preassigned candidate IDs."""
    from .installed_native_v4_source import _verified_intake

    receipt, scope, original = _verified_intake(reference)
    _require(scope["endpoint"] == "Ki" and scope["target_annotation"]
             and scope["physical_target_state_verified"] is False,
             "unsupported_native_comparison_scope")
    rows = []
    for row in original:
        role = row["assigned_role"]
        identity = row["chemical_identity"]
        issues = row["prediction_issues"]
        smiles = identity["canonical_isomeric_smiles"] if identity and not issues else None
        value = (row["observation"]["negative_log10_molar"]
                 if role == "fit" and row["eligible_for_point_model"] else None)
        _require(value is None or _finite(value), "invalid_native_fit_point")
        rows.append({
            "record_id": row["record_id"], "role": role,
            "component_id": row["component_id"], "smiles": smiles,
            "fit_value": value, "assay_id": row["assay_id"],
        })
    checked = _validate_rows(rows)
    selected = [r for r in checked if r["role"] == "fit" and r["fit_value"] is not None]
    _require(len(selected) >= 5 and len({r["component_id"] for r in selected}) >= 2,
             "insufficient_supported_native_fit_rows_or_components")
    return checked, receipt


def _features(smiles: list[str]):
    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import rdFingerprintGenerator

    generator = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=1024, includeChirality=True)
    matrix = []
    for text in smiles:
        molecule = Chem.MolFromSmiles(text)
        _require(molecule is not None, "invalid_inference_smiles")
        matrix.append(generator.GetFingerprintAsNumPy(molecule))
    return np.asarray(matrix, dtype=np.float64).reshape(len(smiles), 1024)


def _predictions(frozen: dict, arm: str) -> dict[str, float]:
    if arm == "engine":
        return {}
    import numpy as np

    selected = [row for row in frozen["rows"] if row["role"] == "fit"
                and row["smiles"] and row["fit_value"] is not None]
    candidates = {row["record_id"]: row for row in frozen["rows"]
                  if row["record_id"] in frozen["pool"]}
    valid = [rid for rid in frozen["pool"] if candidates[rid]["smiles"]]
    x = _features([row["smiles"] for row in selected])
    z = _features([candidates[rid]["smiles"] for rid in valid])
    y = np.asarray([row["fit_value"] for row in selected], dtype=np.float64)
    if arm == "ai_engine":
        from sklearn.linear_model import Ridge

        weights = None
        if frozen["source_kind"] == NATIVE_SOURCE_KIND:
            repetitions = Counter((row["component_id"], row["smiles"])
                                  for row in selected)
            weights = np.asarray([1.0 / repetitions[(row["component_id"], row["smiles"])]
                                  for row in selected], dtype=np.float64)
        model = Ridge(alpha=10.0, solver="cholesky").fit(x, y, sample_weight=weights)
        values = model.predict(z) if valid else []
    else:
        unique = {}
        for index, row in enumerate(selected):
            unique.setdefault(row["smiles"], []).append(index)
        indices = [positions[0] for positions in unique.values()]
        fx = x[indices]
        fy = np.asarray([y[positions].mean() for positions in unique.values()])
        values = []
        for query in z:
            intersection = fx @ query
            union = fx.sum(axis=1) + query.sum() - intersection
            similarity = np.divide(intersection, union, out=np.ones_like(union),
                                   where=union != 0)
            values.append(float(fy[similarity == similarity.max()].mean()))
    return {rid: float(value) for rid, value in zip(valid, values)}


def _order(frozen: dict, arm: str, predictions: dict) -> list[str]:
    if arm == "engine":
        return list(frozen["pool"])
    seed = frozen["protocol"]["selection_seed"]
    ordinal = {rid: index for index, rid in enumerate(frozen["pool"])}
    tie = {rid: _sha({"seed": seed, "pool_index": index})
           for rid, index in ordinal.items()}
    return sorted(predictions,
                  key=lambda rid: (-predictions[rid], tie[rid], ordinal[rid]))


def _comparison_runtime() -> dict:
    from betelgeuze_engine.product.prepared_pose_journal import _runtime_binding
    import torch

    torch.set_num_threads(1)
    runtime = _runtime_binding()
    runtime["comparison_selector_dependencies"] = {
        name: importlib.metadata.version(name) for name in ("scikit-learn", "scipy")}
    runtime["comparison_environment"] = {
        name: os.environ.get(name) for name in BOUND_ENVIRONMENT}
    return runtime


def freeze(protocol: dict) -> dict:
    _require(type(protocol) is dict and set(protocol) == {
        "schema_version", "source", "requests", "budget_seconds_per_arm",
        "max_engine_calls_per_arm", "arm_order", "selection_seed", "tie_policy",
    } and protocol["schema_version"] in {PROTOCOL, NATIVE_PROTOCOL},
             "unsupported_installed_comparison_protocol")
    native = protocol["schema_version"] == NATIVE_PROTOCOL
    budget, cap = protocol["budget_seconds_per_arm"], protocol["max_engine_calls_per_arm"]
    _require(_finite(budget) and 0 < budget <= MAX_BUDGET_SECONDS
             and type(cap) is int and 1 <= cap <= MAX_POOL,
             "invalid_comparison_budget")
    _require(type(protocol["arm_order"]) is list and len(protocol["arm_order"]) == 4
             and set(protocol["arm_order"]) == set(ARMS)
             and protocol["tie_policy"] == "seeded_pool_order"
             and type(protocol["selection_seed"]) is int
             and 0 <= protocol["selection_seed"] < 2**32,
             "invalid_prespecified_comparison_order")
    rows, source_verification = (_native_rows(protocol["source"])
                                 if native else (_rows(protocol["source"]), None))
    pool = [row["record_id"] for row in rows if row["role"] == "development_test"]
    _require(type(protocol["requests"]) is dict and set(protocol["requests"]) == set(pool),
             "candidate_request_denominator_mismatch")
    from betelgeuze_engine.product.prepared_pose_journal import _input_binding

    requests, source_inputs = {}, {}
    for rid in pool:
        ref = protocol["requests"][rid]
        _require(not native or ref is None,
                 "native_prepared_candidate_identity_link_not_supported")
        request = None if ref is None else _bound_json(ref)
        _require(request is None or (type(request) is dict and request.get("schema_version")
                 == "prepared_rigid_pose_cross_request_v1"),
                 "requires_existing_rigid_pose_request")
        requests[rid] = request
        source_inputs[rid] = None if request is None else _input_binding(request)
    runtime = _comparison_runtime()
    frozen = {
        "schema_version": NATIVE_FROZEN if native else FROZEN,
        "protocol": copy.deepcopy(protocol),
        "rows": rows, "pool": pool, "requests": requests,
        "source_inputs": source_inputs, "runtime": runtime,
        "source_kind": NATIVE_SOURCE_KIND if native else "synthetic_constants",
        "evaluation_labels_read": 0,
        "scientifically_validated": False, "source_authenticated": False,
        "same_prepared_assay_state_verified": False,
        "product_ranking_enabled": False,
    }
    if native:
        frozen["source_verification"] = source_verification
    _require(len(_canonical(frozen)) <= MAX_JSON_BYTES,
             "frozen_comparison_capacity_exceeded")
    return frozen


def _envelope(run_dir: Path) -> tuple[dict, str]:
    value = _committed(run_dir / "frozen.json")
    _require(type(value) is dict and set(value) == {"payload", "sha256"}
             and type(value["sha256"]) is str
             and HEX.fullmatch(value["sha256"]) is not None
             and type(value["payload"]) is dict
             and value["payload"].get("schema_version") in {FROZEN, NATIVE_FROZEN}
             and _sha(value["payload"]) == value["sha256"],
             "installed_frozen_binding_mismatch")
    return value["payload"], value["sha256"]


def _report_ref(run_dir: Path, arm: str, rid: str) -> tuple[Path, str]:
    relative = f"{arm}/{_sha(rid)}.poses.json"
    return run_dir / relative, relative


def _stable_mapping_keys(original, normalized) -> bool:
    pending = [(original, normalized)]
    while pending:
        value, decoded = pending.pop()
        if isinstance(value, dict):
            if (type(decoded) is not dict or len(value) != len(decoded)
                    or any(type(key) is not str for key in value)
                    or value.keys() != decoded.keys()):
                return False
            pending.extend((item, decoded[key]) for key, item in value.items())
        elif isinstance(value, (list, tuple)):
            if type(decoded) is not list or len(value) != len(decoded):
                return False
            pending.extend(zip(value, decoded))
    return True


def worker(run_dir: Path, arm: str, deadline: float) -> None:
    _require(arm in ARMS and _finite(deadline) and deadline > 0,
             "invalid_comparison_worker_request")
    run_dir = Path(run_dir).absolute()
    _private_dir(run_dir)
    directory = run_dir / arm
    _private_dir(directory)
    frozen, binding = _envelope(run_dir)
    _require(_comparison_runtime() == frozen["runtime"],
             "installed_worker_runtime_changed")
    tick = time.perf_counter()
    predictions = _predictions(frozen, arm)
    order = _order(frozen, arm, predictions)
    _publish(directory / "priority.json", {
        "binding": binding, "arm": arm, "order": order,
        "predictions": predictions,
        "selector_kind": ("source_order" if arm == "engine" else
                          "fit_only_ridge" if arm == "ai_engine" else
                          "fit_only_morgan_tanimoto"),
        "setup_wall_seconds": time.perf_counter() - tick,
        "evaluation_labels_read": 0,
    })
    if arm != "similarity":
        from betelgeuze_engine.product.prepared_rigid_poses import evaluate_rigid_pose_request
    called, stop_reason = 0, "order_exhausted"
    for rid in order:
        if time.monotonic() >= deadline:
            stop_reason = "deadline"
            break
        if arm != "similarity" and called >= frozen["protocol"]["max_engine_calls_per_arm"]:
            stop_reason = "engine_call_cap"
            break
        started, cpu = time.perf_counter(), time.process_time()
        row = {
            "record_id": rid, "arm": arm, "binding": binding,
            "prediction": predictions.get(rid), "status": "unsupported",
            "score": None, "reason": "prepared_input_missing",
        }
        try:
            if arm == "similarity":
                row.update(status="evaluated", score=predictions[rid], reason=None)
            elif frozen["requests"][rid] is not None:
                called += 1
                raw_report = evaluate_rigid_pose_request(frozen["requests"][rid])
                report = _json(_canonical(raw_report))
                _require(_stable_mapping_keys(raw_report, report),
                         "pose_report_mapping_keys_changed")
                checked = check_report(report)
                path, relative = _report_ref(run_dir, arm, rid)
                if not _publish(path, report, deadline=deadline, max_bytes=MAX_POSE_BYTES):
                    stop_reason = "deadline"
                    break
                ref = _entry(relative, _regular_file(path, MAX_POSE_BYTES))
                row.update(status="failed", reason="incomplete_or_failed_numeric_pose",
                           pose_report=ref, pose_denominator=report["denominator"],
                           numeric_denominator=checked["denominator"])
                if checked["status"] == "passed":
                    row.update(status="evaluated", reason=None,
                               score=min(item["result"]["quantities"]["cross_total_kcal_per_mol"]
                                         for item in report["rows"]))
        except Exception as exc:
            row.update(status="failed", score=None,
                       reason=type(exc).__name__ + ":" + str(exc))
        row.update(cost={"wall_seconds": time.perf_counter() - started,
                         "cpu_seconds": time.process_time() - cpu},
                   completed_monotonic=time.monotonic())
        if not _publish(directory / f"{_sha(rid)}.row.json",
                        {"payload": row, "sha256": _sha(row)}, deadline=deadline):
            stop_reason = "deadline"
            break
    _publish(directory / "worker-complete.json", {
        "binding": binding, "engine_calls": called, "stop_reason": stop_reason,
        "process_cpu_seconds": time.process_time(),
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    })


def _read_report(run_dir: Path, arm: str, rid: str, ref: dict):
    path, relative = _report_ref(run_dir, arm, rid)
    _require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}
             and ref["path"] == relative and type(ref["bytes"]) is int
             and type(ref["sha256"]) is str
             and HEX.fullmatch(ref["sha256"]) is not None,
             "invalid_installed_pose_report_reference")
    raw = _regular_file(path, MAX_POSE_BYTES)
    _require(_entry(relative, raw) == ref, "installed_pose_report_hash_mismatch")
    return _json(raw)


def _summary(run_dir: Path, arm: str, frozen: dict, binding: str) -> dict:
    directory = run_dir / arm
    _private_dir(directory)
    completion = _committed(directory / "completion.json")
    _require(type(completion) is dict and completion.get("binding") == binding
             and completion.get("status") in {
                 "complete", "worker_failed", "budget_exhausted",
                 "interrupted_budget_forfeited",
             }
             and completion.get("budget_seconds") == frozen["protocol"]["budget_seconds_per_arm"]
             and _finite(completion.get("deadline")) and completion["deadline"] > 0,
             "invalid_installed_completion")
    elapsed = completion.get("measured_process_wall_seconds")
    if completion["status"] == "interrupted_budget_forfeited":
        _require(elapsed is None and completion.get("termination_overhead_seconds") is None,
                 "invalid_interrupted_cost")
    else:
        _require(_finite(elapsed) and elapsed >= 0
                 and completion.get("termination_overhead_seconds")
                 == max(0.0, elapsed - completion["budget_seconds"])
                 and ((completion["status"] == "budget_exhausted"
                       and elapsed >= completion["budget_seconds"])
                      or (completion["status"] != "budget_exhausted"
                          and elapsed <= completion["budget_seconds"])),
                 "invalid_installed_completion_cost")
    attempt = _committed(directory / "attempt.json")
    _require(type(attempt) is dict and attempt.get("binding") == binding
             and _finite(attempt.get("started_monotonic"))
             and attempt["started_monotonic"] < completion["deadline"]
             and attempt.get("deadline") == completion["deadline"]
             and attempt["deadline"] == attempt["started_monotonic"] + completion["budget_seconds"],
             "invalid_installed_attempt")
    priority = (_committed(directory / "priority.json")
                if (directory / "priority.json").exists() else None)
    worker_complete = (_committed(directory / "worker-complete.json")
                       if (directory / "worker-complete.json").exists() else None)
    if priority is not None:
        _require(type(priority) is dict and priority.get("binding") == binding
                 and priority.get("arm") == arm
                 and priority.get("evaluation_labels_read") == 0
                 and _finite(priority.get("setup_wall_seconds"))
                 and priority["setup_wall_seconds"] >= 0,
                 "invalid_installed_priority")
        predicted = _predictions(frozen, arm)
        expected_selector = ("source_order" if arm == "engine" else
                             "fit_only_ridge" if arm == "ai_engine" else
                             "fit_only_morgan_tanimoto")
        _require(priority.get("predictions") == predicted
                 and priority.get("order") == _order(frozen, arm, predicted)
                 and priority.get("selector_kind") == expected_selector,
                 "installed_priority_recalculation_mismatch")
    else:
        _require(completion["status"] != "complete", "missing_completed_priority")
    if worker_complete is not None:
        cap = frozen["protocol"]["max_engine_calls_per_arm"]
        _require(type(worker_complete) is dict
                 and worker_complete.get("binding") == binding
                 and type(worker_complete.get("engine_calls")) is int
                 and 0 <= worker_complete["engine_calls"] <= cap
                 and (arm != "similarity" or worker_complete["engine_calls"] == 0)
                 and worker_complete.get("stop_reason") in {
                     "order_exhausted", "engine_call_cap", "deadline"}
                 and (worker_complete["stop_reason"] != "engine_call_cap"
                      or (arm != "similarity" and worker_complete["engine_calls"] == cap))
                 and _finite(worker_complete.get("process_cpu_seconds"))
                 and worker_complete["process_cpu_seconds"] >= 0
                 and type(worker_complete.get("process_peak_rss_kib")) is int
                 and worker_complete["process_peak_rss_kib"] >= 0,
                 "invalid_installed_worker_completion")
    else:
        _require(completion["status"] != "complete", "missing_completed_worker_observation")
    rows, processed = [], []
    for rid in frozen["pool"]:
        path = directory / f"{_sha(rid)}.row.json"
        value = {"record_id": rid, "status": "not_processed", "score": None,
                 "reason": completion["status"]}
        if path.exists():
            wrapped = _committed(path)
            _require(type(wrapped) is dict and set(wrapped) == {"payload", "sha256"}
                     and _sha(wrapped["payload"]) == wrapped["sha256"],
                     "installed_row_hash_mismatch")
            item = wrapped["payload"]
            _require(type(item) is dict and item.get("binding") == binding
                     and item.get("record_id") == rid and item.get("arm") == arm
                     and _finite(item.get("completed_monotonic")),
                     "invalid_installed_row_identity")
            if item["completed_monotonic"] <= completion["deadline"]:
                value = item
                processed.append(item)
            else:
                value["reason"] = "completed_after_budget"
        elif priority is not None:
            if arm != "engine" and rid not in priority["order"]:
                value.update(status="unsupported", reason="predictor_abstained")
            elif completion["status"] == "complete" and worker_complete["stop_reason"] in {
                "engine_call_cap", "deadline",
            }:
                value["reason"] = worker_complete["stop_reason"]
        _require(value["status"] in {"evaluated", "failed", "unsupported", "not_processed"}
                 and ((value["status"] == "evaluated" and _finite(value["score"]))
                      or (value["status"] != "evaluated" and value["score"] is None)),
                 "invalid_installed_row_score")
        if "completed_monotonic" in value:
            _require(priority is not None and rid in priority["order"]
                     and value.get("prediction") == priority["predictions"].get(rid)
                     and type(value.get("cost")) is dict
                     and all(_finite(value["cost"].get(key))
                             and value["cost"][key] >= 0
                             for key in ("wall_seconds", "cpu_seconds")),
                     "installed_row_priority_or_cost_mismatch")
        ref = value.get("pose_report")
        if ref is not None:
            _require(arm != "similarity", "similarity_has_pose_report")
            report = _read_report(run_dir, arm, rid, ref)
            checked = check_report(report)
            _require(value.get("pose_denominator") == report["denominator"]
                     and value.get("numeric_denominator") == checked["denominator"],
                     "installed_pose_report_denominator_mismatch")
            if checked["status"] == "passed":
                expected = min(item["result"]["quantities"]["cross_total_kcal_per_mol"]
                               for item in report["rows"])
                _require(value["status"] == "evaluated" and value["score"] == expected,
                         "installed_pose_report_score_mismatch")
            else:
                _require(value["status"] == "failed", "installed_pose_report_status_mismatch")
        elif arm != "similarity" and value["status"] == "evaluated":
            raise ValueError("installed_evaluated_row_missing_pose_report")
        if arm == "similarity" and value["status"] == "evaluated":
            _require(value["score"] == priority["predictions"][rid],
                     "installed_similarity_score_mismatch")
        rows.append(value)
    if priority is not None:
        observed = sorted(processed, key=lambda item: item["completed_monotonic"])
        _require([item["record_id"] for item in observed]
                 == priority["order"][:len(observed)],
                 "installed_committed_priority_sequence_mismatch")
        if worker_complete is not None and worker_complete["stop_reason"] == "order_exhausted":
            _require(len(processed) == len(priority["order"]),
                     "installed_worker_missing_ordered_row")
    else:
        _require(not processed, "row_without_priority")
    if worker_complete is not None:
        reports = sum("pose_report" in row for row in processed)
        _require(worker_complete["engine_calls"] >= reports,
                 "installed_engine_calls_less_than_reports")
        expected_calls = sum(
            arm != "similarity" and frozen["requests"][row["record_id"]] is not None
            for row in processed)
        uncommitted_call = worker_complete["engine_calls"] - expected_calls
        _require(0 <= uncommitted_call <= (1 if worker_complete["stop_reason"] == "deadline" else 0),
                 "installed_engine_call_count_mismatch")
    direction = -1 if arm == "similarity" else 1
    ranked = sorted((row for row in rows if row["status"] == "evaluated"),
                    key=lambda row: (direction * row["score"], row["record_id"]))
    return {
        "priority": priority, "worker_complete": worker_complete,
        "completion": completion, "rows": rows,
        "denominator": {"requested": len(rows),
                        **dict(Counter(row["status"] for row in rows))},
        "ranked_record_ids": [row["record_id"] for row in ranked],
        "score_quantity": ("predicted_negative_log10_molar_endpoint"
                           if arm == "similarity" else "existing_cross_only_kcal_per_mol"),
        "combined_assay_energy_score": None,
    }


def _lock(path: Path, *, create: bool, shared: bool = False):
    flags = os.O_RDWR | os.O_NOFOLLOW
    if create:
        flags |= os.O_CREAT
    fd = os.open(path, flags, 0o600)
    try:
        observed = os.fstat(fd)
        _require(stat.S_ISREG(observed.st_mode) and observed.st_nlink == 1
                 and observed.st_uid == os.geteuid()
                 and not observed.st_mode & 0o077,
                 "comparison_lock_not_private_regular_file")
        fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _stop_child(child: subprocess.Popen) -> None:
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    child.wait()


def _one_arm(run_dir: Path, arm: str, frozen: dict, binding: str, *, resume: bool) -> dict:
    directory = run_dir / arm
    directory.mkdir(mode=0o700, exist_ok=resume)
    _private_dir(directory)
    attempt_path = directory / "attempt.json"
    completion_path = directory / "completion.json"
    if not attempt_path.exists():
        _require(not completion_path.exists(), "completion_without_attempt")
        tick = time.monotonic()
        budget = frozen["protocol"]["budget_seconds_per_arm"]
        deadline = tick + budget
        lease = _lock(directory / "worker.lock", create=True)
        try:
            _publish(attempt_path, {"binding": binding, "started_monotonic": tick,
                                    "deadline": deadline})
            command = [sys.executable, "-B", "-m",
                       "betelgeuze_product.installed_synthetic_comparison", "worker",
                       "--run-dir", str(run_dir), "--arm", arm,
                       "--deadline", str(deadline)]
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            with (directory / "worker.log").open("x", encoding="utf-8") as log:
                child = subprocess.Popen(
                    command, cwd=Path(__file__).resolve().parents[1], env=environment,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                    pass_fds=(lease,))
                status = "complete"
                try:
                    code = child.wait(timeout=max(0.001, deadline - time.monotonic()))
                    if code != 0:
                        status = "worker_failed"
                except subprocess.TimeoutExpired:
                    _stop_child(child)
                    status = "budget_exhausted"
                except BaseException:
                    _stop_child(child)
                    raise
            elapsed = time.monotonic() - tick
            if elapsed > budget:
                status = "budget_exhausted"
            _publish(completion_path, {
                "binding": binding, "status": status, "deadline": deadline,
                "measured_process_wall_seconds": elapsed, "budget_seconds": budget,
                "termination_overhead_seconds": max(0.0, elapsed - budget),
            })
        finally:
            os.close(lease)
    elif not completion_path.exists():
        # The child inherited this lease. A live child prevents a second run.
        lease = _lock(directory / "worker.lock", create=False)
        os.close(lease)
        attempt = _committed(attempt_path)
        _require(type(attempt) is dict and attempt.get("binding") == binding,
                 "interrupted_attempt_binding_mismatch")
        _publish(completion_path, {
            "binding": binding, "status": "interrupted_budget_forfeited",
            "deadline": attempt["deadline"],
            "measured_process_wall_seconds": None,
            "budget_seconds": frozen["protocol"]["budget_seconds_per_arm"],
            "termination_overhead_seconds": None,
        })
    return _summary(run_dir, arm, frozen, binding)


def _read_protocol(path: Path) -> dict:
    value = _load(Path(path))
    _require(type(value) is dict, "invalid_installed_protocol_json")
    return value


def _validate_result_header(result: dict, frozen: dict, binding: str) -> None:
    protocol = frozen["protocol"]
    native = frozen["source_kind"] == NATIVE_SOURCE_KIND
    expected_schema = NATIVE_RESULT if native else RESULT
    expected_source_kind = NATIVE_SOURCE_KIND if native else "synthetic_constants"
    _require(type(result) is dict and set(result) == {
        "schema_version", "binding", "pool", "arm_order", "arms",
        "budget_seconds_per_arm", "max_engine_calls_per_arm", "source_kind",
        "evaluation_labels_read", "selector_recomputed_locally",
        "source_authenticated", "scientifically_validated",
        "same_prepared_assay_state_verified", "product_ranking_enabled",
        "common_validation_seconds", "arm_execution_and_summary_wall_seconds",
        "orchestrator_wall_seconds", "cost_scope",
        "upstream_acquisition_preparation_and_pose_generation_measured",
    } and result["schema_version"] == expected_schema
             and result["binding"] == binding
             and result["pool"] == frozen["pool"]
             and result["arm_order"] == protocol["arm_order"]
             and type(result["arms"]) is dict and set(result["arms"]) == set(ARMS)
             and result["budget_seconds_per_arm"] == protocol["budget_seconds_per_arm"]
             and result["max_engine_calls_per_arm"] == protocol["max_engine_calls_per_arm"]
             and result["source_kind"] == expected_source_kind
             and result["evaluation_labels_read"] == 0
             and result["selector_recomputed_locally"] is True
             and result["source_authenticated"] is False
             and result["scientifically_validated"] is False
             and result["same_prepared_assay_state_verified"] is False
             and result["product_ranking_enabled"] is False
             and result["upstream_acquisition_preparation_and_pose_generation_measured"] is False
             and result["cost_scope"] ==
             "installed_input_validation_fit_inference_supplied_pose_scoring_worker_io_and_summary"
             and all(_finite(result[key]) and result[key] >= 0
                     for key in ("common_validation_seconds",
                                 "arm_execution_and_summary_wall_seconds",
                                 "orchestrator_wall_seconds")),
             "invalid_installed_result_header")


def run(protocol: dict, output_dir: Path, *, resume: bool = False) -> dict:
    started = time.perf_counter()
    frozen = freeze(protocol)
    setup_seconds = time.perf_counter() - started
    binding = _sha(frozen)
    root = Path(output_dir).absolute()
    if resume:
        _private_dir(root)
    else:
        root.mkdir(mode=0o700)
    lock = _lock(root / "run.lock", create=not resume)
    try:
        if resume:
            observed, observed_binding = _envelope(root)
            _require(observed_binding == binding and observed == frozen,
                     "installed_resume_input_or_runtime_changed")
        else:
            _publish(root / "frozen.json", {"payload": frozen, "sha256": binding})
        final = root / "comparison.json"
        if resume and final.exists():
            result = _committed(final)
            _validate_result_header(result, frozen, binding)
            for arm in ARMS:
                _require(_summary(root, arm, frozen, binding) == result["arms"][arm],
                         "installed_resume_summary_mismatch")
            return result
        arms = {}
        summary_started = time.perf_counter()
        for arm in protocol["arm_order"]:
            arms[arm] = _one_arm(root, arm, frozen, binding, resume=resume)
        summary_seconds = time.perf_counter() - summary_started
        _require(freeze(protocol) == frozen, "installed_inputs_changed_during_comparison")
        result = {
            "schema_version": (NATIVE_RESULT if frozen["source_kind"] == NATIVE_SOURCE_KIND
                               else RESULT),
            "binding": binding, "pool": frozen["pool"],
            "arm_order": protocol["arm_order"], "arms": arms,
            "budget_seconds_per_arm": protocol["budget_seconds_per_arm"],
            "max_engine_calls_per_arm": protocol["max_engine_calls_per_arm"],
            "source_kind": frozen["source_kind"], "evaluation_labels_read": 0,
            "selector_recomputed_locally": True, "source_authenticated": False,
            "scientifically_validated": False,
            "same_prepared_assay_state_verified": False,
            "product_ranking_enabled": False,
            "common_validation_seconds": setup_seconds,
            "arm_execution_and_summary_wall_seconds": summary_seconds,
            "orchestrator_wall_seconds": time.perf_counter() - started,
            "cost_scope": "installed_input_validation_fit_inference_supplied_pose_scoring_worker_io_and_summary",
            "upstream_acquisition_preparation_and_pose_generation_measured": False,
        }
        _publish(final, result)
        return result
    finally:
        os.close(lock)


def verify_run(protocol: dict, run_dir: Path) -> dict:
    """Read-only checkpoint/result verification with current input/runtime binding."""
    outcome = {
        "schema_version": ("installed_native_v4_fit_comparison_verification_v1"
                           if type(protocol) is dict
                           and protocol.get("schema_version") == NATIVE_PROTOCOL else
                           "installed_synthetic_comparison_verification_v1"),
        "status": "invalid", "exit_code": 2, "reason": None,
        "execution_performed": False, "source_authenticated": False,
        "scientifically_validated": False,
    }
    lock = None
    try:
        root = Path(run_dir).absolute()
        _private_dir(root)
        lock = _lock(root / "run.lock", create=False, shared=True)
        frozen = freeze(protocol)
        saved, binding = _envelope(root)
        _require(saved == frozen and binding == _sha(frozen),
                 "installed_verify_input_or_runtime_changed")
        result = _committed(root / "comparison.json")
        _validate_result_header(result, frozen, binding)
        for arm in ARMS:
            _require(_summary(root, arm, frozen, binding) == result["arms"][arm],
                     "installed_result_summary_mismatch")
        outcome.update(status="verified", exit_code=0, reason=None,
                       binding=binding, pool_count=len(frozen["pool"]),
                       arms_verified=list(ARMS))
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        outcome["reason"] = str(exc) if type(exc) is ValueError else type(exc).__name__
    finally:
        if lock is not None:
            os.close(lock)
    return outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "resume", "verify-run"):
        command = commands.add_parser(name)
        command.add_argument("--protocol", type=Path, required=True)
        command.add_argument("--run-dir", type=Path, required=True)
    internal = commands.add_parser("worker", help=argparse.SUPPRESS)
    internal.add_argument("--run-dir", type=Path, required=True)
    internal.add_argument("--arm", choices=ARMS, required=True)
    internal.add_argument("--deadline", type=float, required=True)
    args = parser.parse_args(argv)
    if args.command == "worker":
        worker(args.run_dir, args.arm, args.deadline)
        return 0
    protocol = _read_protocol(args.protocol)
    if args.command == "verify-run":
        outcome = verify_run(protocol, args.run_dir)
    else:
        result = run(protocol, args.run_dir, resume=args.command == "resume")
        outcome = {"schema_version": ("installed_native_v4_fit_comparison_cli_v1"
                                      if protocol.get("schema_version") == NATIVE_PROTOCOL else
                                      "installed_synthetic_comparison_cli_v1"),
                   "status": "committed", "exit_code": 0,
                   "binding": result["binding"], "pool_count": len(result["pool"]),
                   "arms": {arm: result["arms"][arm]["denominator"] for arm in ARMS},
                   "scientifically_validated": False}
    print(json.dumps(outcome, sort_keys=True, allow_nan=False))
    return outcome["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
