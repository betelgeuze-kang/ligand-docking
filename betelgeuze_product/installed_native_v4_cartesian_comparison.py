"""Opt-in native registered Cartesian comparison protocol v4.

Original v1.2 documents remain the sole source descriptor inputs. Only after
native role, chemistry, charge, stereochemistry and common-cohort admission
do we explicitly convert them to 1.3 Cartesian execution requests.
"""
from __future__ import annotations

import copy
from collections import Counter
import hashlib
import math
import os
from pathlib import Path
import resource
import time

from . import installed_synthetic_comparison as comparison
from . import registered_cartesian_policy_adapter as adapter
from .comparison_receipts import (
    ARMS, MAX_JSON_BYTES, _canonical, _entry, _finite, _json,
    _private_dir, _regular_file, _require, _sha,
)
from .prepared_cross_numeric_reference import MAX_BYTES as MAX_POSE_BYTES
from .cpu_refinement_v1_3 import workflow
from .cpu_refinement_v1_3.contracts import SolverConfig

PROTOCOL = "installed_native_v4_registered_cartesian_comparison_protocol_v4"
FROZEN = "installed_native_v4_registered_cartesian_comparison_frozen_v4"
RESULT = "installed_native_v4_registered_cartesian_comparison_result_v4"
VERIFICATION = "installed_native_v4_registered_cartesian_comparison_verification_v4"
CLI = "installed_native_v4_registered_cartesian_comparison_cli_v4"
PREFLIGHT = "installed_native_v4_registered_cartesian_protocol_preflight_v4"
_publish = comparison._publish
_committed = comparison._committed
_report_ref = comparison._report_ref
_read_report = comparison._read_report
_predictions = comparison._predictions
_order = comparison._order


def _runtime():
    runtime = comparison._comparison_runtime()
    runtime["registered_cartesian_comparison_sources"] = {
        Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in (__file__, adapter.__file__)}
    return runtime


def _candidate_dir(run_dir, arm, rid):
    return Path(run_dir) / arm / (_sha(rid) + ".cartesian")


def _candidate_intent(run_dir, arm, rid):
    return Path(run_dir) / arm / (_sha(rid) + ".candidate-intent.json")


def freeze(protocol):
    _require(type(protocol) is dict and set(protocol) == {
        "schema_version", "source", "requests", "budget_seconds_per_arm",
        "max_engine_calls_per_arm", "arm_order", "selection_seed", "tie_policy",
        "cartesian_solver"} and protocol["schema_version"] == PROTOCOL,
        "explicit_native_registered_Cartesian_v4_protocol_required")
    config = SolverConfig.from_dict(protocol["cartesian_solver"])
    original_protocol = {k: copy.deepcopy(v) for k, v in protocol.items() if k != "cartesian_solver"}
    original_protocol["schema_version"] = comparison.NATIVE_PROTOCOL_V3
    # V3 freeze rederives source records and checks source descriptor hashes,
    # original solver settings, XML charge tokens, observed 3D stereo, role
    # separation, two distinct chemicals and the common receptor/pocket cohort.
    original = comparison.freeze(original_protocol)
    converted, bindings = {}, {}
    for rid in original["pool"]:
        converted[rid] = workflow.prepare_cartesian_request(original["requests"][rid], config)
        bindings[rid] = adapter.input_binding(converted[rid])
    frozen = copy.deepcopy(original)
    frozen.update(schema_version=FROZEN, protocol=copy.deepcopy(protocol),
                  original_requests=original["requests"],
                  original_source_inputs=original["source_inputs"],
                  requests=converted, source_inputs=bindings,
                  cartesian_solver=config.to_dict(), runtime=_runtime(),
                  request_conversion="explicit_prepare_cartesian_request_after_original_source_admission")
    _require(len(_canonical(frozen)) <= MAX_JSON_BYTES, "frozen_comparison_capacity_exceeded")
    return frozen


