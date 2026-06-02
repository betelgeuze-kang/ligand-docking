import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_unlock_kit as batch
from tools import build_casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _bridge_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} immune complex",
        "bridge_status": "blocked_awaiting_native_provenance_values",
        "packet_audit_status": "pass",
        "workorder_audit_status": "blocked",
        "metric_runway_status": "blocked_awaiting_native_provenance",
        "metric_requirement_count": 9,
        "prediction_present": 1,
        "ts_prediction_present": 1,
        "native_dropzone_path_present": 1,
        "native_file_present": 0,
        "provenance_template_present": 1,
        "manifest_stub_present": 1,
        "metric_runway_present": 1,
        "workorder_present": 1,
        "packet_action_count": 4,
        "provenance_status": "blocked",
        "evidence_ref_status": "missing",
        "identity_discovery_status": "blocked",
        "manifest_stub_status": "blocked",
        "packet_folder": f"packet/{target_id}",
        "metric_runway_md": f"runway/{target_id}/METRIC_RUNWAY.md",
        "native_dropzone_pdb": f"workorders/{target_id}/native/{target_id}_native.pdb",
        "provenance_template_csv": f"workorders/{target_id}/provenance_template.csv",
        "manifest_stub_csv": f"workorders/{target_id}/manifest_stub.csv",
        "first_blocker": "native_pdb_missing",
        "blockers": "native_pdb_missing,evidence_ref_required,operator_clearance_required",
        "next_action": "place operator-cleared native PDB in the native dropzone",
        "competitive_proof_eligible": "false",
        "author_serialized": "false",
    }


def _packet_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} immune complex",
        "packet_folder": f"packet/{target_id}",
        "actions_csv": f"packet/{target_id}/actions.csv",
        "native_candidates_csv": f"packet/{target_id}/native_candidates.csv",
        "prediction_pdb": f"predictions/{target_id}_model_1.pdb",
        "ts_prediction_pdb": f"predictions/{target_id}TS.pdb",
        "native_dropzone_pdb": f"workorders/{target_id}/native/{target_id}_native.pdb",
        "provenance_template_csv": f"workorders/{target_id}/provenance_template.csv",
        "manifest_stub_csv": f"workorders/{target_id}/manifest_stub.csv",
        "metric_runway_md": f"runway/{target_id}/METRIC_RUNWAY.md",
        "action_count": 4,
        "native_action_count": 1,
        "evidence_action_count": 1,
        "provenance_action_count": 1,
        "manifest_action_count": 1,
    }


def _packet_audit_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} immune complex",
        "audit_status": "pass",
        "operator_packet_status": "open_actions",
        "packet_folder": f"packet/{target_id}",
        "actions_csv": f"packet/{target_id}/actions.csv",
        "native_candidates_csv": f"packet/{target_id}/native_candidates.csv",
        "action_csv_row_count": 4,
        "native_action_csv_count": 1,
        "evidence_action_csv_count": 1,
        "provenance_action_csv_count": 1,
        "manifest_action_csv_count": 1,
        "prediction_present": 1,
        "ts_prediction_present": 1,
        "native_dropzone_path_present": 1,
        "native_file_present": 0,
        "provenance_template_present": 1,
        "manifest_stub_present": 1,
        "metric_runway_present": 1,
        "workorder_folder_present": 1,
        "blockers": "",
    }


def _workorder_audit_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "audit_status": "blocked",
        "provenance_status": "blocked",
        "evidence_ref_status": "missing",
        "identity_discovery_blocker_status": "blocked",
        "manifest_stub_status": "blocked",
        "native_prediction_identity_status": "waiting_on_native",
        "blockers": "native_pdb_missing,evidence_ref_required,operator_clearance_required",
    }


def _action_row(target_id: str, rank: int, lane: str, field: str) -> dict:
    return {
        "target_id": target_id,
        "action_rank": rank,
        "lane": lane,
        "required_field": field,
        "required_artifact": f"workorders/{target_id}/{field}",
        "action_status": "open",
        "blockers": f"{field}_required",
        "recommended_action": f"Fill {field}.",
        "unlocks": f"{field}_ready",
        "verification_command": "python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py",
        "action_md": f"bundle/{target_id}/action_{rank:03d}/ACTION.md",
        "request_md": f"bundle/{target_id}/action_{rank:03d}/request.md",
    }


