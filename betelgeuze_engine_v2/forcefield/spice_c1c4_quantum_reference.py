"""Strict admission of a bounded SPICE 2.0.1 C1-C4 reference corpus.

This module admits exact source values for 200 methane-through-n-butane
single-point records.  Admission establishes integrity only for the frozen
reference slice.  It does not fit a parameter, validate a force field, make
the dataset license decision, or authorize physics/runtime use.

The artifact stores source float32 coordinates and gradients and float64
energies as big-endian IEEE-754 hexadecimal bytes.  No NumPy, HDF5, network,
or scientific-data dependency is needed to verify the committed evidence.
"""

from __future__ import annotations

from dataclasses import InitVar, asdict, dataclass
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping


SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_quantum_reference_evidence/1.0.0"
)
SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE = "SPICE 2.0.1"
SPICE_C1C4_QUANTUM_REFERENCE_DOI = "10.5281/zenodo.10975225"
SPICE_C1C4_QUANTUM_REFERENCE_SUBSET = "SPICE DES Monomers Single Points Dataset v1.1"
SPICE_C1C4_QUANTUM_REFERENCE_SPLIT_POLICY_ID = (
    "per_group_related_conformation_pair_sha256_15_5_5/1.0.0"
)
SPICE_C1C4_QUANTUM_REFERENCE_ADMISSION_REPORT_SCHEMA_ID = (
    "betelgeuze.spice_c1_c4_quantum_reference_admission_report/1.0.0"
)

_MAX_CORPUS_BYTES = 512 * 1024
_LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LOWER_MD5 = re.compile(r"[0-9a-f]{32}\Z")
_LOWER_HEX40 = re.compile(r"[0-9a-f]{40}\Z")
_LOWER_HEX = re.compile(r"(?:[0-9a-f]{2})+\Z")
_RECORD_HASH_DOMAIN = b"spice-c1c4-record-v1\0"
_REPORT_FACTORY_TOKEN = object()

# Filled from the reviewed canonical artifact.  These constants bind callers
# to one byte-for-byte corpus, rather than merely to a permissive schema.
_FROZEN_CORE_SHA256 = "265c9883c06755cb845dd682b3b16634ea1f0d8ffd76dc60094b2224ab072dae"
_FROZEN_ARTIFACT_SHA256 = (
    "ffa884e94f624b89ac8602cda8ff01f363f60838e4efc1c2a3c0a057bf94c0a3"
)
_FROZEN_ARTIFACT_BYTE_COUNT = 251253
SPICE_C1C4_QUANTUM_REFERENCE_CORE_SHA256 = _FROZEN_CORE_SHA256
SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256 = _FROZEN_ARTIFACT_SHA256
SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_BYTE_COUNT = _FROZEN_ARTIFACT_BYTE_COUNT
_FROZEN_SCHEMA_ID = SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID
_FROZEN_SOURCE_RELEASE = SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE
_FROZEN_SOURCE_DOI = SPICE_C1C4_QUANTUM_REFERENCE_DOI
_FROZEN_SUBSET = SPICE_C1C4_QUANTUM_REFERENCE_SUBSET

_GROUP_SPECS: Mapping[str, Mapping[str, Any]] = {
    "c": {
        "component_id": "methane_c1",
        "formula": "CH4",
        "mapped_smiles": "[H:2][C:1]([H:3])([H:4])[H:5]",
        "atomic_numbers": (6, 1, 1, 1, 1),
        "connectivity": (
            (0, 1, 1.0),
            (0, 2, 1.0),
            (0, 3, 1.0),
            (0, 4, 1.0),
        ),
        "conformations_sha256": (
            "5e51aa7b5a92bc55c5ed748354e2bf276e62ed38ff6b53e2146ad285d3e90bb1"
        ),
        "energies_sha256": (
            "fdfb9a790a01d89163c78acfead0b2ed321852b02aa5839c899b232934864a93"
        ),
        "gradients_sha256": (
            "235fb701e31f64467539ad57feeedac71235761432dd1451057fb4ed866d756f"
        ),
    },
    "cc": {
        "component_id": "ethane_c2",
        "formula": "C2H6",
        "mapped_smiles": ("[H:3][C:1]([H:4])([H:5])[C:2]([H:6])([H:7])[H:8]"),
        "atomic_numbers": (6, 6, 1, 1, 1, 1, 1, 1),
        "connectivity": (
            (0, 1, 1.0),
            (0, 2, 1.0),
            (0, 3, 1.0),
            (0, 4, 1.0),
            (1, 5, 1.0),
            (1, 6, 1.0),
            (1, 7, 1.0),
        ),
        "conformations_sha256": (
            "25934750eb828dc436b96bcb3a7ac3ced2474ad0b9a76f99ab265b02575a7b11"
        ),
        "energies_sha256": (
            "670e02f3617347843d0c4e913e84403776bc4531d51661491056e7dd1b0dc0e7"
        ),
        "gradients_sha256": (
            "5bb929b00b333ed00e096f0e1b4b71f65cfed3cb016fae76042b7567b9a22420"
        ),
    },
    "ccc": {
        "component_id": "propane_c3",
        "formula": "C3H8",
        "mapped_smiles": (
            "[H:4][C:1]([H:5])([H:6])[C:3]([H:10])([H:11])[C:2]([H:7])([H:8])[H:9]"
        ),
        "atomic_numbers": (6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1),
        "connectivity": (
            (0, 2, 1.0),
            (0, 3, 1.0),
            (0, 4, 1.0),
            (0, 5, 1.0),
            (1, 2, 1.0),
            (1, 6, 1.0),
            (1, 7, 1.0),
            (1, 8, 1.0),
            (2, 9, 1.0),
            (2, 10, 1.0),
        ),
        "conformations_sha256": (
            "4802ecb632be7f2245be9c6ba6248d9244c8c46b1f7d24f92b9c897021999665"
        ),
        "energies_sha256": (
            "f589866974752c41f7d4005838273703f16e143e7a362376fb96b72604ef8978"
        ),
        "gradients_sha256": (
            "80145f7ca4297bf7dc7df12529567bb4e91a0dfa8a64c3ea3b74809a074616a2"
        ),
    },
    "cccc": {
        "component_id": "n_butane_c4",
        "formula": "C4H10",
        "mapped_smiles": (
            "[H:5][C:1]([H:6])([H:7])[C:3]([H:11])([H:12])"
            "[C:4]([H:13])([H:14])[C:2]([H:8])([H:9])[H:10]"
        ),
        "atomic_numbers": (6, 6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1),
        "connectivity": (
            (0, 2, 1.0),
            (0, 4, 1.0),
            (0, 5, 1.0),
            (0, 6, 1.0),
            (1, 3, 1.0),
            (1, 7, 1.0),
            (1, 8, 1.0),
            (1, 9, 1.0),
            (2, 3, 1.0),
            (2, 10, 1.0),
            (2, 11, 1.0),
            (3, 12, 1.0),
            (3, 13, 1.0),
        ),
        "conformations_sha256": (
            "2fe76411ce91fd3c57ffc592d4712c46496c4f3fc0dde95cdc3e61cedc0b95a9"
        ),
        "energies_sha256": (
            "1181069e78c8190aaa21095f07fa4beac400c3c18751a615779a87001a9206aa"
        ),
        "gradients_sha256": (
            "768fd1a07a9067d9bfc4ead711c0aaf7f5fbb2111c872d2464ba9ce010d7704e"
        ),
    },
}

_TOP_KEYS = frozenset(
    {
        "schema_id",
        "artifact_purpose",
        "evidence_scope",
        "source",
        "quantum_reference",
        "binary_encoding",
        "split",
        "coverage",
        "family_evidence_gaps",
        "nonpromotion",
        "groups",
        "core_sha256",
    }
)
_SOURCE_KEYS = frozenset(
    {
        "release_id",
        "doi",
        "landing_page_url",
        "artifact_name",
        "download_url",
        "artifact_byte_count",
        "artifact_upstream_md5",
        "whole_file_authentication_status",
        "github_repository_url",
        "github_tag",
        "github_commit",
        "upstream_license_declaration",
        "license_human_review_status",
        "qcarchive_server_url",
        "qcarchive_dataset_id",
        "qcarchive_dataset_type",
        "qcarchive_dataset_name",
        "qcarchive_specification_name",
    }
)
_QUANTUM_KEYS = frozenset(
    {
        "subset_id",
        "method",
        "basis",
        "program",
        "program_version",
        "qcengine_version",
        "provenance_routine",
        "provenance_module",
        "driver",
        "keywords",
        "protocols",
        "record_status",
        "compute_history_count_per_record",
        "qcarchive_crosscheck_status",
        "record_created_time_range",
        "record_modified_time_range",
        "coordinate_unit",
        "energy_unit",
        "gradient_unit",
        "gradient_semantics",
        "source_conformation_dtype",
        "source_energy_dtype",
        "source_gradient_dtype",
    }
)
_BINARY_KEYS = frozenset(
    {
        "geometry_encoding",
        "energy_encoding",
        "gradient_encoding",
        "value_hash_algorithm",
        "group_hash_order",
        "record_payload_hash_recipe",
    }
)
_SPLIT_KEYS = frozenset(
    {
        "policy_id",
        "assignment_key",
        "target_value_independent",
        "partition_order",
        "per_group_counts",
        "per_group_pair_counts",
        "source_pair_definition",
        "source_pair_membership",
        "pair_hash_recipe",
        "record_overlap_allowed",
        "geometry_overlap_allowed",
        "source_pair_overlap_allowed",
        "same_molecular_graph_cross_partition_policy",
    }
)
_COVERAGE_KEYS = frozenset(
    {
        "group_ids",
        "group_count",
        "record_count",
        "unique_geometry_count",
        "atom_counts",
        "atom_instances",
        "geometry_scalar_count",
        "energy_scalar_count",
        "gradient_scalar_count",
    }
)
_GAP_KEYS = frozenset(
    {
        "bond",
        "angle",
        "proper_torsion",
        "improper_torsion",
        "partial_charge",
        "lennard_jones",
        "coulomb_method",
        "one_four_scaling",
        "absolute_cross_molecule_energy_fitting",
    }
)
_NONPROMOTION_KEYS = frozenset(
    {
        "dataset_evidence_integrity",
        "license_human_reviewed",
        "source_whole_file_authenticated",
        "candidate_fitting_performed",
        "candidate_parameter_set_available",
        "parameter_family_sufficiency_assessed",
        "reference_validation_performed",
        "production_parameters_available",
        "parameterability_assessed",
        "parameterizable",
        "physics_ready",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
    }
)
_GROUP_KEYS = frozenset(
    {
        "group_id",
        "component_id",
        "formula",
        "mapped_smiles",
        "atomic_numbers",
        "atom_count",
        "molecular_charge",
        "molecular_multiplicity",
        "connectivity",
        "source_record_count",
        "source_array_sha256",
        "partition_counts",
        "records",
    }
)
_SOURCE_ARRAY_HASH_KEYS = frozenset(
    {"conformations", "dft_total_energy", "dft_total_gradient"}
)
_PARTITION_COUNT_KEYS = frozenset({"fit", "selection", "holdout"})
_RECORD_KEYS = frozenset(
    {
        "record_id",
        "source_index",
        "source_pair_id",
        "partition",
        "geometry_binary32_be_hex",
        "energy_binary64_be_hex",
        "gradient_binary32_be_hex",
        "geometry_sha256",
        "energy_sha256",
        "gradient_sha256",
        "record_payload_sha256",
        "qcarchive_entry_name",
        "qcarchive_record_id",
        "qcarchive_molecule_id",
        "qcarchive_molecule_hash",
        "qcarchive_specification_name",
    }
)

