"""Exact ALA/GLY heavy-to-fixed-neutral-all-atom completion profile.

Only the five-category source accepted by
``parse_mmcif_archive_standard_l_peptide_topology`` is admitted.  The archive
child owns heavy identities and its sequence-implied heavy graph.  This module
then applies one hash-pinned, engine-owned ALA/GLY completion rule: source heavy
atoms are retained exactly once, role-active hydrogens are placed in a local
N--CA--C frame, and every output formal charge is assigned zero for the fixed
profile microstate.

The coordinate checks below are admission checks for this deliberately narrow
transform, not scientific geometry validation.  In particular, the transform
does not assess angles, omega, clashes, environmental pH, protonation
correctness, parameterability, physics, runtime eligibility, or claim safety.
It has no outer-source writer; replay always starts from the retained raw
source bytes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import struct
from typing import Any
import weakref

import torch

from .mmcif_archive_standard_l_peptide_topology import (
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_INPUT_BYTES,
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_SOURCE_ID_BYTES,
    MmcifArchiveStandardLPeptideTopologyError,
    MmcifArchiveStandardLPeptideTopologyIngestResult,
    parse_mmcif_archive_standard_l_peptide_topology,
)
from .models import (
    AllAtomSystem,
    Atom,
    Bond,
    Chain,
    Residue,
    atomic_number_for_element,
)
from .observation import (
    attach_parser_observation_digest,
    attached_parser_observation_sha256_matches,
)
from .serialization import deserialize_all_atom_system, serialize_all_atom_system
from .standard_l_peptide_completion_rules import (
    STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256,
    STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION,
    StandardLPeptideCompletionRuleError,
    standard_l_peptide_completion_component_rule,
    standard_l_peptide_completion_role_rule,
    validate_standard_l_peptide_completion_rule_manifest,
)
from .topology import (
    CANONICAL_TOPOLOGY_SCHEMA_ID,
    attached_canonical_topology_sha256_matches,
    canonical_topology_sha256,
)
from .validation import validate_all_atom_system


MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_VERSION = "1.0.0"
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID = (
    "strict_mmcif_ALA_GLY_heavy_complete_fixed_neutral_microstate_completion/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID = (
    "exact_ALA_GLY_heavy_to_fixed_neutral_microstate_completion_policy/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_NAME = (
    "betelgeuze_engine_v2.molecular.mmcif_standard_l_peptide_heavy_completion."
    "complete_mmcif_standard_l_peptide_heavy_neutral_microstate"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_VERSION = "1.0.0"
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_heavy_completion_atom_mapping/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_heavy_completion_parameter_requirements/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_REPORT_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_heavy_completion_report/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_heavy_completion_source_binding/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_STATE_SCHEMA_ID = (
    "betelgeuze.mmcif_standard_l_peptide_heavy_completion_state/1.0.0"
)
MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY = (
    "mmcif_standard_l_peptide_heavy_completion"
)

MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_INPUT_BYTES = (
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_INPUT_BYTES
)
MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_ID_BYTES = (
    MAX_MMCIF_ARCHIVE_STANDARD_L_PEPTIDE_SOURCE_ID_BYTES
)
MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ATOMS = 80_000
MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_BONDS = 120_000
MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ANGLES = 1_000_000
MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROPERS = 1_000_000

_ARCHIVE_MARKER_KEY = "mmcif_archive_standard_l_peptide_topology"
_FACTORY_TOKEN = object()
_ARTIFACT_ANCHORS: dict[int, tuple[weakref.ReferenceType[Any], bytes]] = {}

_PROFILE_TRUE_FIELDS = (
    "archive_heavy_source_independently_accepted",
    "completion_rule_manifest_matched",
    "source_heavy_graph_preserved",
    "source_heavy_coordinates_binary64_preserved",
    "profile_geometry_admission_assessed",
    "profile_geometry_admission_satisfied",
    "role_specific_hydrogen_completion_applied",
    "fixed_neutral_microstate_formal_charges_assigned",
    "profile_heavy_completion_assessed",
    "profile_heavy_completion_ready",
    "profile_molecular_preparation_assessed",
    "profile_molecular_preparation_ready",
)
_FALSE_AUTHORITY_FIELDS = (
    "source_authenticated",
    "source_observed_covalence_established",
    "scientific_geometry_validated",
    "angles_validated",
    "omega_validated",
    "clashes_assessed",
    "environmental_ph_assessed",
    "environmental_protonation_correctness_assessed",
    "generic_hydrogen_completion_assessed",
    "independent_tautomer_assessed",
    "independent_aromaticity_assessed",
    "independent_cip_assessed",
    "modified_residue_supported",
    "nonstandard_monomer_supported",
    "water_role_assessed",
    "ion_role_assessed",
    "metal_role_or_coordination_assessed",
    "cofactor_role_assessed",
    "generic_chemistry_supported",
    "preparation_ready",
    "generic_preparation_ready",
    "generic_molecular_preparation_ready",
    "global_preparation_ready",
    "global_molecular_preparation_ready",
    "parameterability_assessed",
    "parameterizable",
    "production_parameter_set_available",
    "physics_supported",
    "runtime_eligible",
    "energy_supported",
    "force_supported",
    "minimization_supported",
    "simulation_ready",
    "execution_authorized",
    "claim_safe",
    "outer_source_writer_available",
    "general_mmcif_round_trip_evidence_ready",
    "all_format_round_trip_evidence_ready",
    "v2_1_complete",
)


class MmcifStandardLPeptideHeavyCompletionError(ValueError):
    """Stable failure for the exact heavy-completion profile."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code)
        self.detail = str(message)
        super().__init__(
            f"mmcif_standard_l_peptide_heavy_completion:{self.code}: {self.detail}"
        )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_id_sha256(source_id: str) -> str:
    if type(source_id) is not str:
        raise TypeError("source_id must be a string")
    try:
        encoded = source_id.encode("utf-8")
    except UnicodeError:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "invalid_source_id", "source identifier must contain Unicode scalar values"
        ) from None
    if len(encoded) > MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_ID_BYTES:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "source_id_too_large", "source identifier exceeds the byte limit"
        )
    return _sha256_bytes(encoded)


def _profile_true_document() -> dict[str, bool]:
    return {name: True for name in _PROFILE_TRUE_FIELDS}


def _authority_false_document() -> dict[str, bool]:
    return {name: False for name in _FALSE_AUTHORITY_FIELDS}


def _register_anchor(value: Any, binding: bytes) -> None:
    object_id = id(value)

    def discard(reference: weakref.ReferenceType[Any]) -> None:
        current = _ARTIFACT_ANCHORS.get(object_id)
        if current is not None and current[0] is reference:
            _ARTIFACT_ANCHORS.pop(object_id, None)

    reference = weakref.ref(value, discard)
    _ARTIFACT_ANCHORS[object_id] = (reference, binding)


def _validate_anchor(value: Any, binding: bytes) -> None:
    current = _ARTIFACT_ANCHORS.get(id(value))
    if current is None or current[0]() is not value or current[1] != binding:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "stale_artifact_binding", "factory artifact identity binding is stale"
        )


def _validate_rule_manifest() -> None:
    try:
        computed = validate_standard_l_peptide_completion_rule_manifest()
    except StandardLPeptideCompletionRuleError:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "completion_rule_manifest_hash_mismatch",
            "runtime completion rules differ from their literal hash pin",
        ) from None
    if computed != STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "completion_rule_manifest_hash_mismatch",
            "runtime completion rules differ from their literal hash pin",
        )


def _raise_profile(code: str, detail: str) -> None:
    raise MmcifStandardLPeptideHeavyCompletionError(code, detail)


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", float(value)).hex()


def _distance(left: torch.Tensor, right: torch.Tensor) -> float:
    value = float(torch.linalg.vector_norm(left - right).item())
    if not math.isfinite(value):
        _raise_profile(
            "nonfinite_source_geometry", "source geometry must be finite binary64"
        )
    return value


