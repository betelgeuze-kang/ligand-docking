#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODE_COMPARISON_JSON = "runs/gpcr_residual_chembl50_v4_mode_comparison_current.json"
DEFAULT_PROGRESS_JSON = "runs/gpcr_residual_progression_comparison_current.json"
DEFAULT_DECISION_JSON = "runs/gpcr_residual_apply_decision_narrow_v2_current.json"
DEFAULT_FAILURE_ANALYSIS_JSON = "runs/gpcr_100k_failure_analysis_core_decoy_intrusion_shadow_v1_current.json"
DEFAULT_OUT_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_OUT_CSV = "runs/gpcr_hard_decoy_residual_proof_current.csv"
DEFAULT_OUT_MD = "runs/gpcr_hard_decoy_residual_proof_current.md"

MEAN_DELTA_CAP = 0.01
PR_REGRESSION_WARN_THRESHOLD = -1e-12

CLAIM_BOUNDARY = (
    "GPCR hard-decoy residual proof only; evaluates existing local locked-decoy residual comparison evidence. "
    "It does not run docking, train models, alter customer-facing ranking defaults, promote assist/production mode, "
    "upload, submit, email, archive, externalize, or delete files. EF1/top-k gains are treated as hard-decoy "
    "intrusion-reduction proxy evidence unless a direct top-decoy count artifact is supplied."
)


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _read_json_if_present(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _mode_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = packet.get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []


def _failure_summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary", packet)
    return summary if isinstance(summary, dict) else {}


def _proof_row(row: dict[str, Any]) -> dict[str, Any]:
    task_id = _text(row.get("task_id"))
    baseline_pass = bool(row.get("baseline_pass") is True)
    shadow_pass = bool(row.get("shadow_pass") is True)
    apply_pass = bool(row.get("apply_pass") is True)
    delta_ef1_shadow = _float(row.get("delta_ef1_shadow_vs_baseline"))
    delta_ef1_apply = _float(row.get("delta_ef1_apply_vs_baseline"))
    delta_pr_shadow = _float(row.get("delta_pr_auc_shadow_vs_baseline"))
    delta_pr_apply = _float(row.get("delta_pr_auc_apply_vs_baseline"))
    shadow_mean_delta = abs(_float(row.get("shadow_residual_mean_delta")))
    apply_mean_delta = abs(_float(row.get("apply_residual_mean_delta")))
    pass_to_fail = baseline_pass and (not shadow_pass or not apply_pass)
    ef1_gain = max(delta_ef1_shadow, delta_ef1_apply)
    pr_regression = min(delta_pr_shadow, delta_pr_apply)
    correction_norm_ok = max(shadow_mean_delta, apply_mean_delta) <= MEAN_DELTA_CAP
    intrusion_reduction_proxy = ef1_gain > 0
    binder_retention_ok = baseline_pass and shadow_pass and apply_pass and delta_ef1_shadow >= 0 and delta_ef1_apply >= 0
    return {
        "task_id": task_id,
        "baseline_pass": baseline_pass,
        "shadow_pass": shadow_pass,
        "apply_pass": apply_pass,
        "pass_to_fail_regression": pass_to_fail,
        "delta_ef1_shadow_vs_baseline": delta_ef1_shadow,
        "delta_ef1_apply_vs_baseline": delta_ef1_apply,
        "best_delta_ef1_vs_baseline": ef1_gain,
        "delta_pr_auc_shadow_vs_baseline": delta_pr_shadow,
        "delta_pr_auc_apply_vs_baseline": delta_pr_apply,
        "min_delta_pr_auc_vs_baseline": pr_regression,
        "pr_auc_regression_warning": pr_regression < PR_REGRESSION_WARN_THRESHOLD,
        "shadow_residual_mean_delta_abs": shadow_mean_delta,
        "apply_residual_mean_delta_abs": apply_mean_delta,
        "correction_norm_cap": MEAN_DELTA_CAP,
        "correction_norm_cap_ok": correction_norm_ok,
        "intrusion_reduction_proxy": intrusion_reduction_proxy,
        "binder_retention_ok": binder_retention_ok,
        "release_blocker": pass_to_fail or not correction_norm_ok or not binder_retention_ok,
        "reason": (
            "EF1/top-k proxy improves while pass state and correction magnitude stay within guardrails."
            if intrusion_reduction_proxy and binder_retention_ok and correction_norm_ok
            else "No EF1/top-k proxy gain or a guardrail is not satisfied."
        ),
    }


def build_gpcr_hard_decoy_residual_proof(
    *,
    mode_comparison_packet: dict[str, Any],
    progression_packet: dict[str, Any] | None = None,
    decision_packet: dict[str, Any] | None = None,
    failure_analysis_packet: dict[str, Any] | None = None,
    mode_comparison_path: str = DEFAULT_MODE_COMPARISON_JSON,
    progression_path: str = DEFAULT_PROGRESS_JSON,
    decision_path: str = DEFAULT_DECISION_JSON,
    failure_analysis_path: str = DEFAULT_FAILURE_ANALYSIS_JSON,
) -> dict[str, Any]:
    progression_packet = progression_packet or {}
    decision_packet = decision_packet or {}
    failure_analysis_packet = failure_analysis_packet or {}
    rows = [_proof_row(row) for row in _mode_rows(mode_comparison_packet)]
    failure = _failure_summary(failure_analysis_packet)
    task_count = len(rows)
    pass_to_fail_count = sum(1 for row in rows if row["pass_to_fail_regression"])
    correction_norm_fail_count = sum(1 for row in rows if not row["correction_norm_cap_ok"])
    binder_retention_fail_count = sum(1 for row in rows if not row["binder_retention_ok"])
    intrusion_reduction_task_count = sum(1 for row in rows if row["intrusion_reduction_proxy"])
    pr_regression_warning_count = sum(1 for row in rows if row["pr_auc_regression_warning"])
    direct_failure_slice_present = bool(failure.get("status") == "computed" or failure.get("source_rows_available") is True)
    first_binder_retention_ok = _float(failure.get("first_positive_rank_shift")) <= 0 if direct_failure_slice_present else bool(rows)
    top20_binder_retention_ok = (
        _float(failure.get("scaleup_top20_binder_count")) >= _float(failure.get("baseline_top20_binder_count"))
        if direct_failure_slice_present
        else bool(rows)
    )
    pass_regressions_from_decision = int(decision_packet.get("pass_regressions", 0) or 0) if decision_packet else pass_to_fail_count
    proof_ready = bool(
        task_count > 0
        and intrusion_reduction_task_count > 0
        and pass_to_fail_count == 0
        and pass_regressions_from_decision == 0
        and correction_norm_fail_count == 0
        and binder_retention_fail_count == 0
        and first_binder_retention_ok
        and top20_binder_retention_ok
    )
    progression_summary = progression_packet.get("summary", {}) if isinstance(progression_packet.get("summary"), dict) else {}
    summary = {
        "packet_type": "gpcr_hard_decoy_residual_proof",
        "status": "gpcr_hard_decoy_residual_proof_ready" if proof_ready else "blocked_gpcr_hard_decoy_residual_proof",
        "gpcr_hard_decoy_residual_proof_ready": proof_ready,
        "proof_ready": proof_ready,
        "regression_gate_ready": proof_ready,
        "mode_comparison_artifact": mode_comparison_path,
        "progression_artifact": progression_path,
        "decision_artifact": decision_path,
        "failure_analysis_artifact": failure_analysis_path,
        "task_count": task_count,
        "intrusion_reduction_task_count": intrusion_reduction_task_count,
        "pass_to_fail_regression_count": pass_to_fail_count,
        "pass_regressions_from_decision": pass_regressions_from_decision,
        "correction_norm_fail_count": correction_norm_fail_count,
        "binder_retention_fail_count": binder_retention_fail_count,
        "pr_auc_regression_warning_count": pr_regression_warning_count,
        "first_binder_retention_ok": first_binder_retention_ok,
        "top20_binder_retention_ok": top20_binder_retention_ok,
        "direct_failure_slice_present": direct_failure_slice_present,
        "baseline_top20_binder_count": failure.get("baseline_top20_binder_count"),
        "scaleup_top20_binder_count": failure.get("scaleup_top20_binder_count"),
        "first_positive_rank_shift": failure.get("first_positive_rank_shift"),
        "correction_norm_cap": MEAN_DELTA_CAP,
        "core_v4_apply_preserves_baseline": bool(progression_summary.get("core_v4_apply_preserves_baseline")),
        "chembl50_v4_apply_has_ef1_gain": bool(progression_summary.get("chembl50_v4_apply_has_ef1_gain")),
        "assist_promotion_allowed": False,
        "production_promotion_allowed": False,
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Proceed to public benchmark residual regression gate."
            if proof_ready
            else "Repair GPCR hard-decoy residual proof before public benchmark regression."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# GPCR Hard-Decoy Residual Proof",
        "",
        f"- status: `{s['status']}`",
        f"- proof_ready: `{s['proof_ready']}`",
        f"- task_count: `{s['task_count']}`",
        f"- intrusion_reduction_task_count: `{s['intrusion_reduction_task_count']}`",
        f"- pass_to_fail_regression_count: `{s['pass_to_fail_regression_count']}`",
        f"- correction_norm_fail_count: `{s['correction_norm_fail_count']}`",
        f"- binder_retention_fail_count: `{s['binder_retention_fail_count']}`",
        f"- pr_auc_regression_warning_count: `{s['pr_auc_regression_warning_count']}`",
        f"- first_binder_retention_ok: `{s['first_binder_retention_ok']}`",
        f"- top20_binder_retention_ok: `{s['top20_binder_retention_ok']}`",
        f"- assist_promotion_allowed: `{s['assist_promotion_allowed']}`",
        f"- production_promotion_allowed: `{s['production_promotion_allowed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Task Rows",
        "",
        "| task | ef1 gain | pr warning | pass->fail | retention | norm ok | reason |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['task_id']}` | `{row['best_delta_ef1_vs_baseline']}` | `{row['pr_auc_regression_warning']}` | "
            f"`{row['pass_to_fail_regression']}` | `{row['binder_retention_ok']}` | `{row['correction_norm_cap_ok']}` | {row['reason']} |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPCR hard-decoy residual proof gate from existing local evidence.")
    parser.add_argument("--mode-comparison-json", default=DEFAULT_MODE_COMPARISON_JSON)
    parser.add_argument("--progression-json", default=DEFAULT_PROGRESS_JSON)
    parser.add_argument("--decision-json", default=DEFAULT_DECISION_JSON)
    parser.add_argument("--failure-analysis-json", default=DEFAULT_FAILURE_ANALYSIS_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_gpcr_hard_decoy_residual_proof(
        mode_comparison_packet=_read_json_if_present(args.mode_comparison_json),
        progression_packet=_read_json_if_present(args.progression_json),
        decision_packet=_read_json_if_present(args.decision_json),
        failure_analysis_packet=_read_json_if_present(args.failure_analysis_json),
        mode_comparison_path=args.mode_comparison_json,
        progression_path=args.progression_json,
        decision_path=args.decision_json,
        failure_analysis_path=args.failure_analysis_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
