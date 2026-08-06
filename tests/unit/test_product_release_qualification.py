from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import tools.verify_product_release_qualification as mod
from tools.verify_product_release_qualification import (
    ProductReleaseQualificationError,
    load_json,
    verify_evidence,
    verify_policy,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_POLICY_PATH = _REPO_ROOT / "config/product_release_qualification_policy.json"
_TEMPLATE_PATH = (
    _REPO_ROOT / "config/product_release_qualification_evidence.template.json"
)
_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _seal(evidence: dict[str, object]) -> dict[str, object]:
    evidence.pop("evidence_sha256", None)
    evidence["evidence_sha256"] = mod._sha256(evidence)
    return evidence


def _file_row(root: Path, path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": _sha_file(path),
    }


def _complete_fixture(root: Path):
    lock = root / "artifacts/requirements-api.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(
        "package-a==1.0 --hash=sha256:" + "a" * 64 + "\n",
        encoding="utf-8",
    )

    wheel = root / "wheelhouse/package_a-1.0-py3-none-any.whl"
    wheel.parent.mkdir(parents=True, exist_ok=True)
    wheel.write_bytes(b"synthetic-wheel-bytes")
    wheel_manifest = root / "artifacts/wheelhouse.json"
    _write_json(
        wheel_manifest,
        {
            "schema_id": "betelgeuze.product_wheelhouse/1.0.0",
            "offline": True,
            "entries": [
                {
                    "path": wheel.relative_to(root).as_posix(),
                    "sha256": _sha_file(wheel),
                    "origin": "https://files.pythonhosted.org/synthetic",
                    "record_sha256": "b" * 64,
                    "license_spdx": "MIT",
                }
            ],
        },
    )

    sboms = {}
    for index, component in enumerate(mod.SBOM_COMPONENTS):
        path = root / f"artifacts/{component}-sbom.json"
        if index % 2:
            document = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "components": [],
            }
            format_id = "cyclonedx-1.6"
        else:
            document = {
                "spdxVersion": "SPDX-2.3",
                "packages": [],
            }
            format_id = "spdx-2.3"
        _write_json(path, document)
        sboms[component] = {
            **_file_row(root, path),
            "format": format_id,
        }

    vulnerabilities = root / "artifacts/vulnerabilities.json"
    _write_json(
        vulnerabilities,
        {
            "schema_id": "betelgeuze.product_vulnerability_scan/1.0.0",
            "findings": [],
            "exceptions": [],
        },
    )

    licenses = root / "artifacts/licenses.json"
    _write_json(
        licenses,
        {
            "schema_id": "betelgeuze.product_license_scan/1.0.0",
            "packages": [
                {"name": "package-a", "license_spdx": "MIT"}
            ],
        },
    )
    attribution = root / "artifacts/THIRD_PARTY_NOTICES.txt"
    attribution.write_text("package-a — MIT\n", encoding="utf-8")

    restore = root / "artifacts/restore.md"
    restore.write_text("Restore the prior immutable digest.\n", encoding="utf-8")
    incident = root / "artifacts/incident.md"
    incident.write_text("Revoke, retain, investigate, and restore.\n", encoding="utf-8")

    image_digest = "sha256:" + "c" * 64
    base_digest = "sha256:" + "d" * 64
    attestation = root / "artifacts/provenance.json"
    attestation_payload = {
        "schema_id": "betelgeuze.product_provenance/1.0.0",
        "builder_id": "isolated-release-builder-v1",
        "image_digest": image_digest,
        "policy_sha256": mod.EXPECTED_POLICY_SHA256,
        "materials_sha256": "e" * 64,
    }
    _write_json(attestation, attestation_payload)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    signature = base64.b64encode(
        private.sign(mod._canonical_bytes(attestation_payload))
    ).decode("ascii")

    evidence: dict[str, object] = {
        "schema_id": mod.EVIDENCE_SCHEMA_ID,
        "status": mod.COMPLETE_STATUS,
        "policy_sha256": mod.EXPECTED_POLICY_SHA256,
        "image": {
            "reference": f"registry.example/betelgeuze@{image_digest}",
            "digest": image_digest,
            "base_image_reference": f"rocm/pytorch@{base_digest}",
            "base_image_digest": base_digest,
            "registry_immutable": True,
        },
        "python_lock": {
            **_file_row(root, lock),
            "offline": True,
            "require_hashes": True,
        },
        "wheelhouse": {
            "manifest_path": wheel_manifest.relative_to(root).as_posix(),
            "manifest_sha256": _sha_file(wheel_manifest),
            "entry_count": 1,
            "all_origins_verified": True,
            "all_records_verified": True,
        },
        "sboms": sboms,
        "vulnerability_scan": {
            **_file_row(root, vulnerabilities),
            "scanner_db_sha256": "f" * 64,
        },
        "license_scan": {
            **_file_row(root, licenses),
            "attribution_path": attribution.relative_to(root).as_posix(),
            "attribution_sha256": _sha_file(attribution),
        },
        "provenance": {
            "attestation_path": attestation.relative_to(root).as_posix(),
            "attestation_sha256": _sha_file(attestation),
            "signature_base64": signature,
            "signed": True,
        },
        "runtime": {
            "uid": 10001,
            "gid": 10001,
            "read_only_root": True,
            "writable_mounts": ["/app/logs", "/app/runs", "/data"],
            "privileged": False,
            "verified": True,
        },
        "hardware_compatibility": {
            "cpu_rows": [
                {
                    "hardware_id": "x86_64-reference",
                    "operational_compatible": True,
                    "receipt_sha256": "1" * 64,
                }
            ],
            "rocm_rows": [
                {
                    "hardware_id": "gfx1100-rocm-qualified",
                    "operational_compatible": True,
                    "receipt_sha256": "2" * 64,
                }
            ],
            "operational_compatibility_only": True,
            "scientific_parity_claimed": False,
        },
        "rollback": {
            "previous_digest": "sha256:" + "3" * 64,
            "restore_procedure_path": restore.relative_to(root).as_posix(),
            "incident_response_path": incident.relative_to(root).as_posix(),
            "registry_retention_days": 90,
            "verified": True,
        },
        "authority": {key: False for key in mod.AUTHORITY_KEYS},
    }
    return _seal(evidence), public


