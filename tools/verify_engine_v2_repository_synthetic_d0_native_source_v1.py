#!/usr/bin/env python3
"""Verify the non-authoritative native repository synthetic-D0 source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
)
DEFAULT_CPU_PARITY_CONTRACT = (
    REPOSITORY_ROOT / "config/engine_v2_repository_synthetic_d0_cpu_parity_v1.json"
)
DEFAULT_RUST_SOURCE = (
    REPOSITORY_ROOT / "rust/betelgeuze-docking-search/src/repository_d0.rs"
)
DEFAULT_RUST_LIBRARY = REPOSITORY_ROOT / "rust/betelgeuze-docking-search/src/lib.rs"
DEFAULT_FIXTURE_MANIFEST = (
    REPOSITORY_ROOT / "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json"
)
DEFAULT_DOCUMENTATION = (
    REPOSITORY_ROOT / "docs/engine_v2_repository_synthetic_d0_native_source_v1.md"
)
DEFAULT_NATIVE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-native-compute-abi.yml"
)
DEFAULT_RELEASE_WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/ci-engine-v2-release-candidate.yml"
)

EXPECTED_AUTHORITY_FIELDS = frozenset(
    {
        "customer_pose_emission_authorized",
        "d1_d2_molecular_execution_authorized",
        "existing_rank_auto_change_authorized",
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_performance_claim_authorized",
        "production_claim_authorized",
        "public_benchmark_authorized",
        "qualification_rerun_authorized",
        "reservation_authorized",
        "stage0_admission_authorized",
    }
)
EXPECTED_CONSUMER_BINDING = {
    "api_activation_authorized": False,
    "benchmark_activation_authorized": False,
    "binding_ready": True,
    "product_shadow_activation_authorized": False,
    "standalone_activation_authorized": False,
    "test_only": True,
}
EXPECTED_FEATURE_INVENTORY = {
    "atomic_feature_count": 13,
    "donor_attached_hydrogen_required": True,
    "geometry_inventory_receipt_algorithm": (
        "Fixed64FeatureGeometryInventory::new/native-1.0.0"
    ),
    "geometry_receipt_algorithm": "Fixed64FeatureGeometry::new/native-1.0.0",
    "ligand_shape_atom_indices": [0, 1, 3],
    "missing_feature_slot_indices": [*range(36, 44), 56, 57],
    "partial_charge_threshold_binary64_hex": "0x1.0000000000000p-2",
    "pocket_shape_atom_indices": [0, 1, 3],
    "ready_slot_count": 54,
    "result_fields_consumed": False,
    "true_conformer_source_count": 0,
    "typed_failure_count": 10,
}
EXPECTED_FIXTURE = {
    "authority_input_receipt_sha256": (
        "8b434dd9b208c57f0be6f77442d6e041f6ca1a1727409bcf3fd43716b13a4284"
    ),
    "candidate_denominator": 64,
    "fixture_id": "betelgeuze.engine_v2.synthetic_d0_standalone_fixture/1.0.0",
    "ligand_atom_count": 5,
    "ligand_system_sha256": (
        "62dc8387fc033b9f87c1a6f5d97ed8f2e897e5c1332e8d6567faf5ea06000353"
    ),
    "manifest_sha256": (
        "12919355ac208aaa11d9560ebc95db05a30a5d4379bf741f89e81482d131693b"
    ),
    "receptor_atom_count": 5,
    "receptor_system_sha256": (
        "f205331ddce5591aeaac950a32a4e1cc151b1adf92793d6095e1cd226cfdd913"
    ),
    "request_sha256": (
        "bbf826bbdc30818f27c95f04763696bd09b7aa3e9cbd75c5d1597442d8129629"
    ),
    "seed": 4301,
    "top_k": 5,
}
EXPECTED_RECEIPT_IDENTITIES = {
    "allocation_receipt_sha256": (
        "8775a56bcd15bc903ead9365eb699c167d523157404dc2271c11a5274bacd2fb"
    ),
    "bitwise_current_v7_coordinate_identity_count": 28,
    "feature_inventory_receipt_sha256": (
        "0a13f3fd3ee9a95ef496135c6834dd3528aff729e20aa032df07182f6abe78f0"
    ),
    "guided_policy_sha256": (
        "2974e9ba80479cccc97dce1b51567e8e7309e7f89c983401c9a8966a3d08633f"
    ),
    "guided_receipt_sha256": (
        "8fc7cd2c744793fa9a000e6aab7b94e95aa19a2e8d74dda2b5468d2922d512c6"
    ),
    "native_source_bundle_receipt_sha256": (
        "80a7ee8fe919523c7afab78467dddb9bc2e653e028f1e731c9058db3ef17a68f"
    ),
    "prepared_input_receipt_sha256": (
        "9365608f04170392497222d4681e7494c2ddedb01fcab653ca1aded4de984e6e"
    ),
    "proposal_identity_count": 28,
    "selected_current_v7_coordinate_identity_manifest_sha256": (
        "6da149e7d418ebbe709615ba6df8d188c198e26fe56756e81da21dd8eba864b3"
    ),
    "selected_proposal_identity_manifest_sha256": (
        "aa4dc1845c6354116d09d2f99998b8ed0847b00d5ea0b4cf8d144a3b98ee38cf"
    ),
}
EXPECTED_SCOPE = {
    "component": "betelgeuze-docking-search::repository_d0",
    "cpp_parity_policy_profile_id": ("engine_v2_repository_synthetic_d0_cpu_parity_v1"),
    "cpp_parity_policy_schema_id": (
        "betelgeuze.engine_v2_repository_synthetic_d0_cpu_parity_policy/1.1.0"
    ),
    "cpp_parity_status": "implemented_separate_non_authoritative_policy",
    "hip_disposition": "compile_only_no_device_execution_or_parity_claim",
    "implementation": "rust_native_no_python_science_transport",
    "molecular_input_scope": "repository_owned_synthetic_d0_only",
    "performance_claim": "none",
    "validation_mode": "synthetic_native_cpu_only",
}
EXPECTED_CPU_PARITY_AUTHORITY_FIELDS = frozenset(
    {
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_ab_execution_authorized",
        "molecular_execution_authorized",
        "product_performance_claim_authorized",
        "public_benchmark_authorized",
        "qualification_rerun_authorized",
        "reservation_authorized",
        "scientific_claim_authorized",
        "stage0_admission_authorized",
    }
)
EXPECTED_CPU_PARITY_COMPARISON = {
    "absolute_tolerance": 1e-11,
    "all_coordinate_states_compared": True,
    "all_geometric_measurements_compared": True,
    "all_refinement_objectives_compared": True,
    "all_scorer_v1_terms_compared": True,
    "all_validity_measurements_compared": True,
    "backend_bound_receipt_identity_parity_required": False,
    "coordinate_sha256_identity_parity_required": False,
    "exact_decision_sha256_parity_required": True,
    "exact_denominator_and_stage_counts_required": True,
    "exact_failure_status_and_validity_masks_required": True,
    "exact_rank_and_v7_selection_required": True,
    "exact_source_and_allocation_identity_parity_required": True,
    "nonfinite_values_allowed": False,
    "relative_tolerance": 4e-12,
    "repeat_stability_required": True,
}
EXPECTED_CPU_PARITY_RESTRICTIONS = {
    "actual_molecular_execution_allowed": False,
    "contains_molecular_cases": False,
    "fresh_or_historical_case_input_allowed": False,
    "github_actions_production_authority_allowed": False,
    "performance_measurement_allowed": False,
    "reservation_allowed": False,
    "result_dependent_configuration_allowed": False,
    "test_double_production_authority_allowed": False,
}
EXPECTED_CPU_PARITY_RUNTIME = {
    "entrypoint": "native_fixed64_repository_synthetic_d0_cpu_parity_v1",
    "native_backends": ["cpp_cpu_reference", "rust_cpu"],
    "no_caller_science_input": True,
    "source_session_contract_sha256": (
        "51f314de529f1ed3b000bdfff2f7f3494a308303f5d6acf19ab517b3e7054de3"
    ),
    "synthetic_only_acknowledgment": (
        "repository-synthetic-d0-only:no-reservation:no-molecular-experiment:"
        "no-qualification-rerun:no-product-action:no-public-or-scientific-claim"
    ),
    "timing_fields_forbidden": True,
}
EXPECTED_SOURCE_GENERATION = {
    "centered_candidate_count": 8,
    "counter_prng_id": "sha256_counter_uniform_binary64/1.0.0",
    "current_v7_coordinate_identity": "bitwise_binary64_sha256_exact",
    "haar_rotation_algorithm": "shoemake_sha256_counter",
    "legacy_ulp_correction_count": 21,
    "logical_control_source_indices": list(range(24)),
    "one_materialization_call": True,
    "result_dependent_retry_allowed": False,
    "retained_source_indices": [36, 45, 54, 63],
    "transcendental_kernel": (
        "portable_libm_with_frozen_current_v7_one_ulp_corrections"
    ),
    "translation_radius_binary64_hex": "0x1.0000000000000p+2",
    "true_conformer_generation_allowed": False,
    "uniform_upstream_source_indices": [
        24,
        27,
        29,
        32,
        34,
        37,
        40,
        42,
        45,
        47,
        50,
        53,
        55,
        58,
        60,
        63,
    ],
}


class ContractError(RuntimeError):
    """The native synthetic-D0 source contract failed closed."""


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ContractError(f"duplicate JSON key: {key}")
        output[key] = value
    return output


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"{label} is unavailable: {path}") from exc


def _read_text(path: Path, *, label: str) -> str:
    raw = _read_bytes(path, label=label)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"{label} is not UTF-8: {path}") from exc


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(path, label="contract")
    try:
        document = json.loads(raw, object_pairs_hook=_pairs_no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError("contract is not valid UTF-8 JSON") from exc
    if type(document) is not dict:
        raise ContractError("contract must be one object")
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


def _read_compact_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes(path, label=label)
    try:
        document = json.loads(
            raw.decode("ascii"), object_pairs_hook=_pairs_no_duplicates
        )
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ContractError(f"{label} is not valid ASCII JSON") from exc
    if type(document) is not dict:
        raise ContractError(f"{label} must be one object")
    canonical = (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("ascii")
    if raw != canonical:
        raise ContractError(f"{label} is not canonical compact ASCII")
    return document, raw


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


def _digest_values(source: str, start: str, end: str) -> list[str]:
    try:
        section = source.split(start, 1)[1].split(end, 1)[0]
    except IndexError as exc:
        raise ContractError(f"Rust source digest section changed: {start}") from exc
    return re.findall(r'digest\("([0-9a-f]{64})"\)', section)


def _verify_cpu_parity_binding(
    *,
    parity_document: dict[str, Any],
    parity_raw: bytes,
    source_document: dict[str, Any],
    source_raw: bytes,
) -> str:
    _require_exact_keys(
        parity_document,
        {
            "authority",
            "comparison",
            "expected",
            "profile_id",
            "restrictions",
            "runtime",
            "schema_id",
            "status",
        },
        label="CPU parity policy",
    )
    scope = source_document["scope"]
    if (
        parity_document["schema_id"] != scope["cpp_parity_policy_schema_id"]
        or parity_document["profile_id"] != scope["cpp_parity_policy_profile_id"]
        or parity_document["status"]
        != "frozen_synthetic_non_authoritative_cpu_parity_policy"
    ):
        raise ContractError("CPU parity policy identity or status changed")

    authority = _require_exact_keys(
        parity_document["authority"],
        set(EXPECTED_CPU_PARITY_AUTHORITY_FIELDS),
        label="CPU parity authority",
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("CPU parity policy acquired execution authority")
    comparison = _require_exact_keys(
        parity_document["comparison"],
        set(EXPECTED_CPU_PARITY_COMPARISON),
        label="CPU parity comparison",
    )
    if comparison != EXPECTED_CPU_PARITY_COMPARISON:
        raise ContractError("CPU parity comparison coverage changed")
    restrictions = _require_exact_keys(
        parity_document["restrictions"],
        set(EXPECTED_CPU_PARITY_RESTRICTIONS),
        label="CPU parity restrictions",
    )
    if restrictions != EXPECTED_CPU_PARITY_RESTRICTIONS:
        raise ContractError("CPU parity restrictions changed")

    runtime = _require_exact_keys(
        parity_document["runtime"],
        {*EXPECTED_CPU_PARITY_RUNTIME, "source_contract_sha256"},
        label="CPU parity runtime",
    )
    expected_runtime = {
        **EXPECTED_CPU_PARITY_RUNTIME,
        "source_contract_sha256": hashlib.sha256(source_raw).hexdigest(),
    }
    if runtime != expected_runtime:
        raise ContractError("CPU parity policy is not bound to this source policy")

    expected = _require_exact_keys(
        parity_document["expected"],
        {
            "allocation_receipt_sha256",
            "candidate_denominator",
            "cluster_count",
            "compared_f64_count",
            "generated_count",
            "initial_admitted_count",
            "ligand_atom_count",
            "native_source_bundle_receipt_sha256",
            "post_admitted_count",
            "post_rejected_count",
            "prepared_input_receipt_sha256",
            "primary_slot_indices",
            "receptor_atom_count",
            "refined_count",
            "representative_slot_indices",
            "scientific_decision_sha256",
            "scored_count",
            "scorer_v1_term_count",
            "top_k_slot_indices",
            "typed_failure_count",
            "valid_count",
            "valid_slot_indices",
        },
        label="CPU parity expected result",
    )
    required_source_values = {
        "allocation_receipt_sha256": source_document["receipt_identities"][
            "allocation_receipt_sha256"
        ],
        "candidate_denominator": source_document["fixture"]["candidate_denominator"],
        "compared_f64_count": 16_896,
        "ligand_atom_count": source_document["fixture"]["ligand_atom_count"],
        "native_source_bundle_receipt_sha256": source_document["receipt_identities"][
            "native_source_bundle_receipt_sha256"
        ],
        "prepared_input_receipt_sha256": source_document["receipt_identities"][
            "prepared_input_receipt_sha256"
        ],
        "receptor_atom_count": source_document["fixture"]["receptor_atom_count"],
        "typed_failure_count": source_document["feature_inventory"][
            "typed_failure_count"
        ],
    }
    if any(expected[key] != value for key, value in required_source_values.items()):
        raise ContractError("CPU parity expected result is cross-wired from source")
    return hashlib.sha256(parity_raw).hexdigest()


def verify(
    *,
    contract_path: Path = DEFAULT_CONTRACT,
    cpu_parity_contract_path: Path = DEFAULT_CPU_PARITY_CONTRACT,
    rust_source_path: Path = DEFAULT_RUST_SOURCE,
    rust_library_path: Path = DEFAULT_RUST_LIBRARY,
    fixture_manifest_path: Path = DEFAULT_FIXTURE_MANIFEST,
    documentation_path: Path = DEFAULT_DOCUMENTATION,
    native_workflow_path: Path = DEFAULT_NATIVE_WORKFLOW,
    release_workflow_path: Path = DEFAULT_RELEASE_WORKFLOW,
) -> dict[str, object]:
    document, raw = _read_json(contract_path)
    _require_exact_keys(
        document,
        {
            "authority",
            "consumer_binding",
            "feature_inventory",
            "fixture",
            "receipt_identities",
            "schema_id",
            "scope",
            "source_generation",
            "status",
        },
        label="contract",
    )
    if (
        document["schema_id"]
        != "betelgeuze.engine_v2_repository_synthetic_d0_native_source_policy/1.1.0"
        or document["status"]
        != "repository_synthetic_d0_native_source_only_authority_false"
    ):
        raise ContractError("contract identity or status changed")

    authority = _require_exact_keys(
        document["authority"], set(EXPECTED_AUTHORITY_FIELDS), label="authority"
    )
    if any(value is not False for value in authority.values()):
        raise ContractError("native synthetic-D0 source acquired execution authority")
    expected_sections = (
        ("consumer_binding", EXPECTED_CONSUMER_BINDING),
        ("feature_inventory", EXPECTED_FEATURE_INVENTORY),
        ("fixture", EXPECTED_FIXTURE),
        ("receipt_identities", EXPECTED_RECEIPT_IDENTITIES),
        ("scope", EXPECTED_SCOPE),
        ("source_generation", EXPECTED_SOURCE_GENERATION),
    )
    for label, expected in expected_sections:
        observed = _require_exact_keys(document[label], set(expected), label=label)
        if observed != expected:
            raise ContractError(f"{label} changed from the frozen native policy")

    parity_document, parity_raw = _read_compact_json(
        cpu_parity_contract_path,
        label="CPU parity policy",
    )
    parity_policy_sha256 = _verify_cpu_parity_binding(
        parity_document=parity_document,
        parity_raw=parity_raw,
        source_document=document,
        source_raw=raw,
    )

    manifest = _read_bytes(fixture_manifest_path, label="synthetic D0 manifest")
    if hashlib.sha256(manifest).hexdigest() != EXPECTED_FIXTURE["manifest_sha256"]:
        raise ContractError("repository synthetic D0 fixture manifest identity changed")

    rust_source = _read_text(rust_source_path, label="Rust materializer source")
    if (
        len(
            re.findall(
                r"pub fn materialize_repository_synthetic_d0_sources\s*\(\s*\)\s*->",
                rust_source,
            )
        )
        != 1
    ):
        raise ContractError(
            "native materializer API is not one exact zero-input function"
        )
    if re.search(r"\bunsafe\b", rust_source):
        raise ContractError("native materializer gained unsafe Rust")
    _require_snippets(
        rust_source,
        (
            '"betelgeuze.engine_v2_repository_synthetic_d0_native_source/1.0.0"',
            '"betelgeuze.engine_v2_repository_synthetic_d0_fixed64_source/native-1.0.0"',
            "pub const REPOSITORY_D0_CANDIDATE_DENOMINATOR: usize = 64;",
            "24, 27, 29, 32, 34, 37, 40, 42, 45, 47, 50, 53, 55, 58, 60, 63,",
            "pub const REPOSITORY_D0_RETAINED_SOURCE_INDICES: [u32; 4] = [36, 45, 54, 63];",
            "pub const REPOSITORY_D0_SEED: u64 = 4_301;",
            "pub const REPOSITORY_D0_TRANSLATION_RADIUS_ANGSTROM: f64 = 4.0;",
            "pub const REPOSITORY_D0_CENTERED_CANDIDATE_COUNT: usize = 8;",
            ".zip(V7_LEGACY_NATIVE_COORDINATE_SHA256)",
            ".zip(RETAINED_LEGACY_NATIVE_COORDINATE_SHA256)",
            "Fixed64Allocation::build(inventory)",
            "allocation.ready_count() != 54",
            "allocation.typed_failure_count() != 10",
            "allocation.result_dependent_allocation()",
            "allocation.molecular_execution_authorized()",
            "hash.bool(false);",
            "const LIGAND_DONOR_ATOM_INDICES: [usize; 2] = [1, 3];",
            "const RECEPTOR_DONOR_ATOM_INDICES: [usize; 1] = [1];",
            "const PARTIAL_CHARGE_SITE_THRESHOLD: f64 = 0.25;",
            "push_donor_feature(&mut definitions, true, donor)?;",
            "push_donor_feature(&mut definitions, false, donor)?;",
            "push_charge_features(&mut definitions, true, &LIGAND_PARTIAL_CHARGES)?;",
            "push_charge_features(&mut definitions, false, &RECEPTOR_PARTIAL_CHARGES)?;",
            "heavy_atom_indices(&LIGAND_ATOMIC_NUMBERS)?",
            "heavy_atom_indices(&RECEPTOR_ATOMIC_NUMBERS)?",
            "Fixed64FeatureGeometry::new(",
            "Fixed64FeatureGeometryInventory::new(rows)",
            "sha256_counter_uniform_binary64/1.0.0",
            "fn preserve_legacy_binary64(",
            "pure-Rust libm crate differs by one ULP at these 21 frozen fixture points.",
            "(LegacyTranscendental::SinSecond, 7 | 12 | 62) => -1,",
            "(LegacyTranscendental::SinAzimuth, 55) => -1,",
        ),
        label="Rust materializer source",
    )
    manifest_keys = {
        "selected_current_v7_coordinate_identity_manifest_sha256",
        "selected_proposal_identity_manifest_sha256",
    }
    for key, digest in EXPECTED_RECEIPT_IDENTITIES.items():
        if (
            key not in manifest_keys
            and isinstance(digest, str)
            and len(digest) == 64
            and digest not in rust_source
        ):
            raise ContractError("Rust source is missing a frozen receipt identity")
    proposal_identities = _digest_values(
        rust_source,
        "const V7_LEGACY_PROPOSAL_SHA256",
        "const RETAINED_LEGACY_PROPOSAL_SHA256",
    ) + _digest_values(
        rust_source,
        "const RETAINED_LEGACY_PROPOSAL_SHA256",
        "const V7_LEGACY_NATIVE_COORDINATE_SHA256",
    )
    coordinate_identities = _digest_values(
        rust_source,
        "const V7_LEGACY_NATIVE_COORDINATE_SHA256",
        "const RETAINED_LEGACY_NATIVE_COORDINATE_SHA256",
    ) + _digest_values(
        rust_source,
        "const RETAINED_LEGACY_NATIVE_COORDINATE_SHA256",
        "#[derive(Clone, Copy",
    )
    if len(proposal_identities) != 28 or len(coordinate_identities) != 28:
        raise ContractError(
            "frozen current-V7 proposal or coordinate identity count changed"
        )
    proposal_manifest = hashlib.sha256(
        "".join(proposal_identities).encode("ascii")
    ).hexdigest()
    coordinate_manifest = hashlib.sha256(
        "".join(coordinate_identities).encode("ascii")
    ).hexdigest()
    if (
        proposal_manifest
        != EXPECTED_RECEIPT_IDENTITIES["selected_proposal_identity_manifest_sha256"]
        or coordinate_manifest
        != EXPECTED_RECEIPT_IDENTITIES[
            "selected_current_v7_coordinate_identity_manifest_sha256"
        ]
    ):
        raise ContractError(
            "ordered current-V7 proposal or coordinate identity manifest changed"
        )

    rust_library = _read_text(rust_library_path, label="Rust library export")
    _require_snippets(
        rust_library,
        (
            "mod repository_d0;",
            "materialize_repository_synthetic_d0_sources",
            "REPOSITORY_D0_EXPECTED_ALLOCATION_SHA256",
            "REPOSITORY_D0_EXPECTED_BUNDLE_SHA256",
            "REPOSITORY_D0_EXPECTED_FEATURE_INVENTORY_SHA256",
            "REPOSITORY_D0_EXPECTED_PREPARED_INPUT_SHA256",
        ),
        label="Rust library export",
    )

    documentation = _read_text(documentation_path, label="documentation")
    _require_snippets(
        documentation,
        (
            "pure-Rust source derivation",
            "pure-Rust `libm`",
            "21 frozen one-ULP corrections",
            "54 ready plus 10 typed failures",
            "All operational authority remains false",
            "separate non-authoritative Rust-to-C++ CPU parity policy",
            "all 16,896 binary64 values",
            "HIP is compile-only",
            "consumed native fixed64 CPU v7 qualification",
        ),
        label="documentation",
    )

    native_workflow = _read_text(native_workflow_path, label="native workflow")
    release_workflow = _read_text(release_workflow_path, label="release workflow")
    contract_rel = "config/engine_v2_repository_synthetic_d0_native_source_v1.json"
    verifier_rel = "tools/verify_engine_v2_repository_synthetic_d0_native_source_v1.py"
    test_rel = (
        "tests/unit/test_verify_engine_v2_repository_synthetic_d0_native_source_v1.py"
    )
    docs_rel = "docs/engine_v2_repository_synthetic_d0_native_source_v1.md"
    fixture_rel = "betelgeuze_engine_v2/docking/synthetic_d0_fixture_admission.json"
    parity_rel = "config/engine_v2_repository_synthetic_d0_cpu_parity_v1.json"
    _require_snippets(
        native_workflow,
        (
            contract_rel,
            verifier_rel,
            test_rel,
            docs_rel,
            fixture_rel,
            parity_rel,
            f"python3 {verifier_rel}",
        ),
        label="native workflow",
    )
    _require_snippets(
        release_workflow,
        (
            contract_rel,
            verifier_rel,
            test_rel,
            docs_rel,
            parity_rel,
            f"python {verifier_rel}",
        ),
        label="release workflow",
    )

    return {
        "schema_id": (
            "betelgeuze.engine_v2_repository_synthetic_d0_native_source_verification/1.1.0"
        ),
        "status": "verified_static_non_authoritative",
        "contract_sha256": hashlib.sha256(raw).hexdigest(),
        "all_authority_false": True,
        "candidate_denominator": 64,
        "ready_slot_count": 54,
        "typed_failure_count": 10,
        "bitwise_current_v7_coordinate_identity_count": 28,
        "cpp_cpu_parity_bound": True,
        "cpp_cpu_parity_compared_f64_count": 16_896,
        "cpp_cpu_parity_policy_sha256": parity_policy_sha256,
        "native_source_bundle_receipt_sha256": EXPECTED_RECEIPT_IDENTITIES[
            "native_source_bundle_receipt_sha256"
        ],
        "consumer_activation_authorized": False,
        "molecular_execution_authorized": False,
        "reservation_authorized": False,
        "hip_device_execution_authorized": False,
        "verification_blockers": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument(
        "--cpu-parity-contract",
        type=Path,
        default=DEFAULT_CPU_PARITY_CONTRACT,
    )
    arguments = parser.parse_args(argv)
    try:
        result = verify(
            contract_path=arguments.contract,
            cpu_parity_contract_path=arguments.cpu_parity_contract,
        )
    except ContractError as exc:
        parser.exit(1, f"{exc}\n")
    print(
        json.dumps(
            result,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
