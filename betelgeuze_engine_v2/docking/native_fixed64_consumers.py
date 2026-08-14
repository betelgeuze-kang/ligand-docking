"""Thin, claim-blocked consumers over the native Rust fixed64 pipeline.

This module performs no molecular geometry, scoring, validity, or ranking work.
It only selects a consumer surface, calls the one native entrypoint, and checks
that the returned permission boundary remains fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import math
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
_REPOSITORY_D0_SESSION_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_repository_synthetic_d0_session_binding/1.0.0"
)
_REPOSITORY_D0_SESSION_BINDING_RECEIPT_DOMAIN = (
    b"betelgeuze.engine-v2.native-repository-d0-session-binding/v1\0"
)
_REPOSITORY_D0_BACKEND_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_repository_synthetic_d0_backend_binding/1.0.0"
)
_REPOSITORY_D0_BACKEND_BINDING_RECEIPT_DOMAIN = (
    b"betelgeuze.engine-v2.native-repository-d0-backend-binding/v1\0"
)
REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT = (
    "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
    "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
)
_REPOSITORY_D0_SOURCE_PROFILE_ID = (
    "betelgeuze.engine_v2_repository_synthetic_d0_fixed64_source/native-1.0.0"
)
_REPOSITORY_D0_SOURCE_BUNDLE_SHA256 = (
    "80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"
)
_REPOSITORY_D0_SOURCE_PREPARED_INPUT_SHA256 = (
    "9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"
)
_REPOSITORY_D0_ALLOCATION_SHA256 = (
    "8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"
)
_REPOSITORY_D0_SCIENTIFIC_DECISION_SHA256 = (
    "8908c757de4e7a8f5d12452e40ec0292b44c3db7893f98d5b92956e1f0c9d9f4"
)
_REPOSITORY_D0_PRIMARY_SLOT_INDICES = (
    23,
    63,
    9,
    10,
    29,
    16,
    61,
    8,
    11,
    52,
    20,
    13,
    33,
    26,
    34,
    22,
)
_REPOSITORY_D0_REPRESENTATIVE_SLOT_INDICES = (
    23,
    9,
    10,
    29,
    16,
    8,
    11,
    52,
    20,
    13,
    33,
    22,
)
_REPOSITORY_D0_TOP_K_SLOT_INDICES = (23, 9, 10, 29, 16)
_NATIVE_FIXED64_PIPELINE_ID = (
    "betelgeuze.engine_v2_native_fixed64_complete_pipeline/2.0.0"
)
_PREPARED_INPUT_SCALAR_LIMIT = 8 * 1_024 * 1_024
# Versioned v3 transport schema cardinality.  Bound the outer mapping before
# making even a shallow transport copy; Rust then validates the exact key set
# and bounds every nested collection before copying its values.
_COMPLETE_INPUT_KEY_COUNT = 53

_REPOSITORY_D0_BACKEND_BINDING_VALUE_FIELDS = (
    "schema_id",
    "backend",
    "pipeline_id",
    "native_package_version",
    "native_source_closure_sha256",
    "native_source_closure_file_count_decimal",
    "native_build_profile_id",
    "native_toolchain_sha256",
    "toolchain_attestation_status",
    "build_wrapper_control",
    "native_cargo_features",
    "rustc_verbose_sha256",
    "target_triple",
)
_REPOSITORY_D0_BACKEND_BINDING_FIELDS = frozenset(
    (
        *_REPOSITORY_D0_BACKEND_BINDING_VALUE_FIELDS,
        "source_bundle_receipt_sha256",
        "receipt_sha256",
    )
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


def _native_repository_d0_session_entrypoint():
    try:
        module = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError) as exc:
        raise NativeFixed64ConsumerError(
            "native fixed64 extension is required; Python fallback is forbidden"
        ) from exc
    name = "native_fixed64_prepare_repository_synthetic_d0_session_v1"
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


_REPOSITORY_D0_VALIDITY_FIELDS = frozenset(
    {
        "status",
        "failure_code",
        "upstream_scorer_failure_code",
        "passed_check_mask",
        "blocker_mask",
        "observed_count",
        "atom_count",
        "rotation_orthogonality_max_error",
        "rotation_determinant",
        "max_bond_length_delta_angstrom",
        "minimum_ligand_nonbonded_distance_angstrom",
        "evaluated_ligand_nonbonded_pair_count",
        "excluded_ligand_pair_count",
        "minimum_receptor_ligand_distance_angstrom",
        "evaluated_receptor_ligand_pair_count",
        "minimum_declared_chiral_volume",
        "declared_chirality_center_count",
        "maximum_pocket_center_distance_angstrom",
        "element_vdw_ligand_pair_count",
        "element_vdw_ligand_severe_overlap_count",
        "element_vdw_ligand_minimum_distance_angstrom",
        "element_vdw_ligand_minimum_ratio",
        "element_vdw_receptor_candidate_pair_count",
        "element_vdw_receptor_full_cartesian_pair_count",
        "element_vdw_receptor_cell_count",
        "element_vdw_receptor_severe_overlap_count",
        "element_vdw_receptor_minimum_distance_angstrom",
        "element_vdw_receptor_minimum_ratio",
    }
)


def _repository_d0_digest(value: object, *, name: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise NativeFixed64ConsumerError(f"repository D0 {name} is not SHA-256")
    return value


def _repository_d0_slot_indices(value: object, *, name: str) -> tuple[int, ...]:
    if type(value) is not list or any(type(item) is not int for item in value):
        raise NativeFixed64ConsumerError(
            f"repository D0 {name} must be an exact integer list"
        )
    return tuple(value)


def _repository_d0_backend_binding_digest(
    binding: Mapping[str, object],
) -> str:
    if (
        type(binding) is not dict
        or set(binding) != _REPOSITORY_D0_BACKEND_BINDING_FIELDS
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 backend binding key schema changed"
        )
    values: list[str] = []
    for field in _REPOSITORY_D0_BACKEND_BINDING_VALUE_FIELDS:
        value = binding.get(field)
        if type(value) is not str:
            raise NativeFixed64ConsumerError(
                f"repository D0 backend binding field {field} is not an exact string"
            )
        try:
            value.encode("ascii")
        except UnicodeEncodeError as exc:
            raise NativeFixed64ConsumerError(
                f"repository D0 backend binding field {field} is not ASCII"
            ) from exc
        values.append(value)
    if (
        values[0] != _REPOSITORY_D0_BACKEND_BINDING_SCHEMA_ID
        or values[2] != _NATIVE_FIXED64_PIPELINE_ID
        or not values[5].isdigit()
        or int(values[5]) <= 0
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 backend build identity is cross-wired"
        )
    for field in ("native_source_closure_sha256", "rustc_verbose_sha256"):
        _repository_d0_digest(binding.get(field), name=field)
    if values[8] == "attested_sha256":
        _repository_d0_digest(
            binding.get("native_toolchain_sha256"), name="native_toolchain_sha256"
        )
        expected_features = {
            "cpu-manylinux_2_28-gcc14": "extension-module",
            "hip-gfx1030-rocm602": "extension-module,hip",
        }.get(values[6])
        if (
            expected_features is None
            or values[9] != "verified_frozen_wrapper"
            or values[10] != expected_features
        ):
            raise NativeFixed64ConsumerError(
                "repository D0 attested build identity is cross-wired"
            )
    elif not (
        values[8] == "unattested_direct_cargo"
        and values[7] == "unattested"
        and values[6] == "direct-cargo-unattested"
        and values[9] == "direct_cargo_unattested"
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 toolchain attestation state is ambiguous"
        )
    source_bundle = _repository_d0_digest(
        binding.get("source_bundle_receipt_sha256"),
        name="backend source bundle receipt",
    )
    if source_bundle != _REPOSITORY_D0_SOURCE_BUNDLE_SHA256:
        raise NativeFixed64ConsumerError(
            "repository D0 backend binding source bundle is cross-wired"
        )
    digest = hashlib.sha256()
    digest.update(_REPOSITORY_D0_BACKEND_BINDING_RECEIPT_DOMAIN)
    for value in values:
        encoded = value.encode("ascii")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    digest.update(bytes.fromhex(source_bundle))
    digest.update(b"\0")
    observed = _repository_d0_digest(
        binding.get("receipt_sha256"), name="backend binding receipt"
    )
    if digest.hexdigest() != observed:
        raise NativeFixed64ConsumerError(
            "repository D0 backend binding receipt is not rederivable"
        )
    return observed


def _validate_repository_d0_document(
    document: Mapping[str, object],
    *,
    backend: str,
    require_decision: bool,
) -> None:
    if type(document) is not dict or type(backend) is not str:
        raise TypeError("repository D0 evidence must use exact Python identities")
    if (
        type(document.get("backend")) is not str
        or document.get("backend") != backend
        or backend not in {"cpp_cpu_reference", "rust_cpu"}
        or document.get("prepared_source_origin")
        != "repository_synthetic_d0_native_materializer"
        or document.get("caller_science_transport_consumed") is not False
        or document.get("repository_source_profile_id")
        != _REPOSITORY_D0_SOURCE_PROFILE_ID
        or document.get("repository_source_bundle_receipt_sha256")
        != _REPOSITORY_D0_SOURCE_BUNDLE_SHA256
        or document.get("repository_source_prepared_input_receipt_sha256")
        != _REPOSITORY_D0_SOURCE_PREPARED_INPUT_SHA256
        or document.get("repository_allocation_receipt_sha256")
        != _REPOSITORY_D0_ALLOCATION_SHA256
        or document.get("repository_session_binding_schema_id")
        != _REPOSITORY_D0_SESSION_BINDING_SCHEMA_ID
        or document.get("synthetic_only_acknowledgment")
        != REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT
        or document.get("candidate_denominator") != 64
        or document.get("ligand_atom_count") != 5
        or document.get("receptor_atom_count") != 5
        or document.get("exact_cartesian_pair_count") != 25
        or document.get("prepared_input_scalar_count") != 1_178
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 session evidence is cross-wired"
        )
    for field in (
        "qualification_rerun_authorized",
        "d1_d2_molecular_execution_authorized",
        "fresh_holdout_execution_authorized",
        "historical_ab_execution_authorized",
        "public_benchmark_authorized",
        "stage0_admission_authorized",
        "product_performance_claim_authorized",
    ):
        if document.get(field) is not False:
            raise NativeFixed64ConsumerError(
                f"repository D0 authority field {field} changed"
            )
    backend_binding = document.get("repository_backend_binding")
    if not isinstance(backend_binding, Mapping):
        raise NativeFixed64ConsumerError(
            "repository D0 backend binding evidence is absent"
        )
    backend_receipt = _repository_d0_backend_binding_digest(backend_binding)
    if (
        backend_binding.get("backend") != backend
        or document.get("repository_backend_binding_receipt_sha256") != backend_receipt
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 backend binding alias is cross-wired"
        )
    prepared_session_receipt = _repository_d0_digest(
        document.get("prepared_session_receipt_sha256"),
        name="prepared session receipt",
    )
    session_binding = hashlib.sha256()
    session_binding.update(_REPOSITORY_D0_SESSION_BINDING_RECEIPT_DOMAIN)
    schema = _REPOSITORY_D0_SESSION_BINDING_SCHEMA_ID.encode("ascii")
    session_binding.update(len(schema).to_bytes(8, "big"))
    session_binding.update(schema)
    for value in (
        prepared_session_receipt,
        _REPOSITORY_D0_SOURCE_BUNDLE_SHA256,
        _REPOSITORY_D0_SOURCE_PREPARED_INPUT_SHA256,
        _REPOSITORY_D0_ALLOCATION_SHA256,
        backend_receipt,
    ):
        session_binding.update(bytes.fromhex(value))
    session_binding.update(b"\0")
    observed_session_binding = _repository_d0_digest(
        document.get("repository_session_binding_receipt_sha256"),
        name="session binding receipt",
    )
    if session_binding.hexdigest() != observed_session_binding:
        raise NativeFixed64ConsumerError(
            "repository D0 session binding receipt is not rederivable"
        )
    if not require_decision:
        if "repository_scientific_decision_sha256" in document:
            raise NativeFixed64ConsumerError(
                "repository D0 metadata unexpectedly contains run results"
            )
        return
    decision_sha256 = _repository_d0_digest(
        document.get("repository_scientific_decision_sha256"),
        name="scientific decision receipt",
    )
    primary_slot_indices = _repository_d0_slot_indices(
        document.get("primary_slot_indices"), name="primary slots"
    )
    valid_slot_indices = _repository_d0_slot_indices(
        document.get("valid_slot_indices"), name="valid slots"
    )
    representative_slot_indices = _repository_d0_slot_indices(
        document.get("representative_slot_indices"), name="representative slots"
    )
    top_k_slot_indices = _repository_d0_slot_indices(
        document.get("top_k_slot_indices"), name="Top-K slots"
    )
    if (
        decision_sha256 != _REPOSITORY_D0_SCIENTIFIC_DECISION_SHA256
        or document.get("generated_count") != 54
        or document.get("typed_failure_count") != 10
        or document.get("initial_admitted_count") != 30
        or document.get("refined_count") != 16
        or document.get("post_admitted_count") != 16
        or document.get("post_rejected_count") != 0
        or document.get("scored_count") != 16
        or document.get("valid_count") != 16
        or document.get("cluster_count") != 12
        or primary_slot_indices != _REPOSITORY_D0_PRIMARY_SLOT_INDICES
        or valid_slot_indices != _REPOSITORY_D0_PRIMARY_SLOT_INDICES
        or representative_slot_indices != _REPOSITORY_D0_REPRESENTATIVE_SLOT_INDICES
        or top_k_slot_indices != _REPOSITORY_D0_TOP_K_SLOT_INDICES
        or document.get("allocation_receipt_sha256") != _REPOSITORY_D0_ALLOCATION_SHA256
    ):
        raise NativeFixed64ConsumerError(
            "repository D0 runtime denominator or allocation changed"
        )
    candidates = document.get("candidates")
    if type(candidates) is not list or len(candidates) != 64:
        raise NativeFixed64ConsumerError(
            "repository D0 candidate evidence denominator changed"
        )
    available_count = 0
    for candidate in candidates:
        if type(candidate) is not dict:
            raise NativeFixed64ConsumerError(
                "repository D0 candidate evidence is not an exact dict"
            )
        scorer = candidate.get("scorer_v1")
        validity = candidate.get("validity")
        lineage = candidate.get("lineage")
        if (
            type(scorer) is not dict
            or type(validity) is not dict
            or set(validity) != _REPOSITORY_D0_VALIDITY_FIELDS
            or type(lineage) is not dict
        ):
            raise NativeFixed64ConsumerError(
                "repository D0 scorer or validity evidence is incomplete"
            )
        terms = scorer.get("weighted_terms")
        if (
            type(terms) is not list
            or len(terms) != 8
            or any(
                type(value) is not float or not math.isfinite(value) for value in terms
            )
        ):
            raise NativeFixed64ConsumerError(
                "repository D0 complete ScorerV1 term receipt changed"
            )
        _repository_d0_digest(
            lineage.get("scorer_evidence_sha256"), name="ScorerV1 row receipt"
        )
        _repository_d0_digest(
            lineage.get("validity_evidence_sha256"), name="validity row receipt"
        )
        if candidate.get("coordinates_available") is True:
            available_count += 1
            geometric = candidate.get("geometric_admission")
            if type(geometric) is not dict or geometric.get("exact_pair_count") != 25:
                raise NativeFixed64ConsumerError(
                    "repository D0 exact geometric pair denominator changed"
                )
    if available_count != 54:
        raise NativeFixed64ConsumerError(
            "repository D0 available candidate denominator changed"
        )


class NativeRepositorySyntheticD0EvidenceV1(NativeFixed64EvidenceV3):
    """Complete source-bound synthetic D0 evidence from one native session."""

    __slots__ = ()

    def __post_init__(self) -> None:
        _validate_repository_d0_document(
            self._document,
            backend=cast(str, self._document.get("backend")),
            require_decision=True,
        )
        super().__post_init__()


@dataclass(frozen=True, slots=True)
class NativeRepositorySyntheticD0PreparedSessionV1:
    """Validated facade over a no-caller-science repository D0 native session."""

    _base: NativeFixed64PreparedSessionV1

    def __post_init__(self) -> None:
        metadata = self._base.describe()
        _validate_repository_d0_document(
            metadata,
            backend=cast(str, metadata.get("backend")),
            require_decision=False,
        )

    @property
    def prepared_input_projection_sha256(self) -> str:
        return self._base.prepared_input_projection_sha256

    @property
    def prepared_session_receipt_sha256(self) -> str:
        return self._base.prepared_session_receipt_sha256

    def describe(self) -> dict[str, object]:
        return self._base.describe()

    def run(
        self, *, surface: NativeFixed64Surface
    ) -> NativeRepositorySyntheticD0EvidenceV1:
        evidence = self._base.run(surface=surface)
        return NativeRepositorySyntheticD0EvidenceV1(
            surface=surface,
            _document=evidence.to_dict(),
        )


# Import compatibility only. The alias validates and represents the v2 schema;
# it does not admit or reinterpret retired v1 evidence.
NativeFixed64EvidenceV1 = NativeFixed64EvidenceV2


def _bounded_native_payload(
    input_document: Mapping[str, object],
    *,
    surface: NativeFixed64Surface,
) -> dict[str, object]:
    _require_exact_native_input_shell(input_document)
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
    return payload


def _require_exact_native_input_shell(
    input_document: Mapping[str, object],
) -> tuple[str, str, str]:
    if type(input_document) is not dict:
        raise TypeError("native fixed64 input must be an exact dict")
    if len(input_document) != _COMPLETE_INPUT_KEY_COUNT:
        raise NativeFixed64ConsumerError(
            "canonical consumers require the complete fixed64 input schema: "
            "invalid top-level key count"
        )
    if any(type(key) is not str for key in input_document):
        raise NativeFixed64ConsumerError(
            "native fixed64 input keys must be exact strings"
        )
    schema_id = input_document.get("schema_id")
    consumer = input_document.get("consumer")
    backend = input_document.get("backend")
    if any(type(value) is not str for value in (schema_id, consumer, backend)):
        raise NativeFixed64ConsumerError(
            "native fixed64 input identities must be exact strings"
        )
    if schema_id != _COMPLETE_INPUT_SCHEMA_ID:
        raise NativeFixed64ConsumerError(
            "canonical consumers require the complete fixed64 input schema"
        )
    return cast(str, schema_id), cast(str, consumer), cast(str, backend)


def prepare_native_fixed64_session(
    input_document: Mapping[str, object],
) -> NativeFixed64PreparedSessionV1:
    """Prepare one persistent native context without granting run authority."""

    if type(input_document) is not dict:
        raise TypeError("native fixed64 input must be an exact dict")
    _schema_id, surface, _backend = _require_exact_native_input_shell(input_document)
    if surface not in {
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


def prepare_repository_synthetic_d0_session(
    *,
    backend: str,
    default_surface: NativeFixed64Surface,
    synthetic_only_acknowledgment: str,
) -> NativeRepositorySyntheticD0PreparedSessionV1:
    """Create the source-bound synthetic D0 session without Python science input."""

    if any(
        type(value) is not str
        for value in (backend, default_surface, synthetic_only_acknowledgment)
    ):
        raise TypeError("repository D0 session arguments must be exact strings")
    if backend not in {"cpp_cpu_reference", "rust_cpu"}:
        if backend in {"hip_safe", "hip_fast"}:
            raise NativeFixed64ConsumerError(
                "repository D0 session is synthetic CPU-only; HIP execution is unauthorized"
            )
        raise NativeFixed64ConsumerError("repository D0 backend is unsupported")
    if default_surface not in {"cli", "benchmark", "api", "product_shadow"}:
        raise NativeFixed64ConsumerError("native consumer surface is unsupported")
    if synthetic_only_acknowledgment != REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT:
        raise NativeFixed64ConsumerError(
            "repository D0 session requires the exact synthetic-only acknowledgment"
        )
    entrypoint = _native_repository_d0_session_entrypoint()
    try:
        session = entrypoint(
            backend,
            default_surface,
            synthetic_only_acknowledgment,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    describe = getattr(session, "describe", None)
    if not callable(describe):
        raise NativeFixed64ConsumerError(
            "repository D0 native session lacks metadata evidence"
        )
    try:
        metadata = describe()
    except (TypeError, ValueError, RuntimeError) as exc:
        raise NativeFixed64ConsumerError(str(exc)) from exc
    if type(metadata) is not dict:
        raise NativeFixed64ConsumerError(
            "repository D0 prepared-session metadata is not an exact dict"
        )
    base = NativeFixed64PreparedSessionV1(
        _native_session=session,
        _metadata=metadata,
        _backend=backend,
        _default_consumer=default_surface,
    )
    return NativeRepositorySyntheticD0PreparedSessionV1(_base=base)


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

    def run_repository_synthetic_d0(
        self, *, backend: str, synthetic_only_acknowledgment: str
    ) -> NativeRepositorySyntheticD0EvidenceV1:
        return prepare_repository_synthetic_d0_session(
            backend=backend,
            default_surface="cli",
            synthetic_only_acknowledgment=synthetic_only_acknowledgment,
        ).run(surface="cli")


class NativeFixed64DiagnosticBenchmarkAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="benchmark")

    def run_repository_synthetic_d0(
        self, *, backend: str, synthetic_only_acknowledgment: str
    ) -> NativeRepositorySyntheticD0EvidenceV1:
        return prepare_repository_synthetic_d0_session(
            backend=backend,
            default_surface="benchmark",
            synthetic_only_acknowledgment=synthetic_only_acknowledgment,
        ).run(surface="benchmark")


class NativeFixed64PythonApi:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="api")

    def run_repository_synthetic_d0(
        self, *, backend: str, synthetic_only_acknowledgment: str
    ) -> NativeRepositorySyntheticD0EvidenceV1:
        return prepare_repository_synthetic_d0_session(
            backend=backend,
            default_surface="api",
            synthetic_only_acknowledgment=synthetic_only_acknowledgment,
        ).run(surface="api")


class NativeFixed64ProductShadowAdapter:
    __slots__ = ()

    def run(self, input_document: Mapping[str, object]) -> NativeFixed64EvidenceV3:
        return run_native_fixed64_surface(input_document, surface="product_shadow")

    def run_repository_synthetic_d0(
        self, *, backend: str, synthetic_only_acknowledgment: str
    ) -> NativeRepositorySyntheticD0EvidenceV1:
        return prepare_repository_synthetic_d0_session(
            backend=backend,
            default_surface="product_shadow",
            synthetic_only_acknowledgment=synthetic_only_acknowledgment,
        ).run(surface="product_shadow")


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
    "NativeRepositorySyntheticD0EvidenceV1",
    "NativeRepositorySyntheticD0PreparedSessionV1",
    "REPOSITORY_SYNTHETIC_D0_NATIVE_ACKNOWLEDGMENT",
    "prepare_native_fixed64_session",
    "prepare_repository_synthetic_d0_session",
    "run_native_fixed64_surface",
]
