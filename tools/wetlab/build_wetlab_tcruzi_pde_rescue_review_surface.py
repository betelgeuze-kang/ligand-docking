#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean, median
from typing import Any

from tools.wetlab_target_render_utils import load_json, maybe_load_json, write_artifact

TARGET_ID = "T. cruzi PDE"
DEFAULT_HARD_TARGET_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_RESCUE_THREE_BEAD_SLICE_JSON = "runs/wetlab_rescue_three_bead_slice_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.md"


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


def _load_score_rows(score_csv: str) -> list[dict[str, Any]]:
    path = Path(score_csv)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    normalized: list[dict[str, Any]] = []
    for row in rows:
        ligand_id = _text(row.get("ligand_id"))
        if not ligand_id:
            continue
        normalized.append(
            {
                "ligand_id": ligand_id,
                "binding_energy_proxy": _safe_float(row.get("binding_energy_proxy")),
                "stability_score": _safe_float(row.get("stability_score")),
                "mean_min_distance_A": _safe_float(row.get("mean_min_distance_A")),
                "contact_fraction": _safe_float(row.get("contact_fraction")),
                "trajectory_frames": int(_safe_float(row.get("trajectory_frames"), 0)),
                "ligand_model": _text(row.get("ligand_model")),
                "queue_id": _text(row.get("queue_id")),
                "trajectory_npz": _text(row.get("trajectory_npz")),
                "score_json": _text(row.get("score_json")),
            }
        )
    normalized.sort(key=lambda row: (row["mean_min_distance_A"], -row["stability_score"], row["ligand_id"]))
    return normalized


def _looks_human_readable_compound_name(name: Any) -> bool:
    text = _text(name)
    return bool(text and not text.startswith("chembl_cache_"))


def _find_ligand_manifest_path(score_csv: str, score_rows: list[dict[str, Any]]) -> Path | None:
    candidate_paths: list[Path] = []
    score_path = Path(score_csv)
    if _text(score_csv):
        candidate_paths.append(score_path)
    for row in score_rows:
        traj_text = _text(row.get("trajectory_npz"))
        if traj_text:
            traj_path = Path(traj_text)
            candidate_paths.append(traj_path)
    for candidate in candidate_paths:
        for parent in [candidate, *candidate.parents]:
            manifest_path = parent / "ligand_manifest.csv"
            if manifest_path.exists():
                return manifest_path
    return None


