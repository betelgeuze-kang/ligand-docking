from __future__ import annotations

import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_unlock_evidence_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _handoff_row(field: str, *, ready: bool = False, fill_kind: str = "manifest_value") -> dict:
    return {
        "field_order": {"source_id": 1, "prediction_pdb": 2, "prediction_created_at": 3}.get(field, 99),
        "field_key": field,
        "fill_kind": fill_kind,
        "operator_status": "operator_value_present" if ready else "awaiting_operator_value",
        "fill_status": "field_ready_for_fulfillment_gate" if ready else "awaiting_operator_value",
        "required_format": "local pre-native prediction PDB path" if field == "prediction_pdb" else "operator value",
        "destination": "manifest.csv" if fill_kind != "file" else "",
        "operator_template_csv": "request/operator_source_values_template.csv",
        "blocker": "" if ready else "operator_value_missing",
        "next_action": f"fill operator_value for {field}",
    }


def _write_handoff(path: Path, *, ready: bool = False) -> None:
    _write_json(
        path,
        {
            "summary": {
                "first_unlock_handoff_status": (
                    "first_unlock_handoff_ready_for_source_gate_review"
                    if ready
                    else "awaiting_first_unlock_operator_values"
                ),
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "request_id": "source_request_001",
                "candidate_target_id": "HIST_BBA5",
                "candidate_scope": "monomer",
                "operator_template_csv": "request/operator_source_values_template.csv",
                "prediction_dropzone": "dropzone/replacement_prediction.pdb",
                "current_prediction_created_at": "2026-02-19",
                "current_native_release_date": "2004-05-13",
            },
            "rows": [
                _handoff_row("source_id", ready=ready),
                _handoff_row("prediction_pdb", ready=ready, fill_kind="file"),
                _handoff_row("prediction_created_at", ready=ready),
            ],
        },
    )


def _args(tmp_path: Path, handoff: Path) -> list[str]:
    return [
        "--first-unlock-handoff-json",
        str(handoff),
        "--packet-root",
        str(tmp_path / "packet_root"),
        "--out-json",
        str(tmp_path / "packet.json"),
        "--out-csv",
        str(tmp_path / "packet.csv"),
        "--out-md",
        str(tmp_path / "PACKET.md"),
    ]


def test_first_unlock_evidence_packet_creates_field_stubs(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    _write_handoff(handoff, ready=False)

    args = mod.parse_args(_args(tmp_path, handoff))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    packet_folder = tmp_path / "packet_root" / "source_request_001_hist_bba5"
    assert summary["first_unlock_evidence_packet_status"] == "awaiting_first_unlock_evidence_collection"
    assert summary["field_count"] == 3
    assert summary["open_field_count"] == 3
    assert summary["ready_field_count"] == 0
    assert summary["evidence_stub_count"] == 3
    assert summary["file_field_count"] == 1
    assert summary["first_open_field"] == "source_id"
    assert summary["first_blocker"] == "operator_value_missing"
    assert payload["rows"][0]["required_evidence_kind"] == "internal_source_identifier"
    assert (packet_folder / "ACTION.md").is_file()
    assert (packet_folder / "operator_evidence_template.csv").is_file()
    assert (packet_folder / "dropzone_manifest.csv").is_file()
    assert (packet_folder / "field_evidence" / "source_id.md").is_file()
    assert "Claim Boundary" in (tmp_path / "PACKET.md").read_text(encoding="utf-8")


def test_first_unlock_evidence_packet_ready_when_handoff_rows_ready(tmp_path: Path) -> None:
    handoff = tmp_path / "handoff.json"
    _write_handoff(handoff, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, handoff)))

    assert payload["summary"]["first_unlock_evidence_packet_status"] == (
        "first_unlock_evidence_packet_ready_for_source_gate_review"
    )
    assert payload["summary"]["ready_field_count"] == 3
    assert payload["summary"]["open_field_count"] == 0
    assert {row["packet_status"] for row in payload["rows"]} == {"evidence_ready_for_operator_review"}


def test_first_unlock_evidence_packet_blocks_missing_handoff(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing_handoff.json")))

    assert payload["summary"]["first_unlock_evidence_packet_status"] == (
        "blocked_first_unlock_handoff_missing"
    )
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []
