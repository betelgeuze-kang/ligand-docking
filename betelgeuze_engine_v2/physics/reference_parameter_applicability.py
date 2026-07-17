"""Frozen H5 parameter-origin and runtime-applicability boundary record.

The Engine v2 reference force-field evaluator accepts an explicit
``ReferenceForceFieldParameters`` object from its caller.  The package does not
ship a production parameter set, parse the reviewed OpenFF artifact, assign
parameters or charges, or bind values from that artifact to runtime inputs.

This module records that distinction alongside the exact runtime equations,
code-enforced admission checks, configurable capacity defaults, and source-code
identities.  The runtime envelope is an implementation safety boundary only;
it is not a scientifically validated molecular applicability domain and does
not authorize fitting, validation studies, product use, or customer execution.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any, Mapping

from betelgeuze_engine_v2.parameter_source_provenance import (
    FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256,
    PARAMETER_SOURCE_ARTIFACT_SHA256,
    PARAMETER_SOURCE_ID,
    PARAMETER_SOURCE_RELEASE_TAG,
    PARAMETER_SOURCE_VERSION,
)
from betelgeuze_engine_v2.physics.reference_parameters import (
    REFERENCE_PARAMETER_SCHEMA_ID,
    ReferenceApplicabilityDomain,
)


REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_parameter_applicability_record/1.0.0"
)
REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID = (
    "h5_reference_physics_parameter_origin_and_runtime_envelope/1.0.0"
)
REFERENCE_PARAMETER_APPLICABILITY_RECORD_VERSION = "1.0.0"
REFERENCE_PARAMETER_APPLICABILITY_REVIEWED_AT_UTC = "2026-07-17T01:59:30Z"
REFERENCE_PARAMETER_APPLICABILITY_REVIEWER_ROLE = "repository_maintainer"
REFERENCE_PARAMETER_APPLICABILITY_REVIEWER_IDENTITY_SHA256 = (
    "ffaaea9cebb5975ed140fa0633ea4cb44e1f241f6bc73c916164c0ea5123b584"
)
FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256 = (
    "63c3ae48ed755a360afd4c9ed77a8553f75da4ab793e287d89a8a68b76ea7ac8"
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class ReferenceParameterApplicabilityError(ValueError):
    """The H5 record, a bound source, or a supplied document drifted."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceParameterApplicabilityError(
            "reference parameter applicability record is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_sha256(value: str, *, name: str) -> str:
    digest = str(value or "")
    if not _SHA256_RE.fullmatch(digest):
        raise ReferenceParameterApplicabilityError(
            f"{name} must be a lowercase SHA-256 digest"
        )
    return digest


