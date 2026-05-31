from __future__ import annotations

import csv
import json
from pathlib import Path

from tools import build_casp17_historical_seed_complex_source_authority_candidates as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "HEADER    TEST\n"
        "ATOM      1  N   GLY A   1       0.0   0.0   0.0  1.00 20.00           N\n"
        "ATOM      2  CA  GLY A   1       1.0   0.0   0.0  1.00 20.00           C\n"
        "END\n",
        encoding="utf-8",
    )


def test_complex_source_authority_candidates_link_rcsb_and_homolog_ligand_sources(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    protein_pdb = tmp_path / "data/public_structures/selected_allatom_native_v1/t_cruzi_pde_pdb_3V94.pdb"
    complex_pdb = tmp_path / "runs/complex/01/protein_ligand_complex.pdb"
    minimized_pdb = tmp_path / "runs/complex/01/protein_ligand_complex_minimized.pdb"
    _write_pdb(protein_pdb)
    _write_pdb(complex_pdb)
    _write_pdb(minimized_pdb)
    seed_json = tmp_path / "seed.json"
    _write_json(
        seed_json,
        {
            "rows": [
                {
                    "seed_rank": 11,
                    "batch_slot": 11,
                    "target_id": "HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005",
                    "benchmark_id": "hist_seed_complex",
                    "scope": "complex",
                    "target_label": "01_tcruzi_pde_external_pdeb1_010_chembl4453005",
                    "native_pdb": str(complex_pdb.relative_to(tmp_path)),
                    "prediction_pdb": str(minimized_pdb.relative_to(tmp_path)),
                }
            ]
        },
    )
    parameterization_json = tmp_path / "parameterization.json"
    _write_json(
        parameterization_json,
        {
            "summary": {
                "native_pdb": str(protein_pdb.relative_to(tmp_path)),
                "native_chain_id": "B",
            },
            "rows": [
                {
                    "ligand_id": "tcruzi_pde_external_pdeb1_010_chembl4453005",
                    "parameterization_status": "integrated_openmm_system_ready",
                    "protein_local_minimization_status": "pass",
                    "local_minimization_survival_fraction": 1.0,
                    "ligand_heavy_atom_rmsd_A": 1.2,
                    "mean_min_distance_A": 7.3,
                    "contact_fraction": 0.4,
                }
            ],
        },
    )
    chembl_csv = tmp_path / "chembl.csv"
    _write_csv(
        chembl_csv,
        [
            {
                "ligand_id": "tcruzi_pde_external_pdeb1_010_chembl4453005",
                "source_dataset": "ChEMBL",
                "source_anchor": "TbrPDEB1 homolog activity",
                "molecule_chembl_id": "CHEMBL4453005",
                "target_chembl_ids": "CHEMBL2010636",
                "target_organisms": "Trypanosoma brucei",
                "target_pref_names": "Class 1 phosphodiesterase PDEB1",
                "document_chembl_ids": "CHEMBL4402584",
                "assay_chembl_ids": "CHEMBL4405037",
                "standard_types": "Ki",
                "best_document_year": "2020",
                "best_assay_description": "Inhibition of Trypanosoma brucei PDEB1",
                "direct_tcruzi_pde_evidence": "False",
                "homolog_seed_only": "True",
            }
        ],
    )
    args = mod.parse_args(
        [
            "--seed-inventory-json",
            str(seed_json),
            "--parameterization-json",
            str(parameterization_json),
            "--chembl-seed-csv",
            str(chembl_csv),
            "--bindingdb-seed-csv",
            str(tmp_path / "missing_bindingdb.csv"),
            "--out-json",
            str(tmp_path / "out.json"),
            "--out-csv",
            str(tmp_path / "out.csv"),
            "--out-md",
            str(tmp_path / "out.md"),
            "--out-dir",
            str(tmp_path / "folders"),
        ]
    )

    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["complex_source_authority_candidate_status"] == (
        "complex_homolog_source_authority_candidates_ready_claim_limited"
    )
    assert summary["operator_review_ready_count"] == 1
    assert summary["homolog_source_authority_ready_count"] == 1
    assert summary["direct_source_authority_ready_count"] == 0
    assert summary["operator_apply_allowed_count"] == 0
    row = payload["rows"][0]
    assert row["candidate_status"] == "operator_homolog_source_authority_review_ready"
    assert "rcsb:3V94" in row["native_authority_ref_candidate"]
    assert "chembl_molecule:CHEMBL4453005" in row["native_authority_ref_candidate"]
    assert row["blockers"] == "direct_tcruzi_pde_evidence_absent_homolog_seed_only"
    assert (tmp_path / "folders/11_hist_complex_01_tcruzi_pde_external_pdeb1_010_chembl4453005/SOURCE_AUTHORITY.md").exists()
