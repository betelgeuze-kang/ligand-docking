from __future__ import annotations

import datetime as dt
import hashlib
import os
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Mapping, Sequence


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _tail_lines(value: Any, *, limit: int = 40) -> str:
    return "\n".join(_text(value).splitlines()[-int(max(1, limit)) :])


def _env_float(name: str, default: float) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except ValueError:
        return float(default)


def _cmd_digest(cmd: Sequence[str]) -> str:
    raw = "\0".join(str(part) for part in cmd).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def _artifact_paths(cmd: Sequence[str], *, log_path: str | None = None) -> tuple[str, str]:
    explicit = str(log_path or "").strip()
    if explicit:
        path = Path(explicit)
        path.parent.mkdir(parents=True, exist_ok=True)
        stem = path.with_suffix("")
        return f"{stem}.stdout.log", f"{stem}.stderr.log"

    log_dir = str(os.environ.get("BETELGEUZE_SUBPROCESS_LOG_DIR", "") or "").strip()
    if not log_dir:
        return "", ""
    root = Path(log_dir)
    root.mkdir(parents=True, exist_ok=True)
    digest = _cmd_digest(cmd)[:16]
    return str(root / f"{digest}.stdout.log"), str(root / f"{digest}.stderr.log")


def _write_if_requested(path: str, value: Any) -> str:
    dst = str(path or "").strip()
    if not dst:
        return ""
    p = Path(dst)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_text(value), encoding="utf-8")
    return str(p)


def _classify_failure(*, returncode: int, timed_out: bool, stdout: Any, stderr: Any) -> str:
    if timed_out:
        return "timeout"
    if int(returncode) == 0:
        return ""
    joined = f"{_text(stdout)}\n{_text(stderr)}".lower()
    if int(returncode) == 127 or "no such file or directory" in joined or "not found" in joined:
        return "missing_executable"
    if "no module named" in joined or "modulenotfounderror" in joined or "importerror" in joined:
        return "missing_dependency"
    if "required csv missing" in joined or "file not found" in joined or "filenotfounderror" in joined:
        return "input_contract"
    if "production_strict_inputs_failed" in joined or "strict input" in joined:
        return "input_contract"
    if "failed_metrics" in joined or "gate" in joined:
        return "science_gate"
    return "unknown"


def run_cmd(
    cmd: Sequence[str],
    *,
    timeout_s: float | None = None,
    env_overrides: Mapping[str, str] | None = None,
    log_path: str | None = None,
) -> dict[str, Any]:
    """Run a subprocess with fail-closed timeout and log artifacts.

    The return shape intentionally preserves the historical ``_run_cmd`` fields
    consumed by ``htvs_pipeline.py`` while adding P0 operational fields:
    ``timed_out``, ``timeout_sec``, ``failure_class``, ``stdout_path``, and
    ``stderr_path``.
    """

    parts = [str(part) for part in cmd]
    timeout = float(timeout_s if timeout_s is not None else _env_float("BETELGEUZE_SUBPROCESS_TIMEOUT_SEC", 3600.0))
    timeout = max(timeout, 0.001)
    t0 = time.time()
    started = dt.datetime.now().isoformat(timespec="seconds")
    stdout = ""
    stderr = ""
    returncode = 0
    timed_out = False
    env = os.environ.copy()
    if env_overrides:
        env.update({str(k): str(v) for k, v in env_overrides.items()})

    try:
        proc = subprocess.run(parts, text=True, capture_output=True, timeout=timeout, env=env)
        stdout = _text(proc.stdout)
        stderr = _text(proc.stderr)
        returncode = int(proc.returncode)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = _text(exc.stdout)
        stderr = _text(exc.stderr)
        timeout_msg = f"subprocess timed out after {timeout:.3f}s: {shlex.join(parts)}"
        stderr = f"{stderr}\n{timeout_msg}" if stderr else timeout_msg
    except FileNotFoundError as exc:
        returncode = 127
        stderr = f"FileNotFoundError: {exc}"
    except Exception as exc:  # pragma: no cover - defensive runner contract
        returncode = 1
        stderr = f"{type(exc).__name__}: {exc}"

    t1 = time.time()
    ended = dt.datetime.now().isoformat(timespec="seconds")
    stdout_path, stderr_path = _artifact_paths(parts, log_path=log_path)
    stdout_path = _write_if_requested(stdout_path, stdout)
    stderr_path = _write_if_requested(stderr_path, stderr)
    failure_class = _classify_failure(
        returncode=int(returncode),
        timed_out=bool(timed_out),
        stdout=stdout,
        stderr=stderr,
    )
    return {
        "cmd": parts,
        "cmd_str": shlex.join(parts),
        "cmd_sha256": _cmd_digest(parts),
        "ok": bool(returncode == 0 and not timed_out),
        "returncode": int(returncode),
        "started_at_local": started,
        "ended_at_local": ended,
        "duration_sec": float(max(t1 - t0, 0.0)),
        "timeout_sec": float(timeout),
        "timed_out": bool(timed_out),
        "failure_class": failure_class,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "stdout_tail": _tail_lines(stdout),
        "stderr_tail": _tail_lines(stderr),
    }
