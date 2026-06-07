from __future__ import annotations

import json
from pathlib import Path

from tools import build_public_benchmark_residual_assist_comparison_gate as mod


def _public_contract() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_public_benchmark_contract_ready",
            "public_benchmark_validation_ready": True,
            "required_suite_count": 5,
        },
        "rows": [
            {
                "suite_id": f"suite_{idx}",
                "benchmark_family": "family",
                "status": "ready",
                "scorecard_json_present": True,
                "required_for_commercial_release": True,
            }
            for idx in range(5)
        ],
    }


def _comparison_ready() -> dict[str, object]:
    return {
        "summary": {
            "assist_comparison_ready": True,
            "pass_to_fail_regression_count": 0,
            "metric_regression_count": 0,
            "throughput_loss_fraction": 0.02,
        }
    }


def test_public_benchmark_residual_assist_comparison_gate_blocks_missing_artifacts() -> None:
    payload = mod.build_public_benchmark_residual_assist_comparison_gate(
        public_benchmark_packet=_public_contract(),
        comparison_packets_by_suite={},
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_public_benchmark_residual_assist_comparison_gate"
    assert summary["assist_comparison_gate_ready"] is False
    assert summary["missing_assist_comparison_count"] == 5
    assert summary["failed_suite_ids"] == [f"suite_{idx}" for idx in range(5)]


def test_public_benchmark_residual_assist_comparison_gate_ready() -> None:
    payload = mod.build_public_benchmark_residual_assist_comparison_gate(
        public_benchmark_packet=_public_contract(),
        comparison_packets_by_suite={f"suite_{idx}": _comparison_ready() for idx in range(5)},
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_residual_assist_comparison_gate_ready"
    assert summary["assist_comparison_gate_ready"] is True
    assert summary["assist_promotion_allowed"] is True
    assert summary["pass_suite_count"] == 5
    assert summary["missing_assist_comparison_count"] == 0


def test_public_benchmark_residual_assist_comparison_gate_cli_writes_outputs(tmp_path: Path) -> None:
    public_json = tmp_path / "public.json"
    out_json = tmp_path / "gate.json"
    out_csv = tmp_path / "gate.csv"
    out_md = tmp_path / "gate.md"
    public_json.write_text(json.dumps(_public_contract()) + "\n", encoding="utf-8")

    mod.main(["--public-benchmark-json", str(public_json), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["missing_assist_comparison_count"] == 5
    assert "suite_id" in out_csv.read_text(encoding="utf-8")
    assert "Public Benchmark Residual Assist Comparison Gate" in out_md.read_text(encoding="utf-8")
