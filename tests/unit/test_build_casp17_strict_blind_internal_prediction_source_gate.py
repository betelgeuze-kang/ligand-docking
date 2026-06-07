import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_strict_blind_internal_prediction_source_gate as mod


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


def test_internal_prediction_source_gate_blocks_empty_template(tmp_path):
    manifest = tmp_path / "manifest.csv"
    audit = tmp_path / "audit.json"
    first_slot = tmp_path / "first_slot.json"

    _write_manifest(manifest, {})
    _write_json(
        audit,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "internal_source_manifest_template": str(manifest),
            }
        },
    )
    _write_json(
        first_slot,
        {
            "rows": [
                {
                    "field_name": "prediction_pdb",
                    "source_path": str(tmp_path / "dropzone" / "replacement_prediction.pdb"),
                }
            ]
        },
    )

    args = mod.parse_args(
        [
            "--audit-json",
            str(audit),
            "--first-slot-kit-json",
            str(first_slot),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "gate.md"),
            "--gate-dir",
            str(tmp_path / "gate"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["internal_prediction_source_gate_status"] == (
        "awaiting_internal_prediction_source_gate_fields"
    )
    assert payload["summary"]["blocked_count"] > 0
    assert payload["summary"]["first_blocker"] == "internal_source_id_missing_or_external"
    official = next(row for row in payload["rows"] if row["check_id"] == "source_id_internal")
    assert official["check_status"] == "blocked"


def test_internal_prediction_source_gate_passes_ready_internal_manifest(tmp_path):
    prediction = tmp_path / "dropzone" / "replacement_prediction.pdb"
    prediction.parent.mkdir(parents=True, exist_ok=True)
    prediction.write_text(
        "ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.csv"
    audit = tmp_path / "audit.json"
    first_slot = tmp_path / "first_slot.json"

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
            "native_authority_ref": "rcsb:9b0l",
            "prediction_author": "internal",
            "creation_evidence_ref": "evidence/timestamp.md",
            "no_leak_evidence_ref": "evidence/no_leak.md",
            "method_summary": "internal pre-native prediction package",
            "operator_clearance": "approved",
        },
    )
    _write_json(
        audit,
        {
            "summary": {
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "required_scope": "monomer",
                "internal_source_manifest_template": str(manifest),
            }
        },
    )
    _write_json(
        first_slot,
        {
            "rows": [
                {
                    "field_name": "prediction_pdb",
                    "source_path": str(prediction),
                }
            ]
        },
    )

    args = mod.parse_args(
        [
            "--audit-json",
            str(audit),
            "--first-slot-kit-json",
            str(first_slot),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "gate.md"),
            "--gate-dir",
            str(tmp_path / "gate"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["internal_prediction_source_gate_status"] == (
        "internal_prediction_source_ready_for_first_slot_dropzone"
    )
    assert payload["summary"]["blocked_count"] == 0
    assert payload["summary"]["pass_count"] == payload["summary"]["check_count"]