def _ideal_coordinate(atom_rule: Any) -> torch.Tensor:
    try:
        coordinate = torch.tensor(
            (
                float(atom_rule.ideal_x_token),
                float(atom_rule.ideal_y_token),
                float(atom_rule.ideal_z_token),
            ),
            dtype=torch.float64,
            device="cpu",
        )
    except (TypeError, ValueError, OverflowError):
        _raise_profile(
            "invalid_completion_rule_coordinate",
            "completion rule ideal-coordinate tokens are invalid",
        )
    if not bool(torch.isfinite(coordinate).all()):
        _raise_profile(
            "invalid_completion_rule_coordinate",
            "completion rule ideal-coordinate tokens must be finite",
        )
    return coordinate


def _orthonormal_frame(
    coordinate_by_atom_id: Mapping[str, torch.Tensor],
    *,
    failure_code: str,
) -> torch.Tensor:
    anchors = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT.frame_anchor_atom_ids
    if anchors != ("N", "CA", "C"):
        _raise_profile(
            "completion_geometry_contract_mismatch",
            "the v1 completion frame must be the literal N--CA--C frame",
        )
    try:
        n, ca, c = (coordinate_by_atom_id[atom_id] for atom_id in anchors)
    except KeyError:
        _raise_profile(failure_code, "frame anchor atom is missing")
    first = n - ca
    second = c - ca
    first_norm = torch.linalg.vector_norm(first)
    second_norm = torch.linalg.vector_norm(second)
    cross = torch.linalg.cross(first, second)
    cross_norm = torch.linalg.vector_norm(cross)
    values = (first_norm, second_norm, cross_norm)
    if not all(
        bool(torch.isfinite(value)) and float(value.item()) > 0.0 for value in values
    ):
        _raise_profile(failure_code, "N--CA--C frame is nonfinite or degenerate")
    sine = float((cross_norm / (first_norm * second_norm)).item())
    if (
        not math.isfinite(sine)
        or sine
        < STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT.normalized_frame_sine_minimum
    ):
        _raise_profile(
            failure_code,
            "N--CA--C frame fails the normalized-sine admission threshold",
        )
    axis_x = first / first_norm
    orthogonal = second - torch.dot(second, axis_x) * axis_x
    orthogonal_norm = torch.linalg.vector_norm(orthogonal)
    if not bool(torch.isfinite(orthogonal_norm)) or float(orthogonal_norm.item()) <= 0:
        _raise_profile(failure_code, "N--CA--C frame is degenerate")
    axis_y = orthogonal / orthogonal_norm
    axis_z = torch.linalg.cross(axis_x, axis_y)
    frame = torch.stack((axis_x, axis_y, axis_z), dim=1)
    if not bool(torch.isfinite(frame).all()):
        _raise_profile(failure_code, "N--CA--C frame is nonfinite")
    return frame


def _normalized_ala_triple(coordinate_by_atom_id: Mapping[str, torch.Tensor]) -> float:
    contract = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT
    center = coordinate_by_atom_id[contract.ala_orientation_center_atom_id]
    first, second, third = (
        coordinate_by_atom_id[atom_id] - center
        for atom_id in contract.ala_orientation_ordered_atom_ids
    )
    denominator = (
        torch.linalg.vector_norm(first)
        * torch.linalg.vector_norm(second)
        * torch.linalg.vector_norm(third)
    )
    if not bool(torch.isfinite(denominator)) or float(denominator.item()) <= 0.0:
        _raise_profile(
            "ala_orientation_degenerate",
            "ALA orientation vectors are nonfinite or degenerate",
        )
    value = float(
        (torch.dot(torch.linalg.cross(first, second), third) / denominator).item()
    )
    if not math.isfinite(value):
        _raise_profile(
            "ala_orientation_degenerate", "ALA orientation value is nonfinite"
        )
    return value


@dataclass(frozen=True, slots=True)
class _ResidueInstance:
    chain_order: int
    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    role: str
    source_chain_index: int
    source_residue_index: int


@dataclass(frozen=True, slots=True)
class _OutputIdentity:
    prepared_index: int
    source_index: int | None
    source_serial: int | None
    asym_id: str
    entity_id: str
    sequence_number: int
    component_id: str
    role: str
    atom_id: str
    element: str
    origin: str
    parent_atom_id: str | None


@dataclass(frozen=True, slots=True)
class _TransformOutput:
    system: AllAtomSystem
    mapping_bytes: bytes
    parameter_inventory_bytes: bytes
    identities: tuple[_OutputIdentity, ...]
    source_heavy_atom_count: int
    generated_hydrogen_count: int
    source_heavy_bond_count: int
    generated_hydrogen_bond_count: int
    peptide_bond_count: int


def _instances(system: AllAtomSystem) -> tuple[_ResidueInstance, ...]:
    instances: list[_ResidueInstance] = []
    observed_residues: set[int] = set()
    for chain_order, chain in enumerate(system.chains):
        residues = sorted(
            (system.residues[index] for index in chain.residue_indices),
            key=lambda residue: residue.sequence_number,
        )
        if not residues:
            _raise_profile(
                "empty_source_chain", "archive source chain must not be empty"
            )
        if tuple(residue.sequence_number for residue in residues) != tuple(
            range(1, len(residues) + 1)
        ):
            _raise_profile(
                "noncontiguous_source_sequence",
                "archive source chain sequence numbers must be contiguous from one",
            )
        for position, residue in enumerate(residues):
            if residue.index in observed_residues:
                _raise_profile(
                    "duplicate_source_residue",
                    "archive source residue must belong to exactly one chain",
                )
            observed_residues.add(residue.index)
            role = (
                "singleton"
                if len(residues) == 1
                else "n_sequence_boundary"
                if position == 0
                else "c_sequence_boundary"
                if position == len(residues) - 1
                else "internal"
            )
            marker = residue.metadata.get(_ARCHIVE_MARKER_KEY, {})
            if (
                residue.chain_index != chain.index
                or residue.entity_type != "polymer"
                or residue.insertion_code
                or marker.get("asym_id") != chain.chain_id
                or marker.get("component_id") != residue.name
                or marker.get("sequence_number") != residue.sequence_number
                or marker.get("sequence_role") != role
            ):
                _raise_profile(
                    "archive_residue_binding_mismatch",
                    "archive residue metadata differs from canonical chain/sequence state",
                )
            try:
                standard_l_peptide_completion_role_rule(residue.name, role)
            except StandardLPeptideCompletionRuleError:
                _raise_profile(
                    "unsupported_source_component",
                    "only exact ALA/GLY completion roles are admitted",
                )
            instances.append(
                _ResidueInstance(
                    chain_order=chain_order,
                    asym_id=chain.chain_id,
                    entity_id=chain.entity_id,
                    sequence_number=residue.sequence_number,
                    component_id=residue.name,
                    role=role,
                    source_chain_index=chain.index,
                    source_residue_index=residue.index,
                )
            )
    if observed_residues != {residue.index for residue in system.residues}:
        _raise_profile(
            "source_residue_partition_mismatch",
            "archive residues are not partitioned by archive chains",
        )
    return tuple(instances)


def _source_atom_maps(
    system: AllAtomSystem,
    instances: tuple[_ResidueInstance, ...],
) -> tuple[
    dict[int, dict[str, Atom]],
    dict[tuple[int, tuple[str, str]], Bond],
    dict[tuple[int, int], Bond],
]:
    atoms_by_residue: dict[int, dict[str, Atom]] = {}
    instance_by_residue = {
        instance.source_residue_index: instance for instance in instances
    }
    for residue in system.residues:
        observed: dict[str, Atom] = {}
        for atom_index in residue.atom_indices:
            atom = system.atoms[atom_index]
            if atom.residue_index != residue.index or atom.name in observed:
                _raise_profile(
                    "source_atom_partition_mismatch",
                    "archive heavy atoms must partition into unique residue identities",
                )
            if (
                atom.element == "H"
                or atom.formal_charge_known is not False
                or atom.partial_charge_e is not None
                or atom.altloc
            ):
                _raise_profile(
                    "source_atom_state_mismatch",
                    "completion input must be the archive profile's unknown-charge heavy state",
                )
            marker = atom.metadata.get(_ARCHIVE_MARKER_KEY, {})
            instance = instance_by_residue[residue.index]
            if (
                marker.get("asym_id") != instance.asym_id
                or marker.get("sequence_number") != instance.sequence_number
                or marker.get("component_id") != instance.component_id
                or marker.get("atom_id") != atom.name
                or marker.get("sequence_role") != instance.role
            ):
                _raise_profile(
                    "archive_atom_binding_mismatch",
                    "archive atom metadata differs from canonical residue identity",
                )
            observed[atom.name] = atom
        atoms_by_residue[residue.index] = observed

    intra: dict[tuple[int, tuple[str, str]], Bond] = {}
    inter: dict[tuple[int, int], Bond] = {}
    for bond in system.bonds:
        left = system.atoms[bond.atom_i]
        right = system.atoms[bond.atom_j]
        if left.residue_index == right.residue_index:
            key = (
                left.residue_index,
                tuple(sorted((left.name, right.name))),
            )
            if key in intra:
                _raise_profile(
                    "duplicate_source_heavy_bond",
                    "archive source contains duplicate heavy bond endpoints",
                )
            intra[key] = bond
        else:
            key = tuple(sorted((left.residue_index, right.residue_index)))
            if key in inter:
                _raise_profile(
                    "duplicate_source_peptide_bond",
                    "archive source contains duplicate inter-residue endpoints",
                )
            inter[key] = bond
    return atoms_by_residue, intra, inter


