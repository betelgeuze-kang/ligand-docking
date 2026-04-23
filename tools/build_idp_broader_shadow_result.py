#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import os
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows
from tools.operator_surface_contracts import IDP_SAFE_SCOPE_CONTROLLED_PRETEST

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_broader_shadow_full_r1_debug_summary.json"
DEFAULT_COMBINED_GATE_JSON = "runs/idp_3bead_holdout_v7_broader_shadow_full_r1_debug_combined_gate_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_broader_shadow_full_r1_debug_corrected_eval_summary.json"
DEFAULT_REVIEW_RESOLUTION_JSON = "runs/idp_broader_shadow_review_resolution_current.json"
DEFAULT_LAUNCH_PACKET_JSON = "runs/idp_broader_shadow_launch_packet_current.json"
DEFAULT_OUT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_OUT_CSV = "runs/idp_broader_shadow_result_current.csv"
DEFAULT_OUT_MD = "runs/idp_broader_shadow_result_current.md"


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


def _fold_target_name(path: str) -> str:
    stem = Path(path).name
    marker = "_gate_corrected_summary.json"
    if stem.endswith(marker):
        stem = stem[: -len(marker)]
    fold_marker = "_fold"
    idx = stem.find(fold_marker)
    if idx == -1:
        return ""
    remainder = stem[idx + len(fold_marker) :]
    try:
        _, target = remainder.split("_", 1)
    except ValueError:
        return ""
    return target


def _load_fold_gate_rows(holdout_summary_path: Path) -> list[dict[str, Any]]:
    prefix = holdout_summary_path.name.removesuffix("_summary.json")
    pattern = str((holdout_summary_path.parent / f"{prefix}_fold*_gate_corrected_summary.json").resolve())
    rows: list[dict[str, Any]] = []
    for path in sorted(glob.glob(pattern)):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        cls = dict((payload.get("classification_metrics") if isinstance(payload.get("classification_metrics"), dict) else {}) or {})
        rows.append(
            {
                "target_name": _fold_target_name(path),
                "pass": bool(payload.get("pass", False)),
                "dominant_state_accuracy": cls.get("dominant_state_accuracy"),
                "branch_macro_f1": cls.get("branch_macro_f1"),
                "llps_flag_pr_auc": cls.get("llps_flag_pr_auc"),
                "aggregation_relevant_pr_auc": cls.get("aggregation_relevant_pr_auc"),
                "source_json": str(Path(path).resolve()),
            }
        )
    return rows


