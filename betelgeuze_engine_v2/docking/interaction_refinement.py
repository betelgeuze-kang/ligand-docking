"""Deterministic receptor-clash relief for rigid candidate translations."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping

import torch

from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256

from .authority import AuthenticatedDockingProblem, DockingAuthorityError
from .contact_validity import VdwContactPolicy
from .identity import coordinate_fingerprint
from .proposals import DockingProposal


CLASH_RELIEF_REFINER_ID = "betelgeuze.engine_v2_receptor_clash_relief_refiner"
CLASH_RELIEF_REFINER_VERSION = "1.0.0"
CLASH_RELIEF_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_receptor_clash_relief_config/1.0.0"
)
INTERACTION_AWARE_RIGID_REFINER_V2_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_refiner"
)
INTERACTION_AWARE_RIGID_REFINER_V2_VERSION = "2.0.0"
INTERACTION_AWARE_RIGID_CONFIG_V2_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_refiner_config/2.0.0"
)
INTERACTION_AWARE_RIGID_REFINER_V3_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_refiner_v3"
)
INTERACTION_AWARE_RIGID_REFINER_V3_VERSION = "3.0.0"
INTERACTION_AWARE_RIGID_CONFIG_V3_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_refiner_config/3.0.0"
)
INTERACTION_AWARE_RIGID_CLEARANCE_CONFIG_V4_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_clearance_config/4.0.0"
)
INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_ensemble_refiner"
)
INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_VERSION = "4.0.0"
INTERACTION_AWARE_RIGID_ENSEMBLE_CONFIG_V4_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_ensemble_config/4.0.0"
)
INTERACTION_AWARE_RIGID_ENSEMBLE_RECEIPT_V4_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_ensemble_receipt/4.0.0"
)
INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_clearance_ensemble_refiner"
)
INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_VERSION = "5.0.0"
INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_CONFIG_V5_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_clearance_ensemble_config/5.0.0"
)
INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_RECEIPT_V5_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_clearance_ensemble_receipt/5.0.0"
)
INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_hybrid_ensemble_refiner"
)
INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_VERSION = "6.0.0"
INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_CONFIG_V6_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_hybrid_ensemble_config/6.0.0"
)
INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_RECEIPT_V6_SCHEMA_ID = (
    "betelgeuze.engine_v2_interaction_aware_rigid_hybrid_ensemble_receipt/6.0.0"
)
INTERACTION_AWARE_RIGID_HYBRID_NEAR_CLEAR_PENALTY = 2.0**-12


class ClashReliefRefinementError(DockingAuthorityError):
    """The bounded receptor-clash relief contract failed closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class ClashReliefConfig:
    overlap_scale: float = 0.75
    maximum_step_angstrom: float = 0.15
    maximum_total_translation_angstrom: float = 1.50
    epsilon_angstrom: float = 1.0e-9
    schema_id: str = CLASH_RELIEF_CONFIG_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        values = (
            self.overlap_scale,
            self.maximum_step_angstrom,
            self.maximum_total_translation_angstrom,
            self.epsilon_angstrom,
        )
        if any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in values):
            raise ClashReliefRefinementError("clash-relief values must be positive")
        if not 0.55 <= self.overlap_scale <= 1.0:
            raise ClashReliefRefinementError("overlap_scale must be in [0.55,1.0]")
        if self.maximum_step_angstrom > self.maximum_total_translation_angstrom:
            raise ClashReliefRefinementError("clash-relief step exceeds total bound")
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self.to_dict()))

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self.to_dict())
        if observed != self._fingerprint_sha256:
            raise ClashReliefRefinementError("clash-relief configuration changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "overlap_scale": self.overlap_scale,
            "maximum_step_angstrom": self.maximum_step_angstrom,
            "maximum_total_translation_angstrom": (
                self.maximum_total_translation_angstrom
            ),
            "epsilon_angstrom": self.epsilon_angstrom,
            "optimization_variables": ["translation_x", "translation_y", "translation_z"],
            "objective": "quartic_receptor_ligand_vdw_overlap",
            "ranking_score_reused_as_physical_energy": False,
            "scientifically_validated": False,
        }


@dataclass(frozen=True, slots=True)
class InteractionAwareRigidConfigV2:
    """Bounded vdW-contact objective with deterministic backtracking."""

    overlap_scale: float = 0.75
    maximum_step_angstrom: float = 0.30
    minimum_step_angstrom: float = 0.009375
    maximum_total_translation_angstrom: float = 2.25
    maximum_backtracking_evaluations: int = 6
    penalty_tolerance: float = 1.0e-18
    epsilon_angstrom: float = 1.0e-9
    schema_id: str = INTERACTION_AWARE_RIGID_CONFIG_V2_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        values = (
            self.overlap_scale,
            self.maximum_step_angstrom,
            self.minimum_step_angstrom,
            self.maximum_total_translation_angstrom,
            self.penalty_tolerance,
            self.epsilon_angstrom,
        )
        if any(
            not math.isfinite(float(value)) or float(value) <= 0.0
            for value in values
        ):
            raise ClashReliefRefinementError(
                "interaction-aware rigid refinement values must be positive"
            )
        if not 0.55 <= self.overlap_scale <= 1.0:
            raise ClashReliefRefinementError("overlap_scale must be in [0.55,1.0]")
        if not self.minimum_step_angstrom <= self.maximum_step_angstrom:
            raise ClashReliefRefinementError(
                "minimum refinement step exceeds maximum step"
            )
        if self.maximum_step_angstrom > self.maximum_total_translation_angstrom:
            raise ClashReliefRefinementError(
                "interaction-aware step exceeds total translation bound"
            )
        if (
            type(self.maximum_backtracking_evaluations) is not int
            or not 1 <= self.maximum_backtracking_evaluations <= 16
        ):
            raise ClashReliefRefinementError(
                "maximum_backtracking_evaluations must be in [1,16]"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self.to_dict()))

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self.to_dict())
        if observed != self._fingerprint_sha256:
            raise ClashReliefRefinementError(
                "interaction-aware rigid configuration changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "overlap_scale": self.overlap_scale,
            "maximum_step_angstrom": self.maximum_step_angstrom,
            "minimum_step_angstrom": self.minimum_step_angstrom,
            "maximum_total_translation_angstrom": (
                self.maximum_total_translation_angstrom
            ),
            "maximum_backtracking_evaluations": (
                self.maximum_backtracking_evaluations
            ),
            "penalty_tolerance": self.penalty_tolerance,
            "epsilon_angstrom": self.epsilon_angstrom,
            "optimization_variables": [
                "translation_x",
                "translation_y",
                "translation_z",
            ],
            "objective": (
                "quartic_receptor_ligand_vdw_overlap_with_backtracking"
            ),
            "validity_target": "0.75_sum_vdw_radii_contact_clearance",
            "ranking_score_reused_as_physical_energy": False,
            "scientifically_validated": False,
        }


