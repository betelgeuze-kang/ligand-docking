import os

import numpy as np
import torch

from tools import sweep_ai_interval_tradeoff as sweep


def test_parse_topk_values_normalizes():
    vals = sweep._parse_topk_values("0, 8, -2, 4, 8")
    assert vals == [0, 4, 8]


def test_temporary_env_var_restores_previous():
    os.environ["AI_ROUTER_TOPK_ACTIVE"] = "7"
    with sweep._temporary_env_var("AI_ROUTER_TOPK_ACTIVE", "3"):
        assert os.environ.get("AI_ROUTER_TOPK_ACTIVE") == "3"
    assert os.environ.get("AI_ROUTER_TOPK_ACTIVE") == "7"

    with sweep._temporary_env_var("AI_ROUTER_TOPK_ACTIVE", None):
        assert "AI_ROUTER_TOPK_ACTIVE" not in os.environ
    assert os.environ.get("AI_ROUTER_TOPK_ACTIVE") == "7"


def test_run_sweep_interval_topk_grid(monkeypatch):
    def fake_native(_target: str) -> torch.Tensor:
        return torch.zeros((10, 3), dtype=torch.float32)

    def fake_benchmark_simulation(**kwargs):
        interval = int(kwargs["ai_interval"])
        topk = int(os.environ.get("AI_ROUTER_TOPK_ACTIVE", "0") or "0")
        x = float(interval) + (0.01 * float(topk))
        coords = np.zeros((1, 10, 3), dtype=np.float32)
        coords[0, :, 0] = x
        throughput = 1000.0 + (25.0 * float(interval)) + (5.0 * float(topk))
        return {
            "final_coords": coords,
            "avg_throughput_steps_per_sec": throughput,
            "avg_time_per_step_ms": 1.0,
            "avg_ai_inference_calls_per_run": 3.0,
            "avg_ai_reuse_steps_per_run": 10.0,
            "avg_ai_graph_enabled_flag": 0.0,
        }

    monkeypatch.setattr(sweep, "_load_native", fake_native)
    monkeypatch.setattr(sweep, "benchmark_simulation", fake_benchmark_simulation)

    out = sweep.run_sweep(
        targets=["Chignolin"],
        ai_intervals=[1, 2],
        topk_values=[0, 4],
        steps=20,
        runs=1,
        warmup_steps=5,
        batch_replicas=1,
        seed=123,
        benchmark_csv=None,
        neighbor_settings={},
        force_backend="auto",
        force_rust=False,
        ai_collect_aux=False,
        ai_router_checkpoint=None,
        ai_router_checkpoint_strict=False,
        ai_runtime_mode="eager",
        ai_disable_exploration=False,
        ai_use_hip_graph=False,
        ai_graph_warmup_iters=1,
    )

    target_df = out["target_df"]
    curve_df = out["curve_df"]
    payload = out["payload"]

    assert len(target_df) == 4
    assert set(target_df["topk_active"].tolist()) == {0, 4}
    base_row = target_df[
        (target_df["ai_interval"] == 1) & (target_df["topk_active"] == 0)
    ].iloc[0]
    assert float(base_row["speedup_vs_baseline"]) == 1.0
    assert payload["baseline"]["ai_interval"] == 1
    assert payload["baseline"]["topk_active"] == 0
    assert len(curve_df) == 4
