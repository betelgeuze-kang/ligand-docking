"""Pinned offline ALA/GLY heavy-to-all-atom completion rules.

This module admits one deliberately narrow profile: deterministic completion
of the already pinned official CCD ALA and GLY heavy-atom records to the fixed
neutral all-atom microstate used by the standard-L-peptide preparation rules.
The pinned ideal coordinates define a deterministic local placement template
and a bounded geometry-admission contract.  They are not scientific geometry
validation, an environmental-pH assertion, or generic/global preparation
authority.  Runtime use performs no network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
from typing import Any

from .standard_l_peptide_preparation_rules import (
    STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES,
    STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES,
    STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256,
    StandardLPeptidePreparationComponentRule,
    validate_standard_l_peptide_preparation_rule_manifest,
)


STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.standard_l_peptide_heavy_to_fixed_neutral_all_atom_"
    "completion_rule_manifest/1.0.0"
)
STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION = "1.0.0"
STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256 = (
    "eed2b432c6a4b916370e14d922830a5eeb9f531acc579c94b7e823b8949810c6"
)


class StandardLPeptideCompletionRuleError(ValueError):
    """Raised when a bounded completion-rule request cannot be satisfied."""


@dataclass(frozen=True, slots=True)
class StandardLPeptideCompletionAtomRule:
    """One atom's exact CCD ideal-coordinate tokens and completion parent."""

    atom_id: str
    element: str
    formal_charge: int
    ccd_ordinal: int
    ideal_x_token: str
    ideal_y_token: str
    ideal_z_token: str
    hydrogen_parent_atom_id: str | None

    @property
    def ideal_coordinate(self) -> tuple[float, float, float]:
        """Return a numerical view without weakening the pinned string tokens."""

        return (
            float(self.ideal_x_token),
            float(self.ideal_y_token),
            float(self.ideal_z_token),
        )


@dataclass(frozen=True, slots=True)
class StandardLPeptideCompletionHeavyBondRule:
    """One source heavy-atom bond admitted by the geometry contract."""

    atom_id_1: str
    atom_id_2: str
    value_order: str
    ccd_ordinal: int


@dataclass(frozen=True, slots=True)
class StandardLPeptideCompletionComponentRule:
    """Pinned source and placement rules for one admitted component."""

    component_id: str
    rule_id: str
    source_preparation_rule_id: str
    ccd_download_url: str
    ccd_file_sha256: str
    ccd_file_size_bytes: int
    ccd_retrieval_date: str
    frame_anchor_atom_ids: tuple[str, str, str]
    atoms: tuple[StandardLPeptideCompletionAtomRule, ...]
    source_heavy_bonds: tuple[StandardLPeptideCompletionHeavyBondRule, ...]


@dataclass(frozen=True, slots=True)
class StandardLPeptideCompletionRoleRule:
    """Exact role-specific heavy input and fixed-neutral output inventory."""

    component_id: str
    role: str
    required_source_heavy_atom_ids: tuple[str, ...]
    active_hydrogen_atom_ids: tuple[str, ...]
    output_atom_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StandardLPeptideCompletionGeometryContract:
    """Profile admission bounds; explicitly not scientific validation."""

    semantics: str
    heavy_bond_ideal_length_reference: str
    heavy_bond_absolute_tolerance_angstrom: float
    same_asym_adjacent_left_atom_id: str
    same_asym_adjacent_right_atom_id: str
    same_asym_adjacent_c_n_minimum_distance_angstrom: float
    same_asym_adjacent_c_n_maximum_distance_angstrom: float
    distance_bounds_inclusive: bool
    frame_anchor_atom_ids: tuple[str, str, str]
    frame_sine_formula: str
    normalized_frame_sine_minimum: float
    ala_orientation_center_atom_id: str
    ala_orientation_ordered_atom_ids: tuple[str, str, str]
    ala_orientation_formula: str
    ala_orientation_ideal_sign: str
    ala_normalized_absolute_triple_product_minimum: float
    geometry_scientifically_validated: bool


