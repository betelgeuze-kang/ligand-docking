#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REVIEW_RESOLUTION_JSON = "runs/idp_broader_shadow_review_resolution_current.json"
DEFAULT_DECISION_JSON = "runs/idp_commercial_pretest_decision_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_launch_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_shadow_launch_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_launch_packet_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _load_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_payload(
    review_resolution: dict[str, Any],
    decision_payload: dict[str, Any],
) -> dict[str, Any]:
    review_s = dict(review_resolution.get("summary", {}) or {})
    review_rows = [dict(row) for row in review_resolution.get("rows", []) or []]
    decision_s = dict(decision_payload.get("summary", {}) or {})

    env_prefix = "IDP_R17_TAU_PH_SPLIT_PATCH=1 IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH=1"
    config_json = str(review_s.get("config_json", "")).strip()
    same_scope_config_json = str(review_s.get("same_scope_config_json", "")).strip()
    out_prefix = "runs/idp_3bead_holdout_v7_broader_shadow_full_r1"
    command = (
        f"{env_prefix} python3 tools/run_idp_3bead_holdout_pipeline.py "
        f"--config-json {config_json} "
        "--device cuda "
        f"--out-prefix {out_prefix} "
        "--resume-existing 0 "
        "--kalman-shadow-enable 1 "
        "--kalman-shadow-mode feature_state_v1 "
        "--kalman-shadow-family-token idp "
        f"--kalman-shadow-feature-mask {decision_s.get('default_feature_mask', review_s.get('default_feature_mask', 'rg_sasa_only'))} "
        "--kalman-shadow-obs-noise-scale 0.15 "
        "--kalman-shadow-process-noise-scale 0.03 "
        "--kalman-shadow-delta-cap-frac 0.25"
    )
    same_scope_command = (
        f"{env_prefix} python3 tools/run_idp_3bead_holdout_pipeline.py "
        f"--config-json {same_scope_config_json} "
        "--device cuda "
        "--out-prefix runs/idp_3bead_holdout_v7_anchor_commercial_pretest_processcheck_r1 "
        "--resume-existing 0 "
        "--kalman-shadow-enable 1 "
        "--kalman-shadow-mode feature_state_v1 "
        "--kalman-shadow-family-token idp "
        f"--kalman-shadow-feature-mask {decision_s.get('default_feature_mask', review_s.get('default_feature_mask', 'rg_sasa_only'))} "
        "--kalman-shadow-obs-noise-scale 0.15 "
        "--kalman-shadow-process-noise-scale 0.03 "
        "--kalman-shadow-delta-cap-frac 0.25"
    )
    true_broader_rerun_ready = bool(review_s.get("true_broader_rerun_ready", False))
    additional_anchor_backed_target_count = int(review_s.get("additional_anchor_backed_target_count", 0) or 0)
    provisional_expansion_target_count = int(review_s.get("provisional_expansion_target_count", 0) or 0)

    rows = [
        {
            "launch_step": "scope",
            "status": "frozen_same_scope_only" if not true_broader_rerun_ready else "frozen_true_broader_shadow_only",
            "detail": "same_scope_process_check_only" if not true_broader_rerun_ready else "first_true_broader_shadow_only_not_promotion",
        },
        {
            "launch_step": "validated_targets",
            "status": "monitor",
            "detail": str(sum(1 for row in review_rows if row.get("tier", "").startswith("validated_"))),
        },
        {
            "launch_step": "additional_anchor_backed_targets",
            "status": "blocked_no_true_broader_roster" if not true_broader_rerun_ready else "included_first_true_broader_launch",
            "detail": str(additional_anchor_backed_target_count),
        },
        {
            "launch_step": "provisional_targets",
            "status": "blocked_for_true_broader_launch" if not true_broader_rerun_ready else "excluded_from_first_true_broader_launch",
            "detail": str(sum(1 for row in review_rows if row.get("tier") == "provisional_only_expansion")),
        },
        {
            "launch_step": "guardrails",
            "status": "frozen",
            "detail": "no_coordinate_correction; no_ranking_override; no_gate_override; feature_state_smoothing_only",
        },
        {
            "launch_step": "command",
            "status": "draft_only" if not true_broader_rerun_ready else "ready",
            "detail": command,
        },
        {
            "launch_step": "same_scope_process_check",
            "status": "ready",
            "detail": same_scope_command,
        },
    ]

    summary = {
        "status": (
            "launch_blocked_no_true_broader_roster_same_scope_only_ready"
            if not true_broader_rerun_ready
            else "launch_ready_shadow_stress_not_promotion"
        ),
        "operator_scope_now": str(decision_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": bool(decision_s.get("broader_promotion_blocked", True)),
        "shadow_safe_retained": bool(decision_s.get("shadow_safe_retained", False)),
        "review_resolution_status": str(review_s.get("status", "")).strip(),
        "reviewed_target_count": int(review_s.get("reviewed_target_count", 0) or 0),
        "validated_current_target_count": int(review_s.get("validated_current_target_count", 0) or 0),
        "additional_anchor_backed_target_count": additional_anchor_backed_target_count,
        "provisional_expansion_target_count": provisional_expansion_target_count,
        "true_broader_rerun_ready": true_broader_rerun_ready,
        "same_scope_process_check_ready": True,
        "out_prefix": out_prefix,
        "config_json": config_json,
        "command": command,
        "same_scope_command": same_scope_command,
        "next_required_step": (
            "Do not launch a true broader full-IDP rerun yet. Use the same-scope process-check command only on the validated 7-target literature-anchor subset, "
            "or curate at least one additional anchor-backed target before promoting this broader draft toward launch."
            if not true_broader_rerun_ready
            else "Launch this first true broader full-IDP shadow-only rerun with the validated 7-target scaffold plus PAGE4, keep broader_full_idp_promotion blocked, exclude provisional-only expansion targets, and judge success against zero state/gate drift plus no corrected-pass regression on the validated current targets."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Launch Packet",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- review_resolution_status: `{s['review_resolution_status']}`",
        f"- reviewed_target_count: `{s['reviewed_target_count']}`",
        f"- validated_current_target_count: `{s['validated_current_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- provisional_expansion_target_count: `{s['provisional_expansion_target_count']}`",
        f"- true_broader_rerun_ready: `{s['true_broader_rerun_ready']}`",
        f"- same_scope_process_check_ready: `{s['same_scope_process_check_ready']}`",
        f"- config_json: `{s['config_json']}`",
        f"- out_prefix: `{s['out_prefix']}`",
        "",
        "## Command",
        "",
        "```bash",
        s["command"],
        "```",
        "",
        "## Same-Scope Process Check Command",
        "",
        "```bash",
        s["same_scope_command"],
        "```",
        "",
        "## Launch Steps",
        "",
        "| launch_step | status | detail |",
        "| --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['launch_step']}` | `{row['status']}` | `{row['detail']}` |")
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build the first broader full-IDP shadow rerun launch packet.")
    p.add_argument("--review-resolution-json", default=DEFAULT_REVIEW_RESOLUTION_JSON)
    p.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.review_resolution_json),
        _load_json(args.decision_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv_rows(out_csv, payload["rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
