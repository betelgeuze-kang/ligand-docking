from __future__ import annotations

from tools.product import build_product_pose_sampling_readiness as mod


def test_product_pose_sampling_readiness_is_claim_safe_and_ready() -> None:
    payload = mod.build_product_pose_sampling_readiness(n_starts=6)

    summary = payload["summary"]
    assert summary["status"] == "product_pose_sampling_readiness_ready"
    assert summary["pose_sampling_readiness_ready"] is True
    assert summary["pose_generation_contract_ready"] is True
    assert summary["pocket_detection_ready"] is True
    assert summary["multi_start_pose_ensemble_ready"] is True
    assert summary["pose_rmsd_diversity_surface_ready"] is True
    assert summary["bounded_cross_docking_induced_fit_guard_ready"] is True
    assert summary["pose_claim_boundary_guard_ready"] is True
    assert summary["pose_count"] == 6
    assert summary["cluster_count"] >= 2
    assert summary["cross_docking_pose_count"] == 4
    assert summary["execution_enabled"] is False
    assert summary["docking_results_emitted"] is False
    assert summary["external_state_mutated"] is False
    assert summary["claim_grade_pose_accuracy_ready"] is False
    assert summary["claim_grade_induced_fit_ready"] is False
    assert summary["claim_grade_cross_docking_ready"] is False
    assert "does not claim validated induced-fit" in summary["claim_boundary"]
    assert len(payload["blockers"]) == 0


def test_product_pose_sampling_readiness_blocks_if_required_starts_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        mod,
        "generate_pose_ensemble",
        lambda *args, **kwargs: {
            "status": "pose_ensemble_ready",
            "pose_count": 1,
            "poses": [],
            "claim_boundary": mod.POSE_CLAIM_BOUNDARY,
        },
    )

    payload = mod.build_product_pose_sampling_readiness(n_starts=6)

    summary = payload["summary"]
    assert summary["status"] == "blocked_product_pose_sampling_readiness"
    assert summary["pose_sampling_readiness_ready"] is False
    assert summary["multi_start_pose_ensemble_ready"] is False
    assert summary["blocker_count"] >= 1
    blocked_ids = {row["check_id"] for row in payload["blockers"]}
    assert "multi_start_pose_ensemble_ready" in blocked_ids
