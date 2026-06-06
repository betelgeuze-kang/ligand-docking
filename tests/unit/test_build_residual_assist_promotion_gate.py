from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_residual_assist_promotion_gate as mod


def _residual() -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_shadow_ab_scaffold_ready",
            "scaffold_ready": True,
            "raw_baseline_preserved": True,
            "no_customer_facing_ranking_change": True,
            "abstention_fields_present": True,
        }
    }


def _gpcr(*, pr_auc_warning_count: int = 1) -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_hard_decoy_residual_proof_ready",
            "pass_to_fail_regression_count": 0,
            "pass_regressions_from_decision": 0,
            "intrusion_reduction_task_count": 1,
            "binder_retention_fail_count": 0,
            "pr_auc_regression_warning_count": pr_auc_warning_count,
        }
    }


def _public(*, assist_allowed: bool = False) -> dict[str, object]:
    return {
        "summary": {
            "status": "public_benchmark_residual_regression_gate_ready",
            "fail_suite_count": 0,
            "pass_to_fail_regression_count": 0,
            "assist_promotion_allowed": assist_allowed,
        }
    }


def _e2e() -> dict[str, object]:
    return {"summary": {"status": "product_end_to_end_rocm_benchmark_ready", "benchmark_ready": True, "jobs_per_hour": 1000.0}}


def _assist_selection() -> dict[str, object]:
    return {
        "summary": {
            "status": "gpcr_residual_assist_candidate_selection_ready",
            "assist_candidate_ready": True,
            "pr_auc_regression_warning_count": 0,
            "pass_to_fail_regression_count": 0,
            "residual_applied_task_count": 1,
        }
    }


def _public_assist_gate() -> dict[str, object]:
    return {
        "summary": {
            "status": "public_benchmark_residual_assist_comparison_gate_ready",
            "assist_comparison_gate_ready": True,
            "missing_assist_comparison_count": 0,
        }
    }


def test_residual_assist_promotion_gate_blocks_current_warning_and_missing_assist_comparison() -> None:
    payload = mod.build_residual_assist_promotion_gate(
        residual_shadow_packet=_residual(),
        gpcr_proof_packet=_gpcr(),
        public_regression_packet=_public(),
        e2e_benchmark_packet=_e2e(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_assist_promotion_gate"
    assert summary["assist_promotion_allowed"] is False
    assert summary["failed_check_ids"] == ["gpcr_pr_auc_clean", "public_assist_comparison_ready"]


def test_residual_assist_promotion_gate_uses_clean_gpcr_assist_selection() -> None:
    payload = mod.build_residual_assist_promotion_gate(
        residual_shadow_packet=_residual(),
        gpcr_proof_packet=_gpcr(),
        gpcr_assist_selection_packet=_assist_selection(),
        public_regression_packet=_public(),
        e2e_benchmark_packet=_e2e(),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_residual_assist_promotion_gate"
    assert summary["assist_promotion_allowed"] is False
    assert summary["failed_check_ids"] == ["public_assist_comparison_ready"]
    assert summary["primary_blocker"] == "public_assist_comparison_ready"


def test_residual_assist_promotion_gate_ready_when_all_checks_pass() -> None:
    payload = mod.build_residual_assist_promotion_gate(
        residual_shadow_packet=_residual(),
        gpcr_proof_packet=_gpcr(pr_auc_warning_count=0),
        public_regression_packet=_public(assist_allowed=True),
        e2e_benchmark_packet=_e2e(),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_assist_promotion_gate_ready"
    assert summary["assist_promotion_allowed"] is True
    assert summary["production_promotion_allowed"] is False
    assert summary["fail_check_count"] == 0


def test_residual_assist_promotion_gate_ready_with_candidate_selection_and_public_assist_gate() -> None:
    payload = mod.build_residual_assist_promotion_gate(
        residual_shadow_packet=_residual(),
        gpcr_proof_packet=_gpcr(),
        gpcr_assist_selection_packet=_assist_selection(),
        public_regression_packet=_public(),
        public_assist_gate_packet=_public_assist_gate(),
        e2e_benchmark_packet=_e2e(),
    )

    summary = payload["summary"]
    assert summary["status"] == "residual_assist_promotion_gate_ready"
    assert summary["assist_promotion_allowed"] is True
    assert summary["fail_check_count"] == 0


def test_residual_assist_promotion_gate_cli_writes_outputs(tmp_path: Path) -> None:
    residual_json = tmp_path / "residual.json"
    gpcr_json = tmp_path / "gpcr.json"
    public_json = tmp_path / "public.json"
    e2e_json = tmp_path / "e2e.json"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    residual_json.write_text(json.dumps(_residual()) + "\n", encoding="utf-8")
    gpcr_json.write_text(json.dumps(_gpcr()) + "\n", encoding="utf-8")
    public_json.write_text(json.dumps(_public()) + "\n", encoding="utf-8")
    e2e_json.write_text(json.dumps(_e2e()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--residual-shadow-json",
            str(residual_json),
            "--gpcr-proof-json",
            str(gpcr_json),
            "--gpcr-assist-selection-json",
            str(tmp_path / "missing_assist_selection.json"),
            "--public-regression-json",
            str(public_json),
            "--public-assist-gate-json",
            str(tmp_path / "missing_public_assist_gate.json"),
            "--e2e-benchmark-json",
            str(e2e_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["assist_promotion_allowed"] is False
    assert "check_id" in out_csv.read_text(encoding="utf-8")
    assert "Residual Assist Promotion Gate" in out_md.read_text(encoding="utf-8")
