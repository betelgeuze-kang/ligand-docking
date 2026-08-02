"""Consumer-agnostic docking pipeline orchestration.

The pipeline owns sequencing and evidence linkage while injected collaborators
own scientific behavior.  CLI, benchmark, API, and product-shadow adapters can
therefore call the same orchestration core without importing one another.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import inspect
import json
import math
from pathlib import Path
from types import CodeType, MappingProxyType, ModuleType
from typing import Mapping, Protocol, runtime_checkable


DOCKING_PIPELINE_PROFILE_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_profile/1.0.0"
)
DOCKING_PIPELINE_EXECUTION_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_execution/1.0.0"
)
DOCKING_PIPELINE_COMPONENT_PROFILE_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_component_profile/1.0.0"
)
DOCKING_PIPELINE_STAGE_OUTPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_stage_output/1.0.0"
)
VERIFIED_DOCKING_PIPELINE_EXECUTION_SCHEMA_ID = (
    "betelgeuze.verified_engine_v2_docking_pipeline_execution/1.0.0"
)
DOCKING_PIPELINE_SOURCE_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_source_binding/1.0.0"
)
DOCKING_PIPELINE_RESULT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_result_binding/1.0.0"
)
DOCKING_PIPELINE_RECORDED_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_recorded_evidence/1.0.0"
)
DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_pipeline_candidate_evidence/1.0.0"
)
_PUBLIC_CANDIDATE_SCHEMA_IDS = frozenset(
    {
        "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0",
        "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.7.0",
    }
)
MAX_PIPELINE_COMPONENT_SOURCE_BYTES = 8 * 1024 * 1024
_EXECUTION_ORDER = (
    "input_preparer.prepare",
    "conformer_provider.provide",
    "proposal_generator.generate",
    "geometric_admission.admit",
    "scorer.bind",
    "refiner.refine",
    "scorer.score",
    "validity_evaluator.evaluate",
    "ranker.rank",
    "evidence_recorder.record",
)
_EXECUTION_STAGE_ROLES = {
    stage_name: stage_name.split(".", 1)[0] for stage_name in _EXECUTION_ORDER
}
_ROLE_METHODS = {
    "input_preparer": ("prepare",),
    "conformer_provider": ("provide",),
    "proposal_generator": ("generate",),
    "geometric_admission": ("admit",),
    "scorer": ("bind", "score"),
    "refiner": ("refine",),
    "validity_evaluator": ("evaluate",),
    "ranker": ("rank",),
    "evidence_recorder": ("record",),
}


class DockingPipelineError(RuntimeError):
    """A pipeline collaborator violated the shared execution contract."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise DockingPipelineError("pipeline evidence is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _component_source_freeze_sha256(component: object) -> str:
    source_name = inspect.getsourcefile(component.__class__)
    if not source_name:
        raise DockingPipelineError("pipeline component source file is unavailable")
    path = Path(source_name)
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DockingPipelineError(
            "pipeline component source file cannot be read"
        ) from exc
    if not payload or len(payload) > MAX_PIPELINE_COMPONENT_SOURCE_BYTES:
        raise DockingPipelineError("pipeline component source file is outside bounds")
    return hashlib.sha256(payload).hexdigest()


def _code_constant(value: object) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            return {"kind": "float", "binary64_hex": value.hex()}
        return {"kind": "float", "binary64_hex": value.hex()}
    if type(value) is complex:
        return {
            "kind": "complex",
            "real_binary64_hex": value.real.hex(),
            "imag_binary64_hex": value.imag.hex(),
        }
    if isinstance(value, bytes):
        return {"kind": "bytes", "hex": value.hex()}
    if isinstance(value, tuple):
        return {"kind": "tuple", "items": [_code_constant(item) for item in value]}
    if isinstance(value, frozenset):
        items = [_code_constant(item) for item in value]
        return {
            "kind": "frozenset",
            "items": sorted(items, key=lambda item: _canonical_bytes(item)),
        }
    if isinstance(value, CodeType):
        return {"kind": "code", "value": _code_projection(value)}
    if value is Ellipsis:
        return {"kind": "ellipsis"}
    raise DockingPipelineError(
        f"pipeline bytecode contains unsupported constant {type(value).__qualname__}"
    )


def _code_projection(code: CodeType) -> dict[str, object]:
    """Return a process- and checkout-location-independent code fingerprint."""

    return {
        "name": code.co_name,
        "qualname": getattr(code, "co_qualname", code.co_name),
        "code_hex": code.co_code.hex(),
        "constants": [_code_constant(value) for value in code.co_consts],
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
        "freevars": list(code.co_freevars),
        "cellvars": list(code.co_cellvars),
        "argument_count": code.co_argcount,
        "positional_only_argument_count": code.co_posonlyargcount,
        "keyword_only_argument_count": code.co_kwonlyargcount,
        "local_count": code.co_nlocals,
        "stack_size": code.co_stacksize,
        "flags": code.co_flags,
    }


def _component_configuration(role: str, component: object) -> dict[str, object]:
    method = getattr(component, "pipeline_configuration", None)
    if not callable(method):
        raise DockingPipelineError(
            f"pipeline {role} must declare canonical immutable configuration"
        )
    configuration = method()
    if not isinstance(configuration, Mapping):
        raise DockingPipelineError(f"pipeline {role} configuration must be a mapping")
    payload = _canonical_bytes(dict(configuration))
    if len(payload) > 64 * 1024:
        raise DockingPipelineError(f"pipeline {role} configuration is too large")
    return json.loads(payload.decode("ascii"))


def _source_binding(value: object, *, depth: int = 0) -> object:
    """Project referenced runtime globals without trusting their object identity."""

    if depth > 8:
        return {"kind": "depth_limit", "type": type(value).__qualname__}
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise DockingPipelineError(
                "pipeline callable references a non-finite global"
            )
        return {"kind": "float", "binary64_hex": value.hex()}
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, (tuple, list)):
        return {
            "kind": type(value).__name__,
            "items": [_source_binding(item, depth=depth + 1) for item in value],
        }
    if isinstance(value, (set, frozenset)):
        items = [_source_binding(item, depth=depth + 1) for item in value]
        return {
            "kind": type(value).__name__,
            "items": sorted(items, key=lambda item: _canonical_bytes(item)),
        }
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise DockingPipelineError(
                "pipeline callable references a mapping with non-string keys"
            )
        return {
            "kind": "mapping",
            "items": {
                key: _source_binding(item, depth=depth + 1)
                for key, item in sorted(value.items())
            },
        }
    if isinstance(value, ModuleType):
        source_path = getattr(value, "__file__", None)
        source_sha256 = ""
        if isinstance(source_path, str) and Path(source_path).is_file():
            source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        return {
            "kind": "module",
            "module": str(getattr(value, "__name__", "")),
            "source_sha256": source_sha256,
        }
    if inspect.ismethod(value):
        value = value.__func__
    if inspect.isfunction(value) or inspect.isbuiltin(value):
        code = getattr(value, "__code__", None)
        source_path = (
            inspect.getsourcefile(value) if inspect.isfunction(value) else None
        )
        source_sha256 = ""
        if source_path and Path(source_path).is_file():
            source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        return {
            "kind": "callable",
            "module": str(getattr(value, "__module__", "")),
            "qualname": str(getattr(value, "__qualname__", "")),
            "code_sha256": (
                _sha256(_code_projection(code)) if code is not None else ""
            ),
            "source_sha256": source_sha256,
        }
    if inspect.isclass(value):
        source_path = inspect.getsourcefile(value)
        source_sha256 = ""
        if source_path and Path(source_path).is_file():
            source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
        return {
            "kind": "class",
            "module": str(getattr(value, "__module__", "")),
            "qualname": str(getattr(value, "__qualname__", "")),
            "source_sha256": source_sha256,
        }
    return {
        "kind": "typed_value",
        "type": f"{type(value).__module__}.{type(value).__qualname__}",
        "stable_text": str(value),
    }


def _callable_runtime_bindings(method: object) -> dict[str, object]:
    function = getattr(method, "__func__", method)
    try:
        closure = inspect.getclosurevars(function)
    except TypeError as exc:
        raise DockingPipelineError(
            "pipeline callable runtime bindings are unavailable"
        ) from exc
    return {
        "globals": {
            name: _source_binding(value)
            for name, value in sorted(closure.globals.items())
        },
        "nonlocals": {
            name: _source_binding(value)
            for name, value in sorted(closure.nonlocals.items())
        },
        "unbound": sorted(closure.unbound),
    }


def _component_implementation_sha256(role: str, component: object) -> str:
    declared = getattr(component, "implementation_sha256", None)
    if declared is not None and (
        not isinstance(declared, str)
        or len(declared) != 64
        or any(character not in "0123456789abcdef" for character in declared)
    ):
        raise DockingPipelineError(
            f"pipeline {role} declared implementation SHA-256 is invalid"
        )
    callables: list[dict[str, object]] = []
    for method_name in _ROLE_METHODS[role]:
        method = getattr(component, method_name, None)
        if not callable(method):
            raise DockingPipelineError(f"pipeline {role}.{method_name} is not callable")
        function = getattr(method, "__func__", method)
        code = getattr(function, "__code__", None)
        callables.append(
            {
                "method": method_name,
                "module": str(getattr(function, "__module__", "")),
                "qualname": str(getattr(function, "__qualname__", "")),
                "code": _code_projection(code) if code is not None else None,
                "runtime_bindings": _callable_runtime_bindings(method),
            }
        )
    return _sha256(
        {
            "role": role,
            "component_type": (
                f"{component.__class__.__module__}.{component.__class__.__qualname__}"
            ),
            "declared_implementation_sha256": declared or "",
            "callables": callables,
        }
    )


