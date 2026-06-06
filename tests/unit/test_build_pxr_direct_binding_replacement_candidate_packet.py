from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_pxr_direct_binding_replacement_candidate_packet as mod


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_pxr_direct_binding_replacement_candidate_packet_ranks_exact_human_binding_rows(
    tmp_path: Path,
) -> None:
    exact_review_packet = {
        "rows": [
            {
                "review_row_id": "pxr_review_a",
                "packet_step": "core_eval_non_binder_01",
                "candidate_name": "acetaminophen",
            },
            {
                "review_row_id": "pxr_review_b",
                "packet_step": "core_eval_non_binder_02",
                "candidate_name": "caffeine",
            },
        ]
    }
    _write(
        tmp_path / "chembl_activity_CHEMBL3401_assayB_Ki.json",
        {
            "activities": [
                {
                    "target_chembl_id": "CHEMBL3401",
                    "target_organism": "Homo sapiens",
                    "assay_type": "B",
                    "standard_relation": "=",
                    "standard_type": "Ki",
                    "standard_units": "nM",
                    "standard_value": "27.0",
                    "molecule_chembl_id": "CHEMBL1237210",
                    "molecule_pref_name": "HYPERFORIN",
                    "canonical_smiles": "CC",
                    "activity_id": "2532000",
                    "assay_chembl_id": "CHEMBL1012196",
                    "document_chembl_id": "CHEMBL1148111",
                    "assay_description": "Displacement of [3H]SR12813 from human PXR",
                },
                {
                    "target_chembl_id": "CHEMBL3401",
                    "target_organism": "Mus musculus",
                    "assay_type": "B",
                    "standard_relation": "=",
                    "standard_type": "Ki",
                    "standard_units": "nM",
                    "standard_value": "1.0",
                    "molecule_chembl_id": "CHEMBL_BAD",
                },
            ]
        },
    )
    _write(
        tmp_path / "chembl_activity_CHEMBL3401_assayB_Kd.json",
        {
            "activities": [
                {
                    "target_chembl_id": "CHEMBL3401",
                    "target_organism": "Homo sapiens",
                    "assay_type": "B",
                    "standard_relation": "=",
                    "standard_type": "Kd",
                    "standard_units": "nM",
                    "standard_value": "22.3",
                    "molecule_chembl_id": "CHEMBL6167089",
                    "canonical_smiles": "CCC",
                    "activity_id": "29239870",
                    "assay_chembl_id": "CHEMBL6130608",
                    "document_chembl_id": "CHEMBL6127111",
                    "assay_description": "Displacement of BODIPY FL-probe from GST-tagged PXR LBD",
                }
            ]
        },
    )

    payload = mod.build_payload(exact_review_packet=exact_review_packet, source_dir=tmp_path, top_n=2)

    summary = payload["summary"]
    assert summary["status"] == "pxr_direct_binding_replacement_candidates_ready"
    assert summary["replacement_candidate_packet_ready"] is True
    assert summary["direct_binding_candidate_count"] == 2
    assert summary["selected_claim_safe_candidate_count"] == 2
    assert summary["first_replacement_molecule_chembl_id"] == "CHEMBL6167089"
    rows = payload["rows"]
    assert rows[0]["replacement_for_current_candidate_name"] == "acetaminophen"
    assert rows[0]["standard_type"] == "Kd"
    assert rows[0]["reference_binding_kcal_mol"] == "-10.4388"
    assert rows[0]["target_match_confirmed"] is True
    assert rows[0]["assay_is_direct_or_claim_safe"] is True
    assert rows[1]["replacement_ligand_id"] == "hyperforin"
