from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_drd2_full_forcefield_minimization_readiness as mod

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


def test_missing_ligand_template_stack_blocks_claim_even_with_positive_row(tmp_path: Path) -> None:
    ligand_pdb = tmp_path / "ligand.pdb"
    protein_pdb = tmp_path / "protein.pdb"
    ligand_pdb.write_text(
        "HETATM    1 C1   LIG L   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    protein_pdb.write_text(
        "ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 20.00           N\nEND\n",
        encoding="utf-8",
    )
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CCN",
                "protein_structure_source_path": str(protein_pdb),
                "backmapped_pdb": str(ligand_pdb),
                "allatom_backmapping_status": "ok",
            }
        ],
    )

    payload = mod.build_readiness(
        input_csv=input_csv,
        attempt_build=False,
        generated_at_local="2026-05-06T00:00:00+09:00",
        dependency_overrides={
            "openmm": True,
            "rdkit": True,
            "openff": False,
            "openff.toolkit": False,
            "openmmforcefields": False,
            "pdbfixer": False,
            "parmed": False,
            "openbabel": False,
        },
        asset_overrides={
            "chimerax_amber14_all_xml": ligand_pdb,
            "chimerax_gaff_xml": ligand_pdb,
            "ambertools_bin": tmp_path,
        },
    )

    summary = payload["summary"]
    assert summary["status"] == "blocked"
    assert summary["full_forcefield_minimization_ready"] is False
    assert summary["openmm_available"] is True
    assert summary["rdkit_available"] is True
    assert summary["ligand_parameterization_available"] is False
    assert summary["protein_parameterization_available"] is False
    assert "openff.toolkit" in summary["missing_dependencies"]
    assert "openmmforcefields" in summary["missing_dependencies"]
    assert "chimerax_tleap" in summary["missing_assets"]
    assert "No broad/commercial" in summary["claim_boundary"]
    assert payload["safe_next_command_if_ready"] == ""


def test_missing_positive_row_is_reported_as_asset_blocker(tmp_path: Path) -> None:
    input_csv = tmp_path / "repair_rows.csv"
    _write_csv(input_csv, [{"target": "OTHER", "ligand_id": "L1"}])

    payload = mod.build_readiness(
        input_csv=input_csv,
        attempt_build=False,
        generated_at_local="2026-05-06T00:00:00+09:00",
        dependency_overrides={"openmm": True, "rdkit": True},
    )

    assert payload["target_probe"]["row_found"] is False
    assert payload["summary"]["full_forcefield_minimization_ready"] is False
    assert "drd2_positive_repair_row" in payload["summary"]["missing_assets"]


def test_cli_writes_json_and_markdown_outputs_without_large_build(tmp_path: Path) -> None:
    input_csv = tmp_path / "repair_rows.csv"
    ligand_pdb = tmp_path / "ligand.pdb"
    protein_pdb = tmp_path / "protein.pdb"
    out_json = tmp_path / "readiness.json"
    out_md = tmp_path / "readiness.md"
    ligand_pdb.write_text(
        "HETATM    1 C1   LIG L   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n",
        encoding="utf-8",
    )
    protein_pdb.write_text(
        "ATOM      1  N   GLY A   1       0.000   0.000   0.000  1.00 20.00           N\nEND\n",
        encoding="utf-8",
    )
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "ligand_smiles": "CCN",
                "protein_structure_source_path": str(protein_pdb),
                "backmapped_pdb": str(ligand_pdb),
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_full_forcefield_minimization_readiness.py"),
            "--input-csv",
            str(input_csv),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--no-attempt-build",
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["packet_type"] == "gpcr_drd2_full_forcefield_minimization_readiness"
    assert payload["summary"]["status"] == "blocked"
    assert payload["summary"]["full_forcefield_minimization_ready"] is False
    assert "GPCR DRD2 Full-Forcefield Minimization Readiness" in out_md.read_text(encoding="utf-8")
    assert "full_forcefield_minimization_ready" in result.stdout
