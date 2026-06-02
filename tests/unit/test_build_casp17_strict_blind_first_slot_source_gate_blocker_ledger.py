import json
from pathlib import Path

from tools import build_casp17_strict_blind_first_slot_source_gate_blocker_ledger as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_builds_first_slot_source_gate_blocker_ledger(tmp_path):
    source_gate_json = tmp_path / "source_gate.json"
    field_board_json = tmp_path / "field_board.json"
    operator_packet_json = tmp_path / "operator_packet.json"
    review_gate_json = tmp_path / "review_gate.json"
    _write_json(
        source_gate_json,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "pass_count": 3,
                "blocked_count": 2,
                "check_count": 5,
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
            }
        },
    )
    _write_json(
        field_board_json,
        {
            "summary": {"required_benchmark_id": "hist_REQUIRED_MONOMER_001"},
            "rows": [
                {
                    "field_key": "source_id",
                    "fill_kind": "manifest_value",
                    "affected_check_ids": "source_id_internal",
                    "blocked_check_count": 1,
                    "pass_check_count": 0,
                    "blockers": "internal_source_id_missing_or_external",
                    "next_action": "set source_id",
                },
                {
                    "field_key": "prediction_pdb",
                    "fill_kind": "file",
                    "affected_check_ids": "manifest_prediction_pdb_exists",
                    "blocked_check_count": 1,
                    "pass_check_count": 0,
                    "blockers": "prediction_pdb_not_found",
                    "next_action": "attach pdb",
                },
            ],
        },
    )
    _write_json(
        operator_packet_json,
        {"summary": {"operator_ready_count": 0, "operator_awaiting_count": 2}},
    )
    _write_json(
        review_gate_json,
        {
            "summary": {
                "ready_field_count": 0,
                "blocked_field_count": 2,
                "template_operator_value_missing_count": 2,
                "template_operator_clearance_missing_count": 2,
                "template_operator_id_missing_count": 2,
                "stub_present_count": 2,
                "stub_evidence_missing_count": 2,
                "file_ready_count": 0,
                "file_blocked_count": 1,
            },
            "rows": [
                {
                    "field_key": "source_id",
                    "review_gate_status": "awaiting_operator_evidence",
                    "first_blocker": "template_operator_value_missing",
                    "template_value_status": "template_operator_value_missing",
                    "template_evidence_ref_status": "template_operator_evidence_ref_present",
                    "template_clearance_status": "template_operator_clearance_missing",
                    "template_operator_id_status": "template_operator_id_missing",
                    "stub_status": "stub_present",
                    "stub_evidence_status": "stub_operator_value_missing",
                    "policy_status": "policy_not_checked_value_missing",
                    "file_status": "file_not_required",
                    "evidence_stub_md": "field/source_id.md",
                    "next_action": "fill source_id",
                },
                {
                    "field_key": "prediction_pdb",
                    "review_gate_status": "awaiting_operator_evidence",
                    "first_blocker": "template_operator_value_missing",
                    "template_value_status": "template_operator_value_missing",
                    "template_evidence_ref_status": "template_operator_evidence_ref_present",
                    "template_clearance_status": "template_operator_clearance_missing",
                    "template_operator_id_status": "template_operator_id_missing",
                    "stub_status": "stub_present",
                    "stub_evidence_status": "stub_operator_value_missing",
                    "policy_status": "policy_not_checked_value_missing",
                    "file_status": "file_path_missing",
                    "evidence_stub_md": "field/prediction_pdb.md",
                    "next_action": "fill prediction_pdb",
                },
            ],
        },
    )
    args = mod.parse_args(
        [
            "--source-gate-json",
            str(source_gate_json),
            "--field-board-json",
            str(field_board_json),
            "--operator-packet-json",
            str(operator_packet_json),
            "--evidence-review-gate-json",
            str(review_gate_json),
            "--out-dir",
            str(tmp_path / "ledger"),
            "--out-json",
            str(tmp_path / "ledger.json"),
            "--out-csv",
            str(tmp_path / "ledger.csv"),
            "--out-md",
            str(tmp_path / "LEDGER.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_first_slot_source_gate_blocker_ledger_status"] == (
        "awaiting_first_slot_source_gate_operator_evidence"
    )
    assert summary["ledger_field_count"] == 2
    assert summary["ready_field_count"] == 0
    assert summary["blocked_field_count"] == 2
    assert summary["source_gate_pass_count"] == 3
    assert summary["source_gate_blocked_count"] == 2
    assert summary["operator_awaiting_count"] == 2
    assert summary["first_blocked_field"] == "source_id"
    assert summary["first_blocker"] == "template_operator_value_missing"

    rows = payload["rows"]
    assert rows[0]["field_key"] == "source_id"
    assert rows[0]["priority_class"] == "01_source_identity"
    assert "internal_source_id_missing_or_external" in rows[0]["blockers"]
    assert rows[1]["field_key"] == "prediction_pdb"
    assert rows[1]["priority_class"] == "02_prediction_file"
    assert "file_path_missing" in rows[1]["blockers"]
    assert (tmp_path / "ledger" / "01_source_id" / "SOURCE_GATE_BLOCKER.md").exists()
    assert "strict-blind first-slot source-gate" in (tmp_path / "LEDGER.md").read_text(
        encoding="utf-8"
    )
