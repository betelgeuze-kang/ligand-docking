from __future__ import annotations

import json
from pathlib import Path

from tools.wetlab.build_wetlab_tcruzi_pde_bindingdb_similarity_seed_packet import build_payload


def _write_raw(path: Path, affinities: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"getLindsByUniprotResponse": {"bdb.affinities": affinities}}), encoding="utf-8")


def test_bindingdb_similarity_seed_packet_aggregates_claim_safe_rows(tmp_path: Path) -> None:
    _write_raw(
        tmp_path / "bindingdb_similarity_tcruzi_pde_external_pdeb1_010_chemblx_raw.json",
        [
            {
                "bdb.monomerid": 50527537,
                "bdb.smiles": "[H]C1CC1 |r,c:1|",
                "bdb.affinity": " 31",
                "bdb.affinity_type": "Ki",
                "bdb.species": "Trypanosoma brucei",
                "bdb.target": "Phosphodiesterase",
            },
            {
                "bdb.monomerid": 50527537,
                "bdb.smiles": "[H]C1CC1 |r,c:1|",
                "bdb.affinity": " 0.154",
                "bdb.affinity_type": "Ki",
                "bdb.species": "Human",
                "bdb.target": "cAMP-specific phosphodiesterase 4D",
            },
            {
                "bdb.monomerid": 777,
                "bdb.smiles": "COC",
                "bdb.affinity": " 160",
                "bdb.affinity_type": "IC50",
                "bdb.species": "Trypanosoma brucei",
                "bdb.target": "Phosphodiesterase",
            },
        ],
    )

    payload = build_payload(str(tmp_path / "bindingdb_similarity_*_raw.json"))
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "wetlab_tcruzi_pde_bindingdb_similarity_seed_packet_ready"
    assert summary["claim_promotion_allowed"] is False
    assert summary["direct_tcruzi_pde_evidence_count"] == 0
    assert summary["raw_json_count"] == 1
    assert summary["raw_affinity_row_count"] == 3
    assert summary["quantitative_seed_count"] == 2
    assert summary["tbrucei_pde_seed_count"] == 2
    assert rows[0]["bindingdb_monomer_id"] == "50527537"
    assert rows[0]["ligand_id"].startswith("tcruzi_pde_bindingdb_pdeb1_001_bdb")
    assert rows[0]["smiles"] == "C1CC1"
    assert rows[0]["best_affinity_nM"] == 0.154
    assert rows[0]["tbrucei_pde_activity_count"] == 1
    assert rows[0]["homolog_seed_only"] is True
    assert rows[0]["direct_tcruzi_pde_evidence"] is False
