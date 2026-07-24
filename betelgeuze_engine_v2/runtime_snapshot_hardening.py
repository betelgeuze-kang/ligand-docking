"""Runtime hardening for verified Engine v2 source snapshots.

The stdlib bootstrap in ``reference_minimization_validation_bootstrap`` creates
an immutable in-memory source view for the parent interpreter. This module
closes the remaining child-process and live-source gaps without changing the
scientific claim boundary:

* every supervised worker starts a fresh isolated interpreter;
* the complete verified source snapshot is transferred through a sealed memfd;
* the child reconstructs and re-verifies the finder before importing Engine v2;
* source identity and import audits read the verified bytes, never ``__file__``;
* critical runtime modules are audited for unauthorised package-resource reads.

No production, scientific, benchmark, product, customer, or claim promotion is
performed here.
"""

from __future__ import annotations

import ast
import base64
import fcntl
import hashlib
import json
import os
import select
import subprocess
import sys
import time
from typing import Any, Mapping


VERIFIED_SOURCE_CHILD_SNAPSHOT_SCHEMA_ID = (
    "betelgeuze.engine_v2_verified_source_child_snapshot/1.0.0"
)
VERIFIED_SOURCE_CHILD_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_verified_source_child_result/1.0.0"
)
VERIFIED_SOURCE_RESOURCE_AUDIT_SCHEMA_ID = (
    "betelgeuze.engine_v2_verified_source_resource_audit/1.0.0"
)
VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE = (
    "_betelgeuze_reference_minimization_validation_resource_audit_sha256"
)
VERIFIED_SOURCE_CHILD_MAX_SNAPSHOT_BYTES = 96 * 1_048_576
VERIFIED_SOURCE_CHILD_MAX_RESULT_BYTES = 8 * 1_048_576

_CRITICAL_RESOURCE_AUDIT_ALLOWLIST = {
    "betelgeuze_engine_v2/physics/reference_minimization_validation_materializer.py": {
        "cpu_minimization_validation_materializer_source_sha256",
    },
    "betelgeuze_engine_v2/physics/reference_minimization_validation_artifact_binding.py": {
        "_source_path",
        "independent_minimization_oracle_source_sha256",
        "independent_analytic_oracle_source_sha256",
        "_minimization_oracle_import_audit",
    },
    "betelgeuze_engine_v2/physics/reference_minimization_validation_runner.py": {
        "reference_minimization_validation_checked_out_code_commit_sha",
        "_require_clean_checked_out_code_commit",
    },
    "betelgeuze_engine_v2/physics/reference_minimization_independent_oracle.py": set(),
    "betelgeuze_engine_v2/physics/reference_validation_oracle.py": set(),
}

