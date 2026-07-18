"""Exact source binding for the independent minimization reference.

This artifact advances implementation readiness only.  It binds the frozen
pre-result protocol and materialization manifest to an import-separated
stdlib minimization implementation.  It does not authorize validation
execution, collect results, complete scientific review, or promote claims.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping

from . import reference_minimization_independent_oracle as _minimization_oracle
from . import reference_validation_oracle as _analytic_oracle
from .reference_minimization_independent_oracle import (
    INDEPENDENT_MINIMIZATION_ORACLE_ID,
    INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID,
    INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID,
    INDEPENDENT_MINIMIZATION_ORACLE_VERSION,
)
from .reference_minimization_validation_materializer import (
    CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID,
    CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION,
    cpu_minimization_validation_materialization_manifest_document,
    cpu_minimization_validation_materializer_source_sha256,
)
from .reference_minimization_validation_protocol import (
    FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
    cpu_minimization_validation_protocol_document,
)
from .reference_validation_oracle import (
    INDEPENDENT_ANALYTIC_ORACLE_ID,
    INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID,
    INDEPENDENT_ANALYTIC_ORACLE_VERSION,
)


REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_reference_minimization_validation_artifact_binding/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_ID = (
    "cpu_reference_minimization_materializer_independent_oracle_binding/1.0.0"
)
REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_VERSION = "1.0.0"
REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_FROZEN_AT_UTC = (
    "2026-07-18T01:50:52Z"
)
REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_REVIEWER_ROLE = (
    "repository_maintainer"
)
REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_REVIEWER_IDENTITY_SHA256 = (
    "8d0a02097003a141b825483fd0b7195deee65ac253bfd2c07a91a8c48ae6349e"
)

FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256 = (
    "b27bf9858811ff967bb54726616a66149edf44544b2cb1bdf9f57ba410345b26"
)
FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256 = (
    "71627d266a6b1c64b2e6db0f8126bd91e8381c017ea4c6ae2bb76ec84d7b257b"
)
FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256 = (
    "950a8e8200e2b8160b172f2c854f826bb558e2b2598bd38b790bf6e6fa9236d9"
)
FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256 = (
    "100d218ab412088c8c4913f70757547b80b77b0d17155739b52e4e27121b22b7"
)
FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256 = (
    "d9b55fbad450aa1d4a410f8deb5be428aceeb8fd539335665a9a9b1dfc8a6156"
)

_ALLOWED_MINIMIZATION_ORACLE_IMPORTS = frozenset(
    {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "math",
        "numbers",
        "typing",
        ".reference_validation_oracle",
    }
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "torch",
    "numpy",
    "jax",
    "tensorflow",
    "openmm",
    "simtk",
    "rdkit",
    ".reference_forcefield",
    ".reference_forcefield_v2",
    ".reference_minimization",
    ".reference_constrained_minimization",
    ".reference_solvation",
    ".reference_minimization_validation_materializer",
    ".reference_minimization_validation_protocol",
)
_FORBIDDEN_DYNAMIC_IMPORT_TOKENS = ("__import__", "importlib", "eval(", "exec(")

_CURRENT_BLOCKERS = (
    "independent_minimization_reference_is_not_validation_result_evidence",
    "independent_minimization_reference_not_independently_reviewed",
    "independent_scientific_review_missing",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "minimization_validation_results_not_collected",
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_domain_not_established",
    "parameter_fitting_not_authorized",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceMinimizationValidationArtifactBindingError(ValueError):
    """The independent minimization source binding drifted."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ReferenceMinimizationValidationArtifactBindingError(
            "minimization artifact binding is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _source_path(module: object, *, expected_name: str) -> Path:
    module_file = getattr(module, "__file__", None)
    if not module_file:
        raise ReferenceMinimizationValidationArtifactBindingError(
            f"{expected_name} source path is unavailable"
        )
    source = Path(module_file)
    if source.is_symlink():
        raise ReferenceMinimizationValidationArtifactBindingError(
            f"{expected_name} source must not be a symlink"
        )
    resolved = source.resolve(strict=True)
    physics_root = Path(__file__).resolve(strict=True).parent
    if not resolved.is_relative_to(physics_root):
        raise ReferenceMinimizationValidationArtifactBindingError(
            f"{expected_name} source escaped the physics package"
        )
    if not stat.S_ISREG(resolved.stat().st_mode):
        raise ReferenceMinimizationValidationArtifactBindingError(
            f"{expected_name} source must be a regular file"
        )
    return resolved


