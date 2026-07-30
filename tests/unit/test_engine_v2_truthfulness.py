from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from betelgeuze_engine_v2.capabilities import (
    CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
    PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID,
    capability_snapshot,
)
from betelgeuze_engine_v2.truthfulness import (
    RELEASE_REVIEW_EVIDENCE_SCHEMA_ID,
    ScopedMetricEvidence,
    TruthfulnessContractError,
    capability_truthfulness_snapshot,
    require_capability_truthfulness_snapshot,
    require_scoped_metric_evidence_row,
    require_truthfulness_policy_document,
    truthfulness_policy_document,
    verify_release_review_evidence,
)


POLICY_PATH = Path("config/independent_engine_v2_truthfulness_policy.json")


def test_truthfulness_policy_json_matches_executable_policy() -> None:
    loaded = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert loaded == truthfulness_policy_document()
    assert require_truthfulness_policy_document(loaded) is loaded


def test_lifecycle_snapshot_separates_wiring_from_production_evidence() -> None:
    snapshot = capability_truthfulness_snapshot()
    assert require_capability_truthfulness_snapshot(snapshot) is snapshot
    assert snapshot["claim_policy"] == {
        "production_execution_authorized": False,
        "production_result_receipts_present": False,
        "independent_result_review_complete": False,
        "scientific_validity_green": False,
        "benchmark_validity_green": False,
        "product_qualification_green": False,
        "customer_execution_enabled": False,
        "claim_safe": False,
    }
    rows = snapshot["capabilities"]
    assert len(rows) == 45
    required_fields = {
        "current_state",
        "implemented",
        "component_tested",
        "canonical_entrypoint_applicable",
        "canonical_entrypoint_wired",
        "internal_reference_execution_enabled",
        "production_execution_authorized",
        "production_result_receipt_required",
        "production_result_receipt_present",
        "independent_result_review_required",
        "independent_result_reviewed",
        "calibrated",
        "scientifically_validated",
        "public_evidence_ready",
        "benchmark_validated",
        "product_qualified",
        "customer_execution_enabled",
        "claim_safe",
        "current_blockers",
        "superseded_blockers",
        "base_blocker_source",
    }
    assert all(set(row) == required_fields for row in rows.values())
    assert all(row["implemented"] for row in rows.values())
    assert all(row["component_tested"] for row in rows.values())
    assert all(not row["production_execution_authorized"] for row in rows.values())
    assert all(not row["production_result_receipt_present"] for row in rows.values())
    assert all(not row["independent_result_reviewed"] for row in rows.values())
    assert all(not row["claim_safe"] for row in rows.values())

    for capability_id in (
        CPU_REFERENCE_VALIDATION_PROTOCOL_CAPABILITY_ID,
        CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID,
    ):
        row = rows[capability_id]
        assert row["canonical_entrypoint_applicable"] is True
        assert row["canonical_entrypoint_wired"] is True
        assert row["production_result_receipt_required"] is True
        assert row["independent_result_review_required"] is True
        assert row["production_execution_authorized"] is False
        assert row["production_result_receipt_present"] is False
        assert row["independent_result_reviewed"] is False
        assert "validation_runner_not_implemented" in row["superseded_blockers"]
        assert "result_receipt_writer_not_implemented" in row["superseded_blockers"]
        assert "validation_runner_not_implemented" not in row["current_blockers"]
        assert "result_receipt_writer_not_implemented" not in row["current_blockers"]


def test_public_redocking_runner_is_wired_without_benchmark_promotion() -> None:
    base = capability_snapshot()["capabilities"][PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID]
    assert base["current_state"] == (
        "historical_300_case_contaminated_development_with_fresh_"
        "128_case_internal_provisional_blind_unexecuted_and_"
        "active_v7_refiner"
    )
    assert base["internal_reference_execution_enabled"] is True
    assert "symmetry_mapping_materializer_not_implemented" not in base["blockers"]
    assert "reference_ligand_match_materializer_not_implemented" not in base["blockers"]

    row = capability_truthfulness_snapshot()["capabilities"][
        PUBLIC_BENCHMARK_PROTOCOL_CAPABILITY_ID
    ]
    assert "symmetry_mapping_materializer_not_implemented" in row[
        "superseded_blockers"
    ]
    assert "reference_ligand_match_materializer_not_implemented" in row[
        "superseded_blockers"
    ]
    assert row["canonical_entrypoint_applicable"] is True
    assert row["canonical_entrypoint_wired"] is True
    assert row["production_execution_authorized"] is False
    assert row["production_result_receipt_required"] is True
    assert row["independent_result_review_required"] is True
    assert "symmetry_mapping_materializer_not_implemented" not in row["current_blockers"]
    assert "reference_ligand_match_materializer_not_implemented" not in row[
        "current_blockers"
    ]
    assert (
        "fresh_128_internal_provisional_blind_holdout_not_executed"
        in row["current_blockers"]
    )
    assert "fresh_128_stage0_admission_blocked" in row["current_blockers"]
    assert "primary_298_case_blind_holdout_not_executed" not in row[
        "current_blockers"
    ]
    assert "complete_300_case_descriptive_report_missing" not in row[
        "current_blockers"
    ]
    assert "public_holdout_results_missing" in row["current_blockers"]
    assert row["benchmark_validated"] is False
    assert row["claim_safe"] is False


def test_truthfulness_snapshot_rejects_promotion_tampering() -> None:
    tampered = deepcopy(capability_truthfulness_snapshot())
    row = tampered["capabilities"][CPU_MINIMIZATION_VALIDATION_PROTOCOL_CAPABILITY_ID]
    row["claim_safe"] = True
    row["scientifically_validated"] = True
    row["benchmark_validated"] = True
    row["product_qualified"] = True
    row["customer_execution_enabled"] = True

    with pytest.raises(TruthfulnessContractError, match="drifted"):
        require_capability_truthfulness_snapshot(tampered)


