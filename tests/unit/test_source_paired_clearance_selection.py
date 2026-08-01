from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math

import pytest

from betelgeuze_engine_v2.docking import (
    InteractionAwareTorsionContactConfigV7,
    SourcePairedTorsionRescueAllocation,
    SourcePairedTorsionRescuePolicy,
    TorsionContactRefinementError,
)
from betelgeuze_engine_v2.docking.source_paired_clearance_selection import (
    SourcePairedTorsionRescueClearanceSelectionEvidenceV1,
    SourcePairedTorsionRescueClearanceSelectionPolicyV1,
    evaluate_source_paired_torsion_rescue_clearance_selection_v1,
)


def _allocation() -> SourcePairedTorsionRescueAllocation:
    policy = SourcePairedTorsionRescuePolicy()
    return SourcePairedTorsionRescueAllocation(
        authenticated_input_receipt_sha256="1" * 64,
        guidance_context_sha256="2" * 64,
        budget_sha256="3" * 64,
        rescue_policy_sha256=policy.fingerprint_sha256,
        base_guided_policy_sha256=policy.base_guided_policy.fingerprint_sha256,
        candidate_count=64,
        authority_rotor_count=1,
        v3_target_parent_pairs=(),
        rescue_target_parent_pairs=((1, 0),),
    )


def _evidence(
    **updates: object,
) -> SourcePairedTorsionRescueClearanceSelectionEvidenceV1:
    values: dict[str, object] = {
        "allocation": _allocation(),
        "proposal_index": 1,
        "nested_refinement_receipt_schema_id": (
            "betelgeuze.engine_v2_source_paired_torsion_rescue_receipt/1.1.0"
        ),
        "nested_refinement_receipt_sha256": "4" * 64,
        "generic_v7_config_sha256": (
            "5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337"
        ),
        "vdw_contact_policy_sha256": (
            "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
        ),
        "baseline_coordinates_sha256": "a" * 64,
        "optimized_coordinates_sha256": "b" * 64,
        "torsion_variant_available": True,
        "legacy_v7_selected": False,
        "clearance_measurement_evaluated": True,
        "clearance_measurement_unavailable_reason": "none",
        "clearance_ligand_atom_count": 10,
        "clearance_receptor_atom_count": 10,
        "clearance_full_cartesian_pair_count": 100,
        "baseline_receptor_objective": 4.0,
        "optimized_receptor_objective": 3.0,
        "baseline_internal_objective": 2.0,
        "optimized_internal_objective": 1.5,
        "baseline_combined_objective": 6.0,
        "optimized_combined_objective": 4.5,
        "baseline_minimum_vdw_surface_gap_angstrom": -1.0,
        "optimized_minimum_vdw_surface_gap_angstrom": -0.9,
        "baseline_raw_minimum_distance_angstrom": 2.0,
        "optimized_raw_minimum_distance_angstrom": 2.0,
    }
    values.update(updates)
    return SourcePairedTorsionRescueClearanceSelectionEvidenceV1(**values)