_FROZEN_SOURCE = {
    "release_id": SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE,
    "doi": SPICE_C1C4_QUANTUM_REFERENCE_DOI,
    "landing_page_url": "https://doi.org/10.5281/zenodo.10975225",
    "artifact_name": "SPICE-2.0.1.hdf5",
    "download_url": (
        "https://zenodo.org/api/records/10975225/files/SPICE-2.0.1.hdf5/content"
    ),
    "artifact_byte_count": 37479271148,
    "artifact_upstream_md5": "bfba2224b6540e1390a579569b475510",
    "whole_file_authentication_status": (
        "upstream_reported_md5_only_not_locally_recomputed"
    ),
    "github_repository_url": "https://github.com/openmm/spice-dataset",
    "github_tag": "2.0.1",
    "github_commit": "b99b3f4d85585df6bdfeca5a56420c57ec6385f1",
    "upstream_license_declaration": "CC0-1.0",
    "license_human_review_status": "pending",
    "qcarchive_server_url": "https://ml.qcarchive.molssi.org",
    "qcarchive_dataset_id": 340,
    "qcarchive_dataset_type": "singlepoint",
    "qcarchive_dataset_name": SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
    "qcarchive_specification_name": "spec_4",
}
_FROZEN_QUANTUM_REFERENCE = {
    "subset_id": SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
    "method": "wb97m-d3bj",
    "basis": "def2-tzvppd",
    "program": "psi4",
    "program_version": "1.4.1",
    "qcengine_version": "v0.20.1",
    "provenance_routine": "psi4.schema_runner.run_qcschema",
    "provenance_module": "scf",
    "driver": "gradient",
    "keywords": {
        "maxiter": 200,
        "scf_properties": [
            "dipole",
            "quadrupole",
            "wiberg_lowdin_indices",
            "mayer_indices",
            "mbis_charges",
        ],
        "wcombine": False,
    },
    "protocols": {"wavefunction": "orbitals_and_eigenvalues"},
    "record_status": "complete",
    "compute_history_count_per_record": 1,
    "qcarchive_crosscheck_status": (
        "all_200_energy_float64_exact_and_gradient_float32_cast_exact"
    ),
    "record_created_time_range": [
        "2021-12-09T16:27:57.455874+00:00",
        "2021-12-09T22:24:09.433847+00:00",
    ],
    "record_modified_time_range": [
        "2022-01-05T04:57:32.153916+00:00",
        "2022-01-05T07:07:13.058756+00:00",
    ],
    "coordinate_unit": "bohr",
    "energy_unit": "hartree",
    "gradient_unit": "hartree/bohr",
    "gradient_semantics": "energy_derivative_not_labeled_as_force",
    "source_conformation_dtype": "float32",
    "source_energy_dtype": "float64",
    "source_gradient_dtype": "float32",
}
_FROZEN_BINARY_ENCODING = {
    "geometry_encoding": "ieee754_binary32_big_endian_hex",
    "energy_encoding": "ieee754_binary64_big_endian_hex",
    "gradient_encoding": "ieee754_binary32_big_endian_hex",
    "value_hash_algorithm": "sha256",
    "group_hash_order": "ascending_source_index_raw_big_endian_bytes",
    "record_payload_hash_recipe": (
        "sha256(utf8('spice-c1c4-record-v1\\0')||geometry||energy||gradient)"
    ),
}
_FROZEN_SPLIT = {
    "policy_id": SPICE_C1C4_QUANTUM_REFERENCE_SPLIT_POLICY_ID,
    "assignment_key": "ascending_pair_sha256_then_pair_id",
    "target_value_independent": True,
    "partition_order": ["fit", "selection", "holdout"],
    "per_group_counts": {"fit": 30, "selection": 10, "holdout": 10},
    "per_group_pair_counts": {"fit": 15, "selection": 5, "holdout": 5},
    "source_pair_definition": "numeric_qcarchive_entry_suffix_modulo_25",
    "source_pair_membership": "entry_suffixes_pair_id_and_pair_id_plus_25",
    "pair_hash_recipe": (
        "sha256(utf8('SPICE-2.0.1:C1-C4:pair-split:v1')||nul||"
        "lowercase_group_id||nul||ascii_decimal_pair_id)"
    ),
    "record_overlap_allowed": False,
    "geometry_overlap_allowed": False,
    "source_pair_overlap_allowed": False,
    "same_molecular_graph_cross_partition_policy": (
        "allowed_only_for_within_chemistry_unseen_conformation_evidence"
    ),
}
_FROZEN_COVERAGE = {
    "group_ids": ["c", "cc", "ccc", "cccc"],
    "group_count": 4,
    "record_count": 200,
    "unique_geometry_count": 200,
    "atom_counts": [5, 8, 11, 14],
    "atom_instances": 1900,
    "geometry_scalar_count": 5700,
    "energy_scalar_count": 200,
    "gradient_scalar_count": 5700,
}
_FROZEN_FAMILY_GAPS = {
    "bond": "no_decomposition_or_fit_performed",
    "angle": "no_decomposition_or_fit_performed",
    "proper_torsion": "no_decomposition_or_fit_performed",
    "improper_torsion": "not_identified_or_fit",
    "partial_charge": ("not_evidenced_by_total_monomer_energy_and_gradient_targets"),
    "lennard_jones": ("not_evidenced_by_isolated_monomer_energy_and_gradient_targets"),
    "coulomb_method": "not_selected_or_validated",
    "one_four_scaling": "not_selected_or_validated",
    "absolute_cross_molecule_energy_fitting": (
        "prohibited_without_reference_energy_or_relative_energy_protocol"
    ),
}
_FROZEN_NONPROMOTION = {
    "dataset_evidence_integrity": True,
    "license_human_reviewed": False,
    "source_whole_file_authenticated": False,
    "candidate_fitting_performed": False,
    "candidate_parameter_set_available": False,
    "parameter_family_sufficiency_assessed": False,
    "reference_validation_performed": False,
    "production_parameters_available": False,
    "parameterability_assessed": False,
    "parameterizable": False,
    "physics_ready": False,
    "runtime_eligible": False,
    "execution_authorized": False,
    "claim_safe": False,
}


