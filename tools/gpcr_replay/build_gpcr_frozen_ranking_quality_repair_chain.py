#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_STAGE3_SCORES_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage3_scores.csv"
)
DEFAULT_STAGE5_ROWS_CSV = (
    "runs/external_validation_2026-05-03_family_balanced_frozen_r2_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage5_ranking_rows.csv"
)
DEFAULT_V16_SCORES_CSV = (
    "runs/gpcr_false_support_discriminator_v16_frozen_adaptive_truebase_full_shadow_replay_scores_current.csv"
)
DEFAULT_V16_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_V16_DISCRIMINATOR_REFRESH_SCORES_CSV = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_v16_shadow_replay_scores_current.csv"
)
DEFAULT_V16_DISCRIMINATOR_REFRESH_GAP_JSON = (
    "runs/gpcr_frozen_ranking_quality_port_full_nonadrb2_v16_gap_packet_current.json"
)
DEFAULT_HTR2A_REPAIR_JSON = "runs/gpcr_htr2a_anchor_support_repair_packet_current.json"
DEFAULT_HTR2A_PROBE_JSON = "runs/gpcr_htr2a_atom_typed_topology_probe_current.json"
DEFAULT_HTR2A_LIFE_JSON = "runs/gpcr_htr2a_life_science_evidence_packet_current.json"
DEFAULT_HTR2A_REPLAY_JSON = "runs/gpcr_htr2a_topology_support_shadow_replay_summary_current.json"
DEFAULT_OPRM1_LIFE_JSON = "runs/gpcr_oprm1_life_science_evidence_packet_current.json"
DEFAULT_OPRM1_REPLAY_JSON = "runs/gpcr_oprm1_topology_pose_shadow_replay_summary_current.json"
DEFAULT_SHADOW_REVIEW_JSON = "runs/gpcr_guarded_shadow_claim_review_current.json"
DEFAULT_GUARDED_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_CI_LOW_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_OPERATIONAL_RANKING_SUMMARY_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
)
DEFAULT_A1_QUEUE_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_ranking_quality_repair_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_ranking_quality_repair_chain_current.md"


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


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _lane(name: str, path_like: str | Path) -> dict[str, Any]:
    payload = _read_json(path_like)
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "lane": name,
        "status": _text(summary.get("status")),
        "artifact": str(_resolve(path_like)),
        "summary": summary,
    }


