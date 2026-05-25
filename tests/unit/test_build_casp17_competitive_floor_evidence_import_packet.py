from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_evidence_import_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _dropzone_payload(folder: Path, row_fill: Path) -> dict:
    core = folder / "evidence_dropzone" / "files" / "core"
    target_identity = folder / "evidence_dropzone" / "target_identity"
    return {
        "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
        "rows": [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "action_rank": 1,
                "operator_priority": 1,
                "row_rank": 1,
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_class": "core_file",
                "template_column": "prediction_pdb",
                "source_row_fill_csv": str(row_fill),
                "dropzone_folder": str(folder / "evidence_dropzone"),
                "dropzone_class_folder": str(core),
                "drop_path": str(core / "<HISTORICAL_TARGET_ID>_prediction.pdb"),
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "action_rank": 2,
                "operator_priority": 1,
                "row_rank": 1,
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_class": "target_identity",
                "template_column": "target_id",
                "source_row_fill_csv": str(row_fill),
                "dropzone_folder": str(folder / "evidence_dropzone"),
                "dropzone_class_folder": str(target_identity),
                "drop_path": "",
            },
        ],
    }


def test_evidence_import_writes_blank_template_when_import_csv_missing(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001", "prediction_pdb": "REQUIRED_prediction.pdb"}])
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(dropzone_json, _dropzone_payload(folder, row_fill))
    import_csv = tmp_path / "import.csv"
    args = mod.parse_args(
        [
            "--dropzone-json",
            str(dropzone_json),
            "--import-csv",
            str(import_csv),
            "--out-json",
            str(tmp_path / "import.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "IMPORT.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["import_status"] == "awaiting_import"
    assert payload["summary"]["awaiting_import_file_count"] == 1
    assert payload["summary"]["awaiting_import_value_count"] == 1
    template_rows = _read_csv(import_csv)
    assert len(template_rows) == 2
    assert template_rows[0]["import_kind"] == "file"
    assert template_rows[1]["import_kind"] == "value"
    assert (folder / "EVIDENCE_IMPORT.csv").is_file()
    assert (folder / "EVIDENCE_IMPORT.md").is_file()


def test_evidence_import_dry_run_detects_ready_rows_without_mutating(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001", "prediction_pdb": "REQUIRED_prediction.pdb"}])
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "ledger_status": "awaiting_value",
                "next_action": "enter target",
            }
        ],
    )
    source_pdb = tmp_path / "T9001_prediction.pdb"
    source_pdb.write_text("HEADER TEST\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(dropzone_json, _dropzone_payload(folder, row_fill))
    import_csv = tmp_path / "import.csv"
    _write_csv(
        import_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "prediction_pdb",
                "source_path": str(source_pdb),
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "target_id",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            },
        ],
    )
    args = mod.parse_args(["--dropzone-json", str(dropzone_json), "--import-csv", str(import_csv)])

    payload = mod.build_payload(args)

    assert payload["summary"]["import_status"] == "ready_for_apply"
    assert payload["summary"]["ready_for_apply_count"] == 2
    assert payload["summary"]["applied_count"] == 0
    assert not (folder / "evidence_dropzone" / "files" / "core" / source_pdb.name).exists()
    ledger_rows = _read_csv(folder / "FIELD_VALUE_LEDGER.csv")
    assert ledger_rows[0]["proposed_value"] == ""


def test_evidence_import_apply_copies_files_and_updates_ledgers(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001", "prediction_pdb": "REQUIRED_prediction.pdb"}])
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "ledger_status": "awaiting_value",
                "next_action": "enter target",
            }
        ],
    )
    source_pdb = tmp_path / "T9001_prediction.pdb"
    source_pdb.write_text("HEADER TEST\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(dropzone_json, _dropzone_payload(folder, row_fill))
    import_csv = tmp_path / "import.csv"
    _write_csv(
        import_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "prediction_pdb",
                "source_path": str(source_pdb),
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "target_id",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            },
        ],
    )
    args = mod.parse_args(
        [
            "--dropzone-json",
            str(dropzone_json),
            "--import-csv",
            str(import_csv),
            "--out-json",
            str(tmp_path / "import.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "IMPORT.md"),
            "--apply",
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    copied = folder / "evidence_dropzone" / "files" / "core" / source_pdb.name
    assert payload["summary"]["applied_count"] == 2
    assert copied.read_text(encoding="utf-8") == source_pdb.read_text(encoding="utf-8")
    ledger_rows = _read_csv(folder / "FIELD_VALUE_LEDGER.csv")
    assert ledger_rows[0]["proposed_value"] == "T9001"
    assert ledger_rows[0]["evidence_ref"] == "local/no_leak/T9001.md"
    assert ledger_rows[0]["operator_clearance"] == "ready_for_row_fill"
    assert ledger_rows[0]["ledger_status"] == "ready_for_row_fill"


def test_evidence_import_blocks_invalid_column_typed_values(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"selected_model_rank": "REQUIRED_1_TO_5"}])
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "selected_model_rank",
                "evidence_class": "calibration",
                "current_value": "REQUIRED_1_TO_5",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "ledger_status": "awaiting_value",
                "next_action": "enter rank",
            }
        ],
    )
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(
        dropzone_json,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "calibration",
                    "template_column": "selected_model_rank",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(folder / "evidence_dropzone" / "calibration"),
                    "drop_path": "",
                }
            ],
        },
    )
    import_csv = tmp_path / "import.csv"
    _write_csv(
        import_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "selected_model_rank",
                "proposed_value": "6",
                "evidence_ref": "local/calibration/T9001.json",
                "operator_clearance": "ready_for_row_fill",
            }
        ],
    )
    args = mod.parse_args(["--dropzone-json", str(dropzone_json), "--import-csv", str(import_csv), "--apply"])

    payload = mod.build_payload(args)

    assert payload["summary"]["import_status"] == "blocked"
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["applied_count"] == 0
    assert payload["rows"][0]["import_status"] == "blocked_invalid_import_value"
    assert payload["rows"][0]["blocker"] == "selected_model_rank_requires_rank_1_to_5"
    assert payload["rows"][0]["expected_value_rule"] == "integer 1..5"
    ledger_rows = _read_csv(folder / "FIELD_VALUE_LEDGER.csv")
    assert ledger_rows[0]["proposed_value"] == ""
