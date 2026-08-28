from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import (
    verify_engine_v2_native_direct_ewald_composite_dynamics_v1 as verifier,
)


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py"
WORKFLOW = (
    ROOT / ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml"
)
PROFILE_SHA256 = (
    "42aad2692719d3d0233d9b71e24e6b49fe50a27fbc150d31fb4d9688ae84215f"
)


def _profile_inputs() -> tuple[bytes, bytes, int]:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    return profile_raw, manifest_raw, source_count


def test_historical_predecessor_is_exact_squash_tree_and_ancestor() -> None:
    assert verifier.PREDECESSOR == {
        "merge_commit": "f2731176fb913f600349ec6a1fbf3678d399a7c1",
        "merge_tree": "6017cf05e3f437443371966775bb4deb3fc73cab",
        "profile_path": (
            "config/engine_v2_native_direct_ewald_composite_profile_v1.json"
        ),
        "profile_sha256": (
            "31dc3535d915980b1a7c318839162a4ce62d6a8bbf221b3415a67a98677d57e7"
        ),
        "pull_request": 437,
        "reviewed_head": "454bb9ee6cdb4202cecbc807f78503ce842bdd13",
        "source_manifest_entry_count": 73,
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_composite_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "53267e95900402f60f4aba13a674e0e9530291d68310765d1a35a17146bf6afb"
        ),
    }
    observed = verifier.require_predecessor(ROOT)
    assert observed["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert observed["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert observed["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert observed["source_manifest_entry_count"] == 73
    assert set(observed["frozen_predecessor_paths"]) == {
        path.as_posix() for path in verifier.FROZEN_PREDECESSOR_PATHS
    }


def test_invalid_historical_object_identity_fails_before_git_lookup() -> None:
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="object identity is invalid",
    ):
        verifier.require_predecessor(ROOT, merge_commit="not-an-object")

    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="reviewed-head metadata changed",
    ):
        verifier.require_predecessor(ROOT, reviewed_head="0" * 40)


def test_frozen_parent_or_legacy_checkpoint_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frozen = ROOT / verifier.FROZEN_PREDECESSOR_PATHS[-1]
    real_read_bytes = Path.read_bytes

    def read_with_frozen_drift(path: Path) -> bytes:
        raw = real_read_bytes(path)
        return raw + b"\n" if path == frozen else raw

    monkeypatch.setattr(Path, "read_bytes", read_with_frozen_drift)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="frozen predecessor source bytes changed",
    ):
        verifier.require_predecessor(ROOT)


def test_exact_profile_and_source_binding_verify() -> None:
    profile_raw, manifest_raw, source_count = _profile_inputs()
    assert hashlib.sha256(profile_raw).hexdigest() == PROFILE_SHA256
    manifest, _ = verifier.require_source_manifest(ROOT, manifest_raw)
    profile = verifier.require_profile(
        profile_raw,
        source_manifest_raw=manifest_raw,
        source_count=source_count,
    )
    assert profile_raw == verifier.canonical_bytes(profile)
    assert manifest == verifier.build_source_manifest(ROOT)
    assert profile["predecessor"] == verifier.PREDECESSOR
    assert profile["authority"] == verifier.AUTHORITY_CONTRACT
    assert all(value is False for value in profile["authority"].values())
    assert profile["operational_boundary"] == verifier.OPERATIONAL_BOUNDARY
    assert profile["abi"]["exported_symbol_count"] == 13
    assert profile["implementation"]["stateful_owner_added"] is True
    assert profile["implementation"]["shared_velocity_verlet_sha256_pipeline"] is True


def test_manifest_is_sorted_unique_exact_and_acyclic() -> None:
    raw = MANIFEST.read_bytes()
    manifest, sources = verifier.require_source_manifest(ROOT, raw)
    paths = [row["path"] for row in manifest["files"]]
    assert paths == sorted(set(paths))
    assert paths == [
        path.as_posix() for path in verifier.discover_source_paths(ROOT)
    ]
    assert verifier.PROFILE_RELATIVE_PATH.as_posix() not in sources
    assert verifier.SOURCE_MANIFEST_RELATIVE_PATH.as_posix() not in sources
    assert "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py" in sources
    for required in (
        "rust/betelgeuze-runtime/src/dynamics.rs",
        "native/src/hip/backend.hpp",
        "native/src/hip/evaluator.cpp",
        "native/src/hip/evaluator.hpp",
        "native/src/hip/provider.h",
        "native/src/hip/stub.cpp",
        "rust/betelgeuze-sys/vendor/native/src/hip/backend.hpp",
        "rust/betelgeuze-sys/vendor/native/src/hip/evaluator.cpp",
        "rust/betelgeuze-sys/vendor/native/src/hip/evaluator.hpp",
        "rust/betelgeuze-sys/vendor/native/src/hip/provider.h",
        "rust/betelgeuze-sys/vendor/native/src/hip/stub.cpp",
    ):
        assert required in sources
    assert "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_v1.py" not in sources
    assert "docs/engine_v2_native_direct_ewald_composite_dynamics_v1.md" not in sources
    assert (
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics.yml"
        not in sources
    )