def _metric() -> ScopedMetricEvidence:
    return ScopedMetricEvidence(
        scope_id="restricted-gpcr-a1",
        task_id="ligand-ranking",
        dataset_id="gpcr-a1-independent-repeat",
        dataset_version="2026-07-20",
        split_id="external-holdout-v1",
        target_family="gpcr-a1",
        scorer_id="bounded-ranking-scorer",
        scorer_version="1.2.0",
        engine_commit="a" * 40,
        metric_id="pr-auc",
        value=0.81,
        confidence_interval_low=0.74,
        confidence_interval_high=0.87,
        confidence_level=0.95,
        failure_denominator=128,
        as_of_utc="2026-07-20T04:00:00Z",
        claim_boundary="Restricted GPCR A1 holdout ranking only; no family-wide claim.",
    )


def test_scoped_metric_evidence_requires_full_context_and_exact_identity() -> None:
    payload = _metric().to_dict()
    restored = require_scoped_metric_evidence_row(payload)
    assert restored.to_dict() == payload
    assert len(payload["evidence_sha256"]) == 64

    missing = dict(payload)
    missing.pop("split_id")
    with pytest.raises(TruthfulnessContractError, match="incomplete"):
        require_scoped_metric_evidence_row(missing)

    tampered = deepcopy(payload)
    tampered["value"] = 0.82
    with pytest.raises(TruthfulnessContractError, match="SHA-256"):
        require_scoped_metric_evidence_row(tampered)


def test_scoped_metric_evidence_rejects_unbounded_or_inconsistent_values() -> None:
    with pytest.raises(TruthfulnessContractError, match="inside"):
        replace(_metric(), value=0.95)
    with pytest.raises(TruthfulnessContractError, match="positive integer"):
        replace(_metric(), failure_denominator=0)
    with pytest.raises(TruthfulnessContractError, match="finite"):
        replace(_metric(), value=float("nan"))


def _review_evidence() -> dict[str, object]:
    return {
        "schema_id": RELEASE_REVIEW_EVIDENCE_SCHEMA_ID,
        "repository_full_name": "betelgeuze-kang/ligand-docking",
        "pull_request_number": 157,
        "pull_request_head_sha": "b" * 40,
        "pull_request_author_identity_sha256": "1" * 64,
        "ruleset_id": "engine-v2-protected-evidence-lane",
        "ruleset_sha256": "2" * 64,
        "no_admin_bypass": True,
        "stale_approval_dismissal_enabled": True,
        "code_owner_review_required": True,
        "unresolved_review_thread_count": 0,
        "head_up_to_date": True,
        "change_categories": ["numerical_methods", "security"],
        "review_submissions": [
            {
                "submission_id": "review-001",
                "reviewer_identity_sha256": "3" * 64,
                "role": "codeowner",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T04:01:00Z",
                "dismissed": False,
            },
            {
                "submission_id": "review-002",
                "reviewer_identity_sha256": "4" * 64,
                "role": "numerical_methods",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T04:02:00Z",
                "dismissed": False,
            },
            {
                "submission_id": "review-003",
                "reviewer_identity_sha256": "5" * 64,
                "role": "security",
                "state": "APPROVED",
                "submitted_at_utc": "2026-07-20T04:03:00Z",
                "dismissed": False,
            },
        ],
        "required_checks": [
            {
                "name": "ci-engine-v2-main",
                "conclusion": "success",
                "completed_at_utc": "2026-07-20T04:04:00Z",
            },
            {
                "name": "ci-engine-v2-release-candidate",
                "conclusion": "success",
                "completed_at_utc": "2026-07-20T04:05:00Z",
            },
        ],
        "evidence_generated_at_utc": "2026-07-20T04:06:00Z",
    }


def test_release_review_evidence_verifies_operations_without_promoting_science() -> None:
    verification = verify_release_review_evidence(_review_evidence())
    assert verification["operational_review_evidence_verified"] is True
    assert verification["ruleset_evidence_verified"] is True
    assert verification["independent_human_approval_verified"] is True
    assert verification["required_checks_verified"] is True
    assert verification["scientific_validation_granted"] is False
    assert verification["benchmark_validation_granted"] is False
    assert verification["product_qualification_granted"] is False
    assert verification["customer_execution_enabled"] is False
    assert verification["claim_safe"] is False
    assert len(verification["evidence_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutator", "match"),
    (
        (
            lambda payload: payload.__setitem__("unresolved_review_thread_count", 1),
            "zero unresolved",
        ),
        (
            lambda payload: payload.__setitem__("no_admin_bypass", False),
            "administrator bypass",
        ),
        (
            lambda payload: payload["required_checks"][0].__setitem__(
                "conclusion", "failure"
            ),
            "conclude success",
        ),
        (
            lambda payload: payload["review_submissions"][0].__setitem__(
                "reviewer_identity_sha256", "1" * 64
            ),
            "author cannot",
        ),
        (
            lambda payload: payload.__setitem__(
                "review_submissions",
                [
                    row
                    for row in payload["review_submissions"]
                    if row["role"] != "security"
                ],
            ),
            "security changes",
        ),
    ),
)
def test_release_review_evidence_fails_closed(mutator, match: str) -> None:
    payload = _review_evidence()
    mutator(payload)
    with pytest.raises(TruthfulnessContractError, match=match):
        verify_release_review_evidence(payload)