def _validate_source_and_geometry(
    system: AllAtomSystem,
    instances: tuple[_ResidueInstance, ...],
) -> tuple[
    dict[int, dict[str, Atom]],
    dict[int, torch.Tensor],
    dict[int, torch.Tensor],
    dict[tuple[int, tuple[str, str]], Bond],
    dict[tuple[int, int], Bond],
]:
    validation = validate_all_atom_system(system)
    if validation.errors:
        _raise_profile(
            "invalid_archive_source_system",
            "archive child returned a system that violates canonical invariants",
        )
    if (
        system.model_count != 1
        or system.cell is not None
        or system.coordinate_unit != "angstrom"
        or system.coordinates.dtype != torch.float64
        or system.coordinates.device.type != "cpu"
        or not bool(torch.isfinite(system.coordinates).all())
    ):
        _raise_profile(
            "unsupported_archive_coordinate_state",
            "completion requires one finite nonperiodic CPU binary64 angstrom model",
        )
    if not attached_canonical_topology_sha256_matches(system):
        _raise_profile(
            "archive_topology_binding_mismatch",
            "archive canonical topology attachment is stale",
        )
    if not attached_parser_observation_sha256_matches(system):
        _raise_profile(
            "archive_observation_binding_mismatch",
            "archive parser observation attachment is stale",
        )
    atoms_by_residue, source_intra, source_inter = _source_atom_maps(system, instances)
    source_frames: dict[int, torch.Tensor] = {}
    ideal_frames: dict[int, torch.Tensor] = {}
    expected_intra_keys: set[tuple[int, tuple[str, str]]] = set()
    expected_inter_keys: set[tuple[int, int]] = set()
    contract = STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT

    for instance in instances:
        component = standard_l_peptide_completion_component_rule(instance.component_id)
        role = standard_l_peptide_completion_role_rule(
            instance.component_id, instance.role
        )
        source_atoms = atoms_by_residue[instance.source_residue_index]
        if tuple(sorted(source_atoms)) != tuple(
            sorted(role.required_source_heavy_atom_ids)
        ):
            _raise_profile(
                "source_heavy_atom_inventory_mismatch",
                "archive residue heavy inventory differs from the completion role",
            )
        source_coordinates = {
            atom_id: system.coordinates[0, atom.index].clone()
            for atom_id, atom in source_atoms.items()
        }
        atom_rule_by_id = {atom.atom_id: atom for atom in component.atoms}
        ideal_coordinates = {
            atom_id: _ideal_coordinate(atom_rule_by_id[atom_id])
            for atom_id in role.output_atom_ids
        }
        source_frames[instance.source_residue_index] = _orthonormal_frame(
            source_coordinates, failure_code="source_frame_degenerate"
        )
        ideal_frames[instance.source_residue_index] = _orthonormal_frame(
            ideal_coordinates, failure_code="completion_rule_frame_degenerate"
        )

        if instance.component_id == "ALA":
            source_triple = _normalized_ala_triple(source_coordinates)
            ideal_triple = _normalized_ala_triple(ideal_coordinates)
            minimum = contract.ala_normalized_absolute_triple_product_minimum
            expected_positive = contract.ala_orientation_ideal_sign == "positive"
            if (
                abs(source_triple) < minimum
                or abs(ideal_triple) < minimum
                or (source_triple > 0) != expected_positive
                or (source_triple > 0) != (ideal_triple > 0)
            ):
                _raise_profile(
                    "ala_orientation_mismatch",
                    "ALA source orientation differs from the pinned ideal orientation",
                )

        active_heavy = frozenset(role.required_source_heavy_atom_ids)
        for rule_bond in component.source_heavy_bonds:
            if not {rule_bond.atom_id_1, rule_bond.atom_id_2}.issubset(active_heavy):
                continue
            pair = tuple(sorted((rule_bond.atom_id_1, rule_bond.atom_id_2)))
            key = (instance.source_residue_index, pair)
            expected_intra_keys.add(key)
            source_bond = source_intra.get(key)
            expected_order = {"SING": 1.0, "DOUB": 2.0}.get(rule_bond.value_order)
            if (
                source_bond is None
                or expected_order is None
                or source_bond.order != expected_order
                or source_bond.aromatic
            ):
                _raise_profile(
                    "source_heavy_graph_mismatch",
                    "archive heavy graph differs from the completion rule",
                )
            source_length = _distance(
                source_coordinates[rule_bond.atom_id_1],
                source_coordinates[rule_bond.atom_id_2],
            )
            ideal_length = _distance(
                ideal_coordinates[rule_bond.atom_id_1],
                ideal_coordinates[rule_bond.atom_id_2],
            )
            if (
                abs(source_length - ideal_length)
                > contract.heavy_bond_absolute_tolerance_angstrom
            ):
                _raise_profile(
                    "source_heavy_bond_distance_out_of_range",
                    "source heavy bond exceeds the pinned ideal-length tolerance",
                )

    for chain in system.chains:
        residues = sorted(
            (system.residues[index] for index in chain.residue_indices),
            key=lambda residue: residue.sequence_number,
        )
        for left_residue, right_residue in zip(residues, residues[1:]):
            key = tuple(sorted((left_residue.index, right_residue.index)))
            expected_inter_keys.add(key)
            source_bond = source_inter.get(key)
            left_atom = atoms_by_residue[left_residue.index][
                contract.same_asym_adjacent_left_atom_id
            ]
            right_atom = atoms_by_residue[right_residue.index][
                contract.same_asym_adjacent_right_atom_id
            ]
            if source_bond is None or {
                source_bond.atom_i,
                source_bond.atom_j,
            } != {left_atom.index, right_atom.index}:
                _raise_profile(
                    "source_peptide_graph_mismatch",
                    "archive sequence-adjacent peptide bond differs from the profile",
                )
            link_distance = _distance(
                system.coordinates[0, left_atom.index],
                system.coordinates[0, right_atom.index],
            )
            if not (
                contract.same_asym_adjacent_c_n_minimum_distance_angstrom
                <= link_distance
                <= contract.same_asym_adjacent_c_n_maximum_distance_angstrom
            ):
                _raise_profile(
                    "source_peptide_c_n_distance_out_of_range",
                    "sequence-adjacent C--N distance is outside the profile bounds",
                )
    if (
        set(source_intra) != expected_intra_keys
        or set(source_inter) != expected_inter_keys
    ):
        _raise_profile(
            "source_heavy_graph_mismatch",
            "archive heavy graph has missing, extra, or cross-chain bonds",
        )
    return (
        atoms_by_residue,
        source_frames,
        ideal_frames,
        source_intra,
        source_inter,
    )


