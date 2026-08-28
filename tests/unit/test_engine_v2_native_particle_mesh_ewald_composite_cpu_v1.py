from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1 as verifier,
)


ROOT = Path(__file__).resolve().parents[2]
PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_EVIDENCE_PRESENT,
    reason=(
        "legacy particle-mesh Ewald composite evidence is verified from its exact "
        "frozen object after particle-mesh Ewald composite dynamics evidence is present"
    ),
)
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / (
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py"
)
WORKFLOW = ROOT / (
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite.yml"
)


def _profile_inputs() -> tuple[bytes, bytes, int]:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    return profile_raw, manifest_raw, source_count


def test_exact_profile_source_and_parent_binding_verify() -> None:
    profile_raw, manifest_raw, source_count = _profile_inputs()
    manifest, sources = verifier.require_source_manifest(ROOT, manifest_raw)
    profile = verifier.require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=source_count,
    )
    assert manifest == verifier.build_source_manifest(ROOT)
    assert profile_raw == verifier.canonical_bytes(profile)
    assert profile["parent_references"] == verifier.PARENT_REFERENCES
    assert profile["authority"] == verifier.AUTHORITY_CONTRACT
    assert all(value is False for value in profile["authority"].values())
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY
    assert profile["abi"]["borrowed_handle_count"] == 5
    assert profile["abi"]["energy_component_count"] == 12
    assert profile["abi"]["energy_layout_size_64_bit"] == 144
    assert profile["abi"]["force_layout_size_64_bit"] == 88
    assert len(verifier.PUBLIC_SYMBOLS) == 8
    assert (
        profile["validation"]["rust_cpu_frozen_fixture_total_bits_hex"]
        == "4012dc3129bce12e"
    )
    assert "include/betelgeuze/particle_mesh_ewald_composite.h" in sources
    assert verifier.verify(ROOT)["source_count"] == source_count


def test_source_manifest_is_exact_sorted_unique_and_cycle_free() -> None:
    manifest, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert paths == [path.as_posix() for path in verifier.discover_source_paths(ROOT)]
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in sources
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in sources
    for bound in (
        ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite.yml",
        ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml",
        "docs/engine_v2_native_particle_mesh_ewald_composite_cpu_v1.md",
        "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
        "tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
        "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py",
        "tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
    ):
        assert bound in sources


def test_frozen_parent_objects_and_review_metadata_are_exact() -> None:
    verifier.require_frozen_parent_objects(ROOT)
    assert set(verifier.FROZEN_OBJECTS) == {
        "f2731176fb913f600349ec6a1fbf3678d399a7c1",
        "e228f376857ead900bd1ae99cf5b111c8b40cf34",
    }
    direct = verifier.PARENT_REFERENCES["native_direct_ewald_composite"]
    assert direct["reviewed_head"] == "454bb9ee6cdb4202cecbc807f78503ce842bdd13"
    assert direct["merge_tree"] == "6017cf05e3f437443371966775bb4deb3fc73cab"
    assert direct["source_manifest_entry_count"] == 73
    pme = verifier.PARENT_REFERENCES["native_particle_mesh_ewald"]
    assert pme["reviewed_head"] == "59ad72fe57e82106a71df2c88c63c9fe12d014ad"
    assert pme["merge_tree"] == "ae0a6eddd44262eeec633c57a0f5566bf7989361"
    assert pme["source_manifest_entry_count"] == 82


def test_authority_implementation_parent_or_operational_drift_fails_closed() -> None:
    profile_raw, manifest_raw, source_count = _profile_inputs()
    del profile_raw
    mutations = (
        ("authority", "molecular_execution_authorized", True),
        ("implementation", "hip_device_implementation", True),
    )
    for section, key, value in mutations:
        profile = json.loads(PROFILE.read_text(encoding="ascii"))
        profile[section][key] = value
        with pytest.raises(
            verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
            match="profile contract",
        ):
            verifier.require_profile(
                verifier.canonical_bytes(profile),
                source_manifest_raw=manifest_raw,
                source_count=source_count,
            )

    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["parent_references"]["native_particle_mesh_ewald"]["merge_tree"] = (
        "0" * 40
    )
    with pytest.raises(verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )

    profile = json.loads(PROFILE.read_text(encoding="ascii"))
    profile["operational_boundary"]["blockers"].pop()
    with pytest.raises(verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_noncanonical_duplicate_or_tampered_manifest_fails_closed() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_text(encoding="ascii"))
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="exact, sorted, and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    duplicate = b'{"files":[],"files":[],"schema_id":"x","scope":"y"}\n'
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="duplicate JSON key",
    ):
        verifier.require_source_manifest(ROOT, duplicate)


