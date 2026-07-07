from __future__ import annotations

from pathlib import Path
from typing import Any


class PathSafetyError(ValueError):
    """Raised when an artifact path escapes its allowed root."""


def _coerce_path(value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        raise PathSafetyError("path value is empty")
    return Path(text).expanduser()


def _within_root(root_path: Path, candidate: Path) -> bool:
    return candidate == root_path or root_path in candidate.parents


def _resolve_candidate(root_path: Path, candidate: Path) -> Path:
    if candidate.is_absolute():
        return candidate.resolve(strict=False)

    # Worker-produced status files often store paths such as
    # ``./results/<job_id>/result.json``. Preserve those cwd-relative contained
    # paths instead of incorrectly treating them as ``<job_root>/results/...``.
    cwd_relative = (Path.cwd() / candidate).resolve(strict=False)
    if _within_root(root_path, cwd_relative):
        return cwd_relative

    return (root_path / candidate).resolve(strict=False)


def resolve_under_root(
    root: str | Path,
    value: Any,
    *,
    must_exist: bool = False,
    file_required: bool = False,
) -> Path:
    """Resolve ``value`` and require it to stay under ``root``.

    Absolute paths are allowed only when their resolved location is still inside
    ``root``. Relative values can be either cwd-relative already-contained paths
    or direct paths below ``root``.
    """

    root_path = Path(root).expanduser().resolve(strict=False)
    candidate = _coerce_path(value)
    try:
        resolved = _resolve_candidate(root_path, candidate)
    except RuntimeError as exc:  # symlink loops and similar resolution errors
        raise PathSafetyError("path could not be resolved safely") from exc

    if not _within_root(root_path, resolved):
        raise PathSafetyError("path escapes allowed root")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(str(resolved))
    if file_required and not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    return resolved


def resolve_existing_file_under(root: str | Path, value: Any) -> Path:
    """Resolve an existing file while enforcing root containment."""

    return resolve_under_root(root, value, must_exist=True, file_required=True)


def is_within_root(root: str | Path, value: Any) -> bool:
    """Return True when ``value`` resolves under ``root``."""

    try:
        resolve_under_root(root, value)
    except (FileNotFoundError, PathSafetyError):
        return False
    return True


__all__ = [
    "PathSafetyError",
    "is_within_root",
    "resolve_existing_file_under",
    "resolve_under_root",
]
