from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_execution_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, identity_json: Path, file_json: Path, value_json: Path) -> list[str]:
    return [
        "--identity-kit-json",
        str(identity_json),
        "--file-source-plan-json",
        str(file_json),
        "--value-entry-plan-json",
        str(value_json),
        "--out-json",
        str(tmp_path / "board.json"),
        "--out-csv",
        str(tmp_path / "board.csv"),
        "--out-md",
        str(tmp_path / "BOARD.md"),
    ]


def test_execution_board_surfaces_identity_first(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    file_json = tmp_path / "file.json"
    value_json = tmp_path / "value.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "awaiting_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "identity_status": "awaiting_identity",
                    "blockers": "proposed_target_id_required",
                    "next_action": "fill proposed target",
                }
            ],
        },
    )
    _write_json(
        file_json,
        {
            "summary": {"file_source_status": "waiting_on_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "file_source_status": "waiting_on_identity",
                }
            ],
        },
    )
    _write_json(
        value_json,
        {
            "summary": {"value_entry_status": "waiting_on_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "value_entry_status": "waiting_on_identity",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, identity_json, file_json, value_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["execution_board_status"] == "awaiting_identity"
    assert payload["summary"]["awaiting_identity_row_count"] == 1
    assert payload["summary"]["total_file_action_count"] == 1
    assert payload["summary"]["total_value_action_count"] == 1
    assert payload["rows"][0]["row_execution_status"] == "awaiting_identity"
    assert _read_csv(tmp_path / "board.csv")[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert (tmp_path / "BOARD.md").is_file()


def test_execution_board_promotes_ready_identity_apply_before_file_sources(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    file_json = tmp_path / "file.json"
    value_json = tmp_path / "value.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "ready_for_import"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "identity_status": "ready_for_import",
                    "proposed_target_id": "T9001",
                }
            ],
        },
    )
    _write_json(
        file_json,
        {
            "summary": {"file_source_status": "awaiting_source_paths"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "file_source_status": "awaiting_source_path",
                    "next_action": "enter source path",
                }
            ],
        },
    )
    _write_json(
        value_json,
        {
            "summary": {"value_entry_status": "ready_for_identity_apply"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "value_entry_status": "ready_from_identity_kit",
                    "next_action": "apply identity values",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, identity_json, file_json, value_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["execution_board_status"] == "ready_for_identity_apply"
    assert payload["summary"]["ready_for_identity_apply_row_count"] == 1
    assert payload["rows"][0]["row_execution_status"] == "ready_for_identity_apply"
    assert payload["rows"][0]["next_action"] == "apply identity values"


def test_execution_board_tracks_file_and_value_phases(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    file_json = tmp_path / "file.json"
    value_json = tmp_path / "value.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "ready_for_import"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "identity_status": "ready_for_import",
                    "proposed_target_id": "T9001",
                },
                {
                    "dropzone_id": "priority_002_REQUIRED_MONOMER_002",
                    "operator_priority": 2,
                    "row_rank": 2,
                    "scope": "monomer",
                    "identity_status": "ready_for_import",
                    "proposed_target_id": "T9002",
                },
            ],
        },
    )
    _write_json(
        file_json,
        {
            "summary": {"file_source_status": "awaiting_source_paths"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "file_source_status": "awaiting_source_path",
                    "next_action": "enter source path",
                },
                {
                    "dropzone_id": "priority_002_REQUIRED_MONOMER_002",
                    "file_source_status": "ready_for_import",
                    "next_action": "apply file import",
                },
            ],
        },
    )
    _write_json(
        value_json,
        {
            "summary": {"value_entry_status": "awaiting_values"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "value_entry_status": "ready_for_import",
                    "next_action": "apply value import",
                },
                {
                    "dropzone_id": "priority_002_REQUIRED_MONOMER_002",
                    "value_entry_status": "awaiting_value",
                    "next_action": "enter calibration",
                },
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, identity_json, file_json, value_json))

    payload = mod.build_payload(args)
    by_id = {row["dropzone_id"]: row for row in payload["rows"]}

    assert payload["summary"]["execution_board_status"] == "awaiting_file_sources"
    assert by_id["priority_001_REQUIRED_MONOMER_001"]["row_execution_status"] == "awaiting_file_sources"
    assert by_id["priority_002_REQUIRED_MONOMER_002"]["row_execution_status"] == "awaiting_values"
