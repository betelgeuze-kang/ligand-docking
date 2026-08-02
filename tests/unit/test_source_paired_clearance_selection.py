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
    SourcePairedTorsionRescueClearanceSelectionPolicyV1,
    SourcePairedTorsionRescueClearanceSelectionProbeInputsV1,
    evaluate_source_paired_torsion_rescue_clearance_selection_v1,
)


class _StringSubclass(str):
    pass


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


def _probe_inputs(
    **updates: object,
) -> SourcePairedTorsionRescueClearanceSelectionProbeInputsV1:
    values: dict[str, object] = {
        "allocation": _allocation(),
        "proposal_index": 1,
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
        "baseline_receptor_objective": 5.0,
        "optimized_receptor_objective": 4.5,
        "baseline_internal_objective": 2.0,
        "optimized_internal_objective": 1.5,
        "baseline_combined_objective": 7.0,
        "optimized_combined_objective": 6.0,
        "baseline_minimum_vdw_surface_gap_angstrom": -1.0,
        "optimized_minimum_vdw_surface_gap_angstrom": -0.9,
        "baseline_raw_minimum_distance_angstrom": 2.0,
        "optimized_raw_minimum_distance_angstrom": 2.0,
    }
    values.update(updates)
    if "baseline_combined_objective" not in updates and (
        "baseline_receptor_objective" in updates
        or "baseline_internal_objective" in updates
    ):
        values["baseline_combined_objective"] = float(
            values["baseline_receptor_objective"]
        ) + float(values["baseline_internal_objective"])
    if "optimized_combined_objective" not in updates and (
        "optimized_receptor_objective" in updates
        or "optimized_internal_objective" in updates
    ):
        values["optimized_combined_objective"] = float(
            values["optimized_receptor_objective"]
        ) + float(values["optimized_internal_objective"])
    return SourcePairedTorsionRescueClearanceSelectionProbeInputsV1(**values)


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
    assert payload["required_base_guided_policy_sha256"] == (
        SourcePairedTorsionRescuePolicy().base_guided_policy.fingerprint_sha256
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
    assert (
        payload["legacy_v7_minimum_selected_receptor_objective_binary64_hex"]
        == (2.0).hex()
    )
    assert (
        payload["legacy_v7_maximum_selected_receptor_objective_binary64_hex"]
        == (4.0).hex()
    )
    assert payload["legacy_v7_selection_flag_rule"] == (
        "variant_available_and_minimum_lte_optimized_lt_maximum"
    )
    assert payload["minimum_vdw_surface_gap_comparator"] == (
        "optimized_strictly_gt_baseline"
    )
    assert payload["raw_minimum_distance_comparator"] == "optimized_gte_baseline"
    assert payload["clearance_metric_integrity_rule"] == (
        "each_surface_gap_strictly_lt_corresponding_raw_distance"
    )
    assert payload["minimum_vdw_radius_sum_angstrom_binary64_hex"] == (2.4).hex()
    assert payload["clearance_metric_rounding_rule"] == (
        "gap_lte_nextafter_raw_minus_minimum_radius_sum_toward_positive_infinity"
    )
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
        "f4bd88910948bd3afad8c1cca6234e9e072ec2b0c4979f04aee7c2931e710b48"
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
    with pytest.raises(TorsionContactRefinementError, match="policy schema"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(
            schema_id=_StringSubclass(policy.schema_id)
        )
    with pytest.raises(TorsionContactRefinementError, match="unsupported.*policy"):
        SourcePairedTorsionRescueClearanceSelectionPolicyV1(
            policy_id=_StringSubclass(policy.policy_id)
        )


def test_source_paired_clearance_selection_requires_every_guard() -> None:
    decision = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs()
    )
    payload = decision.to_dict()

    assert decision.shadow_selection_eligible is True
    assert decision.blocker_ids == ()
    assert payload["selection_applied"] is False
    assert payload["returned_coordinates_authority"] == "unchanged_active_v7"
    assert payload["source_lane_retained"] is True
    assert len(decision.probe_inputs_sha256) == 64
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
        (
            {
                "torsion_variant_available": False,
                "optimized_coordinates_sha256": "a" * 64,
                "optimized_receptor_objective": 5.0,
                "optimized_internal_objective": 2.0,
                "optimized_combined_objective": 7.0,
                "optimized_minimum_vdw_surface_gap_angstrom": -1.0,
                "optimized_raw_minimum_distance_angstrom": 2.0,
            },
            "torsion_variant_unavailable",
        ),
        (
            {
                "optimized_receptor_objective": 3.0,
                "legacy_v7_selected": True,
            },
            "legacy_v7_already_selected",
        ),
        (
            {"optimized_coordinates_sha256": "a" * 64},
            "optimized_coordinates_unchanged",
        ),
        (
            {"optimized_receptor_objective": 6.0},
            "receptor_objective_regressed",
        ),
        (
            {"optimized_internal_objective": 3.0},
            "internal_objective_regressed",
        ),
        (
            {
                "optimized_receptor_objective": 5.0,
                "optimized_internal_objective": 2.0,
                "optimized_combined_objective": 7.0,
            },
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
            _probe_inputs(**updates)
        )
        assert rejected.shadow_selection_eligible is False
        assert expected_blocker in rejected.blocker_ids
        assert rejected.to_dict()["selection_applied"] is False

    with pytest.raises(TypeError):
        replace(decision, probe_inputs_sha256="0" * 64)


def test_source_paired_clearance_selection_boundaries_are_exact() -> None:
    tolerance = 1.0e-18

    receptor_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_receptor_objective=0.0,
            optimized_receptor_objective=tolerance,
        )
    )
    assert receptor_edge.receptor_objective_guard_passed is True
    receptor_over = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_receptor_objective=0.0,
            optimized_receptor_objective=math.nextafter(tolerance, math.inf),
        )
    )
    assert receptor_over.receptor_objective_guard_passed is False

    internal_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_internal_objective=0.0,
            optimized_internal_objective=tolerance,
        )
    )
    assert internal_edge.internal_objective_guard_passed is True
    internal_over = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_internal_objective=0.0,
            optimized_internal_objective=math.nextafter(tolerance, math.inf),
        )
    )
    assert internal_over.internal_objective_guard_passed is False

    combined_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_receptor_objective=tolerance,
            baseline_internal_objective=tolerance,
            baseline_combined_objective=2.0 * tolerance,
            optimized_receptor_objective=0.0,
            optimized_internal_objective=tolerance,
            optimized_combined_objective=tolerance,
        )
    )
    assert combined_edge.combined_objective_guard_passed is False
    combined_below = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            baseline_receptor_objective=tolerance,
            baseline_internal_objective=tolerance,
            baseline_combined_objective=2.0 * tolerance,
            optimized_receptor_objective=0.0,
            optimized_internal_objective=math.nextafter(tolerance, -math.inf),
            optimized_combined_objective=math.nextafter(tolerance, -math.inf),
        )
    )
    assert combined_below.combined_objective_guard_passed is True

    gap_equal = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(optimized_minimum_vdw_surface_gap_angstrom=-1.0)
    )
    assert gap_equal.minimum_vdw_surface_gap_guard_passed is False
    gap_above = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            optimized_minimum_vdw_surface_gap_angstrom=math.nextafter(-1.0, math.inf)
        )
    )
    assert gap_above.minimum_vdw_surface_gap_guard_passed is True

    distance_equal = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(optimized_raw_minimum_distance_angstrom=2.0)
    )
    assert distance_equal.raw_minimum_distance_guard_passed is True
    distance_below = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            optimized_raw_minimum_distance_angstrom=math.nextafter(2.0, -math.inf)
        )
    )
    assert distance_below.raw_minimum_distance_guard_passed is False

    raw_distance = 4.0
    rounding_aware_maximum_gap = math.nextafter(raw_distance - 2.4, math.inf)
    rounding_edge = evaluate_source_paired_torsion_rescue_clearance_selection_v1(
        _probe_inputs(
            optimized_minimum_vdw_surface_gap_angstrom=(rounding_aware_maximum_gap),
            optimized_raw_minimum_distance_angstrom=raw_distance,
        )
    )
    assert rounding_edge.shadow_selection_eligible is True


