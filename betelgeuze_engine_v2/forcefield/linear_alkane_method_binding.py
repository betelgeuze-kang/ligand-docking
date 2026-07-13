"""Snapshot-bound C1-C4 evaluation-method compatibility without evaluation.

This module binds one canonical molecular snapshot, one nonphysical parameter
artifact, and one nonphysical direct-uncut method artifact.  It recomputes the
full parameter assignment and checks the coordinate geometry domain, but it
does not calculate an energy, force, virial, minimization step, or simulation.
Inputs that cannot be serialized as strict canonical molecular state fail with
their typed molecular validation error before any binding report is created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Any, Mapping

import torch

from betelgeuze_engine_v2.molecular.models import AllAtomSystem
from betelgeuze_engine_v2.molecular.serialization import (
    deserialize_all_atom_system,
    serialize_all_atom_system,
)

from .linear_alkane_assignment import (
    LinearAlkaneC1C4ParameterAssignmentReport,
    analyze_linear_alkane_c1_c4_parameter_assignment,
)
from .linear_alkane_evaluation_method import (
    LinearAlkaneC1C4EvaluationMethod,
    deserialize_linear_alkane_c1_c4_evaluation_method,
    serialize_linear_alkane_c1_c4_evaluation_method,
)
from .linear_alkane_parameters import (
    LinearAlkaneC1C4ParameterSet,
    deserialize_linear_alkane_c1_c4_parameter_set,
    serialize_linear_alkane_c1_c4_parameter_set,
)


_FROZEN_SCHEMA_VERSION = "1.0.0"
_FROZEN_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_binding/"
    f"{_FROZEN_SCHEMA_VERSION}"
)
_FROZEN_BINDING_POLICY_ID = (
    "fresh_system_parameter_method_snapshots_input_envelope_assignment_and_"
    "geometry_domain_no_evaluation/1.0.0"
)
_FROZEN_CLAIM_SCOPE = (
    "bounded_nonphysical_c1_c4_method_assignment_binding_only_no_evaluation"
)
_FROZEN_INPUT_ENVELOPE_POLICY_ID = (
    "observe_live_tensor_interface_before_detach_cpu_contiguous_snapshot/1.0.0"
)
_FROZEN_STATUSES = frozenset(
    {
        "invalid_system",
        "unsupported_system",
        "method_incompatible",
        "contract_fixture_method_bound",
    }
)
_FROZEN_ASSIGNMENT_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_assignment/1.0.0"
)
_FROZEN_ASSIGNMENT_POLICY_ID = (
    "fresh_snapshot_exact_environment_term_and_pair_parameter_mapping/1.0.0"
)
_FROZEN_PARAMETER_PROTOCOL_SHA256 = (
    "28219cd1492b31f3d151048e7ad9db297fe7a896d081b098e901f142f6d4602a"
)
_FROZEN_PARAMETER_SET_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_parameter_set/1.0.0"
)
_FROZEN_METHOD_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method_protocol/1.0.0"
)
_FROZEN_METHOD_PROTOCOL_SHA256 = (
    "7a8416632d83cab3e32ebbbdc43549d59b5a4efb472283d07f773ad66de461da"
)
_FROZEN_METHOD_SCHEMA_ID = (
    "betelgeuze.linear_alkane_c1_c4_evaluation_method/1.0.0"
)
_FROZEN_FORCE_FIELD_UNIT_SYSTEM_ID = (
    "betelgeuze.kilojoule_per_mole_angstrom_radian_elementary_charge/1.0.0"
)
_FROZEN_PAIR_CLASSIFICATION_POLICY_ID = (
    "covalent_shortest_graph_distance_1_2_excluded_1_3_excluded_"
    "1_4_separate_farther_full_v1"
)
_FROZEN_MAXIMUM_ATOM_COUNT = 14
_FROZEN_MAXIMUM_PAIR_COUNT = 91
_FROZEN_MAXIMUM_SELECTED_PAIR_COUNT = 54
_FROZEN_PAIR_CLASSES = (
    "excluded_1_2",
    "excluded_1_3",
    "one_four_separate",
    "full_nonbonded",
)
_FROZEN_COMPATIBILITY_CODES = (
    "canonical_input_snapshot_round_trip_and_envelope_bound",
    "assignment_contract_fixture_mapped",
    "parameter_protocol_matches_method_contract",
    "assignment_schema_and_policy_match_method_contract",
    "force_field_unit_system_matches_method_contract",
    "atom_count_within_direct_reference_limit",
    "single_coordinate_model",
    "coordinate_unit_angstrom",
    "coordinate_dtype_float64",
    "coordinate_device_cpu",
    "coordinate_layout_strided_materialized",
    "coordinates_require_no_grad",
    "cell_free_nonperiodic_input",
    "exact_all_pair_inventory_bound",
    "exact_nonexcluded_pair_subset_covered",
    "all_parameter_deferred_method_fields_explicitly_closed",
    "bond_distances_above_method_minimum",
    "angle_legs_and_sines_above_method_minimum",
    "proper_bonds_and_sines_above_method_minimum",
    "selected_pair_distances_above_method_minimum",
    "geometry_intermediates_finite",
)
_MAX_INPUT_ENVELOPE_BYTES = 16 * 1024
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_VERSION = _FROZEN_SCHEMA_VERSION
LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_ID = _FROZEN_SCHEMA_ID
LINEAR_ALKANE_EVALUATION_METHOD_BINDING_POLICY_ID = _FROZEN_BINDING_POLICY_ID
LINEAR_ALKANE_EVALUATION_METHOD_BINDING_CLAIM_SCOPE = _FROZEN_CLAIM_SCOPE
LINEAR_ALKANE_EVALUATION_METHOD_BINDING_STATUSES = _FROZEN_STATUSES


class LinearAlkaneEvaluationMethodBindingContractError(ValueError):
    """Raised when a stored method binding cannot be reproduced exactly."""


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
        raise LinearAlkaneEvaluationMethodBindingContractError(
            f"method binding is not canonical JSON: {exc}"
        ) from exc


def _sha256_document(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_sha256(name: str, value: Any) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise TypeError(f"{name} must be an exact lowercase SHA-256 digest")
    return value


def _dtype_name(dtype: torch.dtype) -> str:
    if dtype is torch.float32:
        return "torch.float32"
    if dtype is torch.float64:
        return "torch.float64"
    raise LinearAlkaneEvaluationMethodBindingContractError(
        f"unsupported canonical coordinate dtype {dtype}"
    )


def _observe_input_execution_envelope(system: AllAtomSystem) -> dict[str, Any]:
    coordinates = system.coordinates
    cell = system.cell
    return {
        "observation_policy_id": _FROZEN_INPUT_ENVELOPE_POLICY_ID,
        "canonical_snapshot_normalization": "detach_cpu_contiguous",
        "device_preservation_status": (
            "original_device_observed_separately_not_snapshot_encoded"
        ),
        "coordinates_device_type": coordinates.device.type,
        "coordinates_device_index": coordinates.device.index,
        "coordinates_dtype": _dtype_name(coordinates.dtype),
        "coordinates_shape": [int(value) for value in coordinates.shape],
        "coordinate_model_count": int(coordinates.shape[0]),
        "coordinates_layout": "torch.strided",
        "coordinates_materialized": coordinates.device.type != "meta",
        "coordinates_contiguous": coordinates.is_contiguous(),
        "coordinates_requires_grad": coordinates.requires_grad,
        "coordinate_unit": system.coordinate_unit,
        "cell_present": cell is not None,
        "cell_vectors_device_type": (
            None if cell is None else cell.vectors.device.type
        ),
        "cell_vectors_device_index": (
            None if cell is None else cell.vectors.device.index
        ),
        "cell_vectors_dtype": (
            None if cell is None else _dtype_name(cell.vectors.dtype)
        ),
        "cell_vectors_shape": (
            None if cell is None else [int(value) for value in cell.vectors.shape]
        ),
        "cell_periodic_flags": (
            None if cell is None else [bool(value) for value in cell.periodic]
        ),
    }


_INPUT_ENVELOPE_KEYS = frozenset(
    {
        "observation_policy_id",
        "canonical_snapshot_normalization",
        "device_preservation_status",
        "coordinates_device_type",
        "coordinates_device_index",
        "coordinates_dtype",
        "coordinates_shape",
        "coordinate_model_count",
        "coordinates_layout",
        "coordinates_materialized",
        "coordinates_contiguous",
        "coordinates_requires_grad",
        "coordinate_unit",
        "cell_present",
        "cell_vectors_device_type",
        "cell_vectors_device_index",
        "cell_vectors_dtype",
        "cell_vectors_shape",
        "cell_periodic_flags",
    }
)


def _require_optional_device_index(name: str, value: Any) -> int | None:
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError(f"{name} must be an exact integer or None")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_shape(name: str, value: Any, *, expected_rank: int) -> list[int]:
    if type(value) is not list or len(value) != expected_rank:
        raise TypeError(f"{name} must be an exact rank-{expected_rank} list")
    if not all(type(item) is int and item >= 0 for item in value):
        raise TypeError(f"{name} must contain exact non-negative integers")
    return value


def _validate_input_execution_envelope(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise TypeError("input execution envelope must be an exact dictionary")
    if set(value) != _INPUT_ENVELOPE_KEYS:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope keys are inconsistent"
        )
    if value["observation_policy_id"] != _FROZEN_INPUT_ENVELOPE_POLICY_ID:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution observation policy is inconsistent"
        )
    if value["canonical_snapshot_normalization"] != "detach_cpu_contiguous":
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "snapshot normalization declaration is inconsistent"
        )
    if value["device_preservation_status"] != (
        "original_device_observed_separately_not_snapshot_encoded"
    ):
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "device preservation declaration is inconsistent"
        )
    for name in ("coordinates_device_type", "coordinate_unit"):
        if type(value[name]) is not str or not value[name]:
            raise TypeError(f"{name} must be an exact non-empty string")
    _require_optional_device_index(
        "coordinates_device_index",
        value["coordinates_device_index"],
    )
    if value["coordinates_dtype"] not in {"torch.float32", "torch.float64"}:
        raise ValueError("coordinates_dtype is unsupported")
    shape = _require_shape(
        "coordinates_shape",
        value["coordinates_shape"],
        expected_rank=3,
    )
    if shape[2] != 3:
        raise ValueError("coordinates_shape must end in three")
    if type(value["coordinate_model_count"]) is not int:
        raise TypeError("coordinate_model_count must be an exact integer")
    if value["coordinate_model_count"] != shape[0]:
        raise ValueError("coordinate_model_count must match coordinates_shape")
    if value["coordinates_layout"] != "torch.strided":
        raise ValueError("coordinates_layout must be torch.strided")
    for name in (
        "coordinates_materialized",
        "coordinates_contiguous",
        "coordinates_requires_grad",
        "cell_present",
    ):
        if type(value[name]) is not bool:
            raise TypeError(f"{name} must be an exact boolean")
    if value["coordinates_materialized"] is not True:
        raise ValueError("coordinates must be materialized")
    if value["cell_present"] is False:
        for name in (
            "cell_vectors_device_type",
            "cell_vectors_device_index",
            "cell_vectors_dtype",
            "cell_vectors_shape",
            "cell_periodic_flags",
        ):
            if value[name] is not None:
                raise ValueError(f"{name} must be None when no cell is present")
    else:
        if type(value["cell_vectors_device_type"]) is not str:
            raise TypeError("cell_vectors_device_type must be an exact string")
        _require_optional_device_index(
            "cell_vectors_device_index",
            value["cell_vectors_device_index"],
        )
        if value["cell_vectors_dtype"] not in {
            "torch.float32",
            "torch.float64",
        }:
            raise ValueError("cell_vectors_dtype is unsupported")
        if _require_shape(
            "cell_vectors_shape",
            value["cell_vectors_shape"],
            expected_rank=2,
        ) != [3, 3]:
            raise ValueError("cell_vectors_shape must equal [3,3]")
        periodic = value["cell_periodic_flags"]
        if (
            type(periodic) is not list
            or len(periodic) != 3
            or not all(type(item) is bool for item in periodic)
        ):
            raise TypeError("cell_periodic_flags must contain three booleans")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LinearAlkaneEvaluationMethodBindingContractError(
                f"duplicate input execution envelope key {key!r}"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise LinearAlkaneEvaluationMethodBindingContractError(
        f"nonstandard JSON constant {value!r} is not allowed"
    )


def _serialize_input_execution_envelope(value: dict[str, Any]) -> bytes:
    _validate_input_execution_envelope(value)
    payload = _canonical_json_bytes(value)
    if len(payload) > _MAX_INPUT_ENVELOPE_BYTES:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope exceeds its byte limit"
        )
    return payload


def _deserialize_input_execution_envelope(data: bytes) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError("stored input execution envelope must be exact bytes")
    if len(data) > _MAX_INPUT_ENVELOPE_BYTES:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope exceeds its byte limit"
        )
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope must be ASCII"
        ) from exc
    try:
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except LinearAlkaneEvaluationMethodBindingContractError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            f"invalid input execution envelope: {exc}"
        ) from exc
    envelope = _validate_input_execution_envelope(document)
    if _serialize_input_execution_envelope(envelope) != data:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope is noncanonical or tampered"
        )
    return envelope


def _envelope_matches_restored_system(
    envelope: Mapping[str, Any],
    system: AllAtomSystem,
) -> bool:
    expected = _observe_input_execution_envelope(system)
    preserved_fields = (
        "coordinates_dtype",
        "coordinates_shape",
        "coordinate_model_count",
        "coordinates_layout",
        "coordinates_materialized",
        "coordinate_unit",
        "cell_present",
        "cell_vectors_dtype",
        "cell_vectors_shape",
        "cell_periodic_flags",
    )
    return all(envelope[name] == expected[name] for name in preserved_fields)


def _vector(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        second[0] - first[0],
        second[1] - first[1],
        second[2] - first[2],
    )


def _finite_length(vector: tuple[float, float, float]) -> float | None:
    if not all(math.isfinite(value) for value in vector):
        return None
    try:
        length = math.hypot(*vector)
    except (OverflowError, ValueError):
        return None
    return length if math.isfinite(length) else None


def _finite_normalized_sine(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
    first_length: float,
    second_length: float,
) -> float | None:
    try:
        unit_first = tuple(value / first_length for value in first)
        unit_second = tuple(value / second_length for value in second)
        cross = (
            unit_first[1] * unit_second[2]
            - unit_first[2] * unit_second[1],
            unit_first[2] * unit_second[0]
            - unit_first[0] * unit_second[2],
            unit_first[0] * unit_second[1]
            - unit_first[1] * unit_second[0],
        )
        sine = math.hypot(*cross)
    except (OverflowError, ValueError, ZeroDivisionError):
        return None
    return sine if math.isfinite(sine) else None


def _geometry_results(
    system: AllAtomSystem,
    assignment: Mapping[str, Any],
    method: LinearAlkaneC1C4EvaluationMethod,
) -> tuple[tuple[tuple[str, bool], ...], str]:
    coordinates = system.coordinates
    points = tuple(
        tuple(float(coordinates[0, atom_index, axis].item()) for axis in range(3))
        for atom_index in range(system.atom_count)
    )
    finite_intermediates = all(
        math.isfinite(value) for point in points for value in point
    )
    bond_ok = True
    angle_ok = True
    proper_ok = True
    pair_ok = True
    minimum_distance = method.minimum_distance_angstrom

    for row in assignment["bond_assignments"]:
        identity = row["identity"]
        difference = _vector(
            points[identity["atom_i"]],
            points[identity["atom_j"]],
        )
        length = _finite_length(difference)
        if length is None:
            finite_intermediates = False
            bond_ok = False
        elif length <= minimum_distance:
            bond_ok = False

    for row in assignment["angle_assignments"]:
        identity = row["identity"]
        center = points[identity["center_atom"]]
        first = _vector(center, points[identity["outer_atom_i"]])
        second = _vector(center, points[identity["outer_atom_k"]])
        first_length = _finite_length(first)
        second_length = _finite_length(second)
        if first_length is None or second_length is None:
            finite_intermediates = False
            angle_ok = False
            continue
        if first_length <= minimum_distance or second_length <= minimum_distance:
            angle_ok = False
            continue
        sine = _finite_normalized_sine(
            first,
            second,
            first_length,
            second_length,
        )
        if sine is None:
            finite_intermediates = False
            angle_ok = False
        elif sine <= method.minimum_angle_sine:
            angle_ok = False

    for row in assignment["proper_assignments"]:
        identity = row["identity"]
        first = _vector(
            points[identity["atom_i"]],
            points[identity["atom_j"]],
        )
        second = _vector(
            points[identity["atom_j"]],
            points[identity["atom_k"]],
        )
        third = _vector(
            points[identity["atom_k"]],
            points[identity["atom_l"]],
        )
        lengths = tuple(_finite_length(value) for value in (first, second, third))
        if any(value is None for value in lengths):
            finite_intermediates = False
            proper_ok = False
            continue
        first_length, second_length, third_length = lengths
        assert first_length is not None
        assert second_length is not None
        assert third_length is not None
        if any(value <= minimum_distance for value in lengths):
            proper_ok = False
            continue
        first_sine = _finite_normalized_sine(
            first,
            second,
            first_length,
            second_length,
        )
        second_sine = _finite_normalized_sine(
            second,
            third,
            second_length,
            third_length,
        )
        if first_sine is None or second_sine is None:
            finite_intermediates = False
            proper_ok = False
        elif (
            first_sine <= method.minimum_proper_sine
            or second_sine <= method.minimum_proper_sine
        ):
            proper_ok = False

    for row in assignment["pair_assignments"]:
        if row["interaction_class"] not in {
            "one_four_separate",
            "full_nonbonded",
        }:
            continue
        identity = row["identity"]
        difference = _vector(
            points[identity["atom_i"]],
            points[identity["atom_j"]],
        )
        length = _finite_length(difference)
        if length is None:
            finite_intermediates = False
            pair_ok = False
        elif length <= minimum_distance:
            pair_ok = False

    results = (
        ("bond_distances_above_method_minimum", bond_ok),
        ("angle_legs_and_sines_above_method_minimum", angle_ok),
        ("proper_bonds_and_sines_above_method_minimum", proper_ok),
        ("selected_pair_distances_above_method_minimum", pair_ok),
        ("geometry_intermediates_finite", finite_intermediates),
    )
    if not finite_intermediates:
        status = "failed_nonfinite_intermediate"
    elif all(passed for _, passed in results):
        status = "passed_bounded_domain_check_no_evaluation"
    else:
        status = "failed_singularity_threshold"
    return results, status


def _pair_inventory_results(
    assignment: Mapping[str, Any],
) -> tuple[bool, bool, int]:
    if assignment["assignment_status"] != "contract_fixture_mapped":
        return False, False, 0
    atom_count = assignment["atom_count"]
    rows = assignment["pair_assignments"]
    expected_identities = tuple(
        (atom_i, atom_j)
        for atom_i in range(atom_count)
        for atom_j in range(atom_i + 1, atom_count)
    )
    observed_identities = tuple(
        (row["identity"]["atom_i"], row["identity"]["atom_j"])
        for row in rows
    )
    exact_all_pairs = (
        observed_identities == expected_identities
        and len(rows) == atom_count * (atom_count - 1) // 2
        and len(rows) <= _FROZEN_MAXIMUM_PAIR_COUNT
    )
    selected = tuple(
        row
        for row in rows
        if row["interaction_class"]
        in {"one_four_separate", "full_nonbonded"}
    )
    excluded = tuple(
        row
        for row in rows
        if row["interaction_class"] in {"excluded_1_2", "excluded_1_3"}
    )
    selected_valid = all(
        row["parameter_status"]
        == "mapped_nonphysical_contract_fixture_method_deferred"
        and (
            (
                row["interaction_class"] == "one_four_separate"
                and row["lj_energy_scale_binary64"] is not None
                and row["coulomb_energy_scale_binary64"] is not None
            )
            or (
                row["interaction_class"] == "full_nonbonded"
                and row["lj_energy_scale_binary64"] is None
                and row["coulomb_energy_scale_binary64"] is None
            )
        )
        for row in selected
    )
    excluded_valid = all(
        row["parameter_status"] == "excluded_no_parameter_mapping"
        for row in excluded
    )
    exact_selected_subset = (
        exact_all_pairs
        and len(selected) + len(excluded) == len(rows)
        and len(selected) == assignment["mapped_nonexcluded_pair_count"]
        and len(selected) <= _FROZEN_MAXIMUM_SELECTED_PAIR_COUNT
        and selected_valid
        and excluded_valid
    )
    return exact_all_pairs, exact_selected_subset, len(selected)


@dataclass(frozen=True, slots=True)
class _ComputedMethodBinding:
    system: AllAtomSystem
    parameter_set: LinearAlkaneC1C4ParameterSet
    method: LinearAlkaneC1C4EvaluationMethod
    input_execution_envelope: dict[str, Any]
    assignment_report: LinearAlkaneC1C4ParameterAssignmentReport
    assignment_document: dict[str, Any]
    compatibility_results: tuple[tuple[str, bool], ...]
    geometry_domain_assessment_status: str
    method_binding_status: str
    method_covered_nonexcluded_pair_count: int


@dataclass(frozen=True, slots=True)
class _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay:
    """One internally consistent replay capsule for a downstream diagnostic."""

    system: AllAtomSystem
    parameter_set: LinearAlkaneC1C4ParameterSet
    method: LinearAlkaneC1C4EvaluationMethod
    assignment_report: LinearAlkaneC1C4ParameterAssignmentReport
    canonical_system_snapshot_bytes: bytes = field(repr=False)
    canonical_parameter_artifact_bytes: bytes = field(repr=False)
    canonical_method_artifact_bytes: bytes = field(repr=False)
    input_execution_envelope_bytes: bytes = field(repr=False)
    binding_report_bytes: bytes = field(repr=False)
    compatibility_results: tuple[tuple[str, bool], ...]
    method_binding_status: str
    geometry_domain_assessment_status: str

    def __post_init__(self) -> None:
        if type(self.system) is not AllAtomSystem:
            raise TypeError("replay system must be an exact AllAtomSystem")
        if type(self.parameter_set) is not LinearAlkaneC1C4ParameterSet:
            raise TypeError("replay parameter set must be an exact C1-C4 parameter set")
        if type(self.method) is not LinearAlkaneC1C4EvaluationMethod:
            raise TypeError("replay method must be an exact C1-C4 evaluation method")
        if type(self.assignment_report) is not LinearAlkaneC1C4ParameterAssignmentReport:
            raise TypeError("replay assignment must be its exact report type")
        for name in (
            "canonical_system_snapshot_bytes",
            "canonical_parameter_artifact_bytes",
            "canonical_method_artifact_bytes",
            "input_execution_envelope_bytes",
            "binding_report_bytes",
        ):
            if type(getattr(self, name)) is not bytes:
                raise TypeError(f"replay {name} must be exact bytes")
        if (
            type(self.compatibility_results) is not tuple
            or not all(
                type(row) is tuple
                and len(row) == 2
                and type(row[0]) is str
                and type(row[1]) is bool
                for row in self.compatibility_results
            )
        ):
            raise TypeError("replay compatibility results are inconsistent")
        if self.method_binding_status not in _FROZEN_STATUSES:
            raise ValueError("replay method binding status is unknown")
        if type(self.geometry_domain_assessment_status) is not str:
            raise TypeError("replay geometry status must be an exact string")


def _compute(
    system_snapshot: bytes,
    parameter_snapshot: bytes,
    method_snapshot: bytes,
    input_execution_envelope_snapshot: bytes,
) -> _ComputedMethodBinding:
    system = deserialize_all_atom_system(system_snapshot)
    if serialize_all_atom_system(system) != system_snapshot:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "stored system snapshot is not canonical"
        )
    parameter_set = deserialize_linear_alkane_c1_c4_parameter_set(
        parameter_snapshot
    )
    if (
        serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
        != parameter_snapshot
    ):
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "stored parameter artifact is not canonical"
        )
    method = deserialize_linear_alkane_c1_c4_evaluation_method(method_snapshot)
    if serialize_linear_alkane_c1_c4_evaluation_method(method) != method_snapshot:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "stored evaluation-method artifact is not canonical"
        )
    envelope = _deserialize_input_execution_envelope(
        input_execution_envelope_snapshot
    )
    envelope_matches_snapshot = _envelope_matches_restored_system(envelope, system)
    if not envelope_matches_snapshot:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "input execution envelope disagrees with snapshot-preserved values"
        )

    assignment_report = analyze_linear_alkane_c1_c4_parameter_assignment(
        system,
        parameter_set,
    )
    if type(assignment_report) is not LinearAlkaneC1C4ParameterAssignmentReport:
        raise TypeError("assignment dependency must be its exact report type")
    assignment = assignment_report.to_dict()
    if assignment.get("schema_id") != _FROZEN_ASSIGNMENT_SCHEMA_ID:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "assignment dependency schema is inconsistent"
        )
    if assignment.get("assignment_policy_id") != _FROZEN_ASSIGNMENT_POLICY_ID:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "assignment dependency policy is inconsistent"
        )
    system_sha256 = hashlib.sha256(system_snapshot).hexdigest()
    parameter_sha256 = hashlib.sha256(parameter_snapshot).hexdigest()
    if assignment["canonical_system_snapshot_sha256"] != system_sha256:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "assignment does not bind the exact system snapshot"
        )
    if assignment["canonical_parameter_artifact_sha256"] != parameter_sha256:
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "assignment does not bind the exact parameter artifact"
        )
    method_document = method.to_dict()
    method_payload = method_document["method_payload"]
    parameter_protocol_matches = (
        assignment["parameter_protocol_sha256"]
        == _FROZEN_PARAMETER_PROTOCOL_SHA256
        == method_payload["parameter_protocol_sha256"]
    )
    assignment_contract_matches = (
        method_payload["assignment_schema_id"] == _FROZEN_ASSIGNMENT_SCHEMA_ID
        and method_payload["assignment_policy_id"]
        == _FROZEN_ASSIGNMENT_POLICY_ID
    )
    unit_system_matches = (
        assignment["force_field_unit_system_id"]
        == _FROZEN_FORCE_FIELD_UNIT_SYSTEM_ID
        == method_payload["unit_system"]["unit_system_id"]
    )
    mapped = assignment["assignment_status"] == "contract_fixture_mapped"
    atom_count = assignment["atom_count"] if mapped else None
    exact_all_pairs, exact_selected, selected_count = _pair_inventory_results(
        assignment
    )
    method_fields_closed = (
        assignment["deferred_evaluation_method_status"] == "not_defined"
        and method_document["schema_id"] == _FROZEN_METHOD_SCHEMA_ID
        and method_payload["protocol_schema_id"]
        == _FROZEN_METHOD_PROTOCOL_SCHEMA_ID
        and method_payload["protocol_sha256"] == _FROZEN_METHOD_PROTOCOL_SHA256
        and method_payload["r_switch_angstrom"] is None
        and method_payload["r_cut_angstrom"] is None
        and method_payload["minimum_image_policy"] is None
        and method_payload["long_range_correction_method_id"] is None
        and method_payload["reciprocal_space_method_id"] is None
        and method_payload["dispersion_tail_correction"] is False
        and method_payload["maximum_atom_count"] == _FROZEN_MAXIMUM_ATOM_COUNT
        and method_payload["maximum_unordered_pair_count"]
        == _FROZEN_MAXIMUM_PAIR_COUNT
        and method_payload["maximum_selected_pair_count"]
        == _FROZEN_MAXIMUM_SELECTED_PAIR_COUNT
        and method_payload["coordinates_requires_grad"] is False
        and method_payload["geometry_domain_algorithm_id"]
        == "cpu_binary64_hypot_unit_vector_cross_sine_threshold_check/1.0.0"
    )
    base_results = (
        (
            "canonical_input_snapshot_round_trip_and_envelope_bound",
            envelope_matches_snapshot,
        ),
        ("assignment_contract_fixture_mapped", mapped),
        (
            "parameter_protocol_matches_method_contract",
            parameter_protocol_matches,
        ),
        (
            "assignment_schema_and_policy_match_method_contract",
            assignment_contract_matches,
        ),
        (
            "force_field_unit_system_matches_method_contract",
            unit_system_matches,
        ),
        (
            "atom_count_within_direct_reference_limit",
            type(atom_count) is int
            and 5 <= atom_count <= _FROZEN_MAXIMUM_ATOM_COUNT,
        ),
        (
            "single_coordinate_model",
            envelope["coordinate_model_count"] == 1,
        ),
        (
            "coordinate_unit_angstrom",
            envelope["coordinate_unit"] == "angstrom",
        ),
        (
            "coordinate_dtype_float64",
            envelope["coordinates_dtype"] == "torch.float64",
        ),
        (
            "coordinate_device_cpu",
            envelope["coordinates_device_type"] == "cpu"
            and envelope["coordinates_device_index"] is None,
        ),
        (
            "coordinate_layout_strided_materialized",
            envelope["coordinates_layout"] == "torch.strided"
            and envelope["coordinates_materialized"] is True,
        ),
        (
            "coordinates_require_no_grad",
            envelope["coordinates_requires_grad"] is False,
        ),
        ("cell_free_nonperiodic_input", envelope["cell_present"] is False),
        ("exact_all_pair_inventory_bound", exact_all_pairs),
        ("exact_nonexcluded_pair_subset_covered", exact_selected),
        (
            "all_parameter_deferred_method_fields_explicitly_closed",
            method_fields_closed,
        ),
    )
    can_assess_geometry = mapped and all(passed for _, passed in base_results)
    if can_assess_geometry:
        geometry_results, geometry_status = _geometry_results(
            system,
            assignment,
            method,
        )
    else:
        geometry_results = (
            ("bond_distances_above_method_minimum", False),
            ("angle_legs_and_sines_above_method_minimum", False),
            ("proper_bonds_and_sines_above_method_minimum", False),
            ("selected_pair_distances_above_method_minimum", False),
            ("geometry_intermediates_finite", False),
        )
        geometry_status = "not_assessed_upstream_or_interface_incompatible"
    compatibility_results = base_results + geometry_results
    if tuple(code for code, _ in compatibility_results) != (
        _FROZEN_COMPATIBILITY_CODES
    ):
        raise LinearAlkaneEvaluationMethodBindingContractError(
            "compatibility result order is inconsistent"
        )
    assignment_status = assignment["assignment_status"]
    if assignment_status == "invalid_system":
        binding_status = "invalid_system"
    elif assignment_status == "unsupported_system":
        binding_status = "unsupported_system"
    elif not all(passed for _, passed in compatibility_results):
        binding_status = "method_incompatible"
    else:
        binding_status = "contract_fixture_method_bound"
    return _ComputedMethodBinding(
        system=system,
        parameter_set=parameter_set,
        method=method,
        input_execution_envelope=envelope,
        assignment_report=assignment_report,
        assignment_document=assignment,
        compatibility_results=compatibility_results,
        geometry_domain_assessment_status=geometry_status,
        method_binding_status=binding_status,
        method_covered_nonexcluded_pair_count=selected_count,
    )


@dataclass(frozen=True, init=False, slots=True)
class LinearAlkaneC1C4EvaluationMethodBindingReport:
    """Factory-only report that reproduces all four bound byte artifacts."""

    _canonical_system_snapshot: bytes = field(repr=False)
    _canonical_system_snapshot_sha256: str = field(repr=False)
    _canonical_parameter_snapshot: bytes = field(repr=False)
    _canonical_parameter_snapshot_sha256: str = field(repr=False)
    _canonical_method_snapshot: bytes = field(repr=False)
    _canonical_method_snapshot_sha256: str = field(repr=False)
    _input_execution_envelope_snapshot: bytes = field(repr=False)
    _input_execution_envelope_snapshot_sha256: str = field(repr=False)

    def __init__(
        self,
        system: AllAtomSystem,
        parameter_set: LinearAlkaneC1C4ParameterSet,
        method: LinearAlkaneC1C4EvaluationMethod,
    ) -> None:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an exact AllAtomSystem")
        if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
            raise TypeError("parameter_set must be an exact C1-C4 parameter set")
        if type(method) is not LinearAlkaneC1C4EvaluationMethod:
            raise TypeError("method must be an exact C1-C4 evaluation method")
        envelope_snapshot = _serialize_input_execution_envelope(
            _observe_input_execution_envelope(system)
        )
        system_snapshot = serialize_all_atom_system(system)
        parameter_snapshot = serialize_linear_alkane_c1_c4_parameter_set(
            parameter_set
        )
        method_snapshot = serialize_linear_alkane_c1_c4_evaluation_method(method)
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
        object.__setattr__(self, "_canonical_method_snapshot", method_snapshot)
        object.__setattr__(
            self,
            "_canonical_method_snapshot_sha256",
            hashlib.sha256(method_snapshot).hexdigest(),
        )
        object.__setattr__(
            self,
            "_input_execution_envelope_snapshot",
            envelope_snapshot,
        )
        object.__setattr__(
            self,
            "_input_execution_envelope_snapshot_sha256",
            hashlib.sha256(envelope_snapshot).hexdigest(),
        )
        self._validate(
            _compute(
                system_snapshot,
                parameter_snapshot,
                method_snapshot,
                envelope_snapshot,
            )
        )

    def _validated_snapshots(self) -> tuple[bytes, bytes, bytes, bytes]:
        snapshots = (
            self._canonical_system_snapshot,
            self._canonical_parameter_snapshot,
            self._canonical_method_snapshot,
            self._input_execution_envelope_snapshot,
        )
        names = ("system", "parameter", "method", "input envelope")
        digests = (
            self._canonical_system_snapshot_sha256,
            self._canonical_parameter_snapshot_sha256,
            self._canonical_method_snapshot_sha256,
            self._input_execution_envelope_snapshot_sha256,
        )
        for name, snapshot, digest in zip(names, snapshots, digests, strict=True):
            if type(snapshot) is not bytes:
                raise TypeError(f"stored {name} snapshot must be exact bytes")
            expected = _require_sha256(f"stored {name} snapshot digest", digest)
            if hashlib.sha256(snapshot).hexdigest() != expected:
                raise LinearAlkaneEvaluationMethodBindingContractError(
                    f"stored {name} snapshot digest binding is inconsistent"
                )
        return snapshots

    def _validate(
        self,
        analysis: _ComputedMethodBinding | None = None,
    ) -> None:
        snapshots = self._validated_snapshots()
        current = _compute(*snapshots) if analysis is None else analysis
        if type(current) is not _ComputedMethodBinding:
            raise TypeError("analysis must be an exact computed method binding")
        if serialize_all_atom_system(current.system) != snapshots[0]:
            raise LinearAlkaneEvaluationMethodBindingContractError(
                "analysis system does not match stored snapshot"
            )
        if (
            serialize_linear_alkane_c1_c4_parameter_set(current.parameter_set)
            != snapshots[1]
        ):
            raise LinearAlkaneEvaluationMethodBindingContractError(
                "analysis parameter set does not match stored snapshot"
            )
        if (
            serialize_linear_alkane_c1_c4_evaluation_method(current.method)
            != snapshots[2]
        ):
            raise LinearAlkaneEvaluationMethodBindingContractError(
                "analysis evaluation method does not match stored snapshot"
            )
        if (
            _serialize_input_execution_envelope(current.input_execution_envelope)
            != snapshots[3]
        ):
            raise LinearAlkaneEvaluationMethodBindingContractError(
                "analysis input envelope does not match stored snapshot"
            )
        if current.method_binding_status not in _FROZEN_STATUSES:
            raise ValueError("unknown method binding status")
        if tuple(code for code, _ in current.compatibility_results) != (
            _FROZEN_COMPATIBILITY_CODES
        ):
            raise LinearAlkaneEvaluationMethodBindingContractError(
                "analysis compatibility code order is inconsistent"
            )
        if not all(type(passed) is bool for _, passed in current.compatibility_results):
            raise TypeError("compatibility results must contain exact booleans")

    def _analysis(self) -> _ComputedMethodBinding:
        analysis = _compute(*self._validated_snapshots())
        self._validate(analysis)
        return analysis

    @property
    def assignment_status(self) -> str:
        return self._analysis().assignment_document["assignment_status"]

    @property
    def method_binding_status(self) -> str:
        return self._analysis().method_binding_status

    @property
    def compatibility_results(self) -> tuple[tuple[str, bool], ...]:
        return self._analysis().compatibility_results

    @property
    def failed_compatibility_codes(self) -> tuple[str, ...]:
        return tuple(
            code for code, passed in self.compatibility_results if not passed
        )

    @property
    def geometry_domain_assessment_status(self) -> str:
        return self._analysis().geometry_domain_assessment_status

    @property
    def bounded_contract_fixture_method_assignment_binding_complete(self) -> bool:
        return self.method_binding_status == "contract_fixture_method_bound"

    def _binding_document(
        self,
        analysis: _ComputedMethodBinding,
    ) -> dict[str, Any] | None:
        if analysis.method_binding_status != "contract_fixture_method_bound":
            return None
        assignment = analysis.assignment_document
        method = analysis.method
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "binding_policy_id": _FROZEN_BINDING_POLICY_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "canonical_system_snapshot_sha256": (
                self._canonical_system_snapshot_sha256
            ),
            "canonical_parameter_artifact_sha256": (
                self._canonical_parameter_snapshot_sha256
            ),
            "canonical_method_artifact_sha256": (
                self._canonical_method_snapshot_sha256
            ),
            "input_execution_envelope_sha256": (
                self._input_execution_envelope_snapshot_sha256
            ),
            "assignment_report_sha256": assignment["report_sha256"],
            "parameter_assignment_sha256": assignment[
                "parameter_assignment_sha256"
            ],
            "parameter_protocol_sha256": assignment[
                "parameter_protocol_sha256"
            ],
            "parameter_payload_sha256": assignment[
                "parameter_payload_sha256"
            ],
            "parameter_set_sha256": assignment["parameter_set_sha256"],
            "method_protocol_sha256": method.to_dict()["method_payload"][
                "protocol_sha256"
            ],
            "method_payload_sha256": method.method_payload_sha256,
            "evaluation_method_sha256": method.method_sha256,
            "compatibility_results": [
                {"code": code, "passed": passed}
                for code, passed in analysis.compatibility_results
            ],
            "geometry_domain_assessment_status": (
                analysis.geometry_domain_assessment_status
            ),
            "atom_assignment_count": assignment["atom_count"],
            "bond_assignment_count": assignment["bond_assignment_count"],
            "angle_assignment_count": assignment["angle_assignment_count"],
            "proper_assignment_count": assignment["proper_assignment_count"],
            "pair_assignment_count": assignment["pair_assignment_count"],
            "pair_class_counts": assignment["pair_class_counts"],
            "method_covered_nonexcluded_pair_count": (
                analysis.method_covered_nonexcluded_pair_count
            ),
        }

    @property
    def method_binding_sha256(self) -> str | None:
        analysis = self._analysis()
        document = self._binding_document(analysis)
        return None if document is None else _sha256_document(document)

    def _blockers(self, analysis: _ComputedMethodBinding) -> tuple[str, ...]:
        status_blocker = {
            "invalid_system": "canonical_input_invalid_for_bounded_upstream_contract",
            "unsupported_system": "chemistry_outside_bounded_c1_c4_domain",
            "method_incompatible": "input_or_geometry_incompatible_with_bounded_method",
            "contract_fixture_method_bound": None,
        }[analysis.method_binding_status]
        blockers = (
            "numeric_parameter_and_method_values_are_nonphysical_contract_fixtures",
            "geometry_domain_check_is_compatibility_only_no_energy_evaluation",
            "energy_force_and_virial_kernels_missing",
            "scientific_fit_reference_and_validation_missing",
            "licensed_method_provenance_and_review_missing",
            "bounded_n_le_14_direct_all_pair_reference_is_not_scaling_evidence",
            "cell_free_nonperiodic_cpu_float64_single_model_only",
            "production_parameterability_physics_runtime_and_claim_authority_prohibited",
            "digests_and_input_observations_are_binding_not_authentication",
        )
        return blockers if status_blocker is None else (status_blocker, *blockers)

    def _core_dict(self, analysis: _ComputedMethodBinding) -> dict[str, Any]:
        assignment = analysis.assignment_document
        method = analysis.method
        method_document = method.to_dict()
        method_payload = method_document["method_payload"]
        binding_document = self._binding_document(analysis)
        assignment_mapped = (
            assignment["assignment_status"] == "contract_fixture_mapped"
        )
        geometry_assessed = analysis.geometry_domain_assessment_status in {
            "passed_bounded_domain_check_no_evaluation",
            "failed_nonfinite_intermediate",
            "failed_singularity_threshold",
        }
        bound = analysis.method_binding_status == "contract_fixture_method_bound"
        return {
            "schema_id": _FROZEN_SCHEMA_ID,
            "schema_version": _FROZEN_SCHEMA_VERSION,
            "binding_policy_id": _FROZEN_BINDING_POLICY_ID,
            "claim_scope": _FROZEN_CLAIM_SCOPE,
            "canonical_system_snapshot_sha256": (
                self._canonical_system_snapshot_sha256
            ),
            "canonical_parameter_artifact_sha256": (
                self._canonical_parameter_snapshot_sha256
            ),
            "canonical_method_artifact_sha256": (
                self._canonical_method_snapshot_sha256
            ),
            "input_execution_envelope": dict(
                analysis.input_execution_envelope
            ),
            "input_execution_envelope_sha256": (
                self._input_execution_envelope_snapshot_sha256
            ),
            "input_execution_envelope_authentication_status": (
                "digest_bound_not_authenticated"
            ),
            "canonical_snapshot_coordinates_device_type": "cpu",
            "device_preservation_status": (
                "original_device_observed_separately_not_snapshot_encoded"
            ),
            "source_format": assignment["source_format"],
            "source_sha256": assignment["source_sha256"],
            "source_authentication_status": assignment[
                "source_authentication_status"
            ],
            "canonical_topology_sha256": assignment[
                "canonical_topology_sha256"
            ],
            "applicability_report_sha256": assignment[
                "applicability_report_sha256"
            ],
            "typing_report_sha256": assignment["typing_report_sha256"],
            "inventory_report_sha256": assignment["inventory_report_sha256"],
            "pair_classification_policy_id": assignment[
                "pair_classification_policy_id"
            ],
            "assignment_schema_id": _FROZEN_ASSIGNMENT_SCHEMA_ID,
            "assignment_policy_id": _FROZEN_ASSIGNMENT_POLICY_ID,
            "assignment_report_sha256": assignment["report_sha256"],
            "parameter_assignment_sha256": assignment[
                "parameter_assignment_sha256"
            ],
            "parameter_protocol_sha256": assignment[
                "parameter_protocol_sha256"
            ],
            "parameter_set_schema_id": _FROZEN_PARAMETER_SET_SCHEMA_ID,
            "parameter_set_id": assignment["parameter_set_id"],
            "parameter_set_version": assignment["parameter_set_version"],
            "parameter_payload_sha256": assignment[
                "parameter_payload_sha256"
            ],
            "parameter_set_sha256": assignment["parameter_set_sha256"],
            "force_field_unit_system_id": assignment[
                "force_field_unit_system_id"
            ],
            "method_protocol_schema_id": _FROZEN_METHOD_PROTOCOL_SCHEMA_ID,
            "method_protocol_sha256": method_payload["protocol_sha256"],
            "method_schema_id": _FROZEN_METHOD_SCHEMA_ID,
            "method_id": method.method_id,
            "method_version": method.method_version,
            "method_payload_sha256": method.method_payload_sha256,
            "evaluation_method_sha256": method.method_sha256,
            "assignment_status": assignment["assignment_status"],
            "method_binding_status": analysis.method_binding_status,
            "compatibility_results": [
                {"code": code, "passed": passed}
                for code, passed in analysis.compatibility_results
            ],
            "failed_compatibility_codes": [
                code
                for code, passed in analysis.compatibility_results
                if not passed
            ],
            "geometry_domain_assessment_status": (
                analysis.geometry_domain_assessment_status
            ),
            "atom_assignment_count": (
                assignment["atom_count"] if assignment_mapped else 0
            ),
            "bond_assignment_count": assignment["bond_assignment_count"],
            "angle_assignment_count": assignment["angle_assignment_count"],
            "proper_assignment_count": assignment["proper_assignment_count"],
            "pair_assignment_count": assignment["pair_assignment_count"],
            "pair_class_counts": assignment["pair_class_counts"],
            "excluded_pair_count": assignment["excluded_pair_count"],
            "mapped_nonexcluded_pair_count": assignment[
                "mapped_nonexcluded_pair_count"
            ],
            "method_covered_nonexcluded_pair_count": (
                analysis.method_covered_nonexcluded_pair_count
            ),
            "bounded_nonphysical_evaluation_method_contract_complete": True,
            "bounded_contract_fixture_assignment_complete": assignment_mapped,
            "bounded_contract_fixture_geometry_domain_assessed": (
                geometry_assessed
            ),
            "bounded_contract_fixture_method_assignment_binding_complete": bound,
            "evaluation_executed": False,
            "energy_evaluated": False,
            "forces_evaluated": False,
            "virial_evaluated": False,
            "production_evaluation_method_defined": False,
            "production_parameter_assignment_complete": False,
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
            "method_binding_sha256": (
                None
                if binding_document is None
                else _sha256_document(binding_document)
            ),
            "blockers": list(self._blockers(analysis)),
        }

    @property
    def report_sha256(self) -> str:
        return _sha256_document(self._core_dict(self._analysis()))

    def to_dict(self) -> dict[str, Any]:
        document = self._core_dict(self._analysis())
        document["report_sha256"] = _sha256_document(document)
        return document

    def matches(
        self,
        system: AllAtomSystem,
        parameter_set: LinearAlkaneC1C4ParameterSet,
        method: LinearAlkaneC1C4EvaluationMethod,
    ) -> bool:
        if type(system) is not AllAtomSystem:
            raise TypeError("system must be an exact AllAtomSystem")
        if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
            raise TypeError("parameter_set must be an exact C1-C4 parameter set")
        if type(method) is not LinearAlkaneC1C4EvaluationMethod:
            raise TypeError("method must be an exact C1-C4 evaluation method")
        self._analysis()
        return (
            self._canonical_system_snapshot == serialize_all_atom_system(system)
            and self._canonical_parameter_snapshot
            == serialize_linear_alkane_c1_c4_parameter_set(parameter_set)
            and self._canonical_method_snapshot
            == serialize_linear_alkane_c1_c4_evaluation_method(method)
            and self._input_execution_envelope_snapshot
            == _serialize_input_execution_envelope(
                _observe_input_execution_envelope(system)
            )
        )

    def _replay_for_bounded_scalar_energy_diagnostic(
        self,
    ) -> _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay:
        """Return one fresh, same-analysis capsule for the scalar diagnostic.

        The capsule is reconstructed from immutable snapshots and carries the
        exact binding-report and live-envelope bytes produced from that same
        analysis. Downstream code must still require the scoped bound status
        and must not treat this replay API as runtime authorization.
        """

        analysis = self._analysis()
        document = self._core_dict(analysis)
        document["report_sha256"] = _sha256_document(document)
        return _LinearAlkaneC1C4ScalarEnergyDiagnosticReplay(
            system=analysis.system,
            parameter_set=analysis.parameter_set,
            method=analysis.method,
            assignment_report=analysis.assignment_report,
            canonical_system_snapshot_bytes=bytes(
                self._canonical_system_snapshot
            ),
            canonical_parameter_artifact_bytes=bytes(
                self._canonical_parameter_snapshot
            ),
            canonical_method_artifact_bytes=bytes(
                self._canonical_method_snapshot
            ),
            input_execution_envelope_bytes=bytes(
                self._input_execution_envelope_snapshot
            ),
            binding_report_bytes=_canonical_json_bytes(document),
            compatibility_results=analysis.compatibility_results,
            method_binding_status=analysis.method_binding_status,
            geometry_domain_assessment_status=(
                analysis.geometry_domain_assessment_status
            ),
        )


def analyze_linear_alkane_c1_c4_evaluation_method_binding(
    system: AllAtomSystem,
    parameter_set: LinearAlkaneC1C4ParameterSet,
    method: LinearAlkaneC1C4EvaluationMethod,
) -> LinearAlkaneC1C4EvaluationMethodBindingReport:
    """Bind the bounded method to a fresh assignment without evaluation."""

    if type(system) is not AllAtomSystem:
        raise TypeError("system must be an exact AllAtomSystem")
    if type(parameter_set) is not LinearAlkaneC1C4ParameterSet:
        raise TypeError("parameter_set must be an exact C1-C4 parameter set")
    if type(method) is not LinearAlkaneC1C4EvaluationMethod:
        raise TypeError("method must be an exact C1-C4 evaluation method")
    return LinearAlkaneC1C4EvaluationMethodBindingReport(
        system,
        parameter_set,
        method,
    )


def serialize_linear_alkane_c1_c4_evaluation_method_binding_report(
    report: LinearAlkaneC1C4EvaluationMethodBindingReport,
) -> bytes:
    """Serialize a fresh validated binding report to canonical JSON."""

    if type(report) is not LinearAlkaneC1C4EvaluationMethodBindingReport:
        raise TypeError("report must be an exact C1-C4 method binding report")
    report._validate()
    return _canonical_json_bytes(report.to_dict())


__all__ = [
    "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_CLAIM_SCOPE",
    "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_POLICY_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_ID",
    "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_SCHEMA_VERSION",
    "LINEAR_ALKANE_EVALUATION_METHOD_BINDING_STATUSES",
    "LinearAlkaneC1C4EvaluationMethodBindingReport",
    "LinearAlkaneEvaluationMethodBindingContractError",
    "analyze_linear_alkane_c1_c4_evaluation_method_binding",
    "serialize_linear_alkane_c1_c4_evaluation_method_binding_report",
]
