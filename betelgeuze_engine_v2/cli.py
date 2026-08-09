"""Canonical-input command line entry point for the Engine v2 research surface.

The CLI deliberately accepts only canonical Engine v2 molecular documents and a
canonical typed pocket document. It performs no PDB/SDF parsing, protonation,
tautomer selection, atom typing, charge generation, parameter assignment, or
pocket prediction.

The ``dock-canonical`` command connects the existing contracts:

canonical receptor/ligand bytes
    -> typed pocket
    -> element-aware authenticated docking authority
    -> deterministic Haar pocket placement
    -> uncalibrated interpretable scorer
    -> failure-complete retained score-term evidence

The scorer source digest is observed from the installed package resource after
module import. It is recorded explicitly as non-attested execution provenance;
it is not equivalent to the hardened pre-import source-snapshot lane.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
from importlib import resources
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Mapping, Sequence

import torch

from .contracts import DISTRIBUTION_VERSION, ENGINE_API_VERSION
from .docking import (
    DockingBudget,
    DockingScope,
    InterpretablePoseScorerV0,
    PocketDefinition,
    build_element_aware_authenticated_known_pocket_docking_problem,
    run_authenticated_interpretable_pocket_search,
)
from .molecular import all_atom_system_from_canonical_json


CLI_POCKET_INPUT_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_pocket_input/1.0.0"
)
CLI_DOCKING_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_cli_docking_result/1.0.0"
)
CLI_FAILURE_SCHEMA_ID = "betelgeuze.engine_v2_cli_failure/1.0.0"
CLI_COMMAND_ID = "betelgeuze-engine-v2/dock-canonical/1.0.0"
SCORER_SOURCE_BINDING_MODE = (
    "observed_installed_package_resource_after_import_not_preimport_attested"
)
MAX_CLI_INPUT_BYTES = 128 * 1024 * 1024
MAX_CLI_POCKET_BYTES = 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_RENAME_NOREPLACE = 1
_RENAME_EXCHANGE = 2


class EngineV2CliError(RuntimeError):
    """The canonical CLI contract failed closed."""


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
        raise EngineV2CliError(
            "CLI output is not canonical JSON"
        ) from exc


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_document(value: object) -> str:
    return _sha256_bytes(_canonical_bytes(value))


def _directory_open_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise EngineV2CliError(
            "descriptor-anchored no-follow path handling is unavailable"
        )
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _open_parent_directory(path: Path, *, create: bool) -> tuple[int, str]:
    """Open ``path.parent`` without following any user-controlled symlink."""

    candidate = Path(path)
    parts = candidate.parts
    if not parts:
        raise EngineV2CliError("path is empty")
    leaf = parts[-1]
    if leaf in {"", ".", "..", os.sep} or os.sep in leaf:
        raise EngineV2CliError("path has an unsafe final component")
    if candidate.is_absolute():
        parent = os.open(os.sep, _directory_open_flags())
        components = parts[1:-1]
    else:
        parent = os.open(".", _directory_open_flags())
        components = parts[:-1]
    try:
        for component in components:
            if component in {"", ".", "..", os.sep} or os.sep in component:
                raise EngineV2CliError("path contains an unsafe parent component")
            try:
                child = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=parent,
                )
            except FileNotFoundError:
                if not create:
                    raise EngineV2CliError("path parent does not exist") from None
                try:
                    os.mkdir(component, 0o700, dir_fd=parent)
                except FileExistsError:
                    # A concurrent creator is acceptable only if the following
                    # no-follow directory open admits the exact component.
                    pass
                child = os.open(
                    component,
                    _directory_open_flags(),
                    dir_fd=parent,
                )
                try:
                    # The child entry itself must survive a crash, not only
                    # later writes inside the final directory.
                    os.fsync(parent)
                except OSError as exc:
                    os.close(child)
                    raise EngineV2CliError(
                        "created path parent could not be synchronized"
                    ) from exc
            except OSError as exc:
                raise EngineV2CliError(
                    "path parent traversal is not a no-follow directory walk"
                ) from exc
            os.close(parent)
            parent = child
        return parent, leaf
    except Exception:
        os.close(parent)
        raise


def _regular_file_identity(path: Path, *, name: str) -> tuple[int, int]:
    parent, leaf = _open_parent_directory(path, create=False)
    descriptor = -1
    try:
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(leaf, flags, dir_fd=parent)
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
            raise EngineV2CliError(f"{name} must be a single-link regular file")
        return observed.st_dev, observed.st_ino
    except EngineV2CliError:
        raise
    except OSError as exc:
        raise EngineV2CliError(f"{name} could not be inspected safely") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent)


def _read_bounded(path: Path, *, maximum: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= os.O_NOFOLLOW
    parent, leaf = _open_parent_directory(path, create=False)
    descriptor = -1
    try:
        descriptor = os.open(leaf, flags, dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise EngineV2CliError(
                f"{name} must be a single-link regular file"
            )
        if not 0 < before.st_size <= maximum:
            raise EngineV2CliError(f"{name} exceeds its byte bound")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, _READ_CHUNK_BYTES)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise EngineV2CliError(f"{name} exceeds its byte bound")
        after = os.fstat(descriptor)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or total != after.st_size:
            raise EngineV2CliError(
                f"{name} changed while it was being read"
            )
        return b"".join(chunks)
    except EngineV2CliError:
        raise
    except OSError as exc:
        raise EngineV2CliError(f"{name} could not be read") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent)


def _reject_duplicate_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise EngineV2CliError(
                f"pocket document contains duplicate key {key!r}"
            )
        result[key] = value
    return result


def _load_canonical_pocket_document(raw: bytes) -> Mapping[str, object]:
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    if not canonical or b"\r" in raw or raw.endswith(b"\n\n"):
        raise EngineV2CliError("pocket document has non-canonical line endings")
    try:
        text = canonical.decode("ascii")
        document = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineV2CliError("pocket document is invalid JSON") from exc
    if not isinstance(document, dict):
        raise EngineV2CliError("pocket document must be a JSON object")
    if _canonical_bytes(document) != canonical:
        raise EngineV2CliError("pocket document bytes are not canonical")
    return document


def _exact_keys(
    document: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str],
) -> None:
    keys = set(document)
    missing = required - keys
    unexpected = keys - required - optional
    if missing:
        raise EngineV2CliError(
            "pocket document is missing fields: " + ", ".join(sorted(missing))
        )
    if unexpected:
        raise EngineV2CliError(
            "pocket document has unexpected fields: "
            + ", ".join(sorted(unexpected))
        )


def _pocket_from_document(document: Mapping[str, object]) -> PocketDefinition:
    _exact_keys(
        document,
        required={
            "schema_id",
            "scope",
            "method_id",
            "method_version",
            "coordinate_frame_id",
            "center_angstrom",
            "radius_angstrom",
            "source_artifact_sha256",
            "implementation_source_sha256",
        },
        optional={"metadata"},
    )
    if document["schema_id"] != CLI_POCKET_INPUT_SCHEMA_ID:
        raise EngineV2CliError("pocket document schema is unsupported")
    center = document["center_angstrom"]
    if (
        not isinstance(center, list)
        or len(center) != 3
        or any(isinstance(value, bool) for value in center)
    ):
        raise EngineV2CliError(
            "pocket center_angstrom must contain exactly three numbers"
        )
    try:
        center_tensor = torch.tensor(center, dtype=torch.float64)
        radius_value = document["radius_angstrom"]
        if isinstance(radius_value, bool) or not isinstance(
            radius_value, (int, float)
        ):
            raise TypeError("pocket radius must be a JSON number")
        radius = float(radius_value)
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket geometry is invalid") from exc
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        raise EngineV2CliError("pocket metadata must be a JSON object")
    try:
        return PocketDefinition(
            scope=DockingScope(str(document["scope"])),
            method_id=str(document["method_id"]),
            method_version=str(document["method_version"]),
            coordinate_frame_id=str(document["coordinate_frame_id"]),
            center=center_tensor,
            radius_angstrom=radius,
            source_artifact_sha256=str(
                document["source_artifact_sha256"]
            ),
            implementation_source_sha256=str(
                document["implementation_source_sha256"]
            ),
            metadata=metadata,
        )
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError("pocket contract is invalid") from exc


def _installed_scorer_source_sha256() -> str:
    try:
        resource = resources.files(
            "betelgeuze_engine_v2.docking"
        ).joinpath("interpretable_scorer.py")
        payload = resource.read_bytes()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise EngineV2CliError(
            "installed scorer source resource is unavailable"
        ) from exc
    if not payload:
        raise EngineV2CliError("installed scorer source resource is empty")
    return _sha256_bytes(payload)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("CLI output write made no progress")
        view = view[written:]


def _renameat2(
    source_directory: int,
    source_name: str,
    destination_directory: int,
    destination_name: str,
    *,
    flags: int,
) -> None:
    """Call Linux ``renameat2`` or fail closed instead of weakening atomicity."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise EngineV2CliError("atomic no-clobber rename is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_directory,
        os.fsencode(source_name),
        destination_directory,
        os.fsencode(destination_name),
        flags,
    )
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination_name)


