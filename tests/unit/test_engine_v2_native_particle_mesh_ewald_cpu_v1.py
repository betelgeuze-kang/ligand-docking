from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import verify_engine_v2_native_particle_mesh_ewald_cpu_v1 as verifier


ROOT = Path(__file__).resolve().parents[2]
ADDITIVE_PARTICLE_MESH_EWALD_COMPOSITE_EVIDENCE_PRESENT = all(
    (ROOT / relative).is_file()
    for relative in (
        "include/betelgeuze/particle_mesh_ewald_composite.h",
        "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json",
        "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1_sources.json",
        "tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
    )
)
pytestmark = pytest.mark.skipif(
    ADDITIVE_PARTICLE_MESH_EWALD_COMPOSITE_EVIDENCE_PRESENT,
    reason=(
        "legacy particle-mesh Ewald evidence is verified from its exact frozen "
        "object after the additive short-range composite ABI is present"
    ),
)
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / "tools/verify_engine_v2_native_particle_mesh_ewald_cpu_v1.py"


def test_exact_profile_source_and_parent_binding_verify() -> None:
    manifest_raw = MANIFEST.read_bytes()
    manifest, sources = verifier.require_source_manifest(ROOT, manifest_raw)
    rows = manifest["files"]
    assert isinstance(rows, list)
    profile_raw = PROFILE.read_bytes()
    profile = verifier.require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=len(rows),
    )
    assert profile["parent_references"] == verifier.PARENT_REFERENCES
    assert profile["authority"] == verifier.AUTHORITY_CONTRACT
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY
    assert profile["abi"]["public_symbol_count"] == len(verifier.PUBLIC_SYMBOLS) == 8
    assert (
        profile["validation"]["rust_cpu_frozen_fixture_total_bits_hex"]
        == "c0186145396def20"
    )
    assert "include/betelgeuze/particle_mesh_ewald.h" in sources
    assert verifier.verify(ROOT)["source_count"] == len(rows)


def test_source_manifest_is_exact_sorted_unique_and_cycle_free() -> None:
    manifest_raw = MANIFEST.read_bytes()
    manifest, sources = verifier.require_source_manifest(ROOT, manifest_raw)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert paths == [path.as_posix() for path in verifier.discover_source_paths(ROOT)]
    assert manifest == verifier.build_source_manifest(ROOT)
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in sources
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in sources
    for self_evidence in (
        ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml",
        "docs/engine_v2_native_particle_mesh_ewald_cpu_v1.md",
        "tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
        "tools/verify_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
    ):
        assert self_evidence in sources


def test_frozen_parent_objects_are_exact_historical_blobs() -> None:
    verifier.require_frozen_parent_objects(ROOT)
    assert set(verifier.FROZEN_OBJECTS) == {
        "ba008fcaa75891bca45e7b3d33b67449d80fb7d4",
        "074d3b71373088c0738de7a14797fe35d66d986e",
        "ebbd7a20538cfd7516d9b53adb2e54c6de14bd97",
        "735883551510cbef91adc3e57dc131a1234b67fb",
    }
    assert (
        verifier.PARENT_REFERENCES["native_particle_mesh_reciprocal"]["reviewed_head"]
        == "098bce0d726dbed6e4bf7b533e0445f81e244ea2"
    )


def test_authority_or_implementation_escalation_fails_closed() -> None:
    manifest_raw = MANIFEST.read_bytes()
    count = len(json.loads(manifest_raw)["files"])
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["authority"]["molecular_execution_authorized"] = True
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="profile contract",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=count,
        )

    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["implementation"]["hip_device_implementation"] = True
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="profile contract",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=count,
        )


def test_parent_or_operational_drift_fails_closed() -> None:
    manifest_raw = MANIFEST.read_bytes()
    count = len(json.loads(manifest_raw)["files"])
    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["parent_references"]["native_particle_mesh_reciprocal"][
        "merge_tree"
    ] = "0" * 40
    with pytest.raises(verifier.NativeParticleMeshEwaldCPUProfileV1Error):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=count,
        )

    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["operational_boundary"]["blockers"].pop()
    with pytest.raises(verifier.NativeParticleMeshEwaldCPUProfileV1Error):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=count,
        )


def test_manifest_hash_path_or_byte_tampering_fails_closed() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="exact, sorted, and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))


def test_vendor_identity_and_production_dependency_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    tampered = dict(sources)
    tampered[
        "rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_ewald.h"
    ] += b"\n"
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="canonical and vendored",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["rust/betelgeuze-runtime/Cargo.toml"] += (
        b'\nreference-pme = { path = "../reference-pme" }\n'
    )
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="reference entered production",
    ):
        verifier._require_source_contract(tampered)


def test_export_and_rust_binding_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    tampered = dict(sources)
    tampered["native/betelgeuze_engine.exports"] = tampered[
        "native/betelgeuze_engine.exports"
    ].replace(b"_bg_particle_mesh_ewald_v1_profile_id\n", b"")
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="Mach-O export allowlist",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["rust/betelgeuze-runtime/src/particle_mesh_ewald.rs"] = tampered[
        "rust/betelgeuze-runtime/src/particle_mesh_ewald.rs"
    ].replace(b"evaluate_particle_mesh_ewald_energy", b"removed_energy_path")
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCPUProfileV1Error,
        match="safe Rust runtime",
    ):
        verifier._require_source_contract(tampered)


def test_legacy_reciprocal_evidence_is_frozen_and_descendant_aware() -> None:
    workflow = (
        ROOT / ".github/workflows/ci-engine-v2-native-particle-mesh-reciprocal.yml"
    ).read_text(encoding="utf-8")
    unit = (
        ROOT / "tests/unit/test_engine_v2_native_particle_mesh_reciprocal_cpu_v1.py"
    ).read_text(encoding="utf-8")
    for token in (
        "frozen=735883551510cbef91adc3e57dc131a1234b67fb",
        "frozen_tree=6c2b6f3960b6df0592b78bb44e429389aa58bcbb",
        'git checkout --detach --quiet "$frozen"',
        'git checkout --detach --quiet "$current_sha"',
    ):
        assert token in workflow
    assert "--refresh" not in workflow
    assert "pytest.mark.skipif(" in unit
    assert "exact frozen object" in unit


def test_cli_json_report_is_exact() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["profile_sha256"] == hashlib.sha256(PROFILE.read_bytes()).hexdigest()
    assert payload["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST.read_bytes()
    ).hexdigest()
    assert payload["frozen_parent_count"] == 4
    assert payload["authority"] == verifier.AUTHORITY_CONTRACT
