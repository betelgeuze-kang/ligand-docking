from __future__ import annotations

import pandas as pd

from tools import build_trpv1_vendor_quote_request_packet as mod


def test_build_trpv1_vendor_quote_request_packet_collects_unresolved_portal_rows() -> None:
    vendor_payload = {
        "rows": [
            {
                "chembl_id": "CHEMBL2385220",
                "vendor_purchase_confirmed": False,
                "quote_portal_status": "portal_query_page_visible",
                "quote_portal_source": "TargetMol",
                "quote_portal_url": "https://example.com/2385220",
            },
            {
                "chembl_id": "CHEMBL3427109",
                "vendor_purchase_confirmed": True,
                "quote_portal_status": "",
                "quote_portal_source": "",
                "quote_portal_url": "",
            },
            {
                "chembl_id": "CHEMBL2177440",
                "vendor_purchase_confirmed": False,
                "quote_portal_status": "portal_query_page_visible",
                "quote_portal_source": "TargetMol",
                "quote_portal_url": "https://example.com/2177440",
            },
        ]
    }
    sourcing_payload = {
        "rows": [
            {
                "chembl_id": "CHEMBL2385220",
                "normalized_name": "Hit 1",
                "inchi_key": "K1",
                "smiles": "CC",
                "standard_type": "Ki",
                "pchembl": 9.5,
                "reference_binding_kcal_mol": -12.0,
                "binding_score_composite_v5": -20.0,
            },
            {
                "chembl_id": "CHEMBL2177440",
                "normalized_name": "Hit 2",
                "inchi_key": "K2",
                "smiles": "CCC",
                "standard_type": "Ki",
                "pchembl": 9.4,
                "reference_binding_kcal_mol": -11.0,
                "binding_score_composite_v5": -19.0,
            },
        ]
    }
    sourcing_request_frame = pd.DataFrame(
        [
            {"chembl_id": "CHEMBL2385220", "smiles": "CC", "normalized_name": "Hit 1", "inchi_key": "K1", "standard_type": "Ki", "pchembl": 9.5, "reference_binding_kcal_mol": -12.0, "binding_score_composite_v5": -20.0},
            {"chembl_id": "CHEMBL2177440", "smiles": "CCC", "normalized_name": "Hit 2", "inchi_key": "K2", "standard_type": "Ki", "pchembl": 9.4, "reference_binding_kcal_mol": -11.0, "binding_score_composite_v5": -19.0},
        ]
    )

    payload = mod.build_payload(vendor_payload, sourcing_payload, sourcing_request_frame)

    assert payload["summary"]["quote_request_count"] == 2
    assert payload["rows"][0]["chembl_id"] == "CHEMBL2385220"
    assert payload["rows"][0]["smiles"] == "CC"
    assert "CHEMBL2177440" in payload["email_template"]["body"]


def test_build_trpv1_vendor_quote_request_packet_shrinks_to_unresolved_rows_only() -> None:
    vendor_payload = {
        "rows": [
            {
                "chembl_id": "CHEMBL2385220",
                "vendor_purchase_confirmed": False,
                "vendor_status": "quoted",
                "quote_portal_status": "response_received",
                "quote_portal_source": "TargetMol",
                "quote_portal_url": "https://example.com/2385220",
            },
            {
                "chembl_id": "CHEMBL2177440",
                "vendor_purchase_confirmed": False,
                "vendor_status": "quote_portal_unconfirmed",
                "quote_portal_status": "portal_query_page_visible",
                "quote_portal_source": "TargetMol",
                "quote_portal_url": "https://example.com/2177440",
            },
        ]
    }
    sourcing_payload = {
        "rows": [
            {
                "chembl_id": "CHEMBL2177440",
                "normalized_name": "Hit 2",
                "inchi_key": "K2",
                "smiles": "CCC",
                "standard_type": "Ki",
                "pchembl": 9.4,
                "reference_binding_kcal_mol": -11.0,
                "binding_score_composite_v5": -19.0,
            },
        ]
    }
    sourcing_request_frame = pd.DataFrame(
        [
            {"chembl_id": "CHEMBL2177440", "smiles": "CCC", "normalized_name": "Hit 2", "inchi_key": "K2", "standard_type": "Ki", "pchembl": 9.4, "reference_binding_kcal_mol": -11.0, "binding_score_composite_v5": -19.0},
        ]
    )

    payload = mod.build_payload(vendor_payload, sourcing_payload, sourcing_request_frame)

    assert payload["summary"]["quote_request_count"] == 1
    assert payload["rows"][0]["chembl_id"] == "CHEMBL2177440"
