"""Source-frozen shared DockingPipeline profile for public redocking.

The collaborators are generic callback adapters.  Their profile binds both the
Stage 0 Engine V2 implementation closure and an independently derived authority
for the exact benchmark-runner source and canonical callback layout.  Runtime
callbacks are checked against that authority; profile-only verification derives
the same authority directly from the frozen runner source without importing or
executing it.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from functools import lru_cache
import hashlib
import inspect
import json
from pathlib import Path
import re
from types import CodeType, MappingProxyType

from ..pipeline import (
    DockingPipeline,
    DockingPipelineExecution,
    DockingPipelineStagePayload,
    VerifiedDockingPipelineStageOutput,
    docking_pipeline_stage_payload,
    require_pipeline_stage,
)


PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID = (
    "betelgeuze.engine_v2_public_redocking_stage0_cpu_pipeline/1.0.0"
)
PUBLIC_REDOCKING_DEVELOPMENT_PIPELINE_PROFILE_ID = (
    "betelgeuze.engine_v2_public_redocking_development_cpu_pipeline/1.0.0"
)
PUBLIC_REDOCKING_PIPELINE_VARIANTS = frozenset(
    {"", "v8_clearance", "true_conformer", "source_paired_torsion_rescue"}
)
PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH = "tools/run_engine_v2_public_redocking_300.py"
PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS: Mapping[str, tuple[str, ...]] = (
    MappingProxyType(
        {
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
    )
)
PUBLIC_REDOCKING_PIPELINE_ROLES = frozenset(PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS)
_CALLBACK_AUTHORITY_SCHEMA_ID = (
    "betelgeuze.engine_v2_public_redocking_callback_authority/1.0.0"
)
_RUNNER_ADAPTER_CLASS_NAME = "_BenchmarkPipelineComponent"
_RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES = (
    "_prepare_benchmark_scientific_input",
    "_provide_benchmark_conformers",
    "_generate_benchmark_proposals",
    "_admit_benchmark_proposals",
    "_refine_benchmark_candidates",
    "_score_benchmark_candidates",
    "_validate_benchmark_candidates",
    "_rank_benchmark_candidates",
)
_MAX_RUNNER_SOURCE_BYTES = 8 * 1024 * 1024
_FROZEN_RUNNER_SOURCE_SHA256 = (
    "5316cc19f3f7cd5a8712e560ed0d7c8346e917579168661c146cbe60e8552968"
)
_FROZEN_ADAPTER_METHOD_SOURCE_SHA256S: Mapping[str, str] = MappingProxyType(
    {
        "admit": "28f9b0d0e16c30d4edb16eedf7a848f0ba5fcd9cc30cb37dc946e64b55a10bd0",
        "bind": "ee771e5e690c9e4140b500c63690f51ac6bfa722c5e1973ee1c46b3937fcaf77",
        "evaluate": "14a29f634b4126cb0389ead6df62eb775e269f693637557a0c351b704bf82329",
        "generate": "28ca02957aae80825228723dd404b5559fd992db592ebbf6ef483c960b4f7593",
        "prepare": "7d6dd64779b4ce9b4aaa92b0203e703a4e5eaa07a4e95c1623a49c9e5826be1d",
        "provide": "2262a1ae4af0c45bab5fd43777d8c2f9f3bf3d602ea12fd48fb756114ec08409",
        "rank": "30b9a8c38c0b23b0da6d268d7315b62d2bc6ce6d58d2bafbd9e608a78830dec2",
        "record": "451570d815d74b31e70d6eec67c646ee4c27dd13109466ac107caab5ebf50986",
        "refine": "0785ff60ea23c4954144f098794d7e1f1c4997288a2d5f03cab6083fa0c16bfd",
        "score": "88fd7977db6f89e404aedd13b1f9b335c34ae877337b304f2905ce8bf29f0f7d",
    }
)
_FROZEN_SCIENTIFIC_STAGE_SOURCE_SHA256S: Mapping[str, str] = MappingProxyType(
    {
        "_admit_benchmark_proposals": "0090f466d32742ae8d23240097216ce48cb14046b7ad753c65bbb8d560907b31",
        "_generate_benchmark_proposals": "339c7e7040abd34e706a747b89aba4120e6f97be7ff601c54ff3e4703b09e1d3",
        "_prepare_benchmark_scientific_input": "0ce6b89239c4ccc81e321605f71364332e645e0b794159aa384ab4e8724f2a85",
        "_provide_benchmark_conformers": "34dcfe56b93423bc07ab4de632b3130fffcf6d306abbe5227fc34842f3dfeb86",
        "_rank_benchmark_candidates": "12305f78036bc69a7ba986e4180c600fd8d452ca4af76dd0adcd3107d4cc53ae",
        "_refine_benchmark_candidates": "f8bb952ecf420dcab5c4721c29f992a316faa776daf7f6cd91c937d2c82c7a8d",
        "_score_benchmark_candidates": "01ae6c841cff131238fdb8deefcb0f7a67df5d037f03f1dca2808ccd0adbd507",
        "_validate_benchmark_candidates": "3c86c23384361b91e5a3a8f7615f7edb8c22524e5da16b0454d5d1f9f04cedbd",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PublicRedockingPipelineProfileError(ValueError):
    """The shared benchmark pipeline profile is malformed or cross-wired."""


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
        raise PublicRedockingPipelineProfileError(
            "callback authority is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _code_constant(value: object) -> object:
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
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
            "items": sorted(items, key=_canonical_bytes),
        }
    if isinstance(value, CodeType):
        return {"kind": "code", "value": _code_projection(value)}
    if value is Ellipsis:
        return {"kind": "ellipsis"}
    raise PublicRedockingPipelineProfileError(
        "benchmark callback bytecode contains an unsupported constant"
    )


def _code_projection(code: CodeType) -> dict[str, object]:
    """Return bytecode evidence independent of process and checkout location."""

    return {
        "name": code.co_name,
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


def _code_sha256(code: CodeType) -> str:
    return _sha256(_code_projection(code))


def _local_runner_source_path() -> Path | None:
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH
    if not path.exists():
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source is unavailable"
        ) from exc
    if resolved != path or not resolved.is_file():
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source path is invalid"
        )
    return resolved


def _walk_code_objects(
    code: CodeType,
    *,
    parents: tuple[str, ...] = (),
) -> tuple[tuple[tuple[str, ...], CodeType], ...]:
    rows = [(parents, code)]
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            rows.extend(
                _walk_code_objects(
                    constant,
                    parents=parents + (code.co_name,),
                )
            )
    return tuple(rows)


def _one_compiled_code(
    rows: tuple[tuple[tuple[str, ...], CodeType], ...],
    *,
    parent_name: str,
    function_name: str,
) -> CodeType:
    matches = tuple(
        code
        for parents, code in rows
        if code.co_name == function_name and parents[-1:] == (parent_name,)
    )
    if len(matches) != 1:
        raise PublicRedockingPipelineProfileError(
            "canonical runner callback layout is ambiguous"
        )
    return matches[0]


@lru_cache(maxsize=2)
def _authority_from_source(
    source_sha256: str,
    source: bytes,
) -> bytes:
    if hashlib.sha256(source).hexdigest() != source_sha256:
        raise PublicRedockingPipelineProfileError(
            "canonical runner source digest is cross-wired"
        )
    try:
        text = source.decode("utf-8")
        module = ast.parse(text, filename=PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH)
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source cannot be parsed"
        ) from exc
    adapter_classes = tuple(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == _RUNNER_ADAPTER_CLASS_NAME
    )
    stage_nodes = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES
    }
    if len(adapter_classes) != 1 or set(stage_nodes) != set(
        _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES
    ):
        raise PublicRedockingPipelineProfileError(
            "canonical runner callback source layout is ambiguous"
        )
    method_names = {
        method
        for methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.values()
        for method in methods
    }
    method_nodes = {
        node.name: node
        for node in adapter_classes[0].body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    }
    if set(method_nodes) != method_names:
        raise PublicRedockingPipelineProfileError(
            "canonical runner callback source layout is incomplete"
        )
    source_lines = text.splitlines(keepends=True)

    def source_node_sha256(node: ast.AST) -> str:
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", 0)
        if (
            type(start) is not int
            or type(end) is not int
            or start < 1
            or end < start
            or end > len(source_lines)
        ):
            raise PublicRedockingPipelineProfileError(
                "canonical runner callback source location is invalid"
            )
        payload = "".join(source_lines[start - 1 : end]).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    method_source_sha256s = {
        method: source_node_sha256(method_nodes[method])
        for method in sorted(method_names)
    }
    callback_methods = {
        role: list(methods)
        for role, methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.items()
    }
    callback_keys = sorted(
        f"{role}.{method}"
        for role, methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.items()
        for method in methods
    )
    authority = {
        "schema_id": _CALLBACK_AUTHORITY_SCHEMA_ID,
        "runner_relative_path": PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH,
        "runner_source_sha256": source_sha256,
        "adapter_class_name": _RUNNER_ADAPTER_CLASS_NAME,
        "callback_methods": callback_methods,
        "callback_keys": callback_keys,
        "adapter_method_source_sha256s": method_source_sha256s,
        "scientific_stages": {
            name: {
                "qualname": name,
                "source_sha256": source_node_sha256(stage_nodes[name]),
            }
            for name in _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES
        },
        "runtime_callbacks_required_for_execution": True,
        "profile_only_reconstruction_supported": True,
    }
    return _canonical_bytes(authority)


@lru_cache(maxsize=2)
def _runtime_code_authority(
    source_sha256: str,
    source: bytes,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]:
    """Recompile exact source to detect in-memory callback code replacement."""

    if hashlib.sha256(source).hexdigest() != source_sha256:
        raise PublicRedockingPipelineProfileError(
            "canonical runner runtime-code digest is cross-wired"
        )
    try:
        text = source.decode("utf-8")
        module_code = compile(
            text,
            PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH,
            "exec",
            dont_inherit=True,
            optimize=0,
        )
    except (SyntaxError, UnicodeDecodeError) as exc:
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source cannot be compiled"
        ) from exc
    rows = _walk_code_objects(module_code)
    method_code_sha256s = tuple(
        sorted(
            (
                method,
                _code_sha256(
                    _one_compiled_code(
                        rows,
                        parent_name=_RUNNER_ADAPTER_CLASS_NAME,
                        function_name=method,
                    )
                ),
            )
            for method in {
                method
                for methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.values()
                for method in methods
            }
        )
    )
    scientific_stage_code_sha256s = tuple(
        (
            name,
            _code_sha256(
                _one_compiled_code(
                    rows,
                    parent_name="<module>",
                    function_name=name,
                )
            ),
        )
        for name in _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES
    )
    return method_code_sha256s, scientific_stage_code_sha256s


def _frozen_callback_authority() -> bytes:
    callback_methods = {
        role: list(methods)
        for role, methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.items()
    }
    callback_keys = sorted(
        f"{role}.{method}"
        for role, methods in PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS.items()
        for method in methods
    )
    return _canonical_bytes(
        {
            "schema_id": _CALLBACK_AUTHORITY_SCHEMA_ID,
            "runner_relative_path": PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH,
            "runner_source_sha256": _FROZEN_RUNNER_SOURCE_SHA256,
            "adapter_class_name": _RUNNER_ADAPTER_CLASS_NAME,
            "callback_methods": callback_methods,
            "callback_keys": callback_keys,
            "adapter_method_source_sha256s": dict(
                _FROZEN_ADAPTER_METHOD_SOURCE_SHA256S
            ),
            "scientific_stages": {
                name: {
                    "qualname": name,
                    "source_sha256": _FROZEN_SCIENTIFIC_STAGE_SOURCE_SHA256S[name],
                }
                for name in _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES
            },
            "runtime_callbacks_required_for_execution": True,
            "profile_only_reconstruction_supported": True,
        }
    )


def _verify_runner_source(
    runner_path: Path,
    *,
    authority_bytes: bytes,
) -> tuple[dict[str, str], dict[str, str]]:
    try:
        source = runner_path.read_bytes()
    except OSError as exc:
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source cannot be read"
        ) from exc
    if not source or len(source) > _MAX_RUNNER_SOURCE_BYTES:
        raise PublicRedockingPipelineProfileError(
            "canonical public-redocking runner source is outside bounds"
        )
    source_sha256 = hashlib.sha256(source).hexdigest()
    if _authority_from_source(source_sha256, source) != authority_bytes:
        raise PublicRedockingPipelineProfileError(
            "public-redocking runner source does not match frozen callback authority"
        )
    method_rows, scientific_stage_rows = _runtime_code_authority(
        source_sha256,
        source,
    )
    return dict(method_rows), dict(scientific_stage_rows)


def _canonical_callback_authority() -> tuple[Path | None, bytes]:
    authority_bytes = _frozen_callback_authority()
    runner_path = _local_runner_source_path()
    if runner_path is not None:
        _verify_runner_source(runner_path, authority_bytes=authority_bytes)
    return runner_path, authority_bytes


def _runtime_runner_source_path(
    callbacks: Mapping[str, Callable[..., object]],
) -> Path:
    paths = {
        _callable_source_path(callback)
        for callback in callbacks.values()
        if callable(callback)
    }
    if len(paths) != 1:
        raise PublicRedockingPipelineProfileError(
            "pipeline callbacks do not share one exact runner source"
        )
    runner_path = next(iter(paths))
    expected_suffix = Path(PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH).parts
    if runner_path.parts[-len(expected_suffix) :] != expected_suffix:
        raise PublicRedockingPipelineProfileError(
            "pipeline callback source is not the canonical public-redocking runner"
        )
    return runner_path


def _callable_source_path(callback: object) -> Path:
    function = getattr(callback, "__func__", callback)
    source_name = inspect.getsourcefile(function)
    if not source_name:
        raise PublicRedockingPipelineProfileError(
            "public-redocking callback source is unavailable"
        )
    try:
        return Path(source_name).resolve(strict=True)
    except OSError as exc:
        raise PublicRedockingPipelineProfileError(
            "public-redocking callback source is unavailable"
        ) from exc


def _validate_one_callback(
    callback_key: str,
    callback: object,
    *,
    runner_path: Path,
    method_code_sha256s: Mapping[str, str],
) -> object:
    role, method_name = callback_key.split(".", 1)
    if not inspect.ismethod(callback):
        raise PublicRedockingPipelineProfileError(
            f"pipeline callback {callback_key} must be an exact bound method"
        )
    owner = callback.__self__
    function = callback.__func__
    owner_type = type(owner)
    expected_component_id = f"betelgeuze.engine_v2.public_redocking_{role}/1.0.0"
    if (
        owner_type.__name__ != _RUNNER_ADAPTER_CLASS_NAME
        or owner_type.__qualname__ != _RUNNER_ADAPTER_CLASS_NAME
        or getattr(owner_type, method_name, None) is not function
        or function.__name__ != method_name
        or function.__qualname__ != f"{_RUNNER_ADAPTER_CLASS_NAME}.{method_name}"
        or getattr(owner, "role", None) != role
        or getattr(owner, "component_id", None) != expected_component_id
        or getattr(owner, "_sealed", None) is not True
        or _callable_source_path(function) != runner_path
    ):
        raise PublicRedockingPipelineProfileError(
            f"pipeline callback {callback_key} is not the canonical runner adapter"
        )
    code = getattr(function, "__code__", None)
    if not isinstance(code, CodeType) or _code_sha256(code) != method_code_sha256s.get(
        method_name
    ):
        raise PublicRedockingPipelineProfileError(
            f"pipeline callback {callback_key} code is not source-frozen"
        )
    return owner


def _validate_runtime_callbacks(
    callbacks: Mapping[str, Callable[..., object]],
    *,
    runner_path: Path | None,
    authority_bytes: bytes,
) -> tuple[Path, Mapping[str, Callable[..., object]]]:
    try:
        detached = dict(callbacks)
    except (TypeError, ValueError) as exc:
        raise PublicRedockingPipelineProfileError(
            "pipeline callbacks must be a mapping"
        ) from exc
    authority = json.loads(authority_bytes.decode("ascii"))
    expected_keys = set(authority["callback_keys"])
    if set(detached) != expected_keys:
        raise PublicRedockingPipelineProfileError(
            "pipeline callback keys do not match the canonical role layout"
        )
    callback_runner_path = _runtime_runner_source_path(detached)
    if runner_path is not None and callback_runner_path != runner_path:
        raise PublicRedockingPipelineProfileError(
            "pipeline callbacks are not loaded from the canonical runner path"
        )
    runner_path = callback_runner_path
    method_code_sha256s, scientific_stage_code_sha256s = _verify_runner_source(
        runner_path,
        authority_bytes=authority_bytes,
    )
    owners: dict[str, object] = {}
    owner_types: set[type[object]] = set()
    for callback_key in sorted(detached):
        owner = _validate_one_callback(
            callback_key,
            detached[callback_key],
            runner_path=runner_path,
            method_code_sha256s=method_code_sha256s,
        )
        role = callback_key.split(".", 1)[0]
        previous = owners.setdefault(role, owner)
        if previous is not owner:
            raise PublicRedockingPipelineProfileError(
                f"pipeline callbacks for {role} do not share one frozen owner"
            )
        owner_types.add(type(owner))
    if len(owners) != len(PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS):
        raise PublicRedockingPipelineProfileError(
            "pipeline callback owners are incomplete"
        )
    if len({id(owner) for owner in owners.values()}) != len(owners):
        raise PublicRedockingPipelineProfileError(
            "pipeline callback owners are cross-wired across roles"
        )
    if len(owner_types) != 1:
        raise PublicRedockingPipelineProfileError(
            "pipeline callbacks use mixed runner adapter implementations"
        )
    owner_type = next(iter(owner_types))
    if tuple(getattr(owner_type, "__slots__", ())) != (
        "role",
        "component_id",
        "_sealed",
    ):
        raise PublicRedockingPipelineProfileError(
            "pipeline callback owner exposes undeclared execution state"
        )
    reference_function = next(iter(detached.values())).__func__
    globals_mapping = reference_function.__globals__
    scientific_stage_authority = authority.get("scientific_stages")
    if not isinstance(scientific_stage_authority, Mapping) or set(
        scientific_stage_authority
    ) != set(_RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES):
        raise PublicRedockingPipelineProfileError(
            "pipeline scientific stage authority is incomplete"
        )
    for name in _RUNNER_SCIENTIFIC_STAGE_FUNCTION_NAMES:
        function = globals_mapping.get(name)
        declared = scientific_stage_authority.get(name)
        code = getattr(function, "__code__", None)
        if (
            not inspect.isfunction(function)
            or not isinstance(declared, Mapping)
            or function.__name__ != name
            or function.__qualname__ != declared.get("qualname")
            or function.__module__ != owner_type.__module__
            or _callable_source_path(function) != runner_path
            or not isinstance(code, CodeType)
            or _code_sha256(code) != scientific_stage_code_sha256s.get(name)
        ):
            raise PublicRedockingPipelineProfileError(
                f"pipeline scientific stage {name} is not source-frozen"
            )
    return runner_path, MappingProxyType(detached)


def _runtime_integrity_projection(value: object, *, depth: int = 0) -> object:
    """Bind callback-only runtime values without importing the runner's types."""

    if depth > 32:
        raise PublicRedockingPipelineProfileError(
            "pipeline runtime value exceeds the integrity depth bound"
        )
    if value is None or type(value) in {bool, int, str}:
        return value
    if type(value) is float:
        return {"kind": "float", "binary64_hex": value.hex()}
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "length": len(value),
            "sha256": hashlib.sha256(value).hexdigest(),
        }
    if isinstance(value, Path):
        return {"kind": "path", "value": str(value)}
    type_name = f"{type(value).__module__}.{type(value).__qualname__}"
    qualname = type(value).__qualname__
    if qualname == "_PreparedBenchmarkScientificInput":
        authority = getattr(value, "authority", None)
        scorer = getattr(value, "scorer", None)
        context = getattr(value, "context", None)
        budget = getattr(value, "budget", None)
        scorer_backend = getattr(value, "scorer_backend", None)
        return {
            "kind": "prepared_benchmark_scientific_input",
            "type": type_name,
            "case_id": str(getattr(value, "case_id", "")),
            "seed": int(getattr(value, "seed")),
            "variant_kind": str(getattr(value, "variant_kind", "")),
            "scorer_backend": str(getattr(scorer_backend, "value", "")),
            "source_binding": _runtime_integrity_projection(
                getattr(value, "source_binding"),
                depth=depth + 1,
            ),
            "authority_input_receipt_sha256": str(
                getattr(authority, "input_receipt_sha256", "")
            ),
            "budget": _runtime_integrity_projection(
                budget,
                depth=depth + 1,
            ),
            "scorer_contract_fingerprint_sha256": str(
                getattr(scorer, "contract_fingerprint_sha256", "")
            ),
            "context_fingerprint_sha256": str(
                getattr(context, "fingerprint_sha256", "")
            ),
        }
    if qualname == "_BenchmarkConformerStage":
        return {
            "kind": "benchmark_conformer_stage",
            "type": type_name,
            "source_binding_receipt_sha256": str(
                getattr(getattr(value, "prepared").source_binding, "get")(
                    "receipt_sha256", ""
                )
            ),
            "source_conformer_ensemble": _runtime_integrity_projection(
                getattr(value, "source_conformer_ensemble"),
                depth=depth + 1,
            ),
        }
    if qualname in {"_BenchmarkProposalStage", "_BenchmarkAdmissionStage"}:
        proposal_stage = (
            value
            if qualname == "_BenchmarkProposalStage"
            else getattr(value, "proposals")
        )
        proposal_rows = tuple(getattr(proposal_stage, "proposals"))
        for proposal in proposal_rows:
            assertion = getattr(proposal, "assert_integrity", None)
            if callable(assertion):
                assertion()
        projection: dict[str, object] = {
            "kind": (
                "benchmark_proposal_stage"
                if qualname == "_BenchmarkProposalStage"
                else "benchmark_admission_stage"
            ),
            "type": type_name,
            "candidates": [
                {
                    "candidate_id": str(getattr(proposal, "candidate_id", "")),
                    "proposal_index": int(getattr(proposal, "proposal_index")),
                    "fingerprint_sha256": str(
                        getattr(proposal, "fingerprint_sha256", "")
                    ),
                }
                for proposal in proposal_rows
            ],
            "guided_receipt": _runtime_integrity_projection(
                getattr(proposal_stage, "guided_receipt"),
                depth=depth + 1,
            ),
        }
        if qualname == "_BenchmarkProposalStage":
            projection.update(
                {
                    "development_proposal_receipt": (
                        _runtime_integrity_projection(
                            getattr(
                                proposal_stage,
                                "development_proposal_receipt",
                            ),
                            depth=depth + 1,
                        )
                    ),
                    "v3_proposal_indices": list(
                        getattr(proposal_stage, "v3_proposal_indices")
                    ),
                    "rescue_allocation": _runtime_integrity_projection(
                        getattr(proposal_stage, "rescue_allocation"),
                        depth=depth + 1,
                    ),
                }
            )
        return projection
    if qualname == "_BenchmarkRefinementStage":
        refined = getattr(value, "refined")
        candidate_rows = []
        for row in tuple(getattr(refined, "candidates")):
            if row is None:
                candidate_rows.append(None)
                continue
            original, current, refined_flag = row
            original.assert_integrity()
            current.assert_integrity()
            candidate_rows.append(
                {
                    "original_fingerprint_sha256": original.fingerprint_sha256,
                    "result_fingerprint_sha256": current.fingerprint_sha256,
                    "refined": bool(refined_flag),
                }
            )
        return {
            "kind": "benchmark_refinement_stage",
            "type": type_name,
            "candidates": candidate_rows,
            "failure_rows": [
                None
                if row is None
                else _runtime_integrity_projection(row, depth=depth + 1)
                for row in tuple(getattr(refined, "failure_rows"))
            ],
            "refinement_receipts": _runtime_integrity_projection(
                getattr(getattr(value, "refiner"), "receipts"),
                depth=depth + 1,
            ),
        }
    if qualname in {"_BenchmarkScoringStage", "_BenchmarkValidityStage"}:
        scientific = (
            getattr(value, "scored")
            if qualname == "_BenchmarkScoringStage"
            else getattr(value, "validated")
        )
        return {
            "kind": (
                "benchmark_scoring_stage"
                if qualname == "_BenchmarkScoringStage"
                else "benchmark_validity_stage"
            ),
            "type": type_name,
            "rows": [
                {
                    "row": _runtime_integrity_projection(
                        row,
                        depth=depth + 1,
                    ),
                    "score_evidence": _runtime_integrity_projection(
                        getattr(row, "score_evidence", None),
                        depth=depth + 1,
                    ),
                }
                for row in tuple(getattr(scientific, "rows"))
            ],
        }
    if qualname == "EngineV2PoseSearchOutcome":
        return {
            "kind": "engine_v2_pose_search_outcome",
            "type": type_name,
            "ranked_coordinates": _runtime_integrity_projection(
                getattr(value, "ranked_coordinates"),
                depth=depth + 1,
            ),
            "diagnostics": _runtime_integrity_projection(
                getattr(value, "diagnostics"),
                depth=depth + 1,
            ),
            "development_proposal_receipt": _runtime_integrity_projection(
                getattr(value, "development_proposal_receipt"),
                depth=depth + 1,
            ),
            "source_binding": _runtime_integrity_projection(
                getattr(value, "source_binding"),
                depth=depth + 1,
            ),
            "verified_candidate_evidence": _runtime_integrity_projection(
                getattr(value, "verified_candidate_evidence"),
                depth=depth + 1,
            ),
        }
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise PublicRedockingPipelineProfileError(
                "pipeline runtime mapping keys must be strings"
            )
        return {
            "kind": "mapping",
            "items": {
                key: _runtime_integrity_projection(item, depth=depth + 1)
                for key, item in sorted(value.items())
            },
        }
    if isinstance(value, (tuple, list)):
        return {
            "kind": type(value).__name__,
            "items": [
                _runtime_integrity_projection(item, depth=depth + 1) for item in value
            ],
        }
    for digest_name in (
        "receipt_sha256",
        "fingerprint_sha256",
        "input_receipt_sha256",
        "contract_fingerprint_sha256",
    ):
        try:
            digest = getattr(value, digest_name)
        except (AttributeError, RuntimeError, ValueError):
            continue
        if isinstance(digest, str) and _SHA256_RE.fullmatch(digest):
            return {
                "kind": "digest_bound_object",
                "type": type_name,
                "digest_name": digest_name,
                "digest": digest,
            }
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return {
            "kind": "typed_document",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "document": _runtime_integrity_projection(
                to_dict(),
                depth=depth + 1,
            ),
        }
    if is_dataclass(value):
        return {
            "kind": "dataclass",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "fields": {
                field.name: _runtime_integrity_projection(
                    getattr(value, field.name),
                    depth=depth + 1,
                )
                for field in fields(value)
                if hasattr(value, field.name)
            },
        }
    if all(
        hasattr(value, name) for name in ("detach", "cpu", "tolist", "shape", "dtype")
    ):
        detached = value.detach().cpu()
        values = detached.tolist()
        return {
            "kind": "tensor",
            "shape": [int(item) for item in detached.shape],
            "dtype": str(detached.dtype),
            "values_sha256": _sha256(values),
        }
    slots = getattr(type(value), "__slots__", ())
    if isinstance(slots, str):
        slots = (slots,)
    if isinstance(slots, tuple) and slots:
        return {
            "kind": "slotted_object",
            "type": f"{type(value).__module__}.{type(value).__qualname__}",
            "attributes": {
                name: _runtime_integrity_projection(
                    getattr(value, name),
                    depth=depth + 1,
                )
                for name in sorted(slots)
                if isinstance(name, str)
                and not name.startswith("_")
                and hasattr(value, name)
            },
        }
    raise PublicRedockingPipelineProfileError(
        "pipeline callback returned a runtime value without integrity projection"
    )