def _lstat_at(directory: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None


def _inode_identity(observed: os.stat_result) -> tuple[int, int]:
    return observed.st_dev, observed.st_ino


def _unlink_if_identity(
    directory: int,
    name: str,
    expected: tuple[int, int] | None,
) -> bool:
    if expected is None:
        return False
    observed = _lstat_at(directory, name)
    if observed is None or _inode_identity(observed) != expected:
        return False
    os.unlink(name, dir_fd=directory)
    return True


def _descriptor_contains(descriptor: int, expected: bytes) -> bool:
    observed = os.fstat(descriptor)
    if observed.st_size != len(expected):
        return False
    offset = 0
    chunks: list[bytes] = []
    while offset < len(expected):
        chunk = os.pread(
            descriptor,
            min(_READ_CHUNK_BYTES, len(expected) - offset),
            offset,
        )
        if not chunk:
            return False
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks) == expected


def _require_safe_existing_output(
    observed: os.stat_result | None,
    *,
    input_identities: set[tuple[int, int]],
) -> None:
    if observed is None:
        return
    if not stat.S_ISREG(observed.st_mode) or observed.st_nlink != 1:
        raise EngineV2CliError(
            "output must be absent or a single-link regular file"
        )
    if (observed.st_dev, observed.st_ino) in input_identities:
        raise EngineV2CliError("input and output must not alias the same file")