def _component_profile_document(role: str, component: object) -> dict[str, object]:
    component_id = str(getattr(component, "component_id", "") or "").strip()
    configuration = _component_configuration(role, component)
    projection: dict[str, object] = {
        "schema_id": DOCKING_PIPELINE_COMPONENT_PROFILE_SCHEMA_ID,
        "role": role,
        "component_id": component_id,
        "implementation_sha256": _component_implementation_sha256(role, component),
        "source_freeze_sha256": _component_source_freeze_sha256(component),
        "configuration": configuration,
        "configuration_sha256": _sha256(configuration),
    }
    projection["receipt_sha256"] = _sha256(projection)
    return projection


def validate_docking_pipeline_profile_document(
    document: Mapping[str, object],
) -> dict[str, object]:
    """Validate and return a detached exact DockingPipeline profile document."""

    if not isinstance(document, Mapping):
        raise DockingPipelineError("pipeline profile document must be a mapping")
    profile = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "profile_id",
        "components",
        "execution_order",
        "failure_complete_required",
        "candidate_denominator_preservation_required",
        "consumer_agnostic",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "profile_sha256",
    }
    if set(profile) != expected_fields:
        raise DockingPipelineError("pipeline profile fields are invalid")
    if profile.get("schema_id") != DOCKING_PIPELINE_PROFILE_SCHEMA_ID:
        raise DockingPipelineError("pipeline profile schema is invalid")
    if profile.get("execution_order") != list(_EXECUTION_ORDER):
        raise DockingPipelineError("pipeline execution order is invalid")
    components = profile.get("components")
    if not isinstance(components, dict) or set(components) != set(_ROLE_METHODS):
        raise DockingPipelineError("pipeline component roles are invalid")
    component_fields = {
        "schema_id",
        "role",
        "component_id",
        "implementation_sha256",
        "source_freeze_sha256",
        "configuration",
        "configuration_sha256",
        "receipt_sha256",
    }
    for role, raw in components.items():
        if not isinstance(raw, dict) or set(raw) != component_fields:
            raise DockingPipelineError("pipeline component profile fields are invalid")
        if (
            raw.get("schema_id") != DOCKING_PIPELINE_COMPONENT_PROFILE_SCHEMA_ID
            or raw.get("role") != role
            or not isinstance(raw.get("component_id"), str)
            or not raw["component_id"]
            or not isinstance(raw.get("configuration"), dict)
            or raw.get("configuration_sha256") != _sha256(raw["configuration"])
        ):
            raise DockingPipelineError("pipeline component profile is invalid")
        for digest_name in (
            "implementation_sha256",
            "source_freeze_sha256",
            "configuration_sha256",
            "receipt_sha256",
        ):
            digest = raw.get(digest_name)
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise DockingPipelineError("pipeline component digest is invalid")
        component_projection = dict(raw)
        component_receipt = component_projection.pop("receipt_sha256")
        if _sha256(component_projection) != component_receipt:
            raise DockingPipelineError("pipeline component receipt is invalid")
    if any(
        profile.get(name) is not expected
        for name, expected in {
            "failure_complete_required": True,
            "candidate_denominator_preservation_required": True,
            "consumer_agnostic": True,
            "scientifically_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }.items()
    ):
        raise DockingPipelineError("pipeline authority flags are invalid")
    projection = dict(profile)
    profile_sha256 = projection.pop("profile_sha256", None)
    if _sha256(projection) != profile_sha256:
        raise DockingPipelineError("pipeline profile SHA-256 is invalid")
    return profile


def _require_sha256(value: object, *, name: str) -> str:
    digest = str(value or "").strip().lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise DockingPipelineError(f"{name} must be a SHA-256")
    return digest


def _detached_mapping(
    value: Mapping[str, object],
    *,
    name: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DockingPipelineError(f"{name} must be a mapping")
    detached = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if not isinstance(detached, dict):
        raise DockingPipelineError(f"{name} must be a JSON object")
    return MappingProxyType(detached)


@dataclass(frozen=True, slots=True)
class DockingPipelineStagePayload:
    """One collaborator-owned runtime value and its canonical integrity evidence.

    The pipeline, rather than a consumer adapter, seals this payload to the exact
    component profile and upstream stage receipts.  ``value`` deliberately stays
    runtime-only; ``integrity`` must contain the scientific receipts or immutable
    fingerprints that bind that value.
    """

    value: object
    evidence: Mapping[str, object]
    integrity: Mapping[str, object]
    candidate_ids: tuple[str, ...] = ()
    candidate_count: int | None = None

    def __post_init__(self) -> None:
        evidence = _detached_mapping(self.evidence, name="pipeline stage evidence")
        integrity = _detached_mapping(
            self.integrity,
            name="pipeline stage integrity evidence",
        )
        candidate_ids = tuple(str(value or "").strip() for value in self.candidate_ids)
        if any(not value or len(value) > 512 for value in candidate_ids):
            raise DockingPipelineError("pipeline candidate identity is invalid")
        if len(candidate_ids) != len(set(candidate_ids)):
            raise DockingPipelineError("pipeline candidate identities are not unique")
        count = self.candidate_count
        if count is None:
            if candidate_ids:
                raise DockingPipelineError(
                    "pipeline candidate identities require a denominator"
                )
        elif type(count) is not int or count < 0 or count != len(candidate_ids):
            raise DockingPipelineError(
                "pipeline candidate denominator and identities disagree"
            )
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "integrity", integrity)
        object.__setattr__(self, "candidate_ids", candidate_ids)


def docking_pipeline_stage_payload(
    value: object,
    *,
    evidence: Mapping[str, object],
    integrity: Mapping[str, object],
    candidate_ids: tuple[str, ...] = (),
    candidate_count: int | None = None,
) -> DockingPipelineStagePayload:
    """Build the only accepted collaborator return type."""

    return DockingPipelineStagePayload(
        value=value,
        evidence=evidence,
        integrity=integrity,
        candidate_ids=candidate_ids,
        candidate_count=candidate_count,
    )


_VERIFIED_STAGE_FACTORY_AUTHORITY = object()
_VERIFIED_EXECUTION_FACTORY_AUTHORITY = object()


class VerifiedDockingPipelineStageOutput:
    """Factory-only, profile-bound output of exactly one pipeline callback."""

    __slots__ = (
        "_candidate_binding_sha256",
        "_candidate_count",
        "_candidate_ids",
        "_evidence",
        "_integrity",
        "_owner_component_id",
        "_owner_component_receipt_sha256",
        "_owner_role",
        "_payload",
        "_receipt_sha256",
        "_stage_name",
        "_upstream_receipt_sha256s",
    )

    def __init__(
        self,
        *,
        authority: object,
        stage_name: str,
        owner_role: str,
        owner_component_id: str,
        owner_component_receipt_sha256: str,
        upstream_receipt_sha256s: tuple[str, ...],
        payload: DockingPipelineStagePayload,
    ) -> None:
        if authority is not _VERIFIED_STAGE_FACTORY_AUTHORITY:
            raise DockingPipelineError(
                "verified pipeline stages are created only by DockingPipeline"
            )
        stage = str(stage_name or "").strip()
        if stage not in _EXECUTION_ORDER:
            raise DockingPipelineError("pipeline stage name is invalid")
        if owner_role not in _ROLE_METHODS or not isinstance(
            payload,
            DockingPipelineStagePayload,
        ):
            raise DockingPipelineError("pipeline stage owner or payload is invalid")
        component_id = str(owner_component_id or "").strip()
        if not component_id:
            raise DockingPipelineError("pipeline stage component ID is invalid")
        component_receipt = _require_sha256(
            owner_component_receipt_sha256,
            name="pipeline stage component receipt",
        )
        upstream = tuple(
            _require_sha256(value, name="pipeline upstream stage receipt")
            for value in upstream_receipt_sha256s
        )
        candidate_binding = _sha256(
            {
                "candidate_count": payload.candidate_count,
                "candidate_ids": list(payload.candidate_ids),
            }
        )
        self._stage_name = stage
        self._owner_role = owner_role
        self._owner_component_id = component_id
        self._owner_component_receipt_sha256 = component_receipt
        self._upstream_receipt_sha256s = upstream
        self._payload = payload
        self._evidence = payload.evidence
        self._integrity = payload.integrity
        self._candidate_ids = payload.candidate_ids
        self._candidate_count = payload.candidate_count
        self._candidate_binding_sha256 = candidate_binding
        self._receipt_sha256 = _sha256(self._projection())

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": DOCKING_PIPELINE_STAGE_OUTPUT_SCHEMA_ID,
            "stage_name": self._stage_name,
            "owner_role": self._owner_role,
            "owner_component_id": self._owner_component_id,
            "owner_component_receipt_sha256": (self._owner_component_receipt_sha256),
            "upstream_receipt_sha256s": list(self._upstream_receipt_sha256s),
            "evidence": dict(self._evidence),
            "evidence_sha256": _sha256(dict(self._evidence)),
            "runtime_integrity": dict(self._integrity),
            "runtime_integrity_sha256": _sha256(dict(self._integrity)),
            "candidate_count": self._candidate_count,
            "candidate_ids": list(self._candidate_ids),
            "candidate_binding_sha256": self._candidate_binding_sha256,
            "runtime_value_serialized": False,
            "factory_verified": True,
            "claim_safe": False,
        }

    def assert_integrity(self) -> None:
        if not isinstance(self._payload, DockingPipelineStagePayload):
            raise DockingPipelineError("pipeline stage payload changed")
        if (
            self._payload.evidence is not self._evidence
            or self._payload.integrity is not (self._integrity)
        ):
            raise DockingPipelineError("pipeline stage evidence changed")
        if (
            self._payload.candidate_ids != self._candidate_ids
            or self._payload.candidate_count != self._candidate_count
            or _sha256(self._projection()) != self._receipt_sha256
        ):
            raise DockingPipelineError("pipeline stage integrity check failed")

    @property
    def stage_name(self) -> str:
        self.assert_integrity()
        return self._stage_name

    @property
    def owner_role(self) -> str:
        self.assert_integrity()
        return self._owner_role

    @property
    def value(self) -> object:
        self.assert_integrity()
        return self._payload.value

    @property
    def evidence(self) -> Mapping[str, object]:
        self.assert_integrity()
        return self._evidence

    @property
    def integrity(self) -> Mapping[str, object]:
        self.assert_integrity()
        return self._integrity

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        self.assert_integrity()
        return self._candidate_ids

    @property
    def candidate_count(self) -> int | None:
        self.assert_integrity()
        return self._candidate_count

    @property
    def candidate_binding_sha256(self) -> str:
        self.assert_integrity()
        return self._candidate_binding_sha256

    @property
    def receipt_sha256(self) -> str:
        self.assert_integrity()
        return self._receipt_sha256

    def to_dict(self) -> dict[str, object]:
        self.assert_integrity()
        return {**self._projection(), "receipt_sha256": self._receipt_sha256}