class SpiceC1C4QuantumReferenceContractError(ValueError):
    """Raised when the frozen evidence artifact violates its contract."""


@dataclass(frozen=True, order=True, slots=True)
class SpiceC1C4QuantumRecord:
    record_id: str
    source_index: int
    source_pair_id: int
    partition: str
    geometry_binary32_be_hex: str
    energy_binary64_be_hex: str
    gradient_binary32_be_hex: str
    geometry_sha256: str
    energy_sha256: str
    gradient_sha256: str
    record_payload_sha256: str
    qcarchive_entry_name: str
    qcarchive_record_id: int
    qcarchive_molecule_id: int
    qcarchive_molecule_hash: str
    qcarchive_specification_name: str


@dataclass(frozen=True, slots=True)
class SpiceC1C4MoleculeEvidence:
    group_id: str
    component_id: str
    formula: str
    mapped_smiles: str
    atomic_numbers: tuple[int, ...]
    molecular_charge: float
    molecular_multiplicity: int
    connectivity: tuple[tuple[int, int, float], ...]
    records: tuple[SpiceC1C4QuantumRecord, ...]
    conformations_sha256: str
    energies_sha256: str
    gradients_sha256: str

    @property
    def atom_count(self) -> int:
        return len(self.atomic_numbers)


@dataclass(frozen=True, slots=True)
class SpiceC1C4QuantumReferenceCorpus:
    groups: tuple[SpiceC1C4MoleculeEvidence, ...]
    core_sha256: str
    artifact_sha256: str
    artifact_byte_count: int

    @property
    def records(self) -> tuple[SpiceC1C4QuantumRecord, ...]:
        return tuple(record for group in self.groups for record in group.records)


@dataclass(frozen=True, slots=True)
class SpiceC1C4QuantumReferenceAdmissionReport:
    _factory_token: InitVar[object]
    schema_id: str
    evidence_schema_id: str
    source_release: str
    source_doi: str
    subset_id: str
    group_count: int
    record_count: int
    unique_geometry_count: int
    fit_record_count: int
    selection_record_count: int
    holdout_record_count: int
    fit_pair_count: int
    selection_pair_count: int
    holdout_pair_count: int
    exact_record_overlap_count: int
    geometry_overlap_count: int
    qcarchive_molecule_id_overlap_count: int
    source_pair_overlap_count: int
    molecular_graph_overlap_count: int
    molecular_graph_disjoint: bool
    time_disjoint: bool
    release_disjoint: bool
    generic_validation_split: bool
    claim_scope: str
    core_sha256: str
    artifact_sha256: str
    dataset_evidence_integrity: bool = True
    license_human_reviewed: bool = False
    source_whole_file_authenticated: bool = False
    candidate_fitting_performed: bool = False
    candidate_parameter_set_available: bool = False
    parameter_family_sufficiency_assessed: bool = False
    reference_validation_performed: bool = False
    production_parameters_available: bool = False
    parameterability_assessed: bool = False
    parameterizable: bool = False
    physics_ready: bool = False
    runtime_eligible: bool = False
    execution_authorized: bool = False
    claim_safe: bool = False

    def __post_init__(self, _factory_token: object) -> None:
        if _factory_token is not _REPORT_FACTORY_TOKEN:
            raise TypeError(
                "admission reports are factory-only; replay the evidence bytes"
            )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SpiceC1C4QuantumReferenceContractError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise SpiceC1C4QuantumReferenceContractError(
        f"non-standard JSON constant {value!r} is prohibited"
    )


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("ascii")
            + b"\n"
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SpiceC1C4QuantumReferenceContractError(
            f"canonical JSON encoding failed: {exc}"
        ) from exc


