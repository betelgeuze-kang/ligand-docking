"""Opt-in authenticated-proposal adapter for structure-preserving refinement.

The provider declares a fixed model and physical units. Digests detect accidental
cross-wiring; they do NOT authenticate a model, authorize native execution, or
establish molecular accuracy. No backend or default product lane is activated.
A provider must recompute E/F for every supplied coordinate set, rebuilding its
neighbor data as needed. This adapter owns no reusable optimizer or force cache.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from types import MappingProxyType
from typing import Mapping, Protocol

import torch

from betelgeuze_engine_v2.molecular import (
    AllAtomSystem, canonical_system_sha256, canonical_topology_sha256,
    require_valid_all_atom_system,
)
from betelgeuze_engine_v2.docking.authority import AuthenticatedDockingProblem, DockingAuthorityError
from betelgeuze_engine_v2.docking.identity import coordinate_fingerprint
from betelgeuze_engine_v2.docking.proposals import DockingProposal
from . import structure_preserving as _core
from .structure_preserving import (
    Coordinates, Evaluation, SearchConfig, SearchResult, StructureTopology,
    RecoverableTrialRejection, refine_structure,
)


class StructureRefinementError(DockingAuthorityError):
    """A bound refinement contract failed; messages contain no backend text."""


def _digest(value: object) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise StructureRefinementError("expected a lowercase SHA-256 identity")
    return value


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode("utf-8")).hexdigest()


def structure_coordinate_sha256(coordinates: Coordinates) -> str:
    """Exact binary64 tuple identity, distinct from engine tensor identity."""
    if not isinstance(coordinates, tuple) or not coordinates:
        raise StructureRefinementError("invalid coordinate tuple")
    rows = []
    for row in coordinates:
        if not isinstance(row, tuple) or len(row) != 3:
            raise StructureRefinementError("invalid coordinate row")
        if any(type(x) is not float or not math.isfinite(x) for x in row):
            raise StructureRefinementError("invalid coordinate value")
        rows.append([x.hex() for x in row])
    return _hash({"schema": "structure_coordinates_binary64/1", "rows": rows})


@dataclass(frozen=True)
class BoundEnergyForceResult:
    coordinate_sha256: str
    model_fingerprint_sha256: str
    energy: float
    forces: Coordinates
    energy_unit: str = "kcal/mol"
    force_unit: str = "kcal/mol/angstrom"
    force_semantics: str = "negative_coordinate_gradient"


class BoundEnergyForceProvider(Protocol):
    """Explicit identity declaration, not a native execution qualification."""
    problem_fingerprint_sha256: str
    ligand_topology_sha256: str
    model_fingerprint_sha256: str
    implementation_source_sha256: str

    def evaluate(self, coordinates: Coordinates) -> BoundEnergyForceResult:
        ...


@dataclass(frozen=True)
class StructureRefinementAttempt:
    source_proposal_sha256: str
    authority_input_sha256: str
    config_sha256: str
    provider_identity_sha256: str
    status: str
    result: SearchResult
    post_coordinates_sha256: str

    @property
    def receipt_sha256(self) -> str:
        return _hash(asdict(self))


def _dihedral(coordinates: torch.Tensor, indices: tuple[int, int, int, int]) -> float:
    a, b, c, d = (coordinates[i] for i in indices)
    axis = c - b
    norm = float(torch.linalg.vector_norm(axis).item())
    if norm <= 1.e-10:
        raise StructureRefinementError("degenerate torsion axis")
    axis = axis / norm
    left, right = a - b, d - c
    left, right = left - torch.dot(left, axis) * axis, right - torch.dot(right, axis) * axis
    ll, rr = float(torch.linalg.vector_norm(left).item()), float(torch.linalg.vector_norm(right).item())
    if min(ll, rr) <= 1.e-10:
        raise StructureRefinementError("degenerate torsion anchor")
    left, right = left / ll, right / rr
    return math.atan2(float(torch.dot(torch.cross(left, right, dim=0), axis).item()),
                      float(torch.dot(left, right).item()))


class StructurePreservingPoseRefiner:
    """DockingPoseRefiner sibling; opt-in only, preserving existing lineage.

    ``max_steps`` limits accepted steps; the separate config evaluation cap also
    charges initial, rejected, malformed and failed provider calls. A successful
    returned proposal is not necessarily stationary or accurate. The original
    proposal rotation/translation fields remain initial-placement metadata as in
    existing with_refined_coordinates semantics; final coordinates are authoritative.
    Instances are synchronous and single-worker; use separate instances per worker.
    """
    refiner_id = "betelgeuze.structure_preserving_pose_refiner"
    refiner_version = "1.0.0"

    def __init__(self, authority: AuthenticatedDockingProblem, ligand_system: AllAtomSystem,
                 provider: BoundEnergyForceProvider, *, implementation_source_sha256: str,
                 config: SearchConfig | None = None, max_attempts: int = 1024) -> None:
        if not isinstance(authority, AuthenticatedDockingProblem) or not isinstance(ligand_system, AllAtomSystem):
            raise StructureRefinementError("authenticated authority and ligand system required")
        require_valid_all_atom_system(ligand_system)
        if (ligand_system.coordinates.device.type != "cpu" or ligand_system.coordinates.dtype != torch.float64
                or canonical_system_sha256(ligand_system) != authority.ligand_system_sha256):
            raise StructureRefinementError("ligand source is cross-wired or unsupported")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10000:
            raise StructureRefinementError("invalid attempt capacity")
        selected = SearchConfig() if config is None else config
        if type(selected) is not SearchConfig:
            raise StructureRefinementError("explicit SearchConfig required")
        self._authority, self._ligand, self._provider = authority, ligand_system, provider
        self._config, self._max_attempts = selected, max_attempts
        self._source = _digest(implementation_source_sha256)
        self._source_snapshot = self._source
        self._implementation_snapshot = self._implementation_identity()
        self._authority_sha = authority.input_receipt_sha256
        self._topology_sha = canonical_topology_sha256(ligand_system)
        self._provider_snapshot = self._provider_identity()
        self._provider_sha = _hash(self._provider_snapshot)
        if (self._provider_snapshot["problem_fingerprint_sha256"] != authority.problem.fingerprint_sha256
                or self._provider_snapshot["ligand_topology_sha256"] != self._topology_sha):
            raise StructureRefinementError("provider problem or topology is cross-wired")
        if not callable(getattr(provider, "evaluate", None)):
            raise StructureRefinementError("provider evaluate method required")
        self._config_sha = _hash({"config": asdict(selected), "provider": self._provider_sha,
                                  "authority": self._authority_sha, "max_attempts": max_attempts,
                                  "implementation": self._implementation_snapshot})
        dispositions = {(a, b): kind for a, b, kind in authority.search_space_receipt.rotor_bond_dispositions}
        bonds = []
        adjacency = [[] for _ in ligand_system.atoms]
        for bond in ligand_system.bonds:
            a, b = int(bond.atom_i), int(bond.atom_j)
            disposition = dispositions[tuple(sorted((a, b)))]
            kind = ("amide" if disposition in {"amide", "sulfonamide"} else
                    "aromatic" if bond.aromatic else "single" if float(bond.order) == 1.0 else
                    "double" if float(bond.order) == 2.0 else "triple" if float(bond.order) == 3.0 else "other")
            bonds.append((a, b, kind))
            adjacency[a].append(b)
            adjacency[b].append(a)
        children = authority.search_space_receipt.rotatable_child_atom_indices
        rotors = tuple((int(authority.search_space.parent[child].item()), child) for child in children)
        if any(dispositions[tuple(sorted(pair))] != "rotatable" for pair in rotors):
            raise StructureRefinementError("rotor declaration is not authority-derived")
        self._topology = StructureTopology(ligand_system.atom_count, tuple(bonds), rotors)
        self._topology_policy_sha = _hash(asdict(self._topology))
        source_coordinates = ligand_system.coordinates[authority.ligand_model_index]
        rows = []
        for a, b in rotors:
            def anchor(center: int, excluded: int) -> int:
                choices = [i for i in adjacency[center] if i != excluded]
                if not choices:
                    raise StructureRefinementError("rotor lacks a dihedral anchor")
                return min(choices, key=lambda i: (ligand_system.atoms[i].element == "H", i))
            indices = (anchor(a, b), a, b, anchor(b, a))
            rows.append((b, indices, _dihedral(source_coordinates, indices)))
        self._torsion_rows = tuple(rows)
        self._attempts: dict[str, StructureRefinementAttempt] = {}
        self._inflight: set[str] = set()
        self.assert_ready()

    def _implementation_identity(self) -> dict[str, str]:
        return {"implementation_source_sha256": self._source,
                "refiner_id": self.refiner_id, "refiner_version": self.refiner_version,
                "core_algorithm_id": _core.ALGORITHM_ID}

    def _provider_identity(self) -> dict[str, str]:
        return {name: _digest(getattr(self._provider, name, None)) for name in
                ("problem_fingerprint_sha256", "ligand_topology_sha256",
                 "model_fingerprint_sha256", "implementation_source_sha256")}

    @property
    def problem_fingerprint_sha256(self) -> str:
        return self._authority.problem.fingerprint_sha256

    @property
    def implementation_source_sha256(self) -> str:
        return self._source

    @property
    def config_fingerprint_sha256(self) -> str:
        return self._config_sha

    @property
    def attempts(self) -> Mapping[str, StructureRefinementAttempt]:
        return MappingProxyType(dict(self._attempts))

    def assert_ready(self) -> None:
        try:
            if (self._authority.input_receipt_sha256 != self._authority_sha
                    or canonical_system_sha256(self._ligand) != self._authority.ligand_system_sha256
                    or canonical_topology_sha256(self._ligand) != self._topology_sha
                    or self._provider_identity() != self._provider_snapshot
                    or self._source != self._source_snapshot
                    or self._implementation_identity() != self._implementation_snapshot
                    or _hash(asdict(self._topology)) != self._topology_policy_sha
                    or _hash({"config": asdict(self._config), "provider": self._provider_sha,
                              "authority": self._authority_sha, "max_attempts": self._max_attempts,
                              "implementation": self._implementation_snapshot}) != self._config_sha):
                raise StructureRefinementError("construction-bound inputs changed")
        except Exception:
            # Integrity helpers and identity properties may raise their own
            # exception types. Keep the public preflight boundary sanitized.
            raise StructureRefinementError("construction-bound inputs changed") from None

    def refine(self, proposal: DockingProposal, *, max_steps: int) -> DockingProposal:
        self.assert_ready()
        if not isinstance(proposal, DockingProposal):
            raise StructureRefinementError("DockingProposal required")
        proposal.assert_integrity()
        if (proposal.problem_fingerprint_sha256 != self.problem_fingerprint_sha256
                or proposal.search_space_fingerprint_sha256 != self._authority.search_space.fingerprint_sha256
                or proposal.coordinates.dtype != torch.float64
                or proposal.coordinates.device.type != "cpu"
                or tuple(proposal.coordinates.shape) != (self._topology.atom_count, 3)):
            raise StructureRefinementError("proposal is cross-wired or unsupported")
        if type(max_steps) is not int or not 1 <= max_steps <= self._config.max_steps:
            raise StructureRefinementError("max_steps exceeds configured bound")
        source_sha = proposal.fingerprint_sha256
        if (source_sha in self._attempts or source_sha in self._inflight
                or len(self._attempts) + len(self._inflight) >= self._max_attempts):
            raise StructureRefinementError("duplicate or excessive refinement attempt")
        coordinates = tuple(tuple(float(x) for x in row) for row in proposal.coordinates.tolist())
        # Anchor failure is caught before any E/F call, not hidden in cost accounting.
        for _, indices, _ in self._torsion_rows:
            _dihedral(proposal.coordinates, indices)
        effective = replace(self._config, max_steps=max_steps)

        def evaluate(points: Coordinates) -> Evaluation:
            self.assert_ready()
            proposal.assert_integrity()
            expected = structure_coordinate_sha256(points)
            try:
                result = self._provider.evaluate(points)
            except RecoverableTrialRejection:
                # A soft geometry signal must never hide changed bound inputs.
                self.assert_ready()
                proposal.assert_integrity()
                raise
            self.assert_ready()
            proposal.assert_integrity()
            if (type(result) is not BoundEnergyForceResult
                    or result.coordinate_sha256 != expected
                    or result.model_fingerprint_sha256 != self._provider_snapshot["model_fingerprint_sha256"]
                    or result.energy_unit != "kcal/mol" or result.force_unit != "kcal/mol/angstrom"
                    or result.force_semantics != "negative_coordinate_gradient"):
                raise StructureRefinementError("provider result binding or units mismatch")
            return Evaluation(result.energy, result.forces)

        self._inflight.add(source_sha)
        try:
            result = refine_structure(coordinates, self._topology, evaluate, effective)
        finally:
            self._inflight.discard(source_sha)
        successful = result.status in {"projected_stationary", "step_limit", "evaluation_limit",
                                       "line_search_failed", "no_representable_step", "motion_limit"} and result.energy is not None
        post = torch.tensor(result.coordinates, dtype=torch.float64)
        attempt = StructureRefinementAttempt(source_sha, self._authority_sha,
                    _hash({"config": self._config_sha, "effective": asdict(effective)}), self._provider_sha,
                    "success" if successful else "failure", result, coordinate_fingerprint(post))
        # Preserve all charged work even if the final identity/metadata check fails.
        self._attempts[source_sha] = attempt
        try:
            self.assert_ready()
            proposal.assert_integrity()
            if not successful:
                raise StructureRefinementError("structure-preserving refinement failed")
            torsions = torch.zeros_like(proposal.torsion_angles)
            for child, indices, reference in self._torsion_rows:
                angle = _dihedral(post, indices) - reference
                torsions[child] = math.atan2(math.sin(angle), math.cos(angle))
            refined = proposal.with_refined_coordinates(post, refiner_id=self.refiner_id,
                refiner_version=self.refiner_version, refinement_receipt_sha256=attempt.receipt_sha256,
                torsion_angles=torsions)
            return refined
        except Exception:
            self._attempts[source_sha] = replace(attempt, status="failure")
            raise StructureRefinementError("structure-preserving refinement failed") from None
