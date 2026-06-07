import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_batch_packet as mod


def test_build_casp17_competitive_floor_batch_packet_materializes_competitive_rows(tmp_path):
    scaffold = tmp_path / "scaffold" / "row_001_REQUIRED_MONOMER_001"
    scaffold.mkdir(parents=True)
    (scaffold / "README.md").write_text("# row\n", encoding="utf-8")
    (scaffold / "required_files.csv").write_text("file_role,template_column,expected_path\n", encoding="utf-8")
    fill_priority = tmp_path / "fill_priority.json"
    fill_priority.write_text(
        json.dumps(
            {
                "summary": {"fill_priority_status": "ready"},
                "rows": [
                    {
                        "operator_priority": 1,
                        "fill_batch": "competitive_floor_batch",
                        "row_rank": 1,
                        "benchmark_id": "hist_REQUIRED_MONOMER_001",
                        "target_id": "REQUIRED_MONOMER_001",
                        "scope": "monomer",
                        "metric_profile": "TM,GDT_TS,CA_lDDT",
                        "row_dir": str(scaffold),
                        "missing_evidence_item_count": 32,
                        "missing_file_count": 12,
                        "missing_ablation_layer_file_count": 10,
                        "missing_provenance_field_count": 10,
                        "missing_calibration_field_count": 6,
                        "missing_native_metric_gate_count": 3,
                        "next_action": "Replace placeholder target identity.",
                    },
                    {
                        "operator_priority": 2,
                        "fill_batch": "win_extension_batch",
                        "row_rank": 16,
                        "benchmark_id": "hist_REQUIRED_MONOMER_016",
                        "target_id": "REQUIRED_MONOMER_016",
                        "scope": "monomer",
                        "row_dir": str(tmp_path / "not_selected"),
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    args = mod.parse_args(
        [
            "--fill-priority-json",
            str(fill_priority),
            "--out-dir",
            str(tmp_path / "batch"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_status"] == "ready_for_fill"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["monomer_row_count"] == 1
    assert payload["summary"]["missing_evidence_item_count"] == 32
    row = payload["rows"][0]
    assert row["batch_row_status"] == "ready_for_fill"
    assert "placeholder_target_id" in row["blockers"]
    assert Path(row["copied_row_scaffold"]).is_dir()
    assert Path(row["row_metadata_template_csv"]).is_file()
    assert Path(row["row_fill_template_csv"]).is_file()
    assert Path(row["task_md"]).is_file()
    task_text = Path(row["task_md"]).read_text(encoding="utf-8")
    assert "Fill Checklist" in task_text
    assert "row_fill.csv" in task_text
    assert "row_metadata.csv" in task_text
    fill_text = Path(row["row_fill_template_csv"]).read_text(encoding="utf-8")
    assert "prediction_pdb" in fill_text
    assert "prediction_generated_before_native_release" in fill_text


def test_build_casp17_competitive_floor_batch_packet_blocks_missing_row_dir(tmp_path):
    fill_priority = tmp_path / "fill_priority.json"
    fill_priority.write_text(
        json.dumps(
            {
                "summary": {"fill_priority_status": "ready"},
                "rows": [
                    {
                        "operator_priority": 1,
                        "fill_batch": "competitive_floor_batch",
                        "row_rank": 1,
                        "benchmark_id": "hist_REQUIRED_COMPLEX_001",
                        "target_id": "REQUIRED_COMPLEX_001",
                        "scope": "complex",
                        "row_dir": str(tmp_path / "missing"),
                        "missing_evidence_item_count": 34,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    args = mod.parse_args(
        [
            "--fill-priority-json",
            str(fill_priority),
            "--out-dir",
            str(tmp_path / "batch"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_status"] == "blocked"
    assert payload["rows"][0]["batch_row_status"] == "blocked"
    assert "row_dir_not_found" in payload["rows"][0]["blockers"]
