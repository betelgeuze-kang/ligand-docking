from __future__ import annotations

from pathlib import Path
from typing import Any

CLAIM_BOUNDARY = (
    "CAMEO dry-run handoff packet only; it packages selected, format-validated model metadata. "
    "It does not send prediction email, register a server, use native accuracy, or mutate external state."
)
OUTBOUND_EMAIL_APPROVAL_TOKEN = "APPROVE_CAMEO_OUTBOUND_EMAIL"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _blocker(code: str, reason: str) -> dict[str, str]:
    return {"code": code, "severity": "hard", "reason": reason}


def _candidate_key(row: dict[str, Any]) -> tuple[str, str]:
    return _text(row.get("target_id")), _text(row.get("candidate_id"))


def _attachment_filename(row: dict[str, Any]) -> str:
    rank = _int(row.get("cameo_model_rank"))
    fmt = _text(row.get("detected_format")).lower()
    suffix = ".cif" if fmt == "mmcif" else ".pdb"
    candidate = _text(row.get("candidate_id")) or f"model_{rank}"
    safe_candidate = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in candidate).strip("_")
    return f"model_{rank}_{safe_candidate or 'candidate'}{suffix}"


def build_dry_run_handoff_packet(selection_packet: dict[str, Any], format_packet: dict[str, Any]) -> dict[str, Any]:
    selection_summary = selection_packet.get("summary") if isinstance(selection_packet.get("summary"), dict) else {}
    format_summary = format_packet.get("summary") if isinstance(format_packet.get("summary"), dict) else {}
    selection_rows = selection_packet.get("rows") if isinstance(selection_packet.get("rows"), list) else []
    format_rows = format_packet.get("rows") if isinstance(format_packet.get("rows"), list) else []
    blockers: list[dict[str, str]] = []

    if selection_summary.get("selection_status") != "cameo_model1_selection_ready":
        blockers.append(_blocker("selection_packet_not_ready", "CAMEO model1 selection packet must be ready before handoff packaging."))
    if format_summary.get("status") != "cameo_format_validation_ready":
        blockers.append(_blocker("format_packet_not_ready", "CAMEO format validation packet must be ready before handoff packaging."))
    if selection_summary.get("native_or_external_accuracy_used") is not False:
        blockers.append(_blocker("selection_claim_boundary_invalid", "Selection packet must not use native or external accuracy as proof."))
    if format_summary.get("native_or_external_accuracy_used") is not False:
        blockers.append(_blocker("format_claim_boundary_invalid", "Format packet must not use native or external accuracy as proof."))

    selected_keys = {
        _candidate_key(row)
        for row in selection_rows
        if isinstance(row, dict) and _int(row.get("cameo_model_rank")) > 0
    }
    pass_rows = [
        row
        for row in format_rows
        if isinstance(row, dict)
        and _int(row.get("cameo_model_rank")) > 0
        and _text(row.get("format_validation_status")) == "pass"
    ]
    ranks = [_int(row.get("cameo_model_rank")) for row in pass_rows]
    if not pass_rows:
        blockers.append(_blocker("no_format_pass_models", "At least one selected model must pass PDB/mmCIF format validation."))
    if ranks.count(1) != 1:
        blockers.append(_blocker("model1_attachment_missing_or_duplicated", "Exactly one validated model1 attachment is required."))
    if len(ranks) != len(set(ranks)):
        blockers.append(_blocker("duplicate_attachment_rank", "Attachment ranks must be unique."))
    if any(rank < 1 or rank > 5 for rank in ranks):
        blockers.append(_blocker("attachment_rank_out_of_range", "CAMEO dry-run attachments must be ranked model1 through model5."))

    attachments: list[dict[str, Any]] = []
    for row in sorted(pass_rows, key=lambda item: (_int(item.get("cameo_model_rank")), _text(item.get("candidate_id")))):
        key = _candidate_key(row)
        if selected_keys and key not in selected_keys:
            blockers.append(_blocker("format_row_not_in_selection_packet", f"Format row `{key[1]}` is not selected in the model1 packet."))
        model_path = _text(row.get("model_path"))
        if not model_path:
            blockers.append(_blocker("attachment_model_path_missing", f"Selected candidate `{key[1]}` has no model_path."))
        attachments.append(
            {
                "target_id": key[0],
                "candidate_id": key[1],
                "cameo_model_rank": _int(row.get("cameo_model_rank")),
                "model_path": model_path,
                "attachment_filename": _attachment_filename(row),
                "detected_format": _text(row.get("detected_format")),
                "format_validation_status": _text(row.get("format_validation_status")),
                "atom_count": _int(row.get("atom_count")),
                "model_count": _int(row.get("model_count")),
                "chain_count": _int(row.get("chain_count")),
                "residue_count": _int(row.get("residue_count")),
                "outbound_email_enabled": False,
                "claim_boundary": CLAIM_BOUNDARY,
            }
        )

    status = "cameo_handoff_dry_run_ready" if not blockers else "blocked_cameo_handoff"
    target_id = _text(format_summary.get("target_id")) or _text(selection_summary.get("target_id"))
    summary = {
        "packet_type": "cameo_dry_run_handoff_packet",
        "status": status,
        "target_id": target_id,
        "attachment_count": len(attachments),
        "model1_attachment_count": sum(1 for row in attachments if row["cameo_model_rank"] == 1),
        "attachment_ranks": [row["cameo_model_rank"] for row in attachments],
        "blocker_count": len(blockers),
        "blockers": blockers,
        "native_or_external_accuracy_used": False,
        "outbound_email_enabled": False,
        "external_state_mutated": False,
        "email_approval_token_required": OUTBOUND_EMAIL_APPROVAL_TOKEN,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Operator may inspect the dry-run handoff packet; outbound email remains disabled until explicit approval and production sender wiring."
            if status == "cameo_handoff_dry_run_ready"
            else "Repair selection or format-validation blockers before CAMEO dry-run handoff packaging."
        ),
    }
    return {"summary": summary, "rows": attachments}


def source_manifest_rows(packet: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for row in packet.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        path = _text(row.get("model_path"))
        rows.append(
            {
                "candidate_id": _text(row.get("candidate_id")),
                "cameo_model_rank": str(_int(row.get("cameo_model_rank"))),
                "model_path": path,
                "path_suffix": Path(path).suffix.lower(),
            }
        )
    return rows
