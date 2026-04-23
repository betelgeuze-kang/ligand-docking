from __future__ import annotations

import json
from pathlib import Path

from tools import build_wetlab_cro_delivery_packets as mod


def test_build_wetlab_cro_delivery_packets_builds_ready_and_blocked_packets(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs"
    pdf_dir = tmp_path / "pdf"

    payload = mod.build_payload(
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        trpv1_shortlist_csv=mod.DEFAULT_TRPV1_SHORTLIST_CSV,
        trpv1_sourcing_request_csv=mod.DEFAULT_TRPV1_SOURCING_REQUEST_CSV,
        trpv1_vendor_web_check_json=mod.DEFAULT_TRPV1_VENDOR_WEB_CHECK_JSON,
        trpv1_matched_negative_panel_json=mod.DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON,
    )

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_cro_delivery_packet_index_ready"
    assert summary["target_count"] == 4
    assert rows["EGFR_KINASE"]["ready_for_send"] is True
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["ready_for_send"] is False
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["missing_slot_count"] == 5
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["matched_negative_slot_count_locked"] == 3
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["matched_negative_panel_locked_internal"] is True
    assert (pdf_dir / "egfr_kinase_cro_delivery_packet_current.pdf").exists()
    assert (out_dir / "egfr_kinase_cro_data_return_template_current.csv").exists()


def test_build_wetlab_cro_delivery_packets_uses_vendor_confirmed_merge_for_trpv1_positive_slots(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs"
    pdf_dir = tmp_path / "pdf"
    vendor_json = tmp_path / "merged_vendor.json"
    vendor_json.write_text(
        json.dumps(
            {
                "rows": [
                    {"chembl_id": "CHEMBL2385220", "vendor_status": "quoted", "vendor_purchase_confirmed": False},
                    {"chembl_id": "CHEMBL3427109", "vendor_status": "catalog_indexed_pubchem", "vendor_purchase_confirmed": True},
                    {"chembl_id": "CHEMBL2177440", "vendor_status": "purchasable", "vendor_purchase_confirmed": True},
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        trpv1_shortlist_csv=mod.DEFAULT_TRPV1_SHORTLIST_CSV,
        trpv1_sourcing_request_csv=mod.DEFAULT_TRPV1_SOURCING_REQUEST_CSV,
        trpv1_vendor_web_check_json=str(vendor_json),
        trpv1_matched_negative_panel_json=mod.DEFAULT_TRPV1_MATCHED_NEGATIVE_PANEL_JSON,
    )

    rows = {row["target_id"]: row for row in payload["rows"]}

    assert rows["TRPV1_ION_CHANNEL_BLIND"]["ready_for_send"] is False
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["missing_slot_count"] == 3
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["matched_negative_panel_sendable"] is False


def test_build_wetlab_cro_delivery_packets_marks_trpv1_ready_when_controls_are_fully_sendable(tmp_path: Path) -> None:
    out_dir = tmp_path / "runs"
    pdf_dir = tmp_path / "pdf"
    vendor_json = tmp_path / "merged_vendor.json"
    negative_json = tmp_path / "matched_negative.json"
    vendor_json.write_text(
        json.dumps(
            {
                "summary": {"status": "trpv1_vendor_quote_response_intake_ready", "response_update_count": 2},
                "rows": [
                    {"chembl_id": "CHEMBL2385220", "vendor_status": "quoted", "vendor_purchase_confirmed": False},
                    {"chembl_id": "CHEMBL3427109", "vendor_status": "catalog_indexed_pubchem", "vendor_purchase_confirmed": True},
                    {"chembl_id": "CHEMBL2177440", "vendor_status": "purchasable", "vendor_purchase_confirmed": True},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    negative_json.write_text(
        json.dumps(
            {
                "summary": {
                    "matched_negative_slot_count_locked": 3,
                    "matched_negative_panel_locked": True,
                    "matched_negative_panel_sendable": True,
                },
                "rows": [
                    {"panel_slot": "negative_1", "compound_id": "NEG1", "compound_name": "Neg1", "expected_class": "negative_control", "expected_direction": "lower_activity_than_positive_panel", "repo_source": "x", "note": "ok", "external_send_ready": True},
                    {"panel_slot": "negative_2", "compound_id": "NEG2", "compound_name": "Neg2", "expected_class": "negative_control", "expected_direction": "lower_activity_than_positive_panel", "repo_source": "x", "note": "ok", "external_send_ready": True},
                    {"panel_slot": "negative_3", "compound_id": "NEG3", "compound_name": "Neg3", "expected_class": "negative_control", "expected_direction": "lower_activity_than_positive_panel", "repo_source": "x", "note": "ok", "external_send_ready": True},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = mod.build_payload(
        out_dir=out_dir,
        pdf_dir=pdf_dir,
        trpv1_shortlist_csv=mod.DEFAULT_TRPV1_SHORTLIST_CSV,
        trpv1_sourcing_request_csv=mod.DEFAULT_TRPV1_SOURCING_REQUEST_CSV,
        trpv1_vendor_web_check_json=str(vendor_json),
        trpv1_matched_negative_panel_json=str(negative_json),
    )

    rows = {row["target_id"]: row for row in payload["rows"]}

    assert rows["TRPV1_ION_CHANNEL_BLIND"]["ready_for_send"] is True
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["missing_slot_count"] == 0
    assert rows["TRPV1_ION_CHANNEL_BLIND"]["control_panel_locked"] is True
