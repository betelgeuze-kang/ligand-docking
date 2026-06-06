from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_casp17_win_tier_benchmark_fill_priority_packet_orders_competitive_batch(tmp_path: Path) -> None:
    inventory_json = tmp_path / "inventory.json"
    evidence_json = tmp_path / "evidence.json"
    closure_json = tmp_path / "closure.json"
    out_json = tmp_path / "priority.json"
    out_csv = tmp_path / "priority.csv"
    out_md = tmp_path / "priority.md"

    inventory_json.write_text(
        json.dumps(
            {
                "summary": {"inventory_status": "blocked"},
                "rows": [
                    {
                        "row_rank": 1,
                        "benchmark_id": "hist_mono_001",
                        "target_id": "REQUIRED_MONOMER_001",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "inventory_status": "blocked",
                        "row_dir": "runs/casp17_win_tier_inputs/hist_mono_001",
                        "required_file_count": 12,
                        "present_file_count": 0,
                        "missing_file_count": 12,
                        "prediction_file_present": False,
                        "native_file_present": False,
                        "ablation_layer_present_count": 0,
                        "ablation_layer_required_count": 10,
                        "provenance_status": "blocked",
                        "calibration_status": "blocked",
                        "blockers": "placeholder_target_id,missing_files",
                    },
                    {
                        "row_rank": 2,
                        "benchmark_id": "hist_complex_001",
                        "target_id": "HIST_COMPLEX_001",
                        "scope": "complex",
                        "metric_profile": "TM,interface_F1,DockQ,QSbest,IPS",
                        "inventory_status": "blocked",
                        "row_dir": "runs/casp17_win_tier_inputs/hist_complex_001",
                        "required_file_count": 12,
                        "present_file_count": 2,
                        "missing_file_count": 10,
                        "prediction_file_present": True,
                        "native_file_present": True,
                        "ablation_layer_present_count": 0,
                        "ablation_layer_required_count": 10,
                        "provenance_status": "ready",
                        "calibration_status": "blocked",
                        "blockers": "missing_calibration,missing_ablation",
                    },
                    {
                        "row_rank": 30,
                        "benchmark_id": "hist_mono_030",
                        "target_id": "HIST_MONO_030",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "inventory_status": "blocked",
                        "row_dir": "runs/casp17_win_tier_inputs/hist_mono_030",
                        "required_file_count": 12,
                        "present_file_count": 0,
                        "missing_file_count": 12,
                        "prediction_file_present": False,
                        "native_file_present": False,
                        "ablation_layer_present_count": 0,
                        "ablation_layer_required_count": 10,
                        "provenance_status": "blocked",
                        "calibration_status": "blocked",
                        "blockers": "missing_files",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    evidence_json.write_text(
        json.dumps(
            {
                "summary": {
                    "fill_kit_status": "ready",
                    "sidechain_native_priority_status": "open",
                    "sidechain_native_priority_action_count": 2,
                    "sidechain_native_priority_open_action_count": 2,
                    "sidechain_native_priority_csv_path": "runs/sidechain_priority.csv",
                },
                "rows": [
                    {
                        "benchmark_id": "hist_mono_001",
                        "evidence_class": "target_identity",
                        "completion_status": "missing",
                    },
                    {
                        "benchmark_id": "hist_mono_001",
                        "evidence_class": "core_file",
                        "completion_status": "missing",
                    },
                    {
                        "benchmark_id": "hist_complex_001",
                        "evidence_class": "calibration_field",
                        "completion_status": "missing",
                    },
                    {
                        "benchmark_id": "hist_complex_001",
                        "evidence_class": "ablation_layer_file",
                        "completion_status": "missing",
                    },
                    {
                        "benchmark_id": "hist_mono_030",
                        "evidence_class": "core_file",
                        "completion_status": "missing",
                    },
                ],
                "sidechain_native_priority_rows": [
                    {
                        "action_id": "hist_mono_001:leakage_clearance",
                        "completion_status": "missing",
                        "benchmark_id": "hist_mono_001",
                        "target_id": "HIST_MONO_001",
                        "evidence_class": "provenance",
                        "next_action": "Replace placeholder leakage_clearance with operator-confirmed no_leak provenance.",
                    },
                    {
                        "action_id": "hist_mono_001:prediction_pdb",
                        "completion_status": "missing",
                        "benchmark_id": "hist_mono_001",
                        "target_id": "HIST_MONO_001",
                        "evidence_class": "core_file",
                        "next_action": "Place the internal prediction PDB at the manifest prediction_pdb path.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    closure_json.write_text(
        json.dumps(
            {
                "summary": {
                    "closure_plan_status": "ready",
                    "competitive_required_monomer_rows": 1,
                    "competitive_required_complex_rows": 1,
                    "win_required_monomer_rows": 2,
                    "win_required_complex_rows": 1,
                }
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_fill_priority_packet.py"),
            "--input-inventory-json",
            str(inventory_json),
            "--evidence-fill-kit-json",
            str(evidence_json),
            "--closure-plan-json",
            str(closure_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    summary = payload["summary"]
    rows = payload["rows"]
    csv_rows = list(csv.DictReader(out_csv.open(encoding="utf-8")))
    md = out_md.read_text(encoding="utf-8")

    assert summary["fill_priority_status"] == "ready"
    assert summary["row_count"] == 3
    assert summary["competitive_batch_row_count"] == 2
    assert summary["competitive_batch_monomer_count"] == 1
    assert summary["competitive_batch_complex_count"] == 1
    assert summary["win_required_row_count"] == 3
    assert summary["missing_evidence_by_class"]["core_file"] == 2
    assert summary["sidechain_native_priority_status"] == "open"
    assert summary["sidechain_native_priority_open_action_count"] == 2
    assert summary["sidechain_native_first_open_action_id"] == "hist_mono_001:leakage_clearance"
    assert summary["sidechain_native_first_open_next_action"].startswith("Replace placeholder")
    assert rows[0]["benchmark_id"] == "hist_mono_001"
    assert rows[0]["fill_batch"] == "competitive_floor_batch"
    assert rows[0]["next_action"].startswith("Replace placeholder target identity")
    assert rows[1]["benchmark_id"] == "hist_complex_001"
    assert rows[1]["next_action"].startswith("Fill selected/best rank")
    assert rows[2]["fill_batch"] == "win_extension_batch"
    assert csv_rows[0]["operator_priority"] == "1"
    assert "CASP17 Win-Tier Benchmark Fill Priority Packet" in md
    assert "sidechain-native priority" in md
    assert any("build_casp17_sidechain_native_manifest_sync_packet.py" in command for command in summary["post_fill_validation_commands"])
    assert any("build_casp17_sidechain_native_benchmark_packet.py" in command for command in summary["post_fill_validation_commands"])
    assert any("casp17_sidechain_native_manifest_candidate_current.csv" in command for command in summary["post_fill_validation_commands"])
    assert "Local fill-priority planning only" in summary["claim_boundary"]