def test_source_paired_clearance_selection_policy_is_frozen_and_shadow_only() -> None:
    active_v7_before = InteractionAwareTorsionContactConfigV7().to_dict()
    policy = SourcePairedTorsionRescueClearanceSelectionPolicyV1()
    payload = policy.to_dict()

    assert payload["required_generic_v7_config_sha256"] == (
        "5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337"
    )
    assert payload["required_rescue_allocation_policy_sha256"] == (
        SourcePairedTorsionRescuePolicy().fingerprint_sha256
    )
    assert payload["required_vdw_contact_policy_sha256"] == (
        "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
    )
    assert payload["candidate_count"] == 64
    assert payload["maximum_variant_count"] == 4
    assert payload["clearance_pair_count_bound"] == 1_000_000
    assert payload["receptor_objective_tolerance_binary64_hex"] == (1.0e-18).hex()
    assert payload["internal_objective_tolerance_binary64_hex"] == (1.0e-18).hex()
    assert payload["combined_objective_tolerance_binary64_hex"] == (1.0e-18).hex()
    assert payload["minimum_vdw_surface_gap_comparator"] == (
        "optimized_strictly_gt_baseline"
    )
    assert payload["raw_minimum_distance_comparator"] == "optimized_gte_baseline"
    assert payload["selection_activation"] == "not_wired_shadow_only"
    assert payload["shadow_input_authority"] == ("caller_supplied_contract_probe_only")
    assert payload["activation_evidence_admissible"] is False
    assert payload["historical_outcomes_used_to_fit_policy"] is False
    assert payload["score_rank_rmsd_posebusters_native_or_case_identity_used"] is False
    assert payload["development_only"] is True
    assert payload["stage0_eligible"] is False
    assert payload["fresh_execution_authorized"] is False
    assert payload["product_promotion_eligible"] is False
    assert payload["claim_safe"] is False
    assert policy.fingerprint_sha256 == (
        "8878d05b96a4204592e3e08ea9fca03f702c4383891f3effcf9a2d7b1fcd53a2"
    )
    assert InteractionAwareTorsionContactConfigV7().to_dict() == active_v7_before

    with pytest.raises(TorsionContactRefinementError, match="frozen to V7"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(
            receptor_objective_tolerance=2.0e-18
        )
    with pytest.raises(TorsionContactRefinementError, match="fixed cap of four"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(maximum_variant_count=5)
    with pytest.raises(TorsionContactRefinementError, match="64 candidates"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(candidate_count=64.0)  # type: ignore[arg-type]
    with pytest.raises(TorsionContactRefinementError, match="pair-count bound"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(
            clearance_pair_count_bound=1_000_000.0  # type: ignore[arg-type]
        )


def test_source_paired_clearance_selection_requires_every_guard() -> None:
    decision = evaluate_source_paired_torsion_rescue_clearance_selection_v1(_evidence())
    payload = decision.to_dict()

    assert decision.shadow_selection_eligible is True
    assert decision.blocker_ids == ()
    assert payload["selection_applied"] is False
    assert payload["returned_coordinates_authority"] == "unchanged_active_v7"
    assert payload["source_lane_retained"] is True
    assert len(decision.evidence_sha256) == 64
    assert (
        hashlib.sha256(
            json.dumps(
                {
                    key: value
                    for key, value in payload.items()
                    if key != "decision_sha256"
                },
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        == decision.decision_sha256
    )

    cases = (
        ({"torsion_variant_available": False}, "torsion_variant_unavailable"),
        ({"legacy_v7_selected": True}, "legacy_v7_already_selected"),
        (
            {"optimized_coordinates_sha256": "a" * 64},
            "optimized_coordinates_unchanged",
        ),
        (
            {"optimized_receptor_objective": 5.0},
            "receptor_objective_regressed",
        ),
        (
            {"optimized_internal_objective": 3.0},
            "internal_objective_regressed",
        ),
        (
            {"optimized_combined_objective": 6.0},
            "combined_objective_not_strictly_improved",
        ),
        (
            {"optimized_minimum_vdw_surface_gap_angstrom": -1.0},
            "minimum_vdw_surface_gap_not_strictly_improved",
        ),
        (
            {"optimized_raw_minimum_distance_angstrom": 1.9},
            "raw_minimum_distance_regressed",
        ),
    )
    for updates, expected_blocker in cases:
        rejected = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
            _evidence(**updates)
        )
        assert rejected.shadow_selection_eligible is False
        assert expected_blocker in rejected.blocker_ids
        assert rejected.to_dict()["selection_applied"] is False

    with pytest.raises(TorsionContactRefinementError, match="blocker IDs"):
        replace(decision, blocker_ids=("fabricated_blocker",))
    with pytest.raises(TorsionContactRefinementError, match="target and parent"):
        replace(decision, parent_proposal_index=None)
    with pytest.raises(TorsionContactRefinementError, match="coordinate-change"):
        replace(
            decision,
            changed_coordinates_guard_passed=False,
            blocker_ids=("optimized_coordinates_unchanged",),
            shadow_selection_eligible=False,
        )


def test_source_paired_clearance_selection_boundaries_are_exact() -> None:
    tolerance = 1.0e-18

    receptor_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_receptor_objective=0.0,
            optimized_receptor_objective=tolerance,
        )
    )
    assert receptor_edge.receptor_objective_guard_passed is True
    receptor_over = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_receptor_objective=0.0,
            optimized_receptor_objective=math.nextafter(tolerance, math.inf),
        )
    )
    assert receptor_over.receptor_objective_guard_passed is False

    internal_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_internal_objective=0.0,
            optimized_internal_objective=tolerance,
        )
    )
    assert internal_edge.internal_objective_guard_passed is True
    internal_over = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_internal_objective=0.0,
            optimized_internal_objective=math.nextafter(tolerance, math.inf),
        )
    )
    assert internal_over.internal_objective_guard_passed is False

    combined_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_combined_objective=2.0 * tolerance,
            optimized_combined_objective=tolerance,
        )
    )
    assert combined_edge.combined_objective_guard_passed is False
    combined_below = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            baseline_combined_objective=2.0 * tolerance,
            optimized_combined_objective=math.nextafter(tolerance, -math.inf),
        )
    )
    assert combined_below.combined_objective_guard_passed is True

    gap_equal = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(optimized_minimum_vdw_surface_gap_angstrom=-1.0)
    )
    assert gap_equal.minimum_vdw_surface_gap_guard_passed is False
    gap_above = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            optimized_minimum_vdw_surface_gap_angstrom=math.nextafter(-1.0, math.inf)
        )
    )
    assert gap_above.minimum_vdw_surface_gap_guard_passed is True

    distance_equal = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(optimized_raw_minimum_distance_angstrom=2.0)
    )
    assert distance_equal.raw_minimum_distance_guard_passed is True
    distance_below = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _evidence(
            optimized_raw_minimum_distance_angstrom=math.nextafter(2.0, -math.inf)
        )
    )
    assert distance_below.raw_minimum_distance_guard_passed is False


