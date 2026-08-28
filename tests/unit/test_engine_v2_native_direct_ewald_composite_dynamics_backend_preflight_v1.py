from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from tools import (
    verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1
    as verifier,
)


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / verifier.VERIFIER_RELATIVE_PATH
WORKFLOW = ROOT / verifier.WORKFLOW_RELATIVE_PATH


def _inputs() -> tuple[bytes, bytes, int]:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    return profile_raw, manifest_raw, source_count


def test_exact_successor_profile_manifest_and_authority_verify() -> None:
    profile_raw, manifest_raw, source_count = _inputs()
    manifest, sources = verifier.require_source_manifest(ROOT, manifest_raw)
    profile = verifier.require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=source_count,
    )
    assert manifest == verifier.build_source_manifest(ROOT)
    assert profile_raw == verifier.canonical_bytes(profile)
    assert source_count == 120
    assert profile["predecessor"] == verifier.PREDECESSOR
    assert profile["successor_base"] == verifier.SUCCESSOR_BASE
    assert profile["successor_slice"] == verifier.SUCCESSOR_SLICE_CONTRACT
    assert profile["abi"] == verifier.ABI_CONTRACT
    assert profile["authority"] == verifier.AUTHORITY_CONTRACT
    assert all(value is False for value in profile["authority"].values())
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY
    assert profile["implementation"]["requested_backend_is_authoritative"] is True
    assert profile["implementation"]["new_public_symbol_added"] is False
    assert profile["implementation"]["checkpoint_format_changed"] is False
    assert profile["validation"]["actual_auto_context_rejected"] is True
    assert (
        profile["validation"][
            "safe_rust_unsupported_request_rejected_before_resolved_backend_query"
        ]
        is True
    )
    assert verifier.VERIFIER_RELATIVE_PATH.as_posix() in sources
    assert verifier.verify(ROOT)["source_count"] == 120


def test_source_closure_is_exact_sorted_unique_and_acyclic() -> None:
    manifest, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert paths == [path.as_posix() for path in verifier.discover_source_paths(ROOT)]
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in sources
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in sources
    assert manifest["successor_evidence_paths"] == sorted(
        path.as_posix() for path in verifier.SUCCESSOR_EVIDENCE_PATHS
    )
    assert len(manifest["successor_evidence_paths"]) == 6
    predecessor_manifest = json.loads(
        (ROOT / verifier.PREDECESSOR_MANIFEST_RELATIVE_PATH).read_text(
            encoding="ascii"
        )
    )
    predecessor_paths = {row["path"] for row in predecessor_manifest["files"]}
    assert len(predecessor_paths) == 113
    assert predecessor_paths.issubset(sources)
    for relative in verifier.SUCCESSOR_SOURCE_PATHS:
        assert relative.as_posix() in sources


def test_frozen_pr438_merge_review_tree_and_evidence_are_exact() -> None:
    frozen = verifier.require_frozen_predecessor(ROOT)
    assert frozen["merge_commit"] == "e434295b1711f612e0f7e9fac2d95de92abf19a8"
    assert frozen["reviewed_head"] == "581a17a135d75ddf085c4edd29f3763c2f691fcf"
    assert frozen["merge_tree"] == "3546ef29ae708c16c7af1e3be4925d2d7ad1f6b5"
    assert len(frozen["source_paths"]) == 113
    assert len(frozen["frozen_unchanged_digests"]) == 7
    assert verifier.PREDECESSOR["profile_sha256"] == (
        "42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f"
    )
    assert verifier.PREDECESSOR["source_manifest_sha256"] == (
        "1a7a284467958e7c153edb0afd86cc5ea4ad07b659266ecf59d9da7549a19d15"
    )


def test_successor_base_and_exact_five_implementation_deltas_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert verifier.SUCCESSOR_BASE == {
        "commit": "5f6f4e2642dbe5c1272b2a9710288db25db5164f",
        "tree": "95f3d64a553f6c261d59a7ef8bd202561d51c45a",
    }
    assert len(verifier.BOUND_IMPLEMENTATION_DELTAS) == 5
    assert len(verifier.ORIGINAL_SUCCESSOR_SLICE_PATHS) == 11
    assert len(set(verifier.ORIGINAL_SUCCESSOR_SLICE_PATHS)) == 11
    assert (
        verifier.require_bound_implementation_deltas(ROOT)
        == verifier.BOUND_IMPLEMENTATION_DELTAS
    )

    original_git = verifier._git

    def reject_whole_repository_scan(root: Path, *arguments: str) -> bytes:
        assert arguments[0] != "ls-files"
        assert arguments[:2] != ("diff", "--name-only")
        return original_git(root, *arguments)

    monkeypatch.setattr(verifier, "_git", reject_whole_repository_scan)
    assert (
        verifier.require_bound_implementation_deltas(ROOT)
        == verifier.BOUND_IMPLEMENTATION_DELTAS
    )

    def drifted_base_blob(root: Path, *arguments: str) -> bytes:
        result = original_git(root, *arguments)
        if arguments == (
            "cat-file",
            "blob",
            "5f6f4e2642dbe5c1272b2a9710288db25db5164f:"
            "native/src/composite/direct_ewald_composite_dynamics.cpp",
        ):
            result += b"\n"
        return result

    monkeypatch.setattr(verifier, "_git", drifted_base_blob)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="bound implementation delta changed",
    ):
        verifier.require_bound_implementation_deltas(ROOT)


