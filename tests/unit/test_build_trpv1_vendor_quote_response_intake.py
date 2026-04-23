from __future__ import annotations

import pandas as pd
import pytest

from tools import build_trpv1_vendor_quote_response_intake as mod


def _base_vendor_payload() -> dict:
    return {
        "summary": {
            "checked_positive_count": 3,
        },
        "rows": [
            {
                "chembl_id": "CHEMBL2385220",
                "vendor_status": "quote_portal_unconfirmed",
                "vendor_purchase_confirmed": False,
                "quote_portal_url": "https://example.com/2385220",
            },
            {
                "chembl_id": "CHEMBL3427109",
                "vendor_status": "catalog_indexed_pubchem",
                "vendor_purchase_confirmed": True,
                "quote_portal_url": "",
            },
            {
                "chembl_id": "CHEMBL2177440",
                "vendor_status": "quote_portal_unconfirmed",
                "vendor_purchase_confirmed": False,
                "quote_portal_url": "https://example.com/2177440",
            },
        ],
    }


def test_build_trpv1_vendor_quote_response_intake_promotes_rows_from_authenticated_response() -> None:
    base_vendor_payload = _base_vendor_payload()
    response_frame = pd.DataFrame(
        [
            {
                "chembl_id": "CHEMBL2385220",
                "catalog_id": "TM-2385220",
                "purchasable": "yes",
                "purity": "98%",
                "pack_size_mg": "5",
                "lead_time_days": "14",
                "quote_currency": "USD",
                "quote_amount": "180",
                "coa_available": "yes",
                "shipping_region": "KR",
                "notes": "Confirmed by vendor rep",
            },
            {
                "chembl_id": "CHEMBL2177440",
                "catalog_id": "TM-2177440",
                "purchasable": "",
                "purity": "95%",
                "pack_size_mg": "10",
                "lead_time_days": "21",
                "quote_currency": "USD",
                "quote_amount": "240",
                "coa_available": "yes",
                "shipping_region": "KR",
                "notes": "Quoted but stock not yet confirmed",
            },
        ]
    )

    payload = mod.build_payload(base_vendor_payload, response_frame)

    summary = payload["summary"]
    rows = {row["chembl_id"]: row for row in payload["rows"]}

    assert summary["response_update_count"] == 2
    assert summary["purchasable_positive_count"] == 1
    assert summary["quoted_positive_count"] == 1
    assert summary["vendor_evidence_positive_count"] == 3
    assert rows["CHEMBL2385220"]["vendor_status"] == "purchasable"
    assert rows["CHEMBL2385220"]["vendor_purchase_confirmed"] is True
    assert rows["CHEMBL2385220"]["quote_portal_status"] == "response_received"
    assert rows["CHEMBL2177440"]["vendor_status"] == "quoted"
    assert rows["CHEMBL2177440"]["vendor_purchase_confirmed"] is False
    assert rows["CHEMBL2177440"]["manual_follow_up_required"] is True


def test_build_trpv1_vendor_quote_response_intake_blank_template_is_noop() -> None:
    payload = mod.build_payload(_base_vendor_payload(), pd.DataFrame([{"chembl_id": "CHEMBL2385220"}, {"chembl_id": "CHEMBL2177440"}]))

    summary = payload["summary"]
    rows = {row["chembl_id"]: row for row in payload["rows"]}

    assert summary["response_update_count"] == 0
    assert summary["vendor_evidence_positive_count"] == 1
    assert rows["CHEMBL2385220"]["vendor_status"] == "quote_portal_unconfirmed"
    assert rows["CHEMBL2177440"]["vendor_status"] == "quote_portal_unconfirmed"


def test_build_trpv1_vendor_quote_response_intake_does_not_promote_notes_only_rows() -> None:
    response_frame = pd.DataFrame(
        [
            {"chembl_id": "CHEMBL2385220", "notes": "Vendor replied verbally"},
        ]
    )

    payload = mod.build_payload(_base_vendor_payload(), response_frame)

    summary = payload["summary"]
    rows = {row["chembl_id"]: row for row in payload["rows"]}

    assert summary["response_update_count"] == 0
    assert summary["weak_response_count"] == 1
    assert rows["CHEMBL2385220"]["vendor_status"] == "quote_portal_unconfirmed"
    assert rows["CHEMBL2385220"]["quote_response_validation"] == "weak_quote_evidence"


def test_build_trpv1_vendor_quote_response_intake_rejects_unknown_ids() -> None:
    response_frame = pd.DataFrame(
        [
            {"chembl_id": "CHEMBL9999999", "catalog_id": "BAD"},
        ]
    )

    with pytest.raises(ValueError, match="Unknown chembl_id"):
        mod.build_payload(_base_vendor_payload(), response_frame)


def test_build_trpv1_vendor_quote_response_intake_refreshes_downstream_in_order(monkeypatch) -> None:
    calls = []

    def _fake_run(cmd, check):
        calls.append(cmd)
        return None

    monkeypatch.setattr(mod.subprocess, "run", _fake_run)
    mod._refresh_downstream(mod._resolve("runs/trpv1_ion_channel_vendor_web_check_merged_current.json"))

    assert calls[0][1] == "tools/build_trpv1_vendor_quote_request_packet.py"
    assert calls[1][1] == "tools/build_trpv1_sourcing_status_sheet.py"
    assert calls[2][1] == "tools/build_wetlab_cro_delivery_packets.py"
