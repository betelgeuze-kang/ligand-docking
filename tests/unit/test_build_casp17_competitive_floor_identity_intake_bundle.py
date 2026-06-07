from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_identity_intake_bundle as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path, identity_json: Path, gate_json: Path) -> list[str]:
    return [
        "--identity-kit-json",
        str(identity_json),
        "--readiness-gate-json",
        str(gate_json),
        "--out-json",
        str(tmp_path / "intake.json"),
        "--out-csv",
        str(tmp_path / "intake.csv"),
        "--out-md",
        str(tmp_path / "INTAKE.md"),
    ]


def test_identity_intake_bundle_reports_missing_fields(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    gate_json = tmp_path / "gate.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "awaiting_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "current_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "current_target_id": "REQUIRED_MONOMER_001",
                    "identity_status": "awaiting_identity",
                    "blockers": "proposed_benchmark_id_required,proposed_target_id_required,evidence_ref_required,operator_clearance_required",
                }
            ],
        },
    )
    _write_json(gate_json, {"summary": {"readiness_gate_status": "awaiting_identity"}})
    args = mod.parse_args(_args(tmp_path, identity_json, gate_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_intake_status"] == "awaiting_identity"
    assert payload["summary"]["missing_field_count"] == 4
    assert payload["rows"][0]["missing_field_count"] == 4
    assert "proposed_target_id" in payload["rows"][0]["next_action"]
    assert _read_csv(tmp_path / "intake.csv")[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert (tmp_path / "INTAKE.md").is_file()


def test_identity_intake_bundle_marks_ready_rows_for_apply(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    gate_json = tmp_path / "gate.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "ready_for_import"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "current_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "current_target_id": "REQUIRED_MONOMER_001",
                    "proposed_benchmark_id": "hist_T9001",
                    "proposed_target_id": "T9001",
                    "evidence_ref": "local/no_leak/T9001.md",
                    "operator_clearance": "ready_for_row_fill",
                    "identity_status": "ready_for_import",
                    "file_actions_unlocked": 12,
                }
            ],
        },
    )
    _write_json(gate_json, {"summary": {"readiness_gate_status": "ready_for_identity_apply"}})
    args = mod.parse_args(_args(tmp_path, identity_json, gate_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["identity_intake_status"] == "ready_for_identity_apply"
    assert payload["summary"]["ready_for_identity_apply_count"] == 1
    assert payload["summary"]["file_actions_unlocked_count"] == 12
    assert payload["rows"][0]["missing_field_count"] == 0
    assert "--apply-identity" in payload["summary"]["apply_identity_command"]


def test_identity_intake_bundle_preserves_blocked_rows(tmp_path: Path) -> None:
    identity_json = tmp_path / "identity.json"
    gate_json = tmp_path / "gate.json"
    _write_json(
        identity_json,
        {
            "summary": {"identity_unlock_status": "awaiting_identity"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "operator_priority": 1,
                    "row_rank": 1,
                    "scope": "monomer",
                    "proposed_benchmark_id": "hist_T1331",
                    "proposed_target_id": "T1331",
                    "evidence_ref": "local/no_leak/T1331.md",
                    "operator_clearance": "ready_for_row_fill",
                    "identity_status": "blocked_identity",
                    "blockers": "proposed_target_id_is_current_casp17_target",
                }
            ],
        },
    )
    _write_json(gate_json, {"summary": {"readiness_gate_status": "blocked_identity"}})
    args = mod.parse_args(_args(tmp_path, identity_json, gate_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["identity_intake_status"] == "blocked_identity"
    assert payload["summary"]["blocked_identity_count"] == 1
    assert payload["rows"][0]["missing_field_count"] == 0
    assert "current_casp17_target" in payload["rows"][0]["next_action"]
