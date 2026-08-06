#!/usr/bin/env python3
"""Verify release-qualification evidence without authorizing a release."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


POLICY_SCHEMA_ID = "betelgeuze.product_release_qualification_policy/1.0.0"
EVIDENCE_SCHEMA_ID = "betelgeuze.product_release_qualification_evidence/1.0.0"
EXPECTED_POLICY_SHA256 = "e18e20bc218f6fcf3cbe30b87df5b2afcab354d8e0915354436b501bbb5db7e8"
TEMPLATE_STATUS = "unqualified_template"
COMPLETE_STATUS = "qualification_evidence_complete_not_authorized"
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024 * 1024
SBOM_COMPONENTS = ("source", "wheel", "native_extension", "container")
AUTHORITY_KEYS = (
    "deployment_authorized",
    "gpu_parity_claim_authorized",
    "product_release_authorized",
    "registry_push_authorized",
    "scientific_claim_authorized",
)
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProductReleaseQualificationError(ValueError):
    """Raised when release qualification evidence fails closed."""


@dataclass(frozen=True)
class ReleaseQualificationResult:
    technical_evidence_complete: bool
    release_qualified: bool
    blockers: tuple[str, ...]
    evidence_sha256: str


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise ProductReleaseQualificationError(
            "qualification evidence is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProductReleaseQualificationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProductReleaseQualificationError(f"{name} must be an object")
    return value


def _sequence(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProductReleaseQualificationError(f"{name} must be an array")
    return value


def _verify_self_hash(
    value: Mapping[str, Any],
    *,
    field: str,
    name: str,
) -> str:
    observed = _digest(value.get(field), name=f"{name} {field}")
    projection = dict(value)
    projection.pop(field, None)
    if observed != _sha256(projection):
        raise ProductReleaseQualificationError(f"{name} self-hash is invalid")
    return observed


def load_json(path: Path, *, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductReleaseQualificationError(
            f"{name} is not readable JSON"
        ) from exc
    return _mapping(payload, name=name)


def verify_policy(policy: Mapping[str, Any]) -> str:
    expected = {
        "authority",
        "base_image",
        "hardware",
        "license",
        "policy_sha256",
        "provenance",
        "python_dependencies",
        "rollback",
        "runtime",
        "sbom",
        "schema_id",
        "status",
        "vulnerability",
    }
    if set(policy) != expected:
        raise ProductReleaseQualificationError("release policy key set is invalid")
    if (
        policy.get("schema_id") != POLICY_SCHEMA_ID
        or policy.get("status") != "contract_only_release_unqualified"
    ):
        raise ProductReleaseQualificationError("release policy identity is invalid")
    identity = _verify_self_hash(
        policy,
        field="policy_sha256",
        name="release policy",
    )
    if identity != EXPECTED_POLICY_SHA256:
        raise ProductReleaseQualificationError("release policy identity drifted")
    authority = _mapping(policy.get("authority"), name="release authority")
    if set(authority) != set(AUTHORITY_KEYS) or any(
        authority.get(key) is not False for key in AUTHORITY_KEYS
    ):
        raise ProductReleaseQualificationError(
            "release policy authority escalation detected"
        )
    exact_rows = {
        "base_image": {
            "approved_inventory_required": True,
            "digest_required": True,
            "mutable_tag_only_for_development": True,
        },
        "python_dependencies": {
            "offline_wheelhouse_required": True,
            "package_origin_required": True,
            "require_hashes": True,
            "wheel_record_required": True,
        },
        "sbom": {
            "allowed_formats": ["spdx-2.3", "cyclonedx-1.6"],
            "required_components": list(SBOM_COMPONENTS),
        },
        "vulnerability": {
            "blocked_severities": ["critical", "high"],
            "exception_max_days": 30,
            "scanner_db_identity_required": True,
        },
        "license": {
            "attribution_required": True,
            "denied_spdx_ids": ["AGPL-3.0-only", "SSPL-1.0"],
            "scan_required": True,
            "unknown_license_allowed": False,
        },
        "provenance": {
            "immutable_registry_digest_required": True,
            "signature_algorithm": "ed25519",
            "signed_attestation_required": True,
        },
        "runtime": {
            "gid": 10001,
            "privileged_allowed": False,
            "read_only_root_required": True,
            "uid": 10001,
            "writable_mounts": ["/app/logs", "/app/runs", "/data"],
        },
        "hardware": {
            "cpu_matrix_required": True,
            "operational_compatibility_only": True,
            "rocm_matrix_required": True,
            "scientific_parity_claim_allowed": False,
        },
        "rollback": {
            "incident_response_required": True,
            "previous_digest_required": True,
            "registry_retention_required": True,
            "restore_procedure_required": True,
        },
    }
    for name, expected_row in exact_rows.items():
        if policy.get(name) != expected_row:
            raise ProductReleaseQualificationError(f"{name} policy drifted")
    return identity


def _artifact_path(root: Path, relative: object, *, name: str) -> Path:
    if (
        not isinstance(relative, str)
        or not relative
        or Path(relative).is_absolute()
        or any(part in {"", ".", ".."} for part in Path(relative).parts)
    ):
        raise ProductReleaseQualificationError(f"{name} path is unsafe")
    current = root.resolve(strict=True)
    for part in Path(relative).parts:
        current = current / part
        try:
            observed = os.lstat(current)
        except OSError as exc:
            raise ProductReleaseQualificationError(
                f"{name} path is unavailable"
            ) from exc
        if stat.S_ISLNK(observed.st_mode):
            raise ProductReleaseQualificationError(
                f"{name} path contains a symlink"
            )
    if not current.is_file():
        raise ProductReleaseQualificationError(f"{name} must be a regular file")
    return current


def _file_sha256(path: Path, *, name: str) -> str:
    observed = path.stat()
    if observed.st_size <= 0 or observed.st_size > MAX_ARTIFACT_BYTES:
        raise ProductReleaseQualificationError(
            f"{name} size is outside the bounded envelope"
        )
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_file(
    value: object,
    *,
    root: Path,
    name: str,
    extra_keys: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any], Path]:
    row = _mapping(value, name=name)
    if set(row) != {"path", "sha256"} | set(extra_keys):
        raise ProductReleaseQualificationError(f"{name} key set is invalid")
    path = _artifact_path(root, row.get("path"), name=name)
    if _file_sha256(path, name=name) != _digest(
        row.get("sha256"), name=f"{name} sha256"
    ):
        raise ProductReleaseQualificationError(f"{name} hash mismatch")
    return row, path


def _verify_python_lock(value: object, *, root: Path) -> None:
    row = _mapping(value, name="Python lock")
    if set(row) != {"offline", "path", "require_hashes", "sha256"}:
        raise ProductReleaseQualificationError("Python lock key set is invalid")
    if row.get("offline") is not True or row.get("require_hashes") is not True:
        raise ProductReleaseQualificationError(
            "Python lock must be offline and use --require-hashes"
        )
    _, path = _verify_file(
        {"path": row.get("path"), "sha256": row.get("sha256")},
        root=root,
        name="Python lock",
    )
    requirement_count = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        requirement_count += 1
        if "==" not in line or "--hash=sha256:" not in line:
            raise ProductReleaseQualificationError(
                "Python lock contains an unhashed or unpinned requirement"
            )
    if requirement_count == 0:
        raise ProductReleaseQualificationError("Python lock is empty")


def _verify_wheelhouse(value: object, *, root: Path) -> None:
    row = _mapping(value, name="wheelhouse")
    expected = {
        "all_origins_verified",
        "all_records_verified",
        "entry_count",
        "manifest_path",
        "manifest_sha256",
    }
    if set(row) != expected:
        raise ProductReleaseQualificationError("wheelhouse key set is invalid")
    if (
        row.get("all_origins_verified") is not True
        or row.get("all_records_verified") is not True
        or type(row.get("entry_count")) is not int
        or row["entry_count"] <= 0
    ):
        raise ProductReleaseQualificationError("wheelhouse is not fully verified")
    _, manifest_path = _verify_file(
        {
            "path": row.get("manifest_path"),
            "sha256": row.get("manifest_sha256"),
        },
        root=root,
        name="wheelhouse manifest",
    )
    manifest = load_json(manifest_path, name="wheelhouse manifest")
    if set(manifest) != {"entries", "offline", "schema_id"}:
        raise ProductReleaseQualificationError(
            "wheelhouse manifest key set is invalid"
        )
    entries = _sequence(manifest.get("entries"), name="wheelhouse entries")
    if (
        manifest.get("schema_id") != "betelgeuze.product_wheelhouse/1.0.0"
        or manifest.get("offline") is not True
        or len(entries) != row["entry_count"]
    ):
        raise ProductReleaseQualificationError("wheelhouse manifest is invalid")
    for index, value_row in enumerate(entries):
        entry = _mapping(value_row, name=f"wheelhouse entry {index}")
        if set(entry) != {
            "license_spdx",
            "origin",
            "path",
            "record_sha256",
            "sha256",
        }:
            raise ProductReleaseQualificationError(
                "wheelhouse entry key set is invalid"
            )
        if (
            not isinstance(entry.get("origin"), str)
            or not entry["origin"].startswith("https://")
            or entry.get("license_spdx") in {"", "UNKNOWN", None}
        ):
            raise ProductReleaseQualificationError(
                "wheelhouse package origin or license is invalid"
            )
        _digest(entry.get("record_sha256"), name="wheel RECORD sha256")
        _verify_file(
            {"path": entry.get("path"), "sha256": entry.get("sha256")},
            root=root,
            name=f"wheelhouse entry {index}",
        )


def _verify_sboms(value: object, *, root: Path) -> None:
    rows = _mapping(value, name="SBOMs")
    if set(rows) != set(SBOM_COMPONENTS):
        raise ProductReleaseQualificationError("SBOM component set is invalid")
    for component in SBOM_COMPONENTS:
        row, path = _verify_file(
            rows.get(component),
            root=root,
            name=f"{component} SBOM",
            extra_keys=frozenset({"format"}),
        )
        if row.get("format") not in {"spdx-2.3", "cyclonedx-1.6"}:
            raise ProductReleaseQualificationError("SBOM format is invalid")
        document = load_json(path, name=f"{component} SBOM")
        if row["format"] == "spdx-2.3":
            if document.get("spdxVersion") != "SPDX-2.3":
                raise ProductReleaseQualificationError("SPDX version is invalid")
        elif document.get("bomFormat") != "CycloneDX" or document.get(
            "specVersion"
        ) != "1.6":
            raise ProductReleaseQualificationError("CycloneDX version is invalid")


def _parse_utc(value: object, *, name: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ProductReleaseQualificationError(f"{name} must be canonical UTC")
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ProductReleaseQualificationError(
            f"{name} must be canonical UTC"
        ) from exc
    if observed.tzinfo != timezone.utc:
        raise ProductReleaseQualificationError(f"{name} must be UTC")
    return observed


def _verify_vulnerabilities(
    value: object,
    *,
    root: Path,
    now_utc: datetime,
) -> None:
    row, path = _verify_file(
        value,
        root=root,
        name="vulnerability scan",
        extra_keys=frozenset({"scanner_db_sha256"}),
    )
    _digest(row.get("scanner_db_sha256"), name="scanner database sha256")
    scan = load_json(path, name="vulnerability scan")
    if set(scan) != {"exceptions", "findings", "schema_id"} or scan.get(
        "schema_id"
    ) != "betelgeuze.product_vulnerability_scan/1.0.0":
        raise ProductReleaseQualificationError(
            "vulnerability scan identity is invalid"
        )
    exceptions = {
        item.get("id"): item
        for item in _sequence(scan.get("exceptions"), name="exceptions")
        if isinstance(item, dict)
    }
    for finding in _sequence(scan.get("findings"), name="findings"):
        item = _mapping(finding, name="vulnerability finding")
        severity = str(item.get("severity", "")).lower()
        if severity not in {"critical", "high"}:
            continue
        identifier = item.get("id")
        exception = exceptions.get(identifier)
        if not isinstance(exception, dict):
            raise ProductReleaseQualificationError(
                "unexcepted high or critical vulnerability"
            )
        issued = _parse_utc(exception.get("issued_at_utc"), name="exception issue")
        expires = _parse_utc(
            exception.get("expires_at_utc"), name="exception expiry"
        )
        now = now_utc.astimezone(timezone.utc)
        if (
            expires <= issued
            or (expires - issued).days > 30
            or now > expires
            or not isinstance(exception.get("reviewer"), str)
            or not exception["reviewer"]
        ):
            raise ProductReleaseQualificationError(
                "vulnerability exception is invalid or expired"
            )


def _verify_licenses(value: object, *, root: Path) -> None:
    row, path = _verify_file(
        value,
        root=root,
        name="license scan",
        extra_keys=frozenset({"attribution_path", "attribution_sha256"}),
    )
    _verify_file(
        {
            "path": row.get("attribution_path"),
            "sha256": row.get("attribution_sha256"),
        },
        root=root,
        name="license attribution",
    )
    scan = load_json(path, name="license scan")
    if set(scan) != {"packages", "schema_id"} or scan.get(
        "schema_id"
    ) != "betelgeuze.product_license_scan/1.0.0":
        raise ProductReleaseQualificationError("license scan identity is invalid")
    for package in _sequence(scan.get("packages"), name="license packages"):
        item = _mapping(package, name="license package")
        license_id = item.get("license_spdx")
        if license_id in {None, "", "UNKNOWN", "AGPL-3.0-only", "SSPL-1.0"}:
            raise ProductReleaseQualificationError(
                "denied or unknown package license"
            )


def _verify_provenance(
    value: object,
    *,
    root: Path,
    image_digest: str,
    trusted_public_key_raw: bytes | None,
) -> None:
    row = _mapping(value, name="provenance")
    if set(row) != {
        "attestation_path",
        "attestation_sha256",
        "signature_base64",
        "signed",
    }:
        raise ProductReleaseQualificationError("provenance key set is invalid")
    if row.get("signed") is not True or trusted_public_key_raw is None:
        raise ProductReleaseQualificationError(
            "signed provenance and a trusted key are required"
        )
    if len(trusted_public_key_raw) != 32:
        raise ProductReleaseQualificationError("trusted Ed25519 key is invalid")
    _, path = _verify_file(
        {
            "path": row.get("attestation_path"),
            "sha256": row.get("attestation_sha256"),
        },
        root=root,
        name="provenance attestation",
    )
    attestation = load_json(path, name="provenance attestation")
    if (
        set(attestation) != {
            "builder_id",
            "image_digest",
            "materials_sha256",
            "policy_sha256",
            "schema_id",
        }
        or attestation.get("schema_id")
        != "betelgeuze.product_provenance/1.0.0"
        or attestation.get("image_digest") != image_digest
        or attestation.get("policy_sha256") != EXPECTED_POLICY_SHA256
        or not isinstance(attestation.get("builder_id"), str)
        or not attestation["builder_id"]
    ):
        raise ProductReleaseQualificationError(
            "provenance attestation is cross-wired"
        )
    _digest(attestation.get("materials_sha256"), name="provenance materials")
    signature = row.get("signature_base64")
    if not isinstance(signature, str):
        raise ProductReleaseQualificationError("provenance signature is invalid")
    try:
        signature_bytes = base64.b64decode(signature, validate=True)
        Ed25519PublicKey.from_public_bytes(trusted_public_key_raw).verify(
            signature_bytes,
            _canonical_bytes(attestation),
        )
    except (ValueError, InvalidSignature) as exc:
        raise ProductReleaseQualificationError(
            "provenance signature verification failed"
        ) from exc


def _verify_image(value: object) -> str:
    row = _mapping(value, name="image")
    if set(row) != {
        "base_image_digest",
        "base_image_reference",
        "digest",
        "reference",
        "registry_immutable",
    }:
        raise ProductReleaseQualificationError("image key set is invalid")
    image_digest = row.get("digest")
    base_digest = row.get("base_image_digest")
    if (
        not isinstance(image_digest, str)
        or _IMAGE_DIGEST.fullmatch(image_digest) is None
        or not isinstance(base_digest, str)
        or _IMAGE_DIGEST.fullmatch(base_digest) is None
        or not isinstance(row.get("reference"), str)
        or f"@{image_digest}" not in row["reference"]
        or not isinstance(row.get("base_image_reference"), str)
        or f"@{base_digest}" not in row["base_image_reference"]
        or row.get("registry_immutable") is not True
    ):
        raise ProductReleaseQualificationError(
            "image and base image must use immutable digests"
        )
    return image_digest


def _verify_runtime(value: object) -> None:
    row = _mapping(value, name="runtime")
    expected = {
        "gid": 10001,
        "privileged": False,
        "read_only_root": True,
        "uid": 10001,
        "verified": True,
        "writable_mounts": ["/app/logs", "/app/runs", "/data"],
    }
    if row != expected:
        raise ProductReleaseQualificationError(
            "runtime is not non-root, read-only, and mount-bounded"
        )


def _verify_hardware(value: object) -> None:
    row = _mapping(value, name="hardware compatibility")
    if set(row) != {
        "cpu_rows",
        "operational_compatibility_only",
        "rocm_rows",
        "scientific_parity_claimed",
    }:
        raise ProductReleaseQualificationError(
            "hardware compatibility key set is invalid"
        )
    if (
        row.get("operational_compatibility_only") is not True
        or row.get("scientific_parity_claimed") is not False
    ):
        raise ProductReleaseQualificationError(
            "hardware evidence must remain operational-only"
        )
    for name in ("cpu_rows", "rocm_rows"):
        rows = _sequence(row.get(name), name=name)
        if not rows:
            raise ProductReleaseQualificationError(f"{name} is empty")
        for value_row in rows:
            item = _mapping(value_row, name="hardware row")
            if (
                set(item)
                != {
                    "hardware_id",
                    "operational_compatible",
                    "receipt_sha256",
                }
                or not isinstance(item.get("hardware_id"), str)
                or not item["hardware_id"]
                or item.get("operational_compatible") is not True
            ):
                raise ProductReleaseQualificationError(
                    "hardware compatibility row is invalid"
                )
            _digest(item.get("receipt_sha256"), name="hardware receipt")


def _verify_rollback(value: object, *, root: Path) -> None:
    row = _mapping(value, name="rollback")
    if set(row) != {
        "incident_response_path",
        "previous_digest",
        "registry_retention_days",
        "restore_procedure_path",
        "verified",
    }:
        raise ProductReleaseQualificationError("rollback key set is invalid")
    if (
        row.get("verified") is not True
        or not isinstance(row.get("previous_digest"), str)
        or _IMAGE_DIGEST.fullmatch(row["previous_digest"]) is None
        or type(row.get("registry_retention_days")) is not int
        or row["registry_retention_days"] < 30
    ):
        raise ProductReleaseQualificationError("rollback evidence is invalid")
    for field, name in (
        ("restore_procedure_path", "restore procedure"),
        ("incident_response_path", "incident response"),
    ):
        path = _artifact_path(root, row.get(field), name=name)
        if path.stat().st_size <= 0:
            raise ProductReleaseQualificationError(f"{name} is empty")


def verify_evidence(
    evidence: Mapping[str, Any],
    *,
    policy: Mapping[str, Any],
    artifact_root: Path,
    trusted_public_key_raw: bytes | None = None,
    now_utc: datetime | None = None,
) -> ReleaseQualificationResult:
    verify_policy(policy)
    expected_keys = {
        "authority",
        "evidence_sha256",
        "hardware_compatibility",
        "image",
        "license_scan",
        "policy_sha256",
        "provenance",
        "python_lock",
        "rollback",
        "runtime",
        "sboms",
        "schema_id",
        "status",
        "vulnerability_scan",
        "wheelhouse",
    }
    if set(evidence) != expected_keys:
        raise ProductReleaseQualificationError("evidence key set is invalid")
    if (
        evidence.get("schema_id") != EVIDENCE_SCHEMA_ID
        or evidence.get("policy_sha256") != EXPECTED_POLICY_SHA256
    ):
        raise ProductReleaseQualificationError("evidence identity is invalid")
    identity = _verify_self_hash(
        evidence,
        field="evidence_sha256",
        name="release evidence",
    )
    authority = _mapping(evidence.get("authority"), name="evidence authority")
    if set(authority) != set(AUTHORITY_KEYS) or any(
        authority.get(key) is not False for key in AUTHORITY_KEYS
    ):
        raise ProductReleaseQualificationError(
            "release evidence authority escalation detected"
        )
    if evidence.get("status") == TEMPLATE_STATUS:
        blockers = (
            "digest_pinned_image_missing",
            "hash_locked_offline_dependencies_missing",
            "sbom_vulnerability_license_provenance_missing",
            "runtime_and_hardware_qualification_missing",
            "rollback_and_incident_evidence_missing",
            "human_release_authorization_missing",
        )
        return ReleaseQualificationResult(
            technical_evidence_complete=False,
            release_qualified=False,
            blockers=blockers,
            evidence_sha256=identity,
        )
    if evidence.get("status") != COMPLETE_STATUS:
        raise ProductReleaseQualificationError("evidence status is invalid")
    root = artifact_root.resolve(strict=True)
    image_digest = _verify_image(evidence.get("image"))
    _verify_python_lock(evidence.get("python_lock"), root=root)
    _verify_wheelhouse(evidence.get("wheelhouse"), root=root)
    _verify_sboms(evidence.get("sboms"), root=root)
    _verify_vulnerabilities(
        evidence.get("vulnerability_scan"),
        root=root,
        now_utc=now_utc or datetime.now(timezone.utc),
    )
    _verify_licenses(evidence.get("license_scan"), root=root)
    _verify_provenance(
        evidence.get("provenance"),
        root=root,
        image_digest=image_digest,
        trusted_public_key_raw=trusted_public_key_raw,
    )
    _verify_runtime(evidence.get("runtime"))
    _verify_hardware(evidence.get("hardware_compatibility"))
    _verify_rollback(evidence.get("rollback"), root=root)
    return ReleaseQualificationResult(
        technical_evidence_complete=True,
        release_qualified=False,
        blockers=("human_release_authorization_missing",),
        evidence_sha256=identity,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/product_release_qualification_policy.json"
        ),
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=(
            Path(__file__).resolve().parents[1]
            / "config/product_release_qualification_evidence.template.json"
        ),
    )
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--trusted-public-key-hex")
    args = parser.parse_args()
    policy = load_json(args.policy, name="release policy")
    evidence = load_json(args.evidence, name="release evidence")
    trusted_key = (
        bytes.fromhex(args.trusted_public_key_hex)
        if args.trusted_public_key_hex
        else None
    )
    result = verify_evidence(
        evidence,
        policy=policy,
        artifact_root=args.artifact_root or args.evidence.parent.parent,
        trusted_public_key_raw=trusted_key,
    )
    print(
        json.dumps(
            {
                "technical_evidence_complete": (
                    result.technical_evidence_complete
                ),
                "release_qualified": result.release_qualified,
                "blockers": list(result.blockers),
                "evidence_sha256": result.evidence_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