def _source_component_rule(
    component_id: str,
) -> StandardLPeptidePreparationComponentRule:
    for rule in STANDARD_L_PEPTIDE_PREPARATION_COMPONENT_RULES:
        if rule.component_id == component_id:
            return rule
    raise RuntimeError(f"missing pinned preparation component: {component_id}")


def _atom(
    component_id: str,
    atom_id: str,
    x_token: str,
    y_token: str,
    z_token: str,
    *,
    parent: str | None = None,
) -> StandardLPeptideCompletionAtomRule:
    source = _source_component_rule(component_id)
    source_atom = next(atom for atom in source.atoms if atom.atom_id == atom_id)
    return StandardLPeptideCompletionAtomRule(
        atom_id=atom_id,
        element=source_atom.element,
        formal_charge=source_atom.formal_charge,
        ccd_ordinal=source_atom.ccd_ordinal,
        ideal_x_token=x_token,
        ideal_y_token=y_token,
        ideal_z_token=z_token,
        hydrogen_parent_atom_id=parent,
    )


def _component(
    component_id: str,
    atoms: tuple[StandardLPeptideCompletionAtomRule, ...],
) -> StandardLPeptideCompletionComponentRule:
    source = _source_component_rule(component_id)
    element_by_atom = {atom.atom_id: atom.element for atom in source.atoms}
    heavy_bonds = tuple(
        StandardLPeptideCompletionHeavyBondRule(
            atom_id_1=bond.atom_id_1,
            atom_id_2=bond.atom_id_2,
            value_order=bond.value_order,
            ccd_ordinal=bond.ccd_ordinal,
        )
        for bond in source.bonds
        if element_by_atom[bond.atom_id_1] != "H"
        and element_by_atom[bond.atom_id_2] != "H"
    )
    return StandardLPeptideCompletionComponentRule(
        component_id=component_id,
        rule_id=(
            "betelgeuze.standard_l_peptide_heavy_to_fixed_neutral_all_atom_"
            f"completion.{component_id}/1.0.0"
        ),
        source_preparation_rule_id=source.rule_id,
        ccd_download_url=source.ccd_download_url,
        ccd_file_sha256=source.ccd_file_sha256,
        ccd_file_size_bytes=source.ccd_file_size_bytes,
        ccd_retrieval_date="2026-07-15",
        frame_anchor_atom_ids=("N", "CA", "C"),
        atoms=atoms,
        source_heavy_bonds=heavy_bonds,
    )


STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES = (
    _component(
        "ALA",
        (
            _atom("ALA", "N", "-0.966", "0.493", "1.500"),
            _atom("ALA", "CA", "0.257", "0.418", "0.692"),
            _atom("ALA", "C", "-0.094", "0.017", "-0.716"),
            _atom("ALA", "O", "-1.056", "-0.682", "-0.923"),
            _atom("ALA", "CB", "1.204", "-0.620", "1.296"),
            _atom("ALA", "OXT", "0.661", "0.439", "-1.742"),
            _atom("ALA", "H", "-1.383", "-0.425", "1.482", parent="N"),
            _atom("ALA", "H2", "-0.676", "0.661", "2.452", parent="N"),
            _atom("ALA", "HA", "0.746", "1.392", "0.682", parent="CA"),
            _atom("ALA", "HB1", "1.459", "-0.330", "2.316", parent="CB"),
            _atom("ALA", "HB2", "0.715", "-1.594", "1.307", parent="CB"),
            _atom("ALA", "HB3", "2.113", "-0.676", "0.697", parent="CB"),
            _atom("ALA", "HXT", "0.435", "0.182", "-2.647", parent="OXT"),
        ),
    ),
    _component(
        "GLY",
        (
            _atom("GLY", "N", "1.931", "0.090", "-0.034"),
            _atom("GLY", "CA", "0.761", "-0.799", "-0.008"),
            _atom("GLY", "C", "-0.498", "0.029", "-0.005"),
            _atom("GLY", "O", "-0.429", "1.235", "-0.023"),
            _atom("GLY", "OXT", "-1.697", "-0.574", "0.018"),
            _atom("GLY", "H", "1.910", "0.738", "0.738", parent="N"),
            _atom("GLY", "H2", "2.788", "-0.442", "-0.037", parent="N"),
            _atom("GLY", "HA2", "0.772", "-1.440", "-0.889", parent="CA"),
            _atom("GLY", "HA3", "0.793", "-1.415", "0.891", parent="CA"),
            _atom("GLY", "HXT", "-2.477", "-0.002", "0.019", parent="OXT"),
        ),
    ),
)


