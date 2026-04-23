from __future__ import annotations

import pandas as pd

from tools import build_trpv1_sourcing_status_sheet as mod


def test_build_trpv1_sourcing_status_sheet_tracks_vendor_and_negative_blockers() -> None:
    shortlist = pd.DataFrame(
        [
            {"priority_rank": 1, "chembl_id": "CHEMBL1", "normalized_name": "Hit 1", "inchi_key": "K1", "identity_status": "identity_normalized", "vendor_status": "quoted", "readiness_note": "ok"},
            {"priority_rank": 2, "chembl_id": "CHEMBL2", "normalized_name": "Hit 2", "inchi_key": "K2", "identity_status": "identity_normalized", "vendor_status": "vendor_check_pending", "readiness_note": "pending"},
            {"priority_rank": 3, "chembl_id": "CHEMBL3", "normalized_name": "Hit 3", "inchi_key": "K3", "identity_status": "identity_normalized", "vendor_status": "vendor_check_pending", "readiness_note": "pending"},
            {"priority_rank": 4, "chembl_id": "CHEMBL4", "normalized_name": "Hit 4", "inchi_key": "K4", "identity_status": "identity_normalized", "vendor_status": "vendor_check_pending", "readiness_note": "reserve"},
        ]
    )
    sourcing = pd.DataFrame(
        [
            {"priority_rank": 1, "chembl_id": "CHEMBL1", "vendor_status": "quoted"},
            {"priority_rank": 2, "chembl_id": "CHEMBL2", "vendor_status": "vendor_check_pending"},
        ]
    )

    payload = mod.build_payload(
        shortlist,
        sourcing,
        {
            "rows": [
                {
                    "chembl_id": "CHEMBL2",
                    "vendor_status": "catalog_indexed_pubchem",
                    "vendor_purchase_confirmed": True,
                    "vendor_evidence_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/25102898/JSON/?heading=Chemical-Vendors",
                }
            ]
        },
        {
            "summary": {
                "matched_negative_slot_count_locked": 3,
                "matched_negative_panel_locked": True,
                "matched_negative_panel_sendable": False,
            },
            "rows": [
                {"panel_slot": "negative_1", "compound_id": "NEG1", "external_send_ready": False},
                {"panel_slot": "negative_2", "compound_id": "NEG2", "external_send_ready": False},
                {"panel_slot": "negative_3", "compound_id": "NEG3", "external_send_ready": False},
            ],
        },
        {
            "summary": {
                "status": "trpv1_vendor_quote_request_packet_ready",
                "quote_request_count": 2,
            }
        },
    )
    summary = payload["summary"]
    row1 = payload["rows"][0]
    row2 = payload["rows"][1]

    assert summary["status"] == "trpv1_ion_channel_sourcing_status_ready"
    assert summary["proposed_positive_control_count"] == 3
    assert summary["vendor_confirmed_positive_count"] == 2
    assert summary["matched_negative_slot_count_locked"] == 3
    assert summary["matched_negative_panel_locked_internal"] is True
    assert summary["matched_negative_panel_sendable"] is False
    assert summary["vendor_quote_request_packet_ready"] is True
    assert summary["vendor_quote_request_count"] == 2
    assert summary["control_panel_locked"] is False
    assert row1["positive_control_locked"] is True
    assert row2["positive_control_locked"] is True
    assert row2["vendor_status"] == "catalog_indexed_pubchem"
    assert payload["matched_negative_rows"][0]["compound_id"] == "NEG1"


def test_build_trpv1_sourcing_status_sheet_switches_to_negative_sendability_blocker_after_top3_lock() -> None:
    shortlist = pd.DataFrame(
        [
            {"priority_rank": 1, "chembl_id": "CHEMBL1", "normalized_name": "Hit 1", "inchi_key": "K1"},
            {"priority_rank": 2, "chembl_id": "CHEMBL2", "normalized_name": "Hit 2", "inchi_key": "K2"},
            {"priority_rank": 3, "chembl_id": "CHEMBL3", "normalized_name": "Hit 3", "inchi_key": "K3"},
        ]
    )
    sourcing = shortlist.copy()

    payload = mod.build_payload(
        shortlist,
        sourcing,
        {
            "summary": {"status": "trpv1_vendor_quote_response_intake_ready", "response_update_count": 2},
            "rows": [
                {"chembl_id": "CHEMBL1", "vendor_status": "quoted", "vendor_purchase_confirmed": False},
                {"chembl_id": "CHEMBL2", "vendor_status": "purchasable", "vendor_purchase_confirmed": True},
                {"chembl_id": "CHEMBL3", "vendor_status": "catalog_indexed_pubchem", "vendor_purchase_confirmed": True},
            ],
        },
        {
            "summary": {
                "matched_negative_slot_count_locked": 3,
                "matched_negative_panel_locked": True,
                "matched_negative_panel_sendable": False,
            },
            "rows": [],
        },
        {"summary": {"status": "trpv1_vendor_quote_request_packet_ready", "quote_request_count": 0}},
    )

    summary = payload["summary"]

    assert summary["positive_control_panel_locked"] is True
    assert summary["matched_negative_panel_sendable"] is False
    assert summary["control_panel_locked"] is False
    assert "internal synthetic-decoy set" in summary["blocking_reason"]
    assert summary["vendor_evidence_mode"] == "merged_quote_response"


def test_build_trpv1_sourcing_status_sheet_unlocks_control_panel_when_all_conditions_hold() -> None:
    shortlist = pd.DataFrame(
        [
            {"priority_rank": 1, "chembl_id": "CHEMBL1", "normalized_name": "Hit 1", "inchi_key": "K1"},
            {"priority_rank": 2, "chembl_id": "CHEMBL2", "normalized_name": "Hit 2", "inchi_key": "K2"},
            {"priority_rank": 3, "chembl_id": "CHEMBL3", "normalized_name": "Hit 3", "inchi_key": "K3"},
        ]
    )
    sourcing = shortlist.copy()

    payload = mod.build_payload(
        shortlist,
        sourcing,
        {
            "summary": {"status": "trpv1_vendor_quote_response_intake_ready", "response_update_count": 3},
            "rows": [
                {"chembl_id": "CHEMBL1", "vendor_status": "quoted", "vendor_purchase_confirmed": False},
                {"chembl_id": "CHEMBL2", "vendor_status": "purchasable", "vendor_purchase_confirmed": True},
                {"chembl_id": "CHEMBL3", "vendor_status": "catalog_indexed_pubchem", "vendor_purchase_confirmed": True},
            ],
        },
        {
            "summary": {
                "matched_negative_slot_count_locked": 3,
                "matched_negative_panel_locked": True,
                "matched_negative_panel_sendable": True,
            },
            "rows": [],
        },
        {"summary": {"status": "trpv1_vendor_quote_request_packet_ready", "quote_request_count": 0}},
    )

    summary = payload["summary"]

    assert summary["positive_control_panel_locked"] is True
    assert summary["control_panel_locked"] is True
    assert summary["blocking_reason"] == ""
    assert "fully locked" in summary["next_required_step"]
