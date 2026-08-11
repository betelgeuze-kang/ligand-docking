"""Source-bound deterministic geometry for the frozen mixed64 proposal profile.

The module implements two bounded, result-independent proposal primitives:

* one index-stable low-discrepancy SO(3) orientation selected by a fixed64 slot;
* one single-anchor rigid placement selected from the slot's exact feature receipts.

Both receipts retain their complete binary64 coordinate inputs and outputs.  A
reviewer can therefore replay the transform and, for anchor placements, the
full Cartesian geometric precheck without consulting a caller-supplied probe.
The implementation never scores, ranks, refines, or executes a molecular
benchmark and grants no experiment, product, Stage 0, or public-claim authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
import hashlib
import json
import math
import re
from typing import Final, Iterable, Sequence

from .geometric_admission_v2 import (
    HARD_REJECTION_MINIMUM_VDW_RATIO,
    GeometricAdmissionMetricsV2,
    GeometricAdmissionV2Error,
    evaluate_geometric_admission_metrics_one_python,
)
from .global_orientation import (
    GlobalOrientationConfig,
    GlobalOrientationError,
    Quaternion,
    generate_global_orientation_batch,
    rotate_vector,
)
from .mixed64_allocation import (
    ANCHOR_AROMATIC_PLANE,
    ANCHOR_COMPLEMENTARY_CHARGE,
    ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
    ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
    ANCHOR_PRINCIPAL_AXIS_SHAPE,
    FEATURE_LIGAND_ACCEPTOR,
    FEATURE_LIGAND_AROMATIC_PLANE,
    FEATURE_LIGAND_DONOR,
    FEATURE_LIGAND_NEGATIVE_SITE,
    FEATURE_LIGAND_POSITIVE_SITE,
    FEATURE_LIGAND_SHAPE_AXIS,
    FEATURE_POCKET_SHAPE_AXIS,
    FEATURE_RECEPTOR_ACCEPTOR,
    FEATURE_RECEPTOR_AROMATIC_PLANE,
    FEATURE_RECEPTOR_DONOR,
    FEATURE_RECEPTOR_NEGATIVE_SITE,
    FEATURE_RECEPTOR_POSITIVE_SITE,
    GENERATION_PARENT_GENERATOR_INPUT,
    LANE_AROMATIC_PLANE,
    LANE_COMPLEMENTARY_CHARGE,
    LANE_DETERMINISTIC_INDEPENDENT_SO3,
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
    LANE_PRINCIPAL_AXIS_SHAPE,
    LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
    FixedMixed64Allocation,
    Mixed64AtomicFeatureEvidence,
)


MIXED64_INDEXED_SO3_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_indexed_so3_placement/1.0.0"
)
MIXED64_SINGLE_ANCHOR_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_single_anchor_placement/1.0.0"
)
MIXED64_PROPOSAL_GEOMETRY_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_geometry_v3/1.0.0"
)
MIXED64_INDEXED_SO3_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_mixed64_indexed_source_bound_so3/1.0.0"
)
MIXED64_SINGLE_ANCHOR_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_mixed64_single_anchor_rigid_placement/1.0.0"
)

SOURCE_COORDINATE_IDENTITY_MISMATCH: Final = "source_coordinate_identity_mismatch"
RECEPTOR_COORDINATE_IDENTITY_MISMATCH: Final = (
    "receptor_coordinate_identity_mismatch"
)
SOURCE_RECEIPT_IDENTITY_MISMATCH: Final = "source_receipt_identity_mismatch"
SOURCE_PROPOSAL_IDENTITY_MISMATCH: Final = "source_proposal_identity_mismatch"
ALLOCATION_SLOT_NOT_ELIGIBLE: Final = "allocation_slot_not_generation_eligible"
UNSUPPORTED_GEOMETRY_LANE: Final = "unsupported_mixed64_geometry_lane"
FEATURE_RECEIPT_CROSS_WIRING: Final = "selected_feature_receipt_cross_wiring"
FEATURE_ATOM_INDEX_OUT_OF_RANGE: Final = "feature_atom_index_out_of_range"
DEGENERATE_SO3_SOURCE_GEOMETRY: Final = "degenerate_so3_source_geometry"
DEGENERATE_LIGAND_DIRECTION: Final = "degenerate_ligand_anchor_direction"
DEGENERATE_RECEPTOR_DIRECTION: Final = "degenerate_receptor_anchor_direction"
DEGENERATE_LOCAL_SURFACE_NORMAL: Final = "degenerate_local_surface_normal"
DEGENERATE_AROMATIC_PLANE: Final = "degenerate_aromatic_plane"
DEGENERATE_PRINCIPAL_AXIS: Final = "degenerate_principal_axis"
GEOMETRIC_PRECHECK_INPUT_INVALID: Final = "geometric_precheck_input_invalid"

MAX_LIGAND_ATOMS: Final = 512
MAX_RECEPTOR_ATOMS: Final = 4096
MAX_ABSOLUTE_COORDINATE_ANGSTROM: Final = 100_000.0
MAX_CANONICAL_RECEIPT_BYTES: Final = 32 * 1024 * 1024
_EPSILON: Final = 1.0e-12
_AROMATIC_POCKET_FACING_MINIMUM_ABSOLUTE_COSINE: Final = _EPSILON
_PRINCIPAL_AXIS_JACOBI_MAX_ROTATIONS: Final = 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Vector3 = tuple[float, float, float]
Coordinates = tuple[Vector3, ...]

_ANCHOR_LANE_KIND: Final = {
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: (
        ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR
    ),
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: (
        ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR
    ),
    LANE_COMPLEMENTARY_CHARGE: ANCHOR_COMPLEMENTARY_CHARGE,
    LANE_AROMATIC_PLANE: ANCHOR_AROMATIC_PLANE,
    LANE_PRINCIPAL_AXIS_SHAPE: ANCHOR_PRINCIPAL_AXIS_SHAPE,
}
_ANCHOR_TARGET_DISTANCE_ANGSTROM: Final = {
    ANCHOR_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: 2.9,
    ANCHOR_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: 2.9,
    ANCHOR_COMPLEMENTARY_CHARGE: 3.5,
    ANCHOR_AROMATIC_PLANE: 3.8,
    ANCHOR_PRINCIPAL_AXIS_SHAPE: 3.0,
}
_ANCHOR_LANE_WIDTH: Final = {
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: 4,
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: 4,
    LANE_COMPLEMENTARY_CHARGE: 4,
    LANE_AROMATIC_PLANE: 2,
    LANE_PRINCIPAL_AXIS_SHAPE: 2,
}
_ANCHOR_FEATURE_KIND_PAIRS: Final = {
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR: (
        (FEATURE_LIGAND_DONOR, FEATURE_RECEPTOR_ACCEPTOR),
    ),
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR: (
        (FEATURE_LIGAND_ACCEPTOR, FEATURE_RECEPTOR_DONOR),
    ),
    LANE_COMPLEMENTARY_CHARGE: (
        (FEATURE_LIGAND_POSITIVE_SITE, FEATURE_RECEPTOR_NEGATIVE_SITE),
        (FEATURE_LIGAND_NEGATIVE_SITE, FEATURE_RECEPTOR_POSITIVE_SITE),
    ),
    LANE_AROMATIC_PLANE: (
        (FEATURE_LIGAND_AROMATIC_PLANE, FEATURE_RECEPTOR_AROMATIC_PLANE),
    ),
    LANE_PRINCIPAL_AXIS_SHAPE: (
        (FEATURE_LIGAND_SHAPE_AXIS, FEATURE_POCKET_SHAPE_AXIS),
    ),
}


class Mixed64ProposalGeometryError(ValueError):
    """Typed fail-closed error suitable for a denominator-preserving producer."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise Mixed64ProposalGeometryError(code, message)


