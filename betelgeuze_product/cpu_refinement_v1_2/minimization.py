"""One bounded projected descent loop for dry and fixed-Born corrected physics.

Historical solvers/checkpoints are untouched. Optimization-ledger identity is
separate from invocation work; resuming verifies the current state anew.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from typing import Mapping

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import AllAtomSystem, canonical_system_sha256
from betelgeuze_engine_v2.physics.reference_constrained_minimization import (
    ReferenceConstrainedMinimizationConfig as LegacyConstraintConfig,
    _validate_source_system,
)
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    DistanceConstraintProjectionConfig, ReferenceForceFieldV2ApplicabilityError,
    ReferenceForceFieldV2Parameters, project_distance_constraints,
)
from betelgeuze_engine_v2.physics.reference_solvation import (
    FixedBornPolarSolvationParameters, ReferenceFixedBornSolvationApplicabilityError,
)
from betelgeuze_product.cpu_refinement.reference_forcefield_v1_1 import ReferencePhysicsApplicabilityError
from betelgeuze_product.cpu_refinement.reference_minimization_v1_1 import (
    ReferenceMinimizationConfig, _config_from_document,
)
from .evaluation import ExtendedEvaluator
from .provenance import (
    ResearchError, canonical, coordinates_hex, decode_coordinates, digest,
    environment, exact_fields, finite, integer, require_digest, source_manifest,
)

from .work import WorkMeter
from .tangent_projection import project_tangent_forces as _project_forces_to_constraint_tangent

ALGORITHM_ID = "cpu_corrected_projected_descent/1.2.0"
CHECKPOINT_SCHEMA = "cpu_corrected_projected_checkpoint/1.2.0"
REJECTIONS = {"rejected_projection", "rejected_displacement", "rejected_applicability",
              "rejected_nonfinite", "rejected_tangent", "rejected_non_descent", "rejected_armijo"}
ROW_FIELDS = {"index", "iteration", "trial", "outcome", "coordinates_sha256",
              "projection_sha256", "step", "energy", "max_tangent_force", "constraint_residual"}
APPLICABILITY_ERRORS = (ReferencePhysicsApplicabilityError,
                       ReferenceForceFieldV2ApplicabilityError,
                       ReferenceFixedBornSolvationApplicabilityError)


@dataclass(frozen=True)
class SolverConfig:
    minimization: ReferenceMinimizationConfig = field(default_factory=ReferenceMinimizationConfig)
    constraint_projection: DistanceConstraintProjectionConfig = field(default_factory=DistanceConstraintProjectionConfig)
    force_projection_max_sweeps: int = 100
    force_projection_tolerance_kcal_per_mol_angstrom: float = 1.e-8

    def __post_init__(self) -> None:
        if type(self.minimization) is not ReferenceMinimizationConfig:
            raise ResearchError("explicit corrected 1.1 step configuration required")
        if type(self.constraint_projection) is not DistanceConstraintProjectionConfig:
            raise ResearchError("explicit distance projection configuration required")
        LegacyConstraintConfig(**vars(self))  # Reuse bounds, not its solver/identity.

    def to_dict(self) -> dict:
        return {"algorithm_id": ALGORITHM_ID, "minimization": self.minimization.to_dict(),
                "constraint_projection": self.constraint_projection.to_dict(),
                "force_projection_max_sweeps": self.force_projection_max_sweeps,
                "force_projection_tolerance_kcal_per_mol_angstrom":
                    self.force_projection_tolerance_kcal_per_mol_angstrom}

    @classmethod
    def from_dict(cls, value: object) -> "SolverConfig":
        exact_fields(value, set(cls().to_dict()))
        if value["algorithm_id"] != ALGORITHM_ID:
            raise ResearchError("solver algorithm identity mismatch")
        projection = dict(value["constraint_projection"])
        projection.pop("algorithm", None)
        result = cls(_config_from_document(value["minimization"]),
                     DistanceConstraintProjectionConfig(**projection),
                     value["force_projection_max_sweeps"],
                     value["force_projection_tolerance_kcal_per_mol_angstrom"])
        if canonical(result.to_dict()) != canonical(value):
            raise ResearchError("noncanonical solver configuration")
        return result


@dataclass(frozen=True)
class Checkpoint:
    """Immutable canonical bytes; callers never receive an internal mutable dict."""
    _json: str

    def to_dict(self) -> dict:
        return json.loads(self._json)

    @property
    def checkpoint_sha256(self) -> str:
        return self.to_dict()["checkpoint_sha256"]

    def coordinates(self) -> torch.Tensor:
        row = self.to_dict()
        return decode_coordinates(row["coordinates"], row["atom_count"])


def require_checkpoint(value: object) -> Checkpoint:
    if isinstance(value, Checkpoint):
        value = value.to_dict()
    names = {"schema_id", "algorithm_id", "source_system_sha256", "evaluator", "config",
             "implementation_sha256", "environment", "atom_count", "coordinates",
             "coordinates_sha256", "initial_energy", "initial_max_tangent_force",
             "current_energy", "current_max_tangent_force", "current_constraint_residual",
             "accepted_iterations", "evaluation_count", "status", "observations", "checkpoint_sha256"}
    exact_fields(value, names)
    if value["schema_id"] != CHECKPOINT_SCHEMA or value["algorithm_id"] != ALGORITHM_ID:
        raise ResearchError("checkpoint algorithm identity mismatch; no migration permitted")
    for name in ("source_system_sha256", "implementation_sha256", "coordinates_sha256", "checkpoint_sha256"):
        require_digest(value[name])
    projection = {k: v for k, v in value.items() if k != "checkpoint_sha256"}
    if digest(projection) != value["checkpoint_sha256"]:
        raise ResearchError("checkpoint digest mismatch")
    config = SolverConfig.from_dict(value["config"])
    n = integer(value["atom_count"], 1, 256)
    xyz = decode_coordinates(value["coordinates"], n)
    if digest(coordinates_hex(xyz)) != value["coordinates_sha256"]:
        raise ResearchError("checkpoint coordinate digest mismatch")
    maximum = config.minimization.max_iterations
    count = integer(value["evaluation_count"], 1,
                    1 + maximum * (config.minimization.max_backtracks + 1))
    accepted = integer(value["accepted_iterations"], 0, maximum)
    rows = value["observations"]
    if type(rows) is not list or len(rows) != count:
        raise ResearchError("checkpoint observation denominator mismatch")
    seen_accepted, next_trial = 0, 0
    current = None
    for i, row in enumerate(rows):
        exact_fields(row, ROW_FIELDS)
        if integer(row["index"], 1, count) != i + 1:
            raise ResearchError("checkpoint indices are not contiguous")
        for name in ("coordinates_sha256", "projection_sha256"):
            require_digest(row[name])
        finite(row["step"], nonnegative=True)
        finite(row["constraint_residual"], nonnegative=True)
        outcome = row["outcome"]
        if i == 0:
            if outcome != "initial" or type(row["iteration"]) is not int or row["iteration"] != 0 or row["trial"] != 0 or type(row["trial"]) is not int:
                raise ResearchError("checkpoint must begin with initial evaluation")
            if row["step"] != 0:
                raise ResearchError("initial step must be zero")
        else:
            if outcome not in REJECTIONS | {"accepted"}:
                raise ResearchError("unknown checkpoint outcome")
            if integer(row["iteration"], 1, maximum) != seen_accepted + 1:
                raise ResearchError("checkpoint iteration sequence mismatch")
            if integer(row["trial"], 0, config.minimization.max_backtracks) != next_trial:
                raise ResearchError("checkpoint backtracking sequence mismatch")
            expected_step = config.minimization.initial_step_size_angstrom2_mol_per_kcal
            for _ in range(next_trial):
                expected_step *= config.minimization.backtrack_factor
            if finite(row["step"]).hex() != float(expected_step).hex():
                raise ResearchError("checkpoint step does not match bounded backtracking")
            if outcome == "accepted":
                seen_accepted += 1
                next_trial = 0
            else:
                next_trial += 1
        has_values = outcome in {"initial", "accepted", "rejected_tangent", "rejected_non_descent", "rejected_armijo"}
        if has_values:
            finite(row["energy"])
            finite(row["max_tangent_force"], nonnegative=True)
        elif row["energy"] is not None or row["max_tangent_force"] is not None:
            raise ResearchError("failed observation fabricated energy or force")
        if outcome in {"initial", "accepted"}:
            if current is not None and row["energy"] > current["energy"]:
                raise ResearchError("accepted energy increased")
            current = row
    if seen_accepted != accepted or current is None:
        raise ResearchError("checkpoint accepted iteration mismatch")
    for field_name, row, row_name in (
        ("initial_energy", rows[0], "energy"),
        ("initial_max_tangent_force", rows[0], "max_tangent_force"),
        ("current_energy", current, "energy"),
        ("current_max_tangent_force", current, "max_tangent_force"),
        ("current_constraint_residual", current, "constraint_residual"),
    ):
        if finite(value[field_name]).hex() != finite(row[row_name]).hex():
            raise ResearchError("checkpoint summary does not match ledger")
    if current["coordinates_sha256"] != value["coordinates_sha256"]:
        raise ResearchError("checkpoint coordinates do not match accepted state")
    status = value["status"]
    force = finite(value["current_max_tangent_force"], nonnegative=True)
    tolerance = config.minimization.force_tolerance_kcal_per_mol_angstrom
    if status == "converged":
        valid = force <= tolerance and rows[-1]["outcome"] in {"initial", "accepted"}
    elif status == "checkpointed":
        valid = force > tolerance and accepted < maximum and rows[-1]["outcome"] in {"initial", "accepted"}
    elif status == "max_iterations_reached":
        valid = force > tolerance and accepted == maximum and rows[-1]["outcome"] == "accepted"
    elif status == "line_search_failed":
        valid = force > tolerance and accepted < maximum and next_trial == config.minimization.max_backtracks + 1
    else:
        valid = False
    if not valid:
        raise ResearchError("checkpoint termination status is inconsistent")
    return Checkpoint(canonical(value))


@dataclass(frozen=True)
class MinimizationResult:
    system: AllAtomSystem
    checkpoint: Checkpoint
    execution: Mapping[str, object]

    @property
    def status(self) -> str:
        return self.checkpoint.to_dict()["status"]

    @property
    def converged(self) -> bool:
        return self.status == "converged"

    def to_dict(self) -> dict:
        return {"schema_id": "cpu_corrected_minimization_result/1.2.0",
                "checkpoint": self.checkpoint.to_dict(), "execution": dict(self.execution),
                "converged": self.converged, "scientifically_validated": False,
                "claim_safe": False, "customer_execution_allowed": False}


def minimize_extended(
    system: AllAtomSystem,
    parameters: ReferenceForceFieldV2Parameters,
    config: SolverConfig | None = None,
    *,
    solvation: FixedBornPolarSolvationParameters | None = None,
    checkpoint: Checkpoint | Mapping | None = None,
    pause_after_accepted_iterations: int | None = None,
    meter: WorkMeter | None = None,
) -> MinimizationResult:
    return minimize_objective(system, ExtendedEvaluator(parameters, solvation), config,
                              checkpoint=checkpoint,
                              pause_after_accepted_iterations=pause_after_accepted_iterations, meter=meter)


def minimize_objective(system: AllAtomSystem, evaluator, config: SolverConfig | None = None, *,
                       checkpoint=None, pause_after_accepted_iterations=None, meter=None) -> MinimizationResult:
    """Shared solver for explicitly identified internal or fixed-environment objectives.

    The objective identity is retained in the existing source-bound checkpoint;
    no module-global replacement or historical checkpoint translation occurs.
    """
    from .cross_interaction import FixedReceptorEvaluator
    if type(evaluator) not in (ExtendedEvaluator, FixedReceptorEvaluator):
        raise ResearchError("supported explicitly identified evaluator required")
    parameters = evaluator.parameters
    config = SolverConfig() if config is None else config
    if type(config) is not SolverConfig:
        raise ResearchError("explicit 1.2 solver config required")
    _validate_source_system(system)
    if system.cell is not None or system.atom_count > 256:
        raise ResearchError("new solver supports nonperiodic systems of at most 256 atoms")
    initial_identity = evaluator.identity()
    source = canonical_system_sha256(system)
    meter = WorkMeter() if meter is None else meter
    if type(meter) is not WorkMeter or meter.snapshot()["stages"]:
        raise ResearchError("a fresh work meter is required for each minimization invocation")
    with meter.measure("implementation.verify"):
        implementation = digest(source_manifest())
    env = environment()
    minimum = config.minimization
    pause = None if pause_after_accepted_iterations is None else integer(
        pause_after_accepted_iterations, 0, minimum.max_iterations)
    def project(xyz):
        with meter.measure("constraint.project"):
            state = system.with_coordinates(xyz, operation="research_1_2_constraint_projection")
            result = project_distance_constraints(state, parameters, config.constraint_projection)
            return result, result.system.coordinates.detach().clone()

    def evaluate(xyz):
        state = system.with_coordinates(xyz, operation="research_1_2_evaluation")
        with meter.measure("geometry.build"):
            neighbors = build_compact_radius_graph(xyz, RadiusGraphConfig(
                cutoff_angstrom=parameters.base_parameters.cutoff_angstrom,
                max_neighbors=minimum.max_neighbors, max_atoms_per_cell=minimum.max_atoms_per_cell))
        with meter.measure("force.evaluate"):
            result = evaluator.evaluate(state, neighbors)
        energy = float(result.term.energy[0])
        with meter.measure("force.project"):
            tangent, force, _, sweeps, converged = _project_forces_to_constraint_tangent(
                system, xyz, result.term.forces, parameters, config)
            if not math.isfinite(force) or not bool(torch.isfinite(tangent).all()):
                raise FloatingPointError("nonfinite projected tangent force")
            meter.observe_tangent_projection(sweeps, converged)
        residual = max((abs(row.residual_angstrom) for row in result.constraint_observations), default=0.)
        return energy, tangent, force, residual, converged and result.constraints_satisfied

    def observation(index, iteration, trial, outcome, xyz, projection, step, energy=None, force=None):
        return {"index": index, "iteration": iteration, "trial": trial, "outcome": outcome,
                "coordinates_sha256": digest(coordinates_hex(xyz)),
                "projection_sha256": projection.projection_sha256, "step": step,
                "energy": energy, "max_tangent_force": force,
                "constraint_residual": projection.final_observation.max_absolute_residual_angstrom}

    if checkpoint is None:
        projection, xyz = project(system.coordinates.detach().clone())
        if not projection.converged:
            raise ResearchError("initial constraint projection failed")
        try:
            energy, forces, force, residual, tangent_ok = evaluate(xyz)
        except (*APPLICABILITY_ERRORS, FloatingPointError) as exc:
            raise ResearchError("initial corrected state is not evaluable") from exc
        if not tangent_ok:
            raise ResearchError("initial tangent projection or constraint satisfaction failed")
        rows = [observation(1, 0, 0, "initial", xyz, projection, 0., energy, force)]
        accepted = 0
    else:
        saved = require_checkpoint(checkpoint).to_dict()
        expected = {"source_system_sha256": source, "evaluator": initial_identity,
                    "implementation_sha256": implementation, "environment": env,
                    "config": config.to_dict(), "atom_count": system.atom_count}
        for key, value in expected.items():
            if canonical(saved[key]) != canonical(value):
                raise ResearchError(f"checkpoint {key} identity mismatch")
        if saved["status"] == "line_search_failed":
            raise ResearchError("terminal failed checkpoint cannot be resumed")
        xyz = decode_coordinates(saved["coordinates"], system.atom_count)
        projection, verification = project(xyz)
        if not projection.converged or not torch.equal(xyz, verification):
            raise ResearchError("checkpoint is not on the constraint surface")
        with meter.measure("restart.verify"):
            energy, forces, force, residual, tangent_ok = evaluate(xyz)
        if not tangent_ok or any(float(observed).hex() != float(saved[name]).hex()
            for observed, name in ((energy, "current_energy"), (force, "current_max_tangent_force"),
                                   (residual, "current_constraint_residual"))):
            raise ResearchError("checkpoint energy, tangent force or constraints do not reproduce")
        rows = saved["observations"]
        accepted = saved["accepted_iterations"]
    if pause is not None and pause < accepted:
        raise ResearchError("pause precedes checkpoint progress")
    status = "max_iterations_reached"
    while accepted < minimum.max_iterations:
        if force <= minimum.force_tolerance_kcal_per_mol_angstrom:
            status = "converged"
            break
        if pause is not None and accepted >= pause:
            status = "checkpointed"
            break
        direction = forces.clone()
        step = minimum.initial_step_size_angstrom2_mol_per_kcal
        displacement = step * force
        if displacement > minimum.maximum_atom_displacement_angstrom:
            direction *= minimum.maximum_atom_displacement_angstrom / displacement
        moved = False
        for trial in range(minimum.max_backtracks + 1):
            projection, trial_xyz = project(xyz + step * direction)
            outcome = "accepted"
            trial_energy = trial_force = None
            trial_forces = None
            if not projection.converged:
                outcome = "rejected_projection"
            elif float(torch.linalg.vector_norm(trial_xyz - xyz, dim=-1).max()) > minimum.maximum_atom_displacement_angstrom + 1.e-12:
                outcome = "rejected_displacement"
            else:
                try:
                    trial_energy, trial_forces, trial_force, trial_residual, tangent_ok = evaluate(trial_xyz)
                except APPLICABILITY_ERRORS:
                    outcome = "rejected_applicability"
                except FloatingPointError:
                    outcome = "rejected_nonfinite"
                else:
                    slope = -float((forces * (trial_xyz - xyz)).sum())
                    if not tangent_ok:
                        outcome = "rejected_tangent"
                    elif slope >= 0:
                        outcome = "rejected_non_descent"
                    elif trial_energy > energy + minimum.armijo_constant * slope:
                        outcome = "rejected_armijo"
            rows.append(observation(len(rows) + 1, accepted + 1, trial, outcome,
                                    trial_xyz, projection, step, trial_energy, trial_force))
            if outcome == "accepted":
                xyz, energy, forces, force, residual = trial_xyz, trial_energy, trial_forces, trial_force, trial_residual
                accepted += 1
                moved = True
                break
            step *= minimum.backtrack_factor
        if not moved:
            status = "line_search_failed"
            break
    if force <= minimum.force_tolerance_kcal_per_mol_angstrom:
        status = "converged"
    with meter.measure("implementation.verify"):
        if (canonical_system_sha256(system) != source or evaluator.identity() != initial_identity
                or digest(source_manifest()) != implementation or environment() != env):
            raise ResearchError("input, parameters, implementation or environment changed during execution")
    document = {"schema_id": CHECKPOINT_SCHEMA, "algorithm_id": ALGORITHM_ID,
                "source_system_sha256": source, "evaluator": initial_identity,
                "config": config.to_dict(), "implementation_sha256": implementation, "environment": env,
                "atom_count": system.atom_count, "coordinates": coordinates_hex(xyz),
                "coordinates_sha256": digest(coordinates_hex(xyz)),
                "initial_energy": rows[0]["energy"], "initial_max_tangent_force": rows[0]["max_tangent_force"],
                "current_energy": energy, "current_max_tangent_force": force,
                "current_constraint_residual": residual, "accepted_iterations": accepted,
                "evaluation_count": len(rows), "status": status, "observations": rows}
    saved = require_checkpoint({**document, "checkpoint_sha256": digest(document)})
    output = system.with_coordinates(xyz, operation=ALGORITHM_ID,
                                     operation_evidence_sha256=saved.checkpoint_sha256)
    return MinimizationResult(output, saved, meter.numerical_calls())
