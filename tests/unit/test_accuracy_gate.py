import json
from types import SimpleNamespace

import pandas as pd

from tools import validate_accuracy_gate as gate


def _base_parity_row():
    return {
        "target": "Chignolin",
        "neighbor_jaccard_mean": 1.0,
        "e2e_rmse_mean_raw": 0.2,
        "e2e_rel_rmse_mean_clipped": 1e-7,
        "kernel_shared_rs_rmse_mean_raw": 0.2,
        "nblist_effect_py_rmse_mean_raw": 0.05,
        "nblist_effect_rs_rmse_mean_raw": 0.0,
        "rs_neighbor_saturated_samples": 0,
        "rs_cell_overflow_samples": 0,
        "py_saturated_atoms_max": 0,
        "rs_max_cell_count_max": 0,
        "rs_builder_max_atoms_per_cell_max": 64,
        "rs_builder_max_neighbors_max": 100,
        "py_max_required_neighbors_max": 40,
        "py_effective_max_neighbors_max": 100,
    }


def test_accuracy_gate_pass_case():
    df = pd.DataFrame([_base_parity_row()])
    gate_df, failed_metrics, overflow_events, failed_targets = gate.evaluate_parity_gate(
        parity_df=df,
        jaccard_threshold=1.0,
        e2e_rmse_threshold=0.35,
        rel_rmse_threshold=1e-5,
        strict_mode=True,
        strict_kernel_rmse_threshold=0.45,
        strict_nblist_effect_threshold=0.12,
        strict_nblist_effect_rs_threshold=1e-8,
    )
    assert len(failed_metrics) == 0
    assert len(overflow_events) == 0
    assert len(failed_targets) == 0
    assert bool(gate_df.iloc[0]["pass"]) is True


def test_accuracy_gate_fails_on_low_jaccard():
    row = _base_parity_row()
    row["neighbor_jaccard_mean"] = 0.99
    df = pd.DataFrame([row])
    _, failed_metrics, _, failed_targets = gate.evaluate_parity_gate(
        parity_df=df,
        jaccard_threshold=1.0,
        e2e_rmse_threshold=0.35,
        rel_rmse_threshold=1e-5,
        strict_mode=False,
        strict_kernel_rmse_threshold=0.45,
        strict_nblist_effect_threshold=0.12,
        strict_nblist_effect_rs_threshold=1e-8,
    )
    assert "Chignolin" in failed_targets
    assert any(m["metric"] == "neighbor_jaccard_mean" for m in failed_metrics)


def test_accuracy_gate_fails_on_speed_threshold():
    failed_metrics = gate.evaluate_speed_gate(
        perf_summary={"avg_speedup_on_vs_off": 11.0},
        perf_rows=[],
        speedup_threshold=12.0,
        speedup_per_target_threshold=10.0,
    )
    assert len(failed_metrics) == 1
    assert failed_metrics[0]["metric"] == "avg_speedup_on_vs_off"


def test_accuracy_gate_fails_on_per_target_speed_threshold():
    failed_metrics = gate.evaluate_speed_gate(
        perf_summary={"avg_speedup_on_vs_off": 15.0},
        perf_rows=[
            {"target": "Chignolin", "speedup_on_vs_off": 8.0},
            {"target": "Trp_Cage", "speedup_on_vs_off": 12.0},
        ],
        speedup_threshold=12.0,
        speedup_per_target_threshold=10.0,
    )
    assert len(failed_metrics) == 1
    assert failed_metrics[0]["scope"] == "performance_per_target"
    assert failed_metrics[0]["target"] == "Chignolin"
    assert failed_metrics[0]["metric"] == "speedup_on_vs_off"


def test_accuracy_gate_fails_on_overflow_flags():
    row = _base_parity_row()
    row["rs_cell_overflow_samples"] = 1
    df = pd.DataFrame([row])
    gate_df, failed_metrics, overflow_events, failed_targets = gate.evaluate_parity_gate(
        parity_df=df,
        jaccard_threshold=1.0,
        e2e_rmse_threshold=0.35,
        rel_rmse_threshold=1e-5,
        strict_mode=False,
        strict_kernel_rmse_threshold=0.45,
        strict_nblist_effect_threshold=0.12,
        strict_nblist_effect_rs_threshold=1e-8,
    )
    assert "Chignolin" in failed_targets
    assert len(overflow_events) == 1
    assert any(m["metric"] == "overflow_or_saturation" for m in failed_metrics)
    assert bool(gate_df.iloc[0]["pass"]) is False


def test_accuracy_gate_output_schema(tmp_path, monkeypatch):
    parity_target_csv = tmp_path / "gate_parity_target.csv"

    def _fake_run_parity(**kwargs):
        pd.DataFrame([_base_parity_row()]).to_csv(parity_target_csv, index=False)
        return {"summary": {"avg_neighbor_jaccard": 1.0}}

    def _fake_run_stage2_report(_args):
        return {"summary": {"avg_speedup_on_vs_off": 13.0}, "rows": [{"target": "Chignolin", "speedup_on_vs_off": 13.0}]}

    monkeypatch.setattr(gate, "run_parity", _fake_run_parity)
    monkeypatch.setattr(gate, "run_stage2_report", _fake_run_stage2_report)

    args = SimpleNamespace(
        targets="Chignolin",
        samples=1,
        noise=0.08,
        steps=1,
        runs=1,
        cutoff=12.0,
        skin=2.0,
        max_neighbors=100,
        max_atoms_per_cell=64,
        rebuild_stride=4,
        reference_cutoff=14.0,
        reference_max_neighbors=160,
        jaccard_threshold=1.0,
        e2e_rmse_threshold=0.35,
        rel_rmse_threshold=1e-5,
        speedup_threshold=12.0,
        speedup_per_target_threshold=10.0,
        strict_kernel_rmse_threshold=0.45,
        strict_nblist_effect_threshold=0.12,
        strict_nblist_effect_rs_threshold=1e-8,
        strict_mode=True,
        outlier_mode="shared_rs_nblist",
        out_json=str(tmp_path / "accuracy_gate.json"),
        out_csv=str(tmp_path / "accuracy_gate.csv"),
        parity_prefix=str(tmp_path / "gate_parity"),
        stage2_prefix=str(tmp_path / "gate_stage2"),
        benchmark_csv=str(tmp_path / "bench.csv"),
    )

    payload = gate.run_accuracy_gate(args)
    assert payload["summary"]["pass"] is True
    assert isinstance(payload["summary"]["failed_targets"], list)
    assert isinstance(payload["summary"]["failed_metrics"], list)
    assert "parity_summary" in payload
    assert "performance_summary" in payload
    assert "overflow_events" in payload

    with open(args.out_json, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert "summary" in saved
    assert "pass" in saved["summary"]
    assert (tmp_path / "accuracy_gate.csv").exists()
