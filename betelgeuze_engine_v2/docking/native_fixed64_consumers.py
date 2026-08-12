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
_COMPLETE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/1.0.0"
)

_RECEIPT_GRAPH_FIELDS = (
    "allocation_inventory_sha256",
    "allocation_receipt_sha256",
    "source_bundle_receipt_sha256",
    "geometric_admission_batch_receipt_sha256",
    "admission_context_receipt_sha256",
    "refinement_context_receipt_sha256",
    "scorer_context_receipt_sha256",
    "validity_context_receipt_sha256",
    "component_binding_receipt_sha256",
    "producer_batch_receipt_sha256",
    "refinement_policy_receipt_sha256",
    "refinement_batch_receipt_sha256",
    "scorer_batch_receipt_sha256",
    "validity_batch_receipt_sha256",
    "ranking_batch_receipt_sha256",
    "cluster_batch_receipt_sha256",
    "pipeline_batch_receipt_sha256",
)

_RECEIPT_GRAPH_ALIASES = {
    "allocation_receipt_sha256": "allocation_receipt_sha256",
    "proposal_batch_receipt_sha256": "producer_batch_receipt_sha256",
    "geometric_admission_receipt_sha256": (
        "geometric_admission_batch_receipt_sha256"
    ),
    "scorer_receipt_sha256": "scorer_batch_receipt_sha256",
    "validity_receipt_sha256": "validity_batch_receipt_sha256",
    "ranking_receipt_sha256": "ranking_batch_receipt_sha256",
    "pipeline_receipt_sha256": "pipeline_batch_receipt_sha256",
}


def _freeze(value: object) -> object:
    if type(value) is dict:
        return MappingProxyType(
            {str(key): _freeze(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_thaw(item) for item in value]
    return value


def _native_entrypoint():
    try:
        module = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise NativeFixed64ConsumerError(
            "native fixed64 extension is required; Python fallback is forbidden"
        ) from exc
    name = "native_fixed64_complete_pipeline_v1"
    entrypoint = getattr(module, name, None)
    if not callable(entrypoint):
        raise NativeFixed64ConsumerError(
            f"native fixed64 extension lacks the versioned entrypoint {name}"
        )
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
        schema_id = document.get("schema_id")
        candidates = document.get("candidates")
        if (
            schema_id != _COMPLETE_EVIDENCE_SCHEMA_ID
            or document.get("consumer") != self.surface
            or document.get("backend")
            not in {"cpp_cpu_reference", "rust_cpu", "hip_safe", "hip_fast"}
            or document.get("candidate_denominator") != 64
            or not isinstance(candidates, (list, tuple))
            or len(candidates) != 64
            or document.get("evidence_display_authorized") is not True
            or document.get("operator_second_opinion_authorized")
            is not (self.surface == "product_shadow")
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 consumer evidence is cross-wired"
            )
        for slot_index, candidate in enumerate(candidates):
            observed_slot = (
                candidate.get("slot_index") if isinstance(candidate, Mapping) else None
            )
            if type(observed_slot) is not int or observed_slot != slot_index:
                raise NativeFixed64ConsumerError(
                    "native fixed64 candidate denominator is reordered or incomplete"
                )
        for field in (
            "reservation_authorized",
            "molecular_execution_authorized",
            "existing_rank_auto_change_authorized",
            "customer_pose_emission_authorized",
            "production_claim_authorized",
        ):
            if document.get(field) is not False:
                raise NativeFixed64ConsumerError(
                    f"native fixed64 authority field {field} changed"
                )
        for field in (
            "result_dependent_input_consumed",
            "fallback_allowed",
            "multi_anchor_consumed",
            "benchmark_execution_authorized",
            "scientific_claim_authorized",
        ):
            if document.get(field) is not False:
                raise NativeFixed64ConsumerError(
                    f"native fixed64 authority field {field} changed"
                )
        if document.get("denominator_preserved") is not True:
            raise NativeFixed64ConsumerError(
                "native fixed64 denominator preservation changed"
            )
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
                raise NativeFixed64ConsumerError(
                    f"native fixed64 receipt field {field} is invalid"
                )
        receipt_graph = document.get("receipt_graph")
        if (
            not isinstance(receipt_graph, Mapping)
            or len(receipt_graph) != len(_RECEIPT_GRAPH_FIELDS)
            or set(receipt_graph) != set(_RECEIPT_GRAPH_FIELDS)
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 receipt graph is incomplete or cross-wired"
            )
        for field in _RECEIPT_GRAPH_FIELDS:
            value = receipt_graph.get(field)
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise NativeFixed64ConsumerError(
                    f"native fixed64 receipt graph field {field} is invalid"
                )
        for public_field, graph_field in _RECEIPT_GRAPH_ALIASES.items():
            if document.get(public_field) != receipt_graph.get(graph_field):
                raise NativeFixed64ConsumerError(
                    "native fixed64 public receipt aliases are cross-wired"
                )
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
    if payload.get("schema_id") != _COMPLETE_INPUT_SCHEMA_ID:
        raise NativeFixed64ConsumerError(
            "canonical consumers require the complete fixed64 input schema"
        )
    entrypoint = _native_entrypoint()
    try:
        result = entrypoint(payload)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    if type(result) is not dict:
        raise NativeFixed64ConsumerError(
            "native fixed64 entrypoint returned a non-dict result"
        )
    if result.get("backend") != payload.get("backend"):
        raise NativeFixed64ConsumerError(
            "native fixed64 evidence does not match the requested backend"
        )
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
