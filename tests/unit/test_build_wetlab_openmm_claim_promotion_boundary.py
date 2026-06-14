from __future__ import annotations

from tools import build_wetlab_openmm_claim_promotion_boundary as mod


def test_openmm_lane_closes_when_scorecard_is_blocked_only_by_ligand_scope() -> None:
    payload = mod.build_wetlab_openmm_claim_promotion_boundary(
        accuracy_packet={
            "summary": {
                "status": "blocked_accuracy_parity",
                "pass_row_count": 4,
                "restricted_pass_row_count": 1,
                "blocked_row_count": 0,
                "openmm_class_claim_allowed": True,
            },
            "rows": [
                {
                    "axis": "physics_dynamics",
                    "status": "pass",
                    "commercial_parity_claim_allowed": True,
                },
                {
                    "axis": "ligand_ranking",
                    "status": "restricted_pass",
                    "commercial_parity_claim_allowed": False,
                },
            ],
        },
        openmm_packet={"summary": {"pass_count": 11}},
        wetlab_packet={"summary": {"hard_block_count": 0}},
    )

    summary = payload["summary"]
    assert summary["status"] == "wetlab_openmm_claim_promotion_boundary_ready"
    assert summary["openmm_2bead_lane_closed"] is True
    assert summary["wetlab_lane_closed"] is True
    assert summary["claim_promotion_allowed"] is False
