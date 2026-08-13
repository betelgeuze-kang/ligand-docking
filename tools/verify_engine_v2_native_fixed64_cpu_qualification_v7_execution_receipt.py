#!/usr/bin/env python3
"""Verify the frozen non-authoritative fixed64 CPU v7 execution receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import NoReturn

if __package__:
    from . import verify_engine_v2_native_fixed64_cpu_v7_evidence as raw_verifier
else:
    import verify_engine_v2_native_fixed64_cpu_v7_evidence as raw_verifier


RECEIPT_RELATIVE_PATH = Path(
    "config/engine_v2_native_fixed64_cpu_qualification_v7_execution_receipt.json"
)
RECEIPT_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_fixed64_cpu_qualification_execution_receipt/7.0.0"
)
RECEIPT_DOMAIN = (
    b"betelgeuze.engine_v2_native_fixed64_cpu_qualification_execution_receipt_v7\0"
)
EXPECTED_RECEIPT_SHA256 = (
    "f653185c2bfc7642e2d9e73b918a2e0a9c14c0e107f5804799e140bb42c34b82"
)
EXPECTED_PROFILE_ID = "engine_v2_native_fixed64_cpu_synthetic_v7"
EXPECTED_PROFILE_SHA256 = (
    "50c3e609a23e3bf0641a900f71dc360dcadc1a52c3bde66cdfa74b8c1affcd5d"
)
EXPECTED_SOURCE_COMMIT_OID = "5c1e4791e988d4c75a5111f933feac85236ba821"
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "ecb009ac228652c6c6cbdefcdd70828ce3d9aeea5a5e31d0fff0246d4d5f932e"
)
EXPECTED_ACTIVATION_SHA256 = (
    "7d86f8aaa4392ed0bf540c698245e9122dbf4630d6eaab893592d94c927b0d84"
)
EXPECTED_BUILD_CONFIGURATION_SHA256 = (
    "6e39e4e07bcb2f9324f242adcf3f48428191b2a91418d34520c6acc1cf046068"
)
EXPECTED_OUTPUT_PATH_SHA256 = (
    "eb3d3c502baf6d89594ef092d4dfa64a637391f47796570b5279cd60a7616c64"
)
EXPECTED_RUN_NONCE = "87d5132cfeadc8739830d0ffc1bc12650359d99481bd9484d92a24683df05117"
EXPECTED_EXTERNAL_DECISION_SHA256 = (
    "0ce7914de8a02b2ce438aee35dd7907e161f82fa92e9175d684cd96a22800100"
)
EXPECTED_EXTERNAL_BLOCKERS = (
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)
EXPECTED_AUTHORITY_KEYS = (
    "fresh_holdout_execution_authorized",
    "historical_ab_execution_authorized",
    "molecular_execution_authorized",
    "product_performance_claim_authorized",
    "public_benchmark_authorized",
    "qualification_authority",
    "reservation_authorized",
    "scientific_claim_authorized",
    "stage0_admission_authorized",
)
EXPECTED_RESTRICTION_KEYS = (
    "actual_molecular_execution_allowed",
    "contains_molecular_cases",
    "fresh_or_historical_case_input_allowed",
    "github_actions_live_qualification_allowed",
    "github_actions_production_authority_allowed",
    "hip_device_execution_allowed",
    "public_or_scientific_performance_claim_allowed",
    "reservation_allowed",
    "result_dependent_configuration_allowed",
    "test_double_production_authority_allowed",
)
EXPECTED_RAW_EVIDENCE = {
    "artifact": {
        "byte_count": 3_029_064,
        "raw_sha256": "a850247353a90e7ce417a16ba8041872c90a9a849b95b0102c2359a8fa75330b",
        "receipt_sha256": "4e01c7b0489e18e9b6bd856c3ea27ac6fc9943f7deec51ac304d5966de529d84",
    },
    "attempt": {
        "attempt_ordinal": 1,
        "byte_count": 1_572,
        "measurement_started_at_creation": False,
        "raw_sha256": "8d51c9e74fe39ecfcd5f799ca3c8c064b6638cda1c8487d84995dcb7fc357802",
        "receipt_sha256": "a9ce37c62152372242baed55aa3257b39c7906616ace9169de10a6dcfade8d84",
    },
    "terminal": {
        "byte_count": 2_139,
        "raw_sha256": "0febcf69013e28bfa428573bbe9b49550b7b2f9d5b64df5004d7645a1b0831f6",
        "receipt_sha256": "f415c8b60486624ae800f58acae2c3475559a4576f99958bed8f5a169991ff3c",
    },
}
EXPECTED_FIXTURES = {
    "synthetic_complete_64": {
        "fixture_payload_sha256": "5e17b3a292a068115f223c5c433d5ec40557be50a05cc1dbaa07461d9aed7fb8",
        "generated_count": 64,
        "typed_failure_count": 0,
        "cpp_median_nanoseconds": 61_780_433,
        "rust_median_nanoseconds": 35_181_952,
        "rust_to_cpp_median_ratio": 0.5694675529386465,
        "maximum_absolute_difference": 3.552713678800501e-14,
        "maximum_scaled_difference": 2,
    },
    "synthetic_feature_sparse_48_plus_16": {
        "fixture_payload_sha256": "fca0d6dbdc0f188e332929b9ea220f1d3ecaa37e9939c49aa80bf0629c14f1fb",
        "generated_count": 48,
        "typed_failure_count": 16,
        "cpp_median_nanoseconds": 45_719_698,
        "rust_median_nanoseconds": 18_572_880,
        "rust_to_cpp_median_ratio": 0.40623365447427057,
        "maximum_absolute_difference": 8.881784197001252e-16,
        "maximum_scaled_difference": 1,
    },
}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_OID_PATTERN = re.compile(r"[0-9a-f]{40}\Z")


class NativeFixed64CPUV7ExecutionReceiptError(ValueError):
    """The frozen compact execution receipt failed closed."""


def _fail(message: str) -> NoReturn:
    raise NativeFixed64CPUV7ExecutionReceiptError(message)


def _duplicate_rejector(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    _fail(f"non-finite JSON constant is forbidden: {value}")


def _load_json_bytes(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        decoded = raw.decode("ascii")
        value = json.loads(
            decoded,
            object_pairs_hook=_duplicate_rejector,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise NativeFixed64CPUV7ExecutionReceiptError(
            f"{label} is not strict ASCII JSON"
        ) from exc
    if type(value) is not dict:
        _fail(f"{label} is not an object")
    return value


def _canonical_projection(value: dict[str, object]) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _receipt_sha256(projection: dict[str, object]) -> str:
    return _sha256(RECEIPT_DOMAIN + _canonical_projection(projection))


def _require_object(
    value: object, *, keys: tuple[str, ...], label: str
) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} is not an object")
    if set(value) != set(keys):
        _fail(f"{label} keys changed")
    return value


def _require_digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        _fail(f"{label} is not a lowercase SHA-256")
    return value


def _require_all_false(value: object, *, keys: tuple[str, ...], label: str) -> None:
    record = _require_object(value, keys=keys, label=label)
    if any(record[key] is not False for key in keys):
        _fail(f"{label} escalates authority")


def _require_fixture(value: object, *, expected_id: str) -> None:
    keys = (
        "authority_false",
        "candidate_denominator",
        "cpp_decision_sha256",
        "cpp_generated_count",
        "cpp_lane_metrics_decision_sha256",
        "cpp_lane_metrics_receipt_sha256",
        "cpp_median_nanoseconds",
        "cpp_projection_sha256",
        "cpp_repeat_stable",
        "cpp_typed_failure_count",
        "decision_parity",
        "fixture_id",
        "fixture_payload_sha256",
        "gate_passed",
        "lane_metrics_authority_false",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "lane_metrics_reference_sha256",
        "ligand_atom_count",
        "numeric_parity",
        "persistent_cpp_context_count",
        "persistent_rust_context_count",
        "receptor_atom_count",
        "rust_decision_sha256",
        "rust_generated_count",
        "rust_lane_metrics_decision_sha256",
        "rust_lane_metrics_receipt_sha256",
        "rust_median_nanoseconds",
        "rust_projection_sha256",
        "rust_repeat_stable",
        "rust_to_cpp_median_ratio",
        "rust_typed_failure_count",
        "score_term_count",
    )
    fixture = _require_object(value, keys=keys, label=f"fixture {expected_id}")
    expected = EXPECTED_FIXTURES[expected_id]
    if fixture["fixture_id"] != expected_id:
        _fail("fixture order or identity changed")
    if fixture["fixture_payload_sha256"] != expected["fixture_payload_sha256"]:
        _fail(f"fixture payload identity changed: {expected_id}")
    for key in (
        "authority_false",
        "cpp_repeat_stable",
        "decision_parity",
        "gate_passed",
        "lane_metrics_authority_false",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "rust_repeat_stable",
    ):
        if fixture[key] is not True:
            _fail(f"fixture invariant failed: {expected_id}.{key}")
    if (
        fixture["candidate_denominator"] != 64
        or fixture["ligand_atom_count"] != 12
        or fixture["receptor_atom_count"] != 12
        or fixture["score_term_count"] != 8
        or fixture["persistent_cpp_context_count"] != 1
        or fixture["persistent_rust_context_count"] != 1
        or fixture["cpp_generated_count"] != expected["generated_count"]
        or fixture["rust_generated_count"] != expected["generated_count"]
        or fixture["cpp_typed_failure_count"] != expected["typed_failure_count"]
        or fixture["rust_typed_failure_count"] != expected["typed_failure_count"]
        or fixture["cpp_median_nanoseconds"] != expected["cpp_median_nanoseconds"]
        or fixture["rust_median_nanoseconds"] != expected["rust_median_nanoseconds"]
        or fixture["rust_to_cpp_median_ratio"] != expected["rust_to_cpp_median_ratio"]
    ):
        _fail(f"fixture count or timing evidence changed: {expected_id}")
    if (
        type(fixture["rust_to_cpp_median_ratio"]) is not float
        or not math.isfinite(fixture["rust_to_cpp_median_ratio"])
        or not 0.0 < fixture["rust_to_cpp_median_ratio"] <= 1.0
    ):
        _fail(f"fixture performance ratio is invalid: {expected_id}")
    numeric = _require_object(
        fixture["numeric_parity"],
        keys=(
            "compared_f64_count",
            "first_violation_index",
            "maximum_absolute_difference",
            "maximum_scaled_difference",
            "tolerance_violation_count",
        ),
        label=f"fixture numeric parity {expected_id}",
    )
    if (
        numeric["compared_f64_count"] != 28_544
        or numeric["first_violation_index"] is not None
        or numeric["maximum_absolute_difference"]
        != expected["maximum_absolute_difference"]
        or numeric["maximum_scaled_difference"] != expected["maximum_scaled_difference"]
        or numeric["tolerance_violation_count"] != 0
    ):
        _fail(f"fixture numeric parity changed: {expected_id}")
    for key, digest in fixture.items():
        if key.endswith("_sha256"):
            _require_digest(digest, label=f"fixture {expected_id}.{key}")
    if fixture["cpp_decision_sha256"] != fixture["rust_decision_sha256"]:
        _fail(f"fixture decision digest parity failed: {expected_id}")
    if (
        fixture["cpp_lane_metrics_decision_sha256"]
        != fixture["rust_lane_metrics_decision_sha256"]
    ):
        _fail(f"fixture lane-decision digest parity failed: {expected_id}")


def require_execution_receipt_bytes(raw: bytes) -> dict[str, object]:
    envelope = _require_object(
        _load_json_bytes(raw, label="execution receipt"),
        keys=("projection", "receipt_sha256"),
        label="execution receipt envelope",
    )
    projection = _require_object(
        envelope["projection"],
        keys=(
            "authority",
            "claims",
            "execution",
            "external_authority_snapshot",
            "fixtures",
            "host",
            "profile",
            "raw_evidence",
            "restrictions",
            "schema_id",
            "status",
        ),
        label="execution receipt projection",
    )
    receipt_sha256 = _require_digest(
        envelope["receipt_sha256"], label="execution receipt SHA-256"
    )
    if (
        receipt_sha256 != EXPECTED_RECEIPT_SHA256
        or _receipt_sha256(projection) != receipt_sha256
    ):
        _fail("execution receipt identity changed")
    if (
        projection["schema_id"] != RECEIPT_SCHEMA_ID
        or projection["status"] != "recorded_pass_non_authoritative"
    ):
        _fail("execution receipt schema or status changed")
    _require_all_false(
        projection["authority"], keys=EXPECTED_AUTHORITY_KEYS, label="authority"
    )
    _require_all_false(
        projection["restrictions"],
        keys=EXPECTED_RESTRICTION_KEYS,
        label="restrictions",
    )
    _require_all_false(
        projection["claims"],
        keys=(
            "cpu_product_performance_claimed",
            "hip_parity_claimed",
            "molecular_science_claimed",
            "public_benchmark_claimed",
            "stage0_admission_claimed",
        ),
        label="claims",
    )
    profile = _require_object(
        projection["profile"],
        keys=(
            "activation_sha256",
            "build_configuration_sha256",
            "profile_id",
            "profile_sha256",
            "source_commit_oid",
            "source_manifest_sha256",
        ),
        label="profile identity",
    )
    if profile != {
        "activation_sha256": EXPECTED_ACTIVATION_SHA256,
        "build_configuration_sha256": EXPECTED_BUILD_CONFIGURATION_SHA256,
        "profile_id": EXPECTED_PROFILE_ID,
        "profile_sha256": EXPECTED_PROFILE_SHA256,
        "source_commit_oid": EXPECTED_SOURCE_COMMIT_OID,
        "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
    }:
        _fail("profile identity changed")
    if _OID_PATTERN.fullmatch(str(profile["source_commit_oid"])) is None:
        _fail("source commit is not a lowercase Git object ID")
    execution = _require_object(
        projection["execution"],
        keys=(
            "execution_attested",
            "execution_consumed",
            "measurement_started",
            "offline_replay_only",
            "recorded_decision",
            "recorded_gate_passed",
            "recorded_numeric_gate_passed",
            "terminal_persisted_before_decision_return",
        ),
        label="execution state",
    )
    if execution != {
        "execution_attested": False,
        "execution_consumed": True,
        "measurement_started": True,
        "offline_replay_only": True,
        "recorded_decision": "PASS",
        "recorded_gate_passed": True,
        "recorded_numeric_gate_passed": True,
        "terminal_persisted_before_decision_return": True,
    }:
        _fail("execution state changed")
    host = _require_object(
        projection["host"],
        keys=(
            "boost_disabled",
            "cpu_model",
            "measurement_cpu_available",
            "measurement_cpu_ordinal",
            "process_task_count",
        ),
        label="host evidence",
    )
    if host != {
        "boost_disabled": True,
        "cpu_model": "AMD Ryzen 9 5900X 12-Core Processor",
        "measurement_cpu_available": True,
        "measurement_cpu_ordinal": 2,
        "process_task_count": 1,
    }:
        _fail("host evidence changed")
    raw_evidence = _require_object(
        projection["raw_evidence"],
        keys=(
            "artifact",
            "attempt",
            "output_path_sha256",
            "raw_files_embedded_in_repository",
            "raw_files_required_for_full_reverification",
            "run_nonce",
            "terminal",
        ),
        label="raw evidence index",
    )
    for name, expected in EXPECTED_RAW_EVIDENCE.items():
        record = raw_evidence[name]
        if record != expected:
            _fail(f"raw {name} identity changed")
        assert isinstance(record, dict)
        _require_digest(record["raw_sha256"], label=f"raw {name} SHA-256")
        _require_digest(record["receipt_sha256"], label=f"raw {name} receipt")
    if (
        raw_evidence["output_path_sha256"] != EXPECTED_OUTPUT_PATH_SHA256
        or raw_evidence["run_nonce"] != EXPECTED_RUN_NONCE
        or raw_evidence["raw_files_embedded_in_repository"] is not False
        or raw_evidence["raw_files_required_for_full_reverification"] is not True
    ):
        _fail("raw evidence boundary changed")
    fixtures = projection["fixtures"]
    if type(fixtures) is not list or len(fixtures) != len(EXPECTED_FIXTURES):
        _fail("fixture set changed")
    for value, fixture_id in zip(fixtures, EXPECTED_FIXTURES, strict=True):
        _require_fixture(value, expected_id=fixture_id)
    external = _require_object(
        projection["external_authority_snapshot"],
        keys=(
            "all_authority_false",
            "decision_sha256",
            "external_reservation_operational",
            "operational_blockers",
            "operations_decision_ready",
            "unresolved_field_count",
        ),
        label="external authority snapshot",
    )
    if (
        external["all_authority_false"] is not True
        or external["decision_sha256"] != EXPECTED_EXTERNAL_DECISION_SHA256
        or external["external_reservation_operational"] is not False
        or external["operational_blockers"] != list(EXPECTED_EXTERNAL_BLOCKERS)
        or external["operations_decision_ready"] is not False
        or external["unresolved_field_count"] != 32
    ):
        _fail("external authority snapshot changed")
    return projection


def _compact_fixture(value: dict[str, object]) -> dict[str, object]:
    keys = (
        "authority_false",
        "candidate_denominator",
        "cpp_decision_sha256",
        "cpp_generated_count",
        "cpp_lane_metrics_decision_sha256",
        "cpp_lane_metrics_receipt_sha256",
        "cpp_median_nanoseconds",
        "cpp_projection_sha256",
        "cpp_repeat_stable",
        "cpp_typed_failure_count",
        "decision_parity",
        "fixture_id",
        "fixture_payload_sha256",
        "gate_passed",
        "lane_metrics_authority_false",
        "lane_metrics_decision_parity",
        "lane_metrics_rederivable",
        "lane_metrics_reference_sha256",
        "ligand_atom_count",
        "numeric_parity",
        "persistent_cpp_context_count",
        "persistent_rust_context_count",
        "receptor_atom_count",
        "rust_decision_sha256",
        "rust_generated_count",
        "rust_lane_metrics_decision_sha256",
        "rust_lane_metrics_receipt_sha256",
        "rust_median_nanoseconds",
        "rust_projection_sha256",
        "rust_repeat_stable",
        "rust_to_cpp_median_ratio",
        "rust_typed_failure_count",
        "score_term_count",
    )
    return {key: value[key] for key in keys}


def reverify_raw_evidence(
    *,
    artifact_path: Path,
    attempt_path: Path,
    projection: dict[str, object],
    repo_root: Path,
    terminal_path: Path,
) -> None:
    artifact_path = artifact_path.absolute()
    attempt_path = attempt_path.absolute()
    terminal_path = terminal_path.absolute()
    raw_verifier._require_state_paths(attempt_path, terminal_path)
    artifact_raw = raw_verifier._read_owner_file(
        artifact_path,
        maximum=raw_verifier.MAX_ARTIFACT_BYTES,
        label="qualification artifact",
    )
    attempt_raw = raw_verifier._read_owner_file(
        attempt_path, maximum=raw_verifier.MAX_STATE_BYTES, label="attempt ledger"
    )
    terminal_raw = raw_verifier._read_owner_file(
        terminal_path, maximum=raw_verifier.MAX_STATE_BYTES, label="terminal state"
    )
    output_path_sha256 = _sha256(os.fsencode(str(artifact_path)))
    if output_path_sha256 != EXPECTED_OUTPUT_PATH_SHA256:
        _fail("raw artifact path identity changed")
    profile_raw = (repo_root / raw_verifier.PROFILE_RELATIVE_PATH).read_bytes()
    evidence = raw_verifier.require_persisted_evidence_bytes(
        artifact_raw=artifact_raw,
        attempt_raw=attempt_raw,
        expected_source_commit_oid=EXPECTED_SOURCE_COMMIT_OID,
        terminal_raw=terminal_raw,
        output_path_sha256=output_path_sha256,
        profile_raw=profile_raw,
    )
    raw_index = projection["raw_evidence"]
    assert isinstance(raw_index, dict)
    for name, raw in (
        ("artifact", artifact_raw),
        ("attempt", attempt_raw),
        ("terminal", terminal_raw),
    ):
        record = raw_index[name]
        assert isinstance(record, dict)
        if len(raw) != record["byte_count"] or _sha256(raw) != record["raw_sha256"]:
            _fail(f"raw {name} bytes differ from the compact receipt")
        envelope = _load_json_bytes(raw, label=f"raw {name}")
        if envelope.get("receipt_sha256") != record["receipt_sha256"]:
            _fail(f"raw {name} receipt differs from the compact receipt")
    artifact = evidence["artifact"]
    terminal = evidence["terminal"]
    attempt = evidence["attempt"]
    assert isinstance(artifact, dict)
    assert isinstance(terminal, dict)
    assert isinstance(attempt, dict)
    fixtures = projection["fixtures"]
    if [_compact_fixture(value) for value in artifact["fixtures"]] != fixtures:
        _fail("raw fixture evidence differs from the compact receipt")
    if (
        artifact["host"]["source_commit_oid"] != EXPECTED_SOURCE_COMMIT_OID
        or artifact["execution"]["recorded_decision"] != "PASS"
        or artifact["execution"]["recorded_gate_passed"] is not True
        or artifact["execution"]["recorded_numeric_gate_passed"] is not True
        or terminal["execution_consumed"] is not True
        or terminal["recorded_decision"] != "PASS"
        or terminal["recorded_gate_passed"] is not True
        or attempt["attempt_ordinal"] != 1
        or attempt["measurement_started"] is not False
        or attempt["run_nonce"] != EXPECTED_RUN_NONCE
    ):
        _fail("raw execution state differs from the compact receipt")


def verify_execution_receipt(
    *,
    receipt_path: Path,
    artifact_path: Path | None = None,
    attempt_path: Path | None = None,
    repo_root: Path,
    terminal_path: Path | None = None,
) -> tuple[dict[str, object], bool]:
    raw = receipt_path.read_bytes()
    if not 1 <= len(raw) <= 128 * 1024:
        _fail("execution receipt size is out of bounds")
    projection = require_execution_receipt_bytes(raw)
    supplied = (artifact_path, attempt_path, terminal_path)
    if any(value is not None for value in supplied) and not all(
        value is not None for value in supplied
    ):
        _fail("artifact, attempt, and terminal must be supplied together")
    raw_reverified = all(value is not None for value in supplied)
    if raw_reverified:
        assert artifact_path is not None
        assert attempt_path is not None
        assert terminal_path is not None
        reverify_raw_evidence(
            artifact_path=artifact_path,
            attempt_path=attempt_path,
            projection=projection,
            repo_root=repo_root,
            terminal_path=terminal_path,
        )
    return projection, raw_reverified


def _parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--receipt", type=Path, default=repo_root / RECEIPT_RELATIVE_PATH
    )
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--terminal", type=Path)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    projection, raw_reverified = verify_execution_receipt(
        receipt_path=arguments.receipt,
        artifact_path=arguments.artifact,
        attempt_path=arguments.attempt,
        repo_root=arguments.repo_root.resolve(),
        terminal_path=arguments.terminal,
    )
    profile = projection["profile"]
    execution = projection["execution"]
    assert isinstance(profile, dict)
    assert isinstance(execution, dict)
    print(
        json.dumps(
            {
                "all_authority_false": True,
                "execution_consumed": True,
                "profile_id": profile["profile_id"],
                "raw_evidence_reverified": raw_reverified,
                "receipt_sha256": EXPECTED_RECEIPT_SHA256,
                "recorded_decision": execution["recorded_decision"],
                "source_commit_oid": profile["source_commit_oid"],
                "status": projection["status"],
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
