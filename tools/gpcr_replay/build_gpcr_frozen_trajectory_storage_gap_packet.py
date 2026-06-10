#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REPAIR_PACKET_JSON = "runs/gpcr_drd2_pose_generation_repair_packet_current.json"
DEFAULT_REPAIR_ROWS_CSV = "runs/gpcr_drd2_pose_generation_repair_packet_rows_current.csv"
DEFAULT_BACKMAPPING_JSON = "runs/gpcr_drd2_pseudo_allatom_repair_current.json"
DEFAULT_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_MOUNT_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_trajectory_storage_gap_packet_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_frozen_trajectory_storage_gap_packet_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_frozen_trajectory_storage_gap_packet_current.md"
DEFAULT_RESTORATION_JSON = "runs/gpcr_frozen_trajectory_restoration_path_packet_current.json"


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


def _run_root_from_npz(npz_path: str) -> str:
    path = Path(npz_path)
    parts = path.parts
    if "stage2_trajectory_frames" not in parts:
        return ""
    idx = parts.index("stage2_trajectory_frames")
    if idx < 1:
        return ""
    return str(Path(*parts[:idx]))


def _run_id_from_root(run_root: str) -> str:
    return Path(run_root).name if run_root else ""


def _inspect_run_root(run_root: str, mount_root: str) -> dict[str, Any]:
    root_path = Path(run_root)
    mount_path = Path(mount_root)
    rel = ""
    if root_path.is_absolute() and mount_path.is_absolute() and mount_path in root_path.parents:
        rel = str(root_path.relative_to(mount_path))
    elif root_path.is_absolute():
        rel = root_path.name
    else:
        rel = _text(run_root)

    resolved = root_path if root_path.is_absolute() else mount_path / rel
    stage2 = resolved / "stage2_trajectory_frames"
    stage3 = resolved / "stage3_delivery"
    run_children = sorted(p.name for p in resolved.iterdir()) if resolved.exists() and resolved.is_dir() else []
    return {
        "run_id": resolved.name,
        "run_root": str(resolved),
        "run_root_exists": resolved.exists(),
        "stage2_trajectory_frames_exists": stage2.is_dir(),
        "stage3_delivery_exists": stage3.exists(),
        "run_children": run_children,
        "storage_gap_status": (
            "stage2_missing_stage3_only"
            if resolved.exists() and stage3.exists() and not stage2.is_dir()
            else "run_root_missing"
            if not resolved.exists()
            else "stage2_present"
            if stage2.is_dir()
            else "unknown_layout"
        ),
    }


def _npz_row_status(npz_path: str) -> dict[str, Any]:
    path = Path(npz_path)
    return {
        "trajectory_npz": npz_path,
        "npz_exists": path.exists() if npz_path else False,
        "run_root": _run_root_from_npz(npz_path),
        "run_id": _run_id_from_root(_run_root_from_npz(npz_path)),
    }


