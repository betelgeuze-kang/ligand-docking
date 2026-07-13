"""Dependency-free chemistry coverage audit for canonical molecular graphs.

This module deliberately separates graph representability from supported
chemistry and parameterability.  The first report version never authorizes
numeric chemistry: it inventories typed state, independently checks a small
set of graph invariants, and returns explicit blockers for every scientific
layer that is not yet implemented.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from .models import AllAtomSystem, atomic_number_for_element
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    NON_TOPOLOGY_STATE_VALIDATION_ERROR_CODES,
    CanonicalTopologyError,
    canonical_topology_sha256_for_valid_topology,
)
from .validation import validate_all_atom_system


CHEMISTRY_COVERAGE_SCHEMA_VERSION = "1.2.0"
ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID = (
    "organic_graph_encoding_inventory_v1"
)

_PROFILE_ELEMENTS = frozenset({"H", "B", "C", "N", "O", "F", "Si", "P", "S", "Cl", "Br", "I"})
_PROFILE_BOND_ORDERS = frozenset({1.0, 1.5, 2.0, 3.0})
_MAX_REPORT_JSON_INTEGER = (1 << 53) - 1
MAX_CHEMISTRY_AUDIT_ATOMS = 100_000
MAX_CHEMISTRY_AUDIT_BONDS = 200_000
_ALWAYS_BLOCKERS = (
    "electronic_spin_state_not_typed",
    "bond_topology_completeness_not_independently_provable",
    "hydrogen_completeness_not_independently_provable",
    "valence_profile_not_implemented",
    "protonation_not_independently_assessed",
    "tautomer_not_independently_assessed",
    "parameter_assignment_not_implemented",
    "parameterability_not_assessed",
)


def _validate_count_table(name: str, value: Any) -> None:
    if type(value) is not tuple:
        raise TypeError(f"{name} must be a tuple")
    previous: str | None = None
    for entry in value:
        if (
            type(entry) is not tuple
            or len(entry) != 2
            or type(entry[0]) is not str
            or type(entry[1]) is not int
            or entry[1] <= 0
        ):
            raise TypeError(
                f"{name} entries must be string/positive integer pairs"
            )
        if entry[1] > _MAX_REPORT_JSON_INTEGER:
            raise ValueError(
                f"{name} count exceeds the interoperable JSON integer range"
            )
        if previous is not None and entry[0] <= previous:
            raise ValueError(f"{name} keys must be unique and sorted")
        previous = entry[0]


@dataclass(frozen=True)
class ChemistryCoverageReport:
    profile_id: str
    system_schema_id: str
    canonical_topology_schema_id: str
    canonical_topology_sha256: str | None
    canonical_topology_digest_available: bool
    topology_validation_valid: bool
    topology_validation_error_codes: tuple[str, ...]
    atom_count: int
    bond_count: int
    component_count: int
    elements: tuple[str, ...]
    element_counts: tuple[tuple[str, int], ...]
    outside_profile_elements: tuple[str, ...]
    element_atomic_number_identity_valid: bool
    net_formal_charge: int | None
    net_formal_charge_known: bool
    unknown_formal_charge_count: int
    formal_charge_outside_profile_count: int
    isotope_count: int
    atom_map_count: int
    atom_map_contract_valid: bool
    aromatic_atom_count: int
    aromatic_bond_count: int
    assigned_atom_stereo_count: int
    unknown_atom_stereo_count: int
    assigned_bond_stereo_count: int
    unknown_bond_stereo_count: int
    bond_graph_contract_valid: bool
    bond_order_outside_profile_count: int
    aromatic_cycle_contract_valid: bool
    stereo_topology_contract_valid: bool
    bond_stereo_outside_profile_count: int
    coordinates_present: bool
    provenance_preparation_ready_attested: bool
    canonical_validation_valid: bool
    graph_representable: bool
    validation_error_codes: tuple[str, ...]
    blockers: tuple[str, ...]
    chemistry_supported: bool = False
    parameterability_assessed: bool = False
    parameterizable: bool = False
    claim_safe: bool = False

    def __post_init__(self) -> None:
        if self.profile_id != ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID:
            raise ValueError(
                "chemistry coverage v1.2 requires the fixed encoding-inventory profile"
            )
        if type(self.system_schema_id) is not str or not self.system_schema_id:
            raise TypeError("system_schema_id must be a nonempty string")
        boolean_fields = {
            "net_formal_charge_known": self.net_formal_charge_known,
            "canonical_topology_digest_available": self.canonical_topology_digest_available,
            "topology_validation_valid": self.topology_validation_valid,
            "element_atomic_number_identity_valid": (
                self.element_atomic_number_identity_valid
            ),
            "atom_map_contract_valid": self.atom_map_contract_valid,
            "bond_graph_contract_valid": self.bond_graph_contract_valid,
            "aromatic_cycle_contract_valid": self.aromatic_cycle_contract_valid,
            "stereo_topology_contract_valid": self.stereo_topology_contract_valid,
            "coordinates_present": self.coordinates_present,
            "provenance_preparation_ready_attested": (
                self.provenance_preparation_ready_attested
            ),
            "canonical_validation_valid": self.canonical_validation_valid,
            "graph_representable": self.graph_representable,
            "chemistry_supported": self.chemistry_supported,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "claim_safe": self.claim_safe,
        }
        invalid_boolean = next(
            (name for name, value in boolean_fields.items() if type(value) is not bool),
            None,
        )
        if invalid_boolean is not None:
            raise TypeError(f"{invalid_boolean} must be a boolean")
        if self.canonical_topology_schema_id != CANONICAL_TOPOLOGY_SCHEMA_ID:
            raise ValueError(
                "chemistry coverage v1.2 requires the fixed canonical topology schema"
            )
        if self.canonical_topology_digest_available != (
            self.canonical_topology_sha256 is not None
        ):
            raise ValueError(
                "canonical_topology_digest_available must match canonical_topology_sha256"
            )
        if self.canonical_topology_sha256 is not None and (
            type(self.canonical_topology_sha256) is not str
            or len(self.canonical_topology_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.canonical_topology_sha256
            )
        ):
            raise ValueError("canonical_topology_sha256 must be lowercase SHA-256 or None")
        if self.canonical_topology_digest_available and not self.topology_validation_valid:
            raise ValueError(
                "canonical topology digest cannot be available for invalid topology"
            )
        if (
            self.system_schema_id == "betelgeuze.all_atom_system/2.1.0"
            and self.topology_validation_valid
            and not self.canonical_topology_digest_available
        ):
            raise ValueError(
                "valid schema-2.1 topology requires an available canonical digest"
            )
        count_fields = (
            "atom_count",
            "bond_count",
            "component_count",
            "unknown_formal_charge_count",
            "formal_charge_outside_profile_count",
            "isotope_count",
            "atom_map_count",
            "aromatic_atom_count",
            "aromatic_bond_count",
            "assigned_atom_stereo_count",
            "unknown_atom_stereo_count",
            "assigned_bond_stereo_count",
            "unknown_bond_stereo_count",
            "bond_order_outside_profile_count",
            "bond_stereo_outside_profile_count",
        )
        for name in count_fields:
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{name} must be a non-negative integer")
            if value > _MAX_REPORT_JSON_INTEGER:
                raise ValueError(
                    f"{name} exceeds the interoperable JSON integer range"
                )
        if self.component_count > self.atom_count or (
            self.atom_count > 0 and self.component_count < 1
        ):
            raise ValueError("component_count must be consistent with atom_count")
        atom_subset_counts = (
            self.unknown_formal_charge_count,
            self.formal_charge_outside_profile_count,
            self.isotope_count,
            self.atom_map_count,
            self.aromatic_atom_count,
            self.assigned_atom_stereo_count,
            self.unknown_atom_stereo_count,
        )
        if any(count > self.atom_count for count in atom_subset_counts):
            raise ValueError("atom subset counts cannot exceed atom_count")
        if (
            self.assigned_atom_stereo_count + self.unknown_atom_stereo_count
            > self.atom_count
        ):
            raise ValueError(
                "assigned and unknown atom stereo counts cannot exceed atom_count"
            )
        bond_subset_counts = (
            self.aromatic_bond_count,
            self.assigned_bond_stereo_count,
            self.unknown_bond_stereo_count,
            self.bond_order_outside_profile_count,
            self.bond_stereo_outside_profile_count,
        )
        if any(count > self.bond_count for count in bond_subset_counts):
            raise ValueError("bond subset counts cannot exceed bond_count")
        if (
            self.assigned_bond_stereo_count + self.unknown_bond_stereo_count
            > self.bond_count
        ):
            raise ValueError(
                "assigned and unknown bond stereo counts cannot exceed bond_count"
            )
        if (
            type(self.elements) is not tuple
            or not all(type(value) is str for value in self.elements)
            or tuple(sorted(set(self.elements))) != self.elements
        ):
            raise ValueError("elements must be a sorted tuple of unique strings")
        _validate_count_table("element_counts", self.element_counts)
        if sum(count for _, count in self.element_counts) != self.atom_count:
            raise ValueError("element_counts must sum to atom_count")
        if tuple(element for element, _ in self.element_counts) != self.elements:
            raise ValueError("element_counts keys must exactly match elements")
        if (
            type(self.outside_profile_elements) is not tuple
            or not all(type(value) is str for value in self.outside_profile_elements)
            or tuple(sorted(set(self.outside_profile_elements)))
            != self.outside_profile_elements
            or not set(self.outside_profile_elements).issubset(self.elements)
        ):
            raise ValueError(
                "outside_profile_elements must be a sorted unique subset of elements"
            )
        if self.net_formal_charge_known != (self.unknown_formal_charge_count == 0):
            raise ValueError(
                "net_formal_charge_known must match unknown_formal_charge_count"
            )
        if self.net_formal_charge_known:
            if type(self.net_formal_charge) is not int:
                raise TypeError("known net_formal_charge must be an integer")
            if abs(self.net_formal_charge) > _MAX_REPORT_JSON_INTEGER:
                raise ValueError(
                    "net_formal_charge exceeds the interoperable JSON integer range"
                )
        elif self.net_formal_charge is not None:
            raise ValueError("unknown net_formal_charge must be None")
        for name, error_codes in (
            ("validation_error_codes", self.validation_error_codes),
            (
                "topology_validation_error_codes",
                self.topology_validation_error_codes,
            ),
        ):
            if (
                type(error_codes) is not tuple
                or not all(type(value) is str and value for value in error_codes)
            ):
                raise TypeError(f"{name} must be a tuple of nonempty strings")
            if error_codes != tuple(sorted(set(error_codes))):
                raise ValueError(f"{name} must be unique and sorted")
        expected_topology_errors = _graph_validation_errors(
            self.validation_error_codes
        )
        if self.topology_validation_error_codes != expected_topology_errors:
            raise ValueError(
                "topology_validation_error_codes must match topology-affecting validation errors"
            )
        if (
            type(self.blockers) is not tuple
            or not all(type(value) is str and value for value in self.blockers)
        ):
            raise TypeError("blockers must be a tuple of nonempty strings")
        if self.canonical_validation_valid != (not self.validation_error_codes):
            raise ValueError(
                "canonical_validation_valid must match validation_error_codes"
            )
        if self.topology_validation_valid != (
            not self.topology_validation_error_codes
        ):
            raise ValueError(
                "topology_validation_valid must match topology_validation_error_codes"
            )
        expected_graph_representable = bool(
            self.topology_validation_valid
            and self.element_atomic_number_identity_valid
            and self.atom_map_contract_valid
            and self.bond_graph_contract_valid
            and self.aromatic_cycle_contract_valid
            and self.stereo_topology_contract_valid
        )
        if self.graph_representable != expected_graph_representable:
            raise ValueError(
                "graph_representable must match all graph contract diagnostics"
            )
        expected_blockers = list(_ALWAYS_BLOCKERS)
        if not self.canonical_validation_valid:
            expected_blockers.append("canonical_validation_errors_present")
        if not self.canonical_topology_digest_available:
            expected_blockers.append("canonical_topology_digest_unavailable")
        if self.outside_profile_elements:
            expected_blockers.append(
                "elements_outside_organic_graph_inventory_profile"
            )
        if not self.element_atomic_number_identity_valid:
            expected_blockers.append("element_atomic_number_identity_invalid")
        if not self.atom_map_contract_valid:
            expected_blockers.append("atom_map_contract_invalid")
        if self.unknown_formal_charge_count:
            expected_blockers.append("formal_charge_unknown_for_some_atoms")
        if self.formal_charge_outside_profile_count:
            expected_blockers.append("formal_charge_outside_profile_range")
        if self.isotope_count:
            expected_blockers.extend(
                (
                    "isotope_parameter_coverage_not_assessed",
                    "physical_nuclide_validity_not_assessed",
                )
            )
        if not self.bond_graph_contract_valid:
            expected_blockers.append("bond_graph_contract_invalid")
        if self.bond_order_outside_profile_count:
            expected_blockers.append("bond_order_outside_profile")
        if not self.aromatic_cycle_contract_valid:
            expected_blockers.append("aromatic_cycle_contract_invalid")
        if self.bond_stereo_outside_profile_count:
            expected_blockers.append("bond_stereo_outside_profile")
        if not self.stereo_topology_contract_valid:
            expected_blockers.append("stereo_topology_contract_invalid")
        if self.unknown_atom_stereo_count or self.unknown_bond_stereo_count:
            expected_blockers.append("stereochemistry_incomplete_or_unknown")
        if self.assigned_atom_stereo_count or self.assigned_bond_stereo_count:
            expected_blockers.extend(
                (
                    "cip_assignment_not_independently_verified",
                    "stereo_substituent_equivalence_not_independently_verified",
                )
            )
        if self.component_count > 1:
            expected_blockers.append("disconnected_fragment_roles_not_assessed")
        if self.aromatic_atom_count or self.aromatic_bond_count:
            expected_blockers.append(
                "aromaticity_perception_not_independently_available"
            )
        if not self.coordinates_present:
            expected_blockers.append("coordinates_missing")
        if not self.provenance_preparation_ready_attested:
            expected_blockers.append("preparation_not_complete")
        if self.blockers != tuple(expected_blockers):
            raise ValueError(
                "blockers must exactly match the canonical ordered blocker set"
            )
        if (
            self.chemistry_supported
            or self.parameterability_assessed
            or self.parameterizable
            or self.claim_safe
        ):
            raise ValueError(
                "chemistry coverage v1.2 cannot promote chemistry, parameterability, or claims"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CHEMISTRY_COVERAGE_SCHEMA_VERSION,
            "profile_id": self.profile_id,
            "system_schema_id": self.system_schema_id,
            "canonical_topology_schema_id": self.canonical_topology_schema_id,
            "canonical_topology_sha256": self.canonical_topology_sha256,
            "canonical_topology_digest_available": self.canonical_topology_digest_available,
            "topology_validation_valid": self.topology_validation_valid,
            "topology_validation_error_codes": list(
                self.topology_validation_error_codes
            ),
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "component_count": self.component_count,
            "elements": list(self.elements),
            "element_counts": [list(item) for item in self.element_counts],
            "outside_profile_elements": list(self.outside_profile_elements),
            "element_atomic_number_identity_valid": (
                self.element_atomic_number_identity_valid
            ),
            "net_formal_charge": self.net_formal_charge,
            "net_formal_charge_known": self.net_formal_charge_known,
            "unknown_formal_charge_count": self.unknown_formal_charge_count,
            "formal_charge_outside_profile_count": (
                self.formal_charge_outside_profile_count
            ),
            "isotope_count": self.isotope_count,
            "atom_map_count": self.atom_map_count,
            "atom_map_contract_valid": self.atom_map_contract_valid,
            "aromatic_atom_count": self.aromatic_atom_count,
            "aromatic_bond_count": self.aromatic_bond_count,
            "assigned_atom_stereo_count": self.assigned_atom_stereo_count,
            "unknown_atom_stereo_count": self.unknown_atom_stereo_count,
            "assigned_bond_stereo_count": self.assigned_bond_stereo_count,
            "unknown_bond_stereo_count": self.unknown_bond_stereo_count,
            "bond_graph_contract_valid": self.bond_graph_contract_valid,
            "bond_order_outside_profile_count": (
                self.bond_order_outside_profile_count
            ),
            "aromatic_cycle_contract_valid": self.aromatic_cycle_contract_valid,
            "stereo_topology_contract_valid": self.stereo_topology_contract_valid,
            "bond_stereo_outside_profile_count": (
                self.bond_stereo_outside_profile_count
            ),
            "coordinates_present": self.coordinates_present,
            "provenance_preparation_ready_attested": (
                self.provenance_preparation_ready_attested
            ),
            "canonical_validation_valid": self.canonical_validation_valid,
            "graph_representable": self.graph_representable,
            "chemistry_supported": self.chemistry_supported,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "claim_safe": self.claim_safe,
            "validation_error_codes": list(self.validation_error_codes),
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
        """Return whether this report exactly matches a fresh system audit."""

        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        return self.to_dict() == analyze_canonical_chemistry(system).to_dict()


class ChemistryCoverageError(RuntimeError):
    """Raised when a caller requires chemistry support that is not established."""

    def __init__(self, report: ChemistryCoverageReport):
        self.report = report
        self.blockers = report.blockers
        preview = ", ".join(self.blockers[:6])
        suffix = "" if len(self.blockers) <= 6 else f", +{len(self.blockers) - 6} more"
        super().__init__(f"chemistry coverage is not supported: {preview}{suffix}")


class ChemistryCoverageLimitError(ValueError):
    """Raised before a chemistry audit would exceed its fixed resource profile."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"chemistry coverage limit exceeded: {code}: {detail}")


