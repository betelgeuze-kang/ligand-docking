from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_calibration_field_candidates as mod


FIELDS = [
    "target_id",
    "benchmark_id",
    "scope",
    "selected_model_rank",
    "best_model_rank",
    "selected_native_metric",
    "best_native_metric",
    "selected_score",
    "best_score",
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _operator_row(**overrides: str) -> dict[str, str]:
    row = {
        "target_id": "HIST_TEST",
        "benchmark_id": "hist_seed_test",
        "scope": "monomer",
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
    }
    row.update(overrides)
    return row


def _ledger_row(**overrides: str) -> dict[str, str]:
    row = {
        "row_rank": 1,
        "target_id": "HIST_TEST",
        "benchmark_id": "hist_seed_test",
        "scope": "monomer",
        "candidate_ledger_csv": "casp17/historical_seed_calibration_candidate_ledgers/01_hist_test.csv",
        "selected_model_rank_candidate": "1",
        "best_model_rank_candidate": "2",
        "selected_native_metric_candidate": "80.000",
        "best_native_metric_candidate": "95.000",
        "selected_score_candidate": "0.420",
        "best_score_candidate": "0.510",
    }
    row.update(overrides)
    return row


def _args(tmp_path: Path, operator_csv: Path, ledger_json: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--calibration-ledger-json",
        str(ledger_json),
        "--field-dir",
        str(tmp_path / "fields"),
        "--out-json",
        str(tmp_path / "fields.json"),
        "--out-csv",
        str(tmp_path / "fields.csv"),
        "--out-md",
        str(tmp_path / "FIELDS.md"),
    ]


def test_calibration_field_candidates_propose_all_placeholder_fields(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    ledger_json = tmp_path / "ledger.json"
    _write_csv(operator_csv, [_operator_row()])
    _write_json(ledger_json, {"rows": [_ledger_row()]})

    args = mod.parse_args(_args(tmp_path, operator_csv, ledger_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["calibration_field_candidate_status"] == (
        "calibration_field_candidates_ready_for_operator_apply"
    )
    assert payload["summary"]["field_candidate_count"] == 6
    assert payload["summary"]["proposed_field_count"] == 6
    assert payload["summary"]["ready_to_apply_row_count"] == 1
    assert payload["summary"]["blocked_row_count"] == 0
    assert payload["rows"][0]["field_candidate_status"] == "calibration_field_candidates_ready_for_operator_apply"
    assert {row["candidate_status"] for row in payload["field_rows_by_target"]["HIST_TEST"]} == {"proposed"}
    assert json.loads((tmp_path / "fields.json").read_text(encoding="utf-8"))["summary"]["claim_boundary"].startswith(
        "Local CASP17"
    )


def test_calibration_field_candidates_block_missing_candidate_value(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    ledger_json = tmp_path / "ledger.json"
    _write_csv(operator_csv, [_operator_row()])
    _write_json(ledger_json, {"rows": [_ledger_row(best_score_candidate="REQUIRES_INTERNAL_SCORE")]})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, ledger_json)))

    assert payload["summary"]["calibration_field_candidate_status"] == "blocked_calibration_field_candidates"
    assert payload["summary"]["blocked_field_count"] == 1
    assert payload["summary"]["ready_to_apply_row_count"] == 0
    assert "calibration_candidate_value_missing" in payload["rows"][0]["blockers"]


def test_calibration_field_candidates_block_existing_conflict(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    ledger_json = tmp_path / "ledger.json"
    _write_csv(operator_csv, [_operator_row(best_model_rank="5")])
    _write_json(ledger_json, {"rows": [_ledger_row()]})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, ledger_json)))

    assert payload["summary"]["calibration_field_candidate_status"] == "blocked_calibration_field_candidates"
    assert payload["summary"]["conflict_field_count"] == 1
    assert payload["summary"]["proposed_field_count"] == 5
    assert "existing_calibration_value_conflict" in payload["rows"][0]["blockers"]


def test_calibration_field_candidates_block_missing_ledger(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    _write_csv(operator_csv, [_operator_row()])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, tmp_path / "missing.json")))

    assert payload["summary"]["calibration_field_candidate_status"] == "blocked_missing_calibration_ledger"