def _parameter_inventory_document(
    system: AllAtomSystem,
    identities: tuple[_OutputIdentity, ...],
) -> dict[str, Any]:
    identity_by_index = {identity.prepared_index: identity for identity in identities}
    neighbors: list[list[int]] = [[] for _ in system.atoms]
    for bond in system.bonds:
        neighbors[bond.atom_i].append(bond.atom_j)
        neighbors[bond.atom_j].append(bond.atom_i)
    for values in neighbors:
        values.sort()

    angles: list[dict[str, int]] = []
    for center, values in enumerate(neighbors):
        for offset, atom_i in enumerate(values):
            for atom_k in values[offset + 1 :]:
                angles.append({"atom_i": atom_i, "atom_j": center, "atom_k": atom_k})
                if len(angles) > MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ANGLES:
                    _raise_profile(
                        "too_many_parameter_angle_requirements",
                        "angle requirement count exceeds the hard cap",
                    )

    proper_paths: set[tuple[int, int, int, int]] = set()
    for bond in system.bonds:
        atom_j, atom_k = bond.atom_i, bond.atom_j
        for atom_i in neighbors[atom_j]:
            if atom_i == atom_k:
                continue
            for atom_l in neighbors[atom_k]:
                if atom_l in {atom_i, atom_j}:
                    continue
                forward = (atom_i, atom_j, atom_k, atom_l)
                proper_paths.add(min(forward, tuple(reversed(forward))))
                if len(proper_paths) > (
                    MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROPERS
                ):
                    _raise_profile(
                        "too_many_parameter_proper_requirements",
                        "proper requirement count exceeds the hard cap",
                    )

    atom_requirements = [
        {
            "prepared_index": identity.prepared_index,
            "asym_id": identity.asym_id,
            "sequence_number": identity.sequence_number,
            "component_id": identity.component_id,
            "sequence_role": identity.role,
            "atom_id": identity.atom_id,
            "element": identity.element,
            "formal_charge": 0,
            "partial_charge_parameter_required": True,
            "nonbonded_parameter_required": True,
        }
        for identity in identities
    ]
    bond_requirements = [
        {
            "bond_index": bond.index,
            "atom_i": bond.atom_i,
            "atom_j": bond.atom_j,
            "atom_id_i": identity_by_index[bond.atom_i].atom_id,
            "atom_id_j": identity_by_index[bond.atom_j].atom_id,
            "order_ieee754_binary64_be": _binary64_hex(bond.order),
        }
        for bond in system.bonds
    ]
    proper_requirements = [
        {
            "atom_i": path[0],
            "atom_j": path[1],
            "atom_k": path[2],
            "atom_l": path[3],
        }
        for path in sorted(proper_paths)
    ]
    return {
        "schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "inventory_semantics": (
            "bounded_exact_instance_requirements_not_force_field_types_or_parameters"
        ),
        "production_parameter_set_status": "missing",
        "atom_requirements": atom_requirements,
        "bond_requirements": bond_requirements,
        "angle_requirements": angles,
        "proper_torsion_requirements": proper_requirements,
        "nonbonded_site_count": len(atom_requirements),
        "partial_charge_site_count": len(atom_requirements),
        "improper_torsions_enumerated": False,
        "cmap_terms_enumerated": False,
        "parameterability_assessed": False,
        "parameterizable": False,
        "production_parameter_set_available": False,
    }


