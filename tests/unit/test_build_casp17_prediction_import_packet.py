from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, resseq: int, b_factor: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}ALA A{resseq:4d}    "
        f"{float(serial):8.3f}{1.000:8.3f}{1.000:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def _write_intake(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_id",
        "target_name",
        "lane",
        "submission_format",
        "deadline_class",
        "release_date",
        "due_date",
        "sequence_path",
        "stoichiometry",
        "ligand_info_path",
        "prediction_file_path",
        "validation_json_path",
        "geometry_validation_json_path",
        "confidence_validation_json_path",
        "internal_scorecard_json_path",
        "format_check_status",
        "model_generation_status",
        "parameterization_status",
        "protein_local_minimization_status",
        "geometry_sanity_status",
        "confidence_calibration_status",
        "internal_scorecard_status",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _run_builder(tmp_path: Path, intake_csv: Path, prediction_dir: Path) -> tuple[dict, Path]:
    out_json = tmp_path / "runs/import.json"
    out_intake = tmp_path / "runs/intake_imported.csv"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/build_casp17_prediction_import_packet.py"),
            "--intake-csv",
            str(intake_csv),
            "--prediction-dir",
            str(prediction_dir),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "runs/import.csv"),
            "--out-md",
            str(tmp_path / "runs/import.md"),
            "--out-intake-csv",
            str(out_intake),
        ],
        cwd=ROOT,
        check=True,
    )
    return json.loads(out_json.read_text(encoding="utf-8")), out_intake


def test_casp17_prediction_import_packet_imports_valid_ts_candidate(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()
    prediction_file = prediction_dir / "T7000TS.pdb"
    prediction_file.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T7000",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD import smoke.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", 1, 80.0),
                _atom(2, "CA", 1, 75.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T7000",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
            }
        ],
    )

    payload, out_intake = _run_builder(tmp_path, intake, prediction_dir)

    assert payload["summary"]["imported_count"] == 1
    assert payload["rows"][0]["prediction_import_status"] == "imported"
    with out_intake.open("r", encoding="utf-8", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
    assert row["prediction_file_path"].endswith("T7000TS.pdb")
    assert row["prediction_import_status"] == "imported"
    assert row["prediction_import_blockers"] == ""


def test_casp17_prediction_import_packet_blocks_placeholder_candidate(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()
    (prediction_dir / "T7001TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T7001",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD placeholder example only.",
                "MODEL 1",
                _atom(1, "N", 1, 50.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T7001",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
            }
        ],
    )

    payload, out_intake = _run_builder(tmp_path, intake, prediction_dir)

    assert payload["summary"]["blocked_placeholder_or_invalid_count"] == 1
    assert payload["rows"][0]["prediction_import_status"] == "blocked_placeholder_or_invalid"
    assert "placeholder_or_fake_prediction_content" in payload["rows"][0]["blockers"]
    with out_intake.open("r", encoding="utf-8", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
    assert row["prediction_file_path"] == ""
    assert row["prediction_candidate_path"].endswith("T7001TS.pdb")
    assert "placeholder_or_fake_prediction_content" in row["prediction_import_blockers"]


def test_casp17_prediction_import_packet_records_missing_candidate(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()
    intake = tmp_path / "runs/intake.csv"
    _write_intake(
        intake,
        [
            {
                "target_id": "T7002",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
            }
        ],
    )

    payload, out_intake = _run_builder(tmp_path, intake, prediction_dir)

    assert payload["summary"]["missing_candidate_count"] == 1
    assert payload["rows"][0]["prediction_import_status"] == "missing_candidate"
    with out_intake.open("r", encoding="utf-8", newline="") as handle:
        row = list(csv.DictReader(handle))[0]
    assert row["prediction_file_path"] == ""
    assert row["prediction_import_blockers"] == "missing_prediction_candidate"
