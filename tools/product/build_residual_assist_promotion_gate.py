#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESIDUAL_SHADOW_JSON = "runs/residual_shadow_ab_current.json"
DEFAULT_GPCR_PROOF_JSON = "runs/gpcr_hard_decoy_residual_proof_current.json"
DEFAULT_GPCR_ASSIST_SELECTION_JSON = "runs/gpcr_residual_assist_candidate_selection_current.json"
DEFAULT_PUBLIC_REGRESSION_JSON = "runs/public_benchmark_residual_regression_gate_current.json"
DEFAULT_PUBLIC_ASSIST_GATE_JSON = "runs/public_benchmark_residual_assist_comparison_gate_current.json"
DEFAULT_E2E_BENCHMARK_JSON = "runs/product_end_to_end_rocm_benchmark_current.json"
DEFAULT_OUT_JSON = "runs/residual_assist_promotion_gate_current.json"
DEFAULT_OUT_CSV = "runs/residual_assist_promotion_gate_current.csv"
DEFAULT_OUT_MD = "runs/residual_assist_promotion_gate_current.md"

CLAIM_BOUNDARY = (
    "Residual assist promotion gate only; audits existing local shadow, GPCR, public benchmark, and ROCm end-to-end "
    "evidence. It does not train a residual model, alter rankings, promote assist/production mode, run docking, run "
    "benchmarks, upload, submit, email, archive, externalize, or delete files."
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


def _summary(packet: dict[str, Any]) -> dict[str, Any]:
    summary = packet.get("summary")
    return summary if isinstance(summary, dict) else {}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _row(check_id: str, status: str, observed: str, required: str, reason: str, source_artifact: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "observed": observed,
        "required": required,
        "reason": reason,
        "source_artifact": source_artifact,
        "release_blocker": status != "pass",
        "execution_enabled": False,
        "benchmark_executed": False,
        "external_state_mutated": False,
    }


def build_residual_assist_promotion_gate(
    *,
    residual_shadow_packet: dict[str, Any],
    gpcr_proof_packet: dict[str, Any],
    gpcr_assist_selection_packet: dict[str, Any] | None = None,
    public_regression_packet: dict[str, Any],
    public_assist_gate_packet: dict[str, Any] | None = None,
    e2e_benchmark_packet: dict[str, Any],
    residual_shadow_path: str = DEFAULT_RESIDUAL_SHADOW_JSON,
    gpcr_proof_path: str = DEFAULT_GPCR_PROOF_JSON,
    gpcr_assist_selection_path: str = DEFAULT_GPCR_ASSIST_SELECTION_JSON,
    public_regression_path: str = DEFAULT_PUBLIC_REGRESSION_JSON,
    public_assist_gate_path: str = DEFAULT_PUBLIC_ASSIST_GATE_JSON,
    e2e_benchmark_path: str = DEFAULT_E2E_BENCHMARK_JSON,
) -> dict[str, Any]:
    residual = _summary(residual_shadow_packet)
    gpcr = _summary(gpcr_proof_packet)
    assist_selection = _summary(gpcr_assist_selection_packet or {})
    public = _summary(public_regression_packet)
    public_assist = _summary(public_assist_gate_packet or {})
    e2e = _summary(e2e_benchmark_packet)

    shadow_ready = residual.get("shadow_ab_ready") is True or residual.get("residual_shadow_ab_ready") is True or residual.get("scaffold_ready") is True
    raw_preserved = residual.get("raw_baseline_preserved") is True
    no_ranking_change = residual.get("no_customer_facing_ranking_change") is True
    abstention_fields_present = residual.get("abstention_fields_present") is True
    gpcr_no_pass_to_fail = _int(gpcr.get("pass_to_fail_regression_count")) == 0 and _int(gpcr.get("pass_regressions_from_decision")) == 0
    gpcr_hard_decoy_support = _int(gpcr.get("intrusion_reduction_task_count")) >= 1 and _int(gpcr.get("binder_retention_fail_count")) == 0
    assist_selection_ready = assist_selection.get("assist_candidate_ready") is True
    gpcr_pr_auc_clean = (
        _int(gpcr.get("pr_auc_regression_warning_count")) == 0
        or (
            assist_selection_ready
            and _int(assist_selection.get("pr_auc_regression_warning_count")) == 0
            and _int(assist_selection.get("pass_to_fail_regression_count")) == 0
            and _int(assist_selection.get("residual_applied_task_count")) > 0
        )
    )
    public_shadow_clean = _int(public.get("pass_to_fail_regression_count")) == 0 and _int(public.get("fail_suite_count")) == 0
    public_assist_comparison_ready = (
        public_assist.get("assist_comparison_gate_ready") is True
        or public.get("assist_promotion_allowed") is True
    )
    e2e_ready = e2e.get("benchmark_ready") is True and _float(e2e.get("jobs_per_hour")) > 0

    rows = [
        _row(
            "shadow_scaffold_ready",
            "pass" if shadow_ready and raw_preserved and no_ranking_change else "fail",
            f"shadow_ready={shadow_ready}; raw_preserved={raw_preserved}; no_ranking_change={no_ranking_change}",
            "shadow scaffold ready, raw baseline preserved, customer ranking unchanged",
            "Assist promotion must start from a non-mutating shadow baseline.",
            residual_shadow_path,
        ),
        _row(
            "uncertainty_abstention_contract",
            "pass" if abstention_fields_present else "fail",
            f"abstention_fields_present={abstention_fields_present}",
            "uncertainty and abstention fields present",
            "Low-risk assist routing must be able to abstain on high uncertainty/OOD rows.",
            residual_shadow_path,
        ),
        _row(
            "gpcr_no_pass_to_fail_regression",
            "pass" if gpcr_no_pass_to_fail else "fail",
            f"pass_to_fail={gpcr.get('pass_to_fail_regression_count')}; decision_regressions={gpcr.get('pass_regressions_from_decision')}",
            "zero GPCR pass-to-fail regressions",
            "Assist mode cannot degrade existing passing GPCR cases.",
            gpcr_proof_path,
        ),
        _row(
            "gpcr_hard_decoy_support",
            "pass" if gpcr_hard_decoy_support else "fail",
            f"intrusion_reduction_task_count={gpcr.get('intrusion_reduction_task_count')}; binder_retention_fail_count={gpcr.get('binder_retention_fail_count')}",
            "hard-decoy intrusion reduction and binder retention preserved",
            "Assist mode should target the measured hard-decoy failure mode.",
            gpcr_proof_path,
        ),
        _row(
            "gpcr_pr_auc_clean",
            "pass" if gpcr_pr_auc_clean else "fail",
            f"proof_pr_auc_warning_count={gpcr.get('pr_auc_regression_warning_count')}; assist_selection_status={assist_selection.get('status')}; assist_selection_pr_auc_warning_count={assist_selection.get('pr_auc_regression_warning_count')}",
            "zero PR-AUC regression warnings in proof or a clean per-task assist candidate selection",
            "A global apply warning can be isolated only if the assist router selects clean per-task modes and abstains otherwise.",
            f"{gpcr_proof_path}; {gpcr_assist_selection_path}",
        ),
        _row(
            "public_shadow_regression_clean",
            "pass" if public_shadow_clean else "fail",
            f"fail_suite_count={public.get('fail_suite_count')}; pass_to_fail={public.get('pass_to_fail_regression_count')}",
            "zero public benchmark shadow regressions",
            "Public benchmark safety must stay green before assist routing.",
            public_regression_path,
        ),
        _row(
            "public_assist_comparison_ready",
            "pass" if public_assist_comparison_ready else "fail",
            f"public_assist_gate_status={public_assist.get('status')}; assist_promotion_allowed={public_assist_comparison_ready}; missing_assist_comparison_count={public_assist.get('missing_assist_comparison_count')}",
            "per-suite public benchmark raw/shadow/assist comparison evidence allows assist promotion",
            "Shadow-only safety is not enough to change customer-facing ranking behavior.",
            f"{public_regression_path}; {public_assist_gate_path}",
        ),
        _row(
            "rocm_end_to_end_baseline_ready",
            "pass" if e2e_ready else "fail",
            f"benchmark_ready={e2e.get('benchmark_ready')}; jobs_per_hour={e2e.get('jobs_per_hour')}",
            "ROCm end-to-end benchmark baseline ready",
            "Assist mode needs a measured product baseline for throughput/regression accounting.",
            e2e_benchmark_path,
        ),
    ]
    fail_rows = [row for row in rows if row["status"] != "pass"]
    assist_allowed = not fail_rows
    summary = {
        "packet_type": "residual_assist_promotion_gate",
        "status": "residual_assist_promotion_gate_ready" if assist_allowed else "blocked_residual_assist_promotion_gate",
        "assist_promotion_allowed": assist_allowed,
        "production_promotion_allowed": False,
        "residual_mode_from": "shadow",
        "residual_mode_to": "assist",
        "check_count": len(rows),
        "pass_check_count": len(rows) - len(fail_rows),
        "fail_check_count": len(fail_rows),
        "failed_check_ids": [row["check_id"] for row in fail_rows],
        "primary_blocker": fail_rows[0]["check_id"] if fail_rows else "none",
        "execution_enabled": False,
        "benchmark_executed": False,
        "docking_results_emitted": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Assist promotion is evidence-ready; wire low-risk assist mode behind explicit policy change."
            if assist_allowed
            else f"Repair `{fail_rows[0]['check_id']}` before assist promotion."
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
        "# Residual Assist Promotion Gate",
        "",
        f"- status: `{s['status']}`",
        f"- assist_promotion_allowed: `{s['assist_promotion_allowed']}`",
        f"- residual_mode_from: `{s['residual_mode_from']}`",
        f"- residual_mode_to: `{s['residual_mode_to']}`",
        f"- pass_check_count: `{s['pass_check_count']}` / `{s['check_count']}`",
        f"- primary_blocker: `{s['primary_blocker']}`",
        "",
        "## Checks",
        "",
        "| check | status | observed | required | reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(f"| `{row['check_id']}` | `{row['status']}` | `{row['observed']}` | `{row['required']}` | {row['reason']} |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build residual assist promotion gate from local evidence.")
    parser.add_argument("--residual-shadow-json", default=DEFAULT_RESIDUAL_SHADOW_JSON)
    parser.add_argument("--gpcr-proof-json", default=DEFAULT_GPCR_PROOF_JSON)
    parser.add_argument("--gpcr-assist-selection-json", default=DEFAULT_GPCR_ASSIST_SELECTION_JSON)
    parser.add_argument("--public-regression-json", default=DEFAULT_PUBLIC_REGRESSION_JSON)
    parser.add_argument("--public-assist-gate-json", default=DEFAULT_PUBLIC_ASSIST_GATE_JSON)
    parser.add_argument("--e2e-benchmark-json", default=DEFAULT_E2E_BENCHMARK_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_residual_assist_promotion_gate(
        residual_shadow_packet=_read_json_if_present(args.residual_shadow_json),
        gpcr_proof_packet=_read_json_if_present(args.gpcr_proof_json),
        gpcr_assist_selection_packet=_read_json_if_present(args.gpcr_assist_selection_json),
        public_regression_packet=_read_json_if_present(args.public_regression_json),
        public_assist_gate_packet=_read_json_if_present(args.public_assist_gate_json),
        e2e_benchmark_packet=_read_json_if_present(args.e2e_benchmark_json),
        residual_shadow_path=args.residual_shadow_json,
        gpcr_proof_path=args.gpcr_proof_json,
        gpcr_assist_selection_path=args.gpcr_assist_selection_json,
        public_regression_path=args.public_regression_json,
        public_assist_gate_path=args.public_assist_gate_json,
        e2e_benchmark_path=args.e2e_benchmark_json,
    )
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
