"""Bounded, fail-closed wheel and SPDX artifact validation for Stage 0.

The public validator is read-only and has no dependency on an installed wheel.
It authenticates the archive structure, every RECORD-declared payload, the
distribution identity, and an exact SPDX 2.3 wheel binding.  Native extension
bytes are compared with the separately measured installed extension digest;
the legacy HIP build is not inspected or promoted here.
"""

from __future__ import annotations

import base64
import csv
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from enum import Enum
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Mapping
import unicodedata
import zipfile

from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib  # type: ignore[no-redef]


WHEEL_ARTIFACT_VALIDATION_SCHEMA_ID = "betelgeuze.engine_v2_wheel_artifact_validation/2.0.0"
SOURCE_PROVENANCE_SCHEMA_ID = "betelgeuze.engine_v2_wheel_source_provenance/1.0.0"
NATIVE_BUILD_PROVENANCE_SCHEMA_ID = "betelgeuze.engine_v2_native_build_provenance/1.0.0"
BASE_BUILD_PROVENANCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_base_wheel_build_provenance/1.0.0"
)
LICENSE_DETERMINATION_SCHEMA_ID = "betelgeuze.engine_v2_license_determination/1.0.0"

MAX_WHEEL_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_WHEEL_MEMBER_COUNT = 4096
MAX_WHEEL_MEMBER_BYTES = 128 * 1024 * 1024
MAX_WHEEL_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
MAX_WHEEL_CONTROL_FILE_BYTES = 1024 * 1024
MAX_WHEEL_MEMBER_NAME_BYTES = 1024
MAX_WHEEL_MEMBER_COMPONENT_BYTES = 255
MAX_SBOM_BYTES = 8 * 1024 * 1024
MAX_PROVENANCE_BYTES = 4 * 1024 * 1024

_READ_CHUNK_BYTES = 1024 * 1024
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SPDX_ID_RE = re.compile(r"^SPDXRef-[A-Za-z0-9.-]+$")
_DISTRIBUTION_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_VERSION_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.!+_-]*[A-Za-z0-9])?$")
_TAG_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*$")
_BUILD_TAG_RE = re.compile(r"^[0-9][A-Za-z0-9_]*$")
_REQUIREMENT_NAME_RE = re.compile(
    r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r"(?=\s*(?:\[|\(|[<>=!~;@]|$))"
)
_SPDX_LICENSE_EXPRESSION_RE = re.compile(r"^[A-Za-z0-9.+(): -]+$")
_RFC3339_UTC_RE = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_NATIVE_EXTENSION_SUFFIXES = (".so", ".pyd")
_ALLOWED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})

_SOURCE_ANNOTATION_PREFIX = "BETELGEUZE-SOURCE-PROVENANCE-SHA256:"
_LICENSE_ANNOTATION_PREFIX = "BETELGEUZE-LICENSE-DETERMINATION-SHA256:"
_NATIVE_ANNOTATION_PREFIX = "BETELGEUZE-NATIVE-BUILD-PROVENANCE-SHA256:"


class WheelArtifactKind(str, Enum):
    BASE = "base"
    NATIVE = "native"


class _ArtifactInvalid(RuntimeError):
    def __init__(self, blocker: str) -> None:
        super().__init__(blocker)
        self.blocker = blocker


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_or_empty(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if _SHA256_RE.fullmatch(normalized) else ""


def _normalized_distribution_component(value: str) -> str:
    return re.sub(r"[-_.]+", "_", value).lower()


def _normalized_version_component(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]", "_", value)


def _safe_member_name(name: object, *, directory: bool) -> str:
    if not isinstance(name, str) or not name or "\x00" in name or "\\" in name:
        raise _ArtifactInvalid("wheel_member_path_unsafe")
    try:
        encoded = name.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _ArtifactInvalid("wheel_member_path_unsafe") from exc
    if len(encoded) > MAX_WHEEL_MEMBER_NAME_BYTES or unicodedata.normalize("NFC", name) != name:
        raise _ArtifactInvalid("wheel_member_path_unsafe")
    if directory:
        if not name.endswith("/"):
            raise _ArtifactInvalid("wheel_member_path_unsafe")
        canonical = name[:-1]
    else:
        if name.endswith("/"):
            raise _ArtifactInvalid("wheel_member_path_unsafe")
        canonical = name
    path = PurePosixPath(canonical)
    parts = path.parts
    if (
        not canonical
        or canonical.startswith("/")
        or path.is_absolute()
        or path.as_posix() != canonical
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
        or ":" in parts[0]
        or any(len(part.encode("utf-8")) > MAX_WHEEL_MEMBER_COMPONENT_BYTES for part in parts)
    ):
        raise _ArtifactInvalid("wheel_member_path_unsafe")
    return name


def _regular_path(path: Path, *, missing: str, unsafe: str, too_large: str, limit: int) -> int:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise _ArtifactInvalid(missing) from exc
    if not stat.S_ISREG(file_stat.st_mode) or path.is_symlink():
        raise _ArtifactInvalid(unsafe)
    if not 0 < file_stat.st_size <= limit:
        raise _ArtifactInvalid(too_large)
    return file_stat.st_size


def _hash_path(
    path: Path,
    *,
    limit: int,
    too_large: str,
    capture_bytes: bool = False,
) -> tuple[str, bytes | None]:
    digest = hashlib.sha256()
    total = 0
    capture = bytearray() if capture_bytes else None
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_READ_CHUNK_BYTES), b""):
                total += len(chunk)
                if total > limit:
                    raise _ArtifactInvalid(too_large)
                digest.update(chunk)
                if capture is not None:
                    capture.extend(chunk)
    except _ArtifactInvalid:
        raise
    except OSError as exc:
        raise _ArtifactInvalid("artifact_read_failed") from exc
    return digest.hexdigest(), bytes(capture) if capture is not None else None


def _read_json_path(path: Path, *, blocker: str) -> tuple[Mapping[str, object], str]:
    _regular_path(
        path,
        missing=f"{blocker}_missing",
        unsafe=f"{blocker}_not_regular",
        too_large=f"{blocker}_size_out_of_bounds",
        limit=MAX_PROVENANCE_BYTES,
    )
    digest, raw = _hash_path(
        path,
        limit=MAX_PROVENANCE_BYTES,
        too_large=f"{blocker}_size_out_of_bounds",
        capture_bytes=True,
    )
    if raw is None:
        raise _ArtifactInvalid(f"{blocker}_read_failed")
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except _ArtifactInvalid:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise _ArtifactInvalid(f"{blocker}_invalid") from exc
    if not isinstance(payload, Mapping):
        raise _ArtifactInvalid(f"{blocker}_invalid")
    return payload, digest


def _canonical_dependency_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _parse_metadata_requirements(message: object) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for raw in message.get_all("Requires-Dist", []):  # type: ignore[attr-defined]
        requirement = str(raw or "").strip()
        if not requirement or len(requirement) > 4096 or "\r" in requirement or "\n" in requirement:
            raise _ArtifactInvalid("wheel_metadata_requires_dist_invalid")
        match = _REQUIREMENT_NAME_RE.match(requirement)
        if match is None:
            raise _ArtifactInvalid("wheel_metadata_requires_dist_invalid")
        rows.append((_canonical_dependency_name(match.group(1)), requirement))
    if len(rows) != len(set(rows)):
        raise _ArtifactInvalid("wheel_metadata_requires_dist_duplicate")
    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class _CargoPackage:
    name: str
    version: str
    source: str
    checksum: str
    dependencies: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"cargo:{self.name}@{self.version}"

    @property
    def spdx_id(self) -> str:
        digest = _sha256_bytes(self.key.encode("utf-8"))[:24]
        return f"SPDXRef-Cargo-{digest}"


def _parse_cargo_lock(path: Path) -> tuple[tuple[_CargoPackage, ...], str]:
    _regular_path(
        path,
        missing="cargo_lock_missing",
        unsafe="cargo_lock_not_regular",
        too_large="cargo_lock_size_out_of_bounds",
        limit=MAX_PROVENANCE_BYTES,
    )
    digest, raw = _hash_path(
        path,
        limit=MAX_PROVENANCE_BYTES,
        too_large="cargo_lock_size_out_of_bounds",
        capture_bytes=True,
    )
    if raw is None:
        raise _ArtifactInvalid("cargo_lock_read_failed")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise _ArtifactInvalid("cargo_lock_invalid") from exc
    if not re.search(r"^version\s*=\s*4\s*$", text, flags=re.MULTILINE):
        raise _ArtifactInvalid("cargo_lock_version_invalid")
    rows: list[_CargoPackage] = []
    for block in text.split("[[package]]")[1:]:
        name_match = re.search(r'^name\s*=\s*"([^"]+)"\s*$', block, re.MULTILINE)
        version_match = re.search(r'^version\s*=\s*"([^"]+)"\s*$', block, re.MULTILINE)
        source_match = re.search(r'^source\s*=\s*"([^"]+)"\s*$', block, re.MULTILINE)
        checksum_match = re.search(r'^checksum\s*=\s*"([0-9a-f]{64})"\s*$', block, re.MULTILINE)
        if name_match is None or version_match is None:
            raise _ArtifactInvalid("cargo_lock_package_invalid")
        dependency_match = re.search(
            r"^dependencies\s*=\s*\[(.*?)^\]\s*$",
            block,
            flags=re.MULTILINE | re.DOTALL,
        )
        dependencies: tuple[str, ...] = ()
        if dependency_match is not None:
            encoded = dependency_match.group(1)
            dependencies = tuple(re.findall(r'^\s*"([^"]+)"\s*,?\s*$', encoded, re.MULTILINE))
            residue = re.sub(r'^\s*"[^"]+"\s*,?\s*$', "", encoded, flags=re.MULTILINE)
            if residue.strip() or len(dependencies) != len(set(dependencies)):
                raise _ArtifactInvalid("cargo_lock_dependencies_invalid")
        source = "" if source_match is None else source_match.group(1)
        checksum = "" if checksum_match is None else checksum_match.group(1)
        if source.startswith("registry+") and not checksum:
            raise _ArtifactInvalid("cargo_lock_registry_checksum_missing")
        rows.append(
            _CargoPackage(
                name=name_match.group(1),
                version=version_match.group(1),
                source=source,
                checksum=checksum,
                dependencies=dependencies,
            )
        )
    if not rows or len({row.key for row in rows}) != len(rows):
        raise _ArtifactInvalid("cargo_lock_package_invalid")
    return tuple(sorted(rows, key=lambda row: row.key)), digest


