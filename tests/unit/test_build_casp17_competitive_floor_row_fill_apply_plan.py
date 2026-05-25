from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_row_fill_apply_plan as mod


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


def test_apply_plan_dry_run_keeps_ready_patch_unapplied(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001"}])
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "summary": {"patch_gate_status": "ready_for_operator_patch"},
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
                    "current_value": "REQUIRED_MONOMER_001",
                    "recommended_value": "T9001",
                    "patch_status": "ready_to_patch",
                }
            ],
        },
    )
    args = mod.parse_args(
        [
            "--patch-gate-json",
            str(gate),
            "--out-json",
            str(tmp_path / "apply.json"),
            "--out-csv",
            str(tmp_path / "apply.csv"),
            "--out-md",
            str(tmp_path / "APPLY.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["apply_plan_status"] == "ready_for_apply"
    assert payload["summary"]["planned_patch_count"] == 1
    assert payload["summary"]["applied_count"] == 0
    assert _read_csv(row_fill)[0]["target_id"] == "REQUIRED_MONOMER_001"
    assert (folder / "ROW_FILL_APPLY_PLAN.csv").is_file()
    assert (folder / "ROW_FILL_APPLY_PLAN.md").is_file()


def test_apply_plan_apply_mode_updates_placeholder_only(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001", "scope": "monomer"}])
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "summary": {"patch_gate_status": "ready_for_operator_patch"},
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
                    "current_value": "REQUIRED_MONOMER_001",
                    "recommended_value": "T9001",
                    "patch_status": "ready_to_patch",
                },
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 2,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "target_identity",
                    "template_column": "scope",
                    "source_row_fill_csv": str(row_fill),
                    "current_value": "monomer",
                    "recommended_value": "complex",
                    "patch_status": "ready_to_patch",
                },
            ],
        },
    )
    args = mod.parse_args(["--patch-gate-json", str(gate), "--apply", "--no-write-apply-plans"])

    payload = mod.build_payload(args)

    row = _read_csv(row_fill)[0]
    assert payload["summary"]["applied_count"] == 1
    assert row["target_id"] == "T9001"
    assert row["scope"] == "monomer"


def test_apply_plan_awaits_evidence_when_no_ready_patches(tmp_path: Path) -> None:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"target_id": "REQUIRED_MONOMER_001"}])
    gate = tmp_path / "gate.json"
    _write_json(
        gate,
        {
            "summary": {"patch_gate_status": "awaiting_evidence"},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "source_row_fill_csv": str(row_fill),
                    "current_value": "REQUIRED_MONOMER_001",
                    "recommended_value": "",
                    "patch_status": "awaiting_evidence",
                }
            ],
        },
    )
    args = mod.parse_args(["--patch-gate-json", str(gate)])

    payload = mod.build_payload(args)

    assert payload["summary"]["apply_plan_status"] == "awaiting_evidence"
    assert payload["summary"]["awaiting_evidence_count"] == 1
    assert payload["rows"][0]["apply_status"] == "awaiting_evidence"
