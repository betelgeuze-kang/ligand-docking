from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_casp17_win_tier_benchmark_evidence_fill_kit_lists_required_items(tmp_path: Path) -> None:
    prediction = tmp_path / "prediction.pdb"
    native = tmp_path / "native.pdb"
    prediction.write_text("ATOM\n", encoding="utf-8")
    native.write_text("ATOM\n", encoding="utf-8")
    layer = tmp_path / "recursive.pdb"
    layer.write_text("ATOM\n", encoding="utf-8")
    template = tmp_path / "template.csv"
    dashboard = tmp_path / "dashboard.json"
    historical = tmp_path / "historical.json"
    sidechain_workorder = tmp_path / "sidechain_workorder.json"
    sidechain_priority_csv = tmp_path / "sidechain_priority.csv"
    row = {
        "benchmark_id": "hist_demo_001",
        "target_id": "DEMO001",
        "scope": "monomer",
        "split": "historical",
        "prediction_pdb": str(prediction),
        "native_pdb": str(native),
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics_v1",
        "prediction_created_at": "2025-01-01",
        "native_release_date": "2025-02-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
        "recursive_prediction_pdb": str(layer),
        "selected_model_rank": "1",
        "best_model_rank": "1",
        "selected_native_metric": "0.7",
        "best_native_metric": "0.8",
        "selected_score": "42.0",
        "best_score": "43.0",
    }
    _write_csv(template, [row])
    dashboard.write_text(
        json.dumps({"summary": {"dashboard_status": "ready", "ready_count": 0, "blocked_count": 1}}),
        encoding="utf-8",
    )
    historical.write_text(
        json.dumps(
            {
                "summary": {
                    "historical_benchmark_status": "pass",
                    "thresholds": {
                        "monomer_tm": 0.9,
                        "monomer_gdt_ts": 0.8,
                        "monomer_lddt": 0.75,
                    },
                },
                "rows": [
                    {
                        "benchmark_id": "hist_demo_001",
                        "benchmark_status": "pass",
                        "tm_score_proxy": 0.95,
                        "gdt_ts_proxy": 0.9,
                        "ca_lddt_proxy": 0.86,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sidechain_workorder.write_text(
        json.dumps(
            {
                "summary": {"sidechain_native_benchmark_status": "blocked"},
                "rows": [
                    {
                        "action_id": "hist_demo_001:leakage_clearance",
                        "action_status": "open",
                        "benchmark_id": "hist_demo_001",
                        "target_id": "DEMO001",
                        "scope": "monomer",
                        "evidence_class": "provenance",
                        "evidence_item": "leakage_clearance",
                        "source_column": "leakage_clearance",
                        "required_value": "operator-confirmed no_leak provenance",
                        "current_value": "required_no_leak_clearance",
                        "destination_path": "manifest row leakage_clearance",
                        "blocker": "leakage_clearance_missing_or_not_clear",
                        "next_action": "Replace placeholder leakage_clearance with operator-confirmed no_leak provenance.",
                    },
                    {
                        "action_id": "hist_demo_001:prediction_pdb",
                        "action_status": "open",
                        "benchmark_id": "hist_demo_001",
                        "target_id": "DEMO001",
                        "scope": "monomer",
                        "evidence_class": "core_file",
                        "evidence_item": "prediction_pdb",
                        "source_column": "prediction_pdb",
                        "required_value": "internal prediction PDB generated before native release",
                        "current_value": str(prediction),
                        "destination_path": str(prediction),
                        "blocker": "prediction_pdb_missing",
                        "next_action": "Place the internal prediction PDB at the manifest prediction_pdb path.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_win_tier_benchmark_evidence_fill_kit.py"),
            "--operator-template-csv",
            str(template),
            "--operator-dashboard-json",
            str(dashboard),
            "--historical-benchmark-json",
            str(historical),
            "--sidechain-native-workorder-json",
            str(sidechain_workorder),
            "--out-json",
            str(tmp_path / "kit.json"),
            "--out-csv",
            str(tmp_path / "kit.csv"),
            "--out-md",
            str(tmp_path / "kit.md"),
            "--out-html",
            str(tmp_path / "kit.html"),
            "--out-sidechain-native-priority-csv",
            str(sidechain_priority_csv),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "kit.json").read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = payload["rows"]
    priority_rows = payload["sidechain_native_priority_rows"]
    priority_csv_rows = list(csv.DictReader(sidechain_priority_csv.open(encoding="utf-8")))
    html = (tmp_path / "kit.html").read_text(encoding="utf-8")
    md = (tmp_path / "kit.md").read_text(encoding="utf-8")

    assert summary["fill_kit_status"] == "ready"
    assert summary["benchmark_row_count"] == 1
    assert summary["required_target_identity_count"] == 1
    assert summary["required_core_file_count"] == 2
    assert summary["required_ablation_layer_file_count"] == 10
    assert summary["required_provenance_field_count"] == 10
    assert summary["required_calibration_field_count"] == 6
    assert summary["required_native_metric_gate_count"] == 3
    assert summary["missing_by_class"]["native_metric_gate"] == 0
    assert summary["missing_by_class"]["ablation_layer_file"] == 9
    assert summary["sidechain_native_priority_status"] == "open"
    assert summary["sidechain_native_priority_action_count"] == 2
    assert summary["sidechain_native_priority_open_action_count"] == 2
    assert summary["sidechain_native_priority_missing_by_class"] == {"core_file": 1, "provenance": 1}
    assert summary["sidechain_native_priority_first_open_action_id"] == "hist_demo_001:leakage_clearance"
    assert summary["sidechain_native_priority_csv_path"].endswith("sidechain_priority.csv")
    assert priority_rows[0]["source"] == "sidechain_native_workorder"
    assert priority_rows[0]["next_action"].startswith("Replace placeholder leakage_clearance")
    assert priority_csv_rows[1]["evidence_class"] == "core_file"
    assert any(item["evidence_item"] == "internal_prediction_pdb" and item["completion_status"] == "filled" for item in rows)
    assert any(item["evidence_item"] == "statistical_rotamer" and item["completion_status"] == "missing" for item in rows)
    assert any(item["evidence_item"] == "monomer_tm_score_proxy" and item["completion_status"] == "filled" for item in rows)
    assert "CASP17 Benchmark Evidence Fill Kit" in html
    assert "Sidechain-Native Priority Lane" in html
    assert "sidechain-native priority" in md
    assert "http://" not in html
    assert "https://" not in html
    assert "Local evidence fill kit only" in summary["claim_boundary"]
