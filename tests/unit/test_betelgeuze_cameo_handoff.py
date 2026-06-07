from __future__ import annotations

import json
from pathlib import Path

from betelgeuze_cameo.handoff import build_dry_run_handoff_packet
from tools import build_cameo_dry_run_handoff_packet as tool


def _selection_packet() -> dict:
    return {
        "summary": {
            "selection_status": "cameo_model1_selection_ready",
            "target_id": "CAMEO100",
            "native_or_external_accuracy_used": False,
        },
        "rows": [
            {
                "target_id": "CAMEO100",
                "candidate_id": "internal_model1",
                "cameo_model_rank": 1,
                "model_path": "runs/cameo/internal_model1.pdb",
                "selection_status": "model1_candidate",
            },
            {
                "target_id": "CAMEO100",
                "candidate_id": "internal_model2",
                "cameo_model_rank": 2,
                "model_path": "runs/cameo/internal_model2.cif",
                "selection_status": "top5_candidate",
            },
        ],
    }


def _format_packet() -> dict:
    return {
        "summary": {
            "status": "cameo_format_validation_ready",
            "target_id": "CAMEO100",
            "native_or_external_accuracy_used": False,
        },
        "rows": [
            {
                "target_id": "CAMEO100",
                "candidate_id": "internal_model1",
                "cameo_model_rank": 1,
                "model_path": "runs/cameo/internal_model1.pdb",
                "format_validation_status": "pass",
                "detected_format": "pdb",
                "atom_count": 10,
                "model_count": 1,
                "chain_count": 1,
                "residue_count": 4,
            },
            {
                "target_id": "CAMEO100",
                "candidate_id": "internal_model2",
                "cameo_model_rank": 2,
                "model_path": "runs/cameo/internal_model2.cif",
                "format_validation_status": "pass",
                "detected_format": "mmcif",
                "atom_count": 12,
                "model_count": 1,
                "chain_count": 1,
                "residue_count": 5,
            },
        ],
    }


def test_cameo_dry_run_handoff_packet_packages_validated_top_models() -> None:
    payload = build_dry_run_handoff_packet(_selection_packet(), _format_packet())

    summary = payload["summary"]
    assert summary["status"] == "cameo_handoff_dry_run_ready"
    assert summary["attachment_count"] == 2
    assert summary["model1_attachment_count"] == 1
    assert summary["outbound_email_enabled"] is False
    assert summary["external_state_mutated"] is False
    assert summary["email_approval_token_required"] == "APPROVE_CAMEO_OUTBOUND_EMAIL"
    assert payload["rows"][0]["attachment_filename"] == "model_1_internal_model1.pdb"
    assert payload["rows"][1]["attachment_filename"] == "model_2_internal_model2.cif"


def test_cameo_dry_run_handoff_blocks_missing_model1_format_pass() -> None:
    format_packet = _format_packet()
    format_packet["rows"] = [row for row in format_packet["rows"] if row["cameo_model_rank"] != 1]

    payload = build_dry_run_handoff_packet(_selection_packet(), format_packet)
    codes = {blocker["code"] for blocker in payload["summary"]["blockers"]}

    assert payload["summary"]["status"] == "blocked_cameo_handoff"
    assert "model1_attachment_missing_or_duplicated" in codes


def test_cameo_dry_run_handoff_blocks_not_ready_inputs() -> None:
    selection_packet = _selection_packet()
    selection_packet["summary"]["selection_status"] = "blocked_no_model1_candidate"
    format_packet = _format_packet()
    format_packet["summary"]["status"] = "blocked_format_validation_failures"

    payload = build_dry_run_handoff_packet(selection_packet, format_packet)
    codes = {blocker["code"] for blocker in payload["summary"]["blockers"]}

    assert payload["summary"]["status"] == "blocked_cameo_handoff"
    assert "selection_packet_not_ready" in codes
    assert "format_packet_not_ready" in codes


def test_cameo_dry_run_handoff_tool_writes_outputs(tmp_path: Path) -> None:
    selection_json = tmp_path / "selection.json"
    format_json = tmp_path / "format.json"
    out_json = tmp_path / "handoff.json"
    out_csv = tmp_path / "handoff.csv"
    out_md = tmp_path / "handoff.md"
    selection_json.write_text(json.dumps(_selection_packet()) + "\n", encoding="utf-8")
    format_json.write_text(json.dumps(_format_packet()) + "\n", encoding="utf-8")

    tool.main(
        [
            "--selection-json",
            str(selection_json),
            "--format-json",
            str(format_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["status"] == "cameo_handoff_dry_run_ready"
    assert out_csv.read_text(encoding="utf-8").startswith("target_id,")
    assert "CAMEO Dry-Run Handoff Packet" in out_md.read_text(encoding="utf-8")
