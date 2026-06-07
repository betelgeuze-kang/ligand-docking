from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.casp17 import build_casp17_historical_seed_top5_candidate_pools as mod


FIELDS = [
    "seed_rank",
    "batch_slot",
    "benchmark_id",
    "target_id",
    "scope",
    "prediction_pdb",
    "native_pdb",
]


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] = FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _pdb(path: Path, atom_count: int = 3) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for index in range(1, atom_count + 1):
        lines.append(
            f"ATOM  {index:5d}  CA  ALA A{index:4d}    "
            f"{index:8.3f}{index + 1:8.3f}{index + 2:8.3f}  1.00 20.00           C\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
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
    }


def _args(tmp_path: Path, operator_csv: Path, seed_csv: Path) -> list[str]:
    return [
        "--operator-clearance-csv",
        str(operator_csv),
        "--seed-manifest-csv",
        str(seed_csv),
        "--pool-dir",
        str(tmp_path / "pools"),
        "--out-json",
        str(tmp_path / "top5.json"),
        "--out-csv",
        str(tmp_path / "top5.csv"),
        "--out-md",
        str(tmp_path / "TOP5.md"),
    ]


def test_top5_candidate_pool_generates_five_coordinate_valid_models(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    args = mod.parse_args(_args(tmp_path, operator_csv, seed_csv))
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    assert payload["summary"]["top5_candidate_pool_status"] == "top5_candidate_pool_ready_for_review"
    assert payload["summary"]["seed_row_count"] == 1
    assert payload["summary"]["candidate_model_count"] == 5
    assert payload["summary"]["complete_top5_pool_count"] == 1
    assert payload["summary"]["generated_perturbation_count"] == 4
    assert payload["rows"][0]["top5_candidate_pool_ready"] is True
    assert payload["rows"][0]["candidate_model_count"] == 5

    pool_csv = Path(payload["rows"][0]["candidate_pool_csv"])
    if not pool_csv.is_absolute():
        pool_csv = mod.ROOT / pool_csv
    with pool_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 5
    assert {item["coordinate_valid"] for item in rows} == {"True"}
    assert rows[0]["generation_method"] == "copy_selected"
    assert rows[1]["generation_method"] == "deterministic_coordinate_perturbation"

    out_payload = json.loads((tmp_path / "top5.json").read_text(encoding="utf-8"))
    assert out_payload["summary"]["claim_boundary"].startswith("Local CASP17 historical seed")


def test_top5_candidate_pool_blocks_missing_selected_source(tmp_path: Path) -> None:
    row = _base_row(tmp_path)
    row["prediction_pdb"] = str(tmp_path / "missing.pdb")
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [row])
    _write_csv(seed_csv, [row])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["top5_candidate_pool_status"] == "blocked_selected_source_missing"
    assert payload["summary"]["blocked_selected_source_count"] == 1
    assert payload["summary"]["candidate_model_count"] == 0
    assert payload["rows"][0]["pool_status"] == "blocked_selected_source_missing"
    assert "selected_source_pdb_missing_or_invalid" in payload["rows"][0]["blockers"]


def test_top5_candidate_pool_blocks_missing_operator_rows(tmp_path: Path) -> None:
    operator_csv = tmp_path / "operator.csv"
    seed_csv = tmp_path / "seed.csv"
    _write_csv(operator_csv, [])
    _write_csv(seed_csv, [])

    payload = mod.build_payload(mod.parse_args(_args(tmp_path, operator_csv, seed_csv)))

    assert payload["summary"]["top5_candidate_pool_status"] == "blocked_missing_operator_rows"
    assert payload["summary"]["seed_row_count"] == 0
    assert payload["summary"]["first_next_action"] == "provide seed operator rows"
