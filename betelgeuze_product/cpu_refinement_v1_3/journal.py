"""Durable append-only trial evidence, separate from solver/retry semantics.

Replay is a single bounded pass. Appending never rereads previous events or
checkpoints. A torn line or partial publication is retained and rejected; this
module never truncates a journal, retries work, or repairs unknown work.
"""
from __future__ import annotations

import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat

from ..cpu_refinement_v1_2.provenance import ResearchError, canonical, digest

MAX_JOURNAL_BYTES = 128 * 1024 * 1024
MAX_RECORD_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 32768
KINDS = frozenset({"objective_started", "objective_finished", "restart_started", "restart_finished"})
_FLAGS = os.O_NOFOLLOW | os.O_CLOEXEC
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | _FLAGS
_CHECKPOINT = re.compile(r"checkpoint-([0-9]{5})\.json\Z")


def _require(condition, reason):
    if not condition:
        raise ResearchError(reason)


def _json_value(value, depth=0):
    _require(depth <= 64, "journal JSON nesting capacity exceeded")
    if type(value) is dict:
        _require(all(type(key) is str for key in value), "journal JSON string keys required")
        for child in value.values():
            _json_value(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _json_value(child, depth + 1)
    else:
        _require(type(value) in {str, int, float, bool, type(None)}, "journal JSON scalar required")
        if type(value) is float:
            _require(math.isfinite(value), "journal nonfinite JSON value")


def _encode(value):
    _json_value(value)
    try:
        raw = (canonical(value) + "\n").encode("ascii")
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ResearchError("invalid journal JSON") from exc
    _require(len(raw) <= MAX_RECORD_BYTES, "journal record capacity exceeded")
    return raw


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "duplicate journal JSON key")
        result[key] = value
    return result


def _decode(raw):
    _require(len(raw) <= MAX_RECORD_BYTES and raw.endswith(b"\n"), "truncated or oversized journal record")
    try:
        value = json.loads(raw, object_pairs_hook=_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ResearchError("nonfinite journal JSON")))
        _require(_encode(value) == raw, "noncanonical journal JSON")
        return value
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError) as exc:
        raise ResearchError("invalid or noncanonical journal JSON") from exc


def _copy_dict(value):
    _require(type(value) is dict, "journal dictionary payload required")
    return _decode(_encode(value))


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _private_directory(fd):
    info = os.fstat(fd)
    _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
             and not info.st_mode & 0o077, "private owned journal directory required")


def _regular(fd, limit):
    info = os.fstat(fd)
    _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
             and info.st_uid == os.geteuid() and not info.st_mode & 0o077,
             "private single-link journal file required")
    _require(info.st_size <= limit, "journal file capacity exceeded")
    return info


def _write_all(fd, raw):
    remaining = memoryview(raw)
    while remaining:
        written = os.write(fd, remaining)
        _require(written > 0, "journal write made no progress")
        remaining = remaining[written:]


def _names(directory_fd, limit):
    names = set()
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            _require(len(names) < limit, "journal directory entry capacity exceeded")
            names.add(entry.name)
    return names


