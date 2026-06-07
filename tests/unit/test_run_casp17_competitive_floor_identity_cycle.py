from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import run_casp17_competitive_floor_identity_cycle as mod


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _base_identity_row() -> dict[str, str]:
    return {
        "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
        "operator_priority": "1",
        "row_rank": "1",
        "scope": "monomer",
        "proposed_benchmark_id": "",
        "proposed_target_id": "",
        "evidence_ref": "",
        "operator_clearance": "",
    }


def _fixture(tmp_path: Path, *, intake_ready: bool = False) -> tuple[Path, Path, Path, Path, Path]:
    folder = tmp_path / "priority_001_REQUIRED_MONOMER_001"
    row_fill = folder / "row_fill.csv"
    _write_csv(row_fill, [{"benchmark_id": "hist_REQUIRED_MONOMER_001", "target_id": "REQUIRED_MONOMER_001"}])
    _write_csv(
        folder / "FIELD_VALUE_LEDGER.csv",
        [
            {
                "template_column": "benchmark_id",
                "evidence_class": "target_identity",
                "current_value": "hist_REQUIRED_MONOMER_001",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
                "ledger_status": "awaiting_value",
                "next_action": "enter benchmark",
            },
            {
                "template_column": "target_id",
                "evidence_class": "target_identity",
                "current_value": "REQUIRED_MONOMER_001",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
                "ledger_status": "awaiting_value",
                "next_action": "enter target",
            },
        ],
    )
    target_identity = folder / "evidence_dropzone" / "target_identity"
    core = folder / "evidence_dropzone" / "files" / "core"
    base = {
        "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
        "operator_priority": 1,
        "row_rank": 1,
        "benchmark_id": "hist_REQUIRED_MONOMER_001",
        "target_id": "REQUIRED_MONOMER_001",
        "scope": "monomer",
        "source_row_fill_csv": str(row_fill),
        "dropzone_folder": str(folder / "evidence_dropzone"),
    }
    dropzone_json = tmp_path / "dropzone.json"
    _write_json(
        dropzone_json,
        {
            "summary": {"dropzone_status": "open_actions", "dropzone_count": 1},
            "rows": [
                {
                    **base,
                    "action_rank": 1,
                    "evidence_class": "target_identity",
                    "template_column": "benchmark_id",
                    "dropzone_class_folder": str(target_identity),
                    "drop_path": "",
                },
                {
                    **base,
                    "action_rank": 2,
                    "evidence_class": "target_identity",
                    "template_column": "target_id",
                    "dropzone_class_folder": str(target_identity),
                    "drop_path": "",
                },
                {
                    **base,
                    "action_rank": 3,
                    "evidence_class": "core_file",
                    "template_column": "prediction_pdb",
                    "dropzone_class_folder": str(core),
                    "drop_path": str(core / "<HISTORICAL_TARGET_ID>_prediction.pdb"),
                },
            ],
        },
    )
    import_csv = tmp_path / "import.csv"
    _write_csv(
        import_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "operator_priority": "1",
                "row_rank": "1",
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_class": "target_identity",
                "template_column": "benchmark_id",
                "source_row_fill_csv": str(row_fill),
                "dropzone_class_folder": str(target_identity),
                "import_kind": "value",
                "source_path": "",
                "drop_filename": "",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "operator_priority": "1",
                "row_rank": "1",
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_class": "target_identity",
                "template_column": "target_id",
                "source_row_fill_csv": str(row_fill),
                "dropzone_class_folder": str(target_identity),
                "import_kind": "value",
                "source_path": "",
                "drop_filename": "",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
            },
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "operator_priority": "1",
                "row_rank": "1",
                "benchmark_id": "hist_REQUIRED_MONOMER_001",
                "target_id": "REQUIRED_MONOMER_001",
                "scope": "monomer",
                "evidence_class": "core_file",
                "template_column": "prediction_pdb",
                "source_row_fill_csv": str(row_fill),
                "dropzone_class_folder": str(core),
                "import_kind": "file",
                "source_path": "",
                "drop_filename": "",
                "proposed_value": "",
                "evidence_ref": "",
                "operator_clearance": "",
            },
        ],
    )
    current_targets = tmp_path / "current_targets.csv"
    _write_csv(current_targets, [{"target_id": "T1331"}])
    intake_csv = tmp_path / "intake.csv"
    kit_csv = tmp_path / "identity.csv"
    intake_row = _base_identity_row()
    if intake_ready:
        intake_row.update(
            {
                "proposed_benchmark_id": "hist_T9001",
                "proposed_target_id": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            }
        )
    _write_csv(intake_csv, [intake_row])
    _write_csv(kit_csv, [_base_identity_row()])
    return intake_csv, dropzone_json, import_csv, current_targets, kit_csv


