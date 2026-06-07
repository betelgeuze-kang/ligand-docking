#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.operator_surface_contracts import (
    IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
    IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
)

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PROMOTION_RESOLUTION_JSON = "runs/idp_broader_promotion_resolution_current.json"
DEFAULT_BROADER_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_OUT_PREFIX = "runs/idp_3bead_holdout_v7_onewider_repeatability_r1"
DEFAULT_OUT_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_OUT_CSV = "runs/idp_one_wider_shadow_repeatability_packet_current.csv"
DEFAULT_OUT_MD = "runs/idp_one_wider_shadow_repeatability_packet_current.md"


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


def _exact_command(config_json: str, out_prefix: str) -> str:
    return " ".join(
        [
            "IDP_R17_TAU_PH_SPLIT_PATCH=1",
            "IDP_R18_TAU_PH_HELIX_RECOVERY_PATCH=1",
            "python3",
            "tools/run_idp_3bead_holdout_pipeline.py",
            "--config-json",
            config_json,
            "--device",
            "cuda",
            "--out-prefix",
            str(_resolve(out_prefix)),
            "--resume-existing",
            "0",
            "--kalman-shadow-enable",
            "1",
            "--kalman-shadow-mode",
            "feature_state_v1",
            "--kalman-shadow-family-token",
            "idp",
            "--kalman-shadow-feature-mask",
            "rg_sasa_only",
            "--kalman-shadow-obs-noise-scale",
            "0.15",
            "--kalman-shadow-process-noise-scale",
            "0.03",
            "--kalman-shadow-delta-cap-frac",
            "0.25",
        ]
    )


def build_payload(
    promotion_resolution: dict[str, Any],
    broader_result: dict[str, Any],
    *,
    out_prefix: str,
) -> dict[str, Any]:
    resolution_s = dict((promotion_resolution.get("summary") if isinstance(promotion_resolution.get("summary"), dict) else {}) or {})
    result_s = dict((broader_result.get("summary") if isinstance(broader_result.get("summary"), dict) else {}) or {})
    broader_rows = [dict(row) for row in broader_result.get("rows", []) or []]

    config_json = str(result_s.get("config_json", "")).strip()
    rows: list[dict[str, Any]] = []
    for row in broader_rows:
        target_name = str(row.get("target_name", "")).strip()
        rows.append(
            {
                "target_name": target_name,
                "expected_pass": bool(row.get("pass", False)),
                "focus_class": (
                    "page4_anchor_target"
                    if target_name == "page4"
                    else "tau_k18_watch_target"
                    if target_name == "tau_k18"
                    else "validated_anchor_guard"
                ),
                "repeatability_goal": (
                    "keep fold pass, zero state/gate drift, and no corrected regression"
                    if target_name in {"page4", "tau_k18"}
                    else "keep fold pass and zero state/gate drift"
                ),
            }
        )

    summary = {
        "status": "one_wider_shadow_repeatability_packet_ready",
        "operator_scope_now": str(resolution_s.get("operator_scope_now", "")).strip() or IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE,
        "blocked_scope": IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION,
        "broader_promotion_blocked": bool(resolution_s.get("broader_promotion_blocked", True)),
        "shadow_safe_retained": bool(resolution_s.get("shadow_safe_retained", False)),
        "wider_shadow_safe_lane_admitted": bool(resolution_s.get("wider_shadow_safe_lane_admitted", False)),
        "frozen_validated_current_target_count": int(resolution_s.get("frozen_validated_current_target_count", 0) or 0),
        "frozen_additional_anchor_backed_target_count": int(resolution_s.get("frozen_additional_anchor_backed_target_count", 0) or 0),
        "frozen_total_target_count": int(resolution_s.get("frozen_total_target_count", 0) or 0),
        "reference_result_status": str(result_s.get("status", "")).strip(),
        "reference_corrected_pass_folds": int(result_s.get("corrected_pass_folds", 0) or 0),
        "reference_fold_count": int(result_s.get("fold_count", 0) or 0),
        "page4_fold_pass": bool(result_s.get("page4_fold_pass", False)),
        "tau_k18_fold_pass": bool(result_s.get("tau_k18_fold_pass", False)),
        "config_json": config_json,
        "out_prefix": str(_resolve(out_prefix)),
        "row_count": len(rows),
        "exact_command": _exact_command(config_json, out_prefix),
        "success_criteria": (
            "Repeat the admitted 8-target wider shadow-safe lane with 8/8 corrected pass, combined_gate_pass=True, "
            "would_change_state_count=0, would_change_gate_count=0, and no corrected-pass regression versus the first broader shadow pass."
        ),
        "next_required_step": (
            f"Launch this bounded repeatability rerun inside `{IDP_SAFE_SCOPE_ONE_WIDER_SHADOW_SAFE_LANE}`, keep the frozen validated-7-plus-PAGE4 roster unchanged, "
            f"retain the same no-override guardrails, and keep `{IDP_BLOCKED_SCOPE_BROADER_FULL_PROMOTION}` blocked while repeatability is being confirmed."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP One-Wider Shadow Repeatability Packet",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- blocked_scope: `{s['blocked_scope']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- wider_shadow_safe_lane_admitted: `{s['wider_shadow_safe_lane_admitted']}`",
        f"- frozen_validated_current_target_count: `{s['frozen_validated_current_target_count']}`",
        f"- frozen_additional_anchor_backed_target_count: `{s['frozen_additional_anchor_backed_target_count']}`",
        f"- frozen_total_target_count: `{s['frozen_total_target_count']}`",
        f"- reference_result_status: `{s['reference_result_status']}`",
        f"- reference_corrected_pass_folds: `{s['reference_corrected_pass_folds']}`",
        f"- reference_fold_count: `{s['reference_fold_count']}`",
        f"- page4_fold_pass: `{s['page4_fold_pass']}`",
        f"- tau_k18_fold_pass: `{s['tau_k18_fold_pass']}`",
        f"- row_count: `{s['row_count']}`",
        f"- config_json: `{s['config_json']}`",
        f"- out_prefix: `{s['out_prefix']}`",
        "",
        "## Exact Command",
        "",
        "```bash",
        s["exact_command"],
        "```",
        "",
        "## Success Criteria",
        "",
        f"- {s['success_criteria']}",
        "",
        "## Target Rows",
        "",
        "| target_name | expected_pass | focus_class | repeatability_goal |",
        "| --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['expected_pass']}` | `{row['focus_class']}` | {row['repeatability_goal']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the bounded repeatability packet for the admitted one-wider IDP shadow-safe lane.")
    parser.add_argument("--promotion-resolution-json", default=DEFAULT_PROMOTION_RESOLUTION_JSON)
    parser.add_argument("--broader-result-json", default=DEFAULT_BROADER_RESULT_JSON)
    parser.add_argument("--out-prefix", default=DEFAULT_OUT_PREFIX)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        _load_json(args.promotion_resolution_json),
        _load_json(args.broader_result_json),
        out_prefix=args.out_prefix,
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
