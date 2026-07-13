"""Deterministic writer for a strict parser-owned SMILES graph subset.

The writer is intentionally much narrower than :func:`parse_smiles`.  It
serializes one to 256 ordered organic-subset components whose source atoms and
components already occur in canonical spelling order.  The source graph is a
forest or has one simple ring.  A non-aromatic ring remains limited to three
through eight members with zero or one non-closure double edge and an exact
single closure.  A selected aromatic ring is fully aromatic, has five or six
members, and uses a finite canonical B/C/N/O/P/S atom-token table; every ring
bond is exact aromatic order 1.5.  Parser-typed tetrahedral R/S atoms with
zero or one bracket-explicit hydrogen, and parser-observed positive atom maps,
are re-emitted through a source-order lexical-parity projection.  Parser-typed
E/Z double bonds in the
normalized-spelling-admitted source-forest subset, including selected tree
doubles adjacent to a simple nonaromatic ring, plus the unique non-closure
double of the selected eight-member ring, are re-emitted through graph-derived
slash/backslash carrier constraints.
Source formal charges remain parser-observed
exact values in ``{-1, 0, +1}``.  Parser-expanded implicit hydrogens are omitted;
one bracket-explicit hydrogen is retained only when required by a selected
aromatic token or typed tetrahedral atom.  Everything else fails closed.

Round-trip equality is a versioned source-independent projection.  Raw source
bytes, source/system identifiers, the full snapshot, and parser-observation
digests are receipt-bound but are not promoted to equality or authority
claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import re
import struct
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.contracts import ALL_ATOM_SCHEMA_ID

from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    atomic_number_for_element,
)
from .observation import (
    PARSER_OBSERVATION_SCHEMA_ID,
    attached_parser_observation_sha256_matches,
)
from .serialization import (
    canonical_all_atom_snapshot_digest,
    deserialize_all_atom_system,
    serialize_all_atom_system,
)
from .smiles import (
    SMILES_PARSER_VERSION,
    SmilesIngestCoverage,
    SmilesIngestResult,
    SmilesParseError,
    _load_adapter,
    parse_smiles,
)
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import MolecularValidationError, require_valid_all_atom_system


SMILES_WRITER_VERSION = "1.8.0"
SMILES_REPRESENTABLE_STATE_SCHEMA_ID = "betelgeuze.smiles_representable_state/1.8.0"
SMILES_WRITE_RECEIPT_SCHEMA_ID = "betelgeuze.smiles_write_receipt/1.8.0"
SMILES_ROUND_TRIP_REPORT_SCHEMA_ID = "betelgeuze.smiles_round_trip_report/1.8.0"
SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.smiles_component_cycle_projection/1.3.0"
)
SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID = (
    "betelgeuze.smiles_aromatic_ring_projection/1.0.0"
)
SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID = "betelgeuze.smiles_ez_stereo_projection/1.0.0"
SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID = (
    "betelgeuze.smiles_tetrahedral_stereo_projection/1.0.0"
)

_SMILES_PARSER_NAME = "betelgeuze_strict_smiles"
_MAX_OUTPUT_BYTES = 64 * 1024
_MAX_SOURCE_ATOMS = 4_096
_MAX_EXPANDED_ATOMS = 16_384
_MAX_BONDS = 32_768
_MAX_FRAGMENTS = 256
_MAX_RING_COMPONENTS = 1
# Tetrahedral calibration reparses the bounded source through several
# factory-validation paths.  Separate center and conditional source-size caps
# bound both stereo-dense and sparse-stereo inputs below the general atom limit.
_MAX_TYPED_TETRAHEDRAL_ATOMS = 256
_MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS = 2 * _MAX_TYPED_TETRAHEDRAL_ATOMS + 2
_MIN_RING_SIZE = 3
_MAX_RING_SIZE = 8
_MIN_AROMATIC_RING_SIZE = 5
_MAX_AROMATIC_RING_SIZE = 6
# Accepted E/Z bonds are distinct double edges, so their endpoint pairs bound
# the inventory to at most half the already-bounded source-atom count.
_MAX_TYPED_EZ_BONDS = _MAX_SOURCE_ATOMS // 2
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ELEMENTS = frozenset({"B", "C", "N", "O", "P", "S", "F", "Cl", "Br", "I"})
_SOURCE_FORMAL_CHARGES = frozenset({-1, 0, 1})
_SOURCE_BOND_TOKENS = {1.0: "", 1.5: "", 2.0: "=", 3.0: "#"}
_NONAROMATIC_SOURCE_BOND_TOKENS = {1.0: "", 2.0: "=", 3.0: "#"}
_AROMATIC_SOURCE_ELEMENTS = frozenset({"B", "C", "N", "O", "P", "S"})
_AROMATIC_ATOM_TOKENS: Mapping[tuple[str, int, int], str] = {
    ("B", 0, 0): "b",
    ("B", -1, 1): "[bH-]",
    ("C", 0, 0): "c",
    ("C", -1, 0): "[c-]",
    ("C", -1, 1): "[cH-]",
    ("N", 0, 0): "n",
    ("N", 0, 1): "[nH]",
    ("N", -1, 0): "[n-]",
    ("N", 1, 1): "[nH+]",
    ("O", 0, 0): "o",
    ("O", 1, 0): "[o+]",
    ("O", 1, 1): "[oH+]",
    ("P", 0, 0): "p",
    ("P", 0, 1): "[pH]",
    ("P", -1, 0): "[p-]",
    ("P", 1, 1): "[pH+]",
    ("S", 0, 0): "s",
    ("S", 1, 0): "[s+]",
    ("S", 1, 1): "[sH+]",
}
_FORMAL_CHARGE_PROFILE_ID = "ordered_acyclic_organic_forest_bounded_formal_charge/1.0.0"
_RING_FORMAL_CHARGE_PROFILE_ID = (
    "ordered_forest_with_one_simple_unicyclic_component_bounded_formal_charge/1.0.0"
)
_ALL_SINGLE_CYCLE_PROFILE_ID = (
    "at_most_one_simple_nonaromatic_3_8_member_all_single_bond_source_ring/1.0.0"
)
_ONE_DOUBLE_CYCLE_PROFILE_ID = (
    "at_most_one_simple_nonaromatic_3_8_member_source_ring_with_exactly_one_"
    "nonclosure_double_bond/1.0.0"
)
_ONE_DOUBLE_EZ_CYCLE_PROFILE_ID = (
    "one_simple_nonaromatic_8_member_source_ring_with_exactly_one_nonclosure_"
    "parser_typed_ez_double_bond/1.0.0"
)
_ALL_SINGLE_RING_BOND_PROFILE_ID = "all_single_nonaromatic_stereo_none/1.0.0"
_ONE_DOUBLE_RING_BOND_PROFILE_ID = (
    "one_nonclosure_double_otherwise_single_nonaromatic_stereo_none/1.0.0"
)
_ONE_DOUBLE_EZ_RING_BOND_PROFILE_ID = (
    "one_nonclosure_parser_typed_ez_double_otherwise_single_nonaromatic/1.0.0"
)
_AROMATIC_CYCLE_PROFILE_ID = (
    "at_most_one_simple_fully_aromatic_5_6_member_b_c_n_o_p_s_source_ring/1.0.0"
)
_AROMATIC_RING_BOND_PROFILE_ID = "all_order_1_5_aromatic_stereo_none/1.0.0"
_AROMATIC_ATOM_STATE_PROFILE_ID = (
    "selected_b_c_n_o_p_s_unit_charge_and_canonical_bracket_hydrogen_"
    "aromatic_atom_tokens/1.0.0"
)
_AROMATIC_FORMAL_CHARGE_PROFILE_ID = (
    "ordered_forest_with_one_simple_fully_aromatic_5_6_member_ring_selected_"
    "unit_charge_and_canonical_bracket_hydrogen_states/1.0.0"
)
_EMISSION_POLICY_ID = (
    "ordered_source_forest_dfs_dot_bond_bounded_charge_selected_aromatic_atom_"
    "ring_label_bounded_tetrahedral_and_ez_direction_tokens/1.8.0"
)
_EZ_STEREO_PROFILE_ID = (
    "source_order_dfs_lowest_index_lexically_oriented_tree_or_selected_simple_"
    "ring_single_bond_direction_carriers/1.0.0"
)
_TETRAHEDRAL_STEREO_PROFILE_ID = (
    "source_order_dfs_parser_typed_tetrahedral_cw_ccw_lexical_parity_with_"
    "zero_or_one_bracket_hydrogen/1.0.0"
)
_PARSER_OPERATIONS = (
    "rdkit_parse_without_sanitization",
    "rdkit_sanitize",
    "manual_bracket_and_implicit_hydrogen_expansion",
    "dependency_free_canonical_graph_revalidation",
)
_COVERAGE_BASE_BLOCKERS = (
    "coordinates_missing",
    "partial_charges_not_assigned",
    "force_field_parameters_not_assigned",
    "protonation_not_independently_assessed",
    "tautomer_not_independently_assessed",
    "hydrogen_expansion_not_independently_valence_verified",
    "rdkit_sanitization_not_independently_revalidated",
    "stereochemistry_completeness_not_assessed",
    "chemistry_applicability_not_established",
)
_SYSTEM_METADATA_KEYS = frozenset(
    {
        "ordered_topology_sha256",
        "source_atom_count",
        "generated_hydrogen_count",
        "fragment_count",
    }
)
_PROVENANCE_METADATA_KEYS = frozenset(
    {
        "rdkit_version",
        "normalized_isomeric_smiles_sha256",
        "ordered_topology_sha256",
        "coverage",
        "canonical_topology_schema_id",
        "canonical_topology_sha256",
        "parser_observation_schema_id",
        "parser_observation_sha256",
    }
)
_SOURCE_ATOM_METADATA_KEYS = frozenset(
    {
        "source_atom_index",
        "source_atom_order_preserved",
        "hydrogen_origin",
        "formal_charge_source",
        "rdkit_chiral_tag",
    }
)
_GENERATED_HYDROGEN_METADATA_KEYS = frozenset(
    {
        "parent_source_atom_index",
        "hydrogen_origin",
        "hydrogen_ordinal",
        "manually_expanded",
        "formal_charge_source",
    }
)
_SOURCE_BOND_METADATA_KEYS = frozenset({"source_bond_index", "stereo_atom_indices"})
_GENERATED_BOND_METADATA_KEYS = frozenset(
    {"parent_source_atom_index", "hydrogen_origin", "hydrogen_ordinal"}
)
_PRESERVATION_SCOPE = (
    "one_to_256_ordered_source_components_with_global_cycle_rank_zero_or_one",
    "at_most_one_simple_nonaromatic_three_through_eight_member_source_ring_with_zero_or_one_nonclosure_double_edge",
    "at_most_one_simple_fully_aromatic_five_or_six_member_b_c_n_o_p_s_source_ring_with_exact_order_one_point_five_bonds",
    "source_atom_order_equal_to_ordered_closure_removed_forest_textual_depth_first_visitation",
    "dot_separator_only_between_graph_derived_component_roots",
    "known_minus_one_zero_or_plus_one_formal_charge_nonisotopic_optionally_mapped_nonaromatic_organic_subset_atoms_with_bounded_parser_typed_tetrahedral_state",
    "at_most_256_parser_typed_tetrahedral_atoms_per_source_graph",
    "at_most_514_source_atoms_when_parser_typed_tetrahedral_calibration_is_required",
    "known_minus_one_zero_or_plus_one_formal_charge_nonisotopic_optionally_mapped_selected_aromatic_or_nonaromatic_organic_subset_atoms",
    "canonical_bare_bracketed_unit_formal_charge_atom_map_selected_aromatic_bracket_hydrogen_and_tetrahedral_atom_tokens",
    "charged_source_atoms_without_implicit_hydrogens",
    "single_double_or_triple_nonaromatic_source_bonds_with_bounded_tree_or_selected_eight_member_ring_parser_typed_e_or_z_double_bonds",
    "single_double_or_triple_nonaromatic_tree_bonds_and_selected_aromatic_ring_bonds_with_stereo_free_ring_state",
    "graph_derived_slash_or_backslash_tokens_on_lowest_index_lexically_oriented_tree_or_selected_simple_ring_single_bond_direction_carriers",
    "canonical_ring_label_one_immediately_after_both_closure_endpoint_atom_tokens",
    "parser_expanded_trailing_implicit_or_selected_aromatic_or_tetrahedral_bracket_hydrogens_with_parent_origin_and_ordinal_markers",
    "parser_typed_tetrahedral_r_s_and_rdkit_cw_ccw_state_with_source_order_lexical_at_or_at_at_parity",
    "parser_synthesized_exact_l1_through_ln_residues_and_chains",
    "topology_only_empty_cpu_float64_coordinate_carrier",
    "normalized_isomeric_smiles_sha256_equal_to_emitted_ascii_line_sha256",
)
_NON_PROMOTION_BLOCKERS = (
    "raw_source_spelling_and_source_identifier_are_not_preserved",
    "full_canonical_snapshot_and_dynamic_source_provenance_equality_not_claimed",
    "sha256_receipts_are_tamper_evidence_not_source_authentication",
    "general_rings_aromaticity_outside_one_selected_simple_five_or_six_member_ring_general_charge_isotopes_nonpositive_or_duplicate_maps_more_than_256_typed_tetrahedral_atoms_atom_stereo_outside_bounded_tetrahedral_r_s_unknown_bond_stereo_and_ez_outside_the_bounded_tree_or_selected_simple_ring_carrier_profile_unsupported",
    "source_graphs_with_parser_typed_tetrahedral_state_and_more_than_514_source_atoms_unsupported",
    "bounded_cycloalkene_serialization_is_not_unsaturation_ring_stereo_ring_strain_conformation_aromaticity_valence_or_chemistry_interpretation",
    "parser_typed_ez_serialization_is_not_independent_cip_assignment_stereo_completeness_or_stereo_geometry_support",
    "parser_typed_tetrahedral_serialization_is_not_independent_cip_assignment_stereo_completeness_substituent_equivalence_or_stereo_geometry_support",
    "general_bracket_explicit_and_source_hydrogens_outside_selected_aromatic_or_tetrahedral_state_unsupported",
    "selected_parser_observed_aromatic_state_serialization_is_not_independent_aromaticity_resonance_kekulization_or_electronic_structure_support",
    "selected_aromatic_bracket_hydrogen_serialization_is_not_protonation_or_tautomer_assignment_support",
    "selected_parser_observed_formal_charge_serialization_is_not_charge_assignment_protonation_tautomer_oxidation_or_electronic_state_support",
    "formal_charge_serialization_is_not_partial_charge_support",
    "selected_bond_order_serialization_is_not_general_multiple_bond_chemistry_support",
    "ordered_fragment_serialization_is_not_salt_mixture_or_context_chemistry_support",
    "fragment_roles_and_salt_or_mixture_chemistry_unassessed",
    "preparation_parameterability_simulation_and_claim_authority_not_granted",
)
_ARTIFACT_FACTORY_TOKEN = object()


class SmilesWriteError(ValueError):
    """Stable fail-closed error for unrepresentable strict SMILES state."""

    def __init__(self, code: str, message: str, *, location: str | None = None):
        self.code = str(code)
        self.location = None if location is None else str(location)
        self.detail = str(message)
        suffix = "" if self.location is None else f" at {self.location}"
        super().__init__(f"smiles_write:{self.code}{suffix}: {self.detail}")


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


def _require_sha256(value: Any, *, field_name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise TypeError(f"{field_name} must be a lowercase SHA-256")
    return value


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    *,
    code: str,
    location: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SmilesWriteError(code, "value must be a mapping", location=location)
    actual = frozenset(value)
    if actual != expected:
        raise SmilesWriteError(
            code,
            "mapping keys do not match parser-owned state; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}",
            location=location,
        )
    return value


def _exact_typed_structure_equal(actual: Any, expected: Any) -> bool:
    """Compare parser state without bool/int or numeric type coercion."""

    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or frozenset(actual) != frozenset(expected):
            return False
        return all(
            _exact_typed_structure_equal(actual[key], expected_value)
            for key, expected_value in expected.items()
        )
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            return False
        return all(
            _exact_typed_structure_equal(left, right)
            for left, right in zip(actual, expected, strict=True)
        )
    if type(actual) is not type(expected):
        return False
    if type(expected) is float:
        return struct.pack(">d", actual) == struct.pack(">d", expected)
    return bool(actual == expected)


@dataclass(frozen=True, slots=True, init=False)
class SmilesWriteReceipt:
    """Hash and resource binding for one deterministic SMILES emission."""

    input_system_schema_id: str
    parent_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_ordered_topology_sha256: str
    input_representable_state_sha256: str
    input_cycle_projection_sha256: str
    input_aromatic_projection_sha256: str = field(repr=False)
    input_ez_stereo_projection_sha256: str = field(repr=False)
    input_tetrahedral_stereo_projection_sha256: str = field(repr=False)
    input_parser_observation_sha256: str
    normalized_isomeric_smiles_sha256: str
    rdkit_version: str
    output_source_sha256: str
    output_byte_count: int
    source_atom_count: int
    expanded_atom_count: int
    atom_count: int
    bond_count: int
    fragment_count: int
    generated_hydrogen_count: int
    implicit_hydrogen_count: int
    bracket_explicit_hydrogen_count: int
    mapped_source_atom_count: int
    typed_tetrahedral_atom_count: int
    source_bond_count: int
    source_tree_edge_count: int
    ring_closure_count: int
    cyclic_component_count: int
    ring_size: int
    ring_closure_source_bond_index: int | None
    ring_bond_profile_id: str | None
    ring_double_bond_count: int
    ring_double_source_bond_index: int | None
    aromatic_source_atom_count: int
    aromatic_source_bond_count: int
    typed_ez_bond_count: int
    directional_source_bond_count: int
    cycle_projection_schema_id: str
    cycle_profile_id: str
    aromatic_projection_schema_id: str = field(repr=False)
    aromatic_ring_profile_id: str | None = field(repr=False)
    aromatic_atom_state_profile_id: str | None = field(repr=False)
    ez_stereo_projection_schema_id: str = field(repr=False)
    ez_stereo_profile_id: str = field(repr=False)
    tetrahedral_stereo_projection_schema_id: str = field(repr=False)
    tetrahedral_stereo_profile_id: str = field(repr=False)
    formal_charge_profile_id: str
    charged_source_atom_count: int
    formal_charge_total: int

    def __init__(
        self,
        *,
        input_system_schema_id: str,
        parent_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_ordered_topology_sha256: str,
        input_representable_state_sha256: str,
        input_cycle_projection_sha256: str,
        input_aromatic_projection_sha256: str,
        input_ez_stereo_projection_sha256: str,
        input_tetrahedral_stereo_projection_sha256: str,
        input_parser_observation_sha256: str,
        normalized_isomeric_smiles_sha256: str,
        rdkit_version: str,
        output_source_sha256: str,
        output_byte_count: int,
        source_atom_count: int,
        expanded_atom_count: int,
        atom_count: int,
        bond_count: int,
        fragment_count: int,
        generated_hydrogen_count: int,
        implicit_hydrogen_count: int,
        bracket_explicit_hydrogen_count: int,
        mapped_source_atom_count: int,
        typed_tetrahedral_atom_count: int,
        source_bond_count: int,
        source_tree_edge_count: int,
        ring_closure_count: int,
        cyclic_component_count: int,
        ring_size: int,
        ring_closure_source_bond_index: int | None,
        ring_bond_profile_id: str | None,
        ring_double_bond_count: int,
        ring_double_source_bond_index: int | None,
        aromatic_source_atom_count: int,
        aromatic_source_bond_count: int,
        typed_ez_bond_count: int,
        directional_source_bond_count: int,
        cycle_projection_schema_id: str,
        cycle_profile_id: str,
        aromatic_projection_schema_id: str,
        aromatic_ring_profile_id: str | None,
        aromatic_atom_state_profile_id: str | None,
        ez_stereo_projection_schema_id: str,
        ez_stereo_profile_id: str,
        tetrahedral_stereo_projection_schema_id: str,
        tetrahedral_stereo_profile_id: str,
        formal_charge_profile_id: str,
        charged_source_atom_count: int,
        formal_charge_total: int,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SmilesWriteReceipt is factory-only")
        values = locals()
        for field_name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            object.__setattr__(self, field_name, values[field_name])
        self.__post_init__()

    def __post_init__(self) -> None:
        if self.input_system_schema_id != ALL_ATOM_SCHEMA_ID:
            raise ValueError("write receipt must bind the current all-atom schema")
        for field_name in (
            "parent_source_sha256",
            "input_snapshot_sha256",
            "input_topology_sha256",
            "input_ordered_topology_sha256",
            "input_representable_state_sha256",
            "input_cycle_projection_sha256",
            "input_aromatic_projection_sha256",
            "input_ez_stereo_projection_sha256",
            "input_tetrahedral_stereo_projection_sha256",
            "input_parser_observation_sha256",
            "normalized_isomeric_smiles_sha256",
            "output_source_sha256",
        ):
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if type(self.rdkit_version) is not str or not self.rdkit_version:
            raise TypeError("rdkit_version must be a nonempty string")
        for field_name in (
            "output_byte_count",
            "source_atom_count",
            "expanded_atom_count",
            "atom_count",
            "bond_count",
            "fragment_count",
            "generated_hydrogen_count",
            "implicit_hydrogen_count",
            "bracket_explicit_hydrogen_count",
            "mapped_source_atom_count",
            "typed_tetrahedral_atom_count",
            "source_bond_count",
            "source_tree_edge_count",
            "ring_closure_count",
            "cyclic_component_count",
            "ring_size",
            "ring_double_bond_count",
            "aromatic_source_atom_count",
            "aromatic_source_bond_count",
            "typed_ez_bond_count",
            "directional_source_bond_count",
            "charged_source_atom_count",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value < 0:
                raise TypeError(f"{field_name} must be a nonnegative integer")
        if not 1 <= self.output_byte_count <= _MAX_OUTPUT_BYTES:
            raise ValueError("output_byte_count is outside the SMILES writer limit")
        if not 1 <= self.source_atom_count <= _MAX_SOURCE_ATOMS:
            raise ValueError("source_atom_count is outside the parser limit")
        if (
            not self.source_atom_count
            <= self.expanded_atom_count
            <= _MAX_EXPANDED_ATOMS
        ):
            raise ValueError("expanded_atom_count is outside the parser limit")
        if self.atom_count != self.expanded_atom_count:
            raise ValueError("atom_count must equal expanded_atom_count")
        if not 1 <= self.fragment_count <= min(_MAX_FRAGMENTS, self.source_atom_count):
            raise ValueError("fragment_count is outside the SMILES writer limit")
        if self.ring_closure_count not in (0, 1):
            raise ValueError("ring_closure_count must be zero or one")
        if self.cyclic_component_count != self.ring_closure_count:
            raise ValueError("cyclic_component_count must equal ring_closure_count")
        if self.source_tree_edge_count != self.source_atom_count - self.fragment_count:
            raise ValueError("source_tree_edge_count is inconsistent")
        if (
            self.source_bond_count
            != self.source_tree_edge_count + self.ring_closure_count
        ):
            raise ValueError("source_bond_count is inconsistent")
        if (
            self.bond_count > _MAX_BONDS
            or self.bond_count
            != self.expanded_atom_count - self.fragment_count + self.ring_closure_count
        ):
            raise ValueError("bond_count is inconsistent with the supported graph")
        if (
            self.generated_hydrogen_count
            != self.expanded_atom_count - self.source_atom_count
        ):
            raise ValueError("generated_hydrogen_count is inconsistent")
        if (
            self.implicit_hydrogen_count + self.bracket_explicit_hydrogen_count
            != self.generated_hydrogen_count
        ):
            raise ValueError("generated hydrogen origin counts are inconsistent")
        if self.bracket_explicit_hydrogen_count > (
            self.aromatic_source_atom_count + self.typed_tetrahedral_atom_count
        ):
            raise ValueError(
                "bracket-explicit hydrogen count exceeds selected source atoms"
            )
        if type(self.cycle_projection_schema_id) is not str:
            raise TypeError("cycle_projection_schema_id must be an exact string")
        if (
            self.cycle_projection_schema_id
            != SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID
        ):
            raise ValueError(
                "cycle_projection_schema_id is outside the writer contract"
            )
        if type(self.cycle_profile_id) is not str:
            raise TypeError("cycle_profile_id must be an exact string")
        if self.cycle_profile_id not in {
            _ALL_SINGLE_CYCLE_PROFILE_ID,
            _ONE_DOUBLE_CYCLE_PROFILE_ID,
            _ONE_DOUBLE_EZ_CYCLE_PROFILE_ID,
            _AROMATIC_CYCLE_PROFILE_ID,
        }:
            raise ValueError("cycle_profile_id is outside the writer contract")
        if type(self.aromatic_projection_schema_id) is not str:
            raise TypeError("aromatic_projection_schema_id must be an exact string")
        if (
            self.aromatic_projection_schema_id
            != SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID
        ):
            raise ValueError(
                "aromatic_projection_schema_id is outside the writer contract"
            )
        if type(self.ez_stereo_projection_schema_id) is not str:
            raise TypeError("ez_stereo_projection_schema_id must be an exact string")
        if self.ez_stereo_projection_schema_id != SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID:
            raise ValueError(
                "ez_stereo_projection_schema_id is outside the writer contract"
            )
        if type(self.ez_stereo_profile_id) is not str:
            raise TypeError("ez_stereo_profile_id must be an exact string")
        if self.ez_stereo_profile_id != _EZ_STEREO_PROFILE_ID:
            raise ValueError("ez_stereo_profile_id is outside the writer contract")
        if (
            self.tetrahedral_stereo_projection_schema_id
            != SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
        ):
            raise ValueError(
                "tetrahedral_stereo_projection_schema_id is outside the writer contract"
            )
        if self.tetrahedral_stereo_profile_id != _TETRAHEDRAL_STEREO_PROFILE_ID:
            raise ValueError(
                "tetrahedral_stereo_profile_id is outside the writer contract"
            )
        if self.mapped_source_atom_count > self.source_atom_count:
            raise ValueError("mapped_source_atom_count exceeds source_atom_count")
        if self.typed_tetrahedral_atom_count > _MAX_TYPED_TETRAHEDRAL_ATOMS:
            raise ValueError("typed_tetrahedral_atom_count exceeds the writer limit")
        if (
            self.typed_tetrahedral_atom_count
            and self.source_atom_count > _MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS
        ):
            raise ValueError(
                "tetrahedral calibration source_atom_count exceeds the writer limit"
            )
        if self.typed_ez_bond_count > _MAX_TYPED_EZ_BONDS:
            raise ValueError("typed_ez_bond_count exceeds the writer limit")
        if self.typed_ez_bond_count == 0:
            if self.directional_source_bond_count != 0:
                raise ValueError(
                    "stereo-free receipt must not contain direction carriers"
                )
        elif not (
            self.typed_ez_bond_count + 1
            <= self.directional_source_bond_count
            <= 2 * self.typed_ez_bond_count
        ):
            raise ValueError(
                "directional source-bond count is inconsistent with E/Z state"
            )
        for field_name in (
            "aromatic_ring_profile_id",
            "aromatic_atom_state_profile_id",
        ):
            value = getattr(self, field_name)
            if value is not None and type(value) is not str:
                raise TypeError(f"{field_name} must be an exact string or None")
        if (
            self.ring_bond_profile_id is not None
            and type(self.ring_bond_profile_id) is not str
        ):
            raise TypeError("ring_bond_profile_id must be an exact string or None")
        if (
            self.ring_double_source_bond_index is not None
            and type(self.ring_double_source_bond_index) is not int
        ):
            raise TypeError(
                "ring_double_source_bond_index must be an exact integer or None"
            )
        if self.ring_closure_count == 0:
            if (
                self.ring_size != 0
                or self.ring_closure_source_bond_index is not None
                or self.ring_bond_profile_id is not None
                or self.ring_double_bond_count != 0
                or self.ring_double_source_bond_index is not None
                or self.cycle_profile_id != _ALL_SINGLE_CYCLE_PROFILE_ID
                or self.aromatic_source_atom_count != 0
                or self.aromatic_source_bond_count != 0
                or self.aromatic_ring_profile_id is not None
                or self.aromatic_atom_state_profile_id is not None
            ):
                raise ValueError("acyclic receipt must have empty ring fields")
            expected_formal_charge_profile_id = _FORMAL_CHARGE_PROFILE_ID
        else:
            if not _MIN_RING_SIZE <= self.ring_size <= _MAX_RING_SIZE:
                raise ValueError("ring_size is outside the writer contract")
            if (
                type(self.ring_closure_source_bond_index) is not int
                or self.ring_closure_source_bond_index != self.source_bond_count - 1
            ):
                raise ValueError("ring closure must be the final source bond")
            if self.cycle_profile_id == _AROMATIC_CYCLE_PROFILE_ID:
                if (
                    not _MIN_AROMATIC_RING_SIZE
                    <= self.ring_size
                    <= _MAX_AROMATIC_RING_SIZE
                    or self.ring_bond_profile_id != _AROMATIC_RING_BOND_PROFILE_ID
                    or self.ring_double_bond_count != 0
                    or self.ring_double_source_bond_index is not None
                    or self.aromatic_source_atom_count != self.ring_size
                    or self.aromatic_source_bond_count != self.ring_size
                    or self.aromatic_ring_profile_id != _AROMATIC_CYCLE_PROFILE_ID
                    or self.aromatic_atom_state_profile_id
                    != _AROMATIC_ATOM_STATE_PROFILE_ID
                ):
                    raise ValueError("aromatic ring receipt fields are inconsistent")
                expected_formal_charge_profile_id = _AROMATIC_FORMAL_CHARGE_PROFILE_ID
            elif self.ring_double_bond_count == 0:
                if (
                    self.ring_double_source_bond_index is not None
                    or self.ring_bond_profile_id != _ALL_SINGLE_RING_BOND_PROFILE_ID
                    or self.cycle_profile_id != _ALL_SINGLE_CYCLE_PROFILE_ID
                    or self.aromatic_source_atom_count != 0
                    or self.aromatic_source_bond_count != 0
                    or self.aromatic_ring_profile_id is not None
                    or self.aromatic_atom_state_profile_id is not None
                ):
                    raise ValueError("all-single ring receipt fields are inconsistent")
                expected_formal_charge_profile_id = _RING_FORMAL_CHARGE_PROFILE_ID
            elif self.ring_double_bond_count == 1:
                ring_profile_pair = (
                    self.ring_bond_profile_id,
                    self.cycle_profile_id,
                )
                valid_ring_profile_pairs = {
                    (
                        _ONE_DOUBLE_RING_BOND_PROFILE_ID,
                        _ONE_DOUBLE_CYCLE_PROFILE_ID,
                    ),
                    (
                        _ONE_DOUBLE_EZ_RING_BOND_PROFILE_ID,
                        _ONE_DOUBLE_EZ_CYCLE_PROFILE_ID,
                    ),
                }
                if (
                    type(self.ring_double_source_bond_index) is not int
                    or not 0
                    <= self.ring_double_source_bond_index
                    < self.ring_closure_source_bond_index
                    or ring_profile_pair not in valid_ring_profile_pairs
                    or (
                        self.cycle_profile_id == _ONE_DOUBLE_EZ_CYCLE_PROFILE_ID
                        and (self.ring_size != 8 or self.typed_ez_bond_count < 1)
                    )
                    or self.aromatic_source_atom_count != 0
                    or self.aromatic_source_bond_count != 0
                    or self.aromatic_ring_profile_id is not None
                    or self.aromatic_atom_state_profile_id is not None
                ):
                    raise ValueError("one-double ring receipt fields are inconsistent")
                expected_formal_charge_profile_id = _RING_FORMAL_CHARGE_PROFILE_ID
            else:
                raise ValueError("ring_double_bond_count must be zero or one")
        if type(self.formal_charge_profile_id) is not str:
            raise TypeError("formal_charge_profile_id must be an exact string")
        if self.formal_charge_profile_id != expected_formal_charge_profile_id:
            raise ValueError("formal_charge_profile_id is outside the writer contract")
        if type(self.formal_charge_total) is not int:
            raise TypeError("formal_charge_total must be an exact integer")
        if self.charged_source_atom_count > self.source_atom_count:
            raise ValueError("charged_source_atom_count exceeds source_atom_count")
        if abs(self.formal_charge_total) > self.charged_source_atom_count:
            raise ValueError("formal_charge_total exceeds the unit-charge inventory")
        if (self.charged_source_atom_count - abs(self.formal_charge_total)) % 2:
            raise ValueError(
                "formal_charge_total parity is inconsistent with unit charges"
            )
        if self.output_source_sha256 != self.normalized_isomeric_smiles_sha256:
            raise ValueError(
                "emitted source must equal the attached normalized identity"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SMILES_WRITE_RECEIPT_SCHEMA_ID,
            "writer_version": SMILES_WRITER_VERSION,
            "parser_version": SMILES_PARSER_VERSION,
            "input_system_schema_id": self.input_system_schema_id,
            "parent_source_sha256": self.parent_source_sha256,
            "input_snapshot_sha256": self.input_snapshot_sha256,
            "input_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
            "input_topology_sha256": self.input_topology_sha256,
            "input_ordered_topology_sha256": self.input_ordered_topology_sha256,
            "representable_state_schema_id": SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
            "input_representable_state_sha256": self.input_representable_state_sha256,
            "cycle_projection_schema_id": self.cycle_projection_schema_id,
            "cycle_profile_id": self.cycle_profile_id,
            "input_cycle_projection_sha256": self.input_cycle_projection_sha256,
            "aromatic_projection_schema_id": self.aromatic_projection_schema_id,
            "aromatic_ring_profile_id": self.aromatic_ring_profile_id,
            "aromatic_atom_state_profile_id": self.aromatic_atom_state_profile_id,
            "input_aromatic_projection_sha256": (self.input_aromatic_projection_sha256),
            "ez_stereo_projection_schema_id": self.ez_stereo_projection_schema_id,
            "ez_stereo_profile_id": self.ez_stereo_profile_id,
            "input_ez_stereo_projection_sha256": (
                self.input_ez_stereo_projection_sha256
            ),
            "tetrahedral_stereo_projection_schema_id": (
                self.tetrahedral_stereo_projection_schema_id
            ),
            "tetrahedral_stereo_profile_id": self.tetrahedral_stereo_profile_id,
            "input_tetrahedral_stereo_projection_sha256": (
                self.input_tetrahedral_stereo_projection_sha256
            ),
            "parser_observation_schema_id": PARSER_OBSERVATION_SCHEMA_ID,
            "input_parser_observation_sha256": self.input_parser_observation_sha256,
            "normalized_isomeric_smiles_sha256": self.normalized_isomeric_smiles_sha256,
            "rdkit_version": self.rdkit_version,
            "output_source_sha256": self.output_source_sha256,
            "output_byte_count": self.output_byte_count,
            "source_atom_count": self.source_atom_count,
            "expanded_atom_count": self.expanded_atom_count,
            "atom_count": self.atom_count,
            "bond_count": self.bond_count,
            "fragment_count": self.fragment_count,
            "generated_hydrogen_count": self.generated_hydrogen_count,
            "implicit_hydrogen_count": self.implicit_hydrogen_count,
            "bracket_explicit_hydrogen_count": (self.bracket_explicit_hydrogen_count),
            "mapped_source_atom_count": self.mapped_source_atom_count,
            "typed_tetrahedral_atom_count": self.typed_tetrahedral_atom_count,
            "source_bond_count": self.source_bond_count,
            "source_tree_edge_count": self.source_tree_edge_count,
            "ring_closure_count": self.ring_closure_count,
            "cyclic_component_count": self.cyclic_component_count,
            "ring_size": self.ring_size,
            "ring_closure_source_bond_index": self.ring_closure_source_bond_index,
            "ring_bond_profile_id": self.ring_bond_profile_id,
            "ring_double_bond_count": self.ring_double_bond_count,
            "ring_double_source_bond_index": self.ring_double_source_bond_index,
            "aromatic_source_atom_count": self.aromatic_source_atom_count,
            "aromatic_source_bond_count": self.aromatic_source_bond_count,
            "typed_ez_bond_count": self.typed_ez_bond_count,
            "directional_source_bond_count": self.directional_source_bond_count,
            "formal_charge_profile_id": self.formal_charge_profile_id,
            "charged_source_atom_count": self.charged_source_atom_count,
            "formal_charge_total": self.formal_charge_total,
            "resource_limits": {
                "output_bytes": _MAX_OUTPUT_BYTES,
                "source_atoms": _MAX_SOURCE_ATOMS,
                "expanded_atoms": _MAX_EXPANDED_ATOMS,
                "bonds": _MAX_BONDS,
                "fragments": _MAX_FRAGMENTS,
                "ring_components": _MAX_RING_COMPONENTS,
                "ring_size_min": _MIN_RING_SIZE,
                "ring_size_max": _MAX_RING_SIZE,
                "aromatic_ring_size_min": _MIN_AROMATIC_RING_SIZE,
                "aromatic_ring_size_max": _MAX_AROMATIC_RING_SIZE,
                "typed_ez_bonds": _MAX_TYPED_EZ_BONDS,
                "typed_tetrahedral_atoms": _MAX_TYPED_TETRAHEDRAL_ATOMS,
                "tetrahedral_calibration_source_atoms": (
                    _MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS
                ),
            },
            "preservation_scope": list(_PRESERVATION_SCOPE),
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class SmilesWriteResult:
    payload: bytes = field(repr=False)
    receipt: SmilesWriteReceipt
    _input_snapshot: bytes = field(repr=False)

    def __init__(
        self,
        *,
        payload: bytes,
        receipt: SmilesWriteReceipt,
        input_system: AllAtomSystem | None = None,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SmilesWriteResult is factory-only")
        if input_system is None:
            raise ValueError(
                "regenerated SMILES bindings require the live input system"
            )
        if type(input_system) is not AllAtomSystem:
            raise TypeError("input_system must be an exact AllAtomSystem")
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "receipt", receipt)
        object.__setattr__(
            self,
            "_input_snapshot",
            serialize_all_atom_system(input_system),
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        if type(self.payload) is not bytes:
            raise TypeError("SMILES write payload must be exact bytes")
        if type(self.receipt) is not SmilesWriteReceipt:
            raise TypeError("receipt must be a SmilesWriteReceipt")
        if type(self._input_snapshot) is not bytes:
            raise TypeError("input snapshot must be exact bytes")
        if len(self.payload) != self.receipt.output_byte_count:
            raise ValueError("write payload length does not match receipt")
        if (
            hashlib.sha256(self.payload).hexdigest()
            != self.receipt.output_source_sha256
        ):
            raise ValueError("write payload SHA-256 does not match receipt")
        try:
            input_system = deserialize_all_atom_system(self._input_snapshot)
            input_state = _validate_write_state(input_system)
            input_payload = _emit_payload(input_state)
            state = _validated_payload_image(self.payload)
        except (TypeError, ValueError, OverflowError, RuntimeError) as exc:
            raise ValueError(
                "write payload is outside the strict SMILES writer image"
            ) from exc
        input_observation_sha256 = input_system.provenance.metadata.get(
            "parser_observation_sha256"
        )
        expected_pairs = (
            (
                input_system.schema_id,
                self.receipt.input_system_schema_id,
            ),
            (
                input_system.provenance.source_sha256,
                self.receipt.parent_source_sha256,
            ),
            (
                canonical_all_atom_snapshot_digest(input_system),
                self.receipt.input_snapshot_sha256,
            ),
            (
                input_state.canonical_topology_sha256,
                self.receipt.input_topology_sha256,
            ),
            (
                input_state.ordered_topology_sha256,
                self.receipt.input_ordered_topology_sha256,
            ),
            (
                _sha256_document(input_state.representable_state_document),
                self.receipt.input_representable_state_sha256,
            ),
            (
                input_state.cycle_projection_sha256,
                self.receipt.input_cycle_projection_sha256,
            ),
            (
                input_state.aromatic_projection_sha256,
                self.receipt.input_aromatic_projection_sha256,
            ),
            (
                input_state.ez_stereo_projection_sha256,
                self.receipt.input_ez_stereo_projection_sha256,
            ),
            (
                input_state.tetrahedral_stereo_projection_sha256,
                self.receipt.input_tetrahedral_stereo_projection_sha256,
            ),
            (
                input_observation_sha256,
                self.receipt.input_parser_observation_sha256,
            ),
            (
                canonical_topology_sha256(state.system),
                self.receipt.input_topology_sha256,
            ),
            (state.ordered_topology_sha256, self.receipt.input_ordered_topology_sha256),
            (
                _sha256_document(state.representable_state_document),
                self.receipt.input_representable_state_sha256,
            ),
            (
                state.cycle_projection_sha256,
                self.receipt.input_cycle_projection_sha256,
            ),
            (
                state.aromatic_projection_sha256,
                self.receipt.input_aromatic_projection_sha256,
            ),
            (
                state.ez_stereo_projection_sha256,
                self.receipt.input_ez_stereo_projection_sha256,
            ),
            (
                state.tetrahedral_stereo_projection_sha256,
                self.receipt.input_tetrahedral_stereo_projection_sha256,
            ),
            (
                state.normalized_isomeric_smiles_sha256,
                self.receipt.normalized_isomeric_smiles_sha256,
            ),
            (state.rdkit_version, self.receipt.rdkit_version),
            (state.source_atom_count, self.receipt.source_atom_count),
            (state.system.atom_count, self.receipt.expanded_atom_count),
            (state.system.atom_count, self.receipt.atom_count),
            (len(state.system.bonds), self.receipt.bond_count),
            (state.fragment_count, self.receipt.fragment_count),
            (state.generated_hydrogen_count, self.receipt.generated_hydrogen_count),
            (state.implicit_hydrogen_count, self.receipt.implicit_hydrogen_count),
            (
                state.bracket_explicit_hydrogen_count,
                self.receipt.bracket_explicit_hydrogen_count,
            ),
            (
                state.mapped_source_atom_count,
                self.receipt.mapped_source_atom_count,
            ),
            (
                state.typed_tetrahedral_atom_count,
                self.receipt.typed_tetrahedral_atom_count,
            ),
            (state.source_bond_count, self.receipt.source_bond_count),
            (state.source_tree_edge_count, self.receipt.source_tree_edge_count),
            (state.ring_closure_count, self.receipt.ring_closure_count),
            (state.cyclic_component_count, self.receipt.cyclic_component_count),
            (state.ring_size, self.receipt.ring_size),
            (
                state.ring_closure_source_bond_index,
                self.receipt.ring_closure_source_bond_index,
            ),
            (state.ring_bond_profile_id, self.receipt.ring_bond_profile_id),
            (state.ring_double_bond_count, self.receipt.ring_double_bond_count),
            (
                state.ring_double_source_bond_index,
                self.receipt.ring_double_source_bond_index,
            ),
            (
                state.aromatic_source_atom_count,
                self.receipt.aromatic_source_atom_count,
            ),
            (
                state.aromatic_source_bond_count,
                self.receipt.aromatic_source_bond_count,
            ),
            (state.typed_ez_bond_count, self.receipt.typed_ez_bond_count),
            (
                state.directional_source_bond_count,
                self.receipt.directional_source_bond_count,
            ),
            (
                SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID,
                self.receipt.cycle_projection_schema_id,
            ),
            (state.cycle_profile_id, self.receipt.cycle_profile_id),
            (
                SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID,
                self.receipt.aromatic_projection_schema_id,
            ),
            (
                state.aromatic_ring_profile_id,
                self.receipt.aromatic_ring_profile_id,
            ),
            (
                state.aromatic_atom_state_profile_id,
                self.receipt.aromatic_atom_state_profile_id,
            ),
            (
                SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
                self.receipt.ez_stereo_projection_schema_id,
            ),
            (state.ez_stereo_profile_id, self.receipt.ez_stereo_profile_id),
            (
                SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID,
                self.receipt.tetrahedral_stereo_projection_schema_id,
            ),
            (
                state.tetrahedral_stereo_profile_id,
                self.receipt.tetrahedral_stereo_profile_id,
            ),
            (state.formal_charge_profile_id, self.receipt.formal_charge_profile_id),
            (state.charged_source_atom_count, self.receipt.charged_source_atom_count),
            (state.formal_charge_total, self.receipt.formal_charge_total),
            (input_state.fragment_count, state.fragment_count),
            (
                input_state.formal_charge_profile_id,
                state.formal_charge_profile_id,
            ),
            (
                input_state.charged_source_atom_count,
                state.charged_source_atom_count,
            ),
            (input_state.formal_charge_total, state.formal_charge_total),
            (
                input_state.implicit_hydrogen_count,
                state.implicit_hydrogen_count,
            ),
            (
                input_state.bracket_explicit_hydrogen_count,
                state.bracket_explicit_hydrogen_count,
            ),
            (
                input_state.mapped_source_atom_count,
                state.mapped_source_atom_count,
            ),
            (
                input_state.typed_tetrahedral_atom_count,
                state.typed_tetrahedral_atom_count,
            ),
            (input_state.source_bond_count, state.source_bond_count),
            (input_state.source_tree_edge_count, state.source_tree_edge_count),
            (
                input_state.component_cyclomatic_numbers,
                state.component_cyclomatic_numbers,
            ),
            (input_state.ring_closure_count, state.ring_closure_count),
            (input_state.cyclic_component_count, state.cyclic_component_count),
            (input_state.cyclic_component_index, state.cyclic_component_index),
            (input_state.ring_size, state.ring_size),
            (input_state.ring_atom_indices, state.ring_atom_indices),
            (input_state.ring_bond_indices, state.ring_bond_indices),
            (
                input_state.ring_closure_source_bond_index,
                state.ring_closure_source_bond_index,
            ),
            (input_state.ring_closure_endpoints, state.ring_closure_endpoints),
            (
                input_state.ring_open_source_atom_index,
                state.ring_open_source_atom_index,
            ),
            (
                input_state.ring_close_source_atom_index,
                state.ring_close_source_atom_index,
            ),
            (input_state.cycle_profile_id, state.cycle_profile_id),
            (input_state.ring_bond_profile_id, state.ring_bond_profile_id),
            (input_state.ring_double_bond_count, state.ring_double_bond_count),
            (
                input_state.ring_double_source_bond_index,
                state.ring_double_source_bond_index,
            ),
            (
                input_state.aromatic_source_atom_count,
                state.aromatic_source_atom_count,
            ),
            (
                input_state.aromatic_source_bond_count,
                state.aromatic_source_bond_count,
            ),
            (
                input_state.aromatic_ring_profile_id,
                state.aromatic_ring_profile_id,
            ),
            (
                input_state.aromatic_atom_state_profile_id,
                state.aromatic_atom_state_profile_id,
            ),
            (input_state.typed_ez_bond_count, state.typed_ez_bond_count),
            (
                input_state.directional_source_bond_count,
                state.directional_source_bond_count,
            ),
            (input_state.ez_stereo_profile_id, state.ez_stereo_profile_id),
            (input_state.ring_bond_order_table, state.ring_bond_order_table),
            (
                input_state.cycle_projection_sha256,
                state.cycle_projection_sha256,
            ),
            (
                input_state.aromatic_projection_sha256,
                state.aromatic_projection_sha256,
            ),
            (
                input_state.ez_stereo_projection_sha256,
                state.ez_stereo_projection_sha256,
            ),
            (
                input_state.tetrahedral_stereo_projection_sha256,
                state.tetrahedral_stereo_projection_sha256,
            ),
            (input_state.source_atom_tokens, state.source_atom_tokens),
            (input_state.source_component_roots, state.source_component_roots),
            (input_state.source_components, state.source_components),
            (input_state.expanded_components, state.expanded_components),
            (input_state.source_children, state.source_children),
            (
                input_state.source_parent_bond_tokens,
                state.source_parent_bond_tokens,
            ),
            (
                input_state.source_ring_marker_table,
                state.source_ring_marker_table,
            ),
            (input_payload, self.payload),
        )
        if any(
            type(left) is not type(right) or left != right
            for left, right in expected_pairs
        ):
            raise ValueError("regenerated SMILES bindings do not match receipt")


@dataclass(frozen=True, slots=True, init=False)
class SmilesRoundTripReport:
    """Evidence for the declared source-independent SMILES projection."""

    input_source_sha256: str
    input_snapshot_sha256: str
    input_topology_sha256: str
    input_ordered_topology_sha256: str
    input_representable_state_sha256: str
    input_cycle_projection_sha256: str
    input_aromatic_projection_sha256: str
    input_ez_stereo_projection_sha256: str
    input_tetrahedral_stereo_projection_sha256: str
    input_parser_observation_sha256: str
    writer_receipt_sha256: str
    emitted_source_sha256: str
    reparsed_snapshot_sha256: str
    reparsed_topology_sha256: str
    reparsed_ordered_topology_sha256: str
    reparsed_representable_state_sha256: str
    reparsed_cycle_projection_sha256: str
    reparsed_aromatic_projection_sha256: str
    reparsed_ez_stereo_projection_sha256: str
    reparsed_tetrahedral_stereo_projection_sha256: str
    reparsed_parser_observation_sha256: str
    reemitted_source_sha256: str

    def __init__(
        self,
        *,
        input_source_sha256: str,
        input_snapshot_sha256: str,
        input_topology_sha256: str,
        input_ordered_topology_sha256: str,
        input_representable_state_sha256: str,
        input_cycle_projection_sha256: str,
        input_aromatic_projection_sha256: str,
        input_ez_stereo_projection_sha256: str,
        input_tetrahedral_stereo_projection_sha256: str,
        input_parser_observation_sha256: str,
        writer_receipt_sha256: str,
        emitted_source_sha256: str,
        reparsed_snapshot_sha256: str,
        reparsed_topology_sha256: str,
        reparsed_ordered_topology_sha256: str,
        reparsed_representable_state_sha256: str,
        reparsed_cycle_projection_sha256: str,
        reparsed_aromatic_projection_sha256: str,
        reparsed_ez_stereo_projection_sha256: str,
        reparsed_tetrahedral_stereo_projection_sha256: str,
        reparsed_parser_observation_sha256: str,
        reemitted_source_sha256: str,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SmilesRoundTripReport is factory-only")
        values = locals()
        for field_name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            object.__setattr__(self, field_name, values[field_name])
        self.__post_init__()

    def __post_init__(self) -> None:
        for field_name in self.__dataclass_fields__:  # type: ignore[attr-defined]
            _require_sha256(getattr(self, field_name), field_name=field_name)
        if self.input_topology_sha256 != self.reparsed_topology_sha256:
            raise ValueError("round-trip topology hashes must match")
        if self.input_ordered_topology_sha256 != self.reparsed_ordered_topology_sha256:
            raise ValueError("round-trip ordered topology hashes must match")
        if (
            self.input_representable_state_sha256
            != self.reparsed_representable_state_sha256
        ):
            raise ValueError("round-trip representable-state hashes must match")
        if self.input_cycle_projection_sha256 != self.reparsed_cycle_projection_sha256:
            raise ValueError("round-trip cycle-projection hashes must match")
        if (
            self.input_aromatic_projection_sha256
            != self.reparsed_aromatic_projection_sha256
        ):
            raise ValueError("round-trip aromatic-projection hashes must match")
        if (
            self.input_ez_stereo_projection_sha256
            != self.reparsed_ez_stereo_projection_sha256
        ):
            raise ValueError("round-trip E/Z stereo-projection hashes must match")
        if (
            self.input_tetrahedral_stereo_projection_sha256
            != self.reparsed_tetrahedral_stereo_projection_sha256
        ):
            raise ValueError(
                "round-trip tetrahedral stereo-projection hashes must match"
            )
        if self.emitted_source_sha256 != self.reemitted_source_sha256:
            raise ValueError("round-trip emitted bytes must be stable")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": SMILES_ROUND_TRIP_REPORT_SCHEMA_ID,
            "writer_version": SMILES_WRITER_VERSION,
            "parser_version": SMILES_PARSER_VERSION,
            "representable_state_schema_id": SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
            "cycle_projection_schema_id": (SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID),
            "aromatic_projection_schema_id": (
                SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID
            ),
            "ez_stereo_projection_schema_id": (SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID),
            "tetrahedral_stereo_projection_schema_id": (
                SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
            ),
            **{name: getattr(self, name) for name in self.__dataclass_fields__},  # type: ignore[attr-defined]
            "declared_projection_sha256_equal": True,
            "cycle_projection_sha256_equal": True,
            "aromatic_projection_sha256_equal": True,
            "ez_stereo_projection_sha256_equal": True,
            "tetrahedral_stereo_projection_sha256_equal": True,
            "canonical_topology_sha256_equal": True,
            "ordered_topology_sha256_equal": True,
            "declared_parser_marker_projection_equal": True,
            "emitted_source_sha256_and_bytes_stable": True,
            "full_canonical_snapshot_equality_claimed": False,
            "dynamic_source_provenance_equality_claimed": False,
            "source_authentication_status": "not_authenticated",
            "preparation_ready": False,
            "parameterability_assessed": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(_NON_PROMOTION_BLOCKERS),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = self._core_dict()
        payload["report_sha256"] = self.report_sha256
        return payload


@dataclass(frozen=True, slots=True, init=False)
class SmilesRoundTripResult:
    """Snapshot-backed aggregate for one verified SMILES source round trip."""

    _source_snapshot: bytes = field(repr=False)
    _source_coverage: SmilesIngestCoverage = field(repr=False)
    _write_result: SmilesWriteResult = field(repr=False)
    _reparsed_snapshot: bytes = field(repr=False)
    _reparsed_coverage: SmilesIngestCoverage = field(repr=False)
    _report: SmilesRoundTripReport

    def __init__(
        self,
        *,
        source_ingest: SmilesIngestResult,
        write_result: SmilesWriteResult,
        reparsed_ingest: SmilesIngestResult,
        report: SmilesRoundTripReport,
        _factory_token: object | None = None,
    ) -> None:
        if _factory_token is not _ARTIFACT_FACTORY_TOKEN:
            raise TypeError("SmilesRoundTripResult is factory-only")
        if type(source_ingest) is not SmilesIngestResult:
            raise TypeError("source_ingest must be a SmilesIngestResult")
        if type(source_ingest.coverage) is not SmilesIngestCoverage:
            raise TypeError("source_ingest.coverage must be a SmilesIngestCoverage")
        if type(write_result) is not SmilesWriteResult:
            raise TypeError("write_result must be a SmilesWriteResult")
        if type(reparsed_ingest) is not SmilesIngestResult:
            raise TypeError("reparsed_ingest must be a SmilesIngestResult")
        if type(reparsed_ingest.coverage) is not SmilesIngestCoverage:
            raise TypeError("reparsed_ingest.coverage must be a SmilesIngestCoverage")
        if type(report) is not SmilesRoundTripReport:
            raise TypeError("report must be a SmilesRoundTripReport")
        object.__setattr__(
            self, "_source_snapshot", serialize_all_atom_system(source_ingest.system)
        )
        object.__setattr__(self, "_source_coverage", source_ingest.coverage)
        object.__setattr__(self, "_write_result", write_result)
        object.__setattr__(
            self,
            "_reparsed_snapshot",
            serialize_all_atom_system(reparsed_ingest.system),
        )
        object.__setattr__(self, "_reparsed_coverage", reparsed_ingest.coverage)
        object.__setattr__(self, "_report", report)
        self.__post_init__()

    @property
    def source_ingest(self) -> SmilesIngestResult:
        """Return a fresh detached copy of the source canonical snapshot."""

        return SmilesIngestResult(
            system=deserialize_all_atom_system(self._source_snapshot),
            coverage=self._source_coverage,
        )

    @property
    def write_result(self) -> SmilesWriteResult:
        return self._write_result

    @property
    def reparsed_ingest(self) -> SmilesIngestResult:
        """Return a fresh detached copy of the reparsed canonical snapshot."""

        return SmilesIngestResult(
            system=deserialize_all_atom_system(self._reparsed_snapshot),
            coverage=self._reparsed_coverage,
        )

    @property
    def report(self) -> SmilesRoundTripReport:
        return self._report

    def __post_init__(self) -> None:
        if (
            type(self._source_snapshot) is not bytes
            or type(self._reparsed_snapshot) is not bytes
        ):
            raise TypeError("round-trip snapshots must be exact bytes")
        if type(self._source_coverage) is not SmilesIngestCoverage:
            raise TypeError("source coverage must be a SmilesIngestCoverage")
        if type(self._reparsed_coverage) is not SmilesIngestCoverage:
            raise TypeError("reparsed coverage must be a SmilesIngestCoverage")
        if type(self._write_result) is not SmilesWriteResult:
            raise TypeError("write result must be a SmilesWriteResult")
        if type(self._report) is not SmilesRoundTripReport:
            raise TypeError("report must be a SmilesRoundTripReport")

        source_ingest = self.source_ingest
        reparsed_ingest = self.reparsed_ingest
        source = source_ingest.system
        reparsed = reparsed_ingest.system
        source_state = _validate_write_state(source)
        reparsed_state = _validate_write_state(reparsed)
        reemitted = write_smiles(reparsed)
        source_observation = source.provenance.metadata.get("parser_observation_sha256")
        reparsed_observation = reparsed.provenance.metadata.get(
            "parser_observation_sha256"
        )
        output_sha256 = hashlib.sha256(self.write_result.payload).hexdigest()
        pairs = (
            (
                "source schema receipt",
                source.schema_id,
                self.write_result.receipt.input_system_schema_id,
            ),
            (
                "source provenance report",
                source.provenance.source_sha256,
                self.report.input_source_sha256,
            ),
            (
                "source provenance receipt",
                source.provenance.source_sha256,
                self.write_result.receipt.parent_source_sha256,
            ),
            (
                "source snapshot receipt",
                canonical_all_atom_snapshot_digest(source),
                self.write_result.receipt.input_snapshot_sha256,
            ),
            (
                "source snapshot report",
                canonical_all_atom_snapshot_digest(source),
                self.report.input_snapshot_sha256,
            ),
            (
                "source topology receipt",
                source_state.canonical_topology_sha256,
                self.write_result.receipt.input_topology_sha256,
            ),
            (
                "source topology report",
                source_state.canonical_topology_sha256,
                self.report.input_topology_sha256,
            ),
            (
                "source ordered receipt",
                source_state.ordered_topology_sha256,
                self.write_result.receipt.input_ordered_topology_sha256,
            ),
            (
                "source ordered report",
                source_state.ordered_topology_sha256,
                self.report.input_ordered_topology_sha256,
            ),
            (
                "source state receipt",
                _sha256_document(source_state.representable_state_document),
                self.write_result.receipt.input_representable_state_sha256,
            ),
            (
                "source state report",
                _sha256_document(source_state.representable_state_document),
                self.report.input_representable_state_sha256,
            ),
            (
                "source cycle receipt",
                source_state.cycle_projection_sha256,
                self.write_result.receipt.input_cycle_projection_sha256,
            ),
            (
                "source cycle report",
                source_state.cycle_projection_sha256,
                self.report.input_cycle_projection_sha256,
            ),
            (
                "source aromatic receipt",
                source_state.aromatic_projection_sha256,
                self.write_result.receipt.input_aromatic_projection_sha256,
            ),
            (
                "source aromatic report",
                source_state.aromatic_projection_sha256,
                self.report.input_aromatic_projection_sha256,
            ),
            (
                "source E/Z receipt",
                source_state.ez_stereo_projection_sha256,
                self.write_result.receipt.input_ez_stereo_projection_sha256,
            ),
            (
                "source E/Z report",
                source_state.ez_stereo_projection_sha256,
                self.report.input_ez_stereo_projection_sha256,
            ),
            (
                "source tetrahedral receipt",
                source_state.tetrahedral_stereo_projection_sha256,
                self.write_result.receipt.input_tetrahedral_stereo_projection_sha256,
            ),
            (
                "source tetrahedral report",
                source_state.tetrahedral_stereo_projection_sha256,
                self.report.input_tetrahedral_stereo_projection_sha256,
            ),
            (
                "source observation receipt",
                source_observation,
                self.write_result.receipt.input_parser_observation_sha256,
            ),
            (
                "source observation report",
                source_observation,
                self.report.input_parser_observation_sha256,
            ),
            (
                "source fragment receipt",
                source_state.fragment_count,
                self.write_result.receipt.fragment_count,
            ),
            (
                "source formal charge profile receipt",
                source_state.formal_charge_profile_id,
                self.write_result.receipt.formal_charge_profile_id,
            ),
            (
                "source charged atom count receipt",
                source_state.charged_source_atom_count,
                self.write_result.receipt.charged_source_atom_count,
            ),
            (
                "source formal charge total receipt",
                source_state.formal_charge_total,
                self.write_result.receipt.formal_charge_total,
            ),
            (
                "source implicit hydrogen count receipt",
                source_state.implicit_hydrogen_count,
                self.write_result.receipt.implicit_hydrogen_count,
            ),
            (
                "source bracket hydrogen count receipt",
                source_state.bracket_explicit_hydrogen_count,
                self.write_result.receipt.bracket_explicit_hydrogen_count,
            ),
            (
                "source mapped atom count receipt",
                source_state.mapped_source_atom_count,
                self.write_result.receipt.mapped_source_atom_count,
            ),
            (
                "source tetrahedral atom count receipt",
                source_state.typed_tetrahedral_atom_count,
                self.write_result.receipt.typed_tetrahedral_atom_count,
            ),
            (
                "source bond count receipt",
                source_state.source_bond_count,
                self.write_result.receipt.source_bond_count,
            ),
            (
                "source tree-edge count receipt",
                source_state.source_tree_edge_count,
                self.write_result.receipt.source_tree_edge_count,
            ),
            (
                "source closure count receipt",
                source_state.ring_closure_count,
                self.write_result.receipt.ring_closure_count,
            ),
            (
                "source cyclic component count receipt",
                source_state.cyclic_component_count,
                self.write_result.receipt.cyclic_component_count,
            ),
            (
                "source ring size receipt",
                source_state.ring_size,
                self.write_result.receipt.ring_size,
            ),
            (
                "source closure index receipt",
                source_state.ring_closure_source_bond_index,
                self.write_result.receipt.ring_closure_source_bond_index,
            ),
            (
                "source cycle profile receipt",
                source_state.cycle_profile_id,
                self.write_result.receipt.cycle_profile_id,
            ),
            (
                "source ring bond profile receipt",
                source_state.ring_bond_profile_id,
                self.write_result.receipt.ring_bond_profile_id,
            ),
            (
                "source ring double count receipt",
                source_state.ring_double_bond_count,
                self.write_result.receipt.ring_double_bond_count,
            ),
            (
                "source ring double index receipt",
                source_state.ring_double_source_bond_index,
                self.write_result.receipt.ring_double_source_bond_index,
            ),
            (
                "source aromatic atom count receipt",
                source_state.aromatic_source_atom_count,
                self.write_result.receipt.aromatic_source_atom_count,
            ),
            (
                "source aromatic bond count receipt",
                source_state.aromatic_source_bond_count,
                self.write_result.receipt.aromatic_source_bond_count,
            ),
            (
                "source aromatic ring profile receipt",
                source_state.aromatic_ring_profile_id,
                self.write_result.receipt.aromatic_ring_profile_id,
            ),
            (
                "source aromatic atom profile receipt",
                source_state.aromatic_atom_state_profile_id,
                self.write_result.receipt.aromatic_atom_state_profile_id,
            ),
            (
                "source/reparsed formal charge profile",
                source_state.formal_charge_profile_id,
                reparsed_state.formal_charge_profile_id,
            ),
            (
                "source/reparsed charged atom count",
                source_state.charged_source_atom_count,
                reparsed_state.charged_source_atom_count,
            ),
            (
                "source/reparsed formal charge total",
                source_state.formal_charge_total,
                reparsed_state.formal_charge_total,
            ),
            (
                "source/reparsed implicit hydrogen count",
                source_state.implicit_hydrogen_count,
                reparsed_state.implicit_hydrogen_count,
            ),
            (
                "source/reparsed bracket hydrogen count",
                source_state.bracket_explicit_hydrogen_count,
                reparsed_state.bracket_explicit_hydrogen_count,
            ),
            (
                "source/reparsed mapped atom count",
                source_state.mapped_source_atom_count,
                reparsed_state.mapped_source_atom_count,
            ),
            (
                "source/reparsed tetrahedral atom count",
                source_state.typed_tetrahedral_atom_count,
                reparsed_state.typed_tetrahedral_atom_count,
            ),
            (
                "source/reparsed tetrahedral profile",
                source_state.tetrahedral_stereo_profile_id,
                reparsed_state.tetrahedral_stereo_profile_id,
            ),
            (
                "source/reparsed tetrahedral projection",
                source_state.tetrahedral_stereo_projection_sha256,
                reparsed_state.tetrahedral_stereo_projection_sha256,
            ),
            (
                "source/reparsed cycle projection",
                source_state.cycle_projection_sha256,
                reparsed_state.cycle_projection_sha256,
            ),
            (
                "source/reparsed aromatic projection",
                source_state.aromatic_projection_sha256,
                reparsed_state.aromatic_projection_sha256,
            ),
            (
                "source/reparsed component cycle ranks",
                source_state.component_cyclomatic_numbers,
                reparsed_state.component_cyclomatic_numbers,
            ),
            (
                "source/reparsed cycle profile",
                source_state.cycle_profile_id,
                reparsed_state.cycle_profile_id,
            ),
            (
                "source/reparsed ring bond profile",
                source_state.ring_bond_profile_id,
                reparsed_state.ring_bond_profile_id,
            ),
            (
                "source/reparsed ring double count",
                source_state.ring_double_bond_count,
                reparsed_state.ring_double_bond_count,
            ),
            (
                "source/reparsed ring double index",
                source_state.ring_double_source_bond_index,
                reparsed_state.ring_double_source_bond_index,
            ),
            (
                "source/reparsed aromatic atom count",
                source_state.aromatic_source_atom_count,
                reparsed_state.aromatic_source_atom_count,
            ),
            (
                "source/reparsed aromatic bond count",
                source_state.aromatic_source_bond_count,
                reparsed_state.aromatic_source_bond_count,
            ),
            (
                "source/reparsed aromatic ring profile",
                source_state.aromatic_ring_profile_id,
                reparsed_state.aromatic_ring_profile_id,
            ),
            (
                "source/reparsed aromatic atom profile",
                source_state.aromatic_atom_state_profile_id,
                reparsed_state.aromatic_atom_state_profile_id,
            ),
            (
                "source/reparsed aromatic projection document",
                source_state.aromatic_projection_document,
                reparsed_state.aromatic_projection_document,
            ),
            (
                "source/reparsed ring bond order table",
                source_state.ring_bond_order_table,
                reparsed_state.ring_bond_order_table,
            ),
            (
                "source/reparsed ring marker table",
                source_state.source_ring_marker_table,
                reparsed_state.source_ring_marker_table,
            ),
            (
                "source/reparsed source atom tokens",
                source_state.source_atom_tokens,
                reparsed_state.source_atom_tokens,
            ),
            (
                "source/reparsed fragment count",
                source_state.fragment_count,
                reparsed_state.fragment_count,
            ),
            (
                "source/reparsed roots",
                source_state.source_component_roots,
                reparsed_state.source_component_roots,
            ),
            (
                "source/reparsed source components",
                source_state.source_components,
                reparsed_state.source_components,
            ),
            (
                "source/reparsed expanded components",
                source_state.expanded_components,
                reparsed_state.expanded_components,
            ),
            (
                "source/reparsed children",
                source_state.source_children,
                reparsed_state.source_children,
            ),
            (
                "source/reparsed parent bond tokens",
                source_state.source_parent_bond_tokens,
                reparsed_state.source_parent_bond_tokens,
            ),
            (
                "receipt report",
                self.write_result.receipt.receipt_sha256,
                self.report.writer_receipt_sha256,
            ),
            (
                "payload receipt",
                output_sha256,
                self.write_result.receipt.output_source_sha256,
            ),
            ("payload report", output_sha256, self.report.emitted_source_sha256),
            (
                "payload reparsed source",
                output_sha256,
                reparsed.provenance.source_sha256,
            ),
            (
                "reparsed snapshot report",
                canonical_all_atom_snapshot_digest(reparsed),
                self.report.reparsed_snapshot_sha256,
            ),
            (
                "reparsed topology report",
                reparsed_state.canonical_topology_sha256,
                self.report.reparsed_topology_sha256,
            ),
            (
                "reparsed ordered report",
                reparsed_state.ordered_topology_sha256,
                self.report.reparsed_ordered_topology_sha256,
            ),
            (
                "reparsed state report",
                _sha256_document(reparsed_state.representable_state_document),
                self.report.reparsed_representable_state_sha256,
            ),
            (
                "reparsed cycle report",
                reparsed_state.cycle_projection_sha256,
                self.report.reparsed_cycle_projection_sha256,
            ),
            (
                "reparsed aromatic report",
                reparsed_state.aromatic_projection_sha256,
                self.report.reparsed_aromatic_projection_sha256,
            ),
            (
                "reparsed E/Z report",
                reparsed_state.ez_stereo_projection_sha256,
                self.report.reparsed_ez_stereo_projection_sha256,
            ),
            (
                "reparsed tetrahedral report",
                reparsed_state.tetrahedral_stereo_projection_sha256,
                self.report.reparsed_tetrahedral_stereo_projection_sha256,
            ),
            (
                "reparsed observation report",
                reparsed_observation,
                self.report.reparsed_parser_observation_sha256,
            ),
            (
                "reemitted report",
                hashlib.sha256(reemitted.payload).hexdigest(),
                self.report.reemitted_source_sha256,
            ),
        )
        mismatches = [
            label
            for label, left, right in pairs
            if type(left) is not type(right) or left != right
        ]
        if self.write_result._input_snapshot != self._source_snapshot:
            mismatches.append("write input snapshot to source ingest snapshot")
        for label, ingest in (("source", source_ingest), ("reparsed", reparsed_ingest)):
            if not _exact_typed_structure_equal(
                ingest.system.provenance.metadata.get("coverage"),
                ingest.coverage.to_dict(),
            ):
                mismatches.append(f"{label} ingest coverage")
        if reemitted.payload != self.write_result.payload:
            mismatches.append("reemitted payload bytes")
        if mismatches:
            raise ValueError(
                "SMILES round-trip result artifacts are not cross-consistent: "
                f"{mismatches}"
            )


@dataclass(frozen=True, slots=True)
class _ValidatedWriteState:
    system: AllAtomSystem
    source_atom_count: int
    generated_hydrogen_count: int
    implicit_hydrogen_count: int
    bracket_explicit_hydrogen_count: int
    mapped_source_atom_count: int
    typed_tetrahedral_atom_count: int
    fragment_count: int
    formal_charge_profile_id: str
    cycle_profile_id: str
    ring_bond_profile_id: str | None
    charged_source_atom_count: int
    formal_charge_total: int
    source_atom_tokens: tuple[str, ...]
    source_component_roots: tuple[int, ...]
    source_components: tuple[tuple[int, ...], ...]
    expanded_components: tuple[tuple[int, ...], ...]
    source_children: tuple[tuple[int, ...], ...]
    source_parent_bond_tokens: tuple[str, ...]
    source_ring_marker_table: tuple[str, ...]
    source_bond_count: int
    source_tree_edge_count: int
    component_cyclomatic_numbers: tuple[int, ...]
    ring_closure_count: int
    cyclic_component_count: int
    cyclic_component_index: int | None
    ring_size: int
    ring_atom_indices: tuple[int, ...]
    ring_bond_indices: tuple[int, ...]
    ring_closure_source_bond_index: int | None
    ring_closure_endpoints: tuple[int, ...]
    ring_open_source_atom_index: int | None
    ring_close_source_atom_index: int | None
    ring_double_bond_count: int
    ring_double_source_bond_index: int | None
    aromatic_source_atom_count: int
    aromatic_source_bond_count: int
    aromatic_ring_profile_id: str | None
    aromatic_atom_state_profile_id: str | None
    typed_ez_bond_count: int
    directional_source_bond_count: int
    ez_stereo_profile_id: str
    ring_bond_order_table: tuple[
        tuple[int, tuple[int, int], str, bool, str, str, str], ...
    ]
    cycle_projection_document: Mapping[str, Any]
    cycle_projection_sha256: str
    aromatic_projection_document: Mapping[str, Any]
    aromatic_projection_sha256: str
    ez_stereo_projection_document: Mapping[str, Any]
    ez_stereo_projection_sha256: str
    tetrahedral_stereo_profile_id: str
    tetrahedral_stereo_projection_document: Mapping[str, Any]
    tetrahedral_stereo_projection_sha256: str
    rdkit_version: str
    normalized_isomeric_smiles_sha256: str
    ordered_topology_sha256: str
    canonical_topology_sha256: str
    coverage_document: Mapping[str, Any]
    representable_state_document: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ValidatedSourceForest:
    generated_hydrogen_count: int
    implicit_hydrogen_count: int
    bracket_explicit_hydrogen_count: int
    mapped_source_atom_count: int
    typed_tetrahedral_atom_count: int
    fragment_count: int
    charged_source_atom_count: int
    formal_charge_total: int
    source_atom_tokens: tuple[str, ...]
    source_component_roots: tuple[int, ...]
    source_components: tuple[tuple[int, ...], ...]
    expanded_components: tuple[tuple[int, ...], ...]
    source_children: tuple[tuple[int, ...], ...]
    source_parent_bond_tokens: tuple[str, ...]
    source_ring_marker_table: tuple[str, ...]
    source_bond_count: int
    source_tree_edge_count: int
    component_cyclomatic_numbers: tuple[int, ...]
    ring_closure_count: int
    cyclic_component_count: int
    cyclic_component_index: int | None
    ring_size: int
    ring_atom_indices: tuple[int, ...]
    ring_bond_indices: tuple[int, ...]
    ring_closure_source_bond_index: int | None
    ring_closure_endpoints: tuple[int, ...]
    ring_open_source_atom_index: int | None
    ring_close_source_atom_index: int | None
    cycle_profile_id: str
    ring_bond_profile_id: str | None
    ring_double_bond_count: int
    ring_double_source_bond_index: int | None
    aromatic_source_atom_count: int
    aromatic_source_bond_count: int
    aromatic_ring_profile_id: str | None
    aromatic_atom_state_profile_id: str | None
    typed_ez_bond_count: int
    directional_source_bond_count: int
    ez_stereo_profile_id: str
    ring_bond_order_table: tuple[
        tuple[int, tuple[int, int], str, bool, str, str, str], ...
    ]
    cycle_projection_document: Mapping[str, Any]
    cycle_projection_sha256: str
    aromatic_projection_document: Mapping[str, Any]
    aromatic_projection_sha256: str
    ez_stereo_projection_document: Mapping[str, Any]
    ez_stereo_projection_sha256: str
    tetrahedral_stereo_profile_id: str
    tetrahedral_stereo_projection_document: Mapping[str, Any]
    tetrahedral_stereo_projection_sha256: str


def _preflight_snapshot_carrier(system: AllAtomSystem) -> None:
    if type(system) is not AllAtomSystem:
        raise TypeError("SMILES writer input must be an exact AllAtomSystem")
    if len(system.atoms) > _MAX_EXPANDED_ATOMS:
        raise SmilesWriteError(
            "unsupported_expanded_atom_count",
            "expanded atom count is outside the parser safety limit",
            location="atoms",
        )
    if len(system.bonds) > _MAX_BONDS:
        raise SmilesWriteError(
            "unsupported_bond_count",
            "bond count is outside the parser safety limit",
            location="bonds",
        )
    if len(system.residues) > _MAX_FRAGMENTS or len(system.chains) > _MAX_FRAGMENTS:
        raise SmilesWriteError(
            "unsupported_fragment_count",
            "residue or chain count is outside the SMILES writer fragment limit",
            location="residues",
        )
    coordinates = system.coordinates
    if coordinates.shape != (0, system.atom_count, 3):
        raise SmilesWriteError(
            "unsupported_coordinates",
            "SMILES writer accepts only the exact empty topology-only coordinate carrier",
            location="coordinates",
        )


def _snapshot_parser_system(system: AllAtomSystem) -> AllAtomSystem:
    _preflight_snapshot_carrier(system)
    coordinates = system.coordinates
    if coordinates.device.type != "cpu":
        raise SmilesWriteError(
            "unsupported_coordinate_device",
            "parser-owned topology-only coordinates must be on CPU",
            location="coordinates",
        )
    if coordinates.dtype is not torch.float64:
        raise SmilesWriteError(
            "unsupported_coordinate_dtype",
            "parser-owned topology-only coordinates must use float64",
            location="coordinates",
        )
    if coordinates.requires_grad:
        raise SmilesWriteError(
            "coordinate_gradient_state_unsupported",
            "SMILES writing does not accept coordinates requiring gradients",
            location="coordinates",
        )
    try:
        snapshot = replace(system, coordinates=coordinates.detach().clone())
        require_valid_all_atom_system(snapshot)
    except (MolecularValidationError, TypeError, ValueError, RuntimeError) as exc:
        raise SmilesWriteError(
            "canonical_validation_failed",
            str(exc),
            location="system",
        ) from exc
    return snapshot


def _ordered_topology_digest(
    atoms: tuple[Atom, ...],
    bonds: tuple[Bond, ...],
    expanded_components: tuple[tuple[int, ...], ...],
) -> str:
    document = {
        "atoms": [
            {
                "index": atom.index,
                "atomic_number": atom.atomic_number,
                "formal_charge": atom.formal_charge,
                "isotope_mass_number": atom.isotope_mass_number,
                "atom_map": atom.atom_map,
                "aromatic": atom.aromatic,
                "stereo": atom.stereo,
                "residue_index": atom.residue_index,
                "source_atom_index": atom.metadata.get("source_atom_index"),
                "parent_source_atom_index": atom.metadata.get(
                    "parent_source_atom_index"
                ),
                "hydrogen_origin": atom.metadata.get("hydrogen_origin"),
                "hydrogen_ordinal": atom.metadata.get("hydrogen_ordinal"),
            }
            for atom in atoms
        ],
        "bonds": [
            {
                "index": bond.index,
                "atom_i": bond.atom_i,
                "atom_j": bond.atom_j,
                "order": bond.order,
                "aromatic": bond.aromatic,
                "stereo": bond.stereo,
                "source": bond.source,
            }
            for bond in bonds
        ],
        "components": [list(component) for component in expanded_components],
    }
    return hashlib.sha256(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _expected_coverage_document(
    *,
    rdkit_version: str,
    source_atom_count: int,
    expanded_atom_count: int,
    bond_count: int,
    generated_hydrogen_count: int,
    fragment_count: int,
    formal_charge_total: int,
    mapped_source_atom_count: int,
    aromatic_atom_count: int,
    typed_tetrahedral_atom_count: int,
    typed_ez_bond_count: int,
    ordered_topology_sha256: str,
    topology_sha256: str,
) -> dict[str, Any]:
    return SmilesIngestCoverage(
        rdkit_version=rdkit_version,
        source_atom_count=source_atom_count,
        expanded_atom_count=expanded_atom_count,
        bond_count=bond_count,
        fragment_count=fragment_count,
        generated_hydrogen_count=generated_hydrogen_count,
        explicit_hydrogen_count=generated_hydrogen_count,
        formal_charge_total=formal_charge_total,
        isotope_count=0,
        atom_map_count=mapped_source_atom_count,
        aromatic_atom_count=aromatic_atom_count,
        typed_atom_stereo_count=typed_tetrahedral_atom_count,
        typed_bond_stereo_count=typed_ez_bond_count,
        ordered_topology_sha256=ordered_topology_sha256,
        canonical_topology_schema_id=CANONICAL_TOPOLOGY_SCHEMA_ID,
        canonical_topology_sha256=topology_sha256,
        blockers=(
            _COVERAGE_BASE_BLOCKERS
            + (
                ("aromaticity_not_independently_verified",)
                if aromatic_atom_count
                else ()
            )
            + (
                (
                    "cip_assignment_not_independently_verified",
                    "stereo_geometry_unavailable",
                )
                if typed_tetrahedral_atom_count or typed_ez_bond_count
                else ()
            )
            + (
                ("disconnected_fragment_roles_not_assessed",)
                if fragment_count > 1
                else ()
            )
        ),
    ).to_dict()


def _validate_provenance_and_metadata(
    system: AllAtomSystem,
    *,
    source_atom_count: int,
    generated_hydrogen_count: int,
    fragment_count: int,
    formal_charge_total: int,
    mapped_source_atom_count: int,
    aromatic_atom_count: int,
    typed_tetrahedral_atom_count: int,
    typed_ez_bond_count: int,
    ordered_topology_sha256: str,
    topology_sha256: str,
) -> tuple[str, str, Mapping[str, Any]]:
    provenance = system.provenance
    if provenance.source_format != "smiles":
        raise SmilesWriteError(
            "unsupported_source_format",
            "writer accepts only strict SMILES parser output",
            location="provenance.source_format",
        )
    if (
        provenance.parser_name != _SMILES_PARSER_NAME
        or provenance.parser_version != SMILES_PARSER_VERSION
    ):
        raise SmilesWriteError(
            "unsupported_parser_pedigree",
            "writer requires the current strict SMILES parser pedigree",
            location="provenance",
        )
    if provenance.operations != _PARSER_OPERATIONS:
        raise SmilesWriteError(
            "unsupported_provenance_operations",
            "provenance operations are not the exact parser-owned ledger",
            location="provenance.operations",
        )
    if provenance.parent_sha256:
        raise SmilesWriteError(
            "unsupported_parent_provenance",
            "parser-owned SMILES state must not carry parent hashes",
            location="provenance.parent_sha256",
        )
    if provenance.preparation_ready or provenance.claim_safe:
        raise SmilesWriteError(
            "unsupported_authority_state",
            "SMILES writing cannot preserve preparation or claim authority",
            location="provenance",
        )
    _require_sha256(provenance.source_sha256, field_name="provenance.source_sha256")

    system_metadata = _require_exact_keys(
        system.metadata,
        _SYSTEM_METADATA_KEYS,
        code="unsupported_system_metadata",
        location="metadata",
    )
    expected_system_metadata = {
        "ordered_topology_sha256": ordered_topology_sha256,
        "source_atom_count": source_atom_count,
        "generated_hydrogen_count": generated_hydrogen_count,
        "fragment_count": fragment_count,
    }
    if not _exact_typed_structure_equal(system_metadata, expected_system_metadata):
        raise SmilesWriteError(
            "stale_system_markers",
            "system-level parser markers do not match current graph state",
            location="metadata",
        )

    metadata = _require_exact_keys(
        provenance.metadata,
        _PROVENANCE_METADATA_KEYS,
        code="unsupported_provenance_metadata",
        location="provenance.metadata",
    )
    rdkit_version = metadata["rdkit_version"]
    if type(rdkit_version) is not str or not rdkit_version:
        raise SmilesWriteError(
            "unsupported_rdkit_version",
            "RDKit version marker must be a nonempty exact string",
            location="provenance.metadata.rdkit_version",
        )
    try:
        _, _, live_rdkit_version = _load_adapter()
    except SmilesParseError as exc:
        raise SmilesWriteError(
            "unsupported_rdkit_version",
            "the active RDKit adapter is not the parser-owned allowlisted pin",
            location="provenance.metadata.rdkit_version",
        ) from exc
    if rdkit_version != live_rdkit_version:
        raise SmilesWriteError(
            "unsupported_rdkit_version",
            "the attached RDKit version does not match the active parser pin",
            location="provenance.metadata.rdkit_version",
        )
    normalized_sha256 = metadata["normalized_isomeric_smiles_sha256"]
    try:
        _require_sha256(
            normalized_sha256,
            field_name="provenance.metadata.normalized_isomeric_smiles_sha256",
        )
    except TypeError as exc:
        raise SmilesWriteError(
            "invalid_normalized_smiles_sha256",
            str(exc),
            location="provenance.metadata.normalized_isomeric_smiles_sha256",
        ) from exc
    expected_coverage = _expected_coverage_document(
        rdkit_version=rdkit_version,
        source_atom_count=source_atom_count,
        expanded_atom_count=system.atom_count,
        bond_count=len(system.bonds),
        generated_hydrogen_count=generated_hydrogen_count,
        fragment_count=fragment_count,
        formal_charge_total=formal_charge_total,
        mapped_source_atom_count=mapped_source_atom_count,
        aromatic_atom_count=aromatic_atom_count,
        typed_tetrahedral_atom_count=typed_tetrahedral_atom_count,
        typed_ez_bond_count=typed_ez_bond_count,
        ordered_topology_sha256=ordered_topology_sha256,
        topology_sha256=topology_sha256,
    )
    if not _exact_typed_structure_equal(metadata["coverage"], expected_coverage):
        raise SmilesWriteError(
            "stale_smiles_coverage",
            "attached SMILES coverage does not match current canonical state",
            location="provenance.metadata.coverage",
        )
    if (
        metadata["ordered_topology_sha256"] != ordered_topology_sha256
        or metadata["canonical_topology_schema_id"] != CANONICAL_TOPOLOGY_SCHEMA_ID
        or metadata["canonical_topology_sha256"] != topology_sha256
        or not attached_canonical_topology_sha256_matches(system)
    ):
        raise SmilesWriteError(
            "stale_canonical_topology_digest",
            "attached topology digests are missing or stale",
            location="provenance.metadata",
        )
    if (
        metadata["parser_observation_schema_id"] != PARSER_OBSERVATION_SCHEMA_ID
        or type(metadata["parser_observation_sha256"]) is not str
        or _SHA256_RE.fullmatch(metadata["parser_observation_sha256"]) is None
        or not attached_parser_observation_sha256_matches(system)
    ):
        raise SmilesWriteError(
            "stale_parser_observation_digest",
            "attached parser-observation digest is missing or stale",
            location="provenance.metadata",
        )
    return rdkit_version, normalized_sha256, expected_coverage


def _token_with_atom_map(token: str, atom_map: int | None) -> str:
    if atom_map is None:
        return token
    if type(atom_map) is not int or atom_map < 1:
        raise SmilesWriteError(
            "unsupported_atom_map",
            "source atom maps must be unique positive exact integers",
        )
    if token.startswith("[") and token.endswith("]"):
        return f"{token[:-1]}:{atom_map}]"
    return f"[{token}:{atom_map}]"


def _source_atom_token(
    atom: Atom,
    *,
    bracket_hydrogen_count: int,
    tetrahedral_marker: str | None = None,
) -> str:
    """Render only the already-validated parser-observed atom identity."""

    if tetrahedral_marker is not None:
        if tetrahedral_marker not in {"@", "@@"}:
            raise SmilesWriteError(
                "internal_emission_error",
                "tetrahedral marker must be @ or @@",
                location=f"atoms[{atom.index}]",
            )
        if atom.aromatic or bracket_hydrogen_count not in {0, 1}:
            raise SmilesWriteError(
                "unsupported_atom_stereo",
                "typed tetrahedral atoms must be nonaromatic with zero or one bracket-explicit hydrogen",
                location=f"atoms[{atom.index}]",
            )
        hydrogen = "H" if bracket_hydrogen_count else ""
        charge = (
            "" if atom.formal_charge == 0 else ("+" if atom.formal_charge == 1 else "-")
        )
        return _token_with_atom_map(
            f"[{atom.element}{tetrahedral_marker}{hydrogen}{charge}]",
            atom.atom_map,
        )
    if atom.aromatic:
        token = _AROMATIC_ATOM_TOKENS.get(
            (atom.element, atom.formal_charge, bracket_hydrogen_count)
        )
        if token is None:
            raise SmilesWriteError(
                "unsupported_aromatic_atom_state",
                "aromatic source atom state is outside the finite canonical token table",
                location=f"atoms[{atom.index}]",
            )
        return _token_with_atom_map(token, atom.atom_map)
    if bracket_hydrogen_count:
        raise SmilesWriteError(
            "unsupported_bracket_hydrogen",
            "bracket-explicit hydrogens require a selected aromatic source atom",
            location=f"atoms[{atom.index}]",
        )
    if atom.formal_charge == 0:
        return _token_with_atom_map(atom.element, atom.atom_map)
    sign = "+" if atom.formal_charge == 1 else "-"
    return _token_with_atom_map(f"[{atom.element}{sign}]", atom.atom_map)


def _validate_atom_common(atom: Atom, *, location: str) -> None:
    if atom.partial_charge_e is not None:
        raise SmilesWriteError(
            "unsupported_partial_charge",
            "partial charges are not representable",
            location=f"{location}.partial_charge_e",
        )
    if atom.mass_da is not None:
        raise SmilesWriteError(
            "unsupported_atom_mass",
            "atom masses are not representable",
            location=f"{location}.mass_da",
        )
    if atom.isotope_mass_number is not None:
        raise SmilesWriteError(
            "unsupported_isotope",
            "isotopes are not representable",
            location=f"{location}.isotope_mass_number",
        )
    if atom.altloc:
        raise SmilesWriteError(
            "unsupported_altloc",
            "alternate locations are not representable",
            location=f"{location}.altloc",
        )
    if atom.occupancy is not None or atom.b_factor is not None:
        raise SmilesWriteError(
            "unsupported_atom_observation",
            "occupancy and B-factor state are not representable",
            location=location,
        )


def _preflight_supported_scope(
    system: AllAtomSystem,
    *,
    source_atom_count: int,
) -> None:
    """Surface stable projection errors before stale digest side effects."""

    if 0 <= source_atom_count <= system.atom_count:
        seen_atom_maps: set[int] = set()
        typed_tetrahedral_atom_count = 0
        for index, atom in enumerate(system.atoms[:source_atom_count]):
            location = f"atoms[{index}]"
            if atom.element == "H":
                raise SmilesWriteError(
                    "unsupported_source_hydrogen",
                    "source-explicit hydrogen atoms are outside writer v1.8",
                    location=f"{location}.element",
                )
            if atom.element not in _SOURCE_ELEMENTS:
                raise SmilesWriteError(
                    "unsupported_element",
                    "source element is outside the organic-subset writer policy",
                    location=f"{location}.element",
                )
            if (
                atom.formal_charge_known is not True
                or type(atom.formal_charge) is not int
                or atom.formal_charge not in _SOURCE_FORMAL_CHARGES
            ):
                raise SmilesWriteError(
                    "unsupported_formal_charge",
                    "source formal charge must be a known exact -1, 0, or +1",
                    location=f"{location}.formal_charge",
                )
            if atom.isotope_mass_number is not None:
                raise SmilesWriteError(
                    "unsupported_isotope",
                    "isotope-qualified atoms are outside writer v1.8",
                    location=f"{location}.isotope_mass_number",
                )
            if atom.atom_map is not None:
                if (
                    type(atom.atom_map) is not int
                    or atom.atom_map < 1
                    or atom.atom_map in seen_atom_maps
                ):
                    raise SmilesWriteError(
                        "unsupported_atom_map",
                        "source atom maps must be unique positive exact integers",
                        location=f"{location}.atom_map",
                    )
                seen_atom_maps.add(atom.atom_map)
            if atom.stereo not in {"UNSPECIFIED", "R", "S"}:
                raise SmilesWriteError(
                    "unsupported_atom_stereo",
                    "only parser-typed tetrahedral R/S atom stereochemistry is inside writer v1.8",
                    location=f"{location}.stereo",
                )
            typed_tetrahedral_atom_count += int(atom.stereo in {"R", "S"})
            chiral_tag = atom.metadata.get("rdkit_chiral_tag")
            expected_tags = (
                {"CHI_UNSPECIFIED"}
                if atom.stereo == "UNSPECIFIED"
                else {"CHI_TETRAHEDRAL_CW", "CHI_TETRAHEDRAL_CCW"}
            )
            if chiral_tag not in expected_tags:
                raise SmilesWriteError(
                    "inconsistent_tetrahedral_stereo_state",
                    "R/S and parser chiral-tag state are inconsistent",
                    location=f"{location}.metadata.rdkit_chiral_tag",
                )
        if typed_tetrahedral_atom_count > _MAX_TYPED_TETRAHEDRAL_ATOMS:
            raise SmilesWriteError(
                "unsupported_tetrahedral_atom_count",
                "typed tetrahedral atom count exceeds the writer limit",
                location="atoms",
            )
        if (
            typed_tetrahedral_atom_count
            and source_atom_count > _MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS
        ):
            raise SmilesWriteError(
                "unsupported_tetrahedral_calibration_source_atom_count",
                "source atom count exceeds the tetrahedral calibration limit",
                location="metadata.source_atom_count",
            )
        for index, atom in enumerate(
            system.atoms[source_atom_count:],
            start=source_atom_count,
        ):
            if atom.atom_map is not None:
                raise SmilesWriteError(
                    "unsupported_generated_hydrogen_atom_map",
                    "parser-generated hydrogens may not carry atom maps",
                    location=f"atoms[{index}].atom_map",
                )
            origin = atom.metadata.get("hydrogen_origin")
            parent = atom.metadata.get("parent_source_atom_index")
            if (
                type(parent) is int
                and 0 <= parent < source_atom_count
                and system.atoms[parent].formal_charge != 0
                and origin != "bracket_explicit"
            ):
                raise SmilesWriteError(
                    "unsupported_charged_parent_hydrogen",
                    "charged source atoms may not own implicit hydrogens",
                    location=f"atoms[{index}].metadata.parent_source_atom_index",
                )

    source_bonds = tuple(
        bond for bond in system.bonds if bond.source == "smiles_source"
    )
    for bond in source_bonds:
        location = f"bonds[{bond.index}]"
        if bond.stereo not in {"none", "E", "Z"}:
            raise SmilesWriteError(
                "unsupported_bond_stereo",
                "only none, E, or Z source-bond stereochemistry is inside writer v1.8",
                location=f"{location}.stereo",
            )
        if bond.stereo in {"E", "Z"} and (
            bond.aromatic or type(bond.order) is not float or bond.order != 2.0
        ):
            raise SmilesWriteError(
                "unsupported_bond_stereo",
                "E/Z state must belong to an exact nonaromatic double source bond",
                location=f"{location}.stereo",
            )
        if type(bond.order) is not float or (
            (bond.aromatic and bond.order != 1.5)
            or (not bond.aromatic and bond.order not in _NONAROMATIC_SOURCE_BOND_TOKENS)
        ):
            raise SmilesWriteError(
                "unsupported_bond",
                "source bonds must be exact aromatic 1.5 or nonaromatic single, double, or triple bonds",
                location=f"{location}.order",
            )


def _build_ez_direction_projection(
    *,
    source_bonds: tuple[Bond, ...],
    parent_by_atom: tuple[int, ...],
    ring_bond_indices: tuple[int, ...],
    ring_size: int,
    ring_closure_source_bond_index: int | None,
    ring_double_source_bond_index: int | None,
    ring_open_source_atom_index: int | None,
    ring_close_source_atom_index: int | None,
    source_bond_token_by_pair: Mapping[tuple[int, int], str],
) -> tuple[
    dict[tuple[int, int], str],
    Mapping[str, Any],
    str,
    int,
    int,
]:
    """Project bounded typed E/Z state into SMILES direction tokens.

    The lowest exact-single carrier at each endpoint is selected in source
    bond order.  Tree edges are oriented parent-to-child and the selected ring
    closure is oriented close-to-open, exactly as the emitter spells them.
    Carrier/reference substitutions and those lexical orientations are folded
    into E/Z parity constraints.  Shared carriers in conjugated systems are
    solved together; the lowest carrier in each independent constraint
    component is ``/`` unless the component owns the ring closure, which is
    the stable slash anchor.
    """

    typed_bonds = tuple(bond for bond in source_bonds if bond.stereo in {"E", "Z"})
    if len(typed_bonds) > _MAX_TYPED_EZ_BONDS:
        raise SmilesWriteError(
            "unsupported_ez_bond_count",
            "typed E/Z source-bond count exceeds the fixed writer limit",
            location="bonds",
        )

    pair_to_bond = {(bond.atom_i, bond.atom_j): bond for bond in source_bonds}
    incident_source_bonds: list[list[Bond]] = [[] for _ in range(len(parent_by_atom))]
    for source_bond in source_bonds:
        incident_source_bonds[source_bond.atom_i].append(source_bond)
        incident_source_bonds[source_bond.atom_j].append(source_bond)
    ring_bond_index_set = frozenset(ring_bond_indices)
    constraints: list[tuple[int, int, int, int]] = []
    stereo_rows: list[dict[str, Any]] = []
    carrier_roles: dict[int, list[tuple[int, str]]] = {}

    for bond in typed_bonds:
        location = f"bonds[{bond.index}]"
        if bond.aromatic or bond.order != 2.0:
            raise SmilesWriteError(
                "unsupported_bond_stereo",
                "E/Z state must belong to an exact nonaromatic double source bond",
                location=f"{location}.stereo",
            )
        is_selected_ring_double = bond.index in ring_bond_index_set
        if is_selected_ring_double and not (
            ring_size == 8
            and bond.index == ring_double_source_bond_index
            and ring_closure_source_bond_index is not None
            and ring_open_source_atom_index is not None
            and ring_close_source_atom_index is not None
        ):
            raise SmilesWriteError(
                "unsupported_ez_ring_stereo",
                "ring E/Z is limited to the unique non-closure double of the selected eight-member ring",
                location=f"{location}.stereo",
            )
        if not (
            0 <= bond.atom_i < len(parent_by_atom)
            and 0 <= bond.atom_j < len(parent_by_atom)
            and parent_by_atom[bond.atom_j] == bond.atom_i
        ):
            raise SmilesWriteError(
                "unsupported_ez_emission_orientation",
                "typed E/Z double bond must be a forward source-order DFS tree edge",
                location=location,
            )

        raw_references = bond.metadata.get("stereo_atom_indices")
        if (
            not isinstance(raw_references, (list, tuple))
            or len(raw_references) != 2
            or any(
                type(value) is not int or not 0 <= value < len(parent_by_atom)
                for value in raw_references
            )
            or raw_references[0] == raw_references[1]
        ):
            raise SmilesWriteError(
                "inconsistent_ez_stereo_atoms",
                "typed E/Z state must retain two distinct source stereo-neighbor indices",
                location=f"{location}.metadata.stereo_atom_indices",
            )

        adjacent_by_endpoint: dict[int, tuple[Bond, ...]] = {
            endpoint: tuple(
                candidate
                for candidate in incident_source_bonds[endpoint]
                if candidate.index != bond.index
            )
            for endpoint in (bond.atom_i, bond.atom_j)
        }

        references_by_endpoint: dict[int, int] = {}
        for endpoint in (bond.atom_i, bond.atom_j):
            matching = [
                reference
                for reference in raw_references
                if tuple(sorted((endpoint, reference))) in pair_to_bond
                and reference not in {bond.atom_i, bond.atom_j}
            ]
            if len(matching) != 1:
                raise SmilesWriteError(
                    "inconsistent_ez_stereo_atoms",
                    "each E/Z endpoint must own exactly one retained stereo-neighbor reference",
                    location=f"{location}.metadata.stereo_atom_indices",
                )
            references_by_endpoint[endpoint] = matching[0]

        selected_carriers: dict[int, Bond] = {}
        selected_neighbors: dict[int, int] = {}
        selected_emitted_toward_endpoint: dict[int, bool] = {}
        for endpoint in (bond.atom_i, bond.atom_j):
            candidates = tuple(
                candidate
                for candidate in adjacent_by_endpoint[endpoint]
                if candidate.aromatic is False
                and candidate.order == 1.0
                and candidate.stereo == "none"
            )
            if not candidates:
                raise SmilesWriteError(
                    "unsupported_ez_direction_carrier",
                    "each E/Z endpoint needs a lexically emitted exact-single tree or selected-ring direction carrier",
                    location=location,
                )
            carrier = min(candidates, key=lambda candidate: candidate.index)
            neighbor = carrier.atom_j if carrier.atom_i == endpoint else carrier.atom_i
            if carrier.index == ring_closure_source_bond_index:
                emitted_from = ring_close_source_atom_index
                emitted_to = ring_open_source_atom_index
            elif parent_by_atom[carrier.atom_j] == carrier.atom_i:
                emitted_from = carrier.atom_i
                emitted_to = carrier.atom_j
            elif parent_by_atom[carrier.atom_i] == carrier.atom_j:
                emitted_from = carrier.atom_j
                emitted_to = carrier.atom_i
            else:  # pragma: no cover - source graph validation owns this invariant
                raise SmilesWriteError(
                    "internal_emission_error",
                    "direction carrier has no lexical emission orientation",
                    location=f"bonds[{carrier.index}]",
                )
            if (
                emitted_from is None
                or emitted_to is None
                or endpoint
                not in {
                    emitted_from,
                    emitted_to,
                }
            ):
                raise SmilesWriteError(
                    "internal_emission_error",
                    "direction carrier emission endpoints are inconsistent",
                    location=f"bonds[{carrier.index}]",
                )
            selected_carriers[endpoint] = carrier
            selected_neighbors[endpoint] = neighbor
            selected_emitted_toward_endpoint[endpoint] = emitted_to == endpoint

        left_carrier = selected_carriers[bond.atom_i]
        right_carrier = selected_carriers[bond.atom_j]
        left_neighbor = selected_neighbors[bond.atom_i]
        right_neighbor = selected_neighbors[bond.atom_j]
        if left_carrier.index == right_carrier.index:
            raise SmilesWriteError(
                "unsupported_ez_direction_carrier",
                "one source bond cannot be both direction carriers for one E/Z bond",
                location=location,
            )

        reference_flip = (left_neighbor != references_by_endpoint[bond.atom_i]) ^ (
            right_neighbor != references_by_endpoint[bond.atom_j]
        )
        emission_orientation_flip = (
            selected_emitted_toward_endpoint[bond.atom_i]
            ^ selected_emitted_toward_endpoint[bond.atom_j]
        )
        stereo_parity = 1 if bond.stereo == "E" else 0
        direction_xor = stereo_parity ^ emission_orientation_flip ^ reference_flip
        constraints.append(
            (left_carrier.index, right_carrier.index, direction_xor, bond.index)
        )
        carrier_roles.setdefault(left_carrier.index, []).append(
            (
                bond.index,
                (
                    "incoming"
                    if selected_emitted_toward_endpoint[bond.atom_i]
                    else "outgoing"
                ),
            )
        )
        carrier_roles.setdefault(right_carrier.index, []).append(
            (
                bond.index,
                (
                    "incoming"
                    if selected_emitted_toward_endpoint[bond.atom_j]
                    else "outgoing"
                ),
            )
        )
        stereo_rows.append(
            {
                "source_bond_index": bond.index,
                "atom_indices": [bond.atom_i, bond.atom_j],
                "stereo": bond.stereo,
                "stereo_atom_indices": [
                    references_by_endpoint[bond.atom_i],
                    references_by_endpoint[bond.atom_j],
                ],
                "direction_carrier_source_bond_indices": [
                    left_carrier.index,
                    right_carrier.index,
                ],
                "direction_carrier_neighbor_indices": [left_neighbor, right_neighbor],
                "reference_carrier_parity_flipped": reference_flip,
                "direction_carrier_emitted_toward_stereo_endpoint": [
                    selected_emitted_toward_endpoint[bond.atom_i],
                    selected_emitted_toward_endpoint[bond.atom_j],
                ],
                "emission_orientation_parity_flipped": emission_orientation_flip,
                "direction_token_xor": direction_xor,
            }
        )

    constraint_graph: dict[int, list[tuple[int, int, int]]] = {}
    for left_index, right_index, direction_xor, stereo_bond_index in constraints:
        constraint_graph.setdefault(left_index, []).append(
            (right_index, direction_xor, stereo_bond_index)
        )
        constraint_graph.setdefault(right_index, []).append(
            (left_index, direction_xor, stereo_bond_index)
        )

    direction_by_bond_index: dict[int, int] = {}
    for start in sorted(constraint_graph):
        if start in direction_by_bond_index:
            continue
        component_nodes: set[int] = set()
        discovery = [start]
        while discovery:
            node = discovery.pop()
            if node in component_nodes:
                continue
            component_nodes.add(node)
            discovery.extend(neighbor for neighbor, _, _ in constraint_graph[node])
        anchor = (
            ring_closure_source_bond_index
            if ring_closure_source_bond_index in component_nodes
            else min(component_nodes)
        )
        if anchor in direction_by_bond_index:
            continue
        direction_by_bond_index[anchor] = 0
        stack = [anchor]
        while stack:
            current = stack.pop()
            for neighbor, direction_xor, stereo_bond_index in constraint_graph[current]:
                expected = direction_by_bond_index[current] ^ direction_xor
                observed = direction_by_bond_index.get(neighbor)
                if observed is None:
                    direction_by_bond_index[neighbor] = expected
                    stack.append(neighbor)
                elif observed != expected:
                    raise SmilesWriteError(
                        "inconsistent_ez_direction_constraints",
                        "typed E/Z states impose contradictory direction-token parity",
                        location=f"bonds[{stereo_bond_index}]",
                    )

    token_by_pair = dict(source_bond_token_by_pair)
    directional_rows: list[dict[str, Any]] = []
    for source_bond_index in sorted(direction_by_bond_index):
        carrier = source_bonds[source_bond_index]
        token = "/" if direction_by_bond_index[source_bond_index] == 0 else "\\"
        token_by_pair[(carrier.atom_i, carrier.atom_j)] = token
        if source_bond_index == ring_closure_source_bond_index:
            emitted_from = ring_close_source_atom_index
            emitted_to = ring_open_source_atom_index
            carrier_emission_role = "ring_closure"
        elif parent_by_atom[carrier.atom_j] == carrier.atom_i:
            emitted_from = carrier.atom_i
            emitted_to = carrier.atom_j
            carrier_emission_role = "tree"
        elif parent_by_atom[carrier.atom_i] == carrier.atom_j:
            emitted_from = carrier.atom_j
            emitted_to = carrier.atom_i
            carrier_emission_role = "tree"
        else:  # pragma: no cover - selected carrier invariants above
            raise SmilesWriteError(
                "internal_emission_error",
                "direction carrier has no lexical emission orientation",
                location=f"bonds[{source_bond_index}]",
            )
        directional_rows.append(
            {
                "source_bond_index": source_bond_index,
                "atom_indices": [carrier.atom_i, carrier.atom_j],
                "bond_token": token,
                "emitted_from_source_atom_index": emitted_from,
                "emitted_to_source_atom_index": emitted_to,
                "emission_role": carrier_emission_role,
                "roles": [
                    {
                        "stereo_source_bond_index": stereo_bond_index,
                        "endpoint_role": endpoint_role,
                    }
                    for stereo_bond_index, endpoint_role in sorted(
                        carrier_roles[source_bond_index]
                    )
                ],
            }
        )

    token_by_source_bond_index = {
        row["source_bond_index"]: row["bond_token"] for row in directional_rows
    }
    for row in stereo_rows:
        row["direction_carrier_tokens"] = [
            token_by_source_bond_index[index]
            for index in row["direction_carrier_source_bond_indices"]
        ]

    projection: Mapping[str, Any] = {
        "schema_id": SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
        "profile_id": _EZ_STEREO_PROFILE_ID,
        "typed_ez_bond_count": len(typed_bonds),
        "directional_source_bond_count": len(direction_by_bond_index),
        "stereo_bond_table": stereo_rows,
        "directional_bond_table": directional_rows,
        "typed_atom_stereo_supported": False,
        "unknown_bond_stereo_supported": False,
        "ring_bond_ez_supported": True,
        "ring_bond_ez_scope": "selected_eight_member_unique_nonclosure_double_only",
        "selected_simple_ring_single_direction_carriers_supported": True,
        "selected_simple_ring_single_direction_carrier_scope": (
            "lexically_oriented_nonaromatic_three_through_eight_member_ring_edges"
        ),
        "independent_cip_assignment_claimed": False,
        "stereo_completeness_claimed": False,
        "stereo_geometry_claimed": False,
    }
    return (
        token_by_pair,
        projection,
        _sha256_document(projection),
        len(typed_bonds),
        len(direction_by_bond_index),
    )


def _build_tetrahedral_stereo_projection(
    *,
    system: AllAtomSystem,
    source_atom_count: int,
    source_bond_count: int,
    source_bonds: tuple[Bond, ...],
    source_atom_tokens: tuple[str, ...],
    source_component_roots: tuple[int, ...],
    source_children: tuple[tuple[int, ...], ...],
    source_parent_bond_tokens: tuple[str, ...],
    source_ring_marker_table: tuple[str, ...],
    parent_by_atom: tuple[int, ...],
    bracket_hydrogen_count_by_parent: tuple[int, ...],
    expected_generated_specs: tuple[tuple[int, str, int], ...],
) -> tuple[tuple[str, ...], Mapping[str, Any], str]:
    """Resolve lexical ``@``/``@@`` parity against parser-owned CW/CCW tags.

    The calibration is linear in the bounded graph size: one trial parse with
    ``@`` at every typed center, followed by one final parse after independently
    flipping centers whose local RDKit chiral tag differs.  The final parser
    check requires both the local tag and the attached R/S label, so this does
    not infer CIP or treat R/S as a fixed spelling marker.
    """

    typed_indices = tuple(
        atom.index
        for atom in system.atoms[:source_atom_count]
        if atom.stereo in {"R", "S"}
    )
    if not typed_indices:
        projection: Mapping[str, Any] = {
            "schema_id": SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID,
            "tetrahedral_stereo_profile_id": _TETRAHEDRAL_STEREO_PROFILE_ID,
            "typed_tetrahedral_atom_count": 0,
            "mapped_tetrahedral_atom_count": 0,
            "bracket_hydrogen_tetrahedral_atom_count": 0,
            "marker_flip_count": 0,
            "calibration_trial_parse_count": 0,
            "calibration_final_parse_count": 0,
            "atom_rows": [],
            "independent_cip_assignment": False,
            "stereo_completeness_assessed": False,
            "stereo_geometry_assessed": False,
        }
        return source_atom_tokens, projection, _sha256_document(projection)

    trial_payload = _emit_source_forest(
        source_atom_count=source_atom_count,
        source_atom_tokens=source_atom_tokens,
        source_component_roots=source_component_roots,
        source_children=source_children,
        source_parent_bond_tokens=source_parent_bond_tokens,
        source_ring_marker_table=source_ring_marker_table,
    )
    try:
        trial = parse_smiles(trial_payload, source_id="tetrahedral-parity-trial")
    except SmilesParseError as exc:
        raise SmilesWriteError(
            "tetrahedral_calibration_failed",
            "trial tetrahedral spelling did not survive the pinned parser",
        ) from exc
    if trial.system.metadata.get("source_atom_count") != source_atom_count:
        raise SmilesWriteError(
            "tetrahedral_calibration_failed",
            "trial tetrahedral spelling changed the source atom inventory",
        )

    final_tokens = list(source_atom_tokens)
    trial_rows: dict[int, tuple[str, str, str, bool]] = {}
    for atom_index in typed_indices:
        target = system.atoms[atom_index]
        observed = trial.system.atoms[atom_index]
        target_tag = target.metadata.get("rdkit_chiral_tag")
        observed_tag = observed.metadata.get("rdkit_chiral_tag")
        if (
            observed.stereo not in {"R", "S"}
            or observed_tag not in {"CHI_TETRAHEDRAL_CW", "CHI_TETRAHEDRAL_CCW"}
            or target_tag not in {"CHI_TETRAHEDRAL_CW", "CHI_TETRAHEDRAL_CCW"}
        ):
            raise SmilesWriteError(
                "tetrahedral_calibration_failed",
                "trial tetrahedral marker was not retained as exact parser-typed state",
                location=f"atoms[{atom_index}]",
            )
        flipped = observed_tag != target_tag
        final_marker = "@@" if flipped else "@"
        final_tokens[atom_index] = _source_atom_token(
            target,
            bracket_hydrogen_count=bracket_hydrogen_count_by_parent[atom_index],
            tetrahedral_marker=final_marker,
        )
        trial_rows[atom_index] = (
            observed.stereo,
            str(observed_tag),
            final_marker,
            flipped,
        )

    final_payload = _emit_source_forest(
        source_atom_count=source_atom_count,
        source_atom_tokens=tuple(final_tokens),
        source_component_roots=source_component_roots,
        source_children=source_children,
        source_parent_bond_tokens=source_parent_bond_tokens,
        source_ring_marker_table=source_ring_marker_table,
    )
    try:
        final = parse_smiles(final_payload, source_id="tetrahedral-parity-final")
    except SmilesParseError as exc:
        raise SmilesWriteError(
            "tetrahedral_calibration_failed",
            "resolved tetrahedral spelling did not survive the pinned parser",
        ) from exc
    if final.system.metadata.get("source_atom_count") != source_atom_count:
        raise SmilesWriteError(
            "tetrahedral_calibration_failed",
            "resolved tetrahedral spelling changed the source atom inventory",
        )

    source_incident_bonds_by_atom: list[list[Bond]] = [
        [] for _ in range(source_atom_count)
    ]
    for bond in source_bonds:
        source_incident_bonds_by_atom[bond.atom_i].append(bond)
        source_incident_bonds_by_atom[bond.atom_j].append(bond)
    bracket_rows_by_parent: list[list[tuple[int, tuple[int, str, int]]]] = [
        [] for _ in range(source_atom_count)
    ]
    for offset, spec in enumerate(expected_generated_specs):
        parent, origin, _ordinal = spec
        if origin == "bracket_explicit":
            bracket_rows_by_parent[parent].append((offset, spec))

    atom_rows: list[dict[str, Any]] = []
    marker_flip_count = 0
    for atom_index in typed_indices:
        target = system.atoms[atom_index]
        observed = final.system.atoms[atom_index]
        target_tag = target.metadata.get("rdkit_chiral_tag")
        observed_tag = observed.metadata.get("rdkit_chiral_tag")
        if observed.stereo != target.stereo or observed_tag != target_tag:
            raise SmilesWriteError(
                "tetrahedral_calibration_failed",
                "resolved tetrahedral spelling changed parser-owned R/S or CW/CCW state",
                location=f"atoms[{atom_index}]",
            )
        source_incident_bonds = tuple(source_incident_bonds_by_atom[atom_index])
        source_neighbor_indices = tuple(
            bond.atom_j if bond.atom_i == atom_index else bond.atom_i
            for bond in source_incident_bonds
        )
        bracket_rows = tuple(bracket_rows_by_parent[atom_index])
        if len(bracket_rows) != bracket_hydrogen_count_by_parent[atom_index]:
            raise SmilesWriteError(
                "tetrahedral_calibration_failed",
                "tetrahedral bracket-hydrogen projection is inconsistent",
                location=f"atoms[{atom_index}]",
            )
        trial_stereo, trial_tag, final_marker, flipped = trial_rows[atom_index]
        marker_flip_count += int(flipped)
        children = source_children[atom_index]
        parent = parent_by_atom[atom_index]
        closure_neighbors = tuple(
            neighbor
            for neighbor in source_neighbor_indices
            if neighbor != parent and neighbor not in children
        )
        atom_rows.append(
            {
                "source_atom_index": atom_index,
                "atom_map": target.atom_map,
                "target_stereo": target.stereo,
                "target_rdkit_chiral_tag": target_tag,
                "source_neighbor_indices_in_bond_order": list(source_neighbor_indices),
                "source_incident_bond_indices": [
                    bond.index for bond in source_incident_bonds
                ],
                "emitted_parent_source_atom_index": (None if parent < 0 else parent),
                "emitted_ring_closure_neighbor_indices": list(closure_neighbors),
                "emitted_branch_source_atom_indices": list(children[:-1]),
                "emitted_continuation_source_atom_index": (
                    children[-1] if children else None
                ),
                "source_ring_marker": source_ring_marker_table[atom_index],
                "bracket_explicit_hydrogen_count": (
                    bracket_hydrogen_count_by_parent[atom_index]
                ),
                "bracket_explicit_hydrogen_atom_indices": [
                    source_atom_count + offset for offset, _ in bracket_rows
                ],
                "bracket_explicit_hydrogen_bond_indices": [
                    source_bond_count + offset for offset, _ in bracket_rows
                ],
                "trial_marker": "@",
                "trial_stereo": trial_stereo,
                "trial_rdkit_chiral_tag": trial_tag,
                "final_marker": final_marker,
                "marker_flipped": flipped,
                "final_atom_token": final_tokens[atom_index],
                "final_stereo": observed.stereo,
                "final_rdkit_chiral_tag": observed_tag,
            }
        )

    projection = {
        "schema_id": SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID,
        "tetrahedral_stereo_profile_id": _TETRAHEDRAL_STEREO_PROFILE_ID,
        "typed_tetrahedral_atom_count": len(typed_indices),
        "mapped_tetrahedral_atom_count": sum(
            system.atoms[index].atom_map is not None for index in typed_indices
        ),
        "bracket_hydrogen_tetrahedral_atom_count": sum(
            bool(bracket_hydrogen_count_by_parent[index]) for index in typed_indices
        ),
        "marker_flip_count": marker_flip_count,
        "calibration_trial_parse_count": 1,
        "calibration_final_parse_count": 1,
        "atom_rows": atom_rows,
        "independent_cip_assignment": False,
        "stereo_completeness_assessed": False,
        "stereo_geometry_assessed": False,
    }
    return tuple(final_tokens), projection, _sha256_document(projection)


def _validate_atoms_and_graph(
    system: AllAtomSystem,
    *,
    source_atom_count: int,
) -> _ValidatedSourceForest:
    expanded_atom_count = system.atom_count
    generated_hydrogen_count = expanded_atom_count - source_atom_count
    if not 1 <= source_atom_count <= _MAX_SOURCE_ATOMS:
        raise SmilesWriteError(
            "unsupported_source_atom_count",
            "source atom count is outside the parser safety limit",
            location="metadata.source_atom_count",
        )
    if not source_atom_count <= expanded_atom_count <= _MAX_EXPANDED_ATOMS:
        raise SmilesWriteError(
            "unsupported_expanded_atom_count",
            "expanded atom count is outside the parser safety limit",
            location="atoms",
        )
    source_atom_tokens: list[str] = []
    charged_source_atom_count = 0
    mapped_source_atom_count = 0
    typed_tetrahedral_atom_count = 0
    formal_charge_total = 0
    expected_generated_specs: list[tuple[int, str, int]] = []
    implicit_hydrogen_count_by_parent = [0] * source_atom_count
    bracket_hydrogen_count_by_parent = [0] * source_atom_count
    next_implicit_ordinal_by_parent = [1] * source_atom_count
    next_bracket_ordinal_by_parent = [1] * source_atom_count
    for index, atom in enumerate(system.atoms):
        if type(atom) is not Atom:
            raise SmilesWriteError(
                "unsupported_atom_record_type",
                "all parser atoms must be exact Atom records",
                location=f"atoms[{index}]",
            )
        if atom.index != index:
            raise SmilesWriteError(
                "unsupported_atom_index",
                "atom indices must be contiguous source order",
                location=f"atoms[{index}].index",
            )
        location = f"atoms[{index}]"
        _validate_atom_common(atom, location=location)
        if index < source_atom_count:
            if (
                atom.element not in _SOURCE_ELEMENTS
                or atom.atomic_number != atomic_number_for_element(atom.element)
            ):
                raise SmilesWriteError(
                    "unsupported_element",
                    "source atoms must be non-hydrogen organic-subset elements",
                    location=f"{location}.element",
                )
            if (
                atom.formal_charge_known is not True
                or type(atom.formal_charge) is not int
                or atom.formal_charge not in _SOURCE_FORMAL_CHARGES
            ):
                raise SmilesWriteError(
                    "unsupported_formal_charge",
                    "source formal charge must be a known exact -1, 0, or +1",
                    location=f"{location}.formal_charge",
                )
            formal_charge_total += atom.formal_charge
            charged_source_atom_count += int(atom.formal_charge != 0)
            mapped_source_atom_count += int(atom.atom_map is not None)
            typed_tetrahedral_atom_count += int(atom.stereo in {"R", "S"})
            metadata = _require_exact_keys(
                atom.metadata,
                _SOURCE_ATOM_METADATA_KEYS,
                code="unsupported_source_atom_metadata",
                location=f"{location}.metadata",
            )
            chiral_tag = atom.metadata.get("rdkit_chiral_tag")
            expected_metadata = {
                "source_atom_index": index,
                "source_atom_order_preserved": True,
                "hydrogen_origin": "not_hydrogen",
                "formal_charge_source": "smiles_source_via_pinned_rdkit",
                "rdkit_chiral_tag": chiral_tag,
            }
            if (
                (atom.stereo == "UNSPECIFIED" and chiral_tag != "CHI_UNSPECIFIED")
                or (
                    atom.stereo in {"R", "S"}
                    and chiral_tag not in {"CHI_TETRAHEDRAL_CW", "CHI_TETRAHEDRAL_CCW"}
                )
                or not _exact_typed_structure_equal(metadata, expected_metadata)
            ):
                raise SmilesWriteError(
                    "unsupported_source_atom_metadata",
                    "source atom markers do not match parser-owned state",
                    location=f"{location}.metadata",
                )
            if (
                atom.name != f"{atom.element}{index + 1}"
                or atom.serial != index + 1
                or atom.stereo not in {"UNSPECIFIED", "R", "S"}
            ):
                raise SmilesWriteError(
                    "unsupported_source_atom_identity",
                    "source atom identity is not parser-synthesized state",
                    location=location,
                )
        else:
            if atom.formal_charge_known is not True or atom.formal_charge != 0:
                raise SmilesWriteError(
                    "unsupported_generated_hydrogen_formal_charge",
                    "generated hydrogens must carry known neutral formal charge",
                    location=f"{location}.formal_charge",
                )
            metadata = _require_exact_keys(
                atom.metadata,
                _GENERATED_HYDROGEN_METADATA_KEYS,
                code="unsupported_generated_hydrogen_metadata",
                location=f"{location}.metadata",
            )
            parent = metadata["parent_source_atom_index"]
            origin = metadata["hydrogen_origin"]
            ordinal = metadata["hydrogen_ordinal"]
            if type(parent) is not int or not 0 <= parent < source_atom_count:
                raise SmilesWriteError(
                    "invalid_generated_hydrogen_parent",
                    "generated hydrogen parent must be a source atom index",
                    location=f"{location}.metadata.parent_source_atom_index",
                )
            if type(origin) is not str or origin not in {
                "implicit",
                "bracket_explicit",
            }:
                raise SmilesWriteError(
                    "unsupported_generated_hydrogen_origin",
                    "generated hydrogens must retain an implicit or bracket-explicit parser origin",
                    location=f"{location}.metadata.hydrogen_origin",
                )
            if system.atoms[parent].formal_charge != 0 and origin == "implicit":
                raise SmilesWriteError(
                    "unsupported_charged_parent_hydrogen",
                    "charged source atoms may not own implicit hydrogens",
                    location=f"{location}.metadata.parent_source_atom_index",
                )
            expected_ordinal = (
                next_implicit_ordinal_by_parent[parent]
                if origin == "implicit"
                else next_bracket_ordinal_by_parent[parent]
            )
            expected_metadata = {
                "parent_source_atom_index": parent,
                "hydrogen_origin": origin,
                "hydrogen_ordinal": expected_ordinal,
                "manually_expanded": True,
                "formal_charge_source": "manual_hydrogen_expansion_neutral",
            }
            if type(ordinal) is not int or not _exact_typed_structure_equal(
                metadata, expected_metadata
            ):
                raise SmilesWriteError(
                    "inconsistent_generated_hydrogen_metadata",
                    "generated hydrogens must be parent-ascending with consecutive origin-local ordinals",
                    location=f"{location}.metadata",
                )
            if expected_generated_specs and parent < expected_generated_specs[-1][0]:
                raise SmilesWriteError(
                    "generated_hydrogen_order_changed",
                    "generated hydrogens must be grouped by ascending source parent",
                    location=location,
                )
            if (
                expected_generated_specs
                and parent == expected_generated_specs[-1][0]
                and origin == "bracket_explicit"
                and expected_generated_specs[-1][1] == "implicit"
            ):
                raise SmilesWriteError(
                    "generated_hydrogen_order_changed",
                    "bracket-explicit hydrogens must precede implicit hydrogens for one parent",
                    location=location,
                )
            if origin == "implicit":
                next_implicit_ordinal_by_parent[parent] += 1
                implicit_hydrogen_count_by_parent[parent] += 1
            else:
                next_bracket_ordinal_by_parent[parent] += 1
                bracket_hydrogen_count_by_parent[parent] += 1
            expected_generated_specs.append((parent, origin, ordinal))
            if (
                atom.element != "H"
                or atom.atomic_number != 1
                or atom.atom_map is not None
                or atom.name != f"H{index + 1}"
                or atom.serial != index + 1
                or atom.stereo != "unspecified"
            ):
                raise SmilesWriteError(
                    "unsupported_generated_hydrogen_identity",
                    "generated hydrogen identity is not parser-synthesized state",
                    location=location,
                )

    if len(expected_generated_specs) != generated_hydrogen_count:
        raise SmilesWriteError(
            "generated_hydrogen_count_mismatch",
            "generated hydrogen inventory is inconsistent",
            location="atoms",
        )
    if (
        typed_tetrahedral_atom_count
        and source_atom_count > _MAX_TETRAHEDRAL_CALIBRATION_SOURCE_ATOMS
    ):
        raise SmilesWriteError(
            "unsupported_tetrahedral_calibration_source_atom_count",
            "source atom count exceeds the tetrahedral calibration limit",
            location="metadata.source_atom_count",
        )
    source_bond_count = len(system.bonds) - generated_hydrogen_count
    if source_bond_count < 0 or len(system.bonds) > _MAX_BONDS:
        raise SmilesWriteError(
            "unsupported_bond_count",
            "expanded bond inventory cannot contain one generated bond per hydrogen",
            location="bonds",
        )

    full_adjacency: list[list[int]] = [[] for _ in range(source_atom_count)]
    source_pairs: set[tuple[int, int]] = set()
    source_bond_token_by_pair: dict[tuple[int, int], str] = {}
    source_bonds: list[Bond] = []
    for index, bond in enumerate(system.bonds):
        if type(bond) is not Bond:
            raise SmilesWriteError(
                "unsupported_bond_record_type",
                "all parser bonds must be exact Bond records",
                location=f"bonds[{index}]",
            )
        location = f"bonds[{index}]"
        if bond.index != index:
            raise SmilesWriteError(
                "unsupported_bond_index",
                "bond indices must be parser order",
                location=f"{location}.index",
            )
        if index < source_bond_count:
            if bond.stereo not in {"none", "E", "Z"}:
                raise SmilesWriteError(
                    "unsupported_bond_stereo",
                    "source bond stereo must be exact none, E, or Z",
                    location=f"{location}.stereo",
                )
            if type(bond.order) is not float or (
                (bond.aromatic and bond.order != 1.5)
                or (
                    not bond.aromatic
                    and bond.order not in _NONAROMATIC_SOURCE_BOND_TOKENS
                )
            ):
                raise SmilesWriteError(
                    "unsupported_bond",
                    "source bonds must be exact aromatic 1.5 or nonaromatic single, double, or triple bonds",
                    location=f"{location}.order",
                )
            metadata = _require_exact_keys(
                bond.metadata,
                _SOURCE_BOND_METADATA_KEYS,
                code="unsupported_source_bond_metadata",
                location=f"{location}.metadata",
            )
            stereo_atom_indices = bond.metadata.get("stereo_atom_indices")
            expected_stereo_atom_indices: list[int]
            if bond.stereo == "none":
                expected_stereo_atom_indices = []
            else:
                if bond.aromatic or bond.order != 2.0:
                    raise SmilesWriteError(
                        "unsupported_bond_stereo",
                        "E/Z state must belong to an exact nonaromatic double source bond",
                        location=f"{location}.stereo",
                    )
                if (
                    not isinstance(stereo_atom_indices, (list, tuple))
                    or len(stereo_atom_indices) != 2
                    or any(type(value) is not int for value in stereo_atom_indices)
                ):
                    raise SmilesWriteError(
                        "inconsistent_ez_stereo_atoms",
                        "E/Z source bond must retain exactly two integer stereo-neighbor indices",
                        location=f"{location}.metadata.stereo_atom_indices",
                    )
                expected_stereo_atom_indices = list(stereo_atom_indices)
            expected_metadata = {
                "source_bond_index": index,
                "stereo_atom_indices": expected_stereo_atom_indices,
            }
            if (
                bond.source != "smiles_source"
                or not _exact_typed_structure_equal(metadata, expected_metadata)
                or not 0 <= bond.atom_i < bond.atom_j < source_atom_count
            ):
                raise SmilesWriteError(
                    "inconsistent_source_bond_state",
                    "source bond identity or metadata is not parser-shaped",
                    location=location,
                )
            pair = (bond.atom_i, bond.atom_j)
            if pair in source_pairs:
                raise SmilesWriteError(
                    "duplicate_source_bond",
                    "source graph contains a duplicate edge",
                    location=location,
                )
            source_pairs.add(pair)
            source_bonds.append(bond)
            source_bond_token_by_pair[pair] = _SOURCE_BOND_TOKENS[bond.order]
            full_adjacency[bond.atom_i].append(bond.atom_j)
            full_adjacency[bond.atom_j].append(bond.atom_i)
        else:
            if bond.stereo != "none":
                raise SmilesWriteError(
                    "unsupported_bond_stereo",
                    "parser-generated hydrogen bonds cannot carry typed stereochemistry",
                    location=f"{location}.stereo",
                )
            if type(bond.order) is not float or bond.order != 1.0 or bond.aromatic:
                raise SmilesWriteError(
                    "unsupported_bond",
                    "parser-generated hydrogen bonds must remain exact single bonds",
                    location=f"{location}.order",
                )
            offset = index - source_bond_count
            hydrogen_index = source_atom_count + offset
            parent, origin, ordinal = expected_generated_specs[offset]
            metadata = _require_exact_keys(
                bond.metadata,
                _GENERATED_BOND_METADATA_KEYS,
                code="unsupported_generated_bond_metadata",
                location=f"{location}.metadata",
            )
            expected_metadata = {
                "parent_source_atom_index": parent,
                "hydrogen_origin": origin,
                "hydrogen_ordinal": ordinal,
            }
            if (
                bond.source != "manual_hydrogen_expansion"
                or (bond.atom_i, bond.atom_j) != tuple(sorted((parent, hydrogen_index)))
                or not _exact_typed_structure_equal(metadata, expected_metadata)
            ):
                raise SmilesWriteError(
                    "inconsistent_generated_hydrogen_bond",
                    "generated hydrogen bond does not match its atom marker",
                    location=location,
                )

    # Partition source edges once, in parser bond order.  The parser appends a
    # ring-closure edge after every ordinary source edge, so the one accepted
    # non-tree edge is both graph-derived and spelling-order constrained.
    dsu_parent = list(range(source_atom_count))
    dsu_rank = [0] * source_atom_count

    def dsu_find(atom_index: int) -> int:
        root = atom_index
        while dsu_parent[root] != root:
            root = dsu_parent[root]
        while dsu_parent[atom_index] != atom_index:
            next_index = dsu_parent[atom_index]
            dsu_parent[atom_index] = root
            atom_index = next_index
        return root

    source_tree_bond_indices: list[int] = []
    source_non_tree_bond_indices: list[int] = []
    for bond in source_bonds:
        left_root = dsu_find(bond.atom_i)
        right_root = dsu_find(bond.atom_j)
        if left_root == right_root:
            source_non_tree_bond_indices.append(bond.index)
            continue
        if dsu_rank[left_root] < dsu_rank[right_root]:
            left_root, right_root = right_root, left_root
        dsu_parent[right_root] = left_root
        if dsu_rank[left_root] == dsu_rank[right_root]:
            dsu_rank[left_root] += 1
        source_tree_bond_indices.append(bond.index)

    ring_closure_count = len(source_non_tree_bond_indices)
    if ring_closure_count > _MAX_RING_COMPONENTS:
        raise SmilesWriteError(
            "unsupported_source_cycle_rank",
            "source graph may contain at most one independent cycle",
            location="bonds",
        )
    if (
        ring_closure_count == 1
        and source_non_tree_bond_indices[0] != source_bond_count - 1
    ):
        raise SmilesWriteError(
            "unsupported_ring_closure_order",
            "the unique ring closure must be the final source bond",
            location=f"bonds[{source_non_tree_bond_indices[0]}]",
        )

    tree_bond_index_set = frozenset(source_tree_bond_indices)
    forest_adjacency: list[list[int]] = [[] for _ in range(source_atom_count)]
    for bond in source_bonds:
        if bond.index not in tree_bond_index_set:
            continue
        forest_adjacency[bond.atom_i].append(bond.atom_j)
        forest_adjacency[bond.atom_j].append(bond.atom_i)

    visited = [False] * source_atom_count
    parent_by_atom = [-1] * source_atom_count
    component_by_source_atom = [-1] * source_atom_count
    source_component_roots: list[int] = []
    for start in range(source_atom_count):
        if visited[start]:
            continue
        if len(source_component_roots) >= _MAX_FRAGMENTS:
            raise SmilesWriteError(
                "unsupported_fragment_count",
                "source graph exceeds the fixed writer fragment limit",
                location="bonds",
            )
        component_index = len(source_component_roots)
        source_component_roots.append(start)
        visited[start] = True
        stack = [start]
        while stack:
            current = stack.pop()
            component_by_source_atom[current] = component_index
            for neighbor in forest_adjacency[current]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    parent_by_atom[neighbor] = current
                    stack.append(neighbor)

    fragment_count = len(source_component_roots)
    if not 1 <= fragment_count <= min(_MAX_FRAGMENTS, source_atom_count):
        raise SmilesWriteError(
            "unsupported_fragment_count",
            "source graph fragment count is outside the writer limit",
            location="bonds",
        )

    source_component_members: list[list[int]] = [[] for _ in range(fragment_count)]
    for atom_index, component_index in enumerate(component_by_source_atom):
        if not 0 <= component_index < fragment_count:
            raise SmilesWriteError(
                "unsupported_source_tree",
                "source graph component assignment is incomplete",
                location="bonds",
            )
        source_component_members[component_index].append(atom_index)
    source_components = tuple(
        tuple(component) for component in source_component_members
    )
    source_tree_edge_count = source_atom_count - fragment_count
    if len(source_tree_bond_indices) != source_tree_edge_count:
        raise SmilesWriteError(
            "unsupported_source_graph",
            "source tree-edge inventory is inconsistent with graph components",
            location="bonds",
        )
    if source_bond_count != source_tree_edge_count + ring_closure_count:
        raise SmilesWriteError(
            "unsupported_source_graph",
            "source bond inventory is inconsistent with global cycle rank",
            location="bonds",
        )
    if len(system.bonds) != expanded_atom_count - fragment_count + ring_closure_count:
        raise SmilesWriteError(
            "unsupported_bond_count",
            "expanded bond inventory is inconsistent with the supported graph",
            location="bonds",
        )

    component_edge_counts = [0] * fragment_count
    for bond in source_bonds:
        component_index = component_by_source_atom[bond.atom_i]
        if component_index != component_by_source_atom[bond.atom_j]:
            raise SmilesWriteError(
                "unsupported_source_graph",
                "source bond crosses graph-derived components",
                location=f"bonds[{bond.index}]",
            )
        component_edge_counts[component_index] += 1
    component_cyclomatic_numbers = tuple(
        component_edge_counts[index] - len(source_components[index]) + 1
        for index in range(fragment_count)
    )
    if (
        any(
            type(rank) is not int or rank not in (0, 1)
            for rank in component_cyclomatic_numbers
        )
        or sum(component_cyclomatic_numbers) != ring_closure_count
    ):
        raise SmilesWriteError(
            "unsupported_source_cycle_rank",
            "component cyclomatic numbers are outside the zero-or-one contract",
            location="bonds",
        )
    cyclic_component_indices = tuple(
        index for index, rank in enumerate(component_cyclomatic_numbers) if rank == 1
    )
    cyclic_component_count = len(cyclic_component_indices)
    if cyclic_component_count != ring_closure_count:
        raise SmilesWriteError(
            "unsupported_source_cycle_rank",
            "exactly one component must own the unique closure",
            location="bonds",
        )

    cyclic_component_index: int | None = None
    ring_size = 0
    ring_atom_indices: tuple[int, ...] = ()
    ring_bond_indices: tuple[int, ...] = ()
    ring_closure_source_bond_index: int | None = None
    ring_closure_endpoints: tuple[int, ...] = ()
    ring_open_source_atom_index: int | None = None
    ring_close_source_atom_index: int | None = None
    cycle_profile_id = _ALL_SINGLE_CYCLE_PROFILE_ID
    ring_bond_profile_id: str | None = None
    ring_double_bond_count = 0
    ring_double_source_bond_index: int | None = None
    aromatic_source_atom_count = 0
    aromatic_source_bond_count = 0
    aromatic_ring_profile_id: str | None = None
    aromatic_atom_state_profile_id: str | None = None
    ring_bond_order_table: tuple[
        tuple[int, tuple[int, int], str, bool, str, str, str], ...
    ] = ()
    source_ring_marker_table = [""] * source_atom_count
    ring_atom_set: frozenset[int] = frozenset()
    if ring_closure_count == 1:
        cyclic_component_index = cyclic_component_indices[0]
        component_atoms = source_components[cyclic_component_index]
        component_atom_set = frozenset(component_atoms)
        degree = [0] * source_atom_count
        for atom_index in component_atoms:
            degree[atom_index] = sum(
                neighbor in component_atom_set
                for neighbor in full_adjacency[atom_index]
            )
        peel_queue = [
            atom_index for atom_index in component_atoms if degree[atom_index] < 2
        ]
        removed = [False] * source_atom_count
        queue_offset = 0
        while queue_offset < len(peel_queue):
            atom_index = peel_queue[queue_offset]
            queue_offset += 1
            if removed[atom_index]:
                continue
            removed[atom_index] = True
            for neighbor in full_adjacency[atom_index]:
                if neighbor not in component_atom_set or removed[neighbor]:
                    continue
                degree[neighbor] -= 1
                if degree[neighbor] == 1:
                    peel_queue.append(neighbor)
        ring_atom_indices = tuple(
            atom_index for atom_index in component_atoms if not removed[atom_index]
        )
        ring_atom_set = frozenset(ring_atom_indices)
        ring_bond_records = tuple(
            bond
            for bond in source_bonds
            if bond.atom_i in ring_atom_set and bond.atom_j in ring_atom_set
        )
        ring_bond_indices = tuple(sorted(bond.index for bond in ring_bond_records))
        ring_size = len(ring_atom_indices)
        if not _MIN_RING_SIZE <= ring_size <= _MAX_RING_SIZE:
            raise SmilesWriteError(
                "unsupported_ring_size",
                "simple source ring size must be between three and eight atoms",
                location="bonds",
            )
        if len(ring_bond_records) != ring_size or any(
            sum(neighbor in ring_atom_set for neighbor in full_adjacency[atom_index])
            != 2
            for atom_index in ring_atom_indices
        ):
            raise SmilesWriteError(
                "unsupported_simple_cycle",
                "the unique source 2-core must be one dependency-free simple cycle",
                location="bonds",
            )
        ring_closure_source_bond_index = source_non_tree_bond_indices[0]
        closure_bond = source_bonds[ring_closure_source_bond_index]
        if closure_bond.index not in ring_bond_indices:
            raise SmilesWriteError(
                "unsupported_simple_cycle",
                "the unique non-tree edge must belong to the simple ring",
                location=f"bonds[{closure_bond.index}]",
            )
        ring_tree_bond_records = tuple(
            bond
            for bond in ring_bond_records
            if bond.index != ring_closure_source_bond_index
        )
        aromatic_atom_indices = tuple(
            atom.index for atom in system.atoms[:source_atom_count] if atom.aromatic
        )
        aromatic_bond_records = tuple(bond for bond in source_bonds if bond.aromatic)
        aromatic_state_present = bool(aromatic_atom_indices or aromatic_bond_records)
        if aromatic_state_present:
            if not _MIN_AROMATIC_RING_SIZE <= ring_size <= _MAX_AROMATIC_RING_SIZE:
                raise SmilesWriteError(
                    "unsupported_aromatic_ring_size",
                    "the selected fully aromatic source ring must have five or six atoms",
                    location="bonds",
                )
            if (
                frozenset(aromatic_atom_indices) != ring_atom_set
                or frozenset(bond.index for bond in aromatic_bond_records)
                != frozenset(ring_bond_indices)
                or any(
                    bond.order != 1.5 or bond.aromatic is not True
                    for bond in ring_bond_records
                )
            ):
                raise SmilesWriteError(
                    "unsupported_aromatic_ring_state",
                    "selected aromatic state requires every and only simple-ring atom and bond to be aromatic with exact order 1.5",
                    location="bonds",
                )
            cycle_profile_id = _AROMATIC_CYCLE_PROFILE_ID
            ring_bond_profile_id = _AROMATIC_RING_BOND_PROFILE_ID
            aromatic_ring_profile_id = _AROMATIC_CYCLE_PROFILE_ID
            aromatic_atom_state_profile_id = _AROMATIC_ATOM_STATE_PROFILE_ID
            aromatic_source_atom_count = ring_size
            aromatic_source_bond_count = ring_size
        else:
            if type(closure_bond.order) is not float or closure_bond.order != 1.0:
                raise SmilesWriteError(
                    "unsupported_ring_closure_bond",
                    "the canonical nonaromatic ring closure must remain an exact single bond",
                    location=f"bonds[{closure_bond.index}]",
                )
            if any(bond.order == 3.0 for bond in ring_tree_bond_records):
                raise SmilesWriteError(
                    "unsupported_ring_multiple_bond_order",
                    "the bounded simple nonaromatic ring does not admit a triple edge",
                    location="bonds",
                )
            double_ring_bonds = tuple(
                bond for bond in ring_tree_bond_records if bond.order == 2.0
            )
            if len(double_ring_bonds) > 1:
                raise SmilesWriteError(
                    "unsupported_ring_multiple_bond_count",
                    "the bounded simple nonaromatic ring admits at most one non-closure double edge",
                    location="bonds",
                )
            ring_double_bond_count = len(double_ring_bonds)
            if double_ring_bonds:
                ring_double_source_bond_index = double_ring_bonds[0].index
                cycle_profile_id = _ONE_DOUBLE_CYCLE_PROFILE_ID
                ring_bond_profile_id = _ONE_DOUBLE_RING_BOND_PROFILE_ID
            else:
                ring_bond_profile_id = _ALL_SINGLE_RING_BOND_PROFILE_ID
        ring_bond_order_table = tuple(
            (
                bond.index,
                (bond.atom_i, bond.atom_j),
                struct.pack(">d", bond.order).hex(),
                bond.aromatic,
                _SOURCE_BOND_TOKENS[bond.order],
                bond.stereo,
                ("closure" if bond.index == ring_closure_source_bond_index else "tree"),
            )
            for bond in sorted(ring_bond_records, key=lambda record: record.index)
        )
        ring_closure_endpoints = (closure_bond.atom_i, closure_bond.atom_j)
        ring_open_source_atom_index, ring_close_source_atom_index = (
            ring_closure_endpoints
        )
        source_ring_marker_table[ring_open_source_atom_index] = "1"
        source_ring_marker_table[ring_close_source_atom_index] = "1"

    if ring_closure_count == 0 and (
        any(atom.aromatic for atom in system.atoms[:source_atom_count])
        or any(bond.aromatic for bond in source_bonds)
    ):
        raise SmilesWriteError(
            "unsupported_aromatic_ring_state",
            "aromatic source state requires exactly one selected simple ring",
            location="bonds",
        )

    for atom_index, atom in enumerate(system.atoms[:source_atom_count]):
        implicit_count = implicit_hydrogen_count_by_parent[atom_index]
        bracket_count = bracket_hydrogen_count_by_parent[atom_index]
        typed_tetrahedral = atom.stereo in {"R", "S"}
        if atom.aromatic:
            if typed_tetrahedral:
                raise SmilesWriteError(
                    "unsupported_atom_stereo",
                    "typed tetrahedral atoms must be nonaromatic",
                    location=f"atoms[{atom_index}]",
                )
            if (
                atom_index not in ring_atom_set
                or atom.element not in _AROMATIC_SOURCE_ELEMENTS
            ):
                raise SmilesWriteError(
                    "unsupported_aromatic_atom_state",
                    "aromatic source atoms must belong to the selected B/C/N/O/P/S ring",
                    location=f"atoms[{atom_index}]",
                )
            if implicit_count not in (
                {0, 1}
                if atom.element == "C"
                and atom.formal_charge == 0
                and bracket_count == 0
                else {0}
            ):
                raise SmilesWriteError(
                    "unsupported_aromatic_hydrogen_state",
                    "aromatic source implicit hydrogen state is outside the finite token profile",
                    location=f"atoms[{atom_index}]",
                )
        else:
            if bracket_count and not typed_tetrahedral:
                raise SmilesWriteError(
                    "unsupported_bracket_hydrogen",
                    "bracket-explicit hydrogens require a selected aromatic or typed tetrahedral source atom",
                    location=f"atoms[{atom_index}]",
                )
            if atom.formal_charge != 0 and implicit_count:
                raise SmilesWriteError(
                    "unsupported_charged_parent_hydrogen",
                    "charged nonaromatic source atoms may not own implicit hydrogens",
                    location=f"atoms[{atom_index}]",
                )
            if typed_tetrahedral:
                source_neighbors = tuple(full_adjacency[atom_index])
                if (
                    implicit_count != 0
                    or bracket_count not in {0, 1}
                    or len(source_neighbors) + bracket_count != 4
                ):
                    raise SmilesWriteError(
                        "unsupported_tetrahedral_ligand_inventory",
                        "typed tetrahedral atoms require four source-or-bracket-hydrogen ligands and no implicit hydrogen",
                        location=f"atoms[{atom_index}]",
                    )
                incident_bonds = tuple(
                    bond
                    for bond in source_bonds
                    if atom_index in {bond.atom_i, bond.atom_j}
                )
                if len(incident_bonds) != len(source_neighbors) or any(
                    bond.order != 1.0 or bond.aromatic or bond.stereo != "none"
                    for bond in incident_bonds
                ):
                    raise SmilesWriteError(
                        "unsupported_tetrahedral_bond_state",
                        "typed tetrahedral atoms require exact nonaromatic stereo-free single incident source bonds",
                        location=f"atoms[{atom_index}]",
                    )
        source_atom_tokens.append(
            _source_atom_token(
                atom,
                bracket_hydrogen_count=bracket_count,
                tetrahedral_marker="@" if typed_tetrahedral else None,
            )
        )

    (
        source_bond_token_by_pair,
        ez_stereo_projection_document,
        ez_stereo_projection_sha256,
        typed_ez_bond_count,
        directional_source_bond_count,
    ) = _build_ez_direction_projection(
        source_bonds=tuple(source_bonds),
        parent_by_atom=tuple(parent_by_atom),
        ring_bond_indices=ring_bond_indices,
        ring_size=ring_size,
        ring_closure_source_bond_index=ring_closure_source_bond_index,
        ring_double_source_bond_index=ring_double_source_bond_index,
        ring_open_source_atom_index=ring_open_source_atom_index,
        ring_close_source_atom_index=ring_close_source_atom_index,
        source_bond_token_by_pair=source_bond_token_by_pair,
    )

    if (
        ring_closure_source_bond_index is not None
        and ring_close_source_atom_index is not None
    ):
        closure_bond = source_bonds[ring_closure_source_bond_index]
        closure_token = source_bond_token_by_pair[
            (closure_bond.atom_i, closure_bond.atom_j)
        ]
        if closure_token in {"/", "\\"}:
            source_ring_marker_table[ring_close_source_atom_index] = f"{closure_token}1"

    if ring_double_source_bond_index is not None and source_bonds[
        ring_double_source_bond_index
    ].stereo in {"E", "Z"}:
        cycle_profile_id = _ONE_DOUBLE_EZ_CYCLE_PROFILE_ID
        ring_bond_profile_id = _ONE_DOUBLE_EZ_RING_BOND_PROFILE_ID

    if ring_bond_order_table:
        ring_bond_order_table = tuple(
            (
                source_bond_index,
                atom_indices,
                order_hex,
                aromatic,
                source_bond_token_by_pair[atom_indices],
                stereo,
                role,
            )
            for source_bond_index, atom_indices, order_hex, aromatic, _bond_token, stereo, role in ring_bond_order_table
        )

    implicit_hydrogen_count = sum(implicit_hydrogen_count_by_parent)
    bracket_explicit_hydrogen_count = sum(bracket_hydrogen_count_by_parent)
    aromatic_bracket_hydrogen_rows = tuple(
        (offset, parent, origin, ordinal)
        for offset, (parent, origin, ordinal) in enumerate(expected_generated_specs)
        if (
            aromatic_source_atom_count
            and origin == "bracket_explicit"
            and parent in ring_atom_set
            and system.atoms[parent].aromatic
        )
    )
    aromatic_projection_document: Mapping[str, Any] = {
        "schema_id": SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID,
        "aromatic_ring_profile_id": aromatic_ring_profile_id,
        "aromatic_atom_state_profile_id": aromatic_atom_state_profile_id,
        "cyclic_component_index": (
            cyclic_component_index if aromatic_source_atom_count else None
        ),
        "ring_size": ring_size if aromatic_source_atom_count else 0,
        "aromatic_source_atom_count": aromatic_source_atom_count,
        "aromatic_source_bond_count": aromatic_source_bond_count,
        "aromatic_bracket_explicit_hydrogen_count": len(aromatic_bracket_hydrogen_rows),
        "aromatic_implicit_hydrogen_count": (
            sum(implicit_hydrogen_count_by_parent[index] for index in ring_atom_indices)
            if aromatic_source_atom_count
            else 0
        ),
        "aromatic_formal_charge_count": (
            sum(system.atoms[index].formal_charge != 0 for index in ring_atom_indices)
            if aromatic_source_atom_count
            else 0
        ),
        "aromatic_formal_charge_total": (
            sum(system.atoms[index].formal_charge for index in ring_atom_indices)
            if aromatic_source_atom_count
            else 0
        ),
        "ring_atom_state_table": [
            {
                "source_atom_index": atom_index,
                "element": system.atoms[atom_index].element,
                "atomic_number": system.atoms[atom_index].atomic_number,
                "formal_charge": system.atoms[atom_index].formal_charge,
                "formal_charge_known": system.atoms[atom_index].formal_charge_known,
                "aromatic": system.atoms[atom_index].aromatic,
                "implicit_hydrogen_count": (
                    implicit_hydrogen_count_by_parent[atom_index]
                ),
                "bracket_explicit_hydrogen_count": (
                    bracket_hydrogen_count_by_parent[atom_index]
                ),
                "atom_token": source_atom_tokens[atom_index],
            }
            for atom_index in ring_atom_indices
        ]
        if aromatic_source_atom_count
        else [],
        "ring_bond_state_table": [
            {
                "source_bond_index": source_bond_index,
                "atom_indices": list(atom_indices),
                "order_ieee754_binary64_be": order_hex,
                "aromatic": aromatic,
                "bond_token": bond_token,
                "stereo": stereo,
                "role": role,
            }
            for source_bond_index, atom_indices, order_hex, aromatic, bond_token, stereo, role in ring_bond_order_table
        ]
        if aromatic_source_bond_count
        else [],
        "bracket_hydrogen_table": [
            {
                "generated_atom_index": source_atom_count + offset,
                "parent_source_atom_index": parent,
                "hydrogen_origin": origin,
                "hydrogen_ordinal": ordinal,
                "generated_bond_index": source_bond_count + offset,
            }
            for offset, parent, origin, ordinal in aromatic_bracket_hydrogen_rows
        ],
    }
    aromatic_projection_sha256 = _sha256_document(aromatic_projection_document)

    cycle_projection_document: Mapping[str, Any] = {
        "schema_id": SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID,
        "cycle_profile_id": cycle_profile_id,
        "source_bond_count": source_bond_count,
        "source_tree_edge_count": source_tree_edge_count,
        "source_tree_bond_indices": sorted(source_tree_bond_indices),
        "source_non_tree_bond_indices": sorted(source_non_tree_bond_indices),
        "component_cyclomatic_numbers": list(component_cyclomatic_numbers),
        "cyclic_component_count": cyclic_component_count,
        "cyclic_component_index": cyclic_component_index,
        "ring_closure_count": ring_closure_count,
        "ring_size": ring_size,
        "ring_atom_indices": list(ring_atom_indices),
        "ring_bond_indices": list(ring_bond_indices),
        "ring_closure_source_bond_index": ring_closure_source_bond_index,
        "ring_closure_endpoints": list(ring_closure_endpoints),
        "ring_open_source_atom_index": ring_open_source_atom_index,
        "ring_close_source_atom_index": ring_close_source_atom_index,
        "ring_closure_label": 1 if ring_closure_count else None,
        "ring_bond_profile_id": ring_bond_profile_id,
        "ring_double_bond_count": ring_double_bond_count,
        "ring_double_source_bond_index": ring_double_source_bond_index,
        "aromatic_projection_schema_id": SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID,
        "aromatic_ring_profile_id": aromatic_ring_profile_id,
        "aromatic_atom_state_profile_id": aromatic_atom_state_profile_id,
        "aromatic_source_atom_count": aromatic_source_atom_count,
        "aromatic_source_bond_count": aromatic_source_bond_count,
        "aromatic_projection_sha256": aromatic_projection_sha256,
        "ring_bond_order_table": [
            {
                "source_bond_index": source_bond_index,
                "atom_indices": list(atom_indices),
                "order_ieee754_binary64_be": order_hex,
                "aromatic": aromatic,
                "bond_token": bond_token,
                "stereo": stereo,
                "role": role,
            }
            for source_bond_index, atom_indices, order_hex, aromatic, bond_token, stereo, role in ring_bond_order_table
        ],
        "source_ring_marker_table": list(source_ring_marker_table),
    }
    cycle_projection_sha256 = _sha256_document(cycle_projection_document)

    children: list[list[int]] = [[] for _ in range(source_atom_count)]
    source_parent_bond_tokens = [""] * source_atom_count
    roots = frozenset(source_component_roots)
    for atom_index in range(source_atom_count):
        parent = parent_by_atom[atom_index]
        if atom_index in roots:
            if parent != -1:
                raise SmilesWriteError(
                    "unsupported_source_tree",
                    "source component root unexpectedly has a parent",
                    location="bonds",
                )
            continue
        if parent < 0:
            raise SmilesWriteError(
                "unsupported_source_tree",
                "source graph parent assignment is incomplete",
                location="bonds",
            )
        children[parent].append(atom_index)
        pair = tuple(sorted((parent, atom_index)))
        if pair not in source_bond_token_by_pair:
            raise SmilesWriteError(
                "inconsistent_source_bond_state",
                "source graph parent edge is missing its bond token",
                location="bonds",
            )
        source_parent_bond_tokens[atom_index] = source_bond_token_by_pair[pair]

    (
        resolved_source_atom_tokens,
        tetrahedral_stereo_projection_document,
        tetrahedral_stereo_projection_sha256,
    ) = _build_tetrahedral_stereo_projection(
        system=system,
        source_atom_count=source_atom_count,
        source_bond_count=source_bond_count,
        source_bonds=tuple(source_bonds),
        source_atom_tokens=tuple(source_atom_tokens),
        source_component_roots=tuple(source_component_roots),
        source_children=tuple(tuple(values) for values in children),
        source_parent_bond_tokens=tuple(source_parent_bond_tokens),
        source_ring_marker_table=tuple(source_ring_marker_table),
        parent_by_atom=tuple(parent_by_atom),
        bracket_hydrogen_count_by_parent=tuple(bracket_hydrogen_count_by_parent),
        expected_generated_specs=tuple(expected_generated_specs),
    )
    source_atom_tokens = list(resolved_source_atom_tokens)

    expanded_components = [list(component) for component in source_components]
    for atom_index in range(source_atom_count):
        expected_residue_index = component_by_source_atom[atom_index]
        if system.atoms[atom_index].residue_index != expected_residue_index:
            raise SmilesWriteError(
                "unsupported_source_atom_identity",
                "source atom residue index does not match its graph-derived component",
                location=f"atoms[{atom_index}].residue_index",
            )
    for offset, (parent, _origin, _ordinal) in enumerate(expected_generated_specs):
        hydrogen_index = source_atom_count + offset
        expected_residue_index = component_by_source_atom[parent]
        if system.atoms[hydrogen_index].residue_index != expected_residue_index:
            raise SmilesWriteError(
                "unsupported_generated_hydrogen_identity",
                "generated hydrogen residue index does not match its parent component",
                location=f"atoms[{hydrogen_index}].residue_index",
            )
        expanded_components[expected_residue_index].append(hydrogen_index)

    return _ValidatedSourceForest(
        generated_hydrogen_count,
        implicit_hydrogen_count,
        bracket_explicit_hydrogen_count,
        mapped_source_atom_count,
        typed_tetrahedral_atom_count,
        fragment_count,
        charged_source_atom_count,
        formal_charge_total,
        tuple(source_atom_tokens),
        tuple(source_component_roots),
        source_components,
        tuple(tuple(component) for component in expanded_components),
        tuple(tuple(values) for values in children),
        tuple(source_parent_bond_tokens),
        tuple(source_ring_marker_table),
        source_bond_count,
        source_tree_edge_count,
        component_cyclomatic_numbers,
        ring_closure_count,
        cyclic_component_count,
        cyclic_component_index,
        ring_size,
        ring_atom_indices,
        ring_bond_indices,
        ring_closure_source_bond_index,
        ring_closure_endpoints,
        ring_open_source_atom_index,
        ring_close_source_atom_index,
        cycle_profile_id,
        ring_bond_profile_id,
        ring_double_bond_count,
        ring_double_source_bond_index,
        aromatic_source_atom_count,
        aromatic_source_bond_count,
        aromatic_ring_profile_id,
        aromatic_atom_state_profile_id,
        typed_ez_bond_count,
        directional_source_bond_count,
        _EZ_STEREO_PROFILE_ID,
        ring_bond_order_table,
        cycle_projection_document,
        cycle_projection_sha256,
        aromatic_projection_document,
        aromatic_projection_sha256,
        ez_stereo_projection_document,
        ez_stereo_projection_sha256,
        _TETRAHEDRAL_STEREO_PROFILE_ID,
        tetrahedral_stereo_projection_document,
        tetrahedral_stereo_projection_sha256,
    )


def _validate_parser_context(
    system: AllAtomSystem,
    *,
    expanded_components: tuple[tuple[int, ...], ...],
) -> None:
    fragment_count = len(expanded_components)
    if len(system.residues) != fragment_count:
        raise SmilesWriteError(
            "unsupported_residue_context",
            "strict SMILES state requires one parser residue per graph component",
            location="residues",
        )
    for index, (residue, expanded_component) in enumerate(
        zip(system.residues, expanded_components, strict=True)
    ):
        expected_label = f"L{index + 1}"
        if type(residue) is not Residue or not (
            residue.index == index
            and residue.name == expected_label
            and residue.chain_index == index
            and residue.sequence_number == 1
            and residue.atom_indices == expanded_component
            and residue.insertion_code == ""
            and residue.entity_type == "non_polymer"
            and residue.hetero is True
            and _exact_typed_structure_equal(
                residue.metadata, {"graph_component_index": index}
            )
        ):
            raise SmilesWriteError(
                "unsupported_residue_context",
                "residue does not match its graph-derived parser component",
                location=f"residues[{index}]",
            )

    if len(system.chains) != fragment_count:
        raise SmilesWriteError(
            "unsupported_chain_context",
            "strict SMILES state requires one parser chain per graph component",
            location="chains",
        )
    for index, chain in enumerate(system.chains):
        expected_label = f"L{index + 1}"
        if type(chain) is not Chain or not (
            chain.index == index
            and chain.chain_id == expected_label
            and chain.residue_indices == (index,)
            and chain.entity_id == expected_label
            and _exact_typed_structure_equal(
                chain.metadata, {"graph_component_index": index}
            )
        ):
            raise SmilesWriteError(
                "unsupported_chain_context",
                "chain does not match its graph-derived parser component",
                location=f"chains[{index}]",
            )


def _atom_document(atom: Atom) -> dict[str, Any]:
    metadata = dict(atom.metadata)
    return {
        "index": atom.index,
        "name": atom.name,
        "element": atom.element,
        "atomic_number": atom.atomic_number,
        "residue_index": atom.residue_index,
        "formal_charge": atom.formal_charge,
        "formal_charge_known": atom.formal_charge_known,
        "partial_charge_e": atom.partial_charge_e,
        "mass_da": atom.mass_da,
        "isotope_mass_number": atom.isotope_mass_number,
        "serial": atom.serial,
        "atom_map": atom.atom_map,
        "altloc": atom.altloc,
        "occupancy": atom.occupancy,
        "b_factor": atom.b_factor,
        "aromatic": atom.aromatic,
        "stereo": atom.stereo,
        "metadata": metadata,
    }


def _bond_document(bond: Bond) -> dict[str, Any]:
    metadata = dict(bond.metadata)
    stereo_atom_indices = metadata.get("stereo_atom_indices")
    if isinstance(stereo_atom_indices, (list, tuple)):
        metadata["stereo_atom_indices"] = list(stereo_atom_indices)
    return {
        "index": bond.index,
        "atom_i": bond.atom_i,
        "atom_j": bond.atom_j,
        "order_ieee754_binary64_be": struct.pack(">d", bond.order).hex(),
        "aromatic": bond.aromatic,
        "stereo": bond.stereo,
        "source": bond.source,
        "metadata": metadata,
    }


def _validate_write_state(system: AllAtomSystem) -> _ValidatedWriteState:
    _preflight_snapshot_carrier(system)
    if system.cell is not None:
        raise SmilesWriteError(
            "unsupported_cell",
            "SMILES writer does not preserve unit-cell state",
            location="cell",
        )
    snapshot = _snapshot_parser_system(system)
    if snapshot.schema_id != ALL_ATOM_SCHEMA_ID:
        raise SmilesWriteError(
            "unsupported_system_schema",
            "writer requires the current all-atom schema",
            location="schema_id",
        )
    if snapshot.coordinate_unit != "angstrom":
        raise SmilesWriteError(
            "unsupported_coordinate_unit",
            "SMILES parser-owned topology carrier uses angstrom units",
            location="coordinate_unit",
        )
    if snapshot.coordinates.shape != (0, snapshot.atom_count, 3):
        raise SmilesWriteError(
            "unsupported_coordinates",
            "SMILES writer accepts only the exact empty topology-only coordinate carrier",
            location="coordinates",
        )
    if snapshot.cell is not None:
        raise SmilesWriteError(
            "unsupported_cell",
            "SMILES writer does not preserve unit-cell state",
            location="cell",
        )
    system_metadata = _require_exact_keys(
        snapshot.metadata,
        _SYSTEM_METADATA_KEYS,
        code="unsupported_system_metadata",
        location="metadata",
    )
    source_atom_count = system_metadata["source_atom_count"]
    if type(source_atom_count) is not int:
        raise SmilesWriteError(
            "invalid_source_atom_count",
            "source atom count marker must be an exact integer",
            location="metadata.source_atom_count",
        )
    if not 1 <= source_atom_count <= min(_MAX_SOURCE_ATOMS, snapshot.atom_count):
        raise SmilesWriteError(
            "unsupported_source_atom_count",
            "declared source atom count is outside the writer limit",
            location="metadata.source_atom_count",
        )
    declared_fragment_count = system_metadata["fragment_count"]
    if type(declared_fragment_count) is not int:
        raise SmilesWriteError(
            "invalid_fragment_count",
            "fragment count marker must be an exact integer",
            location="metadata.fragment_count",
        )
    if not 1 <= declared_fragment_count <= min(_MAX_FRAGMENTS, source_atom_count):
        raise SmilesWriteError(
            "unsupported_fragment_count",
            "declared fragment count is outside the writer limit",
            location="metadata.fragment_count",
        )
    _preflight_supported_scope(
        snapshot,
        source_atom_count=source_atom_count,
    )
    forest = _validate_atoms_and_graph(
        snapshot,
        source_atom_count=source_atom_count,
    )
    candidate = _emit_source_forest(
        source_atom_count=source_atom_count,
        source_atom_tokens=forest.source_atom_tokens,
        source_component_roots=forest.source_component_roots,
        source_children=forest.source_children,
        source_parent_bond_tokens=forest.source_parent_bond_tokens,
        source_ring_marker_table=forest.source_ring_marker_table,
    )
    attached_normalized_sha256 = snapshot.provenance.metadata.get(
        "normalized_isomeric_smiles_sha256"
    )
    if (
        type(attached_normalized_sha256) is not str
        or _SHA256_RE.fullmatch(attached_normalized_sha256) is None
        or hashlib.sha256(candidate).hexdigest() != attached_normalized_sha256
    ):
        raise SmilesWriteError(
            "normalized_smiles_hash_mismatch",
            "source-order forest DFS atom and bond tokens do not match the attached normalized identity",
            location="provenance.metadata.normalized_isomeric_smiles_sha256",
        )
    _validate_parser_context(
        snapshot,
        expanded_components=forest.expanded_components,
    )
    ordered_topology_sha256 = _ordered_topology_digest(
        snapshot.atoms,
        snapshot.bonds,
        forest.expanded_components,
    )
    topology_sha256 = canonical_topology_sha256(snapshot)
    rdkit_version, normalized_sha256, coverage_document = (
        _validate_provenance_and_metadata(
            snapshot,
            source_atom_count=source_atom_count,
            generated_hydrogen_count=forest.generated_hydrogen_count,
            fragment_count=forest.fragment_count,
            formal_charge_total=forest.formal_charge_total,
            mapped_source_atom_count=forest.mapped_source_atom_count,
            aromatic_atom_count=forest.aromatic_source_atom_count,
            typed_tetrahedral_atom_count=forest.typed_tetrahedral_atom_count,
            typed_ez_bond_count=forest.typed_ez_bond_count,
            ordered_topology_sha256=ordered_topology_sha256,
            topology_sha256=topology_sha256,
        )
    )
    atoms_document = [_atom_document(atom) for atom in snapshot.atoms]
    bonds_document = [_bond_document(bond) for bond in snapshot.bonds]
    formal_charge_profile_id = (
        _AROMATIC_FORMAL_CHARGE_PROFILE_ID
        if forest.aromatic_source_atom_count
        else (
            _RING_FORMAL_CHARGE_PROFILE_ID
            if forest.ring_closure_count
            else _FORMAL_CHARGE_PROFILE_ID
        )
    )
    representable_state_document: Mapping[str, Any] = {
        "schema_id": SMILES_REPRESENTABLE_STATE_SCHEMA_ID,
        "system_schema_id": snapshot.schema_id,
        "writer_version": SMILES_WRITER_VERSION,
        "parser_name": snapshot.provenance.parser_name,
        "parser_version": snapshot.provenance.parser_version,
        "parser_operations": list(snapshot.provenance.operations),
        "rdkit_version": rdkit_version,
        "emission_policy_id": _EMISSION_POLICY_ID,
        "formal_charge_profile_id": formal_charge_profile_id,
        "cycle_projection_schema_id": (SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID),
        "cycle_profile_id": forest.cycle_profile_id,
        "cycle_projection_sha256": forest.cycle_projection_sha256,
        "cycle_projection": dict(forest.cycle_projection_document),
        "aromatic_projection_schema_id": (SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID),
        "aromatic_ring_profile_id": forest.aromatic_ring_profile_id,
        "aromatic_atom_state_profile_id": (forest.aromatic_atom_state_profile_id),
        "aromatic_projection_sha256": forest.aromatic_projection_sha256,
        "aromatic_projection": dict(forest.aromatic_projection_document),
        "ez_stereo_projection_schema_id": SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
        "ez_stereo_profile_id": forest.ez_stereo_profile_id,
        "ez_stereo_projection_sha256": forest.ez_stereo_projection_sha256,
        "ez_stereo_projection": dict(forest.ez_stereo_projection_document),
        "tetrahedral_stereo_projection_schema_id": (
            SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
        ),
        "tetrahedral_stereo_profile_id": forest.tetrahedral_stereo_profile_id,
        "tetrahedral_stereo_projection_sha256": (
            forest.tetrahedral_stereo_projection_sha256
        ),
        "tetrahedral_stereo_projection": dict(
            forest.tetrahedral_stereo_projection_document
        ),
        "normalized_isomeric_smiles_sha256": normalized_sha256,
        "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
        "canonical_topology_sha256": topology_sha256,
        "ordered_topology_sha256": ordered_topology_sha256,
        "coverage": dict(coverage_document),
        "system_metadata": {
            "ordered_topology_sha256": ordered_topology_sha256,
            "source_atom_count": source_atom_count,
            "generated_hydrogen_count": forest.generated_hydrogen_count,
            "fragment_count": forest.fragment_count,
        },
        "source_atom_count": source_atom_count,
        "expanded_atom_count": snapshot.atom_count,
        "generated_hydrogen_count": forest.generated_hydrogen_count,
        "implicit_hydrogen_count": forest.implicit_hydrogen_count,
        "bracket_explicit_hydrogen_count": (forest.bracket_explicit_hydrogen_count),
        "mapped_source_atom_count": forest.mapped_source_atom_count,
        "typed_tetrahedral_atom_count": forest.typed_tetrahedral_atom_count,
        "bond_count": len(snapshot.bonds),
        "fragment_count": forest.fragment_count,
        "source_bond_count": forest.source_bond_count,
        "source_tree_edge_count": forest.source_tree_edge_count,
        "component_cyclomatic_numbers": list(forest.component_cyclomatic_numbers),
        "ring_closure_count": forest.ring_closure_count,
        "cyclic_component_count": forest.cyclic_component_count,
        "cyclic_component_index": forest.cyclic_component_index,
        "ring_size": forest.ring_size,
        "ring_atom_indices": list(forest.ring_atom_indices),
        "ring_bond_indices": list(forest.ring_bond_indices),
        "ring_closure_source_bond_index": (forest.ring_closure_source_bond_index),
        "ring_closure_endpoints": list(forest.ring_closure_endpoints),
        "ring_open_source_atom_index": forest.ring_open_source_atom_index,
        "ring_close_source_atom_index": forest.ring_close_source_atom_index,
        "ring_bond_profile_id": forest.ring_bond_profile_id,
        "ring_double_bond_count": forest.ring_double_bond_count,
        "ring_double_source_bond_index": forest.ring_double_source_bond_index,
        "aromatic_source_atom_count": forest.aromatic_source_atom_count,
        "aromatic_source_bond_count": forest.aromatic_source_bond_count,
        "typed_ez_bond_count": forest.typed_ez_bond_count,
        "directional_source_bond_count": forest.directional_source_bond_count,
        "ring_bond_order_table": [
            {
                "source_bond_index": source_bond_index,
                "atom_indices": list(atom_indices),
                "order_ieee754_binary64_be": order_hex,
                "aromatic": aromatic,
                "bond_token": bond_token,
                "stereo": stereo,
                "role": role,
            }
            for source_bond_index, atom_indices, order_hex, aromatic, bond_token, stereo, role in (
                forest.ring_bond_order_table
            )
        ],
        "charged_source_atom_count": forest.charged_source_atom_count,
        "formal_charge_total": forest.formal_charge_total,
        "source_atom_tokens": list(forest.source_atom_tokens),
        "source_component_roots": list(forest.source_component_roots),
        "source_components": [
            list(component) for component in forest.source_components
        ],
        "expanded_components": [
            list(component) for component in forest.expanded_components
        ],
        "source_children": [list(children) for children in forest.source_children],
        "source_parent_bond_tokens": list(forest.source_parent_bond_tokens),
        "source_ring_marker_table": list(forest.source_ring_marker_table),
        "component_contexts": [
            {
                "component_index": index,
                "root_source_atom_index": forest.source_component_roots[index],
                "source_atom_indices": list(forest.source_components[index]),
                "expanded_atom_indices": list(forest.expanded_components[index]),
                "residue_index": index,
                "chain_index": index,
            }
            for index in range(forest.fragment_count)
        ],
        "atoms": atoms_document,
        "bonds": bonds_document,
        "residues": [
            {
                "index": residue.index,
                "name": residue.name,
                "chain_index": residue.chain_index,
                "sequence_number": residue.sequence_number,
                "atom_indices": list(residue.atom_indices),
                "insertion_code": residue.insertion_code,
                "entity_type": residue.entity_type,
                "hetero": residue.hetero,
                "metadata": dict(residue.metadata),
            }
            for residue in snapshot.residues
        ],
        "chains": [
            {
                "index": chain.index,
                "chain_id": chain.chain_id,
                "residue_indices": list(chain.residue_indices),
                "entity_id": chain.entity_id,
                "metadata": dict(chain.metadata),
            }
            for chain in snapshot.chains
        ],
        "coordinate_unit": "angstrom",
        "coordinate_dtype": "float64",
        "coordinate_shape": [0, snapshot.atom_count, 3],
        "coordinates_present": False,
        "coordinate_requires_grad": False,
        "cell": None,
        "preservation_scope": list(_PRESERVATION_SCOPE),
        "source_authentication_status": "not_authenticated",
        "preparation_ready": False,
        "parameterability_assessed": False,
        "simulation_ready": False,
        "claim_safe": False,
        "blockers": list(_NON_PROMOTION_BLOCKERS),
    }
    return _ValidatedWriteState(
        system=snapshot,
        source_atom_count=source_atom_count,
        generated_hydrogen_count=forest.generated_hydrogen_count,
        implicit_hydrogen_count=forest.implicit_hydrogen_count,
        bracket_explicit_hydrogen_count=(forest.bracket_explicit_hydrogen_count),
        mapped_source_atom_count=forest.mapped_source_atom_count,
        typed_tetrahedral_atom_count=forest.typed_tetrahedral_atom_count,
        fragment_count=forest.fragment_count,
        formal_charge_profile_id=formal_charge_profile_id,
        cycle_profile_id=forest.cycle_profile_id,
        ring_bond_profile_id=forest.ring_bond_profile_id,
        charged_source_atom_count=forest.charged_source_atom_count,
        formal_charge_total=forest.formal_charge_total,
        source_atom_tokens=forest.source_atom_tokens,
        source_component_roots=forest.source_component_roots,
        source_components=forest.source_components,
        expanded_components=forest.expanded_components,
        source_children=forest.source_children,
        source_parent_bond_tokens=forest.source_parent_bond_tokens,
        source_ring_marker_table=forest.source_ring_marker_table,
        source_bond_count=forest.source_bond_count,
        source_tree_edge_count=forest.source_tree_edge_count,
        component_cyclomatic_numbers=forest.component_cyclomatic_numbers,
        ring_closure_count=forest.ring_closure_count,
        cyclic_component_count=forest.cyclic_component_count,
        cyclic_component_index=forest.cyclic_component_index,
        ring_size=forest.ring_size,
        ring_atom_indices=forest.ring_atom_indices,
        ring_bond_indices=forest.ring_bond_indices,
        ring_closure_source_bond_index=forest.ring_closure_source_bond_index,
        ring_closure_endpoints=forest.ring_closure_endpoints,
        ring_open_source_atom_index=forest.ring_open_source_atom_index,
        ring_close_source_atom_index=forest.ring_close_source_atom_index,
        ring_double_bond_count=forest.ring_double_bond_count,
        ring_double_source_bond_index=forest.ring_double_source_bond_index,
        aromatic_source_atom_count=forest.aromatic_source_atom_count,
        aromatic_source_bond_count=forest.aromatic_source_bond_count,
        aromatic_ring_profile_id=forest.aromatic_ring_profile_id,
        aromatic_atom_state_profile_id=forest.aromatic_atom_state_profile_id,
        typed_ez_bond_count=forest.typed_ez_bond_count,
        directional_source_bond_count=forest.directional_source_bond_count,
        ez_stereo_profile_id=forest.ez_stereo_profile_id,
        ring_bond_order_table=forest.ring_bond_order_table,
        cycle_projection_document=forest.cycle_projection_document,
        cycle_projection_sha256=forest.cycle_projection_sha256,
        aromatic_projection_document=forest.aromatic_projection_document,
        aromatic_projection_sha256=forest.aromatic_projection_sha256,
        ez_stereo_projection_document=forest.ez_stereo_projection_document,
        ez_stereo_projection_sha256=forest.ez_stereo_projection_sha256,
        tetrahedral_stereo_profile_id=forest.tetrahedral_stereo_profile_id,
        tetrahedral_stereo_projection_document=(
            forest.tetrahedral_stereo_projection_document
        ),
        tetrahedral_stereo_projection_sha256=(
            forest.tetrahedral_stereo_projection_sha256
        ),
        rdkit_version=rdkit_version,
        normalized_isomeric_smiles_sha256=normalized_sha256,
        ordered_topology_sha256=ordered_topology_sha256,
        canonical_topology_sha256=topology_sha256,
        coverage_document=coverage_document,
        representable_state_document=representable_state_document,
    )


def _emit_source_forest(
    *,
    source_atom_count: int,
    source_atom_tokens: tuple[str, ...],
    source_component_roots: tuple[int, ...],
    source_children: tuple[tuple[int, ...], ...],
    source_parent_bond_tokens: tuple[str, ...],
    source_ring_marker_table: tuple[str, ...],
) -> bytes:
    if (
        not 1 <= len(source_component_roots) <= min(_MAX_FRAGMENTS, source_atom_count)
        or any(
            type(root) is not int or not 0 <= root < source_atom_count
            for root in source_component_roots
        )
        or any(
            left >= right
            for left, right in zip(
                source_component_roots,
                source_component_roots[1:],
            )
        )
        or len(source_atom_tokens) != source_atom_count
        or any(type(token) is not str or not token for token in source_atom_tokens)
        or len(source_children) != source_atom_count
        or len(source_parent_bond_tokens) != source_atom_count
        or len(source_ring_marker_table) != source_atom_count
        or any(source_parent_bond_tokens[root] != "" for root in source_component_roots)
        or any(
            token not in {"", "=", "#", "/", "\\"}
            for token in source_parent_bond_tokens
        )
        or any(
            marker not in ("", "1", "/1", "\\1") for marker in source_ring_marker_table
        )
        or sum(bool(marker) for marker in source_ring_marker_table) not in (0, 2)
        or sum(marker in {"/1", "\\1"} for marker in source_ring_marker_table)
        not in (0, 1)
    ):
        raise SmilesWriteError(
            "internal_emission_error",
            "source atom tokens, forest roots, children, or parent bond tokens are inconsistent",
        )
    output: list[str] = []
    visitation: list[int] = []
    for component_index, root in enumerate(source_component_roots):
        if component_index:
            output.append(".")
        events: list[tuple[str, int | str]] = [("atom", root)]
        while events:
            kind, value = events.pop()
            if kind == "text":
                output.append(value)  # type: ignore[arg-type]
                continue
            atom_index = value
            if type(atom_index) is not int:  # pragma: no cover - private invariant
                raise SmilesWriteError("internal_emission_error", "invalid atom event")
            visitation.append(atom_index)
            output.append(source_atom_tokens[atom_index])
            marker = source_ring_marker_table[atom_index]
            if marker:
                output.append(marker)
            children = source_children[atom_index]
            actions: list[tuple[str, int | str]] = []
            for child in children[:-1]:
                actions.append(("text", "("))
                bond_token = source_parent_bond_tokens[child]
                if bond_token:
                    actions.append(("text", bond_token))
                actions.extend((("atom", child), ("text", ")")))
            if children:
                child = children[-1]
                bond_token = source_parent_bond_tokens[child]
                if bond_token:
                    actions.append(("text", bond_token))
                actions.append(("atom", child))
            events.extend(reversed(actions))
    if tuple(visitation) != tuple(range(source_atom_count)):
        raise SmilesWriteError(
            "source_order_not_depth_first",
            "ordered forest DFS visitation must exactly equal parser source atom order",
            location="atoms",
        )
    text = "".join(output)
    if text.count(".") != len(source_component_roots) - 1:
        raise SmilesWriteError(
            "internal_emission_error",
            "emitted forest must contain exactly one dot between component roots",
        )
    if not text or "\n" in text or "\r" in text or not text.isascii():
        raise SmilesWriteError(
            "invalid_emitted_line",
            "emitted SMILES must be one nonempty ASCII line",
        )
    try:
        payload = text.encode("ascii")
    except UnicodeEncodeError as exc:  # pragma: no cover - element allowlist
        raise SmilesWriteError(
            "invalid_emitted_line", "emitted line is not ASCII"
        ) from exc
    if len(payload) > _MAX_OUTPUT_BYTES:
        raise SmilesWriteError(
            "output_too_large",
            "emitted SMILES exceeds the parser 64 KiB limit",
        )
    return payload


def _emit_payload(state: _ValidatedWriteState) -> bytes:
    payload = _emit_source_forest(
        source_atom_count=state.source_atom_count,
        source_atom_tokens=state.source_atom_tokens,
        source_component_roots=state.source_component_roots,
        source_children=state.source_children,
        source_parent_bond_tokens=state.source_parent_bond_tokens,
        source_ring_marker_table=state.source_ring_marker_table,
    )
    output_sha256 = hashlib.sha256(payload).hexdigest()
    if output_sha256 != state.normalized_isomeric_smiles_sha256:
        raise SmilesWriteError(
            "normalized_smiles_hash_mismatch",
            "source-order forest DFS spelling does not match the attached normalized identity",
            location="provenance.metadata.normalized_isomeric_smiles_sha256",
        )
    return payload


def _verify_emission(
    state: _ValidatedWriteState,
    payload: bytes,
) -> tuple[SmilesIngestResult, _ValidatedWriteState]:
    try:
        reparsed = parse_smiles(payload)
        reparsed_state = _validate_write_state(reparsed.system)
        reemitted = _emit_payload(reparsed_state)
    except SmilesParseError as exc:
        raise SmilesWriteError(
            "canonical_reparse_failed",
            f"emitted line failed strict parser validation ({exc.code})",
        ) from exc
    except SmilesWriteError:
        raise
    except (TypeError, ValueError, OverflowError, RuntimeError) as exc:
        raise SmilesWriteError(
            "canonical_reparse_failed",
            "emitted line failed strict parser-state validation",
        ) from exc
    mismatches: list[str] = []
    pairs = (
        (
            "canonical_topology",
            state.canonical_topology_sha256,
            reparsed_state.canonical_topology_sha256,
        ),
        (
            "ordered_topology",
            state.ordered_topology_sha256,
            reparsed_state.ordered_topology_sha256,
        ),
        ("rdkit_version", state.rdkit_version, reparsed_state.rdkit_version),
        (
            "normalized_identity",
            state.normalized_isomeric_smiles_sha256,
            reparsed_state.normalized_isomeric_smiles_sha256,
        ),
        (
            "source_atom_count",
            state.source_atom_count,
            reparsed_state.source_atom_count,
        ),
        (
            "expanded_atom_count",
            state.system.atom_count,
            reparsed_state.system.atom_count,
        ),
        ("bond_count", len(state.system.bonds), len(reparsed_state.system.bonds)),
        (
            "generated_hydrogen_count",
            state.generated_hydrogen_count,
            reparsed_state.generated_hydrogen_count,
        ),
        (
            "implicit_hydrogen_count",
            state.implicit_hydrogen_count,
            reparsed_state.implicit_hydrogen_count,
        ),
        (
            "bracket_explicit_hydrogen_count",
            state.bracket_explicit_hydrogen_count,
            reparsed_state.bracket_explicit_hydrogen_count,
        ),
        (
            "mapped_source_atom_count",
            state.mapped_source_atom_count,
            reparsed_state.mapped_source_atom_count,
        ),
        (
            "typed_tetrahedral_atom_count",
            state.typed_tetrahedral_atom_count,
            reparsed_state.typed_tetrahedral_atom_count,
        ),
        ("fragment_count", state.fragment_count, reparsed_state.fragment_count),
        (
            "formal_charge_profile_id",
            state.formal_charge_profile_id,
            reparsed_state.formal_charge_profile_id,
        ),
        (
            "charged_source_atom_count",
            state.charged_source_atom_count,
            reparsed_state.charged_source_atom_count,
        ),
        (
            "formal_charge_total",
            state.formal_charge_total,
            reparsed_state.formal_charge_total,
        ),
        (
            "cycle_projection",
            state.cycle_projection_sha256,
            reparsed_state.cycle_projection_sha256,
        ),
        (
            "aromatic_projection",
            state.aromatic_projection_sha256,
            reparsed_state.aromatic_projection_sha256,
        ),
        (
            "ez_stereo_projection",
            state.ez_stereo_projection_sha256,
            reparsed_state.ez_stereo_projection_sha256,
        ),
        (
            "tetrahedral_stereo_profile_id",
            state.tetrahedral_stereo_profile_id,
            reparsed_state.tetrahedral_stereo_profile_id,
        ),
        (
            "tetrahedral_stereo_projection",
            state.tetrahedral_stereo_projection_sha256,
            reparsed_state.tetrahedral_stereo_projection_sha256,
        ),
        (
            "typed_ez_bond_count",
            state.typed_ez_bond_count,
            reparsed_state.typed_ez_bond_count,
        ),
        (
            "directional_source_bond_count",
            state.directional_source_bond_count,
            reparsed_state.directional_source_bond_count,
        ),
        (
            "source_bond_count",
            state.source_bond_count,
            reparsed_state.source_bond_count,
        ),
        (
            "source_tree_edge_count",
            state.source_tree_edge_count,
            reparsed_state.source_tree_edge_count,
        ),
        (
            "component_cyclomatic_numbers",
            state.component_cyclomatic_numbers,
            reparsed_state.component_cyclomatic_numbers,
        ),
        (
            "ring_closure_count",
            state.ring_closure_count,
            reparsed_state.ring_closure_count,
        ),
        (
            "cyclic_component_count",
            state.cyclic_component_count,
            reparsed_state.cyclic_component_count,
        ),
        (
            "cyclic_component_index",
            state.cyclic_component_index,
            reparsed_state.cyclic_component_index,
        ),
        ("ring_size", state.ring_size, reparsed_state.ring_size),
        (
            "ring_atom_indices",
            state.ring_atom_indices,
            reparsed_state.ring_atom_indices,
        ),
        (
            "ring_bond_indices",
            state.ring_bond_indices,
            reparsed_state.ring_bond_indices,
        ),
        (
            "ring_closure_source_bond_index",
            state.ring_closure_source_bond_index,
            reparsed_state.ring_closure_source_bond_index,
        ),
        (
            "ring_closure_endpoints",
            state.ring_closure_endpoints,
            reparsed_state.ring_closure_endpoints,
        ),
        (
            "cycle_profile_id",
            state.cycle_profile_id,
            reparsed_state.cycle_profile_id,
        ),
        (
            "ring_bond_profile_id",
            state.ring_bond_profile_id,
            reparsed_state.ring_bond_profile_id,
        ),
        (
            "ring_double_bond_count",
            state.ring_double_bond_count,
            reparsed_state.ring_double_bond_count,
        ),
        (
            "ring_double_source_bond_index",
            state.ring_double_source_bond_index,
            reparsed_state.ring_double_source_bond_index,
        ),
        (
            "aromatic_source_atom_count",
            state.aromatic_source_atom_count,
            reparsed_state.aromatic_source_atom_count,
        ),
        (
            "aromatic_source_bond_count",
            state.aromatic_source_bond_count,
            reparsed_state.aromatic_source_bond_count,
        ),
        (
            "aromatic_ring_profile_id",
            state.aromatic_ring_profile_id,
            reparsed_state.aromatic_ring_profile_id,
        ),
        (
            "aromatic_atom_state_profile_id",
            state.aromatic_atom_state_profile_id,
            reparsed_state.aromatic_atom_state_profile_id,
        ),
        (
            "ring_bond_order_table",
            state.ring_bond_order_table,
            reparsed_state.ring_bond_order_table,
        ),
        (
            "source_ring_marker_table",
            state.source_ring_marker_table,
            reparsed_state.source_ring_marker_table,
        ),
        (
            "source_atom_tokens",
            state.source_atom_tokens,
            reparsed_state.source_atom_tokens,
        ),
        (
            "source_component_roots",
            state.source_component_roots,
            reparsed_state.source_component_roots,
        ),
        (
            "source_components",
            state.source_components,
            reparsed_state.source_components,
        ),
        (
            "expanded_components",
            state.expanded_components,
            reparsed_state.expanded_components,
        ),
        (
            "source_children",
            state.source_children,
            reparsed_state.source_children,
        ),
        (
            "source_parent_bond_tokens",
            state.source_parent_bond_tokens,
            reparsed_state.source_parent_bond_tokens,
        ),
    )
    mismatches.extend(
        label
        for label, left, right in pairs
        if type(left) is not type(right) or left != right
    )
    if not _exact_typed_structure_equal(
        state.representable_state_document,
        reparsed_state.representable_state_document,
    ):
        mismatches.append("representable_state")
    if not _exact_typed_structure_equal(
        reparsed.system.provenance.metadata.get("coverage"),
        reparsed.coverage.to_dict(),
    ):
        mismatches.append("reparsed_coverage")
    if reemitted != payload:
        mismatches.append("second_emission_bytes")
    if mismatches:
        raise SmilesWriteError(
            "round_trip_projection_mismatch",
            f"emitted line does not reproduce exact declared state: {mismatches}",
        )
    return reparsed, reparsed_state


def _validated_payload_image(payload: bytes) -> _ValidatedWriteState:
    if type(payload) is not bytes:
        raise TypeError("payload must be exact bytes")
    if not 1 <= len(payload) <= _MAX_OUTPUT_BYTES:
        raise ValueError("payload length is outside the SMILES writer limit")
    if b"\n" in payload or b"\r" in payload:
        raise ValueError("payload must contain exactly one line without a terminator")
    ingest = parse_smiles(payload)
    state = _validate_write_state(ingest.system)
    if _emit_payload(state) != payload:
        raise ValueError("payload is not deterministic writer output")
    return state


def smiles_representable_state_sha256(system: AllAtomSystem) -> str:
    """Hash the exact parser-owned SMILES state reproduced by this writer."""

    state = _validate_write_state(system)
    payload = _emit_payload(state)
    _verify_emission(state, payload)
    return _sha256_document(state.representable_state_document)


def write_smiles(system: AllAtomSystem) -> SmilesWriteResult:
    """Emit one deterministic ASCII SMILES line and a non-authoritative receipt."""

    state = _validate_write_state(system)
    payload = _emit_payload(state)
    output_source_sha256 = hashlib.sha256(payload).hexdigest()
    _verify_emission(state, payload)
    parser_observation_sha256 = state.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if type(parser_observation_sha256) is not str:
        raise SmilesWriteError(
            "stale_parser_observation_digest",
            "validated parser observation digest is missing",
            location="provenance.metadata.parser_observation_sha256",
        )
    receipt = SmilesWriteReceipt(
        input_system_schema_id=state.system.schema_id,
        parent_source_sha256=state.system.provenance.source_sha256,
        input_snapshot_sha256=canonical_all_atom_snapshot_digest(state.system),
        input_topology_sha256=state.canonical_topology_sha256,
        input_ordered_topology_sha256=state.ordered_topology_sha256,
        input_representable_state_sha256=_sha256_document(
            state.representable_state_document
        ),
        input_cycle_projection_sha256=state.cycle_projection_sha256,
        input_aromatic_projection_sha256=state.aromatic_projection_sha256,
        input_ez_stereo_projection_sha256=state.ez_stereo_projection_sha256,
        input_tetrahedral_stereo_projection_sha256=(
            state.tetrahedral_stereo_projection_sha256
        ),
        input_parser_observation_sha256=parser_observation_sha256,
        normalized_isomeric_smiles_sha256=(state.normalized_isomeric_smiles_sha256),
        rdkit_version=state.rdkit_version,
        output_source_sha256=output_source_sha256,
        output_byte_count=len(payload),
        source_atom_count=state.source_atom_count,
        expanded_atom_count=state.system.atom_count,
        atom_count=state.system.atom_count,
        bond_count=len(state.system.bonds),
        fragment_count=state.fragment_count,
        generated_hydrogen_count=state.generated_hydrogen_count,
        implicit_hydrogen_count=state.implicit_hydrogen_count,
        bracket_explicit_hydrogen_count=state.bracket_explicit_hydrogen_count,
        mapped_source_atom_count=state.mapped_source_atom_count,
        typed_tetrahedral_atom_count=state.typed_tetrahedral_atom_count,
        source_bond_count=state.source_bond_count,
        source_tree_edge_count=state.source_tree_edge_count,
        ring_closure_count=state.ring_closure_count,
        cyclic_component_count=state.cyclic_component_count,
        ring_size=state.ring_size,
        ring_closure_source_bond_index=state.ring_closure_source_bond_index,
        ring_bond_profile_id=state.ring_bond_profile_id,
        ring_double_bond_count=state.ring_double_bond_count,
        ring_double_source_bond_index=state.ring_double_source_bond_index,
        aromatic_source_atom_count=state.aromatic_source_atom_count,
        aromatic_source_bond_count=state.aromatic_source_bond_count,
        typed_ez_bond_count=state.typed_ez_bond_count,
        directional_source_bond_count=state.directional_source_bond_count,
        cycle_projection_schema_id=(SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID),
        cycle_profile_id=state.cycle_profile_id,
        aromatic_projection_schema_id=(SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID),
        aromatic_ring_profile_id=state.aromatic_ring_profile_id,
        aromatic_atom_state_profile_id=state.aromatic_atom_state_profile_id,
        ez_stereo_projection_schema_id=SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID,
        ez_stereo_profile_id=state.ez_stereo_profile_id,
        tetrahedral_stereo_projection_schema_id=(
            SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID
        ),
        tetrahedral_stereo_profile_id=state.tetrahedral_stereo_profile_id,
        formal_charge_profile_id=state.formal_charge_profile_id,
        charged_source_atom_count=state.charged_source_atom_count,
        formal_charge_total=state.formal_charge_total,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SmilesWriteResult(
        payload=payload,
        receipt=receipt,
        input_system=state.system,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


def serialize_smiles(system: AllAtomSystem) -> bytes:
    """Return deterministic strict SMILES bytes without a line terminator."""

    return write_smiles(system).payload


def round_trip_smiles_source(
    data: bytes,
    *,
    source_id: str = "",
) -> SmilesRoundTripResult:
    """Execute and verify ``source -> canonical -> SMILES -> canonical``.

    Equality covers only :data:`SMILES_REPRESENTABLE_STATE_SCHEMA_ID`.
    Dynamic raw-source provenance and the complete canonical snapshot are
    receipt-bound but intentionally are not equality or authentication claims.
    """

    source_ingest = parse_smiles(data, source_id=source_id)
    write_result = write_smiles(source_ingest.system)
    reparsed_ingest = parse_smiles(write_result.payload, source_id=source_id)
    reemitted = write_smiles(reparsed_ingest.system)
    source_state = _validate_write_state(source_ingest.system)
    reparsed_state = _validate_write_state(reparsed_ingest.system)
    input_state_sha256 = _sha256_document(source_state.representable_state_document)
    reparsed_state_sha256 = _sha256_document(
        reparsed_state.representable_state_document
    )
    input_source_sha256 = hashlib.sha256(data).hexdigest()
    mismatches: list[str] = []
    pairs = (
        (
            "input_source_sha256",
            source_ingest.system.provenance.source_sha256,
            input_source_sha256,
        ),
        (
            "writer_parent_source_sha256",
            write_result.receipt.parent_source_sha256,
            input_source_sha256,
        ),
        (
            "canonical_topology",
            source_state.canonical_topology_sha256,
            reparsed_state.canonical_topology_sha256,
        ),
        (
            "ordered_topology",
            source_state.ordered_topology_sha256,
            reparsed_state.ordered_topology_sha256,
        ),
        (
            "fragment_count",
            source_state.fragment_count,
            reparsed_state.fragment_count,
        ),
        (
            "formal_charge_profile_id",
            source_state.formal_charge_profile_id,
            reparsed_state.formal_charge_profile_id,
        ),
        (
            "charged_source_atom_count",
            source_state.charged_source_atom_count,
            reparsed_state.charged_source_atom_count,
        ),
        (
            "formal_charge_total",
            source_state.formal_charge_total,
            reparsed_state.formal_charge_total,
        ),
        (
            "implicit_hydrogen_count",
            source_state.implicit_hydrogen_count,
            reparsed_state.implicit_hydrogen_count,
        ),
        (
            "bracket_explicit_hydrogen_count",
            source_state.bracket_explicit_hydrogen_count,
            reparsed_state.bracket_explicit_hydrogen_count,
        ),
        (
            "mapped_source_atom_count",
            source_state.mapped_source_atom_count,
            reparsed_state.mapped_source_atom_count,
        ),
        (
            "typed_tetrahedral_atom_count",
            source_state.typed_tetrahedral_atom_count,
            reparsed_state.typed_tetrahedral_atom_count,
        ),
        (
            "cycle_projection",
            source_state.cycle_projection_sha256,
            reparsed_state.cycle_projection_sha256,
        ),
        (
            "aromatic_projection",
            source_state.aromatic_projection_sha256,
            reparsed_state.aromatic_projection_sha256,
        ),
        (
            "ez_stereo_projection",
            source_state.ez_stereo_projection_sha256,
            reparsed_state.ez_stereo_projection_sha256,
        ),
        (
            "tetrahedral_stereo_profile_id",
            source_state.tetrahedral_stereo_profile_id,
            reparsed_state.tetrahedral_stereo_profile_id,
        ),
        (
            "tetrahedral_stereo_projection",
            source_state.tetrahedral_stereo_projection_sha256,
            reparsed_state.tetrahedral_stereo_projection_sha256,
        ),
        (
            "typed_ez_bond_count",
            source_state.typed_ez_bond_count,
            reparsed_state.typed_ez_bond_count,
        ),
        (
            "directional_source_bond_count",
            source_state.directional_source_bond_count,
            reparsed_state.directional_source_bond_count,
        ),
        (
            "source_bond_count",
            source_state.source_bond_count,
            reparsed_state.source_bond_count,
        ),
        (
            "source_tree_edge_count",
            source_state.source_tree_edge_count,
            reparsed_state.source_tree_edge_count,
        ),
        (
            "component_cyclomatic_numbers",
            source_state.component_cyclomatic_numbers,
            reparsed_state.component_cyclomatic_numbers,
        ),
        (
            "ring_closure_count",
            source_state.ring_closure_count,
            reparsed_state.ring_closure_count,
        ),
        (
            "cyclic_component_count",
            source_state.cyclic_component_count,
            reparsed_state.cyclic_component_count,
        ),
        (
            "ring_size",
            source_state.ring_size,
            reparsed_state.ring_size,
        ),
        (
            "ring_closure_source_bond_index",
            source_state.ring_closure_source_bond_index,
            reparsed_state.ring_closure_source_bond_index,
        ),
        (
            "cycle_profile_id",
            source_state.cycle_profile_id,
            reparsed_state.cycle_profile_id,
        ),
        (
            "ring_bond_profile_id",
            source_state.ring_bond_profile_id,
            reparsed_state.ring_bond_profile_id,
        ),
        (
            "ring_double_bond_count",
            source_state.ring_double_bond_count,
            reparsed_state.ring_double_bond_count,
        ),
        (
            "ring_double_source_bond_index",
            source_state.ring_double_source_bond_index,
            reparsed_state.ring_double_source_bond_index,
        ),
        (
            "aromatic_source_atom_count",
            source_state.aromatic_source_atom_count,
            reparsed_state.aromatic_source_atom_count,
        ),
        (
            "aromatic_source_bond_count",
            source_state.aromatic_source_bond_count,
            reparsed_state.aromatic_source_bond_count,
        ),
        (
            "aromatic_ring_profile_id",
            source_state.aromatic_ring_profile_id,
            reparsed_state.aromatic_ring_profile_id,
        ),
        (
            "aromatic_atom_state_profile_id",
            source_state.aromatic_atom_state_profile_id,
            reparsed_state.aromatic_atom_state_profile_id,
        ),
        (
            "ring_bond_order_table",
            source_state.ring_bond_order_table,
            reparsed_state.ring_bond_order_table,
        ),
        (
            "source_ring_marker_table",
            source_state.source_ring_marker_table,
            reparsed_state.source_ring_marker_table,
        ),
        (
            "source_atom_tokens",
            source_state.source_atom_tokens,
            reparsed_state.source_atom_tokens,
        ),
        (
            "source_component_roots",
            source_state.source_component_roots,
            reparsed_state.source_component_roots,
        ),
        (
            "source_components",
            source_state.source_components,
            reparsed_state.source_components,
        ),
        (
            "expanded_components",
            source_state.expanded_components,
            reparsed_state.expanded_components,
        ),
        (
            "source_children",
            source_state.source_children,
            reparsed_state.source_children,
        ),
        (
            "source_parent_bond_tokens",
            source_state.source_parent_bond_tokens,
            reparsed_state.source_parent_bond_tokens,
        ),
        ("representable_state", input_state_sha256, reparsed_state_sha256),
        (
            "reparsed_source_sha256",
            reparsed_ingest.system.provenance.source_sha256,
            write_result.receipt.output_source_sha256,
        ),
    )
    mismatches.extend(
        label
        for label, left, right in pairs
        if type(left) is not type(right) or left != right
    )
    if not _exact_typed_structure_equal(
        source_ingest.system.provenance.metadata.get("coverage"),
        source_ingest.coverage.to_dict(),
    ):
        mismatches.append("input_coverage")
    if not _exact_typed_structure_equal(
        reparsed_ingest.system.provenance.metadata.get("coverage"),
        reparsed_ingest.coverage.to_dict(),
    ):
        mismatches.append("reparsed_coverage")
    if reemitted.payload != write_result.payload:
        mismatches.append("reemitted_bytes")
    if mismatches:
        raise SmilesWriteError(
            "round_trip_mismatch",
            f"declared SMILES round-trip projection failed: {mismatches}",
        )

    input_observation_sha256 = source_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    reparsed_observation_sha256 = reparsed_ingest.system.provenance.metadata.get(
        "parser_observation_sha256"
    )
    if (
        type(input_observation_sha256) is not str
        or type(reparsed_observation_sha256) is not str
    ):
        raise SmilesWriteError(
            "stale_parser_observation_digest",
            "round-trip parser observation digests are missing",
        )
    report = SmilesRoundTripReport(
        input_source_sha256=input_source_sha256,
        input_snapshot_sha256=canonical_all_atom_snapshot_digest(source_ingest.system),
        input_topology_sha256=source_state.canonical_topology_sha256,
        input_ordered_topology_sha256=source_state.ordered_topology_sha256,
        input_representable_state_sha256=input_state_sha256,
        input_cycle_projection_sha256=source_state.cycle_projection_sha256,
        input_aromatic_projection_sha256=(source_state.aromatic_projection_sha256),
        input_ez_stereo_projection_sha256=(source_state.ez_stereo_projection_sha256),
        input_tetrahedral_stereo_projection_sha256=(
            source_state.tetrahedral_stereo_projection_sha256
        ),
        input_parser_observation_sha256=input_observation_sha256,
        writer_receipt_sha256=write_result.receipt.receipt_sha256,
        emitted_source_sha256=write_result.receipt.output_source_sha256,
        reparsed_snapshot_sha256=canonical_all_atom_snapshot_digest(
            reparsed_ingest.system
        ),
        reparsed_topology_sha256=reparsed_state.canonical_topology_sha256,
        reparsed_ordered_topology_sha256=reparsed_state.ordered_topology_sha256,
        reparsed_representable_state_sha256=reparsed_state_sha256,
        reparsed_cycle_projection_sha256=reparsed_state.cycle_projection_sha256,
        reparsed_aromatic_projection_sha256=(reparsed_state.aromatic_projection_sha256),
        reparsed_ez_stereo_projection_sha256=(
            reparsed_state.ez_stereo_projection_sha256
        ),
        reparsed_tetrahedral_stereo_projection_sha256=(
            reparsed_state.tetrahedral_stereo_projection_sha256
        ),
        reparsed_parser_observation_sha256=reparsed_observation_sha256,
        reemitted_source_sha256=hashlib.sha256(reemitted.payload).hexdigest(),
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )
    return SmilesRoundTripResult(
        source_ingest=source_ingest,
        write_result=write_result,
        reparsed_ingest=reparsed_ingest,
        report=report,
        _factory_token=_ARTIFACT_FACTORY_TOKEN,
    )


__all__ = [
    "SMILES_AROMATIC_RING_PROJECTION_SCHEMA_ID",
    "SMILES_COMPONENT_CYCLE_PROJECTION_SCHEMA_ID",
    "SMILES_EZ_STEREO_PROJECTION_SCHEMA_ID",
    "SMILES_TETRAHEDRAL_STEREO_PROJECTION_SCHEMA_ID",
    "SMILES_REPRESENTABLE_STATE_SCHEMA_ID",
    "SMILES_ROUND_TRIP_REPORT_SCHEMA_ID",
    "SMILES_WRITER_VERSION",
    "SMILES_WRITE_RECEIPT_SCHEMA_ID",
    "SmilesRoundTripReport",
    "SmilesRoundTripResult",
    "SmilesWriteError",
    "SmilesWriteReceipt",
    "SmilesWriteResult",
    "round_trip_smiles_source",
    "serialize_smiles",
    "smiles_representable_state_sha256",
    "write_smiles",
]
