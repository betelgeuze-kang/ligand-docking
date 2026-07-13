"""Snapshot-bound C1-C4 contract-fixture parameter assignments.

This module maps the bounded explicit-H neutral linear-alkane topology to a
fully enumerated, deliberately nonphysical parameter fixture.  It resolves
identities, values, charges, Lennard-Jones pairs, and 1-4 scales, but it never
evaluates an energy, force, virial, minimization step, or simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import struct
from typing import Any

from betelgeuze_engine_v2.molecular.alkane_forcefield_applicability import (
    LinearAlkaneC1C4ForceFieldApplicabilityReport,
    analyze_linear_alkane_c1_c4_force_field_applicability,
)
from betelgeuze_engine_v2.molecular.bonded_inventory import (
    CanonicalAngleIdentity,
    CanonicalBondIdentity,
)
from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)

from .linear_alkane_parameters import (
    LinearAlkaneC1C4ParameterSet,
    LinearAlkaneProperTorsionComponent,
    deserialize_linear_alkane_c1_c4_parameter_set,
    resolve_linear_alkane_lj_pair,
    serialize_linear_alkane_c1_c4_parameter_set,
)
from .term_inventory import (
    CanonicalAngleEnvironmentMatchKey,
    CanonicalBondEnvironmentMatchKey,
    CanonicalPairIdentity,
    CanonicalProperEnvironmentMatchKey,
    CanonicalProperTorsionIdentity,
    LinearAlkaneTermPairInventoryReport,
    analyze_linear_alkane_term_pair_inventory,
)
from .typing import (
    LinearAlkaneTopologicalEnvironmentTypingReport,
    analyze_linear_alkane_topological_environment_typing,
)


_FROZEN_SCHEMA_VERSION = "1.0.0"
_FROZEN_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_assignment/"
    f"{_FROZEN_SCHEMA_VERSION}"
)
_FROZEN_ASSIGNMENT_POLICY_ID = (
    "fresh_snapshot_exact_environment_term_and_pair_parameter_mapping/1.0.0"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_nonphysical_contract_fixture_mapping_only_no_evaluation"
)
_FROZEN_ASSIGNMENT_STATUSES = frozenset(
    {"invalid_system", "unsupported_system", "contract_fixture_mapped"}
)
_FROZEN_APPLICABILITY_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_force_field_applicability/1.0.0"
)
_FROZEN_TYPING_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_topological_environment_typing/1.0.0"
)
_FROZEN_INVENTORY_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_term_pair_inventory/1.0.0"
)
_FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_protocol/1.0.0"
)
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0"
)
_FROZEN_PARAMETER_SCOPE = "bounded_c1_c4_full_parameter_contract_fixture_only"
_FROZEN_PARAMETER_DOMAIN_ID = (
    "source_explicit_h_sdf_v2000_linear_alkane_c1_c4_exact_keys/1.0.0"
)
_FROZEN_FORCE_FIELD_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian_elementary_charge/1.0.0"
)
_FROZEN_PAIR_CLASSIFICATION_POLICY_ID = (
    "covalent_shortest_graph_distance_1_2_excluded_1_3_excluded_"
    "1_4_separate_farther_full_v1"
)
_FROZEN_CHARGE_SUM_POLICY_ID = (
    "ascending_environment_then_repeated_count_math_fsum_binary64/1.0.0"
)
_FROZEN_CHARGE_BALANCE_TOLERANCE_E = 1.0e-12
_FROZEN_PAIR_CLASSES = (
    "excluded_1_2",
    "excluded_1_3",
    "one_four_separate",
    "full_nonbonded",
)
_MAX_JSON_INTEGER = (1 << 53) - 1
_IDENTIFIER_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*\Z")
_FROZEN_CONSTRAINT_CODES = (
    "coordinate_unit_angstrom",
    "upstream_applicability_available",
    "upstream_typing_available",
    "upstream_inventory_available",
    "exact_atom_index_set_mapped",
    "exact_bond_identity_set_mapped",
    "exact_angle_identity_set_mapped",
    "exact_proper_identity_set_mapped",
    "exact_pair_identity_set_mapped",
    "excluded_pairs_unresolved",
    "nonexcluded_pairs_mapped_method_deferred",
    "component_partial_charge_balanced",
)

LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_VERSION = _FROZEN_SCHEMA_VERSION
LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_ID = _FROZEN_SCHEMA_ID
LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_POLICY_ID = (
    _FROZEN_ASSIGNMENT_POLICY_ID
)
LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE
LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_STATUSES = _FROZEN_ASSIGNMENT_STATUSES


class LinearAlkaneParameterAssignmentContractError(ValueError):
    """Raised when a bounded assignment cannot be reproduced exactly."""


def _canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise LinearAlkaneParameterAssignmentContractError(
            f"assignment report is not canonical JSON: {exc}"
        ) from exc


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TypeError(f"{name} must be an exact lowercase SHA-256 digest")
    return value


def _require_identifier(name: str, value: Any) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be an exact string")
    if _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be a non-empty canonical identifier")
    return value


def _require_index(name: str, value: Any) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer")
    if value < 0 or value > _MAX_JSON_INTEGER:
        raise ValueError(f"{name} must be an interoperable non-negative index")
    return value


def _require_finite_float(
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
    _require_finite_float("binary64 value", value)
    return struct.pack(">d", value).hex()


def _optional_binary64_hex(value: float | None) -> str | None:
    return None if value is None else _binary64_hex(value)


def _interaction_class(distance: int | None) -> str:
    if distance == 1:
        return "excluded_1_2"
    if distance == 2:
        return "excluded_1_3"
    if distance == 3:
        return "one_four_separate"
    return "full_nonbonded"


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneAtomParameterAssignment:
    atom_index: int
    element: str
    topological_environment_id: str
    force_field_type_id: str
    charge_parameter_id: str
    partial_charge_e: float
    lj_sigma_angstrom: float
    lj_epsilon_kilojoule_per_mole: float

    def __post_init__(self) -> None:
        _require_index("atom_index", self.atom_index)
        if type(self.element) is not str:
            raise TypeError("element must be an exact string")
        if self.element not in {"C", "H"}:
            raise ValueError("element must be C or H")
        _require_identifier(
            "topological_environment_id",
            self.topological_environment_id,
        )
        _require_identifier("force_field_type_id", self.force_field_type_id)
        _require_identifier("charge_parameter_id", self.charge_parameter_id)
        _require_finite_float("partial_charge_e", self.partial_charge_e)
        _require_finite_float(
            "lj_sigma_angstrom",
            self.lj_sigma_angstrom,
            positive=True,
        )
        _require_finite_float(
            "lj_epsilon_kilojoule_per_mole",
            self.lj_epsilon_kilojoule_per_mole,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        LinearAlkaneAtomParameterAssignment.__post_init__(self)
        return {
            "atom_index": self.atom_index,
            "element": self.element,
            "topological_environment_id": self.topological_environment_id,
            "force_field_type_id": self.force_field_type_id,
            "charge_parameter_id": self.charge_parameter_id,
            "partial_charge_e_binary64": _binary64_hex(self.partial_charge_e),
            "lj_sigma_angstrom_binary64": _binary64_hex(
                self.lj_sigma_angstrom
            ),
            "lj_epsilon_kilojoule_per_mole_binary64": _binary64_hex(
                self.lj_epsilon_kilojoule_per_mole
            ),
            "value_source": "declared_nonphysical_contract_fixture_row",
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkaneBondParameterAssignment:
    identity: CanonicalBondIdentity
    match_key: CanonicalBondEnvironmentMatchKey
    parameter_id: str
    equilibrium_length_angstrom: float
    force_constant_kilojoule_per_mole_per_angstrom2: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalBondIdentity:
            raise TypeError("identity must be an exact canonical bond identity")
        CanonicalBondIdentity.__post_init__(self.identity)
        if type(self.match_key) is not CanonicalBondEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical bond key")
        CanonicalBondEnvironmentMatchKey.__post_init__(self.match_key)
        _require_identifier("parameter_id", self.parameter_id)
        _require_finite_float(
            "equilibrium_length_angstrom",
            self.equilibrium_length_angstrom,
            positive=True,
        )
        _require_finite_float(
            "force_constant_kilojoule_per_mole_per_angstrom2",
            self.force_constant_kilojoule_per_mole_per_angstrom2,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        LinearAlkaneBondParameterAssignment.__post_init__(self)
        return {
            "identity": self.identity.to_dict(),
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
class LinearAlkaneAngleParameterAssignment:
    identity: CanonicalAngleIdentity
    match_key: CanonicalAngleEnvironmentMatchKey
    parameter_id: str
    equilibrium_angle_radian: float
    force_constant_kilojoule_per_mole_per_radian2: float

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalAngleIdentity:
            raise TypeError("identity must be an exact canonical angle identity")
        CanonicalAngleIdentity.__post_init__(self.identity)
        if type(self.match_key) is not CanonicalAngleEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical angle key")
        CanonicalAngleEnvironmentMatchKey.__post_init__(self.match_key)
        _require_identifier("parameter_id", self.parameter_id)
        angle = _require_finite_float(
            "equilibrium_angle_radian",
            self.equilibrium_angle_radian,
            positive=True,
        )
        if angle >= math.pi:
            raise ValueError("equilibrium_angle_radian must be below pi")
        _require_finite_float(
            "force_constant_kilojoule_per_mole_per_radian2",
            self.force_constant_kilojoule_per_mole_per_radian2,
            positive=True,
        )

    def to_dict(self) -> dict[str, Any]:
        LinearAlkaneAngleParameterAssignment.__post_init__(self)
        return {
            "identity": self.identity.to_dict(),
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
class LinearAlkaneProperParameterAssignment:
    identity: CanonicalProperTorsionIdentity
    match_key: CanonicalProperEnvironmentMatchKey
    parameter_id: str
    components: tuple[LinearAlkaneProperTorsionComponent, ...]

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalProperTorsionIdentity:
            raise TypeError("identity must be an exact canonical proper identity")
        CanonicalProperTorsionIdentity.__post_init__(self.identity)
        if type(self.match_key) is not CanonicalProperEnvironmentMatchKey:
            raise TypeError("match_key must be an exact canonical proper key")
        CanonicalProperEnvironmentMatchKey.__post_init__(self.match_key)
        _require_identifier("parameter_id", self.parameter_id)
        if type(self.components) is not tuple or not self.components:
            raise TypeError("components must be a non-empty exact tuple")
        if not all(
            type(component) is LinearAlkaneProperTorsionComponent
            for component in self.components
        ):
            raise TypeError("components must contain exact torsion components")
        for component in self.components:
            LinearAlkaneProperTorsionComponent.__post_init__(component)
        if self.components != tuple(sorted(self.components)):
            raise ValueError("components must be canonically sorted")

    def to_dict(self) -> dict[str, Any]:
        LinearAlkaneProperParameterAssignment.__post_init__(self)
        return {
            "identity": self.identity.to_dict(),
            "match_key": self.match_key.to_dict(),
            "parameter_id": self.parameter_id,
            "components": [component.to_dict() for component in self.components],
        }


@dataclass(frozen=True, order=True, slots=True)
class LinearAlkanePairParameterAssignment:
    identity: CanonicalPairIdentity
    shortest_graph_distance: int | None
    interaction_class: str
    parameter_status: str
    atom_i_force_field_type_id: str | None
    atom_j_force_field_type_id: str | None
    atom_i_charge_parameter_id: str | None
    atom_j_charge_parameter_id: str | None
    atom_i_partial_charge_e: float | None
    atom_j_partial_charge_e: float | None
    resolved_lj_type_i: str | None
    resolved_lj_type_j: str | None
    lj_sigma_angstrom: float | None
    lj_epsilon_kilojoule_per_mole: float | None
    lj_resolution_status: str | None
    lj_override_id: str | None
    lj_energy_scale: float | None
    coulomb_energy_scale: float | None

    def __post_init__(self) -> None:
        if type(self.identity) is not CanonicalPairIdentity:
            raise TypeError("identity must be an exact canonical pair identity")
        CanonicalPairIdentity.__post_init__(self.identity)
        if self.shortest_graph_distance is not None:
            distance = _require_index(
                "shortest_graph_distance",
                self.shortest_graph_distance,
            )
            if distance < 1:
                raise ValueError("shortest_graph_distance must be positive")
        if type(self.interaction_class) is not str:
            raise TypeError("interaction_class must be an exact string")
        if self.interaction_class not in _FROZEN_PAIR_CLASSES:
            raise ValueError("unknown interaction_class")
        if self.interaction_class != _interaction_class(
            self.shortest_graph_distance
        ):
            raise ValueError("interaction_class must match graph distance")
        if type(self.parameter_status) is not str:
            raise TypeError("parameter_status must be an exact string")
        if self.parameter_status not in {
            "excluded_no_parameter_mapping",
            "mapped_nonphysical_contract_fixture_method_deferred",
        }:
            raise ValueError("unknown pair parameter_status")
        resolved_parameter_values = (
            self.atom_i_force_field_type_id,
            self.atom_j_force_field_type_id,
            self.atom_i_charge_parameter_id,
            self.atom_j_charge_parameter_id,
            self.atom_i_partial_charge_e,
            self.atom_j_partial_charge_e,
            self.resolved_lj_type_i,
            self.resolved_lj_type_j,
            self.lj_sigma_angstrom,
            self.lj_epsilon_kilojoule_per_mole,
            self.lj_resolution_status,
        )
        excluded = self.interaction_class in {"excluded_1_2", "excluded_1_3"}
        if excluded:
            if self.parameter_status != "excluded_no_parameter_mapping":
                raise ValueError("excluded pairs cannot resolve parameters")
            if any(value is not None for value in resolved_parameter_values) or (
                self.lj_override_id is not None
                or self.lj_energy_scale is not None
                or self.coulomb_energy_scale is not None
            ):
                raise ValueError("excluded pairs must not carry pair parameters")
            return
        if (
            self.parameter_status
            != "mapped_nonphysical_contract_fixture_method_deferred"
        ):
            raise ValueError("non-excluded pairs must resolve the fixture")
        if any(value is None for value in resolved_parameter_values):
            raise ValueError("resolved pairs must carry every required field")
        for name in (
            "atom_i_force_field_type_id",
            "atom_j_force_field_type_id",
            "atom_i_charge_parameter_id",
            "atom_j_charge_parameter_id",
            "resolved_lj_type_i",
            "resolved_lj_type_j",
        ):
            _require_identifier(name, getattr(self, name))
        if (
            self.resolved_lj_type_i,
            self.resolved_lj_type_j,
        ) != tuple(
            sorted(
                (
                    self.atom_i_force_field_type_id,
                    self.atom_j_force_field_type_id,
                )
            )
        ):
            raise ValueError(
                "resolved LJ types must canonically match endpoint types"
            )
        _require_finite_float(
            "atom_i_partial_charge_e",
            self.atom_i_partial_charge_e,
        )
        _require_finite_float(
            "atom_j_partial_charge_e",
            self.atom_j_partial_charge_e,
        )
        _require_finite_float(
            "lj_sigma_angstrom",
            self.lj_sigma_angstrom,
            positive=True,
        )
        _require_finite_float(
            "lj_epsilon_kilojoule_per_mole",
            self.lj_epsilon_kilojoule_per_mole,
            positive=True,
        )
        if type(self.lj_resolution_status) is not str:
            raise TypeError("lj_resolution_status must be an exact string")
        if self.lj_resolution_status not in {
            "lorentz_berthelot",
            "exact_pair_override",
        }:
            raise ValueError("unknown lj_resolution_status")
        if self.lj_resolution_status == "exact_pair_override":
            _require_identifier("lj_override_id", self.lj_override_id)
        elif self.lj_override_id is not None:
            raise ValueError("combined LJ pairs cannot carry an override ID")
        if self.interaction_class == "one_four_separate":
            lj_scale = _require_finite_float(
                "lj_energy_scale",
                self.lj_energy_scale,
                nonnegative=True,
            )
            coulomb_scale = _require_finite_float(
                "coulomb_energy_scale",
                self.coulomb_energy_scale,
                nonnegative=True,
            )
            if lj_scale > 1.0 or coulomb_scale > 1.0:
                raise ValueError("1-4 energy scales must not exceed one")
        elif (
            self.lj_energy_scale is not None
            or self.coulomb_energy_scale is not None
        ):
            raise ValueError("full nonbonded pairs do not carry 1-4 scales")

    def to_dict(self) -> dict[str, Any]:
        LinearAlkanePairParameterAssignment.__post_init__(self)
        return {
            "identity": self.identity.to_dict(),
            "shortest_graph_distance": self.shortest_graph_distance,
            "interaction_class": self.interaction_class,
            "parameter_status": self.parameter_status,
            "atom_i_force_field_type_id": self.atom_i_force_field_type_id,
            "atom_j_force_field_type_id": self.atom_j_force_field_type_id,
            "atom_i_charge_parameter_id": self.atom_i_charge_parameter_id,
            "atom_j_charge_parameter_id": self.atom_j_charge_parameter_id,
            "atom_i_partial_charge_e_binary64": _optional_binary64_hex(
                self.atom_i_partial_charge_e
            ),
            "atom_j_partial_charge_e_binary64": _optional_binary64_hex(
                self.atom_j_partial_charge_e
            ),
            "resolved_lj_type_i": self.resolved_lj_type_i,
            "resolved_lj_type_j": self.resolved_lj_type_j,
            "lj_sigma_angstrom_binary64": _optional_binary64_hex(
                self.lj_sigma_angstrom
            ),
            "lj_epsilon_kilojoule_per_mole_binary64": (
                _optional_binary64_hex(self.lj_epsilon_kilojoule_per_mole)
            ),
            "lj_resolution_status": self.lj_resolution_status,
            "lj_override_id": self.lj_override_id,
            "lj_energy_scale_binary64": _optional_binary64_hex(
                self.lj_energy_scale
            ),
            "coulomb_energy_scale_binary64": _optional_binary64_hex(
                self.coulomb_energy_scale
            ),
        }


@dataclass(frozen=True, slots=True)
class _ComputedParameterAssignment:
    system: AllAtomSystem
    parameter_set: LinearAlkaneC1C4ParameterSet
    applicability: LinearAlkaneC1C4ForceFieldApplicabilityReport
    typing_report: LinearAlkaneTopologicalEnvironmentTypingReport
    inventory: LinearAlkaneTermPairInventoryReport
    assignment_status: str
    atom_assignments: tuple[LinearAlkaneAtomParameterAssignment, ...]
    bond_assignments: tuple[LinearAlkaneBondParameterAssignment, ...]
    angle_assignments: tuple[LinearAlkaneAngleParameterAssignment, ...]
    proper_assignments: tuple[LinearAlkaneProperParameterAssignment, ...]
    pair_assignments: tuple[LinearAlkanePairParameterAssignment, ...]
    component_partial_charge_sum_e: float | None


def _dependency_document(report: Any, schema_id: str, name: str) -> dict[str, Any]:
    document = report.to_dict()
    if type(document) is not dict or document.get("schema_id") != schema_id:
        raise LinearAlkaneParameterAssignmentContractError(
            f"{name} dependency schema binding is inconsistent"
        )
    _require_sha256(f"{name}.report_sha256", document.get("report_sha256"))
    return document


def _derive_assignments(
    system: AllAtomSystem,
    parameter_set: LinearAlkaneC1C4ParameterSet,
    typing_report: LinearAlkaneTopologicalEnvironmentTypingReport,
    inventory: LinearAlkaneTermPairInventoryReport,
) -> tuple[
    tuple[LinearAlkaneAtomParameterAssignment, ...],
    tuple[LinearAlkaneBondParameterAssignment, ...],
    tuple[LinearAlkaneAngleParameterAssignment, ...],
    tuple[LinearAlkaneProperParameterAssignment, ...],
    tuple[LinearAlkanePairParameterAssignment, ...],
    float,
]:
    if system.coordinate_unit != "angstrom":
        raise LinearAlkaneParameterAssignmentContractError(
            "bounded parameter assignment requires angstrom coordinates"
        )
    mapping_by_environment = {
        row.topological_environment_id: row
        for row in parameter_set.environment_mappings
    }
    lj_by_type = {
        row.force_field_type_id: row for row in parameter_set.lj_type_parameters
    }
    charge_by_id = {
        row.charge_parameter_id: row for row in parameter_set.charge_parameters
    }
    atom_by_index = {atom.index: atom for atom in system.atoms}
    if tuple(sorted(atom_by_index)) != tuple(range(system.atom_count)):
        raise LinearAlkaneParameterAssignmentContractError(
            "system atoms must have contiguous canonical indices"
        )
    atom_assignments: list[LinearAlkaneAtomParameterAssignment] = []
    for typing_assignment in typing_report.environment_assignments:
        try:
            mapping = mapping_by_environment[
                typing_assignment.topological_environment_id
            ]
            lj = lj_by_type[mapping.force_field_type_id]
            charge = charge_by_id[mapping.charge_parameter_id]
            atom = atom_by_index[typing_assignment.atom_index]
        except KeyError as exc:
            raise LinearAlkaneParameterAssignmentContractError(
                "atom environment mapping is incomplete"
            ) from exc
        atom_assignments.append(
            LinearAlkaneAtomParameterAssignment(
                atom_index=typing_assignment.atom_index,
                element=atom.element,
                topological_environment_id=(
                    typing_assignment.topological_environment_id
                ),
                force_field_type_id=mapping.force_field_type_id,
                charge_parameter_id=mapping.charge_parameter_id,
                partial_charge_e=charge.partial_charge_e,
                lj_sigma_angstrom=lj.sigma_angstrom,
                lj_epsilon_kilojoule_per_mole=(
                    lj.epsilon_kilojoule_per_mole
                ),
            )
        )
    atom_rows = tuple(atom_assignments)
    if tuple(row.atom_index for row in atom_rows) != tuple(
        range(system.atom_count)
    ):
        raise LinearAlkaneParameterAssignmentContractError(
            "atom assignments must cover the exact atom set in index order"
        )

    bond_by_key = {row.match_key: row for row in parameter_set.bond_rules}
    angle_by_key = {row.match_key: row for row in parameter_set.angle_rules}
    proper_by_key = {row.match_key: row for row in parameter_set.proper_rules}
    try:
        bond_rows = tuple(
            LinearAlkaneBondParameterAssignment(
                identity=term.identity,
                match_key=term.match_key,
                parameter_id=bond_by_key[term.match_key].parameter_id,
                equilibrium_length_angstrom=(
                    bond_by_key[term.match_key].equilibrium_length_angstrom
                ),
                force_constant_kilojoule_per_mole_per_angstrom2=(
                    bond_by_key[
                        term.match_key
                    ].force_constant_kilojoule_per_mole_per_angstrom2
                ),
            )
            for term in inventory.bond_terms
        )
        angle_rows = tuple(
            LinearAlkaneAngleParameterAssignment(
                identity=term.identity,
                match_key=term.match_key,
                parameter_id=angle_by_key[term.match_key].parameter_id,
                equilibrium_angle_radian=(
                    angle_by_key[term.match_key].equilibrium_angle_radian
                ),
                force_constant_kilojoule_per_mole_per_radian2=(
                    angle_by_key[
                        term.match_key
                    ].force_constant_kilojoule_per_mole_per_radian2
                ),
            )
            for term in inventory.angle_terms
        )
        proper_rows = tuple(
            LinearAlkaneProperParameterAssignment(
                identity=term.identity,
                match_key=term.match_key,
                parameter_id=proper_by_key[term.match_key].parameter_id,
                components=proper_by_key[term.match_key].components,
            )
            for term in inventory.proper_terms
        )
    except KeyError as exc:
        raise LinearAlkaneParameterAssignmentContractError(
            "bonded term parameter mapping is incomplete"
        ) from exc

    atom_assignment_by_index = {row.atom_index: row for row in atom_rows}
    pair_rows: list[LinearAlkanePairParameterAssignment] = []
    for classification in inventory.pair_classifications:
        identity = classification.identity
        interaction_class = classification.interaction_class
        if interaction_class in {"excluded_1_2", "excluded_1_3"}:
            pair_rows.append(
                LinearAlkanePairParameterAssignment(
                    identity=identity,
                    shortest_graph_distance=(
                        classification.shortest_graph_distance
                    ),
                    interaction_class=interaction_class,
                    parameter_status="excluded_no_parameter_mapping",
                    atom_i_force_field_type_id=None,
                    atom_j_force_field_type_id=None,
                    atom_i_charge_parameter_id=None,
                    atom_j_charge_parameter_id=None,
                    atom_i_partial_charge_e=None,
                    atom_j_partial_charge_e=None,
                    resolved_lj_type_i=None,
                    resolved_lj_type_j=None,
                    lj_sigma_angstrom=None,
                    lj_epsilon_kilojoule_per_mole=None,
                    lj_resolution_status=None,
                    lj_override_id=None,
                    lj_energy_scale=None,
                    coulomb_energy_scale=None,
                )
            )
            continue
        atom_i = atom_assignment_by_index[identity.atom_i]
        atom_j = atom_assignment_by_index[identity.atom_j]
        resolved_lj = resolve_linear_alkane_lj_pair(
            parameter_set,
            atom_i.force_field_type_id,
            atom_j.force_field_type_id,
        )
        if interaction_class == "one_four_separate":
            lj_scale = parameter_set.one_four_lj_energy_scale
            coulomb_scale = parameter_set.one_four_coulomb_energy_scale
        else:
            lj_scale = None
            coulomb_scale = None
        pair_rows.append(
            LinearAlkanePairParameterAssignment(
                identity=identity,
                shortest_graph_distance=classification.shortest_graph_distance,
                interaction_class=interaction_class,
                parameter_status=(
                    "mapped_nonphysical_contract_fixture_method_deferred"
                ),
                atom_i_force_field_type_id=atom_i.force_field_type_id,
                atom_j_force_field_type_id=atom_j.force_field_type_id,
                atom_i_charge_parameter_id=atom_i.charge_parameter_id,
                atom_j_charge_parameter_id=atom_j.charge_parameter_id,
                atom_i_partial_charge_e=atom_i.partial_charge_e,
                atom_j_partial_charge_e=atom_j.partial_charge_e,
                resolved_lj_type_i=resolved_lj.force_field_type_i,
                resolved_lj_type_j=resolved_lj.force_field_type_j,
                lj_sigma_angstrom=resolved_lj.sigma_angstrom,
                lj_epsilon_kilojoule_per_mole=(
                    resolved_lj.epsilon_kilojoule_per_mole
                ),
                lj_resolution_status=resolved_lj.resolution_status,
                lj_override_id=resolved_lj.override_id,
                lj_energy_scale=lj_scale,
                coulomb_energy_scale=coulomb_scale,
            )
        )
    charge_rows_by_environment: dict[str, tuple[float, int]] = {}
    for row in atom_rows:
        previous_charge, previous_count = charge_rows_by_environment.get(
            row.topological_environment_id,
            (row.partial_charge_e, 0),
        )
        if previous_charge != row.partial_charge_e:
            raise LinearAlkaneParameterAssignmentContractError(
                "one environment cannot resolve to multiple partial charges"
            )
        charge_rows_by_environment[row.topological_environment_id] = (
            row.partial_charge_e,
            previous_count + 1,
        )
    try:
        charge_sum = math.fsum(
            charge
            for environment_id in sorted(charge_rows_by_environment)
            for charge, count in (charge_rows_by_environment[environment_id],)
            for _ in range(count)
        )
    except OverflowError as exc:
        raise LinearAlkaneParameterAssignmentContractError(
            "assigned component charge summation overflowed"
        ) from exc
    if abs(charge_sum) > _FROZEN_CHARGE_BALANCE_TOLERANCE_E:
        raise LinearAlkaneParameterAssignmentContractError(
            "assigned component partial charges do not sum to target zero"
        )
    return (
        atom_rows,
        bond_rows,
        angle_rows,
        proper_rows,
        tuple(pair_rows),
        charge_sum,
    )


def _compute(
    system_snapshot: bytes,
    parameter_snapshot: bytes,
) -> _ComputedParameterAssignment:
    system = deserialize_all_atom_system(system_snapshot)
    if serialize_all_atom_system(system) != system_snapshot:
        raise LinearAlkaneParameterAssignmentContractError(
            "stored system snapshot is not canonical"
        )
    parameter_set = deserialize_linear_alkane_c1_c4_parameter_set(
        parameter_snapshot
    )
    if (
        serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
        != parameter_snapshot
    ):
        raise LinearAlkaneParameterAssignmentContractError(
            "stored parameter snapshot is not canonical"
        )
    applicability = analyze_linear_alkane_c1_c4_force_field_applicability(system)
    typing_report = analyze_linear_alkane_topological_environment_typing(system)
    inventory = analyze_linear_alkane_term_pair_inventory(system)
    if type(applicability) is not LinearAlkaneC1C4ForceFieldApplicabilityReport:
        raise TypeError("applicability dependency must be its exact report type")
    if type(typing_report) is not LinearAlkaneTopologicalEnvironmentTypingReport:
        raise TypeError("typing dependency must be its exact report type")
    if type(inventory) is not LinearAlkaneTermPairInventoryReport:
        raise TypeError("inventory dependency must be its exact report type")
    applicability_document = _dependency_document(
        applicability,
        _FROZEN_APPLICABILITY_SCHEMA_ID,
        "applicability",
    )
    typing_document = _dependency_document(
        typing_report,
        _FROZEN_TYPING_SCHEMA_ID,
        "typing",
    )
    inventory_document = _dependency_document(
        inventory,
        _FROZEN_INVENTORY_SCHEMA_ID,
        "inventory",
    )
    system_sha256 = hashlib.sha256(system_snapshot).hexdigest()
    if any(
        document["canonical_system_snapshot_sha256"] != system_sha256
        for document in (
            applicability_document,
            typing_document,
            inventory_document,
        )
    ):
        raise LinearAlkaneParameterAssignmentContractError(
            "upstream reports must bind the exact system snapshot"
        )
    if typing_document["applicability_report_sha256"] != (
        applicability_document["report_sha256"]
    ):
        raise LinearAlkaneParameterAssignmentContractError(
            "typing report must bind the fresh applicability report"
        )
    if inventory_document["applicability_report_sha256"] != (
        applicability_document["report_sha256"]
    ) or inventory_document[
        "topological_environment_typing_report_sha256"
    ] != typing_document["report_sha256"]:
        raise LinearAlkaneParameterAssignmentContractError(
            "inventory report must bind the fresh applicability and typing reports"
        )
    parameter_document = parameter_set.to_dict()
    if parameter_document["schema_id"] != _FROZEN_PARAMETER_SET_SCHEMA_ID:
        raise LinearAlkaneParameterAssignmentContractError(
            "parameter-set schema binding is inconsistent"
        )
    payload = parameter_document["parameter_payload"]
    if payload["protocol_schema_id"] != _FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID:
        raise LinearAlkaneParameterAssignmentContractError(
            "parameter protocol schema binding is inconsistent"
        )
    status_by_inventory = {
        "invalid": "invalid_system",
        "unsupported": "unsupported_system",
        "available": "contract_fixture_mapped",
    }
    try:
        assignment_status = status_by_inventory[inventory.inventory_status]
    except KeyError as exc:
        raise LinearAlkaneParameterAssignmentContractError(
            "unknown upstream inventory status"
        ) from exc
    if assignment_status == "contract_fixture_mapped":
        (
            atom_assignments,
            bond_assignments,
            angle_assignments,
            proper_assignments,
            pair_assignments,
            charge_sum,
        ) = _derive_assignments(
            system,
            parameter_set,
            typing_report,
            inventory,
        )
    else:
        atom_assignments = ()
        bond_assignments = ()
        angle_assignments = ()
        proper_assignments = ()
        pair_assignments = ()
        charge_sum = None
    return _ComputedParameterAssignment(
        system=system,
        parameter_set=parameter_set,
        applicability=applicability,
        typing_report=typing_report,
        inventory=inventory,
        assignment_status=assignment_status,
        atom_assignments=atom_assignments,
        bond_assignments=bond_assignments,
        angle_assignments=angle_assignments,
        proper_assignments=proper_assignments,
        pair_assignments=pair_assignments,
        component_partial_charge_sum_e=charge_sum,
    )


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4ParameterAssignmentReport:
    """Factory-only report that recomputes both bound canonical snapshots."""

    _canonical_system_snapshot: bytes = field(repr=False)
    _canonical_system_snapshot_sha256: str = field(repr=False)
    _canonical_parameter_snapshot: bytes = field(repr=False)
    _canonical_parameter_snapshot_sha256: str = field(repr=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: LinearAlkaneC1C4ParameterSet,
    ) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an exact AllAtomSystem")
        if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
            raise TypeError("parameter_set must be an exact C1-C4 parameter set")
        system_snapshot = serialize_all_atom_system(system)
        parameter_snapshot = serialize_linear_alkane_c1_c4_parameter_set(
            parameter_set
        )
        object.__setattr__(self, "_canonical_system_snapshot", system_snapshot)
        object.__setattr__(
            self,
            "_canonical_system_snapshot_sha256",
            hashlib.sha256(system_snapshot).hexdigest(),
        )
        object.__setattr__(
            self,
            "_canonical_parameter_snapshot",
            parameter_snapshot,
        )
        object.__setattr__(
            self,
            "_canonical_parameter_snapshot_sha256",
            hashlib.sha256(parameter_snapshot).hexdigest(),
        )
        self._validate(_compute(system_snapshot, parameter_snapshot))

    def _validated_snapshots(self) -> tuple[bytes, bytes]:
        system_snapshot = self._canonical_system_snapshot
        parameter_snapshot = self._canonical_parameter_snapshot
        if type(system_snapshot) is not bytes:
            raise TypeError("stored system snapshot must be exact bytes")
        if type(parameter_snapshot) is not bytes:
            raise TypeError("stored parameter snapshot must be exact bytes")
        system_sha256 = _require_sha256(
            "canonical system snapshot digest",
            self._canonical_system_snapshot_sha256,
        )
        parameter_sha256 = _require_sha256(
            "canonical parameter snapshot digest",
            self._canonical_parameter_snapshot_sha256,
        )
        if hashlib.sha256(system_snapshot).hexdigest() != system_sha256:
            raise LinearAlkaneParameterAssignmentContractError(
                "canonical system snapshot digest binding is inconsistent"
            )
        if hashlib.sha256(parameter_snapshot).hexdigest() != parameter_sha256:
            raise LinearAlkaneParameterAssignmentContractError(
                "canonical parameter snapshot digest binding is inconsistent"
            )
        return system_snapshot, parameter_snapshot

    def _validate(
        self,
        analysis: _ComputedParameterAssignment | None = None,
    ) -> None:
        system_snapshot, parameter_snapshot = self._validated_snapshots()
        current = (
            _compute(system_snapshot, parameter_snapshot)
            if analysis is None
            else analysis
        )
        if type(current) is not _ComputedParameterAssignment:
            raise TypeError("analysis must be an exact computed assignment")
        if serialize_all_atom_system(current.system) != system_snapshot:
            raise LinearAlkaneParameterAssignmentContractError(
                "analysis system does not match the stored snapshot"
            )
        if (
            serialize_linear_alkane_c1_c4_parameter_set(current.parameter_set)
            != parameter_snapshot
        ):
            raise LinearAlkaneParameterAssignmentContractError(
                "analysis parameter set does not match the stored snapshot"
            )
        if type(current.assignment_status) is not str:
            raise TypeError("assignment_status must be an exact string")
        if current.assignment_status not in _FROZEN_ASSIGNMENT_STATUSES:
            raise ValueError("unknown assignment_status")
        mapped = current.assignment_status == "contract_fixture_mapped"
        rows = (
            current.atom_assignments,
            current.bond_assignments,
            current.angle_assignments,
            current.proper_assignments,
            current.pair_assignments,
        )
        if not mapped:
            if any(rows) or current.component_partial_charge_sum_e is not None:
                raise LinearAlkaneParameterAssignmentContractError(
                    "unavailable assignment cannot expose mapped rows"
                )
            return
        exact_contracts = (
            (
                current.atom_assignments,
                LinearAlkaneAtomParameterAssignment,
            ),
            (
                current.bond_assignments,
                LinearAlkaneBondParameterAssignment,
            ),
            (
                current.angle_assignments,
                LinearAlkaneAngleParameterAssignment,
            ),
            (
                current.proper_assignments,
                LinearAlkaneProperParameterAssignment,
            ),
            (
                current.pair_assignments,
                LinearAlkanePairParameterAssignment,
            ),
        )
        for values, expected_type in exact_contracts:
            if type(values) is not tuple or not all(
                type(value) is expected_type for value in values
            ):
                raise TypeError(
                    f"assignment rows must be exact {expected_type.__name__} tuples"
                )
            for value in values:
                expected_type.__post_init__(value)
            if values != tuple(sorted(values)):
                raise LinearAlkaneParameterAssignmentContractError(
                    "assignment rows must be canonically sorted"
                )
        expected_assignments = _derive_assignments(
            current.system,
            current.parameter_set,
            current.typing_report,
            current.inventory,
        )
        observed_assignments = (
            current.atom_assignments,
            current.bond_assignments,
            current.angle_assignments,
            current.proper_assignments,
            current.pair_assignments,
            current.component_partial_charge_sum_e,
        )
        if observed_assignments != expected_assignments:
            raise LinearAlkaneParameterAssignmentContractError(
                "assignment rows must exactly equal a fresh parameter mapping"
            )
        if len(current.atom_assignments) != current.system.atom_count:
            raise LinearAlkaneParameterAssignmentContractError(
                "atom assignments must cover every atom"
            )
        if len(current.bond_assignments) != len(current.inventory.bond_terms):
            raise LinearAlkaneParameterAssignmentContractError(
                "bond assignments must cover every inventory bond"
            )
        if len(current.angle_assignments) != len(current.inventory.angle_terms):
            raise LinearAlkaneParameterAssignmentContractError(
                "angle assignments must cover every inventory angle"
            )
        if len(current.proper_assignments) != len(current.inventory.proper_terms):
            raise LinearAlkaneParameterAssignmentContractError(
                "proper assignments must cover every inventory proper"
            )
        if len(current.pair_assignments) != len(
            current.inventory.pair_classifications
        ):
            raise LinearAlkaneParameterAssignmentContractError(
                "pair assignments must cover every inventory pair"
            )
        charge_sum = _require_finite_float(
            "component_partial_charge_sum_e",
            current.component_partial_charge_sum_e,
        )
        if abs(charge_sum) > _FROZEN_CHARGE_BALANCE_TOLERANCE_E:
            raise LinearAlkaneParameterAssignmentContractError(
                "component charge balance must remain within tolerance"
            )

    def _analysis(self) -> _ComputedParameterAssignment:
        snapshots = self._validated_snapshots()
        analysis = _compute(*snapshots)
        self._validate(analysis)
        return analysis

    @property
    def assignment_status(self) -> str:
        return self._analysis().assignment_status

    @property
    def atom_assignments(
        self,
    ) -> tuple[LinearAlkaneAtomParameterAssignment, ...]:
        return self._analysis().atom_assignments

    @property
    def bond_assignments(
        self,
    ) -> tuple[LinearAlkaneBondParameterAssignment, ...]:
        return self._analysis().bond_assignments

    @property
    def angle_assignments(
        self,
    ) -> tuple[LinearAlkaneAngleParameterAssignment, ...]:
        return self._analysis().angle_assignments

    @property
    def proper_assignments(
        self,
    ) -> tuple[LinearAlkaneProperParameterAssignment, ...]:
        return self._analysis().proper_assignments

    @property
    def pair_assignments(
        self,
    ) -> tuple[LinearAlkanePairParameterAssignment, ...]:
        return self._analysis().pair_assignments

    @property
    def component_partial_charge_sum_e(self) -> float | None:
        return self._analysis().component_partial_charge_sum_e

    @property
    def bounded_contract_fixture_assignment_complete(self) -> bool:
        return self.assignment_status == "contract_fixture_mapped"

    def _false_gate(self) -> bool:
        self._analysis()
        return False

    @property
    def evaluation_method_defined(self) -> bool:
        return self._false_gate()

    @property
    def production_parameter_assignment_complete(self) -> bool:
        return self._false_gate()

    @property
    def parameterability_assessed(self) -> bool:
        return self._false_gate()

    @property
    def parameterizable(self) -> bool:
        return self._false_gate()

    @property
    def production_force_field_atom_types_assigned(self) -> bool:
        return self._false_gate()

    @property
    def production_partial_charges_assigned(self) -> bool:
        return self._false_gate()

    @property
    def production_force_field_parameters_assigned(self) -> bool:
        return self._false_gate()

    @property
    def global_parameter_coverage_complete(self) -> bool:
        return self._false_gate()

    @property
    def preparation_ready(self) -> bool:
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

    def _blockers(
        self,
        analysis: _ComputedParameterAssignment,
    ) -> tuple[str, ...]:
        prefix: tuple[str, ...]
        if analysis.assignment_status == "invalid_system":
            prefix = ("bounded_linear_alkane_system_invalid",)
        elif analysis.assignment_status == "unsupported_system":
            prefix = ("bounded_linear_alkane_profile_unsupported",)
        else:
            prefix = ()
        return (
            *prefix,
            "numeric_values_are_nonphysical_contract_fixtures",
            "source_digest_is_binding_not_authentication",
            "scientific_dataset_fit_holdout_and_reference_validation_missing",
            "charge_model_lj_and_bonded_parameters_are_unvalidated",
            "license_review_and_release_attestation_missing",
            "evaluation_method_cutoff_switch_coulomb_pbc_and_long_range_missing",
            "energy_force_virial_kernel_missing",
            "bounded_neutral_linear_c1_c4_only",
            "global_parameter_coverage_missing",
            "preparation_minimization_simulation_and_claim_authority_prohibited",
        )

    def _constraint_results(
        self,
        analysis: _ComputedParameterAssignment,
    ) -> tuple[tuple[str, bool], ...]:
        mapped = analysis.assignment_status == "contract_fixture_mapped"
        pairs = analysis.pair_assignments
        results = (
            ("coordinate_unit_angstrom", analysis.system.coordinate_unit == "angstrom"),
            (
                "upstream_applicability_available",
                analysis.applicability.applicability_status == "available",
            ),
            (
                "upstream_typing_available",
                analysis.typing_report.typing_status == "environments_available",
            ),
            (
                "upstream_inventory_available",
                analysis.inventory.inventory_status == "available",
            ),
            (
                "exact_atom_index_set_mapped",
                mapped
                and tuple(row.atom_index for row in analysis.atom_assignments)
                == tuple(range(analysis.system.atom_count)),
            ),
            (
                "exact_bond_identity_set_mapped",
                mapped
                and tuple(row.identity for row in analysis.bond_assignments)
                == analysis.inventory.bond_identities,
            ),
            (
                "exact_angle_identity_set_mapped",
                mapped
                and tuple(row.identity for row in analysis.angle_assignments)
                == analysis.inventory.angle_identities,
            ),
            (
                "exact_proper_identity_set_mapped",
                mapped
                and tuple(row.identity for row in analysis.proper_assignments)
                == analysis.inventory.proper_identities,
            ),
            (
                "exact_pair_identity_set_mapped",
                mapped
                and tuple(row.identity for row in pairs)
                == tuple(
                    row.identity for row in analysis.inventory.pair_classifications
                ),
            ),
            (
                "excluded_pairs_unresolved",
                mapped
                and all(
                    row.parameter_status == "excluded_no_parameter_mapping"
                    for row in pairs
                    if row.interaction_class in {"excluded_1_2", "excluded_1_3"}
                ),
            ),
            (
                "nonexcluded_pairs_mapped_method_deferred",
                mapped
                and all(
                    row.parameter_status
                    == "mapped_nonphysical_contract_fixture_method_deferred"
                    for row in pairs
                    if row.interaction_class
                    in {"one_four_separate", "full_nonbonded"}
                ),
            ),
            (
                "component_partial_charge_balanced",
                mapped
                and analysis.component_partial_charge_sum_e is not None
                and abs(analysis.component_partial_charge_sum_e)
                <= _FROZEN_CHARGE_BALANCE_TOLERANCE_E,
            ),
        )
        if tuple(code for code, _ in results) != _FROZEN_CONSTRAINT_CODES:
            raise LinearAlkaneParameterAssignmentContractError(
                "assignment constraint schema is inconsistent"
            )
        return results

    @property
    def constraint_results(self) -> tuple[tuple[str, bool], ...]:
        analysis = self._analysis()
        return self._constraint_results(analysis)

    @property
    def failed_constraint_codes(self) -> tuple[str, ...]:
        return tuple(
            code for code, passed in self.constraint_results if not passed
        )

    @property
    def blockers(self) -> tuple[str, ...]:
        analysis = self._analysis()
        return self._blockers(analysis)

    def _assignment_document(
        self,
        analysis: _ComputedParameterAssignment,
    ) -> dict[str, Any] | None:
        if analysis.assignment_status != "contract_fixture_mapped":
            return None
        applicability = analysis.applicability.to_dict()
        typing_document = analysis.typing_report.to_dict()
        inventory = analysis.inventory.to_dict()
        parameter_set = analysis.parameter_set
        constraint_results = self._constraint_results(analysis)
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "charge_sum_policy_id": _FROZEN_CHARGE_SUM_POLICY_ID,
            "canonical_system_snapshot_sha256": (
                self._canonical_system_snapshot_sha256
            ),
            "canonical_topology_sha256": applicability[
                "canonical_topology_sha256"
            ],
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in constraint_results
            ],
            "applicability_report_sha256": applicability["report_sha256"],
            "typing_report_sha256": typing_document["report_sha256"],
            "inventory_report_sha256": inventory["report_sha256"],
            "parameter_protocol_sha256": parameter_set.protocol_sha256,
            "parameter_set_sha256": parameter_set.parameter_set_sha256,
            "parameter_payload_sha256": parameter_set.parameter_payload_sha256,
            "canonical_parameter_artifact_sha256": (
                self._canonical_parameter_snapshot_sha256
            ),
            "atom_assignments": [
                row.to_dict() for row in analysis.atom_assignments
            ],
            "bond_assignments": [
                row.to_dict() for row in analysis.bond_assignments
            ],
            "angle_assignments": [
                row.to_dict() for row in analysis.angle_assignments
            ],
            "proper_assignments": [
                row.to_dict() for row in analysis.proper_assignments
            ],
            "pair_assignments": [
                row.to_dict() for row in analysis.pair_assignments
            ],
            "component_target_formal_charge": 0,
            "component_partial_charge_sum_e_binary64": _binary64_hex(
                analysis.component_partial_charge_sum_e
            ),
        }

    def _core_dict(self, analysis: _ComputedParameterAssignment) -> dict[str, Any]:
        applicability = analysis.applicability.to_dict()
        typing_document = analysis.typing_report.to_dict()
        inventory = analysis.inventory.to_dict()
        parameter_set = analysis.parameter_set
        mapped = analysis.assignment_status == "contract_fixture_mapped"
        constraint_results = self._constraint_results(analysis)
        assignment_document = self._assignment_document(analysis)
        pair_counts = {
            interaction_class: sum(
                row.interaction_class == interaction_class
                for row in analysis.pair_assignments
            )
            for interaction_class in _FROZEN_PAIR_CLASSES
        }
        mapped_nonexcluded_pair_count = sum(
            row.parameter_status
            == "mapped_nonphysical_contract_fixture_method_deferred"
            for row in analysis.pair_assignments
        )
        excluded_pair_count = (
            len(analysis.pair_assignments) - mapped_nonexcluded_pair_count
        )
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "canonical_system_snapshot_sha256": (
                self._canonical_system_snapshot_sha256
            ),
            "system_schema_id": applicability["system_schema_id"],
            "canonical_topology_schema_id": applicability[
                "canonical_topology_schema_id"
            ],
            "canonical_topology_sha256": applicability[
                "canonical_topology_sha256"
            ],
            "source_format": applicability["source_format"],
            "source_sha256": applicability["source_sha256"],
            "source_authentication_status": applicability[
                "source_authentication_status"
            ],
            "applicability_schema_id": _FROZEN_APPLICABILITY_SCHEMA_ID,
            "applicability_report_sha256": applicability["report_sha256"],
            "typing_schema_id": _FROZEN_TYPING_SCHEMA_ID,
            "typing_report_sha256": typing_document["report_sha256"],
            "inventory_schema_id": _FROZEN_INVENTORY_SCHEMA_ID,
            "inventory_report_sha256": inventory["report_sha256"],
            "pair_classification_policy_id": (
                _FROZEN_PAIR_CLASSIFICATION_POLICY_ID
            ),
            "parameter_protocol_schema_id": (
                _FROZEN_PARAMETER_PROTOCOL_SCHEMA_ID
            ),
            "parameter_protocol_sha256": parameter_set.protocol_sha256,
            "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "parameter_scope": _FROZEN_PARAMETER_SCOPE,
            "parameter_domain_id": _FROZEN_PARAMETER_DOMAIN_ID,
            "force_field_unit_system_id": _FROZEN_FORCE_FIELD_UNIT_SYSTEM_ID,
            "parameter_set_id": parameter_set.parameter_set_id,
            "parameter_set_version": parameter_set.parameter_set_version,
            "parameter_payload_sha256": parameter_set.parameter_payload_sha256,
            "parameter_set_sha256": parameter_set.parameter_set_sha256,
            "canonical_parameter_artifact_sha256": (
                self._canonical_parameter_snapshot_sha256
            ),
            "parameter_artifact_purpose": parameter_set.artifact_purpose,
            "parameter_derivation_status": parameter_set.derivation_status,
            "parameter_scientific_validation_status": (
                parameter_set.scientific_validation_status
            ),
            "parameter_runtime_authorization_status": (
                parameter_set.runtime_authorization_status
            ),
            "parameter_artifact_authentication_status": "not_authenticated",
            "deferred_evaluation_method_status": "not_defined",
            "charge_model_id": parameter_set.charge_model_id,
            "charge_assignment_status": parameter_set.charge_assignment_status,
            "charge_sum_policy_id": _FROZEN_CHARGE_SUM_POLICY_ID,
            "constraint_results": [
                {"code": code, "passed": passed}
                for code, passed in constraint_results
            ],
            "failed_constraint_codes": [
                code for code, passed in constraint_results if not passed
            ],
            "assignment_status": analysis.assignment_status,
            "molecule_label": applicability["molecule_label"],
            "molecular_formula": applicability["molecular_formula"],
            "atom_count": len(analysis.atom_assignments) if mapped else None,
            "topological_environment_counts": [
                {
                    "topological_environment_id": environment_id,
                    "count": sum(
                        row.topological_environment_id == environment_id
                        for row in analysis.atom_assignments
                    ),
                }
                for environment_id in sorted(
                    {
                        row.topological_environment_id
                        for row in analysis.atom_assignments
                    }
                )
            ],
            "atom_assignments": [
                row.to_dict() for row in analysis.atom_assignments
            ],
            "bond_assignment_count": len(analysis.bond_assignments),
            "bond_assignments": [
                row.to_dict() for row in analysis.bond_assignments
            ],
            "angle_assignment_count": len(analysis.angle_assignments),
            "angle_assignments": [
                row.to_dict() for row in analysis.angle_assignments
            ],
            "proper_assignment_count": len(analysis.proper_assignments),
            "proper_assignments": [
                row.to_dict() for row in analysis.proper_assignments
            ],
            "improper_parameter_status": (
                "empty_by_bounded_policy" if mapped else "not_available"
            ),
            "improper_assignments": [],
            "constraint_parameter_status": (
                "empty_by_bounded_policy" if mapped else "not_available"
            ),
            "constraint_assignments": [],
            "pair_assignment_count": len(analysis.pair_assignments),
            "pair_class_counts": pair_counts,
            "excluded_pair_count": excluded_pair_count,
            "mapped_nonexcluded_pair_count": mapped_nonexcluded_pair_count,
            "exact_pair_override_count": sum(
                row.lj_resolution_status == "exact_pair_override"
                for row in analysis.pair_assignments
            ),
            "lorentz_berthelot_pair_count": sum(
                row.lj_resolution_status == "lorentz_berthelot"
                for row in analysis.pair_assignments
            ),
            "pair_assignments": [
                row.to_dict() for row in analysis.pair_assignments
            ],
            "one_four_lj_energy_scale_binary64": _binary64_hex(
                parameter_set.one_four_lj_energy_scale
            ),
            "one_four_coulomb_energy_scale_binary64": _binary64_hex(
                parameter_set.one_four_coulomb_energy_scale
            ),
            "component_target_formal_charge": 0 if mapped else None,
            "component_partial_charge_sum_e_binary64": (
                _binary64_hex(analysis.component_partial_charge_sum_e)
                if mapped
                else None
            ),
            "component_charge_balance_status": (
                "balanced_contract_fixture" if mapped else "not_available"
            ),
            "parameter_assignment_sha256": (
                _sha256_document(assignment_document)
                if assignment_document is not None
                else None
            ),
            "bounded_contract_fixture_atom_mapping_complete": mapped,
            "bounded_contract_fixture_bonded_mapping_complete": mapped,
            "bounded_contract_fixture_pair_mapping_complete": mapped,
            "bounded_contract_fixture_charge_balance_complete": mapped,
            "bounded_contract_fixture_assignment_complete": mapped,
            "evaluation_method_defined": False,
            "production_parameter_assignment_complete": False,
            "parameterability_assessed": False,
            "parameterizable": False,
            "production_force_field_atom_types_assigned": False,
            "production_partial_charges_assigned": False,
            "production_force_field_parameters_assigned": False,
            "global_parameter_coverage_complete": False,
            "preparation_ready": False,
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
            "blockers": list(self._blockers(analysis)),
        }

    @property
    def parameter_assignment_sha256(self) -> str | None:
        analysis = self._analysis()
        document = self._assignment_document(analysis)
        return None if document is None else _sha256_document(document)

    @property
    def report_sha256(self) -> str:
        analysis = self._analysis()
        return _sha256_document(self._core_dict(analysis))

    def to_dict(self) -> dict[str, Any]:
        analysis = self._analysis()
        document = self._core_dict(analysis)
        document["report_sha256"] = _sha256_document(document)
        return document

    def matches(
        self,
        system: AllAtomSystem,
        parameter_set: LinearAlkaneC1C4ParameterSet,
    ) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an exact AllAtomSystem")
        if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
            raise TypeError("parameter_set must be an exact C1-C4 parameter set")
        self._analysis()
        return (
            self._canonical_system_snapshot == serialize_all_atom_system(system)
            and self._canonical_parameter_snapshot
            == serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
        )


def analyze_linear_alkane_c1_c4_parameter_assignment(
    system: AllAtomSystem,
    parameter_set: LinearAlkaneC1C4ParameterSet,
) -> LinearAlkaneC1C4ParameterAssignmentReport:
    """Map a bounded topology to the nonphysical fixture without evaluation."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an exact AllAtomSystem")
    if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
        raise TypeError("parameter_set must be an exact C1-C4 parameter set")
    return LinearAlkaneC1C4ParameterAssignmentReport(system, parameter_set)


