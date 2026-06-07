from __future__ import annotations

from tools.product import apply_glut1_ready_workbook_rows as mod


def test_apply_glut1_ready_workbook_rows_replaces_only_ready_synchronized_row() -> None:
    payload = mod.build_payload(
        reference_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "ligand_id": "glut1_placeholder_binder_01",
                "reference_binding_kcal_mol": "-8.1",
                "is_binder": "1",
                "source": "template_placeholder_needs_curation",
            },
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "ligand_id": "glut1_placeholder_binder_02",
                "reference_binding_kcal_mol": "-7.7",
                "is_binder": "1",
                "source": "template_placeholder_needs_curation",
            },
        ],
        split_rows=[
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_01", "role": "far_ood_eval"},
            {"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "glut1_placeholder_binder_02", "role": "far_ood_eval"},
        ],
        meta_rows=[
            {
                "ligand_id": "glut1_placeholder_binder_01",
                "smiles": "O",
                "molecular_weight": "18.0",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "template_placeholder",
            },
            {
                "ligand_id": "glut1_placeholder_binder_02",
                "smiles": "CC",
                "molecular_weight": "30.0",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "template_placeholder",
            },
        ],
        workbook_payload={
            "workbook_rows": [
                {
                    "target": "GLUT1_TRANSPORT_BLIND",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "glut1_placeholder_binder_01",
                    "replacement_ligand_id": "cytochalasin_b",
                    "replacement_reference_binding_kcal_mol": "-9.1694",
                    "replacement_is_binder": "1",
                    "replacement_source": "pubmed_direct_binding::PMID1716731",
                    "replacement_role": "far_ood_eval",
                    "replacement_smiles": "C=C1",
                    "replacement_molecular_weight": "479.6",
                    "replacement_logp": "",
                    "replacement_h_donors": "",
                    "replacement_h_acceptors": "",
                    "replacement_rot_bonds": "",
                    "replacement_scaffold": "cytochalasin_macrocycle",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                    "row_ready_for_apply": "yes",
                    "required_missing_fields": "",
                },
                {
                    "target": "GLUT1_TRANSPORT_BLIND",
                    "packet_step": "core_binder_02",
                    "current_ligand_id": "glut1_placeholder_binder_02",
                    "replacement_ligand_id": "",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                    "row_ready_for_apply": "no",
                    "required_missing_fields": "replacement_ligand_id",
                },
            ]
        },
    )

    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["newly_applied_row_count"] == 1
    assert payload["summary"]["already_applied_row_count"] == 0
    assert payload["summary"]["after_reference_placeholder_rows"] == 1
    assert payload["summary"]["after_split_placeholder_rows"] == 1
    assert payload["summary"]["after_meta_placeholder_rows"] == 1
    assert payload["summary"]["full_packet_ready_after_apply"] is False
    assert payload["updated_reference_rows"][0]["ligand_id"] == "cytochalasin_b"
    assert payload["updated_split_rows"][0]["ligand_id"] == "cytochalasin_b"
    assert payload["updated_meta_rows"][0]["ligand_id"] == "cytochalasin_b"


def test_apply_glut1_ready_workbook_rows_is_idempotent_for_existing_replacement() -> None:
    workbook_payload = {
        "workbook_rows": [
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "packet_step": "core_binder_01",
                "current_ligand_id": "glut1_placeholder_binder_01",
                "replacement_ligand_id": "cytochalasin_b",
                "replacement_reference_binding_kcal_mol": "-9.1694",
                "replacement_is_binder": "1",
                "replacement_source": "pubmed_direct_binding::PMID1716731",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "C=C1",
                "replacement_molecular_weight": "479.6",
                "replacement_logp": "",
                "replacement_h_donors": "",
                "replacement_h_acceptors": "",
                "replacement_rot_bonds": "",
                "replacement_scaffold": "cytochalasin_macrocycle",
                "apply_reference_row": "yes",
                "apply_split_row": "yes",
                "apply_meta_row": "yes",
                "row_ready_for_apply": "yes",
                "required_missing_fields": "",
            }
        ]
    }

    payload = mod.build_payload(
        reference_rows=[
            {
                "target": "GLUT1_TRANSPORT_BLIND",
                "ligand_id": "cytochalasin_b",
                "reference_binding_kcal_mol": "-9.1694",
                "is_binder": "1",
                "source": "pubmed_direct_binding::PMID1716731",
            }
        ],
        split_rows=[{"target": "GLUT1_TRANSPORT_BLIND", "ligand_id": "cytochalasin_b", "role": "far_ood_eval"}],
        meta_rows=[
            {
                "ligand_id": "cytochalasin_b",
                "smiles": "C=C1",
                "molecular_weight": "479.6",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "cytochalasin_macrocycle",
            }
        ],
        workbook_payload=workbook_payload,
    )

    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["newly_applied_row_count"] == 0
    assert payload["summary"]["already_applied_row_count"] == 1
    assert payload["applied_rows"][0]["apply_status"] == "already_applied"
