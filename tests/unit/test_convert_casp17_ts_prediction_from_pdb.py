from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, resseq: int, b_factor: float, chain_id: str = "A") -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4} ALA {chain_id}{resseq:4d}    "
        f"{float(serial):8.3f}{1.000:8.3f}{1.000:8.3f}{1.00:6.2f}{b_factor:6.2f}           C  "
    )


def test_convert_casp17_ts_prediction_from_pdb_wraps_atom_records(tmp_path: Path) -> None:
    input_pdb = tmp_path / "raw.pdb"
    sequence = tmp_path / "T8000.fasta"
    out_pdb = tmp_path / "T8000TS.pdb"
    out_json = tmp_path / "convert.json"
    sequence.write_text(">T8000\nAC\n", encoding="utf-8")
    input_pdb.write_text("\n".join([_atom(1, "N", 1, 82.0), _atom(2, "CA", 2, 71.0), "END", ""]), encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/convert_casp17_ts_prediction_from_pdb.py"),
            "--target-id",
            "T8000",
            "--input-pdb",
            str(input_pdb),
            "--sequence-path",
            str(sequence),
            "--author-code",
            "1234-5678-ABCD",
            "--out-pdb",
            str(out_pdb),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "convert.csv"),
            "--out-md",
            str(tmp_path / "convert.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["conversion_status"] == "pass"
    text = out_pdb.read_text(encoding="utf-8")
    assert text.startswith("PFRMAT TS\nTARGET T8000\nAUTHOR 1234-5678-ABCD\n")
    assert "MODEL 1\nPARENT N/A\nATOM" in text
    assert text.rstrip().endswith("END")

    validation_json = tmp_path / "validation.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/validate_casp17_ts_prediction.py"),
            "--target-id",
            "T8000",
            "--prediction-file",
            str(out_pdb),
            "--sequence-path",
            str(sequence),
            "--out-json",
            str(validation_json),
            "--out-csv",
            str(tmp_path / "validation.csv"),
            "--out-md",
            str(tmp_path / "validation.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    validation = json.loads(validation_json.read_text(encoding="utf-8"))
    assert validation["summary"]["format_check_status"] == "pass"


def test_convert_casp17_ts_prediction_from_pdb_adds_parent_and_ter_per_chain(tmp_path: Path) -> None:
    input_pdb = tmp_path / "raw_multichain.pdb"
    sequence = tmp_path / "H8002.fasta"
    out_pdb = tmp_path / "H8002TS.pdb"
    out_json = tmp_path / "convert_multichain.json"
    sequence.write_text(">H8002 A\nA\n>H8002 B\nA\n", encoding="utf-8")
    input_pdb.write_text(
        "\n".join([
            _atom(1, "CA", 1, 82.0, "A"),
            _atom(2, "CA", 1, 71.0, "B"),
            "END",
            "",
        ]),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/convert_casp17_ts_prediction_from_pdb.py"),
            "--target-id",
            "H8002",
            "--input-pdb",
            str(input_pdb),
            "--sequence-path",
            str(sequence),
            "--author-code",
            "1234-5678-ABCD",
            "--out-pdb",
            str(out_pdb),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "convert_multichain.csv"),
            "--out-md",
            str(tmp_path / "convert_multichain.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["parent_record_count"] == 2
    assert payload["summary"]["ter_record_count"] == 2
    text = out_pdb.read_text(encoding="utf-8")
    assert text.count("\nPARENT N/A\n") == 2
    assert text.count("\nTER\n") == 2

    validation_json = tmp_path / "validation_multichain.json"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/validate_casp17_ts_prediction.py"),
            "--target-id",
            "H8002",
            "--prediction-file",
            str(out_pdb),
            "--sequence-path",
            str(sequence),
            "--out-json",
            str(validation_json),
            "--out-csv",
            str(tmp_path / "validation_multichain.csv"),
            "--out-md",
            str(tmp_path / "validation_multichain.md"),
        ],
        cwd=ROOT,
        check=True,
    )
    validation = json.loads(validation_json.read_text(encoding="utf-8"))
    assert validation["summary"]["format_check_status"] == "pass"


def test_convert_casp17_ts_prediction_from_pdb_blocks_without_author_code(tmp_path: Path) -> None:
    input_pdb = tmp_path / "raw.pdb"
    sequence = tmp_path / "T8001.fasta"
    input_pdb.write_text(_atom(1, "CA", 1, 50.0) + "\n", encoding="utf-8")
    sequence.write_text(">T8001\nA\n", encoding="utf-8")

    run = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/convert_casp17_ts_prediction_from_pdb.py"),
            "--target-id",
            "T8001",
            "--input-pdb",
            str(input_pdb),
            "--sequence-path",
            str(sequence),
            "--author-code",
            "",
            "--out-json",
            str(tmp_path / "convert.json"),
            "--out-csv",
            str(tmp_path / "convert.csv"),
            "--out-md",
            str(tmp_path / "convert.md"),
        ],
        cwd=ROOT,
        check=False,
    )

    assert run.returncode == 2
    payload = json.loads((tmp_path / "convert.json").read_text(encoding="utf-8"))
    assert payload["summary"]["conversion_status"] == "blocked"
    assert payload["blockers"][0]["code"] == "missing_author_code"
