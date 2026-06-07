import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board as mod


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


def test_value_action_board_expands_current_gate_to_36_actions(tmp_path: Path) -> None:
    target_ids = ["H1319", "H1321", "H2324"]
    gate_json = tmp_path / "value_gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "batch_native_provenance_value_gate_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
                ),
                "batch_operator_fill_intake_csv": str(tmp_path / "operator_fill_intake_batch.csv"),
                "target_count": 3,
            },
            "rows": [_gate_row(target_id) for target_id in target_ids],
        },
    )
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "action_board"),
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

    summary = payload["summary"]
    assert summary["batch_native_provenance_value_action_board_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_open_actions"
    )
    assert summary["target_count"] == 3
    assert summary["target_with_open_action_count"] == 3
    assert summary["target_ready_count"] == 0
    assert summary["action_count"] == 36
    assert summary["open_action_count"] == 36
    assert summary["native_action_count"] == 3
    assert summary["evidence_action_count"] == 3
    assert summary["clearance_action_count"] == 6
    assert summary["operator_action_count"] == 3
    assert summary["date_action_count"] == 6
    assert summary["boolean_action_count"] == 15
    assert summary["review_action_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["first_open_target_id"] == "H1319"
    assert summary["first_open_field"] == "native_source_pdb"
    assert summary["first_open_blocker"] == "native_source_pdb_required"
    assert payload["rows"][0]["field_group"] == "native_file"
    assert payload["rows"][1]["field_group"] == "evidence"
    for target_id in target_ids:
        folders = [
            path for path in (tmp_path / "action_board").iterdir() if path.is_dir() and path.name.startswith(target_id)
        ]
        assert len(folders) == 1
        assert (folders[0] / "value_actions.csv").is_file()
        assert (folders[0] / "README.md").is_file()
    assert (tmp_path / "action_board" / "manifest.json").is_file()
    assert not list((tmp_path / "action_board").rglob("*.pdb"))
    assert not list((tmp_path / "action_board").rglob("*.cif"))
    assert ("AUTHOR" + " ") not in (tmp_path / "board.json").read_text(encoding="utf-8")


def test_value_action_board_ready_when_gate_has_no_blockers(tmp_path: Path) -> None:
    gate_json = tmp_path / "value_gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "batch_native_provenance_value_gate_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_gate_ready_for_operator_intake_apply"
                ),
                "batch_operator_fill_intake_csv": str(tmp_path / "operator_fill_intake_batch.csv"),
                "target_count": 1,
            },
            "rows": [
                {
                    "target_id": "H1319",
                    "target_name": "ready target",
                    "gate_status": "ready_for_operator_intake_apply",
                    "blockers": "",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "action_board"),
            "--out-json",
            str(tmp_path / "board.json"),
            "--out-csv",
            str(tmp_path / "board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_native_provenance_value_action_board_status"] == (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_ready_no_open_actions"
    )
    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["target_with_open_action_count"] == 0
    assert payload["summary"]["target_ready_count"] == 1
    assert payload["summary"]["action_count"] == 0
    assert payload["rows"] == []