def _canonical_bytes(value: object) -> bytes:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) > MAX_CANONICAL_RECEIPT_BYTES:
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, "receipt exceeds bounded capacity")
    return encoded


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def frozen_mixed64_proposal_geometry_policy() -> dict[str, object]:
    """Return a fresh canonical projection of the non-authoritative policy."""

    return {
        "schema_id": "betelgeuze.engine_v2_mixed64_proposal_geometry_policy/1.0.0",
        "component_id": MIXED64_PROPOSAL_GEOMETRY_COMPONENT_ID,
        "indexed_so3": {
            "profile_id": MIXED64_INDEXED_SO3_PROFILE_ID,
            "lanes": [
                LANE_DETERMINISTIC_INDEPENDENT_SO3,
                LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
            ],
            "translation_shell_radii_binary64_hex": [],
            "translation_points_per_shell": 1,
            "minimum_receptor_distance_binary64_hex": (0.0).hex(),
            "index_selected_by_allocation_only": True,
            "source_seeded": True,
            "prefix_stable": True,
            "duplicate_orientation_elimination_required": True,
        },
        "single_anchor": {
            "profile_id": MIXED64_SINGLE_ANCHOR_PROFILE_ID,
            "profiles": [
                {
                    "lane": lane,
                    "anchor_kind": _ANCHOR_LANE_KIND[lane],
                    "target_distance_angstrom_binary64_hex": (
                        _ANCHOR_TARGET_DISTANCE_ANGSTROM[
                            _ANCHOR_LANE_KIND[lane]
                        ].hex()
                    ),
                    "twist_variant_count": _ANCHOR_LANE_WIDTH[lane],
                    "twist_rule": "two_pi_times_lane_offset_over_lane_width",
                }
                for lane in (
                    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
                    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
                    LANE_COMPLEMENTARY_CHARGE,
                    LANE_AROMATIC_PLANE,
                    LANE_PRINCIPAL_AXIS_SHAPE,
                )
            ],
            "hard_rejection_minimum_vdw_ratio_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
            ),
            "full_cartesian_geometric_precheck_required": True,
            "severe_penetration_slot_preserved": True,
            "fallback_lane_allowed": False,
            "multi_anchor_allowed": False,
            "result_dependent_feature_selection_allowed": False,
            "aromatic_pocket_facing_minimum_absolute_cosine_binary64_hex": (
                _AROMATIC_POCKET_FACING_MINIMUM_ABSOLUTE_COSINE.hex()
            ),
            "principal_axis_solver": "symmetric_jacobi_largest_off_diagonal",
            "principal_axis_jacobi_max_rotations": (
                _PRINCIPAL_AXIS_JACOBI_MAX_ROTATIONS
            ),
            "principal_axis_relative_tolerance_binary64_hex": _EPSILON.hex(),
        },
        "evidence": {
            "complete_source_and_output_coordinates_required": True,
            "allocation_and_slot_receipts_required": True,
            "selected_feature_receipts_required": True,
            "target_distance_direction_surface_normal_approach_required": True,
            "exact_pair_count_required": True,
            "bounded_iterable_normalization_before_materialization": True,
            "maximum_ligand_atoms": MAX_LIGAND_ATOMS,
            "maximum_receptor_atoms": MAX_RECEPTOR_ATOMS,
        },
        "authority": {
            "reservation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_ab_authorized": False,
            "fresh_holdout_authorized": False,
            "product_mutation_authorized": False,
            "stage0_admission_authorized": False,
            "public_benchmark_authorized": False,
            "scientific_claim_authorized": False,
            "github_actions_production_authority_allowed": False,
            "test_double_production_authority_allowed": False,
        },
        "status": "synthetic_pre_activation_geometry_only",
    }


MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256: Final = _sha256(
    frozen_mixed64_proposal_geometry_policy()
)


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be a lowercase SHA-256")
    return value


def _finite(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be a finite number")
    observed = float(value)
    if not math.isfinite(observed):
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be finite")
    return observed


def _vector(value: Sequence[float], *, name: str) -> Vector3:
    if isinstance(value, (str, bytes, bytearray)) or len(value) != 3:
        _fail(
            GEOMETRIC_PRECHECK_INPUT_INVALID,
            f"{name} must contain exactly three coordinates",
        )
    observed = tuple(
        _finite(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )
    if any(abs(component) > MAX_ABSOLUTE_COORDINATE_ANGSTROM for component in observed):
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} exceeds coordinate bounds")
    return observed  # type: ignore[return-value]


def _coordinates(
    value: Iterable[Sequence[float]],
    *,
    name: str,
    maximum_count: int,
) -> Coordinates:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be an iterable")
    iterator = iter(value)
    rows = []
    for index in range(maximum_count + 1):
        try:
            row = next(iterator)
        except StopIteration:
            break
        rows.append(_vector(row, name=f"{name}[{index}]"))
    if not rows or len(rows) > maximum_count:
        _fail(
            GEOMETRIC_PRECHECK_INPUT_INVALID,
            f"{name} count must be within [1, {maximum_count}]",
        )
    return tuple(rows)


def _float_tuple(
    value: Iterable[float],
    *,
    name: str,
    expected_count: int,
) -> tuple[float, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be an iterable")
    iterator = iter(value)
    observed = []
    for index in range(expected_count + 1):
        try:
            item = next(iterator)
        except StopIteration:
            break
        observed.append(_finite(item, name=f"{name}[{index}]"))
    if len(observed) != expected_count:
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} denominator changed")
    return tuple(observed)


def _bool_tuple(
    value: Iterable[bool],
    *,
    name: str,
    expected_count: int,
) -> tuple[bool, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must be an iterable")
    iterator = iter(value)
    observed = []
    for _ in range(expected_count + 1):
        try:
            item = next(iterator)
        except StopIteration:
            break
        if type(item) is not bool:
            _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} must contain booleans")
        observed.append(item)
    if len(observed) != expected_count:
        _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, f"{name} denominator changed")
    return tuple(observed)


