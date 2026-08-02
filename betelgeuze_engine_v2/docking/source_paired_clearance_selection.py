"""Predeclared shadow selection for source-paired torsion clearance.

This module freezes a development-only decision rule before any subsequent
historical A/B.  It is intentionally not wired into a refiner or runner: the
active V7/V1.1 path and every returned coordinate remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math

from .contact_validity import VdwContactPolicy
from .guided_placement import (
    MAX_UNIFORM_TORSION_RESCUE_VARIANTS,
    SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT,
    SourcePairedTorsionRescueAllocation,
    SourcePairedTorsionRescuePolicy,
)
from .torsion_contact_refinement import (
    INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
    MAX_RECEPTOR_CLEARANCE_PAIR_COUNT,
    SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256,
    InteractionAwareTorsionContactConfigV7,
    TorsionContactRefinementError,
)


SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_clearance_selection_policy/1.0.0"
)
SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_DECISION_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_torsion_rescue_clearance_selection_"
    "decision/1.0.0"
)
SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_ID = (
    "betelgeuze.engine_v2_historical_development_source_paired_torsion_rescue_"
    "clearance_selection/1.0.0"
)

_FROZEN_V7_CONFIG_SHA256 = (
    "5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337"
)
_FROZEN_OBJECTIVE_TOLERANCE = float.fromhex("0x1.2725dd1d243acp-60")
_FROZEN_V7_MINIMUM_SELECTED_RECEPTOR_OBJECTIVE = 2.0
_FROZEN_V7_MAXIMUM_SELECTED_RECEPTOR_OBJECTIVE = 4.0
_FROZEN_MINIMUM_VDW_RADIUS_SUM_ANGSTROM = 2.4
_FROZEN_MAXIMUM_VDW_RADIUS_SUM_ANGSTROM = 4.62
_FROZEN_RESCUE_ALLOCATION_POLICY_SHA256 = (
    "1930119181619f603f563e3e2aabc8b7ae1347b58e2fcf0a657a7b234f8bb8a6"
)
_FROZEN_BASE_GUIDED_POLICY_SHA256 = (
    "2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f"
)
_FROZEN_VDW_CONTACT_POLICY_SHA256 = (
    "acd011160586307d92ee2ff26a62183aaac5dbd9d12093ac13f018f3787c3f8e"
)
_FROZEN_CANDIDATE_COUNT = 64
_FROZEN_MAXIMUM_VARIANT_COUNT = 4
_FROZEN_CLEARANCE_PAIR_COUNT_BOUND = 1_000_000
_FROZEN_POLICY_SHA256 = (
    "e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad"
)
_DECISION_GUARD_NAMES = (
    "target_scope_guard_passed",
    "clearance_measurement_guard_passed",
    "torsion_variant_guard_passed",
    "legacy_v7_unselected_guard_passed",
    "changed_coordinates_guard_passed",
    "receptor_objective_guard_passed",
    "internal_objective_guard_passed",
    "combined_objective_guard_passed",
    "minimum_vdw_surface_gap_guard_passed",
    "raw_minimum_distance_guard_passed",
)
_DECISION_BLOCKER_IDS = (
    "not_fixed_rescue_target",
    "clearance_measurement_unavailable",
    "torsion_variant_unavailable",
    "legacy_v7_already_selected",
    "optimized_coordinates_unchanged",
    "receptor_objective_regressed",
    "internal_objective_regressed",
    "combined_objective_not_strictly_improved",
    "minimum_vdw_surface_gap_not_strictly_improved",
    "raw_minimum_distance_regressed",
)


def _require_frozen_dependencies() -> None:
    v7_config = InteractionAwareTorsionContactConfigV7()
    rescue_policy = SourcePairedTorsionRescuePolicy()
    vdw_policy = VdwContactPolicy()
    if (
        v7_config.fingerprint_sha256 != _FROZEN_V7_CONFIG_SHA256
        or v7_config.penalty_tolerance != _FROZEN_OBJECTIVE_TOLERANCE
        or v7_config.minimum_selected_final_receptor_penalty
        != _FROZEN_V7_MINIMUM_SELECTED_RECEPTOR_OBJECTIVE
        or v7_config.maximum_selected_final_receptor_penalty
        != _FROZEN_V7_MAXIMUM_SELECTED_RECEPTOR_OBJECTIVE
        or rescue_policy.fingerprint_sha256 != _FROZEN_RESCUE_ALLOCATION_POLICY_SHA256
        or rescue_policy.base_guided_policy.fingerprint_sha256
        != _FROZEN_BASE_GUIDED_POLICY_SHA256
        or SOURCE_PAIRED_TORSION_RESCUE_VDW_CONTACT_POLICY_SHA256
        != _FROZEN_VDW_CONTACT_POLICY_SHA256
        or SOURCE_PAIRED_TORSION_RESCUE_CANDIDATE_COUNT != _FROZEN_CANDIDATE_COUNT
        or MAX_UNIFORM_TORSION_RESCUE_VARIANTS != _FROZEN_MAXIMUM_VARIANT_COUNT
        or MAX_RECEPTOR_CLEARANCE_PAIR_COUNT != _FROZEN_CLEARANCE_PAIR_COUNT_BOUND
        or min(vdw_policy.radii_angstrom.values()) * 2.0
        != _FROZEN_MINIMUM_VDW_RADIUS_SUM_ANGSTROM
        or max(vdw_policy.radii_angstrom.values()) * 2.0
        != _FROZEN_MAXIMUM_VDW_RADIUS_SUM_ANGSTROM
    ):
        raise TorsionContactRefinementError(
            "source-paired clearance-selection frozen dependency drift"
        )


_require_frozen_dependencies()


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise TorsionContactRefinementError(
            "source-paired clearance-selection state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TorsionContactRefinementError(f"{name} must be canonical SHA-256")
    return value


def _finite_float(value: object, *, name: str) -> float:
    if type(value) is not float or not math.isfinite(value):
        raise TorsionContactRefinementError(f"{name} must be a finite float")
    return value


@dataclass(frozen=True, slots=True)
class SourcePairedTorsionRescueClearanceSelectionPolicyV1:
    """Immutable, outcome-unfitted shadow policy for one later historical A/B."""

    receptor_objective_tolerance: float = _FROZEN_OBJECTIVE_TOLERANCE
    internal_objective_tolerance: float = _FROZEN_OBJECTIVE_TOLERANCE
    combined_objective_tolerance: float = _FROZEN_OBJECTIVE_TOLERANCE
    candidate_count: int = _FROZEN_CANDIDATE_COUNT
    maximum_variant_count: int = _FROZEN_MAXIMUM_VARIANT_COUNT
    clearance_pair_count_bound: int = _FROZEN_CLEARANCE_PAIR_COUNT_BOUND
    policy_id: str = SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_ID
    schema_id: str = SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.schema_id) is not str or self.schema_id != (
            SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_SCHEMA_ID
        ):
            raise TorsionContactRefinementError(
                "unsupported source-paired clearance-selection policy schema"
            )
        if type(self.policy_id) is not str or self.policy_id != (
            SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_ID
        ):
            raise TorsionContactRefinementError(
                "unsupported source-paired clearance-selection policy"
            )
        for name in (
            "receptor_objective_tolerance",
            "internal_objective_tolerance",
            "combined_objective_tolerance",
        ):
            value = _finite_float(getattr(self, name), name=name)
            if value != _FROZEN_OBJECTIVE_TOLERANCE:
                raise TorsionContactRefinementError(
                    "source-paired objective tolerances are frozen to V7"
                )
        if (
            type(self.candidate_count) is not int
            or self.candidate_count != _FROZEN_CANDIDATE_COUNT
        ):
            raise TorsionContactRefinementError(
                "source-paired clearance selection requires 64 candidates"
            )
        if (
            type(self.maximum_variant_count) is not int
            or self.maximum_variant_count != _FROZEN_MAXIMUM_VARIANT_COUNT
        ):
            raise TorsionContactRefinementError(
                "source-paired clearance selection requires the fixed cap of four"
            )
        if (
            type(self.clearance_pair_count_bound) is not int
            or self.clearance_pair_count_bound != _FROZEN_CLEARANCE_PAIR_COUNT_BOUND
        ):
            raise TorsionContactRefinementError(
                "source-paired clearance pair-count bound is frozen"
            )
        fingerprint = _sha256(self._projection())
        if fingerprint != _FROZEN_POLICY_SHA256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection policy projection drift"
            )
        object.__setattr__(self, "_fingerprint_sha256", fingerprint)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "policy_id": self.policy_id,
            "required_nested_refinement_receipt_schema_id": (
                INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
            ),
            "required_generic_v7_config_sha256": _FROZEN_V7_CONFIG_SHA256,
            "required_rescue_allocation_policy_sha256": (
                _FROZEN_RESCUE_ALLOCATION_POLICY_SHA256
            ),
            "required_base_guided_policy_sha256": (_FROZEN_BASE_GUIDED_POLICY_SHA256),
            "required_vdw_contact_policy_sha256": (_FROZEN_VDW_CONTACT_POLICY_SHA256),
            "candidate_count": self.candidate_count,
            "maximum_variant_count": self.maximum_variant_count,
            "clearance_pair_count_bound": self.clearance_pair_count_bound,
            "receptor_objective_tolerance_binary64_hex": (
                self.receptor_objective_tolerance.hex()
            ),
            "internal_objective_tolerance_binary64_hex": (
                self.internal_objective_tolerance.hex()
            ),
            "combined_objective_tolerance_binary64_hex": (
                self.combined_objective_tolerance.hex()
            ),
            "legacy_v7_minimum_selected_receptor_objective_binary64_hex": (
                _FROZEN_V7_MINIMUM_SELECTED_RECEPTOR_OBJECTIVE.hex()
            ),
            "legacy_v7_maximum_selected_receptor_objective_binary64_hex": (
                _FROZEN_V7_MAXIMUM_SELECTED_RECEPTOR_OBJECTIVE.hex()
            ),
            "legacy_v7_selection_flag_rule": (
                "variant_available_and_minimum_lte_optimized_lt_maximum"
            ),
            "receptor_objective_comparator": ("optimized_lte_baseline_plus_tolerance"),
            "internal_objective_comparator": ("optimized_lte_baseline_plus_tolerance"),
            "combined_objective_comparator": (
                "optimized_strictly_lt_baseline_minus_tolerance"
            ),
            "minimum_vdw_surface_gap_comparator": "optimized_strictly_gt_baseline",
            "raw_minimum_distance_comparator": "optimized_gte_baseline",
            "clearance_metric_integrity_rule": (
                "each_surface_gap_strictly_lt_corresponding_raw_distance"
            ),
            "minimum_vdw_radius_sum_angstrom_binary64_hex": (
                _FROZEN_MINIMUM_VDW_RADIUS_SUM_ANGSTROM.hex()
            ),
            "maximum_vdw_radius_sum_angstrom_binary64_hex": (
                _FROZEN_MAXIMUM_VDW_RADIUS_SUM_ANGSTROM.hex()
            ),
            "clearance_metric_rounding_rule": (
                "gap_lte_nextafter_raw_minus_minimum_radius_sum_toward_"
                "positive_infinity"
            ),
            "clearance_metric_lower_rounding_rule": (
                "gap_gte_nextafter_raw_minus_maximum_radius_sum_toward_"
                "negative_infinity"
            ),
            "coordinate_comparator": "optimized_sha256_not_equal_baseline_sha256",
            "legacy_v7_selection_action": "retain_legacy_v7",
            "otherwise_eligible_action": "shadow_eligible_only",
            "measurement_unavailable_action": "retain_legacy_v7",
            "selection_activation": "not_wired_shadow_only",
            "shadow_input_authority": "caller_supplied_contract_probe_only",
            "activation_evidence_admissible": False,
            "historical_outcomes_used_to_fit_policy": False,
            "score_rank_rmsd_posebusters_native_or_case_identity_used": False,
            "result_dependent_allocation": False,
            "source_lane_retention_required": True,
            "candidate_denominator_changed": False,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection policy changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class SourcePairedTorsionRescueClearanceSelectionProbeInputsV1:
    """Caller-supplied, non-authoritative inputs to the shadow predicate."""

    allocation: SourcePairedTorsionRescueAllocation
    proposal_index: int
    source_refinement_receipt_schema_id: str
    generic_v7_config_sha256: str
    vdw_contact_policy_sha256: str
    baseline_coordinates_sha256: str
    optimized_coordinates_sha256: str
    torsion_variant_available: bool
    legacy_v7_selected: bool
    clearance_measurement_evaluated: bool
    clearance_measurement_unavailable_reason: str
    clearance_ligand_atom_count: int
    clearance_receptor_atom_count: int
    clearance_full_cartesian_pair_count: int
    baseline_receptor_objective: float
    optimized_receptor_objective: float
    baseline_internal_objective: float
    optimized_internal_objective: float
    baseline_combined_objective: float
    optimized_combined_objective: float
    baseline_minimum_vdw_surface_gap_angstrom: float | None
    optimized_minimum_vdw_surface_gap_angstrom: float | None
    baseline_raw_minimum_distance_angstrom: float | None
    optimized_raw_minimum_distance_angstrom: float | None
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.allocation, SourcePairedTorsionRescueAllocation):
            raise TypeError("allocation must be SourcePairedTorsionRescueAllocation")
        if (
            type(self.allocation.candidate_count) is not int
            or self.allocation.candidate_count != _FROZEN_CANDIDATE_COUNT
            or self.allocation.rescue_policy_sha256
            != _FROZEN_RESCUE_ALLOCATION_POLICY_SHA256
            or self.allocation.base_guided_policy_sha256
            != _FROZEN_BASE_GUIDED_POLICY_SHA256
            or len(self.allocation.rescue_target_parent_pairs)
            > _FROZEN_MAXIMUM_VARIANT_COUNT
        ):
            raise TorsionContactRefinementError(
                "source-paired clearance-selection allocation drifted"
            )
        self.allocation.allocation_sha256
        if (
            type(self.proposal_index) is not int
            or not 0 <= self.proposal_index < self.allocation.candidate_count
        ):
            raise TorsionContactRefinementError(
                "source-paired clearance-selection proposal index is invalid"
            )
        if (
            type(self.source_refinement_receipt_schema_id) is not str
            or self.source_refinement_receipt_schema_id
            != INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID
        ):
            raise TorsionContactRefinementError(
                "clearance-selection probes require the V1.1 source receipt schema"
            )
        for name in (
            "generic_v7_config_sha256",
            "vdw_contact_policy_sha256",
            "baseline_coordinates_sha256",
            "optimized_coordinates_sha256",
        ):
            _digest(getattr(self, name), name=name)
        if self.generic_v7_config_sha256 != _FROZEN_V7_CONFIG_SHA256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection V7 identity drifted"
            )
        if self.vdw_contact_policy_sha256 != _FROZEN_VDW_CONTACT_POLICY_SHA256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection VDW identity drifted"
            )
        for name in (
            "torsion_variant_available",
            "legacy_v7_selected",
            "clearance_measurement_evaluated",
        ):
            if type(getattr(self, name)) is not bool:
                raise TorsionContactRefinementError(f"{name} must be boolean")
        if type(self.clearance_measurement_unavailable_reason) is not str:
            raise TorsionContactRefinementError(
                "clearance measurement reason must be an exact string"
            )
        for name in (
            "clearance_ligand_atom_count",
            "clearance_receptor_atom_count",
            "clearance_full_cartesian_pair_count",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise TorsionContactRefinementError(
                    "clearance counts must be nonnegative integers"
                )
        for name in (
            "baseline_receptor_objective",
            "optimized_receptor_objective",
            "baseline_internal_objective",
            "optimized_internal_objective",
            "baseline_combined_objective",
            "optimized_combined_objective",
        ):
            value = _finite_float(getattr(self, name), name=name)
            if value < 0.0:
                raise TorsionContactRefinementError(
                    "source-paired objective values must be nonnegative"
                )
        if (
            self.baseline_combined_objective
            != self.baseline_receptor_objective + self.baseline_internal_objective
            or self.optimized_combined_objective
            != self.optimized_receptor_objective + self.optimized_internal_objective
        ):
            raise TorsionContactRefinementError(
                "combined objectives must match receptor plus internal components"
            )
        expected_legacy_v7_selected = bool(
            self.torsion_variant_available
            and _FROZEN_V7_MINIMUM_SELECTED_RECEPTOR_OBJECTIVE
            <= self.optimized_receptor_objective
            < _FROZEN_V7_MAXIMUM_SELECTED_RECEPTOR_OBJECTIVE
        )
        if self.legacy_v7_selected is not expected_legacy_v7_selected:
            raise TorsionContactRefinementError(
                "legacy V7 selection flag contradicts variant availability or window"
            )

        target_indices = {
            target for target, _parent in self.allocation.rescue_target_parent_pairs
        }
        is_target = self.proposal_index in target_indices
        if is_target and (
            self.clearance_ligand_atom_count <= 0
            or self.clearance_receptor_atom_count <= 0
            or self.clearance_ligand_atom_count * self.clearance_receptor_atom_count
            != self.clearance_full_cartesian_pair_count
        ):
            raise TorsionContactRefinementError(
                "rescue-target clearance counts are inconsistent"
            )
        clearance_names = (
            "baseline_minimum_vdw_surface_gap_angstrom",
            "optimized_minimum_vdw_surface_gap_angstrom",
            "baseline_raw_minimum_distance_angstrom",
            "optimized_raw_minimum_distance_angstrom",
        )
        if is_target and (
            self.clearance_full_cartesian_pair_count
            <= _FROZEN_CLEARANCE_PAIR_COUNT_BOUND
        ):
            if (
                not self.clearance_measurement_evaluated
                or self.clearance_measurement_unavailable_reason != "none"
            ):
                raise TorsionContactRefinementError(
                    "bounded rescue-target clearance must be evaluated"
                )
            for name in clearance_names:
                _finite_float(getattr(self, name), name=name)
            if (
                self.baseline_raw_minimum_distance_angstrom is not None
                and self.baseline_raw_minimum_distance_angstrom < 0.0
            ) or (
                self.optimized_raw_minimum_distance_angstrom is not None
                and self.optimized_raw_minimum_distance_angstrom < 0.0
            ):
                raise TorsionContactRefinementError(
                    "raw minimum distances must be nonnegative"
                )
            if (
                self.baseline_minimum_vdw_surface_gap_angstrom is None
                or self.optimized_minimum_vdw_surface_gap_angstrom is None
                or self.baseline_raw_minimum_distance_angstrom is None
                or self.optimized_raw_minimum_distance_angstrom is None
            ):
                raise TorsionContactRefinementError(
                    "evaluated clearance values are unavailable"
                )
            if (
                self.baseline_minimum_vdw_surface_gap_angstrom
                >= self.baseline_raw_minimum_distance_angstrom
                or self.optimized_minimum_vdw_surface_gap_angstrom
                >= self.optimized_raw_minimum_distance_angstrom
            ):
                raise TorsionContactRefinementError(
                    "VDW surface gaps must be below raw minimum distances"
                )
            if self.baseline_minimum_vdw_surface_gap_angstrom > math.nextafter(
                self.baseline_raw_minimum_distance_angstrom
                - _FROZEN_MINIMUM_VDW_RADIUS_SUM_ANGSTROM,
                math.inf,
            ) or self.optimized_minimum_vdw_surface_gap_angstrom > math.nextafter(
                self.optimized_raw_minimum_distance_angstrom
                - _FROZEN_MINIMUM_VDW_RADIUS_SUM_ANGSTROM,
                math.inf,
            ):
                raise TorsionContactRefinementError(
                    "VDW surface gaps lack the frozen minimum radius separation"
                )
            if self.baseline_minimum_vdw_surface_gap_angstrom < math.nextafter(
                self.baseline_raw_minimum_distance_angstrom
                - _FROZEN_MAXIMUM_VDW_RADIUS_SUM_ANGSTROM,
                -math.inf,
            ) or self.optimized_minimum_vdw_surface_gap_angstrom < math.nextafter(
                self.optimized_raw_minimum_distance_angstrom
                - _FROZEN_MAXIMUM_VDW_RADIUS_SUM_ANGSTROM,
                -math.inf,
            ):
                raise TorsionContactRefinementError(
                    "VDW surface gaps exceed the frozen maximum radius separation"
                )
        elif is_target:
            if (
                self.clearance_measurement_evaluated
                or self.clearance_measurement_unavailable_reason
                != "full_cartesian_pair_count_exceeds_fixed_bound"
                or any(getattr(self, name) is not None for name in clearance_names)
            ):
                raise TorsionContactRefinementError(
                    "unbounded rescue-target clearance must fail closed"
                )
        elif (
            self.clearance_measurement_evaluated
            or self.clearance_measurement_unavailable_reason
            != "not_source_paired_rescue_target"
            or self.clearance_ligand_atom_count != 0
            or self.clearance_receptor_atom_count != 0
            or self.clearance_full_cartesian_pair_count != 0
            or any(getattr(self, name) is not None for name in clearance_names)
        ):
            raise TorsionContactRefinementError(
                "non-target clearance probe inputs are inconsistent"
            )
        if not self.torsion_variant_available and (
            self.optimized_coordinates_sha256 != self.baseline_coordinates_sha256
            or self.optimized_receptor_objective != self.baseline_receptor_objective
            or self.optimized_internal_objective != self.baseline_internal_objective
            or self.optimized_combined_objective != self.baseline_combined_objective
            or self.optimized_minimum_vdw_surface_gap_angstrom
            != self.baseline_minimum_vdw_surface_gap_angstrom
            or self.optimized_raw_minimum_distance_angstrom
            != self.baseline_raw_minimum_distance_angstrom
        ):
            raise TorsionContactRefinementError(
                "unavailable torsion variants must retain the complete baseline state"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        def optional_hex(value: float | None) -> str | None:
            return None if value is None else value.hex()

        return {
            "allocation_sha256": self.allocation.allocation_sha256,
            "proposal_index": self.proposal_index,
            "source_refinement_receipt_schema_id": (
                self.source_refinement_receipt_schema_id
            ),
            "generic_v7_config_sha256": self.generic_v7_config_sha256,
            "vdw_contact_policy_sha256": self.vdw_contact_policy_sha256,
            "baseline_coordinates_sha256": self.baseline_coordinates_sha256,
            "optimized_coordinates_sha256": self.optimized_coordinates_sha256,
            "torsion_variant_available": self.torsion_variant_available,
            "legacy_v7_selected": self.legacy_v7_selected,
            "clearance_measurement_evaluated": (self.clearance_measurement_evaluated),
            "clearance_measurement_unavailable_reason": (
                self.clearance_measurement_unavailable_reason
            ),
            "clearance_ligand_atom_count": self.clearance_ligand_atom_count,
            "clearance_receptor_atom_count": self.clearance_receptor_atom_count,
            "clearance_full_cartesian_pair_count": (
                self.clearance_full_cartesian_pair_count
            ),
            "baseline_receptor_objective_binary64_hex": (
                self.baseline_receptor_objective.hex()
            ),
            "optimized_receptor_objective_binary64_hex": (
                self.optimized_receptor_objective.hex()
            ),
            "baseline_internal_objective_binary64_hex": (
                self.baseline_internal_objective.hex()
            ),
            "optimized_internal_objective_binary64_hex": (
                self.optimized_internal_objective.hex()
            ),
            "baseline_combined_objective_binary64_hex": (
                self.baseline_combined_objective.hex()
            ),
            "optimized_combined_objective_binary64_hex": (
                self.optimized_combined_objective.hex()
            ),
            "baseline_minimum_vdw_surface_gap_angstrom_binary64_hex": (
                optional_hex(self.baseline_minimum_vdw_surface_gap_angstrom)
            ),
            "optimized_minimum_vdw_surface_gap_angstrom_binary64_hex": (
                optional_hex(self.optimized_minimum_vdw_surface_gap_angstrom)
            ),
            "baseline_raw_minimum_distance_angstrom_binary64_hex": optional_hex(
                self.baseline_raw_minimum_distance_angstrom
            ),
            "optimized_raw_minimum_distance_angstrom_binary64_hex": optional_hex(
                self.optimized_raw_minimum_distance_angstrom
            ),
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection probe inputs changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True, init=False)
class _SourcePairedTorsionRescueClearanceSelectionShadowDecisionV1:
    """Self-hashed result values from the non-activated shadow predicate."""

    policy_sha256: str
    probe_inputs_sha256: str
    allocation_sha256: str
    proposal_index: int
    parent_proposal_index: int | None
    target_scope_guard_passed: bool
    clearance_measurement_guard_passed: bool
    torsion_variant_guard_passed: bool
    legacy_v7_unselected_guard_passed: bool
    changed_coordinates_guard_passed: bool
    receptor_objective_guard_passed: bool
    internal_objective_guard_passed: bool
    combined_objective_guard_passed: bool
    minimum_vdw_surface_gap_guard_passed: bool
    raw_minimum_distance_guard_passed: bool
    blocker_ids: tuple[str, ...]
    shadow_selection_eligible: bool
    baseline_coordinates_sha256: str
    optimized_coordinates_sha256: str
    schema_id: str = SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_DECISION_SCHEMA_ID
    _decision_sha256: str = field(init=False, repr=False)

    @classmethod
    def _from_evaluator(
        cls,
        values: dict[str, object],
    ) -> _SourcePairedTorsionRescueClearanceSelectionShadowDecisionV1:
        expected_fields = {
            "policy_sha256",
            "probe_inputs_sha256",
            "allocation_sha256",
            "proposal_index",
            "parent_proposal_index",
            *_DECISION_GUARD_NAMES,
            "blocker_ids",
            "shadow_selection_eligible",
            "baseline_coordinates_sha256",
            "optimized_coordinates_sha256",
        }
        if type(values) is not dict or set(values) != expected_fields:
            raise TorsionContactRefinementError(
                "shadow-decision evaluator fields are inconsistent"
            )
        instance = object.__new__(cls)
        for name in sorted(expected_fields):
            object.__setattr__(instance, name, values[name])
        object.__setattr__(
            instance,
            "schema_id",
            SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_DECISION_SCHEMA_ID,
        )
        instance.__post_init__()
        return instance

    def __post_init__(self) -> None:
        if type(self.schema_id) is not str or self.schema_id != (
            SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_DECISION_SCHEMA_ID
        ):
            raise TorsionContactRefinementError(
                "unsupported source-paired clearance-selection decision schema"
            )
        for name in (
            "policy_sha256",
            "probe_inputs_sha256",
            "allocation_sha256",
            "baseline_coordinates_sha256",
            "optimized_coordinates_sha256",
        ):
            _digest(getattr(self, name), name=name)
        if self.policy_sha256 != _FROZEN_POLICY_SHA256:
            raise TorsionContactRefinementError("decision policy identity drifted")
        if (
            type(self.proposal_index) is not int
            or not 0 <= self.proposal_index < _FROZEN_CANDIDATE_COUNT
        ):
            raise TorsionContactRefinementError("decision proposal index is invalid")
        if self.parent_proposal_index is not None and (
            type(self.parent_proposal_index) is not int
            or not 0 <= self.parent_proposal_index < _FROZEN_CANDIDATE_COUNT
            or self.parent_proposal_index == self.proposal_index
        ):
            raise TorsionContactRefinementError("decision parent index is invalid")
        if any(type(getattr(self, name)) is not bool for name in _DECISION_GUARD_NAMES):
            raise TorsionContactRefinementError("decision guards must be boolean")
        if type(self.shadow_selection_eligible) is not bool:
            raise TorsionContactRefinementError(
                "shadow-selection eligibility must be boolean"
            )
        if (
            type(self.blocker_ids) is not tuple
            or any(type(value) is not str or not value for value in self.blocker_ids)
            or len(set(self.blocker_ids)) != len(self.blocker_ids)
        ):
            raise TorsionContactRefinementError("decision blocker IDs are invalid")
        if self.target_scope_guard_passed is not (
            self.parent_proposal_index is not None
        ):
            raise TorsionContactRefinementError(
                "decision target and parent fields are inconsistent"
            )
        if self.changed_coordinates_guard_passed is not (
            self.optimized_coordinates_sha256 != self.baseline_coordinates_sha256
        ):
            raise TorsionContactRefinementError(
                "decision coordinate-change guard is inconsistent"
            )
        if not self.clearance_measurement_guard_passed and (
            self.minimum_vdw_surface_gap_guard_passed
            or self.raw_minimum_distance_guard_passed
        ):
            raise TorsionContactRefinementError(
                "unavailable clearance cannot pass geometric guards"
            )
        expected_blockers = tuple(
            blocker
            for name, blocker in zip(
                _DECISION_GUARD_NAMES,
                _DECISION_BLOCKER_IDS,
                strict=True,
            )
            if not getattr(self, name)
        )
        if self.blocker_ids != expected_blockers:
            raise TorsionContactRefinementError("decision blocker IDs are inconsistent")
        expected = bool(all(getattr(self, name) for name in _DECISION_GUARD_NAMES))
        if self.shadow_selection_eligible is not expected:
            raise TorsionContactRefinementError(
                "shadow-selection eligibility is inconsistent"
            )
        object.__setattr__(self, "_decision_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "policy_sha256": self.policy_sha256,
            "probe_inputs_sha256": self.probe_inputs_sha256,
            "allocation_sha256": self.allocation_sha256,
            "proposal_index": self.proposal_index,
            "parent_proposal_index": self.parent_proposal_index,
            "target_scope_guard_passed": self.target_scope_guard_passed,
            "clearance_measurement_guard_passed": (
                self.clearance_measurement_guard_passed
            ),
            "torsion_variant_guard_passed": self.torsion_variant_guard_passed,
            "legacy_v7_unselected_guard_passed": (
                self.legacy_v7_unselected_guard_passed
            ),
            "changed_coordinates_guard_passed": (self.changed_coordinates_guard_passed),
            "receptor_objective_guard_passed": (self.receptor_objective_guard_passed),
            "internal_objective_guard_passed": (self.internal_objective_guard_passed),
            "combined_objective_guard_passed": (self.combined_objective_guard_passed),
            "minimum_vdw_surface_gap_guard_passed": (
                self.minimum_vdw_surface_gap_guard_passed
            ),
            "raw_minimum_distance_guard_passed": (
                self.raw_minimum_distance_guard_passed
            ),
            "blocker_ids": list(self.blocker_ids),
            "shadow_selection_eligible": self.shadow_selection_eligible,
            "selection_applied": False,
            "baseline_coordinates_sha256": self.baseline_coordinates_sha256,
            "optimized_coordinates_sha256": self.optimized_coordinates_sha256,
            "returned_coordinates_authority": "unchanged_active_v7",
            "input_authority": "caller_supplied_contract_probe_only",
            "activation_evidence_admissible": False,
            "historical_outcomes_used_to_fit_policy": False,
            "score_rank_rmsd_posebusters_native_or_case_identity_used": False,
            "source_lane_retained": True,
            "development_only": True,
            "stage0_eligible": False,
            "fresh_execution_authorized": False,
            "product_promotion_eligible": False,
            "public_claim_eligible": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }

    @property
    def decision_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._decision_sha256:
            raise TorsionContactRefinementError(
                "source-paired clearance-selection decision changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "decision_sha256": self.decision_sha256}


def evaluate_source_paired_torsion_rescue_clearance_selection_v1(
    probe_inputs: SourcePairedTorsionRescueClearanceSelectionProbeInputsV1,
    *,
    policy: SourcePairedTorsionRescueClearanceSelectionPolicyV1 | None = None,
) -> _SourcePairedTorsionRescueClearanceSelectionShadowDecisionV1:
    """Evaluate the frozen rule without changing any live selection or coordinate."""

    if not isinstance(
        probe_inputs,
        SourcePairedTorsionRescueClearanceSelectionProbeInputsV1,
    ):
        raise TypeError(
            "probe_inputs must be "
            "SourcePairedTorsionRescueClearanceSelectionProbeInputsV1"
        )
    selected_policy = policy or SourcePairedTorsionRescueClearanceSelectionPolicyV1()
    if not isinstance(
        selected_policy,
        SourcePairedTorsionRescueClearanceSelectionPolicyV1,
    ):
        raise TypeError(
            "policy must be SourcePairedTorsionRescueClearanceSelectionPolicyV1"
        )

    parent_by_target = dict(probe_inputs.allocation.rescue_target_parent_pairs)
    parent_index = parent_by_target.get(probe_inputs.proposal_index)
    target_scope = parent_index is not None
    measurement = probe_inputs.clearance_measurement_evaluated
    variant = probe_inputs.torsion_variant_available
    legacy_unselected = not probe_inputs.legacy_v7_selected
    changed = (
        probe_inputs.optimized_coordinates_sha256
        != probe_inputs.baseline_coordinates_sha256
    )
    receptor = bool(
        probe_inputs.optimized_receptor_objective
        <= probe_inputs.baseline_receptor_objective
        + selected_policy.receptor_objective_tolerance
    )
    internal = bool(
        probe_inputs.optimized_internal_objective
        <= probe_inputs.baseline_internal_objective
        + selected_policy.internal_objective_tolerance
    )
    combined = bool(
        probe_inputs.optimized_combined_objective
        < probe_inputs.baseline_combined_objective
        - selected_policy.combined_objective_tolerance
    )
    if measurement:
        baseline_gap = probe_inputs.baseline_minimum_vdw_surface_gap_angstrom
        optimized_gap = probe_inputs.optimized_minimum_vdw_surface_gap_angstrom
        baseline_distance = probe_inputs.baseline_raw_minimum_distance_angstrom
        optimized_distance = probe_inputs.optimized_raw_minimum_distance_angstrom
        assert baseline_gap is not None
        assert optimized_gap is not None
        assert baseline_distance is not None
        assert optimized_distance is not None
        gap = optimized_gap > baseline_gap
        raw_distance = optimized_distance >= baseline_distance
    else:
        gap = False
        raw_distance = False

    guards = (
        target_scope,
        measurement,
        variant,
        legacy_unselected,
        changed,
        receptor,
        internal,
        combined,
        gap,
        raw_distance,
    )
    blocker_ids: list[str] = []
    for passed, label in zip(guards, _DECISION_BLOCKER_IDS, strict=True):
        if not passed:
            blocker_ids.append(label)

    return _SourcePairedTorsionRescueClearanceSelectionShadowDecisionV1._from_evaluator(
        {
            "policy_sha256": selected_policy.fingerprint_sha256,
            "probe_inputs_sha256": probe_inputs.fingerprint_sha256,
            "allocation_sha256": probe_inputs.allocation.allocation_sha256,
            "proposal_index": probe_inputs.proposal_index,
            "parent_proposal_index": parent_index,
            "target_scope_guard_passed": target_scope,
            "clearance_measurement_guard_passed": measurement,
            "torsion_variant_guard_passed": variant,
            "legacy_v7_unselected_guard_passed": legacy_unselected,
            "changed_coordinates_guard_passed": changed,
            "receptor_objective_guard_passed": receptor,
            "internal_objective_guard_passed": internal,
            "combined_objective_guard_passed": combined,
            "minimum_vdw_surface_gap_guard_passed": gap,
            "raw_minimum_distance_guard_passed": raw_distance,
            "blocker_ids": tuple(blocker_ids),
            "shadow_selection_eligible": all(guards),
            "baseline_coordinates_sha256": probe_inputs.baseline_coordinates_sha256,
            "optimized_coordinates_sha256": probe_inputs.optimized_coordinates_sha256,
        }
    )


__all__ = [
    "SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_DECISION_SCHEMA_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_ID",
    "SOURCE_PAIRED_TORSION_RESCUE_CLEARANCE_SELECTION_POLICY_SCHEMA_ID",
    "SourcePairedTorsionRescueClearanceSelectionProbeInputsV1",
    "SourcePairedTorsionRescueClearanceSelectionPolicyV1",
    "evaluate_source_paired_torsion_rescue_clearance_selection_v1",
]