_CHILD_BOOTSTRAP = r'''
from __future__ import annotations
import base64
import fcntl
import hashlib
import importlib.abc
import importlib.machinery
import json
import os
import sys
import types

MAX_SNAPSHOT = 96 * 1048576
MAX_RESULT = 8 * 1048576
SOURCE_SCHEMA = "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/2.0.0"
CHILD_SCHEMA = "betelgeuze.engine_v2_verified_source_child_snapshot/1.0.0"
RESULT_SCHEMA = "betelgeuze.engine_v2_verified_source_child_result/1.0.0"
FINDER_ATTR = "_betelgeuze_reference_minimization_validation_source_finder"
MANIFEST_ATTR = "_betelgeuze_reference_minimization_validation_source_manifest_sha256"
STATE_ATTR = "_betelgeuze_reference_minimization_validation_bootstrap_state"
AUDIT_ATTR = "_betelgeuze_reference_minimization_validation_resource_audit_sha256"


def canonical(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read_bounded(fd, maximum):
    chunks = []
    total = 0
    while True:
        chunk = os.read(fd, min(1048576, maximum + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > maximum:
            raise RuntimeError("verified source child payload exceeded its bound")
    return b"".join(chunks)


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeError("verified source child payload has duplicate keys")
        result[key] = value
    return result


class Loader(importlib.abc.Loader):
    def __init__(self, fullname, filename, payload, is_package):
        self.fullname = fullname
        self.filename = filename
        self.payload = payload
        self.package = is_package

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = self.filename
        module.__cached__ = None
        code = compile(self.payload, self.filename, "exec", dont_inherit=True, optimize=sys.flags.optimize)
        exec(code, module.__dict__)

    def get_filename(self, fullname):
        if fullname != self.fullname:
            raise ImportError("verified child loader name mismatch")
        return self.filename

    def get_source(self, fullname):
        if fullname != self.fullname:
            raise ImportError("verified child loader name mismatch")
        return self.payload.decode("utf-8")

    def is_package(self, fullname):
        if fullname != self.fullname:
            raise ImportError("verified child loader name mismatch")
        return self.package


class Finder(importlib.abc.MetaPathFinder):
    def __init__(self, document, sources):
        self.repository_root = document["repository_root"]
        self.source_manifest_sha256 = document["source_manifest_sha256"]
        self.finder_identity_sha256 = document["finder_identity_sha256"]
        self._sources = types.MappingProxyType(dict(sources))
        records = {}
        for relative_path, payload in sorted(sources.items()):
            parts = relative_path.split("/")
            package = parts[-1] == "__init__.py"
            module_parts = parts[:-1] if package else (*parts[:-1], parts[-1][:-3])
            fullname = ".".join(module_parts)
            filename = os.path.join(self.repository_root, *parts)
            if fullname in records:
                raise RuntimeError("verified child source module is duplicated")
            records[fullname] = (filename, payload, package)
        self._records = types.MappingProxyType(records)

    def source_bytes_for_relative_path(self, relative_path):
        try:
            return self._sources[relative_path]
        except KeyError as exc:
            raise RuntimeError("verified child source path is unavailable") from exc

    def find_spec(self, fullname, path=None, target=None):
        del path, target
        record = self._records.get(fullname)
        if record is None:
            if fullname == "betelgeuze_engine_v2" or fullname.startswith("betelgeuze_engine_v2."):
                raise ModuleNotFoundError(f"{fullname} is absent from the verified child snapshot")
            return None
        filename, payload, package = record
        loader = Loader(fullname, filename, payload, package)
        spec = importlib.machinery.ModuleSpec(fullname, loader, origin=filename, is_package=package)
        if package:
            spec.submodule_search_locations = [f"<verified-source:{self.source_manifest_sha256}>/{fullname.replace('.', '/')}"]
        return spec


def main():
    if len(sys.argv) != 4:
        raise RuntimeError("verified source child arguments are invalid")
    snapshot_fd = int(sys.argv[1])
    result_fd = int(sys.argv[2])
    expected_snapshot_sha256 = sys.argv[3]
    required_seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
    if fcntl.fcntl(snapshot_fd, fcntl.F_GET_SEALS) != required_seals:
        raise RuntimeError("verified source child snapshot is not sealed")
    os.lseek(snapshot_fd, 0, os.SEEK_SET)
    raw = read_bounded(snapshot_fd, MAX_SNAPSHOT)
    document = json.loads(raw.decode("ascii"), object_pairs_hook=reject_duplicates)
    if not isinstance(document, dict) or canonical(document) != raw:
        raise RuntimeError("verified source child snapshot is not canonical")
    projection = dict(document)
    observed_snapshot_sha256 = projection.pop("snapshot_sha256", None)
    if observed_snapshot_sha256 != expected_snapshot_sha256 or observed_snapshot_sha256 != digest(projection):
        raise RuntimeError("verified source child snapshot identity is invalid")
    if projection.get("schema_id") != CHILD_SCHEMA:
        raise RuntimeError("verified source child snapshot schema is invalid")
    source_rows = projection.get("sources")
    if not isinstance(source_rows, list) or not source_rows:
        raise RuntimeError("verified source child snapshot has no source rows")
    sources = {}
    manifest_rows = []
    total = 0
    for row in source_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "size", "payload_base64"}:
            raise RuntimeError("verified source child row fields are invalid")
        path = row["path"]
        if not isinstance(path, str) or not path.startswith("betelgeuze_engine_v2/") or not path.endswith(".py") or path in sources:
            raise RuntimeError("verified source child row path is invalid")
        payload = base64.b64decode(row["payload_base64"], validate=True)
        if len(payload) != row["size"] or hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise RuntimeError("verified source child row identity is invalid")
        sources[path] = payload
        total += len(payload)
        manifest_rows.append({"path": path, "sha256": row["sha256"], "size": row["size"]})
    if manifest_rows != sorted(manifest_rows, key=lambda row: row["path"]):
        raise RuntimeError("verified source child rows are not sorted")
    manifest = {
        "schema_id": SOURCE_SCHEMA,
        "source_count": len(manifest_rows),
        "total_source_bytes": total,
        "sources": manifest_rows,
    }
    if digest(manifest) != projection.get("source_manifest_sha256"):
        raise RuntimeError("verified source child source manifest is invalid")
    finder_identity = digest({
        "schema_id": "betelgeuze.engine_v2_reference_minimization_validation_source_finder/1.0.0",
        "source_manifest_sha256": projection["source_manifest_sha256"],
        "module_count": len(manifest_rows),
    })
    if finder_identity != projection.get("finder_identity_sha256"):
        raise RuntimeError("verified source child finder identity is invalid")
    frozen_sys_path = projection.get("frozen_sys_path")
    dependency_roots = projection.get("dependency_roots")
    if not isinstance(frozen_sys_path, list) or not frozen_sys_path or any(not isinstance(item, str) or not item for item in frozen_sys_path):
        raise RuntimeError("verified source child sys.path is invalid")
    if not isinstance(dependency_roots, list) or not dependency_roots or any(not isinstance(item, str) or not item for item in dependency_roots):
        raise RuntimeError("verified source child dependency roots are invalid")
    repository_root = projection.get("repository_root")
    bootstrap_path = projection.get("bootstrap_path")
    if not isinstance(repository_root, str) or not os.path.isabs(repository_root) or repository_root in frozen_sys_path:
        raise RuntimeError("verified source child repository root is invalid")
    if not isinstance(bootstrap_path, str) or not os.path.isabs(bootstrap_path):
        raise RuntimeError("verified source child bootstrap path is invalid")
    if any(name == "betelgeuze_engine_v2" or name.startswith("betelgeuze_engine_v2.") for name in sys.modules):
        raise RuntimeError("Engine v2 was imported before child source verification")
    finder = Finder(projection, sources)
    sys.path[:] = list(frozen_sys_path)
    sys.meta_path.insert(0, finder)
    setattr(sys, FINDER_ATTR, finder)
    setattr(sys, MANIFEST_ATTR, projection["source_manifest_sha256"])
    setattr(sys, STATE_ATTR, (
        bootstrap_path,
        repository_root,
        tuple(dependency_roots),
        tuple(frozen_sys_path),
        projection["source_manifest_sha256"],
        projection["finder_identity_sha256"],
    ))
    import betelgeuze_engine_v2.physics.reference_minimization_validation_runner as runner
    import torch
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        if torch.get_num_interop_threads() != 1:
            raise
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(int(projection["application_seed"]))
    if getattr(sys, AUDIT_ATTR, None) != projection.get("resource_audit_sha256"):
        raise RuntimeError("verified source child resource audit is cross-wired")
    rows = runner._run_case_matrix_in_process()
    envelope = {
        "schema_id": RESULT_SCHEMA,
        "source_manifest_sha256": projection["source_manifest_sha256"],
        "finder_identity_sha256": projection["finder_identity_sha256"],
        "resource_audit_sha256": projection["resource_audit_sha256"],
        "case_results": [row.to_dict() for row in rows],
    }
    payload = canonical(envelope)
    if len(payload) > MAX_RESULT:
        raise RuntimeError("verified source child result exceeds its bound")
    view = memoryview(payload)
    while view:
        written = os.write(result_fd, view)
        if written <= 0:
            raise RuntimeError("verified source child result write made no progress")
        view = view[written:]


try:
    main()
except BaseException:
    raise SystemExit(97)
'''