def test_source_paired_clearance_selection_unavailability_fails_closed() -> None:
    unavailable = _probe_inputs(
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
        ({"generic_v7_config_sha256": "0" * 64}, "V7 identity drifted"),
        ({"vdw_contact_policy_sha256": "0" * 64}, "VDW identity drifted"),
        ({"clearance_ligand_atom_count": 10.0}, "nonnegative integers"),
        ({"clearance_receptor_atom_count": 11}, "counts are inconsistent"),
        (
            {
                "allocation": replace(
                    _allocation(),
                    base_guided_policy_sha256="0" * 64,
                )
            },
            "allocation drifted",
        ),
        (
            {"allocation": replace(_allocation(), candidate_count=64.0)},
            "allocation drifted",
        ),
        (
            {"baseline_combined_objective": 5.9},
            "combined objectives must match",
        ),
        (
            {"optimized_combined_objective": 4.4},
            "combined objectives must match",
        ),
        (
            {
                "baseline_minimum_vdw_surface_gap_angstrom": 3.0,
                "baseline_raw_minimum_distance_angstrom": 2.0,
            },
            "surface gaps must be below",
        ),
        (
            {
                "optimized_minimum_vdw_surface_gap_angstrom": 3.0,
                "optimized_raw_minimum_distance_angstrom": 2.0,
            },
            "surface gaps must be below",
        ),
        (
            {
                "baseline_minimum_vdw_surface_gap_angstrom": 2.0,
                "baseline_raw_minimum_distance_angstrom": 2.0,
            },
            "surface gaps must be below",
        ),
        (
            {
                "optimized_minimum_vdw_surface_gap_angstrom": 2.0,
                "optimized_raw_minimum_distance_angstrom": 2.0,
            },
            "surface gaps must be below",
        ),
        (
            {
                "baseline_minimum_vdw_surface_gap_angstrom": 1.7,
                "baseline_raw_minimum_distance_angstrom": 4.0,
            },
            "minimum radius separation",
        ),
        (
            {
                "optimized_minimum_vdw_surface_gap_angstrom": 1.7,
                "optimized_raw_minimum_distance_angstrom": 4.0,
            },
            "minimum radius separation",
        ),
        (
            {
                "optimized_minimum_vdw_surface_gap_angstrom": math.nextafter(
                    math.nextafter(4.0 - 2.4, math.inf),
                    math.inf,
                ),
                "optimized_raw_minimum_distance_angstrom": 4.0,
            },
            "minimum radius separation",
        ),
        (
            {"torsion_variant_available": False},
            "complete baseline state",
        ),
        (
            {
                "torsion_variant_available": False,
                "optimized_coordinates_sha256": "a" * 64,
                "optimized_receptor_objective": 5.0,
                "optimized_internal_objective": 2.0,
                "optimized_combined_objective": 7.0,
                "optimized_minimum_vdw_surface_gap_angstrom": -0.9,
                "optimized_raw_minimum_distance_angstrom": 2.0,
            },
            "complete baseline state",
        ),
        (
            {"clearance_measurement_unavailable_reason": _StringSubclass("none")},
            "exact string",
        ),
        (
            {
                "torsion_variant_available": False,
                "legacy_v7_selected": True,
            },
            "legacy V7 selection flag contradicts",
        ),
        (
            {"optimized_receptor_objective": 3.0},
            "legacy V7 selection flag contradicts",
        ),
    ),
)
def test_source_paired_clearance_selection_rejects_noncanonical_probe_inputs(
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(TorsionContactRefinementError, match=message):
        _probe_inputs(**updates)
