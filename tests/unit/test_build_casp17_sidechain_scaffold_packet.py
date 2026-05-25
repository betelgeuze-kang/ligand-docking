from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _ca(serial: int, resname: str, chain: str, resseq: int, x: float) -> str:
    return f"ATOM  {serial:5d} CA   {resname:>3} {chain}{resseq:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.00:6.2f}{60.0 + resseq:6.2f}           C  "


def test_build_casp17_sidechain_scaffold_packet_rebuilds_residue_specific_atoms(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    sequence_dir = tmp_path / "seq"
    out_dir = tmp_path / "sidechain"
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
                "SCORE 0.420",
                "PARENT N/A",
                _ca(1, "ALA", "A", 1, 0.0),
                _ca(2, "GLY", "A", 2, 3.8),
                _ca(3, "LYS", "A", 3, 7.6),
                _ca(4, "SER", "A", 4, 11.4),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (sequence_dir / "T9999.fasta").write_text(">T9999\nAGKS\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_sidechain_scaffold_packet.py"),
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

    assert payload["summary"]["sidechain_scaffold_status"] == "pass"
    assert row["sidechain_scaffold_status"] == "pass"
    assert row["residue_count"] == 4
    assert row["format_check_status"] == "pass"
    assert row["geometry_sanity_status"] == "pass"
    assert row["confidence_calibration_status"] == "pass"
    assert "REMARK CASP17 SIDECHAIN_SCAFFOLD" in text
    assert "NZ   LYS" in text
    assert "OG   SER" in text
    assert "CB   GLY" not in text
    assert row["emitted_heavy_atom_count"] > 16
    assert row["rotamer_selected_residue_count"] == 3
    assert row["rotamer_candidate_count"] == 18
    assert payload["summary"]["total_rotamer_selected_residue_count"] == 3