class VerifiedSourceRuntimeHardeningError(RuntimeError):
    """The verified-source runtime hardening contract failed closed."""


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source runtime payload is not canonical JSON"
        ) from exc


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _finder() -> object | None:
    from betelgeuze_engine_v2.physics import reference_minimization_validation_bootstrap as bootstrap

    finder = getattr(
        sys, bootstrap.REFERENCE_MINIMIZATION_VALIDATION_SOURCE_FINDER_ATTRIBUTE, None
    )
    if finder is None:
        return None
    if finder not in sys.meta_path or not hasattr(
        finder, "source_bytes_for_relative_path"
    ):
        raise VerifiedSourceRuntimeHardeningError(
            "verified source finder is malformed"
        )
    return finder


def _verified_source_bytes(relative_path: str) -> bytes:
    finder = _finder()
    if finder is None:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source bytes are unavailable outside the bootstrap boundary"
        )
    payload = finder.source_bytes_for_relative_path(relative_path)
    if not isinstance(payload, bytes):
        raise VerifiedSourceRuntimeHardeningError(
            "verified source finder returned non-bytes"
        )
    return payload


def _verified_source_sha256(relative_path: str) -> str:
    return hashlib.sha256(_verified_source_bytes(relative_path)).hexdigest()


def _current_function_name(stack: list[str]) -> str:
    return stack[-1] if stack else "<module>"


