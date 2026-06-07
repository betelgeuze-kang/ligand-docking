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

BETA_BLOCKER_SUMMARY_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_summary.json"
)
BETA_BLOCKER_STAGE5_ROWS_CSV = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage5_ranking_rows.csv"
)
BETA_BLOCKER_STAGE5_SUMMARY_JSON = (
    "runs/external_validation_2026-05-10_beta_blocker_rescue_v2_family_balanced100k_r1_set1_core_blind_"
    "gpcr_core_full_p0_n100000_r1_stage5_ranking_summary.json"
)
COVERAGE_V1_POSITIVE_JSON = "runs/gpcr_positive_coverage_freeze_packet_coverage_v1_current.json"
COVERAGE_V1_SCOREABILITY_JSON = "runs/gpcr_frozen_candidate_scoreability_coverage_v1_current.json"
COVERAGE_V1_FAMILY_HELDOUT_JSON = (
    "runs/gpcr_family_heldout_scorecard_guardrail_beta_blocker_rescue_v2_coverage_v1_full_current.json"
)
COVERAGE_V1_TRIAGE_JSON = "runs/gpcr_scaleup_regression_triage_beta_blocker_rescue_v2_coverage_v1_full_current.json"
COVERAGE_V1_LEAKAGE_JSON = (
    "runs/external_validation_2026-05-10_coverage_v1_family_balanced100k_r1_set1_core_blind_gpcr_core_full_"
    "p0_n100000_r1_stage0_leakage_summary.json"
)
DEFAULT_V16_GAP_JSON = "runs/gpcr_false_support_discriminator_v16_adaptive_frozen_gap_packet_current.json"
DEFAULT_CI_LOW_JSON = "runs/gpcr_ci_low_recovery_packet_current.json"
DEFAULT_READINESS_JSON = "runs/gpcr_guarded_100k_rerun_readiness_current.json"
DEFAULT_SHADOW_SCORES_CSV = "runs/gpcr_drd2_weakbase_false_support_shadow_replay_scores_current.csv"
DEFAULT_SHADOW_SCORE_COL = "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow"
DEFAULT_SHADOW_REVIEW_JSON = "runs/gpcr_guarded_shadow_claim_review_current.json"
DEFAULT_A1_QUEUE_JSON = "runs/gpcr_a1_accuracy_repair_queue_current.json"
DEFAULT_REPAIR_CHAIN_JSON = "runs/gpcr_frozen_ranking_quality_repair_chain_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_guarded_operational_gate_refresh_chain_current.json"
DEFAULT_OUT_MD = "runs/gpcr_guarded_operational_gate_refresh_chain_current.md"


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
    return {"lane": name, "status": _text(summary.get("status")), "artifact": str(_resolve(path_like)), "summary": summary}


