from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "verify_community_reproduction_receipt_v1",
    ROOT / "tools/verify_community_reproduction_receipt_v1.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _valid_receipt(*, backend: str = "rust_cpu") -> dict[str, object]:
    document: dict[str, object] = {
        "schema_id": MODULE.SCHEMA_ID,
        "repository": MODULE.REPOSITORY,
        "source_commit_sha": "1" * 40,
        "profile_id": "engine_v2_native_fixed64_cpu_synthetic_v7",
        "backend": backend,
        "hardware": {
            "os": "Ubuntu 24.04",
            "architecture": "x86_64",
            "cpu_model": "Example CPU",
            "gpu_model": "AMD GPU" if backend.startswith("hip_") else None,
            "rocm_version": "6.0.2" if backend.startswith("hip_") else None,
        },
        "software": {
            "python_version": "3.12.4",
            "rustc_version": "rustc example",
            "compiler_identity": "gcc example",
            "wheel_sha256": "2" * 64,
            "native_extension_sha256": "3" * 64,
        },
        "benchmark": {
            "benchmark_id": "synthetic-fixed64-v7",
            "manifest_sha256": "4" * 64,
            "case_count": 2,
            "candidate_denominator": 64,
            "result_sha256": "5" * 64,
        },
        "results": {
            "completed_case_count": 2,
            "failed_case_count": 0,
            "metrics": {
                "top1_recovery_count": 1,
                "runtime_seconds": 0.125,
                "failure_codes": [],
            },
        },
        "submitter": {
            "github_login": "independent-user",
            "organization": None,
            "attests_independent_run": True,
        },
        "claim_boundary": {
            "self_reported": True,
            "project_verified": False,
            "scientific_claim_authorized": False,
            "benchmark_claim_authorized": False,
            "product_claim_authorized": False,
        },
    }
    document["receipt_sha256"] = MODULE._sha256(document)
    return document


def _write(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _reseal(document: dict[str, object]) -> None:
    document.pop("receipt_sha256", None)
    document["receipt_sha256"] = MODULE._sha256(document)


def test_valid_cpu_receipt_is_structurally_verified(tmp_path: Path) -> None:
    result = MODULE.verify(_write(tmp_path, _valid_receipt()))
    assert result["verified"] is True
    assert result["project_verified"] is False
    assert result["claim_authority_granted"] is False


def test_valid_hip_receipt_requires_device_identity(tmp_path: Path) -> None:
    document = _valid_receipt(backend="hip_safe")
    result = MODULE.verify(_write(tmp_path, document))
    assert result["backend"] == "hip_safe"

    document["hardware"]["rocm_version"] = None
    _reseal(document)
    with pytest.raises(MODULE.CommunityReceiptError, match="require GPU and ROCm"):
        MODULE.verify(_write(tmp_path, document))


def test_case_denominator_mismatch_is_rejected(tmp_path: Path) -> None:
    document = _valid_receipt()
    document["results"]["failed_case_count"] = 1
    _reseal(document)
    with pytest.raises(MODULE.CommunityReceiptError, match="must equal case_count"):
        MODULE.verify(_write(tmp_path, document))


def test_claim_escalation_is_rejected_even_when_resealed(tmp_path: Path) -> None:
    document = _valid_receipt()
    document["claim_boundary"]["scientific_claim_authorized"] = True
    _reseal(document)
    with pytest.raises(MODULE.CommunityReceiptError, match="claim authority escalated"):
        MODULE.verify(_write(tmp_path, document))


def test_receipt_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    document = _valid_receipt()
    document["results"]["metrics"]["top1_recovery_count"] = 2
    with pytest.raises(MODULE.CommunityReceiptError, match="does not match"):
        MODULE.verify(_write(tmp_path, document))


def test_secret_like_metric_key_is_rejected(tmp_path: Path) -> None:
    document = _valid_receipt()
    document["results"]["metrics"]["access_token"] = "do-not-submit"
    _reseal(document)
    with pytest.raises(MODULE.CommunityReceiptError, match="secret-like"):
        MODULE.verify(_write(tmp_path, document))
