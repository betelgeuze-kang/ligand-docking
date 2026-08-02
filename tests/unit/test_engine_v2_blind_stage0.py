from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess

import pytest

import betelgeuze_engine_v2.benchmark.blind_stage0 as blind_stage0_contract
import betelgeuze_engine_v2.benchmark.public_redocking_benchmark as benchmark_contract
from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    STAGE0_DIAGNOSTIC_CONTRACT_ID,
    STAGE0_DIAGNOSTIC_REVIEW_HEAD_SHA,
    STAGE0_ENGINE_V2_ALGORITHM_PROFILE_ID,
    STAGE0_PROTOCOL_ID,
    STAGE0_REQUIRED_SOURCE_FREEZE_PATHS,
    Stage0AdmissionError,
    VerifiedStage0Admission,
    compute_stage0_execution_profile_sha256,
    compute_stage0_policy_sha256,
    compute_stage0_review_subject_sha256,
    current_stage0_host_environment,
    stage0_development_source_receipt_binding,
    stage0_engine_implementation_sha256,
    stage0_engine_v2_algorithm_profile,
    stage0_execution_profile_development_provenance,
    stage0_fresh_execution_profile,
    stage0_fresh_execution_runtime_arguments,
    stage0_recompute_development_report,
    verify_stage0_admission,
)
from betelgeuze_engine_v2.benchmark.public_redocking_benchmark import (
    FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS,
    PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS,
    PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS,
    PUBLIC_REDOCKING_RUNNER_ID,
    PublicRedockingCaseResult,
    PublicRedockingEngineV2CandidateDiagnostic,
    PublicRedockingEngineV2Diagnostics,
    VerifiedCaseMaterialization,
    VerifiedPublicRedockingCaseExecution,
    frozen_public_redocking_profiles,
)
from tools import run_engine_v2_public_redocking_300 as runner
from tools.audit_engine_v2_ci_authority import (
    AUTHORITATIVE_WORKFLOWS,
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
    build_inventory,
)


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "missing"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _write_canonical_json(path: Path, payload: object) -> None:
    path.write_bytes(_canonical_bytes(payload) + b"\n")


def _fixture_threshold_contract() -> tuple[
    dict[str, tuple[str, float]], dict[str, object]
]:
    thresholds = {
        "preparation_input_unsupported_rate": ("max", 0.10),
        "candidate_generation_coverage": ("min", 0.95),
        "proposal_oracle_2a_recovery": ("min", 0.50),
        "top1_selection_failure_given_oracle": ("max", 0.35),
        "top5_selection_failure_given_oracle": ("max", 0.20),
        "invalid_top1_pose_rate": ("max", 0.10),
        "case_level_failure_rate": ("max", 0.15),
    }
    payload: dict[str, object] = {
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
    payload["evidence_sha256"] = _canonical_sha256(payload)
    return thresholds, payload


def _python_backend_receipt() -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_id": "betelgeuze.engine_v2_scorer_v1_backend_receipt/1.0.0",
        "backend": "python_reference",
        "backend_version": "1.0.0",
        "implementation_source_sha256": "e" * 64,
        "options_fingerprint_sha256": "f" * 64,
        "extension_sha256": "",
        "cargo_lock_sha256": "",
        "rustc_version": "",
        "target_triple": "",
        "build_flags": [],
        "implicit_fallback_allowed": False,
    }
    payload["receipt_sha256"] = _canonical_sha256(payload)
    return payload


def _zero_score_terms() -> dict[str, str]:
    return {
        name: (0.0).hex()
        for name in (
            "typed_vdw",
            "electrostatics",
            "directional_hbond",
            "hydrophobic_contact",
            "desolvation_proxy",
            "torsion_energy",
            "ligand_strain",
            "weak_pocket_prior",
            "total_score",
        )
    }