@pytest.mark.parametrize(
    ("section", "key", "value"),
    (
        ("authority", "molecular_execution_authorized", True),
        ("authority", "qualification_rerun_authorized", True),
        ("implementation", "hip_to_cpu_fallback", True),
        ("implementation", "new_public_symbol_added", True),
        ("abi", "checkpoint_format_changed", True),
        ("validation", "actual_auto_context_rejected", False),
    ),
)
def test_profile_drift_fails_closed(section: str, key: str, value: object) -> None:
    _, manifest_raw, source_count = _inputs()
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile[section][key] = value
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="profile contract",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_exact_blockers_and_32_decisions_cannot_drift() -> None:
    _, manifest_raw, source_count = _inputs()
    for mutation in ("blocker", "decisions"):
        profile = json.loads(PROFILE.read_text(encoding="ascii"))
        if mutation == "blocker":
            profile["operational_boundary"]["blockers"].pop()
        else:
            profile["operational_boundary"]["unresolved_operational_decisions"] = 31
        with pytest.raises(
            verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error
        ):
            verifier.require_profile(
                verifier.canonical_bytes(profile),
                source_manifest_raw=manifest_raw,
                source_count=source_count,
            )


def test_tampered_duplicate_or_noncanonical_manifest_fails_closed() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="exact, sorted, and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    duplicate = b'{"files":[],"files":[],"schema_id":"x","scope":"y"}\n'
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="duplicate JSON key",
    ):
        verifier.require_source_manifest(ROOT, duplicate)


def test_native_requested_backend_and_mismatch_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    implementation = "native/src/composite/direct_ewald_composite_dynamics.cpp"
    vendor = f"rust/betelgeuze-sys/vendor/{implementation}"
    tampered = dict(sources)
    for path in (implementation, vendor):
        tampered[path] = tampered[path].replace(
            b"switch (context->requested_backend)",
            b"switch (context->backend)",
        )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="requested-backend preflight",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    for path in (implementation, vendor):
        tampered[path] = tampered[path].replace(
            b"context->backend != context->requested_backend",
            b"false",
        )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="requested-backend preflight",
    ):
        verifier._require_source_contract(tampered)


def test_safe_rust_real_auto_and_vendor_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    runtime = "rust/betelgeuze-runtime/src/direct_ewald_composite_dynamics.rs"
    tampered = dict(sources)
    tampered[runtime] = tampered[runtime].replace(
        b"let requested = self.requested_backend();",
        b"let requested = self.backend().unwrap();",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="safe Rust backend preflight",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered[runtime] = tampered[runtime].replace(
        b"        self.require_direct_ewald_composite_dynamics_backend()?;\n"
        b"        ensure_composite_dynamics_abi_compatibility()?;",
        b"        ensure_composite_dynamics_abi_compatibility()?;\n"
        b"        self.require_direct_ewald_composite_dynamics_backend()?;",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="preflight must precede ABI",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered[runtime] = tampered[runtime].replace(
        b"        if resolved != requested {\n"
        b"            return Err(abi_error(format!(\n"
        b"                \"native context resolved {resolved:?} after explicit {requested:?} request\"\n"
        b"            )));\n"
        b"        }\n"
        b"        require_direct_ewald_backend(resolved)?;",
        b"        require_direct_ewald_backend(resolved)?;\n"
        b"        if resolved != requested {\n"
        b"            return Err(abi_error(format!(\n"
        b"                \"native context resolved {resolved:?} after explicit {requested:?} request\"\n"
        b"            )));\n"
        b"        }",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="reject mismatch as ABI",
    ):
        verifier._require_source_contract(tampered)

    native = "native/src/composite/direct_ewald_composite_dynamics.cpp"
    vendor = f"rust/betelgeuze-sys/vendor/{native}"
    tampered = dict(sources)
    tampered[vendor] += b"\n"
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="canonical and vendored",
    ):
        verifier._require_source_contract(tampered)


def test_public_symbol_and_checkpoint_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    tampered = dict(sources)
    tampered["native/betelgeuze_engine.exports"] = tampered[
        "native/betelgeuze_engine.exports"
    ].replace(b"_bg_context_integrate_direct_ewald_composite_v1\n", b"")
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="symbol set changed",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/betelgeuze_engine.map"] = tampered[
        "native/betelgeuze_engine.map"
    ].replace(
        b"BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0 {",
        b"BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.1 {",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="ELF version node",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/tests/check_exports.cmake"] = tampered[
        "native/tests/check_exports.cmake"
    ].replace(
        b'set(expected_version "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0")',
        b'set(expected_version "BETELGEUZE_DIRECT_EWALD_COMPOSITE_1.0")',
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="export-version regression mapping",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    checkpoint = "native/src/composite/direct_ewald_composite_checkpoint.cpp"
    vendor_checkpoint = f"rust/betelgeuze-sys/vendor/{checkpoint}"
    for path in (checkpoint, vendor_checkpoint):
        tampered[path] = tampered[path].replace(
            b"constexpr std::size_t kHeaderSize = 104U",
            b"constexpr std::size_t kHeaderSize = 105U",
        )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="unchanged composite checkpoint",
    ):
        verifier._require_source_contract(tampered)


