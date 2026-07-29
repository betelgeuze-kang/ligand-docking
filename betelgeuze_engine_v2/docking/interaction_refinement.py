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
    """Rigid vdW-contact optimizer with bounded deterministic line search."""

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


__all__ = [
    "CLASH_RELIEF_CONFIG_SCHEMA_ID",
    "CLASH_RELIEF_REFINER_ID",
    "CLASH_RELIEF_REFINER_VERSION",
    "INTERACTION_AWARE_RIGID_CONFIG_V2_SCHEMA_ID",
    "INTERACTION_AWARE_RIGID_REFINER_V2_ID",
    "INTERACTION_AWARE_RIGID_REFINER_V2_VERSION",
    "ClashReliefConfig",
    "ClashReliefRefinementError",
    "InteractionAwareRigidConfigV2",
    "InteractionAwareRigidRefinerV2",
    "ReceptorClashReliefRefiner",
]
