#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"

DEFAULT_OUT_JSON = RUNS / "local_delivery_environment_manifest_current.json"
DEFAULT_OUT_MD = RUNS / "local_delivery_environment_manifest_current.md"
DEFAULT_REQUIREMENTS_FILES = ("requirements.txt", "requirements-dev.txt")
DEFAULT_REQUIREMENTS_LOCK_JSON = RUNS / "local_delivery_requirements_lock_current.json"
DEFAULT_REQUIREMENTS_LOCK_MD = RUNS / "local_delivery_requirements_lock_current.md"
DEFAULT_REQUIREMENTS_LOCK_TXT = RUNS / "local_delivery_requirements_lock_current.txt"

_ACCELERATOR_ENV_KEYS = (
    "CUDA_HOME",
    "CUDA_PATH",
    "CUDA_VISIBLE_DEVICES",
    "CUDA_DEVICE_ORDER",
    "CUDA_MODULE_LOADING",
    "NVIDIA_VISIBLE_DEVICES",
    "NVIDIA_DRIVER_CAPABILITIES",
    "NCCL_DEBUG",
    "ROCM_HOME",
    "ROCM_PATH",
    "HIP_PATH",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "AMD_VISIBLE_DEVICES",
    "HSA_OVERRIDE_GFX_VERSION",
    "PYTORCH_ROCM_ARCH",
    "TORCH_BLAS_PREFER_HIPBLASLT",
    "LD_LIBRARY_PATH",
)

