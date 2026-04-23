from __future__ import annotations

from tools import build_ca2_review_only_negative_packet as mod


def _contains_tokens(text: str, *tokens: str) -> None:
    lowered = text.lower()
    for token in tokens:
        assert token.lower() in lowered


def test_build_ca2_review_only_negative_packet_payload_and_checklist() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "next_required_step": "Keep the remaining CA2 negative-like rows review-only.",
            },
            "rows": [
                {
                    "priority_rank": "4",
                    "packet": "core",
                    "packet_step": "core_non_binder_01",
                    "replacement_ligand_id": "acetaminophen",
                    "disposition": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                },
                {
                    "priority_rank": "10",
                    "packet": "ood",
                    "packet_step": "ood_non_binder_01",
                    "replacement_ligand_id": "aspirin",
                    "disposition": "review_only_negative_evidence",
                    "promotion_blocker": "no_quantitative_nonbinder_value_curated",
                    "next_required_action": "manual_negative_evidence_review",
                },
            ],
        },
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "review_reason": "keep_core_negative_like_rows_review_only",
                    "assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                }
            ]
        },
        {
            "summary": {
                "most_common_missing_field": "replacement_reference_binding_kcal_mol",
            },
            "workbook_rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "missing_fields": "replacement_reference_binding_kcal_mol",
                },
                {
                    "packet_step": "ood_non_binder_01",
                    "missing_fields": "replacement_reference_binding_kcal_mol",
                },
            ],
        },
        [
            {
                "packet_step": "core_non_binder_01",
                "replacement_source": "pubchem_name_resolve_pending::generic_negative_seed",
                "replacement_smiles": "CC(=O)Nc1ccc(O)cc1",
                "replacement_scaffold": "c1ccccc1",
            },
            {
                "packet_step": "ood_non_binder_01",
                "replacement_source": "pubchem_name_resolve_pending::generic_negative_seed",
                "replacement_smiles": "CC(=O)Oc1ccccc1C(=O)O",
                "replacement_scaffold": "c1ccccc1",
            },
        ],
        {
            "rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "capture_status": "captured_direct_conflict_review_only",
                    "manual_assay_type_honesty": "review_only_negative_conflict_with_weak_activity",
                    "manual_promotion_blocker": "direct_ca2_inhibitor_conflict_present",
                    "manual_next_required_action": "keep_review_only_conflict_documented",
                    "source_title": "Paracetamol weak CA2 conflict paper",
                    "source_id": "PMID:18579385",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/18579385/",
                    "manual_decision_note": "Keep review-only due to direct CA2 conflict.",
                },
                {
                    "packet_step": "ood_non_binder_01",
                    "capture_status": "captured_no_direct_negative_source_found",
                    "manual_promotion_blocker": "no_direct_ca2_negative_evidence_located_after_research",
                    "manual_next_required_action": "keep_review_only_no_direct_negative_source",
                    "source_title": "Aspirin CA2 review anchor",
                    "source_id": "PMCID:PMC7226357",
                    "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7226357/",
                    "manual_decision_note": "Keep review-only due to cited aspirin CA2 activity.",
                },
            ],
            "slot_summary": [
                {
                    "packet_step": "core_non_binder_01",
                    "hint_count": 2,
                    "recommended_next_move": "Prefer exact local curated candidate review",
                }
            ],
            "hint_rows": [
                {
                    "packet_step": "core_non_binder_01",
                    "evidence_strength": "exact_smiles_local_curated",
                    "candidate_ligand_id": "acetaminophen",
                    "repo_source_path": "config/ligand_meta_blind_aqp1_v1.csv",
                }
            ],
        },
    )

    assert payload["summary"]["family"] == "ca2"
    assert payload["summary"]["review_only_row_count"] == 2
    assert payload["summary"]["core_review_only_count"] == 1
    assert payload["summary"]["ood_review_only_count"] == 1
    assert payload["summary"]["high_conflict_row_count"] == 1
    assert payload["summary"]["rows_with_cited_source"] == 2
    assert payload["summary"]["rows_with_local_exact_match_hint"] == 1
    rows = {row["packet_step"]: row for row in payload["rows"]}
    assert rows["core_non_binder_01"]["operator_review_bucket"] == "conflict_review"
    assert rows["ood_non_binder_01"]["operator_review_bucket"] == "standard_review"
    assert rows["core_non_binder_01"]["authoritative_apply_allowed_now"] == "no"
    assert rows["core_non_binder_01"]["source_id"] == "PMID:18579385"
    assert rows["core_non_binder_01"]["local_exact_match_hint_count"] == 1
    assert rows["core_non_binder_01"]["local_exact_match_candidate_ids"] == "acetaminophen"
    assert "Conflict anchor PMID:18579385" in rows["core_non_binder_01"]["blocker_action_summary"]
    _contains_tokens(rows["core_non_binder_01"]["operator_note_template"], "keep", "review-only")

    checklist = mod.build_checklist(payload)
    assert len(checklist) == 5
    assert checklist[0]["check_id"] == "confirm_policy_lock"
    assert checklist[2]["applies_to"] == "core_non_binder_01"
