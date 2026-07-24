from __future__ import annotations

from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import importlib.util
import os

import pytest

import betelgeuze_engine_v2.physics.reference_minimization_validation_bootstrap as bootstrap


_REQUIRED_SOURCE_ROWS = {
    "betelgeuze_engine_v2/__init__.py": b"\n",
    "betelgeuze_engine_v2/physics/__init__.py": b"\n",
    bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_RELATIVE_PATH: (
        b"BOOTSTRAP = 'snapshot'\n"
    ),
    bootstrap.REFERENCE_MINIMIZATION_VALIDATION_DEPENDENCY_IDENTITY_RELATIVE_PATH: (
        b"DEPENDENCY = 'snapshot'\n"
    ),
    "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py": (
        b"RUNNER = 'snapshot'\n"
    ),
}


def _write_source_tree(root: Path) -> None:
    for relative_path, payload in _REQUIRED_SOURCE_ROWS.items():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def test_package_source_snapshot_is_bounded_canonical_and_complete(
    tmp_path: Path,
) -> None:
    _write_source_tree(tmp_path)

    manifest_sha256, sources, repository_identity = (
        bootstrap._snapshot_reference_minimization_validation_sources(
            str(tmp_path)
        )
    )

    assert len(manifest_sha256) == 64
    assert isinstance(sources, MappingProxyType)
    assert dict(sources) == _REQUIRED_SOURCE_ROWS
    assert repository_identity == bootstrap._source_stat_signature(
        tmp_path.stat()
    )


def test_source_snapshot_rejects_final_source_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are unavailable")
    _write_source_tree(tmp_path)
    runner = (
        tmp_path
        / "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py"
    )
    external = tmp_path / "external.py"
    external.write_bytes(b"RUNNER = 'external'\n")
    runner.unlink()
    runner.symlink_to(external)

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="symlink|special file",
    ):
        bootstrap._snapshot_reference_minimization_validation_sources(
            str(tmp_path)
        )


def test_source_snapshot_rejects_parent_directory_symlink(tmp_path: Path) -> None:
    if not hasattr(os, "symlink"):
        pytest.skip("symbolic links are unavailable")
    outside = tmp_path / "outside"
    _write_source_tree(outside)
    package = tmp_path / "betelgeuze_engine_v2"
    package.symlink_to(outside / "betelgeuze_engine_v2", target_is_directory=True)

    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="non-directory|cannot be opened securely",
    ):
        bootstrap._snapshot_reference_minimization_validation_sources(
            str(tmp_path)
        )


def test_source_reader_detects_path_replacement_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    source.write_bytes(b"A" * (1_048_576 + 17))
    replacement = tmp_path / "replacement.py"
    replacement.write_bytes(b"B" * (1_048_576 + 17))
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_read = bootstrap.os.read
    replaced = False

    def replacing_read(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        chunk = original_read(descriptor, size)
        if chunk and not replaced:
            os.replace(replacement, source)
            replaced = True
        return chunk

    monkeypatch.setattr(bootstrap.os, "read", replacing_read)
    try:
        with pytest.raises(
            bootstrap._ReferenceMinimizationValidationBootstrapError,
            match="changed while it was read|bounded single-link",
        ):
            bootstrap._read_source_file_at(directory_fd, "source.py")
    finally:
        os.close(directory_fd)


def test_source_snapshot_detects_directory_entry_set_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = tmp_path / "betelgeuze_engine_v2"
    package.mkdir()
    (package / "__init__.py").write_bytes(b"\n")
    directory_fd = os.open(package, os.O_RDONLY | os.O_DIRECTORY)
    original_listdir = bootstrap.os.listdir
    calls = 0

    def changing_listdir(value: int) -> list[str]:
        nonlocal calls
        names = original_listdir(value)
        calls += 1
        if calls == 1:
            (package / "added.py").write_bytes(b"ADDED = True\n")
        return names

    monkeypatch.setattr(bootstrap.os, "listdir", changing_listdir)
    try:
        with pytest.raises(
            bootstrap._ReferenceMinimizationValidationBootstrapError,
            match="directory changed during snapshot",
        ):
            bootstrap._snapshot_source_directory(
                directory_fd,
                ("betelgeuze_engine_v2",),
                {},
                [0, 0],
            )
    finally:
        os.close(directory_fd)


def test_verified_loader_executes_snapshot_bytes_not_replaced_live_file(
    tmp_path: Path,
) -> None:
    package = tmp_path / "betelgeuze_engine_v2"
    package.mkdir()
    live = package / "snapshot_probe.py"
    live.write_text("VALUE = 'live-replacement'\n", encoding="utf-8")
    relative_path = "betelgeuze_engine_v2/snapshot_probe.py"
    sources = MappingProxyType(
        {relative_path: b"VALUE = 'verified-snapshot'\n"}
    )
    finder = bootstrap._VerifiedSourceFinder(
        str(tmp_path),
        "a" * 64,
        sources,
        bootstrap._source_stat_signature(tmp_path.stat()),
    )

    spec = finder.find_spec("betelgeuze_engine_v2.snapshot_probe")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.VALUE == "verified-snapshot"
    assert live.read_text(encoding="utf-8") == "VALUE = 'live-replacement'\n"


def test_verified_finder_refuses_engine_module_missing_from_snapshot(
    tmp_path: Path,
) -> None:
    finder = bootstrap._VerifiedSourceFinder(
        str(tmp_path),
        "b" * 64,
        MappingProxyType(
            {"betelgeuze_engine_v2/__init__.py": b"\n"}
        ),
        bootstrap._source_stat_signature(tmp_path.stat()),
    )

    with pytest.raises(ModuleNotFoundError, match="verified source snapshot"):
        finder.find_spec("betelgeuze_engine_v2.not_verified")


def test_source_finder_install_rejects_preloaded_engine_package(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        bootstrap._ReferenceMinimizationValidationBootstrapError,
        match="imported before source verification",
    ):
        bootstrap._install_verified_source_finder(
            str(tmp_path),
            "c" * 64,
            MappingProxyType(
                {"betelgeuze_engine_v2/__init__.py": b"\n"}
            ),
            bootstrap._source_stat_signature(tmp_path.stat()),
        )


def test_dependency_measurement_helper_is_executed_from_verified_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        artifact_id: character * 64
        for artifact_id, character in zip(
            bootstrap._REFERENCE_MINIMIZATION_VALIDATION_REQUIRED_DEPENDENCY_ARTIFACT_IDS,
            "abcdef",
            strict=True,
        )
    }
    helper_source = (
        "def observed_reference_minimization_validation_dependency_artifact_sha256_rows(roots):\n"
        f"    return {expected!r}\n"
    ).encode("utf-8")
    finder = SimpleNamespace(
        repository_root="/verified/repository",
        source_bytes_for_relative_path=lambda relative_path: helper_source,
    )
    monkeypatch.setattr(
        bootstrap, "_require_verified_source_finder", lambda: finder
    )

    bootstrap._require_observed_dependency_artifact_rows_before_import(
        "/verified/repository",
        ("/trusted/dependencies",),
        {"expected_dependency_artifact_sha256_rows": dict(expected)},
        signed_expected=expected,
    )