def _development_materialization(case_id: str) -> VerifiedCaseMaterialization:
    profile = next(
        profile
        for profile in frozen_public_redocking_profiles()
        if profile.case_id == case_id
    )

    def digest(role: str) -> str:
        return hashlib.sha256(f"{case_id}:{role}".encode("ascii")).hexdigest()

    return VerifiedCaseMaterialization._from_verified_archive(
        case_id=case_id,
        artifact_sha256s={
            "receptor": digest("receptor"),
            "reference": digest("reference"),
            "native": profile.ligand_artifact_sha256,
            "seed": digest("seed"),
        },
        archive_member_names=tuple(
            f"posebusters_benchmark_set/{case_id}/{case_id}_{filename}"
            for filename in (
                "protein.pdb",
                "ligands.sdf",
                "ligand.sdf",
                "ligand_start_conf.sdf",
            )
        ),
        verification_authority=benchmark_contract._VERIFIED_ARCHIVE_AUTHORITY,
    )


def _development_run_root(repo_root: Path) -> Path:
    return repo_root / ".betelgeuze/stage0-development/v7-fixture"


def _development_report_path(repo_root: Path) -> Path:
    return _development_run_root(repo_root) / "development-report.json"


def _development_receipt_path(repo_root: Path, case_id: str) -> Path:
    return _development_run_root(repo_root) / "receipts/engine_v2" / f"{case_id}.json"


def _development_result(
    repo_root: Path,
    case_id: str,
    materialization: VerifiedCaseMaterialization,
) -> PublicRedockingCaseResult:
    candidates = tuple(
        (
            PublicRedockingEngineV2CandidateDiagnostic(
                proposal_index=index,
                status="success",
                proposal_mode="uniform_fallback",
                proposal_fingerprint_sha256=f"{index + 1:064x}",
                coordinate_fingerprint_sha256=f"{index + 193:064x}",
                score=0.0,
                rmsd_angstrom=float(index + 1),
                geometric_valid=True,
                chemical_valid=True,
                pose_artifact_sha256=f"{index + 65:064x}",
                score_terms_receipt_sha256=f"{index + 129:064x}",
                hbond_count=1,
                selection_eligible=True,
                score_term_binary64_hex=_zero_score_terms(),
            )
            if index < 5
            else PublicRedockingEngineV2CandidateDiagnostic(
                proposal_index=index,
                status="failure",
                error_code="fixture_candidate_failure",
            )
        )
        for index in range(64)
    )
    diagnostics = PublicRedockingEngineV2Diagnostics(
        preparation_status="success",
        scorer_backend_receipt=_python_backend_receipt(),
        receptor_atom_count=1,
        ligand_atom_count=1,
        receptor_partial_charge_count=1,
        ligand_partial_charge_count=1,
        receptor_donor_count=1,
        receptor_acceptor_count=1,
        ligand_donor_count=1,
        ligand_acceptor_count=1,
        candidates=candidates,
    )
    paths = {
        "receptor": repo_root / "inputs" / case_id / f"{case_id}_protein.pdb",
        "seed": (repo_root / "inputs" / case_id / f"{case_id}_ligand_start_conf.sdf"),
        "native": repo_root / "inputs" / case_id / f"{case_id}_ligand.sdf",
    }
    command = runner._engine_v2_command(
        case_id,
        paths,
        output=repo_root / "poses/engine_v2" / f"{case_id}.sdf",
        seed=materialization.frozen_case_seed,
    )
    execution_policy = runner._execution_policy_tokens(
        {
            **runner.ENGINE_V2_CPU_POLICY,
            "scorer_backend": "python_reference",
            "scorer_thread_count": 1,
        }
    )
    return PublicRedockingCaseResult(
        case_id=case_id,
        engine_id="engine_v2",
        status="success",
        runtime_seconds=1.0,
        receptor_artifact_sha256=materialization.receptor_artifact_sha256,
        reference_artifact_sha256=materialization.reference_artifact_sha256,
        native_artifact_sha256=materialization.native_artifact_sha256,
        seed_artifact_sha256=materialization.seed_artifact_sha256,
        execution_command=command,
        execution_policy=execution_policy,
        rmsd_angstroms=tuple(float(index + 1) for index in range(5)),
        geometric_valid=(True,) * 5,
        chemical_valid=(True,) * 5,
        pose_artifact_sha256s=tuple(f"{index + 65:064x}" for index in range(5)),
        engine_v2_diagnostics=diagnostics,
    )


