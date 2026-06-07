import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_first_slot_closure_kit as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_first_slot_closure_kit_surfaces_first_gate_blocker(tmp_path):
    benchmark_id = "hist_REQUIRED_MONOMER_001"
    patch_preview = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    operator_values = tmp_path / "intake" / "replacement_operator_values.csv"
    intake_csv = tmp_path / "intake" / "replacement_candidate_intake.csv"
    _write_csv(
        patch_preview,
        [
            {
                "field_name": "prediction_pdb",
                "field_kind": "file",
                "source_status": "missing",
                "source_path": "dropzone/prediction/replacement_prediction.pdb",
                "destination_intake_csv": str(intake_csv),
                "operator_action": "place valid local prediction PDB at source_path",
            },
            {
                "field_name": "replacement_target_id",
                "field_kind": "operator_value",
                "source_status": "operator_required",
                "source_path": "",
                "destination_intake_csv": str(intake_csv),
                "operator_action": "fill and clear this value",
            },
        ],
        [
            "field_name",
            "field_kind",
            "source_status",
            "source_path",
            "destination_intake_csv",
            "operator_action",
        ],
    )
    _write_csv(operator_values, [], ["field_name", "operator_value"])
    first_slot = tmp_path / "first_slot.json"
    gate = tmp_path / "gate.json"
    operator_packet = tmp_path / "operator_packet.json"
    source_request_packet = tmp_path / "source_request_packet.json"
    apply_plan = tmp_path / "apply_plan.json"
    dropzones = tmp_path / "dropzones.json"
    operator_gate = tmp_path / "operator_gate.json"
    intake = tmp_path / "intake.json"

    _write_json(
        first_slot,
        {"summary": {"required_benchmark_id": benchmark_id, "required_target_id": "REQUIRED_MONOMER_001", "scope": "monomer"}},
    )
    _write_json(
        gate,
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "required_benchmark_id": benchmark_id,
                "manifest_csv": "gate/internal_prediction_source_manifest_template.csv",
                "pass_count": 3,
                "blocked_count": 13,
                "check_count": 16,
                "first_blocked_check": "source_id_internal",
                "first_blocker": "internal_source_id_missing_or_external",
                "first_next_action": "set source_id",
            },
            "rows": [
                {
                    "check_id": "source_id_internal",
                    "check_status": "blocked",
                    "actual_value": "",
                    "blocker": "internal_source_id_missing_or_external",
                    "next_action": "set source_id",
                }
            ],
        },
    )
    operator_fields = [
        "source_id",
        "prediction_pdb",
        "prediction_pdb_dropzone",
        "prediction_created_at",
        "native_release_date",
        "prediction_created_at/native_release_date",
        "native_authority_ref",
        "creation_evidence_ref",
        "no_leak_evidence_ref",
        "method_summary",
        "operator_clearance",
    ]
    _write_json(
        operator_packet,
        {
            "summary": {
                "source_gate_operator_packet_status": "awaiting_source_gate_operator_values",
                "required_benchmark_id": benchmark_id,
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "operator_csv": "source_gate_operator_values.csv",
                "field_action_count": 11,
                "operator_ready_count": 0,
                "operator_awaiting_count": 11,
                "patch_ready_count": 0,
                "patch_awaiting_count": 11,
                "first_field_key": "source_id",
                "first_operator_status": "awaiting_operator_value",
                "first_next_action": "fill source_id",
                "packet_dir": "operator_packet/hist_REQUIRED_MONOMER_001",
            },
            "operator_rows": [
                {
                    "field_key": field,
                    "fill_kind": "file" if field in {"prediction_pdb", "prediction_pdb_dropzone"} else "manifest_value",
                    "operator_status": "awaiting_operator_value",
                    "destination": "manifest.csv",
                    "next_action": f"fill {field}",
                }
                for field in operator_fields
            ],
        },
    )
    _write_json(
        source_request_packet,
        {
            "summary": {
                "source_request_packet_status": "awaiting_pre_native_source_or_candidate_replacement",
                "required_benchmark_id": benchmark_id,
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "request_count": 2,
                "pre_native_source_required_count": 1,
                "candidate_replacement_required_count": 1,
                "operator_evidence_repair_required_count": 0,
                "first_request_id": "source_request_001",
                "first_request_target_id": "HIST_BBA5",
                "first_request_kind": "pre_native_prediction_source_required",
                "first_request_blocker": "prediction_not_before_native",
                "first_next_action": "attach a pre-native prediction source",
                "request_dir": "source_requests",
            },
            "rows": [
                {
                    "candidate_target_id": "HIST_BBA5",
                    "request_folder": "source_requests/source_request_001",
                    "request_status": "awaiting_pre_native_source_or_replacement",
                    "next_action": "attach a pre-native prediction source",
                },
                {
                    "candidate_target_id": "HIST_COMPLEX_01",
                    "request_folder": "source_requests/source_request_002",
                    "request_status": "awaiting_candidate_replacement",
                    "next_action": "replace with a strict-blind monomer candidate",
                },
            ],
        },
    )
    _write_json(
        apply_plan,
        {
            "summary": {
                "internal_prediction_source_apply_plan_status": "blocked_until_internal_prediction_source_gate_passes",
                "ready_action_count": 0,
                "blocked_action_count": 16,
                "action_count": 16,
                "first_blocker": "internal_prediction_source_gate_not_ready",
                "first_next_action": "copy verified internal prediction PDB",
            },
            "rows": [
                {
                    "action_type": "file_copy",
                    "field_name": "prediction_pdb",
                    "action_status": "blocked",
                    "source_value": "",
                    "destination": "dropzone/prediction/replacement_prediction.pdb",
                    "next_action": "copy verified internal prediction PDB",
                }
            ],
        },
    )
    _write_json(
        dropzones,
        {
            "rows": [
                {
                    "required_benchmark_id": benchmark_id,
                    "dropzone_status": "awaiting_strict_blind_evidence_files",
                    "file_present_count": 0,
                    "file_missing_count": 6,
                    "file_required_count": 6,
                    "patch_preview_csv": str(patch_preview),
                    "dropzone_folder": "dropzone",
                    "blockers": "missing_files:6",
                    "next_action": "place strict-blind evidence files",
                }
            ]
        },
    )
    _write_json(
        operator_gate,
        {
            "summary": {
                "strict_blind_replacement_operator_value_gate_status": "awaiting_operator_values",
                "ready_for_apply_count": 0,
                "awaiting_operator_value_count": 10,
                "action_count": 10,
                "first_open_field": "replacement_target_id",
                "first_next_action": "fill operator values",
            },
            "rows": [{"required_benchmark_id": benchmark_id, "operator_values_csv": str(operator_values)}],
        },
    )
    _write_json(
        intake,
        {
            "rows": [
                {
                    "required_benchmark_id": benchmark_id,
                    "preflight_status": "awaiting_operator_input",
                    "filled_field_count": 0,
                    "missing_field_count": 16,
                    "required_field_count": 16,
                    "intake_csv": str(intake_csv),
                    "blockers": "prediction_pdb_required",
                    "next_action": "fill replacement_candidate_intake.csv",
                }
            ]
        },
    )

    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(first_slot),
            "--source-gate-json",
            str(gate),
            "--source-gate-operator-packet-json",
            str(operator_packet),
            "--source-gate-source-request-packet-json",
            str(source_request_packet),
            "--apply-plan-json",
            str(apply_plan),
            "--evidence-dropzones-json",
            str(dropzones),
            "--operator-gate-json",
            str(operator_gate),
            "--intake-json",
            str(intake),
            "--kit-dir",
            str(tmp_path / "kit"),
            "--out-json",
            str(tmp_path / "kit.json"),
            "--out-csv",
            str(tmp_path / "kit.csv"),
            "--out-md",
            str(tmp_path / "kit.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["first_slot_closure_kit_status"] == "blocked_on_internal_prediction_source_gate"
    assert payload["summary"]["step_blocked_count"] == 7
    assert payload["summary"]["step_count"] == 7
    assert payload["summary"]["first_blocker"] == "internal_source_id_missing_or_external"
    assert payload["summary"]["source_gate_operator_packet_status"] == "awaiting_source_gate_operator_values"
    assert payload["summary"]["source_gate_operator_awaiting_count"] == 11
    assert payload["summary"]["source_gate_source_request_packet_status"] == (
        "awaiting_pre_native_source_or_candidate_replacement"
    )
    assert payload["summary"]["source_request_fill_count"] == 2
    assert payload["summary"]["source_gate_fill_count"] == 11
    assert payload["summary"]["fill_item_count"] == 16
    assert payload["rows"][1]["step_id"] == "source_gate_operator_packet"
    assert payload["rows"][2]["step_id"] == "source_gate_source_requests"
    assert payload["fill_rows"][0]["fill_kind"] == "source_gate_operator_value"
    assert payload["fill_rows"][0]["field_name"] == "source_id"
    assert payload["fill_rows"][11]["fill_kind"] == "source_request"
    assert payload["fill_rows"][11]["field_name"] == "HIST_BBA5"
    assert (tmp_path / "kit" / benchmark_id / "fill_order.csv").exists()


def test_first_slot_closure_kit_blocks_missing_inputs(tmp_path):
    args = mod.parse_args(
        [
            "--first-slot-kit-json",
            str(tmp_path / "missing_first_slot.json"),
            "--source-gate-json",
            str(tmp_path / "missing_gate.json"),
            "--source-gate-operator-packet-json",
            str(tmp_path / "missing_operator_packet.json"),
            "--source-gate-source-request-packet-json",
            str(tmp_path / "missing_source_request_packet.json"),
            "--apply-plan-json",
            str(tmp_path / "missing_apply_plan.json"),
            "--evidence-dropzones-json",
            str(tmp_path / "missing_dropzones.json"),
            "--operator-gate-json",
            str(tmp_path / "missing_operator_gate.json"),
            "--intake-json",
            str(tmp_path / "missing_intake.json"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["first_slot_closure_kit_status"] == "blocked_missing_inputs"
    assert "first_slot_kit_json_missing" in payload["summary"]["input_blockers"]
    assert "source_gate_operator_packet_json_missing" in payload["summary"]["input_blockers"]
    assert "source_gate_source_request_packet_json_missing" in payload["summary"]["input_blockers"]
