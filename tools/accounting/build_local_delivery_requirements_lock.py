#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"

DEFAULT_REQUIREMENTS_FILES = ("requirements.txt", "requirements-dev.txt")
DEFAULT_OPTIONAL_REQUIREMENTS_PROFILES = {
    "api": ("requirements-api.txt",),
    "train": ("requirements-train.txt",),
    "deploy": ("requirements-deploy.txt",),
    "optional": ("requirements-optional.txt",),
}
DEFAULT_OUT_JSON = RUNS / "local_delivery_requirements_lock_current.json"
DEFAULT_OUT_MD = RUNS / "local_delivery_requirements_lock_current.md"
DEFAULT_OUT_TXT = RUNS / "local_delivery_requirements_lock_current.txt"

_INCLUDE_FLAGS = {"-r", "--requirement"}
_IGNORED_OPTION_PREFIXES = (
    "--extra-index-url",
    "--find-links",
    "--index-url",
    "--no-binary",
    "--only-binary",
    "--prefer-binary",
    "--trusted-host",
    "-c",
    "--constraint",
    "-f",
    "-i",
)


def _now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _resolve_path(path_like: str | Path, *, base_dir: Path | None = None) -> Path:
    path = Path(str(path_like)).expanduser()
    if path.is_absolute():
        return path.resolve()
    if base_dir is not None:
        return (base_dir / path).resolve()
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (ROOT / path).resolve()


def _relative_path(path_like: str | Path) -> str:
    path = Path(path_like).resolve()
    for base in (ROOT, Path.cwd()):
        try:
            return str(path.relative_to(base.resolve()))
        except ValueError:
            continue
    return str(path)


