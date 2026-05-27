from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_calibration_candidate_ledgers as mod


FIELDS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
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


def _pdb(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n",
        encoding="utf-8",
    )
    return str(path)


def _base_row(tmp_path: Path) -> dict[str, str]:
    return {
        "seed_rank": "1",
        "batch_slot": "1",
        "benchmark_id": "hist_seed_chignolin",
        "target_id": "HIST_CHIGNOLIN",
        "scope": "monomer",
        "prediction_pdb": _pdb(tmp_path / "prediction.pdb"),
        "native_pdb": _pdb(tmp_path / "native.pdb"),
        "selected_model_rank": "REQUIRED_1_TO_5",
        "best_model_rank": "REQUIRED_1_TO_5",
        "selected_native_metric": "REQUIRED_NATIVE_METRIC",
        "best_native_metric": "REQUIRED_ORACLE_METRIC",
        "selected_score": "REQUIRED_INTERNAL_SCORE",
        "best_score": "REQUIRED_ORACLE_SCORE",
    }


def _manifest_row(row: dict[str, str], role: str, path: str, sha: str = "sha") -> dict:
    return {
        "target_id": row["target_id"],
        "benchmark_id": row["benchmark_id"],
        "scope": row["scope"],
        "role": role,
        "path": path,
        "exists": True,
        "atom_count": 1,
        "coordinate_valid": True,
        "sha256_16": sha,
        "notes": role,
    }


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path, ablation_json: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--ablation-candidate-json",
        str(ablation_json),
        "--ledger-dir",
        str(tmp_path / "ledgers"),
        "--out-json",
        str(tmp_path / "calibration.json"),
        "--out-csv",
        str(tmp_path / "calibration.csv"),
        "--out-md",
        str(tmp_path / "CALIBRATION.md"),
    ]


def test_calibration_candidate_ledgers_surface_selected_rank_but_keep_oracle_gaps(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    ablation_json = tmp_path / "ablation.json"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])
    _write_json(
        ablation_json,
        {
            "manifest_rows_by_target": {
                row["target_id"]: [
                    _manifest_row(row, "selected_prediction", row["prediction_pdb"], "predsha"),
                    _manifest_row(row, "native_reference", row["native_pdb"], "nativesha"),
                    _manifest_row(row, "same_run_step_candidate", str(tmp_path / "step10.pdb"), "step10sha"),
                ]
            }
        },
    )

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv, ablation_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["calibration_candidate_status"] == "operator_calibration_review_required"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["ledger_count"] == 1
    assert payload["summary"]["candidate_model_count"] == 2
    assert payload["summary"]["selected_model_rank_candidate_count"] == 1
    assert payload["summary"]["top5_candidate_pool_ready_count"] == 0
    assert payload["summary"]["candidate_pool_gap_count"] == 1
    assert payload["summary"]["native_oracle_metric_available_count"] == 0
    assert payload["summary"]["internal_score_available_count"] == 0
    assert payload["summary"]["open_calibration_field_count"] == 6
    assert payload["rows"][0]["selected_model_rank_candidate"] == "1"
    assert payload["rows"][0]["best_model_rank_candidate"] == "REQUIRES_NATIVE_ORACLE"
    assert "best_of_5_candidate_pool_missing" in payload["rows"][0]["blockers"]
    assert "native_oracle_metrics_required" in payload["rows"][0]["blockers"]
    assert "internal_score_candidates_required" in payload["rows"][0]["blockers"]

    ledger_path = Path(payload["rows"][0]["candidate_ledger_csv"])
    if not ledger_path.is_absolute():
        ledger_path = mod.ROOT / ledger_path
    with ledger_path.open("r", encoding="utf-8", newline="") as handle:
        ledger_rows = list(csv.DictReader(handle))
    assert {item["role"] for item in ledger_rows} == {"selected_prediction", "same_run_step_candidate"}
    assert json.loads((tmp_path / "calibration.json").read_text(encoding="utf-8"))["summary"]["claim_boundary"].startswith("Local CASP17")


def test_calibration_candidate_ledgers_count_top5_pool_ready_without_filling_metrics(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    ablation_json = tmp_path / "ablation.json"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])
    manifest_rows = [_manifest_row(row, "selected_prediction", row["prediction_pdb"], "predsha")]
    manifest_rows.extend(
        _manifest_row(row, f"candidate_{index}", str(tmp_path / f"candidate_{index}.pdb"), f"sha{index}")
        for index in range(2, 6)
    )
    _write_json(ablation_json, {"manifest_rows_by_target": {row["target_id"]: manifest_rows}})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv, ablation_json)))

    assert payload["summary"]["top5_candidate_pool_ready_count"] == 1
    assert payload["summary"]["candidate_pool_gap_count"] == 0
    assert payload["summary"]["ready_for_calibration_fill_count"] == 0
    assert payload["rows"][0]["top5_candidate_pool_ready"] is True
    assert "native_oracle_metrics_required" in payload["rows"][0]["blockers"]


def test_calibration_candidate_ledgers_block_missing_selected_prediction(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    ablation_json = tmp_path / "ablation.json"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])
    missing_selected = _manifest_row(row, "selected_prediction", str(tmp_path / "missing.pdb"), "")
    missing_selected["exists"] = False
    missing_selected["coordinate_valid"] = False
    _write_json(ablation_json, {"manifest_rows_by_target": {row["target_id"]: [missing_selected]}})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv, ablation_json)))

    assert payload["summary"]["calibration_candidate_status"] == "blocked_selected_prediction_missing"
    assert payload["summary"]["blocked_selected_prediction_count"] == 1
    assert payload["rows"][0]["ledger_status"] == "blocked_selected_prediction_missing"
    assert "selected_prediction_candidate_missing" in payload["rows"][0]["blockers"]