def _transform_system(
    raw_source: bytes,
    source_id: str,
    archive: MmcifArchiveStandardLPeptideTopologyIngestResult,
) -> _TransformOutput:
    source = archive.system
    instances = _instances(source)
    (
        source_atoms_by_residue,
        source_frames,
        ideal_frames,
        source_intra,
        source_inter,
    ) = _validate_source_and_geometry(source, instances)

    prepared_atoms: list[Atom] = []
    prepared_coordinates: list[torch.Tensor] = []
    prepared_residues: list[Residue] = []
    prepared_chains: list[Chain] = []
    identities: list[_OutputIdentity] = []
    mapping_rows: list[dict[str, Any]] = []
    endpoint_by_identity: dict[tuple[str, int, str], int] = {}
    residue_index_by_source: dict[int, int] = {}

    for instance in instances:
        if instance.source_residue_index not in residue_index_by_source:
            residue_index_by_source[instance.source_residue_index] = len(
                residue_index_by_source
            )
        prepared_residue_index = residue_index_by_source[instance.source_residue_index]
        component = standard_l_peptide_completion_component_rule(instance.component_id)
        role = standard_l_peptide_completion_role_rule(
            instance.component_id, instance.role
        )
        atom_rule_by_id = {atom.atom_id: atom for atom in component.atoms}
        active_atom_rules = tuple(
            sorted(
                (atom_rule_by_id[atom_id] for atom_id in role.output_atom_ids),
                key=lambda atom: atom.ccd_ordinal,
            )
        )
        source_atoms = source_atoms_by_residue[instance.source_residue_index]
        source_coordinate_by_id = {
            atom_id: source.coordinates[0, atom.index]
            for atom_id, atom in source_atoms.items()
        }
        ideal_coordinate_by_id = {
            atom.atom_id: _ideal_coordinate(atom) for atom in component.atoms
        }
        residue_atom_indices: list[int] = []
        for atom_rule in active_atom_rules:
            prepared_index = len(prepared_atoms)
            residue_atom_indices.append(prepared_index)
            source_atom = source_atoms.get(atom_rule.atom_id)
            if atom_rule.element == "H":
                if source_atom is not None or atom_rule.atom_id not in (
                    role.active_hydrogen_atom_ids
                ):
                    _raise_profile(
                        "hydrogen_generation_partition_mismatch",
                        "role-active hydrogen partition is inconsistent",
                    )
                parent_atom_id = atom_rule.hydrogen_parent_atom_id
                if (
                    parent_atom_id is None
                    or parent_atom_id not in source_coordinate_by_id
                ):
                    _raise_profile(
                        "hydrogen_parent_not_active",
                        "generated hydrogen parent must be an active source heavy atom",
                    )
                local_vector = ideal_frames[instance.source_residue_index].transpose(
                    0, 1
                ) @ (
                    ideal_coordinate_by_id[atom_rule.atom_id]
                    - ideal_coordinate_by_id[parent_atom_id]
                )
                coordinate = source_coordinate_by_id[parent_atom_id] + (
                    source_frames[instance.source_residue_index] @ local_vector
                )
                if not bool(torch.isfinite(coordinate).all()):
                    _raise_profile(
                        "generated_coordinate_nonfinite",
                        "generated hydrogen coordinate must be finite",
                    )
                atom = Atom(
                    index=prepared_index,
                    name=atom_rule.atom_id,
                    element="H",
                    atomic_number=atomic_number_for_element("H"),
                    residue_index=prepared_residue_index,
                    formal_charge=0,
                    formal_charge_known=True,
                    partial_charge_e=None,
                    serial=None,
                    aromatic=False,
                    stereo="unspecified",
                    metadata={
                        "formal_charge_source": (
                            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID
                        ),
                        "hydrogen_origin": "profile_generated",
                        MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                            "origin": "profile_generated",
                            "profile_id": (
                                MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID
                            ),
                            "rule_id": component.rule_id,
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                            ),
                            "component_id": instance.component_id,
                            "asym_id": instance.asym_id,
                            "sequence_number": instance.sequence_number,
                            "sequence_role": instance.role,
                            "atom_id": atom_rule.atom_id,
                            "hydrogen_parent_atom_id": parent_atom_id,
                            "frame_anchor_atom_ids": list(
                                component.frame_anchor_atom_ids
                            ),
                        },
                    },
                )
                identity = _OutputIdentity(
                    prepared_index=prepared_index,
                    source_index=None,
                    source_serial=None,
                    asym_id=instance.asym_id,
                    entity_id=instance.entity_id,
                    sequence_number=instance.sequence_number,
                    component_id=instance.component_id,
                    role=instance.role,
                    atom_id=atom_rule.atom_id,
                    element="H",
                    origin="profile_generated",
                    parent_atom_id=parent_atom_id,
                )
                mapping_rows.append(
                    {
                        "prepared_index": prepared_index,
                        "status": "profile_generated",
                        "asym_id": instance.asym_id,
                        "entity_id": instance.entity_id,
                        "sequence_number": instance.sequence_number,
                        "component_id": instance.component_id,
                        "sequence_role": instance.role,
                        "atom_id": atom_rule.atom_id,
                        "element": "H",
                        "generation_parent_atom_id": parent_atom_id,
                        "generation_parent_source_index": source_atoms[
                            parent_atom_id
                        ].index,
                        "generation_anchor_atom_ids": list(
                            component.frame_anchor_atom_ids
                        ),
                        "generation_rule_id": component.rule_id,
                        "generation_rule_atom_ordinal": atom_rule.ccd_ordinal,
                        "generation_rule_manifest_sha256": (
                            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                        ),
                    }
                )
            else:
                if source_atom is None or atom_rule.atom_id not in (
                    role.required_source_heavy_atom_ids
                ):
                    _raise_profile(
                        "source_retention_partition_mismatch",
                        "every active heavy atom must be retained exactly once",
                    )
                coordinate = source.coordinates[0, source_atom.index].clone()
                atom_metadata = dict(source_atom.metadata)
                atom_metadata.update(
                    {
                        "formal_charge_interpretation": (
                            "fixed_profile_neutral_microstate_assignment"
                        ),
                        "formal_charge_known": True,
                        "formal_charge_source": (
                            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID
                        ),
                        MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                            "origin": "source_retained",
                            "profile_id": (
                                MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID
                            ),
                            "rule_id": component.rule_id,
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                            ),
                            "component_id": instance.component_id,
                            "asym_id": instance.asym_id,
                            "sequence_number": instance.sequence_number,
                            "sequence_role": instance.role,
                            "atom_id": atom_rule.atom_id,
                            "source_atom_index": source_atom.index,
                            "source_atom_serial": source_atom.serial,
                        },
                    }
                )
                atom = replace(
                    source_atom,
                    index=prepared_index,
                    residue_index=prepared_residue_index,
                    formal_charge=0,
                    formal_charge_known=True,
                    partial_charge_e=None,
                    stereo=(
                        "S"
                        if instance.component_id == "ALA" and atom_rule.atom_id == "CA"
                        else "unspecified"
                    ),
                    metadata=atom_metadata,
                )
                identity = _OutputIdentity(
                    prepared_index=prepared_index,
                    source_index=source_atom.index,
                    source_serial=source_atom.serial,
                    asym_id=instance.asym_id,
                    entity_id=instance.entity_id,
                    sequence_number=instance.sequence_number,
                    component_id=instance.component_id,
                    role=instance.role,
                    atom_id=atom_rule.atom_id,
                    element=atom_rule.element,
                    origin="source_retained",
                    parent_atom_id=None,
                )
                mapping_rows.append(
                    {
                        "prepared_index": prepared_index,
                        "status": "source_retained",
                        "source_index": source_atom.index,
                        "source_serial": source_atom.serial,
                        "asym_id": instance.asym_id,
                        "entity_id": instance.entity_id,
                        "sequence_number": instance.sequence_number,
                        "component_id": instance.component_id,
                        "sequence_role": instance.role,
                        "atom_id": atom_rule.atom_id,
                        "element": atom_rule.element,
                        "source_coordinate_binary64_be": [
                            _binary64_hex(value) for value in coordinate.tolist()
                        ],
                        "retention_rule_id": component.rule_id,
                        "retention_rule_atom_ordinal": atom_rule.ccd_ordinal,
                        "retention_rule_manifest_sha256": (
                            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                        ),
                    }
                )
            prepared_atoms.append(atom)
            prepared_coordinates.append(coordinate.clone())
            identities.append(identity)
            endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, atom_rule.atom_id)
            ] = prepared_index

        source_residue = source.residues[instance.source_residue_index]
        prepared_residues.append(
            replace(
                source_residue,
                index=prepared_residue_index,
                chain_index=instance.chain_order,
                atom_indices=tuple(residue_atom_indices),
                metadata={
                    **dict(source_residue.metadata),
                    MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
                        "component_id": instance.component_id,
                        "asym_id": instance.asym_id,
                        "sequence_number": instance.sequence_number,
                        "sequence_role": instance.role,
                        "completion_rule_manifest_sha256": (
                            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                        ),
                    },
                },
            )
        )

    for chain_order, source_chain in enumerate(source.chains):
        residue_indices = tuple(
            residue_index_by_source[instance.source_residue_index]
            for instance in instances
            if instance.chain_order == chain_order
        )
        prepared_chains.append(
            replace(
                source_chain,
                index=chain_order,
                residue_indices=residue_indices,
                metadata={
                    **dict(source_chain.metadata),
                    MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
                        "asym_id": source_chain.chain_id,
                        "completion_rule_manifest_sha256": (
                            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                        ),
                    },
                },
            )
        )

    if len(prepared_atoms) > MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ATOMS:
        _raise_profile(
            "too_many_completed_atoms", "completed atom count exceeds the hard cap"
        )
    if sum(identity.origin == "source_retained" for identity in identities) != (
        source.atom_count
    ):
        _raise_profile(
            "source_retention_partition_mismatch",
            "source heavy atoms must map bijectively into the completed system",
        )
    if len(endpoint_by_identity) != len(prepared_atoms):
        _raise_profile(
            "duplicate_completed_atom_identity",
            "completed atom label identities must be unique",
        )

    pending_bonds: list[Bond] = []
    generated_hydrogen_bond_count = 0
    peptide_bond_count = 0
    for instance in instances:
        component = standard_l_peptide_completion_component_rule(instance.component_id)
        role = standard_l_peptide_completion_role_rule(
            instance.component_id, instance.role
        )
        active_atom_ids = frozenset(role.output_atom_ids)
        for rule_bond in component.source_heavy_bonds:
            if not {rule_bond.atom_id_1, rule_bond.atom_id_2}.issubset(active_atom_ids):
                continue
            source_bond = source_intra[
                (
                    instance.source_residue_index,
                    tuple(sorted((rule_bond.atom_id_1, rule_bond.atom_id_2))),
                )
            ]
            left = endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, rule_bond.atom_id_1)
            ]
            right = endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, rule_bond.atom_id_2)
            ]
            pending_bonds.append(
                Bond(
                    index=-1,
                    atom_i=min(left, right),
                    atom_j=max(left, right),
                    order={"SING": 1.0, "DOUB": 2.0}[rule_bond.value_order],
                    aromatic=False,
                    stereo="none",
                    source="profile_retained_archive_heavy_reference",
                    metadata={
                        MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                            "origin": "source_retained",
                            "bond_kind": "intra_residue_heavy",
                            "source_bond_index": source_bond.index,
                            "rule_id": component.rule_id,
                            "rule_bond_ordinal": rule_bond.ccd_ordinal,
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                            ),
                            "asym_id": instance.asym_id,
                            "sequence_number": instance.sequence_number,
                            "atom_id_1": rule_bond.atom_id_1,
                            "atom_id_2": rule_bond.atom_id_2,
                        }
                    },
                )
            )
        atom_rule_by_id = {atom.atom_id: atom for atom in component.atoms}
        for hydrogen_atom_id in role.active_hydrogen_atom_ids:
            parent_atom_id = atom_rule_by_id[hydrogen_atom_id].hydrogen_parent_atom_id
            if parent_atom_id is None:
                _raise_profile(
                    "hydrogen_parent_not_active",
                    "generated hydrogen rule lacks a heavy parent",
                )
            left = endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, parent_atom_id)
            ]
            right = endpoint_by_identity[
                (instance.asym_id, instance.sequence_number, hydrogen_atom_id)
            ]
            pending_bonds.append(
                Bond(
                    index=-1,
                    atom_i=min(left, right),
                    atom_j=max(left, right),
                    order=1.0,
                    aromatic=False,
                    stereo="none",
                    source="profile_generated_standard_l_peptide_completion_rule",
                    metadata={
                        MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                            "origin": "profile_generated",
                            "bond_kind": "generated_hydrogen_parent",
                            "rule_id": component.rule_id,
                            "rule_manifest_sha256": (
                                STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                            ),
                            "asym_id": instance.asym_id,
                            "sequence_number": instance.sequence_number,
                            "parent_atom_id": parent_atom_id,
                            "hydrogen_atom_id": hydrogen_atom_id,
                        }
                    },
                )
            )
            generated_hydrogen_bond_count += 1

    instance_by_source_residue = {
        instance.source_residue_index: instance for instance in instances
    }
    for source_bond in source_inter.values():
        source_left = source.atoms[source_bond.atom_i]
        source_right = source.atoms[source_bond.atom_j]
        left_instance = instance_by_source_residue[source_left.residue_index]
        right_instance = instance_by_source_residue[source_right.residue_index]
        if left_instance.sequence_number > right_instance.sequence_number:
            left_instance, right_instance = right_instance, left_instance
            source_left, source_right = source_right, source_left
        if (
            left_instance.asym_id != right_instance.asym_id
            or right_instance.sequence_number != left_instance.sequence_number + 1
            or source_left.name != "C"
            or source_right.name != "N"
        ):
            _raise_profile(
                "source_peptide_graph_mismatch",
                "only same-asym sequence-adjacent C--N source links are admitted",
            )
        left = endpoint_by_identity[
            (left_instance.asym_id, left_instance.sequence_number, "C")
        ]
        right = endpoint_by_identity[
            (right_instance.asym_id, right_instance.sequence_number, "N")
        ]
        pending_bonds.append(
            Bond(
                index=-1,
                atom_i=min(left, right),
                atom_j=max(left, right),
                order=1.0,
                aromatic=False,
                stereo="none",
                source="profile_retained_archive_heavy_reference",
                metadata={
                    MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: {
                        "origin": "source_retained",
                        "bond_kind": "sequence_adjacent_peptide",
                        "source_bond_index": source_bond.index,
                        "rule_manifest_sha256": (
                            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
                        ),
                        "asym_id": left_instance.asym_id,
                        "left_sequence_number": left_instance.sequence_number,
                        "right_sequence_number": right_instance.sequence_number,
                        "left_atom_id": "C",
                        "right_atom_id": "N",
                    }
                },
            )
        )
        peptide_bond_count += 1

    if len(pending_bonds) > MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_BONDS:
        _raise_profile(
            "too_many_completed_bonds", "completed bond count exceeds the hard cap"
        )
    endpoint_pairs = [(bond.atom_i, bond.atom_j) for bond in pending_bonds]
    if len(endpoint_pairs) != len(set(endpoint_pairs)):
        _raise_profile(
            "duplicate_completed_bond", "completion produced duplicate bond endpoints"
        )
    pending_bonds.sort(key=lambda bond: (bond.atom_i, bond.atom_j))
    prepared_bonds = tuple(
        replace(bond, index=index) for index, bond in enumerate(pending_bonds)
    )

    coordinates = torch.stack(prepared_coordinates, dim=0).unsqueeze(0)
    source_snapshot_sha256 = _sha256_bytes(serialize_all_atom_system(source))
    base_marker = {
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
        "completion_rule_manifest_schema_id": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID
        ),
        "completion_rule_manifest_version": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION
        ),
        "completion_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
        ),
        "geometry_contract_semantics": (
            STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT.semantics
        ),
        "source_hash_semantics": "raw_outer_source_bytes_tamper_evidence",
        **_profile_true_document(),
        **_authority_false_document(),
    }
    provenance = replace(
        source.provenance,
        source_id=source_id,
        source_sha256=_sha256_bytes(raw_source),
        parser_name=MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_NAME,
        parser_version=MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_VERSION,
        operations=(
            "accept_exact_archive_standard_l_peptide_heavy_source/v1",
            "validate_completion_contract_geometry/v1",
            "retain_archive_heavy_graph_and_binary64_coordinates/v1",
            "generate_role_active_fixed_neutral_microstate_hydrogens/v1",
            "assign_profile_owned_known_zero_formal_charges/v1",
        ),
        parent_sha256=(source_snapshot_sha256,),
        preparation_ready=False,
        claim_safe=False,
        metadata={MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: base_marker},
    )
    provisional = AllAtomSystem(
        system_id=f"{source.system_id}:ALA_GLY_heavy_completed_neutral_v1",
        atoms=tuple(prepared_atoms),
        bonds=prepared_bonds,
        residues=tuple(prepared_residues),
        chains=tuple(prepared_chains),
        coordinates=coordinates,
        provenance=provenance,
        cell=None,
        coordinate_unit="angstrom",
        metadata={MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: base_marker},
        schema_id=source.schema_id,
    )
    topology_sha256 = canonical_topology_sha256(provisional)
    mapping_bytes = _canonical_json_bytes(
        {
            "schema_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID,
            "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
            "partition_semantics": (
                "completed_output_equals_source_retained_disjoint_union_profile_generated"
            ),
            "rows": mapping_rows,
        }
    )
    inventory = _parameter_inventory_document(provisional, tuple(identities))
    inventory["canonical_topology_schema_id"] = CANONICAL_TOPOLOGY_SCHEMA_ID
    inventory["canonical_topology_sha256"] = topology_sha256
    parameter_inventory_bytes = _canonical_json_bytes(inventory)
    marker = {
        **base_marker,
        "atom_mapping_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID
        ),
        "atom_mapping_sha256": _sha256_bytes(mapping_bytes),
        "parameter_requirement_inventory_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "parameter_requirement_inventory_sha256": _sha256_bytes(
            parameter_inventory_bytes
        ),
        "source_heavy_atom_count": source.atom_count,
        "completed_atom_count": len(prepared_atoms),
        "generated_hydrogen_count": len(prepared_atoms) - source.atom_count,
        "source_heavy_bond_count": len(source.bonds),
        "completed_bond_count": len(prepared_bonds),
        "generated_hydrogen_bond_count": generated_hydrogen_bond_count,
        "sequence_adjacent_peptide_bond_count": peptide_bond_count,
    }
    system = replace(
        provisional,
        metadata={MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: marker},
        provenance=replace(
            provisional.provenance,
            metadata={
                MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY: marker,
                "canonical_topology_schema_id": CANONICAL_TOPOLOGY_SCHEMA_ID,
                "canonical_topology_sha256": topology_sha256,
            },
        ),
    )
    system = attach_parser_observation_digest(system)
    validation = validate_all_atom_system(system)
    if validation.errors:
        _raise_profile(
            "completed_system_invalid",
            "completed system violates canonical all-atom invariants",
        )
    if not attached_canonical_topology_sha256_matches(system):
        _raise_profile(
            "completed_topology_binding_mismatch",
            "completed canonical topology attachment is stale",
        )
    if not attached_parser_observation_sha256_matches(system):
        _raise_profile(
            "completed_observation_binding_mismatch",
            "completed parser observation attachment is stale",
        )
    return _TransformOutput(
        system=system,
        mapping_bytes=mapping_bytes,
        parameter_inventory_bytes=parameter_inventory_bytes,
        identities=tuple(identities),
        source_heavy_atom_count=source.atom_count,
        generated_hydrogen_count=len(prepared_atoms) - source.atom_count,
        source_heavy_bond_count=len(source.bonds),
        generated_hydrogen_bond_count=generated_hydrogen_bond_count,
        peptide_bond_count=peptide_bond_count,
    )


