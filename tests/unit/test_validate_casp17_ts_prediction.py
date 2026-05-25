from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, res: str, chain: str, resseq: int, x: float, y: float, z: float, occ: float, b: float) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}{res:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{occ:6.2f}{b:6.2f}           C  "
    )


def test_validate_casp17_ts_prediction_passes_valid_basic_file(tmp_path: Path) -> None:
    fasta = tmp_path / "H2000.fasta"
    prediction = tmp_path / "H2000TS.pdb"
    out_json = tmp_path / "validation.json"
    fasta.write_text(">H2000 chain A\nACDE\n", encoding="utf-8")
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET H2000",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD Betelgeuze local CASP17 gate smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", "ALA", "A", 1, 1.0, 1.0, 1.0, 1.00, 70.0),
                _atom(2, "CA", "ALA", "A", 1, 2.0, 1.0, 1.0, 1.00, 72.0),
                _atom(3, "C", "CYS", "A", 2, 3.0, 1.0, 1.0, 1.00, 65.0),
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
            str(ROOT / "tools/validate_casp17_ts_prediction.py"),
            "--target-id",
            "H2000",
            "--prediction-file",
            str(prediction),
            "--sequence-path",
            str(fasta),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "validation.csv"),
            "--out-md",
            str(tmp_path / "validation.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["format_check_status"] == "pass"
    assert payload["summary"]["blocker_count"] == 0
    assert payload["summary"]["model_indices"] == [1]
    assert payload["summary"]["b_factor_unique_count"] == 3


def test_validate_casp17_ts_prediction_fails_uniform_bfactor_and_missing_parent(tmp_path: Path) -> None:
    fasta = tmp_path / "T2001.fasta"
    prediction = tmp_path / "T2001TS.pdb"
    out_json = tmp_path / "validation.json"
    fasta.write_text(">T2001 chain A\nACDEFG\n", encoding="utf-8")
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T2001",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD deliberately malformed smoke file.",
                "MODEL 1",
                _atom(1, "N", "ALA", "A", 1, 1.0, 1.0, 1.0, 1.00, 50.0),
                _atom(2, "CA", "ALA", "A", 1, 2.0, 1.0, 1.0, 1.00, 50.0),
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/validate_casp17_ts_prediction.py"),
            "--target-id",
            "T2001",
            "--prediction-file",
            str(prediction),
            "--sequence-path",
            str(fasta),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "validation.csv"),
            "--out-md",
            str(tmp_path / "validation.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    codes = {blocker["code"] for blocker in payload["blockers"]}
    assert payload["summary"]["format_check_status"] == "fail"
    assert "parent_record_missing" in codes
    assert "ter_record_missing" in codes
    assert "uniform_b_factor_confidence" in codes


def test_validate_casp17_ts_prediction_allows_ranked_model_index_when_requested(tmp_path: Path) -> None:
    fasta = tmp_path / "T2002.fasta"
    prediction = tmp_path / "T2002_model_3TS.pdb"
    out_json = tmp_path / "validation.json"
    fasta.write_text(">T2002 chain A\nACD\n", encoding="utf-8")
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T2002",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD ranked candidate smoke file.",
                "MODEL 3",
                "PARENT N/A",
                _atom(1, "N", "ALA", "A", 1, 1.0, 1.0, 1.0, 1.00, 62.0),
                _atom(2, "CA", "ALA", "A", 1, 2.0, 1.0, 1.0, 1.00, 70.0),
                _atom(3, "C", "CYS", "A", 2, 3.0, 1.0, 1.0, 1.00, 74.0),
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
            str(ROOT / "tools/validate_casp17_ts_prediction.py"),
            "--target-id",
            "T2002",
            "--prediction-file",
            str(prediction),
            "--sequence-path",
            str(fasta),
            "--allow-ranked-model-index",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "validation.csv"),
            "--out-md",
            str(tmp_path / "validation.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["format_check_status"] == "pass"
    assert payload["summary"]["model_indices"] == [3]
