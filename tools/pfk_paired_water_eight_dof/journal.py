"""Durable, budgeted stages for the fixed PFK paired experiment.

Every stage is reserved before its callable. An incomplete or damaged journal
is unknown work and is never eligible for automatic continuation.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time


SCHEMA = "pfk_paired_water_dispatch/1.0.0"


class DispatchError(RuntimeError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class StageJournal:
    """One fresh process/arm; poisoned instances cannot issue further work."""

    def __init__(self, path, caps, stop_check=lambda: None):
        self.path = Path(path)
        self.caps = dict(caps)
        if not self.caps or any(type(v) is not int or v < 0 for v in self.caps.values()):
            raise DispatchError("invalid dispatch caps")
        # There is no resume or overwrite path. The directory must preexist.
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        self.serial = 0
        self.chain = "0" * 64
        self.started = Counter()
        self.pending = {}
        self.poisoned = False
        self.publication_uncertain = False
        self.stop_check = stop_check
        self.t0 = time.monotonic()
        try:
            parent = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            self.poisoned = True
            os.close(self.fd)
            self.fd = None
            raise

    def _append(self, event):
        document = {"schema": SCHEMA, "previous_sha256": self.chain,
                    "elapsed_seconds": time.monotonic() - self.t0, **event}
        checksum = digest(document)
        data = (canonical({**document, "record_sha256": checksum}) + "\n").encode("utf-8")
        try:
            view = memoryview(data)
            while view:
                count = os.write(self.fd, view)
                if count <= 0:
                    raise OSError("zero-byte journal write")
                view = view[count:]
            os.fsync(self.fd)
        except BaseException:
            self.poisoned = True
            self.publication_uncertain = True
            raise
        self.chain = checksum

    def event(self, kind, event, success=None):
        if self.poisoned or self.fd is None:
            raise DispatchError("dispatch journal unusable; retry forbidden")
        if kind not in self.caps:
            raise DispatchError("unplanned dispatch kind")
        if event == "started":
            self.stop_check()
            if kind in self.pending or self.started[kind] >= self.caps[kind]:
                raise DispatchError("overlapping or exhausted dispatch")
            self.serial += 1
            # Reserve in memory BEFORE writing: fsync may fail after a complete
            # start row becomes visible. Never let that failure look reusable.
            self.pending[kind] = self.serial
            self.started[kind] += 1
            self._append({"id": self.serial, "kind": kind, "event": event, "success": None})
        elif event == "finished":
            if kind not in self.pending or type(success) is not bool:
                raise DispatchError("unpaired dispatch finish")
            self._append({"id": self.pending[kind], "kind": kind,
                          "event": event, "success": success})
            del self.pending[kind]
            if not success:
                self.poisoned = True
        else:
            raise DispatchError("unknown dispatch event")

    def invoke(self, kind, function, *args, **kwargs):
        self.event(kind, "started")
        try:
            value = function(*args, **kwargs)
        except BaseException:
            # A durable failed finish records the attempted stage; the whole
            # instance remains poisoned even if that publication also fails.
            try:
                self.event(kind, "finished", False)
            finally:
                self.poisoned = True
            raise
        self.event(kind, "finished", True)
        return value

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def inspect(path, caps):
    """Reconcile complete durable records, independently of worker memory."""
    data = Path(path).read_bytes()
    lines = data.split(b"\n")
    tail = len(lines[-1])
    counts = {key: {name: 0 for name in ("started", "finished", "succeeded", "failed")}
              for key in caps}
    pending = {}
    seen = set()
    chain = "0" * 64
    errors = []
    for number, raw in enumerate(lines[:-1], 1):
        try:
            row = json.loads(raw)
            declared = row.pop("record_sha256")
            if declared != digest(row) or row["previous_sha256"] != chain or row["schema"] != SCHEMA:
                raise DispatchError("journal chain mismatch")
            kind, identity = row["kind"], row["id"]
            if kind not in counts or type(identity) is not int or identity < 1:
                raise DispatchError("unplanned kind or invalid id")
            if row["event"] == "started":
                if identity in seen or kind in pending or row["success"] is not None:
                    raise DispatchError("duplicate/overlapping reservation")
                if counts[kind]["started"] >= caps[kind]:
                    raise DispatchError("dispatch cap exceeded")
                seen.add(identity)
                pending[kind] = identity
                counts[kind]["started"] += 1
            else:
                if row["event"] != "finished" or pending.get(kind) != identity or type(row["success"]) is not bool:
                    raise DispatchError("unpaired finish")
                del pending[kind]
                counts[kind]["finished"] += 1
                counts[kind]["succeeded" if row["success"] else "failed"] += 1
            chain = declared
        except (ValueError, KeyError, TypeError, DispatchError) as exc:
            errors.append({"line": number, "error": str(exc)})
            break
    known = not tail and not pending and not errors
    return {"counts": counts, "pending": pending, "partial_tail_bytes": tail,
            "errors": errors, "total_work_known": known,
            "known_started_calls": sum(row["started"] for row in counts.values()),
            "total_started_calls": sum(row["started"] for row in counts.values()) if known else None,
            "automatic_retry_admitted": False, "last_verified_record_sha256": chain}
