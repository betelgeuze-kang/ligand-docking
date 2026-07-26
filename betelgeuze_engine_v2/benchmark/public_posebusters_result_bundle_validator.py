"""Fail-closed validator for a published PoseBusters result bundle.

Every stage of the internal cohort already writes its own canonical receipt,
but nothing checked that a *published set* of those receipts is complete and
internally consistent.  A bundle could omit a stage, mix receipts from two
different archive intakes, or pair an oracle receipt with a stratification
receipt that measured a different oracle.

This module validates one bundle manifest.  Every required role must be
present exactly once, every receipt must self-authenticate against its pinned
digest, every declared upstream link must resolve to the receipt actually in
the bundle, and every receipt must remain claim-closed.  Optional roles are
admitted only when the manifest lists them.

Validation is a structural completeness and linkage check.  It does not
re-execute physics, does not re-derive any metric, and does not review the
science, so a valid bundle stays claim-closed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any

from . import public_posebusters_corpus_audit as corpus_module
from . import public_posebusters_intake as intake_module
from . import public_posebusters_internal_execution as execution_module
from . import public_posebusters_internal_oracle_evaluation as oracle_module
from . import public_posebusters_internal_oracle_runtime_observation as runtime_module
from . import public_posebusters_internal_oracle_stratification as strata_module
from . import public_posebusters_internal_preparation as preparation_module
from . import public_posebusters_internal_rmsd_evaluation as rmsd_module
from . import public_posebusters_same_input_engine_comparison as comparison_module
from .public_posebusters_corpus_audit import (
    _canonical_bytes,
    _canonical_sha256,
    _source_file_sha256,
)
from .public_posebusters_intake import (
    PoseBustersArchiveIntakeError,
    _read_exact_regular_file,
)


POSEBUSTERS_RESULT_BUNDLE_MANIFEST_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_result_bundle_manifest/1.0.0"
)
POSEBUSTERS_RESULT_BUNDLE_VALIDATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_result_bundle_validation/1.0.0"
)
POSEBUSTERS_RESULT_BUNDLE_ROLE_SCHEMA_ID = (
    "betelgeuze.engine_v2_posebusters_result_bundle_role/1.0.0"
)
POSEBUSTERS_RESULT_BUNDLE_MAX_INPUT_BYTES = 64 * 1024 * 1024
POSEBUSTERS_RESULT_BUNDLE_MAX_MANIFEST_BYTES = 1024 * 1024
POSEBUSTERS_RESULT_BUNDLE_MAX_RECEIPT_BYTES = 8 * 1024 * 1024

POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES = (
    "archive_intake",
    "corpus_audit",
    "internal_preparation",
    "internal_execution",
    "internal_rmsd_evaluation",
    "internal_oracle_evaluation",
)
POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES = (
    "internal_oracle_runtime_observation",
    "internal_oracle_stratification",
    "same_input_engine_comparison",
)
POSEBUSTERS_RESULT_BUNDLE_ROLES = (
    *POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES,
    *POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES,
)

_ROLE_SCHEMA_IDS = {
    "archive_intake": intake_module.POSEBUSTERS_ARCHIVE_INTAKE_SCHEMA_ID,
    "corpus_audit": corpus_module.POSEBUSTERS_CORPUS_AUDIT_SCHEMA_ID,
    "internal_preparation": (
        preparation_module.POSEBUSTERS_INTERNAL_PREPARATION_SCHEMA_ID
    ),
    "internal_execution": execution_module.POSEBUSTERS_INTERNAL_EXECUTION_SCHEMA_ID,
    "internal_rmsd_evaluation": (
        rmsd_module.POSEBUSTERS_INTERNAL_RMSD_EVALUATION_SCHEMA_ID
    ),
    "internal_oracle_evaluation": (
        oracle_module.POSEBUSTERS_INTERNAL_ORACLE_EVALUATION_SCHEMA_ID
    ),
    "internal_oracle_runtime_observation": (
        runtime_module.POSEBUSTERS_INTERNAL_ORACLE_RUNTIME_OBSERVATION_SCHEMA_ID
    ),
    "internal_oracle_stratification": (
        strata_module.POSEBUSTERS_INTERNAL_ORACLE_STRATIFICATION_SCHEMA_ID
    ),
    "same_input_engine_comparison": (
        comparison_module.POSEBUSTERS_SAME_INPUT_ENGINE_COMPARISON_SCHEMA_ID
    ),
}

# (role, field, referenced role) linkage every present receipt must satisfy.
_ROLE_LINKS = (
    ("corpus_audit", "archive_intake_receipt_sha256", "archive_intake"),
    ("internal_preparation", "archive_intake_receipt_sha256", "archive_intake"),
    ("internal_preparation", "corpus_audit_receipt_sha256", "corpus_audit"),
    ("internal_execution", "preparation_receipt_sha256", "internal_preparation"),
    ("internal_rmsd_evaluation", "execution_receipt_sha256", "internal_execution"),
    ("internal_rmsd_evaluation", "archive_intake_receipt_sha256", "archive_intake"),
    (
        "internal_oracle_evaluation",
        "internal_rmsd_receipt_sha256",
        "internal_rmsd_evaluation",
    ),
    (
        "internal_oracle_evaluation",
        "internal_execution_receipt_sha256",
        "internal_execution",
    ),
    ("internal_oracle_evaluation", "archive_intake_receipt_sha256", "archive_intake"),
    (
        "internal_oracle_runtime_observation",
        "oracle_receipt_sha256",
        "internal_oracle_evaluation",
    ),
    (
        "internal_oracle_stratification",
        "oracle_receipt_sha256",
        "internal_oracle_evaluation",
    ),
    (
        "internal_oracle_stratification",
        "runtime_observation_receipt_sha256",
        "internal_oracle_runtime_observation",
    ),
    ("internal_oracle_stratification", "archive_intake_receipt_sha256", "archive_intake"),
    ("internal_oracle_stratification", "corpus_audit_receipt_sha256", "corpus_audit"),
    (
        "internal_oracle_stratification",
        "preparation_receipt_sha256",
        "internal_preparation",
    ),
    (
        "same_input_engine_comparison",
        "archive_intake_receipt_sha256",
        "archive_intake",
    ),
)

_ROLE_DEPENDENCIES = {
    "internal_oracle_stratification": ("internal_oracle_runtime_observation",),
}

POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION = {
    "schema_id": (
        "betelgeuze.engine_v2_posebusters_result_bundle_configuration/1.0.0"
    ),
    "required_roles": list(POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES),
    "optional_roles": list(POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES),
    "role_uniqueness_required": True,
    "receipt_self_authentication_required": True,
    "declared_upstream_link_resolution_required": True,
    "claim_closed_receipts_required": True,
    "unknown_role_rejected": True,
    "physics_reexecuted": False,
    "metrics_recomputed": False,
    "scientific_review_performed": False,
}
POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION_SHA256 = _canonical_sha256(
    POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION
)

POSEBUSTERS_RESULT_BUNDLE_BLOCKERS = (
    "bundle_validation_is_structural_not_scientific",
    "receipt_payload_physics_not_reexecuted_by_this_validator",
    "bundle_manifest_is_unsigned_operator_local_document",
    "independent_second_host_bundle_validation_missing",
    "independent_scientific_review_missing",
    "public_docking_benchmark_claim_not_authorized",
)

_RESULT_FLAGS = {
    "bundle_structurally_complete": True,
    "every_declared_link_resolved_within_the_bundle": True,
    "every_receipt_claim_closed": True,
    "physics_reexecuted": False,
    "metrics_recomputed": False,
    "bundle_manifest_signature_verified": False,
    "independent_external_bundle_validation_present": False,
    "benchmark_executed": False,
    "scientifically_validated": False,
    "claim_safe": False,
}

_LOWERCASE_SHA256 = frozenset("0123456789abcdef")


class PoseBustersResultBundleValidationError(ValueError):
    """A bundle manifest, receipt, linkage, or claim state is invalid."""


def _mapping(value: object, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PoseBustersResultBundleValidationError(f"{name} must be a mapping")
    return dict(value)


def _list(value: object, *, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PoseBustersResultBundleValidationError(f"{name} must be a list")
    return value


def _digest(value: object, *, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _LOWERCASE_SHA256 for character in value)
    ):
        raise PoseBustersResultBundleValidationError(
            f"{name} must be a lowercase SHA-256"
        )
    return value


def _text(value: object, *, name: str, maximum: int = 1024) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > maximum
        or any(character in "\r\n\x00" for character in value)
    ):
        raise PoseBustersResultBundleValidationError(
            f"{name} must be bounded single-line text"
        )
    return value


def _json_object_pairs(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PoseBustersResultBundleValidationError(
                "document contains a duplicate JSON key"
            )
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise PoseBustersResultBundleValidationError(
        f"document contains forbidden JSON constant {value}"
    )


def _load_canonical_document(
    path: str | os.PathLike[str],
    *,
    maximum_bytes: int,
    name: str,
) -> tuple[dict[str, Any], bytes]:
    try:
        source = _read_exact_regular_file(path, maximum_bytes=maximum_bytes)
        metadata = Path(path).stat(follow_symlinks=False)
    except (OSError, PoseBustersArchiveIntakeError) as exc:
        raise PoseBustersResultBundleValidationError(
            f"{name} could not be read securely"
        ) from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise PoseBustersResultBundleValidationError(
            f"{name} must be a bounded mode-0600 regular file"
        )
    try:
        raw = json.loads(
            source.decode("ascii"),
            object_pairs_hook=_json_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except PoseBustersResultBundleValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PoseBustersResultBundleValidationError(
            f"{name} is not canonical ASCII JSON"
        ) from exc
    if not isinstance(raw, dict) or source != _canonical_bytes(raw) + b"\n":
        raise PoseBustersResultBundleValidationError(
            f"{name} bytes are not canonical"
        )
    return dict(raw), source


def _load_bundle_receipt(
    path: str | os.PathLike[str],
    *,
    role: str,
    expected_receipt_sha256: str,
) -> tuple[dict[str, Any], str]:
    document, source = _load_canonical_document(
        path,
        maximum_bytes=POSEBUSTERS_RESULT_BUNDLE_MAX_INPUT_BYTES,
        name=f"{role} receipt",
    )
    payload = dict(document)
    receipt_sha = _digest(payload.pop("receipt_sha256", None), name=f"{role} receipt")
    if (
        document.get("schema_id") != _ROLE_SCHEMA_IDS[role]
        or _canonical_sha256(payload) != receipt_sha
        or receipt_sha != expected_receipt_sha256
    ):
        raise PoseBustersResultBundleValidationError(
            f"{role} receipt schema, digest, or pin is invalid"
        )
    for field in ("benchmark_executed", "scientifically_validated", "claim_safe"):
        if document.get(field) is not False:
            raise PoseBustersResultBundleValidationError(
                f"{role} receipt must keep {field}=false"
            )
    return document, hashlib.sha256(source).hexdigest()


def _source_members() -> tuple[tuple[str, str], ...]:
    return (
        (
            "posebusters_result_bundle_validator",
            _source_file_sha256(Path(__file__).resolve()),
        ),
    )


def _atomic_write_new(path: str | os.PathLike[str], source: bytes) -> Path:
    if len(source) > POSEBUSTERS_RESULT_BUNDLE_MAX_RECEIPT_BYTES:
        raise PoseBustersResultBundleValidationError(
            "bundle validation receipt exceeds its byte bound"
        )
    output = Path(path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=str(output.parent),
    )
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(source)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary_name, output, follow_symlinks=False)
        except FileExistsError as exc:
            raise PoseBustersResultBundleValidationError(
                "bundle validation output already exists"
            ) from exc
    finally:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


class PoseBustersResultBundleValidationReceipt:
    """Canonical, claim-closed structural validation of one result bundle."""

    __slots__ = ("_payload_bytes",)

    def __init__(self, payload: Mapping[str, Any]) -> None:
        if "receipt_sha256" in payload:
            raise PoseBustersResultBundleValidationError(
                "receipt payload cannot predefine its digest"
            )
        self._payload_bytes = _canonical_bytes(dict(payload))

    @property
    def fingerprint_sha256(self) -> str:
        return hashlib.sha256(self._payload_bytes).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self._payload_bytes)
        payload["receipt_sha256"] = self.fingerprint_sha256
        return payload

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_dict()) + b"\n"

    def write_json(self, output_path: str | os.PathLike[str]) -> Path:
        return _atomic_write_new(output_path, self.canonical_bytes())


def _manifest_entries(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_id") != POSEBUSTERS_RESULT_BUNDLE_MANIFEST_SCHEMA_ID:
        raise PoseBustersResultBundleValidationError(
            "unsupported bundle manifest schema"
        )
    entries = [
        _mapping(item, name="bundle manifest entry")
        for item in _list(manifest.get("receipts"), name="bundle manifest receipts")
    ]
    if not entries:
        raise PoseBustersResultBundleValidationError(
            "bundle manifest lists no receipts"
        )
    seen: set[str] = set()
    resolved: list[dict[str, Any]] = []
    for entry in entries:
        role = _text(entry.get("role"), name="bundle role", maximum=128)
        if role not in _ROLE_SCHEMA_IDS:
            raise PoseBustersResultBundleValidationError(
                f"bundle manifest declares unknown role {role}"
            )
        if role in seen:
            raise PoseBustersResultBundleValidationError(
                f"bundle manifest declares role {role} more than once"
            )
        seen.add(role)
        resolved.append(
            {
                "role": role,
                "relative_path": _text(
                    entry.get("relative_path"),
                    name="bundle relative path",
                ),
                "receipt_sha256": _digest(
                    entry.get("receipt_sha256"),
                    name=f"{role} manifest digest",
                ),
            }
        )
    missing = [
        role for role in POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES if role not in seen
    ]
    if missing:
        raise PoseBustersResultBundleValidationError(
            f"bundle manifest omits required role {missing[0]}"
        )
    for role, dependencies in _ROLE_DEPENDENCIES.items():
        if role in seen:
            for dependency in dependencies:
                if dependency not in seen:
                    raise PoseBustersResultBundleValidationError(
                        f"bundle role {role} requires {dependency}"
                    )
    resolved.sort(key=lambda row: row["role"])
    return resolved


def _resolve_bundle_path(bundle_root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PoseBustersResultBundleValidationError(
            "bundle relative path escapes the bundle root"
        )
    resolved = (bundle_root / candidate).resolve()
    try:
        resolved.relative_to(bundle_root.resolve())
    except ValueError as exc:
        raise PoseBustersResultBundleValidationError(
            "bundle relative path escapes the bundle root"
        ) from exc
    return resolved


def _build_validation(
    bundle_root: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    expected_manifest_sha256: str,
) -> PoseBustersResultBundleValidationReceipt:
    root = Path(bundle_root)
    if not root.is_dir() or root.is_symlink():
        raise PoseBustersResultBundleValidationError(
            "bundle root must be a non-symlink directory"
        )
    manifest, manifest_source = _load_canonical_document(
        manifest_path,
        maximum_bytes=POSEBUSTERS_RESULT_BUNDLE_MAX_MANIFEST_BYTES,
        name="bundle manifest",
    )
    manifest_sha = hashlib.sha256(manifest_source).hexdigest()
    if manifest_sha != _digest(expected_manifest_sha256, name="expected manifest"):
        raise PoseBustersResultBundleValidationError(
            "bundle manifest differs from its expected identity"
        )
    entries = _manifest_entries(manifest)
    receipts: dict[str, dict[str, Any]] = {}
    role_rows: list[dict[str, Any]] = []
    for entry in entries:
        role = entry["role"]
        path = _resolve_bundle_path(root, entry["relative_path"])
        document, file_sha = _load_bundle_receipt(
            path,
            role=role,
            expected_receipt_sha256=entry["receipt_sha256"],
        )
        receipts[role] = document
        role_rows.append(
            {
                "schema_id": POSEBUSTERS_RESULT_BUNDLE_ROLE_SCHEMA_ID,
                "role": role,
                "relative_path": entry["relative_path"],
                "receipt_schema_id": _ROLE_SCHEMA_IDS[role],
                "receipt_sha256": entry["receipt_sha256"],
                "receipt_file_sha256": file_sha,
                "required": role in POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES,
                "claim_closed": True,
            }
        )
    digests = {row["receipt_sha256"] for row in role_rows}
    if len(digests) != len(role_rows):
        raise PoseBustersResultBundleValidationError(
            "bundle roles must reference distinct receipts"
        )
    link_rows: list[dict[str, Any]] = []
    for role, field, referenced_role in _ROLE_LINKS:
        if role not in receipts or referenced_role not in receipts:
            continue
        declared = _digest(
            receipts[role].get(field),
            name=f"{role}.{field}",
        )
        expected = _digest(
            receipts[referenced_role].get("receipt_sha256"),
            name=f"{referenced_role} receipt",
        )
        if declared != expected:
            raise PoseBustersResultBundleValidationError(
                f"{role}.{field} does not reference the bundled {referenced_role}"
            )
        link_rows.append(
            {
                "role": role,
                "field": field,
                "referenced_role": referenced_role,
                "referenced_receipt_sha256": expected,
                "resolved_within_bundle": True,
            }
        )
    source_members = _source_members()
    payload = {
        "schema_id": POSEBUSTERS_RESULT_BUNDLE_VALIDATION_SCHEMA_ID,
        "status": "bundle_structurally_valid",
        "bundle_manifest_sha256": manifest_sha,
        "bundle_manifest_receipt_count": len(role_rows),
        "present_roles": [row["role"] for row in role_rows],
        "missing_optional_roles": [
            role
            for role in POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES
            if role not in receipts
        ],
        "role_rows": role_rows,
        "resolved_link_rows": link_rows,
        "resolved_link_count": len(link_rows),
        "archive_intake_receipt_sha256": _digest(
            receipts["archive_intake"].get("receipt_sha256"),
            name="archive intake receipt",
        ),
        "implementation_source_members": dict(source_members),
        "implementation_source_sha256": _canonical_sha256(dict(source_members)),
        "configuration": POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION,
        "configuration_sha256": POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION_SHA256,
        "scientific_blockers": list(POSEBUSTERS_RESULT_BUNDLE_BLOCKERS),
        **_RESULT_FLAGS,
    }
    return PoseBustersResultBundleValidationReceipt(payload)


def validate_posebusters_result_bundle(
    bundle_root: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    expected_manifest_sha256: str,
) -> PoseBustersResultBundleValidationReceipt:
    """Validate one published result bundle's completeness and linkage."""

    return _build_validation(
        bundle_root,
        manifest_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )


