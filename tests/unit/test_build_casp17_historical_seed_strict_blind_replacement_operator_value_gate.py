from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_strict_blind_replacement_operator_value_gate as mod


INTAKE_COLUMNS = [
    "replacement_target_id",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "operator_clearance",
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
                "replacement_target_id": "REQUIRED_REPLACEMENT_TARGET_ID",
                "prediction_created_at": "YYYY-MM-DD",
                "native_release_date": "YYYY-MM-DD",
                "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
            }
        ],
        INTAKE_COLUMNS,
    )


def _patch_preview(path: Path, intake_csv: Path) -> None:
    _write_csv(
        path,
        [
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "replacement_target_id",
                "field_kind": "operator_value",
                "destination_intake_csv": str(intake_csv),
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "prediction_created_at",
                "field_kind": "operator_value",
                "destination_intake_csv": str(intake_csv),
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "native_release_date",
                "field_kind": "operator_value",
                "destination_intake_csv": str(intake_csv),
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "prediction_generated_before_native_release",
                "field_kind": "operator_value",
                "destination_intake_csv": str(intake_csv),
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "operator_clearance",
                "field_kind": "operator_value",
                "destination_intake_csv": str(intake_csv),
            },
        ],
    )


def _dropzones_json(tmp_path: Path, patch_csv: Path) -> None:
    _write_json(
        tmp_path / "dropzones.json",
        {
            "summary": {
                "strict_blind_replacement_evidence_dropzone_status": "awaiting_strict_blind_evidence_files"
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
        str(tmp_path / "gate.json"),
        "--out-csv",
        str(tmp_path / "gate.csv"),
        "--out-md",
        str(tmp_path / "GATE.md"),
    ]
    if apply:
        args.append("--apply")
    return args


def _filled_operator_values(path: Path) -> None:
    _write_csv(
        path,
        [
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "replacement_target_id",
                "required_policy": "operator_supplied_non_placeholder",
                "operator_value": "HIST_CLOSED_001",
                "evidence_ref": "evidence/identity.md",
                "operator_clearance": "clear",
                "operator_id": "tester",
                "notes": "ok",
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "prediction_created_at",
                "required_policy": "authoritative_iso_date",
                "operator_value": "2025-01-01",
                "evidence_ref": "evidence/chronology.md",
                "operator_clearance": "clear",
                "operator_id": "tester",
                "notes": "ok",
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "native_release_date",
                "required_policy": "authoritative_iso_date",
                "operator_value": "2025-02-01",
                "evidence_ref": "evidence/chronology.md",
                "operator_clearance": "clear",
                "operator_id": "tester",
                "notes": "ok",
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "prediction_generated_before_native_release",
                "required_policy": "operator_confirmed_true",
                "operator_value": "true",
                "evidence_ref": "evidence/chronology.md",
                "operator_clearance": "clear",
                "operator_id": "tester",
                "notes": "ok",
            },
            {
                "queue_rank": "1",
                "required_benchmark_id": "hist_REQUIRED_MONOMER_001",
                "field_name": "operator_clearance",
                "required_policy": "operator_cleared",
                "operator_value": "clear",
                "evidence_ref": "evidence/operator.md",
                "operator_clearance": "clear",
                "operator_id": "tester",
                "notes": "ok",
            },
        ],
        mod.OPERATOR_VALUE_COLUMNS,
    )


def test_operator_value_gate_creates_fail_closed_template(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv)
    _dropzones_json(tmp_path, patch_csv)

    args = mod.parse_args(_args(tmp_path))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["strict_blind_replacement_operator_value_gate_status"] == "awaiting_operator_values"
    assert payload["summary"]["template_count"] == 1
    assert payload["summary"]["created_template_count"] == 1
    assert payload["summary"]["action_count"] == 5
    assert payload["summary"]["awaiting_operator_value_count"] == 5
    template = tmp_path / "replacement_operator_values.csv"
    assert template.is_file()
    assert _read_csv(template)[0]["operator_value"].startswith("REQUIRED_")
    assert "Claim Boundary" in (tmp_path / "GATE.md").read_text(encoding="utf-8")


def test_operator_value_gate_dry_run_detects_ready_values_without_mutating(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv)
    _dropzones_json(tmp_path, patch_csv)
    _filled_operator_values(tmp_path / "replacement_operator_values.csv")

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_operator_value_gate_status"] == (
        "ready_for_operator_value_apply"
    )
    assert payload["summary"]["ready_for_apply_count"] == 5
    assert _read_csv(intake_csv)[0]["replacement_target_id"] == "REQUIRED_REPLACEMENT_TARGET_ID"


def test_operator_value_gate_apply_updates_only_placeholder_values(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv)
    _dropzones_json(tmp_path, patch_csv)
    _filled_operator_values(tmp_path / "replacement_operator_values.csv")

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, apply=True)))

    assert payload["summary"]["strict_blind_replacement_operator_value_gate_status"] == (
        "applied_operator_values_pending_intake_preflight"
    )
    assert payload["summary"]["applied_count"] == 5
    row = _read_csv(intake_csv)[0]
    assert row["replacement_target_id"] == "HIST_CLOSED_001"
    assert row["prediction_generated_before_native_release"] == "true"
    assert row["operator_clearance"] == "clear"


def test_operator_value_gate_blocks_invalid_chronology(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    patch_csv = tmp_path / "dropzone" / "replacement_intake_patch_preview.csv"
    _placeholder_intake(intake_csv)
    _patch_preview(patch_csv, intake_csv)
    _dropzones_json(tmp_path, patch_csv)
    operator_csv = tmp_path / "replacement_operator_values.csv"
    _filled_operator_values(operator_csv)
    rows = _read_csv(operator_csv)
    for row in rows:
        if row["field_name"] == "prediction_created_at":
            row["operator_value"] = "2025-03-01"
    _write_csv(operator_csv, rows, mod.OPERATOR_VALUE_COLUMNS)

    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_operator_value_gate_status"] == (
        "blocked_operator_value_review"
    )
    assert payload["summary"]["blocked_count"] == 2


def test_operator_value_gate_reports_missing_dropzone_input(tmp_path: Path) -> None:
    payload = mod.build_payload(mod.parse_args(_args(tmp_path)))

    assert payload["summary"]["strict_blind_replacement_operator_value_gate_status"] == "blocked_missing_input"
    assert "strict_blind_replacement_evidence_dropzones_json_missing" in payload["summary"]["input_blockers"]
