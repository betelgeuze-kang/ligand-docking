"""Derive source-bound relative-energy and force targets from frozen SPICE data.

This module is deliberately a target-view transform, not a fitter.  It replays
the strict SPICE C1-C4 evidence loader, assigns pair roles from numeric
QCArchive entry suffixes, subtracts exact dyadic source energies before unit
conversion, and changes the sign bit of every source gradient scalar to obtain
``force = -dE/dr``.  Nothing here selects a force-field form, estimates a
parameter, projects a force, or authorizes runtime use.

The unit conversions are a versioned protocol convention built from the 2022
CODATA central values recorded below.  Treating those decimal central values as
exact rationals makes this transform reproducible; it is not a statement that
the underlying measured physical constants are exact.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass, replace
from fractions import Fraction
import hashlib
import json
import math
import struct
from typing import Any, Mapping

from .spice_c1c4_quantum_reference import (
    SPICE_C1C4_QUANTUM_REFERENCE_DOI,
    SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
    SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE,
    SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
    load_spice_c1c4_quantum_reference_evidence,
)


SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_relative_energy_force_targets/1.0.0"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_REPORT_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_relative_energy_force_target_report/1.0.0"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_ID = (
    "spice_c1_c4_pair_relative_energy_negative_gradient_targets/1.0.0"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE = (
    "source_bound_pair_relative_energy_and_negative_gradient_target_view_only"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_VALIDATION_SCOPE = (
    "within_same_four_graphs_unseen_conformations_only"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_UNIT_CONVENTION_ID = (
    "codata_2022_central_value_decimal_rational_single_binary64_round/1.0.0"
)

BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL = "0.529177210544"
HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL = "2625.499639479162971656"
HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_DECIMAL_VIEW = (
    "4961.475262285237924310517017872101374655905631663894475680163"
)
BOHR_TO_ANGSTROM_BINARY64_BE_HEX = "3fe0ef050ba2664a"
HARTREE_TO_KJ_PER_MOL_BINARY64_BE_HEX = "40a482ffd0beed97"
HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_BINARY64_BE_HEX = "40b36179aaca041e"

_BOHR_TO_ANGSTROM = Fraction(BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL)
_HARTREE_TO_KJ_PER_MOL = Fraction(HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL)
_HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM = (
    _HARTREE_TO_KJ_PER_MOL / _BOHR_TO_ANGSTROM
)
_GROUP_ORDER = ("c", "cc", "ccc", "cccc")
_PARTITION_ORDER = ("fit", "selection", "holdout")
_ROLE_ORDER = ("seed", "related_nearby_lower")
_DATASET_FACTORY_TOKEN = object()
_REPORT_FACTORY_TOKEN = object()
_TOPOLOGY_HASH_DOMAIN = b"spice-c1c4-target-topology-v1\0"
_ENERGY_TARGET_HASH_DOMAIN = b"spice-c1c4-relative-energy-target-v1\0"
_FORCE_TARGET_HASH_DOMAIN = b"spice-c1c4-force-target-v1\0"

_PROTOCOL_DOCUMENT: Mapping[str, Any] = {
    "protocol_id": SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_ID,
    "target_schema_id": SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID,
    "source_schema_id": SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
    "claim_scope": SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE,
    "canonical_order": [
        "group_order_c_cc_ccc_cccc",
        "numeric_source_pair_id_0_through_24",
        "role_seed_before_related_nearby_lower",
    ],
    "pair_roles": {
        "seed": "numeric_qcarchive_entry_suffix_equal_to_source_pair_id",
        "related_nearby_lower": (
            "numeric_qcarchive_entry_suffix_equal_to_source_pair_id_plus_25;"
            " provenance_role_only_not_a_qm_minimum_or_torsion_scan_endpoint"
        ),
        "role_assignment_prohibitions": [
            "source_index",
            "lexicographic_entry_order",
            "energy_order",
            "energy_difference_sign",
            "absolute_energy_difference",
        ],
    },
    "source_pair_generator_provenance": {
        "repository_commit": "b99b3f4d85585df6bdfeca5a56420c57ec6385f1",
        "path": "des370k/createDESMonomers.py",
        "raw_sha256": (
            "1ed3ac577e2aded15c408ec8e0330b95ed115958a28139cdf5611606fead0a9b"
        ),
        "role_interpretation": (
            "first_25_sampled_then_25_related_nearby_lower_geometries_from_"
            "limited_minimization_or_100K_MD"
        ),
        "openff_1_3_0_scope": (
            "geometry_sampling_provenance_only_not_label_or_parameter_evidence"
        ),
    },
    "relative_energy_operation": {
        "definition": "energy(seed_suffix_p)-energy(related_suffix_p_plus_25)",
        "source_arithmetic": "exact_difference_of_ieee754_binary64_dyadic_values",
        "conversion_order": (
            "subtract_in_exact_hartree_then_multiply_exact_protocol_rational_then_"
            "round_once_to_binary64_round_to_nearest_ties_to_even"
        ),
        "absolute_cross_molecule_energies_used": False,
    },
    "force_operation": {
        "definition": "force=-dE_dr",
        "raw_operation": (
            "xor_big_endian_ieee754_binary32_sign_bit_for_every_gradient_scalar"
        ),
        "signed_zero_preserved": True,
        "converted_operation": (
            "multiply_exact_source_dyadic_by_exact_protocol_rational_then_round_"
            "once_to_binary64_round_to_nearest_ties_to_even"
        ),
        "projection_applied": False,
        "mean_removal_applied": False,
        "clipping_applied": False,
        "denoising_applied": False,
    },
    "geometry_operation": {
        "definition": "source_bohr_coordinates_converted_to_angstrom",
        "converted_operation": (
            "multiply_exact_source_dyadic_by_exact_protocol_rational_then_round_"
            "once_to_binary64_round_to_nearest_ties_to_even"
        ),
    },
    "unit_convention": {
        "id": SPICE_C1C4_FORCE_MATCHING_TARGET_UNIT_CONVENTION_ID,
        "interpretation": (
            "2022_CODATA_central_values_frozen_as_exact_protocol_decimals_not_a_"
            "claim_of_physical_exactness"
        ),
        "bohr_to_angstrom_decimal_rational": BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL,
        "hartree_to_kj_per_mol_decimal_rational": (
            HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL
        ),
        "hartree_per_bohr_to_kj_per_mol_per_angstrom_definition": (
            "hartree_to_kj_per_mol_decimal_rational_divided_by_"
            "bohr_to_angstrom_decimal_rational"
        ),
        "binary64_constant_views": {
            "bohr_to_angstrom": BOHR_TO_ANGSTROM_BINARY64_BE_HEX,
            "hartree_to_kj_per_mol": HARTREE_TO_KJ_PER_MOL_BINARY64_BE_HEX,
            "hartree_per_bohr_to_kj_per_mol_per_angstrom": (
                HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_BINARY64_BE_HEX
            ),
        },
        "openmm_constants_used": False,
    },
    "diagnostics": {
        "net_force": "exact_rational_sum_before_one_binary64_round",
        "torque_origin": "arithmetic_coordinate_centroid",
        "torque": ("exact_rational_sum_of_cross_products_before_one_binary64_round"),
        "norm": "sqrt_of_binary64_rounded_exact_sum_of_squares",
        "diagnostic_only": True,
    },
    "leakage_boundary": {
        "pair_members_must_share_partition": True,
        "target_uses_only_its_source_pair_or_source_record": True,
        "selection_or_holdout_centering_or_normalization": False,
        "same_four_molecular_graphs_across_partitions": True,
        "public_holdout_is_blind_to_humans": False,
    },
}


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256 = hashlib.sha256(
    _canonical_json_bytes(_PROTOCOL_DOCUMENT)
).hexdigest()

# Frozen after reviewing the canonical transform.  The artifact is generated
# on demand and is never a committed data file.
SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_BYTE_COUNT = 686561
SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256 = (
    "ff19771d03dc476dd538c99b1468bce3ada25e68623b3cb329f8e71c05fd7e13"
)
SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256 = (
    "caff216e22207a368ad640dc2fa0567dec3d3f04027b3ce2c3b8c433ee1c4c74"
)


def spice_c1c4_force_matching_target_protocol_bytes() -> bytes:
    """Return the immutable canonical target-transform protocol bytes."""

    return _canonical_json_bytes(_PROTOCOL_DOCUMENT)


def spice_c1c4_force_matching_target_protocol_document() -> dict[str, Any]:
    """Return a detached copy of the target-transform protocol document."""

    return json.loads(spice_c1c4_force_matching_target_protocol_bytes())


class SpiceC1C4ForceMatchingTargetContractError(ValueError):
    """Raised when derived target bytes do not match the frozen transform."""


@dataclass(frozen=True, slots=True)
class SpiceC1C4TargetTopology:
    group_id: str
    component_id: str
    formula: str
    mapped_smiles: str
    atomic_numbers: tuple[int, ...]
    molecular_charge: float
    molecular_multiplicity: int
    connectivity: tuple[tuple[int, int, float], ...]
    topology_sha256: str


@dataclass(frozen=True, slots=True)
class SpiceC1C4RelativeEnergyTarget:
    group_id: str
    topology_sha256: str
    source_pair_id: int
    partition: str
    seed_qcarchive_entry_name: str
    related_qcarchive_entry_name: str
    seed_record_id: str
    related_record_id: str
    seed_record_payload_sha256: str
    related_record_payload_sha256: str
    seed_energy_sha256: str
    related_energy_sha256: str
    seed_energy_binary64_be_hex: str
    related_energy_binary64_be_hex: str
    energy_difference_hartree_signed_numerator_hex: str
    energy_difference_hartree_denominator_power_of_two: int
    relative_energy_kj_per_mol_binary64_be_hex: str
    target_sha256: str


@dataclass(frozen=True, slots=True)
class SpiceC1C4ForceTarget:
    group_id: str
    topology_sha256: str
    source_pair_id: int
    role: str
    partition: str
    qcarchive_entry_name: str
    qcarchive_entry_numeric_suffix: int
    record_id: str
    qcarchive_record_id: int
    qcarchive_molecule_id: int
    qcarchive_molecule_hash: str
    record_payload_sha256: str
    source_geometry_sha256: str
    source_energy_sha256: str
    source_gradient_sha256: str
    geometry_angstrom_binary64_be_hex: str
    geometry_angstrom_sha256: str
    force_hartree_per_bohr_binary32_be_hex: str
    force_hartree_per_bohr_sha256: str
    force_kj_per_mol_per_angstrom_binary64_be_hex: str
    force_kj_per_mol_per_angstrom_sha256: str
    net_force_kj_per_mol_per_angstrom_binary64_be_hex: str
    net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex: str
    torque_about_coordinate_centroid_kj_per_mol_binary64_be_hex: str
    torque_norm_kj_per_mol_binary64_be_hex: str
    diagnostic_sha256: str
    target_sha256: str


@dataclass(frozen=True, slots=True)
class SpiceC1C4ForceMatchingTargets:
    _factory_token: InitVar[object]
    schema_id: str
    protocol_id: str
    protocol_sha256: str
    claim_scope: str
    validation_scope: str
    source_schema_id: str
    source_release: str
    source_doi: str
    source_subset: str
    source_core_sha256: str
    source_artifact_sha256: str
    source_artifact_byte_count: int
    unit_convention_id: str
    group_order: tuple[str, ...]
    partition_order: tuple[str, ...]
    role_order: tuple[str, ...]
    topologies: tuple[SpiceC1C4TargetTopology, ...]
    relative_energy_targets: tuple[SpiceC1C4RelativeEnergyTarget, ...]
    force_targets: tuple[SpiceC1C4ForceTarget, ...]
    relative_energy_target_count: int
    force_target_record_count: int
    force_target_scalar_count: int
    fit_relative_energy_target_count: int
    selection_relative_energy_target_count: int
    holdout_relative_energy_target_count: int
    fit_force_target_record_count: int
    selection_force_target_record_count: int
    holdout_force_target_record_count: int
    fit_force_target_scalar_count: int
    selection_force_target_scalar_count: int
    holdout_force_target_scalar_count: int
    max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex: str
    max_torque_norm_kj_per_mol_binary64_be_hex: str
    projection_applied: bool
    mean_removal_applied: bool
    clipping_applied: bool
    denoising_applied: bool
    target_view_only: bool
    molecular_graph_disjoint: bool
    public_holdout_blind_to_humans: bool
    license_human_reviewed: bool
    source_whole_file_authenticated: bool
    energy_gradient_finite_difference_consistency_established: bool
    candidate_fitting_performed: bool
    candidate_parameter_set_available: bool
    parameter_identifiability_established: bool
    parameter_family_sufficiency_assessed: bool
    reference_validation_performed: bool
    production_parameters_available: bool
    parameterability_assessed: bool
    parameterizable: bool
    physics_ready: bool
    runtime_eligible: bool
    execution_authorized: bool
    claim_safe: bool
    core_sha256: str

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _DATASET_FACTORY_TOKEN:
            raise TypeError("target datasets are factory-only; replay the source bytes")


@dataclass(frozen=True, slots=True)
class SpiceC1C4ForceMatchingTargetReport:
    _factory_token: InitVar[object]
    schema_id: str
    target_schema_id: str
    protocol_sha256: str
    target_core_sha256: str
    serialized_target_sha256: str
    serialized_target_byte_count: int
    relative_energy_target_count: int
    force_target_record_count: int
    force_target_scalar_count: int
    fit_relative_energy_target_count: int
    selection_relative_energy_target_count: int
    holdout_relative_energy_target_count: int
    fit_force_target_record_count: int
    selection_force_target_record_count: int
    holdout_force_target_record_count: int
    fit_force_target_scalar_count: int
    selection_force_target_scalar_count: int
    holdout_force_target_scalar_count: int
    exact_record_overlap_count: int
    geometry_overlap_count: int
    source_pair_overlap_count: int
    derived_target_hash_overlap_count: int
    molecular_graph_overlap_count: int
    molecular_graph_disjoint: bool
    public_holdout_blind_to_humans: bool
    generic_validation_split: bool
    validation_scope: str
    max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex: str
    max_torque_norm_kj_per_mol_binary64_be_hex: str
    projection_applied: bool
    license_human_reviewed: bool
    source_whole_file_authenticated: bool
    energy_gradient_finite_difference_consistency_established: bool
    candidate_fitting_performed: bool
    candidate_parameter_set_available: bool
    parameter_identifiability_established: bool
    parameter_family_sufficiency_assessed: bool
    reference_validation_performed: bool
    production_parameters_available: bool
    parameterability_assessed: bool
    parameterizable: bool
    physics_ready: bool
    runtime_eligible: bool
    execution_authorized: bool
    claim_safe: bool

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _REPORT_FACTORY_TOKEN:
            raise TypeError("target reports are factory-only; replay the source bytes")

    @property
    def max_net_force_norm_kj_per_mol_per_angstrom(self) -> float:
        return struct.unpack(
            ">d",
            bytes.fromhex(
                self.max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex
            ),
        )[0]

    @property
    def max_torque_norm_kj_per_mol(self) -> float:
        return struct.unpack(
            ">d", bytes.fromhex(self.max_torque_norm_kj_per_mol_binary64_be_hex)
        )[0]


def _fraction_from_ieee(raw: bytes, format_code: str) -> tuple[Fraction, bool]:
    (value,) = struct.unpack(format_code, raw)
    if not math.isfinite(value):
        raise SpiceC1C4ForceMatchingTargetContractError(
            "source loader admitted a non-finite IEEE value"
        )
    negative_zero = value == 0.0 and bool(raw[0] & 0x80)
    return Fraction.from_float(value), negative_zero


def _fraction_to_binary64_bytes(
    value: Fraction, *, negative_zero: bool = False
) -> bytes:
    converted = float(value)
    if not math.isfinite(converted):
        raise SpiceC1C4ForceMatchingTargetContractError(
            "derived target is not finite binary64"
        )
    if value == 0 and negative_zero:
        converted = -0.0
    return struct.pack(">d", converted)


def _negate_binary32_sign_bits(raw: bytes) -> bytes:
    if len(raw) % 4:
        raise SpiceC1C4ForceMatchingTargetContractError(
            "binary32 source width must be divisible by four bytes"
        )
    result = bytearray(raw)
    for index in range(0, len(result), 4):
        result[index] ^= 0x80
    return bytes(result)


def _signed_hex(value: int) -> str:
    return f"-{abs(value):x}" if value < 0 else f"{value:x}"


def _sha256_canonical(domain: bytes, value: Mapping[str, Any]) -> str:
    return hashlib.sha256(domain + _canonical_json_bytes(value)).hexdigest()


def _topology_for_group(group: Any) -> SpiceC1C4TargetTopology:
    body = {
        "group_id": group.group_id,
        "component_id": group.component_id,
        "formula": group.formula,
        "mapped_smiles": group.mapped_smiles,
        "atomic_numbers": tuple(group.atomic_numbers),
        "molecular_charge": group.molecular_charge,
        "molecular_multiplicity": group.molecular_multiplicity,
        "connectivity": tuple(tuple(row) for row in group.connectivity),
    }
    return SpiceC1C4TargetTopology(
        **body,
        topology_sha256=_sha256_canonical(_TOPOLOGY_HASH_DOMAIN, body),
    )


def _relative_energy_target(
    *,
    group_id: str,
    topology_sha256: str,
    source_pair_id: int,
    seed: Any,
    related: Any,
) -> SpiceC1C4RelativeEnergyTarget:
    seed_energy_raw = bytes.fromhex(seed.energy_binary64_be_hex)
    related_energy_raw = bytes.fromhex(related.energy_binary64_be_hex)
    seed_energy, _ = _fraction_from_ieee(seed_energy_raw, ">d")
    related_energy, _ = _fraction_from_ieee(related_energy_raw, ">d")
    difference = seed_energy - related_energy
    if difference.denominator & (difference.denominator - 1):
        raise SpiceC1C4ForceMatchingTargetContractError(
            "binary64 energy difference is not dyadic"
        )
    converted = _fraction_to_binary64_bytes(difference * _HARTREE_TO_KJ_PER_MOL)
    body = {
        "group_id": group_id,
        "topology_sha256": topology_sha256,
        "source_pair_id": source_pair_id,
        "partition": seed.partition,
        "seed_qcarchive_entry_name": seed.qcarchive_entry_name,
        "related_qcarchive_entry_name": related.qcarchive_entry_name,
        "seed_record_id": seed.record_id,
        "related_record_id": related.record_id,
        "seed_record_payload_sha256": seed.record_payload_sha256,
        "related_record_payload_sha256": related.record_payload_sha256,
        "seed_energy_sha256": seed.energy_sha256,
        "related_energy_sha256": related.energy_sha256,
        "seed_energy_binary64_be_hex": seed.energy_binary64_be_hex,
        "related_energy_binary64_be_hex": related.energy_binary64_be_hex,
        "energy_difference_hartree_signed_numerator_hex": _signed_hex(
            difference.numerator
        ),
        "energy_difference_hartree_denominator_power_of_two": (
            difference.denominator.bit_length() - 1
        ),
        "relative_energy_kj_per_mol_binary64_be_hex": converted.hex(),
    }
    return SpiceC1C4RelativeEnergyTarget(
        **body,
        target_sha256=_sha256_canonical(_ENERGY_TARGET_HASH_DOMAIN, body),
    )


def _norm_binary64_bytes(vector: tuple[Fraction, Fraction, Fraction]) -> bytes:
    squared = sum((component * component for component in vector), Fraction())
    # The diagnostic norm is not a target.  Its frozen operation is one
    # binary64 rounding of the exact sum of squares followed by IEEE sqrt.
    return struct.pack(">d", math.sqrt(float(squared)))


def _force_target(
    *,
    group_id: str,
    topology_sha256: str,
    atom_count: int,
    role: str,
    record: Any,
) -> SpiceC1C4ForceTarget:
    geometry_raw = bytes.fromhex(record.geometry_binary32_be_hex)
    gradient_raw = bytes.fromhex(record.gradient_binary32_be_hex)
    force_raw_chunks: list[bytes] = []
    geometry_exact: list[Fraction] = []
    force_exact: list[Fraction] = []
    geometry_converted_chunks: list[bytes] = []
    force_converted_chunks: list[bytes] = []

    for geometry_chunk in (
        geometry_raw[index : index + 4] for index in range(0, len(geometry_raw), 4)
    ):
        geometry_value, geometry_negative_zero = _fraction_from_ieee(
            geometry_chunk, ">f"
        )
        converted_exact = geometry_value * _BOHR_TO_ANGSTROM
        geometry_exact.append(converted_exact)
        geometry_converted_chunks.append(
            _fraction_to_binary64_bytes(
                converted_exact,
                negative_zero=geometry_negative_zero,
            )
        )

    force_raw_all = _negate_binary32_sign_bits(gradient_raw)
    for force_chunk in (
        force_raw_all[index : index + 4] for index in range(0, len(force_raw_all), 4)
    ):
        force_raw_chunks.append(force_chunk)
        force_value, force_negative_zero = _fraction_from_ieee(force_chunk, ">f")
        converted_exact = force_value * _HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM
        force_exact.append(converted_exact)
        force_converted_chunks.append(
            _fraction_to_binary64_bytes(
                converted_exact,
                negative_zero=force_negative_zero,
            )
        )

    expected_scalar_count = atom_count * 3
    if (
        len(geometry_exact) != expected_scalar_count
        or len(force_exact) != expected_scalar_count
    ):
        raise SpiceC1C4ForceMatchingTargetContractError(
            "source geometry/gradient width does not match topology"
        )

    centroid = tuple(
        sum(
            (geometry_exact[atom * 3 + axis] for atom in range(atom_count)),
            Fraction(),
        )
        / atom_count
        for axis in range(3)
    )
    net_force = tuple(
        sum(
            (force_exact[atom * 3 + axis] for atom in range(atom_count)),
            Fraction(),
        )
        for axis in range(3)
    )
    torque_values = [Fraction(), Fraction(), Fraction()]
    for atom in range(atom_count):
        rx, ry, rz = (
            geometry_exact[atom * 3 + axis] - centroid[axis] for axis in range(3)
        )
        fx, fy, fz = (force_exact[atom * 3 + axis] for axis in range(3))
        torque_values[0] += ry * fz - rz * fy
        torque_values[1] += rz * fx - rx * fz
        torque_values[2] += rx * fy - ry * fx
    torque = tuple(torque_values)

    geometry_converted = b"".join(geometry_converted_chunks)
    force_raw = b"".join(force_raw_chunks)
    force_converted = b"".join(force_converted_chunks)
    net_force_raw = b"".join(_fraction_to_binary64_bytes(value) for value in net_force)
    net_force_norm_raw = _norm_binary64_bytes(net_force)
    torque_raw = b"".join(_fraction_to_binary64_bytes(value) for value in torque)
    torque_norm_raw = _norm_binary64_bytes(torque)  # type: ignore[arg-type]
    diagnostic_raw = net_force_raw + net_force_norm_raw + torque_raw + torque_norm_raw

    suffix = int(record.qcarchive_entry_name.rsplit("-", 1)[1])
    body = {
        "group_id": group_id,
        "topology_sha256": topology_sha256,
        "source_pair_id": record.source_pair_id,
        "role": role,
        "partition": record.partition,
        "qcarchive_entry_name": record.qcarchive_entry_name,
        "qcarchive_entry_numeric_suffix": suffix,
        "record_id": record.record_id,
        "qcarchive_record_id": record.qcarchive_record_id,
        "qcarchive_molecule_id": record.qcarchive_molecule_id,
        "qcarchive_molecule_hash": record.qcarchive_molecule_hash,
        "record_payload_sha256": record.record_payload_sha256,
        "source_geometry_sha256": record.geometry_sha256,
        "source_energy_sha256": record.energy_sha256,
        "source_gradient_sha256": record.gradient_sha256,
        "geometry_angstrom_binary64_be_hex": geometry_converted.hex(),
        "geometry_angstrom_sha256": hashlib.sha256(geometry_converted).hexdigest(),
        "force_hartree_per_bohr_binary32_be_hex": force_raw.hex(),
        "force_hartree_per_bohr_sha256": hashlib.sha256(force_raw).hexdigest(),
        "force_kj_per_mol_per_angstrom_binary64_be_hex": force_converted.hex(),
        "force_kj_per_mol_per_angstrom_sha256": hashlib.sha256(
            force_converted
        ).hexdigest(),
        "net_force_kj_per_mol_per_angstrom_binary64_be_hex": net_force_raw.hex(),
        "net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex": (
            net_force_norm_raw.hex()
        ),
        "torque_about_coordinate_centroid_kj_per_mol_binary64_be_hex": (
            torque_raw.hex()
        ),
        "torque_norm_kj_per_mol_binary64_be_hex": torque_norm_raw.hex(),
        "diagnostic_sha256": hashlib.sha256(diagnostic_raw).hexdigest(),
    }
    return SpiceC1C4ForceTarget(
        **body,
        target_sha256=_sha256_canonical(_FORCE_TARGET_HASH_DOMAIN, body),
    )


def _dataset_body(dataset: SpiceC1C4ForceMatchingTargets) -> dict[str, Any]:
    body = asdict(dataset)
    body.pop("core_sha256")
    return body


def _dataset_document(dataset: SpiceC1C4ForceMatchingTargets) -> dict[str, Any]:
    body = _dataset_body(dataset)
    body["core_sha256"] = dataset.core_sha256
    return body


def _build_targets(source_bytes: bytes) -> SpiceC1C4ForceMatchingTargets:
    corpus = load_spice_c1c4_quantum_reference_evidence(source_bytes)
    if tuple(group.group_id for group in corpus.groups) != _GROUP_ORDER:
        raise SpiceC1C4ForceMatchingTargetContractError(
            "source group order does not match target protocol"
        )

    topologies: list[SpiceC1C4TargetTopology] = []
    relative_targets: list[SpiceC1C4RelativeEnergyTarget] = []
    force_targets: list[SpiceC1C4ForceTarget] = []
    for group in corpus.groups:
        topology = _topology_for_group(group)
        topologies.append(topology)
        by_suffix = {
            int(record.qcarchive_entry_name.rsplit("-", 1)[1]): record
            for record in group.records
        }
        if set(by_suffix) != set(range(50)):
            raise SpiceC1C4ForceMatchingTargetContractError(
                f"{group.group_id} numeric entry suffix coverage mismatch"
            )
        for pair_id in range(25):
            seed = by_suffix[pair_id]
            related = by_suffix[pair_id + 25]
            if (
                seed.source_pair_id != pair_id
                or related.source_pair_id != pair_id
                or seed.partition != related.partition
            ):
                raise SpiceC1C4ForceMatchingTargetContractError(
                    f"{group.group_id} source pair {pair_id} binding mismatch"
                )
            relative_targets.append(
                _relative_energy_target(
                    group_id=group.group_id,
                    topology_sha256=topology.topology_sha256,
                    source_pair_id=pair_id,
                    seed=seed,
                    related=related,
                )
            )
            force_targets.append(
                _force_target(
                    group_id=group.group_id,
                    topology_sha256=topology.topology_sha256,
                    atom_count=group.atom_count,
                    role="seed",
                    record=seed,
                )
            )
            force_targets.append(
                _force_target(
                    group_id=group.group_id,
                    topology_sha256=topology.topology_sha256,
                    atom_count=group.atom_count,
                    role="related_nearby_lower",
                    record=related,
                )
            )

    force_scalar_counts = {
        partition: sum(
            len(bytes.fromhex(row.force_hartree_per_bohr_binary32_be_hex)) // 4
            for row in force_targets
            if row.partition == partition
        )
        for partition in _PARTITION_ORDER
    }
    max_net = max(
        force_targets,
        key=lambda row: struct.unpack(
            ">d",
            bytes.fromhex(row.net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex),
        )[0],
    )
    max_torque = max(
        force_targets,
        key=lambda row: struct.unpack(
            ">d", bytes.fromhex(row.torque_norm_kj_per_mol_binary64_be_hex)
        )[0],
    )
    provisional = SpiceC1C4ForceMatchingTargets(
        _factory_token=_DATASET_FACTORY_TOKEN,
        schema_id=SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID,
        protocol_id=SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_ID,
        protocol_sha256=SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256,
        claim_scope=SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE,
        validation_scope=SPICE_C1C4_FORCE_MATCHING_TARGET_VALIDATION_SCOPE,
        source_schema_id=SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
        source_release=SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE,
        source_doi=SPICE_C1C4_QUANTUM_REFERENCE_DOI,
        source_subset=SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
        source_core_sha256=corpus.core_sha256,
        source_artifact_sha256=corpus.artifact_sha256,
        source_artifact_byte_count=corpus.artifact_byte_count,
        unit_convention_id=SPICE_C1C4_FORCE_MATCHING_TARGET_UNIT_CONVENTION_ID,
        group_order=_GROUP_ORDER,
        partition_order=_PARTITION_ORDER,
        role_order=_ROLE_ORDER,
        topologies=tuple(topologies),
        relative_energy_targets=tuple(relative_targets),
        force_targets=tuple(force_targets),
        relative_energy_target_count=len(relative_targets),
        force_target_record_count=len(force_targets),
        force_target_scalar_count=sum(force_scalar_counts.values()),
        fit_relative_energy_target_count=sum(
            row.partition == "fit" for row in relative_targets
        ),
        selection_relative_energy_target_count=sum(
            row.partition == "selection" for row in relative_targets
        ),
        holdout_relative_energy_target_count=sum(
            row.partition == "holdout" for row in relative_targets
        ),
        fit_force_target_record_count=sum(
            row.partition == "fit" for row in force_targets
        ),
        selection_force_target_record_count=sum(
            row.partition == "selection" for row in force_targets
        ),
        holdout_force_target_record_count=sum(
            row.partition == "holdout" for row in force_targets
        ),
        fit_force_target_scalar_count=force_scalar_counts["fit"],
        selection_force_target_scalar_count=force_scalar_counts["selection"],
        holdout_force_target_scalar_count=force_scalar_counts["holdout"],
        max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex=(
            max_net.net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex
        ),
        max_torque_norm_kj_per_mol_binary64_be_hex=(
            max_torque.torque_norm_kj_per_mol_binary64_be_hex
        ),
        projection_applied=False,
        mean_removal_applied=False,
        clipping_applied=False,
        denoising_applied=False,
        target_view_only=True,
        molecular_graph_disjoint=False,
        public_holdout_blind_to_humans=False,
        license_human_reviewed=False,
        source_whole_file_authenticated=False,
        energy_gradient_finite_difference_consistency_established=False,
        candidate_fitting_performed=False,
        candidate_parameter_set_available=False,
        parameter_identifiability_established=False,
        parameter_family_sufficiency_assessed=False,
        reference_validation_performed=False,
        production_parameters_available=False,
        parameterability_assessed=False,
        parameterizable=False,
        physics_ready=False,
        runtime_eligible=False,
        execution_authorized=False,
        claim_safe=False,
        core_sha256="",
    )
    core_sha256 = hashlib.sha256(
        _canonical_json_bytes(_dataset_body(provisional))
    ).hexdigest()
    return replace(
        provisional,
        core_sha256=core_sha256,
        _factory_token=_DATASET_FACTORY_TOKEN,
    )


def _serialized_bytes(dataset: SpiceC1C4ForceMatchingTargets) -> bytes:
    return _canonical_json_bytes(_dataset_document(dataset))


def _verify_frozen_target(dataset: SpiceC1C4ForceMatchingTargets) -> bytes:
    data = _serialized_bytes(dataset)
    if dataset.core_sha256 != SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256:
        raise SpiceC1C4ForceMatchingTargetContractError(
            "derived target core does not match the frozen transform"
        )
    if (
        len(data) != SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_BYTE_COUNT
        or hashlib.sha256(data).hexdigest()
        != SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256
    ):
        raise SpiceC1C4ForceMatchingTargetContractError(
            "derived target serialization does not match the frozen transform"
        )
    return data


def derive_spice_c1c4_force_matching_targets(
    source_bytes: bytes,
) -> SpiceC1C4ForceMatchingTargets:
    """Replay frozen evidence and derive the immutable nonpromoting target view."""

    dataset = _build_targets(source_bytes)
    _verify_frozen_target(dataset)
    return dataset


def serialize_spice_c1c4_force_matching_targets(source_bytes: bytes) -> bytes:
    """Generate the byte-for-byte canonical target view from frozen source bytes."""

    dataset = derive_spice_c1c4_force_matching_targets(source_bytes)
    return _verify_frozen_target(dataset)


def analyze_spice_c1c4_force_matching_targets(
    source_bytes: bytes,
) -> SpiceC1C4ForceMatchingTargetReport:
    """Return a factory-only integrity/limitations report for derived targets."""

    dataset = derive_spice_c1c4_force_matching_targets(source_bytes)
    serialized = _verify_frozen_target(dataset)
    by_partition_force = {
        partition: tuple(
            row for row in dataset.force_targets if row.partition == partition
        )
        for partition in _PARTITION_ORDER
    }
    by_partition_energy = {
        partition: tuple(
            row for row in dataset.relative_energy_targets if row.partition == partition
        )
        for partition in _PARTITION_ORDER
    }

    def overlap(attribute: str) -> int:
        sets = [
            {getattr(row, attribute) for row in by_partition_force[partition]}
            for partition in _PARTITION_ORDER
        ]
        return len((sets[0] & sets[1]) | (sets[0] & sets[2]) | (sets[1] & sets[2]))

    pair_sets = [
        {(row.group_id, row.source_pair_id) for row in by_partition_energy[p]}
        for p in _PARTITION_ORDER
    ]
    pair_overlap = len(
        (pair_sets[0] & pair_sets[1])
        | (pair_sets[0] & pair_sets[2])
        | (pair_sets[1] & pair_sets[2])
    )
    target_hash_sets = [
        {row.target_sha256 for row in by_partition_force[p]}
        | {row.target_sha256 for row in by_partition_energy[p]}
        for p in _PARTITION_ORDER
    ]
    target_hash_overlap = len(
        (target_hash_sets[0] & target_hash_sets[1])
        | (target_hash_sets[0] & target_hash_sets[2])
        | (target_hash_sets[1] & target_hash_sets[2])
    )
    graph_sets = [
        {row.group_id for row in by_partition_force[p]} for p in _PARTITION_ORDER
    ]
    graph_overlap = len(set.intersection(*graph_sets))
    return SpiceC1C4ForceMatchingTargetReport(
        _factory_token=_REPORT_FACTORY_TOKEN,
        schema_id=SPICE_C1C4_FORCE_MATCHING_TARGET_REPORT_SCHEMA_ID,
        target_schema_id=dataset.schema_id,
        protocol_sha256=dataset.protocol_sha256,
        target_core_sha256=dataset.core_sha256,
        serialized_target_sha256=hashlib.sha256(serialized).hexdigest(),
        serialized_target_byte_count=len(serialized),
        relative_energy_target_count=dataset.relative_energy_target_count,
        force_target_record_count=dataset.force_target_record_count,
        force_target_scalar_count=dataset.force_target_scalar_count,
        fit_relative_energy_target_count=dataset.fit_relative_energy_target_count,
        selection_relative_energy_target_count=(
            dataset.selection_relative_energy_target_count
        ),
        holdout_relative_energy_target_count=(
            dataset.holdout_relative_energy_target_count
        ),
        fit_force_target_record_count=dataset.fit_force_target_record_count,
        selection_force_target_record_count=(
            dataset.selection_force_target_record_count
        ),
        holdout_force_target_record_count=dataset.holdout_force_target_record_count,
        fit_force_target_scalar_count=dataset.fit_force_target_scalar_count,
        selection_force_target_scalar_count=(
            dataset.selection_force_target_scalar_count
        ),
        holdout_force_target_scalar_count=dataset.holdout_force_target_scalar_count,
        exact_record_overlap_count=overlap("record_id"),
        geometry_overlap_count=overlap("source_geometry_sha256"),
        source_pair_overlap_count=pair_overlap,
        derived_target_hash_overlap_count=target_hash_overlap,
        molecular_graph_overlap_count=graph_overlap,
        molecular_graph_disjoint=graph_overlap == 0,
        public_holdout_blind_to_humans=False,
        generic_validation_split=False,
        validation_scope=SPICE_C1C4_FORCE_MATCHING_TARGET_VALIDATION_SCOPE,
        max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex=(
            dataset.max_net_force_norm_kj_per_mol_per_angstrom_binary64_be_hex
        ),
        max_torque_norm_kj_per_mol_binary64_be_hex=(
            dataset.max_torque_norm_kj_per_mol_binary64_be_hex
        ),
        projection_applied=False,
        license_human_reviewed=False,
        source_whole_file_authenticated=False,
        energy_gradient_finite_difference_consistency_established=False,
        candidate_fitting_performed=False,
        candidate_parameter_set_available=False,
        parameter_identifiability_established=False,
        parameter_family_sufficiency_assessed=False,
        reference_validation_performed=False,
        production_parameters_available=False,
        parameterability_assessed=False,
        parameterizable=False,
        physics_ready=False,
        runtime_eligible=False,
        execution_authorized=False,
        claim_safe=False,
    )


def serialize_spice_c1c4_force_matching_target_report(source_bytes: bytes) -> bytes:
    """Replay source bytes and serialize the nonpromotion report canonically."""

    return _canonical_json_bytes(
        asdict(analyze_spice_c1c4_force_matching_targets(source_bytes))
    )


__all__ = [
    "BOHR_TO_ANGSTROM_BINARY64_BE_HEX",
    "BOHR_TO_ANGSTROM_PROTOCOL_DECIMAL",
    "HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_BINARY64_BE_HEX",
    "HARTREE_PER_BOHR_TO_KJ_PER_MOL_PER_ANGSTROM_DECIMAL_VIEW",
    "HARTREE_TO_KJ_PER_MOL_BINARY64_BE_HEX",
    "HARTREE_TO_KJ_PER_MOL_PROTOCOL_DECIMAL",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_CLAIM_SCOPE",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_CORE_SHA256",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_ID",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_PROTOCOL_SHA256",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_REPORT_SCHEMA_ID",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_SCHEMA_ID",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_BYTE_COUNT",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_SERIALIZED_SHA256",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_UNIT_CONVENTION_ID",
    "SPICE_C1C4_FORCE_MATCHING_TARGET_VALIDATION_SCOPE",
    "SpiceC1C4ForceMatchingTargetContractError",
    "SpiceC1C4ForceMatchingTargetReport",
    "SpiceC1C4ForceMatchingTargets",
    "SpiceC1C4ForceTarget",
    "SpiceC1C4RelativeEnergyTarget",
    "SpiceC1C4TargetTopology",
    "analyze_spice_c1c4_force_matching_targets",
    "derive_spice_c1c4_force_matching_targets",
    "serialize_spice_c1c4_force_matching_target_report",
    "serialize_spice_c1c4_force_matching_targets",
    "spice_c1c4_force_matching_target_protocol_bytes",
    "spice_c1c4_force_matching_target_protocol_document",
]
