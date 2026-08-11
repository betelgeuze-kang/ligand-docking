"""Failure-complete source-bound producer for the frozen mixed64 allocation.

The producer emits exactly one record for each of the 64 preallocated slots.
It rederives source proposal, source-receipt, coordinate, and V7 lineage
identities from complete payloads; executes only deterministic geometry; and
turns expected generation failures into typed, denominator-preserving receipts.

This is still a synthetic pre-activation component. It does not refine, score,
rank, evaluate final pose validity, run a molecular case, or grant authority.
"""

from __future__ import annotations

from dataclasses import InitVar, dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import stat
from typing import TYPE_CHECKING, Final, Iterable, Mapping, Sequence

from .mixed64_allocation import (
    FIXED_MIXED64_CANDIDATE_COUNT,
    GENERATION_PARENT_EXACT_PASSTHROUGH,
    LANE_AROMATIC_PLANE,
    LANE_COMPLEMENTARY_CHARGE,
    LANE_DETERMINISTIC_INDEPENDENT_SO3,
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
    LANE_PAIRED_RETAINED_CONTROLS,
    LANE_POCKET_CENTERED_CONTROLS,
    LANE_PRINCIPAL_AXIS_SHAPE,
    LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
    LANE_UNIFORM_SOURCE_CONTROLS,
    FixedMixed64Allocation,
)
from .mixed64_proposal_geometry_v3 import (
    MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256,
    IndexedSO3PlacementReceiptV1,
    Mixed64ProposalGeometryError,
    SingleAnchorPlacementReceiptV1,
    coordinate_sha256,
    generate_indexed_so3_placement,
    generate_single_anchor_placement,
)

if TYPE_CHECKING:
    from .pipeline_candidate_evidence_v2 import ProposalExecutionReceiptV2


MIXED64_COORDINATE_SOURCE_PAYLOAD_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_coordinate_source_payload/1.0.0"
)
MIXED64_PROPOSAL_SOURCE_BUNDLE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_source_bundle/1.0.0"
)
MIXED64_EXACT_PASSTHROUGH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_exact_passthrough_placement/1.0.0"
)
MIXED64_GENERATION_FAILURE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_generation_failure/1.0.0"
)
MIXED64_GENERATION_RECORD_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_generation_record/1.0.0"
)
MIXED64_PRODUCER_BATCH_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_proposal_producer_batch/1.0.0"
)
MIXED64_PRODUCER_COMPONENT_ID: Final = (
    "betelgeuze.engine_v2_mixed64_fixed64_producer_v3/1.0.0"
)
MIXED64_PRODUCER_PROFILE_ID: Final = (
    "betelgeuze.engine_v2_global_orientation_fixed_mixed64_producer/1.0.0"
)
MIXED64_GENERATED_PROPOSAL_ID_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_mixed64_generated_proposal_identity/1.0.0"
)

SOURCE_KIND_EXACT_V11_BASE: Final = "exact_v11_base"
SOURCE_KIND_V7_CONTROL: Final = "v7_control"
SOURCE_KIND_TRUE_CONFORMER: Final = "true_conformer"
SOURCE_KIND_RETAINED_CONTROL: Final = "retained_control"
_SOURCE_KINDS: Final = {
    SOURCE_KIND_EXACT_V11_BASE,
    SOURCE_KIND_V7_CONTROL,
    SOURCE_KIND_TRUE_CONFORMER,
    SOURCE_KIND_RETAINED_CONTROL,
}

GENERATION_STATUS_SUCCESS: Final = "generated"
GENERATION_STATUS_FAILURE: Final = "typed_generation_failure"
ALLOCATION_MISSING_FEATURE_FAILURE: Final = "allocation_typed_missing_feature"
MISSING_EXACT_V11_SOURCE_PAYLOAD: Final = "missing_exact_v11_source_payload"
MISSING_V7_CONTROL_SOURCE_PAYLOAD: Final = "missing_v7_control_source_payload"
MISSING_CONFORMER_SOURCE_PAYLOAD: Final = "missing_conformer_source_payload"
MISSING_RETAINED_SOURCE_PAYLOAD: Final = "missing_retained_source_payload"
LIGAND_ATOM_DENOMINATOR_MISMATCH: Final = "ligand_atom_denominator_mismatch"
SOURCE_PAYLOAD_CROSS_WIRING: Final = "source_payload_cross_wiring"
SOURCE_PAYLOAD_RECEIPT_INVALID: Final = "source_payload_receipt_invalid"
SOURCE_PAYLOAD_NONCANONICAL: Final = "source_payload_noncanonical"
PRODUCER_SOURCE_CHANGED: Final = "producer_implementation_source_changed"

MAX_LIGAND_ATOMS: Final = 512
MAX_RECEPTOR_ATOMS: Final = 4096
MAX_SOURCE_JSON_BYTES: Final = 4 * 1024 * 1024
MAX_PRODUCER_SOURCE_BYTES: Final = 4 * 1024 * 1024
MAX_CANONICAL_RECEIPT_BYTES: Final = 64 * 1024 * 1024
MAX_JSON_DEPTH: Final = 64
MAX_JSON_NODES: Final = 250_000
MAX_JSON_ITEMS: Final = 100_000
MAX_JSON_STRING_BYTES: Final = 4 * 1024 * 1024
MAX_ABSOLUTE_JSON_INTEGER: Final = (1 << 53) - 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Vector3 = tuple[float, float, float]
Coordinates = tuple[Vector3, ...]

_PASSTHROUGH_LANES: Final = {
    LANE_POCKET_CENTERED_CONTROLS,
    LANE_UNIFORM_SOURCE_CONTROLS,
    LANE_PAIRED_RETAINED_CONTROLS,
}
_SO3_LANES: Final = {
    LANE_DETERMINISTIC_INDEPENDENT_SO3,
    LANE_TRUE_CONFORMER_INDEPENDENT_SO3,
}
_ANCHOR_LANES: Final = {
    LANE_LIGAND_DONOR_TO_RECEPTOR_ACCEPTOR,
    LANE_LIGAND_ACCEPTOR_TO_RECEPTOR_DONOR,
    LANE_COMPLEMENTARY_CHARGE,
    LANE_AROMATIC_PLANE,
    LANE_PRINCIPAL_AXIS_SHAPE,
}

_BATCH_FACTORY_SEAL = object()
_RECORD_FACTORY_SEAL = object()


