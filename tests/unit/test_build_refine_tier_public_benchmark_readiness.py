from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.product import build_refine_tier_public_benchmark_readiness as mod


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=mod.REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _ready_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    proxy = [-9.0, -8.5, -8.0, -7.5, -7.0, -6.5, -6.0, -5.5]
    exp = [-10.0, -9.3, -8.7, -8.1, -7.2, -6.9, -6.1, -5.4]
    for idx, (pred, ref) in enumerate(zip(proxy, exp, strict=True)):
        rows.append(
            {
                "benchmark_id": f"curated_{idx:03d}",
                "target_id": f"T{idx:03d}",
                "benchmark_family": "pdbbind_core_refine_tier_v1",
                "split": "fit" if idx < 5 else "holdout",
                "provenance_kind": "operator_curated_public",
                "provenance_id": f"PDB:{idx:04d}",
                "license_ok": "true",
                "external_engine_calls": 0,
                "pose_rmsd_A": 1.2,
                "dockq": 0.65,
                "lddt_pli": 0.82,
                "deltaG_mm_gbsa_kcal_mol": pred,
                "deltaG_experimental_kcal_mol": ref,
            }
        )
    return rows


def test_missing_input_blocks_without_external_mutation(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    payload = mod.build_refine_tier_public_benchmark_readiness(input_csv=missing)
    summary = payload["summary"]

    assert summary["status"] == "blocked_refine_tier_public_benchmark_readiness"
    assert summary["claim_grade_public_benchmark_ready"] is False
    assert summary["external_state_mutated"] is False
    assert "input_csv_missing" in summary["blockers"]


def test_ready_rows_pass_claim_grade_public_benchmark_gate(tmp_path: Path) -> None:
    csv_path = tmp_path / "ready.csv"
    _write_rows(csv_path, _ready_rows())

    payload = mod.build_refine_tier_public_benchmark_readiness(input_csv=csv_path)
    summary = payload["summary"]

    assert summary["status"] == "refine_tier_public_benchmark_ready"
    assert summary["claim_grade_public_benchmark_ready"] is True
    assert summary["valid_row_count"] == 8
    assert summary["pose_metric_pass_count"] == 8
    assert summary["free_energy_pair_count"] == 8
    assert summary["fit_split_present"] is True
    assert summary["holdout_or_test_split_present"] is True
    assert float(summary["free_energy_spearman"]) > 0.9


def test_external_engine_and_missing_provenance_block(tmp_path: Path) -> None:
    rows = _ready_rows()
    rows[0]["external_engine_calls"] = 1
    rows[1]["provenance_id"] = ""
    csv_path = tmp_path / "blocked.csv"
    _write_rows(csv_path, rows)

    payload = mod.build_refine_tier_public_benchmark_readiness(input_csv=csv_path)
    summary = payload["summary"]
    row_blockers = ";".join(str(row["blockers"]) for row in payload["rows"])

    assert summary["claim_grade_public_benchmark_ready"] is False
    assert "insufficient_valid_rows" in summary["blockers"]
    assert "external_engine_calls_present" in row_blockers
    assert "provenance_missing_or_unaccepted" in row_blockers


def test_cli_writes_json_csv_and_markdown(tmp_path: Path) -> None:
    input_csv = tmp_path / "ready.csv"
    out_json = tmp_path / "out.json"
    out_csv = tmp_path / "out.csv"
    out_md = tmp_path / "out.md"
    _write_rows(input_csv, _ready_rows())

    mod.main(
        [
            "--input-csv",
            str(input_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["claim_grade_public_benchmark_ready"] is True
    assert out_csv.read_text(encoding="utf-8").startswith("benchmark_id,")
    assert "Refine Tier Public Benchmark Readiness" in out_md.read_text(encoding="utf-8")