def require_pipeline_stage(
    value: object,
    *,
    stage_name: str,
) -> VerifiedDockingPipelineStageOutput:
    """Fail closed when a collaborator is handed raw or cross-wired input."""

    if not isinstance(value, VerifiedDockingPipelineStageOutput):
        raise DockingPipelineError("pipeline collaborator received an unverified stage")
    value.assert_integrity()
    if value.stage_name != stage_name:
        raise DockingPipelineError("pipeline collaborator received a cross-wired stage")
    return value


def build_docking_pipeline_source_binding(
    *,
    request_receipt_sha256: str,
    source_receipt_sha256: str,
    source_artifact_sha256s: Mapping[str, str],
) -> dict[str, object]:
    """Build one exact, self-hashed source authority for a recorded execution."""

    artifacts = dict(source_artifact_sha256s)
    if not artifacts or any(
        not isinstance(role, str)
        or not role.strip()
        or _require_sha256(digest, name="source artifact") != digest
        for role, digest in artifacts.items()
    ):
        raise DockingPipelineError("pipeline source artifact binding is invalid")
    projection: dict[str, object] = {
        "schema_id": DOCKING_PIPELINE_SOURCE_BINDING_SCHEMA_ID,
        "request_receipt_sha256": _require_sha256(
            request_receipt_sha256,
            name="pipeline request receipt",
        ),
        "source_receipt_sha256": _require_sha256(
            source_receipt_sha256,
            name="pipeline source receipt",
        ),
        "source_artifact_sha256s": {
            role: artifacts[role] for role in sorted(artifacts)
        },
        "exact_source_required": True,
    }
    projection["receipt_sha256"] = _sha256(projection)
    return projection


def _validate_source_binding(document: object) -> dict[str, object]:
    if not isinstance(document, Mapping):
        raise DockingPipelineError("pipeline source binding must be a mapping")
    binding = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    if set(binding) != {
        "schema_id",
        "request_receipt_sha256",
        "source_receipt_sha256",
        "source_artifact_sha256s",
        "exact_source_required",
        "receipt_sha256",
    }:
        raise DockingPipelineError("pipeline source binding fields are invalid")
    expected = build_docking_pipeline_source_binding(
        request_receipt_sha256=binding.get("request_receipt_sha256", ""),
        source_receipt_sha256=binding.get("source_receipt_sha256", ""),
        source_artifact_sha256s=binding.get("source_artifact_sha256s", {}),
    )
    if binding != expected:
        raise DockingPipelineError("pipeline source binding receipt is invalid")
    return binding


def _validated_public_source_candidate(
    value: object,
) -> dict[str, object]:
    """Validate only neutral wrapper links; runner owns source-schema semantics."""

    if not isinstance(value, Mapping):
        raise DockingPipelineError("pipeline source candidate must be a mapping")
    source = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    if (
        source.get("schema_id") not in _PUBLIC_CANDIDATE_SCHEMA_IDS
        or source.get("status") not in {"success", "failure"}
        or type(source.get("proposal_index")) is not int
        or source["proposal_index"] < 0
    ):
        raise DockingPipelineError("pipeline source candidate identity is invalid")
    if (
        source["status"] == "failure"
        and not str(source.get("error_code") or "").strip()
    ):
        raise DockingPipelineError("failed source candidate lacks an error code")
    return source