def _args(
    tmp_path: Path,
    intake_csv: Path,
    dropzone_json: Path,
    import_csv: Path,
    current_targets: Path,
    kit_csv: Path,
    *extra: str,
) -> list[str]:
    return [
        "--intake-csv",
        str(intake_csv),
        "--identity-sync-json",
        str(tmp_path / "sync.json"),
        "--identity-sync-csv",
        str(tmp_path / "sync.csv"),
        "--identity-sync-md",
        str(tmp_path / "SYNC.md"),
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
        "--current-target-csv",
        str(current_targets),
        "--identity-kit-json",
        str(tmp_path / "identity.json"),
        "--identity-kit-csv",
        str(kit_csv),
        "--identity-kit-md",
        str(tmp_path / "IDENTITY.md"),
        "--unlock-priority-json",
        str(tmp_path / "unlock.json"),
        "--unlock-priority-csv",
        str(tmp_path / "unlock.csv"),
        "--unlock-priority-md",
        str(tmp_path / "UNLOCK.md"),
        "--identity-round-json",
        str(tmp_path / "round.json"),
        "--identity-round-csv",
        str(tmp_path / "round.csv"),
        "--identity-round-md",
        str(tmp_path / "ROUND.md"),
        "--file-source-plan-json",
        str(tmp_path / "file_plan.json"),
        "--file-source-plan-csv",
        str(tmp_path / "file_plan.csv"),
        "--file-source-plan-md",
        str(tmp_path / "FILE_PLAN.md"),
        "--value-entry-plan-json",
        str(tmp_path / "value_plan.json"),
        "--value-entry-plan-csv",
        str(tmp_path / "value_plan.csv"),
        "--value-entry-plan-md",
        str(tmp_path / "VALUE_PLAN.md"),
        "--execution-board-json",
        str(tmp_path / "board.json"),
        "--execution-board-csv",
        str(tmp_path / "board.csv"),
        "--execution-board-md",
        str(tmp_path / "BOARD.md"),
        "--readiness-gate-json",
        str(tmp_path / "gate.json"),
        "--readiness-gate-csv",
        str(tmp_path / "gate.csv"),
        "--readiness-gate-md",
        str(tmp_path / "GATE.md"),
        "--workbench-json",
        str(tmp_path / "workbench.json"),
        "--workbench-csv",
        str(tmp_path / "workbench.csv"),
        "--workbench-md",
        str(tmp_path / "WORKBENCH.md"),
        "--out-json",
        str(tmp_path / "cycle.json"),
        "--out-csv",
        str(tmp_path / "cycle.csv"),
        "--out-md",
        str(tmp_path / "CYCLE.md"),
        *extra,
    ]


def test_identity_cycle_waits_for_missing_intake_values(tmp_path: Path) -> None:
    intake_csv, dropzone_json, import_csv, current_targets, kit_csv = _fixture(tmp_path)
    args = mod.parse_args(_args(tmp_path, intake_csv, dropzone_json, import_csv, current_targets, kit_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    by_stage = {row["stage"]: row for row in payload["rows"]}
    assert summary["identity_cycle_status"] == "awaiting_intake"
    assert summary["sync_status"] == "awaiting_intake"
    assert summary["sync_missing_field_count"] == 4
    assert by_stage["identity_sync"]["status"] == "awaiting_intake"
    assert by_stage["readiness_gate"]["status"] == "awaiting_identity"
    assert by_stage["workbench"]["status"] in {"ready_for_operator_fill", "blocked", "ready_for_win_tier_scoring"}
    assert (tmp_path / "cycle.json").is_file()
    assert (tmp_path / "CYCLE.md").is_file()
    assert _read_csv(tmp_path / "cycle.csv")[0]["stage"] == "identity_sync"


def test_identity_cycle_apply_sync_advances_to_identity_apply_review(tmp_path: Path) -> None:
    intake_csv, dropzone_json, import_csv, current_targets, kit_csv = _fixture(tmp_path, intake_ready=True)
    args = mod.parse_args(
        _args(tmp_path, intake_csv, dropzone_json, import_csv, current_targets, kit_csv, "--apply-sync")
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    by_stage = {row["stage"]: row for row in payload["rows"]}
    updated_kit = _read_csv(kit_csv)[0]
    assert summary["identity_cycle_status"] == "ready_for_identity_apply"
    assert summary["sync_status"] == "ready_to_sync"
    assert summary["sync_applied_count"] == 1
    assert summary["identity_ready_for_import_count"] == 1
    assert summary["readiness_gate_status"] == "ready_for_identity_apply"
    assert by_stage["identity_round"]["status"] == "ready_for_identity_apply"
    assert updated_kit["proposed_benchmark_id"] == "hist_T9001"
    assert updated_kit["proposed_target_id"] == "T9001"
