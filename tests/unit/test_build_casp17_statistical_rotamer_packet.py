from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(
    serial: int,
    atom_name: str,
    resname: str,
    chain: str,
    resseq: int,
    x: float,
    y: float,
    z: float,
    b_factor: float,
) -> str:
    element = atom_name.strip()[0]
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b_factor:6.2f}          {element:>2}  "
    )


def test_build_casp17_statistical_rotamer_packet_keeps_valid_ts_and_reports_prior_evidence(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    out_dir = tmp_path / "out"
    source_dir.mkdir()
    sequence_dir.mkdir()
    sequence_dir.joinpath("T9999.fasta").write_text(">T9999\nSD\n", encoding="utf-8")
    source_dir.joinpath("T9999TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T9999",
                "AUTHOR REDACTED",
                "METHOD statistical rotamer fixture",
                "MODEL 1",
                "SCORE 0.600",
                "PARENT N/A",
                _atom(1, "N", "SER", "A", 1, -0.300, 0.160, 0.000, 74.0),
                _atom(2, "CA", "SER", "A", 1, 0.000, 0.000, 0.000, 75.0),
                _atom(3, "C", "SER", "A", 1, 0.360, 0.160, 0.000, 76.0),
                _atom(4, "O", "SER", "A", 1, 0.480, 0.340, 0.120, 77.0),
                _atom(5, "CB", "SER", "A", 1, 0.000, 1.460, -0.480, 78.0),
                _atom(6, "OG", "SER", "A", 1, 0.000, 2.360, -0.620, 79.0),
                _atom(7, "N", "ASP", "A", 2, 3.450, 0.180, 0.000, 74.0),
                _atom(8, "CA", "ASP", "A", 2, 3.800, 0.000, 0.000, 75.0),
                _atom(9, "C", "ASP", "A", 2, 4.160, 0.160, 0.000, 76.0),
                _atom(10, "O", "ASP", "A", 2, 4.280, 0.340, 0.120, 77.0),
                _atom(11, "CB", "ASP", "A", 2, 3.800, 1.460, -0.480, 78.0),
                _atom(12, "CG", "ASP", "A", 2, 3.800, 2.420, -0.680, 79.0),
                _atom(13, "OD1", "ASP", "A", 2, 3.250, 3.100, -0.500, 80.0),
                _atom(14, "OD2", "ASP", "A", 2, 4.350, 3.100, -0.820, 81.0),
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
            str(ROOT / "tools/build_casp17_statistical_rotamer_packet.py"),
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
    out_pdb = out_dir / "T9999TS.pdb"

    assert payload["summary"]["statistical_rotamer_status"] == "pass"
    assert row["statistical_rotamer_status"] == "pass"
    assert row["evaluated_residue_count"] >= 2
    assert row["statistical_rotamer_candidate_count"] > row["evaluated_residue_count"]
    assert row["forcefield_energy_after"] <= row["forcefield_energy_before"]
    assert row["soft_clash_count_after"] <= row["soft_clash_count_before"]
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert "REMARK CASP17 STATISTICAL_ROTAMER" in out_pdb.read_text(encoding="utf-8")
    assert "no external rotamer library" in (tmp_path / "packet.md").read_text(encoding="utf-8")
