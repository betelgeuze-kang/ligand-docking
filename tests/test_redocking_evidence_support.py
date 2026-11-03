"""Synthetic filesystem contracts; no package installation or molecular work."""
from __future__ import annotations

import base64
import csv
from importlib import metadata, util
import io
import json
import marshal
import os
from pathlib import Path
import py_compile
import stat
import sys
import zipfile

import pytest

from tools import redocking_evidence_support as support


METADATA = b"Metadata-Version: 2.1\nName: demo\nVersion: 1.0\n"
WHEEL = b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n"


def _wheel(root, *, extra=None):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "demo-1.0-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("demo/__init__.py", b"VALUE = 1\n")
        archive.writestr("demo-1.0.dist-info/METADATA", METADATA)
        archive.writestr("demo-1.0.dist-info/WHEEL", WHEEL)
        if extra:
            archive.writestr(*extra)
    return path


def _record(root, *, reverse=False):
    base = root / "lib/python3.10/site-packages"
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "RECORD":
            continue
        key = os.path.relpath(path, base).replace(os.sep, "/")
        body = path.read_bytes()
        digest = base64.urlsafe_b64encode(support.hashlib.sha256(body).digest()).rstrip(b"=").decode()
        rows.append([key, "" if path.suffix == ".pyc" else "sha256=" + digest,
                     "" if path.suffix == ".pyc" else str(len(body))])
    rows.append(["demo-1.0.dist-info/RECORD", "", ""])
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(reversed(rows) if reverse else rows)
    (base / "demo-1.0.dist-info/RECORD").write_text(buffer.getvalue())


def _install(root, *, cache=False, reverse_record=False):
    base = root / "lib/python3.10/site-packages"
    package, distinfo = base / "demo", base / "demo-1.0.dist-info"
    package.mkdir(parents=True)
    distinfo.mkdir()
    (package / "__init__.py").write_bytes(b"VALUE = 1\n")
    (package / "_native.so").write_bytes(b"synthetic-native-payload\0")
    (distinfo / "METADATA").write_bytes(METADATA)
    (distinfo / "WHEEL").write_bytes(WHEEL)
    (distinfo / "INSTALLER").write_bytes(b"pip\n")
    (distinfo / "REQUESTED").write_bytes(b"")
    (root / "bin").mkdir()
    script = root / "bin/demo"
    script.write_bytes(b"#!/usr/bin/env python3\nfrom demo import VALUE\n")
    script.chmod(0o755)
    if cache:
        py_compile.compile(str(package / "__init__.py"), doraise=True)
    _record(root, reverse=reverse_record)
    return metadata.PathDistribution(distinfo)


@pytest.fixture
def environment_fixture(tmp_path, monkeypatch):
    _wheel(tmp_path / "wheels")
    manifest = support.freeze_wheelhouse(tmp_path / "wheels", expected_versions={"Demo": "1.0"})
    source = tmp_path / "runner.py"
    source.write_text("# fixed synthetic source\n")
    # The real interpreter capture is checked separately; all synthetic nodes use
    # one recorded interpreter while installed distributions use real RECORD APIs.
    runtime = {"implementation": "cpython", "version": "fixed", "cache_tag": "fixed",
        "platform": "linux", "machine": "x86_64", "byteorder": "little",
        "executable": {"path": "/python", "size": 1, "sha256": "1" * 64, "mode": 0o755},
        "libpython": [{"path": "/libpython.so", "size": 2, "sha256": "2" * 64, "mode": 0o755}]}
    monkeypatch.setattr(support, "_runtime", lambda: runtime)

    def capture(root, *, chosen_manifest=None):
        distribution = metadata.PathDistribution(root / "lib/python3.10/site-packages/demo-1.0.dist-info")
        monkeypatch.setattr(support.metadata, "distribution", lambda name: distribution)
        return support.snapshot_environment({"demo": "1.0"}, source_files={"tools/runner.py": source},
            wheelhouse_manifest=chosen_manifest or manifest, install_root=root)

    return manifest, source, capture


def test_wheel_manifest_freezes_bytes_versions_and_hashed_requirements(tmp_path):
    wheel = _wheel(tmp_path / "wheels")
    manifest = support.freeze_wheelhouse(wheel.parent, expected_versions={"Demo": "1.0"})
    assert manifest["distributions"] == {"demo": "1.0"}
    assert support.verify_wheelhouse(wheel.parent, manifest) == manifest
    assert support.hashed_requirements(manifest) == f"demo==1.0 --hash=sha256:{manifest['files'][0]['sha256']}\n"
    wheel.write_bytes(wheel.read_bytes() + b"different wheel bytes")
    with pytest.raises(support.EvidenceError, match="differ"):
        support.verify_wheelhouse(wheel.parent, manifest)


