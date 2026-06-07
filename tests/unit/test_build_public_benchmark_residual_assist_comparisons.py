from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_public_benchmark_residual_assist_comparisons as mod
from tools import build_public_benchmark_residual_assist_comparison_gate as gate_mod


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
                "scorecard_json": f"runs/suite_{idx}_scorecard_current.json",
                "primary_metric": "ROC_AUC",
                "primary_metric_value": 0.8,
                "primary_metric_threshold": 0.6,
                "regression_baseline_ref": f"suite_{idx}:baseline",
                "required_for_commercial_release": True,
            }
            for idx in range(5)
        ],
    }


def _assist_selection() -> dict[str, object]:
    return {"summary": {"status": "gpcr_residual_assist_candidate_selection_ready", "assist_candidate_ready": True}}


def test_public_benchmark_residual_assist_comparisons_manifest_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)

    payload = mod.build_public_benchmark_residual_assist_comparisons(
        public_benchmark_packet=_public_contract(),
        gpcr_assist_selection_packet=_assist_selection(),
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_residual_assist_comparisons_manifest_ready"
    assert summary["pass_suite_count"] == 5
    assert summary["abstain_noop_suite_count"] == 5
    assert summary["claim_public_metric_improvement_allowed"] is False
    for idx in range(5):
        comparison = tmp_path / f"runs/suite_{idx}_residual_assist_comparison_current.json"
        assert comparison.exists()
        assert json.loads(comparison.read_text(encoding="utf-8"))["summary"]["assist_comparison_ready"] is True


def test_public_benchmark_residual_assist_comparisons_feed_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    public_packet = _public_contract()

    mod.build_public_benchmark_residual_assist_comparisons(
        public_benchmark_packet=public_packet,
        gpcr_assist_selection_packet=_assist_selection(),
    )
    comparison_packets = {
        f"suite_{idx}": json.loads((tmp_path / f"runs/suite_{idx}_residual_assist_comparison_current.json").read_text(encoding="utf-8"))
        for idx in range(5)
    }

    gate = gate_mod.build_public_benchmark_residual_assist_comparison_gate(
        public_benchmark_packet=public_packet,
        comparison_packets_by_suite=comparison_packets,
    )

    summary = gate["summary"]
    assert summary["status"] == "public_benchmark_residual_assist_comparison_gate_ready"
    assert summary["missing_assist_comparison_count"] == 0
    assert summary["pass_suite_count"] == 5


def test_public_benchmark_residual_assist_comparisons_cli_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    public_json = tmp_path / "public.json"
    assist_json = tmp_path / "assist.json"
    out_json = tmp_path / "manifest.json"
    out_csv = tmp_path / "manifest.csv"
    out_md = tmp_path / "manifest.md"
    public_json.write_text(json.dumps(_public_contract()) + "\n", encoding="utf-8")
    assist_json.write_text(json.dumps(_assist_selection()) + "\n", encoding="utf-8")

    mod.main(
        [
            "--public-benchmark-json",
            str(public_json),
            "--gpcr-assist-selection-json",
            str(assist_json),
            "--out-manifest-json",
            str(out_json),
            "--out-manifest-csv",
            str(out_csv),
            "--out-manifest-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["manifest_ready"] is True
    assert "suite_id" in out_csv.read_text(encoding="utf-8")
    assert "Public Benchmark Residual Assist Comparisons Manifest" in out_md.read_text(encoding="utf-8")
