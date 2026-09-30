"""Authenticate a frozen export, then project its receipt list for JSON-only metrics.

No evaluator is imported or called. The pinned parent exporter owns the saved
endpoint binding; the original metric evaluator still owns packet/review checks
and evaluation-only RMSD policy. Non-JSON artifacts remain in a separate receipt.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

EXPORTER_SHA256 = "b27c623d2fff44375f917d779894a4a1406a08072785389fa1c2d513b563611d"
PROTOCOL_SHA256 = "5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23"
MANIFEST_SHA256 = "4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3"
MAX_REFERENCE_BYTES = 256 * 1024 * 1024
CASE_IDS = [f"perturbed_{index:02d}" for index in range(1, 5)]
AUTHORITY = {
    "known_reserved_source_development_only": True, "existing_source_role_unchanged": True,
    "new_source_rights_admitted": False, "training_admitted": False,
    "calibration_admitted": False, "independent_evaluation_admitted": False,
    "independent_recovery_claim_allowed": False, "experimental_labels_used": False,
    "protected_evaluation_used": False, "scientifically_validated": False,
    "product_qualified": False, "HIP_qualified": False,
}
CASE_FIELDS = {
    "case_id", "status", "started_at", "input_coordinates_sha256", "chemistry_sha256",
    "original_input_hashes", "endpoint_policy", "coordinates_angstrom",
    "forces_kcal_per_mol_angstrom", "initial_internal_energy_kcal_per_mol",
    "final_internal_energy_kcal_per_mol", "baseline_dimensionless_score",
    "final_dimensionless_score", "geometry_complete", "geometry_checks",
    "numerical_audit", "work", "actual_receipt_refs",
}
WORK_FIELDS = {
    "objective_attempts", "initial_successful_objectives", "accepted_steps",
    "rejected_attempts", "failed_attempts", "unknown_pending_attempts",
    "restart_force_calls", "score_calls", "oracle_states", "AI_inference_calls", "proposal_calls",
}
_ROOT_JSON = {"terminal-case.json", "terminal-seal-watchdog.json", "supervisor.json",
              "postfailure-integrity.json"}
_NATIVE_JSON = {"child-result.json", "endpoint-states.json", "native-end.json", "native-start.json",
                "post-exit-source-check.json", "preflight.json", "semantic-verification.json"}
_RUN_JSON = {"baseline-score-intent.json", "baseline-score.json", "binding.json",
             "numerical-start-intent.json", "refined-score-intent.json", "refined-score.json",
             "request.json", "result.json"}
_REQUIRED_COMPLETED = {
    "native/child-result.json", "native/endpoint-states.json", "native/run/result.json",
    "native/semantic-verification.json", "native/run/invocation-000000.end.json",
    "native/run/numerical/meta.json", "native/run/numerical/result.json",
    "oracle/lifecycle.json", "oracle/numerical-receipt.json",
}


class ProjectionError(ValueError):
    """A receipt, role, or immutable projection contract was not authenticated."""


def _require(condition, reason):
    if not condition:
        raise ProjectionError(reason)


def _encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _pin(path, raw):
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _float(text):
    value = float(text)
    _require(math.isfinite(value), "nonfinite_json_number")
    return value


def _json(raw):
    try:
        result = json.loads(raw, object_pairs_hook=_pairs, parse_float=_float,
                            parse_constant=lambda _: (_ for _ in ()).throw(
                                ProjectionError("nonfinite_json_number")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProjectionError("invalid_json_receipt") from exc
    _require(type(result) is dict, "json_receipt_object_required")
    return result


def _reference(ref):
    _require(type(ref) is dict and set(ref) == {"path", "sha256", "bytes"}, "reference_shape")
    _require(type(ref["path"]) is str and type(ref["sha256"]) is str and
             re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]) is not None and
             type(ref["bytes"]) is int and 0 <= ref["bytes"] <= MAX_REFERENCE_BYTES, "reference_values")
    path = Path(ref["path"])
    _require(path.is_absolute() and str(path.resolve(strict=True)) == str(path),
             "canonical_reference_path_required")
    return path


def _read(ref):
    path = _reference(ref)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode), "regular_reference_required")
        _require(before.st_size == ref["bytes"], "reference_size_mismatch_before_read")
        raw = stream.read()
        after = os.fstat(stream.fileno())
    def identity(s):
        return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns
    _require(identity(before) == identity(after) == identity(path.stat()), "reference_changed_during_read")
    _require(_pin(path, raw) == ref, "reference_hash_or_bytes_mismatch")
    return raw


def _case_role(relative):
    parts = relative.parts
    if len(parts) == 1 and parts[0] in _ROOT_JSON:
        return "json"
    if len(parts) == 2:
        folder, name = parts
        if folder == "native" and name in _NATIVE_JSON:
            return "json"
        if folder == "native" and name == "dispatch.jsonl":
            return "jsonl"
        if folder == "oracle" and name in {"lifecycle.json", "numerical-receipt.json"}:
            return "json"
        if folder in {"native-process", "oracle-process"}:
            if name in {"process-start.json", "process-end.json"}:
                return "json"
            if name in {"stdout.log", "stderr.log"}:
                return "log"
    if parts[:2] == ("native", "run"):
        if len(parts) == 3:
            if parts[2] in _RUN_JSON or re.fullmatch(r"invocation-[0-9]{6}\.(start|end)\.json", parts[2]):
                return "json"
            if parts[2] == ".minimization.lock":
                return "lock"
        if len(parts) == 4 and parts[2] == "numerical":
            if parts[3] in {"meta.json", "result.json"}:
                return "json"
            if parts[3] == "events.jsonl":
                return "jsonl"
            if parts[3] == ".journal.lock":
                return "lock"
        if len(parts) == 5 and parts[2:4] == ("numerical", "checkpoints") and re.fullmatch(
                r"checkpoint-[0-9]{5}\.json", parts[4]):
            return "json"
    raise ProjectionError("undeclared_case_receipt_role")


def _unique(refs):
    _require(type(refs) is list, "reference_list_required")
    paths = [str(_reference(ref)) for ref in refs]
    _require(len(paths) == len(set(paths)), "duplicate_reference")
    return paths


def _work(value):
    _require(type(value) is dict and set(value) == WORK_FIELDS and
             all(v is None or (type(v) is int and v >= 0) for v in value.values()), "work_shape")
    _require(value["AI_inference_calls"] == value["proposal_calls"] == 0, "source_role_or_work_changed")


def _authority(value):
    return (type(value) is dict and set(value) == set(AUTHORITY) and
            all(type(v) is bool for v in value.values()) and value == AUTHORITY)


def _publish(path, value):
    raw = _encode(value)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return _pin(path, raw)


def project_saved_metric_input(saved_results_ref, export_receipt_ref, output):
    """Return pins for a create-only JSON projection, full receipt, and omissions.

    Caller-supplied pins are the trust boundary. This verifies the parent
    exporter's identity and saved binding assertions, not molecular execution.
    The returned projection must still pass the unchanged frozen metric evaluator.
    """
    raw_by_path, roles = {}, {}

    def authenticated(ref, role, expected_path=None, parse=True):
        path = _reference(ref)
        if expected_path is not None:
            _require(path == expected_path, "control_receipt_role_changed")
        raw = _read(ref)
        _require(str(path) not in raw_by_path or raw_by_path[str(path)][0] == ref,
                 "conflicting_reference_pin")
        raw_by_path[str(path)] = (deepcopy(ref), raw)
        roles.setdefault(str(path), set()).add(role)
        return _json(raw) if parse else raw

    saved_path, export_path = _reference(saved_results_ref), _reference(export_receipt_ref)
    _require(saved_path.name == "saved-recovery-results.json" and export_path.name == "export-receipt.json"
             and saved_path.parent == export_path.parent, "saved_export_role_changed")
    saved = authenticated(saved_results_ref, "saved_results")
    export = authenticated(export_receipt_ref, "export_receipt")
    base_export_fields = {"schema_id", "campaign_ref", "saved_results_ref", "case_results", "denominator",
                          "export_source_ref", "new_native_force_calls", "new_native_score_calls",
                          "new_openmm_observations", "authority", "evidence_scope"}
    version = export.get("schema_id")
    _require(version in {"sro_saved_recovery_export/1", "sro_saved_recovery_export/2"}, "export_schema")
    _require(set(export) == base_export_fields | ({"operational_revision"} if version.endswith("/2") else set()),
             "export_receipt_fields")
    _require(export["saved_results_ref"] == saved_results_ref and _authority(export["authority"]) and
             all(type(export[k]) is int and export[k] == 0 for k in
                 ("new_native_force_calls", "new_native_score_calls", "new_openmm_observations")),
             "saved_export_binding_or_authority_changed")
    _require(set(saved) == {"schema_id", "protocol_sha256", "authority", "case_results"} and
             saved["schema_id"] == "sro_saved_recovery_results/1" and _authority(saved["authority"]) and
             saved["protocol_sha256"] == PROTOCOL_SHA256, "saved_result_contract")
    campaign_path = _reference(export["campaign_ref"])
    _require(campaign_path.name == "campaign-result.json" and campaign_path.parent.name == "campaign",
             "campaign_role_required")
    archive = campaign_path.parent.parent
    campaign = authenticated(export["campaign_ref"], "campaign")
    _require(campaign["schema_id"] == "sro_four_case_campaign/" + version[-1] and
             campaign["execution_order"] == CASE_IDS and campaign["denominator"] == export["denominator"] == 4
             and campaign["status"] in {"completed", "stopped"}, "four_case_campaign_required")
    exporter_ref = export["export_source_ref"]
    _require(exporter_ref["sha256"] == EXPORTER_SHA256, "unapproved_parent_exporter_source")
    authenticated(exporter_ref, "parent_exporter_source", archive / "source/campaign_supervisor.py", False)
    plan = authenticated(campaign["plan_ref"], "plan", archive / "plan.json")
    review = authenticated(campaign["review_ref"], "execution_review", archive / "execution-review.json")
    _require(plan["protocol_sha256"] == PROTOCOL_SHA256 and plan["manifest_sha256"] == MANIFEST_SHA256,
             "parent_frozen_protocol_binding")
    driver_ref = plan["driver_source_ref"]
    authenticated(driver_ref, "native_driver_source", archive / "source/runtime_execution.py", False)
    oracle_refs = plan["oracle_phase"]["source_refs"]
    _unique(oracle_refs)
    expected_sources = {archive / "source" / name for name in
                        ("campaign_supervisor.py", "endpoint_oracle_runner.py", "sro_recovery_endpoint_numerics_v1.py")}
    expected_sources.add(archive / "oracle-input-spec.json")
    _require({Path(ref["path"]) for ref in oracle_refs} == expected_sources, "parent_source_roles_changed")
    _require(exporter_ref in oracle_refs, "parent_exporter_source_not_bound_to_plan")
    for ref in oracle_refs:
        authenticated(ref, "oracle_spec" if ref["path"].endswith(".json") else "oracle_source",
                      parse=ref["path"].endswith(".json"))
    _require(review["schema_id"] == "sro_native_execution_review/1" and
             review["execution_authorized"] is True and
             review["plan_sha256"] == campaign["plan_ref"]["sha256"] and
             review["driver_source_sha256"] == driver_ref["sha256"], "parent_saved_binding_review")
    reviewed = datetime.fromisoformat(review["reviewed_at"])
    _require(reviewed.utcoffset() is not None, "review_timezone_required")
    if version.endswith("/2"):
        revision = export["operational_revision"]
        _require(type(revision) is dict and campaign["operational_revision"] == plan["operational_revision"] == revision,
                 "operational_revision_changed")
        _require(all(revision.get(k) is False for k in
                     ("resume", "budget_reset", "scientific_protocol_changed", "source_roles_changed")),
                 "operational_revision_rights_changed")
        start = authenticated(campaign["campaign_start_ref"], "campaign_start",
                              campaign_path.parent / "campaign-start.json")
        _require(start["plan_ref"] == campaign["plan_ref"] and start["review_ref"] == campaign["review_ref"]
                 and start["supervisor_source_ref"] == exporter_ref and start["case_order"] == CASE_IDS
                 and start["denominator"] == 4 and start["operational_revision"] == revision,
                 "campaign_start_binding_changed")
    campaign_rows, rich_rows = campaign["case_results"], export["case_results"]
    _require([r["case_id"] for r in campaign_rows] == [r["case_id"] for r in rich_rows] == CASE_IDS,
             "rich_four_case_order_or_duplicate")
    legacy_ids = [r["case_id"] for r in saved["case_results"]]
    _require(legacy_ids == [r["case_id"] for r in rich_rows if r["legacy_exported"] is True],
             "rich_legacy_case_set_mismatch")
    projection = deepcopy(saved)
    actual_records, case_counts, fatal = [], [], False
    for campaign_row, rich in zip(campaign_rows, rich_rows):
        case_id, status = rich["case_id"], rich["status"]
        _require(status == campaign_row["status"] and status in {"completed", "failed", "watchdog", "unstarted"}
                 and (not fatal or status == "unstarted") and type(rich["legacy_exported"]) is bool,
                 "case_status_changed")
        fatal = fatal or status in {"failed", "watchdog"}
        if status == "unstarted":
            _require(rich["work"] is None and rich["legacy_exported"] is False and
                     rich["omission_reason"] == "unstarted_work_unknown", "unstarted_work_changed")
            case_counts.append({"case_id": case_id, "status": status, "legacy_exported": False,
                                "original_actual_reference_count": 0, "json_projection_reference_count": 0})
            continue
        started = datetime.fromisoformat(campaign_row["started_at"])
        _require(started.utcoffset() is not None and started > reviewed, "result_precedes_review")
        _work(rich["work"])
        _require(rich["accounting"]["work"] == rich["work"], "rich_accounting_work_changed")
        case_root = campaign_path.parent / case_id
        terminal_ref = campaign_row["terminal_case_ref"]
        _require(Path(terminal_ref["path"]) in {case_root / "terminal-case.json", case_root / "terminal-seal-watchdog.json"},
                 "terminal_receipt_role_changed")
        actual_refs = [terminal_ref, *campaign_row["actual_receipt_refs"]]
        paths = _unique(actual_refs)
        types = {}
        for ref, path in zip(actual_refs, paths):
            _require(Path(path).is_relative_to(case_root), "case_receipt_path_injection")
            relative = Path(path).relative_to(case_root)
            kind = _case_role(relative)
            types[path] = kind
            authenticated(ref, "case:" + case_id + ":" + relative.as_posix(), parse=False)
        projected_row = next((r for r in projection["case_results"] if r["case_id"] == case_id), None)
        if rich["legacy_exported"]:
            _require(projected_row is not None and set(projected_row) == CASE_FIELDS and
                     projected_row["status"] == status and projected_row["started_at"] == campaign_row["started_at"]
                     and projected_row["work"] == rich["work"] and projected_row["endpoint_policy"] == "last_accepted_state"
                     and projected_row["actual_receipt_refs"] == actual_refs and rich["omission_reason"] is None,
                     "legacy_saved_case_binding_changed")
            if status == "completed":
                relatives = {Path(p).relative_to(case_root).as_posix() for p in paths}
                _require(_REQUIRED_COMPLETED <= relatives, "required_completed_json_receipt_missing")
                _require(campaign_row["native_child_ref"] in actual_refs and campaign_row["numerical_receipt_ref"] in actual_refs,
                         "completed_parent_receipt_missing")
            projected_row["actual_receipt_refs"] = [deepcopy(ref) for ref in actual_refs if types[ref["path"]] == "json"]
        else:
            _require(projected_row is None and type(rich["omission_reason"]) is str,
                     "omitted_legacy_case_changed")
        for ref in actual_refs:
            actual_records.append({"case_id": case_id, "ref": deepcopy(ref), "kind": types[ref["path"]],
                                   "legacy_exported": rich["legacy_exported"],
                                   "projected": rich["legacy_exported"] and types[ref["path"]] == "json",
                                   "projection_omission_reason": None if rich["legacy_exported"] and types[ref["path"]] == "json"
                                   else "non_json_receipt_format" if rich["legacy_exported"]
                                   else "legacy_case_omitted_by_parent_exporter"})
        case_counts.append({"case_id": case_id, "status": status, "legacy_exported": rich["legacy_exported"],
                            "original_actual_reference_count": len(actual_refs),
                            "json_projection_reference_count": 0 if projected_row is None else len(projected_row["actual_receipt_refs"])})
    # Every original actual reference is authenticated above before content parsing.
    for record in actual_records:
        raw = raw_by_path[record["ref"]["path"]][1]
        if record["kind"] == "json":
            value = _json(raw)
            if "case_id" in value:
                _require(value["case_id"] == record["case_id"], "json_receipt_case_role_changed")
            if record["ref"]["path"].endswith(("terminal-case.json", "terminal-seal-watchdog.json")):
                _require(value["status"] == next(r["status"] for r in rich_rows if r["case_id"] == record["case_id"]),
                         "terminal_status_changed")
        elif record["kind"] == "jsonl":
            _require(not raw or raw.endswith(b"\n"), "incomplete_jsonl_receipt")
            for line in raw.splitlines():
                _require(bool(line.strip()), "empty_jsonl_record")
                _json(line)
            record["jsonl_record_count"] = len(raw.splitlines())
    for before_ref, _ in raw_by_path.values():
        _read(before_ref)
    _require(all({k: v for k, v in a.items() if k != "actual_receipt_refs"} ==
                 {k: v for k, v in b.items() if k != "actual_receipt_refs"}
                 for a, b in zip(saved["case_results"], projection["case_results"])), "projection_changed_result_body")
    output = Path(output).absolute()
    _require(str(output.parent.resolve(strict=True)) == str(output.parent) and
             not output.is_relative_to(archive) and not output.exists(), "create_only_external_output_required")
    output.mkdir(mode=0o700)
    projection_ref = _publish(output / "saved-metric-input.json", projection)
    omitted = [record for record in actual_records if not record["projected"]]
    omission_ref = _publish(output / "non-json-reference-omissions.json", {
        "schema_id": "sro_saved_metric_reference_omissions/1", "saved_results_ref": saved_results_ref,
        "export_receipt_ref": export_receipt_ref, "excluded_from_projection_only": omitted,
        "original_artifacts_deleted": False, "classification": "explicit_authenticated_path_roles",
        "note": "Rich-only case receipts remain here even when JSON; legacy omitted cases are not synthesized.",
    })
    receipt_ref = _publish(output / "full-reference-validation.json", {
        "schema_id": "sro_saved_metric_receipt_projection/1", "validated_at": datetime.now(timezone.utc).isoformat(),
        "saved_results_ref": saved_results_ref, "export_receipt_ref": export_receipt_ref,
        "campaign_ref": export["campaign_ref"], "projection_ref": projection_ref,
        "omission_manifest_ref": omission_ref, "parent_exporter_source_ref": exporter_ref,
        "adapter_source_ref": _pin(Path(__file__).resolve(), Path(__file__).read_bytes()),
        "parent_saved_binding_precedes_export": "authenticated_pinned_parent_exporter_assertion",
        "parent_binding_review_ref": campaign["review_ref"], "parent_binding_plan_ref": campaign["plan_ref"],
        "rich_export_schema": version, "rich_case_results": deepcopy(rich_rows),
        "legacy_saved_schema": saved["schema_id"], "legacy_case_ids": legacy_ids,
        "denominator": 4, "case_reference_counts": case_counts,
        "original_legacy_actual_reference_count": sum(len(r["actual_receipt_refs"]) for r in saved["case_results"]),
        "all_campaign_actual_reference_count": len(actual_records),
        "artifact_kind_counts": dict(Counter(r["kind"] for r in actual_records)),
        "legacy_artifact_kind_counts": dict(Counter(r["kind"] for r in actual_records if r["legacy_exported"])),
        "excluded_legacy_artifact_kind_counts": dict(Counter(r["kind"] for r in actual_records
                                                            if r["legacy_exported"] and not r["projected"])),
        "all_original_actual_references_raw_authenticated_before_content_validation": True,
        "all_before_after_pins_unchanged": True, "full_reference_validation": actual_records,
        "control_reference_validation": [{"ref": ref, "roles": sorted(roles[path])}
                                         for path, (ref, _) in sorted(raw_by_path.items())
                                         if not any(record["ref"]["path"] == path for record in actual_records)],
        "source_provenance": [{"ref": ref, "roles": sorted(roles[path])}
                              for path, (ref, _) in sorted(raw_by_path.items()) if path.endswith(".py")],
        "projection_changes_only_actual_receipt_refs": True,
        "original_packet_and_evaluation_only_policy_checks_still_required": True,
        "new_force_score_graph_optimizer_openmm_observations": 0,
        "authority": deepcopy(AUTHORITY), "scientifically_validated": False,
    })
    return {"projection_ref": projection_ref, "validation_receipt_ref": receipt_ref,
            "omission_manifest_ref": omission_ref}
