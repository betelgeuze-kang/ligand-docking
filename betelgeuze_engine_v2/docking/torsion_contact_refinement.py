"""Receipt-bound torsion contact rescue layered after rigid V6 refinement.

The refiner deliberately reuses the authority-proven torsion tree.  It does
not perceive new chemistry, alter ring bonds, consult PoseBusters/RMSD, or
replace the retained source lane.  A torsion move is accepted only when a
bounded receptor-plus-internal quartic-overlap objective strictly decreases
without increasing its receptor component.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256

from .authority import AuthenticatedDockingProblem
from .contact_validity import VdwContactPolicy
from .identity import coordinate_fingerprint
from .interaction_refinement import (
    ClashReliefRefinementError,
    InteractionAwareRigidClearanceConfigV4,
    InteractionAwareRigidConfigV2,
    InteractionAwareRigidConfigV3,
    InteractionAwareRigidHybridClearanceEnsembleRefinerV6,
)
from .proposals import DockingProposal


INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_contact_config/7.0.0"
)
INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_contact_refiner"
)
INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION = "7.0.0"
INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_contact_receipt/7.0.0"
)
INTERACTION_AWARE_TORSION_CLEARANCE_CONFIG_V8_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_clearance_config/8.0.0"
)
INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_clearance_refiner"
)
INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_VERSION = "8.0.0"
INTERACTION_AWARE_TORSION_CLEARANCE_RECEIPT_V8_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_torsion_clearance_receipt/8.0.0"
)


class TorsionContactRefinementError(ClashReliefRefinementError):
    """The bounded torsion-contact evidence contract failed closed."""


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
            "torsion-contact state is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class InteractionAwareTorsionContactConfigV7:
    """Deterministic bounded coordinate descent over proven rotor subtrees."""

    receptor_overlap_scale: float = 1.0
    internal_overlap_scale: float = 0.80
    internal_overlap_weight: float = 1.0
    maximum_baseline_v6_steps: int = 20
    maximum_torsions_evaluated: int = 4
    maximum_torsion_steps: int = 4
    maximum_backtracking_evaluations: int = 3
    maximum_torsion_step_radians: float = math.pi / 8.0
    minimum_torsion_step_radians: float = math.pi / 32.0
    maximum_total_torsion_path_radians: float = math.pi / 2.0
    maximum_centroid_offset_angstrom: float = 4.0
    minimum_selected_final_receptor_penalty: float = 2.0
    maximum_selected_final_receptor_penalty: float = 4.0
    penalty_tolerance: float = 1.0e-18
    epsilon_angstrom: float = 1.0e-9
    schema_id: str = INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID:
            raise TorsionContactRefinementError(
                "unsupported torsion-contact configuration schema"
            )
        finite_positive = (
            self.receptor_overlap_scale,
            self.internal_overlap_scale,
            self.internal_overlap_weight,
            self.maximum_torsion_step_radians,
            self.minimum_torsion_step_radians,
            self.maximum_total_torsion_path_radians,
            self.maximum_centroid_offset_angstrom,
            self.penalty_tolerance,
            self.epsilon_angstrom,
        )
        if any(
            not math.isfinite(float(value)) or float(value) <= 0.0
            for value in finite_positive
        ):
            raise TorsionContactRefinementError(
                "torsion-contact floating values must be finite and positive"
            )
        if not 0.55 <= self.receptor_overlap_scale <= 1.0:
            raise TorsionContactRefinementError(
                "receptor_overlap_scale must be in [0.55,1.0]"
            )
        if not 0.55 <= self.internal_overlap_scale <= 1.0:
            raise TorsionContactRefinementError(
                "internal_overlap_scale must be in [0.55,1.0]"
            )
        if not (
            self.minimum_torsion_step_radians
            <= self.maximum_torsion_step_radians
            <= self.maximum_total_torsion_path_radians
            <= math.pi
        ):
            raise TorsionContactRefinementError(
                "torsion-contact angular bounds are inconsistent"
            )
        integer_bounds = (
            (self.maximum_baseline_v6_steps, 1, 64, "maximum_baseline_v6_steps"),
            (self.maximum_torsions_evaluated, 1, 32, "maximum_torsions_evaluated"),
            (self.maximum_torsion_steps, 1, 8, "maximum_torsion_steps"),
            (
                self.maximum_backtracking_evaluations,
                1,
                8,
                "maximum_backtracking_evaluations",
            ),
        )
        for value, minimum, maximum, name in integer_bounds:
            if type(value) is not int or not minimum <= value <= maximum:
                raise TorsionContactRefinementError(
                    f"{name} must be an integer in [{minimum},{maximum}]"
                )
        if not 0.5 <= self.maximum_centroid_offset_angstrom <= 8.0:
            raise TorsionContactRefinementError(
                "maximum centroid offset must be in [0.5,8.0] angstrom"
            )
        selection_window = (
            self.minimum_selected_final_receptor_penalty,
            self.maximum_selected_final_receptor_penalty,
        )
        if any(not math.isfinite(float(value)) for value in selection_window):
            raise TorsionContactRefinementError(
                "torsion-contact selection window bounds must be finite"
            )
        if not (
            0.0 <= self.minimum_selected_final_receptor_penalty
            < self.maximum_selected_final_receptor_penalty
        ):
            raise TorsionContactRefinementError(
                "torsion-contact selection window must satisfy 0 <= minimum < maximum"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self.to_dict()))

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self.to_dict())
        if observed != self._fingerprint_sha256:
            raise TorsionContactRefinementError(
                "torsion-contact configuration changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "receptor_overlap_scale_binary64_hex": (
                self.receptor_overlap_scale.hex()
            ),
            "internal_overlap_scale_binary64_hex": (
                self.internal_overlap_scale.hex()
            ),
            "internal_overlap_weight_binary64_hex": (
                self.internal_overlap_weight.hex()
            ),
            "maximum_baseline_v6_steps": self.maximum_baseline_v6_steps,
            "maximum_torsions_evaluated": self.maximum_torsions_evaluated,
            "maximum_torsion_steps": self.maximum_torsion_steps,
            "maximum_backtracking_evaluations": (
                self.maximum_backtracking_evaluations
            ),
            "maximum_torsion_step_radians_binary64_hex": (
                self.maximum_torsion_step_radians.hex()
            ),
            "minimum_torsion_step_radians_binary64_hex": (
                self.minimum_torsion_step_radians.hex()
            ),
            "maximum_total_torsion_path_radians_binary64_hex": (
                self.maximum_total_torsion_path_radians.hex()
            ),
            "maximum_centroid_offset_angstrom_binary64_hex": (
                self.maximum_centroid_offset_angstrom.hex()
            ),
            "minimum_selected_final_receptor_penalty_binary64_hex": (
                self.minimum_selected_final_receptor_penalty.hex()
            ),
            "maximum_selected_final_receptor_penalty_binary64_hex": (
                self.maximum_selected_final_receptor_penalty.hex()
            ),
            "penalty_tolerance_binary64_hex": self.penalty_tolerance.hex(),
            "epsilon_angstrom_binary64_hex": self.epsilon_angstrom.hex(),
            "optimization_variables": "authority_proven_rotatable_child_subtrees",
            "objective": "quartic_receptor_plus_internal_vdw_overlap",
            "selection_policy": (
                "strict_combined_decrease_and_receptor_component_nonincrease_"
                "then_final_receptor_penalty_half_open_window"
            ),
            "selection_window_role": "historical_development_guardrail",
            "selection_window_development_tuned": True,
            "selection_window_monotonicity_pruning": True,
            "posebusters_or_rmsd_used_for_selection": False,
            "source_lane_retention_required": True,
            "scientifically_validated": False,
        }


@dataclass(frozen=True, slots=True)
class InteractionAwareTorsionClearanceConfigV8:
    """Development-only guard for V7 states outside its historical window."""

    clearance_tolerance_angstrom: float = 1.0e-9
    schema_id: str = INTERACTION_AWARE_TORSION_CLEARANCE_CONFIG_V8_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != INTERACTION_AWARE_TORSION_CLEARANCE_CONFIG_V8_SCHEMA_ID:
            raise TorsionContactRefinementError(
                "unsupported torsion-clearance configuration schema"
            )
        tolerance = float(self.clearance_tolerance_angstrom)
        if not math.isfinite(tolerance) or not 0.0 < tolerance <= 1.0e-6:
            raise TorsionContactRefinementError(
                "torsion-clearance tolerance must be in (0,1e-6] angstrom"
            )
        object.__setattr__(self, "clearance_tolerance_angstrom", tolerance)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self.to_dict()))

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self.to_dict())
        if observed != self._fingerprint_sha256:
            raise TorsionContactRefinementError(
                "torsion-clearance configuration changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "clearance_tolerance_angstrom_binary64_hex": (
                self.clearance_tolerance_angstrom.hex()
            ),
            "selection_policy": (
                "retain_v7_unless_outside_window_optimized_state_strictly_"
                "improves_minimum_vdw_surface_gap_with_raw_distance_and_"
                "receptor_internal_objective_nonregression"
            ),
            "candidate_scope": "existing_uniform_v3_source_paired_slots_only",
            "candidate_budget_changed": False,
            "posebusters_or_rmsd_used_for_selection": False,
            "ranking_score_used_for_selection": False,
            "source_lane_retention_required": True,
            "stage0_eligible": False,
            "scientifically_validated": False,
            "claim_safe": False,
        }


@dataclass(frozen=True, slots=True)
class _TorsionOptimizedState:
    coordinates: torch.Tensor
    torsion_angles: torch.Tensor


@dataclass(frozen=True, slots=True)
class _ReceptorClearanceStatistics:
    minimum_distance_angstrom: float
    minimum_distance_ligand_atom_index: int
    minimum_distance_receptor_atom_index: int
    minimum_vdw_surface_gap_angstrom: float
    minimum_vdw_surface_gap_ligand_atom_index: int
    minimum_vdw_surface_gap_receptor_atom_index: int
    minimum_vdw_ratio: float
    minimum_vdw_ratio_ligand_atom_index: int
    minimum_vdw_ratio_receptor_atom_index: int

    def to_dict(self) -> dict[str, object]:
        return {
            "minimum_distance_angstrom_binary64_hex": (
                self.minimum_distance_angstrom.hex()
            ),
            "minimum_distance_ligand_atom_index": (
                self.minimum_distance_ligand_atom_index
            ),
            "minimum_distance_receptor_atom_index": (
                self.minimum_distance_receptor_atom_index
            ),
            "minimum_vdw_surface_gap_angstrom_binary64_hex": (
                self.minimum_vdw_surface_gap_angstrom.hex()
            ),
            "minimum_vdw_surface_gap_ligand_atom_index": (
                self.minimum_vdw_surface_gap_ligand_atom_index
            ),
            "minimum_vdw_surface_gap_receptor_atom_index": (
                self.minimum_vdw_surface_gap_receptor_atom_index
            ),
            "minimum_vdw_ratio_binary64_hex": self.minimum_vdw_ratio.hex(),
            "minimum_vdw_ratio_ligand_atom_index": (
                self.minimum_vdw_ratio_ligand_atom_index
            ),
            "minimum_vdw_ratio_receptor_atom_index": (
                self.minimum_vdw_ratio_receptor_atom_index
            ),
        }


def _receptor_clearance_statistics(
    coordinates: torch.Tensor,
    *,
    receptor_coordinates: torch.Tensor,
    ligand_radii: torch.Tensor,
    receptor_radii: torch.Tensor,
    receptor_atom_indices: tuple[int, ...],
) -> _ReceptorClearanceStatistics:
    ligand = coordinates.to(dtype=torch.float64, device="cpu").contiguous()
    receptor = receptor_coordinates.to(dtype=torch.float64, device="cpu").contiguous()
    ligand_radius = ligand_radii.to(dtype=torch.float64, device="cpu").contiguous()
    receptor_radius = receptor_radii.to(
        dtype=torch.float64,
        device="cpu",
    ).contiguous()
    if (
        ligand.ndim != 2
        or ligand.shape[1:] != (3,)
        or receptor.ndim != 2
        or receptor.shape[1:] != (3,)
        or not len(ligand)
        or not len(receptor)
        or ligand_radius.shape != (len(ligand),)
        or receptor_radius.shape != (len(receptor),)
        or len(receptor_atom_indices) != len(receptor)
        or receptor_atom_indices != tuple(sorted(set(receptor_atom_indices)))
        or not bool(torch.isfinite(ligand).all().item())
        or not bool(torch.isfinite(receptor).all().item())
        or not bool(torch.isfinite(ligand_radius).all().item())
        or not bool(torch.isfinite(receptor_radius).all().item())
        or bool((ligand_radius <= 0.0).any().item())
        or bool((receptor_radius <= 0.0).any().item())
    ):
        raise TorsionContactRefinementError(
            "torsion-clearance receptor geometry is invalid"
        )
    minimum_distance: tuple[float, int, int] | None = None
    minimum_gap: tuple[float, int, int] | None = None
    minimum_ratio: tuple[float, int, int] | None = None
    for start in range(0, len(receptor), 4096):
        stop = min(start + 4096, len(receptor))
        delta = ligand[:, None, :] - receptor[None, start:stop, :]
        distance = torch.linalg.vector_norm(delta, dim=-1)
        radii_sum = ligand_radius[:, None] + receptor_radius[None, start:stop]
        metrics = (distance, distance - radii_sum, distance / radii_sum)
        observed: list[tuple[float, int, int]] = []
        width = stop - start
        for metric in metrics:
            flat_index = int(torch.argmin(metric).item())
            ligand_index = flat_index // width
            receptor_local_index = start + flat_index % width
            value = float(metric.reshape(-1)[flat_index].item())
            if not math.isfinite(value):
                raise TorsionContactRefinementError(
                    "torsion-clearance metric is non-finite"
                )
            observed.append(
                (
                    value,
                    ligand_index,
                    receptor_atom_indices[receptor_local_index],
                )
            )
        if minimum_distance is None or observed[0] < minimum_distance:
            minimum_distance = observed[0]
        if minimum_gap is None or observed[1] < minimum_gap:
            minimum_gap = observed[1]
        if minimum_ratio is None or observed[2] < minimum_ratio:
            minimum_ratio = observed[2]
    if minimum_distance is None or minimum_gap is None or minimum_ratio is None:
        raise TorsionContactRefinementError(
            "torsion-clearance metric denominator is empty"
        )
    return _ReceptorClearanceStatistics(
        minimum_distance_angstrom=minimum_distance[0],
        minimum_distance_ligand_atom_index=minimum_distance[1],
        minimum_distance_receptor_atom_index=minimum_distance[2],
        minimum_vdw_surface_gap_angstrom=minimum_gap[0],
        minimum_vdw_surface_gap_ligand_atom_index=minimum_gap[1],
        minimum_vdw_surface_gap_receptor_atom_index=minimum_gap[2],
        minimum_vdw_ratio=minimum_ratio[0],
        minimum_vdw_ratio_ligand_atom_index=minimum_ratio[1],
        minimum_vdw_ratio_receptor_atom_index=minimum_ratio[2],
    )


class InteractionAwareTorsionContactEnsembleRefinerV7:
    """Layer bounded torsion contact rescue over the receipt-complete V6 lane."""

    refiner_id = INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID
    refiner_version = INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        v3_proposal_indices: tuple[int, ...],
        torsion_config: InteractionAwareTorsionContactConfigV7 | None = None,
        v2_config: InteractionAwareRigidConfigV2 | None = None,
        v3_config: InteractionAwareRigidConfigV3 | None = None,
        clearance_config: InteractionAwareRigidClearanceConfigV4 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem):
            raise TypeError("authority must be AuthenticatedDockingProblem")
        if canonical_system_sha256(receptor_system) != authority.receptor_system_sha256:
            raise TorsionContactRefinementError("receptor system is cross-wired")
        if canonical_system_sha256(ligand_system) != authority.ligand_system_sha256:
            raise TorsionContactRefinementError("ligand system is cross-wired")
        if (
            len(implementation_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in implementation_source_sha256
            )
        ):
            raise TorsionContactRefinementError(
                "implementation source hash is invalid"
            )
        selected_config = torsion_config or InteractionAwareTorsionContactConfigV7()
        selected_policy = radii_policy or VdwContactPolicy()
        self._v6 = InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=(
                clearance_config or InteractionAwareRigidClearanceConfigV4()
            ),
            radii_policy=selected_policy,
        )
        self._authority = authority
        self._config = selected_config
        self._implementation_source_sha256 = implementation_source_sha256
        self._v3_proposal_indices = tuple(v3_proposal_indices)
        self._v3_proposal_index_set = frozenset(v3_proposal_indices)
        self._search_space = authority.search_space
        self._search_space.assert_integrity()
        receptor_indices = list(authority.receptor_atom_indices)
        self._receptor_coordinates = receptor_system.coordinates[
            authority.receptor_model_index,
            receptor_indices,
        ].to(dtype=torch.float64, device="cpu").contiguous()
        self._receptor_radii = torch.tensor(
            [
                selected_policy.radius(receptor_system.atoms[index].element)
                for index in receptor_indices
            ],
            dtype=torch.float64,
        )
        self._ligand_radii = torch.tensor(
            [selected_policy.radius(atom.element) for atom in ligand_system.atoms],
            dtype=torch.float64,
        )
        exclusions = set(authority.validity_context.excluded_nonbonded_pairs)
        internal_pairs = tuple(
            (first, second)
            for first in range(ligand_system.atom_count)
            for second in range(first + 1, ligand_system.atom_count)
            if (first, second) not in exclusions
        )
        self._internal_first = torch.tensor(
            [row[0] for row in internal_pairs], dtype=torch.long
        )
        self._internal_second = torch.tensor(
            [row[1] for row in internal_pairs], dtype=torch.long
        )
        children: list[list[int]] = [
            [] for _ in range(self._search_space.atom_count)
        ]
        for child, raw_parent in enumerate(self._search_space.parent.tolist()):
            parent = int(raw_parent)
            if parent >= 0:
                children[parent].append(child)
        descendants: dict[int, tuple[int, ...]] = {}
        rotor_indices = tuple(
            int(value)
            for value in torch.nonzero(
                self._search_space.rotatable_mask,
                as_tuple=False,
            ).reshape(-1).tolist()
        )
        for rotor in rotor_indices:
            pending = [rotor]
            observed: list[int] = []
            while pending:
                node = pending.pop()
                observed.append(node)
                pending.extend(reversed(children[node]))
            descendants[rotor] = tuple(sorted(observed))
        descendant_index_tensors = {
            rotor: torch.tensor(descendants[rotor], dtype=torch.long)
            for rotor in rotor_indices
        }
        descendant_sets = {
            rotor: frozenset(descendants[rotor]) for rotor in rotor_indices
        }
        cross_internal_pair_indices = {
            rotor: tuple(
                pair_index
                for pair_index, (first, second) in enumerate(internal_pairs)
                if (first in descendant_sets[rotor])
                != (second in descendant_sets[rotor])
            )
            for rotor in rotor_indices
        }
        self._rotor_indices = rotor_indices
        self._descendants = MappingProxyType(descendants)
        self._descendant_index_tensors = MappingProxyType(
            descendant_index_tensors
        )
        self._cross_internal_pair_indices = MappingProxyType(
            cross_internal_pair_indices
        )
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "schema_id": INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID,
                "baseline_v6_config_sha256": self._v6.config_fingerprint_sha256,
                "torsion_config_sha256": selected_config.fingerprint_sha256,
                "radii_policy_sha256": selected_policy.fingerprint_sha256,
                "authority_input_receipt_sha256": authority.input_receipt_sha256,
                "search_space_fingerprint_sha256": (
                    self._search_space.fingerprint_sha256
                ),
                "rotatable_child_atom_indices": list(rotor_indices),
                "rotor_descendant_atom_indices": {
                    str(index): list(descendants[index]) for index in rotor_indices
                },
                "rotor_cross_internal_pair_indices": {
                    str(index): list(cross_internal_pair_indices[index])
                    for index in rotor_indices
                },
                "excluded_internal_pair_count": len(exclusions),
                "evaluated_internal_pair_count": len(internal_pairs),
                "source_lane_retained": True,
                "scientifically_validated": False,
            }
        )
        self._receipts: dict[str, Mapping[str, object]] = {}
        self._baseline_states: dict[str, _TorsionOptimizedState] = {}
        self._optimized_states: dict[str, _TorsionOptimizedState] = {}

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self._authority.problem.fingerprint_sha256

    @property
    def config_fingerprint_sha256(self) -> str:
        return self._component_config_fingerprint_sha256

    @property
    def implementation_source_sha256(self) -> str:
        if self._v6.implementation_source_sha256 != self._implementation_source_sha256:
            raise TorsionContactRefinementError(
                "nested V6 implementation identity changed"
            )
        return self._implementation_source_sha256

    @property
    def receipts(self) -> Mapping[str, Mapping[str, object]]:
        return MappingProxyType(
            {
                key: MappingProxyType(deepcopy(dict(receipt)))
                for key, receipt in self._receipts.items()
            }
        )

    def _optimized_state_for_experimental_v8(
        self,
        source_proposal_sha256: str,
    ) -> _TorsionOptimizedState:
        if source_proposal_sha256 not in self._receipts:
            raise TorsionContactRefinementError(
                "V7 receipt must exist before experimental V8 selection"
            )
        try:
            state = self._optimized_states[source_proposal_sha256]
        except KeyError as exc:
            raise TorsionContactRefinementError(
                "V7 optimized state is unavailable"
            ) from exc
        return _TorsionOptimizedState(
            coordinates=state.coordinates.clone(),
            torsion_angles=state.torsion_angles.clone(),
        )

    def _baseline_state_for_experimental_v8(
        self,
        source_proposal_sha256: str,
    ) -> _TorsionOptimizedState:
        if source_proposal_sha256 not in self._receipts:
            raise TorsionContactRefinementError(
                "V7 receipt must exist before experimental V8 selection"
            )
        try:
            state = self._baseline_states[source_proposal_sha256]
        except KeyError as exc:
            raise TorsionContactRefinementError(
                "V7 baseline state is unavailable"
            ) from exc
        return _TorsionOptimizedState(
            coordinates=state.coordinates.clone(),
            torsion_angles=state.torsion_angles.clone(),
        )

    def _receptor_penalty_by_atom(self, coordinates: torch.Tensor) -> torch.Tensor:
        per_atom = torch.zeros(len(coordinates), dtype=torch.float64)
        for start in range(0, len(self._receptor_coordinates), 4096):
            stop = min(start + 4096, len(self._receptor_coordinates))
            receptor = self._receptor_coordinates[start:stop]
            receptor_radii = self._receptor_radii[start:stop]
            delta = coordinates[:, None, :] - receptor[None, :, :]
            distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
                self._config.epsilon_angstrom
            )
            cutoff = self._config.receptor_overlap_scale * (
                self._ligand_radii[:, None] + receptor_radii[None, :]
            )
            overlap = (cutoff - distance).clamp_min(0.0)
            per_atom += (overlap * overlap * overlap * overlap).sum(dim=1)
        return per_atom

    def _internal_pair_penalties(self, coordinates: torch.Tensor) -> torch.Tensor:
        if not len(self._internal_first):
            return torch.zeros(0, dtype=torch.float64)
        delta = (
            coordinates[self._internal_first]
            - coordinates[self._internal_second]
        )
        distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
            self._config.epsilon_angstrom
        )
        cutoff = self._config.internal_overlap_scale * (
            self._ligand_radii[self._internal_first]
            + self._ligand_radii[self._internal_second]
        )
        overlap = (cutoff - distance).clamp_min(0.0)
        return overlap * overlap * overlap * overlap

    def _objective(
        self,
        coordinates: torch.Tensor,
    ) -> tuple[float, float, float, torch.Tensor, torch.Tensor]:
        receptor_by_atom = self._receptor_penalty_by_atom(coordinates)
        internal_by_pair = self._internal_pair_penalties(coordinates)
        receptor = float(receptor_by_atom.sum().item())
        internal = float(internal_by_pair.sum().item())
        combined = receptor + self._config.internal_overlap_weight * internal
        return receptor, internal, combined, receptor_by_atom, internal_by_pair

    def _rotor_priority(
        self,
        rotor: int,
        receptor_by_atom: torch.Tensor,
        internal_by_pair: torch.Tensor,
    ) -> float:
        receptor = float(
            receptor_by_atom[self._descendant_index_tensors[rotor]].sum().item()
        )
        pair_indices = self._cross_internal_pair_indices[rotor]
        internal = (
            0.0
            if not pair_indices
            else float(internal_by_pair[list(pair_indices)].sum().item())
        )
        return receptor + self._config.internal_overlap_weight * internal

    def _rotated_subtree(
        self,
        coordinates: torch.Tensor,
        *,
        rotor: int,
        delta_radians: float,
    ) -> torch.Tensor:
        parent = int(self._search_space.parent[rotor].item())
        if parent < 0:
            raise TorsionContactRefinementError(
                "authority marked a root atom as rotatable"
            )
        origin = coordinates[parent]
        axis = coordinates[rotor] - origin
        norm = float(torch.linalg.vector_norm(axis).item())
        if not math.isfinite(norm) or norm <= self._config.epsilon_angstrom:
            raise TorsionContactRefinementError(
                "torsion-contact central bond is degenerate"
            )
        axis = axis / norm
        indices = self._descendant_index_tensors[rotor]
        vectors = coordinates[indices] - origin
        cosine = math.cos(delta_radians)
        sine = math.sin(delta_radians)
        cross = torch.cross(axis.expand_as(vectors), vectors, dim=1)
        projection = (vectors * axis).sum(dim=1, keepdim=True) * axis
        rotated = (
            vectors * cosine
            + cross * sine
            + projection * (1.0 - cosine)
        )
        result = coordinates.clone()
        result[indices] = origin + rotated
        return result

    @staticmethod
    def _normalized_angle(value: float) -> float:
        return math.atan2(math.sin(value), math.cos(value))

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.fingerprint_sha256 in self._receipts:
            raise TorsionContactRefinementError("proposal was already refined")
        if type(max_steps) is not int or not 0 <= max_steps <= 10_000:
            raise TorsionContactRefinementError(
                "max_steps must be an integer in [0,10000]"
            )
        self._search_space.assert_integrity()
        if proposal.search_space_fingerprint_sha256 != (
            self._search_space.fingerprint_sha256
        ):
            raise TorsionContactRefinementError(
                "proposal is cross-wired to a different torsion search space"
            )

        baseline_v6_max_steps = min(
            max_steps,
            self._config.maximum_baseline_v6_steps,
        )
        baseline = self._v6.refine(
            proposal,
            max_steps=baseline_v6_max_steps,
        )
        baseline_receipt = dict(
            self._v6.receipts[proposal.fingerprint_sha256]
        )
        self._baseline_states[proposal.fingerprint_sha256] = (
            _TorsionOptimizedState(
                coordinates=baseline.coordinates.clone(),
                torsion_angles=baseline.torsion_angles.clone(),
            )
        )
        source_coordinates = proposal.coordinates.to(
            dtype=torch.float64,
            device="cpu",
        )
        (
            source_receptor,
            source_internal,
            source_combined,
            _source_receptor_by_atom,
            _source_internal_by_pair,
        ) = self._objective(source_coordinates)
        coordinates = baseline.coordinates.to(dtype=torch.float64, device="cpu")
        torsion_angles = baseline.torsion_angles.clone().to(
            dtype=torch.float64,
            device="cpu",
        )
        (
            baseline_receptor,
            baseline_internal,
            baseline_combined,
            receptor_by_atom,
            internal_by_pair,
        ) = self._objective(coordinates)
        current_receptor = baseline_receptor
        current_internal = baseline_internal
        current_combined = baseline_combined
        evaluation_count = 2
        torsion_trial_evaluation_count = 0
        total_torsion_path = 0.0
        accepted_moves: list[dict[str, object]] = []
        baseline_steps = int(baseline_receipt["accepted_steps"])
        remaining_steps = max(0, max_steps - baseline_steps)
        torsion_step_budget = min(
            self._config.maximum_torsion_steps,
            remaining_steps,
        )
        selection_window_reachable = bool(
            baseline_receptor
            + torsion_step_budget * self._config.penalty_tolerance
            >= self._config.minimum_selected_final_receptor_penalty
        )
        if proposal.proposal_index not in self._v3_proposal_index_set:
            torsion_evaluation_skip_reason = "not_v3_variant"
        elif not self._rotor_indices:
            torsion_evaluation_skip_reason = "no_authority_rotor"
        elif torsion_step_budget == 0:
            torsion_evaluation_skip_reason = "no_remaining_torsion_step_budget"
        elif current_combined <= self._config.penalty_tolerance:
            torsion_evaluation_skip_reason = "objective_at_or_below_tolerance"
        elif not selection_window_reachable:
            torsion_evaluation_skip_reason = (
                "selection_window_unreachable_under_receptor_nonincrease"
            )
        else:
            torsion_evaluation_skip_reason = "none"
        torsion_evaluated = bool(
            proposal.proposal_index in self._v3_proposal_index_set
            and self._rotor_indices
            and torsion_step_budget > 0
            and current_combined > self._config.penalty_tolerance
            and selection_window_reachable
        )
        evaluation_stopped_after_selection_window_became_unreachable = False

        for _ in range(
            torsion_step_budget if torsion_evaluated else 0
        ):
            prioritized = sorted(
                (
                    (
                        -self._rotor_priority(
                            rotor,
                            receptor_by_atom,
                            internal_by_pair,
                        ),
                        rotor,
                    )
                    for rotor in self._rotor_indices
                ),
                key=lambda row: (row[0], row[1]),
            )[: self._config.maximum_torsions_evaluated]
            evaluated_rotors = tuple(row[1] for row in prioritized)
            best: tuple[
                float,
                float,
                float,
                int,
                int,
                float,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
            ] | None = None
            step = self._config.maximum_torsion_step_radians
            for _backtracking in range(
                self._config.maximum_backtracking_evaluations
            ):
                if step + self._config.penalty_tolerance < (
                    self._config.minimum_torsion_step_radians
                ):
                    break
                if total_torsion_path + step > (
                    self._config.maximum_total_torsion_path_radians
                    + self._config.penalty_tolerance
                ):
                    step *= 0.5
                    continue
                for rotor in evaluated_rotors:
                    for sign_order, sign in enumerate((-1.0, 1.0)):
                        delta = sign * step
                        candidate = self._rotated_subtree(
                            coordinates,
                            rotor=rotor,
                            delta_radians=delta,
                        )
                        centroid_offset = float(
                            torch.linalg.vector_norm(
                                candidate.mean(dim=0)
                                - self._authority.pocket.center
                            ).item()
                        )
                        if centroid_offset > (
                            self._config.maximum_centroid_offset_angstrom
                            + self._config.penalty_tolerance
                        ):
                            continue
                        (
                            receptor,
                            internal,
                            combined,
                            candidate_receptor_by_atom,
                            candidate_internal_by_pair,
                        ) = self._objective(candidate)
                        evaluation_count += 1
                        torsion_trial_evaluation_count += 1
                        if receptor > (
                            current_receptor + self._config.penalty_tolerance
                        ) or combined >= (
                            current_combined - self._config.penalty_tolerance
                        ):
                            continue
                        candidate_key = (
                            combined,
                            receptor,
                            internal,
                            rotor,
                            sign_order,
                        )
                        if best is None or candidate_key < best[:5]:
                            next_angles = torsion_angles.clone()
                            next_angles[rotor] = self._normalized_angle(
                                float(next_angles[rotor].item()) + delta
                            )
                            best = (
                                combined,
                                receptor,
                                internal,
                                rotor,
                                sign_order,
                                delta,
                                candidate,
                                next_angles,
                                candidate_receptor_by_atom,
                                candidate_internal_by_pair,
                            )
                if best is not None:
                    break
                step *= 0.5
            if best is None:
                break
            (
                current_combined,
                current_receptor,
                current_internal,
                rotor,
                _sign_order,
                delta,
                coordinates,
                torsion_angles,
                receptor_by_atom,
                internal_by_pair,
            ) = best
            total_torsion_path += abs(delta)
            accepted_moves.append(
                {
                    "rotatable_child_atom_index": rotor,
                    "delta_radians_binary64_hex": delta.hex(),
                    "receptor_penalty_binary64_hex": current_receptor.hex(),
                    "internal_penalty_binary64_hex": current_internal.hex(),
                    "combined_penalty_binary64_hex": current_combined.hex(),
                }
            )
            remaining_torsion_steps = torsion_step_budget - len(accepted_moves)
            if (
                current_receptor
                + remaining_torsion_steps * self._config.penalty_tolerance
                < self._config.minimum_selected_final_receptor_penalty
            ):
                evaluation_stopped_after_selection_window_became_unreachable = True
                break

        torsion_variant_available = bool(accepted_moves)
        optimized_coordinates = coordinates
        optimized_torsion_angles = torsion_angles
        optimized_receptor = current_receptor
        optimized_internal = current_internal
        optimized_combined = current_combined
        evaluated_moves = accepted_moves
        evaluated_total_torsion_path = total_torsion_path
        self._optimized_states[proposal.fingerprint_sha256] = (
            _TorsionOptimizedState(
                coordinates=optimized_coordinates.to(
                    dtype=proposal.coordinates.dtype
                ).clone(),
                torsion_angles=optimized_torsion_angles.to(
                    dtype=proposal.torsion_angles.dtype
                ).clone(),
            )
        )
        torsion_selected = bool(
            torsion_variant_available
            and self._config.minimum_selected_final_receptor_penalty
            <= optimized_receptor
            < self._config.maximum_selected_final_receptor_penalty
        )
        if torsion_selected:
            final_coordinates = optimized_coordinates.to(
                dtype=proposal.coordinates.dtype
            )
            final_torsion_angles = optimized_torsion_angles.to(
                dtype=proposal.torsion_angles.dtype
            )
            final_receptor = optimized_receptor
            final_internal = optimized_internal
            final_combined = optimized_combined
            selected_moves = evaluated_moves
            selected_total_torsion_path = evaluated_total_torsion_path
        else:
            final_coordinates = baseline.coordinates
            final_torsion_angles = baseline.torsion_angles
            final_receptor = baseline_receptor
            final_internal = baseline_internal
            final_combined = baseline_combined
            selected_moves = []
            selected_total_torsion_path = 0.0
        if torsion_selected:
            selection_reason = "final_receptor_penalty_window_selected"
        elif torsion_variant_available:
            selection_reason = (
                "v6_retained_outside_final_receptor_penalty_window"
            )
        else:
            selection_reason = (
                "v6_baseline_retained_no_torsion_objective_reduction"
            )
        receipt: dict[str, object] = {
            "schema_id": INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self.config_fingerprint_sha256,
            "lane": (
                "torsion_contact_v7_rescue"
                if torsion_selected
                else "rigid_v6_retained"
            ),
            "selection_reason": selection_reason,
            "baseline_v6_receipt_sha256": baseline_receipt["receipt_sha256"],
            "baseline_v6_receipt_payload": baseline_receipt,
            "baseline_v6_max_steps": baseline_v6_max_steps,
            "v3_proposal_indices": list(self._v3_proposal_indices),
            "rotatable_child_atom_indices": list(self._rotor_indices),
            "torsion_step_budget": torsion_step_budget,
            "selection_window_reachable_from_baseline_v6_receptor_penalty": (
                selection_window_reachable
            ),
            "torsion_evaluation_skip_reason": torsion_evaluation_skip_reason,
            "evaluation_stopped_after_selection_window_became_unreachable": (
                evaluation_stopped_after_selection_window_became_unreachable
            ),
            "torsion_evaluated": torsion_evaluated,
            "torsion_variant_available": torsion_variant_available,
            "torsion_selected": torsion_selected,
            "evaluated_torsion_steps": len(evaluated_moves),
            "evaluated_torsion_moves": evaluated_moves,
            "evaluated_total_torsion_path_radians_binary64_hex": (
                evaluated_total_torsion_path.hex()
            ),
            "accepted_torsion_steps": len(selected_moves),
            "accepted_torsion_moves": selected_moves,
            "objective_evaluation_count": evaluation_count,
            "fixed_objective_evaluation_count": 2,
            "torsion_trial_objective_evaluation_count": (
                torsion_trial_evaluation_count
            ),
            "initial_receptor_penalty_binary64_hex": source_receptor.hex(),
            "baseline_v6_receptor_penalty_binary64_hex": (
                baseline_receptor.hex()
            ),
            "optimized_receptor_penalty_binary64_hex": (
                optimized_receptor.hex()
            ),
            "final_receptor_penalty_binary64_hex": final_receptor.hex(),
            "initial_internal_penalty_binary64_hex": source_internal.hex(),
            "baseline_v6_internal_penalty_binary64_hex": (
                baseline_internal.hex()
            ),
            "optimized_internal_penalty_binary64_hex": optimized_internal.hex(),
            "final_internal_penalty_binary64_hex": final_internal.hex(),
            "initial_combined_penalty_binary64_hex": source_combined.hex(),
            "baseline_v6_combined_penalty_binary64_hex": (
                baseline_combined.hex()
            ),
            "optimized_combined_penalty_binary64_hex": (
                optimized_combined.hex()
            ),
            "final_combined_penalty_binary64_hex": final_combined.hex(),
            "initial_penalty_binary64_hex": source_combined.hex(),
            "final_penalty_binary64_hex": final_combined.hex(),
            "generic_penalty_scope": (
                "source_proposal_to_final_coordinates_v7_objective"
            ),
            "baseline_v6_penalty_scope": (
                "post_v6_coordinates_v7_objective"
            ),
            "minimum_selected_final_receptor_penalty_binary64_hex": (
                self._config.minimum_selected_final_receptor_penalty.hex()
            ),
            "maximum_selected_final_receptor_penalty_binary64_hex": (
                self._config.maximum_selected_final_receptor_penalty.hex()
            ),
            "total_torsion_path_radians_binary64_hex": (
                selected_total_torsion_path.hex()
            ),
            "accepted_steps": baseline_steps + len(selected_moves),
            "accepted_translation_steps": baseline_receipt.get(
                "accepted_translation_steps",
                baseline_steps,
            ),
            "accepted_rigid_rotation_steps": baseline_receipt.get(
                "accepted_rotation_steps", 0
            ),
            "accepted_rotation_steps": (
                int(baseline_receipt.get("accepted_rotation_steps", 0))
                + len(selected_moves)
            ),
            "accepted_rotation_steps_include_torsion": True,
            "line_search_evaluation_count": (
                int(baseline_receipt.get("line_search_evaluation_count", 0))
                + torsion_trial_evaluation_count
            ),
            "fallback_direction_step_count": baseline_receipt.get(
                "fallback_direction_step_count",
                0,
            ),
            "original_pose_valid": baseline_receipt["original_pose_valid"],
            "total_translation_binary64_hex": baseline_receipt[
                "total_translation_binary64_hex"
            ],
            "total_rotation_vector_binary64_hex": baseline_receipt[
                "total_rotation_vector_binary64_hex"
            ],
            "pre_coordinates_sha256": baseline_receipt[
                "pre_coordinates_sha256"
            ],
            "baseline_coordinates_sha256": coordinate_fingerprint(
                baseline.coordinates
            ),
            "post_coordinates_sha256": coordinate_fingerprint(
                final_coordinates
            ),
            "ranking_score_reused_as_physical_energy": False,
            "posebusters_or_rmsd_used_for_selection": False,
            "source_lane_retained": True,
            "scientifically_validated": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            final_coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=final_torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


class InteractionAwareTorsionClearanceEnsembleRefinerV8:
    """Development-only clearance selection over exact V7 optimized states."""

    refiner_id = INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_ID
    refiner_version = INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        v3_proposal_indices: tuple[int, ...],
        clearance_guard_config: InteractionAwareTorsionClearanceConfigV8 | None = None,
        torsion_config: InteractionAwareTorsionContactConfigV7 | None = None,
        v2_config: InteractionAwareRigidConfigV2 | None = None,
        v3_config: InteractionAwareRigidConfigV3 | None = None,
        clearance_config: InteractionAwareRigidClearanceConfigV4 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        selected_guard = (
            clearance_guard_config or InteractionAwareTorsionClearanceConfigV8()
        )
        selected_policy = radii_policy or VdwContactPolicy()
        self._v7 = InteractionAwareTorsionContactEnsembleRefinerV7(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            torsion_config=torsion_config,
            v2_config=v2_config,
            v3_config=v3_config,
            clearance_config=clearance_config,
            radii_policy=selected_policy,
        )
        self._authority = authority
        self._config = selected_guard
        self._implementation_source_sha256 = implementation_source_sha256
        self._v3_proposal_indices = tuple(v3_proposal_indices)
        self._receptor_atom_indices = tuple(authority.receptor_atom_indices)
        self._receptor_coordinates = self._v7._receptor_coordinates.clone()
        self._receptor_radii = self._v7._receptor_radii.clone()
        self._ligand_radii = self._v7._ligand_radii.clone()
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "schema_id": INTERACTION_AWARE_TORSION_CLEARANCE_CONFIG_V8_SCHEMA_ID,
                "legacy_v7_config_sha256": self._v7.config_fingerprint_sha256,
                "clearance_guard_config_sha256": selected_guard.fingerprint_sha256,
                "radii_policy_sha256": selected_policy.fingerprint_sha256,
                "authority_input_receipt_sha256": authority.input_receipt_sha256,
                "v3_proposal_indices": list(v3_proposal_indices),
                "source_lane_retained": True,
                "stage0_eligible": False,
                "scientifically_validated": False,
            }
        )
        self._receipts: dict[str, Mapping[str, object]] = {}
        self._legacy_results: dict[str, tuple[int, DockingProposal]] = {}

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self._v7.problem_fingerprint_sha256

    @property
    def config_fingerprint_sha256(self) -> str:
        return self._component_config_fingerprint_sha256

    @property
    def implementation_source_sha256(self) -> str:
        if self._v7.implementation_source_sha256 != self._implementation_source_sha256:
            raise TorsionContactRefinementError(
                "nested V7 implementation identity changed"
            )
        return self._implementation_source_sha256

    @property
    def receipts(self) -> Mapping[str, Mapping[str, object]]:
        return MappingProxyType(
            {
                key: MappingProxyType(deepcopy(dict(receipt)))
                for key, receipt in self._receipts.items()
            }
        )

    def _clearance_statistics(
        self,
        coordinates: torch.Tensor,
    ) -> _ReceptorClearanceStatistics:
        return _receptor_clearance_statistics(
            coordinates,
            receptor_coordinates=self._receptor_coordinates,
            ligand_radii=self._ligand_radii,
            receptor_radii=self._receptor_radii,
            receptor_atom_indices=self._receptor_atom_indices,
        )

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.fingerprint_sha256 in self._receipts:
            raise TorsionContactRefinementError("proposal was already refined")
        if type(max_steps) is not int or not 0 <= max_steps <= 10_000:
            raise TorsionContactRefinementError(
                "max_steps must be an integer in [0,10000]"
            )
        cached_legacy = self._legacy_results.get(proposal.fingerprint_sha256)
        if cached_legacy is None:
            legacy_v7 = self._v7.refine(proposal, max_steps=max_steps)
            self._legacy_results[proposal.fingerprint_sha256] = (
                max_steps,
                legacy_v7,
            )
        else:
            cached_max_steps, legacy_v7 = cached_legacy
            if cached_max_steps != max_steps:
                raise TorsionContactRefinementError(
                    "experimental V8 retry must use the original max_steps"
                )
        legacy_v7_receipt = dict(
            self._v7.receipts[proposal.fingerprint_sha256]
        )
        legacy_projection = dict(legacy_v7_receipt)
        legacy_receipt_sha256 = legacy_projection.pop("receipt_sha256", "")
        if (
            legacy_receipt_sha256 != _sha256(legacy_projection)
            or legacy_v7_receipt.get("source_proposal_sha256")
            != proposal.fingerprint_sha256
        ):
            raise TorsionContactRefinementError("nested V7 receipt is invalid")
        optimized_state = self._v7._optimized_state_for_experimental_v8(
            proposal.fingerprint_sha256
        )
        baseline_state = self._v7._baseline_state_for_experimental_v8(
            proposal.fingerprint_sha256
        )
        (
            observed_baseline_receptor,
            observed_baseline_internal,
            observed_baseline_combined,
            _baseline_receptor_by_atom,
            _baseline_internal_by_pair,
        ) = self._v7._objective(
            baseline_state.coordinates.to(dtype=torch.float64, device="cpu")
        )
        (
            observed_optimized_receptor,
            observed_optimized_internal,
            observed_optimized_combined,
            _receptor_by_atom,
            _internal_by_pair,
        ) = self._v7._objective(
            optimized_state.coordinates.to(dtype=torch.float64, device="cpu")
        )
        (
            observed_legacy_final_receptor,
            observed_legacy_final_internal,
            observed_legacy_final_combined,
            _legacy_final_receptor_by_atom,
            _legacy_final_internal_by_pair,
        ) = self._v7._objective(
            legacy_v7.coordinates.to(dtype=torch.float64, device="cpu")
        )
        try:
            baseline_receptor = float.fromhex(
                str(legacy_v7_receipt["baseline_v6_receptor_penalty_binary64_hex"])
            )
            baseline_internal = float.fromhex(
                str(legacy_v7_receipt["baseline_v6_internal_penalty_binary64_hex"])
            )
            baseline_combined = float.fromhex(
                str(legacy_v7_receipt["baseline_v6_combined_penalty_binary64_hex"])
            )
            optimized_receptor = float.fromhex(
                str(legacy_v7_receipt["optimized_receptor_penalty_binary64_hex"])
            )
            optimized_internal = float.fromhex(
                str(legacy_v7_receipt["optimized_internal_penalty_binary64_hex"])
            )
            optimized_combined = float.fromhex(
                str(legacy_v7_receipt["optimized_combined_penalty_binary64_hex"])
            )
            legacy_final_receptor = float.fromhex(
                str(legacy_v7_receipt["final_receptor_penalty_binary64_hex"])
            )
            legacy_final_internal = float.fromhex(
                str(legacy_v7_receipt["final_internal_penalty_binary64_hex"])
            )
            legacy_final_combined = float.fromhex(
                str(legacy_v7_receipt["final_combined_penalty_binary64_hex"])
            )
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise TorsionContactRefinementError(
                "nested V7 objective receipt is invalid"
            ) from exc
        tolerance = self._v7._config.penalty_tolerance
        optimized_dtype = optimized_state.coordinates.dtype
        precision = (
            float(torch.finfo(optimized_dtype).eps)
            if optimized_dtype.is_floating_point
            else 0.0
        )
        validation_scale = max(
            1.0,
            abs(observed_optimized_receptor),
            abs(observed_optimized_internal),
            abs(observed_optimized_combined),
            abs(observed_baseline_receptor),
            abs(observed_baseline_internal),
            abs(observed_baseline_combined),
            abs(observed_legacy_final_receptor),
            abs(observed_legacy_final_internal),
            abs(observed_legacy_final_combined),
            abs(optimized_receptor),
            abs(optimized_internal),
            abs(optimized_combined),
        )
        objective_validation_tolerance = max(
            tolerance,
            128.0 * precision * validation_scale,
        )
        if (
            any(
                not math.isfinite(value) or value < 0.0
                for value in (
                    baseline_receptor,
                    baseline_internal,
                    baseline_combined,
                    optimized_receptor,
                    optimized_internal,
                    optimized_combined,
                    legacy_final_receptor,
                    legacy_final_internal,
                    legacy_final_combined,
                )
            )
            or abs(observed_optimized_receptor - optimized_receptor)
            > objective_validation_tolerance
            or abs(observed_optimized_internal - optimized_internal)
            > objective_validation_tolerance
            or abs(observed_optimized_combined - optimized_combined)
            > objective_validation_tolerance
            or abs(observed_baseline_receptor - baseline_receptor)
            > objective_validation_tolerance
            or abs(observed_baseline_internal - baseline_internal)
            > objective_validation_tolerance
            or abs(observed_baseline_combined - baseline_combined)
            > objective_validation_tolerance
            or abs(observed_legacy_final_receptor - legacy_final_receptor)
            > objective_validation_tolerance
            or abs(observed_legacy_final_internal - legacy_final_internal)
            > objective_validation_tolerance
            or abs(observed_legacy_final_combined - legacy_final_combined)
            > objective_validation_tolerance
        ):
            raise TorsionContactRefinementError(
                "nested V7 optimized objective is cross-wired"
            )
        baseline_receptor = observed_baseline_receptor
        baseline_internal = observed_baseline_internal
        baseline_combined = observed_baseline_combined
        optimized_receptor = observed_optimized_receptor
        optimized_internal = observed_optimized_internal
        optimized_combined = observed_optimized_combined
        legacy_final_receptor = observed_legacy_final_receptor
        legacy_final_internal = observed_legacy_final_internal
        legacy_final_combined = observed_legacy_final_combined
        legacy_clearance = self._clearance_statistics(legacy_v7.coordinates)
        optimized_clearance = self._clearance_statistics(
            optimized_state.coordinates
        )
        torsion_variant_available = bool(
            legacy_v7_receipt.get("torsion_variant_available")
        )
        legacy_v7_selected = bool(legacy_v7_receipt.get("torsion_selected"))
        combined_guard = bool(
            optimized_combined < baseline_combined - tolerance
        )
        receptor_guard = bool(
            optimized_receptor <= baseline_receptor + tolerance
        )
        internal_guard = bool(
            optimized_internal <= baseline_internal + tolerance
        )
        surface_gap_guard = bool(
            optimized_clearance.minimum_vdw_surface_gap_angstrom
            > legacy_clearance.minimum_vdw_surface_gap_angstrom
            + self._config.clearance_tolerance_angstrom
        )
        raw_distance_guard = bool(
            optimized_clearance.minimum_distance_angstrom
            + self._config.clearance_tolerance_angstrom
            >= legacy_clearance.minimum_distance_angstrom
        )
        clearance_guard_passed = bool(
            torsion_variant_available
            and combined_guard
            and receptor_guard
            and internal_guard
            and surface_gap_guard
            and raw_distance_guard
        )
        v8_clearance_selected = bool(
            not legacy_v7_selected and clearance_guard_passed
        )
        if v8_clearance_selected:
            final_coordinates = optimized_state.coordinates
            final_torsion_angles = optimized_state.torsion_angles
            final_receptor = optimized_receptor
            final_internal = optimized_internal
            final_combined = optimized_combined
            accepted_torsion_steps = int(
                legacy_v7_receipt["evaluated_torsion_steps"]
            )
            accepted_torsion_moves = list(
                legacy_v7_receipt["evaluated_torsion_moves"]
            )
            total_torsion_path = str(
                legacy_v7_receipt[
                    "evaluated_total_torsion_path_radians_binary64_hex"
                ]
            )
            selection_reason = "outside_v7_window_clearance_guard_selected"
        else:
            final_coordinates = legacy_v7.coordinates
            final_torsion_angles = legacy_v7.torsion_angles
            final_receptor = legacy_final_receptor
            final_internal = legacy_final_internal
            final_combined = legacy_final_combined
            accepted_torsion_steps = int(
                legacy_v7_receipt["accepted_torsion_steps"]
            )
            accepted_torsion_moves = list(
                legacy_v7_receipt["accepted_torsion_moves"]
            )
            total_torsion_path = str(
                legacy_v7_receipt["total_torsion_path_radians_binary64_hex"]
            )
            selection_reason = (
                "legacy_v7_window_selection_retained"
                if legacy_v7_selected
                else "legacy_v7_retained_clearance_guard_rejected"
            )
        final_clearance = (
            optimized_clearance if v8_clearance_selected else legacy_clearance
        )
        baseline_steps = int(legacy_v7_receipt["accepted_steps"]) - int(
            legacy_v7_receipt["accepted_torsion_steps"]
        )
        accepted_rigid_rotation_steps = int(
            legacy_v7_receipt.get("accepted_rigid_rotation_steps", 0)
        )
        receipt: dict[str, object] = {
            "schema_id": INTERACTION_AWARE_TORSION_CLEARANCE_RECEIPT_V8_SCHEMA_ID,
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self.config_fingerprint_sha256,
            "lane": (
                "torsion_clearance_v8_experimental"
                if v8_clearance_selected
                else "torsion_contact_v7_retained"
            ),
            "selection_reason": selection_reason,
            "legacy_v7_receipt_sha256": legacy_receipt_sha256,
            "legacy_v7_receipt_payload": legacy_v7_receipt,
            "v3_proposal_indices": list(self._v3_proposal_indices),
            "clearance_tolerance_angstrom_binary64_hex": (
                self._config.clearance_tolerance_angstrom.hex()
            ),
            "optimized_objective_validation_tolerance_binary64_hex": (
                objective_validation_tolerance.hex()
            ),
            "optimized_objective_recomputed_from_output_coordinates": True,
            "legacy_v7_selected": legacy_v7_selected,
            "torsion_variant_available": torsion_variant_available,
            "combined_strict_decrease_guard_passed": combined_guard,
            "receptor_nonincrease_guard_passed": receptor_guard,
            "internal_nonincrease_guard_passed": internal_guard,
            "minimum_vdw_surface_gap_improvement_guard_passed": (
                surface_gap_guard
            ),
            "raw_minimum_distance_nonregression_guard_passed": raw_distance_guard,
            "v8_clearance_guard_passed": clearance_guard_passed,
            "v8_clearance_selected": v8_clearance_selected,
            "legacy_v7_clearance": legacy_clearance.to_dict(),
            "optimized_clearance": optimized_clearance.to_dict(),
            "final_clearance": final_clearance.to_dict(),
            "initial_receptor_penalty_binary64_hex": legacy_v7_receipt[
                "initial_receptor_penalty_binary64_hex"
            ],
            "baseline_v6_receptor_penalty_binary64_hex": baseline_receptor.hex(),
            "optimized_receptor_penalty_binary64_hex": optimized_receptor.hex(),
            "final_receptor_penalty_binary64_hex": final_receptor.hex(),
            "initial_internal_penalty_binary64_hex": legacy_v7_receipt[
                "initial_internal_penalty_binary64_hex"
            ],
            "baseline_v6_internal_penalty_binary64_hex": baseline_internal.hex(),
            "optimized_internal_penalty_binary64_hex": optimized_internal.hex(),
            "final_internal_penalty_binary64_hex": final_internal.hex(),
            "initial_combined_penalty_binary64_hex": legacy_v7_receipt[
                "initial_combined_penalty_binary64_hex"
            ],
            "baseline_v6_combined_penalty_binary64_hex": baseline_combined.hex(),
            "optimized_combined_penalty_binary64_hex": optimized_combined.hex(),
            "final_combined_penalty_binary64_hex": final_combined.hex(),
            "initial_penalty_binary64_hex": legacy_v7_receipt[
                "initial_penalty_binary64_hex"
            ],
            "final_penalty_binary64_hex": final_combined.hex(),
            "accepted_torsion_steps": accepted_torsion_steps,
            "accepted_torsion_moves": accepted_torsion_moves,
            "total_torsion_path_radians_binary64_hex": total_torsion_path,
            "accepted_steps": baseline_steps + accepted_torsion_steps,
            "accepted_translation_steps": legacy_v7_receipt[
                "accepted_translation_steps"
            ],
            "accepted_rigid_rotation_steps": accepted_rigid_rotation_steps,
            "accepted_rotation_steps": (
                accepted_rigid_rotation_steps + accepted_torsion_steps
            ),
            "accepted_rotation_steps_include_torsion": True,
            "line_search_evaluation_count": legacy_v7_receipt[
                "line_search_evaluation_count"
            ],
            "fallback_direction_step_count": legacy_v7_receipt[
                "fallback_direction_step_count"
            ],
            "original_pose_valid": legacy_v7_receipt["original_pose_valid"],
            "total_translation_binary64_hex": legacy_v7_receipt[
                "total_translation_binary64_hex"
            ],
            "total_rotation_vector_binary64_hex": legacy_v7_receipt[
                "total_rotation_vector_binary64_hex"
            ],
            "pre_coordinates_sha256": legacy_v7_receipt[
                "pre_coordinates_sha256"
            ],
            "legacy_v7_coordinates_sha256": coordinate_fingerprint(
                legacy_v7.coordinates
            ),
            "optimized_coordinates_sha256": coordinate_fingerprint(
                optimized_state.coordinates
            ),
            "post_coordinates_sha256": coordinate_fingerprint(final_coordinates),
            "ranking_score_reused_as_physical_energy": False,
            "posebusters_or_rmsd_used_for_selection": False,
            "source_lane_retained": True,
            "development_experimental": True,
            "stage0_eligible": False,
            "scientifically_validated": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            final_coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=final_torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


__all__ = [
    "INTERACTION_AWARE_TORSION_CLEARANCE_CONFIG_V8_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CLEARANCE_RECEIPT_V8_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_ID",
    "INTERACTION_AWARE_TORSION_CLEARANCE_REFINER_V8_VERSION",
    "INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION",
    "InteractionAwareTorsionClearanceConfigV8",
    "InteractionAwareTorsionClearanceEnsembleRefinerV8",
    "InteractionAwareTorsionContactConfigV7",
    "InteractionAwareTorsionContactEnsembleRefinerV7",
    "TorsionContactRefinementError",
]
