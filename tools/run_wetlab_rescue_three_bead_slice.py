#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.wetlab_broad_screen_watch_utils import slug
from tools.wetlab_target_render_utils import load_json, write_artifact

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES_JSON = "runs/wetlab_rescue_three_bead_candidates_current.json"
DEFAULT_RESCUE_LANE_JSON = "runs/wetlab_hard_target_rescue_lane_current.json"
DEFAULT_RESCUE_ANCHOR_JSON = "runs/wetlab_rescue_anchor_artifacts_current.json"
DEFAULT_OUT_MD = "runs/wetlab_rescue_three_bead_slice_current.md"
DEFAULT_TOP_K = 8


def _text(value: Any) -> str:
    return "" if value in {None, ""} else str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in {"", None}:
            return default
        return int(value)
    except Exception:
        return default


def _under_root(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def _base_prefix_for_command_kind(command_kind: str) -> str:
    kind = _text(command_kind)
    if kind == "throughput_preflight_tuned_gate51":
        return "throughput_run_gate51"
    if kind == "throughput_preflight_tuned_gate45":
        return "throughput_run_gate45"
    if kind == "throughput_preflight_hard_target_rescue":
        return "throughput_run_gate51"
    if kind.startswith("throughput_preflight_"):
        suffix = kind.removeprefix("throughput_preflight_").strip()
        if suffix:
            return f"throughput_run_{suffix}"
    return "throughput_run"


def _resolve_focus(
    candidates_payload: dict[str, Any],
    rescue_lane_payload: dict[str, Any],
    *,
    target_id: str = "",
    shard_id: str = "",
) -> tuple[str, str]:
    candidate_summary = dict(candidates_payload.get("summary", {}) or {})
    rescue_summary = dict(rescue_lane_payload.get("summary", {}) or {})
    resolved_target = (
        _text(target_id)
        or _text(candidate_summary.get("target_id"))
        or _text(candidate_summary.get("focus_target_id"))
        or _text(rescue_summary.get("target_id"))
        or _text(rescue_summary.get("focus_target_id"))
    )
    resolved_shard = (
        _text(shard_id)
        or _text(candidate_summary.get("shard_id"))
        or _text(candidate_summary.get("focus_shard_id"))
        or _text(rescue_summary.get("shard_id"))
        or _text(rescue_summary.get("focus_shard_id"))
    )
    if not resolved_target or not resolved_shard:
        raise SystemExit("rescue three-bead slice has no focus target/shard")
    return resolved_target, resolved_shard


def run(
    *,
    candidates_json: str,
    rescue_lane_json: str,
    rescue_anchor_json: str,
    target_id: str,
    shard_id: str,
    top_k: int,
    python_bin: str,
    execute: bool,
    out_md: str,
) -> dict[str, Any]:
    candidates_payload = load_json(candidates_json)
    rescue_lane_payload = load_json(rescue_lane_json)
    rescue_anchor_payload = load_json(rescue_anchor_json)

    resolved_target, resolved_shard = _resolve_focus(
        candidates_payload,
        rescue_lane_payload,
        target_id=target_id,
        shard_id=shard_id,
    )
    candidate_rows = [
        dict(row or {})
        for row in candidates_payload.get("rows", []) or []
        if _text((row or {}).get("target_id")) == resolved_target
        and _text((row or {}).get("shard_id")) == resolved_shard
    ]
    candidate_rows.sort(
        key=lambda row: (
            _safe_int(row.get("priority_rank"), 0),
            _text(row.get("ligand_id")),
        )
    )
    requested_top_k = max(1, int(top_k))
    slice_rows = candidate_rows[:requested_top_k]
    if not slice_rows:
        raise SystemExit(f"no 3-bead rescue candidates found for {resolved_target} {resolved_shard}")

    rescue_summary = dict(rescue_lane_payload.get("summary", {}) or {})
    anchor_summary = dict(rescue_anchor_payload.get("summary", {}) or {})
    target_slug = slug(resolved_target)
    actual_top_k = len(slice_rows)
    selected_command_kind = "three_bead_rescue_local_refine"
    base_command_kind = _text(
        rescue_summary.get("rescue_base_command_kind")
        or rescue_summary.get("focus_rescue_base_command_kind")
    )
    base_prefix = _base_prefix_for_command_kind(base_command_kind)

    slice_dir = _under_root(
        f"runs/wetlab_rescue_three_bead/{target_slug}/{resolved_shard}/top_{requested_top_k}"
    )
    slice_dir.mkdir(parents=True, exist_ok=True)
    manifest_csv = slice_dir / "three_bead_slice_manifest.csv"
    queue_subset_csv = slice_dir / "three_bead_slice_queue.csv"
    state_json = slice_dir / "three_bead_slice_state.json"
    scores_csv = slice_dir / "three_bead_slice_scores.csv"
    summary_json = slice_dir / "three_bead_slice_summary.json"
    summary_md = slice_dir / "three_bead_slice_summary.md"
    scoring_log = slice_dir / "three_bead_slice_scoring.log"
    out_dir = slice_dir / "three_bead_delivery"

    stage1_queue_csv = _under_root(
        f"runs/wetlab_broad_screen_throughput/{target_slug}/{resolved_shard}/{base_prefix}_stage1_queue.csv"
    )
    stage2_manifest_csv = _under_root(
        f"runs/wetlab_broad_screen_throughput/{target_slug}/{resolved_shard}/{base_prefix}_stage2_traj_manifest.csv"
    )
    trajectory_root = _under_root(
        f"runs/wetlab_broad_screen_throughput/{target_slug}/{resolved_shard}/{base_prefix}_stage2_traj_frames"
    )
    if not stage1_queue_csv.exists():
        raise SystemExit(f"missing stage1 queue for 3-bead rescue slice: {stage1_queue_csv}")
    if not stage2_manifest_csv.exists():
        raise SystemExit(f"missing stage2 manifest for 3-bead rescue slice: {stage2_manifest_csv}")
    if not trajectory_root.exists():
        raise SystemExit(f"missing stage2 trajectory root for 3-bead rescue slice: {trajectory_root}")

    manifest_rows: list[dict[str, Any]] = []
    selected_ligand_ids: set[str] = set()
    for row in slice_rows:
        ligand_id = _text(row.get("ligand_id"))
        selected_ligand_ids.add(ligand_id)
        manifest_rows.append(
            {
                "target_id": resolved_target,
                "target_slug": target_slug,
                "shard_id": resolved_shard,
                "priority_rank": _safe_int(row.get("priority_rank"), 0),
                "ligand_id": ligand_id,
                "binding_energy_proxy": row.get("binding_energy_proxy", ""),
                "stability_score": row.get("stability_score", ""),
                "mean_min_distance_A": row.get("mean_min_distance_A", ""),
                "selected_command_kind": selected_command_kind,
                "selected_threshold_A": 2.5,
                "rescue_target_native_csv": _text(anchor_summary.get("rescue_target_native_csv")),
                "rescue_target_pocket_csv": _text(anchor_summary.get("rescue_target_pocket_csv")),
                "rescue_target_ligand_csv": _text(anchor_summary.get("rescue_target_ligand_csv")),
            }
        )
    write_csv_rows(manifest_csv, manifest_rows)

    queue_subset_rows: list[dict[str, Any]] = []
    with stage1_queue_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if _text(row.get("ligand_id")) in selected_ligand_ids:
                queue_subset_rows.append(dict(row))
    if not queue_subset_rows:
        raise SystemExit(f"no queue rows matched rescue slice ligands for {resolved_target} {resolved_shard}")
    write_csv_rows(queue_subset_csv, queue_subset_rows)

    execution_mode = "controller_manifest_only"
    scoring_status = "not_executed"
    scoring_returncode: int | None = None
    if execute:
        scoring_cmd = [
            python_bin,
            str(ROOT / "tools" / "run_ligand_backmapping_scoring.py"),
            "--queue-csv",
            str(queue_subset_csv),
            "--stage2-manifest-csv",
            str(stage2_manifest_csv),
            "--trajectory-root",
            str(trajectory_root),
            "--min-frames",
            "100",
            "--max-jobs",
            str(actual_top_k),
            "--ligand-model",
            "3bead_implicit_hbond",
            "--out-dir",
            str(out_dir),
            "--out-scores-csv",
            str(scores_csv),
            "--out-summary-json",
            str(summary_json),
            "--out-summary-md",
            str(summary_md),
            "--workers",
            "0",
            "--parallel-threshold",
            "2",
            "--score-only",
            "--make-bundle-zip",
            "--no-allow-missing-trajectory",
        ]
        with scoring_log.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.run(
                scoring_cmd,
                cwd=ROOT,
                text=True,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        scoring_returncode = int(proc.returncode)
        execution_mode = "local_refine_scoring_executed"
        if summary_json.exists():
            scoring_payload = load_json(str(summary_json))
            scoring_summary = dict(scoring_payload.get("summary", {}) or {})
            scoring_pass = bool(
                scoring_summary.get("pass", False)
                or scoring_payload.get("pass", False)
                or proc.returncode == 0
            )
            scoring_status = "pass" if scoring_pass else "error"
        else:
            scoring_status = "error"

    payload = {
        "summary": {
            "status": "wetlab_rescue_three_bead_slice_ready",
            "target_id": resolved_target,
            "shard_id": resolved_shard,
            "selected_command_kind": selected_command_kind,
            "selected_threshold_A": 2.5,
            "requested_top_k": requested_top_k,
            "slice_candidate_count": actual_top_k,
            "source_candidate_count": len(candidate_rows),
            "focus_ligand_id": _text(manifest_rows[0].get("ligand_id")),
            "slice_manifest_csv": str(manifest_csv),
            "slice_queue_csv": str(queue_subset_csv),
            "slice_state_json": str(state_json),
            "stage2_manifest_csv": str(stage2_manifest_csv),
            "trajectory_root": str(trajectory_root),
            "three_bead_scores_csv": str(scores_csv),
            "three_bead_summary_json": str(summary_json),
            "three_bead_summary_md": str(summary_md),
            "three_bead_scoring_log": str(scoring_log),
            "rescue_target_native_csv": _text(anchor_summary.get("rescue_target_native_csv")),
            "rescue_target_pocket_csv": _text(anchor_summary.get("rescue_target_pocket_csv")),
            "rescue_target_ligand_csv": _text(anchor_summary.get("rescue_target_ligand_csv")),
            "attach_rescue_target_native_csv": bool(anchor_summary.get("attach_rescue_target_native_csv", False)),
            "attach_rescue_target_pocket_csv": bool(anchor_summary.get("attach_rescue_target_pocket_csv", False)),
            "attach_rescue_target_ligand_csv": bool(anchor_summary.get("attach_rescue_target_ligand_csv", False)),
            "execution_mode": execution_mode,
            "scoring_status": scoring_status,
            "scoring_returncode": scoring_returncode,
            "next_required_step": (
                f"Review the top-{actual_top_k} 3-bead rescue slice results for {resolved_target} {resolved_shard} "
                f"before reopening the rescue lane."
            ),
        },
        "structured": {
            "rescue_three_bead_candidates_artifact": "runs/wetlab_rescue_three_bead_candidates_current.md",
            "hard_target_rescue_lane_artifact": "runs/wetlab_hard_target_rescue_lane_current.md",
            "rescue_anchor_artifact": "runs/wetlab_rescue_anchor_artifacts_current.md",
        },
        "rows": manifest_rows,
    }
    state_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_artifact(out_md, "Wet-Lab Rescue Three-Bead Slice", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch a small top-N 3-bead rescue slice from the current hard-target rescue candidates."
    )
    parser.add_argument("--candidates-json", default=DEFAULT_CANDIDATES_JSON)
    parser.add_argument("--rescue-lane-json", default=DEFAULT_RESCUE_LANE_JSON)
    parser.add_argument("--rescue-anchor-json", default=DEFAULT_RESCUE_ANCHOR_JSON)
    parser.add_argument("--target-id", default="")
    parser.add_argument("--shard-id", default="")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--python-bin", default=sys.executable or "python3")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        candidates_json=args.candidates_json,
        rescue_lane_json=args.rescue_lane_json,
        rescue_anchor_json=args.rescue_anchor_json,
        target_id=args.target_id,
        shard_id=args.shard_id,
        top_k=max(1, int(args.top_k)),
        python_bin=str(args.python_bin),
        execute=bool(args.execute),
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
