"""Receipt-bound torsion contact rescue layered after rigid V6 refinement.

The refiner deliberately reuses the authority-proven torsion tree.  It does
not perceive new chemistry, alter ring bonds, consult PoseBusters/RMSD, or
replace the retained source lane.  A torsion move is accepted only when a
bounded receptor-plus-internal quartic-overlap objective strictly decreases
without increasing its receptor component.
"""

from __future__ import annotations

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
        return MappingProxyType(dict(self._receipts))

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
        coordinates = baseline.coordinates.to(dtype=torch.float64, device="cpu")
        torsion_angles = baseline.torsion_angles.clone().to(
            dtype=torch.float64,
            device="cpu",
        )
        (
            initial_receptor,
            initial_internal,
            initial_combined,
            receptor_by_atom,
            internal_by_pair,
        ) = self._objective(coordinates)
        current_receptor = initial_receptor
        current_internal = initial_internal
        current_combined = initial_combined
        evaluation_count = 1
        total_torsion_path = 0.0
        accepted_moves: list[dict[str, object]] = []
        baseline_steps = int(baseline_receipt["accepted_steps"])
        remaining_steps = max(0, max_steps - baseline_steps)
        torsion_step_budget = min(
            self._config.maximum_torsion_steps,
            remaining_steps,
        )
        selection_window_reachable = bool(
            initial_receptor
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
            final_receptor = initial_receptor
            final_internal = initial_internal
            final_combined = initial_combined
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
            "selection_window_reachable_from_initial_receptor_penalty": (
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
            "initial_receptor_penalty_binary64_hex": initial_receptor.hex(),
            "optimized_receptor_penalty_binary64_hex": (
                optimized_receptor.hex()
            ),
            "final_receptor_penalty_binary64_hex": final_receptor.hex(),
            "initial_internal_penalty_binary64_hex": initial_internal.hex(),
            "optimized_internal_penalty_binary64_hex": optimized_internal.hex(),
            "final_internal_penalty_binary64_hex": final_internal.hex(),
            "initial_combined_penalty_binary64_hex": initial_combined.hex(),
            "optimized_combined_penalty_binary64_hex": (
                optimized_combined.hex()
            ),
            "final_combined_penalty_binary64_hex": final_combined.hex(),
            "initial_penalty_binary64_hex": initial_combined.hex(),
            "final_penalty_binary64_hex": final_combined.hex(),
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
            "accepted_rotation_steps": baseline_receipt.get(
                "accepted_rotation_steps",
                0,
            ),
            "line_search_evaluation_count": (
                int(baseline_receipt.get("line_search_evaluation_count", 0))
                + evaluation_count
                - 1
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


__all__ = [
    "INTERACTION_AWARE_TORSION_CONTACT_CONFIG_V7_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_ID",
    "INTERACTION_AWARE_TORSION_CONTACT_REFINER_V7_VERSION",
    "InteractionAwareTorsionContactConfigV7",
    "InteractionAwareTorsionContactEnsembleRefinerV7",
    "TorsionContactRefinementError",
]
