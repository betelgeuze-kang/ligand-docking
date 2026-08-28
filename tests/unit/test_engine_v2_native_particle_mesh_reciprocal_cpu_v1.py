from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / "tools/verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"
WORKFLOW = ROOT / (
    ".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"
)


def test_exact_profile_and_source_binding_verify() -> None:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
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
    assert profile["validation"][
        "cpp_rust_energy_and_force_mixed_tolerance"
    ] == {
        "absolute_tolerance": 5e-12,
        "formula": (
            "abs(observed - expected) <= absolute_tolerance + "
            "relative_tolerance * max(abs(observed), abs(expected))"
        ),
        "relative_tolerance": 5e-12,
    }


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
    assert "CMakeLists.txt" in sources
    assert "tools/__init__.py" in sources
    assert "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py" in sources
    assert "tools/verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py" in sources
    for self_evidence in (
        ".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml",
        "docs/engine_v2_native_particle_mesh_reciprocal_cpu_v1.md",
        "tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py",
    ):
        assert self_evidence in sources
    assert not any(
        "particle_mesh_reciprocal_composite" in Path(path).name for path in sources
    )


def test_parent_oracle_and_merge_provenance_are_exact() -> None:
    assert verifier.PARENT_REFERENCE == {
        "cargo_lock_sha256": (
            "98d90148a16d2a7fc3f20b27a0cc9ab570c47759c2666ea7a9a0193067c94d80"
        ),
        "fft_sha256": (
            "e65c2a4f3837ae25ce32883671462120c6a2ac9af60c27bbe78e92d502c58c01"
        ),
        "fixture_sha256": (
            "669e4409ba56897061976c38fbf53985fb1f744e8e5b3613512b0f957951deef"
        ),
        "merge_commit": "ebbd7a20538cfd7516d9b53adb2e54c6de14bd97",
        "merge_tree": "2ae92801369c7e16147e07cbb16e19c062e52cc9",
        "observation_sha256": (
            "899845a391e23da253a5f0e2bdb5a78794ec7beb4dabee1f04726d6af1492144"
        ),
        "profile_path": "config/engine_v2_pme_reciprocal_reference_profile_v1.json",
        "profile_sha256": (
            "d867651e8d6ce0ec1ead0c0e22dc684b4a0b6247ee35f2bcc9e17105f4c244d3"
        ),
        "pull_request": 439,
        "reference_schema_id": "betelgeuze.reference_particle_mesh_reciprocal/1.0.0",
        "reviewed_head": "62d309c82aab9b4cfa45c4c3e6d11c93b3bd3786",
        "source_manifest_path": (
            "config/engine_v2_pme_reciprocal_reference_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "da6d669c85d63236936ba1f1324937b90e7cf57cc6dd58b16ab7d43d6278b296"
        ),
        "source_sha256": (
            "9579d213ec47fc75f70dbb4df76ff951de4a51518dc9216233c663a3e43e53c4"
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
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="claim authority changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )

    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["implementation"]["full_pme_implemented"] = True
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="native implementation binding changed",
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
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    for self_evidence in (
        Path(".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"),
        Path("docs/engine_v2_native_particle_mesh_reciprocal_cpu_v1.md"),
        Path("tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"),
    ):
        original = verifier.REQUIRED_SOURCE_PATHS
        try:
            verifier.REQUIRED_SOURCE_PATHS = tuple(
                path for path in original if path != self_evidence
            )
            with pytest.raises(
                verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
                match="source manifest path closure changed",
            ):
                verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
        finally:
            verifier.REQUIRED_SOURCE_PATHS = original

    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="sorted and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))


def test_manifest_hash_binding_tampering_fails_closed() -> None:
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["implementation"]["source_manifest_sha256"] = "f" * 64
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
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
        tampered[path] += b'\nreference-pme = { path = "../reference-pme" }\n'
        with pytest.raises(
            verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
            match="reference entered production",
        ):
            verifier._require_source_contract(tampered)


def test_mach_o_export_boundary_fails_closed_on_private_or_missing_symbols() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    exports_path = "native/betelgeuze_engine.exports"

    tampered = dict(sources)
    tampered[exports_path] += (
        b"_bg_rust_particle_mesh_reciprocal_provider_abi_version_v1\n"
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="private Rust provider entered the Mach-O",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    export_lines = tampered[exports_path].splitlines()
    tampered[exports_path] = b"\n".join(export_lines[:-1]) + b"\n"
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="Mach-O public export allowlist changed",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/CMakeLists.txt"] = tampered[
        "native/CMakeLists.txt"
    ].replace(b"LINKER:-exported_symbols_list", b"LINKER:-not-an-export-list")
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="Mach-O final-link export boundary is missing",
    ):
        verifier._require_source_contract(tampered)


def test_particle_mesh_reciprocal_elf_node_is_exact_and_independent() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    tampered = dict(sources)
    tampered["native/betelgeuze_engine.map"] = tampered[
        "native/betelgeuze_engine.map"
    ].replace(
        b"bg_particle_mesh_reciprocal_energy_v1_init;",
        b"bg_particle_mesh_reciprocal_unreviewed_symbol;",
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="public symbol set or order changed",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    decoy_header = b"BETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0 {"
    tampered["native/betelgeuze_engine.map"] = tampered[
        "native/betelgeuze_engine.map"
    ].replace(decoy_header, b"X" + decoy_header, 1) + (
        b"\nBETELGEUZE_PARTICLE_MESH_RECIPROCAL_1.0 {\n"
        b"    global:\n"
        b"        rogue_public_symbol;\n"
        b"} BETELGEUZE_ENGINE_1.21;\n"
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="public symbol set or order changed",
    ):
        verifier._require_source_contract(tampered)

    for rogue_declaration in (b"rogue_public_symbol;", b"*;"):
        tampered = dict(sources)
        tampered["native/betelgeuze_engine.map"] = tampered[
            "native/betelgeuze_engine.map"
        ].replace(
            b"bg_particle_mesh_reciprocal_energy_v1_init;",
            b"bg_particle_mesh_reciprocal_energy_v1_init;\n        "
            + rogue_declaration,
        )
        with pytest.raises(
            verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
            match="public symbol set or order changed",
        ):
            verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/betelgeuze_engine.map"] = tampered[
        "native/betelgeuze_engine.map"
    ].replace(
        b"bg_context_evaluate_particle_mesh_reciprocal_v1;",
        b"bg_context_evaluate_particle_mesh_reciprocal_v1;\n"
        b"        // } BETELGEUZE_ENGINE_1.21;\n"
        b"        rogue_public_symbol;",
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="public symbol set or order changed",
    ):
        verifier._require_source_contract(tampered)


def test_noexcept_typed_error_and_capacity_preflight_tampering_fails_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())

    tampered = dict(sources)
    tampered["native/src/particle_mesh_reciprocal/api.cpp"] = tampered[
        "native/src/particle_mesh_reciprocal/api.cpp"
    ].replace(b"std::string_view detail", b"const std::string &detail", 1)
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="typed-error commit is not allocation-free",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/src/particle_mesh_reciprocal/api.cpp"] = tampered[
        "native/src/particle_mesh_reciprocal/api.cpp"
    ].replace(
        b"switch (context->requested_backend)",
        b"switch (context->backend)",
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="requested-backend fail-closed boundary is missing",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    kernel_path = "rust/cpu-kernel/src/particle_mesh_reciprocal.rs"
    tampered[kernel_path] = tampered[kernel_path].replace(
        b"detail: &'static str",
        b"detail: String",
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="failure diagnostic may allocate",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered[kernel_path] = tampered[kernel_path].replace(
        b".sort_unstable_by(",
        b".sort_by(",
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="failure diagnostic may allocate",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered[kernel_path] = tampered[kernel_path].replace(
        b".sort_unstable_by(",
        b".sort_unstable_by_key(",
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="allocation-free sort contract changed",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    adapter_path = "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
    adapter = tampered[adapter_path]
    capacity = b"if (atom_count > kMaxAtomCount)"
    force_allocation = b"force_x.resize(atom_count)"
    tampered[adapter_path] = adapter.replace(capacity, b"if (false)", 1).replace(
        force_allocation,
        capacity + b" {}\n        " + force_allocation,
        1,
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="capacity preflight moved after provider or force allocation",
    ):
        verifier._require_source_contract(tampered)


def test_descendant_composite_discovery_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    descendant = (
        tmp_path
        / "native/src/particle_mesh_reciprocal_composite/implementation.cpp"
    )
    descendant.parent.mkdir(parents=True)
    descendant.write_text("// must not enter the parent closure\n", encoding="ascii")
    monkeypatch.setattr(verifier, "REQUIRED_SOURCE_PATHS", ())
    monkeypatch.setattr(
        verifier,
        "DISCOVERED_SOURCE_GLOBS",
        ("native/src/**/*",),
    )
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
        match="descendant composite source entered parent discovery",
    ):
        verifier.discover_source_paths(tmp_path)


def test_operational_blocker_removal_fails_closed() -> None:
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["operational_boundary"]["blockers"].pop()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    with pytest.raises(
        verifier.NativeParticleMeshReciprocalCPUProfileV1Error,
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
    assert payload["profile_sha256"] == hashlib.sha256(PROFILE.read_bytes()).hexdigest()
    assert payload["source_count"] > 0
    assert payload["fixed64_cpu_v7_qualification_invoked"] is False
    assert payload["hip_device_execution_invoked"] is False
    assert payload["molecular_execution_invoked"] is False
    assert payload["operational_blocker_count"] == 4


def test_ci_is_read_only_evidence_verification_without_forbidden_execution() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--refresh" not in workflow
    assert "verify_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py" in workflow
    assert "test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py" in workflow
    for required in (
        '"CMakeLists.txt"',
        '"native/betelgeuze_engine.exports"',
        "Materialize frozen parent review and merge",
        "refs/pull/439/head",
        "62d309c82aab9b4cfa45c4c3e6d11c93b3bd3786",
        "ebbd7a20538cfd7516d9b53adb2e54c6de14bd97^{tree}",
        "2ae92801369c7e16147e07cbb16e19c062e52cc9",
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


def test_legacy_native_evidence_runs_from_the_exact_frozen_object() -> None:
    for relative in (
        ".github/workflows/ci-engine-v2-native-direct-ewald.yml",
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml",
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml",
    ):
        workflow = (ROOT / relative).read_text(encoding="utf-8")
        for required in (
            "frozen=ebbd7a20538cfd7516d9b53adb2e54c6de14bd97",
            "frozen_tree=2ae92801369c7e16147e07cbb16e19c062e52cc9",
            'current_sha="$(git rev-parse HEAD)"',
            'git diff --exit-code "$frozen" --',
            'git checkout --detach --quiet "$frozen"',
            'git checkout --detach --quiet "$current_sha"',
            'test "$(git rev-parse HEAD)" = "$current_sha"',
        ):
            assert required in workflow
        assert "--refresh" not in workflow
