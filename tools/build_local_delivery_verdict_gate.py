#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = "runs/local_delivery_verdict_gate_current.json"
DEFAULT_OUT_MD = "runs/local_delivery_verdict_gate_current.md"

DEFAULT_PREFLIGHT_JSON = "runs/local_delivery_preflight_current.json"
DEFAULT_ACCURACY_GATE_JSON = "runs/accuracy_gate_local_delivery_preflight_current.json"
DEFAULT_REQUIREMENTS_LOCK_JSON = "runs/local_delivery_requirements_lock_current.json"
DEFAULT_ENVIRONMENT_MANIFEST_JSON = "runs/local_delivery_environment_manifest_current.json"
DEFAULT_ENGINE_PROVENANCE_JSON = "runs/local_delivery_engine_provenance_current.json"
DEFAULT_COMMERCIALIZATION_QUEUE_JSON = "runs/local_engine_commercialization_queue_current.json"
DEFAULT_STATUS_REPORT_MD = "commercialization_status_report.md"
DEFAULT_NIGHTLY_GATE_JSON = "runs/nightly_gate_burndown_packet_current.json"
DEFAULT_WETLAB_SELECTED_ALLATOM_JSON = "runs/wetlab_selected_allatom_gate_burndown_packet_current.json"
DEFAULT_CURRENT_RESULTS_INDEX_JSON = "runs/wetlab_current_results_index_current.json"
DEFAULT_PARTNERING_STACK_JSON = "runs/wetlab_partnering_stack_current.json"
DEFAULT_RESCUE_CURRENT_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_current.json"
DEFAULT_RESCUE_ATTEMPT_VALIDATION_JSON = "runs/wetlab_tcruzi_pde_allatom_rescue_attempt_validation_current.json"

ALLOWED_CLAIM_SCOPES = {"kinase", "gpcr", "ion_channel"}
DISALLOWED_SCOPE_WORDS = {
    "all",
    "any",
    "broad",
    "commercial",
    "delivery-ready",
    "drug",
    "global",
    "market",
    "pan",
    "production",
    "proteome",
    "release",
    "therapeutic",
    "transporter",
    "universal",
    "validated",
    "wetlab-ready",
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _relative(path_like: str | Path) -> str:
    path = _resolve(path_like)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "y", "1", "pass", "passed", "ok", "green", "complete"}:
            return True
        if lowered in {"false", "no", "n", "0", "fail", "failed", "red", "blocked", "incomplete"}:
            return False
    return None


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> str:
    parsed = _float_or_none(value)
    if parsed is None:
        return _text(value) or "-"
    return f"{parsed:.3f}"