def test_authority_or_operational_escalation_fails_closed() -> None:
    profile_raw, manifest_raw, source_count = _profile_inputs()
    profile = json.loads(profile_raw)
    profile["authority"]["molecular_execution_authorized"] = True
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="authority changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )

    profile = json.loads(profile_raw)
    profile["operational_boundary"]["blockers"].pop()
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="operational blocker boundary changed",
    ):
        verifier.require_profile(
            verifier.canonical_bytes(profile),
            source_manifest_raw=manifest_raw,
            source_count=source_count,
        )


def test_source_byte_or_path_tampering_fails_closed() -> None:
    manifest = json.loads(MANIFEST.read_bytes())
    manifest["files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_bytes())
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="sorted and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))


def test_stateful_pipeline_and_vendor_tampering_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())

    tampered = dict(sources)
    implementation = "native/src/composite/direct_ewald_composite_dynamics.cpp"
    tampered[implementation] = tampered[implementation].replace(
        b"DynamicStateRollback",
        b"DynamicStateCommit",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="implementation contract is missing",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    vendor = "rust/betelgeuze-sys/vendor/native/src/ewald/model.hpp"
    tampered[vendor] += b"\n"
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="vendored composite-dynamics dependency drifted",
    ):
        verifier._require_source_contract(tampered)


def test_command_line_verifier_is_read_only_and_authority_bounded() -> None:
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
    assert payload["all_authority_false"] is True
    assert payload["fixed64_cpu_v7_qualification_invoked"] is False
    assert payload["frozen_predecessor_file_count"] == 4
    assert payload["hip_device_execution_invoked"] is False
    assert payload["molecular_execution_invoked"] is False
    assert payload["operational_blocker_count"] == 4
    assert payload["unresolved_operational_decisions"] == 32
    assert payload["profile_sha256"] == PROFILE_SHA256


def test_ci_runs_only_bounded_cpu_and_hosted_export_checks() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--refresh" not in workflow
    for required in (
        "verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py",
        "test_engine_v2_native_direct_ewald_composite_dynamics_v1.py",
        "betelgeuze_engine_direct_ewald_composite_dynamics",
        "-p betelgeuze-sys --test layout --test raw_smoke",
        "-p betelgeuze-runtime --test direct_ewald_composite_dynamics",
        "-p betelgeuze-runtime --doc",
        "macos-export-boundary:",
        "runs-on: macos-15",
        'CUDA_VISIBLE_DEVICES: ""',
        'HIP_VISIBLE_DEVICES: ""',
        'ROCR_VISIBLE_DEVICES: ""',
        "-DBG_ENABLE_HIP=OFF",
        "-DBG_ENABLE_HIP_SAFE=OFF",
        "betelgeuze_engine_export_allowlist",
        "fetch-depth: 0",
        'native/src/hip/**',
    ):
        assert required in workflow
    for forbidden in (
        "fixed64-cpu-qualify-v7",
        "qualification_v7_execution",
        "workflow_run",
        "pull_request_target",
        "BG_REQUIRE_HIP_DEVICE",
    ):
        assert forbidden not in workflow


@pytest.mark.parametrize("failure_phase", ("second_replace", "post_verify"))
def test_refresh_rolls_back_both_evidence_files_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_phase: str,
) -> None:
    manifest_relative = Path("manifest.json")
    profile_relative = Path("profile.json")
    manifest = tmp_path / manifest_relative
    profile = tmp_path / profile_relative
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")

    real_replace = verifier.os.replace
    second_replace_failed = False
    verify_called = False

    def replace_with_injected_failure(source: object, destination: object) -> None:
        nonlocal second_replace_failed
        if (
            failure_phase == "second_replace"
            and Path(destination) == profile
            and not second_replace_failed
        ):
            second_replace_failed = True
            raise OSError("injected second replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(verifier.os, "replace", replace_with_injected_failure)

    def verify_current() -> dict[str, object]:
        nonlocal verify_called
        verify_called = True
        if failure_phase == "post_verify":
            raise verifier.NativeDirectEwaldCompositeDynamicsV1Error(
                "injected post-write verification failure"
            )
        return {"verified": True}

    expected_error = (
        "original evidence restored"
        if failure_phase == "second_replace"
        else "injected post-write verification failure"
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match=expected_error,
    ):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (manifest_relative, b"new manifest\n"),
                (profile_relative, b"new profile\n"),
            ),
            verify_current,
        )

    assert second_replace_failed is (failure_phase == "second_replace")
    assert verify_called is (failure_phase == "post_verify")
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "manifest.json",
        "profile.json",
    ]


