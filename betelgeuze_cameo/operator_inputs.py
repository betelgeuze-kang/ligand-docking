from __future__ import annotations

from pathlib import Path
from typing import Any

from betelgeuze_cameo.performance import ALLOWED_RESULT_SOURCES
from betelgeuze_cameo.selector import ALLOWED_INTERNAL_SOURCE_KINDS

CLAIM_BOUNDARY = (
    "CAMEO operator input validation only; it checks filled local CSV inputs before artifact rebuild. "
    "It does not run predictions, validate model coordinates, submit CAMEO targets, send email, use local native accuracy, "
    "or mutate external state."
)
CANDIDATE_REQUIRED_COLUMNS = (
    "target_id",
    "candidate_id",
    "source_kind",
    "validation_status",
    "model_path",
    "confidence_mean",
    "continuity_fraction",
)
MODEL_REQUIRED_COLUMNS = ("target_id", "candidate_id", "cameo_model_rank", "model_path")
OFFICIAL_RESULT_REQUIRED_COLUMNS = ("target_id", "candidate_id", "cameo_model_rank", "result_source_kind")
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


def _blocker(code: str, reason: str, *, input_name: str = "", row_number: int = 0) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "severity": "hard", "reason": reason}
    if input_name:
        payload["input_name"] = input_name
    if row_number:
        payload["row_number"] = row_number
    return payload


def _warning(code: str, reason: str, *, input_name: str = "", row_number: int = 0) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "severity": "warning", "reason": reason}
    if input_name:
        payload["input_name"] = input_name
    if row_number:
        payload["row_number"] = row_number
    return payload


def _has_placeholder(row: dict[str, Any]) -> bool:
    return any(_text(value).startswith("OPERATOR_FILL") for value in row.values())


def _missing_columns(rows: list[dict[str, Any]], required: tuple[str, ...]) -> list[str]:
    if not rows:
        return list(required)
    columns: set[str] = set()
    for row in rows:
        columns.update(row.keys())
    return [column for column in required if column not in columns]


def _resolve(base_dir: Path, path_text: str) -> Path:
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else base_dir / path


def _validate_candidate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    if not rows:
        blockers.append(_blocker("candidate_rows_missing", "At least one CAMEO candidate row is required.", input_name="candidates_csv"))
        return normalized, blockers, warnings
    missing = _missing_columns(rows, CANDIDATE_REQUIRED_COLUMNS)
    if missing:
        blockers.append(_blocker("candidate_required_columns_missing", "Candidate CSV is missing required columns: " + ",".join(missing), input_name="candidates_csv"))

    seen_candidate_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        row_blockers: list[str] = []
        target_id = _text(row.get("target_id"))
        candidate_id = _text(row.get("candidate_id"))
        source_kind = _text(row.get("source_kind"))
        validation_status = _text(row.get("validation_status"))
        confidence = _float_or_none(row.get("confidence_mean", row.get("confidence")))
        continuity = _float_or_none(row.get("continuity_fraction"))
        if _has_placeholder(row):
            row_blockers.append("operator_placeholder_present")
        if not target_id:
            row_blockers.append("target_id_missing")
        if not candidate_id:
            row_blockers.append("candidate_id_missing")
        elif candidate_id in seen_candidate_ids:
            row_blockers.append("duplicate_candidate_id")
        seen_candidate_ids.add(candidate_id)
        if source_kind not in ALLOWED_INTERNAL_SOURCE_KINDS:
            row_blockers.append("source_kind_not_internal_prediction")
        if validation_status != "pass":
            row_blockers.append("validation_status_not_pass")
        if not _text(row.get("model_path")):
            row_blockers.append("model_path_missing")
        if confidence is None:
            row_blockers.append("confidence_not_numeric")
        if continuity is None:
            row_blockers.append("continuity_fraction_not_numeric")
        if confidence is not None and not (0.0 <= confidence <= 100.0):
            row_blockers.append("confidence_out_of_range")
        if continuity is not None and not (0.0 <= continuity <= 1.0):
            row_blockers.append("continuity_fraction_out_of_range")
        if row_blockers:
            blockers.append(
                _blocker(
                    "candidate_row_blocked",
                    f"Candidate row is not ready: {','.join(row_blockers)}",
                    input_name="candidates_csv",
                    row_number=index,
                )
            )
        normalized.append(
            {
                "input_name": "candidates_csv",
                "row_number": index,
                "target_id": target_id,
                "candidate_id": candidate_id,
                "ready": not row_blockers,
                "blockers": ",".join(row_blockers),
                "source_kind": source_kind,
                "model_path": _text(row.get("model_path")),
            }
        )
    return normalized, blockers, warnings


