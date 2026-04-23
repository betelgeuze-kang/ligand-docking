from __future__ import annotations

from tools import build_idp_page4_anchor_evidence_seed as mod


def test_build_idp_page4_anchor_evidence_seed() -> None:
    payload = mod.build_payload(
        {
            "targets": [
                {
                    "name": "page4",
                    "source": "synthetic",
                    "n_res": 102,
                    "split_group": "page4",
                }
            ]
        },
        {
            "holdout_name": "page4",
            "source_kind": "synthetic",
            "publication_year": "2011",
            "provenance_source": "https://pmc.ncbi.nlm.nih.gov/articles/PMC3077599/",
        },
        {
            "summary": {
                "source_class": "branch_family_provisional",
                "provenance_kind": "branch_family_prior",
                "current_wrong_conditions": ["hydro_high", "salt_high"],
            }
        },
    )
    s = payload["summary"]
    assert s["status"] == "page4_anchor_evidence_seed_ready"
    assert s["target_name"] == "page4"
    assert s["residue_count"] == 102
    assert s["construct_match_required"] is True
    assert s["condition_match_required"] is True
    assert s["first_open_source_anchor"].startswith("PMC3077599")
    assert s["top_search_target"] == "PAGE4 full-length 102 aa"
    assert len(payload["rows"]) == 4
    assert payload["rows"][0]["identity_candidate"] == "PAGE4"
    assert payload["rows"][1]["source_anchor"] == "PMID 26242913"
    assert payload["rows"][2]["source_anchor"] == "PMID 28289210"