def test_frozen_policy_and_unqualified_template_verify() -> None:
    policy = load_json(_POLICY_PATH, name="policy")
    template = load_json(_TEMPLATE_PATH, name="template")

    assert verify_policy(policy) == mod.EXPECTED_POLICY_SHA256
    result = verify_evidence(
        template,
        policy=policy,
        artifact_root=_REPO_ROOT,
    )

    assert result.technical_evidence_complete is False
    assert result.release_qualified is False
    assert "human_release_authorization_missing" in result.blockers


def test_complete_synthetic_evidence_is_technical_only(
    tmp_path: Path,
) -> None:
    evidence, public = _complete_fixture(tmp_path)
    policy = load_json(_POLICY_PATH, name="policy")

    result = verify_evidence(
        evidence,
        policy=policy,
        artifact_root=tmp_path,
        trusted_public_key_raw=public,
        now_utc=_NOW,
    )

    assert result.technical_evidence_complete is True
    assert result.release_qualified is False
    assert result.blockers == ("human_release_authorization_missing",)


def test_image_lock_runtime_and_hardware_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    policy = load_json(_POLICY_PATH, name="policy")
    original, public = _complete_fixture(tmp_path)

    mutations = []
    image = copy.deepcopy(original)
    image["image"]["base_image_reference"] = "rocm/pytorch:mutable"
    mutations.append((image, "immutable digests"))

    lock = copy.deepcopy(original)
    lock_path = tmp_path / lock["python_lock"]["path"]
    lock_path.write_text("package-a==1.0\n", encoding="utf-8")
    lock["python_lock"]["sha256"] = _sha_file(lock_path)
    mutations.append((lock, "unhashed"))

    runtime = copy.deepcopy(original)
    runtime["runtime"]["uid"] = 0
    mutations.append((runtime, "runtime"))

    hardware = copy.deepcopy(original)
    hardware["hardware_compatibility"]["rocm_rows"] = []
    mutations.append((hardware, "rocm_rows"))

    for evidence, match in mutations:
        _seal(evidence)
        with pytest.raises(ProductReleaseQualificationError, match=match):
            verify_evidence(
                evidence,
                policy=policy,
                artifact_root=tmp_path,
                trusted_public_key_raw=public,
                now_utc=_NOW,
            )
        if match == "unhashed":
            lock_path.write_text(
                "package-a==1.0 --hash=sha256:" + "a" * 64 + "\n",
                encoding="utf-8",
            )