def _component_count(adjacency: list[set[int]]) -> int:
    visited = [False] * len(adjacency)
    component_count = 0
    for start in range(len(adjacency)):
        if visited[start]:
            continue
        component_count += 1
        stack = [start]
        visited[start] = True
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(neighbor)
    return component_count


def _bridge_edges(adjacency: list[set[int]]) -> set[tuple[int, int]]:
    """Return undirected bridges with one iterative Tarjan traversal."""

    discovery = [-1] * len(adjacency)
    low = [-1] * len(adjacency)
    parent = [-1] * len(adjacency)
    bridges: set[tuple[int, int]] = set()
    time = 0
    for root in range(len(adjacency)):
        if discovery[root] >= 0:
            continue
        discovery[root] = low[root] = time
        time += 1
        stack: list[tuple[int, Any]] = [(root, iter(adjacency[root]))]
        while stack:
            current, neighbors = stack[-1]
            try:
                neighbor = next(neighbors)
            except StopIteration:
                stack.pop()
                previous = parent[current]
                if previous >= 0:
                    low[previous] = min(low[previous], low[current])
                    if low[current] > discovery[previous]:
                        bridges.add(tuple(sorted((previous, current))))
                continue
            if discovery[neighbor] < 0:
                parent[neighbor] = current
                discovery[neighbor] = low[neighbor] = time
                time += 1
                stack.append((neighbor, iter(adjacency[neighbor])))
            elif neighbor != parent[current]:
                low[current] = min(low[current], discovery[neighbor])
    return bridges


