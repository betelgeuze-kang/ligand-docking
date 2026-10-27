"""Opt-in source-level fixed-receptor E/F binding, not an execution approval.

The owning caller must retain its existing input/runtime admission and HOLDs.
This module provides no CLI, gate credential, native qualification, or default
activation. Explicit synthetic parameters test implementation, not chemistry.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from types import MappingProxyType

import torch

from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph
from betelgeuze_engine_v2.molecular import canonical_system_sha256, canonical_topology_sha256
from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem
from betelgeuze_engine_v2.docking.proposals import DockingProposal
from .structure_preserving import SearchConfig, RecoverableTrialRejection
from betelgeuze_engine_v2.physics.reference_forcefield import _applicability_blockers
from betelgeuze_engine_v2.physics.reference_forcefield_v2 import (
    ReferenceForceFieldV2Parameters, _constraint_observations, _validate_extension_topology,
)
from .cpu_refinement_v1_2.evaluation import ExtendedEvaluator
from .cpu_refinement_v1_2.fixed_receptor import (
    CrossParameters, FixedReceptorEnvironment, FixedReceptorEvaluator, require_system,
    components_document, validate_components, FIXED_POLICY_ID, ENERGY_BASIS,
)
from .structure_preserving_refinement import (
    BoundEnergyForceResult, StructureRefinementError, StructurePreservingPoseRefiner, _digest, _hash,
    structure_coordinate_sha256,
)


@dataclass(frozen=True)
class FixedReceptorObservation:
    evaluation_attempt: int
    coordinate_sha256: str
    evaluator_fingerprint_sha256: str
    components: tuple[tuple[str, float], ...]
    constraint_observations: tuple
    scientific_blockers: tuple[str, ...]
    energy_unit: str
    force_unit: str
    calibrated: bool
    force_calibrated: bool
    energy_semantics: str
    force_semantics: str
    validated_for_composition: bool

    @property
    def constraints_satisfied(self):
        return all(row.satisfied for row in self.constraint_observations)

    def components_document(self):
        return dict(self.components)


class FixedReceptorEnergyForceProvider:
    """Fresh raw forces for each call; synchronous, single-worker, bounded calls.

    All identities are declarations/cross-wiring checks, not credentials. The
    provider never projects forces or modifies input chemistry/coordinates.
    """
    def __init__(self, authority, ligand, receptor, parameters, cross, *,
                 implementation_source_sha256: str, max_neighbors: int = 256,
                 max_atoms_per_cell: int = 256, max_evaluations: int = 4096):
        if (type(authority) is not AuthenticatedDockingProblem
                or type(parameters) is not ReferenceForceFieldV2Parameters
                or type(cross) is not CrossParameters):
            raise StructureRefinementError("explicit authority and fixed-receptor parameters required")
        for value in (max_neighbors, max_atoms_per_cell):
            if type(value) is not int or not 1 <= value <= 256:
                raise StructureRefinementError("invalid neighbor capacity")
        if type(max_evaluations) is not int or not 1 <= max_evaluations <= 100000:
            raise StructureRefinementError("invalid provider evaluation capacity")
        require_system(ligand, 256)
        require_system(receptor, 8192)
        self._authority, self._ligand, self._receptor = authority, ligand, receptor
        self._source = _digest(implementation_source_sha256)
        self._graph = RadiusGraphConfig(parameters.base_parameters.cutoff_angstrom,
                                       max_neighbors, max_atoms_per_cell)
        self._evaluator = FixedReceptorEvaluator(ExtendedEvaluator(parameters),
                                                FixedReceptorEnvironment(receptor, cross))
        self._evaluator.fixed.validate_ligand(ligand, parameters.base_parameters)
        self._capacity, self._calls = max_evaluations, 0
        self._observations = []
        self._graph_builds = self._physical_calls = self._domain_rejections = 0
        self._snapshot = self._identity()
        self._assert_binding()

    def _assert_binding(self):
        a, f = self._authority, self._evaluator.fixed
        if (a.ligand_model_index != 0 or a.receptor_model_index != 0
                or canonical_system_sha256(self._ligand) != a.ligand_system_sha256
                or canonical_system_sha256(self._receptor) != a.receptor_system_sha256
                or f.cross.receptor_system_sha256 != a.receptor_system_sha256
                or f.cross.coordinate_frame_id != a.pocket.coordinate_frame_id):
            raise StructureRefinementError("fixed-receptor source or coordinate frame is cross-wired")
        f.validate_ligand(self._ligand, self._evaluator.parameters.base_parameters)

    def _identity(self):
        return {"authority": self._authority.input_receipt_sha256,
                "problem": self._authority.problem.fingerprint_sha256,
                "ligand": canonical_system_sha256(self._ligand),
                "receptor": canonical_system_sha256(self._receptor),
                "evaluator": self._evaluator.fingerprint_sha256,
                "graph": asdict(self._graph), "source": self._source,
                "max_evaluations": self._capacity}

    def assert_ready(self):
        try:
            self._assert_binding()
            if self._identity() != self._snapshot:
                raise StructureRefinementError("fixed-receptor construction-bound inputs changed")
        except Exception:
            raise StructureRefinementError("fixed-receptor construction-bound inputs changed") from None

    @property
    def problem_fingerprint_sha256(self):
        self.assert_ready()
        return self._snapshot["problem"]

    @property
    def ligand_topology_sha256(self):
        self.assert_ready()
        return canonical_topology_sha256(self._ligand)

    @property
    def model_fingerprint_sha256(self):
        self.assert_ready()
        return _hash(self._snapshot)

    @property
    def implementation_source_sha256(self):
        self.assert_ready()
        return self._source

    @property
    def evaluation_attempts(self):
        """Admitted provider calls; excludes binding/capacity preflight denials."""
        return self._calls

    @property
    def graph_build_attempts(self):
        """Provider-owned graph builds; excludes evaluator's own integrity rebuilds."""
        return self._graph_builds

    @property
    def physical_evaluation_attempts(self):
        return self._physical_calls

    @property
    def recoverable_rejections(self):
        return self._domain_rejections

    @property
    def observations(self):
        return tuple(self._observations)

    @property
    def max_internal_increase_kcal_per_mol(self):
        self.assert_ready()
        return self._evaluator.fixed.cross.max_internal_increase_kcal_per_mol

    def observe_constraints(self, coordinates):
        """Geometry-only initial admission; performs no E/F or graph evaluation."""
        self.assert_ready()
        structure_coordinate_sha256(coordinates)
        if len(coordinates) != self._ligand.atom_count:
            raise StructureRefinementError("fixed-receptor coordinate count mismatch")
        xyz = torch.tensor([coordinates], dtype=torch.float64)
        state = self._ligand.with_coordinates(xyz, operation="fixed_receptor_constraint_admission")
        _validate_extension_topology(state, self._evaluator.parameters)
        rows = _constraint_observations(xyz, state, self._evaluator.parameters.constraints)
        self.assert_ready()
        return rows

    def _coordinate_domain_precheck(self, xyz, neighbors):
        def reject():
            self.assert_ready()
            self._domain_rejections += 1
            raise RecoverableTrialRejection("coordinate_domain_singularity")

        # Same active pairs and distance cutoff as the actual internal evaluator;
        # its minimum-distance check precedes excluded/scaled-pair arithmetic.
        batch, left, slot = torch.nonzero(neighbors.upper_mask(), as_tuple=True)
        right = neighbors.indices[batch, left, slot]
        if batch.numel():
            distances = torch.linalg.vector_norm(xyz[batch, left] - xyz[batch, right], dim=-1)
            minimum = self._evaluator.parameters.base_parameters.applicability_domain.minimum_pair_distance_angstrom
            if not bool(torch.isfinite(distances).all()) or bool((distances < minimum).any()):
                reject()
        cross = self._evaluator.fixed.cross
        for start in range(0, self._receptor.atom_count, cross.receptor_block_size):
            receptor = self._receptor.coordinates[0, start:start + cross.receptor_block_size]
            distances = torch.linalg.vector_norm(xyz[0, :, None, :] - receptor[None, :, :], dim=-1)
            if (not bool(torch.isfinite(distances).all())
                    or bool((distances < cross.minimum_distance_angstrom).any())):
                reject()

    def evaluate(self, coordinates):
        self.assert_ready()
        if self._calls >= self._capacity:
            raise StructureRefinementError("provider evaluation capacity exhausted")
        self._calls += 1
        coordinate_sha = structure_coordinate_sha256(coordinates)
        if len(coordinates) != self._ligand.atom_count:
            raise StructureRefinementError("fixed-receptor coordinate count mismatch")
        xyz = torch.tensor([coordinates], dtype=torch.float64)
        state = self._ligand.with_coordinates(xyz, operation="structure_preserving_fixed_receptor_evaluation")
        _validate_extension_topology(state, self._evaluator.parameters)
        self._graph_builds += 1
        neighbors = build_compact_radius_graph(xyz, self._graph)
        if _applicability_blockers(state, neighbors, self._evaluator.parameters.base_parameters):
            raise StructureRefinementError("fixed-receptor model applicability failed")
        self._coordinate_domain_precheck(xyz, neighbors)
        self._physical_calls += 1
        result = self._evaluator.evaluate(state, neighbors)
        self.assert_ready()
        energy_descriptor = result.term.energy_descriptor
        force_descriptor = result.term.force_descriptor
        energy, force = result.term.energy, result.term.forces
        if (result.evaluator_fingerprint_sha256 != self._snapshot["evaluator"]
                or not isinstance(energy, torch.Tensor) or not isinstance(force, torch.Tensor)
                or tuple(energy.shape) != (1,)
                or tuple(force.shape) != (1, self._ligand.atom_count, 3)
                or energy.device.type != "cpu" or force.device.type != "cpu"
                or energy.dtype != torch.float64 or force.dtype != torch.float64
                or not bool(torch.isfinite(energy).all()) or not bool(torch.isfinite(force).all())
                or energy_descriptor.calibrated is not False
                or force_descriptor.calibrated is not False
                or energy_descriptor.physical_quantity is not True
                or force_descriptor.physical_quantity is not True
                or energy_descriptor.unit != "kcal/mol"
                or force_descriptor.unit != "kcal/mol/angstrom"
                or energy_descriptor.semantics != ENERGY_BASIS
                or force_descriptor.semantics != "negative_ligand_coordinate_gradient_of_fixed_receptor_total"
                or result.term.validated_for_composition is not False
                or "fixed_receptor_model_not_scientifically_validated" not in result.scientific_blockers):
            raise StructureRefinementError("fixed-receptor output contract mismatch")
        expected_constraints = _constraint_observations(xyz, state, self._evaluator.parameters.constraints)
        if tuple(result.constraint_observations) != expected_constraints:
            raise StructureRefinementError("fixed-receptor constraint observation coverage mismatch")
        for row in result.constraint_observations:
            if (type(row.satisfied) is not bool
                    or not all(math.isfinite(v) for v in (row.observed_distance_angstrom,
                        row.target_distance_angstrom, row.residual_angstrom, row.tolerance_angstrom))
                    or row.tolerance_angstrom < 0
                    or row.satisfied != (abs(row.residual_angstrom) <= row.tolerance_angstrom)):
                raise StructureRefinementError("invalid fixed-receptor constraint observation")
        components = components_document(result)
        validate_components(components, float(energy[0]))
        self._observations.append(FixedReceptorObservation(
            self._calls, coordinate_sha, result.evaluator_fingerprint_sha256,
            tuple(sorted(components.items())), tuple(result.constraint_observations),
            tuple(result.scientific_blockers), energy_descriptor.unit, force_descriptor.unit,
            energy_descriptor.calibrated, force_descriptor.calibrated,
            energy_descriptor.semantics, force_descriptor.semantics,
            result.term.validated_for_composition))
        return BoundEnergyForceResult(coordinate_sha, self.model_fingerprint_sha256,
            float(result.term.energy[0]),
            tuple(tuple(float(x) for x in row) for row in result.term.forces[0].tolist()))


