#!/usr/bin/env python3
"""Stdlib-only bootstrap for the synthetic CPU performance sidecar.

The regular package initializers intentionally expose the full development
surface and therefore import optional scientific dependencies.  Qualification
must instead enter through this tiny, source-bound loader so that only the
repository source tree and one clean virtual-environment site-packages root are
added *after* the isolated interpreter's standard-library paths.
"""

# ruff: noqa: E402 -- the zip-absence check must precede non-built-in imports.

from __future__ import annotations

import posix
import sys


_STDLIB_ZIP_PATH = "/usr/lib/python310.zip"
try:
    posix.lstat(_STDLIB_ZIP_PATH)
except FileNotFoundError:
    pass
except OSError as exc:
    raise RuntimeError(
        "CPU qualification bootstrap rejected runtime: "
        "isolated standard-library zip state is ambiguous"
    ) from exc
else:
    raise RuntimeError(
        "CPU qualification bootstrap rejected runtime: "
        "isolated standard-library zip must be absent"
    )

import importlib.machinery
import os
from pathlib import Path
import stat
import types
from typing import NoReturn


_EXPECTED_INITIAL_PATHS = (
    _STDLIB_ZIP_PATH,
    "/usr/lib/python3.10",
    "/usr/lib/python3.10/lib-dynload",
)
_EXPECTED_VENV_CONFIGURATION = (
    b"home = /usr/bin\n"
    b"include-system-site-packages = false\n"
    b"version = 3.10.12\n"
)


def _fail(message: str) -> NoReturn:
    raise RuntimeError(f"CPU qualification bootstrap rejected runtime: {message}")


def _require_owner_controlled_directory(path: Path, *, name: str) -> Path:
    try:
        unresolved = path.absolute()
        resolved = path.resolve(strict=True)
        metadata = unresolved.lstat()
    except OSError as exc:
        raise RuntimeError(f"{name} is unavailable") from exc
    if unresolved != resolved or not stat.S_ISDIR(metadata.st_mode):
        _fail(f"{name} must be a real directory without symlinks")
    if metadata.st_uid != os.geteuid():
        _fail(f"{name} owner changed")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        _fail(f"{name} is writable by another principal")
    return resolved


def _require_absent_path(path: str, *, name: str) -> None:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise RuntimeError(f"{name} state is ambiguous") from exc
    _fail(f"{name} must be absent")


def _read_owner_controlled_source(path: Path, *, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"{name} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or before.st_nlink != 1
            or not 1 <= before.st_size <= 4 * 1024 * 1024
        ):
            _fail(f"{name} is not an owner-controlled bounded source file")
        chunks: list[bytes] = []
        observed = 0
        while observed <= 4 * 1024 * 1024:
            chunk = os.read(descriptor, min(1 << 20, 4 * 1024 * 1024 + 1 - observed))
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in identity
        ):
            _fail(f"{name} changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _install_package_stub(name: str, path: Path) -> None:
    module = types.ModuleType(name)
    module.__file__ = str(path / "__init__.py")
    module.__package__ = name
    module.__path__ = [str(path)]
    module.__spec__ = importlib.machinery.ModuleSpec(
        name=name,
        loader=None,
        is_package=True,
    )
    sys.modules[name] = module


def _load_source_module(name: str, path: Path) -> None:
    raw = _read_owner_controlled_source(path, name=name)
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__package__ = name.rpartition(".")[0]
    module.__loader__ = None
    module.__spec__ = importlib.machinery.ModuleSpec(name=name, loader=None)
    sys.modules[name] = module
    try:
        code = compile(raw, str(path), "exec", dont_inherit=True, optimize=0)
        exec(code, module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise


def _read_venv_configuration(path: Path) -> bytes:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RuntimeError("qualification virtual environment is unavailable") from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_uid != os.geteuid()
        or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        or metadata.st_nlink != 1
        or not 1 <= metadata.st_size <= 4096
    ):
        _fail("virtual-environment configuration is not a bounded owned file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RuntimeError("qualification virtual environment is unavailable") from exc
    try:
        after = path.lstat()
    except OSError as exc:
        raise RuntimeError("qualification virtual environment is unavailable") from exc
    stable_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if len(raw) != metadata.st_size or any(
        getattr(metadata, field) != getattr(after, field) for field in stable_fields
    ):
        _fail("virtual-environment configuration changed while it was read")
    return raw


def main() -> int:
    if tuple(sys.path) != _EXPECTED_INITIAL_PATHS:
        _fail("isolated standard-library path set changed")
    _require_absent_path(
        _STDLIB_ZIP_PATH,
        name="isolated standard-library zip",
    )
    if not (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.flags.no_user_site == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.hash_randomization == 1
    ):
        _fail("effective interpreter flags changed")
    if hasattr(sys.flags, "safe_path"):
        _fail("unexpected safe_path field appeared in the pinned CPython lane")

    bootstrap_path = Path(__file__).absolute()
    repository_root = _require_owner_controlled_directory(
        bootstrap_path.parent.parent,
        name="repository root",
    )
    tools_root = _require_owner_controlled_directory(
        repository_root / "tools",
        name="repository tools root",
    )
    if bootstrap_path.parent != tools_root:
        _fail("qualification bootstrap escaped the repository tools root")
    _read_owner_controlled_source(
        bootstrap_path,
        name="qualification bootstrap",
    )
    launcher = Path(sys.executable).absolute()
    virtual_environment_root = _require_owner_controlled_directory(
        launcher.parent.parent,
        name="qualification virtual environment",
    )
    if launcher.parent != virtual_environment_root / "bin":
        _fail("Python launcher is outside the qualification virtual environment")
    _require_owner_controlled_directory(
        virtual_environment_root / "bin",
        name="qualification virtual-environment bin",
    )
    _require_owner_controlled_directory(
        virtual_environment_root / "lib",
        name="qualification virtual-environment lib",
    )
    _require_owner_controlled_directory(
        virtual_environment_root / "lib/python3.10",
        name="qualification virtual-environment Python root",
    )
    configuration = virtual_environment_root / "pyvenv.cfg"
    if _read_venv_configuration(configuration) != _EXPECTED_VENV_CONFIGURATION:
        _fail("virtual-environment configuration changed")
    site_packages = _require_owner_controlled_directory(
        virtual_environment_root / "lib/python3.10/site-packages",
        name="qualification site-packages",
    )

    # Appending keeps the frozen stdlib ahead of mutable application roots.
    sys.path.extend((str(repository_root), str(site_packages)))
    package_root = repository_root / "betelgeuze_engine_v2"
    docking_root = package_root / "docking"
    _require_owner_controlled_directory(package_root, name="Engine V2 package root")
    _require_owner_controlled_directory(docking_root, name="Engine V2 docking root")
    _install_package_stub("betelgeuze_engine_v2", package_root)
    _install_package_stub("betelgeuze_engine_v2.docking", docking_root)

    for module_name in (
        "mixed64_allocation",
        "geometric_admission_v2",
        "performance_sidecar",
    ):
        _load_source_module(
            f"betelgeuze_engine_v2.docking.{module_name}",
            docking_root / f"{module_name}.py",
        )
    module = sys.modules["betelgeuze_engine_v2.docking.performance_sidecar"]
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
