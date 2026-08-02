#!/usr/bin/env python3
"""Generate a fail-closed SPDX 2.3 SBOM for an exact Engine v2 wheel.

The generator refuses to create an admission-capable SBOM unless it can bind
every base-wheel payload byte to the source tree, or a native wheel to its
Cargo.lock, complete native source inventory, and an external build-provenance
receipt.  A reviewed, exact license-determination ledger is mandatory for the
root package and every declared/transitive dependency.
"""

from __future__ import annotations

import argparse
import email
import hashlib
import json
from pathlib import Path
import zipfile

from betelgeuze_engine_v2.benchmark.wheel_artifact import (
    _ArtifactInvalid,
    _canonical_bytes,
    _canonical_dependency_name,
    _cargo_dependency_packages,
    _expected_license_keys,
    _LICENSE_ANNOTATION_PREFIX,
    _load_license_determinations,
    _load_native_build_provenance,
    _NATIVE_ANNOTATION_PREFIX,
    _parse_cargo_lock,
    _parse_metadata_requirements,
    _pypi_dependency_packages,
    _SOURCE_ANNOTATION_PREFIX,
    _sha256_bytes,
    _source_file_inventory,
    _source_file_spdx_id,
    _source_provenance,
    _wheel_file_spdx_id,
    SOURCE_PROVENANCE_SCHEMA_ID,
    WheelArtifactKind,
)

SPDX_VERSION = "SPDX-2.3"
DATA_LICENSE = "CC0-1.0"
SBOM_TOOL = "Tool: betelgeuze-engine-v2-sbom/2.0.0"
SBOM_CREATED = "2025-01-01T00:00:00Z"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_from_wheel(path: Path) -> email.message.Message:
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise RuntimeError("wheel must contain exactly one METADATA file")
        raw = archive.read(names[0])
    return email.message_from_bytes(raw)


def _wheel_file_inventory(path: Path) -> dict[str, tuple[str, int]]:
    """Return a deterministic SHA-256/size inventory of every wheel file."""

    with zipfile.ZipFile(path) as archive:
        infos = tuple(info for info in archive.infolist() if not info.is_dir())
        names = tuple(info.filename for info in infos)
        if not names or len(names) != len(set(names)):
            raise RuntimeError("wheel file inventory is empty or contains duplicates")
        return {
            info.filename: (hashlib.sha256(archive.read(info)).hexdigest(), info.file_size)
            for info in sorted(infos, key=lambda value: value.filename)
        }


def _annotation(comment: str) -> dict[str, str]:
    return {
        "annotationDate": SBOM_CREATED,
        "annotationType": "OTHER",
        "annotator": SBOM_TOOL,
        "comment": comment,
    }