def _load_ligand_manifest_lookup(manifest_path: Path | None) -> dict[str, dict[str, str]]:
    if manifest_path is None or not manifest_path.exists():
        return {}
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
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
    hard_target_rescue_lane_payload: dict[str, Any],
    rescue_anchor_artifacts_payload: dict[str, Any],
    rescue_three_bead_candidates_payload: dict[str, Any],
    rescue_three_bead_slice_payload: dict[str, Any],
) -> dict[str, Any]:
    rescue_lane = _summary(hard_target_rescue_lane_payload)
    rescue_anchors = _summary(rescue_anchor_artifacts_payload)
    rescue_candidates = _summary(rescue_three_bead_candidates_payload)
    rescue_slice = _summary(rescue_three_bead_slice_payload)

    target_id = _text(
        rescue_slice.get("target_id"),
        rescue_candidates.get("target_id"),
        rescue_lane.get("target_id"),
        TARGET_ID,
    )
    shard_id = _text(
        rescue_slice.get("shard_id"),
        rescue_candidates.get("shard_id"),
        rescue_lane.get("shard_id"),
    )
    strict_threshold = _safe_float(rescue_slice.get("selected_threshold_A"), 2.5)
    near_threshold = 3.0
    score_csv = _text(rescue_slice.get("three_bead_scores_csv"))
    score_rows = _load_score_rows(score_csv)
    ligand_manifest_path = _find_ligand_manifest_path(score_csv, score_rows)
    ligand_manifest_lookup = _load_ligand_manifest_lookup(ligand_manifest_path)

    promoted_rows = [
        row for row in score_rows if row["mean_min_distance_A"] > 0 and row["mean_min_distance_A"] <= near_threshold
    ]
    strict_rows = [row for row in promoted_rows if row["mean_min_distance_A"] <= strict_threshold]
    strict_count = len(strict_rows)
    near_only_rows = [row for row in promoted_rows if row["mean_min_distance_A"] > strict_threshold]
    near_count = len(near_only_rows)

    best_row = promoted_rows[0] if promoted_rows else (score_rows[0] if score_rows else {})
    promoted_values = [row["mean_min_distance_A"] for row in promoted_rows if row["mean_min_distance_A"] > 0]
    promoted_min = round(min(promoted_values), 3) if promoted_values else 0.0
    promoted_median = round(median(promoted_values), 3) if promoted_values else 0.0
    promoted_mean = round(mean(promoted_values), 3) if promoted_values else 0.0
    promoted_max = round(max(promoted_values), 3) if promoted_values else 0.0

    if strict_count > 0:
        decision = "promote_rescue_only_branch_keep_default_closed"
        decision_rationale = (
            f"The PDE hard-target rescue lane produced {strict_count} top-8 3-bead candidate(s) at or below "
            f"{strict_threshold:.1f}A and {near_count} additional candidate(s) within the {near_threshold:.1f}A near band, "
            "so the default broad-screen lane should stay closed and PDE should move forward only through the rescue branch."
        )
    elif near_count > 0:
        decision = "review_rescue_only_branch_keep_default_closed"
        decision_rationale = (
            f"The PDE hard-target rescue lane produced {near_count} near-threshold top-8 3-bead candidate(s) within "
            f"{near_threshold:.1f}A but none at or below {strict_threshold:.1f}A yet, so the default lane should stay "
            "closed while PDE is managed as a rescue-only branch."
        )
    else:
        decision = "review_more_before_reopen_keep_default_closed"
        decision_rationale = (
            "The PDE hard-target rescue lane has not yet produced near-threshold 3-bead candidates, so the default lane "
            "must stay closed until the rescue branch produces better geometry."
        )

    next_required_step = (
        f"Operate T. cruzi PDE as a rescue-only branch, keep the default lane closed, and review the promoted "
        f"top-8 3-bead rescue subset ({strict_count} at or below {strict_threshold:.1f}A; {near_count} additional within {near_threshold:.1f}A)."
    )

    rows: list[dict[str, Any]] = []
    for priority_rank, row in enumerate(promoted_rows, start=1):
        band = "strict_under_2p5A" if row["mean_min_distance_A"] <= strict_threshold else "near_under_3p0A"
        manifest_meta = ligand_manifest_lookup.get(row["ligand_id"], {})
        compound_name_raw = _text(manifest_meta.get("compound_name"))
        compound_name_human = compound_name_raw if _looks_human_readable_compound_name(compound_name_raw) else ""
        compound_name_resolution = (
            "human_readable"
            if compound_name_human
            else "cache_placeholder"
            if compound_name_raw
            else "unresolved"
        )
        rows.append(
            {
                "row_kind": "pde_rescue_review_candidate",
                "target_id": target_id,
                "shard_id": shard_id,
                "priority_rank": priority_rank,
                "ligand_id": row["ligand_id"],
                "rescue_review_band": band,
                "mean_min_distance_A": round(row["mean_min_distance_A"], 3),
                "binding_energy_proxy": row["binding_energy_proxy"],
                "stability_score": row["stability_score"],
                "contact_fraction": row["contact_fraction"],
                "trajectory_frames": row["trajectory_frames"],
                "ligand_model": row["ligand_model"],
                "queue_id": row["queue_id"],
                "compound_name": compound_name_human or compound_name_raw,
                "compound_name_human_readable": compound_name_human,
                "compound_name_resolution": compound_name_resolution,
                "smiles": _text(manifest_meta.get("smiles")),
                "compound_source_dataset": _text(manifest_meta.get("source_dataset")),
                "compound_source_anchor": _text(manifest_meta.get("source_anchor")),
                "compound_source_url": _text(manifest_meta.get("source_url")),
                "trajectory_npz": row["trajectory_npz"],
                "score_json": row["score_json"],
            }
        )

    best_promoted_row = rows[0] if rows else {}

    return {
        "summary": {
            "status": "wetlab_tcruzi_pde_rescue_review_surface_ready",
            "target_id": target_id,
            "shard_id": shard_id,
            "surface_label": "pde_rescue_review",
            "rescue_only_review": True,
            "default_lane_reopen_allowed": False,
            "branch_to_rescue_only": True,
            "decision": decision,
            "decision_rationale": decision_rationale,
            "strict_threshold_A": strict_threshold,
            "near_threshold_A": near_threshold,
            "source_candidate_count": int(_safe_float(rescue_candidates.get("candidate_count"), 0)),
            "slice_candidate_count": int(_safe_float(rescue_slice.get("slice_candidate_count"), 0)),
            "promoted_candidate_count": len(promoted_rows),
            "under_2p5_candidate_count": strict_count,
            "near_candidate_count": near_count,
            "promoted_ligand_ids": ";".join(row["ligand_id"] for row in rows),
            "best_ligand_id": _text(best_row.get("ligand_id")),
            "best_mean_min_distance_A": round(_safe_float(best_row.get("mean_min_distance_A")), 3),
            "best_binding_energy_proxy": _safe_float(best_row.get("binding_energy_proxy")),
            "best_stability_score": _safe_float(best_row.get("stability_score")),
            "best_compound_name": _text(best_promoted_row.get("compound_name")),
            "best_compound_name_human_readable": _text(best_promoted_row.get("compound_name_human_readable")),
            "best_compound_name_resolution": _text(best_promoted_row.get("compound_name_resolution"), default="unresolved"),
            "best_smiles": _text(best_promoted_row.get("smiles")),
            "promoted_metric_name": "mean_min_distance_A",
            "promoted_metric_min_A": promoted_min,
            "promoted_metric_median_A": promoted_median,
            "promoted_metric_mean_A": promoted_mean,
            "promoted_metric_max_A": promoted_max,
            "selected_command_kind": _text(rescue_slice.get("selected_command_kind"), rescue_candidates.get("selected_command_kind")),
            "selected_threshold_A": strict_threshold,
            "rescue_branch_kind": "three_bead_rescue_branch_only",
            "rescue_anchor_artifact_count": int(_safe_float(rescue_anchors.get("anchor_artifact_count"), 0)),
            "rescue_only": bool(rescue_anchors.get("rescue_only", False)),
            "next_required_step": next_required_step,
        },
        "structured": {
            "hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "rescue_anchor_artifacts_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
            "rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "rescue_three_bead_slice_artifact": "runs/wetlab_rescue_three_bead_slice_current.md",
            "three_bead_scores_csv": score_csv,
            "ligand_manifest_csv": str(ligand_manifest_path) if ligand_manifest_path else "",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE rescue review surface.")
    parser.add_argument("--hard-target-rescue-lane-json", default=DEFAULT_HARD_TARGET_RESCUE_LANE_JSON)
    parser.add_argument("--rescue-anchor-artifacts-json", default=DEFAULT_RESCUE_ANCHOR_ARTIFACTS_JSON)
    parser.add_argument("--rescue-three-bead-candidates-json", default=DEFAULT_RESCUE_THREE_BEAD_CANDIDATES_JSON)
    parser.add_argument("--rescue-three-bead-slice-json", default=DEFAULT_RESCUE_THREE_BEAD_SLICE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.hard_target_rescue_lane_json),
        maybe_load_json(args.rescue_anchor_artifacts_json),
        maybe_load_json(args.rescue_three_bead_candidates_json),
        maybe_load_json(args.rescue_three_bead_slice_json),
    )
    write_artifact(args.out_md, "Wet-Lab T. cruzi PDE Rescue Review Surface", payload)


if __name__ == "__main__":
    main()