@pytest.mark.parametrize("interrupt_type", (KeyboardInterrupt, SystemExit))
def test_refresh_rolls_back_on_base_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupt_type: type[BaseException],
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")
    real_replace = verifier.os.replace
    interrupted = False

    def replace_with_interrupt(source: object, destination: object) -> None:
        nonlocal interrupted
        if Path(destination) == profile and not interrupted:
            interrupted = True
            raise interrupt_type()
        real_replace(source, destination)

    monkeypatch.setattr(verifier.os, "replace", replace_with_interrupt)
    with pytest.raises(interrupt_type):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )

    assert interrupted is True
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "manifest.json",
        "profile.json",
    ]


def test_refresh_preserves_backup_when_rollback_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")
    real_replace = verifier.os.replace
    commit_failed = False

    def replace_with_failures(source: object, destination: object) -> None:
        nonlocal commit_failed
        destination_path = Path(destination)
        if destination_path == profile and not commit_failed:
            commit_failed = True
            raise OSError("injected second replace failure")
        if destination_path == manifest and commit_failed:
            raise OSError("injected manifest rollback failure")
        real_replace(source, destination)

    monkeypatch.setattr(verifier.os, "replace", replace_with_failures)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="rollback was incomplete.*backup preserved",
    ):
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )

    assert manifest.read_bytes() == b"new manifest\n"
    assert profile.read_bytes() == b"old profile\n"
    backups = [
        path
        for path in tmp_path.iterdir()
        if path.name not in ("manifest.json", "profile.json")
    ]
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old manifest\n"


def test_refresh_rejects_a_symlinked_evidence_ancestor(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "config").symlink_to(outside, target_is_directory=True)

    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="symlinked or non-directory ancestor",
    ):
        verifier._replace_evidence_transactionally(
            root,
            (
                (Path("config/manifest.json"), b"new manifest\n"),
                (Path("config/profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )

    assert list(outside.iterdir()) == []


def test_temporary_cleanup_is_best_effort_and_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.tmp"
    second = tmp_path / "second.tmp"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    real_unlink = Path.unlink

    def unlink_with_one_failure(
        path: Path, *, missing_ok: bool = False
    ) -> None:
        if path == first:
            raise OSError("injected cleanup failure")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink_with_one_failure)
    errors = verifier._cleanup_evidence_temporaries((first, second))

    assert len(errors) == 1
    assert "injected cleanup failure" in errors[0]
    assert first.exists()
    assert not second.exists()


def test_staging_cleanup_failure_reports_the_preserved_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")
    real_unlink = Path.unlink

    def fail_fsync(_descriptor: int) -> None:
        raise OSError("injected staging failure")

    def fail_temporary_unlink(
        path: Path, *, missing_ok: bool = False
    ) -> None:
        if path.suffix == ".tmp":
            raise OSError("injected temporary cleanup failure")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(verifier.os, "fsync", fail_fsync)
    monkeypatch.setattr(Path, "unlink", fail_temporary_unlink)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="evidence staging failed and temporary cleanup was incomplete",
    ) as raised:
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )

    temporaries = [path for path in tmp_path.iterdir() if path.suffix == ".tmp"]
    assert len(temporaries) == 1
    assert str(temporaries[0]) in str(raised.value)
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"


def test_late_staging_and_outer_cleanup_report_every_preserved_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "manifest.json"
    profile = tmp_path / "profile.json"
    manifest.write_bytes(b"old manifest\n")
    profile.write_bytes(b"old profile\n")
    fsync_calls = 0
    real_unlink = Path.unlink

    def fail_third_fsync(_descriptor: int) -> None:
        nonlocal fsync_calls
        fsync_calls += 1
        if fsync_calls == 3:
            raise OSError("injected late staging failure")

    def fail_temporary_unlink(
        path: Path, *, missing_ok: bool = False
    ) -> None:
        if path.suffix == ".tmp":
            raise OSError("injected temporary cleanup failure")
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(verifier.os, "fsync", fail_third_fsync)
    monkeypatch.setattr(Path, "unlink", fail_temporary_unlink)
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeDynamicsV1Error,
        match="refresh staging failed before commit.*cleanup was incomplete",
    ) as raised:
        verifier._replace_evidence_transactionally(
            tmp_path,
            (
                (Path("manifest.json"), b"new manifest\n"),
                (Path("profile.json"), b"new profile\n"),
            ),
            lambda: {"verified": True},
        )

    temporaries = sorted(
        (path for path in tmp_path.iterdir() if path.suffix == ".tmp"),
        key=lambda path: path.name,
    )
    assert fsync_calls == 3
    assert len(temporaries) == 3
    for temporary in temporaries:
        assert str(temporary) in str(raised.value)
    assert manifest.read_bytes() == b"old manifest\n"
    assert profile.read_bytes() == b"old profile\n"