def _core_sha256(document: Mapping[str, Any]) -> str:
    core = dict(document)
    core.pop("core_sha256", None)
    return hashlib.sha256(_canonical_json_bytes(core)).hexdigest()


def _exact_object(
    value: Any,
    expected_keys: frozenset[str],
    location: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} must be an exact JSON object"
        )
    observed = set(value)
    if observed != expected_keys:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} keys mismatch: "
            f"missing={sorted(expected_keys - observed)}, "
            f"unexpected={sorted(observed - expected_keys)}"
        )
    return value


def _require_exact(value: Any, expected: Any, location: str) -> None:
    if type(value) is not type(expected) or value != expected:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} does not match the frozen evidence contract"
        )


def _require_sha256(value: Any, location: str) -> str:
    if type(value) is not str or _LOWER_SHA256.fullmatch(value) is None:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} must be a lowercase SHA-256 digest"
        )
    return value


def _decode_finite_hex(
    value: Any,
    *,
    byte_count: int,
    format_code: str,
    location: str,
) -> bytes:
    if (
        type(value) is not str
        or len(value) != byte_count * 2
        or _LOWER_HEX.fullmatch(value) is None
    ):
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} has the wrong canonical hexadecimal width"
        )
    raw = bytes.fromhex(value)
    for (number,) in struct.iter_unpack(format_code, raw):
        if not math.isfinite(number):
            raise SpiceC1C4QuantumReferenceContractError(
                f"{location} contains a non-finite IEEE-754 value"
            )
    return raw


def _parse_document(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError("SPICE evidence payload must be exact bytes")
    if not data:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence payload must not be empty"
        )
    if len(data) > _MAX_CORPUS_BYTES:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence payload exceeds the fixed byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence payload must be strict ASCII"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except SpiceC1C4QuantumReferenceContractError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise SpiceC1C4QuantumReferenceContractError(
            f"invalid SPICE evidence JSON: {exc}"
        ) from exc
    document = _exact_object(value, _TOP_KEYS, "corpus")
    if _canonical_json_bytes(document) != data:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence payload is not canonical ASCII JSON"
        )
    return document


def _validate_frozen_metadata(document: Mapping[str, Any]) -> None:
    _require_exact(
        document["schema_id"],
        _FROZEN_SCHEMA_ID,
        "schema_id",
    )
    _require_exact(
        document["artifact_purpose"],
        "bounded_quantum_reference_evidence_only",
        "artifact_purpose",
    )
    _require_exact(
        document["evidence_scope"],
        "spice_2_0_1_des_monomer_c1_c4_exact_200_records",
        "evidence_scope",
    )
    metadata = (
        ("source", _SOURCE_KEYS, _FROZEN_SOURCE),
        ("quantum_reference", _QUANTUM_KEYS, _FROZEN_QUANTUM_REFERENCE),
        ("binary_encoding", _BINARY_KEYS, _FROZEN_BINARY_ENCODING),
        ("split", _SPLIT_KEYS, _FROZEN_SPLIT),
        ("coverage", _COVERAGE_KEYS, _FROZEN_COVERAGE),
        ("family_evidence_gaps", _GAP_KEYS, _FROZEN_FAMILY_GAPS),
        ("nonpromotion", _NONPROMOTION_KEYS, _FROZEN_NONPROMOTION),
    )
    for location, keys, frozen in metadata:
        value = _exact_object(document[location], keys, location)
        _require_exact(value, frozen, location)
    source = document["source"]
    assert type(source) is dict
    if _LOWER_MD5.fullmatch(source["artifact_upstream_md5"]) is None:
        raise SpiceC1C4QuantumReferenceContractError(
            "source artifact_upstream_md5 must be lowercase MD5 text"
        )


