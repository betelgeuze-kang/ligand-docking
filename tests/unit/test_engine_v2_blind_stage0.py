from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess

import pytest

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    STAGE0_DIAGNOSTIC_CONTRACT_ID,
    STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA,
    STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID,
    STAGE0_PROTOCOL_ID,
    STAGE0_REQUIRED_SOURCE_FREEZE_PATHS,
    Stage0AdmissionError,
    compute_stage0_policy_sha256,
    compute_stage0_review_subject_sha256,
    current_stage0_host_environment,
    stage0_engine_v2_algorithm_profile,
    verify_stage0_admission,
)
from tools import run_engine_v2_public_redocking_300 as runner
from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    build_inventory,
)


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "missing"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _policy(repo_root: Path, gnina: Path) -> dict[str, object]:
    source_paths = tuple(sorted(STAGE0_REQUIRED_SOURCE_FREEZE_PATHS))
    for relative_path in source_paths:
        source = repo_root / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        if relative_path in {
            "config/engine_v2_public_redocking_contamination_registry.json",
            "config/engine_v2_fresh_redocking_holdout_manifest.json",
        }:
            source.write_text(
                Path(relative_path).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            source.write_text(f"# frozen {relative_path}\n", encoding="utf-8")
    subprocess.run(("git", "init", "-q", str(repo_root)), check=True)
    subprocess.run(
        ("git", "-C", str(repo_root), "config", "user.name", "stage0-test"),
        check=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(repo_root),
            "config",
            "user.email",
            "stage0-test@example.invalid",
        ),
        check=True,
    )
    subprocess.run(
        ("git", "-C", str(repo_root), "add", "--", *source_paths), check=True
    )
    subprocess.run(
        ("git", "-C", str(repo_root), "commit", "-qm", "freeze source"),
        check=True,
    )
    git_head = subprocess.run(
        ("git", "-C", str(repo_root), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        (
            "git",
            "-C",
            str(repo_root),
            "update-ref",
            "refs/remotes/origin/main",
            git_head,
        ),
        check=True,
    )
    threshold_evidence = repo_root / "threshold-evidence.json"
    suite_receipt = repo_root / "suite-classification.json"
    reconciliation_receipt = repo_root / "suite-reconciliation.json"
    attestation = repo_root / "independent-attestation.json"
    ci_receipt = repo_root / "ci-authority.json"
    native_wheel = repo_root / "native-wheel.whl"
    native_wheel.write_bytes(b"native-wheel-test-fixture")
    for workflow in AUTHORITATIVE_WORKFLOWS:
        path = repo_root / workflow
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("name: test\n", encoding="utf-8")
    (repo_root / AUTHORITATIVE_WORKFLOWS[0]).write_text(
        "\n".join(
            (
                "name: test",
                "tests/unit/test_engine_v2_blind_stage0.py",
                "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
                "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
                "tools/verify_engine_v2_public_redocking_stage0.py",
                "tools/classify_engine_v2_stage0_full_suite.py",
                "tools/reconcile_engine_v2_stage0_full_suites.py",
            )
        ),
        encoding="utf-8",
    )
    specialized = repo_root / ".github/workflows/ci-engine-v2-specialized.yml"
    specialized.write_text("name: specialized\n", encoding="utf-8")
    ci_receipt.write_text(
        json.dumps(build_inventory(repo_root), sort_keys=True), encoding="utf-8"
    )
    thresholds = {
        "preparation_input_unsupported_rate": ("max", 0.10),
        "candidate_generation_coverage": ("min", 0.95),
        "proposal_oracle_2a_recovery": ("min", 0.50),
        "top1_selection_failure_given_oracle": ("max", 0.35),
        "top5_selection_failure_given_oracle": ("max", 0.20),
        "invalid_top1_pose_rate": ("max", 0.10),
        "case_level_failure_rate": ("max", 0.15),
    }
    threshold_evidence_payload = {
        "schema_id": "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0",
        "corpus_id": "public-development-test-corpus",
        "case_count": 40,
        "case_ids_sha256": "5" * 64,
        "contains_engineering_smoke": False,
        "contains_primary_holdout": False,
        "contains_fresh_internal_blind_holdout": False,
        "diagnostic_contract_id": STAGE0_DIAGNOSTIC_CONTRACT_ID,
        "sample_size_justification": "test fixture with reviewed development cases",
        "metrics": {
            metric: {
                "operator": operator,
                "observed_estimate": value,
                "proposed_threshold": value,
                "derivation_rule": "reviewed development estimate",
            }
            for metric, (operator, value) in thresholds.items()
        },
        "paired_baseline_engines": ["vina", "gnina"],
        "baseline_noninferiority_margins": {
            "top1_2a_recovery_delta": -0.05,
            "top5_2a_recovery_delta": -0.05,
        },
        "metric_denominator_policy": {
            "preparation_input_unsupported_rate": "all_cases",
            "candidate_generation_coverage": "preparation_success_cases",
            "proposal_oracle_2a_recovery": "preparation_success_cases",
            "top1_selection_failure_given_oracle": "proposal_oracle_success_cases",
            "top5_selection_failure_given_oracle": "proposal_oracle_success_cases",
            "invalid_top1_pose_rate": "preparation_success_cases",
            "case_level_failure_rate": "all_cases",
        },
    }
    threshold_evidence.write_text(
        json.dumps(threshold_evidence_payload, sort_keys=True), encoding="utf-8"
    )
    provenance = {
        "basis": "public_development_corpus",
        "evidence_path": threshold_evidence.name,
        "evidence_sha256": _sha256(threshold_evidence),
        "excluded_sources": ["engineering_smoke", "fresh_internal_blind_holdout"],
    }
    payload: dict[str, object] = {
        "schema_version": 1,
        "protocol_id": STAGE0_PROTOCOL_ID,
        "diagnostic_contract_id": STAGE0_DIAGNOSTIC_CONTRACT_ID,
        "freeze_status": "frozen_before_primary_execution",
        "partition": {
            "source_total": 428,
            "historical_development": 300,
            "fresh_internal_blind_holdout": 128,
        },
        "acceptance_thresholds": {
            metric: {
                "operator": operator,
                "value": value,
                "analysis_scope": "fresh_internal_blind_holdout",
                "denominator": threshold_evidence_payload["metric_denominator_policy"][
                    metric
                ],
                "provenance": dict(provenance),
            }
            for metric, (operator, value) in thresholds.items()
        },
        "baseline_comparison": {
            "engines": ["vina", "gnina"],
            "paired_case_analysis": True,
            "confidence_interval": "percentile_bootstrap_95pct",
            "decision_rule": "lower_ci_ge_noninferiority_margin",
            "noninferiority_margins": {
                "top1_2a_recovery_delta": -0.05,
                "top5_2a_recovery_delta": -0.05,
            },
            "provenance": {
                **provenance,
                "basis": "vina_gnina_development_baseline",
            },
            "runtime_role": "descriptive_only",
            "runtime_is_promotion_gate": False,
        },
        "diagnostic_branching": {
            "preparation_coverage_low": "preparation_track",
            "proposal_oracle_low": "proposal_track",
            "oracle_high_top5_low": "ranking_track",
            "top5_high_top1_low": "scorer_calibration_track",
            "rmsd_good_validity_low": "refinement_validity_track",
            "small_ligand_only_success": "capacity_bias_track",
            "rotor_5plus_drop": "flexible_ligand_search_track",
            "ring_subgroup_drop": "ring_conformer_track",
            "hbond_features_unrealized": "multi_anchor_track",
        },
        "holdout_reuse_policy": "never_use_fresh_128_for_tuning",
        "source_freeze": {
            "algorithm_profile": stage0_engine_v2_algorithm_profile(),
            "diagnostic_contract_pr_number": 211,
            "diagnostic_contract_review_head_sha": (STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA),
            "git_head_sha": git_head,
            "origin_main_sha": git_head,
            "candidate_budget": 64,
            "retained_pose_count": 5,
            "scorer_id": "chemistry_pose_scorer_v1",
            "scorer_backend": "rust_cpu_required",
            "native_thread_count": 1,
            "charge_policy_id": "test-charge-policy",
            "pocket_policy_id": "test-pocket-policy",
            "files": [
                {"path": relative_path, "sha256": _sha256(repo_root / relative_path)}
                for relative_path in source_paths
            ],
        },
        "environment_freeze": {
            "versions": {
                "python": platform.python_version(),
                "torch": _version("torch"),
                "rdkit": _version("rdkit-pypi"),
                "posebusters": _version("posebusters"),
            },
            "gnina_sha256": _sha256(gnina),
            "native_backend": {
                "backend": "rust_cpu_required",
                "distribution_version": "0.2.0rc5",
                "wheel_path": native_wheel.name,
                "wheel_sha256": _sha256(native_wheel),
                "extension_sha256": "8" * 64,
                "cargo_lock_sha256": _sha256(repo_root / "rust_engine_v2/Cargo.lock"),
                "rustc_version": "rustc 1.93.0 (test)",
                "target_triple": "x86_64-unknown-linux-gnu",
                "build_flags": "-C target-cpu=x86-64",
                "thread_count": 1,
            },
            "cpu_policy": {
                "cpu_count": 1,
                "torch_intraop_threads": 1,
                "torch_interop_threads": 1,
            },
            "host": current_stage0_host_environment(),
        },
        "artifact_retention": {
            "engine_case_rows": 384,
            "engine_v2_candidate_diagnostic_slots": 8_192,
            "retention_root": ".betelgeuze/fresh-redocking-128",
            "minimum_free_bytes_before_run": 1_000_000,
            "retain_poses": True,
            "retain_logs": True,
            "retain_receipts": True,
            "retain_candidate_diagnostics": True,
            "retain_fresh_128_report": True,
            "retain_historical_300_development_report": True,
            "retain_environment_snapshot": True,
            "retain_source_freeze": True,
            "retain_external_binary_and_version_log": True,
            "retain_infrastructure_failure_report": True,
            "retain_result_review_receipt": True,
            "sha256_manifest_required": True,
            "owner_only_permissions_required": True,
            "partial_results_nonclaimable": True,
            "cache_cannot_promote_partial_results": True,
            "retain_until_independent_review_complete": True,
        },
        "full_suite_classification": {
            "historical_pr_run": {"failed": 216, "errors": 3},
            "historical_reproduction": {"failed": 215, "errors": 3},
            "current_reproduction": {"failed": 215, "errors": 3},
            "category_counts": {
                "actual_regression": 0,
                "fixture_dependent": 179,
                "host_capability_missing": 20,
                "local_evidence_required": 10,
                "legacy_deterministic": 9,
                "product_fixture_dependent": 0,
            },
            "all_outcomes_classified": True,
            "unclassified_count": 0,
            "actual_regression_review_complete": True,
            "engine_v2_required_suite_green": True,
            "official_tier_definitions_frozen": True,
            "execution_boundary": "official_tiered_suites",
            "classification_receipt_path": suite_receipt.name,
            "classification_receipt_sha256": "0" * 64,
            "historical_count_reconciliation_review_complete": True,
            "historical_count_disposition": (
                "declared_pr_aggregate_unreproducible_and_non_authoritative"
            ),
            "reconciliation_receipt_path": reconciliation_receipt.name,
            "reconciliation_receipt_sha256": "0" * 64,
        },
        "ci_authority": {
            "authoritative_workflows": list(AUTHORITATIVE_WORKFLOWS),
            "new_feature_workflow_policy": "consolidate_into_authoritative_workflows",
            "specialized_workflows_review_complete": True,
            "issue_199_status_reviewed": True,
            "issue_199_state_at_freeze": "open",
            "inventory_receipt_path": ci_receipt.name,
            "inventory_receipt_sha256": _sha256(ci_receipt),
        },
        "governance": {
            "contract_author_id": "author-a",
            "independent_reviewer_id": "reviewer-b",
            "blind_operator_id": "operator-c",
            "contract_review_approved": True,
            "scientific_boundary_review_approved": True,
            "legal_and_license_review_approved": True,
            "operator_runbook_accepted": True,
            "full_suite_classification_review_approved": True,
            "suite_boundaries_approved": True,
            "ci_authority_review_approved": True,
            "primary_holdout_unopened_confirmed": True,
            "thresholds_frozen_before_execution_confirmed": True,
            "github_pr_211_merged_confirmed": True,
            "github_issue_199_status_updated_confirmed": True,
            "historical_216_3_reconciliation_approved": True,
            "frozen_at_utc": "2026-07-29T00:00:00Z",
            "independent_attestation_path": attestation.name,
            "independent_attestation_sha256": "0" * 64,
            "product_execution_enabled": False,
        },
    }
    suite_policy = payload["full_suite_classification"]
    assert isinstance(suite_policy, dict)
    current = dict(suite_policy["current_reproduction"])
    current["nonpassing_total"] = current["failed"] + current["errors"]
    suite_payload = {
        "schema_id": "betelgeuze.engine_v2_stage0_full_suite_classification/1.0.0",
        "source_junit_path": "test-suite.xml",
        "source_junit_sha256": "4" * 64,
        "historical_pr_run": dict(suite_policy["historical_pr_run"]),
        "current_reproduction": current,
        "historical_delta": {"failed": -1, "errors": 0},
        "category_counts": dict(suite_policy["category_counts"]),
        "all_outcomes_classified": True,
        "recommended_execution_boundary": "official_tiered_suites",
        "rows": [],
    }
    suite_rows = suite_payload["rows"]
    assert isinstance(suite_rows, list)
    row_index = 0
    errors_remaining = current["errors"]
    for category, count in suite_policy["category_counts"].items():
        for _ in range(count):
            kind = "error" if errors_remaining else "failure"
            errors_remaining = max(0, errors_remaining - 1)
            suite_rows.append(
                {
                    "category": category,
                    "classname": f"tests.unit.test_stage0_{row_index}",
                    "kind": kind,
                    "message_sha256": f"{row_index:064x}",
                    "name": f"test_outcome_{row_index}",
                    "rule_id": "stage0_test_fixture",
                }
            )
            row_index += 1
    suite_payload["receipt_sha256"] = _canonical_sha256(suite_payload)
    suite_receipt.write_text(
        json.dumps(suite_payload, sort_keys=True), encoding="utf-8"
    )
    suite_policy["classification_receipt_sha256"] = _sha256(suite_receipt)

    reconciliation_payload = {
        "schema_id": ("betelgeuze.engine_v2_stage0_full_suite_reconciliation/1.0.0"),
        "declared_pr_counts": {"failed": 216, "errors": 3},
        "historical_source_commit_sha": STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA,
        "historical_junit_sha256": "6" * 64,
        "historical_reproduction": {"failed": 215, "errors": 3},
        "current_junit_sha256": "7" * 64,
        "current_reproduction": {"failed": 215, "errors": 3},
        "unresolved_declared_failure_count": 1,
        "declared_aggregate_reproduced": False,
        "historical_and_current_row_multisets_equal": True,
        "only_historical_rows": [],
        "only_current_rows": [],
        "review_required": True,
    }
    reconciliation_payload["receipt_sha256"] = _canonical_sha256(reconciliation_payload)
    reconciliation_receipt.write_text(
        json.dumps(reconciliation_payload, sort_keys=True), encoding="utf-8"
    )
    suite_policy["reconciliation_receipt_sha256"] = _sha256(reconciliation_receipt)

    attestation_payload = {
        "schema_id": "betelgeuze.engine_v2_stage0_independent_attestation/1.0.0",
        "review_subject_sha256": compute_stage0_review_subject_sha256(payload),
        "contract_author_id": "author-a",
        "independent_reviewer_id": "reviewer-b",
        "blind_operator_id": "operator-c",
        "decisions": {
            "contract_review_approved": True,
            "scientific_boundary_review_approved": True,
            "legal_and_license_review_approved": True,
            "operator_runbook_accepted": True,
            "full_suite_classification_review_approved": True,
            "suite_boundaries_approved": True,
            "ci_authority_review_approved": True,
            "primary_holdout_unopened_confirmed": True,
            "thresholds_frozen_before_execution_confirmed": True,
            "github_pr_211_merged_confirmed": True,
            "github_issue_199_status_updated_confirmed": True,
            "historical_216_3_reconciliation_approved": True,
        },
        "attested_at_utc": "2026-07-29T00:00:01Z",
    }
    attestation.write_text(
        json.dumps(attestation_payload, sort_keys=True), encoding="utf-8"
    )
    governance = payload["governance"]
    assert isinstance(governance, dict)
    governance["independent_attestation_sha256"] = _sha256(attestation)
    payload["policy_sha256"] = compute_stage0_policy_sha256(payload)
    return payload


def _write_policy(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _native_snapshot(payload: dict[str, object]) -> dict[str, object]:
    environment = payload["environment_freeze"]
    assert isinstance(environment, dict)
    native = environment["native_backend"]
    assert isinstance(native, dict)
    return {
        key: value
        for key, value in native.items()
        if key not in {"wheel_path", "wheel_sha256"}
    }


def _as_solo_policy(payload: dict[str, object], repo_root: Path) -> dict[str, object]:
    decisions = {
        "ci_authority_self_review_completed": True,
        "contract_self_review_completed": True,
        "full_suite_classification_self_review_completed": True,
        "historical_216_3_reconciliation_self_review_completed": True,
        "legal_and_license_self_review_completed": True,
        "native_parity_gate_verified": True,
        "operator_runbook_self_review_completed": True,
        "primary_holdout_unopened_confirmed": True,
        "run_once_no_tuning_policy_accepted": True,
        "scientific_boundary_self_review_completed": True,
        "source_freeze_verified": True,
        "suite_boundaries_self_review_completed": True,
        "thresholds_frozen_before_execution_confirmed": True,
    }
    controls = {
        "automated_policy_verifier_required": True,
        "clean_frozen_commit_required": True,
        "external_review_required_before_public_claim": True,
        "immutable_artifact_manifest_required": True,
        "post_result_retuning_forbidden": True,
        "two_pass_self_review_required": True,
        "review_pass_minimum_separation_hours": 24,
    }
    source_freeze = payload["source_freeze"]
    assert isinstance(source_freeze, dict)
    source_freeze["integration_state"] = "frozen_dedicated_branch_commit"
    source_freeze["unmerged_execution_is_internal_only"] = True
    developer_id = "solo-developer"
    threshold_path = repo_root / "threshold-evidence.json"
    threshold = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold["evidence_sha256"] = _canonical_sha256(threshold)
    threshold_path.write_text(json.dumps(threshold, sort_keys=True), encoding="utf-8")
    thresholds = payload["acceptance_thresholds"]
    assert isinstance(thresholds, dict)
    for row in thresholds.values():
        assert isinstance(row, dict)
        provenance = row["provenance"]
        assert isinstance(provenance, dict)
        provenance["evidence_sha256"] = _sha256(threshold_path)
    baseline = payload["baseline_comparison"]
    assert isinstance(baseline, dict)
    baseline_provenance = baseline["provenance"]
    assert isinstance(baseline_provenance, dict)
    baseline_provenance["evidence_sha256"] = _sha256(threshold_path)
    operational_path = repo_root / "solo-operational.json"
    operational = {
        "schema_id": "betelgeuze.engine_v2_stage0_solo_operational_evidence/1.0.0",
        "developer_id": developer_id,
    }
    operational["receipt_sha256"] = _canonical_sha256(operational)
    operational_path.write_text(
        json.dumps(operational, sort_keys=True), encoding="utf-8"
    )
    reviewed_evidence = {
        "operational_evidence_path": operational_path.name,
        "operational_evidence_file_sha256": _sha256(operational_path),
        "operational_evidence_receipt_sha256": operational["receipt_sha256"],
        "threshold_evidence_path": threshold_path.name,
        "threshold_evidence_file_sha256": _sha256(threshold_path),
        "threshold_evidence_sha256": threshold["evidence_sha256"],
    }
    git_head = source_freeze["git_head_sha"]
    pass1_path = repo_root / "solo-self-review-pass-1.json"
    pass2_path = repo_root / "solo-self-review-pass-2.json"
    pass1: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_stage0_solo_self_review_pass/1.2.0",
        "review_pass": 1,
        "developer_id": developer_id,
        "reviewed_at_utc": "2026-07-27T00:00:00Z",
        "source_freeze_commit_sha": git_head,
        "source_worktree_clean": True,
        "reviewed_evidence": reviewed_evidence,
        "development_gate_results": {
            name: "pass"
            for name in (
                "preparation_input_unsupported_rate",
                "candidate_generation_coverage",
                "proposal_oracle_2a_recovery",
                "top1_selection_failure_given_oracle",
                "top5_selection_failure_given_oracle",
                "invalid_top1_pose_rate",
                "case_level_failure_rate",
            )
        },
        "fresh_internal_blind_holdout_executed": False,
        "self_review_decisions": decisions,
    }
    pass1["receipt_sha256"] = _canonical_sha256(pass1)
    pass1_path.write_text(json.dumps(pass1, sort_keys=True), encoding="utf-8")
    pass2: dict[str, object] = {
        **pass1,
        "review_pass": 2,
        "reviewed_at_utc": "2026-07-28T00:00:00Z",
        "previous_review_pass": {
            "path": pass1_path.name,
            "file_sha256": _sha256(pass1_path),
            "receipt_sha256": pass1["receipt_sha256"],
            "reviewed_at_utc": pass1["reviewed_at_utc"],
        },
    }
    pass2.pop("receipt_sha256")
    pass2["receipt_sha256"] = _canonical_sha256(pass2)
    pass2_path.write_text(json.dumps(pass2, sort_keys=True), encoding="utf-8")
    review_passes = [
        {
            "review_pass": review_pass,
            "path": path.name,
            "file_sha256": _sha256(path),
            "receipt_sha256": review["receipt_sha256"],
            "reviewed_at_utc": review["reviewed_at_utc"],
        }
        for review_pass, path, review in (
            (1, pass1_path, pass1),
            (2, pass2_path, pass2),
        )
    ]
    governance: dict[str, object] = {
        "governance_mode": "solo_developer_controlled",
        "developer_id": developer_id,
        "blind_operator_id": developer_id,
        "independent_reviewer_id": "",
        "independent_review_complete": False,
        "execution_scope": "internal_provisional_evidence_only",
        "public_claims_allowed": False,
        "product_promotion_allowed": False,
        "product_execution_enabled": False,
        "self_review_decisions": decisions,
        "compensating_controls": controls,
        "solo_review_passes": review_passes,
        "reviewed_evidence": reviewed_evidence,
        "first_self_reviewed_at_utc": "2026-07-27T00:00:00Z",
        "second_self_reviewed_at_utc": "2026-07-28T00:00:00Z",
        "frozen_at_utc": "2026-07-29T00:00:00Z",
        "solo_attestation_path": "solo-attestation.json",
        "solo_attestation_sha256": "0" * 64,
    }
    payload["governance"] = governance
    attestation = {
        "schema_id": "betelgeuze.engine_v2_stage0_solo_attestation/1.0.0",
        "review_subject_sha256": compute_stage0_review_subject_sha256(payload),
        "developer_id": "solo-developer",
        "blind_operator_id": "solo-developer",
        "independent_review_complete": False,
        "external_review_required_before_public_claim": True,
        "self_review_decisions": decisions,
        "compensating_controls": controls,
        "solo_review_passes": review_passes,
        "reviewed_evidence": reviewed_evidence,
        "attested_at_utc": "2026-07-29T00:00:01Z",
    }
    attestation_path = repo_root / "solo-attestation.json"
    attestation_path.write_text(
        json.dumps(attestation, sort_keys=True), encoding="utf-8"
    )
    governance["solo_attestation_sha256"] = _sha256(attestation_path)
    payload["policy_sha256"] = compute_stage0_policy_sha256(payload)
    return payload


def test_stage0_admits_only_complete_frozen_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)

    receipt = verify_stage0_admission(
        policy_path,
        repo_root=tmp_path,
        gnina_path=gnina,
        output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
    )

    assert receipt.policy_sha256 == payload["policy_sha256"]
    assert receipt.reviewer_id == "reviewer-b"
    assert receipt.operator_id == "operator-c"