def _callback_stage_input(
    value: object,
    *,
    stage_name: str,
) -> VerifiedDockingPipelineStageOutput:
    try:
        return require_pipeline_stage(value, stage_name=stage_name)
    except Exception as exc:
        raise PublicRedockingPipelineProfileError(
            "pipeline callback received cross-wired stage authority"
        ) from exc


def _callback_stage_payload(
    value: object,
    *,
    role: str,
    method: str,
    candidate_ids: tuple[str, ...],
) -> DockingPipelineStagePayload:
    adapter_evidence: dict[str, object] = {
        "adapter_id": "betelgeuze.engine_v2.public_redocking_typed_adapter/1.0.0",
        "owner_role": role,
        "method": method,
        "runtime_type": f"{type(value).__module__}.{type(value).__qualname__}",
    }
    if isinstance(value, Mapping):
        try:
            _canonical_bytes(dict(value))
        except PublicRedockingPipelineProfileError:
            evidence = adapter_evidence
        else:
            evidence = dict(value)
    else:
        evidence = adapter_evidence
    runtime_projection = _runtime_integrity_projection(value)
    return docking_pipeline_stage_payload(
        value,
        evidence=evidence,
        integrity={
            "runtime_projection_sha256": _sha256(runtime_projection),
            "runtime_projection": runtime_projection,
            "callback_authority_bound": True,
        },
        candidate_ids=candidate_ids,
        candidate_count=(len(candidate_ids) if candidate_ids else None),
    )