@dataclass(frozen=True, slots=True)
class ReferencePhysicsSourceIdentity:
    """One repository-relative implementation source bound by exact bytes."""

    role: str
    relative_path: str
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or not self.role:
            raise ReferenceParameterApplicabilityError(
                "source identity role must be non-empty"
            )
        if not isinstance(self.relative_path, str) or not self.relative_path:
            raise ReferenceParameterApplicabilityError(
                "source identity relative_path must be non-empty"
            )
        path = PurePosixPath(self.relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ReferenceParameterApplicabilityError(
                "source identity must stay within the repository"
            )
        object.__setattr__(
            self,
            "sha256",
            _require_sha256(self.sha256, name="source identity sha256"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "relative_path": self.relative_path,
            "sha256": self.sha256,
        }


_RUNTIME_SOURCE_IDENTITIES = (
    ReferencePhysicsSourceIdentity(
        role="explicit_parameter_schema_and_capacity_defaults",
        relative_path="betelgeuze_engine_v2/physics/reference_parameters.py",
        sha256="cb72413a6ef6c33e65f3641ebfc836d1011ba4deb077ecdd5ab669317bb5e0de",
    ),
    ReferencePhysicsSourceIdentity(
        role="reference_force_field_equations_and_admission",
        relative_path="betelgeuze_engine_v2/physics/reference_forcefield.py",
        sha256="af8422789c5c9a473bce05d93b7e502d00cd0a955601ff39dbb3fd3b831648db",
    ),
    ReferencePhysicsSourceIdentity(
        role="energy_term_composition_contract",
        relative_path="betelgeuze_engine_v2/physics/composition.py",
        sha256="fb6da1b06ea2307b2fddf645ddde7c87b856c2c49e78204b1ae02071b95a0a03",
    ),
    ReferencePhysicsSourceIdentity(
        role="bounded_neighbor_graph_contract",
        relative_path="betelgeuze_engine_v2/geometry/neighbors.py",
        sha256="8026d68f86b5a93adc1e44aa56594d9f5461f180e8c383a346d85963944c7f25",
    ),
    ReferencePhysicsSourceIdentity(
        role="all_atom_system_and_orthorhombic_cell_contract",
        relative_path="betelgeuze_engine_v2/molecular/models.py",
        sha256="6e048062e5e8988855785841c8b044e805ddccd3b541b6f1ac109902a9e14448",
    ),
    ReferencePhysicsSourceIdentity(
        role="canonical_system_and_topology_identity",
        relative_path="betelgeuze_engine_v2/molecular/serialization.py",
        sha256="971d15d5630410ad6d262e256195baad2380f6826bec516484b8ed7f551c8441",
    ),
    ReferencePhysicsSourceIdentity(
        role="reviewed_candidate_source_provenance_contract",
        relative_path="betelgeuze_engine_v2/parameter_source_provenance.py",
        sha256="712526cf93540ca5247b551f2c9c3544e02c9cf3c7cd9c6807a29ba25a2c9d21",
    ),
)


def _implemented_term_semantics() -> list[dict[str, Any]]:
    return [
        {
            "term": "harmonic_bond",
            "equation": "0.5*k*(r-r0)^2",
            "parameter_origin": "caller_supplied_explicit_per_bond_rows",
        },
        {
            "term": "harmonic_angle",
            "equation": "0.5*k*(theta-theta0)^2",
            "parameter_origin": "caller_supplied_explicit_per_angle_rows",
        },
        {
            "term": "periodic_torsion",
            "equation": "amplitude*(1+cos(periodicity*phi-phase))",
            "path_semantics": "graph_implied_proper_paths_with_explicit_rows",
            "multiple_periodicity_rows_per_path_allowed": True,
            "improper_torsion_semantics_implemented": False,
        },
        {
            "term": "lennard_jones_12_6",
            "equation": "4*epsilon_ij*((sigma_ij/r)^12-(sigma_ij/r)^6)",
            "sigma_combination_rule": "arithmetic_mean",
            "epsilon_combination_rule": "geometric_mean",
        },
        {
            "term": "screened_coulomb",
            "equation": ("332.063713299*q_i*q_j*exp(-kappa*r)/(dielectric*r)"),
            "charge_origin": "caller_supplied_explicit_per_atom_values",
        },
    ]


def _runtime_admission_requirements() -> list[str]:
    return [
        "coordinate_unit_is_angstrom",
        "coordinate_tensor_is_finite_via_neighbor_graph_construction",
        "parameter_numeric_fields_are_finite_via_parameter_schema_validation",
        "canonical_topology_sha256_matches_parameter_record",
        "nonbonded_parameter_rows_exactly_cover_all_atom_indices",
        "bond_parameter_rows_exactly_cover_system_bonds",
        "angle_parameter_rows_exactly_cover_all_graph_implied_angles",
        "torsion_parameter_rows_cover_all_graph_implied_proper_paths",
        "all_parameter_indices_are_within_the_system_topology",
        "neighbor_cutoff_is_at_least_the_parameter_cutoff",
        "neighbor_graph_is_exactly_rebuilt_and_bound_to_current_system_state",
        "atom_bond_angle_torsion_and_nonbonded_pair_capacity_guards_hold",
        "nonbonded_pair_distance_is_at_least_the_configured_minimum",
        "periodic_cells_are_supported_orthorhombic_cells_only",
        "periodic_cutoff_is_strictly_below_half_the_smallest_periodic_length",
        "zero_length_angle_vectors_and_undefined_collinear_torsions_fail_closed",
    ]


def _claim_policy() -> dict[str, bool]:
    return {
        "record_frozen": True,
        "runtime_source_identities_bound": True,
        "caller_parameter_origin_recorded": True,
        "runtime_execution_envelope_documented": True,
        "reviewed_candidate_source_identity_referenced": True,
        "production_parameter_set_shipped": False,
        "reviewed_source_values_bound_to_runtime": False,
        "parameter_assignment_implemented": False,
        "partial_charge_generation_implemented": False,
        "parameter_values_calibrated": False,
        "runtime_envelope_is_scientific_applicability_domain": False,
        "molecule_or_element_coverage_validated": False,
        "force_or_energy_validated": False,
        "parameter_fitting_authorized": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


_BLOCKERS = (
    "production_reference_parameter_values_not_shipped",
    "caller_supplied_parameter_values_not_independently_reviewed",
    "reviewed_sage_source_not_bound_to_runtime_parameter_values",
    "offxml_parsing_atom_typing_and_parameter_assignment_not_implemented",
    "partial_charge_generation_and_atom_mass_assignment_not_implemented",
    "improper_torsions_constraints_long_range_and_solvation_not_supported",
    "automatic_bonded_exclusion_and_one_four_scaling_inference_not_implemented",
    "runtime_capacity_envelope_is_not_scientific_applicability_evidence",
    "molecule_element_charge_and_chemical_space_coverage_not_validated",
    "parameter_fitting_not_authorized",
    "independent_force_energy_validation_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


@dataclass(frozen=True, slots=True)
class ReferenceParameterApplicabilityRecord:
    """Immutable reviewed boundary for H5 reference-physics parameters."""

    schema_id: str
    profile_id: str
    record_version: str
    reviewed_at_utc: str
    reviewer_role: str
    reviewer_identity_sha256: str
    runtime_sources: tuple[ReferencePhysicsSourceIdentity, ...]
    parameter_source_provenance_snapshot_sha256: str
    superseded: bool = False
    revoked: bool = False

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID:
            raise ReferenceParameterApplicabilityError(
                "unsupported reference parameter applicability schema"
            )
        if self.profile_id != REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID:
            raise ReferenceParameterApplicabilityError(
                "unsupported reference parameter applicability profile"
            )
        if self.record_version != REFERENCE_PARAMETER_APPLICABILITY_RECORD_VERSION:
            raise ReferenceParameterApplicabilityError(
                "unsupported reference parameter applicability record version"
            )
        if not _UTC_RE.fullmatch(self.reviewed_at_utc):
            raise ReferenceParameterApplicabilityError(
                "review timestamp must be second-resolution UTC"
            )
        if not self.reviewer_role:
            raise ReferenceParameterApplicabilityError(
                "reviewer role must be non-empty"
            )
        object.__setattr__(
            self,
            "reviewer_identity_sha256",
            _require_sha256(
                self.reviewer_identity_sha256,
                name="reviewer identity",
            ),
        )
        object.__setattr__(
            self,
            "parameter_source_provenance_snapshot_sha256",
            _require_sha256(
                self.parameter_source_provenance_snapshot_sha256,
                name="parameter source provenance snapshot",
            ),
        )
        if not self.runtime_sources or not all(
            isinstance(row, ReferencePhysicsSourceIdentity)
            for row in self.runtime_sources
        ):
            raise ReferenceParameterApplicabilityError(
                "runtime source identities must be explicit"
            )
        roles = [row.role for row in self.runtime_sources]
        paths = [row.relative_path for row in self.runtime_sources]
        if len(roles) != len(set(roles)) or len(paths) != len(set(paths)):
            raise ReferenceParameterApplicabilityError(
                "runtime source identities must be unique"
            )
        if type(self.superseded) is not bool or type(self.revoked) is not bool:
            raise ReferenceParameterApplicabilityError(
                "review state flags must be booleans"
            )
        if self.superseded or self.revoked:
            raise ReferenceParameterApplicabilityError(
                "the frozen H5 record cannot be superseded or revoked"
            )

    def projection(self) -> dict[str, Any]:
        default_domain = ReferenceApplicabilityDomain().to_dict()
        return {
            "schema_id": self.schema_id,
            "profile_id": self.profile_id,
            "record_version": self.record_version,
            "purpose": {
                "scope": "h5_reference_physics_parameter_origin_and_runtime_envelope",
                "record_only": True,
                "enables_new_physics_execution": False,
                "authorizes_validation_study": False,
                "authorizes_parameter_fitting": False,
            },
            "parameter_origin": {
                "runtime_schema_id": REFERENCE_PARAMETER_SCHEMA_ID,
                "runtime_values_origin": (
                    "caller_supplied_explicit_ReferenceForceFieldParameters"
                ),
                "packaged_production_parameter_set": False,
                "packaged_reference_parameter_values": False,
                "offxml_parser_implemented": False,
                "atom_typing_or_parameter_assignment_implemented": False,
                "source_values_extracted": False,
                "reviewed_source_to_runtime_values_binding_established": False,
                "fit_or_training_lineage_present": False,
                "reviewed_candidate_source": {
                    "source_id": PARAMETER_SOURCE_ID,
                    "source_version": PARAMETER_SOURCE_VERSION,
                    "release_tag": PARAMETER_SOURCE_RELEASE_TAG,
                    "artifact_sha256": PARAMETER_SOURCE_ARTIFACT_SHA256,
                    "provenance_snapshot_sha256": (
                        self.parameter_source_provenance_snapshot_sha256
                    ),
                    "selection_role": ("preexisting_reviewed_candidate_identity_only"),
                    "latest_release_selection_claimed": False,
                    "parameter_coverage_validated": False,
                    "runtime_value_binding_established": False,
                },
            },
            "implemented_runtime_semantics": {
                "terms": _implemented_term_semantics(),
                "pair_policy": {
                    "excluded_pairs": "caller_supplied_explicit_pairs",
                    "scaled_pairs": "caller_supplied_explicit_lj_and_electrostatic_scales",
                    "automatic_one_four_inference": False,
                    "switch": (
                        "quintic_smoothstep_from_switch_start_to_cutoff_for_both_"
                        "nonbonded_terms"
                    ),
                },
                "periodic_policy": (
                    "minimum_image_for_supported_orthorhombic_periodic_axes_only"
                ),
                "forces": "negative_autograd_coordinate_gradient_of_total_energy",
                "energy_unit": "kcal/mol",
                "force_unit": "kcal/mol/angstrom",
                "calibrated": False,
                "validated_for_composition": False,
            },
            "runtime_execution_envelope": {
                "status": "code_enforced_admission_and_capacity_guard_only",
                "scientific_applicability_domain": False,
                "default_values_are_caller_configurable": True,
                "default_capacity_guard": default_domain,
                "admission_requirements": _runtime_admission_requirements(),
                "admission_success_means": (
                    "the_explicit_inputs_can_execute_the_bounded_reference_code_path"
                ),
                "admission_success_does_not_mean": [
                    "parameter_values_are_correct",
                    "molecule_is_within_a_validated_chemical_domain",
                    "energy_or_forces_are_physically_accurate",
                    "simulation_or_docking_is_scientifically_valid",
                ],
            },
            "scientific_applicability": {
                "status": "not_established",
                "validated_molecule_classes": [],
                "validated_elements": [],
                "validated_charge_states": [],
                "validated_bond_orders": [],
                "validated_temperature_or_ensemble": [],
                "validated_energy_force_reference_sets": [],
                "parameter_fit_dataset": None,
                "independent_holdout_dataset": None,
                "uncertainty_or_acceptance_thresholds": None,
            },
            "unsupported_or_unimplemented": [
                "smirnoff_offxml_semantic_parsing",
                "atom_typing_and_parameter_assignment",
                "partial_charge_generation",
                "atom_mass_assignment",
                "improper_torsion_semantics",
                "constraints_and_virtual_sites",
                "automatic_exclusion_or_one_four_scaling_inference",
                "nonorthorhombic_periodic_cells",
                "pme_ewald_or_other_long_range_electrostatics",
                "tail_corrections_and_long_range_dispersion",
                "implicit_or_explicit_solvation_model",
                "parameter_fitting_or_calibration",
                "minimization_dynamics_or_ensemble_validation",
            ],
            "runtime_source_identities": [
                row.to_dict() for row in self.runtime_sources
            ],
            "review": {
                "status": "reviewed_contract_boundary_only",
                "reviewed_at_utc": self.reviewed_at_utc,
                "reviewer_role": self.reviewer_role,
                "reviewer_identity_sha256": self.reviewer_identity_sha256,
                "superseded": self.superseded,
                "revoked": self.revoked,
                "supersession_record_sha256": None,
                "revocation_reason": None,
            },
            "claim_policy": _claim_policy(),
            "blockers": list(_BLOCKERS),
        }

    @property
    def record_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["record_sha256"] = self.record_sha256
        return payload


def _build_record() -> ReferenceParameterApplicabilityRecord:
    return ReferenceParameterApplicabilityRecord(
        schema_id=REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID,
        profile_id=REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID,
        record_version=REFERENCE_PARAMETER_APPLICABILITY_RECORD_VERSION,
        reviewed_at_utc=REFERENCE_PARAMETER_APPLICABILITY_REVIEWED_AT_UTC,
        reviewer_role=REFERENCE_PARAMETER_APPLICABILITY_REVIEWER_ROLE,
        reviewer_identity_sha256=(
            REFERENCE_PARAMETER_APPLICABILITY_REVIEWER_IDENTITY_SHA256
        ),
        runtime_sources=_RUNTIME_SOURCE_IDENTITIES,
        parameter_source_provenance_snapshot_sha256=(
            FROZEN_PARAMETER_SOURCE_PROVENANCE_SNAPSHOT_SHA256
        ),
    )


def frozen_reference_parameter_applicability_record() -> (
    ReferenceParameterApplicabilityRecord
):
    """Return the immutable reviewed H5 record and reject constant drift."""

    record = _build_record()
    if record.record_sha256 != FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256:
        raise ReferenceParameterApplicabilityError(
            "frozen reference parameter applicability record SHA-256 drifted"
        )
    return record


def reference_parameter_applicability_document(
    record: ReferenceParameterApplicabilityRecord | None = None,
) -> dict[str, Any]:
    """Return a detached canonical JSON-compatible H5 record document."""

    selected = record or frozen_reference_parameter_applicability_record()
    payload = selected.to_dict()
    if payload["record_sha256"] != _sha256(
        {key: value for key, value in payload.items() if key != "record_sha256"}
    ):
        raise ReferenceParameterApplicabilityError(
            "reference parameter applicability record digest is inconsistent"
        )
    return json.loads(_canonical_bytes(payload).decode("ascii"))


def require_reference_parameter_applicability_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Require exact equality with the frozen reviewed document."""

    if not isinstance(document, Mapping):
        raise ReferenceParameterApplicabilityError(
            "reference parameter applicability document must be a mapping"
        )
    observed = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    digest = observed.get("record_sha256")
    _require_sha256(digest, name="record_sha256")
    projection = {
        key: value for key, value in observed.items() if key != "record_sha256"
    }
    if digest != _sha256(projection):
        raise ReferenceParameterApplicabilityError(
            "reference parameter applicability document digest mismatch"
        )
    expected = reference_parameter_applicability_document()
    if observed != expected:
        raise ReferenceParameterApplicabilityError(
            "reference parameter applicability document does not match the frozen record"
        )
    return observed


def verify_reference_parameter_applicability_sources(
    repository_root: str | os.PathLike[str],
) -> dict[str, str]:
    """Verify exact bound implementation bytes without revealing their content."""

    root = Path(repository_root).resolve(strict=True)
    if not root.is_dir():
        raise ReferenceParameterApplicabilityError(
            "repository root must be a directory"
        )
    observed: dict[str, str] = {}
    record = frozen_reference_parameter_applicability_record()
    for source in record.runtime_sources:
        candidate = root / source.relative_path
        if candidate.is_symlink() or not candidate.is_file():
            raise ReferenceParameterApplicabilityError(
                f"bound runtime source is unavailable: {source.role}"
            )
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ReferenceParameterApplicabilityError(
                f"bound runtime source escaped the repository: {source.role}"
            ) from exc
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if digest != source.sha256:
            raise ReferenceParameterApplicabilityError(
                f"bound runtime source SHA-256 mismatch: {source.role}"
            )
        observed[source.role] = digest
    return observed


def reference_parameter_applicability_json_bytes() -> bytes:
    """Serialize the frozen record as canonical private-artifact JSON bytes."""

    document = reference_parameter_applicability_document()
    return _canonical_bytes(document) + b"\n"


def write_reference_parameter_applicability_json(
    path: str | os.PathLike[str],
) -> str:
    """Atomically write the frozen record with owner-only file permissions."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ReferenceParameterApplicabilityError(
            "refusing to replace a symlink destination"
        )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(reference_parameter_applicability_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        if destination.is_symlink():
            raise ReferenceParameterApplicabilityError(
                "refusing to replace a symlink destination"
            )
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    return FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256


__all__ = [
    "FROZEN_REFERENCE_PARAMETER_APPLICABILITY_RECORD_SHA256",
    "REFERENCE_PARAMETER_APPLICABILITY_PROFILE_ID",
    "REFERENCE_PARAMETER_APPLICABILITY_RECORD_VERSION",
    "REFERENCE_PARAMETER_APPLICABILITY_SCHEMA_ID",
    "ReferenceParameterApplicabilityError",
    "ReferenceParameterApplicabilityRecord",
    "ReferencePhysicsSourceIdentity",
    "frozen_reference_parameter_applicability_record",
    "reference_parameter_applicability_document",
    "reference_parameter_applicability_json_bytes",
    "require_reference_parameter_applicability_document",
    "verify_reference_parameter_applicability_sources",
    "write_reference_parameter_applicability_json",
]