def _role_rule(component_id: str, role: str) -> StandardLPeptideCompletionRoleRule:
    component = next(
        rule
        for rule in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES
        if rule.component_id == component_id
    )
    preparation_role = next(
        rule for rule in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES if rule.role == role
    )
    deleted = frozenset(preparation_role.deleted_atom_ids)
    retained = tuple(atom for atom in component.atoms if atom.atom_id not in deleted)
    return StandardLPeptideCompletionRoleRule(
        component_id=component_id,
        role=role,
        required_source_heavy_atom_ids=tuple(
            atom.atom_id for atom in retained if atom.element != "H"
        ),
        active_hydrogen_atom_ids=tuple(
            atom.atom_id for atom in retained if atom.element == "H"
        ),
        output_atom_ids=tuple(atom.atom_id for atom in retained),
    )


STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES = tuple(
    _role_rule(component_id, role)
    for component_id in ("ALA", "GLY")
    for role in (
        "singleton",
        "n_sequence_boundary",
        "internal",
        "c_sequence_boundary",
    )
)


STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT = (
    StandardLPeptideCompletionGeometryContract(
        semantics="profile_contract_admission_not_scientific_validation",
        heavy_bond_ideal_length_reference=(
            "euclidean_distance_between_pinned_CCD_ideal_coordinate_decimal_tokens"
        ),
        heavy_bond_absolute_tolerance_angstrom=0.20,
        same_asym_adjacent_left_atom_id="C",
        same_asym_adjacent_right_atom_id="N",
        same_asym_adjacent_c_n_minimum_distance_angstrom=1.15,
        same_asym_adjacent_c_n_maximum_distance_angstrom=1.55,
        distance_bounds_inclusive=True,
        frame_anchor_atom_ids=("N", "CA", "C"),
        frame_sine_formula=("norm(cross(N-CA,C-CA))/(norm(N-CA)*norm(C-CA))"),
        normalized_frame_sine_minimum=0.05,
        ala_orientation_center_atom_id="CA",
        ala_orientation_ordered_atom_ids=("N", "C", "CB"),
        ala_orientation_formula=(
            "dot(cross(N-CA,C-CA),CB-CA)/(norm(N-CA)*norm(C-CA)*norm(CB-CA))"
        ),
        ala_orientation_ideal_sign="positive",
        ala_normalized_absolute_triple_product_minimum=0.05,
        geometry_scientifically_validated=False,
    )
)


def _atom_document(atom: StandardLPeptideCompletionAtomRule) -> dict[str, Any]:
    return {
        "atom_id": atom.atom_id,
        "element": atom.element,
        "formal_charge": atom.formal_charge,
        "ccd_ordinal": atom.ccd_ordinal,
        "ideal_coordinate_decimal_tokens": {
            "x": atom.ideal_x_token,
            "y": atom.ideal_y_token,
            "z": atom.ideal_z_token,
        },
        "hydrogen_parent_atom_id": atom.hydrogen_parent_atom_id,
    }


def _heavy_bond_document(
    bond: StandardLPeptideCompletionHeavyBondRule,
) -> dict[str, Any]:
    return {
        "atom_id_1": bond.atom_id_1,
        "atom_id_2": bond.atom_id_2,
        "value_order": bond.value_order,
        "ccd_ordinal": bond.ccd_ordinal,
    }


