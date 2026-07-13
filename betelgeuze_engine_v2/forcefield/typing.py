"""Bounded C1-C4 linear-alkane topological environment assignments.

This module deliberately does *not* assign production force-field atom types
or partial charges.  It derives deterministic graph-environment match keys for
the source-bound explicit-hydrogen C1-C4 linear-alkane applicability profile.
Those keys are an input contract for later parameter matching, not evidence
that any parameter, charge model, physics method, or runtime is available.

Each report owns canonical snapshot bytes and replays the upstream
applicability analysis and environment derivation whenever report state is
read.  The snapshot and report digests are deterministic internal bindings;
they are not source authentication or a security signature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID,
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION,
    LinearAlkaneC1C4ForceFieldApplicabilityReport,
    analyze_linear_alkane_c1_c4_force_field_applicability,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)


_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION = (
    "1.0.0"
)
_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_topological_environment_typing/"
    f"{_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION}"
)
_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID = (
    "linear_alkane_c1_c4_graph_neighbor_environment/1.0.0"
)
_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE = (
    "bounded_topological_environment_match_keys_only"
)
_FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID = (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID
)
_FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION = (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION
)
_FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID = (
    LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID
)

# Public names are compatibility labels.  Versioned behavior below is bound to
# the private import-time literals so monkeypatching a convenience export
# cannot silently redefine an existing artifact.
LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION = (
    _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION
)
LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID = (
    _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID
)
LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID = (
    _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID
)
LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE = (
    _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE
)
LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_STATUSES = frozenset(
    {"invalid_system", "unsupported_system", "environments_available"}
)
_FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_STATUSES = (
    LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_STATUSES
)

_MAX_JSON_INTEGER = (1 << 53) - 1
_ENVIRONMENTS_AVAILABLE = "environments_available"
_INVALID_SYSTEM = "invalid_system"
_UNSUPPORTED_SYSTEM = "unsupported_system"
_COVERAGE_COMPLETE = "complete_for_bounded_c1_c4_linear_alkane_profile"
_COVERAGE_NOT_AVAILABLE = "not_available"
_FF_TYPING_NOT_ASSIGNED = "not_assigned_topological_environment_only"
_PARTIAL_CHARGE_NOT_ASSIGNED = "not_assigned"
_FORMAL_CHARGE_OBSERVED = (
    "source_observed_known_zero_not_partial_charge_assignment"
)
_FORMAL_CHARGE_NOT_AVAILABLE = "not_available_for_typing"
_SOURCE_PARTIAL_CHARGE_ABSENT = "absent_required_by_applicability_profile"
_SOURCE_PARTIAL_CHARGE_REJECTED = "present_not_used_and_profile_rejected"


class TopologicalEnvironmentTypingContractError(ValueError):
    """Raised when a typing report or its canonical binding is inconsistent."""


def _validate_json_index(name: str, value: Any) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > _MAX_JSON_INTEGER:
        raise ValueError(
            f"{name} must be a non-negative interoperable JSON integer"
        )


def _validate_count(name: str, value: Any, *, maximum: int = 4) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > maximum:
        raise ValueError(f"{name} must be in [0, {maximum}]")


@dataclass(frozen=True, slots=True, order=True)
class LinearAlkaneTopologicalEnvironmentAssignment:
    """One topology-only environment key; never a force-field atom type."""

    atom_index: int
    element: str
    local_carbon_neighbor_count: int
    local_hydrogen_neighbor_count: int
    environment_center_carbon_neighbor_count: int
    environment_center_hydrogen_neighbor_count: int
    topological_environment_id: str
    formal_charge_known: bool
    observed_formal_charge: int
    force_field_type_id: None = None
    assigned_partial_charge_e: None = None

    def __post_init__(self) -> None:
        _validate_json_index("atom_index", self.atom_index)
        if self.element not in {"C", "H"}:
            raise ValueError("element must be C or H")
        for name in (
            "local_carbon_neighbor_count",
            "local_hydrogen_neighbor_count",
            "environment_center_carbon_neighbor_count",
            "environment_center_hydrogen_neighbor_count",
        ):
            _validate_count(name, getattr(self, name))
        if type(self.formal_charge_known) is not bool:
            raise TypeError("formal_charge_known must be a boolean")
        if self.formal_charge_known is not True or self.observed_formal_charge != 0:
            raise ValueError(
                "bounded assignments require a source-observed known-zero "
                "formal charge"
            )
        if type(self.observed_formal_charge) is not int:
            raise TypeError("observed_formal_charge must be an integer")
        if self.force_field_type_id is not None:
            raise ValueError(
                "topological environment assignments cannot carry a "
                "force-field type"
            )
        if self.assigned_partial_charge_e is not None:
            raise ValueError(
                "topological environment assignments cannot carry a partial charge"
            )

        center_carbon_count = self.environment_center_carbon_neighbor_count
        center_hydrogen_count = self.environment_center_hydrogen_neighbor_count
        if center_carbon_count + center_hydrogen_count != 4:
            raise ValueError("environment-center carbon valence must equal four")
        if self.element == "C":
            if (
                self.local_carbon_neighbor_count != center_carbon_count
                or self.local_hydrogen_neighbor_count != center_hydrogen_count
            ):
                raise ValueError(
                    "carbon local counts must equal its environment-center counts"
                )
            expected_id = (
                f"c_single_valence4_c{center_carbon_count}_"
                f"h{center_hydrogen_count}"
            )
        else:
            if (
                self.local_carbon_neighbor_count != 1
                or self.local_hydrogen_neighbor_count != 0
            ):
                raise ValueError(
                    "hydrogen assignments require one local carbon neighbor"
                )
            expected_id = (
                "h_attached_c_single_valence4_"
                f"c{center_carbon_count}_h{center_hydrogen_count}"
            )
        if self.topological_environment_id != expected_id:
            raise ValueError(
                "topological_environment_id must match the frozen graph policy"
            )

    @property
    def local_neighbor_count(self) -> int:
        return self.local_carbon_neighbor_count + self.local_hydrogen_neighbor_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "atom_index": self.atom_index,
            "element": self.element,
            "local_carbon_neighbor_count": self.local_carbon_neighbor_count,
            "local_hydrogen_neighbor_count": self.local_hydrogen_neighbor_count,
            "local_neighbor_count": self.local_neighbor_count,
            "environment_center_carbon_neighbor_count": (
                self.environment_center_carbon_neighbor_count
            ),
            "environment_center_hydrogen_neighbor_count": (
                self.environment_center_hydrogen_neighbor_count
            ),
            "topological_environment_id": self.topological_environment_id,
            "formal_charge_known": self.formal_charge_known,
            "observed_formal_charge": self.observed_formal_charge,
            "force_field_type_id": self.force_field_type_id,
            "assigned_partial_charge_e": self.assigned_partial_charge_e,
        }


def _derive_environment_assignments(
    system: AllAtomSystem,
) -> tuple[LinearAlkaneTopologicalEnvironmentAssignment, ...]:
    atom_by_index = {atom.index: atom for atom in system.atoms}
    expected_indices = tuple(range(system.atom_count))
    if tuple(sorted(atom_by_index)) != expected_indices:
        raise TopologicalEnvironmentTypingContractError(
            "applicable system must use contiguous canonical atom indices"
        )
    neighbors: dict[int, set[int]] = {index: set() for index in expected_indices}
    for bond in system.bonds:
        if (
            bond.atom_i not in atom_by_index
            or bond.atom_j not in atom_by_index
            or bond.atom_i == bond.atom_j
            or bond.atom_j in neighbors[bond.atom_i]
        ):
            raise TopologicalEnvironmentTypingContractError(
                "applicable system contains an invalid canonical graph edge"
            )
        neighbors[bond.atom_i].add(bond.atom_j)
        neighbors[bond.atom_j].add(bond.atom_i)

    local_counts: dict[int, tuple[int, int]] = {}
    for atom_index in expected_indices:
        element_counts = {"C": 0, "H": 0}
        for neighbor_index in neighbors[atom_index]:
            neighbor_element = atom_by_index[neighbor_index].element
            if neighbor_element not in element_counts:
                raise TopologicalEnvironmentTypingContractError(
                    "applicable system contains an unexpected element"
                )
            element_counts[neighbor_element] += 1
        local_counts[atom_index] = (element_counts["C"], element_counts["H"])

    assignments: list[LinearAlkaneTopologicalEnvironmentAssignment] = []
    for atom_index in expected_indices:
        atom = atom_by_index[atom_index]
        local_carbon_count, local_hydrogen_count = local_counts[atom_index]
        if atom.element == "C":
            center_carbon_count = local_carbon_count
            center_hydrogen_count = local_hydrogen_count
            environment_id = (
                f"c_single_valence4_c{center_carbon_count}_"
                f"h{center_hydrogen_count}"
            )
        elif atom.element == "H":
            attached_carbons = tuple(
                neighbor_index
                for neighbor_index in neighbors[atom_index]
                if atom_by_index[neighbor_index].element == "C"
            )
            if len(attached_carbons) != 1 or len(neighbors[atom_index]) != 1:
                raise TopologicalEnvironmentTypingContractError(
                    "applicable hydrogen must have exactly one carbon neighbor"
                )
            center_carbon_count, center_hydrogen_count = local_counts[
                attached_carbons[0]
            ]
            environment_id = (
                "h_attached_c_single_valence4_"
                f"c{center_carbon_count}_h{center_hydrogen_count}"
            )
        else:
            raise TopologicalEnvironmentTypingContractError(
                "applicable system contains an unexpected element"
            )
        assignments.append(
            LinearAlkaneTopologicalEnvironmentAssignment(
                atom_index=atom_index,
                element=atom.element,
                local_carbon_neighbor_count=local_carbon_count,
                local_hydrogen_neighbor_count=local_hydrogen_count,
                environment_center_carbon_neighbor_count=center_carbon_count,
                environment_center_hydrogen_neighbor_count=center_hydrogen_count,
                topological_environment_id=environment_id,
                formal_charge_known=atom.formal_charge_known,
                observed_formal_charge=atom.formal_charge,
            )
        )
    return tuple(assignments)


def _typing_status(
    applicability: LinearAlkaneC1C4ForceFieldApplicabilityReport,
) -> str:
    if applicability.applicability_status == "invalid":
        return _INVALID_SYSTEM
    if not applicability.applicable:
        return _UNSUPPORTED_SYSTEM
    return _ENVIRONMENTS_AVAILABLE


@dataclass(frozen=True, slots=True)
class _ValidatedTypingState:
    system: AllAtomSystem
    applicability: LinearAlkaneC1C4ForceFieldApplicabilityReport
    assignments: tuple[LinearAlkaneTopologicalEnvironmentAssignment, ...]
    typing_status: str


@dataclass(frozen=True, slots=True, init=False)
class LinearAlkaneTopologicalEnvironmentTypingReport:
    """Factory-only, snapshot-bound topology-environment coverage report."""

    _canonical_system_snapshot_bytes: bytes = field(repr=False)
    _applicability_report_sha256: str = field(repr=False)
    _environment_assignments: tuple[
        LinearAlkaneTopologicalEnvironmentAssignment, ...
    ] = field(repr=False)

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        canonical_bytes = serialize_all_atom_system(system)
        snapshot = deserialize_all_atom_system(canonical_bytes)
        if serialize_all_atom_system(snapshot) != canonical_bytes:
            raise TopologicalEnvironmentTypingContractError(
                "canonical system snapshot did not round trip exactly"
            )
        applicability = analyze_linear_alkane_c1_c4_force_field_applicability(
            snapshot
        )
        assignments = (
            _derive_environment_assignments(snapshot)
            if applicability.applicable
            else ()
        )
        object.__setattr__(
            self,
            "_canonical_system_snapshot_bytes",
            canonical_bytes,
        )
        object.__setattr__(
            self,
            "_applicability_report_sha256",
            applicability.report_sha256,
        )
        object.__setattr__(self, "_environment_assignments", assignments)
        self._validated_state()

    def _validated_state(self) -> _ValidatedTypingState:
        canonical_bytes = object.__getattribute__(
            self,
            "_canonical_system_snapshot_bytes",
        )
        if type(canonical_bytes) is not bytes:
            raise TopologicalEnvironmentTypingContractError(
                "canonical system snapshot binding must be bytes"
            )
        try:
            system = deserialize_all_atom_system(canonical_bytes)
            round_trip_bytes = serialize_all_atom_system(system)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise TopologicalEnvironmentTypingContractError(
                f"canonical system snapshot binding is invalid: {exc}"
            ) from exc
        if round_trip_bytes != canonical_bytes:
            raise TopologicalEnvironmentTypingContractError(
                "canonical system snapshot binding is noncanonical"
            )
        applicability = analyze_linear_alkane_c1_c4_force_field_applicability(
            system
        )
        expected_applicability_sha256 = object.__getattribute__(
            self,
            "_applicability_report_sha256",
        )
        if (
            type(expected_applicability_sha256) is not str
            or applicability.report_sha256 != expected_applicability_sha256
        ):
            raise TopologicalEnvironmentTypingContractError(
                "upstream applicability report binding is inconsistent"
            )
        expected_assignments = (
            _derive_environment_assignments(system)
            if applicability.applicable
            else ()
        )
        stored_assignments = object.__getattribute__(
            self,
            "_environment_assignments",
        )
        if (
            type(stored_assignments) is not tuple
            or stored_assignments != expected_assignments
        ):
            raise TopologicalEnvironmentTypingContractError(
                "topological environment assignments are inconsistent"
            )
        status = _typing_status(applicability)
        if status not in _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_STATUSES:
            raise TopologicalEnvironmentTypingContractError(
                "derived an unknown topological environment typing status"
            )
        if status == _ENVIRONMENTS_AVAILABLE and (
            len(expected_assignments) != system.atom_count
            or any(
                assignment.atom_index != index
                for index, assignment in enumerate(expected_assignments)
            )
        ):
            raise TopologicalEnvironmentTypingContractError(
                "available typing must cover every canonical atom exactly once"
            )
        return _ValidatedTypingState(
            system=system,
            applicability=applicability,
            assignments=expected_assignments,
            typing_status=status,
        )

    @property
    def canonical_system_snapshot_bytes(self) -> bytes:
        self._validated_state()
        return bytes(
            object.__getattribute__(self, "_canonical_system_snapshot_bytes")
        )

    @property
    def canonical_system_snapshot_sha256(self) -> str:
        state = self._validated_state()
        del state
        return hashlib.sha256(
            object.__getattribute__(self, "_canonical_system_snapshot_bytes")
        ).hexdigest()

    @property
    def system(self) -> AllAtomSystem:
        return self._validated_state().system

    @property
    def applicability_report(self) -> LinearAlkaneC1C4ForceFieldApplicabilityReport:
        return self._validated_state().applicability

    @property
    def applicability_report_sha256(self) -> str:
        return self._validated_state().applicability.report_sha256

    @property
    def environment_assignments(
        self,
    ) -> tuple[LinearAlkaneTopologicalEnvironmentAssignment, ...]:
        return self._validated_state().assignments

    @property
    def topological_environment_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    assignment.topological_environment_id
                    for assignment in self._validated_state().assignments
                }
            )
        )

    @property
    def topological_environment_typing_status(self) -> str:
        return self._validated_state().typing_status

    @property
    def typing_status(self) -> str:
        return self.topological_environment_typing_status

    @property
    def topological_environment_coverage_complete(self) -> bool:
        return self._validated_state().typing_status == _ENVIRONMENTS_AVAILABLE

    @property
    def topological_environment_coverage_status(self) -> str:
        return (
            _COVERAGE_COMPLETE
            if self.topological_environment_coverage_complete
            else _COVERAGE_NOT_AVAILABLE
        )

    @property
    def source_partial_charge_count(self) -> int:
        return sum(
            atom.partial_charge_e is not None
            for atom in self._validated_state().system.atoms
        )

    @property
    def source_partial_charge_status(self) -> str:
        return (
            _SOURCE_PARTIAL_CHARGE_ABSENT
            if self.source_partial_charge_count == 0
            else _SOURCE_PARTIAL_CHARGE_REJECTED
        )

    @property
    def formal_charge_observation_status(self) -> str:
        return (
            _FORMAL_CHARGE_OBSERVED
            if self.topological_environment_coverage_complete
            else _FORMAL_CHARGE_NOT_AVAILABLE
        )

    @property
    def force_field_atom_typing_status(self) -> str:
        return _FF_TYPING_NOT_ASSIGNED

    @property
    def partial_charge_assignment_status(self) -> str:
        return _PARTIAL_CHARGE_NOT_ASSIGNED

    @property
    def force_field_atom_types_assigned(self) -> bool:
        return False

    @property
    def partial_charges_assigned(self) -> bool:
        return False

    @property
    def parameter_set_id(self) -> None:
        return None

    @property
    def parameter_assignment_sha256(self) -> None:
        return None

    @property
    def charge_model_id(self) -> None:
        return None

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def physics_supported(self) -> bool:
        return False

    @property
    def scientifically_validated(self) -> bool:
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        return False

    @property
    def virial_evaluation_authorized(self) -> bool:
        return False

    @property
    def minimization_authorized(self) -> bool:
        return False

    @property
    def runtime_ready(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def authority_granted(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        status = self._validated_state().typing_status
        prefix: tuple[str, ...]
        if status == _INVALID_SYSTEM:
            prefix = ("linear_alkane_typing_system_invalid",)
        elif status == _UNSUPPORTED_SYSTEM:
            prefix = ("linear_alkane_typing_profile_unsupported",)
        else:
            prefix = ()
        return (
            *prefix,
            "source_digest_is_not_authentication",
            "topological_environment_is_not_force_field_atom_type",
            "force_field_atom_types_not_assigned",
            "partial_charge_model_not_assigned",
            "partial_charges_not_assigned",
            "parameter_set_not_assigned",
            "parameterability_not_assessed",
            "physics_not_supported",
            "scientific_validation_not_established",
            "energy_evaluation_not_authorized",
            "force_evaluation_not_authorized",
            "virial_evaluation_not_authorized",
            "minimization_not_authorized",
            "runtime_not_ready",
            "simulation_not_authorized",
            "authority_not_granted",
            "claim_not_authorized",
        )

    def _core_dict(self) -> dict[str, Any]:
        state = self._validated_state()
        applicability = state.applicability
        canonical_bytes = object.__getattribute__(
            self,
            "_canonical_system_snapshot_bytes",
        )
        coverage_complete = state.typing_status == _ENVIRONMENTS_AVAILABLE
        source_partial_charge_count = sum(
            atom.partial_charge_e is not None for atom in state.system.atoms
        )
        return {
            "schema_id": (
                _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID
            ),
            "schema_version": (
                _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION
            ),
            "applicability_schema_id": (
                _FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_ID
            ),
            "applicability_schema_version": (
                _FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_SCHEMA_VERSION
            ),
            "applicability_profile_id": (
                _FROZEN_LINEAR_ALKANE_C1_C4_FORCE_FIELD_APPLICABILITY_PROFILE_ID
            ),
            "applicability_report_sha256": applicability.report_sha256,
            "applicability_status": applicability.applicability_status,
            "assignment_policy_id": (
                _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID
            ),
            "claim_scope": (
                _FROZEN_LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE
            ),
            "canonical_system_snapshot_sha256": hashlib.sha256(
                canonical_bytes
            ).hexdigest(),
            "canonical_topology_sha256": applicability.canonical_topology_sha256,
            "source_format": applicability.source_format,
            "source_sha256": applicability.source_sha256,
            "source_authentication_status": (
                applicability.source_authentication_status
            ),
            "topological_environment_typing_status": state.typing_status,
            "topological_environment_coverage_status": (
                _COVERAGE_COMPLETE if coverage_complete else _COVERAGE_NOT_AVAILABLE
            ),
            "topological_environment_coverage_complete": coverage_complete,
            "environment_assignment_count": len(state.assignments),
            "topological_environment_ids": sorted(
                {
                    assignment.topological_environment_id
                    for assignment in state.assignments
                }
            ),
            "environment_assignments": [
                assignment.to_dict() for assignment in state.assignments
            ],
            "formal_charge_observation_status": (
                _FORMAL_CHARGE_OBSERVED
                if coverage_complete
                else _FORMAL_CHARGE_NOT_AVAILABLE
            ),
            "source_partial_charge_count": source_partial_charge_count,
            "source_partial_charge_status": (
                _SOURCE_PARTIAL_CHARGE_ABSENT
                if source_partial_charge_count == 0
                else _SOURCE_PARTIAL_CHARGE_REJECTED
            ),
            "force_field_atom_typing_status": _FF_TYPING_NOT_ASSIGNED,
            "force_field_atom_types_assigned": False,
            "partial_charge_assignment_status": _PARTIAL_CHARGE_NOT_ASSIGNED,
            "partial_charges_assigned": False,
            "parameter_set_id": None,
            "parameter_assignment_sha256": None,
            "charge_model_id": None,
            "parameterability_assessed": False,
            "parameterizable": False,
            "physics_supported": False,
            "scientifically_validated": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "runtime_ready": False,
            "simulation_ready": False,
            "authority_granted": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def report_sha256(self) -> str:
        payload = json.dumps(
            self._core_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
        ).hexdigest()
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        self._validated_state()
        return self.to_dict() == analyze_linear_alkane_topological_environment_typing(
            system
        ).to_dict()


def analyze_linear_alkane_topological_environment_typing(
    system: AllAtomSystem,
) -> LinearAlkaneTopologicalEnvironmentTypingReport:
    """Derive graph-environment keys for the bounded applicable profile only."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return LinearAlkaneTopologicalEnvironmentTypingReport(system)


__all__ = [
    "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_ASSIGNMENT_POLICY_ID",
    "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_CLAIM_SCOPE",
    "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_ID",
    "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_SCHEMA_VERSION",
    "LINEAR_ALKANE_TOPOLOGICAL_ENVIRONMENT_TYPING_STATUSES",
    "LinearAlkaneTopologicalEnvironmentAssignment",
    "LinearAlkaneTopologicalEnvironmentTypingReport",
    "TopologicalEnvironmentTypingContractError",
    "analyze_linear_alkane_topological_environment_typing",
]