class _ResourceVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.findings: set[str] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "__file__":
            self.findings.add(_current_function_name(self.stack))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        function = node.func
        flagged = isinstance(function, ast.Name) and function.id == "open"
        if isinstance(function, ast.Attribute) and function.attr in {
            "read_bytes",
            "read_text",
            "get_data",
        }:
            flagged = True
        if flagged:
            self.findings.add(_current_function_name(self.stack))
        self.generic_visit(node)


def _resource_audit() -> str:
    finder = _finder()
    if finder is None:
        return ""
    rows: list[dict[str, object]] = []
    for relative_path, allowed in sorted(_CRITICAL_RESOURCE_AUDIT_ALLOWLIST.items()):
        source = _verified_source_bytes(relative_path)
        try:
            tree = ast.parse(source.decode("utf-8"), filename=relative_path)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise VerifiedSourceRuntimeHardeningError(
                "critical verified source is not valid UTF-8 Python"
            ) from exc
        visitor = _ResourceVisitor()
        visitor.visit(tree)
        unexpected = visitor.findings - allowed
        missing = allowed - visitor.findings
        if unexpected or missing:
            raise VerifiedSourceRuntimeHardeningError(
                "critical package resource audit drifted"
            )
        rows.append(
            {
                "path": relative_path,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "overridden_live_source_functions": sorted(visitor.findings),
                "unaudited_resource_reads": [],
            }
        )
    document = {
        "schema_id": VERIFIED_SOURCE_RESOURCE_AUDIT_SCHEMA_ID,
        "critical_module_count": len(rows),
        "package_resources_loaded_from_live_checkout": False,
        "rows": rows,
    }
    audit_sha256 = _sha256(document)
    setattr(sys, VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE, audit_sha256)
    return audit_sha256


