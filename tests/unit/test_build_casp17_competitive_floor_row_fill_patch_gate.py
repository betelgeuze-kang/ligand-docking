from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_competitive_floor_row_fill_patch_gate as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_patch_gate_marks_placeholder_patch_candidate_ready(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001"}])
    intake = tmp_path / "intake.json"
    _write_json(
        intake,
        {
            "summary": {"intake_status": "ready_for_operator_patch"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "source_row_fill_csv": str(row_fill),
                    "row_fill_value": "REQUIRED_MONOMER_001",
                    "recommended_value": "T9001",
                    "intake_status": "patch_candidate",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--intake-json",
            str(intake),
            "--out-json",
            str(tmp_path / "gate.json"),
            "--out-csv",
            str(tmp_path / "gate.csv"),
            "--out-md",
            str(tmp_path / "GATE.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["patch_gate_status"] == "ready_for_operator_patch"
    assert payload["summary"]["ready_to_patch_count"] == 1
    assert payload["summary"]["ready_row_count"] == 1
    assert payload["rows"][0]["patch_status"] == "ready_to_patch"
    assert (folder / "ROW_FILL_PATCH_DRY_RUN.csv").is_file()
    assert (folder / "ROW_FILL_PATCH_DRY_RUN.md").is_file()
    dry_rows = _read_csv(folder / "ROW_FILL_PATCH_DRY_RUN.csv")
    assert dry_rows[0]["recommended_value"] == "T9001"


def test_patch_gate_blocks_conflicting_existing_value(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "T8000"}])
    intake = tmp_path / "intake.json"
    _write_json(
        intake,
        {
            "summary": {"intake_status": "ready_for_operator_patch"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "source_row_fill_csv": str(row_fill),
                    "row_fill_value": "T8000",
                    "recommended_value": "T9001",
                    "intake_status": "patch_candidate",
                }
            ],
        },
    )
    args = mod.parse_args(["--intake-json", str(intake)])

    payload = mod.build_payload(args)

    assert payload["summary"]["patch_gate_status"] == "blocked"
    assert payload["summary"]["conflict_count"] == 1
    assert payload["rows"][0]["patch_status"] == "conflict_existing_value"


def test_patch_gate_awaits_evidence_without_candidates(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"prediction_pdb": "REQUIRED_prediction.pdb"}])
    intake = tmp_path / "intake.json"
    _write_json(
        intake,
        {
            "summary": {"intake_status": "awaiting_evidence"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "source_row_fill_csv": str(row_fill),
                    "row_fill_value": "REQUIRED_prediction.pdb",
                    "recommended_value": "",
                    "intake_status": "awaiting_dropzone_file",
                }
            ],
        },
    )
    args = mod.parse_args(["--intake-json", str(intake)])

    payload = mod.build_payload(args)

    assert payload["summary"]["patch_gate_status"] == "awaiting_evidence"
    assert payload["summary"]["awaiting_evidence_count"] == 1
    assert payload["rows"][0]["patch_status"] == "awaiting_evidence"
