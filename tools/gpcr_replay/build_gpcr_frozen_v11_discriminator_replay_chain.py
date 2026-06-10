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

DEFAULT_INPUT_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_allbasic_truebase_16500_current.csv"
DEFAULT_REFRESHED_CACHE_CSV = "runs/gpcr_cationic_pose_distortion_frozen_feature_cache_v11_discriminator_current.csv"
DEFAULT_SPEC_JSON = "runs/gpcr_residual_prototype_spec_cationic_weakbase_rescue_shadow_v11_current.json"
DEFAULT_REPLAY_SCORES_CSV = "runs/gpcr_cationic_weakbase_v11_frozen_discriminator_shadow_replay_scores_current.csv"
DEFAULT_REPLAY_SUMMARY_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_discriminator_shadow_replay_summary_current.json"
DEFAULT_REPLAY_SUMMARY_MD = "runs/gpcr_cationic_weakbase_v11_frozen_discriminator_shadow_replay_summary_current.md"
DEFAULT_REVIEW_JSON = "runs/gpcr_cationic_weakbase_v11_frozen_discriminator_shadow_replay_review_current.json"
DEFAULT_REVIEW_MD = "runs/gpcr_cationic_weakbase_v11_frozen_discriminator_shadow_replay_review_current.md"
DEFAULT_OUT_JSON = "runs/gpcr_frozen_v11_discriminator_replay_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_frozen_v11_discriminator_replay_chain_current.md"


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


def build_packet(
    *,
    input_cache_csv: str | Path = DEFAULT_INPUT_CACHE_CSV,
    refreshed_cache_csv: str | Path = DEFAULT_REFRESHED_CACHE_CSV,
    spec_json: str | Path = DEFAULT_SPEC_JSON,
    replay_scores_csv: str | Path = DEFAULT_REPLAY_SCORES_CSV,
    replay_summary_json: str | Path = DEFAULT_REPLAY_SUMMARY_JSON,
    review_json: str | Path = DEFAULT_REVIEW_JSON,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    _run(
        [
            sys.executable,
            "tools/gpcr_replay/recompute_gpcr_frozen_feature_cache_discriminator_pressures.py",
            "--input-csv",
            str(input_cache_csv),
            "--out-csv",
            str(refreshed_cache_csv),
            "--out-json",
            str(_resolve(refreshed_cache_csv).with_suffix(".json")),
        ]
    )
    refresh_summary = _read_json(_resolve(refreshed_cache_csv).with_suffix(".json")).get("summary", {})

    from tools.accounting.build_gpcr_residual_prototype_spec import (
        build_payload as build_spec_payload,
        _write_csv as write_spec_csv,
        _write_markdown as write_spec_markdown,
    )

    spec_path = _resolve(spec_json)
    spec_payload = build_spec_payload(variant="gpcr_core_cationic_weakbase_rescue_shadow_v11")
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(spec_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_spec_csv(spec_path.with_suffix(".csv"), spec_payload["feature_rows"])
    write_spec_markdown(spec_path.with_suffix(".md"), spec_payload)

    _run(
        [
            sys.executable,
            "tools/product/replay_gpcr_residual_shadow_scores.py",
            "--input-scores-csv",
            str(refreshed_cache_csv),
            "--residual-prototype-spec-json",
            str(spec_json),
            "--out-scores-csv",
            str(replay_scores_csv),
            "--out-summary-json",
            str(replay_summary_json),
            "--out-summary-md",
            str(DEFAULT_REPLAY_SUMMARY_MD),
        ]
    )

    _run(
        [
            sys.executable,
            "tools/gpcr_replay/build_gpcr_cationic_weakbase_frozen_shadow_replay_review.py",
            "--input-scores-csv",
            str(replay_scores_csv),
            "--input-summary-json",
            str(replay_summary_json),
            "--out-json",
            str(review_json),
            "--out-md",
            str(DEFAULT_REVIEW_MD),
        ]
    )

    replay_summary = _read_json(replay_summary_json).get("summary", {})
    review_summary = _read_json(review_json).get("summary", {})
    shadow_summary = review_summary.get("shadow_score_summary") or {}
    target_positive_ranks = shadow_summary.get("target_positive_ranks") or {}
    summary = {
        "packet_type": "gpcr_frozen_v11_discriminator_replay_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": _text(review_summary.get("status")) or "blocked_frozen_shadow_review_claim_locked",
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": False,
        "refresh_status": _text(refresh_summary.get("status")),
        "false_valid_anchor_discriminator_row_count": refresh_summary.get("false_valid_anchor_discriminator_row_count"),
        "replay_status": _text(replay_summary.get("status")),
        "shadow_top20_positive_count": shadow_summary.get("top20_positive_count"),
        "drd2_decoys_above_positive": next(
            (
                item.get("decoys_above_positive")
                for item in target_positive_ranks.get("CHEMBL217_DRD2_HUMAN", [])
                if isinstance(item, dict)
            ),
            None,
        ),
        "blockers": list(review_summary.get("blockers") or []),
        "artifacts": {
            "refreshed_cache_csv": str(_resolve(refreshed_cache_csv)),
            "replay_scores_csv": str(_resolve(replay_scores_csv)),
            "review_json": str(_resolve(review_json)),
        },
        "next_required_step": _text(review_summary.get("next_required_step"))
        or (
            "Wait for stage2/stage3 regeneration to finish, rebuild full frozen cache from fresh stage3 scores, "
            "then rerun guarded 100k claim review."
        ),
    }
    return {
        "summary": summary,
        "refresh_summary": refresh_summary,
        "replay_summary": replay_summary,
        "review_summary": review_summary,
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Frozen v11 Discriminator Replay Chain",
        "",
        f"- status: `{summary['status']}`",
        f"- refresh_status: `{summary['refresh_status']}`",
        f"- false_valid_anchor_discriminator_row_count: `{summary['false_valid_anchor_discriminator_row_count']}`",
        f"- shadow_top20_positive_count: `{summary['shadow_top20_positive_count']}`",
        f"- drd2_decoys_above_positive: `{summary['drd2_decoys_above_positive']}`",
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
    parser = argparse.ArgumentParser(description="Refresh discriminator pressures and rerun v11 frozen shadow replay.")
    parser.add_argument("--input-cache-csv", default=DEFAULT_INPUT_CACHE_CSV)
    parser.add_argument("--refreshed-cache-csv", default=DEFAULT_REFRESHED_CACHE_CSV)
    parser.add_argument("--spec-json", default=DEFAULT_SPEC_JSON)
    parser.add_argument("--replay-scores-csv", default=DEFAULT_REPLAY_SCORES_CSV)
    parser.add_argument("--replay-summary-json", default=DEFAULT_REPLAY_SUMMARY_JSON)
    parser.add_argument("--review-json", default=DEFAULT_REVIEW_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        input_cache_csv=args.input_cache_csv,
        refreshed_cache_csv=args.refreshed_cache_csv,
        spec_json=args.spec_json,
        replay_scores_csv=args.replay_scores_csv,
        replay_summary_json=args.replay_summary_json,
        review_json=args.review_json,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