def standard_l_peptide_completion_rule_manifest_document() -> dict[str, Any]:
    """Return a fresh deterministic JSON-safe view of the immutable rules."""

    geometry = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT
    return {
        "schema_id": STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID,
        "version": STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION,
        "scope": "bounded_ALA_GLY_heavy_to_fixed_neutral_all_atom_completion",
        "runtime_network_required": False,
        "source_authenticated": False,
        "source_hash_semantics": ("downloaded_file_tamper_evidence_not_authentication"),
        "source_preparation_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
        ),
        "ideal_coordinate_source_fields": [
            "_chem_comp_atom.pdbx_model_Cartn_x_ideal",
            "_chem_comp_atom.pdbx_model_Cartn_y_ideal",
            "_chem_comp_atom.pdbx_model_Cartn_z_ideal",
        ],
        "hydrogen_parent_mapping_source": (
            "official_CCD_chem_comp_bond_exactly_one_hydrogen_to_heavy_bond"
        ),
        "output_formal_charge_policy": {
            "scope": "all_output_atoms",
            "formal_charge": 0,
            "semantics": ("fixed_profile_microstate_not_environmental_pH_correctness"),
        },
        "environmental_pH_correctness_assessed": False,
        "generic_preparation_ready": False,
        "global_preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_execution_authorized": False,
        "claim_safe": False,
        "components": [
            {
                "component_id": component.component_id,
                "rule_id": component.rule_id,
                "source_preparation_rule_id": component.source_preparation_rule_id,
                "ccd_provenance": {
                    "download_url": component.ccd_download_url,
                    "downloaded_file_sha256": component.ccd_file_sha256,
                    "downloaded_file_size_bytes": component.ccd_file_size_bytes,
                    "retrieval_date": component.ccd_retrieval_date,
                },
                "frame_anchor_atom_ids": list(component.frame_anchor_atom_ids),
                "atoms": [_atom_document(atom) for atom in component.atoms],
                "source_heavy_bonds": [
                    _heavy_bond_document(bond) for bond in component.source_heavy_bonds
                ],
            }
            for component in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES
        ],
        "sequence_roles": [
            {
                "component_id": role.component_id,
                "role": role.role,
                "required_source_heavy_atom_ids": list(
                    role.required_source_heavy_atom_ids
                ),
                "active_hydrogen_atom_ids": list(role.active_hydrogen_atom_ids),
                "output_atom_ids": list(role.output_atom_ids),
            }
            for role in STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES
        ],
        "geometry_contract": {
            "semantics": geometry.semantics,
            "source_heavy_intra_residue_bonds": {
                "ideal_length_reference": (geometry.heavy_bond_ideal_length_reference),
                "absolute_tolerance_angstrom": (
                    geometry.heavy_bond_absolute_tolerance_angstrom
                ),
                "bounds_inclusive": geometry.distance_bounds_inclusive,
            },
            "same_asym_adjacent_c_n": {
                "left_atom_id": geometry.same_asym_adjacent_left_atom_id,
                "right_atom_id": geometry.same_asym_adjacent_right_atom_id,
                "minimum_distance_angstrom": (
                    geometry.same_asym_adjacent_c_n_minimum_distance_angstrom
                ),
                "maximum_distance_angstrom": (
                    geometry.same_asym_adjacent_c_n_maximum_distance_angstrom
                ),
                "bounds_inclusive": geometry.distance_bounds_inclusive,
            },
            "n_ca_c_frame": {
                "anchor_atom_ids": list(geometry.frame_anchor_atom_ids),
                "normalized_sine_formula": geometry.frame_sine_formula,
                "normalized_sine_minimum": geometry.normalized_frame_sine_minimum,
                "minimum_inclusive": True,
            },
            "ala_orientation": {
                "center_atom_id": geometry.ala_orientation_center_atom_id,
                "ordered_atom_ids": list(geometry.ala_orientation_ordered_atom_ids),
                "normalized_signed_triple_product_formula": (
                    geometry.ala_orientation_formula
                ),
                "ideal_sign": geometry.ala_orientation_ideal_sign,
                "normalized_absolute_triple_product_minimum": (
                    geometry.ala_normalized_absolute_triple_product_minimum
                ),
                "minimum_inclusive": True,
            },
            "geometry_scientifically_validated": (
                geometry.geometry_scientifically_validated
            ),
        },
    }


