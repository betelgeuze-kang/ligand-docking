from __future__ import annotations

import ast
import base64
import fcntl
import hashlib
import json
import os
import subprocess
import sys

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2 import VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256
from betelgeuze_engine_v2 import runtime_snapshot_hardening as hardening


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def test_normal_library_import_does_not_replace_the_runner_boundary() -> None:
    assert VERIFIED_SOURCE_RUNTIME_HARDENING_SHA256 == ""


def test_sealed_source_snapshot_rejects_later_writes() -> None:
    if not hasattr(os, "memfd_create"):
        pytest.skip("memfd is unavailable")
    descriptor = hardening._sealed_snapshot_fd(b"verified-source")
    try:
        required = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        assert fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) == required
        with pytest.raises(OSError):
            os.write(descriptor, b"tamper")
    finally:
        os.close(descriptor)


def test_resource_audit_visitor_detects_live_source_reads_by_function() -> None:
    tree = compile(
        "def safe():\n    return 1\n\n"
        "def live():\n    return open(__file__, 'rb').read()\n",
        "<audit-source>",
        "exec",
        ast.PyCF_ONLY_AST,
    )
    visitor = hardening._ResourceVisitor()
    visitor.visit(tree)
    assert visitor.findings == {"live"}


def _module_row(path: str, payload: bytes) -> dict[str, object]:
    return {
        "path": path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size": len(payload),
        "payload_base64": base64.b64encode(payload).decode("ascii"),
    }


def test_fresh_isolated_child_reinstalls_only_the_sealed_snapshot() -> None:
    if not hasattr(os, "memfd_create"):
        pytest.skip("memfd is unavailable")

    audit_sha256 = "a" * 64
    root_source = (
        "import sys\n"
        f"setattr(sys, {hardening.VERIFIED_SOURCE_RESOURCE_AUDIT_ATTRIBUTE!r}, "
        f"{audit_sha256!r})\n"
    ).encode("utf-8")
    physics_source = b""
    runner_source = b'''
class _Row:
    def __init__(self, ordinal):
        self.ordinal = ordinal
        self.case_id = f"case-{ordinal}"
    def to_dict(self):
        return {"ordinal": self.ordinal, "case_id": self.case_id}

def _run_case_matrix_in_process():
    return (_Row(1), _Row(2))
'''
    source_payloads = {
        "betelgeuze_engine_v2/__init__.py": root_source,
        "betelgeuze_engine_v2/physics/__init__.py": physics_source,
        (
            "betelgeuze_engine_v2/physics/"
            "reference_minimization_validation_runner.py"
        ): runner_source,
    }
    manifest_rows = [
        {
            "path": path,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size": len(payload),
        }
        for path, payload in sorted(source_payloads.items())
    ]
    source_manifest = {
        "schema_id": (
            "betelgeuze.engine_v2_reference_minimization_validation_execution_sources/"
            "2.0.0"
        ),
        "source_count": len(manifest_rows),
        "total_source_bytes": sum(row["size"] for row in manifest_rows),
        "sources": manifest_rows,
    }
    manifest_sha256 = _sha256(source_manifest)
    finder_identity_sha256 = _sha256(
        {
            "schema_id": (
                "betelgeuze.engine_v2_reference_minimization_validation_source_finder/"
                "1.0.0"
            ),
            "source_manifest_sha256": manifest_sha256,
            "module_count": len(manifest_rows),
        }
    )

    project_root = os.path.realpath(os.getcwd())
    site_packages = os.path.realpath(
        os.path.dirname(os.path.dirname(torch.__file__))
    )
    standard_library_roots: list[str] = []
    for raw_path in sys.path:
        if not raw_path or not os.path.isdir(raw_path):
            continue
        resolved = os.path.realpath(raw_path)
        if resolved == project_root or resolved.startswith(project_root + os.sep):
            continue
        if "site-packages" in resolved or "dist-packages" in resolved:
            continue
        if resolved not in standard_library_roots:
            standard_library_roots.append(resolved)
    assert standard_library_roots
    assert any(path.endswith("lib-dynload") for path in standard_library_roots)
    frozen_path = list(
        dict.fromkeys([*standard_library_roots, site_packages])
    )
    projection: dict[str, object] = {
        "schema_id": hardening.VERIFIED_SOURCE_CHILD_SNAPSHOT_SCHEMA_ID,
        "source_manifest_sha256": manifest_sha256,
        "finder_identity_sha256": finder_identity_sha256,
        "resource_audit_sha256": audit_sha256,
        "repository_root": "/nonexistent/verified-source-repository",
        "bootstrap_path": "/nonexistent/verified-source-bootstrap.py",
        "dependency_roots": [site_packages],
        "frozen_sys_path": frozen_path,
        "application_seed": 17,
        "sources": [
            _module_row(path, payload)
            for path, payload in sorted(source_payloads.items())
        ],
    }
    projection["snapshot_sha256"] = _sha256(projection)
    raw = _canonical(projection)
    snapshot_fd = hardening._sealed_snapshot_fd(raw)
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC)
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
                hardening._CHILD_BOOTSTRAP,
                str(snapshot_fd),
                str(write_fd),
                str(projection["snapshot_sha256"]),
            ],
            env={
                "BETELGEUZE_REFERENCE_MINIMIZATION_VALIDATION_SEED": "17",
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
            },
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            pass_fds=(snapshot_fd, write_fd),
            close_fds=True,
        )
        os.close(write_fd)
        write_fd = -1
        os.close(snapshot_fd)
        snapshot_fd = -1
        chunks: list[bytes] = []
        while True:
            chunk = os.read(read_fd, 65_536)
            if not chunk:
                break
            chunks.append(chunk)
        stderr = process.communicate(timeout=60)[1]
        assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
        envelope = json.loads(b"".join(chunks).decode("ascii"))
        assert envelope["schema_id"] == hardening.VERIFIED_SOURCE_CHILD_RESULT_SCHEMA_ID
        assert envelope["source_manifest_sha256"] == manifest_sha256
        assert envelope["finder_identity_sha256"] == finder_identity_sha256
        assert envelope["resource_audit_sha256"] == audit_sha256
        assert envelope["case_results"] == [
            {"case_id": "case-1", "ordinal": 1},
            {"case_id": "case-2", "ordinal": 2},
        ]
    finally:
        if snapshot_fd >= 0:
            os.close(snapshot_fd)
        if write_fd >= 0:
            os.close(write_fd)
        os.close(read_fd)
