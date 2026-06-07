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


def test_model_selection_calibration_blocks_without_historical_or_calibration_csv(tmp_path: Path) -> None:
    score = tmp_path / "score.json"
    ranked = tmp_path / "ranked.json"
    historical = tmp_path / "historical.json"
    _write_json(
        score,
        {
            "summary": {
                "score_record_status": "pass",
                "target_count": 2,
                "score_record_count": 2,
                "qscore_multichain_count": 1,
                "multichain_target_count": 1,
            }
        },
    )
    _write_json(
        ranked,
        {
            "summary": {
                "ranked_depth_status": "pass",
                "target_count": 2,
                "pass_count": 2,
                "candidate_gate_pass_count": 10,
                "candidate_gate_total_count": 10,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "blocked",
                "benchmark_count": 0,
                "sequence_exact_match_count": 0,
                "chain_exact_match_count": 0,
                "manifest_blockers": "manifest_missing",
            }
        },
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_packet.py"),
            "--score-record-json",
            str(score),
            "--ranked-depth-json",
            str(ranked),
            "--historical-benchmark-json",
            str(historical),
            "--calibration-csv",
            str(tmp_path / "missing_calibration.csv"),
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
    rows = {row["calibration_dimension"]: row for row in payload["rows"]}

    assert payload["summary"]["calibration_status"] == "blocked"
    assert payload["summary"]["score_record_coverage_status"] == "pass"
    assert payload["summary"]["qscore_record_coverage_status"] == "pass"
    assert payload["summary"]["ranked_candidate_depth_status"] == "pass"
    assert payload["summary"]["historical_exactness_status"] == "blocked"
    assert payload["summary"]["calibration_rows_status"] == "blocked"
    assert "calibration_csv_missing" in rows["calibration_rows"]["blockers"]


def test_model_selection_calibration_passes_no_leak_rows(tmp_path: Path) -> None:
    score = tmp_path / "score.json"
    ranked = tmp_path / "ranked.json"
    historical = tmp_path / "historical.json"
    calibration = tmp_path / "calibration.csv"
    _write_json(
        score,
        {
            "summary": {
                "score_record_status": "pass",
                "target_count": 2,
                "score_record_count": 2,
                "qscore_multichain_count": 1,
                "multichain_target_count": 1,
            }
        },
    )
    _write_json(
        ranked,
        {
            "summary": {
                "ranked_depth_status": "pass",
                "target_count": 2,
                "pass_count": 2,
                "candidate_gate_pass_count": 10,
                "candidate_gate_total_count": 10,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "pass",
                "benchmark_count": 2,
                "sequence_exact_match_count": 2,
                "chain_exact_match_count": 2,
            }
        },
    )
    _write_calibration_csv(
        calibration,
        [
            {
                "benchmark_id": "hist_T9001",
                "scope": "monomer",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.91",
                "best_native_metric": "0.91",
                "selected_score": "0.72",
                "best_score": "0.72",
                "leakage_clearance": "no_leak",
            },
            {
                "benchmark_id": "hist_H9002",
                "scope": "complex",
                "selected_model_rank": "2",
                "best_model_rank": "1",
                "selected_native_metric": "0.60",
                "best_native_metric": "0.62",
                "selected_score": "0.65",
                "best_score": "0.63",
                "leakage_clearance": "no_leak",
            },
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_packet.py"),
            "--score-record-json",
            str(score),
            "--ranked-depth-json",
            str(ranked),
            "--historical-benchmark-json",
            str(historical),
            "--calibration-csv",
            str(calibration),
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

    assert payload["summary"]["calibration_status"] == "pass"
    assert payload["summary"]["calibration_pass_count"] == 2
    assert payload["summary"]["monomer_calibration_pass_count"] == 1
    assert payload["summary"]["complex_calibration_pass_count"] == 1
    assert payload["summary"]["top1_selected_best_count"] == 1
    assert payload["summary"]["score_order_agree_count"] == 2
    assert payload["summary"]["mean_selection_loss"] == 0.01


def test_model_selection_calibration_blocks_selection_loss_and_score_order(tmp_path: Path) -> None:
    score = tmp_path / "score.json"
    ranked = tmp_path / "ranked.json"
    historical = tmp_path / "historical.json"
    calibration = tmp_path / "calibration.csv"
    _write_json(score, {"summary": {"score_record_status": "pass", "target_count": 1, "score_record_count": 1}})
    _write_json(
        ranked,
        {
            "summary": {
                "ranked_depth_status": "pass",
                "target_count": 1,
                "pass_count": 1,
                "candidate_gate_pass_count": 5,
                "candidate_gate_total_count": 5,
            }
        },
    )
    _write_json(
        historical,
        {
            "summary": {
                "historical_benchmark_status": "pass",
                "benchmark_count": 1,
                "sequence_exact_match_count": 1,
                "chain_exact_match_count": 1,
            }
        },
    )
    _write_calibration_csv(
        calibration,
        [
            {
                "benchmark_id": "hist_T9001",
                "scope": "monomer",
                "selected_model_rank": "5",
                "best_model_rank": "1",
                "selected_native_metric": "0.40",
                "best_native_metric": "0.90",
                "selected_score": "0.10",
                "best_score": "0.80",
                "leakage_clearance": "no_leak",
            }
        ],
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_model_selection_calibration_packet.py"),
            "--score-record-json",
            str(score),
            "--ranked-depth-json",
            str(ranked),
            "--historical-benchmark-json",
            str(historical),
            "--calibration-csv",
            str(calibration),
            "--min-calibration-rows",
            "1",
            "--min-complex-rows",
            "0",
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
    row = payload["calibration_rows"][0]

    assert payload["summary"]["calibration_status"] == "blocked"
    assert row["calibration_row_status"] == "blocked"
    assert "selection_loss_above_threshold" in row["blockers"]
    assert "score_order_disagrees_with_native_best" in row["blockers"]