def test_vendor_zero_charge_export_and_runtime_guards_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())

    tampered = dict(sources)
    vendor = (
        "rust/betelgeuze-sys/vendor/include/betelgeuze/"
        "particle_mesh_ewald_composite.h"
    )
    tampered[vendor] += b"\n"
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="canonical and vendored",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    implementation = "native/src/composite/particle_mesh_ewald_composite.cpp"
    tampered[implementation] = tampered[implementation].replace(
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0)",
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 1.0)",
    )
    vendor_implementation = f"rust/betelgeuze-sys/vendor/{implementation}"
    tampered[vendor_implementation] = tampered[vendor_implementation].replace(
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0)",
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 1.0)",
    )
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="native composite implementation",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    tampered["native/betelgeuze_engine.exports"] = tampered[
        "native/betelgeuze_engine.exports"
    ].replace(b"_bg_particle_mesh_ewald_composite_v1_profile_id\n", b"")
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="Mach-O export allowlist",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    runtime = "rust/betelgeuze-runtime/src/particle_mesh_ewald_composite.rs"
    tampered[runtime] = tampered[runtime].replace(
        b"evaluate_particle_mesh_ewald_composite_energy",
        b"removed_composite_energy_path",
    )
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="safe Rust composite runtime",
    ):
        verifier._require_source_contract(tampered)


def test_predecessor_evidence_is_frozen_and_descendant_aware() -> None:
    workflow = (
        ROOT / ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml"
    ).read_text(encoding="utf-8")
    unit = (
        ROOT / "tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py"
    ).read_text(encoding="utf-8")
    for token in (
        "frozen=e228f376857ead900bd1ae99cf5b111c8b40cf34",
        "frozen_tree=ae0a6eddd44262eeec633c57a0f5566bf7989361",
        'git diff --exit-code "$frozen" --',
        'git checkout --detach --quiet "$frozen"',
        'git checkout --detach --quiet "$current_sha"',
        "refs/pull/441/head",
    ):
        assert token in workflow
    assert "--refresh" not in workflow
    assert "pytest.mark.skipif(" in unit
    assert "exact frozen object" in unit


def test_cli_report_is_read_only_and_authority_bounded() -> None:
    before = (PROFILE.read_bytes(), MANIFEST.read_bytes())
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["verified"] is True
    assert payload["all_authority_false"] is True
    assert payload["fixed64_cpu_v7_qualification_invoked"] is False
    assert payload["hip_device_execution_invoked"] is False
    assert payload["molecular_execution_invoked"] is False
    assert payload["operational_blocker_count"] == 4
    assert payload["unresolved_operational_decisions"] == 32
    assert payload["frozen_parent_count"] == 2
    assert payload["profile_sha256"] == hashlib.sha256(PROFILE.read_bytes()).hexdigest()
    assert payload["source_manifest_sha256"] == hashlib.sha256(
        MANIFEST.read_bytes()
    ).hexdigest()
    assert before == (PROFILE.read_bytes(), MANIFEST.read_bytes())


def test_refresh_rolls_back_both_files_on_post_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest_relative = Path("manifest.json")
    profile_relative = Path("profile.json")
    manifest = tmp_path / manifest_relative
    profile = tmp_path / profile_relative
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")

    def fail_verify(_: Path) -> dict[str, object]:
        raise verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error(
            "injected verification failure"
        )

    monkeypatch.setattr(verifier, "verify", fail_verify)
    with pytest.raises(
        verifier.NativeParticleMeshEwaldCompositeCPUProfileV1Error,
        match="injected verification failure",
    ):
        verifier._replace_evidence(
            tmp_path,
            (
                (manifest_relative, b"new manifest\n"),
                (profile_relative, b"new profile\n"),
            ),
        )
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"
    assert not list(tmp_path.glob(".*.tmp"))


def test_ci_is_hosted_cpu_only_pinned_and_never_refreshes_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--refresh" not in workflow
    for required in (
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        "fetch-depth: 0",
        "refs/pull/437/head",
        "refs/pull/441/head",
        "runs-on: ubuntu-latest",
        "runs-on: macos-15",
        "betelgeuze_engine_particle_mesh_ewald_composite",
        "betelgeuze_engine_export_allowlist",
        "--package betelgeuze-sys --test layout --test raw_smoke",
        "--package betelgeuze-runtime --test particle_mesh_ewald_composite",
        "-DBG_ENABLE_HIP=OFF",
        "-DBG_ENABLE_HIP_SAFE=OFF",
    ):
        assert required in workflow
    for forbidden in (
        "self-hosted",
        "workflow_run",
        "pull_request_target",
        "BG_REQUIRE_HIP_DEVICE",
        "fixed64-cpu-qualify-v7",
        "qualification_v7_execution",
    ):
        assert forbidden not in workflow
