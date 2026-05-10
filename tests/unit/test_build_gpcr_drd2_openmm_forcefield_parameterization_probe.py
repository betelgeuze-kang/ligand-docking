from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

from tools import build_gpcr_drd2_openmm_forcefield_parameterization_probe as mod

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


def test_parse_mol2_and_write_template(tmp_path: Path) -> None:
    mol2 = tmp_path / "lig.mol2"
    template = tmp_path / "lig.xml"
    mol2.write_text(
        "\n".join(
            [
                "@<TRIPOS>MOLECULE",
                "LIG",
                "@<TRIPOS>ATOM",
                "1 C1 0.0 0.0 0.0 c3 1 LIG -0.1",
                "2 N2 1.0 0.0 0.0 n3 1 LIG 0.1",
                "@<TRIPOS>BOND",
                "1 1 2 1",
                "",
            ]
        ),
        encoding="utf-8",
    )

    atoms, bonds = mod._parse_mol2(mol2)
    mod._write_ligand_template_xml(template, atoms, bonds)

    rendered = template.read_text(encoding="utf-8")
    assert atoms == [
        {"index": 1, "name": "C1", "type": "c3", "charge": -0.1},
        {"index": 2, "name": "N2", "type": "n3", "charge": 0.1},
    ]
    assert bonds == [(1, 2)]
    assert '<Residue name="LIG">' in rendered
    assert '<Bond from="0" to="1"/>' in rendered


def test_build_probe_reports_ligand_partial_without_claim(monkeypatch, tmp_path: Path) -> None:
    protein = tmp_path / "protein.pdb"
    ligand = tmp_path / "ligand.pdb"
    input_csv = tmp_path / "rows.csv"
    protein.write_text("ATOM      1  CA  GLY A   1       0.0     0.0     0.0  1.00 20.00           C\nEND\n")
    ligand.write_text("HETATM    1 C1   LIG L   1       0.0     0.0     0.0  1.00 20.00           C\nEND\n")
    _write_csv(
        input_csv,
        [
            {
                "target": "CHEMBL217_DRD2_HUMAN",
                "ligand_id": "CHEMBL301265",
                "is_positive": "True",
                "protein_structure_source_path": str(protein),
                "backmapped_pdb": str(ligand),
                "ligand_smiles": "CCN",
            }
        ],
    )
    monkeypatch.setattr(mod, "_module_available", lambda name: True)
    monkeypatch.setattr(
        mod,
        "_probe_protein_parameterization",
        lambda protein_pdb, attempt_build: {"attempted": True, "ready": False, "error": "protein_failed"},
    )
    monkeypatch.setattr(
        mod,
        "_probe_ligand_template",
        lambda *args, **kwargs: {
            "attempted": True,
            "ready": True,
            "claim_grade": False,
            "particle_count": 14,
            "force_count": 5,
        },
    )

    payload = mod.build_probe(
        input_csv=input_csv,
        attempt_build=True,
        ambertools_home=tmp_path,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["claim_grade_parameterization_ready"] is False
    assert summary["local_probe_partial"] is True
    assert summary["protein_parameterization_available"] is False
    assert summary["ligand_template_parameterization_available"] is True
    assert "protein_amber14_parameterization_unavailable" in summary["blockers"]
    assert "ligand_probe_is_ligand_only_not_full_complex" in summary["blockers"]
    assert payload["claim_boundary"]["ligand_only_probe_is_not_claim_grade"] is True


def test_cli_writes_probe_outputs_without_build(tmp_path: Path) -> None:
    input_csv = tmp_path / "rows.csv"
    out_json = tmp_path / "probe.json"
    out_md = tmp_path / "probe.md"
    _write_csv(input_csv, [{"target": "OTHER", "ligand_id": "L1"}])

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_gpcr_drd2_openmm_forcefield_parameterization_probe.py"),
            "--input-csv",
            str(input_csv),
            "--no-attempt-build",
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert payload["packet_type"] == "gpcr_drd2_openmm_forcefield_parameterization_probe"
    assert payload["summary"]["claim_grade_parameterization_ready"] is False
    assert "GPCR DRD2 OpenMM Forcefield Parameterization Probe" in out_md.read_text(encoding="utf-8")