@dataclass(frozen=True, slots=True)
class InteractionAwareRigidConfigV3:
    """Bounded translation/rotation clash objective with a pocket guard."""

    overlap_scale: float = 0.75
    maximum_step_angstrom: float = 0.30
    minimum_step_angstrom: float = 0.009375
    maximum_total_translation_angstrom: float = 2.25
    maximum_rotation_step_radians: float = math.pi / 36.0
    minimum_rotation_step_radians: float = math.pi / 1152.0
    maximum_total_rotation_radians: float = math.pi / 18.0
    maximum_rotation_steps: int = 2
    minimum_rotation_relative_penalty_reduction: float = 0.01
    maximum_centroid_offset_angstrom: float = 4.0
    maximum_backtracking_evaluations: int = 6
    penalty_tolerance: float = 1.0e-18
    epsilon_angstrom: float = 1.0e-9
    schema_id: str = INTERACTION_AWARE_RIGID_CONFIG_V3_SCHEMA_ID
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        values = (
            self.overlap_scale,
            self.maximum_step_angstrom,
            self.minimum_step_angstrom,
            self.maximum_total_translation_angstrom,
            self.maximum_rotation_step_radians,
            self.minimum_rotation_step_radians,
            self.maximum_total_rotation_radians,
            self.minimum_rotation_relative_penalty_reduction,
            self.maximum_centroid_offset_angstrom,
            self.penalty_tolerance,
            self.epsilon_angstrom,
        )
        if any(
            not math.isfinite(float(value)) or float(value) <= 0.0
            for value in values
        ):
            raise ClashReliefRefinementError(
                "interaction-aware rigid refinement values must be positive"
            )
        if not 0.55 <= self.overlap_scale <= 1.0:
            raise ClashReliefRefinementError("overlap_scale must be in [0.55,1.0]")
        if not self.minimum_step_angstrom <= self.maximum_step_angstrom:
            raise ClashReliefRefinementError(
                "minimum refinement step exceeds maximum step"
            )
        if self.maximum_step_angstrom > self.maximum_total_translation_angstrom:
            raise ClashReliefRefinementError(
                "interaction-aware step exceeds total translation bound"
            )
        if not (
            self.minimum_rotation_step_radians
            <= self.maximum_rotation_step_radians
            <= self.maximum_total_rotation_radians
        ):
            raise ClashReliefRefinementError(
                "interaction-aware rotation bounds are inconsistent"
            )
        if (
            type(self.maximum_rotation_steps) is not int
            or not 1 <= self.maximum_rotation_steps <= 8
        ):
            raise ClashReliefRefinementError(
                "maximum_rotation_steps must be in [1,8]"
            )
        if not 0.0 < self.minimum_rotation_relative_penalty_reduction <= 0.25:
            raise ClashReliefRefinementError(
                "minimum rotation penalty reduction must be in (0,0.25]"
            )
        if not 0.5 <= self.maximum_centroid_offset_angstrom <= 8.0:
            raise ClashReliefRefinementError(
                "maximum centroid offset must be in [0.5,8.0] angstrom"
            )
        if (
            type(self.maximum_backtracking_evaluations) is not int
            or not 1 <= self.maximum_backtracking_evaluations <= 16
        ):
            raise ClashReliefRefinementError(
                "maximum_backtracking_evaluations must be in [1,16]"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self.to_dict()))

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self.to_dict())
        if observed != self._fingerprint_sha256:
            raise ClashReliefRefinementError(
                "interaction-aware rigid configuration changed"
            )
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "overlap_scale": self.overlap_scale,
            "maximum_step_angstrom": self.maximum_step_angstrom,
            "minimum_step_angstrom": self.minimum_step_angstrom,
            "maximum_total_translation_angstrom": (
                self.maximum_total_translation_angstrom
            ),
            "maximum_rotation_step_radians": self.maximum_rotation_step_radians,
            "minimum_rotation_step_radians": self.minimum_rotation_step_radians,
            "maximum_total_rotation_radians": self.maximum_total_rotation_radians,
            "maximum_rotation_steps": self.maximum_rotation_steps,
            "minimum_rotation_relative_penalty_reduction": (
                self.minimum_rotation_relative_penalty_reduction
            ),
            "maximum_centroid_offset_angstrom": (
                self.maximum_centroid_offset_angstrom
            ),
            "maximum_backtracking_evaluations": (
                self.maximum_backtracking_evaluations
            ),
            "penalty_tolerance": self.penalty_tolerance,
            "epsilon_angstrom": self.epsilon_angstrom,
            "optimization_variables": [
                "translation_x",
                "translation_y",
                "translation_z",
                "rotation_x",
                "rotation_y",
                "rotation_z",
            ],
            "objective": (
                "quartic_receptor_ligand_vdw_overlap_with_backtracking"
            ),
            "validity_target": "0.75_sum_vdw_radii_contact_clearance",
            "centroid_constraint": "hard_pocket_center_offset_bound",
            "rotation_vector_receipt_semantics": (
                "sum_of_accepted_axis_angle_step_vectors"
            ),
            "ranking_score_reused_as_physical_energy": False,
            "scientifically_validated": False,
        }


@dataclass(frozen=True, slots=True)
class InteractionAwareRigidClearanceConfigV4(InteractionAwareRigidConfigV3):
    """Bounded higher-clearance policy for retained-source variant lanes."""

    overlap_scale: float = 0.80
    maximum_total_translation_angstrom: float = 4.0
    maximum_total_rotation_radians: float = math.pi / 6.0
    maximum_rotation_steps: int = 6
    schema_id: str = INTERACTION_AWARE_RIGID_CLEARANCE_CONFIG_V4_SCHEMA_ID

    def to_dict(self) -> dict[str, object]:
        payload = InteractionAwareRigidConfigV3.to_dict(self)
        payload.update(
            {
                "schema_id": self.schema_id,
                "validity_target": (
                    "parameterized_sum_vdw_radii_contact_clearance"
                ),
                "validity_target_overlap_scale_binary64_hex": (
                    self.overlap_scale.hex()
                ),
                "policy_role": "retained_source_variant_clearance_rescue",
                "source_lane_retention_required": True,
            }
        )
        return payload


