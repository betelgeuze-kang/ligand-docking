from __future__ import annotations

import math

import torch
import pytest

from betelgeuze_engine.contracts import EngineState
from betelgeuze_engine.physics.terms import LegacyLJTerm
from betelgeuze_engine.residual import (
    FORCE_RESIDUAL_CLAIM_METADATA_SCHEMA_VERSION,
    ForceResidualPolicy,
    apply_guarded_force_residual,
    decide_force_residual,
    validate_force_residual_report_contract,
)
from betelgeuze_engine.validation import (
    energy_drift_smoke_pct,
    finite_difference_force_error,
    neighbor_list_parity_error,
    translation_invariance_error,
)


def test_guarded_force_residual_applies_only_inside_top_k_policy() -> None:
    policy = ForceResidualPolicy(top_k_rank_pct=0.05, abstain_uncertainty=0.75)

    outside = decide_force_residual(rank_pct=0.20, topology_valid=True, uncertainty=0.1, delta_score=0.1, policy=policy)
    invalid = decide_force_residual(rank_pct=0.01, topology_valid=False, uncertainty=0.1, delta_score=0.1, policy=policy)
    uncertain = decide_force_residual(rank_pct=0.01, topology_valid=True, uncertainty=0.9, delta_score=0.1, policy=policy)
    allowed = decide_force_residual(rank_pct=0.01, topology_valid=True, uncertainty=0.1, delta_score=0.1, policy=policy)

    assert outside.apply is False
    assert outside.reason == "outside_top_k_policy"
    assert invalid.reason == "topology_invalid"
    assert uncertain.reason == "uncertainty_abstained"
    assert allowed.apply is True
    assert allowed.delta_score == 0.1
    assert allowed.confidence == 0.9
    assert policy.max_abs_delta_score > 0
    assert policy.abstain_threshold == policy.abstain_uncertainty
    assert policy.max_energy_drift == policy.max_energy_drift_pct

    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    _updated, outside_report = apply_guarded_force_residual(coords, forces, decision=outside, policy=policy)
    outside_metadata = outside_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    assert outside_report.applied is False
    assert outside_report.rank_pct == pytest.approx(0.20)
    assert outside_report.top_k_eligible is False
    assert outside_report.policy_caps["top_k_rank_pct"] == pytest.approx(0.05)
    assert outside_metadata["claim_safe"] is False
    assert outside_metadata["blocked_reason"] == "outside_top_k_policy"
    assert outside_metadata["force_residual_rank_pct"] == pytest.approx(0.20)
    assert outside_metadata["force_residual_top_k_rank_pct"] == pytest.approx(0.05)
    assert outside_metadata["force_residual_top_k_eligible"] is False

    _updated, allowed_report = apply_guarded_force_residual(coords, forces, decision=allowed, policy=policy)
    allowed_metadata = allowed_report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )
    assert allowed_report.applied is True
    assert allowed_report.rank_pct == pytest.approx(0.01)
    assert allowed_report.top_k_eligible is True
    assert allowed_metadata["force_residual_rank_pct"] == pytest.approx(0.01)
    assert allowed_metadata["force_residual_top_k_eligible"] is True


def test_guarded_force_residual_rejects_nonfinite_rank_pct() -> None:
    policy = ForceResidualPolicy(top_k_rank_pct=0.05)
    decision = decide_force_residual(
        rank_pct=math.nan,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=0.1,
        policy=policy,
    )

    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)

    assert decision.apply is False
    assert decision.reason == "rank_pct_nonfinite"
    assert report.applied is False
    assert report.skipped_reason == "rank_pct_nonfinite"
    assert report.top_k_eligible is False
    assert torch.equal(updated, coords)


