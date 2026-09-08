"""License and release-bundle projection assertions for the product goal suite."""

from __future__ import annotations


def _split_delimited(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [
            part.strip()
            for part in value.replace(";", ",").split(",")
            if part.strip()
        ]
    return []


def _assert_license_legal_boundary_fields(*, observed: dict, artifact: dict) -> None:
    audit_bool_fields = [
        "gate_present",
        "recorded",
        "product_license_hash_matches_approved_source",
        "third_party_license_review_gate_ready",
        "legal_advice_provided",
        "external_state_mutated",
    ]
    audit_int_fields = [
        "hard_blocker_count",
        "operator_review_item_count",
        "third_party_license_review_gate_blocker_count",
    ]
    audit_text_fields = [
        "status",
        "product_license_path",
        "approved_license_text_source",
        "spdx_license_id",
        "copyright_holder",
        "third_party_license_review_gate_status",
        "viewer_third_party_notice_path",
    ]
    for field in audit_bool_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] is (artifact.get(key) is True)
    for field in audit_int_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] == int(artifact.get(key) or 0)
    for field in audit_text_fields:
        key = f"self_hosted_license_distribution_audit_{field}"
        assert observed[key] == artifact.get(key, "")
    assert observed[
        "self_hosted_license_distribution_audit_third_party_dual_license_assets"
    ] == _split_delimited(
        artifact.get("self_hosted_license_distribution_audit_third_party_dual_license_assets")
    )

    audit_guard_missing_reasons = []
    if artifact.get("self_hosted_license_distribution_audit_gate_present") is not True:
        audit_guard_missing_reasons.append("audit_gate_not_present")
    if artifact.get("self_hosted_license_distribution_audit_recorded") is not True:
        audit_guard_missing_reasons.append("audit_not_recorded")
    if artifact.get("self_hosted_license_distribution_audit_status") != (
        "self_hosted_license_distribution_audit_recorded"
    ):
        audit_guard_missing_reasons.append("audit_status_not_recorded")
    if artifact.get(
        "self_hosted_license_distribution_audit_product_license_hash_matches_approved_source"
    ) is not True:
        audit_guard_missing_reasons.append("product_license_hash_mismatch")
    if int(artifact.get("self_hosted_license_distribution_audit_hard_blocker_count") or 0) != 0:
        audit_guard_missing_reasons.append("hard_blockers_present")
    if int(artifact.get("self_hosted_license_distribution_audit_operator_review_item_count") or 0) < 1:
        audit_guard_missing_reasons.append("operator_review_boundary_missing")
    if artifact.get(
        "self_hosted_license_distribution_audit_third_party_license_review_gate_ready"
    ) is not True:
        audit_guard_missing_reasons.append("third_party_review_gate_not_ready")
    if int(
        artifact.get(
            "self_hosted_license_distribution_audit_third_party_license_review_gate_blocker_count"
        )
        or 0
    ) != 0:
        audit_guard_missing_reasons.append("third_party_review_blockers_present")
    if artifact.get("self_hosted_license_distribution_audit_legal_advice_provided") is True:
        audit_guard_missing_reasons.append("legal_advice_claimed")
    if artifact.get("self_hosted_license_distribution_audit_external_state_mutated") is True:
        audit_guard_missing_reasons.append("audit_mutated_external_state")
    assert observed["self_hosted_license_distribution_audit_boundary_guard_ready"] is (
        not audit_guard_missing_reasons
    )
    assert (
        observed["self_hosted_license_distribution_audit_boundary_guard_missing_reasons"]
        == audit_guard_missing_reasons
    )

    review_bool_fields = [
        "present",
        "recorded",
        "ready",
        "review_csv_present",
        "asset_modified",
        "legal_advice_provided",
        "external_state_mutated",
    ]
    review_int_fields = [
        "review_row_count",
        "expected_review_asset_count",
        "approved_review_asset_count",
        "missing_review_asset_count",
        "deferred_review_asset_count",
        "blocker_count",
        "source_hard_blocker_count",
        "source_operator_review_item_count",
    ]
    review_text_fields = [
        "status",
        "review_csv",
        "operator_template_csv",
        "approval_token_required",
        "source_license_audit_status",
    ]
    for field in review_bool_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] is (artifact.get(key) is True)
    for field in review_int_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] == int(artifact.get(key) or 0)
    for field in review_text_fields:
        key = f"third_party_license_review_gate_{field}"
        assert observed[key] == artifact.get(key, "")
    assert observed["third_party_license_review_gate_approved_assets"] == _split_delimited(
        artifact.get("third_party_license_review_gate_approved_assets")
    )
    assert observed["third_party_license_review_gate_allowed_license_paths"] == _split_delimited(
        artifact.get("third_party_license_review_gate_allowed_license_paths")
    )

    review_guard_missing_reasons = []
    if artifact.get("third_party_license_review_gate_present") is not True:
        review_guard_missing_reasons.append("review_gate_not_present")
    if artifact.get("third_party_license_review_gate_recorded") is not True:
        review_guard_missing_reasons.append("review_gate_not_recorded")
    if artifact.get("third_party_license_review_gate_ready") is not True:
        review_guard_missing_reasons.append("review_gate_not_ready")
    if artifact.get("third_party_license_review_gate_status") != "third_party_license_review_gate_ready":
        review_guard_missing_reasons.append("review_gate_status_not_ready")
    if artifact.get("third_party_license_review_gate_review_csv_present") is not True:
        review_guard_missing_reasons.append("review_csv_missing")
    if not artifact.get("third_party_license_review_gate_review_csv"):
        review_guard_missing_reasons.append("review_csv_path_missing")
    if not artifact.get("third_party_license_review_gate_operator_template_csv"):
        review_guard_missing_reasons.append("operator_template_missing")
    if not artifact.get("third_party_license_review_gate_approval_token_required"):
        review_guard_missing_reasons.append("approval_token_missing")
    if int(artifact.get("third_party_license_review_gate_review_row_count") or 0) < 1:
        review_guard_missing_reasons.append("review_row_missing")
    if int(artifact.get("third_party_license_review_gate_blocker_count") or 0) != 0:
        review_guard_missing_reasons.append("review_blockers_present")
    if int(artifact.get("third_party_license_review_gate_missing_review_asset_count") or 0) != 0:
        review_guard_missing_reasons.append("missing_review_assets_present")
    if int(artifact.get("third_party_license_review_gate_deferred_review_asset_count") or 0) != 0:
        review_guard_missing_reasons.append("deferred_review_assets_present")
    if artifact.get("third_party_license_review_gate_asset_modified") is True:
        review_guard_missing_reasons.append("asset_modified")
    if artifact.get("third_party_license_review_gate_legal_advice_provided") is True:
        review_guard_missing_reasons.append("legal_advice_claimed")
    if artifact.get("third_party_license_review_gate_external_state_mutated") is True:
        review_guard_missing_reasons.append("review_mutated_external_state")
    assert observed["third_party_license_review_gate_boundary_guard_ready"] is (
        not review_guard_missing_reasons
    )
    assert (
        observed["third_party_license_review_gate_boundary_guard_missing_reasons"]
        == review_guard_missing_reasons
    )


