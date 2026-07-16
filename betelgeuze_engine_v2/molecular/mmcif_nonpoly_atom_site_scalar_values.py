"""Bounded numeric semantics for selected nonpoly atom-site scalar fields.

The contract composes the accepted observation and finite-coordinate carriers.
It preserves known/unknown/not-applicable marker state and interprets known
``occupancy`` and ``B_iso_or_equiv`` values as finite binary64 numbers and
known ``pdbx_formal_charge`` values as dictionary-bounded integers. Missing
values are never replaced by dictionary defaults.

This is source-value interpretation only. Occupancy populations, displacement
quality, charge chemistry, topology, preparation, and scientific validity are
outside the profile.
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
from types import MappingProxyType
from typing import Any, Mapping

from .mmcif_nonpoly_atom_site_observations import (
    MmcifNonpolyAtomSiteObservation,
    parse_mmcif_nonpoly_atom_site_observations,
)
from .mmcif_nonpoly_coordinate_values import parse_mmcif_nonpoly_coordinate_values
from .mmcif_semantics import MmcifSemanticValue


MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROJECTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_scalar_value_projection/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_scalar_value_source_binding/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID = (
    "betelgeuze.engine_v2_mmcif_nonpoly_atom_site_scalar_value_document/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID = (
    "bounded_mmcif_nonpoly_atom_site_scalar_values/1.0.0"
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION = "1.0.0"

MMCIF_NONPOLY_ATOM_SITE_SCALAR_HEADERS = (
    "_atom_site.occupancy",
    "_atom_site.b_iso_or_equiv",
    "_atom_site.pdbx_formal_charge",
)
MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS: Mapping[str, str] = MappingProxyType({
    "_atom_site.occupancy": (
        "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
        "_atom_site.occupancy.html"
    ),
    "_atom_site.b_iso_or_equiv": (
        "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
        "_atom_site.B_iso_or_equiv.html"
    ),
    "_atom_site.pdbx_formal_charge": (
        "https://mmcif.wwpdb.org/dictionaries/mmcif_pdbx_v50.dic/Items/"
        "_atom_site.pdbx_formal_charge.html"
    ),
})
MMCIF_FORMAL_CHARGE_MINIMUM = -8
MMCIF_FORMAL_CHARGE_MAXIMUM = 8

_MMCIF_FLOAT_RE = re.compile(
    r"^(?P<mantissa>-?(?:[0-9]+(?:\.)?|[0-9]*\.[0-9]+))"
    r"(?:\((?P<uncertainty>[0-9]+)\))?"
    r"(?P<exponent>[eE][+-]?[0-9]+)?$"
)
_MMCIF_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_BINARY64_BITS_RE = re.compile(r"^[0-9a-f]{16}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MmcifNonpolyAtomSiteScalarValueError(ValueError):
    """Stable fail-closed error that never echoes a private scalar token."""

    def __init__(self, code: str, detail: str, *, line_number: int | None = None):
        self.code = str(code)
        self.detail = str(detail)
        self.line_number = None if line_number is None else int(line_number)
        suffix = "" if self.line_number is None else f" at line {self.line_number}"
        super().__init__(
            f"mmcif_nonpoly_atom_site_scalar_value:{self.code}{suffix}: {self.detail}"
        )


@dataclass(frozen=True, slots=True, repr=False)
class MmcifAtomSiteFloatScalarValue:
    field_name: str
    state: str
    raw_value: str
    raw_lexeme: str
    quoted: bool
    numeric_value: float | None
    binary64_bits_hex: str | None
    binary64_hex: str | None
    standard_uncertainty_digits: str | None
    value_identity_sha256: str
    source_value_binding_sha256: str

    def __repr__(self) -> str:
        return (
            "MmcifAtomSiteFloatScalarValue("
            f"field_name={self.field_name!r}, state={self.state!r})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "state": self.state,
            "raw_token": {
                "value": self.raw_value,
                "lexeme": self.raw_lexeme,
                "quoted": self.quoted,
            },
            "numeric_kind": "finite_binary64" if self.state == "known" else "unavailable",
            "numeric_value": self.numeric_value,
            "binary64_bits_hex": self.binary64_bits_hex,
            "binary64_hex": self.binary64_hex,
            "standard_uncertainty_digits": self.standard_uncertainty_digits,
            "value_identity_sha256": self.value_identity_sha256,
            "source_value_binding_sha256": self.source_value_binding_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifAtomSiteFormalChargeValue:
    field_name: str
    state: str
    raw_value: str
    raw_lexeme: str
    quoted: bool
    integer_value: int | None
    value_identity_sha256: str
    source_value_binding_sha256: str

    def __repr__(self) -> str:
        return f"MmcifAtomSiteFormalChargeValue(state={self.state!r})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "state": self.state,
            "raw_token": {
                "value": self.raw_value,
                "lexeme": self.raw_lexeme,
                "quoted": self.quoted,
            },
            "numeric_kind": "bounded_integer" if self.state == "known" else "unavailable",
            "integer_value": self.integer_value,
            "minimum": MMCIF_FORMAL_CHARGE_MINIMUM,
            "maximum": MMCIF_FORMAL_CHARGE_MAXIMUM,
            "value_identity_sha256": self.value_identity_sha256,
            "source_value_binding_sha256": self.source_value_binding_sha256,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomSiteScalarObservation:
    source_atom_id: int
    site_identity_sha256: str
    coordinate_value_identity_sha256: str
    occupancy: MmcifAtomSiteFloatScalarValue
    b_iso_or_equiv: MmcifAtomSiteFloatScalarValue
    formal_charge: MmcifAtomSiteFormalChargeValue
    scalar_value_identity_sha256: str
    scalar_source_binding_sha256: str
    source_ordinal: int

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomSiteScalarObservation("
            f"source_atom_id={self.source_atom_id}, source_ordinal={self.source_ordinal})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_atom_id": self.source_atom_id,
            "site_identity_sha256": self.site_identity_sha256,
            "coordinate_value_identity_sha256": self.coordinate_value_identity_sha256,
            "occupancy": self.occupancy.to_dict(),
            "b_iso_or_equiv": self.b_iso_or_equiv.to_dict(),
            "formal_charge": self.formal_charge.to_dict(),
            "scalar_value_identity_sha256": self.scalar_value_identity_sha256,
            "scalar_source_binding_sha256": self.scalar_source_binding_sha256,
            "source_ordinal": self.source_ordinal,
        }


@dataclass(frozen=True, slots=True, repr=False)
class MmcifNonpolyAtomSiteScalarValueSnapshot:
    source_sha256: str
    observation_snapshot_sha256: str
    coordinate_snapshot_sha256: str
    coordinate_projection_sha256: str
    coordinate_source_binding_sha256: str
    scalar_observations: tuple[MmcifNonpolyAtomSiteScalarObservation, ...]

    def __repr__(self) -> str:
        return (
            "MmcifNonpolyAtomSiteScalarValueSnapshot("
            f"scalar_observation_count={len(self.scalar_observations)})"
        )

    @property
    def scalar_projection_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_atom_site_scalar_value_projection(self))

    @property
    def source_binding_sha256(self) -> str:
        return _sha256(mmcif_nonpoly_atom_site_scalar_value_source_binding(self))

    @property
    def snapshot_sha256(self) -> str:
        return _sha256(
            {
                "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
                "scalar_projection_sha256": self.scalar_projection_sha256,
                "source_binding_sha256": self.source_binding_sha256,
                "claim_policy": _claim_policy(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        state_counts = {
            field: {
                state: sum(
                    1
                    for row in self.scalar_observations
                    if getattr(row, field).state == state
                )
                for state in ("known", "unknown", "not_applicable")
            }
            for field in ("occupancy", "b_iso_or_equiv", "formal_charge")
        }
        return {
            "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
            "profile_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
            "parser_version": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION,
            "source_sha256": self.source_sha256,
            "observation_snapshot_sha256": self.observation_snapshot_sha256,
            "coordinate_snapshot_sha256": self.coordinate_snapshot_sha256,
            "scalar_observation_count": len(self.scalar_observations),
            "scalar_value_count": 3 * len(self.scalar_observations),
            "state_counts": state_counts,
            "scalar_projection_sha256": self.scalar_projection_sha256,
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


def _bits(value: float) -> str:
    return struct.pack(">d", value).hex()


def _claim_policy() -> dict[str, bool]:
    return {
        "source_atom_site_scalar_tokens_preserved": True,
        "atom_site_identity_joined": True,
        "coordinate_values_interpreted": True,
        "occupancy_marker_state_interpreted": True,
        "occupancy_values_interpreted": True,
        "occupancy_unit_interval_verified": True,
        "b_factor_marker_state_interpreted": True,
        "b_factor_interpreted": True,
        "formal_charge_marker_state_interpreted": True,
        "formal_charge_interpreted": True,
        "formal_charge_dictionary_range_verified": True,
        "source_authenticated": False,
        "occupancy_default_inferred": False,
        "occupancy_population_interpreted": False,
        "b_factor_quality_assessed": False,
        "b_factor_units_interpreted": False,
        "standard_uncertainty_interpreted": False,
        "formal_charge_chemistry_validated": False,
        "coordinate_units_interpreted": False,
        "coordinate_geometry_interpreted": False,
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


def _raw_lexeme(text: str, value: MmcifSemanticValue, *, field_name: str) -> str:
    lines = text.splitlines()
    line_index = value.line_number - 1
    start = value.column_number - 1
    if line_index < 0 or line_index >= len(lines) or start < 0:
        raise MmcifNonpolyAtomSiteScalarValueError(
            "scalar_source_location_invalid",
            f"{field_name} source location is outside the bounded input",
            line_number=value.line_number,
        )
    line = lines[line_index]
    if start >= len(line):
        raise MmcifNonpolyAtomSiteScalarValueError(
            "scalar_source_location_invalid",
            f"{field_name} source location is outside the bounded input",
            line_number=value.line_number,
        )
    if value.quoted:
        quote = line[start]
        if quote not in {"'", '"'}:
            raise MmcifNonpolyAtomSiteScalarValueError(
                "scalar_source_lexeme_mismatch",
                f"{field_name} quoted source spelling cannot be recovered",
                line_number=value.line_number,
            )
        end = line.find(quote, start + 1)
        while end >= 0 and end + 1 < len(line) and line[end + 1] not in " \t":
            end = line.find(quote, end + 1)
        if end < 0 or line[start + 1 : end] != value.value:
            raise MmcifNonpolyAtomSiteScalarValueError(
                "scalar_source_lexeme_mismatch",
                f"{field_name} quoted source spelling cannot be recovered",
                line_number=value.line_number,
            )
        return line[start : end + 1]
    end = start
    while end < len(line) and line[end] not in " \t":
        end += 1
    lexeme = line[start:end]
    if lexeme != value.value:
        raise MmcifNonpolyAtomSiteScalarValueError(
            "scalar_source_lexeme_mismatch",
            f"{field_name} bare source spelling cannot be recovered",
            line_number=value.line_number,
        )
    return lexeme


def _raw_token(value: MmcifSemanticValue, lexeme: str) -> dict[str, Any]:
    return {"value": value.value, "lexeme": lexeme, "quoted": value.quoted}


def _float_scalar(
    text: str,
    value: MmcifSemanticValue,
    *,
    field_name: str,
    occupancy: bool,
) -> MmcifAtomSiteFloatScalarValue:
    lexeme = _raw_lexeme(text, value, field_name=field_name)
    raw = _raw_token(value, lexeme)
    if value.state != "known":
        identity = _sha256({"state": value.state})
        return MmcifAtomSiteFloatScalarValue(
            field_name=field_name,
            state=value.state,
            raw_value=value.value,
            raw_lexeme=lexeme,
            quoted=value.quoted,
            numeric_value=None,
            binary64_bits_hex=None,
            binary64_hex=None,
            standard_uncertainty_digits=None,
            value_identity_sha256=identity,
            source_value_binding_sha256=_sha256(
                {"raw_token": raw, "value_identity_sha256": identity}
            ),
        )
    match = _MMCIF_FLOAT_RE.fullmatch(value.value)
    if match is None:
        raise MmcifNonpolyAtomSiteScalarValueError(
            "invalid_scalar_float",
            f"{field_name} must use the bounded PDBx/mmCIF float grammar",
            line_number=value.line_number,
        )
    numeric_text = match.group("mantissa") + (match.group("exponent") or "")
    numeric = float(numeric_text)
    if not math.isfinite(numeric):
        raise MmcifNonpolyAtomSiteScalarValueError(
            "nonfinite_scalar_value",
            f"{field_name} must round to a finite binary64 value",
            line_number=value.line_number,
        )
    if occupancy and not 0.0 <= numeric <= 1.0:
        raise MmcifNonpolyAtomSiteScalarValueError(
            "occupancy_out_of_bounds",
            "_atom_site.occupancy must be within the bounded unit interval",
            line_number=value.line_number,
        )
    bits = _bits(numeric)
    identity = _sha256({"state": "known", "binary64_bits_hex": bits})
    uncertainty = match.group("uncertainty")
    return MmcifAtomSiteFloatScalarValue(
        field_name=field_name,
        state="known",
        raw_value=value.value,
        raw_lexeme=lexeme,
        quoted=value.quoted,
        numeric_value=numeric,
        binary64_bits_hex=bits,
        binary64_hex=numeric.hex(),
        standard_uncertainty_digits=uncertainty,
        value_identity_sha256=identity,
        source_value_binding_sha256=_sha256(
            {
                "raw_token": raw,
                "standard_uncertainty_digits": uncertainty,
                "value_identity_sha256": identity,
            }
        ),
    )


def _formal_charge(
    text: str,
    value: MmcifSemanticValue,
) -> MmcifAtomSiteFormalChargeValue:
    field_name = "_atom_site.pdbx_formal_charge"
    lexeme = _raw_lexeme(text, value, field_name=field_name)
    raw = _raw_token(value, lexeme)
    if value.state != "known":
        identity = _sha256({"state": value.state})
        integer_value = None
    else:
        if _MMCIF_INTEGER_RE.fullmatch(value.value) is None:
            raise MmcifNonpolyAtomSiteScalarValueError(
                "invalid_formal_charge_integer",
                "formal charge must use the PDBx/mmCIF integer grammar",
                line_number=value.line_number,
            )
        integer_value = int(value.value)
        if not MMCIF_FORMAL_CHARGE_MINIMUM <= integer_value <= MMCIF_FORMAL_CHARGE_MAXIMUM:
            raise MmcifNonpolyAtomSiteScalarValueError(
                "formal_charge_out_of_bounds",
                "formal charge is outside the PDBx/mmCIF dictionary boundary",
                line_number=value.line_number,
            )
        identity = _sha256({"state": "known", "integer_value": integer_value})
    return MmcifAtomSiteFormalChargeValue(
        field_name=field_name,
        state=value.state,
        raw_value=value.value,
        raw_lexeme=lexeme,
        quoted=value.quoted,
        integer_value=integer_value,
        value_identity_sha256=identity,
        source_value_binding_sha256=_sha256(
            {"raw_token": raw, "value_identity_sha256": identity}
        ),
    )


def _scalar_observation(
    text: str,
    observation: MmcifNonpolyAtomSiteObservation,
    *,
    coordinate_value_identity_sha256: str,
) -> MmcifNonpolyAtomSiteScalarObservation:
    occupancy = _float_scalar(
        text,
        observation.occupancy,
        field_name="_atom_site.occupancy",
        occupancy=True,
    )
    b_factor = _float_scalar(
        text,
        observation.b_iso_or_equiv,
        field_name="_atom_site.b_iso_or_equiv",
        occupancy=False,
    )
    formal_charge = _formal_charge(text, observation.formal_charge)
    identity = _sha256(
        {
            "site_identity_sha256": observation.site_identity_sha256,
            "occupancy_value_identity_sha256": occupancy.value_identity_sha256,
            "b_factor_value_identity_sha256": b_factor.value_identity_sha256,
            "formal_charge_value_identity_sha256": formal_charge.value_identity_sha256,
        }
    )
    source_binding = _sha256(
        {
            "scalar_value_identity_sha256": identity,
            "occupancy": occupancy.to_dict(),
            "b_iso_or_equiv": b_factor.to_dict(),
            "formal_charge": formal_charge.to_dict(),
        }
    )
    return MmcifNonpolyAtomSiteScalarObservation(
        source_atom_id=observation.source_atom_id,
        site_identity_sha256=observation.site_identity_sha256,
        coordinate_value_identity_sha256=coordinate_value_identity_sha256,
        occupancy=occupancy,
        b_iso_or_equiv=b_factor,
        formal_charge=formal_charge,
        scalar_value_identity_sha256=identity,
        scalar_source_binding_sha256=source_binding,
        source_ordinal=observation.source_ordinal,
    )


def parse_mmcif_nonpoly_atom_site_scalar_values(
    text: str,
) -> MmcifNonpolyAtomSiteScalarValueSnapshot:
    """Interpret selected nonpoly occupancy, B-factor, and formal-charge values."""

    if type(text) is not str:
        raise TypeError("mmCIF nonpoly atom-site scalar value input must be a string")
    coordinate = parse_mmcif_nonpoly_coordinate_values(text)
    observation = parse_mmcif_nonpoly_atom_site_observations(text)
    if (
        coordinate.source_sha256 != observation.source_sha256
        or coordinate.observation_snapshot_sha256 != observation.snapshot_sha256
        or len(coordinate.coordinates) != len(observation.observations)
    ):
        raise MmcifNonpolyAtomSiteScalarValueError(
            "coordinate_observation_binding_mismatch",
            "coordinate and observation carriers must describe the same selected rows",
        )
    rows: list[MmcifNonpolyAtomSiteScalarObservation] = []
    for source_row, coordinate_row in zip(
        observation.observations, coordinate.coordinates, strict=True
    ):
        if (
            source_row.source_atom_id != coordinate_row.source_atom_id
            or source_row.site_identity_sha256 != coordinate_row.site_identity_sha256
            or source_row.source_ordinal != coordinate_row.source_ordinal
        ):
            raise MmcifNonpolyAtomSiteScalarValueError(
                "coordinate_observation_row_mismatch",
                "coordinate and observation row identities must match exactly",
            )
        rows.append(
            _scalar_observation(
                text,
                source_row,
                coordinate_value_identity_sha256=(
                    coordinate_row.coordinate_value_identity_sha256
                ),
            )
        )
    return MmcifNonpolyAtomSiteScalarValueSnapshot(
        source_sha256=observation.source_sha256,
        observation_snapshot_sha256=observation.snapshot_sha256,
        coordinate_snapshot_sha256=coordinate.snapshot_sha256,
        coordinate_projection_sha256=coordinate.coordinate_projection_sha256,
        coordinate_source_binding_sha256=coordinate.source_binding_sha256,
        scalar_observations=tuple(rows),
    )


def mmcif_nonpoly_atom_site_scalar_value_projection(
    snapshot: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROJECTION_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION,
        "coordinate_projection_sha256": snapshot.coordinate_projection_sha256,
        "scalar_observations": [row.to_dict() for row in snapshot.scalar_observations],
        "row_order": "selected_source_atom_site_order",
        **_claim_policy(),
    }


def mmcif_nonpoly_atom_site_scalar_value_source_binding(
    snapshot: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> dict[str, Any]:
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_SOURCE_BINDING_SCHEMA_ID,
        "source_sha256": snapshot.source_sha256,
        "observation_snapshot_sha256": snapshot.observation_snapshot_sha256,
        "coordinate_snapshot_sha256": snapshot.coordinate_snapshot_sha256,
        "coordinate_source_binding_sha256": snapshot.coordinate_source_binding_sha256,
        "scalar_headers": list(MMCIF_NONPOLY_ATOM_SITE_SCALAR_HEADERS),
        "dictionary_items": dict(MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS),
        "scalar_source_binding_sha256": [
            row.scalar_source_binding_sha256 for row in snapshot.scalar_observations
        ],
    }


def mmcif_nonpoly_atom_site_scalar_value_document(
    snapshot: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> dict[str, Any]:
    projection = mmcif_nonpoly_atom_site_scalar_value_projection(snapshot)
    binding = mmcif_nonpoly_atom_site_scalar_value_source_binding(snapshot)
    return {
        "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
        "profile_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID,
        "parser_version": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION,
        "scalar_projection": projection,
        "source_binding": binding,
        "scalar_projection_sha256": _sha256(projection),
        "source_binding_sha256": _sha256(binding),
        **snapshot.to_dict(),
    }


def _require_digest(value: object, label: str) -> str:
    candidate = str(value or "")
    if _SHA256_RE.fullmatch(candidate) is None:
        raise ValueError(f"nonpoly atom-site scalar {label} digest invalid")
    return candidate


def _require_raw_token(payload: object, state: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site scalar raw token must be a mapping")
    raw = dict(payload)
    value = raw.get("value")
    lexeme = raw.get("lexeme")
    quoted = raw.get("quoted")
    if type(value) is not str or type(lexeme) is not str or type(quoted) is not bool:
        raise ValueError("nonpoly atom-site scalar raw token is invalid")
    if quoted:
        if (
            len(lexeme) < 2
            or lexeme[0] not in {"'", '"'}
            or lexeme[-1] != lexeme[0]
            or lexeme[1:-1] != value
        ):
            raise ValueError("nonpoly atom-site scalar quoted lexeme mismatch")
    elif lexeme != value:
        raise ValueError("nonpoly atom-site scalar bare lexeme mismatch")
    if state == "unknown" and (value, quoted) != ("?", False):
        raise ValueError("nonpoly atom-site scalar unknown marker mismatch")
    if state == "not_applicable" and (value, quoted) != (".", False):
        raise ValueError("nonpoly atom-site scalar not-applicable marker mismatch")
    return raw


def _require_float_scalar(payload: object, field_name: str, *, occupancy: bool) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site float scalar must be a mapping")
    scalar = dict(payload)
    state = scalar.get("state")
    if state not in {"known", "unknown", "not_applicable"}:
        raise ValueError("nonpoly atom-site float scalar state invalid")
    if scalar.get("field_name") != field_name:
        raise ValueError("nonpoly atom-site float scalar field mismatch")
    raw = _require_raw_token(scalar.get("raw_token"), state)
    if state != "known":
        if any(
            scalar.get(key) is not None
            for key in (
                "numeric_value",
                "binary64_bits_hex",
                "binary64_hex",
                "standard_uncertainty_digits",
            )
        ) or scalar.get("numeric_kind") != "unavailable":
            raise ValueError("nonpoly atom-site unavailable float scalar has a numeric value")
        identity = _sha256({"state": state})
    else:
        match = _MMCIF_FLOAT_RE.fullmatch(raw["value"])
        if match is None:
            raise ValueError("nonpoly atom-site float scalar grammar mismatch")
        numeric_text = match.group("mantissa") + (match.group("exponent") or "")
        numeric = float(numeric_text)
        if not math.isfinite(numeric):
            raise ValueError("nonpoly atom-site float scalar is not finite")
        if occupancy and not 0.0 <= numeric <= 1.0:
            raise ValueError("nonpoly atom-site occupancy is outside the unit interval")
        supplied = scalar.get("numeric_value")
        if type(supplied) not in (int, float) or _bits(float(supplied)) != _bits(numeric):
            raise ValueError("nonpoly atom-site float scalar numeric value mismatch")
        bits = _bits(numeric)
        if (
            _BINARY64_BITS_RE.fullmatch(str(scalar.get("binary64_bits_hex") or ""))
            is None
            or scalar.get("binary64_bits_hex") != bits
            or scalar.get("binary64_hex") != numeric.hex()
            or scalar.get("standard_uncertainty_digits") != match.group("uncertainty")
            or scalar.get("numeric_kind") != "finite_binary64"
        ):
            raise ValueError("nonpoly atom-site float scalar representation mismatch")
        identity = _sha256({"state": "known", "binary64_bits_hex": bits})
    if scalar.get("value_identity_sha256") != identity:
        raise ValueError("nonpoly atom-site float scalar value identity mismatch")
    expected_binding_payload: dict[str, Any] = {
        "raw_token": raw,
        "value_identity_sha256": identity,
    }
    if state == "known":
        expected_binding_payload["standard_uncertainty_digits"] = scalar.get(
            "standard_uncertainty_digits"
        )
    binding = _sha256(expected_binding_payload)
    if scalar.get("source_value_binding_sha256") != binding:
        raise ValueError("nonpoly atom-site float scalar source binding mismatch")
    return identity, scalar


def _require_formal_charge(payload: object) -> tuple[str, dict[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site formal charge must be a mapping")
    scalar = dict(payload)
    state = scalar.get("state")
    if state not in {"known", "unknown", "not_applicable"}:
        raise ValueError("nonpoly atom-site formal charge state invalid")
    if scalar.get("field_name") != "_atom_site.pdbx_formal_charge":
        raise ValueError("nonpoly atom-site formal charge field mismatch")
    raw = _require_raw_token(scalar.get("raw_token"), state)
    if (
        scalar.get("minimum") != MMCIF_FORMAL_CHARGE_MINIMUM
        or scalar.get("maximum") != MMCIF_FORMAL_CHARGE_MAXIMUM
    ):
        raise ValueError("nonpoly atom-site formal charge boundary mismatch")
    if state != "known":
        if scalar.get("integer_value") is not None or scalar.get("numeric_kind") != "unavailable":
            raise ValueError("nonpoly atom-site unavailable formal charge has a value")
        identity = _sha256({"state": state})
    else:
        if _MMCIF_INTEGER_RE.fullmatch(raw["value"]) is None:
            raise ValueError("nonpoly atom-site formal charge grammar mismatch")
        integer = int(raw["value"])
        if not MMCIF_FORMAL_CHARGE_MINIMUM <= integer <= MMCIF_FORMAL_CHARGE_MAXIMUM:
            raise ValueError("nonpoly atom-site formal charge outside dictionary boundary")
        if type(scalar.get("integer_value")) is not int or scalar.get("integer_value") != integer:
            raise ValueError("nonpoly atom-site formal charge integer mismatch")
        if scalar.get("numeric_kind") != "bounded_integer":
            raise ValueError("nonpoly atom-site formal charge numeric kind mismatch")
        identity = _sha256({"state": "known", "integer_value": integer})
    if scalar.get("value_identity_sha256") != identity:
        raise ValueError("nonpoly atom-site formal charge identity mismatch")
    binding = _sha256({"raw_token": raw, "value_identity_sha256": identity})
    if scalar.get("source_value_binding_sha256") != binding:
        raise ValueError("nonpoly atom-site formal charge source binding mismatch")
    return identity, scalar


def _require_scalar_row(payload: object) -> tuple[int, str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site scalar observation must be a mapping")
    row = dict(payload)
    source_id = row.get("source_atom_id")
    ordinal = row.get("source_ordinal")
    if type(source_id) is not int or source_id <= 0:
        raise ValueError("nonpoly atom-site scalar source atom id invalid")
    if type(ordinal) is not int or ordinal < 0:
        raise ValueError("nonpoly atom-site scalar source ordinal invalid")
    site_identity = _require_digest(row.get("site_identity_sha256"), "site identity")
    _require_digest(row.get("coordinate_value_identity_sha256"), "coordinate value identity")
    occupancy_identity, occupancy = _require_float_scalar(
        row.get("occupancy"), "_atom_site.occupancy", occupancy=True
    )
    b_identity, b_factor = _require_float_scalar(
        row.get("b_iso_or_equiv"), "_atom_site.b_iso_or_equiv", occupancy=False
    )
    charge_identity, formal_charge = _require_formal_charge(row.get("formal_charge"))
    identity = _sha256(
        {
            "site_identity_sha256": site_identity,
            "occupancy_value_identity_sha256": occupancy_identity,
            "b_factor_value_identity_sha256": b_identity,
            "formal_charge_value_identity_sha256": charge_identity,
        }
    )
    if row.get("scalar_value_identity_sha256") != identity:
        raise ValueError("nonpoly atom-site scalar observation identity mismatch")
    binding = _sha256(
        {
            "scalar_value_identity_sha256": identity,
            "occupancy": occupancy,
            "b_iso_or_equiv": b_factor,
            "formal_charge": formal_charge,
        }
    )
    if row.get("scalar_source_binding_sha256") != binding:
        raise ValueError("nonpoly atom-site scalar observation source binding mismatch")
    return source_id, site_identity, binding


def require_mmcif_nonpoly_atom_site_scalar_value_document(
    payload: object,
) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError("nonpoly atom-site scalar document must be a mapping")
    document = dict(payload)
    if document.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID:
        raise ValueError("nonpoly atom-site scalar document schema mismatch")
    if document.get("profile_id") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID:
        raise ValueError("nonpoly atom-site scalar profile mismatch")
    if document.get("parser_version") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION:
        raise ValueError("nonpoly atom-site scalar parser version mismatch")
    projection = document.get("scalar_projection")
    binding = document.get("source_binding")
    if not isinstance(projection, Mapping) or not isinstance(binding, Mapping):
        raise ValueError("nonpoly atom-site scalar sections must be mappings")
    if projection.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROJECTION_SCHEMA_ID:
        raise ValueError("nonpoly atom-site scalar projection schema mismatch")
    if binding.get("schema_id") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_SOURCE_BINDING_SCHEMA_ID:
        raise ValueError("nonpoly atom-site scalar source binding schema mismatch")
    projection_digest = _sha256(dict(projection))
    binding_digest = _sha256(dict(binding))
    if document.get("scalar_projection_sha256") != projection_digest:
        raise ValueError("nonpoly atom-site scalar projection digest mismatch")
    if document.get("source_binding_sha256") != binding_digest:
        raise ValueError("nonpoly atom-site scalar source binding digest mismatch")
    expected_snapshot = _sha256(
        {
            "schema_id": MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID,
            "scalar_projection_sha256": projection_digest,
            "source_binding_sha256": binding_digest,
            "claim_policy": _claim_policy(),
        }
    )
    if document.get("snapshot_sha256") != expected_snapshot:
        raise ValueError("nonpoly atom-site scalar snapshot digest mismatch")
    for key, expected in _claim_policy().items():
        if document.get(key) is not expected or projection.get(key) is not expected:
            raise ValueError("nonpoly atom-site scalar claim policy mismatch")

    rows = projection.get("scalar_observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonpoly atom-site scalar observations must be a non-empty list")
    if document.get("scalar_observation_count") != len(rows):
        raise ValueError("nonpoly atom-site scalar observation count mismatch")
    if document.get("scalar_value_count") != 3 * len(rows):
        raise ValueError("nonpoly atom-site scalar value count mismatch")
    source_ids: set[int] = set()
    site_ids: set[str] = set()
    source_bindings: list[str] = []
    state_counts = {
        field: {state: 0 for state in ("known", "unknown", "not_applicable")}
        for field in ("occupancy", "b_iso_or_equiv", "formal_charge")
    }
    for row in rows:
        source_id, site_id, source_binding = _require_scalar_row(row)
        if source_id in source_ids or site_id in site_ids:
            raise ValueError("nonpoly atom-site scalar observations must be unique")
        source_ids.add(source_id)
        site_ids.add(site_id)
        source_bindings.append(source_binding)
        if not isinstance(row, Mapping):
            raise ValueError("nonpoly atom-site scalar observation must be a mapping")
        for field in state_counts:
            scalar = row[field]
            if not isinstance(scalar, Mapping):
                raise ValueError("nonpoly atom-site scalar field must be a mapping")
            state_counts[field][str(scalar["state"])] += 1
    if document.get("state_counts") != state_counts:
        raise ValueError("nonpoly atom-site scalar state counts mismatch")

    source_sha = _require_digest(binding.get("source_sha256"), "source")
    if document.get("source_sha256") != source_sha:
        raise ValueError("nonpoly atom-site scalar source digest mismatch")
    observation_snapshot = _require_digest(
        binding.get("observation_snapshot_sha256"), "observation snapshot"
    )
    coordinate_snapshot = _require_digest(
        binding.get("coordinate_snapshot_sha256"), "coordinate snapshot"
    )
    if document.get("observation_snapshot_sha256") != observation_snapshot:
        raise ValueError("nonpoly atom-site scalar observation snapshot mismatch")
    if document.get("coordinate_snapshot_sha256") != coordinate_snapshot:
        raise ValueError("nonpoly atom-site scalar coordinate snapshot mismatch")
    _require_digest(
        projection.get("coordinate_projection_sha256"), "coordinate projection"
    )
    _require_digest(
        binding.get("coordinate_source_binding_sha256"), "coordinate source binding"
    )
    if binding.get("scalar_headers") != list(MMCIF_NONPOLY_ATOM_SITE_SCALAR_HEADERS):
        raise ValueError("nonpoly atom-site scalar source header binding mismatch")
    if binding.get("dictionary_items") != MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS:
        raise ValueError("nonpoly atom-site scalar dictionary binding mismatch")
    if binding.get("scalar_source_binding_sha256") != source_bindings:
        raise ValueError("nonpoly atom-site scalar source binding sequence mismatch")
    return payload


def mmcif_nonpoly_atom_site_scalar_value_json_bytes(
    snapshot: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> bytes:
    return _canonical_bytes(mmcif_nonpoly_atom_site_scalar_value_document(snapshot))


def write_mmcif_nonpoly_atom_site_scalar_value_json(
    path: str | Path,
    snapshot: MmcifNonpolyAtomSiteScalarValueSnapshot,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = mmcif_nonpoly_atom_site_scalar_value_json_bytes(snapshot) + b"\n"
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
    "MMCIF_FORMAL_CHARGE_MAXIMUM",
    "MMCIF_FORMAL_CHARGE_MINIMUM",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_DICTIONARY_ITEMS",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_HEADERS",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_DOCUMENT_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PARSER_VERSION",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROFILE_ID",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_PROJECTION_SCHEMA_ID",
    "MMCIF_NONPOLY_ATOM_SITE_SCALAR_VALUE_SOURCE_BINDING_SCHEMA_ID",
    "MmcifAtomSiteFloatScalarValue",
    "MmcifAtomSiteFormalChargeValue",
    "MmcifNonpolyAtomSiteScalarObservation",
    "MmcifNonpolyAtomSiteScalarValueError",
    "MmcifNonpolyAtomSiteScalarValueSnapshot",
    "mmcif_nonpoly_atom_site_scalar_value_document",
    "mmcif_nonpoly_atom_site_scalar_value_json_bytes",
    "mmcif_nonpoly_atom_site_scalar_value_projection",
    "mmcif_nonpoly_atom_site_scalar_value_source_binding",
    "parse_mmcif_nonpoly_atom_site_scalar_values",
    "require_mmcif_nonpoly_atom_site_scalar_value_document",
    "write_mmcif_nonpoly_atom_site_scalar_value_json",
]
