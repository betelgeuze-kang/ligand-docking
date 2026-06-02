import json
from pathlib import Path

from tools import build_casp17_competitive_floor_native_provenance_metric_unlock_bridge as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metric_row(target_id: str, ready: bool) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "runway_status": "ready_for_metric_after_native_provenance" if ready else "blocked_awaiting_native_provenance",
        "metric_requirement_count": 9,
        "required_metric_names": "GDT_TS|lDDT|TM-score|RMSD|GDT_HA|MolProbity|DockQ|ICS|IPS",
        "native_status": "present" if ready else "missing",
        "provenance_status": "ready" if ready else "blocked",
        "evidence_ref_status": "verified" if ready else "missing",
        "identity_discovery_status": "cleared" if ready else "blocked",
        "operator_clearance_status": "" if ready else "required",
        "native_candidate_count": 1,
        "native_candidate_blocked_count": 0 if ready else 1,
        "native_candidate_no_candidate_count": 0,
        "metric_runway_md": f"runway/{target_id}/METRIC_RUNWAY.md",
        "native_dropzone_pdb": f"workorders/{target_id}/native/{target_id}.pdb",
        "provenance_template_csv": f"workorders/{target_id}/provenance_template.csv",
        "manifest_stub_csv": f"workorders/{target_id}/manifest_stub.csv",
        "blockers": "" if ready else "native_pdb_missing,evidence_ref_required,operator_clearance_required",
    }


def _packet_audit_row(target_id: str, native_file: bool = False) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "audit_status": "pass",
        "operator_packet_status": "open_actions",
        "packet_folder": f"packet/{target_id}",
        "action_csv_row_count": 4,
        "native_action_csv_count": 1,
        "evidence_action_csv_count": 1,
        "provenance_action_csv_count": 1,
        "manifest_action_csv_count": 1,
        "prediction_present": 1,
        "ts_prediction_present": 1,
        "native_dropzone_path_present": 1,
        "native_file_present": 1 if native_file else 0,
        "provenance_template_present": 1,
        "manifest_stub_present": 1,
        "metric_runway_present": 1,
        "workorder_folder_present": 1,
        "metric_requirement_count": 9,
        "blockers": "",
    }


def _workorder_audit_row(target_id: str, ready: bool) -> dict:
    return {
        "target_id": target_id,
        "audit_status": "pass" if ready else "blocked",
        "provenance_status": "ready" if ready else "blocked",
        "evidence_ref_status": "verified" if ready else "missing",
        "identity_discovery_blocker_status": "cleared" if ready else "blocked",
        "manifest_stub_status": "ready" if ready else "blocked",
        "native_prediction_identity_status": "distinct" if ready else "waiting_on_native",
        "blockers": ""
        if ready
        else (
            "native_pdb_missing,identity_discovery_no_leak_clearance_required,"
            "evidence_ref_required,operator_clearance_required"
        ),
    }


def _operator_packet_row(target_id: str) -> dict:
    return {
        "target_id": target_id,
        "target_name": f"{target_id} complex",
        "packet_folder": f"packet/{target_id}",
        "action_count": 4,
        "native_action_count": 1,
        "evidence_action_count": 1,
        "provenance_action_count": 1,
        "manifest_action_count": 1,
        "native_candidate_count": 1,
        "native_candidate_blocked_count": 1,
        "native_candidate_no_candidate_count": 0,
    }


