#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPAIR_ROWS_CSV = "runs/gpcr_drd2_pose_generation_repair_packet_rows_current.csv"
DEFAULT_GAP_JSON = "runs/gpcr_frozen_trajectory_storage_gap_packet_current.json"
DEFAULT_MOUNT_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs"
DEFAULT_LOCAL_PSEUDO_ROOT = "runs/gpcr_drd2_pseudo_allatom_repair_current"
DEFAULT_FROZEN_RUN_ID = (
    "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1"
)
DEFAULT_OUT_JSON = "runs/gpcr_frozen_trajectory_restoration_path_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_frozen_trajectory_restoration_path_packet_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_frozen_trajectory_restoration_path_packet_current.md"
DEFAULT_OVERLAY_CSV = "runs/gpcr_drd2_pose_generation_repair_rows_local_pseudo_restoration_overlay_current.csv"
DEFAULT_DRD2_NATIVE_PDB = "runs/gpcr_frozen_candidate_profile_support_current/native_pdb/6cm4.pdb"
DEFAULT_REUSE_JSON = "runs/gpcr_drd2_pseudo_allatom_repair_local_reuse_current.json"
DEFAULT_REUSE_CSV = "runs/gpcr_drd2_pseudo_allatom_repair_rows_local_reuse_current.csv"
DEFAULT_REUSE_MD = "runs/gpcr_drd2_pseudo_allatom_repair_local_reuse_current.md"


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_csv(path_like: str | Path) -> list[dict[str, str]]:
    path = _resolve(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "row"


def _local_pseudo_npz_path(row: dict[str, str], local_root: Path) -> Path:
    return local_root / f"{_safe_name(_text(row.get('target')))}__{_safe_name(_text(row.get('ligand_id')))}.npz"


def _npz_readable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    try:
        import numpy as np

        with np.load(str(path), allow_pickle=False) as npz:
            frames = np.asarray(npz.get("ligand_frames"))
            return frames.ndim == 3 and frames.shape[0] > 0 and frames.shape[2] == 3
    except Exception:
        return False


def _mount_run_candidates(mount_root: Path, frozen_run_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    primary = mount_root / frozen_run_id
    candidates.append(
        {
            "run_id": frozen_run_id,
            "run_root": str(primary),
            "run_root_exists": primary.exists(),
            "stage2_trajectory_frames_exists": (primary / "stage2_trajectory_frames").is_dir(),
            "stage3_delivery_exists": (primary / "stage3_delivery").exists(),
            "stage2_npz_count": sum(1 for _ in (primary / "stage2_trajectory_frames").rglob("*.npz"))
            if (primary / "stage2_trajectory_frames").is_dir()
            else 0,
            "stage3_npz_count": sum(1 for _ in (primary / "stage3_delivery").rglob("*.npz"))
            if (primary / "stage3_delivery").exists()
            else 0,
            "candidate_role": "primary_frozen_gpcr_100k_r2",
        }
    )
    if mount_root.exists():
        for run_root in sorted(mount_root.glob("external_validation_*gpcr*100000*")):
            if run_root.name == frozen_run_id:
                continue
            candidates.append(
                {
                    "run_id": run_root.name,
                    "run_root": str(run_root),
                    "run_root_exists": True,
                    "stage2_trajectory_frames_exists": (run_root / "stage2_trajectory_frames").is_dir(),
                    "stage3_delivery_exists": (run_root / "stage3_delivery").exists(),
                    "stage2_npz_count": sum(1 for _ in (run_root / "stage2_trajectory_frames").rglob("*.npz"))
                    if (run_root / "stage2_trajectory_frames").is_dir()
                    else 0,
                    "stage3_npz_count": sum(1 for _ in (run_root / "stage3_delivery").rglob("*.npz"))
                    if (run_root / "stage3_delivery").exists()
                    else 0,
                    "candidate_role": "alternate_gpcr_100k_mount_run",
                }
            )
    return candidates


def _default_native_pdb_for_target(target: str, default_drd2_native_pdb: str) -> str:
    if _text(target) == "CHEMBL217_DRD2_HUMAN":
        return str(_resolve(default_drd2_native_pdb))
    return ""


def build_local_reuse_repair_rows(
    overlay_rows: list[dict[str, str]],
    *,
    default_drd2_native_pdb: str = DEFAULT_DRD2_NATIVE_PDB,
) -> list[dict[str, Any]]:
    reuse_rows: list[dict[str, Any]] = []
    for row in overlay_rows:
        local_npz = Path(_text(row.get("trajectory_npz")))
        native_pdb = _text(row.get("protein_structure_source_path")) or _default_native_pdb_for_target(
            _text(row.get("target")),
            default_drd2_native_pdb,
        )
        base = dict(row)
        base.update(
            {
                "source_trajectory_npz": _text(row.get("original_trajectory_npz")),
                "trajectory_npz": str(local_npz),
                "protein_structure_source_path": native_pdb,
                "restoration_path": "interim_local_pseudo_allatom_reuse",
                "allatom_backmapping_status": "not_started",
                "allatom_backmapping_reason": "",
                "allatom_backmapping_method": "",
            }
        )
        if not local_npz.exists():
            reuse_rows.append(
                {
                    **base,
                    "allatom_backmapping_status": "failed",
                    "allatom_backmapping_reason": "local_pseudo_npz_missing",
                }
            )
            continue
        if not _npz_readable(local_npz):
            reuse_rows.append(
                {
                    **base,
                    "allatom_backmapping_status": "failed",
                    "allatom_backmapping_reason": "local_pseudo_npz_unreadable",
                }
            )
            continue
        if not native_pdb or not Path(native_pdb).exists():
            reuse_rows.append(
                {
                    **base,
                    "allatom_backmapping_status": "failed",
                    "allatom_backmapping_reason": "native_pdb_missing",
                }
            )
            continue
        reuse_rows.append(
            {
                **base,
                "allatom_backmapping_status": "ok",
                "allatom_backmapping_reason": "local_pseudo_allatom_reused",
                "allatom_backmapping_method": "local_pseudo_allatom_reuse_no_rebackmap",
                "restoration_reuse_allowed": True,
            }
        )
    return reuse_rows


def build_local_reuse_repair_packet(
    reuse_rows: list[dict[str, Any]],
    *,
    overlay_csv: str,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    ok_rows = [row for row in reuse_rows if row.get("allatom_backmapping_status") == "ok"]
    positive_ok = [
        row for row in ok_rows if _text(row.get("ligand_id")) == "CHEMBL301265" or _text(row.get("is_positive")).lower() in {"1", "true", "yes"}
    ]
    summary = {
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pseudo_allatom_local_reuse_ready" if ok_rows and len(ok_rows) == len(reuse_rows) else "pseudo_allatom_local_reuse_partial",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "input_row_count": len(reuse_rows),
        "reused_row_count": len(ok_rows),
        "failed_row_count": len(reuse_rows) - len(ok_rows),
        "positive_reused_count": len(positive_ok),
        "overlay_csv": overlay_csv,
        "next_action": "rebuild_atom_window_cache_on_reused_rows_then_rescore_shadow_only",
        "next_required_step": (
            "Rebuild the atom-window cache and cationic-center geometry cache on the reused local pseudo-allatom "
            "trajectories, then rerun the DRD2 hard-decoy slice diagnostics. Shadow-only; do not promote claims."
        ),
    }
    return {
        "packet_type": "gpcr_drd2_pseudo_allatom_local_reuse_repair",
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "threshold_relaxation_allowed": False,
        },
        "rows": reuse_rows,
    }


def build_overlay_rows(repair_rows: list[dict[str, str]], local_root: Path) -> list[dict[str, str]]:
    overlay_rows: list[dict[str, str]] = []
    for row in repair_rows:
        local_npz = _local_pseudo_npz_path(row, local_root)
        overlay = dict(row)
        overlay["original_trajectory_npz"] = _text(row.get("trajectory_npz"))
        overlay["trajectory_npz"] = str(local_npz)
        overlay["restoration_path"] = "interim_local_pseudo_allatom"
        overlay["restoration_source_exists"] = str(local_npz.exists())
        overlay["restoration_source_readable"] = str(_npz_readable(local_npz))
        overlay_rows.append(overlay)
    return overlay_rows


def build_packet(
    *,
    repair_rows: list[dict[str, str]],
    gap_packet: dict[str, Any],
    mount_root: str,
    local_pseudo_root: str,
    frozen_run_id: str,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    local_root = _resolve(local_pseudo_root)
    mount_path = Path(mount_root)
    gap_summary = gap_packet.get("summary") if isinstance(gap_packet.get("summary"), dict) else {}
    mount_candidates = _mount_run_candidates(mount_path, frozen_run_id)
    stage2_present_runs = [row for row in mount_candidates if row["stage2_trajectory_frames_exists"]]
    overlay_rows = build_overlay_rows(repair_rows, local_root)
    local_mapped_count = sum(1 for row in overlay_rows if row["restoration_source_exists"] == "True")
    local_readable_count = sum(1 for row in overlay_rows if row["restoration_source_readable"] == "True")
    positive_row = next(
        (row for row in overlay_rows if _text(row.get("ligand_id")) == "CHEMBL301265"),
        overlay_rows[0] if overlay_rows else {},
    )
    positive_readable = positive_row.get("restoration_source_readable") == "True"

    full_mount_command = (
        "python3 tools/run_external_validation_blind_sets.py "
        f"--tag frozen_gpcr_stage2_restore --sets gpcr_core_full --resume "
        f"# rerun the frozen GPCR 100k set so stage2_trajectory_frames repopulates under {mount_root}/{frozen_run_id}"
    )
    shadow_chain_command = (
        "python3 tools/gpcr_replay/build_gpcr_frozen_trajectory_restoration_path_packet.py && "
        "python3 tools/gpcr_replay/build_gpcr_atom_window_anchor_feature_cache.py "
        "--input-csv runs/gpcr_drd2_pseudo_allatom_repair_rows_local_reuse_current.csv "
        "--target CHEMBL217_DRD2_HUMAN --top-n 65 "
        "--out-csv runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.csv "
        "--out-json runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.json "
        "--out-md runs/gpcr_atom_window_anchor_feature_cache_drd2_pseudo_allatom_repair_current.md"
    )

    restoration_paths = [
        {
            "path_id": "full_mount_stage2_regeneration",
            "path_kind": "authoritative_mount_restore",
            "status": "required_for_full_100k_claim_review",
            "claim_promotion_allowed": False,
            "mount_stage2_present_run_count": len(stage2_present_runs),
            "recommended_command": full_mount_command,
            "notes": (
                "Mount inspection shows stage3-only layout for the frozen GPCR 100k run. "
                "Regenerate stage2 trajectory frames on the heavy-run mount with resume enabled."
            ),
        },
        {
            "path_id": "interim_local_pseudo_allatom_overlay",
            "path_kind": "shadow_only_local_reuse",
            "status": "ready_for_drd2_repair_slice_shadow_diagnostics" if local_readable_count == len(repair_rows) and repair_rows else "blocked_local_pseudo_unreadable",
            "claim_promotion_allowed": False,
            "local_pseudo_root": str(local_root),
            "mapped_row_count": local_mapped_count,
            "readable_row_count": local_readable_count,
            "overlay_csv": str(DEFAULT_OVERLAY_CSV),
            "recommended_command": shadow_chain_command,
            "notes": (
                "Reuse previously generated pseudo-allatom NPZ under runs/gpcr_drd2_pseudo_allatom_repair_current "
                "for the 65-row DRD2 repair slice only. Shadow diagnostics only; do not promote claims."
            ),
        },
    ]

    blockers: list[str] = []
    if gap_summary.get("drd2_repair_blocked") is True:
        blockers.append("mount_source_npz_missing_for_default_repair_rows")
    if local_readable_count < len(repair_rows):
        blockers.append("local_pseudo_allatom_overlay_incomplete")
    if not stage2_present_runs:
        blockers.append("mount_stage2_absent_for_all_gpcr_100k_runs")

    summary = {
        "packet_type": "gpcr_frozen_trajectory_restoration_path_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": (
            "restoration_path_ready_shadow_overlay"
            if local_readable_count == len(repair_rows) and repair_rows and positive_readable
            else "restoration_path_investigated_blocked"
        ),
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "mount_root": mount_root,
        "mount_root_exists": mount_path.exists(),
        "frozen_run_id": frozen_run_id,
        "repair_slice_row_count": len(repair_rows),
        "repair_slice_rows_with_mount_npz": sum(1 for row in repair_rows if _text(row.get("trajectory_npz"))),
        "local_pseudo_mapped_row_count": local_mapped_count,
        "local_pseudo_readable_row_count": local_readable_count,
        "positive_ligand_id": _text(positive_row.get("ligand_id")),
        "positive_local_pseudo_readable": positive_readable,
        "mount_stage2_present_run_count": len(stage2_present_runs),
        "recommended_primary_path_id": "full_mount_stage2_regeneration",
        "recommended_interim_path_id": "interim_local_pseudo_allatom_overlay",
        "overlay_csv": str(DEFAULT_OVERLAY_CSV),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "next_required_step": (
            "Use the local pseudo-allatom overlay CSV for shadow-only DRD2 repair/cache rebuild while scheduling "
            "a resumed frozen GPCR 100k stage2 regeneration on the heavy-run mount before any claim review."
            if local_readable_count == len(repair_rows) and repair_rows
            else "Investigate missing local pseudo-allatom NPZ or rerun stage2 regeneration on the mount."
        ),
    }
    detail_rows: list[dict[str, Any]] = []
    for path in restoration_paths:
        detail_rows.append({"record_type": "restoration_path", **path})
    for candidate in mount_candidates:
        detail_rows.append({"record_type": "mount_run_candidate", **candidate})
    for row in overlay_rows[:20]:
        detail_rows.append(
            {
                "record_type": "overlay_row",
                "target": _text(row.get("target")),
                "ligand_id": _text(row.get("ligand_id")),
                "original_trajectory_npz": _text(row.get("original_trajectory_npz")),
                "trajectory_npz": _text(row.get("trajectory_npz")),
                "restoration_source_readable": row.get("restoration_source_readable"),
            }
        )
    return {
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "fake_pass_allowed": False,
            "full_100k_claim_review_allowed": False,
            "scorer_apply_allowed": False,
            "threshold_relaxation_allowed": False,
        },
        "summary": summary,
        "restoration_paths": restoration_paths,
        "mount_run_candidates": mount_candidates,
        "overlay_rows": overlay_rows,
        "rows": detail_rows,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Trajectory Restoration Path Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- repair_slice_row_count: `{summary['repair_slice_row_count']}`",
        f"- local_pseudo_readable_row_count: `{summary['local_pseudo_readable_row_count']}`",
        f"- positive_local_pseudo_readable: `{summary['positive_local_pseudo_readable']}`",
        f"- mount_stage2_present_run_count: `{summary['mount_stage2_present_run_count']}`",
        f"- overlay_csv: `{summary['overlay_csv']}`",
        f"- blockers: `{', '.join(summary['blockers']) or 'none'}`",
        "",
        "## Restoration Paths",
        "",
        "| path_id | path_kind | status | mapped/readable |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("restoration_paths", []):
        mapped = row.get("mapped_row_count", "")
        readable = row.get("readable_row_count", "")
        metric = f"{mapped}/{readable}" if mapped != "" else ""
        lines.append(
            f"| `{row['path_id']}` | `{row['path_kind']}` | `{row['status']}` | `{metric}` |"
        )
    lines.extend(
        [
            "",
            "## Recommended Commands",
            "",
        ]
    )
    for row in payload.get("restoration_paths", []):
        lines.append(f"- `{row['path_id']}`: `{row.get('recommended_command', '')}`")
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
            "## Claim Boundary",
            "",
            "- Restoration-path packet only. Interim local pseudo-allatom reuse is shadow-only.",
            "",
        ]
    )
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Investigate frozen GPCR trajectory restoration paths and emit local overlay CSV.")
    parser.add_argument("--repair-rows-csv", default=DEFAULT_REPAIR_ROWS_CSV)
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--mount-root", default=DEFAULT_MOUNT_ROOT)
    parser.add_argument("--local-pseudo-root", default=DEFAULT_LOCAL_PSEUDO_ROOT)
    parser.add_argument("--frozen-run-id", default=DEFAULT_FROZEN_RUN_ID)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--overlay-csv", default=DEFAULT_OVERLAY_CSV)
    parser.add_argument("--drd2-native-pdb", default=DEFAULT_DRD2_NATIVE_PDB)
    parser.add_argument("--reuse-json", default=DEFAULT_REUSE_JSON)
    parser.add_argument("--reuse-csv", default=DEFAULT_REUSE_CSV)
    parser.add_argument("--reuse-md", default=DEFAULT_REUSE_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repair_rows = _read_csv(args.repair_rows_csv)
    payload = build_packet(
        repair_rows=repair_rows,
        gap_packet=_read_json(args.gap_json),
        mount_root=str(args.mount_root),
        local_pseudo_root=str(args.local_pseudo_root),
        frozen_run_id=str(args.frozen_run_id),
    )
    reuse_rows = build_local_reuse_repair_rows(
        payload["overlay_rows"],
        default_drd2_native_pdb=str(args.drd2_native_pdb),
    )
    reuse_payload = build_local_reuse_repair_packet(
        reuse_rows,
        overlay_csv=str(args.overlay_csv),
    )
    payload["summary"]["local_reuse_status"] = reuse_payload["summary"]["status"]
    payload["summary"]["local_reuse_row_count"] = reuse_payload["summary"]["reused_row_count"]
    payload["summary"]["local_reuse_csv"] = str(args.reuse_csv)
    payload["local_reuse_summary"] = reuse_payload["summary"]

    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_csv(args.overlay_csv, payload["overlay_rows"])
    _write_markdown(args.out_md, payload)
    _write_json(args.reuse_json, reuse_payload)
    _write_csv(args.reuse_csv, reuse_rows)
    _resolve(args.reuse_md).write_text(
        "\n".join(
            [
                "# GPCR DRD2 Pseudo-Allatom Local Reuse Repair",
                "",
                f"- status: `{reuse_payload['summary']['status']}`",
                f"- reused_row_count: `{reuse_payload['summary']['reused_row_count']}` / `{reuse_payload['summary']['input_row_count']}`",
                f"- positive_reused_count: `{reuse_payload['summary']['positive_reused_count']}`",
                f"- overlay_csv: `{reuse_payload['summary']['overlay_csv']}`",
                "",
                "## Next Step",
                "",
                f"- {reuse_payload['summary']['next_required_step']}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