class ReceptorClashReliefRefiner:
    """Bounded rigid translation optimizer for receptor-ligand overlaps."""

    refiner_id = CLASH_RELIEF_REFINER_ID
    refiner_version = CLASH_RELIEF_REFINER_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        config: ClashReliefConfig | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem):
            raise TypeError("authority must be AuthenticatedDockingProblem")
        if canonical_system_sha256(receptor_system) != authority.receptor_system_sha256:
            raise ClashReliefRefinementError("receptor system is cross-wired")
        if canonical_system_sha256(ligand_system) != authority.ligand_system_sha256:
            raise ClashReliefRefinementError("ligand system is cross-wired")
        if (
            len(implementation_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in implementation_source_sha256
            )
        ):
            raise ClashReliefRefinementError("implementation source hash is invalid")
        selected_config = config or ClashReliefConfig()
        selected_policy = radii_policy or VdwContactPolicy()
        receptor_indices = authority.receptor_atom_indices
        receptor_coordinates = receptor_system.coordinates[
            authority.receptor_model_index,
            list(receptor_indices),
        ].to(dtype=torch.float64, device="cpu")
        receptor_radii = torch.tensor(
            [selected_policy.radius(receptor_system.atoms[index].element) for index in receptor_indices],
            dtype=torch.float64,
        )
        ligand_radii = torch.tensor(
            [selected_policy.radius(atom.element) for atom in ligand_system.atoms],
            dtype=torch.float64,
        )
        self._authority = authority
        self._receptor_coordinates = receptor_coordinates.contiguous()
        self._receptor_radii = receptor_radii
        self._ligand_radii = ligand_radii
        self._config = selected_config
        self._implementation_source_sha256 = implementation_source_sha256
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "config_sha256": selected_config.fingerprint_sha256,
                "radii_policy_sha256": selected_policy.fingerprint_sha256,
                "receptor_coordinate_sha256": coordinate_fingerprint(
                    self._receptor_coordinates
                ),
                "ligand_radii": [float(value).hex() for value in ligand_radii],
                "receptor_radii": [float(value).hex() for value in receptor_radii],
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
        return self._implementation_source_sha256

    @property
    def receipts(self) -> Mapping[str, Mapping[str, object]]:
        return MappingProxyType(dict(self._receipts))

    def _penalty_and_direction(
        self, coordinates: torch.Tensor
    ) -> tuple[float, torch.Tensor]:
        penalty = 0.0
        direction = torch.zeros(3, dtype=torch.float64)
        for start in range(0, len(self._receptor_coordinates), 4096):
            stop = min(start + 4096, len(self._receptor_coordinates))
            receptor = self._receptor_coordinates[start:stop]
            receptor_radii = self._receptor_radii[start:stop]
            delta = coordinates[:, None, :] - receptor[None, :, :]
            distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
                self._config.epsilon_angstrom
            )
            cutoff = self._config.overlap_scale * (
                self._ligand_radii[:, None] + receptor_radii[None, :]
            )
            penetration = torch.clamp(cutoff - distance, min=0.0)
            penalty += float(torch.sum(penetration**4).item())
            direction += torch.sum(
                penetration[..., None] ** 3 * delta / distance[..., None],
                dim=(0, 1),
            )
        return penalty, direction

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise ClashReliefRefinementError("proposal is cross-wired")
        if type(max_steps) is not int or not 1 <= max_steps <= 128:
            raise ClashReliefRefinementError("max_steps must be in [1,128]")
        if proposal.fingerprint_sha256 in self._receipts:
            raise ClashReliefRefinementError("proposal was already refined")
        coordinates = proposal.coordinates.to(dtype=torch.float64, device="cpu").clone()
        initial_penalty, _ = self._penalty_and_direction(coordinates)
        original_valid = self._authority.validity_context.evaluate(proposal).valid
        total_shift = torch.zeros(3, dtype=torch.float64)
        accepted_steps = 0
        for _ in range(0 if original_valid else max_steps):
            penalty, direction = self._penalty_and_direction(coordinates)
            norm = float(torch.linalg.vector_norm(direction).item())
            if penalty <= 1.0e-18 or norm <= self._config.epsilon_angstrom:
                break
            remaining = self._config.maximum_total_translation_angstrom - float(
                torch.linalg.vector_norm(total_shift).item()
            )
            if remaining <= self._config.epsilon_angstrom:
                break
            step = direction / norm * min(self._config.maximum_step_angstrom, remaining)
            trial = coordinates + step
            trial_penalty, _ = self._penalty_and_direction(trial)
            if trial_penalty >= penalty:
                break
            coordinates = trial
            total_shift += step
            accepted_steps += 1
        final_penalty, _ = self._penalty_and_direction(coordinates)
        receipt: dict[str, object] = {
            "schema_id": "betelgeuze.engine_v2_receptor_clash_relief_receipt/1.0.0",
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self._config.fingerprint_sha256,
            "initial_penalty_binary64_hex": initial_penalty.hex(),
            "final_penalty_binary64_hex": final_penalty.hex(),
            "accepted_steps": accepted_steps,
            "original_pose_valid": original_valid,
            "total_translation_binary64_hex": [
                float(value).hex() for value in total_shift
            ],
            "pre_coordinates_sha256": coordinate_fingerprint(proposal.coordinates),
            "post_coordinates_sha256": coordinate_fingerprint(coordinates),
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            coordinates.to(dtype=proposal.coordinates.dtype),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=proposal.torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


class InteractionAwareRigidRefinerV2(ReceptorClashReliefRefiner):
    """Translation-only v2 reference retained as a frozen comparison lane."""

    refiner_id = INTERACTION_AWARE_RIGID_REFINER_V2_ID
    refiner_version = INTERACTION_AWARE_RIGID_REFINER_V2_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        config: InteractionAwareRigidConfigV2 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        selected_config = config or InteractionAwareRigidConfigV2()
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=selected_config,  # type: ignore[arg-type]
            radii_policy=radii_policy,
        )

    def _maximum_penetration_direction(
        self,
        coordinates: torch.Tensor,
    ) -> torch.Tensor:
        best_penetration = -1.0
        best_ligand_index = 0
        best_receptor_index = 0
        best_delta = torch.zeros(3, dtype=torch.float64)
        best_distance = self._config.epsilon_angstrom
        for start in range(0, len(self._receptor_coordinates), 4096):
            stop = min(start + 4096, len(self._receptor_coordinates))
            receptor = self._receptor_coordinates[start:stop]
            receptor_radii = self._receptor_radii[start:stop]
            delta = coordinates[:, None, :] - receptor[None, :, :]
            distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
                self._config.epsilon_angstrom
            )
            cutoff = self._config.overlap_scale * (
                self._ligand_radii[:, None] + receptor_radii[None, :]
            )
            penetration = torch.clamp(cutoff - distance, min=0.0)
            flat_index = int(torch.argmax(penetration).item())
            receptor_count = int(penetration.shape[1])
            ligand_index = flat_index // receptor_count
            receptor_local_index = flat_index % receptor_count
            observed = float(
                penetration[ligand_index, receptor_local_index].item()
            )
            receptor_index = start + receptor_local_index
            if (
                observed > best_penetration
                or (
                    observed == best_penetration
                    and (ligand_index, receptor_index)
                    < (best_ligand_index, best_receptor_index)
                )
            ):
                best_penetration = observed
                best_ligand_index = ligand_index
                best_receptor_index = receptor_index
                best_delta = delta[ligand_index, receptor_local_index]
                best_distance = float(
                    distance[ligand_index, receptor_local_index].item()
                )
        if best_penetration <= 0.0:
            return torch.zeros(3, dtype=torch.float64)
        norm = float(torch.linalg.vector_norm(best_delta).item())
        if norm > self._config.epsilon_angstrom:
            return best_delta / best_distance
        direction = torch.zeros(3, dtype=torch.float64)
        signed_axis = (best_ligand_index * 131 + best_receptor_index) % 6
        direction[signed_axis // 2] = -1.0 if signed_axis % 2 else 1.0
        return direction

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise ClashReliefRefinementError("proposal is cross-wired")
        if type(max_steps) is not int or not 1 <= max_steps <= 128:
            raise ClashReliefRefinementError("max_steps must be in [1,128]")
        if proposal.fingerprint_sha256 in self._receipts:
            raise ClashReliefRefinementError("proposal was already refined")

        coordinates = proposal.coordinates.to(
            dtype=torch.float64,
            device="cpu",
        ).clone()
        initial_penalty, _ = self._penalty_and_direction(coordinates)
        original_valid = self._authority.validity_context.evaluate(proposal).valid
        total_shift = torch.zeros(3, dtype=torch.float64)
        accepted_steps = 0
        line_search_evaluation_count = 0
        fallback_direction_step_count = 0

        for _ in range(max_steps):
            penalty, aggregate_direction = self._penalty_and_direction(coordinates)
            if penalty <= self._config.penalty_tolerance:
                break
            remaining = self._config.maximum_total_translation_angstrom - float(
                torch.linalg.vector_norm(total_shift).item()
            )
            if remaining <= self._config.minimum_step_angstrom:
                break

            directions: list[torch.Tensor] = []
            aggregate_norm = float(
                torch.linalg.vector_norm(aggregate_direction).item()
            )
            if aggregate_norm > self._config.epsilon_angstrom:
                directions.append(aggregate_direction / aggregate_norm)
            fallback_direction = self._maximum_penetration_direction(coordinates)
            fallback_norm = float(
                torch.linalg.vector_norm(fallback_direction).item()
            )
            if fallback_norm > self._config.epsilon_angstrom:
                fallback_direction = fallback_direction / fallback_norm
                if not directions or not torch.allclose(
                    directions[0],
                    fallback_direction,
                    atol=1.0e-12,
                    rtol=0.0,
                ):
                    directions.append(fallback_direction)
            if not directions:
                break

            base_step = min(self._config.maximum_step_angstrom, remaining)
            best: tuple[float, int, int, torch.Tensor, torch.Tensor] | None = None
            for direction_index, direction in enumerate(directions):
                step_size = base_step
                for backtracking_index in range(
                    self._config.maximum_backtracking_evaluations
                ):
                    if step_size < self._config.minimum_step_angstrom:
                        break
                    step = direction * step_size
                    trial_shift = total_shift + step
                    if float(torch.linalg.vector_norm(trial_shift).item()) > (
                        self._config.maximum_total_translation_angstrom
                        + self._config.epsilon_angstrom
                    ):
                        step_size *= 0.5
                        continue
                    trial = coordinates + step
                    trial_penalty, _ = self._penalty_and_direction(trial)
                    line_search_evaluation_count += 1
                    row = (
                        trial_penalty,
                        direction_index,
                        backtracking_index,
                        trial,
                        trial_shift,
                    )
                    if best is None or row[:3] < best[:3]:
                        best = row
                    step_size *= 0.5

            required_reduction = max(
                self._config.penalty_tolerance,
                abs(penalty) * 1.0e-12,
            )
            if best is None or best[0] > penalty - required_reduction:
                break
            coordinates = best[3]
            total_shift = best[4]
            accepted_steps += 1
            fallback_direction_step_count += int(best[1] > 0)

        final_penalty, _ = self._penalty_and_direction(coordinates)
        receipt: dict[str, object] = {
            "schema_id": (
                "betelgeuze.engine_v2_interaction_aware_rigid_refinement_receipt/2.0.0"
            ),
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self._config.fingerprint_sha256,
            "initial_penalty_binary64_hex": initial_penalty.hex(),
            "final_penalty_binary64_hex": final_penalty.hex(),
            "accepted_steps": accepted_steps,
            "line_search_evaluation_count": line_search_evaluation_count,
            "fallback_direction_step_count": fallback_direction_step_count,
            "original_pose_valid": original_valid,
            "total_translation_binary64_hex": [
                float(value).hex() for value in total_shift
            ],
            "pre_coordinates_sha256": coordinate_fingerprint(proposal.coordinates),
            "post_coordinates_sha256": coordinate_fingerprint(coordinates),
            "ranking_score_reused_as_physical_energy": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            coordinates.to(dtype=proposal.coordinates.dtype),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=proposal.torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


class InteractionAwareRigidRefinerV3(ReceptorClashReliefRefiner):
    """Rigid translation/rotation optimizer with a hard pocket guard."""

    refiner_id = INTERACTION_AWARE_RIGID_REFINER_V3_ID
    refiner_version = INTERACTION_AWARE_RIGID_REFINER_V3_VERSION

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        config: InteractionAwareRigidConfigV3 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        selected_config = config or InteractionAwareRigidConfigV3()
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=selected_config,  # type: ignore[arg-type]
            radii_policy=radii_policy,
        )
        self._pocket_center = authority.pocket.center.to(
            dtype=torch.float64,
            device="cpu",
        ).clone().contiguous()
        self._maximum_centroid_offset_angstrom = min(
            selected_config.maximum_centroid_offset_angstrom,
            float(authority.pocket.radius_angstrom),
        )

    def _maximum_penetration_direction(
        self,
        coordinates: torch.Tensor,
    ) -> torch.Tensor:
        best_penetration = -1.0
        best_ligand_index = 0
        best_receptor_index = 0
        best_delta = torch.zeros(3, dtype=torch.float64)
        best_distance = self._config.epsilon_angstrom
        for start in range(0, len(self._receptor_coordinates), 4096):
            stop = min(start + 4096, len(self._receptor_coordinates))
            receptor = self._receptor_coordinates[start:stop]
            receptor_radii = self._receptor_radii[start:stop]
            delta = coordinates[:, None, :] - receptor[None, :, :]
            distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
                self._config.epsilon_angstrom
            )
            cutoff = self._config.overlap_scale * (
                self._ligand_radii[:, None] + receptor_radii[None, :]
            )
            penetration = torch.clamp(cutoff - distance, min=0.0)
            flat_index = int(torch.argmax(penetration).item())
            receptor_count = int(penetration.shape[1])
            ligand_index = flat_index // receptor_count
            receptor_local_index = flat_index % receptor_count
            observed = float(
                penetration[ligand_index, receptor_local_index].item()
            )
            receptor_index = start + receptor_local_index
            if (
                observed > best_penetration
                or (
                    observed == best_penetration
                    and (ligand_index, receptor_index)
                    < (best_ligand_index, best_receptor_index)
                )
            ):
                best_penetration = observed
                best_ligand_index = ligand_index
                best_receptor_index = receptor_index
                best_delta = delta[ligand_index, receptor_local_index]
                best_distance = float(
                    distance[ligand_index, receptor_local_index].item()
                )
        if best_penetration <= 0.0:
            return torch.zeros(3, dtype=torch.float64)
        norm = float(torch.linalg.vector_norm(best_delta).item())
        if norm > self._config.epsilon_angstrom:
            return best_delta / best_distance
        direction = torch.zeros(3, dtype=torch.float64)
        signed_axis = (best_ligand_index * 131 + best_receptor_index) % 6
        direction[signed_axis // 2] = -1.0 if signed_axis % 2 else 1.0
        return direction

    def _rotation_torque(self, coordinates: torch.Tensor) -> torch.Tensor:
        centroid = coordinates.mean(dim=0)
        lever = coordinates - centroid
        torque = torch.zeros(3, dtype=torch.float64)
        for start in range(0, len(self._receptor_coordinates), 4096):
            stop = min(start + 4096, len(self._receptor_coordinates))
            receptor = self._receptor_coordinates[start:stop]
            receptor_radii = self._receptor_radii[start:stop]
            delta = coordinates[:, None, :] - receptor[None, :, :]
            distance = torch.linalg.vector_norm(delta, dim=-1).clamp_min(
                self._config.epsilon_angstrom
            )
            cutoff = self._config.overlap_scale * (
                self._ligand_radii[:, None] + receptor_radii[None, :]
            )
            penetration = torch.clamp(cutoff - distance, min=0.0)
            force = penetration[..., None] ** 3 * delta / distance[..., None]
            torque += torch.linalg.cross(
                lever[:, None, :].expand_as(force),
                force,
                dim=-1,
            ).sum(dim=(0, 1))
        return torque

    def _rotate_about_centroid(
        self,
        coordinates: torch.Tensor,
        rotation_vector: torch.Tensor,
    ) -> torch.Tensor:
        angle = float(torch.linalg.vector_norm(rotation_vector).item())
        if angle <= self._config.epsilon_angstrom:
            return coordinates.clone()
        axis = rotation_vector / angle
        centered = coordinates - coordinates.mean(dim=0)
        axis_rows = axis.expand_as(centered)
        rotated = (
            centered * math.cos(angle)
            + torch.linalg.cross(axis_rows, centered, dim=-1) * math.sin(angle)
            + axis_rows
            * torch.sum(centered * axis_rows, dim=-1, keepdim=True)
            * (1.0 - math.cos(angle))
        )
        return rotated + coordinates.mean(dim=0)

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256:
            raise ClashReliefRefinementError("proposal is cross-wired")
        if type(max_steps) is not int or not 1 <= max_steps <= 128:
            raise ClashReliefRefinementError("max_steps must be in [1,128]")
        if proposal.fingerprint_sha256 in self._receipts:
            raise ClashReliefRefinementError("proposal was already refined")

        coordinates = proposal.coordinates.to(
            dtype=torch.float64,
            device="cpu",
        ).clone()
        initial_penalty, _ = self._penalty_and_direction(coordinates)
        initial_centroid_offset = float(
            torch.linalg.vector_norm(
                coordinates.mean(dim=0) - self._pocket_center
            ).item()
        )
        original_valid = self._authority.validity_context.evaluate(proposal).valid
        total_shift = torch.zeros(3, dtype=torch.float64)
        total_rotation_vector = torch.zeros(3, dtype=torch.float64)
        total_rotation_path_radians = 0.0
        accepted_steps = 0
        accepted_rotation_steps = 0
        line_search_evaluation_count = 0
        fallback_direction_step_count = 0

        for _ in range(max_steps):
            penalty, aggregate_direction = self._penalty_and_direction(coordinates)
            if penalty <= self._config.penalty_tolerance:
                break
            remaining_translation = (
                self._config.maximum_total_translation_angstrom
                - float(torch.linalg.vector_norm(total_shift).item())
            )
            remaining_rotation = (
                self._config.maximum_total_rotation_radians
                - total_rotation_path_radians
            )
            if (
                remaining_translation <= self._config.minimum_step_angstrom
                and remaining_rotation
                <= self._config.minimum_rotation_step_radians
            ):
                break

            directions: list[torch.Tensor] = []
            aggregate_norm = float(torch.linalg.vector_norm(aggregate_direction).item())
            if aggregate_norm > self._config.epsilon_angstrom:
                directions.append(aggregate_direction / aggregate_norm)
            fallback_direction = self._maximum_penetration_direction(coordinates)
            fallback_norm = float(
                torch.linalg.vector_norm(fallback_direction).item()
            )
            if fallback_norm > self._config.epsilon_angstrom:
                fallback_direction = fallback_direction / fallback_norm
                if not directions or not torch.allclose(
                    directions[0],
                    fallback_direction,
                    atol=1.0e-12,
                    rtol=0.0,
                ):
                    directions.append(fallback_direction)
            best: tuple[
                float,
                int,
                int,
                torch.Tensor,
                torch.Tensor,
                torch.Tensor,
                float,
            ] | None = None
            if remaining_translation > self._config.minimum_step_angstrom:
                base_step = min(
                    self._config.maximum_step_angstrom,
                    remaining_translation,
                )
                for direction_index, direction in enumerate(directions):
                    step_size = base_step
                    for backtracking_index in range(
                        self._config.maximum_backtracking_evaluations
                    ):
                        if step_size < self._config.minimum_step_angstrom:
                            break
                        step = direction * step_size
                        trial_shift = total_shift + step
                        if float(torch.linalg.vector_norm(trial_shift).item()) > (
                            self._config.maximum_total_translation_angstrom
                            + self._config.epsilon_angstrom
                        ):
                            step_size *= 0.5
                            continue
                        trial = coordinates + step
                        trial_centroid_offset = float(
                            torch.linalg.vector_norm(
                                trial.mean(dim=0) - self._pocket_center
                            ).item()
                        )
                        if trial_centroid_offset > (
                            self._maximum_centroid_offset_angstrom
                            + self._config.epsilon_angstrom
                        ):
                            step_size *= 0.5
                            continue
                        trial_penalty, _ = self._penalty_and_direction(trial)
                        line_search_evaluation_count += 1
                        row = (
                            trial_penalty,
                            direction_index,
                            backtracking_index,
                            trial,
                            trial_shift,
                            total_rotation_vector,
                            total_rotation_path_radians,
                        )
                        if best is None or row[:3] < best[:3]:
                            best = row
                        step_size *= 0.5

            required_reduction = max(
                self._config.penalty_tolerance,
                abs(penalty) * 1.0e-12,
            )
            translation_improves = bool(
                best is not None
                and best[0] <= penalty - required_reduction
            )
            torque = self._rotation_torque(coordinates)
            torque_norm = float(torch.linalg.vector_norm(torque).item())
            if (
                not translation_improves
                and torque_norm > self._config.epsilon_angstrom
                and remaining_rotation > self._config.minimum_rotation_step_radians
                and accepted_rotation_steps < self._config.maximum_rotation_steps
            ):
                rotation_axis = torque / torque_norm
                rotation_required_reduction = max(
                    required_reduction,
                    abs(penalty)
                    * self._config.minimum_rotation_relative_penalty_reduction,
                )
                angle = min(
                    self._config.maximum_rotation_step_radians,
                    remaining_rotation,
                )
                for backtracking_index in range(
                    self._config.maximum_backtracking_evaluations
                ):
                    if angle < self._config.minimum_rotation_step_radians:
                        break
                    rotation_step = rotation_axis * angle
                    trial = self._rotate_about_centroid(
                        coordinates,
                        rotation_step,
                    )
                    trial_penalty, _ = self._penalty_and_direction(trial)
                    line_search_evaluation_count += 1
                    row = (
                        trial_penalty,
                        2,
                        backtracking_index,
                        trial,
                        total_shift,
                        total_rotation_vector + rotation_step,
                        total_rotation_path_radians + angle,
                    )
                    if (
                        trial_penalty
                        <= penalty - rotation_required_reduction
                        and (best is None or row[:3] < best[:3])
                    ):
                        best = row
                    angle *= 0.5

            if best is None or best[0] > penalty - required_reduction:
                break
            coordinates = best[3]
            total_shift = best[4]
            total_rotation_vector = best[5]
            total_rotation_path_radians = best[6]
            accepted_steps += 1
            accepted_rotation_steps += int(best[1] == 2)
            fallback_direction_step_count += int(best[1] == 1)

        final_penalty, _ = self._penalty_and_direction(coordinates)
        final_centroid_offset = float(
            torch.linalg.vector_norm(
                coordinates.mean(dim=0) - self._pocket_center
            ).item()
        )
        receipt: dict[str, object] = {
            "schema_id": (
                "betelgeuze.engine_v2_interaction_aware_rigid_refinement_receipt/3.0.0"
            ),
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self._config.fingerprint_sha256,
            "initial_penalty_binary64_hex": initial_penalty.hex(),
            "final_penalty_binary64_hex": final_penalty.hex(),
            "accepted_steps": accepted_steps,
            "accepted_translation_steps": (
                accepted_steps - accepted_rotation_steps
            ),
            "accepted_rotation_steps": accepted_rotation_steps,
            "line_search_evaluation_count": line_search_evaluation_count,
            "fallback_direction_step_count": fallback_direction_step_count,
            "original_pose_valid": original_valid,
            "total_translation_binary64_hex": [
                float(value).hex() for value in total_shift
            ],
            "total_rotation_vector_binary64_hex": [
                float(value).hex() for value in total_rotation_vector
            ],
            "total_rotation_path_radians_binary64_hex": (
                total_rotation_path_radians.hex()
            ),
            "initial_centroid_offset_angstrom_binary64_hex": (
                initial_centroid_offset.hex()
            ),
            "final_centroid_offset_angstrom_binary64_hex": (
                final_centroid_offset.hex()
            ),
            "maximum_centroid_offset_angstrom_binary64_hex": (
                self._maximum_centroid_offset_angstrom.hex()
            ),
            "pre_coordinates_sha256": coordinate_fingerprint(proposal.coordinates),
            "post_coordinates_sha256": coordinate_fingerprint(coordinates),
            "ranking_score_reused_as_physical_energy": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            coordinates.to(dtype=proposal.coordinates.dtype),
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=proposal.torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


class InteractionAwareRigidEnsembleRefinerV4:
    """Preserve V2 originals while applying V3 only to receipt-bound variants."""

    refiner_id = INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_ID
    refiner_version = INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_VERSION
    ensemble_config_schema_id = (
        INTERACTION_AWARE_RIGID_ENSEMBLE_CONFIG_V4_SCHEMA_ID
    )
    receipt_schema_id = INTERACTION_AWARE_RIGID_ENSEMBLE_RECEIPT_V4_SCHEMA_ID

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        v3_proposal_indices: tuple[int, ...],
        v2_config: InteractionAwareRigidConfigV2 | None = None,
        v3_config: InteractionAwareRigidConfigV3 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        indices = tuple(v3_proposal_indices)
        if any(
            type(index) is not int or not 0 <= index <= 127
            for index in indices
        ) or len(indices) != len(set(indices)):
            raise ClashReliefRefinementError(
                "V3 ensemble proposal indices must be unique integers in [0,127]"
            )
        if indices != tuple(sorted(indices)):
            raise ClashReliefRefinementError(
                "V3 ensemble proposal indices must be sorted"
            )
        self._v2 = InteractionAwareRigidRefinerV2(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=v2_config,
            radii_policy=radii_policy,
        )
        self._v3 = InteractionAwareRigidRefinerV3(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=v3_config,
            radii_policy=radii_policy,
        )
        self._v3_proposal_indices = indices
        self._v3_proposal_index_set = frozenset(indices)
        self._implementation_source_sha256 = implementation_source_sha256
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "schema_id": self.ensemble_config_schema_id,
                "v2_component_config_sha256": self._v2.config_fingerprint_sha256,
                "v3_component_config_sha256": self._v3.config_fingerprint_sha256,
                "v3_proposal_indices": list(indices),
                "source_lane_retained": True,
                "scientifically_validated": False,
            }
        )
        self._receipts: dict[str, Mapping[str, object]] = {}

    @property
    def problem_fingerprint_sha256(self) -> str:
        observed = self._v2.problem_fingerprint_sha256
        if observed != self._v3.problem_fingerprint_sha256:
            raise ClashReliefRefinementError("ensemble refiner is cross-wired")
        return observed

    @property
    def config_fingerprint_sha256(self) -> str:
        return self._component_config_fingerprint_sha256

    @property
    def implementation_source_sha256(self) -> str:
        if (
            self._v2.implementation_source_sha256
            != self._implementation_source_sha256
            or self._v3.implementation_source_sha256
            != self._implementation_source_sha256
        ):
            raise ClashReliefRefinementError(
                "ensemble refiner implementation identity changed"
            )
        return self._implementation_source_sha256

    @property
    def v3_proposal_indices(self) -> tuple[int, ...]:
        return self._v3_proposal_indices

    @property
    def receipts(self) -> Mapping[str, Mapping[str, object]]:
        return MappingProxyType(dict(self._receipts))

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.fingerprint_sha256 in self._receipts:
            raise ClashReliefRefinementError("proposal was already refined")
        use_v3 = proposal.proposal_index in self._v3_proposal_index_set
        lane = "translation_rotation_v3" if use_v3 else "translation_v2"
        nested_refiner = self._v3 if use_v3 else self._v2
        nested = nested_refiner.refine(proposal, max_steps=max_steps)
        nested_receipt = nested_refiner.receipts[proposal.fingerprint_sha256]
        zero_rotation = [0.0.hex(), 0.0.hex(), 0.0.hex()]
        receipt: dict[str, object] = {
            "schema_id": self.receipt_schema_id,
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self.config_fingerprint_sha256,
            "lane": lane,
            "v3_proposal_indices": list(self._v3_proposal_indices),
            "nested_refiner_id": nested_refiner.refiner_id,
            "nested_refiner_version": nested_refiner.refiner_version,
            "nested_receipt_sha256": nested_receipt["receipt_sha256"],
            "initial_penalty_binary64_hex": nested_receipt[
                "initial_penalty_binary64_hex"
            ],
            "final_penalty_binary64_hex": nested_receipt[
                "final_penalty_binary64_hex"
            ],
            "accepted_steps": nested_receipt["accepted_steps"],
            "accepted_translation_steps": nested_receipt.get(
                "accepted_translation_steps",
                nested_receipt["accepted_steps"],
            ),
            "accepted_rotation_steps": nested_receipt.get(
                "accepted_rotation_steps",
                0,
            ),
            "line_search_evaluation_count": nested_receipt.get(
                "line_search_evaluation_count",
                0,
            ),
            "fallback_direction_step_count": nested_receipt.get(
                "fallback_direction_step_count",
                0,
            ),
            "original_pose_valid": nested_receipt["original_pose_valid"],
            "total_translation_binary64_hex": nested_receipt[
                "total_translation_binary64_hex"
            ],
            "total_rotation_vector_binary64_hex": nested_receipt.get(
                "total_rotation_vector_binary64_hex",
                zero_rotation,
            ),
            "pre_coordinates_sha256": nested_receipt["pre_coordinates_sha256"],
            "post_coordinates_sha256": nested_receipt["post_coordinates_sha256"],
            "ranking_score_reused_as_physical_energy": False,
            "source_lane_retained": True,
            "scientifically_validated": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            nested.coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=nested.torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


class InteractionAwareRigidClearanceEnsembleRefinerV5(
    InteractionAwareRigidEnsembleRefinerV4
):
    """Apply expanded clearance only to variants whose V2 sources remain retained."""

    refiner_id = INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_ID
    refiner_version = (
        INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_VERSION
    )
    ensemble_config_schema_id = (
        INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_CONFIG_V5_SCHEMA_ID
    )
    receipt_schema_id = (
        INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_RECEIPT_V5_SCHEMA_ID
    )

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        v3_proposal_indices: tuple[int, ...],
        v2_config: InteractionAwareRigidConfigV2 | None = None,
        v3_config: InteractionAwareRigidConfigV3 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            v2_config=v2_config,
            v3_config=(v3_config or InteractionAwareRigidClearanceConfigV4()),
            radii_policy=radii_policy,
        )


