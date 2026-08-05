"""Pure helper contracts for one-shot source and durable-state verification.

This module provides deterministic Git and owner-only receipt readers. It does
not mutate another module, replace policy constants, wrap callables at import
time, reserve a run, execute docking, or grant product/scientific authority.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_binding/2.0.0"
)
EXPECTED_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_policy/1.1.0"
)
EXPECTED_VERDICT_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_verdict/1.1.0"
)
EXPECTED_ONE_SHOT_POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
EXPECTED_PHASE25_POLICY_SHA256 = (
    "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
)
EXPECTED_ACTIVATION_POLICY_SHA256 = (
    "988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c"
)
EXPECTED_NO_GO_CRITERIA = (
    "required_invariant_failed",
    "all_primary_go_criteria_failed",
    "existing_recovery_regression",
    "selected_state_remains_penetrating_without_posebusters_validity_change",
)
MAX_DURABLE_RECEIPT_BYTES = 4 * 1024 * 1024


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _git_executable() -> Path:
    for candidate in (Path("/usr/bin/git"), Path("/bin/git")):
        if candidate.is_file():
            return candidate
    raise RuntimeError("a fixed system Git executable is required")


def _run_git(repository_root: Path, *arguments: str) -> str:
    root = repository_root.resolve(strict=True)
    completed = subprocess.run(
        [str(_git_executable()), "-C", str(root), *arguments],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().replace("\n", " ")[:240]
        raise RuntimeError(f"Git source verification failed: {detail}")
    return completed.stdout.strip()


def require_clean_checkout(repository_root: Path) -> str:
    """Return exact lowercase Git HEAD only for a clean complete checkout."""

    head = _run_git(repository_root, "rev-parse", "--verify", "HEAD^{commit}")
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise RuntimeError("observed Git HEAD is not a lowercase SHA-1")
    status = _run_git(
        repository_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise RuntimeError("one-shot authority requires a clean Git checkout")
    return head


def _durable_path_components(path: Path, *, repository_root: Path) -> tuple[Path, ...]:
    root = repository_root.resolve(strict=True)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("durable receipt path escapes the repository root") from exc
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise RuntimeError("durable receipt path contains an unsafe component")
    current = root
    components: list[Path] = []
    for component in relative.parts:
        current = current / component
        components.append(current)
    return tuple(components)


def read_durable_receipt(
    path: Path,
    *,
    repository_root: Path,
    name: str,
) -> dict[str, Any]:
    """Read an exact owner-only JSON receipt without following symlinks."""

    components = _durable_path_components(path, repository_root=repository_root)
    if not components:
        raise RuntimeError(f"{name} path is empty")
    for directory in components[:-1]:
        try:
            observed = os.lstat(directory)
        except OSError as exc:
            raise RuntimeError(f"{name} cannot be opened safely: {exc}") from exc
        if stat.S_ISLNK(observed.st_mode) or not stat.S_ISDIR(observed.st_mode):
            raise RuntimeError(f"{name} path contains a symlink or non-directory")
        if stat.S_IMODE(observed.st_mode) != 0o700:
            raise RuntimeError(f"{name} directory must have mode 0700")

    target = components[-1]
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(target, flags)
    except OSError as exc:
        raise RuntimeError(f"{name} cannot be opened safely: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"{name} must be a regular file")
        if stat.S_IMODE(before.st_mode) != 0o600:
            raise RuntimeError(f"{name} must have mode 0600")
        if before.st_size <= 0 or before.st_size > MAX_DURABLE_RECEIPT_BYTES:
            raise RuntimeError(f"{name} size is outside the bounded receipt envelope")
        chunks: list[bytes] = []
        observed_size = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, MAX_DURABLE_RECEIPT_BYTES + 1))
            if not chunk:
                break
            observed_size += len(chunk)
            if observed_size > MAX_DURABLE_RECEIPT_BYTES:
                raise RuntimeError(f"{name} exceeds the bounded receipt envelope")
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if identity_before != identity_after or observed_size != before.st_size:
        raise RuntimeError(f"{name} changed while it was being read")
    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{name} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{name} must be a JSON object")
    return payload


def install_source_paired_clearance_one_shot_binding() -> str:
    """Return a compatibility receipt without mutating any imported module."""

    return _sha256(
        {
            "schema_id": SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID,
            "one_shot_policy_schema_id": EXPECTED_POLICY_SCHEMA_ID,
            "one_shot_policy_sha256": EXPECTED_ONE_SHOT_POLICY_SHA256,
            "verdict_schema_id": EXPECTED_VERDICT_SCHEMA_ID,
            "phase25_policy_sha256": EXPECTED_PHASE25_POLICY_SHA256,
            "activation_policy_sha256": EXPECTED_ACTIVATION_POLICY_SHA256,
            "module_mutation_performed": False,
            "clean_git_checkout_required": True,
            "durable_receipt_reopen_required": True,
            "historical_ab_execution_authorized": False,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )


__all__ = [
    "EXPECTED_ACTIVATION_POLICY_SHA256",
    "EXPECTED_NO_GO_CRITERIA",
    "EXPECTED_ONE_SHOT_POLICY_SHA256",
    "EXPECTED_PHASE25_POLICY_SHA256",
    "EXPECTED_POLICY_SCHEMA_ID",
    "EXPECTED_VERDICT_SCHEMA_ID",
    "MAX_DURABLE_RECEIPT_BYTES",
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_BINDING_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_binding",
    "read_durable_receipt",
    "require_clean_checkout",
]
