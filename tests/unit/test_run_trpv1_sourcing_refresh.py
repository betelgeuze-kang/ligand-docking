from __future__ import annotations

from pathlib import Path

from tools import run_trpv1_sourcing_refresh as mod


def test_build_command_plan_prefers_merged_vendor_json_when_present(tmp_path: Path) -> None:
    base_vendor = tmp_path / "base.json"
    merged_vendor = tmp_path / "merged.json"
    quote_response = tmp_path / "response.csv"
    base_vendor.write_text("{}", encoding="utf-8")
    merged_vendor.write_text("{}", encoding="utf-8")
    quote_response.write_text("chembl_id,catalog_id\n", encoding="utf-8")

    commands = mod.build_command_plan(
        base_vendor_json=str(base_vendor),
        quote_response_csv=str(quote_response),
        merged_vendor_json=str(merged_vendor),
    )

    assert commands[0][0:2] == ["python3", "tools/build_trpv1_sendable_negative_panel.py"]
    assert commands[1][0:2] == ["python3", "tools/build_trpv1_vendor_quote_response_intake.py"]
    assert commands[1][-1] == "--no-refresh-downstream"
    assert commands[2][-1] == str(merged_vendor)
    assert commands[3][-1] == str(merged_vendor)
    assert commands[4][-1] == str(merged_vendor)


def test_build_payload_summarizes_trpv1_refresh_state() -> None:
    payload = mod.build_payload(
        selected_vendor_json="runs/trpv1_ion_channel_vendor_web_check_merged_current.json",
        quote_response_rows_with_data=2,
        merged_vendor_payload={
            "summary": {
                "vendor_evidence_positive_count": 3,
            }
        },
        quote_request_payload={
            "summary": {
                "status": "trpv1_vendor_quote_request_packet_ready",
                "quote_request_count": 1,
            }
        },
        sourcing_payload={
            "summary": {
                "status": "trpv1_ion_channel_sourcing_status_ready",
                "vendor_confirmed_positive_count": 3,
                "matched_negative_slot_count_locked": 3,
                "next_required_step": "Replace the internal synthetic matched negatives with vendor-feasible controls before external CRO send.",
            }
        },
        cro_payload={
            "rows": [
                {
                    "target_id": "TRPV1_ION_CHANNEL_BLIND",
                    "packet_status": "cro_delivery_packet_blocked",
                    "ready_for_send": False,
                    "missing_slot_count": 3,
                }
            ]
        },
    )

    summary = payload["summary"]
    assert summary["quote_response_rows_with_data"] == 2
    assert summary["vendor_confirmed_positive_count"] == 3
    assert summary["cro_missing_slot_count"] == 3
    assert payload["rows"][-1]["status"] == "cro_delivery_packet_blocked"