def _resolve_cargo_dependency(
    dependency: str,
    *,
    packages: tuple[_CargoPackage, ...],
) -> _CargoPackage:
    by_name = [row for row in packages if row.name == dependency]
    if len(by_name) == 1:
        return by_name[0]
    match = re.fullmatch(r"([^ ]+) ([^ ]+)(?: \((.+)\))?", dependency)
    if match is not None:
        by_identity = [
            row
            for row in packages
            if row.name == match.group(1)
            and row.version == match.group(2)
            and (match.group(3) is None or row.source == match.group(3))
        ]
        if len(by_identity) == 1:
            return by_identity[0]
    raise _ArtifactInvalid("cargo_lock_dependency_unresolved")


@dataclass(frozen=True, slots=True)
class _LicenseDetermination:
    package_key: str
    license_concluded: str
    license_declared: str
    copyright_text: str
    evidence: str


@dataclass(frozen=True, slots=True)
class _DependencyPackage:
    spdx_id: str
    license_key: str
    name: str
    version: str
    checksum: str
    purl: str
    comment: str
    dependency_ids: tuple[str, ...]


def _pypi_dependency_packages(
    requirements: tuple[tuple[str, str], ...],
) -> tuple[_DependencyPackage, ...]:
    rows: list[_DependencyPackage] = []
    for name, requirement in requirements:
        identity = f"pypi:{name}|requires-dist:{_sha256_bytes(requirement.encode('utf-8'))}"
        rows.append(
            _DependencyPackage(
                spdx_id=f"SPDXRef-PyPI-{_sha256_bytes(identity.encode('utf-8'))[:24]}",
                license_key=f"pypi:{name}",
                name=name,
                version="",
                checksum="",
                purl=f"pkg:pypi/{name}",
                comment=f"Declared Requires-Dist: {requirement}",
                dependency_ids=(),
            )
        )
    return tuple(rows)


def _cargo_dependency_packages(
    packages: tuple[_CargoPackage, ...],
    *,
    root_distribution: str,
    root_version: str = "",
) -> tuple[tuple[_DependencyPackage, ...], tuple[str, ...]]:
    normalized_root = _canonical_dependency_name(root_distribution)
    roots = [row for row in packages if _canonical_dependency_name(row.name) == normalized_root]
    if len(roots) != 1:
        raise _ArtifactInvalid("cargo_lock_root_package_invalid")
    root = roots[0]
    if root_version and re.sub(r"[^a-z0-9]", "", root.version.lower()) != re.sub(
        r"[^a-z0-9]", "", root_version.lower()
    ):
        raise _ArtifactInvalid("cargo_lock_root_version_mismatch")
    rows: list[_DependencyPackage] = []
    for row in packages:
        if row is root:
            continue
        dependency_ids = tuple(
            sorted(
                _resolve_cargo_dependency(value, packages=packages).spdx_id
                for value in row.dependencies
                if _resolve_cargo_dependency(value, packages=packages) is not root
            )
        )
        rows.append(
            _DependencyPackage(
                spdx_id=row.spdx_id,
                license_key=row.key,
                name=row.name,
                version=row.version,
                checksum=row.checksum,
                purl=f"pkg:cargo/{row.name}@{row.version}",
                comment=(f"Cargo.lock source: {row.source}" if row.source else ""),
                dependency_ids=dependency_ids,
            )
        )
    root_dependency_ids = tuple(
        sorted(_resolve_cargo_dependency(value, packages=packages).spdx_id for value in root.dependencies)
    )
    return tuple(sorted(rows, key=lambda value: value.spdx_id)), root_dependency_ids


def _expected_license_keys(
    *,
    distribution: str,
    version: str,
    dependencies: tuple[_DependencyPackage, ...],
) -> set[str]:
    return {
        f"pypi:{_canonical_dependency_name(distribution)}@{version}",
        *(row.license_key for row in dependencies),
    }


def _wheel_file_spdx_id(name: str) -> str:
    return f"SPDXRef-WheelFile-{_sha256_bytes(name.encode('utf-8'))[:24]}"


def _source_file_spdx_id(name: str) -> str:
    return f"SPDXRef-SourceFile-{_sha256_bytes(name.encode('utf-8'))[:24]}"


def _valid_license_expression(value: object) -> str:
    normalized = str(value or "").strip()
    if (
        not normalized
        or normalized in {"NOASSERTION", "NONE"}
        or len(normalized) > 256
        or _SPDX_LICENSE_EXPRESSION_RE.fullmatch(normalized) is None
    ):
        raise _ArtifactInvalid("license_determination_expression_invalid")
    return normalized


def _license_scope_sha256(package_keys: set[str]) -> str:
    return _sha256_bytes(_canonical_bytes(sorted(package_keys)))


def _load_license_determinations(
    path: Path,
    *,
    expected_package_keys: set[str],
) -> tuple[dict[str, _LicenseDetermination], tuple[dict[str, object], ...], str]:
    payload, digest = _read_json_path(path, blocker="license_determination")
    if (
        set(payload)
        != {
            "schema_id",
            "review_id",
            "reviewer_identity",
            "reviewed_at",
            "review_status",
            "review_evidence_sha256",
            "scope_sha256",
            "determinations",
            "extracted_licenses",
        }
        or payload.get("schema_id") != LICENSE_DETERMINATION_SCHEMA_ID
    ):
        raise _ArtifactInvalid("license_determination_invalid")
    if (
        not str(payload.get("review_id") or "").strip()
        or not str(payload.get("reviewer_identity") or "").strip()
        or payload.get("review_status") != "approved"
        or _RFC3339_UTC_RE.fullmatch(str(payload.get("reviewed_at") or "")) is None
        or _digest_or_empty(payload.get("review_evidence_sha256")) == ""
        or payload.get("scope_sha256") != _license_scope_sha256(expected_package_keys)
    ):
        raise _ArtifactInvalid("license_determination_review_incomplete")
    rows = payload.get("determinations")
    if not isinstance(rows, list):
        raise _ArtifactInvalid("license_determination_invalid")
    determinations: dict[str, _LicenseDetermination] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "package_key",
            "license_concluded",
            "license_declared",
            "copyright_text",
            "evidence",
        }:
            raise _ArtifactInvalid("license_determination_invalid")
        package_key = str(row.get("package_key") or "").strip()
        copyright_text = str(row.get("copyright_text") or "").strip()
        evidence = str(row.get("evidence") or "").strip()
        if (
            not package_key
            or package_key in determinations
            or not copyright_text
            or copyright_text == "NOASSERTION"
            or not evidence
        ):
            raise _ArtifactInvalid("license_determination_invalid")
        determinations[package_key] = _LicenseDetermination(
            package_key=package_key,
            license_concluded=_valid_license_expression(row.get("license_concluded")),
            license_declared=_valid_license_expression(row.get("license_declared")),
            copyright_text=copyright_text,
            evidence=evidence,
        )
    if set(determinations) != expected_package_keys:
        raise _ArtifactInvalid("license_determination_package_scope_mismatch")
    extracted_rows = payload.get("extracted_licenses")
    if not isinstance(extracted_rows, list):
        raise _ArtifactInvalid("license_determination_extracted_license_invalid")
    extracted: list[dict[str, object]] = []
    extracted_ids: set[str] = set()
    for row in extracted_rows:
        if not isinstance(row, Mapping) or set(row) != {
            "license_id",
            "name",
            "extracted_text",
            "see_alsos",
        }:
            raise _ArtifactInvalid("license_determination_extracted_license_invalid")
        license_id = str(row.get("license_id") or "").strip()
        name = str(row.get("name") or "").strip()
        extracted_text = str(row.get("extracted_text") or "").strip()
        see_alsos = row.get("see_alsos")
        if (
            not license_id.startswith("LicenseRef-")
            or _SPDX_ID_RE.fullmatch(f"SPDXRef-{license_id}") is None
            or license_id in extracted_ids
            or not name
            or not extracted_text
            or extracted_text == "NOASSERTION"
            or not isinstance(see_alsos, list)
            or any(not isinstance(value, str) or not value for value in see_alsos)
            or len(see_alsos) != len(set(see_alsos))
        ):
            raise _ArtifactInvalid("license_determination_extracted_license_invalid")
        extracted_ids.add(license_id)
        spdx_row: dict[str, object] = {
            "licenseId": license_id,
            "name": name,
            "extractedText": extracted_text,
        }
        if see_alsos:
            spdx_row["seeAlsos"] = see_alsos
        extracted.append(spdx_row)
    used_license_refs = {
        token
        for determination in determinations.values()
        for expression in (
            determination.license_concluded,
            determination.license_declared,
        )
        for token in re.findall(r"LicenseRef-[A-Za-z0-9.-]+", expression)
    }
    if used_license_refs != extracted_ids:
        raise _ArtifactInvalid("license_determination_extracted_license_scope_mismatch")
    return (
        determinations,
        tuple(sorted(extracted, key=lambda value: str(value["licenseId"]))),
        digest,
    )