def _repository_root() -> str:
    from betelgeuze_engine_v2.physics import reference_minimization_validation_bootstrap as bootstrap

    state = getattr(
        sys, bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, None
    )
    if not isinstance(state, tuple) or len(state) != 8:
        raise VerifiedSourceRuntimeHardeningError(
            "verified bootstrap state is unavailable"
        )
    root = state[2]
    if not isinstance(root, str) or not os.path.isabs(root):
        raise VerifiedSourceRuntimeHardeningError(
            "verified repository root is invalid"
        )
    return root


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def _checked_out_code_commit_sha() -> str:
    result = subprocess.run(
        [
            "/usr/bin/git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "rev-parse",
            "--verify",
            "HEAD",
        ],
        cwd=_repository_root(),
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    value = result.stdout.decode("ascii", errors="strict").strip()
    if result.returncode != 0 or len(value) != 40 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise VerifiedSourceRuntimeHardeningError(
            "checked-out code commit is unavailable"
        )
    return value


def _require_clean_checkout(expected_commit_sha: str) -> None:
    if _checked_out_code_commit_sha() != expected_commit_sha:
        raise VerifiedSourceRuntimeHardeningError(
            "checked-out code commit is cross-wired"
        )
    common = [
        "/usr/bin/git",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.hooksPath=/dev/null",
    ]
    status_result = subprocess.run(
        [*common, "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=_repository_root(),
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    replace_result = subprocess.run(
        [*common, "replace", "--list"],
        cwd=_repository_root(),
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=10,
        check=False,
    )
    if (
        status_result.returncode != 0
        or status_result.stdout
        or replace_result.returncode != 0
        or replace_result.stdout
    ):
        raise VerifiedSourceRuntimeHardeningError(
            "validation checkout is not clean"
        )


def _snapshot_document() -> dict[str, object]:
    from betelgeuze_engine_v2.physics import reference_minimization_validation_bootstrap as bootstrap

    finder = _finder()
    if finder is None:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source child snapshot requires the bootstrap finder"
        )
    sources = getattr(finder, "_sources", None)
    if not isinstance(sources, Mapping) or not sources:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source finder does not expose an immutable source map"
        )
    rows = []
    manifest_rows = []
    total = 0
    for relative_path, payload in sorted(sources.items()):
        if not isinstance(relative_path, str) or not isinstance(payload, bytes):
            raise VerifiedSourceRuntimeHardeningError(
                "verified source map contains an invalid row"
            )
        digest = hashlib.sha256(payload).hexdigest()
        rows.append(
            {
                "path": relative_path,
                "sha256": digest,
                "size": len(payload),
                "payload_base64": base64.b64encode(payload).decode("ascii"),
            }
        )
        manifest_rows.append(
            {"path": relative_path, "sha256": digest, "size": len(payload)}
        )
        total += len(payload)
    manifest = {
        "schema_id": bootstrap.REFERENCE_MINIMIZATION_VALIDATION_SOURCE_MANIFEST_SCHEMA_ID,
        "source_count": len(manifest_rows),
        "total_source_bytes": total,
        "sources": manifest_rows,
    }
    manifest_sha256 = _sha256(manifest)
    state = getattr(
        sys, bootstrap.REFERENCE_MINIMIZATION_VALIDATION_BOOTSTRAP_STATE_ATTRIBUTE, None
    )
    if (
        not isinstance(state, tuple)
        or len(state) != 8
        or state[6] != manifest_sha256
        or state[7] != getattr(finder, "finder_identity_sha256", None)
    ):
        raise VerifiedSourceRuntimeHardeningError(
            "verified source child snapshot is cross-wired"
        )
    seed_text = os.environ.get(
        "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED"
    )
    if not isinstance(seed_text, str) or not seed_text.isdigit():
        raise VerifiedSourceRuntimeHardeningError(
            "verified source child application seed is unavailable"
        )
    audit_sha256 = getattr(sys, VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE, None)
    if not isinstance(audit_sha256, str) or len(audit_sha256) != 64:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source resource audit is unavailable"
        )
    projection: dict[str, object] = {
        "schema_id": VERIFIED_SOURCE_CHILD_SNAPSHOT_SCHEMA_ID,
        "source_manifest_sha256": manifest_sha256,
        "finder_identity_sha256": state[7],
        "resource_audit_sha256": audit_sha256,
        "repository_root": state[2],
        "bootstrap_path": state[1],
        "dependency_roots": list(state[3]),
        "frozen_sys_path": list(state[4]),
        "application_seed": int(seed_text),
        "sources": rows,
    }
    projection["snapshot_sha256"] = _sha256(projection)
    return projection


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise VerifiedSourceRuntimeHardeningError(
                "verified source snapshot write made no progress"
            )
        remaining = remaining[written:]


