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


def test_allatom_gate_exposes_strict_gate_pass_metrics_for_representative_scope(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    _write_json(
        policy,
        {
            "version": "representative_scope_test",
            "domains": [
                {
                    "name": "core",
                    "required_for_core_gate": True,
                    "required_for_claim": True,
                    "metrics": [
                        {
                            "name": "long_stability_gate_pass",
                            "source": "strict_summary",
                            "operator": ">=",
                            "threshold": 1.0,
                        },
                        {
                            "name": "speed_gate_pass",
                            "source": "strict_summary",
                            "operator": ">=",
                            "threshold": 1.0,
                        },
                    ],
                }
            ],
        },
    )
    _write_json(
        strict_json,
        {
            "summary": {"pass": True, "targets": 1},
            "gates": {
                "long_stability": {"pass": True, "passed_targets": 1},
                "speed": {
                    "pass": True,
                    "enforced": False,
                    "avg_speedup_on_vs_off": 8.0,
                    "reason": "skipped_for_single_target_scope",
                },
            },
        },
    )

    payload = gate.run_gate(
        gate.build_parser().parse_args(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--expected-target-count",
                "1",
                "--out-json",
                str(out_json),
                "--out-csv",
                str(out_csv),
            ]
        )
    )

    assert payload["summary"]["pass_core_gate"] is True
    strict_metrics = payload["observed_sources"]["strict_summary"]
    assert strict_metrics["long_stability_gate_pass"] == 1.0
    assert strict_metrics["speed_gate_pass"] == 1.0
    assert strict_metrics["speed_gate_enforced"] == 0.0


def test_allatom_gate_fails_when_enforced_strict_speed_gate_fails(tmp_path):
    policy = tmp_path / "policy.json"
    strict_json = tmp_path / "strict.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    _write_json(
        policy,
        {
            "version": "representative_scope_test",
            "domains": [
                {
                    "name": "core",
                    "required_for_core_gate": True,
                    "required_for_claim": True,
                    "metrics": [
                        {
                            "name": "speed_gate_pass",
                            "source": "strict_summary",
                            "operator": ">=",
                            "threshold": 1.0,
                        }
                    ],
                }
            ],
        },
    )
    _write_json(
        strict_json,
        {
            "summary": {"pass": False, "targets": 10},
            "gates": {
                "speed": {
                    "pass": False,
                    "enforced": True,
                    "avg_speedup_on_vs_off": 8.0,
                    "reason": "avg_speedup_on_vs_off=8.0",
                }
            },
        },
    )

    payload = gate.run_gate(
        gate.build_parser().parse_args(
            [
                "--policy-json",
                str(policy),
                "--strict-summary-json",
                str(strict_json),
                "--expected-target-count",
                "10",
                "--out-json",
                str(out_json),
                "--out-csv",
                str(out_csv),
            ]
        )
    )

    assert payload["summary"]["pass_core_gate"] is False
    assert payload["summary"]["core_failed_metrics"] == 1
    row = pd.read_csv(out_csv).iloc[0]
    assert row["metric"] == "speed_gate_pass"
    assert row["observed"] == 0.0