def test_stage0_template_binds_exact_v7_profile_and_source_manifest() -> None:
    template = json.loads(
        Path("config/engine_v2_public_redocking_stage0_freeze.template.json").read_text(
            encoding="utf-8"
        )
    )
    source_freeze = template["source_freeze"]
    assert source_freeze["algorithm_profile"] == stage0_engine_v2_algorithm_profile()
    assert source_freeze["algorithm_profile"]["profile_id"] == (
        STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID
    )
    assert {
        row["path"] for row in source_freeze["files"]
    } == STAGE0_REQUIRED_SOURCE_FREEZE_PATHS
    assert (
        "betelgeuze_engine_v2/docking/torsion_contact_refinement.py"
        in STAGE0_REQUIRED_SOURCE_FREEZE_PATHS
    )


def test_stage0_admits_solo_developer_internal_only_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _as_solo_policy(_policy(tmp_path, gnina), tmp_path)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)

    receipt = verify_stage0_admission(
        policy_path,
        repo_root=tmp_path,
        gnina_path=gnina,
        output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
    )

    assert receipt.governance_mode == "solo_developer_controlled"
    assert receipt.reviewer_id == "solo-developer"
    assert receipt.operator_id == "solo-developer"
    assert receipt.independent_review_complete is False


def test_stage0_rejects_mutated_solo_review_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _as_solo_policy(_policy(tmp_path, gnina), tmp_path)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)
    pass2_path = tmp_path / "solo-self-review-pass-2.json"
    pass2 = json.loads(pass2_path.read_text(encoding="utf-8"))
    pass2["reviewed_at_utc"] = "2026-07-28T00:00:01Z"
    pass2_path.write_text(json.dumps(pass2, sort_keys=True), encoding="utf-8")

    with pytest.raises(Stage0AdmissionError) as raised:
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )

    assert "solo_review_pass_2_artifact_hash_mismatch" in raised.value.blockers