def _materialize_batch(tmp_path: Path, target_ids: list[str]) -> Path:
    bridge_json = tmp_path / "bridge.json"
    packet_json = tmp_path / "packet.json"
    packet_audit_json = tmp_path / "packet_audit.json"
    workorder_audit_json = tmp_path / "workorder_audit.json"
    action_bundle_json = tmp_path / "action_bundle.json"
    actions = []
    for target_id in target_ids:
        actions.extend(
            [
                _action_row(target_id, 1, "native_dropzone", "native_pdb"),
                _action_row(target_id, 2, "no_leak_evidence", "evidence_ref"),
                _action_row(target_id, 3, "provenance_fields", "provenance_template_required_fields"),
                _action_row(target_id, 4, "manifest_stub_sync", "manifest_stub_fields"),
            ]
        )
    _write_json(bridge_json, {"rows": [_bridge_row(target_id) for target_id in target_ids]})
    _write_json(packet_json, {"rows": [_packet_row(target_id) for target_id in target_ids]})
    _write_json(packet_audit_json, {"rows": [_packet_audit_row(target_id) for target_id in target_ids]})
    _write_json(workorder_audit_json, {"rows": [_workorder_audit_row(target_id) for target_id in target_ids]})
    _write_json(action_bundle_json, {"rows": actions})
    batch_json = tmp_path / "batch.json"
    args = batch.parse_args(
        [
            "--bridge-json",
            str(bridge_json),
            "--operator-packet-json",
            str(packet_json),
            "--operator-packet-completion-audit-json",
            str(packet_audit_json),
            "--workorder-audit-json",
            str(workorder_audit_json),
            "--action-bundle-json",
            str(action_bundle_json),
            "--out-dir",
            str(tmp_path / "batch"),
            "--out-json",
            str(batch_json),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "BATCH.md"),
        ]
    )
    payload = batch.build_payload(args)
    batch.write_outputs(args, payload)
    return batch_json


def test_batch_native_provenance_unlock_kit_completion_audit_passes_complete_kit(tmp_path: Path) -> None:
    batch_json = _materialize_batch(tmp_path, ["H1319", "H1321"])
    args = mod.parse_args(
        [
            "--batch-kit-json",
            str(batch_json),
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
    assert summary["batch_unlock_kit_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_pass"
    )
    assert summary["target_count"] == 2
    assert summary["target_pass_count"] == 2
    assert summary["target_blocked_count"] == 0
    assert summary["batch_file_present_count"] == 6
    assert summary["batch_operator_fill_intake_expected_rows"] == 2
    assert summary["batch_operator_fill_intake_csv_rows"] == 2
    assert summary["batch_required_actions_expected_rows"] == 8
    assert summary["batch_required_actions_csv_rows"] == 8
    assert summary["target_folder_present_count"] == 2
    assert summary["target_readme_present_count"] == 2
    assert summary["target_manifest_present_count"] == 2
    assert summary["target_operator_fill_intake_present_count"] == 2
    assert summary["target_required_actions_present_count"] == 2
    assert summary["target_rerun_commands_present_count"] == 2
    assert summary["target_operator_fill_intake_expected_rows"] == 2
    assert summary["target_operator_fill_intake_csv_rows"] == 2
    assert summary["target_required_actions_expected_rows"] == 8
    assert summary["target_required_actions_csv_rows"] == 8
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_coordinate_copy_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["native_file_present_count"] == 0
    assert summary["provenance_ready_count"] == 0
    assert summary["evidence_ref_verified_count"] == 0
    assert summary["identity_discovery_cleared_count"] == 0
    assert ("AUTHOR" + " ") not in (tmp_path / "audit.json").read_text(encoding="utf-8")


def test_batch_native_provenance_unlock_kit_completion_audit_blocks_missing_target_actions(
    tmp_path: Path,
) -> None:
    batch_json = _materialize_batch(tmp_path, ["H1319", "H1321"])
    batch_payload = json.loads(batch_json.read_text(encoding="utf-8"))
    target_folder = Path(batch_payload["rows"][1]["kit_folder"])
    (target_folder / "required_actions.csv").unlink()
    args = mod.parse_args(
        [
            "--batch-kit-json",
            str(batch_json),
            "--out-json",
            str(tmp_path / "audit.json"),
            "--out-csv",
            str(tmp_path / "audit.csv"),
            "--out-md",
            str(tmp_path / "AUDIT.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["batch_unlock_kit_completion_audit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_completion_audit_blocked"
    )
    assert payload["summary"]["target_pass_count"] == 1
    assert payload["summary"]["target_blocked_count"] == 1
    blocked = [row for row in payload["rows"] if row["audit_status"] == "blocked"][0]
    assert blocked["target_id"] == "H1321"
    assert "target_required_actions_missing" in blocked["blockers"]
    assert "target_required_actions_row_mismatch" in blocked["blockers"]
