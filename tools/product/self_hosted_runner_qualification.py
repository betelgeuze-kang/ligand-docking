#!/usr/bin/env python3
"""Qualify a self-hosted GitHub Actions runner for Node 24 based Actions.

The trusted workflow deliberately keeps setup-python v5 until a real runner
receipt demonstrates that its Actions runner satisfies the Node 24 minimum.
This tool discovers the installed Runner.Listener, records its exact version and
binary digest, and fails closed when the version cannot be established.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

QUALIFICATION_SCHEMA_VERSION = "self_hosted_runner_qualification_v1"
NODE24_MINIMUM_RUNNER_VERSION = (2, 327, 1)
_VERSION_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
MAX_LISTENER_BYTES = 256 * 1024 * 1024


class RunnerQualificationError(RuntimeError):
    """Raised when the runner identity cannot be established safely."""


def parse_runner_version(value: Any) -> tuple[int, int, int]:
    text = str(value or "").strip()
    match = _VERSION_RE.fullmatch(text)
    if match is None:
        raise ValueError("runner version must be semantic major.minor.patch")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def version_text(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def version_at_least(
    observed: tuple[int, int, int],
    minimum: tuple[int, int, int] = NODE24_MINIMUM_RUNNER_VERSION,
) -> bool:
    return observed >= minimum


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    file_fd = os.open(path, flags)
    digest = hashlib.sha256()
    try:
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise RunnerQualificationError("runner listener is not a regular file")
        if before.st_size <= 0 or before.st_size > MAX_LISTENER_BYTES:
            raise RunnerQualificationError("runner listener size is outside the qualification bound")
        observed = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            observed += len(chunk)
            if observed > MAX_LISTENER_BYTES:
                raise RunnerQualificationError("runner listener size is outside the qualification bound")
            digest.update(chunk)
        after = os.fstat(file_fd)
        identity_before = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        identity_after = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity_before != identity_after or observed != before.st_size:
            raise RunnerQualificationError("runner listener changed during qualification")
        return digest.hexdigest(), observed
    finally:
        os.close(file_fd)


def _candidate_listener_paths(
    *,
    runner_root: str | Path | None,
    environment: Mapping[str, str],
    parent_pid: int | None,
) -> Iterable[Path]:
    seen: set[Path] = set()

    def emit(path: Path) -> Iterable[Path]:
        normalized = Path(os.path.abspath(str(path.expanduser())))
        if normalized not in seen:
            seen.add(normalized)
            yield normalized

    explicit_roots: list[Path] = []
    if runner_root:
        explicit_roots.append(Path(runner_root))
    for key in ("ACTIONS_RUNNER_ROOT", "RUNNER_ROOT"):
        value = str(environment.get(key, "") or "").strip()
        if value:
            explicit_roots.append(Path(value))
    for root in explicit_roots:
        yield from emit(root / "bin" / "Runner.Listener")
        yield from emit(root / "Runner.Listener")

    if os.name != "posix" or not Path("/proc").is_dir():
        return
    pid = int(parent_pid if parent_pid is not None else os.getppid())
    visited: set[int] = set()
    for _ in range(16):
        if pid <= 1 or pid in visited:
            break
        visited.add(pid)
        try:
            executable = Path(os.readlink(f"/proc/{pid}/exe"))
        except OSError:
            executable = Path()
        if executable:
            yield from emit(executable.parent / "Runner.Listener")
            yield from emit(executable.parent.parent / "bin" / "Runner.Listener")
        try:
            stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
            pid = int(stat_fields[3])
        except (OSError, ValueError, IndexError):
            break


def discover_runner_listener(
    *,
    runner_root: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    parent_pid: int | None = None,
) -> Path:
    env = dict(os.environ if environment is None else environment)
    for candidate in _candidate_listener_paths(
        runner_root=runner_root,
        environment=env,
        parent_pid=parent_pid,
    ):
        try:
            metadata = candidate.lstat()
        except OSError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            continue
        if os.access(candidate, os.X_OK):
            return candidate
    raise RunnerQualificationError("Runner.Listener executable could not be discovered")


def listener_version(listener: Path) -> str:
    completed = subprocess.run(
        [str(listener), "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        raise RunnerQualificationError("Runner.Listener --version failed")
    candidates = [token.strip() for line in output.splitlines() for token in line.split()]
    for token in reversed(candidates):
        try:
            return version_text(parse_runner_version(token))
        except ValueError:
            continue
    raise RunnerQualificationError("Runner.Listener did not return a semantic version")


def build_qualification_receipt(
    *,
    observed_version: str,
    version_source: str,
    listener_sha256: str = "",
    listener_size_bytes: int = 0,
    environment: Mapping[str, str] | None = None,
    observed_at_utc: str | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    parsed = parse_runner_version(observed_version)
    minimum = NODE24_MINIMUM_RUNNER_VERSION
    qualified = version_at_least(parsed, minimum)
    runner_name = str(env.get("RUNNER_NAME", "") or "")
    body: dict[str, Any] = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "status": (
            "qualified_node24_actions_runtime"
            if qualified
            else "blocked_node24_actions_runtime_runner_too_old"
        ),
        "qualified": qualified,
        "observed_runner_version": version_text(parsed),
        "minimum_runner_version": version_text(minimum),
        "version_source": str(version_source),
        "runner_listener_sha256": str(listener_sha256),
        "runner_listener_size_bytes": int(listener_size_bytes),
        "runner_name_sha256": hashlib.sha256(runner_name.encode("utf-8")).hexdigest() if runner_name else "",
        "runner_os": str(env.get("RUNNER_OS", "") or ""),
        "runner_arch": str(env.get("RUNNER_ARCH", "") or ""),
        "github_run_id": str(env.get("GITHUB_RUN_ID", "") or ""),
        "github_run_attempt": str(env.get("GITHUB_RUN_ATTEMPT", "") or ""),
        "github_sha": str(env.get("GITHUB_SHA", "") or ""),
        "observed_at_utc": observed_at_utc
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "node24_action_runtime_required": True,
        "setup_python_v6_qualified": qualified,
        "claim_boundary": (
            "Runner software compatibility receipt only. It does not qualify scientific results, "
            "GPU parity, product execution, customer delivery, or commercial readiness."
        ),
    }
    body["receipt_sha256"] = hashlib.sha256(_canonical_bytes(body)).hexdigest()
    return body


def write_receipt(path: str | Path, receipt: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(dict(receipt), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    file_fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        os.fchmod(file_fd, 0o600)
        with os.fdopen(file_fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        try:
            os.close(file_fd)
        except OSError:
            pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise
    return destination


def qualify_runner(
    *,
    observed_version: str = "",
    runner_root: str | Path | None = None,
    environment: Mapping[str, str] | None = None,
    parent_pid: int | None = None,
    observed_at_utc: str | None = None,
) -> dict[str, Any]:
    env = dict(os.environ if environment is None else environment)
    explicit = str(observed_version or "").strip()
    listener_sha256 = ""
    listener_size = 0
    if explicit:
        version = version_text(parse_runner_version(explicit))
        source = "explicit_argument"
    else:
        env_version = str(env.get("ACTIONS_RUNNER_VERSION", "") or "").strip()
        if env_version:
            version = version_text(parse_runner_version(env_version))
            source = "ACTIONS_RUNNER_VERSION"
        else:
            listener = discover_runner_listener(
                runner_root=runner_root,
                environment=env,
                parent_pid=parent_pid,
            )
            version = listener_version(listener)
            listener_sha256, listener_size = _sha256_file(listener)
            source = "Runner.Listener"
    return build_qualification_receipt(
        observed_version=version,
        version_source=source,
        listener_sha256=listener_sha256,
        listener_size_bytes=listener_size,
        environment=env,
        observed_at_utc=observed_at_utc,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observed-version", default="")
    parser.add_argument("--runner-root", default="")
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--observed-at-utc", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = qualify_runner(
            observed_version=args.observed_version,
            runner_root=args.runner_root or None,
            observed_at_utc=args.observed_at_utc or None,
        )
    except (OSError, ValueError, RunnerQualificationError, subprocess.SubprocessError) as exc:
        print(f"self_hosted_runner_qualification=blocked:{type(exc).__name__}:{exc}")
        return 1
    destination = write_receipt(args.receipt, receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(f"self_hosted_runner_qualification_receipt={destination}")
    return 0 if receipt["qualified"] is True else 1


if __name__ == "__main__":
    sys.exit(main())