def test_guarded_force_residual_enforces_delta_score_cap_and_claim_metadata() -> None:
    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(max_abs_delta_score=0.25)

    capped_decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=0.30,
        policy=policy,
    )
    updated, report = apply_guarded_force_residual(coords, forces, decision=capped_decision, policy=policy)
    metadata = report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )

    assert capped_decision.apply is False
    assert capped_decision.reason == "delta_score_cap_exceeded"
    assert report.applied is False
    assert report.delta_score == 0.30
    assert report.rank_pct == pytest.approx(0.01)
    assert report.top_k_eligible is True
    assert report.skipped_reason == "delta_score_cap_exceeded"
    assert report.policy_caps["max_abs_delta_score"] == 0.25
    assert report.policy_caps["abstain_threshold"] == policy.abstain_threshold
    assert torch.equal(updated, coords)
    assert metadata["claim_safe"] is False
    assert metadata["force_residual_applied"] is False
    assert metadata["force_residual_claim_safe"] is False
    assert metadata["force_residual_delta_score"] == 0.30
    assert metadata["force_residual_uncertainty"] == 0.1
    assert metadata["force_residual_confidence"] == 0.9
    assert metadata["force_residual_abstain_threshold"] == policy.abstain_threshold
    assert metadata["blocked_reason"] == "delta_score_cap_exceeded"
    assert metadata["force_residual_policy_caps"]["max_abs_delta_score"] == 0.25
    assert metadata["force_residual_policy_caps"]["abstain_threshold"] == policy.abstain_threshold
    assert metadata["force_residual_delta_score_within_cap"] is False
    assert metadata["force_residual_all_observed_caps_within_policy"] is False
    assert metadata["force_residual_claim_metadata_schema_version"] == FORCE_RESIDUAL_CLAIM_METADATA_SCHEMA_VERSION
    assert metadata["force_residual_policy_caps_ready"] is True
    assert metadata["force_residual_observed_caps_ready"] is False
    assert report.to_dict()["claim_metadata_schema_version"] == FORCE_RESIDUAL_CLAIM_METADATA_SCHEMA_VERSION
    assert report.to_dict()["policy_caps_ready"] is True
    assert report.to_dict()["observed_caps_ready"] is False
    assert report.to_dict()["delta_score_within_cap"] is False
    assert report.to_dict()["all_observed_caps_within_policy"] is False


def test_guarded_force_residual_enforces_caps_and_rollback() -> None:
    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(max_force_norm=5.0, max_displacement=0.05, step_size=0.10)
    decision = decide_force_residual(rank_pct=0.01, topology_valid=True, uncertainty=0.1, delta_score=0.2, policy=policy)

    updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)
    metadata = report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )

    assert report.applied is True
    assert report.claim_safe is True
    assert report.delta_score == 0.2
    assert report.uncertainty == 0.1
    assert report.confidence == 0.9
    assert metadata["claim_safe"] is True
    assert metadata["force_residual_applied"] is True
    assert metadata["force_residual_claim_safe"] is True
    assert metadata["force_residual_confidence"] == 0.9
    assert metadata["force_residual_status"] == "applied"
    assert metadata["force_residual_force_norm_within_cap"] is True
    assert metadata["force_residual_energy_drift_within_cap"] is True
    assert metadata["force_residual_displacement_within_cap"] is True
    assert metadata["force_residual_delta_score_within_cap"] is True
    assert metadata["force_residual_all_observed_caps_within_policy"] is True
    assert metadata["force_residual_claim_metadata_schema_version"] == FORCE_RESIDUAL_CLAIM_METADATA_SCHEMA_VERSION
    assert metadata["force_residual_policy_caps_ready"] is True
    assert metadata["force_residual_observed_caps_ready"] is True
    assert set(metadata["force_residual_required_policy_caps"]).issuperset(
        {"max_abs_delta_score", "max_force_norm", "max_displacement", "max_energy_drift", "abstain_threshold"}
    )
    assert report.policy_caps["max_abs_delta_score"] == policy.max_abs_delta_score
    assert report.policy_caps["max_force_norm"] == policy.max_force_norm
    assert report.policy_caps["abstain_threshold"] == policy.abstain_threshold
    assert report.policy_caps["max_energy_drift"] == policy.max_energy_drift
    assert report.displacement_rmsd <= policy.max_displacement + 1e-7
    assert report.to_dict()["all_observed_caps_within_policy"] is True
    assert report.to_dict()["policy_caps_ready"] is True
    assert report.to_dict()["observed_caps_ready"] is True
    assert torch.isfinite(updated).all()

    too_large = torch.ones_like(coords) * 100.0
    rolled_back, capped = apply_guarded_force_residual(coords, too_large, decision=decision, policy=policy)
    assert capped.applied is False
    assert capped.claim_safe is False
    assert capped.skipped_reason == "max_force_norm_exceeded"
    assert capped.abstention_reason == "max_force_norm_exceeded"
    assert capped.to_dict()["force_norm_within_cap"] is False
    assert capped.to_dict()["all_observed_caps_within_policy"] is False
    assert torch.equal(rolled_back, coords)


