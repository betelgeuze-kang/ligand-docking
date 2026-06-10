from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_architecture_validation_evidence_depth as depth_mod


def test_audit_evidence_depth_flags_metric_surface_summary_row_mismatch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(depth_mod, "ROOT", tmp_path)
    casp17 = tmp_path / "casp17"
    casp17.mkdir()
    (casp17 / "casp17_win_tier_metric_surface_contract_current.json").write_text(
        json.dumps(
            {
                "summary": {"ready_metric_row_count": 10},
                "rows": [{"metric_status": "awaiting_strict_blind_evidence_files", "slot_rank": 1}] * 10,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "casp17_historical_benchmark_packet_current.json").write_text(
        json.dumps({"summary": {"historical_benchmark_status": "pass"}, "rows": [{"benchmark_status": "pass"}]})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs" / "casp17_sidechain_native_benchmark_packet_current.json").write_text(
        json.dumps({"summary": {"pass_count": 0}, "rows": []}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs" / "competition_benchmark_rollup_current.json").write_text(
        json.dumps({"summary": {"cameo_official_results_used": False}}) + "\n",
        encoding="utf-8",
    )
    (casp17 / "casp17_strict_blind_internal_prediction_source_gate_current.json").write_text(
        json.dumps({"summary": {"internal_prediction_source_gate_status": "blocked"}}) + "\n",
        encoding="utf-8",
    )
    (casp17 / "casp17_historical_winner_normalized_bands_current.json").write_text(
        json.dumps({"rows": [{"band_status": "blocked_input"}]}) + "\n",
        encoding="utf-8",
    )

    audit = depth_mod.audit_evidence_depth()
    codes = [item["code"] for item in audit["overclaim_warnings"]]
    assert "metric_surface_summary_row_mismatch" in codes
    assert audit["evidence_depth_tier"] == "accounting_only"


def test_audit_evidence_depth_uses_sidechain_native_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(depth_mod, "ROOT", tmp_path)
    casp17 = tmp_path / "casp17"
    casp17.mkdir()
    (casp17 / "casp17_win_tier_metric_surface_contract_current.json").write_text(
        json.dumps({"summary": {"ready_metric_row_count": 1}, "rows": [{"metric_status": "metric_inputs_ready", "slot_rank": 1}]})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "casp17_historical_benchmark_packet_current.json").write_text(
        json.dumps({"summary": {"historical_benchmark_status": "pass"}, "rows": [{"benchmark_status": "pass"}]})
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs" / "casp17_sidechain_native_benchmark_packet_current.json").write_text(
        json.dumps(
            {
                "summary": {"pass_count": 1},
                "rows": [{"sidechain_native_status": "pass"}, {"sidechain_native_status": "blocked"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "runs" / "competition_benchmark_rollup_current.json").write_text(
        json.dumps({"summary": {}}) + "\n",
        encoding="utf-8",
    )
    (casp17 / "casp17_strict_blind_internal_prediction_source_gate_current.json").write_text(
        json.dumps({"summary": {}}) + "\n",
        encoding="utf-8",
    )
    (casp17 / "casp17_historical_winner_normalized_bands_current.json").write_text(
        json.dumps({"rows": [{"band_status": "ready_for_review"}]}) + "\n",
        encoding="utf-8",
    )

    audit = depth_mod.audit_evidence_depth()
    assert audit["sidechain_native_row_pass_count"] == 1
    codes = [item["code"] for item in audit["overclaim_warnings"]]
    assert "sidechain_native_summary_row_mismatch" not in codes
