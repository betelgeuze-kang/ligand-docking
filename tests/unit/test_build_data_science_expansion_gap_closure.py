from __future__ import annotations

from tools import build_data_science_expansion_gap_closure as mod


def test_data_science_expansion_gap_closure_with_curated_transporter_csv() -> None:
    payload = mod.build_data_science_expansion_gap_closure(
        transporter_membrane_packet={"summary": {"status": "transporter_membrane_readiness_ready", "p0_open_count": 0}},
        ca2_readiness_packet={"summary": {"ready_row_count": 12, "blocked_row_count": 0}},
        pxr_readiness_packet={"summary": {"ready_row_count": 14, "blocked_row_count": 0}},
        cameo_architecture_packet={"summary": {"local_validation_protocol_ready": True, "receiver_api_readiness_ready": True}},
        idp_promotion_packet={"summary": {"wider_shadow_safe_lane_admitted": True, "bounded_lane_closure_ready": True}},
        gpcr_breadth_packet={"summary": {"gpcr_residual_proof_breadth_gate_ready": True, "effective_gpcr_breadth_count": 7}},
        accuracy_parity_packet={"summary": {"status": "green", "pass_row_count": 5}},
    )
    summary = payload["summary"]
    assert summary["status"] == "data_science_expansion_gap_closure_complete"
    assert summary["closed_gap_count"] == 7
    assert summary["open_item_ids"] == []
