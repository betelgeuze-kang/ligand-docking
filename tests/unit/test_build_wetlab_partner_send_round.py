from __future__ import annotations

from tools.wetlab import build_wetlab_partner_send_round as mod


def test_build_wetlab_partner_send_round_orders_tracks_by_dispatch_rank() -> None:
    outbound_board = {
        "rows": [
            {"priority_rank": 2, "track_id": "READDI_Korea"},
            {"priority_rank": 1, "track_id": "DNDi_IPK"},
        ]
    }
    export_bundle = {
        "summary": {"sender_name": "강지훈", "sender_affiliation": ""},
        "rows": [
            {
                "track_id": "READDI_Korea",
                "track_label": "READDI / Korea antiviral rail",
                "status": "ready_to_send",
                "lead_targets": "SARS-CoV-2 PLpro; SARS-CoV-2 Mpro",
                "email_subject": "READDI subject",
                "proposal_title": "READDI title",
                "attachment_artifacts": "readdi.md",
            },
            {
                "track_id": "DNDi_IPK",
                "track_label": "DNDi / Institut Pasteur Korea",
                "status": "ready_to_send",
                "lead_targets": "T. cruzi PDE; Cruzain",
                "email_subject": "DNDi subject",
                "proposal_title": "DNDi title",
                "attachment_artifacts": "dndi.md",
            },
        ],
    }

    payload = mod.build_payload(outbound_board, export_bundle)
    assert payload["summary"]["status"] == "wetlab_partner_send_round_ready"
    assert payload["summary"]["first_dispatch_track_id"] == "DNDi_IPK"
    assert "explicit R4 confirmation" in payload["summary"]["next_required_step"]
    assert payload["rows"][0]["track_id"] == "DNDi_IPK"
    assert payload["rows"][0]["dispatch_status"] == "send_ready_manual_dispatch"
