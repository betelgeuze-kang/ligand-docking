from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tools.gpcr_replay import build_gpcr_drd2_full_forcefield_local_minimization_survival as mod


def test_rmsd_A_is_absolute_heavy_atom_rmsd() -> None:
    ref = np.asarray([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    mob = np.asarray([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])

    assert mod._rmsd_A(ref, mob) == np.sqrt(0.5)


def test_build_survival_packet_records_claim_grade_pass(monkeypatch, tmp_path: Path) -> None:
    probe = tmp_path / "parameterization.json"
    probe.write_text(
        json.dumps(
            {
                "capability_probes": {
                    "integrated_protein_ligand_openmm": {
                        "complex_pdb": "complex.pdb",
                        "ligand_template_xml": "lig.xml",
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mod,
        "_run_full_forcefield_minimization",
        lambda **kwargs: {
            "attempted": True,
            "ready": True,
            "ligand_heavy_atom_rmsd_A": 0.42,
            "particle_count": 10,
        },
    )

    payload = mod.build_survival_packet(
        parameterization_probe_json=probe,
        generated_at_local="2026-05-06T00:00:00+09:00",
    )

    summary = payload["summary"]
    row = payload["rows"][0]
    assert summary["status"] == "full_forcefield_local_minimization_survival_pass"
    assert summary["hard_decoy_rebuild_evidence_allowed"] is True
    assert row["target"] == "CHEMBL217_DRD2_HUMAN"
    assert row["ligand_id"] == "CHEMBL301265"
    assert row["survival_fraction"] == 1.0
    assert row["survival_claim_scope"] == "full_protein_ligand_forcefield_restrained_receptor"
    assert payload["claim_boundary"]["claim_promotion_allowed"] is False