def test_vulnerability_license_and_provenance_tamper_fail_closed(
    tmp_path: Path,
) -> None:
    policy = load_json(_POLICY_PATH, name="policy")
    original, public = _complete_fixture(tmp_path)

    vulnerable = copy.deepcopy(original)
    scan_path = tmp_path / vulnerable["vulnerability_scan"]["path"]
    _write_json(
        scan_path,
        {
            "schema_id": "betelgeuze.product_vulnerability_scan/1.0.0",
            "findings": [{"id": "CVE-TEST", "severity": "critical"}],
            "exceptions": [],
        },
    )
    vulnerable["vulnerability_scan"]["sha256"] = _sha_file(scan_path)
    _seal(vulnerable)
    with pytest.raises(
        ProductReleaseQualificationError,
        match="high or critical",
    ):
        verify_evidence(
            vulnerable,
            policy=policy,
            artifact_root=tmp_path,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )

    original, public = _complete_fixture(tmp_path)
    denied = copy.deepcopy(original)
    license_path = tmp_path / denied["license_scan"]["path"]
    _write_json(
        license_path,
        {
            "schema_id": "betelgeuze.product_license_scan/1.0.0",
            "packages": [
                {"name": "package-a", "license_spdx": "AGPL-3.0-only"}
            ],
        },
    )
    denied["license_scan"]["sha256"] = _sha_file(license_path)
    _seal(denied)
    with pytest.raises(ProductReleaseQualificationError, match="denied"):
        verify_evidence(
            denied,
            policy=policy,
            artifact_root=tmp_path,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )

    original, public = _complete_fixture(tmp_path)
    signature = copy.deepcopy(original)
    signature["provenance"]["signature_base64"] = base64.b64encode(
        b"invalid-signature"
    ).decode("ascii")
    _seal(signature)
    with pytest.raises(ProductReleaseQualificationError, match="signature"):
        verify_evidence(
            signature,
            policy=policy,
            artifact_root=tmp_path,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )


def test_symlink_and_authority_escalation_fail_closed(
    tmp_path: Path,
) -> None:
    policy = load_json(_POLICY_PATH, name="policy")
    original, public = _complete_fixture(tmp_path)

    authority = copy.deepcopy(original)
    authority["authority"]["registry_push_authorized"] = True
    _seal(authority)
    with pytest.raises(ProductReleaseQualificationError, match="authority"):
        verify_evidence(
            authority,
            policy=policy,
            artifact_root=tmp_path,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )

    original, public = _complete_fixture(tmp_path)
    lock_path = tmp_path / original["python_lock"]["path"]
    target = tmp_path / "outside.lock"
    target.write_bytes(lock_path.read_bytes())
    lock_path.unlink()
    lock_path.symlink_to(target)
    original["python_lock"]["sha256"] = _sha_file(target)
    _seal(original)
    with pytest.raises(ProductReleaseQualificationError, match="symlink"):
        verify_evidence(
            original,
            policy=policy,
            artifact_root=tmp_path,
            trusted_public_key_raw=public,
            now_utc=_NOW,
        )
