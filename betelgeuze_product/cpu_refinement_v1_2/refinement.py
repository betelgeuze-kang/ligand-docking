"""Authenticated candidate adapter for corrected extended CPU minimization."""
from __future__ import annotations

from dataclasses import dataclass, replace
import json

import torch

from betelgeuze_engine_v2.contracts import failure_receipt
from betelgeuze_engine_v2.docking import energy_refinement as legacy
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import _constraint_observations
from .evaluation import make_evaluator
from .fixed_receptor import FIXED_ATTEMPT_SCHEMA
from .minimization import ALGORITHM_ID, SolverConfig, minimize_extended
from .provenance import ResearchError, canonical, coordinates_hex, digest, require_digest

from .work import WorkMeter


@dataclass(frozen=True)
class RefinementConfig(legacy.EnergyLocalRefinementConfig):
    solver: SolverConfig | None = None
    evaluator_fingerprint_sha256: str = ""
    fixed_receptor: bool = False

    def __post_init__(self) -> None:
        if type(self.solver) is not SolverConfig or self.minimization != self.solver.minimization:
            raise ResearchError("refiner solver/step configuration mismatch")
        if type(self.fixed_receptor) is not bool:
            raise ResearchError("exact fixed-receptor scope flag required")
        require_digest(self.evaluator_fingerprint_sha256)
        legacy.EnergyLocalRefinementConfig.__post_init__(self)

    def _projection(self) -> dict:
        row = legacy.EnergyLocalRefinementConfig._projection(self)
        row.update(algorithm_id="authenticated_corrected_extended_refiner/1.2.0",
                   reference_minimization_algorithm_id=ALGORITHM_ID,
                   solver=self.solver.to_dict(), evaluator_fingerprint_sha256=self.evaluator_fingerprint_sha256,
                   input_constraint_policy="reject_candidates_not_already_on_constraint_surface")
        if self.fixed_receptor:
            row["algorithm_id"] = "authenticated_fixed_receptor_refiner/1.0.0"
        return row


@dataclass(frozen=True)
class Attempt:
    _json: str
    _work_json: str

    @property
    def receipt_sha256(self) -> str:
        return digest(json.loads(self._json))

    def to_dict(self) -> dict:
        return {**json.loads(self._json), "receipt_sha256": self.receipt_sha256}

    def work(self) -> dict:
        return json.loads(self._work_json)


