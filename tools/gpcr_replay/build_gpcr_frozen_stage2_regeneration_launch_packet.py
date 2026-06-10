#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MOUNT_ROOT = "/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs"
DEFAULT_FROZEN_RUN_ID = (
    "external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_p0_n100000_r1"
)
DEFAULT_PROFILE_JSON = (
    "runs/gpcr_scaleup_100k_family_balanced_rescore_candidate_current/profiles/profile_family-balanced-frozen-r1.json"
)
DEFAULT_OUT_PREFIX = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full"
)
DEFAULT_RESTORATION_JSON = "runs/gpcr_frozen_trajectory_restoration_path_packet_current.json"
DEFAULT_REPLAY_JSON = "runs/gpcr_drd2_valid_anchor_discriminator_slice_replay_packet_current.json"
DEFAULT_GAP_JSON = "runs/gpcr_frozen_trajectory_storage_gap_packet_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_stage2_regeneration_launch_packet_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_stage2_regeneration_launch_packet_current.md"


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


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _inspect_mount_run(mount_root: Path, frozen_run_id: str) -> dict[str, Any]:
    run_root = mount_root / frozen_run_id
    stage2_dir = run_root / "stage2_trajectory_frames"
    stage3_dir = run_root / "stage3_delivery"
    return {
        "run_id": frozen_run_id,
        "run_root": str(run_root),
        "run_root_exists": run_root.exists(),
        "stage2_trajectory_frames_exists": stage2_dir.is_dir(),
        "stage3_delivery_exists": stage3_dir.exists(),
        "stage2_npz_count": sum(1 for _ in stage2_dir.rglob("*.npz")) if stage2_dir.is_dir() else 0,
        "stage3_npz_count": sum(1 for _ in stage3_dir.rglob("*.npz")) if stage3_dir.exists() else 0,
    }


def _resume_command(
    *,
    profile_json: str,
    out_prefix: str,
    date_tag: str = "2026-05-03_family_balanced_frozen_r2-gpcr-core-full-family-balanced-frozen-r1",
) -> str:
    return (
        "python3 tools/run_ligand_stress_validation.py "
        f"--profile-json {profile_json} "
        "--ligand-sizes 100000 --repeats 1 "
        f"--date-tag {date_tag} "
        f"--out-prefix {out_prefix} "
        "--resume --resume-retry-failed-runs --fail-fast "
        "--enforce-data-contract --data-contract-json config/ligand_data_contract_v1.json"
    )


