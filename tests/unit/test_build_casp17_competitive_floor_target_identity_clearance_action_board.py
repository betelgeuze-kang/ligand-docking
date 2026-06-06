import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_action_board as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path, audit_json: Path) -> list[str]:
    return [
        "--audit-json",
        str(audit_json),
        "--out-json",
        str(tmp_path / "action_board.json"),
        "--out-csv",
        str(tmp_path / "action_board.csv"),
        "--out-md",
        str(tmp_path / "ACTION_BOARD.md"),
    ]


def test_clearance_action_board_expands_audit_blockers(tmp_path: Path) -> None:
    audit_json = tmp_path / "audit.json"
    _write_json(
        audit_json,
        {
            "summary": {
                "clearance_workorder_audit_status": "blocked",
                "audit_target_count": 1,
            },
            "rows": [
                {
                    "target_id": "H1001",
                    "audit_status": "blocked",
                    "native_dropzone_pdb": "casp17/workorders/H1001/native/H1001_native.pdb",
                    "provenance_template_csv": "casp17/workorders/H1001/provenance_template.csv",
                    "manifest_stub_csv": "casp17/workorders/H1001/manifest_stub.csv",
                    "native_file_status": "missing",
                    "blockers": (
                        "native_pdb_missing,"
                        "identity_discovery_no_leak_clearance_required,"
                        "evidence_ref_required,"
                        "operator_required,"
                        "leakage_clearance_required,"
                        "operator_clearance_required,"
                        "prediction_created_at_required_iso_date,"
                        "native_release_date_required_iso_date,"
                        "prediction_generated_before_native_release_required,"
                        "public_template_or_native_used_for_prediction_must_be_false,"
                        "current_casp17_target_must_be_false,"
                        "manifest_native_pdb_not_found,"
                        "manifest_operator_clearance_required,"
                        "manifest_waiting_on_provenance_template"
                    ),
                }
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, audit_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    lanes = {row["lane"]: row for row in payload["rows"]}
    assert payload["summary"]["action_board_status"] == "open_actions"
    assert payload["summary"]["action_count"] == 4
    assert payload["summary"]["native_action_count"] == 1
    assert payload["summary"]["evidence_action_count"] == 1
    assert payload["summary"]["provenance_action_count"] == 1
    assert payload["summary"]["manifest_action_count"] == 1
    assert payload["summary"]["first_open_target_id"] == "H1001"
    assert payload["summary"]["first_open_lane"] == "native_dropzone"
    assert "native_pdb_missing" in lanes["native_dropzone"]["blockers"]
    assert "identity_discovery_no_leak_clearance_required" in lanes["no_leak_evidence"]["blockers"]
    assert "operator_clearance_required" in lanes["provenance_fields"]["blockers"]
    assert "manifest_operator_clearance_required" in lanes["manifest_stub_sync"]["blockers"]
    assert (tmp_path / "action_board.csv").is_file()
    assert (tmp_path / "ACTION_BOARD.md").is_file()


def test_clearance_action_board_ready_when_audit_passes(tmp_path: Path) -> None:
    audit_json = tmp_path / "audit.json"
    _write_json(
        audit_json,
        {
            "summary": {
                "clearance_workorder_audit_status": "pass",
                "audit_target_count": 1,
            },
            "rows": [{"target_id": "H1001", "audit_status": "pass", "blockers": ""}],
        },
    )
    args = mod.parse_args(_args(tmp_path, audit_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["action_board_status"] == "ready"
    assert payload["summary"]["action_count"] == 0
    assert payload["rows"] == []
