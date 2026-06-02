import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_batch_native_provenance_unlock_kit as mod


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
        "required_metric_names": "GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity|DockQ|ICS|IPS",
        "prediction_present": 1,
        "ts_prediction_present": 1,
        "native_dropzone_path_present": 1,
        "native_file_present": 0,
        "provenance_template_present": 1,
        "manifest_stub_present": 1,
        "metric_runway_present": 1,
        "workorder_present": 1,
        "packet_action_count": 4,
        "packet_native_action_count": 1,
        "packet_evidence_action_count": 1,
        "packet_provenance_action_count": 1,
        "packet_manifest_action_count": 1,
        "native_candidate_count": 2,
        "native_candidate_blocked_count": 2,
        "native_candidate_no_candidate_count": 0,
        "provenance_status": "blocked",
        "evidence_ref_status": "missing",
        "identity_discovery_status": "blocked",
        "operator_clearance_status": "required",
        "manifest_stub_status": "blocked",
        "native_prediction_identity_status": "waiting_on_native",
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
        "packet_coordinate_copy_count": 0,
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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_batch_native_provenance_unlock_kit_materializes_all_blocked_targets(tmp_path: Path) -> None:
    target_ids = ["H1319", "H1321", "H2324"]
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
    args = mod.parse_args(
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
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "BATCH.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    batch_folder = Path(summary["batch_folder"])
    assert summary["batch_unlock_kit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_ready_for_operator_fill"
    )
    assert summary["target_count"] == 3
    assert summary["target_ready_for_operator_fill_count"] == 3
    assert summary["target_blocked_count"] == 0
    assert summary["required_field_per_target_count"] == 13
    assert summary["required_field_total_count"] == 39
    assert summary["required_action_count"] == 12
    assert summary["action_bundle_action_count"] == 12
    assert summary["packet_file_pass_count"] == 3
    assert summary["metric_runway_ready_count"] == 0
    assert summary["workorder_audit_pass_count"] == 0
    assert summary["prediction_present_count"] == 3
    assert summary["ts_prediction_present_count"] == 3
    assert summary["native_dropzone_path_present_count"] == 3
    assert summary["native_file_present_count"] == 0
    assert summary["provenance_template_present_count"] == 3
    assert summary["manifest_stub_present_count"] == 3
    assert summary["metric_runway_present_count"] == 3
    assert summary["workorder_present_count"] == 3
    assert summary["provenance_ready_count"] == 0
    assert summary["evidence_ref_verified_count"] == 0
    assert summary["identity_discovery_cleared_count"] == 0
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert summary["coordinate_copy_count"] == 0
    assert summary["target_ids"] == "H1319,H1321,H2324"
    assert (batch_folder / "README.md").is_file()
    assert (batch_folder / "operator_fill_intake_batch.csv").is_file()
    assert (batch_folder / "required_actions_batch.csv").is_file()
    assert (batch_folder / "rerun_commands.md").is_file()
    assert (batch_folder / "batch_manifest.json").is_file()
    assert len(_read_csv(batch_folder / "operator_fill_intake_batch.csv")) == 3
    assert len(_read_csv(batch_folder / "required_actions_batch.csv")) == 12
    for target_id in target_ids:
        target_folders = [path for path in batch_folder.iterdir() if path.is_dir() and path.name.startswith(target_id)]
        assert len(target_folders) == 1
        assert (target_folders[0] / "operator_fill_intake.csv").is_file()
        assert (target_folders[0] / "required_actions.csv").is_file()
    assert not list(batch_folder.rglob("*.pdb"))
    assert not list(batch_folder.rglob("*.cif"))
    assert ("AUTHOR" + " ") not in (tmp_path / "batch.json").read_text(encoding="utf-8")
    assert ("AUTHOR" + " ") not in (batch_folder / "README.md").read_text(encoding="utf-8")


def test_batch_native_provenance_unlock_kit_blocks_without_targets(tmp_path: Path) -> None:
    bridge_json = tmp_path / "bridge.json"
    _write_json(
        bridge_json,
        {
            "rows": [
                {
                    "target_id": "H9999",
                    "target_name": "ready target",
                    "bridge_status": "ready_for_metric_execution",
                }
            ]
        },
    )
    args = mod.parse_args(
        [
            "--bridge-json",
            str(bridge_json),
            "--out-dir",
            str(tmp_path / "batch"),
            "--out-json",
            str(tmp_path / "batch.json"),
            "--out-csv",
            str(tmp_path / "batch.csv"),
            "--out-md",
            str(tmp_path / "BATCH.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["batch_unlock_kit_status"] == (
        "casp17_competitive_floor_batch_native_provenance_unlock_kit_blocked_no_blocked_targets"
    )
    assert payload["summary"]["target_count"] == 0
    assert payload["summary"]["first_blocker"] == "no_blocked_targets"
    assert payload["rows"] == []
    assert (tmp_path / "batch.json").is_file()
