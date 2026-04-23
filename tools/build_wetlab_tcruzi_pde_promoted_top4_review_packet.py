#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_THREE_BEAD_SLICE_JSON = "runs/wetlab_rescue_three_bead_slice_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md"


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


def build_payload(
    review_surface_payload: dict[str, Any],
    three_bead_slice_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review = _summary(review_surface_payload)
    slice_summary = _summary(three_bead_slice_payload)
    review_rows = [dict(row or {}) for row in (review_surface_payload.get("rows", []) or [])]
    promoted_rows = review_rows[:4]

    target_id = _text(review.get("target_id"), slice_summary.get("target_id"), TARGET_ID)
    shard_id = _text(review.get("shard_id"), slice_summary.get("shard_id"))
    selected_command_kind = _text(
        review.get("selected_command_kind"),
        slice_summary.get("selected_command_kind"),
        "three_bead_rescue_local_refine",
    )
    strict_threshold = _safe_float(review.get("strict_threshold_A"), _safe_float(slice_summary.get("selected_threshold_A"), 2.5))
    near_threshold = _safe_float(review.get("near_threshold_A"), 3.0)

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(promoted_rows, start=1):
        mean_min_distance = _safe_float(row.get("mean_min_distance_A"))
        rows.append(
            {
                "row_kind": "tcruzi_pde_promoted_top4_packet_row",
                "packet_rank": idx,
                "target_id": target_id,
                "shard_id": shard_id,
                "ligand_id": _text(row.get("ligand_id")),
                "promotion_band": _text(row.get("rescue_review_band")),
                "mean_min_distance_A": round(mean_min_distance, 3),
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "trajectory_frames": _safe_int(row.get("trajectory_frames")),
                "queue_id": _text(row.get("queue_id")),
                "ligand_model": _text(row.get("ligand_model")),
                "compound_name": _text(row.get("compound_name")),
                "compound_name_human_readable": _text(row.get("compound_name_human_readable")),
                "compound_name_resolution": _text(row.get("compound_name_resolution"), default="unresolved"),
                "smiles": _text(row.get("smiles")),
                "review_action": (
                    "strict_promote_rescue_only_branch"
                    if mean_min_distance > 0 and mean_min_distance <= strict_threshold
                    else "near_band_manual_review_rescue_only_branch"
                ),
            }
        )

    best_row = rows[0] if rows else {}
    next_required_step = (
        f"Use this promoted top-4 packet as the PDE rescue-only review unit, keep the default lane closed, and review only these promoted rescue candidates before any reopen decision."
        if rows
        else "The PDE rescue-only branch has no promoted top-4 packet rows yet."
    )

    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_promoted_top4_review_packet_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "packet_scope": "promoted_top4_three_bead_rescue_review",
            "packet_ready": bool(rows),
            "packet_ready_for_operator_review": bool(rows),
            # This packet is a rescue-review surface, not a final wetlab gate.
            "wetlab_gate_pass": False,
            "wetlab_final_gate_pass": False,
            "claim_gate_available": False,
            "claim_ready_for_allatom": False,
            "rescue_only_branch": True,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "selected_command_kind": selected_command_kind,
            "strict_threshold_A": strict_threshold,
            "near_threshold_A": near_threshold,
            "source_slice_candidate_count": _safe_int(slice_summary.get("slice_candidate_count")),
            "promoted_candidate_count": len(rows),
            "under_2p5_candidate_count": sum(
                1 for row in rows if _safe_float(row.get("mean_min_distance_A")) > 0 and _safe_float(row.get("mean_min_distance_A")) <= strict_threshold
            ),
            "near_candidate_count": sum(
                1 for row in rows if _safe_float(row.get("mean_min_distance_A")) > strict_threshold and _safe_float(row.get("mean_min_distance_A")) <= near_threshold
            ),
            "best_ligand_id": _text(best_row.get("ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(best_row.get("mean_min_distance_A")), 3),
            "best_binding_energy_proxy": _safe_float(best_row.get("binding_energy_proxy")),
            "best_stability_score": _safe_float(best_row.get("stability_score")),
            "best_compound_name": _text(best_row.get("compound_name")),
            "best_compound_name_human_readable": _text(best_row.get("compound_name_human_readable")),
            "best_compound_name_resolution": _text(best_row.get("compound_name_resolution"), default="unresolved"),
            "best_smiles": _text(best_row.get("smiles")),
            "next_required_step": next_required_step,
        },
        "structured": {
            "rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            "rescue_three_bead_slice_artifact": "runs/wetlab_rescue_three_bead_slice_current.md",
            "three_bead_scores_csv": _text(slice_summary.get("three_bead_scores_csv")),
            "three_bead_summary_json": _text(slice_summary.get("three_bead_summary_json")),
            "ligand_manifest_csv": _text((review_surface_payload.get("structured", {}) or {}).get("ligand_manifest_csv")),
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE promoted top-4 rescue review packet.")
    parser.add_argument("--review-surface-json", default=DEFAULT_REVIEW_SURFACE_JSON)
    parser.add_argument("--three-bead-slice-json", default=DEFAULT_THREE_BEAD_SLICE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.review_surface_json),
        maybe_load_json(args.three_bead_slice_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE Promoted Top-4 Review Packet", payload)


if __name__ == "__main__":
    main()