def _load_group(
    value: Any,
    expected_group_id: str,
) -> SpiceC1C4MoleculeEvidence:
    location = f"groups[{expected_group_id}]"
    group = _exact_object(value, _GROUP_KEYS, location)
    spec = _GROUP_SPECS[expected_group_id]
    for key in ("group_id", "component_id", "formula", "mapped_smiles"):
        expected = expected_group_id if key == "group_id" else spec[key]
        _require_exact(group[key], expected, f"{location}.{key}")

    expected_atomic_numbers = list(spec["atomic_numbers"])
    _require_exact(
        group["atomic_numbers"],
        expected_atomic_numbers,
        f"{location}.atomic_numbers",
    )
    atom_count = len(expected_atomic_numbers)
    _require_exact(group["atom_count"], atom_count, f"{location}.atom_count")
    _require_exact(group["molecular_charge"], 0.0, f"{location}.molecular_charge")
    _require_exact(
        group["molecular_multiplicity"],
        1,
        f"{location}.molecular_multiplicity",
    )
    expected_connectivity = [list(row) for row in spec["connectivity"]]
    _require_exact(
        group["connectivity"],
        expected_connectivity,
        f"{location}.connectivity",
    )
    _require_exact(
        group["source_record_count"],
        50,
        f"{location}.source_record_count",
    )
    hashes = _exact_object(
        group["source_array_sha256"],
        _SOURCE_ARRAY_HASH_KEYS,
        f"{location}.source_array_sha256",
    )
    expected_hashes = {
        "conformations": spec["conformations_sha256"],
        "dft_total_energy": spec["energies_sha256"],
        "dft_total_gradient": spec["gradients_sha256"],
    }
    _require_exact(hashes, expected_hashes, f"{location}.source_array_sha256")
    counts = _exact_object(
        group["partition_counts"],
        _PARTITION_COUNT_KEYS,
        f"{location}.partition_counts",
    )
    _require_exact(
        counts,
        {"fit": 30, "selection": 10, "holdout": 10},
        f"{location}.partition_counts",
    )
    values = group["records"]
    if type(values) is not list or len(values) != 50:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location}.records must contain exactly 50 rows"
        )

    records: list[SpiceC1C4QuantumRecord] = []
    geometry_chunks: list[bytes] = []
    energy_chunks: list[bytes] = []
    gradient_chunks: list[bytes] = []
    for source_index, raw_record in enumerate(values):
        record_location = f"{location}.records[{source_index}]"
        record = _exact_object(raw_record, _RECORD_KEYS, record_location)
        _require_exact(
            record["source_index"],
            source_index,
            f"{record_location}.source_index",
        )
        entry_name = record["qcarchive_entry_name"]
        if (
            type(entry_name) is not str
            or re.fullmatch(rf"{expected_group_id}-(?:0|[1-9][0-9]?)", entry_name)
            is None
        ):
            raise SpiceC1C4QuantumReferenceContractError(
                f"{record_location}.qcarchive_entry_name is invalid"
            )
        entry_suffix = int(entry_name.rsplit("-", 1)[1])
        expected_pair_id = entry_suffix % 25
        _require_exact(
            record["source_pair_id"],
            expected_pair_id,
            f"{record_location}.source_pair_id",
        )
        for id_field in ("qcarchive_record_id", "qcarchive_molecule_id"):
            if type(record[id_field]) is not int or record[id_field] <= 0:
                raise SpiceC1C4QuantumReferenceContractError(
                    f"{record_location}.{id_field} must be a positive exact integer"
                )
        molecule_hash = record["qcarchive_molecule_hash"]
        if (
            type(molecule_hash) is not str
            or _LOWER_HEX40.fullmatch(molecule_hash) is None
        ):
            raise SpiceC1C4QuantumReferenceContractError(
                f"{record_location}.qcarchive_molecule_hash is invalid"
            )
        _require_exact(
            record["qcarchive_specification_name"],
            "spec_4",
            f"{record_location}.qcarchive_specification_name",
        )
        _require_exact(
            record["record_id"],
            (f"qcarchive:340:spec_4:{entry_name}:{record['qcarchive_record_id']}"),
            f"{record_location}.record_id",
        )
        if type(record["partition"]) is not str or record["partition"] not in {
            "fit",
            "selection",
            "holdout",
        }:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{record_location}.partition is invalid"
            )
        geometry = _decode_finite_hex(
            record["geometry_binary32_be_hex"],
            byte_count=atom_count * 3 * 4,
            format_code=">f",
            location=f"{record_location}.geometry",
        )
        energy = _decode_finite_hex(
            record["energy_binary64_be_hex"],
            byte_count=8,
            format_code=">d",
            location=f"{record_location}.energy",
        )
        gradient = _decode_finite_hex(
            record["gradient_binary32_be_hex"],
            byte_count=atom_count * 3 * 4,
            format_code=">f",
            location=f"{record_location}.gradient",
        )
        for field_name, raw in (
            ("geometry", geometry),
            ("energy", energy),
            ("gradient", gradient),
        ):
            observed = _require_sha256(
                record[f"{field_name}_sha256"],
                f"{record_location}.{field_name}_sha256",
            )
            if hashlib.sha256(raw).hexdigest() != observed:
                raise SpiceC1C4QuantumReferenceContractError(
                    f"{record_location}.{field_name}_sha256 mismatch"
                )
        payload_sha256 = _require_sha256(
            record["record_payload_sha256"],
            f"{record_location}.record_payload_sha256",
        )
        if (
            hashlib.sha256(
                _RECORD_HASH_DOMAIN + geometry + energy + gradient
            ).hexdigest()
            != payload_sha256
        ):
            raise SpiceC1C4QuantumReferenceContractError(
                f"{record_location}.record_payload_sha256 mismatch"
            )
        geometry_chunks.append(geometry)
        energy_chunks.append(energy)
        gradient_chunks.append(gradient)
        records.append(
            SpiceC1C4QuantumRecord(**{key: record[key] for key in _RECORD_KEYS})
        )

    for field_name, chunks in (
        ("conformations", geometry_chunks),
        ("dft_total_energy", energy_chunks),
        ("dft_total_gradient", gradient_chunks),
    ):
        if hashlib.sha256(b"".join(chunks)).hexdigest() != hashes[field_name]:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{location}.{field_name} aggregate source digest mismatch"
            )

    entry_names = [record.qcarchive_entry_name for record in records]
    if entry_names != sorted(entry_names) or set(entry_names) != {
        f"{expected_group_id}-{index}" for index in range(50)
    }:
        raise SpiceC1C4QuantumReferenceContractError(
            f"{location} QCArchive entry coverage/order mismatch"
        )

    rows_by_pair: dict[int, list[SpiceC1C4QuantumRecord]] = {
        pair_id: [] for pair_id in range(25)
    }
    for row in records:
        rows_by_pair[row.source_pair_id].append(row)
    for pair_id, pair_rows in rows_by_pair.items():
        observed_suffixes = {
            int(row.qcarchive_entry_name.rsplit("-", 1)[1]) for row in pair_rows
        }
        if observed_suffixes != {pair_id, pair_id + 25}:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{location} source pair {pair_id} membership mismatch"
            )
        if len({row.partition for row in pair_rows}) != 1:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{location} source pair {pair_id} crosses partitions"
            )

    pair_hash_domain = b"SPICE-2.0.1:C1-C4:pair-split:v1"
    ordered_pair_ids = sorted(
        range(25),
        key=lambda pair_id: (
            hashlib.sha256(
                pair_hash_domain
                + b"\0"
                + expected_group_id.lower().encode("ascii")
                + b"\0"
                + str(pair_id).encode("ascii")
            ).digest(),
            pair_id,
        ),
    )
    expected_partition_by_pair: dict[int, str] = {}
    for rank, pair_id in enumerate(ordered_pair_ids):
        partition = "fit" if rank < 15 else "selection" if rank < 20 else "holdout"
        expected_partition_by_pair[pair_id] = partition
    for row in records:
        if row.partition != expected_partition_by_pair[row.source_pair_id]:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{location} target-independent source-pair partition assignment "
                "mismatch"
            )

    return SpiceC1C4MoleculeEvidence(
        group_id=expected_group_id,
        component_id=spec["component_id"],
        formula=spec["formula"],
        mapped_smiles=spec["mapped_smiles"],
        atomic_numbers=tuple(expected_atomic_numbers),
        molecular_charge=0.0,
        molecular_multiplicity=1,
        connectivity=tuple(tuple(row) for row in expected_connectivity),
        records=tuple(records),
        conformations_sha256=hashes["conformations"],
        energies_sha256=hashes["dft_total_energy"],
        gradients_sha256=hashes["dft_total_gradient"],
    )


