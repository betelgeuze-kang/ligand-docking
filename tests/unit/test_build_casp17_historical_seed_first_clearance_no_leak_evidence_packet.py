from __future__ import annotations

import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_first_clearance_no_leak_evidence_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gate_row(field_name: str, *, ready: bool = False, weak_hint: str = "") -> dict:
    return {
        "target_id": "HIST_CHIGNOLIN",
        "benchmark_id": "hist_seed_chignolin",
        "field_name": field_name,
        "required_value_policy": "iso_date" if field_name.endswith("_date") else "operator_id",
        "weak_local_hint": weak_hint,
        "weak_local_hint_source": "prediction_path_date" if weak_hint else "",
        "evidence_ref": "casp17/no_leak_dossier.md",
        "value_status": "operator_value_present" if ready else "operator_value_missing",
        "clearance_status": "operator_clearance_present" if ready else "operator_clearance_missing",
        "policy_status": "policy_pass" if ready else "policy_not_checked_value_missing",
        "field_gate_status": "ready_for_no_leak_review" if ready else "awaiting_operator_input",
        "first_blocker": "" if ready else "operator_value_missing",
    }


def _write_gate(path: Path, *, ready: bool = False) -> None:
    _write_json(
        path,
        {
            "summary": {
                "first_clearance_no_leak_gate_status": (
                    "first_clearance_no_leak_ready_for_promotion_review"
                    if ready
                    else "awaiting_operator_no_leak_values"
                ),
                "target_id": "HIST_CHIGNOLIN",
                "benchmark_id": "hist_seed_chignolin",
                "no_leak_operator_intake_csv": "kit/no_leak_operator_intake.csv",
            },
            "rows": [
                _gate_row("no_leak_evidence_ref", ready=ready),
                _gate_row("prediction_created_at", ready=ready, weak_hint="2026-02-19"),
            ],
        },
    )


def _args(tmp_path: Path, gate: Path) -> list[str]:
    return [
        "--no-leak-gate-json",
        str(gate),
        "--packet-root",
        str(tmp_path / "packet_root"),
        "--out-json",
        str(tmp_path / "packet.json"),
        "--out-csv",
        str(tmp_path / "packet.csv"),
        "--out-md",
        str(tmp_path / "PACKET.md"),
    ]


def test_no_leak_evidence_packet_creates_operator_stubs(tmp_path: Path) -> None:
    gate = tmp_path / "gate.json"
    _write_gate(gate, ready=False)

    args = mod.parse_args(_args(tmp_path, gate))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    packet_folder = tmp_path / "packet_root" / "hist_chignolin"
    assert summary["first_clearance_no_leak_evidence_packet_status"] == (
        "awaiting_first_clearance_no_leak_evidence_collection"
    )
    assert summary["field_count"] == 2
    assert summary["open_field_count"] == 2
    assert summary["ready_field_count"] == 0
    assert summary["evidence_stub_count"] == 2
    assert summary["weak_hint_count"] == 1
    assert summary["first_open_field"] == "no_leak_evidence_ref"
    assert payload["rows"][0]["evidence_request_kind"] == "independent_no_leak_evidence"
    assert (packet_folder / "ACTION.md").is_file()
    assert (packet_folder / "operator_evidence_template.csv").is_file()
    assert (packet_folder / "field_evidence" / "no_leak_evidence_ref.md").is_file()
    assert "Claim Boundary" in (tmp_path / "PACKET.md").read_text(encoding="utf-8")


def test_no_leak_evidence_packet_reports_ready_gate_for_review(tmp_path: Path) -> None:
    gate = tmp_path / "gate.json"
    _write_gate(gate, ready=True)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, gate)))

    assert payload["summary"]["first_clearance_no_leak_evidence_packet_status"] == (
        "first_clearance_no_leak_evidence_packet_ready_for_review"
    )
    assert payload["summary"]["ready_field_count"] == 2
    assert payload["summary"]["open_field_count"] == 0
    assert {row["packet_status"] for row in payload["rows"]} == {"evidence_ready_for_operator_review"}


def test_no_leak_evidence_packet_blocks_missing_gate(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path, tmp_path / "missing_gate.json")))

    assert payload["summary"]["first_clearance_no_leak_evidence_packet_status"] == "blocked_no_leak_gate_missing"
    assert payload["summary"]["field_count"] == 0
    assert payload["rows"] == []
