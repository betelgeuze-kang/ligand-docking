from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, resseq: int, b_factor: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}ALA A{resseq:4d}    "
        f"{float(serial):8.3f}{1.000:8.3f}{1.000:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def test_validate_casp17_confidence_calibration_passes_nonuniform_confidence(tmp_path: Path) -> None:
    fasta = tmp_path / "T5000.fasta"
    prediction = tmp_path / "T5000TS.pdb"
    out_json = tmp_path / "confidence.json"
    fasta.write_text(">T5000\nACDEFGHIK\n", encoding="utf-8")
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T5000",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD confidence smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", 1, 88.0),
                _atom(2, "CA", 1, 82.0),
                _atom(3, "C", 2, 76.0),
                _atom(4, "CA", 2, 64.0),
                _atom(5, "CA", 3, 53.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/validate_casp17_confidence_calibration.py"),
            "--target-id",
            "T5000",
            "--prediction-file",
            str(prediction),
            "--sequence-path",
            str(fasta),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "confidence.csv"),
            "--out-md",
            str(tmp_path / "confidence.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["confidence_calibration_status"] == "pass"
    assert payload["summary"]["confidence_unique_count"] >= 3
    assert payload["summary"]["confidence_stddev"] > 1.0


def test_validate_casp17_confidence_calibration_fails_uniform_confidence(tmp_path: Path) -> None:
    fasta = tmp_path / "T5001.fasta"
    prediction = tmp_path / "T5001TS.pdb"
    out_json = tmp_path / "confidence.json"
    fasta.write_text(">T5001\nACDEFGHIK\n", encoding="utf-8")
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T5001",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD uniform confidence smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", 1, 50.0),
                _atom(2, "CA", 1, 50.0),
                _atom(3, "C", 2, 50.0),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/casp17/validate_casp17_confidence_calibration.py"),
            "--target-id",
            "T5001",
            "--prediction-file",
            str(prediction),
            "--sequence-path",
            str(fasta),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "confidence.csv"),
            "--out-md",
            str(tmp_path / "confidence.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert payload["summary"]["confidence_calibration_status"] == "fail"
    assert "confidence_not_nonuniform" in codes
    assert "confidence_variance_too_low" in codes
