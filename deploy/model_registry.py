from __future__ import annotations

import hashlib
import hmac
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
MANIFEST_VERSION = "product_model_artifact_manifest_v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def default_version() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def require_safe_id(value: str, *, field: str) -> str:
    if not SAFE_ID_RE.fullmatch(value):
        raise ValueError(f"{field} must match {SAFE_ID_RE.pattern}")
    return value


def sha256_file(path_like: str | Path) -> str:
    path = Path(path_like)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sign_payload(payload: dict[str, Any], *, signing_key: str) -> str:
    if not signing_key:
        raise ValueError("MODEL_REGISTRY_SIGNING_KEY is required")
    return hmac.new(signing_key.encode("utf-8"), canonical_json(payload), hashlib.sha256).hexdigest()


def verify_signed_payload(payload: dict[str, Any], *, signing_key: str) -> bool:
    observed = str(payload.get("signature", "") or "")
    if not observed:
        return False
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    expected = sign_payload(unsigned, signing_key=signing_key)
    return hmac.compare_digest(observed, expected)


def model_root(registry_dir: str | Path, model_name: str) -> Path:
    return Path(registry_dir) / "models" / require_safe_id(model_name, field="model_name")


def version_root(registry_dir: str | Path, model_name: str, version: str) -> Path:
    return model_root(registry_dir, model_name) / "versions" / require_safe_id(version, field="version")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def build_manifest(
    *,
    model_name: str,
    version: str,
    artifact_path: Path,
    source_path: Path,
    signing_key: str,
    key_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_sha256 = sha256_file(artifact_path)
    payload: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "model_name": model_name,
        "version": version,
        "artifact_file": artifact_path.name,
        "artifact_size_bytes": artifact_path.stat().st_size,
        "artifact_sha256": artifact_sha256,
        "source_file_name": source_path.name,
        "created_at_utc": utc_now(),
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": key_id,
        "metadata": dict(metadata or {}),
        "claim_boundary": (
            "Product model artifact manifest only; signs artifact provenance and registry activation state. "
            "It does not claim scientific validity, approve production promotion, or bypass model evaluation gates."
        ),
    }
    payload["signature"] = sign_payload(payload, signing_key=signing_key)
    return payload


