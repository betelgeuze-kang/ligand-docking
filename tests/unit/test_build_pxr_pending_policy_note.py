from __future__ import annotations

from tools.product import build_pxr_pending_policy_note as mod


def test_build_pxr_pending_policy_note() -> None:
    payload = mod.build_payload(
        {
            "rows": [
                {"replacement_ligand_id": "ibuprofen", "review_bucket": "review_only_negative"},
                {"replacement_ligand_id": "bexarotene", "review_bucket": "defer_pending_target_specific_evidence"},
                {"replacement_ligand_id": "caffeine", "review_bucket": "defer_pending_target_specific_evidence"},
            ]
        }
    )
    assert payload["summary"]["review_only_rows"] == ["ibuprofen"]
    assert payload["summary"]["defer_rows"] == ["bexarotene", "caffeine"]
    assert "ibuprofen" in payload["summary"]["policy_line"]
