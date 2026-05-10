from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_drd2_protein_amber14_parameterization_repair as mod

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _atom(serial: int, atom: str, res: str, resid: int, x: float = 0.0) -> str:
    return f"ATOM  {serial:5d} {atom:<4s}{res:>3s} A{resid:4d}    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           {atom[0]}"


def test_missing_heavy_atom_audit_flags_incomplete_histidine(tmp_path: Path) -> None:
    pdb = tmp_path / "protein.pdb"
    pdb.write_text(
        "\n".join(
            [
                _atom(1, "N", "HIS", 1),
                _atom(2, "CA", "HIS", 1),
                _atom(3, "C", "HIS", 1),
                _atom(4, "O", "HIS", 1),
                _atom(5, "CB", "HIS", 1),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    audit = mod._audit_missing_heavy_atoms(pdb)

    assert audit["missing_heavy_atom_residue_count"] == 1
    assert audit["incomplete_histidine_count"] == 1
    assert audit["examples"][0]["missing_heavy_atoms"] == ["CD2", "CE1", "CG", "ND1", "NE2"]


def test_build_repair_packet_keeps_claim_closed_for_missing_heavy_atoms(monkeypatch, tmp_path: Path) -> None:
    pdb = tmp_path / "protein.pdb"
    rows = tmp_path / "rows.csv"
    pdb.write_text(
        "\n".join(
            [
                _atom(1, "N", "ASN", 1),
                _atom(2, "CA", "ASN", 1),
                _atom(3, "C", "ASN", 1),
                _atom(4, "O", "ASN", 1),
                _atom(5, "CB", "ASN", 1),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        rows,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "protein_structure_source_path": str(pdb),
            }
        ],
    )
    monkeypatch.setattr(
        mod,
        "_openmm_probe",
        lambda protein_pdb, attempt_build=True: {
            "attempted": True,
            "raw_create_system": {"ready": False, "error": "raw_fail"},
            "add_hydrogens": {"ready": False, "error": "hyd_fail"},
        },
    )

    payload = mod.build_repair_packet(
        input_csv=rows,
        attempt_conservative_repair=False,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked_protein_amber14_parameterization"
    assert summary["protein_parameterization_ready"] is False
    assert summary["claim_grade_repair_allowed"] is False
    assert summary["missing_heavy_atom_residue_count"] == 1
    assert "missing_heavy_atom_residues_present" in summary["blockers"]
    assert payload["claim_boundary"]["deletion_or_mutation_repair_claim_grade_allowed"] is False


def test_fragment_split_oxt_repair_can_clear_openmm_terminal_gap_probe(tmp_path: Path) -> None:
    raw = tmp_path / "raw.pdb"
    repaired = tmp_path / "repaired.pdb"
    raw.write_text(
        "\n".join(
            [
                _atom(1, "N", "GLY", 1, 0.0),
                _atom(2, "CA", "GLY", 1, 1.0),
                _atom(3, "C", "GLY", 1, 2.0),
                _atom(4, "O", "GLY", 1, 3.0),
                _atom(5, "N", "GLY", 3, 4.0),
                _atom(6, "CA", "GLY", 3, 5.0),
                _atom(7, "C", "GLY", 3, 6.0),
                _atom(8, "O", "GLY", 3, 7.0),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    split = mod._write_fragment_split_oxt_pdb(raw, repaired)
    text = repaired.read_text(encoding="utf-8")

    assert split["fragment_count"] == 2
    assert text.count(" OXT ") == 2
    assert text.count("\nTER") == 2


def test_cli_writes_repair_packet_without_openmm_build(tmp_path: Path) -> None:
    pdb = tmp_path / "protein.pdb"
    rows = tmp_path / "rows.csv"
    out_json = tmp_path / "repair.json"
    out_md = tmp_path / "repair.md"
    pdb.write_text(
        "\n".join(
            [
                _atom(1, "N", "GLY", 1),
                _atom(2, "CA", "GLY", 1),
                _atom(3, "C", "GLY", 1),
                _atom(4, "O", "GLY", 1),
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        rows,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "protein_structure_source_path": str(pdb),
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_protein_amber14_parameterization_repair.py"),
            "--input-csv",
            str(rows),
            "--no-attempt-build",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["packet_type"] == "gpcr_drd2_protein_amber14_parameterization_repair"
    assert "GPCR DRD2 Protein Amber14 Parameterization Repair" in out_md.read_text(encoding="utf-8")
