#!/usr/bin/env python3
"""Verify the unresolved external-ledger operations decision record."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_"
    "operations_decision/1.0.0"
)
EXPECTED_DECISION_SHA256 = (
    "0ce7914de8a02b2ce438aee35dd7907e161f82fa92e9175d684cd96a22800100"
)
EXPECTED_EXTERNAL_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_external_reservation_policy/"
    "1.1.0"
)
EXPECTED_EXTERNAL_POLICY_SHA256 = (
    "e018b149a010b337ddc3705c0cb904466a6cd870db82836b3b5c580c3cb650c4"
)
EXPECTED_ONE_SHOT_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_policy/1.1.0"
)
EXPECTED_ONE_SHOT_POLICY_SHA256 = (
    "b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f"
)
EXPECTED_COHORT_POLICY_SCHEMA_ID = (
    "betelgeuze.engine_v2_phase25_cohort_admission/1.3.0"
)
EXPECTED_COHORT_POLICY_SHA256 = (
    "b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211"
)
EXPECTED_OPERATIONAL_BLOCKERS = (
    "external_reservation_provider_not_operational",
    "external_reservation_endpoint_not_configured",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
)
EXPECTED_AUTHORITY = {
    "customer_pose_emission_authorized": False,
    "fresh_holdout_execution_authorized": False,
    "historical_execution_operational": False,
    "product_execution_authorized": False,
    "profile_promotion_authority": False,
    "public_or_scientific_claim_authorized": False,
    "stage0_admission_authority": False,
}
EXPECTED_BINDINGS = {
    "external_reservation_policy_schema_id": EXPECTED_EXTERNAL_POLICY_SCHEMA_ID,
    "external_reservation_policy_sha256": EXPECTED_EXTERNAL_POLICY_SHA256,
    "one_shot_policy_schema_id": EXPECTED_ONE_SHOT_POLICY_SCHEMA_ID,
    "one_shot_policy_sha256": EXPECTED_ONE_SHOT_POLICY_SHA256,
    "phase25_cohort_policy_schema_id": EXPECTED_COHORT_POLICY_SCHEMA_ID,
    "phase25_cohort_policy_sha256": EXPECTED_COHORT_POLICY_SHA256,
}
EXPECTED_REQUIREMENTS = {
    "distinct_human_author_operator_reviewer_required": True,
    "github_actions_production_access_forbidden": True,
    "independent_provider_qualification_required": True,
    "non_consuming_preflight_required": True,
    "non_exporting_asymmetric_hsm_or_kms_required": True,
    "private_network_and_mutual_tls_required": True,
    "reservation_before_zero_blockers_forbidden": True,
    "separate_production_realm_required": True,
    "strongly_consistent_atomic_lifetime_key_store_required": True,
    "test_double_production_access_forbidden": True,
    "worm_audit_log_required": True,
}
EXPECTED_DECISIONS: dict[str, object] = {
    "audit_and_recovery": {
        "backup_design": None,
        "rpo_seconds": None,
        "rto_seconds": None,
        "retention_years": None,
        "worm_audit_log_product": None,
    },
    "ledger_ownership": {
        "accountable_owner": None,
        "operating_organization": None,
    },
    "mutual_tls": {
        "certificate_authority": None,
        "client_certificate_lifetime_seconds": None,
        "workload_identity_profile": None,
    },
    "operating_procedures": {
        "ambiguous_commit": None,
        "break_glass": None,
        "incident": None,
        "revocation": None,
    },
    "role_roster": {
        "author_real_names": [],
        "operator_real_names": [],
        "reviewer_real_names": [],
    },
    "service_realm": {
        "account_or_project_id": None,
        "consistency_model": None,
        "lifetime_key_store_product": None,
        "region": None,
        "versioned_endpoint": None,
    },
    "signing_custody": {
        "asymmetric_algorithm": None,
        "hsm_or_kms_product": None,
        "key_destruction_procedure": None,
        "key_rotation_procedure": None,
        "non_export_configuration_reference": None,
        "region": None,
    },
    "trust_anchor_lifecycle": {
        "issuing_authority": None,
        "publication_procedure": None,
        "revocation_procedure": None,
        "rotation_procedure": None,
    },
}
EXPECTED_QUALIFICATION = {
    "independent_review_complete": False,
    "provider_qualification_complete": False,
    "qualification_receipt_sha256": None,
}
TOP_LEVEL_KEYS = {
    "authority",
    "bindings",
    "decision_sha256",
    "decisions",
    "operations_decision_ready",
    "operational_blockers",
    "qualification",
    "record_role",
    "requirements",
    "schema_id",
    "status",
    "unresolved_fields",
}
FORBIDDEN_FIELD_FRAGMENTS = (
    "credential",
    "password",
    "private_key",
    "privatekey",
    "secret",
    "token",
)


class ExternalOperationsDecisionError(ValueError):
    """Raised when the review-only decision record drifts."""


def _canonical_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ExternalOperationsDecisionError(
            f"value is not canonical JSON: {exc}"
        ) from exc
    return encoded.encode("ascii")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ExternalOperationsDecisionError(
                f"duplicate JSON key rejected: {key}"
            )
        result[key] = value
    return result


def _load_json(path: Path, *, name: str) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except ExternalOperationsDecisionError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalOperationsDecisionError(
            f"{name} is not readable JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalOperationsDecisionError(f"{name} must be an object")
    return payload


def _mapping(value: object, *, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ExternalOperationsDecisionError(f"{name} must be an object")
    return value


def _exact_mapping(
    value: object,
    expected: Mapping[str, object],
    *,
    name: str,
) -> None:
    observed = _mapping(value, name=name)
    if set(observed) != set(expected):
        raise ExternalOperationsDecisionError(f"{name} keys are invalid")
    for key, expected_value in expected.items():
        observed_value = observed[key]
        if type(observed_value) is not type(expected_value):
            raise ExternalOperationsDecisionError(f"{name}.{key} type is invalid")
        if isinstance(expected_value, dict):
            _exact_mapping(observed_value, expected_value, name=f"{name}.{key}")
        elif observed_value != expected_value:
            raise ExternalOperationsDecisionError(f"{name}.{key} is invalid")


def _forbid_sensitive_fields(value: object, *, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if any(fragment in normalized for fragment in FORBIDDEN_FIELD_FRAGMENTS):
                raise ExternalOperationsDecisionError(
                    f"sensitive material field is forbidden: {path}.{key}"
                )
            _forbid_sensitive_fields(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _forbid_sensitive_fields(child, path=f"{path}[{index}]")


def _unresolved_paths(value: Mapping[str, object]) -> tuple[str, ...]:
    paths: list[str] = []

    def walk(current: object, prefix: str) -> None:
        if isinstance(current, dict):
            for key in sorted(current):
                walk(current[key], f"{prefix}.{key}")
            return
        if current is None or current == []:
            paths.append(prefix)
            return
        raise ExternalOperationsDecisionError(
            f"operational decision must remain null or empty: {prefix}"
        )

    walk(value, "decisions")
    return tuple(paths)


def _verify_source_policy(
    path: Path,
    *,
    name: str,
    expected_schema_id: str,
    expected_policy_sha256: str,
) -> dict[str, Any]:
    payload = _load_json(path, name=name)
    if payload.get("schema_id") != expected_schema_id:
        raise ExternalOperationsDecisionError(f"{name} schema identity drifted")
    observed = payload.get("policy_sha256")
    if observed != expected_policy_sha256:
        raise ExternalOperationsDecisionError(f"{name} policy identity drifted")
    projection = dict(payload)
    projection.pop("policy_sha256", None)
    if _sha256(projection) != expected_policy_sha256:
        raise ExternalOperationsDecisionError(f"{name} self-hash is invalid")
    return payload


def _derive_external_blockers(policy: Mapping[str, Any]) -> tuple[str, ...]:
    provider = _mapping(policy.get("provider"), name="external policy provider")
    authority = _mapping(policy.get("authority"), name="external policy authority")
    blockers: list[str] = []
    if provider.get("provider_operational") is not True:
        blockers.append("external_reservation_provider_not_operational")
    if not provider.get("endpoint"):
        blockers.append("external_reservation_endpoint_not_configured")
    if not provider.get("trust_anchor_public_key_hex"):
        blockers.append("external_reservation_trust_anchor_not_configured")
    if authority.get("historical_execution_operational") is not True:
        blockers.append("historical_execution_operational_authority_false")
    return tuple(blockers)


def verify_external_operations_decision(
    *,
    decision_path: Path,
    external_policy_path: Path,
    one_shot_policy_path: Path,
    cohort_policy_path: Path,
) -> dict[str, object]:
    """Verify a deliberately unresolved decision record and its source bindings."""

    payload = _load_json(decision_path, name="external operations decision")
    _forbid_sensitive_fields(payload)
    if set(payload) != TOP_LEVEL_KEYS:
        raise ExternalOperationsDecisionError("decision record keys are invalid")
    if payload.get("schema_id") != SCHEMA_ID:
        raise ExternalOperationsDecisionError("decision record schema drifted")
    if payload.get("record_role") != (
        "review_only_unresolved_external_reservation_operations_decision"
    ):
        raise ExternalOperationsDecisionError("decision record role drifted")
    if payload.get("status") != "unresolved_review_only_no_operational_authority":
        raise ExternalOperationsDecisionError("decision record status drifted")
    if payload.get("operations_decision_ready") is not False:
        raise ExternalOperationsDecisionError(
            "operations_decision_ready must remain false"
        )

    _exact_mapping(payload.get("authority"), EXPECTED_AUTHORITY, name="authority")
    _exact_mapping(payload.get("bindings"), EXPECTED_BINDINGS, name="bindings")
    _exact_mapping(
        payload.get("requirements"), EXPECTED_REQUIREMENTS, name="requirements"
    )
    _exact_mapping(
        payload.get("qualification"), EXPECTED_QUALIFICATION, name="qualification"
    )
    _exact_mapping(payload.get("decisions"), EXPECTED_DECISIONS, name="decisions")

    decisions = _mapping(payload["decisions"], name="decisions")
    expected_unresolved = _unresolved_paths(decisions)
    unresolved = payload.get("unresolved_fields")
    if not isinstance(unresolved, list) or tuple(unresolved) != expected_unresolved:
        raise ExternalOperationsDecisionError(
            "unresolved_fields must exactly enumerate every unresolved decision"
        )
    blockers = payload.get("operational_blockers")
    if not isinstance(blockers, list) or tuple(blockers) != EXPECTED_OPERATIONAL_BLOCKERS:
        raise ExternalOperationsDecisionError(
            "operational blockers must remain the exact frozen four"
        )

    projection = dict(payload)
    observed_sha256 = projection.pop("decision_sha256", None)
    if observed_sha256 != _sha256(projection):
        raise ExternalOperationsDecisionError("decision record self-hash is invalid")
    if observed_sha256 != EXPECTED_DECISION_SHA256:
        raise ExternalOperationsDecisionError("decision record identity drifted")

    canonical_text = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    )
    try:
        observed_text = decision_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ExternalOperationsDecisionError(
            f"decision record cannot be re-read: {exc}"
        ) from exc
    if observed_text != canonical_text:
        raise ExternalOperationsDecisionError(
            "decision record encoding is not canonical pretty JSON"
        )

    external_policy = _verify_source_policy(
        external_policy_path,
        name="external reservation policy",
        expected_schema_id=EXPECTED_EXTERNAL_POLICY_SCHEMA_ID,
        expected_policy_sha256=EXPECTED_EXTERNAL_POLICY_SHA256,
    )
    one_shot_policy = _verify_source_policy(
        one_shot_policy_path,
        name="one-shot policy",
        expected_schema_id=EXPECTED_ONE_SHOT_POLICY_SCHEMA_ID,
        expected_policy_sha256=EXPECTED_ONE_SHOT_POLICY_SHA256,
    )
    _verify_source_policy(
        cohort_policy_path,
        name="phase25 cohort policy",
        expected_schema_id=EXPECTED_COHORT_POLICY_SCHEMA_ID,
        expected_policy_sha256=EXPECTED_COHORT_POLICY_SHA256,
    )
    source_bindings = _mapping(
        one_shot_policy.get("source_bindings"), name="one-shot source bindings"
    )
    if source_bindings.get("phase25_cohort_policy_sha256") != (
        EXPECTED_COHORT_POLICY_SHA256
    ):
        raise ExternalOperationsDecisionError(
            "one-shot policy is cross-wired from the frozen cohort policy"
        )
    external_blockers = _derive_external_blockers(external_policy)
    if external_blockers != EXPECTED_OPERATIONAL_BLOCKERS:
        raise ExternalOperationsDecisionError(
            "external policy no longer yields the exact frozen four blockers"
        )

    return {
        "all_authority_false": all(
            value is False for value in EXPECTED_AUTHORITY.values()
        ),
        "decision_sha256": observed_sha256,
        "external_reservation_operational": False,
        "operations_decision_ready": False,
        "operational_blockers": list(external_blockers),
        "unresolved_field_count": len(expected_unresolved),
        "unresolved_fields": list(expected_unresolved),
    }


def _parser() -> argparse.ArgumentParser:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decision-record",
        type=Path,
        default=(
            repo_root
            / "config/engine_v2_source_paired_clearance_external_reservation_"
            "operations_decision.json"
        ),
    )
    parser.add_argument(
        "--external-policy",
        type=Path,
        default=(
            repo_root
            / "config/engine_v2_source_paired_clearance_external_reservation.json"
        ),
    )
    parser.add_argument(
        "--one-shot-policy",
        type=Path,
        default=(
            repo_root / "config/engine_v2_source_paired_clearance_one_shot_ab.json"
        ),
    )
    parser.add_argument(
        "--cohort-policy",
        type=Path,
        default=(repo_root / "config/engine_v2_phase25_cohort_admission.json"),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    report = verify_external_operations_decision(
        decision_path=arguments.decision_record,
        external_policy_path=arguments.external_policy,
        one_shot_policy_path=arguments.one_shot_policy,
        cohort_policy_path=arguments.cohort_policy,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExternalOperationsDecisionError as error:
        print(f"external operations decision rejected: {error}", file=sys.stderr)
        raise SystemExit(2) from error
