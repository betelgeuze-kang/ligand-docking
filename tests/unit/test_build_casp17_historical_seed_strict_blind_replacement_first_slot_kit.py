from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_first_slot_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _args(tmp_path: Path) -> list[str]:
    return [
        "--evidence-action-board-json",
        str(tmp_path / "evidence.json"),
        "--operator-action-board-json",
        str(tmp_path / "operator.json"),
        "--cycle-json",
        str(tmp_path / "cycle.json"),
        "--kit-dir",
        str(tmp_path / "kit"),
        "--out-json",
        str(tmp_path / "first_slot.json"),
        "--out-csv",
        str(tmp_path / "first_slot.csv"),
        "--out-md",
        str(tmp_path / "FIRST_SLOT.md"),
    ]


def _write_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "cycle.json",
        {
            "summary": {
                "strict_blind_replacement_cycle_status": "awaiting_evidence_files",
                "first_blocking_stage": "evidence_dropzones",
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
            }
        },
    )
    _write_json(
        tmp_path / "evidence.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_action_board_status": (
                    "awaiting_strict_blind_evidence_actions"
                ),
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
            },
            "rows": [
                {
                    "action_id": "strict_blind_evidence_001",
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "required_target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "field_name": "prediction_pdb",
                    "action_status": "open_missing_file",
                    "source_path": "casp17/dropzone/prediction/replacement_prediction.pdb",
                    "verify_command": "python3 tools/build_quality.py",
                    "next_action": "place prediction PDB",
                },
                {
                    "action_id": "strict_blind_evidence_002",
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "required_target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "field_name": "native_pdb",
                    "action_status": "open_missing_file",
                    "source_path": "casp17/dropzone/native/replacement_native.pdb",
                    "verify_command": "python3 tools/build_quality.py",
                    "next_action": "place native PDB",
                },
                {
                    "action_id": "strict_blind_evidence_999",
                    "queue_rank": 2,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_002",
                    "field_name": "prediction_pdb",
                    "action_status": "open_missing_file",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "operator.json",
        {
            "summary": {
                "strict_blind_replacement_operator_action_board_status": (
                    "awaiting_strict_blind_operator_actions"
                ),
                "first_open_benchmark_id": "hist_REQUIRED_MONOMER_001",
            },
            "rows": [
                {
                    "action_id": "strict_blind_operator_001",
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "field_name": "replacement_target_id",
                    "action_status": "open_operator_value",
                    "operator_value_present": "false",
                    "evidence_ref_present": "false",
                    "operator_clearance_present": "false",
                    "operator_values_csv": "casp17/intake/replacement_operator_values.csv",
                    "destination_intake_csv": "casp17/intake/replacement_candidate_intake.csv",
                    "verify_command": "python3 tools/build_operator.py",
                    "next_action": "fill replacement target",
                },
                {
                    "action_id": "strict_blind_operator_002",
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "field_name": "native_release_date",
                    "action_status": "open_operator_value",
                    "operator_value_present": "false",
                    "evidence_ref_present": "false",
                    "operator_clearance_present": "false",
                    "operator_values_csv": "casp17/intake/replacement_operator_values.csv",
                    "destination_intake_csv": "casp17/intake/replacement_candidate_intake.csv",
                    "verify_command": "python3 tools/build_operator.py",
                    "next_action": "fill native date",
                },
                {
                    "action_id": "strict_blind_operator_999",
                    "queue_rank": 2,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_002",
                    "field_name": "replacement_target_id",
                    "action_status": "open_operator_value",
                    "operator_value_present": "false",
                    "evidence_ref_present": "false",
                    "operator_clearance_present": "false",
                },
            ],
        },
    )


def test_first_slot_kit_filters_current_first_benchmark_and_writes_kit(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["strict_blind_replacement_first_slot_kit_status"] == "awaiting_first_slot_evidence_files"
    assert summary["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001"
    assert summary["required_target_id"] == "REQUIRED_MONOMER_001"
    assert summary["scope"] == "monomer"
    assert summary["evidence_action_count"] == 2
    assert summary["evidence_open_count"] == 2
    assert summary["operator_action_count"] == 2
    assert summary["operator_open_value_count"] == 2
    assert summary["operator_open_evidence_count"] == 2
    assert summary["operator_open_clearance_count"] == 2
    assert summary["first_open_action_group"] == "evidence_file"
    assert summary["first_open_field"] == "prediction_pdb"
    assert len(payload["rows"]) == 4

    kit_dir = tmp_path / "kit" / "hist_REQUIRED_MONOMER_001"
    assert (kit_dir / "FIRST_SLOT_KIT.md").is_file()
    assert len(_read_csv(kit_dir / "first_slot_evidence_actions.csv")) == 2
    assert len(_read_csv(kit_dir / "first_slot_operator_actions.csv")) == 2
    assert len(_read_csv(tmp_path / "first_slot.csv")) == 4
    assert "Claim Boundary" in (tmp_path / "FIRST_SLOT.md").read_text(encoding="utf-8")


def test_first_slot_kit_can_report_ready_for_import(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    evidence = json.loads((tmp_path / "evidence.json").read_text(encoding="utf-8"))
    for row in evidence["rows"]:
        if row["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001":
            row["action_status"] = "ready_for_quality_audit"
    _write_json(tmp_path / "evidence.json", evidence)
    operator = json.loads((tmp_path / "operator.json").read_text(encoding="utf-8"))
    for row in operator["rows"]:
        if row["required_benchmark_id"] == "hist_REQUIRED_MONOMER_001":
            row["action_status"] = "ready_to_apply"
            row["operator_value_present"] = "true"
            row["evidence_ref_present"] = "true"
            row["operator_clearance_present"] = "true"
    _write_json(tmp_path / "operator.json", operator)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_kit_status"] == (
        "first_slot_ready_for_import_gate"
    )
    assert payload["summary"]["evidence_ready_count"] == 2
    assert payload["summary"]["operator_ready_count"] == 2


def test_first_slot_kit_reports_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_first_slot_kit_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_evidence_action_board_json_missing" in payload["summary"]["input_blockers"]
