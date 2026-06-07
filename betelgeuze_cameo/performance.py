from __future__ import annotations

from typing import Any

from betelgeuze_cameo.performance_policy import PRODUCT_GRADE_MODEL1_THRESHOLDS

CLAIM_BOUNDARY = (
    "CAMEO performance scorecard only; it accepts official CAMEO benchmark metrics as external validation evidence. "
    "It does not use local native structures, does not generate predictions, does not send email, and does not mutate external state."
)
ALLOWED_RESULT_SOURCES = {"official_cameo", "cameo_official", "cameo_assessment"}
DEFAULT_THRESHOLDS = dict(PRODUCT_GRADE_MODEL1_THRESHOLDS)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _metric(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _normalize_result_row(row: dict[str, Any], handoff_by_rank: dict[int, dict[str, Any]]) -> dict[str, Any]:
    rank = _int(row.get("cameo_model_rank") or row.get("model_rank") or row.get("rank"))
    source_kind = _text(row.get("result_source_kind") or row.get("source_kind") or row.get("source"))
    handoff_row = handoff_by_rank.get(rank, {})
    target_id = _text(row.get("target_id")) or _text(handoff_row.get("target_id"))
    candidate_id = _text(row.get("candidate_id")) or _text(handoff_row.get("candidate_id"))
    lddt = _metric(row, "lddt", "lDDT", "local_distance_difference_test")
    tm_score = _metric(row, "tm_score", "tm", "tmScore")
    qs_score = _metric(row, "qs_score", "qs", "qsScore")
    rmsd = _metric(row, "rmsd_A", "rmsd", "rmsd_angstrom")
    blockers: list[str] = []
    if source_kind.lower() not in ALLOWED_RESULT_SOURCES:
        blockers.append("result_source_not_official_cameo")
    if rank <= 0 or rank > 5:
        blockers.append("cameo_model_rank_invalid")
    if rank not in handoff_by_rank:
        blockers.append("result_rank_not_in_handoff")
    if not any(value is not None for value in (lddt, tm_score, qs_score, rmsd)):
        blockers.append("official_metric_missing")
    return {
        "target_id": target_id,
        "candidate_id": candidate_id,
        "cameo_model_rank": rank,
        "result_source_kind": source_kind,
        "result_record_id": _text(row.get("result_record_id") or row.get("cameo_result_id") or row.get("assessment_id")),
        "lddt": lddt,
        "tm_score": tm_score,
        "qs_score": qs_score,
        "rmsd_A": rmsd,
        "result_status": "accepted_official_cameo_result" if not blockers else "blocked_result_row",
        "result_blockers": ",".join(blockers),
        "native_local_accuracy_used": False,
        "official_cameo_result_used": not blockers,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _thresholds(thresholds: dict[str, Any] | None) -> dict[str, float]:
    merged: dict[str, float] = dict(DEFAULT_THRESHOLDS)
    for key, value in (thresholds or {}).items():
        parsed = _float_or_none(value)
        if parsed is not None:
            merged[_text(key)] = parsed
    return merged


def _thresholds_from_policy(policy_packet: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(policy_packet, dict):
        return {}
    thresholds = policy_packet.get("thresholds")
    if isinstance(thresholds, dict):
        return thresholds
    summary = policy_packet.get("summary")
    if not isinstance(summary, dict):
        return {}
    return {
        key: summary.get(key)
        for key in DEFAULT_THRESHOLDS
        if summary.get(key) is not None
    }


def _evaluate_model1(row: dict[str, Any], thresholds: dict[str, float]) -> tuple[str, list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    lddt = row.get("lddt")
    if lddt is not None and float(lddt) < thresholds["min_model1_lddt"]:
        failures.append({"metric": "lddt", "value": lddt, "threshold": thresholds["min_model1_lddt"], "operator": ">="})
    tm_score = row.get("tm_score")
    if tm_score is not None and float(tm_score) < thresholds["min_model1_tm_score"]:
        failures.append({"metric": "tm_score", "value": tm_score, "threshold": thresholds["min_model1_tm_score"], "operator": ">="})
    qs_score = row.get("qs_score")
    if qs_score is not None and float(qs_score) < thresholds["min_model1_qs_score"]:
        failures.append({"metric": "qs_score", "value": qs_score, "threshold": thresholds["min_model1_qs_score"], "operator": ">="})
    rmsd = row.get("rmsd_A")
    if rmsd is not None and float(rmsd) > thresholds["max_model1_rmsd_A"]:
        failures.append({"metric": "rmsd_A", "value": rmsd, "threshold": thresholds["max_model1_rmsd_A"], "operator": "<="})
    return ("pass" if not failures else "fail"), failures


def build_cameo_performance_packet(
    handoff_packet: dict[str, Any],
    result_rows: list[dict[str, Any]],
    *,
    thresholds: dict[str, Any] | None = None,
    threshold_policy_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    handoff_summary = handoff_packet.get("summary") if isinstance(handoff_packet.get("summary"), dict) else {}
    handoff_rows = handoff_packet.get("rows") if isinstance(handoff_packet.get("rows"), list) else []
    blockers: list[dict[str, str]] = []
    if handoff_summary.get("status") != "cameo_handoff_dry_run_ready":
        blockers.append(_blocker("handoff_packet_not_ready", "CAMEO handoff packet must be cameo_handoff_dry_run_ready."))
    if handoff_summary.get("native_or_external_accuracy_used") is not False:
        blockers.append(_blocker("handoff_claim_boundary_invalid", "Handoff packet must not use native or external accuracy as proof."))
    if handoff_summary.get("outbound_email_enabled") is not False:
        blockers.append(_blocker("handoff_email_flag_invalid", "Performance intake must start from an email-disabled handoff packet."))

    handoff_by_rank = {
        _int(row.get("cameo_model_rank")): row
        for row in handoff_rows
        if isinstance(row, dict) and _int(row.get("cameo_model_rank")) > 0
    }
    rows = [_normalize_result_row(row, handoff_by_rank) for row in result_rows if isinstance(row, dict)]
    row_blockers = [
        _blocker("official_result_row_blocked", f"Rank {row['cameo_model_rank']} result blocked: {row['result_blockers']}")
        for row in rows
        if row["result_status"] != "accepted_official_cameo_result"
    ]
    blockers.extend(row_blockers)
    accepted = [row for row in rows if row["result_status"] == "accepted_official_cameo_result"]
    model1_rows = [row for row in accepted if _int(row.get("cameo_model_rank")) == 1]
    model1 = model1_rows[0] if model1_rows else {}

    policy_summary = threshold_policy_packet.get("summary") if isinstance(threshold_policy_packet, dict) else {}
    threshold_policy_ready = bool(isinstance(policy_summary, dict) and policy_summary.get("threshold_policy_ready") is True)
    threshold_values = _thresholds(thresholds or _thresholds_from_policy(threshold_policy_packet))
    threshold_gate_status = "not_evaluated"
    threshold_failures: list[dict[str, Any]] = []
    if model1:
        threshold_gate_status, threshold_failures = _evaluate_model1(model1, threshold_values)
    elif rows:
        blockers.append(_blocker("model1_official_result_missing", "Official CAMEO model1 result is required for model1-centered validation."))

    if not rows and not blockers:
        status = "cameo_performance_pending_official_results"
    elif blockers:
        status = "blocked_cameo_performance_scorecard"
    elif threshold_gate_status == "fail":
        status = "cameo_performance_threshold_fail"
    else:
        status = "cameo_performance_evidence_ready"

    target_id = _text(handoff_summary.get("target_id")) or (_text(rows[0].get("target_id")) if rows else "")
    summary = {
        "packet_type": "cameo_performance_scorecard",
        "status": status,
        "target_id": target_id,
        "result_row_count": len(rows),
        "accepted_official_result_count": len(accepted),
        "model1_official_result_count": len(model1_rows),
        "blocker_count": len(blockers),
        "threshold_gate_status": threshold_gate_status,
        "threshold_failure_count": len(threshold_failures),
        "threshold_policy_ready": threshold_policy_ready,
        "threshold_profile_name": _text(policy_summary.get("profile_name")) if isinstance(policy_summary, dict) else "",
        "model1_lddt": model1.get("lddt"),
        "model1_tm_score": model1.get("tm_score"),
        "model1_qs_score": model1.get("qs_score"),
        "model1_rmsd_A": model1.get("rmsd_A"),
        "native_local_accuracy_used": False,
        "official_cameo_results_used": bool(accepted),
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Wait for official CAMEO result rows, then regenerate this scorecard."
            if status == "cameo_performance_pending_official_results"
            else (
                "Review official CAMEO model1 performance evidence against product thresholds."
                if status == "cameo_performance_evidence_ready"
                else "Repair blocked result rows or inspect threshold failures before using this as product validation evidence."
            )
        ),
    }
    return {
        "summary": summary,
        "blockers": blockers,
        "thresholds": threshold_values,
        "threshold_failures": threshold_failures,
        "rows": rows,
    }