def preflight(protocol):
    from .installed_native_v4_registered_admission import RegisteredAdmissionError
    result = {"schema_version": PREFLIGHT, "status": "blocked", "blockers": [],
              "protocol": None, "protocol_sha256": None, "frozen_binding_sha256": None,
              "candidate_count": None, "distinct_Ki_chemical_identity_count": None,
              "assigned_role_counts": None, "cohort_sha256": None,
              "evaluation_labels_read": 0, "numeric_validation_completed": False,
              "source_authenticated": False, "same_prepared_assay_state_verified": False,
              "scientifically_validated": False, "training_admitted": False,
              "product_ranking_enabled": False}
    try:
        frozen = freeze(protocol)
        candidates = [row for row in frozen["rows"] if row["record_id"] in frozen["pool"]]
        result.update(status="ready", protocol=copy.deepcopy(protocol),
                      protocol_sha256=_sha(protocol), frozen_binding_sha256=_sha(frozen),
                      candidate_count=len(frozen["pool"]),
                      distinct_Ki_chemical_identity_count=len({row["smiles"] for row in candidates}),
                      assigned_role_counts=frozen["source_verification"]["assigned_role_counts"],
                      cohort_sha256=_sha(frozen["registered_cohort"]))
    except RegisteredAdmissionError as exc:
        result.update(exc.report)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        result["blockers"].append({"code": "registered_Cartesian_freeze_failed",
                                   "reason": str(exc) if isinstance(exc, ValueError) else type(exc).__name__})
    return result


def worker(run_dir, arm, deadline):
    _require(arm in ARMS and _finite(deadline) and deadline > 0,
             "invalid_comparison_worker_request")
    run_dir = Path(run_dir).absolute()
    _private_dir(run_dir)
    directory = run_dir / arm
    _private_dir(directory)
    frozen, binding = comparison._envelope(run_dir)
    _require(frozen["schema_version"] == FROZEN and freeze(frozen["protocol"]) == frozen,
             "registered_Cartesian_binding_changed_before_scoring")
    tick = time.perf_counter()
    predictions = _predictions(frozen, arm)
    order = _order(frozen, arm, predictions)
    _publish(directory / "priority.json", {
        "binding": binding, "arm": arm, "order": order, "predictions": predictions,
        "selector_kind": ("source_order" if arm == "engine" else
                          "fit_only_ridge" if arm == "ai_engine" else "fit_only_morgan_tanimoto"),
        "setup_wall_seconds": time.perf_counter() - tick, "evaluation_labels_read": 0})
    called, stop_reason = 0, "order_exhausted"
    for rid in order:
        if time.monotonic() >= deadline:
            stop_reason = "deadline"
            break
        if arm != "similarity" and called >= frozen["protocol"]["max_engine_calls_per_arm"]:
            stop_reason = "engine_call_cap"
            break
        started, cpu = time.perf_counter(), time.process_time()
        row = {"record_id": rid, "arm": arm, "binding": binding,
               "prediction": predictions.get(rid), "status": "unsupported",
               "score": None, "reason": "prepared_input_missing"}
        try:
            if arm == "similarity":
                row.update(status="evaluated", score=predictions[rid], reason=None)
            else:
                intent = {"schema_version": RESULT + "/candidate-intent", "binding": binding,
                          "record_id": rid, "arm": arm,
                          "request_sha256": _sha(frozen["requests"][rid]), "reserved_candidate_calls": 1,
                          "cartesian_directory": _candidate_dir(run_dir, arm, rid).name}
                _publish(_candidate_intent(run_dir, arm, rid), intent)
                called += 1
                raw_report = adapter.evaluate(frozen["requests"][rid], _candidate_dir(run_dir, arm, rid))
                report = _json(_canonical(raw_report))
                _require(comparison._stable_mapping_keys(raw_report, report), "pose_report_mapping_keys_changed")
                checked = adapter.summarize(report, request=frozen["requests"][rid],
                                            run_dir=_candidate_dir(run_dir, arm, rid))
                path, relative = _report_ref(run_dir, arm, rid)
                if not _publish(path, report, deadline=deadline, max_bytes=MAX_POSE_BYTES):
                    stop_reason = "deadline"
                    break
                row.update(status=checked["status"], score=checked["score"], reason=checked["reason"],
                           pose_report=_entry(relative, _regular_file(path, MAX_POSE_BYTES)),
                           registered_summary=checked)
        except Exception as exc:
            row.update(status="failed", score=None, reason=type(exc).__name__ + ":" + str(exc))
        row.update(cost={"wall_seconds": time.perf_counter() - started,
                         "cpu_seconds": time.process_time() - cpu},
                   completed_monotonic=time.monotonic())
        if not _publish(directory / f"{_sha(rid)}.row.json", {"payload": row, "sha256": _sha(row)}, deadline=deadline):
            stop_reason = "deadline"
            break
    _publish(directory / "worker-complete.json", {
        "binding": binding, "engine_calls": called, "stop_reason": stop_reason,
        "process_cpu_seconds": time.process_time(),
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})