@pytest.mark.parametrize("change", ["missing", "extra", "version", "symlink", "nested"])
def test_wheelhouse_rejects_unfrozen_or_unsafe_set(tmp_path, change):
    wheel = _wheel(tmp_path / "wheels")
    manifest = support.freeze_wheelhouse(wheel.parent)
    if change == "missing":
        wheel.unlink()
    elif change == "extra":
        (wheel.parent / "unknown.txt").write_text("extra")
    elif change == "version":
        with pytest.raises(support.EvidenceError, match="version differs"):
            support.freeze_wheelhouse(wheel.parent, expected_versions={"demo": "2.0"})
        return
    elif change == "symlink":
        target = tmp_path / wheel.name
        wheel.rename(target)
        wheel.symlink_to(target)
    else:
        (wheel.parent / "nested").mkdir()
    with pytest.raises(support.EvidenceError):
        support.verify_wheelhouse(wheel.parent, manifest)


def test_freeze_rejects_wheel_member_escape_and_manifest_tampering(tmp_path):
    wheel = _wheel(tmp_path / "bad", extra=("../escaped.py", b"bad"))
    with pytest.raises(support.EvidenceError, match="unsafe relative"):
        support.freeze_wheelhouse(wheel.parent)
    good = _wheel(tmp_path / "good")
    manifest = support.freeze_wheelhouse(good.parent)
    manifest["distributions"]["demo"] = "2.0"
    with pytest.raises(support.EvidenceError, match="manifest_sha256 mismatch"):
        support.verify_wheelhouse(good.parent, manifest)