def _validated_full_scorer_v1_terms(
    value: object,
    *,
    source_candidate: Mapping[str, object],
) -> dict[str, object]:
    """Validate one complete 1.1 ScorerV1Terms receipt and its source links."""

    from .docking.scorer_v1 import (
        SCORER_V1_SCORE_ID,
        SCORER_V1_TERMS_SCHEMA_ID,
    )

    if not isinstance(value, Mapping):
        raise DockingPipelineError(
            "successful public candidate lacks full ScorerV1Terms"
        )
    terms = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    term_names = (
        "typed_vdw",
        "electrostatics",
        "directional_hbond",
        "hydrophobic_contact",
        "desolvation_proxy",
        "torsion_energy",
        "ligand_strain",
        "weak_pocket_prior",
        "total_score",
    )
    digest_names = (
        "proposal_fingerprint_sha256",
        "authority_input_receipt_sha256",
        "context_fingerprint_sha256",
        "config_fingerprint_sha256",
        "backend_receipt_sha256",
    )
    count_names = (
        "receptor_candidate_pair_count",
        "ligand_pair_count",
        "hbond_count",
        "hydrophobic_contact_count",
        "buried_polar_count",
    )
    expected_fields = {
        "schema_id",
        "score_id",
        *digest_names,
        *(f"{name}_binary64_hex" for name in term_names),
        *count_names,
        "calibrated",
        "scientifically_validated",
        "claim_safe",
        "receipt_sha256",
    }
    if (
        set(terms) != expected_fields
        or terms.get("schema_id") != SCORER_V1_TERMS_SCHEMA_ID
        or terms.get("score_id") != SCORER_V1_SCORE_ID
        or terms.get("calibrated") is not False
        or terms.get("scientifically_validated") is not False
        or terms.get("claim_safe") is not False
    ):
        raise DockingPipelineError("ScorerV1Terms receipt fields are not exact")
    for name in digest_names:
        _require_sha256(terms.get(name), name=f"ScorerV1Terms {name}")
    for name in count_names:
        count = terms.get(name)
        if type(count) is not int or count < 0:
            raise DockingPipelineError("ScorerV1Terms pair counts are invalid")
    decoded: dict[str, float] = {}
    try:
        for name in term_names:
            encoded = terms[f"{name}_binary64_hex"]
            if not isinstance(encoded, str):
                raise ValueError
            decoded[name] = float.fromhex(encoded)
            if not math.isfinite(decoded[name]) or decoded[name].hex() != encoded:
                raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise DockingPipelineError("ScorerV1Terms values are invalid") from exc
    if not math.isclose(
        decoded["total_score"],
        sum(decoded[name] for name in term_names[:-1]),
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise DockingPipelineError("ScorerV1Terms total is inconsistent")
    projection = dict(terms)
    receipt = _require_sha256(
        projection.pop("receipt_sha256", ""),
        name="ScorerV1Terms receipt",
    )
    source_terms_receipt = _require_sha256(
        source_candidate.get("score_terms_receipt_sha256"),
        name="source candidate ScorerV1Terms receipt",
    )
    source_term_values = source_candidate.get("score_term_binary64_hex")
    if (
        _sha256(projection) != receipt
        or receipt != source_terms_receipt
        or terms["proposal_fingerprint_sha256"]
        != source_candidate.get("proposal_fingerprint_sha256")
        or not isinstance(source_term_values, dict)
        or source_term_values
        != {name: terms[f"{name}_binary64_hex"] for name in term_names}
        or source_candidate.get("hbond_count") != terms["hbond_count"]
        or type(source_candidate.get("score")) is not float
        or source_candidate["score"].hex() != terms["total_score_binary64_hex"]
    ):
        raise DockingPipelineError(
            "ScorerV1Terms receipt is cross-wired to the source candidate"
        )
    return terms


def _validated_full_refinement_receipt(
    value: object,
    *,
    source_candidate: Mapping[str, object],
) -> dict[str, object]:
    """Validate full V7/source-paired refinement evidence and exact linkage."""

    from .docking.torsion_contact_refinement import (
        INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID,
        INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID,
    )

    if not isinstance(value, Mapping):
        raise DockingPipelineError(
            "successful public candidate lacks a full refinement receipt"
        )
    refinement = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    source_schema = source_candidate.get("schema_id")
    allowed_schemas = (
        {INTERACTION_AWARE_TORSION_CONTACT_RECEIPT_V7_SCHEMA_ID}
        if source_schema
        == "betelgeuze.engine_v2_public_redocking_engine_v2_candidate/1.6.0"
        else {INTERACTION_AWARE_SOURCE_PAIRED_TORSION_RESCUE_RECEIPT_SCHEMA_ID}
    )
    if refinement.get("schema_id") not in allowed_schemas:
        raise DockingPipelineError("public candidate refinement is not V7 authority")
    projection = dict(refinement)
    receipt = _require_sha256(
        projection.pop("receipt_sha256", ""),
        name="full refinement receipt",
    )
    source_receipt = _require_sha256(
        source_candidate.get("refinement_receipt_sha256"),
        name="source candidate refinement receipt",
    )
    source_payload = source_candidate.get("refinement_receipt_payload")
    summary_pairs = (
        ("refinement_initial_penalty_binary64_hex", "initial_penalty_binary64_hex"),
        ("refinement_final_penalty_binary64_hex", "final_penalty_binary64_hex"),
        ("refinement_accepted_steps", "accepted_steps"),
        ("refinement_original_pose_valid", "original_pose_valid"),
        ("refinement_total_translation_binary64_hex", "total_translation_binary64_hex"),
    )
    if (
        _sha256(projection) != receipt
        or receipt != source_receipt
        or not isinstance(source_payload, dict)
        or source_payload != refinement
        or (
            "post_coordinates_sha256" in refinement
            and refinement["post_coordinates_sha256"]
            != source_candidate.get("coordinate_fingerprint_sha256")
        )
        or any(
            source_candidate.get(source_name) != refinement.get(receipt_name)
            for source_name, receipt_name in summary_pairs
        )
        or source_candidate.get("refinement_accepted_rotation_steps")
        != refinement.get("accepted_rotation_steps", 0)
        or source_candidate.get("refinement_total_rotation_vector_binary64_hex")
        != refinement.get(
            "total_rotation_vector_binary64_hex",
            [(0.0).hex(), (0.0).hex(), (0.0).hex()],
        )
    ):
        raise DockingPipelineError(
            "full refinement receipt is cross-wired to the source candidate"
        )
    return refinement


def _validated_baseline_disagreement(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise DockingPipelineError("pipeline baseline disagreement is invalid")
    disagreement = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    available = disagreement.get("available")
    if available is False:
        if (
            set(disagreement) != {"available", "reason"}
            or not isinstance(disagreement.get("reason"), str)
            or not disagreement["reason"].strip()
        ):
            raise DockingPipelineError(
                "unavailable baseline disagreement fields are not exact"
            )
    elif available is True:
        reasons = disagreement.get("reason_codes")
        if (
            set(disagreement) != {"available", "disagrees", "reason_codes"}
            or type(disagreement.get("disagrees")) is not bool
            or not isinstance(reasons, list)
            or any(
                not isinstance(reason, str) or not reason.strip() for reason in reasons
            )
            or len(reasons) != len(set(reasons))
            or bool(reasons) != disagreement["disagrees"]
        ):
            raise DockingPipelineError(
                "available baseline disagreement fields are not exact"
            )
    else:
        raise DockingPipelineError("baseline availability must be explicit")
    return disagreement


def _validated_public_candidate_evidence_row(
    value: object,
    *,
    expected_index: int,
    expected_candidate_id: str | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise DockingPipelineError("pipeline public candidate row is invalid")
    row = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected_fields = {
        "schema_id",
        "source_candidate_schema_id",
        "source_candidate_sha256",
        "source_candidate",
        "candidate_id",
        "proposal_index",
        "status",
        "lineage",
        "scorer_v1_terms",
        "refinement_receipt",
        "validity",
        "failure",
        "abstention",
        "baseline_disagreement",
        "claim_safe",
        "receipt_sha256",
    }
    candidate_id = row.get("candidate_id")
    if (
        set(row) != expected_fields
        or row.get("schema_id") != DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID
        or row.get("source_candidate_schema_id") not in _PUBLIC_CANDIDATE_SCHEMA_IDS
        or not isinstance(candidate_id, str)
        or not candidate_id
        or len(candidate_id) > 512
        or (expected_candidate_id is not None and candidate_id != expected_candidate_id)
        or row.get("proposal_index") != expected_index
        or row.get("status") not in {"success", "failure"}
        or row.get("claim_safe") is not False
    ):
        raise DockingPipelineError(
            "pipeline candidate evidence is not an exact public row"
        )
    source_candidate = _validated_public_source_candidate(row.get("source_candidate"))
    if (
        source_candidate.get("schema_id") != row["source_candidate_schema_id"]
        or source_candidate.get("proposal_index") != expected_index
        or source_candidate.get("status") != row["status"]
        or _sha256(source_candidate)
        != _require_sha256(
            row.get("source_candidate_sha256"),
            name="source public candidate digest",
        )
    ):
        raise DockingPipelineError("pipeline source candidate payload is cross-wired")
    expected_lineage = {
        "proposal_mode": source_candidate.get("proposal_mode", ""),
        "ensemble_source_proposal_index": source_candidate.get(
            "ensemble_source_proposal_index"
        ),
        "torsion_rescue_parent_proposal_index": source_candidate.get(
            "torsion_rescue_parent_proposal_index"
        ),
        "proposal_fingerprint_sha256": source_candidate.get(
            "proposal_fingerprint_sha256", ""
        ),
        "coordinate_fingerprint_sha256": source_candidate.get(
            "coordinate_fingerprint_sha256", ""
        ),
    }
    if row.get("lineage") != expected_lineage:
        raise DockingPipelineError("pipeline candidate lineage is cross-wired")
    _validated_baseline_disagreement(row.get("baseline_disagreement"))
    success = row["status"] == "success"
    if success:
        terms = _validated_full_scorer_v1_terms(
            row.get("scorer_v1_terms"),
            source_candidate=source_candidate,
        )
        refinement = _validated_full_refinement_receipt(
            row.get("refinement_receipt"),
            source_candidate=source_candidate,
        )
        expected_validity = {
            "geometric_valid": source_candidate.get("geometric_valid"),
            "chemical_valid": source_candidate.get("chemical_valid"),
            "selection_eligible": source_candidate.get("selection_eligible"),
            "posebusters_failed_check_ids": source_candidate.get(
                "posebusters_failed_check_ids", []
            ),
            "pose_artifact_sha256": source_candidate.get("pose_artifact_sha256", ""),
        }
        if (
            row.get("scorer_v1_terms") != terms
            or row.get("refinement_receipt") != refinement
            or row.get("validity") != expected_validity
            or row.get("failure") != {}
            or row.get("abstention")
            is not (not bool(source_candidate.get("selection_eligible")))
        ):
            raise DockingPipelineError(
                "successful public candidate evidence is cross-wired"
            )
    elif (
        row.get("scorer_v1_terms") is not None
        or row.get("refinement_receipt") is not None
        or row.get("validity") != {}
        or row.get("failure")
        != {"error_code": str(source_candidate.get("error_code") or "")}
        or row.get("abstention") is not True
    ):
        raise DockingPipelineError(
            "failed public candidate fabricates scientific receipts"
        )
    projection = dict(row)
    receipt = _require_sha256(
        projection.pop("receipt_sha256", ""),
        name="pipeline candidate evidence receipt",
    )
    if _sha256(projection) != receipt:
        raise DockingPipelineError("pipeline candidate evidence receipt is invalid")
    return row


def _validated_public_candidate_evidence(
    candidates: object,
    *,
    expected_candidate_ids: tuple[str, ...] | None = None,
) -> tuple[dict[str, object], ...]:
    if not isinstance(candidates, list) or not candidates:
        raise DockingPipelineError("pipeline public candidate evidence is missing")
    if expected_candidate_ids is not None and len(candidates) != len(
        expected_candidate_ids
    ):
        raise DockingPipelineError(
            "pipeline candidate evidence denominator is cross-wired"
        )
    return tuple(
        _validated_public_candidate_evidence_row(
            value,
            expected_index=expected_index,
            expected_candidate_id=(
                None
                if expected_candidate_ids is None
                else expected_candidate_ids[expected_index]
            ),
        )
        for expected_index, value in enumerate(candidates)
    )


def validate_docking_pipeline_candidate_evidence_document(
    document: Mapping[str, object],
) -> dict[str, object]:
    """Validate one detached neutral candidate wrapper and all self-hash links."""

    if not isinstance(document, Mapping):
        raise DockingPipelineError("pipeline candidate evidence must be a mapping")
    proposal_index = document.get("proposal_index")
    if type(proposal_index) is not int or proposal_index < 0:
        raise DockingPipelineError("pipeline candidate proposal index is invalid")
    return _validated_public_candidate_evidence_row(
        document,
        expected_index=proposal_index,
        expected_candidate_id=(
            document.get("candidate_id")
            if isinstance(document.get("candidate_id"), str)
            else ""
        ),
    )


def build_docking_pipeline_candidate_evidence(
    *,
    candidate_id: str,
    source_candidate: Mapping[str, object],
    scorer_v1_terms: Mapping[str, object] | None,
    refinement_receipt: Mapping[str, object] | None,
    baseline_disagreement: Mapping[str, object],
) -> dict[str, object]:
    """Wrap one immutable public diagnostic without changing its frozen schema."""

    source = _validated_public_source_candidate(source_candidate)
    schema_id = source.get("schema_id")
    status = source.get("status")
    proposal_index = source.get("proposal_index")
    normalized_candidate_id = str(candidate_id or "").strip()
    if (
        schema_id not in _PUBLIC_CANDIDATE_SCHEMA_IDS
        or status not in {"success", "failure"}
        or type(proposal_index) is not int
        or not normalized_candidate_id
        or len(normalized_candidate_id) > 512
        or normalized_candidate_id != candidate_id
        or not isinstance(baseline_disagreement, Mapping)
    ):
        raise DockingPipelineError("source public candidate evidence is invalid")
    disagreement = _validated_baseline_disagreement(baseline_disagreement)
    terms = (
        None
        if scorer_v1_terms is None
        else json.loads(_canonical_bytes(dict(scorer_v1_terms)).decode("ascii"))
    )
    refinement = (
        None
        if refinement_receipt is None
        else json.loads(_canonical_bytes(dict(refinement_receipt)).decode("ascii"))
    )
    success = status == "success"
    projection: dict[str, object] = {
        "schema_id": DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID,
        "source_candidate_schema_id": schema_id,
        "source_candidate_sha256": _sha256(source),
        "source_candidate": source,
        "candidate_id": normalized_candidate_id,
        "proposal_index": proposal_index,
        "status": status,
        "lineage": {
            "proposal_mode": source.get("proposal_mode", ""),
            "ensemble_source_proposal_index": source.get(
                "ensemble_source_proposal_index"
            ),
            "torsion_rescue_parent_proposal_index": source.get(
                "torsion_rescue_parent_proposal_index"
            ),
            "proposal_fingerprint_sha256": source.get(
                "proposal_fingerprint_sha256", ""
            ),
            "coordinate_fingerprint_sha256": source.get(
                "coordinate_fingerprint_sha256", ""
            ),
        },
        "scorer_v1_terms": terms,
        "refinement_receipt": refinement,
        "validity": (
            {
                "geometric_valid": source.get("geometric_valid"),
                "chemical_valid": source.get("chemical_valid"),
                "selection_eligible": source.get("selection_eligible"),
                "posebusters_failed_check_ids": source.get(
                    "posebusters_failed_check_ids", []
                ),
                "pose_artifact_sha256": source.get("pose_artifact_sha256", ""),
            }
            if success
            else {}
        ),
        "failure": (
            {} if success else {"error_code": str(source.get("error_code") or "")}
        ),
        "abstention": (not success or not bool(source.get("selection_eligible"))),
        "baseline_disagreement": disagreement,
        "claim_safe": False,
    }
    projection["receipt_sha256"] = _sha256(projection)
    assert isinstance(proposal_index, int)
    return _validated_public_candidate_evidence_row(
        projection,
        expected_index=proposal_index,
        expected_candidate_id=normalized_candidate_id,
    )


def build_docking_pipeline_recorded_evidence(
    *,
    source_binding: Mapping[str, object],
    candidates: list[dict[str, object]],
    candidate_ids: tuple[str, ...],
    candidate_binding_sha256: str,
) -> dict[str, object]:
    """Build the canonical candidate payload consumed by product shadow."""

    source = _validate_source_binding(source_binding)
    normalized_candidate_ids = tuple(
        str(candidate_id or "").strip() for candidate_id in candidate_ids
    )
    if (
        normalized_candidate_ids != candidate_ids
        or any(
            not candidate_id or len(candidate_id) > 512
            for candidate_id in candidate_ids
        )
        or len(candidate_ids) != len(set(candidate_ids))
    ):
        raise DockingPipelineError("pipeline candidate IDs are invalid")
    rows = _validated_public_candidate_evidence(
        candidates,
        expected_candidate_ids=normalized_candidate_ids,
    )
    expected_candidate_binding = _sha256(
        {
            "candidate_count": len(normalized_candidate_ids),
            "candidate_ids": list(normalized_candidate_ids),
        }
    )
    if candidate_binding_sha256 != expected_candidate_binding:
        raise DockingPipelineError("pipeline candidate binding is cross-wired")
    source_receipt_sha256 = source["source_receipt_sha256"]
    if any(
        row["status"] == "success"
        and row["scorer_v1_terms"]["authority_input_receipt_sha256"]
        != source_receipt_sha256
        for row in rows
    ):
        raise DockingPipelineError(
            "pipeline scoring authority is cross-wired to the exact source receipt"
        )
    projection: dict[str, object] = {
        "schema_id": DOCKING_PIPELINE_RECORDED_EVIDENCE_SCHEMA_ID,
        "source_binding": source,
        "candidate_count": len(rows),
        "candidate_ids": list(normalized_candidate_ids),
        "candidate_binding_sha256": _require_sha256(
            candidate_binding_sha256,
            name="pipeline candidate binding",
        ),
        "candidate_payload_sha256": _sha256(list(rows)),
        "candidates": list(rows),
        "failure_complete": True,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    projection["receipt_sha256"] = _sha256(projection)
    return projection


def _validate_recorded_execution_evidence(
    document: object,
    *,
    candidate_count: int,
    candidate_ids: tuple[str, ...],
    candidate_binding_sha256: str,
) -> dict[str, object]:
    if not isinstance(document, Mapping):
        raise DockingPipelineError("pipeline recorded execution evidence is invalid")
    evidence = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    if set(evidence) != {
        "schema_id",
        "source_binding",
        "candidate_count",
        "candidate_ids",
        "candidate_binding_sha256",
        "candidate_payload_sha256",
        "candidates",
        "failure_complete",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
        "receipt_sha256",
    }:
        raise DockingPipelineError("pipeline recorded evidence fields are invalid")
    expected = build_docking_pipeline_recorded_evidence(
        source_binding=evidence.get("source_binding", {}),
        candidates=evidence.get("candidates", []),
        candidate_ids=tuple(evidence.get("candidate_ids", ())),
        candidate_binding_sha256=evidence.get("candidate_binding_sha256", ""),
    )
    if (
        evidence != expected
        or evidence.get("candidate_count") != candidate_count
        or evidence.get("candidate_ids") != list(candidate_ids)
        or evidence.get("candidate_binding_sha256") != candidate_binding_sha256
    ):
        raise DockingPipelineError(
            "pipeline recorded evidence authority is cross-wired"
        )
    return evidence


@runtime_checkable
class PipelineComponent(Protocol):
    component_id: str

    def pipeline_configuration(self) -> Mapping[str, object]: ...


class InputPreparer(Protocol):
    component_id: str

    def prepare(self, request: object) -> object: ...


class ConformerProvider(Protocol):
    component_id: str

    def provide(self, prepared_input: object) -> object: ...


class ProposalGenerator(Protocol):
    component_id: str

    def generate(
        self,
        prepared_input: object,
        conformer_evidence: object,
    ) -> object: ...


class GeometricAdmission(Protocol):
    component_id: str

    def admit(
        self,
        prepared_input: object,
        proposal_evidence: object,
    ) -> object: ...


class PipelineScorer(Protocol):
    component_id: str

    def bind(
        self,
        prepared_input: object,
        admission_evidence: object,
    ) -> object: ...

    def score(
        self,
        prepared_input: object,
        refined_candidates: object,
        scorer_binding: object,
    ) -> object: ...


class PipelineRefiner(Protocol):
    component_id: str

    def refine(
        self,
        prepared_input: object,
        admission_evidence: object,
        scorer_binding: object,
    ) -> object: ...


class ValidityEvaluator(Protocol):
    component_id: str

    def evaluate(
        self,
        prepared_input: object,
        scored_result: object,
    ) -> object: ...


class PipelineRanker(Protocol):
    component_id: str

    def rank(
        self,
        prepared_input: object,
        scored_result: object,
        validity_evidence: object,
    ) -> object: ...


class EvidenceRecorder(Protocol):
    component_id: str

    def record(self, execution: "DockingPipelineExecution") -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class DockingPipelineExecution:
    request: object
    prepared_input: object
    conformer_evidence: object
    proposal_evidence: object
    admission_evidence: object
    scorer_binding: object
    refiner_binding: object
    scoring_result: object
    scored_result: object
    validity_evidence: object
    ranking_evidence: object
    pipeline_profile_id: str
    pipeline_profile_sha256: str
    pipeline_profile_document: Mapping[str, object]
    stage_outputs: tuple[VerifiedDockingPipelineStageOutput, ...]
    schema_id: str = DOCKING_PIPELINE_EXECUTION_SCHEMA_ID


class VerifiedDockingPipelineExecution:
    """Non-forgeable authority for one complete, recorded pipeline execution."""

    __slots__ = (
        "_candidate_binding_sha256",
        "_candidate_count",
        "_candidate_evidence",
        "_execution",
        "_profile_document",
        "_receipt_sha256",
        "_recorded_evidence",
        "_recorded_evidence_sha256",
        "_recorded_execution_evidence",
        "_result_binding",
        "_source_binding",
        "_stage_outputs",
    )

    def __init__(
        self,
        *,
        authority: object,
        execution: DockingPipelineExecution,
        recorder_stage: VerifiedDockingPipelineStageOutput,
    ) -> None:
        if authority is not _VERIFIED_EXECUTION_FACTORY_AUTHORITY:
            raise DockingPipelineError(
                "verified executions are created only by DockingPipeline"
            )
        if not isinstance(execution, DockingPipelineExecution):
            raise DockingPipelineError("verified execution payload is invalid")
        stages = (*execution.stage_outputs, recorder_stage)
        if tuple(stage.stage_name for stage in stages) != _EXECUTION_ORDER:
            raise DockingPipelineError("verified execution stage order is incomplete")
        for stage in stages:
            stage.assert_integrity()
        recorded = recorder_stage.value
        if not isinstance(recorded, Mapping):
            raise DockingPipelineError(
                "pipeline evidence recorder must return a mapping payload"
            )
        candidate_stages = tuple(
            stage for stage in stages if stage.candidate_count is not None
        )
        if not candidate_stages:
            raise DockingPipelineError(
                "verified pipeline execution lacks a candidate denominator"
            )
        candidate_count = candidate_stages[0].candidate_count
        candidate_ids = candidate_stages[0].candidate_ids
        candidate_binding = candidate_stages[0].candidate_binding_sha256
        if any(
            stage.candidate_count != candidate_count
            or stage.candidate_binding_sha256 != candidate_binding
            for stage in candidate_stages
        ):
            raise DockingPipelineError(
                "verified pipeline candidate authority changed between stages"
            )
        self._execution = execution
        self._stage_outputs = stages
        self._recorded_evidence = recorded
        self._recorded_evidence_sha256 = _sha256(
            {
                "recorder_stage_receipt_sha256": recorder_stage.receipt_sha256,
                "runtime_integrity_sha256": _sha256(dict(recorder_stage.integrity)),
            }
        )
        self._candidate_count = candidate_count
        self._candidate_binding_sha256 = candidate_binding
        profile_document = validate_docking_pipeline_profile_document(
            execution.pipeline_profile_document
        )
        if (
            profile_document.get("profile_id") != execution.pipeline_profile_id
            or profile_document.get("profile_sha256")
            != execution.pipeline_profile_sha256
        ):
            raise DockingPipelineError(
                "verified execution pipeline profile is cross-wired"
            )
        self._profile_document = MappingProxyType(profile_document)
        recorded_execution = recorder_stage.evidence.get("verified_execution_evidence")
        if recorded_execution is None:
            self._recorded_execution_evidence = None
            self._candidate_evidence = ()
            self._source_binding = None
            self._result_binding = None
        else:
            verified_recorded = _validate_recorded_execution_evidence(
                recorded_execution,
                candidate_count=candidate_count,
                candidate_ids=candidate_ids,
                candidate_binding_sha256=candidate_binding,
            )
            source_binding = _validate_source_binding(
                verified_recorded["source_binding"]
            )
            result_projection: dict[str, object] = {
                "schema_id": DOCKING_PIPELINE_RESULT_BINDING_SCHEMA_ID,
                "recorder_stage_receipt_sha256": recorder_stage.receipt_sha256,
                "recorded_evidence_receipt_sha256": verified_recorded["receipt_sha256"],
                "candidate_payload_sha256": verified_recorded[
                    "candidate_payload_sha256"
                ],
                "candidate_binding_sha256": candidate_binding,
                "candidate_count": candidate_count,
                "completed": True,
                "failure_complete": True,
            }
            result_projection["receipt_sha256"] = _sha256(result_projection)
            self._recorded_execution_evidence = MappingProxyType(verified_recorded)
            self._candidate_evidence = tuple(
                MappingProxyType(row) for row in verified_recorded["candidates"]
            )
            self._source_binding = MappingProxyType(source_binding)
            self._result_binding = MappingProxyType(result_projection)
        self._receipt_sha256 = _sha256(self._projection())

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": VERIFIED_DOCKING_PIPELINE_EXECUTION_SCHEMA_ID,
            "pipeline_execution_schema_id": self._execution.schema_id,
            "pipeline_profile_id": self._execution.pipeline_profile_id,
            "pipeline_profile_sha256": self._execution.pipeline_profile_sha256,
            "pipeline_profile_document_sha256": _sha256(dict(self._profile_document)),
            "execution_order": list(_EXECUTION_ORDER),
            "stage_receipt_sha256s": [
                stage.receipt_sha256 for stage in self._stage_outputs
            ],
            "candidate_count": self._candidate_count,
            "candidate_binding_sha256": self._candidate_binding_sha256,
            "recorded_evidence_sha256": self._recorded_evidence_sha256,
            "source_binding_receipt_sha256": (
                ""
                if self._source_binding is None
                else self._source_binding["receipt_sha256"]
            ),
            "result_binding_receipt_sha256": (
                ""
                if self._result_binding is None
                else self._result_binding["receipt_sha256"]
            ),
            "candidate_payload_sha256": (
                ""
                if self._recorded_execution_evidence is None
                else self._recorded_execution_evidence["candidate_payload_sha256"]
            ),
            "scientific_candidate_evidence_available": (
                self._recorded_execution_evidence is not None
            ),
            "all_stage_outputs_factory_verified": True,
            "candidate_denominator_preserved": True,
            "runtime_values_serialized": False,
            "scientifically_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }

    def assert_integrity(self) -> None:
        if tuple(self._execution.stage_outputs) != self._stage_outputs[:-1]:
            raise DockingPipelineError("verified pipeline execution stages changed")
        for stage in self._stage_outputs:
            stage.assert_integrity()
        if self._stage_outputs[-1].value is not self._recorded_evidence:
            raise DockingPipelineError("verified recorded evidence changed")
        if validate_docking_pipeline_profile_document(self._profile_document) != dict(
            self._profile_document
        ):
            raise DockingPipelineError("verified pipeline profile changed")
        if self._recorded_execution_evidence is not None:
            observed = _validate_recorded_execution_evidence(
                self._recorded_execution_evidence,
                candidate_count=self._candidate_count,
                candidate_ids=self._stage_outputs[2].candidate_ids,
                candidate_binding_sha256=self._candidate_binding_sha256,
            )
            if (
                observed["receipt_sha256"]
                != self._result_binding["recorded_evidence_receipt_sha256"]
            ):
                raise DockingPipelineError("verified result binding changed")
            result_projection = dict(self._result_binding)
            result_receipt = result_projection.pop("receipt_sha256")
            if _sha256(result_projection) != result_receipt:
                raise DockingPipelineError("verified result binding is invalid")
        if _sha256(self._projection()) != self._receipt_sha256:
            raise DockingPipelineError("verified pipeline execution changed")

    @property
    def pipeline_execution(self) -> DockingPipelineExecution:
        self.assert_integrity()
        return self._execution

    @property
    def recorded_evidence(self) -> Mapping[str, object]:
        self.assert_integrity()
        return self._recorded_evidence

    @property
    def profile_document(self) -> Mapping[str, object]:
        self.assert_integrity()
        return self._profile_document

    @property
    def candidate_evidence(self) -> tuple[Mapping[str, object], ...]:
        self.assert_integrity()
        if self._recorded_execution_evidence is None:
            raise DockingPipelineError(
                "execution has no verified public candidate evidence"
            )
        return self._candidate_evidence

    @property
    def source_binding(self) -> Mapping[str, object]:
        self.assert_integrity()
        if self._source_binding is None:
            raise DockingPipelineError("execution has no verified source binding")
        return self._source_binding

    @property
    def result_binding(self) -> Mapping[str, object]:
        self.assert_integrity()
        if self._result_binding is None:
            raise DockingPipelineError("execution has no verified result binding")
        return self._result_binding

    @property
    def execution_receipt(self) -> Mapping[str, object]:
        self.assert_integrity()
        return MappingProxyType(self.to_dict())

    @property
    def stage_outputs(self) -> tuple[VerifiedDockingPipelineStageOutput, ...]:
        self.assert_integrity()
        return self._stage_outputs

    @property
    def candidate_count(self) -> int:
        self.assert_integrity()
        assert self._candidate_count is not None
        return self._candidate_count

    @property
    def candidate_binding_sha256(self) -> str:
        self.assert_integrity()
        return self._candidate_binding_sha256

    @property
    def receipt_sha256(self) -> str:
        self.assert_integrity()
        return self._receipt_sha256

    def to_dict(self) -> dict[str, object]:
        self.assert_integrity()
        return {
            **self._projection(),
            "profile_document": dict(self._profile_document),
            "source_binding": (
                None if self._source_binding is None else dict(self._source_binding)
            ),
            "result_binding": (
                None if self._result_binding is None else dict(self._result_binding)
            ),
            "stage_receipts": [stage.to_dict() for stage in self._stage_outputs],
            "receipt_sha256": self._receipt_sha256,
        }


def _validate_serialized_stage_receipts(
    value: object,
    *,
    profile_document: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list) or len(value) != len(_EXECUTION_ORDER):
        raise DockingPipelineError(
            "verified pipeline execution must contain all ten stage receipts"
        )
    component_profiles = profile_document.get("components")
    if not isinstance(component_profiles, dict):  # validated by the caller
        raise DockingPipelineError("verified pipeline components are invalid")
    upstream_indices = (
        (),
        (0,),
        (0, 1),
        (0, 2),
        (0, 3),
        (0, 3, 4),
        (0, 5, 4),
        (0, 6),
        (0, 6, 7),
        tuple(range(9)),
    )
    stage_fields = {
        "schema_id",
        "stage_name",
        "owner_role",
        "owner_component_id",
        "owner_component_receipt_sha256",
        "upstream_receipt_sha256s",
        "evidence",
        "evidence_sha256",
        "runtime_integrity",
        "runtime_integrity_sha256",
        "candidate_count",
        "candidate_ids",
        "candidate_binding_sha256",
        "runtime_value_serialized",
        "factory_verified",
        "claim_safe",
        "receipt_sha256",
    }
    stages: list[dict[str, object]] = []
    candidate_ids: list[str] | None = None
    candidate_count: int | None = None
    candidate_binding = ""
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise DockingPipelineError("verified pipeline stage receipt is invalid")
        stage = json.loads(_canonical_bytes(dict(raw)).decode("ascii"))
        stage_name = _EXECUTION_ORDER[index]
        role = _EXECUTION_STAGE_ROLES[stage_name]
        component = component_profiles[role]
        if (
            set(stage) != stage_fields
            or stage.get("schema_id") != DOCKING_PIPELINE_STAGE_OUTPUT_SCHEMA_ID
            or stage.get("stage_name") != stage_name
            or stage.get("owner_role") != role
            or stage.get("owner_component_id") != component["component_id"]
            or stage.get("owner_component_receipt_sha256")
            != component["receipt_sha256"]
            or stage.get("runtime_value_serialized") is not False
            or stage.get("factory_verified") is not True
            or stage.get("claim_safe") is not False
            or not isinstance(stage.get("evidence"), dict)
            or not isinstance(stage.get("runtime_integrity"), dict)
            or not isinstance(stage.get("candidate_ids"), list)
        ):
            raise DockingPipelineError(
                "verified pipeline stage fields or ownership are invalid"
            )
        if _sha256(stage["evidence"]) != stage.get("evidence_sha256") or _sha256(
            stage["runtime_integrity"]
        ) != stage.get("runtime_integrity_sha256"):
            raise DockingPipelineError("verified pipeline stage evidence changed")
        ids = stage["candidate_ids"]
        count = stage.get("candidate_count")
        if (
            any(
                not isinstance(item, str) or not item or len(item) > 512 for item in ids
            )
            or len(ids) != len(set(ids))
            or (
                count is not None
                and (type(count) is not int or count < 0 or count != len(ids))
            )
            or (count is None and ids)
        ):
            raise DockingPipelineError(
                "verified pipeline candidate identities are invalid"
            )
        observed_binding = _sha256({"candidate_count": count, "candidate_ids": ids})
        if observed_binding != stage.get("candidate_binding_sha256"):
            raise DockingPipelineError("verified pipeline candidate binding is invalid")
        if index < 2:
            if count is not None or ids:
                raise DockingPipelineError(
                    "verified pipeline declares candidates before proposal generation"
                )
        elif index == 2:
            if type(count) is not int or count < 1:
                raise DockingPipelineError(
                    "verified pipeline proposal denominator is invalid"
                )
            candidate_ids = ids
            candidate_count = count
            candidate_binding = observed_binding
        elif (
            count != candidate_count
            or ids != candidate_ids
            or observed_binding != candidate_binding
        ):
            raise DockingPipelineError(
                "verified pipeline candidate authority changed between stages"
            )
        expected_upstream = [
            stages[upstream_index]["receipt_sha256"]
            for upstream_index in upstream_indices[index]
        ]
        if stage.get("upstream_receipt_sha256s") != expected_upstream:
            raise DockingPipelineError(
                "verified pipeline upstream receipt chain is cross-wired"
            )
        projection = dict(stage)
        receipt = _require_sha256(
            projection.pop("receipt_sha256", ""),
            name="verified pipeline stage receipt",
        )
        if _sha256(projection) != receipt:
            raise DockingPipelineError("verified pipeline stage receipt changed")
        stages.append(stage)
    return tuple(stages)


def _validated_result_binding(
    value: object,
    *,
    recorder_stage_receipt_sha256: str,
    recorded_evidence: Mapping[str, object],
    candidate_count: int,
    candidate_binding_sha256: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise DockingPipelineError("verified pipeline result binding is missing")
    result = json.loads(_canonical_bytes(dict(value)).decode("ascii"))
    expected: dict[str, object] = {
        "schema_id": DOCKING_PIPELINE_RESULT_BINDING_SCHEMA_ID,
        "recorder_stage_receipt_sha256": recorder_stage_receipt_sha256,
        "recorded_evidence_receipt_sha256": recorded_evidence["receipt_sha256"],
        "candidate_payload_sha256": recorded_evidence["candidate_payload_sha256"],
        "candidate_binding_sha256": candidate_binding_sha256,
        "candidate_count": candidate_count,
        "completed": True,
        "failure_complete": True,
    }
    expected["receipt_sha256"] = _sha256(expected)
    if result != expected:
        raise DockingPipelineError("verified pipeline result binding is cross-wired")
    return result


def validate_verified_docking_pipeline_execution_document(
    document: Mapping[str, object],
    profile_document: Mapping[str, object],
    recorded_evidence_document: Mapping[str, object],
) -> dict[str, object]:
    """Purely validate one serialized, public-evidence pipeline execution.

    Runtime values are deliberately absent from this contract.  The supplied
    frozen profile and recorded candidate document are therefore required and
    are cross-bound to all ten stage receipts and the execution self-hash.
    """

    if not isinstance(document, Mapping):
        raise DockingPipelineError("verified pipeline execution must be a mapping")
    execution = json.loads(_canonical_bytes(dict(document)).decode("ascii"))
    profile = validate_docking_pipeline_profile_document(profile_document)
    projection_fields = {
        "schema_id",
        "pipeline_execution_schema_id",
        "pipeline_profile_id",
        "pipeline_profile_sha256",
        "pipeline_profile_document_sha256",
        "execution_order",
        "stage_receipt_sha256s",
        "candidate_count",
        "candidate_binding_sha256",
        "recorded_evidence_sha256",
        "source_binding_receipt_sha256",
        "result_binding_receipt_sha256",
        "candidate_payload_sha256",
        "scientific_candidate_evidence_available",
        "all_stage_outputs_factory_verified",
        "candidate_denominator_preserved",
        "runtime_values_serialized",
        "scientifically_validated",
        "product_qualified",
        "claim_safe",
    }
    supplemental_fields = {
        "profile_document",
        "source_binding",
        "result_binding",
        "stage_receipts",
        "receipt_sha256",
    }
    if set(execution) != projection_fields | supplemental_fields:
        raise DockingPipelineError("verified pipeline execution fields are invalid")
    embedded_profile = execution.get("profile_document")
    if (
        not isinstance(embedded_profile, dict)
        or embedded_profile != profile
        or execution.get("schema_id") != VERIFIED_DOCKING_PIPELINE_EXECUTION_SCHEMA_ID
        or execution.get("pipeline_execution_schema_id")
        != DOCKING_PIPELINE_EXECUTION_SCHEMA_ID
        or execution.get("pipeline_profile_id") != profile["profile_id"]
        or execution.get("pipeline_profile_sha256") != profile["profile_sha256"]
        or execution.get("pipeline_profile_document_sha256") != _sha256(profile)
        or execution.get("execution_order") != list(_EXECUTION_ORDER)
    ):
        raise DockingPipelineError("verified pipeline execution profile is cross-wired")
    expected_flags = {
        "scientific_candidate_evidence_available": True,
        "all_stage_outputs_factory_verified": True,
        "candidate_denominator_preserved": True,
        "runtime_values_serialized": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    if any(
        execution.get(name) is not expected for name, expected in expected_flags.items()
    ):
        raise DockingPipelineError("verified pipeline execution flags are invalid")
    stages = _validate_serialized_stage_receipts(
        execution.get("stage_receipts"),
        profile_document=profile,
    )
    proposal_stage = stages[2]
    recorder_stage = stages[-1]
    candidate_count = proposal_stage["candidate_count"]
    candidate_binding = proposal_stage["candidate_binding_sha256"]
    assert isinstance(candidate_count, int)
    assert isinstance(candidate_binding, str)
    if (
        execution.get("stage_receipt_sha256s")
        != [stage["receipt_sha256"] for stage in stages]
        or execution.get("candidate_count") != candidate_count
        or execution.get("candidate_binding_sha256") != candidate_binding
    ):
        raise DockingPipelineError(
            "verified pipeline stage or candidate authority is cross-wired"
        )
    recorded = _validate_recorded_execution_evidence(
        recorded_evidence_document,
        candidate_count=candidate_count,
        candidate_ids=tuple(proposal_stage["candidate_ids"]),
        candidate_binding_sha256=candidate_binding,
    )
    recorder_evidence = recorder_stage["evidence"]
    if recorder_evidence.get("verified_execution_evidence") != recorded:
        raise DockingPipelineError(
            "verified pipeline recorded evidence is not the recorder output"
        )
    source = _validate_source_binding(execution.get("source_binding"))
    if source != recorded["source_binding"]:
        raise DockingPipelineError("verified pipeline source binding is cross-wired")
    result = _validated_result_binding(
        execution.get("result_binding"),
        recorder_stage_receipt_sha256=str(recorder_stage["receipt_sha256"]),
        recorded_evidence=recorded,
        candidate_count=candidate_count,
        candidate_binding_sha256=candidate_binding,
    )
    expected_recorded_sha256 = _sha256(
        {
            "recorder_stage_receipt_sha256": recorder_stage["receipt_sha256"],
            "runtime_integrity_sha256": recorder_stage["runtime_integrity_sha256"],
        }
    )
    if (
        execution.get("recorded_evidence_sha256") != expected_recorded_sha256
        or execution.get("source_binding_receipt_sha256") != source["receipt_sha256"]
        or execution.get("result_binding_receipt_sha256") != result["receipt_sha256"]
        or execution.get("candidate_payload_sha256")
        != recorded["candidate_payload_sha256"]
    ):
        raise DockingPipelineError(
            "verified pipeline source, result, or candidate payload changed"
        )
    projection = {
        name: execution[name] for name in execution if name in projection_fields
    }
    receipt = _require_sha256(
        execution.get("receipt_sha256"),
        name="verified pipeline execution receipt",
    )
    if _sha256(projection) != receipt:
        raise DockingPipelineError("verified pipeline execution receipt changed")
    return execution


class DockingPipeline:
    """Execute one immutable nine-collaborator docking core."""

    __slots__ = (
        "_components",
        "_component_bindings",
        "_profile_document",
        "_profile_id",
        "_profile_sha256",
    )

    def __init__(
        self,
        input_preparer: InputPreparer,
        conformer_provider: ConformerProvider,
        proposal_generator: ProposalGenerator,
        geometric_admission: GeometricAdmission,
        scorer: PipelineScorer,
        refiner: PipelineRefiner,
        validity_evaluator: ValidityEvaluator,
        ranker: PipelineRanker,
        evidence_recorder: EvidenceRecorder,
        *,
        profile_id: str = "betelgeuze.engine_v2_docking_pipeline/unqualified",
    ) -> None:
        profile = str(profile_id or "").strip()
        if not profile or len(profile) > 240:
            raise DockingPipelineError("pipeline profile_id is invalid")
        components = {
            "input_preparer": input_preparer,
            "conformer_provider": conformer_provider,
            "proposal_generator": proposal_generator,
            "geometric_admission": geometric_admission,
            "scorer": scorer,
            "refiner": refiner,
            "validity_evaluator": validity_evaluator,
            "ranker": ranker,
            "evidence_recorder": evidence_recorder,
        }
        component_bindings: dict[str, dict[str, object]] = {}
        for role, component in components.items():
            component_id = str(getattr(component, "component_id", "") or "").strip()
            if not component_id or len(component_id) > 240:
                raise DockingPipelineError(f"pipeline {role} component_id is invalid")
            component_bindings[role] = _component_profile_document(role, component)
        self._components = tuple(components.items())
        self._component_bindings = component_bindings
        self._profile_id = profile
        self._profile_document = {
            "schema_id": DOCKING_PIPELINE_PROFILE_SCHEMA_ID,
            "profile_id": profile,
            "components": component_bindings,
            "execution_order": list(_EXECUTION_ORDER),
            "failure_complete_required": True,
            "candidate_denominator_preservation_required": True,
            "consumer_agnostic": True,
            "scientifically_validated": False,
            "product_qualified": False,
            "claim_safe": False,
        }
        self._profile_sha256 = _sha256(self._profile_document)

    def _component(self, role: str) -> object:
        return dict(self._components)[role]

    def _assert_component_integrity(self) -> None:
        if tuple(role for role, _ in self._components) != tuple(_ROLE_METHODS):
            raise DockingPipelineError("pipeline component order changed")
        for role, component in self._components:
            expected = self._component_bindings[role]
            if (
                getattr(component, "component_id", None) != expected["component_id"]
                or _component_profile_document(role, component) != expected
            ):
                raise DockingPipelineError(
                    f"pipeline {role} component changed after construction"
                )

    @property
    def input_preparer(self) -> InputPreparer:
        return self._component("input_preparer")  # type: ignore[return-value]

    @property
    def conformer_provider(self) -> ConformerProvider:
        return self._component("conformer_provider")  # type: ignore[return-value]

    @property
    def proposal_generator(self) -> ProposalGenerator:
        return self._component("proposal_generator")  # type: ignore[return-value]

    @property
    def geometric_admission(self) -> GeometricAdmission:
        return self._component("geometric_admission")  # type: ignore[return-value]

    @property
    def scorer(self) -> PipelineScorer:
        return self._component("scorer")  # type: ignore[return-value]

    @property
    def refiner(self) -> PipelineRefiner:
        return self._component("refiner")  # type: ignore[return-value]

    @property
    def validity_evaluator(self) -> ValidityEvaluator:
        return self._component("validity_evaluator")  # type: ignore[return-value]

    @property
    def ranker(self) -> PipelineRanker:
        return self._component("ranker")  # type: ignore[return-value]

    @property
    def evidence_recorder(self) -> EvidenceRecorder:
        return self._component("evidence_recorder")  # type: ignore[return-value]

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def profile_sha256(self) -> str:
        self._assert_component_integrity()
        if _sha256(self._profile_document) != self._profile_sha256:
            raise DockingPipelineError("pipeline profile changed after construction")
        return self._profile_sha256

    def profile_document(self) -> dict[str, object]:
        self._assert_component_integrity()
        document = json.loads(_canonical_bytes(self._profile_document).decode("ascii"))
        document["profile_sha256"] = self._profile_sha256
        return validate_docking_pipeline_profile_document(document)

    def _seal_stage(
        self,
        *,
        stage_name: str,
        payload: object,
        upstream: tuple[VerifiedDockingPipelineStageOutput, ...],
        expected_candidates: VerifiedDockingPipelineStageOutput | None = None,
    ) -> VerifiedDockingPipelineStageOutput:
        role = _EXECUTION_STAGE_ROLES.get(stage_name)
        if role is None:
            raise DockingPipelineError("pipeline attempted to seal an unknown stage")
        if not isinstance(payload, DockingPipelineStagePayload):
            raise DockingPipelineError(
                f"pipeline {stage_name} must return DockingPipelineStagePayload"
            )
        if expected_candidates is None:
            if stage_name == "proposal_generator.generate":
                if payload.candidate_count is None or payload.candidate_count < 1:
                    raise DockingPipelineError(
                        "pipeline proposal stage lacks a positive denominator"
                    )
            elif payload.candidate_count is not None:
                raise DockingPipelineError(
                    f"pipeline {stage_name} declared candidates before proposal generation"
                )
        elif (
            payload.candidate_count != expected_candidates.candidate_count
            or payload.candidate_ids != expected_candidates.candidate_ids
        ):
            raise DockingPipelineError(
                f"pipeline {stage_name} changed candidate authority"
            )
        component = self._component(role)
        binding = self._component_bindings[role]
        sealed = VerifiedDockingPipelineStageOutput(
            authority=_VERIFIED_STAGE_FACTORY_AUTHORITY,
            stage_name=stage_name,
            owner_role=role,
            owner_component_id=str(binding["component_id"]),
            owner_component_receipt_sha256=str(binding["receipt_sha256"]),
            upstream_receipt_sha256s=tuple(stage.receipt_sha256 for stage in upstream),
            payload=payload,
        )
        self._assert_component_integrity()
        if getattr(component, "component_id", None) != sealed._owner_component_id:
            raise DockingPipelineError("pipeline stage owner changed while sealing")
        return sealed

    def run_verified(self, request: object) -> VerifiedDockingPipelineExecution:
        """Run the shared core and return a factory-only execution authority."""

        self._assert_component_integrity()
        prepared = self._seal_stage(
            stage_name="input_preparer.prepare",
            payload=self.input_preparer.prepare(request),
            upstream=(),
        )
        self._assert_component_integrity()
        conformer = self._seal_stage(
            stage_name="conformer_provider.provide",
            payload=self.conformer_provider.provide(prepared),
            upstream=(prepared,),
        )
        self._assert_component_integrity()
        proposal = self._seal_stage(
            stage_name="proposal_generator.generate",
            payload=self.proposal_generator.generate(
                prepared,
                conformer,
            ),
            upstream=(prepared, conformer),
        )
        self._assert_component_integrity()
        admission = self._seal_stage(
            stage_name="geometric_admission.admit",
            payload=self.geometric_admission.admit(
                prepared,
                proposal,
            ),
            upstream=(prepared, proposal),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        scorer = self._seal_stage(
            stage_name="scorer.bind",
            payload=self.scorer.bind(prepared, admission),
            upstream=(prepared, admission),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        refiner = self._seal_stage(
            stage_name="refiner.refine",
            payload=self.refiner.refine(prepared, admission, scorer),
            upstream=(prepared, admission, scorer),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        scored = self._seal_stage(
            stage_name="scorer.score",
            payload=self.scorer.score(
                prepared,
                refiner,
                scorer,
            ),
            upstream=(prepared, refiner, scorer),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        validity = self._seal_stage(
            stage_name="validity_evaluator.evaluate",
            payload=self.validity_evaluator.evaluate(
                prepared,
                scored,
            ),
            upstream=(prepared, scored),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        ranking = self._seal_stage(
            stage_name="ranker.rank",
            payload=self.ranker.rank(
                prepared,
                scored,
                validity,
            ),
            upstream=(prepared, scored, validity),
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        execution = DockingPipelineExecution(
            request=request,
            prepared_input=prepared.value,
            conformer_evidence=dict(conformer.evidence),
            proposal_evidence=dict(proposal.evidence),
            admission_evidence=dict(admission.evidence),
            scorer_binding=scorer.value,
            refiner_binding=refiner.value,
            scoring_result=scored.value,
            scored_result=ranking.value,
            validity_evidence=dict(validity.evidence),
            ranking_evidence=dict(ranking.evidence),
            pipeline_profile_id=self.profile_id,
            pipeline_profile_sha256=self.profile_sha256,
            pipeline_profile_document=self.profile_document(),
            stage_outputs=(
                prepared,
                conformer,
                proposal,
                admission,
                scorer,
                refiner,
                scored,
                validity,
                ranking,
            ),
        )
        recorder = self._seal_stage(
            stage_name="evidence_recorder.record",
            payload=self.evidence_recorder.record(execution),
            upstream=execution.stage_outputs,
            expected_candidates=proposal,
        )
        self._assert_component_integrity()
        return VerifiedDockingPipelineExecution(
            authority=_VERIFIED_EXECUTION_FACTORY_AUTHORITY,
            execution=execution,
            recorder_stage=recorder,
        )

    def run(self, request: object) -> dict[str, object]:
        """Compatibility surface returning the recorder mapping only."""

        verified = self.run_verified(request)
        return dict(verified.recorded_evidence)


__all__ = [
    "ConformerProvider",
    "DOCKING_PIPELINE_CANDIDATE_EVIDENCE_SCHEMA_ID",
    "DOCKING_PIPELINE_COMPONENT_PROFILE_SCHEMA_ID",
    "DOCKING_PIPELINE_EXECUTION_SCHEMA_ID",
    "DOCKING_PIPELINE_PROFILE_SCHEMA_ID",
    "DOCKING_PIPELINE_RECORDED_EVIDENCE_SCHEMA_ID",
    "DOCKING_PIPELINE_RESULT_BINDING_SCHEMA_ID",
    "DOCKING_PIPELINE_SOURCE_BINDING_SCHEMA_ID",
    "DOCKING_PIPELINE_STAGE_OUTPUT_SCHEMA_ID",
    "DockingPipeline",
    "DockingPipelineError",
    "DockingPipelineExecution",
    "DockingPipelineStagePayload",
    "EvidenceRecorder",
    "GeometricAdmission",
    "InputPreparer",
    "PipelineComponent",
    "PipelineRanker",
    "PipelineRefiner",
    "PipelineScorer",
    "ProposalGenerator",
    "VERIFIED_DOCKING_PIPELINE_EXECUTION_SCHEMA_ID",
    "VerifiedDockingPipelineExecution",
    "VerifiedDockingPipelineStageOutput",
    "ValidityEvaluator",
    "build_docking_pipeline_candidate_evidence",
    "build_docking_pipeline_recorded_evidence",
    "build_docking_pipeline_source_binding",
    "docking_pipeline_stage_payload",
    "require_pipeline_stage",
    "validate_docking_pipeline_candidate_evidence_document",
    "validate_docking_pipeline_profile_document",
    "validate_verified_docking_pipeline_execution_document",
]
