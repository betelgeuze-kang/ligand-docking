#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from tools.build_wetlab_rescue_three_bead_candidates import (
    annotate_translation_gate_row,
    summarize_translation_gate_rows,
)
from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_BRANCH_SUMMARY_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.json"
DEFAULT_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_RESCUE_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_THREE_BEAD_SLICE_JSON = "runs/wetlab_rescue_three_bead_slice_current.json"
DEFAULT_RESCUE_ANCHORS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_allatom_rescue_lane_current.md"
DEFAULT_TOP_N = 32
DEFAULT_DEFAULT_TOP_K = 8
ALLATOM_COMMAND_KIND = "pseudo_allatom_backmapping_rescore"
ALLATOM_LIGAND_MODEL = "3bead_implicit_hbond"
STRICT_THRESHOLD_A = 2.5
NEAR_THRESHOLD_A = 3.0
DEFAULT_FILTER_MODE = "all"
AVAILABLE_FILTER_MODES = ["all", "union", "strict_only", "near_only", "strict_then_near_fill"]


def _summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    return dict((payload or {}).get("summary", {}) or {})



def _text(*values: Any, default: str = "") -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default



def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {"", None}:
            return default
        return float(value)
    except Exception:
        return default


def _safe_optional_float(value: Any) -> float | None:
    try:
        if value in {"", None}:
            return None
        return float(value)
    except Exception:
        return None



def _looks_human_readable_compound_name(name: Any) -> bool:
    text = _text(name)
    return bool(text and not text.startswith("chembl_cache_"))


def _normalize_filter_mode(value: Any) -> str:
    raw = _text(value).lower().replace("-", "_")
    aliases = {
        "": DEFAULT_FILTER_MODE,
        "union": "all",
        "strict": "strict_only",
        "near": "near_only",
        "strict_then_near": "strict_then_near_fill",
    }
    mode = aliases.get(raw, raw)
    if mode not in {"all", "strict_only", "near_only", "strict_then_near_fill"}:
        raise ValueError(f"unsupported PDE all-atom rescue filter mode: {value}")
    return mode


def _resolve_review_band(raw_band: Any, mean_min_distance_A: Any) -> tuple[str, str]:
    band = _text(raw_band)
    if band:
        return band, "source_rescue_review_band"
    distance = _safe_float(mean_min_distance_A, float("nan"))
    if distance == distance:
        if distance <= STRICT_THRESHOLD_A:
            return "strict_under_2p5A", "mean_min_distance_A_fallback"
        if distance <= NEAR_THRESHOLD_A:
            return "near_under_3p0A", "mean_min_distance_A_fallback"
        return "candidate_top32", "mean_min_distance_A_fallback"
    return "candidate_top32", "fallback_default"


def _review_band_bucket(review_band: Any) -> str:
    band = _text(review_band)
    if band == "strict_under_2p5A" or band.startswith("strict"):
        return "strict"
    if band == "near_under_3p0A" or band.startswith("near"):
        return "near"
    return "other"


def _numeric_review_band(mean_min_distance_A: Any) -> tuple[str, str]:
    distance = _safe_optional_float(mean_min_distance_A)
    if distance is None:
        return "", ""
    if distance <= STRICT_THRESHOLD_A:
        return "strict_under_2p5A", "source_three_bead_mean_min_distance_A"
    if distance <= NEAR_THRESHOLD_A:
        return "near_under_3p0A", "source_three_bead_mean_min_distance_A"
    return "candidate_top32", "source_three_bead_mean_min_distance_A"


