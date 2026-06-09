from __future__ import annotations

from tools.product import apply_aqp1_ready_workbook_rows as mod


def test_apply_aqp1_ready_workbook_rows_replaces_only_claim_safe_ready_row() -> None:
    intake_payload = {
        "rows": [
            {
                "packet_step": "core_binder_01",
                "intake_status": "claim_safe_approved",
            }
        ]
    }
    payload = mod.build_payload(
        reference_rows=[
            {
                "target": "AQP1_TRANSPORT_BLIND",
                "ligand_id": "aqp1_placeholder_binder_01",
                "reference_binding_kcal_mol": "",
                "is_binder": "1",
                "source": "template_placeholder_needs_curation",
            },
            {
                "target": "AQP1_TRANSPORT_BLIND",
                "ligand_id": "aqp1_placeholder_binder_02",
                "reference_binding_kcal_mol": "",
                "is_binder": "1",
                "source": "template_placeholder_needs_curation",
            },
        ],
        split_rows=[
            {"target": "AQP1_TRANSPORT_BLIND", "ligand_id": "aqp1_placeholder_binder_01", "role": "far_ood_eval"},
            {"target": "AQP1_TRANSPORT_BLIND", "ligand_id": "aqp1_placeholder_binder_02", "role": "far_ood_eval"},
        ],
        meta_rows=[
            {
                "ligand_id": "aqp1_placeholder_binder_01",
                "smiles": "O",
                "molecular_weight": "18.0",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "template_placeholder",
            },
            {
                "ligand_id": "aqp1_placeholder_binder_02",
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
                    "target": "AQP1_TRANSPORT_BLIND",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "aqp1_placeholder_binder_01",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_claim_safe",
                    "replacement_reference_binding_kcal_mol": "-8.2",
                    "replacement_is_binder": "1",
                    "replacement_source": "pubmed_direct_binding::PMID12345678::Kd_1200nM",
                    "replacement_role": "far_ood_eval",
                    "replacement_smiles": "C=C1",
                    "replacement_molecular_weight": "929.1",
                    "replacement_logp": "-0.1",
                    "replacement_h_donors": "10",
                    "replacement_h_acceptors": "18",
                    "replacement_rot_bonds": "10",
                    "replacement_scaffold": "bacopaside_scaffold",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                    "row_ready_for_apply": "yes",
                    "required_missing_fields": "",
                },
                {
                    "target": "AQP1_TRANSPORT_BLIND",
                    "packet_step": "core_binder_02",
                    "current_ligand_id": "aqp1_placeholder_binder_02",
                    "replacement_ligand_id": "",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                    "row_ready_for_apply": "no",
                    "required_missing_fields": "replacement_ligand_id",
                },
            ]
        },
        intake_payload=intake_payload,
    )

    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["newly_applied_row_count"] == 1
    assert payload["summary"]["after_reference_placeholder_rows"] == 1
    assert payload["updated_reference_rows"][0]["ligand_id"] == "aqp1_bacopaside_ii_claim_safe"
    assert payload["updated_reference_rows"][0]["reference_binding_kcal_mol"] == "-8.2"


def test_apply_aqp1_blocks_functional_surrogate_source_even_when_workbook_ready() -> None:
    payload = mod.build_payload(
        reference_rows=[
            {
                "target": "AQP1_TRANSPORT_BLIND",
                "ligand_id": "bacopaside_ii",
                "reference_binding_kcal_mol": "",
                "is_binder": "1",
                "source": "functional_ic50_derived_surrogate::PMID27474162::not_direct_binding_kcal",
            }
        ],
        split_rows=[{"target": "AQP1_TRANSPORT_BLIND", "ligand_id": "bacopaside_ii", "role": "far_ood_eval"}],
        meta_rows=[
            {
                "ligand_id": "bacopaside_ii",
                "smiles": "C=C1",
                "molecular_weight": "929.1",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "bacopaside_scaffold",
            }
        ],
        workbook_payload={
            "workbook_rows": [
                {
                    "target": "AQP1_TRANSPORT_BLIND",
                    "packet_step": "core_binder_01",
                    "current_ligand_id": "bacopaside_ii",
                    "replacement_ligand_id": "aqp1_bacopaside_ii_claim_safe",
                    "replacement_reference_binding_kcal_mol": "-6.47",
                    "replacement_is_binder": "1",
                    "replacement_source": "functional_ic50_derived_surrogate::PMID27474162::not_direct_binding_kcal",
                    "replacement_role": "far_ood_eval",
                    "replacement_smiles": "C=C1",
                    "replacement_molecular_weight": "929.1",
                    "replacement_logp": "",
                    "replacement_h_donors": "",
                    "replacement_h_acceptors": "",
                    "replacement_rot_bonds": "",
                    "replacement_scaffold": "bacopaside_scaffold",
                    "apply_reference_row": "yes",
                    "apply_split_row": "yes",
                    "apply_meta_row": "yes",
                    "row_ready_for_apply": "yes",
                    "required_missing_fields": "",
                }
            ]
        },
        intake_payload={
            "rows": [{"packet_step": "core_binder_01", "intake_status": "claim_safe_approved"}]
        },
    )

    assert payload["summary"]["applied_row_count"] == 0
    assert payload["blocked_rows"][0]["blocker"] == "claim_safe_direct_binding_kcal_required"


def test_apply_aqp1_ready_workbook_rows_is_idempotent_for_existing_replacement() -> None:
    workbook_payload = {
        "workbook_rows": [
            {
                "target": "AQP1_TRANSPORT_BLIND",
                "packet_step": "core_binder_01",
                "current_ligand_id": "aqp1_placeholder_binder_01",
                "replacement_ligand_id": "aqp1_bacopaside_ii_claim_safe",
                "replacement_reference_binding_kcal_mol": "-8.2",
                "replacement_is_binder": "1",
                "replacement_source": "pubmed_direct_binding::PMID12345678::Kd_1200nM",
                "replacement_role": "far_ood_eval",
                "replacement_smiles": "C=C1",
                "replacement_molecular_weight": "929.1",
                "replacement_logp": "",
                "replacement_h_donors": "",
                "replacement_h_acceptors": "",
                "replacement_rot_bonds": "",
                "replacement_scaffold": "bacopaside_scaffold",
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
                "target": "AQP1_TRANSPORT_BLIND",
                "ligand_id": "aqp1_bacopaside_ii_claim_safe",
                "reference_binding_kcal_mol": "-8.2",
                "is_binder": "1",
                "source": "pubmed_direct_binding::PMID12345678::Kd_1200nM",
            }
        ],
        split_rows=[
            {"target": "AQP1_TRANSPORT_BLIND", "ligand_id": "aqp1_bacopaside_ii_claim_safe", "role": "far_ood_eval"}
        ],
        meta_rows=[
            {
                "ligand_id": "aqp1_bacopaside_ii_claim_safe",
                "smiles": "C=C1",
                "molecular_weight": "929.1",
                "logp": "",
                "h_donors": "",
                "h_acceptors": "",
                "rot_bonds": "",
                "scaffold": "bacopaside_scaffold",
            }
        ],
        workbook_payload=workbook_payload,
        intake_payload={"rows": [{"packet_step": "core_binder_01", "intake_status": "claim_safe_approved"}]},
    )

    assert payload["summary"]["applied_row_count"] == 1
    assert payload["summary"]["already_applied_row_count"] == 1
    assert payload["applied_rows"][0]["apply_status"] == "already_applied"
