"""Stdlib-only bootstrap for the bounded reference-validation process.

This file is executed directly, before importing the Engine v2 package.  The
frozen command uses isolated Python startup with automatic ``site`` loading
disabled, so ``PYTHONPATH``, user-site packages, ``sitecustomize``, and ``.pth``
files cannot run before the validation trust boundary is established.
"""

from __future__ import annotations

import os
import stat
import sys
import sysconfig


REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH = (
    "betelgeuze_engine_v2/physics/reference_validation_bootstrap.py"
)
REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV = (
    "python",
    "-I",
    "-S",
    "-B",
    "-X",
    "pycache_prefix=/dev/null",
    REFERENCE_VALIDATION_BOOTSTRAP_RELATIVE_PATH,
)
REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE = (
    "_betelgeuze_reference_validation_bootstrap_state"
)


class _ReferenceValidationBootstrapError(RuntimeError):
    """The interpreter did not establish the frozen import boundary."""


def reference_validation_bootstrap_path() -> str:
    """Return the canonical checked-out bootstrap path."""

    return os.path.realpath(__file__)


def _require_root_owned_read_only_directory(raw_path: str) -> str:
    if not raw_path or not os.path.isabs(raw_path) or os.pathsep in raw_path:
        raise _ReferenceValidationBootstrapError("bootstrap path is invalid")
    resolved = os.path.realpath(raw_path)
    if resolved != os.path.abspath(raw_path):
        raise _ReferenceValidationBootstrapError("bootstrap path is not canonical")
    current = resolved
    while current != os.path.dirname(current):
        try:
            file_stat = os.lstat(current)
        except OSError as exc:
            raise _ReferenceValidationBootstrapError(
                "bootstrap path is unavailable"
            ) from exc
        if (
            not stat.S_ISDIR(file_stat.st_mode)
            or file_stat.st_uid != 0
            or stat.S_IMODE(file_stat.st_mode) & 0o022
        ):
            raise _ReferenceValidationBootstrapError(
                "bootstrap path is not root-owned read-only storage"
            )
        current = os.path.dirname(current)
    return resolved


def _trusted_standard_library_roots() -> tuple[str, ...]:
    roots: list[str] = []
    for raw_path in sys.path:
        if not raw_path or not os.path.isdir(raw_path):
            continue
        resolved = _require_root_owned_read_only_directory(raw_path)
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceValidationBootstrapError(
            "trusted standard-library roots are unavailable"
        )
    return tuple(roots)


def _trusted_dependency_roots() -> tuple[str, ...]:
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    configured = sysconfig.get_paths()
    candidates = (
        configured.get("purelib"),
        configured.get("platlib"),
        f"/usr/local/lib/{version}/site-packages",
        f"/usr/local/lib/{version}/dist-packages",
        f"/usr/lib/{version}/site-packages",
        f"/usr/lib/{version}/dist-packages",
        "/usr/lib/python3/dist-packages",
    )
    roots: list[str] = []
    for raw_path in candidates:
        if not isinstance(raw_path, str) or not os.path.isdir(raw_path):
            continue
        try:
            resolved = _require_root_owned_read_only_directory(raw_path)
        except _ReferenceValidationBootstrapError:
            continue
        if resolved not in roots:
            roots.append(resolved)
    if not roots:
        raise _ReferenceValidationBootstrapError(
            "trusted dependency roots are unavailable"
        )
    return tuple(roots)


def _prepare_isolated_import_boundary() -> None:
    expected_bootstrap = reference_validation_bootstrap_path()
    try:
        bootstrap_stat = os.lstat(__file__)
    except OSError as exc:
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap source is unavailable"
        ) from exc
    if (
        os.path.abspath(__file__) != expected_bootstrap
        or not stat.S_ISREG(bootstrap_stat.st_mode)
        or bootstrap_stat.st_nlink != 1
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap source is not a canonical regular file"
        )
    expected_tail = (
        *REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV[1:-1],
        expected_bootstrap,
    )
    observed_argv = tuple(getattr(sys, "orig_argv", ()))
    if (
        len(observed_argv) != len(REFERENCE_VALIDATION_LOGICAL_RUNNER_ARGV)
        or observed_argv[1:] != expected_tail
        or sys.argv != [expected_bootstrap]
        or sys.flags.isolated != 1
        or sys.flags.ignore_environment != 1
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.dont_write_bytecode is not True
        or sys.pycache_prefix != "/dev/null"
    ):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap requires the frozen isolated Python command"
        )

    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(expected_bootstrap))
    )
    package_root = os.path.join(repository_root, "betelgeuze_engine_v2")
    if not os.path.isdir(package_root):
        raise _ReferenceValidationBootstrapError(
            "validation bootstrap checkout is unavailable"
        )
    standard_library_roots = _trusted_standard_library_roots()
    dependency_roots = _trusted_dependency_roots()
    sanitized_path = (
        repository_root,
        *standard_library_roots,
        *dependency_roots,
    )
    sys.path[:] = list(dict.fromkeys(sanitized_path))
    state = (
        expected_bootstrap,
        repository_root,
        dependency_roots,
        tuple(sys.path),
    )
    setattr(sys, REFERENCE_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, state)


def main() -> int:
    """Establish the import boundary and delegate canonical stdin handling."""

    try:
        _prepare_isolated_import_boundary()
        from betelgeuze_engine_v2.physics import reference_validation_runner

        return reference_validation_runner._main_from_standard_streams()
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