def build_packet(
    *,
    repair_packet: dict[str, Any],
    repair_rows: list[dict[str, str]],
    backmapping_packet: dict[str, Any],
    readiness_packet: dict[str, Any],
    mount_root: str,
    restoration_path_packet: dict[str, Any] | None = None,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    positive = repair_packet.get("positive_row") if isinstance(repair_packet.get("positive_row"), dict) else {}
    positive_npz = _text(positive.get("trajectory_npz"))
    positive_npz_status = _npz_row_status(positive_npz)

    npz_paths = [_text(row.get("trajectory_npz")) for row in repair_rows if _text(row.get("trajectory_npz"))]
    unique_npz_paths = sorted(set(npz_paths))
    npz_status_rows = [_npz_row_status(path) for path in unique_npz_paths]
    npz_present_count = sum(1 for row in npz_status_rows if row["npz_exists"])
    npz_missing_count = len(npz_status_rows) - npz_present_count

    run_roots = sorted({row["run_root"] for row in npz_status_rows if row["run_root"]})
    run_inspections = [_inspect_run_root(run_root, mount_root) for run_root in run_roots]
    stage2_missing_runs = [row for row in run_inspections if row["storage_gap_status"] == "stage2_missing_stage3_only"]

    backmapping_summary = backmapping_packet.get("summary") if isinstance(backmapping_packet.get("summary"), dict) else {}
    repaired_row_count = _int(
        backmapping_summary.get("repaired_row_count") or backmapping_summary.get("reused_row_count")
    )
    backmapping_input_row_count = _int(backmapping_summary.get("input_row_count"))
    failed_reasons = Counter(
        _text(row.get("allatom_backmapping_reason"))
        for row in backmapping_packet.get("rows", []) or []
        if isinstance(row, dict) and _text(row.get("allatom_backmapping_reason"))
    )
    readiness_summary = readiness_packet.get("summary") if isinstance(readiness_packet.get("summary"), dict) else {}

    blockers: list[str] = []
    if not Path(mount_root).exists():
        blockers.append("heavy_run_mount_missing")
    if stage2_missing_runs:
        blockers.append("stage2_trajectory_frames_missing")
    if npz_missing_count > 0:
        blockers.append("repair_slice_source_npz_missing")
    if _int(backmapping_summary.get("repaired_row_count") or backmapping_summary.get("reused_row_count")) == 0 and backmapping_input_row_count > 0:
        blockers.append("drd2_pseudo_allatom_repair_blocked")
    if readiness_summary.get("claim_review_eligible") is False:
        blockers.append("guarded_100k_claim_review_blocked")

    repair_blocked = (
        "drd2_pseudo_allatom_repair_blocked" in blockers or "repair_slice_source_npz_missing" in blockers
    ) and repaired_row_count <= 0
    restoration_summary = (
        restoration_path_packet.get("summary")
        if isinstance((restoration_path_packet or {}).get("summary"), dict)
        else {}
    )
    summary = {
        "packet_type": "gpcr_frozen_trajectory_storage_gap_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "blocked_frozen_trajectory_storage_gap" if blockers else "ready_frozen_trajectory_storage",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "threshold_relaxation_allowed": False,
        "mount_root": mount_root,
        "mount_root_exists": Path(mount_root).exists(),
        "repair_slice_row_count": len(repair_rows),
        "repair_slice_unique_npz_count": len(unique_npz_paths),
        "repair_slice_npz_present_count": npz_present_count,
        "repair_slice_npz_missing_count": npz_missing_count,
        "positive_ligand_id": _text(positive.get("ligand_id")),
        "positive_trajectory_npz_exists": positive_npz_status["npz_exists"],
        "positive_trajectory_npz": positive_npz,
        "stage2_missing_run_count": len(stage2_missing_runs),
        "drd2_repair_blocked": repair_blocked,
        "backmapping_failed_row_count": _int(backmapping_summary.get("failed_row_count")),
        "backmapping_repaired_row_count": repaired_row_count,
        "backmapping_reuse_status": _text(backmapping_summary.get("status")),
        "dominant_backmapping_failure_reason": failed_reasons.most_common(1)[0][0] if failed_reasons else "",
        "guarded_100k_launch_eligible": readiness_summary.get("launch_eligible"),
        "guarded_100k_claim_review_eligible": readiness_summary.get("claim_review_eligible"),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "restoration_path_status": _text(restoration_summary.get("status")),
        "restoration_overlay_csv": _text(restoration_summary.get("overlay_csv")),
        "local_pseudo_readable_row_count": _int(restoration_summary.get("local_pseudo_readable_row_count")),
        "recommended_interim_path_id": _text(restoration_summary.get("recommended_interim_path_id")),
        "next_required_step": (
            restoration_summary.get("next_required_step")
            if restoration_summary.get("next_required_step") and repair_blocked
            else (
                "Restore or regenerate stage2 trajectory frames for the frozen GPCR 100k runs on the heavy-run mount, "
                "then rerun repair_gpcr_drd2_pseudo_allatom_backmapping.py and the DRD2 hard-decoy rebuild chain before "
                "another guarded 100k claim review."
                if repair_blocked
                else "Trajectory storage looks sufficient for the current DRD2 repair slice; continue shadow-only rescoring "
                "and claim-locked diagnostics."
            )
        ),
    }
    detail_rows: list[dict[str, Any]] = []
    for inspection in run_inspections:
        detail_rows.append({"record_type": "run_root", **inspection})
    for row in npz_status_rows[:20]:
        detail_rows.append({"record_type": "npz_path", **row})
    if positive_npz:
        detail_rows.insert(0, {"record_type": "positive_npz", **positive_npz_status, "ligand_id": summary["positive_ligand_id"]})
    return {
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "fake_pass_allowed": False,
            "full_100k_claim_review_allowed": False,
            "scorer_apply_allowed": False,
            "threshold_relaxation_allowed": False,
        },
        "summary": summary,
        "run_inspections": run_inspections,
        "npz_status_rows": npz_status_rows,
        "restoration_paths": list(restoration_path_packet.get("restoration_paths", []) or [])
        if isinstance(restoration_path_packet, dict)
        else [],
        "rows": detail_rows,
    }