def _projection_vector(value: Vector3) -> list[str]:
    return [component.hex() for component in value]


def _projection_coordinates(value: Coordinates) -> list[list[str]]:
    return [_projection_vector(point) for point in value]


def coordinate_sha256(value: Iterable[Sequence[float]]) -> str:
    """Return the canonical binary64 coordinate identity used by admission v2."""

    coordinates = _coordinates(
        value,
        name="coordinates",
        maximum_count=MAX_RECEPTOR_ATOMS,
    )
    return _sha256(_projection_coordinates(coordinates))


def _add(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _subtract(left: Vector3, right: Vector3) -> Vector3:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _scale(value: Vector3, factor: float) -> Vector3:
    return (value[0] * factor, value[1] * factor, value[2] * factor)


def _dot(left: Vector3, right: Vector3) -> float:
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2]


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _norm(value: Vector3) -> float:
    return math.sqrt(_dot(value, value))


def _normalize(value: Vector3, *, code: str, name: str) -> Vector3:
    length = _norm(value)
    if length <= _EPSILON:
        _fail(code, f"{name} is degenerate")
    return _scale(value, 1.0 / length)


def _centroid(coordinates: Coordinates) -> Vector3:
    inverse = 1.0 / len(coordinates)
    return (
        sum(point[0] for point in coordinates) * inverse,
        sum(point[1] for point in coordinates) * inverse,
        sum(point[2] for point in coordinates) * inverse,
    )


def _canonical_direction(value: Vector3, *, code: str, name: str) -> Vector3:
    normalized = _normalize(value, code=code, name=name)
    for component in normalized:
        if abs(component) <= _EPSILON:
            continue
        if component < 0.0:
            return _scale(normalized, -1.0)
        break
    return normalized


def _quaternion_normalize(value: Quaternion) -> Quaternion:
    length = math.sqrt(sum(component * component for component in value))
    if length <= _EPSILON:
        _fail(DEGENERATE_LIGAND_DIRECTION, "quaternion is degenerate")
    normalized = tuple(component / length for component in value)
    for component in reversed(normalized):
        if component > 0.0:
            break
        if component < 0.0:
            normalized = tuple(-item for item in normalized)
            break
    return tuple(0.0 if item == 0.0 else item for item in normalized)  # type: ignore[return-value]


def _quaternion_axis_angle(axis: Vector3, angle: float) -> Quaternion:
    unit = _normalize(axis, code=DEGENERATE_LIGAND_DIRECTION, name="twist axis")
    half = angle * 0.5
    sine = math.sin(half)
    return _quaternion_normalize(
        (unit[0] * sine, unit[1] * sine, unit[2] * sine, math.cos(half))
    )


def _quaternion_between(source: Vector3, target: Vector3) -> Quaternion:
    source_unit = _normalize(
        source,
        code=DEGENERATE_LIGAND_DIRECTION,
        name="ligand interaction direction",
    )
    target_unit = _normalize(
        target,
        code=DEGENERATE_RECEPTOR_DIRECTION,
        name="receptor interaction target direction",
    )
    cosine = max(-1.0, min(1.0, _dot(source_unit, target_unit)))
    if cosine >= 1.0 - 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0)
    if cosine <= -1.0 + 1.0e-12:
        fallback = (1.0, 0.0, 0.0)
        if abs(_dot(source_unit, fallback)) > 0.9:
            fallback = (0.0, 1.0, 0.0)
        axis = _normalize(
            _cross(source_unit, fallback),
            code=DEGENERATE_LIGAND_DIRECTION,
            name="opposite-direction rotation axis",
        )
        return _quaternion_axis_angle(axis, math.pi)
    axis = _cross(source_unit, target_unit)
    return _quaternion_normalize((axis[0], axis[1], axis[2], 1.0 + cosine))


def _quaternion_multiply(left: Quaternion, right: Quaternion) -> Quaternion:
    lx, ly, lz, lw = left
    rx, ry, rz, rw = right
    return _quaternion_normalize(
        (
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
            lw * rw - lx * rx - ly * ry - lz * rz,
        )
    )


def _feature_coordinates(
    feature: Mixed64AtomicFeatureEvidence,
    coordinates: Coordinates,
    *,
    role: str,
) -> Coordinates:
    if any(index >= len(coordinates) for index in feature.atom_indices):
        _fail(
            FEATURE_ATOM_INDEX_OUT_OF_RANGE,
            f"{role} feature atom index exceeds coordinate denominator",
        )
    return tuple(coordinates[index] for index in feature.atom_indices)


def _aromatic_normal(coordinates: Coordinates, *, role: str) -> Vector3:
    for first, second, third in combinations(coordinates, 3):
        normal = _cross(_subtract(second, first), _subtract(third, first))
        if _norm(normal) > _EPSILON:
            return _canonical_direction(
                normal,
                code=DEGENERATE_AROMATIC_PLANE,
                name=f"{role} aromatic plane",
            )
    _fail(DEGENERATE_AROMATIC_PLANE, f"{role} aromatic plane is collinear")