def _source_file_inventory(
    source_root: Path,
    *,
    kind: WheelArtifactKind,
    payload_members: Mapping[str, tuple[str, int]],
) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    try:
        root = source_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise _ArtifactInvalid("wheel_source_root_missing") from exc
    if not root.is_dir() or root.is_symlink():
        raise _ArtifactInvalid("wheel_source_root_not_directory")
    inventory: dict[str, str] = {}
    mappings: list[tuple[str, str]] = []
    if kind is WheelArtifactKind.BASE:
        for member, (wheel_digest, _) in sorted(payload_members.items()):
            source_path = root.joinpath(*PurePosixPath(member).parts)
            try:
                resolved = source_path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise _ArtifactInvalid("wheel_source_member_missing") from exc
            try:
                inside = resolved.is_relative_to(root)
            except AttributeError:  # pragma: no cover - Python 3.8/3.9 compatibility
                inside = root == resolved or root in resolved.parents
            if not inside or source_path.is_symlink() or not resolved.is_file():
                raise _ArtifactInvalid("wheel_source_member_unsafe")
            source_digest, _ = _hash_path(
                resolved,
                limit=MAX_WHEEL_MEMBER_BYTES,
                too_large="wheel_source_member_size_out_of_bounds",
            )
            if source_digest != wheel_digest:
                raise _ArtifactInvalid("wheel_source_member_sha256_mismatch")
            inventory[member] = source_digest
            mappings.append((member, member))
    else:
        required = {
            "Cargo.lock",
            "Cargo.toml",
            "build.rs",
            "pyproject.toml",
        }
        if (root / "target").exists():
            raise _ArtifactInvalid("native_source_build_output_present")
        all_entries = tuple(root.rglob("*"))
        if len(all_entries) > MAX_WHEEL_MEMBER_COUNT:
            raise _ArtifactInvalid("native_source_inventory_size_out_of_bounds")
        if any(path.is_symlink() for path in all_entries):
            raise _ArtifactInvalid("native_source_member_unsafe")
        candidates = {path.relative_to(root).as_posix() for path in all_entries if path.is_file()}
        if (
            not required.issubset(candidates)
            or not any(value.startswith("src/") for value in candidates)
            or any({".git", "__pycache__"}.intersection(PurePosixPath(value).parts) for value in candidates)
        ):
            raise _ArtifactInvalid("native_source_inventory_incomplete")
        for relative in sorted(candidates):
            source_path = root.joinpath(*PurePosixPath(relative).parts)
            try:
                resolved = source_path.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise _ArtifactInvalid("native_source_inventory_incomplete") from exc
            try:
                inside = resolved.is_relative_to(root)
            except AttributeError:  # pragma: no cover
                inside = root == resolved or root in resolved.parents
            if not inside or source_path.is_symlink() or not resolved.is_file():
                raise _ArtifactInvalid("native_source_member_unsafe")
            inventory[relative], _ = _hash_path(
                resolved,
                limit=MAX_WHEEL_MEMBER_BYTES,
                too_large="native_source_member_size_out_of_bounds",
            )
    return inventory, tuple(mappings)


def _source_provenance(
    *,
    kind: WheelArtifactKind,
    payload_members: Mapping[str, tuple[str, int]],
    source_inventory: Mapping[str, str],
    mappings: tuple[tuple[str, str], ...],
    source_receipt_sha256: str,
    cargo_lock_sha256: str = "",
    native_build_provenance_sha256: str = "",
) -> dict[str, object]:
    return {
        "schema_id": SOURCE_PROVENANCE_SCHEMA_ID,
        "artifact_kind": kind.value,
        "source_receipt_sha256": source_receipt_sha256,
        "wheel_payload_sha256": {name: value[0] for name, value in sorted(payload_members.items())},
        "source_files_sha256": dict(sorted(source_inventory.items())),
        "source_inventory_sha256": _sha256_bytes(_canonical_bytes(dict(sorted(source_inventory.items())))),
        "generated_from": [
            {"wheel_member": wheel_member, "source_path": source_path} for wheel_member, source_path in mappings
        ],
        "cargo_lock_sha256": cargo_lock_sha256,
        "native_build_provenance_sha256": native_build_provenance_sha256,
    }


def _load_native_build_provenance(
    path: Path,
    *,
    wheel_sha256: str,
    extension_member: str,
    extension_sha256: str,
    cargo_lock_sha256: str,
    source_inventory: Mapping[str, str],
    source_receipt_sha256: str,
) -> str:
    payload, digest = _read_json_path(path, blocker="native_build_provenance")
    expected_keys = {
        "schema_id",
        "source_receipt_sha256",
        "source_inventory_sha256",
        "cargo_lock_sha256",
        "wheel_sha256",
        "extension_member",
        "extension_sha256",
        "builder_id",
        "builder_version",
        "build_environment_sha256",
        "build_invocation_sha256",
        "reproducible_build_match",
    }
    if set(payload) != expected_keys or payload.get("schema_id") != NATIVE_BUILD_PROVENANCE_SCHEMA_ID:
        raise _ArtifactInvalid("native_build_provenance_invalid")
    if (
        payload.get("source_receipt_sha256") != source_receipt_sha256
        or payload.get("source_inventory_sha256")
        != _sha256_bytes(_canonical_bytes(dict(sorted(source_inventory.items()))))
        or payload.get("cargo_lock_sha256") != cargo_lock_sha256
        or payload.get("wheel_sha256") != wheel_sha256
        or payload.get("extension_member") != extension_member
        or payload.get("extension_sha256") != extension_sha256
        or not str(payload.get("builder_id") or "").strip()
        or not str(payload.get("builder_version") or "").strip()
        or _digest_or_empty(payload.get("build_environment_sha256")) == ""
        or _digest_or_empty(payload.get("build_invocation_sha256")) == ""
        or payload.get("reproducible_build_match") is not True
    ):
        raise _ArtifactInvalid("native_build_provenance_binding_mismatch")
    return digest


def _control_header_ledger(message: object, *, blocker: str) -> dict[str, tuple[str, ...]]:
    rows: dict[str, list[str]] = {}
    for raw_name, raw_value in message.raw_items():  # type: ignore[attr-defined]
        name = str(raw_name).strip().lower()
        value = str(raw_value).strip()
        if not name or not value or "\r" in value or "\n" in value:
            raise _ArtifactInvalid(blocker)
        rows.setdefault(name, []).append(value)
    return {name: tuple(values) for name, values in rows.items()}


def _canonical_requirement(value: object, *, blocker: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _ArtifactInvalid(blocker)
    try:
        return str(Requirement(value))
    except InvalidRequirement as exc:
        raise _ArtifactInvalid(blocker) from exc


def _optional_requirement(value: object, *, extra: str) -> str:
    canonical = _canonical_requirement(
        value,
        blocker="base_build_pyproject_optional_dependency_invalid",
    )
    if ";" in canonical:
        requirement, marker = canonical.split(";", 1)
        return f'{requirement.strip()}; ({marker.strip()}) and extra == "{extra}"'
    return f'{canonical}; extra == "{extra}"'


def _parse_entry_points(raw: bytes) -> dict[str, str]:
    if (
        not raw
        or len(raw) > MAX_WHEEL_CONTROL_FILE_BYTES
        or b"\x00" in raw
        or b"\r" in raw
        or not raw.endswith(b"\n")
    ):
        raise _ArtifactInvalid("base_wheel_entry_points_invalid")
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeDecodeError as exc:
        raise _ArtifactInvalid("base_wheel_entry_points_invalid") from exc
    if not lines or lines[0] != "[console_scripts]" or any(not line for line in lines):
        raise _ArtifactInvalid("base_wheel_entry_points_invalid")
    scripts: dict[str, str] = {}
    for line in lines[1:]:
        if line.startswith("[") or line.count(" = ") != 1:
            raise _ArtifactInvalid("base_wheel_entry_points_invalid")
        name, target = line.split(" = ", 1)
        if (
            not name
            or name in scripts
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None
            or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*",
                target,
            )
            is None
        ):
            raise _ArtifactInvalid("base_wheel_entry_points_invalid")
        scripts[name] = target
    if not scripts:
        raise _ArtifactInvalid("base_wheel_entry_points_invalid")
    return dict(sorted(scripts.items()))