@dataclass(frozen=True)
class FixedStructureRefinementOutcome:
    """Policy outcome; admissible is NOT pose validity, rank, or execution approval."""
    proposal: object
    optimizer_attempt: object
    initial_observation: FixedReceptorObservation
    final_observation: FixedReceptorObservation
    max_internal_increase_kcal_per_mol: float
    rejection_reasons: tuple[str, ...]
    evaluation_attempts: int
    provider_admitted_attempts: int
    physical_evaluation_attempts: int
    graph_build_attempts: int
    recoverable_rejections: int
    policy_id: str = FIXED_POLICY_ID
    scientifically_validated: bool = False

    @property
    def admissible(self):
        return not self.rejection_reasons

    def admission_document(self):
        """Required strain fields retained for existing selection policy."""
        initial, final = self.initial_observation.components_document(), self.final_observation.components_document()
        return {"status": "success" if self.admissible else "failure",
                "initial_components": initial, "final_components": final,
                "max_internal_increase_kcal_per_mol": self.max_internal_increase_kcal_per_mol,
                "energy_delta": final["total"] - initial["total"],
                # Projected stationarity is not the existing Cartesian convergence.
                "converged": False, "policy_id": self.policy_id,
                "constraints_satisfied": self.final_observation.constraints_satisfied,
                "scientifically_validated": False}


