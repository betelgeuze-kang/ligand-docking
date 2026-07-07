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


def resolve_under_root(
    root: str | Path,
    value: Any,
    *,
    must_exist: bool = False,
    file_required: bool = False,
) -> Path:
    """Resolve ``value`` and require it to stay under ``root``.

    Relative paths are interpreted relative to ``root``. Absolute paths are
    allowed only when their resolved location is still inside ``root``. The
    helper is intentionally small and dependency-free so API endpoints, worker
    finalizers, and tests can share the same containment semantics.
    """

    root_path = Path(root).expanduser().resolve(strict=False)
    candidate = _coerce_path(value)
    if not candidate.is_absolute():
        candidate = root_path / candidate
    try:
        resolved = candidate.resolve(strict=must_exist)
    except FileNotFoundError:
        raise
    except RuntimeError as exc:  # symlink loops and similar resolution errors
        raise PathSafetyError("path could not be resolved safely") from exc

    if resolved != root_path and root_path not in resolved.parents:
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
