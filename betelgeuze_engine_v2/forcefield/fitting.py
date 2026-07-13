"""Deterministic nonphysical harmonic fitting pipeline scaffold.

The bundled pipeline exists to prove artifact separation, exact arithmetic,
hash binding, and fit-receipt mechanics.  Its inputs are synthetic test-only
rows and its output is never scientifically validated or runtime eligible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
import re
from typing import Any

from . import parameters as _parameter_contract
from .parameters import (
    ExactMethaneBondAngleParameterSet,
    ForceFieldParameterContractError,
    HarmonicAngleParameter,
    HarmonicBondParameter,
    _binary64_hex,
    _canonical_json_bytes,
    _sha256_document,
)


SYNTHETIC_HARMONIC_FIT_ROWS_SCHEMA_ID = (
    "betelgeuze.synthetic_harmonic_fit_rows/1.0.0"
)
PARAMETER_FIT_DATASET_MANIFEST_SCHEMA_ID = (
    "betelgeuze.parameter_fit_dataset_manifest/1.0.0"
)
PARAMETER_FIT_SPLIT_MANIFEST_SCHEMA_ID = (
    "betelgeuze.parameter_fit_split_manifest/1.0.0"
)
PARAMETER_FIT_RUN_RECEIPT_SCHEMA_ID = (
    "betelgeuze.parameter_fit_run_receipt/1.0.0"
)
SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID = (
    "betelgeuze.synthetic_harmonic_fit_protocol/1.0.0"
)
SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID = (
    "exact_three_point_zero_offset_harmonic_fraction_fit_v1"
)
SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID_1_1 = (
    "betelgeuze.synthetic_harmonic_fit_protocol/1.1.0"
)
SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1 = (
    "exact_three_point_zero_offset_harmonic_fraction_fit_form_bound_v1_1"
)
SYNTHETIC_HARMONIC_FIT_ALGORITHM_ID = (
    "exact_three_point_quadratic_interpolation/1.0.0"
)
SYNTHETIC_HARMONIC_ARITHMETIC_POLICY_ID = (
    "canonical_decimal_to_fraction_exact_binary64_exact_only/1.0.0"
)
SYNTHETIC_HARMONIC_OBJECTIVE_ID = (
    "energy_equals_one_half_k_delta_q_squared_zero_offset/1.0.0"
)
SYNTHETIC_OUTPUT_PARAMETER_SET_ID = (
    "nonphysical_synthetic_fit_exact_methane_candidate"
)
SYNTHETIC_OUTPUT_PARAMETER_SET_VERSION = "1.0.0"

_MAX_FIT_INPUT_BYTES = 1024 * 1024
_CANONICAL_DECIMAL_RE = re.compile(
    r"^(?:0|[1-9][0-9]*)(?:\.(?:[0-9]*[1-9]))?$"
)
_LOWER_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_FACTORY_TOKEN = object()
_BINARY64_PI = Fraction.from_float(math.pi)

_ROWS_KEYS = frozenset(
    {"schema_id", "artifact_purpose", "scientific_status", "energy_unit", "rows"}
)
_ROW_KEYS = frozenset(
    {
        "row_id",
        "term_kind",
        "coordinate_unit",
        "coordinate_decimal",
        "energy_decimal",
    }
)
_DATASET_KEYS = frozenset(
    {
        "schema_id",
        "dataset_id",
        "dataset_version",
        "artifact_purpose",
        "scientific_status",
        "rows_artifact_name",
        "rows_sha256",
        "row_count",
        "bond_row_count",
        "angle_row_count",
        "license_review_status",
        "source_authentication_status",
        "runtime_eligible",
        "manifest_sha256",
    }
)
_SPLIT_KEYS = frozenset(
    {
        "schema_id",
        "split_id",
        "split_version",
        "dataset_id",
        "dataset_version",
        "dataset_manifest_sha256",
        "rows_sha256",
        "split_policy_id",
        "fit_row_ids",
        "holdout_row_ids",
        "artifact_purpose",
        "runtime_eligible",
        "manifest_sha256",
    }
)


class ParameterFitContractError(ValueError):
    """Raised when synthetic fit inputs or derived evidence are invalid."""


# Kept as a compatibility alias for callers that inspect the module.  Fit
# behavior below is bound to the private parameter-contract snapshot instead.
EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = (
    _parameter_contract.EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
)


_FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION = (
    _parameter_contract
    ._FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION
)
_FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_ID = (
    _parameter_contract
    ._FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID
)
_FROZEN_FORM_BOUND_OUTPUT_PARAMETER_SCHEMA_VERSION = (
    _parameter_contract
    ._FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_VERSION_1_1
)
_FROZEN_FORM_BOUND_OUTPUT_PARAMETER_SCHEMA_ID = (
    _parameter_contract
    ._FROZEN_EXACT_METHANE_BOND_ANGLE_PARAMETER_SET_SCHEMA_ID_1_1
)
_FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID = (
    _parameter_contract._FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
)


_SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES = _canonical_json_bytes(
    {
        "schema_id": SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID,
        "protocol_id": SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID,
        "algorithm_id": SYNTHETIC_HARMONIC_FIT_ALGORITHM_ID,
        "arithmetic_policy_id": SYNTHETIC_HARMONIC_ARITHMETIC_POLICY_ID,
        "objective_id": SYNTHETIC_HARMONIC_OBJECTIVE_ID,
        "energy_convention": "E(q)=0.5*k*(q-q0)^2",
        "additive_energy_offset": "exactly_zero_required",
        "fit_rows_per_term_kind": 3,
        "holdout_rows_used_for_fit": False,
        "holdout_residual_policy": "exact_zero_required",
        "random_seed": None,
    }
)

_SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES_1_1 = _canonical_json_bytes(
    {
        "schema_id": SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID_1_1,
        "protocol_id": SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1,
        "algorithm_id": SYNTHETIC_HARMONIC_FIT_ALGORITHM_ID,
        "arithmetic_policy_id": SYNTHETIC_HARMONIC_ARITHMETIC_POLICY_ID,
        "objective_id": SYNTHETIC_HARMONIC_OBJECTIVE_ID,
        "energy_convention": "E(q)=0.5*k*(q-q0)^2",
        "additive_energy_offset": "exactly_zero_required",
        "fit_rows_per_term_kind": 3,
        "holdout_rows_used_for_fit": False,
        "holdout_residual_policy": "exact_zero_required",
        "random_seed": None,
        "output_parameter_set_schema_id": (
            _FROZEN_FORM_BOUND_OUTPUT_PARAMETER_SCHEMA_ID
        ),
        "functional_form_id": (
            _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID
        ),
    }
)


def _output_parameter_contract(
    artifact_schema_version: str,
) -> tuple[str, str | None, bytes]:
    if type(artifact_schema_version) is not str:
        raise ParameterFitContractError(
            "output_parameter_artifact_schema_version must be a string"
        )
    if artifact_schema_version == (
        _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
    ):
        return (
            _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_ID,
            None,
            _SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES,
        )
    if artifact_schema_version == (
        _FROZEN_FORM_BOUND_OUTPUT_PARAMETER_SCHEMA_VERSION
    ):
        return (
            _FROZEN_FORM_BOUND_OUTPUT_PARAMETER_SCHEMA_ID,
            _FROZEN_EXACT_METHANE_HARMONIC_FUNCTIONAL_FORM_ID,
            _SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES_1_1,
        )
    raise ParameterFitContractError(
        "unsupported output parameter artifact schema version"
    )


def _output_parameter_constructor_kwargs(
    artifact_schema_version: str,
) -> dict[str, str | None]:
    _, functional_form_id, _ = _output_parameter_contract(
        artifact_schema_version
    )
    return {
        "artifact_schema_version": artifact_schema_version,
        "functional_form_id": functional_form_id,
    }


def _protocol_document(
    output_parameter_artifact_schema_version: str = (
        _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
    ),
) -> dict[str, Any]:
    # The canonical bytes, rather than mutable module attributes, are the
    # single source of truth for both execution receipts and their digest.
    _, _, protocol_bytes = _output_parameter_contract(
        output_parameter_artifact_schema_version
    )
    document = json.loads(protocol_bytes)
    if type(document) is not dict:  # pragma: no cover - fixed import snapshot
        raise RuntimeError("frozen fit protocol must decode to an object")
    return document


_FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256 = hashlib.sha256(
    _SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES
).hexdigest()
SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256 = (
    _FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256
)
_FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1 = hashlib.sha256(
    _SYNTHETIC_HARMONIC_FIT_PROTOCOL_BYTES_1_1
).hexdigest()
SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1 = (
    _FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1
)


def _frozen_protocol_sha256(artifact_schema_version: str) -> str:
    _output_parameter_contract(artifact_schema_version)
    if artifact_schema_version == (
        _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
    ):
        return _FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256
    return _FROZEN_SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1


def _require_exact_keys(
    value: Any,
    expected: frozenset[str],
    location: str,
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ParameterFitContractError(f"{location} must be a JSON object")
    observed = set(value)
    if observed != expected:
        raise ParameterFitContractError(
            f"{location} keys mismatch: missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )
    return value


def _require_string(name: str, value: Any) -> str:
    if type(value) is not str or not value:
        raise ParameterFitContractError(f"{name} must be a nonempty string")
    return value


def _require_exact_int(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise ParameterFitContractError(
            f"{name} must be a non-negative exact integer"
        )
    return value


def _require_sha256(name: str, value: Any) -> str:
    if type(value) is not str or _LOWER_SHA256_RE.fullmatch(value) is None:
        raise ParameterFitContractError(f"{name} must be a lowercase SHA-256")
    return value


def _canonical_fraction(name: str, value: Any) -> Fraction:
    if (
        type(value) is not str
        or len(value) > 64
        or _CANONICAL_DECIMAL_RE.fullmatch(value) is None
    ):
        raise ParameterFitContractError(
            f"{name} must be a canonical non-negative decimal string"
        )
    return Fraction(value)


def _fraction_document(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _fraction_to_exact_binary64(name: str, value: Fraction) -> float:
    result = float(value)
    if Fraction.from_float(result) != value:
        raise ParameterFitContractError(
            f"{name} is not exactly representable as IEEE-754 binary64"
        )
    return result


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ParameterFitContractError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ParameterFitContractError(
        f"non-standard JSON constant {value!r} is not allowed"
    )


def _parse_json(data: bytes, location: str) -> dict[str, Any]:
    if type(data) is not bytes:
        raise TypeError(f"{location} payload must be bytes")
    if len(data) > _MAX_FIT_INPUT_BYTES:
        raise ParameterFitContractError(f"{location} exceeds the fixed byte limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParameterFitContractError(
            f"{location} must be valid UTF-8 JSON"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except ParameterFitContractError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ParameterFitContractError(f"invalid {location} JSON: {exc}") from exc
    if type(value) is not dict:
        raise ParameterFitContractError(f"{location} root must be an object")
    return value


@dataclass(frozen=True, order=True)
class SyntheticHarmonicFitRow:
    row_id: str
    term_kind: str
    coordinate_unit: str
    coordinate_decimal: str
    energy_decimal: str

    def __post_init__(self) -> None:
        _require_string("row_id", self.row_id)
        if type(self.term_kind) is not str or self.term_kind not in {
            "bond",
            "angle",
        }:
            raise ParameterFitContractError("term_kind must be bond or angle")
        expected_unit = "angstrom" if self.term_kind == "bond" else "radian"
        if self.coordinate_unit != expected_unit:
            raise ParameterFitContractError(
                f"{self.term_kind} rows require {expected_unit} coordinates"
            )
        if self.coordinate <= 0:
            raise ParameterFitContractError("fit coordinates must be positive")
        if self.term_kind == "angle" and self.coordinate >= _BINARY64_PI:
            raise ParameterFitContractError(
                "angle fit coordinates must be strictly between zero and pi radians"
            )
        if self.energy < 0:
            raise ParameterFitContractError("fit energies cannot be negative")

    @property
    def coordinate(self) -> Fraction:
        return _canonical_fraction("coordinate_decimal", self.coordinate_decimal)

    @property
    def energy(self) -> Fraction:
        return _canonical_fraction("energy_decimal", self.energy_decimal)

    def to_dict(self) -> dict[str, str]:
        return {
            "row_id": self.row_id,
            "term_kind": self.term_kind,
            "coordinate_unit": self.coordinate_unit,
            "coordinate_decimal": self.coordinate_decimal,
            "energy_decimal": self.energy_decimal,
        }


@dataclass(frozen=True)
class SyntheticHarmonicFitRows:
    rows: tuple[SyntheticHarmonicFitRow, ...]
    rows_sha256: str

    def __post_init__(self) -> None:
        if type(self.rows) is not tuple or not all(
            type(row) is SyntheticHarmonicFitRow for row in self.rows
        ):
            raise TypeError("rows must be a tuple of SyntheticHarmonicFitRow")
        if tuple(row.row_id for row in self.rows) != tuple(
            sorted(row.row_id for row in self.rows)
        ):
            raise ParameterFitContractError("fit rows must be sorted by row_id")
        if len({row.row_id for row in self.rows}) != len(self.rows):
            raise ParameterFitContractError("fit row IDs must be unique")
        _require_sha256("rows_sha256", self.rows_sha256)

    @property
    def by_id(self) -> dict[str, SyntheticHarmonicFitRow]:
        return {row.row_id: row for row in self.rows}


@dataclass(frozen=True)
class ParameterFitDatasetManifest:
    dataset_id: str
    dataset_version: str
    rows_artifact_name: str
    rows_sha256: str
    row_count: int
    bond_row_count: int
    angle_row_count: int
    manifest_sha256: str

    def __post_init__(self) -> None:
        for name in ("dataset_id", "dataset_version", "rows_artifact_name"):
            _require_string(name, getattr(self, name))
        _require_sha256("rows_sha256", self.rows_sha256)
        _require_sha256("manifest_sha256", self.manifest_sha256)
        for name in ("row_count", "bond_row_count", "angle_row_count"):
            _require_exact_int(name, getattr(self, name))
        if self.bond_row_count + self.angle_row_count != self.row_count:
            raise ParameterFitContractError(
                "dataset term counts must sum to row_count"
            )

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PARAMETER_FIT_DATASET_MANIFEST_SCHEMA_ID,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "artifact_purpose": "contract_fixture_only",
            "scientific_status": "nonphysical_test_fixture",
            "rows_artifact_name": self.rows_artifact_name,
            "rows_sha256": self.rows_sha256,
            "row_count": self.row_count,
            "bond_row_count": self.bond_row_count,
            "angle_row_count": self.angle_row_count,
            "license_review_status": "not_applicable_nonphysical_fixture",
            "source_authentication_status": "not_authenticated",
            "runtime_eligible": False,
        }


@dataclass(frozen=True)
class ParameterFitSplitManifest:
    split_id: str
    split_version: str
    dataset_id: str
    dataset_version: str
    dataset_manifest_sha256: str
    rows_sha256: str
    split_policy_id: str
    fit_row_ids: tuple[str, ...]
    holdout_row_ids: tuple[str, ...]
    manifest_sha256: str

    def __post_init__(self) -> None:
        for name in (
            "split_id",
            "split_version",
            "dataset_id",
            "dataset_version",
            "split_policy_id",
        ):
            _require_string(name, getattr(self, name))
        for name in (
            "dataset_manifest_sha256",
            "rows_sha256",
            "manifest_sha256",
        ):
            _require_sha256(name, getattr(self, name))
        for name in ("fit_row_ids", "holdout_row_ids"):
            values = getattr(self, name)
            if type(values) is not tuple or not all(
                type(value) is str and value for value in values
            ):
                raise ParameterFitContractError(
                    f"{name} must be a tuple of row IDs"
                )
            if values != tuple(sorted(values)) or len(set(values)) != len(values):
                raise ParameterFitContractError(
                    f"{name} must be unique and sorted"
                )
        if set(self.fit_row_ids) & set(self.holdout_row_ids):
            raise ParameterFitContractError("fit and holdout rows must be disjoint")

    def _core_dict(self) -> dict[str, Any]:
        return {
            "schema_id": PARAMETER_FIT_SPLIT_MANIFEST_SCHEMA_ID,
            "split_id": self.split_id,
            "split_version": self.split_version,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "dataset_manifest_sha256": self.dataset_manifest_sha256,
            "rows_sha256": self.rows_sha256,
            "split_policy_id": self.split_policy_id,
            "fit_row_ids": list(self.fit_row_ids),
            "holdout_row_ids": list(self.holdout_row_ids),
            "artifact_purpose": "contract_fixture_only",
            "runtime_eligible": False,
        }


def _load_rows(data: bytes) -> SyntheticHarmonicFitRows:
    document = _require_exact_keys(_parse_json(data, "fit rows"), _ROWS_KEYS, "rows")
    if document["schema_id"] != SYNTHETIC_HARMONIC_FIT_ROWS_SCHEMA_ID:
        raise ParameterFitContractError("unsupported fit-row schema")
    if document["artifact_purpose"] != "contract_fixture_only":
        raise ParameterFitContractError("fit rows must remain contract fixtures")
    if document["scientific_status"] != "nonphysical_test_fixture":
        raise ParameterFitContractError("fit rows must remain explicitly nonphysical")
    if document["energy_unit"] != "kilojoule_per_mole":
        raise ParameterFitContractError("fit rows require kilojoule_per_mole")
    if type(document["rows"]) is not list:
        raise ParameterFitContractError("rows must be a list")
    rows = tuple(
        SyntheticHarmonicFitRow(**_require_exact_keys(row, _ROW_KEYS, f"rows[{index}]"))
        for index, row in enumerate(document["rows"])
    )
    return SyntheticHarmonicFitRows(
        rows=rows,
        rows_sha256=hashlib.sha256(data).hexdigest(),
    )


def _load_dataset_manifest(
    data: bytes,
    rows: SyntheticHarmonicFitRows,
) -> ParameterFitDatasetManifest:
    document = _require_exact_keys(
        _parse_json(data, "dataset manifest"),
        _DATASET_KEYS,
        "dataset_manifest",
    )
    if document["schema_id"] != PARAMETER_FIT_DATASET_MANIFEST_SCHEMA_ID:
        raise ParameterFitContractError("unsupported dataset-manifest schema")
    fixed = {
        "artifact_purpose": "contract_fixture_only",
        "scientific_status": "nonphysical_test_fixture",
        "license_review_status": "not_applicable_nonphysical_fixture",
        "source_authentication_status": "not_authenticated",
        "runtime_eligible": False,
    }
    if type(document["runtime_eligible"]) is not bool:
        raise ParameterFitContractError(
            "dataset manifest runtime_eligible must be a boolean"
        )
    if any(document[key] != value for key, value in fixed.items()):
        raise ParameterFitContractError("dataset manifest nonpromotion fields changed")
    manifest = ParameterFitDatasetManifest(
        dataset_id=document["dataset_id"],
        dataset_version=document["dataset_version"],
        rows_artifact_name=document["rows_artifact_name"],
        rows_sha256=document["rows_sha256"],
        row_count=document["row_count"],
        bond_row_count=document["bond_row_count"],
        angle_row_count=document["angle_row_count"],
        manifest_sha256=document["manifest_sha256"],
    )
    if manifest.rows_sha256 != rows.rows_sha256:
        raise ParameterFitContractError("dataset manifest rows digest mismatch")
    observed_bond = sum(row.term_kind == "bond" for row in rows.rows)
    observed_angle = sum(row.term_kind == "angle" for row in rows.rows)
    if (
        manifest.row_count != len(rows.rows)
        or manifest.bond_row_count != observed_bond
        or manifest.angle_row_count != observed_angle
    ):
        raise ParameterFitContractError("dataset manifest row counts mismatch")
    if _sha256_document(manifest._core_dict()) != manifest.manifest_sha256:
        raise ParameterFitContractError("dataset manifest self-hash mismatch")
    return manifest


def _load_split_manifest(
    data: bytes,
    rows: SyntheticHarmonicFitRows,
    dataset: ParameterFitDatasetManifest,
) -> ParameterFitSplitManifest:
    document = _require_exact_keys(
        _parse_json(data, "split manifest"),
        _SPLIT_KEYS,
        "split_manifest",
    )
    if document["schema_id"] != PARAMETER_FIT_SPLIT_MANIFEST_SCHEMA_ID:
        raise ParameterFitContractError("unsupported split-manifest schema")
    if document["artifact_purpose"] != "contract_fixture_only" or (
        type(document["runtime_eligible"]) is not bool
        or document["runtime_eligible"]
    ):
        raise ParameterFitContractError("split manifest nonpromotion fields changed")
    for name in ("fit_row_ids", "holdout_row_ids"):
        if type(document[name]) is not list:
            raise ParameterFitContractError(f"{name} must be a list")
    split = ParameterFitSplitManifest(
        split_id=document["split_id"],
        split_version=document["split_version"],
        dataset_id=document["dataset_id"],
        dataset_version=document["dataset_version"],
        dataset_manifest_sha256=document["dataset_manifest_sha256"],
        rows_sha256=document["rows_sha256"],
        split_policy_id=document["split_policy_id"],
        fit_row_ids=tuple(document["fit_row_ids"]),
        holdout_row_ids=tuple(document["holdout_row_ids"]),
        manifest_sha256=document["manifest_sha256"],
    )
    if (
        split.dataset_id != dataset.dataset_id
        or split.dataset_version != dataset.dataset_version
        or split.dataset_manifest_sha256 != dataset.manifest_sha256
        or split.rows_sha256 != rows.rows_sha256
    ):
        raise ParameterFitContractError("split manifest dataset binding mismatch")
    all_ids = set(rows.by_id)
    if set(split.fit_row_ids) | set(split.holdout_row_ids) != all_ids:
        raise ParameterFitContractError(
            "split manifests must cover every row exactly once"
        )
    for kind in ("bond", "angle"):
        fit = [rows.by_id[row_id] for row_id in split.fit_row_ids if rows.by_id[row_id].term_kind == kind]
        holdout = [rows.by_id[row_id] for row_id in split.holdout_row_ids if rows.by_id[row_id].term_kind == kind]
        if len(fit) != 3 or len(holdout) < 1:
            raise ParameterFitContractError(
                "each term kind requires exactly three fit rows and a holdout"
            )
        fit_coordinates = {row.coordinate for row in fit}
        if len(fit_coordinates) != 3 or any(
            row.coordinate in fit_coordinates for row in holdout
        ):
            raise ParameterFitContractError(
                "fit coordinates must be distinct and disjoint from holdout"
            )
    if _sha256_document(split._core_dict()) != split.manifest_sha256:
        raise ParameterFitContractError("split manifest self-hash mismatch")
    return split


def _fit_quadratic(
    rows: tuple[SyntheticHarmonicFitRow, ...],
) -> tuple[Fraction, Fraction, Fraction, Fraction, Fraction]:
    if len(rows) != 3:
        raise ParameterFitContractError("quadratic interpolation requires three rows")
    points = tuple((row.coordinate, row.energy) for row in rows)
    if len({x for x, _ in points}) != 3:
        raise ParameterFitContractError("quadratic coordinates must be distinct")
    a = Fraction(0)
    b = Fraction(0)
    c = Fraction(0)
    for index, (x_i, y_i) in enumerate(points):
        others = [points[j][0] for j in range(3) if j != index]
        x_j, x_k = others
        denominator = (x_i - x_j) * (x_i - x_k)
        a += y_i / denominator
        b -= y_i * (x_j + x_k) / denominator
        c += y_i * x_j * x_k / denominator
    if a <= 0:
        raise ParameterFitContractError("fitted harmonic curvature must be positive")
    if c - b * b / (4 * a) != 0:
        raise ParameterFitContractError(
            "fitted quadratic violates the required zero additive offset"
        )
    equilibrium = -b / (2 * a)
    force_constant = 2 * a
    if equilibrium <= 0 or force_constant <= 0:
        raise ParameterFitContractError("fitted harmonic parameters must be positive")
    return a, b, c, equilibrium, force_constant


def _rows_digest(rows: tuple[SyntheticHarmonicFitRow, ...]) -> str:
    return _sha256_document({"rows": [row.to_dict() for row in rows]})


@dataclass(frozen=True)
class _DerivedSyntheticFit:
    rows: SyntheticHarmonicFitRows
    dataset_manifest: ParameterFitDatasetManifest
    split_manifest: ParameterFitSplitManifest
    fit_rows: tuple[SyntheticHarmonicFitRow, ...]
    holdout_rows: tuple[SyntheticHarmonicFitRow, ...]
    bond_fit: tuple[Fraction, Fraction, Fraction, Fraction, Fraction]
    angle_fit: tuple[Fraction, Fraction, Fraction, Fraction, Fraction]
    bond_parameter: HarmonicBondParameter
    angle_parameter: HarmonicAngleParameter
    parameter_payload_sha256: str
    max_holdout_absolute_residual: Fraction


def _derive_synthetic_fit(
    rows_data: bytes,
    dataset_manifest_data: bytes,
    split_manifest_data: bytes,
    *,
    output_parameter_artifact_schema_version: str = (
        _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
    ),
) -> _DerivedSyntheticFit:
    parameter_constructor_kwargs = _output_parameter_constructor_kwargs(
        output_parameter_artifact_schema_version
    )
    rows = _load_rows(rows_data)
    dataset = _load_dataset_manifest(dataset_manifest_data, rows)
    split = _load_split_manifest(split_manifest_data, rows, dataset)
    fit_rows = tuple(rows.by_id[row_id] for row_id in split.fit_row_ids)
    holdout_rows = tuple(rows.by_id[row_id] for row_id in split.holdout_row_ids)
    bond_rows = tuple(row for row in fit_rows if row.term_kind == "bond")
    angle_rows = tuple(row for row in fit_rows if row.term_kind == "angle")
    bond_fit = _fit_quadratic(bond_rows)
    angle_fit = _fit_quadratic(angle_rows)
    if angle_fit[3] >= _BINARY64_PI:
        raise ParameterFitContractError(
            "fitted angle equilibrium must be strictly between zero and pi radians"
        )

    fits = {"bond": bond_fit, "angle": angle_fit}
    residuals: list[Fraction] = []
    for row in holdout_rows:
        equilibrium = fits[row.term_kind][3]
        force_constant = fits[row.term_kind][4]
        predicted = Fraction(1, 2) * force_constant * (
            row.coordinate - equilibrium
        ) ** 2
        residuals.append(abs(predicted - row.energy))
    max_residual = max(residuals, default=Fraction(0))
    if max_residual != 0:
        raise ParameterFitContractError(
            "synthetic holdout residual must be exactly zero"
        )

    try:
        bond_parameter = HarmonicBondParameter(
            "synthetic_fit_ch_bond",
            _fraction_to_exact_binary64("bond equilibrium", bond_fit[3]),
            _fraction_to_exact_binary64("bond force constant", bond_fit[4]),
        )
        angle_parameter = HarmonicAngleParameter(
            "synthetic_fit_hch_angle",
            _fraction_to_exact_binary64("angle equilibrium", angle_fit[3]),
            _fraction_to_exact_binary64("angle force constant", angle_fit[4]),
        )
        payload_probe = ExactMethaneBondAngleParameterSet(
            parameter_set_id=SYNTHETIC_OUTPUT_PARAMETER_SET_ID,
            parameter_set_version=SYNTHETIC_OUTPUT_PARAMETER_SET_VERSION,
            derivation_status="declared_contract_fixture",
            bond_parameter=bond_parameter,
            angle_parameter=angle_parameter,
            **parameter_constructor_kwargs,
        )
    except ForceFieldParameterContractError as exc:
        raise ParameterFitContractError(
            f"derived harmonic parameter violates the fitting contract: {exc}"
        ) from exc

    return _DerivedSyntheticFit(
        rows=rows,
        dataset_manifest=dataset,
        split_manifest=split,
        fit_rows=fit_rows,
        holdout_rows=holdout_rows,
        bond_fit=bond_fit,
        angle_fit=angle_fit,
        bond_parameter=bond_parameter,
        angle_parameter=angle_parameter,
        parameter_payload_sha256=payload_probe.parameter_payload_sha256,
        max_holdout_absolute_residual=max_residual,
    )


def _validated_dataset_manifest_copy(
    value: Any,
) -> ParameterFitDatasetManifest:
    if type(value) is not ParameterFitDatasetManifest:
        raise ParameterFitContractError(
            "fit receipt dataset_manifest must use the exact manifest type"
        )
    return ParameterFitDatasetManifest(
        dataset_id=value.dataset_id,
        dataset_version=value.dataset_version,
        rows_artifact_name=value.rows_artifact_name,
        rows_sha256=value.rows_sha256,
        row_count=value.row_count,
        bond_row_count=value.bond_row_count,
        angle_row_count=value.angle_row_count,
        manifest_sha256=value.manifest_sha256,
    )


def _validated_split_manifest_copy(
    value: Any,
) -> ParameterFitSplitManifest:
    if type(value) is not ParameterFitSplitManifest:
        raise ParameterFitContractError(
            "fit receipt split_manifest must use the exact manifest type"
        )
    return ParameterFitSplitManifest(
        split_id=value.split_id,
        split_version=value.split_version,
        dataset_id=value.dataset_id,
        dataset_version=value.dataset_version,
        dataset_manifest_sha256=value.dataset_manifest_sha256,
        rows_sha256=value.rows_sha256,
        split_policy_id=value.split_policy_id,
        fit_row_ids=value.fit_row_ids,
        holdout_row_ids=value.holdout_row_ids,
        manifest_sha256=value.manifest_sha256,
    )


def _manifest_structure(
    value: ParameterFitDatasetManifest,
) -> tuple[Any, ...]:
    return (
        value.dataset_id,
        value.dataset_version,
        value.rows_artifact_name,
        value.rows_sha256,
        value.row_count,
        value.bond_row_count,
        value.angle_row_count,
        value.manifest_sha256,
    )


def _split_structure(value: ParameterFitSplitManifest) -> tuple[Any, ...]:
    return (
        value.split_id,
        value.split_version,
        value.dataset_id,
        value.dataset_version,
        value.dataset_manifest_sha256,
        value.rows_sha256,
        value.split_policy_id,
        value.fit_row_ids,
        value.holdout_row_ids,
        value.manifest_sha256,
    )


def _require_exact_string_tuple(name: str, value: Any) -> tuple[str, ...]:
    if type(value) is not tuple or not all(
        type(item) is str and item for item in value
    ):
        raise ParameterFitContractError(
            f"fit receipt {name} must be an exact tuple of exact strings"
        )
    return value


def _require_exact_fraction(name: str, value: Any) -> Fraction:
    if type(value) is not Fraction:
        raise ParameterFitContractError(
            f"fit receipt {name} must be an exact Fraction"
        )
    return value


def _require_exact_fraction_tuple(
    name: str,
    value: Any,
) -> tuple[Fraction, Fraction, Fraction]:
    if (
        type(value) is not tuple
        or len(value) != 3
        or not all(type(item) is Fraction for item in value)
    ):
        raise ParameterFitContractError(
            f"fit receipt {name} must be an exact three-Fraction tuple"
        )
    return value


@dataclass(frozen=True, init=False, slots=True)
class ParameterFitRunReceipt:
    dataset_manifest: ParameterFitDatasetManifest
    split_manifest: ParameterFitSplitManifest
    fit_row_ids: tuple[str, ...]
    holdout_row_ids: tuple[str, ...]
    fit_rows_sha256: str
    holdout_rows_sha256: str
    bond_coefficients: tuple[Fraction, Fraction, Fraction]
    angle_coefficients: tuple[Fraction, Fraction, Fraction]
    bond_equilibrium: Fraction
    bond_force_constant: Fraction
    angle_equilibrium: Fraction
    angle_force_constant: Fraction
    parameter_payload_sha256: str
    max_holdout_absolute_residual: Fraction
    _fit_protocol_json: bytes = field(repr=False, compare=False)
    _rows_data: bytes = field(repr=False, compare=False)
    _dataset_manifest_data: bytes = field(repr=False, compare=False)
    _split_manifest_data: bytes = field(repr=False, compare=False)
    _output_parameter_artifact_schema_version: str = field(
        repr=False,
        compare=False,
    )

    def __init__(
        self,
        *,
        factory_token: object,
        rows_data: bytes,
        dataset_manifest_data: bytes,
        split_manifest_data: bytes,
        output_parameter_artifact_schema_version: str = (
            _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
        ),
    ) -> None:
        if factory_token is not _RECEIPT_FACTORY_TOKEN:
            raise TypeError("ParameterFitRunReceipt is factory-only")
        _, _, protocol_bytes = _output_parameter_contract(
            output_parameter_artifact_schema_version
        )
        derived = _derive_synthetic_fit(
            rows_data,
            dataset_manifest_data,
            split_manifest_data,
            output_parameter_artifact_schema_version=(
                output_parameter_artifact_schema_version
            ),
        )
        bond_fit = derived.bond_fit
        angle_fit = derived.angle_fit
        object.__setattr__(self, "dataset_manifest", derived.dataset_manifest)
        object.__setattr__(self, "split_manifest", derived.split_manifest)
        object.__setattr__(
            self,
            "fit_row_ids",
            tuple(row.row_id for row in derived.fit_rows),
        )
        object.__setattr__(
            self,
            "holdout_row_ids",
            tuple(row.row_id for row in derived.holdout_rows),
        )
        object.__setattr__(self, "fit_rows_sha256", _rows_digest(derived.fit_rows))
        object.__setattr__(
            self,
            "holdout_rows_sha256",
            _rows_digest(derived.holdout_rows),
        )
        object.__setattr__(self, "bond_coefficients", bond_fit[:3])
        object.__setattr__(self, "angle_coefficients", angle_fit[:3])
        object.__setattr__(self, "bond_equilibrium", bond_fit[3])
        object.__setattr__(self, "bond_force_constant", bond_fit[4])
        object.__setattr__(self, "angle_equilibrium", angle_fit[3])
        object.__setattr__(self, "angle_force_constant", angle_fit[4])
        object.__setattr__(
            self,
            "parameter_payload_sha256",
            derived.parameter_payload_sha256,
        )
        object.__setattr__(
            self,
            "max_holdout_absolute_residual",
            derived.max_holdout_absolute_residual,
        )
        object.__setattr__(
            self,
            "_fit_protocol_json",
            protocol_bytes,
        )
        object.__setattr__(self, "_rows_data", rows_data)
        object.__setattr__(self, "_dataset_manifest_data", dataset_manifest_data)
        object.__setattr__(self, "_split_manifest_data", split_manifest_data)
        object.__setattr__(
            self,
            "_output_parameter_artifact_schema_version",
            output_parameter_artifact_schema_version,
        )

    def _validated_stored_structure(self) -> tuple[Any, ...]:
        if type(self._output_parameter_artifact_schema_version) is not str:
            raise ParameterFitContractError(
                "fit receipt output schema version must be an exact string"
            )
        _output_parameter_contract(
            self._output_parameter_artifact_schema_version
        )
        for name in (
            "_fit_protocol_json",
            "_rows_data",
            "_dataset_manifest_data",
            "_split_manifest_data",
        ):
            if type(getattr(self, name)) is not bytes:
                raise ParameterFitContractError(
                    f"fit receipt {name} must be exact bytes"
                )
        dataset_manifest = _validated_dataset_manifest_copy(
            self.dataset_manifest
        )
        split_manifest = _validated_split_manifest_copy(self.split_manifest)
        fit_row_ids = _require_exact_string_tuple(
            "fit_row_ids",
            self.fit_row_ids,
        )
        holdout_row_ids = _require_exact_string_tuple(
            "holdout_row_ids",
            self.holdout_row_ids,
        )
        for name in (
            "fit_rows_sha256",
            "holdout_rows_sha256",
            "parameter_payload_sha256",
        ):
            _require_sha256(name, getattr(self, name))
        bond_coefficients = _require_exact_fraction_tuple(
            "bond_coefficients",
            self.bond_coefficients,
        )
        angle_coefficients = _require_exact_fraction_tuple(
            "angle_coefficients",
            self.angle_coefficients,
        )
        scalar_fractions = tuple(
            _require_exact_fraction(name, getattr(self, name))
            for name in (
                "bond_equilibrium",
                "bond_force_constant",
                "angle_equilibrium",
                "angle_force_constant",
                "max_holdout_absolute_residual",
            )
        )
        return (
            _manifest_structure(dataset_manifest),
            _split_structure(split_manifest),
            fit_row_ids,
            holdout_row_ids,
            self.fit_rows_sha256,
            self.holdout_rows_sha256,
            bond_coefficients,
            angle_coefficients,
            *scalar_fractions[:4],
            self.parameter_payload_sha256,
            scalar_fractions[4],
        )

    def _require_self_consistent(self) -> _DerivedSyntheticFit:
        observed = ParameterFitRunReceipt._validated_stored_structure(self)
        _, _, expected_protocol_bytes = _output_parameter_contract(
            self._output_parameter_artifact_schema_version
        )
        derived = _derive_synthetic_fit(
            self._rows_data,
            self._dataset_manifest_data,
            self._split_manifest_data,
            output_parameter_artifact_schema_version=(
                self._output_parameter_artifact_schema_version
            ),
        )
        expected = (
            _manifest_structure(derived.dataset_manifest),
            _split_structure(derived.split_manifest),
            tuple(row.row_id for row in derived.fit_rows),
            tuple(row.row_id for row in derived.holdout_rows),
            _rows_digest(derived.fit_rows),
            _rows_digest(derived.holdout_rows),
            derived.bond_fit[:3],
            derived.angle_fit[:3],
            derived.bond_fit[3],
            derived.bond_fit[4],
            derived.angle_fit[3],
            derived.angle_fit[4],
            derived.parameter_payload_sha256,
            derived.max_holdout_absolute_residual,
        )
        if observed != expected:
            raise ParameterFitContractError(
                "fit receipt recomputation did not match its stored evidence"
            )
        if (
            self._fit_protocol_json
            != expected_protocol_bytes
            or hashlib.sha256(self._fit_protocol_json).hexdigest()
            != _frozen_protocol_sha256(
                self._output_parameter_artifact_schema_version
            )
        ):
            raise ParameterFitContractError(
                "fit receipt protocol snapshot does not match the frozen protocol"
            )
        return derived

    @property
    def output_parameter_artifact_schema_version(self) -> str:
        ParameterFitRunReceipt._require_self_consistent(self)
        return self._output_parameter_artifact_schema_version

    @property
    def fit_protocol_id(self) -> str:
        ParameterFitRunReceipt._require_self_consistent(self)
        protocol_id = json.loads(self._fit_protocol_json)["protocol_id"]
        if type(protocol_id) is not str:  # pragma: no cover - fixed snapshot
            raise RuntimeError("frozen fit protocol ID must be a string")
        return protocol_id

    @property
    def blockers(self) -> tuple[str, ...]:
        return (
            "nonphysical_synthetic_contract_fixture",
            "dataset_and_receipt_digests_are_not_authentication",
            "code_environment_evidence_missing",
            "scientific_validation_missing",
            "runtime_parameter_use_prohibited",
            "energy_force_minimization_not_authorized",
            "claim_not_authorized",
        )

    def _core_dict(self) -> dict[str, Any]:
        ParameterFitRunReceipt._require_self_consistent(self)
        output_parameter_set_schema_id, _, _ = _output_parameter_contract(
            self._output_parameter_artifact_schema_version
        )
        bond_a, bond_b, bond_c = self.bond_coefficients
        angle_a, angle_b, angle_c = self.angle_coefficients
        return {
            "schema_id": PARAMETER_FIT_RUN_RECEIPT_SCHEMA_ID,
            "fit_run_id": (
                "nonphysical_exact_methane_harmonic_fit_v1"
                if self._output_parameter_artifact_schema_version
                == _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
                else "nonphysical_exact_methane_harmonic_fit_form_bound_v1_1"
            ),
            "dataset_id": self.dataset_manifest.dataset_id,
            "dataset_version": self.dataset_manifest.dataset_version,
            "dataset_manifest_sha256": self.dataset_manifest.manifest_sha256,
            "rows_sha256": self.dataset_manifest.rows_sha256,
            "split_id": self.split_manifest.split_id,
            "split_version": self.split_manifest.split_version,
            "split_manifest_sha256": self.split_manifest.manifest_sha256,
            "fit_protocol": json.loads(self._fit_protocol_json),
            "fit_protocol_sha256": hashlib.sha256(
                self._fit_protocol_json
            ).hexdigest(),
            "fit_row_ids": list(self.fit_row_ids),
            "holdout_row_ids": list(self.holdout_row_ids),
            "fit_rows_sha256": self.fit_rows_sha256,
            "holdout_rows_sha256": self.holdout_rows_sha256,
            "bond_quadratic_coefficients": {
                "a": _fraction_document(bond_a),
                "b": _fraction_document(bond_b),
                "c": _fraction_document(bond_c),
            },
            "angle_quadratic_coefficients": {
                "a": _fraction_document(angle_a),
                "b": _fraction_document(angle_b),
                "c": _fraction_document(angle_c),
            },
            "bond_equilibrium_exact": _fraction_document(self.bond_equilibrium),
            "bond_force_constant_exact": _fraction_document(self.bond_force_constant),
            "angle_equilibrium_exact": _fraction_document(self.angle_equilibrium),
            "angle_force_constant_exact": _fraction_document(self.angle_force_constant),
            "bond_equilibrium_ieee754_binary64_be": _binary64_hex(_fraction_to_exact_binary64("bond equilibrium", self.bond_equilibrium)),
            "bond_force_constant_ieee754_binary64_be": _binary64_hex(_fraction_to_exact_binary64("bond force constant", self.bond_force_constant)),
            "angle_equilibrium_ieee754_binary64_be": _binary64_hex(_fraction_to_exact_binary64("angle equilibrium", self.angle_equilibrium)),
            "angle_force_constant_ieee754_binary64_be": _binary64_hex(_fraction_to_exact_binary64("angle force constant", self.angle_force_constant)),
            "output_parameter_set_schema_id": output_parameter_set_schema_id,
            "output_parameter_set_id": SYNTHETIC_OUTPUT_PARAMETER_SET_ID,
            "output_parameter_set_version": SYNTHETIC_OUTPUT_PARAMETER_SET_VERSION,
            "output_parameter_payload_sha256": self.parameter_payload_sha256,
            "fit_execution_status": "succeeded",
            "arithmetic_recomputation_status": "matched",
            "termination_status": "exact_solution",
            "quadratic_solve_count": 2,
            "max_holdout_absolute_residual_exact": _fraction_document(self.max_holdout_absolute_residual),
            "artifact_purpose": "contract_fixture_only",
            "scientific_status": "nonphysical_test_fixture",
            "fit_evidence_review_status": "not_applicable",
            "scientific_validation_status": "missing",
            "source_authentication_status": "not_authenticated",
            "runtime_authorization_status": "prohibited",
            "code_environment_evidence_status": "missing",
            "blockers": list(self.blockers),
        }

    @property
    def receipt_sha256(self) -> str:
        return _sha256_document(ParameterFitRunReceipt._core_dict(self))

    def to_dict(self) -> dict[str, Any]:
        payload = ParameterFitRunReceipt._core_dict(self)
        payload["receipt_sha256"] = self.receipt_sha256
        return payload


@dataclass(frozen=True, slots=True)
class SyntheticParameterFitBundle:
    parameter_set: ExactMethaneBondAngleParameterSet
    receipt: ParameterFitRunReceipt

    def __post_init__(self) -> None:
        SyntheticParameterFitBundle._require_self_consistent(self)

    def _require_self_consistent(
        self,
    ) -> ExactMethaneBondAngleParameterSet:
        if type(self.parameter_set) is not ExactMethaneBondAngleParameterSet:
            raise TypeError("parameter_set must be an exact methane parameter set")
        if type(self.receipt) is not ParameterFitRunReceipt:
            raise TypeError("receipt must be a ParameterFitRunReceipt")
        validated_parameter_set = (
            ExactMethaneBondAngleParameterSet._validated_copy(
                self.parameter_set
            )
        )
        derived = ParameterFitRunReceipt._require_self_consistent(self.receipt)
        parameter_constructor_kwargs = _output_parameter_constructor_kwargs(
            self.receipt._output_parameter_artifact_schema_version
        )
        expected_parameter_set = ExactMethaneBondAngleParameterSet(
            parameter_set_id=SYNTHETIC_OUTPUT_PARAMETER_SET_ID,
            parameter_set_version=SYNTHETIC_OUTPUT_PARAMETER_SET_VERSION,
            derivation_status="declared_fit_candidate_unverified",
            bond_parameter=derived.bond_parameter,
            angle_parameter=derived.angle_parameter,
            dataset_manifest_sha256=derived.dataset_manifest.manifest_sha256,
            split_manifest_sha256=derived.split_manifest.manifest_sha256,
            fit_protocol_id=self.receipt.fit_protocol_id,
            fit_receipt_sha256=self.receipt.receipt_sha256,
            **parameter_constructor_kwargs,
        )
        if (
            ExactMethaneBondAngleParameterSet.to_dict(
                validated_parameter_set
            )
            != ExactMethaneBondAngleParameterSet.to_dict(
                expected_parameter_set
            )
            or validated_parameter_set.parameter_payload_sha256
            != self.receipt.parameter_payload_sha256
        ):
            raise ParameterFitContractError("fit bundle hash binding mismatch")
        return expected_parameter_set

    @property
    def bundle_sha256(self) -> str:
        expected_parameter_set = (
            SyntheticParameterFitBundle._require_self_consistent(self)
        )
        return _sha256_document(
            {
                "parameter_set_sha256": (
                    expected_parameter_set.parameter_set_sha256
                ),
                "receipt_sha256": self.receipt.receipt_sha256,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        expected_parameter_set = (
            SyntheticParameterFitBundle._require_self_consistent(self)
        )
        return {
            "verification_status": "recomputed_nonphysical_fixture_match",
            "parameter_set": expected_parameter_set.to_dict(),
            "fit_receipt": ParameterFitRunReceipt.to_dict(self.receipt),
            "parameterability_assessed": False,
            "parameterizable": False,
            "runtime_eligible": False,
            "execution_authorized": False,
            "energy_evaluation_authorized": False,
            "force_evaluation_authorized": False,
            "minimization_authorized": False,
            "simulation_ready": False,
            "claim_safe": False,
            "bundle_sha256": self.bundle_sha256,
        }


def run_synthetic_exact_methane_harmonic_fit(
    rows_data: bytes,
    dataset_manifest_data: bytes,
    split_manifest_data: bytes,
    *,
    output_parameter_artifact_schema_version: str = (
        _FROZEN_LEGACY_OUTPUT_PARAMETER_SCHEMA_VERSION
    ),
) -> SyntheticParameterFitBundle:
    """Recompute a nonphysical exact-methane bond/angle fit and receipt."""

    receipt = ParameterFitRunReceipt(
        factory_token=_RECEIPT_FACTORY_TOKEN,
        rows_data=rows_data,
        dataset_manifest_data=dataset_manifest_data,
        split_manifest_data=split_manifest_data,
        output_parameter_artifact_schema_version=(
            output_parameter_artifact_schema_version
        ),
    )
    derived = ParameterFitRunReceipt._require_self_consistent(receipt)
    parameter_constructor_kwargs = _output_parameter_constructor_kwargs(
        output_parameter_artifact_schema_version
    )
    parameter_set = ExactMethaneBondAngleParameterSet(
        parameter_set_id=SYNTHETIC_OUTPUT_PARAMETER_SET_ID,
        parameter_set_version=SYNTHETIC_OUTPUT_PARAMETER_SET_VERSION,
        derivation_status="declared_fit_candidate_unverified",
        bond_parameter=derived.bond_parameter,
        angle_parameter=derived.angle_parameter,
        dataset_manifest_sha256=derived.dataset_manifest.manifest_sha256,
        split_manifest_sha256=derived.split_manifest.manifest_sha256,
        fit_protocol_id=receipt.fit_protocol_id,
        fit_receipt_sha256=receipt.receipt_sha256,
        **parameter_constructor_kwargs,
    )
    if parameter_set.parameter_payload_sha256 != receipt.parameter_payload_sha256:
        raise ParameterFitContractError("fit output payload digest mismatch")
    return SyntheticParameterFitBundle(parameter_set, receipt)


def serialize_parameter_fit_run_receipt(receipt: ParameterFitRunReceipt) -> bytes:
    if type(receipt) is not ParameterFitRunReceipt:
        raise TypeError("receipt must be a ParameterFitRunReceipt")
    return _canonical_json_bytes(ParameterFitRunReceipt.to_dict(receipt))


__all__ = [
    "PARAMETER_FIT_DATASET_MANIFEST_SCHEMA_ID",
    "PARAMETER_FIT_RUN_RECEIPT_SCHEMA_ID",
    "PARAMETER_FIT_SPLIT_MANIFEST_SCHEMA_ID",
    "SYNTHETIC_HARMONIC_ARITHMETIC_POLICY_ID",
    "SYNTHETIC_HARMONIC_FIT_ALGORITHM_ID",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_ID_1_1",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_SCHEMA_ID_1_1",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256",
    "SYNTHETIC_HARMONIC_FIT_PROTOCOL_SHA256_1_1",
    "SYNTHETIC_HARMONIC_FIT_ROWS_SCHEMA_ID",
    "SYNTHETIC_HARMONIC_OBJECTIVE_ID",
    "ParameterFitContractError",
    "ParameterFitDatasetManifest",
    "ParameterFitRunReceipt",
    "ParameterFitSplitManifest",
    "SyntheticHarmonicFitRow",
    "SyntheticHarmonicFitRows",
    "SyntheticParameterFitBundle",
    "run_synthetic_exact_methane_harmonic_fit",
    "serialize_parameter_fit_run_receipt",
]
