"""Authenticated, read-only product adapter for Engine V2 shadow evidence.

The public adapter accepts one factory-created :class:`DockingPipeline`
execution authority.  Callers cannot supply a profile, source binding, score
terms, candidate list, or any other scientific fragment independently.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json

from betelgeuze_engine_v2.pipeline import (
    VerifiedDockingPipelineExecution,
)
from betelgeuze_engine_v2.product_shadow import (
    ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID,
    project_engine_v2_product_shadow_evidence,
    validate_engine_v2_product_shadow_evidence,
)


ENGINE_V2_PRODUCT_SHADOW_ADAPTER_SCHEMA_ID = (
    "betelgeuze.product_engine_v2_operator_shadow_adapter/1.0.0"
)
ENGINE_V2_PRODUCT_SHADOW_VERIFIED_SOURCE_SCHEMA_ID = (
    "betelgeuze.product_engine_v2_shadow_verified_pipeline_source/1.0.0"
)


class EngineV2ProductShadowAccessError(PermissionError):
    """The caller or source evidence cannot enter the operator shadow lane."""


def _canonical_sha256(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise EngineV2ProductShadowAccessError(
            "operator shadow adapter evidence is not canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _operator_identity(identity: object) -> tuple[str, str]:
    try:
        from api.request_identity import ProductRequestIdentity
    except (ImportError, ModuleNotFoundError) as exc:
        raise EngineV2ProductShadowAccessError(
            "product identity authority is unavailable"
        ) from exc
    if (
        type(identity) is not ProductRequestIdentity
        or identity.authenticated is not True
        or identity.is_admin is not True
    ):
        raise EngineV2ProductShadowAccessError(
            "authenticated administrator identity is required"
        )
    principal = str(identity.principal or "").strip()
    tenant_id = str(identity.tenant_id or "").strip()
    if not principal or not tenant_id:
        raise EngineV2ProductShadowAccessError("operator identity is incomplete")
    return principal, tenant_id


def _stage0_receipt_sha256(stage0_admission: object) -> str:
    """Read the factory authority; the scientific projector fully verifies it."""

    try:
        receipt = getattr(stage0_admission, "receipt_sha256")
        document = getattr(stage0_admission, "to_dict")()
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise EngineV2ProductShadowAccessError(
            "verified Stage 0 admission authority is required"
        ) from exc
    if (
        not isinstance(document, Mapping)
        or document.get("receipt_sha256") != receipt
        or not isinstance(receipt, str)
        or len(receipt) != 64
    ):
        raise EngineV2ProductShadowAccessError(
            "verified Stage 0 admission authority is invalid"
        )
    return receipt


def _build_shadow_projection_documents(
    *,
    profile_document: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    stage0_admission_receipt_sha256: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Derive legacy projection receipts from one already-verified execution.

    This helper is private because the profile and candidate arguments are not
    an accepted product boundary.  The direct boundary obtains them only from
    ``VerifiedDockingPipelineExecution`` and the persisted boundary obtains
    them only after the pipeline's pure document validator succeeds.
    """

    profile_id = profile_document.get("profile_id")
    profile_sha256 = profile_document.get("profile_sha256")
    normalized_candidates = [dict(candidate) for candidate in candidates]
    candidate_sha256s = [
        _canonical_sha256(candidate) for candidate in normalized_candidates
    ]
    upstream: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_UPSTREAM_SCHEMA_ID,
        "pipeline_profile_id": profile_id,
        "pipeline_profile_sha256": profile_sha256,
        "stage0_admission_receipt_sha256": stage0_admission_receipt_sha256,
        "candidate_count": len(normalized_candidates),
        "candidate_source_sha256s": candidate_sha256s,
        "execution_completed": True,
        "projection_only": False,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    upstream["receipt_sha256"] = _canonical_sha256(upstream)
    source: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_VERIFIED_SOURCE_SCHEMA_ID,
        "profile_id": profile_id,
        "profile_sha256": profile_sha256,
        "stage0_admission_receipt_sha256": stage0_admission_receipt_sha256,
        "candidate_count": len(normalized_candidates),
        "candidate_source_sha256s": candidate_sha256s,
        "upstream_evidence_schema_id": upstream["schema_id"],
        "upstream_evidence_receipt_sha256": upstream["receipt_sha256"],
        "execution_already_completed": True,
        "projection_only": True,
        "scientifically_validated": False,
        "product_qualified": False,
        "claim_safe": False,
    }
    source["receipt_sha256"] = _canonical_sha256(source)
    return upstream, source