def load_spice_c1c4_quantum_reference_evidence(
    data: bytes,
) -> SpiceC1C4QuantumReferenceCorpus:
    """Verify and load the one frozen C1-C4 SPICE evidence corpus."""

    document = _parse_document(data)
    _validate_frozen_metadata(document)
    supplied_core_sha256 = _require_sha256(document["core_sha256"], "core_sha256")
    computed_core_sha256 = _core_sha256(document)
    if computed_core_sha256 != supplied_core_sha256:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence core self-hash mismatch"
        )

    values = document["groups"]
    if type(values) is not list or len(values) != 4:
        raise SpiceC1C4QuantumReferenceContractError(
            "groups must contain exactly c, cc, ccc, and cccc"
        )
    groups = tuple(
        _load_group(value, expected_group_id)
        for value, expected_group_id in zip(values, _GROUP_SPECS, strict=True)
    )
    records = tuple(record for group in groups for record in group.records)
    if len(records) != 200:
        raise SpiceC1C4QuantumReferenceContractError(
            "frozen evidence must contain exactly 200 records"
        )
    geometry_hashes = [record.geometry_sha256 for record in records]
    record_hashes = [record.record_payload_sha256 for record in records]
    source_ids = [record.record_id for record in records]
    qcarchive_record_ids = [record.qcarchive_record_id for record in records]
    qcarchive_molecule_ids = [record.qcarchive_molecule_id for record in records]
    qcarchive_molecule_hashes = [record.qcarchive_molecule_hash for record in records]
    if len(set(geometry_hashes)) != 200:
        raise SpiceC1C4QuantumReferenceContractError(
            "geometry overlap across records or partitions is prohibited"
        )
    if len(set(record_hashes)) != 200:
        raise SpiceC1C4QuantumReferenceContractError(
            "record payload overlap across partitions is prohibited"
        )
    for values_for_identity, identity_name in (
        (source_ids, "source record ID"),
        (qcarchive_record_ids, "QCArchive record ID"),
        (qcarchive_molecule_ids, "QCArchive molecule ID"),
        (qcarchive_molecule_hashes, "QCArchive molecule hash"),
    ):
        if len(set(values_for_identity)) != 200:
            raise SpiceC1C4QuantumReferenceContractError(
                f"{identity_name} coverage must be unique for all 200 records"
            )
    observed_partition_counts = {
        name: sum(record.partition == name for record in records)
        for name in ("fit", "selection", "holdout")
    }
    if observed_partition_counts != {"fit": 120, "selection": 40, "holdout": 40}:
        raise SpiceC1C4QuantumReferenceContractError(
            "global partition counts do not match 120/40/40"
        )

    artifact_sha256 = hashlib.sha256(data).hexdigest()
    if supplied_core_sha256 != _FROZEN_CORE_SHA256:
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence core is not the frozen reviewed corpus"
        )
    if (
        artifact_sha256 != _FROZEN_ARTIFACT_SHA256
        or len(data) != _FROZEN_ARTIFACT_BYTE_COUNT
    ):
        raise SpiceC1C4QuantumReferenceContractError(
            "SPICE evidence bytes are not the frozen reviewed artifact"
        )
    return SpiceC1C4QuantumReferenceCorpus(
        groups=groups,
        core_sha256=supplied_core_sha256,
        artifact_sha256=artifact_sha256,
        artifact_byte_count=len(data),
    )


