from __future__ import annotations

from tools import build_wetlab_wave2_runtime_event as mod


def test_build_wetlab_wave2_runtime_event_uses_placeholder_when_no_event_is_present() -> None:
    payload = mod.build_payload({})
    summary = payload["summary"]

    assert summary["status"] == "wetlab_wave2_runtime_event_placeholder"
    assert summary["target_id"] == "none"
    assert summary["event"] == "not_present"
    assert summary["queue_status_now"] == "not_present"
    assert summary["gate_status"] == "not_present"
    assert "No Wave 2 runtime event has been applied yet" in summary["next_required_step"]
    assert payload["rows"] == []