def _fsync_directory(descriptor: int) -> None:
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise EngineV2CliError("output directory could not be synchronized") from exc


def _write_output(
    document: Mapping[str, object],
    path: Path,
    *,
    overwrite: bool,
    input_paths: Sequence[Path] = (),
) -> None:
    payload = _canonical_bytes(document) + b"\n"
    input_identities = {
        _regular_file_identity(source, name="CLI input")
        for source in input_paths
    }
    parent, leaf = _open_parent_directory(path, create=True)
    temporary = f".{leaf}.tmp-{os.getpid()}-{secrets.token_hex(8)}"
    descriptor = -1
    existing_descriptor = -1
    temporary_identity: tuple[int, int] | None = None
    cleanup_identity: tuple[int, int] | None = None
    try:
        existing = _lstat_at(parent, leaf)
        _require_safe_existing_output(
            existing,
            input_identities=input_identities,
        )
        if existing is not None and not overwrite:
            raise EngineV2CliError(
                "output already exists; use --overwrite to replace it"
            )
        if existing is not None:
            try:
                existing_descriptor = os.open(
                    leaf,
                    os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=parent,
                )
            except OSError as exc:
                raise EngineV2CliError(
                    "output changed before it could be pinned"
                ) from exc
            pinned = os.fstat(existing_descriptor)
            _require_safe_existing_output(
                pinned,
                input_identities=input_identities,
            )
            if (pinned.st_dev, pinned.st_ino) != (
                existing.st_dev,
                existing.st_ino,
            ):
                raise EngineV2CliError("output changed before it could be pinned")
            # Keep this descriptor open through publication. Besides proving
            # lstat/open identity, this prevents an unlink/recreate race from
            # reusing the admitted inode number (the classic ABA case).
            existing = pinned
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_CLOEXEC", 0)
        flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent)
        temporary_identity = _inode_identity(os.fstat(descriptor))
        cleanup_identity = temporary_identity
        _write_all(descriptor, payload)
        os.fsync(descriptor)
        if not _descriptor_contains(descriptor, payload):
            raise EngineV2CliError("temporary output changed before publication")
        temporary_path = _lstat_at(parent, temporary)
        if (
            temporary_path is None
            or _inode_identity(temporary_path) != temporary_identity
        ):
            raise EngineV2CliError("temporary output path changed before publication")
        if existing is None:
            # Follow the kernel-owned /proc descriptor link, not the mutable
            # temporary pathname. This binds publication to the open inode.
            os.link(
                f"/proc/self/fd/{descriptor}",
                leaf,
                dst_dir_fd=parent,
                follow_symlinks=True,
            )
            published = _lstat_at(parent, leaf)
            if (
                published is None
                or _inode_identity(published) != temporary_identity
                or not _descriptor_contains(descriptor, payload)
            ):
                if (
                    published is not None
                    and _inode_identity(published) == temporary_identity
                ):
                    _unlink_if_identity(parent, leaf, temporary_identity)
                    _fsync_directory(parent)
                raise EngineV2CliError("published output identity is inconsistent")
            _unlink_if_identity(parent, temporary, temporary_identity)
            cleanup_identity = None
        else:
            current = _lstat_at(parent, leaf)
            _require_safe_existing_output(
                current,
                input_identities=input_identities,
            )
            if current is None or (
                current.st_dev,
                current.st_ino,
            ) != (existing.st_dev, existing.st_ino):
                raise EngineV2CliError("output changed before atomic replacement")
            _renameat2(
                parent,
                temporary,
                parent,
                leaf,
                flags=_RENAME_EXCHANGE,
            )
            moved = _lstat_at(parent, temporary)
            published = _lstat_at(parent, leaf)
            if (
                moved is None
                or _inode_identity(moved) != _inode_identity(existing)
                or published is None
                or _inode_identity(published) != temporary_identity
                or not _descriptor_contains(descriptor, payload)
            ):
                rollback_confirmed = False
                try:
                    if (
                        moved is not None
                        and published is not None
                        and stat.S_ISREG(moved.st_mode)
                        and stat.S_ISREG(published.st_mode)
                        and moved.st_nlink == 1
                        and published.st_nlink == 1
                        # Only try to undo an exchange when at least one side
                        # is still an inode pinned by this operation. Never
                        # exchange two wholly unrelated replacement paths.
                        and (
                            _inode_identity(moved) == _inode_identity(existing)
                            or _inode_identity(published) == temporary_identity
                        )
                    ):
                        rollback_source = _lstat_at(parent, temporary)
                        rollback_destination = _lstat_at(parent, leaf)
                        if (
                            rollback_source is not None
                            and rollback_destination is not None
                            and _inode_identity(rollback_source)
                            == _inode_identity(moved)
                            and _inode_identity(rollback_destination)
                            == _inode_identity(published)
                        ):
                            _renameat2(
                                parent,
                                temporary,
                                parent,
                                leaf,
                                flags=_RENAME_EXCHANGE,
                            )
                            rolled_back = _lstat_at(parent, leaf)
                            displaced = _lstat_at(parent, temporary)
                            rollback_confirmed = (
                                rolled_back is not None
                                and displaced is not None
                                and _inode_identity(rolled_back)
                                == _inode_identity(moved)
                                and _inode_identity(displaced)
                                == _inode_identity(published)
                            )
                            if rollback_confirmed:
                                _fsync_directory(parent)
                except (EngineV2CliError, OSError):
                    rollback_confirmed = False
                if not rollback_confirmed:
                    raise EngineV2CliError(
                        "output identity changed during atomic replacement; "
                        "rollback was not confirmed"
                    )
                raise EngineV2CliError(
                    "output identity changed during atomic replacement"
                )
            cleanup_identity = _inode_identity(existing)
            _unlink_if_identity(parent, temporary, cleanup_identity)
            cleanup_identity = None
        _fsync_directory(parent)
    except EngineV2CliError:
        raise
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise EngineV2CliError("output was created concurrently") from exc
        raise EngineV2CliError("CLI output could not be written durably") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if existing_descriptor >= 0:
            os.close(existing_descriptor)
        try:
            _unlink_if_identity(parent, temporary, cleanup_identity)
        finally:
            os.close(parent)