def test_stage0_rejects_failed_development_threshold_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    threshold_path = tmp_path / "threshold-evidence.json"
    threshold_evidence = json.loads(threshold_path.read_text(encoding="utf-8"))
    threshold_evidence["metrics"]["proposal_oracle_2a_recovery"][
        "observed_estimate"
    ] = 0.0
    threshold_evidence.pop("evidence_sha256", None)
    threshold_evidence["evidence_sha256"] = _canonical_sha256(threshold_evidence)
    threshold_path.write_text(
        json.dumps(threshold_evidence, sort_keys=True), encoding="utf-8"
    )
    for row in payload["acceptance_thresholds"].values():
        row["provenance"]["evidence_sha256"] = _sha256(threshold_path)
    payload["baseline_comparison"]["provenance"]["evidence_sha256"] = _sha256(
        threshold_path
    )
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)

    with pytest.raises(
        Stage0AdmissionError,
        match="threshold_development_gate_failed:proposal_oracle_2a_recovery",
    ):
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )


def test_stage0_rejects_unfrozen_threshold_and_self_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    thresholds = payload["acceptance_thresholds"]
    assert isinstance(thresholds, dict)
    proposal_threshold = thresholds["proposal_oracle_2a_recovery"]
    assert isinstance(proposal_threshold, dict)
    proposal_threshold["value"] = None
    _write_policy(policy_path, payload)

    with pytest.raises(Stage0AdmissionError) as raised:
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )

    assert (
        "threshold_value_not_frozen:proposal_oracle_2a_recovery"
        in raised.value.blockers
    )
    assert "stage0_policy_self_hash_mismatch" in raised.value.blockers