class Mixed64ProposalProducerError(ValueError):
    """Raised when source-bound production cannot safely preserve semantics."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise Mixed64ProposalProducerError(code, message)


def _normalize_json(value: object) -> object:
    state = {"nodes": 0, "active": set()}

    def visit(item: object, *, depth: int) -> object:
        state["nodes"] = int(state["nodes"]) + 1
        if depth > MAX_JSON_DEPTH or int(state["nodes"]) > MAX_JSON_NODES:
            _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON exceeds depth or node bounds")
        active = state["active"]
        assert isinstance(active, set)
        if isinstance(item, Mapping):
            if len(item) > MAX_JSON_ITEMS:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON mapping exceeds item bounds")
            identity = id(item)
            if identity in active:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON contains a reference cycle")
            active.add(identity)
            try:
                normalized: dict[str, object] = {}
                for key, nested in item.items():
                    if type(key) is not str or not key or key != key.strip():
                        _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON key is not canonical")
                    if len(key.encode("utf-8")) > 256 or key in normalized:
                        _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON key exceeds bounds")
                    normalized[key] = visit(nested, depth=depth + 1)
                return normalized
            finally:
                active.remove(identity)
        if isinstance(item, (list, tuple)):
            if len(item) > MAX_JSON_ITEMS:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON sequence exceeds item bounds")
            identity = id(item)
            if identity in active:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON contains a reference cycle")
            active.add(identity)
            try:
                return [visit(nested, depth=depth + 1) for nested in item]
            finally:
                active.remove(identity)
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            if abs(item) > MAX_ABSOLUTE_JSON_INTEGER:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON integer exceeds exact bounds")
            return item
        if type(item) is float:
            if not math.isfinite(item):
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON float must be finite")
            return item
        if type(item) is str:
            if len(item.encode("utf-8")) > MAX_JSON_STRING_BYTES:
                _fail(SOURCE_PAYLOAD_NONCANONICAL, "JSON string exceeds byte bounds")
            return item
        _fail(SOURCE_PAYLOAD_NONCANONICAL, "payload contains a non-JSON value")

    return visit(value, depth=0)


def _canonical_bytes(value: object) -> bytes:
    encoded = json.dumps(
        _normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    if len(encoded) > MAX_CANONICAL_RECEIPT_BYTES:
        _fail(SOURCE_PAYLOAD_NONCANONICAL, "canonical receipt exceeds byte bounds")
    return encoded


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must be a lowercase SHA-256")
    return value


def _parse_canonical_payload(value: object, *, name: str) -> dict[str, object]:
    if type(value) is not bytes or not value or len(value) > MAX_SOURCE_JSON_BYTES:
        _fail(SOURCE_PAYLOAD_NONCANONICAL, f"{name} must be bounded bytes")
    raw = value[:-1] if value.endswith(b"\n") else value
    if not raw or raw.endswith(b"\n"):
        _fail(SOURCE_PAYLOAD_NONCANONICAL, f"{name} has invalid terminal bytes")
    try:
        document = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Mixed64ProposalProducerError(
            SOURCE_PAYLOAD_NONCANONICAL,
            f"{name} is invalid JSON",
        ) from exc
    if type(document) is not dict:
        _fail(SOURCE_PAYLOAD_NONCANONICAL, f"{name} must be one JSON object")
    canonical = _canonical_bytes(document)
    if raw != canonical:
        _fail(SOURCE_PAYLOAD_NONCANONICAL, f"{name} is not canonical JSON")
    return document


def _canonical_payload_bytes(value: bytes, *, name: str) -> bytes:
    return _canonical_bytes(_parse_canonical_payload(value, name=name))


def _rederive_receipt_sha256(value: bytes, *, name: str) -> str:
    document = _parse_canonical_payload(value, name=name)
    embedded = document.pop("receipt_sha256", None)
    observed = _sha256(document)
    if embedded != observed:
        _fail(SOURCE_PAYLOAD_RECEIPT_INVALID, f"{name} receipt does not rederive")
    return observed


def _finite(value: object, *, name: str) -> float:
    if type(value) not in {int, float}:
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must be numeric")
    observed = float(value)
    if not math.isfinite(observed):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must be finite")
    return observed


def _vector(value: Sequence[float], *, name: str) -> Vector3:
    if isinstance(value, (str, bytes, bytearray)) or len(value) != 3:
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must contain three values")
    return tuple(
        _finite(component, name=f"{name}[{index}]")
        for index, component in enumerate(value)
    )  # type: ignore[return-value]


def _coordinates(
    value: Iterable[Sequence[float]],
    *,
    name: str,
    maximum_count: int,
) -> Coordinates:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must be an iterable")
    iterator = iter(value)
    rows = []
    for index in range(maximum_count + 1):
        try:
            row = next(iterator)
        except StopIteration:
            break
        rows.append(_vector(row, name=f"{name}[{index}]"))
    if not rows or len(rows) > maximum_count:
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} denominator is invalid")
    return tuple(rows)


def _radii(
    value: Iterable[float],
    *,
    name: str,
    expected_count: int,
) -> tuple[float, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} must be an iterable")
    iterator = iter(value)
    rows = []
    for index in range(expected_count + 1):
        try:
            item = next(iterator)
        except StopIteration:
            break
        rows.append(_finite(item, name=f"{name}[{index}]"))
    observed = tuple(rows)
    if len(observed) != expected_count or any(not 0.1 <= item <= 10.0 for item in observed):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} denominator or range is invalid")
    return observed


def _heavy_mask(value: Iterable[bool], *, expected_count: int) -> tuple[bool, ...]:
    if isinstance(value, (str, bytes, bytearray)):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, "ligand heavy-atom mask must be iterable")
    iterator = iter(value)
    rows = []
    for _ in range(expected_count + 1):
        try:
            rows.append(next(iterator))
        except StopIteration:
            break
    observed = tuple(rows)
    if len(observed) != expected_count or any(type(item) is not bool for item in observed):
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, "ligand heavy-atom mask is invalid")
    return observed


def _projection_coordinates(value: Coordinates) -> list[list[str]]:
    return [[component.hex() for component in point] for point in value]


def _projection_vector(value: Vector3) -> list[str]:
    return [component.hex() for component in value]


def _source_ordinal_valid(kind: str, ordinal: int | None) -> bool:
    if kind == SOURCE_KIND_EXACT_V11_BASE:
        return ordinal is None
    if type(ordinal) is not int:
        return False
    if kind == SOURCE_KIND_V7_CONTROL:
        return 0 <= ordinal < 24
    if kind == SOURCE_KIND_TRUE_CONFORMER:
        return 2 <= ordinal <= 8
    if kind == SOURCE_KIND_RETAINED_CONTROL:
        return ordinal in {36, 45, 54, 63}
    return False


@dataclass(frozen=True, slots=True)
class Mixed64CoordinateSourcePayloadV1:
    """Complete payloads that rederive one proposal source and its identities."""

    source_kind: str
    source_ordinal: int | None
    proposal_identity_payload_canonical_json: bytes = field(repr=False)
    source_receipt_canonical_json: bytes = field(repr=False)
    coordinates: Coordinates = field(repr=False)
    proposal_lineage_canonical_json: bytes | None = field(default=None, repr=False)
    schema_id: str = MIXED64_COORDINATE_SOURCE_PAYLOAD_SCHEMA_ID
    _proposal_sha256: str = field(init=False, repr=False)
    _source_receipt_sha256: str = field(init=False, repr=False)
    _coordinate_sha256: str = field(init=False, repr=False)
    _proposal_lineage_sha256: str | None = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_COORDINATE_SOURCE_PAYLOAD_SCHEMA_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "coordinate source schema changed")
        if self.source_kind not in _SOURCE_KINDS or not _source_ordinal_valid(
            self.source_kind,
            self.source_ordinal,
        ):
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "source kind or ordinal is invalid")
        proposal_bytes = _canonical_payload_bytes(
            self.proposal_identity_payload_canonical_json,
            name="proposal identity payload",
        )
        source_receipt_bytes = _canonical_payload_bytes(
            self.source_receipt_canonical_json,
            name="source receipt payload",
        )
        proposal_sha256 = hashlib.sha256(proposal_bytes).hexdigest()
        source_receipt_sha256 = _rederive_receipt_sha256(
            source_receipt_bytes,
            name="source receipt payload",
        )
        coordinates = _coordinates(
            self.coordinates,
            name="source coordinates",
            maximum_count=MAX_LIGAND_ATOMS,
        )
        lineage_bytes: bytes | None = None
        lineage_sha256: str | None = None
        if self.proposal_lineage_canonical_json is not None:
            lineage_bytes = _canonical_payload_bytes(
                self.proposal_lineage_canonical_json,
                name="proposal lineage payload",
            )
            lineage_sha256 = hashlib.sha256(lineage_bytes).hexdigest()
        if (self.source_kind == SOURCE_KIND_V7_CONTROL) is not (
            lineage_bytes is not None
        ):
            _fail(
                SOURCE_PAYLOAD_CROSS_WIRING,
                "only V7 controls require one proposal lineage payload",
            )
        object.__setattr__(
            self,
            "proposal_identity_payload_canonical_json",
            proposal_bytes,
        )
        object.__setattr__(self, "source_receipt_canonical_json", source_receipt_bytes)
        object.__setattr__(self, "coordinates", coordinates)
        object.__setattr__(self, "proposal_lineage_canonical_json", lineage_bytes)
        object.__setattr__(self, "_proposal_sha256", proposal_sha256)
        object.__setattr__(self, "_source_receipt_sha256", source_receipt_sha256)
        object.__setattr__(self, "_coordinate_sha256", coordinate_sha256(coordinates))
        object.__setattr__(self, "_proposal_lineage_sha256", lineage_sha256)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def proposal_sha256(self) -> str:
        return self._proposal_sha256

    @property
    def source_receipt_sha256(self) -> str:
        return self._source_receipt_sha256

    @property
    def coordinate_sha256(self) -> str:
        return self._coordinate_sha256

    @property
    def proposal_lineage_sha256(self) -> str | None:
        return self._proposal_lineage_sha256

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "source_kind": self.source_kind,
            "source_ordinal": self.source_ordinal,
            "proposal_sha256": self.proposal_sha256,
            "proposal_identity_payload": _parse_canonical_payload(
                self.proposal_identity_payload_canonical_json,
                name="proposal identity payload",
            ),
            "source_receipt_sha256": self.source_receipt_sha256,
            "source_receipt": _parse_canonical_payload(
                self.source_receipt_canonical_json,
                name="source receipt payload",
            ),
            "coordinate_sha256": self.coordinate_sha256,
            "coordinates_binary64_hex": _projection_coordinates(self.coordinates),
            "proposal_lineage_sha256": self.proposal_lineage_sha256,
            "proposal_lineage": (
                None
                if self.proposal_lineage_canonical_json is None
                else _parse_canonical_payload(
                    self.proposal_lineage_canonical_json,
                    name="proposal lineage payload",
                )
            ),
            "identity_payloads_rederived": True,
            "result_fields_consumed": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "coordinate source payload changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64ProposalSourceBundleV1:
    """All pre-result coordinate and topology inputs available to the producer."""

    allocation: FixedMixed64Allocation = field(repr=False)
    exact_v11_source: Mixed64CoordinateSourcePayloadV1 | None
    v7_control_sources: tuple[Mixed64CoordinateSourcePayloadV1, ...]
    conformer_sources: tuple[Mixed64CoordinateSourcePayloadV1, ...]
    retained_sources: tuple[Mixed64CoordinateSourcePayloadV1, ...]
    ligand_vdw_radii: tuple[float, ...]
    ligand_heavy_atom_mask: tuple[bool, ...]
    receptor_coordinates: Coordinates = field(repr=False)
    receptor_vdw_radii: tuple[float, ...]
    receptor_source_receipt_canonical_json: bytes = field(repr=False)
    pocket_center: Vector3
    pocket_normal: Vector3
    pocket_radius: float
    schema_id: str = MIXED64_PROPOSAL_SOURCE_BUNDLE_SCHEMA_ID
    _receptor_source_receipt_sha256: str = field(init=False, repr=False)
    _receptor_coordinate_sha256: str = field(init=False, repr=False)
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_PROPOSAL_SOURCE_BUNDLE_SCHEMA_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "source bundle schema changed")
        if type(self.allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be the exact FixedMixed64Allocation type")
        if self.exact_v11_source is not None:
            if type(self.exact_v11_source) is not Mixed64CoordinateSourcePayloadV1:
                raise TypeError("exact source must be exact coordinate source evidence")
            if self.exact_v11_source.source_kind != SOURCE_KIND_EXACT_V11_BASE:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "exact source kind changed")
            exact_evidence = self.allocation.features.exact_v11_source
            if (
                self.exact_v11_source.source_receipt_sha256,
                self.exact_v11_source.proposal_sha256,
                self.exact_v11_source.coordinate_sha256,
            ) != (
                exact_evidence.source_receipt_sha256,
                exact_evidence.proposal_sha256,
                exact_evidence.ligand_coordinate_sha256,
            ):
                _fail(
                    SOURCE_PAYLOAD_CROSS_WIRING,
                    "exact V1.1 receipt, proposal, or ligand coordinates changed",
                )
        normalized_groups: list[tuple[Mixed64CoordinateSourcePayloadV1, ...]] = []
        for name, values, kind in (
            ("v7_control_sources", self.v7_control_sources, SOURCE_KIND_V7_CONTROL),
            ("conformer_sources", self.conformer_sources, SOURCE_KIND_TRUE_CONFORMER),
            ("retained_sources", self.retained_sources, SOURCE_KIND_RETAINED_CONTROL),
        ):
            if type(values) is not tuple or any(
                type(value) is not Mixed64CoordinateSourcePayloadV1 for value in values
            ):
                raise TypeError(f"{name} must contain exact source payloads")
            if any(value.source_kind != kind for value in values):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} contains a wrong source kind")
            if len({value.source_ordinal for value in values}) != len(values):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} contains duplicate ordinals")
            ordered = tuple(sorted(values, key=lambda value: int(value.source_ordinal)))
            if ordered != values:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"{name} is not canonically ordered")
            normalized_groups.append(ordered)
        v7_controls, conformers, retained = normalized_groups
        for source in v7_controls:
            expected = self.allocation.features.v7_control_for_index(
                int(source.source_ordinal)
            )
            if expected is None or (
                source.proposal_sha256,
                source.coordinate_sha256,
                source.source_receipt_sha256,
                source.proposal_lineage_sha256,
            ) != (
                expected.proposal_sha256,
                expected.coordinate_sha256,
                expected.source_receipt_sha256,
                expected.proposal_lineage_sha256,
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "V7 source payload is cross-wired")
        for source in conformers:
            expected = self.allocation.features.conformer_for_rank(
                int(source.source_ordinal)
            )
            if expected is None or (
                source.proposal_sha256,
                source.coordinate_sha256,
                source.source_receipt_sha256,
            ) != (
                expected.proposal_sha256,
                expected.coordinate_sha256,
                expected.source_receipt_sha256,
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "conformer payload is cross-wired")
        for source in retained:
            expected = self.allocation.features.retained_for_index(
                int(source.source_ordinal)
            )
            if expected is None or (
                source.proposal_sha256,
                source.coordinate_sha256,
                source.source_receipt_sha256,
            ) != (
                expected.proposal_sha256,
                expected.coordinate_sha256,
                expected.source_receipt_sha256,
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "retained payload is cross-wired")
        all_sources = (
            (() if self.exact_v11_source is None else (self.exact_v11_source,))
            + v7_controls
            + conformers
            + retained
        )
        ligand_atom_count = (
            len(all_sources[0].coordinates)
            if all_sources
            else len(self.ligand_vdw_radii)
        )
        if not 1 <= ligand_atom_count <= MAX_LIGAND_ATOMS or any(
            len(source.coordinates) != ligand_atom_count for source in all_sources
        ):
            _fail(LIGAND_ATOM_DENOMINATOR_MISMATCH, "source atom denominators differ")
        ligand_radii = _radii(
            self.ligand_vdw_radii,
            name="ligand_vdw_radii",
            expected_count=ligand_atom_count,
        )
        heavy_mask = _heavy_mask(
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
        receptor_source_bytes = _canonical_payload_bytes(
            self.receptor_source_receipt_canonical_json,
            name="receptor source receipt",
        )
        receptor_source_sha = _rederive_receipt_sha256(
            receptor_source_bytes,
            name="receptor source receipt",
        )
        exact_evidence = self.allocation.features.exact_v11_source
        receptor_coordinate_sha = coordinate_sha256(receptor)
        if (
            receptor_source_sha != exact_evidence.source_receipt_sha256
            or receptor_coordinate_sha != exact_evidence.receptor_coordinate_sha256
        ):
            _fail(
                SOURCE_PAYLOAD_CROSS_WIRING,
                "receptor receipt or coordinates are not exact V1.1 evidence",
            )
        center = _vector(self.pocket_center, name="pocket_center")
        normal = _vector(self.pocket_normal, name="pocket_normal")
        normal_length = math.sqrt(sum(value * value for value in normal))
        if normal_length <= 1.0e-12:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "pocket normal is degenerate")
        normal = tuple(value / normal_length for value in normal)  # type: ignore[assignment]
        radius = _finite(self.pocket_radius, name="pocket_radius")
        if not 0.0 < radius <= 1_000.0:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "pocket radius is outside bounds")
        object.__setattr__(self, "v7_control_sources", v7_controls)
        object.__setattr__(self, "conformer_sources", conformers)
        object.__setattr__(self, "retained_sources", retained)
        object.__setattr__(self, "ligand_vdw_radii", ligand_radii)
        object.__setattr__(self, "ligand_heavy_atom_mask", heavy_mask)
        object.__setattr__(self, "receptor_coordinates", receptor)
        object.__setattr__(self, "receptor_vdw_radii", receptor_radii)
        object.__setattr__(
            self,
            "receptor_source_receipt_canonical_json",
            receptor_source_bytes,
        )
        object.__setattr__(self, "pocket_center", center)
        object.__setattr__(self, "pocket_normal", normal)
        object.__setattr__(self, "pocket_radius", radius)
        object.__setattr__(self, "_receptor_source_receipt_sha256", receptor_source_sha)
        object.__setattr__(self, "_receptor_coordinate_sha256", receptor_coordinate_sha)
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def receptor_source_receipt_sha256(self) -> str:
        return self._receptor_source_receipt_sha256

    @property
    def receptor_coordinate_sha256(self) -> str:
        return self._receptor_coordinate_sha256

    def v7_control_for_index(self, index: int) -> Mixed64CoordinateSourcePayloadV1 | None:
        return next((value for value in self.v7_control_sources if value.source_ordinal == index), None)

    def conformer_for_rank(self, rank: int) -> Mixed64CoordinateSourcePayloadV1 | None:
        return next((value for value in self.conformer_sources if value.source_ordinal == rank), None)

    def retained_for_index(self, index: int) -> Mixed64CoordinateSourcePayloadV1 | None:
        return next((value for value in self.retained_sources if value.source_ordinal == index), None)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "exact_v11_source": (
                None if self.exact_v11_source is None else self.exact_v11_source.to_dict()
            ),
            "v7_control_sources": [value.to_dict() for value in self.v7_control_sources],
            "conformer_sources": [value.to_dict() for value in self.conformer_sources],
            "retained_sources": [value.to_dict() for value in self.retained_sources],
            "ligand_vdw_radii_binary64_hex": [value.hex() for value in self.ligand_vdw_radii],
            "ligand_heavy_atom_mask": list(self.ligand_heavy_atom_mask),
            "receptor_source_receipt_sha256": self.receptor_source_receipt_sha256,
            "receptor_source_receipt": _parse_canonical_payload(
                self.receptor_source_receipt_canonical_json,
                name="receptor source receipt",
            ),
            "receptor_coordinate_sha256": self.receptor_coordinate_sha256,
            "receptor_coordinates_binary64_hex": _projection_coordinates(self.receptor_coordinates),
            "receptor_vdw_radii_binary64_hex": [value.hex() for value in self.receptor_vdw_radii],
            "pocket_center_binary64_hex": _projection_vector(self.pocket_center),
            "pocket_normal_binary64_hex": _projection_vector(self.pocket_normal),
            "pocket_radius_binary64_hex": self.pocket_radius.hex(),
            "all_present_source_payload_identities_rederived": True,
            "missing_source_payloads_allowed_only_as_typed_slot_failures": True,
            "result_fields_consumed": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "proposal source bundle changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def frozen_mixed64_producer_policy() -> dict[str, object]:
    return {
        "schema_id": "betelgeuze.engine_v2_mixed64_producer_policy/1.0.0",
        "component_id": MIXED64_PRODUCER_COMPONENT_ID,
        "profile_id": MIXED64_PRODUCER_PROFILE_ID,
        "candidate_denominator": FIXED_MIXED64_CANDIDATE_COUNT,
        "geometry_policy_sha256": MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256,
        "lane_execution": {
            "exact_passthrough": sorted(_PASSTHROUGH_LANES),
            "indexed_so3": sorted(_SO3_LANES),
            "single_anchor": sorted(_ANCHOR_LANES),
        },
        "source_payload_requirements": {
            "proposal_identity_payload_required": True,
            "source_receipt_payload_required": True,
            "coordinate_payload_required": True,
            "v7_lineage_payload_required": True,
            "payload_hashes_rederived": True,
            "exact_v11_receipt_proposal_ligand_coordinates_bound": True,
            "exact_v11_receptor_coordinates_bound": True,
            "prepared_ligand_receptor_topologies_bound": True,
            "exact_v11_binding_pre_result": True,
        },
        "failure_semantics": {
            "one_record_per_slot_required": True,
            "allocation_failure_preserved": True,
            "missing_source_payload_preserved": True,
            "typed_geometry_failure_preserved": True,
            "fallback_lane_allowed": False,
            "slot_reallocation_allowed": False,
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
        "status": "synthetic_pre_activation_producer_only",
    }


MIXED64_PRODUCER_POLICY_SHA256: Final = _sha256(frozen_mixed64_producer_policy())


@dataclass(frozen=True, slots=True)
class ExactPassthroughPlacementReceiptV1:
    allocation: FixedMixed64Allocation = field(repr=False)
    source_bundle_receipt_sha256: str
    slot_index: int
    source_payload: Mixed64CoordinateSourcePayloadV1 = field(repr=False)
    schema_id: str = MIXED64_EXACT_PASSTHROUGH_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_EXACT_PASSTHROUGH_SCHEMA_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "passthrough schema changed")
        if type(self.allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be exact")
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "passthrough slot is invalid")
        slot = self.allocation.slots[self.slot_index]
        if slot.lane not in _PASSTHROUGH_LANES or not slot.generation_eligible:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "slot is not a ready passthrough")
        _digest(self.source_bundle_receipt_sha256, name="source bundle receipt")
        if type(self.source_payload) is not Mixed64CoordinateSourcePayloadV1:
            raise TypeError("source payload must be exact")
        expected_ordinal = (
            slot.v7_control_source_index
            if slot.lane != LANE_PAIRED_RETAINED_CONTROLS
            else slot.retained_source_index
        )
        expected_kind = (
            SOURCE_KIND_RETAINED_CONTROL
            if slot.lane == LANE_PAIRED_RETAINED_CONTROLS
            else SOURCE_KIND_V7_CONTROL
        )
        expected_evidence = (
            self.allocation.features.retained_for_index(int(expected_ordinal))
            if slot.lane == LANE_PAIRED_RETAINED_CONTROLS
            else self.allocation.features.v7_control_for_index(int(expected_ordinal))
        )
        if (
            expected_evidence is None
            or self.source_payload.source_kind != expected_kind
            or self.source_payload.source_ordinal != expected_ordinal
            or self.source_payload.proposal_sha256
            != slot.selected_generation_parent_proposal_sha256
            or self.source_payload.coordinate_sha256
            != slot.selected_generation_parent_coordinate_sha256
            or self.source_payload.source_receipt_sha256
            != expected_evidence.source_receipt_sha256
            or (expected_evidence.receipt_sha256,)
            != slot.selected_source_receipt_sha256s
            or slot.generation_parent_role != GENERATION_PARENT_EXACT_PASSTHROUGH
        ):
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "passthrough source changed")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def output_coordinates(self) -> Coordinates:
        return self.source_payload.coordinates

    @property
    def output_coordinate_sha256(self) -> str:
        return self.source_payload.coordinate_sha256

    def _projection(self) -> dict[str, object]:
        slot = self.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PRODUCER_COMPONENT_ID,
            "producer_policy_sha256": MIXED64_PRODUCER_POLICY_SHA256,
            "source_bundle_receipt_sha256": self.source_bundle_receipt_sha256,
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "source_payload_receipt_sha256": self.source_payload.receipt_sha256,
            "source_proposal_sha256": self.source_payload.proposal_sha256,
            "source_coordinate_sha256": self.source_payload.coordinate_sha256,
            "output_coordinate_sha256": self.output_coordinate_sha256,
            "output_coordinates_binary64_hex": _projection_coordinates(self.output_coordinates),
            "exact_coordinate_passthrough": True,
            "result_fields_consumed": False,
            "authority_granted": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "passthrough receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class ProposalGenerationFailureReceiptV1:
    allocation: FixedMixed64Allocation = field(repr=False)
    source_bundle_receipt_sha256: str
    slot_index: int
    failure_code: str
    allocation_missing_feature_codes: tuple[str, ...]
    attempted_source_payload_receipt_sha256: str | None = None
    geometry_error_message: str | None = None
    schema_id: str = MIXED64_GENERATION_FAILURE_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.schema_id != MIXED64_GENERATION_FAILURE_SCHEMA_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation failure schema changed")
        if type(self.allocation) is not FixedMixed64Allocation:
            raise TypeError("allocation must be exact")
        if type(self.slot_index) is not int or not 0 <= self.slot_index < 64:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "failure slot is invalid")
        _digest(self.source_bundle_receipt_sha256, name="source bundle receipt")
        if type(self.failure_code) is not str or re.fullmatch(
            r"[a-z][a-z0-9_]{2,127}", self.failure_code
        ) is None:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "failure code is not canonical")
        slot = self.allocation.slots[self.slot_index]
        if self.allocation_missing_feature_codes != slot.missing_feature_codes:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "allocation failure codes changed")
        if not slot.generation_eligible:
            if self.failure_code != ALLOCATION_MISSING_FEATURE_FAILURE:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "allocation failure was relabeled")
        elif self.failure_code == ALLOCATION_MISSING_FEATURE_FAILURE:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "ready slot fabricated allocation failure")
        if self.attempted_source_payload_receipt_sha256 is not None:
            _digest(
                self.attempted_source_payload_receipt_sha256,
                name="attempted source payload receipt",
            )
        if self.geometry_error_message is not None and (
            type(self.geometry_error_message) is not str
            or not self.geometry_error_message
            or len(self.geometry_error_message.encode("utf-8")) > 4096
        ):
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "geometry error message is invalid")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        slot = self.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PRODUCER_COMPONENT_ID,
            "producer_policy_sha256": MIXED64_PRODUCER_POLICY_SHA256,
            "source_bundle_receipt_sha256": self.source_bundle_receipt_sha256,
            "allocation_receipt_sha256": self.allocation.receipt_sha256,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "failure_code": self.failure_code,
            "allocation_missing_feature_codes": list(self.allocation_missing_feature_codes),
            "attempted_source_payload_receipt_sha256": (
                self.attempted_source_payload_receipt_sha256
            ),
            "geometry_error_message": self.geometry_error_message,
            "coordinate_emitted": False,
            "proposal_execution_receipt_emitted": False,
            "slot_preserved_in_denominator": True,
            "fallback_or_reallocation_allowed": False,
            "result_fields_consumed": False,
            "authority_granted": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation failure receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


PlacementReceipt = (
    ExactPassthroughPlacementReceiptV1
    | IndexedSO3PlacementReceiptV1
    | SingleAnchorPlacementReceiptV1
)


@dataclass(frozen=True, slots=True)
class Mixed64ProposalGenerationRecordV1:
    allocation: FixedMixed64Allocation = field(repr=False)
    source_bundle_receipt_sha256: str
    slot_index: int
    status: str
    source_proposal_sha256: str | None
    source_coordinate_sha256: str | None
    output_coordinates: Coordinates | None = field(repr=False)
    placement_receipt: PlacementReceipt | None
    proposal_execution_receipt: ProposalExecutionReceiptV2 | None
    failure_receipt: ProposalGenerationFailureReceiptV1 | None
    _factory_seal: InitVar[object | None] = None
    schema_id: str = MIXED64_GENERATION_RECORD_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _RECORD_FACTORY_SEAL:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation record requires factory")
        if self.schema_id != MIXED64_GENERATION_RECORD_SCHEMA_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation record schema changed")
        _digest(self.source_bundle_receipt_sha256, name="source bundle receipt")
        slot = self.allocation.slots[self.slot_index]
        if self.status == GENERATION_STATUS_SUCCESS:
            if (
                self.source_proposal_sha256 is None
                or self.source_coordinate_sha256 is None
                or self.output_coordinates is None
                or self.placement_receipt is None
                or self.proposal_execution_receipt is None
                or self.failure_receipt is not None
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "success record is incomplete")
            _digest(self.source_proposal_sha256, name="generated proposal")
            _digest(self.source_coordinate_sha256, name="generated coordinate")
            coordinates = _coordinates(
                self.output_coordinates,
                name="generated coordinates",
                maximum_count=MAX_LIGAND_ATOMS,
            )
            if coordinate_sha256(coordinates) != self.source_coordinate_sha256:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generated coordinates changed")
            if (
                self.placement_receipt.slot_index != self.slot_index
                or self.placement_receipt.allocation.receipt_sha256
                != self.allocation.receipt_sha256
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "placement receipt slot changed")
            proposal = self.proposal_execution_receipt
            if (
                proposal.slot_index != self.slot_index
                or proposal.allocation_slot_receipt_sha256 != slot.receipt_sha256
                or proposal.allocation_source_receipt_sha256s
                != slot.selected_source_receipt_sha256s
                or proposal.source_proposal_sha256 != self.source_proposal_sha256
                or proposal.source_coordinate_sha256 != self.source_coordinate_sha256
                or proposal.generation_parent_proposal_sha256
                != slot.selected_generation_parent_proposal_sha256
                or proposal.generation_parent_coordinate_sha256
                != slot.selected_generation_parent_coordinate_sha256
                or proposal.generator_config_sha256 != MIXED64_PRODUCER_POLICY_SHA256
                or proposal.generator_component_id != MIXED64_PRODUCER_COMPONENT_ID
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "proposal execution receipt changed")
            object.__setattr__(self, "output_coordinates", coordinates)
        elif self.status == GENERATION_STATUS_FAILURE:
            if any(
                value is not None
                for value in (
                    self.source_proposal_sha256,
                    self.source_coordinate_sha256,
                    self.output_coordinates,
                    self.placement_receipt,
                    self.proposal_execution_receipt,
                )
            ) or self.failure_receipt is None:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "failure record fabricated output")
            if self.failure_receipt.slot_index != self.slot_index:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "failure receipt slot changed")
            if (
                self.failure_receipt.source_bundle_receipt_sha256
                != self.source_bundle_receipt_sha256
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "failure source bundle changed")
        else:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation record status is invalid")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def generated(self) -> bool:
        return self.status == GENERATION_STATUS_SUCCESS

    def _projection(self) -> dict[str, object]:
        slot = self.allocation.slots[self.slot_index]
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PRODUCER_COMPONENT_ID,
            "source_bundle_receipt_sha256": self.source_bundle_receipt_sha256,
            "allocation_slot_receipt_sha256": slot.receipt_sha256,
            "slot_index": self.slot_index,
            "lane": slot.lane,
            "status": self.status,
            "source_proposal_sha256": self.source_proposal_sha256,
            "source_coordinate_sha256": self.source_coordinate_sha256,
            "output_coordinates_binary64_hex": (
                None
                if self.output_coordinates is None
                else _projection_coordinates(self.output_coordinates)
            ),
            "placement_receipt": (
                None if self.placement_receipt is None else self.placement_receipt.to_dict()
            ),
            "proposal_execution_receipt": (
                None
                if self.proposal_execution_receipt is None
                else self.proposal_execution_receipt.to_dict()
            ),
            "failure_receipt": (
                None if self.failure_receipt is None else self.failure_receipt.to_dict()
            ),
            "slot_preserved_in_denominator": True,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "generation record changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class Mixed64ProposalProducerBatchV1:
    allocation: FixedMixed64Allocation = field(repr=False)
    source_bundle: Mixed64ProposalSourceBundleV1 = field(repr=False)
    records: tuple[Mixed64ProposalGenerationRecordV1, ...]
    producer_implementation_source_sha256: str
    geometry_implementation_source_sha256: str
    _factory_seal: InitVar[object | None] = None
    profile_id: str = MIXED64_PRODUCER_PROFILE_ID
    schema_id: str = MIXED64_PRODUCER_BATCH_SCHEMA_ID
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self, _factory_seal: object | None) -> None:
        if _factory_seal is not _BATCH_FACTORY_SEAL:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer batch requires factory")
        if self.schema_id != MIXED64_PRODUCER_BATCH_SCHEMA_ID or self.profile_id != MIXED64_PRODUCER_PROFILE_ID:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer batch identity changed")
        if type(self.allocation) is not FixedMixed64Allocation or type(self.source_bundle) is not Mixed64ProposalSourceBundleV1:
            raise TypeError("producer batch inputs must be exact")
        if self.source_bundle.allocation.receipt_sha256 != self.allocation.receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "source bundle allocation changed")
        if type(self.records) is not tuple or len(self.records) != FIXED_MIXED64_CANDIDATE_COUNT:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer denominator is not fixed64")
        if any(type(record) is not Mixed64ProposalGenerationRecordV1 for record in self.records):
            raise TypeError("producer records must be exact")
        if tuple(record.slot_index for record in self.records) != tuple(range(64)):
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer slot order changed")
        for name in (
            "producer_implementation_source_sha256",
            "geometry_implementation_source_sha256",
        ):
            _digest(getattr(self, name), name=name)
        allocation_receipt_sha256 = self.allocation.receipt_sha256
        source_bundle_receipt_sha256 = self.source_bundle.receipt_sha256
        for record in self.records:
            if (
                record.allocation.receipt_sha256 != allocation_receipt_sha256
                or record.source_bundle_receipt_sha256
                != source_bundle_receipt_sha256
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer record source changed")
            if (
                record.generated
                and record.proposal_execution_receipt is not None
                and record.proposal_execution_receipt.generator_implementation_source_sha256
                != self.producer_implementation_source_sha256
            ):
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer source binding changed")
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def generated_count(self) -> int:
        return sum(record.generated for record in self.records)

    @property
    def typed_failure_count(self) -> int:
        return len(self.records) - self.generated_count

    @property
    def candidate_coordinates(self) -> tuple[Coordinates | None, ...]:
        return tuple(record.output_coordinates for record in self.records)

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": self.schema_id,
            "component_id": MIXED64_PRODUCER_COMPONENT_ID,
            "profile_id": self.profile_id,
            "producer_policy": frozen_mixed64_producer_policy(),
            "producer_policy_sha256": MIXED64_PRODUCER_POLICY_SHA256,
            "geometry_policy_sha256": MIXED64_PROPOSAL_GEOMETRY_POLICY_SHA256,
            "producer_implementation_source_sha256": self.producer_implementation_source_sha256,
            "geometry_implementation_source_sha256": self.geometry_implementation_source_sha256,
            "allocation": self.allocation.to_dict(),
            "source_bundle": self.source_bundle.to_dict(),
            "candidate_denominator": len(self.records),
            "generated_count": self.generated_count,
            "typed_failure_count": self.typed_failure_count,
            "generation_record_receipt_sha256s": [record.receipt_sha256 for record in self.records],
            "records": [record.to_dict() for record in self.records],
            "denominator_failure_complete": True,
            "generation_scope_source_payloads_rederived": True,
            "generation_scope_orientation_receipts_complete": True,
            "generation_scope_single_anchor_receipts_complete": True,
            "generation_scope_failure_receipts_complete": True,
            "producer_attested": False,
            "activation_evidence_eligible": False,
            "post_refinement_admission_complete": False,
            "scorer_v1_reexecuted": False,
            "pose_validity_reexecuted": False,
            "result_fields_consumed": False,
            "reservation_allowed": False,
            "molecular_execution_authorized": False,
            "historical_or_fresh_execution_authorized": False,
            "product_or_stage0_authority": False,
            "public_or_scientific_claim_authorized": False,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            _fail(SOURCE_PAYLOAD_CROSS_WIRING, "producer batch changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


def _stable_source_sha256(path: Path) -> str:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_PRODUCER_SOURCE_BYTES:
            _fail(PRODUCER_SOURCE_CHANGED, f"source {path.name} is not bounded regular data")
        payload = path.read_bytes()
        after = path.lstat()
    except OSError as exc:
        raise Mixed64ProposalProducerError(
            PRODUCER_SOURCE_CHANGED,
            f"source {path.name} is unavailable",
        ) from exc
    if (
        len(payload) != before.st_size
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        _fail(PRODUCER_SOURCE_CHANGED, f"source {path.name} changed during read")
    return hashlib.sha256(payload).hexdigest()


def _source_for_slot(
    bundle: Mixed64ProposalSourceBundleV1,
    *,
    slot_index: int,
) -> tuple[Mixed64CoordinateSourcePayloadV1 | None, str]:
    slot = bundle.allocation.slots[slot_index]
    if slot.lane in {LANE_POCKET_CENTERED_CONTROLS, LANE_UNIFORM_SOURCE_CONTROLS}:
        assert slot.v7_control_source_index is not None
        return bundle.v7_control_for_index(slot.v7_control_source_index), MISSING_V7_CONTROL_SOURCE_PAYLOAD
    if slot.lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3:
        assert slot.true_conformer_rank is not None
        return bundle.conformer_for_rank(slot.true_conformer_rank), MISSING_CONFORMER_SOURCE_PAYLOAD
    if slot.lane == LANE_PAIRED_RETAINED_CONTROLS:
        assert slot.retained_source_index is not None
        return bundle.retained_for_index(slot.retained_source_index), MISSING_RETAINED_SOURCE_PAYLOAD
    return bundle.exact_v11_source, MISSING_EXACT_V11_SOURCE_PAYLOAD


def _generated_proposal_sha256(
    *,
    allocation: FixedMixed64Allocation,
    slot_index: int,
    source_payload: Mixed64CoordinateSourcePayloadV1,
    placement_receipt_sha256: str,
    output_coordinate_sha256: str,
) -> str:
    return _sha256(
        {
            "schema_id": MIXED64_GENERATED_PROPOSAL_ID_SCHEMA_ID,
            "producer_policy_sha256": MIXED64_PRODUCER_POLICY_SHA256,
            "allocation_receipt_sha256": allocation.receipt_sha256,
            "allocation_slot_receipt_sha256": allocation.slots[slot_index].receipt_sha256,
            "slot_index": slot_index,
            "generation_input_source_payload_receipt_sha256": source_payload.receipt_sha256,
            "placement_receipt_sha256": placement_receipt_sha256,
            "output_coordinate_sha256": output_coordinate_sha256,
        }
    )


def _failure_record(
    allocation: FixedMixed64Allocation,
    *,
    source_bundle_receipt_sha256: str,
    slot_index: int,
    failure_code: str,
    attempted_source: Mixed64CoordinateSourcePayloadV1 | None = None,
    geometry_error_message: str | None = None,
) -> Mixed64ProposalGenerationRecordV1:
    failure = ProposalGenerationFailureReceiptV1(
        allocation=allocation,
        source_bundle_receipt_sha256=source_bundle_receipt_sha256,
        slot_index=slot_index,
        failure_code=failure_code,
        allocation_missing_feature_codes=allocation.slots[slot_index].missing_feature_codes,
        attempted_source_payload_receipt_sha256=(
            None if attempted_source is None else attempted_source.receipt_sha256
        ),
        geometry_error_message=geometry_error_message,
    )
    return Mixed64ProposalGenerationRecordV1(
        allocation=allocation,
        source_bundle_receipt_sha256=source_bundle_receipt_sha256,
        slot_index=slot_index,
        status=GENERATION_STATUS_FAILURE,
        source_proposal_sha256=None,
        source_coordinate_sha256=None,
        output_coordinates=None,
        placement_receipt=None,
        proposal_execution_receipt=None,
        failure_receipt=failure,
        _factory_seal=_RECORD_FACTORY_SEAL,
    )


def _success_record(
    allocation: FixedMixed64Allocation,
    *,
    source_bundle_receipt_sha256: str,
    slot_index: int,
    source_payload: Mixed64CoordinateSourcePayloadV1,
    placement: PlacementReceipt,
    producer_source_sha256: str,
) -> Mixed64ProposalGenerationRecordV1:
    from .pipeline_candidate_evidence_v2 import bind_proposal_execution_receipt_v2

    slot = allocation.slots[slot_index]
    output_coordinates = placement.output_coordinates
    output_coordinate_sha256 = coordinate_sha256(output_coordinates)
    if isinstance(placement, ExactPassthroughPlacementReceiptV1):
        output_proposal_sha256 = source_payload.proposal_sha256
    else:
        output_proposal_sha256 = _generated_proposal_sha256(
            allocation=allocation,
            slot_index=slot_index,
            source_payload=source_payload,
            placement_receipt_sha256=placement.receipt_sha256,
            output_coordinate_sha256=output_coordinate_sha256,
        )
    proposal_receipt = bind_proposal_execution_receipt_v2(
        slot_index=slot_index,
        allocation_slot_receipt_sha256=slot.receipt_sha256,
        allocation_source_receipt_sha256s=slot.selected_source_receipt_sha256s,
        generation_parent_proposal_sha256=slot.selected_generation_parent_proposal_sha256,
        generation_parent_coordinate_sha256=slot.selected_generation_parent_coordinate_sha256,
        source_proposal_sha256=output_proposal_sha256,
        source_coordinate_sha256=output_coordinate_sha256,
        generation_input_receipt_sha256=source_payload.source_receipt_sha256,
        generator_config_sha256=MIXED64_PRODUCER_POLICY_SHA256,
        generator_implementation_source_sha256=producer_source_sha256,
        generator_component_id=MIXED64_PRODUCER_COMPONENT_ID,
    )
    return Mixed64ProposalGenerationRecordV1(
        allocation=allocation,
        source_bundle_receipt_sha256=source_bundle_receipt_sha256,
        slot_index=slot_index,
        status=GENERATION_STATUS_SUCCESS,
        source_proposal_sha256=output_proposal_sha256,
        source_coordinate_sha256=output_coordinate_sha256,
        output_coordinates=output_coordinates,
        placement_receipt=placement,
        proposal_execution_receipt=proposal_receipt,
        failure_receipt=None,
        _factory_seal=_RECORD_FACTORY_SEAL,
    )


def produce_fixed_mixed64_proposals(
    allocation: FixedMixed64Allocation,
    *,
    source_bundle: Mixed64ProposalSourceBundleV1,
) -> Mixed64ProposalProducerBatchV1:
    """Generate exactly 64 success/failure records without consuming results."""

    if type(allocation) is not FixedMixed64Allocation:
        raise TypeError("allocation must be the exact FixedMixed64Allocation type")
    if type(source_bundle) is not Mixed64ProposalSourceBundleV1:
        raise TypeError("source_bundle must be exact")
    if source_bundle.allocation.receipt_sha256 != allocation.receipt_sha256:
        _fail(SOURCE_PAYLOAD_CROSS_WIRING, "source bundle belongs to another allocation")
    producer_path = Path(__file__)
    geometry_path = Path(__file__).with_name("mixed64_proposal_geometry_v3.py")
    producer_source_sha256 = _stable_source_sha256(producer_path)
    geometry_source_sha256 = _stable_source_sha256(geometry_path)
    source_bundle_receipt_sha256 = source_bundle.receipt_sha256
    records: list[Mixed64ProposalGenerationRecordV1] = []
    for slot in allocation.slots:
        if not slot.generation_eligible:
            records.append(
                _failure_record(
                    allocation,
                    source_bundle_receipt_sha256=source_bundle_receipt_sha256,
                    slot_index=slot.slot_index,
                    failure_code=ALLOCATION_MISSING_FEATURE_FAILURE,
                )
            )
            continue
        source, missing_source_code = _source_for_slot(
            source_bundle,
            slot_index=slot.slot_index,
        )
        if source is None:
            records.append(
                _failure_record(
                    allocation,
                    source_bundle_receipt_sha256=source_bundle_receipt_sha256,
                    slot_index=slot.slot_index,
                    failure_code=missing_source_code,
                )
            )
            continue
        try:
            if slot.lane in _PASSTHROUGH_LANES:
                placement: PlacementReceipt = ExactPassthroughPlacementReceiptV1(
                    allocation=allocation,
                    source_bundle_receipt_sha256=source_bundle_receipt_sha256,
                    slot_index=slot.slot_index,
                    source_payload=source,
                )
            elif slot.lane in _SO3_LANES:
                orientation_source_receipt_sha256 = (
                    slot.selected_source_receipt_sha256s[0]
                    if slot.lane == LANE_TRUE_CONFORMER_INDEPENDENT_SO3
                    else source.source_receipt_sha256
                )
                placement = generate_indexed_so3_placement(
                    allocation,
                    slot_index=slot.slot_index,
                    source_proposal_sha256=source.proposal_sha256,
                    source_coordinate_sha256=source.coordinate_sha256,
                    source_receipt_sha256=orientation_source_receipt_sha256,
                    source_coordinates=source.coordinates,
                    pocket_center=source_bundle.pocket_center,
                    pocket_normal=source_bundle.pocket_normal,
                )
            elif slot.lane in _ANCHOR_LANES:
                placement = generate_single_anchor_placement(
                    allocation,
                    slot_index=slot.slot_index,
                    source_proposal_sha256=source.proposal_sha256,
                    source_coordinate_sha256=source.coordinate_sha256,
                    source_receipt_sha256=source.source_receipt_sha256,
                    ligand_coordinates=source.coordinates,
                    ligand_vdw_radii=source_bundle.ligand_vdw_radii,
                    ligand_heavy_atom_mask=source_bundle.ligand_heavy_atom_mask,
                    receptor_coordinate_sha256=source_bundle.receptor_coordinate_sha256,
                    receptor_coordinates=source_bundle.receptor_coordinates,
                    receptor_vdw_radii=source_bundle.receptor_vdw_radii,
                    pocket_center=source_bundle.pocket_center,
                    pocket_radius=source_bundle.pocket_radius,
                )
            else:
                _fail(SOURCE_PAYLOAD_CROSS_WIRING, f"unimplemented lane {slot.lane}")
        except Mixed64ProposalGeometryError as exc:
            records.append(
                _failure_record(
                    allocation,
                    source_bundle_receipt_sha256=source_bundle_receipt_sha256,
                    slot_index=slot.slot_index,
                    failure_code=exc.code,
                    attempted_source=source,
                    geometry_error_message=str(exc),
                )
            )
            continue
        records.append(
            _success_record(
                allocation,
                source_bundle_receipt_sha256=source_bundle_receipt_sha256,
                slot_index=slot.slot_index,
                source_payload=source,
                placement=placement,
                producer_source_sha256=producer_source_sha256,
            )
        )
    if (
        _stable_source_sha256(producer_path) != producer_source_sha256
        or _stable_source_sha256(geometry_path) != geometry_source_sha256
    ):
        _fail(PRODUCER_SOURCE_CHANGED, "producer or geometry source drifted")
    return Mixed64ProposalProducerBatchV1(
        allocation=allocation,
        source_bundle=source_bundle,
        records=tuple(records),
        producer_implementation_source_sha256=producer_source_sha256,
        geometry_implementation_source_sha256=geometry_source_sha256,
        _factory_seal=_BATCH_FACTORY_SEAL,
    )


__all__ = [
    "ALLOCATION_MISSING_FEATURE_FAILURE",
    "ExactPassthroughPlacementReceiptV1",
    "GENERATION_STATUS_FAILURE",
    "GENERATION_STATUS_SUCCESS",
    "LIGAND_ATOM_DENOMINATOR_MISMATCH",
    "MISSING_CONFORMER_SOURCE_PAYLOAD",
    "MISSING_EXACT_V11_SOURCE_PAYLOAD",
    "MISSING_RETAINED_SOURCE_PAYLOAD",
    "MISSING_V7_CONTROL_SOURCE_PAYLOAD",
    "MIXED64_PRODUCER_COMPONENT_ID",
    "MIXED64_PRODUCER_POLICY_SHA256",
    "MIXED64_PRODUCER_PROFILE_ID",
    "Mixed64CoordinateSourcePayloadV1",
    "Mixed64ProposalGenerationRecordV1",
    "Mixed64ProposalProducerBatchV1",
    "Mixed64ProposalProducerError",
    "Mixed64ProposalSourceBundleV1",
    "PRODUCER_SOURCE_CHANGED",
    "ProposalGenerationFailureReceiptV1",
    "SOURCE_KIND_EXACT_V11_BASE",
    "SOURCE_KIND_RETAINED_CONTROL",
    "SOURCE_KIND_TRUE_CONFORMER",
    "SOURCE_KIND_V7_CONTROL",
    "SOURCE_PAYLOAD_CROSS_WIRING",
    "SOURCE_PAYLOAD_NONCANONICAL",
    "SOURCE_PAYLOAD_RECEIPT_INVALID",
    "frozen_mixed64_producer_policy",
    "produce_fixed_mixed64_proposals",
]
