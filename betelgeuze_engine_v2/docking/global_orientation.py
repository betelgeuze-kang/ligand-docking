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
GLOBAL_ORIENTATION_SLOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_slot/1.0.0"
)
GLOBAL_ORIENTATION_BATCH_SCHEMA_ID = (
    "betelgeuze.engine_v2_global_orientation_batch/1.0.0"
)
GLOBAL_ORIENTATION_GENERATOR_ID = "deterministic_surface_aware_rigid_v1"
MAX_LIGAND_ATOMS = 512
MAX_RECEPTOR_SURFACE_POINTS = 4096
MAX_ORIENTATIONS = 512
MAX_TRANSLATION_SHELLS = 32
MAX_TRANSLATION_POINTS_PER_SHELL = 256
MAX_CANDIDATE_SLOTS = 65536
_EPSILON = 1.0e-12
_GOLDEN_RATIO_CONJUGATE = (math.sqrt(5.0) - 1.0) / 2.0
_SQRT2_FRACTION = math.sqrt(2.0) - 1.0

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


def _long_axis(coordinates: Coordinates) -> Vector3:
    best_distance = -1.0
    best_pair: tuple[int, int] | None = None
    for left_index, left in enumerate(coordinates[:-1]):
        for right_index in range(left_index + 1, len(coordinates)):
            delta = _subtract(coordinates[right_index], left)
            distance = _dot(delta, delta)
            candidate_pair = (left_index, right_index)
            if distance > best_distance + _EPSILON or (
                abs(distance - best_distance) <= _EPSILON
                and (best_pair is None or candidate_pair < best_pair)
            ):
                best_distance = distance
                best_pair = candidate_pair
    if best_pair is None or best_distance <= _EPSILON:
        raise GlobalOrientationError(
            "ligand coordinates must contain at least two distinct points"
        )
    return _normalize(
        _subtract(coordinates[best_pair[1]], coordinates[best_pair[0]]),
        name="ligand long axis",
    )


def _quaternion_normalize(value: Quaternion) -> Quaternion:
    length = math.sqrt(sum(component * component for component in value))
    if length <= _EPSILON:
        raise GlobalOrientationError("quaternion must be non-zero")
    normalized = tuple(component / length for component in value)
    if normalized[3] < 0.0:
        normalized = tuple(-component for component in normalized)
    return normalized  # type: ignore[return-value]


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


def _hopf_quaternion(index: int, count: int) -> Quaternion:
    unit_1 = (index + 0.5) / count
    unit_2 = (index * _GOLDEN_RATIO_CONJUGATE) % 1.0
    unit_3 = (index * _SQRT2_FRACTION) % 1.0
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


def _orientation_quaternions(
    *,
    long_axis: Vector3,
    pocket_normal: Vector3,
    count: int,
) -> tuple[Quaternion, ...]:
    basis = _orthonormal_basis(pocket_normal)
    aligned_to_normal = _quaternion_between(long_axis, basis[2])
    aligned_to_tangent = _quaternion_between(long_axis, basis[0])
    orientations: list[Quaternion] = []
    for candidate in (aligned_to_normal, aligned_to_tangent):
        if len(orientations) < count and candidate not in orientations:
            orientations.append(candidate)
    hopf_index = 0
    while len(orientations) < count:
        candidate = _hopf_quaternion(hopf_index, max(1, count))
        hopf_index += 1
        if any(
            sum((left - right) ** 2 for left, right in zip(candidate, existing))
            <= 1.0e-20
            for existing in orientations
        ):
            continue
        orientations.append(candidate)
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
            ("translation_index", self.translation_index),
        ):
            if type(value) is not int or value < 0:
                raise GlobalOrientationError(
                    f"{name} must be a non-negative integer"
                )
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
        if len(self.ligand_input_sha256) != 64:
            raise GlobalOrientationError("ligand input SHA-256 is invalid")
        if self.receptor_surface_input_sha256 is not None and len(
            self.receptor_surface_input_sha256
        ) != 64:
            raise GlobalOrientationError(
                "receptor surface input SHA-256 is invalid"
            )
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
            raise GlobalOrientationError(
                "orientation/translation grid is incomplete"
            )
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

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "generator_id": GLOBAL_ORIENTATION_GENERATOR_ID,
            "config": self.config.to_dict(),
            "ligand_input_sha256": self.ligand_input_sha256,
            "receptor_surface_input_sha256": self.receptor_surface_input_sha256,
            "pocket_center_binary64_hex": _vector_projection(self.pocket_center),
            "pocket_normal_binary64_hex": _vector_projection(self.pocket_normal),
            "candidate_slot_count": len(self.slots),
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
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
    centered_ligand = _center(ligand)
    long_axis = _long_axis(centered_ligand)
    orientations = _orientation_quaternions(
        long_axis=long_axis,
        pocket_normal=normal,
        count=active_config.orientation_count,
    )
    translations = _translation_targets(
        pocket_center=center,
        pocket_normal=normal,
        radii=active_config.translation_shell_radii,
        points_per_shell=active_config.translation_points_per_shell,
    )
    ligand_identity = _coordinate_identity(ligand)
    receptor_identity = _coordinate_identity(receptor) if receptor else None

    slots: list[GlobalOrientationSlot] = []
    proposal_index = 0
    for orientation_index, quaternion in enumerate(orientations):
        rotated = tuple(
            rotate_vector(point, quaternion) for point in centered_ligand
        )
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
        pocket_center=center,
        pocket_normal=normal,
        slots=tuple(slots),
    )


__all__ = [
    "Coordinates",
    "GLOBAL_ORIENTATION_BATCH_SCHEMA_ID",
    "GLOBAL_ORIENTATION_CONFIG_SCHEMA_ID",
    "GLOBAL_ORIENTATION_GENERATOR_ID",
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
