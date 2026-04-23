from __future__ import annotations

from tools import build_wetlab_partner_outreach_tracks as mod


def test_build_wetlab_partner_outreach_tracks() -> None:
    payload = mod.build_payload()
    summary = payload["summary"]
    rows = {row["track_id"]: row for row in payload["rows"]}
    ordered_track_ids = [row["track_id"] for row in payload["rows"]]

    assert summary["status"] == "wetlab_partner_outreach_tracks_ready"
    assert summary["track_count"] == 5
    assert ordered_track_ids == [
        "DNDi_IPK",
        "M4K_open_science",
        "READDI_Korea",
        "oncology_condition_aware",
        "SGC_dark_kinase",
    ]
    assert "T. cruzi PDE" in rows["DNDi_IPK"]["best_targets"]
    assert rows["READDI_Korea"]["offer_model"].startswith("rapid micro-validation")