def final_admission_reasons(initial, final, max_internal_increase_kcal_per_mol):
    """Final-only physical policy; intentionally not a trial-level predicate."""
    if type(initial) is not FixedReceptorObservation or type(final) is not FixedReceptorObservation:
        raise StructureRefinementError("explicit endpoint observations required")
    if (type(max_internal_increase_kcal_per_mol) not in (int, float)
            or not math.isfinite(max_internal_increase_kcal_per_mol)
            or max_internal_increase_kcal_per_mol < 0):
        raise StructureRefinementError("explicit finite nonnegative strain limit required")
    if (len(initial.components) != len(dict(initial.components))
            or len(final.components) != len(dict(final.components))):
        raise StructureRefinementError("duplicate component keys")
    a, b = initial.components_document(), final.components_document()
    validate_components(a, a["total"])
    validate_components(b, b["total"])
    if initial.evaluator_fingerprint_sha256 != final.evaluator_fingerprint_sha256:
        raise StructureRefinementError("endpoint model mismatch")
    reasons = []
    if not initial.constraints_satisfied:
        reasons.append("initial_constraints_unsatisfied")
    if b["total"] > a["total"]:
        reasons.append("total_energy_increased")
    if b["ligand_internal"] - a["ligand_internal"] > max_internal_increase_kcal_per_mol:
        reasons.append("final_internal_strain_exceeded")
    if not final.constraints_satisfied:
        reasons.append("final_constraints_unsatisfied")
    return tuple(reasons)


