"""Thin, claim-blocked consumers over the native Rust fixed64 pipeline.

This module performs no molecular geometry, scoring, validity, or ranking work.
It only selects a consumer surface, calls the one native entrypoint, and checks
that the returned permission boundary remains fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
from types import MappingProxyType
from typing import ClassVar, Literal, Mapping, cast


NativeFixed64Surface = Literal["cli", "benchmark", "api", "product_shadow"]


class NativeFixed64ConsumerError(RuntimeError):
    """The native fixed64 bridge or its authority boundary failed closed."""


_COMPLETE_INPUT_SCHEMA_ID_V2 = (
    "betelgeuze.engine_v2_native_fixed64_complete_input/2.0.0"
)
_COMPLETE_EVIDENCE_SCHEMA_ID_V2 = (
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/2.0.0"
)
_COMPLETE_INPUT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"
_COMPLETE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/3.0.0"
)
_PREPARED_INPUT_RECEIPT_DOMAIN = (
    b"betelgeuze.engine-v2.native-fixed64-prepared-input-receipt/v1\0"
)
_PREPARED_SESSION_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_prepared_session/1.0.0"
)
_PREPARED_SESSION_RECEIPT_DOMAIN = (
    b"betelgeuze.engine-v2.native-fixed64-prepared-session/v1\0"
)
_NATIVE_FIXED64_PIPELINE_ID = (
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
)
_PREPARED_INPUT_SCALAR_LIMIT = 8 * 1_024 * 1_024
# Versioned v3 transport schema cardinality.  Bound the outer mapping before
# making even a shallow transport copy; Rust then validates the exact key set
# and bounds every nested collection before copying its values.
_COMPLETE_INPUT_KEY_COUNT = 53

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
    "post_admission_policy_receipt_sha256",
    "post_admission_batch_receipt_sha256",
    "scorer_batch_receipt_sha256",
    "validity_batch_receipt_sha256",
    "ranking_batch_receipt_sha256",
    "cluster_batch_receipt_sha256",
    "pipeline_batch_receipt_sha256",
)

_RECEIPT_GRAPH_ALIASES = {
    "allocation_receipt_sha256": "allocation_receipt_sha256",
    "proposal_batch_receipt_sha256": "producer_batch_receipt_sha256",
    "geometric_admission_receipt_sha256": ("geometric_admission_batch_receipt_sha256"),
    "post_refinement_admission_receipt_sha256": ("post_admission_batch_receipt_sha256"),
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
    name = "native_fixed64_complete_pipeline_v3"
    entrypoint = getattr(module, name, None)
    if not callable(entrypoint):
        raise NativeFixed64ConsumerError(
            f"native fixed64 extension lacks the versioned entrypoint {name}"
        )
    return entrypoint


def _native_session_entrypoint():
    try:
        module = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise NativeFixed64ConsumerError(
            "native fixed64 extension is required; Python fallback is forbidden"
        ) from exc
    name = "native_fixed64_prepare_session_v1"
    entrypoint = getattr(module, name, None)
    if not callable(entrypoint):
        raise NativeFixed64ConsumerError(
            f"native fixed64 extension lacks the versioned entrypoint {name}"
        )
    return entrypoint


@dataclass(frozen=True, slots=True)
class NativeFixed64EvidenceV2:
    """Immutable compatibility view of one v2 native pipeline receipt."""

    _EXPECTED_SCHEMA_ID: ClassVar[str] = _COMPLETE_EVIDENCE_SCHEMA_ID_V2

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
            schema_id != self._EXPECTED_SCHEMA_ID
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
            post_admission = candidate.get("post_refinement_geometric_admission")
            ranking = candidate.get("ranking")
            lineage = candidate.get("lineage")
            if (
                not isinstance(post_admission, Mapping)
                or type(post_admission.get("rank_eligible")) is not bool
                or not isinstance(ranking, Mapping)
                or type(ranking.get("rank_eligible")) is not bool
                or type(ranking.get("valid_rank_eligible")) is not bool
                or not isinstance(lineage, Mapping)
                or lineage.get("post_admission_row_receipt_sha256")
                != post_admission.get("receipt_sha256")
            ):
                raise NativeFixed64ConsumerError(
                    "native fixed64 post-refinement admission evidence is cross-wired"
                )
            if post_admission.get("rank_eligible") is False and (
                ranking.get("rank_eligible") is not False
                or ranking.get("valid_rank_eligible") is not False
            ):
                raise NativeFixed64ConsumerError(
                    "post-refinement rejected candidate remained rank eligible"
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
        counts = {
            field: document.get(field)
            for field in (
                "generated_count",
                "typed_failure_count",
                "initial_admitted_count",
                "refined_count",
                "post_admitted_count",
                "post_rejected_count",
                "scored_count",
                "valid_count",
                "cluster_count",
            )
        }
        if any(
            type(value) is not int or not 0 <= value <= 64 for value in counts.values()
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 denominator counts are invalid"
            )
        if (
            counts["generated_count"] + counts["typed_failure_count"] != 64
            or counts["initial_admitted_count"] > counts["generated_count"]
            or counts["refined_count"] > counts["initial_admitted_count"]
            or counts["post_admitted_count"] + counts["post_rejected_count"]
            != counts["refined_count"]
            or counts["scored_count"] > counts["post_admitted_count"]
            or counts["valid_count"] > counts["scored_count"]
            or counts["cluster_count"] > counts["valid_count"]
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 denominator counts are cross-wired"
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
            "post_refinement_admission_receipt_sha256",
            "scorer_receipt_sha256",
            "validity_receipt_sha256",
            "ranking_receipt_sha256",
            "scientific_projection_sha256",
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


class NativeFixed64EvidenceV3(NativeFixed64EvidenceV2):
    """Immutable bounded prepared-input and native pipeline receipt view."""

    __slots__ = ()
    _EXPECTED_SCHEMA_ID: ClassVar[str] = _COMPLETE_EVIDENCE_SCHEMA_ID

    def __post_init__(self) -> None:
        super().__post_init__()
        document = self._document
        projection = document.get("prepared_input_projection_sha256")
        prepared_receipt = document.get("prepared_input_receipt_sha256")
        pipeline_receipt = document.get("pipeline_receipt_sha256")
        if document.get("prepared_input_bounded") is not True:
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared input is not bounded"
            )
        for field, value in (
            ("prepared_input_projection_sha256", projection),
            ("prepared_input_receipt_sha256", prepared_receipt),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise NativeFixed64ConsumerError(
                    f"native fixed64 receipt field {field} is invalid"
                )
        ligand_count = document.get("ligand_atom_count")
        receptor_count = document.get("receptor_atom_count")
        exact_pair_count = document.get("exact_cartesian_pair_count")
        scalar_count = document.get("prepared_input_scalar_count")
        scalar_limit = document.get("prepared_input_scalar_limit")
        if (
            type(ligand_count) is not int
            or not 1 <= ligand_count <= 512
            or type(receptor_count) is not int
            or not 1 <= receptor_count <= 4096
            or type(exact_pair_count) is not int
            or exact_pair_count != ligand_count * receptor_count
            or type(scalar_count) is not int
            or not 0 < scalar_count <= _PREPARED_INPUT_SCALAR_LIMIT
            or scalar_limit != _PREPARED_INPUT_SCALAR_LIMIT
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-input bounds are cross-wired"
            )
        expected_receipt = hashlib.sha256(
            _PREPARED_INPUT_RECEIPT_DOMAIN
            + bytes.fromhex(str(projection))
            + bytes.fromhex(str(pipeline_receipt))
        ).hexdigest()
        if prepared_receipt != expected_receipt:
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-input receipt is cross-wired"
            )

    @property
    def prepared_input_receipt_sha256(self) -> str:
        return str(self._document["prepared_input_receipt_sha256"])


@dataclass(frozen=True, slots=True)
class NativeFixed64PreparedSessionV1:
    """Thread-confined owner of one bounded native fixed64 prepared context."""

    _native_session: object
    _metadata: Mapping[str, object]
    _backend: str
    _default_consumer: NativeFixed64Surface

    def __post_init__(self) -> None:
        metadata = self._metadata
        if type(metadata) is not dict:
            raise TypeError("native prepared-session metadata must be an exact dict")
        if type(self._backend) is not str or type(self._default_consumer) is not str:
            raise TypeError("native prepared-session identities must be exact strings")
        pipeline_id = metadata.get("pipeline_id")
        projection = metadata.get("prepared_input_projection_sha256")
        session_receipt = metadata.get("prepared_session_receipt_sha256")
        default_consumer = metadata.get("default_consumer")
        metadata_backend = metadata.get("backend")
        schema_id = metadata.get("schema_id")
        ligand_count = metadata.get("ligand_atom_count")
        receptor_count = metadata.get("receptor_atom_count")
        exact_pair_count = metadata.get("exact_cartesian_pair_count")
        scalar_count = metadata.get("prepared_input_scalar_count")
        if any(
            type(value) is not str
            for value in (schema_id, pipeline_id, default_consumer, metadata_backend)
        ):
            raise TypeError(
                "native prepared-session metadata identities must be exact strings"
            )
        if (
            schema_id != _PREPARED_SESSION_SCHEMA_ID
            or pipeline_id != _NATIVE_FIXED64_PIPELINE_ID
            or default_consumer != self._default_consumer
            or metadata_backend != self._backend
            or self._backend not in {"cpp_cpu_reference", "rust_cpu"}
            or metadata.get("candidate_denominator") != 64
            or metadata.get("test_only") is not True
            or metadata.get("persistent_native_context") is not True
            or metadata.get("context_reused_across_runs") is not True
            or metadata.get("scientific_result_cached") is not False
            or metadata.get("session_thread_confined") is not True
            or metadata.get("result_dependent_input_consumed") is not False
            or type(ligand_count) is not int
            or not 1 <= ligand_count <= 512
            or type(receptor_count) is not int
            or not 1 <= receptor_count <= 4096
            or type(exact_pair_count) is not int
            or exact_pair_count != ligand_count * receptor_count
            or type(scalar_count) is not int
            or not 0 < scalar_count <= _PREPARED_INPUT_SCALAR_LIMIT
            or metadata.get("prepared_input_scalar_limit")
            != _PREPARED_INPUT_SCALAR_LIMIT
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-session metadata is cross-wired"
            )
        for field in (
            "reservation_authorized",
            "molecular_execution_authorized",
            "benchmark_execution_authorized",
            "scientific_claim_authorized",
            "hip_device_execution_authorized",
            "existing_rank_auto_change_authorized",
            "customer_pose_emission_authorized",
            "production_claim_authorized",
        ):
            if metadata.get(field) is not False:
                raise NativeFixed64ConsumerError(
                    f"native fixed64 prepared-session authority field {field} changed"
                )
        for field, value in (
            ("prepared_input_projection_sha256", projection),
            ("prepared_session_receipt_sha256", session_receipt),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise NativeFixed64ConsumerError(
                    f"native fixed64 prepared-session field {field} is invalid"
                )
        expected_receipt = hashlib.sha256(
            _PREPARED_SESSION_RECEIPT_DOMAIN
            + len(_NATIVE_FIXED64_PIPELINE_ID).to_bytes(8, "big")
            + _NATIVE_FIXED64_PIPELINE_ID.encode("ascii")
            + bytes.fromhex(str(projection))
        ).hexdigest()
        if session_receipt != expected_receipt:
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-session receipt is cross-wired"
            )
        if not callable(getattr(self._native_session, "run", None)):
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-session runner is unavailable"
            )
        object.__setattr__(self, "_metadata", _freeze(dict(metadata)))

    @property
    def prepared_input_projection_sha256(self) -> str:
        return str(self._metadata["prepared_input_projection_sha256"])

    @property
    def prepared_session_receipt_sha256(self) -> str:
        return str(self._metadata["prepared_session_receipt_sha256"])

    def describe(self) -> dict[str, object]:
        value = _thaw(self._metadata)
        if type(value) is not dict:
            raise NativeFixed64ConsumerError("native prepared-session thaw failed")
        return value

    def run(self, *, surface: NativeFixed64Surface) -> NativeFixed64EvidenceV3:
        if type(surface) is not str or surface not in {
            "cli",
            "benchmark",
            "api",
            "product_shadow",
        }:
            raise NativeFixed64ConsumerError("native consumer surface is unsupported")
        try:
            result = self._native_session.run(surface)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise NativeFixed64ConsumerError(str(exc)) from exc
        if type(result) is not dict:
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared session returned a non-dict result"
            )
        if (
            result.get("backend") != self._backend
            or result.get("prepared_input_projection_sha256")
            != self.prepared_input_projection_sha256
        ):
            raise NativeFixed64ConsumerError(
                "native fixed64 prepared-session result is cross-wired"
            )
        return NativeFixed64EvidenceV3(surface=surface, _document=result)


# Import compatibility only. The alias validates and represents the v2 schema;
# it does not admit or reinterpret retired v1 evidence.
NativeFixed64EvidenceV1 = NativeFixed64EvidenceV2


def _bounded_native_payload(
    input_document: Mapping[str, object],
    *,
    surface: NativeFixed64Surface,
) -> dict[str, object]:
    if type(input_document) is not dict:
        raise TypeError("native fixed64 input must be an exact dict")
    if len(input_document) != _COMPLETE_INPUT_KEY_COUNT:
        raise NativeFixed64ConsumerError(
            "canonical consumers require the complete fixed64 input schema: "
            "invalid top-level key count"
        )
    if type(surface) is not str or surface not in {
        "cli",
        "benchmark",
        "api",
        "product_shadow",
    }:
        raise NativeFixed64ConsumerError("native consumer surface is unsupported")
    # Do not deepcopy caller-owned nested collections before the native bounded
    # preflight. Rust copies every admitted collection into owned native state.
    payload = input_document.copy()
    payload["consumer"] = surface
    if payload.get("schema_id") != _COMPLETE_INPUT_SCHEMA_ID:
        raise NativeFixed64ConsumerError(
            "canonical consumers require the complete fixed64 input schema"
        )
    return payload


def prepare_native_fixed64_session(
    input_document: Mapping[str, object],
) -> NativeFixed64PreparedSessionV1:
    """Prepare one persistent native context without granting run authority."""

    if type(input_document) is not dict:
        raise TypeError("native fixed64 input must be an exact dict")
    surface = input_document.get("consumer")
    if type(surface) is not str or surface not in {
        "cli",
        "benchmark",
        "api",
        "product_shadow",
    }:
        raise NativeFixed64ConsumerError("native consumer surface is unsupported")
    surface = cast(NativeFixed64Surface, surface)
    payload = _bounded_native_payload(input_document, surface=surface)
    entrypoint = _native_session_entrypoint()
    try:
        session = entrypoint(payload)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    describe = getattr(session, "describe", None)
    if not callable(describe):
        raise NativeFixed64ConsumerError(
            "native fixed64 prepared session lacks metadata evidence"
        )
    try:
        metadata = describe()
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    if type(metadata) is not dict:
        raise NativeFixed64ConsumerError(
            "native fixed64 prepared-session metadata is not an exact dict"
        )
    backend = payload.get("backend")
    if type(backend) is not str:
        raise NativeFixed64ConsumerError(
            "native fixed64 prepared-session backend is invalid"
        )
    return NativeFixed64PreparedSessionV1(
        _native_session=session,
        _metadata=metadata,
        _backend=backend,
        _default_consumer=surface,
    )


def run_native_fixed64_surface(
    input_document: Mapping[str, object],
    *,
    surface: NativeFixed64Surface,
) -> NativeFixed64EvidenceV3:
    """Run one surface through the exact same Rust receipt core."""

    payload = _bounded_native_payload(input_document, surface=surface)
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
    return NativeFixed64EvidenceV3(surface=surface, _document=result)


class NativeFixed64CliAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="cli")


class NativeFixed64DiagnosticBenchmarkAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="benchmark")


class NativeFixed64PythonApi:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="api")


class NativeFixed64ProductShadowAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="product_shadow")


__all__ = [
    "NativeFixed64CliAdapter",
    "NativeFixed64ConsumerError",
    "NativeFixed64DiagnosticBenchmarkAdapter",
    "NativeFixed64EvidenceV1",
    "NativeFixed64EvidenceV2",
    "NativeFixed64EvidenceV3",
    "NativeFixed64PreparedSessionV1",
    "NativeFixed64ProductShadowAdapter",
    "NativeFixed64PythonApi",
    "NativeFixed64Surface",
    "prepare_native_fixed64_session",
    "run_native_fixed64_surface",
]
