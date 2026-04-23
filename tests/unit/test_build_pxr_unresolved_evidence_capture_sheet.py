from __future__ import annotations

from tools import build_pxr_unresolved_evidence_capture_sheet as mod


def test_build_pxr_unresolved_evidence_capture_sheet_promotes_gap_row_with_supportive_overlay() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "review_reason": "binder gap",
                    "assay_type_honesty": "no_local_target_activity_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": 1,
                    "priority_rank": 10,
                    "commit_class": "must_remain_deferred",
                    "resolution_bias": "defer",
                    "staged_assay_type_honesty": "no_local_target_activity_curated",
                    "staged_promotion_blocker": "no_local_target_activity_curated",
                    "staged_next_required_action": "manual_curated_search_or_defer",
                    "commit_note": "keep deferred",
                }
            ]
        },
        {"summary": {"review_only_rows": [], "defer_rows": ["bexarotene"], "policy_line": "keep deferred"}},
        existing_sheet={
            "ood_fit_binder_01": {
                "packet_step": "ood_fit_binder_01",
                "capture_status": "captured_gap",
                "supports_local_target_specific_human_pxr": "no",
                "source_title": "Old gap source",
                "source_url": "https://example.org/gap",
                "manual_promotion_blocker": "no_local_target_activity_curated",
                "commit_status": "confirmed_defer",
            }
        },
        overlay_payload={
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "capture_status": "captured_supportive",
                    "supports_local_target_specific_human_pxr": "yes",
                    "source_title": "PMID 18544536",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "source_note": "literature support",
                    "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                    "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                    "manual_next_required_action": "curate_quantitative_binding_value",
                    "manual_commit_note": "confirmed_defer",
                    "commit_status": "confirmed_defer",
                }
            ]
        },
    )

    row = payload["rows"][0]
    assert row["capture_status"] == "captured_supportive"
    assert row["supports_local_target_specific_human_pxr"] == "yes"
    assert row["source_title"] == "PMID 18544536"
    assert row["manual_promotion_blocker"] == "quantitative_binding_value_or_activity_proxy_missing"
    assert row["manual_next_required_action"] == "curate_quantitative_binding_value"
    assert payload["summary"]["supportive_target_specific_human_count"] == 1


def test_build_pxr_unresolved_evidence_capture_sheet_allows_supportive_quantitative_gap_upgrade() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "review_reason": "binder support with quantitative proxy",
                    "assay_type_honesty": "activity_present_manual_confirmation_required",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "binder": 1,
                    "priority_rank": 10,
                    "commit_class": "must_remain_deferred",
                    "resolution_bias": "defer",
                    "staged_assay_type_honesty": "activity_present_manual_confirmation_required",
                    "staged_promotion_blocker": "activity_present_manual_confirmation_required",
                    "staged_next_required_action": "manual_curated_search_or_defer",
                    "commit_note": "keep deferred pending manual confirmation",
                }
            ]
        },
        {"summary": {"review_only_rows": [], "defer_rows": ["bexarotene"], "policy_line": "keep deferred"}},
        existing_sheet={
            "ood_fit_binder_01": {
                "packet_step": "ood_fit_binder_01",
                "capture_status": "captured_supportive",
                "supports_local_target_specific_human_pxr": "yes",
                "source_title": "PMID 18544536",
                "source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                "manual_promotion_blocker": "quantitative_binding_value_or_activity_proxy_missing",
                "manual_assay_type_honesty": "literature_confirmed_target_specific_human_pxr_binder_quantitative_value_missing",
                "manual_next_required_action": "curate_quantitative_binding_value",
                "commit_status": "confirmed_defer",
            }
        },
        overlay_payload={
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "capture_status": "captured_supportive",
                    "supports_local_target_specific_human_pxr": "yes",
                    "source_title": "PubChem CID 82146 human PXR qHTS summary for bexarotene.",
                    "source_url": "https://pubchem.ncbi.nlm.nih.gov/bioassay/1346982",
                    "source_note": "AID 1346982 potency 19.3312 uM; conflicting inactive rows remain.",
                    "manual_assay_type_honesty": "activity_present_manual_confirmation_required",
                    "manual_promotion_blocker": "activity_present_manual_confirmation_required",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "manual_commit_note": "confirmed_defer",
                    "commit_status": "confirmed_defer",
                }
            ]
        },
    )

    row = payload["rows"][0]
    assert row["capture_status"] == "captured_supportive"
    assert row["source_title"] == "PubChem CID 82146 human PXR qHTS summary for bexarotene."
    assert row["manual_assay_type_honesty"] == "activity_present_manual_confirmation_required"
    assert row["manual_promotion_blocker"] == "activity_present_manual_confirmation_required"
    assert row["manual_next_required_action"] == "manual_curated_search_or_defer"


