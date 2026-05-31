import csv
import json
from pathlib import Path

from tools import build_casp17_strict_blind_internal_prediction_source_apply_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manifest(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "replacement_target_id",
        "target_id",
        "scope",
        "prediction_pdb",
        "prediction_created_at",
        "native_release_date",
        "native_authority_ref",
        "prediction_author",
        "creation_evidence_ref",
        "no_leak_evidence_ref",
        "method_summary",
        "operator_clearance",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def _first_slot_payload(tmp_path: Path) -> dict:
    intake = tmp_path / "intake" / "replacement_candidate_intake.csv"
    operator_values = tmp_path / "intake" / "replacement_operator_values.csv"
    return {
        "summary": {
            "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
            "required_target_id": "REQUIRED_MONOMER_001",
            "scope": "monomer",
        },
        "rows": [
            {
                "field_name": "prediction_pdb",
                "source_path": str(tmp_path / "dropzone" / "prediction" / "replacement_prediction.pdb"),
            },
            {
                "field_name": "native_pdb",
                "source_path": str(tmp_path / "dropzone" / "native" / "replacement_native.pdb"),
            },
            {
                "field_name": "ablation_manifest_ref",
                "source_path": str(tmp_path / "dropzone" / "ablation" / "ablation_manifest.csv"),
            },
            {
                "field_name": "calibration_values_ref",
                "source_path": str(tmp_path / "dropzone" / "calibration" / "calibration_values.csv"),
            },
            {
                "field_name": "replacement_target_id",
                "operator_values_csv": str(operator_values),
                "destination_intake_csv": str(intake),
            },
        ],
    }


def test_apply_plan_blocks_until_gate_ready(tmp_path):
    manifest = tmp_path / "manifest.csv"
    gate = tmp_path / "gate.json"
    audit = tmp_path / "audit.json"
    first_slot = tmp_path / "first_slot.json"
    source_bridge = tmp_path / "bridge.json"

    _write_manifest(manifest, {})
    _write_json(
        gate,
        {
            "summary": {
                "internal_prediction_source_gate_status": "awaiting_internal_prediction_source_gate_fields",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "manifest_csv": str(manifest),
                "first_blocker": "internal_source_id_missing_or_external",
                "prediction_dropzone": str(tmp_path / "dropzone" / "prediction" / "replacement_prediction.pdb"),
            }
        },
    )
    _write_json(audit, {"summary": {"internal_source_manifest_template": str(manifest)}})
    _write_json(first_slot, _first_slot_payload(tmp_path))
    _write_json(source_bridge, {"summary": {"source_bridge_status": "first_slot_source_bridge_internal_prediction_required"}})

    args = mod.parse_args(
        [
            "--gate-json",
            str(gate),
            "--audit-json",
            str(audit),
            "--first-slot-kit-json",
            str(first_slot),
            "--source-bridge-json",
            str(source_bridge),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
            "--plan-dir",
            str(tmp_path / "plan"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["internal_prediction_source_apply_plan_status"] == (
        "blocked_until_internal_prediction_source_gate_passes"
    )
    assert payload["summary"]["ready_action_count"] == 0
    assert payload["summary"]["blocked_action_count"] == payload["summary"]["action_count"]
    assert payload["summary"]["operator_value_action_count"] == 10
    first = payload["rows"][0]
    assert "internal_prediction_source_gate_not_ready" in first["blockers"]


def test_apply_plan_still_requires_supplemental_evidence_after_gate_ready(tmp_path):
    prediction = tmp_path / "internal" / "prediction.pdb"
    prediction.parent.mkdir(parents=True, exist_ok=True)
    prediction.write_text("ATOM      1  CA  ALA A   1       1.0     2.0     3.0  1.00 20.00           C\n", encoding="utf-8")
    manifest = tmp_path / "manifest.csv"
    gate = tmp_path / "gate.json"
    audit = tmp_path / "audit.json"
    first_slot = tmp_path / "first_slot.json"
    source_bridge = tmp_path / "bridge.json"

    _write_manifest(
        manifest,
        {
            "source_id": "internal_pre_native_run_001",
            "replacement_target_id": "CASP16_T1212",
            "target_id": "REQUIRED_MONOMER_001",
            "scope": "monomer",
            "prediction_pdb": str(prediction),
            "prediction_created_at": "2024-06-03",
            "native_release_date": "2025-02-01",
            "native_authority_ref": "casp17/native_authority/9b0l.md",
            "creation_evidence_ref": "casp17/evidence/internal_prediction_timestamp.md",
            "no_leak_evidence_ref": "casp17/evidence/no_leak.md",
            "method_summary": "internal pre-native prediction package",
            "operator_clearance": "approved",
        },
    )
    _write_json(
        gate,
        {
            "summary": {
                "internal_prediction_source_gate_status": "internal_prediction_source_ready_for_first_slot_dropzone",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "manifest_csv": str(manifest),
                "manifest_prediction_pdb": str(prediction),
                "prediction_dropzone": str(tmp_path / "dropzone" / "prediction" / "replacement_prediction.pdb"),
            }
        },
    )
    _write_json(audit, {"summary": {"internal_source_manifest_template": str(manifest)}})
    _write_json(first_slot, _first_slot_payload(tmp_path))
    _write_json(source_bridge, {"summary": {"source_bridge_status": "first_slot_source_bridge_internal_prediction_required"}})

    args = mod.parse_args(
        [
            "--gate-json",
            str(gate),
            "--audit-json",
            str(audit),
            "--first-slot-kit-json",
            str(first_slot),
            "--source-bridge-json",
            str(source_bridge),
            "--out-json",
            str(tmp_path / "plan.json"),
            "--out-csv",
            str(tmp_path / "plan.csv"),
            "--out-md",
            str(tmp_path / "plan.md"),
            "--plan-dir",
            str(tmp_path / "plan"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["ready_action_count"] == 11
    assert payload["summary"]["blocked_action_count"] == 5
    supplemental = [row for row in payload["rows"] if row["action_type"] == "supplemental_evidence"]
    assert len(supplemental) == 5
    assert all("supplemental_evidence_required" in row["blockers"] for row in supplemental)
