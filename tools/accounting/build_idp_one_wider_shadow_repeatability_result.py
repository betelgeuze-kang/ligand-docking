#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PACKET_JSON = "runs/idp_one_wider_shadow_repeatability_packet_current.json"
DEFAULT_REFERENCE_RESULT_JSON = "runs/idp_broader_shadow_result_current.json"
DEFAULT_HOLDOUT_SUMMARY_JSON = "runs/idp_3bead_holdout_v7_onewider_repeatability_r1_summary.json"
DEFAULT_COMBINED_GATE_JSON = "runs/idp_3bead_holdout_v7_onewider_repeatability_r1_combined_gate_summary.json"
DEFAULT_CORRECTED_EVAL_JSON = "runs/idp_3bead_holdout_v7_onewider_repeatability_r1_corrected_eval_summary.json"
DEFAULT_OUT_JSON = "runs/idp_one_wider_shadow_repeatability_result_current.json"
DEFAULT_OUT_CSV = "runs/idp_one_wider_shadow_repeatability_result_current.csv"
DEFAULT_OUT_MD = "runs/idp_one_wider_shadow_repeatability_result_current.md"


def _resolve(path_like: str) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _maybe_read_json(path_like: str) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
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
    if not holdout_summary_path.exists():
        return []
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
            }
        )
    return rows


