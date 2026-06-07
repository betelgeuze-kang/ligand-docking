from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom_name: str, resname: str, chain: str, resseq: int, x: float, y: float, z: float) -> str:
    element = atom_name.strip()[0]
    return (
        f"ATOM  {serial:5d} {atom_name:<4} {resname:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{70.0:6.2f}          {element:>2}  "
    )


def test_build_casp17_sidechain_quality_packet_scores_rotamer_proxy(tmp_path: Path) -> None:
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
                _atom(1, "N", "ALA", "A", 1, -0.30, 0.16, 0.00),
                _atom(2, "CA", "ALA", "A", 1, 0.00, 0.00, 0.00),
                _atom(3, "C", "ALA", "A", 1, 0.36, 0.16, 0.00),
                _atom(4, "O", "ALA", "A", 1, 0.48, 0.34, 0.12),
                _atom(5, "CB", "ALA", "A", 1, 0.00, 1.46, -0.48),
                _atom(6, "N", "ALA", "A", 2, 3.44, 0.16, 0.00),
                _atom(7, "CA", "ALA", "A", 2, 3.80, 0.00, 0.00),
                _atom(8, "C", "ALA", "A", 2, 4.16, 0.16, 0.00),
                _atom(9, "O", "ALA", "A", 2, 4.28, 0.34, 0.12),
                _atom(10, "CB", "ALA", "A", 2, 3.80, 1.46, -0.48),
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
            str(ROOT / "tools/casp17/build_casp17_sidechain_quality_packet.py"),
            "--target-ids",
            "T9999",
            "--prediction-dir",
            str(prediction_dir),
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

    assert payload["summary"]["sidechain_quality_status"] == "pass"
    assert row["sidechain_quality_status"] == "pass"
    assert row["complete_sidechain_residue_fraction"] == 1.0
    assert row["rotamer_proxy_pass_fraction"] == 1.0
    assert row["cb_radial_outlier_fraction"] == 0.0
    assert "rotamer-frame proxy QC" in payload["summary"]["claim_boundary"]
