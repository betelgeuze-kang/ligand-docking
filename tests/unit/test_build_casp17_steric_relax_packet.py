from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    b_factor = 55.0 + serial
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}          {element:>2}  "
    )


def test_build_casp17_steric_relax_packet_reduces_sidechain_soft_clashes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    out_dir = tmp_path / "relaxed"
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
                _atom(1, "N", "ALA", "A", 1, -0.30, 0.16, 0.00),
                _atom(2, "CA", "ALA", "A", 1, 0.00, 0.00, 0.00),
                _atom(3, "C", "ALA", "A", 1, 0.36, 0.16, 0.00),
                _atom(4, "O", "ALA", "A", 1, 0.48, 0.34, 0.12),
                _atom(5, "CB", "ALA", "A", 1, 1.90, 0.50, 0.00),
                _atom(6, "N", "ALA", "A", 2, 3.44, 0.16, 0.00),
                _atom(7, "CA", "ALA", "A", 2, 3.80, 0.00, 0.00),
                _atom(8, "C", "ALA", "A", 2, 4.16, 0.16, 0.00),
                _atom(9, "O", "ALA", "A", 2, 4.28, 0.34, 0.12),
                _atom(10, "CB", "ALA", "A", 2, 1.90, -0.40, 0.00),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (sequence_dir / "T9999.fasta").write_text(">T9999\nAA\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_steric_relax_packet.py"),
            "--target-ids",
            "T9999",
            "--source-dir",
            str(source_dir),
            "--sequence-dir",
            str(sequence_dir),
            "--out-dir",
            str(out_dir),
            "--iterations",
            "8",
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

    assert payload["summary"]["steric_relax_status"] == "pass"
    assert row["steric_relax_status"] == "pass"
    assert row["soft_clash_count_before"] >= row["soft_clash_count_after"]
    assert row["soft_clash_delta"] > 0
    assert row["coordinate_update_count"] > 0
    assert row["severe_clash_count_after"] == 0
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert "REMARK CASP17 STERIC_RELAX" in text