def _principal_axis(coordinates: Coordinates, *, role: str) -> Vector3:
    center = _centroid(coordinates)
    centered = tuple(_subtract(point, center) for point in coordinates)
    covariance = tuple(
        tuple(sum(point[row] * point[column] for point in centered) for column in range(3))
        for row in range(3)
    )
    diagonal = tuple(covariance[index][index] for index in range(3))
    if max(diagonal) <= _EPSILON:
        _fail(DEGENERATE_PRINCIPAL_AXIS, f"{role} principal-axis variance is zero")

    matrix = [list(row) for row in covariance]
    eigenvectors = [
        [1.0 if row == column else 0.0 for column in range(3)]
        for row in range(3)
    ]
    pairs = ((0, 1), (0, 2), (1, 2))
    for _ in range(_PRINCIPAL_AXIS_JACOBI_MAX_ROTATIONS):
        first, second = max(
            pairs,
            key=lambda pair: (
                abs(matrix[pair[0]][pair[1]]),
                -pair[0],
                -pair[1],
            ),
        )
        off_diagonal = abs(matrix[first][second])
        scale = max(abs(matrix[index][index]) for index in range(3))
        if off_diagonal <= _EPSILON * scale:
            break
        angle = 0.5 * math.atan2(
            2.0 * matrix[first][second],
            matrix[second][second] - matrix[first][first],
        )
        cosine = math.cos(angle)
        sine = math.sin(angle)
        rotation = [
            [1.0 if row == column else 0.0 for column in range(3)]
            for row in range(3)
        ]
        rotation[first][first] = cosine
        rotation[second][second] = cosine
        rotation[first][second] = sine
        rotation[second][first] = -sine
        right_product = [
            [
                sum(matrix[row][inner] * rotation[inner][column] for inner in range(3))
                for column in range(3)
            ]
            for row in range(3)
        ]
        matrix = [
            [
                sum(
                    rotation[inner][row] * right_product[inner][column]
                    for inner in range(3)
                )
                for column in range(3)
            ]
            for row in range(3)
        ]
        eigenvectors = [
            [
                sum(
                    eigenvectors[row][inner] * rotation[inner][column]
                    for inner in range(3)
                )
                for column in range(3)
            ]
            for row in range(3)
        ]
    dominant_index = max(
        range(3),
        key=lambda index: (matrix[index][index], -index),
    )
    vector: Vector3 = tuple(
        eigenvectors[row][dominant_index] for row in range(3)
    )  # type: ignore[assignment]
    vector = _normalize(
        vector,
        code=DEGENERATE_PRINCIPAL_AXIS,
        name=f"{role} principal axis",
    )
    transformed: Vector3 = tuple(
        sum(covariance[row][column] * vector[column] for column in range(3))
        for row in range(3)
    )  # type: ignore[assignment]
    rayleigh = _dot(vector, transformed)
    residual = _norm(_subtract(transformed, _scale(vector, rayleigh)))
    if residual > _EPSILON * max(_EPSILON, abs(rayleigh)):
        _fail(DEGENERATE_PRINCIPAL_AXIS, f"{role} principal-axis solver did not converge")
    return _canonical_direction(
        vector,
        code=DEGENERATE_PRINCIPAL_AXIS,
        name=f"{role} principal axis",
    )


def _selected_anchor_features(
    allocation: FixedMixed64Allocation,
    *,
    slot_index: int,
) -> tuple[Mixed64AtomicFeatureEvidence, Mixed64AtomicFeatureEvidence]:
    slot = allocation.slots[slot_index]
    if len(slot.selected_source_receipt_sha256s) != 2:
        _fail(FEATURE_RECEIPT_CROSS_WIRING, "anchor slot does not select two features")
    by_receipt = {
        feature.receipt_sha256: feature for feature in allocation.features.atomic_features
    }
    try:
        first, second = tuple(
            by_receipt[receipt] for receipt in slot.selected_source_receipt_sha256s
        )
    except KeyError:
        _fail(FEATURE_RECEIPT_CROSS_WIRING, "selected feature receipt is absent")
    allowed_pairs = _ANCHOR_FEATURE_KIND_PAIRS.get(slot.lane, ())
    if (first.kind, second.kind) not in allowed_pairs:
        _fail(FEATURE_RECEIPT_CROSS_WIRING, "selected feature kinds cross lanes")
    return first, second


def _validate_slot(
    allocation: FixedMixed64Allocation,
    *,
    slot_index: int,
    allowed_lanes: set[str],
) -> None:
    if type(allocation) is not FixedMixed64Allocation:
        raise TypeError("allocation must be the exact FixedMixed64Allocation type")
    if type(slot_index) is not int or not 0 <= slot_index < len(allocation.slots):
        _fail(UNSUPPORTED_GEOMETRY_LANE, "slot index is outside fixed64")
    slot = allocation.slots[slot_index]
    if slot.slot_index != slot_index:
        _fail(UNSUPPORTED_GEOMETRY_LANE, "allocation slot ordering changed")
    if slot.lane not in allowed_lanes:
        _fail(UNSUPPORTED_GEOMETRY_LANE, f"slot lane {slot.lane!r} is unsupported")
    if not slot.generation_eligible:
        _fail(ALLOCATION_SLOT_NOT_ELIGIBLE, "slot retains typed feature failures")


def _validate_exact_source(
    allocation: FixedMixed64Allocation,
    *,
    source_proposal_sha256: str,
    source_coordinate_sha256: str,
    source_receipt_sha256: str,
    receptor_coordinate_sha256: str | None = None,
) -> None:
    proposal = _digest(source_proposal_sha256, name="source_proposal_sha256")
    coordinate = _digest(source_coordinate_sha256, name="source_coordinate_sha256")
    source = _digest(source_receipt_sha256, name="source_receipt_sha256")
    exact = allocation.features.exact_v11_source
    if source != exact.source_receipt_sha256:
        _fail(
            SOURCE_RECEIPT_IDENTITY_MISMATCH,
            "source is not the exact V1.1 receipt",
        )
    if proposal != exact.proposal_sha256:
        _fail(
            SOURCE_PROPOSAL_IDENTITY_MISMATCH,
            "source proposal is not bound by the exact V1.1 evidence",
        )
    if coordinate != exact.ligand_coordinate_sha256:
        _fail(
            SOURCE_COORDINATE_IDENTITY_MISMATCH,
            "source coordinates are not bound by the exact V1.1 evidence",
        )
    if receptor_coordinate_sha256 is not None and _digest(
        receptor_coordinate_sha256,
        name="receptor_coordinate_sha256",
    ) != exact.receptor_coordinate_sha256:
        _fail(
            RECEPTOR_COORDINATE_IDENTITY_MISMATCH,
            "receptor coordinates are not bound by the exact V1.1 evidence",
        )


