"""Strict nonphysical C1-C4 linear-alkane parameter contract.

The schema in this module fixes parameter identities, units, functional
forms, charge bookkeeping, Lennard-Jones combination semantics, and 1-4
scales for the bounded topology domain.  It is deliberately not a force-field
runtime.  No scientific values are shipped here, and every parameterability,
physics, execution, and claim gate remains closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import struct
from typing import Any, Mapping

from .term_inventory import (
    CanonicalAngleEnvironmentMatchKey,
    CanonicalBondEnvironmentMatchKey,
    CanonicalProperEnvironmentMatchKey,
)


_FROZEN_PROTOCOL_SCHEMA_VERSION = "1.0.0"
_FROZEN_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_protocol/"
    f"{_FROZEN_PROTOCOL_SCHEMA_VERSION}"
)
_FROZEN_PARAMETER_SET_SCHEMA_VERSION = "1.0.0"
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/"
    f"{_FROZEN_PARAMETER_SET_SCHEMA_VERSION}"
)
_FROZEN_PARAMETER_SCOPE = (
    "bounded_c1_c4_full_parameter_contract_fixture_only"
)
_FROZEN_PARAMETER_DOMAIN_ID = (
    "source_explicit_h_sdf_v2000_linear_alkane_c1_c4_exact_keys/1.0.0"
)
_FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID = (
    "exact_environment_and_term_keys_no_wildcards_no_precedence/1.0.0"
)
_FROZEN_FORCE_FIELD_TYPE_POLICY_ID = (
    "bounded_environment_exact_one_to_one_force_field_types/1.0.0"
)
_FROZEN_CHARGE_ASSIGNMENT_POLICY_ID = (
    "explicit_charge_parameter_lookup_no_source_or_formal_copy/1.0.0"
)
_FROZEN_CHARGE_SUM_POLICY_ID = (
    "ascending_environment_then_repeated_count_math_fsum_binary64/1.0.0"
)
_FROZEN_LJ_FUNCTIONAL_FORM_ID = "lj_12_6_four_epsilon_sigma/1.0.0"
_FROZEN_LJ_COMBINING_RULE_ID = "lorentz_berthelot_sigma_arithmetic_epsilon_geometric/1.0.0"
_FROZEN_LJ_OVERRIDE_POLICY_ID = (
    "exact_unordered_type_pair_full_sigma_epsilon_override_before_1_4_scale/1.0.0"
)
_FROZEN_COULOMB_BASE_FORM_ID = "direct_pair_k_e_q_i_q_j_over_r_coefficient_deferred/1.0.0"
_FROZEN_PROPER_FUNCTIONAL_FORM_ID = (
    "periodic_proper_sum_k_one_plus_cos_n_phi_minus_delta/1.0.0"
)
_FROZEN_PROPER_COORDINATE_CONVENTION_ID = (
    "signed_dihedral_cross_normals_full_reversal_invariant/1.0.0"
)
_FROZEN_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian_elementary_charge/"
    "1.0.0"
)
_FROZEN_BINARY64_ENCODING_ID = "ieee754_binary64_big_endian_hex/1.0.0"
_FROZEN_CHARGE_BALANCE_TOLERANCE_E = 1.0e-12
_FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID = (
    "harmonic_half_k_delta_squared_bond_angle/1.0.0"
)
_FROZEN_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_force_field_applicability/1.0.0"
)
_FROZEN_APPLICABILITY_PROFILE_ID = (
    "source_bound_sdf_v2000_explicit_h_neutral_linear_alkane_c1_c4/1.0.0"
)
_FROZEN_TYPING_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_topological_environment_typing/1.0.0"
)
_FROZEN_TYPING_ENVIRONMENT_POLICY_ID = (
    "linear_alkane_c1_c4_graph_neighbor_environment/1.0.0"
)
_FROZEN_INVENTORY_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_term_pair_inventory/1.0.0"
)
_FROZEN_INVENTORY_PROFILE_ID = (
    "source_explicit_h_sdf_v2000_linear_alkane_c1_c4_topology_v1"
)
_FROZEN_ENVIRONMENT_MATCH_POLICY_ID = (
    "linear_alkane_c1_c4_topological_environment_match_v1"
)
_FROZEN_PAIR_CLASSIFICATION_POLICY_ID = (
    "covalent_shortest_graph_distance_1_2_excluded_1_3_excluded_"
    "1_4_separate_farther_full_v1"
)
_FROZEN_IMPROPER_SELECTION_POLICY_ID = (
    "linear_alkane_c1_c4_selected_improper_empty_v1"
)
_FROZEN_CONSTRAINT_SELECTION_POLICY_ID = (
    "linear_alkane_c1_c4_unconstrained_diagnostic_empty_v1"
)
_MAX_ARTIFACT_BYTES = 1024 * 1024
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*\Z")
_SEMVER_PATTERN = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

_CM = "c_single_valence4_c0_h4"
_HM = "h_attached_c_single_valence4_c0_h4"
_CT = "c_single_valence4_c1_h3"
_HT = "h_attached_c_single_valence4_c1_h3"
_CI = "c_single_valence4_c2_h2"
_HI = "h_attached_c_single_valence4_c2_h2"

_FROZEN_ENVIRONMENT_IDS = tuple(sorted((_CM, _HM, _CT, _HT, _CI, _HI)))
_FROZEN_BOND_KEYS = tuple(
    sorted(
        (
            (_CM, _HM),
            (_CT, _CT),
            (_CT, _CI),
            (_CT, _HT),
            (_CI, _CI),
            (_CI, _HI),
        )
    )
)
_FROZEN_ANGLE_KEYS = tuple(
    sorted(
        (
            (_HM, _CM, _HM),
            (_CT, _CT, _HT),
            (_HT, _CT, _HT),
            (_CT, _CI, _CT),
            (_CT, _CI, _CI),
            (_CT, _CI, _HI),
            (_CI, _CT, _HT),
            (_CI, _CI, _HI),
            (_HI, _CI, _HI),
        )
    )
)
_FROZEN_PROPER_KEYS = tuple(
    sorted(
        (
            (_CI, _CI, _CT, _HT),
            (_CT, _CI, _CI, _CT),
            (_CT, _CI, _CI, _HI),
            (_CT, _CI, _CT, _HT),
            (_HI, _CI, _CI, _HI),
            (_HT, _CT, _CI, _HI),
            (_HT, _CT, _CT, _HT),
        )
    )
)
_FROZEN_COMPONENT_ENVIRONMENT_COUNTS = tuple(
    (
        component_id,
        tuple(sorted(counts)),
    )
    for component_id, counts in (
        ("methane_c1", ((_CM, 1), (_HM, 4))),
        ("ethane_c2", ((_CT, 2), (_HT, 6))),
        ("propane_c3", ((_CI, 1), (_CT, 2), (_HI, 2), (_HT, 6))),
        ("n_butane_c4", ((_CI, 2), (_CT, 2), (_HI, 4), (_HT, 6))),
    )
)

LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_VERSION = (
    _FROZEN_PROTOCOL_SCHEMA_VERSION
)
LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_ID = _FROZEN_PROTOCOL_SCHEMA_ID
LINEAR_ALKANE_PARAMETER_SET_SCHEMA_VERSION = (
    _FROZEN_PARAMETER_SET_SCHEMA_VERSION
)
LINEAR_ALKANE_PARAMETER_SET_SCHEMA_ID = _FROZEN_PARAMETER_SET_SCHEMA_ID
LINEAR_ALKANE_PARAMETER_SCOPE = _FROZEN_PARAMETER_SCOPE
LINEAR_ALKANE_PARAMETER_DOMAIN_ID = _FROZEN_PARAMETER_DOMAIN_ID
LINEAR_ALKANE_PARAMETER_ASSIGNMENT_POLICY_ID = (
    _FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID
)
LINEAR_ALKANE_FORCE_FIELD_TYPE_POLICY_ID = _FROZEN_FORCE_FIELD_TYPE_POLICY_ID
LINEAR_ALKANE_CHARGE_ASSIGNMENT_POLICY_ID = (
    _FROZEN_CHARGE_ASSIGNMENT_POLICY_ID
)
LINEAR_ALKANE_CHARGE_SUM_POLICY_ID = _FROZEN_CHARGE_SUM_POLICY_ID
LINEAR_ALKANE_LJ_FUNCTIONAL_FORM_ID = _FROZEN_LJ_FUNCTIONAL_FORM_ID
LINEAR_ALKANE_LJ_COMBINING_RULE_ID = _FROZEN_LJ_COMBINING_RULE_ID
LINEAR_ALKANE_LJ_OVERRIDE_POLICY_ID = _FROZEN_LJ_OVERRIDE_POLICY_ID
LINEAR_ALKANE_COULOMB_BASE_FORM_ID = _FROZEN_COULOMB_BASE_FORM_ID
LINEAR_ALKANE_PROPER_FUNCTIONAL_FORM_ID = (
    _FROZEN_PROPER_FUNCTIONAL_FORM_ID
)
LINEAR_ALKANE_PROPER_COORDINATE_CONVENTION_ID = (
    _FROZEN_PROPER_COORDINATE_CONVENTION_ID
)
LINEAR_ALKANE_FORCE_FIELD_UNIT_SYSTEM_ID = _FROZEN_UNIT_SYSTEM_ID
LINEAR_ALKANE_BINARY64_ENCODING_ID = _FROZEN_BINARY64_ENCODING_ID
LINEAR_ALKANE_CHARGE_BALANCE_TOLERANCE_E = (
    _FROZEN_CHARGE_BALANCE_TOLERANCE_E
)
LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS = _FROZEN_ENVIRONMENT_IDS
LINEAR_ALKANE_PARAMETER_BOND_KEYS = _FROZEN_BOND_KEYS
LINEAR_ALKANE_PARAMETER_ANGLE_KEYS = _FROZEN_ANGLE_KEYS
LINEAR_ALKANE_PARAMETER_PROPER_KEYS = _FROZEN_PROPER_KEYS


class LinearAlkaneParameterContractError(ValueError):
    """Raised when a bounded parameter artifact violates its frozen contract."""


class LinearAlkaneParameterSerializationError(LinearAlkaneParameterContractError):
    """Raised when canonical parameter JSON is malformed or noncanonical."""


def _require_identifier(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a non-empty canonical identifier")
    return value


def _require_semver(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if _SEMVER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical semantic version text")
    return value


def _require_sha256_or_none(name: str, value: Any) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest or None")
    return value


def _require_finite_binary64(
    name: str,
    value: Any,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if type(value) is not float:
        raise TypeError(f"{name} must be an exact float")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value == 0.0 and math.copysign(1.0, value) < 0.0:
        raise ValueError(f"{name} must not be negative zero")
    if positive and value <= 0.0:
        raise ValueError(f"{name} must be positive")
    if nonnegative and value < 0.0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _binary64_hex(value: float) -> str:
    _require_finite_binary64("binary64 value", value)
    return struct.pack(">d", value).hex()


def _binary64_from_hex(name: str, value: Any) -> float:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{16}", value) is None:
        raise LinearAlkaneParameterSerializationError(
            f"{name} must be canonical lowercase 16-digit binary64 hex"
        )
    number = struct.unpack(">d", bytes.fromhex(value))[0]
    _require_finite_binary64(name, number)
    if _binary64_hex(number) != value:
        raise LinearAlkaneParameterSerializationError(
            f"{name} is not canonical binary64 hex"
        )
    return number


def _canonical_json_bytes(document: Mapping[str, Any]) -> bytes:
    try:
        payload = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise LinearAlkaneParameterSerializationError(
            f"canonical JSON encoding failed: {exc}"
        ) from exc
    if len(payload) > _MAX_ARTIFACT_BYTES:
        raise LinearAlkaneParameterSerializationError(
            "parameter artifact exceeds the one-megabyte limit"
        )
    return payload


def _sha256_document(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json_bytes(document)).hexdigest()


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneEnvironmentParameterMapping:
    topological_environment_id: str
    force_field_type_id: str
    charge_parameter_id: str

    def __post_init__(self) -> None:
        _require_identifier(
            "topological_environment_id",
            self.topological_environment_id,
        )
        _require_identifier("force_field_type_id", self.force_field_type_id)
        _require_identifier("charge_parameter_id", self.charge_parameter_id)
        if self.topological_environment_id not in _FROZEN_ENVIRONMENT_IDS:
            raise ValueError("unknown bounded topological environment ID")

    def to_dict(self) -> dict[str, str]:
        self.__post_init__()
        return {
            "topological_environment_id": self.topological_environment_id,
            "force_field_type_id": self.force_field_type_id,
            "charge_parameter_id": self.charge_parameter_id,
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneLennardJonesTypeParameter:
    force_field_type_id: str
    sigma_angstrom: float
    epsilon_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        _require_identifier("force_field_type_id", self.force_field_type_id)
        _require_finite_binary64(
            "sigma_angstrom",
            self.sigma_angstrom,
            positive=True,
        )
        _require_finite_binary64(
            "epsilon_kilojoule_per_mole",
            self.epsilon_kilojoule_per_mole,
            positive=True,
        )

    def to_dict(self) -> dict[str, str]:
        self.__post_init__()
        return {
            "force_field_type_id": self.force_field_type_id,
            "sigma_angstrom_binary64": _binary64_hex(self.sigma_angstrom),
            "epsilon_kilojoule_per_mole_binary64": _binary64_hex(
                self.epsilon_kilojoule_per_mole
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkanePartialChargeParameter:
    charge_parameter_id: str
    partial_charge_e: float

    def __post_init__(self) -> None:
        _require_identifier("charge_parameter_id", self.charge_parameter_id)
        _require_finite_binary64("partial_charge_e", self.partial_charge_e)

    def to_dict(self) -> dict[str, str]:
        self.__post_init__()
        return {
            "charge_parameter_id": self.charge_parameter_id,
            "partial_charge_e_binary64": _binary64_hex(self.partial_charge_e),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneLennardJonesPairOverride:
    force_field_type_i: str
    force_field_type_j: str
    sigma_angstrom: float
    epsilon_kilojoule_per_mole: float
    override_id: str

    def __post_init__(self) -> None:
        _require_identifier("force_field_type_i", self.force_field_type_i)
        _require_identifier("force_field_type_j", self.force_field_type_j)
        _require_identifier("override_id", self.override_id)
        if self.force_field_type_i > self.force_field_type_j:
            raise ValueError("LJ override type pair must be canonically ordered")
        _require_finite_binary64(
            "sigma_angstrom",
            self.sigma_angstrom,
            positive=True,
        )
        _require_finite_binary64(
            "epsilon_kilojoule_per_mole",
            self.epsilon_kilojoule_per_mole,
            positive=True,
        )

    def to_dict(self) -> dict[str, str]:
        self.__post_init__()
        return {
            "force_field_type_i": self.force_field_type_i,
            "force_field_type_j": self.force_field_type_j,
            "sigma_angstrom_binary64": _binary64_hex(self.sigma_angstrom),
            "epsilon_kilojoule_per_mole_binary64": _binary64_hex(
                self.epsilon_kilojoule_per_mole
            ),
            "override_id": self.override_id,
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneBondParameterRule:
    match_key: CanonicalBondEnvironmentMatchKey
    parameter_id: str
    equilibrium_length_angstrom: float
    force_constant_kilojoule_per_mole_per_angstrom2: float

    def __post_init__(self) -> None:
        if type(self.match_key) is not CanonicalBondEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical bond key")
        self.match_key.__post_init__()
        _require_identifier("parameter_id", self.parameter_id)
        _require_finite_binary64(
            "equilibrium_length_angstrom",
            self.equilibrium_length_angstrom,
            positive=True,
        )
        _require_finite_binary64(
            "force_constant_kilojoule_per_mole_per_angstrom2",
            self.force_constant_kilojoule_per_mole_per_angstrom2,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "match_key": self.match_key.to_dict(),
            "parameter_id": self.parameter_id,
            "equilibrium_length_angstrom_binary64": _binary64_hex(
                self.equilibrium_length_angstrom
            ),
            "force_constant_kilojoule_per_mole_per_angstrom2_binary64": (
                _binary64_hex(
                    self.force_constant_kilojoule_per_mole_per_angstrom2
                )
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneAngleParameterRule:
    match_key: CanonicalAngleEnvironmentMatchKey
    parameter_id: str
    equilibrium_angle_radian: float
    force_constant_kilojoule_per_mole_per_radian2: float

    def __post_init__(self) -> None:
        if type(self.match_key) is not CanonicalAngleEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical angle key")
        self.match_key.__post_init__()
        _require_identifier("parameter_id", self.parameter_id)
        angle = _require_finite_binary64(
            "equilibrium_angle_radian",
            self.equilibrium_angle_radian,
            positive=True,
        )
        if angle >= math.pi:
            raise ValueError("equilibrium angle must be strictly below pi")
        _require_finite_binary64(
            "force_constant_kilojoule_per_mole_per_radian2",
            self.force_constant_kilojoule_per_mole_per_radian2,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "match_key": self.match_key.to_dict(),
            "parameter_id": self.parameter_id,
            "equilibrium_angle_radian_binary64": _binary64_hex(
                self.equilibrium_angle_radian
            ),
            "force_constant_kilojoule_per_mole_per_radian2_binary64": (
                _binary64_hex(
                    self.force_constant_kilojoule_per_mole_per_radian2
                )
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneProperTorsionComponent:
    periodicity: int
    phase_radian: float
    amplitude_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        if type(self.periodicity) is not int:
            raise TypeError("periodicity must be an exact integer")
        if self.periodicity < 1 or self.periodicity > 6:
            raise ValueError("periodicity must be in [1, 6]")
        phase = _require_finite_binary64("phase_radian", self.phase_radian)
        if phase < 0.0 or phase >= math.tau:
            raise ValueError("phase_radian must be in [0, 2*pi)")
        _require_finite_binary64(
            "amplitude_kilojoule_per_mole",
            self.amplitude_kilojoule_per_mole,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "periodicity": self.periodicity,
            "phase_radian_binary64": _binary64_hex(self.phase_radian),
            "amplitude_kilojoule_per_mole_binary64": _binary64_hex(
                self.amplitude_kilojoule_per_mole
            ),
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneProperParameterRule:
    match_key: CanonicalProperEnvironmentMatchKey
    parameter_id: str
    components: tuple[LinearAlkaneProperTorsionComponent, ...]

    def __post_init__(self) -> None:
        if type(self.match_key) is not CanonicalProperEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical proper key")
        self.match_key.__post_init__()
        _require_identifier("parameter_id", self.parameter_id)
        if type(self.components) is not tuple or not self.components:
            raise TypeError("components must be a non-empty tuple")
        if not all(
            type(component) is LinearAlkaneProperTorsionComponent
            for component in self.components
        ):
            raise TypeError("components must contain exact torsion components")
        for component in self.components:
            component.__post_init__()
        component_keys = tuple(
            (component.periodicity, _binary64_hex(component.phase_radian))
            for component in self.components
        )
        if component_keys != tuple(sorted(component_keys)):
            raise ValueError("proper components must be canonically sorted")
        if len(set(component_keys)) != len(component_keys):
            raise ValueError("proper components must not duplicate n/phase")

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return {
            "match_key": self.match_key.to_dict(),
            "parameter_id": self.parameter_id,
            "components": [component.to_dict() for component in self.components],
        }


@dataclass(frozen=True, order=True, slots=True)
class ResolvedLinearAlkaneLennardJonesPair:
    force_field_type_i: str
    force_field_type_j: str
    sigma_angstrom: float
    epsilon_kilojoule_per_mole: float
    resolution_status: str
    override_id: str | None

    def __post_init__(self) -> None:
        _require_identifier("force_field_type_i", self.force_field_type_i)
        _require_identifier("force_field_type_j", self.force_field_type_j)
        if self.force_field_type_i > self.force_field_type_j:
            raise ValueError("resolved LJ type pair must be canonically ordered")
        _require_finite_binary64(
            "sigma_angstrom",
            self.sigma_angstrom,
            positive=True,
        )
        _require_finite_binary64(
            "epsilon_kilojoule_per_mole",
            self.epsilon_kilojoule_per_mole,
            positive=True,
        )
        if type(self.resolution_status) is not str:
            raise TypeError("resolution_status must be an exact string")
        if self.resolution_status not in {
            "lorentz_berthelot",
            "exact_pair_override",
        }:
            raise ValueError("unknown LJ resolution status")
        if self.resolution_status == "exact_pair_override":
            _require_identifier("override_id", self.override_id)
        elif self.override_id is not None:
            raise ValueError("combined LJ pairs cannot carry an override ID")


def _bond_key_from_raw(
    value: tuple[str, str],
) -> CanonicalBondEnvironmentMatchKey:
    return CanonicalBondEnvironmentMatchKey.from_environments(*value)


def _angle_key_from_raw(
    value: tuple[str, str, str],
) -> CanonicalAngleEnvironmentMatchKey:
    return CanonicalAngleEnvironmentMatchKey.from_environments(*value)


def _proper_key_from_raw(
    value: tuple[str, str, str, str],
) -> CanonicalProperEnvironmentMatchKey:
    return CanonicalProperEnvironmentMatchKey.from_environments(*value)


def _unit_system_document() -> dict[str, Any]:
    return {
        "unit_system_id": _FROZEN_UNIT_SYSTEM_ID,
        "binary64_encoding_id": _FROZEN_BINARY64_ENCODING_ID,
        "distance": "angstrom",
        "angle": "radian",
        "energy": "kilojoule_per_mole",
        "charge": "elementary_charge",
        "bond_force_constant": (
            "kilojoule_per_mole_per_angstrom_squared"
        ),
        "angle_force_constant": (
            "kilojoule_per_mole_per_radian_squared"
        ),
        "proper_amplitude": "kilojoule_per_mole",
        "lj_sigma": "angstrom",
        "lj_epsilon": "kilojoule_per_mole",
        "energy_scale": "dimensionless",
        "force": "kilojoule_per_mole_per_angstrom",
        "virial": "kilojoule_per_mole",
    }


def _protocol_document() -> dict[str, Any]:
    return {
        "schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
        "schema_version": _FROZEN_PROTOCOL_SCHEMA_VERSION,
        "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
        "parameter_scope": _FROZEN_PARAMETER_SCOPE,
        "parameter_domain_id": _FROZEN_PARAMETER_DOMAIN_ID,
        "assignment_policy_id": _FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID,
        "force_field_type_policy_id": _FROZEN_FORCE_FIELD_TYPE_POLICY_ID,
        "applicability_schema_id": _FROZEN_APPLICABILITY_SCHEMA_ID,
        "applicability_profile_id": _FROZEN_APPLICABILITY_PROFILE_ID,
        "typing_schema_id": (
            _FROZEN_TYPING_SCHEMA_ID
        ),
        "typing_environment_policy_id": (
            _FROZEN_TYPING_ENVIRONMENT_POLICY_ID
        ),
        "inventory_schema_id": _FROZEN_INVENTORY_SCHEMA_ID,
        "inventory_profile_id": _FROZEN_INVENTORY_PROFILE_ID,
        "environment_match_policy_id": _FROZEN_ENVIRONMENT_MATCH_POLICY_ID,
        "pair_classification_policy_id": (
            _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
        ),
        "improper_selection_policy_id": (
            _FROZEN_IMPROPER_SELECTION_POLICY_ID
        ),
        "constraint_selection_policy_id": (
            _FROZEN_CONSTRAINT_SELECTION_POLICY_ID
        ),
        "bond_angle_functional_form_id": (
            _FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID
        ),
        "proper_functional_form_id": _FROZEN_PROPER_FUNCTIONAL_FORM_ID,
        "proper_coordinate_convention_id": (
            _FROZEN_PROPER_COORDINATE_CONVENTION_ID
        ),
        "functional_form_definitions": {
            "bond": {
                "coordinate": "r=norm(r_j-r_i)",
                "energy": "E_b=0.5*k_b*(r-r0)^2",
                "domain": "r0>0;k_b>0",
            },
            "angle": {
                "vectors": "u=r_i-r_j;v=r_k-r_j",
                "coordinate": (
                    "theta=atan2(norm(cross(u,v)),dot(u,v))"
                ),
                "energy": "E_a=0.5*k_a*(theta-theta0)^2",
                "domain": "0<theta0<pi;k_a>0",
            },
            "proper": {
                "energy": (
                    "E_p(phi)=sum_m(k_m*(1+cos(n_m*phi-delta_m)))"
                ),
                "component_domain": (
                    "k_m>0;n_m_integer_in_[1,6];0<=delta_m<2*pi"
                ),
                "duplicate_policy": (
                    "each_(n_m,delta_m)_pair_unique_per_proper_rule"
                ),
            },
            "lennard_jones": {
                "energy": (
                    "U_lj=4*epsilon_ij*((sigma_ij/r)^12-(sigma_ij/r)^6)"
                ),
                "domain": "r>0;sigma_ij>0;epsilon_ij>0",
            },
            "coulomb_base": {
                "energy": "U_q=k_e*q_i*q_j/r",
                "coefficient_status": (
                    "k_e_deferred_to_evaluation_method_artifact"
                ),
                "domain": "r>0",
            },
        },
        "proper_coordinate_convention": {
            "bond_1": "b1=r_j-r_i",
            "bond_2": "b2=r_k-r_j",
            "bond_3": "b3=r_l-r_k",
            "normal_1": "n1=cross(b1,b2)",
            "normal_2": "n2=cross(b2,b3)",
            "middle_unit": "b2_hat=b2/norm(b2)",
            "atan2_y": "y=dot(cross(n1,n2),b2_hat)",
            "atan2_x": "x=dot(n1,n2)",
            "coordinate": "phi=atan2(y,x)",
            "range": "-pi<=phi<=pi",
            "full_path_reversal": (
                "phi(r_i,r_j,r_k,r_l)=phi(r_l,r_k,r_j,r_i)"
            ),
        },
        "lj_functional_form_id": _FROZEN_LJ_FUNCTIONAL_FORM_ID,
        "lj_combining_rule_id": _FROZEN_LJ_COMBINING_RULE_ID,
        "lj_override_policy_id": _FROZEN_LJ_OVERRIDE_POLICY_ID,
        "lj_resolution_semantics": {
            "sigma_combining": "sigma_ij=(sigma_i+sigma_j)/2",
            "epsilon_combining": "epsilon_ij=sqrt(epsilon_i*epsilon_j)",
            "override_precedence": (
                "exact_full_sigma_epsilon_pair_override_before_1_4_scale"
            ),
            "partial_override": "prohibited",
        },
        "coulomb_base_form_id": _FROZEN_COULOMB_BASE_FORM_ID,
        "charge_assignment_policy_id": _FROZEN_CHARGE_ASSIGNMENT_POLICY_ID,
        "charge_sum_policy_id": _FROZEN_CHARGE_SUM_POLICY_ID,
        "charge_balance_tolerance_e_binary64": _binary64_hex(
            _FROZEN_CHARGE_BALANCE_TOLERANCE_E
        ),
        "charge_semantics": {
            "assignment": (
                "environment_to_charge_parameter_explicit_lookup"
            ),
            "source_partial_charge_use": "prohibited",
            "formal_charge_copy": "prohibited",
            "neutral_to_zero_inference": "prohibited",
            "component_sum": (
                "q_component=math_fsum(q_environment_repeated_by_count)"
            ),
            "acceptance": (
                "abs(q_component-target_formal_charge)<=tolerance"
            ),
            "renormalization": "prohibited",
        },
        "pair_scaling_semantics": {
            "excluded_1_2": "no_lj_or_coulomb_evaluation",
            "excluded_1_3": "no_lj_or_coulomb_evaluation",
            "one_four": "U_1_4=s_lj*U_lj+s_q*U_q",
            "one_four_lj_scale_field": "one_four_lj_energy_scale",
            "one_four_coulomb_scale_field": (
                "one_four_coulomb_energy_scale"
            ),
            "full_nonbonded": "U_full=U_lj+U_q",
            "scale_application_order": (
                "resolve_lj_override_or_combining_then_apply_1_4_scale"
            ),
            "per_torsion_scale": "unsupported_in_schema_1_0",
        },
        "environment_ids": list(_FROZEN_ENVIRONMENT_IDS),
        "bond_keys": [list(value) for value in _FROZEN_BOND_KEYS],
        "angle_keys": [list(value) for value in _FROZEN_ANGLE_KEYS],
        "proper_keys": [list(value) for value in _FROZEN_PROPER_KEYS],
        "component_environment_counts": [
            {
                "component_id": component_id,
                "environment_counts": [
                    {"environment_id": environment_id, "count": count}
                    for environment_id, count in counts
                ],
                "target_formal_charge": 0,
            }
            for component_id, counts in _FROZEN_COMPONENT_ENVIRONMENT_COUNTS
        ],
        "unit_system": _unit_system_document(),
        "deferred_evaluation_method_fields": [
            "coulomb_coefficient",
            "relative_dielectric",
            "r_switch",
            "r_cut",
            "switch_function",
            "neighbor_skin",
            "neighbor_capacity",
            "periodic_boundary_conditions",
            "minimum_image",
            "long_range_method",
            "dispersion_tail_correction",
            "dtype",
            "device",
            "kernel_accumulation_order",
        ],
    }


_FROZEN_PROTOCOL_DOCUMENT = _protocol_document()
_FROZEN_PROTOCOL_BYTES = _canonical_json_bytes(_FROZEN_PROTOCOL_DOCUMENT)
_FROZEN_PROTOCOL_SHA256 = hashlib.sha256(_FROZEN_PROTOCOL_BYTES).hexdigest()

LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256 = _FROZEN_PROTOCOL_SHA256


def linear_alkane_parameter_protocol_document() -> dict[str, Any]:
    """Return an independent canonical protocol document."""

    return json.loads(_FROZEN_PROTOCOL_BYTES.decode("ascii"))


def linear_alkane_parameter_protocol_bytes() -> bytes:
    """Return the frozen canonical protocol bytes."""

    return bytes(_FROZEN_PROTOCOL_BYTES)


@dataclass(frozen=True, slots=True)
class LinearAlkaneC1C4ParameterSet:
    """A complete but explicitly nonphysical bounded contract artifact."""

    parameter_set_id: str
    parameter_set_version: str
    charge_model_id: str
    environment_mappings: tuple[LinearAlkaneEnvironmentParameterMapping, ...]
    lj_type_parameters: tuple[LinearAlkaneLennardJonesTypeParameter, ...]
    charge_parameters: tuple[LinearAlkanePartialChargeParameter, ...]
    lj_pair_overrides: tuple[LinearAlkaneLennardJonesPairOverride, ...]
    bond_rules: tuple[LinearAlkaneBondParameterRule, ...]
    angle_rules: tuple[LinearAlkaneAngleParameterRule, ...]
    proper_rules: tuple[LinearAlkaneProperParameterRule, ...]
    one_four_lj_energy_scale: float
    one_four_coulomb_energy_scale: float
    parameter_source_sha256: str | None = None
    dataset_manifest_sha256: str | None = None
    split_manifest_sha256: str | None = None
    fit_protocol_sha256: str | None = None
    fit_receipt_sha256: str | None = None
    scientific_review_sha256: str | None = None
    license_review_sha256: str | None = None
    release_attestation_sha256: str | None = None
    reference_nonbonded_method_id: None = None

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        _require_identifier("parameter_set_id", self.parameter_set_id)
        _require_semver("parameter_set_version", self.parameter_set_version)
        _require_identifier("charge_model_id", self.charge_model_id)
        tuple_contracts = (
            (
                "environment_mappings",
                self.environment_mappings,
                LinearAlkaneEnvironmentParameterMapping,
            ),
            (
                "lj_type_parameters",
                self.lj_type_parameters,
                LinearAlkaneLennardJonesTypeParameter,
            ),
            (
                "charge_parameters",
                self.charge_parameters,
                LinearAlkanePartialChargeParameter,
            ),
            (
                "lj_pair_overrides",
                self.lj_pair_overrides,
                LinearAlkaneLennardJonesPairOverride,
            ),
            ("bond_rules", self.bond_rules, LinearAlkaneBondParameterRule),
            ("angle_rules", self.angle_rules, LinearAlkaneAngleParameterRule),
            ("proper_rules", self.proper_rules, LinearAlkaneProperParameterRule),
        )
        for name, values, expected_type in tuple_contracts:
            if type(values) is not tuple or not all(
                type(value) is expected_type for value in values
            ):
                raise TypeError(
                    f"{name} must be a tuple of exact "
                    f"{expected_type.__name__} rows"
                )
            for value in values:
                value.__post_init__()
                if type(value) is LinearAlkaneProperParameterRule:
                    for component in value.components:
                        component.__post_init__()
            if values != tuple(sorted(values)):
                raise ValueError(f"{name} must be canonically sorted")

        environment_ids = tuple(
            row.topological_environment_id for row in self.environment_mappings
        )
        if environment_ids != _FROZEN_ENVIRONMENT_IDS:
            raise ValueError("environment mappings must cover the exact universe")
        force_field_type_ids = tuple(
            row.force_field_type_id for row in self.environment_mappings
        )
        if len(set(force_field_type_ids)) != len(_FROZEN_ENVIRONMENT_IDS):
            raise ValueError(
                "v1 force-field types must map one-to-one to environments"
            )
        lj_type_ids = tuple(
            row.force_field_type_id for row in self.lj_type_parameters
        )
        if set(lj_type_ids) != set(force_field_type_ids) or (
            len(lj_type_ids) != len(force_field_type_ids)
        ):
            raise ValueError("LJ rows must cover every force-field type exactly")

        charge_parameter_ids = tuple(
            row.charge_parameter_id for row in self.charge_parameters
        )
        if not charge_parameter_ids or len(set(charge_parameter_ids)) != len(
            charge_parameter_ids
        ):
            raise ValueError("charge parameter IDs must be unique and non-empty")
        referenced_charge_ids = tuple(
            row.charge_parameter_id for row in self.environment_mappings
        )
        if set(charge_parameter_ids) != set(referenced_charge_ids):
            raise ValueError(
                "charge rows must exactly cover referenced charge parameter IDs"
            )
        charge_values = tuple(
            row.partial_charge_e for row in self.charge_parameters
        )
        if not any(value > 0.0 for value in charge_values) or not any(
            value < 0.0 for value in charge_values
        ):
            raise ValueError(
                "the nonphysical contract fixture must exercise nonzero "
                "positive and negative partial charges"
            )

        override_pairs = tuple(
            (row.force_field_type_i, row.force_field_type_j)
            for row in self.lj_pair_overrides
        )
        override_ids = tuple(row.override_id for row in self.lj_pair_overrides)
        if len(set(override_pairs)) != len(override_pairs):
            raise ValueError("LJ override type pairs must be unique")
        if len(set(override_ids)) != len(override_ids):
            raise ValueError("LJ override IDs must be unique")
        known_types = set(force_field_type_ids)
        if any(
            type_i not in known_types or type_j not in known_types
            for type_i, type_j in override_pairs
        ):
            raise ValueError("LJ overrides must reference known types")

        observed_bond_keys = tuple(
            (
                row.match_key.environment_i,
                row.match_key.environment_j,
            )
            for row in self.bond_rules
        )
        observed_angle_keys = tuple(
            (
                row.match_key.outer_environment_i,
                row.match_key.center_environment,
                row.match_key.outer_environment_k,
            )
            for row in self.angle_rules
        )
        observed_proper_keys = tuple(
            (
                row.match_key.environment_i,
                row.match_key.environment_j,
                row.match_key.environment_k,
                row.match_key.environment_l,
            )
            for row in self.proper_rules
        )
        if observed_bond_keys != _FROZEN_BOND_KEYS:
            raise ValueError("bond rules must cover the exact six-key universe")
        if observed_angle_keys != _FROZEN_ANGLE_KEYS:
            raise ValueError("angle rules must cover the exact nine-key universe")
        if observed_proper_keys != _FROZEN_PROPER_KEYS:
            raise ValueError("proper rules must cover the exact seven-key universe")
        term_parameter_ids = tuple(
            row.parameter_id
            for rows in (self.bond_rules, self.angle_rules, self.proper_rules)
            for row in rows
        )
        if len(set(term_parameter_ids)) != len(term_parameter_ids):
            raise ValueError("bonded parameter IDs must be globally unique")

        for name in (
            "one_four_lj_energy_scale",
            "one_four_coulomb_energy_scale",
        ):
            scale = _require_finite_binary64(
                name,
                getattr(self, name),
                nonnegative=True,
            )
            if scale > 1.0:
                raise ValueError(f"{name} must not exceed one")
        for name in (
            "parameter_source_sha256",
            "dataset_manifest_sha256",
            "split_manifest_sha256",
            "fit_protocol_sha256",
            "fit_receipt_sha256",
            "scientific_review_sha256",
            "license_review_sha256",
            "release_attestation_sha256",
        ):
            if _require_sha256_or_none(name, getattr(self, name)) is not None:
                raise ValueError(
                    f"{name} must remain None for a contract-only fixture"
                )
        if self.reference_nonbonded_method_id is not None:
            raise ValueError(
                "reference_nonbonded_method_id is deferred from schema 1.0"
            )
        try:
            component_sums = self._component_charge_sums_unvalidated()
        except OverflowError as exc:
            raise ValueError("component partial-charge summation overflowed") from exc
        for component_id, charge_sum in component_sums:
            if abs(charge_sum) > _FROZEN_CHARGE_BALANCE_TOLERANCE_E:
                raise ValueError(
                    f"{component_id} partial charges do not sum to target zero"
                )

    def _component_charge_sums_unvalidated(
        self,
    ) -> tuple[tuple[str, float], ...]:
        mapping_by_environment = {
            row.topological_environment_id: row
            for row in self.environment_mappings
        }
        charge_by_id = {
            row.charge_parameter_id: row.partial_charge_e
            for row in self.charge_parameters
        }
        return tuple(
            (
                component_id,
                math.fsum(
                    charge_by_id[
                        mapping_by_environment[
                            environment_id
                        ].charge_parameter_id
                    ]
                    for environment_id, count in counts
                    for _ in range(count)
                ),
            )
            for component_id, counts in _FROZEN_COMPONENT_ENVIRONMENT_COUNTS
        )

    @property
    def component_charge_sums_e(self) -> tuple[tuple[str, float], ...]:
        self._validate()
        return self._component_charge_sums_unvalidated()

    @property
    def protocol_sha256(self) -> str:
        self._validate()
        return _FROZEN_PROTOCOL_SHA256

    @property
    def contract_key_universe_complete(self) -> bool:
        self._validate()
        return True

    @property
    def artifact_purpose(self) -> str:
        self._validate()
        return "contract_fixture_only"

    @property
    def derivation_status(self) -> str:
        self._validate()
        return "declared_contract_fixture"

    @property
    def charge_assignment_status(self) -> str:
        self._validate()
        return "nonphysical_contract_fixture_explicit_lookup"

    @property
    def scientific_validation_status(self) -> str:
        self._validate()
        return "missing"

    @property
    def runtime_authorization_status(self) -> str:
        self._validate()
        return "prohibited"

    def _false_gate(self) -> bool:
        self._validate()
        return False

    @property
    def parameterability_assessed(self) -> bool:
        return self._false_gate()

    @property
    def parameterizable(self) -> bool:
        return self._false_gate()

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return self._false_gate()

    @property
    def physics_supported(self) -> bool:
        return self._false_gate()

    @property
    def scientifically_validated(self) -> bool:
        return self._false_gate()

    @property
    def runtime_eligible(self) -> bool:
        return self._false_gate()

    @property
    def execution_authorized(self) -> bool:
        return self._false_gate()

    @property
    def energy_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def force_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def virial_evaluation_authorized(self) -> bool:
        return self._false_gate()

    @property
    def minimization_authorized(self) -> bool:
        return self._false_gate()

    @property
    def simulation_ready(self) -> bool:
        return self._false_gate()

    @property
    def claim_safe(self) -> bool:
        return self._false_gate()

    @property
    def blockers(self) -> tuple[str, ...]:
        self._validate()
        return (
            "numeric_values_are_nonphysical_contract_fixtures",
            "scientific_dataset_fit_holdout_and_reference_validation_missing",
            "charge_model_and_lj_parameters_are_unvalidated",
            "license_review_and_release_attestation_missing",
            "bounded_neutral_linear_c1_c4_only",
            "branched_cyclic_charged_and_isotopic_chemistry_unsupported",
            "improper_and_constraint_parameters_absent_by_policy",
            "evaluation_method_cutoff_switch_coulomb_coefficient_pbc_and_long_range_undefined",
            "energy_force_virial_kernel_missing",
            "global_parameter_coverage_missing",
            "runtime_minimization_simulation_and_claim_authority_prohibited",
            "digests_are_binding_not_authentication",
        )

    def _parameter_payload_document(self) -> dict[str, Any]:
        self._validate()
        return {
            "protocol_schema_id": _FROZEN_PROTOCOL_SCHEMA_ID,
            "protocol_sha256": _FROZEN_PROTOCOL_SHA256,
            "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "parameter_scope": _FROZEN_PARAMETER_SCOPE,
            "parameter_domain_id": _FROZEN_PARAMETER_DOMAIN_ID,
            "assignment_policy_id": _FROZEN_PARAMETER_ASSIGNMENT_POLICY_ID,
            "force_field_type_policy_id": (
                _FROZEN_FORCE_FIELD_TYPE_POLICY_ID
            ),
            "charge_model_id": self.charge_model_id,
            "charge_assignment_policy_id": (
                _FROZEN_CHARGE_ASSIGNMENT_POLICY_ID
            ),
            "charge_sum_policy_id": _FROZEN_CHARGE_SUM_POLICY_ID,
            "charge_balance_tolerance_e_binary64": _binary64_hex(
                _FROZEN_CHARGE_BALANCE_TOLERANCE_E
            ),
            "bond_angle_functional_form_id": (
                _FROZEN_BOND_ANGLE_FUNCTIONAL_FORM_ID
            ),
            "proper_functional_form_id": (
                _FROZEN_PROPER_FUNCTIONAL_FORM_ID
            ),
            "proper_coordinate_convention_id": (
                _FROZEN_PROPER_COORDINATE_CONVENTION_ID
            ),
            "lj_functional_form_id": _FROZEN_LJ_FUNCTIONAL_FORM_ID,
            "lj_combining_rule_id": _FROZEN_LJ_COMBINING_RULE_ID,
            "lj_override_policy_id": _FROZEN_LJ_OVERRIDE_POLICY_ID,
            "coulomb_base_form_id": _FROZEN_COULOMB_BASE_FORM_ID,
            "pair_classification_policy_id": (
                _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
            ),
            "improper_selection_policy_id": (
                _FROZEN_IMPROPER_SELECTION_POLICY_ID
            ),
            "constraint_selection_policy_id": (
                _FROZEN_CONSTRAINT_SELECTION_POLICY_ID
            ),
            "unit_system": _unit_system_document(),
            "environment_mappings": [
                row.to_dict() for row in self.environment_mappings
            ],
            "lj_type_parameters": [
                row.to_dict() for row in self.lj_type_parameters
            ],
            "charge_parameters": [
                row.to_dict() for row in self.charge_parameters
            ],
            "lj_pair_overrides": [
                row.to_dict() for row in self.lj_pair_overrides
            ],
            "bond_rules": [row.to_dict() for row in self.bond_rules],
            "angle_rules": [row.to_dict() for row in self.angle_rules],
            "proper_rules": [row.to_dict() for row in self.proper_rules],
            "improper_parameters": [],
            "constraint_parameters": [],
            "one_four_lj_energy_scale_binary64": _binary64_hex(
                self.one_four_lj_energy_scale
            ),
            "one_four_coulomb_energy_scale_binary64": _binary64_hex(
                self.one_four_coulomb_energy_scale
            ),
            "reference_nonbonded_method_id": None,
            "deferred_evaluation_method_status": "not_defined",
        }

    @property
    def parameter_payload_sha256(self) -> str:
        return _sha256_document(self._parameter_payload_document())

    def _core_dict(self) -> dict[str, Any]:
        payload = self._parameter_payload_document()
        return {
            "schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "schema_version": _FROZEN_PARAMETER_SET_SCHEMA_VERSION,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_version": self.parameter_set_version,
            "parameter_payload": payload,
            "parameter_payload_sha256": _sha256_document(payload),
            "artifact_purpose": "contract_fixture_only",
            "derivation_status": "declared_contract_fixture",
            "charge_assignment_status": (
                "nonphysical_contract_fixture_explicit_lookup"
            ),
            "fit_execution_status": "not_run",
            "fit_evidence_review_status": "not_applicable",
            "scientific_validation_status": "missing",
            "runtime_authorization_status": "prohibited",
            "source_authentication_status": "not_authenticated",
            "license_review_status": "not_reviewed",
            "parameter_source_sha256": None,
            "dataset_manifest_sha256": None,
            "split_manifest_sha256": None,
            "fit_protocol_sha256": None,
            "fit_receipt_sha256": None,
            "scientific_review_sha256": None,
            "license_review_sha256": None,
            "release_attestation_sha256": None,
            "contract_key_universe_complete": True,
            "component_charge_sums_e_binary64": [
                {
                    "component_id": component_id,
                    "charge_sum_e_binary64": _binary64_hex(charge_sum),
                    "target_formal_charge": 0,
                }
                for component_id, charge_sum in self.component_charge_sums_e
            ],
            "parameterability_assessed": False,
            "parameterizable": False,
            "global_parameter_coverage_complete": False,
            "physics_supported": False,
            "scientifically_validated": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "virial_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "blockers": list(self.blockers),
        }

    @property
    def parameter_set_sha256(self) -> str:
        return _sha256_document(self._core_dict())

    def to_dict(self) -> dict[str, Any]:
        document = self._core_dict()
        document["parameter_set_sha256"] = _sha256_document(document)
        return document


def resolve_linear_alkane_lj_pair(
    parameter_set: LinearAlkaneC1C4ParameterSet,
    force_field_type_i: str,
    force_field_type_j: str,
) -> ResolvedLinearAlkaneLennardJonesPair:
    """Resolve an LJ parameter pair without evaluating an interaction."""

    if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
        raise TypeError("parameter_set must be an exact parameter set")
    parameter_set._validate()
    type_i = _require_identifier("force_field_type_i", force_field_type_i)
    type_j = _require_identifier("force_field_type_j", force_field_type_j)
    type_i, type_j = sorted((type_i, type_j))
    for override in parameter_set.lj_pair_overrides:
        if (
            override.force_field_type_i,
            override.force_field_type_j,
        ) == (type_i, type_j):
            return ResolvedLinearAlkaneLennardJonesPair(
                force_field_type_i=type_i,
                force_field_type_j=type_j,
                sigma_angstrom=override.sigma_angstrom,
                epsilon_kilojoule_per_mole=(
                    override.epsilon_kilojoule_per_mole
                ),
                resolution_status="exact_pair_override",
                override_id=override.override_id,
            )
    by_type = {
        row.force_field_type_id: row
        for row in parameter_set.lj_type_parameters
    }
    try:
        row_i = by_type[type_i]
        row_j = by_type[type_j]
    except KeyError as exc:
        raise LinearAlkaneParameterContractError(
            "LJ resolution requires two known force-field types"
        ) from exc
    sigma_lo, sigma_hi = sorted(
        (row_i.sigma_angstrom, row_j.sigma_angstrom)
    )
    combined_sigma = sigma_lo + 0.5 * (sigma_hi - sigma_lo)
    combined_epsilon = (
        math.sqrt(row_i.epsilon_kilojoule_per_mole)
        * math.sqrt(row_j.epsilon_kilojoule_per_mole)
    )
    return ResolvedLinearAlkaneLennardJonesPair(
        force_field_type_i=type_i,
        force_field_type_j=type_j,
        sigma_angstrom=combined_sigma,
        epsilon_kilojoule_per_mole=combined_epsilon,
        resolution_status="lorentz_berthelot",
        override_id=None,
    )


_ROOT_KEYS = frozenset(
    {
        "schema_id",
        "schema_version",
        "parameter_set_id",
        "parameter_set_version",
        "parameter_payload",
        "parameter_payload_sha256",
        "artifact_purpose",
        "derivation_status",
        "charge_assignment_status",
        "fit_execution_status",
        "fit_evidence_review_status",
        "scientific_validation_status",
        "runtime_authorization_status",
        "source_authentication_status",
        "license_review_status",
        "parameter_source_sha256",
        "dataset_manifest_sha256",
        "split_manifest_sha256",
        "fit_protocol_sha256",
        "fit_receipt_sha256",
        "scientific_review_sha256",
        "license_review_sha256",
        "release_attestation_sha256",
        "contract_key_universe_complete",
        "component_charge_sums_e_binary64",
        "parameterability_assessed",
        "parameterizable",
        "global_parameter_coverage_complete",
        "physics_supported",
        "scientifically_validated",
        "runtime_eligible",
        "execution_authorized",
        "energy_evaluation_authorized",
        "force_evaluation_authorized",
        "virial_evaluation_authorized",
        "minimization_authorized",
        "simulation_ready",
        "claim_safe",
        "blockers",
        "parameter_set_sha256",
    }
)
_PAYLOAD_KEYS = frozenset(
    {
        "protocol_schema_id",
        "protocol_sha256",
        "parameter_set_schema_id",
        "parameter_scope",
        "parameter_domain_id",
        "assignment_policy_id",
        "force_field_type_policy_id",
        "charge_model_id",
        "charge_assignment_policy_id",
        "charge_sum_policy_id",
        "charge_balance_tolerance_e_binary64",
        "bond_angle_functional_form_id",
        "proper_functional_form_id",
        "proper_coordinate_convention_id",
        "lj_functional_form_id",
        "lj_combining_rule_id",
        "lj_override_policy_id",
        "coulomb_base_form_id",
        "pair_classification_policy_id",
        "improper_selection_policy_id",
        "constraint_selection_policy_id",
        "unit_system",
        "environment_mappings",
        "lj_type_parameters",
        "charge_parameters",
        "lj_pair_overrides",
        "bond_rules",
        "angle_rules",
        "proper_rules",
        "improper_parameters",
        "constraint_parameters",
        "one_four_lj_energy_scale_binary64",
        "one_four_coulomb_energy_scale_binary64",
        "reference_nonbonded_method_id",
        "deferred_evaluation_method_status",
    }
)
_ENVIRONMENT_MAPPING_KEYS = frozenset(
    {
        "topological_environment_id",
        "force_field_type_id",
        "charge_parameter_id",
    }
)
_LJ_TYPE_KEYS = frozenset(
    {
        "force_field_type_id",
        "sigma_angstrom_binary64",
        "epsilon_kilojoule_per_mole_binary64",
    }
)
_CHARGE_KEYS = frozenset(
    {"charge_parameter_id", "partial_charge_e_binary64"}
)
_LJ_OVERRIDE_KEYS = frozenset(
    {
        "force_field_type_i",
        "force_field_type_j",
        "sigma_angstrom_binary64",
        "epsilon_kilojoule_per_mole_binary64",
        "override_id",
    }
)
_BOND_RULE_KEYS = frozenset(
    {
        "match_key",
        "parameter_id",
        "equilibrium_length_angstrom_binary64",
        "force_constant_kilojoule_per_mole_per_angstrom2_binary64",
    }
)
_ANGLE_RULE_KEYS = frozenset(
    {
        "match_key",
        "parameter_id",
        "equilibrium_angle_radian_binary64",
        "force_constant_kilojoule_per_mole_per_radian2_binary64",
    }
)
_PROPER_RULE_KEYS = frozenset({"match_key", "parameter_id", "components"})
_PROPER_COMPONENT_KEYS = frozenset(
    {
        "periodicity",
        "phase_radian_binary64",
        "amplitude_kilojoule_per_mole_binary64",
    }
)
_BOND_MATCH_KEYS = frozenset({"environment_i", "environment_j"})
_ANGLE_MATCH_KEYS = frozenset(
    {
        "outer_environment_i",
        "center_environment",
        "outer_environment_k",
    }
)
_PROPER_MATCH_KEYS = frozenset(
    {
        "environment_i",
        "environment_j",
        "environment_k",
        "environment_l",
    }
)


def _require_mapping(value: Any, *, location: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise LinearAlkaneParameterSerializationError(
            f"{location} must be a JSON object"
        )
    return value


def _require_list(value: Any, *, location: str) -> list[Any]:
    if type(value) is not list:
        raise LinearAlkaneParameterSerializationError(
            f"{location} must be a JSON array"
        )
    return value


def _require_string(value: Any, *, location: str) -> str:
    if type(value) is not str:
        raise LinearAlkaneParameterSerializationError(
            f"{location} must be a JSON string"
        )
    return value


def _require_integer(value: Any, *, location: str) -> int:
    if type(value) is not int:
        raise LinearAlkaneParameterSerializationError(
            f"{location} must be a JSON integer"
        )
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: frozenset[str],
    *,
    location: str,
) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise LinearAlkaneParameterSerializationError(
            f"{location} keys mismatch; missing={missing}, extra={extra}"
        )


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LinearAlkaneParameterSerializationError(
                f"duplicate JSON object key {key!r}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise LinearAlkaneParameterSerializationError(
        f"nonstandard JSON constant {value!r} is not allowed"
    )


def _parse_environment_mapping(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneEnvironmentParameterMapping:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _ENVIRONMENT_MAPPING_KEYS, location=location)
    return LinearAlkaneEnvironmentParameterMapping(
        topological_environment_id=_require_string(
            row["topological_environment_id"],
            location=f"{location}.topological_environment_id",
        ),
        force_field_type_id=_require_string(
            row["force_field_type_id"],
            location=f"{location}.force_field_type_id",
        ),
        charge_parameter_id=_require_string(
            row["charge_parameter_id"],
            location=f"{location}.charge_parameter_id",
        ),
    )


def _parse_lj_type(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneLennardJonesTypeParameter:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _LJ_TYPE_KEYS, location=location)
    return LinearAlkaneLennardJonesTypeParameter(
        force_field_type_id=_require_string(
            row["force_field_type_id"],
            location=f"{location}.force_field_type_id",
        ),
        sigma_angstrom=_binary64_from_hex(
            f"{location}.sigma_angstrom_binary64",
            row["sigma_angstrom_binary64"],
        ),
        epsilon_kilojoule_per_mole=_binary64_from_hex(
            f"{location}.epsilon_kilojoule_per_mole_binary64",
            row["epsilon_kilojoule_per_mole_binary64"],
        ),
    )


def _parse_charge(
    value: Any,
    *,
    location: str,
) -> LinearAlkanePartialChargeParameter:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _CHARGE_KEYS, location=location)
    return LinearAlkanePartialChargeParameter(
        charge_parameter_id=_require_string(
            row["charge_parameter_id"],
            location=f"{location}.charge_parameter_id",
        ),
        partial_charge_e=_binary64_from_hex(
            f"{location}.partial_charge_e_binary64",
            row["partial_charge_e_binary64"],
        ),
    )


def _parse_lj_override(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneLennardJonesPairOverride:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _LJ_OVERRIDE_KEYS, location=location)
    return LinearAlkaneLennardJonesPairOverride(
        force_field_type_i=_require_string(
            row["force_field_type_i"],
            location=f"{location}.force_field_type_i",
        ),
        force_field_type_j=_require_string(
            row["force_field_type_j"],
            location=f"{location}.force_field_type_j",
        ),
        sigma_angstrom=_binary64_from_hex(
            f"{location}.sigma_angstrom_binary64",
            row["sigma_angstrom_binary64"],
        ),
        epsilon_kilojoule_per_mole=_binary64_from_hex(
            f"{location}.epsilon_kilojoule_per_mole_binary64",
            row["epsilon_kilojoule_per_mole_binary64"],
        ),
        override_id=_require_string(
            row["override_id"],
            location=f"{location}.override_id",
        ),
    )


def _parse_bond_match_key(
    value: Any,
    *,
    location: str,
) -> CanonicalBondEnvironmentMatchKey:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _BOND_MATCH_KEYS, location=location)
    return CanonicalBondEnvironmentMatchKey(
        environment_i=_require_string(
            row["environment_i"],
            location=f"{location}.environment_i",
        ),
        environment_j=_require_string(
            row["environment_j"],
            location=f"{location}.environment_j",
        ),
    )


def _parse_angle_match_key(
    value: Any,
    *,
    location: str,
) -> CanonicalAngleEnvironmentMatchKey:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _ANGLE_MATCH_KEYS, location=location)
    return CanonicalAngleEnvironmentMatchKey(
        outer_environment_i=_require_string(
            row["outer_environment_i"],
            location=f"{location}.outer_environment_i",
        ),
        center_environment=_require_string(
            row["center_environment"],
            location=f"{location}.center_environment",
        ),
        outer_environment_k=_require_string(
            row["outer_environment_k"],
            location=f"{location}.outer_environment_k",
        ),
    )


def _parse_proper_match_key(
    value: Any,
    *,
    location: str,
) -> CanonicalProperEnvironmentMatchKey:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _PROPER_MATCH_KEYS, location=location)
    return CanonicalProperEnvironmentMatchKey(
        environment_i=_require_string(
            row["environment_i"],
            location=f"{location}.environment_i",
        ),
        environment_j=_require_string(
            row["environment_j"],
            location=f"{location}.environment_j",
        ),
        environment_k=_require_string(
            row["environment_k"],
            location=f"{location}.environment_k",
        ),
        environment_l=_require_string(
            row["environment_l"],
            location=f"{location}.environment_l",
        ),
    )


def _parse_bond_rule(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneBondParameterRule:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _BOND_RULE_KEYS, location=location)
    return LinearAlkaneBondParameterRule(
        match_key=_parse_bond_match_key(
            row["match_key"],
            location=f"{location}.match_key",
        ),
        parameter_id=_require_string(
            row["parameter_id"],
            location=f"{location}.parameter_id",
        ),
        equilibrium_length_angstrom=_binary64_from_hex(
            f"{location}.equilibrium_length_angstrom_binary64",
            row["equilibrium_length_angstrom_binary64"],
        ),
        force_constant_kilojoule_per_mole_per_angstrom2=_binary64_from_hex(
            (
                f"{location}."
                "force_constant_kilojoule_per_mole_per_angstrom2_binary64"
            ),
            row[
                "force_constant_kilojoule_per_mole_per_angstrom2_binary64"
            ],
        ),
    )


def _parse_angle_rule(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneAngleParameterRule:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _ANGLE_RULE_KEYS, location=location)
    return LinearAlkaneAngleParameterRule(
        match_key=_parse_angle_match_key(
            row["match_key"],
            location=f"{location}.match_key",
        ),
        parameter_id=_require_string(
            row["parameter_id"],
            location=f"{location}.parameter_id",
        ),
        equilibrium_angle_radian=_binary64_from_hex(
            f"{location}.equilibrium_angle_radian_binary64",
            row["equilibrium_angle_radian_binary64"],
        ),
        force_constant_kilojoule_per_mole_per_radian2=_binary64_from_hex(
            (
                f"{location}."
                "force_constant_kilojoule_per_mole_per_radian2_binary64"
            ),
            row[
                "force_constant_kilojoule_per_mole_per_radian2_binary64"
            ],
        ),
    )


def _parse_proper_component(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneProperTorsionComponent:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _PROPER_COMPONENT_KEYS, location=location)
    return LinearAlkaneProperTorsionComponent(
        periodicity=_require_integer(
            row["periodicity"],
            location=f"{location}.periodicity",
        ),
        phase_radian=_binary64_from_hex(
            f"{location}.phase_radian_binary64",
            row["phase_radian_binary64"],
        ),
        amplitude_kilojoule_per_mole=_binary64_from_hex(
            f"{location}.amplitude_kilojoule_per_mole_binary64",
            row["amplitude_kilojoule_per_mole_binary64"],
        ),
    )


def _parse_proper_rule(
    value: Any,
    *,
    location: str,
) -> LinearAlkaneProperParameterRule:
    row = _require_mapping(value, location=location)
    _require_exact_keys(row, _PROPER_RULE_KEYS, location=location)
    components = _require_list(
        row["components"],
        location=f"{location}.components",
    )
    return LinearAlkaneProperParameterRule(
        match_key=_parse_proper_match_key(
            row["match_key"],
            location=f"{location}.match_key",
        ),
        parameter_id=_require_string(
            row["parameter_id"],
            location=f"{location}.parameter_id",
        ),
        components=tuple(
            _parse_proper_component(
                component,
                location=f"{location}.components[{index}]",
            )
            for index, component in enumerate(components)
        ),
    )


def serialize_linear_alkane_c1_c4_parameter_set(
    parameter_set: LinearAlkaneC1C4ParameterSet,
) -> bytes:
    """Serialize an exact validated parameter artifact to canonical ASCII JSON."""

    if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
        raise TypeError("parameter_set must be an exact parameter set")
    parameter_set._validate()
    return _canonical_json_bytes(parameter_set.to_dict())


def deserialize_linear_alkane_c1_c4_parameter_set(
    data: bytes,
) -> LinearAlkaneC1C4ParameterSet:
    """Parse strict canonical parameter JSON and recompute every binding."""

    if type(data) is not bytes:
        raise LinearAlkaneParameterSerializationError(
            "parameter artifact must be exact bytes"
        )
    if len(data) > _MAX_ARTIFACT_BYTES:
        raise LinearAlkaneParameterSerializationError(
            "parameter artifact exceeds the one-megabyte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LinearAlkaneParameterSerializationError(
            "parameter artifact must be ASCII"
        ) from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except LinearAlkaneParameterSerializationError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise LinearAlkaneParameterSerializationError(
            f"invalid parameter JSON: {exc}"
        ) from exc
    root = _require_mapping(document, location="root")
    _require_exact_keys(root, _ROOT_KEYS, location="root")
    payload = _require_mapping(
        root["parameter_payload"],
        location="parameter_payload",
    )
    _require_exact_keys(payload, _PAYLOAD_KEYS, location="parameter_payload")
    for name in ("improper_parameters", "constraint_parameters"):
        if _require_list(payload[name], location=f"parameter_payload.{name}"):
            raise LinearAlkaneParameterSerializationError(
                f"parameter_payload.{name} must remain empty"
            )
    environment_rows = _require_list(
        payload["environment_mappings"],
        location="parameter_payload.environment_mappings",
    )
    lj_rows = _require_list(
        payload["lj_type_parameters"],
        location="parameter_payload.lj_type_parameters",
    )
    charge_rows = _require_list(
        payload["charge_parameters"],
        location="parameter_payload.charge_parameters",
    )
    override_rows = _require_list(
        payload["lj_pair_overrides"],
        location="parameter_payload.lj_pair_overrides",
    )
    bond_rows = _require_list(
        payload["bond_rules"],
        location="parameter_payload.bond_rules",
    )
    angle_rows = _require_list(
        payload["angle_rules"],
        location="parameter_payload.angle_rules",
    )
    proper_rows = _require_list(
        payload["proper_rules"],
        location="parameter_payload.proper_rules",
    )
    try:
        result = LinearAlkaneC1C4ParameterSet(
            parameter_set_id=_require_string(
                root["parameter_set_id"],
                location="parameter_set_id",
            ),
            parameter_set_version=_require_string(
                root["parameter_set_version"],
                location="parameter_set_version",
            ),
            charge_model_id=_require_string(
                payload["charge_model_id"],
                location="parameter_payload.charge_model_id",
            ),
            environment_mappings=tuple(
                _parse_environment_mapping(
                    row,
                    location=f"parameter_payload.environment_mappings[{index}]",
                )
                for index, row in enumerate(environment_rows)
            ),
            lj_type_parameters=tuple(
                _parse_lj_type(
                    row,
                    location=f"parameter_payload.lj_type_parameters[{index}]",
                )
                for index, row in enumerate(lj_rows)
            ),
            charge_parameters=tuple(
                _parse_charge(
                    row,
                    location=f"parameter_payload.charge_parameters[{index}]",
                )
                for index, row in enumerate(charge_rows)
            ),
            lj_pair_overrides=tuple(
                _parse_lj_override(
                    row,
                    location=f"parameter_payload.lj_pair_overrides[{index}]",
                )
                for index, row in enumerate(override_rows)
            ),
            bond_rules=tuple(
                _parse_bond_rule(
                    row,
                    location=f"parameter_payload.bond_rules[{index}]",
                )
                for index, row in enumerate(bond_rows)
            ),
            angle_rules=tuple(
                _parse_angle_rule(
                    row,
                    location=f"parameter_payload.angle_rules[{index}]",
                )
                for index, row in enumerate(angle_rows)
            ),
            proper_rules=tuple(
                _parse_proper_rule(
                    row,
                    location=f"parameter_payload.proper_rules[{index}]",
                )
                for index, row in enumerate(proper_rows)
            ),
            one_four_lj_energy_scale=_binary64_from_hex(
                "parameter_payload.one_four_lj_energy_scale_binary64",
                payload["one_four_lj_energy_scale_binary64"],
            ),
            one_four_coulomb_energy_scale=_binary64_from_hex(
                "parameter_payload.one_four_coulomb_energy_scale_binary64",
                payload["one_four_coulomb_energy_scale_binary64"],
            ),
            parameter_source_sha256=root["parameter_source_sha256"],
            dataset_manifest_sha256=root["dataset_manifest_sha256"],
            split_manifest_sha256=root["split_manifest_sha256"],
            fit_protocol_sha256=root["fit_protocol_sha256"],
            fit_receipt_sha256=root["fit_receipt_sha256"],
            scientific_review_sha256=root["scientific_review_sha256"],
            license_review_sha256=root["license_review_sha256"],
            release_attestation_sha256=root["release_attestation_sha256"],
            reference_nonbonded_method_id=payload[
                "reference_nonbonded_method_id"
            ],
        )
    except LinearAlkaneParameterSerializationError:
        raise
    except (TypeError, ValueError, KeyError, OverflowError) as exc:
        raise LinearAlkaneParameterSerializationError(
            f"parameter contract validation failed: {exc}"
        ) from exc
    canonical = serialize_linear_alkane_c1_c4_parameter_set(result)
    if canonical != data:
        raise LinearAlkaneParameterSerializationError(
            "parameter artifact is noncanonical, stale, or tampered"
        )
    return result


__all__ = [
    "LINEAR_ALKANE_BINARY64_ENCODING_ID",
    "LINEAR_ALKANE_CHARGE_ASSIGNMENT_POLICY_ID",
    "LINEAR_ALKANE_CHARGE_BALANCE_TOLERANCE_E",
    "LINEAR_ALKANE_CHARGE_SUM_POLICY_ID",
    "LINEAR_ALKANE_COULOMB_BASE_FORM_ID",
    "LINEAR_ALKANE_FORCE_FIELD_TYPE_POLICY_ID",
    "LINEAR_ALKANE_FORCE_FIELD_UNIT_SYSTEM_ID",
    "LINEAR_ALKANE_LJ_COMBINING_RULE_ID",
    "LINEAR_ALKANE_LJ_FUNCTIONAL_FORM_ID",
    "LINEAR_ALKANE_LJ_OVERRIDE_POLICY_ID",
    "LINEAR_ALKANE_PARAMETER_ANGLE_KEYS",
    "LINEAR_ALKANE_PARAMETER_ASSIGNMENT_POLICY_ID",
    "LINEAR_ALKANE_PARAMETER_BOND_KEYS",
    "LINEAR_ALKANE_PARAMETER_DOMAIN_ID",
    "LINEAR_ALKANE_PARAMETER_ENVIRONMENT_IDS",
    "LINEAR_ALKANE_PARAMETER_PROPER_KEYS",
    "LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_ID",
    "LINEAR_ALKANE_PARAMETER_PROTOCOL_SCHEMA_VERSION",
    "LINEAR_ALKANE_PARAMETER_PROTOCOL_SHA256",
    "LINEAR_ALKANE_PARAMETER_SCOPE",
    "LINEAR_ALKANE_PARAMETER_SET_SCHEMA_ID",
    "LINEAR_ALKANE_PARAMETER_SET_SCHEMA_VERSION",
    "LINEAR_ALKANE_PROPER_COORDINATE_CONVENTION_ID",
    "LINEAR_ALKANE_PROPER_FUNCTIONAL_FORM_ID",
    "LinearAlkaneAngleParameterRule",
    "LinearAlkaneBondParameterRule",
    "LinearAlkaneC1C4ParameterSet",
    "LinearAlkaneEnvironmentParameterMapping",
    "LinearAlkaneLennardJonesPairOverride",
    "LinearAlkaneLennardJonesTypeParameter",
    "LinearAlkaneParameterContractError",
    "LinearAlkaneParameterSerializationError",
    "LinearAlkanePartialChargeParameter",
    "LinearAlkaneProperParameterRule",
    "LinearAlkaneProperTorsionComponent",
    "ResolvedLinearAlkaneLennardJonesPair",
    "deserialize_linear_alkane_c1_c4_parameter_set",
    "linear_alkane_parameter_protocol_bytes",
    "linear_alkane_parameter_protocol_document",
    "resolve_linear_alkane_lj_pair",
    "serialize_linear_alkane_c1_c4_parameter_set",
]
