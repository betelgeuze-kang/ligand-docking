"""Deterministic synthetic-only global rigid-body orientation proposals.

This module explores bounded ligand rigid transforms without consuming a native
pose, RMSD target, benchmark outcome, scorer result, or fresh-holdout datum. It
is an implementation contract and synthetic test surface only; it does not
select a production docking profile or authorize customer/scientific use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Iterable, Sequence


GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_config/1.0.0"
)
GLOBAL_ORIENTATION_SLOT_SCHEMA_ID = "betelgeuze.engine_v2_global_orientation_slot/2.0.0"
GLOBAL_ORIENTATION_BATCH_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_batch/2.0.0"
)
GLOBAL_ORIENTATION_GENERATOR_ID = "deterministic_surface_aware_rigid_v2"
GLOBAL_ORIENTATION_SOURCE_SEED_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_source_seed/1.0.0"
)
MAX_LIGAND_ATOMS = 512
MAX_RECEPTOR_SURFACE_POINTS = 4096
MAX_ORIENTATIONS = 512
MAX_TRANSLATION_SHELLS = 32
MAX_TRANSLATION_POINTS_PER_SHELL = 256
MAX_CANDIDATE_SLOTS = 65536
_EPSILON = 1.0e-12
_GOLDEN_RATIO_CONJUGATE = (math.sqrt(5.0) - 1.0) / 2.0
_GEODESIC_DUPLICATE_TOLERANCE_RADIANS = 1.0e-10
_LOW_DISCREPANCY_BASES = (2, 3, 5)
_MAX_SEQUENCE_ATTEMPTS_PER_ORIENTATION = 1024

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
Coordinates = tuple[Vector3, ...]


class GlobalOrientationError(ValueError):
    """Raised when a global-orientation contract fails closed."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _sha256_identity(value: object, *, name: str) -> str:
    if type(value) is not str or len(value) != 64:
        raise GlobalOrientationError(f"{name} must be a lowercase SHA-256")
    if any(character not in "0123456789abcdef" for character in value):
        raise GlobalOrientationError(f"{name} must be a lowercase SHA-256")
    return value


def _profile_id(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 256
        or value != value.strip()
        or not value.isascii()
    ):
        raise GlobalOrientationError(
            "profile_id must be non-empty canonical ASCII within 256 characters"
        )
    return value


