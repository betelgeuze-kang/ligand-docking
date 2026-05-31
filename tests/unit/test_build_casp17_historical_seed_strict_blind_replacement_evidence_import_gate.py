from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_strict_blind_replacement_evidence_import_gate as mod


INTAKE_COLUMNS = [
    "queue_rank",
    "required_benchmark_id",
    "required_target_id",
    "scope",
    "metric_profile",
    "replacement_target_id",
    "replacement_benchmark_id",
    "target_identity_non_current_historical",
    "prediction_pdb",
    "native_pdb",
    "native_authority_ref",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "no_leak_evidence_ref",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "ablation_manifest_ref",
    "calibration_values_ref",
    "operator_clearance",
    "operator",
    "notes",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in resolved:
                resolved.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _placeholder_intake(path: Path) -> None:
    _write_csv(
        path,
        [
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "required_target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "metric_profile": "TM,GDT_TS,CA_lDDT",
                "replacement_target_id": "REQUIRED_CLOSED_HISTORICAL_TARGET_ID",
                "replacement_benchmark_id": "REQUIRED_REPLACEMENT_BENCHMARK_ID",
                "target_identity_non_current_historical": "REQUIRED_TRUE_CONFIRMATION",
                "prediction_pdb": "REQUIRED_LOCAL_PREDICTION_PDB",
                "native_pdb": "REQUIRED_LOCAL_NATIVE_PDB",
                "native_authority_ref": "REQUIRED_LOCAL_NATIVE_AUTHORITY_REF",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "no_leak_evidence_ref": "REQUIRED_LOCAL_NO_LEAK_EVIDENCE_REF",
                "public_template_or_native_used_for_prediction": "REQUIRED_FALSE_CONFIRMATION",
                "other_team_model_used": "REQUIRED_FALSE_CONFIRMATION",
                "post_release_information_used": "REQUIRED_FALSE_CONFIRMATION",
                "ablation_manifest_ref": "REQUIRED_LOCAL_ABLATION_MANIFEST_REF",
                "calibration_values_ref": "REQUIRED_LOCAL_CALIBRATION_VALUES_REF",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "operator": "REQUIRED_OPERATOR_ID",
                "notes": "placeholder",
            }
        ],
        INTAKE_COLUMNS,
    )


def _patch_preview(path: Path, intake_csv: Path, *, source_status: str = "missing") -> None:
    source = path.parent / "prediction" / "replacement_prediction.pdb"
    if source_status == "present":
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("ATOM      1  CA  ALA A   1       0.000   1.000   2.000  1.00 70.00           C  \n", encoding="utf-8")
    _write_csv(
        path,
        [
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "prediction_pdb",
                "field_kind": "file",
                "recommended_value": str(source) if source_status == "present" else "",
                "source_status": source_status,
                "source_path": str(source),
                "destination_intake_csv": str(intake_csv),
                "operator_action": "review and copy",
                "notes": "valid local prediction PDB",
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "replacement_target_id",
                "field_kind": "operator_value",
                "recommended_value": "",
                "source_status": "operator_required",
                "source_path": "",
                "destination_intake_csv": str(intake_csv),
                "operator_action": "fill value",
                "notes": "required operator value",
            },
        ],
    )


def _dropzones_json(tmp_path: Path, patch_csv: Path) -> None:
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_dropzone_status": "awaiting_strict_blind_evidence_files",
                "dropzone_count": 1,
            },
            "rows": [
                {
                    "queue_rank": 1,
                    "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "patch_preview_csv": str(patch_csv),
                }
            ],
        },
    )


def _args(tmp_path: Path, *, apply: bool = False) -> list[str]:
    args = [
        "--dropzones-json",
        str(tmp_path / "dropzones.json"),
        "--out-json",
        str(tmp_path / "import.json"),
        "--out-csv",
        str(tmp_path / "import.csv"),
        "--out-md",
        str(tmp_path / "IMPORT.md"),
    ]
    if apply:
        args.append("--apply")
    return args


def test_evidence_import_gate_waits_for_missing_file_and_operator_value(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv)
    _dropzones_json(tmp_path, patch_csv)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["strict_blind_replacement_evidence_import_gate_status"] == (
        "awaiting_strict_blind_evidence_import"
    )
    assert payload["summary"]["action_count"] == 2
    assert payload["summary"]["file_action_count"] == 1
    assert payload["summary"]["operator_value_action_count"] == 1
    assert payload["summary"]["awaiting_file_count"] == 1
    assert payload["summary"]["awaiting_operator_value_count"] == 1
    assert payload["summary"]["ready_for_apply_count"] == 0
    assert "Claim Boundary" in (tmp_path / "IMPORT.md").read_text(encoding="utf-8")


def test_evidence_import_gate_dry_run_detects_ready_file_without_mutating(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv, source_status="present")
    _dropzones_json(tmp_path, patch_csv)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_import_gate_status"] == "ready_for_file_path_apply"
    assert payload["summary"]["ready_for_apply_count"] == 1
    assert _read_csv(intake_csv)[0]["prediction_pdb"] == "REQUIRED_LOCAL_PREDICTION_PDB"


def test_evidence_import_gate_apply_updates_only_file_placeholders(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv, source_status="present")
    _dropzones_json(tmp_path, patch_csv)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, apply=True)))

    assert payload["summary"]["strict_blind_replacement_evidence_import_gate_status"] == (
        "applied_file_paths_pending_operator_values"
    )
    assert payload["summary"]["applied_count"] == 1
    assert payload["summary"]["awaiting_operator_value_count"] == 1
    assert _read_csv(intake_csv)[0]["prediction_pdb"].endswith("dropzone/prediction/replacement_prediction.pdb")
    assert _read_csv(intake_csv)[0]["replacement_target_id"] == "REQUIRED_CLOSED_HISTORICAL_TARGET_ID"


def test_evidence_import_gate_reports_missing_dropzone_input(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_evidence_import_gate_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_evidence_dropzones_json_missing" in payload["summary"]["input_blockers"]
