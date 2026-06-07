from __future__ import annotations

from tools import build_wetlab_partner_first_contact_export_bundle as mod


def _sample_packets() -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    neglected_outreach: dict[str, object] = {
        "rows": [
            {"target_id": "T. cruzi PDE", "status": "ready_for_outbound_send"},
            {"target_id": "Cruzain", "status": "ready_for_outbound_send"},
        ]
    }
    oncology_first_contact: dict[str, object] = {
        "summary": {"export_ready": True},
        "structured": {"target_id": "CA IX"},
    }
    antiviral_first_contact: dict[str, object] = {
        "rows": [
            {"target_id": "SARS-CoV-2 Mpro", "status": "ready_for_outbound_send"},
            {"target_id": "SARS-CoV-2 PLpro", "status": "ready_for_outbound_send"},
        ]
    }
    kinase_outreach: dict[str, object] = {
        "rows": [
            {"target_id": "ALK2", "partner_track_id": "M4K_open_science", "status": "ready_for_partner_specific_export"},
            {"target_id": "STK17B (DRAK2)", "partner_track_id": "SGC_dark_kinase", "status": "ready_for_partner_specific_export"},
        ]
    }
    return neglected_outreach, oncology_first_contact, antiviral_first_contact, kinase_outreach


def test_build_wetlab_partner_first_contact_export_bundle_uses_default_sender() -> None:
    payload = mod.build_payload(*_sample_packets())
    summary = payload["summary"]
    rows = {row["track_id"]: row for row in payload["rows"]}

    assert summary["status"] == "wetlab_partner_first_contact_export_bundle_ready"
    assert summary["track_count"] == 5
    assert summary["ready_to_send_count"] == 5
    assert summary["sender_name"] == "강지훈"
    assert summary["sender_affiliation"] == ""
    assert "explicit R4 confirmation" in summary["next_required_step"]
    assert rows["DNDi_IPK"]["status"] == "ready_to_send"
    assert rows["DNDi_IPK"]["email_body"].endswith("Best,\n강지훈")
    assert "[Your Name]" not in rows["DNDi_IPK"]["email_body"]
    assert "T. cruzi PDE" in rows["DNDi_IPK"]["lead_targets"]
    assert "runs/tcruzi_pde_dndi_ipk_export_current.md" in rows["DNDi_IPK"]["attachment_artifacts"]
    assert rows["M4K_open_science"]["status"] == "ready_to_send"
    assert rows["SGC_dark_kinase"]["status"] == "ready_to_send"
    assert rows["oncology_condition_aware"]["status"] == "ready_to_send"
    assert "runs/caix_oncology_export_current.md" in rows["oncology_condition_aware"]["attachment_artifacts"]
    assert rows["READDI_Korea"]["status"] == "ready_to_send"
    assert "runs/sarscov2_mpro_readdi_export_current.md" in rows["READDI_Korea"]["attachment_artifacts"]
    assert "Mpro plus PLpro" in rows["READDI_Korea"]["proposal_title"]


def test_build_wetlab_partner_first_contact_export_bundle_allows_sender_override() -> None:
    payload = mod.build_payload(*_sample_packets(), sender_name="Jane Doe", sender_affiliation="Example Lab")

    for row in payload["rows"]:
        assert row["email_body"].endswith("Best,\nJane Doe\nExample Lab")
