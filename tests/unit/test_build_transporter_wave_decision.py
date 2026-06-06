from __future__ import annotations

from tools.product import build_transporter_wave_decision as mod


def test_build_transporter_wave_decision() -> None:
    payload = mod.build_payload(
        {
            "target_rows": [
                {"target_id": "AQP1", "local_evidence_status": "draft_only_local_evidence_blocked", "placeholder_rows": 6},
                {"target_id": "GLUT1", "local_evidence_status": "draft_only_local_evidence_blocked", "placeholder_rows": 6},
            ]
        },
        {
            "target_rows": [
                {"target_id": "Aquaporin_1", "p0_open_count": 3},
                {"target_id": "GLUT1_4PYP", "p0_open_count": 5},
            ]
        },
    )
    assert payload["summary"]["decision_status"] == "aqp1_first_wave_glut1_second_wave"
    assert payload["rows"][0]["target_id"] == "AQP1"