def _sealed_snapshot_fd(payload: bytes) -> int:
    required_names = (
        "memfd_create",
        "MFD_CLOEXEC",
        "MFD_ALLOW_SEALING",
    )
    if any(not hasattr(os, name) for name in required_names):
        raise VerifiedSourceRuntimeHardeningError(
            "sealed verified source snapshots are unavailable"
        )
    required_fcnt = (
        "F_ADD_SEALS",
        "F_GET_SEALS",
        "F_SEAL_WRITE",
        "F_SEAL_GROW",
        "F_SEAL_SHRINK",
        "F_SEAL_SEAL",
    )
    if any(not hasattr(fcntl, name) for name in required_fcnt):
        raise VerifiedSourceRuntimeHardeningError(
            "verified source snapshot sealing is unavailable"
        )
    descriptor = os.memfd_create(
        "betelgeuze-engine-v2-source-snapshot",
        flags=os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING,
    )
    try:
        _write_all(descriptor, payload)
        seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
        if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) != seals:
            raise VerifiedSourceRuntimeHardeningError(
                "verified source snapshot seals were not applied"
            )
        os.lseek(descriptor, 0, os.SEEK_SET)
        result = descriptor
        descriptor = -1
        return result
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _child_environment() -> dict[str, str]:
    seed = os.environ.get("BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED")
    if seed is None:
        raise VerifiedSourceRuntimeHardeningError(
            "verified source child seed is unavailable"
        )
    return {
        "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED": seed,
        "CUDA_VISIBLE_DEVICES": "",
        "HIP_VISIBLE_DEVICES": "",
        "ROCR_VISIBLE_DEVICES": "",
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MKL_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": "/dev/null",
        "TZ": "UTC",
    }