def _summary(run_dir: Path, arm: str, frozen: dict, binding: str, *,
             selector_cache: comparison._SelectorCache | None = None) -> dict:
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
        predicted = _predictions(frozen, arm, cache=selector_cache)
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
                     and _finite(item.get("completed_monotonic"))
                     and item["completed_monotonic"] >= attempt["started_monotonic"],
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
            if arm == "similarity":
                _require(value["status"] == "evaluated"
                         and value["score"] == priority["predictions"][rid]
                         and value.get("reason") is None,
                         "installed_similarity_row_state_mismatch")
            elif frozen["requests"][rid] is None:
                _require(value["status"] == "unsupported"
                         and value.get("reason") == "prepared_input_missing",
                         "installed_missing_prepared_row_state_mismatch")
            else:
                _require(value["status"] in {"evaluated", "failed"},
                         "installed_prepared_row_state_mismatch")
        ref = value.get("pose_report")
        if frozen["schema_version"] == FROZEN and "completed_monotonic" in value:
            fields = {"record_id", "arm", "binding", "prediction", "status", "score",
                      "reason", "cost", "completed_monotonic"}
            if ref is not None:
                fields.update({"pose_report", "registered_summary"})
            _require(set(value) == fields, "installed_registered_row_fields_mismatch")
        report_path, _ = _report_ref(run_dir, arm, rid)
        if "completed_monotonic" in value:
            # The worker publishes a pose before its row. A deadline can leave
            # an orphan only for an uncommitted row, never a completed one.
            _require(os.path.lexists(report_path) == (ref is not None),
                     "installed_pose_report_row_presence_mismatch")
        if ref is not None:
            _require(arm != "similarity", "similarity_has_pose_report")
            report = _read_report(run_dir, arm, rid, ref)
            if frozen["schema_version"] == FROZEN:
                checked = adapter.summarize(report, request=frozen["requests"][rid],
                                            run_dir=_candidate_dir(run_dir, arm, rid))
                _require(value.get("registered_summary") == checked
                         and all(value.get(key) == checked[key]
                                 for key in ("status", "score", "reason"))
                         and not {"pose_denominator", "numeric_denominator", "selected_pose",
                                  "hard_overlap_screen", "ligand_net_charge_screen"}.intersection(value),
                         "installed_registered_report_summary_mismatch")
                _require(adapter.input_binding(frozen["requests"][rid])
                         == frozen["source_inputs"][rid],
                         "installed_registered_input_binding_mismatch")
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
    # Candidate measurements are sequential subsets of the worker's outer cost.
    # Missing parent/worker observations on interrupted attempts remain unknown.
    if elapsed is not None:
        row_wall = math.fsum(row["cost"]["wall_seconds"] for row in processed)
        _require(row_wall <= elapsed + max(1e-6, 1e-9 * elapsed),
                 "installed_row_wall_exceeds_arm_wall")
    if worker_complete is not None:
        worker_cpu = worker_complete["process_cpu_seconds"]
        row_cpu = math.fsum(row["cost"]["cpu_seconds"] for row in processed)
        _require(row_cpu <= worker_cpu + max(1e-6, 1e-9 * worker_cpu),
                 "installed_row_cpu_exceeds_worker_cpu")
    direction = -1 if arm == "similarity" else 1
    ranked = sorted((row for row in rows if row["status"] == "evaluated"),
                    key=lambda row: (direction * row["score"], row["record_id"]))
    summary = {
        "priority": priority, "worker_complete": worker_complete,
        "completion": completion, "rows": rows,
        "denominator": {"requested": len(rows),
                        **dict(Counter(row["status"] for row in rows))},
        "ranked_record_ids": [row["record_id"] for row in ranked],
        "score_quantity": ("predicted_negative_log10_molar_endpoint"
                           if arm == "similarity" else
                           "uncalibrated_explicit_graph_scorer_dimensionless_minimize"
                           if frozen["schema_version"] == FROZEN else
                           "existing_cross_only_kcal_per_mol"),
        "combined_assay_energy_score": None,
    }
    if frozen["schema_version"] == FROZEN:
        keys = adapter.WORK_KEYS
        recorded = [row["registered_summary"]["work"] for row in processed
                    if "pose_report" in row]
        calls = 0 if arm == "similarity" else (
            None if worker_complete is None else worker_complete["engine_calls"])
        summary["registered_work"] = {
            "recorded_call_counters": {key: sum(row[key] for row in recorded) for key in keys},
            "candidate_reports": len(recorded),
            "candidate_calls_without_returned_report": (
                None if calls is None else calls - len(recorded)),
            "all_candidate_molecular_work_recorded": calls == len(recorded),
        }
    partial, reservations = {}, []
    returned = {row["record_id"] for row in processed if "pose_report" in row}
    for rid in frozen["pool"]:
        intent_path = _candidate_intent(run_dir, arm, rid)
        nested = _candidate_dir(run_dir, arm, rid)
        if intent_path.exists():
            _require(arm != "similarity", "similarity_has_Cartesian_candidate_reservation")
            expected = {"schema_version": RESULT + "/candidate-intent", "binding": binding,
                        "record_id": rid, "arm": arm,
                        "request_sha256": _sha(frozen["requests"][rid]), "reserved_candidate_calls": 1,
                        "cartesian_directory": nested.name}
            _require(_committed(intent_path) == expected, "Cartesian_candidate_intent_mismatch")
            reservations.append(rid)
            if rid not in returned:
                if nested.exists():
                    _private_dir(nested)
                    partial[rid] = adapter.inspect_partial_work(frozen["requests"][rid], nested)
                else:
                    partial[rid] = {"numerical_work": None, "committed_score_calls": 0,
                                    "unknown_score_attempts": None, "unfinished_invocations": None,
                                    "all_candidate_molecular_work_recorded": False,
                                    "reason": "reserved_candidate_without_retained_work",
                                    "scoring_reexecuted": False, "numerical_evaluation_reexecuted": False}
        else:
            _require(not nested.exists() and rid not in returned,
                     "Cartesian_candidate_work_without_reservation")
    if priority is not None:
        ordered_reservations = [rid for rid in priority["order"] if rid in reservations]
        _require(ordered_reservations == priority["order"][:len(reservations)]
                 and len(reservations) <= frozen["protocol"]["max_engine_calls_per_arm"],
                 "Cartesian_candidate_reservation_sequence_mismatch")
    if worker_complete is not None:
        _require(worker_complete["engine_calls"] == len(reservations),
                 "Cartesian_candidate_reservation_denominator_mismatch")
    summary["registered_work"].update(
        candidate_calls_reserved=len(reservations),
        candidate_calls_without_returned_report=(
            None if arm != "similarity" and worker_complete is None else len(reservations) - len(returned)),
        known_candidate_reservations_without_report=len(reservations) - len(returned),
        candidate_call_denominator_complete=arm == "similarity" or worker_complete is not None,
        all_candidate_molecular_work_recorded=(not partial and (arm == "similarity" or worker_complete is not None)),
        partial_candidate_calls_with_unknown_work=len(partial))
    summary["cartesian_partial_work"] = partial
    return summary


