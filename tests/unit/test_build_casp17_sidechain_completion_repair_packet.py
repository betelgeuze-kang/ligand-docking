from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    b_factor = 42.0 + float(serial)
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}          {element:>2}  "
    )


def test_build_casp17_sidechain_completion_repair_packet_inserts_missing_atoms(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    out_dir = tmp_path / "completed"
    source_dir.mkdir()
    sequence_dir.mkdir()
    (source_dir / "T9999TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T9999",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", "LYS", "A", 1, -0.30, 0.16, 0.00),
                _atom(2, "CA", "LYS", "A", 1, 0.00, 0.00, 0.00),
                _atom(3, "C", "LYS", "A", 1, 0.36, 0.16, 0.00),
                _atom(4, "O", "LYS", "A", 1, 0.48, 0.34, 0.12),
                _atom(5, "CB", "LYS", "A", 1, 0.00, 1.46, -0.48),
                _atom(6, "CG", "LYS", "A", 1, 0.00, 2.45, -0.72),
                _atom(7, "N", "ALA", "A", 2, 3.44, 0.16, 0.00),
                _atom(8, "CA", "ALA", "A", 2, 3.80, 0.00, 0.00),
                _atom(9, "C", "ALA", "A", 2, 4.16, 0.16, 0.00),
                _atom(10, "O", "ALA", "A", 2, 4.28, 0.34, 0.12),
                _atom(11, "CB", "ALA", "A", 2, 3.80, 1.46, -0.48),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (sequence_dir / "T9999.fasta").write_text(">T9999\nKA\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_completion_repair_packet.py"),
            "--target-ids",
            "T9999",
            "--source-dir",
            str(source_dir),
            "--sequence-dir",
            str(sequence_dir),
            "--out-dir",
            str(out_dir),
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
    text = (out_dir / "T9999TS.pdb").read_text(encoding="utf-8")

    assert payload["summary"]["sidechain_completion_repair_status"] == "pass"
    assert row["missing_sidechain_atom_count_before"] == 3
    assert row["inserted_sidechain_atom_count"] == 3
    assert row["missing_sidechain_atom_count_after"] == 0
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert " CD " in text
    assert " CE " in text
    assert " NZ " in text
    assert "REMARK CASP17 SIDECHAIN_COMPLETION_REPAIR" in text
