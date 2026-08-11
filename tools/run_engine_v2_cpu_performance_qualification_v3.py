#!/usr/bin/env python3
"""Verify, replay, or transactionally execute CPU qualification profile v3."""

# ruff: noqa: E402 -- isolated live execution checks precede non-built-in imports.

from __future__ import annotations

import posix
import sys


_STDLIB_ZIP_PATH = "/usr/lib/python310.zip"
_LIVE_REQUESTED = any(
    argument == "--run-output" or argument.startswith("--run-output=")
    for argument in sys.argv[1:]
)
_ISOLATED_REQUESTED = sys.flags.isolated == 1 or sys.flags.no_site == 1
if _LIVE_REQUESTED or _ISOLATED_REQUESTED:
    try:
        posix.lstat(_STDLIB_ZIP_PATH)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RuntimeError(
            "CPU qualification v3 bootstrap rejected runtime: "
            "isolated standard-library zip state is ambiguous"
        ) from exc
    else:
        raise RuntimeError(
            "CPU qualification v3 bootstrap rejected runtime: "
            "isolated standard-library zip must be absent"
        )

import argparse
import importlib
import importlib.machinery
import json
import os
from pathlib import Path
import stat
import types
from typing import NoReturn, Sequence


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
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> NoReturn:
    raise RuntimeError(f"CPU qualification v3 bootstrap rejected runtime: {message}")


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
            chunk = os.read(
                descriptor,
                min(1 << 20, 4 * 1024 * 1024 + 1 - observed),
            )
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


def _load_source_module(name: str, path: Path) -> types.ModuleType:
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
    return module


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
    raw = _read_owner_controlled_source(
        path,
        name="qualification virtual-environment configuration",
    )
    if len(raw) != metadata.st_size:
        _fail("virtual-environment configuration changed while it was read")
    return raw


def _load_isolated_qualification_module() -> types.ModuleType:
    if tuple(sys.path) != _EXPECTED_INITIAL_PATHS:
        _fail("isolated standard-library path set changed")
    _require_absent_path(_STDLIB_ZIP_PATH, name="isolated standard-library zip")
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
    _read_owner_controlled_source(bootstrap_path, name="qualification v3 bootstrap")

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
        "performance_host_preflight_v3",
        "performance_qualification_v3",
    ):
        _load_source_module(
            f"betelgeuze_engine_v2.docking.{module_name}",
            docking_root / f"{module_name}.py",
        )
    return sys.modules[
        "betelgeuze_engine_v2.docking.performance_qualification_v3"
    ]


def _load_qualification_module() -> types.ModuleType:
    if _LIVE_REQUESTED and os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        _fail("GitHub Actions cannot execute the live v3 qualification")
    if _LIVE_REQUESTED and not _ISOLATED_REQUESTED:
        _fail("live execution requires CPython -I -S -B")
    if _LIVE_REQUESTED or _ISOLATED_REQUESTED:
        return _load_isolated_qualification_module()
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    return importlib.import_module(
        "betelgeuze_engine_v2.docking.performance_qualification_v3"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-activation", action="store_true")
    parser.add_argument("--verify-artifact", type=Path)
    parser.add_argument("--run-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    selected = sum(
        (
            bool(arguments.verify_activation),
            arguments.verify_artifact is not None,
            arguments.run_output is not None,
        )
    )
    module = _load_qualification_module()
    if selected != 1:
        raise module.CPUPerformanceQualificationV3Error(
            "select exactly one public v3 operation"
        )
    activation = dict(module.verify_runner_activation_contract())
    if arguments.verify_activation:
        output: dict[str, object] = {
            **activation,
            "execution_attested": False,
            "verification_only": True,
        }
    elif arguments.verify_artifact is not None:
        verified = module.read_cpu_performance_artifact_v3(
            arguments.verify_artifact
        )
        output = {
            "authority": activation["authority"],
            "execution_attested": False,
            "live_run_capability": verified.live_run_capability,
            "local_numeric_gate_eligible": verified.local_numeric_gate_eligible,
            "offline_replay_only": verified.offline_replay_only,
            "qualification_authority": verified.qualification_authority,
            "recorded_decision": verified.recorded_decision,
            "recorded_numeric_gate_passed": verified.recorded_numeric_gate_passed,
            "structural_integrity_verified": True,
            "verification_blockers": list(verified.verification_blockers),
        }
    else:
        result = module.run_sealed_local_performance_runner_v3(
            arguments.run_output
        )
        output = {
            "artifact": str(result.artifact_path),
            "artifact_sha256": result.artifact_sha256,
            "attempt_ledger": str(result.attempt_ledger_path),
            "authority": activation["authority"],
            "blockers": list(result.blockers),
            "execution_attested": result.execution_attested,
            "live_run_capability": result.live_run_capability,
            "qualification_authority": result.qualification_authority,
            "recorded_decision": result.recorded_decision,
            "recorded_numeric_gate_passed": result.recorded_numeric_gate_passed,
            "terminal_state": str(result.terminal_state_path),
            "terminal_state_sha256": result.terminal_state_sha256,
        }
    print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
