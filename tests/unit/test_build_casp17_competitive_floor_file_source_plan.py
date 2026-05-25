from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_file_source_plan as mod


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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _file_rows(source_path: str = "") -> list[dict[str, str]]:
    base = {
        "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
        "operator_priority": "1",
        "row_rank": "1",
        "scope": "monomer",
        "evidence_class": "core_file",
        "source_row_fill_csv": "row_fill.csv",
        "dropzone_class_folder": "evidence_dropzone/files/core",
        "import_kind": "file",
        "source_path": source_path,
    }
    return [
        {**base, "template_column": "prediction_pdb"},
        {**base, "template_column": "native_pdb"},
        {**base, "evidence_class": "ablation_file", "template_column": "recursive_prediction_pdb"},
    ]


def _args(tmp_path: Path, import_csv: Path, identity_json: Path, current_targets: Path) -> list[str]:
    return [
        "--import-csv",
        str(import_csv),
        "--identity-kit-json",
        str(identity_json),
        "--identity-kit-csv",
        str(tmp_path / "identity.csv"),
        "--current-target-csv",
        str(current_targets),
        "--out-json",
        str(tmp_path / "plan.json"),
        "--out-csv",
        str(tmp_path / "plan.csv"),
        "--out-md",
        str(tmp_path / "PLAN.md"),
    ]


def test_file_source_plan_waits_on_identity(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    current_targets = tmp_path / "current_targets.csv"
    _write_csv(import_csv, _file_rows())
    _write_csv(current_targets, [{"target_id": "T1331"}])
    _write_json(
        identity_json,
        {
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "identity_status": "awaiting_identity",
                    "proposed_target_id": "",
                }
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json, current_targets))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["file_source_status"] == "waiting_on_identity"
    assert payload["summary"]["file_action_count"] == 3
    assert payload["summary"]["waiting_on_identity_count"] == 3
    assert payload["rows"][0]["file_source_status"] == "waiting_on_identity"
    assert _read_csv(tmp_path / "plan.csv")[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert (tmp_path / "PLAN.md").is_file()


def test_file_source_plan_builds_canonical_destinations_after_identity(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    current_targets = tmp_path / "current_targets.csv"
    _write_csv(import_csv, _file_rows())
    _write_csv(current_targets, [{"target_id": "T1331"}])
    _write_json(
        identity_json,
        {
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "identity_status": "ready_for_import",
                    "proposed_benchmark_id": "hist_T9001",
                    "proposed_target_id": "T9001",
                    "evidence_ref": "local/no_leak/T9001.md",
                    "operator_clearance": "ready_for_row_fill",
                }
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json, current_targets))

    payload = mod.build_payload(args)

    assert payload["summary"]["file_source_status"] == "awaiting_source_paths"
    assert payload["summary"]["awaiting_source_path_count"] == 3
    by_column = {row["template_column"]: row for row in payload["rows"]}
    assert by_column["prediction_pdb"]["recommended_drop_filename"] == "T9001_prediction.pdb"
    assert by_column["native_pdb"]["canonical_destination_path"] == "runs/casp17_historical_benchmark_natives_current/T9001_native.pdb"
    assert (
        by_column["recursive_prediction_pdb"]["canonical_destination_path"]
        == "runs/casp17_historical_ablation_predictions_current/recursive/T9001TS.pdb"
    )


def test_file_source_plan_blocks_current_target_source_and_accepts_pdb(tmp_path: Path) -> None:
    current_source = tmp_path / "casp17" / "targets_current" / "T1331" / "model.pdb"
    good_source = tmp_path / "historical" / "T9001_prediction.pdb"
    current_source.parent.mkdir(parents=True)
    good_source.parent.mkdir(parents=True)
    current_source.write_text("HEADER CURRENT\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    good_source.write_text("HEADER HIST\nATOM      1  CA  ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    current_targets = tmp_path / "current_targets.csv"
    rows = _file_rows(str(good_source))
    rows[1]["source_path"] = str(current_source)
    _write_csv(import_csv, rows)
    _write_csv(current_targets, [{"target_id": "T1331"}])
    _write_json(
        identity_json,
        {
            "rows": [
                {
                    "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                    "identity_status": "ready_for_import",
                    "proposed_benchmark_id": "hist_T9001",
                    "proposed_target_id": "T9001",
                    "evidence_ref": "local/no_leak/T9001.md",
                    "operator_clearance": "ready_for_row_fill",
                }
            ]
        },
    )
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json, current_targets))

    payload = mod.build_payload(args)

    by_column = {row["template_column"]: row for row in payload["rows"]}
    assert by_column["prediction_pdb"]["file_source_status"] == "ready_for_import"
    assert by_column["native_pdb"]["file_source_status"] == "blocked_current_target_source"
    assert payload["summary"]["ready_for_import_count"] == 2
    assert payload["summary"]["blocked_file_source_count"] == 1
