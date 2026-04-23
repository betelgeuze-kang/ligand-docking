from __future__ import annotations

from tools import build_wetlab_outbound_execution_priority_board as mod


def test_build_wetlab_outbound_execution_priority_board_prioritizes_disease_and_virus_tracks() -> None:
    portfolio = {
        "rows": [
            {
                "target_id": "T. cruzi PDE",
                "wave": "Wave 1",
                "disease_area": "Chagas disease",
                "partner_rail": "DNDi/IPK neglected-disease rail",
                "total_priority_score": 13,
            },
            {
                "target_id": "Cruzain",
                "wave": "Wave 1",
                "disease_area": "Chagas disease",
                "partner_rail": "DNDi/IPK neglected-disease rail",
                "total_priority_score": 12,
            },
            {
                "target_id": "SARS-CoV-2 Mpro",
                "wave": "Wave 1",
                "disease_area": "Pan-coronavirus / pandemic preparedness",
                "partner_rail": "COVID Moonshot / READDI adjacent rail",
                "total_priority_score": 13,
            },
        ]
    }
    export_bundle = {
        "summary": {"sender_name": "강지훈"},
        "rows": [
            {
                "track_id": "READDI_Korea",
                "track_label": "READDI / Korea antiviral rail",
                "status": "ready_to_send",
                "lead_targets": "SARS-CoV-2 Mpro",
                "proposal_title": "READDI antiviral packet",
                "attachment_artifacts": "mpro.md",
            },
            {
                "track_id": "DNDi_IPK",
                "track_label": "DNDi / Institut Pasteur Korea",
                "status": "ready_to_send",
                "lead_targets": "T. cruzi PDE; Cruzain",
                "proposal_title": "DNDi neglected packet",
                "attachment_artifacts": "neglected.md",
            },
        ],
    }
    master_queue = {
        "summary": {
            "chain_count": 4,
            "resolved_target_count": 13,
            "stack_gate_states": {
                "priority3": {"all_rows_resolved": True},
                "next3": {"all_rows_resolved": True},
                "final2": {"all_rows_resolved": True},
                "wave2": {"all_rows_resolved": True},
            },
        }
    }

    payload = mod.build_payload(export_bundle, portfolio, master_queue)
    summary = payload["summary"]

    assert summary["status"] == "wetlab_outbound_execution_priority_board_ready"
    assert summary["all_chains_resolved"] is True
    assert summary["ready_to_send_count"] == 2
    assert summary["ready_to_send_target_count"] == 2
    assert summary["top_priority_track_id"] == "DNDi_IPK"
    assert summary["first_priority_target"] == "T. cruzi PDE; Cruzain"
    assert summary["follow_on_target_count"] == 1
    assert payload["rows"][0]["track_id"] == "DNDi_IPK"
    assert payload["rows"][0]["execution_now"] is True
    assert payload["rows"][1]["track_id"] == "READDI_Korea"