def _run_supervised_case_matrix(*, deadline: float) -> tuple[object, ...]:
    from betelgeuze_engine_v2.physics import reference_minimization_validation_runner as runner

    remaining = deadline - time.monotonic()
    if remaining <= 0.0:
        return runner._failure_complete_matrix("runner_wall_time_exhausted")
    document = _snapshot_document()
    payload = _canonical_bytes(document)
    if len(payload) > VERIFIED_SOURCE_CHILD_MAX_SNAPSHOT_BYTES:
        return runner._failure_complete_matrix("runner_source_snapshot_too_large")
    snapshot_fd = _sealed_snapshot_fd(payload)
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-X",
                "pycache_prefix=/dev/null",
                "-c",
                _CHILD_BOOTSTRAP,
                str(snapshot_fd),
                str(write_fd),
                str(document["snapshot_sha256"]),
            ],
            env=_child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            pass_fds=(snapshot_fd, write_fd),
        )
        os.close(write_fd)
        write_fd = -1
        os.close(snapshot_fd)
        snapshot_fd = -1
        chunks: list[bytes] = []
        total = 0
        while True:
            now_remaining = deadline - time.monotonic()
            if now_remaining <= 0.0:
                process.kill()
                process.wait(timeout=5.0)
                return runner._failure_complete_matrix("runner_wall_time_exhausted")
            ready, _, _ = select.select([read_fd], [], [], min(now_remaining, 0.25))
            if ready:
                chunk = os.read(read_fd, 1_048_576)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > VERIFIED_SOURCE_CHILD_MAX_RESULT_BYTES:
                    process.kill()
                    process.wait(timeout=5.0)
                    return runner._failure_complete_matrix(
                        "runner_worker_output_invalid"
                    )
            elif process.poll() is not None:
                chunk = os.read(read_fd, 1_048_576)
                if chunk:
                    chunks.append(chunk)
                    total += len(chunk)
                    continue
                break
        return_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        raw = b"".join(chunks)
        if return_code != 0 or not raw:
            return runner._failure_complete_matrix("runner_worker_output_invalid")
        try:
            envelope = json.loads(raw.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return runner._failure_complete_matrix("runner_worker_output_invalid")
        if not isinstance(envelope, dict) or raw != _canonical_bytes(envelope):
            return runner._failure_complete_matrix("runner_worker_output_invalid")
        finder = _finder()
        expected_audit = getattr(sys, VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE, None)
        if (
            envelope.get("schema_id") != VERIFIED_SOURCE_CHILD_RESULT_SCHEMA_ID
            or envelope.get("source_manifest_sha256")
            != getattr(finder, "source_manifest_sha256", None)
            or envelope.get("finder_identity_sha256")
            != getattr(finder, "finder_identity_sha256", None)
            or envelope.get("resource_audit_sha256") != expected_audit
            or not isinstance(envelope.get("case_results"), list)
            or len(envelope["case_results"])
            != runner.REFERENCE_MINIMIZATION_VALIDATION_RUNNER_MAX_CASES
        ):
            return runner._failure_complete_matrix("runner_worker_output_crosswired")
        try:
            rows = tuple(
                runner._case_observation_from_payload(row)
                for row in envelope["case_results"]
            )
        except runner.ReferenceMinimizationValidationRunnerError:
            return runner._failure_complete_matrix("runner_worker_output_invalid")
        expected_ids = [
            row["case_id"]
            for row in runner.cpu_minimization_validation_protocol_document()[
                "case_manifest"
            ]["cases"]
        ]
        if [row.case_id for row in rows] != expected_ids:
            return runner._failure_complete_matrix("runner_worker_output_crosswired")
        return rows
    except (OSError, subprocess.SubprocessError, VerifiedSourceRuntimeHardeningError):
        return runner._failure_complete_matrix("runner_worker_output_invalid")
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)