def _base_build_provenance_sha256(
    *,
    source_root: Path,
    metadata_message: object,
    entry_points_raw: bytes,
    wheel_message: object,
    filename: _WheelFilename,
    metadata_sha256: str,
    entry_points_sha256: str,
    wheel_control_sha256: str,
) -> str:
    pyproject_path = source_root / "packaging/engine-v2/pyproject.toml"
    _regular_path(
        pyproject_path,
        missing="base_build_pyproject_missing",
        unsafe="base_build_pyproject_not_regular",
        too_large="base_build_pyproject_size_out_of_bounds",
        limit=MAX_PROVENANCE_BYTES,
    )
    pyproject_sha256, pyproject_raw = _hash_path(
        pyproject_path,
        limit=MAX_PROVENANCE_BYTES,
        too_large="base_build_pyproject_size_out_of_bounds",
        capture_bytes=True,
    )
    if pyproject_raw is None:
        raise _ArtifactInvalid("base_build_pyproject_invalid")
    try:
        pyproject = tomllib.loads(pyproject_raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError, TypeError, ValueError) as exc:
        raise _ArtifactInvalid("base_build_pyproject_invalid") from exc
    if not isinstance(pyproject, Mapping):
        raise _ArtifactInvalid("base_build_pyproject_invalid")
    build_system = pyproject.get("build-system")
    project = pyproject.get("project")
    if not isinstance(build_system, Mapping) or not isinstance(project, Mapping):
        raise _ArtifactInvalid("base_build_pyproject_invalid")
    build_requires = build_system.get("requires")
    if (
        build_system.get("build-backend") != "setuptools.build_meta"
        or not isinstance(build_requires, list)
        or any(not isinstance(value, str) for value in build_requires)
    ):
        raise _ArtifactInvalid("base_build_pyproject_build_system_invalid")
    parsed_build_requires = tuple(
        Requirement(value) for value in build_requires
    )
    setuptools_requirements = [
        requirement
        for requirement in parsed_build_requires
        if _canonical_dependency_name(requirement.name) == "setuptools"
    ]
    wheel_requirements = [
        requirement
        for requirement in parsed_build_requires
        if _canonical_dependency_name(requirement.name) == "wheel"
    ]
    if len(setuptools_requirements) != 1 or len(wheel_requirements) != 1:
        raise _ArtifactInvalid("base_build_pyproject_build_system_invalid")
    setuptools_specifiers = tuple(setuptools_requirements[0].specifier)
    wheel_specifiers = tuple(wheel_requirements[0].specifier)
    if (
        len(setuptools_specifiers) != 1
        or setuptools_specifiers[0].operator != "=="
        or len(wheel_specifiers) != 1
        or wheel_specifiers[0].operator != "=="
    ):
        raise _ArtifactInvalid("base_build_pyproject_build_system_invalid")

    dependencies = project.get("dependencies")
    classifiers = project.get("classifiers")
    scripts = project.get("scripts")
    optional_dependencies = project.get("optional-dependencies", {})
    if (
        not isinstance(dependencies, list)
        or any(not isinstance(value, str) for value in dependencies)
        or not isinstance(classifiers, list)
        or any(not isinstance(value, str) or not value for value in classifiers)
        or not isinstance(scripts, Mapping)
        or not isinstance(optional_dependencies, Mapping)
    ):
        raise _ArtifactInvalid("base_build_pyproject_project_invalid")
    expected_scripts = {
        str(name): str(target)
        for name, target in scripts.items()
        if isinstance(name, str) and isinstance(target, str)
    }
    if len(expected_scripts) != len(scripts) or _parse_entry_points(
        entry_points_raw
    ) != dict(sorted(expected_scripts.items())):
        raise _ArtifactInvalid("base_wheel_entry_points_build_provenance_mismatch")

    try:
        requires_python = str(SpecifierSet(str(project.get("requires-python", ""))))
    except InvalidSpecifier as exc:
        raise _ArtifactInvalid("base_build_pyproject_project_invalid") from exc
    expected_requirements = [
        _canonical_requirement(
            value,
            blocker="base_build_pyproject_dependency_invalid",
        )
        for value in dependencies
    ]
    expected_extras: list[str] = []
    for extra, raw_requirements in optional_dependencies.items():
        if (
            not isinstance(extra, str)
            or not extra
            or not isinstance(raw_requirements, list)
        ):
            raise _ArtifactInvalid("base_build_pyproject_optional_dependency_invalid")
        expected_extras.append(extra)
        expected_requirements.extend(
            _optional_requirement(value, extra=extra) for value in raw_requirements
        )
    expected_metadata_headers = {
        "metadata-version": ("2.2",),
        "name": (str(project.get("name", "")),),
        "version": (str(project.get("version", "")),),
        "summary": (str(project.get("description", "")),),
        "classifier": tuple(classifiers),
        "requires-python": (requires_python,),
        "requires-dist": tuple(expected_requirements),
        "provides-extra": tuple(expected_extras),
    }
    expected_metadata_headers = {
        name: values
        for name, values in expected_metadata_headers.items()
        if values
    }
    if (
        str(metadata_message.get_payload() or "").strip()  # type: ignore[attr-defined]
        or _control_header_ledger(
            metadata_message,
            blocker="base_wheel_metadata_invalid",
        )
        != expected_metadata_headers
    ):
        raise _ArtifactInvalid("base_wheel_metadata_build_provenance_mismatch")

    expected_wheel_headers = {
        "wheel-version": ("1.0",),
        "generator": (
            f"setuptools ({setuptools_specifiers[0].version})",
        ),
        "root-is-purelib": ("true",),
        "tag": tuple(sorted(filename.expanded_tags)),
    }
    if filename.build_tag:
        expected_wheel_headers["build"] = (filename.build_tag,)
    if _control_header_ledger(
        wheel_message,
        blocker="base_wheel_control_metadata_invalid",
    ) != expected_wheel_headers:
        raise _ArtifactInvalid("base_wheel_control_build_provenance_mismatch")

    projection = {
        "schema_id": BASE_BUILD_PROVENANCE_SCHEMA_ID,
        "pyproject_sha256": pyproject_sha256,
        "source_receipt_includes_pyproject": True,
        "build_backend": build_system["build-backend"],
        "build_requirements": [str(value) for value in parsed_build_requires],
        "metadata_sha256": metadata_sha256,
        "entry_points_sha256": entry_points_sha256,
        "wheel_control_sha256": wheel_control_sha256,
        "metadata_headers": expected_metadata_headers,
        "console_scripts": dict(sorted(expected_scripts.items())),
        "wheel_headers": expected_wheel_headers,
    }
    return _sha256_bytes(_canonical_bytes(projection))


@dataclass(frozen=True, slots=True)
class _WheelFilename:
    distribution: str
    version: str
    build_tag: str
    python_tags: tuple[str, ...]
    abi_tags: tuple[str, ...]
    platform_tags: tuple[str, ...]

    @property
    def expanded_tags(self) -> frozenset[str]:
        return frozenset(
            f"{python_tag}-{abi_tag}-{platform_tag}"
            for python_tag in self.python_tags
            for abi_tag in self.abi_tags
            for platform_tag in self.platform_tags
        )


def _parse_wheel_filename(
    filename: str,
    *,
    expected_distribution: str,
    expected_version: str,
) -> _WheelFilename:
    if not filename.endswith(".whl") or "/" in filename or "\\" in filename:
        raise _ArtifactInvalid("wheel_filename_invalid")
    components = filename[:-4].split("-")
    if len(components) == 5:
        distribution, version, python_tag, abi_tag, platform_tag = components
        build_tag = ""
    elif len(components) == 6:
        distribution, version, build_tag, python_tag, abi_tag, platform_tag = components
        if _BUILD_TAG_RE.fullmatch(build_tag) is None:
            raise _ArtifactInvalid("wheel_filename_build_tag_invalid")
    else:
        raise _ArtifactInvalid("wheel_filename_invalid")
    if distribution != _normalized_distribution_component(expected_distribution):
        raise _ArtifactInvalid("wheel_filename_distribution_mismatch")
    if version != _normalized_version_component(expected_version):
        raise _ArtifactInvalid("wheel_filename_version_mismatch")
    if any(_TAG_COMPONENT_RE.fullmatch(value) is None for value in (python_tag, abi_tag, platform_tag)):
        raise _ArtifactInvalid("wheel_filename_tag_invalid")
    return _WheelFilename(
        distribution=distribution,
        version=version,
        build_tag=build_tag,
        python_tags=tuple(python_tag.split(".")),
        abi_tags=tuple(abi_tag.split(".")),
        platform_tags=tuple(platform_tag.split(".")),
    )


def _unique_headers(message: object, name: str, *, blocker: str) -> str:
    values = message.get_all(name, [])  # type: ignore[attr-defined]
    if len(values) != 1:
        raise _ArtifactInvalid(blocker)
    value = str(values[0] or "").strip()
    if not value or "\r" in value or "\n" in value:
        raise _ArtifactInvalid(blocker)
    return value


def _parse_control_message(raw: bytes, *, blocker: str) -> object:
    if not raw or len(raw) > MAX_WHEEL_CONTROL_FILE_BYTES or b"\x00" in raw:
        raise _ArtifactInvalid(blocker)
    try:
        message = BytesParser(policy=policy.compat32).parsebytes(raw)
    except (TypeError, ValueError) as exc:
        raise _ArtifactInvalid(blocker) from exc
    if message.defects:
        raise _ArtifactInvalid(blocker)
    return message