def build_packet(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    stage5_rows_csv: str | Path = DEFAULT_STAGE5_ROWS_CSV,
    v16_scores_csv: str | Path = DEFAULT_V16_SCORES_CSV,
    v16_gap_json: str | Path = DEFAULT_V16_GAP_JSON,
    skip_htr2a: bool = False,
    skip_oprm1: bool = False,
    skip_guarded: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    lanes: dict[str, Any] = {}

    if not skip_htr2a:
        _run(
            [
                sys.executable,
                "tools/build_gpcr_htr2a_anchor_support_repair_packet.py",
                "--pose-gap-json",
                str(v16_gap_json),
                "--scores-csv",
                str(v16_scores_csv),
            ]
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_htr2a_atom_typed_topology_probe.py",
                "--stage3-scores-csv",
                str(stage3_scores_csv),
            ]
        )
        _run([sys.executable, "tools/build_gpcr_htr2a_life_science_evidence_packet.py"])
        _run(
            [
                sys.executable,
                "tools/build_gpcr_htr2a_topology_support_shadow_replay.py",
                "--input-scores-csv",
                str(v16_scores_csv),
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
            ]
        )

    htr2a_lane = _lane("htr2a_anchor_topology_repair", DEFAULT_HTR2A_REPLAY_JSON)
    lanes["htr2a_anchor_topology_repair"] = htr2a_lane
    if htr2a_lane["status"] != "htr2a_topology_support_shadow_replay_selected_slice_green_claim_locked":
        blockers.append(f"htr2a:{htr2a_lane['status'] or 'missing'}")

    if not skip_oprm1:
        _run([sys.executable, "tools/build_gpcr_oprm1_life_science_evidence_packet.py"])
        _run(
            [
                sys.executable,
                "tools/build_gpcr_oprm1_topology_pose_shadow_replay.py",
                "--stage3-scores-csv",
                str(stage3_scores_csv),
                "--pose-gap-json",
                str(v16_gap_json),
                "--htr2a-replay-json",
                str(DEFAULT_HTR2A_REPLAY_JSON),
            ]
        )

    oprm1_lane = _lane("oprm1_pose_backmapping_repair", DEFAULT_OPRM1_REPLAY_JSON)
    lanes["oprm1_pose_backmapping_repair"] = oprm1_lane
    if oprm1_lane["status"] != "oprm1_topology_pose_shadow_replay_selected_slice_green_claim_locked":
        blockers.append(f"oprm1:{oprm1_lane['status'] or 'missing'}")

    if not skip_guarded:
        _run([sys.executable, "tools/build_gpcr_a1_accuracy_repair_queue.py"])
        _run(
            [
                sys.executable,
                "tools/build_gpcr_guarded_shadow_claim_review.py",
                "--ci-low-recovery-json",
                str(DEFAULT_CI_LOW_JSON),
            ]
        )
        _run(
            [
                sys.executable,
                "tools/build_gpcr_a1_accuracy_repair_queue.py",
                "--ranking-json",
                str(DEFAULT_OPERATIONAL_RANKING_SUMMARY_JSON),
            ]
        )

    shadow_lane = _lane("guarded_shadow_claim_review", DEFAULT_SHADOW_REVIEW_JSON)
    readiness_lane = _lane("guarded_100k_rerun_readiness", DEFAULT_GUARDED_READINESS_JSON)
    queue_lane = _lane("a1_accuracy_repair_queue", DEFAULT_A1_QUEUE_JSON)
    lanes["guarded_shadow_claim_review"] = shadow_lane
    lanes["guarded_100k_rerun_readiness"] = readiness_lane
    lanes["a1_accuracy_repair_queue"] = queue_lane

    shadow_summary = shadow_lane.get("summary") or {}
    readiness_summary = readiness_lane.get("summary") or {}
    if not shadow_summary.get("guarded_shadow_claim_review_passed"):
        blockers.extend([f"shadow:{item}" for item in shadow_summary.get("blockers") or []])
    if not readiness_summary.get("claim_review_eligible"):
        blockers.extend([f"readiness:{item}" for item in readiness_summary.get("blockers") or []])

    status = "ranking_quality_repair_chain_complete_claim_locked"
    if blockers:
        status = "blocked_ranking_quality_repair_chain_claim_locked"

    summary = {
        "packet_type": "gpcr_frozen_ranking_quality_repair_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": bool(readiness_summary.get("claim_review_eligible")),
        "lanes": lanes,
        "blockers": sorted(set(blockers)),
        "artifacts": {
            "v16_scores_csv": str(_resolve(v16_scores_csv)),
            "v16_gap_json": str(_resolve(v16_gap_json)),
            "htr2a_repair_json": str(_resolve(DEFAULT_HTR2A_REPAIR_JSON)),
            "htr2a_probe_json": str(_resolve(DEFAULT_HTR2A_PROBE_JSON)),
            "htr2a_replay_json": str(_resolve(DEFAULT_HTR2A_REPLAY_JSON)),
            "oprm1_replay_json": str(_resolve(DEFAULT_OPRM1_REPLAY_JSON)),
            "shadow_review_json": str(_resolve(DEFAULT_SHADOW_REVIEW_JSON)),
            "guarded_readiness_json": str(_resolve(DEFAULT_GUARDED_READINESS_JSON)),
            "a1_queue_json": str(_resolve(DEFAULT_A1_QUEUE_JSON)),
        },
        "next_required_step": (
            "Repair chain refreshed under claim lock. HTR2A/OPRM1 shadow green on selected slice does not "
            "authorize claim promotion; expand non-leaky positive coverage and clear CI-low/top20 before guarded review."
            if blockers
            else "Unexpected repair-chain green; keep claim locked until independent guarded gates confirm."
        ),
    }
    return {"summary": summary}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Ranking Quality Repair Chain (1→2→3)",
        "",
        f"- status: `{summary['status']}`",
        f"- claim_promotion_allowed: `false`",
        f"- full_100k_claim_review_allowed: `{summary.get('full_100k_claim_review_allowed')}`",
        "",
        "## Lanes",
        "",
    ]
    for lane_id, lane in (summary.get("lanes") or {}).items():
        lines.append(f"### `{lane_id}`")
        lines.append(f"- status: `{lane.get('status')}`")
        lines.append(f"- artifact: `{lane.get('artifact')}`")
        lines.append("")
    if summary.get("blockers"):
        lines.extend(["## Blockers", ""])
        for blocker in summary["blockers"]:
            lines.append(f"- `{blocker}`")
        lines.append("")
    lines.extend(["## Next Step", "", f"- {summary['next_required_step']}", ""])
    _resolve(path_like).write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run HTR2A anchor repair (1), OPRM1 pose/backmapping repair (2), guarded 100k readiness (3)."
    )
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--stage5-rows-csv", default=DEFAULT_STAGE5_ROWS_CSV)
    parser.add_argument("--v16-scores-csv", default=DEFAULT_V16_SCORES_CSV)
    parser.add_argument("--v16-gap-json", default=DEFAULT_V16_GAP_JSON)
    parser.add_argument(
        "--v16-source",
        choices=["canonical-adaptive", "discriminator-refreshed"],
        default="canonical-adaptive",
        help="canonical-adaptive=legacy true-base v16 replay; discriminator-refreshed=port-probe refresh (HTR2A regresses).",
    )
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--skip-htr2a", action="store_true")
    parser.add_argument("--skip-oprm1", action="store_true")
    parser.add_argument("--skip-guarded", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    v16_scores_csv = args.v16_scores_csv
    v16_gap_json = args.v16_gap_json
    if args.v16_source == "discriminator-refreshed":
        v16_scores_csv = DEFAULT_V16_DISCRIMINATOR_REFRESH_SCORES_CSV
        v16_gap_json = DEFAULT_V16_DISCRIMINATOR_REFRESH_GAP_JSON
    payload = build_packet(
        stage3_scores_csv=args.stage3_scores_csv,
        stage5_rows_csv=args.stage5_rows_csv,
        v16_scores_csv=v16_scores_csv,
        v16_gap_json=v16_gap_json,
        skip_htr2a=args.skip_htr2a,
        skip_oprm1=args.skip_oprm1,
        skip_guarded=args.skip_guarded,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
