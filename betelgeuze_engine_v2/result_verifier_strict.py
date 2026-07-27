"""Strict public wrapper for canonical CLI result verification.

The base verifier reconstructs every currently expandable receipt. This wrapper
adds the cross-link whose source projection is not fully reconstructible: the
interpretable result's retained generic-search fingerprint must equal both the
placement-search fingerprint and the expanded generic search-result fingerprint.

The historical ``DockingSearchResult.to_dict`` surface predates an explicit
schema identifier, calls the selected-row count ``top_count``, and calls the
per-row pose flag ``pose_valid``. Verification normalizes only those legacy
presentation details in an isolated copy. The stored document, its top-level
SHA, nested receipts, rows, scores, identities, and claim flags are never
rewritten or trusted from the normalized copy.

The generic search fingerprint remains cross-linked rather than recomputed,
because the public search-result document does not expand symmetry mappings.
"""

from __future__ import annotations

import json
from typing import Mapping

from . import result_verifier as _base


STRICT_CLI_RESULT_VERIFICATION_SCHEMA_ID = (
    "betelgeuze.engine_v2_strict_cli_result_verification/1.0.0"
)
LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID = (
    "betelgeuze.engine_v2_docking_search_result/1.0.0"
)


CliResultVerificationError = _base.CliResultVerificationError
CliResultVerificationReceipt = _base.CliResultVerificationReceipt


_ORIGINAL_VERIFY_GENERIC_SEARCH = _base._verify_generic_search


def _require_mapping(value: object, *, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise CliResultVerificationError(f"{name} must be a JSON object")
    return value


def _verify_legacy_generic_search(document: object) -> dict[str, object]:
    """Verify the historical public result without mutating signed evidence."""

    original = _require_mapping(document, name="generic search result")
    generic = dict(original)
    schema_id = generic.get("schema_id")
    if schema_id not in {None, LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID}:
        raise CliResultVerificationError(
            "generic search-result schema is unsupported"
        )
    if schema_id is None:
        generic["schema_id"] = LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID

    top_count = generic.get("top_count")
    selected_count = generic.get("selected_count")
    if selected_count is None:
        generic["selected_count"] = top_count
    elif top_count is not None and selected_count != top_count:
        raise CliResultVerificationError(
            "generic top_count and selected_count disagree"
        )

    original_rows = generic.get("rows")
    if not isinstance(original_rows, list):
        raise CliResultVerificationError(
            "generic search rows must be a JSON array"
        )
    normalized_rows: list[object] = []
    for raw_row in original_rows:
        if not isinstance(raw_row, dict):
            raise CliResultVerificationError(
                "generic search row must be a JSON object"
            )
        row = dict(raw_row)
        pose_valid = row.get("pose_valid")
        legacy_valid_pose = row.get("valid_pose")
        if legacy_valid_pose is None:
            row["valid_pose"] = pose_valid
        elif pose_valid is not None and legacy_valid_pose != pose_valid:
            raise CliResultVerificationError(
                "generic pose_valid and valid_pose disagree"
            )
        normalized_rows.append(row)
    generic["rows"] = normalized_rows

    if generic.get("claim_safe") is not False:
        raise CliResultVerificationError(
            "generic search result must retain claim_safe=false"
        )
    # These promotion flags were historically carried by the authenticated
    # wrapper rather than the expanded generic result. Supply their required
    # false values only to the base structural verifier's temporary copy.
    generic.setdefault("scientifically_validated", False)
    generic.setdefault("product_qualified", False)
    generic.setdefault("customer_execution_enabled", False)

    verified = _ORIGINAL_VERIFY_GENERIC_SEARCH(generic)
    # Downstream receipt checks hash the exact historical row documents. Restore
    # the original rows after structural count validation on the normalized copy.
    verified["rows"] = original_rows
    verified["document"] = original
    return verified


# The base verification call resolves this module global dynamically. Installing
# one idempotent compatibility boundary keeps direct strict calls and byte calls
# on the same validation path without altering the evidence document.
if getattr(_base, "_strict_generic_search_compat_installed", False) is False:
    _base._verify_generic_search = _verify_legacy_generic_search
    _base._strict_generic_search_compat_installed = True


def _verify_generic_search_crosslink(document: Mapping[str, object]) -> None:
    cli_result = _require_mapping(document, name="CLI docking result")
    interpreted = _require_mapping(
        cli_result.get("result"),
        name="interpretable scored search result",
    )
    placement = _require_mapping(
        interpreted.get("placement_search_result"),
        name="placement search result",
    )
    authenticated = _require_mapping(
        placement.get("search"),
        name="authenticated search result",
    )
    generic = _require_mapping(
        authenticated.get("search_result"),
        name="generic search result",
    )
    interpreted_fingerprint = _base._require_sha256(
        interpreted.get("generic_search_fingerprint_sha256"),
        name="interpretable generic-search fingerprint",
    )
    placement_fingerprint = _base._require_sha256(
        placement.get("search_fingerprint_sha256"),
        name="placement generic-search fingerprint",
    )
    expanded_fingerprint = _base._require_sha256(
        generic.get("search_fingerprint_sha256"),
        name="expanded generic-search fingerprint",
    )
    if len(
        {
            interpreted_fingerprint,
            placement_fingerprint,
            expanded_fingerprint,
        }
    ) != 1:
        raise CliResultVerificationError(
            "generic search fingerprint cross-link is inconsistent"
        )


def verify_canonical_cli_result_document(
    document: Mapping[str, object],
) -> CliResultVerificationReceipt:
    _verify_generic_search_crosslink(document)
    return _base.verify_canonical_cli_result_document(document)


def verify_canonical_cli_result_bytes(
    raw: bytes,
) -> CliResultVerificationReceipt:
    receipt = _base.verify_canonical_cli_result_bytes(raw)
    canonical = raw[:-1] if raw.endswith(b"\n") else raw
    document = json.loads(
        canonical.decode("ascii"),
        object_pairs_hook=_base._reject_duplicate_pairs,
    )
    _verify_generic_search_crosslink(
        _base._require_dict(document, name="CLI docking result")
    )
    return receipt


__all__ = [
    "LEGACY_GENERIC_SEARCH_RESULT_SCHEMA_ID",
    "STRICT_CLI_RESULT_VERIFICATION_SCHEMA_ID",
    "CliResultVerificationError",
    "CliResultVerificationReceipt",
    "verify_canonical_cli_result_bytes",
    "verify_canonical_cli_result_document",
]
