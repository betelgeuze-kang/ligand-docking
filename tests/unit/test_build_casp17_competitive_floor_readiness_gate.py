from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_readiness_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, board_json: Path) -> list[str]:
    return [
        "--execution-board-json",
        str(board_json),
        "--out-json",
        str(tmp_path / "gate.json"),
        "--out-csv",
        str(tmp_path / "gate.csv"),
        "--out-md",
        str(tmp_path / "GATE.md"),
    ]


def test_readiness_gate_blocks_on_identity_first(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    _write_json(
        board_json,
        {
            "summary": {"execution_board_status": "awaiting_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "row_execution_status": "awaiting_identity",
                    "identity_status": "awaiting_identity",
                    "identity_blockers": "proposed_target_id_required",
                    "file_action_count": 12,
                    "file_waiting_on_identity_count": 12,
                    "value_action_count": 18,
                    "value_waiting_on_identity_count": 18,
                    "next_action": "fill identity",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, board_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["readiness_gate_status"] == "awaiting_identity"
    assert payload["summary"]["first_blocked_gate_id"] == "identity_gate"
    by_gate = {row["gate_id"]: row for row in payload["rows"]}
    assert by_gate["identity_gate"]["blocked_count"] == 1
    assert by_gate["file_source_gate"]["blocked_count"] == 12
    assert by_gate["value_entry_gate"]["blocked_count"] == 18
    assert _read_csv(tmp_path / "gate.csv")[0]["gate_id"] == "identity_gate"
    assert (tmp_path / "GATE.md").is_file()


def test_readiness_gate_promotes_identity_apply_before_sources(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    _write_json(
        board_json,
        {
            "summary": {"execution_board_status": "ready_for_identity_apply"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "row_execution_status": "ready_for_identity_apply",
                    "identity_status": "ready_for_import",
                    "file_action_count": 12,
                    "file_awaiting_source_path_count": 12,
                    "value_action_count": 18,
                    "value_ready_from_identity_kit_count": 2,
                    "value_awaiting_value_count": 16,
                    "next_action": "apply identity",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, board_json))

    payload = mod.build_payload(args)
    by_gate = {row["gate_id"]: row for row in payload["rows"]}

    assert payload["summary"]["readiness_gate_status"] == "ready_for_identity_apply"
    assert by_gate["identity_gate"]["gate_status"] == "pass"
    assert by_gate["identity_apply_gate"]["gate_status"] == "ready_for_identity_apply"


def test_readiness_gate_can_pass_all_stages(tmp_path: Path) -> None:
    board_json = tmp_path / "board.json"
    _write_json(
        board_json,
        {
            "summary": {"execution_board_status": "ready_for_evidence_import"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "row_execution_status": "ready_for_evidence_import",
                    "identity_status": "ready_for_import",
                    "file_action_count": 2,
                    "file_ready_for_import_count": 2,
                    "value_action_count": 3,
                    "value_ready_for_import_count": 3,
                    "next_action": "apply evidence import",
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, board_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["readiness_gate_status"] == "ready_for_competitive_floor"
    assert payload["summary"]["pass_count"] == payload["summary"]["gate_count"]
    assert payload["rows"][-1]["gate_id"] == "competitive_floor_gate"
    assert payload["rows"][-1]["gate_status"] == "ready_for_competitive_floor"