@dataclass(frozen=True, slots=True)
class IndexedSO3PlacementReceiptV1:
    """One fixed slot's exact source-bound low-discrepancy SO(3) placement."""

    allocation: FixedMixed64Allocation = field(repr=False)
    slot_index: int
    source_proposal_sha256: str
    source_coordinate_sha256: str
    source_receipt_sha256: str
    source_coordinates: Coordinates = field(repr=False)
    pocket_center: Vector3
    pocket_normal: Vector3
    profile_id: str = MIXED64_INDEXED_SO3_PROFILE_ID
    schema_id: str = MIXED64_INDEXED_SO3_SCHEMA_ID
    output_coordinates: Coordinates = field(init=False, repr=False)
    quaternion: Quaternion = field(init=False)
    translation: Vector3 = field(init=False)
    raw_sequence_index: int = field(init=False)
    accepted_sequence_index: int = field(init=False)
    source_seed_sha256: str = field(init=False)
    global_orientation_batch_receipt_sha256: str = field(init=False)
    global_orientation_slot_receipt_sha256: str = field(init=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_INDEXED_SO3_SCHEMA_ID:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "indexed SO3 schema changed")
        if self.profile_id != MIXED64_INDEXED_SO3_PROFILE_ID:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "indexed SO3 profile changed")
        _validate_slot(
            self.allocation,
            slot_index=self.slot_index,
            allowed_lanes={
                LANE_DETERMINISTIC_INDEPENDENT_SO3,
                LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
            },
        )
        slot = self.allocation.slots[self.slot_index]
        if slot.so3_sequence_index is None:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "slot lacks a frozen SO3 index")
        source_proposal = _digest(
            self.source_proposal_sha256,
            name="source_proposal_sha256",
        )
        source_coordinate = _digest(
            self.source_coordinate_sha256,
            name="source_coordinate_sha256",
        )
        source_receipt = _digest(
            self.source_receipt_sha256,
            name="source_receipt_sha256",
        )
        coordinates = _coordinates(
            self.source_coordinates,
            name="source_coordinates",
            maximum_count=MAX_LIGAND_ATOMS,
        )
        if coordinate_sha256(coordinates) != source_coordinate:
            _fail(SOURCE_COORDINATE_IDENTITY_MISMATCH, "SO3 source coordinates changed")
        if slot.lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
            if slot.generation_parent_role != GENERATION_PARENT_GENERATOR_INPUT:
                _fail(SOURCE_PROPOSAL_IDENTITY_MISMATCH, "conformer parent role changed")
            if source_proposal != slot.selected_generation_parent_proposal_sha256:
                _fail(SOURCE_PROPOSAL_IDENTITY_MISMATCH, "conformer proposal changed")
            if source_coordinate != slot.selected_generation_parent_coordinate_sha256:
                _fail(SOURCE_COORDINATE_IDENTITY_MISMATCH, "conformer coordinates changed")
            if (source_receipt,) != slot.selected_source_receipt_sha256s:
                _fail(SOURCE_RECEIPT_IDENTITY_MISMATCH, "conformer receipt changed")
        else:
            _validate_exact_source(
                self.allocation,
                source_proposal_sha256=source_proposal,
                source_coordinate_sha256=source_coordinate,
                source_receipt_sha256=source_receipt,
            )
        center = _vector(self.pocket_center, name="pocket_center")
        normal = _normalize(
            _vector(self.pocket_normal, name="pocket_normal"),
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="pocket normal",
        )
        try:
            batch = generate_global_orientation_batch(
                coordinates,
                pocket_center=center,
                pocket_normal=normal,
                config=GlobalOrientationConfig(
                    orientation_count=slot.so3_sequence_index + 1,
                    translation_shell_radii=(),
                    translation_points_per_shell=1,
                    minimum_receptor_distance=0.0,
                ),
                source_receipt_sha256=source_receipt,
                profile_id=self.profile_id,
            )
        except GlobalOrientationError as exc:
            _fail(DEGENERATE_SO3_SOURCE_GEOMETRY, str(exc))
        selected = batch.slots[slot.so3_sequence_index]
        if (
            selected.accepted_sequence_index != slot.so3_sequence_index
            or selected.orientation_index != slot.so3_sequence_index
            or selected.translation_index != 0
            or not selected.accepted
        ):
            _fail(DEGENERATE_SO3_SOURCE_GEOMETRY, "SO3 sequence selection changed")
        object.__setattr__(self, "source_proposal_sha256", source_proposal)
        object.__setattr__(self, "source_coordinate_sha256", source_coordinate)
        object.__setattr__(self, "source_receipt_sha256", source_receipt)
        object.__setattr__(self, "source_coordinates", coordinates)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_normal", normal)
        object.__setattr__(self, "output_coordinates", selected.transformed_coordinates)
        object.__setattr__(self, "quaternion", selected.quaternion)
        object.__setattr__(self, "translation", selected.translation)
        object.__setattr__(self, "raw_sequence_index", selected.raw_sequence_index)
        object.__setattr__(
            self,
            "accepted_sequence_index",
            selected.accepted_sequence_index,
        )
        object.__setattr__(self, "source_seed_sha256", batch.source_seed_sha256)
        object.__setattr__(
            self,
            "global_orientation_batch_receipt_sha256",
            batch.receipt_sha256,
        )
        object.__setattr__(
            self,
            "global_orientation_slot_receipt_sha256",
            selected.receipt_sha256,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def output_coordinate_sha256(self) -> str:
        return coordinate_sha256(self.output_coordinates)

    def _projection(self) -> dict[str, object]:
        slot = self.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PROPOSAL_GEOMETRY_COMPONENT_ID,
            "profile_id": self.profile_id,
            "geometry_policy_sha256": (
                MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256
            ),
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "lane_offset": slot.lane_offset,
            "so3_sequence_index": slot.so3_sequence_index,
            "source_proposal_sha256": self.source_proposal_sha256,
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "source_coordinates_binary64_hex": _projection_coordinates(
                self.source_coordinates
            ),
            "pocket_center_binary64_hex": _projection_vector(self.pocket_center),
            "pocket_normal_binary64_hex": _projection_vector(self.pocket_normal),
            "source_seed_sha256": self.source_seed_sha256,
            "raw_sequence_index": self.raw_sequence_index,
            "accepted_sequence_index": self.accepted_sequence_index,
            "quaternion_binary64_hex": [value.hex() for value in self.quaternion],
            "translation_binary64_hex": _projection_vector(self.translation),
            "output_coordinate_sha256": self.output_coordinate_sha256,
            "output_coordinates_binary64_hex": _projection_coordinates(
                self.output_coordinates
            ),
            "global_orientation_batch_receipt_sha256": (
                self.global_orientation_batch_receipt_sha256
            ),
            "global_orientation_slot_receipt_sha256": (
                self.global_orientation_slot_receipt_sha256
            ),
            "index_stable": True,
            "source_dependent_seed": True,
            "orientation_duplicate_elimination_enabled": True,
            "result_dependent_input_consumed": False,
            "slot_reallocation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_COORDINATE_IDENTITY_MISMATCH, "indexed SO3 receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class SingleAnchorPlacementReceiptV1:
    """One fixed slot's feature-bound single-anchor rigid placement and precheck."""

    allocation: FixedMixed64Allocation = field(repr=False)
    slot_index: int
    source_proposal_sha256: str
    source_coordinate_sha256: str
    source_receipt_sha256: str
    ligand_coordinates: Coordinates = field(repr=False)
    ligand_vdw_radii: tuple[float, ...] = field(repr=False)
    ligand_heavy_atom_mask: tuple[bool, ...] = field(repr=False)
    receptor_coordinate_sha256: str
    receptor_coordinates: Coordinates = field(repr=False)
    receptor_vdw_radii: tuple[float, ...] = field(repr=False)
    pocket_center: Vector3
    pocket_radius: float
    profile_id: str = MIXED64_SINGLE_ANCHOR_PROFILE_ID
    schema_id: str = MIXED64_SINGLE_ANCHOR_SCHEMA_ID
    selected_ligand_feature: Mixed64AtomicFeatureEvidence = field(init=False)
    selected_receptor_feature: Mixed64AtomicFeatureEvidence = field(init=False)
    ligand_anchor_point: Vector3 = field(init=False)
    receptor_anchor_point: Vector3 = field(init=False)
    target_anchor_point: Vector3 = field(init=False)
    local_surface_normal: Vector3 = field(init=False)
    approach_vector: Vector3 = field(init=False)
    ligand_direction: Vector3 = field(init=False)
    alignment_target_direction: Vector3 = field(init=False)
    target_distance_angstrom: float = field(init=False)
    twist_angle_radians: float = field(init=False)
    quaternion: Quaternion = field(init=False)
    translation: Vector3 = field(init=False)
    output_coordinates: Coordinates = field(init=False, repr=False)
    geometric_metrics: GeometricAdmissionMetricsV2 = field(init=False)
    steric_precheck_passed: bool = field(init=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_SINGLE_ANCHOR_SCHEMA_ID:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "single-anchor schema changed")
        if self.profile_id != MIXED64_SINGLE_ANCHOR_PROFILE_ID:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "single-anchor profile changed")
        _validate_slot(
            self.allocation,
            slot_index=self.slot_index,
            allowed_lanes=set(_ANCHOR_LANE_KIND),
        )
        slot = self.allocation.slots[self.slot_index]
        if slot.declared_anchor_kind != _ANCHOR_LANE_KIND[slot.lane]:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "slot anchor identity changed")
        source_proposal = _digest(
            self.source_proposal_sha256,
            name="source_proposal_sha256",
        )
        source_coordinate = _digest(
            self.source_coordinate_sha256,
            name="source_coordinate_sha256",
        )
        receptor_coordinate = _digest(
            self.receptor_coordinate_sha256,
            name="receptor_coordinate_sha256",
        )
        _validate_exact_source(
            self.allocation,
            source_proposal_sha256=source_proposal,
            source_coordinate_sha256=source_coordinate,
            source_receipt_sha256=self.source_receipt_sha256,
            receptor_coordinate_sha256=receptor_coordinate,
        )
        ligand = _coordinates(
            self.ligand_coordinates,
            name="ligand_coordinates",
            maximum_count=MAX_LIGAND_ATOMS,
        )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
            maximum_count=MAX_RECEPTOR_ATOMS,
        )
        if coordinate_sha256(ligand) != source_coordinate:
            _fail(SOURCE_COORDINATE_IDENTITY_MISMATCH, "anchor source coordinates changed")
        if coordinate_sha256(receptor) != receptor_coordinate:
            _fail(RECEPTOR_COORDINATE_IDENTITY_MISMATCH, "receptor coordinates changed")
        ligand_radii = _float_tuple(
            self.ligand_vdw_radii,
            name="ligand_vdw_radii",
            expected_count=len(ligand),
        )
        heavy_mask = _bool_tuple(
            self.ligand_heavy_atom_mask,
            name="ligand_heavy_atom_mask",
            expected_count=len(ligand),
        )
        receptor_radii = _float_tuple(
            self.receptor_vdw_radii,
            name="receptor_vdw_radii",
            expected_count=len(receptor),
        )
        center = _vector(self.pocket_center, name="pocket_center")
        radius = _finite(self.pocket_radius, name="pocket_radius")
        ligand_feature, receptor_feature = _selected_anchor_features(
            self.allocation,
            slot_index=self.slot_index,
        )
        ligand_feature_coordinates = _feature_coordinates(
            ligand_feature,
            ligand,
            role="ligand",
        )
        receptor_feature_coordinates = _feature_coordinates(
            receptor_feature,
            receptor,
            role="receptor",
        )
        ligand_anchor, receptor_anchor, ligand_direction, local_normal, target = (
            _derive_anchor_geometry(
                lane=slot.lane,
                ligand_coordinates=ligand,
                receptor_coordinates=receptor,
                ligand_feature_coordinates=ligand_feature_coordinates,
                receptor_feature_coordinates=receptor_feature_coordinates,
                pocket_center=center,
            )
        )
        approach = _scale(local_normal, -1.0)
        target_distance = _ANCHOR_TARGET_DISTANCE_ANGSTROM[slot.declared_anchor_kind]
        target_anchor = _add(receptor_anchor, _scale(local_normal, target_distance))
        base_quaternion = _quaternion_between(ligand_direction, target)
        lane_width = _ANCHOR_LANE_WIDTH[slot.lane]
        if not 0 <= slot.lane_offset < lane_width:
            _fail(UNSUPPORTED_GEOMETRY_LANE, "anchor lane offset changed")
        twist_angle = 2.0 * math.pi * slot.lane_offset / lane_width
        twist_quaternion = _quaternion_axis_angle(target, twist_angle)
        quaternion = _quaternion_multiply(twist_quaternion, base_quaternion)
        translation = _subtract(target_anchor, rotate_vector(ligand_anchor, quaternion))
        output = tuple(
            _add(rotate_vector(point, quaternion), translation) for point in ligand
        )
        try:
            metrics = evaluate_geometric_admission_metrics_one_python(
                output,
                ligand_vdw_radii=ligand_radii,
                ligand_heavy_atom_mask=heavy_mask,
                receptor_coordinates=receptor,
                receptor_vdw_radii=receptor_radii,
                pocket_center=center,
                pocket_radius=radius,
            )
        except GeometricAdmissionV2Error as exc:
            _fail(GEOMETRIC_PRECHECK_INPUT_INVALID, str(exc))
        object.__setattr__(self, "source_proposal_sha256", source_proposal)
        object.__setattr__(self, "source_coordinate_sha256", source_coordinate)
        object.__setattr__(self, "source_receipt_sha256", _digest(self.source_receipt_sha256, name="source_receipt_sha256"))
        object.__setattr__(self, "ligand_coordinates", ligand)
        object.__setattr__(self, "ligand_vdw_radii", ligand_radii)
        object.__setattr__(self, "ligand_heavy_atom_mask", heavy_mask)
        object.__setattr__(self, "receptor_coordinate_sha256", receptor_coordinate)
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "receptor_vdw_radii", receptor_radii)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_radius", radius)
        object.__setattr__(self, "selected_ligand_feature", ligand_feature)
        object.__setattr__(self, "selected_receptor_feature", receptor_feature)
        object.__setattr__(self, "ligand_anchor_point", ligand_anchor)
        object.__setattr__(self, "receptor_anchor_point", receptor_anchor)
        object.__setattr__(self, "target_anchor_point", target_anchor)
        object.__setattr__(self, "local_surface_normal", local_normal)
        object.__setattr__(self, "approach_vector", approach)
        object.__setattr__(self, "ligand_direction", ligand_direction)
        object.__setattr__(self, "alignment_target_direction", target)
        object.__setattr__(self, "target_distance_angstrom", target_distance)
        object.__setattr__(self, "twist_angle_radians", twist_angle)
        object.__setattr__(self, "quaternion", quaternion)
        object.__setattr__(self, "translation", translation)
        object.__setattr__(self, "output_coordinates", output)
        object.__setattr__(self, "geometric_metrics", metrics)
        object.__setattr__(
            self,
            "steric_precheck_passed",
            metrics.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def output_coordinate_sha256(self) -> str:
        return coordinate_sha256(self.output_coordinates)

    def _projection(self) -> dict[str, object]:
        slot = self.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PROPOSAL_GEOMETRY_COMPONENT_ID,
            "profile_id": self.profile_id,
            "geometry_policy_sha256": (
                MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256
            ),
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "lane_offset": slot.lane_offset,
            "declared_anchor_kind": slot.declared_anchor_kind,
            "selected_feature_receipt_sha256s": list(
                slot.selected_source_receipt_sha256s
            ),
            "selected_ligand_feature": self.selected_ligand_feature.to_dict(),
            "selected_receptor_feature": self.selected_receptor_feature.to_dict(),
            "source_proposal_sha256": self.source_proposal_sha256,
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "ligand_coordinates_binary64_hex": _projection_coordinates(
                self.ligand_coordinates
            ),
            "ligand_vdw_radii_binary64_hex": [
                value.hex() for value in self.ligand_vdw_radii
            ],
            "ligand_heavy_atom_mask": list(self.ligand_heavy_atom_mask),
            "receptor_coordinate_sha256": self.receptor_coordinate_sha256,
            "receptor_coordinates_binary64_hex": _projection_coordinates(
                self.receptor_coordinates
            ),
            "receptor_vdw_radii_binary64_hex": [
                value.hex() for value in self.receptor_vdw_radii
            ],
            "pocket_center_binary64_hex": _projection_vector(self.pocket_center),
            "pocket_radius_binary64_hex": self.pocket_radius.hex(),
            "ligand_anchor_point_binary64_hex": _projection_vector(
                self.ligand_anchor_point
            ),
            "receptor_anchor_point_binary64_hex": _projection_vector(
                self.receptor_anchor_point
            ),
            "target_anchor_point_binary64_hex": _projection_vector(
                self.target_anchor_point
            ),
            "local_surface_normal_binary64_hex": _projection_vector(
                self.local_surface_normal
            ),
            "approach_vector_binary64_hex": _projection_vector(self.approach_vector),
            "ligand_direction_binary64_hex": _projection_vector(
                self.ligand_direction
            ),
            "alignment_target_direction_binary64_hex": _projection_vector(
                self.alignment_target_direction
            ),
            "target_distance_angstrom_binary64_hex": (
                self.target_distance_angstrom.hex()
            ),
            "twist_angle_radians_binary64_hex": self.twist_angle_radians.hex(),
            "quaternion_binary64_hex": [value.hex() for value in self.quaternion],
            "translation_binary64_hex": _projection_vector(self.translation),
            "output_coordinate_sha256": self.output_coordinate_sha256,
            "output_coordinates_binary64_hex": _projection_coordinates(
                self.output_coordinates
            ),
            "geometric_precheck": self.geometric_metrics.to_dict(),
            "steric_precheck_threshold_minimum_vdw_ratio_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
            ),
            "steric_precheck_passed": self.steric_precheck_passed,
            "severe_penetration_preserved_for_typed_admission": (
                not self.steric_precheck_passed
            ),
            "single_anchor_count": 1,
            "multi_anchor_consumed": False,
            "exact_pair_count_preserved": True,
            "result_dependent_input_consumed": False,
            "slot_reallocation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_COORDINATE_IDENTITY_MISMATCH, "single-anchor receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _derive_anchor_geometry(
    *,
    lane: str,
    ligand_coordinates: Coordinates,
    receptor_coordinates: Coordinates,
    ligand_feature_coordinates: Coordinates,
    receptor_feature_coordinates: Coordinates,
    pocket_center: Vector3,
) -> tuple[Vector3, Vector3, Vector3, Vector3, Vector3]:
    ligand_center = _centroid(ligand_coordinates)
    ligand_anchor = _centroid(ligand_feature_coordinates)
    receptor_anchor = _centroid(receptor_feature_coordinates)
    if lane == LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR:
        ligand_anchor = ligand_feature_coordinates[0]
        ligand_direction = _normalize(
            _subtract(ligand_feature_coordinates[1], ligand_feature_coordinates[0]),
            code=DEGENERATE_LIGAND_DIRECTION,
            name="ligand donor-to-hydrogen direction",
        )
        local_normal = _normalize(
            _subtract(pocket_center, receptor_anchor),
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="receptor acceptor local surface normal",
        )
        target = _scale(local_normal, -1.0)
    elif lane == LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR:
        ligand_direction = _normalize(
            _subtract(ligand_anchor, ligand_center),
            code=DEGENERATE_LIGAND_DIRECTION,
            name="ligand acceptor outward direction",
        )
        receptor_anchor = receptor_feature_coordinates[0]
        local_normal = _normalize(
            _subtract(receptor_feature_coordinates[1], receptor_feature_coordinates[0]),
            code=DEGENERATE_RECEPTOR_DIRECTION,
            name="receptor donor-to-hydrogen direction",
        )
        target = _scale(local_normal, -1.0)
    elif lane == LANE_COMPLEMENTARY_CHARGE:
        ligand_direction = _normalize(
            _subtract(ligand_anchor, ligand_center),
            code=DEGENERATE_LIGAND_DIRECTION,
            name="ligand charge-site outward direction",
        )
        local_normal = _normalize(
            _subtract(pocket_center, receptor_anchor),
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="receptor charge-site local surface normal",
        )
        target = _scale(local_normal, -1.0)
    elif lane == LANE_AROMATIC_PLANE:
        ligand_direction = _aromatic_normal(
            ligand_feature_coordinates,
            role="ligand",
        )
        receptor_plane_normal = _aromatic_normal(
            receptor_feature_coordinates,
            role="receptor",
        )
        toward_pocket = _normalize(
            _subtract(pocket_center, receptor_anchor),
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="receptor aromatic pocket-facing direction",
        )
        pocket_facing_cosine = _dot(receptor_plane_normal, toward_pocket)
        if (
            abs(pocket_facing_cosine)
            <= _AROMATIC_POCKET_FACING_MINIMUM_ABSOLUTE_COSINE
        ):
            _fail(
                DEGENERATE_LOCAL_SURFACE_NORMAL,
                "receptor aromatic normal is tangent to the pocket direction",
            )
        if pocket_facing_cosine < 0.0:
            receptor_plane_normal = _scale(receptor_plane_normal, -1.0)
        local_normal = _normalize(
            receptor_plane_normal,
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="receptor aromatic surface normal",
        )
        target = local_normal
    elif lane == LANE_PRINCIPAL_AXIS_SHAPE:
        ligand_direction = _principal_axis(
            ligand_feature_coordinates,
            role="ligand",
        )
        target = _principal_axis(
            receptor_feature_coordinates,
            role="pocket",
        )
        local_normal = _normalize(
            _subtract(pocket_center, receptor_anchor),
            code=DEGENERATE_LOCAL_SURFACE_NORMAL,
            name="pocket shape local surface normal",
        )
    else:
        _fail(UNSUPPORTED_GEOMETRY_LANE, f"unsupported anchor lane {lane!r}")
    return ligand_anchor, receptor_anchor, ligand_direction, local_normal, target


