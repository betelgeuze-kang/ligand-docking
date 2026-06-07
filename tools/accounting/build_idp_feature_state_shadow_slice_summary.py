#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_EVAL_SUMMARY_JSON = "runs/idp_page4_feature_state_v1_shadow_current_summary.json"
DEFAULT_OUT_JSON = "runs/idp_page4_feature_state_v1_shadow_slice_current.json"
DEFAULT_OUT_CSV = "runs/idp_page4_feature_state_v1_shadow_slice_current.csv"
DEFAULT_OUT_MD = "runs/idp_page4_feature_state_v1_shadow_slice_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _read_json(path_like: str) -> dict[str, Any]:
    with _resolve(path_like).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_payload(eval_summary: dict[str, Any]) -> dict[str, Any]:
    rows = list(eval_summary.get("targets", []))
    changed_rows = [
        row for row in rows
        if bool(row.get("would_have_changed_state", False))
        or bool(row.get("would_have_changed_llps_flag", False))
        or bool(row.get("would_have_changed_aggregation_flag", False))
        or bool(row.get("would_have_changed_gate", False))
    ]
    anchor_policy_counts: dict[str, int] = {}
    row_summary: list[dict[str, Any]] = []
    for row in rows:
        policy = str(row.get("kf_shadow_anchor_policy", "") or "")
        anchor_policy_counts[policy] = anchor_policy_counts.get(policy, 0) + 1
        row_summary.append(
            {
                "condition_group": str(row.get("condition_group", "")),
                "kf_shadow_anchor_policy": policy,
                "would_have_changed_state": int(bool(row.get("would_have_changed_state", False))),
                "would_have_changed_llps_flag": int(bool(row.get("would_have_changed_llps_flag", False))),
                "would_have_changed_aggregation_flag": int(bool(row.get("would_have_changed_aggregation_flag", False))),
                "would_have_changed_gate": int(bool(row.get("would_have_changed_gate", False))),
                "kf_shadow_mean_abs_delta": float(row.get("kf_shadow_mean_abs_delta", 0.0) or 0.0),
                "kf_shadow_max_abs_delta": float(row.get("kf_shadow_max_abs_delta", 0.0) or 0.0),
            }
        )
    kalman = dict(eval_summary.get("kalman_shadow", {}) or {})
    summary = {
        "target_count": int(len(rows)),
        "changed_row_count": int(len(changed_rows)),
        "anchor_policy_counts": anchor_policy_counts,
        "kalman_status": str(kalman.get("status", "")),
        "kalman_mode": str(kalman.get("mode", "")),
        "provisional_anchor_row_count": int(kalman.get("provisional_anchor_row_count", 0) or 0),
        "anchor_feature_count": int(kalman.get("anchor_feature_count", 0) or 0),
        "smoothed_feature_count": int(kalman.get("smoothed_feature_count", 0) or 0),
        "would_change_state_count": int(kalman.get("would_change_state_count", 0) or 0),
        "would_change_gate_count": int(kalman.get("would_change_gate_count", 0) or 0),
        "next_required_step": (
            "Feature/state shadow is safe to observe, but provisional-anchor rows are currently abstained. "
            "Promote only after construct-matched anchors exist for the slice."
        ),
    }
    return {"summary": summary, "row_summary": row_summary}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    lines = [
        "# IDP Feature/State Shadow Slice Summary",
        "",
        f"- kalman_status: `{summary['kalman_status']}`",
        f"- kalman_mode: `{summary['kalman_mode']}`",
        f"- target_count: `{summary['target_count']}`",
        f"- changed_row_count: `{summary['changed_row_count']}`",
        f"- provisional_anchor_row_count: `{summary['provisional_anchor_row_count']}`",
        f"- anchor_feature_count: `{summary['anchor_feature_count']}`",
        f"- smoothed_feature_count: `{summary['smoothed_feature_count']}`",
        f"- would_change_state_count: `{summary['would_change_state_count']}`",
        f"- would_change_gate_count: `{summary['would_change_gate_count']}`",
        "",
        "## Anchor Policies",
        "",
    ]
    for key, value in sorted(summary["anchor_policy_counts"].items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| condition | policy | state | llps | agg | gate | mean_abs_delta | max_abs_delta |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["row_summary"]:
        lines.append(
            f"| {row['condition_group']} | {row['kf_shadow_anchor_policy']} | {row['would_have_changed_state']} | "
            f"{row['would_have_changed_llps_flag']} | {row['would_have_changed_aggregation_flag']} | "
            f"{row['would_have_changed_gate']} | {row['kf_shadow_mean_abs_delta']:.6f} | {row['kf_shadow_max_abs_delta']:.6f} |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize an IDP feature/state shadow slice evaluator output.")
    parser.add_argument("--eval-summary-json", default=DEFAULT_EVAL_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(_read_json(args.eval_summary_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["row_summary"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
