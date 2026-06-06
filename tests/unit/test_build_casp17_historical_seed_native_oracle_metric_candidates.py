from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_native_oracle_metric_candidates as mod


FIELDS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
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


def _pdb(path: Path, perturb: float = 0.0) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    coords = [
        (0.0, 0.0, 0.0),
        (1.5, 0.2, 0.4),
        (2.6, 1.1, 0.8),
        (3.1, 1.8, 1.7),
        (4.0, 2.4, 2.2),
    ]
    lines = []
    for index, (x, y, z) in enumerate(coords, start=1):
        lines.append(
            f"ATOM  {index:5d}  CA  ALA A{index:4d}    "
            f"{x + perturb * index:8.3f}{y:8.3f}{z:8.3f}  1.00 50.00           C\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return str(path)


def _candidate(target_id: str, path: str, rank: int, role: str) -> dict:
    return {
        "target_id": target_id,
        "benchmark_id": "hist_seed_test",
        "scope": "monomer",
        "candidate_rank": rank,
        "role": role,
        "path": path,
        "exists": True,
        "atom_count": 5,
        "coordinate_valid": True,
        "sha256_16": f"sha{rank}",
        "notes": role,
    }


def _args(tmp_path: Path, seed_csv: Path, ledger_json: Path) -> list[str]:
    return [
        "--seed-manifest-csv",
        str(seed_csv),
        "--calibration-ledger-json",
        str(ledger_json),
        "--metric-dir",
        str(tmp_path / "metrics"),
        "--out-json",
        str(tmp_path / "metrics.json"),
        "--out-csv",
        str(tmp_path / "metrics.csv"),
        "--out-md",
        str(tmp_path / "METRICS.md"),
    ]


def test_native_oracle_metric_candidates_score_selected_and_best(tmp_path: Path) -> None:
    target_id = "HIST_TEST"
    native_pdb = _pdb(tmp_path / "native.pdb")
    seed_csv = tmp_path / "seed.csv"
    _write_csv(
        seed_csv,
        [
            {
                "benchmark_id": "hist_seed_test",
                "target_id": target_id,
                "scope": "monomer",
                "split": "calibration",
                "prediction_pdb": str(tmp_path / "model_1.pdb"),
                "native_pdb": native_pdb,
            }
        ],
    )
    candidates = [
        _candidate(target_id, _pdb(tmp_path / "model_1.pdb", perturb=2.50), 1, "selected_prediction"),
        _candidate(target_id, _pdb(tmp_path / "model_2.pdb", perturb=0.00), 2, "deterministic_perturbation_2"),
        _candidate(target_id, _pdb(tmp_path / "model_3.pdb", perturb=0.15), 3, "deterministic_perturbation_3"),
        _candidate(target_id, _pdb(tmp_path / "model_4.pdb", perturb=0.18), 4, "deterministic_perturbation_4"),
        _candidate(target_id, _pdb(tmp_path / "model_5.pdb", perturb=0.21), 5, "deterministic_perturbation_5"),
    ]
    ledger_json = tmp_path / "calibration.json"
    _write_json(ledger_json, {"candidate_rows_by_target": {target_id: candidates}})

    args = mod.parse_args(_args(tmp_path, seed_csv, ledger_json))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["native_metric_candidate_status"] == "native_oracle_metric_candidates_ready_for_review"
    assert payload["summary"]["candidate_count"] == 5
    assert payload["summary"]["metric_candidate_count"] == 5
    assert payload["summary"]["top5_native_metric_ready_count"] == 1
    assert payload["summary"]["selected_native_metric_candidate_count"] == 1
    assert payload["summary"]["best_native_metric_candidate_count"] == 1
    assert payload["summary"]["blocked_candidate_input_count"] == 0
    assert payload["rows"][0]["best_model_rank_candidate"] == "2"
    assert float(payload["rows"][0]["best_native_metric_candidate"]) >= float(
        payload["rows"][0]["selected_native_metric_candidate"]
    )
    assert json.loads((tmp_path / "metrics.json").read_text(encoding="utf-8"))["summary"]["claim_boundary"].startswith(
        "Local CASP17"
    )


def test_native_oracle_metric_candidates_block_missing_native(tmp_path: Path) -> None:
    target_id = "HIST_TEST"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(
        seed_csv,
        [
            {
                "benchmark_id": "hist_seed_test",
                "target_id": target_id,
                "scope": "monomer",
                "split": "calibration",
                "prediction_pdb": str(tmp_path / "model_1.pdb"),
                "native_pdb": str(tmp_path / "missing_native.pdb"),
            }
        ],
    )
    candidates = [
        _candidate(
            target_id,
            _pdb(tmp_path / f"model_{rank}.pdb"),
            rank,
            "selected_prediction" if rank == 1 else f"deterministic_perturbation_{rank}",
        )
        for rank in range(1, 6)
    ]
    ledger_json = tmp_path / "calibration.json"
    _write_json(ledger_json, {"candidate_rows_by_target": {target_id: candidates}})

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, seed_csv, ledger_json)))

    assert payload["summary"]["native_metric_candidate_status"] == "blocked_native_metric_inputs"
    assert payload["summary"]["blocked_candidate_input_count"] == 1
    assert payload["rows"][0]["metric_status"] == "blocked_native_metric_inputs"
    assert "native_pdb_missing" in payload["rows"][0]["blockers"]


def test_native_oracle_metric_candidates_block_missing_ledger_or_rows(tmp_path: Path) -> None:
    seed_csv = tmp_path / "seed.csv"
    _write_csv(seed_csv, [])
    missing_payload = mod.build_payload(mod.parse_args(_args(tmp_path, seed_csv, tmp_path / "missing.json")))
    assert missing_payload["summary"]["native_metric_candidate_status"] == "blocked_missing_calibration_ledger"

    empty_json = tmp_path / "empty.json"
    _write_json(empty_json, {"candidate_rows_by_target": {}})
    empty_payload = mod.build_payload(mod.parse_args(_args(tmp_path, seed_csv, empty_json)))
    assert empty_payload["summary"]["native_metric_candidate_status"] == "blocked_missing_candidate_rows"
