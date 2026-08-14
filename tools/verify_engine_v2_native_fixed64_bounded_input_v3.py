#!/usr/bin/env python3
"""Verify the fail-closed native fixed64 bounded-input v3 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_native_fixed64_bounded_input_v3.json"
)
DEFAULT_RUST_SOURCE = (
    REPOSITORY_ROOT / "rust_engine_v2/src/complete_fixed64_pipeline.rs"
)
DEFAULT_PYTHON_CONSUMER = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/native_fixed64_consumers.py"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_native_fixed64_bounded_input_v3.md"
)

EXPECTED_AUTHORITY_FIELDS = frozenset(
    {
        "benchmark_execution_authorized",
        "customer_pose_emission_authorized",
        "existing_rank_auto_change_authorized",
        "molecular_execution_authorized",
        "production_claim_authorized",
        "reservation_authorized",
        "scientific_claim_authorized",
    }
)
EXPECTED_LIMITS = {
    "candidate_denominator": 64,
    "conformer_source_count": 7,
    "exact_cartesian_pair_count": 2_097_152,
    "feature_atom_indices_per_row": 4_096,
    "feature_geometry_row_count": 3_072,
    "ligand_atom_count": 512,
    "prepared_input_scalar_count": 8_388_608,
    "receptor_atom_count": 4_096,
    "retained_source_count": 4,
    "v7_control_source_count": 24,
}
INPUT_SCHEMA_ID = "betelgeuze.engine_v2_native_fixed64_complete_input/3.0.0"
EVIDENCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_complete_python_evidence/3.0.0"
)
PROJECTION_DOMAIN = "betelgeuze.engine-v2.native-fixed64-prepared-input-projection/v1"
RECEIPT_DOMAIN = "betelgeuze.engine-v2.native-fixed64-prepared-input-receipt/v1"


class ContractError(RuntimeError):
    """The bounded-input contract or its source binding failed closed."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ContractError(f"contract is unavailable: {path}") from exc
    try:
        document = json.loads(raw, object_pairs_hook=_pairs_no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError("contract is not valid UTF-8 JSON") from exc
    if type(document) is not dict:
        raise ContractError("contract must be an object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if raw != canonical:
        raise ContractError("contract JSON is not canonical pretty ASCII")
    return document, raw


def _read_text(path: Path, *, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"{label} is unavailable or not UTF-8: {path}") from exc


def _require_exact_keys(
    value: object, expected: set[str], *, label: str
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise ContractError(f"{label} key schema changed")
    return value


def _require_snippets(source: str, snippets: tuple[str, ...], *, label: str) -> None:
    missing = [snippet for snippet in snippets if snippet not in source]
    if missing:
        raise ContractError(f"{label} is missing frozen contract snippets: {missing}")


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    rust_source_path: Path = DEFAULT_RUST_SOURCE,
    python_consumer_path: Path = DEFAULT_PYTHON_CONSUMER,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
) -> dict[str, object]:
    document, raw = _read_json(contract_path)
    _require_exact_keys(
        document,
        {
            "authority",
            "canonical_entrypoint",
            "compatibility",
            "evidence_schema_id",
            "input_schema_id",
            "limits",
            "receipt_domains",
            "schema_id",
            "status",
        },
        label="contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_native_fixed64_bounded_input_contract/1.0.0"
        or document["status"] != "synthetic_test_only_authority_false"
        or document["canonical_entrypoint"] != "native_fixed64_complete_pipeline_v3"
        or document["input_schema_id"] != INPUT_SCHEMA_ID
        or document["evidence_schema_id"] != EVIDENCE_SCHEMA_ID
    ):
        raise ContractError("contract identity or status changed")
    compatibility = _require_exact_keys(
        document["compatibility"], {"v1", "v2", "v3"}, label="compatibility"
    )
    if compatibility != {
        "v1": "retired",
        "v2": "historical_receipt_compatible",
        "v3": "canonical_synthetic_transport",
    }:
        raise ContractError("compatibility policy changed")
    limits = _require_exact_keys(
        document["limits"], set(EXPECTED_LIMITS), label="limits"
    )
    if limits != EXPECTED_LIMITS or any(
        type(value) is not int for value in limits.values()
    ):
        raise ContractError("bounded-input limits changed")
    authority = _require_exact_keys(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError(
            "bounded-input contract acquired execution or claim authority"
        )
    receipts = _require_exact_keys(
        document["receipt_domains"],
        {
            "consumer_identity_in_prepared_projection",
            "nul_terminated",
            "prepared_input_projection",
            "prepared_input_receipt",
            "prepared_input_receipt_binds_pipeline_batch_receipt",
        },
        label="receipt_domains",
    )
    if receipts != {
        "consumer_identity_in_prepared_projection": False,
        "nul_terminated": True,
        "prepared_input_projection": PROJECTION_DOMAIN,
        "prepared_input_receipt": RECEIPT_DOMAIN,
        "prepared_input_receipt_binds_pipeline_batch_receipt": True,
    }:
        raise ContractError("prepared-input receipt policy changed")

    rust_source = _read_text(rust_source_path, label="Rust complete pipeline source")
    _require_snippets(
        rust_source,
        (
            INPUT_SCHEMA_ID,
            EVIDENCE_SCHEMA_ID,
            "native_fixed64_complete_pipeline_v3",
            "const MAX_V7_CONTROL_SOURCES: usize = 24;",
            "const MAX_CONFORMER_SOURCES: usize = 7;",
            "const MAX_RETAINED_SOURCES: usize = 4;",
            "const MAX_ATOMIC_FEATURES: usize = 12 * 256;",
            "const MAX_PREPARED_INPUT_SCALAR_COUNT: usize = 8 * 1_024 * 1_024;",
            f'{PROJECTION_DOMAIN}\\0"',
            f'{RECEIPT_DOMAIN}\\0"',
            "bounded_prepared_input_preflight(input)",
            "prepared_input_receipt_sha256(",
        ),
        label="Rust complete pipeline source",
    )
    python_source = _read_text(python_consumer_path, label="Python native consumer")
    _require_snippets(
        python_source,
        (
            INPUT_SCHEMA_ID,
            EVIDENCE_SCHEMA_ID,
            'name = "native_fixed64_complete_pipeline_v3"',
            RECEIPT_DOMAIN,
            "_PREPARED_INPUT_SCALAR_LIMIT = 8 * 1_024 * 1_024",
            "_COMPLETE_INPUT_KEY_COUNT = 53",
            "payload = input_document.copy()",
            "NativeFixed64EvidenceV3",
        ),
        label="Python native consumer",
    )
    documentation = _read_text(documentation_path, label="bounded-input documentation")
    _require_snippets(
        documentation,
        (
            "native_fixed64_complete_pipeline_v3",
            "8,388,608",
            "External authority must reach blocker zero",
        ),
        label="bounded-input documentation",
    )
    return {
        "all_authority_false": True,
        "canonical_entrypoint": document["canonical_entrypoint"],
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "evidence_schema_id": EVIDENCE_SCHEMA_ID,
        "input_schema_id": INPUT_SCHEMA_ID,
        "limits": limits,
        "status": "verified_static_non_authoritative",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--rust-source", type=Path, default=DEFAULT_RUST_SOURCE)
    parser.add_argument("--python-consumer", type=Path, default=DEFAULT_PYTHON_CONSUMER)
    parser.add_argument("--documentation", type=Path, default=DEFAULT_DOCUMENTATION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify(
            contract_path=args.contract,
            rust_source_path=args.rust_source,
            python_consumer_path=args.python_consumer,
            documentation_path=args.documentation,
        )
    except ContractError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