def _decode_record_hash(value: str) -> str:
    if not value.startswith("sha256="):
        raise _ArtifactInvalid("wheel_record_hash_algorithm_invalid")
    encoded = value[len("sha256=") :]
    if len(encoded) != 43 or "=" in encoded:
        raise _ArtifactInvalid("wheel_record_hash_invalid")
    try:
        ascii_value = encoded.encode("ascii")
        decoded = base64.b64decode(ascii_value + b"=", altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise _ArtifactInvalid("wheel_record_hash_invalid") from exc
    if len(decoded) != hashlib.sha256().digest_size or base64.urlsafe_b64encode(decoded).rstrip(b"=") != ascii_value:
        raise _ArtifactInvalid("wheel_record_hash_invalid")
    return decoded.hex()


def _parse_record(raw: bytes, *, record_path: str) -> dict[str, tuple[str, int | None]]:
    if not raw or len(raw) > MAX_WHEEL_CONTROL_FILE_BYTES or b"\x00" in raw:
        raise _ArtifactInvalid("wheel_record_invalid")
    try:
        text = raw.decode("utf-8", errors="strict")
        rows = tuple(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise _ArtifactInvalid("wheel_record_invalid") from exc
    if not rows:
        raise _ArtifactInvalid("wheel_record_invalid")
    result: dict[str, tuple[str, int | None]] = {}
    for row in rows:
        if len(row) != 3:
            raise _ArtifactInvalid("wheel_record_row_invalid")
        path, encoded_hash, encoded_size = row
        _safe_member_name(path, directory=False)
        if path in result:
            raise _ArtifactInvalid("wheel_record_path_duplicate")
        if path == record_path:
            if encoded_hash or encoded_size:
                raise _ArtifactInvalid("wheel_record_self_row_invalid")
            result[path] = ("", None)
            continue
        if not encoded_hash:
            raise _ArtifactInvalid("wheel_record_hash_missing")
        decoded_hash = _decode_record_hash(encoded_hash)
        if not encoded_size or not encoded_size.isascii() or not encoded_size.isdecimal():
            raise _ArtifactInvalid("wheel_record_size_invalid")
        if len(encoded_size) > 1 and encoded_size.startswith("0"):
            raise _ArtifactInvalid("wheel_record_size_invalid")
        size = int(encoded_size)
        if size < 0 or size > MAX_WHEEL_MEMBER_BYTES:
            raise _ArtifactInvalid("wheel_record_size_invalid")
        result[path] = (decoded_hash, size)
    if record_path not in result:
        raise _ArtifactInvalid("wheel_record_self_row_missing")
    return result


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _ArtifactInvalid("wheel_sbom_json_duplicate_key")
        result[key] = value
    return result


def _reject_json_constant(_: str) -> object:
    raise _ArtifactInvalid("wheel_sbom_json_invalid")


def _validate_sbom(
    raw: bytes,
    *,
    wheel_sha256: str,
    expected_distribution: str,
    expected_version: str,
    member_hashes: Mapping[str, tuple[str, int]],
    payload_members: Mapping[str, tuple[str, int]],
    source_inventory: Mapping[str, str],
    source_provenance: Mapping[str, object],
    native_build_provenance_sha256: str,
    license_determinations: Mapping[str, _LicenseDetermination],
    extracted_licenses: tuple[dict[str, object], ...],
    license_determination_sha256: str,
    dependencies: tuple[_DependencyPackage, ...],
    root_dependency_ids: tuple[str, ...],
) -> None:
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except _ArtifactInvalid:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise _ArtifactInvalid("wheel_sbom_json_invalid") from exc
    if not isinstance(payload, Mapping):
        raise _ArtifactInvalid("wheel_sbom_json_invalid")
    if (
        payload.get("spdxVersion") != "SPDX-2.3"
        or payload.get("dataLicense") != "CC0-1.0"
        or payload.get("SPDXID") != "SPDXRef-DOCUMENT"
    ):
        raise _ArtifactInvalid("wheel_sbom_spdx23_invalid")
    expected_namespace = f"https://betelgeuze.invalid/spdx/{expected_distribution}/{expected_version}/{wheel_sha256}"
    if payload.get("documentNamespace") != expected_namespace:
        raise _ArtifactInvalid("wheel_sbom_namespace_mismatch")
    if payload.get("name") != f"{expected_distribution}-{expected_version}-sbom":
        raise _ArtifactInvalid("wheel_sbom_document_name_mismatch")
    root_id = "SPDXRef-Package-EngineV2"
    source_id = "SPDXRef-Package-Source"
    root_license_key = f"pypi:{_canonical_dependency_name(expected_distribution)}@{expected_version}"
    root_license = license_determinations[root_license_key]
    source_inventory_sha256 = _sha256_bytes(_canonical_bytes(dict(sorted(source_inventory.items()))))

    def package_license_fields(row: _LicenseDetermination) -> dict[str, str]:
        return {
            "licenseConcluded": row.license_concluded,
            "licenseDeclared": row.license_declared,
            "copyrightText": row.copyright_text,
        }

    expected_packages: list[dict[str, object]] = [
        {
            "SPDXID": root_id,
            "name": expected_distribution,
            "versionInfo": expected_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
            **package_license_fields(root_license),
            "checksums": [{"algorithm": "SHA256", "checksumValue": wheel_sha256}],
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": (f"pkg:pypi/{expected_distribution}@{expected_version}"),
                }
            ],
            "comment": f"License determination evidence: {root_license.evidence}",
        },
        {
            "SPDXID": source_id,
            "name": f"{expected_distribution}-source",
            "versionInfo": expected_version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
            **package_license_fields(root_license),
            "checksums": [
                {
                    "algorithm": "SHA256",
                    "checksumValue": source_inventory_sha256,
                }
            ],
            "comment": (f"{SOURCE_PROVENANCE_SCHEMA_ID}; license determination evidence: {root_license.evidence}"),
        },
    ]
    for dependency in dependencies:
        determination = license_determinations[dependency.license_key]
        package: dict[str, object] = {
            "SPDXID": dependency.spdx_id,
            "name": dependency.name,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            **package_license_fields(determination),
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": dependency.purl,
                }
            ],
            "comment": "; ".join(
                value
                for value in (
                    dependency.comment,
                    f"License determination evidence: {determination.evidence}",
                )
                if value
            ),
        }
        if dependency.version:
            package["versionInfo"] = dependency.version
        if dependency.checksum:
            package["checksums"] = [{"algorithm": "SHA256", "checksumValue": dependency.checksum}]
        expected_packages.append(package)
    packages = payload.get("packages")
    if not isinstance(packages, list):
        raise _ArtifactInvalid("wheel_sbom_packages_invalid")
    roots = [value for value in packages if isinstance(value, Mapping) and value.get("SPDXID") == root_id]
    if len(roots) != 1:
        raise _ArtifactInvalid("wheel_sbom_root_package_invalid")
    if roots[0].get("name") != expected_distribution or roots[0].get("versionInfo") != expected_version:
        raise _ArtifactInvalid("wheel_sbom_package_identity_mismatch")
    if roots[0].get("checksums") != [{"algorithm": "SHA256", "checksumValue": wheel_sha256}]:
        raise _ArtifactInvalid("wheel_sbom_checksum_mismatch")
    if packages != expected_packages:
        if not any(
            isinstance(value, Mapping) and value.get("SPDXID") == root_id and value.get("filesAnalyzed") is True
            for value in packages
        ):
            raise _ArtifactInvalid("wheel_sbom_root_files_not_analyzed")
        if any(
            isinstance(value, Mapping)
            and (
                value.get("licenseConcluded") in {None, "", "NOASSERTION", "NONE"}
                or value.get("licenseDeclared") in {None, "", "NOASSERTION", "NONE"}
            )
            for value in packages
        ):
            raise _ArtifactInvalid("wheel_sbom_license_determination_incomplete")
        raise _ArtifactInvalid("wheel_sbom_package_dependency_ledger_mismatch")

    expected_files: list[dict[str, object]] = []
    for name, (checksum, _) in sorted(member_hashes.items()):
        expected_files.append(
            {
                "SPDXID": _wheel_file_spdx_id(name),
                "fileName": name,
                "checksums": [{"algorithm": "SHA256", "checksumValue": checksum}],
                "licenseConcluded": root_license.license_concluded,
                "copyrightText": root_license.copyright_text,
            }
        )
    for name, checksum in sorted(source_inventory.items()):
        expected_files.append(
            {
                "SPDXID": _source_file_spdx_id(name),
                "fileName": f"source/{name}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": checksum}],
                "licenseConcluded": root_license.license_concluded,
                "copyrightText": root_license.copyright_text,
            }
        )
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise _ArtifactInvalid("wheel_sbom_file_inventory_missing")
    if files != expected_files:
        observed_names = {
            value.get("fileName")
            for value in files
            if isinstance(value, Mapping) and isinstance(value.get("fileName"), str)
        }
        expected_names = {value["fileName"] for value in expected_files}
        if observed_names != expected_names:
            raise _ArtifactInvalid("wheel_sbom_file_inventory_member_set_mismatch")
        if any(
            isinstance(value, Mapping) and value.get("licenseConcluded") in {None, "", "NOASSERTION", "NONE"}
            for value in files
        ):
            raise _ArtifactInvalid("wheel_sbom_file_license_determination_incomplete")
        raise _ArtifactInvalid("wheel_sbom_file_checksum_mismatch")

    expected_relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        },
        {
            "spdxElementId": root_id,
            "relationshipType": "GENERATED_FROM",
            "relatedSpdxElement": source_id,
        },
    ]
    expected_relationships.extend(
        {
            "spdxElementId": root_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": _wheel_file_spdx_id(name),
        }
        for name in sorted(member_hashes)
    )
    expected_relationships.extend(
        {
            "spdxElementId": source_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": _source_file_spdx_id(name),
        }
        for name in sorted(source_inventory)
    )
    generated_from = source_provenance.get("generated_from")
    if not isinstance(generated_from, list):
        raise _ArtifactInvalid("wheel_source_provenance_invalid")
    for mapping in generated_from:
        if not isinstance(mapping, Mapping):
            raise _ArtifactInvalid("wheel_source_provenance_invalid")
        wheel_member = str(mapping.get("wheel_member") or "")
        source_path = str(mapping.get("source_path") or "")
        expected_relationships.append(
            {
                "spdxElementId": _wheel_file_spdx_id(wheel_member),
                "relationshipType": "GENERATED_FROM",
                "relatedSpdxElement": _source_file_spdx_id(source_path),
            }
        )
    if native_build_provenance_sha256:
        for name in sorted(payload_members):
            expected_relationships.append(
                {
                    "spdxElementId": _wheel_file_spdx_id(name),
                    "relationshipType": "GENERATED_FROM",
                    "relatedSpdxElement": source_id,
                }
            )
    pypi_dependency_ids = {row.spdx_id for row in dependencies if row.spdx_id.startswith("SPDXRef-PyPI-")}
    for dependency_id in sorted({*root_dependency_ids, *pypi_dependency_ids}):
        expected_relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
        )
    for dependency in dependencies:
        for dependency_id in dependency.dependency_ids:
            expected_relationships.append(
                {
                    "spdxElementId": dependency.spdx_id,
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": dependency_id,
                }
            )
    expected_relationships = sorted(
        expected_relationships,
        key=lambda row: (
            row["spdxElementId"],
            row["relationshipType"],
            row["relatedSpdxElement"],
        ),
    )
    relationships = payload.get("relationships")
    if relationships != expected_relationships:
        if isinstance(relationships, list):
            observed_contains = {
                (
                    value.get("spdxElementId"),
                    value.get("relatedSpdxElement"),
                )
                for value in relationships
                if isinstance(value, Mapping) and value.get("relationshipType") == "CONTAINS"
            }
            expected_contains = {
                (value["spdxElementId"], value["relatedSpdxElement"])
                for value in expected_relationships
                if value["relationshipType"] == "CONTAINS"
            }
            if observed_contains != expected_contains:
                raise _ArtifactInvalid("wheel_sbom_contains_binding_mismatch")
        raise _ArtifactInvalid("wheel_sbom_relationship_dependency_closure_mismatch")

    source_provenance_sha256 = _sha256_bytes(_canonical_bytes(source_provenance))
    expected_annotations = [
        {
            "annotationDate": "2025-01-01T00:00:00Z",
            "annotationType": "OTHER",
            "annotator": "Tool: betelgeuze-engine-v2-sbom/2.0.0",
            "comment": f"{_SOURCE_ANNOTATION_PREFIX}{source_provenance_sha256}",
        },
        {
            "annotationDate": "2025-01-01T00:00:00Z",
            "annotationType": "OTHER",
            "annotator": "Tool: betelgeuze-engine-v2-sbom/2.0.0",
            "comment": (f"{_LICENSE_ANNOTATION_PREFIX}{license_determination_sha256}"),
        },
    ]
    if native_build_provenance_sha256:
        expected_annotations.append(
            {
                "annotationDate": "2025-01-01T00:00:00Z",
                "annotationType": "OTHER",
                "annotator": "Tool: betelgeuze-engine-v2-sbom/2.0.0",
                "comment": (f"{_NATIVE_ANNOTATION_PREFIX}{native_build_provenance_sha256}"),
            }
        )
    if payload.get("annotations") != expected_annotations:
        raise _ArtifactInvalid("wheel_sbom_provenance_annotation_mismatch")
    expected_extracted = list(extracted_licenses)
    if expected_extracted:
        if payload.get("hasExtractedLicensingInfos") != expected_extracted:
            raise _ArtifactInvalid("wheel_sbom_extracted_license_mismatch")
    elif "hasExtractedLicensingInfos" in payload:
        raise _ArtifactInvalid("wheel_sbom_extracted_license_mismatch")


