import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board as board
from tools.casp17 import build_casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _gate_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} immune complex",
        "gate_status": "blocked_awaiting_operator_values",
        "required_field_count": 13,
        "ready_value_count": 1,
        "blocked_value_count": 12,
        "native_source_pdb": "REQUIRED_OPERATOR_NATIVE_PDB_SOURCE_PATH",
        "native_source_status": "blocked",
        "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_FILE",
        "no_leak_evidence_ref_status": "blocked",
        "leakage_clearance_status": "blocked",
        "operator_clearance_status": "blocked",
        "operator_status": "blocked",
        "prediction_created_at_status": "blocked",
        "native_release_date_status": "blocked",
        "prediction_generated_before_native_release_status": "blocked",
        "public_template_or_native_used_for_prediction_status": "blocked",
        "other_team_model_used_status": "blocked",
        "post_release_information_used_status": "blocked",
        "current_casp17_target_status": "blocked",
        "notes_status": "ready",
        "coordinate_copy_count": 0,
        "blocker_count": 12,
        "blockers": (
            "native_source_pdb_required,no_leak_evidence_ref_required,leakage_clearance_required,"
            "operator_clearance_required,operator_required,prediction_created_at_required_iso_date,"
            "native_release_date_required_iso_date,prediction_generated_before_native_release_required,"
            "public_template_or_native_used_for_prediction_must_be_false,other_team_model_used_must_be_false,"
            "post_release_information_used_must_be_false,current_casp17_target_must_be_false"
        ),
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def _materialize_board(tmp_path: Path, target_ids: list[str]) -> tuple[Path, Path]:
    gate_json = tmp_path / "value_gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "batch_native_provenance_value_gate_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
                ),
                "batch_operator_fill_intake_csv": str(tmp_path / "operator_fill_intake_batch.csv"),
                "target_count": len(target_ids),
            },
            "rows": [_gate_row(target_id) for target_id in target_ids],
        },
    )
    action_board_json = tmp_path / "action_board.json"
    args = board.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "action_board"),
            "--out-json",
            str(action_board_json),
            "--out-csv",
            str(tmp_path / "action_board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )
    payload = board.build_payload(args)
    board.write_outputs(args, payload)
    return gate_json, action_board_json


def test_value_action_board_completion_audit_passes_complete_board(tmp_path: Path) -> None:
    gate_json, action_board_json = _materialize_board(tmp_path, ["H1319", "H1321", "H2324"])
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(action_board_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["batch_native_provenance_value_action_board_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_pass"
    )
    assert summary["target_count"] == 3
    assert summary["target_pass_count"] == 3
    assert summary["target_blocked_count"] == 0
    assert summary["action_expected_count"] == 36
    assert summary["action_board_json_rows"] == 36
    assert summary["action_json_row_mismatch_count"] == 0
    assert summary["target_folder_present_count"] == 3
    assert summary["target_readme_present_count"] == 3
    assert summary["target_value_actions_present_count"] == 3
    assert summary["target_value_actions_expected_rows"] == 36
    assert summary["target_value_actions_csv_rows"] == 36
    assert summary["target_value_actions_row_mismatch_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert ("AUTHOR" + " ") not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_value_action_board_completion_audit_blocks_missing_target_csv(tmp_path: Path) -> None:
    gate_json, action_board_json = _materialize_board(tmp_path, ["H1319", "H1321"])
    action_payload = json.loads(action_board_json.read_text(encoding="utf-8"))
    h1321_folder = Path(
        next(row["target_action_folder"] for row in action_payload["rows"] if row["target_id"] == "H1321")
    )
    (h1321_folder / "value_actions.csv").unlink()
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(action_board_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_native_provenance_value_action_board_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_blocked"
    )
    assert payload["summary"]["target_pass_count"] == 1
    assert payload["summary"]["target_blocked_count"] == 1
    blocked = [row for row in payload["rows"] if row["audit_status"] == "blocked"][0]
    assert blocked["target_id"] == "H1321"
    assert "target_value_actions_csv_missing" in blocked["blockers"]
    assert "target_value_actions_csv_row_mismatch" in blocked["blockers"]
