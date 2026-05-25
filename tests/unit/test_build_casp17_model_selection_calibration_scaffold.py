from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_calibration_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "benchmark_id",
        "scope",
        "selected_model_rank",
        "best_model_rank",
        "selected_native_metric",
        "best_native_metric",
        "selected_score",
        "best_score",
        "leakage_clearance",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_calibration_scaffold_blocks_without_historical_or_existing_csv(tmp_path: Path) -> None:
    historical = tmp_path / "historical.json"
    _write_json(historical, {"summary": {"historical_benchmark_status": "blocked", "benchmark_count": 0}, "rows": []})

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_scaffold.py"),
            "--historical-benchmark-json",
            str(historical),
            "--existing-calibration-csv",
            str(tmp_path / "missing.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["source_mode"] == "placeholder_required_inputs"
    assert payload["summary"]["scaffold_status"] == "blocked"
    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["ready_count"] == 0
    assert payload["summary"]["monomer_candidate_count"] == 1
    assert payload["summary"]["complex_candidate_count"] == 1
    assert "existing_calibration_csv_missing" in payload["summary"]["existing_csv_blockers"]
    assert all(row["calibration_ready_status"] == "blocked" for row in payload["rows"])


def test_calibration_scaffold_uses_historical_pass_rows_but_requires_oracle_metrics(tmp_path: Path) -> None:
    historical = tmp_path / "historical.json"
    _write_json(
        historical,
        {
            "summary": {"historical_benchmark_status": "pass", "benchmark_count": 1},
            "rows": [
                {
                    "benchmark_status": "pass",
                    "benchmark_id": "hist_T9001",
                    "scope": "monomer",
                    "leakage_clearance": "no_leak",
                }
            ],
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_scaffold.py"),
            "--historical-benchmark-json",
            str(historical),
            "--existing-calibration-csv",
            str(tmp_path / "missing.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    row = payload["rows"][0]

    assert payload["summary"]["source_mode"] == "historical_benchmark_rows"
    assert payload["summary"]["candidate_count"] == 1
    assert row["benchmark_id"] == "hist_T9001"
    assert row["leakage_clearance"] == "no_leak"
    assert row["calibration_ready_status"] == "blocked"
    assert "selected_model_rank_required_1_to_5" in row["blockers"]
    assert "selected_native_metric_required_numeric" in row["blockers"]


def test_calibration_scaffold_accepts_ready_existing_csv(tmp_path: Path) -> None:
    historical = tmp_path / "historical.json"
    existing = tmp_path / "calibration.csv"
    _write_json(historical, {"summary": {"historical_benchmark_status": "pass", "benchmark_count": 2}, "rows": []})
    _write_calibration_csv(
        existing,
        [
            {
                "benchmark_id": "hist_T9001",
                "scope": "monomer",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.92",
                "best_native_metric": "0.92",
                "selected_score": "0.70",
                "best_score": "0.70",
                "leakage_clearance": "no_leak",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_scaffold.py"),
            "--historical-benchmark-json",
            str(historical),
            "--existing-calibration-csv",
            str(existing),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))

    assert payload["summary"]["source_mode"] == "existing_calibration_csv"
    assert payload["summary"]["scaffold_status"] == "ready"
    assert payload["summary"]["ready_count"] == 1
    assert payload["rows"][0]["calibration_ready_status"] == "ready"
    assert payload["rows"][0]["blockers"] == ""
