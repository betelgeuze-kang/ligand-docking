"""Shared, local-admission-only prepared Fourier research job authority.

This registry is distinct from generic retry queues. A lost owner or unfinished
numerical invocation is never automatically acquired again. Public methods do
not import Torch, evaluate forces, accept paths, or launch arbitrary commands.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import platform
import re
import secrets
import sqlite3
import stat
import sys
import time
import uuid

SCHEMA = "prepared_lifecycle/1.0.0"
ADMISSION_SCHEMA = "prepared_local_admission/1.0.0"
REFS = ("ligand", "receptor", "parameters", "cross", "source_evidence")
POLICY = {"wall_seconds": 300, "cpu_seconds": 300, "address_space_bytes": 4 * 1024**3,
          "file_bytes": 64 * 1024**2, "output_bytes": 200 * 1024**2,
          "capture_bytes": 1024**2, "cpu_threads": 1,
          "max_numerical_invocations": 2}
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_TENANT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}\Z")
_KEY = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class LifecycleError(ValueError):
    def __init__(self, code, message, http_status=400, retry_allowed=False):
        super().__init__(message)
        self.code, self.message = code, message
        self.http_status, self.retry_allowed = http_status, retry_allowed

    def document(self):
        return {"schema_version": "prepared_lifecycle_error/1.0.0",
                "error": {"code": self.code, "message": self.message,
                          "retry_allowed": self.retry_allowed},
                "research_only": True, "qualified": False}


def require(value, code, message, status=400):
    if not value:
        raise LifecycleError(code, message, status)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def _absolute(path):
    path = Path(path)
    require(path.is_absolute() and os.path.normpath(str(path)) == str(path),
            "INVALID_CONFIGURATION", "A normalized absolute configured path is required", 503)
    return path


def _directory_fd(path):
    path = _absolute(path)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def private_root(path, *, create=False):
    path = _absolute(path)
    if create and not path.exists():
        parent = _directory_fd(path.parent)
        try:
            try:
                os.mkdir(path.name, 0o700, dir_fd=parent)
            except FileExistsError:
                pass  # Another constructor won; validate the existing directory below.
            os.fsync(parent)
        finally:
            os.close(parent)
    fd = _directory_fd(path)
    try:
        info = os.fstat(fd)
        require(info.st_uid == os.geteuid() and not info.st_mode & 0o077,
                "INVALID_CONFIGURATION", "Configured storage must be private and locally owned", 503)
    finally:
        os.close(fd)
    return path


def regular_bytes(path, root, *, maximum=64 * 1024**2):
    path, root = _absolute(path), _absolute(root)
    require(path.is_relative_to(root), "INVALID_ADMISSION", "Input is outside the configured admission root")
    parent = _directory_fd(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= maximum,
                "INVALID_ADMISSION", "A bounded private regular input is required")
        data = handle.read(maximum + 1)
        require(len(data) <= maximum, "INVALID_ADMISSION", "Input size limit exceeded")
        return data


def json_bytes(data):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "INVALID_ADMISSION", "Duplicate JSON field")
            value[key] = item
        return value
    try:
        return json.loads(data, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, LifecycleError):
            raise
        raise LifecycleError("INVALID_ADMISSION", "Invalid finite JSON input") from exc


def write_absent(path, value):
    """Private immutable publication; any uncertain failure propagates."""
    path = _absolute(path)
    parent = _directory_fd(path.parent)
    data = (canonical(value) + "\n").encode()
    try:
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)
    return hashlib.sha256(data).hexdigest()


def _identifier(value, pattern=_ID):
    require(type(value) is str and bool(pattern.fullmatch(value)), "INVALID_IDENTIFIER", "Invalid opaque identifier")
    return value


def implementation_sources():
    root = Path(__file__).resolve().parent.parent
    names = ("betelgeuze_product/prepared_lifecycle.py",
             "betelgeuze_product/prepared_lifecycle_owner.py",
             "betelgeuze_product/prepared_lifecycle_worker.py",
             "api/runner_process.py", "api/linux_runner_supervisor.py",
             "api/validated_runner_runtime_qualification.py")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def runtime_identity():
    distributions = {}
    for name in ("betelgeuze-md-product", "torch", "numpy"):
        try:
            distributions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            distributions[name] = None
    return {"python_version": platform.python_version(), "python_implementation": platform.python_implementation(),
            "python_executable_sha256": hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
            "distribution_versions": distributions}


def admission_document(input_root, admission_id, *, tenant_id="local"):
    try:
        return _admission_document(input_root, admission_id, tenant_id=tenant_id)
    except FileNotFoundError as exc:
        raise LifecycleError("NOT_FOUND_OR_FORBIDDEN", "Admission was not found", 404) from exc
    except LifecycleError:
        raise
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise LifecycleError("INVALID_ADMISSION", "Registered admission is invalid") from exc


def _admission_document(input_root, admission_id, *, tenant_id="local"):
    _identifier(admission_id)
    bundle = private_root(Path(input_root) / admission_id)
    manifest = json_bytes(regular_bytes(bundle / "admission.json", input_root))
    require(isinstance(manifest, dict) and manifest.get("schema_version") == ADMISSION_SCHEMA,
            "INVALID_ADMISSION", "Registered admission manifest required")
    require(manifest.get("tenant_id") == tenant_id, "NOT_FOUND_OR_FORBIDDEN", "Admission was not found", 404)
    raw = regular_bytes(bundle / "protocol.json", input_root)
    require(hashlib.sha256(raw).hexdigest() == manifest.get("protocol_sha256"),
            "SOURCE_OR_MODEL_MISMATCH", "Registered protocol bytes changed", 409)
    protocol = json_bytes(raw)
    require(isinstance(protocol, dict) and protocol.get("schema_version") == "prepared_fourier_development_protocol/1.0.0",
            "INVALID_ADMISSION", "Only the bounded prepared Fourier protocol is supported")
    require(protocol.get("evidence_kind") in ("synthetic_control", "prepared_real_development")
            and manifest.get("evidence_kind") == protocol["evidence_kind"],
            "INVALID_ADMISSION", "Explicit matching research evidence kind required")
    sources = {str(bundle / "protocol.json"): hashlib.sha256(raw).hexdigest()}
    for name in REFS:
        ref = protocol.get(name)
        require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}
                and isinstance(ref["sha256"], str) and _SHA.fullmatch(ref["sha256"]),
                "INVALID_ADMISSION", "Exact prepared input bindings required")
        data = regular_bytes(Path(ref["path"]), bundle)
        require(hashlib.sha256(data).hexdigest() == ref["sha256"],
                "SOURCE_OR_MODEL_MISMATCH", "Registered input bytes changed", 409)
        sources[ref["path"]] = ref["sha256"]
        if name == "source_evidence":
            evidence = json_bytes(data)
            for original in evidence.get("source_files", []):
                original_data = regular_bytes(Path(original["path"]), bundle)
                require(hashlib.sha256(original_data).hexdigest() == original["sha256"],
                        "SOURCE_OR_MODEL_MISMATCH", "Registered source evidence changed", 409)
                sources[original["path"]] = original["sha256"]
    try:
        config = protocol["solver"]["minimization"]
        iterations, backtracks = config["max_iterations"], config["max_backtracks"]
    except (KeyError, TypeError) as exc:
        raise LifecycleError("INVALID_ADMISSION", "Explicit solver bounds required") from exc
    require(type(iterations) is int and 1 <= iterations <= 4 and type(backtracks) is int
            and 0 <= backtracks <= 3, "INVALID_ADMISSION", "Bounded original solver limits required")
    pause = manifest.get("initial_pause_after_accepted_iterations")
    require(pause is None or type(pause) is int and 0 < pause < iterations,
            "INVALID_ADMISSION", "Initial pause must precede the original solver ceiling")
    sources[str(bundle / "admission.json")] = hashlib.sha256(regular_bytes(bundle / "admission.json", input_root)).hexdigest()
    return {"admission_id": admission_id, "manifest": manifest, "protocol": protocol,
            "protocol_path": str(bundle / "protocol.json"), "sources": sources,
            "model_id": "prepared_fourier_development/1.0.0", "lifecycle_sources": implementation_sources(), "runtime_identity": runtime_identity(), "iterations": iterations,
            "backtracks": backtracks, "initial_pause": pause,
            "force_call_ceiling": 1 + (1 + iterations * (backtracks + 1)) + (1 if pause is not None else 0)}


def register_admission(input_root, admission_id, protocol_path, *, initial_pause_after_accepted_iterations=None, tenant_id="local"):
    """Trusted local preparation helper; never exposed as a public submission."""
    input_root = private_root(input_root)
    _identifier(admission_id)
    bundle = private_root(input_root / admission_id)
    require(Path(protocol_path) == bundle / "protocol.json", "INVALID_ADMISSION", "Protocol must already belong to its private bundle")
    raw = regular_bytes(protocol_path, bundle)
    protocol = json_bytes(raw)
    _identifier(tenant_id, _TENANT)
    manifest = {"schema_version": ADMISSION_SCHEMA, "tenant_id": tenant_id, "protocol_sha256": hashlib.sha256(raw).hexdigest(),
                "evidence_kind": protocol.get("evidence_kind"),
                "initial_pause_after_accepted_iterations": initial_pause_after_accepted_iterations,
                "research_only": True, "qualified": False}
    write_absent(bundle / "admission.json", manifest)
    return admission_document(input_root, admission_id, tenant_id=tenant_id)


class PreparedLifecycle:
    def __init__(self, state_root, admitted_input_root, *, tenant_id="local"):
        self.root = private_root(state_root, create=True)
        self.input_root = private_root(admitted_input_root)
        self.tenant_id = _identifier(tenant_id, _TENANT)
        self.database = self.root / "prepared-jobs.sqlite3"
        for name in ("jobs",):
            path = self.root / name
            private_root(path, create=True)
        if self.database.exists():
            info = self.database.lstat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid(),
                    "INVALID_CONFIGURATION", "Private regular registry required", 503)
        with self._initialization_lock(), self._connect(initialize=True) as connection:
            connection.executescript("""
            CREATE TABLE IF NOT EXISTS prepared_jobs (
              execution_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, idem TEXT NOT NULL,
              request_hash TEXT NOT NULL, admission_json TEXT NOT NULL, policy_json TEXT NOT NULL,
              status TEXT NOT NULL, numerical_state TEXT NOT NULL, cancel_state TEXT NOT NULL,
              generation INTEGER NOT NULL DEFAULT 0, owner_token TEXT NOT NULL DEFAULT '',
              owner_pid INTEGER, owner_start TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0,
              invocation_count INTEGER NOT NULL DEFAULT 0, wall_spent REAL NOT NULL DEFAULT 0,
              cpu_spent REAL NOT NULL DEFAULT 0, known_force INTEGER NOT NULL DEFAULT 0,
              force_known INTEGER NOT NULL DEFAULT 1, force_reserved INTEGER NOT NULL DEFAULT 0,
              error_json TEXT, created REAL NOT NULL, updated REAL NOT NULL,
              UNIQUE(tenant,idem));
            CREATE TABLE IF NOT EXISTS prepared_invocations (
              execution_id TEXT NOT NULL, generation INTEGER NOT NULL, token TEXT NOT NULL,
              resume INTEGER NOT NULL, status TEXT NOT NULL, reserved_force INTEGER NOT NULL,
              reserved_wall REAL NOT NULL, reserved_cpu REAL NOT NULL, receipt_json TEXT,
              PRIMARY KEY(execution_id,generation));
            CREATE TABLE IF NOT EXISTS prepared_events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT, execution_id TEXT NOT NULL,
              kind TEXT NOT NULL, document_json TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS prepared_artifacts (
              artifact_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL, relative_path TEXT NOT NULL,
              role TEXT NOT NULL, schema_name TEXT, checksum TEXT NOT NULL, bytes INTEGER NOT NULL);
            """)
        os.chmod(self.database, 0o600)
        parent = _directory_fd(self.root)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)

    @contextmanager
    def _initialization_lock(self):
        parent = _directory_fd(self.root)
        try:
            fd = os.open("registry-initialization.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                         0o600, dir_fd=parent)
        finally:
            os.close(parent)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
                    and not info.st_mode & 0o077, "INVALID_CONFIGURATION", "Private registry lock required", 503)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def _connect(self, *, initialize=False):
        connection = sqlite3.connect(self.database, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        if initialize:
            connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _row(self, connection, execution_id):
        _identifier(execution_id, _HEX32)
        row = connection.execute("SELECT * FROM prepared_jobs WHERE execution_id=? AND tenant=?",
                                 (execution_id, self.tenant_id)).fetchone()
        require(row is not None, "NOT_FOUND_OR_FORBIDDEN", "Execution was not found", 404)
        return dict(row)

    def _event(self, connection, execution_id, kind, document):
        connection.execute("INSERT INTO prepared_events(execution_id,kind,document_json,created) VALUES(?,?,?,?)",
                           (execution_id, kind, canonical(document), time.time()))

    def _snapshot(self, row):
        policy = json.loads(row["policy_json"])
        inflight = row["status"] in ("running", "cancel_requested")
        return {"schema_version": SCHEMA, "execution_id": row["execution_id"], "status": row["status"],
                "numerical_state": "running_unresolved" if inflight else row["numerical_state"],
                "last_verified_numerical_state": row["numerical_state"], "cancel_state": row["cancel_state"],
                "research_only": True, "qualified": False, "model_id": "prepared_fourier_development/1.0.0",
                "implementation_sources": json.loads(row["admission_json"])["lifecycle_sources"],
                "runtime_identity": json.loads(row["admission_json"])["runtime_identity"],
                "units": {"coordinates": "angstrom", "energy": "kcal/mol", "raw_force": "kcal/mol/angstrom"},
                "budget": {"limits": policy, "wall_seconds_spent": row["wall_spent"],
                           "cpu_seconds_charged": row["cpu_spent"], "known_force_calls": row["known_force"],
                           "total_force_calls": row["known_force"] if row["force_known"] and not inflight else None,
                           "total_work_known": bool(row["force_known"]) and not inflight,
                           "force_calls_reserved": row["force_reserved"],
                           "numerical_invocations": row["invocation_count"],
                           "scope": "cumulative active wall/CPU and output; virtual address-space cap is not RSS/RAM"},
                "error": json.loads(row["error_json"]) if row["error_json"] else None,
                "artifacts": self.artifacts(row["execution_id"])["artifacts"]}

    def submit(self, admission_id, idempotency_key, budget_policy="local_cpu_research_v1"):
        _identifier(idempotency_key, _KEY)
        require(budget_policy == "local_cpu_research_v1", "INVALID_BUDGET_POLICY", "Unknown bounded budget policy")
        admission = admission_document(self.input_root, admission_id, tenant_id=self.tenant_id)
        policy = {**POLICY, "force_call_ceiling": admission["force_call_ceiling"],
                  "policy_id": budget_policy, "RAM_limit_claimed": False,
                  "output_scope": "publication byte guard plus sampled tree; sampled overshoot possible"}
        request_hash = digest({"admission": admission, "budget": policy, "tenant": self.tenant_id})
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM prepared_jobs WHERE tenant=? AND idem=?",
                                     (self.tenant_id, idempotency_key)).fetchone()
            if row:
                require(row["request_hash"] == request_hash, "IDEMPOTENCY_CONFLICT",
                        "Idempotency key is bound to a different request", 409)
                execution_id = row["execution_id"]
            else:
                available = sorted(os.sched_getaffinity(0))
                require(bool(available), "INVALID_CONFIGURATION", "No admitted CPU is available", 503)
                policy["cpu_affinity"] = [available[0]]
                execution_id, now = uuid.uuid4().hex, time.time()
                connection.execute("""INSERT INTO prepared_jobs(execution_id,tenant,idem,request_hash,
                    admission_json,policy_json,status,numerical_state,cancel_state,created,updated)
                    VALUES(?,?,?,?,?,?,'queued','not_started','none',?,?)""",
                    (execution_id, self.tenant_id, idempotency_key, request_hash, canonical(admission), canonical(policy), now, now))
                self._event(connection, execution_id, "submitted", {"request_sha256": request_hash})
        return self.status(execution_id)

    def status(self, execution_id):
        with self._connect() as connection:
            row = self._row(connection, execution_id)
        return self._snapshot(row)

    def cancel(self, execution_id, reason=""):
        require(type(reason) is str and len(reason) <= 512 and all(ord(c) >= 32 for c in reason),
                "INVALID_CANCEL_REASON", "A bounded cancellation reason is required")
        with self._transaction() as connection:
            row = self._row(connection, execution_id)
            if row["status"] in ("queued", "resume_queued", "paused", "unqualified"):
                connection.execute("UPDATE prepared_jobs SET status='cancelled',cancel_state='confirmed_no_active_process',cancel_requested=1,updated=? WHERE execution_id=?", (time.time(), execution_id))
                self._event(connection, execution_id, "cancelled_without_active_process", {"reason": reason})
            elif row["status"] == "running":
                connection.execute("UPDATE prepared_jobs SET status='cancel_requested',cancel_state='requested',cancel_requested=1,updated=? WHERE execution_id=?", (time.time(), execution_id))
                self._event(connection, execution_id, "cancel_requested", {"reason": reason})
        return self.status(execution_id)

    def resume(self, execution_id):
        with self._transaction() as connection:
            row = self._row(connection, execution_id)
            if row["status"] == "complete":
                return self._snapshot(row)
            known_pause = row["status"] == "paused" or (row["status"] == "cancelled"
                and row["cancel_state"] in ("confirmed_process_terminal", "confirmed_no_active_process"))
            require(known_pause and row["numerical_state"] == "paused" and row["force_known"],
                    "RESUME_NOT_ADMITTED", "Only a verified known paused execution may resume", 409)
            policy = json.loads(row["policy_json"])
            require(row["invocation_count"] < policy["max_numerical_invocations"]
                    and row["wall_spent"] < policy["wall_seconds"] and row["cpu_spent"] < policy["cpu_seconds"]
                    and row["known_force"] < policy["force_call_ceiling"],
                    "BUDGET_EXHAUSTED", "Cumulative execution budget is exhausted", 409)
            current = admission_document(self.input_root, json.loads(row["admission_json"])["admission_id"], tenant_id=self.tenant_id)
            require(current == json.loads(row["admission_json"]), "SOURCE_OR_MODEL_MISMATCH", "Registered inputs changed", 409)
            connection.execute("UPDATE prepared_jobs SET status='resume_queued',cancel_state='none',cancel_requested=0,updated=? WHERE execution_id=?", (time.time(), execution_id))
            self._event(connection, execution_id, "resume_queued", {"previous_generation": row["generation"]})
        return self.status(execution_id)

    def artifacts(self, execution_id):
        with self._connect() as connection:
            self._row(connection, execution_id)
            rows = connection.execute("SELECT * FROM prepared_artifacts WHERE execution_id=? ORDER BY artifact_id", (execution_id,)).fetchall()
        return {"execution_id": execution_id, "artifacts": [self._artifact_metadata(dict(row)) for row in rows],
                "research_only": True, "qualified": False}

    @staticmethod
    def _artifact_metadata(row):
        return {"artifact_id": row["artifact_id"], "role": row["role"], "schema": row["schema_name"],
                "sha256": row["checksum"], "bytes": row["bytes"], "media_type": "application/json"}

    def artifact(self, execution_id, artifact_id):
        _identifier(artifact_id, _HEX32)
        with self._connect() as connection:
            self._row(connection, execution_id)
            row = connection.execute("SELECT * FROM prepared_artifacts WHERE execution_id=? AND artifact_id=?", (execution_id, artifact_id)).fetchone()
        require(row is not None, "NOT_FOUND_OR_FORBIDDEN", "Artifact was not found", 404)
        row = dict(row)
        path = self.root / "jobs" / execution_id / row["relative_path"]
        data = regular_bytes(path, self.root / "jobs" / execution_id, maximum=POLICY["output_bytes"])
        require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["checksum"],
                "ARTIFACT_PUBLICATION_UNKNOWN", "Artifact bytes do not match their manifest", 409)
        return path, self._artifact_metadata(row)

    def _claim(self, execution_id=None):
        with self._transaction() as connection:
            if execution_id is None:
                found = connection.execute("SELECT execution_id FROM prepared_jobs WHERE tenant=? AND status IN ('queued','resume_queued') ORDER BY created,execution_id LIMIT 1", (self.tenant_id,)).fetchone()
                if found is None:
                    return None
                execution_id = found["execution_id"]
            row = self._row(connection, execution_id)
            require(row["status"] in ("queued", "resume_queued"), "BUSY", "Execution is not queued for a new owner", 409)
            admission, policy = json.loads(row["admission_json"]), json.loads(row["policy_json"])
            require(admission_document(self.input_root, admission["admission_id"], tenant_id=self.tenant_id) == admission,
                    "SOURCE_OR_MODEL_MISMATCH", "Registered input bytes changed", 409)
            resume = row["status"] == "resume_queued"
            reserve_force = policy["force_call_ceiling"] - row["known_force"]
            require(reserve_force > 0 and row["wall_spent"] < policy["wall_seconds"]
                    and row["cpu_spent"] < policy["cpu_seconds"]
                    and row["invocation_count"] < policy["max_numerical_invocations"],
                    "BUDGET_EXHAUSTED", "Cumulative execution budget is exhausted", 409)
            generation, token = row["generation"] + 1, secrets.token_hex(32)
            wall, cpu = policy["wall_seconds"] - row["wall_spent"], policy["cpu_seconds"] - row["cpu_spent"]
            connection.execute("UPDATE prepared_jobs SET status='running',generation=?,owner_token=?,owner_pid=?,owner_start=?,force_reserved=?,updated=? WHERE execution_id=?", (generation, token, os.getpid(), process_identity(os.getpid()), reserve_force, time.time(), execution_id))
            connection.execute("INSERT INTO prepared_invocations VALUES(?,?,?,?,?,?,?,?,NULL)",
                (execution_id, generation, token, int(resume), "reserved", reserve_force, wall, cpu))
            self._event(connection, execution_id, "invocation_reserved", {"generation": generation, "force_calls_upper_bound": reserve_force})
            row.update(generation=generation, owner_token=token, resume=resume, reserved_wall=wall,
                       reserved_cpu=cpu, force_reserved=reserve_force)
            return row

    def _finish(self, claim, *, status, numerical_state, error=None, receipt=None,
                known_force=None, force_known=True, wall=0., cpu=0., spawned=False, artifacts=()):
        require(type(force_known) is bool and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in (wall, cpu)),
                "INVALID_OWNER_RECEIPT", "Invalid measured owner receipt", 500)
        with self._transaction() as connection:
            row = self._row(connection, claim["execution_id"])
            require(row["owner_token"] == claim["owner_token"] and row["generation"] == claim["generation"]
                    and row["status"] in ("running", "cancel_requested"),
                    "OWNER_FENCE_LOST", "Owner no longer has publication authority", 409)
            policy = json.loads(row["policy_json"])
            if known_force is None:
                known_force = row["known_force"]
            require(type(known_force) is int and known_force >= row["known_force"]
                    and known_force <= policy["force_call_ceiling"], "INVALID_OWNER_RECEIPT", "Force census violates the frozen budget", 500)
            cancel_state = ("confirmed_process_terminal" if status == "cancelled" else
                            "completion_won_race" if row["cancel_requested"] and status == "complete" else row["cancel_state"])
            connection.execute("""UPDATE prepared_jobs SET status=?,numerical_state=?,cancel_state=?,owner_token='',owner_pid=NULL,owner_start=NULL,
                invocation_count=invocation_count+?,wall_spent=wall_spent+?,cpu_spent=cpu_spent+?,known_force=?,force_known=?,force_reserved=?,error_json=?,updated=?
                WHERE execution_id=?""", (status, numerical_state, cancel_state, int(spawned), wall, cpu, known_force, int(force_known),
                  0 if force_known else row["force_reserved"], canonical(error) if error else None, time.time(), row["execution_id"]))
            connection.execute("UPDATE prepared_invocations SET status=?,receipt_json=? WHERE execution_id=? AND generation=? AND token=?",
                (status, canonical(receipt or {}), row["execution_id"], row["generation"], claim["owner_token"]))
            for path, role in artifacts:
                self._add_artifact(connection, row["execution_id"], path, role)
            self._event(connection, row["execution_id"], "invocation_terminal", {"status": status, "numerical_state": numerical_state, "force_total_known": force_known})
        return self.status(claim["execution_id"])

    def _add_artifact(self, connection, execution_id, path, role):
        root = self.root / "jobs" / execution_id
        row = self._row(connection, execution_id)
        output_limit = json.loads(row["policy_json"])["output_bytes"]
        data = regular_bytes(path, root, maximum=output_limit)
        published = connection.execute("SELECT coalesce(sum(bytes),0) FROM prepared_artifacts WHERE execution_id=?",
                                       (execution_id,)).fetchone()[0]
        require(published + len(data) <= output_limit, "PUBLICATION_BUDGET_EXHAUSTED",
                "Cumulative immutable artifact publication budget is exhausted", 409)
        document = json_bytes(data)
        schema = document.get("schema_version", document.get("schema_id")) if isinstance(document, dict) else None
        connection.execute("INSERT INTO prepared_artifacts VALUES(?,?,?,?,?,?,?)", (uuid.uuid4().hex, execution_id,
            str(Path(path).relative_to(root)), role, schema, hashlib.sha256(data).hexdigest(), len(data)))


def process_identity(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def configured_service(*, tenant_id=None):
    prefix = "BETELGEUZE_PREPARED_LIFECYCLE_"
    require(os.environ.get(prefix + "ENABLED") == "1", "LIFECYCLE_DISABLED", "Prepared lifecycle is not enabled", 503)
    if tenant_id is None:
        tenant_id = os.environ.get(prefix + "TENANT_ID", "local")
    state, inputs = os.environ.get(prefix + "STATE_ROOT"), os.environ.get(prefix + "INPUT_ROOT")
    require(bool(state and inputs), "INVALID_CONFIGURATION", "Private local lifecycle storage is not configured", 503)
    try:
        return PreparedLifecycle(state, inputs, tenant_id=tenant_id)
    except OSError as exc:
        raise LifecycleError("INVALID_CONFIGURATION", "Private local lifecycle storage is unavailable", 503) from exc
