#!/usr/bin/env python3
"""Verify the merge-anchored archive for native fixed64 CPU profile v5."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import NoReturn


PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_fixed64_cpu_profile_v5.json")
ARCHIVE_RELATIVE_PATH = Path(
    "config/engine_v2_native_fixed64_cpu_profile_v5_archive.json"
)
PROFILE_ID = "engine_v2_native_fixed64_cpu_synthetic_v5"
PROFILE_SHA256 = "f5b3f288b432a15a1382a175b70821c1c57e8d41a986de2dea8898712374aece"
ARCHIVE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_cpu_profile_archive/1.0.0"
)
MERGE_COMMIT_OID = "50c6a0e633b6edc90a5e4fae3d7740c5957816ea"
REVIEWED_HEAD_OID = "9d4f275cf6bd72798cad2562346ea81718859514"
TRANSITIVE_SOURCE_MANIFEST_SHA256 = (
    "3bfff31c5f5cf006a2031448f134a34a74bb4fef498145ef552ce839b6b93d2f"
)
FALSE_AUTHORITY_KEYS = {
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
}


class NativeFixed64CPUProfileV5ArchiveError(ValueError):
    """The immutable v5 archive failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUProfileV5ArchiveError(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")


def _load_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("ascii"),
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUProfileV5ArchiveError(
            f"{label} is not canonical ASCII JSON"
        ) from exc
    if type(value) is not dict or raw != _canonical_bytes(value):
        _fail(f"{label} canonical serialization changed")
    return value


def require_archived_profile_v5(
    profile_raw: bytes, archive_raw: bytes
) -> dict[str, object]:
    profile = _load_canonical_object(profile_raw, label="v5 profile")
    archive = _load_canonical_object(archive_raw, label="v5 archive")
    profile_sha256 = hashlib.sha256(profile_raw).hexdigest()
    if profile_sha256 != PROFILE_SHA256:
        _fail("v5 profile bytes changed from the merge-anchored identity")
    if (
        profile.get("profile_id") != PROFILE_ID
        or profile.get("schema_id")
        != "betelgeuze.engine_v2_native_fixed64_cpu_profile/5.0.0"
        or profile.get("status")
        != "implementation_profile_frozen_execution_not_consumed"
    ):
        _fail("v5 profile identity or terminal state changed")
    profile_authority = profile.get("authority")
    if (
        type(profile_authority) is not dict
        or set(profile_authority) != FALSE_AUTHORITY_KEYS
        or any(value is not False for value in profile_authority.values())
    ):
        _fail("v5 profile authority is not entirely false")

    if set(archive) != {
        "authority",
        "execution_consumed",
        "implementation_main_commit_oid",
        "profile_id",
        "profile_sha256",
        "reservation_created",
        "review",
        "schema_id",
        "status",
        "transitive_source_count",
        "transitive_source_manifest_sha256",
    }:
        _fail("v5 archive field set changed")
    authority = archive["authority"]
    review = archive["review"]
    if (
        type(authority) is not dict
        or set(authority) != FALSE_AUTHORITY_KEYS
        or any(value is not False for value in authority.values())
        or type(review) is not dict
        or review
        != {
            "required_checks_success": 95,
            "reviewed_head_oid": REVIEWED_HEAD_OID,
            "unresolved_review_threads": 0,
        }
        or archive["execution_consumed"] is not False
        or archive["reservation_created"] is not False
        or archive["implementation_main_commit_oid"] != MERGE_COMMIT_OID
        or archive["profile_id"] != PROFILE_ID
        or archive["profile_sha256"] != profile_sha256
        or archive["schema_id"] != ARCHIVE_SCHEMA_ID
        or archive["status"] != "archived_frozen_superseded_by_v6_activation"
        or type(archive["transitive_source_count"]) is not int
        or archive["transitive_source_count"] != 187
        or archive["transitive_source_manifest_sha256"]
        != TRANSITIVE_SOURCE_MANIFEST_SHA256
        or re.fullmatch(r"[0-9a-f]{40}", str(archive["implementation_main_commit_oid"]))
        is None
    ):
        _fail("v5 archive evidence changed")
    return archive


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    archive_raw = (root / ARCHIVE_RELATIVE_PATH).read_bytes()
    archive = require_archived_profile_v5(profile_raw, archive_raw)
    print(
        json.dumps(
            {
                "all_authority_false": True,
                "archived": True,
                "compiled_profile_binding_verified": False,
                "execution_consumed": False,
                "implementation_main_commit_oid": archive[
                    "implementation_main_commit_oid"
                ],
                "profile_id": PROFILE_ID,
                "profile_sha256": PROFILE_SHA256,
                "reservation_created": False,
                "status": archive["status"],
            },
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