def generate_indexed_so3_placement(
    allocation: FixedMixed64Allocation,
    *,
    slot_index: int,
    source_proposal_sha256: str,
    source_coordinate_sha256: str,
    source_receipt_sha256: str,
    source_coordinates: Iterable[Sequence[float]],
    pocket_center: Sequence[float],
    pocket_normal: Sequence[float],
) -> IndexedSO3PlacementReceiptV1:
    """Generate and seal one fixed SO(3) slot without scoring or selection."""

    coordinates = _coordinates(
        source_coordinates,
        name="source_coordinates",
        maximum_count=MAX_LIGAND_ATOMS,
    )
    return IndexedSO3PlacementReceiptV1(
        allocation=allocation,
        slot_index=slot_index,
        source_proposal_sha256=source_proposal_sha256,
        source_coordinate_sha256=source_coordinate_sha256,
        source_receipt_sha256=source_receipt_sha256,
        source_coordinates=coordinates,
        pocket_center=_vector(pocket_center, name="pocket_center"),
        pocket_normal=_vector(pocket_normal, name="pocket_normal"),
    )


def generate_single_anchor_placement(
    allocation: FixedMixed64Allocation,
    *,
    slot_index: int,
    source_proposal_sha256: str,
    source_coordinate_sha256: str,
    source_receipt_sha256: str,
    ligand_coordinates: Iterable[Sequence[float]],
    ligand_vdw_radii: Iterable[float],
    ligand_heavy_atom_mask: Iterable[bool],
    receptor_coordinate_sha256: str,
    receptor_coordinates: Iterable[Sequence[float]],
    receptor_vdw_radii: Iterable[float],
    pocket_center: Sequence[float],
    pocket_radius: float,
) -> SingleAnchorPlacementReceiptV1:
    """Generate and precheck one fixed single-anchor slot without deleting it."""

    ligand = _coordinates(
        ligand_coordinates,
        name="ligand_coordinates",
        maximum_count=MAX_LIGAND_ATOMS,
    )
    receptor = _coordinates(
        receptor_coordinates,
        name="receptor_coordinates",
        maximum_count=MAX_RECEPTOR_ATOMS,
    )
    return SingleAnchorPlacementReceiptV1(
        allocation=allocation,
        slot_index=slot_index,
        source_proposal_sha256=source_proposal_sha256,
        source_coordinate_sha256=source_coordinate_sha256,
        source_receipt_sha256=source_receipt_sha256,
        ligand_coordinates=ligand,
        ligand_vdw_radii=_float_tuple(
            ligand_vdw_radii,
            name="ligand_vdw_radii",
            expected_count=len(ligand),
        ),
        ligand_heavy_atom_mask=_bool_tuple(
            ligand_heavy_atom_mask,
            name="ligand_heavy_atom_mask",
            expected_count=len(ligand),
        ),
        receptor_coordinate_sha256=receptor_coordinate_sha256,
        receptor_coordinates=receptor,
        receptor_vdw_radii=_float_tuple(
            receptor_vdw_radii,
            name="receptor_vdw_radii",
            expected_count=len(receptor),
        ),
        pocket_center=_vector(pocket_center, name="pocket_center"),
        pocket_radius=pocket_radius,
    )


