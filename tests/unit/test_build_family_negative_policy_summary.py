from __future__ import annotations

from tools.build_family_negative_policy_summary import build_payload


def test_build_payload_summarizes_review_only_vs_deferred() -> None:
    ca2 = {
        "summary": {"family": "ca2", "review_only_negative_count": 1, "defer_binder_count": 5},
        "rows": [
            {"replacement_ligand_id": "aspirin", "review_bucket": "review_only_negative"},
            {"replacement_ligand_id": "acetaminophen", "review_bucket": "review_only_negative"},
        ],
    }
    pxr = {
        "summary": {"family": "pxr", "review_only_negative_count": 1, "defer_binder_count": 5},
        "rows": [
            {"replacement_ligand_id": "ibuprofen", "review_bucket": "review_only_negative"},
            {"replacement_ligand_id": "bexarotene", "review_bucket": "defer_pending_target_specific_evidence"},
        ],
    }
    payload = build_payload(ca2, pxr)
    rows = {row["family"]: row for row in payload["rows"]}
    assert payload["summary"]["family_count"] == 2
    assert rows["ca2"]["review_only_negative_ligands"] == ["aspirin", "acetaminophen"]
    assert rows["pxr"]["review_only_negative_ligands"] == ["ibuprofen"]
    assert rows["ca2"]["deferred_ligands"] == []
    assert rows["pxr"]["deferred_ligands"] == ["bexarotene"]