def admit_spice_c1c4_quantum_reference_evidence(
    data: bytes,
) -> SpiceC1C4QuantumReferenceAdmissionReport:
    """Admit dataset evidence without promoting any parameter/runtime claim."""

    corpus = load_spice_c1c4_quantum_reference_evidence(data)
    records = corpus.records
    by_partition = {
        partition: tuple(record for record in records if record.partition == partition)
        for partition in ("fit", "selection", "holdout")
    }

    def _pairwise_overlap_count(attribute: str) -> int:
        partition_sets = [
            {getattr(record, attribute) for record in by_partition[partition]}
            for partition in ("fit", "selection", "holdout")
        ]
        return len(
            (partition_sets[0] & partition_sets[1])
            | (partition_sets[0] & partition_sets[2])
            | (partition_sets[1] & partition_sets[2])
        )

    graph_sets = [
        {
            group.group_id
            for group in corpus.groups
            if any(record.partition == partition for record in group.records)
        }
        for partition in ("fit", "selection", "holdout")
    ]
    source_pair_sets = [
        {
            (group.group_id, record.source_pair_id)
            for group in corpus.groups
            for record in group.records
            if record.partition == partition
        }
        for partition in ("fit", "selection", "holdout")
    ]
    source_pair_overlap_count = len(
        (source_pair_sets[0] & source_pair_sets[1])
        | (source_pair_sets[0] & source_pair_sets[2])
        | (source_pair_sets[1] & source_pair_sets[2])
    )
    molecular_graph_overlap_count = len(set.intersection(*graph_sets))
    return SpiceC1C4QuantumReferenceAdmissionReport(
        _factory_token=_REPORT_FACTORY_TOKEN,
        schema_id=SPICE_C1C4_QUANTUM_REFERENCE_ADMISSION_REPORT_SCHEMA_ID,
        evidence_schema_id=_FROZEN_SCHEMA_ID,
        source_release=_FROZEN_SOURCE_RELEASE,
        source_doi=_FROZEN_SOURCE_DOI,
        subset_id=_FROZEN_SUBSET,
        group_count=len(corpus.groups),
        record_count=len(records),
        unique_geometry_count=len({record.geometry_sha256 for record in records}),
        fit_record_count=sum(record.partition == "fit" for record in records),
        selection_record_count=sum(
            record.partition == "selection" for record in records
        ),
        holdout_record_count=sum(record.partition == "holdout" for record in records),
        fit_pair_count=len(source_pair_sets[0]),
        selection_pair_count=len(source_pair_sets[1]),
        holdout_pair_count=len(source_pair_sets[2]),
        exact_record_overlap_count=_pairwise_overlap_count("record_id"),
        geometry_overlap_count=_pairwise_overlap_count("geometry_sha256"),
        qcarchive_molecule_id_overlap_count=_pairwise_overlap_count(
            "qcarchive_molecule_id"
        ),
        source_pair_overlap_count=source_pair_overlap_count,
        molecular_graph_overlap_count=molecular_graph_overlap_count,
        molecular_graph_disjoint=molecular_graph_overlap_count == 0,
        time_disjoint=False,
        release_disjoint=False,
        generic_validation_split=False,
        claim_scope="within_same_four_graphs_unseen_conformations_only",
        core_sha256=corpus.core_sha256,
        artifact_sha256=corpus.artifact_sha256,
    )


def serialize_spice_c1c4_quantum_reference_admission_report(data: bytes) -> bytes:
    """Replay the frozen evidence and serialize its nonpromoting report."""

    report = admit_spice_c1c4_quantum_reference_evidence(data)
    return _canonical_json_bytes(asdict(report))


__all__ = [
    "SPICE_C1C4_QUANTUM_REFERENCE_ADMISSION_REPORT_SCHEMA_ID",
    "SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_BYTE_COUNT",
    "SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256",
    "SPICE_C1C4_QUANTUM_REFERENCE_CORE_SHA256",
    "SPICE_C1C4_QUANTUM_REFERENCE_DOI",
    "SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID",
    "SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE",
    "SPICE_C1C4_QUANTUM_REFERENCE_SPLIT_POLICY_ID",
    "SPICE_C1C4_QUANTUM_REFERENCE_SUBSET",
    "SpiceC1C4MoleculeEvidence",
    "SpiceC1C4QuantumRecord",
    "SpiceC1C4QuantumReferenceAdmissionReport",
    "SpiceC1C4QuantumReferenceContractError",
    "SpiceC1C4QuantumReferenceCorpus",
    "admit_spice_c1c4_quantum_reference_evidence",
    "load_spice_c1c4_quantum_reference_evidence",
    "serialize_spice_c1c4_quantum_reference_admission_report",
]
