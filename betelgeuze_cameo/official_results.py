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
    payload: dict[str, Any] = {"code": code, "severity": "hard", "reason": reason}
    if row_number:
        payload["row_number"] = row_number
    return payload


def _normalize_row(row: dict[str, Any], row_number: int) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    target_id = _text(row.get("target_id"))
    candidate_id = _text(row.get("candidate_id"))
    rank = _int_or_none(row.get("cameo_model_rank") or row.get("model_rank") or row.get("rank"))
    source_kind = _text(row.get("result_source_kind") or row.get("source_kind") or row.get("source"))
    source_url = _text(row.get("result_source_url") or row.get("source_url"))
    result_record_id = _text(row.get("result_record_id") or row.get("cameo_result_id") or row.get("assessment_id"))
    retrieved_at = _text(row.get("retrieved_at_utc"))
    assessment_date = _text(row.get("assessment_date"))

    metrics = {column: _float_or_none(row.get(column)) for column in METRIC_COLUMNS}
    if _has_placeholder(row):
        blockers.append("operator_placeholder_present")
    if not target_id:
        blockers.append("target_id_missing")
    if not candidate_id:
        blockers.append("candidate_id_missing")
    if rank is None or not (1 <= rank <= 5):
        blockers.append("cameo_model_rank_invalid")
    if source_kind not in ALLOWED_RESULT_SOURCES:
        blockers.append("result_source_not_official_cameo")
    if not _official_url_ok(source_url):
        blockers.append("result_source_url_not_cameo")
    if not result_record_id:
        blockers.append("result_record_id_missing")
    if not _parse_date(retrieved_at):
        blockers.append("retrieved_at_utc_invalid")
    if not _parse_date(assessment_date):
        blockers.append("assessment_date_invalid")
    if not any(value is not None for value in metrics.values()):
        blockers.append("official_metric_missing")
    for column in DISALLOWED_LOCAL_ACCURACY_COLUMNS:
        if _text(row.get(column)):
            blockers.append("local_native_accuracy_column_present")
            break

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
        "native_local_accuracy_used": False,
        "official_cameo_result_used": not blockers,
        "external_state_mutated": False,
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
    blocker_codes = sorted({str(blocker.get("code", "")).strip() for blocker in blockers if str(blocker.get("code", "")).strip()})
    summary = {
        "packet_type": "cameo_official_results_intake_gate",
        "status": status,
        "result_row_count": len(rows),
        "accepted_official_result_count": len(accepted),
        "rejected_official_result_count": len(rows) - len(accepted),
        "model1_official_result_ready": model1_ready,
        "blocker_count": len(blockers),
        "blocker_codes": blocker_codes,
        "require_model1": require_model1,
        "required_columns": list(REQUIRED_COLUMNS),
        "missing_required_columns": missing,
        "official_metric_columns": list(METRIC_COLUMNS),
        "disallowed_local_accuracy_columns": list(DISALLOWED_LOCAL_ACCURACY_COLUMNS),
        "operator_template_csv": operator_template_csv,
        "operator_intake_csv": operator_intake_csv,
        "native_local_accuracy_used": False,
        "official_cameo_results_used": bool(accepted),
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Use the generated CSV rows as --results-csv for tools/build_cameo_performance_scorecard.py."
            if status == "cameo_official_results_intake_ready"
            else "Fill official CAMEO result rows with CAMEO provenance, model rank, record ID, dates, and at least one official metric."
        ),
    }
    return {"summary": summary, "blockers": blockers, "rows": rows}
