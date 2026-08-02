from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from betelgeuze_cameo.performance import ALLOWED_RESULT_SOURCES

CLAIM_BOUNDARY = (
    "CAMEO official-results intake gate only; it validates operator-provided official CAMEO assessment rows and "
    "their provenance before they are used by the performance scorecard. It does not fetch web pages, submit "
    "predictions, generate models, send email, use local native accuracy, or mutate external state."
)

REQUIRED_COLUMNS = (
    "target_id",
    "candidate_id",
    "cameo_model_rank",
    "result_source_kind",
    "result_source_url",
    "result_record_id",
    "retrieved_at_utc",
    "assessment_date",
)
METRIC_COLUMNS = ("lddt", "tm_score", "qs_score", "rmsd_A")
DISALLOWED_LOCAL_ACCURACY_COLUMNS = (
    "native_accuracy",
    "local_accuracy",
    "tm_against_native",
    "lddt_against_native",
    "rmsd_against_native",
    "template_accuracy",
)
ALLOWED_RESULT_SOURCE_KINDS = tuple(sorted(ALLOWED_RESULT_SOURCES))

BLOCKER_REQUIRED_ACTIONS = {
    "official_result_rows_missing": "Fill at least one official CAMEO result row in the operator intake CSV.",
    "official_result_required_columns_missing": "Use the generated CAMEO official results template and include all required columns.",
    "official_result_row_blocked": "Fix the row-level official CAMEO intake blockers.",
    "official_model1_result_missing": "Attach a ready official CAMEO model1 result row.",
    "operator_placeholder_present": "Replace OPERATOR_FILL placeholders with reviewed official CAMEO result values.",
    "target_id_missing": "Fill target_id from the official CAMEO result row.",
    "candidate_id_missing": "Fill candidate_id for the submitted model/result being assessed.",
    "cameo_model_rank_invalid": "Set cameo_model_rank to an integer between 1 and 5.",
    "result_source_not_official_cameo": "Use an official CAMEO result source kind only.",
    "result_source_url_not_cameo": "Attach the official CAMEO result URL or record URL.",
    "result_record_id_missing": "Attach the official CAMEO result record identifier.",
    "retrieved_at_utc_invalid": "Record a timezone-aware retrieved_at_utc timestamp.",
    "assessment_date_invalid": "Record the official CAMEO assessment date.",
    "official_metric_missing": "Provide at least one official CAMEO metric value.",
    "local_native_accuracy_column_present": "Remove local/native accuracy columns; use official CAMEO metrics only.",
}

BLOCKER_ACTION_PRIORITY = (
    "operator_placeholder_present",
    "result_source_not_official_cameo",
    "result_source_url_not_cameo",
    "result_record_id_missing",
    "retrieved_at_utc_invalid",
    "assessment_date_invalid",
    "official_metric_missing",
    "local_native_accuracy_column_present",
    "target_id_missing",
    "candidate_id_missing",
    "cameo_model_rank_invalid",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(_text(value)))
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return None


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith("OPERATOR_FILL") for value in row.values())


def _parse_date(value: str) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def _official_url_ok(value: str) -> bool:
    parsed = urlparse(_text(value))
    host = parsed.netloc.lower()
    return parsed.scheme in {"http", "https"} and ("cameo" in host or "cameo" in parsed.path.lower())


def _missing_columns(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return list(REQUIRED_COLUMNS)
    columns: set[str] = set()
    for row in rows:
        columns.update(row.keys())
    return [column for column in REQUIRED_COLUMNS if column not in columns]


def _blocker(code: str, reason: str, *, row_number: int = 0) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": "hard",
        "reason": reason,
        "required_action": BLOCKER_REQUIRED_ACTIONS.get(
            code,
            "Resolve this official CAMEO intake blocker.",
        ),
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_promotion_allowed": False,
    }
    if row_number:
        payload["row_number"] = row_number
    return payload


def _disallowed_columns_present(row: dict[str, Any]) -> list[str]:
    row_columns = {str(column).strip().lower() for column in row.keys()}
    return [
        column
        for column in DISALLOWED_LOCAL_ACCURACY_COLUMNS
        if column.lower() in row_columns
    ]


