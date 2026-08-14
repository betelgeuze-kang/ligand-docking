#!/usr/bin/env python3
"""Run the exact-runtime, non-consuming full-pipeline CPU activation preflight."""

# ruff: noqa: E402 -- repository modules are loaded only after isolation checks.

from __future__ import annotations

import argparse
import grp
import importlib
import importlib.machinery
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import types
from typing import NoReturn, Sequence


_EXPECTED_INITIAL_PATHS = (
    "/usr/lib/python310.zip",
    "/usr/lib/python3.10",
    "/usr/lib/python3.10/lib-dynload",
)
_STDLIB_ZIP_PATH = Path(_EXPECTED_INITIAL_PATHS[0])
_EXPECTED_VENV_CONFIGURATION = (
    b"home = /usr/bin\n"
    b"include-system-site-packages = false\n"
    b"version = 3.10.12\n"
)
_MAX_SOURCE_BYTES = 4 * 1024 * 1024


def _fail(message: str) -> NoReturn:
    raise RuntimeError(
        "full-pipeline CPU activation preflight rejected runtime: " + message
    )


def _require_private_effective_group() -> None:
    try:
        account = pwd.getpwuid(os.geteuid())
        group = grp.getgrgid(os.getegid())
        primary_accounts = tuple(
            entry.pw_name for entry in pwd.getpwall() if entry.pw_gid == os.getegid()
        )
    except KeyError:
        _fail("effective account or group identity is unavailable")
    if (
        account.pw_gid != os.getegid()
        or primary_accounts != (account.pw_name,)
        or any(name != account.pw_name for name in group.gr_mem)
    ):
        _fail("effective account group is not private")


def _require_isolated_bootstrap() -> None:
    if tuple(sys.path) != _EXPECTED_INITIAL_PATHS:
        _fail("isolated standard-library path set changed")
    try:
        _STDLIB_ZIP_PATH.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise RuntimeError("isolated standard-library zip state is ambiguous") from exc
    else:
        _fail("isolated standard-library zip must be absent")
    if not (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.flags.no_user_site == 1
        and sys.flags.dont_write_bytecode == 1
        and sys.flags.hash_randomization == 1
    ):
        _fail("preflight requires exact CPython -I -S -B flags")
    if hasattr(sys.flags, "safe_path"):
        _fail("unexpected safe_path field appeared in the pinned CPython lane")
    if os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        _fail("GitHub Actions cannot run the exact-runtime activation preflight")
    _require_private_effective_group()


def _require_owner_directory(path: Path, *, name: str) -> Path:
    try:
        unresolved = path.absolute()
        resolved = path.resolve(strict=True)
        metadata = unresolved.lstat()
    except OSError as exc:
        raise RuntimeError(f"{name} is unavailable") from exc
    if unresolved != resolved or not stat.S_ISDIR(metadata.st_mode):
        _fail(f"{name} must be a real directory without symlinks")
    if (
        metadata.st_uid != os.geteuid()
        or metadata.st_gid != os.getegid()
        or metadata.st_mode & stat.S_IWOTH
    ):
        _fail(f"{name} is not account-controlled")
    return resolved


