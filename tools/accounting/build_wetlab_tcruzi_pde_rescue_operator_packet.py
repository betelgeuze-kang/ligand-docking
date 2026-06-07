#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
PARTNER_TRACK_ID = "DNDi_IPK"
PARTNER_TRACK_LABEL = "DNDi / Institut Pasteur Korea"
DEFAULT_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md"


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})


def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value in {"", None}:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "ready", "pass", "passed"}:
        return True
    if text in {"0", "false", "f", "no", "n", "fail", "failed"}:
        return False
    return None


def _resolve_bool_value(
    review_packet_summary: dict[str, Any],
    branch_summary: dict[str, Any],
    *,
    review_keys: tuple[str, ...],
    branch_keys: tuple[str, ...],
    default: bool = False,
    default_source: str = "default",
) -> tuple[bool, str]:
    for key in review_keys:
        value = _safe_bool(review_packet_summary.get(key))
        if value is not None:
            return value, f"review_packet.{key}"
    for key in branch_keys:
        value = _safe_bool(branch_summary.get(key))
        if value is not None:
            return value, f"branch_summary.{key}"
    return default, default_source


def _resolve_optional_bool_value(
    review_packet_summary: dict[str, Any],
    branch_summary: dict[str, Any],
    *,
    review_keys: tuple[str, ...],
    branch_keys: tuple[str, ...],
) -> tuple[bool | None, str]:
    for key in review_keys:
        value = _safe_bool(review_packet_summary.get(key))
        if value is not None:
            return value, f"review_packet.{key}"
    for key in branch_keys:
        value = _safe_bool(branch_summary.get(key))
        if value is not None:
            return value, f"branch_summary.{key}"
    return None, "missing"


def _review_ready_only_source(review_ready_source: str) -> str:
    if review_ready_source and review_ready_source != "default":
        return f"review_ready_only.{review_ready_source}"
    return "missing_explicit_gate"


def _source_is_review_ready_only_fallback(source: str) -> bool:
    return source.startswith("review_ready_only.") or source == "missing_explicit_gate"


def _gate_semantics(source: str, *, reported: bool) -> str:
    if source == "derived_from_explicit_wetlab_gate_pass":
        return "derived_from_explicit_wetlab_gate"
    if reported:
        return "explicit_gate_reported"
    if _source_is_review_ready_only_fallback(source):
        return "review_ready_only_blocked_pending_explicit_gate"
    return "blocked_pending_explicit_gate"


