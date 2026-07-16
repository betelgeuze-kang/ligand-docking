#!/usr/bin/env python3
"""Incremental repository hygiene policy for reviewed source changes.

The repository has a long history containing generated evidence and operational
artifacts. This checker does not retroactively fail every historical path. It
blocks new or modified generated/local artifacts and permanently forbids the two
previously tracked local harness state files.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Callable, Iterable, Sequence

MAX_CHANGED_FILE_BYTES = 10 * 1024 * 1024
FORBIDDEN_TRACKED_PATHS = {
    ".betelgeuze/state.md",
    ".betelgeuze/run_log.md",
}
GENERATED_ROOTS = (
    ".betelgeuze/",
    "archives/",
    "build/",
    "data/",
    "dist/",
    "logs/",
    "models/",
    "output/",
    "results/",
    "runs/",
    "runtime/cache/",
    "rust_engine/target/",
    "target/",
    "test-results/",
    "tmp/",
)
GENERATED_SUFFIXES = (
    ".h5",
    ".log",
    ".npz",
    ".onnx",
    ".pt",
    ".pth",
    ".tar.gz",
    ".tar.zst",
)
FIXTURE_ROOT = "tests/fixtures/"


def _normalize_path(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return PurePosixPath(text).as_posix() if text else ""


def classify_changed_path(
    path: str,
    *,
    size_bytes: int,
    is_symlink: bool = False,
) -> list[str]:
    """Return deterministic violation codes for one added/modified path."""

    normalized = _normalize_path(path)
    reasons: list[str] = []
    if not normalized or normalized == "." or normalized.startswith("../"):
        reasons.append("invalid_repository_path")
        return reasons
    if normalized.startswith("/"):
        reasons.append("absolute_repository_path")
    if is_symlink:
        reasons.append("changed_symlink_forbidden")
    if any(normalized == root.rstrip("/") or normalized.startswith(root) for root in GENERATED_ROOTS):
        reasons.append("generated_or_local_root_forbidden")
    lowered = normalized.lower()
    if not normalized.startswith(FIXTURE_ROOT) and any(
        lowered.endswith(suffix) for suffix in GENERATED_SUFFIXES
    ):
        reasons.append("generated_binary_or_log_suffix_forbidden")
    if int(size_bytes) > MAX_CHANGED_FILE_BYTES:
        reasons.append("changed_file_exceeds_10_mib")
    return sorted(set(reasons))


def audit_repository_paths(
    *,
    tracked_paths: Iterable[str],
    changed_paths: Iterable[str],
    size_lookup: Callable[[str], int],
    symlink_lookup: Callable[[str], bool] | None = None,
) -> list[str]:
    """Audit fixed tracked-state blockers and incremental changed-path policy."""

    tracked = {_normalize_path(path) for path in tracked_paths}
    violations = [
        f"{path}:forbidden_local_operational_state_tracked"
        for path in sorted(FORBIDDEN_TRACKED_PATHS & tracked)
    ]
    is_symlink = symlink_lookup or (lambda _path: False)
    for path in sorted({_normalize_path(value) for value in changed_paths if _normalize_path(value)}):
        for reason in classify_changed_path(
            path,
            size_bytes=int(size_lookup(path)),
            is_symlink=bool(is_symlink(path)),
        ):
            violations.append(f"{path}:{reason}")
    return sorted(set(violations))


def _git(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _nul_paths(payload: bytes) -> list[str]:
    return [
        item.decode("utf-8", errors="strict")
        for item in payload.split(b"\0")
        if item
    ]


def _valid_commit(root: Path, ref: str) -> bool:
    if not ref or set(ref) == {"0"}:
        return False
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{ref}^{{commit}}"],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def _fallback_base(root: Path, head: str) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", f"{head}^"],
        cwd=root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def changed_paths(root: Path, *, base: str | None, head: str) -> list[str]:
    """Return added/copied/modified/renamed paths for the reviewed range."""

    resolved_base = base if base and _valid_commit(root, base) else _fallback_base(root, head)
    if resolved_base and _valid_commit(root, resolved_base):
        return _nul_paths(
            _git(
                root,
                "diff",
                "--name-only",
                "--diff-filter=ACMR",
                "-z",
                resolved_base,
                head,
            )
        )
    return _nul_paths(_git(root, "ls-tree", "-r", "--name-only", "-z", head))


def _working_tree_size(root: Path, path: str) -> int:
    candidate = root / Path(path)
    try:
        return int(candidate.lstat().st_size)
    except FileNotFoundError:
        return 0


def _working_tree_symlink(root: Path, path: str) -> bool:
    return (root / Path(path)).is_symlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository working tree")
    parser.add_argument("--base", default="", help="review range base commit")
    parser.add_argument("--head", default="HEAD", help="review range head commit")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    tracked = _nul_paths(_git(root, "ls-files", "-z"))
    changed = changed_paths(root, base=str(args.base or ""), head=str(args.head or "HEAD"))
    violations = audit_repository_paths(
        tracked_paths=tracked,
        changed_paths=changed,
        size_lookup=lambda path: _working_tree_size(root, path),
        symlink_lookup=lambda path: _working_tree_symlink(root, path),
    )
    print(f"repository_hygiene_tracked_count={len(tracked)}")
    print(f"repository_hygiene_changed_count={len(changed)}")
    if violations:
        print("repository_hygiene_status=blocked")
        for violation in violations:
            print(f"violation={violation}")
        return 1
    print("repository_hygiene_status=pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
