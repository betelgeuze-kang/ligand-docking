from __future__ import annotations

from typing import Any

ALLOWED_INTERNAL_SOURCE_KINDS = {"internal_prediction", "local_pipeline", "cameo_dry_run"}
CLAIM_BOUNDARY = (
    "CAMEO model1 selector packet only; native structures, public/template structures, external model pools, "
    "and official CAMEO results are not used as proof."
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _confidence_score(row: dict[str, Any]) -> float:
    confidence = _float(row.get("confidence_mean", row.get("confidence", 0.0)))
    if confidence > 1.0:
        confidence /= 100.0
    return _clamp(confidence)


def _rank_prior(row: dict[str, Any]) -> float:
    rank = _int(row.get("rank_hint", row.get("input_rank", 0)))
    if rank <= 0:
        return 0.0
    return _clamp(1.0 / float(rank))


def score_candidate(row: dict[str, Any]) -> dict[str, Any]:
    source_kind = _text(row.get("source_kind")) or "unknown"
    validation_status = _text(row.get("validation_status")) or "unknown"
    confidence_score = _confidence_score(row)
    continuity_score = _clamp(_float(row.get("continuity_fraction"), 0.0))
    clash_score = _clamp(1.0 - (_float(row.get("ca_clash_count"), 0.0) / 10.0))
    shape_score = _clamp(1.0 - _float(row.get("shape_penalty"), 0.0))
    rank_prior = _rank_prior(row)
    blockers: list[str] = []
    if validation_status != "pass":
        blockers.append("validation_status_not_pass")
    if source_kind not in ALLOWED_INTERNAL_SOURCE_KINDS:
        blockers.append("source_kind_not_internal_prediction")
    if not _text(row.get("model_path")):
        blockers.append("model_path_missing")
    eligible = not blockers
    selection_score = (
        0.45 * confidence_score
        + 0.25 * continuity_score
        + 0.15 * clash_score
        + 0.10 * shape_score
        + 0.05 * rank_prior
    )
    result = dict(row)
    result.update(
        {
            "candidate_id": _text(row.get("candidate_id")) or _text(row.get("model_path")) or "unknown_candidate",
            "target_id": _text(row.get("target_id")) or "unknown_target",
            "source_kind": source_kind,
            "validation_status": validation_status,
            "confidence_score": round(confidence_score, 6),
            "continuity_score": round(continuity_score, 6),
            "clash_score": round(clash_score, 6),
            "shape_score": round(shape_score, 6),
            "rank_prior": round(rank_prior, 6),
            "selection_score": round(selection_score, 6),
            "selector_eligible": eligible,
            "selector_blockers": ",".join(blockers),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    )
    return result


def build_selection_packet(candidates: list[dict[str, Any]], target_id: str = "") -> dict[str, Any]:
    rows = [score_candidate(row) for row in candidates]
    if target_id:
        rows = [row for row in rows if _text(row.get("target_id")).upper() == target_id.upper()]
    eligible_rows = [row for row in rows if row["selector_eligible"]]
    ordered = sorted(
        eligible_rows,
        key=lambda row: (-_float(row.get("selection_score")), _int(row.get("rank_hint"), 999999), _text(row.get("candidate_id"))),
    )
    selected = ordered[:5]
    selected_ids = {id(row): rank for rank, row in enumerate(selected, start=1)}
    for row in rows:
        rank = selected_ids.get(id(row), 0)
        row["cameo_model_rank"] = rank
        row["model1_candidate"] = rank == 1
        row["top5_candidate"] = rank > 0
        row["selection_status"] = "model1_candidate" if rank == 1 else ("top5_candidate" if rank else "not_selected")
    model1_rows = [row for row in rows if row["model1_candidate"]]
    status = "cameo_model1_selection_ready" if len(model1_rows) == 1 else "blocked_no_model1_candidate"
    model1 = model1_rows[0] if model1_rows else {}
    summary = {
        "packet_type": "cameo_model1_selection_packet",
        "selection_status": status,
        "target_id": _text(target_id) or (_text(rows[0].get("target_id")) if rows else ""),
        "candidate_count": len(rows),
        "eligible_candidate_count": len(eligible_rows),
        "top5_candidate_count": len(selected),
        "model1_candidate_count": len(model1_rows),
        "model1_candidate_id": _text(model1.get("candidate_id")),
        "model1_model_path": _text(model1.get("model_path")),
        "model1_selection_score": _float(model1.get("selection_score")),
        "native_or_external_accuracy_used": False,
        "outbound_email_enabled": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Run CAMEO/PDB/mmCIF format validation and operator approval before any outbound prediction email."
            if model1_rows
            else "Generate or attach at least one validation-pass internal candidate before CAMEO model1 handoff."
        ),
    }
    return {"summary": summary, "rows": sorted(rows, key=lambda row: (_text(row.get("target_id")), _int(row.get("cameo_model_rank"), 999999), _text(row.get("candidate_id"))))}