def _int(value: Any) -> int:
    try:
        return int(float(str(value or "").strip()))
    except (TypeError, ValueError):
        return 0


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Trajectory Storage Gap Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- mount_root_exists: `{summary['mount_root_exists']}`",
        f"- repair_slice_npz_missing_count: `{summary['repair_slice_npz_missing_count']}` / `{summary['repair_slice_unique_npz_count']}`",
        f"- positive_trajectory_npz_exists: `{summary['positive_trajectory_npz_exists']}`",
        f"- stage2_missing_run_count: `{summary['stage2_missing_run_count']}`",
        f"- drd2_repair_blocked: `{summary['drd2_repair_blocked']}`",
        f"- dominant_backmapping_failure_reason: `{summary['dominant_backmapping_failure_reason']}`",
        f"- guarded_100k_launch_eligible: `{summary['guarded_100k_launch_eligible']}`",
        f"- guarded_100k_claim_review_eligible: `{summary['guarded_100k_claim_review_eligible']}`",
        f"- blockers: `{', '.join(summary['blockers']) or 'none'}`",
        "",
        "## Run Inspections",
        "",
        "| run_id | stage2 | stage3 | storage_gap_status |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload.get("run_inspections", []):
        lines.append(
            f"| `{row['run_id']}` | `{row['stage2_trajectory_frames_exists']}` | "
            f"`{row['stage3_delivery_exists']}` | `{row['storage_gap_status']}` |"
        )
    if summary.get("restoration_path_status"):
        lines.extend(
            [
                "",
                "## Restoration Path",
                "",
                f"- restoration_path_status: `{summary['restoration_path_status']}`",
                f"- local_pseudo_readable_row_count: `{summary.get('local_pseudo_readable_row_count', 0)}`",
                f"- restoration_overlay_csv: `{summary.get('restoration_overlay_csv', '')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- {summary['next_required_step']}",
            "",
            "## Claim Boundary",
            "",
            "- Diagnostic-only packet. Do not promote to claim/router/platform wording.",
            "",
        ]
    )
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose missing frozen GPCR trajectory storage blocking DRD2 repair.")
    parser.add_argument("--repair-packet-json", default=DEFAULT_REPAIR_PACKET_JSON)
    parser.add_argument("--repair-rows-csv", default=DEFAULT_REPAIR_ROWS_CSV)
    parser.add_argument("--backmapping-json", default=DEFAULT_BACKMAPPING_JSON)
    parser.add_argument("--readiness-json", default=DEFAULT_READINESS_JSON)
    parser.add_argument("--mount-root", default=DEFAULT_MOUNT_ROOT)
    parser.add_argument("--restoration-json", default=DEFAULT_RESTORATION_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    restoration_path = _read_json(args.restoration_json)
    payload = build_packet(
        repair_packet=_read_json(args.repair_packet_json),
        repair_rows=_read_csv(args.repair_rows_csv),
        backmapping_packet=_read_json(args.backmapping_json),
        readiness_packet=_read_json(args.readiness_json),
        mount_root=str(args.mount_root),
        restoration_path_packet=restoration_path if restoration_path else None,
    )
    _write_json(args.out_json, payload)
    _write_csv(args.out_csv, payload["rows"])
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