class InteractionAwareRigidHybridClearanceEnsembleRefinerV6(
    InteractionAwareRigidEnsembleRefinerV4
):
    """Rescue only duplicate or receipt-bound near-clear V3 variants."""

    refiner_id = INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_ID
    refiner_version = INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_VERSION
    ensemble_config_schema_id = (
        INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_CONFIG_V6_SCHEMA_ID
    )
    receipt_schema_id = (
        INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_RECEIPT_V6_SCHEMA_ID
    )

    def __init__(
        self,
        authority: AuthenticatedDockingProblem,
        receptor_system: AllAtomSystem,
        ligand_system: AllAtomSystem,
        *,
        implementation_source_sha256: str,
        v3_proposal_indices: tuple[int, ...],
        v2_config: InteractionAwareRigidConfigV2 | None = None,
        v3_config: InteractionAwareRigidConfigV3 | None = None,
        clearance_config: InteractionAwareRigidConfigV3 | None = None,
        radii_policy: VdwContactPolicy | None = None,
    ) -> None:
        super().__init__(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            v3_proposal_indices=v3_proposal_indices,
            v2_config=v2_config,
            v3_config=v3_config,
            radii_policy=radii_policy,
        )
        selected_clearance = (
            clearance_config or InteractionAwareRigidClearanceConfigV4()
        )
        self._clearance_v3 = InteractionAwareRigidRefinerV3(
            authority,
            receptor_system,
            ligand_system,
            implementation_source_sha256=implementation_source_sha256,
            config=selected_clearance,
            radii_policy=radii_policy,
        )
        baseline_config_sha256 = self._component_config_fingerprint_sha256
        self._component_config_fingerprint_sha256 = _sha256(
            {
                "schema_id": self.ensemble_config_schema_id,
                "baseline_ensemble_config_sha256": baseline_config_sha256,
                "clearance_component_config_sha256": (
                    self._clearance_v3.config_fingerprint_sha256
                ),
                "near_clear_penalty_binary64_hex": (
                    INTERACTION_AWARE_RIGID_HYBRID_NEAR_CLEAR_PENALTY.hex()
                ),
                "selection_policy": (
                    "v2_duplicate_or_near_clear_clearance_objective_reduction"
                ),
                "source_lane_retained": True,
                "scientifically_validated": False,
            }
        )

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        proposal.assert_integrity()
        if proposal.proposal_index not in self._v3_proposal_index_set:
            return super().refine(proposal, max_steps=max_steps)
        if proposal.fingerprint_sha256 in self._receipts:
            raise ClashReliefRefinementError("proposal was already refined")

        comparison_v2 = self._v2.refine(proposal, max_steps=max_steps)
        baseline_v3 = self._v3.refine(proposal, max_steps=max_steps)
        comparison_receipt = self._v2.receipts[proposal.fingerprint_sha256]
        baseline_receipt = self._v3.receipts[proposal.fingerprint_sha256]
        baseline_duplicate = bool(
            coordinate_fingerprint(comparison_v2.coordinates)
            == coordinate_fingerprint(baseline_v3.coordinates)
        )
        baseline_penalty = float.fromhex(
            str(baseline_receipt["final_penalty_binary64_hex"])
        )
        clearance_evaluated = bool(
            baseline_duplicate
            or baseline_penalty
            <= INTERACTION_AWARE_RIGID_HYBRID_NEAR_CLEAR_PENALTY
        )
        clearance_receipt: Mapping[str, object] | None = None
        clearance_initial_penalty: float | None = None
        clearance_penalty: float | None = None
        clearance_selected = False
        selected = baseline_v3
        selected_refiner = self._v3
        selected_receipt = baseline_receipt
        selection_reason = "baseline_v3_retained"
        if clearance_evaluated:
            clearance = self._clearance_v3.refine(
                proposal,
                max_steps=max_steps,
            )
            clearance_receipt = self._clearance_v3.receipts[
                proposal.fingerprint_sha256
            ]
            clearance_initial_penalty = float.fromhex(
                str(clearance_receipt["initial_penalty_binary64_hex"])
            )
            clearance_penalty = float.fromhex(
                str(clearance_receipt["final_penalty_binary64_hex"])
            )
            clearance_selected = bool(
                baseline_duplicate
                or clearance_penalty < clearance_initial_penalty
            )
            if clearance_selected:
                selected = clearance
                selected_refiner = self._clearance_v3
                selected_receipt = clearance_receipt
                selection_reason = (
                    "v2_duplicate_clearance_rescue"
                    if baseline_duplicate
                    else "near_clear_clearance_objective_reduction"
                )

        zero_rotation = [0.0.hex(), 0.0.hex(), 0.0.hex()]
        receipt: dict[str, object] = {
            "schema_id": self.receipt_schema_id,
            "source_proposal_sha256": proposal.fingerprint_sha256,
            "config_sha256": self.config_fingerprint_sha256,
            "lane": (
                "translation_rotation_v5_clearance_rescue"
                if clearance_selected
                else "translation_rotation_v3"
            ),
            "selection_reason": selection_reason,
            "v3_proposal_indices": list(self._v3_proposal_indices),
            "comparison_v2_receipt_sha256": comparison_receipt[
                "receipt_sha256"
            ],
            "baseline_v3_receipt_sha256": baseline_receipt["receipt_sha256"],
            "clearance_receipt_sha256": (
                ""
                if clearance_receipt is None
                else clearance_receipt["receipt_sha256"]
            ),
            "baseline_duplicate_of_v2_refinement": baseline_duplicate,
            "baseline_final_penalty_binary64_hex": baseline_penalty.hex(),
            "clearance_evaluated": clearance_evaluated,
            "clearance_initial_penalty_binary64_hex": (
                ""
                if clearance_initial_penalty is None
                else clearance_initial_penalty.hex()
            ),
            "clearance_final_penalty_binary64_hex": (
                "" if clearance_penalty is None else clearance_penalty.hex()
            ),
            "clearance_selected": clearance_selected,
            "near_clear_penalty_binary64_hex": (
                INTERACTION_AWARE_RIGID_HYBRID_NEAR_CLEAR_PENALTY.hex()
            ),
            "nested_refiner_id": selected_refiner.refiner_id,
            "nested_refiner_version": selected_refiner.refiner_version,
            "nested_receipt_sha256": selected_receipt["receipt_sha256"],
            "initial_penalty_binary64_hex": selected_receipt[
                "initial_penalty_binary64_hex"
            ],
            "final_penalty_binary64_hex": selected_receipt[
                "final_penalty_binary64_hex"
            ],
            "accepted_steps": selected_receipt["accepted_steps"],
            "accepted_translation_steps": selected_receipt.get(
                "accepted_translation_steps",
                selected_receipt["accepted_steps"],
            ),
            "accepted_rotation_steps": selected_receipt.get(
                "accepted_rotation_steps",
                0,
            ),
            "line_search_evaluation_count": selected_receipt.get(
                "line_search_evaluation_count",
                0,
            ),
            "fallback_direction_step_count": selected_receipt.get(
                "fallback_direction_step_count",
                0,
            ),
            "original_pose_valid": selected_receipt["original_pose_valid"],
            "total_translation_binary64_hex": selected_receipt[
                "total_translation_binary64_hex"
            ],
            "total_rotation_vector_binary64_hex": selected_receipt.get(
                "total_rotation_vector_binary64_hex",
                zero_rotation,
            ),
            "pre_coordinates_sha256": selected_receipt[
                "pre_coordinates_sha256"
            ],
            "post_coordinates_sha256": selected_receipt[
                "post_coordinates_sha256"
            ],
            "ranking_score_reused_as_physical_energy": False,
            "source_lane_retained": True,
            "scientifically_validated": False,
        }
        receipt_sha256 = _sha256(receipt)
        receipt["receipt_sha256"] = receipt_sha256
        refined = proposal.with_refined_coordinates(
            selected.coordinates,
            refiner_id=self.refiner_id,
            refiner_version=self.refiner_version,
            refinement_receipt_sha256=receipt_sha256,
            torsion_angles=selected.torsion_angles,
        )
        self._receipts[proposal.fingerprint_sha256] = MappingProxyType(receipt)
        return refined


