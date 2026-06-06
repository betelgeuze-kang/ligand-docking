from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


HISTORICAL_COLUMNS = [
    "benchmark_id",
    "target_id",
    "scope",
    "split",
    "prediction_pdb",
    "native_pdb",
    "leakage_clearance",
    "prediction_method",
    "prediction_created_at",
    "native_release_date",
    "prediction_generated_before_native_release",
    "public_template_or_native_used_for_prediction",
    "other_team_model_used",
    "post_release_information_used",
    "current_casp17_target",
    "operator_clearance",
    "recursive_prediction_pdb",
    "scored_prediction_pdb",
    "sidechain_scaffold_prediction_pdb",
    "sidechain_repacked_prediction_pdb",
    "sidechain_completed_prediction_pdb",
    "steric_relaxed_prediction_pdb",
    "rotamer_minimized_prediction_pdb",
    "polar_refined_prediction_pdb",
    "forcefield_minimized_prediction_pdb",
    "statistical_rotamer_prediction_pdb",
]

CALIBRATION_COLUMNS = [
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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "MODEL 1",
                "ATOM      1 CA   ALA A   1       0.000   0.000   0.000  1.00 80.00           C  ",
                "ATOM      2 CB   ALA A   1       1.500   0.000   0.000  1.00 80.00           C  ",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _historical_row(tmp_path: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for column in ["prediction_pdb", "native_pdb", *HISTORICAL_COLUMNS[16:]]:
        path = tmp_path / "pdbs" / f"{column}.pdb"
        _write_pdb(path)
        files[column] = str(path)
    return {
        "benchmark_id": "hist_local_001",
        "target_id": "HIST001",
        "scope": "monomer",
        "split": "historical",
        **files,
        "leakage_clearance": "no_leak",
        "prediction_method": "internal_physics_historical_fixture",
        "prediction_created_at": "2024-01-01",
        "native_release_date": "2024-06-01",
        "prediction_generated_before_native_release": "true",
        "public_template_or_native_used_for_prediction": "false",
        "other_team_model_used": "false",
        "post_release_information_used": "false",
        "current_casp17_target": "false",
        "operator_clearance": "no_leak",
    }


def test_build_casp17_win_tier_benchmark_activation_packet_writes_active_csvs_on_pass(tmp_path: Path) -> None:
    import_json = tmp_path / "import.json"
    watchlist_json = tmp_path / "watchlist.json"
    historical_csv = tmp_path / "historical_candidate.csv"
    calibration_csv = tmp_path / "calibration_candidate.csv"
    active_historical = tmp_path / "active_historical.csv"
    active_calibration = tmp_path / "active_calibration.csv"

    _write_json(import_json, {"summary": {"import_status": "pass"}})
    _write_json(watchlist_json, {"rows": [{"target_id": "T1331", "human_open": True}]})
    _write_csv(historical_csv, [_historical_row(tmp_path)], HISTORICAL_COLUMNS)
    _write_csv(
        calibration_csv,
        [
            {
                "benchmark_id": "hist_local_001",
                "scope": "monomer",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.82",
                "best_native_metric": "0.82",
                "selected_score": "0.61",
                "best_score": "0.61",
                "leakage_clearance": "no_leak",
            }
        ],
        CALIBRATION_COLUMNS,
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_activation_packet.py"),
            "--operator-import-json",
            str(import_json),
            "--historical-manifest-candidate-csv",
            str(historical_csv),
            "--calibration-candidate-csv",
            str(calibration_csv),
            "--target-watchlist-json",
            str(watchlist_json),
            "--out-historical-manifest-csv",
            str(active_historical),
            "--out-calibration-csv",
            str(active_calibration),
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
    assert payload["summary"]["activation_status"] == "pass"
    assert payload["summary"]["active_files_written"] is True
    assert payload["summary"]["validated_historical_row_count"] == 1
    assert payload["summary"]["validated_calibration_row_count"] == 1
    assert active_historical.exists()
    assert active_calibration.exists()
    assert "hist_local_001" in active_historical.read_text(encoding="utf-8")


def test_build_casp17_win_tier_benchmark_activation_packet_blocks_current_target_and_does_not_write_active(
    tmp_path: Path,
) -> None:
    import_json = tmp_path / "import.json"
    watchlist_json = tmp_path / "watchlist.json"
    historical_csv = tmp_path / "historical_candidate.csv"
    calibration_csv = tmp_path / "calibration_candidate.csv"
    active_historical = tmp_path / "active_historical.csv"

    row = _historical_row(tmp_path)
    row["target_id"] = "T1331"
    _write_json(import_json, {"summary": {"import_status": "pass"}})
    _write_json(watchlist_json, {"rows": [{"target_id": "T1331", "human_open": True}]})
    _write_csv(historical_csv, [row], HISTORICAL_COLUMNS)
    _write_csv(
        calibration_csv,
        [
            {
                "benchmark_id": "hist_local_001",
                "scope": "monomer",
                "selected_model_rank": "1",
                "best_model_rank": "1",
                "selected_native_metric": "0.82",
                "best_native_metric": "0.82",
                "selected_score": "0.61",
                "best_score": "0.61",
                "leakage_clearance": "no_leak",
            }
        ],
        CALIBRATION_COLUMNS,
    )

    result = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_win_tier_benchmark_activation_packet.py"),
            "--operator-import-json",
            str(import_json),
            "--historical-manifest-candidate-csv",
            str(historical_csv),
            "--calibration-candidate-csv",
            str(calibration_csv),
            "--target-watchlist-json",
            str(watchlist_json),
            "--out-historical-manifest-csv",
            str(active_historical),
            "--out-calibration-csv",
            str(tmp_path / "active_calibration.csv"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    payload = json.loads((tmp_path / "packet.json").read_text(encoding="utf-8"))
    assert result.returncode == 2
    assert payload["summary"]["activation_status"] == "blocked"
    assert "historical_candidate_rows_blocked" in payload["summary"]["blockers"]
    assert "current_casp17_target_not_allowed" in payload["historical_row_blockers"][0]["blockers"]
    assert not active_historical.exists()