def build_payload(
    packet: dict[str, Any] | None = None,
    reference_result: dict[str, Any] | None = None,
    holdout_summary: dict[str, Any] | None = None,
    combined_gate_summary: dict[str, Any] | None = None,
    corrected_eval_summary: dict[str, Any] | None = None,
    fold_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    packet_s = dict(((packet or {}).get("summary", {}) if isinstance((packet or {}).get("summary", {}), dict) else {}) or {})
    reference_s = dict(((reference_result or {}).get("summary", {}) if isinstance((reference_result or {}).get("summary", {}), dict) else {}) or {})
    holdout_s = dict(holdout_summary or {})
    combined_s = dict(combined_gate_summary or {})
    corrected_s = dict(corrected_eval_summary or {})
    rows = [dict(row) for row in (fold_rows or [])]
    kalman_s = dict((corrected_s.get("kalman_shadow", {}) if isinstance(corrected_s.get("kalman_shadow"), dict) else {}) or {})
    cls = dict((combined_s.get("classification_metrics", {}) if isinstance(combined_s.get("classification_metrics"), dict) else {}) or {})

    summary_exists = bool(holdout_s)
    corrected_exists = bool(corrected_s)
    fold_count = int(holdout_s.get("fold_count", 0) or 0)
    corrected_pass_folds = int(holdout_s.get("corrected_pass_folds", 0) or 0)
    reference_corrected_pass_folds = int(reference_s.get("corrected_pass_folds", 0) or 0)
    would_change_state_count = int(kalman_s.get("would_change_state_count", 0) or 0)
    would_change_gate_count = int(kalman_s.get("would_change_gate_count", 0) or 0)
    would_change_llps_flag_count = int(kalman_s.get("would_change_llps_flag_count", 0) or 0)
    would_change_aggregation_flag_count = int(kalman_s.get("would_change_aggregation_flag_count", 0) or 0)
    shadow_safe_retained = (
        corrected_exists
        and would_change_state_count == 0
        and would_change_gate_count == 0
        and would_change_llps_flag_count == 0
        and would_change_aggregation_flag_count == 0
    )
    no_corrected_pass_regression_vs_reference = summary_exists and corrected_pass_folds >= reference_corrected_pass_folds
    combined_gate_pass = bool(holdout_s.get("pass", combined_s.get("pass", False)))
    page4_fold = next((row for row in rows if row.get("target_name") == "page4"), {})
    tau_fold = next((row for row in rows if row.get("target_name") == "tau_k18"), {})

    if not summary_exists:
        status = "one_wider_shadow_repeatability_running_or_not_yet_summarized"
        next_required_step = "Wait for the bounded one-wider repeatability rerun to finish. Keep broader_full_idp_promotion blocked and do not widen the frozen 8-target roster meanwhile."
    elif shadow_safe_retained and combined_gate_pass and corrected_pass_folds == fold_count and no_corrected_pass_regression_vs_reference:
        status = "one_wider_shadow_repeatability_confirmed"
        next_required_step = "Treat the admitted one-wider shadow-safe lane as repeatability-confirmed, keep broader_full_idp_promotion blocked, and only reopen any broader expansion through an explicit new promotion review."
    else:
        status = "one_wider_shadow_repeatability_attention_required"
        next_required_step = "Do not widen the lane. Inspect the repeatability regression details, keep broader_full_idp_promotion blocked, and restore 8-target repeatability before any new expansion review."

    summary = {
        "status": status,
        "operator_scope_now": str(packet_s.get("operator_scope_now", "")).strip(),
        "broader_promotion_blocked": True,
        "summary_exists": summary_exists,
        "corrected_eval_exists": corrected_exists,
        "fold_count": fold_count,
        "corrected_pass_folds": corrected_pass_folds,
        "reference_corrected_pass_folds": reference_corrected_pass_folds,
        "combined_gate_pass": combined_gate_pass,
        "shadow_safe_retained": shadow_safe_retained,
        "no_corrected_pass_regression_vs_reference": no_corrected_pass_regression_vs_reference,
        "page4_fold_pass": bool(page4_fold.get("pass", False)),
        "tau_k18_fold_pass": bool(tau_fold.get("pass", False)),
        "dominant_state_accuracy": cls.get("dominant_state_accuracy"),
        "would_change_state_count": would_change_state_count,
        "would_change_gate_count": would_change_gate_count,
        "would_change_llps_flag_count": would_change_llps_flag_count,
        "would_change_aggregation_flag_count": would_change_aggregation_flag_count,
        "out_prefix": str(packet_s.get("out_prefix", "")).strip(),
        "next_required_step": next_required_step,
    }
    return {"summary": summary, "rows": rows}


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    s = payload["summary"]
    lines = [
        "# IDP One-Wider Shadow Repeatability Result",
        "",
        f"- status: `{s['status']}`",
        f"- operator_scope_now: `{s['operator_scope_now']}`",
        f"- broader_promotion_blocked: `{s['broader_promotion_blocked']}`",
        f"- summary_exists: `{s['summary_exists']}`",
        f"- corrected_eval_exists: `{s['corrected_eval_exists']}`",
        f"- fold_count: `{s['fold_count']}`",
        f"- corrected_pass_folds: `{s['corrected_pass_folds']}`",
        f"- reference_corrected_pass_folds: `{s['reference_corrected_pass_folds']}`",
        f"- combined_gate_pass: `{s['combined_gate_pass']}`",
        f"- shadow_safe_retained: `{s['shadow_safe_retained']}`",
        f"- no_corrected_pass_regression_vs_reference: `{s['no_corrected_pass_regression_vs_reference']}`",
        f"- page4_fold_pass: `{s['page4_fold_pass']}`",
        f"- tau_k18_fold_pass: `{s['tau_k18_fold_pass']}`",
        f"- dominant_state_accuracy: `{s['dominant_state_accuracy']}`",
        f"- would_change_state_count: `{s['would_change_state_count']}`",
        f"- would_change_gate_count: `{s['would_change_gate_count']}`",
        f"- would_change_llps_flag_count: `{s['would_change_llps_flag_count']}`",
        f"- would_change_aggregation_flag_count: `{s['would_change_aggregation_flag_count']}`",
        f"- out_prefix: `{s['out_prefix']}`",
        "",
    ]
    if payload["rows"]:
        lines.extend(
            [
                "## Fold Results",
                "",
                "| target_name | pass | dominant_state_accuracy | branch_macro_f1 | llps_flag_pr_auc | aggregation_relevant_pr_auc |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in payload["rows"]:
            lines.append(
                f"| `{row['target_name']}` | `{row['pass']}` | `{row['dominant_state_accuracy']}` | `{row['branch_macro_f1']}` | `{row['llps_flag_pr_auc']}` | `{row['aggregation_relevant_pr_auc']}` |"
            )
        lines.extend(["", "## Next Step", "", f"- {s['next_required_step']}", ""])
    else:
        lines.extend(["## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the current result surface for the admitted one-wider IDP shadow-safe repeatability rerun.")
    parser.add_argument("--packet-json", default=DEFAULT_PACKET_JSON)
    parser.add_argument("--reference-result-json", default=DEFAULT_REFERENCE_RESULT_JSON)
    parser.add_argument("--holdout-summary-json", default=DEFAULT_HOLDOUT_SUMMARY_JSON)
    parser.add_argument("--combined-gate-json", default=DEFAULT_COMBINED_GATE_JSON)
    parser.add_argument("--corrected-eval-json", default=DEFAULT_CORRECTED_EVAL_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    holdout_summary_path = _resolve(args.holdout_summary_json)
    payload = build_payload(
        _maybe_read_json(args.packet_json),
        _maybe_read_json(args.reference_result_json),
        _maybe_read_json(args.holdout_summary_json),
        _maybe_read_json(args.combined_gate_json),
        _maybe_read_json(args.corrected_eval_json),
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