@dataclass(frozen=True, slots=True)
class WheelArtifactValidationResult:
    artifact_kind: WheelArtifactKind
    expected_distribution: str
    expected_version: str
    wheel_filename: str
    valid: bool
    blockers: tuple[str, ...]
    wheel_sha256: str = ""
    sbom_sha256: str = ""
    metadata_name: str = ""
    metadata_version: str = ""
    member_count: int = 0
    total_uncompressed_bytes: int = 0
    extension_member: str = ""
    extension_sha256: str = ""
    base_build_provenance_sha256: str = ""
    source_provenance_sha256: str = ""
    native_build_provenance_sha256: str = ""
    license_determination_sha256: str = ""
    dependency_package_count: int = 0
    license_review_closed: bool = False
    _receipt_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        kind = self.artifact_kind
        if isinstance(kind, str):
            kind = WheelArtifactKind(kind)
            object.__setattr__(self, "artifact_kind", kind)
        blockers = tuple(str(value) for value in self.blockers)
        if any(not value for value in blockers) or len(blockers) != len(set(blockers)):
            raise ValueError("blockers must be unique non-empty strings")
        object.__setattr__(self, "blockers", blockers)
        if self.valid != (not blockers):
            raise ValueError("valid does not match blockers")
        object.__setattr__(self, "_receipt_sha256", _sha256_bytes(_canonical_bytes(self._projection())))

    def _projection(self) -> dict[str, object]:
        return {
            "schema_id": WHEEL_ARTIFACT_VALIDATION_SCHEMA_ID,
            "artifact_kind": self.artifact_kind.value,
            "expected_distribution": self.expected_distribution,
            "expected_version": self.expected_version,
            "wheel_filename": self.wheel_filename,
            "valid": self.valid,
            "blockers": list(self.blockers),
            "wheel_sha256": self.wheel_sha256,
            "sbom_sha256": self.sbom_sha256,
            "metadata_name": self.metadata_name,
            "metadata_version": self.metadata_version,
            "member_count": self.member_count,
            "total_uncompressed_bytes": self.total_uncompressed_bytes,
            "extension_member": self.extension_member,
            "extension_sha256": self.extension_sha256,
            "base_build_provenance_sha256": (
                self.base_build_provenance_sha256
            ),
            "source_provenance_sha256": self.source_provenance_sha256,
            "native_build_provenance_sha256": self.native_build_provenance_sha256,
            "license_determination_sha256": self.license_determination_sha256,
            "dependency_package_count": self.dependency_package_count,
            "license_review_closed": self.license_review_closed,
        }

    @property
    def receipt_sha256(self) -> str:
        observed = _sha256_bytes(_canonical_bytes(self._projection()))
        if observed != self._receipt_sha256:
            raise ValueError("wheel artifact validation result changed")
        return observed

    def to_dict(self) -> dict[str, object]:
        return {**self._projection(), "receipt_sha256": self.receipt_sha256}


@dataclass(slots=True)
class _ObservedArtifact:
    wheel_sha256: str = ""
    sbom_sha256: str = ""
    metadata_name: str = ""
    metadata_version: str = ""
    member_count: int = 0
    total_uncompressed_bytes: int = 0
    extension_member: str = ""
    extension_sha256: str = ""
    base_build_provenance_sha256: str = ""
    source_provenance_sha256: str = ""
    native_build_provenance_sha256: str = ""
    license_determination_sha256: str = ""
    dependency_package_count: int = 0
    license_review_closed: bool = False


def _result(
    *,
    kind: WheelArtifactKind,
    expected_distribution: str,
    expected_version: str,
    wheel_filename: str,
    observed: _ObservedArtifact,
    blocker: str = "",
) -> WheelArtifactValidationResult:
    blockers = (blocker,) if blocker else ()
    return WheelArtifactValidationResult(
        artifact_kind=kind,
        expected_distribution=expected_distribution,
        expected_version=expected_version,
        wheel_filename=wheel_filename,
        valid=not blockers,
        blockers=blockers,
        wheel_sha256=observed.wheel_sha256,
        sbom_sha256=observed.sbom_sha256,
        metadata_name=observed.metadata_name,
        metadata_version=observed.metadata_version,
        member_count=observed.member_count,
        total_uncompressed_bytes=observed.total_uncompressed_bytes,
        extension_member=observed.extension_member,
        extension_sha256=observed.extension_sha256,
        base_build_provenance_sha256=(observed.base_build_provenance_sha256),
        source_provenance_sha256=observed.source_provenance_sha256,
        native_build_provenance_sha256=observed.native_build_provenance_sha256,
        license_determination_sha256=observed.license_determination_sha256,
        dependency_package_count=observed.dependency_package_count,
        license_review_closed=observed.license_review_closed,
    )


