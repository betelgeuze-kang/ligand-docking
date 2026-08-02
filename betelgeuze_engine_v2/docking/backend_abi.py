"""Versioned, fail-closed native backend ABI contracts for Engine V2.

This module is deliberately declarative.  It does not load a native library,
discover a GPU, or make either HIP backend executable.  The legacy scorer
backend names are accepted only as identity aliases so existing receipts can
be migrated without silently promoting the legacy HIP implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
from typing import Mapping


ENGINE_V2_NATIVE_ABI_SCHEMA_ID = "engine-v2-native-tensor-stream-abi-v1"
ENGINE_V2_NATIVE_ABI_VERSION = "1.1.0"
ENGINE_V2_BACKEND_RECEIPT_SCHEMA_ID = "engine-v2-backend-receipt-v1"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HIP_ARCHITECTURE_RE = re.compile(r"^gfx[0-9a-f]+$")


class BackendABIError(ValueError):
    """Raised when a native ABI or backend receipt is not claim-safe."""


class EngineV2Backend(str, Enum):
    """Canonical Engine V2 backend taxonomy.

    ``hip_safe`` and ``hip_fast`` are contract identities only in this phase;
    :class:`EngineV2BackendReceipt` rejects an available HIP receipt.
    """

    PYTHON_REFERENCE = "python_reference"
    RUST_CPU = "rust_cpu"
    HIP_SAFE = "hip_safe"
    HIP_FAST = "hip_fast"


HIP_BACKENDS = frozenset({EngineV2Backend.HIP_SAFE, EngineV2Backend.HIP_FAST})

# Compatibility is identity-only.  In particular, cpp_hip_required does not
# establish safe math, parity, availability, or eligibility for GPU claims.
LEGACY_SCORER_BACKEND_ALIASES: Mapping[str, EngineV2Backend] = {
    "python_reference": EngineV2Backend.PYTHON_REFERENCE,
    "rust_cpu_required": EngineV2Backend.RUST_CPU,
    "cpp_hip_required": EngineV2Backend.HIP_SAFE,
}


class DeviceKind(str, Enum):
    CPU = "cpu"
    HIP = "hip"


class StreamKind(str, Enum):
    HOST_SYNCHRONOUS = "host_synchronous"
    HIP_STREAM = "hip_stream"


class StreamOwnership(str, Enum):
    CALLER = "caller"
    BACKEND = "backend"


class SynchronizationProtocol(str, Enum):
    HOST_BLOCKING = "host_blocking"
    CALLER_EVENT_HANDOFF = "caller_event_handoff"


class TensorDType(str, Enum):
    FLOAT64 = "float64"
    FLOAT32 = "float32"
    INT64 = "int64"
    INT32 = "int32"
    UINT8 = "uint8"


class TensorOwnership(str, Enum):
    CALLER = "caller"
    BACKEND = "backend"


class EngineV2ABIStage(str, Enum):
    """Exact native execution stages covered by ABI v1."""

    PERSISTENT_RECEPTOR_CONTEXT = "persistent_receptor_context"
    CANDIDATE_TRANSFORM_BATCH = "candidate_transform_batch"
    PAIR_LIST = "pair_list"
    SCORER_V1_8TERM = "scorer_v1_8term"
    POSE_VALIDITY = "pose_validity"
    STABLE_TOP_K = "stable_top_k"
    REFINEMENT_V2 = "refinement_v2"
    REFINEMENT_V3 = "refinement_v3"
    REFINEMENT_V6 = "refinement_v6"
    REFINEMENT_V7 = "refinement_v7"
    CLUSTERING_RMSD = "clustering_rmsd"


class TensorRole(str, Enum):
    """Closed tensor-role vocabulary for the Engine V2 native ABI."""

    RECEPTOR_COORDINATES = "receptor_coordinates"
    RECEPTOR_FEATURES = "receptor_features"
    RECEPTOR_CONTEXT_METADATA = "receptor_context_metadata"
    LIGAND_COORDINATES = "ligand_coordinates"
    CANDIDATE_TRANSFORMS = "candidate_transforms"
    CANDIDATE_COORDINATES = "candidate_coordinates"
    PAIR_INDICES = "pair_indices"
    PAIR_OFFSETS = "pair_offsets"
    PAIR_OVERFLOW_FLAGS = "pair_overflow_flags"
    SCORER_TERMS = "scorer_v1_terms"
    TOTAL_SCORES = "total_scores"
    FAILURE_CODES = "failure_codes"
    VALIDITY_FLAGS = "validity_flags"
    VALIDITY_REASON_CODES = "validity_reason_codes"
    TOPK_INDICES = "topk_indices"
    TOPK_SCORES = "topk_scores"
    TOPK_COUNT = "topk_count"
    REFINED_COORDINATES = "refined_coordinates"
    REFINEMENT_DECISIONS = "refinement_decisions"
    CLUSTER_LABELS = "cluster_labels"
    RMSD_MATRIX = "rmsd_matrix"


class MathMode(str, Enum):
    STRICT_BINARY64 = "strict_binary64"
    PARITY_QUALIFIED_FAST = "parity_qualified_fast"


_DTYPE_ITEMSIZE = {
    TensorDType.FLOAT64: 8,
    TensorDType.FLOAT32: 4,
    TensorDType.INT64: 8,
    TensorDType.INT32: 4,
    TensorDType.UINT8: 1,
}

SCORER_V1_TERM_NAMES = (
    "typed_vdw",
    "electrostatics",
    "directional_hbond",
    "hydrophobic_contact",
    "desolvation_proxy",
    "torsion_energy",
    "ligand_strain",
    "weak_pocket_prior",
)

HIP_SAFE_BUILD_FLAGS = (
    "-O2",
    "-fno-fast-math",
    "-fno-unsafe-math-optimizations",
    "-fno-finite-math-only",
    "-fsigned-zeros",
    "-ffp-contract=off",
)
HIP_FAST_BUILD_FLAGS = ("-O3", "-ffast-math")
HIP_SAFE_BUILD_PROFILE_SHA256 = hashlib.sha256(
    json.dumps(
        {"backend": "hip_safe", "build_flags": list(HIP_SAFE_BUILD_FLAGS)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
).hexdigest()
HIP_FAST_BUILD_PROFILE_SHA256 = hashlib.sha256(
    json.dumps(
        {"backend": "hip_fast", "build_flags": list(HIP_FAST_BUILD_FLAGS)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _digest(value: object, *, name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SHA256_RE.fullmatch(normalized):
        raise BackendABIError(f"{name} must be a lowercase SHA-256 digest")
    return normalized


def _optional_digest(value: object, *, name: str) -> str:
    normalized = str(value or "").strip().lower()
    return _digest(normalized, name=name) if normalized else ""


def _non_empty(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BackendABIError(f"{name} must be non-empty")
    return normalized


def canonical_backend(value: object) -> EngineV2Backend:
    """Return the canonical backend for a new or legacy scorer identity.

    Enum-like objects are accepted through their string ``value``.  Mapping a
    legacy HIP name is not an availability decision; HIP receipts remain
    unavailable and must pass the separate parity verifier.
    """

    if isinstance(value, EngineV2Backend):
        return value
    raw_value = getattr(value, "value", value)
    normalized = str(raw_value or "").strip()
    if normalized in LEGACY_SCORER_BACKEND_ALIASES:
        return LEGACY_SCORER_BACKEND_ALIASES[normalized]
    try:
        return EngineV2Backend(normalized)
    except ValueError as exc:
        raise BackendABIError(f"unsupported Engine V2 backend: {normalized!r}") from exc


def compatibility_alias(value: object) -> str | None:
    """Return the legacy scorer name when ``value`` uses a compatibility alias."""

    raw_value = str(getattr(value, "value", value) or "").strip()
    if raw_value in {"rust_cpu_required", "cpp_hip_required"}:
        return raw_value
    return None


@dataclass(frozen=True, slots=True)
class DeviceABI:
    kind: DeviceKind
    ordinal: int
    architecture: str
    runtime_name: str
    runtime_version: str
    device_identity_sha256: str
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        kind = self.kind
        if isinstance(kind, str):
            try:
                kind = DeviceKind(kind)
            except ValueError as exc:
                raise BackendABIError("unsupported device kind") from exc
            object.__setattr__(self, "kind", kind)
        if not isinstance(kind, DeviceKind):
            raise TypeError("kind must be DeviceKind")
        if isinstance(self.ordinal, bool) or not isinstance(self.ordinal, int):
            raise TypeError("ordinal must be an integer")
        if self.ordinal < 0:
            raise BackendABIError("ordinal must be non-negative")
        architecture = _non_empty(self.architecture, name="architecture").lower()
        if kind is DeviceKind.HIP and not _HIP_ARCHITECTURE_RE.fullmatch(architecture):
            raise BackendABIError("HIP architecture must be an exact gfx identifier")
        object.__setattr__(self, "architecture", architecture)
        object.__setattr__(
            self, "runtime_name", _non_empty(self.runtime_name, name="runtime_name")
        )
        object.__setattr__(
            self,
            "runtime_version",
            _non_empty(self.runtime_version, name="runtime_version"),
        )
        object.__setattr__(
            self,
            "device_identity_sha256",
            _digest(self.device_identity_sha256, name="device_identity_sha256"),
        )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_NATIVE_ABI_SCHEMA_ID,
            "abi_version": ENGINE_V2_NATIVE_ABI_VERSION,
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "architecture": self.architecture,
            "runtime_name": self.runtime_name,
            "runtime_version": self.runtime_version,
            "device_identity_sha256": self.device_identity_sha256,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise BackendABIError("device ABI changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class StreamABI:
    kind: StreamKind
    ownership: StreamOwnership
    synchronization: SynchronizationProtocol
    device_fingerprint_sha256: str
    stream_ordinal: int = 0
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name, enum_type in (
            ("kind", StreamKind),
            ("ownership", StreamOwnership),
            ("synchronization", SynchronizationProtocol),
        ):
            value = getattr(self, name)
            if isinstance(value, str):
                try:
                    value = enum_type(value)
                except ValueError as exc:
                    raise BackendABIError(f"unsupported {name}") from exc
                object.__setattr__(self, name, value)
            if not isinstance(value, enum_type):
                raise TypeError(f"{name} must be {enum_type.__name__}")
        object.__setattr__(
            self,
            "device_fingerprint_sha256",
            _digest(
                self.device_fingerprint_sha256,
                name="stream device_fingerprint_sha256",
            ),
        )
        if isinstance(self.stream_ordinal, bool) or not isinstance(
            self.stream_ordinal, int
        ):
            raise TypeError("stream_ordinal must be an integer")
        if self.stream_ordinal < 0:
            raise BackendABIError("stream_ordinal must be non-negative")
        if self.kind is StreamKind.HOST_SYNCHRONOUS and (
            self.stream_ordinal != 0
            or self.synchronization is not SynchronizationProtocol.HOST_BLOCKING
        ):
            raise BackendABIError("host stream must be ordinal zero and blocking")
        if self.kind is StreamKind.HIP_STREAM and (
            self.synchronization is not SynchronizationProtocol.CALLER_EVENT_HANDOFF
        ):
            raise BackendABIError("HIP stream requires explicit event handoff")
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_NATIVE_ABI_SCHEMA_ID,
            "abi_version": ENGINE_V2_NATIVE_ABI_VERSION,
            "kind": self.kind.value,
            "ownership": self.ownership.value,
            "synchronization": self.synchronization.value,
            "device_fingerprint_sha256": self.device_fingerprint_sha256,
            "stream_ordinal": self.stream_ordinal,
            "raw_pointer_serialized": False,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise BackendABIError("stream ABI changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


@dataclass(frozen=True, slots=True)
class TensorABI:
    role: TensorRole
    dtype: TensorDType
    shape: tuple[int, ...]
    strides_bytes: tuple[int, ...]
    device_fingerprint_sha256: str
    ownership: TensorOwnership
    read_only: bool
    alignment_bytes: int = 8
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        role = self.role
        if isinstance(role, str):
            try:
                role = TensorRole(role)
            except ValueError as exc:
                raise BackendABIError("unsupported tensor role") from exc
            object.__setattr__(self, "role", role)
        if not isinstance(role, TensorRole):
            raise TypeError("role must be TensorRole")
        dtype = self.dtype
        if isinstance(dtype, str):
            try:
                dtype = TensorDType(dtype)
            except ValueError as exc:
                raise BackendABIError("unsupported tensor dtype") from exc
            object.__setattr__(self, "dtype", dtype)
        if not isinstance(dtype, TensorDType):
            raise TypeError("dtype must be TensorDType")
        ownership = self.ownership
        if isinstance(ownership, str):
            try:
                ownership = TensorOwnership(ownership)
            except ValueError as exc:
                raise BackendABIError("unsupported tensor ownership") from exc
            object.__setattr__(self, "ownership", ownership)
        if not isinstance(ownership, TensorOwnership):
            raise TypeError("ownership must be TensorOwnership")
        shape = tuple(self.shape)
        strides = tuple(self.strides_bytes)
        if not shape or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in shape
        ):
            raise BackendABIError("tensor shape must contain non-negative integers")
        if len(strides) != len(shape) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in strides
        ):
            raise BackendABIError("tensor strides must be positive and match rank")
        expected: list[int] = [0] * len(shape)
        running = _DTYPE_ITEMSIZE[dtype]
        for index in range(len(shape) - 1, -1, -1):
            expected[index] = running
            running *= shape[index]
        if strides != tuple(expected):
            raise BackendABIError("tensor ABI v1 requires C-contiguous byte strides")
        object.__setattr__(self, "shape", shape)
        object.__setattr__(self, "strides_bytes", strides)
        object.__setattr__(
            self,
            "device_fingerprint_sha256",
            _digest(
                self.device_fingerprint_sha256,
                name="tensor device_fingerprint_sha256",
            ),
        )
        if not isinstance(self.read_only, bool):
            raise TypeError("read_only must be bool")
        if isinstance(self.alignment_bytes, bool) or not isinstance(
            self.alignment_bytes, int
        ):
            raise TypeError("alignment_bytes must be an integer")
        if self.alignment_bytes < _DTYPE_ITEMSIZE[dtype] or (
            self.alignment_bytes & (self.alignment_bytes - 1)
        ):
            raise BackendABIError(
                "alignment_bytes must be a power of two at least the dtype size"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_NATIVE_ABI_SCHEMA_ID,
            "abi_version": ENGINE_V2_NATIVE_ABI_VERSION,
            "role": self.role.value,
            "dtype": self.dtype.value,
            "shape": list(self.shape),
            "strides_bytes": list(self.strides_bytes),
            "layout": "c_contiguous",
            "device_fingerprint_sha256": self.device_fingerprint_sha256,
            "ownership": self.ownership.value,
            "read_only": self.read_only,
            "alignment_bytes": self.alignment_bytes,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise BackendABIError("tensor ABI changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "fingerprint_sha256": self.fingerprint_sha256}


_StageTensorContract = tuple[TensorRole, TensorDType, TensorOwnership, bool]

_STAGE_TENSOR_CONTRACTS: Mapping[EngineV2ABIStage, tuple[_StageTensorContract, ...]] = {
    EngineV2ABIStage.PERSISTENT_RECEPTOR_CONTEXT: (
        (
            TensorRole.RECEPTOR_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.CALLER,
            True,
        ),
        (
            TensorRole.RECEPTOR_FEATURES,
            TensorDType.FLOAT64,
            TensorOwnership.CALLER,
            True,
        ),
        (
            TensorRole.RECEPTOR_CONTEXT_METADATA,
            TensorDType.INT64,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    EngineV2ABIStage.CANDIDATE_TRANSFORM_BATCH: (
        (
            TensorRole.LIGAND_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.CALLER,
            True,
        ),
        (
            TensorRole.CANDIDATE_TRANSFORMS,
            TensorDType.FLOAT64,
            TensorOwnership.CALLER,
            True,
        ),
        (
            TensorRole.CANDIDATE_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    EngineV2ABIStage.PAIR_LIST: (
        (
            TensorRole.CANDIDATE_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.PAIR_INDICES,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.PAIR_OFFSETS,
            TensorDType.INT64,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.PAIR_OVERFLOW_FLAGS,
            TensorDType.UINT8,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    EngineV2ABIStage.SCORER_V1_8TERM: (
        (
            TensorRole.PAIR_INDICES,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.PAIR_OFFSETS,
            TensorDType.INT64,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.PAIR_OVERFLOW_FLAGS,
            TensorDType.UINT8,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.SCORER_TERMS,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.TOTAL_SCORES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.FAILURE_CODES,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    EngineV2ABIStage.POSE_VALIDITY: (
        (
            TensorRole.CANDIDATE_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.VALIDITY_FLAGS,
            TensorDType.UINT8,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.VALIDITY_REASON_CODES,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    EngineV2ABIStage.STABLE_TOP_K: (
        (
            TensorRole.TOTAL_SCORES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.FAILURE_CODES,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.VALIDITY_FLAGS,
            TensorDType.UINT8,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.TOPK_INDICES,
            TensorDType.INT64,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.TOPK_SCORES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.TOPK_COUNT,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
    **{
        stage: (
            (
                TensorRole.CANDIDATE_COORDINATES,
                TensorDType.FLOAT64,
                TensorOwnership.BACKEND,
                True,
            ),
            (
                TensorRole.REFINED_COORDINATES,
                TensorDType.FLOAT64,
                TensorOwnership.BACKEND,
                False,
            ),
            (
                TensorRole.REFINEMENT_DECISIONS,
                TensorDType.INT32,
                TensorOwnership.BACKEND,
                False,
            ),
        )
        for stage in (
            EngineV2ABIStage.REFINEMENT_V2,
            EngineV2ABIStage.REFINEMENT_V3,
            EngineV2ABIStage.REFINEMENT_V6,
            EngineV2ABIStage.REFINEMENT_V7,
        )
    },
    EngineV2ABIStage.CLUSTERING_RMSD: (
        (
            TensorRole.REFINED_COORDINATES,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            True,
        ),
        (
            TensorRole.CLUSTER_LABELS,
            TensorDType.INT32,
            TensorOwnership.BACKEND,
            False,
        ),
        (
            TensorRole.RMSD_MATRIX,
            TensorDType.FLOAT64,
            TensorOwnership.BACKEND,
            False,
        ),
    ),
}

_STAGE_ORDER = tuple(EngineV2ABIStage)


def _tensor_by_role(tensors: tuple[TensorABI, ...]) -> dict[TensorRole, TensorABI]:
    return {value.role: value for value in tensors}


def _require_shape(
    tensor: TensorABI,
    *,
    rank: int,
    trailing: tuple[int, ...] = (),
    positive_axes: tuple[int, ...] = (),
) -> None:
    if len(tensor.shape) != rank:
        raise BackendABIError(
            f"{tensor.role.value} must have rank {rank}, got {len(tensor.shape)}"
        )
    if trailing and tensor.shape[-len(trailing) :] != trailing:
        raise BackendABIError(
            f"{tensor.role.value} must have trailing shape {trailing}"
        )
    if any(tensor.shape[index] <= 0 for index in positive_axes):
        raise BackendABIError(f"{tensor.role.value} requires positive dimensions")


def _validate_stage_shapes(
    stage: EngineV2ABIStage, tensors: tuple[TensorABI, ...]
) -> None:
    rows = _tensor_by_role(tensors)
    if stage is EngineV2ABIStage.PERSISTENT_RECEPTOR_CONTEXT:
        coordinates = rows[TensorRole.RECEPTOR_COORDINATES]
        features = rows[TensorRole.RECEPTOR_FEATURES]
        metadata = rows[TensorRole.RECEPTOR_CONTEXT_METADATA]
        _require_shape(coordinates, rank=2, trailing=(3,), positive_axes=(0,))
        _require_shape(features, rank=2, positive_axes=(0, 1))
        _require_shape(metadata, rank=1, trailing=(4,))
        if features.shape[0] != coordinates.shape[0]:
            raise BackendABIError("receptor feature and coordinate counts must match")
        return
    if stage is EngineV2ABIStage.CANDIDATE_TRANSFORM_BATCH:
        ligand = rows[TensorRole.LIGAND_COORDINATES]
        transforms = rows[TensorRole.CANDIDATE_TRANSFORMS]
        candidates = rows[TensorRole.CANDIDATE_COORDINATES]
        _require_shape(ligand, rank=2, trailing=(3,), positive_axes=(0,))
        _require_shape(transforms, rank=2, trailing=(7,), positive_axes=(0,))
        _require_shape(candidates, rank=3, trailing=(3,), positive_axes=(0, 1))
        if candidates.shape[:2] != (transforms.shape[0], ligand.shape[0]):
            raise BackendABIError("candidate transform batch dimensions do not match")
        return
    if stage is EngineV2ABIStage.PAIR_LIST:
        candidates = rows[TensorRole.CANDIDATE_COORDINATES]
        pair_indices = rows[TensorRole.PAIR_INDICES]
        pair_offsets = rows[TensorRole.PAIR_OFFSETS]
        overflow = rows[TensorRole.PAIR_OVERFLOW_FLAGS]
        _require_shape(candidates, rank=3, trailing=(3,), positive_axes=(0, 1))
        _require_shape(pair_indices, rank=2, trailing=(3,))
        _require_shape(pair_offsets, rank=1, positive_axes=(0,))
        _require_shape(overflow, rank=1, positive_axes=(0,))
        batch = candidates.shape[0]
        if pair_offsets.shape != (batch + 1,) or overflow.shape != (batch,):
            raise BackendABIError(
                "pair-list offsets and overflow flags must bind batch"
            )
        return
    if stage is EngineV2ABIStage.SCORER_V1_8TERM:
        pair_indices = rows[TensorRole.PAIR_INDICES]
        pair_offsets = rows[TensorRole.PAIR_OFFSETS]
        overflow = rows[TensorRole.PAIR_OVERFLOW_FLAGS]
        terms = rows[TensorRole.SCORER_TERMS]
        totals = rows[TensorRole.TOTAL_SCORES]
        failures = rows[TensorRole.FAILURE_CODES]
        _require_shape(pair_indices, rank=2, trailing=(3,))
        _require_shape(pair_offsets, rank=1, positive_axes=(0,))
        _require_shape(overflow, rank=1, positive_axes=(0,))
        _require_shape(
            terms,
            rank=2,
            trailing=(len(SCORER_V1_TERM_NAMES),),
            positive_axes=(0,),
        )
        _require_shape(totals, rank=1, positive_axes=(0,))
        _require_shape(failures, rank=1, positive_axes=(0,))
        batch = terms.shape[0]
        if (
            pair_offsets.shape != (batch + 1,)
            or overflow.shape != (batch,)
            or totals.shape != (batch,)
            or failures.shape != (batch,)
        ):
            raise BackendABIError("ScorerV1 tensors must bind one exact batch")
        return
    if stage is EngineV2ABIStage.POSE_VALIDITY:
        candidates = rows[TensorRole.CANDIDATE_COORDINATES]
        flags = rows[TensorRole.VALIDITY_FLAGS]
        reasons = rows[TensorRole.VALIDITY_REASON_CODES]
        _require_shape(candidates, rank=3, trailing=(3,), positive_axes=(0, 1))
        _require_shape(flags, rank=2, trailing=(4,), positive_axes=(0,))
        _require_shape(reasons, rank=1, positive_axes=(0,))
        if flags.shape[0] != candidates.shape[0] or reasons.shape != (
            candidates.shape[0],
        ):
            raise BackendABIError("pose-validity tensors must bind candidate batch")
        return
    if stage is EngineV2ABIStage.STABLE_TOP_K:
        totals = rows[TensorRole.TOTAL_SCORES]
        failures = rows[TensorRole.FAILURE_CODES]
        flags = rows[TensorRole.VALIDITY_FLAGS]
        indices = rows[TensorRole.TOPK_INDICES]
        scores = rows[TensorRole.TOPK_SCORES]
        count = rows[TensorRole.TOPK_COUNT]
        _require_shape(totals, rank=1, positive_axes=(0,))
        _require_shape(failures, rank=1, positive_axes=(0,))
        _require_shape(flags, rank=2, trailing=(4,), positive_axes=(0,))
        _require_shape(indices, rank=1, positive_axes=(0,))
        _require_shape(scores, rank=1, positive_axes=(0,))
        _require_shape(count, rank=1, trailing=(1,))
        batch = totals.shape[0]
        expected_top_k = min(5, batch)
        if (
            failures.shape != (batch,)
            or flags.shape[0] != batch
            or indices.shape != (expected_top_k,)
            or scores.shape != (expected_top_k,)
            or count.shape != (1,)
        ):
            raise BackendABIError(
                "stable Top-K must preserve failures and expose bounded output count"
            )
        return
    if stage in {
        EngineV2ABIStage.REFINEMENT_V2,
        EngineV2ABIStage.REFINEMENT_V3,
        EngineV2ABIStage.REFINEMENT_V6,
        EngineV2ABIStage.REFINEMENT_V7,
    }:
        candidates = rows[TensorRole.CANDIDATE_COORDINATES]
        refined = rows[TensorRole.REFINED_COORDINATES]
        decisions = rows[TensorRole.REFINEMENT_DECISIONS]
        _require_shape(candidates, rank=3, trailing=(3,), positive_axes=(0, 1))
        _require_shape(refined, rank=3, trailing=(3,), positive_axes=(0, 1))
        _require_shape(decisions, rank=1, positive_axes=(0,))
        if refined.shape != candidates.shape or decisions.shape != (
            candidates.shape[0],
        ):
            raise BackendABIError("refinement tensors must preserve candidate shape")
        return
    if stage is EngineV2ABIStage.CLUSTERING_RMSD:
        refined = rows[TensorRole.REFINED_COORDINATES]
        labels = rows[TensorRole.CLUSTER_LABELS]
        rmsd = rows[TensorRole.RMSD_MATRIX]
        _require_shape(refined, rank=3, trailing=(3,), positive_axes=(0, 1))
        _require_shape(labels, rank=1, positive_axes=(0,))
        _require_shape(rmsd, rank=2, positive_axes=(0, 1))
        batch = refined.shape[0]
        if labels.shape != (batch,) or rmsd.shape != (batch, batch):
            raise BackendABIError("clustering/RMSD tensors must bind candidate batch")
        return
    raise BackendABIError("unsupported Engine V2 ABI stage")


@dataclass(frozen=True, slots=True)
class StageABI:
    stage: EngineV2ABIStage
    tensors: tuple[TensorABI, ...]
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        stage = self.stage
        if isinstance(stage, str):
            try:
                stage = EngineV2ABIStage(stage)
            except ValueError as exc:
                raise BackendABIError("unsupported Engine V2 ABI stage") from exc
            object.__setattr__(self, "stage", stage)
        if not isinstance(stage, EngineV2ABIStage):
            raise TypeError("stage must be EngineV2ABIStage")
        tensors = tuple(self.tensors)
        if any(not isinstance(value, TensorABI) for value in tensors):
            raise TypeError("stage tensors must contain TensorABI values")
        expected = _STAGE_TENSOR_CONTRACTS[stage]
        if tuple(value.role for value in tensors) != tuple(row[0] for row in expected):
            raise BackendABIError(
                f"{stage.value} requires its exact ordered tensor-role signature"
            )
        for tensor, (_, dtype, ownership, read_only) in zip(
            tensors, expected, strict=True
        ):
            if (
                tensor.dtype is not dtype
                or tensor.ownership is not ownership
                or tensor.read_only is not read_only
            ):
                raise BackendABIError(
                    f"{stage.value}:{tensor.role.value} violates its exact tensor contract"
                )
        _validate_stage_shapes(stage, tensors)
        object.__setattr__(self, "tensors", tensors)
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def tensor(self, role: TensorRole) -> TensorABI:
        for value in self.tensors:
            if value.role is role:
                return value
        raise BackendABIError(f"{self.stage.value} does not define {role.value}")

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_NATIVE_ABI_SCHEMA_ID,
            "abi_version": ENGINE_V2_NATIVE_ABI_VERSION,
            "stage": self.stage.value,
            "tensor_fingerprint_sha256": [
                value.fingerprint_sha256 for value in self.tensors
            ],
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise BackendABIError("stage ABI changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "tensors": [value.to_dict() for value in self.tensors],
            "fingerprint_sha256": self.fingerprint_sha256,
        }


@dataclass(frozen=True, slots=True)
class EngineV2NativeABI:
    backend: EngineV2Backend
    device: DeviceABI
    stream: StreamABI
    stages: tuple[StageABI, ...]
    max_batch_size: int
    deterministic_required: bool = True
    fast_math_allowed: bool = False
    unsafe_fp_atomics_allowed: bool = False
    implicit_fallback_allowed: bool = False
    abi_version: str = ENGINE_V2_NATIVE_ABI_VERSION
    _fingerprint_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if compatibility_alias(self.backend) is not None:
            raise BackendABIError(
                "legacy backend aliases cannot create a new Engine V2 native ABI"
            )
        backend = canonical_backend(self.backend)
        object.__setattr__(self, "backend", backend)
        if not isinstance(self.device, DeviceABI):
            raise TypeError("device must be DeviceABI")
        if not isinstance(self.stream, StreamABI):
            raise TypeError("stream must be StreamABI")
        stages = tuple(self.stages)
        if any(not isinstance(value, StageABI) for value in stages):
            raise TypeError("stages must contain StageABI values")
        if tuple(value.stage for value in stages) != _STAGE_ORDER:
            raise BackendABIError("native ABI requires the exact Engine V2 stage order")
        object.__setattr__(self, "stages", stages)
        if self.stream.device_fingerprint_sha256 != self.device.fingerprint_sha256:
            raise BackendABIError("stream and device identities do not match")
        if any(
            value.device_fingerprint_sha256 != self.device.fingerprint_sha256
            for stage in stages
            for value in stage.tensors
        ):
            raise BackendABIError("tensor and device identities do not match")
        if isinstance(self.max_batch_size, bool) or not isinstance(
            self.max_batch_size, int
        ):
            raise TypeError("max_batch_size must be an integer")
        if not 1 <= self.max_batch_size <= 64:
            raise BackendABIError("max_batch_size must be within [1, 64]")
        for name in (
            "deterministic_required",
            "fast_math_allowed",
            "unsafe_fp_atomics_allowed",
            "implicit_fallback_allowed",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.abi_version != ENGINE_V2_NATIVE_ABI_VERSION:
            raise BackendABIError("unsupported Engine V2 native ABI version")
        if self.implicit_fallback_allowed:
            raise BackendABIError("implicit backend fallback is forbidden")
        if self.unsafe_fp_atomics_allowed:
            raise BackendABIError("unsafe floating-point atomics are forbidden")
        if not self.deterministic_required:
            raise BackendABIError(
                "all Engine V2 backends require deterministic execution"
            )
        if backend in HIP_BACKENDS:
            if self.device.kind is not DeviceKind.HIP:
                raise BackendABIError("HIP backend requires a HIP device")
            if self.stream.kind is not StreamKind.HIP_STREAM:
                raise BackendABIError("HIP backend requires an explicit HIP stream")
        else:
            if self.device.kind is not DeviceKind.CPU:
                raise BackendABIError("CPU backend requires a CPU device")
            if self.stream.kind is not StreamKind.HOST_SYNCHRONOUS:
                raise BackendABIError(
                    "CPU backend requires the synchronous host stream"
                )
        if backend is not EngineV2Backend.HIP_FAST and self.fast_math_allowed:
            raise BackendABIError("fast math is reserved for hip_fast")
        if backend is EngineV2Backend.HIP_FAST and not self.fast_math_allowed:
            raise BackendABIError("hip_fast requires its explicit fast-math ABI mode")
        if backend is EngineV2Backend.HIP_SAFE and self.fast_math_allowed:
            raise BackendABIError("hip_safe requires deterministic strict math")
        candidate_shape = (
            self.stage(EngineV2ABIStage.CANDIDATE_TRANSFORM_BATCH)
            .tensor(TensorRole.CANDIDATE_COORDINATES)
            .shape
        )
        batch, ligand_atoms, _ = candidate_shape
        if batch != self.max_batch_size:
            raise BackendABIError("candidate batch must equal max_batch_size")
        pair_stage = self.stage(EngineV2ABIStage.PAIR_LIST)
        scorer_stage = self.stage(EngineV2ABIStage.SCORER_V1_8TERM)
        stages_with_candidate_coordinates = (
            EngineV2ABIStage.PAIR_LIST,
            EngineV2ABIStage.POSE_VALIDITY,
            EngineV2ABIStage.REFINEMENT_V2,
            EngineV2ABIStage.REFINEMENT_V3,
            EngineV2ABIStage.REFINEMENT_V6,
            EngineV2ABIStage.REFINEMENT_V7,
        )
        if any(
            self.stage(stage).tensor(TensorRole.CANDIDATE_COORDINATES).shape
            != (batch, ligand_atoms, 3)
            for stage in stages_with_candidate_coordinates
        ):
            raise BackendABIError("all native stages must bind one candidate tensor")
        if (
            scorer_stage.tensor(TensorRole.PAIR_INDICES).shape
            != pair_stage.tensor(TensorRole.PAIR_INDICES).shape
            or scorer_stage.tensor(TensorRole.PAIR_OFFSETS).shape
            != pair_stage.tensor(TensorRole.PAIR_OFFSETS).shape
            or scorer_stage.tensor(TensorRole.PAIR_OVERFLOW_FLAGS).shape
            != pair_stage.tensor(TensorRole.PAIR_OVERFLOW_FLAGS).shape
        ):
            raise BackendABIError(
                "pair-list and ScorerV1 stages must share one contract"
            )
        stable_top_k_stage = self.stage(EngineV2ABIStage.STABLE_TOP_K)
        if (
            stable_top_k_stage.tensor(TensorRole.TOTAL_SCORES).shape
            != scorer_stage.tensor(TensorRole.TOTAL_SCORES).shape
            or stable_top_k_stage.tensor(TensorRole.FAILURE_CODES).shape
            != scorer_stage.tensor(TensorRole.FAILURE_CODES).shape
        ):
            raise BackendABIError(
                "stable Top-K must consume the exact scorer denominator and failures"
            )
        batch_roles = (
            (EngineV2ABIStage.SCORER_V1_8TERM, TensorRole.SCORER_TERMS),
            (EngineV2ABIStage.POSE_VALIDITY, TensorRole.VALIDITY_FLAGS),
            (EngineV2ABIStage.STABLE_TOP_K, TensorRole.TOTAL_SCORES),
            (EngineV2ABIStage.REFINEMENT_V2, TensorRole.REFINEMENT_DECISIONS),
            (EngineV2ABIStage.REFINEMENT_V3, TensorRole.REFINEMENT_DECISIONS),
            (EngineV2ABIStage.REFINEMENT_V6, TensorRole.REFINEMENT_DECISIONS),
            (EngineV2ABIStage.REFINEMENT_V7, TensorRole.REFINEMENT_DECISIONS),
            (EngineV2ABIStage.CLUSTERING_RMSD, TensorRole.CLUSTER_LABELS),
        )
        if any(
            self.stage(stage).tensor(role).shape[0] != batch
            for stage, role in batch_roles
        ):
            raise BackendABIError("all native stages must bind one batch denominator")
        clustering_shape = (
            self.stage(EngineV2ABIStage.CLUSTERING_RMSD)
            .tensor(TensorRole.REFINED_COORDINATES)
            .shape
        )
        if clustering_shape != (batch, ligand_atoms, 3):
            raise BackendABIError(
                "clustering must consume the bound refined coordinates"
            )
        object.__setattr__(self, "_fingerprint_sha256", _sha256(self._projection()))

    def stage(self, stage: EngineV2ABIStage) -> StageABI:
        for value in self.stages:
            if value.stage is stage:
                return value
        raise BackendABIError(f"native ABI does not define {stage.value}")

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_NATIVE_ABI_SCHEMA_ID,
            "abi_version": self.abi_version,
            "backend": self.backend.value,
            "device_fingerprint_sha256": self.device.fingerprint_sha256,
            "stream_fingerprint_sha256": self.stream.fingerprint_sha256,
            "stage_fingerprint_sha256": [
                value.fingerprint_sha256 for value in self.stages
            ],
            "stage_order": [value.value for value in _STAGE_ORDER],
            "scorer_v1_term_names": list(SCORER_V1_TERM_NAMES),
            "max_batch_size": self.max_batch_size,
            "deterministic_required": self.deterministic_required,
            "fast_math_allowed": self.fast_math_allowed,
            "unsafe_fp_atomics_allowed": self.unsafe_fp_atomics_allowed,
            "implicit_fallback_allowed": self.implicit_fallback_allowed,
        }

    @property
    def fingerprint_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._fingerprint_sha256:
            raise BackendABIError("native execution ABI changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "device": self.device.to_dict(),
            "stream": self.stream.to_dict(),
            "stages": [value.to_dict() for value in self.stages],
            "fingerprint_sha256": self.fingerprint_sha256,
        }


def _contiguous_strides(dtype: TensorDType, shape: tuple[int, ...]) -> tuple[int, ...]:
    strides = [0] * len(shape)
    running = _DTYPE_ITEMSIZE[dtype]
    for index in range(len(shape) - 1, -1, -1):
        strides[index] = running
        running *= shape[index]
    return tuple(strides)


def build_engine_v2_native_abi(
    *,
    backend: EngineV2Backend,
    device: DeviceABI,
    stream: StreamABI,
    receptor_atom_count: int,
    receptor_feature_count: int,
    ligand_atom_count: int,
    pair_capacity: int,
    max_batch_size: int = 64,
) -> EngineV2NativeABI:
    """Build the only complete tensor-stage signature accepted by ABI v1."""

    counts = {
        "receptor_atom_count": receptor_atom_count,
        "receptor_feature_count": receptor_feature_count,
        "ligand_atom_count": ligand_atom_count,
        "max_batch_size": max_batch_size,
    }
    for name, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{name} must be an integer")
        if value <= 0:
            raise BackendABIError(f"{name} must be positive")
    if isinstance(pair_capacity, bool) or not isinstance(pair_capacity, int):
        raise TypeError("pair_capacity must be an integer")
    if pair_capacity < 0:
        raise BackendABIError("pair_capacity must be non-negative")

    batch = max_batch_size
    ligand = ligand_atom_count
    shapes: Mapping[EngineV2ABIStage, Mapping[TensorRole, tuple[int, ...]]] = {
        EngineV2ABIStage.PERSISTENT_RECEPTOR_CONTEXT: {
            TensorRole.RECEPTOR_COORDINATES: (receptor_atom_count, 3),
            TensorRole.RECEPTOR_FEATURES: (
                receptor_atom_count,
                receptor_feature_count,
            ),
            TensorRole.RECEPTOR_CONTEXT_METADATA: (4,),
        },
        EngineV2ABIStage.CANDIDATE_TRANSFORM_BATCH: {
            TensorRole.LIGAND_COORDINATES: (ligand, 3),
            TensorRole.CANDIDATE_TRANSFORMS: (batch, 7),
            TensorRole.CANDIDATE_COORDINATES: (batch, ligand, 3),
        },
        EngineV2ABIStage.PAIR_LIST: {
            TensorRole.CANDIDATE_COORDINATES: (batch, ligand, 3),
            TensorRole.PAIR_INDICES: (pair_capacity, 3),
            TensorRole.PAIR_OFFSETS: (batch + 1,),
            TensorRole.PAIR_OVERFLOW_FLAGS: (batch,),
        },
        EngineV2ABIStage.SCORER_V1_8TERM: {
            TensorRole.PAIR_INDICES: (pair_capacity, 3),
            TensorRole.PAIR_OFFSETS: (batch + 1,),
            TensorRole.PAIR_OVERFLOW_FLAGS: (batch,),
            TensorRole.SCORER_TERMS: (batch, len(SCORER_V1_TERM_NAMES)),
            TensorRole.TOTAL_SCORES: (batch,),
            TensorRole.FAILURE_CODES: (batch,),
        },
        EngineV2ABIStage.POSE_VALIDITY: {
            TensorRole.CANDIDATE_COORDINATES: (batch, ligand, 3),
            TensorRole.VALIDITY_FLAGS: (batch, 4),
            TensorRole.VALIDITY_REASON_CODES: (batch,),
        },
        EngineV2ABIStage.STABLE_TOP_K: {
            TensorRole.TOTAL_SCORES: (batch,),
            TensorRole.FAILURE_CODES: (batch,),
            TensorRole.VALIDITY_FLAGS: (batch, 4),
            TensorRole.TOPK_INDICES: (min(5, batch),),
            TensorRole.TOPK_SCORES: (min(5, batch),),
            TensorRole.TOPK_COUNT: (1,),
        },
        **{
            stage: {
                TensorRole.CANDIDATE_COORDINATES: (batch, ligand, 3),
                TensorRole.REFINED_COORDINATES: (batch, ligand, 3),
                TensorRole.REFINEMENT_DECISIONS: (batch,),
            }
            for stage in (
                EngineV2ABIStage.REFINEMENT_V2,
                EngineV2ABIStage.REFINEMENT_V3,
                EngineV2ABIStage.REFINEMENT_V6,
                EngineV2ABIStage.REFINEMENT_V7,
            )
        },
        EngineV2ABIStage.CLUSTERING_RMSD: {
            TensorRole.REFINED_COORDINATES: (batch, ligand, 3),
            TensorRole.CLUSTER_LABELS: (batch,),
            TensorRole.RMSD_MATRIX: (batch, batch),
        },
    }
    stages: list[StageABI] = []
    for stage in _STAGE_ORDER:
        tensors: list[TensorABI] = []
        for role, dtype, ownership, read_only in _STAGE_TENSOR_CONTRACTS[stage]:
            shape = shapes[stage][role]
            tensors.append(
                TensorABI(
                    role=role,
                    dtype=dtype,
                    shape=shape,
                    strides_bytes=_contiguous_strides(dtype, shape),
                    device_fingerprint_sha256=device.fingerprint_sha256,
                    ownership=ownership,
                    read_only=read_only,
                )
            )
        stages.append(StageABI(stage=stage, tensors=tuple(tensors)))
    canonical = canonical_backend(backend)
    return EngineV2NativeABI(
        backend=backend,
        device=device,
        stream=stream,
        stages=tuple(stages),
        max_batch_size=max_batch_size,
        fast_math_allowed=canonical is EngineV2Backend.HIP_FAST,
    )


@dataclass(frozen=True, slots=True)
class BackendSourceBinding:
    exact_source_receipt_sha256: str
    implementation_source_sha256: str
    algorithm_profile_id: str
    algorithm_profile_sha256: str
    execution_profile_id: str
    execution_profile_sha256: str
    native_build_provenance_sha256: str
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        for name in (
            "exact_source_receipt_sha256",
            "implementation_source_sha256",
            "algorithm_profile_sha256",
            "execution_profile_sha256",
            "native_build_provenance_sha256",
        ):
            object.__setattr__(self, name, _digest(getattr(self, name), name=name))
        for name in ("algorithm_profile_id", "execution_profile_id"):
            object.__setattr__(self, name, _non_empty(getattr(self, name), name=name))
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": "engine-v2-backend-source-binding-v1",
            "exact_source_receipt_sha256": self.exact_source_receipt_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "algorithm_profile_id": self.algorithm_profile_id,
            "algorithm_profile_sha256": self.algorithm_profile_sha256,
            "execution_profile_id": self.execution_profile_id,
            "execution_profile_sha256": self.execution_profile_sha256,
            "native_build_provenance_sha256": (self.native_build_provenance_sha256),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise BackendABIError("backend source binding changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(frozen=True, slots=True)
class EngineV2BackendReceipt:
    native_abi: EngineV2NativeABI
    source_binding: BackendSourceBinding
    backend_version: str
    execution_available: bool
    artifact_sha256: str = ""
    compiler_name: str = ""
    compiler_version: str = ""
    target_triple: str = ""
    build_flags: tuple[str, ...] = ()
    math_mode: MathMode = MathMode.STRICT_BINARY64
    deterministic: bool = True
    unsafe_fp_atomics: bool = False
    rocm_device_library_fallback_used: bool = False
    hip_safe_qualification_receipt_sha256: str = ""
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.native_abi, EngineV2NativeABI):
            raise TypeError("native_abi must be EngineV2NativeABI")
        if not isinstance(self.source_binding, BackendSourceBinding):
            raise TypeError("source_binding must be BackendSourceBinding")
        backend = self.native_abi.backend
        object.__setattr__(
            self,
            "backend_version",
            _non_empty(self.backend_version, name="backend_version"),
        )
        object.__setattr__(
            self,
            "artifact_sha256",
            _optional_digest(self.artifact_sha256, name="artifact_sha256"),
        )
        object.__setattr__(
            self,
            "hip_safe_qualification_receipt_sha256",
            _optional_digest(
                self.hip_safe_qualification_receipt_sha256,
                name="hip_safe_qualification_receipt_sha256",
            ),
        )
        for name in (
            "compiler_name",
            "compiler_version",
            "target_triple",
        ):
            object.__setattr__(self, name, str(getattr(self, name) or "").strip())
        flags = tuple(str(value).strip() for value in self.build_flags)
        if any(not value for value in flags) or len(flags) != len(set(flags)):
            raise BackendABIError("build_flags must be unique non-empty strings")
        object.__setattr__(self, "build_flags", flags)
        math_mode = self.math_mode
        if isinstance(math_mode, str):
            try:
                math_mode = MathMode(math_mode)
            except ValueError as exc:
                raise BackendABIError("unsupported math mode") from exc
            object.__setattr__(self, "math_mode", math_mode)
        if not isinstance(math_mode, MathMode):
            raise TypeError("math_mode must be MathMode")
        for name in (
            "execution_available",
            "deterministic",
            "unsafe_fp_atomics",
            "rocm_device_library_fallback_used",
        ):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be bool")
        if self.unsafe_fp_atomics:
            raise BackendABIError("unsafe floating-point atomics are forbidden")
        if self.rocm_device_library_fallback_used:
            raise BackendABIError("ROCm device-library fallback is forbidden")
        if not self.deterministic:
            raise BackendABIError(
                "all Engine V2 backend receipts must be deterministic"
            )
        native_build_fields = (
            self.artifact_sha256,
            self.compiler_name,
            self.compiler_version,
            self.target_triple,
        )
        if backend is EngineV2Backend.PYTHON_REFERENCE:
            if (
                any(native_build_fields)
                or self.build_flags
                or self.hip_safe_qualification_receipt_sha256
            ):
                raise BackendABIError("python reference cannot claim native build data")
        elif backend is EngineV2Backend.RUST_CPU:
            if not all(native_build_fields):
                raise BackendABIError(
                    "rust_cpu receipt requires complete native build data"
                )
            if self.hip_safe_qualification_receipt_sha256:
                raise BackendABIError("rust_cpu cannot claim HIP qualification")
        else:
            if self.execution_available:
                raise BackendABIError(
                    "HIP backends are declared unavailable in this contract version"
                )
            if not all(native_build_fields):
                raise BackendABIError("HIP receipt requires complete native build data")
            if self.compiler_name.lower() != "hipcc":
                raise BackendABIError("HIP receipt requires the exact hipcc compiler")
            if self.target_triple != "amdgcn-amd-amdhsa":
                raise BackendABIError("HIP receipt requires the exact AMDGPU target")
            if self.native_abi.device.runtime_name.lower() != "rocm":
                raise BackendABIError("HIP receipt requires an exact ROCm device ABI")
            if (
                backend is EngineV2Backend.HIP_SAFE
                and math_mode is not MathMode.STRICT_BINARY64
            ):
                raise BackendABIError(
                    "hip_safe receipt requires deterministic strict math"
                )
            if (
                backend is EngineV2Backend.HIP_FAST
                and not self.hip_safe_qualification_receipt_sha256
            ):
                raise BackendABIError(
                    "hip_fast receipt requires prior hip_safe qualification"
                )
            if (
                backend is EngineV2Backend.HIP_FAST
                and math_mode is not MathMode.PARITY_QUALIFIED_FAST
            ):
                raise BackendABIError(
                    "hip_fast receipt requires parity-qualified fast math"
                )
            expected_flags = (
                HIP_SAFE_BUILD_FLAGS
                if backend is EngineV2Backend.HIP_SAFE
                else HIP_FAST_BUILD_FLAGS
            )
            if self.build_flags != expected_flags:
                raise BackendABIError(
                    f"{backend.value} requires its exact predeclared build profile"
                )
        if (
            backend is not EngineV2Backend.HIP_FAST
            and math_mode is not MathMode.STRICT_BINARY64
        ):
            raise BackendABIError(
                "python_reference, rust_cpu, and hip_safe require deterministic strict math"
            )
        if (
            backend is EngineV2Backend.HIP_FAST
            and not self.native_abi.fast_math_allowed
        ):
            raise BackendABIError("hip_fast receipt and ABI math modes do not match")
        if (
            backend is not EngineV2Backend.HIP_FAST
            and self.native_abi.fast_math_allowed
        ):
            raise BackendABIError(
                "strict backend receipt and ABI math modes do not match"
            )
        object.__setattr__(self, "_receipt_sha256", _sha256(self._projection()))

    @property
    def backend(self) -> EngineV2Backend:
        return self.native_abi.backend

    @property
    def abi_fingerprint_sha256(self) -> str:
        return self.native_abi.fingerprint_sha256

    @property
    def implementation_source_sha256(self) -> str:
        return self.source_binding.implementation_source_sha256

    @property
    def architecture(self) -> str:
        return self.native_abi.device.architecture

    @property
    def runtime_name(self) -> str:
        return self.native_abi.device.runtime_name

    @property
    def runtime_version(self) -> str:
        return self.native_abi.device.runtime_version

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": ENGINE_V2_BACKEND_RECEIPT_SCHEMA_ID,
            "backend": self.backend.value,
            "backend_version": self.backend_version,
            "abi_fingerprint_sha256": self.abi_fingerprint_sha256,
            "implementation_source_sha256": self.implementation_source_sha256,
            "source_binding_receipt_sha256": self.source_binding.receipt_sha256,
            "execution_available": self.execution_available,
            "artifact_sha256": self.artifact_sha256,
            "compiler_name": self.compiler_name,
            "compiler_version": self.compiler_version,
            "target_triple": self.target_triple,
            "runtime_name": self.runtime_name,
            "runtime_version": self.runtime_version,
            "architecture": self.architecture,
            "build_flags": list(self.build_flags),
            "math_mode": self.math_mode.value,
            "deterministic": self.deterministic,
            "unsafe_fp_atomics": self.unsafe_fp_atomics,
            "rocm_device_library_fallback_used": (
                self.rocm_device_library_fallback_used
            ),
            "hip_safe_qualification_receipt_sha256": (
                self.hip_safe_qualification_receipt_sha256
            ),
            "implicit_fallback_allowed": False,
            "build_profile_sha256": (
                HIP_SAFE_BUILD_PROFILE_SHA256
                if self.backend is EngineV2Backend.HIP_SAFE
                else (
                    HIP_FAST_BUILD_PROFILE_SHA256
                    if self.backend is EngineV2Backend.HIP_FAST
                    else ""
                )
            ),
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256(self._projection())
        if observed != self._receipt_sha256:
            raise BackendABIError("backend receipt changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {
            **self._projection(),
            "native_abi": self.native_abi.to_dict(),
            "source_binding": self.source_binding.to_dict(),
            "receipt_sha256": self.receipt_sha256,
        }


__all__ = [
    "BackendSourceBinding",
    "BackendABIError",
    "DeviceABI",
    "DeviceKind",
    "ENGINE_V2_BACKEND_RECEIPT_SCHEMA_ID",
    "ENGINE_V2_NATIVE_ABI_SCHEMA_ID",
    "ENGINE_V2_NATIVE_ABI_VERSION",
    "EngineV2ABIStage",
    "EngineV2Backend",
    "EngineV2BackendReceipt",
    "EngineV2NativeABI",
    "HIP_BACKENDS",
    "HIP_FAST_BUILD_FLAGS",
    "HIP_FAST_BUILD_PROFILE_SHA256",
    "HIP_SAFE_BUILD_FLAGS",
    "HIP_SAFE_BUILD_PROFILE_SHA256",
    "LEGACY_SCORER_BACKEND_ALIASES",
    "MathMode",
    "StreamABI",
    "StreamKind",
    "StreamOwnership",
    "StageABI",
    "SynchronizationProtocol",
    "TensorABI",
    "TensorDType",
    "TensorOwnership",
    "TensorRole",
    "build_engine_v2_native_abi",
    "canonical_backend",
    "compatibility_alias",
]
