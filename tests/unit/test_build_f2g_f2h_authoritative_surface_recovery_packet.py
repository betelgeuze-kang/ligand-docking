from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_f2g_f2h_authoritative_surface_recovery_packet as mod


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _blocked_preflight() -> dict[str, object]:
    return {
        "summary": {
            "status": "blocked_f2g_f2h_surface_preflight",
            "blocker_count": 8,
            "blockers": [
                "implementation_phase1_dir_missing",
                "real_mgt_input_surface_missing",
                "f2h_blocked_until_f2g_audit",
            ],
            "f2g_audit_ready": False,
            "f2h_continuation_allowed": False,
            "g1_promotion_allowed": False,
        },
        "rows": [
            {
                "check_id": "implementation_phase1_dir",
                "status": "fail",
                "observed": "missing",
                "blocker": "implementation_phase1_dir_missing",
            },
            {
                "check_id": "real_mgt_input_surface",
                "status": "fail",
                "observed": "none",
                "blocker": "real_mgt_input_surface_missing",
            },
            {
                "check_id": "f2h_continuation_prerequisites",
                "status": "fail",
                "observed": "none",
                "blocker": "f2h_blocked_until_f2g_audit",
            },
        ],
    }


def test_recovery_packet_documents_authoritative_restore_work_order(tmp_path: Path) -> None:
    preflight = tmp_path / ".betelgeuze/f2g_f2h_surface_preflight.local.json"
    _write_json(preflight, _blocked_preflight())

    payload = mod.build_f2g_f2h_authoritative_surface_recovery_packet(root=tmp_path)

    summary = payload["summary"]
    rows = {row["preflight_check_id"]: row for row in payload["rows"]}
    assert summary["status"] == "f2g_f2h_authoritative_surface_recovery_packet_ready"
    assert summary["recovery_required"] is True
    assert summary["placeholder_surface_creation_allowed"] is False
    assert summary["g1_promotion_allowed"] is False
    assert summary["external_state_mutated"] is False
    assert rows["real_mgt_input_surface"]["status"] == "fail"
    assert "real-MGT" in rows["real_mgt_input_surface"]["authoritative_source_hint"]
    assert "do_not_create_placeholder_json" in rows["real_mgt_input_surface"]["prohibited_actions"]


def test_recovery_packet_blocks_when_preflight_artifact_is_missing(tmp_path: Path) -> None:
    payload = mod.build_f2g_f2h_authoritative_surface_recovery_packet(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "blocked_f2g_f2h_authoritative_surface_recovery_packet"
    assert summary["preflight_artifact_present"] is False
    assert summary["preflight_blockers"] == ["f2g_f2h_surface_preflight_artifact_missing"]
    assert summary["execution_enabled"] is False


def test_recovery_packet_is_not_required_after_ready_preflight(tmp_path: Path) -> None:
    preflight = tmp_path / ".betelgeuze/f2g_f2h_surface_preflight.local.json"
    _write_json(
        preflight,
        {
            "summary": {
                "status": "f2g_f2h_surface_preflight_ready",
                "blocker_count": 0,
                "blockers": [],
                "f2g_audit_ready": True,
                "f2h_continuation_allowed": False,
                "g1_promotion_allowed": False,
            },
            "rows": [
                {"check_id": requirement["check_id"], "status": "pass", "observed": "present", "blocker": ""}
                for requirement in mod.SURFACE_REQUIREMENTS
            ],
        },
    )

    payload = mod.build_f2g_f2h_authoritative_surface_recovery_packet(root=tmp_path)

    summary = payload["summary"]
    assert summary["status"] == "f2g_f2h_authoritative_surface_recovery_not_required"
    assert summary["recovery_required"] is False
    assert summary["blocked_recovery_item_count"] == 0


def test_recovery_packet_cli_writes_outputs(tmp_path: Path) -> None:
    _write_json(tmp_path / ".betelgeuze/f2g_f2h_surface_preflight.local.json", _blocked_preflight())
    out_json = tmp_path / "packet.json"
    out_csv = tmp_path / "packet.csv"
    out_md = tmp_path / "packet.md"

    mod.main(["--root", str(tmp_path), "--out-json", str(out_json), "--out-csv", str(out_csv), "--out-md", str(out_md)])

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["packet_type"] == "f2g_f2h_authoritative_surface_recovery_packet"
    assert out_csv.read_text(encoding="utf-8").startswith("recovery_item_id,")
    assert "F2g/F2h Authoritative Surface Recovery Packet" in out_md.read_text(encoding="utf-8")
