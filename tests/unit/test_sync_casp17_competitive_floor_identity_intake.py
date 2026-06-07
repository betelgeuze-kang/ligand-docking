from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import sync_casp17_competitive_floor_identity_intake as mod


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


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _base_row() -> dict[str, str]:
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


def _args(tmp_path: Path, intake_csv: Path, kit_csv: Path, *extra: str) -> list[str]:
    return [
        "--intake-csv",
        str(intake_csv),
        "--kit-csv",
        str(kit_csv),
        "--out-json",
        str(tmp_path / "sync.json"),
        "--out-csv",
        str(tmp_path / "sync.csv"),
        "--out-md",
        str(tmp_path / "SYNC.md"),
        *extra,
    ]


def test_identity_intake_sync_waits_for_intake_values(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    kit_csv = tmp_path / "kit.csv"
    _write_csv(intake_csv, [_base_row()])
    _write_csv(kit_csv, [_base_row()])
    args = mod.parse_args(_args(tmp_path, intake_csv, kit_csv))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_intake_sync_status"] == "awaiting_intake"
    assert payload["summary"]["awaiting_intake_count"] == 1
    assert payload["summary"]["missing_field_count"] == 4
    assert _read_csv(tmp_path / "sync.csv")[0]["sync_status"] == "awaiting_intake"
    assert _read_json(tmp_path / "sync.json")["summary"]["row_count"] == 1


def test_identity_intake_sync_apply_updates_kit_csv(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    kit_csv = tmp_path / "kit.csv"
    intake = {
        **_base_row(),
        "proposed_benchmark_id": "hist_T9001",
        "proposed_target_id": "T9001",
        "evidence_ref": "local/no_leak/T9001.md",
        "operator_clearance": "ready_for_row_fill",
    }
    _write_csv(intake_csv, [intake])
    _write_csv(kit_csv, [_base_row()])
    args = mod.parse_args(_args(tmp_path, intake_csv, kit_csv, "--apply"))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["identity_intake_sync_status"] == "ready_to_sync"
    assert payload["summary"]["ready_to_sync_count"] == 1
    assert payload["summary"]["applied_sync_count"] == 1
    updated = _read_csv(kit_csv)[0]
    assert updated["proposed_benchmark_id"] == "hist_T9001"
    assert updated["proposed_target_id"] == "T9001"
    assert updated["operator_clearance"] == "ready_for_row_fill"


def test_identity_intake_sync_marks_synced_rows(tmp_path: Path) -> None:
    intake_csv = tmp_path / "intake.csv"
    kit_csv = tmp_path / "kit.csv"
    synced = {
        **_base_row(),
        "proposed_benchmark_id": "hist_T9001",
        "proposed_target_id": "T9001",
        "evidence_ref": "local/no_leak/T9001.md",
        "operator_clearance": "ready_for_row_fill",
    }
    _write_csv(intake_csv, [synced])
    _write_csv(kit_csv, [synced])
    args = mod.parse_args(_args(tmp_path, intake_csv, kit_csv))

    payload = mod.build_payload(args)

    assert payload["summary"]["identity_intake_sync_status"] == "synced"
    assert payload["summary"]["synced_count"] == 1
    assert payload["summary"]["kit_mismatch_count"] == 0
