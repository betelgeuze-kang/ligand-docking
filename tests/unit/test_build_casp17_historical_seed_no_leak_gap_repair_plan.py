from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_no_leak_gap_repair_plan as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _dossier_row(target_id: str) -> dict[str, object]:
    return {
        "target_id": target_id,
        "benchmark_id": f"hist_seed_{target_id.lower()}",
        "scope": "monomer",
        "prediction_path_date": "2026-02-19",
        "prediction_file_mtime_date": "2026-02-20",
        "native_file_mtime_date": "2026-02-12",
        "file_mtime_prediction_before_native": False,
        "operator_required_open_fields": ",".join(mod.NO_LEAK_FIELDS),
    }


def _chronology_row(target_id: str) -> dict[str, object]:
    return {
        "target_id": target_id,
        "benchmark_id": f"hist_seed_{target_id.lower()}",
        "prediction_path_date": "2026-02-18",
        "prediction_file_mtime_date": "2026-02-20",
        "native_file_mtime_date": "2026-02-12",
        "file_mtime_prediction_before_native": False,
    }


def _args(tmp_path: Path, no_leak_json: Path, chronology_json: Path) -> list[str]:
    return [
        "--no-leak-dossiers-json",
        str(no_leak_json),
        "--chronology-board-json",
        str(chronology_json),
        "--repair-dir",
        str(tmp_path / "repair"),
        "--out-json",
        str(tmp_path / "repair.json"),
        "--out-csv",
        str(tmp_path / "repair.csv"),
        "--out-md",
        str(tmp_path / "REPAIR.md"),
    ]


def test_no_leak_gap_repair_plan_decomposes_operator_required_fields(tmp_path: Path) -> None:
    no_leak_json = tmp_path / "no_leak.json"
    chronology_json = tmp_path / "chronology.json"
    _write_json(no_leak_json, {"rows": [_dossier_row("HIST_A")]})
    _write_json(chronology_json, {"rows": [_chronology_row("HIST_A")]})

    args = mod.parse_args(_args(tmp_path, no_leak_json, chronology_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["no_leak_gap_repair_status"] == "no_leak_gap_repair_required"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["field_count"] == 10
    assert payload["summary"]["operator_required_field_count"] == 10
    assert payload["summary"]["weak_local_candidate_field_count"] == 2
    assert payload["summary"]["authoritative_candidate_field_count"] == 0
    assert payload["summary"]["chronology_field_count"] == 3
    assert payload["summary"]["negative_control_field_count"] == 3
    assert payload["summary"]["clearance_field_count"] == 4
    assert payload["summary"]["mtime_risk_row_count"] == 1
    assert payload["rows"][0]["repair_status"] == "no_leak_gap_repair_required"
    assert payload["rows"][0]["weak_local_candidate_field_count"] == 2
    assert "mtime_not_clearance_authority" in payload["rows"][0]["blockers"]

    repair_csv = Path(payload["rows"][0]["repair_csv"])
    if not repair_csv.is_absolute():
        repair_csv = mod.ROOT / repair_csv
    with repair_csv.open("r", encoding="utf-8", newline="") as handle:
        field_rows = list(csv.DictReader(handle))
    assert len(field_rows) == 10
    by_field = {row["field_name"]: row for row in field_rows}
    assert by_field["prediction_created_at"]["weak_local_candidate_value"] == "2026-02-18"
    assert by_field["prediction_created_at"]["authoritative_candidate_value"] == ""
    assert by_field["native_release_date"]["weak_local_candidate_source"] == (
        "native_file_mtime_not_release_authority"
    )
    assert by_field["leakage_clearance"]["repair_status"] == "operator_evidence_required"
    assert all(row["operator_required"] == "True" for row in field_rows)

    written = json.loads((tmp_path / "repair.json").read_text(encoding="utf-8"))
    assert written["summary"]["claim_boundary"].startswith("Local CASP17 historical seed no-leak")


def test_no_leak_gap_repair_plan_blocks_missing_inputs(tmp_path: Path) -> None:
    payload = mod.build_payload(
        mod.parse_args(_args(tmp_path, tmp_path / "missing_no_leak.json", tmp_path / "missing_chronology.json"))
    )

    assert payload["summary"]["no_leak_gap_repair_status"] == "blocked_missing_input"
    assert "no_leak_dossiers_json_missing" in payload["summary"]["input_blockers"]
    assert "chronology_board_json_missing" in payload["summary"]["input_blockers"]
