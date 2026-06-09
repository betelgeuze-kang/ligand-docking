from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools import generate_ligand_trajectory_engine as engine_mod
from tools.product.build_trajectory_engine_ranking_guard_smoke import run_smoke

PRODUCTION_GUARDED_REGISTRY = {
    "summary": {
        "default_residual_mode": "production_guarded",
        "production_promotion_allowed": True,
        "customer_facing_auto_correction_allowed": True,
        "customer_facing_score_mutation_allowed": True,
        "customer_facing_ranking_mutation_allowed": True,
        "trained_model_checkpoint_count": 1,
    }
}


def test_trajectory_engine_ranking_guard_smoke_passes_with_mocked_engine(tmp_path, monkeypatch) -> None:
    def _fake_load_protein_coords(target: str, native_path: str):
        import numpy as np

        return np.zeros((2, 3), dtype=np.float32)

    def _fake_simulate_with_engine_batch(protein, ligand0_batch, pocket_batch, **kwargs):
        import numpy as np

        batch_size = int(ligand0_batch.shape[0])
        selected = np.asarray(ligand0_batch[:, None, :, :], dtype=np.float32)
        frame_idx = np.asarray([0], dtype=np.int32)
        return (
            selected,
            frame_idx,
            "rust_hip",
            1,
            False,
            1,
            {
                "prod_early_stop_metric_backend_counts": {},
                "prod_early_stop_eval_keep_count": 0,
                "prod_early_stop_eval_row_count": 0,
            },
        )

    def _fake_engine_runner(queue_csv: Path, out_root: Path) -> dict:
        return engine_mod.run_batch(
            engine_mod.build_parser().parse_args(
                [
                    "--queue-csv",
                    str(queue_csv),
                    "--out-root",
                    str(out_root),
                    "--out-summary-json",
                    str(out_root.parent / "summary.json"),
                    "--out-manifest-csv",
                    str(out_root.parent / "manifest.csv"),
                    "--frame-output-format",
                    "manifest_only",
                    "--max-jobs",
                    "1",
                    "--frames",
                    "2",
                    "--write-every",
                    "1",
                    "--writer-workers",
                    "0",
                    "--no-fail-on-missing-native",
                ]
            )
        )

    monkeypatch.setattr(engine_mod, "_load_protein_coords", _fake_load_protein_coords)
    monkeypatch.setattr(engine_mod, "_simulate_with_engine_batch", _fake_simulate_with_engine_batch)

    payload = run_smoke(
        registry_packet=PRODUCTION_GUARDED_REGISTRY,
        engine_runner=_fake_engine_runner,
        work_root=tmp_path / "work",
    )
    summary = payload["summary"]
    assert summary["status"] == "trajectory_engine_ranking_guard_smoke_ready"
    assert summary["production_promotion_green"] is True
    assert summary["engine_ok_rows"] == 1
    assert summary["ranking_pass_scenario_count"] == 2
    assert all(row["pass"] for row in payload["ranking_rows"])


def test_trajectory_engine_ranking_guard_smoke_blocks_when_promotion_not_green() -> None:
    payload = run_smoke(
        registry_packet={
            "summary": {
                "default_residual_mode": "shadow_only",
                "production_promotion_allowed": False,
                "customer_facing_ranking_mutation_allowed": False,
                "trained_model_checkpoint_count": 0,
            }
        }
    )
    summary = payload["summary"]
    assert summary["status"] == "blocked_trajectory_engine_ranking_guard_smoke"
    assert summary["production_promotion_green"] is False
    assert summary["engine_executed"] is False
    assert "production_promotion_not_green" in summary["blockers"]
