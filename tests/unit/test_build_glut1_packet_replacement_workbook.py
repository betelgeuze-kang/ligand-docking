from __future__ import annotations

from tools.product import build_glut1_packet_replacement_workbook as mod


def test_build_glut1_packet_replacement_workbook() -> None:
    payload = mod.build_payload(
        {
            "queue_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "binder_label": "binder",
                    "current_role": "far_ood_eval",
                    "current_reference_binding_kcal_mol": "-8.1",
                    "current_source": "template_placeholder_needs_curation",
                    "current_smiles": "OCC1OC(O)C(O)C(O)C1O",
                    "current_scaffold": "template_placeholder",
                    "placeholder_sources": "reference,meta",
                    "replacement_role": "far_ood_eval",
                }
            ]
        }
    )
    row = payload["workbook_rows"][0]
    assert payload["summary"]["workbook_row_count"] == 1
    assert row["replacement_is_binder"] == "1"
    assert "replacement_ligand_id" in row["required_missing_fields"]


def test_build_glut1_packet_replacement_workbook_prefills_claim_safe_row() -> None:
    payload = mod.build_payload(
        {
            "queue_rows": [
                {
                    "packet": "core",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "binder_label": "binder",
                    "current_role": "far_ood_eval",
                    "current_reference_binding_kcal_mol": "-8.1",
                    "current_source": "template_placeholder_needs_curation",
                    "current_smiles": "OCC1OC(O)C(O)C(O)C1O",
                    "current_scaffold": "template_placeholder",
                    "placeholder_sources": "reference,meta",
                    "replacement_role": "far_ood_eval",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_binder_01",
                    "replacement_ligand_id": "cytochalasin_b",
                    "replacement_reference_binding_kcal_mol": "-9.1683",
                    "replacement_is_binder": "1",
                    "replacement_source": "pubmed_direct_binding::PMID1716731::Kd_190_nM",
                    "replacement_role": "far_ood_eval",
                    "replacement_smiles": "C=C1",
                    "replacement_scaffold": "cytochalasin_macrocycle",
                    "row_ready_for_apply": "yes",
                }
            ]
        },
    )

    row = payload["workbook_rows"][0]
    assert payload["summary"]["ready_seed_row_count"] == 1
    assert row["replacement_ligand_id"] == "cytochalasin_b"
    assert row["row_ready_for_apply"] == "yes"
    assert row["required_missing_fields"] == ""
