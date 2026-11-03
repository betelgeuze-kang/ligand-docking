"""Standard-library process supervision and atomic phase journals for development."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import sys
import tempfile
import threading
import time


class IsolationError(RuntimeError):
    pass


class CleanupError(IsolationError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = record


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest_json(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def digest_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value, *, replace=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise IsolationError("atomic evidence path is a symlink")
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".pending", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(canonical(value) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        if replace:
            os.replace(temp, path)
        else:
            os.link(temp, path)  # atomic, and never overwrites an existing event
            temp.unlink()
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)


class AtomicJournal:
    """An immutable event is committed before its replaceable checkpoint."""

    def __init__(self, directory, identity, *, max_bytes=64 * 1024 * 1024, max_events=10000):
        if type(max_bytes) is not int or max_bytes <= 0 or type(max_events) is not int or max_events <= 0:
            raise ValueError("positive journal budgets required")
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.max_bytes, self.max_events = max_bytes, max_events
        self.sequence, self.bytes, self.previous = 0, 0, None
        self.identity = json.loads(canonical(identity))
        self.identity_sha256 = digest_json(self.identity)
        atomic_json(self.directory / "identity.json", self.identity, replace=False)

    def emit(self, event):
        if not isinstance(event, dict):
            raise TypeError("journal event must be a dictionary")
        payload = {"schema_id": "betelgeuze.redocking_phase_journal_event/1.0.0",
                   "journal_sequence": self.sequence + 1, "identity_sha256": self.identity_sha256,
                   "previous_event_sha256": self.previous, "event": event}
        event_hash = digest_json(payload)
        payload["event_sha256"] = event_hash
        size = len(canonical(payload)) + 1
        if self.sequence >= self.max_events or self.bytes + size > self.max_bytes:
            raise IsolationError("phase journal budget exceeded")
        name = f"event-{self.sequence + 1:06d}.json"
        atomic_json(self.directory / name, payload, replace=False)
        atomic_json(self.directory / "checkpoint.json", {
            "schema_id": "betelgeuze.redocking_phase_checkpoint/1.0.0",
            "identity_sha256": self.identity_sha256, "last_sequence": self.sequence + 1,
            "event_path": name, "event_sha256": event_hash, "event_bytes_total": self.bytes + size,
            "last_event": event})
        self.sequence += 1
        self.bytes += size
        self.previous = event_hash

    @contextmanager
    def stage(self, name, **details):
        started = time.monotonic()
        self.emit({"stage": name, "phase": "start", "details": details})
        try:
            yield
        except BaseException as exc:
            self.emit({"stage": name, "phase": "error", "elapsed_seconds": time.monotonic() - started,
                       "details": {"exception_type": type(exc).__name__, "message": str(exc)}})
            raise
        else:
            self.emit({"stage": name, "phase": "complete", "elapsed_seconds": time.monotonic() - started,
                       "details": details})


def read_checkpoint(directory):
    directory = Path(directory)
    path = directory / "checkpoint.json"
    if not path.exists():
        return None
    checkpoint = json.loads(path.read_bytes())
    if checkpoint["event_path"] != f"event-{checkpoint['last_sequence']:06d}.json":
        raise IsolationError("invalid checkpoint event path")
    event = json.loads((directory / checkpoint["event_path"]).read_bytes())
    claimed = event.pop("event_sha256")
    identity = json.loads((directory / "identity.json").read_bytes())
    if (digest_json(event) != claimed or claimed != checkpoint["event_sha256"]
            or digest_json(identity) != checkpoint["identity_sha256"]
            or event["identity_sha256"] != checkpoint["identity_sha256"]
            or event["journal_sequence"] != checkpoint["last_sequence"]
            or event["event"] != checkpoint["last_event"]):
        raise IsolationError("checkpoint integrity mismatch")
    return checkpoint


@dataclass(frozen=True)
class Limits:
    wall_seconds: float
    rss_bytes: int = 6 * 1024 ** 3
    poll_seconds: float = .25
    log_bytes: int = 8 * 1024 ** 2
    terminate_grace_seconds: float = 1.0
    cleanup_seconds: float = 3.0

    def __post_init__(self):
        for name in ("wall_seconds", "poll_seconds", "terminate_grace_seconds", "cleanup_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {name}")
        if self.poll_seconds > 1:
            raise ValueError("poll interval must be at most one second")
        for name in ("rss_bytes", "log_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"invalid {name}")


@dataclass(frozen=True)
class ProcessInfo:
    pid: int  # procfs PID, which can differ from the signal namespace PID
    parent: int
    start: int
    rss: int
    state: str


def _proc_info(pid):
    text = Path("/proc", str(pid), "stat").read_text()
    fields = text[text.rfind(")") + 2:].split()
    return ProcessInfo(pid, int(fields[1]), int(fields[19]),
                       max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE"), fields[0])


def proc_snapshot():
    records = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            pid = int(path.parent.name)
            records[pid] = _proc_info(pid)
        except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError, IndexError):
            continue
    return records


def _status_ids(pid):
    fields = {}
    for line in Path("/proc", str(pid), "status").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("NSpid", "NSpgid"):
            fields[key] = [int(x) for x in value.split()]
    return fields


class ProcessTree:
    def __init__(self):
        if sys.platform != "linux":
            raise IsolationError("Linux procfs and subreaper support required")
        self.owner = int(os.readlink("/proc/self"))
        ids = _status_ids(self.owner)["NSpid"]
        if not ids or ids[-1] != os.getpid():
            raise IsolationError("cannot establish controller PID namespace")
        self.depth = len(ids) - 1
        self.existing = {(p.pid, p.start) for p in proc_snapshot().values() if p.parent == self.owner}
        self.tracked = {}

    def active(self):
        snapshot = proc_snapshot()
        for pid, start in self.tracked.items():
            if pid not in snapshot:
                try:
                    current = _proc_info(pid)
                except (FileNotFoundError, ProcessLookupError):
                    continue
                # Permission/parsing errors for a tracked process are fatal.
                if current.start == start:
                    snapshot[pid] = current
        ids = {p.pid for p in snapshot.values() if p.parent == self.owner
               and (p.pid, p.start) not in self.existing}
        ids.update(pid for pid, start in self.tracked.items()
                   if pid in snapshot and snapshot[pid].start == start)
        while True:
            children = {p.pid for p in snapshot.values() if p.parent in ids}
            if children <= ids:
                break
            ids |= children
        active = {pid: snapshot[pid] for pid in ids if pid in snapshot}
        self.tracked.update((pid, p.start) for pid, p in active.items())
        return active

    def local_pid(self, info):
        try:
            if _proc_info(info.pid).start != info.start:
                return None
            ids = _status_ids(info.pid)
        except (FileNotFoundError, ProcessLookupError):
            return None
        if len(ids.get("NSpid", ())) <= self.depth:
            raise IsolationError("descendant is outside controller signal namespace")
        return ids["NSpid"][self.depth]

    def signal(self, sig):
        for info in self.active().values():
            if info.state == "Z":
                continue
            pid = self.local_pid(info)
            if pid is None or pid == os.getpid():
                continue
            fd = None
            try:
                fd = os.pidfd_open(pid)
                if _proc_info(info.pid).start == info.start:
                    signal.pidfd_send_signal(fd, sig)
            except (FileNotFoundError, ProcessLookupError):
                pass
            finally:
                if fd is not None:
                    os.close(fd)

    def reap(self, root_pid):
        for info in self.active().values():
            if info.state != "Z":
                continue
            pid = self.local_pid(info)
            if pid is None or pid == root_pid:
                continue
            try:
                os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                pass


@contextmanager
def _subreaper():
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) != 0:
        raise IsolationError("cannot read child subreaper state")
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise IsolationError("cannot enable child subreaper")
    try:
        yield
    finally:
        if libc.prctl(36, previous.value, 0, 0, 0) != 0:
            raise IsolationError("cannot restore child subreaper state")


class _Logs:
    def __init__(self, process, directory, limit):
        self.selector = selectors.DefaultSelector()
        self.handles, self.counts = {}, {}
        self.directory, self.limit = directory, limit
        try:
            for name in ("stdout", "stderr"):
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                self.selector.register(stream, selectors.EVENT_READ, name)
                self.handles[name] = (directory / (name + ".log")).open("xb")
                self.counts[name] = {"bytes_seen": 0, "bytes_retained": 0,
                                     "eof_observed": False, "path": name + ".log"}
        except BaseException:
            self.selector.close()
            for handle in self.handles.values():
                handle.close()
            raise

    def drain(self, wait=0):
        # One block per stream per poll: flooding cannot starve deadlines.
        for key, _ in self.selector.select(wait):
            try:
                block = os.read(key.fd, 65536)
            except BlockingIOError:
                continue
            if not block:
                self.counts[key.data]["eof_observed"] = True
                self.selector.unregister(key.fileobj)
                key.fileobj.close()
                continue
            row = self.counts[key.data]
            keep = block[:max(0, self.limit - row["bytes_retained"])]
            self.handles[key.data].write(keep)
            row["bytes_seen"] += len(block)
            row["bytes_retained"] += len(keep)

    def finish(self):
        deadline = time.monotonic() + 1
        while self.selector.get_map() and time.monotonic() < deadline:
            self.drain(.01)
        for key in list(self.selector.get_map().values()):
            self.selector.unregister(key.fileobj)
            key.fileobj.close()
        self.selector.close()
        for name, f in self.handles.items():
            f.flush()
            os.fsync(f.fileno())
            f.close()
            row = self.counts[name]
            row["bytes_discarded"] = row["bytes_seen"] - row["bytes_retained"]
            row["truncated"] = row["bytes_discarded"] > 0
            row["retained_sha256"] = digest_file(self.directory / row["path"])
        return self.counts


_SUPERVISION_LOCK = threading.Lock()


def _cleanup(process, tree, logs, limits):
    def drain():
        if logs is None:
            time.sleep(.01)
        else:
            # A failed output device must not prevent TERM/KILL of descendants.
            try:
                logs.drain(.01)
            except (OSError, ValueError) as exc:
                logs.cleanup_capture_error = str(exc)
                time.sleep(.01)
    tree.signal(signal.SIGTERM)
    grace = time.monotonic() + limits.terminate_grace_seconds
    while time.monotonic() < grace:
        drain()
        process.poll()
        tree.reap(process.pid)
        if not any(p.state != "Z" for p in tree.active().values()):
            break
    deadline = time.monotonic() + limits.cleanup_seconds
    while True:
        tree.signal(signal.SIGKILL)
        process.poll()
        tree.reap(process.pid)
        live = [p for p in tree.active().values() if p.state != "Z"]
        if not live and process.poll() is not None:
            process.wait()
            tree.reap(process.pid)
            return
        if time.monotonic() >= deadline:
            raise IsolationError("live descendants survived bounded cleanup")
        drain()


def supervise(command, directory, limits, *, cwd=None, env=None):
    """Run one worker; cleanup failure is fatal to the entire engine sequence."""
    if not command or any(not isinstance(x, str) or "\0" in x for x in command):
        raise ValueError("command must be a nonempty argv")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if directory.is_symlink() or any((directory / n).exists() for n in
                                    ("stdout.log", "stderr.log", "process-execution.json")):
        raise IsolationError("process output is not fresh")
    if not _SUPERVISION_LOCK.acquire(blocking=False):
        raise IsolationError("concurrent supervision in one controller is unsupported")
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process = logs = tree = None
    reason, cleanup_complete, peak, error, interrupted = "not_started", True, 0, None, None
    try:
        with _subreaper():
            tree = ProcessTree()
            try:
                process = subprocess.Popen(list(command), cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           start_new_session=True)
                logs = _Logs(process, directory, limits.log_bytes)
                reason, sampled_at = "exited", -math.inf
                while True:
                    now = time.monotonic()
                    if now - sampled_at >= limits.poll_seconds:
                        peak = max(peak, sum(p.rss for p in tree.active().values()))
                        sampled_at = now
                    if process.poll() is not None:
                        if any(p.state != "Z" for p in tree.active().values()):
                            reason = "remaining_descendants_terminated"
                            _cleanup(process, tree, logs, limits)
                        break
                    elapsed = now - started
                    if elapsed > limits.wall_seconds or peak > limits.rss_bytes:
                        reason = "wall_timeout" if elapsed > limits.wall_seconds else "sampled_rss_limit"
                        _cleanup(process, tree, logs, limits)
                        break
                    logs.drain(min(limits.poll_seconds, .05))
                process.wait()
                tree.reap(process.pid)
            except BaseException as exc:
                error = {"exception_type": type(exc).__name__, "message": str(exc)}
                interrupted = exc if isinstance(exc, (KeyboardInterrupt, SystemExit)) else None
                reason = "supervision_error"
                if process is not None:
                    try:
                        _cleanup(process, tree, logs, limits)
                    except BaseException as cleanup_exc:
                        cleanup_complete, reason = False, "cleanup_failed"
                        error["cleanup_error"] = str(cleanup_exc)
    finally:
        try:
            if logs is None and process is not None:
                for name in ("stdout", "stderr"):
                    getattr(process, name).close()
            try:
                streams = {} if logs is None else logs.finish()
            except (OSError, ValueError) as exc:
                streams = {}
                error = {**(error or {}), "stream_finalization_error": str(exc)}
                if cleanup_complete:
                    reason = "supervision_error"
            if logs is not None and hasattr(logs, "cleanup_capture_error"):
                error = {**(error or {}), "cleanup_stream_error": logs.cleanup_capture_error}
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            record = {"schema_id": "betelgeuze.redocking_process_execution/1.0.0",
                "command": list(command), "returncode": None if process is None else process.returncode,
                "termination": reason, "cleanup_complete": cleanup_complete,
                "wall_seconds": time.monotonic() - started,
                "child_cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                "sampled_peak_process_tree_rss_bytes": peak, "rss_sampling_seconds": limits.poll_seconds,
                "rss_limit_bytes": limits.rss_bytes, "wall_limit_seconds": limits.wall_seconds,
                "supervision_scope": "observed procfs descendants plus adopted orphans; no cgroup containment",
                "rss_measurement": "sum of observed descendant RSS; shared pages may be counted multiple times",
                "procfs_namespace_depth": None if tree is None else tree.depth,
                "error": error, "streams": streams}
            record["control_sha256"] = digest_json(record)
            atomic_json(directory / "process-execution.json", record, replace=False)
        finally:
            _SUPERVISION_LOCK.release()
    if not cleanup_complete:
        raise CleanupError("worker cleanup could not be confirmed", record)
    if interrupted is not None:
        raise interrupted
    return record


def run_engine_sequence(commands, directory, limits, *, inputs_ready=True, cwd=None, env=None):
    """Control-only orchestration; never fabricates a scientific execution row."""
    results = {}
    for engine in ("engine_v2", "vina", "gnina"):
        if not inputs_ready:
            results[engine] = {"termination": "not_started", "reason": "materialization_not_verified",
                               "returncode": None, "cleanup_complete": True}
        else:
            results[engine] = supervise(commands[engine], Path(directory) / engine,
                                        limits[engine], cwd=cwd, env=env)
    return results