def _policy(
    repo_root: Path,
    gnina: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, object]:
    thresholds, threshold_evidence_payload = _fixture_threshold_contract()
    threshold_relative_path = (
        blind_stage0_contract.STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH
    )
    source_paths = tuple(sorted(STAGE0_REQUIRED_SOURCE_FREEZE_PATHS))
    for relative_path in source_paths:
        source = repo_root / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        if relative_path == threshold_relative_path:
            _write_canonical_json(source, threshold_evidence_payload)
        elif relative_path in {
            "config/engine_v2_public_redocking_contamination_registry.json",
            "config/engine_v2_fresh_redocking_holdout_manifest.json",
            "tools/analyze_engine_v2_score_terms.py",
        }:
            source.write_text(
                (Path(__file__).resolve().parents[2] / relative_path).read_text(
                    encoding="utf-8"
                ),
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
    threshold_evidence = repo_root / threshold_relative_path
    monkeypatch.setattr(
        blind_stage0_contract,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_FILE_SHA256",
        _sha256(threshold_evidence),
    )
    monkeypatch.setattr(
        blind_stage0_contract,
        "STAGE0_FROZEN_THRESHOLD_EVIDENCE_SHA256",
        threshold_evidence_payload["evidence_sha256"],
    )
    development_run_root = _development_run_root(repo_root)
    development_report = _development_report_path(repo_root)
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
                "tools/__init__.py",
                "config/engine_v2_public_redocking_stage0_threshold_evidence.json",
                "tests/unit/test_analyze_engine_v2_score_terms.py",
                "tests/unit/test_engine_v2_blind_stage0.py",
                "tests/unit/test_build_engine_v2_stage0_development_gate_ledger.py",
                "tests/unit/test_classify_engine_v2_stage0_full_suite.py",
                "tests/unit/test_reconcile_engine_v2_stage0_full_suites.py",
                "tools/verify_engine_v2_public_redocking_stage0.py",
                "tools/build_engine_v2_stage0_development_gate_ledger.py",
                "tools/classify_engine_v2_stage0_full_suite.py",
                "tools/reconcile_engine_v2_stage0_full_suites.py",
                *CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
            )
        ),
        encoding="utf-8",
    )
    specialized = repo_root / ".github/workflows/ci-engine-v2-specialized.yml"
    specialized.write_text("name: specialized\n", encoding="utf-8")
    ci_receipt.write_text(
        json.dumps(build_inventory(repo_root), sort_keys=True), encoding="utf-8"
    )
    development_case_ids = [
        case_id
        for case_id in PUBLIC_REDOCKING_CONTAMINATED_DEVELOPMENT_CASE_IDS
        if case_id not in PUBLIC_REDOCKING_ENGINEERING_SMOKE_CASE_IDS
    ][:8]
    implementation_sha256 = stage0_engine_implementation_sha256(repo_root)
    source_receipts_sha256: dict[str, str] = {}
    development_results: list[dict[str, object]] = []
    for case_id in development_case_ids:
        materialization = _development_materialization(case_id)
        monkeypatch.setitem(
            benchmark_contract._FROZEN_MATERIALIZATION_RECEIPT_SHA256_BY_CASE,
            case_id,
            materialization.receipt_sha256,
        )
        materialization_path = (
            development_run_root / "receipts/materializations" / f"{case_id}.json"
        )
        materialization_path.parent.mkdir(parents=True, exist_ok=True)
        _write_canonical_json(materialization_path, materialization.to_dict())
        result = _development_result(development_run_root, case_id, materialization)
        execution = VerifiedPublicRedockingCaseExecution._from_fresh_execution(
            result=result,
            materialization_receipt_sha256=materialization.receipt_sha256,
            implementation_sha256=implementation_sha256,
            evaluation_pipeline_sha256="7" * 64,
            execution_environment_sha256="8" * 64,
            verification_authority=benchmark_contract._VERIFIED_EXECUTION_AUTHORITY,
        )
        receipt_path = _development_receipt_path(repo_root, case_id)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        _write_canonical_json(receipt_path, execution.to_dict())
        source_receipts_sha256[receipt_path.relative_to(repo_root).as_posix()] = (
            _sha256(receipt_path)
        )
        development_results.append(result.to_dict())
    development_report_payload = stage0_recompute_development_report(
        repo_root=repo_root,
        results=development_results,
        source_receipts_sha256=source_receipts_sha256,
    )
    source_receipt_binding = stage0_development_source_receipt_binding(
        development_report_payload,
        repo_root=repo_root,
    )
    _write_canonical_json(development_report, development_report_payload)
    development_provenance = stage0_execution_profile_development_provenance(
        development_report_path=development_report.relative_to(repo_root).as_posix(),
        development_report_file_sha256=_sha256(development_report),
        development_report_sha256=str(development_report_payload["report_sha256"]),
        case_ids=development_case_ids,
        scored_case_count=len(development_case_ids),
        source_receipt_binding=source_receipt_binding,
    )
    provenance = {
        "basis": "public_development_corpus",
        "evidence_path": threshold_evidence.relative_to(repo_root).as_posix(),
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
            "execution_profile": stage0_fresh_execution_profile(development_provenance),
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


def _rebind_development_profile(
    payload: dict[str, object],
    development_path: Path,
    development: dict[str, object],
) -> None:
    development.pop("report_sha256", None)
    development["report_sha256"] = _canonical_sha256(development)
    _write_canonical_json(development_path, development)
    source_freeze = payload["source_freeze"]
    assert isinstance(source_freeze, dict)
    previous_profile = source_freeze["execution_profile"]
    assert isinstance(previous_profile, dict)
    provenance = dict(previous_profile["development_provenance"])
    case_ids = development.get("case_ids")
    if isinstance(case_ids, list):
        provenance["case_ids_sha256"] = _canonical_sha256(case_ids)
    source_receipts = development.get("source_receipts_sha256")
    if isinstance(source_receipts, dict):
        provenance["development_source_receipts_sha256"] = _canonical_sha256(
            dict(sorted(source_receipts.items()))
        )
    provenance["development_report_file_sha256"] = _sha256(development_path)
    provenance["development_report_sha256"] = development["report_sha256"]
    source_freeze["execution_profile"] = stage0_fresh_execution_profile(provenance)
    payload["policy_sha256"] = compute_stage0_policy_sha256(payload)


def _reseal_development_receipt(
    *,
    repo_root: Path,
    payload: dict[str, object],
    development_path: Path,
    development: dict[str, object],
    receipt_path: Path,
    receipt: dict[str, object],
) -> None:
    receipt.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _write_canonical_json(receipt_path, receipt)
    relative_path = receipt_path.relative_to(repo_root).as_posix()
    source_receipts = development["source_receipts_sha256"]
    assert isinstance(source_receipts, dict)
    source_receipts[relative_path] = _sha256(receipt_path)
    _rebind_development_profile(payload, development_path, development)


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
    threshold_path = (
        repo_root / blind_stage0_contract.STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH
    )
    threshold = json.loads(threshold_path.read_text(encoding="utf-8"))
    assert threshold["evidence_sha256"] == _canonical_sha256(
        {key: value for key, value in threshold.items() if key != "evidence_sha256"}
    )
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
        "threshold_evidence_path": threshold_path.relative_to(repo_root).as_posix(),
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
    payload = _policy(tmp_path, gnina, monkeypatch)
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
    assert (
        receipt.execution_profile_sha256
        == payload["source_freeze"]["execution_profile"]["profile_sha256"]
    )
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
    execution_profile = source_freeze["execution_profile"]
    assert execution_profile["runtime_arguments"] == (
        stage0_fresh_execution_runtime_arguments()
    )
    assert execution_profile["result_independent_runtime"] is True
    assert execution_profile["development_provenance"]["analysis_scope"] == (
        "historical_contaminated_development_only"
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
    payload = _as_solo_policy(_policy(tmp_path, gnina, monkeypatch), tmp_path)
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
    payload = _as_solo_policy(_policy(tmp_path, gnina, monkeypatch), tmp_path)
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
    payload = _policy(tmp_path, gnina, monkeypatch)
    threshold_path = (
        tmp_path / blind_stage0_contract.STAGE0_FROZEN_THRESHOLD_EVIDENCE_PATH
    )
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
    payload = _policy(tmp_path, gnina, monkeypatch)
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
    payload = _policy(tmp_path, gnina, monkeypatch)
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
    payload = _policy(tmp_path, gnina, monkeypatch)
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
    payload = _policy(tmp_path, gnina, monkeypatch)
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


def test_stage0_rejects_rehashed_execution_profile_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    source_freeze = payload["source_freeze"]
    assert isinstance(source_freeze, dict)
    execution_profile = source_freeze["execution_profile"]
    assert isinstance(execution_profile, dict)
    runtime_arguments = execution_profile["runtime_arguments"]
    assert isinstance(runtime_arguments, dict)
    runtime_arguments["bootstrap_samples"] = 1_999
    execution_profile["profile_sha256"] = compute_stage0_execution_profile_sha256(
        execution_profile
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

    assert "execution_profile_contract_mismatch" in raised.value.blockers


def test_stage0_rejects_fresh_case_in_rebound_development_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    original_case_id = str(development["case_ids"][0])
    fresh_case_id = FROZEN_PUBLIC_REDOCKING_FRESH_HOLDOUT_CASE_IDS[0]
    original_receipt_relative = (
        _development_receipt_path(tmp_path, original_case_id)
        .relative_to(tmp_path)
        .as_posix()
    )
    fresh_receipt_path = _development_receipt_path(tmp_path, fresh_case_id)
    fresh_receipt_relative = fresh_receipt_path.relative_to(tmp_path).as_posix()
    source_receipts = dict(development["source_receipts_sha256"])
    source_receipts.pop(original_receipt_relative)
    source_receipts[fresh_receipt_relative] = "a" * 64
    development["source_receipts_sha256"] = source_receipts
    case_ids = list(development["case_ids"])
    case_ids[0] = fresh_case_id
    development["case_ids"] = sorted(case_ids)
    for case_row in development["cases"]:
        if case_row["case_id"] == original_case_id:
            case_row["case_id"] = fresh_case_id
    development["cases"] = sorted(development["cases"], key=lambda row: row["case_id"])
    _rebind_development_profile(payload, development_path, development)
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

    assert "execution_profile_development_case_outside_corpus" in raised.value.blockers
    assert "execution_profile_development_fresh_overlap" in raised.value.blockers
    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_report_cohort_invalid"
    ) in raised.value.blockers
    assert not fresh_receipt_path.exists()


def test_stage0_rejects_self_hashed_development_report_without_source_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    development.pop("source_receipts_sha256")
    _rebind_development_profile(payload, development_path, development)
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

    assert any(
        blocker
        == (
            "execution_profile_development_source_receipts_invalid:"
            "development_source_receipts_missing"
        )
        for blocker in raised.value.blockers
    )


def test_stage0_rejects_resealed_cross_wired_development_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    first_case_id, second_case_id = development["case_ids"][:2]
    receipt_paths = {
        case_id: _development_receipt_path(tmp_path, case_id)
        for case_id in (first_case_id, second_case_id)
    }
    receipts = {
        case_id: json.loads(path.read_text(encoding="utf-8"))
        for case_id, path in receipt_paths.items()
    }
    receipts[first_case_id]["result"]["case_id"] = second_case_id
    receipts[second_case_id]["result"]["case_id"] = first_case_id
    source_receipts = dict(development["source_receipts_sha256"])
    for case_id, receipt in receipts.items():
        receipt.pop("receipt_sha256")
        receipt["receipt_sha256"] = _canonical_sha256(receipt)
        _write_canonical_json(receipt_paths[case_id], receipt)
        relative_path = receipt_paths[case_id].relative_to(tmp_path).as_posix()
        source_receipts[relative_path] = _sha256(receipt_paths[case_id])
    development["source_receipts_sha256"] = source_receipts
    _rebind_development_profile(payload, development_path, development)
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

    assert any(
        blocker.startswith("execution_profile_development_source_receipts_invalid:")
        for blocker in raised.value.blockers
    )


def test_stage0_rejects_resealed_skeletal_development_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    skeletal_receipt: dict[str, object] = {
        "schema_id": benchmark_contract.PUBLIC_REDOCKING_CASE_EXECUTION_SCHEMA_ID,
        "runner_id": PUBLIC_REDOCKING_RUNNER_ID,
        "implementation_sha256": stage0_engine_implementation_sha256(tmp_path),
        "result": {"case_id": case_id, "engine_id": "engine_v2"},
    }
    skeletal_receipt["receipt_sha256"] = _canonical_sha256(skeletal_receipt)
    _write_canonical_json(receipt_path, skeletal_receipt)
    relative_path = receipt_path.relative_to(tmp_path).as_posix()
    development["source_receipts_sha256"][relative_path] = _sha256(receipt_path)
    _rebind_development_profile(payload, development_path, development)
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_schema_invalid"
    ) in raised.value.blockers


def test_stage0_rejects_resealed_truncated_development_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    truncated_command = [PUBLIC_REDOCKING_RUNNER_ID, "engine_v2", "--case-id"]
    receipt["command"] = truncated_command
    receipt["result"]["execution_command"] = truncated_command
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _write_canonical_json(receipt_path, receipt)
    relative_path = receipt_path.relative_to(tmp_path).as_posix()
    development["source_receipts_sha256"][relative_path] = _sha256(receipt_path)
    _rebind_development_profile(payload, development_path, development)
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_command_invalid"
    ) in raised.value.blockers