def serialize_linear_alkane_c1_c4_parameter_assignment_report(
    report: LinearAlkaneC1C4ParameterAssignmentReport,
) -> bytes:
    """Serialize a freshly revalidated assignment report to canonical JSON."""

    if type(report) is not LinearAlkaneC1C4ParameterAssignmentReport:
        raise TypeError("report must be an exact C1-C4 assignment report")
    analysis = report._analysis()
    document = report._core_dict(analysis)
    document["report_sha256"] = _sha256_document(document)
    return _canonical_json_bytes(document)


__all__ = [
    "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_CLAIM_SCOPE",
    "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_POLICY_ID",
    "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_ID",
    "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_SCHEMA_VERSION",
    "LINEAR_ALKANE_C1_C4_PARAMETER_ASSIGNMENT_STATUSES",
    "LinearAlkaneAngleParameterAssignment",
    "LinearAlkaneAtomParameterAssignment",
    "LinearAlkaneBondParameterAssignment",
    "LinearAlkaneC1C4ParameterAssignmentReport",
    "LinearAlkanePairParameterAssignment",
    "LinearAlkaneParameterAssignmentContractError",
    "LinearAlkaneProperParameterAssignment",
    "analyze_linear_alkane_c1_c4_parameter_assignment",
    "serialize_linear_alkane_c1_c4_parameter_assignment_report",
]
