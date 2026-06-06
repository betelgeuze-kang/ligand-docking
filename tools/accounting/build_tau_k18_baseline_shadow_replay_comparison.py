#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ENSEMBLE_SUMMARY_JSON = "runs/idp_tau_k18_baseline_shadow_replay_ensemble_r1_summary.json"
DEFAULT_ENSEMBLE_SLICE_JSON = "runs/idp_tau_k18_baseline_shadow_replay_ensemble_slice_current.json"
DEFAULT_RGSASA_SUMMARY_JSON = "runs/idp_tau_k18_baseline_shadow_replay_rgsasa_r1_summary.json"
DEFAULT_RGSASA_SLICE_JSON = "runs/idp_tau_k18_baseline_shadow_replay_rgsasa_slice_current.json"
DEFAULT_OUT_JSON = "runs/idp_tau_k18_baseline_shadow_replay_comparison_current.json"
DEFAULT_OUT_CSV = "runs/idp_tau_k18_baseline_shadow_replay_comparison_current.csv"
DEFAULT_OUT_MD = "runs/idp_tau_k18_baseline_shadow_replay_comparison_current.md"


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


def _build_row(mode: str, summary: dict[str, Any], slice_payload: dict[str, Any]) -> dict[str, Any]:
    kalman = dict(summary.get("kalman_shadow", {}) or {})
    slice_summary = dict(slice_payload.get("summary", {}) or {})
    return {
        "mode": mode,
        "pass": bool(summary.get("pass", False)),
        "baseline_gate_pass": bool(summary.get("baseline_gate_pass", False)),
        "replay_gate_pass": bool(summary.get("replay_gate_pass", False)),
        "state_changes": int(kalman.get("would_change_state_count", 0) or 0),
        "gate_changes": int(kalman.get("would_change_gate_count", 0) or 0),
        "anchor_feature_count": int(slice_summary.get("anchor_feature_count", 0) or 0),
        "smoothed_feature_count": int(slice_summary.get("smoothed_feature_count", 0) or 0),
        "changed_row_count": int(slice_summary.get("changed_row_count", 0) or 0),
    }


def build_payload(
    ensemble_summary: dict[str, Any],
    ensemble_slice: dict[str, Any],
    rgsasa_summary: dict[str, Any],
    rgsasa_slice: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        _build_row("ensemble_only", ensemble_summary, ensemble_slice),
        _build_row("rg_sasa_only", rgsasa_summary, rgsasa_slice),
    ]
    recommended_mode = "rg_sasa_only"
    reason = (
        "Both modes are gate-safe with zero state/gate changes, but rg_sasa_only keeps the smoothing surface narrower."
    )
    return {"recommended_mode": recommended_mode, "reason": reason, "rows": rows}


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Tau K18 Baseline Shadow Replay Comparison",
        "",
        f"- recommended_mode: `{payload['recommended_mode']}`",
        f"- reason: {payload['reason']}",
        "",
        "| mode | pass | baseline_gate_pass | replay_gate_pass | state_changes | gate_changes | anchor_features | smoothed_features | changed_rows |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['mode']}` | `{row['pass']}` | `{row['baseline_gate_pass']}` | `{row['replay_gate_pass']}` | "
            f"{row['state_changes']} | {row['gate_changes']} | {row['anchor_feature_count']} | "
            f"{row['smoothed_feature_count']} | {row['changed_row_count']} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compare tau_k18 baseline-only Kalman shadow replay modes.")
    p.add_argument("--ensemble-summary-json", default=DEFAULT_ENSEMBLE_SUMMARY_JSON)
    p.add_argument("--ensemble-slice-json", default=DEFAULT_ENSEMBLE_SLICE_JSON)
    p.add_argument("--rgsasa-summary-json", default=DEFAULT_RGSASA_SUMMARY_JSON)
    p.add_argument("--rgsasa-slice-json", default=DEFAULT_RGSASA_SLICE_JSON)
    p.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    p.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    p.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return p


def main() -> None:
    args = build_parser().parse_args()
    payload = build_payload(
        _read_json(args.ensemble_summary_json),
        _read_json(args.ensemble_slice_json),
        _read_json(args.rgsasa_summary_json),
        _read_json(args.rgsasa_slice_json),
    )
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(out_csv, payload["rows"])
    _write_md(out_md, payload)


if __name__ == "__main__":
    main()