_ACCELERATOR_PROBES: dict[str, list[str]] = {
    "nvidia_smi": ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
    "nvcc": ["nvcc", "--version"],
    "rocm_smi": ["rocm-smi", "--showdriverversion", "--showproductname", "--json"],
    "rocminfo": ["rocminfo"],
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _relative_path(path: str | Path) -> str:
    resolved = _resolve(path)
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _sanitize_label(value: str) -> str:
    cleaned = "".join(ch if (ch.isalnum() or ch in {"-", "_"}) else "_" for ch in str(value).strip())
    return cleaned.strip("_") or "local_delivery_environment_manifest_current"


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", str(value).strip().lower())


def _extract_requirement_name(requirement: str) -> str:
    base = str(requirement).split(";", 1)[0].strip()
    if base.startswith("-e "):
        base = base[3:].strip()
    if base.startswith("--editable "):
        base = base[len("--editable ") :].strip()
    if " @ " in base:
        name = base.split(" @ ", 1)[0].strip()
    else:
        name = re.split(r"\s*(?:===|~=|==|!=|<=|>=|<|>)\s*|\s+", base, maxsplit=1)[0].strip()
    return name.split("[", 1)[0].strip()


def _is_pinned_requirement(requirement: str) -> bool:
    return bool(
        re.match(r"^[A-Za-z0-9_.-]+(\[[A-Za-z0-9_.,-]+\])?\s*==\s*[^=;,\s]+(?:\s*;.*)?$", str(requirement).strip())
    )


def _now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sha256_file(path_like: str | Path) -> str:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _load_json_object(path_like: str | Path) -> dict[str, Any]:
    path = _resolve(path_like)
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _command_result(cmd: Sequence[str], cwd: Path = ROOT, timeout: int = 5) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        return {
            "cmd": list(cmd),
            "returncode": None,
            "ok": False,
            "stdout_excerpt": "",
            "stderr_excerpt": str(exc),
        }
    return {
        "cmd": list(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout_excerpt": "\n".join((proc.stdout or "").splitlines()[:20]),
        "stderr_excerpt": "\n".join((proc.stderr or "").splitlines()[:20]),
    }


def _collect_python_runtime() -> dict[str, Any]:
    return {
        "executable": sys.executable,
        "version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "version_info": {
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
        },
        "prefix": sys.prefix,
        "base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "virtual_env_active": bool(getattr(sys, "base_prefix", sys.prefix) != sys.prefix),
        "venv_name": str(Path(sys.prefix).name),
        "virtual_env": str(os.environ.get("VIRTUAL_ENV", "")),
        "conda_prefix": str(os.environ.get("CONDA_PREFIX", "")),
        "pythonpath": str(os.environ.get("PYTHONPATH", "")),
        "sys_path0": str(sys.path[0]) if sys.path else "",
    }


def _collect_platform_info() -> dict[str, Any]:
    uname = platform.uname()
    libc_name, libc_version = platform.libc_ver()
    return {
        "platform": platform.platform(),
        "system": uname.system,
        "release": uname.release,
        "version": uname.version,
        "machine": uname.machine,
        "processor": uname.processor,
        "node": uname.node,
        "architecture": list(platform.architecture()),
        "libc": {
            "name": libc_name,
            "version": libc_version,
        },
    }


def _collect_accelerator_info(
    env: Mapping[str, str] | None = None,
    probe_commands: bool = True,
) -> dict[str, Any]:
    effective_env = dict(env or {})
    present_env = {key: effective_env[key] for key in _ACCELERATOR_ENV_KEYS if effective_env.get(key)}
    cuda_keys = [key for key in present_env if key.startswith("CUDA") or key.startswith("NVIDIA") or key == "NCCL_DEBUG"]
    rocm_keys = [
        key
        for key in present_env
        if key.startswith("ROCM")
        or key.startswith("HIP")
        or key.startswith("ROCR")
        or key.startswith("AMD")
        or key.startswith("HSA")
    ]
    detected_stack = "unspecified"
    if cuda_keys and rocm_keys:
        detected_stack = "mixed_cuda_rocm_env"
    elif cuda_keys:
        detected_stack = "cuda_env_configured"
    elif rocm_keys:
        detected_stack = "rocm_env_configured"
    elif present_env:
        detected_stack = "accelerator_env_present"

    command_probes: dict[str, dict[str, Any]] = {}
    if probe_commands:
        for label, cmd in _ACCELERATOR_PROBES.items():
            command_probes[label] = {
                "available": bool(shutil.which(cmd[0])),
                **_command_result(cmd),
            }
    available_probes = [label for label, probe in command_probes.items() if bool(probe.get("available"))]
    ok_probe_labels = [label for label, probe in command_probes.items() if bool(probe.get("ok"))]
    status_parts = [f"stack={detected_stack}"]
    if present_env:
        status_parts.append("env=" + ",".join(sorted(present_env)))
    if available_probes:
        status_parts.append("probes=" + ",".join(sorted(available_probes)))
    if ok_probe_labels:
        status_parts.append("probe_ok=" + ",".join(sorted(ok_probe_labels)))
    if len(status_parts) == 1:
        status_parts.append("env=none")
    return {
        "detected_stack": detected_stack,
        "present_env": present_env,
        "available_probe_labels": available_probes,
        "ok_probe_labels": ok_probe_labels,
        "command_probes": command_probes,
        "status_line": " | ".join(status_parts),
    }


def _collect_git_info() -> dict[str, Any]:
    git_available = bool(shutil.which("git"))
    if not git_available:
        return {
            "command_available": False,
            "available": False,
            "commit": "",
            "short_commit": "",
            "branch": "",
            "dirty": False,
            "repository_root": "",
            "status_line": "git unavailable",
        }

    commit_result = _command_result(["git", "rev-parse", "HEAD"])
    short_result = _command_result(["git", "rev-parse", "--short", "HEAD"])
    branch_result = _command_result(["git", "branch", "--show-current"])
    dirty_result = _command_result(["git", "status", "--short", "--untracked-files=no"])
    root_result = _command_result(["git", "rev-parse", "--show-toplevel"])

    commit = str(commit_result.get("stdout_excerpt", "")).strip()
    short_commit = str(short_result.get("stdout_excerpt", "")).strip()
    branch = str(branch_result.get("stdout_excerpt", "")).strip()
    dirty = bool(str(dirty_result.get("stdout_excerpt", "")).strip())
    repository_root = str(root_result.get("stdout_excerpt", "")).strip()
    available = bool(commit)
    status_parts = [f"git={'available' if available else 'unavailable'}"]
    if short_commit:
        status_parts.append(f"commit={short_commit}")
    if branch:
        status_parts.append(f"branch={branch}")
    status_parts.append(f"dirty={dirty}")
    return {
        "command_available": True,
        "available": available,
        "commit": commit,
        "short_commit": short_commit,
        "branch": branch,
        "dirty": dirty,
        "repository_root": repository_root,
        "status_line": " | ".join(status_parts),
    }


def _installed_distribution_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = str(dist.metadata.get("Name") or "").strip()
        if not name:
            continue
        versions[_normalize_name(name)] = str(dist.version)
    return versions


def _collect_declared_requirements(requirement_files: Sequence[str | Path]) -> dict[str, Any]:
    declared: list[dict[str, Any]] = []
    visited_files: list[str] = []
    missing_source_files: list[str] = []
    seen_files: set[Path] = set()
    seen_requirements: set[tuple[str, str]] = set()

    def _walk(path_like: str | Path) -> None:
        path = _resolve(path_like)
        if path in seen_files:
            return
        seen_files.add(path)
        if not path.exists():
            missing_source_files.append(_relative_path(path))
            return
        visited_files.append(_relative_path(path))
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r ") or line.startswith("--requirement "):
                _, target = line.split(maxsplit=1)
                _walk((path.parent / target.strip()).resolve())
                continue
            if line.startswith("--"):
                continue
            requirement = line
            name = _extract_requirement_name(requirement)
            if not name:
                continue
            key = (_normalize_name(name), requirement)
            if key in seen_requirements:
                continue
            seen_requirements.add(key)
            declared.append(
                {
                    "name": name,
                    "normalized_name": _normalize_name(name),
                    "requirement": requirement,
                    "source_file": _relative_path(path),
                }
            )

    for requirement_file in requirement_files:
        _walk(requirement_file)
    return {
        "declared": declared,
        "resolved_source_files": visited_files,
        "missing_source_files": missing_source_files,
    }


def _collect_requirements_snapshot(requirement_files: Sequence[str | Path]) -> dict[str, Any]:
    declared_snapshot = _collect_declared_requirements(requirement_files)
    installed_versions = _installed_distribution_versions()
    declared: list[dict[str, Any]] = []
    missing_packages: list[str] = []
    unpinned_packages: list[str] = []
    for entry in declared_snapshot["declared"]:
        installed_version = installed_versions.get(entry["normalized_name"], "")
        row = dict(entry)
        row["installed"] = bool(installed_version)
        row["installed_version"] = installed_version
        row["is_pinned"] = _is_pinned_requirement(row["requirement"])
        declared.append(row)
        if not row["installed"]:
            missing_packages.append(row["name"])
        if not row["is_pinned"]:
            unpinned_packages.append(row["name"])
    return {
        "source_files": [_relative_path(path) for path in requirement_files],
        "resolved_source_files": list(declared_snapshot["resolved_source_files"]),
        "missing_source_files": list(declared_snapshot["missing_source_files"]),
        "declared": declared,
        "declared_requirement_count": len(declared),
        "installed_requirement_count": sum(1 for row in declared if bool(row["installed"])),
        "missing_requirement_count": len(missing_packages),
        "pinned_requirement_count": sum(1 for row in declared if bool(row["is_pinned"])),
        "unpinned_requirement_count": sum(1 for row in declared if not bool(row["is_pinned"])),
        "missing_packages": missing_packages,
        "unpinned_packages": unpinned_packages,
        "installed_distribution_count": len(installed_versions),
        "resolution_source": "importlib.metadata",
        "status_line": (
            f"{sum(1 for row in declared if bool(row['installed']))}/{len(declared)} declared requirements installed"
            f" | {sum(1 for row in declared if not bool(row['is_pinned']))} unpinned"
        ),
    }


def _preview(values: Sequence[Any], *, limit: int = 5) -> str:
    shown = [str(value) for value in list(values)[:limit]]
    if len(values) > limit:
        shown.append("...")
    return ", ".join(shown)


def _lock_summary_list(lock_summary: Mapping[str, Any], key: str) -> list[Any]:
    value = lock_summary.get(key)
    return list(value) if isinstance(value, list) else []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture the local-delivery machine/runtime baseline so delivery bundles can point to a reproducible "
            "Python, platform, accelerator, and requirements manifest."
        )
    )
    parser.add_argument("--manifest-label", default="local_delivery_environment_manifest_current")
    parser.add_argument("--requirements-files", nargs="*", default=list(DEFAULT_REQUIREMENTS_FILES))
    parser.add_argument("--requirements-lock-json", default=str(DEFAULT_REQUIREMENTS_LOCK_JSON))
    parser.add_argument("--requirements-lock-md", default=str(DEFAULT_REQUIREMENTS_LOCK_MD))
    parser.add_argument("--requirements-lock-txt", default=str(DEFAULT_REQUIREMENTS_LOCK_TXT))
    parser.add_argument("--probe-accelerator-commands", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    return parser


def build_payload(
    args: argparse.Namespace,
    *,
    generated_at_local: str,
    python_runtime: dict[str, Any],
    platform_info: dict[str, Any],
    accelerator_info: dict[str, Any],
    git_info: dict[str, Any],
    requirements_snapshot: dict[str, Any],
    requirements_lock: dict[str, Any] | None = None,
) -> dict[str, Any]:
    label = _sanitize_label(str(args.manifest_label))
    missing_packages = list(requirements_snapshot.get("missing_packages", []) or [])
    unpinned_packages = list(requirements_snapshot.get("unpinned_packages", []) or [])
    git_short_commit = str(git_info.get("short_commit") or "")
    platform_tag = " ".join(
        part for part in [platform_info.get("system"), platform_info.get("release"), platform_info.get("machine")] if str(part).strip()
    )
    requirements_lock = dict(requirements_lock or {})
    lock_payload = requirements_lock.get("payload")
    lock_summary = dict(requirements_lock.get("summary", {}) or {})
    if not lock_summary and isinstance(lock_payload, dict):
        lock_summary = dict(lock_payload.get("summary", {}) or {})
    requirements_lock["summary"] = lock_summary

    def _lock_summary_int(key: str) -> int:
        try:
            return int(lock_summary.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    lock_json_present = bool(requirements_lock.get("json_present", False))
    lock_md_present = bool(requirements_lock.get("md_present", False))
    lock_txt_present = bool(requirements_lock.get("txt_present", False))
    lock_artifacts_present = bool(lock_json_present and lock_md_present and lock_txt_present)
    lock_missing_count = _lock_summary_int("missing_count")
    lock_loose_source_count = _lock_summary_int("loose_source_requirement_count")
    lock_missing_input_count = _lock_summary_int("missing_input_file_count")
    lock_unpinned_count = _lock_summary_int("unpinned_count")
    lock_optional_missing_count = _lock_summary_int("optional_missing_count")
    lock_missing_package_targets = [
        str(value) for value in _lock_summary_list(lock_summary, "missing_package_install_targets")
    ]
    lock_optional_deferred_targets = [
        str(value) for value in _lock_summary_list(lock_summary, "optional_deferred_install_targets")
    ]
    lock_loose_source_requirements = [
        str(value) for value in _lock_summary_list(lock_summary, "loose_source_requirements")
    ]
    lock_unpinned_pin_suggestions = [
        row
        for row in _lock_summary_list(lock_summary, "unpinned_pin_suggestions")
        if isinstance(row, dict)
    ]
    explicit_lock_complete = lock_summary.get("requirements_lock_complete")
    if isinstance(explicit_lock_complete, bool):
        lock_complete = bool(lock_artifacts_present and explicit_lock_complete)
    else:
        lock_complete = bool(
            lock_artifacts_present
            and lock_missing_count == 0
            and lock_loose_source_count == 0
            and lock_missing_input_count == 0
        )
    lock_state = (
        "complete"
        if lock_complete
        else ("incomplete" if any((lock_json_present, lock_md_present, lock_txt_present)) else "missing")
    )

    if not lock_artifacts_present:
        next_required_step = (
            "Build the local-delivery requirements lock, then rerun `python3 tools/run_local_delivery_preflight.py` "
            "before treating this environment baseline as reproducible."
        )
    elif not lock_complete:
        action_parts = []
        if lock_missing_package_targets:
            action_parts.append(f"install or remove missing packages: {_preview(lock_missing_package_targets)}")
        if lock_loose_source_requirements:
            action_parts.append(
                f"replace loose/source requirements with package pins: {_preview(lock_loose_source_requirements)}"
            )
        if lock_missing_input_count:
            action_parts.append("restore or remove missing requirement input files")
        detail = "; ".join(action_parts) or "resolve the requirements lock incomplete reasons"
        next_required_step = (
            f"{detail}. Then rebuild the requirements lock and rerun the local-delivery preflight."
        )
    elif missing_packages:
        preview = ", ".join(missing_packages[:3])
        if len(missing_packages) > 3:
            preview += ", ..."
        next_required_step = (
            f"Install or reconcile the missing declared packages ({preview}) on the delivery machine, then rerun this "
            "environment manifest and `python3 tools/run_local_delivery_preflight.py` before treating the baseline as reproducible."
        )
    elif unpinned_packages:
        next_required_step = (
            "Attach this manifest and its requirements lock to the local-delivery bundle as the current machine record; "
            "regenerate both artifacts after any dependency, interpreter, accelerator-driver, or git-baseline change."
        )
    else:
        next_required_step = (
            "Attach this manifest and its requirements lock to the delivery bundle and refresh both artifacts after any "
            "interpreter, dependency, accelerator-driver, or git-baseline change before issuing another delivery verdict."
        )

    git_available = bool(git_info.get("available"))
    git_state = "dirty" if bool(git_info.get("dirty")) else ("clean" if git_available else "unknown")
    accelerator_present_env = dict(accelerator_info.get("present_env", {}) or {})
    torch_blas_prefer_hipblaslt = str(accelerator_present_env.get("TORCH_BLAS_PREFER_HIPBLASLT", ""))
    accelerator_env_var_count = len(accelerator_present_env)
    status_line = (
        f"python={python_runtime.get('version', '-')}"
        f" | platform={platform_tag or '-'}"
        f" | git={(git_short_commit or 'unavailable')}:{git_state}"
        f" | requirements={requirements_snapshot.get('installed_requirement_count', 0)}/{requirements_snapshot.get('declared_requirement_count', 0)} installed"
        f" | requirements_lock={lock_state}"
        f" | accelerator={accelerator_info.get('detected_stack', 'unspecified')}"
        f" | accelerator_env_vars={accelerator_env_var_count}"
        f" | torch_blas_prefer_hipblaslt={torch_blas_prefer_hipblaslt or '-'}"
    )
    summary = {
        "manifest_label": label,
        "generated_at_local": generated_at_local,
        "python_executable": str(python_runtime.get("executable", "")),
        "python_version": str(python_runtime.get("version", "")),
        "platform_tag": platform_tag,
        "git_commit": str(git_info.get("commit", "")),
        "git_short_commit": git_short_commit,
        "git_dirty": bool(git_info.get("dirty", False)),
        "accelerator_stack": str(accelerator_info.get("detected_stack", "unspecified")),
        "accelerator_env_var_count": accelerator_env_var_count,
        "torch_blas_prefer_hipblaslt": torch_blas_prefer_hipblaslt,
        "requirements_source_files": list(requirements_snapshot.get("source_files", []) or []),
        "declared_requirement_count": int(requirements_snapshot.get("declared_requirement_count", 0) or 0),
        "installed_requirement_count": int(requirements_snapshot.get("installed_requirement_count", 0) or 0),
        "missing_requirement_count": int(requirements_snapshot.get("missing_requirement_count", 0) or 0),
        "pinned_requirement_count": int(requirements_snapshot.get("pinned_requirement_count", 0) or 0),
        "unpinned_requirement_count": int(requirements_snapshot.get("unpinned_requirement_count", 0) or 0),
        "requirements_lock_json": str(requirements_lock.get("json_path", "")),
        "requirements_lock_md": str(requirements_lock.get("md_path", "")),
        "requirements_lock_txt": str(requirements_lock.get("txt_path", "")),
        "requirements_lock_json_present": lock_json_present,
        "requirements_lock_md_present": lock_md_present,
        "requirements_lock_txt_present": lock_txt_present,
        "requirements_lock_complete": lock_complete,
        "requirements_lock_state": lock_state,
        "requirements_lock_missing_count": lock_missing_count,
        "requirements_lock_loose_source_requirement_count": lock_loose_source_count,
        "requirements_lock_missing_input_file_count": lock_missing_input_count,
        "requirements_lock_unpinned_count": lock_unpinned_count,
        "requirements_lock_missing_package_install_targets": lock_missing_package_targets,
        "requirements_lock_optional_missing_count": lock_optional_missing_count,
        "requirements_lock_optional_deferred_install_targets": lock_optional_deferred_targets,
        "requirements_lock_optional_profiles": dict(lock_summary.get("optional_profiles", {}) or {}),
        "requirements_lock_loose_source_requirements": lock_loose_source_requirements,
        "requirements_lock_unpinned_pin_suggestions": lock_unpinned_pin_suggestions,
        "requirements_lock_txt_sha256": str(requirements_lock.get("txt_sha256", "")),
        "status_line": status_line,
        "next_required_step": next_required_step,
    }
    return {
        "summary": summary,
        "python_runtime": python_runtime,
        "platform": platform_info,
        "accelerator_runtime": accelerator_info,
        "git": git_info,
        "requirements_snapshot": requirements_snapshot,
        "requirements_lock": requirements_lock,
    }


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    summary = payload["summary"]
    python_runtime = payload["python_runtime"]
    platform_info = payload["platform"]
    accelerator_info = payload["accelerator_runtime"]
    git_info = payload["git"]
    requirements_snapshot = payload["requirements_snapshot"]
    requirements_lock = dict(payload.get("requirements_lock", {}) or {})
    requirements_lock_summary = dict(requirements_lock.get("summary", {}) or {})
    lines = [
        "# Local Delivery Environment Manifest",
        "",
        f"- manifest_label: `{summary['manifest_label']}`",
        f"- generated_at_local: `{summary['generated_at_local']}`",
        f"- status_line: `{summary['status_line']}`",
        f"- python_version: `{summary['python_version']}`",
        f"- python_executable: `{summary['python_executable']}`",
        f"- platform_tag: `{summary['platform_tag']}`",
        f"- git_short_commit: `{summary['git_short_commit'] or '-'}`",
        f"- git_dirty: `{summary['git_dirty']}`",
        f"- accelerator_stack: `{summary['accelerator_stack']}`",
        f"- accelerator_env_var_count: `{summary['accelerator_env_var_count']}`",
        f"- torch_blas_prefer_hipblaslt: `{summary.get('torch_blas_prefer_hipblaslt', '') or '-'}`",
        f"- declared_requirement_count: `{summary['declared_requirement_count']}`",
        f"- installed_requirement_count: `{summary['installed_requirement_count']}`",
        f"- missing_requirement_count: `{summary['missing_requirement_count']}`",
        f"- pinned_requirement_count: `{summary['pinned_requirement_count']}`",
        f"- unpinned_requirement_count: `{summary['unpinned_requirement_count']}`",
        f"- requirements_lock_complete: `{summary.get('requirements_lock_complete', False)}`",
        f"- requirements_lock_state: `{summary.get('requirements_lock_state', '-')}`",
        f"- requirements_lock_missing_count: `{summary.get('requirements_lock_missing_count', 0)}`",
        f"- requirements_lock_loose_source_requirement_count: `{summary.get('requirements_lock_loose_source_requirement_count', 0)}`",
        f"- requirements_lock_unpinned_count: `{summary.get('requirements_lock_unpinned_count', 0)}`",
        f"- requirements_lock_missing_package_install_targets: `{', '.join(summary.get('requirements_lock_missing_package_install_targets', []) or []) or '-'}`",
        f"- requirements_lock_optional_missing_count: `{summary.get('requirements_lock_optional_missing_count', 0)}`",
        f"- requirements_lock_optional_deferred_install_targets: `{', '.join(summary.get('requirements_lock_optional_deferred_install_targets', []) or []) or '-'}`",
        f"- requirements_lock_json: `{summary.get('requirements_lock_json', '') or '-'}`",
        f"- requirements_lock_md: `{summary.get('requirements_lock_md', '') or '-'}`",
        f"- requirements_lock_txt: `{summary.get('requirements_lock_txt', '') or '-'}`",
        f"- requirements_lock_txt_sha256: `{summary.get('requirements_lock_txt_sha256', '') or '-'}`",
        f"- next_required_step: {summary['next_required_step']}",
        "",
        "## Python Runtime",
        "",
        f"- executable: `{python_runtime.get('executable', '')}`",
        f"- version: `{python_runtime.get('version', '')}`",
        f"- implementation: `{python_runtime.get('implementation', '')}`",
        f"- prefix: `{python_runtime.get('prefix', '')}`",
        f"- base_prefix: `{python_runtime.get('base_prefix', '')}`",
        f"- virtual_env_active: `{python_runtime.get('virtual_env_active', False)}`",
        f"- virtual_env: `{python_runtime.get('virtual_env', '') or '-'}`",
        f"- conda_prefix: `{python_runtime.get('conda_prefix', '') or '-'}`",
        f"- pythonpath: `{python_runtime.get('pythonpath', '') or '-'}`",
        "",
        "## Platform",
        "",
        f"- platform: `{platform_info.get('platform', '')}`",
        f"- system: `{platform_info.get('system', '')}`",
        f"- release: `{platform_info.get('release', '')}`",
        f"- version: `{platform_info.get('version', '')}`",
        f"- machine: `{platform_info.get('machine', '')}`",
        f"- processor: `{platform_info.get('processor', '')}`",
        "",
        "## Accelerator Runtime",
        "",
        f"- status_line: `{accelerator_info.get('status_line', '')}`",
        f"- detected_stack: `{accelerator_info.get('detected_stack', '')}`",
        "",
        "| env_var | value |",
        "| --- | --- |",
    ]
    present_env = dict(accelerator_info.get("present_env", {}) or {})
    if present_env:
        for key, value in sorted(present_env.items()):
            lines.append(f"| `{key}` | `{value}` |")
    else:
        lines.append("| `-` | `-` |")

    command_probes = dict(accelerator_info.get("command_probes", {}) or {})
    lines.extend(
        [
            "",
            "## Accelerator Command Probes",
            "",
            "| probe | available | ok | cmd | excerpt |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if command_probes:
        for label, probe in sorted(command_probes.items()):
            excerpt = str(probe.get("stdout_excerpt") or probe.get("stderr_excerpt") or "").replace("\n", " / ")
            lines.append(
                f"| `{label}` | `{probe.get('available', False)}` | `{probe.get('ok', False)}` | "
                f"`{shlex.join(list(probe.get('cmd', []) or []))}` | `{excerpt or '-'}` |"
            )
    else:
        lines.append("| `-` | `False` | `False` | `-` | `-` |")

    lines.extend(
        [
            "",
            "## Git",
            "",
            f"- status_line: `{git_info.get('status_line', '')}`",
            f"- commit: `{git_info.get('commit', '') or '-'}`",
            f"- short_commit: `{git_info.get('short_commit', '') or '-'}`",
            f"- branch: `{git_info.get('branch', '') or '-'}`",
            f"- dirty: `{git_info.get('dirty', False)}`",
            f"- repository_root: `{git_info.get('repository_root', '') or '-'}`",
            "",
            "## Requirements Lock",
            "",
            f"- json_path: `{summary.get('requirements_lock_json', '') or '-'}`",
            f"- json_present: `{summary.get('requirements_lock_json_present', False)}`",
            f"- md_path: `{summary.get('requirements_lock_md', '') or '-'}`",
            f"- md_present: `{summary.get('requirements_lock_md_present', False)}`",
            f"- txt_path: `{summary.get('requirements_lock_txt', '') or '-'}`",
            f"- txt_present: `{summary.get('requirements_lock_txt_present', False)}`",
            f"- txt_sha256: `{summary.get('requirements_lock_txt_sha256', '') or '-'}`",
            f"- complete: `{summary.get('requirements_lock_complete', False)}`",
            f"- state: `{summary.get('requirements_lock_state', '-')}`",
            f"- missing_package_install_targets: `{', '.join(summary.get('requirements_lock_missing_package_install_targets', []) or []) or '-'}`",
            f"- optional_deferred_install_targets: `{', '.join(summary.get('requirements_lock_optional_deferred_install_targets', []) or []) or '-'}`",
            f"- loose_source_requirements: `{', '.join(summary.get('requirements_lock_loose_source_requirements', []) or []) or '-'}`",
            f"- status_line: `{requirements_lock_summary.get('status_line', '-')}`",
            f"- next_required_step: {requirements_lock_summary.get('next_required_step', '-')}",
        "",
            "### Pin Suggestions From Lock",
            "",
            "| requirement | installed_version | suggested_requirement | source |",
            "| --- | --- | --- | --- |",
        ]
    )
    pin_suggestions = list(summary.get("requirements_lock_unpinned_pin_suggestions", []) or [])
    if pin_suggestions:
        for row in pin_suggestions:
            lines.append(
                f"| `{row.get('current_requirement', '')}` | `{row.get('installed_version', '') or '-'}` | "
                f"`{row.get('suggested_requirement', '') or '-'}` | `{row.get('source', '')}` |"
            )
    else:
        lines.append("| `-` | `-` | `-` | `-` |")

    lines.extend(
        [
            "",
            "## Declared Requirements Snapshot",
            "",
            f"- source_files: `{', '.join(requirements_snapshot.get('source_files', []) or [])}`",
            f"- resolved_source_files: `{', '.join(requirements_snapshot.get('resolved_source_files', []) or [])}`",
            f"- missing_source_files: `{', '.join(requirements_snapshot.get('missing_source_files', []) or [])}`",
            f"- resolution_source: `{requirements_snapshot.get('resolution_source', '')}`",
            f"- status_line: `{requirements_snapshot.get('status_line', '')}`",
            "",
            "| requirement | installed_version | pinned | source_file |",
            "| --- | --- | --- | --- |",
        ]
    )
    declared = list(requirements_snapshot.get("declared", []) or [])
    if declared:
        for row in declared:
            lines.append(
                f"| `{row.get('requirement', '')}` | `{row.get('installed_version', '') or '-'}` | "
                f"`{row.get('is_pinned', False)}` | `{row.get('source_file', '')}` |"
            )
    else:
        lines.append("| `-` | `-` | `False` | `-` |")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    requirements_lock_payload = _load_json_object(args.requirements_lock_json)
    payload = build_payload(
        args,
        generated_at_local=_now_local(),
        python_runtime=_collect_python_runtime(),
        platform_info=_collect_platform_info(),
        accelerator_info=_collect_accelerator_info(
            env=dict(os.environ),
            probe_commands=bool(args.probe_accelerator_commands),
        ),
        git_info=_collect_git_info(),
        requirements_snapshot=_collect_requirements_snapshot(args.requirements_files),
        requirements_lock={
            "json_path": _relative_path(args.requirements_lock_json),
            "md_path": _relative_path(args.requirements_lock_md),
            "txt_path": _relative_path(args.requirements_lock_txt),
            "json_present": _resolve(args.requirements_lock_json).exists(),
            "md_present": _resolve(args.requirements_lock_md).exists(),
            "txt_present": _resolve(args.requirements_lock_txt).exists(),
            "txt_sha256": _sha256_file(args.requirements_lock_txt),
            "payload": requirements_lock_payload,
            "summary": dict(requirements_lock_payload.get("summary", {}) or {}),
        },
    )
    _write_json(args.out_json, payload)
    _write_markdown(args.out_md, payload)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
