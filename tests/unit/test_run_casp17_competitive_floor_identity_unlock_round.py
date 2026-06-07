from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import run_casp17_competitive_floor_identity_unlock_round as mod


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


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
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
    dropzone_json = tmp_path / "dropzone.json"
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
    identity_csv = tmp_path / "identity.csv"
    return folder, dropzone_json, import_csv, current_targets, identity_csv


def _args(
    tmp_path: Path,
    dropzone_json: Path,
    import_csv: Path,
    current_targets: Path,
    identity_csv: Path,
    *extra: str,
) -> list[str]:
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
        "--current-target-csv",
        str(current_targets),
        "--identity-kit-json",
        str(tmp_path / "identity.json"),
        "--identity-kit-csv",
        str(identity_csv),
        "--identity-kit-md",
        str(tmp_path / "IDENTITY.md"),
        "--unlock-priority-json",
        str(tmp_path / "unlock.json"),
        "--unlock-priority-csv",
        str(tmp_path / "unlock.csv"),
        "--unlock-priority-md",
        str(tmp_path / "UNLOCK.md"),
        "--out-json",
        str(tmp_path / "round.json"),
        "--out-csv",
        str(tmp_path / "round.csv"),
        "--out-md",
        str(tmp_path / "ROUND.md"),
        *extra,
    ]


def test_identity_unlock_round_reports_awaiting_identity_by_default(tmp_path: Path) -> None:
    _folder, dropzone_json, import_csv, current_targets, identity_csv = _fixture(tmp_path)
    args = mod.parse_args(_args(tmp_path, dropzone_json, import_csv, current_targets, identity_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_round_status"] == "awaiting_identity"
    assert payload["summary"]["identity_awaiting_count"] == 1
    assert payload["summary"]["target_id_open_count"] == 1
    assert payload["summary"]["file_actions_waiting_on_identity_count"] == 1
    assert (tmp_path / "round.json").is_file()
    assert (tmp_path / "ROUND.md").is_file()


def test_identity_unlock_round_can_stage_ready_identity_before_import_apply(tmp_path: Path) -> None:
    folder, dropzone_json, import_csv, current_targets, identity_csv = _fixture(tmp_path)
    _write_csv(
        identity_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "proposed_benchmark_id": "hist_T9001",
                "proposed_target_id": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            }
        ],
    )
    args = mod.parse_args(_args(tmp_path, dropzone_json, import_csv, current_targets, identity_csv, "--apply-identity"))

    payload = mod.build_payload(args)

    assert payload["summary"]["identity_round_status"] == "ready_for_identity_import_apply"
    assert payload["summary"]["applied_identity_import_count"] == 2
    assert payload["summary"]["import_ready_for_apply_count"] == 2
    assert _read_csv(import_csv)[1]["proposed_value"] == "T9001"
    assert _read_csv(folder / "FIELD_VALUE_LEDGER.csv")[1]["proposed_value"] == ""


def test_identity_unlock_round_apply_import_unlocks_file_phase(tmp_path: Path) -> None:
    folder, dropzone_json, import_csv, current_targets, identity_csv = _fixture(tmp_path)
    _write_csv(
        identity_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "proposed_benchmark_id": "hist_T9001",
                "proposed_target_id": "T9001",
                "evidence_ref": "local/no_leak/T9001.md",
                "operator_clearance": "ready_for_row_fill",
            }
        ],
    )
    args = mod.parse_args(
        _args(tmp_path, dropzone_json, import_csv, current_targets, identity_csv, "--apply-identity", "--apply-import")
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["identity_round_status"] == "identity_unlocked_continue_file_sources"
    assert payload["summary"]["import_applied_count"] == 2
    assert payload["summary"]["target_id_open_count"] == 0
    assert payload["summary"]["file_actions_waiting_on_identity_count"] == 0
    assert _read_csv(folder / "FIELD_VALUE_LEDGER.csv")[1]["proposed_value"] == "T9001"
