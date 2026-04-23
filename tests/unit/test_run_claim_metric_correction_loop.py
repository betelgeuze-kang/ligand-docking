import json
from pathlib import Path

import pandas as pd

from tools import run_claim_metric_correction_loop as loop_runner


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_policy(path: Path) -> None:
    payload = {
        "version": "test_policy_claim_v1",
        "domains": [
            {
                "name": "core",
                "required_for_core_gate": True,
                "required_for_claim": True,
                "metrics": [
                    {
                        "name": "avg_neighbor_jaccard",
                        "source": "strict_summary",
                        "operator": "==",
                        "threshold": 1.0,
                    }
                ],
            },
            {
                "name": "structure",
                "required_for_core_gate": True,
                "required_for_claim": True,
                "metrics": [
                    {
                        "name": "avg_rmsd_vs_native_aligned_A",
                        "source": "accuracy_external_csv",
                        "operator": "<=",
                        "threshold": 0.1,
                    }
                ],
            },
            {
                "name": "thermo",
                "required_for_core_gate": False,
                "required_for_claim": True,
                "metrics": [
                    {
                        "name": "deltaG_rmse_kcal_mol",
                        "source": "thermo_json",
                        "operator": "<=",
                        "threshold": 0.5,
                    },
                    {
                        "name": "state_population_jsd",
                        "source": "thermo_json",
                        "operator": "<=",
                        "threshold": 0.05,
                    },
                    {
                        "name": "pmf_1d_emd",
                        "source": "thermo_json",
                        "operator": "<=",
                        "threshold": 0.2,
                    },
                ],
            },
            {
                "name": "kinetics",
                "required_for_core_gate": False,
                "required_for_claim": True,
                "metrics": [
                    {
                        "name": "log10_mfpt_error",
                        "source": "kinetics_json",
                        "operator": "<=",
                        "threshold": 0.3,
                    },
                    {
                        "name": "implied_timescale_rel_error",
                        "source": "kinetics_json",
                        "operator": "<=",
                        "threshold": 0.15,
                    },
                ],
            },
            {
                "name": "experiment",
                "required_for_core_gate": False,
                "required_for_claim": True,
                "metrics": [
                    {
                        "name": "nmr_noe_violation_rate",
                        "source": "experiment_json",
                        "operator": "<=",
                        "threshold": 0.1,
                    }
                ],
            },
        ],
    }
    _write_json(path, payload)


def _write_strict_summary(path: Path) -> None:
    payload = {
        "summary": {"pass": True, "targets": 10},
        "gates": {
            "accuracy_gate": {
                "avg_neighbor_jaccard": 1.0,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "speed": {"avg_speedup_on_vs_off": 50.0},
            "long_stability": {"passed_targets": 10},
        },
    }
    _write_json(path, payload)


def test_claim_metric_correction_loop_reduces_failures(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    thermo_csv = tmp_path / "thermo.csv"
    kinetics_csv = tmp_path / "kinetics.csv"
    experiment_csv = tmp_path / "exp.csv"
    out_prefix = tmp_path / "loop_out"

    _write_policy(policy)
    _write_strict_summary(strict_json)
    pd.DataFrame([{"target": "A", "avg_rmsd_vs_native_aligned": 0.05}]).to_csv(acc_csv, index=False)
    pd.DataFrame(
        [
            {
                "target": "A",
                "deltaG_rmse_kcal_mol": 10.0,
                "state_population_jsd": 0.30,
                "pmf_1d_emd": 0.45,
            },
            {
                "target": "B",
                "deltaG_rmse_kcal_mol": 8.0,
                "state_population_jsd": 0.20,
                "pmf_1d_emd": 0.30,
            },
        ]
    ).to_csv(thermo_csv, index=False)
    pd.DataFrame(
        [
            {"target": "A", "mfpt_pred": 6.0, "mfpt_ref": 6.0, "its_pred": 12.0, "its_ref": 8.0},
            {"target": "B", "mfpt_pred": 5.0, "mfpt_ref": 5.0, "its_pred": 9.0, "its_ref": 7.0},
        ]
    ).to_csv(kinetics_csv, index=False)
    pd.DataFrame(
        [
            {
                "target": "A",
                "nmr_noe_violation_rate": 0.01,
                "cryoem_map_cc": 0.95,
                "saxs_chi2": 1.0,
            }
        ]
    ).to_csv(experiment_csv, index=False)

    payload = loop_runner.run_loop(
        loop_runner.build_parser().parse_args(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--accuracy-external-csv",
                str(acc_csv),
                "--thermo-input-csv",
                str(thermo_csv),
                "--kinetics-input-csv",
                str(kinetics_csv),
                "--experiment-input-csv",
                str(experiment_csv),
                "--out-prefix",
                str(out_prefix),
                "--max-iters",
                "6",
            ]
        )
    )

    summary = payload["summary"]
    assert summary["initial_fail_count"] >= 1
    assert summary["best_fail_count"] < summary["initial_fail_count"]
    assert summary["claim_failed_metrics_after_runner"] <= summary["initial_fail_count"]
    assert "objective_breakdown" in payload["best"]
    assert "hard_objective" in payload["best"]["objective_breakdown"]
    assert "soft_objective" in payload["best"]["objective_breakdown"]
    assert Path(f"{out_prefix}_summary.json").exists()
    assert Path(f"{out_prefix}_claim_gate.csv").exists()
