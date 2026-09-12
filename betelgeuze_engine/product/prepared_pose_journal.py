"""Local durable completion journal, not a scheduler or scientific approval.

An exclusive request lock complements (and does not replace) the API job store's
worker lease. Only fully committed per-pose results are reused. Input bytes,
request, implementation and numerical environment must still match. SQLite
transactions make a killed writer leave either a complete row or no row.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sqlite3
import stat
import sys

SCHEMA = "prepared_rigid_pose_completion_journal_v1"
MAX_SOURCE_BYTES = 16 * 1024 * 1024


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_checkpoint_json_key")
        result[key] = value
    return result


def _decode(text):
    return json.loads(text, object_pairs_hook=_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_checkpoint_json")))


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            data = stream.read(65536)
            if not data:
                return digest.hexdigest()
            digest.update(data)


def _source_refs(value):
    if isinstance(value, dict):
        if set(value) == {"path", "sha256", "source_id"}:
            yield value
        else:
            for child in value.values():
                yield from _source_refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _source_refs(child)


def _input_binding(request):
    bound = []
    for ref in _source_refs(request.get("prepared_input", {})):
        path = Path(ref["path"])
        if not path.is_absolute():
            raise ValueError("checkpoint_requires_absolute_source_paths")
        # Missing/invalid sources can produce durable failed rows, but changing
        # their availability later requires a NEW run, not resume under old input.
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        except FileNotFoundError:
            bound.append({"declaration": ref, "observed": "missing"})
            continue
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SOURCE_BYTES:
                raise ValueError("checkpoint_requires_bounded_regular_sources")
            digest = hashlib.sha256()
            size = 0
            while True:
                block = stream.read(65536)
                if not block:
                    break
                size += len(block)
                if size > MAX_SOURCE_BYTES:
                    raise ValueError("checkpoint_source_exceeds_capacity")
                digest.update(block)
            after = os.fstat(stream.fileno())
            current = path.stat()
            def signature(st):
                return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            if signature(before) != signature(after) or signature(after) != signature(current):
                raise ValueError("checkpoint_source_changed_during_read")
            bound.append({"declaration": ref, "observed": "regular_file",
                          "size": size, "sha256": digest.hexdigest()})
    return bound


def _runtime_binding():
    import torch

    root = Path(__file__).resolve().parents[2]
    sources = {}
    # Conservative transitive package binding, including Python code imported
    # lazily by the existing evaluator. No historical V2 manifest is resealed.
    for package in ("betelgeuze_engine", "betelgeuze_engine_v2", "betelgeuze_product", "core"):
        for path in sorted((root / package).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".so", ".pyd"}:
                sources[str(path.relative_to(root))] = _file_hash(path)
    consumer = root / "tools/product/score_prepared_cross_interactions.py"
    if consumer.is_file():
        sources[str(consumer.relative_to(root))] = _file_hash(consumer)
    dependencies = {}
    for name in ("torch", "numpy", "rdkit"):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    return {"backend": "cpu", "precision": "float64", "python": sys.version,
            "platform": platform.platform(), "machine": platform.machine(),
            "dependencies": dependencies, "torch_threads": torch.get_num_threads(),
            "torch_interop_threads": torch.get_num_interop_threads(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "default_dtype": str(torch.get_default_dtype()),
            "torch_build": torch.__config__.show(), "sources": sources}


class PoseJournal:
    """Private local storage; hashes detect corruption, not hostile forgery."""

    def __init__(self, directory, request, *, resume=False):
        self.directory = Path(directory)
        self.request = _decode(_json(request))
        self.resume = resume
        self.connection = None
        self.lock_fd = self.directory_fd = None
        self.restored = 0

    def __enter__(self):
        try:
            if not self.resume:
                self.directory.mkdir(mode=0o700)  # existing journals never overwritten
            self.directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            st = os.fstat(self.directory_fd)
            if st.st_uid != os.geteuid() or st.st_mode & 0o077:
                raise ValueError("checkpoint_directory_must_be_private_owned_directory")
            self.lock_fd = os.open(".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                   0o600, dir_fd=self.directory_fd)
            self._regular_single_link(os.fstat(self.lock_fd))
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("checkpoint_request_already_running") from exc
            dbname = "completion.sqlite3"
            if self.resume:
                self._regular_single_link(os.stat(dbname, dir_fd=self.directory_fd, follow_symlinks=False))
            else:
                fd = os.open(dbname, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self.directory_fd)
                os.close(fd)
                os.fsync(self.directory_fd)
            # Anchor the SQLite path to the open directory; renaming or swapping
            # the caller's directory path cannot redirect journal writes.
            self.connection = sqlite3.connect(f"/proc/self/fd/{self.directory_fd}/{dbname}", timeout=0)
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA journal_mode=DELETE")
            if self.connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("checkpoint_database_integrity_failure")
            self.inputs = _input_binding(self.request)
            self.runtime = _runtime_binding()
            contract = {"schema_version": SCHEMA, "request": self.request,
                        "inputs": self.inputs, "runtime": self.runtime}
            self.contract_text = _json(contract)
            self.contract_digest = _digest(self.contract_text)
            if not self.resume:
                with self.connection:
                    self.connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    self.connection.execute("CREATE TABLE poses (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)")
                    self.connection.executemany("INSERT INTO meta VALUES (?,?)", [
                        ("contract", self.contract_text), ("contract_digest", self.contract_digest),
                        ("completed_count", "0"), ("shared", "null"), ("shared_digest", _digest("null")),
                        ("attempts", "0"), ("execution", "null"), ("execution_digest", _digest("null"))])
            if (self._meta("contract") != self.contract_text
                    or self._meta("contract_digest") != self.contract_digest):
                raise ValueError("checkpoint_request_input_runtime_mismatch")
            shared_text = self._meta("shared")
            if _digest(shared_text) != self._meta("shared_digest"):
                raise ValueError("checkpoint_shared_payload_corrupt")
            self.shared = _decode(shared_text)
            execution_text = self._meta("execution")
            if _digest(execution_text) != self._meta("execution_digest"):
                raise ValueError("checkpoint_execution_payload_corrupt")
            self.execution = _decode(execution_text)
            self.rows = {}
            count = int(self._meta("completed_count"))
            for expected, (ordinal, text, digest) in enumerate(self.connection.execute(
                    "SELECT ordinal,payload,digest FROM poses ORDER BY ordinal")):
                if ordinal != expected or _digest(text) != digest:
                    raise ValueError("checkpoint_row_corrupt_or_noncontiguous")
                row = _decode(text)
                if (row.get("request_index") != ordinal or row.get("status") not in {"evaluated", "failed"}
                        or (row["status"] == "evaluated" and (row.get("evaluation_completed") is not True
                                                             or not isinstance(row.get("result"), dict)))):
                    raise ValueError("checkpoint_invalid_completed_row")
                if ordinal >= len(self.request["poses"]):
                    raise ValueError("checkpoint_contains_unrequested_row")
                self.rows[ordinal] = row
            if len(self.rows) != count:
                raise ValueError("checkpoint_completed_count_mismatch")
            self.attempt = int(self._meta("attempts")) + 1
            with self.connection:
                self._set("attempts", str(self.attempt))
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    @staticmethod
    def _regular_single_link(st):
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.geteuid():
            raise ValueError("checkpoint_requires_owned_single_link_regular_file")

    def _meta(self, key):
        row = self.connection.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            raise ValueError("checkpoint_metadata_missing")
        return row[0]

    def _set(self, key, value):
        self.connection.execute("UPDATE meta SET value=? WHERE key=?", (value, key))

    def check_inputs(self):
        if _input_binding(self.request) != self.inputs:
            raise ValueError("checkpoint_source_changed")

    def restore(self, ordinal):
        row = self.rows.get(ordinal)
        if row is not None:
            self.check_inputs()
            self.restored += 1
            return _decode(_json(row))
        return None

    def commit(self, row, shared, execution):
        self.check_inputs()
        ordinal = row["request_index"]
        if ordinal != len(self.rows):
            raise ValueError("checkpoint_commit_out_of_order")
        text, shared_text, execution_text = _json(row), _json(shared), _json(execution)
        # Row, original geometry and committed count change in one transaction.
        with self.connection:
            self.connection.execute("INSERT INTO poses VALUES (?,?,?)", (ordinal, text, _digest(text)))
            self._set("shared", shared_text)
            self._set("shared_digest", _digest(shared_text))
            self._set("completed_count", str(ordinal + 1))
            self._set("execution", execution_text)
            self._set("execution_digest", _digest(execution_text))
        self.rows[ordinal] = _decode(text)
        self.shared = _decode(shared_text)
        self.execution = _decode(execution_text)

    def observation(self):
        self.check_inputs()
        if _runtime_binding() != self.runtime:
            raise ValueError("checkpoint_runtime_changed_during_execution")
        return {"schema_version": SCHEMA, "contract_sha256": self.contract_digest,
                "attempt": self.attempt, "restored_rows": self.restored,
                "newly_completed_rows": len(self.rows) - self.restored,
                "completed_rows": len(self.rows), "terminal_failures_retried": False,
                "previous_row_costs_preserved": True,
                "current_preparation_observations_scope": "this_invocation_only",
                "local_integrity_only_not_source_authentication": True}

    def __exit__(self, *_):
        if self.connection is not None:
            self.connection.close()
            self.connection = None
        if self.lock_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self.lock_fd)
            self.lock_fd = None
        if self.directory_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self.directory_fd)
            self.directory_fd = None


def evaluate_with_journal(request, checkpoint_dir, *, resume=False):
    from .prepared_rigid_poses import SCHEMA as REQUEST_SCHEMA, _evaluate_rigid_pose_request
    if (type(request) is not dict or request.get("schema_version") != REQUEST_SCHEMA
            or type(request.get("poses")) is not list or not 1 <= len(request["poses"]) <= 32):
        raise ValueError("checkpoint_supported_only_for_explicit_rigid_pose_request")
    with PoseJournal(checkpoint_dir, request, resume=resume) as journal:
        report = _evaluate_rigid_pose_request(request, journal=journal)
        report["resume_observation"] = journal.observation()
        report["preparation_observation"]["numerical_results_reused"] = journal.restored > 0
        return report
