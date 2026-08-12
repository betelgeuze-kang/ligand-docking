"""Thin, claim-blocked consumers over the native Rust fixed64 pipeline.

This module performs no molecular geometry, scoring, validity, or ranking work.
It only selects a consumer surface, calls the one native entrypoint, and checks
that the returned permission boundary remains fail-closed.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import importlib
from types import MappingProxyType
from typing import Literal, Mapping


NativeFixed64Surface = Literal["cli", "benchmark", "api", "product_shadow"]


class NativeFixed64ConsumerError(RuntimeError):
    """The native fixed64 bridge or its authority boundary failed closed."""


_COMPLETE_INPUT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_complete_input/1.0.0"
_COMPLETE_EVIDENCE_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/1.0.0"
_COMPATIBILITY_INPUT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_exact_source_input/1.0.0"
_COMPATIBILITY_EVIDENCE_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_python_evidence/1.0.0"


def _freeze(value: object) -> object:
    if type(value) is dict:
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


def _native_entrypoint(input_schema_id: object):
    try:
        module = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise NativeFixed64ConsumerError("native fixed64 extension is required; Python fallback is forbidden") from exc
    if input_schema_id == _COMPLETE_INPUT_SCHEMA_ID:
        name = "native_fixed64_complete_pipeline_v1"
    elif input_schema_id == _COMPATIBILITY_INPUT_SCHEMA_ID:
        name = "native_fixed64_exact_source_pipeline_v1"
    else:
        raise NativeFixed64ConsumerError("native fixed64 input schema is unsupported")
    entrypoint = getattr(module, name, None)
    if not callable(entrypoint):
        raise NativeFixed64ConsumerError(f"native fixed64 extension lacks the versioned entrypoint {name}")
    return entrypoint


@dataclass(frozen=True, slots=True)
class NativeFixed64EvidenceV1:
    """Immutable view of one self-verified native pipeline/consumer receipt."""

    surface: NativeFixed64Surface
    _document: Mapping[str, object]

    def __post_init__(self) -> None:
        if self.surface not in {"cli", "benchmark", "api", "product_shadow"}:
            raise NativeFixed64ConsumerError("native consumer surface is unsupported")
        if not isinstance(self._document, Mapping):
            raise TypeError("native evidence must be a mapping")
        document = self._document
        if (
            document.get("schema_id")
            not in {
                _COMPLETE_EVIDENCE_SCHEMA_ID,
                _COMPATIBILITY_EVIDENCE_SCHEMA_ID,
            }
            or document.get("consumer") != self.surface
            or document.get("candidate_denominator") != 64
            or not isinstance(document.get("candidates"), (list, tuple))
            or len(document["candidates"]) != 64  # type: ignore[arg-type]
            or document.get("evidence_display_authorized") is not True
            or document.get("operator_second_opinion_authorized") is not (self.surface == "product_shadow")
        ):
            raise NativeFixed64ConsumerError("native fixed64 consumer evidence is cross-wired")
        for field in (
            "reservation_authorized",
            "molecular_execution_authorized",
            "existing_rank_auto_change_authorized",
            "customer_pose_emission_authorized",
            "production_claim_authorized",
        ):
            if document.get(field) is not False:
                raise NativeFixed64ConsumerError(f"native fixed64 authority field {field} changed")
        for field in (
            "pipeline_receipt_sha256",
            "consumer_view_receipt_sha256",
            "allocation_receipt_sha256",
            "proposal_batch_receipt_sha256",
            "geometric_admission_receipt_sha256",
            "scorer_receipt_sha256",
            "validity_receipt_sha256",
            "ranking_receipt_sha256",
        ):
            value = document.get(field)
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise NativeFixed64ConsumerError(f"native fixed64 receipt field {field} is invalid")
        object.__setattr__(self, "_document", _freeze(dict(document)))

    @property
    def pipeline_receipt_sha256(self) -> str:
        return str(self._document["pipeline_receipt_sha256"])

    @property
    def consumer_view_receipt_sha256(self) -> str:
        return str(self._document["consumer_view_receipt_sha256"])

    def to_dict(self) -> dict[str, object]:
        value = _thaw(self._document)
        if type(value) is not dict:
            raise NativeFixed64ConsumerError("native evidence thaw failed")
        return value


def run_native_fixed64_surface(
    input_document: Mapping[str, object],
    *,
    surface: NativeFixed64Surface,
) -> NativeFixed64EvidenceV1:
    """Run one surface through the exact same Rust receipt core."""

    if type(input_document) is not dict:
        raise TypeError("native fixed64 input must be an exact dict")
    if surface not in {"cli", "benchmark", "api", "product_shadow"}:
        raise NativeFixed64ConsumerError("native consumer surface is unsupported")
    payload = deepcopy(input_document)
    payload["consumer"] = surface
    entrypoint = _native_entrypoint(payload.get("schema_id"))
    try:
        result = entrypoint(payload)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    if type(result) is not dict:
        raise NativeFixed64ConsumerError("native fixed64 entrypoint returned a non-dict result")
    return NativeFixed64EvidenceV1(surface=surface, _document=result)


class NativeFixed64CliAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV1:
        return run_native_fixed64_surface(input_document, surface="cli")


class NativeFixed64DiagnosticBenchmarkAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV1:
        return run_native_fixed64_surface(input_document, surface="benchmark")


class NativeFixed64PythonApi:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV1:
        return run_native_fixed64_surface(input_document, surface="api")


class NativeFixed64ProductShadowAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV1:
        return run_native_fixed64_surface(input_document, surface="product_shadow")


__all__ = [
    "NativeFixed64CliAdapter",
    "NativeFixed64ConsumerError",
    "NativeFixed64DiagnosticBenchmarkAdapter",
    "NativeFixed64EvidenceV1",
    "NativeFixed64ProductShadowAdapter",
    "NativeFixed64PythonApi",
    "NativeFixed64Surface",
    "run_native_fixed64_surface",
]
