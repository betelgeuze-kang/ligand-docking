from __future__ import annotations

import json
from pathlib import Path

from tools.build_wetlab_tcruzi_pde_external_pdeb1_seed_packet import build_payload


def _write_raw(path: Path, activities: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"activities": activities}), encoding="utf-8")


def test_external_pdeb1_seed_packet_aggregates_quantitative_homolog_seed_rows(tmp_path: Path) -> None:
    raw = tmp_path / "chembl_tbrucei.json"
    _write_raw(
        raw,
        [
            {
                "molecule_chembl_id": "CHEMBL_A",
                "canonical_smiles": "CCOc1ccc(C2=NNC(=O)C2)cc1",
                "standard_relation": "=",
                "standard_units": "nM",
                "standard_type": "IC50",
                "standard_value": "40",
                "pchembl_value": "7.4",
                "target_chembl_id": "CHEMBL2010636",
                "target_organism": "Trypanosoma brucei",
                "target_pref_name": "Class 1 phosphodiesterase PDEB1",
                "document_chembl_id": "CHEMBL_DOC",
                "assay_chembl_id": "CHEMBL_ASSAY",
                "assay_description": "Inhibition of recombinant TbrPDEB1.",
                "document_year": 2018,
            },
            {
                "molecule_chembl_id": "CHEMBL_B",
                "canonical_smiles": "CCN",
                "standard_relation": "=",
                "standard_units": "nM",
                "standard_type": "IC50",
                "standard_value": "500",
                "pchembl_value": "6.3",
                "target_chembl_id": "CHEMBL2010636",
                "target_organism": "Trypanosoma brucei",
                "target_pref_name": "Class 1 phosphodiesterase PDEB1",
            },
            {
                "molecule_chembl_id": "CHEMBL_BAD",
                "canonical_smiles": "CCO",
                "standard_relation": ">",
                "standard_units": "nM",
                "standard_value": "10",
            },
        ],
    )

    payload = build_payload(tbrucei_raw_jsons=[str(raw)], lmajor_raw_jsons=[], top_n=2)

    summary = payload["summary"]
    assert summary["status"] == "wetlab_tcruzi_pde_external_pdeb1_seed_packet_ready"
    assert summary["claim_promotion_allowed"] is False
    assert summary["direct_tcruzi_pde_evidence_count"] == 0
    assert summary["quantitative_seed_count"] == 2
    assert summary["top_seed_molecule_chembl_id"] == "CHEMBL_A"
    assert summary["top_seed_min_standard_value_nM"] == 40.0

    first = payload["rows"][0]
    assert first["ligand_id"].startswith("tcruzi_pde_external_pdeb1_001_chembl_a")
    assert first["homolog_seed_only"] is True
    assert first["direct_tcruzi_pde_evidence"] is False
    assert first["claim_policy"] == "seed_for_candidate_pool_expansion_not_direct_tcruzi_pde_claim"
    assert first["target_organisms"] == "Trypanosoma brucei"