def standard_l_peptide_completion_rule_manifest_bytes() -> bytes:
    """Serialize the completion-rule document as canonical ASCII JSON bytes."""

    return json.dumps(
        standard_l_peptide_completion_rule_manifest_document(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


_MANIFEST_KEYS = frozenset(
    {
        "schema_id",
        "version",
        "scope",
        "runtime_network_required",
        "source_authenticated",
        "source_hash_semantics",
        "source_preparation_rule_manifest_sha256",
        "ideal_coordinate_source_fields",
        "hydrogen_parent_mapping_source",
        "output_formal_charge_policy",
        "environmental_pH_correctness_assessed",
        "generic_preparation_ready",
        "global_preparation_ready",
        "parameterability_assessed",
        "physics_supported",
        "runtime_execution_authorized",
        "claim_safe",
        "components",
        "sequence_roles",
        "geometry_contract",
    }
)
_FORMAL_CHARGE_POLICY_KEYS = frozenset({"scope", "formal_charge", "semantics"})
_COMPONENT_KEYS = frozenset(
    {
        "component_id",
        "rule_id",
        "source_preparation_rule_id",
        "ccd_provenance",
        "frame_anchor_atom_ids",
        "atoms",
        "source_heavy_bonds",
    }
)
_PROVENANCE_KEYS = frozenset(
    {
        "download_url",
        "downloaded_file_sha256",
        "downloaded_file_size_bytes",
        "retrieval_date",
    }
)
_ATOM_KEYS = frozenset(
    {
        "atom_id",
        "element",
        "formal_charge",
        "ccd_ordinal",
        "ideal_coordinate_decimal_tokens",
        "hydrogen_parent_atom_id",
    }
)
_COORDINATE_KEYS = frozenset({"x", "y", "z"})
_HEAVY_BOND_KEYS = frozenset({"atom_id_1", "atom_id_2", "value_order", "ccd_ordinal"})
_ROLE_KEYS = frozenset(
    {
        "component_id",
        "role",
        "required_source_heavy_atom_ids",
        "active_hydrogen_atom_ids",
        "output_atom_ids",
    }
)
_GEOMETRY_KEYS = frozenset(
    {
        "semantics",
        "source_heavy_intra_residue_bonds",
        "same_asym_adjacent_c_n",
        "n_ca_c_frame",
        "ala_orientation",
        "geometry_scientifically_validated",
    }
)
_HEAVY_GEOMETRY_KEYS = frozenset(
    {"ideal_length_reference", "absolute_tolerance_angstrom", "bounds_inclusive"}
)
_ADJACENT_GEOMETRY_KEYS = frozenset(
    {
        "left_atom_id",
        "right_atom_id",
        "minimum_distance_angstrom",
        "maximum_distance_angstrom",
        "bounds_inclusive",
    }
)
_FRAME_GEOMETRY_KEYS = frozenset(
    {
        "anchor_atom_ids",
        "normalized_sine_formula",
        "normalized_sine_minimum",
        "minimum_inclusive",
    }
)
_ALA_ORIENTATION_KEYS = frozenset(
    {
        "center_atom_id",
        "ordered_atom_ids",
        "normalized_signed_triple_product_formula",
        "ideal_sign",
        "normalized_absolute_triple_product_minimum",
        "minimum_inclusive",
    }
)


def _require_exact_keys(
    value: object, expected: frozenset[str], error_code: str
) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != expected:
        raise StandardLPeptideCompletionRuleError(error_code)
    return value


def _validate_exact_document_keys(document: dict[str, Any]) -> None:
    _require_exact_keys(
        document,
        _MANIFEST_KEYS,
        "standard_l_peptide_completion_rule_manifest_top_level_keys_mismatch",
    )
    _require_exact_keys(
        document["output_formal_charge_policy"],
        _FORMAL_CHARGE_POLICY_KEYS,
        "standard_l_peptide_completion_rule_manifest_charge_policy_keys_mismatch",
    )
    if type(document["components"]) is not list:
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_manifest_components_type_mismatch"
        )
    for component in document["components"]:
        component_document = _require_exact_keys(
            component,
            _COMPONENT_KEYS,
            "standard_l_peptide_completion_rule_manifest_component_keys_mismatch",
        )
        _require_exact_keys(
            component_document["ccd_provenance"],
            _PROVENANCE_KEYS,
            "standard_l_peptide_completion_rule_manifest_provenance_keys_mismatch",
        )
        if type(component_document["atoms"]) is not list:
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_manifest_atoms_type_mismatch"
            )
        for atom in component_document["atoms"]:
            atom_document = _require_exact_keys(
                atom,
                _ATOM_KEYS,
                "standard_l_peptide_completion_rule_manifest_atom_keys_mismatch",
            )
            _require_exact_keys(
                atom_document["ideal_coordinate_decimal_tokens"],
                _COORDINATE_KEYS,
                "standard_l_peptide_completion_rule_manifest_coordinate_keys_mismatch",
            )
        if type(component_document["source_heavy_bonds"]) is not list:
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_manifest_heavy_bonds_type_mismatch"
            )
        for bond in component_document["source_heavy_bonds"]:
            _require_exact_keys(
                bond,
                _HEAVY_BOND_KEYS,
                "standard_l_peptide_completion_rule_manifest_heavy_bond_keys_mismatch",
            )
    if type(document["sequence_roles"]) is not list:
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_manifest_roles_type_mismatch"
        )
    for role in document["sequence_roles"]:
        _require_exact_keys(
            role,
            _ROLE_KEYS,
            "standard_l_peptide_completion_rule_manifest_role_keys_mismatch",
        )
    geometry = _require_exact_keys(
        document["geometry_contract"],
        _GEOMETRY_KEYS,
        "standard_l_peptide_completion_rule_manifest_geometry_keys_mismatch",
    )
    _require_exact_keys(
        geometry["source_heavy_intra_residue_bonds"],
        _HEAVY_GEOMETRY_KEYS,
        "standard_l_peptide_completion_rule_manifest_heavy_geometry_keys_mismatch",
    )
    _require_exact_keys(
        geometry["same_asym_adjacent_c_n"],
        _ADJACENT_GEOMETRY_KEYS,
        "standard_l_peptide_completion_rule_manifest_adjacent_geometry_keys_mismatch",
    )
    _require_exact_keys(
        geometry["n_ca_c_frame"],
        _FRAME_GEOMETRY_KEYS,
        "standard_l_peptide_completion_rule_manifest_frame_geometry_keys_mismatch",
    )
    _require_exact_keys(
        geometry["ala_orientation"],
        _ALA_ORIENTATION_KEYS,
        "standard_l_peptide_completion_rule_manifest_orientation_keys_mismatch",
    )


