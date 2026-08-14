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
    "betelgeuze.engine_v2_loaded_dynamic_library_closure/1.0.0"
)
PREFLIGHT_EVIDENCE_SCHEMA_ID: Final = (
    "betelgeuze.engine_v2_full_pipeline_cpu_activation_preflight/1.0.0"
)

PYTHON_STDLIB_ROOT: Final = Path("/usr/lib/python3.10")
MAX_CLOSURE_FILE_BYTES: Final = 32 * 1024 * 1024
MAX_CLOSURE_TOTAL_BYTES: Final = 128 * 1024 * 1024
MAX_STDLIB_MODULE_ROWS: Final = 512
MAX_DYNAMIC_LIBRARY_ROWS: Final = 128


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
            getattr(before, field) != getattr(after, field)
            for field in identity_fields
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


def derive_stdlib_import_closure(
    modules: Mapping[str, ModuleType] | None = None,
) -> dict[str, object]:
    """Hash the exact built-in, frozen, and file-backed stdlib module set."""

    source = sys.modules if modules is None else modules
    rows: list[dict[str, object]] = []
    total_bytes = 0
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
        rows.append(
            {
                "module": name,
                "origin": "stdlib_file",
                "path": relative,
                "sha256": sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
        total_bytes += len(raw)
    if not rows or len(rows) > MAX_STDLIB_MODULE_ROWS:
        raise FullPipelineCPUActivationError(
            "standard-library import closure row count is invalid"
        )
    if total_bytes > MAX_CLOSURE_TOTAL_BYTES:
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
        "rows_sha256": manifest_rows_sha256(rows),
        "rows": rows,
    }


def _mapped_library_identity(path: Path, *, site_packages: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return "qualified_site_packages/" + resolved.relative_to(
            site_packages.resolve(strict=True)
        ).as_posix()
    except ValueError:
        pass
    try:
        return "stdlib/" + resolved.relative_to(
            PYTHON_STDLIB_ROOT.resolve(strict=True)
        ).as_posix()
    except ValueError:
        return "system:" + str(resolved)


def derive_dynamic_library_closure(
    *,
    site_packages: Path,
    process_maps_path: Path | None = None,
) -> dict[str, object]:
    """Hash every mapped shared object in the isolated activation process."""

    maps_path = process_maps_path or Path(f"/proc/{os.getpid()}/maps")
    try:
        lines = maps_path.read_text(encoding="ascii", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise FullPipelineCPUActivationError(
            "dynamic-library process map is unavailable"
        ) from exc
    observed: dict[Path, str] = {}
    for line in lines:
        fields = line.split()
        if len(fields) < 6:
            continue
        raw_path = fields[-1]
        if not raw_path.startswith("/") or ".so" not in Path(raw_path).name:
            continue
        try:
            path = Path(raw_path).resolve(strict=True)
            identity = _mapped_library_identity(path, site_packages=site_packages)
        except OSError as exc:
            raise FullPipelineCPUActivationError(
                "mapped dynamic library is unavailable"
            ) from exc
        previous = observed.setdefault(path, identity)
        if previous != identity:
            raise FullPipelineCPUActivationError(
                "mapped dynamic library identity is ambiguous"
            )
    rows: list[dict[str, object]] = []
    total_bytes = 0
    for path, identity in sorted(observed.items(), key=lambda item: item[1]):
        raw = _read_stable_regular_file(
            path,
            name="mapped dynamic library",
            allowed_owner_uids=(0, os.geteuid()),
        )
        rows.append(
            {
                "path": identity,
                "sha256": sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
        total_bytes += len(raw)
    if not rows or len(rows) > MAX_DYNAMIC_LIBRARY_ROWS:
        raise FullPipelineCPUActivationError(
            "dynamic-library closure row count is invalid"
        )
    if total_bytes > MAX_CLOSURE_TOTAL_BYTES:
        raise FullPipelineCPUActivationError(
            "dynamic-library closure exceeds its byte envelope"
        )
    return {
        "schema_id": DYNAMIC_LIBRARY_CLOSURE_SCHEMA_ID,
        "library_count": len(rows),
        "total_bytes": total_bytes,
        "rows_sha256": manifest_rows_sha256(rows),
        "rows": rows,
    }


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
    "sha256_bytes",
]
