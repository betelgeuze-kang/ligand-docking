from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools import verify_engine_v2_native_direct_ewald_composite_v1 as verifier


ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / verifier.PROFILE_RELATIVE_PATH
MANIFEST = ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH
TOOL = ROOT / "tools/verify_engine_v2_native_direct_ewald_composite_v1.py"
WORKFLOW = (
    ROOT / ".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml"
)
PROFILE_SHA256 = (
    "31dc3535d915980b1a7c318839162a4ce62d6a8bbf221b3415a67a98677d57e7"
)


def _profile_inputs() -> tuple[bytes, bytes, int]:
    profile_raw = PROFILE.read_bytes()
    manifest_raw = MANIFEST.read_bytes()
    source_count = len(json.loads(manifest_raw)["files"])
    return profile_raw, manifest_raw, source_count


def test_historical_predecessor_is_exact_squash_tree_and_ancestor() -> None:
    assert verifier.PREDECESSOR == {
        "merge_commit": "074d3b71373088c0738de7a14797fe35d66d986e",
        "merge_tree": "e2763a42f4605d7435514c49f18259ea44f4dd3c",
        "profile_path": "config/engine_v2_native_direct_ewald_cpu_profile_v1.json",
        "profile_sha256": (
            "5d0a09742e8388938e90988a6a23fd945d5e2613d0fa37e9f2c8c9dd86d89de8"
        ),
        "pull_request": 436,
        "reviewed_head": "60a0047af27acacbce3feed7ee1dcedd8a690176",
        "source_manifest_entry_count": 55,
        "source_manifest_path": (
            "config/engine_v2_native_direct_ewald_cpu_profile_v1_sources.json"
        ),
        "source_manifest_sha256": (
            "4f2acac517f56ade77b8712bfd24b4312f208f2a5902862f73a807e2a3f7e3ab"
        ),
    }
    observed = verifier.require_predecessor(ROOT)
    assert observed["merge_commit"] == verifier.PREDECESSOR["merge_commit"]
    assert observed["merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert observed["reviewed_head"] == verifier.PREDECESSOR["reviewed_head"]
    assert observed["source_manifest_entry_count"] == 55


def test_invalid_historical_object_identity_fails_before_git_lookup() -> None:
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
        match="object identity is invalid",
    ):
        verifier.require_predecessor(ROOT, merge_commit="not-an-object")

    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
        match="reviewed-head metadata changed",
    ):
        verifier.require_predecessor(ROOT, reviewed_head="0" * 40)


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
    assert "tools/verify_engine_v2_native_direct_ewald_composite_v1.py" in sources
    assert "tests/unit/test_engine_v2_native_direct_ewald_composite_v1.py" not in sources
    assert "docs/engine_v2_native_direct_ewald_composite_v1.md" not in sources
    assert (
        ".github/workflows/ci-engine-v2-native-direct-ewald-composite.yml"
        not in sources
    )


def test_authority_or_operational_escalation_fails_closed() -> None:
    profile_raw, manifest_raw, source_count = _profile_inputs()
    profile = json.loads(profile_raw)
    profile["authority"]["molecular_execution_authorized"] = True
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
        match="source bytes drifted",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))

    manifest = json.loads(MANIFEST.read_bytes())
    manifest["files"].append(dict(manifest["files"][-1]))
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
        match="sorted and unique",
    ):
        verifier.require_source_manifest(ROOT, verifier.canonical_bytes(manifest))


def test_zero_charge_provenance_and_vendor_tampering_fail_closed() -> None:
    _, sources = verifier.require_source_manifest(ROOT, MANIFEST.read_bytes())

    tampered = dict(sources)
    implementation = "native/src/composite/direct_ewald.cpp"
    tampered[implementation] = tampered[implementation].replace(
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0)",
        b"std::fill(short_system.charge.begin(), short_system.charge.end(), 1.0)",
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
        match="implementation contract is missing",
    ):
        verifier._require_source_contract(tampered)

    tampered = dict(sources)
    vendor = "rust/betelgeuze-sys/vendor/native/src/ewald/model.hpp"
    tampered[vendor] += b"\n"
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
        match="vendored composite dependency drifted",
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
    assert payload["hip_device_execution_invoked"] is False
    assert payload["molecular_execution_invoked"] is False
    assert payload["operational_blocker_count"] == 4
    assert payload["unresolved_operational_decisions"] == 32
    assert payload["profile_sha256"] == PROFILE_SHA256


def test_ci_runs_only_bounded_cpu_and_hosted_export_checks() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "--refresh" not in workflow
    for required in (
        "verify_engine_v2_native_direct_ewald_composite_v1.py",
        "test_engine_v2_native_direct_ewald_composite_v1.py",
        "betelgeuze_engine_direct_ewald_composite",
        "-p betelgeuze-sys --test layout --test raw_smoke",
        "-p betelgeuze-runtime --test composite",
        "macos-export-boundary:",
        "runs-on: macos-15",
        "-DBG_ENABLE_HIP_SAFE=OFF",
        "betelgeuze_engine_export_allowlist",
        "fetch-depth: 0",
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
            raise verifier.NativeDirectEwaldCompositeV1Error(
                "injected post-write verification failure"
            )
        return {"verified": True}

    expected_error = (
        "original evidence restored"
        if failure_phase == "second_replace"
        else "injected post-write verification failure"
    )
    with pytest.raises(
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
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
        verifier.NativeDirectEwaldCompositeV1Error,
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