def test_build_pxr_unresolved_evidence_capture_sheet_refreshes_base_reason_and_honesty_from_overlay() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_02",
                    "review_reason": "old gap note",
                    "assay_type_honesty": "no_local_target_activity_curated",
                    "next_required_action": "manual_curated_search_or_defer",
                }
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_02",
                    "ligand": "caffeine",
                    "binder": 0,
                    "priority_rank": 6,
                    "commit_class": "must_remain_deferred",
                    "resolution_bias": "defer",
                    "staged_assay_type_honesty": "no_local_target_activity_curated",
                    "staged_promotion_blocker": "no_local_target_activity_curated",
                    "staged_next_required_action": "manual_curated_search_or_defer",
                    "commit_note": "keep deferred",
                }
            ]
        },
        {"summary": {"review_only_rows": ["ibuprofen"], "defer_rows": ["caffeine"], "policy_line": "keep deferred"}},
        existing_sheet={
            "core_eval_non_binder_02": {
                "packet_step": "core_eval_non_binder_02",
                "capture_status": "captured_gap",
                "review_reason": "old gap note",
                "assay_type_honesty": "no_local_target_activity_curated",
                "manual_promotion_blocker": "no_local_target_activity_curated",
                "commit_status": "confirmed_defer",
            }
        },
        overlay_payload={
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_02",
                    "capture_status": "captured_conflict",
                    "supports_local_target_specific_human_pxr": "yes",
                    "source_title": "PubChem CID 2519 human PXR qHTS summary for caffeine.",
                    "source_url": "https://pubchem.ncbi.nlm.nih.gov/bioassay/1346982",
                    "source_note": "PubChem human PXR active plus inactive rows exist for caffeine.",
                    "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "manual_commit_note": "confirmed_defer",
                    "commit_status": "confirmed_defer",
                }
            ]
        },
    )

    row = payload["rows"][0]
    assert row["review_reason"] == "PubChem human PXR active plus inactive rows exist for caffeine."
    assert row["assay_type_honesty"] == "activity_proxy_conflicts_with_non_binder"
    assert row["capture_status"] == "captured_conflict"
    assert row["manual_promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"


def test_build_pxr_unresolved_evidence_capture_sheet_prefers_existing_source_note_after_conflict_is_already_captured() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_02",
                    "ligand": "caffeine",
                    "binder": 0,
                    "priority_rank": 6,
                    "commit_class": "must_remain_deferred",
                    "resolution_bias": "defer",
                    "staged_assay_type_honesty": "no_local_target_activity_curated",
                    "staged_promotion_blocker": "no_local_target_activity_curated",
                    "staged_next_required_action": "manual_curated_search_or_defer",
                    "commit_note": "keep deferred",
                }
            ]
        },
        {"summary": {"review_only_rows": ["ibuprofen"], "defer_rows": ["caffeine"], "policy_line": "keep deferred"}},
        existing_sheet={
            "core_eval_non_binder_02": {
                "packet_step": "core_eval_non_binder_02",
                "capture_status": "captured_conflict",
                "source_note": "Existing PubChem caffeine conflict note.",
                "assay_type_honesty": "no_local_target_activity_curated",
                "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                "commit_status": "confirmed_defer",
            }
        },
        overlay_payload={"rows": []},
    )

    row = payload["rows"][0]
    assert row["review_reason"] == "Existing PubChem caffeine conflict note."
    assert row["assay_type_honesty"] == "activity_proxy_conflicts_with_non_binder"


def test_build_pxr_unresolved_evidence_capture_sheet_refreshes_existing_conflict_from_overlay() -> None:
    payload = mod.build_payload(
        {"rows": []},
        {
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "binder": 0,
                    "priority_rank": 5,
                    "commit_class": "must_remain_deferred",
                    "resolution_bias": "defer",
                    "staged_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "staged_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "staged_next_required_action": "manual_curated_search_or_defer",
                    "commit_note": "keep deferred",
                }
            ]
        },
        {"summary": {"review_only_rows": ["ibuprofen"], "defer_rows": ["acetaminophen"], "policy_line": "keep deferred"}},
        existing_sheet={
            "core_eval_non_binder_01": {
                "packet_step": "core_eval_non_binder_01",
                "capture_status": "captured_conflict",
                "source_note": "Old reversed note.",
                "assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                "commit_status": "confirmed_defer",
            }
        },
        overlay_payload={
            "rows": [
                {
                    "packet_step": "core_eval_non_binder_01",
                    "capture_status": "captured_conflict",
                    "supports_local_target_specific_human_pxr": "yes",
                    "source_title": "ChEMBL CHEMBL3401 activity query for acetaminophen returned 2 records.",
                    "source_url": "https://www.ebi.ac.uk/chembl/api/data/activity.json?molecule_chembl_id=CHEMBL112&target_chembl_id=CHEMBL3401&limit=20",
                    "source_note": "Antagonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 =23999.9 nM; CHEMBL5291845 / CHEMBL5291721); Agonist activity at human NR1I2 in an in vitro cell free assay measured by time-resolved fluorescence resonance energy transfer method (AC50 >30000.0 nM; CHEMBL5291844 / CHEMBL5291721).",
                    "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "manual_next_required_action": "manual_curated_search_or_defer",
                    "manual_commit_note": "confirmed_defer",
                    "commit_status": "confirmed_defer",
                }
            ]
        },
    )

    row = payload["rows"][0]
    assert row["capture_status"] == "captured_conflict"
    assert row["review_reason"].startswith("Antagonist activity at human NR1I2")
    assert row["source_note"].startswith("Antagonist activity at human NR1I2")
    assert row["manual_promotion_blocker"] == "activity_proxy_conflicts_with_non_binder"
