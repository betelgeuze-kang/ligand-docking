from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.claim_boundary import (
    CLAIM_SCOPE_PRODUCT_LIGAND,
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    GENERAL_MD_ACCURACY_CLAIM,
    PRODUCT_CLAIM_BOUNDARY_TEXT,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    general_md_accuracy_promotion_allowed,
    validate_manifest_claim_fields,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_text(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload if isinstance(payload, dict) else {"value": payload})).hexdigest()


def _sha256_file(path_like: str | Path) -> str:
    path = Path(path_like)
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_result_manifest(
    *,
    job_id: str,
    request: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
    signing_key: str,
    key_id: str,
    claim_scope: str = CLAIM_SCOPE_PRODUCT_LIGAND,
    fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    topology_fidelity: str | None = None,
    accuracy_claim_grade: str = "restricted-local-delivery",
) -> dict[str, Any]:
    resolved_fidelity = str(topology_fidelity or fidelity or TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE)
    resolved_scope = str(claim_scope or CLAIM_SCOPE_PRODUCT_LIGAND)
    if accuracy_claim_grade == GENERAL_MD_ACCURACY_CLAIM and not general_md_accuracy_promotion_allowed(
        fidelity=resolved_fidelity,
        claim_scope=resolved_scope,
    ):
        raise ValueError(
            f"accuracy_claim_grade '{GENERAL_MD_ACCURACY_CLAIM}' is forbidden for fidelity={resolved_fidelity}"
        )
    result_file_sha256 = _sha256_file(result_file) if result_file else ""
    payload: dict[str, Any] = {
        "manifest_version": "api_result_manifest_v1",
        "job_id": job_id,
        "status": status,
        "request_sha256": _sha256_text(request),
        "result_file": result_file,
        "result_file_sha256": result_file_sha256,
        "error": error,
        "created_at_utc": _utc_now(),
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": key_id,
        "claim_scope": resolved_scope,
        "fidelity": resolved_fidelity,
        "topology_fidelity": resolved_fidelity,
        "accuracy_claim_grade": accuracy_claim_grade,
        "claim_boundary": (
            "API result manifest only; signs request/status/result-file provenance. It does not claim "
            "scientific validity, run simulations, emit fake results, or promote model outputs. "
            f"{PRODUCT_CLAIM_BOUNDARY_TEXT}"
        ),
    }
    validate_manifest_claim_fields(payload)
    signature = hmac.new(signing_key.encode("utf-8"), _canonical_json(payload), hashlib.sha256).hexdigest()
    payload["signature"] = signature
    return payload


def verify_result_manifest(manifest: dict[str, Any], *, signing_key: str) -> bool:
    observed = str(manifest.get("signature", "") or "")
    if not observed:
        return False
    payload = {k: v for k, v in manifest.items() if k != "signature"}
    expected = hmac.new(signing_key.encode("utf-8"), _canonical_json(payload), hashlib.sha256).hexdigest()
    return hmac.compare_digest(observed, expected)


def write_result_manifest(
    path_like: str | Path,
    *,
    job_id: str,
    request: dict[str, Any],
    status: str,
    result_file: str = "",
    error: str = "",
    signing_key: str,
    key_id: str,
    claim_scope: str = CLAIM_SCOPE_PRODUCT_LIGAND,
    fidelity: str = TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    topology_fidelity: str | None = None,
    accuracy_claim_grade: str = "restricted-local-delivery",
) -> dict[str, Any]:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = build_result_manifest(
        job_id=job_id,
        request=request,
        status=status,
        result_file=result_file,
        error=error,
        signing_key=signing_key,
        key_id=key_id,
        claim_scope=claim_scope,
        fidelity=fidelity,
        topology_fidelity=topology_fidelity,
        accuracy_claim_grade=accuracy_claim_grade,
    )
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest
