"""Bounded neutral acyclic C/O/H graph preparation and parameterability report.

This first chemistry slice composes accepted nonpoly source/value/topology
carriers. It interprets component element, formal-charge, aromatic, and stereo
declarations; cross-checks source-reported atom-site element/charge when
present; and creates a hydrogen-completed *chemical graph* only for neutral,
non-aromatic, acyclic C/O/H components with single/double component bonds.

The output deliberately has no generated hydrogen coordinates, reviewed
parameter set, partial charges, or :class:`AllAtomSystem`. Every instance gets
a failure-complete parameterability report and remains non-parameterable. This
is not pH-dependent protonation, tautomer selection, validated chemistry, or a
commercially ready preparation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_biological_assembly_policy import (
    parse_mmcif_biological_assembly_policy,
)
from .mmcif_missing_atom_residue_policy import (
    parse_mmcif_missing_atom_residue_policy,
)
from .mmcif_nonpoly_atom_site_observations import (
    MmcifNonpolyAtomSiteObservationSnapshot,
    parse_mmcif_nonpoly_atom_site_observations,
)
from .mmcif_nonpoly_atom_site_scalar_values import (
    MmcifNonpolyAtomSiteScalarValueSnapshot,
    parse_mmcif_nonpoly_atom_site_scalar_values,
)
from .mmcif_nonpoly_canonical_topology import (
    MmcifCanonicalTopologyAtomReference,
    MmcifNonpolyCanonicalTopologySnapshot,
    parse_mmcif_nonpoly_canonical_topology,
)
from .mmcif_nonpoly_component_declarations import (
    MmcifNonpolyComponentAtomDeclaration,
    MmcifNonpolyComponentDeclarationSnapshot,
    parse_mmcif_nonpoly_component_declarations,
)


MMCIF_NONPOLY_PREPARATION_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_projection/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_source_binding/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_preparation_document/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_PROFILE_ID = (
    "bounded_neutral_acyclic_coh_graph_preparation/1.0.0"
)
MMCIF_NONPOLY_PREPARATION_PARSER_VERSION = "1.0.0"

MMCIF_PREPARATION_SUPPORTED_ELEMENTS = ("C", "H", "O")
MMCIF_PREPARATION_TARGET_VALENCE: Mapping[str, int] = MappingProxyType(
    {"C": 4, "H": 1, "O": 2}
)
MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS = (1.0, 2.0)
MAX_MMCIF_PREPARATION_SOURCE_ATOMS_PER_INSTANCE = 64
MAX_MMCIF_PREPARATION_ADDED_HYDROGENS_PER_INSTANCE = 256
MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS = (
    "reviewed_parameter_source_not_bound_to_preparation",
    "hydrogen_coordinate_geometry_not_validated",
    "canonical_all_atom_system_not_bound_to_preparation_report",
)
MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS: Mapping[str, str] = MappingProxyType(
    {
        "_chem_comp_atom.type_symbol": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
            "_chem_comp_atom.type_symbol.html"
        ),
        "_chem_comp_atom.charge": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
            "_chem_comp_atom.charge.html"
        ),
        "_chem_comp_atom.pdbx_aromatic_flag": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
            "_chem_comp_atom.pdbx_aromatic_flag.html"
        ),
        "_chem_comp_atom.pdbx_stereo_config": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
            "_chem_comp_atom.pdbx_stereo_config.html"
        ),
        "_atom_site.pdbx_formal_charge": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
            "_atom_site.pdbx_formal_charge.html"
        ),
    }
)

_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyPreparationError(ValueError):
    """Stable fail-closed preparation error without private source values."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_preparation:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifPreparedGraphAtom:
    index: int
    name: str
    element: str
    formal_charge: int
    aromatic: bool
    stereo: str
    origin: str
    source_atom_index: int | None
    source_atom_id: int | None
    parent_atom_index: int | None
    atom_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifPreparedGraphAtom("
            f"index={self.index}, element={self.element!r}, origin={self.origin!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "element": self.element,
            "formal_charge": self.formal_charge,
            "aromatic": self.aromatic,
            "stereo": self.stereo,
            "origin": self.origin,
            "source_atom_index": self.source_atom_index,
            "source_atom_id": self.source_atom_id,
            "parent_atom_index": self.parent_atom_index,
            "atom_identity_sha256": self.atom_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifPreparedGraphBond:
    index: int
    atom_i: int
    atom_j: int
    order: float
    aromatic: bool
    stereo: str
    origin: str
    bond_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifPreparedGraphBond("
            f"index={self.index}, atom_i={self.atom_i}, atom_j={self.atom_j}, "
            f"origin={self.origin!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "atom_i": self.atom_i,
            "atom_j": self.atom_j,
            "order": self.order,
            "aromatic": self.aromatic,
            "stereo": self.stereo,
            "origin": self.origin,
            "bond_identity_sha256": self.bond_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyInstancePreparationReport:
    instance_identity_sha256: str
    component_id: str
    source_atom_indices: tuple[int, ...]
    preparation_status: str
    chemistry_blockers: tuple[str, ...]
    parameterability_status: str
    parameterability_blockers: tuple[str, ...]
    atoms: tuple[MmcifPreparedGraphAtom, ...]
    bonds: tuple[MmcifPreparedGraphBond, ...]
    formula: tuple[tuple[str, int], ...]
    total_formal_charge: int | None
    added_hydrogen_count: int
    preparation_graph_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyInstancePreparationReport("
            f"preparation_status={self.preparation_status!r}, "
            f"source_atom_count={len(self.source_atom_indices)}, "
            f"added_hydrogen_count={self.added_hydrogen_count})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "source_atom_indices": list(self.source_atom_indices),
            "source_atom_count": len(self.source_atom_indices),
            "preparation_status": self.preparation_status,
            "chemistry_blockers": list(self.chemistry_blockers),
            "parameterability_assessed": True,
            "parameterability_status": self.parameterability_status,
            "parameterable": False,
            "parameterability_blockers": list(self.parameterability_blockers),
            "prepared_all_atom_system_created": False,
            "hydrogen_coordinates_generated": False,
            "atoms": [row.to_dict() for row in self.atoms],
            "bonds": [row.to_dict() for row in self.bonds],
            "prepared_atom_count": len(self.atoms),
            "prepared_bond_count": len(self.bonds),
            "formula": dict(self.formula),
            "total_formal_charge": self.total_formal_charge,
            "added_hydrogen_count": self.added_hydrogen_count,
            "preparation_graph_sha256": self.preparation_graph_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyPreparationSnapshot:
    source_sha256: str
    biological_assembly_policy_snapshot_sha256: str
    biological_assembly_policy_projection_sha256: str
    biological_assembly_policy_source_binding_sha256: str
    missing_atom_residue_policy_snapshot_sha256: str
    missing_atom_residue_policy_projection_sha256: str
    missing_atom_residue_policy_source_binding_sha256: str
    observation_snapshot_sha256: str
    scalar_snapshot_sha256: str
    scalar_projection_sha256: str
    scalar_source_binding_sha256: str
    component_snapshot_sha256: str
    component_projection_sha256: str
    component_source_binding_sha256: str
    topology_snapshot_sha256: str
    topology_projection_sha256: str
    topology_source_binding_sha256: str
    instance_reports: tuple[MmcifNonpolyInstancePreparationReport, ...]
    global_parameterability_blockers: tuple[str, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyPreparationSnapshot("
            f"instance_count={len(self.instance_reports)}, "
            f"prepared_graph_count={self.prepared_graph_count})"
        )

    @property
    def prepared_graph_count(self) -> int:
        return sum(
            row.preparation_status == "prepared_component_graph"
            for row in self.instance_reports
        )

    @property
    def preparation_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_preparation_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_preparation_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
                "preparation_projection_sha256": self.preparation_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "biological_assembly_policy_snapshot_sha256": (
                self.biological_assembly_policy_snapshot_sha256
            ),
            "missing_atom_residue_policy_snapshot_sha256": (
                self.missing_atom_residue_policy_snapshot_sha256
            ),
            "observation_snapshot_sha256": self.observation_snapshot_sha256,
            "scalar_snapshot_sha256": self.scalar_snapshot_sha256,
            "component_snapshot_sha256": self.component_snapshot_sha256,
            "topology_snapshot_sha256": self.topology_snapshot_sha256,
            "instance_count": len(self.instance_reports),
            "prepared_graph_count": self.prepared_graph_count,
            "unsupported_instance_count": (
                len(self.instance_reports) - self.prepared_graph_count
            ),
            "all_instance_graphs_prepared": (
                self.prepared_graph_count == len(self.instance_reports)
            ),
            "parameterable_instance_count": 0,
            "global_parameterability_blockers": list(
                self.global_parameterability_blockers
            ),
            "preparation_projection_sha256": self.preparation_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "supported_chemistry_scope_defined": True,
        "source_element_interpreted": True,
        "component_formal_charge_interpreted": True,
        "atom_site_formal_charge_crosschecked": True,
        "nonaromatic_state_interpreted": True,
        "fixed_neutral_valence_hydrogen_completion_applied": True,
        "protonation_policy_interpreted": True,
        "hydrogen_completion_graph_created": True,
        "parameterability_assessed": True,
        "failure_complete_instance_reports": True,
        "biological_assembly_admission_checked": True,
        "missing_atom_residue_admission_checked": True,
        "source_authenticated": False,
        "charged_chemistry_supported": False,
        "aromatic_chemistry_supported": False,
        "nitrogen_sulfur_halogen_metal_chemistry_supported": False,
        "cyclic_chemistry_supported": False,
        "triple_quadruple_bond_chemistry_supported": False,
        "stereochemistry_prepared": False,
        "ph_dependent_protonation_interpreted": False,
        "tautomer_selection_interpreted": False,
        "intercomponent_connection_prepared": False,
        "hydrogen_coordinates_generated": False,
        "reviewed_parameter_source_bound": False,
        "prepared_all_atom_system_created": False,
        "parameterable": False,
        "chemistry_validated": False,
        "preparation_ready": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _normalized_element(value: str) -> str:
    return value[:1].upper() + value[1:].lower()


def _component_charge(declaration: MmcifNonpolyComponentAtomDeclaration) -> int | None:
    value = declaration.charge
    if value.state != "known":
        return None
    if _INTEGER_RE.fullmatch(value.value) is None:
        raise MmcifNonpolyPreparationError(
            "invalid_component_formal_charge",
            "component atom charge must use the PDBx/mmCIF integer grammar",
            line_number=value.line_number,
        )
    charge = int(value.value)
    if not -8 <= charge <= 8:
        raise MmcifNonpolyPreparationError(
            "component_formal_charge_out_of_bounds",
            "component atom charge is outside the PDBx/mmCIF dictionary boundary",
            line_number=value.line_number,
        )
    return charge


def _atom_semantics(
    atom: MmcifCanonicalTopologyAtomReference,
    declaration: MmcifNonpolyComponentAtomDeclaration,
    observation: MmcifNonpolyAtomSiteObservationSnapshot,
    scalar: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> tuple[str, int | None, str, list[str]]:
    blockers: list[str] = []
    source_observation = observation.observations[atom.atom_index]
    scalar_observation = scalar.scalar_observations[atom.atom_index]
    if (
        source_observation.site_identity_sha256 != atom.site_identity_sha256
        or scalar_observation.site_identity_sha256 != atom.site_identity_sha256
    ):
        raise MmcifNonpolyPreparationError(
            "atom_carrier_mismatch",
            "preparation atom identities must match source/value carriers",
        )

    element = ""
    if declaration.type_symbol.state != "known":
        blockers.append("component_element_unavailable")
    else:
        element = _normalized_element(declaration.type_symbol.value)
        if element not in MMCIF_PREPARATION_SUPPORTED_ELEMENTS:
            blockers.append("element_outside_neutral_coh_scope")
    if source_observation.type_symbol.state != "known":
        blockers.append("atom_site_element_unavailable")
    elif (
        element and _normalized_element(source_observation.type_symbol.value) != element
    ):
        blockers.append("atom_site_component_element_mismatch")

    charge = _component_charge(declaration)
    if charge is None:
        blockers.append("component_formal_charge_unavailable")
    elif charge != 0:
        blockers.append("charged_chemistry_not_supported")
    source_charge = scalar_observation.formal_charge
    if (
        source_charge.state == "known"
        and charge is not None
        and source_charge.integer_value != charge
    ):
        blockers.append("atom_site_component_formal_charge_mismatch")

    aromatic_code = ""
    if declaration.aromatic_flag.state != "known":
        blockers.append("component_aromaticity_unavailable")
    else:
        aromatic_code = declaration.aromatic_flag.value.upper()
        if aromatic_code not in {"N", "Y"}:
            raise MmcifNonpolyPreparationError(
                "invalid_component_aromatic_flag",
                "component atom aromatic flag is outside the PDBx/mmCIF vocabulary",
                line_number=declaration.aromatic_flag.line_number,
            )
        if aromatic_code == "Y":
            blockers.append("aromatic_chemistry_not_supported")

    stereo_code = ""
    if declaration.stereo_config.state != "known":
        blockers.append("component_stereo_unavailable")
    else:
        stereo_code = declaration.stereo_config.value.upper()
        if stereo_code not in {"N", "R", "S"}:
            raise MmcifNonpolyPreparationError(
                "invalid_component_atom_stereo",
                "component atom stereo is outside the PDBx/mmCIF vocabulary",
                line_number=declaration.stereo_config.line_number,
            )
        if stereo_code in {"R", "S"}:
            blockers.append("atom_stereochemistry_not_prepared")
    return element, charge, stereo_code, blockers


def _prepared_atom(
    *,
    instance_identity_sha256: str,
    index: int,
    name: str,
    element: str,
    formal_charge: int,
    stereo: str,
    origin: str,
    source_atom_index: int | None,
    source_atom_id: int | None,
    parent_atom_index: int | None,
) -> MmcifPreparedGraphAtom:
    identity = _sha256(
        {
            "instance_identity_sha256": instance_identity_sha256,
            "index": index,
            "name": name,
            "element": element,
            "formal_charge": formal_charge,
            "aromatic": False,
            "stereo": stereo,
            "origin": origin,
            "source_atom_index": source_atom_index,
            "source_atom_id": source_atom_id,
            "parent_atom_index": parent_atom_index,
        }
    )
    return MmcifPreparedGraphAtom(
        index=index,
        name=name,
        element=element,
        formal_charge=formal_charge,
        aromatic=False,
        stereo=stereo,
        origin=origin,
        source_atom_index=source_atom_index,
        source_atom_id=source_atom_id,
        parent_atom_index=parent_atom_index,
        atom_identity_sha256=identity,
    )


def _prepared_bond(
    *,
    instance_identity_sha256: str,
    index: int,
    atom_i: int,
    atom_j: int,
    order: float,
    stereo: str,
    origin: str,
) -> MmcifPreparedGraphBond:
    first, second = sorted((atom_i, atom_j))
    identity = _sha256(
        {
            "instance_identity_sha256": instance_identity_sha256,
            "index": index,
            "atom_i": first,
            "atom_j": second,
            "order": order,
            "aromatic": False,
            "stereo": stereo,
            "origin": origin,
        }
    )
    return MmcifPreparedGraphBond(
        index=index,
        atom_i=first,
        atom_j=second,
        order=order,
        aromatic=False,
        stereo=stereo,
        origin=origin,
        bond_identity_sha256=identity,
    )


def _connected(atom_count: int, bonds: list[tuple[int, int]]) -> tuple[bool, bool]:
    adjacency = {index: set() for index in range(atom_count)}
    for atom_i, atom_j in bonds:
        adjacency[atom_i].add(atom_j)
        adjacency[atom_j].add(atom_i)
    visited = set()
    stack = [0]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        stack.extend(sorted(adjacency[current] - visited, reverse=True))
    connected = len(visited) == atom_count
    cyclic = connected and len(bonds) != atom_count - 1
    return connected, cyclic


def _instance_connection_blockers(
    source_indices: set[int], topology: MmcifNonpolyCanonicalTopologySnapshot
) -> list[str]:
    blockers: list[str] = []
    if any(
        row.source_kind == "mmcif_struct_conn_covale"
        and ({row.atom_i, row.atom_j} & source_indices)
        for row in topology.bonds
    ):
        blockers.append("intercomponent_covalent_connection_not_prepared")
    if any(
        {row.atom_i, row.atom_j} & source_indices for row in topology.coordination_edges
    ):
        blockers.append("intercomponent_coordination_not_prepared")
    return blockers


def _instance_report(
    atoms: tuple[MmcifCanonicalTopologyAtomReference, ...],
    *,
    topology: MmcifNonpolyCanonicalTopologySnapshot,
    observation: MmcifNonpolyAtomSiteObservationSnapshot,
    scalar: MmcifNonpolyAtomSiteScalarValueSnapshot,
    components: MmcifNonpolyComponentDeclarationSnapshot,
) -> MmcifNonpolyInstancePreparationReport:
    instance_identity = atoms[0].instance_identity_sha256
    component_id = atoms[0].component_id
    source_indices = tuple(row.atom_index for row in atoms)
    chemistry_blockers: list[str] = []
    if len(atoms) > MAX_MMCIF_PREPARATION_SOURCE_ATOMS_PER_INSTANCE:
        chemistry_blockers.append("source_atom_count_out_of_bounds")

    declarations = {
        (row.comp_id, row.atom_id): row for row in components.atom_declarations
    }
    interpreted: list[tuple[str, int, str]] = []
    for atom in atoms:
        declaration = declarations.get((component_id, atom.atom_id))
        if declaration is None:
            raise MmcifNonpolyPreparationError(
                "component_atom_declaration_missing",
                "every preparation atom must retain a component declaration",
            )
        element, charge, stereo, blockers = _atom_semantics(
            atom, declaration, observation, scalar
        )
        chemistry_blockers.extend(blockers)
        interpreted.append((element, 0 if charge is None else charge, stereo))

    source_index_set = set(source_indices)
    component_bonds = [
        row
        for row in topology.bonds
        if row.atom_i in source_index_set
        and row.atom_j in source_index_set
        and row.source_kind == "mmcif_chem_comp_bond"
    ]
    if any(
        row.atom_i in source_index_set
        and row.atom_j in source_index_set
        and row.source_kind != "mmcif_chem_comp_bond"
        for row in topology.bonds
    ):
        chemistry_blockers.append("non_component_bond_inside_instance")
    for bond in component_bonds:
        if bond.order not in MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS or bond.aromatic:
            chemistry_blockers.append("bond_order_outside_neutral_coh_scope")
        if bond.stereo != "none":
            chemistry_blockers.append("bond_stereochemistry_not_prepared")

    local_index = {
        global_index: index for index, global_index in enumerate(source_indices)
    }
    local_pairs = [
        (local_index[row.atom_i], local_index[row.atom_j]) for row in component_bonds
    ]
    connected, cyclic = _connected(len(atoms), local_pairs)
    if not connected:
        chemistry_blockers.append("component_graph_disconnected")
    if cyclic:
        chemistry_blockers.append("cyclic_chemistry_not_supported")

    chemistry_blockers = list(_unique(chemistry_blockers))
    added_counts = [0 for _ in atoms]
    if not chemistry_blockers:
        valence = [0.0 for _ in atoms]
        for bond in component_bonds:
            valence[local_index[bond.atom_i]] += bond.order
            valence[local_index[bond.atom_j]] += bond.order
        for index, (element, _charge, _stereo) in enumerate(interpreted):
            target = MMCIF_PREPARATION_TARGET_VALENCE[element]
            missing = target - valence[index]
            if missing < 0.0 or not float(missing).is_integer():
                chemistry_blockers.append("neutral_valence_not_satisfied")
                continue
            if element == "H" and missing != 0.0:
                chemistry_blockers.append("source_hydrogen_valence_incomplete")
                continue
            if element != "H":
                added_counts[index] = int(missing)
        if sum(added_counts) > MAX_MMCIF_PREPARATION_ADDED_HYDROGENS_PER_INSTANCE:
            chemistry_blockers.append("added_hydrogen_count_out_of_bounds")
    chemistry_blockers = list(_unique(chemistry_blockers))

    prepared_atoms: list[MmcifPreparedGraphAtom] = []
    prepared_bonds: list[MmcifPreparedGraphBond] = []
    if not chemistry_blockers:
        for local, (source_atom, semantics) in enumerate(
            zip(atoms, interpreted, strict=True)
        ):
            element, charge, stereo = semantics
            prepared_atoms.append(
                _prepared_atom(
                    instance_identity_sha256=instance_identity,
                    index=local,
                    name=source_atom.atom_id,
                    element=element,
                    formal_charge=charge,
                    stereo="none" if stereo == "N" else stereo,
                    origin="source_atom",
                    source_atom_index=source_atom.atom_index,
                    source_atom_id=source_atom.source_atom_id,
                    parent_atom_index=None,
                )
            )
        for source_bond in component_bonds:
            prepared_bonds.append(
                _prepared_bond(
                    instance_identity_sha256=instance_identity,
                    index=len(prepared_bonds),
                    atom_i=local_index[source_bond.atom_i],
                    atom_j=local_index[source_bond.atom_j],
                    order=source_bond.order,
                    stereo=source_bond.stereo,
                    origin="source_component_bond",
                )
            )
        for parent_index, count in enumerate(added_counts):
            for ordinal in range(1, count + 1):
                hydrogen_index = len(prepared_atoms)
                prepared_atoms.append(
                    _prepared_atom(
                        instance_identity_sha256=instance_identity,
                        index=hydrogen_index,
                        name=f"HADD_{parent_index + 1}_{ordinal}",
                        element="H",
                        formal_charge=0,
                        stereo="none",
                        origin="added_hydrogen",
                        source_atom_index=None,
                        source_atom_id=None,
                        parent_atom_index=parent_index,
                    )
                )
                prepared_bonds.append(
                    _prepared_bond(
                        instance_identity_sha256=instance_identity,
                        index=len(prepared_bonds),
                        atom_i=parent_index,
                        atom_j=hydrogen_index,
                        order=1.0,
                        stereo="none",
                        origin="hydrogen_completion_bond",
                    )
                )

    integration_blockers = _instance_connection_blockers(source_index_set, topology)
    parameterability_blockers = _unique(
        chemistry_blockers
        + integration_blockers
        + list(MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS)
    )
    if chemistry_blockers:
        status = "unsupported_chemistry"
        parameterability_status = "unsupported_chemistry"
        formula: tuple[tuple[str, int], ...] = ()
        total_charge: int | None = None
        graph_sha = ""
    else:
        status = "prepared_component_graph"
        parameterability_status = (
            "graph_ready_external_connection_blocked"
            if integration_blockers
            else "graph_ready_parameter_source_not_bound"
        )
        formula_counts = {
            element: sum(row.element == element for row in prepared_atoms)
            for element in MMCIF_PREPARATION_SUPPORTED_ELEMENTS
        }
        formula = tuple((key, value) for key, value in formula_counts.items() if value)
        total_charge = sum(row.formal_charge for row in prepared_atoms)
        graph_sha = _sha256(
            {
                "schema_id": "betelgeuze.engine_v2_prepared_chemical_graph/1.0.0",
                "instance_identity_sha256": instance_identity,
                "atoms": [row.to_dict() for row in prepared_atoms],
                "bonds": [row.to_dict() for row in prepared_bonds],
                "formula": dict(formula),
                "total_formal_charge": total_charge,
            }
        )
    return MmcifNonpolyInstancePreparationReport(
        instance_identity_sha256=instance_identity,
        component_id=component_id,
        source_atom_indices=source_indices,
        preparation_status=status,
        chemistry_blockers=tuple(chemistry_blockers),
        parameterability_status=parameterability_status,
        parameterability_blockers=parameterability_blockers,
        atoms=tuple(prepared_atoms),
        bonds=tuple(prepared_bonds),
        formula=formula,
        total_formal_charge=total_charge,
        added_hydrogen_count=sum(added_counts) if not chemistry_blockers else 0,
        preparation_graph_sha256=graph_sha,
    )


def parse_mmcif_nonpoly_preparation(text: str) -> MmcifNonpolyPreparationSnapshot:
    """Create bounded component-graph preparation and parameterability reports."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly preparation input must be a string")
    biological_assembly_policy = parse_mmcif_biological_assembly_policy(text)
    if not biological_assembly_policy.execution_allowed:
        raise MmcifNonpolyPreparationError(
            "source_declared_biological_assembly_not_supported",
            "source-declared biological-assembly rows block preparation",
        )
    missing_atom_residue_policy = parse_mmcif_missing_atom_residue_policy(text)
    if not missing_atom_residue_policy.execution_allowed:
        raise MmcifNonpolyPreparationError(
            "source_declared_observation_gap_not_supported",
            "source-declared unobserved or zero-occupancy rows block preparation",
        )
    observation = parse_mmcif_nonpoly_atom_site_observations(text)
    scalar = parse_mmcif_nonpoly_atom_site_scalar_values(text)
    components = parse_mmcif_nonpoly_component_declarations(text)
    topology = parse_mmcif_nonpoly_canonical_topology(text)
    if not (
        biological_assembly_policy.source_sha256
        == missing_atom_residue_policy.source_sha256
        == observation.source_sha256
        == scalar.source_sha256
        == components.source_sha256
        == topology.source_sha256
    ):
        raise MmcifNonpolyPreparationError(
            "source_carrier_mismatch",
            "all preparation carriers must bind the same source bytes",
        )
    if (
        scalar.observation_snapshot_sha256 != observation.snapshot_sha256
        or topology.observation_snapshot_sha256 != observation.snapshot_sha256
        or topology.scalar_snapshot_sha256 != scalar.snapshot_sha256
        or topology.component_snapshot_sha256 != components.snapshot_sha256
    ):
        raise MmcifNonpolyPreparationError(
            "source_snapshot_mismatch",
            "preparation dependencies must bind the exact accepted snapshots",
        )
    instances: list[tuple[MmcifCanonicalTopologyAtomReference, ...]] = []
    by_instance: dict[str, list[MmcifCanonicalTopologyAtomReference]] = {}
    for atom in topology.atoms:
        if atom.instance_identity_sha256 not in by_instance:
            by_instance[atom.instance_identity_sha256] = []
        by_instance[atom.instance_identity_sha256].append(atom)
    for rows in by_instance.values():
        instances.append(tuple(rows))
    reports = tuple(
        _instance_report(
            rows,
            topology=topology,
            observation=observation,
            scalar=scalar,
            components=components,
        )
        for rows in instances
    )
    global_blockers = list(MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS)
    if topology.struct_covalent_bond_count:
        global_blockers.append("intercomponent_covalent_connection_not_prepared")
    if topology.coordination_edges:
        global_blockers.append("intercomponent_coordination_not_prepared")
    return MmcifNonpolyPreparationSnapshot(
        source_sha256=observation.source_sha256,
        biological_assembly_policy_snapshot_sha256=(
            biological_assembly_policy.snapshot_sha256
        ),
        biological_assembly_policy_projection_sha256=(
            biological_assembly_policy.policy_projection_sha256
        ),
        biological_assembly_policy_source_binding_sha256=(
            biological_assembly_policy.source_binding_sha256
        ),
        missing_atom_residue_policy_snapshot_sha256=(
            missing_atom_residue_policy.snapshot_sha256
        ),
        missing_atom_residue_policy_projection_sha256=(
            missing_atom_residue_policy.policy_projection_sha256
        ),
        missing_atom_residue_policy_source_binding_sha256=(
            missing_atom_residue_policy.source_binding_sha256
        ),
        observation_snapshot_sha256=observation.snapshot_sha256,
        scalar_snapshot_sha256=scalar.snapshot_sha256,
        scalar_projection_sha256=scalar.scalar_projection_sha256,
        scalar_source_binding_sha256=scalar.source_binding_sha256,
        component_snapshot_sha256=components.snapshot_sha256,
        component_projection_sha256=components.declaration_projection_sha256,
        component_source_binding_sha256=components.source_binding_sha256,
        topology_snapshot_sha256=topology.snapshot_sha256,
        topology_projection_sha256=topology.topology_projection_sha256,
        topology_source_binding_sha256=topology.source_binding_sha256,
        instance_reports=reports,
        global_parameterability_blockers=_unique(global_blockers),
    )


def mmcif_nonpoly_preparation_projection(
    snapshot: MmcifNonpolyPreparationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
        "biological_assembly_policy_projection_sha256": (
            snapshot.biological_assembly_policy_projection_sha256
        ),
        "missing_atom_residue_policy_projection_sha256": (
            snapshot.missing_atom_residue_policy_projection_sha256
        ),
        "scalar_projection_sha256": snapshot.scalar_projection_sha256,
        "component_projection_sha256": snapshot.component_projection_sha256,
        "topology_projection_sha256": snapshot.topology_projection_sha256,
        "instance_reports": [row.to_dict() for row in snapshot.instance_reports],
        "global_parameterability_blockers": list(
            snapshot.global_parameterability_blockers
        ),
        "instance_order": "first_selected_source_atom_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_preparation_source_binding(
    snapshot: MmcifNonpolyPreparationSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "biological_assembly_policy_snapshot_sha256": (
            snapshot.biological_assembly_policy_snapshot_sha256
        ),
        "biological_assembly_policy_source_binding_sha256": (
            snapshot.biological_assembly_policy_source_binding_sha256
        ),
        "missing_atom_residue_policy_snapshot_sha256": (
            snapshot.missing_atom_residue_policy_snapshot_sha256
        ),
        "missing_atom_residue_policy_source_binding_sha256": (
            snapshot.missing_atom_residue_policy_source_binding_sha256
        ),
        "observation_snapshot_sha256": snapshot.observation_snapshot_sha256,
        "scalar_snapshot_sha256": snapshot.scalar_snapshot_sha256,
        "scalar_source_binding_sha256": snapshot.scalar_source_binding_sha256,
        "component_snapshot_sha256": snapshot.component_snapshot_sha256,
        "component_source_binding_sha256": snapshot.component_source_binding_sha256,
        "topology_snapshot_sha256": snapshot.topology_snapshot_sha256,
        "topology_source_binding_sha256": snapshot.topology_source_binding_sha256,
        "dictionary_items": dict(MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS),
        "supported_elements": list(MMCIF_PREPARATION_SUPPORTED_ELEMENTS),
        "target_valence": dict(MMCIF_PREPARATION_TARGET_VALENCE),
        "supported_bond_orders": list(MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS),
        "maximum_source_atoms_per_instance": (
            MAX_MMCIF_PREPARATION_SOURCE_ATOMS_PER_INSTANCE
        ),
        "maximum_added_hydrogens_per_instance": (
            MAX_MMCIF_PREPARATION_ADDED_HYDROGENS_PER_INSTANCE
        ),
        "universal_parameterability_blockers": list(
            MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS
        ),
    }


def mmcif_nonpoly_preparation_document(
    snapshot: MmcifNonpolyPreparationSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_preparation_projection(snapshot)
    binding = mmcif_nonpoly_preparation_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_PREPARATION_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_PREPARATION_PARSER_VERSION,
        "preparation_projection": projection,
        "source_binding": binding,
        "preparation_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"nonpoly preparation {label} digest invalid")
    return candidate


def _require_instance_report(payload: object) -> tuple[str, bool]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly preparation instance report must be a mapping")
    report = dict(payload)
    instance = _require_digest(
        report.get("instance_identity_sha256"), "instance identity"
    )
    if type(report.get("component_id")) is not str or not report.get("component_id"):
        raise ValueError("nonpoly preparation component id invalid")
    source_indices = report.get("source_atom_indices")
    if (
        not isinstance(source_indices, list)
        or not source_indices
        or any(type(value) is not int or value < 0 for value in source_indices)
        or len(set(source_indices)) != len(source_indices)
        or report.get("source_atom_count") != len(source_indices)
    ):
        raise ValueError("nonpoly preparation source atom indices invalid")
    chemistry_blockers = report.get("chemistry_blockers")
    parameterability_blockers = report.get("parameterability_blockers")
    if (
        not isinstance(chemistry_blockers, list)
        or not all(type(value) is str and value for value in chemistry_blockers)
        or len(set(chemistry_blockers)) != len(chemistry_blockers)
        or not isinstance(parameterability_blockers, list)
        or not all(type(value) is str and value for value in parameterability_blockers)
        or len(set(parameterability_blockers)) != len(parameterability_blockers)
    ):
        raise ValueError("nonpoly preparation blocker list invalid")
    for blocker in MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS:
        if blocker not in parameterability_blockers:
            raise ValueError("nonpoly preparation universal blocker missing")
    if (
        report.get("parameterability_assessed") is not True
        or report.get("parameterable") is not False
        or report.get("prepared_all_atom_system_created") is not False
        or report.get("hydrogen_coordinates_generated") is not False
    ):
        raise ValueError("nonpoly preparation parameterability policy mismatch")

    status = report.get("preparation_status")
    atoms = report.get("atoms")
    bonds = report.get("bonds")
    if not isinstance(atoms, list) or not isinstance(bonds, list):
        raise ValueError("nonpoly preparation graph sections must be lists")
    if status == "unsupported_chemistry":
        if (
            not chemistry_blockers
            or atoms
            or bonds
            or report.get("prepared_atom_count") != 0
            or report.get("prepared_bond_count") != 0
            or report.get("formula") != {}
            or report.get("total_formal_charge") is not None
            or report.get("added_hydrogen_count") != 0
            or report.get("preparation_graph_sha256") != ""
            or report.get("parameterability_status") != "unsupported_chemistry"
        ):
            raise ValueError("nonpoly preparation unsupported report mismatch")
        return instance, False
    if status != "prepared_component_graph" or chemistry_blockers:
        raise ValueError("nonpoly preparation status mismatch")
    if report.get("parameterability_status") not in {
        "graph_ready_external_connection_blocked",
        "graph_ready_parameter_source_not_bound",
    }:
        raise ValueError("nonpoly preparation parameterability status invalid")

    source_atom_count = len(source_indices)
    formula_counts = {element: 0 for element in MMCIF_PREPARATION_SUPPORTED_ELEMENTS}
    added_atoms: dict[int, int] = {}
    total_charge = 0
    for index, item in enumerate(atoms):
        if not isinstance(item, Mapping):
            raise ValueError("nonpoly prepared atom must be a mapping")
        atom = dict(item)
        if atom.get("index") != index:
            raise ValueError("nonpoly prepared atom indices must be contiguous")
        element = atom.get("element")
        if element not in MMCIF_PREPARATION_SUPPORTED_ELEMENTS:
            raise ValueError("nonpoly prepared atom element invalid")
        if type(atom.get("formal_charge")) is not int or atom["formal_charge"] != 0:
            raise ValueError("nonpoly prepared atom charge invalid")
        if atom.get("aromatic") is not False or atom.get("stereo") != "none":
            raise ValueError("nonpoly prepared atom aromatic/stereo state invalid")
        if type(atom.get("name")) is not str or not atom.get("name"):
            raise ValueError("nonpoly prepared atom name invalid")
        origin = atom.get("origin")
        if index < source_atom_count:
            if (
                origin != "source_atom"
                or atom.get("source_atom_index") != source_indices[index]
                or type(atom.get("source_atom_id")) is not int
                or atom["source_atom_id"] <= 0
                or atom.get("parent_atom_index") is not None
            ):
                raise ValueError("nonpoly prepared source atom binding mismatch")
        else:
            parent = atom.get("parent_atom_index")
            if (
                origin != "added_hydrogen"
                or element != "H"
                or atom.get("source_atom_index") is not None
                or atom.get("source_atom_id") is not None
                or type(parent) is not int
                or not 0 <= parent < source_atom_count
            ):
                raise ValueError("nonpoly added hydrogen binding mismatch")
            added_atoms[index] = parent
        identity = _sha256(
            {
                "instance_identity_sha256": instance,
                "index": index,
                "name": atom["name"],
                "element": element,
                "formal_charge": atom["formal_charge"],
                "aromatic": False,
                "stereo": "none",
                "origin": origin,
                "source_atom_index": atom.get("source_atom_index"),
                "source_atom_id": atom.get("source_atom_id"),
                "parent_atom_index": atom.get("parent_atom_index"),
            }
        )
        if atom.get("atom_identity_sha256") != identity:
            raise ValueError("nonpoly prepared atom identity mismatch")
        formula_counts[element] += 1
        total_charge += atom["formal_charge"]

    pairs: set[tuple[int, int]] = set()
    added_bond_parent: dict[int, int] = {}
    for index, item in enumerate(bonds):
        if not isinstance(item, Mapping):
            raise ValueError("nonpoly prepared bond must be a mapping")
        bond = dict(item)
        atom_i = bond.get("atom_i")
        atom_j = bond.get("atom_j")
        if (
            bond.get("index") != index
            or type(atom_i) is not int
            or type(atom_j) is not int
            or not 0 <= atom_i < atom_j < len(atoms)
        ):
            raise ValueError("nonpoly prepared bond endpoints invalid")
        pair = (atom_i, atom_j)
        if pair in pairs:
            raise ValueError("nonpoly prepared bond pairs must be unique")
        pairs.add(pair)
        order = bond.get("order")
        origin = bond.get("origin")
        if (
            type(order) not in (int, float)
            or float(order) not in MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS
            or bond.get("aromatic") is not False
            or bond.get("stereo") != "none"
            or origin not in {"source_component_bond", "hydrogen_completion_bond"}
        ):
            raise ValueError("nonpoly prepared bond semantics invalid")
        if origin == "hydrogen_completion_bond":
            hydrogen = atom_j if atom_j in added_atoms else atom_i
            parent = atom_i if hydrogen == atom_j else atom_j
            if (
                hydrogen not in added_atoms
                or added_atoms[hydrogen] != parent
                or float(order) != 1.0
            ):
                raise ValueError("nonpoly hydrogen completion bond mismatch")
            added_bond_parent[hydrogen] = parent
        identity = _sha256(
            {
                "instance_identity_sha256": instance,
                "index": index,
                "atom_i": atom_i,
                "atom_j": atom_j,
                "order": float(order),
                "aromatic": False,
                "stereo": bond["stereo"],
                "origin": origin,
            }
        )
        if bond.get("bond_identity_sha256") != identity:
            raise ValueError("nonpoly prepared bond identity mismatch")
    if added_bond_parent != added_atoms:
        raise ValueError("nonpoly added hydrogen coverage mismatch")
    if report.get("prepared_atom_count") != len(atoms) or report.get(
        "prepared_bond_count"
    ) != len(bonds):
        raise ValueError("nonpoly preparation graph count mismatch")
    if report.get("added_hydrogen_count") != len(added_atoms):
        raise ValueError("nonpoly preparation added hydrogen count mismatch")
    formula = {key: value for key, value in formula_counts.items() if value}
    if (
        report.get("formula") != formula
        or report.get("total_formal_charge") != total_charge
    ):
        raise ValueError("nonpoly preparation formula or charge mismatch")
    graph_payload = {
        "schema_id": "betelgeuze.engine_v2_prepared_chemical_graph/1.0.0",
        "instance_identity_sha256": instance,
        "atoms": atoms,
        "bonds": bonds,
        "formula": formula,
        "total_formal_charge": total_charge,
    }
    graph_sha = _sha256(graph_payload)
    if report.get("preparation_graph_sha256") != graph_sha:
        raise ValueError("nonpoly preparation graph digest mismatch")
    return instance, True


def require_mmcif_nonpoly_preparation_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly preparation document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly preparation document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_PREPARATION_PROFILE_ID:
        raise ValueError("nonpoly preparation profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_PREPARATION_PARSER_VERSION:
        raise ValueError("nonpoly preparation parser version mismatch")
    projection = document.get("preparation_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly preparation sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_PREPARATION_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly preparation projection schema mismatch")
    if binding.get("schema_id") != MMCIF_NONPOLY_PREPARATION_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("nonpoly preparation source binding schema mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("preparation_projection_sha256") != projection_digest:
        raise ValueError("nonpoly preparation projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly preparation source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID,
            "preparation_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly preparation snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly preparation claim policy mismatch")

    reports = projection.get("instance_reports")
    if not isinstance(reports, list) or not reports:
        raise ValueError("nonpoly preparation reports must be a non-empty list")
    instances: set[str] = set()
    prepared_count = 0
    for report in reports:
        instance, prepared = _require_instance_report(report)
        if instance in instances:
            raise ValueError("nonpoly preparation instance reports must be unique")
        instances.add(instance)
        prepared_count += int(prepared)
    if (
        document.get("instance_count") != len(reports)
        or document.get("prepared_graph_count") != prepared_count
        or document.get("unsupported_instance_count") != len(reports) - prepared_count
        or document.get("all_instance_graphs_prepared")
        is not (prepared_count == len(reports))
        or document.get("parameterable_instance_count") != 0
    ):
        raise ValueError("nonpoly preparation summary count mismatch")

    global_blockers = document.get("global_parameterability_blockers")
    if (
        not isinstance(global_blockers, list)
        or len(set(global_blockers)) != len(global_blockers)
        or not all(type(value) is str and value for value in global_blockers)
        or projection.get("global_parameterability_blockers") != global_blockers
    ):
        raise ValueError("nonpoly preparation global blockers invalid")
    for blocker in MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS:
        if blocker not in global_blockers:
            raise ValueError("nonpoly preparation global universal blocker missing")

    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly preparation source digest mismatch")
    for key in (
        "biological_assembly_policy_snapshot_sha256",
        "missing_atom_residue_policy_snapshot_sha256",
        "observation_snapshot_sha256",
        "scalar_snapshot_sha256",
        "component_snapshot_sha256",
        "topology_snapshot_sha256",
    ):
        digest = _require_digest(binding.get(key), key)
        if document.get(key) != digest:
            raise ValueError(f"nonpoly preparation {key} mismatch")
    for key in (
        "biological_assembly_policy_projection_sha256",
        "missing_atom_residue_policy_projection_sha256",
        "scalar_projection_sha256",
        "component_projection_sha256",
        "topology_projection_sha256",
    ):
        _require_digest(projection.get(key), key)
    for key in (
        "biological_assembly_policy_source_binding_sha256",
        "missing_atom_residue_policy_source_binding_sha256",
        "scalar_source_binding_sha256",
        "component_source_binding_sha256",
        "topology_source_binding_sha256",
    ):
        _require_digest(binding.get(key), key)
    if binding.get("dictionary_items") != MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS:
        raise ValueError("nonpoly preparation dictionary binding mismatch")
    if (
        binding.get("supported_elements") != list(MMCIF_PREPARATION_SUPPORTED_ELEMENTS)
        or binding.get("target_valence") != MMCIF_PREPARATION_TARGET_VALENCE
        or binding.get("supported_bond_orders")
        != list(MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS)
        or binding.get("maximum_source_atoms_per_instance")
        != MAX_MMCIF_PREPARATION_SOURCE_ATOMS_PER_INSTANCE
        or binding.get("maximum_added_hydrogens_per_instance")
        != MAX_MMCIF_PREPARATION_ADDED_HYDROGENS_PER_INSTANCE
        or binding.get("universal_parameterability_blockers")
        != list(MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS)
    ):
        raise ValueError("nonpoly preparation scope policy mismatch")
    return payload


def mmcif_nonpoly_preparation_json_bytes(
    snapshot: MmcifNonpolyPreparationSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_preparation_document(snapshot))


def write_mmcif_nonpoly_preparation_json(
    path: str | Path,
    snapshot: MmcifNonpolyPreparationSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_preparation_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "MAX_MMCIF_PREPARATION_ADDED_HYDROGENS_PER_INSTANCE",
    "MAX_MMCIF_PREPARATION_SOURCE_ATOMS_PER_INSTANCE",
    "MMCIF_NONPOLY_PREPARATION_DICTIONARY_ITEMS",
    "MMCIF_NONPOLY_PREPARATION_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_PREPARATION_PARSER_VERSION",
    "MMCIF_NONPOLY_PREPARATION_PROFILE_ID",
    "MMCIF_NONPOLY_PREPARATION_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_PREPARATION_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_PREPARATION_SUPPORTED_BOND_ORDERS",
    "MMCIF_PREPARATION_SUPPORTED_ELEMENTS",
    "MMCIF_PREPARATION_TARGET_VALENCE",
    "MMCIF_PREPARATION_UNIVERSAL_PARAMETERABILITY_BLOCKERS",
    "MmcifNonpolyInstancePreparationReport",
    "MmcifNonpolyPreparationError",
    "MmcifNonpolyPreparationSnapshot",
    "MmcifPreparedGraphAtom",
    "MmcifPreparedGraphBond",
    "mmcif_nonpoly_preparation_document",
    "mmcif_nonpoly_preparation_json_bytes",
    "mmcif_nonpoly_preparation_projection",
    "mmcif_nonpoly_preparation_source_binding",
    "parse_mmcif_nonpoly_preparation",
    "require_mmcif_nonpoly_preparation_document",
    "write_mmcif_nonpoly_preparation_json",
]