def test_metric_unlock_bridge_marks_ready_and_blocked_targets(tmp_path: Path) -> None:
    metric_json = tmp_path / "metric.json"
    packet_audit_json = tmp_path / "packet_audit.json"
    workorder_audit_json = tmp_path / "workorder_audit.json"
    packet_json = tmp_path / "packet.json"
    _write_json(
        metric_json,
        {"summary": {"metric_runway_status": "mixed"}, "rows": [_metric_row("H1319", False), _metric_row("H2324", True)]},
    )
    _write_json(
        packet_audit_json,
        {
            "summary": {
                "operator_packet_completion_audit_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_pass"
                )
            },
            "rows": [_packet_audit_row("H1319", False), _packet_audit_row("H2324", True)],
        },
    )
    _write_json(
        workorder_audit_json,
        {"summary": {"clearance_workorder_audit_status": "blocked"}, "rows": [_workorder_audit_row("H1319", False), _workorder_audit_row("H2324", True)]},
    )
    _write_json(packet_json, {"rows": [_operator_packet_row("H1319"), _operator_packet_row("H2324")]})
    args = mod.parse_args(
        [
            "--metric-runway-json",
            str(metric_json),
            "--operator-packet-completion-audit-json",
            str(packet_audit_json),
            "--workorder-audit-json",
            str(workorder_audit_json),
            "--operator-packet-json",
            str(packet_json),
            "--out-json",
            str(tmp_path / "bridge.json"),
            "--out-csv",
            str(tmp_path / "bridge.csv"),
            "--out-md",
            str(tmp_path / "BRIDGE.md"),
            "--out-html",
            str(tmp_path / "bridge.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["metric_unlock_bridge_status"] == (
        "casp17_competitive_floor_native_provenance_metric_unlock_bridge_blocked_awaiting_operator_values"
    )
    assert summary["target_count"] == 2
    assert summary["target_ready_count"] == 1
    assert summary["target_blocked_count"] == 1
    assert summary["packet_pass_count"] == 2
    assert summary["workorder_audit_pass_count"] == 1
    assert summary["metric_runway_ready_count"] == 1
    assert summary["metric_requirement_count"] == 18
    assert summary["native_file_present_count"] == 1
    assert summary["provenance_ready_count"] == 1
    assert summary["evidence_ref_verified_count"] == 1
    assert summary["identity_discovery_cleared_count"] == 1
    assert rows["H1319"]["bridge_status"] == "blocked_awaiting_native_provenance_values"
    assert rows["H1319"]["next_action"] == "place operator-cleared native PDB in the native dropzone"
    assert "native_pdb_missing" in rows["H1319"]["blockers"]
    assert rows["H2324"]["bridge_status"] == "ready_for_metric_execution"
    assert (tmp_path / "BRIDGE.md").is_file()
    assert ("AUTHOR" + " ") not in (tmp_path / "bridge.json").read_text(encoding="utf-8")


def test_metric_unlock_bridge_blocks_when_packet_completion_audit_missing(
    tmp_path: Path,
) -> None:
    metric_json = tmp_path / "metric.json"
    packet_audit_json = tmp_path / "packet_audit.json"
    workorder_audit_json = tmp_path / "workorder_audit.json"
    packet_json = tmp_path / "packet.json"
    _write_json(metric_json, {"rows": [_metric_row("T9999", True)]})
    _write_json(
        packet_audit_json,
        {
            "summary": {
                "operator_packet_completion_audit_status": (
                    "casp17_competitive_floor_native_provenance_operator_packet_completion_audit_blocked"
                )
            },
            "rows": [{**_packet_audit_row("T9999", True), "audit_status": "blocked", "blockers": "actions_csv_missing"}],
        },
    )
    _write_json(workorder_audit_json, {"rows": [_workorder_audit_row("T9999", True)]})
    _write_json(packet_json, {"rows": [_operator_packet_row("T9999")]})
    args = mod.parse_args(
        [
            "--metric-runway-json",
            str(metric_json),
            "--operator-packet-completion-audit-json",
            str(packet_audit_json),
            "--workorder-audit-json",
            str(workorder_audit_json),
            "--operator-packet-json",
            str(packet_json),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["target_blocked_count"] == 1
    blockers = payload["rows"][0]["blockers"]
    assert "packet_completion_audit_not_pass" in blockers
    assert "packet_actions_csv_missing" in blockers