def test_stage0_rejects_resealed_external_path_and_extra_command_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    command = list(receipt["command"])
    command[command.index("--receptor") + 1] = (
        f"/attacker/inputs/{case_id}/{case_id}_protein.pdb"
    )
    command.extend(("--unreviewed-mode", "fresh"))
    receipt["command"] = command
    receipt["result"]["execution_command"] = command
    _reseal_development_receipt(
        repo_root=tmp_path,
        payload=payload,
        development_path=development_path,
        development=development,
        receipt_path=receipt_path,
        receipt=receipt,
    )
    monkeypatch.setattr(
        blind_stage0_contract,
        "current_stage0_native_backend",
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_command_invalid"
    ) in raised.value.blockers


@pytest.mark.parametrize(
    "policy_mutation",
    (
        {
            "interaction_refiner": "forged-refiner",
            "fresh_execution_authorized": True,
        },
        {"cpu_count": True, "scorer_thread_count": 1.0},
    ),
    ids=("extra-and-forged", "json-type-confusion"),
)
def test_stage0_rejects_resealed_extra_or_forged_execution_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy_mutation: dict[str, object],
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    execution_policy = dict(receipt["execution_policy"])
    execution_policy.update(policy_mutation)
    receipt["execution_policy"] = execution_policy
    receipt["result"]["execution_policy"] = list(
        runner._execution_policy_tokens(execution_policy)
    )
    _reseal_development_receipt(
        repo_root=tmp_path,
        payload=payload,
        development_path=development_path,
        development=development,
        receipt_path=receipt_path,
        receipt=receipt,
    )
    monkeypatch.setattr(
        blind_stage0_contract,
        "current_stage0_native_backend",
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_policy_invalid"
    ) in raised.value.blockers


