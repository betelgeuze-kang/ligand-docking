from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(
    serial: int,
    atom: str,
    resname: str,
    chain: str,
    resseq: int,
    x: float,
    y: float,
    z: float,
    b_factor: float,
) -> str:
    element = atom[0] if atom[0].isalpha() else atom[-1]
    return (
        f"ATOM  {serial:5d} {atom:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}           {element:>2}  "
    )


def test_build_casp17_polar_refinement_packet_keeps_quality_not_worse(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    source_dir.mkdir()
    sequence_dir.mkdir()
    sequence_dir.joinpath("T9999.fasta").write_text(">T9999\nKE\n", encoding="utf-8")
    lines = [
        "PFRMAT TS",
        "TARGET T9999",
        "AUTHOR 0000-0000-0000",
        "METHOD internal polar refinement fixture",
        "MODEL 1",
        "PARENT N/A",
    ]
    serial = 1
    for line in [
        _atom(serial, "N", "LYS", "A", 1, 0.0, 0.0, 0.0, 72.0),
        _atom(serial + 1, "CA", "LYS", "A", 1, 1.4, 0.0, 0.0, 74.0),
        _atom(serial + 2, "C", "LYS", "A", 1, 2.4, 1.0, 0.0, 76.0),
        _atom(serial + 3, "O", "LYS", "A", 1, 2.4, 2.2, 0.0, 78.0),
        _atom(serial + 4, "CB", "LYS", "A", 1, 1.4, -1.5, 0.0, 80.0),
        _atom(serial + 5, "NZ", "LYS", "A", 1, 1.4, -2.7, 0.0, 82.0),
        _atom(serial + 6, "N", "GLU", "A", 2, 3.8, 0.0, 0.0, 73.0),
        _atom(serial + 7, "CA", "GLU", "A", 2, 5.2, 0.0, 0.0, 75.0),
        _atom(serial + 8, "C", "GLU", "A", 2, 6.2, 1.0, 0.0, 77.0),
        _atom(serial + 9, "O", "GLU", "A", 2, 6.2, 2.2, 0.0, 79.0),
        _atom(serial + 10, "CB", "GLU", "A", 2, 5.2, -1.5, 0.0, 81.0),
        _atom(serial + 11, "OE1", "GLU", "A", 2, 5.2, -2.7, 0.0, 83.0),
    ]:
        lines.append(line)
    lines.extend(["TER", "END", ""])
    source_dir.joinpath("T9999TS.pdb").write_text("\n".join(lines), encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_polar_refinement_packet.py"),
            "--target-ids",
            "T9999",
            "--source-dir",
            str(source_dir),
            "--sequence-dir",
            str(sequence_dir),
            "--out-dir",
            str(tmp_path / "out"),
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
    out_pdb = tmp_path / "out/T9999TS.pdb"

    assert payload["summary"]["polar_refinement_status"] == "pass"
    assert row["polar_refinement_status"] == "pass"
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert row["soft_clash_count_after"] <= row["soft_clash_count_before"]
    assert row["polar_contact_delta"] >= 0
    assert out_pdb.exists()
    assert "REMARK CASP17 POLAR_REFINEMENT" in out_pdb.read_text(encoding="utf-8")