def _expected_hydrogen_parent(
    source: StandardLPeptidePreparationComponentRule, hydrogen_atom_id: str
) -> str:
    element_by_atom = {atom.atom_id: atom.element for atom in source.atoms}
    parents: list[str] = []
    for bond in source.bonds:
        if bond.atom_id_1 == hydrogen_atom_id:
            parents.append(bond.atom_id_2)
        elif bond.atom_id_2 == hydrogen_atom_id:
            parents.append(bond.atom_id_1)
    heavy_parents = tuple(
        parent for parent in parents if element_by_atom.get(parent) != "H"
    )
    if len(heavy_parents) != 1:
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_source_hydrogen_parent_mismatch"
        )
    return heavy_parents[0]


def _validate_rule_invariants() -> None:
    if tuple(
        component.component_id
        for component in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES
    ) != ("ALA", "GLY"):
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_component_set_mismatch"
        )
    if tuple(
        (role.component_id, role.role)
        for role in STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES
    ) != tuple(
        (component_id, role)
        for component_id in ("ALA", "GLY")
        for role in (
            "singleton",
            "n_sequence_boundary",
            "internal",
            "c_sequence_boundary",
        )
    ):
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_role_set_mismatch"
        )

    for component in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES:
        source = _source_component_rule(component.component_id)
        if component.frame_anchor_atom_ids != ("N", "CA", "C"):
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_frame_anchor_mismatch"
            )
        if (
            component.source_preparation_rule_id != source.rule_id
            or component.ccd_download_url != source.ccd_download_url
            or component.ccd_file_sha256 != source.ccd_file_sha256
            or component.ccd_file_size_bytes != source.ccd_file_size_bytes
            or component.ccd_retrieval_date != "2026-07-15"
        ):
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_source_provenance_mismatch"
            )
        if tuple(atom.atom_id for atom in component.atoms) != tuple(
            atom.atom_id for atom in source.atoms
        ):
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_atom_set_mismatch"
            )
        source_atom_by_id = {atom.atom_id: atom for atom in source.atoms}
        for atom in component.atoms:
            source_atom = source_atom_by_id[atom.atom_id]
            if (
                atom.element != source_atom.element
                or atom.formal_charge != 0
                or atom.formal_charge != source_atom.formal_charge
                or atom.ccd_ordinal != source_atom.ccd_ordinal
            ):
                raise StandardLPeptideCompletionRuleError(
                    "standard_l_peptide_completion_rule_atom_metadata_mismatch"
                )
            for token in (
                atom.ideal_x_token,
                atom.ideal_y_token,
                atom.ideal_z_token,
            ):
                if type(token) is not str:
                    raise StandardLPeptideCompletionRuleError(
                        "standard_l_peptide_completion_rule_coordinate_token_type_mismatch"
                    )
                try:
                    coordinate = Decimal(token)
                except InvalidOperation as error:
                    raise StandardLPeptideCompletionRuleError(
                        "standard_l_peptide_completion_rule_invalid_coordinate_token"
                    ) from error
                if not coordinate.is_finite():
                    raise StandardLPeptideCompletionRuleError(
                        "standard_l_peptide_completion_rule_nonfinite_coordinate_token"
                    )
            expected_parent = (
                _expected_hydrogen_parent(source, atom.atom_id)
                if atom.element == "H"
                else None
            )
            if atom.hydrogen_parent_atom_id != expected_parent:
                raise StandardLPeptideCompletionRuleError(
                    "standard_l_peptide_completion_rule_hydrogen_parent_mismatch"
                )

        element_by_atom = {atom.atom_id: atom.element for atom in source.atoms}
        expected_heavy_bonds = tuple(
            (
                bond.atom_id_1,
                bond.atom_id_2,
                bond.value_order,
                bond.ccd_ordinal,
            )
            for bond in source.bonds
            if element_by_atom[bond.atom_id_1] != "H"
            and element_by_atom[bond.atom_id_2] != "H"
        )
        actual_heavy_bonds = tuple(
            (
                bond.atom_id_1,
                bond.atom_id_2,
                bond.value_order,
                bond.ccd_ordinal,
            )
            for bond in component.source_heavy_bonds
        )
        if actual_heavy_bonds != expected_heavy_bonds:
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_heavy_bond_mismatch"
            )

    for completion_role in STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES:
        component = next(
            rule
            for rule in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES
            if rule.component_id == completion_role.component_id
        )
        preparation_role = next(
            rule
            for rule in STANDARD_L_PEPTIDE_PREPARATION_ROLE_RULES
            if rule.role == completion_role.role
        )
        retained = tuple(
            atom
            for atom in component.atoms
            if atom.atom_id not in preparation_role.deleted_atom_ids
        )
        expected_heavy = tuple(atom.atom_id for atom in retained if atom.element != "H")
        expected_hydrogen = tuple(
            atom.atom_id for atom in retained if atom.element == "H"
        )
        expected_output = tuple(atom.atom_id for atom in retained)
        if (
            completion_role.required_source_heavy_atom_ids != expected_heavy
            or completion_role.active_hydrogen_atom_ids != expected_hydrogen
            or completion_role.output_atom_ids != expected_output
        ):
            raise StandardLPeptideCompletionRuleError(
                "standard_l_peptide_completion_rule_role_inventory_mismatch"
            )

    geometry = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT
    if (
        geometry.semantics != "profile_contract_admission_not_scientific_validation"
        or geometry.heavy_bond_absolute_tolerance_angstrom != 0.20
        or geometry.same_asym_adjacent_c_n_minimum_distance_angstrom != 1.15
        or geometry.same_asym_adjacent_c_n_maximum_distance_angstrom != 1.55
        or geometry.frame_anchor_atom_ids != ("N", "CA", "C")
        or geometry.normalized_frame_sine_minimum != 0.05
        or geometry.ala_orientation_center_atom_id != "CA"
        or geometry.ala_orientation_ordered_atom_ids != ("N", "C", "CB")
        or geometry.ala_orientation_ideal_sign != "positive"
        or geometry.ala_normalized_absolute_triple_product_minimum != 0.05
        or not geometry.distance_bounds_inclusive
        or geometry.geometry_scientifically_validated
    ):
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_geometry_contract_mismatch"
        )