def build_packet(
    *,
    rerun_summary_json: str | Path = BETA_BLOCKER_SUMMARY_JSON,
    operational_ranking_rows_csv: str | Path = BETA_BLOCKER_STAGE5_ROWS_CSV,
    operational_ranking_summary_json: str | Path = BETA_BLOCKER_STAGE5_SUMMARY_JSON,
    positive_json: str | Path = COVERAGE_V1_POSITIVE_JSON,
    scoreability_json: str | Path = COVERAGE_V1_SCOREABILITY_JSON,
    family_heldout_json: str | Path = COVERAGE_V1_FAMILY_HELDOUT_JSON,
    triage_json: str | Path = COVERAGE_V1_TRIAGE_JSON,
    leakage_audit_json: str | Path = COVERAGE_V1_LEAKAGE_JSON,
    pose_gap_json: str | Path = DEFAULT_V16_GAP_JSON,
    ci_low_json: str | Path = DEFAULT_CI_LOW_JSON,
    readiness_json: str | Path = DEFAULT_READINESS_JSON,
    shadow_review_json: str | Path = DEFAULT_SHADOW_REVIEW_JSON,
    a1_queue_json: str | Path = DEFAULT_A1_QUEUE_JSON,
    repair_chain_json: str | Path = DEFAULT_REPAIR_CHAIN_JSON,
    skip_repair_chain_finalize: bool = False,
    generated_at_local: str | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []

    _run(
        [
            sys.executable,
            "tools/gpcr_replay/build_gpcr_ci_low_recovery_packet.py",
            "--summary-json",
            str(rerun_summary_json),
            "--triage-json",
            str(triage_json),
            "--out-json",
            str(ci_low_json),
            "--out-md",
            str(_resolve(ci_low_json).with_suffix(".md")),
        ]
    )
    ci_lane = _lane("ci_low_recovery", ci_low_json)
    if not ci_lane["summary"].get("pass") and ci_lane["summary"].get("ci_low_blocker"):
        blockers.append("ci_low_recovery:ci_low_blocker")

    _run(
        [
            sys.executable,
            "tools/gpcr_replay/build_gpcr_guarded_100k_rerun_readiness.py",
            "--positive-json",
            str(positive_json),
            "--scoreability-json",
            str(scoreability_json),
            "--family-heldout-json",
            str(family_heldout_json),
            "--ci-low-json",
            str(ci_low_json),
            "--triage-json",
            str(triage_json),
            "--leakage-audit-json",
            str(leakage_audit_json),
            "--out-json",
            str(readiness_json),
            "--out-md",
            str(_resolve(readiness_json).with_suffix(".md")),
        ]
    )
    readiness_lane = _lane("guarded_100k_rerun_readiness", readiness_json)
    if not readiness_lane["summary"].get("claim_review_eligible"):
        blockers.extend([f"readiness:{item}" for item in readiness_lane["summary"].get("blockers") or []])

    _run([sys.executable, "tools/build_gpcr_a1_accuracy_repair_queue.py"])
    _run(
        [
            sys.executable,
            "tools/build_gpcr_guarded_shadow_claim_review.py",
            "--scores-csv",
            str(DEFAULT_SHADOW_SCORES_CSV),
            "--score-col",
            DEFAULT_SHADOW_SCORE_COL,
            "--pose-gap-json",
            str(pose_gap_json),
            "--ci-low-recovery-json",
            str(ci_low_json),
            "--a1-queue-json",
            str(a1_queue_json),
            "--out-json",
            str(shadow_review_json),
            "--out-md",
            str(_resolve(shadow_review_json).with_suffix(".md")),
            "--out-rows-csv",
            str(_resolve(shadow_review_json).with_name("gpcr_guarded_shadow_claim_review_rows_current.csv")),
        ]
    )
    _run(
        [
            sys.executable,
            "tools/build_gpcr_a1_accuracy_repair_queue.py",
            "--ranking-json",
            str(operational_ranking_summary_json),
        ]
    )

    shadow_lane = _lane("guarded_shadow_claim_review", shadow_review_json)
    if not shadow_lane["summary"].get("guarded_shadow_claim_review_passed"):
        blockers.extend([f"shadow:{item}" for item in shadow_lane["summary"].get("blockers") or []])

    if not skip_repair_chain_finalize:
        _run(
            [
                sys.executable,
                "tools/build_gpcr_frozen_ranking_quality_repair_chain.py",
                "--skip-htr2a",
                "--skip-oprm1",
                "--skip-guarded",
            ]
        )

    repair_lane = _lane("repair_chain", repair_chain_json)
    queue_lane = _lane("a1_accuracy_repair_queue", a1_queue_json)

    status = "guarded_operational_gate_refresh_complete_claim_locked"
    if blockers:
        status = "blocked_guarded_operational_gate_refresh_claim_locked"

    summary = {
        "packet_type": "gpcr_guarded_operational_gate_refresh_chain",
        "generated_at_local": generated_at_local or dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "claim_promotion_allowed": False,
        "scorer_apply_allowed": False,
        "full_100k_claim_review_allowed": bool(readiness_lane["summary"].get("claim_review_eligible")),
        "operational_rerun_evidence": {
            "summary_json": str(_resolve(rerun_summary_json)),
            "stage5_ranking_rows_csv": str(_resolve(operational_ranking_rows_csv)),
            "stage5_ranking_summary_json": str(_resolve(operational_ranking_summary_json)),
            "coverage_v1_positive_json": str(_resolve(positive_json)),
        },
        "shadow_diagnostic_evidence": {
            "scores_csv": str(_resolve(DEFAULT_SHADOW_SCORES_CSV)),
            "score_col": DEFAULT_SHADOW_SCORE_COL,
            "ci_low_recovery_json": str(_resolve(ci_low_json)),
        },
        "lanes": {
            "ci_low_recovery": ci_lane,
            "guarded_100k_rerun_readiness": readiness_lane,
            "guarded_shadow_claim_review": shadow_lane,
            "repair_chain": repair_lane,
            "a1_accuracy_repair_queue": queue_lane,
        },
        "blockers": sorted(set(blockers)),
        "next_required_step": (
            "Operational CI-low/top20 gates refreshed from beta_blocker_rescue_v2 coverage-v1 rerun evidence. "
            "claim_promotion_allowed remains false; execute formal claim review before any scorer/router promotion."
            if not blockers
            else "Operational gate refresh incomplete; resolve listed blockers without threshold relaxation or fake pass."
        ),
    }
    return {"summary": summary}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# GPCR Guarded Operational Gate Refresh Chain",
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
        description="Refresh guarded CI-low/top20 and shadow claim-review gates from beta_blocker_rescue_v2 rerun evidence."
    )
    parser.add_argument("--rerun-summary-json", default=BETA_BLOCKER_SUMMARY_JSON)
    parser.add_argument("--operational-ranking-rows-csv", default=BETA_BLOCKER_STAGE5_ROWS_CSV)
    parser.add_argument("--operational-ranking-summary-json", default=BETA_BLOCKER_STAGE5_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument(
        "--skip-repair-chain-finalize",
        action="store_true",
        help="Skip repair-chain rollup refresh; default runs a guarded-free rollup before shadow/A1 finalize.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_packet(
        rerun_summary_json=args.rerun_summary_json,
        operational_ranking_rows_csv=args.operational_ranking_rows_csv,
        operational_ranking_summary_json=args.operational_ranking_summary_json,
        skip_repair_chain_finalize=args.skip_repair_chain_finalize,
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