def _install_source_identity_overrides() -> None:
    from betelgeuze_engine_v2 import physics
    from betelgeuze_engine_v2.physics import reference_minimization_validation_artifact_binding as binding
    from betelgeuze_engine_v2.physics import reference_minimization_validation_materializer as materializer
    from betelgeuze_engine_v2.physics import reference_minimization_validation_runner as runner

    original_materializer = materializer.cpu_minimization_validation_materializer_source_sha256
    original_minimization = binding.independent_minimization_oracle_source_sha256
    original_analytic = binding.independent_analytic_oracle_source_sha256
    original_audit = binding._minimization_oracle_import_audit

    def materializer_sha256() -> str:
        if _finder() is None:
            return original_materializer()
        return _verified_source_sha256(
            "betelgeuze_engine_v2/physics/reference_minimization_validation_materializer.py"
        )

    def minimization_sha256() -> str:
        if _finder() is None:
            return original_minimization()
        return _verified_source_sha256(
            "betelgeuze_engine_v2/physics/reference_minimization_independent_oracle.py"
        )

    def analytic_sha256() -> str:
        if _finder() is None:
            return original_analytic()
        return _verified_source_sha256(
            "betelgeuze_engine_v2/physics/reference_validation_oracle.py"
        )

    def oracle_import_audit() -> dict[str, Any]:
        if _finder() is None:
            return original_audit()
        relative_path = (
            "betelgeuze_engine_v2/physics/reference_minimization_independent_oracle.py"
        )
        source_bytes = _verified_source_bytes(relative_path)
        try:
            source = source_bytes.decode("utf-8")
            tree = ast.parse(source, filename=relative_path)
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise binding.ReferenceMinimizationValidationArtifactBindingError(
                "independent minimization oracle must be valid UTF-8 Python"
            ) from exc
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                prefix = "." * node.level
                imports.append(f"{prefix}{node.module or ''}")
        unexpected = sorted(
            set(imports) - binding._ALLOWED_MINIMIZATION_ORACLE_IMPORTS
        )
        forbidden = sorted(
            name
            for name in imports
            if any(
                name == prefix or name.startswith(f"{prefix}.")
                for prefix in binding._FORBIDDEN_IMPORT_PREFIXES
            )
        )
        dynamic_tokens = sorted(
            token
            for token in binding._FORBIDDEN_DYNAMIC_IMPORT_TOKENS
            if token in source
        )
        if unexpected or forbidden or dynamic_tokens:
            raise binding.ReferenceMinimizationValidationArtifactBindingError(
                "independent minimization oracle violates the frozen import boundary"
            )
        return {
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "imports": sorted(imports),
            "allowed_imports": sorted(binding._ALLOWED_MINIMIZATION_ORACLE_IMPORTS),
            "forbidden_import_prefixes": list(binding._FORBIDDEN_IMPORT_PREFIXES),
            "forbidden_dynamic_import_tokens": list(
                binding._FORBIDDEN_DYNAMIC_IMPORT_TOKENS
            ),
            "analytic_oracle_is_only_relative_dependency": True,
            "operational_evaluator_imported": False,
            "operational_minimizer_imported": False,
            "constraint_or_solvation_implementation_imported": False,
            "protocol_or_materializer_imported": False,
            "third_party_dependency_imported": False,
            "dynamic_import_tokens_present": False,
            "audit_passed": True,
        }

    materializer.cpu_minimization_validation_materializer_source_sha256 = (
        materializer_sha256
    )
    binding.cpu_minimization_validation_materializer_source_sha256 = (
        materializer_sha256
    )
    binding.independent_minimization_oracle_source_sha256 = minimization_sha256
    binding.independent_analytic_oracle_source_sha256 = analytic_sha256
    binding._minimization_oracle_import_audit = oracle_import_audit
    physics.cpu_minimization_validation_materializer_source_sha256 = (
        materializer_sha256
    )
    physics.independent_minimization_oracle_source_sha256 = minimization_sha256
    runner.reference_minimization_validation_checked_out_code_commit_sha = (
        _checked_out_code_commit_sha
    )
    runner._require_clean_checked_out_code_commit = _require_clean_checkout
    runner._run_supervised_case_matrix = _run_supervised_case_matrix


def install_verified_source_runtime_hardening() -> str:
    """Install idempotent verified-source runtime overrides."""

    marker = "_betelgeuze_verified_source_runtime_hardening_installed"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing
    _install_source_identity_overrides()
    audit_sha256 = _resource_audit()
    installed_sha256 = _sha256(
        {
            "schema_id": (
                "betelgeuze.engine_v2_verified_source_runtime_hardening/1.0.0"
            ),
            "resource_audit_sha256": audit_sha256,
            "fresh_child_reinstalls_verified_snapshot": True,
            "sealed_snapshot_transport": True,
            "live_source_identity_reads": False,
            "package_resource_audit_enforced": bool(audit_sha256),
            "scientifically_validated": False,
            "claim_safe": False,
        }
    )
    setattr(sys, marker, installed_sha256)
    return installed_sha256


__all__ = [
    "VERIFIED_SOURCE_CHILD_RESULT_SCHEMA_ID",
    "VERIFIED_SOURCE_CHILD_SNAPSHOT_SCHEMA_ID",
    "VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE",
    "VERIFIED_SOURCE_RESOURCE_AUDIT_SCHEMA_ID",
    "VerifiedSourceRuntimeHardeningError",
    "install_verified_source_runtime_hardening",
]