def _write_private_bundle(
    files: Mapping[str, bytes],
    output_directory: Path,
    *,
    input_paths: Sequence[Path] = (),
) -> None:
    """Publish an owner-only, absent-only directory as one atomic bundle."""

    if not files:
        raise EngineV2CliError("bundle must contain at least one file")
    normalized: dict[str, bytes] = {}
    for raw_name, raw_payload in files.items():
        filename = str(raw_name)
        if (
            not filename
            or filename in {".", ".."}
            or os.sep in filename
            or (os.altsep is not None and os.altsep in filename)
        ):
            raise EngineV2CliError("bundle contains an unsafe filename")
        payload = bytes(raw_payload)
        if not payload:
            raise EngineV2CliError("bundle files must not be empty")
        normalized[filename] = payload

    # Inspect every input through the same no-follow walker before creating
    # staging state. This rejects hard links, FIFOs, and parent symlinks.
    for source in input_paths:
        _regular_file_identity(source, name="bundle input")

    parent, leaf = _open_parent_directory(output_directory, create=True)
    if _lstat_at(parent, leaf) is not None:
        os.close(parent)
        raise EngineV2CliError("bundle output directory must be absent")
    staging = f".{leaf}.staging-{os.getpid()}-{secrets.token_hex(8)}"
    staging_descriptor = -1
    staging_identity: tuple[int, int] | None = None
    created_names: list[str] = []
    published = False
    try:
        os.mkdir(staging, 0o700, dir_fd=parent)
        created_staging = _lstat_at(parent, staging)
        if created_staging is None or not stat.S_ISDIR(created_staging.st_mode):
            raise EngineV2CliError("bundle staging directory was replaced")
        staging_identity = _inode_identity(created_staging)
        staging_descriptor = os.open(
            staging,
            _directory_open_flags(),
            dir_fd=parent,
        )
        if _inode_identity(os.fstat(staging_descriptor)) != staging_identity:
            raise EngineV2CliError("bundle staging directory changed while opening")
        for filename in sorted(normalized):
            descriptor = os.open(
                filename,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | os.O_NOFOLLOW
                | getattr(os, "O_CLOEXEC", 0),
                0o600,
                dir_fd=staging_descriptor,
            )
            created_names.append(filename)
            try:
                _write_all(descriptor, normalized[filename])
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        _fsync_directory(staging_descriptor)
        staging_path = _lstat_at(parent, staging)
        if (
            staging_path is None
            or _inode_identity(staging_path) != staging_identity
        ):
            raise EngineV2CliError("bundle staging path changed before publication")
        _renameat2(
            parent,
            staging,
            parent,
            leaf,
            flags=_RENAME_NOREPLACE,
        )
        final_path = _lstat_at(parent, leaf)
        if final_path is None or _inode_identity(final_path) != staging_identity:
            try:
                if final_path is not None and _lstat_at(parent, staging) is None:
                    _renameat2(
                        parent,
                        leaf,
                        parent,
                        staging,
                        flags=_RENAME_NOREPLACE,
                    )
            except OSError:
                pass
            raise EngineV2CliError("published bundle identity is inconsistent")
        published = True
        _fsync_directory(parent)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            raise EngineV2CliError("bundle output directory was created concurrently") from exc
        raise EngineV2CliError("bundle could not be written durably") from exc
    finally:
        if not published and staging_descriptor >= 0:
            for filename in reversed(created_names):
                try:
                    os.unlink(filename, dir_fd=staging_descriptor)
                except FileNotFoundError:
                    pass
        if staging_descriptor >= 0:
            os.close(staging_descriptor)
        if not published:
            staging_path = _lstat_at(parent, staging)
            if (
                staging_path is not None
                and staging_identity is not None
                and _inode_identity(staging_path) == staging_identity
            ):
                try:
                    os.rmdir(staging, dir_fd=parent)
                except OSError:
                    pass
        os.close(parent)