def _finite_float(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        raise GlobalOrientationError(f"{name} must be a finite number")
    observed = float(value)
    if not math.isfinite(observed):
        raise GlobalOrientationError(f"{name} must be finite")
    return observed


def _vector(value: Sequence[float], *, name: str) -> Vector3:
    if len(value) != 3:
        raise GlobalOrientationError(f"{name} must contain exactly three values")
    return tuple(
        _finite_float(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )  # type: ignore[return-value]


def _coordinates(
    value: Iterable[Sequence[float]],
    *,
    name: str,
    minimum_count: int,
    maximum_count: int,
) -> Coordinates:
    observed = tuple(
        _vector(row, name=f"{name}[{index}]") for index, row in enumerate(value)
    )
    if not minimum_count <= len(observed) <= maximum_count:
        raise GlobalOrientationError(
            f"{name} count must be within [{minimum_count}, {maximum_count}]"
        )
    return observed


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


def _normalize(value: Vector3, *, name: str) -> Vector3:
    length = _norm(value)
    if length <= _EPSILON:
        raise GlobalOrientationError(f"{name} must be non-zero")
    if abs(length - 1.0) <= 1.0e-15:
        return value
    return _scale(value, 1.0 / length)


def _centroid(coordinates: Coordinates) -> Vector3:
    inverse = 1.0 / len(coordinates)
    return (
        sum(point[0] for point in coordinates) * inverse,
        sum(point[1] for point in coordinates) * inverse,
        sum(point[2] for point in coordinates) * inverse,
    )


def _center(coordinates: Coordinates) -> Coordinates:
    center = _centroid(coordinates)
    return tuple(_subtract(point, center) for point in coordinates)


def _require_distinct_points(coordinates: Coordinates) -> None:
    first = coordinates[0]
    if all(
        _dot(_subtract(point, first), _subtract(point, first)) <= _EPSILON
        for point in coordinates[1:]
    ):
        raise GlobalOrientationError(
            "ligand coordinates must contain at least two distinct points"
        )


def _quaternion_normalize(value: Quaternion) -> Quaternion:
    if len(value) != 4:
        raise GlobalOrientationError("quaternion must contain exactly four values")
    finite = tuple(
        _finite_float(component, name=f"quaternion[{index}]")
        for index, component in enumerate(value)
    )
    length = math.sqrt(sum(component * component for component in finite))
    if length <= _EPSILON:
        raise GlobalOrientationError("quaternion must be non-zero")
    normalized = tuple(component / length for component in finite)
    # q and -q encode the same SO(3) rotation. Choose one representation using
    # the first non-zero component in (w, z, y, x) order so even exact pi
    # rotations (w == 0) have one canonical receipt representation.
    for component in reversed(normalized):
        if component > 0.0:
            break
        if component < 0.0:
            normalized = tuple(-observed for observed in normalized)
            break
    return tuple(0.0 if component == 0.0 else component for component in normalized)  # type: ignore[return-value]


def _quaternion_from_axis_angle(axis: Vector3, angle: float) -> Quaternion:
    normalized_axis = _normalize(axis, name="rotation axis")
    half = 0.5 * angle
    sine = math.sin(half)
    return _quaternion_normalize(
        (
            normalized_axis[0] * sine,
            normalized_axis[1] * sine,
            normalized_axis[2] * sine,
            math.cos(half),
        )
    )


def _quaternion_between(source: Vector3, target: Vector3) -> Quaternion:
    source_unit = _normalize(source, name="source direction")
    target_unit = _normalize(target, name="target direction")
    cosine = max(-1.0, min(1.0, _dot(source_unit, target_unit)))
    if cosine >= 1.0 - 1.0e-12:
        return (0.0, 0.0, 0.0, 1.0)
    if cosine <= -1.0 + 1.0e-12:
        fallback = (1.0, 0.0, 0.0)
        if abs(_dot(source_unit, fallback)) > 0.9:
            fallback = (0.0, 1.0, 0.0)
        axis = _normalize(_cross(source_unit, fallback), name="opposite rotation axis")
        return _quaternion_from_axis_angle(axis, math.pi)
    axis = _cross(source_unit, target_unit)
    return _quaternion_normalize((axis[0], axis[1], axis[2], 1.0 + cosine))


def rotate_vector(value: Vector3, quaternion: Quaternion) -> Vector3:
    """Rotate one vector with a normalized `(x, y, z, w)` quaternion."""

    qx, qy, qz, qw = _quaternion_normalize(quaternion)
    q_vector = (qx, qy, qz)
    twice_cross = _scale(_cross(q_vector, value), 2.0)
    return _add(value, _add(_scale(twice_cross, qw), _cross(q_vector, twice_cross)))


def _vector_projection(value: Vector3) -> list[str]:
    return [component.hex() for component in value]


def _coordinates_projection(value: Coordinates) -> list[list[str]]:
    return [_vector_projection(point) for point in value]


def _coordinate_identity(value: Coordinates) -> str:
    return _sha256(_coordinates_projection(value))


def _derive_source_seed_sha256(
    *,
    source_receipt_sha256: str | None,
    ligand_input_sha256: str,
    pocket_center: Vector3,
    pocket_normal: Vector3,
    profile_id: str,
) -> str:
    return _sha256(
        {
            "schema_id": GLOBAL_ORIENTATION_SOURCE_SEED_SCHEMA_ID,
            "source_receipt_sha256": source_receipt_sha256,
            "ligand_input_sha256": ligand_input_sha256,
            "pocket_center_binary64_hex": _vector_projection(pocket_center),
            "pocket_normal_binary64_hex": _vector_projection(pocket_normal),
            "profile_id": profile_id,
        }
    )


def _orthonormal_basis(normal: Vector3) -> tuple[Vector3, Vector3, Vector3]:
    axis_z = _normalize(normal, name="pocket normal")
    reference = (1.0, 0.0, 0.0)
    if abs(_dot(axis_z, reference)) > 0.9:
        reference = (0.0, 1.0, 0.0)
    axis_x = _normalize(_cross(reference, axis_z), name="pocket tangent x")
    axis_y = _normalize(_cross(axis_z, axis_x), name="pocket tangent y")
    return axis_x, axis_y, axis_z


def _local_to_global(
    local: Vector3,
    basis: tuple[Vector3, Vector3, Vector3],
) -> Vector3:
    axis_x, axis_y, axis_z = basis
    return _add(
        _add(_scale(axis_x, local[0]), _scale(axis_y, local[1])),
        _scale(axis_z, local[2]),
    )


def _quaternion_geodesic_distance(
    left: Quaternion,
    right: Quaternion,
) -> float:
    left_unit = _quaternion_normalize(left)
    right_unit = _quaternion_normalize(right)
    dot = sum(a * b for a, b in zip(left_unit, right_unit))
    equivalent_right = (
        right_unit if dot >= 0.0 else tuple(-value for value in right_unit)
    )
    difference_norm = math.sqrt(
        sum(
            (a - b) ** 2
            for a, b in zip(left_unit, equivalent_right)
        )
    )
    sum_norm = math.sqrt(
        sum(
            (a + b) ** 2
            for a, b in zip(left_unit, equivalent_right)
        )
    )
    # For unit quaternions, the SO(3) angle is twice their S3 angle.
    # This atan2/chord form remains stable when dot rounds to exactly 1.0.
    return 4.0 * math.atan2(difference_norm, sum_norm)


def _radical_inverse(index: int, base: int) -> float:
    if type(index) is not int or index < 0:
        raise GlobalOrientationError(
            "low-discrepancy sequence index must be non-negative"
        )
    inverse_base = 1.0 / base
    fraction = inverse_base
    value = 0.0
    remaining = index
    while remaining:
        remaining, digit = divmod(remaining, base)
        value += digit * fraction
        fraction *= inverse_base
    return value


def _source_seed_offsets(source_seed_sha256: str) -> tuple[float, float, float]:
    digest = bytes.fromhex(
        _sha256_identity(source_seed_sha256, name="source_seed_sha256")
    )
    denominator = float(1 << 64)
    return tuple(
        int.from_bytes(digest[offset : offset + 8], "big") / denominator
        for offset in (0, 8, 16)
    )  # type: ignore[return-value]


def _low_discrepancy_quaternion(
    raw_sequence_index: int,
    *,
    source_seed_sha256: str,
) -> Quaternion:
    offsets = _source_seed_offsets(source_seed_sha256)
    unit_1, unit_2, unit_3 = tuple(
        (_radical_inverse(raw_sequence_index, base) + offset) % 1.0
        for base, offset in zip(_LOW_DISCREPANCY_BASES, offsets)
    )
    first_radius = math.sqrt(max(0.0, 1.0 - unit_1))
    second_radius = math.sqrt(max(0.0, unit_1))
    return _quaternion_normalize(
        (
            first_radius * math.sin(2.0 * math.pi * unit_2),
            first_radius * math.cos(2.0 * math.pi * unit_2),
            second_radius * math.sin(2.0 * math.pi * unit_3),
            second_radius * math.cos(2.0 * math.pi * unit_3),
        )
    )


@dataclass(frozen=True, slots=True)
class _OrientationSequenceItem:
    raw_sequence_index: int
    accepted_sequence_index: int
    quaternion: Quaternion


def _orientation_quaternions(
    *,
    source_seed_sha256: str,
    count: int,
) -> tuple[_OrientationSequenceItem, ...]:
    orientations: list[_OrientationSequenceItem] = []
    raw_sequence_index = 0
    maximum_attempts = count * _MAX_SEQUENCE_ATTEMPTS_PER_ORIENTATION
    while len(orientations) < count:
        if raw_sequence_index >= maximum_attempts:
            raise GlobalOrientationError(
                "low-discrepancy sequence exhausted before the requested "
                "unique orientation count"
            )
        candidate = _low_discrepancy_quaternion(
            raw_sequence_index,
            source_seed_sha256=source_seed_sha256,
        )
        observed_raw_sequence_index = raw_sequence_index
        raw_sequence_index += 1
        if any(
            _quaternion_geodesic_distance(candidate, existing.quaternion)
            <= _GEODESIC_DUPLICATE_TOLERANCE_RADIANS
            for existing in orientations
        ):
            continue
        orientations.append(
            _OrientationSequenceItem(
                raw_sequence_index=observed_raw_sequence_index,
                accepted_sequence_index=len(orientations),
                quaternion=candidate,
            )
        )
    return tuple(orientations)


def _translation_targets(
    *,
    pocket_center: Vector3,
    pocket_normal: Vector3,
    radii: tuple[float, ...],
    points_per_shell: int,
) -> tuple[Vector3, ...]:
    basis = _orthonormal_basis(pocket_normal)
    targets: list[Vector3] = [pocket_center]
    for radius in radii:
        for index in range(points_per_shell):
            z = 1.0 - (2.0 * (index + 0.5) / points_per_shell)
            radial = math.sqrt(max(0.0, 1.0 - z * z))
            angle = 2.0 * math.pi * ((index * _GOLDEN_RATIO_CONJUGATE) % 1.0)
            local = (radial * math.cos(angle), radial * math.sin(angle), z)
            targets.append(
                _add(pocket_center, _scale(_local_to_global(local, basis), radius))
            )
    return tuple(targets)


def _minimum_distance(left: Coordinates, right: Coordinates) -> float | None:
    if not right:
        return None
    minimum_squared = math.inf
    for left_point in left:
        for right_point in right:
            delta = _subtract(left_point, right_point)
            minimum_squared = min(minimum_squared, _dot(delta, delta))
    return math.sqrt(minimum_squared)


@dataclass(frozen=True, slots=True)
class GlobalOrientationConfig:
    orientation_count: int = 24
    translation_shell_radii: tuple[float, ...] = (1.5, 3.0)
    translation_points_per_shell: int = 8
    minimum_receptor_distance: float = 1.1
    schema_id: str = GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID:
            raise GlobalOrientationError("global-orientation config schema is invalid")
        if (
            type(self.orientation_count) is not int
            or not 1 <= self.orientation_count <= MAX_ORIENTATIONS
        ):
            raise GlobalOrientationError(
                "orientation_count is outside the bounded range"
            )
        if (
            type(self.translation_points_per_shell) is not int
            or not 1
            <= self.translation_points_per_shell
            <= MAX_TRANSLATION_POINTS_PER_SHELL
        ):
            raise GlobalOrientationError(
                "translation_points_per_shell is outside the bounded range"
            )
        radii = tuple(
            _finite_float(radius, name=f"translation_shell_radii[{index}]")
            for index, radius in enumerate(self.translation_shell_radii)
        )
        if len(radii) > MAX_TRANSLATION_SHELLS:
            raise GlobalOrientationError("too many translation shells")
        if any(radius <= 0.0 for radius in radii):
            raise GlobalOrientationError("translation shell radii must be positive")
        if tuple(sorted(set(radii))) != radii:
            raise GlobalOrientationError(
                "translation shell radii must be unique and strictly increasing"
            )
        minimum_distance = _finite_float(
            self.minimum_receptor_distance,
            name="minimum_receptor_distance",
        )
        if minimum_distance < 0.0:
            raise GlobalOrientationError(
                "minimum_receptor_distance must be non-negative"
            )
        slot_count = self.orientation_count * (
            1 + len(radii) * self.translation_points_per_shell
        )
        if slot_count > MAX_CANDIDATE_SLOTS:
            raise GlobalOrientationError(
                "global-orientation slot count exceeds the cap"
            )
        object.__setattr__(self, "translation_shell_radii", radii)
        object.__setattr__(self, "minimum_receptor_distance", minimum_distance)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def translation_count(self) -> int:
        return 1 + len(self.translation_shell_radii) * self.translation_points_per_shell

    @property
    def candidate_slot_count(self) -> int:
        return self.orientation_count * self.translation_count

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "generator_id": GLOBAL_ORIENTATION_GENERATOR_ID,
            "orientation_count": self.orientation_count,
            "translation_shell_radii_binary64_hex": [
                radius.hex() for radius in self.translation_shell_radii
            ],
            "translation_points_per_shell": self.translation_points_per_shell,
            "minimum_receptor_distance_binary64_hex": (
                self.minimum_receptor_distance.hex()
            ),
            "candidate_slot_count": self.candidate_slot_count,
            "native_pose_input_allowed": False,
            "score_input_allowed": False,
            "benchmark_outcome_input_allowed": False,
            "fresh_holdout_input_allowed": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationError("global-orientation config changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationSlot:
    proposal_index: int
    orientation_index: int
    raw_sequence_index: int
    accepted_sequence_index: int
    translation_index: int
    quaternion: Quaternion
    translation: Vector3
    transformed_coordinates: Coordinates
    accepted: bool
    rejection_code: str | None
    minimum_receptor_distance: float | None
    schema_id: str = GLOBAL_ORIENTATION_SLOT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_SLOT_SCHEMA_ID:
            raise GlobalOrientationError("global-orientation slot schema is invalid")
        for name, value in (
            ("proposal_index", self.proposal_index),
            ("orientation_index", self.orientation_index),
            ("raw_sequence_index", self.raw_sequence_index),
            ("accepted_sequence_index", self.accepted_sequence_index),
            ("translation_index", self.translation_index),
        ):
            if type(value) is not int or value < 0:
                raise GlobalOrientationError(f"{name} must be a non-negative integer")
        quaternion = _quaternion_normalize(self.quaternion)
        translation = _vector(self.translation, name="translation")
        coordinates = _coordinates(
            self.transformed_coordinates,
            name="transformed_coordinates",
            minimum_count=2,
            maximum_count=MAX_LIGAND_ATOMS,
        )
        if type(self.accepted) is not bool:
            raise GlobalOrientationError("accepted must be boolean")
        if self.accepted and self.rejection_code is not None:
            raise GlobalOrientationError(
                "accepted slots cannot contain a rejection code"
            )
        if not self.accepted and not self.rejection_code:
            raise GlobalOrientationError("rejected slots require a rejection code")
        minimum_distance = self.minimum_receptor_distance
        if minimum_distance is not None:
            minimum_distance = _finite_float(
                minimum_distance,
                name="minimum_receptor_distance",
            )
            if minimum_distance < 0.0:
                raise GlobalOrientationError(
                    "minimum_receptor_distance cannot be negative"
                )
        object.__setattr__(self, "quaternion", quaternion)
        object.__setattr__(self, "translation", translation)
        object.__setattr__(self, "transformed_coordinates", coordinates)
        object.__setattr__(self, "minimum_receptor_distance", minimum_distance)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def coordinate_sha256(self) -> str:
        return _coordinate_identity(self.transformed_coordinates)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "proposal_index": self.proposal_index,
            "orientation_index": self.orientation_index,
            "raw_sequence_index": self.raw_sequence_index,
            "accepted_sequence_index": self.accepted_sequence_index,
            "translation_index": self.translation_index,
            "quaternion_binary64_hex": [
                component.hex() for component in self.quaternion
            ],
            "translation_binary64_hex": _vector_projection(self.translation),
            "coordinate_sha256": self.coordinate_sha256,
            "transformed_coordinates_binary64_hex": _coordinates_projection(
                self.transformed_coordinates
            ),
            "accepted": self.accepted,
            "rejection_code": self.rejection_code,
            "minimum_receptor_distance_binary64_hex": (
                None
                if self.minimum_receptor_distance is None
                else self.minimum_receptor_distance.hex()
            ),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationError("global-orientation slot changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GlobalOrientationBatch:
    config: GlobalOrientationConfig
    ligand_input_sha256: str
    receptor_surface_input_sha256: str | None
    source_receipt_sha256: str | None
    source_seed_sha256: str
    profile_id: str
    pocket_center: Vector3
    pocket_normal: Vector3
    slots: tuple[GlobalOrientationSlot, ...]
    schema_id: str = GLOBAL_ORIENTATION_BATCH_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GLOBAL_ORIENTATION_BATCH_SCHEMA_ID:
            raise GlobalOrientationError("global-orientation batch schema is invalid")
        if type(self.config) is not GlobalOrientationConfig:
            raise TypeError("config must be the exact GlobalOrientationConfig type")
        ligand_input_sha256 = _sha256_identity(
            self.ligand_input_sha256,
            name="ligand_input_sha256",
        )
        receptor_surface_input_sha256 = self.receptor_surface_input_sha256
        if receptor_surface_input_sha256 is not None:
            receptor_surface_input_sha256 = _sha256_identity(
                receptor_surface_input_sha256,
                name="receptor_surface_input_sha256",
            )
        source_receipt_sha256 = self.source_receipt_sha256
        if source_receipt_sha256 is not None:
            source_receipt_sha256 = _sha256_identity(
                source_receipt_sha256,
                name="source_receipt_sha256",
            )
        source_seed_sha256 = _sha256_identity(
            self.source_seed_sha256,
            name="source_seed_sha256",
        )
        profile_id = _profile_id(self.profile_id)
        pocket_center = _vector(self.pocket_center, name="pocket_center")
        pocket_normal = _normalize(
            _vector(self.pocket_normal, name="pocket_normal"),
            name="pocket_normal",
        )
        slots = tuple(self.slots)
        if len(slots) != self.config.candidate_slot_count:
            raise GlobalOrientationError("candidate denominator is incomplete")
        if any(type(slot) is not GlobalOrientationSlot for slot in slots):
            raise TypeError("slots must contain exact GlobalOrientationSlot values")
        if tuple(slot.proposal_index for slot in slots) != tuple(range(len(slots))):
            raise GlobalOrientationError("proposal indices must be contiguous")
        if len({slot.receipt_sha256 for slot in slots}) != len(slots):
            raise GlobalOrientationError("candidate slot receipts must be unique")
        expected_pairs = tuple(
            (orientation_index, translation_index)
            for orientation_index in range(self.config.orientation_count)
            for translation_index in range(self.config.translation_count)
        )
        observed_pairs = tuple(
            (slot.orientation_index, slot.translation_index) for slot in slots
        )
        if observed_pairs != expected_pairs:
            raise GlobalOrientationError("orientation/translation grid is incomplete")
        raw_sequence_indices: list[int] = []
        orientation_quaternions: list[Quaternion] = []
        for orientation_index in range(self.config.orientation_count):
            start = orientation_index * self.config.translation_count
            stop = start + self.config.translation_count
            orientation_slots = slots[start:stop]
            first = orientation_slots[0]
            if any(
                slot.raw_sequence_index != first.raw_sequence_index
                or slot.accepted_sequence_index != orientation_index
                or slot.orientation_index != orientation_index
                or slot.quaternion != first.quaternion
                for slot in orientation_slots
            ):
                raise GlobalOrientationError(
                    "orientation sequence evidence is inconsistent within a slot group"
                )
            raw_sequence_indices.append(first.raw_sequence_index)
            orientation_quaternions.append(first.quaternion)
        if raw_sequence_indices[0] != 0 or any(
            right <= left
            for left, right in zip(
                raw_sequence_indices,
                raw_sequence_indices[1:],
            )
        ):
            raise GlobalOrientationError(
                "raw orientation sequence indices must begin at zero and increase"
            )
        if any(
            _quaternion_geodesic_distance(left, right)
            <= _GEODESIC_DUPLICATE_TOLERANCE_RADIANS
            for index, left in enumerate(orientation_quaternions[:-1])
            for right in orientation_quaternions[index + 1 :]
        ):
            raise GlobalOrientationError(
                "orientation sequence contains a geodesic duplicate"
            )
        expected_source_seed_sha256 = _derive_source_seed_sha256(
            source_receipt_sha256=source_receipt_sha256,
            ligand_input_sha256=ligand_input_sha256,
            pocket_center=pocket_center,
            pocket_normal=pocket_normal,
            profile_id=profile_id,
        )
        if source_seed_sha256 != expected_source_seed_sha256:
            raise GlobalOrientationError(
                "source seed is not bound to source, ligand, pocket, and profile"
            )
        object.__setattr__(self, "ligand_input_sha256", ligand_input_sha256)
        object.__setattr__(
            self,
            "receptor_surface_input_sha256",
            receptor_surface_input_sha256,
        )
        object.__setattr__(self, "source_receipt_sha256", source_receipt_sha256)
        object.__setattr__(self, "source_seed_sha256", source_seed_sha256)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "pocket_center", pocket_center)
        object.__setattr__(self, "pocket_normal", pocket_normal)
        object.__setattr__(self, "slots", slots)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def accepted_count(self) -> int:
        return sum(slot.accepted for slot in self.slots)

    @property
    def rejected_count(self) -> int:
        return len(self.slots) - self.accepted_count

    @property
    def raw_sequence_count(self) -> int:
        return (
            self.slots[
                (self.config.orientation_count - 1) * self.config.translation_count
            ].raw_sequence_index
            + 1
        )

    @property
    def duplicate_orientation_count(self) -> int:
        return self.raw_sequence_count - self.config.orientation_count

    def _orientation_coverage_statistics(self) -> dict[str, object]:
        quaternions = tuple(
            self.slots[index * self.config.translation_count].quaternion
            for index in range(self.config.orientation_count)
        )
        pairwise_distances = tuple(
            _quaternion_geodesic_distance(left, right)
            for index, left in enumerate(quaternions[:-1])
            for right in quaternions[index + 1 :]
        )
        nearest_neighbor_distances = (
            tuple(
                min(
                    _quaternion_geodesic_distance(quaternion, other)
                    for other_index, other in enumerate(quaternions)
                    if other_index != index
                )
                for index, quaternion in enumerate(quaternions)
            )
            if len(quaternions) > 1
            else ()
        )
        minimum_pairwise = min(pairwise_distances) if pairwise_distances else None
        mean_nearest_neighbor = (
            sum(nearest_neighbor_distances) / len(nearest_neighbor_distances)
            if nearest_neighbor_distances
            else None
        )
        maximum_nearest_neighbor = (
            max(nearest_neighbor_distances) if nearest_neighbor_distances else None
        )
        return {
            "requested_orientation_count": self.config.orientation_count,
            "raw_sequence_count": self.raw_sequence_count,
            "accepted_sequence_count": self.config.orientation_count,
            "duplicate_orientation_count": self.duplicate_orientation_count,
            "geodesic_duplicate_tolerance_radians_binary64_hex": (
                _GEODESIC_DUPLICATE_TOLERANCE_RADIANS.hex()
            ),
            "minimum_pairwise_geodesic_distance_radians_binary64_hex": (
                None if minimum_pairwise is None else minimum_pairwise.hex()
            ),
            "mean_nearest_neighbor_geodesic_distance_radians_binary64_hex": (
                None if mean_nearest_neighbor is None else mean_nearest_neighbor.hex()
            ),
            "maximum_nearest_neighbor_geodesic_distance_radians_binary64_hex": (
                None
                if maximum_nearest_neighbor is None
                else maximum_nearest_neighbor.hex()
            ),
        }

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "generator_id": GLOBAL_ORIENTATION_GENERATOR_ID,
            "config": self.config.to_dict(),
            "ligand_input_sha256": self.ligand_input_sha256,
            "receptor_surface_input_sha256": self.receptor_surface_input_sha256,
            "source_receipt_sha256": self.source_receipt_sha256,
            "source_seed_sha256": self.source_seed_sha256,
            "profile_id": self.profile_id,
            "pocket_center_binary64_hex": _vector_projection(self.pocket_center),
            "pocket_normal_binary64_hex": _vector_projection(self.pocket_normal),
            "candidate_slot_count": len(self.slots),
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "orientation_coverage_statistics": (
                self._orientation_coverage_statistics()
            ),
            "slot_receipt_sha256s": [slot.receipt_sha256 for slot in self.slots],
            "failure_complete_denominator": True,
            "native_pose_input_consumed": False,
            "score_input_consumed": False,
            "benchmark_outcome_input_consumed": False,
            "fresh_holdout_input_consumed": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GlobalOrientationError("global-orientation batch changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def generate_global_orientation_batch(
    ligand_coordinates: Iterable[Sequence[float]],
    *,
    pocket_center: Sequence[float],
    pocket_normal: Sequence[float],
    receptor_surface_points: Iterable[Sequence[float]] = (),
    config: GlobalOrientationConfig | None = None,
    source_receipt_sha256: str | None = None,
    profile_id: str = GLOBAL_ORIENTATION_GENERATOR_ID,
) -> GlobalOrientationBatch:
    """Generate a deterministic failure-complete rigid proposal grid.

    The signature intentionally has no native-pose, RMSD, benchmark-outcome, or
    scorer-result argument. Receptor points are used only for a bounded steric
    prefilter; rejected slots remain in the denominator.
    """

    active_config = config or GlobalOrientationConfig()
    if type(active_config) is not GlobalOrientationConfig:
        raise TypeError("config must be the exact GlobalOrientationConfig type")
    ligand = _coordinates(
        ligand_coordinates,
        name="ligand_coordinates",
        minimum_count=2,
        maximum_count=MAX_LIGAND_ATOMS,
    )
    receptor = _coordinates(
        receptor_surface_points,
        name="receptor_surface_points",
        minimum_count=0,
        maximum_count=MAX_RECEPTOR_SURFACE_POINTS,
    )
    center = _vector(pocket_center, name="pocket_center")
    normal = _normalize(
        _vector(pocket_normal, name="pocket_normal"),
        name="pocket_normal",
    )
    if source_receipt_sha256 is not None:
        source_receipt_sha256 = _sha256_identity(
            source_receipt_sha256,
            name="source_receipt_sha256",
        )
    profile_identity = _profile_id(profile_id)
    centered_ligand = _center(ligand)
    # Preserve the fail-closed requirement for non-degenerate ligand geometry;
    # independent SO(3) sampling deliberately has no molecule-specific axis
    # alignment step.
    _require_distinct_points(centered_ligand)
    ligand_identity = _coordinate_identity(ligand)
    source_seed_sha256 = _derive_source_seed_sha256(
        source_receipt_sha256=source_receipt_sha256,
        ligand_input_sha256=ligand_identity,
        pocket_center=center,
        pocket_normal=normal,
        profile_id=profile_identity,
    )
    orientations = _orientation_quaternions(
        source_seed_sha256=source_seed_sha256,
        count=active_config.orientation_count,
    )
    translations = _translation_targets(
        pocket_center=center,
        pocket_normal=normal,
        radii=active_config.translation_shell_radii,
        points_per_shell=active_config.translation_points_per_shell,
    )
    receptor_identity = _coordinate_identity(receptor) if receptor else None

    slots: list[GlobalOrientationSlot] = []
    proposal_index = 0
    for orientation_index, orientation in enumerate(orientations):
        quaternion = orientation.quaternion
        rotated = tuple(rotate_vector(point, quaternion) for point in centered_ligand)
        for translation_index, translation in enumerate(translations):
            transformed = tuple(_add(point, translation) for point in rotated)
            minimum_distance = _minimum_distance(transformed, receptor)
            accepted = (
                minimum_distance is None
                or minimum_distance + _EPSILON
                >= active_config.minimum_receptor_distance
            )
            slots.append(
                GlobalOrientationSlot(
                    proposal_index=proposal_index,
                    orientation_index=orientation_index,
                    raw_sequence_index=orientation.raw_sequence_index,
                    accepted_sequence_index=orientation.accepted_sequence_index,
                    translation_index=translation_index,
                    quaternion=quaternion,
                    translation=translation,
                    transformed_coordinates=transformed,
                    accepted=accepted,
                    rejection_code=None if accepted else "receptor_clash",
                    minimum_receptor_distance=minimum_distance,
                )
            )
            proposal_index += 1

    return GlobalOrientationBatch(
        config=active_config,
        ligand_input_sha256=ligand_identity,
        receptor_surface_input_sha256=receptor_identity,
        source_receipt_sha256=source_receipt_sha256,
        source_seed_sha256=source_seed_sha256,
        profile_id=profile_identity,
        pocket_center=center,
        pocket_normal=normal,
        slots=tuple(slots),
    )


__all__ = [
    "Coordinates",
    "GLOBAL_ORIENTATION_BATCH_SCHEMA_ID",
    "GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID",
    "GLOBAL_ORIENTATION_GENERATOR_ID",
    "GLOBAL_ORIENTATION_SOURCE_SEED_SCHEMA_ID",
    "GLOBAL_ORIENTATION_SLOT_SCHEMA_ID",
    "GlobalOrientationBatch",
    "GlobalOrientationConfig",
    "GlobalOrientationError",
    "GlobalOrientationSlot",
    "Quaternion",
    "Vector3",
    "generate_global_orientation_batch",
    "rotate_vector",
]
