from __future__ import annotations

from pathlib import Path

from tools.check_repository_hygiene import (
    MAX_CHANGED_FILE_BYTES,
    audit_repository_paths,
    classify_changed_path,
)


def _sizes(values: dict[str, int]):
    return lambda path: values.get(path, 0)


def test_tracked_local_harness_state_is_always_rejected() -> None:
    violations = audit_repository_paths(
        tracked_paths=["README.md", ".betelgeuze/state.md", ".betelgeuze/run_log.md"],
        changed_paths=[],
        size_lookup=_sizes({}),
    )
    assert violations == [
        ".betelgeuze/run_log.md:forbidden_local_operational_state_tracked",
        ".betelgeuze/state.md:forbidden_local_operational_state_tracked",
    ]


def test_incremental_generated_and_local_roots_are_rejected() -> None:
    changed = [
        ".betelgeuze/session.json",
        "runs/new_current.json",
        "results/result.json",
        "models/checkpoint.bin",
        "runtime/cache/index.json",
    ]
    violations = audit_repository_paths(
        tracked_paths=[],
        changed_paths=changed,
        size_lookup=_sizes({}),
    )
    assert violations == [
        f"{path}:generated_or_local_root_forbidden"
        for path in sorted(changed)
    ]


def test_source_and_small_text_fixture_paths_are_allowed() -> None:
    for path in (
        "api/main.py",
        "config/independent_engine_v2_capabilities.yaml",
        "docs/architecture.md",
        "tests/fixtures/example/output.log",
        "tests/fixtures/example/tiny.npz",
    ):
        assert classify_changed_path(path, size_bytes=1024) == []


def test_generated_suffix_is_rejected_outside_fixtures() -> None:
    assert classify_changed_path("docs/debug.log", size_bytes=12) == [
        "generated_binary_or_log_suffix_forbidden"
    ]
    assert classify_changed_path("config/model.onnx", size_bytes=12) == [
        "generated_binary_or_log_suffix_forbidden"
    ]


def test_large_file_and_symlink_are_rejected() -> None:
    assert classify_changed_path(
        "tests/fixtures/large.bin",
        size_bytes=MAX_CHANGED_FILE_BYTES + 1,
        is_symlink=True,
    ) == ["changed_file_exceeds_10_mib", "changed_symlink_forbidden"]


def test_current_repository_no_longer_unignores_local_state() -> None:
    ignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".betelgeuze/" in ignore
    assert "!.betelgeuze/state.md" not in ignore
    assert "!.betelgeuze/run_log.md" not in ignore
    assert not Path(".betelgeuze/state.md").exists()
    assert not Path(".betelgeuze/run_log.md").exists()
