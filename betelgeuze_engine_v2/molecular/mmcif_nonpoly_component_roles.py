"""Bounded composition roles for selected nonpoly mmCIF instances.

This layer interprets only source facts that can be joined without biological
role heuristics: ``_entity.type``, ``_chem_comp.type``, component atom element
symbols, and component atom formal charges.  It distinguishes source water,
monoatomic metal components, and charged monoatomic nonmetal ions.  Every other
nonpoly component remains unresolved; ligand, cofactor, and modified-residue
roles are never inferred from component identifiers, names, or atom counts.
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

from .mmcif_nonpoly_component_declarations import (
    MmcifNonpolyComponentAtomDeclaration,
    parse_mmcif_nonpoly_component_declarations,
)
from .mmcif_nonpoly_identity import parse_mmcif_nonpoly_identity
from .mmcif_syntax import CifLoop, CifToken, parse_cif_block
from .models import atomic_number_for_element, canonical_element_symbol


MMCIF_NONPOLY_COMPONENT_ROLE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_role_projection/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_ROLE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_role_source_binding/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_component_role_document/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID = (
    "bounded_mmcif_nonpoly_composition_roles/1.0.0"
)
MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION = "1.0.0"
MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS = (
    "_chem_comp.id",
    "_chem_comp.type",
)
MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES = ("non-polymer",)
MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS: Mapping[str, str] = MappingProxyType(
    {
        "_entity.type": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
            "Items/_entity.type.html"
        ),
        "_chem_comp.type": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
            "Items/_chem_comp.type.html"
        ),
        "_chem_comp_atom.type_symbol": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
            "Items/_chem_comp_atom.type_symbol.html"
        ),
        "_chem_comp_atom.charge": (
            "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/"
            "Items/_chem_comp_atom.charge.html"
        ),
    }
)

# This is an explicit applicability-policy set, not a claim that mmCIF assigns
# chemical roles from periodic-table groups.  Metalloids are intentionally not
# included.  Any future policy change alters the source-binding digest.
MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS = (
    "Ac",
    "Ag",
    "Al",
    "Am",
    "Au",
    "Ba",
    "Be",
    "Bh",
    "Bi",
    "Bk",
    "Ca",
    "Cd",
    "Ce",
    "Cf",
    "Cm",
    "Cn",
    "Co",
    "Cr",
    "Cs",
    "Cu",
    "Db",
    "Ds",
    "Dy",
    "Er",
    "Es",
    "Eu",
    "Fe",
    "Fl",
    "Fm",
    "Fr",
    "Ga",
    "Gd",
    "Hf",
    "Hg",
    "Ho",
    "Hs",
    "In",
    "Ir",
    "K",
    "La",
    "Li",
    "Lr",
    "Lu",
    "Lv",
    "Mc",
    "Md",
    "Mg",
    "Mn",
    "Mo",
    "Mt",
    "Na",
    "Nb",
    "Nd",
    "Nh",
    "Ni",
    "No",
    "Np",
    "Os",
    "Pa",
    "Pb",
    "Pd",
    "Pm",
    "Po",
    "Pr",
    "Pt",
    "Pu",
    "Ra",
    "Rb",
    "Re",
    "Rf",
    "Rg",
    "Rh",
    "Ru",
    "Sc",
    "Sg",
    "Sm",
    "Sn",
    "Sr",
    "Ta",
    "Tb",
    "Tc",
    "Th",
    "Ti",
    "Tl",
    "Tm",
    "U",
    "V",
    "W",
    "Y",
    "Yb",
    "Zn",
    "Zr",
)
# Nonmetals are also allowlisted instead of being inferred as the complement of
# the metal set; metalloids and disputed superheavy classifications stay unresolved.
MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS = (
    "Ar",
    "Br",
    "C",
    "Cl",
    "F",
    "H",
    "He",
    "I",
    "Kr",
    "N",
    "Ne",
    "O",
    "P",
    "Rn",
    "S",
    "Se",
    "Xe",
)

_CHEM_COMP_CATEGORY = "_chem_comp"
_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_METAL_ELEMENTS = frozenset(MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS)
_NONMETAL_ION_ELEMENTS = frozenset(MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS)


class MmcifNonpolyComponentRoleError(ValueError):
    """Stable fail-closed role error without opaque source-value echo."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_component_role:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True)