def test_guarded_force_residual_rolls_back_on_energy_drift() -> None:
    coords = torch.zeros(1, 1, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(max_energy_drift_pct=1.0)
    decision = decide_force_residual(rank_pct=0.01, topology_valid=True, uncertainty=0.1, delta_score=0.1, policy=policy)

    updated, report = apply_guarded_force_residual(
        coords,
        forces,
        decision=decision,
        policy=policy,
        energy_before=10.0,
        energy_after=12.0,
    )

    assert report.applied is False
    assert report.skipped_reason == "energy_drift_exceeded"
    assert report.abstention_reason == "energy_drift_exceeded"
    assert report.policy_caps["max_energy_drift_pct"] == policy.max_energy_drift_pct
    assert report.policy_caps["max_energy_drift"] == policy.max_energy_drift
    assert report.to_dict()["energy_drift_within_cap"] is False
    assert report.to_dict()["all_observed_caps_within_policy"] is False
    assert torch.equal(updated, coords)


def test_guarded_force_residual_rejects_invalid_policy_caps_before_apply() -> None:
    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(max_force_norm=0.0)

    decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=0.1,
        policy=policy,
    )
    updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)
    metadata = report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )

    assert policy.policy_caps_ready() is False
    assert decision.apply is False
    assert decision.reason == "policy_caps_invalid"
    assert report.applied is False
    assert report.policy_caps_ready is False
    assert report.observed_caps_ready is False
    assert report.to_dict()["policy_caps_ready"] is False
    assert report.to_dict()["observed_caps_ready"] is False
    assert metadata["claim_safe"] is False
    assert metadata["force_residual_policy_caps_ready"] is False
    assert metadata["force_residual_observed_caps_ready"] is False
    assert metadata["blocked_reason"] == "policy_caps_invalid"
    assert torch.equal(updated, coords)


def test_guarded_force_residual_abstains_on_low_confidence_threshold() -> None:
    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(abstain_uncertainty=0.75)
    decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.80,
        delta_score=0.1,
        policy=policy,
    )

    updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)
    metadata = report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )

    assert decision.apply is False
    assert decision.reason == "uncertainty_abstained"
    assert decision.confidence == pytest.approx(0.2)
    assert report.applied is False
    assert report.abstention_reason == "uncertainty_abstained"
    assert report.confidence == pytest.approx(0.2)
    assert report.policy_caps["abstain_threshold"] == 0.75
    assert metadata["claim_safe"] is False
    assert metadata["force_residual_status"] == "abstained"
    assert metadata["force_residual_abstention_reason"] == "uncertainty_abstained"
    assert metadata["force_residual_abstain_threshold"] == 0.75
    assert torch.equal(updated, coords)


def test_guarded_force_residual_report_contract_blocks_metadata_drift() -> None:
    coords = torch.zeros(1, 2, 3)
    forces = torch.ones_like(coords)
    policy = ForceResidualPolicy(max_force_norm=5.0, max_displacement=0.05, step_size=0.10)
    decision = decide_force_residual(
        rank_pct=0.01,
        topology_valid=True,
        uncertainty=0.1,
        delta_score=0.2,
        policy=policy,
    )
    _updated, report = apply_guarded_force_residual(coords, forces, decision=decision, policy=policy)
    metadata = report.to_claim_metadata(
        {
            "topology_fidelity": "sequence_mapped",
            "ligand_topology_valid": True,
            "claim_safe": True,
            "blocked_reason": "",
        }
    )

    validate_force_residual_report_contract(report, claim_metadata=metadata)

    missing = dict(metadata)
    missing.pop("force_residual_policy_caps")
    with pytest.raises(ValueError, match="force residual claim metadata missing keys"):
        validate_force_residual_report_contract(report, claim_metadata=missing)

    drifted = dict(metadata)
    drifted["force_residual_observed_caps_ready"] = False
    with pytest.raises(ValueError, match="observed caps mismatch"):
        validate_force_residual_report_contract(report, claim_metadata=drifted)


def test_force_validation_helpers_cover_finite_difference_and_translation() -> None:
    term = LegacyLJTerm(sigma=1.0, epsilon=0.5)
    state = EngineState(
        coords=torch.tensor([[[0.0, 0.0, 0.0], [4.0, 0.0, 0.0]]], dtype=torch.float64),
        atom_types=torch.tensor([0, 0]),
    )

    assert finite_difference_force_error(term, state, atom_index=0, coord_index=0) < 1e-6
    assert (
        translation_invariance_error(
            term,
            state,
            torch.tensor([[[7.0, -2.0, 1.0]]], dtype=torch.float64),
        )
        < 1e-9
    )
    assert neighbor_list_parity_error(state.coords, cutoff=8.0) == 0.0
    assert energy_drift_smoke_pct(term, state, step_size=1e-4) < 1e-2
