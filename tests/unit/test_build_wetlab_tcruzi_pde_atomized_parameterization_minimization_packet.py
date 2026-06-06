from __future__ import annotations

import json
from pathlib import Path

from tools.wetlab import build_wetlab_tcruzi_pde_atomized_parameterization_minimization_packet as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_extract_chain_pdb_keeps_requested_chain_only(tmp_path: Path) -> None:
    native = tmp_path / "native.pdb"
    out = tmp_path / "chain_b.pdb"
    native.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY A   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  GLY B   1       1.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  ALA B   2       2.000   0.000   0.000  1.00 20.00           C",
                "ATOM      4  CA  SER B   3       3.000   0.000   0.000  1.00 20.00           C",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    info = mod._extract_chain_pdb(native, out, chain_id="B")

    text = out.read_text(encoding="utf-8")
    assert info["ready"] is True
    assert info["ca_count"] == 3
    assert " GLY A " not in text
    assert text.count(" CA ") == 3


def test_build_payload_counts_parameterized_and_minimized_rows(monkeypatch, tmp_path: Path) -> None:
    draft = tmp_path / "draft.json"
    native = tmp_path / "native.pdb"
    ligand = tmp_path / "ligand.pdb"
    sdf = tmp_path / "ligand.sdf"
    ligand.write_text("HETATM    1  C1  UNL     1       0.000   0.000   0.000  1.00  0.00           C\nEND\n")
    sdf.write_text("", encoding="utf-8")
    native.write_text(
        "\n".join(
            [
                "ATOM      1  CA  GLY B   1       0.000   0.000   0.000  1.00 20.00           C",
                "ATOM      2  CA  ALA B   2       1.000   0.000   0.000  1.00 20.00           C",
                "ATOM      3  CA  SER B   3       2.000   0.000   0.000  1.00 20.00           C",
                "END",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(
        draft,
        {
            "rows": [
                {
                    "ligand_id": "lig_a",
                    "atomized_ligand_pdb": str(ligand),
                    "atomized_ligand_sdf": str(sdf),
                    "ligand_smiles": "C",
                }
            ]
        },
    )

    def fake_parameterize(**kwargs):
        row = dict(kwargs["row"])
        return {
            **row,
            "parameterization_status": "integrated_openmm_system_ready",
            "protein_local_minimization_status": "pass",
            "parameterization_ready": True,
            "protein_local_minimization_ready": True,
            "local_minimization_survival_fraction": 1.0,
            "ligand_heavy_atom_rmsd_A": 0.2,
            "mean_min_distance_A": 1.4,
            "contact_fraction": 0.9,
            "blockers": [],
        }

    monkeypatch.setattr(mod, "_parameterize_and_minimize", fake_parameterize)

    payload = mod.build_payload(
        draft_json=draft,
        native_pdb=native,
        out_dir=tmp_path / "out",
        generated_at_local="2026-05-17T00:00:00+09:00",
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_tcruzi_pde_atomized_parameterization_minimization_pass"
    assert summary["parameterization_ready_count"] == 1
    assert summary["protein_local_minimization_ready_count"] == 1
    assert summary["validated_repair_count"] == 1
    assert summary["best_validated_ligand_id"] == "lig_a"
    assert summary["claim_promotion_allowed"] is False
    assert payload["claim_boundary"]["commercial_repair_evidence_allowed"] is True
