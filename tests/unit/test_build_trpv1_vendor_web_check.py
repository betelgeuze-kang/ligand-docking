from __future__ import annotations

from tools import build_trpv1_vendor_web_check as mod


def test_build_trpv1_vendor_web_check_tracks_quote_portal_and_pubchem_evidence() -> None:
    payload = mod.build_payload()

    summary = payload["summary"]
    rows = {row["chembl_id"]: row for row in payload["rows"]}

    assert summary["vendor_evidence_positive_count"] == 1
    assert rows["CHEMBL3427109"]["vendor_purchase_confirmed"] is True
    assert rows["CHEMBL2385220"]["vendor_status"] == "quote_portal_unconfirmed"
    assert rows["CHEMBL2177440"]["quote_portal_status"] == "portal_query_page_visible"
