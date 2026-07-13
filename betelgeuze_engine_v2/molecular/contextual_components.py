"""Fail-closed contextual component inventory for canonical molecular state.

The inventory preserves residue-local observations already represented by an
``AllAtomSystem``.  It deliberately does not interpret residue names, element
symbols, formal charges, or hetero markers as water, ion, metal, cofactor, or
modified-residue roles.  Parser pedigree and source digests are retained only
as observation metadata; neither authenticates a source nor establishes a
contextual chemical role.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem
from .preparation import (
    PREPARATION_POLICY_ID,
    PREPARATION_REPORT_SCHEMA_VERSION,
    MolecularPreparationReport,
    PreparationCoverageLimitError,
    analyze_molecular_preparation,
)
from .topology import CANONICAL_TOPOLOGY_SCHEMA_ID, canonical_topology_sha256


CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION = "1.0.0"
CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID = (
    "betelgeuze.contextual_component_inventory/"
    f"{CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION}"
)
CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE = (
    "canonical_component_observation_only"
)
CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS = (
    "not_authenticated"
)

CANONICAL_MARKER_OBSERVED_STATUS = "canonical_marker_observed"
CANONICAL_MARKER_NOT_OBSERVED_STATUS = "canonical_marker_not_observed"
CONTEXTUAL_COMPONENT_UNASSESSED_STATUS = "unassessed"

CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS = (
    "canonical_component_markers_are_not_contextual_role_evidence",
    "connection_context_unassessed",
    "source_authentication_not_established",
    "water_role_unassessed",
    "ion_role_unassessed",
    "metal_role_unassessed",
    "metal_coordination_unassessed",
    "oxidation_state_unassessed",
    "cofactor_role_unassessed",
    "modified_residue_identity_unassessed",
    "chemistry_support_not_established",
    "preparation_not_assessed",
    "preparation_not_ready",
    "parameterability_not_assessed",
    "parameterization_not_authorized",
    "simulation_not_authorized",
    "claim_not_authorized",
)

_MAX_JSON_INTEGER = (1 << 53) - 1
_MARKER_STATUSES = frozenset(
    {
        CANONICAL_MARKER_OBSERVED_STATUS,
        CANONICAL_MARKER_NOT_OBSERVED_STATUS,
    }
)


def _validate_nonnegative_count(name: str, value: Any) -> None:
    if type(value) is not int or value < 0:
        raise TypeError(f"{name} must be a non-negative integer")
    if value > _MAX_JSON_INTEGER:
        raise ValueError(f"{name} exceeds the interoperable JSON integer range")


def _validate_element_counts(value: Any) -> None:
    if type(value) is not tuple:
        raise TypeError("element_counts must be a tuple")
    previous: str | None = None
    for entry in value:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or not entry[0]
            or type(entry[1]) is not int
            or entry[1] <= 0
        ):
            raise TypeError(
                "element_counts entries must be nonempty-string/positive-integer pairs"
            )
        if entry[1] > _MAX_JSON_INTEGER:
            raise ValueError(
                "element_counts count exceeds the interoperable JSON integer range"
            )
        if previous is not None and entry[0] <= previous:
            raise ValueError("element_counts keys must be unique and sorted")
        previous = entry[0]


@dataclass(frozen=True)
class CanonicalComponentObservation:
    """Immutable residue-local facts visible in the canonical system."""

    residue_index: int
    residue_name: str
    entity_type: str
    hetero: bool
    atom_indices: tuple[int, ...]
    atom_count: int
    element_counts: tuple[tuple[str, int], ...]
    formal_charge_known_count: int
    formal_charge_unknown_count: int
    canonical_net_formal_charge: int | None
    canonical_water_entity_marker_status: str
    canonical_known_charged_monatomic_marker_status: str
    canonical_polymer_hetero_marker_status: str
    connection_context_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    water_role_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    ion_role_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    metal_role_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    metal_coordination_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    oxidation_state_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    cofactor_role_status: str = CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    modified_residue_identity_status: str = (
        CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
    )

    def __post_init__(self) -> None:
        _validate_nonnegative_count("residue_index", self.residue_index)
        if type(self.residue_name) is not str or not self.residue_name:
            raise TypeError("residue_name must be a nonempty string")
        if type(self.entity_type) is not str:
            raise TypeError("entity_type must be a string")
        if type(self.hetero) is not bool:
            raise TypeError("hetero must be a boolean")
        if type(self.atom_indices) is not tuple or not all(
            type(index) is int for index in self.atom_indices
        ):
            raise TypeError("atom_indices must be a tuple of integers")
        if any(index < 0 or index > _MAX_JSON_INTEGER for index in self.atom_indices):
            raise ValueError(
                "atom_indices must contain non-negative interoperable JSON integers"
            )
        if any(
            first >= second
            for first, second in zip(self.atom_indices, self.atom_indices[1:])
        ):
            raise ValueError("atom_indices must be unique and sorted")
        for name in (
            "atom_count",
            "formal_charge_known_count",
            "formal_charge_unknown_count",
        ):
            _validate_nonnegative_count(name, getattr(self, name))
        if self.atom_count != len(self.atom_indices):
            raise ValueError("atom_count must match atom_indices")
        _validate_element_counts(self.element_counts)
        if sum(count for _, count in self.element_counts) != self.atom_count:
            raise ValueError("element_counts must sum to atom_count")
        if (
            self.formal_charge_known_count + self.formal_charge_unknown_count
            != self.atom_count
        ):
            raise ValueError(
                "formal-charge known and unknown counts must sum to atom_count"
            )
        if self.formal_charge_unknown_count:
            if self.canonical_net_formal_charge is not None:
                raise ValueError(
                    "canonical_net_formal_charge must be None when any formal charge is unknown"
                )
        elif type(self.canonical_net_formal_charge) is not int:
            raise TypeError(
                "canonical_net_formal_charge must be an integer when all formal charges are known"
            )
        elif abs(self.canonical_net_formal_charge) > _MAX_JSON_INTEGER:
            raise ValueError(
                "canonical_net_formal_charge exceeds the interoperable JSON integer range"
            )

        marker_statuses = {
            "canonical_water_entity_marker_status": (
                self.canonical_water_entity_marker_status
            ),
            "canonical_known_charged_monatomic_marker_status": (
                self.canonical_known_charged_monatomic_marker_status
            ),
            "canonical_polymer_hetero_marker_status": (
                self.canonical_polymer_hetero_marker_status
            ),
        }
        invalid_marker = next(
            (
                name
                for name, status in marker_statuses.items()
                if status not in _MARKER_STATUSES
            ),
            None,
        )
        if invalid_marker is not None:
            raise ValueError(f"{invalid_marker} is unsupported")

        expected_water_marker = (
            CANONICAL_MARKER_OBSERVED_STATUS
            if self.entity_type == "water"
            else CANONICAL_MARKER_NOT_OBSERVED_STATUS
        )
        if self.canonical_water_entity_marker_status != expected_water_marker:
            raise ValueError(
                "canonical water marker must exactly match entity_type=='water'"
            )
        expected_charged_monatomic_marker = (
            CANONICAL_MARKER_OBSERVED_STATUS
            if (
                self.atom_count == 1
                and self.formal_charge_known_count == 1
                and self.canonical_net_formal_charge not in (None, 0)
            )
            else CANONICAL_MARKER_NOT_OBSERVED_STATUS
        )
        if (
            self.canonical_known_charged_monatomic_marker_status
            != expected_charged_monatomic_marker
        ):
            raise ValueError(
                "canonical charged monatomic marker must exactly match one known nonzero formal charge"
            )
        expected_polymer_hetero_marker = (
            CANONICAL_MARKER_OBSERVED_STATUS
            if self.entity_type == "polymer" and self.hetero
            else CANONICAL_MARKER_NOT_OBSERVED_STATUS
        )
        if (
            self.canonical_polymer_hetero_marker_status
            != expected_polymer_hetero_marker
        ):
            raise ValueError(
                "canonical polymer hetero marker must exactly match polymer and hetero state"
            )

        role_statuses = (
            self.connection_context_status,
            self.water_role_status,
            self.ion_role_status,
            self.metal_role_status,
            self.metal_coordination_status,
            self.oxidation_state_status,
            self.cofactor_role_status,
            self.modified_residue_identity_status,
        )
        if any(
            status != CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
            for status in role_statuses
        ):
            raise ValueError(
                "contextual component role and connection statuses must remain unassessed"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "residue_index": self.residue_index,
            "residue_name": self.residue_name,
            "entity_type": self.entity_type,
            "hetero": self.hetero,
            "atom_indices": list(self.atom_indices),
            "atom_count": self.atom_count,
            "element_counts": [list(item) for item in self.element_counts],
            "formal_charge_known_count": self.formal_charge_known_count,
            "formal_charge_unknown_count": self.formal_charge_unknown_count,
            "canonical_net_formal_charge": self.canonical_net_formal_charge,
            "canonical_water_entity_marker_status": (
                self.canonical_water_entity_marker_status
            ),
            "canonical_known_charged_monatomic_marker_status": (
                self.canonical_known_charged_monatomic_marker_status
            ),
            "canonical_polymer_hetero_marker_status": (
                self.canonical_polymer_hetero_marker_status
            ),
            "connection_context_status": self.connection_context_status,
            "water_role_status": self.water_role_status,
            "ion_role_status": self.ion_role_status,
            "metal_role_status": self.metal_role_status,
            "metal_coordination_status": self.metal_coordination_status,
            "oxidation_state_status": self.oxidation_state_status,
            "cofactor_role_status": self.cofactor_role_status,
            "modified_residue_identity_status": (
                self.modified_residue_identity_status
            ),
        }


def _canonical_marker_status(observed: bool) -> str:
    return (
        CANONICAL_MARKER_OBSERVED_STATUS
        if observed
        else CANONICAL_MARKER_NOT_OBSERVED_STATUS
    )


def _observe_components(
    system: AllAtomSystem,
) -> tuple[CanonicalComponentObservation, ...]:
    observations: list[CanonicalComponentObservation] = []
    for residue in system.residues:
        atoms = tuple(system.atoms[index] for index in residue.atom_indices)
        unknown_charge_count = sum(
            not atom.formal_charge_known for atom in atoms
        )
        known_charge_count = len(atoms) - unknown_charge_count
        observed_net_charge = (
            None
            if unknown_charge_count
            else sum(atom.formal_charge for atom in atoms)
        )
        observations.append(
            CanonicalComponentObservation(
                residue_index=residue.index,
                residue_name=residue.name,
                entity_type=residue.entity_type,
                hetero=residue.hetero,
                atom_indices=residue.atom_indices,
                atom_count=len(atoms),
                element_counts=tuple(
                    sorted(Counter(atom.element for atom in atoms).items())
                ),
                formal_charge_known_count=known_charge_count,
                formal_charge_unknown_count=unknown_charge_count,
                canonical_net_formal_charge=observed_net_charge,
                canonical_water_entity_marker_status=_canonical_marker_status(
                    residue.entity_type == "water"
                ),
                canonical_known_charged_monatomic_marker_status=(
                    _canonical_marker_status(
                        len(atoms) == 1
                        and atoms[0].formal_charge_known
                        and atoms[0].formal_charge != 0
                    )
                ),
                canonical_polymer_hetero_marker_status=(
                    _canonical_marker_status(
                        residue.entity_type == "polymer" and residue.hetero
                    )
                ),
            )
        )
    return tuple(observations)


@dataclass(frozen=True, init=False)
class ContextualComponentInventoryReport:
    """Factory-only report bound to one freshly analyzed canonical system."""

    preparation_report: MolecularPreparationReport
    system_schema_id: str
    source_format: str
    source_sha256: str | None
    source_digest_available: bool
    source_authentication_status: str
    parser_pedigree_id: str
    parser_observation_self_consistent: bool
    canonical_topology_schema_id: str
    canonical_topology_sha256: str
    preparation_report_schema_version: str
    preparation_policy_id: str
    preparation_report_sha256: str
    atom_count: int
    residue_count: int
    components: tuple[CanonicalComponentObservation, ...]
    contextual_role_status: str
    connection_context_status: str
    water_role_status: str
    ion_role_status: str
    metal_role_status: str
    metal_coordination_status: str
    oxidation_state_status: str
    cofactor_role_status: str
    modified_residue_identity_status: str
    chemistry_supported: bool
    preparation_assessed: bool
    preparation_ready: bool
    parameterability_assessed: bool
    parameterizable: bool
    simulation_ready: bool
    claim_safe: bool
    blockers: tuple[str, ...]

    def __init__(self, system: AllAtomSystem) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        preparation = analyze_molecular_preparation(system)
        if type(preparation) is not MolecularPreparationReport:
            raise TypeError(
                "analyze_molecular_preparation must return a MolecularPreparationReport"
            )
        if (
            not preparation.canonical_validation_valid
            or not preparation.canonical_topology_digest_available
            or preparation.canonical_topology_sha256 is None
        ):
            raise ValueError(
                "contextual component inventory requires a valid canonical topology digest"
            )
        fresh_topology_sha256 = canonical_topology_sha256(system)
        if preparation.canonical_topology_sha256 != fresh_topology_sha256:
            raise ValueError(
                "fresh canonical topology digest does not match preparation evidence"
            )
        components = _observe_components(system)

        object.__setattr__(self, "preparation_report", preparation)
        object.__setattr__(self, "system_schema_id", system.schema_id)
        object.__setattr__(self, "source_format", preparation.source_format)
        object.__setattr__(self, "source_sha256", preparation.source_sha256)
        object.__setattr__(
            self,
            "source_digest_available",
            preparation.source_digest_available,
        )
        object.__setattr__(
            self,
            "source_authentication_status",
            CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS,
        )
        object.__setattr__(
            self,
            "parser_pedigree_id",
            preparation.parser_pedigree_id,
        )
        object.__setattr__(
            self,
            "parser_observation_self_consistent",
            preparation.parser_observation_self_consistent,
        )
        object.__setattr__(
            self,
            "canonical_topology_schema_id",
            CANONICAL_TOPOLOGY_SCHEMA_ID,
        )
        object.__setattr__(
            self,
            "canonical_topology_sha256",
            fresh_topology_sha256,
        )
        object.__setattr__(
            self,
            "preparation_report_schema_version",
            PREPARATION_REPORT_SCHEMA_VERSION,
        )
        object.__setattr__(self, "preparation_policy_id", PREPARATION_POLICY_ID)
        object.__setattr__(
            self,
            "preparation_report_sha256",
            preparation.report_sha256,
        )
        object.__setattr__(self, "atom_count", len(system.atoms))
        object.__setattr__(self, "residue_count", len(system.residues))
        object.__setattr__(self, "components", components)
        for status_field in (
            "contextual_role_status",
            "connection_context_status",
            "water_role_status",
            "ion_role_status",
            "metal_role_status",
            "metal_coordination_status",
            "oxidation_state_status",
            "cofactor_role_status",
            "modified_residue_identity_status",
        ):
            object.__setattr__(
                self,
                status_field,
                CONTEXTUAL_COMPONENT_UNASSESSED_STATUS,
            )
        for false_field in (
            "chemistry_supported",
            "preparation_assessed",
            "preparation_ready",
            "parameterability_assessed",
            "parameterizable",
            "simulation_ready",
            "claim_safe",
        ):
            object.__setattr__(self, false_field, False)
        object.__setattr__(
            self,
            "blockers",
            CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS,
        )
        self._validate_bound_state(system, fresh_topology_sha256)

    def _validate_bound_state(
        self,
        system: AllAtomSystem,
        fresh_topology_sha256: str,
    ) -> None:
        preparation = self.preparation_report
        if type(preparation) is not MolecularPreparationReport:
            raise TypeError("preparation_report must be a MolecularPreparationReport")
        if self.system_schema_id != system.schema_id:
            raise ValueError("system schema binding mismatch")
        if self.source_format != system.provenance.source_format:
            raise ValueError("source format binding mismatch")
        expected_source_sha256 = system.provenance.source_sha256 or None
        if (
            self.source_sha256 != expected_source_sha256
            or self.source_digest_available != (expected_source_sha256 is not None)
        ):
            raise ValueError("source SHA-256 binding mismatch")
        if (
            self.source_authentication_status
            != CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS
        ):
            raise ValueError("source authentication must remain explicitly unproven")
        if (
            self.source_format != preparation.source_format
            or self.source_sha256 != preparation.source_sha256
            or self.source_digest_available
            != preparation.source_digest_available
            or self.parser_pedigree_id != preparation.parser_pedigree_id
            or self.parser_observation_self_consistent
            != preparation.parser_observation_self_consistent
        ):
            raise ValueError("preparation observation metadata binding mismatch")
        if (
            self.canonical_topology_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID
            or self.canonical_topology_sha256 != fresh_topology_sha256
            or preparation.canonical_topology_schema_id
            != CANONICAL_TOPOLOGY_SCHEMA_ID
            or preparation.canonical_topology_sha256
            != fresh_topology_sha256
        ):
            raise ValueError("canonical topology binding mismatch")
        if (
            self.preparation_report_schema_version
            != PREPARATION_REPORT_SCHEMA_VERSION
            or self.preparation_policy_id != PREPARATION_POLICY_ID
            or preparation.policy_id != PREPARATION_POLICY_ID
            or self.preparation_report_sha256 != preparation.report_sha256
        ):
            raise ValueError("preparation report binding mismatch")
        _validate_nonnegative_count("atom_count", self.atom_count)
        _validate_nonnegative_count("residue_count", self.residue_count)
        if self.atom_count != len(system.atoms):
            raise ValueError("atom_count must match the bound system")
        if self.residue_count != len(system.residues):
            raise ValueError("residue_count must match the bound system")
        if type(self.components) is not tuple or not all(
            type(component) is CanonicalComponentObservation
            for component in self.components
        ):
            raise TypeError(
                "components must be a tuple of CanonicalComponentObservation rows"
            )
        if self.components != _observe_components(system):
            raise ValueError("component observations must match the bound system")
        if len(self.components) != self.residue_count:
            raise ValueError("components must contain one row per residue")
        if sum(component.atom_count for component in self.components) != self.atom_count:
            raise ValueError("component atom counts must sum to atom_count")
        status_values = (
            self.contextual_role_status,
            self.connection_context_status,
            self.water_role_status,
            self.ion_role_status,
            self.metal_role_status,
            self.metal_coordination_status,
            self.oxidation_state_status,
            self.cofactor_role_status,
            self.modified_residue_identity_status,
        )
        if any(
            status != CONTEXTUAL_COMPONENT_UNASSESSED_STATUS
            for status in status_values
        ):
            raise ValueError("all contextual role statuses must remain unassessed")
        false_flags = (
            self.chemistry_supported,
            self.preparation_assessed,
            self.preparation_ready,
            self.parameterability_assessed,
            self.parameterizable,
            self.simulation_ready,
            self.claim_safe,
        )
        if not all(type(flag) is bool for flag in false_flags):
            raise TypeError("inventory gate flags must be booleans")
        if any(false_flags):
            raise ValueError("contextual inventory cannot promote readiness or claims")
        if self.blockers != CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS:
            raise ValueError("blockers must match the exact ordered blocker set")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID,
            "schema_version": CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION,
            "claim_scope": CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE,
            "system_schema_id": self.system_schema_id,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "source_digest_available": self.source_digest_available,
            "source_authentication_status": self.source_authentication_status,
            "parser_pedigree_id": self.parser_pedigree_id,
            "parser_observation_self_consistent": (
                self.parser_observation_self_consistent
            ),
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "preparation_report_schema_version": (
                self.preparation_report_schema_version
            ),
            "preparation_policy_id": self.preparation_policy_id,
            "preparation_report_sha256": self.preparation_report_sha256,
            "atom_count": self.atom_count,
            "residue_count": self.residue_count,
            "components": [component.to_dict() for component in self.components],
            "contextual_role_status": self.contextual_role_status,
            "connection_context_status": self.connection_context_status,
            "water_role_status": self.water_role_status,
            "ion_role_status": self.ion_role_status,
            "metal_role_status": self.metal_role_status,
            "metal_coordination_status": self.metal_coordination_status,
            "oxidation_state_status": self.oxidation_state_status,
            "cofactor_role_status": self.cofactor_role_status,
            "modified_residue_identity_status": (
                self.modified_residue_identity_status
            ),
            "chemistry_supported": self.chemistry_supported,
            "preparation_assessed": self.preparation_assessed,
            "preparation_ready": self.preparation_ready,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "simulation_ready": self.simulation_ready,
            "claim_safe": self.claim_safe,
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
        payload["report_sha256"] = self.report_sha256
        return payload

    def matches_system(self, system: AllAtomSystem) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        try:
            current = analyze_contextual_component_inventory(system)
        except PreparationCoverageLimitError:
            raise
        except (TypeError, ValueError, OverflowError):
            return False
        return self.to_dict() == current.to_dict()


def analyze_contextual_component_inventory(
    system: AllAtomSystem,
) -> ContextualComponentInventoryReport:
    """Observe canonical component markers without assigning chemical roles."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    return ContextualComponentInventoryReport(system)


__all__ = [
    "CANONICAL_MARKER_NOT_OBSERVED_STATUS",
    "CANONICAL_MARKER_OBSERVED_STATUS",
    "CONTEXTUAL_COMPONENT_INVENTORY_BLOCKERS",
    "CONTEXTUAL_COMPONENT_INVENTORY_CLAIM_SCOPE",
    "CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_ID",
    "CONTEXTUAL_COMPONENT_INVENTORY_SCHEMA_VERSION",
    "CONTEXTUAL_COMPONENT_SOURCE_AUTHENTICATION_STATUS",
    "CONTEXTUAL_COMPONENT_UNASSESSED_STATUS",
    "CanonicalComponentObservation",
    "ContextualComponentInventoryReport",
    "analyze_contextual_component_inventory",
]
