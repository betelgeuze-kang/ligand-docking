from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_competitive_floor_value_entry_plan as mod


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


def _rows() -> list[dict[str, str]]:
    base = {
        "dropzone_id": "priority_001_REQUIRED_MONOMER_001",
        "operator_priority": "1",
        "row_rank": "1",
        "scope": "monomer",
        "source_row_fill_csv": "row_fill.csv",
        "import_kind": "value",
        "proposed_value": "",
        "expected_value_rule": "non-placeholder cleared value",
        "evidence_ref": "",
        "operator_clearance": "",
    }
    return [
        {
            **base,
            "evidence_class": "target_identity",
            "template_column": "benchmark_id",
            "expected_value_rule": "cleared historical non-current identifier",
        },
        {
            **base,
            "evidence_class": "target_identity",
            "template_column": "target_id",
            "expected_value_rule": "cleared historical non-current identifier",
        },
        {
            **base,
            "evidence_class": "provenance",
            "template_column": "current_casp17_target",
            "expected_value_rule": "false",
        },
        {
            **base,
            "evidence_class": "calibration",
            "template_column": "selected_model_rank",
            "expected_value_rule": "integer 1..5",
        },
    ]


def _args(tmp_path: Path, import_csv: Path, identity_json: Path) -> list[str]:
    return [
        "--import-csv",
        str(import_csv),
        "--identity-kit-json",
        str(identity_json),
        "--identity-kit-csv",
        str(tmp_path / "identity.csv"),
        "--out-json",
        str(tmp_path / "plan.json"),
        "--out-csv",
        str(tmp_path / "plan.csv"),
        "--out-md",
        str(tmp_path / "PLAN.md"),
    ]


def test_value_entry_plan_waits_on_identity(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    _write_csv(import_csv, _rows())
    _write_json(
        identity_json,
        {"rows": [{"dropzone_id": "priority_001_REQUIRED_MONOMER_001", "identity_status": "awaiting_identity"}]},
    )
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json))

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["value_entry_status"] == "waiting_on_identity"
    assert payload["summary"]["value_action_count"] == 4
    assert payload["summary"]["waiting_on_identity_count"] == 4
    assert payload["rows"][0]["value_entry_status"] == "waiting_on_identity"
    assert _read_csv(tmp_path / "plan.csv")[0]["dropzone_id"] == "priority_001_REQUIRED_MONOMER_001"
    assert (tmp_path / "PLAN.md").is_file()


def test_value_entry_plan_uses_identity_kit_recommendations(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    rows = _rows()
    rows[2]["proposed_value"] = "false"
    rows[2]["operator_clearance"] = "ready_for_row_fill"
    rows[2]["evidence_ref"] = "local/no_leak/T9001.md"
    rows[3]["proposed_value"] = "3"
    rows[3]["operator_clearance"] = "ready_for_row_fill"
    rows[3]["evidence_ref"] = "local/calibration/T9001.md"
    _write_csv(import_csv, rows)
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
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json))

    payload = mod.build_payload(args)

    assert payload["summary"]["value_entry_status"] == "ready_for_identity_apply"
    assert payload["summary"]["ready_from_identity_kit_count"] == 2
    assert payload["summary"]["ready_for_import_count"] == 2
    by_column = {row["template_column"]: row for row in payload["rows"]}
    assert by_column["benchmark_id"]["recommended_value"] == "hist_T9001"
    assert by_column["target_id"]["recommended_value"] == "T9001"
    assert by_column["current_casp17_target"]["value_entry_status"] == "ready_for_import"


def test_value_entry_plan_blocks_invalid_values(tmp_path: Path) -> None:
    import_csv = tmp_path / "import.csv"
    identity_json = tmp_path / "identity.json"
    rows = _rows()
    rows[0]["proposed_value"] = "hist_T9001"
    rows[0]["operator_clearance"] = "ready_for_row_fill"
    rows[0]["evidence_ref"] = "local/no_leak/T9001.md"
    rows[1]["proposed_value"] = "T9001"
    rows[1]["operator_clearance"] = "ready_for_row_fill"
    rows[1]["evidence_ref"] = "local/no_leak/T9001.md"
    rows[2]["proposed_value"] = "true"
    rows[2]["operator_clearance"] = "ready_for_row_fill"
    rows[2]["evidence_ref"] = "local/no_leak/T9001.md"
    rows[3]["proposed_value"] = "9"
    rows[3]["operator_clearance"] = "ready_for_row_fill"
    rows[3]["evidence_ref"] = "local/calibration/T9001.md"
    _write_csv(import_csv, rows)
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
    args = mod.parse_args(_args(tmp_path, import_csv, identity_json))

    payload = mod.build_payload(args)

    by_column = {row["template_column"]: row for row in payload["rows"]}
    assert by_column["current_casp17_target"]["value_entry_status"] == "blocked_invalid_value"
    assert by_column["selected_model_rank"]["value_entry_status"] == "blocked_invalid_value"
    assert payload["summary"]["blocked_value_count"] == 2