def _validate_model_rows(rows: list[dict[str, Any]], *, base_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    if not rows:
        blockers.append(_blocker("model_rows_missing", "At least one selected CAMEO model row is required.", input_name="models_csv"))
        return normalized, blockers, warnings
    missing = _missing_columns(rows, MODEL_REQUIRED_COLUMNS)
    if missing:
        blockers.append(_blocker("model_required_columns_missing", "Model CSV is missing required columns: " + ",".join(missing), input_name="models_csv"))

    ranks: list[int] = []
    for index, row in enumerate(rows, start=1):
        row_blockers: list[str] = []
        target_id = _text(row.get("target_id"))
        candidate_id = _text(row.get("candidate_id"))
        rank = _int_or_none(row.get("cameo_model_rank"))
        model_path_text = _text(row.get("model_path"))
        resolved = _resolve(base_dir, model_path_text) if model_path_text else Path()
        if _has_placeholder(row):
            row_blockers.append("operator_placeholder_present")
        if not target_id:
            row_blockers.append("target_id_missing")
        if not candidate_id:
            row_blockers.append("candidate_id_missing")
        if rank is None or not (1 <= rank <= 5):
            row_blockers.append("cameo_model_rank_invalid")
        else:
            ranks.append(rank)
        if not model_path_text:
            row_blockers.append("model_path_missing")
        elif not resolved.exists():
            row_blockers.append("model_path_missing_on_disk")
        elif not resolved.is_file():
            row_blockers.append("model_path_not_file")
        elif resolved.suffix.lower() not in {".pdb", ".ent", ".cif", ".mmcif"}:
            warnings.append(_warning("model_path_extension_unusual", f"Model path extension is not a standard PDB/mmCIF suffix: {model_path_text}", input_name="models_csv", row_number=index))
        if row_blockers:
            blockers.append(
                _blocker(
                    "model_row_blocked",
                    f"Model row is not ready: {','.join(row_blockers)}",
                    input_name="models_csv",
                    row_number=index,
                )
            )
        normalized.append(
            {
                "input_name": "models_csv",
                "row_number": index,
                "target_id": target_id,
                "candidate_id": candidate_id,
                "cameo_model_rank": rank or 0,
                "ready": not row_blockers,
                "blockers": ",".join(row_blockers),
                "model_path": model_path_text,
                "resolved_model_path": str(resolved) if model_path_text else "",
            }
        )
    if ranks and len(set(ranks)) != len(ranks):
        blockers.append(_blocker("model_ranks_not_unique", "CAMEO selected model ranks must be unique.", input_name="models_csv"))
    if ranks and 1 not in ranks:
        blockers.append(_blocker("model1_rank_missing", "Exactly one model row with cameo_model_rank=1 is required.", input_name="models_csv"))
    return normalized, blockers, warnings


def _validate_official_result_rows(
    rows: list[dict[str, Any]],
    *,
    require_official_results: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    if not rows:
        if require_official_results:
            blockers.append(_blocker("official_result_rows_missing", "Official CAMEO result rows are required for evidence-ready validation.", input_name="official_results_csv"))
        else:
            warnings.append(_warning("official_result_rows_not_provided", "Official CAMEO result rows are not available yet; performance will remain pending.", input_name="official_results_csv"))
        return normalized, blockers, warnings
    missing = _missing_columns(rows, OFFICIAL_RESULT_REQUIRED_COLUMNS)
    if missing:
        blockers.append(_blocker("official_result_required_columns_missing", "Official result CSV is missing required columns: " + ",".join(missing), input_name="official_results_csv"))

    model1_seen = False
    for index, row in enumerate(rows, start=1):
        row_blockers: list[str] = []
        rank = _int_or_none(row.get("cameo_model_rank") or row.get("model_rank") or row.get("rank"))
        source = _text(row.get("result_source_kind") or row.get("source_kind") or row.get("source"))
        metric_count = sum(1 for column in METRIC_COLUMNS if _float_or_none(row.get(column)) is not None)
        if _has_placeholder(row):
            row_blockers.append("operator_placeholder_present")
        if rank is None or not (1 <= rank <= 5):
            row_blockers.append("cameo_model_rank_invalid")
        elif rank == 1:
            model1_seen = True
        if source not in ALLOWED_RESULT_SOURCES:
            row_blockers.append("result_source_not_official_cameo")
        if metric_count == 0:
            row_blockers.append("official_metric_missing")
        for column in DISALLOWED_LOCAL_ACCURACY_COLUMNS:
            if _text(row.get(column)):
                row_blockers.append("local_native_accuracy_column_present")
                break
        if row_blockers:
            blockers.append(
                _blocker(
                    "official_result_row_blocked",
                    f"Official result row is not ready: {','.join(row_blockers)}",
                    input_name="official_results_csv",
                    row_number=index,
                )
            )
        normalized.append(
            {
                "input_name": "official_results_csv",
                "row_number": index,
                "target_id": _text(row.get("target_id")),
                "candidate_id": _text(row.get("candidate_id")),
                "cameo_model_rank": rank or 0,
                "ready": not row_blockers,
                "blockers": ",".join(row_blockers),
                "result_source_kind": source,
                "official_metric_count": metric_count,
            }
        )
    if require_official_results and not model1_seen:
        blockers.append(_blocker("official_model1_result_missing", "Official model1 CAMEO result is required for evidence-ready validation.", input_name="official_results_csv"))
    return normalized, blockers, warnings


def build_operator_input_validation(
    *,
    candidates_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    official_result_rows: list[dict[str, Any]] | None = None,
    base_dir: str | Path = ".",
    require_official_results: bool = False,
) -> dict[str, Any]:
    base = Path(base_dir).resolve()
    official_result_rows = official_result_rows or []
    candidate_rows, candidate_blockers, candidate_warnings = _validate_candidate_rows(candidates_rows)
    selected_rows, model_blockers, model_warnings = _validate_model_rows(model_rows, base_dir=base)
    result_rows, result_blockers, result_warnings = _validate_official_result_rows(
        official_result_rows,
        require_official_results=require_official_results,
    )
    blockers = [*candidate_blockers, *model_blockers, *result_blockers]
    warnings = [*candidate_warnings, *model_warnings, *result_warnings]
    if blockers:
        status = "blocked_cameo_operator_input_validation"
    elif official_result_rows:
        status = "cameo_operator_inputs_ready_with_official_results"
    else:
        status = "cameo_operator_inputs_ready_pending_official_results"
    summary = {
        "packet_type": "cameo_operator_input_validation",
        "status": status,
        "candidate_row_count": len(candidates_rows),
        "model_row_count": len(model_rows),
        "official_result_row_count": len(official_result_rows),
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "base_dir": str(base),
        "require_official_results": bool(require_official_results),
        "action_executed": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "native_local_accuracy_used": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run CAMEO selection, format validation, dry-run handoff, and performance artifact builders with these checked inputs."
            if status == "cameo_operator_inputs_ready_with_official_results"
            else (
                "Run CAMEO selection, format validation, and dry-run handoff; performance will remain pending official CAMEO results."
                if status == "cameo_operator_inputs_ready_pending_official_results"
                else "Replace placeholders or repair blocked rows before rebuilding CAMEO validation artifacts."
            )
        ),
    }
    rows = [*candidate_rows, *selected_rows, *result_rows]
    return {"summary": summary, "blockers": blockers, "warnings": warnings, "rows": rows}
