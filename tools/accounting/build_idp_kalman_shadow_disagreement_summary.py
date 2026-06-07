#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_kfshadow_2026-03-26_r1_summary.json"
DEFAULT_OUT_JSON = "runs/idp_kalman_shadow_disagreement_summary_current.json"
DEFAULT_OUT_CSV = "runs/idp_kalman_shadow_disagreement_summary_current.csv"
DEFAULT_OUT_MD = "runs/idp_kalman_shadow_disagreement_summary_current.md"


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


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def build_payload(holdout_summary: dict[str, Any], corrected_eval: dict[str, Any]) -> dict[str, Any]:
    rows = list(corrected_eval.get("targets", []))
    kf_rows = [row for row in rows if "kf_shadow_enabled" in row]
    fold_map: dict[str, list[dict[str, Any]]] = {}
    for row in kf_rows:
        fold = str(row.get("holdout_fold", "") or "unassigned")
        fold_map.setdefault(fold, []).append(row)

    def summarize(group_rows: list[dict[str, Any]], fold_name: str) -> dict[str, Any]:
        enabled_count = sum(int(bool(row.get("kf_shadow_enabled", False))) for row in group_rows)
        state_change_count = sum(int(bool(row.get("would_have_changed_state", False))) for row in group_rows)
        gate_change_count = sum(int(bool(row.get("would_have_changed_gate", False))) for row in group_rows)
        mean_abs_deltas = [float(row.get("kf_shadow_mean_abs_delta", 0.0) or 0.0) for row in group_rows]
        max_abs_deltas = [float(row.get("kf_shadow_max_abs_delta", 0.0) or 0.0) for row in group_rows]
        obs_noise = [float(row.get("kf_shadow_obs_noise_scale", 0.0) or 0.0) for row in group_rows]
        process_noise = [float(row.get("kf_shadow_process_noise_scale", 0.0) or 0.0) for row in group_rows]
        support_counts = [int(row.get("kf_shadow_support_count", 0) or 0) for row in group_rows]
        statuses = sorted({str(row.get("kf_shadow_status", "") or "") for row in group_rows if str(row.get("kf_shadow_status", "") or "")})
        families = sorted({str(row.get("kf_shadow_family_token", "") or "") for row in group_rows if str(row.get("kf_shadow_family_token", "") or "")})
        return {
            "fold": fold_name,
            "row_count": int(len(group_rows)),
            "kf_enabled_row_count": int(enabled_count),
            "identity_shadow_row_count": int(sum(1 for row in group_rows if str(row.get("kf_shadow_status", "")) == "identity_shadow")),
            "feature_state_shadow_row_count": int(
                sum(1 for row in group_rows if str(row.get("kf_shadow_status", "")) == "feature_state_v1_shadow")
            ),
            "would_have_changed_state_count": int(state_change_count),
            "would_have_changed_gate_count": int(gate_change_count),
            "mean_kf_mean_abs_delta": _mean(mean_abs_deltas),
            "max_kf_max_abs_delta": max(max_abs_deltas) if max_abs_deltas else 0.0,
            "mean_obs_noise_scale": _mean(obs_noise),
            "mean_process_noise_scale": _mean(process_noise),
            "mean_support_count": _mean([float(x) for x in support_counts]),
            "kf_statuses": "|".join(statuses) if statuses else "",
            "kf_family_tokens": "|".join(families) if families else "",
        }

    fold_rows = [summarize(group_rows, fold_name) for fold_name, group_rows in sorted(fold_map.items())]
    overall = summarize(kf_rows, "all")
    summary = {
        "holdout_summary_json": str(_resolve(str(holdout_summary.get("summary_json", "")) if holdout_summary.get("summary_json") else "")) if holdout_summary.get("summary_json") else "",
        "corrected_eval_json": str(_resolve(str(holdout_summary.get("combined_corrected_eval_json", "")))),
        "fold_count": int(holdout_summary.get("fold_count", 0) or 0),
        "target_row_count": int(len(rows)),
        "kf_schema_row_count": int(len(kf_rows)),
        "kf_identity_shadow_ready": bool(kf_rows) and overall["would_have_changed_state_count"] == 0 and overall["would_have_changed_gate_count"] == 0,
        "next_required_step": (
            "Promote from identity shadow to real feature/state smoothing only after a completed run still shows zero would_have_changed_state "
            "and zero would_have_changed_gate counts."
        ),
    }
    return {"summary": summary, "overall": overall, "fold_rows": fold_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    overall = payload["overall"]
    lines = [
        "# IDP Kalman Shadow Disagreement Summary",
        "",
        f"- fold_count: `{summary['fold_count']}`",
        f"- target_row_count: `{summary['target_row_count']}`",
        f"- kf_schema_row_count: `{summary['kf_schema_row_count']}`",
        f"- kf_identity_shadow_ready: `{summary['kf_identity_shadow_ready']}`",
        "",
        "## Overall",
        "",
        f"- row_count: `{overall['row_count']}`",
        f"- kf_enabled_row_count: `{overall['kf_enabled_row_count']}`",
        f"- identity_shadow_row_count: `{overall['identity_shadow_row_count']}`",
        f"- feature_state_shadow_row_count: `{overall['feature_state_shadow_row_count']}`",
        f"- would_have_changed_state_count: `{overall['would_have_changed_state_count']}`",
        f"- would_have_changed_gate_count: `{overall['would_have_changed_gate_count']}`",
        f"- mean_kf_mean_abs_delta: `{overall['mean_kf_mean_abs_delta']}`",
        f"- max_kf_max_abs_delta: `{overall['max_kf_max_abs_delta']}`",
        f"- mean_obs_noise_scale: `{overall['mean_obs_noise_scale']}`",
        f"- mean_process_noise_scale: `{overall['mean_process_noise_scale']}`",
        "",
        "## Fold Rows",
        "",
        "| fold | row_count | identity | feature_state | state_changes | gate_changes | mean_abs_delta | max_abs_delta | statuses |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["fold_rows"]:
        lines.append(
            f"| {row['fold']} | {row['row_count']} | {row['identity_shadow_row_count']} | {row['feature_state_shadow_row_count']} | "
            f"{row['would_have_changed_state_count']} | {row['would_have_changed_gate_count']} | "
            f"{row['mean_kf_mean_abs_delta']:.6f} | {row['max_kf_max_abs_delta']:.6f} | {row['kf_statuses']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {summary['next_required_step']}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a holdout-level IDP Kalman shadow disagreement summary.")
    parser.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    holdout_summary = _read_json(args.holdout_summary_json)
    corrected_eval_json = str(holdout_summary.get("combined_corrected_eval_json", "")).strip()
    if not corrected_eval_json:
        raise SystemExit("holdout summary missing combined_corrected_eval_json")
    payload = build_payload(holdout_summary, _read_json(corrected_eval_json))
    out_json = _resolve(args.out_json)
    out_csv = _resolve(args.out_csv)
    out_md = _resolve(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_csv(out_csv, payload["fold_rows"])
    _write_markdown(out_md, payload)


if __name__ == "__main__":
    main()
