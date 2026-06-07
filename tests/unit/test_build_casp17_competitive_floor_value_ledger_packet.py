from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_value_ledger_packet as mod


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


def _dropzone(path: Path, folder: Path) -> Path:
    row_fill = folder / "row_fill.csv"
    row_fill.parent.mkdir(parents=True, exist_ok=True)
    row_fill.write_text("benchmark_id,target_id\n", encoding="utf-8")
    _write_json(
        path,
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
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "current_value": "REQUIRED_MONOMER_001",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 2,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "current_value": "REQUIRED_prediction.pdb",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                },
            ],
        },
    )
    return path


def test_value_ledger_seeds_non_file_actions_only(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    dropzone = _dropzone(tmp_path / "dropzone.json", folder)
    args = mod.parse_args(
        [
            "--dropzone-json",
            str(dropzone),
            "--out-json",
            str(tmp_path / "ledger.json"),
            "--out-csv",
            str(tmp_path / "ledger.csv"),
            "--out-md",
            str(tmp_path / "LEDGER.md"),
        ]
    )

    mod.write_outputs(args, mod.build_payload(args))

    payload = json.loads((tmp_path / "ledger.json").read_text(encoding="utf-8"))
    assert payload["summary"]["value_ledger_status"] == "awaiting_values"
    assert payload["summary"]["ledger_count"] == 1
    assert payload["summary"]["action_count"] == 1
    rows = _read_csv(folder / "FIELD_VALUE_LEDGER.csv")
    assert [row["template_column"] for row in rows] == ["target_id"]
    assert rows[0]["operator_clearance"] == "REQUIRED_OPERATOR_CLEARANCE"
    assert (folder / "FIELD_VALUE_LEDGER.md").is_file()


def test_value_ledger_reports_ready_for_intake_when_value_is_cleared(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    dropzone = _dropzone(tmp_path / "dropzone.json", folder)
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
                "ledger_status": "ready_for_row_fill",
                "next_action": "use this target_id",
            }
        ],
    )
    args = mod.parse_args(["--dropzone-json", str(dropzone), "--no-write-ledgers"])

    payload = mod.build_payload(args)

    assert payload["summary"]["value_ledger_status"] == "ready_for_intake"
    assert payload["summary"]["ready_for_intake_count"] == 1
    assert payload["rows"][0]["proposed_value"] == "T9001"
