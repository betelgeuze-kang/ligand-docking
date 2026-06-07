from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    b_factor = 41.0 + float(serial)
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}          {element:>2}  "
    )


def test_build_casp17_rotamer_minimization_packet_keeps_ts_valid_and_reports_evidence(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    out_dir = tmp_path / "out"
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
                "SCORE 0.500",
                "PARENT N/A",
                _atom(1, "N", "SER", "A", 1, -0.300, 0.160, 0.000),
                _atom(2, "CA", "SER", "A", 1, 0.000, 0.000, 0.000),
                _atom(3, "C", "SER", "A", 1, 0.360, 0.160, 0.000),
                _atom(4, "O", "SER", "A", 1, 0.480, 0.340, 0.120),
                _atom(5, "CB", "SER", "A", 1, 0.000, 1.460, -0.480),
                _atom(6, "OG", "SER", "A", 1, 0.000, 2.360, -0.620),
                _atom(7, "N", "ASP", "A", 2, 3.450, 0.180, 0.000),
                _atom(8, "CA", "ASP", "A", 2, 3.800, 0.000, 0.000),
                _atom(9, "C", "ASP", "A", 2, 4.160, 0.160, 0.000),
                _atom(10, "O", "ASP", "A", 2, 4.280, 0.340, 0.120),
                _atom(11, "CB", "ASP", "A", 2, 3.800, 1.460, -0.480),
                _atom(12, "CG", "ASP", "A", 2, 3.800, 2.420, -0.680),
                _atom(13, "OD1", "ASP", "A", 2, 3.250, 3.100, -0.500),
                _atom(14, "OD2", "ASP", "A", 2, 4.350, 3.100, -0.820),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (sequence_dir / "T9999.fasta").write_text(">T9999\nSD\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_rotamer_minimization_packet.py"),
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

    assert payload["summary"]["rotamer_minimization_status"] == "pass"
    assert row["rotamer_minimization_status"] == "pass"
    assert row["minimized_residue_count"] >= 2
    assert row["rotamer_candidate_count"] > 0
    assert row["soft_clash_count_after"] <= row["soft_clash_count_before"]
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert "REMARK CASP17 ROTAMER_MINIMIZATION" in text
    assert "Rotamer Minimization" in (tmp_path / "packet.md").read_text(encoding="utf-8")
