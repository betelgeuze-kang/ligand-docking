import json
from pathlib import Path

import pandas as pd
import pytest

from tools import run_allatom_claim_readiness as runner


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
                        "tolerance": 0.0,
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
                    }
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
                    }
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
            "speed": {"avg_speedup_on_vs_off": 100.0},
            "long_stability": {"passed_targets": 10},
        },
    }
    _write_json(path, payload)


def _write_accuracy_csv(path: Path) -> None:
    pd.DataFrame([{"target": "A", "avg_rmsd_vs_native_aligned": 0.05}]).to_csv(path, index=False)


def test_claim_runner_builds_from_csv_and_outputs_artifacts(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    _write_policy(policy)
    _write_strict_summary(strict_json)
    _write_accuracy_csv(acc_csv)

    kinetics_in = tmp_path / "k.csv"
    thermo_in = tmp_path / "t.csv"
    exp_in = tmp_path / "e.csv"
    pd.DataFrame([{"target": "A", "mfpt_pred": 10.0, "mfpt_ref": 10.0, "its_pred": 5.0, "its_ref": 5.0}]).to_csv(
        kinetics_in, index=False
    )
    pd.DataFrame([{"target": "A", "deltaG_rmse_kcal_mol": 0.2, "state_population_jsd": 0.01, "pmf_1d_emd": 0.1}]).to_csv(
        thermo_in, index=False
    )
    pd.DataFrame([{"target": "A", "nmr_noe_violation_rate": 0.05, "cryoem_map_cc": 0.9, "saxs_chi2": 1.0}]).to_csv(
        exp_in, index=False
    )

    out_json = tmp_path / "summary.json"
    out_csv = tmp_path / "summary.csv"
    out_md = tmp_path / "summary.md"
    gate_json = tmp_path / "gate.json"
    gate_csv = tmp_path / "gate.csv"
    prefix = tmp_path / "bundle"

    payload = runner.run_pipeline(
        runner.build_parser().parse_args(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--accuracy-external-csv",
                str(acc_csv),
                "--kinetics-input-csv",
                str(kinetics_in),
                "--thermo-input-csv",
                str(thermo_in),
                "--experiment-input-csv",
                str(exp_in),
                "--intermediate-prefix",
                str(prefix),
                "--gate-out-json",
                str(gate_json),
                "--gate-out-csv",
                str(gate_csv),
                "--out-json",
                str(out_json),
                "--out-csv",
                str(out_csv),
                "--out-md",
                str(out_md),
            ]
        )
    )

    assert payload["summary"]["pass_core_gate"] is True
    assert payload["summary"]["claim_ready_for_allatom"] is True
    assert gate_json.exists()
    assert gate_csv.exists()
    assert out_json.exists()
    assert out_csv.exists()
    assert out_md.exists()


def test_claim_runner_allows_partial_claim_by_default(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    _write_policy(policy)
    _write_strict_summary(strict_json)
    _write_accuracy_csv(acc_csv)

    kinetics_json = tmp_path / "k.json"
    _write_json(kinetics_json, {"metrics": {"log10_mfpt_error": 0.2}})

    payload = runner.run_pipeline(
        runner.build_parser().parse_args(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--accuracy-external-csv",
                str(acc_csv),
                "--kinetics-json",
                str(kinetics_json),
                "--out-json",
                str(tmp_path / "s.json"),
                "--out-csv",
                str(tmp_path / "s.csv"),
                "--out-md",
                str(tmp_path / "s.md"),
                "--gate-out-json",
                str(tmp_path / "g.json"),
                "--gate-out-csv",
                str(tmp_path / "g.csv"),
                "--intermediate-prefix",
                str(tmp_path / "p"),
            ]
        )
    )

    assert payload["summary"]["pass_core_gate"] is True
    assert payload["summary"]["claim_ready_for_allatom"] is False
    assert payload["summary"]["claim_missing_metrics"] >= 1


def test_claim_runner_enforce_complete_claim_exits_nonzero(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    _write_policy(policy)
    _write_strict_summary(strict_json)
    _write_accuracy_csv(acc_csv)

    with pytest.raises(SystemExit) as exc_info:
        runner.main(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--accuracy-external-csv",
                str(acc_csv),
                "--enforce-complete-claim",
                "--out-json",
                str(tmp_path / "s.json"),
                "--out-csv",
                str(tmp_path / "s.csv"),
                "--out-md",
                str(tmp_path / "s.md"),
                "--gate-out-json",
                str(tmp_path / "g.json"),
                "--gate-out-csv",
                str(tmp_path / "g.csv"),
                "--intermediate-prefix",
                str(tmp_path / "p"),
            ]
        )
    assert exc_info.value.code == 2
