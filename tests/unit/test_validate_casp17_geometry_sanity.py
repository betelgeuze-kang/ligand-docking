from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _atom(serial: int, atom: str, res: str, chain: str, resseq: int, x: float, y: float, z: float, b: float = 70.0) -> str:
    return (
        f"ATOM  {serial:5d} {atom:<4}{res:>3} {chain}{resseq:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.00:6.2f}{b:6.2f}           C  "
    )


def test_validate_casp17_geometry_sanity_passes_basic_model(tmp_path: Path) -> None:
    prediction = tmp_path / "T4000TS.pdb"
    out_json = tmp_path / "geometry.json"
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T4000",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD geometry sanity smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "N", "ALA", "A", 1, 0.0, 0.0, 0.0),
                _atom(2, "CA", "ALA", "A", 1, 1.5, 0.0, 0.0),
                _atom(3, "C", "ALA", "A", 1, 2.5, 1.0, 0.0),
                _atom(4, "N", "CYS", "A", 2, 3.5, 1.5, 0.0),
                _atom(5, "CA", "CYS", "A", 2, 5.2, 0.2, 0.0),
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
            str(ROOT / "tools/casp17/validate_casp17_geometry_sanity.py"),
            "--target-id",
            "T4000",
            "--prediction-file",
            str(prediction),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "geometry.csv"),
            "--out-md",
            str(tmp_path / "geometry.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["geometry_sanity_status"] == "pass"
    assert payload["summary"]["severe_clash_count"] == 0
    assert payload["summary"]["ca_pair_checked_count"] == 1


def test_validate_casp17_geometry_sanity_fails_severe_inter_residue_clash(tmp_path: Path) -> None:
    prediction = tmp_path / "T4001TS.pdb"
    out_json = tmp_path / "geometry.json"
    prediction.write_text(
        "\n".join(
            [
                "PFRMAT TS",
                "TARGET T4001",
                "AUTHOR XXXX-XXXX-XXXX",
                "METHOD clashing geometry smoke file.",
                "MODEL 1",
                "PARENT N/A",
                _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
                _atom(2, "CA", "CYS", "A", 2, 0.2, 0.0, 0.0),
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
            str(ROOT / "tools/casp17/validate_casp17_geometry_sanity.py"),
            "--target-id",
            "T4001",
            "--prediction-file",
            str(prediction),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(tmp_path / "geometry.csv"),
            "--out-md",
            str(tmp_path / "geometry.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["geometry_sanity_status"] == "fail"
    assert "severe_inter_residue_atom_clashes" in {blocker["code"] for blocker in payload["blockers"]}
