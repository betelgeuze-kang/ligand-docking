"""Frozen source binding for CPU evaluator, materializer, and analytic oracle.

This record advances implementation readiness only.  It binds the exact
materializer and independent-oracle sources to the already-frozen pre-result
protocol while retaining every scientific review, authorization, result,
fitting, minimization, and product gate in the closed state.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping

from . import reference_validation_oracle as _oracle_module
from .reference_validation_materializer import (
    REFERENCE_VALIDATION_MATERIALIZER_ID,
    REFERENCE_VALIDATION_MATERIALIZER_VERSION,
    reference_validation_materialization_manifest_document,
    reference_validation_materializer_source_sha256,
)
from .reference_validation_oracle import (
    INDEPENDENT_ANALYTIC_ORACLE_ID,
    INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID,
    INDEPENDENT_ANALYTIC_ORACLE_VERSION,
)
from .reference_validation_protocol import frozen_cpu_reference_validation_protocol


REFERENCE_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID = "betelgeuze.engine_v2_reference_validation_artifact_binding/1.2.0"
REFERENCE_VALIDATION_ARTIFACT_BINDING_ID = "cpu_reference_validation_materializer_oracle_binding/1.2.0"
REFERENCE_VALIDATION_ARTIFACT_BINDING_VERSION = "1.2.0"
REFERENCE_VALIDATION_ARTIFACT_BINDING_FROZEN_AT_UTC = "2026-07-24T18:10:00Z"
REFERENCE_VALIDATION_ARTIFACT_BINDING_REVIEWER_ROLE = "repository_maintainer"
REFERENCE_VALIDATION_ARTIFACT_BINDING_REVIEWER_IDENTITY_SHA256 = (
    "ffaaea9cebb5975ed140fa0633ea4cb44e1f241f6bc73c916164c0ea5123b584"
)

FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256 = (
    "2d4eda974f2a551f3963ead1f12c5f474414e6760aa461e735d7aa45829bf19a"
)
FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256 = "71627d266a6b1c64b2e6db0f8126bd91e8381c017ea4c6ae2bb76ec84d7b257b"
FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256 = (
    "af8422789c5c9a473bce05d93b7e502d00cd0a955601ff39dbb3fd3b831648db"
)
FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256 = (
    "b3341f3b98e29594cfcd727353553efa466116f275f5250c4ae944d624ef62b0"
)
FROZEN_LEGACY_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256_V1_1 = "8518e10598ef0b17203720e2494b0e4ff67c2d24058b2677016daa180c1674ae"
FROZEN_LEGACY_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256_V1 = "76241cbc9441f8fbed86cb5858069e3c64b21b37838d2ae94d1b2c768db5b57e"

_REFERENCE_EVALUATOR_SOURCE_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_forcefield.py"
)
_ORACLE_SOURCE_RELATIVE_PATH = "betelgeuze_engine_v2/physics/reference_validation_oracle.py"
_MATERIALIZER_SOURCE_RELATIVE_PATH = "betelgeuze_engine_v2/physics/reference_validation_materializer.py"
_ALLOWED_ORACLE_IMPORT_ROOTS = frozenset({"__future__", "dataclasses", "hashlib", "json", "math", "numbers", "typing"})
_FORBIDDEN_ORACLE_IMPORT_PREFIXES = (
    "betelgeuze_engine_v2",
    "torch",
    "numpy",
    "jax",
    "tensorflow",
    "openmm",
    "simtk",
    "rdkit",
)
_FORBIDDEN_DYNAMIC_IMPORT_TOKENS = (
    "__import__",
    "importlib",
    "eval(",
    "exec(",
)

_CURRENT_BLOCKERS = (
    "reviewed_runtime_parameter_values_not_bound",
    "scientific_parameter_applicability_domain_not_established",
    "scientific_holdout_case_manifest_not_frozen",
    "independent_scientific_review_missing",
    "implementation_author_and_independent_reviewer_separation_not_attested",
    "signed_execution_authorization_receipt_schema_not_frozen",
    "signed_execution_authorization_receipt_missing",
    "validation_execution_not_authorized",
    "validation_results_not_collected",
    "parameter_fitting_not_authorized",
    "minimization_validation_protocol_missing",
    "scientific_validation_missing",
    "product_integration_not_qualified",
)


class ReferenceValidationArtifactBindingError(ValueError):
    """The frozen source binding or its closed gate drifted."""


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
        raise ReferenceValidationArtifactBindingError("artifact binding is not canonical JSON") from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _source_path(module_file: str | None, *, expected_name: str) -> Path:
    if not module_file:
        raise ReferenceValidationArtifactBindingError(f"{expected_name} source path is unavailable")
    source = Path(module_file)
    if source.is_symlink():
        raise ReferenceValidationArtifactBindingError(f"{expected_name} source must not be a symlink")
    resolved = source.resolve(strict=True)
    physics_root = Path(__file__).resolve(strict=True).parent
    if not resolved.is_relative_to(physics_root):
        raise ReferenceValidationArtifactBindingError(f"{expected_name} source escaped the physics package")
    mode = resolved.stat().st_mode
    if not stat.S_ISREG(mode):
        raise ReferenceValidationArtifactBindingError(f"{expected_name} source must be a regular file")
    return resolved


def _oracle_source_path() -> Path:
    return _source_path(
        getattr(_oracle_module, "__file__", None),
        expected_name="independent analytic oracle",
    )


def independent_analytic_oracle_source_sha256() -> str:
    return hashlib.sha256(_oracle_source_path().read_bytes()).hexdigest()


def _reference_evaluator_source_path() -> Path:
    return _source_path(
        str(Path(__file__).resolve(strict=True).parent / "reference_forcefield.py"),
        expected_name="reference force-field evaluator",
    )


def reference_forcefield_source_sha256() -> str:
    """Return the exact evaluator source identity frozen for this study."""

    return hashlib.sha256(_reference_evaluator_source_path().read_bytes()).hexdigest()


def _oracle_import_audit() -> dict[str, Any]:
    source_path = _oracle_source_path()
    source_bytes = source_path.read_bytes()
    try:
        source_text = source_bytes.decode("utf-8")
        tree = ast.parse(source_text, filename=source_path.name)
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise ReferenceValidationArtifactBindingError("independent oracle source must be valid UTF-8 Python") from exc
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise ReferenceValidationArtifactBindingError("independent oracle must not use relative imports")
            imports.append(node.module or "")
    roots = {name.split(".", 1)[0] for name in imports}
    unexpected = sorted(roots - _ALLOWED_ORACLE_IMPORT_ROOTS)
    forbidden = sorted(
        name
        for name in imports
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in _FORBIDDEN_ORACLE_IMPORT_PREFIXES)
    )
    dynamic_tokens = sorted(token for token in _FORBIDDEN_DYNAMIC_IMPORT_TOKENS if token in source_text)
    if unexpected or forbidden or dynamic_tokens:
        raise ReferenceValidationArtifactBindingError("independent oracle source violates the frozen import boundary")
    return {
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "imports": sorted(imports),
        "allowed_import_roots": sorted(_ALLOWED_ORACLE_IMPORT_ROOTS),
        "forbidden_import_prefixes": list(_FORBIDDEN_ORACLE_IMPORT_PREFIXES),
        "forbidden_dynamic_import_tokens": list(_FORBIDDEN_DYNAMIC_IMPORT_TOKENS),
        "relative_imports_present": False,
        "unexpected_imports_present": False,
        "dynamic_import_tokens_present": False,
        "reference_evaluator_imported": False,
        "validation_protocol_imported": False,
        "third_party_dependency_imported": False,
        "audit_passed": True,
    }


def _claim_policy() -> dict[str, bool]:
    return {
        "protocol_definition_frozen": True,
        "fixture_materializer_implemented": True,
        "fixture_materializer_source_identity_bound": True,
        "reference_evaluator_source_identity_bound": True,
        "independent_oracle_implemented": True,
        "independent_oracle_source_identity_bound": True,
        "independent_oracle_import_boundary_verified": True,
        "validation_execution_authorized": False,
        "validation_results_collected": False,
        "force_or_energy_validated": False,
        "runtime_parameter_values_independently_reviewed": False,
        "scientific_applicability_established": False,
        "independent_scientific_review_completed": False,
        "parameter_fitting_proposal_authorized": False,
        "parameter_fitting_authorized": False,
        "minimization_validated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }


@dataclass(frozen=True, slots=True)
class ReferenceValidationArtifactBinding:
    """Immutable binding of source artifacts to the frozen protocol."""

    schema_id: str
    binding_id: str
    binding_version: str
    frozen_at_utc: str
    reviewer_role: str
    reviewer_identity_sha256: str
    protocol_sha256: str
    fixture_manifest_sha256: str
    h5_applicability_record_sha256: str
    materialization_manifest_sha256: str
    reference_evaluator_source_sha256: str
    materializer_source_sha256: str
    oracle_source_sha256: str

    def __post_init__(self) -> None:
        if self.schema_id != REFERENCE_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID:
            raise ReferenceValidationArtifactBindingError("unsupported validation artifact binding schema")
        if self.binding_id != REFERENCE_VALIDATION_ARTIFACT_BINDING_ID:
            raise ReferenceValidationArtifactBindingError("unsupported validation artifact binding identity")
        if self.binding_version != REFERENCE_VALIDATION_ARTIFACT_BINDING_VERSION:
            raise ReferenceValidationArtifactBindingError("unsupported validation artifact binding version")
        if not self.reviewer_role:
            raise ReferenceValidationArtifactBindingError("artifact binding reviewer role must be non-empty")
        for name in (
            "reviewer_identity_sha256",
            "protocol_sha256",
            "fixture_manifest_sha256",
            "h5_applicability_record_sha256",
            "materialization_manifest_sha256",
            "reference_evaluator_source_sha256",
            "materializer_source_sha256",
            "oracle_source_sha256",
        ):
            value = getattr(self, name)
            if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
                raise ReferenceValidationArtifactBindingError(f"{name} must be a lowercase SHA-256")

    def projection(self) -> dict[str, Any]:
        import_audit = _oracle_import_audit()
        return {
            "schema_id": self.schema_id,
            "binding_id": self.binding_id,
            "binding_version": self.binding_version,
            "frozen_at_utc": self.frozen_at_utc,
            "superseded_binding_sha256": (
                FROZEN_LEGACY_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256_V1_1
            ),
            "legacy_binding_chain_sha256s": [
                FROZEN_LEGACY_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256_V1
            ],
            "refreeze_reason": (
                "bind_cpu_reference_validation_protocol_1_2_0_without_"
                "evaluator_or_oracle_source_change"
            ),
            "purpose": {
                "scope": "bind_exact_reference_evaluator_fixture_materializer_and_independent_analytic_oracle",
                "implementation_artifact_only": True,
                "validation_result": False,
                "authorizes_validation_execution": False,
                "authorizes_parameter_fitting_proposal": False,
                "authorizes_parameter_fitting": False,
            },
            "dependencies": {
                "protocol_sha256": self.protocol_sha256,
                "fixture_manifest_sha256": self.fixture_manifest_sha256,
                "h5_applicability_record_sha256": (self.h5_applicability_record_sha256),
                "exact_dependencies_required": True,
                "dependency_claim_status_inherited": False,
            },
            "materializer": {
                "status": "implemented_exact_source_bound_not_executed_as_validation_study",
                "materializer_id": REFERENCE_VALIDATION_MATERIALIZER_ID,
                "materializer_version": REFERENCE_VALIDATION_MATERIALIZER_VERSION,
                "source_relative_path": _MATERIALIZER_SOURCE_RELATIVE_PATH,
                "source_sha256": self.materializer_source_sha256,
                "materialization_manifest_sha256": (self.materialization_manifest_sha256),
                "all_frozen_fixtures_materialized": True,
                "all_frozen_mutations_materialized": True,
                "all_frozen_cases_retained": True,
                "result_values_present": False,
            },
            "reference_evaluator": {
                "status": "implemented_exact_source_bound_not_executed_as_validation_study",
                "source_relative_path": _REFERENCE_EVALUATOR_SOURCE_RELATIVE_PATH,
                "source_sha256": self.reference_evaluator_source_sha256,
                "exact_source_reverification_required_before_execution": True,
                "result_values_present": False,
            },
            "independent_oracle": {
                "status": "implemented_exact_source_bound_pending_independent_scientific_review",
                "oracle_id": INDEPENDENT_ANALYTIC_ORACLE_ID,
                "oracle_version": INDEPENDENT_ANALYTIC_ORACLE_VERSION,
                "oracle_schema_id": INDEPENDENT_ANALYTIC_ORACLE_SCHEMA_ID,
                "source_relative_path": _ORACLE_SOURCE_RELATIVE_PATH,
                "source_sha256": self.oracle_source_sha256,
                "equation_scope": [
                    "harmonic_bond",
                    "harmonic_angle",
                    "proper_periodic_torsion",
                    "lorentz_berthelot_lennard_jones",
                    "screened_coulomb",
                    "explicit_pair_exclusion_and_scaling",
                    "quintic_switch",
                    "orthorhombic_minimum_image",
                ],
                "force_method": "negative_exact_forward_mode_derivative_of_scalar_energy",
                "finite_difference_used_for_oracle_forces": False,
                "external_molecular_solver_used": False,
                "third_party_numeric_runtime_used": False,
                "import_audit": import_audit,
                "independent_scientific_review_completed": False,
            },
            "review": {
                "status": "maintainer_reviewed_implementation_boundary_only",
                "reviewer_role": self.reviewer_role,
                "reviewer_identity_sha256": self.reviewer_identity_sha256,
                "independent_scientific_reviewer_identity_sha256": None,
                "independent_scientific_reviewed_at_utc": None,
                "implementation_author_separation_attested": False,
                "superseded": False,
                "revoked": False,
            },
            "authorization_gate": {
                "status": "closed",
                "validation_execution_authorized": False,
                "parameter_fitting_proposal_authorized": False,
                "parameter_fitting_authorized": False,
                "signed_authorization_receipt_schema_frozen": False,
                "signed_authorization_receipt_present": False,
                "current_blockers": list(_CURRENT_BLOCKERS),
            },
            "result_state": {
                "validation_study_executed": False,
                "result_receipt_created": False,
                "energy_or_force_metrics_collected": False,
                "failure_rows_observed": False,
                "parameter_fitting_data_created": False,
            },
            "claim_policy": _claim_policy(),
            "blockers": list(_CURRENT_BLOCKERS),
        }

    @property
    def binding_sha256(self) -> str:
        return _sha256(self.projection())

    def to_dict(self) -> dict[str, Any]:
        payload = self.projection()
        payload["binding_sha256"] = self.binding_sha256
        return payload


def _build_reference_validation_artifact_binding() -> ReferenceValidationArtifactBinding:
    protocol = frozen_cpu_reference_validation_protocol()
    materialization = reference_validation_materialization_manifest_document(protocol)
    evaluator_source = reference_forcefield_source_sha256()
    materializer_source = reference_validation_materializer_source_sha256()
    oracle_source = independent_analytic_oracle_source_sha256()
    if evaluator_source != FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256:
        raise ReferenceValidationArtifactBindingError(
            "frozen reference evaluator source SHA-256 drifted"
        )
    if materializer_source != FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256:
        raise ReferenceValidationArtifactBindingError("frozen fixture materializer source SHA-256 drifted")
    if oracle_source != FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256:
        raise ReferenceValidationArtifactBindingError("frozen independent analytic oracle source SHA-256 drifted")
    import_audit = _oracle_import_audit()
    if import_audit["source_sha256"] != oracle_source:
        raise ReferenceValidationArtifactBindingError("oracle import audit source identity drifted")
    return ReferenceValidationArtifactBinding(
        schema_id=REFERENCE_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID,
        binding_id=REFERENCE_VALIDATION_ARTIFACT_BINDING_ID,
        binding_version=REFERENCE_VALIDATION_ARTIFACT_BINDING_VERSION,
        frozen_at_utc=REFERENCE_VALIDATION_ARTIFACT_BINDING_FROZEN_AT_UTC,
        reviewer_role=REFERENCE_VALIDATION_ARTIFACT_BINDING_REVIEWER_ROLE,
        reviewer_identity_sha256=(REFERENCE_VALIDATION_ARTIFACT_BINDING_REVIEWER_IDENTITY_SHA256),
        protocol_sha256=protocol.protocol_sha256,
        fixture_manifest_sha256=protocol.fixture_manifest_sha256,
        h5_applicability_record_sha256=protocol.h5_applicability_record_sha256,
        materialization_manifest_sha256=materialization["materialization_manifest_sha256"],
        reference_evaluator_source_sha256=evaluator_source,
        materializer_source_sha256=materializer_source,
        oracle_source_sha256=oracle_source,
    )


def frozen_reference_validation_artifact_binding() -> ReferenceValidationArtifactBinding:
    """Return the exact source binding and reject any artifact drift."""

    binding = _build_reference_validation_artifact_binding()
    if binding.binding_sha256 != FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256:
        raise ReferenceValidationArtifactBindingError("frozen validation artifact binding SHA-256 drifted")
    return binding


def reference_validation_artifact_binding_document() -> dict[str, Any]:
    return frozen_reference_validation_artifact_binding().to_dict()


def require_reference_validation_artifact_binding_document(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ReferenceValidationArtifactBindingError("artifact binding document must be a mapping")
    try:
        observed = json.loads(_canonical_bytes(dict(payload)).decode("ascii"))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ReferenceValidationArtifactBindingError("artifact binding document is invalid") from exc
    expected = reference_validation_artifact_binding_document()
    if observed != expected:
        raise ReferenceValidationArtifactBindingError("artifact binding document does not match the frozen record")
    return observed


@dataclass(frozen=True, slots=True)
class ReferenceValidationArtifactAuthorizationDecision:
    binding_sha256: str
    validation_execution_authorized: bool
    parameter_fitting_proposal_authorized: bool
    parameter_fitting_authorized: bool
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.validation_execution_authorized
            or self.parameter_fitting_proposal_authorized
            or self.parameter_fitting_authorized
        ):
            raise ReferenceValidationArtifactBindingError("artifact implementation cannot open an authorization gate")
        if not self.blockers:
            raise ReferenceValidationArtifactBindingError("closed artifact authorization must retain blockers")

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_sha256": self.binding_sha256,
            "validation_execution_authorized": self.validation_execution_authorized,
            "parameter_fitting_proposal_authorized": (self.parameter_fitting_proposal_authorized),
            "parameter_fitting_authorized": self.parameter_fitting_authorized,
            "blockers": list(self.blockers),
        }


def reference_validation_artifact_authorization_decision(
    binding_document: Mapping[str, Any] | None = None,
) -> ReferenceValidationArtifactAuthorizationDecision:
    document = (
        reference_validation_artifact_binding_document()
        if binding_document is None
        else require_reference_validation_artifact_binding_document(binding_document)
    )
    gate = document["authorization_gate"]
    if gate["status"] != "closed" or gate["current_blockers"] != list(_CURRENT_BLOCKERS):
        raise ReferenceValidationArtifactBindingError("validation artifact authorization gate drifted")
    return ReferenceValidationArtifactAuthorizationDecision(
        binding_sha256=document["binding_sha256"],
        validation_execution_authorized=False,
        parameter_fitting_proposal_authorized=False,
        parameter_fitting_authorized=False,
        blockers=_CURRENT_BLOCKERS,
    )


def require_reference_validation_execution_authorized(
    binding_document: Mapping[str, Any] | None = None,
) -> None:
    decision = reference_validation_artifact_authorization_decision(binding_document)
    raise ReferenceValidationArtifactBindingError(
        "CPU reference validation execution remains unauthorized: " + ", ".join(decision.blockers)
    )


def reference_validation_artifact_binding_json_bytes() -> bytes:
    return _canonical_bytes(reference_validation_artifact_binding_document()) + b"\n"


def write_reference_validation_artifact_binding_json(
    path: str | os.PathLike[str],
) -> str:
    """Atomically write the exact binding with owner-only permissions."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ReferenceValidationArtifactBindingError("refusing to replace a symlink destination")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(reference_validation_artifact_binding_json_bytes())
            handle.flush()
            os.fsync(handle.fileno())
        if destination.is_symlink():
            raise ReferenceValidationArtifactBindingError("refusing to replace a symlink destination")
        os.replace(temporary, destination)
        os.chmod(destination, 0o600)
    finally:
        if temporary.exists():
            temporary.unlink()
    return FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256