def publish_model_artifact(
    *,
    model_path: str | Path,
    model_name: str,
    version: str,
    registry_dir: str | Path,
    signing_key: str,
    key_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model_name = require_safe_id(model_name, field="model_name")
    version = require_safe_id(version, field="version")
    source = Path(model_path)
    if not source.is_file():
        raise FileNotFoundError(f"model artifact not found: {source}")

    root = version_root(registry_dir, model_name, version)
    artifact_dir = root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / source.name
    shutil.copy2(source, artifact_path)

    manifest = build_manifest(
        model_name=model_name,
        version=version,
        artifact_path=artifact_path,
        source_path=source,
        signing_key=signing_key,
        key_id=key_id,
        metadata=metadata,
    )
    write_json(root / "manifest.json", manifest)
    activate_model_version(
        model_name=model_name,
        version=version,
        registry_dir=registry_dir,
        signing_key=signing_key,
        key_id=key_id,
        reason="publish",
    )
    return manifest


def load_manifest(
    *,
    model_name: str,
    version: str,
    registry_dir: str | Path,
    signing_key: str,
) -> dict[str, Any]:
    manifest_path = version_root(registry_dir, model_name, version) / "manifest.json"
    manifest = load_json(manifest_path)
    if not verify_signed_payload(manifest, signing_key=signing_key):
        raise ValueError(f"model artifact manifest signature verification failed: {manifest_path}")
    artifact = manifest_path.parent / "artifacts" / str(manifest.get("artifact_file", ""))
    if not artifact.is_file():
        raise FileNotFoundError(f"registered artifact missing: {artifact}")
    if sha256_file(artifact) != str(manifest.get("artifact_sha256", "")):
        raise ValueError(f"registered artifact sha256 mismatch: {artifact}")
    return manifest


def _index_path(registry_dir: str | Path, model_name: str) -> Path:
    return model_root(registry_dir, model_name) / "index.json"


def load_index(*, registry_dir: str | Path, model_name: str) -> dict[str, Any]:
    return load_json(_index_path(registry_dir, model_name))


def load_verified_index(*, registry_dir: str | Path, model_name: str, signing_key: str) -> dict[str, Any]:
    index_path = _index_path(registry_dir, model_name)
    index = load_json(index_path)
    if not index:
        return {}
    if not verify_signed_payload(index, signing_key=signing_key):
        raise ValueError(f"model registry index signature verification failed: {index_path}")
    return index


def write_index(*, registry_dir: str | Path, model_name: str, payload: dict[str, Any]) -> None:
    write_json(_index_path(registry_dir, model_name), payload)


def activate_model_version(
    *,
    model_name: str,
    version: str,
    registry_dir: str | Path,
    signing_key: str,
    key_id: str,
    reason: str,
) -> dict[str, Any]:
    manifest = load_manifest(model_name=model_name, version=version, registry_dir=registry_dir, signing_key=signing_key)
    index = load_verified_index(registry_dir=registry_dir, model_name=model_name, signing_key=signing_key)
    previous_version = str(index.get("current_version", "") or "")
    versions = list(dict.fromkeys([*list(index.get("versions", []) or []), version]))
    unsigned: dict[str, Any] = {
        "index_version": "product_model_registry_index_v1",
        "model_name": model_name,
        "current_version": version,
        "previous_version": previous_version,
        "versions": versions,
        "current_artifact_sha256": manifest["artifact_sha256"],
        "updated_at_utc": utc_now(),
        "activation_reason": reason,
        "signature_algorithm": "hmac-sha256",
        "signature_key_id": key_id,
    }
    unsigned["signature"] = sign_payload(unsigned, signing_key=signing_key)
    write_index(registry_dir=registry_dir, model_name=model_name, payload=unsigned)
    return unsigned


def resolve_version(*, registry_dir: str | Path, model_name: str, version_or_stage: str) -> str:
    if version_or_stage.lower() in {"current", "latest", "production"}:
        raise ValueError("resolve_version requires signing_key for current/latest/Production aliases")
    return require_safe_id(version_or_stage, field="version_or_stage")


def resolve_version_verified(*, registry_dir: str | Path, model_name: str, version_or_stage: str, signing_key: str) -> str:
    if version_or_stage.lower() in {"current", "latest", "production"}:
        index = load_verified_index(registry_dir=registry_dir, model_name=model_name, signing_key=signing_key)
        version = str(index.get("current_version", "") or "")
        if not version:
            raise ValueError(f"no current version registered for model: {model_name}")
        return version
    return require_safe_id(version_or_stage, field="version_or_stage")


def download_model_artifact(
    *,
    model_name: str,
    version_or_stage: str,
    registry_dir: str | Path,
    download_path: str | Path,
    signing_key: str,
) -> dict[str, Any]:
    version = resolve_version_verified(
        registry_dir=registry_dir,
        model_name=model_name,
        version_or_stage=version_or_stage,
        signing_key=signing_key,
    )
    manifest = load_manifest(model_name=model_name, version=version, registry_dir=registry_dir, signing_key=signing_key)
    artifact = version_root(registry_dir, model_name, version) / "artifacts" / str(manifest["artifact_file"])
    dest_dir = Path(download_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_artifact = dest_dir / artifact.name
    shutil.copy2(artifact, dest_artifact)
    write_json(dest_dir / f"{model_name}.{version}.manifest.json", manifest)
    return {
        "model_name": model_name,
        "version": version,
        "artifact_path": str(dest_artifact),
        "artifact_sha256": manifest["artifact_sha256"],
        "manifest_path": str(dest_dir / f"{model_name}.{version}.manifest.json"),
        "verified": True,
    }


def rollback_model_version(
    *,
    model_name: str,
    target_version: str,
    registry_dir: str | Path,
    signing_key: str,
    key_id: str,
) -> dict[str, Any]:
    if target_version == "previous":
        index = load_verified_index(registry_dir=registry_dir, model_name=model_name, signing_key=signing_key)
        target_version = str(index.get("previous_version", "") or "")
        if not target_version:
            raise ValueError(f"no previous version available for model: {model_name}")
    return activate_model_version(
        model_name=model_name,
        version=target_version,
        registry_dir=registry_dir,
        signing_key=signing_key,
        key_id=key_id,
        reason="rollback",
    )
