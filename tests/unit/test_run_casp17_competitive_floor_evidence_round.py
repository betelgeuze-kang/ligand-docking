from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import run_casp17_competitive_floor_evidence_round as mod


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


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(
        row_fill,
        [
            {
                "target_id": "REQUIRED_MONOMER_001",
                "prediction_pdb": "REQUIRED_prediction.pdb",
            }
        ],
    )
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "REQUIRED_OPERATOR_CLEARANCE",
                "ledger_status": "awaiting_value",
                "next_action": "enter target",
            }
        ],
    )
    core = folder / "evidence_dropzone" / "files" / "core"
    target_identity = folder / "evidence_dropzone" / "target_identity"
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(
        dropzone_json,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "action_rank": 1,
                    "operator_priority": 1,
                    "row_rank": 1,
                    "benchmark_id": "hist_REQUIRED_MONOMER_001",
                    "target_id": "REQUIRED_MONOMER_001",
                    "scope": "monomer",
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(core),
                    "drop_path": str(core / "<HISTORICAL_TARGET_ID>_prediction.pdb"),
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
                    "template_column": "target_id",
                    "source_row_fill_csv": str(row_fill),
                    "dropzone_folder": str(folder / "evidence_dropzone"),
                    "dropzone_class_folder": str(target_identity),
                    "drop_path": "",
                },
            ],
        },
    )
    source_pdb = tmp_path / "T9001_prediction.pdb"
    source_pdb.write_text("HEADER TEST\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    import_csv = tmp_path / "import.csv"
    _write_csv(
        import_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "prediction_pdb",
                "source_path": str(source_pdb),
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "template_column": "target_id",
                "proposed_value": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            },
        ],
    )
    return folder, row_fill, dropzone_json, import_csv


def _args(tmp_path: Path, dropzone_json: Path, import_csv: Path, *extra: str) -> list[str]:
    return [
        "--dropzone-json",
        str(dropzone_json),
        "--import-csv",
        str(import_csv),
        "--import-json",
        str(tmp_path / "import.json"),
        "--import-audit-csv",
        str(tmp_path / "import_audit.csv"),
        "--import-md",
        str(tmp_path / "IMPORT.md"),
        "--value-ledger-json",
        str(tmp_path / "value_ledger.json"),
        "--value-ledger-csv",
        str(tmp_path / "value_ledger.csv"),
        "--value-ledger-md",
        str(tmp_path / "VALUE_LEDGER.md"),
        "--intake-json",
        str(tmp_path / "intake.json"),
        "--intake-csv",
        str(tmp_path / "intake.csv"),
        "--intake-md",
        str(tmp_path / "INTAKE.md"),
        "--patch-gate-json",
        str(tmp_path / "patch_gate.json"),
        "--patch-gate-csv",
        str(tmp_path / "patch_gate.csv"),
        "--patch-gate-md",
        str(tmp_path / "PATCH_GATE.md"),
        "--apply-plan-json",
        str(tmp_path / "apply_plan.json"),
        "--apply-plan-csv",
        str(tmp_path / "apply_plan.csv"),
        "--apply-plan-md",
        str(tmp_path / "APPLY_PLAN.md"),
        "--out-json",
        str(tmp_path / "round.json"),
        "--out-csv",
        str(tmp_path / "round.csv"),
        "--out-md",
        str(tmp_path / "ROUND.md"),
        *extra,
    ]


def test_evidence_round_stops_before_import_apply_by_default(tmp_path: Path) -> None:
    folder, row_fill, dropzone_json, import_csv = _fixture(tmp_path)
    args = mod.parse_args(_args(tmp_path, dropzone_json, import_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["round_status"] == "ready_for_import_apply"
    assert payload["summary"]["import_ready_for_apply_count"] == 2
    assert payload["summary"]["import_applied_count"] == 0
    assert not (folder / "evidence_dropzone" / "files" / "core" / "T9001_prediction.pdb").exists()
    assert _read_csv(row_fill)[0]["target_id"] == "REQUIRED_MONOMER_001"
    assert (tmp_path / "round.json").is_file()
    assert (tmp_path / "ROUND.md").is_file()


def test_evidence_round_apply_import_surfaces_row_fill_patch_plan(tmp_path: Path) -> None:
    folder, row_fill, dropzone_json, import_csv = _fixture(tmp_path)
    args = mod.parse_args(_args(tmp_path, dropzone_json, import_csv, "--apply-import"))

    payload = mod.build_payload(args)

    assert payload["summary"]["round_status"] == "ready_for_partial_row_fill_apply"
    assert payload["summary"]["import_applied_count"] == 2
    assert payload["summary"]["intake_patch_candidate_count"] == 2
    assert payload["summary"]["patch_gate_ready_to_patch_count"] == 1
    assert payload["summary"]["apply_plan_planned_patch_count"] == 1
    assert (folder / "evidence_dropzone" / "files" / "core" / "T9001_prediction.pdb").is_file()
    assert _read_csv(row_fill)[0]["target_id"] == "REQUIRED_MONOMER_001"