def independent_minimization_oracle_source_sha256() -> str:
    """Return the exact independent minimization implementation identity."""

    return hashlib.sha256(
        _source_path(
            _minimization_oracle,
            expected_name="independent minimization oracle",
        ).read_bytes()
    ).hexdigest()


def independent_analytic_oracle_source_sha256() -> str:
    """Return the exact scalar analytic dependency identity."""

    return hashlib.sha256(
        _source_path(
            _analytic_oracle,
            expected_name="independent analytic oracle",
        ).read_bytes()
    ).hexdigest()


def _minimization_oracle_import_audit() -> dict[str, Any]:
    source_path = _source_path(
        _minimization_oracle,
        expected_name="independent minimization oracle",
    )
    source_bytes = source_path.read_bytes()
    try:
        source = source_bytes.decode("utf-8")
        tree = ast.parse(source, filename=source_path.name)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ReferenceMinimizationValidationArtifactBindingError(
            "independent minimization oracle must be valid UTF-8 Python"
        ) from exc
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            imports.append(f"{prefix}{node.module or ''}")
    unexpected = sorted(set(imports) - _ALLOWED_MINIMIZATION_ORACLE_IMPORTS)
    forbidden = sorted(
        name
        for name in imports
        if any(
            name == prefix or name.startswith(f"{prefix}.")
            for prefix in _FORBIDDEN_IMPORT_PREFIXES
        )
    )
    dynamic_tokens = sorted(
        token for token in _FORBIDDEN_DYNAMIC_IMPORT_TOKENS if token in source
    )
    if unexpected or forbidden or dynamic_tokens:
        raise ReferenceMinimizationValidationArtifactBindingError(
            "independent minimization oracle violates the frozen import boundary"
        )
    return {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "imports": sorted(imports),
        "allowed_imports": sorted(_ALLOWED_MINIMIZATION_ORACLE_IMPORTS),
        "forbidden_import_prefixes": list(_FORBIDDEN_IMPORT_PREFIXES),
        "forbidden_dynamic_import_tokens": list(_FORBIDDEN_DYNAMIC_IMPORT_TOKENS),
        "analytic_oracle_is_only_relative_dependency": True,
        "operational_evaluator_imported": False,
        "operational_minimizer_imported": False,
        "constraint_or_solvation_implementation_imported": False,
        "protocol_or_materializer_imported": False,
        "third_party_dependency_imported": False,
        "dynamic_import_tokens_present": False,
        "audit_passed": True,
    }


