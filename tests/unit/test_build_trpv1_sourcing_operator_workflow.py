from __future__ import annotations

from tools import build_trpv1_sourcing_operator_workflow as mod


def test_build_trpv1_sourcing_operator_workflow_surfaces_fill_file_and_status_rules() -> None:
    sourcing_payload = {
        "summary": {
            "vendor_confirmed_positive_count": 1,
            "matched_negative_slot_count_locked": 3,
            "control_panel_locked": False,
            "blocking_reason": "two positives remain unresolved",
            "next_required_step": "convert the remaining positives to quoted or purchasable",
        }
    }
    quote_packet_payload = {
        "summary": {
            "quote_request_count": 2,
            "primary_blocker": "manual quote confirmation still pending",
        },
        "rows": [
            {"chembl_id": "CHEMBL2385220", "normalized_name": "Hit 1"},
            {"chembl_id": "CHEMBL2177440", "normalized_name": "Hit 2"},
        ],
    }
    merged_vendor_payload = {
        "summary": {
            "response_update_count": 0,
        },
        "rows": [
            {"chembl_id": "CHEMBL2385220", "vendor_status": "quote_portal_unconfirmed", "quote_response_received": False},
            {"chembl_id": "CHEMBL2177440", "vendor_status": "quote_portal_unconfirmed", "quote_response_received": False},
        ],
    }

    payload = mod.build_payload(
        sourcing_payload,
        quote_packet_payload,
        merged_vendor_payload,
        "runs/trpv1_ion_channel_vendor_quote_response_current.csv",
        "runs/trpv1_ion_channel_vendor_quote_response_template_current.csv",
    )

    assert payload["summary"]["quote_request_count"] == 2
    assert payload["summary"]["vendor_confirmed_positive_count"] == 1
    assert payload["steps"][0]["path"].endswith("runs/trpv1_ion_channel_vendor_quote_response_current.csv")
    assert payload["summary"]["response_template_csv"].endswith("runs/trpv1_ion_channel_vendor_quote_response_template_current.csv")
    assert payload["steps"][1]["command"] == "python3 tools/build_trpv1_vendor_quote_response_intake.py"
    assert payload["transitions"][1]["resulting_vendor_status"] == "quoted"
    assert payload["transitions"][2]["resulting_vendor_status"] == "purchasable"
    assert payload["unresolved_rows"][0]["chembl_id"] == "CHEMBL2385220"