def validate_standard_l_peptide_completion_rule_manifest() -> str:
    """Fail closed unless the runtime rule document exactly matches its pin."""

    document = standard_l_peptide_completion_rule_manifest_document()
    _validate_exact_document_keys(document)
    preparation_sha = validate_standard_l_peptide_preparation_rule_manifest()
    if not hmac.compare_digest(
        preparation_sha, STANDARD_L_PEPTIDE_PREPARATION_RULE_MANIFEST_SHA256
    ):
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_source_manifest_hash_mismatch"
        )
    _validate_rule_invariants()
    computed = hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()
    if not hmac.compare_digest(
        computed, STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
    ):
        raise StandardLPeptideCompletionRuleError(
            "standard_l_peptide_completion_rule_manifest_hash_mismatch"
        )
    return STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256


def standard_l_peptide_completion_component_rule(
    component_id: str,
) -> StandardLPeptideCompletionComponentRule:
    """Return the exact immutable completion rule for one component."""

    validate_standard_l_peptide_completion_rule_manifest()
    if type(component_id) is not str:
        raise TypeError("component_id must be a string")
    for rule in STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES:
        if rule.component_id == component_id:
            return rule
    raise StandardLPeptideCompletionRuleError(
        "unsupported_standard_l_peptide_completion_component"
    )