def _read_owner_source(path: Path, *, name: str) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        _fail("safe no-follow source reads are unavailable")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RuntimeError(f"{name} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or before.st_gid != os.getegid()
            or before.st_mode & stat.S_IWOTH
            or before.st_nlink != 1
            or not 1 <= before.st_size <= _MAX_SOURCE_BYTES
        ):
            _fail(f"{name} is not an owner-controlled bounded source file")
        chunks: list[bytes] = []
        observed = 0
        while observed <= _MAX_SOURCE_BYTES:
            chunk = os.read(
                descriptor,
                min(1 << 20, _MAX_SOURCE_BYTES + 1 - observed),
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
            _fail(f"{name} changed while read")
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
    existing = sys.modules.get(name)
    if isinstance(existing, types.ModuleType):
        return existing
    raw = _read_owner_source(path, name=name)
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


def _require_runtime_root(runtime_root: Path) -> tuple[Path, Path]:
    runtime_root = _require_owner_directory(runtime_root, name="native runtime root")
    launcher = Path(sys.executable).absolute()
    if launcher.parent.parent != runtime_root:
        _fail("running interpreter is outside the supplied native runtime root")
    configuration = _read_owner_source(
        runtime_root / "pyvenv.cfg",
        name="native runtime virtual-environment configuration",
    )
    if configuration != _EXPECTED_VENV_CONFIGURATION:
        _fail("native runtime virtual-environment configuration changed")
    site_packages = _require_owner_directory(
        runtime_root / "lib/python3.10/site-packages",
        name="native runtime site-packages",
    )
    if launcher.parent != runtime_root / "bin":
        _fail("native runtime launcher escaped the runtime bin directory")
    if launcher.resolve(strict=True) != Path("/usr/bin/python3.10"):
        _fail("native runtime launcher target changed")
    return runtime_root, site_packages


def _load_bound_modules(
    *, repository_root: Path, site_packages: Path
) -> dict[str, types.ModuleType]:
    package_root = _require_owner_directory(
        repository_root / "betelgeuze_engine_v2",
        name="Engine V2 package root",
    )
    docking_root = _require_owner_directory(
        package_root / "docking",
        name="Engine V2 docking root",
    )
    tools_root = _require_owner_directory(
        repository_root / "tools",
        name="repository tools root",
    )
    sys.path.extend((str(repository_root), str(site_packages)))
    _install_package_stub("betelgeuze_engine_v2", package_root)
    _install_package_stub("betelgeuze_engine_v2.docking", docking_root)
    _install_package_stub("tools", tools_root)
    modules: dict[str, types.ModuleType] = {}
    for short_name in (
        "full_pipeline_cpu_performance_v1_activation",
        "full_pipeline_cpu_performance_v1",
        "native_fixed64_consumers",
        "native_cpu_parity",
        "performance_sidecar",
        "performance_host_preflight_v3",
    ):
        qualified = f"betelgeuze_engine_v2.docking.{short_name}"
        modules[short_name] = _load_source_module(
            qualified,
            docking_root / f"{short_name}.py",
        )
    modules["activation_verifier"] = _load_source_module(
        "tools.verify_engine_v2_full_pipeline_cpu_performance_v1_activation",
        tools_root
        / "verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py",
    )
    return modules


def _require_native_extension(site_packages: Path) -> types.ModuleType:
    try:
        native = importlib.import_module("betelgeuze_engine_v2_native")
    except (ImportError, OSError):
        _fail("exact native extension cannot be initialized")
    raw_path = getattr(native, "__file__", None)
    if type(raw_path) is not str:
        _fail("native extension module path is absent")
    try:
        path = Path(raw_path).resolve(strict=True)
        path.relative_to(site_packages)
    except (OSError, ValueError):
        _fail("native extension escaped the exact runtime site-packages")
    for name in (
        "native_fixed64_prepare_repository_synthetic_d0_session_v1",
        "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
    ):
        if not callable(getattr(native, name, None)):
            _fail(f"exact native extension lacks required entrypoint {name}")
    return native


def derive_preflight(
    *,
    artifact_directory: Path,
    runtime_root: Path,
) -> dict[str, object]:
    """Inspect exact bytes and imports without creating an execution attempt."""

    _require_isolated_bootstrap()
    bootstrap = Path(__file__).absolute()
    repository_root = _require_owner_directory(
        bootstrap.parent.parent,
        name="repository root",
    )
    if bootstrap.parent != repository_root / "tools":
        _fail("activation preflight bootstrap escaped repository tools")
    _read_owner_source(bootstrap, name="activation preflight bootstrap")
    runtime_root, site_packages = _require_runtime_root(runtime_root)
    modules = _load_bound_modules(
        repository_root=repository_root,
        site_packages=site_packages,
    )
    verifier = modules["activation_verifier"]
    static_result = verifier.verify(repository_root=repository_root)
    measurement = modules["full_pipeline_cpu_performance_v1"]
    runtime_evidence = measurement.verify_local_runtime_binding(
        artifact_directory=artifact_directory,
        runtime_root=runtime_root,
    ).to_dict()
    _require_native_extension(site_packages)
    host = modules["performance_host_preflight_v3"].derive_host_preflight_evidence_v3()
    host_document = host.to_dict()

    activation = modules["full_pipeline_cpu_performance_v1_activation"]
    observed_stdlib = activation.derive_stdlib_import_closure()
    observed_dynamic = activation.derive_dynamic_library_closure(
        site_packages=site_packages
    )
    expected_stdlib = verifier.load_closure_manifest(
        repository_root
        / "config/engine_v2_full_pipeline_cpu_performance_v1_stdlib_closure.json",
        expected_schema_id=activation.STDLIB_CLOSURE_SCHEMA_ID,
    )[0]
    expected_dynamic = verifier.load_closure_manifest(
        repository_root
        / "config/engine_v2_full_pipeline_cpu_performance_v1_dynamic_library_closure.json",
        expected_schema_id=activation.DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
    )[0]
    activation.require_exact_closure(
        observed_stdlib,
        expected_stdlib,
        name="standard-library import closure",
    )
    activation.require_exact_closure(
        observed_dynamic,
        expected_dynamic,
        name="dynamic-library closure",
    )
    blockers = tuple(str(value) for value in host_document["blockers"])
    evidence = activation.ActivationPreflightEvidenceV1(
        activation_sha256=str(static_result["activation_sha256"]),
        profile_sha256=str(static_result["profile_sha256"]),
        stdlib_import_closure_manifest_sha256=str(
            static_result["stdlib_import_closure_manifest_sha256"]
        ),
        dynamic_library_closure_manifest_sha256=str(
            static_result["dynamic_library_closure_manifest_sha256"]
        ),
        host_preflight=host_document,
        blockers=blockers,
    ).to_dict()
    evidence["artifact_and_runtime_verified"] = bool(
        runtime_evidence["artifact_and_runtime_verified"]
    )
    evidence["native_extension_sha256"] = runtime_evidence[
        "native_extension_sha256"
    ]
    evidence["native_entrypoints_verified"] = True
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-directory", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = derive_preflight(
        artifact_directory=arguments.artifact_directory,
        runtime_root=arguments.runtime_root,
    )
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