def _project_operator_engine_v2_shadow_documents(
    *,
    identity: object,
    stage0_admission: object,
    profile_document: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Internal persisted-document projection after the pure validator."""

    principal, tenant_id = _operator_identity(identity)
    upstream, source = _build_shadow_projection_documents(
        profile_document=profile_document,
        candidates=candidates,
        stage0_admission_receipt_sha256=_stage0_receipt_sha256(stage0_admission),
    )
    evidence = project_engine_v2_product_shadow_evidence(
        stage0_admission=stage0_admission,
        profile_document=profile_document,
        upstream_evidence_document=upstream,
        source_evidence_document=source,
        candidates=candidates,
    )
    validate_engine_v2_product_shadow_evidence(
        evidence,
        stage0_admission=stage0_admission,
    )
    projection: dict[str, object] = {
        "schema_id": ENGINE_V2_PRODUCT_SHADOW_ADAPTER_SCHEMA_ID,
        "access_scope": "authenticated_operator_read_only",
        "operator_principal_sha256": hashlib.sha256(
            principal.encode("utf-8")
        ).hexdigest(),
        "tenant_id_sha256": hashlib.sha256(tenant_id.encode("utf-8")).hexdigest(),
        "engine_v2_shadow_evidence": evidence,
        "shared_docking_pipeline_profile_verified": True,
        "execution_performed": False,
        "primary_rank_mutation_performed": False,
        "customer_pose_emitted": False,
        "production_claim_granted": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    projection["receipt_sha256"] = _canonical_sha256(projection)
    return projection


def project_operator_engine_v2_shadow(
    *,
    identity: object,
    stage0_admission: object,
    verified_fresh_run: object,
    verified_execution: VerifiedDockingPipelineExecution,
) -> dict[str, object]:
    """Project one live, factory-verified execution for an operator only."""

    from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
        require_fresh_run_product_shadow_activation,
    )

    try:
        require_fresh_run_product_shadow_activation(
            verified_fresh_run,
            stage0_admission=stage0_admission,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise EngineV2ProductShadowAccessError(
            "verified Fresh-128 activation authority is required"
        ) from exc
    if type(verified_execution) is not VerifiedDockingPipelineExecution:
        raise EngineV2ProductShadowAccessError(
            "factory-created VerifiedDockingPipelineExecution is required"
        )
    try:
        verified_execution.assert_integrity()
        profile = dict(verified_execution.profile_document)
        candidates = [dict(row) for row in verified_execution.candidate_evidence]
        # These accessors force validation of exact source/result bindings even
        # though the read-only projection intentionally redacts both payloads.
        dict(verified_execution.source_binding)
        dict(verified_execution.result_binding)
    except (RuntimeError, TypeError, ValueError) as exc:
        raise EngineV2ProductShadowAccessError(
            "verified DockingPipeline execution authority is invalid"
        ) from exc
    return _project_operator_engine_v2_shadow_documents(
        identity=identity,
        stage0_admission=stage0_admission,
        profile_document=profile,
        candidates=candidates,
    )


__all__ = [
    "ENGINE_V2_PRODUCT_SHADOW_ADAPTER_SCHEMA_ID",
    "ENGINE_V2_PRODUCT_SHADOW_VERIFIED_SOURCE_SCHEMA_ID",
    "EngineV2ProductShadowAccessError",
    "project_operator_engine_v2_shadow",
]