class PublicRedockingPipelineComponent:
    """One role adapter bound to an exact implementation closure and variant."""

    __slots__ = (
        "role",
        "component_id",
        "_engine_implementation_sha256",
        "_variant_kind",
        "_callbacks",
        "_runner_path",
        "_callback_authority_bytes",
        "_sealed",
    )

    def __init__(
        self,
        role: str,
        *,
        engine_implementation_sha256: str,
        variant_kind: str,
        callbacks: Mapping[str, Callable[..., object]] | None = None,
    ) -> None:
        if role not in PUBLIC_REDOCKING_PIPELINE_ROLES:
            raise PublicRedockingPipelineProfileError("pipeline role is invalid")
        if _SHA256_RE.fullmatch(engine_implementation_sha256) is None:
            raise PublicRedockingPipelineProfileError(
                "engine implementation SHA-256 is invalid"
            )
        if variant_kind not in PUBLIC_REDOCKING_PIPELINE_VARIANTS:
            raise PublicRedockingPipelineProfileError("pipeline variant is invalid")
        runner_path, authority_bytes = _canonical_callback_authority()
        frozen_callbacks: Mapping[str, Callable[..., object]]
        if callbacks is None:
            frozen_callbacks = MappingProxyType({})
        else:
            runner_path, frozen_callbacks = _validate_runtime_callbacks(
                callbacks,
                runner_path=runner_path,
                authority_bytes=authority_bytes,
            )
        object.__setattr__(self, "role", role)
        object.__setattr__(
            self,
            "component_id",
            f"betelgeuze.engine_v2.public_redocking_{role}/1.0.0",
        )
        object.__setattr__(
            self,
            "_engine_implementation_sha256",
            engine_implementation_sha256,
        )
        object.__setattr__(self, "_variant_kind", variant_kind)
        object.__setattr__(self, "_callbacks", frozen_callbacks)
        object.__setattr__(self, "_runner_path", runner_path)
        object.__setattr__(self, "_callback_authority_bytes", authority_bytes)
        object.__setattr__(self, "_sealed", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_sealed", False):
            raise PublicRedockingPipelineProfileError(
                "public-redocking pipeline component is immutable"
            )
        object.__setattr__(self, name, value)

    def pipeline_configuration(self) -> Mapping[str, object]:
        return {
            "role": self.role,
            "variant_kind": self._variant_kind,
            "engine_implementation_sha256": self._engine_implementation_sha256,
            "callback_authority": json.loads(
                self._callback_authority_bytes.decode("ascii")
            ),
        }

    def _invoke(self, method: str, *values: object) -> object:
        callback_key = f"{self.role}.{method}"
        callback = self._callbacks.get(callback_key)
        if not callable(callback):
            raise PublicRedockingPipelineProfileError(
                f"pipeline callback {callback_key} is unavailable"
            )
        if self._runner_path is None:
            raise PublicRedockingPipelineProfileError(
                "runtime pipeline has no verified runner source"
            )
        current_authority_bytes = _frozen_callback_authority()
        if current_authority_bytes != self._callback_authority_bytes:
            raise PublicRedockingPipelineProfileError(
                "canonical public-redocking runner source changed after construction"
            )
        method_code_sha256s, _ = _verify_runner_source(
            self._runner_path,
            authority_bytes=self._callback_authority_bytes,
        )
        _validate_one_callback(
            callback_key,
            callback,
            runner_path=self._runner_path,
            method_code_sha256s=method_code_sha256s,
        )
        _validate_runtime_callbacks(
            self._callbacks,
            runner_path=self._runner_path,
            authority_bytes=self._callback_authority_bytes,
        )
        return callback(*values)

    def prepare(self, request: object) -> DockingPipelineStagePayload:
        return _callback_stage_payload(
            self._invoke("prepare", request),
            role=self.role,
            method="prepare",
            candidate_ids=(),
        )

    def provide(self, prepared: object) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        return _callback_stage_payload(
            self._invoke("provide", prepared_stage.value),
            role=self.role,
            method="provide",
            candidate_ids=(),
        )

    def generate(
        self,
        prepared: object,
        conformers: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        conformer_stage = _callback_stage_input(
            conformers,
            stage_name="conformer_provider.provide",
        )
        result = self._invoke(
            "generate",
            prepared_stage.value,
            conformer_stage.value,
        )
        proposals = getattr(result, "proposals", None)
        if not isinstance(proposals, tuple) or not proposals:
            raise PublicRedockingPipelineProfileError(
                "pipeline proposal callback did not return typed candidates"
            )
        candidate_ids = tuple(
            str(getattr(proposal, "candidate_id", "") or "").strip()
            for proposal in proposals
        )
        if any(not value for value in candidate_ids) or len(candidate_ids) != len(
            set(candidate_ids)
        ):
            raise PublicRedockingPipelineProfileError(
                "pipeline proposal callback candidate identity is invalid"
            )
        return _callback_stage_payload(
            result,
            role=self.role,
            method="generate",
            candidate_ids=candidate_ids,
        )

    def admit(
        self,
        prepared: object,
        proposals: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        proposal_stage = _callback_stage_input(
            proposals,
            stage_name="proposal_generator.generate",
        )
        return _callback_stage_payload(
            self._invoke("admit", prepared_stage.value, proposal_stage.value),
            role=self.role,
            method="admit",
            candidate_ids=proposal_stage.candidate_ids,
        )

    def bind(
        self,
        prepared: object,
        admission: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        admission_stage = _callback_stage_input(
            admission,
            stage_name="geometric_admission.admit",
        )
        return _callback_stage_payload(
            self._invoke("bind", prepared_stage.value, admission_stage.value),
            role=self.role,
            method="bind",
            candidate_ids=admission_stage.candidate_ids,
        )

    def refine(
        self,
        prepared: object,
        admission: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        stages = (
            _callback_stage_input(
                prepared,
                stage_name="input_preparer.prepare",
            ),
            _callback_stage_input(
                admission,
                stage_name="geometric_admission.admit",
            ),
            _callback_stage_input(scorer, stage_name="scorer.bind"),
        )
        result = self._invoke(
            "refine",
            *(stage.value for stage in stages),
        )
        return _callback_stage_payload(
            result,
            role=self.role,
            method="refine",
            candidate_ids=stages[1].candidate_ids,
        )

    def score(
        self,
        prepared: object,
        refined: object,
        scorer: object,
    ) -> DockingPipelineStagePayload:
        stages = (
            _callback_stage_input(
                prepared,
                stage_name="input_preparer.prepare",
            ),
            _callback_stage_input(refined, stage_name="refiner.refine"),
            _callback_stage_input(scorer, stage_name="scorer.bind"),
        )
        result = self._invoke(
            "score",
            *(stage.value for stage in stages),
        )
        return _callback_stage_payload(
            result,
            role=self.role,
            method="score",
            candidate_ids=stages[1].candidate_ids,
        )

    def evaluate(
        self,
        prepared: object,
        scored: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        scored_stage = _callback_stage_input(
            scored,
            stage_name="scorer.score",
        )
        return _callback_stage_payload(
            self._invoke("evaluate", prepared_stage.value, scored_stage.value),
            role=self.role,
            method="evaluate",
            candidate_ids=scored_stage.candidate_ids,
        )

    def rank(
        self,
        prepared: object,
        scored: object,
        validity: object,
    ) -> DockingPipelineStagePayload:
        prepared_stage = _callback_stage_input(
            prepared,
            stage_name="input_preparer.prepare",
        )
        scored_stage = _callback_stage_input(
            scored,
            stage_name="scorer.score",
        )
        validity_stage = _callback_stage_input(
            validity,
            stage_name="validity_evaluator.evaluate",
        )
        outcome = self._invoke(
            "rank",
            prepared_stage.value,
            scored_stage.value,
            validity_stage.value,
        )
        diagnostics = getattr(outcome, "diagnostics", None)
        ranked = getattr(diagnostics, "score_ranked_candidates", None)
        ranked_coordinates = getattr(outcome, "ranked_coordinates", None)
        if not isinstance(ranked, tuple) or not isinstance(
            ranked_coordinates,
            tuple,
        ):
            raise PublicRedockingPipelineProfileError(
                "pipeline rank callback did not return a typed outcome"
            )
        ranking = {
            "ranker_id": self.component_id,
            "ranking_semantics": "raw_score_then_proposal_index",
            "raw_top5_proposal_indices": [
                int(getattr(candidate, "proposal_index")) for candidate in ranked[:5]
            ],
            "validity_filtered_before_raw_rank": False,
            "invalid_top1_observable": True,
        }
        return docking_pipeline_stage_payload(
            outcome,
            evidence=ranking,
            integrity={
                "ranked_runtime_projection_sha256": _sha256(
                    _runtime_integrity_projection(outcome)
                ),
                "ranking_evidence_sha256": _sha256(ranking),
                "validity_stage_receipt_sha256": validity_stage.receipt_sha256,
            },
            candidate_ids=scored_stage.candidate_ids,
            candidate_count=len(scored_stage.candidate_ids),
        )

    def record(self, execution: object) -> DockingPipelineStagePayload:
        if not isinstance(execution, DockingPipelineExecution):
            raise PublicRedockingPipelineProfileError(
                "pipeline recorder received an invalid execution"
            )
        proposal_stage = execution.stage_outputs[2]
        if proposal_stage.stage_name != "proposal_generator.generate":
            raise PublicRedockingPipelineProfileError(
                "pipeline recorder candidate authority is cross-wired"
            )
        recorded = self._invoke("record", execution)
        if not isinstance(recorded, Mapping):
            raise PublicRedockingPipelineProfileError(
                "pipeline recorder did not return a mapping"
            )
        verified_execution_evidence = recorded.get("verified_execution_evidence")
        if not isinstance(verified_execution_evidence, Mapping):
            raise PublicRedockingPipelineProfileError(
                "pipeline recorder lacks verified execution evidence"
            )
        payload = _callback_stage_payload(
            recorded,
            role=self.role,
            method="record",
            candidate_ids=proposal_stage.candidate_ids,
        )
        return docking_pipeline_stage_payload(
            payload.value,
            evidence={"verified_execution_evidence": dict(verified_execution_evidence)},
            integrity=dict(payload.integrity),
            candidate_ids=payload.candidate_ids,
            candidate_count=payload.candidate_count,
        )


def build_public_redocking_pipeline(
    *,
    engine_implementation_sha256: str,
    variant_kind: str,
    callbacks: Mapping[str, Callable[..., object]] | None = None,
) -> DockingPipeline:
    profile_id = (
        PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID
        if not variant_kind
        else PUBLIC_REDOCKING_DEVELOPMENT_PIPELINE_PROFILE_ID
    )
    roles = tuple(PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS)
    components = tuple(
        PublicRedockingPipelineComponent(
            role,
            engine_implementation_sha256=engine_implementation_sha256,
            variant_kind=variant_kind,
            callbacks=callbacks,
        )
        for role in roles
    )
    return DockingPipeline(*components, profile_id=profile_id)


def public_redocking_pipeline_profile_identity(
    *,
    engine_implementation_sha256: str,
    variant_kind: str,
) -> tuple[str, str]:
    pipeline = build_public_redocking_pipeline(
        engine_implementation_sha256=engine_implementation_sha256,
        variant_kind=variant_kind,
    )
    return pipeline.profile_id, pipeline.profile_sha256


__all__ = [
    "PUBLIC_REDOCKING_DEVELOPMENT_PIPELINE_PROFILE_ID",
    "PUBLIC_REDOCKING_PIPELINE_ROLE_METHODS",
    "PUBLIC_REDOCKING_PIPELINE_ROLES",
    "PUBLIC_REDOCKING_PIPELINE_VARIANTS",
    "PUBLIC_REDOCKING_RUNNER_RELATIVE_PATH",
    "PUBLIC_REDOCKING_STAGE0_PIPELINE_PROFILE_ID",
    "PublicRedockingPipelineComponent",
    "PublicRedockingPipelineProfileError",
    "build_public_redocking_pipeline",
    "public_redocking_pipeline_profile_identity",
]
