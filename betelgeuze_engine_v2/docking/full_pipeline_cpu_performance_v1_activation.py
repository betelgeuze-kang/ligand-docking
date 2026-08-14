"""Non-consuming runtime-closure evidence for full-pipeline CPU activation v1.

The functions in this module inspect an already-started, isolated CPython
process.  They never create qualification state, invoke a prepared docking
session, read molecular inputs, or call a clock.  The activation bootstrap
loads the exact native extension only to bind its import and mapped shared
library closure before any exactly-once runner can be admitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType
from typing import Final, Mapping, Sequence


ACTIVATION_ID: Final = "engine_v2_full_pipeline_cpu_performance_v1_activation"
ACTIVATION_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_performance_activation/1.0.0"
)
STDLIB_CLOSURE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_python_stdlib_import_closure/1.0.0"
)
DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_executable_mapping_closure/1.0.0"
)
PREFLIGHT_EVIDENCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_activation_preflight/1.0.0"
)

PYTHON_STDLIB_ROOT: Final = Path("/usr/lib/python3.10")
MAX_CLOSURE_FILE_BYTES: Final = 32 * 1024 * 1024
MAX_CLOSURE_TOTAL_BYTES: Final = 128 * 1024 * 1024
MAX_STDLIB_MODULE_ROWS: Final = 512
MAX_EXECUTABLE_FILE_ROWS: Final = 128
ALLOWED_VIRTUAL_EXECUTABLE_MAPPINGS: Final = frozenset({"[vdso]", "[vsyscall]"})
SEALED_NATIVE_EXTENSION_MAP_PATH: Final = (
    "/memfd:engine-v2-native-extension-v1 (deleted)"
)
SEALED_NATIVE_EXTENSION_IDENTITY: Final = "sealed_memfd:engine-v2-native-extension-v1"


class FullPipelineCPUActivationError(RuntimeError):
    """Raised when a source, runtime, or closure boundary fails closed."""


def canonical_json_bytes(value: object) -> bytes:
    """Return the single canonical byte encoding used by closure receipts."""

    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def manifest_rows_sha256(rows: Sequence[Mapping[str, object]]) -> str:
    return sha256_bytes(canonical_json_bytes([dict(row) for row in rows]))


def _read_stable_regular_file(
    path: Path,
    *,
    name: str,
    allowed_owner_uids: tuple[int, ...],
    expected_mapping_identity: tuple[int, int, int] | None = None,
) -> bytes:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    if getattr(os, "O_NOFOLLOW", 0) == 0:
        raise FullPipelineCPUActivationError("safe no-follow reads are unavailable")
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise FullPipelineCPUActivationError(f"{name} cannot be opened safely") from exc
    try:
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid not in allowed_owner_uids
            or before.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
            or before.st_size < 0
            or before.st_size > MAX_CLOSURE_FILE_BYTES
        ):
            raise FullPipelineCPUActivationError(
                f"{name} is not a bounded controlled regular file: {path}"
            )
        observed_mapping_identity = (
            os.major(before.st_dev),
            os.minor(before.st_dev),
            before.st_ino,
        )
        if (
            expected_mapping_identity is not None
            and observed_mapping_identity != expected_mapping_identity
        ):
            raise FullPipelineCPUActivationError(
                f"{name} device/inode differs from the executable mapping"
            )
        chunks: list[bytes] = []
        observed = 0
        while observed <= MAX_CLOSURE_FILE_BYTES:
            chunk = os.read(
                descriptor,
                min(1 << 20, MAX_CLOSURE_FILE_BYTES + 1 - observed),
            )
            if not chunk:
                break
            chunks.append(chunk)
            observed += len(chunk)
        after = os.fstat(descriptor)
        identity_fields = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if observed != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in identity_fields
        ):
            raise FullPipelineCPUActivationError(f"{name} changed while read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _stdlib_file_identity(path: Path) -> tuple[str, bytes]:
    try:
        resolved = path.resolve(strict=True)
        relative = resolved.relative_to(PYTHON_STDLIB_ROOT.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise FullPipelineCPUActivationError(
            "imported standard-library module escaped the frozen stdlib root"
        ) from exc
    raw = _read_stable_regular_file(
        resolved,
        name="imported standard-library module",
        allowed_owner_uids=(0,),
    )
    return relative.as_posix(), raw


def _stdlib_cached_bytecode_identity(module: ModuleType) -> dict[str, object] | None:
    raw_cached = getattr(module, "__cached__", None)
    if raw_cached is None:
        return None
    if type(raw_cached) is not str or not raw_cached:
        raise FullPipelineCPUActivationError(
            "imported standard-library bytecode cache identity is invalid"
        )
    path = Path(raw_cached)
    if not path.is_absolute() or path.suffix != ".pyc":
        raise FullPipelineCPUActivationError(
            "imported standard-library bytecode cache path is invalid"
        )
    try:
        relative, raw = _stdlib_file_identity(path)
    except FullPipelineCPUActivationError as exc:
        try:
            root = PYTHON_STDLIB_ROOT.resolve(strict=True)
            parent = path.parent.resolve(strict=True)
            unresolved = parent / path.name
            relative_path = unresolved.relative_to(root)
        except (OSError, ValueError) as path_exc:
            raise FullPipelineCPUActivationError(
                "imported standard-library bytecode cache escaped the frozen root"
            ) from path_exc
        try:
            unresolved.lstat()
        except FileNotFoundError:
            return {
                "path": relative_path.as_posix(),
                "present": False,
            }
        except OSError as path_exc:
            raise FullPipelineCPUActivationError(
                "imported standard-library bytecode cache state is ambiguous"
            ) from path_exc
        raise exc
    return {
        "path": relative,
        "present": True,
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def derive_stdlib_import_closure(
    modules: Mapping[str, ModuleType] | None = None,
) -> dict[str, object]:
    """Hash built-ins plus source, extension, and declared bytecode identities."""

    source = sys.modules if modules is None else modules
    rows: list[dict[str, object]] = []
    total_bytes = 0
    cached_bytecode_file_count = 0
    cached_bytecode_total_bytes = 0
    for name, module in sorted(source.items()):
        if type(name) is not str or not name or not isinstance(module, ModuleType):
            continue
        spec = getattr(module, "__spec__", None)
        origin = getattr(spec, "origin", None)
        if origin in {"built-in", "frozen"}:
            rows.append({"module": name, "origin": origin})
            continue
        raw_file = getattr(module, "__file__", None)
        if type(raw_file) is not str or not raw_file:
            continue
        path = Path(raw_file)
        try:
            relative, raw = _stdlib_file_identity(path)
        except FullPipelineCPUActivationError:
            # Repository modules and the separately bound native extension are
            # intentionally outside this standard-library-only projection.
            try:
                path.resolve(strict=True).relative_to(
                    PYTHON_STDLIB_ROOT.resolve(strict=True)
                )
            except (OSError, ValueError):
                continue
            raise
        row: dict[str, object] = {
            "module": name,
            "origin": "stdlib_file",
            "path": relative,
            "sha256": sha256_bytes(raw),
            "size_bytes": len(raw),
        }
        cached = _stdlib_cached_bytecode_identity(module)
        if relative.endswith(".py") and cached is None:
            raise FullPipelineCPUActivationError(
                "source-backed standard-library module lacks a bytecode cache identity"
            )
        if cached is not None:
            row["cached_bytecode"] = cached
            if cached["present"] is True:
                cached_bytecode_file_count += 1
                cached_bytecode_total_bytes += int(cached["size_bytes"])
        rows.append(row)
        total_bytes += len(raw)
    if not rows or len(rows) > MAX_STDLIB_MODULE_ROWS:
        raise FullPipelineCPUActivationError(
            "standard-library import closure row count is invalid"
        )
    if total_bytes + cached_bytecode_total_bytes > MAX_CLOSURE_TOTAL_BYTES:
        raise FullPipelineCPUActivationError(
            "standard-library import closure exceeds its byte envelope"
        )
    return {
        "schema_id": STDLIB_CLOSURE_SCHEMA_ID,
        "module_count": len(rows),
        "file_backed_module_count": sum(
            row.get("origin") == "stdlib_file" for row in rows
        ),
        "file_backed_total_bytes": total_bytes,
        "cached_bytecode_file_count": cached_bytecode_file_count,
        "cached_bytecode_total_bytes": cached_bytecode_total_bytes,
        "rows_sha256": manifest_rows_sha256(rows),
        "rows": rows,
    }


def _mapped_executable_identity(path: Path, *, site_packages: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return (
            "qualified_site_packages/"
            + resolved.relative_to(site_packages.resolve(strict=True)).as_posix()
        )
    except ValueError:
        pass
    try:
        return (
            "stdlib/"
            + resolved.relative_to(PYTHON_STDLIB_ROOT.resolve(strict=True)).as_posix()
        )
    except ValueError:
        return "system:" + str(resolved)


def _parse_mapping_device_inode(*, device: str, inode: str) -> tuple[int, int, int]:
    try:
        major_text, minor_text = device.split(":", maxsplit=1)
        major = int(major_text, 16)
        minor = int(minor_text, 16)
        inode_number = int(inode, 10)
    except (TypeError, ValueError) as exc:
        raise FullPipelineCPUActivationError(
            "executable mapping device/inode is invalid"
        ) from exc
    if major < 0 or minor < 0 or inode_number <= 0:
        raise FullPipelineCPUActivationError(
            "executable mapping device/inode is invalid"
        )
    return major, minor, inode_number


def _require_mapping_permissions(permissions: str) -> None:
    if (
        len(permissions) != 4
        or permissions[0] not in {"r", "-"}
        or permissions[1] not in {"w", "-"}
        or permissions[2] not in {"x", "-"}
        or permissions[3] not in {"p", "s"}
    ):
        raise FullPipelineCPUActivationError("process map contains invalid permissions")


def _read_stable_sealed_snapshot_descriptor(
    descriptor: int,
) -> tuple[tuple[int, int, int], bytes]:
    try:
        before = os.fstat(descriptor)
    except OSError as exc:
        raise FullPipelineCPUActivationError(
            "sealed executable snapshot descriptor is unavailable"
        ) from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.geteuid()
        or before.st_gid != os.getegid()
        or stat.S_IMODE(before.st_mode) != 0o500
        or before.st_nlink != 0
        or not 1 <= before.st_size <= MAX_CLOSURE_FILE_BYTES
    ):
        raise FullPipelineCPUActivationError(
            "sealed executable snapshot descriptor is invalid"
        )
    chunks: list[bytes] = []
    observed = 0
    while observed <= MAX_CLOSURE_FILE_BYTES:
        chunk = os.pread(
            descriptor,
            min(1 << 20, MAX_CLOSURE_FILE_BYTES + 1 - observed),
            observed,
        )
        if not chunk:
            break
        chunks.append(chunk)
        observed += len(chunk)
    after = os.fstat(descriptor)
    identity_fields = (
        "st_dev",
        "st_ino",
        "st_mode",
        "st_uid",
        "st_gid",
        "st_nlink",
        "st_size",
        "st_mtime_ns",
        "st_ctime_ns",
    )
    if observed != before.st_size or any(
        getattr(before, field) != getattr(after, field) for field in identity_fields
    ):
        raise FullPipelineCPUActivationError(
            "sealed executable snapshot changed while read"
        )
    return (
        (os.major(before.st_dev), os.minor(before.st_dev), before.st_ino),
        b"".join(chunks),
    )


def derive_dynamic_library_closure(
    *,
    site_packages: Path,
    process_maps_path: Path | None = None,
    required_executable_file_identity: tuple[int, int, int] | None = None,
    sealed_executable_descriptor: int | None = None,
) -> dict[str, object]:
    """Hash every file-backed executable mapping in the activation process."""

    maps_path = process_maps_path or Path(f"/proc/{os.getpid()}/maps")
    try:
        lines = maps_path.read_text(encoding="ascii", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise FullPipelineCPUActivationError(
            "dynamic-library process map is unavailable"
        ) from exc
    sealed_identity: tuple[int, int, int] | None = None
    sealed_raw: bytes | None = None
    if sealed_executable_descriptor is not None:
        sealed_identity, sealed_raw = _read_stable_sealed_snapshot_descriptor(
            sealed_executable_descriptor
        )
        if (
            required_executable_file_identity is not None
            and sealed_identity != required_executable_file_identity
        ):
            raise FullPipelineCPUActivationError(
                "required executable identity differs from sealed snapshot"
            )
    observed: dict[tuple[int, int, int], tuple[Path | None, str]] = {}
    path_identities: dict[Path, tuple[int, int, int]] = {}
    virtual_executable_mappings: set[str] = set()
    for line in lines:
        fields = line.split(maxsplit=5)
        if len(fields) < 5:
            raise FullPipelineCPUActivationError("process map row is malformed")
        permissions = fields[1]
        _require_mapping_permissions(permissions)
        if permissions[2] != "x":
            continue
        raw_path = fields[5] if len(fields) == 6 else ""
        if not raw_path.startswith("/"):
            if raw_path not in ALLOWED_VIRTUAL_EXECUTABLE_MAPPINGS:
                raise FullPipelineCPUActivationError(
                    "unexpected anonymous executable mapping"
                )
            virtual_executable_mappings.add(raw_path)
            continue
        mapping_identity = _parse_mapping_device_inode(
            device=fields[3], inode=fields[4]
        )
        if raw_path.endswith(" (deleted)"):
            if (
                sealed_identity is None
                or mapping_identity != sealed_identity
                or raw_path != SEALED_NATIVE_EXTENSION_MAP_PATH
            ):
                raise FullPipelineCPUActivationError(
                    "deleted executable file mapping is forbidden"
                )
            previous = observed.setdefault(
                mapping_identity,
                (None, SEALED_NATIVE_EXTENSION_IDENTITY),
            )
            if previous != (None, SEALED_NATIVE_EXTENSION_IDENTITY):
                raise FullPipelineCPUActivationError(
                    "sealed executable mapping identity is ambiguous"
                )
            continue
        try:
            path = Path(raw_path).resolve(strict=True)
            identity = _mapped_executable_identity(path, site_packages=site_packages)
        except OSError as exc:
            raise FullPipelineCPUActivationError(
                "mapped executable file is unavailable"
            ) from exc
        previous_path_identity = path_identities.setdefault(path, mapping_identity)
        if previous_path_identity != mapping_identity:
            raise FullPipelineCPUActivationError(
                "mapped executable file identity is ambiguous"
            )
        previous = observed.setdefault(mapping_identity, (path, identity))
        if previous != (path, identity):
            raise FullPipelineCPUActivationError(
                "mapped executable device/inode has ambiguous paths"
            )
    if (
        required_executable_file_identity is not None
        and required_executable_file_identity not in observed
    ):
        raise FullPipelineCPUActivationError(
            "authenticated native extension is not an executable mapping"
        )
    rows: list[dict[str, object]] = []
    total_bytes = 0
    for mapping_identity, (path, identity) in sorted(
        observed.items(), key=lambda item: item[1][1]
    ):
        if path is None:
            if sealed_executable_descriptor is None or sealed_raw is None:
                raise FullPipelineCPUActivationError(
                    "sealed executable mapping lacks its descriptor"
                )
            observed_identity, raw = _read_stable_sealed_snapshot_descriptor(
                sealed_executable_descriptor
            )
            if observed_identity != mapping_identity or raw != sealed_raw:
                raise FullPipelineCPUActivationError(
                    "sealed executable mapping changed during closure derivation"
                )
        else:
            raw = _read_stable_regular_file(
                path,
                name="mapped executable file",
                allowed_owner_uids=(0, os.geteuid()),
                expected_mapping_identity=mapping_identity,
            )
        rows.append(
            {
                "path": identity,
                "sha256": sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
        total_bytes += len(raw)
    if not rows or len(rows) > MAX_EXECUTABLE_FILE_ROWS:
        raise FullPipelineCPUActivationError(
            "executable-file closure row count is invalid"
        )
    if total_bytes > MAX_CLOSURE_TOTAL_BYTES:
        raise FullPipelineCPUActivationError(
            "executable-file closure exceeds its byte envelope"
        )
    return {
        "schema_id": DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        "executable_file_count": len(rows),
        "total_bytes": total_bytes,
        "virtual_executable_mappings": sorted(virtual_executable_mappings),
        "rows_sha256": manifest_rows_sha256(rows),
        "rows": rows,
    }


def _validated_executable_closure_rows(
    document: Mapping[str, object], *, name: str
) -> dict[str, dict[str, object]]:
    expected_keys = {
        "schema_id",
        "executable_file_count",
        "total_bytes",
        "virtual_executable_mappings",
        "rows_sha256",
        "rows",
    }
    if type(document) is not dict or set(document) != expected_keys:
        raise FullPipelineCPUActivationError(f"{name} is not an exact closure object")
    if document["schema_id"] != DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID:
        raise FullPipelineCPUActivationError(f"{name} schema changed")
    raw_virtual = document["virtual_executable_mappings"]
    if (
        type(raw_virtual) is not list
        or any(
            type(value) is not str or value not in ALLOWED_VIRTUAL_EXECUTABLE_MAPPINGS
            for value in raw_virtual
        )
        or raw_virtual != sorted(set(raw_virtual))
    ):
        raise FullPipelineCPUActivationError(f"{name} virtual mappings changed")
    raw_rows = document["rows"]
    if type(raw_rows) is not list or not raw_rows:
        raise FullPipelineCPUActivationError(f"{name} rows changed")
    rows: dict[str, dict[str, object]] = {}
    total_bytes = 0
    ordered_paths: list[str] = []
    for raw_row in raw_rows:
        if type(raw_row) is not dict or set(raw_row) != {
            "path",
            "sha256",
            "size_bytes",
        }:
            raise FullPipelineCPUActivationError(f"{name} row changed")
        path = raw_row["path"]
        digest = raw_row["sha256"]
        size = raw_row["size_bytes"]
        if (
            type(path) is not str
            or not path
            or not path.isascii()
            or type(digest) is not str
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or type(size) is not int
            or size <= 0
        ):
            raise FullPipelineCPUActivationError(f"{name} row identity changed")
        if path in rows:
            raise FullPipelineCPUActivationError(f"{name} contains duplicate rows")
        row = dict(raw_row)
        rows[path] = row
        ordered_paths.append(path)
        total_bytes += size
    if ordered_paths != sorted(ordered_paths):
        raise FullPipelineCPUActivationError(f"{name} row order changed")
    if (
        type(document["executable_file_count"]) is not int
        or document["executable_file_count"] != len(raw_rows)
        or type(document["total_bytes"]) is not int
        or document["total_bytes"] != total_bytes
        or document["rows_sha256"] != manifest_rows_sha256(raw_rows)
    ):
        raise FullPipelineCPUActivationError(f"{name} summary changed")
    return rows


def require_exact_native_initialization_delta(
    preinit: Mapping[str, object],
    postinit: Mapping[str, object],
    *,
    native_extension_sha256: str,
    native_extension_size_bytes: int,
) -> None:
    """Require native initialization to add only its authenticated sealed mapping."""

    if (
        type(native_extension_sha256) is not str
        or len(native_extension_sha256) != 64
        or any(
            character not in "0123456789abcdef" for character in native_extension_sha256
        )
        or type(native_extension_size_bytes) is not int
        or native_extension_size_bytes <= 0
    ):
        raise FullPipelineCPUActivationError(
            "native initialization expected identity is invalid"
        )
    preinit_rows = _validated_executable_closure_rows(
        preinit, name="pre-initialization executable closure"
    )
    postinit_rows = _validated_executable_closure_rows(
        postinit, name="post-initialization executable closure"
    )
    if (
        preinit["virtual_executable_mappings"]
        != postinit["virtual_executable_mappings"]
    ):
        raise FullPipelineCPUActivationError(
            "native initialization changed virtual executable mappings"
        )
    expected_postinit_paths = set(preinit_rows) | {SEALED_NATIVE_EXTENSION_IDENTITY}
    if (
        SEALED_NATIVE_EXTENSION_IDENTITY in preinit_rows
        or set(postinit_rows) != expected_postinit_paths
    ):
        raise FullPipelineCPUActivationError(
            "native initialization executable mapping delta changed"
        )
    for path, preinit_row in preinit_rows.items():
        if canonical_json_bytes(preinit_row) != canonical_json_bytes(
            postinit_rows[path]
        ):
            raise FullPipelineCPUActivationError(
                "native initialization changed an authenticated dependency mapping"
            )
    expected_native_row = {
        "path": SEALED_NATIVE_EXTENSION_IDENTITY,
        "sha256": native_extension_sha256,
        "size_bytes": native_extension_size_bytes,
    }
    if canonical_json_bytes(postinit_rows[SEALED_NATIVE_EXTENSION_IDENTITY]) != (
        canonical_json_bytes(expected_native_row)
    ):
        raise FullPipelineCPUActivationError(
            "native initialization sealed mapping identity changed"
        )


def require_exact_closure(
    observed: Mapping[str, object],
    expected: Mapping[str, object],
    *,
    name: str,
) -> None:
    if type(observed) is not dict or type(expected) is not dict:
        raise FullPipelineCPUActivationError(f"{name} must be exact objects")
    if canonical_json_bytes(observed) != canonical_json_bytes(expected):
        raise FullPipelineCPUActivationError(
            f"{name} changed: observed rows receipt "
            f"{observed.get('rows_sha256')!r}, expected "
            f"{expected.get('rows_sha256')!r}"
        )


@dataclass(frozen=True, slots=True)
class ActivationPreflightEvidenceV1:
    activation_sha256: str
    profile_sha256: str
    preinit_executable_closure_manifest_sha256: str
    stdlib_import_closure_manifest_sha256: str
    dynamic_library_closure_manifest_sha256: str
    host_preflight: Mapping[str, object]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_id": PREFLIGHT_EVIDENCE_SCHEMA_ID,
            "activation_id": ACTIVATION_ID,
            "activation_sha256": self.activation_sha256,
            "profile_sha256": self.profile_sha256,
            "preinit_executable_closure_manifest_sha256": (
                self.preinit_executable_closure_manifest_sha256
            ),
            "stdlib_import_closure_manifest_sha256": (
                self.stdlib_import_closure_manifest_sha256
            ),
            "dynamic_library_closure_manifest_sha256": (
                self.dynamic_library_closure_manifest_sha256
            ),
            "host_preflight": dict(self.host_preflight),
            "ready": not self.blockers,
            "blockers": list(self.blockers),
            "imports_performed": True,
            "native_extension_initialized": True,
            "performance_measurement_performed": False,
            "qualification_attempt_created": False,
            "qualification_consumed": False,
            "reservation_created": False,
            "molecular_execution_performed": False,
            "public_benchmark_performed": False,
            "hip_device_execution_performed": False,
            "product_action_performed": False,
            "all_authority_false": True,
        }


__all__ = [
    "ACTIVATION_ID",
    "ACTIVATION_SCHEMA_ID",
    "ActivationPreflightEvidenceV1",
    "DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID",
    "FullPipelineCPUActivationError",
    "PREFLIGHT_EVIDENCE_SCHEMA_ID",
    "PYTHON_STDLIB_ROOT",
    "STDLIB_CLOSURE_SCHEMA_ID",
    "canonical_json_bytes",
    "derive_dynamic_library_closure",
    "derive_stdlib_import_closure",
    "manifest_rows_sha256",
    "require_exact_closure",
    "require_exact_native_initialization_delta",
    "sha256_bytes",
]