def run_canonical_docking(
    *,
    receptor_path: Path,
    ligand_path: Path,
    pocket_path: Path,
    candidate_count: int,
    top_k: int,
    max_torsions: int,
    translation_radius_angstrom: float,
    seed: int,
    receptor_margin_angstrom: float,
) -> dict[str, object]:
    receptor_bytes = _read_bounded(
        receptor_path,
        maximum=MAX_CLI_INPUT_BYTES,
        name="receptor canonical document",
    )
    ligand_bytes = _read_bounded(
        ligand_path,
        maximum=MAX_CLI_INPUT_BYTES,
        name="ligand canonical document",
    )
    pocket_bytes = _read_bounded(
        pocket_path,
        maximum=MAX_CLI_POCKET_BYTES,
        name="pocket canonical document",
    )
    try:
        receptor = all_atom_system_from_canonical_json(receptor_bytes)
        ligand = all_atom_system_from_canonical_json(ligand_bytes)
    except (TypeError, ValueError) as exc:
        raise EngineV2CliError(
            "canonical molecular document is invalid"
        ) from exc
    pocket_document = _load_canonical_pocket_document(pocket_bytes)
    pocket = _pocket_from_document(pocket_document)
    authority = build_element_aware_authenticated_known_pocket_docking_problem(
        receptor,
        ligand,
        pocket,
        receptor_margin_angstrom=float(receptor_margin_angstrom),
    )
    source_sha = _installed_scorer_source_sha256()
    scorer = InterpretablePoseScorerV0(
        authority,
        implementation_source_sha256=source_sha,
    )
    budget = DockingBudget(
        candidate_count=candidate_count,
        top_k=top_k,
        max_torsions=max_torsions,
        translation_radius_angstrom=translation_radius_angstrom,
        seed=seed,
    )
    result = run_authenticated_interpretable_pocket_search(
        authority,
        budget,
        scorer,
    )
    projection: dict[str, object] = {
        "schema_id": CLI_DOCKING_RESULT_SCHEMA_ID,
        "command_id": CLI_COMMAND_ID,
        "engine_api_version": ENGINE_API_VERSION,
        "distribution_version": DISTRIBUTION_VERSION,
        "receptor_artifact_sha256": _sha256_bytes(receptor_bytes),
        "ligand_artifact_sha256": _sha256_bytes(ligand_bytes),
        "pocket_artifact_sha256": _sha256_bytes(pocket_bytes),
        "pocket_definition_sha256": pocket.fingerprint_sha256,
        "authenticated_input_receipt_sha256": authority.input_receipt_sha256,
        "scorer_source_sha256": source_sha,
        "scorer_source_binding_mode": SCORER_SOURCE_BINDING_MODE,
        "scorer_source_preimport_attested": False,
        "scorer_qualification": scorer.qualification_document(),
        "result_receipt_sha256": result.receipt_sha256,
        "candidate_count": len(result.rows),
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "network_fetch_performed": False,
        "chemistry_inference_performed": False,
        "pocket_prediction_performed": False,
        "calibrated": False,
        "scientifically_validated": False,
        "benchmark_validated": False,
        "product_qualified": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
        "result": result.to_dict(),
    }
    projection["document_sha256"] = _sha256_document(projection)
    return projection