__all__ = [
    "FROZEN_INDEPENDENT_ANALYTIC_ORACLE_SOURCE_SHA256",
    "FROZEN_REFERENCE_FORCEFIELD_SOURCE_SHA256",
    "FROZEN_REFERENCE_VALIDATION_ARTIFACT_BINDING_SHA256",
    "FROZEN_REFERENCE_VALIDATION_MATERIALIZER_SOURCE_SHA256",
    "REFERENCE_VALIDATION_ARTIFACT_BINDING_ID",
    "REFERENCE_VALIDATION_ARTIFACT_BINDING_SCHEMA_ID",
    "REFERENCE_VALIDATION_ARTIFACT_BINDING_VERSION",
    "ReferenceValidationArtifactAuthorizationDecision",
    "ReferenceValidationArtifactBinding",
    "ReferenceValidationArtifactBindingError",
    "frozen_reference_validation_artifact_binding",
    "independent_analytic_oracle_source_sha256",
    "reference_forcefield_source_sha256",
    "reference_validation_artifact_authorization_decision",
    "reference_validation_artifact_binding_document",
    "reference_validation_artifact_binding_json_bytes",
    "require_reference_validation_artifact_binding_document",
    "require_reference_validation_execution_authorized",
    "write_reference_validation_artifact_binding_json",
]
