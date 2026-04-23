import json
from pathlib import Path

import pandas as pd

from tools import evaluate_allatom_equivalence_gate as gate


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_policy(path: Path) -> None:
    payload = {
        "version": "test_policy_v1",
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
                    },
                    {
                        "name": "avg_rmsd_vs_native_aligned_A",
                        "source": "accuracy_external_csv",
                        "operator": "<=",
                        "threshold": 0.1,
                    },
                ],
            },
            {
                "name": "thermo_claim_only",
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
        ],
    }
    _write_json(path, payload)


def _write_strict_summary(path: Path, jaccard: float = 1.0) -> None:
    payload = {
        "summary": {"pass": True, "targets": 10},
        "gates": {
            "accuracy_gate": {
                "avg_neighbor_jaccard": jaccard,
                "avg_e2e_rmse_raw": 0.2,
                "avg_e2e_rel_rmse_mean_clipped": 1e-7,
            },
            "speed": {"avg_speedup_on_vs_off": 100.0},
            "long_stability": {"passed_targets": 10},
        },
    }
    _write_json(path, payload)


def _write_accuracy_csv(path: Path, val: float = 0.05) -> None:
    pd.DataFrame(
        [
            {"target": "A", "avg_rmsd_vs_native_aligned": val},
            {"target": "B", "avg_rmsd_vs_native_aligned": val},
        ]
    ).to_csv(path, index=False)


def test_allatom_gate_core_pass_claim_not_ready_when_missing_claim_sources(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    _write_policy(policy)
    _write_strict_summary(strict_json, jaccard=1.0)
    _write_accuracy_csv(acc_csv, val=0.05)

    args = gate.build_parser().parse_args(
        [
            "--policy-json",
            str(policy),
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(acc_csv),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
        ]
    )
    payload = gate.run_gate(args)

    assert payload["summary"]["pass_core_gate"] is True
    assert payload["summary"]["claim_ready_for_allatom"] is False
    assert payload["summary"]["claim_missing_metrics"] == 1


def test_allatom_gate_claim_ready_when_all_sources_present(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    thermo_json = tmp_path / "thermo.json"
    _write_policy(policy)
    _write_strict_summary(strict_json, jaccard=1.0)
    _write_accuracy_csv(acc_csv, val=0.05)
    _write_json(thermo_json, {"deltaG_rmse_kcal_mol": 0.2})

    args = gate.build_parser().parse_args(
        [
            "--policy-json",
            str(policy),
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(acc_csv),
            "--thermo-json",
            str(thermo_json),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
        ]
    )
    payload = gate.run_gate(args)

    assert payload["summary"]["pass_core_gate"] is True
    assert payload["summary"]["claim_ready_for_allatom"] is True
    assert payload["summary"]["claim_missing_metrics"] == 0


def test_allatom_gate_core_fail_when_threshold_violated(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    acc_csv = tmp_path / "acc.csv"
    _write_policy(policy)
    _write_strict_summary(strict_json, jaccard=0.99)
    _write_accuracy_csv(acc_csv, val=0.05)

    args = gate.build_parser().parse_args(
        [
            "--policy-json",
            str(policy),
            "--strict-summary-json",
            str(strict_json),
            "--accuracy-external-csv",
            str(acc_csv),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
        ]
    )
    payload = gate.run_gate(args)

    assert payload["summary"]["pass_core_gate"] is False
    assert payload["summary"]["core_failed_metrics"] == 1