def verify_posebusters_result_bundle_validation_receipt(
    validation_receipt_path: str | os.PathLike[str],
    bundle_root: str | os.PathLike[str],
    manifest_path: str | os.PathLike[str],
    *,
    expected_validation_receipt_sha256: str,
    expected_manifest_sha256: str,
) -> PoseBustersResultBundleValidationReceipt:
    """Revalidate a bundle and require byte-exact receipt reconstruction."""

    document, source = _load_canonical_document(
        validation_receipt_path,
        maximum_bytes=POSEBUSTERS_RESULT_BUNDLE_MAX_RECEIPT_BYTES,
        name="bundle validation receipt",
    )
    if document.get("schema_id") != POSEBUSTERS_RESULT_BUNDLE_VALIDATION_SCHEMA_ID:
        raise PoseBustersResultBundleValidationError(
            "unsupported bundle validation schema"
        )
    expected = _build_validation(
        bundle_root,
        manifest_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if document.get("receipt_sha256") != _digest(
        expected_validation_receipt_sha256,
        name="expected validation receipt",
    ) or source != expected.canonical_bytes():
        raise PoseBustersResultBundleValidationError(
            "bundle validation receipt failed exact reconstruction"
        )
    return expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="betelgeuze-engine-v2-posebusters-validate-bundle",
        description=(
            "Validate a published PoseBusters result bundle for role "
            "completeness, receipt identity, and upstream linkage while "
            "keeping every scientific claim closed."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    verify = subparsers.add_parser("verify")
    for command in (validate, verify):
        command.add_argument("--bundle-root", required=True)
        command.add_argument("--manifest", required=True)
        command.add_argument("--expected-manifest-sha256", required=True)
    validate.add_argument("--output", required=True)
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--expected-validation-receipt-sha256", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        receipt = validate_posebusters_result_bundle(
            args.bundle_root,
            args.manifest,
            expected_manifest_sha256=args.expected_manifest_sha256,
        )
        receipt.write_json(args.output)
    else:
        receipt = verify_posebusters_result_bundle_validation_receipt(
            validation_receipt_path=args.receipt,
            bundle_root=args.bundle_root,
            manifest_path=args.manifest,
            expected_validation_receipt_sha256=(
                args.expected_validation_receipt_sha256
            ),
            expected_manifest_sha256=args.expected_manifest_sha256,
        )
    payload = receipt.to_dict()
    print(
        json.dumps(
            {
                "receipt_sha256": receipt.fingerprint_sha256,
                "status": payload["status"],
                "present_role_count": len(payload["present_roles"]),
                "resolved_link_count": payload["resolved_link_count"],
                "bundle_structurally_complete": True,
                "scientifically_validated": False,
                "claim_safe": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = [
    "POSEBUSTERS_RESULT_BUNDLE_BLOCKERS",
    "POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION",
    "POSEBUSTERS_RESULT_BUNDLE_CONFIGURATION_SHA256",
    "POSEBUSTERS_RESULT_BUNDLE_MANIFEST_SCHEMA_ID",
    "POSEBUSTERS_RESULT_BUNDLE_MAX_INPUT_BYTES",
    "POSEBUSTERS_RESULT_BUNDLE_MAX_MANIFEST_BYTES",
    "POSEBUSTERS_RESULT_BUNDLE_MAX_RECEIPT_BYTES",
    "POSEBUSTERS_RESULT_BUNDLE_OPTIONAL_ROLES",
    "POSEBUSTERS_RESULT_BUNDLE_REQUIRED_ROLES",
    "POSEBUSTERS_RESULT_BUNDLE_ROLES",
    "POSEBUSTERS_RESULT_BUNDLE_ROLE_SCHEMA_ID",
    "POSEBUSTERS_RESULT_BUNDLE_VALIDATION_SCHEMA_ID",
    "PoseBustersResultBundleValidationError",
    "PoseBustersResultBundleValidationReceipt",
    "main",
    "validate_posebusters_result_bundle",
    "verify_posebusters_result_bundle_validation_receipt",
]
