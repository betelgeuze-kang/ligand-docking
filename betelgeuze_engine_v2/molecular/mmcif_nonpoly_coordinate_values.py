"""Bounded finite-binary64 interpretation of selected nonpoly coordinates.

This contract composes the accepted nonpoly ``_atom_site`` observation carrier.
For every selected atom it binds each original ``Cartn_x/y/z`` token spelling to
the finite Python/IEEE-754 binary64 value and its exact 64-bit pattern.  It does
not interpret coordinate units, geometry quality, distances, chemistry, or
topology and it does not create a prepared molecular system.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile
from typing import Any, Mapping

from .mmcif_nonpoly_atom_site_observations import (
    MmcifNonpolyAtomSiteObservation,
    parse_mmcif_nonpoly_atom_site_observations,
)
from .mmcif_semantics import MmcifSemanticValue


MMCIF_NONPOLY_COORDINATE_VALUE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_coordinate_value_projection/1.0.0"
)
MMCIF_NONPOLY_COORDINATE_VALUE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_coordinate_value_source_binding/1.0.0"
)
MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_coordinate_value_document/1.0.0"
)
MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID = (
    "bounded_mmcif_nonpoly_finite_binary64_coordinate_values/1.0.0"
)
MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION = "1.0.0"

MMCIF_NONPOLY_COORDINATE_HEADERS = (
    "_atom_site.cartn_x",
    "_atom_site.cartn_y",
    "_atom_site.cartn_z",
)

_DECIMAL_BINARY64_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]+)?$"
)
_BINARY64_BITS_RE = re.compile(r"^[0-9a-f]{16}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyCoordinateValueError(ValueError):
    """Stable fail-closed error that never echoes a source coordinate token."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_coordinate_value:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifBinary64CoordinateValue:
    field_name: str
    raw_value: str
    raw_lexeme: str
    quoted: bool
    numeric_value: float
    binary64_bits_hex: str
    binary64_hex: str
    value_identity_sha256: str
    source_value_binding_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifBinary64CoordinateValue("
            f"field_name={self.field_name!r}, binary64_bits_hex={self.binary64_bits_hex!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "raw_token": {
                "state": "known",
                "value": self.raw_value,
                "lexeme": self.raw_lexeme,
                "quoted": self.quoted,
            },
            "numeric_value": self.numeric_value,
            "binary64_bits_hex": self.binary64_bits_hex,
            "binary64_hex": self.binary64_hex,
            "value_identity_sha256": self.value_identity_sha256,
            "source_value_binding_sha256": self.source_value_binding_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyCoordinateValueObservation:
    source_atom_id: int
    site_identity_sha256: str
    instance_identity_sha256: str
    component_atom_identity_sha256: str
    cartn_x: MmcifBinary64CoordinateValue
    cartn_y: MmcifBinary64CoordinateValue
    cartn_z: MmcifBinary64CoordinateValue
    coordinate_value_identity_sha256: str
    coordinate_source_binding_sha256: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyCoordinateValueObservation("
            f"source_atom_id={self.source_atom_id}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_atom_id": self.source_atom_id,
            "site_identity_sha256": self.site_identity_sha256,
            "instance_identity_sha256": self.instance_identity_sha256,
            "component_atom_identity_sha256": self.component_atom_identity_sha256,
            "cartn_x": self.cartn_x.to_dict(),
            "cartn_y": self.cartn_y.to_dict(),
            "cartn_z": self.cartn_z.to_dict(),
            "coordinate_value_identity_sha256": self.coordinate_value_identity_sha256,
            "coordinate_source_binding_sha256": self.coordinate_source_binding_sha256,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyCoordinateValueSnapshot:
    source_sha256: str
    observation_snapshot_sha256: str
    observation_projection_sha256: str
    observation_source_binding_sha256: str
    coordinates: tuple[MmcifNonpolyCoordinateValueObservation, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyCoordinateValueSnapshot("
            f"coordinate_count={len(self.coordinates)})"
        )

    @property
    def coordinate_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_coordinate_value_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_coordinate_value_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
                "coordinate_projection_sha256": self.coordinate_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "observation_snapshot_sha256": self.observation_snapshot_sha256,
            "coordinate_count": len(self.coordinates),
            "coordinate_scalar_count": 3 * len(self.coordinates),
            "coordinate_projection_sha256": self.coordinate_projection_sha256,
            "source_binding_sha256": self.source_binding_sha256,
            "snapshot_sha256": self.snapshot_sha256,
            **_claim_policy(),
        }


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_coordinate_tokens_preserved": True,
        "atom_site_identity_joined": True,
        "coordinate_values_interpreted": True,
        "coordinate_binary64_bits_bound": True,
        "coordinate_value_identity_bound": True,
        "coordinate_source_spelling_bound": True,
        "coordinate_finiteness_verified": True,
        "source_authenticated": False,
        "coordinate_observation_scientifically_assessed": False,
        "coordinate_units_interpreted": False,
        "coordinate_geometry_interpreted": False,
        "distance_or_clash_interpreted": False,
        "occupancy_values_interpreted": False,
        "b_factor_interpreted": False,
        "formal_charge_interpreted": False,
        "type_symbol_interpreted": False,
        "altloc_population_interpreted": False,
        "missingness_inferred": False,
        "connection_type_interpreted": False,
        "symmetry_interpreted": False,
        "bond_order_interpreted": False,
        "covalence_interpreted": False,
        "coordination_interpreted": False,
        "topology_interpreted": False,
        "chemistry_interpreted": False,
        "preparation_ready": False,
        "parameterability_assessed": False,
        "physics_supported": False,
        "runtime_eligible": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def _semantic_projection(value: MmcifSemanticValue) -> dict[str, Any]:
    return {"state": value.state, "value": value.value, "quoted": value.quoted}


def _bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def _raw_lexeme(text: str, value: MmcifSemanticValue, *, field_name: str) -> str:
    lines = text.splitlines()
    line_index = value.line_number - 1
    start = value.column_number - 1
    if line_index < 0 or line_index >= len(lines) or start < 0:
        raise MmcifNonpolyCoordinateValueError(
            "coordinate_source_location_invalid",
            f"{field_name} source location is outside the bounded input",
            line_number=value.line_number,
        )
    line = lines[line_index]
    if start >= len(line):
        raise MmcifNonpolyCoordinateValueError(
            "coordinate_source_location_invalid",
            f"{field_name} source location is outside the bounded input",
            line_number=value.line_number,
        )
    if value.quoted:
        quote = line[start]
        if quote not in {"'", '"'}:
            raise MmcifNonpolyCoordinateValueError(
                "coordinate_source_lexeme_mismatch",
                f"{field_name} quoted source spelling cannot be recovered",
                line_number=value.line_number,
            )
        end = line.find(quote, start + 1)
        while end >= 0 and end + 1 < len(line) and line[end + 1] not in " \t":
            end = line.find(quote, end + 1)
        if end < 0 or line[start + 1 : end] != value.value:
            raise MmcifNonpolyCoordinateValueError(
                "coordinate_source_lexeme_mismatch",
                f"{field_name} quoted source spelling cannot be recovered",
                line_number=value.line_number,
            )
        return line[start : end + 1]
    end = start
    while end < len(line) and line[end] not in " \t":
        end += 1
    lexeme = line[start:end]
    if lexeme != value.value:
        raise MmcifNonpolyCoordinateValueError(
            "coordinate_source_lexeme_mismatch",
            f"{field_name} bare source spelling cannot be recovered",
            line_number=value.line_number,
        )
    return lexeme


def _parse_binary64(
    value: MmcifSemanticValue,
    *,
    field_name: str,
    text: str,
) -> MmcifBinary64CoordinateValue:
    if value.state != "known":
        raise MmcifNonpolyCoordinateValueError(
            "coordinate_value_unavailable",
            f"{field_name} must be a known source value",
            line_number=value.line_number,
        )
    if _DECIMAL_BINARY64_RE.fullmatch(value.value) is None:
        raise MmcifNonpolyCoordinateValueError(
            "invalid_coordinate_decimal",
            f"{field_name} must use the bounded decimal coordinate grammar",
            line_number=value.line_number,
        )
    try:
        numeric = float(value.value)
    except ValueError as exc:
        raise MmcifNonpolyCoordinateValueError(
            "invalid_coordinate_decimal",
            f"{field_name} cannot be interpreted as binary64",
            line_number=value.line_number,
        ) from exc
    if not math.isfinite(numeric):
        raise MmcifNonpolyCoordinateValueError(
            "nonfinite_coordinate_value",
            f"{field_name} must round to a finite binary64 value",
            line_number=value.line_number,
        )
    bits = _bits(numeric)
    raw_projection = _semantic_projection(value)
    lexeme = _raw_lexeme(text, value, field_name=field_name)
    raw_projection["lexeme"] = lexeme
    return MmcifBinary64CoordinateValue(
        field_name=field_name,
        raw_value=value.value,
        raw_lexeme=lexeme,
        quoted=value.quoted,
        numeric_value=numeric,
        binary64_bits_hex=bits,
        binary64_hex=numeric.hex(),
        value_identity_sha256=_sha256({"binary64_bits_hex": bits}),
        source_value_binding_sha256=_sha256(
            {"raw_token": raw_projection, "binary64_bits_hex": bits}
        ),
    )


def _coordinate_observation(
    row: MmcifNonpolyAtomSiteObservation,
    *,
    text: str,
) -> MmcifNonpolyCoordinateValueObservation:
    cartn_x = _parse_binary64(
        row.cartn_x, field_name="_atom_site.cartn_x", text=text
    )
    cartn_y = _parse_binary64(
        row.cartn_y, field_name="_atom_site.cartn_y", text=text
    )
    cartn_z = _parse_binary64(
        row.cartn_z, field_name="_atom_site.cartn_z", text=text
    )
    value_identity = _sha256(
        {
            "site_identity_sha256": row.site_identity_sha256,
            "cartn_x_bits": cartn_x.binary64_bits_hex,
            "cartn_y_bits": cartn_y.binary64_bits_hex,
            "cartn_z_bits": cartn_z.binary64_bits_hex,
        }
    )
    source_binding = _sha256(
        {
            "coordinate_value_identity_sha256": value_identity,
            "cartn_x": cartn_x.to_dict(),
            "cartn_y": cartn_y.to_dict(),
            "cartn_z": cartn_z.to_dict(),
        }
    )
    return MmcifNonpolyCoordinateValueObservation(
        source_atom_id=row.source_atom_id,
        site_identity_sha256=row.site_identity_sha256,
        instance_identity_sha256=row.instance_identity_sha256,
        component_atom_identity_sha256=row.component_atom_identity_sha256,
        cartn_x=cartn_x,
        cartn_y=cartn_y,
        cartn_z=cartn_z,
        coordinate_value_identity_sha256=value_identity,
        coordinate_source_binding_sha256=source_binding,
        source_ordinal=row.source_ordinal,
    )


def parse_mmcif_nonpoly_coordinate_values(
    text: str,
) -> MmcifNonpolyCoordinateValueSnapshot:
    """Interpret selected nonpoly coordinates as finite binary64 values."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly coordinate value input must be a string")
    observation = parse_mmcif_nonpoly_atom_site_observations(text)
    coordinates = tuple(
        _coordinate_observation(row, text=text) for row in observation.observations
    )
    return MmcifNonpolyCoordinateValueSnapshot(
        source_sha256=observation.source_sha256,
        observation_snapshot_sha256=observation.snapshot_sha256,
        observation_projection_sha256=observation.observation_projection_sha256,
        observation_source_binding_sha256=observation.source_binding_sha256,
        coordinates=coordinates,
    )


def mmcif_nonpoly_coordinate_value_projection(
    snapshot: MmcifNonpolyCoordinateValueSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION,
        "observation_projection_sha256": snapshot.observation_projection_sha256,
        "coordinates": [row.to_dict() for row in snapshot.coordinates],
        "row_order": "selected_source_atom_site_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_coordinate_value_source_binding(
    snapshot: MmcifNonpolyCoordinateValueSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "observation_snapshot_sha256": snapshot.observation_snapshot_sha256,
        "observation_source_binding_sha256": snapshot.observation_source_binding_sha256,
        "coordinate_headers": list(MMCIF_NONPOLY_COORDINATE_HEADERS),
        "coordinate_source_binding_sha256": [
            row.coordinate_source_binding_sha256 for row in snapshot.coordinates
        ],
    }


def mmcif_nonpoly_coordinate_value_document(
    snapshot: MmcifNonpolyCoordinateValueSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_coordinate_value_projection(snapshot)
    binding = mmcif_nonpoly_coordinate_value_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION,
        "coordinate_projection": projection,
        "source_binding": binding,
        "coordinate_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"nonpoly coordinate value {label} digest invalid")
    return candidate


def _require_coordinate_scalar(payload: object, field_name: str) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly coordinate scalar must be a mapping")
    scalar = dict(payload)
    if scalar.get("field_name") != field_name:
        raise ValueError("nonpoly coordinate scalar field mismatch")
    raw = scalar.get("raw_token")
    if not isinstance(raw, Mapping):
        raise ValueError("nonpoly coordinate raw token must be a mapping")
    raw_token = dict(raw)
    raw_value = raw_token.get("value")
    raw_lexeme = raw_token.get("lexeme")
    if (
        raw_token.get("state") != "known"
        or type(raw_value) is not str
        or type(raw_lexeme) is not str
        or type(raw_token.get("quoted")) is not bool
        or _DECIMAL_BINARY64_RE.fullmatch(raw_value) is None
    ):
        raise ValueError("nonpoly coordinate raw token is outside the decimal grammar")
    if raw_token["quoted"]:
        if (
            len(raw_lexeme) < 2
            or raw_lexeme[0] not in {"'", '"'}
            or raw_lexeme[-1] != raw_lexeme[0]
            or raw_lexeme[1:-1] != raw_value
        ):
            raise ValueError("nonpoly coordinate quoted lexeme mismatch")
    elif raw_lexeme != raw_value:
        raise ValueError("nonpoly coordinate bare lexeme mismatch")
    parsed = float(raw_value)
    if not math.isfinite(parsed):
        raise ValueError("nonpoly coordinate raw token is not finite binary64")
    numeric = scalar.get("numeric_value")
    if type(numeric) not in (int, float) or not math.isfinite(float(numeric)):
        raise ValueError("nonpoly coordinate numeric value is invalid")
    expected_bits = _bits(parsed)
    if _bits(float(numeric)) != expected_bits:
        raise ValueError("nonpoly coordinate numeric value does not match raw token")
    if (
        _BINARY64_BITS_RE.fullmatch(str(scalar.get("binary64_bits_hex") or ""))
        is None
        or scalar.get("binary64_bits_hex") != expected_bits
    ):
        raise ValueError("nonpoly coordinate bit pattern mismatch")
    if scalar.get("binary64_hex") != parsed.hex():
        raise ValueError("nonpoly coordinate hexadecimal value mismatch")
    value_identity = _sha256({"binary64_bits_hex": expected_bits})
    if scalar.get("value_identity_sha256") != value_identity:
        raise ValueError("nonpoly coordinate value identity mismatch")
    source_binding = _sha256(
        {"raw_token": raw_token, "binary64_bits_hex": expected_bits}
    )
    if scalar.get("source_value_binding_sha256") != source_binding:
        raise ValueError("nonpoly coordinate source value binding mismatch")
    return expected_bits, scalar


def _require_coordinate_row(payload: object) -> tuple[int, str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly coordinate observation must be a mapping")
    row = dict(payload)
    source_atom_id = row.get("source_atom_id")
    source_ordinal = row.get("source_ordinal")
    if type(source_atom_id) is not int or source_atom_id <= 0:
        raise ValueError("nonpoly coordinate source atom id invalid")
    if type(source_ordinal) is not int or source_ordinal < 0:
        raise ValueError("nonpoly coordinate source ordinal invalid")
    site_identity = _require_digest(row.get("site_identity_sha256"), "site identity")
    _require_digest(row.get("instance_identity_sha256"), "instance identity")
    _require_digest(row.get("component_atom_identity_sha256"), "component atom identity")
    x_bits, x = _require_coordinate_scalar(row.get("cartn_x"), "_atom_site.cartn_x")
    y_bits, y = _require_coordinate_scalar(row.get("cartn_y"), "_atom_site.cartn_y")
    z_bits, z = _require_coordinate_scalar(row.get("cartn_z"), "_atom_site.cartn_z")
    value_identity = _sha256(
        {
            "site_identity_sha256": site_identity,
            "cartn_x_bits": x_bits,
            "cartn_y_bits": y_bits,
            "cartn_z_bits": z_bits,
        }
    )
    if row.get("coordinate_value_identity_sha256") != value_identity:
        raise ValueError("nonpoly coordinate observation value identity mismatch")
    source_binding = _sha256(
        {
            "coordinate_value_identity_sha256": value_identity,
            "cartn_x": x,
            "cartn_y": y,
            "cartn_z": z,
        }
    )
    if row.get("coordinate_source_binding_sha256") != source_binding:
        raise ValueError("nonpoly coordinate observation source binding mismatch")
    return source_atom_id, site_identity, source_binding


def require_mmcif_nonpoly_coordinate_value_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly coordinate value document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly coordinate value document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID:
        raise ValueError("nonpoly coordinate value profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION:
        raise ValueError("nonpoly coordinate value parser version mismatch")
    projection = document.get("coordinate_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly coordinate value sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_COORDINATE_VALUE_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly coordinate value projection schema mismatch")
    if binding.get("schema_id") != MMCIF_NONPOLY_COORDINATE_VALUE_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("nonpoly coordinate value source binding schema mismatch")

    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("coordinate_projection_sha256") != projection_digest:
        raise ValueError("nonpoly coordinate value projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly coordinate value source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID,
            "coordinate_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly coordinate value snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly coordinate value claim policy mismatch")

    coordinates = projection.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("nonpoly coordinate observations must be a non-empty list")
    if document.get("coordinate_count") != len(coordinates):
        raise ValueError("nonpoly coordinate observation count mismatch")
    if document.get("coordinate_scalar_count") != 3 * len(coordinates):
        raise ValueError("nonpoly coordinate scalar count mismatch")
    source_ids: set[int] = set()
    site_ids: set[str] = set()
    source_bindings: list[str] = []
    for row in coordinates:
        source_id, site_id, source_binding = _require_coordinate_row(row)
        if source_id in source_ids or site_id in site_ids:
            raise ValueError("nonpoly coordinate observations must be unique")
        source_ids.add(source_id)
        site_ids.add(site_id)
        source_bindings.append(source_binding)

    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly coordinate value source digest mismatch")
    observation_snapshot = _require_digest(
        binding.get("observation_snapshot_sha256"), "observation snapshot"
    )
    if document.get("observation_snapshot_sha256") != observation_snapshot:
        raise ValueError("nonpoly coordinate observation snapshot mismatch")
    _require_digest(
        projection.get("observation_projection_sha256"), "observation projection"
    )
    _require_digest(
        binding.get("observation_source_binding_sha256"),
        "observation source binding",
    )
    if binding.get("coordinate_headers") != list(MMCIF_NONPOLY_COORDINATE_HEADERS):
        raise ValueError("nonpoly coordinate source header binding mismatch")
    if binding.get("coordinate_source_binding_sha256") != source_bindings:
        raise ValueError("nonpoly coordinate source binding sequence mismatch")
    return payload


def mmcif_nonpoly_coordinate_value_json_bytes(
    snapshot: MmcifNonpolyCoordinateValueSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_coordinate_value_document(snapshot))


def write_mmcif_nonpoly_coordinate_value_json(
    path: str | Path,
    snapshot: MmcifNonpolyCoordinateValueSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_coordinate_value_json_bytes(snapshot) + b"\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        file_fd = -1
        os.replace(temporary_path, destination)
        directory_fd = os.open(
            destination.parent,
            os.O_RDONLY
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if file_fd >= 0:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


__all__ = [
    "MMCIF_NONPOLY_COORDINATE_HEADERS",
    "MMCIF_NONPOLY_COORDINATE_VALUE_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_COORDINATE_VALUE_PARSER_VERSION",
    "MMCIF_NONPOLY_COORDINATE_VALUE_PROFILE_ID",
    "MMCIF_NONPOLY_COORDINATE_VALUE_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_COORDINATE_VALUE_SOURCE_BINDING_SCHEMA_ID",
    "MmcifBinary64CoordinateValue",
    "MmcifNonpolyCoordinateValueError",
    "MmcifNonpolyCoordinateValueObservation",
    "MmcifNonpolyCoordinateValueSnapshot",
    "mmcif_nonpoly_coordinate_value_document",
    "mmcif_nonpoly_coordinate_value_json_bytes",
    "mmcif_nonpoly_coordinate_value_projection",
    "mmcif_nonpoly_coordinate_value_source_binding",
    "parse_mmcif_nonpoly_coordinate_values",
    "require_mmcif_nonpoly_coordinate_value_document",
    "write_mmcif_nonpoly_coordinate_value_json",
]
