from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_chronology_candidate_board as mod


FIELDS = [
    "benchmark_id",
    "target_id",
    "prediction_pdb",
    "native_pdb",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
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


def _pdb(path: Path, mtime: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ATOM      1  CA  ALA A   1       0.000   0.000   0.000\n", encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return str(path)


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--out-json",
        str(tmp_path / "chronology.json"),
        "--out-csv",
        str(tmp_path / "chronology.csv"),
        "--out-md",
        str(tmp_path / "CHRONOLOGY.md"),
    ]


def test_chronology_board_keeps_path_and_mtime_candidates_out_of_clearance(tmp_path: Path) -> None:
    prediction = _pdb(tmp_path / "nightly/2026-02-19-run/prediction.pdb", 200)
    native = _pdb(tmp_path / "native.pdb", 100)
    row = {
        "benchmark_id": "hist_a",
        "target_id": "HIST_A",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "prediction_created_at": "YYYY-MM-DD",
        "native_release_date": "YYYY-MM-DD",
        "prediction_generated_before_native_release": "REQUIRED_TRUE_CONFIRMATION",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["chronology_board_status"] == "operator_evidence_required"
    assert payload["summary"]["prediction_path_date_count"] == 1
    assert payload["summary"]["file_mtime_candidate_count"] == 1
    assert payload["summary"]["file_mtime_order_risk_count"] == 1
    assert payload["rows"][0]["prediction_path_date"] == "2026-02-19"
    assert payload["rows"][0]["chronology_status"] == "operator_evidence_required"
    assert "file_mtime_not_before_native_mtime" in payload["rows"][0]["blockers"]


def test_chronology_board_accepts_operator_entered_ordered_dates(tmp_path: Path) -> None:
    prediction = _pdb(tmp_path / "prediction.pdb", 1_700_000_000)
    native = _pdb(tmp_path / "native.pdb", 1_700_086_400)
    row = {
        "benchmark_id": "hist_a",
        "target_id": "HIST_A",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "prediction_created_at": "2026-02-19",
        "native_release_date": "2026-02-20",
        "prediction_generated_before_native_release": "true",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["chronology_board_status"] == "operator_chronology_ready"
    assert payload["summary"]["operator_chronology_ready_count"] == 1
    assert payload["rows"][0]["chronology_status"] == "operator_chronology_ready"


def test_chronology_board_blocks_operator_date_order_conflict(tmp_path: Path) -> None:
    prediction = _pdb(tmp_path / "prediction.pdb", 1_700_000_000)
    native = _pdb(tmp_path / "native.pdb", 1_700_086_400)
    row = {
        "benchmark_id": "hist_a",
        "target_id": "HIST_A",
        "prediction_pdb": prediction,
        "native_pdb": native,
        "prediction_created_at": "2026-02-21",
        "native_release_date": "2026-02-20",
        "prediction_generated_before_native_release": "true",
    }
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["chronology_board_status"] == "blocked_chronology_conflict"
    assert payload["summary"]["blocked_chronology_conflict_count"] == 1
    assert "operator_chronology_date_order_conflict" in payload["rows"][0]["blockers"]