class MmcifNonpolyComponentRoleCategoryBinding:
    category: str
    headers: tuple[str, ...]
    interpreted_headers: tuple[str, ...]
    uninterpreted_headers: tuple[str, ...]
    row_count: int
    selected_row_count: int
    source_ordinal: int
    row_sha256: tuple[str, ...]
    selected_row_sha256: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "representation": "loop",
            "headers": list(self.headers),
            "interpreted_headers": list(self.interpreted_headers),
            "uninterpreted_headers": list(self.uninterpreted_headers),
            "row_count": self.row_count,
            "selected_row_count": self.selected_row_count,
            "source_ordinal": self.source_ordinal,
            "row_sha256": list(self.row_sha256),
            "selected_row_sha256": list(self.selected_row_sha256),
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyComponentRole:
    instance_identity_sha256: str
    component_id: str
    entity_type: str
    chem_comp_type: str
    composition_role: str
    role_status: str
    preparation_disposition: str
    atom_count: int
    element_counts: tuple[tuple[str, int], ...]
    formal_charge_state: str
    total_formal_charge: int | None
    role_blockers: tuple[str, ...]
    role_identity_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyComponentRole("
            f"entity_type={self.entity_type!r}, "
            f"composition_role={self.composition_role!r}, "
            f"atom_count={self.atom_count})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_id": self.component_id,
            "entity_type": self.entity_type,
            "chem_comp_type": self.chem_comp_type,
            "composition_role": self.composition_role,
            "role_status": self.role_status,
            "preparation_disposition": self.preparation_disposition,
            "atom_count": self.atom_count,
            "element_counts": dict(self.element_counts),
            "formal_charge_state": self.formal_charge_state,
            "total_formal_charge": self.total_formal_charge,
            "role_blockers": list(self.role_blockers),
            "role_identity_sha256": self.role_identity_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyComponentRoleSnapshot:
    source_sha256: str
    identity_snapshot_sha256: str
    identity_projection_sha256: str
    identity_source_binding_sha256: str
    component_snapshot_sha256: str
    component_projection_sha256: str
    component_source_binding_sha256: str
    roles: tuple[MmcifNonpolyComponentRole, ...]
    chem_comp_binding: MmcifNonpolyComponentRoleCategoryBinding

    def __repr__(self) -> str:
        return f"MmcifNonpolyComponentRoleSnapshot(role_count={len(self.roles)})"

    @property
    def role_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_component_role_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_component_role_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
                "role_projection_sha256": self.role_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        roles = sorted({row.composition_role for row in self.roles})
        statuses = sorted({row.role_status for row in self.roles})
        return {
            "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "role_count": len(self.roles),
            "composition_role_counts": {
                value: sum(row.composition_role == value for row in self.roles)
                for value in roles
            },
            "role_status_counts": {
                value: sum(row.role_status == value for row in self.roles)
                for value in statuses
            },
            "role_projection_sha256": self.role_projection_sha256,
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
        "source_entity_type_interpreted": True,
        "chem_comp_type_interpreted": True,
        "component_element_composition_interpreted": True,
        "component_formal_charge_composition_interpreted": True,
        "source_water_role_interpreted": True,
        "monoatomic_metal_composition_interpreted": True,
        "monoatomic_nonmetal_ion_composition_interpreted": True,
        "bounded_composition_role_interpreted": True,
        "formal_charge_default_inferred": False,
        "general_ligand_role_interpreted": False,
        "cofactor_role_interpreted": False,
        "modified_residue_role_interpreted": False,
        "biological_function_inferred": False,
        "metal_coordination_chemistry_interpreted": False,
        "ion_parameterization_supported": False,
        "metal_parameterization_supported": False,
        "preparation_ready": False,
        "parameterable": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _row_sha(loop: CifLoop, row: tuple[CifToken, ...]) -> str:
    return _sha256(
        [
            {
                "tag": tag,
                "value": token.value,
                "quoted": bool(token.quoted),
                "multiline": bool(token.multiline),
            }
            for tag, token in zip(loop.tags, row, strict=True)
        ]
    )


def _known_value(token: CifToken) -> str:
    if token.multiline or (not token.quoted and token.value in {".", "?"}):
        raise MmcifNonpolyComponentRoleError(
            "required_role_value_missing",
            "one required component-role source value is unavailable",
            line_number=token.line_number,
        )
    value = token.value.strip()
    if not value:
        raise MmcifNonpolyComponentRoleError(
            "required_role_value_missing",
            "one required component-role source value is empty",
            line_number=token.line_number,
        )
    return value


def _known_code(token: CifToken) -> str:
    return _known_value(token).lower()


def _chem_comp_types(
    text: str,
    selected_component_ids: set[str],
) -> tuple[dict[str, str], MmcifNonpolyComponentRoleCategoryBinding]:
    block = parse_cif_block(text)
    scalar_tags = tuple(
        tag for tag in block.scalar_values if tag.startswith(f"{_CHEM_COMP_CATEGORY}.")
    )
    if scalar_tags:
        raise MmcifNonpolyComponentRoleError(
            "category_must_be_loop",
            "_chem_comp must use one category-local loop",
            line_number=block.scalar_values[scalar_tags[0]].line_number,
        )
    loops = [loop for loop in block.loops if _CHEM_COMP_CATEGORY in loop.categories]
    if len(loops) != 1:
        raise MmcifNonpolyComponentRoleError(
            "chem_comp_loop_count_mismatch",
            "_chem_comp must occur in exactly one category-local loop",
        )
    loop = loops[0]
    if loop.categories != (_CHEM_COMP_CATEGORY,):
        raise MmcifNonpolyComponentRoleError(
            "mixed_category_loop",
            "cross-category _chem_comp loops are outside this bounded role profile",
            line_number=loop.line_number,
        )
    index = {tag: position for position, tag in enumerate(loop.tags)}
    if any(
        header not in index for header in MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS
    ):
        raise MmcifNonpolyComponentRoleError(
            "required_chem_comp_header_missing",
            "_chem_comp is missing a reviewed role header",
            line_number=loop.line_number,
        )
    selected: dict[str, str] = {}
    selected_hashes: list[str] = []
    row_hashes: list[str] = []
    for row in loop.rows:
        row_hash = _row_sha(loop, row)
        row_hashes.append(row_hash)
        comp_id = _known_value(row[index["_chem_comp.id"]])
        if comp_id not in selected_component_ids:
            continue
        if comp_id in selected:
            raise MmcifNonpolyComponentRoleError(
                "duplicate_selected_component_type",
                "selected components must have exactly one _chem_comp type row",
                line_number=row[index["_chem_comp.id"]].line_number,
            )
        comp_type = _known_code(row[index["_chem_comp.type"]])
        if comp_type not in MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES:
            raise MmcifNonpolyComponentRoleError(
                "selected_component_type_not_nonpolymer",
                "selected nonpoly components must use the reviewed non-polymer type",
                line_number=row[index["_chem_comp.type"]].line_number,
            )
        selected[comp_id] = comp_type
        selected_hashes.append(row_hash)
    if set(selected) != selected_component_ids:
        raise MmcifNonpolyComponentRoleError(
            "selected_component_type_coverage_mismatch",
            "_chem_comp type rows must exactly cover selected nonpoly components",
        )
    interpreted = frozenset(MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS)
    return selected, MmcifNonpolyComponentRoleCategoryBinding(
        category=_CHEM_COMP_CATEGORY,
        headers=tuple(loop.tags),
        interpreted_headers=tuple(tag for tag in loop.tags if tag in interpreted),
        uninterpreted_headers=tuple(tag for tag in loop.tags if tag not in interpreted),
        row_count=len(loop.rows),
        selected_row_count=len(selected),
        source_ordinal=block.category_order.index(_CHEM_COMP_CATEGORY),
        row_sha256=tuple(row_hashes),
        selected_row_sha256=tuple(selected_hashes),
    )


def _component_composition(
    declarations: tuple[MmcifNonpolyComponentAtomDeclaration, ...],
) -> tuple[tuple[tuple[str, int], ...], str, int | None, list[str]]:
    blockers: list[str] = []
    element_counts: dict[str, int] = {}
    charges: list[int] = []
    charge_available = True
    for declaration in declarations:
        if declaration.type_symbol.state != "known":
            blockers.append("element_composition_unavailable")
        else:
            element = canonical_element_symbol(declaration.type_symbol.value)
            if atomic_number_for_element(element) == 0:
                raise MmcifNonpolyComponentRoleError(
                    "invalid_component_element_symbol",
                    "one component atom element is outside the canonical periodic table",
                    line_number=declaration.type_symbol.line_number,
                )
            element_counts[element] = element_counts.get(element, 0) + 1
        if declaration.charge.state != "known":
            charge_available = False
            blockers.append("formal_charge_composition_unavailable")
            continue
        if _INTEGER_RE.fullmatch(declaration.charge.value) is None:
            raise MmcifNonpolyComponentRoleError(
                "invalid_component_formal_charge",
                "component atom charge must use the PDBx/mmCIF integer grammar",
                line_number=declaration.charge.line_number,
            )
        charge = int(declaration.charge.value)
        if not -8 <= charge <= 8:
            raise MmcifNonpolyComponentRoleError(
                "component_formal_charge_out_of_bounds",
                "component atom charge is outside the PDBx/mmCIF dictionary boundary",
                line_number=declaration.charge.line_number,
            )
        charges.append(charge)
    return (
        tuple(sorted(element_counts.items())),
        "known" if charge_available else "unavailable",
        sum(charges) if charge_available else None,
        list(dict.fromkeys(blockers)),
    )


def _classify_role(
    *,
    instance_identity_sha256: str,
    component_id: str,
    entity_type: str,
    chem_comp_type: str,
    declarations: tuple[MmcifNonpolyComponentAtomDeclaration, ...],
) -> MmcifNonpolyComponentRole:
    element_counts, charge_state, total_charge, blockers = _component_composition(
        declarations
    )
    atom_count = len(declarations)
    element_map = dict(element_counts)
    sole_element = element_counts[0][0] if len(element_counts) == 1 else ""
    if entity_type == "water":
        valid_formula = element_map in ({"O": 1}, {"H": 2, "O": 1})
        valid_charge = charge_state == "known" and total_charge == 0
        if valid_formula and valid_charge and not blockers:
            role = "water"
            status = "interpreted"
            disposition = "eligible_for_bounded_preparation"
        else:
            role = "water_composition_mismatch"
            status = "inconsistent"
            disposition = "explicitly_unsupported"
            blockers.extend(
                value
                for value, condition in (
                    ("water_element_composition_mismatch", not valid_formula),
                    ("water_formal_charge_mismatch", not valid_charge),
                )
                if condition
            )
    elif (
        atom_count == 1 and sole_element in _METAL_ELEMENTS and len(element_counts) == 1
    ):
        role = "monoatomic_metal_component"
        status = "interpreted"
        disposition = "explicitly_unsupported"
        blockers.append("monoatomic_metal_preparation_not_supported")
    elif (
        atom_count == 1
        and len(element_counts) == 1
        and sole_element in _NONMETAL_ION_ELEMENTS
        and charge_state == "known"
        and total_charge not in {None, 0}
    ):
        role = "monoatomic_nonmetal_ion"
        status = "interpreted"
        disposition = "explicitly_unsupported"
        blockers.append("monoatomic_nonmetal_ion_preparation_not_supported")
    else:
        role = "unresolved_nonpoly_component"
        status = "unresolved"
        disposition = "eligible_for_chemistry_gate_only"
        blockers.append("ligand_cofactor_and_other_nonpoly_roles_not_interpreted")
    blockers = list(dict.fromkeys(blockers))
    identity_payload = {
        "instance_identity_sha256": instance_identity_sha256,
        "component_id": component_id,
        "entity_type": entity_type,
        "chem_comp_type": chem_comp_type,
        "composition_role": role,
        "role_status": status,
        "preparation_disposition": disposition,
        "atom_count": atom_count,
        "element_counts": dict(element_counts),
        "formal_charge_state": charge_state,
        "total_formal_charge": total_charge,
        "role_blockers": blockers,
    }
    return MmcifNonpolyComponentRole(
        instance_identity_sha256=instance_identity_sha256,
        component_id=component_id,
        entity_type=entity_type,
        chem_comp_type=chem_comp_type,
        composition_role=role,
        role_status=status,
        preparation_disposition=disposition,
        atom_count=atom_count,
        element_counts=element_counts,
        formal_charge_state=charge_state,
        total_formal_charge=total_charge,
        role_blockers=tuple(blockers),
        role_identity_sha256=_sha256(identity_payload),
    )


def parse_mmcif_nonpoly_component_roles(text: str) -> MmcifNonpolyComponentRoleSnapshot:
    """Interpret only bounded, source-provable nonpoly composition roles."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly component-role input must be a string")
    identity = parse_mmcif_nonpoly_identity(text)
    components = parse_mmcif_nonpoly_component_declarations(text)
    if identity.source_sha256 != components.source_sha256:
        raise MmcifNonpolyComponentRoleError(
            "source_carrier_mismatch",
            "identity and component carriers must bind the same source bytes",
        )
    selected_ids = {row.comp_id for row in identity.components}
    comp_types, binding = _chem_comp_types(text, selected_ids)
    atoms_by_component: dict[str, list[MmcifNonpolyComponentAtomDeclaration]] = {
        comp_id: [] for comp_id in selected_ids
    }
    for declaration in components.atom_declarations:
        if declaration.comp_id in atoms_by_component:
            atoms_by_component[declaration.comp_id].append(declaration)
    if any(not rows for rows in atoms_by_component.values()):
        raise MmcifNonpolyComponentRoleError(
            "component_atom_coverage_mismatch",
            "every selected component role requires component atom declarations",
        )
    entities = {row.entity_id: row for row in identity.entities}
    roles: list[MmcifNonpolyComponentRole] = []
    for instance in identity.instances:
        entity = entities.get(instance.entity_id)
        if entity is None or entity.comp_id != instance.mon_id:
            raise MmcifNonpolyComponentRoleError(
                "instance_entity_component_mismatch",
                "component-role instances must preserve the identity carrier join",
            )
        roles.append(
            _classify_role(
                instance_identity_sha256=instance.instance_identity_sha256,
                component_id=instance.mon_id,
                entity_type=instance.entity_type,
                chem_comp_type=comp_types[instance.mon_id],
                declarations=tuple(atoms_by_component[instance.mon_id]),
            )
        )
    return MmcifNonpolyComponentRoleSnapshot(
        source_sha256=identity.source_sha256,
        identity_snapshot_sha256=identity.snapshot_sha256,
        identity_projection_sha256=identity.identity_projection_sha256,
        identity_source_binding_sha256=identity.source_binding_sha256,
        component_snapshot_sha256=components.snapshot_sha256,
        component_projection_sha256=components.declaration_projection_sha256,
        component_source_binding_sha256=components.source_binding_sha256,
        roles=tuple(roles),
        chem_comp_binding=binding,
    )


def mmcif_nonpoly_component_role_projection(
    snapshot: MmcifNonpolyComponentRoleSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION,
        "identity_projection_sha256": snapshot.identity_projection_sha256,
        "component_projection_sha256": snapshot.component_projection_sha256,
        "roles": [row.to_dict() for row in snapshot.roles],
        "role_order": "nonpoly_instance_source_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_component_role_source_binding(
    snapshot: MmcifNonpolyComponentRoleSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "identity_snapshot_sha256": snapshot.identity_snapshot_sha256,
        "identity_source_binding_sha256": snapshot.identity_source_binding_sha256,
        "component_snapshot_sha256": snapshot.component_snapshot_sha256,
        "component_source_binding_sha256": snapshot.component_source_binding_sha256,
        "dictionary_items": dict(MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS),
        "accepted_chem_comp_types": list(
            MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES
        ),
        "metal_element_policy": list(MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS),
        "nonmetal_ion_element_policy": list(
            MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS
        ),
        "metal_element_policy_kind": "bounded_explicit_applicability_set",
        "nonmetal_ion_element_policy_kind": "bounded_explicit_applicability_set",
        "chem_comp_binding": snapshot.chem_comp_binding.to_dict(),
    }


def mmcif_nonpoly_component_role_document(
    snapshot: MmcifNonpolyComponentRoleSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_component_role_projection(snapshot)
    binding = mmcif_nonpoly_component_role_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION,
        "role_projection": projection,
        "source_binding": binding,
        "role_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"nonpoly component-role {label} digest invalid")
    return candidate


def _require_role(payload: object) -> tuple[str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly component role must be a mapping")
    role = dict(payload)
    instance = _require_digest(
        role.get("instance_identity_sha256"), "instance identity"
    )
    component_id = role.get("component_id")
    if type(component_id) is not str or not component_id:
        raise ValueError("nonpoly component-role component id invalid")
    if role.get("entity_type") not in {"non-polymer", "water"}:
        raise ValueError("nonpoly component-role entity type invalid")
    if role.get("chem_comp_type") not in (
        MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES
    ):
        raise ValueError("nonpoly component-role chem_comp type invalid")
    atom_count = role.get("atom_count")
    element_counts = role.get("element_counts")
    if (
        type(atom_count) is not int
        or atom_count <= 0
        or not isinstance(element_counts, Mapping)
        or any(
            type(key) is not str
            or atomic_number_for_element(key) == 0
            or canonical_element_symbol(key) != key
            or type(value) is not int
            or value <= 0
            for key, value in element_counts.items()
        )
        or sum(element_counts.values()) > atom_count
    ):
        raise ValueError("nonpoly component-role element composition invalid")
    charge_state = role.get("formal_charge_state")
    total_charge = role.get("total_formal_charge")
    if charge_state == "known":
        if type(total_charge) is not int:
            raise ValueError("nonpoly component-role total charge invalid")
    elif charge_state == "unavailable":
        if total_charge is not None:
            raise ValueError("nonpoly component-role unavailable charge mismatch")
    else:
        raise ValueError("nonpoly component-role charge state invalid")
    blockers = role.get("role_blockers")
    if (
        not isinstance(blockers, list)
        or not all(type(value) is str and value for value in blockers)
        or len(set(blockers)) != len(blockers)
    ):
        raise ValueError("nonpoly component-role blocker list invalid")

    known_element_count = sum(element_counts.values())
    expected_availability_blockers = {
        *(
            ("element_composition_unavailable",)
            if known_element_count < atom_count
            else ()
        ),
        *(
            ("formal_charge_composition_unavailable",)
            if charge_state == "unavailable"
            else ()
        ),
    }
    observed_availability_blockers = {
        value
        for value in blockers
        if value
        in {
            "element_composition_unavailable",
            "formal_charge_composition_unavailable",
        }
    }
    if observed_availability_blockers != expected_availability_blockers:
        raise ValueError("nonpoly component-role availability blocker mismatch")

    composition_role = role.get("composition_role")
    status = role.get("role_status")
    disposition = role.get("preparation_disposition")
    if composition_role == "water":
        if (
            role.get("entity_type") != "water"
            or dict(element_counts) not in ({"O": 1}, {"H": 2, "O": 1})
            or charge_state != "known"
            or total_charge != 0
            or status != "interpreted"
            or disposition != "eligible_for_bounded_preparation"
            or blockers
        ):
            raise ValueError("nonpoly source-water role mismatch")
    elif composition_role == "monoatomic_metal_component":
        if (
            role.get("entity_type") != "non-polymer"
            or atom_count != 1
            or len(element_counts) != 1
            or next(iter(element_counts)) not in _METAL_ELEMENTS
            or status != "interpreted"
            or disposition != "explicitly_unsupported"
            or "monoatomic_metal_preparation_not_supported" not in blockers
        ):
            raise ValueError("nonpoly monoatomic-metal role mismatch")
    elif composition_role == "monoatomic_nonmetal_ion":
        if (
            role.get("entity_type") != "non-polymer"
            or atom_count != 1
            or len(element_counts) != 1
            or next(iter(element_counts)) not in _NONMETAL_ION_ELEMENTS
            or charge_state != "known"
            or total_charge in {None, 0}
            or status != "interpreted"
            or disposition != "explicitly_unsupported"
            or "monoatomic_nonmetal_ion_preparation_not_supported" not in blockers
        ):
            raise ValueError("nonpoly monoatomic-nonmetal-ion role mismatch")
    elif composition_role == "unresolved_nonpoly_component":
        if (
            role.get("entity_type") != "non-polymer"
            or status != "unresolved"
            or disposition != "eligible_for_chemistry_gate_only"
            or "ligand_cofactor_and_other_nonpoly_roles_not_interpreted" not in blockers
        ):
            raise ValueError("nonpoly unresolved role mismatch")
    elif composition_role == "water_composition_mismatch":
        valid_formula = dict(element_counts) in ({"O": 1}, {"H": 2, "O": 1})
        valid_charge = charge_state == "known" and total_charge == 0
        if (
            role.get("entity_type") != "water"
            or (valid_formula and valid_charge and not expected_availability_blockers)
            or status != "inconsistent"
            or disposition != "explicitly_unsupported"
            or not {
                "water_element_composition_mismatch",
                "water_formal_charge_mismatch",
            }.intersection(blockers)
        ):
            raise ValueError("nonpoly water mismatch role invalid")
    else:
        raise ValueError("nonpoly component-role vocabulary invalid")

    sole_element = next(iter(element_counts)) if len(element_counts) == 1 else ""
    if role.get("entity_type") == "water":
        valid_formula = dict(element_counts) in ({"O": 1}, {"H": 2, "O": 1})
        valid_charge = charge_state == "known" and total_charge == 0
        expected_role = (
            "water"
            if valid_formula and valid_charge and not expected_availability_blockers
            else "water_composition_mismatch"
        )
    elif (
        atom_count == 1 and known_element_count == 1 and sole_element in _METAL_ELEMENTS
    ):
        expected_role = "monoatomic_metal_component"
    elif (
        atom_count == 1
        and known_element_count == 1
        and sole_element in _NONMETAL_ION_ELEMENTS
        and charge_state == "known"
        and total_charge not in {None, 0}
    ):
        expected_role = "monoatomic_nonmetal_ion"
    else:
        expected_role = "unresolved_nonpoly_component"
    if composition_role != expected_role:
        raise ValueError("nonpoly component-role deterministic classification mismatch")
    expected_blockers = set(expected_availability_blockers)
    if expected_role == "water_composition_mismatch":
        if not valid_formula:
            expected_blockers.add("water_element_composition_mismatch")
        if not valid_charge:
            expected_blockers.add("water_formal_charge_mismatch")
    elif expected_role == "monoatomic_metal_component":
        expected_blockers.add("monoatomic_metal_preparation_not_supported")
    elif expected_role == "monoatomic_nonmetal_ion":
        expected_blockers.add("monoatomic_nonmetal_ion_preparation_not_supported")
    elif expected_role == "unresolved_nonpoly_component":
        expected_blockers.add("ligand_cofactor_and_other_nonpoly_roles_not_interpreted")
    if set(blockers) != expected_blockers:
        raise ValueError("nonpoly component-role deterministic blocker mismatch")

    identity_payload = {
        "instance_identity_sha256": instance,
        "component_id": component_id,
        "entity_type": role["entity_type"],
        "chem_comp_type": role["chem_comp_type"],
        "composition_role": composition_role,
        "role_status": status,
        "preparation_disposition": disposition,
        "atom_count": atom_count,
        "element_counts": dict(element_counts),
        "formal_charge_state": charge_state,
        "total_formal_charge": total_charge,
        "role_blockers": blockers,
    }
    if role.get("role_identity_sha256") != _sha256(identity_payload):
        raise ValueError("nonpoly component-role identity mismatch")
    return instance, str(composition_role)


def require_mmcif_nonpoly_component_role_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly component-role document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly component-role document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID:
        raise ValueError("nonpoly component-role profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION:
        raise ValueError("nonpoly component-role parser version mismatch")
    projection = document.get("role_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly component-role sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_COMPONENT_ROLE_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly component-role projection schema mismatch")
    if (
        projection.get("profile_id") != MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID
        or projection.get("parser_version")
        != MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION
        or projection.get("role_order") != "nonpoly_instance_source_order"
    ):
        raise ValueError("nonpoly component-role projection policy mismatch")
    if (
        binding.get("schema_id")
        != MMCIF_NONPOLY_COMPONENT_ROLE_SOURCE_BINDING_SCHEMA_ID
    ):
        raise ValueError("nonpoly component-role source binding schema mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("role_projection_sha256") != projection_digest:
        raise ValueError("nonpoly component-role projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly component-role source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID,
            "role_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly component-role snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly component-role claim policy mismatch")

    roles = projection.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ValueError("nonpoly component-role rows must be non-empty")
    instances: set[str] = set()
    observed_roles: list[str] = []
    for role in roles:
        instance, composition_role = _require_role(role)
        if instance in instances:
            raise ValueError("nonpoly component-role instances must be unique")
        instances.add(instance)
        observed_roles.append(composition_role)
    if document.get("role_count") != len(roles):
        raise ValueError("nonpoly component-role count mismatch")
    expected_role_counts = {
        value: observed_roles.count(value) for value in sorted(set(observed_roles))
    }
    if document.get("composition_role_counts") != expected_role_counts:
        raise ValueError("nonpoly component-role summary mismatch")
    statuses = [str(row["role_status"]) for row in roles]
    expected_status_counts = {
        value: statuses.count(value) for value in sorted(set(statuses))
    }
    if document.get("role_status_counts") != expected_status_counts:
        raise ValueError("nonpoly component-role status summary mismatch")

    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly component-role source digest mismatch")
    for key in ("identity_projection_sha256", "component_projection_sha256"):
        _require_digest(projection.get(key), key)
    for key in (
        "identity_snapshot_sha256",
        "identity_source_binding_sha256",
        "component_snapshot_sha256",
        "component_source_binding_sha256",
    ):
        _require_digest(binding.get(key), key)
    if binding.get("dictionary_items") != MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS:
        raise ValueError("nonpoly component-role dictionary binding mismatch")
    if (
        binding.get("accepted_chem_comp_types")
        != list(MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES)
        or binding.get("metal_element_policy")
        != list(MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS)
        or binding.get("nonmetal_ion_element_policy")
        != list(MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS)
        or binding.get("metal_element_policy_kind")
        != "bounded_explicit_applicability_set"
        or binding.get("nonmetal_ion_element_policy_kind")
        != "bounded_explicit_applicability_set"
    ):
        raise ValueError("nonpoly component-role applicability policy mismatch")
    category = binding.get("chem_comp_binding")
    if not isinstance(category, Mapping):
        raise ValueError("nonpoly component-role category binding missing")
    unique_components = {
        str(row["component_id"]) for row in roles if isinstance(row, Mapping)
    }
    category_headers = category.get("headers")
    category_uninterpreted = category.get("uninterpreted_headers")
    row_count = category.get("row_count")
    selected_row_count = category.get("selected_row_count")
    row_hashes = category.get("row_sha256")
    selected_row_hashes = category.get("selected_row_sha256")
    interpreted_headers = category.get("interpreted_headers")
    if (
        category.get("category") != _CHEM_COMP_CATEGORY
        or category.get("representation") != "loop"
        or not isinstance(category_headers, list)
        or not all(type(value) is str and value for value in category_headers)
        or len(set(category_headers)) != len(category_headers)
        or not isinstance(interpreted_headers, list)
        or set(interpreted_headers)
        != set(MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS)
        or interpreted_headers
        != [
            value
            for value in category_headers
            if value in MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS
        ]
        or category_uninterpreted
        != [
            value
            for value in category_headers
            if value not in MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS
        ]
        or type(row_count) is not int
        or row_count < len(unique_components)
        or selected_row_count != len(unique_components)
        or type(category.get("source_ordinal")) is not int
        or category.get("source_ordinal") < 0
        or not isinstance(row_hashes, list)
        or len(row_hashes) != row_count
        or not all(_SHA256_RE.fullmatch(str(value or "")) for value in row_hashes)
        or not isinstance(selected_row_hashes, list)
        or len(selected_row_hashes) != len(unique_components)
        or not all(value in row_hashes for value in selected_row_hashes)
    ):
        raise ValueError("nonpoly component-role category binding invalid")
    return payload


def mmcif_nonpoly_component_role_json_bytes(
    snapshot: MmcifNonpolyComponentRoleSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_component_role_document(snapshot))


def write_mmcif_nonpoly_component_role_json(
    path: str | Path,
    snapshot: MmcifNonpolyComponentRoleSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_component_role_json_bytes(snapshot) + b"\n"
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
    "MMCIF_NONPOLY_COMPONENT_ROLE_ACCEPTED_CHEM_COMP_TYPES",
    "MMCIF_NONPOLY_COMPONENT_ROLE_CHEM_COMP_HEADERS",
    "MMCIF_NONPOLY_COMPONENT_ROLE_DICTIONARY_ITEMS",
    "MMCIF_NONPOLY_COMPONENT_ROLE_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_COMPONENT_ROLE_METAL_ELEMENTS",
    "MMCIF_NONPOLY_COMPONENT_ROLE_NONMETAL_ION_ELEMENTS",
    "MMCIF_NONPOLY_COMPONENT_ROLE_PARSER_VERSION",
    "MMCIF_NONPOLY_COMPONENT_ROLE_PROFILE_ID",
    "MMCIF_NONPOLY_COMPONENT_ROLE_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_COMPONENT_ROLE_SOURCE_BINDING_SCHEMA_ID",
    "MmcifNonpolyComponentRole",
    "MmcifNonpolyComponentRoleCategoryBinding",
    "MmcifNonpolyComponentRoleError",
    "MmcifNonpolyComponentRoleSnapshot",
    "mmcif_nonpoly_component_role_document",
    "mmcif_nonpoly_component_role_json_bytes",
    "mmcif_nonpoly_component_role_projection",
    "mmcif_nonpoly_component_role_source_binding",
    "parse_mmcif_nonpoly_component_roles",
    "require_mmcif_nonpoly_component_role_document",
    "write_mmcif_nonpoly_component_role_json",
]