def _source_binding_document(
    *,
    raw_source: bytes,
    source_id: str,
    archive: MmcifArchiveStandardLPeptideTopologyIngestResult,
    transformed: _TransformOutput,
    prepared_snapshot: bytes,
) -> dict[str, Any]:
    archive_document = archive.to_dict()
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_BINDING_SCHEMA_ID,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
        "raw_source_sha256": _sha256_bytes(raw_source),
        "source_id_sha256": _source_id_sha256(source_id),
        "archive_projection_sha256": archive_document["projection_sha256"],
        "archive_topology_state_sha256": archive_document["topology_state_sha256"],
        "archive_source_binding_sha256": archive_document["source_binding_sha256"],
        "archive_system_snapshot_sha256": archive_document["system_snapshot_sha256"],
        "archive_canonical_topology_sha256": archive_document[
            "canonical_topology_sha256"
        ],
        "completion_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
        ),
        "atom_mapping_sha256": _sha256_bytes(transformed.mapping_bytes),
        "parameter_requirement_inventory_sha256": _sha256_bytes(
            transformed.parameter_inventory_bytes
        ),
        "completed_canonical_topology_sha256": canonical_topology_sha256(
            transformed.system
        ),
        "completed_parser_observation_sha256": transformed.system.provenance.metadata[
            "parser_observation_sha256"
        ],
        "completed_system_snapshot_sha256": _sha256_bytes(prepared_snapshot),
        "source_binding_semantics": (
            "raw_source_recomputed_tamper_evidence_not_source_authentication"
        ),
        "source_authenticated": False,
    }