def _failure_document(exc: BaseException) -> dict[str, object]:
    private = (
        f"{exc.__class__.__module__}.{exc.__class__.__qualname__}: {exc}"
    ).encode("utf-8", errors="replace")
    return {
        "schema_id": CLI_FAILURE_SCHEMA_ID,
        "status": "failure",
        "error_code": "engine_v2_cli_failed",
        "public_message": "Engine v2 canonical docking command failed",
        "private_error_sha256": _sha256_bytes(private),
        "private_error_byte_length": len(private),
        "claim_safe": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2",
        description=(
            "Fail-closed Engine v2 canonical-input research commands."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    dock = subparsers.add_parser(
        "dock-canonical",
        help=(
            "Run authenticated known-pocket docking from canonical Engine v2 inputs."
        ),
    )
    dock.add_argument("--receptor", type=Path, required=True)
    dock.add_argument("--ligand", type=Path, required=True)
    dock.add_argument("--pocket", type=Path, required=True)
    dock.add_argument("--output", type=Path)
    dock.add_argument("--overwrite", action="store_true")
    dock.add_argument("--candidate-count", type=int, default=64)
    dock.add_argument("--top-k", type=int, default=10)
    dock.add_argument("--max-torsions", type=int, default=32)
    dock.add_argument("--translation-radius-angstrom", type=float, default=4.0)
    dock.add_argument("--receptor-margin-angstrom", type=float, default=4.0)
    dock.add_argument("--seed", type=int, default=0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command != "dock-canonical":
            raise EngineV2CliError("unsupported command")
        document = run_canonical_docking(
            receptor_path=arguments.receptor,
            ligand_path=arguments.ligand,
            pocket_path=arguments.pocket,
            candidate_count=arguments.candidate_count,
            top_k=arguments.top_k,
            max_torsions=arguments.max_torsions,
            translation_radius_angstrom=(
                arguments.translation_radius_angstrom
            ),
            seed=arguments.seed,
            receptor_margin_angstrom=(
                arguments.receptor_margin_angstrom
            ),
        )
        if arguments.output is None:
            sys.stdout.buffer.write(_canonical_bytes(document) + b"\n")
            sys.stdout.buffer.flush()
        else:
            _write_output(
                document,
                arguments.output,
                overwrite=bool(arguments.overwrite),
            )
        return 0
    except Exception as exc:
        failure = _failure_document(exc)
        sys.stderr.buffer.write(_canonical_bytes(failure) + b"\n")
        sys.stderr.buffer.flush()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CLI_COMMAND_ID",
    "CLI_DOCKING_RESULT_SCHEMA_ID",
    "CLI_FAILURE_SCHEMA_ID",
    "CLI_POCKET_INPUT_SCHEMA_ID",
    "EngineV2CliError",
    "SCORER_SOURCE_BINDING_MODE",
    "main",
    "run_canonical_docking",
]
