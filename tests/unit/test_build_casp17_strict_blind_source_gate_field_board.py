import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_source_gate_field_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _gate_payload() -> dict:
    rows = [
        {"check_id": "manifest_exists", "check_status": "pass", "actual_value": "manifest.csv"},
        {"check_id": "source_id_internal", "check_status": "blocked", "actual_value": "", "blocker": "internal_source_id_missing_or_external", "next_action": "set source_id"},
        {"check_id": "target_id_present", "check_status": "pass", "actual_value": "REQUIRED_MONOMER_001"},
        {"check_id": "scope_matches", "check_status": "pass", "actual_value": "monomer"},
        {"check_id": "manifest_prediction_pdb_present", "check_status": "blocked", "actual_value": "", "blocker": "prediction_pdb_missing", "next_action": "point prediction_pdb"},
        {"check_id": "manifest_prediction_pdb_exists", "check_status": "blocked", "actual_value": "", "blocker": "prediction_pdb_not_found", "next_action": "place prediction PDB"},
        {"check_id": "dropzone_prediction_pdb_exists", "check_status": "blocked", "actual_value": "dropzone/replacement_prediction.pdb", "blocker": "dropzone_prediction_pdb_missing", "next_action": "copy prediction PDB"},
        {"check_id": "prediction_pdb_has_atom_records", "check_status": "blocked", "actual_value": "", "blocker": "prediction_pdb_has_no_atom_records", "next_action": "provide atom records"},
        {"check_id": "prediction_created_at_present", "check_status": "blocked", "actual_value": "", "blocker": "prediction_created_at_missing_or_invalid", "next_action": "enter prediction date"},
        {"check_id": "native_release_date_present", "check_status": "blocked", "actual_value": "", "blocker": "native_release_date_missing_or_invalid", "next_action": "enter native release date"},
        {"check_id": "prediction_before_native", "check_status": "blocked", "actual_value": "/", "blocker": "prediction_not_before_native", "next_action": "verify prediction before native"},
        {"check_id": "native_authority_ref_present", "check_status": "blocked", "actual_value": "", "blocker": "native_authority_ref_missing", "next_action": "attach native authority"},
        {"check_id": "creation_evidence_ref_present", "check_status": "blocked", "actual_value": "", "blocker": "creation_evidence_ref_missing", "next_action": "attach timestamp evidence"},
        {"check_id": "no_leak_evidence_ref_present", "check_status": "blocked", "actual_value": "", "blocker": "no_leak_evidence_ref_missing", "next_action": "attach no-leak evidence"},
        {"check_id": "method_summary_present", "check_status": "blocked", "actual_value": "", "blocker": "method_summary_missing", "next_action": "summarize method"},
        {"check_id": "operator_clearance_present", "check_status": "blocked", "actual_value": "", "blocker": "operator_clearance_missing", "next_action": "set operator clearance"},
    ]
    return {
        "summary": {
            "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
            "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
            "required_target_id": "REQUIRED_MONOMER_001",
            "required_scope": "monomer",
            "manifest_csv": "casp17/manifest.csv",
            "prediction_dropzone": "dropzone/replacement_prediction.pdb",
            "pass_count": 3,
            "blocked_count": 13,
        },
        "rows": rows,
    }


def test_source_gate_field_board_groups_blocked_checks_by_unique_fill_action(tmp_path):
    gate = tmp_path / "gate.json"
    _write_json(gate, _gate_payload())

    args = mod.parse_args(
        [
            "--source-gate-json",
            str(gate),
            "--board-dir",
            str(tmp_path / "field_board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    rows = {row["field_key"]: row for row in payload["rows"]}
    summary = payload["summary"]
    assert summary["source_gate_field_board_status"] == "awaiting_source_gate_field_fills"
    assert summary["field_action_count"] == 11
    assert summary["manifest_value_action_count"] == 9
    assert summary["file_action_count"] == 2
    assert summary["blocked_check_covered_count"] == 13
    assert rows["prediction_pdb"]["blocked_check_count"] == 3
    assert rows["prediction_pdb_dropzone"]["destination"] == "dropzone/replacement_prediction.pdb"
    assert "manifest_prediction_pdb_exists" in rows["prediction_pdb"]["affected_check_ids"]
    assert (tmp_path / "field_board" / "hist_REQUIRED_MONOMER_001" / "source_gate_field_board.csv").is_file()


def test_source_gate_field_board_reports_clear_gate(tmp_path):
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "summary": {
                "internal_prediction_source_gate_status": "internal_prediction_source_ready_for_first_slot_dropzone",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "pass_count": 16,
                "blocked_count": 0,
            },
            "rows": [{"check_id": "source_id_internal", "check_status": "pass", "actual_value": "internal_run"}],
        },
    )

    args = mod.parse_args(["--source-gate-json", str(gate), "--out-json", str(tmp_path / "board.json")])
    payload = mod.build_payload(args)

    assert payload["summary"]["source_gate_field_board_status"] == "source_gate_field_board_clear"
    assert payload["summary"]["field_action_count"] == 0
    assert payload["rows"] == []


def test_source_gate_field_board_blocks_missing_gate_json(tmp_path):
    args = mod.parse_args(["--source-gate-json", str(tmp_path / "missing_gate.json")])
    payload = mod.build_payload(args)

    assert payload["summary"]["source_gate_field_board_status"] == "blocked_missing_inputs"
    assert "source_gate_json_missing" in payload["summary"]["input_blockers"]
