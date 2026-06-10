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
DEFAULT_FEATURE_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_none_stage3_current.csv"
DEFAULT_FEATURE_CACHE_JSON = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_none_stage3_current.json"
DEFAULT_V11_REPLAY_SCORES_CSV = "runs/gpcr_cationic_weakbase_v11_frozen_none_stage3_shadow_replay_scores_current.csv"
DEFAULT_V11_REPLAY_SUMMARY_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_none_stage3_shadow_replay_summary_current.json"
DEFAULT_V11_REVIEW_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_none_stage3_shadow_replay_review_current.json"
DEFAULT_GUARDED_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_post_stage3_v11_claim_review_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_post_stage3_v11_claim_review_chain_current.md"


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


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def _text(value: Any) -> str:
    return str(value or "").strip()


def build_packet(
    *,
    stage3_scores_csv: str | Path = DEFAULT_STAGE3_SCORES_CSV,
    feature_cache_csv: str | Path = DEFAULT_FEATURE_CACHE_CSV,
    feature_cache_json: str | Path = DEFAULT_FEATURE_CACHE_JSON,
    v11_replay_scores_csv: str | Path = DEFAULT_V11_REPLAY_SCORES_CSV,
    v11_replay_summary_json: str | Path = DEFAULT_V11_REPLAY_SUMMARY_JSON,
    v11_review_json: str | Path = DEFAULT_V11_REVIEW_JSON,
    guarded_readiness_json: str | Path = DEFAULT_GUARDED_READINESS_JSON,
    anchor_mode: str = "none",
    row_limit: int = 0,
    skip_cache_build: bool = False,
    skip_v11_replay: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    stage3_path = _resolve(stage3_scores_csv)
    blockers: list[str] = []
    if not stage3_path.exists() or stage3_path.stat().st_size <= 0:
        blockers.append("stage3_scores_csv_missing")

    cache_summary: dict[str, Any] = {}
    v11_chain_summary: dict[str, Any] = {}
    guarded_summary: dict[str, Any] = {}

    if blockers:
        summary = {
            "packet_type": "gpcr_frozen_post_stage3_v11_claim_review_chain",
            "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "blocked_wait_stage3_scores_csv",
            "claim_promotion_allowed": False,
            "scorer_apply_allowed": False,
            "full_100k_claim_review_allowed": False,
            "blockers": blockers,
            "next_required_step": "Wait for stage3_scores.csv to appear after stage2 completes.",
        }
        return {
            "summary": summary,
            "cache_summary": cache_summary,
            "v11_chain_summary": v11_chain_summary,
            "guarded_readiness_summary": guarded_summary,
        }

    if not skip_cache_build:
        cache_cmd = [
            sys.executable,
            "tools/build_gpcr_cationic_pose_distortion_frozen_feature_cache.py",
            "--input-csv",
            str(stage3_scores_csv),
            "--anchor-mode",
            str(anchor_mode),
            "--resume-existing",
            "--out-csv",
            str(feature_cache_csv),
            "--out-json",
            str(feature_cache_json),
        ]
        if int(row_limit) > 0:
            cache_cmd.extend(["--row-limit", str(int(row_limit))])
        _run(cache_cmd)
    cache_summary = _read_json(feature_cache_json).get("summary", {})
    if int(cache_summary.get("feature_row_count") or 0) <= 0:
        blockers.append("feature_cache_empty")

    if not skip_v11_replay and not blockers:
        from tools.gpcr_replay.build_gpcr_frozen_v11_discriminator_replay_chain import build_packet as build_v11_chain

        v11_payload = build_v11_chain(
            input_cache_csv=feature_cache_csv,
            refreshed_cache_csv=str(_resolve(feature_cache_csv).with_name(_resolve(feature_cache_csv).stem + "_discriminator.csv")),
            replay_scores_csv=v11_replay_scores_csv,
            replay_summary_json=v11_replay_summary_json,
            review_json=v11_review_json,
        )
        v11_chain_summary = v11_payload.get("summary", {})
        if _text(v11_chain_summary.get("status")) != "frozen_shadow_green_claim_locked":
            blockers.extend(list(v11_chain_summary.get("blockers") or []))

    _run([sys.executable, "tools/build_gpcr_guarded_100k_rerun_readiness.py"])
    guarded_summary = _read_json(guarded_readiness_json).get("summary", {})
    if not _as_bool(guarded_summary.get("claim_review_eligible")):
        blockers.extend(list(guarded_summary.get("blockers") or []))

    status = "blocked_post_stage3_claim_review_claim_locked"
    if not blockers:
        status = "post_stage3_review_packets_refreshed_claim_locked"

    summary = {
        "packet_type": "gpcr_frozen_post_stage3_v11_claim_review_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "stage3_scores_csv": str(stage3_path),
        "feature_cache_status": _text(cache_summary.get("status")),
        "feature_row_count": cache_summary.get("feature_row_count"),
        "label_free_anchor_mode": _text(cache_summary.get("label_free_anchor_mode") or anchor_mode),
        "v11_replay_status": _text(v11_chain_summary.get("status")),
        "shadow_top20_positive_count": v11_chain_summary.get("shadow_top20_positive_count"),
        "guarded_readiness_status": _text(guarded_summary.get("status")),
        "guarded_claim_review_eligible": _as_bool(guarded_summary.get("claim_review_eligible")),
        "blockers": sorted(set(blockers)),
        "artifacts": {
            "feature_cache_csv": str(_resolve(feature_cache_csv)),
            "feature_cache_json": str(_resolve(feature_cache_json)),
            "v11_review_json": str(_resolve(v11_review_json)),
            "guarded_readiness_json": str(_resolve(guarded_readiness_json)),
        },
        "next_required_step": (
            "All post-stage3 review packets refreshed under claim lock. Claim promotion remains blocked until "
            "CI-low, top20, leakage, and family-held-out gates are green."
            if status == "post_stage3_review_packets_refreshed_claim_locked"
            else "Keep claim promotion blocked. Resolve blockers in frozen cache coverage, v11 shadow replay, "
            "and guarded 100k readiness gates before any claim review."
        ),
    }
    return {
        "summary": summary,
        "cache_summary": cache_summary,
        "v11_chain_summary": v11_chain_summary,
        "guarded_readiness_summary": guarded_summary,
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "passed", "green", "eligible"}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen Post-Stage3 v11 Claim Review Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- feature_row_count: `{summary.get('feature_row_count')}`",
        f"- v11_replay_status: `{summary.get('v11_replay_status')}`",
        f"- guarded_readiness_status: `{summary.get('guarded_readiness_status')}`",
        f"- claim_promotion_allowed: `false`",
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
    parser = argparse.ArgumentParser(
        description="Rebuild frozen feature cache from stage3, rerun v11 shadow replay, refresh guarded 100k readiness."
    )
    parser.add_argument("--stage3-scores-csv", default=DEFAULT_STAGE3_SCORES_CSV)
    parser.add_argument("--feature-cache-csv", default=DEFAULT_FEATURE_CACHE_CSV)
    parser.add_argument("--feature-cache-json", default=DEFAULT_FEATURE_CACHE_JSON)
    parser.add_argument("--v11-replay-scores-csv", default=DEFAULT_V11_REPLAY_SCORES_CSV)
    parser.add_argument("--v11-replay-summary-json", default=DEFAULT_V11_REPLAY_SUMMARY_JSON)
    parser.add_argument("--v11-review-json", default=DEFAULT_V11_REVIEW_JSON)
    parser.add_argument("--guarded-readiness-json", default=DEFAULT_GUARDED_READINESS_JSON)
    parser.add_argument("--anchor-mode", choices=["none", "all_basic", "adaptive_pose_preserving"], default="none")
    parser.add_argument("--row-limit", type=int, default=0)
    parser.add_argument("--skip-cache-build", action="store_true")
    parser.add_argument("--skip-v11-replay", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        stage3_scores_csv=args.stage3_scores_csv,
        feature_cache_csv=args.feature_cache_csv,
        feature_cache_json=args.feature_cache_json,
        v11_replay_scores_csv=args.v11_replay_scores_csv,
        v11_replay_summary_json=args.v11_replay_summary_json,
        v11_review_json=args.v11_review_json,
        guarded_readiness_json=args.guarded_readiness_json,
        anchor_mode=args.anchor_mode,
        row_limit=int(args.row_limit),
        skip_cache_build=bool(args.skip_cache_build),
        skip_v11_replay=bool(args.skip_v11_replay),
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
