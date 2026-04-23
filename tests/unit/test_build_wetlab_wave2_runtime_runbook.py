from __future__ import annotations

from tools import build_wetlab_wave2_runtime_runbook as mod


def test_build_wetlab_wave2_runtime_runbook_numbers_commands_sequentially() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "queue_target_count": 2,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 2,
                "blocked_on_target_content_count": 0,
            },
            "rows": [
                {"target_id": "Cathepsin K"},
                {"target_id": "DprE1"},
            ],
        }
    )
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave2_runtime_runbook_ready"
    assert summary["target_count"] == 2
    assert summary["command_row_count"] == 7
    assert [row["command_rank"] for row in payload["rows"]] == [1, 2, 3, 4, 5, 6, 7]
    assert payload["rows"][-1]["target_id"] == "all_wave2"
    assert payload["rows"][-1]["event"] == "reset"


def test_build_wetlab_wave2_runtime_runbook_uses_real_cathepsin_stage_label_when_present() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "queue_target_count": 1,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 0,
                "blocked_on_target_content_count": 1,
                "next_required_step": "The final2 gate is open, but Cathepsin K still needs its compound-fill-backed launch readiness before the serialized Wave 2 chain can advance.",
            },
            "rows": [
                {
                    "target_id": "Cathepsin K",
                    "placeholder_state": "live_target_specific_packet_present",
                }
            ],
        }
    )
    summary = payload["summary"]

    assert "compound-fill-backed launch readiness" in summary["next_required_step"]
    assert "acidic_primary_protease_assay" in payload["rows"][0]["command"]
    assert "promote_clean_cathepsin_k_acidic_bias" in payload["rows"][1]["command"]


def test_build_wetlab_wave2_runtime_runbook_keeps_tcruzi_krs1_as_target_specific_slug_once_present() -> None:
    payload = mod.build_payload(
        {
            "summary": {
                "queue_target_count": 1,
                "ready_now_target_count": 0,
                "blocked_on_previous_review_count": 1,
                "blocked_on_target_content_count": 0,
                "next_required_step": "Keep T. cruzi KRS1 blocked until DprE1 resolves.",
            },
            "rows": [
                {
                    "target_id": "T. cruzi KRS1",
                    "queue_status": "blocked_on_previous_review",
                    "placeholder_state": "live_target_specific_packet_present",
                }
            ],
        }
    )
    summary = payload["summary"]

    assert summary["target_count"] == 1
    assert payload["rows"][0]["target_id"] == "T. cruzi KRS1"
    assert "--target t_cruzi_krs1" in payload["rows"][0]["command"]
    assert "pending_target_specific_packet" in payload["rows"][0]["command"]
    assert payload["rows"][0]["queue_note"] == "only valid once predecessor gates resolve and a real target packet exists"
