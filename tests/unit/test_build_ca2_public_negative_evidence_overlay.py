from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from tools import build_ca2_public_negative_evidence_overlay as mod


def test_build_ca2_public_negative_evidence_overlay_detects_direct_negative_like_evidence() -> None:
    def fake_fetch(url: str) -> dict[str, object]:
        params = parse_qs(urlparse(url).query)
        assert params["molecule_chembl_id"][0] == "CHEMBL1431"
        assert params["target_chembl_id"][0] == "CHEMBL205"
        return {
            "activities": [
                {
                    "activity_comment": "Inhibition < 50% @ 10 uM and thus dose-reponse curve not measured",
                    "assay_chembl_id": "CHEMBL1909123",
                    "document_chembl_id": "CHEMBL1909000",
                }
            ]
        }

    payload = mod.build_payload(
        [
            {
                "packet_step": "core_non_binder_02",
                "ligand": "metformin",
                "capture_status": "captured_no_direct_negative_source_found",
                "manual_promotion_blocker": "no_direct_ca2_negative_evidence_located_after_research",
            }
        ],
        fetch_json=fake_fetch,
        today_local="2026-04-18",
    )

    assert payload["summary"]["row_count"] == 1
    assert payload["summary"]["direct_negative_row_count"] == 1
    row = payload["rows"][0]
    assert row["overlay_status"] == "captured_direct_negative_review_only"
    assert row["supports_direct_ca2_negative"] == "yes"
    assert row["capture_status"] == "captured_direct_negative_review_only"
    assert row["manual_promotion_blocker"] == "direct_ca2_negative_evidence_curated_review_only"
    assert "CHEMBL1909123" in row["source_id"]
