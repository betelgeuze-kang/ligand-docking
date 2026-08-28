from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import verify_engine_v2_native_direct_ewald_cpu_v1 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / "tools/verify_engine_v2_native_direct_ewald_cpu_v1.py"
WORKFLOW = ROOT / ".github/workflows/ci-engine-v2-native-direct-ewald.yml"
PROFILE_SHA256 = (
    "5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8"
)


def test_exact_profile_and_source_binding_verify() -> None:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
    assert hashlib.sha256(profile_raw).hexdigest() == PROFILE_SHA256
    manifest, _ = verifier.require_source_manifest(ROOT, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile = verifier.require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    assert profile["parent_reference"] == verifier.PARENT_REFERENCE
    assert profile["authority"] == verifier.AUTHORITY_CONTRACT
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY


def test_manifest_is_sorted_unique_exact_and_cycle_free() -> None:
    raw = MANIFEST.read_bytes()
    manifest, sources = verifier.require_source_manifest(ROOT, raw)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert paths == [
        path.as_posix() for path in verifier.discover_source_paths(ROOT)
    ]
    assert manifest == verifier.build_source_manifest(ROOT)
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in sources
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in sources
    assert "tools/__init__.py" in sources
    assert "tools/verify_engine_v2_native_direct_ewald_cpu_v1.py" in sources
    assert "tests/unit/test_engine_v2_native_direct_ewald_cpu_v1.py" not in sources


def test_parent_oracle_and_merge_provenance_are_exact() -> None:
    assert verifier.PARENT_REFERENCE == {
        "cargo_lock_sha256": (
            "cc64500cc1c97dfda26a8a4c8b8825c5296935f1e63cbaf61676a321364b3d9d"
        ),
        "fixture_sha256": (
            "a720c83852c79e401cb8838e9e20b2196985b6e424275949f77291b30b3da338"
        ),
        "merge_commit": "ba008fcaa75891bca45e7b3d33b67449d80fb7d4",
        "merge_tree": "0530a50af2cceeff02341ccb6fab141fd8c43726",
        "profile_path": "config/engine_v2_direct_ewald_reference_profile_v1.json",
        "profile_sha256": (
            "dd2c7460c2c3e7ea800da51e29bdf54d8933497ade086812d882a65cca4f4e6c"
        ),
        "pull_request": 435,
        "reference_schema_id": "betelgeuze.reference_direct_ewald/1.0.0",
        "reviewed_head": "b94e4c008db1c8414f5d0f24fa266c85c828d13c",
        "source_sha256": (
            "2de8d94d69175053ccaf2a8057a385019fe5c398d7d95d96c84dc3d9bfafc99e"
        ),
    }
    assert (
        ROOT / verifier.RUNTIME_FIXTURE_RELATIVE_PATH
    ).read_bytes() == (
        ROOT / verifier.REFERENCE_FIXTURE_RELATIVE_PATH
    ).read_bytes()
    verifier.verify(ROOT)


def test_authority_escalation_fails_closed() -> None:
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["authority"]["molecular_execution_authorized"] = True
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="claim authority changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_source_byte_or_path_tampering_fails_closed() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="sorted and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))


def test_manifest_hash_binding_tampering_fails_closed() -> None:
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["implementation"]["source_manifest_sha256"] = "f" * 64
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="native implementation binding changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_production_reference_dependency_fails_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    for path in (
        "native/CMakeLists.txt",
        "rust/betelgeuze-runtime/Cargo.toml",
        "rust_engine_v2/Cargo.lock",
        "rust_engine_v2/Cargo.toml",
    ):
        tampered = dict(sources)
        tampered[path] += b'\nreference-ewald = { path = "../reference-ewald" }\n'
        with pytest.raises(
            verifier.NativeDirectEwaldCPUProfileV1Error,
            match="reference entered production",
        ):
            verifier._require_source_contract(tampered)


def test_mach_o_export_boundary_fails_closed_on_private_or_missing_symbols() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    exports_path = "native/betelgeuze_engine.exports"

    tampered = dict(sources)
    tampered[exports_path] += (
        b"_bg_rust_direct_ewald_provider_abi_version_v1\n"
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="private Rust provider entered the Mach-O",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    export_lines = tampered[exports_path].splitlines()
    tampered[exports_path] = b"\n".join(export_lines[:-1]) + b"\n"
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="Mach-O public export allowlist changed",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/CMakeLists.txt"] = tampered[
        "native/CMakeLists.txt"
    ].replace(b"LINKER:-exported_symbols_list", b"LINKER:-not-an-export-list")
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="Mach-O final-link export boundary is missing",
    ):
        verifier._require_source_contract(tampered)


def test_operational_blocker_removal_fails_closed() -> None:
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["operational_boundary"]["blockers"].pop()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    with pytest.raises(
        verifier.NativeDirectEwaldCPUProfileV1Error,
        match="operational blocker boundary changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_command_line_verifier_is_non_executing_and_authority_bounded() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert completed.stderr == ""
    assert payload["verified"] is True
    assert payload["profile_sha256"] == PROFILE_SHA256
    assert payload["source_count"] > 0
    assert payload["fixed64_cpu_v7_qualification_invoked"] is False
    assert payload["hip_device_execution_invoked"] is False
    assert payload["molecular_execution_invoked"] is False
    assert payload["operational_blocker_count"] == 4


def test_ci_is_read_only_evidence_verification_without_forbidden_execution() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--refresh" not in workflow
    assert "verify_engine_v2_native_direct_ewald_cpu_v1.py" in workflow
    assert "test_engine_v2_native_direct_ewald_cpu_v1.py" in workflow
    for required in (
        '"native/betelgeuze_engine.exports"',
        "macos-export-boundary:",
        "runs-on: macos-15",
        "-DBG_ENABLE_HIP_SAFE=OFF",
        "betelgeuze_engine_export_allowlist",
    ):
        assert required in workflow
    for forbidden in (
        "fixed64-cpu-qualify-v7",
        "qualification_v7_execution",
        "workflow_run",
        "pull_request_target",
        "BETELGEUZE_V7_QUALIFICATION_BUILD",
    ):
        assert forbidden not in workflow