__all__ = [
    "CLASH_RELIEF_CONFIG_SCHEMA_ID",
    "CLASH_RELIEF_REFINER_ID",
    "CLASH_RELIEF_REFINER_VERSION",
    "INTERACTION_AWARE_RIGID_CONFIG_V2_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_CONFIG_V3_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_CLEARANCE_CONFIG_V4_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_CONFIG_V5_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_RECEIPT_V5_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_ID",
    "INTERACTION_AWARE_RIGID_CLEARANCE_ENSEMBLE_REFINER_V5_VERSION",
    "INTERACTION_AWARE_RIGID_ENSEMBLE_CONFIG_V4_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_CONFIG_V6_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_RECEIPT_V6_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_ID",
    "INTERACTION_AWARE_RIGID_HYBRID_ENSEMBLE_REFINER_V6_VERSION",
    "INTERACTION_AWARE_RIGID_HYBRID_NEAR_CLEAR_PENALTY",
    "INTERACTION_AWARE_RIGID_ENSEMBLE_RECEIPT_V4_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_ID",
    "INTERACTION_AWARE_RIGID_ENSEMBLE_REFINER_V4_VERSION",
    "INTERACTION_AWARE_RIGID_REFINER_V2_ID",
    "INTERACTION_AWARE_RIGID_REFINER_V2_VERSION",
    "INTERACTION_AWARE_RIGID_REFINER_V3_ID",
    "INTERACTION_AWARE_RIGID_REFINER_V3_VERSION",
    "ClashReliefConfig",
    "ClashReliefRefinementError",
    "InteractionAwareRigidClearanceConfigV4",
    "InteractionAwareRigidClearanceEnsembleRefinerV5",
    "InteractionAwareRigidHybridClearanceEnsembleRefinerV6",
    "InteractionAwareRigidConfigV2",
    "InteractionAwareRigidConfigV3",
    "InteractionAwareRigidRefinerV2",
    "InteractionAwareRigidRefinerV3",
    "InteractionAwareRigidEnsembleRefinerV4",
    "ReceptorClashReliefRefiner",
]