class ExtendedRefiner(legacy.EnergyBasedLocalRefiner):
    """Reuse authority/proposal checks and rotor bookkeeping, not legacy numerics."""
    refiner_id = "cpu_corrected_extended_refiner"
    refiner_version = "1.2.0"

    def __init__(self, authority, ligand, parameters, solver, *, implementation_source_sha256,
                 solvation=None, max_attempts=256, fixed_environment=None):
        self._fixed_environment = fixed_environment
        self._extended_evaluator = make_evaluator(parameters, solvation, fixed_environment)
        if fixed_environment is not None and (
            fixed_environment.parameters.receptor_system_sha256 != authority.receptor_system_sha256
            or fixed_environment.parameters.coordinate_frame_id != authority.problem.coordinate_frame_id
        ):
            raise ResearchError("refinement fixed receptor or coordinate frame differs from search authority")
        if fixed_environment is not None:
            self.refiner_id = "cpu_fixed_receptor_refiner"
            self.refiner_version = "1.0.0"
            fixed_environment.validate_ligand(ligand, parameters.base_parameters)
        self._solver = solver
        selected = RefinementConfig(minimization=solver.minimization, max_attempts=max_attempts,
            solver=solver, evaluator_fingerprint_sha256=self._extended_evaluator.fingerprint_sha256,
            fixed_receptor=fixed_environment is not None)
        super().__init__(authority, ligand, parameters.base_parameters,
                         implementation_source_sha256=implementation_source_sha256, config=selected)

    def assert_ready(self) -> None:
        super().assert_ready()
        if self._extended_evaluator.fingerprint_sha256 != self._config.evaluator_fingerprint_sha256:
            raise ResearchError("extended refiner parameters changed")

    def refine(self, proposal, *, max_steps):
        steps = self._assert_inputs(proposal, max_steps)
        if proposal.fingerprint_sha256 in self._attempts:
            raise ResearchError("proposal already refined")
        self.assert_ready()
        before = proposal.coordinates.detach().clone()
        identity = self._extended_evaluator.identity()
        solver = replace(self._solver, minimization=replace(self._solver.minimization, max_iterations=steps))
        payload = {"schema_id": FIXED_ATTEMPT_SCHEMA if self._fixed_environment is not None else "cpu_extended_refinement_attempt/1.2.0",
                   "candidate_id": proposal.candidate_id, "proposal_index": proposal.proposal_index,
                   "source_proposal_fingerprint_sha256": proposal.fingerprint_sha256,
                   "pre_coordinates_sha256": coordinate_fingerprint(before),
                   "pre_coordinates_binary64_hex": coordinates_hex(before),
                   "evaluator": identity, "solver": solver.to_dict(),
                   "implementation_source_sha256": self.implementation_source_sha256}
        meter = WorkMeter()
        try:
            source = self._ligand_system.with_coordinates(before.unsqueeze(0), operation="extended_refinement_input")
            constraints = _constraint_observations(source.coordinates, source, self._extended_evaluator.parameters.constraints)
            if not all(row.satisfied for row in constraints):
                raise ResearchError("candidate is not on the declared constraint surface")
            result = minimize_extended(source, self._extended_evaluator.parameters, solver,
                                       solvation=self._extended_evaluator.solvation, meter=meter,
                                       fixed_environment=self._fixed_environment)
            state = result.checkpoint.to_dict()
            after = result.system.coordinates[0].detach().clone()
            displacement = float(torch.linalg.vector_norm(after - before, dim=-1).max())
            if displacement > steps * solver.minimization.maximum_atom_displacement_angstrom + 1.e-10:
                raise ResearchError("candidate displacement exceeds reserved step bound")
            payload.update(status="success", post_coordinates_sha256=coordinate_fingerprint(after),
                post_coordinates_binary64_hex=coordinates_hex(after),
                initial_energy=state["initial_energy"], final_energy=state["current_energy"],
                energy_delta=state["current_energy"] - state["initial_energy"],
                maximum_displacement_angstrom=displacement, converged=result.converged,
                minimization_status=result.status, max_tangent_force=state["current_max_tangent_force"],
                max_constraint_residual=state["current_constraint_residual"],
                accepted_iterations=state["accepted_iterations"], evaluation_count=state["evaluation_count"],
                checkpoint_sha256=result.checkpoint.checkpoint_sha256)
            if self._fixed_environment is not None:
                payload.update(initial_objective_components=state["initial_objective_components"],
                               final_objective_components=state["current_objective_components"])
            work = dict(result.execution)
            attempt = Attempt(canonical(payload), canonical(work))
            refined = proposal.with_refined_coordinates(after, refiner_id=self.refiner_id,
                refiner_version=self.refiner_version, refinement_receipt_sha256=attempt.receipt_sha256,
                torsion_angles=self._torsion_angles_for(after))
            self.assert_ready()
            self._attempts[proposal.fingerprint_sha256] = attempt
            return refined
        except Exception as exc:
            receipt = failure_receipt(exc, public_message="corrected extended refinement failed")
            # Never retain a partially successful numerical result as success.
            failed = {key: value for key, value in payload.items()
                      if key in {"schema_id", "candidate_id", "proposal_index", "source_proposal_fingerprint_sha256",
                                 "pre_coordinates_sha256", "pre_coordinates_binary64_hex", "evaluator", "solver",
                                 "implementation_source_sha256"}}
            failed.update(status="failure", public_error_code=receipt.public_error_code,
                          private_error_sha256=receipt.private_error_sha256,
                          private_error_byte_length=receipt.private_error_byte_length)
            self._attempts[proposal.fingerprint_sha256] = Attempt(canonical(failed), canonical(meter.numerical_calls()))
            raise ResearchError("corrected extended refinement failed") from exc
