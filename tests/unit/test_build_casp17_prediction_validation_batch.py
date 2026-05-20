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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_casp17_prediction_validation_batch_enriches_valid_ts_row(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    outputs = tmp_path / "outputs"
    inputs.mkdir()
    outputs.mkdir()
    (inputs / "T3000.fasta").write_text(">T3000\nACDE\n", encoding="utf-8")
    (outputs / "T3000TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T3000",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD batch validation smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", 1, 80.0),
                _atom(2, "CA", 1, 75.0),
                _atom(3, "C", 2, 70.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake_csv = tmp_path / "runs/intake.csv"
    _write_intake(
        intake_csv,
        [
            {
                "target_id": "T3000",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T3000.fasta"),
                "prediction_file_path": str(outputs / "T3000TS.pdb"),
                "format_check_status": "missing",
            },
            {
                "target_id": "T3001",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T3000.fasta"),
                "prediction_file_path": "",
                "format_check_status": "missing",
            },
        ],
    )
    out_json = tmp_path / "runs/batch.json"
    out_intake = tmp_path / "runs/intake_validated.csv"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_prediction_validation_batch.py"),
            "--intake-csv",
            str(intake_csv),
            "--out-dir",
            str(tmp_path / "runs/validations"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "runs/batch.csv"),
            "--out-md",
            str(tmp_path / "runs/batch.md"),
            "--out-intake-csv",
            str(out_intake),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["validated_count"] == 1
    assert payload["summary"]["skipped_count"] == 1
    assert payload["summary"]["format_pass_count"] == 1
    assert payload["summary"]["geometry_pass_count"] == 1
    assert payload["summary"]["confidence_pass_count"] == 1
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T3000"]["format_check_status"] == "pass"
    assert rows["T3000"]["geometry_sanity_status"] == "pass"
    assert rows["T3000"]["confidence_calibration_status"] == "pass"
    assert rows["T3001"]["skip_reason"] == "missing_prediction_file_path"

    with out_intake.open("r", encoding="utf-8", newline="") as handle:
        enriched_rows = {row["target_id"]: row for row in csv.DictReader(handle)}
    assert enriched_rows["T3000"]["format_check_status"] == "pass"
    assert enriched_rows["T3000"]["geometry_sanity_status"] == "pass"
    assert enriched_rows["T3000"]["confidence_calibration_status"] == "pass"
    assert enriched_rows["T3000"]["validation_json_path"].endswith("T3000_ts_validation.json")
    assert enriched_rows["T3000"]["geometry_validation_json_path"].endswith("T3000_geometry_sanity.json")
    assert enriched_rows["T3000"]["confidence_validation_json_path"].endswith("T3000_confidence_calibration.json")
    assert enriched_rows["T3001"]["validation_json_path"] == ""


def test_build_casp17_prediction_validation_batch_records_failures(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    outputs = tmp_path / "outputs"
    inputs.mkdir()
    outputs.mkdir()
    (inputs / "T3002.fasta").write_text(">T3002\nACDE\n", encoding="utf-8")
    (outputs / "T3002TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T3002",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD malformed batch validation smoke file.",
                "MODEL 1",
                _atom(1, "N", 1, 50.0),
                _atom(2, "CA", 1, 50.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    intake_csv = tmp_path / "runs/intake.csv"
    _write_intake(
        intake_csv,
        [
            {
                "target_id": "T3002",
                "lane": "difficult_protein_complexes",
                "submission_format": "TS",
                "deadline_class": "regular",
                "sequence_path": str(inputs / "T3002.fasta"),
                "prediction_file_path": str(outputs / "T3002TS.pdb"),
                "format_check_status": "missing",
            }
        ],
    )
    out_json = tmp_path / "runs/batch.json"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_prediction_validation_batch.py"),
            "--intake-csv",
            str(intake_csv),
            "--out-dir",
            str(tmp_path / "runs/validations"),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "runs/batch.csv"),
            "--out-md",
            str(tmp_path / "runs/batch.md"),
            "--out-intake-csv",
            str(tmp_path / "runs/intake_validated.csv"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["validated_count"] == 1
    assert payload["summary"]["format_fail_count"] == 1
    assert payload["summary"]["geometry_skipped_count"] == 1
    assert payload["summary"]["confidence_skipped_count"] == 1
    assert payload["rows"][0]["format_check_status"] == "fail"
    assert payload["rows"][0]["geometry_sanity_status"] == "blocked_by_format_failure"
    assert payload["rows"][0]["confidence_calibration_status"] == "blocked_by_format_failure"
    validation_json = tmp_path / "runs/validations/T3002_ts_validation.json"
    validation = json.loads(validation_json.read_text(encoding="utf-8"))
    assert {blocker["code"] for blocker in validation["blockers"]} >= {"parent_record_missing", "uniform_b_factor_confidence"}