def _assert_product_release_bundle_fields(*, observed: dict, artifact: dict) -> None:
    policy = artifact.get("operator_promotion_policy")
    policy = policy if isinstance(policy, dict) else {}
    checks = artifact.get("checks")
    checks = [row for row in checks if isinstance(row, dict)] if isinstance(checks, list) else []
    failed_check_ids = [
        str(row.get("check") or "").strip()
        for row in checks
        if row.get("passed") is not True and str(row.get("check") or "").strip()
    ]
    approval_tokens = policy.get("approval_tokens_required") or []
    must_review_fields = policy.get("must_review_fields") or []
    required_before_execution = policy.get("required_before_execution") or []

    assert observed["product_release_bundle_status"] == artifact.get("status", "")
    assert observed["product_release_bundle_ready"] is (
        artifact.get("release_bundle_ready") is True
    )
    assert observed["product_release_bundle_artifact_path"].endswith(
        "runs/product_release_bundle_current.json"
    )
    assert observed["product_release_bundle_release_id"] == artifact.get("release_id", "")
    assert observed["product_release_bundle_bundle_version"] == artifact.get(
        "bundle_version", ""
    )
    assert observed["product_release_bundle_artifact_count"] == int(
        artifact.get("artifact_count") or 0
    )
    assert observed["product_release_bundle_check_count"] == int(
        artifact.get("check_count") or 0
    )
    assert observed["product_release_bundle_pass_count"] == int(
        artifact.get("pass_count") or 0
    )
    assert observed["product_release_bundle_blocker_count"] == int(
        artifact.get("blocker_count") or 0
    )
    assert observed["product_release_bundle_failed_check_ids"] == failed_check_ids
    assert observed["product_release_bundle_operator_policy_status"] == policy.get(
        "status", ""
    )
    assert observed[
        "product_release_bundle_operator_policy_approval_tokens_required"
    ] == approval_tokens
    assert observed["product_release_bundle_operator_policy_must_review_fields"] == (
        must_review_fields
    )
    assert observed[
        "product_release_bundle_operator_policy_required_before_execution"
    ] == required_before_execution
    assert observed[
        "product_release_bundle_operator_policy_external_state_mutation_allowed"
    ] is (policy.get("external_state_mutation_allowed") is True)

    guard_missing_reasons = []
    if artifact.get("status") != "release_bundle_ready_for_operator_review":
        guard_missing_reasons.append("bundle_status_not_ready")
    if artifact.get("release_bundle_ready") is not True:
        guard_missing_reasons.append("bundle_ready_flag_not_true")
    if int(artifact.get("blocker_count") or 0) != 0:
        guard_missing_reasons.append("blockers_present")
    if int(artifact.get("check_count") or 0) == 0 or int(
        artifact.get("pass_count") or 0
    ) != int(artifact.get("check_count") or 0):
        guard_missing_reasons.append("checks_not_all_passed")
    if failed_check_ids:
        guard_missing_reasons.append("failed_checks_present")
    if int(artifact.get("artifact_count") or 0) < 1:
        guard_missing_reasons.append("artifacts_missing")
    if policy.get("status") != "operator_approval_required":
        guard_missing_reasons.append("operator_policy_not_approval_required")
    if policy.get("external_state_mutation_allowed") is True:
        guard_missing_reasons.append("external_state_mutation_allowed")
    for token in (
        "APPROVE_PRODUCT_ROLLOUT",
        "APPROVE_HOSTED_PRODUCT_API_EXPOSURE",
        "MODEL_REGISTRY_SIGNING_KEY",
        "API_RESULT_MANIFEST_SIGNING_KEY",
    ):
        if token not in approval_tokens:
            guard_missing_reasons.append("approval_tokens_missing")
            break
    for field in ("target", "action", "impact", "risk", "rollback", "verification"):
        if field not in must_review_fields:
            guard_missing_reasons.append("must_review_fields_missing")
            break
    if len(required_before_execution) < 1:
        guard_missing_reasons.append("required_before_execution_missing")
    assert observed["product_release_bundle_operator_review_guard_ready"] is (
        not guard_missing_reasons
    )
    assert (
        observed["product_release_bundle_operator_review_guard_missing_reasons"]
        == guard_missing_reasons
    )
