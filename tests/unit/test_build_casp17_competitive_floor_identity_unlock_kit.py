from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_identity_unlock_kit as mod


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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _import_rows() -> list[dict[str, str]]:
    base = {
        "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
        "operator_priority": "1",
        "row_rank": "1",
        "benchmark_id": "hist_REQUIRED_MONOMER_001",
        "target_id": "REQUIRED_MONOMER_001",
        "scope": "monomer",
        "source_row_fill_csv": "row_fill.csv",
        "import_kind": "value",
        "proposed_value": "",
        "evidence_ref": "",
        "operator_clearance": "",
    }
    return [
        {**base, "evidence_class": "target_identity", "template_column": "benchmark_id"},
        {**base, "evidence_class": "target_identity", "template_column": "target_id"},
        {**base, "evidence_class": "core_file", "template_column": "prediction_pdb", "import_kind": "file"},
        {**base, "evidence_class": "ablation_file", "template_column": "recursive_prediction_pdb", "import_kind": "file"},
    ]


def test_identity_unlock_kit_builds_compact_awaiting_rows(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    current_targets = tmp_path / "current.csv"
    out_csv = tmp_path / "identity.csv"
    _write_csv(import_csv, _import_rows())
    _write_csv(current_targets, [{"target_id": "T1331"}])
    args = mod.parse_args(
        [
            "--import-csv",
            str(import_csv),
            "--current-target-csv",
            str(current_targets),
            "--out-json",
            str(tmp_path / "identity.json"),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(tmp_path / "IDENTITY.md"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_unlock_status"] == "awaiting_identity"
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["awaiting_identity_count"] == 1
    assert payload["rows"][0]["identity_status"] == "awaiting_identity"
    assert payload["rows"][0]["file_actions_unlocked"] == 0
    assert "proposed_target_id_required" in payload["rows"][0]["blockers"]
    assert _read_csv(out_csv)[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert _read_json(tmp_path / "identity.json")["summary"]["row_count"] == 1


def test_identity_unlock_kit_apply_updates_import_csv(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    current_targets = tmp_path / "current.csv"
    out_csv = tmp_path / "identity.csv"
    _write_csv(import_csv, _import_rows())
    _write_csv(current_targets, [{"target_id": "T1331"}])
    _write_csv(
        out_csv,
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
        [
            "--import-csv",
            str(import_csv),
            "--current-target-csv",
            str(current_targets),
            "--out-json",
            str(tmp_path / "identity.json"),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(tmp_path / "IDENTITY.md"),
            "--apply",
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_unlock_status"] == "ready_for_import"
    assert payload["summary"]["ready_for_import_count"] == 1
    assert payload["summary"]["applied_identity_import_count"] == 2
    assert payload["summary"]["file_actions_unlocked_count"] == 2
    rows = _read_csv(import_csv)
    by_column = {row["template_column"]: row for row in rows}
    assert by_column["benchmark_id"]["proposed_value"] == "hist_T9001"
    assert by_column["target_id"]["proposed_value"] == "T9001"
    assert by_column["target_id"]["evidence_ref"] == "local/no_leak/T9001.md"
    assert by_column["target_id"]["operator_clearance"] == "ready_for_row_fill"


def test_identity_unlock_kit_blocks_current_target_and_duplicates(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    current_targets = tmp_path / "current.csv"
    out_csv = tmp_path / "identity.csv"
    rows = _import_rows()
    second = [{**row, "dropzone_id": "priority_002_REQUIRED_MONOMER_002", "operator_priority": "2"} for row in rows]
    _write_csv(import_csv, rows + second)
    _write_csv(current_targets, [{"target_id": "T1331"}])
    _write_csv(
        out_csv,
        [
            {
                "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
                "proposed_benchmark_id": "hist_T1331",
                "proposed_target_id": "T1331",
                "evidence_ref": "local/no_leak/T1331.md",
                "operator_clearance": "ready_for_row_fill",
            },
            {
                "dropzone_id": "priority_002_REQUIRED_MONOMER_002",
                "proposed_benchmark_id": "hist_T1331_dup",
                "proposed_target_id": "T1331",
                "evidence_ref": "local/no_leak/T1331_dup.md",
                "operator_clearance": "ready_for_row_fill",
            },
        ],
    )
    args = mod.parse_args(["--import-csv", str(import_csv), "--current-target-csv", str(current_targets), "--out-csv", str(out_csv)])

    payload = mod.build_payload(args)

    assert payload["summary"]["blocked_identity_count"] == 2
    assert all(row["identity_status"] == "blocked_identity" for row in payload["rows"])
    assert all("proposed_target_id_is_current_casp17_target" in row["blockers"] for row in payload["rows"])
    assert all("proposed_target_id_duplicate" in row["blockers"] for row in payload["rows"])