def test_stage0_rejects_frozen_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)
    changed = tmp_path / "betelgeuze_engine_v2/docking/scorer_v1.py"
    changed.write_text("# changed after freeze\n", encoding="utf-8")

    with pytest.raises(Stage0AdmissionError) as raised:
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )

    assert (
        "source_freeze_hash_mismatch:betelgeuze_engine_v2/docking/scorer_v1.py"
        in raised.value.blockers
    )


def test_stage0_rejects_missing_v7_source_manifest_row(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    source_freeze = payload["source_freeze"]
    assert isinstance(source_freeze, dict)
    files = source_freeze["files"]
    assert isinstance(files, list)
    source_freeze["files"] = [
        row
        for row in files
        if row["path"] != "betelgeuze_engine_v2/docking/torsion_contact_refinement.py"
    ]
    payload["policy_sha256"] = compute_stage0_policy_sha256(payload)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)

    with pytest.raises(Stage0AdmissionError) as raised:
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )

    assert "source_freeze_path_set_incomplete" in raised.value.blockers


def test_stage0_rejects_algorithm_profile_identity_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina)
    source_freeze = payload["source_freeze"]
    assert isinstance(source_freeze, dict)
    algorithm_profile = source_freeze["algorithm_profile"]
    assert isinstance(algorithm_profile, dict)
    algorithm_profile["runner_id"] = (
        "betelgeuze.engine_v2_public_redocking_300_runner/2.12.0"
    )
    payload["policy_sha256"] = compute_stage0_policy_sha256(payload)
    monkeypatch.setattr(
        "betelgeuze_engine_v2.benchmark.blind_stage0.current_stage0_native_backend",
        lambda: _native_snapshot(payload),
    )
    _write_policy(policy_path, payload)

    with pytest.raises(Stage0AdmissionError) as raised:
        verify_stage0_admission(
            policy_path,
            repo_root=tmp_path,
            gnina_path=gnina,
            output_root=tmp_path / ".betelgeuze/fresh-redocking-128",
        )

    assert "source_runner_id_not_2_13_0" in raised.value.blockers
    assert "source_algorithm_profile_mismatch" in raised.value.blockers


def test_holdout_runner_requires_stage0_before_output_creation(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    with pytest.raises(Stage0AdmissionError) as raised:
        runner.main(
            [
                "--archive",
                str(tmp_path / "missing.tar.gz"),
                "--source-identifiers",
                str(tmp_path / "missing.pdf"),
                "--gnina",
                str(tmp_path / "missing-gnina"),
                "--output-root",
                str(output_root),
                "--case-subset",
                "fresh-internal-blind-holdout",
            ]
        )

    assert raised.value.blockers == ("stage0_policy_required_before_holdout",)
    assert not output_root.exists()