def validate_wheel_artifact(
    wheel_path: str | Path,
    sbom_path: str | Path,
    *,
    artifact_kind: WheelArtifactKind | str,
    expected_distribution: str,
    expected_version: str,
    expected_extension_sha256: str = "",
    expected_wheel_sha256: str = "",
    expected_sbom_sha256: str = "",
    source_root: str | Path | None = None,
    license_determination_path: str | Path | None = None,
    cargo_lock_path: str | Path | None = None,
    native_build_provenance_path: str | Path | None = None,
    expected_source_receipt_sha256: str = "",
    expected_license_determination_sha256: str = "",
    expected_native_build_provenance_sha256: str = "",
) -> WheelArtifactValidationResult:
    """Validate one exact wheel/SBOM pair without executing wheel contents.

    Invalid or unreadable artifacts return ``valid=False`` with a stable blocker
    rather than raising.  Optional expected artifact hashes bind the result to a
    predeclared Stage 0 receipt.  Native wheels always require the independently
    measured installed-extension SHA-256.  Source, license-determination, and
    native-build provenance are mandatory external authorities; they are never
    accepted solely because a wheel or its self-authored SBOM names them.
    """

    observed = _ObservedArtifact()
    try:
        try:
            kind = (
                artifact_kind if isinstance(artifact_kind, WheelArtifactKind) else WheelArtifactKind(str(artifact_kind))
            )
        except (TypeError, ValueError) as exc:
            raise _ArtifactInvalid("wheel_artifact_kind_invalid") from exc
        expected_distribution = str(expected_distribution or "").strip()
        expected_version = str(expected_version or "").strip()
        if _DISTRIBUTION_RE.fullmatch(expected_distribution) is None or len(expected_distribution) > 128:
            raise _ArtifactInvalid("wheel_expected_distribution_invalid")
        if _VERSION_RE.fullmatch(expected_version) is None or len(expected_version) > 128:
            raise _ArtifactInvalid("wheel_expected_version_invalid")
        expected_extension = _digest_or_empty(expected_extension_sha256)
        if kind is WheelArtifactKind.NATIVE and not expected_extension:
            raise _ArtifactInvalid("native_extension_expected_sha256_invalid")
        if kind is WheelArtifactKind.BASE and str(expected_extension_sha256 or "").strip():
            raise _ArtifactInvalid("base_extension_expected_sha256_forbidden")
        requested_wheel_sha256 = _digest_or_empty(expected_wheel_sha256)
        if str(expected_wheel_sha256 or "").strip() and not requested_wheel_sha256:
            raise _ArtifactInvalid("expected_wheel_sha256_invalid")
        requested_sbom_sha256 = _digest_or_empty(expected_sbom_sha256)
        if str(expected_sbom_sha256 or "").strip() and not requested_sbom_sha256:
            raise _ArtifactInvalid("expected_sbom_sha256_invalid")
        requested_source_receipt_sha256 = _digest_or_empty(expected_source_receipt_sha256)
        if not requested_source_receipt_sha256:
            raise _ArtifactInvalid("expected_source_receipt_sha256_invalid")
        requested_license_sha256 = _digest_or_empty(expected_license_determination_sha256)
        if not requested_license_sha256:
            raise _ArtifactInvalid("expected_license_determination_sha256_invalid")
        requested_native_provenance_sha256 = _digest_or_empty(expected_native_build_provenance_sha256)
        if kind is WheelArtifactKind.NATIVE and not requested_native_provenance_sha256:
            raise _ArtifactInvalid("expected_native_build_provenance_sha256_invalid")
        if kind is WheelArtifactKind.BASE and str(expected_native_build_provenance_sha256 or "").strip():
            raise _ArtifactInvalid("base_native_provenance_forbidden")
        try:
            wheel = Path(wheel_path)
            sbom = Path(sbom_path)
        except TypeError as exc:
            raise _ArtifactInvalid("artifact_path_invalid") from exc
        wheel_filename = wheel.name
        filename = _parse_wheel_filename(
            wheel_filename,
            expected_distribution=expected_distribution,
            expected_version=expected_version,
        )
        _regular_path(
            wheel,
            missing="wheel_artifact_missing",
            unsafe="wheel_artifact_not_regular",
            too_large="wheel_size_out_of_bounds",
            limit=MAX_WHEEL_ARCHIVE_BYTES,
        )
        observed.wheel_sha256, _ = _hash_path(
            wheel,
            limit=MAX_WHEEL_ARCHIVE_BYTES,
            too_large="wheel_size_out_of_bounds",
        )
        if requested_wheel_sha256 and observed.wheel_sha256 != requested_wheel_sha256:
            raise _ArtifactInvalid("wheel_expected_sha256_mismatch")

        try:
            archive = zipfile.ZipFile(wheel, mode="r")
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
            raise _ArtifactInvalid("wheel_zip_invalid") from exc
        with archive:
            infos = tuple(archive.infolist())
            if not 1 <= len(infos) <= MAX_WHEEL_MEMBER_COUNT:
                raise _ArtifactInvalid("wheel_member_count_out_of_bounds")
            seen_names: set[str] = set()
            seen_collision_keys: set[str] = set()
            files: dict[str, zipfile.ZipInfo] = {}
            total_uncompressed = 0
            for info in infos:
                if getattr(info, "orig_filename", info.filename) != info.filename:
                    raise _ArtifactInvalid("wheel_member_path_unsafe")
                name = _safe_member_name(info.filename, directory=info.is_dir())
                collision_key = name.rstrip("/").casefold()
                if name in seen_names or collision_key in seen_collision_keys:
                    raise _ArtifactInvalid("wheel_member_duplicate")
                seen_names.add(name)
                seen_collision_keys.add(collision_key)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                file_type = stat.S_IFMT(unix_mode)
                allowed_types = {0, stat.S_IFDIR if info.is_dir() else stat.S_IFREG}
                if file_type not in allowed_types:
                    raise _ArtifactInvalid("wheel_member_type_unsafe")
                if info.flag_bits & 0x1:
                    raise _ArtifactInvalid("wheel_member_encrypted")
                if info.compress_type not in _ALLOWED_COMPRESSION:
                    raise _ArtifactInvalid("wheel_compression_unsupported")
                if info.file_size < 0 or info.compress_size < 0:
                    raise _ArtifactInvalid("wheel_member_size_invalid")
                if info.is_dir():
                    if info.file_size or info.compress_size:
                        raise _ArtifactInvalid("wheel_directory_member_invalid")
                    continue
                if info.file_size > MAX_WHEEL_MEMBER_BYTES:
                    raise _ArtifactInvalid("wheel_member_size_out_of_bounds")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_WHEEL_UNCOMPRESSED_BYTES:
                    raise _ArtifactInvalid("wheel_uncompressed_size_out_of_bounds")
                files[name] = info
            observed.member_count = len(files)
            observed.total_uncompressed_bytes = total_uncompressed
            if len(files) < 4:
                raise _ArtifactInvalid("wheel_payload_incomplete")

            expected_dist_info = f"{filename.distribution}-{filename.version}.dist-info"
            dist_info_components = {
                (index, part)
                for name in files
                for index, part in enumerate(PurePosixPath(name).parts)
                if part.endswith(".dist-info")
            }
            if dist_info_components != {(0, expected_dist_info)}:
                raise _ArtifactInvalid("wheel_dist_info_identity_invalid")
            metadata_path = f"{expected_dist_info}/METADATA"
            entry_points_path = f"{expected_dist_info}/entry_points.txt"
            wheel_metadata_path = f"{expected_dist_info}/WHEEL"
            record_path = f"{expected_dist_info}/RECORD"
            for required_path, blocker in (
                (metadata_path, "wheel_metadata_missing"),
                (wheel_metadata_path, "wheel_control_metadata_missing"),
                (record_path, "wheel_record_missing"),
            ):
                if required_path not in files:
                    raise _ArtifactInvalid(blocker)
            if kind is WheelArtifactKind.BASE and entry_points_path not in files:
                raise _ArtifactInvalid("base_wheel_entry_points_missing")
            if kind is WheelArtifactKind.NATIVE and any(
                name.endswith(".dist-info/entry_points.txt") for name in files
            ):
                raise _ArtifactInvalid("native_wheel_entry_points_forbidden")
            if tuple(name for name in files if name.endswith(".dist-info/METADATA")) != (metadata_path,):
                raise _ArtifactInvalid("wheel_metadata_identity_invalid")
            if tuple(name for name in files if name.endswith(".dist-info/WHEEL")) != (wheel_metadata_path,):
                raise _ArtifactInvalid("wheel_control_metadata_identity_invalid")
            if tuple(name for name in files if name.endswith(".dist-info/RECORD")) != (record_path,):
                raise _ArtifactInvalid("wheel_record_identity_invalid")
            if kind is WheelArtifactKind.BASE and tuple(
                name for name in files if name.endswith(".dist-info/entry_points.txt")
            ) != (entry_points_path,):
                raise _ArtifactInvalid("base_wheel_entry_points_identity_invalid")

            member_hashes: dict[str, tuple[str, int]] = {}
            captured: dict[str, bytes] = {}
            capture_names = {metadata_path, wheel_metadata_path, record_path}
            if kind is WheelArtifactKind.BASE:
                capture_names.add(entry_points_path)
            for name, info in files.items():
                digest = hashlib.sha256()
                size = 0
                capture = bytearray() if name in capture_names else None
                try:
                    with archive.open(info, mode="r") as handle:
                        for chunk in iter(lambda: handle.read(_READ_CHUNK_BYTES), b""):
                            size += len(chunk)
                            if size > info.file_size or size > MAX_WHEEL_MEMBER_BYTES:
                                raise _ArtifactInvalid("wheel_member_size_invalid")
                            digest.update(chunk)
                            if capture is not None:
                                if len(capture) + len(chunk) > MAX_WHEEL_CONTROL_FILE_BYTES:
                                    raise _ArtifactInvalid("wheel_control_file_too_large")
                                capture.extend(chunk)
                except _ArtifactInvalid:
                    raise
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise _ArtifactInvalid("wheel_member_read_failed") from exc
                if size != info.file_size:
                    raise _ArtifactInvalid("wheel_member_size_invalid")
                member_hashes[name] = (digest.hexdigest(), size)
                if capture is not None:
                    captured[name] = bytes(capture)

            metadata = _parse_control_message(captured[metadata_path], blocker="wheel_metadata_invalid")
            _unique_headers(
                metadata,
                "Metadata-Version",
                blocker="wheel_metadata_version_header_invalid",
            )
            observed.metadata_name = _unique_headers(metadata, "Name", blocker="wheel_metadata_name_invalid")
            observed.metadata_version = _unique_headers(
                metadata,
                "Version",
                blocker="wheel_metadata_distribution_version_invalid",
            )
            if observed.metadata_name != expected_distribution:
                raise _ArtifactInvalid("wheel_metadata_name_mismatch")
            if observed.metadata_version != expected_version:
                raise _ArtifactInvalid("wheel_metadata_version_mismatch")
            metadata_requirements = _parse_metadata_requirements(metadata)

            wheel_metadata = _parse_control_message(
                captured[wheel_metadata_path], blocker="wheel_control_metadata_invalid"
            )
            if _unique_headers(wheel_metadata, "Wheel-Version", blocker="wheel_version_invalid") != "1.0":
                raise _ArtifactInvalid("wheel_version_invalid")
            expected_purelib = "false" if kind is WheelArtifactKind.NATIVE else "true"
            if (
                _unique_headers(
                    wheel_metadata,
                    "Root-Is-Purelib",
                    blocker="wheel_purelib_flag_invalid",
                ).lower()
                != expected_purelib
            ):
                raise _ArtifactInvalid("wheel_purelib_flag_invalid")
            wheel_tags = wheel_metadata.get_all("Tag", [])
            if (
                not wheel_tags
                or len(wheel_tags) != len(set(wheel_tags))
                or frozenset(str(value).strip() for value in wheel_tags) != filename.expanded_tags
            ):
                raise _ArtifactInvalid("wheel_tag_mismatch")
            builds = tuple(str(value).strip() for value in wheel_metadata.get_all("Build", []))
            if builds != ((filename.build_tag,) if filename.build_tag else ()):
                raise _ArtifactInvalid("wheel_build_tag_mismatch")

            record = _parse_record(captured[record_path], record_path=record_path)
            if set(record) != set(files):
                raise _ArtifactInvalid("wheel_record_member_set_mismatch")
            for name, (declared_hash, declared_size) in record.items():
                if name == record_path:
                    continue
                actual_hash, actual_size = member_hashes[name]
                if declared_hash != actual_hash:
                    raise _ArtifactInvalid("wheel_record_hash_mismatch")
                if declared_size != actual_size:
                    raise _ArtifactInvalid("wheel_record_size_mismatch")

            payload_files = tuple(name for name in files if not name.startswith(f"{expected_dist_info}/"))
            if not payload_files:
                raise _ArtifactInvalid("wheel_payload_missing")
            extensions = tuple(name for name in files if name.lower().endswith(_NATIVE_EXTENSION_SUFFIXES))
            if kind is WheelArtifactKind.BASE:
                if extensions:
                    raise _ArtifactInvalid("base_wheel_native_extension_forbidden")
                if any(not name.startswith("betelgeuze_engine_v2/") for name in payload_files):
                    raise _ArtifactInvalid("wheel_payload_namespace_invalid")
            else:
                if len(extensions) != 1 or extensions[0] not in payload_files:
                    raise _ArtifactInvalid("native_wheel_extension_count_invalid")
                if (
                    len(payload_files) != 1
                    or len(PurePosixPath(extensions[0]).parts) != 1
                    or not extensions[0].startswith("betelgeuze_engine_v2_native")
                ):
                    raise _ArtifactInvalid("wheel_payload_namespace_invalid")
                observed.extension_member = extensions[0]
                observed.extension_sha256 = member_hashes[extensions[0]][0]
                if observed.extension_sha256 != expected_extension:
                    raise _ArtifactInvalid("native_wheel_extension_sha256_mismatch")

        try:
            source_root_path = Path(source_root)  # type: ignore[arg-type]
        except TypeError as exc:
            raise _ArtifactInvalid("wheel_source_root_missing") from exc
        try:
            license_path = Path(license_determination_path)  # type: ignore[arg-type]
        except TypeError as exc:
            raise _ArtifactInvalid("license_determination_missing") from exc
        if kind is WheelArtifactKind.BASE:
            observed.base_build_provenance_sha256 = (
                _base_build_provenance_sha256(
                    source_root=source_root_path,
                    metadata_message=metadata,
                    entry_points_raw=captured[entry_points_path],
                    wheel_message=wheel_metadata,
                    filename=filename,
                    metadata_sha256=member_hashes[metadata_path][0],
                    entry_points_sha256=member_hashes[entry_points_path][0],
                    wheel_control_sha256=member_hashes[wheel_metadata_path][0],
                )
            )
        pypi_dependencies = _pypi_dependency_packages(metadata_requirements)
        cargo_dependencies: tuple[_DependencyPackage, ...] = ()
        root_dependency_ids: tuple[str, ...] = ()
        cargo_lock_sha256 = ""
        cargo_packages: tuple[_CargoPackage, ...] = ()
        cargo_path: Path | None = None
        native_provenance_path: Path | None = None
        if kind is WheelArtifactKind.BASE:
            if cargo_lock_path is not None or native_build_provenance_path is not None:
                raise _ArtifactInvalid("base_native_provenance_forbidden")
        else:
            try:
                cargo_path = Path(cargo_lock_path)  # type: ignore[arg-type]
            except TypeError as exc:
                raise _ArtifactInvalid("cargo_lock_missing") from exc
            cargo_packages, cargo_lock_sha256 = _parse_cargo_lock(cargo_path)
            cargo_dependencies, root_dependency_ids = _cargo_dependency_packages(
                cargo_packages,
                root_distribution=expected_distribution,
                root_version=expected_version,
            )
        dependencies = tuple((*pypi_dependencies, *cargo_dependencies))
        expected_license_keys = _expected_license_keys(
            distribution=expected_distribution,
            version=expected_version,
            dependencies=dependencies,
        )
        (
            license_determinations,
            extracted_licenses,
            observed.license_determination_sha256,
        ) = _load_license_determinations(
            license_path,
            expected_package_keys=expected_license_keys,
        )
        if observed.license_determination_sha256 != requested_license_sha256:
            raise _ArtifactInvalid("license_determination_expected_sha256_mismatch")
        observed.license_review_closed = True
        observed.dependency_package_count = len(dependencies)
        payload_member_hashes = {name: member_hashes[name] for name in payload_files}
        source_inventory, generated_from = _source_file_inventory(
            source_root_path,
            kind=kind,
            payload_members=payload_member_hashes,
        )
        if kind is WheelArtifactKind.NATIVE:
            expected_cargo_lock = source_root_path / "Cargo.lock"
            try:
                cargo_resolved = Path(cargo_lock_path).resolve(strict=True)  # type: ignore[arg-type]
                expected_cargo_resolved = expected_cargo_lock.resolve(strict=True)
            except (OSError, RuntimeError, TypeError) as exc:
                raise _ArtifactInvalid("cargo_lock_source_binding_mismatch") from exc
            if cargo_resolved != expected_cargo_resolved:
                raise _ArtifactInvalid("cargo_lock_source_binding_mismatch")
            try:
                native_provenance_path = Path(native_build_provenance_path)  # type: ignore[arg-type]
            except TypeError as exc:
                raise _ArtifactInvalid("native_build_provenance_missing") from exc
            observed.native_build_provenance_sha256 = _load_native_build_provenance(
                native_provenance_path,
                wheel_sha256=observed.wheel_sha256,
                extension_member=observed.extension_member,
                extension_sha256=observed.extension_sha256,
                cargo_lock_sha256=cargo_lock_sha256,
                source_inventory=source_inventory,
                source_receipt_sha256=requested_source_receipt_sha256,
            )
            if observed.native_build_provenance_sha256 != requested_native_provenance_sha256:
                raise _ArtifactInvalid("native_build_provenance_expected_sha256_mismatch")
        source_provenance = _source_provenance(
            kind=kind,
            payload_members=payload_member_hashes,
            source_inventory=source_inventory,
            mappings=generated_from,
            source_receipt_sha256=requested_source_receipt_sha256,
            cargo_lock_sha256=cargo_lock_sha256,
            native_build_provenance_sha256=(observed.native_build_provenance_sha256),
        )
        observed.source_provenance_sha256 = _sha256_bytes(_canonical_bytes(source_provenance))

        post_validation_wheel_sha256, _ = _hash_path(
            wheel,
            limit=MAX_WHEEL_ARCHIVE_BYTES,
            too_large="wheel_size_out_of_bounds",
        )
        if post_validation_wheel_sha256 != observed.wheel_sha256:
            raise _ArtifactInvalid("wheel_changed_during_validation")

        _regular_path(
            sbom,
            missing="wheel_sbom_missing",
            unsafe="wheel_sbom_not_regular",
            too_large="wheel_sbom_size_out_of_bounds",
            limit=MAX_SBOM_BYTES,
        )
        observed.sbom_sha256, sbom_raw = _hash_path(
            sbom,
            limit=MAX_SBOM_BYTES,
            too_large="wheel_sbom_size_out_of_bounds",
            capture_bytes=True,
        )
        if requested_sbom_sha256 and observed.sbom_sha256 != requested_sbom_sha256:
            raise _ArtifactInvalid("wheel_sbom_expected_sha256_mismatch")
        if sbom_raw is None:
            raise _ArtifactInvalid("wheel_sbom_read_failed")
        _validate_sbom(
            sbom_raw,
            wheel_sha256=observed.wheel_sha256,
            expected_distribution=expected_distribution,
            expected_version=expected_version,
            member_hashes=member_hashes,
            payload_members=payload_member_hashes,
            source_inventory=source_inventory,
            source_provenance=source_provenance,
            native_build_provenance_sha256=(observed.native_build_provenance_sha256),
            license_determinations=license_determinations,
            extracted_licenses=extracted_licenses,
            license_determination_sha256=(observed.license_determination_sha256),
            dependencies=dependencies,
            root_dependency_ids=root_dependency_ids,
        )
        post_source_inventory, post_generated_from = _source_file_inventory(
            source_root_path,
            kind=kind,
            payload_members=payload_member_hashes,
        )
        if post_source_inventory != source_inventory or post_generated_from != generated_from:
            raise _ArtifactInvalid("wheel_source_changed_during_validation")
        post_license_sha256, _ = _hash_path(
            license_path,
            limit=MAX_PROVENANCE_BYTES,
            too_large="license_determination_size_out_of_bounds",
        )
        if post_license_sha256 != observed.license_determination_sha256:
            raise _ArtifactInvalid("license_determination_changed_during_validation")
        if kind is WheelArtifactKind.NATIVE:
            if cargo_path is None or native_provenance_path is None:
                raise _ArtifactInvalid("native_build_provenance_missing")
            post_cargo_sha256, _ = _hash_path(
                cargo_path,
                limit=MAX_PROVENANCE_BYTES,
                too_large="cargo_lock_size_out_of_bounds",
            )
            if post_cargo_sha256 != cargo_lock_sha256:
                raise _ArtifactInvalid("cargo_lock_changed_during_validation")
            post_native_sha256, _ = _hash_path(
                native_provenance_path,
                limit=MAX_PROVENANCE_BYTES,
                too_large="native_build_provenance_size_out_of_bounds",
            )
            if post_native_sha256 != observed.native_build_provenance_sha256:
                raise _ArtifactInvalid("native_build_provenance_changed_during_validation")
        final_wheel_sha256, _ = _hash_path(
            wheel,
            limit=MAX_WHEEL_ARCHIVE_BYTES,
            too_large="wheel_size_out_of_bounds",
        )
        if final_wheel_sha256 != observed.wheel_sha256:
            raise _ArtifactInvalid("wheel_changed_during_validation")
        return _result(
            kind=kind,
            expected_distribution=expected_distribution,
            expected_version=expected_version,
            wheel_filename=wheel_filename,
            observed=observed,
        )
    except _ArtifactInvalid as exc:
        fallback_kind = artifact_kind if isinstance(artifact_kind, WheelArtifactKind) else WheelArtifactKind.BASE
        return _result(
            kind=fallback_kind,
            expected_distribution=str(expected_distribution or "").strip(),
            expected_version=str(expected_version or "").strip(),
            wheel_filename=(Path(wheel_path).name if isinstance(wheel_path, (str, Path)) else ""),
            observed=observed,
            blocker=exc.blocker,
        )
    except Exception:
        fallback_kind = artifact_kind if isinstance(artifact_kind, WheelArtifactKind) else WheelArtifactKind.BASE
        return _result(
            kind=fallback_kind,
            expected_distribution=str(expected_distribution or "").strip(),
            expected_version=str(expected_version or "").strip(),
            wheel_filename=(Path(wheel_path).name if isinstance(wheel_path, (str, Path)) else ""),
            observed=observed,
            blocker="wheel_artifact_validation_error",
        )


__all__ = [
    "BASE_BUILD_PROVENANCE_SCHEMA_ID",
    "LICENSE_DETERMINATION_SCHEMA_ID",
    "MAX_SBOM_BYTES",
    "MAX_WHEEL_ARCHIVE_BYTES",
    "MAX_WHEEL_CONTROL_FILE_BYTES",
    "MAX_WHEEL_MEMBER_BYTES",
    "MAX_WHEEL_MEMBER_COUNT",
    "MAX_WHEEL_UNCOMPRESSED_BYTES",
    "NATIVE_BUILD_PROVENANCE_SCHEMA_ID",
    "SOURCE_PROVENANCE_SCHEMA_ID",
    "WHEEL_ARTIFACT_VALIDATION_SCHEMA_ID",
    "WheelArtifactKind",
    "WheelArtifactValidationResult",
    "validate_wheel_artifact",
]
