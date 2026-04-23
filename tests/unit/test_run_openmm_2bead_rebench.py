import json
from pathlib import Path

import pandas as pd

from tools import run_openmm_2bead_rebench as rebench


def test_run_pipeline_records_speed_runtime_config(monkeypatch, tmp_path):
    def _fake_parse_targets(_spec: str, seed: int):
        _ = seed
        return ["Chignolin"]

    def _fake_long_stability(*, targets, paths, args):
        return {"summary": {"gate_pass": True, "targets": len(targets), "failed_targets": []}}

    def _fake_speed_rebench(*, targets, paths, args):
        # speed stage is skipped in this test; keep stub for completeness
        return {"summary": {"skipped": True}}

    def _fake_accuracy_rebench(*, targets, external_manifest_csv, paths, args):
        out_csv = Path(paths["accuracy_csv"])
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [
                {
                    "target": "Chignolin",
                    "avg_rmsd_aligned": 1.23,
                    "avg_rmsd_vs_native_aligned": 1.11,
                }
            ]
        ).to_csv(out_csv, index=False)
        out_json = Path(paths["accuracy_json"])
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps({"summary": {"targets": 1}}), encoding="utf-8")
        return {"summary": {"targets": 1}}

    monkeypatch.setattr(rebench, "_parse_targets", _fake_parse_targets)
    monkeypatch.setattr(rebench, "_run_long_stability", _fake_long_stability)
    monkeypatch.setattr(rebench, "_run_speed_rebench", _fake_speed_rebench)
    monkeypatch.setattr(rebench, "_run_accuracy_rebench", _fake_accuracy_rebench)

    args = rebench.build_parser().parse_args(
        [
            "--targets",
            "Chignolin",
            "--skip-openmm-generate",
            "--skip-speed-rebench",
            "--external-manifest",
            "runs/real_md_source_manifest_openmm_2bead_2026-02-17.csv",
            "--out-prefix",
            str(tmp_path / "rebench_runtime_test"),
            "--ai-runtime-mode",
            "onnx",
            "--no-ai-disable-exploration",
            "--ai-use-hip-graph",
            "--ai-graph-warmup-iters",
            "5",
            "--no-use-ai-router",
            "--ai-router-checkpoint",
            "models/router_ckpt.pth",
            "--ai-router-checkpoint-strict",
        ]
    )

    payload = rebench.run_pipeline(args)
    cfg = payload.get("speed_runtime_config", {})

    assert cfg.get("use_ai_router") is False
    assert cfg.get("ai_runtime_mode") == "onnx"
    assert cfg.get("ai_disable_exploration") is False
    assert cfg.get("ai_use_hip_graph") is True
    assert cfg.get("ai_graph_warmup_iters") == 5
    assert cfg.get("ai_router_checkpoint") == "models/router_ckpt.pth"
    assert cfg.get("ai_router_checkpoint_strict") is True