def _report_document(
    *,
    source_binding: Mapping[str, Any],
    transformed: _TransformOutput,
) -> dict[str, Any]:
    system = transformed.system
    inventory = json.loads(transformed.parameter_inventory_bytes.decode("ascii"))
    role_counts: dict[str, int] = {}
    component_counts: dict[str, int] = {}
    for residue in system.residues:
        marker = residue.metadata[MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY]
        role_counts[marker["sequence_role"]] = (
            role_counts.get(marker["sequence_role"], 0) + 1
        )
        component_counts[marker["component_id"]] = (
            component_counts.get(marker["component_id"], 0) + 1
        )
    if not all(
        atom.formal_charge_known
        and atom.formal_charge == 0
        and atom.partial_charge_e is None
        for atom in system.atoms
    ):
        _raise_profile(
            "completed_charge_policy_mismatch",
            "all completed atoms must have known zero formal charge and no partial charge",
        )
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_REPORT_SCHEMA_ID,
        "schema_version": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_VERSION,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "policy_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
        "claim_scope": "exact_profile_heavy_completion_transform_only",
        "status": "satisfied",
        "microstate_semantics": (
            "fixed_neutral_profile_assignment_not_environmental_ph_or_protonation_correctness"
        ),
        "geometry_semantics": (
            STANDARD_L_PEPTIDE_COMPLETION_GEOMETRY_CONTRACT.semantics
        ),
        "completion_rule_manifest_schema_id": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SCHEMA_ID
        ),
        "completion_rule_manifest_version": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_VERSION
        ),
        "completion_rule_manifest_sha256": (
            STANDARD_L_PEPTIDE_COMPLETION_RULE_MANIFEST_SHA256
        ),
        "source_binding_schema_id": source_binding["schema_id"],
        "source_binding_sha256": _sha256_bytes(_canonical_json_bytes(source_binding)),
        **{
            key: value
            for key, value in source_binding.items()
            if key
            not in {
                "schema_id",
                "profile_id",
                "policy_id",
                "source_authenticated",
            }
        },
        "atom_mapping_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID
        ),
        "parameter_requirement_inventory_schema_id": (
            MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID
        ),
        "source_heavy_atom_count": transformed.source_heavy_atom_count,
        "generated_hydrogen_count": transformed.generated_hydrogen_count,
        "completed_atom_count": system.atom_count,
        "source_heavy_bond_count": transformed.source_heavy_bond_count,
        "generated_hydrogen_bond_count": transformed.generated_hydrogen_bond_count,
        "sequence_adjacent_peptide_bond_count": transformed.peptide_bond_count,
        "completed_bond_count": len(system.bonds),
        "residue_count": len(system.residues),
        "chain_count": len(system.chains),
        "sequence_role_counts": [list(item) for item in sorted(role_counts.items())],
        "component_instance_counts": [
            list(item) for item in sorted(component_counts.items())
        ],
        "all_completed_formal_charges_known_zero": True,
        "completed_net_formal_charge": 0,
        "parameter_atom_requirement_count": len(inventory["atom_requirements"]),
        "parameter_bond_requirement_count": len(inventory["bond_requirements"]),
        "parameter_angle_requirement_count": len(inventory["angle_requirements"]),
        "parameter_proper_requirement_count": len(
            inventory["proper_torsion_requirements"]
        ),
        "improper_torsions_enumerated": False,
        "cmap_terms_enumerated": False,
        "production_parameter_set_status": "missing",
        "parameterability_status": "not_assessed_production_parameter_set_missing",
        "blockers": [
            "source_digest_is_not_authentication",
            "geometry_admission_is_not_scientific_geometry_validation",
            "environmental_ph_and_protonation_correctness_unassessed",
            "angles_omega_and_clashes_unassessed",
            "generic_and_global_preparation_not_ready",
            "production_parameter_set_missing",
            "parameterability_not_assessed",
            "physics_and_runtime_not_supported",
            "execution_and_claim_not_authorized",
            "outer_source_writer_not_available",
            "v2_1_not_complete",
        ],
        **_profile_true_document(),
        **_authority_false_document(),
    }


@dataclass(frozen=True, slots=True)
class _CompletedState:
    raw_source: bytes = field(repr=False)
    source_id: str = field(repr=False)
    archive_snapshot: bytes = field(repr=False)
    completed_snapshot: bytes = field(repr=False)
    mapping_bytes: bytes = field(repr=False)
    parameter_inventory_bytes: bytes = field(repr=False)
    source_binding_bytes: bytes = field(repr=False)
    report_bytes: bytes = field(repr=False)


def _build_state(data: bytes, *, source_id: str) -> _CompletedState:
    if type(data) is not bytes:
        raise TypeError("mmCIF heavy-completion input must be bytes")
    if len(data) > MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_INPUT_BYTES:
        _raise_profile("input_too_large", "input exceeds the profile byte limit")
    _source_id_sha256(source_id)
    _validate_rule_manifest()
    try:
        archive = parse_mmcif_archive_standard_l_peptide_topology(
            data, source_id=source_id
        )
    except MmcifArchiveStandardLPeptideTopologyError as exc:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "archive_heavy_source_rejected",
            f"archive-heavy source rejected the exact input ({exc.code})",
        ) from None
    transformed = _transform_system(data, source_id, archive)
    archive_snapshot = serialize_all_atom_system(archive.system)
    completed_snapshot = serialize_all_atom_system(transformed.system)
    source_binding = _source_binding_document(
        raw_source=data,
        source_id=source_id,
        archive=archive,
        transformed=transformed,
        prepared_snapshot=completed_snapshot,
    )
    source_binding_bytes = _canonical_json_bytes(source_binding)
    report_bytes = _canonical_json_bytes(
        _report_document(source_binding=source_binding, transformed=transformed)
    )
    return _CompletedState(
        raw_source=data,
        source_id=source_id,
        archive_snapshot=archive_snapshot,
        completed_snapshot=completed_snapshot,
        mapping_bytes=transformed.mapping_bytes,
        parameter_inventory_bytes=transformed.parameter_inventory_bytes,
        source_binding_bytes=source_binding_bytes,
        report_bytes=report_bytes,
    )


def _state_document(state: _CompletedState) -> dict[str, Any]:
    report = json.loads(state.report_bytes.decode("ascii"))
    return {
        "schema_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_STATE_SCHEMA_ID,
        "profile_id": MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID,
        "raw_source_sha256": _sha256_bytes(state.raw_source),
        "source_id_sha256": _source_id_sha256(state.source_id),
        "archive_snapshot_sha256": _sha256_bytes(state.archive_snapshot),
        "completed_snapshot_sha256": _sha256_bytes(state.completed_snapshot),
        "mapping_sha256": _sha256_bytes(state.mapping_bytes),
        "parameter_inventory_sha256": _sha256_bytes(state.parameter_inventory_bytes),
        "source_binding_sha256": _sha256_bytes(state.source_binding_bytes),
        "report_sha256": _sha256_bytes(state.report_bytes),
        "completed_canonical_topology_sha256": report[
            "completed_canonical_topology_sha256"
        ],
    }


def _result_access_binding(
    value: "MmcifStandardLPeptideHeavyCompletionResult",
) -> bytes:
    state = value._state
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifStandardLPeptideHeavyCompletionResult",
            "self_object_id": id(value),
            "state_object_id": id(state),
            **_state_document(state),
        }
    )


def _report_access_binding(
    value: "MmcifStandardLPeptideHeavyCompletionReport",
) -> bytes:
    return _canonical_json_bytes(
        {
            "artifact_type": "MmcifStandardLPeptideHeavyCompletionReport",
            "self_object_id": id(value),
            "raw_source_sha256": _sha256_bytes(value._raw_source),
            "source_id_sha256": _source_id_sha256(value._source_id),
            "report_sha256": _sha256_bytes(value._report_bytes),
        }
    )