def _summaryish(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    merged = dict(payload or {})
    if isinstance(summary, dict):
        merged.update(summary)
    return merged


def _json_generated_at(payload: dict[str, Any]) -> str | None:
    containers: list[dict[str, Any]] = [payload]
    summary = payload.get("summary")
    if isinstance(summary, dict):
        containers.append(summary)
    for container in containers:
        for key in ("generated_at", "generated_at_local", "created_at", "created_at_local"):
            value = container.get(key)
            if value not in (None, ""):
                return str(value)
    return None


def _local_time_from_timestamp(value: float) -> str:
    return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def _source_artifact(
    label: str,
    path_like: str | Path,
    *,
    required: bool,
    json_artifact: bool = True,
) -> dict[str, Any]:
    path = _resolve(path_like)
    artifact = {
        "label": label,
        "path": _relative(path),
        "present": False,
        "required": required,
        "status": "missing",
        "size_bytes": 0,
        "sha256": "",
        "mtime_ns": 0,
        "mtime_epoch": 0.0,
        "mtime_local": "",
        "generated_at": None,
        "json_valid": False if json_artifact else None,
        "parse_error": "",
    }
    if not path.exists():
        return artifact

    try:
        stat = path.stat()
        data = path.read_bytes()
    except OSError as exc:
        artifact["present"] = True
        artifact["status"] = "read_error"
        artifact["parse_error"] = str(exc)
        return artifact

    artifact.update(
        {
            "present": True,
            "status": "present",
            "size_bytes": stat.st_size,
            "sha256": hashlib.sha256(data).hexdigest(),
            "mtime_ns": stat.st_mtime_ns,
            "mtime_epoch": stat.st_mtime,
            "mtime_local": _local_time_from_timestamp(stat.st_mtime),
        }
    )
    if not json_artifact:
        return artifact
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        artifact.update({"status": "invalid_json", "json_valid": False, "parse_error": str(exc)})
        return artifact
    if not isinstance(payload, dict):
        artifact.update({"status": "invalid_json_object", "json_valid": False, "parse_error": "JSON payload is not an object."})
        return artifact
    artifact["json_valid"] = True
    artifact["generated_at"] = _json_generated_at(payload)
    return artifact


def _source_fingerprint_summary(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    present = [artifact for artifact in artifacts if artifact.get("present")]
    digest = hashlib.sha256(
        "\n".join(
            f"{artifact.get('label','')}|{artifact.get('path','')}|{artifact.get('sha256','')}|{artifact.get('mtime_ns',0)}"
            for artifact in sorted(present, key=lambda item: str(item.get("label", "")))
        ).encode("utf-8")
    ).hexdigest()
    max_mtime_ns = max((_int(artifact.get("mtime_ns")) for artifact in present), default=0)
    max_mtime_local = ""
    for artifact in present:
        if _int(artifact.get("mtime_ns")) == max_mtime_ns:
            max_mtime_local = _text(artifact.get("mtime_local"))
            break
    return {
        "input_artifact_fingerprint_sha256": digest,
        "input_artifact_count": len(artifacts),
        "input_artifact_present_count": len(present),
        "input_artifact_max_mtime_ns": max_mtime_ns,
        "input_artifact_max_mtime_local": max_mtime_local,
    }


def _read_json_artifact(path_like: str | Path, *, required: bool = True) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path = _resolve(path_like)
    if not path.exists():
        blocker = None
        if required:
            blocker = {
                "code": "missing_required_artifact",
                "severity": "hard",
                "artifact": _relative(path),
                "reason": f"Required artifact `{_relative(path)}` is missing.",
            }
        return {}, blocker
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {
            "code": "invalid_required_artifact",
            "severity": "hard",
            "artifact": _relative(path),
            "reason": f"Required artifact `{_relative(path)}` could not be parsed as JSON: {exc}",
        }
    if not isinstance(payload, dict):
        return {}, {
            "code": "invalid_required_artifact",
            "severity": "hard",
            "artifact": _relative(path),
            "reason": f"Required artifact `{_relative(path)}` is not a JSON object.",
        }
    return payload, None


def _first_bool(data: dict[str, Any], keys: list[str]) -> bool | None:
    for key in keys:
        if key in data:
            parsed = _boolish(data.get(key))
            if parsed is not None:
                return parsed
    return None


def _first_value(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _status_implies_pass(status_line: str) -> bool | None:
    lowered = status_line.lower()
    if not lowered:
        return None
    fail_words = ("fail", "failed", "blocked", "incomplete", "missing", "burning down", "over threshold")
    pass_words = ("pass", "passed", "green", "complete", "ok=true", "overall_ok=true")
    if any(word in lowered for word in fail_words):
        return False
    if any(word in lowered for word in pass_words):
        return True
    return None


def _common_pass(data: dict[str, Any], keys: list[str]) -> bool | None:
    explicit = _first_bool(data, keys)
    if explicit is not None:
        return explicit
    return _status_implies_pass(_text(data.get("status_line") or data.get("status")))


def _accuracy_gate_check(data: dict[str, Any], artifact: str) -> dict[str, Any]:
    if not data:
        return {
            "checked": True,
            "present": False,
            "valid": False,
            "pass": False,
            "status": "missing",
            "artifact": artifact,
            "failed_metric_count": 0,
            "failed_metrics": [],
            "failed_targets": [],
            "primary_failed_metric": {},
            "reason": f"Accuracy gate artifact `{artifact}` is missing or invalid.",
            "next_required_step": "Run the accuracy gate and regenerate the verdict inputs before any delivery-ready verdict.",
        }

    failed_metrics = [row for row in (data.get("failed_metrics") or []) if isinstance(row, dict)]
    failed_targets = [str(value) for value in (data.get("failed_targets") or [])] if isinstance(data.get("failed_targets"), list) else []
    explicit_pass = _first_bool(data, ["pass", "accuracy_gate_pass", "gate_pass", "overall_ok", "passed"])
    gate_pass = bool(explicit_pass is True and not failed_metrics)
    primary_failed_metric = dict(failed_metrics[0]) if failed_metrics else {}
    if gate_pass:
        reason = "Accuracy gate artifact reports pass=true with no failed metrics."
        next_required_step = "Accuracy gate is green; continue with the remaining local-delivery gates."
    else:
        metric = _text(primary_failed_metric.get("metric")) or "unknown_metric"
        target = _text(primary_failed_metric.get("target")) or "all"
        value = primary_failed_metric.get("value", "")
        threshold = primary_failed_metric.get("threshold", "")
        operator = _text(primary_failed_metric.get("operator"))
        reason = (
            "Accuracy gate is not green"
            f": metric={metric}, target={target}, value={value}, threshold={threshold}, operator={operator}."
        )
        next_required_step = _text(data.get("next_required_step")) or (
            "Fix the failing accuracy metric(s), rerun the accuracy gate, and only proceed after it reports pass=true."
        )
    return {
        "checked": True,
        "present": True,
        "valid": True,
        "pass": gate_pass,
        "status": "pass" if gate_pass else "fail",
        "artifact": artifact,
        "failed_metric_count": len(failed_metrics),
        "failed_metrics": failed_metrics,
        "failed_targets": failed_targets,
        "primary_failed_metric": primary_failed_metric,
        "reason": reason,
        "next_required_step": next_required_step,
    }


def _add_blocker(blockers: list[dict[str, Any]], code: str, reason: str, artifact: str = "", severity: str = "hard") -> None:
    blockers.append({"code": code, "severity": severity, "artifact": artifact, "reason": reason})


def _is_dry_run(data: dict[str, Any]) -> bool:
    if bool(data.get("dry_run", False)):
        return True
    steps = data.get("steps")
    if isinstance(steps, list) and any(bool(step.get("dry_run", False)) for step in steps if isinstance(step, dict)):
        return True
    status_line = _text(data.get("status_line") or data.get("next_required_step")).lower()
    return "dry run" in status_line or "dry-run" in status_line


def _requirements_lock_complete(data: dict[str, Any]) -> bool:
    explicit = _common_pass(data, ["requirements_lock_complete", "lock_complete", "complete", "overall_ok", "pass"])
    if explicit is not None:
        return explicit
    if any(_int(data.get(key)) > 0 for key in ("missing_count", "loose_source_requirement_count", "missing_input_file_count")):
        return False
    status_line = _text(data.get("status_line")).lower()
    if status_line.startswith("complete"):
        return True
    if status_line.startswith("incomplete"):
        return False
    return False


def _environment_lock_complete(data: dict[str, Any]) -> bool:
    explicit = _common_pass(
        data,
        ["environment_lock_complete", "environment_manifest_complete", "requirements_lock_complete", "overall_ok", "pass"],
    )
    if explicit is not None:
        return explicit
    if _int(data.get("missing_requirement_count")) > 0:
        return False
    status_line = _text(data.get("status_line"))
    return _status_implies_pass(status_line) is True


def _engine_provenance_ok(data: dict[str, Any]) -> bool:
    explicit = _common_pass(
        data,
        ["engine_provenance_ok", "provenance_ok", "existing_engine_reused", "overall_ok", "pass"],
    )
    if explicit is not None:
        return explicit
    if _int(data.get("missing_surface_count")) > 0:
        return False
    return _status_implies_pass(_text(data.get("status_line"))) is True


def _commercialization_queue_clear(data: dict[str, Any]) -> bool:
    explicit = _common_pass(data, ["commercialization_queue_clear", "queue_clear", "overall_ok", "pass"])
    if explicit is not None:
        return explicit
    blocking_keys = (
        "blocked_count",
        "hard_blocker_count",
        "p0_blocker_count",
    )
    return not any(_int(data.get(key)) > 0 for key in blocking_keys)


def _gate_metric(data: dict[str, Any], prefix: str) -> tuple[Any, Any]:
    value = _first_value(
        data,
        [
            f"{prefix}_metric_value",
            f"{prefix}_primary_value",
            f"{prefix}_gate_primary_value",
            "selected_allatom_best_mean_min_distance_A",
            "primary_gate_value",
            "primary_burndown_value",
            "metric_value",
            "value",
        ],
    )
    threshold = _first_value(
        data,
        [
            f"{prefix}_metric_threshold",
            f"{prefix}_primary_threshold",
            f"{prefix}_gate_primary_threshold",
            "selected_allatom_selected_threshold_A",
            "primary_gate_threshold",
            "primary_burndown_threshold",
            "metric_threshold",
            "threshold",
        ],
    )
    return value, threshold


def _metric_delta(value: Any, threshold: Any) -> float | None:
    parsed_value = _float_or_none(value)
    parsed_threshold = _float_or_none(threshold)
    if parsed_value is None or parsed_threshold is None:
        return None
    return parsed_value - parsed_threshold


def _nightly_gate_pass(data: dict[str, Any]) -> bool:
    if _first_bool(data, ["stage6_gate_failed", "gate_failed"]) is True:
        return False
    explicit = _common_pass(
        data,
        [
            "nightly_gate_pass",
            "nightly_stage6_rescored_gate_pass",
            "gate_pass",
            "overall_ok",
            "pass",
            "passed",
        ],
    )
    if explicit is not None:
        return explicit
    if _int(data.get("gate_failed_metric_count")) > 0:
        return False
    return False


def _wetlab_selected_allatom_pass(data: dict[str, Any]) -> bool:
    if _int(data.get("hard_block_count")) > 0 or _int(data.get("missing_metric_count")) > 0:
        return False
    status = _text(data.get("selected_allatom_actionability_status") or data.get("status_line") or data.get("status")).lower()
    if "hard_block" in status or "blocked" in status:
        return False
    explicit = _common_pass(
        data,
        [
            "wetlab_selected_allatom_pass",
            "selected_allatom_final_gate_pass",
            "selected_allatom_wetlab_gate_pass",
            "final_gate_pass",
            "wetlab_gate_pass",
            "gate_pass",
            "overall_ok",
            "pass",
            "passed",
        ],
    )
    if explicit is not None:
        return explicit
    return False


def _rescue_attempt_validation_summary(
    data: dict[str, Any],
    *,
    artifact: str,
    required: bool,
    artifact_present: bool,
    artifact_valid: bool,
) -> dict[str, Any]:
    if not required and not artifact_present:
        reason = "No PDE rescue current artifact is present; rescue attempt validation is not required."
        return {
            "required": False,
            "present": False,
            "valid": False,
            "pass": False,
            "ok": True,
            "status": "not_required",
            "failed_check_count": 0,
            "hard_fail_count": 0,
            "warning_count": 0,
            "attempt_id": "",
            "attempt_dir": "",
            "attempt_state_json": "",
            "execution_mode": "",
            "scoring_status": "",
            "input_fingerprint_recomputed_ok": False,
            "required_artifact_missing_count": 0,
            "path_boundary_fail_count": 0,
            "artifact": artifact,
            "reason": reason,
            "next_required_step": "Continue with the normal local-delivery gate path.",
        }
    if not artifact_present:
        reason = f"Rescue attempt validation artifact `{artifact}` is missing."
        return {
            "required": required,
            "present": False,
            "valid": False,
            "pass": False,
            "status": "missing",
            "ok": False,
            "failed_check_count": 0,
            "hard_fail_count": 0,
            "warning_count": 0,
            "attempt_id": "",
            "attempt_dir": "",
            "attempt_state_json": "",
            "execution_mode": "",
            "scoring_status": "",
            "input_fingerprint_recomputed_ok": False,
            "required_artifact_missing_count": 0,
            "path_boundary_fail_count": 0,
            "artifact": artifact,
            "reason": reason,
            "next_required_step": "Run `python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py` before reusing rescue evidence.",
        }
    if not artifact_valid or not data:
        reason = f"Rescue attempt validation artifact `{artifact}` is invalid or not a JSON object."
        return {
            "required": required,
            "present": True,
            "valid": False,
            "pass": False,
            "status": "invalid",
            "ok": False,
            "failed_check_count": 0,
            "hard_fail_count": 0,
            "warning_count": 0,
            "attempt_id": "",
            "attempt_dir": "",
            "attempt_state_json": "",
            "execution_mode": "",
            "scoring_status": "",
            "input_fingerprint_recomputed_ok": False,
            "required_artifact_missing_count": 0,
            "path_boundary_fail_count": 0,
            "artifact": artifact,
            "reason": reason,
            "next_required_step": "Regenerate the rescue attempt validation artifact before reusing rescue evidence.",
        }

    status = _text(data.get("rescue_attempt_validation") or data.get("status")) or "unknown"
    failed_check_count = _int(data.get("failed_check_count"))
    hard_fail_count = _int(data.get("hard_fail_count"))
    warning_count = _int(data.get("warning_count"))
    explicit_ok = _common_pass(data, ["overall_ok", "pass", "passed"])
    status_pass = _status_implies_pass(status) is True
    passed = bool((explicit_ok is True or status_pass) and hard_fail_count == 0 and failed_check_count == 0)
    reason = (
        "Rescue attempt validation reports pass with no failed checks."
        if passed
        else (
            "Rescue attempt validation is not passing: "
            f"status={status}, failed_check_count={failed_check_count}, hard_fail_count={hard_fail_count}."
        )
    )
    return {
        "required": required,
        "present": True,
        "valid": True,
        "pass": passed,
        "status": status,
        "ok": passed,
        "failed_check_count": failed_check_count,
        "hard_fail_count": hard_fail_count,
        "warning_count": warning_count,
        "attempt_id": _text(data.get("attempt_id")),
        "attempt_dir": _text(data.get("attempt_dir")),
        "attempt_state_json": _text(data.get("attempt_state_json")),
        "execution_mode": _text(data.get("execution_mode")),
        "scoring_status": _text(data.get("scoring_status")),
        "input_fingerprint_recomputed_ok": _boolish(data.get("input_fingerprint_recomputed_ok")) is True,
        "required_artifact_missing_count": _int(data.get("required_artifact_missing_count")),
        "path_boundary_fail_count": _int(data.get("path_boundary_fail_count")),
        "artifact": artifact,
        "reason": reason,
        "next_required_step": (
            "Continue with review packet and verdict refresh; this validates evidence integrity only."
            if passed
            else "Regenerate or repair the rescue attempt validation before reusing rescue evidence."
        ),
    }


def _status_is_placeholder_or_minimal(status: str) -> bool:
    lowered = status.strip().lower()
    return lowered in {"", "ok", "placeholder", "minimal", "stub", "incomplete"} or any(
        marker in lowered for marker in ("placeholder", "minimal")
    )


def _partnering_stack_index_check(data: dict[str, Any], *, requested: bool) -> tuple[bool, str, bool | None, list[str]]:
    if not requested:
        return True, "", None, []
    if not data:
        return False, "", False, ["current_results_index artifact is missing or invalid"]

    status = _text(data.get("partnering_stack_artifact_status"))
    complete = _first_bool(data, ["partnering_stack_artifact_complete"])
    reasons: list[str] = []
    if complete is not True:
        reasons.append(f"current_results_index partnering_stack_artifact_complete={complete}")
    if _status_is_placeholder_or_minimal(status):
        reasons.append(f"current_results_index partnering_stack_artifact_status={status or '-'}")
    elif status != "wetlab_partnering_stack_ready":
        reasons.append(f"current_results_index partnering_stack_artifact_status={status}")
    return not reasons, status, complete, reasons


def _partnering_stack_source_check(data: dict[str, Any], *, requested: bool) -> tuple[bool, str, bool | None, list[str]]:
    if not requested:
        return True, "", None, []
    if not data:
        return False, "", False, ["partnering stack artifact is missing or invalid"]

    status = _text(data.get("status"))
    reasons: list[str] = []
    if status != "wetlab_partnering_stack_ready":
        reasons.append(f"partnering_stack status={status or '-'}")
    if _text(data.get("artifact_kind")) != "wetlab_partnering_stack":
        reasons.append("partnering_stack artifact_kind is not wetlab_partnering_stack")
    if _text(data.get("artifact_completeness")) != "full_partnering_stack":
        reasons.append("partnering_stack artifact_completeness is not full_partnering_stack")

    metric_value = _float_or_none(data.get("selected_allatom_best_mean_min_distance_A"))
    threshold = _float_or_none(data.get("selected_allatom_selected_threshold_A"))
    metric_source = _text(data.get("selected_allatom_best_mean_min_distance_A_source"))
    wetlab_gate = _first_bool(data, ["selected_allatom_wetlab_gate_pass"])
    final_gate = _first_bool(data, ["selected_allatom_final_gate_pass"])
    if metric_value is None:
        reasons.append("missing selected_allatom_best_mean_min_distance_A")
    if threshold is None:
        reasons.append("missing selected_allatom_selected_threshold_A")
    if not metric_source:
        reasons.append("missing selected_allatom_best_mean_min_distance_A_source")
    if wetlab_gate is None:
        reasons.append("missing selected_allatom_wetlab_gate_pass")
    if final_gate is None:
        reasons.append("missing selected_allatom_final_gate_pass")

    return not reasons, status, not reasons, reasons


def _claim_scope_ok(claim_scope: str) -> tuple[bool, str]:
    normalized = claim_scope.strip().lower().replace("-", "_")
    normalized = re.sub(r"\bion\s+channel\b", "ion_channel", normalized)
    tokens = set(re.findall(r"[a-z][a-z0-9_]*", normalized))
    broad = sorted(word for word in DISALLOWED_SCOPE_WORDS if word in tokens or word in normalized)
    allowed = sorted(token for token in tokens if token in ALLOWED_CLAIM_SCOPES)
    unknown = sorted(token for token in tokens if token not in ALLOWED_CLAIM_SCOPES and token not in DISALLOWED_SCOPE_WORDS)
    ok = bool(allowed) and not broad and not unknown
    if ok:
        return True, f"Claim scope restricted to {', '.join(allowed)}."
    if broad:
        return False, f"Claim scope includes disallowed broad wording: {', '.join(broad)}."
    if unknown:
        return False, f"Claim scope includes unsupported scope terms: {', '.join(unknown)}."
    return False, "Claim scope is empty; restrict it to kinase/gpcr/ion_channel before delivery."


def build_payload(
    *,
    claim_scope: str,
    preflight_json: str | Path = DEFAULT_PREFLIGHT_JSON,
    accuracy_gate_json: str | Path = DEFAULT_ACCURACY_GATE_JSON,
    requirements_lock_json: str | Path = DEFAULT_REQUIREMENTS_LOCK_JSON,
    environment_manifest_json: str | Path = DEFAULT_ENVIRONMENT_MANIFEST_JSON,
    engine_provenance_json: str | Path = DEFAULT_ENGINE_PROVENANCE_JSON,
    commercialization_queue_json: str | Path = DEFAULT_COMMERCIALIZATION_QUEUE_JSON,
    status_report_md: str | Path = DEFAULT_STATUS_REPORT_MD,
    nightly_gate_json: str | Path = DEFAULT_NIGHTLY_GATE_JSON,
    wetlab_selected_allatom_json: str | Path = DEFAULT_WETLAB_SELECTED_ALLATOM_JSON,
    current_results_index_json: str | Path | None = DEFAULT_CURRENT_RESULTS_INDEX_JSON,
    partnering_stack_json: str | Path | None = DEFAULT_PARTNERING_STACK_JSON,
    rescue_current_json: str | Path = DEFAULT_RESCUE_CURRENT_JSON,
    rescue_attempt_validation_json: str | Path = DEFAULT_RESCUE_ATTEMPT_VALIDATION_JSON,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []

    required_inputs = {
        "preflight": preflight_json,
        "accuracy_gate": accuracy_gate_json,
        "requirements_lock": requirements_lock_json,
        "environment_manifest": environment_manifest_json,
        "engine_provenance": engine_provenance_json,
        "commercialization_queue": commercialization_queue_json,
        "nightly_gate": nightly_gate_json,
        "wetlab_selected_allatom": wetlab_selected_allatom_json,
    }
    loaded: dict[str, dict[str, Any]] = {}
    for label, path_like in required_inputs.items():
        path = _resolve(path_like)
        payload, blocker = _read_json_artifact(path)
        loaded[label] = _summaryish(payload) if payload else {}
        artifacts.append(_source_artifact(label, path, required=True))
        if blocker:
            blockers.append(blocker)

    evidence_loaded: dict[str, dict[str, Any]] = {}
    evidence_inputs = {
        "current_results_index": current_results_index_json,
        "partnering_stack": partnering_stack_json,
    }
    for label, path_like in evidence_inputs.items():
        if path_like is None:
            evidence_loaded[label] = {}
            continue
        payload, blocker = _read_json_artifact(path_like, required=False)
        evidence_loaded[label] = _summaryish(payload) if payload else {}
        artifacts.append(_source_artifact(label, path_like, required=True))
        if blocker:
            blockers.append(blocker)

    rescue_current_present = _resolve(rescue_current_json).exists()
    rescue_validation_path = _resolve(rescue_attempt_validation_json)
    rescue_validation_artifact_relevant = rescue_current_present or rescue_validation_path.exists()
    rescue_validation_payload: dict[str, Any] = {}
    rescue_validation_artifact = None
    if rescue_validation_artifact_relevant:
        payload, _blocker = _read_json_artifact(rescue_attempt_validation_json, required=False)
        rescue_validation_payload = _summaryish(payload) if payload else {}
        rescue_validation_artifact = _source_artifact(
            "rescue_attempt_validation",
            rescue_attempt_validation_json,
            required=rescue_current_present,
        )
        artifacts.append(rescue_validation_artifact)

    report_path = _resolve(status_report_md)
    status_report_present = report_path.exists()
    artifacts.append(_source_artifact("status_report_md", report_path, required=True, json_artifact=False))

    preflight = loaded["preflight"]
    accuracy_gate = loaded["accuracy_gate"]
    requirements = loaded["requirements_lock"]
    environment = loaded["environment_manifest"]
    engine = loaded["engine_provenance"]
    queue = loaded["commercialization_queue"]
    nightly = loaded["nightly_gate"]
    wetlab = loaded["wetlab_selected_allatom"]
    current_results_index = evidence_loaded["current_results_index"]
    partnering_stack = evidence_loaded["partnering_stack"]
    rescue_attempt_validation = _rescue_attempt_validation_summary(
        rescue_validation_payload,
        artifact=_relative(rescue_attempt_validation_json),
        required=rescue_current_present,
        artifact_present=bool(rescue_validation_artifact and rescue_validation_artifact.get("present")),
        artifact_valid=bool(rescue_validation_artifact and rescue_validation_artifact.get("json_valid") is True),
    )

    preflight_ok = _common_pass(preflight, ["preflight_ok", "overall_ok", "pass", "passed"]) is True and not _is_dry_run(preflight)
    accuracy_gate_check = _accuracy_gate_check(accuracy_gate, _relative(accuracy_gate_json))
    accuracy_gate_pass = bool(accuracy_gate_check.get("pass") is True)
    requirements_lock_complete = _requirements_lock_complete(requirements)
    environment_lock_complete = _environment_lock_complete(environment)
    engine_provenance_ok = _engine_provenance_ok(engine)
    commercialization_queue_clear = _commercialization_queue_clear(queue)
    nightly_gate_pass = _nightly_gate_pass(nightly)
    wetlab_selected_allatom_pass = _wetlab_selected_allatom_pass(wetlab)
    current_results_index_requested = current_results_index_json is not None
    partnering_stack_requested = partnering_stack_json is not None
    (
        partnering_stack_index_complete,
        partnering_stack_artifact_status,
        partnering_stack_artifact_complete,
        partnering_stack_index_reasons,
    ) = _partnering_stack_index_check(current_results_index, requested=current_results_index_requested)
    (
        partnering_stack_source_artifact_complete,
        partnering_stack_source_artifact_status,
        _partnering_stack_source_complete_value,
        partnering_stack_source_reasons,
    ) = _partnering_stack_source_check(partnering_stack, requested=partnering_stack_requested)
    partnering_stack_complete = partnering_stack_index_complete and partnering_stack_source_artifact_complete
    claim_scope_ok, claim_scope_reason = _claim_scope_ok(claim_scope)

    nightly_metric_value, nightly_metric_threshold = _gate_metric(nightly, "nightly")
    wetlab_metric_value, wetlab_metric_threshold = _gate_metric(wetlab, "wetlab")
    nightly_metric_delta = _metric_delta(nightly_metric_value, nightly_metric_threshold)
    wetlab_metric_delta = _metric_delta(wetlab_metric_value, wetlab_metric_threshold)
    nightly_downstream_execute_gate_pass = _first_bool(
        queue,
        [
            "nightly_stage6_execute_gate_pass",
            "nightly_stage6_downstream_rerun_execute_pass",
        ],
    )
    nightly_downstream_execute_metric = _first_value(
        queue,
        [
            "nightly_stage6_execute_gate_mean_min_distance_A",
            "nightly_stage6_rescored_gate_mean_min_distance_A",
            "nightly_stage6_probe_projected_gate_mean_min_distance_A",
        ],
    )
    nightly_downstream_execute_source = _text(
        _first_value(
            queue,
            [
                "nightly_stage6_execute_artifact",
                "nightly_stage6_downstream_rerun_artifact",
                "nightly_stage6_rescored_gate_artifact",
            ],
        )
    )
    nightly_top_level_status = _text(nightly.get("status"))
    nightly_top_level_latest_failed_stage = _text(nightly.get("latest_failed_stage"))
    nightly_top_level_error_code = _text(nightly.get("latest_error_code"))
    nightly_top_level_next_required_step = _text(nightly.get("next_required_step"))
    nightly_top_level_promotion_pending = bool(
        nightly_downstream_execute_gate_pass is True and not nightly_gate_pass
    )
    wetlab_hard_block_count = _int(wetlab.get("hard_block_count"))
    wetlab_semi_hard_block_count = _int(wetlab.get("semi_hard_block_count"))
    wetlab_missing_metric_count = _int(wetlab.get("missing_metric_count"))
    wetlab_primary_burndown_code = _text(wetlab.get("primary_burndown_code"))
    wetlab_primary_burndown_action = _text(wetlab.get("primary_burndown_action"))
    wetlab_primary_burndown_metric = _text(wetlab.get("primary_burndown_metric"))
    wetlab_primary_burndown_delta = _float_or_none(wetlab.get("primary_burndown_delta"))
    wetlab_primary_repair_lane = _text(wetlab.get("primary_repair_lane"))
    wetlab_primary_repair_action = _text(wetlab.get("primary_repair_action"))
    wetlab_primary_repair_source_artifact = _text(wetlab.get("primary_repair_source_artifact"))
    wetlab_primary_repair_source_ligand_id = _text(wetlab.get("primary_repair_source_ligand_id"))
    wetlab_next_required_step = _text(wetlab.get("next_required_step"))

    nightly_gate_reason = "Nightly reliability gate is not green."
    if nightly_top_level_promotion_pending:
        top_level_detail = ""
        if nightly_top_level_status or nightly_top_level_latest_failed_stage:
            top_level_detail = (
                f" Current top-level status={nightly_top_level_status or '-'}, "
                f"latest_failed_stage={nightly_top_level_latest_failed_stage or '-'}."
            )
        nightly_gate_reason = (
            "Nightly downstream execute evidence is green, but the top-level nightly gate artifact is still not green; "
            "rerun or promote the current nightly gate artifact before delivery-ready wording."
            f"{top_level_detail}"
        )
    wetlab_gate_reason = (
        "Wetlab selected-allatom gate is not green."
        if not any((wetlab_hard_block_count, wetlab_missing_metric_count, wetlab_primary_burndown_code))
        else (
            "Wetlab selected-allatom gate is not green: "
            f"hard_block_count={wetlab_hard_block_count}, "
            f"missing_metric_count={wetlab_missing_metric_count}, "
            f"primary_burndown={wetlab_primary_burndown_code or '-'}, "
            f"delta_A={_fmt(wetlab_primary_burndown_delta if wetlab_primary_burndown_delta is not None else wetlab_metric_delta)}, "
            f"repair_lane={wetlab_primary_repair_lane or '-'}, "
            f"repair_action={wetlab_primary_repair_action or wetlab_primary_burndown_code or '-'}."
        )
    )

    checks = [
        ("preflight_not_green", preflight_ok, "Local delivery preflight is missing, failed, unknown, or dry-run only.", _relative(preflight_json)),
        ("accuracy_gate_not_green", accuracy_gate_pass, str(accuracy_gate_check.get("reason", "")), _relative(accuracy_gate_json)),
        ("requirements_lock_not_complete", requirements_lock_complete, "Requirements lock is not complete.", _relative(requirements_lock_json)),
        ("environment_lock_not_complete", environment_lock_complete, "Environment manifest is not complete.", _relative(environment_manifest_json)),
        ("engine_provenance_not_green", engine_provenance_ok, "Engine provenance does not prove existing-engine reuse.", _relative(engine_provenance_json)),
        ("commercialization_queue_not_clear", commercialization_queue_clear, "Commercialization queue still reports blockers.", _relative(commercialization_queue_json)),
        ("nightly_gate_not_green", nightly_gate_pass, nightly_gate_reason, _relative(nightly_gate_json)),
        (
            "wetlab_selected_allatom_not_green",
            wetlab_selected_allatom_pass,
            wetlab_gate_reason,
            _relative(wetlab_selected_allatom_json),
        ),
        (
            "partnering_stack_placeholder_or_incomplete",
            partnering_stack_complete,
            "Partnering stack evidence is placeholder, minimal, missing, or incomplete: "
            + "; ".join(partnering_stack_index_reasons + partnering_stack_source_reasons),
            _relative(partnering_stack_json or DEFAULT_PARTNERING_STACK_JSON),
        ),
        (
            "missing_status_report",
            status_report_present,
            "Commercialization status report is missing.",
            _relative(status_report_md),
        ),
        ("claim_scope_not_restricted", claim_scope_ok, claim_scope_reason, ""),
    ]
    for code, ok, reason, artifact in checks:
        if not ok:
            _add_blocker(blockers, code, reason, artifact)

    if rescue_current_present and not rescue_attempt_validation["ok"]:
        _add_blocker(
            blockers,
            "rescue_attempt_validation_not_pass",
            rescue_attempt_validation["reason"],
            rescue_attempt_validation["artifact"],
        )

    hard_blocker_count = sum(1 for blocker in blockers if blocker.get("severity") == "hard")
    p0_blocker_count = hard_blocker_count
    source_artifact_missing_count = sum(1 for artifact in artifacts if not artifact.get("present"))
    source_artifact_invalid_count = sum(1 for artifact in artifacts if artifact.get("json_valid") is False and artifact.get("present"))
    source_artifacts_all_fingerprinted = all(
        bool(artifact.get("present")) and bool(artifact.get("sha256")) and int(artifact.get("size_bytes", 0)) > 0
        for artifact in artifacts
    )
    fingerprint_summary = _source_fingerprint_summary(artifacts)
    delivery_ready = hard_blocker_count == 0
    verdict = "delivery_ready" if delivery_ready else "blocked"
    status_line = (
        "delivery-ready verdict may be issued for the restricted local scope."
        if delivery_ready
        else f"blocked: {p0_blocker_count} P0 blocker(s) remain; do not issue a delivery-ready verdict."
    )
    next_required_step = (
        "Proceed with the scoped local delivery bundle."
        if delivery_ready
        else blockers[0]["reason"]
    )

    generated_at_local = datetime.now().astimezone().isoformat(timespec="seconds")
    summary = {
        "generated_at_local": generated_at_local,
        "delivery_ready": delivery_ready,
        "verdict": verdict,
        "p0_blocker_count": p0_blocker_count,
        "hard_blocker_count": hard_blocker_count,
        "source_artifact_count": len(artifacts),
        "source_artifact_missing_count": source_artifact_missing_count,
        "source_artifact_invalid_count": source_artifact_invalid_count,
        "source_artifacts_all_fingerprinted": source_artifacts_all_fingerprinted,
        **fingerprint_summary,
        "preflight_ok": preflight_ok,
        "accuracy_gate_pass": accuracy_gate_pass,
        "accuracy_gate_check": accuracy_gate_check,
        "requirements_lock_complete": requirements_lock_complete,
        "environment_lock_complete": environment_lock_complete,
        "engine_provenance_ok": engine_provenance_ok,
        "nightly_gate_pass": nightly_gate_pass,
        "nightly_metric_value": nightly_metric_value,
        "nightly_metric_threshold": nightly_metric_threshold,
        "nightly_metric_delta_A": nightly_metric_delta,
        "nightly_downstream_execute_gate_pass": nightly_downstream_execute_gate_pass,
        "nightly_downstream_execute_metric": nightly_downstream_execute_metric,
        "nightly_downstream_execute_source": nightly_downstream_execute_source,
        "nightly_top_level_status": nightly_top_level_status,
        "nightly_top_level_latest_failed_stage": nightly_top_level_latest_failed_stage,
        "nightly_top_level_error_code": nightly_top_level_error_code,
        "nightly_top_level_next_required_step": nightly_top_level_next_required_step,
        "nightly_top_level_promotion_pending": nightly_top_level_promotion_pending,
        "wetlab_selected_allatom_pass": wetlab_selected_allatom_pass,
        "wetlab_metric_value": wetlab_metric_value,
        "wetlab_metric_threshold": wetlab_metric_threshold,
        "wetlab_metric_delta_A": wetlab_metric_delta,
        "wetlab_hard_block_count": wetlab_hard_block_count,
        "wetlab_semi_hard_block_count": wetlab_semi_hard_block_count,
        "wetlab_missing_metric_count": wetlab_missing_metric_count,
        "wetlab_primary_burndown_code": wetlab_primary_burndown_code,
        "wetlab_primary_burndown_action": wetlab_primary_burndown_action,
        "wetlab_primary_burndown_metric": wetlab_primary_burndown_metric,
        "wetlab_primary_burndown_delta_A": wetlab_primary_burndown_delta,
        "wetlab_primary_repair_lane": wetlab_primary_repair_lane,
        "wetlab_primary_repair_action": wetlab_primary_repair_action,
        "wetlab_primary_repair_source_artifact": wetlab_primary_repair_source_artifact,
        "wetlab_primary_repair_source_ligand_id": wetlab_primary_repair_source_ligand_id,
        "wetlab_next_required_step": wetlab_next_required_step,
        "rescue_attempt_validation_required": rescue_attempt_validation["required"],
        "rescue_attempt_validation_present": rescue_attempt_validation["present"],
        "rescue_attempt_validation_status": rescue_attempt_validation["status"],
        "rescue_attempt_validation_pass": rescue_attempt_validation["pass"],
        "rescue_attempt_validation_ok": rescue_attempt_validation["ok"],
        "rescue_attempt_validation_failed_check_count": rescue_attempt_validation["failed_check_count"],
        "rescue_attempt_validation_hard_fail_count": rescue_attempt_validation["hard_fail_count"],
        "rescue_attempt_validation_warning_count": rescue_attempt_validation["warning_count"],
        "rescue_attempt_validation_artifact": rescue_attempt_validation["artifact"],
        "rescue_attempt_validation_check": {
            "checked": True,
            "required": rescue_attempt_validation["required"],
            "present": rescue_attempt_validation["present"],
            "valid": rescue_attempt_validation["valid"],
            "pass": rescue_attempt_validation["pass"],
            "ok": rescue_attempt_validation["ok"],
            "status": rescue_attempt_validation["status"],
            "artifact": rescue_attempt_validation["artifact"],
            "reason": rescue_attempt_validation["reason"],
            "next_required_step": rescue_attempt_validation["next_required_step"],
            "hard_fail_count": rescue_attempt_validation["hard_fail_count"],
            "failed_check_count": rescue_attempt_validation["failed_check_count"],
            "warning_count": rescue_attempt_validation["warning_count"],
            "attempt_id": rescue_attempt_validation["attempt_id"],
            "attempt_dir": rescue_attempt_validation["attempt_dir"],
            "attempt_state_json": rescue_attempt_validation["attempt_state_json"],
            "execution_mode": rescue_attempt_validation["execution_mode"],
            "scoring_status": rescue_attempt_validation["scoring_status"],
            "input_fingerprint_recomputed_ok": rescue_attempt_validation["input_fingerprint_recomputed_ok"],
            "required_artifact_missing_count": rescue_attempt_validation["required_artifact_missing_count"],
            "path_boundary_fail_count": rescue_attempt_validation["path_boundary_fail_count"],
        },
        "partnering_stack_artifact_status": partnering_stack_artifact_status,
        "partnering_stack_artifact_complete": partnering_stack_artifact_complete,
        "partnering_stack_source_artifact_status": partnering_stack_source_artifact_status,
        "partnering_stack_source_artifact_complete": partnering_stack_source_artifact_complete,
        "claim_scope_ok": claim_scope_ok,
        "status_line": status_line,
        "next_required_step": next_required_step,
        "claim_scope": claim_scope,
        "claim_scope_reason": claim_scope_reason,
        "commercialization_queue_clear": commercialization_queue_clear,
        "status_report_present": status_report_present,
    }
    return {
        "generated_at_local": generated_at_local,
        "summary": summary,
        "p0_blockers": blockers,
        "source_artifacts": artifacts,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Delivery Verdict Gate",
        "",
        "This gate reads existing artifacts only. It does not run heavy engine jobs.",
        "",
        "## Summary",
        "",
        f"- generated_at_local: `{summary['generated_at_local']}`",
        f"- delivery_ready: `{summary['delivery_ready']}`",
        f"- verdict: `{summary['verdict']}`",
        f"- p0_blocker_count: `{summary['p0_blocker_count']}`",
        f"- hard_blocker_count: `{summary['hard_blocker_count']}`",
        f"- source_artifact_count: `{summary['source_artifact_count']}`",
        f"- source_artifact_missing_count: `{summary['source_artifact_missing_count']}`",
        f"- source_artifact_invalid_count: `{summary['source_artifact_invalid_count']}`",
        f"- source_artifacts_all_fingerprinted: `{summary['source_artifacts_all_fingerprinted']}`",
        f"- preflight_ok: `{summary['preflight_ok']}`",
        f"- accuracy_gate_pass: `{summary['accuracy_gate_pass']}`",
        f"- accuracy_gate_check_status: `{summary.get('accuracy_gate_check', {}).get('status', '-')}`",
        f"- accuracy_gate_failed_metric_count: `{summary.get('accuracy_gate_check', {}).get('failed_metric_count', 0)}`",
        f"- accuracy_gate_reason: {summary.get('accuracy_gate_check', {}).get('reason', '-')}",
        f"- accuracy_gate_next_required_step: {summary.get('accuracy_gate_check', {}).get('next_required_step', '-')}",
        f"- requirements_lock_complete: `{summary['requirements_lock_complete']}`",
        f"- environment_lock_complete: `{summary['environment_lock_complete']}`",
        f"- engine_provenance_ok: `{summary['engine_provenance_ok']}`",
        f"- nightly_gate_pass: `{summary['nightly_gate_pass']}`",
        f"- nightly_metric: `{_fmt(summary['nightly_metric_value'])}` / `{_fmt(summary['nightly_metric_threshold'])}` "
        f"(delta `{_fmt(summary.get('nightly_metric_delta_A'))}`)",
        f"- nightly_downstream_execute_gate_pass: `{summary.get('nightly_downstream_execute_gate_pass')}`",
        f"- nightly_downstream_execute_metric: `{_fmt(summary.get('nightly_downstream_execute_metric'))}`",
        f"- nightly_downstream_execute_source: `{summary.get('nightly_downstream_execute_source') or '-'}`",
        f"- nightly_top_level_status: `{summary.get('nightly_top_level_status') or '-'}`",
        f"- nightly_top_level_latest_failed_stage: `{summary.get('nightly_top_level_latest_failed_stage') or '-'}`",
        f"- nightly_top_level_error_code: `{summary.get('nightly_top_level_error_code') or '-'}`",
        f"- nightly_top_level_promotion_pending: `{summary.get('nightly_top_level_promotion_pending', False)}`",
        f"- nightly_top_level_next_required_step: {summary.get('nightly_top_level_next_required_step') or '-'}",
        f"- wetlab_selected_allatom_pass: `{summary['wetlab_selected_allatom_pass']}`",
        f"- wetlab_metric: `{_fmt(summary['wetlab_metric_value'])}` / `{_fmt(summary['wetlab_metric_threshold'])}` "
        f"(delta `{_fmt(summary.get('wetlab_metric_delta_A'))}`)",
        f"- wetlab_hard_block_count: `{summary.get('wetlab_hard_block_count', 0)}`",
        f"- wetlab_semi_hard_block_count: `{summary.get('wetlab_semi_hard_block_count', 0)}`",
        f"- wetlab_missing_metric_count: `{summary.get('wetlab_missing_metric_count', 0)}`",
        f"- wetlab_primary_burndown_code: `{summary.get('wetlab_primary_burndown_code', '') or '-'}`",
        f"- wetlab_primary_burndown_action: `{summary.get('wetlab_primary_burndown_action', '') or '-'}`",
        f"- wetlab_primary_burndown_metric: `{summary.get('wetlab_primary_burndown_metric', '') or '-'}`",
        f"- wetlab_primary_burndown_delta_A: `{_fmt(summary.get('wetlab_primary_burndown_delta_A'))}`",
        f"- wetlab_primary_repair_lane: `{summary.get('wetlab_primary_repair_lane', '') or '-'}`",
        f"- wetlab_primary_repair_action: `{summary.get('wetlab_primary_repair_action', '') or '-'}`",
        f"- wetlab_primary_repair_source_artifact: `{summary.get('wetlab_primary_repair_source_artifact', '') or '-'}`",
        f"- wetlab_primary_repair_source_ligand_id: `{summary.get('wetlab_primary_repair_source_ligand_id', '') or '-'}`",
        f"- wetlab_next_required_step: {summary.get('wetlab_next_required_step') or '-'}",
        f"- rescue_attempt_validation_required: `{summary.get('rescue_attempt_validation_required')}`",
        f"- rescue_attempt_validation_present: `{summary.get('rescue_attempt_validation_present')}`",
        f"- rescue_attempt_validation_status: `{summary.get('rescue_attempt_validation_status') or '-'}`",
        f"- rescue_attempt_validation_pass: `{summary.get('rescue_attempt_validation_pass')}`",
        f"- rescue_attempt_validation_ok: `{summary.get('rescue_attempt_validation_ok')}`",
        f"- rescue_attempt_validation_failed_check_count: `{summary.get('rescue_attempt_validation_failed_check_count', 0)}`",
        f"- rescue_attempt_validation_hard_fail_count: `{summary.get('rescue_attempt_validation_hard_fail_count', 0)}`",
        f"- rescue_attempt_validation_warning_count: `{summary.get('rescue_attempt_validation_warning_count', 0)}`",
        f"- rescue_attempt_validation_artifact: `{summary.get('rescue_attempt_validation_artifact') or '-'}`",
        f"- rescue_attempt_validation_reason: `{(summary.get('rescue_attempt_validation_check') or {}).get('reason', '-')}`",
        f"- partnering_stack_artifact_status: `{summary.get('partnering_stack_artifact_status') or '-'}`",
        f"- partnering_stack_artifact_complete: `{summary.get('partnering_stack_artifact_complete')}`",
        f"- partnering_stack_source_artifact_status: `{summary.get('partnering_stack_source_artifact_status') or '-'}`",
        f"- partnering_stack_source_artifact_complete: `{summary.get('partnering_stack_source_artifact_complete')}`",
        f"- claim_scope_ok: `{summary['claim_scope_ok']}`",
        f"- status_line: {summary['status_line']}",
        f"- next_required_step: {summary['next_required_step']}",
        "",
        "## P0 Blockers",
        "",
    ]
    blockers = payload.get("p0_blockers", []) or []
    if blockers:
        lines.append("Do not issue a delivery-ready verdict while any P0 blocker remains.")
        lines.append("")
        for blocker in blockers:
            artifact = _text(blocker.get("artifact")) or "-"
            lines.append(f"- `{blocker.get('code')}` ({artifact}): {blocker.get('reason')}")
    else:
        lines.append("- None. Restricted-scope delivery-ready verdict is allowed by this code-only gate.")

    lines.extend(
        [
            "",
            "## Artifact Fingerprints",
            "",
            "| label | status | generated_at | mtime_local | size_bytes | sha256_prefix | path |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for artifact in payload.get("source_artifacts", []) or []:
        sha256 = _text(artifact.get("sha256"))
        sha256_display = sha256[:12] if sha256 else "-"
        generated_at = _text(artifact.get("generated_at")) or "-"
        mtime_local = _text(artifact.get("mtime_local")) or "-"
        lines.append(
            f"| `{artifact.get('label')}` | `{artifact.get('status', '-')}` | `{generated_at}` | "
            f"`{mtime_local}` | {_int(artifact.get('size_bytes'))} | `{sha256_display}` | `{artifact.get('path')}` |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the conservative local-delivery verdict gate from existing artifacts.")
    parser.add_argument("--claim-scope", default="kinase,gpcr,ion_channel")
    parser.add_argument("--preflight-json", default=DEFAULT_PREFLIGHT_JSON)
    parser.add_argument("--accuracy-gate-json", default=DEFAULT_ACCURACY_GATE_JSON)
    parser.add_argument("--requirements-lock-json", default=DEFAULT_REQUIREMENTS_LOCK_JSON)
    parser.add_argument("--environment-manifest-json", default=DEFAULT_ENVIRONMENT_MANIFEST_JSON)
    parser.add_argument("--engine-provenance-json", default=DEFAULT_ENGINE_PROVENANCE_JSON)
    parser.add_argument("--commercialization-queue-json", default=DEFAULT_COMMERCIALIZATION_QUEUE_JSON)
    parser.add_argument("--status-report-md", default=DEFAULT_STATUS_REPORT_MD)
    parser.add_argument("--nightly-gate-json", default=DEFAULT_NIGHTLY_GATE_JSON)
    parser.add_argument("--wetlab-selected-allatom-json", default=DEFAULT_WETLAB_SELECTED_ALLATOM_JSON)
    parser.add_argument("--current-results-index-json", default=DEFAULT_CURRENT_RESULTS_INDEX_JSON)
    parser.add_argument("--partnering-stack-json", default=DEFAULT_PARTNERING_STACK_JSON)
    parser.add_argument("--rescue-current-json", default=DEFAULT_RESCUE_CURRENT_JSON)
    parser.add_argument("--rescue-attempt-validation-json", default=DEFAULT_RESCUE_ATTEMPT_VALIDATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_payload(
        claim_scope=args.claim_scope,
        preflight_json=args.preflight_json,
        accuracy_gate_json=args.accuracy_gate_json,
        requirements_lock_json=args.requirements_lock_json,
        environment_manifest_json=args.environment_manifest_json,
        engine_provenance_json=args.engine_provenance_json,
        commercialization_queue_json=args.commercialization_queue_json,
        status_report_md=args.status_report_md,
        nightly_gate_json=args.nightly_gate_json,
        wetlab_selected_allatom_json=args.wetlab_selected_allatom_json,
        current_results_index_json=args.current_results_index_json,
        partnering_stack_json=args.partnering_stack_json,
        rescue_current_json=args.rescue_current_json,
        rescue_attempt_validation_json=args.rescue_attempt_validation_json,
    )
    out_json = _resolve(args.out_json)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))
    return 0 if bool(payload["summary"]["delivery_ready"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
