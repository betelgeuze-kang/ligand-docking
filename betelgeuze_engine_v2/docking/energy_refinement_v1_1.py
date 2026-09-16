"""Opt-in 1.1 ligand-internal refiner, reusing authenticated search contracts.

The 1.0 adapter and frozen protocols remain unchanged. Configuration, attempt
receipts and component version explicitly identify this minimizer. No global
function replacement, checkpoint migration, receptor interaction minimization,
product-routing change or validation promotion is performed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.physics.reference_minimization_v1_1 import (
    REFERENCE_MINIMIZATION_ALGORITHM_ID, ReferenceMinimizationConfig,
    minimize_reference_force_field,
)
from . import energy_refinement as legacy
from .energy_refinement import EnergyRefinementError, _coordinate_hex
from .identity import coordinate_fingerprint
from .proposals import DockingProposal

ENERGY_REFINER_ALGORITHM_ID = "authenticated_ligand_internal_reference_forcefield_bounded_minimization/1.1.0"


@dataclass(frozen=True, slots=True)
class EnergyLocalRefinementConfig(legacy.EnergyLocalRefinementConfig):
    minimization: ReferenceMinimizationConfig = field(default_factory=ReferenceMinimizationConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.minimization, ReferenceMinimizationConfig):
            raise TypeError("1.1 refinement requires explicit 1.1 minimization config")
        legacy.EnergyLocalRefinementConfig.__post_init__(self)

    def _projection(self) -> dict[str, object]:
        row = legacy.EnergyLocalRefinementConfig._projection(self)
        row["algorithm_id"] = ENERGY_REFINER_ALGORITHM_ID
        row["reference_minimization_algorithm_id"] = REFERENCE_MINIMIZATION_ALGORITHM_ID
        return row


class EnergyRefinementAttempt(legacy.EnergyRefinementAttempt):
    def _projection(self) -> dict[str, object]:
        row = legacy.EnergyRefinementAttempt._projection(self)
        row["algorithm_id"] = ENERGY_REFINER_ALGORITHM_ID
        row["reference_minimization_algorithm_id"] = REFERENCE_MINIMIZATION_ALGORITHM_ID
        return row


class EnergyBasedLocalRefiner(legacy.EnergyBasedLocalRefiner):
    refiner_version = "1.1.0"

    def __init__(self, authority, ligand_system, parameters, *, implementation_source_sha256,
                 config: EnergyLocalRefinementConfig | None = None):
        selected = EnergyLocalRefinementConfig() if config is None else config
        if not isinstance(selected, EnergyLocalRefinementConfig):
            raise TypeError("1.1 refiner requires explicit 1.1 refinement config")
        super().__init__(authority, ligand_system, parameters,
                         implementation_source_sha256=implementation_source_sha256, config=selected)

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        steps = self._assert_inputs(proposal, max_steps)
        if proposal.fingerprint_sha256 in self._attempts:
            raise EnergyRefinementError("proposal refinement was already attempted")
        pre_coordinates = (
            proposal.coordinates.detach()
            .to(dtype=torch.float64, device="cpu")
            .clone()
            .contiguous()
        )
        effective_config = replace(
            self._config.minimization,
            max_iterations=steps,
        )
        common = {
            "candidate_id": proposal.candidate_id,
            "proposal_index": proposal.proposal_index,
            "source_proposal_fingerprint_sha256": proposal.fingerprint_sha256,
            "authority_input_receipt_sha256": self._authority.input_receipt_sha256,
            "ligand_system_sha256": self._authority.ligand_system_sha256,
            "parameter_fingerprint_sha256": self._parameter_fingerprint_sha256,
            "parameter_set_id": self._parameters.parameter_set_id,
            "parameter_set_version": self._parameters.parameter_set_version,
            "implementation_source_sha256": self._implementation_source_sha256,
            "refiner_config_fingerprint_sha256": self._config.fingerprint_sha256,
            "effective_minimization_config_fingerprint_sha256": (
                effective_config.fingerprint_sha256
            ),
            "max_steps": steps,
            "maximum_atom_displacement_per_step_angstrom": (
                effective_config.maximum_atom_displacement_angstrom
            ),
            "pre_coordinates_sha256": coordinate_fingerprint(pre_coordinates),
            "pre_coordinates_binary64_hex": _coordinate_hex(pre_coordinates),
        }
        try:
            source = self._ligand_system.with_coordinates(
                pre_coordinates.unsqueeze(0),
                operation="docking_energy_local_refinement_input",
            )
            result = minimize_reference_force_field(
                source,
                self._parameters,
                effective_config,
            )
            post_coordinates = (
                result.system.coordinates[0]
                .detach()
                .to(dtype=torch.float64, device="cpu")
                .clone()
                .contiguous()
            )
            maximum_displacement = float(
                torch.linalg.vector_norm(
                    post_coordinates - pre_coordinates,
                    dim=-1,
                )
                .max()
                .item()
            )
            attempt = EnergyRefinementAttempt(
                **common,
                status="success",
                post_coordinates_sha256=coordinate_fingerprint(post_coordinates),
                post_coordinates_binary64_hex=_coordinate_hex(post_coordinates),
                initial_energy_kcal_per_mol=result.initial_energy_kcal_per_mol,
                final_energy_kcal_per_mol=result.final_energy_kcal_per_mol,
                energy_delta_kcal_per_mol=(
                    result.final_energy_kcal_per_mol
                    - result.initial_energy_kcal_per_mol
                ),
                maximum_displacement_angstrom=maximum_displacement,
                minimization_status=result.status,
                minimization_failure_code=str(result.failure_code or ""),
                converged=result.converged,
                accepted_iterations=result.accepted_iterations,
                rejected_evaluations=result.rejected_evaluations,
                evaluation_count=result.evaluation_count,
                checkpoint_sha256=result.checkpoint.checkpoint_sha256,
            )
            refined = proposal.with_refined_coordinates(
                post_coordinates.to(dtype=proposal.coordinates.dtype),
                refiner_id=self.refiner_id,
                refiner_version=self.refiner_version,
                refinement_receipt_sha256=attempt.receipt_sha256,
                torsion_angles=self._torsion_angles_for(post_coordinates),
            )
            self._attempts[proposal.fingerprint_sha256] = attempt
            self._assert_inputs(proposal, steps)
            return refined
        except Exception as exc:
            receipt = failure_receipt(
                exc,
                public_message="energy-based local refinement failed",
            )
            attempt = EnergyRefinementAttempt(
                **common,
                status="failure",
                public_error_code=receipt.public_error_code,
                private_error_sha256=receipt.private_error_sha256,
                private_error_byte_length=receipt.private_error_byte_length,
            )
            self._attempts[proposal.fingerprint_sha256] = attempt
            if isinstance(exc, EnergyRefinementError):
                raise
            raise EnergyRefinementError("energy-based local refinement failed") from exc