def build_sbom(
    wheel: Path,
    *,
    source_root: Path | None = None,
    license_determination: Path | None = None,
    cargo_lock: Path | None = None,
    native_build_provenance: Path | None = None,
    source_receipt_sha256: str = "",
) -> dict[str, object]:
    """Build an exact SPDX document or fail if an authority input is absent."""

    if source_root is None:
        raise RuntimeError("source_root is required for source-to-wheel provenance")
    if license_determination is None:
        raise RuntimeError("license_determination is required for legal closure")
    if len(source_receipt_sha256) != 64 or any(value not in "0123456789abcdef" for value in source_receipt_sha256):
        raise RuntimeError("source_receipt_sha256 must be an exact lowercase SHA-256")
    metadata = _metadata_from_wheel(wheel)
    name = str(metadata.get("Name", "")).strip()
    version = str(metadata.get("Version", "")).strip()
    if not name or not version:
        raise RuntimeError("wheel metadata is missing Name or Version")
    try:
        requirements = _parse_metadata_requirements(metadata)
        wheel_sha256 = _sha256(wheel)
        wheel_inventory = _wheel_file_inventory(wheel)
        payload_members = {member: value for member, value in wheel_inventory.items() if ".dist-info/" not in member}
        if not payload_members:
            raise RuntimeError("wheel contains no package payload")
        extensions = tuple(member for member in payload_members if member.lower().endswith((".so", ".pyd")))
        kind = WheelArtifactKind.NATIVE if extensions else WheelArtifactKind.BASE
        if kind is WheelArtifactKind.NATIVE and len(extensions) != 1:
            raise RuntimeError("native wheel must contain exactly one extension")
        if kind is WheelArtifactKind.BASE and (cargo_lock is not None or native_build_provenance is not None):
            raise RuntimeError("base wheel cannot carry native build provenance")

        pypi_dependencies = _pypi_dependency_packages(requirements)
        cargo_dependencies = ()
        root_dependency_ids: tuple[str, ...] = ()
        cargo_lock_sha256 = ""
        if kind is WheelArtifactKind.NATIVE:
            if cargo_lock is None:
                raise RuntimeError("cargo_lock is required for a native wheel")
            cargo_packages, cargo_lock_sha256 = _parse_cargo_lock(cargo_lock)
            cargo_dependencies, root_dependency_ids = _cargo_dependency_packages(
                cargo_packages,
                root_distribution=name,
                root_version=version,
            )
        dependencies = tuple((*pypi_dependencies, *cargo_dependencies))
        license_keys = _expected_license_keys(
            distribution=name,
            version=version,
            dependencies=dependencies,
        )
        license_rows, extracted_licenses, license_sha256 = _load_license_determinations(
            license_determination,
            expected_package_keys=license_keys,
        )
        source_inventory, generated_from = _source_file_inventory(
            source_root,
            kind=kind,
            payload_members=payload_members,
        )
        native_build_sha256 = ""
        if kind is WheelArtifactKind.NATIVE:
            if cargo_lock is None or native_build_provenance is None:
                raise RuntimeError("native_build_provenance is required for a native wheel")
            if cargo_lock.resolve(strict=True) != (source_root / "Cargo.lock").resolve(strict=True):
                raise RuntimeError("Cargo.lock is not bound to the native source root")
            extension_member = extensions[0]
            native_build_sha256 = _load_native_build_provenance(
                native_build_provenance,
                wheel_sha256=wheel_sha256,
                extension_member=extension_member,
                extension_sha256=payload_members[extension_member][0],
                cargo_lock_sha256=cargo_lock_sha256,
                source_inventory=source_inventory,
                source_receipt_sha256=source_receipt_sha256,
            )
        source_provenance = _source_provenance(
            kind=kind,
            payload_members=payload_members,
            source_inventory=source_inventory,
            mappings=generated_from,
            source_receipt_sha256=source_receipt_sha256,
            cargo_lock_sha256=cargo_lock_sha256,
            native_build_provenance_sha256=native_build_sha256,
        )
    except _ArtifactInvalid as exc:
        raise RuntimeError(f"cannot build admission SBOM: {exc.blocker}") from exc

    namespace = f"https://betelgeuze.invalid/spdx/{name}/{version}/{wheel_sha256}"
    root_id = "SPDXRef-Package-EngineV2"
    source_id = "SPDXRef-Package-Source"
    root_license_key = f"pypi:{_canonical_dependency_name(name)}@{version}"
    root_license = license_rows[root_license_key]

    def license_fields(package_key: str) -> dict[str, str]:
        row = license_rows[package_key]
        return {
            "licenseConcluded": row.license_concluded,
            "licenseDeclared": row.license_declared,
            "copyrightText": row.copyright_text,
        }

    source_inventory_sha256 = _sha256_bytes(_canonical_bytes(dict(sorted(source_inventory.items()))))
    packages: list[dict[str, object]] = [
        {
            "SPDXID": root_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
            **license_fields(root_license_key),
            "checksums": [{"algorithm": "SHA256", "checksumValue": wheel_sha256}],
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{name}@{version}",
                }
            ],
            "comment": f"License determination evidence: {root_license.evidence}",
        },
        {
            "SPDXID": source_id,
            "name": f"{name}-source",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": True,
            **license_fields(root_license_key),
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
        determination = license_rows[dependency.license_key]
        package: dict[str, object] = {
            "SPDXID": dependency.spdx_id,
            "name": dependency.name,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            **license_fields(dependency.license_key),
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
        packages.append(package)

    files: list[dict[str, object]] = []
    for file_name, (file_sha256, _) in sorted(wheel_inventory.items()):
        files.append(
            {
                "SPDXID": _wheel_file_spdx_id(file_name),
                "fileName": file_name,
                "checksums": [{"algorithm": "SHA256", "checksumValue": file_sha256}],
                "licenseConcluded": root_license.license_concluded,
                "copyrightText": root_license.copyright_text,
            }
        )
    for source_name, source_sha256 in sorted(source_inventory.items()):
        files.append(
            {
                "SPDXID": _source_file_spdx_id(source_name),
                "fileName": f"source/{source_name}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": source_sha256}],
                "licenseConcluded": root_license.license_concluded,
                "copyrightText": root_license.copyright_text,
            }
        )

    relationships: list[dict[str, str]] = [
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
    relationships.extend(
        {
            "spdxElementId": root_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": _wheel_file_spdx_id(file_name),
        }
        for file_name in sorted(wheel_inventory)
    )
    relationships.extend(
        {
            "spdxElementId": source_id,
            "relationshipType": "CONTAINS",
            "relatedSpdxElement": _source_file_spdx_id(source_name),
        }
        for source_name in sorted(source_inventory)
    )
    relationships.extend(
        {
            "spdxElementId": _wheel_file_spdx_id(mapping["wheel_member"]),
            "relationshipType": "GENERATED_FROM",
            "relatedSpdxElement": _source_file_spdx_id(mapping["source_path"]),
        }
        for mapping in source_provenance["generated_from"]  # type: ignore[index]
    )
    if native_build_sha256:
        relationships.extend(
            {
                "spdxElementId": _wheel_file_spdx_id(file_name),
                "relationshipType": "GENERATED_FROM",
                "relatedSpdxElement": source_id,
            }
            for file_name in sorted(payload_members)
        )
    pypi_dependency_ids = {row.spdx_id for row in dependencies if row.spdx_id.startswith("SPDXRef-PyPI-")}
    relationships.extend(
        {
            "spdxElementId": root_id,
            "relationshipType": "DEPENDS_ON",
            "relatedSpdxElement": dependency_id,
        }
        for dependency_id in sorted({*root_dependency_ids, *pypi_dependency_ids})
    )
    for dependency in dependencies:
        relationships.extend(
            {
                "spdxElementId": dependency.spdx_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
            for dependency_id in dependency.dependency_ids
        )
    relationships.sort(
        key=lambda row: (
            row["spdxElementId"],
            row["relationshipType"],
            row["relatedSpdxElement"],
        )
    )

    source_provenance_sha256 = _sha256_bytes(_canonical_bytes(source_provenance))
    annotations = [
        _annotation(f"{_SOURCE_ANNOTATION_PREFIX}{source_provenance_sha256}"),
        _annotation(f"{_LICENSE_ANNOTATION_PREFIX}{license_sha256}"),
    ]
    if native_build_sha256:
        annotations.append(_annotation(f"{_NATIVE_ANNOTATION_PREFIX}{native_build_sha256}"))
    result: dict[str, object] = {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": DATA_LICENSE,
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}-sbom",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": SBOM_CREATED,
            "creators": [SBOM_TOOL],
            "licenseListVersion": "3.25",
        },
        "packages": packages,
        "files": files,
        "relationships": relationships,
        "annotations": annotations,
    }
    if extracted_licenses:
        result["hasExtractedLicensingInfos"] = list(extracted_licenses)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--license-determination", required=True)
    parser.add_argument("--cargo-lock")
    parser.add_argument("--native-build-provenance")
    parser.add_argument("--source-receipt-sha256", required=True)
    args = parser.parse_args()
    wheel = Path(args.wheel).resolve(strict=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_sbom(
        wheel,
        source_root=Path(args.source_root).resolve(strict=True),
        license_determination=Path(args.license_determination).resolve(strict=True),
        cargo_lock=(None if args.cargo_lock is None else Path(args.cargo_lock).resolve(strict=True)),
        native_build_provenance=(
            None if args.native_build_provenance is None else Path(args.native_build_provenance).resolve(strict=True)
        ),
        source_receipt_sha256=args.source_receipt_sha256,
    )
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