def _required_action(blockers: list[str]) -> str:
    if not blockers:
        return "Use this official CAMEO row in the performance scorecard."
    ordered = [
        code
        for code in BLOCKER_ACTION_PRIORITY
        if code in set(blockers)
    ]
    ordered.extend(code for code in blockers if code not in set(ordered))
    actions: list[str] = []
    for code in ordered:
        action = BLOCKER_REQUIRED_ACTIONS.get(code)
        if action and action not in actions:
            actions.append(action)
    return " ".join(actions) or "Resolve this official CAMEO intake row blocker."


def _normalize_row(row: dict[str, Any], row_number: int) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    target_id = _text(row.get("target_id"))
    candidate_id = _text(row.get("candidate_id"))
    rank = _int_or_none(row.get("cameo_model_rank") or row.get("model_rank") or row.get("rank"))
    source_kind = _text(row.get("result_source_kind") or row.get("source_kind") or row.get("source")).lower()
    source_url = _text(row.get("result_source_url") or row.get("source_url"))
    result_record_id = _text(row.get("result_record_id") or row.get("cameo_result_id") or row.get("assessment_id"))
    retrieved_at = _text(row.get("retrieved_at_utc"))
    assessment_date = _text(row.get("assessment_date"))

    metrics = {column: _float_or_none(row.get(column)) for column in METRIC_COLUMNS}
    official_source_kind_ready = source_kind in ALLOWED_RESULT_SOURCES
    official_source_url_ready = _official_url_ok(source_url)
    result_record_ready = bool(result_record_id)
    retrieved_at_utc_ready = _parse_date(retrieved_at)
    assessment_date_ready = _parse_date(assessment_date)
    official_metric_ready = any(value is not None for value in metrics.values())
    disallowed_columns = _disallowed_columns_present(row)
    local_native_accuracy_absent = not disallowed_columns
    if _has_placeholder(row):
        blockers.append("operator_placeholder_present")
    if not target_id:
        blockers.append("target_id_missing")
    if not candidate_id:
        blockers.append("candidate_id_missing")
    if rank is None or not (1 <= rank <= 5):
        blockers.append("cameo_model_rank_invalid")
    if not official_source_kind_ready:
        blockers.append("result_source_not_official_cameo")
    if not official_source_url_ready:
        blockers.append("result_source_url_not_cameo")
    if not result_record_ready:
        blockers.append("result_record_id_missing")
    if not retrieved_at_utc_ready:
        blockers.append("retrieved_at_utc_invalid")
    if not assessment_date_ready:
        blockers.append("assessment_date_invalid")
    if not official_metric_ready:
        blockers.append("official_metric_missing")
    if disallowed_columns:
        blockers.append("local_native_accuracy_column_present")

    normalized = {
        "row_number": row_number,
        "target_id": target_id,
        "candidate_id": candidate_id,
        "cameo_model_rank": rank or 0,
        "result_source_kind": source_kind,
        "result_source_url": source_url,
        "result_record_id": result_record_id,
        "retrieved_at_utc": retrieved_at,
        "assessment_date": assessment_date,
        "lddt": metrics["lddt"],
        "tm_score": metrics["tm_score"],
        "qs_score": metrics["qs_score"],
        "rmsd_A": metrics["rmsd_A"],
        "official_metric_count": sum(1 for value in metrics.values() if value is not None),
        "ready": not blockers,
        "blockers": ",".join(blockers),
        "blocker_count": len(blockers),
        "source_provenance_ready": bool(
            official_source_kind_ready
            and official_source_url_ready
            and result_record_ready
            and retrieved_at_utc_ready
            and assessment_date_ready
        ),
        "official_source_kind_ready": official_source_kind_ready,
        "official_source_url_ready": official_source_url_ready,
        "result_record_ready": result_record_ready,
        "retrieved_at_utc_ready": retrieved_at_utc_ready,
        "assessment_date_ready": assessment_date_ready,
        "official_metric_ready": official_metric_ready,
        "local_native_accuracy_absent": local_native_accuracy_absent,
        "disallowed_local_accuracy_columns_present": ",".join(disallowed_columns),
        "required_action": _required_action(blockers),
        "operator_action_required": bool(blockers),
        "native_local_accuracy_used": False,
        "official_cameo_result_used": not blockers,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return normalized, blockers


def build_cameo_official_results_intake_gate(
    *,
    result_rows: list[dict[str, Any]],
    require_model1: bool = True,
    operator_template_csv: str = "runs/cameo_official_results_operator_template_current.csv",
    operator_intake_csv: str = "runs/cameo_official_results_operator_intake.csv",
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    missing = _missing_columns(result_rows)
    if not result_rows:
        blockers.append(_blocker("official_result_rows_missing", "At least one official CAMEO result row is required."))
    if missing:
        blockers.append(_blocker("official_result_required_columns_missing", "Official result CSV is missing required columns: " + ",".join(missing)))

    rows: list[dict[str, Any]] = []
    model1_ready = False
    for index, row in enumerate(result_rows, start=1):
        normalized, row_blockers = _normalize_row(row, index)
        if row_blockers:
            blockers.append(_blocker("official_result_row_blocked", "Official result row is not ready: " + ",".join(row_blockers), row_number=index))
        if normalized["ready"] and normalized["cameo_model_rank"] == 1:
            model1_ready = True
        rows.append(normalized)
    if require_model1 and result_rows and not model1_ready:
        blockers.append(_blocker("official_model1_result_missing", "A ready official CAMEO model1 result row is required."))

    status = "cameo_official_results_intake_ready" if not blockers else "blocked_cameo_official_results_intake"
    accepted = [row for row in rows if row["ready"]]
    action_rows = [row for row in rows if row["operator_action_required"]]
    blocker_codes = sorted({str(blocker.get("code", "")).strip() for blocker in blockers if str(blocker.get("code", "")).strip()})
    primary_blocker = blockers[0] if blockers else {}
    summary = {
        "packet_type": "cameo_official_results_intake_gate",
        "status": status,
        "official_result_intake_ready": status == "cameo_official_results_intake_ready",
        "result_row_count": len(rows),
        "accepted_official_result_count": len(accepted),
        "rejected_official_result_count": len(rows) - len(accepted),
        "model1_official_result_ready": model1_ready,
        "blocker_count": len(blockers),
        "blocker_codes": blocker_codes,
        "operator_action_required_count": len(blockers),
        "operator_action_required_row_count": len(action_rows),
        "primary_blocker_code": _text(primary_blocker.get("code")),
        "primary_blocker_row_number": int(primary_blocker.get("row_number") or 0),
        "primary_required_action": _text(primary_blocker.get("required_action")),
        "require_model1": require_model1,
        "required_columns": list(REQUIRED_COLUMNS),
        "missing_required_columns": missing,
        "official_metric_columns": list(METRIC_COLUMNS),
        "disallowed_local_accuracy_columns": list(DISALLOWED_LOCAL_ACCURACY_COLUMNS),
        "allowed_result_source_kinds": list(ALLOWED_RESULT_SOURCE_KINDS),
        "operator_template_csv": operator_template_csv,
        "operator_intake_csv": operator_intake_csv,
        "source_provenance_ready_row_count": sum(
            1 for row in rows if row["source_provenance_ready"]
        ),
        "official_metric_ready_row_count": sum(
            1 for row in rows if row["official_metric_ready"]
        ),
        "local_native_accuracy_blocker_count": sum(
            1 for row in rows if not row["local_native_accuracy_absent"]
        ),
        "native_local_accuracy_used": False,
        "official_cameo_results_used": bool(accepted),
        "outbound_email_enabled": False,
        "claim_promotion_allowed": False,
        "execution_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the generated CSV rows as --results-csv for tools/build_cameo_performance_scorecard.py."
            if status == "cameo_official_results_intake_ready"
            else "Fill official CAMEO result rows with CAMEO provenance, model rank, record ID, dates, and at least one official metric."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