def _band_consistency_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = _text(row.get("rescue_review_band_consistency_status"), default="not_checked")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _band_mismatch_rows_preview(rows: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for row in rows:
        if _text(row.get("rescue_review_band_consistency_status")) != "mismatch_fail_closed":
            continue
        preview.append(
            {
                "lane_rank": _safe_int(row.get("lane_rank")),
                "ligand_id": _text(row.get("ligand_id")),
                "source_three_bead_mean_min_distance_A": _safe_float(
                    row.get("source_three_bead_mean_min_distance_A")
                ),
                "metadata_rescue_review_bucket": _text(row.get("metadata_rescue_review_bucket")),
                "numeric_rescue_review_bucket": _text(row.get("numeric_rescue_review_bucket")),
                "source_rescue_review_band": _text(row.get("source_rescue_review_band")),
                "numeric_rescue_review_band": _text(row.get("numeric_rescue_review_band")),
                "action_code": "rebuild_rescue_review_band_metadata_from_numeric_distance",
            }
        )
        if len(preview) >= limit:
            break
    return preview


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


def _resolve_bool_value(payload: dict[str, Any], *keys: str, default: bool = False) -> bool:
    for key in keys:
        value = _safe_bool(payload.get(key))
        if value is not None:
            return value
    return default


def _translation_gate_row_from_lane_inputs(
    row: dict[str, Any],
    *,
    resolved_review_band: str,
) -> dict[str, Any]:
    source_like_row = {
        "mean_min_distance_A": row.get("source_three_bead_mean_min_distance_A"),
        "binding_energy_proxy": row.get("source_three_bead_binding_energy_proxy"),
        "stability_score": row.get("source_three_bead_stability_score"),
        "contact_fraction": row.get("source_three_bead_contact_fraction"),
        "trajectory_frames": row.get("source_three_bead_trajectory_frames"),
        "pose_preservation_rmsd_A": row.get("source_three_bead_pose_preservation_rmsd_A"),
        "backmapping_consistency_score": row.get("source_three_bead_backmapping_consistency_score"),
        "local_minimization_survival_fraction": row.get("source_three_bead_local_minimization_survival_fraction"),
        "replicate_pass_fraction": row.get("source_three_bead_replicate_pass_fraction"),
    }
    annotated = annotate_translation_gate_row(source_like_row, review_band=resolved_review_band)
    return {
        "translation_gate_version": annotated.get("translation_gate_version"),
        "translation_gate_band_bucket": annotated.get("translation_gate_band_bucket"),
        "translation_gate_score": annotated.get("translation_gate_score"),
        "translation_gate_soft_score": annotated.get("translation_gate_soft_score"),
        "translation_gate_status": annotated.get("translation_gate_status"),
        "translation_gate_hard_status": annotated.get("translation_gate_hard_status"),
        "translation_gate_soft_status": annotated.get("translation_gate_soft_status"),
        "translation_gate_pass": annotated.get("translation_gate_pass"),
        "translation_gate_required_check_count": annotated.get("translation_gate_required_check_count"),
        "translation_gate_required_pass_count": annotated.get("translation_gate_required_pass_count"),
        "translation_gate_optional_check_count": annotated.get("translation_gate_optional_check_count"),
        "translation_gate_optional_pass_count": annotated.get("translation_gate_optional_pass_count"),
        "translation_gate_hard_check_count": annotated.get("translation_gate_hard_check_count"),
        "translation_gate_hard_pass_count": annotated.get("translation_gate_hard_pass_count"),
        "translation_gate_hard_failed_checks": annotated.get("translation_gate_hard_failed_checks"),
        "translation_gate_soft_warning_checks": annotated.get("translation_gate_soft_warning_checks"),
        "translation_gate_failed_checks": annotated.get("translation_gate_failed_checks"),
        "translation_gate_warning_checks": annotated.get("translation_gate_warning_checks"),
        "translation_gate_passed_checks": annotated.get("translation_gate_passed_checks"),
        "translation_gate_requires_pose_tightening": annotated.get("translation_gate_requires_pose_tightening"),
        "translation_gate_reason": annotated.get("translation_gate_reason"),
        "translation_gate_action_codes": annotated.get("translation_gate_action_codes"),
        "translation_gate_blocker_codes": annotated.get("translation_gate_blocker_codes"),
        "stronger_physics_shortlist_version": annotated.get("stronger_physics_shortlist_version"),
        "shortlist_tier": annotated.get("shortlist_tier"),
        "shortlist_promising": annotated.get("shortlist_promising"),
        "recommended_next_expensive_lane": annotated.get("recommended_next_expensive_lane"),
        "recommended_next_expensive_lane_priority": annotated.get("recommended_next_expensive_lane_priority"),
        "recommended_next_expensive_lane_reason": annotated.get("recommended_next_expensive_lane_reason"),
        "recommended_next_expensive_lane_entry_status": annotated.get("recommended_next_expensive_lane_entry_status"),
        "recommended_next_expensive_lane_gate": annotated.get("recommended_next_expensive_lane_gate"),
        "recommended_next_expensive_lane_action": annotated.get("recommended_next_expensive_lane_action"),
        "recommended_next_expensive_lane_action_codes": annotated.get("recommended_next_expensive_lane_action_codes"),
        "recommended_next_expensive_lane_blocker_codes": annotated.get("recommended_next_expensive_lane_blocker_codes"),
    }



def _resolve_stage1_queue_csv(stage2_manifest_csv: str) -> str:
    path = Path(_text(stage2_manifest_csv))
    if not path.exists():
        return ""
    for suffix in ("_stage2_traj_manifest.csv", "_stage2_manifest.csv"):
        if path.name.endswith(suffix):
            return str(path.with_name(path.name.replace(suffix, "_stage1_queue.csv")))
    return str(path.parent / "throughput_run_stage1_queue.csv")



def _resolve_ligand_manifest_csv(
    review_packet_payload: dict[str, Any] | None,
    rescue_review_surface_payload: dict[str, Any] | None,
    stage2_manifest_csv: str,
) -> str:
    review_packet_structured = dict((review_packet_payload or {}).get("structured", {}) or {})
    review_surface_structured = dict((rescue_review_surface_payload or {}).get("structured", {}) or {})
    explicit = _text(
        review_packet_structured.get("ligand_manifest_csv"),
        review_surface_structured.get("ligand_manifest_csv"),
    )
    if explicit:
        return explicit
    path = Path(_text(stage2_manifest_csv))
    if not path.exists():
        return ""
    for parent in [path.parent, *path.parents]:
        candidate = parent / "ligand_manifest.csv"
        if candidate.exists():
            return str(candidate)
    return ""



def _load_ligand_manifest_lookup(path_like: str) -> dict[str, dict[str, str]]:
    path = Path(_text(path_like))
    if not path.exists() or path.is_dir():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    lookup: dict[str, dict[str, str]] = {}
    for row in rows:
        ligand_id = _text(row.get("ligand_id"))
        if not ligand_id:
            continue
        lookup[ligand_id] = {
            "compound_name": _text(row.get("compound_name")),
            "smiles": _text(row.get("smiles")),
            "source_dataset": _text(row.get("source_dataset")),
            "source_anchor": _text(row.get("source_anchor")),
            "source_url": _text(row.get("source_url")),
        }
    return lookup



def build_payload(
    branch_summary_payload: dict[str, Any] | None,
    review_packet_payload: dict[str, Any] | None,
    rescue_review_surface_payload: dict[str, Any] | None,
    rescue_three_bead_candidates_payload: dict[str, Any] | None,
    rescue_three_bead_slice_payload: dict[str, Any] | None,
    rescue_anchor_artifacts_payload: dict[str, Any] | None,
    *,
    top_n: int = DEFAULT_TOP_N,
    default_top_k: int = DEFAULT_DEFAULT_TOP_K,
    default_filter_mode: str = DEFAULT_FILTER_MODE,
) -> dict[str, Any]:
    resolved_default_filter_mode = _normalize_filter_mode(default_filter_mode)
    branch = _summary(branch_summary_payload)
    review_packet = _summary(review_packet_payload)
    rescue_review = _summary(rescue_review_surface_payload)
    rescue_candidates = _summary(rescue_three_bead_candidates_payload)
    rescue_slice = _summary(rescue_three_bead_slice_payload)
    rescue_anchors = _summary(rescue_anchor_artifacts_payload)
    review_rows_by_ligand = {
        _text((row or {}).get("ligand_id")): dict(row or {})
        for row in ((rescue_review_surface_payload or {}).get("rows", []) or [])
        if _text((row or {}).get("ligand_id"))
    }

    target_id = _text(
        branch.get("target_id"),
        review_packet.get("target_id"),
        rescue_review.get("target_id"),
        rescue_candidates.get("target_id"),
        rescue_slice.get("target_id"),
        default=TARGET_ID,
    )
    shard_id = _text(
        branch.get("shard_id"),
        review_packet.get("shard_id"),
        rescue_review.get("shard_id"),
        rescue_candidates.get("shard_id"),
        rescue_slice.get("shard_id"),
    )
    stage2_manifest_csv = _text(rescue_slice.get("stage2_manifest_csv"))
    trajectory_root = _text(rescue_slice.get("trajectory_root"))
    stage1_queue_csv = _resolve_stage1_queue_csv(stage2_manifest_csv)
    ligand_manifest_csv = _resolve_ligand_manifest_csv(review_packet_payload, rescue_review_surface_payload, stage2_manifest_csv)
    ligand_manifest_lookup = _load_ligand_manifest_lookup(ligand_manifest_csv)

    candidate_rows = [
        dict(row or {})
        for row in ((rescue_three_bead_candidates_payload or {}).get("rows", []) or [])
        if _text((row or {}).get("target_id")) == target_id and _text((row or {}).get("shard_id")) == shard_id
    ]
    candidate_rows.sort(
        key=lambda row: (
            _safe_int(row.get("priority_rank"), 0),
            _safe_float(row.get("mean_min_distance_A"), 0.0),
            _text(row.get("ligand_id")),
        )
    )
    lane_rows: list[dict[str, Any]] = []
    for lane_rank, row in enumerate(candidate_rows[: max(1, int(top_n))], start=1):
        ligand_id = _text(row.get("ligand_id"))
        manifest_meta = ligand_manifest_lookup.get(ligand_id, {})
        review_meta = review_rows_by_ligand.get(ligand_id, {})
        compound_name_raw = _text(
            review_meta.get("compound_name"),
            manifest_meta.get("compound_name"),
        )
        compound_name_human = _text(review_meta.get("compound_name_human_readable"))
        if not compound_name_human and _looks_human_readable_compound_name(compound_name_raw):
            compound_name_human = compound_name_raw
        compound_name_resolution = _text(review_meta.get("compound_name_resolution"))
        if not compound_name_resolution:
            compound_name_resolution = (
                "human_readable"
                if compound_name_human
                else "cache_placeholder"
                if compound_name_raw
                else "unresolved"
            )
        raw_review_band = _text(review_meta.get("rescue_review_band"))
        resolved_review_band, review_band_source = _resolve_review_band(
            raw_review_band,
            _text(review_meta.get("mean_min_distance_A"), row.get("mean_min_distance_A")),
        )
        numeric_review_band, numeric_review_band_source = _numeric_review_band(row.get("mean_min_distance_A"))
        metadata_review_bucket = _review_band_bucket(resolved_review_band)
        numeric_review_bucket = _review_band_bucket(numeric_review_band) if numeric_review_band else ""
        if numeric_review_bucket and metadata_review_bucket and metadata_review_bucket != numeric_review_bucket:
            band_consistency_status = "mismatch_fail_closed"
            band_consistency_action_codes = ["rebuild_rescue_review_band_metadata_from_numeric_distance"]
        elif numeric_review_bucket:
            band_consistency_status = "match" if metadata_review_bucket == numeric_review_bucket else "numeric_only"
            band_consistency_action_codes = []
        else:
            band_consistency_status = "metadata_only" if review_band_source != "fallback_default" else "not_checked"
            band_consistency_action_codes = []
        lane_row = {
            "row_kind": "tcruzi_pde_allatom_rescue_candidate",
            "target_id": target_id,
            "target_slug": slug(target_id),
            "shard_id": shard_id,
            "lane_rank": lane_rank,
            "ligand_id": ligand_id,
            "compound_name": compound_name_human or compound_name_raw,
            "compound_name_human_readable": compound_name_human,
            "compound_name_resolution": compound_name_resolution,
            "smiles": _text(review_meta.get("smiles"), manifest_meta.get("smiles")),
            "compound_source_dataset": _text(manifest_meta.get("source_dataset")),
            "compound_source_anchor": _text(manifest_meta.get("source_anchor")),
            "compound_source_url": _text(manifest_meta.get("source_url")),
            "source_three_bead_priority_rank": _safe_int(row.get("priority_rank"), lane_rank),
            "source_three_bead_binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
            "source_three_bead_stability_score": _safe_float(row.get("stability_score")),
            "source_three_bead_mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
            "source_three_bead_contact_fraction": _safe_optional_float(row.get("contact_fraction")),
            "source_three_bead_trajectory_frames": _safe_optional_float(row.get("trajectory_frames")),
            "source_three_bead_pose_preservation_rmsd_A": _safe_optional_float(row.get("pose_preservation_rmsd_A")),
            "source_three_bead_backmapping_consistency_score": _safe_optional_float(
                row.get("backmapping_consistency_score")
            ),
            "source_three_bead_local_minimization_survival_fraction": _safe_optional_float(
                row.get("local_minimization_survival_fraction")
            ),
            "source_three_bead_replicate_pass_fraction": _safe_optional_float(row.get("replicate_pass_fraction")),
            "source_rescue_review_band": raw_review_band or resolved_review_band,
            "source_rescue_review_band_raw": raw_review_band,
            "resolved_rescue_review_band": resolved_review_band,
            "resolved_rescue_review_band_source": review_band_source,
            "metadata_rescue_review_bucket": metadata_review_bucket,
            "numeric_rescue_review_band": numeric_review_band,
            "numeric_rescue_review_band_source": numeric_review_band_source,
            "numeric_rescue_review_bucket": numeric_review_bucket,
            "rescue_review_band_consistency_status": band_consistency_status,
            "rescue_review_band_consistency_action_codes": band_consistency_action_codes,
            "default_filter_mode": resolved_default_filter_mode,
            "selected_command_kind": ALLATOM_COMMAND_KIND,
            "selected_threshold_A": STRICT_THRESHOLD_A,
            "allatom_ligand_model": ALLATOM_LIGAND_MODEL,
            "base_stage1_queue_csv": stage1_queue_csv,
            "base_stage2_manifest_csv": stage2_manifest_csv,
            "base_trajectory_root": trajectory_root,
            "rescue_target_native_csv": _text(rescue_anchors.get("rescue_target_native_csv")),
            "rescue_target_pocket_csv": _text(rescue_anchors.get("rescue_target_pocket_csv")),
            "rescue_target_ligand_csv": _text(rescue_anchors.get("rescue_target_ligand_csv")),
        }
        lane_row.update(
            _translation_gate_row_from_lane_inputs(
                lane_row,
                resolved_review_band=resolved_review_band,
            )
        )
        lane_rows.append(lane_row)

    focus_row = lane_rows[0] if lane_rows else {}
    translation_summary = summarize_translation_gate_rows(lane_rows)
    strict_band_candidate_count = sum(
        1 for row in lane_rows if _review_band_bucket(row.get("resolved_rescue_review_band")) == "strict"
    )
    near_band_candidate_count = sum(
        1 for row in lane_rows if _review_band_bucket(row.get("resolved_rescue_review_band")) == "near"
    )
    other_band_candidate_count = max(0, len(lane_rows) - strict_band_candidate_count - near_band_candidate_count)
    band_mismatch_rows_preview = _band_mismatch_rows_preview(lane_rows)
    band_mismatch_count = len(
        [
            row
            for row in lane_rows
            if _text(row.get("rescue_review_band_consistency_status")) == "mismatch_fail_closed"
        ]
    )
    band_consistency_action_codes = (
        ["rebuild_rescue_review_band_metadata_from_numeric_distance"] if band_mismatch_count else []
    )
    rescue_only_branch_ready_for_operator_review = _resolve_bool_value(
        branch,
        "branch_ready_for_operator_review",
        "review_packet_ready_for_operator_review",
        "review_packet_ready",
        "promoted_top4_packet_ready",
        default=_text(branch.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
    )
    rescue_only_branch_ready_for_final_wetlab = _resolve_bool_value(
        branch,
        "branch_ready_for_final_wetlab",
        "review_packet_final_gate_pass",
        "wetlab_final_gate_pass",
        default=False,
    )
    review_packet_ready_for_operator_review = _resolve_bool_value(
        review_packet,
        "packet_ready_for_operator_review",
        "packet_ready",
        default=False,
    )
    review_packet_wetlab_final_gate_pass = _resolve_bool_value(
        review_packet,
        "wetlab_final_gate_pass",
        "wetlab_gate_pass",
        default=False,
    )
    review_packet_claim_gate_available = _resolve_bool_value(
        review_packet,
        "claim_gate_available",
        default=False,
    )
    review_packet_claim_ready_for_allatom = _resolve_bool_value(
        review_packet,
        "claim_ready_for_allatom",
        default=False,
    )
    lane_ready = bool(lane_rows) and target_id == TARGET_ID and bool(shard_id)
    focus_lane = _text(focus_row.get("recommended_next_expensive_lane")) or "seed_replicated_short_md_consensus"
    focus_lane_gate = _text(focus_row.get("recommended_next_expensive_lane_gate"))
    focus_actions = list(focus_row.get("translation_gate_action_codes", []) or [])
    next_required_step = (
        (
            f"Run the {TARGET_ID} pseudo-all-atom rescue lane for the top-{min(max(1, int(default_top_k)), len(lane_rows))} "
            f"ligands from {shard_id} using the {resolved_default_filter_mode} filter mode; keep the default lane closed and "
            f"use the existing rescue-only branch as the candidate source. Focus lane `{focus_lane}` opens under "
            f"`{focus_lane_gate or 'translation_v2_default'}` with action codes {focus_actions or ['collect_replicate_translation_support']}."
        )
        if lane_rows
        else "The T. cruzi PDE all-atom rescue lane has no top-32 candidate rows yet."
    )
    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_allatom_rescue_lane_ready" if lane_ready else "wetlab_tcruzi_pde_allatom_rescue_lane_empty",
            "target_id": target_id,
            "shard_id": shard_id,
            "lane_label": "tcruzi_pde_allatom_rescue_lane",
            "rescue_only_branch_ready": _text(branch.get("status")) == "wetlab_tcruzi_pde_rescue_only_branch_summary_ready",
            "rescue_only_branch_ready_for_operator_review": rescue_only_branch_ready_for_operator_review,
            "rescue_only_branch_ready_for_final_wetlab": rescue_only_branch_ready_for_final_wetlab,
            "source_branch_label": _text(branch.get("branch_label"), default="tcruzi_pde_rescue_only_branch"),
            "source_branch_state": _text(branch.get("branch_state")),
            "review_packet_ready": bool(review_packet.get("packet_ready", False)),
            "review_packet_ready_for_operator_review": review_packet_ready_for_operator_review,
            "review_packet_wetlab_final_gate_pass": review_packet_wetlab_final_gate_pass,
            "review_packet_claim_gate_available": review_packet_claim_gate_available,
            "review_packet_claim_ready_for_allatom": review_packet_claim_ready_for_allatom,
            "review_surface_ready": _text(rescue_review.get("status")) == "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "selected_command_kind": ALLATOM_COMMAND_KIND,
            "selected_threshold_A": STRICT_THRESHOLD_A,
            "near_threshold_A": NEAR_THRESHOLD_A,
            "allatom_ligand_model": ALLATOM_LIGAND_MODEL,
            "default_filter_mode": resolved_default_filter_mode,
            "available_filter_modes": AVAILABLE_FILTER_MODES,
            "source_candidate_count": _safe_int(rescue_candidates.get("candidate_count"), len(candidate_rows)),
            "lane_candidate_count": len(lane_rows),
            "default_top_k": max(1, int(default_top_k)),
            "strict_band_candidate_count": strict_band_candidate_count,
            "near_band_candidate_count": near_band_candidate_count,
            "other_band_candidate_count": other_band_candidate_count,
            "rescue_review_band_consistency_counts": _band_consistency_counts(lane_rows),
            "rescue_review_band_mismatch_count": band_mismatch_count,
            "source_rescue_review_band_mismatch_count": band_mismatch_count,
            "rescue_review_band_mismatch_rows_preview": band_mismatch_rows_preview,
            "rescue_review_band_consistency_action_codes": band_consistency_action_codes,
            **translation_summary,
            "translation_gate_focus_hard_status": _text(translation_summary.get("translation_gate_focus_hard_status")),
            "translation_gate_focus_soft_status": _text(translation_summary.get("translation_gate_focus_soft_status")),
            "translation_gate_focus_hard_failed_checks": list(
                translation_summary.get("translation_gate_focus_hard_failed_checks", []) or []
            ),
            "translation_gate_focus_soft_warning_checks": list(
                translation_summary.get("translation_gate_focus_soft_warning_checks", []) or []
            ),
            "translation_gate_focus_action_codes": list(
                translation_summary.get("translation_gate_focus_action_codes", []) or []
            ),
            "translation_gate_focus_blocker_codes": list(
                translation_summary.get("translation_gate_focus_blocker_codes", []) or []
            ),
            "source_three_bead_selected_command_kind": _text(
                rescue_candidates.get("selected_command_kind"),
                branch.get("selected_command_kind"),
                default="three_bead_rescue_local_refine",
            ),
            "source_three_bead_selected_threshold_A": _safe_float(
                rescue_candidates.get("selected_threshold_A"),
                _safe_float(branch.get("selected_threshold_A"), STRICT_THRESHOLD_A),
            ),
            "strict_candidate_count": _safe_int(review_packet.get("under_2p5_candidate_count"), _safe_int(rescue_review.get("under_2p5_candidate_count"))),
            "near_candidate_count": _safe_int(review_packet.get("near_candidate_count"), _safe_int(rescue_review.get("near_candidate_count"))),
            "best_ligand_id": _text(review_packet.get("best_ligand_id"), focus_row.get("ligand_id")),
            "best_source_three_bead_mean_min_distance_A": _safe_float(
                review_packet.get("best_mean_min_distance_A"),
                _safe_float(focus_row.get("source_three_bead_mean_min_distance_A")),
            ),
            "base_stage1_queue_csv": stage1_queue_csv,
            "base_stage2_manifest_csv": stage2_manifest_csv,
            "base_trajectory_root": trajectory_root,
            "ligand_manifest_csv": ligand_manifest_csv,
            "rescue_target_native_csv": _text(rescue_anchors.get("rescue_target_native_csv")),
            "rescue_target_pocket_csv": _text(rescue_anchors.get("rescue_target_pocket_csv")),
            "rescue_target_ligand_csv": _text(rescue_anchors.get("rescue_target_ligand_csv")),
            "recommended_next_expensive_lane": _text(focus_row.get("recommended_next_expensive_lane")),
            "recommended_next_expensive_lane_reason": _text(focus_row.get("recommended_next_expensive_lane_reason")),
            "recommended_next_expensive_lane_entry_status": _text(
                translation_summary.get("focus_recommended_next_expensive_lane_entry_status")
            ),
            "recommended_next_expensive_lane_gate": _text(
                translation_summary.get("focus_recommended_next_expensive_lane_gate")
            ),
            "recommended_next_expensive_lane_action": _text(
                translation_summary.get("focus_recommended_next_expensive_lane_action")
            ),
            "recommended_next_expensive_lane_action_codes": list(
                translation_summary.get("focus_recommended_next_expensive_lane_action_codes", []) or []
            ),
            "recommended_next_expensive_lane_blocker_codes": list(
                translation_summary.get("focus_recommended_next_expensive_lane_blocker_codes", []) or []
            ),
            "next_required_step": next_required_step,
        },
        "structured": {
            "rescue_only_branch_summary_artifact": "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md",
            "rescue_review_surface_artifact": "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md",
            "promoted_top4_review_packet_artifact": "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md",
            "rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "rescue_three_bead_slice_artifact": "runs/wetlab_rescue_three_bead_slice_current.md",
            "rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
        },
        "rows": lane_rows,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE pseudo-all-atom rescue lane from the rescue-only branch inputs.")
    parser.add_argument("--branch-summary-json", default=DEFAULT_BRANCH_SUMMARY_JSON)
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--rescue-review-surface-json", default=DEFAULT_RESCUE_REVIEW_SURFACE_JSON)
    parser.add_argument("--three-bead-candidates-json", default=DEFAULT_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--three-bead-slice-json", default=DEFAULT_THREE_BEAD_SLICE_JSON)
    parser.add_argument("--rescue-anchors-json", default=DEFAULT_RESCUE_ANCHORS_JSON)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--default-top-k", type=int, default=DEFAULT_DEFAULT_TOP_K)
    parser.add_argument("--default-filter-mode", default=DEFAULT_FILTER_MODE)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.branch_summary_json),
        maybe_load_json(args.review_packet_json),
        maybe_load_json(args.rescue_review_surface_json),
        maybe_load_json(args.three_bead_candidates_json),
        maybe_load_json(args.three_bead_slice_json),
        maybe_load_json(args.rescue_anchors_json),
        top_n=max(1, int(args.top_n)),
        default_top_k=max(1, int(args.default_top_k)),
        default_filter_mode=args.default_filter_mode,
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE All-Atom Rescue Lane", payload)


if __name__ == "__main__":
    main()