__all__ = [
    "ALLOCATION_SLOT_NOT_ELIGIBLE",
    "DEGENERATE_AROMATIC_PLANE",
    "DEGENERATE_LIGAND_DIRECTION",
    "DEGENERATE_LOCAL_SURFACE_NORMAL",
    "DEGENERATE_PRINCIPAL_AXIS",
    "DEGENERATE_RECEPTOR_DIRECTION",
    "DEGENERATE_SO3_SOURCE_GEOMETRY",
    "FEATURE_ATOM_INDEX_OUT_OF_RANGE",
    "FEATURE_RECEIPT_CROSS_WIRING",
    "GEOMETRIC_PRECHECK_INPUT_INVALID",
    "IndexedSO3PlacementReceiptV1",
    "MIXED64_INDEXED_SO3_PROFILE_ID",
    "MIXED64_INDEXED_SO3_SCHEMA_ID",
    "MIXED64_PROPOSAL_GEOMETRY_COMPONENT_ID",
    "MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256",
    "MIXED64_SINGLE_ANCHOR_PROFILE_ID",
    "MIXED64_SINGLE_ANCHOR_SCHEMA_ID",
    "Mixed64ProposalGeometryError",
    "RECEPTOR_COORDINATE_IDENTITY_MISMATCH",
    "SOURCE_COORDINATE_IDENTITY_MISMATCH",
    "SOURCE_PROPOSAL_IDENTITY_MISMATCH",
    "SOURCE_RECEIPT_IDENTITY_MISMATCH",
    "SingleAnchorPlacementReceiptV1",
    "UNSUPPORTED_GEOMETRY_LANE",
    "coordinate_sha256",
    "frozen_mixed64_proposal_geometry_policy",
    "generate_indexed_so3_placement",
    "generate_single_anchor_placement",
]