def _normalize_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", str(value).strip().lower())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _command_result(cmd: Sequence[str], *, timeout: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            list(cmd),
            cwd=ROOT,
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
            "stdout": "",
            "stderr": str(exc),
        }
    return {
        "cmd": list(cmd),
        "returncode": int(proc.returncode),
        "ok": bool(proc.returncode == 0),
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _git_info() -> dict[str, Any]:
    commit_result = _command_result(["git", "rev-parse", "HEAD"])
    short_result = _command_result(["git", "rev-parse", "--short", "HEAD"])
    dirty_result = _command_result(["git", "status", "--short", "--untracked-files=no"])
    branch_result = _command_result(["git", "branch", "--show-current"])
    commit = str(commit_result.get("stdout", "")).strip()
    short_commit = str(short_result.get("stdout", "")).strip()
    dirty = bool(str(dirty_result.get("stdout", "")).strip())
    return {
        "available": bool(commit),
        "commit": commit,
        "short_commit": short_commit,
        "branch": str(branch_result.get("stdout", "")).strip(),
        "dirty": dirty,
        "status_line": f"git={'available' if commit else 'unavailable'} | commit={short_commit or '-'} | dirty={dirty}",
    }


def _runtime_info() -> dict[str, Any]:
    pip_result = _command_result([sys.executable, "-m", "pip", "--version"])
    return {
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "pip": {
            "available": bool(pip_result.get("ok", False)),
            "version_line": str(pip_result.get("stdout", "")),
        },
        "platform": {
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }


def _installed_distributions(installed_versions: Mapping[str, str] | None = None) -> list[dict[str, str]]:
    if installed_versions is not None:
        rows = [
            {
                "name": str(name),
                "normalized_name": _normalize_name(str(name)),
                "version": str(version),
            }
            for name, version in installed_versions.items()
        ]
    else:
        rows = []
        for dist in importlib.metadata.distributions():
            name = str(dist.metadata.get("Name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "normalized_name": _normalize_name(name),
                    "version": str(dist.version),
                }
            )
    return sorted(rows, key=lambda row: (row["normalized_name"], row["version"]))


def _split_inline_comment(line: str) -> str:
    match = re.search(r"\s+#", line)
    if not match:
        return line.strip()
    return line[: match.start()].strip()


def _source_ref(row: Mapping[str, Any]) -> str:
    return f"{row.get('source_file_relative', '')}:{row.get('line_number', '')}"


def _preview(values: Sequence[str], *, limit: int = 5) -> str:
    shown = [str(value) for value in values[:limit]]
    if len(values) > limit:
        shown.append("...")
    return ", ".join(shown)


def _default_optional_requirement_profiles() -> dict[str, tuple[str, ...]]:
    return {
        profile: files
        for profile, files in DEFAULT_OPTIONAL_REQUIREMENTS_PROFILES.items()
        if any(_resolve_path(path).exists() for path in files)
    }


def _parse_include(line: str) -> str | None:
    try:
        tokens = shlex.split(line, comments=False)
    except ValueError:
        tokens = line.split()
    if not tokens:
        return None
    first = tokens[0]
    if first in _INCLUDE_FLAGS and len(tokens) >= 2:
        return tokens[1]
    for flag in _INCLUDE_FLAGS:
        prefix = f"{flag}="
        if first.startswith(prefix):
            return first[len(prefix) :]
    return None


def _is_ignored_option(line: str) -> bool:
    stripped = line.strip()
    return any(
        stripped == prefix or stripped.startswith(prefix + " ") or stripped.startswith(prefix + "=")
        for prefix in _IGNORED_OPTION_PREFIXES
    )


def _parse_requirement_token(requirement: str) -> dict[str, Any]:
    text = _split_inline_comment(requirement)
    marker = ""
    if ";" in text:
        text, marker = [part.strip() for part in text.split(";", 1)]
    editable = False
    if text.startswith("-e "):
        editable = True
        text = text[3:].strip()
    elif text.startswith("--editable "):
        editable = True
        text = text[len("--editable ") :].strip()

    if " @ " in text:
        name_token = text.split(" @ ", 1)[0].strip()
    else:
        name_token = re.split(r"\s*(?:===|~=|==|!=|<=|>=|<|>)\s*|\s+", text, maxsplit=1)[0].strip()

    match = re.match(
        r"^(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[(?P<extras>[A-Za-z0-9_., -]+)\])?$",
        name_token,
    )
    if not match:
        return {
            "requirement": text,
            "marker": marker,
            "editable": editable,
            "name": "",
            "extras": [],
            "display_name": "",
            "normalized_name": "",
            "pinned_exact": False,
            "source_requirement": True,
        }

    extras = [extra.strip() for extra in (match.group("extras") or "").split(",") if extra.strip()]
    display_name = match.group("name")
    if extras:
        display_name = f"{display_name}[{','.join(extras)}]"
    pinned_exact = bool(
        re.match(
            r"^[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_., -]+\])?\s*==\s*[^=;,\s]+$",
            text,
        )
    )
    source_requirement = editable or bool(re.match(r"^(?:https?|git|svn|hg|bzr)\+", text)) or bool(
        text.startswith(("./", "../", "/", "file:"))
    )
    return {
        "requirement": text,
        "marker": marker,
        "editable": editable,
        "name": match.group("name"),
        "extras": extras,
        "display_name": display_name,
        "normalized_name": _normalize_name(match.group("name")),
        "pinned_exact": pinned_exact,
        "source_requirement": source_requirement,
    }


def read_requirements(requirement_files: Sequence[str | Path]) -> dict[str, Any]:
    visited: set[Path] = set()
    input_files: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    loose_sources: list[dict[str, Any]] = []

    def visit(path_like: str | Path, *, requested_by: str = "", base_dir: Path | None = None) -> None:
        path = _resolve_path(path_like, base_dir=base_dir)
        if path in visited:
            return
        visited.add(path)
        file_row = {
            "path": str(path),
            "relative_path": _relative_path(path),
            "requested_by": requested_by,
            "exists": path.exists(),
        }
        input_files.append(file_row)
        if not path.exists():
            return
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = _split_inline_comment(raw_line)
            if not stripped or stripped.startswith("#"):
                continue
            include = _parse_include(stripped)
            if include:
                visit(include, requested_by=f"{_relative_path(path)}:{line_number}", base_dir=path.parent)
                continue
            if _is_ignored_option(stripped):
                continue
            parsed = _parse_requirement_token(stripped)
            row = {
                "source_file": str(path),
                "source_file_relative": _relative_path(path),
                "line_number": line_number,
                "raw": raw_line.strip(),
                **parsed,
            }
            if parsed["name"]:
                requirements.append(row)
            else:
                loose_sources.append(row)

    for requirement_file in requirement_files:
        visit(requirement_file)
    return {
        "input_files": input_files,
        "requirements": requirements,
        "loose_source_requirements": loose_sources,
    }


def _installed_version(name: str, installed_versions: Mapping[str, str] | None = None) -> str:
    normalized = _normalize_name(name)
    if installed_versions is not None:
        return str(installed_versions.get(normalized) or installed_versions.get(name) or "")
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return ""


def build_payload(
    requirement_files: Sequence[str | Path] = DEFAULT_REQUIREMENTS_FILES,
    *,
    optional_requirement_profiles: Mapping[str, Sequence[str | Path]] | None = None,
    installed_versions: Mapping[str, str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    parsed = read_requirements(requirement_files)
    requirements: list[dict[str, Any]] = []
    lock_lines: list[str] = []
    missing_packages: list[dict[str, Any]] = []
    unpinned_requirements: list[dict[str, Any]] = []
    loose_source_requirements = list(parsed["loose_source_requirements"])

    def _resolve_requirement_rows(
        rows: Sequence[Mapping[str, Any]], *, profile: str, blocking: bool
    ) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], list[dict[str, Any]]]:
        resolved_rows: list[dict[str, Any]] = []
        resolved_lock_lines: list[str] = []
        resolved_missing: list[dict[str, Any]] = []
        resolved_unpinned: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, tuple[str, ...]]] = set()
        for row in rows:
            installed = _installed_version(str(row["name"]), installed_versions=installed_versions)
            key = (str(row["normalized_name"]), tuple(row["extras"]))
            lock_name = str(row["normalized_name"])
            if row["extras"]:
                lock_name = f"{lock_name}[{','.join(sorted(row['extras']))}]"
            lock_line = f"{lock_name}=={installed}" if installed else ""
            resolved = {
                **row,
                "profile": profile,
                "blocking": blocking,
                "installed_version": installed,
                "lock_line": lock_line,
                "status": "installed" if installed else "missing",
            }
            resolved_rows.append(resolved)
            if not row["pinned_exact"] or row["source_requirement"]:
                resolved_unpinned.append(resolved)
            if not installed:
                resolved_missing.append(resolved)
            elif key not in seen_keys:
                resolved_lock_lines.append(lock_line)
                seen_keys.add(key)
        return resolved_rows, resolved_lock_lines, resolved_missing, resolved_unpinned

    base_rows, base_lock_lines, missing_packages, unpinned_requirements = _resolve_requirement_rows(
        parsed["requirements"], profile="delivery", blocking=True
    )
    for row in base_rows:
        requirements.append(row)
    lock_lines.extend(base_lock_lines)

    optional_profiles_input = (
        {str(name): list(files) for name, files in optional_requirement_profiles.items()}
        if optional_requirement_profiles is not None
        else _default_optional_requirement_profiles()
    )
    optional_profiles: dict[str, dict[str, Any]] = {}
    optional_requirements: list[dict[str, Any]] = []
    optional_missing_packages: list[dict[str, Any]] = []
    optional_unpinned_requirements: list[dict[str, Any]] = []
    optional_lock_lines: list[str] = []
    for profile_name, profile_files in sorted(optional_profiles_input.items()):
        optional_parsed = read_requirements(profile_files)
        rows, profile_lock_lines, profile_missing, profile_unpinned = _resolve_requirement_rows(
            optional_parsed["requirements"], profile=profile_name, blocking=False
        )
        profile_missing_input_count = sum(1 for row in optional_parsed["input_files"] if not row["exists"])
        profile_loose_sources = list(optional_parsed["loose_source_requirements"])
        optional_profiles[profile_name] = {
            "requirement_files": optional_parsed["input_files"],
            "declared_count": len(rows),
            "installed_count": sum(1 for row in rows if row["installed_version"]),
            "missing_count": len(profile_missing),
            "lock_line_count": len(profile_lock_lines),
            "unpinned_count": len(profile_unpinned),
            "loose_source_requirement_count": len(profile_loose_sources),
            "missing_input_file_count": profile_missing_input_count,
            "missing_package_install_targets": sorted(
                {str(row["display_name"]) for row in profile_missing}, key=str.casefold
            ),
            "lock_lines": sorted(profile_lock_lines, key=str.casefold),
            "requirements": rows,
            "missing_packages": profile_missing,
            "unpinned_requirements": profile_unpinned,
            "loose_source_requirements": profile_loose_sources,
            "delivery_blocking": False,
        }
        optional_requirements.extend(rows)
        optional_missing_packages.extend(profile_missing)
        optional_unpinned_requirements.extend(profile_unpinned)
        optional_lock_lines.extend(profile_lock_lines)

    lock_lines = sorted(lock_lines, key=str.casefold)
    optional_lock_lines = sorted(set(optional_lock_lines), key=str.casefold)
    raw_lock_text = "\n".join(lock_lines) + ("\n" if lock_lines else "")
    normalized_lock_text = raw_lock_text
    runtime_info = _runtime_info()
    git_info = _git_info()
    frozen_distributions = _installed_distributions(installed_versions)
    installed_count = sum(1 for row in requirements if row["installed_version"])
    missing_count = len(missing_packages)
    loose_count = len(loose_source_requirements)
    unpinned_count = len(unpinned_requirements)
    missing_input_count = sum(1 for row in parsed["input_files"] if not row["exists"])
    missing_package_names = [str(row["display_name"]) for row in missing_packages]
    missing_package_install_targets = sorted(set(missing_package_names), key=str.casefold)
    optional_missing_package_names = [str(row["display_name"]) for row in optional_missing_packages]
    optional_deferred_install_targets = sorted(set(optional_missing_package_names), key=str.casefold)
    loose_source_values = [str(row["raw"]) for row in loose_source_requirements]
    unpinned_requirement_names = [str(row["display_name"]) for row in unpinned_requirements]
    unpinned_pin_suggestions = [
        {
            "name": str(row["display_name"]),
            "source": _source_ref(row),
            "current_requirement": str(row["raw"]),
            "installed_version": str(row.get("installed_version", "")),
            "suggested_requirement": (
                f"{row['display_name']}=={row['installed_version']}" if row.get("installed_version") else ""
            ),
        }
        for row in unpinned_requirements
    ]
    incomplete_reasons: list[str] = []
    if missing_count:
        incomplete_reasons.append(f"missing_packages={_preview(missing_package_install_targets)}")
    if loose_count:
        incomplete_reasons.append(f"loose_source_requirements={_preview(loose_source_values)}")
    if missing_input_count:
        missing_files = [str(row["relative_path"]) for row in parsed["input_files"] if not row["exists"]]
        incomplete_reasons.append(f"missing_requirement_files={_preview(missing_files)}")
    if missing_count or loose_count or missing_input_count:
        status_line = (
            f"incomplete: installed={installed_count}/{len(requirements)} "
            f"missing={missing_count} loose_sources={loose_count} missing_files={missing_input_count}"
        )
        action_parts = []
        if missing_package_install_targets:
            action_parts.append(f"install or remove missing packages: {_preview(missing_package_install_targets)}")
        if loose_source_values:
            action_parts.append(f"replace loose/source entries with package pins: {_preview(loose_source_values)}")
        if missing_input_count:
            action_parts.append("restore or remove missing requirement input files")
        next_required_step = (
            "; ".join(action_parts)
            + ". Then rebuild this lock before paid local delivery."
        )
    elif unpinned_count:
        status_line = f"complete_with_unpinned_inputs: lock_lines={len(lock_lines)} unpinned_inputs={unpinned_count}"
        next_required_step = "Use the generated txt lock artifact for local delivery reproduction."
    else:
        status_line = f"complete: lock_lines={len(lock_lines)}"
        next_required_step = "Use the generated txt lock artifact for local delivery reproduction."

    summary = {
        "declared_count": len(requirements),
        "installed_count": installed_count,
        "missing_count": missing_count,
        "blocking_missing_count": missing_count,
        "lock_line_count": len(lock_lines),
        "unpinned_count": unpinned_count,
        "loose_source_requirement_count": loose_count,
        "missing_input_file_count": missing_input_count,
        "incomplete_reason_count": len(incomplete_reasons),
        "incomplete_reasons": incomplete_reasons,
        "missing_package_names": missing_package_names,
        "missing_package_install_targets": missing_package_install_targets,
        "optional_profile_count": len(optional_profiles),
        "optional_declared_count": len(optional_requirements),
        "optional_installed_count": sum(1 for row in optional_requirements if row["installed_version"]),
        "optional_missing_count": len(optional_missing_packages),
        "optional_lock_line_count": len(optional_lock_lines),
        "optional_deferred_install_targets": optional_deferred_install_targets,
        "optional_profiles": {
            name: {
                "declared_count": profile["declared_count"],
                "installed_count": profile["installed_count"],
                "missing_count": profile["missing_count"],
                "lock_line_count": profile["lock_line_count"],
                "unpinned_count": profile["unpinned_count"],
                "loose_source_requirement_count": profile["loose_source_requirement_count"],
                "missing_input_file_count": profile["missing_input_file_count"],
                "missing_package_install_targets": profile["missing_package_install_targets"],
                "delivery_blocking": False,
            }
            for name, profile in optional_profiles.items()
        },
        "loose_source_requirements": loose_source_values,
        "unpinned_requirement_names": unpinned_requirement_names,
        "unpinned_pin_suggestions": unpinned_pin_suggestions,
        "installed_distribution_count": len(frozen_distributions),
        "raw_lock_text_sha256": _sha256_text(raw_lock_text),
        "normalized_lock_text_sha256": _sha256_text(normalized_lock_text),
        "python_executable": runtime_info["python"]["executable"],
        "python_version": runtime_info["python"]["version"],
        "pip_available": runtime_info["pip"]["available"],
        "platform_tag": (
            f"{runtime_info['platform']['system']} "
            f"{runtime_info['platform']['release']} "
            f"{runtime_info['platform']['machine']}"
        ).strip(),
        "git_commit": git_info["commit"],
        "git_short_commit": git_info["short_commit"],
        "git_dirty": git_info["dirty"],
        "requirements_lock_complete": bool(missing_count == 0 and loose_count == 0 and missing_input_count == 0),
        "status_line": status_line,
        "next_required_step": next_required_step,
    }
    return {
        "generated_at": generated_at or _now_local(),
        "runtime": runtime_info,
        "git": git_info,
        "requirement_files": parsed["input_files"],
        "summary": summary,
        "requirements": requirements,
        "lock_lines": lock_lines,
        "optional_profiles": optional_profiles,
        "optional_requirements": optional_requirements,
        "optional_lock_lines": optional_lock_lines,
        "frozen_distributions": frozen_distributions,
        "hashes": {
            "raw_lock_text_sha256": summary["raw_lock_text_sha256"],
            "normalized_lock_text_sha256": summary["normalized_lock_text_sha256"],
        },
        "missing_packages": missing_packages,
        "optional_missing_packages": optional_missing_packages,
        "unpinned_requirements": unpinned_requirements,
        "optional_unpinned_requirements": optional_unpinned_requirements,
        "loose_source_requirements": loose_source_requirements,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Delivery Requirements Lock",
        "",
        f"- status_line: `{summary['status_line']}`",
        f"- declared_count: `{summary['declared_count']}`",
        f"- installed_count: `{summary['installed_count']}`",
        f"- missing_count: `{summary['missing_count']}`",
        f"- optional_missing_count: `{summary.get('optional_missing_count', 0)}`",
        f"- lock_line_count: `{summary['lock_line_count']}`",
        f"- optional_lock_line_count: `{summary.get('optional_lock_line_count', 0)}`",
        f"- unpinned_count: `{summary['unpinned_count']}`",
        f"- loose_source_requirement_count: `{summary['loose_source_requirement_count']}`",
        f"- missing_input_file_count: `{summary['missing_input_file_count']}`",
        f"- incomplete_reason_count: `{summary.get('incomplete_reason_count', 0)}`",
        f"- missing_package_install_targets: `{', '.join(summary.get('missing_package_install_targets', []) or []) or '-'}`",
        f"- optional_deferred_install_targets: `{', '.join(summary.get('optional_deferred_install_targets', []) or []) or '-'}`",
        f"- installed_distribution_count: `{summary['installed_distribution_count']}`",
        f"- python_version: `{summary['python_version']}`",
        f"- python_executable: `{summary['python_executable']}`",
        f"- pip_available: `{summary['pip_available']}`",
        f"- platform_tag: `{summary['platform_tag']}`",
        f"- git_short_commit: `{summary['git_short_commit'] or '-'}`",
        f"- git_dirty: `{summary['git_dirty']}`",
        f"- normalized_lock_text_sha256: `{summary['normalized_lock_text_sha256']}`",
        f"- next_required_step: {summary['next_required_step']}",
        "",
        "## Lock Lines",
        "",
    ]
    if payload["lock_lines"]:
        lines.extend(f"- `{line}`" for line in payload["lock_lines"])
    else:
        lines.append("- none")
    lines.extend(["", "## Optional Deferred Profiles", ""])
    optional_profiles = dict(payload.get("optional_profiles", {}) or {})
    if optional_profiles:
        lines.extend(
            [
                "| profile | declared | installed | missing | deferred_install_targets |",
                "| --- | ---: | ---: | ---: | --- |",
            ]
        )
        for profile_name, profile in sorted(optional_profiles.items()):
            lines.append(
                f"| `{profile_name}` | {profile.get('declared_count', 0)} | {profile.get('installed_count', 0)} | "
                f"{profile.get('missing_count', 0)} | "
                f"`{', '.join(profile.get('missing_package_install_targets', []) or []) or '-'}` |"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Missing Packages", ""])
    if payload["missing_packages"]:
        for row in payload["missing_packages"]:
            lines.append(
                f"- `{row['display_name']}` from `{row['source_file_relative']}:{row['line_number']}`; "
                f"install/pin target: `{row['display_name']}`"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Optional Missing Packages", ""])
    if payload.get("optional_missing_packages"):
        for row in payload["optional_missing_packages"]:
            lines.append(
                f"- `{row['display_name']}` from `{row['source_file_relative']}:{row['line_number']}` "
                f"(profile: `{row.get('profile', 'optional')}`, delivery_blocking: `False`)"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Unpinned Or Source Inputs", ""])
    if payload["unpinned_requirements"] or payload["loose_source_requirements"]:
        for row in payload["unpinned_requirements"]:
            suggested = (
                f"{row['display_name']}=={row['installed_version']}" if row.get("installed_version") else "missing"
            )
            lines.append(
                f"- `{row['raw']}` from `{row['source_file_relative']}:{row['line_number']}`; "
                f"suggested pin: `{suggested}`"
            )
        for row in payload["loose_source_requirements"]:
            lines.append(f"- `{row['raw']}` from `{row['source_file_relative']}:{row['line_number']}`")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def render_lock_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local delivery requirements lock",
        f"# status: {summary['status_line']}",
        f"# normalized_lock_text_sha256: {summary['normalized_lock_text_sha256']}",
        f"# next_required_step: {summary['next_required_step']}",
        "",
    ]
    lines.extend(payload["lock_lines"])
    if payload.get("optional_profiles"):
        lines.extend(["", "# Optional/deferred profiles not required for base local delivery"])
        for profile_name, profile in sorted((payload.get("optional_profiles") or {}).items()):
            targets = ", ".join(profile.get("missing_package_install_targets", []) or []) or "-"
            lines.append(f"# OPTIONAL_PROFILE {profile_name} missing={profile.get('missing_count', 0)} targets={targets}")
            for lock_line in profile.get("lock_lines", []) or []:
                lines.append(f"# OPTIONAL_LOCK {profile_name} {lock_line}")
    if payload["missing_packages"]:
        lines.extend(["", "# Missing packages not locked"])
        for row in payload["missing_packages"]:
            lines.append(f"# MISSING {row['display_name']} from {row['source_file_relative']}:{row['line_number']}")
    if payload["unpinned_requirements"]:
        lines.extend(["", "# Unpinned or source package inputs resolved to installed versions"])
        for row in payload["unpinned_requirements"]:
            lines.append(f"# INPUT {row['raw']} from {row['source_file_relative']}:{row['line_number']}")
    if payload["loose_source_requirements"]:
        lines.extend(["", "# Loose/source requirements not locked"])
        for row in payload["loose_source_requirements"]:
            lines.append(f"# SOURCE {row['raw']} from {row['source_file_relative']}:{row['line_number']}")
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_text(path_like: str | Path, text: str) -> None:
    path = Path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_outputs(payload: dict[str, Any], *, out_json: str | Path, out_md: str | Path, out_txt: str | Path) -> None:
    _write_json(out_json, payload)
    _write_text(out_md, render_markdown(payload))
    _write_text(out_txt, render_lock_text(payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build an offline local-delivery requirements lock from declared requirement files and "
            "currently installed package versions."
        )
    )
    parser.add_argument(
        "--requirements-file",
        action="append",
        dest="requirements_files",
        default=[],
        help="Requirement file to read. May be provided multiple times. Defaults to requirements.txt and requirements-dev.txt.",
    )
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON))
    parser.add_argument("--out-md", default=str(DEFAULT_OUT_MD))
    parser.add_argument("--out-txt", default=str(DEFAULT_OUT_TXT))
    parser.add_argument("--enforce-complete", action=argparse.BooleanOptionalAction, default=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requirement_files = args.requirements_files or list(DEFAULT_REQUIREMENTS_FILES)
    payload = build_payload(requirement_files)
    write_outputs(payload, out_json=args.out_json, out_md=args.out_md, out_txt=args.out_txt)
    incomplete = bool(
        payload["summary"]["missing_count"]
        or payload["summary"]["loose_source_requirement_count"]
        or payload["summary"]["missing_input_file_count"]
    )
    if args.enforce_complete and incomplete:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