def _claim_policy() -> dict[str, bool]:
    return {
        "protocol_definition_frozen": True,
        "fixture_materializer_implemented": True,
        "fixture_materializer_source_identity_bound": True,
        "independent_analytic_oracle_source_identity_bound": True,
        "independent_minimization_reference_implemented": True,
        "independent_minimization_reference_source_identity_bound": True,
        "independent_minimization_reference_import_boundary_verified": True,
        "independent_scientific_review_completed": False,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "runtime_parameter_values_independently_reviewed": False,
        "scientific_applicability_established": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "minimization_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


def reference_minimization_validation_artifact_binding_document() -> dict[str, Any]:
    """Return the frozen source binding with all result gates closed."""

    protocol = cpu_minimization_validation_protocol_document()
    materialization = cpu_minimization_validation_materialization_manifest_document()
    actual_sources = {
        "materializer_source_sha256": (
            cpu_minimization_validation_materializer_source_sha256()
        ),
        "analytic_oracle_source_sha256": (independent_analytic_oracle_source_sha256()),
        "minimization_oracle_source_sha256": (
            independent_minimization_oracle_source_sha256()
        ),
    }
    expected_sources = {
        "materializer_source_sha256": (
            FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256
        ),
        "analytic_oracle_source_sha256": (
            FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256
        ),
        "minimization_oracle_source_sha256": (
            FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256
        ),
    }
    if actual_sources != expected_sources:
        raise ReferenceMinimizationValidationArtifactBindingError(
            "bound minimization source identity drifted"
        )
    if materialization["materialization_manifest_sha256"] != (
        FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256
    ):
        raise ReferenceMinimizationValidationArtifactBindingError(
            "bound minimization materialization manifest drifted"
        )
    projection = {
        "schema_id": (REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID),
        "binding_id": REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_ID,
        "binding_version": (REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_VERSION),
        "frozen_at_utc": (
            REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_FROZEN_AT_UTC
        ),
        "reviewer": {
            "role": (REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_REVIEWER_ROLE),
            "identity_sha256": (
                REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_REVIEWER_IDENTITY_SHA256
            ),
            "review_scope": "source_identity_and_import_boundary_only",
            "independent_scientific_review": False,
        },
        "purpose": {
            "scope": "bind_exact_minimization_materializer_and_import_separated_reference",
            "implementation_artifact_only": True,
            "validation_result": False,
            "authorizes_validation_execution": False,
            "authorizes_parameter_fitting": False,
        },
        "dependencies": {
            "protocol_sha256": FROZEN_CPU_MINIMIZATION_VALIDATION_PROTOCOL_SHA256,
            "fixture_manifest_sha256": protocol["fixture_manifest"][
                "fixture_manifest_sha256"
            ],
            "case_manifest_sha256": protocol["case_manifest"]["case_manifest_sha256"],
            "materialization_manifest_sha256": materialization[
                "materialization_manifest_sha256"
            ],
            **actual_sources,
        },
        "artifacts": {
            "materializer": {
                "id": CPU_MINIMIZATION_VALIDATION_MATERIALIZER_ID,
                "version": CPU_MINIMIZATION_VALIDATION_MATERIALIZER_VERSION,
            },
            "analytic_oracle": {
                "id": INDEPENDENT_ANALYTIC_ORACLE_ID,
                "version": INDEPENDENT_ANALYTIC_ORACLE_VERSION,
                "schema_id": INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID,
            },
            "minimization_oracle": {
                "id": INDEPENDENT_MINIMIZATION_ORACLE_ID,
                "version": INDEPENDENT_MINIMIZATION_ORACLE_VERSION,
                "input_schema_id": INDEPENDENT_MINIMIZATION_ORACLE_INPUT_SCHEMA_ID,
                "result_schema_id": INDEPENDENT_MINIMIZATION_ORACLE_SCHEMA_ID,
            },
        },
        "import_audit": _minimization_oracle_import_audit(),
        "claim_policy": _claim_policy(),
        "authorization_gate": {
            "decision": "closed",
            "current_blockers": list(_CURRENT_BLOCKERS),
        },
    }
    binding_sha256 = _sha256(projection)
    if binding_sha256 != (
        FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256
    ):
        raise ReferenceMinimizationValidationArtifactBindingError(
            "frozen minimization artifact binding identity drifted"
        )
    return {**projection, "artifact_binding_sha256": binding_sha256}


def require_reference_minimization_validation_artifact_binding_document(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Require exact equality with the frozen source binding."""

    candidate = json.loads(json.dumps(dict(value), allow_nan=False))
    expected = reference_minimization_validation_artifact_binding_document()
    if candidate != expected:
        raise ReferenceMinimizationValidationArtifactBindingError(
            "minimization artifact binding does not match the frozen document"
        )
    if candidate["artifact_binding_sha256"] != _sha256(
        {
            key: item
            for key, item in candidate.items()
            if key != "artifact_binding_sha256"
        }
    ):
        raise ReferenceMinimizationValidationArtifactBindingError(
            "minimization artifact binding digest mismatch"
        )
    return candidate


def reference_minimization_validation_artifact_binding_json_bytes() -> bytes:
    """Return canonical ASCII JSON for the frozen binding."""

    return (
        _canonical_bytes(reference_minimization_validation_artifact_binding_document())
        + b"\n"
    )


def write_reference_minimization_validation_artifact_binding_json(
    path: str | os.PathLike[str],
) -> Path:
    """Atomically write the frozen binding without following a symlink."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ReferenceMinimizationValidationArtifactBindingError(
            "artifact binding destination must not be a symlink"
        )
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(
                reference_minimization_validation_artifact_binding_json_bytes()
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o644)
        os.replace(temporary_name, destination)
    finally:
        if temporary_name is not None and Path(temporary_name).exists():
            Path(temporary_name).unlink()
    return destination


__all__ = [
    "FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZATION_MANIFEST_SHA256",
    "FROZEN_CPU_MINIMIZATION_VALIDATION_MATERIALIZER_SOURCE_SHA256",
    "FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256",
    "FROZEN_INDEPENDENT_MINIMIZATION_ORACLE_SOURCE_SHA256",
    "FROZEN_REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SHA256",
    "REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID",
    "REFERENCE_MINIMIZATION_VALIDATION_ARTIFACT_BINDING_VERSION",
    "ReferenceMinimizationValidationArtifactBindingError",
    "independent_analytic_oracle_source_sha256",
    "independent_minimization_oracle_source_sha256",
    "reference_minimization_validation_artifact_binding_document",
    "reference_minimization_validation_artifact_binding_json_bytes",
    "require_reference_minimization_validation_artifact_binding_document",
    "write_reference_minimization_validation_artifact_binding_json",
]
