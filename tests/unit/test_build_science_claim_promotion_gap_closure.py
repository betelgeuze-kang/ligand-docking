from __future__ import annotations

from tools import build_science_claim_promotion_gap_closure as mod


def _gpcr_gate_ready() -> dict:
    return {
        "summary": {
            "promotion_boundary_ready": True,
            "accounting_closed": True,
            "claim_promotion_allowed": False,
        }
    }


def _transporter_ready() -> dict:
    return {
        "summary": {
            "promotion_boundary_ready": True,
            "accounting_closed": True,
            "claim_promotion_allowed": False,
        }
    }


def _wetlab_openmm_ready() -> dict:
    return {
        "summary": {
            "promotion_boundary_ready": True,
            "wetlab_lane_closed": True,
            "openmm_2bead_lane_closed": True,
            "claim_promotion_allowed": False,
        }
    }


def test_science_claim_promotion_gap_closure_complete() -> None:
    payload = mod.build_science_claim_promotion_gap_closure(
        gpcr_gate_packet=_gpcr_gate_ready(),
        transporter_boundary_packet=_transporter_ready(),
        ca2_readiness_packet={"summary": {"ready_row_count": 12, "blocked_row_count": 0, "workbook_row_count": 12}},
        pxr_readiness_packet={"summary": {"ready_row_count": 14, "blocked_row_count": 0}},
        wetlab_openmm_boundary_packet=_wetlab_openmm_ready(),
    )
    summary = payload["summary"]
    assert summary["status"] == "science_claim_promotion_gap_closure_complete"
    assert summary["all_gaps_closed"] is True
    assert summary["closed_gap_count"] == 5
    assert summary["claim_promotion_allowed"] is False
    assert summary["open_gap_ids"] == []
