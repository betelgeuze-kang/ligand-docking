import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_target_identity_clearance_action_bundle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _args(tmp_path: Path, action_board_json: Path) -> list[str]:
    return [
        "--action-board-json",
        str(action_board_json),
        "--out-dir",
        str(tmp_path / "action_bundle"),
        "--out-json",
        str(tmp_path / "action_bundle.json"),
        "--out-csv",
        str(tmp_path / "action_bundle.csv"),
        "--out-md",
        str(tmp_path / "ACTION_BUNDLE.md"),
    ]


def _action(rank: int, lane: str, artifact: str, blockers: str) -> dict:
    return {
        "action_rank": rank,
        "target_id": "H1001",
        "lane": lane,
        "action_status": "open",
        "source_audit_status": "blocked",
        "required_artifact": artifact,
        "required_field": lane,
        "blocker_count": 1,
        "blockers": blockers,
        "recommended_action": f"complete {lane}",
        "unlocks": f"{lane}_unlocked",
        "verification_command": "python3 tools/run_casp17_competitive_floor_target_identity_clearance_cycle.py",
    }


def test_action_bundle_materializes_per_target_requests(tmp_path: Path) -> None:
    action_board_json = tmp_path / "action_board.json"
    workorder = "casp17/competitive_floor_target_identity_clearance_workorders/H1001_Example_protein"
    _write_json(
        action_board_json,
        {
            "summary": {"action_board_status": "open_actions", "action_count": 4, "open_action_count": 4},
            "rows": [
                _action(1, "native_dropzone", f"{workorder}/native/H1001_native.pdb", "native_pdb_missing"),
                _action(2, "no_leak_evidence", f"{workorder}/provenance_template.csv", "evidence_ref_required"),
                _action(3, "provenance_fields", f"{workorder}/provenance_template.csv", "operator_required"),
                _action(4, "manifest_stub_sync", f"{workorder}/manifest_stub.csv", "manifest_operator_clearance_required"),
            ],
        },
    )
    args = mod.parse_args(_args(tmp_path, action_board_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["action_bundle_status"] == "open_actions"
    assert summary["target_count"] == 1
    assert summary["action_count"] == 4
    assert summary["open_action_count"] == 4
    assert summary["target_folder_count"] == 1
    assert summary["action_folder_count"] == 4
    assert summary["bundle_file_count"] == 8
    assert summary["native_action_count"] == 1
    assert summary["evidence_action_count"] == 1
    assert summary["provenance_action_count"] == 1
    assert summary["manifest_action_count"] == 1
    assert summary["first_open_action_md"].endswith("action_001_native_dropzone/ACTION.md")

    by_lane = {row["lane"]: row for row in payload["rows"]}
    evidence_request = Path(by_lane["no_leak_evidence"]["request_md"])
    if not evidence_request.is_absolute():
        evidence_request = mod.ROOT / evidence_request
    assert evidence_request.name == "evidence_request.md"
    assert "CLEARANCE_EVIDENCE_STATUS: request_template" in evidence_request.read_text(encoding="utf-8")
    assert "not a completed no-leak clearance" in evidence_request.read_text(encoding="utf-8")
    assert (tmp_path / "action_bundle.csv").is_file()
    assert (tmp_path / "ACTION_BUNDLE.md").is_file()


def test_action_bundle_ready_when_action_board_has_no_rows(tmp_path: Path) -> None:
    action_board_json = tmp_path / "action_board.json"
    _write_json(action_board_json, {"summary": {"action_board_status": "ready"}, "rows": []})
    args = mod.parse_args(_args(tmp_path, action_board_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["action_bundle_status"] == "ready"
    assert payload["summary"]["action_count"] == 0
    assert payload["summary"]["bundle_file_count"] == 0
    assert payload["rows"] == []
