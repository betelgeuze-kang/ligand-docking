"""API-side authenticated, server-artifact-only Engine V2 shadow evidence."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Callable

try:
    from fastapi import APIRouter, Request
except ModuleNotFoundError:  # base wheel intentionally has no API dependency
    APIRouter = None
    Request = object


ENGINE_V2_SHADOW_SERVER_ARTIFACT_SCHEMA_ID = (
    "betelgeuze.api_engine_v2_shadow_server_artifact/1.0.0"
)
_ENGINE_V2_SHADOW_SERVER_ARTIFACT_FIELDS = frozenset(
    {
        "schema_id",
        "access_scope",
        "outer_result_manifest_signature_required",
        "stage0_admission_receipt",
        "fresh_128_verification_receipt",
        "validated_runner_execution_evidence",
        "verified_docking_pipeline_execution",
        "profile_document",
        "recorded_evidence_document",
        "scientific_inputs_derived_from_verified_execution",
        "artifact_creation_execution_performed",
        "primary_rank_mutation_performed",
        "customer_pose_emitted",
        "production_claim_granted",
        "customer_execution_enabled",
        "claim_safe",
        "receipt_sha256",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    ).hexdigest()


def _detached_json_mapping(value: object, *, label: str) -> dict[str, object]:
    """Return a detached canonical JSON mapping with no runtime aliases."""

    try:
        serializable = dict(value) if isinstance(value, Mapping) else value
        detached = json.loads(
            json.dumps(
                serializable,
                allow_nan=False,
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not canonical JSON") from exc
    if not isinstance(detached, dict):
        raise ValueError(f"{label} must be a mapping")
    return detached


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON keys are forbidden")
        result[key] = value
    return result


def _identity_authorizers() -> tuple[
    Callable[[object], object],
    Callable[[object], None],
]:
    """Load the product API auth boundary only when the adapter is invoked."""

    from api.request_identity import request_identity, require_admin

    return request_identity, require_admin


def _product_projector() -> Callable[..., dict[str, object]]:
    """Load the scientific adapter only after signed evidence is available."""

    from betelgeuze_product.engine_v2_shadow import (
        project_operator_engine_v2_shadow,
    )

    return project_operator_engine_v2_shadow


def _persisted_product_projector() -> Callable[..., dict[str, object]]:
    """Load the private document projector used only after pure validation."""

    from betelgeuze_product.engine_v2_shadow import (
        _project_operator_engine_v2_shadow_documents,
    )

    return _project_operator_engine_v2_shadow_documents


def get_engine_v2_operator_shadow(
    request: "Request",
    *,
    stage0_admission: object,
    verified_fresh_run: object,
    verified_execution: object,
) -> dict[str, object]:
    """Authenticate and project one live factory-verified execution."""

    request_identity, require_admin = _identity_authorizers()
    identity = request_identity(request)
    require_admin(identity)
    _verified_fresh_128_document(
        verified_fresh_run,
        stage0_admission=stage0_admission,
    )
    return _product_projector()(
        identity=identity,
        stage0_admission=stage0_admission,
        verified_fresh_run=verified_fresh_run,
        verified_execution=verified_execution,
    )


def _standard_recorded_execution_evidence(
    verified_execution: object,
) -> dict[str, object]:
    """Extract the canonical recorder document from a typed execution only."""

    from betelgeuze_engine_v2.pipeline import VerifiedDockingPipelineExecution

    if type(verified_execution) is not VerifiedDockingPipelineExecution:
        raise TypeError("factory-created VerifiedDockingPipelineExecution is required")
    verified_execution.assert_integrity()
    recorded = verified_execution.recorded_evidence
    if not isinstance(recorded, Mapping):
        raise ValueError("verified execution recorder evidence is invalid")
    standard = recorded.get("verified_execution_evidence")
    if not isinstance(standard, Mapping):
        raise ValueError(
            "verified execution lacks standard recorded scientific evidence"
        )
    return _detached_json_mapping(
        standard,
        label="verified execution recorded evidence",
    )


def _verified_stage0_document(stage0_admission: object) -> dict[str, object]:
    from betelgeuze_engine_v2.benchmark.blind_stage0 import VerifiedStage0Admission

    if type(stage0_admission) is not VerifiedStage0Admission:
        raise TypeError("factory-created VerifiedStage0Admission is required")
    receipt_sha256 = stage0_admission.receipt_sha256
    document = stage0_admission.to_dict()
    if document.get("receipt_sha256") != receipt_sha256:
        raise ValueError("verified Stage 0 admission receipt changed")
    return document


def _verified_fresh_128_document(
    verified_fresh_run: object,
    *,
    stage0_admission: object,
) -> dict[str, object]:
    """Require the exact completed Fresh-128 authority before shadow activation."""

    from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
        require_fresh_run_product_shadow_activation,
    )

    return require_fresh_run_product_shadow_activation(
        verified_fresh_run,
        stage0_admission=stage0_admission,
    )


def build_engine_v2_shadow_server_artifact(
    *,
    job_id: str,
    verified_execution: object,
    stage0_admission: object,
    verified_fresh_run: object,
) -> dict[str, object]:
    """Build an immutable server artifact from a typed execution authority.

    The caller supplies no scientific fragments.  The returned artifact still
    requires the normal signed completed-result manifest before the GET route
    will serve it.
    """

    from api.validated_runner_execution_evidence import (
        engine_v2_shadow_execution_evidence,
    )
    from betelgeuze_engine_v2.pipeline import (
        VerifiedDockingPipelineExecution,
        validate_verified_docking_pipeline_execution_document,
    )

    if type(verified_execution) is not VerifiedDockingPipelineExecution:
        raise TypeError("factory-created VerifiedDockingPipelineExecution is required")
    verified_execution.assert_integrity()
    profile = _detached_json_mapping(
        verified_execution.profile_document,
        label="verified execution profile",
    )
    execution = _detached_json_mapping(
        verified_execution.execution_receipt,
        label="verified execution receipt",
    )
    recorded = _standard_recorded_execution_evidence(verified_execution)
    execution = validate_verified_docking_pipeline_execution_document(
        execution,
        profile,
        recorded,
    )
    admission = _verified_stage0_document(stage0_admission)
    fresh_128 = _verified_fresh_128_document(
        verified_fresh_run,
        stage0_admission=stage0_admission,
    )
    if admission.get("docking_pipeline_profile_id") != profile.get(
        "profile_id"
    ) or admission.get("docking_pipeline_profile_sha256") != profile.get(
        "profile_sha256"
    ):
        raise ValueError("Stage 0 admission and pipeline profile are cross-wired")
    runner_evidence = engine_v2_shadow_execution_evidence(job_id)
    artifact: dict[str, object] = {
        "schema_id": ENGINE_V2_SHADOW_SERVER_ARTIFACT_SCHEMA_ID,
        "access_scope": "server_owned_authenticated_operator_read_only",
        "outer_result_manifest_signature_required": True,
        "stage0_admission_receipt": admission,
        "fresh_128_verification_receipt": fresh_128,
        "validated_runner_execution_evidence": runner_evidence,
        "verified_docking_pipeline_execution": execution,
        "profile_document": profile,
        "recorded_evidence_document": recorded,
        "scientific_inputs_derived_from_verified_execution": True,
        "artifact_creation_execution_performed": False,
        "primary_rank_mutation_performed": False,
        "customer_pose_emitted": False,
        "production_claim_granted": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    artifact["receipt_sha256"] = _canonical_sha256(artifact)
    return artifact


def _validate_and_project_engine_v2_shadow_server_artifact(
    *,
    artifact: object,
    receipt_sha256: str,
    job_id: str,
    identity: object,
    stage0_admission: object,
    verified_fresh_run: object,
    signed_runner_execution_evidence: object,
) -> dict[str, object]:
    """Pure persisted-artifact gate used after outer manifest verification."""

    from api.validated_runner_execution_evidence import (
        require_engine_v2_shadow_execution_evidence,
    )
    from betelgeuze_engine_v2.pipeline import (
        validate_verified_docking_pipeline_execution_document,
    )

    if (
        not isinstance(artifact, Mapping)
        or set(artifact) != _ENGINE_V2_SHADOW_SERVER_ARTIFACT_FIELDS
    ):
        raise ValueError("Engine V2 shadow artifact fields are invalid")
    claimed = artifact.get("receipt_sha256")
    unsigned = dict(artifact)
    unsigned.pop("receipt_sha256")
    if (
        artifact.get("schema_id") != ENGINE_V2_SHADOW_SERVER_ARTIFACT_SCHEMA_ID
        or not isinstance(claimed, str)
        or not hmac.compare_digest(claimed, receipt_sha256)
        or not hmac.compare_digest(_canonical_sha256(unsigned), receipt_sha256)
    ):
        raise ValueError("Engine V2 shadow artifact receipt is invalid")
    signed_execution = require_engine_v2_shadow_execution_evidence(
        signed_runner_execution_evidence
    )
    if not job_id or signed_execution["docking_job_id"] != job_id:
        raise ValueError(
            "Engine V2 shadow runner evidence is cross-wired to the signed job"
        )
    if artifact["validated_runner_execution_evidence"] != signed_execution:
        raise ValueError(
            "Engine V2 shadow artifact is cross-wired to runner execution evidence"
        )
    if artifact["stage0_admission_receipt"] != _verified_stage0_document(
        stage0_admission
    ):
        raise ValueError("Engine V2 Stage 0 admission receipt is cross-wired")
    if artifact["fresh_128_verification_receipt"] != _verified_fresh_128_document(
        verified_fresh_run,
        stage0_admission=stage0_admission,
    ):
        raise ValueError("Engine V2 Fresh-128 verification receipt is cross-wired")
    if (
        artifact.get("access_scope") != "server_owned_authenticated_operator_read_only"
        or artifact.get("outer_result_manifest_signature_required") is not True
        or artifact.get("scientific_inputs_derived_from_verified_execution") is not True
        or artifact.get("artifact_creation_execution_performed") is not False
        or artifact.get("primary_rank_mutation_performed") is not False
        or artifact.get("customer_pose_emitted") is not False
        or artifact.get("production_claim_granted") is not False
        or artifact.get("customer_execution_enabled") is not False
        or artifact.get("claim_safe") is not False
    ):
        raise ValueError("Engine V2 shadow artifact permissions are invalid")
    profile_document = artifact["profile_document"]
    recorded_document = artifact["recorded_evidence_document"]
    if not isinstance(profile_document, Mapping) or not isinstance(
        recorded_document, Mapping
    ):
        raise ValueError("Engine V2 persisted execution documents are invalid")
    execution_document = validate_verified_docking_pipeline_execution_document(
        artifact["verified_docking_pipeline_execution"],
        profile_document,
        recorded_document,
    )
    candidates = recorded_document.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Engine V2 candidate evidence is invalid")
    if (
        execution_document.get("candidate_count") != len(candidates)
        or execution_document.get("profile_document") != profile_document
    ):
        raise ValueError("Engine V2 persisted execution is cross-wired")
    return _persisted_product_projector()(
        identity=identity,
        stage0_admission=stage0_admission,
        profile_document=profile_document,
        candidates=candidates,
    )


def _verified_stage0_admission() -> object:
    """Reverify the configured Stage 0 trust root for every shadow read."""

    from api.config import settings
    from betelgeuze_engine_v2.benchmark.blind_stage0 import (
        Stage0AdmissionError,
        verify_stage0_admission,
    )

    policy_value = str(settings.engine_v2_stage0_policy_path or "").strip()
    gnina_value = str(settings.engine_v2_stage0_gnina_path or "").strip()
    output_value = str(settings.engine_v2_stage0_output_root or "").strip()
    if not policy_value or not gnina_value or not output_value:
        raise Stage0AdmissionError(("product_shadow_stage0_authority_unconfigured",))
    return verify_stage0_admission(
        Path(policy_value),
        repo_root=Path(__file__).resolve().parents[1],
        gnina_path=Path(gnina_value),
        output_root=Path(output_value),
    )


def _verified_fresh_128_run(stage0_admission: object) -> object:
    """Reverify the retained Fresh-128 root for every shadow read."""

    from api.config import settings
    from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
        FreshRunVerificationError,
        verify_fresh_run_root,
    )

    output_value = str(settings.engine_v2_fresh_output_root or "").strip()
    if not output_value:
        raise FreshRunVerificationError(
            "product shadow Fresh-128 authority is unconfigured"
        )
    repo_root = Path(__file__).resolve().parents[1]
    return verify_fresh_run_root(
        Path(output_value),
        repo_root=repo_root,
        source_repo_root=repo_root,
        verified_stage0_receipt=stage0_admission,
    )


def _project_server_owned_shadow_artifact(
    request: "Request",
    *,
    job_id: str,
    receipt_sha256: str,
) -> dict[str, object]:
    """Load one signed completed job result and project its embedded shadow receipt."""

    from fastapi import HTTPException

    from api.artifact_access import (
        read_confined_json_object,
        verify_completed_result_artifacts,
    )
    from api.config import settings
    from api.job_store import get_configured_job_store
    from api.request_identity import request_identity, require_admin
    from api.simulation_endpoint_access import get_simulation_job_for_identity
    from api.worker import job_results_dir, job_status_path

    if _SHA256_RE.fullmatch(receipt_sha256) is None:
        raise HTTPException(
            status_code=404, detail="Engine V2 shadow receipt not found"
        )
    identity = request_identity(request)
    if identity.authenticated is not True:
        raise HTTPException(
            status_code=401, detail="authenticated product identity required"
        )
    require_admin(identity)
    store = get_configured_job_store(settings.api_job_store_path)
    record = get_simulation_job_for_identity(
        store,
        identity,
        job_id,
        resource="Engine V2 shadow receipt",
    )
    status_path = str(record.get("published_status_path") or job_status_path(job_id))
    result_root = job_results_dir(job_id)
    status = read_confined_json_object(
        result_root,
        status_path,
        label="Engine V2 shadow status",
        missing_ok=True,
    )
    if status is None:
        raise HTTPException(
            status_code=404, detail="Engine V2 shadow receipt not found"
        )
    verified = verify_completed_result_artifacts(
        job_id=job_id,
        record=record,
        status_data=status,
        result_root=result_root,
        signing_key=settings.api_result_manifest_signing_key,
        expected_key_id=settings.api_result_manifest_key_id,
        snapshot_result=True,
    )
    try:
        if (
            verified.artifact_type != "json"
            or verified.media_type != "application/json"
        ):
            raise HTTPException(
                status_code=404,
                detail="Engine V2 shadow receipt not found",
            )
        if verified.result_snapshot is None:
            raise HTTPException(
                status_code=409, detail="verified result snapshot missing"
            )
        result_document = json.load(
            verified.result_snapshot,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=409, detail="Engine V2 shadow artifact invalid"
        ) from exc
    finally:
        verified.close()
    if not isinstance(result_document, dict):
        raise HTTPException(status_code=409, detail="Engine V2 shadow artifact invalid")
    artifact = result_document.get("engine_v2_shadow_server_artifact")
    if not isinstance(artifact, dict):
        raise HTTPException(
            status_code=404, detail="Engine V2 shadow receipt not found"
        )
    try:
        stage0_admission = _verified_stage0_admission()
        verified_fresh_run = _verified_fresh_128_run(stage0_admission)
        return _validate_and_project_engine_v2_shadow_server_artifact(
            artifact=artifact,
            receipt_sha256=receipt_sha256,
            job_id=job_id,
            identity=identity,
            stage0_admission=stage0_admission,
            verified_fresh_run=verified_fresh_run,
            signed_runner_execution_evidence=(
                verified.validated_runner_execution_evidence
            ),
        )
    except (TypeError, ValueError, PermissionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=409, detail="Engine V2 shadow evidence invalid"
        ) from exc


if APIRouter is not None:
    router = APIRouter(
        prefix="/product/engine-v2/shadow",
        tags=["product-engine-v2-shadow"],
    )

    @router.get("/{job_id}/{receipt_sha256}")
    def get_server_engine_v2_operator_shadow(
        job_id: str,
        receipt_sha256: str,
        request: Request,
    ) -> dict[str, object]:
        return _project_server_owned_shadow_artifact(
            request,
            job_id=job_id,
            receipt_sha256=receipt_sha256,
        )
else:
    router = None


__all__ = [
    "ENGINE_V2_SHADOW_SERVER_ARTIFACT_SCHEMA_ID",
    "build_engine_v2_shadow_server_artifact",
    "get_engine_v2_operator_shadow",
    "router",
]