def test_stage0_rejects_resealed_development_input_materialization_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["input_sha256s"]["receptor"] = "9" * 64
    receipt["result"]["receptor_artifact_sha256"] = "9" * 64
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _write_canonical_json(receipt_path, receipt)
    relative_path = receipt_path.relative_to(tmp_path).as_posix()
    development["source_receipts_sha256"][relative_path] = _sha256(receipt_path)
    _rebind_development_profile(payload, development_path, development)
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_identity_invalid"
    ) in raised.value.blockers


def test_stage0_rejects_resealed_analyzer_report_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    development["candidate_count"] = int(development["candidate_count"]) + 1
    _rebind_development_profile(payload, development_path, development)
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_report_recomputation_mismatch"
    ) in raised.value.blockers


def test_stage0_rejects_resealed_extra_development_receipt_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gnina = tmp_path / "gnina"
    gnina.write_bytes(b"gnina-test-binary")
    policy_path = tmp_path / "policy.json"
    payload = _policy(tmp_path, gnina, monkeypatch)
    development_path = _development_report_path(tmp_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    case_id = development["case_ids"][0]
    receipt_path = _development_receipt_path(tmp_path, case_id)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["unexpected"] = True
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    _write_canonical_json(receipt_path, receipt)
    relative_path = receipt_path.relative_to(tmp_path).as_posix()
    development["source_receipts_sha256"][relative_path] = _sha256(receipt_path)
    _rebind_development_profile(payload, development_path, development)
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

    assert (
        "execution_profile_development_source_receipts_invalid:"
        "development_source_receipt_schema_invalid"
    ) in raised.value.blockers


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


def test_holdout_runner_rejects_profile_argument_drift_before_output_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_root = tmp_path / "output"
    receipt = VerifiedStage0Admission(
        policy_sha256="1" * 64,
        source_freeze_sha256="2" * 64,
        execution_profile_sha256="3" * 64,
        reviewer_id="reviewer",
        operator_id="operator",
        governance_mode="independent_three_role",
        independent_review_complete=True,
    )
    monkeypatch.setattr(
        runner, "verify_stage0_admission", lambda *args, **kwargs: receipt
    )

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
                "--stage0-policy",
                str(tmp_path / "stage0-policy.json"),
                "--engine-v2-scorer-backend",
                "rust_cpu_required",
                "--seed",
                "2026073000",
                "--timeout-seconds",
                "301",
            ]
        )

    assert raised.value.blockers == (
        "stage0_execution_argument_mismatch:external_timeout_seconds",
    )
    assert not output_root.exists()