def build_payload(
    review_packet_payload: dict[str, Any] | None,
    branch_summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    packet_summary = _summary(review_packet_payload)
    branch_summary = _summary(branch_summary_payload)
    packet_rows = [dict(row) for row in ((review_packet_payload or {}).get("rows", []) or [])]

    target_id = _text(packet_summary.get("target_id"), TARGET_ID)
    shard_id = _text(packet_summary.get("shard_id"))
    selected_command_kind = _text(packet_summary.get("selected_command_kind"))
    selected_threshold_A = _safe_float(packet_summary.get("strict_threshold_A"), 2.5)
    near_threshold_A = _safe_float(packet_summary.get("near_threshold_A"), 3.0)
    strict_candidate_count = _safe_int(packet_summary.get("under_2p5_candidate_count"))
    near_candidate_count = _safe_int(packet_summary.get("near_candidate_count"))
    legacy_packet_ready = (
        _text(packet_summary.get("status")) == "wetlab_tcruzi_pde_promoted_top4_review_packet_ready"
        and bool(packet_rows)
    )
    packet_ready_for_operator_review, operator_ready_source = _resolve_bool_value(
        packet_summary,
        branch_summary,
        review_keys=("packet_ready_for_operator_review", "packet_ready"),
        branch_keys=(
            "review_packet_ready_for_operator_review",
            "packet_ready_for_operator_review",
            "review_packet_ready",
            "packet_ready",
        ),
        default=legacy_packet_ready,
        default_source="legacy_status_rows",
    )
    explicit_wetlab_gate_pass, explicit_wetlab_gate_source = _resolve_optional_bool_value(
        packet_summary,
        branch_summary,
        review_keys=("wetlab_gate_pass",),
        branch_keys=("review_packet_wetlab_gate_pass", "wetlab_gate_pass"),
    )
    if explicit_wetlab_gate_pass is None:
        wetlab_gate_pass = False
        wetlab_gate_source = _review_ready_only_source(operator_ready_source)
        wetlab_gate_reported = False
    else:
        wetlab_gate_pass = explicit_wetlab_gate_pass
        wetlab_gate_source = explicit_wetlab_gate_source
        wetlab_gate_reported = True

    explicit_final_gate_pass, explicit_final_gate_source = _resolve_optional_bool_value(
        packet_summary,
        branch_summary,
        review_keys=("wetlab_final_gate_pass",),
        branch_keys=(
            "review_packet_final_gate_pass",
            "wetlab_final_gate_pass",
        ),
    )
    if explicit_final_gate_pass is not None:
        wetlab_final_gate_pass = explicit_final_gate_pass
        wetlab_final_gate_source = explicit_final_gate_source
        wetlab_final_gate_reported = True
    elif explicit_wetlab_gate_pass is not None:
        wetlab_final_gate_pass = explicit_wetlab_gate_pass
        wetlab_final_gate_source = "derived_from_explicit_wetlab_gate_pass"
        wetlab_final_gate_reported = False
    else:
        wetlab_final_gate_pass = False
        wetlab_final_gate_source = _review_ready_only_source(operator_ready_source)
        wetlab_final_gate_reported = False
    claim_gate_available, claim_gate_source = _resolve_bool_value(
        packet_summary,
        branch_summary,
        review_keys=("claim_gate_available",),
        branch_keys=("review_packet_claim_gate_available", "claim_gate_available"),
        default=False,
    )
    claim_ready_for_allatom, claim_ready_source = _resolve_bool_value(
        packet_summary,
        branch_summary,
        review_keys=("claim_ready_for_allatom",),
        branch_keys=("review_packet_claim_ready_for_allatom", "claim_ready_for_allatom"),
        default=False,
    )
    next_required_step = (
        (
            "Use this PDE rescue operator packet as the partner/operator review surface for the promoted top-4 rescue unit only, "
            "keep outbound send blocked, and keep the default lane closed until operator review confirms the rescue-only branch handoff. "
            "The final wetlab gate currently passes."
            if wetlab_final_gate_pass and not _source_is_review_ready_only_fallback(wetlab_final_gate_source)
            else "Use this PDE rescue operator packet as the partner/operator review surface for the promoted top-4 rescue unit only, "
            "keep outbound send blocked, and keep the default lane closed until the explicit final wetlab gate is reported and passes."
        )
        if packet_ready_for_operator_review
        else "No promoted top-4 rescue candidates are available for the PDE rescue operator packet yet."
    )

    rows: list[dict[str, Any]] = []
    for row in packet_rows:
        mean_min_distance_A = round(_safe_float(row.get("mean_min_distance_A")), 3)
        strict_candidate = mean_min_distance_A > 0 and mean_min_distance_A <= selected_threshold_A
        rows.append(
            {
                "row_kind": "tcruzi_pde_rescue_operator_packet_row",
                "packet_rank": _safe_int(row.get("packet_rank")),
                "target_id": target_id,
                "shard_id": shard_id,
                "ligand_id": _text(row.get("ligand_id")),
                "promotion_band": _text(row.get("promotion_band")),
                "mean_min_distance_A": mean_min_distance_A,
                "review_action": _text(row.get("review_action")),
                "operator_review_bucket": (
                    "strict_promote_candidate_review"
                    if strict_candidate
                    else "near_band_manual_candidate_review"
                ),
                "operator_decision_hint": (
                    "promote_rescue_only_branch"
                    if strict_candidate
                    else "manual_review_rescue_only_branch"
                ),
                "partner_track_id": PARTNER_TRACK_ID,
                "partner_track_label": PARTNER_TRACK_LABEL,
                "partner_review_status": "internal_rescue_review_only",
                "outbound_send_allowed_now": "no",
                "packet_ready_for_operator_review": packet_ready_for_operator_review,
                "wetlab_gate_pass": wetlab_gate_pass,
                "wetlab_gate_reported": wetlab_gate_reported,
                "wetlab_final_gate_pass": wetlab_final_gate_pass,
                "wetlab_final_gate_reported": wetlab_final_gate_reported,
                "claim_gate_available": claim_gate_available,
                "claim_ready_for_allatom": claim_ready_for_allatom,
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "compound_name": _text(row.get("compound_name")),
                "compound_name_human_readable": _text(row.get("compound_name_human_readable")),
                "compound_name_resolution": _text(row.get("compound_name_resolution"), default="unresolved"),
                "smiles": _text(row.get("smiles")),
            }
        )

    return {
        "summary": {
            "status": (
                "wetlab_tcruzi_pde_rescue_operator_packet_ready"
                if packet_ready_for_operator_review
                else "wetlab_tcruzi_pde_rescue_operator_packet_empty"
            ),
            "target_id": target_id,
            "shard_id": shard_id,
            "packet_scope": "partner_operator_rescue_only_review",
            "packet_ready": packet_ready_for_operator_review,
            "packet_ready_for_operator_review": packet_ready_for_operator_review,
            "packet_ready_source": operator_ready_source,
            "wetlab_gate_pass": wetlab_gate_pass,
            "wetlab_gate_source": wetlab_gate_source,
            "wetlab_gate_reported": wetlab_gate_reported,
            "wetlab_gate_semantics": _gate_semantics(wetlab_gate_source, reported=wetlab_gate_reported),
            "wetlab_gate_legacy_fallback": _source_is_review_ready_only_fallback(wetlab_gate_source),
            "wetlab_final_gate_pass": wetlab_final_gate_pass,
            "wetlab_final_gate_source": wetlab_final_gate_source,
            "wetlab_final_gate_reported": wetlab_final_gate_reported,
            "wetlab_final_gate_semantics": _gate_semantics(
                wetlab_final_gate_source,
                reported=wetlab_final_gate_reported,
            ),
            "wetlab_final_gate_legacy_fallback": _source_is_review_ready_only_fallback(wetlab_final_gate_source),
            "claim_gate_available": claim_gate_available,
            "claim_gate_source": claim_gate_source,
            "claim_ready_for_allatom": claim_ready_for_allatom,
            "claim_ready_source": claim_ready_source,
            "surface_label": "pde_rescue_operator_packet",
            "review_unit_kind": "promoted_top4_rescue_unit_only",
            "promoted_unit_source_status": _text(packet_summary.get("status")),
            "promoted_unit_source_branch_status": _text(branch_summary.get("status")),
            "partner_track_id": PARTNER_TRACK_ID,
            "partner_track_label": PARTNER_TRACK_LABEL,
            "selected_command_kind": selected_command_kind,
            "selected_threshold_A": selected_threshold_A,
            "near_threshold_A": near_threshold_A,
            "promoted_candidate_count": len(rows),
            "under_2p5_candidate_count": strict_candidate_count,
            "near_candidate_count": near_candidate_count,
            "strict_candidate_count": strict_candidate_count,
            "manual_review_candidate_count": near_candidate_count,
            "best_ligand_id": _text(packet_summary.get("best_ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(packet_summary.get("best_mean_min_distance_A")), 3),
            "best_compound_name": _text(packet_summary.get("best_compound_name")),
            "best_compound_name_human_readable": _text(packet_summary.get("best_compound_name_human_readable")),
            "best_compound_name_resolution": _text(packet_summary.get("best_compound_name_resolution"), default="unresolved"),
            "best_smiles": _text(packet_summary.get("best_smiles")),
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "outbound_partner_send_allowed_now": False,
            "partner_send_gate_pass": wetlab_final_gate_pass,
            "next_required_step": next_required_step,
        },
        "structured": {
            "promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "ligand_manifest_csv": _text((review_packet_payload or {}).get("structured", {}).get("ligand_manifest_csv")),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE rescue operator packet.")
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--branch-summary-json", default=DEFAULT_BRANCH_SUMMARY_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.review_packet_json),
        maybe_load_json(args.branch_summary_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE Rescue Operator Packet", payload)


if __name__ == "__main__":
    main()
