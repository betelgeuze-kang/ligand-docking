from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_public_benchmark_residual_regression_gate as mod


def _public_contract() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_public_benchmark_contract_ready",
            "public_benchmark_validation_ready": True,
            "required_suite_count": 5,
            "ready_required_suite_count": 5,
        },
        "rows": [
            {
                "suite_id": f"suite_{idx}",
                "benchmark_family": "family",
                "status": "ready",
                "scorecard_json": f"scorecard_{idx}.json",
                "scorecard_json_present": True,
                "primary_metric": "EF1",
                "primary_metric_value": 1.5,
                "primary_metric_threshold": 1.0,
            }
            for idx in range(5)
        ],
    }


def _residual_shadow(*, no_ranking_change: bool = True) -> dict[str, object]:
    return {
        "summary": {
            "status": "residual_shadow_ab_scaffold_ready",
            "scaffold_ready": True,
            "no_customer_facing_ranking_change": no_ranking_change,
            "residual_mode": "shadow",
        }
    }


def test_public_benchmark_residual_regression_gate_ready() -> None:
    payload = mod.build_public_benchmark_residual_regression_gate(
        public_benchmark_packet=_public_contract(),
        residual_shadow_packet=_residual_shadow(),
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_residual_regression_gate_ready"
    assert summary["regression_gate_ready"] is True
    assert summary["required_suite_count"] == 5
    assert summary["pass_suite_count"] == 5
    assert summary["pass_to_fail_regression_count"] == 0
    assert summary["assist_promotion_allowed"] is False
    assert summary["production_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False


def test_public_benchmark_residual_regression_gate_blocks_ranking_mutation() -> None:
    payload = mod.build_public_benchmark_residual_regression_gate(
        public_benchmark_packet=_public_contract(),
        residual_shadow_packet=_residual_shadow(no_ranking_change=False),
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_residual_regression_gate"
    assert summary["regression_gate_ready"] is False
    assert summary["fail_suite_count"] == 5
    assert summary["pass_to_fail_regression_count"] == 5


def test_public_benchmark_residual_regression_gate_cli_writes_outputs(tmp_path: Path) -> None:
    public_json = tmp_path / "public.json"
    residual_json = tmp_path / "residual.json"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    public_json.write_text(json.dumps(_public_contract()) + "\n", encoding="utf-8")
    residual_json.write_text(json.dumps(_residual_shadow()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--public-benchmark-json",
            str(public_json),
            "--residual-shadow-json",
            str(residual_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["regression_gate_ready"] is True
    assert "suite_id" in out_csv.read_text(encoding="utf-8")
    assert "Public Benchmark Residual Regression Gate" in out_md.read_text(encoding="utf-8")
