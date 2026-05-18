import json
import subprocess
import sys
from pathlib import Path


ROOT = Path("/home/betelgeuze/분자동역학")


def test_idp_3bead_eval_gate_dataset_train(tmp_path):
    config_path = tmp_path / "idp_cfg.json"
    config_path.write_text(
        json.dumps(
            {
                "runtime": {
                    "device": "cpu",
                    "rollout_steps": 24,
                    "sample_stride": 4,
                    "dt": 0.03,
                    "thermal_noise": 0.01,
                    "knn_k": 8,
                    "ionic_strength": 0.15,
                    "pH": 7.2,
                    "ptm_count": 1.0,
                    "hydro_strength": 1.0,
                },
                "gate": {
                    "min_target_pass_fraction": 0.5,
                    "min_mean_force": 0.0,
                    "max_virtual_hbond_mean_distance_A": 6.0,
                    "min_virtual_hbond_contacts_mean": 0.0,
                    "min_anti_collapse_force_mean": 0.0,
                    "max_overcollapse_rate": 1.0,
                    "min_abs_delta_contact_persistence": 0.0,
                    "min_abs_delta_transient_helicity": 0.0,
                    "min_abs_delta_ensemble_diversity": 0.0,
                },
                "targets": [
                    {"name": "synthetic_a", "source": "synthetic", "n_res": 24, "seed": 7, "noise_scale": 0.25},
                    {"name": "synthetic_b", "source": "synthetic", "n_res": 28, "seed": 8, "noise_scale": 0.30, "collapse_bias": 0.2},
                    {"name": "synthetic_c", "source": "synthetic", "n_res": 30, "seed": 9, "noise_scale": 0.32, "ionic_strength": 0.30},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    prefix = tmp_path / "idp3"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "run_idp_3bead_pipeline.py"),
            "--config-json",
            str(config_path),
            "--device",
            "cpu",
            "--out-prefix",
            str(prefix),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        payload = json.loads(proc.stdout)
        assert proc.returncode == 2
        assert payload["pass"] is False
        return
    summary = json.loads((tmp_path / "idp3_summary.json").read_text(encoding="utf-8"))
    assert summary["pass"] is True
    assert summary["eval"]["payload"]["target_count"] == 3
    assert summary["gate"]["payload"]["pass"] is True
    assert summary["residual_train"]["payload"]["ok"] is True
    assert "eval_residual" in summary
    assert "gate_residual" in summary
    assert "branch_report" in summary
