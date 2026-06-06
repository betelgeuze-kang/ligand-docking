from __future__ import annotations

import argparse
import csv
from pathlib import Path

from tools.product import freeze_glut1_target_packet_from_pdb as mod


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _pdb_line(record: str, atom_id: int, atom: str, res: str, chain: str, resid: int, x: float, y: float, z: float) -> str:
    return (
        f"{record:<6}{atom_id:5d} {atom:^4s} {res:>3s} {chain}{resid:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 10.00           C\n"
    )


def test_freeze_glut1_target_packet_from_pdb_updates_target_and_metadata(tmp_path: Path) -> None:
    pdb = tmp_path / "4pyp.pdb"
    pdb.write_text(
        "SEQRES   1 A    5  GLN ALA ASN TRP GLN\n"
        + _pdb_line("ATOM", 1, "CA", "GLN", "A", 161, 1.0, 2.0, 3.0)
        + _pdb_line("ATOM", 2, "CA", "GLN", "A", 282, 3.0, 4.0, 5.0)
        + _pdb_line("ATOM", 3, "CA", "ASN", "A", 288, 5.0, 6.0, 7.0)
        + _pdb_line("ATOM", 4, "CA", "TRP", "A", 388, 7.0, 8.0, 9.0)
        + _pdb_line("ATOM", 5, "CA", "ASN", "A", 411, 9.0, 10.0, 11.0),
        encoding="utf-8",
    )
    target_csv = tmp_path / "targets.csv"
    target_meta_csv = tmp_path / "target_meta.csv"
    _write_csv(
        target_csv,
        [
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "native_pdb_path": "4pyp.pdb",
                "pdb_id": "4PYP",
                "pocket_x": "0.0",
                "pocket_y": "0.0",
                "pocket_z": "0.0",
                "notes": "placeholder",
            }
        ],
        ["target", "native_pdb_path", "pdb_id", "pocket_x", "pocket_y", "pocket_z", "notes"],
    )
    _write_csv(
        target_meta_csv,
        [
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "target_family": "",
                "sequence": "TEMPLATE_SEQ",
                "pocket_fingerprint": "glut_transporter",
            }
        ],
        ["target", "target_family", "sequence", "pocket_fingerprint"],
    )

    payload = mod.build_payload(
        argparse.Namespace(
            pdb_path=str(pdb),
            target_csv=str(target_csv),
            target_meta_csv=str(target_meta_csv),
            target_id="GLUT1_TRANSPORT_BLIND",
            chain_id="A",
            centroid_residues="161,282,288,388,411",
        )
    )

    assert payload["derived"]["pocket_center_xyz"] == [5.0, 6.0, 7.0]
    target_row = next(csv.DictReader(target_csv.open("r", encoding="utf-8")))
    assert target_row["pocket_x"] == "5.000"
    assert target_row["pocket_y"] == "6.000"
    assert target_row["pocket_z"] == "7.000"
    meta_row = next(csv.DictReader(target_meta_csv.open("r", encoding="utf-8")))
    assert meta_row["sequence"] == "QANWQ"
    assert meta_row["target_family"] == "MEMBRANE_TRANSPORT_GLUCOSE"
    assert "residue_ca_centroid" in meta_row["pocket_fingerprint"]