def test_holdout_runner_rejects_fresh_slice_before_output_creation(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="explicit case subsets cannot be combined",
    ):
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
                "--limit",
                "1",
            ]
        )

    assert not output_root.exists()


def test_fresh_report_requires_complete_profile_bound_execution_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case_ids = tuple(f"case-{index:03d}" for index in range(128))
    profile_sha256 = "4" * 64

    class _Payload:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def to_dict(self) -> dict[str, object]:
            return json.loads(json.dumps(self.payload))

        def __getattr__(self, name: str) -> object:
            return self.payload[name]

        def recovery(self, top_k: int, threshold: float) -> float:
            del top_k, threshold
            return 0.0

        def valid_recovery(self, top_k: int, threshold: float) -> float:
            del top_k, threshold
            return 0.0

    rows = {
        (engine_id, case_id): _Payload(
            {"engine_id": engine_id, "case_id": case_id, "status": "failure"}
        )
        for engine_id in runner.PUBLIC_REDOCKING_PRIMARY_ENGINES
        for case_id in case_ids
    }
    executions = {
        engine_id: [
            _Payload(
                {
                    "result": rows[(engine_id, case_id)].to_dict(),
                    "execution_policy": {"execution_profile_sha256": profile_sha256},
                }
            )
            for case_id in case_ids
        ]
        for engine_id in runner.PUBLIC_REDOCKING_PRIMARY_ENGINES
    }
    incomplete = dict(executions)
    incomplete[runner.PUBLIC_REDOCKING_PRIMARY_ENGINES[-1]] = incomplete[
        runner.PUBLIC_REDOCKING_PRIMARY_ENGINES[-1]
    ][:-1]
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="receipt ledger is incomplete",
    ):
        runner._fresh_execution_receipt_payloads(
            expected_case_ids=case_ids,
            row_map=rows,
            executions_by_engine=incomplete,
            execution_profile_sha256=profile_sha256,
        )

    mixed_profile = dict(executions)
    mixed_profile["engine_v2"] = [
        _Payload(
            {
                "result": rows[("engine_v2", case_ids[0])].to_dict(),
                "execution_policy": {"execution_profile_sha256": "5" * 64},
            }
        ),
        *executions["engine_v2"][1:],
    ]
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="profile binding is inconsistent",
    ):
        runner._fresh_execution_receipt_payloads(
            expected_case_ids=case_ids,
            row_map=rows,
            executions_by_engine=mixed_profile,
            execution_profile_sha256=profile_sha256,
        )

    wrong_result = dict(executions)
    altered_result = rows[("engine_v2", case_ids[0])].to_dict()
    altered_result["unexpected"] = True
    wrong_result["engine_v2"] = [
        _Payload(
            {
                "result": altered_result,
                "execution_policy": {"execution_profile_sha256": profile_sha256},
            }
        ),
        *executions["engine_v2"][1:],
    ]
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="receipt ledger is cross-wired",
    ):
        runner._fresh_execution_receipt_payloads(
            expected_case_ids=case_ids,
            row_map=rows,
            executions_by_engine=wrong_result,
            execution_profile_sha256=profile_sha256,
        )

    duplicate = dict(executions)
    duplicate["engine_v2"] = [
        *executions["engine_v2"],
        executions["engine_v2"][0],
    ]
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="receipt ledger is cross-wired",
    ):
        runner._fresh_execution_receipt_payloads(
            expected_case_ids=case_ids,
            row_map=rows,
            executions_by_engine=duplicate,
            execution_profile_sha256=profile_sha256,
        )

    unexpected_engine = {**executions, "unexpected": []}
    with pytest.raises(
        runner.PublicRedockingRunnerError,
        match="engine ledger is cross-wired",
    ):
        runner._fresh_execution_receipt_payloads(
            expected_case_ids=case_ids,
            row_map=rows,
            executions_by_engine=unexpected_engine,
            execution_profile_sha256=profile_sha256,
        )

    validated_receipts = runner._fresh_execution_receipt_payloads(
        expected_case_ids=case_ids,
        row_map=rows,
        executions_by_engine=executions,
        execution_profile_sha256=profile_sha256,
    )
    assert len(validated_receipts) == 384

    monkeypatch.setattr(
        runner.benchmark_contract,
        "_derive_scope_all_metrics",
        lambda *args, **kwargs: (),
    )
    profiles = [
        _Payload(
            {
                "case_id": case_id,
                "size_subgroup": "fixture",
                "rotor_subgroup": "fixture",
                "ring_subgroup": "fixture",
            }
        )
        for case_id in case_ids
    ]
    rows_by_engine = {
        engine_id: [rows[(engine_id, case_id)] for case_id in case_ids]
        for engine_id in runner.PUBLIC_REDOCKING_PRIMARY_ENGINES
    }
    report = runner._fresh_internal_report(
        case_ids=case_ids,
        profiles=profiles,
        materializations=[_Payload({"case_id": case_id}) for case_id in case_ids],
        rows_by_engine=rows_by_engine,
        executions_by_engine=executions,
        identities=[
            _Payload({"engine_id": engine_id})
            for engine_id in runner.PUBLIC_REDOCKING_PRIMARY_ENGINES
        ],
        policy=_Payload({"rmsd_threshold_angstrom": 2.0}),
        stage0_receipt=VerifiedStage0Admission(
            policy_sha256="1" * 64,
            source_freeze_sha256="2" * 64,
            execution_profile_sha256=profile_sha256,
            reviewer_id="reviewer",
            operator_id="operator",
            governance_mode="independent_three_role",
            independent_review_complete=True,
        ),
        manifest_sha256="6" * 64,
    )
    assert report["execution_receipts"] == validated_receipts
    assert len(report["execution_receipts"]) == 384
