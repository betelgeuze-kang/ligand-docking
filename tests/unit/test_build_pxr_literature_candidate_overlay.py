from __future__ import annotations

from tools.product import build_pxr_literature_candidate_overlay as mod


def test_build_pxr_literature_candidate_overlay_scores_high_signal_rows() -> None:
    def fake_search_ids(query: str) -> list[str]:
        if "bexarotene" in query:
            return ["18544536"]
        if "caffeine" in query:
            return []
        return []

    def fake_fetch_articles(ids: list[str]) -> list[dict[str, str]]:
        if ids == ["18544536"]:
            return [
                {
                    "pmid": "18544536",
                    "title": "Rexinoids modulate steroid and xenobiotic receptor activity by increasing its protein turnover in a calpain-dependent manner.",
                    "abstract": "The steroid and xenobiotic receptor SXR (human pregnane X receptor) is a nuclear receptor. Rexinoids are weak activators of SXR, and two rexinoids, bexarotene and LG100268, caused a rapid decrease in SXR levels. Competition for binding to SXR can explain the antagonism.",
                }
            ]
        return []

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "family": "pxr",
                    "packet_step": "ood_fit_binder_01",
                    "ligand": "bexarotene",
                    "priority_tier": "P2_supportive_manual_confirmation",
                    "blocking_reason": "activity_present_manual_confirmation_required",
                },
                {
                    "queue_rank": 2,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_02",
                    "ligand": "caffeine",
                    "priority_tier": "P1_count_improving_negative_gap",
                    "blocking_reason": "no_local_target_activity_curated",
                },
            ]
        },
        top_n=2,
        search_ids=fake_search_ids,
        fetch_articles=fake_fetch_articles,
        throttle_sec=0,
    )

    summary = payload["summary"]
    assert summary["row_count"] == 2
    assert summary["high_signal_row_count"] == 1
    assert summary["same_sentence_human_row_count"] == 0
    assert summary["same_sentence_row_count"] == 0
    assert summary["no_candidate_row_count"] == 1
    assert summary["primary_focus_ligand"] == "bexarotene"

    bexarotene_row, caffeine_row = payload["rows"]
    assert bexarotene_row["candidate_status"] == "high_signal_candidates_present"
    assert bexarotene_row["best_candidate_pmid"] == "18544536"
    assert bexarotene_row["best_candidate_signal"] == "abstract_direct_human_candidate"
    assert caffeine_row["candidate_status"] == "no_candidates"


def test_build_pxr_literature_candidate_overlay_demotes_title_direct_nonhuman_rows() -> None:
    def fake_search_ids(query: str) -> list[str]:
        if "acetaminophen" in query:
            return ["41034397", "40076408"]
        return []

    def fake_fetch_articles(ids: list[str]) -> list[dict[str, str]]:
        return [
            {
                "pmid": "41034397",
                "title": "PXR ribosylation at E194 amplifies NAPQI in acetaminophen-induced liver injury in mice.",
                "abstract": "Human hepatic cells were used for follow-up, but the primary model is mice.",
            },
            {
                "pmid": "40076408",
                "title": "Forsythiaside A Reduces Acetaminophen Hepatotoxic Metabolism by Inhibiting Pregnane X Receptor.",
                "abstract": "The work is preclinical and does not establish a claim-safe human PXR source for acetaminophen.",
            },
        ]

    payload = mod.build_payload(
        {
            "rows": [
                {
                    "queue_rank": 1,
                    "family": "pxr",
                    "packet_step": "core_eval_non_binder_01",
                    "ligand": "acetaminophen",
                    "priority_tier": "P2_conflict_resolution",
                    "blocking_reason": "activity_proxy_conflicts_with_non_binder",
                }
            ]
        },
        top_n=1,
        search_ids=fake_search_ids,
        fetch_articles=fake_fetch_articles,
        throttle_sec=0,
    )

    summary = payload["summary"]
    assert summary["high_signal_row_count"] == 0
    assert summary["title_direct_nonhuman_row_count"] == 1
    row = payload["rows"][0]
    assert row["candidate_status"] == "title_direct_nonhuman_candidates_present"
    assert row["best_candidate_signal"] == "title_direct_nonhuman_candidate"
    assert row["best_candidate_mentions_nonhuman"] == "yes"