def standard_l_peptide_completion_role_rule(
    component_id: str, role: str
) -> StandardLPeptideCompletionRoleRule:
    """Return the exact component/sequence-role completion inventory."""

    validate_standard_l_peptide_completion_rule_manifest()
    if type(component_id) is not str:
        raise TypeError("component_id must be a string")
    if type(role) is not str:
        raise TypeError("role must be a string")
    for rule in STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES:
        if rule.component_id == component_id and rule.role == role:
            return rule
    if component_id not in {"ALA", "GLY"}:
        raise StandardLPeptideCompletionRuleError(
            "unsupported_standard_l_peptide_completion_component"
        )
    raise StandardLPeptideCompletionRuleError(
        "unsupported_standard_l_peptide_completion_role"
    )


__all__ = [
    "STANDARD_L_PEPTIDE_COMPLETION_COMPONENT_RULES",
    "STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT",
    "STANDARD_L_PEPTIDE_COMPLETION_ROLE_RULES",
    "STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID",
    "STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256",
    "STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION",
    "StandardLPeptideCompletionAtomRule",
    "StandardLPeptideCompletionComponentRule",
    "StandardLPeptideCompletionGeometryContract",
    "StandardLPeptideCompletionHeavyBondRule",
    "StandardLPeptideCompletionRoleRule",
    "StandardLPeptideCompletionRuleError",
    "standard_l_peptide_completion_component_rule",
    "standard_l_peptide_completion_role_rule",
    "standard_l_peptide_completion_rule_manifest_bytes",
    "standard_l_peptide_completion_rule_manifest_document",
    "validate_standard_l_peptide_completion_rule_manifest",
]
