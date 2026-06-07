from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.00:6.2f}          {element:>2}  "
    )


def test_build_casp17_all_atom_quality_packet_reports_internal_steric_qc(tmp_path: Path) -> None:
    prediction_dir = tmp_path / "predictions"
    prediction_dir.mkdir()
    (prediction_dir / "T9999TS.pdb").write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T9999",
                "AUTHOR REDACTED",
                "METHOD fixture",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", "ALA", "A", 1, -0.3, 0.2, 0.0),
                _atom(2, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
                _atom(3, "C", "ALA", "A", 1, 0.4, 0.2, 0.0),
                _atom(4, "O", "ALA", "A", 1, 0.5, 0.4, 0.1),
                _atom(5, "CB", "ALA", "A", 1, 0.0, 1.6, 0.0),
                _atom(6, "N", "GLY", "A", 2, 4.7, 0.2, 0.0),
                _atom(7, "CA", "GLY", "A", 2, 5.0, 0.0, 0.0),
                _atom(8, "C", "GLY", "A", 2, 5.4, 0.2, 0.0),
                _atom(9, "O", "GLY", "A", 2, 5.5, 0.4, 0.1),
                "TER",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sidechain = tmp_path / "sidechain.json"
    sidechain.write_text(
        json.dumps({"summary": {"pass_count": 1, "validation_pass_count": 1}}),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_all_atom_quality_packet.py"),
            "--target-ids",
            "T9999",
            "--prediction-dir",
            str(prediction_dir),
            "--sidechain-scaffold-json",
            str(sidechain),
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

    assert payload["summary"]["all_atom_quality_status"] == "pass"
    assert payload["summary"]["pass_count"] == 1
    assert row["all_atom_quality_status"] == "pass"
    assert row["heavy_atom_completion_fraction"] == 1.0
    assert row["severe_clash_count"] == 0
    assert row["soft_clashscore_per_1000_atoms"] == 0.0
    assert "Internal MolProbity-style" in payload["summary"]["claim_boundary"]