def _read_file(directory_fd, name):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | _FLAGS, dir_fd=directory_fd)
    try:
        before = _regular(fd, MAX_RECORD_BYTES)
        chunks, size = [], 0
        while True:
            chunk = os.read(fd, min(65536, MAX_RECORD_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            _require(size <= MAX_RECORD_BYTES, "journal record capacity exceeded")
        after = os.fstat(fd)
        current = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        _require(_identity(before) == _identity(after) == _identity(current)
                 and size == before.st_size, "journal file changed during read")
        return _decode(b"".join(chunks)), _identity(after)
    finally:
        os.close(fd)


def _publish(directory_fd, name, value):
    """Publish once without replacement; retain interrupted bytes for diagnosis."""
    raw = _encode(value)
    temporary = "." + name + ".partial"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _FLAGS, 0o600, dir_fd=directory_fd)
    try:
        _write_all(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    # link is no-clobber publication. A crash before unlink retains a partial
    # artifact and is explicitly blocked on replay, never silently repaired.
    os.link(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd, follow_symlinks=False)
    os.unlink(temporary, dir_fd=directory_fd)
    os.fsync(directory_fd)


class TrialJournal:
    """One private directory and exclusive writer lock for the entire context.

    ``events`` is a detached replay snapshot; use ``event_count``/``head_sha256``
    in hot loops instead of repeatedly copying all prior payloads.
    """

    def __init__(self, directory: Path, binding: dict, create: bool):
        _require(type(create) is bool, "explicit journal create flag required")
        self.directory = Path(directory)
        self._binding = _copy_dict(binding)
        self._binding_sha256 = digest(self._binding)
        self._create = create
        self._fds = []
        self._chain = []
        self._lock_fd = self._journal_fd = self._root_fd = self._checkpoints_fd = None
        self._events = []
        self._checkpoints = {}
        self._latest_count = None
        self._latest_checkpoint = None
        self._latest_stat = self._result_stat = None
        self._result = None
        self._active = self._used = self._poisoned = False

    @property
    def events(self):
        self._require_active()
        return [_copy_dict(event) for event in self._events]

    @property
    def checkpoint_digests(self):
        """Detached prefix-to-digest index for one-pass semantic replay."""
        self._require_active()
        return dict(self._checkpoints)

    @property
    def event_count(self):
        self._require_active()
        return len(self._events)

    @property
    def head_sha256(self):
        self._require_active()
        return self._head(len(self._events))

    def _head(self, count):
        return self._events[count - 1]["event_sha256"] if count else self._binding_sha256

    def _require_active(self):
        _require(self._active and not self._poisoned, "journal lock is closed or session is damaged")

    def _open_path(self):
        _require(self.directory.is_absolute() and ".." not in self.directory.parts
                 and 1 < len(self.directory.parts) <= 128, "absolute journal path without traversal required")
        parent = os.open("/", _DIRECTORY)
        self._fds.append(parent)
        for index, component in enumerate(self.directory.parts[1:]):
            leaf = index == len(self.directory.parts) - 2
            if leaf and self._create:
                os.mkdir(component, mode=0o700, dir_fd=parent)
                os.fsync(parent)
            child = os.open(component, _DIRECTORY, dir_fd=parent)
            self._fds.append(child)
            info = os.fstat(child)
            self._chain.append((parent, component, (info.st_dev, info.st_ino)))
            parent = child
        self._root_fd = parent
        _private_directory(parent)

    def __enter__(self):
        _require(not self._used, "journal context cannot be reused")
        self._used = True
        try:
            self._open_path()
            flags = os.O_RDWR | _FLAGS
            self._lock_fd = os.open(".journal.lock", flags | (os.O_CREAT | os.O_EXCL if self._create else 0),
                                    0o600, dir_fd=self._root_fd)
            _regular(self._lock_fd, 0)
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self._create:
                os.fsync(self._lock_fd)
                _publish(self._root_fd, "meta.json", {"schema_id": "cartesian_trial_journal/1.0.0",
                    "binding": self._binding, "binding_sha256": self._binding_sha256})
                os.mkdir("checkpoints", mode=0o700, dir_fd=self._root_fd)
            self._checkpoints_fd = os.open("checkpoints", _DIRECTORY, dir_fd=self._root_fd)
            _private_directory(self._checkpoints_fd)
            self._journal_fd = os.open("events.jsonl", flags | os.O_APPEND |
                                       (os.O_CREAT | os.O_EXCL if self._create else 0),
                                       0o600, dir_fd=self._root_fd)
            if self._create:
                os.fsync(self._journal_fd)
                os.fsync(self._checkpoints_fd)
                os.fsync(self._root_fd)
            self._remember()
            self._replay()
            self._active = True
            self._guard()
            return self
        except BaseException:
            self._close()
            raise

    def _replay(self):
        names = _names(self._root_fd, 5)
        _require(names <= {".journal.lock", "meta.json", "checkpoints", "events.jsonl", "result.json"},
                 "unexpected or partial journal files")
        meta, self._meta_stat = _read_file(self._root_fd, "meta.json")
        _require(canonical(meta) == canonical({"schema_id": "cartesian_trial_journal/1.0.0",
                 "binding": self._binding, "binding_sha256": self._binding_sha256}), "journal binding changed")
        before = _regular(self._journal_fd, MAX_JOURNAL_BYTES)
        total = 0
        with os.fdopen(os.dup(self._journal_fd), "rb") as stream:
            stream.seek(0)
            while True:
                raw = stream.readline(MAX_RECORD_BYTES + 1)
                if not raw:
                    break
                total += len(raw)
                _require(total <= MAX_JOURNAL_BYTES, "journal byte capacity exceeded")
                _require(len(self._events) < MAX_EVENTS, "journal event capacity exceeded")
                event = _decode(raw)
                _require(type(event) is dict and set(event) == {
                    "index", "kind", "payload", "previous_sha256", "event_sha256"}, "invalid journal event fields")
                _require(type(event["index"]) is int and event["index"] == len(self._events)
                         and type(event["kind"]) is str and event["kind"] in KINDS
                         and type(event["payload"]) is dict,
                         "journal event order or kind mismatch")
                _require(event["previous_sha256"] == self._head(len(self._events))
                         and event["event_sha256"] == digest({k: v for k, v in event.items() if k != "event_sha256"}),
                         "journal event hash chain mismatch")
                self._events.append(event)
        _require(_identity(before) == _identity(os.fstat(self._journal_fd)) ==
                 _identity(os.stat("events.jsonl", dir_fd=self._root_fd, follow_symlinks=False)),
                 "journal changed during replay")
        checkpoint_names = _names(self._checkpoints_fd, MAX_EVENTS + 1)
        for name in checkpoint_names:
            match = _CHECKPOINT.fullmatch(name)
            _require(match is not None, "unexpected or partial checkpoint files")
            checkpoint, checkpoint_stat = _read_file(self._checkpoints_fd, name)
            self._validate_checkpoint(checkpoint)
            count = checkpoint["journal_count"]
            _require(int(match[1]) == count and count not in self._checkpoints,
                     "checkpoint filename or prefix conflict")
            self._checkpoints[count] = checkpoint["checkpoint_sha256"]
            if self._latest_count is None or count > self._latest_count:
                self._latest_count, self._latest_stat = count, checkpoint_stat
                self._latest_checkpoint = checkpoint
        if "result.json" in names:
            result, self._result_stat = _read_file(self._root_fd, "result.json")
            _require(type(result) is dict and set(result) == {
                "journal_count", "journal_sha256", "result", "result_sha256"}, "invalid journal result fields")
            self._validate_prefix(result)
            _require(result["journal_count"] == len(self._events) and type(result["result"]) is dict
                     and result["result_sha256"] == digest({k: v for k, v in result.items() if k != "result_sha256"}),
                     "journal result digest or terminal prefix mismatch")
            self._result = result

    def _validate_prefix(self, value):
        count = value["journal_count"]
        _require(type(count) is int and 0 <= count <= len(self._events)
                 and value["journal_sha256"] == self._head(count), "checkpoint or result journal prefix mismatch")

    def _validate_checkpoint(self, value):
        _require(type(value) is dict and set(value) == {
            "journal_count", "journal_sha256", "state", "checkpoint_sha256"}, "invalid journal checkpoint fields")
        self._validate_prefix(value)
        _require(type(value["state"]) is dict and value["checkpoint_sha256"] ==
                 digest({k: v for k, v in value.items() if k != "checkpoint_sha256"}), "checkpoint digest mismatch")

    def _remember(self):
        self._root_stat = _identity(os.fstat(self._root_fd))
        self._checkpoints_stat = _identity(os.fstat(self._checkpoints_fd))
        self._journal_stat = _identity(os.fstat(self._journal_fd))
        self._lock_stat = _identity(os.fstat(self._lock_fd))

    def _guard(self):
        self._require_active()
        for parent, name, expected in self._chain:
            info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            _require(stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == expected,
                     "journal parent path changed or became a symlink")
        for fd, name, expected in ((self._journal_fd, "events.jsonl", self._journal_stat),
                                   (self._lock_fd, ".journal.lock", self._lock_stat),
                                   (self._checkpoints_fd, "checkpoints", self._checkpoints_stat)):
            _require(_identity(os.fstat(fd)) == expected ==
                     _identity(os.stat(name, dir_fd=self._root_fd, follow_symlinks=False)), "journal storage changed")
        _require(_identity(os.fstat(self._root_fd)) == self._root_stat and
                 _identity(os.stat("meta.json", dir_fd=self._root_fd, follow_symlinks=False)) == self._meta_stat,
                 "journal directory or metadata changed")
        if self._latest_count is not None:
            name = f"checkpoint-{self._latest_count:05d}.json"
            _require(_identity(os.stat(name, dir_fd=self._checkpoints_fd, follow_symlinks=False)) ==
                     self._latest_stat, "latest checkpoint changed")
        if self._result_stat is not None:
            _require(_identity(os.stat("result.json", dir_fd=self._root_fd, follow_symlinks=False)) ==
                     self._result_stat, "journal result changed")

    def append(self, kind, payload):
        self._guard()
        _require(self._result is None, "journal already finalized")
        _require(type(kind) is str and kind in KINDS, "unsupported journal event kind")
        _require(len(self._events) < MAX_EVENTS, "journal event capacity exceeded")
        value = {"index": len(self._events), "kind": kind, "payload": _copy_dict(payload),
                 "previous_sha256": self._head(len(self._events))}
        event = {**value, "event_sha256": digest(value)}
        raw = _encode(event)
        expected_size = self._journal_stat[6] + len(raw)
        _require(expected_size <= MAX_JOURNAL_BYTES, "journal byte capacity exceeded")
        try:
            _write_all(self._journal_fd, raw)
            os.fsync(self._journal_fd)
            _require(os.fstat(self._journal_fd).st_size == expected_size, "journal changed during append")
            self._journal_stat = _identity(_regular(self._journal_fd, MAX_JOURNAL_BYTES))
            self._guard()
        except BaseException:
            self._poisoned = True
            raise
        self._events.append(event)
        return _copy_dict(event)

    def save_checkpoint(self, state):
        self._guard()
        _require(self._result is None, "journal already finalized")
        value = {"journal_count": len(self._events), "journal_sha256": self._head(len(self._events)),
                 "state": _copy_dict(state)}
        checkpoint = {**value, "checkpoint_sha256": digest(value)}
        count = len(self._events)
        if count in self._checkpoints:
            _require(self._checkpoints[count] == checkpoint["checkpoint_sha256"],
                     "immutable checkpoint prefix already exists")
            return _copy_dict(checkpoint)
        try:
            _publish(self._checkpoints_fd, f"checkpoint-{count:05d}.json", checkpoint)
            self._checkpoints_stat = _identity(os.fstat(self._checkpoints_fd))
            self._guard()
        except BaseException:
            self._poisoned = True
            raise
        self._checkpoints[count] = checkpoint["checkpoint_sha256"]
        self._latest_count = count
        self._latest_checkpoint = checkpoint
        self._latest_stat = _identity(os.stat(f"checkpoint-{count:05d}.json",
                                             dir_fd=self._checkpoints_fd, follow_symlinks=False))
        return _copy_dict(checkpoint)

    def latest_checkpoint(self):
        self._guard()
        return _copy_dict(self._latest_checkpoint) if self._latest_count is not None else None

    def publish_result(self, result):
        self._guard()
        value = {"journal_count": len(self._events), "journal_sha256": self._head(len(self._events)),
                 "result": _copy_dict(result)}
        envelope = {**value, "result_sha256": digest(value)}
        if self._result is not None:
            _require(self._result == envelope, "immutable journal result already exists")
            return
        try:
            _publish(self._root_fd, "result.json", envelope)
            self._root_stat = _identity(os.fstat(self._root_fd))
            self._guard()
        except BaseException:
            self._poisoned = True
            raise
        self._result = envelope
        self._result_stat = _identity(os.stat("result.json", dir_fd=self._root_fd, follow_symlinks=False))

    def result(self):
        self._guard()
        return _copy_dict(self._result["result"]) if self._result is not None else None

    def _close(self):
        self._active = False
        for fd in (self._journal_fd, self._checkpoints_fd, self._lock_fd, *reversed(self._fds)):
            if fd is not None:
                os.close(fd)
        self._journal_fd = self._checkpoints_fd = self._lock_fd = None
        self._fds = []

    def __exit__(self, *_):
        self._close()
