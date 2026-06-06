from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_evidence_unlock_priority as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_unlock_priority_ranks_identity_before_file_and_values(tmp_path: Path) -> None:
    import_json = tmp_path / "import.json"
    _write_json(
        import_json,
        {
            "summary": {"import_status": "awaiting_import", "action_count": 4},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "benchmark_id",
                    "evidence_class": "target_identity",
                    "import_kind": "value",
                    "import_status": "awaiting_import_value",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "target_id",
                    "evidence_class": "target_identity",
                    "import_kind": "value",
                    "import_status": "awaiting_import_value",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "prediction_pdb",
                    "evidence_class": "core_file",
                    "import_kind": "file",
                    "import_status": "awaiting_import_file",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "selected_model_rank",
                    "evidence_class": "calibration",
                    "import_kind": "value",
                    "import_status": "awaiting_import_value",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--import-json",
            str(import_json),
            "--import-csv",
            str(tmp_path / "missing.csv"),
            "--out-json",
            str(tmp_path / "unlock.json"),
            "--out-csv",
            str(tmp_path / "unlock.csv"),
            "--out-md",
            str(tmp_path / "UNLOCK.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["unlock_status"] == "identity_unlock_required"
    assert payload["summary"]["identity_open_action_count"] == 2
    assert payload["summary"]["target_id_open_count"] == 1
    assert payload["summary"]["file_actions_waiting_on_identity_count"] == 1
    assert payload["summary"]["first_open_phase"] == "identity_unlock"
    assert payload["rows"][0]["phase"] == "identity_unlock"
    assert payload["rows"][0]["downstream_blocked_file_actions"] == 1
    assert _read_csv(tmp_path / "unlock.csv")[0]["phase"] == "identity_unlock"
    assert (tmp_path / "UNLOCK.md").is_file()


def test_unlock_priority_marks_identity_complete_when_target_id_imported(tmp_path: Path) -> None:
    import_json = tmp_path / "import.json"
    _write_json(
        import_json,
        {
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "benchmark_id",
                    "evidence_class": "target_identity",
                    "import_kind": "value",
                    "import_status": "ledger_updated",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "target_id",
                    "evidence_class": "target_identity",
                    "import_kind": "value",
                    "import_status": "ledger_updated",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "template_column": "prediction_pdb",
                    "evidence_class": "core_file",
                    "import_kind": "file",
                    "import_status": "awaiting_import_file",
                },
            ]
        },
    )
    args = mod.parse_args(["--import-json", str(import_json), "--import-csv", str(tmp_path / "missing.csv")])

    payload = mod.build_payload(args)
    identity = next(row for row in payload["rows"] if row["phase"] == "identity_unlock")

    assert identity["unlock_status"] == "complete"
    assert identity["downstream_unlocked_file_actions"] == 1
    assert identity["downstream_blocked_file_actions"] == 0
    assert payload["summary"]["identity_open_action_count"] == 0
    assert payload["summary"]["target_id_open_count"] == 0