def test_source_paired_clearance_selection_unavailability_fails_closed() -> None:
    unavailable = _evidence(
        clearance_measurement_evaluated=False,
        clearance_measurement_unavailable_reason=(
            "full_cartesian_pair_count_exceeds_fixed_bound"
        ),
        clearance_ligand_atom_count=1,
        clearance_receptor_atom_count=1_000_001,
        clearance_full_cartesian_pair_count=1_000_001,
        baseline_minimum_vdw_surface_gap_angstrom=None,
        optimized_minimum_vdw_surface_gap_angstrom=None,
        baseline_raw_minimum_distance_angstrom=None,
        optimized_raw_minimum_distance_angstrom=None,
    )
    decision = evaluate_source_paired_torsion_rescue_clearance_selection_v1(unavailable)
    assert decision.shadow_selection_eligible is False
    assert "clearance_measurement_unavailable" in decision.blocker_ids
    assert decision.to_dict()["selection_applied"] is False

    with pytest.raises(
        TorsionContactRefinementError,
        match="bounded rescue-target clearance must be evaluated",
    ):
        replace(
            unavailable,
            clearance_ligand_atom_count=10,
            clearance_receptor_atom_count=10,
            clearance_full_cartesian_pair_count=100,
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    (
        ({"torsion_variant_available": 1}, "must be boolean"),
        ({"optimized_combined_objective": math.nan}, "finite float"),
        ({"optimized_coordinates_sha256": "A" * 64}, "canonical SHA-256"),
        (
            {"nested_refinement_receipt_schema_id": "unsupported/1.0.0"},
            "requires a V1.1 receipt",
        ),
        ({"generic_v7_config_sha256": "0" * 64}, "V7 identity drifted"),
        ({"vdw_contact_policy_sha256": "0" * 64}, "VDW identity drifted"),
        ({"clearance_ligand_atom_count": 10.0}, "nonnegative integers"),
        ({"clearance_receptor_atom_count": 11}, "counts are inconsistent"),
    ),
)
def test_source_paired_clearance_selection_rejects_noncanonical_evidence(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(TorsionContactRefinementError, match=message):
        _evidence(**updates)