def _validate_result_header(result, frozen, binding):
    _require(type(result) is dict and result.get("schema_version") == RESULT
             and result.get("cartesian_solver") == frozen["cartesian_solver"]
             and result.get("request_conversion") == frozen["request_conversion"]
             and result.get("cost_scope") ==
             "installed_original_source_admission_fit_inference_cartesian_refinement_durable_io_and_summary",
             "invalid_registered_Cartesian_result_header")
    # Reuse the unchanged common cost/role/denominator header validation.
    common = {k: v for k, v in result.items() if k not in {"cartesian_solver", "request_conversion"}}
    common["schema_version"] = comparison.NATIVE_RESULT_V3
    common["cost_scope"] = "installed_input_validation_fit_inference_supplied_pose_scoring_worker_io_and_summary"
    legacy_frozen = {**frozen, "schema_version": comparison.NATIVE_FROZEN_V3}
    comparison._validate_result_header(common, legacy_frozen, binding)


def run(protocol, output_dir, *, resume=False):
    _require(type(resume) is bool, "explicit_installed_resume_boolean_required")
    started = time.perf_counter()
    frozen = freeze(protocol)
    setup_seconds = time.perf_counter() - started
    selector_cache = comparison._SelectorCache(frozen)
    binding = _sha(frozen)
    root = Path(output_dir).absolute()
    if resume:
        _private_dir(root)
    else:
        root.mkdir(mode=0o700)
    lock = comparison._lock(root / "run.lock", create=not resume)
    try:
        if resume:
            observed, observed_binding = comparison._envelope(root)
            _require(observed_binding == binding and observed == frozen,
                     "installed_resume_input_or_runtime_changed")
        else:
            _publish(root / "frozen.json", {"payload": frozen, "sha256": binding})
        final = root / "comparison.json"
        if resume and final.exists():
            result = _committed(final)
            _validate_result_header(result, frozen, binding)
            for arm in ARMS:
                _require(_summary(root, arm, frozen, binding, selector_cache=selector_cache)
                         == result["arms"][arm], "installed_resume_summary_mismatch")
            return result
        arms = {}
        summary_started = time.perf_counter()
        for arm in protocol["arm_order"]:
            # This uses the same immutable arm deadline and child lease as v3.
            # An interrupted candidate never receives a new arm or solver budget.
            arms[arm] = comparison._one_arm(root, arm, frozen, binding, resume=resume,
                                            selector_cache=selector_cache)
        summary_seconds = time.perf_counter() - summary_started
        _require(freeze(protocol) == frozen, "installed_inputs_changed_during_comparison")
        result = {
            "schema_version": RESULT, "binding": binding, "pool": frozen["pool"],
            "arm_order": protocol["arm_order"], "arms": arms,
            "budget_seconds_per_arm": protocol["budget_seconds_per_arm"],
            "max_engine_calls_per_arm": protocol["max_engine_calls_per_arm"],
            "source_kind": frozen["source_kind"], "evaluation_labels_read": 0,
            "selector_recomputed_locally": True, "source_authenticated": False,
            "scientifically_validated": False, "same_prepared_assay_state_verified": False,
            "product_ranking_enabled": False, "common_validation_seconds": setup_seconds,
            "arm_execution_and_summary_wall_seconds": summary_seconds,
            "orchestrator_wall_seconds": time.perf_counter() - started,
            "cost_scope": "installed_original_source_admission_fit_inference_cartesian_refinement_durable_io_and_summary",
            "upstream_acquisition_preparation_and_pose_generation_measured": False,
            "candidate_prepared_identity_bound": {rid: True for rid in frozen["pool"]},
            "cartesian_solver": frozen["cartesian_solver"],
            "request_conversion": frozen["request_conversion"],
        }
        _validate_result_header(result, frozen, binding)
        _publish(final, result)
        return result
    finally:
        os.close(lock)


def verify_run(protocol, run_dir):
    outcome = {"schema_version": VERIFICATION, "status": "invalid", "exit_code": 2,
               "reason": None, "execution_performed": False, "new_force_calls": 0,
               "new_score_calls": 0, "source_authenticated": False, "scientifically_validated": False}
    lock = None
    try:
        root = Path(run_dir).absolute()
        _private_dir(root)
        lock = comparison._lock(root / "run.lock", create=False, shared=True)
        frozen = freeze(protocol)
        saved, binding = comparison._envelope(root)
        _require(saved == frozen and binding == _sha(frozen), "installed_verify_input_or_runtime_changed")
        selector_cache = comparison._SelectorCache(frozen)
        result = _committed(root / "comparison.json")
        _validate_result_header(result, frozen, binding)
        for arm in ARMS:
            _require(_summary(root, arm, frozen, binding, selector_cache=selector_cache)
                     == result["arms"][arm], "installed_result_summary_mismatch")
        outcome.update(status="verified", exit_code=0, binding=binding,
                       pool_count=len(frozen["pool"]), arms_verified=list(ARMS))
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        outcome["reason"] = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
    finally:
        if lock is not None:
            os.close(lock)
    return outcome