def test_snapshot_captures_actual_record_source_native_and_console_script(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    report = capture(root)
    files = {r["path"]: r for r in report["distributions"]["demo"]["files"]}
    assert files["demo/__init__.py"]["content_included"]
    assert files["demo/_native.so"]["content_included"]
    assert files["../../../bin/demo"]["content_included"]
    assert files["demo-1.0.dist-info/RECORD"]["exclusion_reason"] == "installer_file_record"
    assert report["raw_payload_sha256"] != report["content_identity_sha256"]
    assert support.require_matching_environment(report, report)["matches"]
    legacy = [[key, "regular", row["size"], row["sha256"]] for key, row in sorted(files.items())]
    assert report["legacy_payload_sha256s"]["demo"] == support._digest(legacy)


def test_raw_cache_and_record_differences_are_visible_but_content_matches(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    left, right = tmp_path / "left", tmp_path / "right"
    _install(left, cache=True)
    _install(right, cache=True, reverse_record=True)
    a, b = capture(left), capture(right)
    comparison = support.require_matching_environment(a, b)
    assert comparison["matches"] and comparison["content_identity_equal"]
    assert not comparison["raw_installed_payload_equal"]
    paths = [row["path"] for row in comparison["raw_file_differences"]]
    assert any(path.endswith(".pyc") for path in paths)
    assert "demo-1.0.dist-info/RECORD" in paths
    assert all(row["allowed_installation_only_difference"] for row in comparison["raw_file_differences"])
    cache = next(row for row in b["distributions"]["demo"]["files"] if row["path"].endswith(".pyc"))
    assert cache["exclusion_validation"]["validation"] == "code_matches_compilation_of_present_source"
    assert cache["sha256"] and cache["exclusion_validation"]["source_sha256"]


@pytest.mark.parametrize("target", ["demo/__init__.py", "demo/_native.so", "../../../bin/demo"])
def test_source_native_or_console_byte_changes_fail_active_identity(tmp_path, environment_fixture, target):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    before = capture(root)
    path = root / "lib/python3.10/site-packages" / target
    path.write_bytes(path.read_bytes() + b"# changed\n")
    _record(root)
    after = capture(root)
    with pytest.raises(support.EnvironmentMismatch) as error:
        support.require_matching_environment(before, after)
    differences = error.value.comparison["forbidden_file_differences"]
    assert {"distribution": "demo", "path": target} in differences
    assert not error.value.comparison["content_identity_equal"]


def test_source_mapping_and_wheel_set_are_part_of_identity(tmp_path, environment_fixture):
    _, source, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    before = capture(root)
    source.write_text("# revised runner\n")
    changed_source = capture(root)
    comparison = support.compare_environments(before, changed_source)
    assert not comparison["matches"]
    assert "source_files" in comparison["identity_context_differences"]
    _wheel(tmp_path / "different-wheels", extra=("demo/data.txt", b"extra wheel payload"))
    manifest = support.freeze_wheelhouse(tmp_path / "different-wheels")
    changed_wheels = capture(root, chosen_manifest=manifest)
    comparison = support.compare_environments(changed_source, changed_wheels)
    assert not comparison["matches"]
    assert "wheel_set_sha256" in comparison["identity_context_differences"]


@pytest.mark.parametrize("corruption", ["code", "missing_source", "unrecorded_source", "native_missing", "symlink", "escape"])
def test_installed_payload_rejects_unknown_or_unvalidated_changes(tmp_path, environment_fixture, corruption):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root, cache=True)
    base = root / "lib/python3.10/site-packages"
    source = base / "demo/__init__.py"
    if corruption == "code":
        cache = Path(util.cache_from_source(str(source)))
        header = cache.read_bytes()[:16]
        cache.write_bytes(header + marshal.dumps(compile("VALUE = 999\n", str(source), "exec")))
    elif corruption == "missing_source":
        source.unlink()
    elif corruption == "unrecorded_source":
        (base / "demo/extra.py").write_text("VALUE = 3\n")
    elif corruption == "native_missing":
        (base / "demo/_native.so").unlink()
    elif corruption == "symlink":
        source.unlink()
        source.symlink_to(tmp_path / "runner.py")
    else:
        record = base / "demo-1.0.dist-info/RECORD"
        with record.open("a") as stream:
            stream.write("../../../../escape.py,,\n")
    with pytest.raises(support.EvidenceError):
        capture(root)


def test_unrecorded_generated_cache_is_in_raw_inventory(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    before = capture(root)
    source = root / "lib/python3.10/site-packages/demo/__init__.py"
    py_compile.compile(str(source), doraise=True)
    after = capture(root)
    rows = after["distributions"]["demo"]["files"]
    cache = next(row for row in rows if row["path"].endswith(".pyc"))
    assert cache["recorded"] is False and cache["content_included"] is False
    assert after["legacy_payload_sha256s"] == before["legacy_payload_sha256s"]
    assert after["raw_payload_sha256"] != before["raw_payload_sha256"]
    assert support.require_matching_environment(before, after)["matches"]


def test_recorded_missing_cache_stays_visible_and_does_not_become_missing_source(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root, cache=True)
    before = capture(root)
    source = root / "lib/python3.10/site-packages/demo/__init__.py"
    Path(util.cache_from_source(str(source))).unlink()
    after = capture(root)
    cache = next(row for row in after["distributions"]["demo"]["files"] if row["path"].endswith(".pyc"))
    assert cache["status"] == "missing" and cache["sha256"] is None
    assert cache["exclusion_validation"]["validation"] == "missing_cache_with_present_source"
    assert support.require_matching_environment(before, after)["matches"]


def test_install_origin_exclusion_requires_frozen_wheel_hash(tmp_path, environment_fixture):
    manifest, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    direct_url = root / "lib/python3.10/site-packages/demo-1.0.dist-info/direct_url.json"
    direct_url.write_text(json.dumps({"url": "file:///one/wheel.whl", "archive_info": {"hashes": {"sha256": manifest["files"][0]["sha256"]}}}))
    _record(root)
    before = capture(root)
    data = json.loads(direct_url.read_text())
    data["url"] = "file:///other/wheel.whl"
    direct_url.write_text(json.dumps(data))
    _record(root)
    after = capture(root)
    assert support.require_matching_environment(before, after)["matches"]
    data["archive_info"]["hashes"]["sha256"] = "f" * 64
    direct_url.write_text(json.dumps(data))
    _record(root)
    with pytest.raises(support.EvidenceError, match="not bound to the frozen wheel"):
        capture(root)


def test_record_hash_and_wheel_metadata_are_checked(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    source = root / "lib/python3.10/site-packages/demo/__init__.py"
    source.write_bytes(b"VALUE = 9\n")
    with pytest.raises(support.EvidenceError, match="RECORD hash differs"):
        capture(root)
    _record(root)
    metadata_file = root / "lib/python3.10/site-packages/demo-1.0.dist-info/METADATA"
    metadata_file.write_bytes(METADATA + b"Summary: changed metadata\n")
    _record(root)
    with pytest.raises(support.EvidenceError, match="metadata is not bound"):
        capture(root)


def test_real_interpreter_is_resolved_and_libpython_is_separate():
    runtime = support._runtime()
    assert runtime["executable"]["path"] == str(Path(sys.executable).resolve())
    assert runtime["executable"]["sha256"] == support._regular(Path(sys.executable).resolve())["sha256"]
    for library in runtime["libpython"]:
        assert Path(library["path"]).is_file()
        assert library["sha256"] == support._regular(Path(library["path"]))["sha256"]


def _evidence(root):
    hidden = root / "raw/CASE/inputs/.CASE.pinned-0123456789abcdef0123456789abcdef"
    hidden.mkdir(parents=True)
    (hidden / "native.sdf").write_bytes(b"synthetic saved input, no molecular execution\n")
    (root / "attempt.json").write_text('{"termination":"wall_timeout","rows":{}}\n')
    binary = root / "raw/CASE/private-external-binary"
    binary.mkdir()
    (binary / "gnina").write_bytes(b"disposable private binary")
    (root / "artifact-inventory.json").write_text('{"stale_inventory":true}\n')
    return hidden


def test_sealed_upload_contains_hidden_timeout_inputs_and_exact_inventory(tmp_path):
    root, archive = tmp_path / "evidence", tmp_path / "upload.zip"
    hidden = _evidence(root)
    original = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = support.seal_artifact_archive(root, archive)
    assert result["inventory_matches_actual_upload"] and result["hidden_files_included"]
    assert result["payload_files"] == 2 and result["archive_members"] == 3
    with zipfile.ZipFile(archive) as sealed:
        inventory = json.loads(sealed.read("artifact-inventory.json"))
        assert hidden.relative_to(root).as_posix() + "/native.sdf" in sealed.namelist()
        assert not any("private-external-binary" in path for path in sealed.namelist())
        assert inventory["excluded_paths"] == [{"path": "raw/CASE/private-external-binary", "reason": "private_external_binary_not_uploaded"}]
        assert set(sealed.namelist()) == {row["path"] for row in inventory["files"]} | {"artifact-inventory.json"}
    assert original == {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert support.verify_artifact_archive(archive, expected_sha256=result["archive_sha256"])["status"] == "verified"


@pytest.mark.parametrize("change", ["symlink_file", "symlink_directory", "fifo", "destination_inside", "destination_alias", "size_limit"])
def test_seal_rejects_unsafe_paths_and_bounds(tmp_path, change):
    root, archive = tmp_path / "evidence", tmp_path / "upload.zip"
    _evidence(root)
    kwargs = {}
    if change == "symlink_file":
        (root / "link").symlink_to(tmp_path / "outside")
    elif change == "symlink_directory":
        (root / "link").symlink_to(tmp_path, target_is_directory=True)
    elif change == "fifo":
        os.mkfifo(root / "pipe")
    elif change == "destination_inside":
        archive = root / "upload.zip"
    elif change == "destination_alias":
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        archive = alias / "upload.zip"
    else:
        kwargs["maximum_bytes"] = 1
    with pytest.raises(support.EvidenceError):
        support.seal_artifact_archive(root, archive, **kwargs)
    assert not archive.exists()


@pytest.mark.parametrize("change", ["payload", "extra", "missing", "escape", "symlink"])
def test_verify_archive_rejects_changed_actual_upload_set(tmp_path, change):
    root, archive = tmp_path / "evidence", tmp_path / "upload.zip"
    _evidence(root)
    support.seal_artifact_archive(root, archive)
    with zipfile.ZipFile(archive) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    if change == "payload":
        entries["attempt.json"] += b"changed"
    elif change == "extra":
        entries["unlisted.txt"] = b"unlisted"
    elif change == "missing":
        entries.pop("attempt.json")
    elif change == "escape":
        entries["../escaped"] = b"bad"
    with zipfile.ZipFile(archive, "w") as modified:
        for name, value in entries.items():
            info = zipfile.ZipInfo(name)
            if change == "symlink" and name == "attempt.json":
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
            modified.writestr(info, value)
    with pytest.raises(support.EvidenceError):
        support.verify_artifact_archive(archive)


def test_unrecorded_standalone_module_cache_is_validated(tmp_path, environment_fixture):
    _, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    standalone = root / "lib/python3.10/site-packages/standalone.py"
    standalone.write_text("VALUE = 42\n")
    _record(root)
    before = capture(root)
    py_compile.compile(str(standalone), doraise=True)
    after = capture(root)
    caches = [r for r in after["distributions"]["demo"]["files"] if "__pycache__/standalone." in r["path"]]
    assert len(caches) == 1 and caches[0]["recorded"] is False
    assert support.require_matching_environment(before, after)["matches"]
    cache = Path(util.cache_from_source(str(standalone)))
    cache.write_bytes(cache.read_bytes()[:16] + marshal.dumps(compile("VALUE = 99\n", str(standalone), "exec")))
    with pytest.raises(support.EvidenceError, match="bytecode differs"):
        capture(root)


def test_archive_is_not_published_if_payload_changes_during_freeze(tmp_path, monkeypatch):
    root, archive = tmp_path / "evidence", tmp_path / "upload.zip"
    _evidence(root)
    regular = support._regular
    changed = False

    def mutate_after_snapshot(path, **kwargs):
        nonlocal changed
        row = regular(path, **kwargs)
        if Path(path).name == "attempt.json" and not changed:
            changed = True
            Path(path).write_bytes(Path(path).read_bytes() + b"changed after initial snapshot")
        return row

    monkeypatch.setattr(support, "_regular", mutate_after_snapshot)
    with pytest.raises(support.EvidenceError, match="grew while freezing|changed while freezing"):
        support.seal_artifact_archive(root, archive)
    assert not archive.exists()
    assert not list(tmp_path.glob("upload.zip.*"))


def test_cli_freeze_verify_and_seal(tmp_path, capsys):
    wheel = _wheel(tmp_path / "wheels")
    manifest, requirements = wheel.parent / "wheelhouse-manifest.json", wheel.parent / "requirements-hashed.txt"
    assert support.main(["freeze", "--wheelhouse", str(wheel.parent), "--output", str(manifest),
                         "--requirements", str(requirements)]) == 0
    assert requirements.read_text().startswith("demo==1.0 --hash=sha256:")
    assert support.main(["verify", "--wheelhouse", str(wheel.parent), "--manifest", str(manifest)]) == 0
    root, archive = tmp_path / "evidence", tmp_path / "upload.zip"
    _evidence(root)
    assert support.main(["seal", "--root", str(root), "--output", str(archive)]) == 0
    assert support.main(["verify-artifact", "--archive", str(archive)]) == 0
    assert support.main(["verify-artifact", "--archive", str(archive), "--sha256", "0" * 64]) == 1
    assert "sealed archive SHA256 mismatch" in capsys.readouterr().err


def test_environment_cli_persists_snapshot_and_file_diff_before_failure(tmp_path, environment_fixture):
    manifest, _, capture = environment_fixture
    root = tmp_path / "install"
    _install(root)
    capture(root)  # Select the real synthetic PathDistribution for the CLI too.
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    reference, observed, difference = (tmp_path / name for name in ("reference.json", "observed.json", "difference.json"))
    args = ["environment", "--manifest", str(manifest_path), "--source-root", str(tmp_path),
            "--source-file", "runner.py", "--install-root", str(root)]
    assert support.main([*args, "--output", str(reference)]) == 0
    native = root / "lib/python3.10/site-packages/demo/_native.so"
    native.write_bytes(b"changed binary")
    _record(root)
    assert support.main([*args, "--output", str(observed), "--reference", str(reference),
                         "--comparison-output", str(difference)]) == 1
    assert observed.is_file() and difference.is_file()
    comparison = json.loads(difference.read_text())
    assert not comparison["matches"]
    assert {"distribution": "demo", "path": "demo/_native.so"} in comparison["forbidden_file_differences"]
    assert support.main(["compare", "--reference", str(reference), "--observed", str(observed),
                         "--output", str(difference)]) == 1


def test_requirements_cannot_silently_select_a_different_install_set(tmp_path):
    wheel = _wheel(tmp_path / "wheels")
    manifest = support.freeze_wheelhouse(wheel.parent)
    requirements = wheel.parent / "requirements-hashed.txt"
    requirements.write_text("# omitted the frozen wheel\n")
    with pytest.raises(support.EvidenceError, match="hashed requirements differ"):
        support.verify_wheelhouse(wheel.parent, manifest)
    requirements.write_text(support.hashed_requirements(manifest))
    assert support.verify_wheelhouse(wheel.parent, manifest) == manifest