def build_payload(
    holdout_summary: dict[str, Any],
    combined_gate_summary: dict[str, Any],
    corrected_eval_summary: dict[str, Any],
    review_resolution: dict[str, Any],
    launch_packet: dict[str, Any],
    fold_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    holdout_s = dict(holdout_summary or {})
    combined_s = dict(combined_gate_summary or {})
    corrected_s = dict(corrected_eval_summary or {})
    review_s = dict((review_resolution.get("summary") if isinstance(review_resolution.get("summary"), dict) else {}) or {})
    launch_s = dict((launch_packet.get("summary") if isinstance(launch_packet.get("summary"), dict) else {}) or {})
    kalman_s = dict((corrected_s.get("kalman_shadow") if isinstance(corrected_s.get("kalman_shadow"), dict) else {}) or {})
    cls = dict((combined_s.get("classification_metrics") if isinstance(combined_s.get("classification_metrics"), dict) else {}) or {})
    rank = dict((combined_s.get("ranking_metrics") if isinstance(combined_s.get("ranking_metrics"), dict) else {}) or {})

    would_change_state_count = int(kalman_s.get("would_change_state_count", 0) or 0)
    would_change_gate_count = int(kalman_s.get("would_change_gate_count", 0) or 0)
    would_change_llps_flag_count = int(kalman_s.get("would_change_llps_flag_count", 0) or 0)
    would_change_aggregation_flag_count = int(kalman_s.get("would_change_aggregation_flag_count", 0) or 0)
    shadow_safe_retained = (
        would_change_state_count == 0
        and would_change_gate_count == 0
        and would_change_llps_flag_count == 0
        and would_change_aggregation_flag_count == 0
    )

    fold_count = int(holdout_s.get("fold_count", 0) or 0)
    corrected_pass_folds = int(holdout_s.get("corrected_pass_folds", 0) or 0)
    combined_gate_pass = bool(holdout_s.get("pass", combined_s.get("pass", False)))
    page4_fold = next((row for row in fold_rows if row.get("target_name") == "page4"), {})
    tau_fold = next((row for row in fold_rows if row.get("target_name") == "tau_k18"), {})

    dominant_values = [float(row["dominant_state_accuracy"]) for row in fold_rows if row.get("dominant_state_accuracy") is not None]
    min_fold_dominant_state_accuracy = min(dominant_values) if dominant_values else None
    mean_fold_dominant_state_accuracy = round(sum(dominant_values) / len(dominant_values), 4) if dominant_values else None

    summary = {
        "status": (
            "first_true_broader_shadow_completed_pass"
            if fold_count > 0 and corrected_pass_folds == fold_count and combined_gate_pass and shadow_safe_retained
            else "first_true_broader_shadow_completed_attention_required"
        ),
        "operator_scope_now": str(launch_s.get("operator_scope_now", "")).strip() or IDP_SAFE_SCOPE_CONTROLLED_PRETEST,
        "broader_promotion_blocked": True,
        "shadow_safe_retained": shadow_safe_retained,
        "true_broader_shadow_completed": True,
        "true_broader_shadow_passed": bool(fold_count > 0 and corrected_pass_folds == fold_count and combined_gate_pass),
        "fold_count": fold_count,
        "corrected_pass_folds": corrected_pass_folds,
        "combined_gate_pass": combined_gate_pass,
        "utility_gate_pass": bool(combined_s.get("utility_gate_pass", False)),
        "physics_gate_pass": bool(combined_s.get("physics_gate_pass", False)),
        "target_count": int(combined_s.get("target_count", corrected_s.get("target_count", 0)) or 0),
        "validated_current_target_count": int(review_s.get("validated_current_target_count", 0) or 0),
        "additional_anchor_backed_target_count": int(review_s.get("additional_anchor_backed_target_count", 0) or 0),
        "provisional_expansion_target_count": int(review_s.get("provisional_expansion_target_count", 0) or 0),
        "page4_fold_pass": bool(page4_fold.get("pass", False)),
        "tau_k18_fold_pass": bool(tau_fold.get("pass", False)),
        "min_fold_dominant_state_accuracy": min_fold_dominant_state_accuracy,
        "mean_fold_dominant_state_accuracy": mean_fold_dominant_state_accuracy,
        "branch_macro_f1": cls.get("branch_macro_f1"),
        "dominant_state_accuracy": cls.get("dominant_state_accuracy"),
        "llps_flag_pr_auc": cls.get("llps_flag_pr_auc"),
        "aggregation_relevant_pr_auc": cls.get("aggregation_relevant_pr_auc"),
        "compactness_rank_auc": rank.get("compactness_rank_auc"),
        "helicity_rank_auc": rank.get("helicity_rank_auc"),
        "condensation_rank_auc": rank.get("condensation_rank_auc"),
        "would_change_state_count": would_change_state_count,
        "would_change_gate_count": would_change_gate_count,
        "would_change_llps_flag_count": would_change_llps_flag_count,
        "would_change_aggregation_flag_count": would_change_aggregation_flag_count,
        "config_json": str(launch_s.get("config_json", "")).strip() or str(corrected_s.get("config_json", "")),
        "run_prefix": str(launch_s.get("out_prefix", "")).strip() or str(_resolve(DEFAULT_HOLDOUT_SUMMARY_JSON)).removesuffix("_summary.json"),
        "next_required_step": (
            "Treat this as a clean first true broader shadow-only pass, keep broader_full_idp_promotion blocked, and reopen promotion review with the completed 8-target result instead of the old launch draft."
        ),
    }
    return {"summary": summary, "rows": fold_rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP Broader Shadow Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- true_broader_shadow_completed: `{s['true_broader_shadow_completed']}`",
        f"- true_broader_shadow_passed: `{s['true_broader_shadow_passed']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- combined_gate_pass: `{s['combined_gate_pass']}`",
        f"- utility_gate_pass: `{s['utility_gate_pass']}`",
        f"- physics_gate_pass: `{s['physics_gate_pass']}`",
        f"- target_count: `{s['target_count']}`",
        f"- validated_current_target_count: `{s['validated_current_target_count']}`",
        f"- additional_anchor_backed_target_count: `{s['additional_anchor_backed_target_count']}`",
        f"- provisional_expansion_target_count: `{s['provisional_expansion_target_count']}`",
        f"- page4_fold_pass: `{s['page4_fold_pass']}`",
        f"- tau_k18_fold_pass: `{s['tau_k18_fold_pass']}`",
        f"- min_fold_dominant_state_accuracy: `{s['min_fold_dominant_state_accuracy']}`",
        f"- mean_fold_dominant_state_accuracy: `{s['mean_fold_dominant_state_accuracy']}`",
        f"- branch_macro_f1: `{s['branch_macro_f1']}`",
        f"- dominant_state_accuracy: `{s['dominant_state_accuracy']}`",
        f"- llps_flag_pr_auc: `{s['llps_flag_pr_auc']}`",
        f"- aggregation_relevant_pr_auc: `{s['aggregation_relevant_pr_auc']}`",
        f"- compactness_rank_auc: `{s['compactness_rank_auc']}`",
        f"- helicity_rank_auc: `{s['helicity_rank_auc']}`",
        f"- condensation_rank_auc: `{s['condensation_rank_auc']}`",
        f"- config_json: `{s['config_json']}`",
        f"- run_prefix: `{s['run_prefix']}`",
        "",
        "## Fold Results",
        "",
        "| target | pass | dominant_state_accuracy | branch_macro_f1 | llps_flag_pr_auc | aggregation_relevant_pr_auc |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['target_name']}` | `{row['pass']}` | `{row['dominant_state_accuracy']}` | `{row['branch_macro_f1']}` | `{row['llps_flag_pr_auc']}` | `{row['aggregation_relevant_pr_auc']}` |"
        )
    lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build the completed first-true-broader IDP shadow result artifact.")
    ap.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    ap.add_argument("--combined-gate-json", default=DEFAULT_COMBINED_GATE_JSON)
    ap.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    ap.add_argument("--review-resolution-json", default=DEFAULT_REVIEW_RESOLUTION_JSON)
    ap.add_argument("--launch-packet-json", default=DEFAULT_LAUNCH_PACKET_JSON)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    ap.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    holdout_summary_path = _resolve(args.holdout_summary_json)
    payload = build_payload(
        _read_json(args.holdout_summary_json),
        _read_json(args.combined_gate_json),
        _read_json(args.corrected_eval_json),
        _read_json(args.review_resolution_json),
        _read_json(args.launch_packet_json),
        _load_fold_gate_rows(holdout_summary_path),
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