def build_packet(
    *,
    mount_root: str | Path = DEFAULT_MOUNT_ROOT,
    frozen_run_id: str = DEFAULT_FROZEN_RUN_ID,
    profile_json: str | Path = DEFAULT_PROFILE_JSON,
    out_prefix: str | Path = DEFAULT_OUT_PREFIX,
    restoration_json: str | Path = DEFAULT_RESTORATION_JSON,
    replay_json: str | Path = DEFAULT_REPLAY_JSON,
    gap_json: str | Path = DEFAULT_GAP_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    mount_path = _resolve(mount_root)
    profile_path = _resolve(profile_json)
    out_prefix_path = _resolve(out_prefix)
    mount_inspection = _inspect_mount_run(mount_path, frozen_run_id)
    restoration_summary = _read_json(restoration_json).get("summary", {})
    replay_summary = _read_json(replay_json).get("summary", {})
    gap_summary = _read_json(gap_json).get("summary", {})
    local_stage2_summary = _read_json(f"{out_prefix_path}_p0_n100000_r1_stage2_traj_summary.json")
    resume_cmd = _resume_command(
        profile_json=str(profile_path.relative_to(ROOT) if profile_path.is_relative_to(ROOT) else profile_path),
        out_prefix=str(out_prefix_path.relative_to(ROOT) if out_prefix_path.is_relative_to(ROOT) else out_prefix_path),
    )

    blockers: list[str] = []
    if not mount_path.exists():
        blockers.append("mount_root_missing")
    if not profile_path.exists():
        blockers.append("profile_json_missing")
    if mount_inspection["stage2_trajectory_frames_exists"] and mount_inspection["stage2_npz_count"] > 0:
        blockers.append("mount_stage2_already_present_no_regen_needed")
    elif not mount_inspection["run_root_exists"]:
        blockers.append("mount_run_root_missing")
    elif not mount_inspection["stage3_delivery_exists"]:
        blockers.append("mount_stage3_delivery_missing")
    if gap_summary.get("drd2_repair_blocked") is True:
        blockers.append("drd2_repair_slice_still_blocked")
    if replay_summary.get("status") not in {
        "selected_slice_shadow_green_claim_locked",
        "blocked_internal_review",
        "blocked_penalty_envelope_insufficient",
    } and not replay_summary:
        blockers.append("valid_anchor_discriminator_slice_replay_packet_missing")

    launch_allowed = not any(
        item in blockers
        for item in (
            "mount_root_missing",
            "profile_json_missing",
            "mount_run_root_missing",
            "mount_stage3_delivery_missing",
        )
    ) and "mount_stage2_already_present_no_regen_needed" not in blockers

    summary = {
        "packet_type": "gpcr_frozen_stage2_regeneration_launch_packet",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "stage2_regeneration_launch_ready" if launch_allowed else "stage2_regeneration_launch_blocked",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "launch_allowed": launch_allowed,
        "mount_root": str(mount_path),
        "mount_root_exists": mount_path.exists(),
        "frozen_run_id": frozen_run_id,
        "profile_json": str(profile_path),
        "profile_json_exists": profile_path.exists(),
        "out_prefix": str(out_prefix_path),
        "local_stage2_summary_present": bool(local_stage2_summary),
        "mount_stage2_npz_count": mount_inspection["stage2_npz_count"],
        "mount_stage3_npz_count": mount_inspection["stage3_npz_count"],
        "restoration_status": _text(restoration_summary.get("status")),
        "replay_status": _text(replay_summary.get("status")),
        "gap_status": _text(gap_summary.get("status")),
        "recommended_resume_command": resume_cmd,
        "blockers": blockers,
        "next_required_step": (
            "Launch the resume command on a GPU worker with heavy-run mount access. Stage2 trajectory frames "
            "must repopulate under the frozen GPCR 100k run root before any guarded full-100k claim review. "
            "This remains infrastructure recovery, not claim authorization."
            if launch_allowed
            else "Resolve launch blockers, rebuild the repaired-slice replay packet if needed, then regenerate "
            "mount stage2 trajectory frames with resume enabled."
        ),
    }
    return {
        "summary": summary,
        "claim_boundary": {
            "claim_promotion_allowed": False,
            "fake_pass_allowed": False,
            "full_100k_claim_review_allowed": False,
            "launch_is_not_claim_authorization": True,
            "scorer_apply_allowed": False,
        },
        "mount_inspection": mount_inspection,
        "restoration_summary": restoration_summary,
        "replay_summary": replay_summary,
        "gap_summary": gap_summary,
    }


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Stage2 Regeneration Launch Packet",
        "",
        f"- status: `{summary['status']}`",
        f"- launch_allowed: `{str(summary['launch_allowed']).lower()}`",
        f"- mount_stage2_npz_count: `{summary['mount_stage2_npz_count']}`",
        f"- mount_stage3_npz_count: `{summary['mount_stage3_npz_count']}`",
        f"- replay_status: `{summary['replay_status']}`",
        "",
        "## Resume Command",
        "",
        "```bash",
        summary["recommended_resume_command"],
        "```",
        "",
        "## Next Step",
        "",
        f"- {summary['next_required_step']}",
        "",
    ]
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mount stage2 regeneration launch packet for frozen GPCR 100k.")
    parser.add_argument("--mount-root", default=DEFAULT_MOUNT_ROOT)
    parser.add_argument("--frozen-run-id", default=DEFAULT_FROZEN_RUN_ID)
    parser.add_argument("--profile-json", default=DEFAULT_PROFILE_JSON)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--restoration-json", default=DEFAULT_RESTORATION_JSON)
    parser.add_argument("--replay-json", default=DEFAULT_REPLAY_JSON)
    parser.add_argument("--gap-json", default=DEFAULT_GAP_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        mount_root=args.mount_root,
        frozen_run_id=args.frozen_run_id,
        profile_json=args.profile_json,
        out_prefix=args.out_prefix,
        restoration_json=args.restoration_json,
        replay_json=args.replay_json,
        gap_json=args.gap_json,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
