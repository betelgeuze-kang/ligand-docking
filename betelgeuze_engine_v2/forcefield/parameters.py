"""Exact-methane bond/angle parameter and assignment contracts.

The first V2-2 parameter schema is deliberately limited to the bond and angle
identities already established by the exact-methane molecular inventory.  It
can carry a nonphysical contract fixture or an unreviewed output from a future
versioned fitter, but neither state authorizes parameterability, energy,
forces, minimization, simulation, or product claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import struct
from types import MappingProxyType
from typing import Any, Mapping

from betelgeuze_engine_v2.contracts import ContractVersionError, SemanticVersion
from betelgeuze_engine_v2.molecular.bonded_inventory import (
    EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID,
    EXACT_METHANE_BOND_ANGLE_PROFILE_ID,
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
    ExactMethaneBondAngleInventoryReport,
    analyze_exact_methane_bond_angle_inventory,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem


_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION = "1.0.0"
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.exact_methane_bond_angle_parameter_set/"
    f"{_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION}"
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1 = "1.1.0"
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1 = (
    "betelgeuze.exact_methane_bond_angle_parameter_set/"
    f"{_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1}"
)
_FROZEN_SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS = frozenset(
    {
        _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION,
        _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1,
    }
)
_FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = (
    "harmonic_half_k_delta_squared_bond_angle/1.0.0"
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_PROFILE_ID = (
    EXACT_METHANE_BOND_ANGLE_PROFILE_ID
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE = (
    "exact_methane_bond_angle_parameter_assignment_only"
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID = (
    "exact_methane_identity_role_assignment/1.0.0"
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID = (
    EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION = (
    "1.0.0"
)
_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.exact_methane_bond_angle_parameter_assignment/"
    f"{_FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION}"
)

# Public names are compatibility aliases.  Contract behavior below uses only
# the import-time literals above, so monkeypatching an exported convenience
# constant cannot silently redefine an already-versioned artifact schema.
EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1 = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1 = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
)
SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS = (
    _FROZEN_SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS
)
EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = (
    _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
)
_PARAMETER_SET_SCHEMA_ID_BY_VERSION = MappingProxyType(
    {
        _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION: (
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID
        ),
        _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1: (
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
        ),
    }
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID
)
EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE
)
EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID = (
    _FROZEN_EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID
)
FORCE_FIELD_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian/1.0.0"
)
_FORCE_FIELD_UNIT_SYSTEM_ITEMS = (
    ("unit_system_id", FORCE_FIELD_UNIT_SYSTEM_ID),
    ("coordinate_length", "angstrom"),
    ("bond_equilibrium_length", "angstrom"),
    ("angle_equilibrium_value", "radian"),
    ("energy", "kilojoule_per_mole"),
    ("bond_force_constant", "kilojoule_per_mole_per_angstrom_squared"),
    ("angle_force_constant", "kilojoule_per_mole_per_radian_squared"),
    ("numeric_encoding", "ieee754_binary64_big_endian_hex"),
)
_FROZEN_FORCE_FIELD_UNIT_SYSTEM_ITEMS = _FORCE_FIELD_UNIT_SYSTEM_ITEMS
_FORCE_FIELD_UNIT_SYSTEM = MappingProxyType(dict(_FORCE_FIELD_UNIT_SYSTEM_ITEMS))
PARAMETER_SET_DERIVATION_STATUSES = frozenset(
    {"declared_contract_fixture", "declared_fit_candidate_unverified"}
)
_FROZEN_PARAMETER_SET_DERIVATION_STATUSES = PARAMETER_SET_DERIVATION_STATUSES
PARAMETER_ASSIGNMENT_STATUSES = frozenset(
    {
        "invalid_system",
        "unsupported_system",
        "contract_fixture_mapped",
        "declared_fit_candidate_mapped_unverified",
    }
)
_FROZEN_PARAMETER_ASSIGNMENT_STATUSES = PARAMETER_ASSIGNMENT_STATUSES
PARAMETER_ASSIGNMENT_CONSTRAINT_CODES = (
    "upstream_inventory_valid",
    "upstream_inventory_available",
    "coordinate_unit_angstrom",
    "parameter_profile_matches",
    "assignment_policy_matches",
    "exact_bond_term_set_resolved",
    "exact_angle_term_set_resolved",
)
_FROZEN_PARAMETER_ASSIGNMENT_CONSTRAINT_CODES = (
    PARAMETER_ASSIGNMENT_CONSTRAINT_CODES
)

_MAX_PARAMETER_SET_BYTES = 1024 * 1024
_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,127}$")
_LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BINARY64_HEX_RE = re.compile(r"^[0-9a-f]{16}$")


class ForceFieldParameterContractError(ValueError):
    """Raised when a parameter or assignment contract is invalid."""


class ForceFieldParameterSerializationError(ForceFieldParameterContractError):
    """Raised when canonical parameter-set JSON cannot be decoded."""


def _require_identifier(name: str, value: Any) -> str:
    if type(value) is not str or _IDENTIFIER_RE.fullmatch(value) is None:
        raise ForceFieldParameterContractError(
            f"{name} must be a lowercase canonical identifier"
        )
    return value


def _require_sha256_or_none(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _LOWER_SHA256_RE.fullmatch(value) is None:
        raise ForceFieldParameterContractError(
            f"{name} must be a lowercase SHA-256 or None"
        )
    return value


def _require_semver(name: str, value: Any) -> str:
    if type(value) is not str:
        raise ForceFieldParameterContractError(f"{name} must be a string")
    try:
        SemanticVersion.parse(value)
    except ContractVersionError as exc:
        raise ForceFieldParameterContractError(f"invalid {name}: {exc}") from exc
    return value


def _require_finite_binary64(
    name: str,
    value: Any,
    *,
    positive: bool = False,
    angle: bool = False,
) -> float:
    if type(value) is not float:
        raise TypeError(f"{name} must be an exact binary64 float")
    if not math.isfinite(value):
        raise ForceFieldParameterContractError(f"{name} must be finite")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise ForceFieldParameterContractError(f"{name} cannot be negative zero")
    if positive and value <= 0.0:
        raise ForceFieldParameterContractError(f"{name} must be positive")
    if angle and not (0.0 < value < math.pi):
        raise ForceFieldParameterContractError(
            f"{name} must be strictly between zero and pi radians"
        )
    return value


def _binary64_hex(value: float) -> str:
    return struct.pack(">d", value).hex()


def _binary64_from_hex(name: str, value: Any) -> float:
    if type(value) is not str or _BINARY64_HEX_RE.fullmatch(value) is None:
        raise ForceFieldParameterSerializationError(
            f"{name} must be 16 lowercase binary64 hex digits"
        )
    return struct.unpack(">d", bytes.fromhex(value))[0]


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ForceFieldParameterSerializationError(
            f"canonical parameter JSON encoding failed: {exc}"
        ) from exc
    if len(payload) > _MAX_PARAMETER_SET_BYTES:
        raise ForceFieldParameterSerializationError(
            "parameter-set payload exceeds the fixed byte limit"
        )
    return payload


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


@dataclass(frozen=True, slots=True)
class HarmonicBondParameter:
    parameter_id: str
    equilibrium_length_angstrom: float
    force_constant_kj_mol_angstrom2: float

    def __post_init__(self) -> None:
        _require_identifier("parameter_id", self.parameter_id)
        _require_finite_binary64(
            "equilibrium_length_angstrom",
            self.equilibrium_length_angstrom,
            positive=True,
        )
        _require_finite_binary64(
            "force_constant_kj_mol_angstrom2",
            self.force_constant_kj_mol_angstrom2,
            positive=True,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "parameter_id": self.parameter_id,
            "equilibrium_length_ieee754_binary64_be": _binary64_hex(
                self.equilibrium_length_angstrom
            ),
            "force_constant_ieee754_binary64_be": _binary64_hex(
                self.force_constant_kj_mol_angstrom2
            ),
        }


@dataclass(frozen=True, slots=True)
class HarmonicAngleParameter:
    parameter_id: str
    equilibrium_angle_radian: float
    force_constant_kj_mol_radian2: float

    def __post_init__(self) -> None:
        _require_identifier("parameter_id", self.parameter_id)
        _require_finite_binary64(
            "equilibrium_angle_radian",
            self.equilibrium_angle_radian,
            angle=True,
        )
        _require_finite_binary64(
            "force_constant_kj_mol_radian2",
            self.force_constant_kj_mol_radian2,
            positive=True,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "parameter_id": self.parameter_id,
            "equilibrium_angle_ieee754_binary64_be": _binary64_hex(
                self.equilibrium_angle_radian
            ),
            "force_constant_ieee754_binary64_be": _binary64_hex(
                self.force_constant_kj_mol_radian2
            ),
        }


def _parameter_set_blockers(derivation_status: str) -> tuple[str, ...]:
    if (
        type(derivation_status) is not str
        or derivation_status not in _FROZEN_PARAMETER_SET_DERIVATION_STATUSES
    ):
        raise ForceFieldParameterContractError(
            "unknown parameter-set derivation status"
        )
    derivation_blocker = (
        "parameter_values_are_nonphysical_contract_fixture"
        if derivation_status == "declared_contract_fixture"
        else "declared_fit_candidate_evidence_unverified"
    )
    return (
        "parameter_artifact_digest_is_not_authentication",
        derivation_blocker,
        "parameter_license_not_reviewed",
        "scientific_validation_missing",
        "atom_typing_not_assessed",
        "partial_charge_parameters_not_assessed",
        "vdw_parameters_not_assessed",
        "short_range_electrostatics_not_assessed",
        "proper_torsion_parameters_not_assessed",
        "improper_parameters_not_assessed",
        "constraint_parameters_not_assessed",
        "implicit_solvation_parameters_not_assessed",
        "global_parameter_coverage_incomplete",
        "runtime_parameter_use_prohibited",
    )


@dataclass(frozen=True, slots=True)
class ExactMethaneBondAngleParameterSet:
    """Canonical scoped parameter artifact with no runtime authority."""

    parameter_set_id: str
    parameter_set_version: str
    derivation_status: str
    bond_parameter: HarmonicBondParameter
    angle_parameter: HarmonicAngleParameter
    dataset_manifest_sha256: str | None = None
    split_manifest_sha256: str | None = None
    fit_protocol_id: str | None = None
    fit_receipt_sha256: str | None = None
    artifact_schema_version: str = field(
        default=(
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
        ),
        kw_only=True,
    )
    functional_form_id: str | None = field(
        default=None,
        kw_only=True,
    )
    _unit_system_items: tuple[tuple[str, str], ...] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_unit_system_items",
            _FROZEN_FORCE_FIELD_UNIT_SYSTEM_ITEMS,
        )
        _require_identifier("parameter_set_id", self.parameter_set_id)
        _require_semver("parameter_set_version", self.parameter_set_version)
        if type(self.artifact_schema_version) is not str:
            raise TypeError("artifact_schema_version must be a string")
        if self.artifact_schema_version not in (
            _FROZEN_SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS
        ):
            raise ForceFieldParameterContractError(
                "unsupported exact-methane parameter artifact schema version"
            )
        if self.artifact_schema_version == (
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
        ):
            if self.functional_form_id is not None:
                raise ForceFieldParameterContractError(
                    "parameter artifact schema 1.0 requires functional_form_id "
                    "to remain None"
                )
        elif (
            type(self.functional_form_id) is not str
            or self.functional_form_id
            != _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
        ):
            raise ForceFieldParameterContractError(
                "parameter artifact schema 1.1 requires the fixed exact-methane "
                "harmonic functional form"
            )
        if (
            type(self.derivation_status) is not str
            or self.derivation_status
            not in _FROZEN_PARAMETER_SET_DERIVATION_STATUSES
        ):
            raise ForceFieldParameterContractError(
                "unknown parameter-set derivation status"
            )
        if type(self.bond_parameter) is not HarmonicBondParameter:
            raise TypeError("bond_parameter must be a HarmonicBondParameter")
        if type(self.angle_parameter) is not HarmonicAngleParameter:
            raise TypeError("angle_parameter must be a HarmonicAngleParameter")
        for name in (
            "dataset_manifest_sha256",
            "split_manifest_sha256",
            "fit_receipt_sha256",
        ):
            _require_sha256_or_none(name, getattr(self, name))
        if self.fit_protocol_id is not None:
            _require_identifier("fit_protocol_id", self.fit_protocol_id)
        evidence = (
            self.dataset_manifest_sha256,
            self.split_manifest_sha256,
            self.fit_protocol_id,
            self.fit_receipt_sha256,
        )
        if self.derivation_status == "declared_contract_fixture":
            if any(value is not None for value in evidence):
                raise ForceFieldParameterContractError(
                    "contract fixtures cannot claim fit evidence"
                )
        elif any(value is None for value in evidence):
            raise ForceFieldParameterContractError(
                "declared fit candidates require dataset, split, protocol, "
                "and receipt references"
            )

    def _validated_copy(self) -> "ExactMethaneBondAngleParameterSet":
        if (
            type(self._unit_system_items) is not tuple
            or not all(
                type(item) is tuple
                and len(item) == 2
                and type(item[0]) is str
                and type(item[1]) is str
                for item in self._unit_system_items
            )
            or self._unit_system_items != _FROZEN_FORCE_FIELD_UNIT_SYSTEM_ITEMS
        ):
            raise ForceFieldParameterContractError(
                "parameter unit-system snapshot does not match the fixed contract"
            )
        if type(self.bond_parameter) is not HarmonicBondParameter:
            raise TypeError("bond_parameter must be a HarmonicBondParameter")
        if type(self.angle_parameter) is not HarmonicAngleParameter:
            raise TypeError("angle_parameter must be a HarmonicAngleParameter")
        bond = self.bond_parameter
        angle = self.angle_parameter
        return ExactMethaneBondAngleParameterSet(
            parameter_set_id=self.parameter_set_id,
            parameter_set_version=self.parameter_set_version,
            derivation_status=self.derivation_status,
            bond_parameter=HarmonicBondParameter(
                parameter_id=bond.parameter_id,
                equilibrium_length_angstrom=bond.equilibrium_length_angstrom,
                force_constant_kj_mol_angstrom2=(
                    bond.force_constant_kj_mol_angstrom2
                ),
            ),
            angle_parameter=HarmonicAngleParameter(
                parameter_id=angle.parameter_id,
                equilibrium_angle_radian=angle.equilibrium_angle_radian,
                force_constant_kj_mol_radian2=(
                    angle.force_constant_kj_mol_radian2
                ),
            ),
            dataset_manifest_sha256=self.dataset_manifest_sha256,
            split_manifest_sha256=self.split_manifest_sha256,
            fit_protocol_id=self.fit_protocol_id,
            fit_receipt_sha256=self.fit_receipt_sha256,
            artifact_schema_version=self.artifact_schema_version,
            functional_form_id=self.functional_form_id,
        )

    @property
    def schema_id(self) -> str:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        return _PARAMETER_SET_SCHEMA_ID_BY_VERSION[
            validated.artifact_schema_version
        ]

    @property
    def applicability_profile_id(self) -> str:
        return _FROZEN_EXACT_METHANE_BOND_ANGLE_PROFILE_ID

    @property
    def parameter_scope(self) -> str:
        return _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE

    @property
    def assignment_policy_id(self) -> str:
        return _FROZEN_EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID

    @property
    def artifact_purpose(self) -> str:
        _parameter_set_blockers(self.derivation_status)
        return (
            "contract_fixture_only"
            if self.derivation_status == "declared_contract_fixture"
            else "declared_fit_candidate_unverified"
        )

    @property
    def fit_execution_status(self) -> str:
        _parameter_set_blockers(self.derivation_status)
        return (
            "not_run"
            if self.derivation_status == "declared_contract_fixture"
            else "unverified"
        )

    @property
    def fit_evidence_review_status(self) -> str:
        _parameter_set_blockers(self.derivation_status)
        return (
            "not_applicable"
            if self.derivation_status == "declared_contract_fixture"
            else "unreviewed"
        )

    @property
    def scientific_validation_status(self) -> str:
        return "missing"

    @property
    def runtime_authorization_status(self) -> str:
        return "prohibited"

    @property
    def parameter_artifact_authentication_status(self) -> str:
        return "not_authenticated"

    @property
    def license_review_status(self) -> str:
        return "not_reviewed"

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return False

    @property
    def runtime_eligible(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        return _parameter_set_blockers(self.derivation_status)

    def _payload_document_unchecked(self) -> dict[str, Any]:
        payload = {
            "applicability_profile_id": self.applicability_profile_id,
            "parameter_scope": self.parameter_scope,
            "assignment_policy_id": self.assignment_policy_id,
            "unit_system": dict(self._unit_system_items),
            "bond_parameter": HarmonicBondParameter.to_dict(self.bond_parameter),
            "angle_parameter": HarmonicAngleParameter.to_dict(
                self.angle_parameter
            ),
        }
        if self.artifact_schema_version == (
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
        ):
            payload["functional_form_id"] = self.functional_form_id
        return payload

    def _payload_document(self) -> dict[str, Any]:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        return ExactMethaneBondAngleParameterSet._payload_document_unchecked(
            validated
        )

    @property
    def parameter_payload_sha256(self) -> str:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        return _sha256_document(
            ExactMethaneBondAngleParameterSet._payload_document_unchecked(
                validated
            )
        )

    def _core_dict_unchecked(self) -> dict[str, Any]:
        payload = {
            "schema_id": _PARAMETER_SET_SCHEMA_ID_BY_VERSION[
                self.artifact_schema_version
            ],
            "schema_version": self.artifact_schema_version,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "applicability_profile_id": self.applicability_profile_id,
            "parameter_scope": self.parameter_scope,
            "assignment_policy_id": self.assignment_policy_id,
            "unit_system": dict(self._unit_system_items),
            "bond_parameter": HarmonicBondParameter.to_dict(self.bond_parameter),
            "angle_parameter": HarmonicAngleParameter.to_dict(
                self.angle_parameter
            ),
            "parameter_payload_sha256": _sha256_document(
                ExactMethaneBondAngleParameterSet._payload_document_unchecked(
                    self
                )
            ),
            "parameter_artifact_status": "present",
            "derivation_status": self.derivation_status,
            "artifact_purpose": self.artifact_purpose,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "split_manifest_sha256": self.split_manifest_sha256,
            "fit_protocol_id": self.fit_protocol_id,
            "fit_receipt_sha256": self.fit_receipt_sha256,
            "fit_execution_status": self.fit_execution_status,
            "fit_evidence_review_status": self.fit_evidence_review_status,
            "scientific_validation_status": self.scientific_validation_status,
            "runtime_authorization_status": self.runtime_authorization_status,
            "parameter_artifact_authentication_status": (
                self.parameter_artifact_authentication_status
            ),
            "license_review_status": self.license_review_status,
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "global_parameter_coverage_complete": (
                self.global_parameter_coverage_complete
            ),
            "runtime_eligible": self.runtime_eligible,
            "execution_authorized": self.execution_authorized,
            "claim_safe": self.claim_safe,
            "blockers": list(_parameter_set_blockers(self.derivation_status)),
        }
        if self.artifact_schema_version == (
            _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
        ):
            payload["functional_form_id"] = self.functional_form_id
        return payload

    def _core_dict(self) -> dict[str, Any]:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        return ExactMethaneBondAngleParameterSet._core_dict_unchecked(validated)

    @property
    def parameter_set_sha256(self) -> str:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        return _sha256_document(
            ExactMethaneBondAngleParameterSet._core_dict_unchecked(validated)
        )

    def to_dict(self) -> dict[str, Any]:
        validated = ExactMethaneBondAngleParameterSet._validated_copy(self)
        payload = ExactMethaneBondAngleParameterSet._core_dict_unchecked(
            validated
        )
        payload["parameter_set_sha256"] = _sha256_document(payload)
        return payload


@dataclass(frozen=True, order=True, slots=True)
class BondParameterAssignment:
    identity: CanonicalBondIdentity
    parameter_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalBondIdentity:
            raise TypeError("identity must be a CanonicalBondIdentity")
        # Reconstructing rejects post-construction mutation of the otherwise
        # non-slotted upstream identity and validates exact integer fields.
        CanonicalBondIdentity(self.identity.atom_i, self.identity.atom_j)
        _require_identifier("parameter_id", self.parameter_id)

    def _validated_copy(self) -> "BondParameterAssignment":
        if type(self.identity) is not CanonicalBondIdentity:
            raise TypeError("identity must be a CanonicalBondIdentity")
        identity = self.identity
        return BondParameterAssignment(
            CanonicalBondIdentity(identity.atom_i, identity.atom_j),
            self.parameter_id,
        )

    def _to_dict_unchecked(self) -> dict[str, Any]:
        return {
            **CanonicalBondIdentity.to_dict(self.identity),
            "parameter_id": self.parameter_id,
        }

    def to_dict(self) -> dict[str, Any]:
        validated = BondParameterAssignment._validated_copy(self)
        return BondParameterAssignment._to_dict_unchecked(validated)


@dataclass(frozen=True, order=True, slots=True)
class AngleParameterAssignment:
    identity: CanonicalAngleIdentity
    parameter_id: str

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalAngleIdentity:
            raise TypeError("identity must be a CanonicalAngleIdentity")
        CanonicalAngleIdentity(
            self.identity.outer_atom_i,
            self.identity.center_atom,
            self.identity.outer_atom_k,
        )
        _require_identifier("parameter_id", self.parameter_id)

    def _validated_copy(self) -> "AngleParameterAssignment":
        if type(self.identity) is not CanonicalAngleIdentity:
            raise TypeError("identity must be a CanonicalAngleIdentity")
        identity = self.identity
        return AngleParameterAssignment(
            CanonicalAngleIdentity(
                identity.outer_atom_i,
                identity.center_atom,
                identity.outer_atom_k,
            ),
            self.parameter_id,
        )

    def _to_dict_unchecked(self) -> dict[str, Any]:
        return {
            **CanonicalAngleIdentity.to_dict(self.identity),
            "parameter_id": self.parameter_id,
        }

    def to_dict(self) -> dict[str, Any]:
        validated = AngleParameterAssignment._validated_copy(self)
        return AngleParameterAssignment._to_dict_unchecked(validated)


def _assignment_status(
    inventory: ExactMethaneBondAngleInventoryReport,
    parameter_set: ExactMethaneBondAngleParameterSet,
    constraints: tuple[tuple[str, bool], ...],
) -> str:
    if inventory.inventory_status == "invalid":
        return "invalid_system"
    if any(not passed for _, passed in constraints):
        return "unsupported_system"
    return (
        "contract_fixture_mapped"
        if parameter_set.derivation_status == "declared_contract_fixture"
        else "declared_fit_candidate_mapped_unverified"
    )


def _assignment_blockers(
    status: str,
    failed_constraint_codes: tuple[str, ...],
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if status == "invalid_system":
        blockers.append("parameter_assignment_system_invalid")
    elif status == "unsupported_system":
        blockers.append("exact_methane_parameter_assignment_unsupported")
    blockers.extend(
        f"parameter_assignment_constraint_failed_{code}"
        for code in failed_constraint_codes
    )
    if status in {"invalid_system", "unsupported_system"}:
        blockers.append("bond_angle_parameters_not_assigned")
    blockers.extend(
        (
            "molecular_source_digest_is_not_authentication",
            *_parameter_set_blockers(parameter_set.derivation_status),
            "preparation_not_ready",
            "energy_evaluation_not_authorized",
            "force_evaluation_not_authorized",
            "minimization_not_authorized",
            "simulation_not_authorized",
            "claim_not_authorized",
        )
    )
    return tuple(blockers)


@dataclass(frozen=True, init=False, slots=True)
class ExactMethaneBondAngleParameterAssignmentReport:
    """Fresh, exact-set-equality assignment with no scientific promotion."""

    inventory_report: ExactMethaneBondAngleInventoryReport
    parameter_set: ExactMethaneBondAngleParameterSet
    constraint_results: tuple[tuple[str, bool], ...]
    assignment_status: str
    bond_assignments: tuple[BondParameterAssignment, ...]
    angle_assignments: tuple[AngleParameterAssignment, ...]
    _inventory_report_sha256_snapshot: str = field(repr=False, compare=False)
    _parameter_set_sha256_snapshot: str = field(repr=False, compare=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
            raise TypeError(
                "parameter_set must be an ExactMethaneBondAngleParameterSet"
            )
        parameter_set = ExactMethaneBondAngleParameterSet._validated_copy(
            parameter_set
        )
        inventory = analyze_exact_methane_bond_angle_inventory(system)
        inventory_available = inventory.inventory_status == "available"
        if inventory_available:
            bond_assignments = tuple(
                BondParameterAssignment(
                    identity,
                    parameter_set.bond_parameter.parameter_id,
                )
                for identity in inventory.bond_identities
            )
            angle_assignments = tuple(
                AngleParameterAssignment(
                    identity,
                    parameter_set.angle_parameter.parameter_id,
                )
                for identity in inventory.angle_identities
            )
        else:
            bond_assignments = ()
            angle_assignments = ()
        constraints = (
            (
                "upstream_inventory_valid",
                inventory.inventory_status != "invalid",
            ),
            ("upstream_inventory_available", inventory_available),
            ("coordinate_unit_angstrom", system.coordinate_unit == "angstrom"),
            (
                "parameter_profile_matches",
                parameter_set.applicability_profile_id
                == _FROZEN_EXACT_METHANE_BOND_ANGLE_PROFILE_ID,
            ),
            (
                "assignment_policy_matches",
                parameter_set.assignment_policy_id
                == _FROZEN_EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID,
            ),
            (
                "exact_bond_term_set_resolved",
                bool(
                    inventory_available
                    and tuple(item.identity for item in bond_assignments)
                    == inventory.bond_identities
                    and len(set(bond_assignments)) == len(bond_assignments)
                ),
            ),
            (
                "exact_angle_term_set_resolved",
                bool(
                    inventory_available
                    and tuple(item.identity for item in angle_assignments)
                    == inventory.angle_identities
                    and len(set(angle_assignments)) == len(angle_assignments)
                ),
            ),
        )
        status = _assignment_status(inventory, parameter_set, constraints)
        if status in {"invalid_system", "unsupported_system"}:
            bond_assignments = ()
            angle_assignments = ()
        object.__setattr__(self, "inventory_report", inventory)
        object.__setattr__(self, "parameter_set", parameter_set)
        object.__setattr__(self, "constraint_results", constraints)
        object.__setattr__(self, "assignment_status", status)
        object.__setattr__(self, "bond_assignments", bond_assignments)
        object.__setattr__(self, "angle_assignments", angle_assignments)
        object.__setattr__(
            self,
            "_inventory_report_sha256_snapshot",
            _sha256_document(
                ExactMethaneBondAngleInventoryReport._core_dict(inventory)
            ),
        )
        object.__setattr__(
            self,
            "_parameter_set_sha256_snapshot",
            parameter_set.parameter_set_sha256,
        )
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)

    def _validate(self) -> None:
        if type(self.inventory_report) is not ExactMethaneBondAngleInventoryReport:
            raise TypeError("inventory_report must be a factory inventory")
        ExactMethaneBondAngleInventoryReport._validate(self.inventory_report)
        if type(self.inventory_report.inventory_status) is not str:
            raise TypeError("inventory status must be an exact string")
        if type(self.parameter_set) is not ExactMethaneBondAngleParameterSet:
            raise TypeError("parameter_set must be an exact parameter set")
        parameter_set = ExactMethaneBondAngleParameterSet._validated_copy(
            self.parameter_set
        )
        if type(self._inventory_report_sha256_snapshot) is not str:
            raise TypeError("inventory snapshot digest must be an exact string")
        _require_sha256_or_none(
            "inventory snapshot digest",
            self._inventory_report_sha256_snapshot,
        )
        if type(self._parameter_set_sha256_snapshot) is not str:
            raise TypeError("parameter snapshot digest must be an exact string")
        _require_sha256_or_none(
            "parameter snapshot digest",
            self._parameter_set_sha256_snapshot,
        )
        if self._inventory_report_sha256_snapshot != _sha256_document(
            ExactMethaneBondAngleInventoryReport._core_dict(
                self.inventory_report
            )
        ):
            raise ForceFieldParameterContractError(
                "assignment inventory changed after construction"
            )
        if self._parameter_set_sha256_snapshot != (
            parameter_set.parameter_set_sha256
        ):
            raise ForceFieldParameterContractError(
                "assignment parameter set changed after construction"
            )
        if type(self.constraint_results) is not tuple or not all(
            type(item) is tuple
            and len(item) == 2
            and type(item[0]) is str
            and type(item[1]) is bool
            for item in self.constraint_results
        ):
            raise TypeError("assignment constraints must be string/boolean pairs")
        if tuple(code for code, _ in self.constraint_results) != (
            _FROZEN_PARAMETER_ASSIGNMENT_CONSTRAINT_CODES
        ):
            raise ForceFieldParameterContractError(
                "assignment constraints must match the fixed schema"
            )
        if type(self.assignment_status) is not str:
            raise TypeError("assignment status must be an exact string")
        expected = _assignment_status(
            self.inventory_report,
            parameter_set,
            self.constraint_results,
        )
        if self.assignment_status != expected:
            raise ForceFieldParameterContractError(
                "assignment status must match the derived constraints"
            )
        if self.assignment_status not in _FROZEN_PARAMETER_ASSIGNMENT_STATUSES:
            raise ForceFieldParameterContractError("unknown assignment status")
        if type(self.bond_assignments) is not tuple or not all(
            type(item) is BondParameterAssignment
            for item in self.bond_assignments
        ):
            raise TypeError("bond assignments must be an exact tuple")
        if type(self.angle_assignments) is not tuple or not all(
            type(item) is AngleParameterAssignment
            for item in self.angle_assignments
        ):
            raise TypeError("angle assignments must be an exact tuple")
        bond_assignments = tuple(
            BondParameterAssignment._validated_copy(item)
            for item in self.bond_assignments
        )
        angle_assignments = tuple(
            AngleParameterAssignment._validated_copy(item)
            for item in self.angle_assignments
        )
        inventory_bonds = tuple(
            CanonicalBondIdentity(identity.atom_i, identity.atom_j)
            for identity in self.inventory_report.bond_identities
        )
        inventory_angles = tuple(
            CanonicalAngleIdentity(
                identity.outer_atom_i,
                identity.center_atom,
                identity.outer_atom_k,
            )
            for identity in self.inventory_report.angle_identities
        )
        mapped = self.assignment_status in {
            "contract_fixture_mapped",
            "declared_fit_candidate_mapped_unverified",
        }
        if mapped:
            if tuple(item.identity for item in bond_assignments) != (
                inventory_bonds
            ):
                raise ForceFieldParameterContractError(
                    "bond assignment set must exactly equal the inventory"
                )
            if tuple(item.identity for item in angle_assignments) != (
                inventory_angles
            ):
                raise ForceFieldParameterContractError(
                    "angle assignment set must exactly equal the inventory"
                )
            if any(
                item.parameter_id
                != parameter_set.bond_parameter.parameter_id
                for item in bond_assignments
            ) or any(
                item.parameter_id
                != parameter_set.angle_parameter.parameter_id
                for item in angle_assignments
            ):
                raise ForceFieldParameterContractError(
                    "assignments must resolve to the bound parameter set"
                )
        elif bond_assignments or angle_assignments:
            raise ForceFieldParameterContractError(
                "unavailable assignments cannot expose resolved terms"
            )

    @property
    def failed_constraint_codes(self) -> tuple[str, ...]:
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)
        return tuple(
            code for code, passed in self.constraint_results if not passed
        )

    @property
    def bond_angle_assignment_complete(self) -> bool:
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)
        return self.assignment_status in {
            "contract_fixture_mapped",
            "declared_fit_candidate_mapped_unverified",
        }

    @property
    def parameterability_assessed(self) -> bool:
        return False

    @property
    def parameterizable(self) -> bool:
        return False

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return False

    @property
    def preparation_ready(self) -> bool:
        return False

    @property
    def physics_supported(self) -> bool:
        return False

    @property
    def runtime_eligible(self) -> bool:
        return False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def energy_evaluation_authorized(self) -> bool:
        return False

    @property
    def force_evaluation_authorized(self) -> bool:
        return False

    @property
    def minimization_authorized(self) -> bool:
        return False

    @property
    def simulation_ready(self) -> bool:
        return False

    @property
    def claim_safe(self) -> bool:
        return False

    @property
    def blockers(self) -> tuple[str, ...]:
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)
        return _assignment_blockers(
            self.assignment_status,
            self.failed_constraint_codes,
            self.parameter_set,
        )

    def _assignment_document(self) -> dict[str, Any] | None:
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)
        if not self.bond_angle_assignment_complete:
            return None
        return {
            "canonical_topology_schema_id": (
                self.inventory_report.canonical_topology_schema_id
            ),
            "canonical_topology_sha256": (
                self.inventory_report.canonical_topology_sha256
            ),
            "inventory_schema_id": (
                _FROZEN_EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID
            ),
            "inventory_report_sha256": self.inventory_report.report_sha256,
            "parameter_set_schema_id": self.parameter_set.schema_id,
            "parameter_set_sha256": self.parameter_set.parameter_set_sha256,
            "parameter_payload_sha256": (
                self.parameter_set.parameter_payload_sha256
            ),
            "assignment_policy_id": self.parameter_set.assignment_policy_id,
            "resolved_bond_parameter": HarmonicBondParameter.to_dict(
                self.parameter_set.bond_parameter
            ),
            "resolved_angle_parameter": (
                HarmonicAngleParameter.to_dict(
                    self.parameter_set.angle_parameter
                )
            ),
            "bond_assignments": [
                BondParameterAssignment.to_dict(item)
                for item in self.bond_assignments
            ],
            "angle_assignments": [
                AngleParameterAssignment.to_dict(item)
                for item in self.angle_assignments
            ],
        }

    @property
    def parameter_assignment_sha256(self) -> str | None:
        document = (
            ExactMethaneBondAngleParameterAssignmentReport._assignment_document(
                self
            )
        )
        return None if document is None else _sha256_document(document)

    def _core_dict(self) -> dict[str, Any]:
        ExactMethaneBondAngleParameterAssignmentReport._validate(self)
        return {
            "schema_id": (
                _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID
            ),
            "schema_version": (
                _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION
            ),
            "parameter_scope": (
                _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE
            ),
            "assignment_policy_id": self.parameter_set.assignment_policy_id,
            "system_schema_id": self.inventory_report.system_schema_id,
            "canonical_topology_schema_id": (
                self.inventory_report.canonical_topology_schema_id
            ),
            "canonical_topology_sha256": (
                self.inventory_report.canonical_topology_sha256
            ),
            "molecular_source_sha256": self.inventory_report.source_sha256,
            "molecular_source_authentication_status": (
                self.inventory_report.source_authentication_status
            ),
            "inventory_schema_id": (
                _FROZEN_EXACT_METHANE_BOND_ANGLE_INVENTORY_SCHEMA_ID
            ),
            "inventory_report_sha256": self.inventory_report.report_sha256,
            "parameter_set_schema_id": self.parameter_set.schema_id,
            "parameter_set_id": self.parameter_set.parameter_set_id,
            "parameter_set_version": self.parameter_set.parameter_set_version,
            "parameter_set_sha256": self.parameter_set.parameter_set_sha256,
            "parameter_payload_sha256": (
                self.parameter_set.parameter_payload_sha256
            ),
            "parameter_derivation_status": (
                self.parameter_set.derivation_status
            ),
            "parameter_artifact_purpose": self.parameter_set.artifact_purpose,
            "parameter_fit_execution_status": (
                self.parameter_set.fit_execution_status
            ),
            "parameter_fit_evidence_review_status": (
                self.parameter_set.fit_evidence_review_status
            ),
            "parameter_scientific_validation_status": (
                self.parameter_set.scientific_validation_status
            ),
            "parameter_runtime_authorization_status": (
                self.parameter_set.runtime_authorization_status
            ),
            "parameter_artifact_authentication_status": (
                self.parameter_set.parameter_artifact_authentication_status
            ),
            "parameter_license_review_status": (
                self.parameter_set.license_review_status
            ),
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in self.constraint_results
            ],
            "failed_constraint_codes": list(self.failed_constraint_codes),
            "assignment_status": self.assignment_status,
            "bond_angle_assignment_complete": (
                self.bond_angle_assignment_complete
            ),
            "bond_assignments": [
                BondParameterAssignment.to_dict(item)
                for item in self.bond_assignments
            ],
            "angle_assignments": [
                AngleParameterAssignment.to_dict(item)
                for item in self.angle_assignments
            ],
            "resolved_bond_parameter": (
                HarmonicBondParameter.to_dict(
                    self.parameter_set.bond_parameter
                )
                if self.bond_angle_assignment_complete
                else None
            ),
            "resolved_angle_parameter": (
                HarmonicAngleParameter.to_dict(
                    self.parameter_set.angle_parameter
                )
                if self.bond_angle_assignment_complete
                else None
            ),
            "parameter_assignment_sha256": self.parameter_assignment_sha256,
            "proper_torsion_parameter_status": "not_assessed",
            "improper_parameter_status": "not_assessed",
            "constraint_parameter_status": "not_assessed",
            "atom_typing_status": "not_assessed",
            "partial_charge_parameter_status": "not_assessed",
            "vdw_parameter_status": "not_assessed",
            "short_range_electrostatics_status": "not_assessed",
            "implicit_solvation_parameter_status": "not_assessed",
            "parameterability_assessed": self.parameterability_assessed,
            "parameterizable": self.parameterizable,
            "global_parameter_coverage_complete": (
                self.global_parameter_coverage_complete
            ),
            "preparation_ready": self.preparation_ready,
            "physics_supported": self.physics_supported,
            "runtime_eligible": self.runtime_eligible,
            "execution_authorized": self.execution_authorized,
            "energy_evaluation_authorized": self.energy_evaluation_authorized,
            "force_evaluation_authorized": self.force_evaluation_authorized,
            "minimization_authorized": self.minimization_authorized,
            "simulation_ready": self.simulation_ready,
            "claim_safe": self.claim_safe,
            "blockers": list(self.blockers),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(
            ExactMethaneBondAngleParameterAssignmentReport._core_dict(self)
        )

    def to_dict(self) -> dict[str, Any]:
        payload = ExactMethaneBondAngleParameterAssignmentReport._core_dict(
            self
        )
        payload["report_sha256"] = self.report_sha256
        return payload

    def matches(
        self,
        system: AllAtomSystem,
        parameter_set: ExactMethaneBondAngleParameterSet,
    ) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an AllAtomSystem")
        if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
            raise TypeError(
                "parameter_set must be an ExactMethaneBondAngleParameterSet"
            )
        return ExactMethaneBondAngleParameterAssignmentReport.to_dict(
            self
        ) == (
            ExactMethaneBondAngleParameterAssignmentReport.to_dict(
                analyze_exact_methane_bond_angle_parameter_assignment(
                system,
                parameter_set,
                )
            )
        )


_PARAMETER_SET_KEYS_1_0 = frozenset(
    {
        "schema_id",
        "schema_version",
        "parameter_set_id",
        "parameter_set_version",
        "applicability_profile_id",
        "parameter_scope",
        "assignment_policy_id",
        "unit_system",
        "bond_parameter",
        "angle_parameter",
        "parameter_payload_sha256",
        "parameter_artifact_status",
        "derivation_status",
        "artifact_purpose",
        "dataset_manifest_sha256",
        "split_manifest_sha256",
        "fit_protocol_id",
        "fit_receipt_sha256",
        "fit_execution_status",
        "fit_evidence_review_status",
        "scientific_validation_status",
        "runtime_authorization_status",
        "parameter_artifact_authentication_status",
        "license_review_status",
        "parameterability_assessed",
        "parameterizable",
        "global_parameter_coverage_complete",
        "runtime_eligible",
        "execution_authorized",
        "claim_safe",
        "blockers",
        "parameter_set_sha256",
    }
)
_PARAMETER_SET_KEYS_1_1 = frozenset(
    {*_PARAMETER_SET_KEYS_1_0, "functional_form_id"}
)
_BOND_PARAMETER_KEYS = frozenset(
    {
        "parameter_id",
        "equilibrium_length_ieee754_binary64_be",
        "force_constant_ieee754_binary64_be",
    }
)
_ANGLE_PARAMETER_KEYS = frozenset(
    {
        "parameter_id",
        "equilibrium_angle_ieee754_binary64_be",
        "force_constant_ieee754_binary64_be",
    }
)


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    location: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForceFieldParameterSerializationError(
            f"{location} must be a JSON object"
        )
    observed = set(value)
    if observed != expected:
        raise ForceFieldParameterSerializationError(
            f"{location} keys mismatch: missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForceFieldParameterSerializationError(
                f"duplicate JSON object key {key!r}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ForceFieldParameterSerializationError(
        f"non-standard JSON constant {value!r} is not allowed"
    )


def _parameter_set_keys_for_schema(document: Any) -> frozenset[str]:
    if type(document) is not dict:
        raise ForceFieldParameterSerializationError(
            "parameter_set must be a JSON object"
        )
    schema_id = document.get("schema_id")
    schema_version = document.get("schema_version")
    if type(schema_id) is not str or type(schema_version) is not str:
        raise ForceFieldParameterSerializationError(
            "parameter-set schema_id and schema_version must be strings"
        )
    expected_schema_id = _PARAMETER_SET_SCHEMA_ID_BY_VERSION.get(
        schema_version
    )
    if expected_schema_id is None:
        raise ForceFieldParameterSerializationError(
            "unsupported exact-methane parameter-set schema version"
        )
    if schema_id != expected_schema_id:
        raise ForceFieldParameterSerializationError(
            "parameter-set schema_id and schema_version mismatch"
        )
    if schema_version == (
        _FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
    ):
        return _PARAMETER_SET_KEYS_1_0
    return _PARAMETER_SET_KEYS_1_1


def serialize_exact_methane_bond_angle_parameter_set(
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> bytes:
    if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
        raise TypeError(
            "parameter_set must be an ExactMethaneBondAngleParameterSet"
        )
    return _canonical_json_bytes(
        ExactMethaneBondAngleParameterSet.to_dict(parameter_set)
    )


def deserialize_exact_methane_bond_angle_parameter_set(
    data: bytes,
) -> ExactMethaneBondAngleParameterSet:
    if type(data) is not bytes:
        raise TypeError("parameter-set payload must be bytes")
    if len(data) > _MAX_PARAMETER_SET_BYTES:
        raise ForceFieldParameterSerializationError(
            "parameter-set payload exceeds the fixed byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ForceFieldParameterSerializationError(
            "parameter-set payload must be canonical ASCII JSON"
        ) from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except ForceFieldParameterSerializationError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ForceFieldParameterSerializationError(
            f"invalid parameter-set JSON: {exc}"
        ) from exc
    root = _require_exact_keys(
        document,
        _parameter_set_keys_for_schema(document),
        "parameter_set",
    )
    bond = _require_exact_keys(
        root["bond_parameter"],
        _BOND_PARAMETER_KEYS,
        "bond_parameter",
    )
    angle = _require_exact_keys(
        root["angle_parameter"],
        _ANGLE_PARAMETER_KEYS,
        "angle_parameter",
    )
    try:
        result = ExactMethaneBondAngleParameterSet(
            parameter_set_id=root["parameter_set_id"],
            parameter_set_version=root["parameter_set_version"],
            derivation_status=root["derivation_status"],
            bond_parameter=HarmonicBondParameter(
                parameter_id=bond["parameter_id"],
                equilibrium_length_angstrom=_binary64_from_hex(
                    "bond_parameter.equilibrium_length",
                    bond["equilibrium_length_ieee754_binary64_be"],
                ),
                force_constant_kj_mol_angstrom2=_binary64_from_hex(
                    "bond_parameter.force_constant",
                    bond["force_constant_ieee754_binary64_be"],
                ),
            ),
            angle_parameter=HarmonicAngleParameter(
                parameter_id=angle["parameter_id"],
                equilibrium_angle_radian=_binary64_from_hex(
                    "angle_parameter.equilibrium_angle",
                    angle["equilibrium_angle_ieee754_binary64_be"],
                ),
                force_constant_kj_mol_radian2=_binary64_from_hex(
                    "angle_parameter.force_constant",
                    angle["force_constant_ieee754_binary64_be"],
                ),
            ),
            dataset_manifest_sha256=root["dataset_manifest_sha256"],
            split_manifest_sha256=root["split_manifest_sha256"],
            fit_protocol_id=root["fit_protocol_id"],
            fit_receipt_sha256=root["fit_receipt_sha256"],
            artifact_schema_version=root["schema_version"],
            functional_form_id=root.get("functional_form_id"),
        )
    except ForceFieldParameterContractError:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise ForceFieldParameterSerializationError(
            f"invalid parameter-set document: {exc}"
        ) from exc
    if result.to_dict() != root:
        raise ForceFieldParameterSerializationError(
            "parameter-set document contains stale or forged derived fields"
        )
    if serialize_exact_methane_bond_angle_parameter_set(result) != data:
        raise ForceFieldParameterSerializationError(
            "parameter-set payload is not byte-canonical ASCII JSON"
        )
    return result


def analyze_exact_methane_bond_angle_parameter_assignment(
    system: AllAtomSystem,
    parameter_set: ExactMethaneBondAngleParameterSet,
) -> ExactMethaneBondAngleParameterAssignmentReport:
    """Map exact methane bond/angle identities without authorizing physics."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an AllAtomSystem")
    if type(parameter_set) is not ExactMethaneBondAngleParameterSet:
        raise TypeError(
            "parameter_set must be an ExactMethaneBondAngleParameterSet"
        )
    return ExactMethaneBondAngleParameterAssignmentReport(system, parameter_set)


__all__ = [
    "EXACT_METHANE_BOND_ANGLE_ASSIGNMENT_POLICY_ID",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_ID",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_ASSIGNMENT_SCHEMA_VERSION",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_SCOPE",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION",
    "EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1",
    "EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID",
    "FORCE_FIELD_UNIT_SYSTEM_ID",
    "SUPPORTED_EXACT_METHANE_PARAMETER_SET_SCHEMA_VERSIONS",
    "AngleParameterAssignment",
    "BondParameterAssignment",
    "ExactMethaneBondAngleParameterAssignmentReport",
    "ExactMethaneBondAngleParameterSet",
    "ForceFieldParameterContractError",
    "ForceFieldParameterSerializationError",
    "HarmonicAngleParameter",
    "HarmonicBondParameter",
    "analyze_exact_methane_bond_angle_parameter_assignment",
    "deserialize_exact_methane_bond_angle_parameter_set",
    "serialize_exact_methane_bond_angle_parameter_set",
]
