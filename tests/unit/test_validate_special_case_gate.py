import json

import pandas as pd

from tools import validate_special_case_gate as vg


def _write_policy(path):
    payload = {
        "common": {"require_core_gate_pass": True, "fail_on_overflow_or_saturation": True},
        "domains": {
            "metal": {
                "metrics": [
                    {"name": "coordination_number_mae", "operator": "<=", "threshold": 0.3},
                    {"name": "metal_ligand_distance_rmse_A", "operator": "<=", "threshold": 0.35},
                ]
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_labels(path, *, mae=0.2, dist=0.3, overflow=0):
    payload = {
        "summary": {
            "metrics": {
                "coordination_number_mae": mae,
                "metal_ligand_distance_rmse_A": dist,
            },
            "overflow_events_count": int(overflow),
        },
        "per_target": [
            {
                "target": "M1",
                "coordination_number_mae": mae,
                "metal_ligand_distance_rmse_A": dist,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_core(path, passed=True):
    path.write_text(json.dumps({"summary": {"pass": bool(passed)}, "overflow_events": []}), encoding="utf-8")


def test_validate_special_case_gate_pass(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "M1"}]).to_csv(manifest, index=False)
    labels = tmp_path / "labels.json"
    policy = tmp_path / "policy.json"
    core = tmp_path / "core.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    _write_policy(policy)
    _write_labels(labels, mae=0.2, dist=0.31, overflow=0)
    _write_core(core, passed=True)

    args = vg.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--manifest-csv",
            str(manifest),
            "--labels-json",
            str(labels),
            "--policy-json",
            str(policy),
            "--core-gate-json",
            str(core),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
        ]
    )
    payload = vg.run_gate(args)
    assert payload["summary"]["pass"] is True


def test_validate_special_case_gate_metric_fail(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "M1"}]).to_csv(manifest, index=False)
    labels = tmp_path / "labels.json"
    policy = tmp_path / "policy.json"
    core = tmp_path / "core.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    _write_policy(policy)
    _write_labels(labels, mae=0.6, dist=0.31, overflow=0)
    _write_core(core, passed=True)

    args = vg.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--manifest-csv",
            str(manifest),
            "--labels-json",
            str(labels),
            "--policy-json",
            str(policy),
            "--core-gate-json",
            str(core),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
        ]
    )
    payload = vg.run_gate(args)
    assert payload["summary"]["pass"] is False
    assert len(payload["summary"]["failed_metrics"]) >= 1


def test_validate_special_case_gate_overflow_fail(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"target": "M1"}]).to_csv(manifest, index=False)
    labels = tmp_path / "labels.json"
    policy = tmp_path / "policy.json"
    core = tmp_path / "core.json"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    _write_policy(policy)
    _write_labels(labels, mae=0.2, dist=0.31, overflow=1)
    _write_core(core, passed=True)

    args = vg.build_parser().parse_args(
        [
            "--domain",
            "metal",
            "--manifest-csv",
            str(manifest),
            "--labels-json",
            str(labels),
            "--policy-json",
            str(policy),
            "--core-gate-json",
            str(core),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
        ]
    )
    payload = vg.run_gate(args)
    assert payload["summary"]["pass"] is False
    assert payload["summary"]["overflow_events_count"] > 0
