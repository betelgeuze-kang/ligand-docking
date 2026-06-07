from __future__ import annotations

from tools.product import build_transporter_candidate_verdict_sheet as mod


def test_build_transporter_candidate_verdict_sheet() -> None:
    payload = mod.build_payload(
        "aqp1",
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "proposed_packet_step": "core_binder_01",
                    "recommended_review_bucket": "review_only_first_wave",
                    "recommended_verdict": "keep_review_only",
                    "promotion_policy": "draft_first_wave_manual_review",
                    "source_anchor": "PMID 27474162",
                    "caution": "note",
                },
                {
                    "candidate_name": "acetazolamide",
                    "proposed_packet_step": "caution_only",
                    "recommended_review_bucket": "defer_contested_system_effect",
                    "recommended_verdict": "defer",
                    "promotion_policy": "caution_only_not_for_authoritative_apply",
                    "source_anchor": "PLOS One 2012",
                    "caution": "note",
                },
            ]
        },
    )
    assert payload["summary"]["candidate_count"] == 2
    assert payload["summary"]["keep_review_only_count"] == 1
    assert payload["summary"]["defer_count"] == 1
