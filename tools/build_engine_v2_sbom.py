#!/usr/bin/env python3
"""Generate a deterministic SPDX 2.3 JSON SBOM for an Engine v2 wheel."""

from __future__ import annotations

import argparse
import email
import hashlib
import json
from pathlib import Path
import re
import zipfile

SPDX_VERSION = "SPDX-2.3"
DATA_LICENSE = "CC0-1.0"


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


def _dependency_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise RuntimeError(f"cannot parse Requires-Dist value: {requirement!r}")
    return match.group(1).lower().replace("_", "-")


def build_sbom(wheel: Path) -> dict[str, object]:
    metadata = _metadata_from_wheel(wheel)
    name = str(metadata.get("Name", "")).strip()
    version = str(metadata.get("Version", "")).strip()
    if not name or not version:
        raise RuntimeError("wheel metadata is missing Name or Version")
    wheel_sha256 = _sha256(wheel)
    namespace = f"https://betelgeuze.invalid/spdx/{name}/{version}/{wheel_sha256}"
    root_spdx_id = "SPDXRef-Package-EngineV2"
    packages: list[dict[str, object]] = [
        {
            "SPDXID": root_spdx_id,
            "name": name,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "checksums": [
                {"algorithm": "SHA256", "checksumValue": wheel_sha256}
            ],
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{name}@{version}",
                }
            ],
        }
    ]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_spdx_id,
        }
    ]
    for index, requirement in enumerate(sorted(metadata.get_all("Requires-Dist", []))):
        dependency = _dependency_name(requirement)
        spdx_id = f"SPDXRef-Dependency-{index + 1}"
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": dependency,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "comment": f"Declared requirement: {requirement}",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{dependency}",
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": root_spdx_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
        )
    return {
        "spdxVersion": SPDX_VERSION,
        "dataLicense": DATA_LICENSE,
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}-sbom",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": "2025-01-01T00:00:00Z",
            "creators": ["Tool: betelgeuze-engine-v2-sbom/1.0.0"],
            "licenseListVersion": "3.25",
        },
        "packages": packages,
        "relationships": relationships,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    wheel = Path(args.wheel).resolve(strict=True)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_sbom(wheel)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