@dataclass(frozen=True)
class FixedRefinementWork:
    evaluation_attempts: int
    provider_admitted_attempts: int
    physical_evaluation_attempts: int
    graph_build_attempts: int
    recoverable_rejections: int


class FixedReceptorStructureCoordinator:
    """Unregistered research coordinator; no scoring or pose-validity replacement.

    Final strain is checked only after optimization. Arbitrary distance
    constraints can change under torsion: preserve observations and deny final
    admission if unsatisfied, rather than silently projecting or waiving them.
    The owner must separately perform structural validity and ranking checks.
    """
    def __init__(self, authority, ligand, provider, *, implementation_source_sha256,
                 config=None, max_attempts=1024):
        if type(provider) is not FixedReceptorEnergyForceProvider:
            raise StructureRefinementError("explicit fixed-receptor provider required")
        self._provider = provider
        self._authority = authority
        self._atom_count = ligand.atom_count
        self._config = SearchConfig() if config is None else config
        self._refiner = StructurePreservingPoseRefiner(authority, ligand, provider,
            implementation_source_sha256=implementation_source_sha256,
            config=self._config, max_attempts=max_attempts)
        self._outcomes = {}
        self._failed_work = {}
        self._initial_constraint_rejections = {}
        self._max_attempts = max_attempts

    @property
    def attempts(self):
        return self._refiner.attempts

    @property
    def outcomes(self):
        return MappingProxyType(dict(self._outcomes))

    @property
    def failed_work(self):
        return MappingProxyType(dict(self._failed_work))

    @property
    def initial_constraint_rejections(self):
        return MappingProxyType(dict(self._initial_constraint_rejections))

    def run(self, proposal, *, max_steps):
        self._refiner.assert_ready()
        if not isinstance(proposal, DockingProposal):
            raise StructureRefinementError("DockingProposal required")
        if type(max_steps) is not int or not 1 <= max_steps <= self._config.max_steps:
            raise StructureRefinementError("max_steps exceeds configured bound")
        proposal.assert_integrity()
        source_sha = proposal.fingerprint_sha256
        if (source_sha in self._initial_constraint_rejections
                or source_sha in self._refiner.attempts
                or len(self._initial_constraint_rejections) + len(self._refiner.attempts) >= self._max_attempts):
            raise StructureRefinementError("duplicate or excessive refinement attempt")
        if (proposal.problem_fingerprint_sha256 != self._provider.problem_fingerprint_sha256
                or proposal.search_space_fingerprint_sha256 != self._authority.search_space.fingerprint_sha256
                or tuple(proposal.coordinates.shape) != (self._atom_count, 3)
                or proposal.coordinates.dtype != torch.float64
                or proposal.coordinates.device.type != "cpu"):
            raise StructureRefinementError("proposal is cross-wired or unsupported")
        initial_points = tuple(tuple(float(x) for x in row) for row in proposal.coordinates.tolist())
        constraints = self._provider.observe_constraints(initial_points)
        if not all(row.satisfied for row in constraints):
            self._initial_constraint_rejections[source_sha] = constraints
            raise StructureRefinementError("initial constraints unsatisfied")
        before = self._provider.evaluation_attempts
        physical_before = self._provider.physical_evaluation_attempts
        graphs_before = self._provider.graph_build_attempts
        rejected_before = self._provider.recoverable_rejections
        first = len(self._provider.observations)
        try:
            refined = self._refiner.refine(proposal, max_steps=max_steps)
        except Exception:
            recorded = self._refiner.attempts.get(source_sha)
            if recorded is not None:
                self._failed_work[source_sha] = FixedRefinementWork(
                    recorded.result.evaluation_attempts,
                    self._provider.evaluation_attempts - before,
                    self._provider.physical_evaluation_attempts - physical_before,
                    self._provider.graph_build_attempts - graphs_before,
                    self._provider.recoverable_rejections - rejected_before)
            raise
        attempt = self._refiner.attempts[proposal.fingerprint_sha256]
        observations = self._provider.observations[first:]
        initial_sha = structure_coordinate_sha256(tuple(tuple(float(x) for x in row)
                                                 for row in proposal.coordinates.tolist()))
        final_sha = structure_coordinate_sha256(attempt.result.coordinates)
        initial = next((row for row in observations if row.coordinate_sha256 == initial_sha), None)
        final = next((row for row in reversed(observations) if row.coordinate_sha256 == final_sha), None)
        if initial is None or final is None:
            raise StructureRefinementError("missing endpoint physical observations")
        limit = self._provider.max_internal_increase_kcal_per_mol
        reasons = final_admission_reasons(initial, final, limit)
        outcome = FixedStructureRefinementOutcome(refined, attempt, initial, final, limit,
            tuple(reasons), attempt.result.evaluation_attempts,
            self._provider.evaluation_attempts - before,
            self._provider.physical_evaluation_attempts - physical_before,
            self._provider.graph_build_attempts - graphs_before,
            self._provider.recoverable_rejections - rejected_before)
        self._outcomes[proposal.fingerprint_sha256] = outcome
        return outcome