@dataclass(frozen=True, init=False)
class MmcifStandardLPeptideHeavyCompletionReport:
    """Detached immutable view of a factory-recomputed completion report."""

    _raw_source: bytes = field(repr=False)
    _source_id: str = field(repr=False)
    _report_bytes: bytes = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self,
        raw_source: bytes,
        source_id: str,
        report_bytes: bytes,
        *,
        _factory_token: object | None = None,
    ) -> None:
        if (
            _factory_token is not _FACTORY_TOKEN
            or type(raw_source) is not bytes
            or type(source_id) is not str
            or type(report_bytes) is not bytes
        ):
            raise TypeError(
                "MmcifStandardLPeptideHeavyCompletionReport is factory-only"
            )
        document = json.loads(report_bytes.decode("ascii"))
        if (
            document.get("schema_id")
            != MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_REPORT_SCHEMA_ID
            or document.get("profile_id")
            != MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID
            or any(document.get(name) is not True for name in _PROFILE_TRUE_FIELDS)
            or any(document.get(name) is not False for name in _FALSE_AUTHORITY_FIELDS)
        ):
            _raise_profile(
                "invalid_report_document", "stored report violates the fixed schema"
            )
        object.__setattr__(self, "_raw_source", bytes(raw_source))
        object.__setattr__(self, "_source_id", source_id)
        object.__setattr__(self, "_report_bytes", bytes(report_bytes))
        binding = _report_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def report_sha256(self) -> str:
        return _sha256_bytes(_validate_report(self))

    @property
    def profile_heavy_completion_ready(self) -> bool:
        _validate_report(self)
        return True

    @property
    def profile_molecular_preparation_ready(self) -> bool:
        _validate_report(self)
        return True

    def to_dict(self) -> dict[str, Any]:
        report_bytes = _validate_report(self)
        document = json.loads(report_bytes.decode("ascii"))
        document["report_sha256"] = _sha256_bytes(report_bytes)
        return document


def _validate_report(value: MmcifStandardLPeptideHeavyCompletionReport) -> bytes:
    if type(value) is not MmcifStandardLPeptideHeavyCompletionReport:
        raise TypeError("an exact heavy-completion report is required")
    try:
        binding = _report_access_binding(value)
        _validate_anchor(value, binding)
        if value._access_binding_bytes != binding:
            raise MmcifStandardLPeptideHeavyCompletionError(
                "stale_report_binding", "stored completion report evidence is stale"
            )
        fresh = _build_state(value._raw_source, source_id=value._source_id)
    except MmcifStandardLPeptideHeavyCompletionError:
        raise
    except Exception:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "stale_report_binding", "stored completion report evidence is stale"
        ) from None
    if fresh.report_bytes != value._report_bytes:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "stale_report_binding", "stored completion report evidence is stale"
        )
    return value._report_bytes


@dataclass(frozen=True, init=False)
class MmcifStandardLPeptideHeavyCompletionResult:
    """Factory-only result retaining raw-source replay authority."""

    _state: _CompletedState = field(repr=False)
    _access_binding_bytes: bytes = field(repr=False)

    def __init__(
        self, state: _CompletedState, *, _factory_token: object | None = None
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN or type(state) is not _CompletedState:
            raise TypeError(
                "MmcifStandardLPeptideHeavyCompletionResult is factory-only"
            )
        object.__setattr__(self, "_state", state)
        binding = _result_access_binding(self)
        object.__setattr__(self, "_access_binding_bytes", binding)
        _register_anchor(self, binding)

    @property
    def system(self) -> AllAtomSystem:
        return deserialize_all_atom_system(_validate_result(self).completed_snapshot)

    @property
    def archive_heavy_ingest(
        self,
    ) -> MmcifArchiveStandardLPeptideTopologyIngestResult:
        state = _validate_result(self)
        return parse_mmcif_archive_standard_l_peptide_topology(
            state.raw_source, source_id=state.source_id
        )

    @property
    def report(self) -> MmcifStandardLPeptideHeavyCompletionReport:
        state = _validate_result(self)
        return MmcifStandardLPeptideHeavyCompletionReport(
            state.raw_source,
            state.source_id,
            state.report_bytes,
            _factory_token=_FACTORY_TOKEN,
        )

    @property
    def atom_mapping(self) -> tuple[dict[str, Any], ...]:
        state = _validate_result(self)
        document = json.loads(state.mapping_bytes.decode("ascii"))
        return tuple(dict(row) for row in document["rows"])

    @property
    def parameter_requirement_inventory(self) -> dict[str, Any]:
        state = _validate_result(self)
        return json.loads(state.parameter_inventory_bytes.decode("ascii"))

    @property
    def full_source_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).raw_source)

    @property
    def transformed_topology_sha256(self) -> str:
        return str(self.report.to_dict()["completed_canonical_topology_sha256"])

    @property
    def transformed_system_snapshot_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).completed_snapshot)

    @property
    def state_sha256(self) -> str:
        state = _validate_result(self)
        return _sha256_bytes(_canonical_json_bytes(_state_document(state)))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256_bytes(_validate_result(self).source_binding_bytes)

    def verify_replay(self) -> bool:
        state = _validate_result(self)
        return state == _build_state(state.raw_source, source_id=state.source_id)

    def to_dict(self) -> dict[str, Any]:
        state = _validate_result(self)
        document = json.loads(state.report_bytes.decode("ascii"))
        document.update(
            {
                "report_sha256": _sha256_bytes(state.report_bytes),
                "state_sha256": _sha256_bytes(
                    _canonical_json_bytes(_state_document(state))
                ),
                "result_source_binding_sha256": _sha256_bytes(
                    state.source_binding_bytes
                ),
            }
        )
        return document


def _validate_result(
    value: MmcifStandardLPeptideHeavyCompletionResult,
) -> _CompletedState:
    if type(value) is not MmcifStandardLPeptideHeavyCompletionResult:
        raise TypeError("an exact heavy-completion result is required")
    try:
        state = value._state
        binding = _result_access_binding(value)
        _validate_anchor(value, binding)
        if value._access_binding_bytes != binding:
            raise MmcifStandardLPeptideHeavyCompletionError(
                "stale_result_binding", "stored completion result evidence is stale"
            )
        fresh = _build_state(state.raw_source, source_id=state.source_id)
    except MmcifStandardLPeptideHeavyCompletionError:
        raise
    except Exception:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "stale_result_binding", "stored completion result evidence is stale"
        ) from None
    if state != fresh:
        raise MmcifStandardLPeptideHeavyCompletionError(
            "stale_result_binding", "stored completion result evidence is stale"
        )
    return state


def complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
    data: bytes,
    *,
    source_id: str = "",
    policy_id: str = MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
) -> MmcifStandardLPeptideHeavyCompletionResult:
    """Complete the exact archive-heavy ALA/GLY profile atomically."""

    if policy_id != MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID:
        _raise_profile(
            "unsupported_policy_id", "only the literal v1 completion policy is accepted"
        )
    return MmcifStandardLPeptideHeavyCompletionResult(
        _build_state(data, source_id=source_id), _factory_token=_FACTORY_TOKEN
    )


def require_mmcif_standard_l_peptide_heavy_completion(
    data: bytes,
    *,
    source_id: str = "",
    policy_id: str = MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID,
) -> MmcifStandardLPeptideHeavyCompletionResult:
    """Require exact profile readiness without promoting broad authority."""

    result = complete_mmcif_standard_l_peptide_heavy_neutral_microstate(
        data, source_id=source_id, policy_id=policy_id
    )
    report = result.report
    if (
        report.profile_heavy_completion_ready is not True
        or report.profile_molecular_preparation_ready is not True
    ):
        _raise_profile(
            "profile_heavy_completion_not_ready",
            "exact profile heavy completion was not satisfied",
        )
    return result


__all__ = [
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ANGLES",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_ATOMS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_BONDS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_INPUT_BYTES",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROPERS",
    "MAX_MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_ID_BYTES",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MAPPING_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_MARKER_KEY",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PARAMETER_REQUIREMENT_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_POLICY_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_PROFILE_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_REPORT_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_SOURCE_BINDING_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_STATE_SCHEMA_ID",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_NAME",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_TRANSFORMER_VERSION",
    "MMCIF_STANDARD_L_PEPTIDE_HEAVY_COMPLETION_VERSION",
    "MmcifStandardLPeptideHeavyCompletionError",
    "MmcifStandardLPeptideHeavyCompletionReport",
    "MmcifStandardLPeptideHeavyCompletionResult",
    "complete_mmcif_standard_l_peptide_heavy_neutral_microstate",
    "require_mmcif_standard_l_peptide_heavy_completion",
]
