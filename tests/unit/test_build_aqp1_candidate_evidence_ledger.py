from __future__ import annotations

from tools import build_aqp1_candidate_evidence_ledger as mod


def test_build_aqp1_candidate_evidence_ledger() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {
                    "candidate_name": "bacopaside II",
                    "proposed_packet_step": "core_binder_01",
                    "evidence_class": "functional_aqp1_water_channel_inhibitor",
                    "promotion_policy": "draft_first_wave_manual_review",
                    "recommended_review_bucket": "review_only_first_wave",
                    "source_anchor": "PMID 27474162",
                    "source_url": "https://pubmed.ncbi.nlm.nih.gov/27474162/",
                    "potency_or_signal": "IC50 18 uM",
                    "caution": "functional not direct binding",
                    "evidence_strength": "moderate_functional",
                }
            ]
        }
    )
    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["first_wave_row_count"] == 1
    row = payload["rows"][0]
    assert row["candidate_name"] == "bacopaside II"
    assert row["confidence"] == "medium"
