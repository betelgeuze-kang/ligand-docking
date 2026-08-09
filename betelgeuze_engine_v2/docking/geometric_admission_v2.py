"""Failure-complete synthetic geometric admission for a fixed64 batch.

Every ligand atom is traversed against every receptor atom in ligand-major,
receptor-minor index order.  The pairwise sphere-intersection volume sum is a
diagnostic overlap proxy (pair intersections may overlap each other).  Pocket
escape is the maximum positive distance by which a ligand atom's vdW sphere
extends beyond the declared pocket sphere::

    max_i(max(0, ||x_i - pocket_center|| + r_i - pocket_radius))

The sole hard rejection is ``minimum_vdw_ratio < 0.55``.  Rejected candidates
remain in the 64-slot denominator and are explicitly rank-ineligible.  This
module binds each decision to an exact mixed64 allocation slot.  Typed
missing-feature slots retain no fabricated coordinates or metrics, while ready
slots retain private canonical inputs sufficient to rederive every metric.
An exact ligand heavy-atom mask controls the heavy-atom penetration count.  The
module evaluates supplied synthetic geometry only; it does not generate poses,
score molecules, run a benchmark, or authorize molecular execution.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
from itertools import islice
import json
import math
import re
from typing import Final, Iterable, TypeVar

from .mixed64_allocation import FixedMixed64Allocation


GEOMETRIC_ADMISSION_V2_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2/2.0.0"
)
GEOMETRIC_ADMISSION_V2_METRICS_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_metrics/2.0.0"
)
GEOMETRIC_ADMISSION_V2_DECISION_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_decision/2.0.0"
)
GEOMETRIC_ADMISSION_V2_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_batch/2.0.0"
)
_GEOMETRIC_ADMISSION_V2_INPUT_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_geometric_admission_v2_exact_inputs/1.0.0"
)
FIXED_CANDIDATE_DENOMINATOR: Final = 64
HARD_REJECTION_MINIMUM_VDW_RATIO: Final = 0.55
ACCEPTED_STATUS: Final = "accepted"
REJECTED_STATUS: Final = "rejected"
TYPED_GENERATION_FAILURE_STATUS: Final = "typed_generation_failure"
TYPED_MISSING_FEATURE_REJECTION_CODE: Final = "mixed64_typed_missing_feature"
SEVERE_PENETRATION_REJECTION_CODE: Final = "severe_receptor_penetration_min_vdw_ratio"
PAIR_TRAVERSAL_ORDER: Final = "full_cartesian_ligand_index_major_receptor_index_minor"
SPHERE_OVERLAP_PROXY_DEFINITION: Final = (
    "sum_of_pairwise_vdw_sphere_intersection_volumes_angstrom3"
)
POCKET_ESCAPE_DEFINITION: Final = (
    "max_zero_or_ligand_center_distance_plus_vdw_radius_minus_pocket_radius"
)
MAX_LIGAND_ATOMS: Final = 512
MAX_RECEPTOR_ATOMS: Final = 4096
# These envelopes are intentionally much wider than a docking pocket while
# excluding values that have no molecular interpretation and can overflow
# derived geometry.  100,000 A is 10 micrometres; a 1,000 A pocket already
# exceeds ordinary atomic docking use.  Atomic vdW radii outside 0.1--10 A are
# likewise treated as corrupt topology evidence rather than extrapolated.
MAX_ABSOLUTE_COORDINATE_ANGSTROM: Final = 100_000.0
MIN_VDW_RADIUS_ANGSTROM: Final = 0.1
MAX_VDW_RADIUS_ANGSTROM: Final = 10.0
MAX_POCKET_RADIUS_ANGSTROM: Final = 1_000.0
# The largest frozen synthetic qualification fixture is 64 * 48 * 4096 =
# 12,582,912 pairs.  This next power-of-two ceiling admits that fixture while
# failing closed before an adversarial fixed64 batch can demand the nominal
# 64 * 512 * 4096 Python traversal.
MAX_BATCH_EXACT_PAIR_EVALUATIONS: Final = 16_777_216
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BATCH_FACTORY_SEAL = object()

Vector3 = tuple[float, float, float]
Coordinates = tuple[Vector3, ...]
_T = TypeVar("_T")


class GeometricAdmissionV2Error(ValueError):
    """Raised when geometric admission input or evidence fails closed."""


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


def _require_digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise GeometricAdmissionV2Error(f"{name} must be a lowercase SHA-256")
    return value


def _finite_float(value: object, *, name: str) -> float:
    if isinstance(value, bool):
        raise GeometricAdmissionV2Error(f"{name} must be a finite number")
    try:
        observed = float(value)  # supports current CPU tensor scalar inputs
    except (TypeError, ValueError, OverflowError) as exc:
        raise GeometricAdmissionV2Error(f"{name} must be a finite number") from exc
    if not math.isfinite(observed):
        raise GeometricAdmissionV2Error(f"{name} must be finite")
    return observed


def _bounded_tuple(
    value: Iterable[_T],
    *,
    name: str,
    maximum_count: int,
) -> tuple[_T, ...]:
    """Collect at most ``maximum_count + 1`` values from any iterable."""

    if isinstance(value, (str, bytes, bytearray)):
        raise GeometricAdmissionV2Error(f"{name} must be a bounded iterable")
    try:
        iterator = iter(value)
    except TypeError as exc:
        raise GeometricAdmissionV2Error(f"{name} must be a bounded iterable") from exc
    observed = tuple(islice(iterator, maximum_count + 1))
    if len(observed) > maximum_count:
        raise GeometricAdmissionV2Error(f"{name} exceeds maximum count {maximum_count}")
    return observed


def _coordinate_component(value: object, *, name: str) -> float:
    observed = _finite_float(value, name=name)
    if abs(observed) > MAX_ABSOLUTE_COORDINATE_ANGSTROM:
        raise GeometricAdmissionV2Error(
            f"{name} exceeds the coordinate safety envelope"
        )
    return observed


def _vector(value: Iterable[float], *, name: str) -> Vector3:
    components = _bounded_tuple(value, name=name, maximum_count=3)
    if len(components) != 3:
        raise GeometricAdmissionV2Error(
            f"{name} must contain exactly three coordinates"
        )
    return tuple(
        _coordinate_component(component, name=f"{name}[{index}]")
        for index, component in enumerate(components)
    )  # type: ignore[return-value]


def _coordinates(
    value: Iterable[Iterable[float]],
    *,
    name: str,
    maximum_count: int,
) -> Coordinates:
    rows = _bounded_tuple(value, name=name, maximum_count=maximum_count)
    if not rows:
        raise GeometricAdmissionV2Error(
            f"{name} count must be within [1, {maximum_count}]"
        )
    return tuple(
        _vector(row, name=f"{name}[{index}]") for index, row in enumerate(rows)
    )


def _radii(
    value: Iterable[float],
    *,
    name: str,
    expected_count: int,
) -> tuple[float, ...]:
    values = _bounded_tuple(value, name=name, maximum_count=expected_count)
    if len(values) != expected_count:
        raise GeometricAdmissionV2Error(
            f"{name} count does not match its atom denominator"
        )
    observed = tuple(
        _finite_float(radius, name=f"{name}[{index}]")
        for index, radius in enumerate(values)
    )
    if any(
        not MIN_VDW_RADIUS_ANGSTROM <= radius <= MAX_VDW_RADIUS_ANGSTROM
        for radius in observed
    ):
        raise GeometricAdmissionV2Error(
            f"{name} values must be within the vdW radius safety envelope"
        )
    return observed


def _heavy_atom_mask(
    value: Iterable[bool],
    *,
    expected_count: int,
) -> tuple[bool, ...]:
    observed = _bounded_tuple(
        value,
        name="ligand_heavy_atom_mask",
        maximum_count=expected_count,
    )
    if len(observed) != expected_count:
        raise GeometricAdmissionV2Error(
            "ligand heavy-atom mask does not match the atom denominator"
        )
    if any(type(item) is not bool for item in observed):
        raise GeometricAdmissionV2Error(
            "ligand heavy-atom mask must contain exact booleans"
        )
    return observed


def _coordinates_projection(value: Coordinates) -> list[list[str]]:
    return [[component.hex() for component in point] for point in value]


def _coordinate_sha256(value: Coordinates) -> str:
    return _sha256(_coordinates_projection(value))


def _distance(left: Vector3, right: Vector3) -> float:
    dx = left[0] - right[0]
    dy = left[1] - right[1]
    dz = left[2] - right[2]
    distance = math.hypot(dx, dy, dz)
    if not math.isfinite(distance):
        raise GeometricAdmissionV2Error("derived center distance is not finite")
    return distance


def _sphere_intersection_volume(
    radius_left: float,
    radius_right: float,
    center_distance: float,
) -> float:
    try:
        radius_sum = radius_left + radius_right
        if center_distance >= radius_sum:
            return 0.0
        radius_difference = abs(radius_left - radius_right)
        if center_distance <= radius_difference:
            smaller = min(radius_left, radius_right)
            volume = (4.0 / 3.0) * math.pi * smaller**3
        else:
            numerator = (
                math.pi
                * (radius_sum - center_distance) ** 2
                * (
                    center_distance**2
                    + 2.0 * center_distance * radius_sum
                    - 3.0 * radius_difference**2
                )
            )
            volume = numerator / (12.0 * center_distance)
    except OverflowError as exc:
        raise GeometricAdmissionV2Error(
            "sphere overlap proxy overflowed its numeric envelope"
        ) from exc
    if not math.isfinite(volume):
        raise GeometricAdmissionV2Error("sphere overlap proxy is not finite")
    # The analytic expression can undershoot zero by a few ulps immediately
    # above internal tangency.  Zero is the physically meaningful lower bound.
    return max(0.0, volume)


@dataclass(frozen=True, slots=True)
class _GeometricAdmissionExactInputsV2:
    """Private canonical inputs sufficient to rederive every slot decision."""

    allocation_receipt_sha256: str
    allocation_slot_receipt_sha256s: tuple[str, ...]
    candidate_coordinates: tuple[Coordinates | None, ...]
    ligand_vdw_radii: tuple[float, ...]
    ligand_heavy_atom_mask: tuple[bool, ...]
    receptor_coordinates: Coordinates
    receptor_vdw_radii: tuple[float, ...]
    pocket_center: Vector3
    pocket_radius: float
    schema_id: str = _GEOMETRIC_ADMISSION_V2_INPUT_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != _GEOMETRIC_ADMISSION_V2_INPUT_SCHEMA_ID:
            raise GeometricAdmissionV2Error(
                "geometric admission exact-input schema is invalid"
            )
        allocation_receipt = _require_digest(
            self.allocation_receipt_sha256,
            name="allocation_receipt_sha256",
        )
        if (
            type(self.allocation_slot_receipt_sha256s) is not tuple
            or len(self.allocation_slot_receipt_sha256s) != FIXED_CANDIDATE_DENOMINATOR
        ):
            raise GeometricAdmissionV2Error(
                "allocation slot receipt denominator is not fixed64"
            )
        slot_receipts = tuple(
            _require_digest(value, name=f"allocation_slot_receipt_sha256s[{index}]")
            for index, value in enumerate(self.allocation_slot_receipt_sha256s)
        )
        if (
            type(self.candidate_coordinates) is not tuple
            or len(self.candidate_coordinates) != FIXED_CANDIDATE_DENOMINATOR
        ):
            raise GeometricAdmissionV2Error(
                "candidate coordinate denominator is not fixed64"
            )
        candidates = tuple(
            None
            if coordinates is None
            else _coordinates(
                coordinates,
                name=f"candidate_coordinates[{slot_index}]",
                maximum_count=MAX_LIGAND_ATOMS,
            )
            for slot_index, coordinates in enumerate(self.candidate_coordinates)
        )
        present = tuple(value for value in candidates if value is not None)
        if not present:
            raise GeometricAdmissionV2Error(
                "at least one generation-eligible coordinate slot is required"
            )
        ligand_atom_count = len(present[0])
        if any(len(value) != ligand_atom_count for value in present):
            raise GeometricAdmissionV2Error(
                "candidate ligand atom denominator changed between ready slots"
            )
        ligand_radii = _radii(
            self.ligand_vdw_radii,
            name="ligand_vdw_radii",
            expected_count=ligand_atom_count,
        )
        heavy_mask = _heavy_atom_mask(
            self.ligand_heavy_atom_mask,
            expected_count=ligand_atom_count,
        )
        receptor = _coordinates(
            self.receptor_coordinates,
            name="receptor_coordinates",
            maximum_count=MAX_RECEPTOR_ATOMS,
        )
        receptor_radii = _radii(
            self.receptor_vdw_radii,
            name="receptor_vdw_radii",
            expected_count=len(receptor),
        )
        center = _vector(self.pocket_center, name="pocket_center")
        radius = _finite_float(self.pocket_radius, name="pocket_radius")
        if not 0.0 < radius <= MAX_POCKET_RADIUS_ANGSTROM:
            raise GeometricAdmissionV2Error(
                "pocket_radius must be within the pocket safety envelope"
            )
        pair_evaluations = len(present) * ligand_atom_count * len(receptor)
        if pair_evaluations > MAX_BATCH_EXACT_PAIR_EVALUATIONS:
            raise GeometricAdmissionV2Error(
                "fixed64 exact pair work exceeds the fail-closed batch limit"
            )
        object.__setattr__(self, "allocation_receipt_sha256", allocation_receipt)
        object.__setattr__(self, "allocation_slot_receipt_sha256s", slot_receipts)
        object.__setattr__(self, "candidate_coordinates", candidates)
        object.__setattr__(self, "ligand_vdw_radii", ligand_radii)
        object.__setattr__(self, "ligand_heavy_atom_mask", heavy_mask)
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "receptor_vdw_radii", receptor_radii)
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_radius", radius)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def ligand_vdw_radii_sha256(self) -> str:
        return _sha256([value.hex() for value in self.ligand_vdw_radii])

    @property
    def ligand_heavy_atom_mask_sha256(self) -> str:
        return _sha256(list(self.ligand_heavy_atom_mask))

    @property
    def receptor_geometry_sha256(self) -> str:
        return _sha256(
            {
                "coordinates_binary64_hex": _coordinates_projection(
                    self.receptor_coordinates
                ),
                "vdw_radii_binary64_hex": [
                    value.hex() for value in self.receptor_vdw_radii
                ],
            }
        )

    @property
    def pocket_geometry_sha256(self) -> str:
        return _sha256(
            {
                "center_binary64_hex": [value.hex() for value in self.pocket_center],
                "radius_binary64_hex": self.pocket_radius.hex(),
                "escape_definition": POCKET_ESCAPE_DEFINITION,
            }
        )

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "allocation_receipt_sha256": self.allocation_receipt_sha256,
            "allocation_slot_receipt_sha256s": list(
                self.allocation_slot_receipt_sha256s
            ),
            "candidate_coordinates_binary64_hex": [
                None if coordinates is None else _coordinates_projection(coordinates)
                for coordinates in self.candidate_coordinates
            ],
            "ligand_vdw_radii_binary64_hex": [
                value.hex() for value in self.ligand_vdw_radii
            ],
            "ligand_heavy_atom_mask": list(self.ligand_heavy_atom_mask),
            "receptor_coordinates_binary64_hex": _coordinates_projection(
                self.receptor_coordinates
            ),
            "receptor_vdw_radii_binary64_hex": [
                value.hex() for value in self.receptor_vdw_radii
            ],
            "pocket_center_binary64_hex": [value.hex() for value in self.pocket_center],
            "pocket_radius_binary64_hex": self.pocket_radius.hex(),
            "pocket_escape_definition": POCKET_ESCAPE_DEFINITION,
            "input_safety_envelope": {
                "maximum_absolute_coordinate_angstrom_binary64_hex": (
                    MAX_ABSOLUTE_COORDINATE_ANGSTROM.hex()
                ),
                "minimum_vdw_radius_angstrom_binary64_hex": (
                    MIN_VDW_RADIUS_ANGSTROM.hex()
                ),
                "maximum_vdw_radius_angstrom_binary64_hex": (
                    MAX_VDW_RADIUS_ANGSTROM.hex()
                ),
                "maximum_pocket_radius_angstrom_binary64_hex": (
                    MAX_POCKET_RADIUS_ANGSTROM.hex()
                ),
            },
            "batch_exact_pair_evaluations": (
                sum(value is not None for value in self.candidate_coordinates)
                * len(self.ligand_vdw_radii)
                * len(self.receptor_coordinates)
            ),
            "maximum_batch_exact_pair_evaluations": (MAX_BATCH_EXACT_PAIR_EVALUATIONS),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GeometricAdmissionV2Error("geometric admission exact inputs changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        """Return complete binary64 inputs so persisted evidence is replayable."""

        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GeometricAdmissionMetricsV2:
    ligand_atom_count: int
    receptor_atom_count: int
    exact_pair_count: int
    raw_minimum_distance_angstrom: float
    minimum_vdw_surface_gap_angstrom: float
    minimum_vdw_ratio: float
    penetration_pair_count: int
    unique_ligand_penetration_atom_count: int
    unique_ligand_heavy_atom_penetration_count: int
    sphere_overlap_proxy_angstrom3: float
    pocket_escape_angstrom: float
    schema_id: str = GEOMETRIC_ADMISSION_V2_METRICS_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GEOMETRIC_ADMISSION_V2_METRICS_SCHEMA_ID:
            raise GeometricAdmissionV2Error(
                "geometric admission metrics schema is invalid"
            )
        for name, value, maximum in (
            ("ligand_atom_count", self.ligand_atom_count, MAX_LIGAND_ATOMS),
            ("receptor_atom_count", self.receptor_atom_count, MAX_RECEPTOR_ATOMS),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise GeometricAdmissionV2Error(f"{name} is invalid")
        if (
            type(self.exact_pair_count) is not int
            or self.exact_pair_count
            != self.ligand_atom_count * self.receptor_atom_count
        ):
            raise GeometricAdmissionV2Error(
                "exact pair count is not the full Cartesian denominator"
            )
        raw_distance = _finite_float(
            self.raw_minimum_distance_angstrom,
            name="raw_minimum_distance_angstrom",
        )
        surface_gap = _finite_float(
            self.minimum_vdw_surface_gap_angstrom,
            name="minimum_vdw_surface_gap_angstrom",
        )
        minimum_ratio = _finite_float(
            self.minimum_vdw_ratio,
            name="minimum_vdw_ratio",
        )
        overlap = _finite_float(
            self.sphere_overlap_proxy_angstrom3,
            name="sphere_overlap_proxy_angstrom3",
        )
        pocket_escape = _finite_float(
            self.pocket_escape_angstrom,
            name="pocket_escape_angstrom",
        )
        if raw_distance < 0.0 or minimum_ratio < 0.0:
            raise GeometricAdmissionV2Error(
                "distance and vdW ratio metrics cannot be negative"
            )
        if overlap < 0.0 or pocket_escape < 0.0:
            raise GeometricAdmissionV2Error(
                "overlap and pocket escape metrics cannot be negative"
            )
        if (
            type(self.penetration_pair_count) is not int
            or not 0 <= self.penetration_pair_count <= self.exact_pair_count
        ):
            raise GeometricAdmissionV2Error("penetration pair count is invalid")
        if (
            type(self.unique_ligand_penetration_atom_count) is not int
            or not 0
            <= self.unique_ligand_penetration_atom_count
            <= self.ligand_atom_count
        ):
            raise GeometricAdmissionV2Error(
                "unique ligand penetration atom count is invalid"
            )
        if (
            type(self.unique_ligand_heavy_atom_penetration_count) is not int
            or not 0
            <= self.unique_ligand_heavy_atom_penetration_count
            <= self.unique_ligand_penetration_atom_count
        ):
            raise GeometricAdmissionV2Error(
                "unique ligand heavy-atom penetration count is invalid"
            )
        if self.unique_ligand_penetration_atom_count > self.penetration_pair_count:
            raise GeometricAdmissionV2Error(
                "unique penetration atoms exceed penetrating pairs"
            )
        if (self.penetration_pair_count == 0) is not (
            self.unique_ligand_penetration_atom_count == 0
        ):
            raise GeometricAdmissionV2Error(
                "penetration pair and unique-atom counts disagree"
            )
        if self.penetration_pair_count == 0 and overlap != 0.0:
            raise GeometricAdmissionV2Error(
                "non-penetrating geometry cannot report sphere overlap"
            )
        if self.penetration_pair_count > 0 and overlap <= 0.0:
            raise GeometricAdmissionV2Error(
                "penetrating geometry must report positive sphere overlap"
            )
        object.__setattr__(self, "raw_minimum_distance_angstrom", raw_distance)
        object.__setattr__(
            self,
            "minimum_vdw_surface_gap_angstrom",
            surface_gap,
        )
        object.__setattr__(self, "minimum_vdw_ratio", minimum_ratio)
        object.__setattr__(self, "sphere_overlap_proxy_angstrom3", overlap)
        object.__setattr__(self, "pocket_escape_angstrom", pocket_escape)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "ligand_atom_count": self.ligand_atom_count,
            "receptor_atom_count": self.receptor_atom_count,
            "exact_pair_count": self.exact_pair_count,
            "pair_traversal_order": PAIR_TRAVERSAL_ORDER,
            "raw_minimum_distance_angstrom_binary64_hex": (
                self.raw_minimum_distance_angstrom.hex()
            ),
            "minimum_vdw_surface_gap_angstrom_binary64_hex": (
                self.minimum_vdw_surface_gap_angstrom.hex()
            ),
            "minimum_vdw_ratio_binary64_hex": self.minimum_vdw_ratio.hex(),
            "penetration_pair_count": self.penetration_pair_count,
            "penetration_definition": "center_distance_less_than_vdw_radius_sum",
            "unique_ligand_penetration_atom_count": (
                self.unique_ligand_penetration_atom_count
            ),
            "unique_ligand_heavy_atom_penetration_count": (
                self.unique_ligand_heavy_atom_penetration_count
            ),
            "heavy_atom_definition": "exact_ligand_heavy_atom_mask_true",
            "sphere_overlap_proxy_angstrom3_binary64_hex": (
                self.sphere_overlap_proxy_angstrom3.hex()
            ),
            "sphere_overlap_proxy_definition": SPHERE_OVERLAP_PROXY_DEFINITION,
            "pocket_escape_angstrom_binary64_hex": (self.pocket_escape_angstrom.hex()),
            "pocket_escape_definition": POCKET_ESCAPE_DEFINITION,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GeometricAdmissionV2Error("geometric admission metrics changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GeometricAdmissionDecisionV2:
    slot_index: int
    allocation_slot_receipt_sha256: str
    lane: str
    allocation_generation_eligible: bool
    allocation_missing_feature_codes: tuple[str, ...]
    candidate_coordinate_sha256: str | None
    metrics: GeometricAdmissionMetricsV2 | None
    status: str
    rejection_code: str | None
    rank_eligible: bool
    schema_id: str = GEOMETRIC_ADMISSION_V2_DECISION_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != GEOMETRIC_ADMISSION_V2_DECISION_SCHEMA_ID:
            raise GeometricAdmissionV2Error(
                "geometric admission decision schema is invalid"
            )
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            raise GeometricAdmissionV2Error("geometric admission slot index is invalid")
        allocation_slot_receipt = _require_digest(
            self.allocation_slot_receipt_sha256,
            name="allocation_slot_receipt_sha256",
        )
        if (
            type(self.lane) is not str
            or not self.lane
            or self.lane != self.lane.strip()
        ):
            raise GeometricAdmissionV2Error(
                "geometric admission lane identity is invalid"
            )
        if type(self.allocation_generation_eligible) is not bool:
            raise GeometricAdmissionV2Error(
                "allocation generation eligibility must be boolean"
            )
        if type(self.allocation_missing_feature_codes) is not tuple or any(
            type(value) is not str or not value or value != value.strip()
            for value in self.allocation_missing_feature_codes
        ):
            raise GeometricAdmissionV2Error(
                "allocation missing-feature codes are invalid"
            )
        if type(self.rank_eligible) is not bool:
            raise GeometricAdmissionV2Error("rank eligibility must be boolean")
        coordinate_sha256 = self.candidate_coordinate_sha256
        if self.allocation_generation_eligible:
            if self.allocation_missing_feature_codes:
                raise GeometricAdmissionV2Error(
                    "ready allocation slot cannot contain feature failures"
                )
            coordinate_sha256 = _require_digest(
                coordinate_sha256,
                name="candidate_coordinate_sha256",
            )
            if type(self.metrics) is not GeometricAdmissionMetricsV2:
                raise TypeError(
                    "ready slot metrics must be exact GeometricAdmissionMetricsV2"
                )
            accepted = (
                self.metrics.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO
            )
            expected_status = ACCEPTED_STATUS if accepted else REJECTED_STATUS
            expected_code = None if accepted else SEVERE_PENETRATION_REJECTION_CODE
            if self.status != expected_status or self.rejection_code != expected_code:
                raise GeometricAdmissionV2Error(
                    "geometric admission decision changed its sole hard rule"
                )
            if self.rank_eligible is not accepted:
                raise GeometricAdmissionV2Error(
                    "geometric admission rank eligibility disagrees with rejection"
                )
        else:
            if not self.allocation_missing_feature_codes:
                raise GeometricAdmissionV2Error(
                    "generation-ineligible slot requires typed feature failures"
                )
            if coordinate_sha256 is not None or self.metrics is not None:
                raise GeometricAdmissionV2Error(
                    "generation-ineligible slot cannot fabricate geometry or metrics"
                )
            if (
                self.status != TYPED_GENERATION_FAILURE_STATUS
                or self.rejection_code != TYPED_MISSING_FEATURE_REJECTION_CODE
                or self.rank_eligible
            ):
                raise GeometricAdmissionV2Error(
                    "typed generation failure decision is inconsistent"
                )
        object.__setattr__(
            self,
            "candidate_coordinate_sha256",
            coordinate_sha256,
        )
        object.__setattr__(
            self,
            "allocation_slot_receipt_sha256",
            allocation_slot_receipt,
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def accepted(self) -> bool:
        return self.status == ACCEPTED_STATUS

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": GEOMETRIC_ADMISSION_V2_COMPONENT_ID,
            "slot_index": self.slot_index,
            "allocation_slot_receipt_sha256": (self.allocation_slot_receipt_sha256),
            "lane": self.lane,
            "allocation_generation_eligible": (self.allocation_generation_eligible),
            "allocation_missing_feature_codes": list(
                self.allocation_missing_feature_codes
            ),
            "candidate_coordinate_sha256": self.candidate_coordinate_sha256,
            "metrics": None if self.metrics is None else self.metrics.to_dict(),
            "decision_basis": (
                "minimum_vdw_ratio"
                if self.allocation_generation_eligible
                else "allocation_typed_missing_feature"
            ),
            "hard_rejection_metric": (
                "minimum_vdw_ratio" if self.allocation_generation_eligible else None
            ),
            "hard_rejection_operator": (
                "strictly_less_than" if self.allocation_generation_eligible else None
            ),
            "hard_rejection_threshold_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
                if self.allocation_generation_eligible
                else None
            ),
            "status": self.status,
            "rejection_code": self.rejection_code,
            "rank_eligible": self.rank_eligible,
            "slot_preserved_in_denominator": True,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GeometricAdmissionV2Error("geometric admission decision changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class GeometricAdmissionBatchV2:
    allocation: FixedMixed64Allocation
    decisions: tuple[GeometricAdmissionDecisionV2, ...]
    _exact_inputs: _GeometricAdmissionExactInputsV2 = field(repr=False)
    _factory_seal: InitVar[object | None] = None
    schema_id: str = GEOMETRIC_ADMISSION_V2_BATCH_SCHEMA_ID
    component_id: str = GEOMETRIC_ADMISSION_V2_COMPONENT_ID
    _receipt_sha256: str = field(init=False, repr=False)
    _validated_allocation_receipt_sha256: str = field(init=False, repr=False)
    _validated_exact_input_receipt_sha256: str = field(init=False, repr=False)
    _validated_decision_receipt_sha256s: tuple[str, ...] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            raise GeometricAdmissionV2Error(
                "geometric admission batch must use the bounded evaluator factory"
            )
        if self.schema_id != GEOMETRIC_ADMISSION_V2_BATCH_SCHEMA_ID:
            raise GeometricAdmissionV2Error(
                "geometric admission batch schema is invalid"
            )
        if self.component_id != GEOMETRIC_ADMISSION_V2_COMPONENT_ID:
            raise GeometricAdmissionV2Error(
                "geometric admission component identity is invalid"
            )
        if type(self.allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be the exact FixedMixed64Allocation type")
        if type(self._exact_inputs) is not _GeometricAdmissionExactInputsV2:
            raise TypeError(
                "exact inputs must be the private geometric input binding type"
            )
        if (
            self._exact_inputs.allocation_receipt_sha256
            != self.allocation.receipt_sha256
            or self._exact_inputs.allocation_slot_receipt_sha256s
            != tuple(slot.receipt_sha256 for slot in self.allocation.slots)
        ):
            raise GeometricAdmissionV2Error(
                "geometric inputs are cross-wired to another mixed64 allocation"
            )
        for slot, coordinates in zip(
            self.allocation.slots,
            self._exact_inputs.candidate_coordinates,
            strict=True,
        ):
            if slot.generation_eligible is (coordinates is None):
                raise GeometricAdmissionV2Error(
                    "candidate coordinate presence disagrees with allocation eligibility"
                )
        if type(self.decisions) is not tuple or any(
            type(decision) is not GeometricAdmissionDecisionV2
            for decision in self.decisions
        ):
            raise TypeError(
                "decisions must contain exact GeometricAdmissionDecisionV2 values"
            )
        if len(self.decisions) != FIXED_CANDIDATE_DENOMINATOR:
            raise GeometricAdmissionV2Error(
                "geometric admission denominator is not fixed64"
            )
        if tuple(decision.slot_index for decision in self.decisions) != tuple(
            range(FIXED_CANDIDATE_DENOMINATOR)
        ):
            raise GeometricAdmissionV2Error(
                "geometric admission decisions are not index-stable"
            )
        # The factory immediately below is the sole constructor and derives each
        # decision once from the private exact inputs.  Re-running the full
        # Cartesian traversal here doubled the bounded pair workload while adding
        # no independent trust boundary.  Keep lightweight lineage checks here;
        # persisted artifacts are independently replayed by the standalone
        # verifier in a fresh process.
        for slot, coordinates, decision in zip(
            self.allocation.slots,
            self._exact_inputs.candidate_coordinates,
            self.decisions,
            strict=True,
        ):
            if (
                decision.allocation_slot_receipt_sha256 != slot.receipt_sha256
                or decision.lane != slot.lane
                or decision.allocation_generation_eligible
                is not slot.generation_eligible
                or decision.allocation_missing_feature_codes
                != slot.missing_feature_codes
            ):
                raise GeometricAdmissionV2Error(
                    "geometric decision is cross-wired to another allocation slot"
                )
            expected_coordinate_sha256 = (
                None if coordinates is None else _coordinate_sha256(coordinates)
            )
            if decision.candidate_coordinate_sha256 != expected_coordinate_sha256:
                raise GeometricAdmissionV2Error(
                    "geometric decision coordinate identity is cross-wired"
                )
        object.__setattr__(
            self,
            "_validated_allocation_receipt_sha256",
            self.allocation.receipt_sha256,
        )
        object.__setattr__(
            self,
            "_validated_exact_input_receipt_sha256",
            self._exact_inputs.receipt_sha256,
        )
        object.__setattr__(
            self,
            "_validated_decision_receipt_sha256s",
            tuple(decision.receipt_sha256 for decision in self.decisions),
        )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def ligand_vdw_radii_sha256(self) -> str:
        return self._exact_inputs.ligand_vdw_radii_sha256

    @property
    def ligand_heavy_atom_mask_sha256(self) -> str:
        return self._exact_inputs.ligand_heavy_atom_mask_sha256

    @property
    def receptor_geometry_sha256(self) -> str:
        return self._exact_inputs.receptor_geometry_sha256

    @property
    def pocket_geometry_sha256(self) -> str:
        return self._exact_inputs.pocket_geometry_sha256

    @property
    def accepted_count(self) -> int:
        return sum(decision.accepted for decision in self.decisions)

    @property
    def nonaccepted_count(self) -> int:
        return len(self.decisions) - self.accepted_count

    @property
    def typed_generation_failure_count(self) -> int:
        return sum(
            decision.status == TYPED_GENERATION_FAILURE_STATUS
            for decision in self.decisions
        )

    @property
    def geometric_rejected_count(self) -> int:
        return sum(decision.status == REJECTED_STATUS for decision in self.decisions)

    @property
    def rank_eligibility(self) -> tuple[bool, ...]:
        return tuple(decision.rank_eligible for decision in self.decisions)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": self.component_id,
            "candidate_denominator": len(self.decisions),
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_profile_id": self.allocation.profile_id,
            "allocation": self.allocation.to_dict(),
            "allocation_slot_receipt_sha256s": [
                slot.receipt_sha256 for slot in self.allocation.slots
            ],
            "exact_input_binding_sha256": self._exact_inputs.receipt_sha256,
            "exact_inputs": self._exact_inputs.to_dict(),
            "ligand_vdw_radii_sha256": self.ligand_vdw_radii_sha256,
            "ligand_heavy_atom_mask_sha256": (self.ligand_heavy_atom_mask_sha256),
            "receptor_geometry_sha256": self.receptor_geometry_sha256,
            "pocket_geometry_sha256": self.pocket_geometry_sha256,
            "hard_rejection_minimum_vdw_ratio_binary64_hex": (
                HARD_REJECTION_MINIMUM_VDW_RATIO.hex()
            ),
            "accepted_count": self.accepted_count,
            "nonaccepted_count": self.nonaccepted_count,
            "typed_generation_failure_count": self.typed_generation_failure_count,
            "geometric_rejected_count": self.geometric_rejected_count,
            "decision_receipt_sha256s": [
                decision.receipt_sha256 for decision in self.decisions
            ],
            "decisions": [decision.to_dict() for decision in self.decisions],
            "rejected_slots_preserved": True,
            "rejected_slots_rank_ineligible": True,
            "score_input_consumed": False,
            "benchmark_outcome_input_consumed": False,
            "molecular_execution_authorized": False,
            "production_claim_authorized": False,
        }

    def _validate_immutable_bindings(self) -> None:
        if self.allocation.receipt_sha256 != self._validated_allocation_receipt_sha256:
            raise GeometricAdmissionV2Error("mixed64 allocation changed")
        if (
            self._exact_inputs.receipt_sha256
            != self._validated_exact_input_receipt_sha256
        ):
            raise GeometricAdmissionV2Error("geometric admission exact inputs changed")
        if (
            tuple(decision.receipt_sha256 for decision in self.decisions)
            != self._validated_decision_receipt_sha256s
        ):
            raise GeometricAdmissionV2Error("geometric admission decisions changed")

    @property
    def receipt_sha256(self) -> str:
        self._validate_immutable_bindings()
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise GeometricAdmissionV2Error("geometric admission batch changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        self._validate_immutable_bindings()
        projection = self._projection()
        observed = _sha256(projection)
        if observed != self._receipt_sha256:
            raise GeometricAdmissionV2Error("geometric admission batch changed")
        return {**projection, "receipt_sha256": observed}


def _evaluate_metrics(
    ligand_coordinates: Coordinates,
    ligand_radii: tuple[float, ...],
    ligand_heavy_atom_mask: tuple[bool, ...],
    receptor_coordinates: Coordinates,
    receptor_radii: tuple[float, ...],
    pocket_center: Vector3,
    pocket_radius: float,
) -> GeometricAdmissionMetricsV2:
    raw_minimum_distance = math.inf
    minimum_surface_gap = math.inf
    minimum_ratio = math.inf
    penetration_pair_count = 0
    penetrating_ligand_indices: set[int] = set()
    penetrating_heavy_ligand_indices: set[int] = set()
    sphere_overlap_proxy = 0.0

    for ligand_index, (ligand_point, ligand_radius) in enumerate(
        zip(ligand_coordinates, ligand_radii, strict=True)
    ):
        for receptor_point, receptor_radius in zip(
            receptor_coordinates,
            receptor_radii,
            strict=True,
        ):
            distance = _distance(ligand_point, receptor_point)
            radius_sum = ligand_radius + receptor_radius
            surface_gap = distance - radius_sum
            ratio = distance / radius_sum
            raw_minimum_distance = min(raw_minimum_distance, distance)
            minimum_surface_gap = min(minimum_surface_gap, surface_gap)
            minimum_ratio = min(minimum_ratio, ratio)
            if distance < radius_sum:
                penetration_pair_count += 1
                penetrating_ligand_indices.add(ligand_index)
                if ligand_heavy_atom_mask[ligand_index]:
                    penetrating_heavy_ligand_indices.add(ligand_index)
                sphere_overlap_proxy = math.fsum(
                    (
                        sphere_overlap_proxy,
                        _sphere_intersection_volume(
                            ligand_radius,
                            receptor_radius,
                            distance,
                        ),
                    )
                )
                if not math.isfinite(sphere_overlap_proxy):
                    raise GeometricAdmissionV2Error(
                        "sphere overlap proxy accumulation is not finite"
                    )

    pocket_escape = max(
        max(
            0.0,
            _distance(point, pocket_center) + radius - pocket_radius,
        )
        for point, radius in zip(
            ligand_coordinates,
            ligand_radii,
            strict=True,
        )
    )
    return GeometricAdmissionMetricsV2(
        ligand_atom_count=len(ligand_coordinates),
        receptor_atom_count=len(receptor_coordinates),
        exact_pair_count=len(ligand_coordinates) * len(receptor_coordinates),
        raw_minimum_distance_angstrom=raw_minimum_distance,
        minimum_vdw_surface_gap_angstrom=minimum_surface_gap,
        minimum_vdw_ratio=minimum_ratio,
        penetration_pair_count=penetration_pair_count,
        unique_ligand_penetration_atom_count=len(penetrating_ligand_indices),
        unique_ligand_heavy_atom_penetration_count=len(
            penetrating_heavy_ligand_indices
        ),
        sphere_overlap_proxy_angstrom3=sphere_overlap_proxy,
        pocket_escape_angstrom=pocket_escape,
    )


def evaluate_geometric_admission_metrics_one_python(
    ligand_coordinates: Iterable[Iterable[float]],
    *,
    ligand_vdw_radii: Iterable[float],
    ligand_heavy_atom_mask: Iterable[bool],
    receptor_coordinates: Iterable[Iterable[float]],
    receptor_vdw_radii: Iterable[float],
    pocket_center: Iterable[float],
    pocket_radius: float,
) -> GeometricAdmissionMetricsV2:
    """Run the bounded one-candidate Python reference geometric kernel.

    The wrapper applies the same bounded normalization as fixed64 batch input
    construction and then dispatches to its exact ``_evaluate_metrics``
    implementation. Synthetic parity uses this validation surface; timing uses
    the already-normalized internal boundary that fixed64 calls per candidate.
    """

    ligand = _coordinates(
        ligand_coordinates,
        name="ligand_coordinates",
        maximum_count=MAX_LIGAND_ATOMS,
    )
    ligand_radii = _radii(
        ligand_vdw_radii,
        name="ligand_vdw_radii",
        expected_count=len(ligand),
    )
    heavy_mask = _heavy_atom_mask(
        ligand_heavy_atom_mask,
        expected_count=len(ligand),
    )
    receptor = _coordinates(
        receptor_coordinates,
        name="receptor_coordinates",
        maximum_count=MAX_RECEPTOR_ATOMS,
    )
    receptor_radii = _radii(
        receptor_vdw_radii,
        name="receptor_vdw_radii",
        expected_count=len(receptor),
    )
    center = _vector(pocket_center, name="pocket_center")
    radius = _finite_float(pocket_radius, name="pocket_radius")
    if not 0.0 < radius <= MAX_POCKET_RADIUS_ANGSTROM:
        raise GeometricAdmissionV2Error(
            "pocket_radius must be within the pocket safety envelope"
        )
    if len(ligand) * len(receptor) > MAX_BATCH_EXACT_PAIR_EVALUATIONS:
        raise GeometricAdmissionV2Error(
            "one-candidate exact pair work exceeds the fail-closed limit"
        )
    return _evaluate_metrics(
        ligand,
        ligand_radii,
        heavy_mask,
        receptor,
        receptor_radii,
        center,
        radius,
    )


def _derive_decisions(
    allocation: FixedMixed64Allocation,
    exact_inputs: _GeometricAdmissionExactInputsV2,
) -> tuple[GeometricAdmissionDecisionV2, ...]:
    decisions: list[GeometricAdmissionDecisionV2] = []
    for slot, coordinates in zip(
        allocation.slots,
        exact_inputs.candidate_coordinates,
        strict=True,
    ):
        common = {
            "slot_index": slot.slot_index,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "lane": slot.lane,
            "allocation_generation_eligible": slot.generation_eligible,
            "allocation_missing_feature_codes": slot.missing_feature_codes,
        }
        if not slot.generation_eligible:
            if coordinates is not None:
                raise GeometricAdmissionV2Error(
                    "typed missing-feature slot received fabricated coordinates"
                )
            decisions.append(
                GeometricAdmissionDecisionV2(
                    **common,
                    candidate_coordinate_sha256=None,
                    metrics=None,
                    status=TYPED_GENERATION_FAILURE_STATUS,
                    rejection_code=TYPED_MISSING_FEATURE_REJECTION_CODE,
                    rank_eligible=False,
                )
            )
            continue
        if coordinates is None:
            raise GeometricAdmissionV2Error(
                "generation-eligible slot is missing candidate coordinates"
            )
        metrics = _evaluate_metrics(
            coordinates,
            exact_inputs.ligand_vdw_radii,
            exact_inputs.ligand_heavy_atom_mask,
            exact_inputs.receptor_coordinates,
            exact_inputs.receptor_vdw_radii,
            exact_inputs.pocket_center,
            exact_inputs.pocket_radius,
        )
        accepted = metrics.minimum_vdw_ratio >= HARD_REJECTION_MINIMUM_VDW_RATIO
        decisions.append(
            GeometricAdmissionDecisionV2(
                **common,
                candidate_coordinate_sha256=_coordinate_sha256(coordinates),
                metrics=metrics,
                status=ACCEPTED_STATUS if accepted else REJECTED_STATUS,
                rejection_code=(
                    None if accepted else SEVERE_PENETRATION_REJECTION_CODE
                ),
                rank_eligible=accepted,
            )
        )
    return tuple(decisions)


class GeometricAdmissionV2:
    """Evaluate one exact synthetic fixed64 coordinate batch."""

    __slots__ = ()
    component_id = GEOMETRIC_ADMISSION_V2_COMPONENT_ID
    hard_rejection_minimum_vdw_ratio = HARD_REJECTION_MINIMUM_VDW_RATIO

    def admit_fixed64(
        self,
        candidate_coordinates: Iterable[Iterable[Iterable[float]] | None],
        *,
        allocation: FixedMixed64Allocation,
        ligand_vdw_radii: Iterable[float],
        ligand_heavy_atom_mask: Iterable[bool],
        receptor_coordinates: Iterable[Iterable[float]],
        receptor_vdw_radii: Iterable[float],
        pocket_center: Iterable[float],
        pocket_radius: float,
    ) -> GeometricAdmissionBatchV2:
        """Measure and admit exactly 64 slots without deleting failures."""

        if type(allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be the exact FixedMixed64Allocation type")
        candidates = _bounded_tuple(
            candidate_coordinates,
            name="candidate_coordinates",
            maximum_count=FIXED_CANDIDATE_DENOMINATOR,
        )
        if len(candidates) != FIXED_CANDIDATE_DENOMINATOR:
            raise GeometricAdmissionV2Error(
                "geometric admission requires exactly 64 candidate slots"
            )
        # Canonicalize every externally supplied iterable through a bounded
        # collector before the private receipt type sees it.  Inner coordinate
        # rows remain bounded by _coordinates/_vector during canonicalization.
        ligand_radii_input = _bounded_tuple(
            ligand_vdw_radii,
            name="ligand_vdw_radii",
            maximum_count=MAX_LIGAND_ATOMS,
        )
        heavy_mask_input = _bounded_tuple(
            ligand_heavy_atom_mask,
            name="ligand_heavy_atom_mask",
            maximum_count=MAX_LIGAND_ATOMS,
        )
        receptor_coordinates_input = _bounded_tuple(
            receptor_coordinates,
            name="receptor_coordinates",
            maximum_count=MAX_RECEPTOR_ATOMS,
        )
        receptor_radii_input = _bounded_tuple(
            receptor_vdw_radii,
            name="receptor_vdw_radii",
            maximum_count=MAX_RECEPTOR_ATOMS,
        )
        pocket_center_input = _bounded_tuple(
            pocket_center,
            name="pocket_center",
            maximum_count=3,
        )
        exact_inputs = _GeometricAdmissionExactInputsV2(
            allocation_receipt_sha256=allocation.receipt_sha256,
            allocation_slot_receipt_sha256s=tuple(
                slot.receipt_sha256 for slot in allocation.slots
            ),
            candidate_coordinates=candidates,
            ligand_vdw_radii=ligand_radii_input,
            ligand_heavy_atom_mask=heavy_mask_input,
            receptor_coordinates=receptor_coordinates_input,
            receptor_vdw_radii=receptor_radii_input,
            pocket_center=pocket_center_input,
            pocket_radius=pocket_radius,
        )
        decisions = _derive_decisions(allocation, exact_inputs)
        return GeometricAdmissionBatchV2(
            allocation=allocation,
            decisions=decisions,
            _exact_inputs=exact_inputs,
            _factory_seal=_BATCH_FACTORY_SEAL,
        )


__all__ = [
    "ACCEPTED_STATUS",
    "FIXED_CANDIDATE_DENOMINATOR",
    "GEOMETRIC_ADMISSION_V2_BATCH_SCHEMA_ID",
    "GEOMETRIC_ADMISSION_V2_COMPONENT_ID",
    "GEOMETRIC_ADMISSION_V2_DECISION_SCHEMA_ID",
    "GEOMETRIC_ADMISSION_V2_METRICS_SCHEMA_ID",
    "GeometricAdmissionBatchV2",
    "GeometricAdmissionDecisionV2",
    "GeometricAdmissionMetricsV2",
    "GeometricAdmissionV2",
    "GeometricAdmissionV2Error",
    "HARD_REJECTION_MINIMUM_VDW_RATIO",
    "MAX_ABSOLUTE_COORDINATE_ANGSTROM",
    "MAX_BATCH_EXACT_PAIR_EVALUATIONS",
    "MAX_LIGAND_ATOMS",
    "MAX_POCKET_RADIUS_ANGSTROM",
    "MAX_RECEPTOR_ATOMS",
    "MAX_VDW_RADIUS_ANGSTROM",
    "MIN_VDW_RADIUS_ANGSTROM",
    "PAIR_TRAVERSAL_ORDER",
    "POCKET_ESCAPE_DEFINITION",
    "REJECTED_STATUS",
    "SEVERE_PENETRATION_REJECTION_CODE",
    "SPHERE_OVERLAP_PROXY_DEFINITION",
    "TYPED_GENERATION_FAILURE_STATUS",
    "TYPED_MISSING_FEATURE_REJECTION_CODE",
    "evaluate_geometric_admission_metrics_one_python",
]
