import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_operator_fill_preflight as mod
from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board as board
from tools import build_casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit as audit
from tools import build_casp17_competitive_floor_batch_native_provenance_value_gate as gate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_intake(path: Path, target_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mod.INTAKE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for target_id in target_ids:
            writer.writerow(
                {
                    "target_id": target_id,
                    "native_source_pdb": "REQUIRED_OPERATOR_NATIVE_PDB_SOURCE_PATH",
                    "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_FILE",
                    "leakage_clearance": "REQUIRED_NO_LEAK_CLEARANCE",
                    "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                    "operator": "REQUIRED_OPERATOR_ID",
                    "prediction_created_at": "YYYY-MM-DD",
                    "native_release_date": "YYYY-MM-DD",
                    "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                    "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                    "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                    "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                    "current_casp17_target": "REQUIRED_FALSE_CONFIRMATION",
                    "notes": "Do not mark cleared until native and no-leak provenance are operator-reviewed.",
                }
            )


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


def _materialize_inputs(tmp_path: Path, target_ids: list[str]) -> tuple[Path, Path, Path]:
    intake_csv = tmp_path / "operator_fill_intake_batch.csv"
    _write_intake(intake_csv, target_ids)
    gate_json = tmp_path / "value_gate.json"
    _write_json(
        gate_json,
        {
            "summary": {
                "batch_native_provenance_value_gate_status": (
                    "casp17_competitive_floor_batch_native_provenance_value_gate_blocked_awaiting_operator_values"
                ),
                "batch_operator_fill_intake_csv": str(intake_csv),
                "target_count": len(target_ids),
            },
            "rows": [_gate_row(target_id) for target_id in target_ids],
        },
    )
    board_json = tmp_path / "action_board.json"
    board_args = board.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--out-dir",
            str(tmp_path / "action_board"),
            "--out-json",
            str(board_json),
            "--out-csv",
            str(tmp_path / "action_board.csv"),
            "--out-md",
            str(tmp_path / "BOARD.md"),
        ]
    )
    board_payload = board.build_payload(board_args)
    board.write_outputs(board_args, board_payload)
    audit_json = tmp_path / "action_board_audit.json"
    audit_args = audit.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(board_json),
            "--out-json",
            str(audit_json),
            "--out-csv",
            str(tmp_path / "action_board_audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    audit_payload = audit.build_payload(audit_args)
    audit.write_outputs(audit_args, audit_payload)
    return gate_json, board_json, audit_json


def test_operator_fill_preflight_materializes_target_templates(tmp_path: Path) -> None:
    gate_json, board_json, audit_json = _materialize_inputs(tmp_path, ["H1319", "H1321", "H2324"])
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(board_json),
            "--action-board-completion-audit-json",
            str(audit_json),
            "--out-dir",
            str(tmp_path / "preflight"),
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "PREFLIGHT.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["batch_native_provenance_operator_fill_preflight_status"] == (
        "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_ready_for_operator_fill"
    )
    assert summary["target_count"] == 3
    assert summary["target_ready_for_fill_count"] == 3
    assert summary["target_blocked_count"] == 0
    assert summary["open_action_count"] == 36
    assert summary["native_action_count"] == 3
    assert summary["evidence_action_count"] == 3
    assert summary["clearance_action_count"] == 6
    assert summary["operator_action_count"] == 3
    assert summary["date_action_count"] == 6
    assert summary["boolean_action_count"] == 15
    assert summary["review_action_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["first_ready_target_id"] == "H1319"
    for row in payload["rows"]:
        folder = Path(row["target_preflight_folder"])
        assert (folder / "README.md").is_file()
        assert (folder / "operator_fill_template.csv").is_file()
        assert (folder / "field_policy.csv").is_file()
    assert (tmp_path / "preflight" / "manifest.json").is_file()
    assert not list((tmp_path / "preflight").rglob("*.pdb"))
    assert not list((tmp_path / "preflight").rglob("*.cif"))
    assert ("AUTHOR" + " ") not in (tmp_path / "preflight.json").read_text(encoding="utf-8")


def test_operator_fill_preflight_blocks_when_action_board_audit_not_pass(tmp_path: Path) -> None:
    gate_json, board_json, audit_json = _materialize_inputs(tmp_path, ["H1319"])
    audit_payload = json.loads(audit_json.read_text(encoding="utf-8"))
    audit_payload["summary"]["batch_native_provenance_value_action_board_completion_audit_status"] = (
        "casp17_competitive_floor_batch_native_provenance_value_action_board_completion_audit_blocked"
    )
    _write_json(audit_json, audit_payload)
    args = mod.parse_args(
        [
            "--value-gate-json",
            str(gate_json),
            "--action-board-json",
            str(board_json),
            "--action-board-completion-audit-json",
            str(audit_json),
            "--out-dir",
            str(tmp_path / "preflight"),
            "--out-json",
            str(tmp_path / "preflight.json"),
            "--out-csv",
            str(tmp_path / "preflight.csv"),
            "--out-md",
            str(tmp_path / "PREFLIGHT.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_native_provenance_operator_fill_preflight_status"] == (
        "casp17_competitive_floor_batch_native_provenance_operator_fill_preflight_blocked"
    )
    assert payload["summary"]["target_ready_for_fill_count"] == 0
    assert payload["summary"]["target_blocked_count"] == 1
    assert "value_action_board_completion_audit_not_pass" in payload["rows"][0]["blockers"]