def _graph_validation_errors(error_codes: tuple[str, ...]) -> tuple[str, ...]:
    """Treat future validation codes as graph-blocking unless explicitly classified otherwise."""

    return tuple(
        code
        for code in error_codes
        if code not in NON_TOPOLOGY_STATE_VALIDATION_ERROR_CODES
    )


def analyze_canonical_chemistry(system: AllAtomSystem) -> ChemistryCoverageReport:
    """Audit canonical typed state without importing a chemistry toolkit."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    atom_count = len(system.atoms)
    bond_count = len(system.bonds)
    if atom_count > MAX_CHEMISTRY_AUDIT_ATOMS:
        raise ChemistryCoverageLimitError(
            "atom_limit_exceeded",
            f"atom_count exceeds {MAX_CHEMISTRY_AUDIT_ATOMS}",
        )
    if bond_count > MAX_CHEMISTRY_AUDIT_BONDS:
        raise ChemistryCoverageLimitError(
            "bond_limit_exceeded",
            f"bond_count exceeds {MAX_CHEMISTRY_AUDIT_BONDS}",
        )

    validation = validate_all_atom_system(system)
    validation_error_codes = tuple(
        sorted({issue.code for issue in validation.errors})
    )
    topology_validation_error_codes = _graph_validation_errors(
        validation_error_codes
    )
    topology_validation_valid = not topology_validation_error_codes
    topology_sha256: str | None = None
    if topology_validation_valid:
        try:
            topology_sha256 = canonical_topology_sha256_for_valid_topology(
                system
            )
        except CanonicalTopologyError:
            topology_sha256 = None

    element_counts = tuple(
        sorted(Counter(atom.element for atom in system.atoms).items())
    )
    elements = tuple(element for element, _ in element_counts)
    outside_profile_elements = tuple(
        element for element in elements if element not in _PROFILE_ELEMENTS
    )
    element_atomic_number_identity_valid = not any(
        atomic_number_for_element(atom.element) != atom.atomic_number
        for atom in system.atoms
    )

    atom_maps: set[int] = set()
    atom_map_contract_valid = True
    for atom in system.atoms:
        if atom.atom_map is None:
            continue
        if atom.atom_map < 1 or atom.atom_map in atom_maps:
            atom_map_contract_valid = False
        atom_maps.add(atom.atom_map)

    unknown_formal_charge_count = sum(
        not atom.formal_charge_known for atom in system.atoms
    )
    formal_charge_outside_profile_count = sum(
        atom.formal_charge_known and abs(atom.formal_charge) > 3
        for atom in system.atoms
    )
    net_formal_charge_known = unknown_formal_charge_count == 0
    net_formal_charge = (
        sum(atom.formal_charge for atom in system.atoms)
        if net_formal_charge_known
        else None
    )
    isotope_count = sum(
        atom.isotope_mass_number is not None for atom in system.atoms
    )

    adjacency = [set() for _ in range(atom_count)]
    aromatic_adjacency = [set() for _ in range(atom_count)]
    bond_pairs: set[tuple[int, int]] = set()
    valid_bonds = []
    bond_graph_contract_valid = True
    bond_order_outside_profile_count = 0
    for bond in system.bonds:
        if bond.order not in _PROFILE_BOND_ORDERS:
            bond_order_outside_profile_count += 1
        endpoints_valid = 0 <= bond.atom_i < bond.atom_j < atom_count
        pair = (bond.atom_i, bond.atom_j)
        if not endpoints_valid or pair in bond_pairs:
            bond_graph_contract_valid = False
            continue
        bond_pairs.add(pair)
        adjacency[bond.atom_i].add(bond.atom_j)
        adjacency[bond.atom_j].add(bond.atom_i)
        if (bond.aromatic and bond.order != 1.5) or (
            not bond.aromatic and bond.order == 1.5
        ):
            bond_graph_contract_valid = False
        else:
            valid_bonds.append(bond)
        if bond.aromatic:
            if (
                not system.atoms[bond.atom_i].aromatic
                or not system.atoms[bond.atom_j].aromatic
            ):
                bond_graph_contract_valid = False
            aromatic_adjacency[bond.atom_i].add(bond.atom_j)
            aromatic_adjacency[bond.atom_j].add(bond.atom_i)

    aromatic_cycle_invalid = False
    aromatic_cycle_atoms: set[int] = set()
    aromatic_bridges = _bridge_edges(aromatic_adjacency)
    for bond in valid_bonds:
        if not bond.aromatic:
            continue
        if (bond.atom_i, bond.atom_j) in aromatic_bridges:
            aromatic_cycle_invalid = True
        else:
            aromatic_cycle_atoms.update((bond.atom_i, bond.atom_j))
    if any(atom.aromatic and atom.index not in aromatic_cycle_atoms for atom in system.atoms):
        aromatic_cycle_invalid = True
    aromatic_cycle_contract_valid = not aromatic_cycle_invalid

    assigned_atom_stereo_count = 0
    unknown_atom_stereo_count = 0
    assigned_bond_stereo_count = 0
    unknown_bond_stereo_count = 0
    bond_stereo_outside_profile_count = 0
    stereo_topology_invalid = False
    for atom in system.atoms:
        stereo = atom.stereo.strip().upper()
        if stereo in {"R", "S"}:
            assigned_atom_stereo_count += 1
            if atom.index < 0 or atom.index >= atom_count or len(adjacency[atom.index]) < 3:
                stereo_topology_invalid = True
        elif stereo == "UNKNOWN":
            unknown_atom_stereo_count += 1
    for bond in system.bonds:
        stereo = bond.stereo.strip().upper()
        if stereo in {"E", "Z"}:
            assigned_bond_stereo_count += 1
            if (
                not (0 <= bond.atom_i < bond.atom_j < atom_count)
                or bond.order != 2.0
                or bond.aromatic
                or len(adjacency[bond.atom_i]) < 2
                or len(adjacency[bond.atom_j]) < 2
            ):
                stereo_topology_invalid = True
        elif stereo in {"UNKNOWN", "EITHER"}:
            unknown_bond_stereo_count += 1
        elif stereo in {"CIS", "TRANS", "UP", "DOWN"}:
            bond_stereo_outside_profile_count += 1
    stereo_topology_contract_valid = not stereo_topology_invalid

    component_count = _component_count(adjacency)
    aromatic_atom_count = sum(atom.aromatic for atom in system.atoms)
    aromatic_bond_count = sum(bond.aromatic for bond in system.bonds)
    graph_representable = bool(
        topology_validation_valid
        and element_atomic_number_identity_valid
        and atom_map_contract_valid
        and bond_graph_contract_valid
        and aromatic_cycle_contract_valid
        and stereo_topology_contract_valid
    )

    blockers = list(_ALWAYS_BLOCKERS)
    if validation_error_codes:
        blockers.append("canonical_validation_errors_present")
    if topology_sha256 is None:
        blockers.append("canonical_topology_digest_unavailable")
    if outside_profile_elements:
        blockers.append("elements_outside_organic_graph_inventory_profile")
    if not element_atomic_number_identity_valid:
        blockers.append("element_atomic_number_identity_invalid")
    if not atom_map_contract_valid:
        blockers.append("atom_map_contract_invalid")
    if unknown_formal_charge_count:
        blockers.append("formal_charge_unknown_for_some_atoms")
    if formal_charge_outside_profile_count:
        blockers.append("formal_charge_outside_profile_range")
    if isotope_count:
        blockers.extend(
            (
                "isotope_parameter_coverage_not_assessed",
                "physical_nuclide_validity_not_assessed",
            )
        )
    if not bond_graph_contract_valid:
        blockers.append("bond_graph_contract_invalid")
    if bond_order_outside_profile_count:
        blockers.append("bond_order_outside_profile")
    if not aromatic_cycle_contract_valid:
        blockers.append("aromatic_cycle_contract_invalid")
    if bond_stereo_outside_profile_count:
        blockers.append("bond_stereo_outside_profile")
    if not stereo_topology_contract_valid:
        blockers.append("stereo_topology_contract_invalid")
    if unknown_atom_stereo_count or unknown_bond_stereo_count:
        blockers.append("stereochemistry_incomplete_or_unknown")
    if assigned_atom_stereo_count or assigned_bond_stereo_count:
        blockers.extend(
            (
                "cip_assignment_not_independently_verified",
                "stereo_substituent_equivalence_not_independently_verified",
            )
        )
    if component_count > 1:
        blockers.append("disconnected_fragment_roles_not_assessed")
    if aromatic_atom_count or aromatic_bond_count:
        blockers.append("aromaticity_perception_not_independently_available")
    if not system.has_coordinates:
        blockers.append("coordinates_missing")
    if not system.provenance.preparation_ready:
        blockers.append("preparation_not_complete")

    return ChemistryCoverageReport(
        profile_id=ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID,
        system_schema_id=system.schema_id,
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256=topology_sha256,
        canonical_topology_digest_available=topology_sha256 is not None,
        topology_validation_valid=topology_validation_valid,
        topology_validation_error_codes=topology_validation_error_codes,
        atom_count=atom_count,
        bond_count=bond_count,
        component_count=component_count,
        elements=elements,
        element_counts=element_counts,
        outside_profile_elements=outside_profile_elements,
        element_atomic_number_identity_valid=(
            element_atomic_number_identity_valid
        ),
        net_formal_charge=net_formal_charge,
        net_formal_charge_known=net_formal_charge_known,
        unknown_formal_charge_count=unknown_formal_charge_count,
        formal_charge_outside_profile_count=(
            formal_charge_outside_profile_count
        ),
        isotope_count=isotope_count,
        atom_map_count=sum(atom.atom_map is not None for atom in system.atoms),
        atom_map_contract_valid=atom_map_contract_valid,
        aromatic_atom_count=aromatic_atom_count,
        aromatic_bond_count=aromatic_bond_count,
        assigned_atom_stereo_count=assigned_atom_stereo_count,
        unknown_atom_stereo_count=unknown_atom_stereo_count,
        assigned_bond_stereo_count=assigned_bond_stereo_count,
        unknown_bond_stereo_count=unknown_bond_stereo_count,
        bond_graph_contract_valid=bond_graph_contract_valid,
        bond_order_outside_profile_count=bond_order_outside_profile_count,
        aromatic_cycle_contract_valid=aromatic_cycle_contract_valid,
        stereo_topology_contract_valid=stereo_topology_contract_valid,
        bond_stereo_outside_profile_count=(
            bond_stereo_outside_profile_count
        ),
        coordinates_present=system.has_coordinates,
        provenance_preparation_ready_attested=(
            system.provenance.preparation_ready
        ),
        canonical_validation_valid=validation.valid,
        graph_representable=graph_representable,
        validation_error_codes=validation_error_codes,
        blockers=tuple(blockers),
    )


def require_supported_chemistry(system: AllAtomSystem) -> ChemistryCoverageReport:
    report = analyze_canonical_chemistry(system)
    if not report.chemistry_supported or not report.parameterizable:
        raise ChemistryCoverageError(report)
    return report


__all__ = [
    "CHEMISTRY_COVERAGE_SCHEMA_VERSION",
    "MAX_CHEMISTRY_AUDIT_ATOMS",
    "MAX_CHEMISTRY_AUDIT_BONDS",
    "ORGANIC_GRAPH_ENCODING_INVENTORY_PROFILE_ID",
    "ChemistryCoverageError",
    "ChemistryCoverageLimitError",
    "ChemistryCoverageReport",
    "analyze_canonical_chemistry",
    "require_supported_chemistry",
]
