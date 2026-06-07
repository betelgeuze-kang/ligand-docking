from __future__ import annotations

from tools.product import build_pxr_exact_source_confirmation_packet as mod


def test_build_pxr_exact_source_confirmation_packet_focuses_manual_confirmation_rows() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "priority_rank": 10,
                    "replacement_ligand_id": "bexarotene",
                    "capture_status": "captured_supportive",
                    "policy_bucket": "defer",
                    "manual_assay_type_honesty": "activity_present_manual_confirmation_required",
                    "manual_promotion_blocker": "activity_present_manual_confirmation_required",
                    "source_title": "PMID 18544536",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "source_note": "supportive binder source",
                },
                {
                    "packet_step": "core_eval_non_binder_01",
                    "priority_rank": 5,
                    "replacement_ligand_id": "acetaminophen",
                    "capture_status": "captured_conflict",
                    "policy_bucket": "defer",
                    "manual_assay_type_honesty": "activity_proxy_conflicts_with_non_binder",
                    "manual_promotion_blocker": "activity_proxy_conflicts_with_non_binder",
                    "source_title": "Conflict anchor",
                    "source_url": "https://example.org/conflict",
                    "source_note": "conflict source",
                },
                {
                    "packet_step": "ood_eval_non_binder_01",
                    "replacement_ligand_id": "nicotinamide",
                    "capture_status": "captured_gap",
                    "policy_bucket": "defer",
                    "manual_assay_type_honesty": "no_local_target_activity_curated",
                    "manual_promotion_blocker": "no_local_target_activity_curated",
                },
            ]
        },
        {
            "rows": [
                {"focus_rank": 1, "queue_rank": 1, "packet_step": "core_eval_non_binder_01"},
                {"focus_rank": 2, "queue_rank": 2, "packet_step": "ood_eval_non_binder_01"},
            ]
        },
        {
            "rows": [
                {
                    "packet_step": "ood_fit_binder_01",
                    "candidate_status": "high_signal_candidates_present",
                    "best_candidate_pmid": "18544536",
                    "best_candidate_title": "Rexinoids modulate steroid and xenobiotic receptor activity",
                    "best_candidate_url": "https://pubmed.ncbi.nlm.nih.gov/18544536/",
                    "best_candidate_signal": "abstract_direct_human_candidate",
                    "best_candidate_mentions_human": "yes",
                    "best_candidate_mentions_nonhuman": "no",
                    "best_candidate_review_like": "no",
                },
                {
                    "packet_step": "core_eval_non_binder_01",
                    "candidate_status": "title_direct_nonhuman_candidates_present",
                    "best_candidate_pmid": "40076408",
                    "best_candidate_title": "Forsythiaside A Reduces Acetaminophen Hepatotoxic Metabolism by Inhibiting Pregnane X Receptor.",
                    "best_candidate_url": "https://pubmed.ncbi.nlm.nih.gov/40076408/",
                    "best_candidate_signal": "title_direct_nonhuman_candidate",
                    "best_candidate_mentions_human": "no",
                    "best_candidate_mentions_nonhuman": "yes",
                    "best_candidate_review_like": "no",
                },
            ]
        },
        {
            "rows": [
                {"packet_step": "ood_fit_binder_01", "commit_note": "keep deferred pending manual confirmation"},
                {"packet_step": "core_eval_non_binder_01", "commit_note": "keep deferred due to conflict"},
            ]
        },
    )

    summary = payload["summary"]
    assert summary["row_count"] == 1
    assert summary["supportive_binder_confirmation_count"] == 1
    assert summary["conflict_confirmation_count"] == 0
    assert summary["title_direct_nonhuman_count"] == 0
    assert summary["primary_focus_ligand"] == "bexarotene"

    (bexarotene_row,) = payload["rows"]
    assert bexarotene_row["confirmation_scope"] == "supportive_binder_manual_confirmation"
    assert bexarotene_row["manual_promotion_blocker"] == "activity_present_manual_confirmation_required"
    assert bexarotene_row["best_candidate_signal"] == "abstract_direct_human_candidate"