def test_workflow_is_pinned_focused_and_non_authoritative() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    verifier._require_workflow_contract(workflow)
    uses = re.findall(r"(?m)^[ ]{8}uses:[ ]+([^# \t]+)", workflow)
    assert uses == [verifier.PINNED_CHECKOUT_ACTION] * 4
    assert workflow.count("permissions:") == 1
    assert "permissions:\n  contents: read\n\nconcurrency:" in workflow
    assert workflow.count('CUDA_VISIBLE_DEVICES: ""') == 1
    assert workflow.count('HIP_VISIBLE_DEVICES: ""') == 1
    assert workflow.count('ROCR_VISIBLE_DEVICES: ""') == 1
    assert workflow.count("-DBG_ENABLE_HIP=OFF") == 3
    assert workflow.count("-DBG_ENABLE_HIP_SAFE=OFF") == 3
    assert workflow.count('      - "tools/__init__.py"') == 2
    assert "refs/pull/438/head" in workflow
    assert "betelgeuze_engine_direct_ewald_composite_dynamics" in workflow
    assert "--test direct_ewald_composite_dynamics" in workflow
    assert "cargo doc --manifest-path rust/Cargo.toml --locked" in workflow
    for forbidden in (
        "--refresh",
        "self-hosted",
        "pull_request_target",
        "workflow_run",
        "fixed64-cpu-qualify",
        "BG_REQUIRE_HIP_DEVICE",
    ):
        assert forbidden not in workflow


def test_workflow_pin_environment_and_permissions_tampering_fails_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    mutations = (
        (
            workflow.replace(
                verifier.PINNED_CHECKOUT_ACTION,
                "actions/checkout@v4",
                1,
            ),
            "all four workflow uses entries",
        ),
        (
            workflow.replace("  contents: read", "  contents: write", 1),
            "global contents-read permissions",
        ),
        (
            workflow.replace(
                "  native-linux:\n    runs-on:",
                "  native-linux:\n    permissions:\n      contents: read\n    runs-on:",
                1,
            ),
            "exactly one global",
        ),
        (
            workflow.replace('  HIP_VISIBLE_DEVICES: ""', '  HIP_VISIBLE_DEVICES: "0"', 1),
            "global CPU-only environment",
        ),
        (
            workflow.replace("            -DBG_ENABLE_HIP_SAFE=OFF \\\n", "", 1),
            "disable both HIP lanes",
        ),
    )
    for tampered, message in mutations:
        with pytest.raises(
            verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
            match=message,
        ):
            verifier._require_workflow_contract(tampered)


def test_workflow_forbidden_execution_and_trigger_tampering_fails_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for command in (
        "python3 tools/verify_engine_v2_source_paired_clearance_external_reservation.py",
        "python3 tools/install_root_supervisor.py",
        "python3 tools/build_public_benchmark_product_preflight.py",
    ):
        tampered = workflow.replace(
            "          set -euo pipefail\n",
            f"          set -euo pipefail\n          {command}\n",
            1,
        )
        with pytest.raises(
            verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
            match="prohibited reservation, root-supervisor",
        ):
            verifier._require_workflow_contract(tampered)

    tampered = workflow.replace('      - "tools/__init__.py"\n', "", 1)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsBackendPreflightV1Error,
        match="both cover bound tools/__init__.py",
    ):
        verifier._require_workflow_contract(tampered)


def test_cli_is_read_only_and_reports_bounded_result() -> None:
    before = (PROFILE.read_bytes(), MANIFEST.read_bytes())
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["verified"] is True
    assert report["source_count"] == 120
    assert report["all_authority_false"] is True
    assert report["unresolved_operational_decisions"] == 32
    assert report["fixed64_cpu_v7_qualification_invoked"] is False
    assert report["hip_device_execution_invoked"] is False
    assert report["molecular_execution_invoked"] is False
    assert before == (PROFILE.read_bytes(), MANIFEST.read_bytes())
