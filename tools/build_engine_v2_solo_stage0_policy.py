#!/usr/bin/env python3
"""Assemble a fail-closed internal-only solo Stage 0 policy and attestation."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    compute_stage0_policy_sha256,
    compute_stage0_review_subject_sha256,
    stage0_development_source_receipt_binding,
    stage0_execution_profile_development_provenance,
    stage0_fresh_execution_profile,
)
from tools.run_engine_v2_public_redocking_300 import (
    RUNNER_ID,
    _engine_source_sha256,
)


SELF_REVIEW_SCHEMA_ID = "betelgeuze.engine_v2_stage0_solo_self_review_pass/1.3.0"
OPERATIONAL_SCHEMA_ID = (
    "betelgeuze.engine_v2_stage0_solo_operational_evidence/1.1.0"
)
THRESHOLD_SCHEMA_ID = "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
ATTESTATION_SCHEMA_ID = "betelgeuze.engine_v2_stage0_solo_attestation/1.0.0"
REQUIRED_ENGINES = ("engine_v2", "vina", "gnina")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _verify_self_hash(payload: Mapping[str, object], field: str) -> None:
    projection = dict(payload)
    observed = projection.pop(field, None)
    expected = hashlib.sha256(_canonical_bytes(projection)).hexdigest()
    if observed != expected:
        raise ValueError(f"self-hash mismatch: {field}")


def _utc(value: object, *, name: str) -> datetime:
    parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an explicit UTC timestamp")
    return parsed


def _git(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _repo_file(repo_root: Path, value: object, *, name: str) -> Path:
    raw = Path(str(value or ""))
    resolved = (raw if raw.is_absolute() else repo_root / raw).resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{name} escapes the repository") from exc
    if not resolved.is_file():
        raise ValueError(f"{name} is missing: {resolved}")
    return resolved


def _repo_output(repo_root: Path, path: Path, *, name: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(f"{name} escapes the repository") from exc
    if resolved.exists():
        raise ValueError(f"{name} already exists: {resolved}")
    return resolved


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _bound_artifact(
    repo_root: Path,
    owner: Mapping[str, object],
    *,
    path_field: str,
    sha_field: str,
    name: str,
) -> tuple[Path, dict[str, object]]:
    path = _repo_file(repo_root, owner.get(path_field), name=name)
    if _sha256_path(path) != owner.get(sha_field):
        raise ValueError(f"{name} hash is cross-wired")
    payload = _read_json(path)
    _verify_self_hash(payload, "receipt_sha256")
    return path, payload


def _verify_review_chain(
    *,
    repo_root: Path,
    operational_path: Path,
    threshold_path: Path,
    pass1_path: Path,
    pass2_path: Path,
    developer_id: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
    operational = _read_json(operational_path)
    threshold = _read_json(threshold_path)
    pass1 = _read_json(pass1_path)
    pass2 = _read_json(pass2_path)
    if operational.get("schema_id") != OPERATIONAL_SCHEMA_ID:
        raise ValueError("operational evidence schema is invalid")
    if threshold.get("schema_id") != THRESHOLD_SCHEMA_ID:
        raise ValueError("threshold evidence schema is invalid")
    if pass1.get("schema_id") != SELF_REVIEW_SCHEMA_ID or pass2.get(
        "schema_id"
    ) != SELF_REVIEW_SCHEMA_ID:
        raise ValueError("solo self-review schema is invalid")
    _verify_self_hash(operational, "receipt_sha256")
    _verify_self_hash(threshold, "evidence_sha256")
    _verify_self_hash(pass1, "receipt_sha256")
    _verify_self_hash(pass2, "receipt_sha256")
    if (
        pass1.get("review_pass") != 1
        or pass2.get("review_pass") != 2
        or pass1.get("developer_id") != developer_id
        or pass2.get("developer_id") != developer_id
        or operational.get("developer_id") != developer_id
    ):
        raise ValueError("solo review identities are cross-wired")
    if pass1.get("reviewed_evidence") != pass2.get("reviewed_evidence"):
        raise ValueError("solo review passes do not bind identical evidence")
    previous = pass2.get("previous_review_pass")
    if not isinstance(previous, Mapping):
        raise ValueError("pass 2 does not bind pass 1")
    expected_previous = {
        "path": str(pass1_path.relative_to(repo_root)),
        "file_sha256": _sha256_path(pass1_path),
        "receipt_sha256": pass1["receipt_sha256"],
        "reviewed_at_utc": pass1["reviewed_at_utc"],
    }
    if dict(previous) != expected_previous:
        raise ValueError("pass 1 hash chain is cross-wired")
    first = _utc(pass1.get("reviewed_at_utc"), name="pass 1 reviewed_at_utc")
    second = _utc(pass2.get("reviewed_at_utc"), name="pass 2 reviewed_at_utc")
    if second - first < timedelta(hours=24):
        raise ValueError("solo review passes are less than 24 hours apart")
    gate_results = pass2.get("development_gate_results")
    if not isinstance(gate_results, Mapping) or not gate_results or any(
        value != "pass" for value in gate_results.values()
    ):
        raise ValueError("development gates do not admit Stage 0 assembly")
    if (
        pass1.get("fresh_internal_blind_holdout_executed") is not False
        or pass2.get("fresh_internal_blind_holdout_executed") is not False
    ):
        raise ValueError("solo review reports a previously opened holdout")
    reviewed = pass2.get("reviewed_evidence")
    if not isinstance(reviewed, Mapping):
        raise ValueError("reviewed evidence is missing")
    for path, file_hash, label in (
        (operational_path, reviewed.get("operational_evidence_file_sha256"), "operational"),
        (threshold_path, reviewed.get("threshold_evidence_file_sha256"), "threshold"),
    ):
        if _sha256_path(path) != file_hash:
            raise ValueError(f"{label} review binding changed")
    return operational, threshold, pass1, pass2


def build_policy(
    *,
    repo_root: Path,
    template_path: Path,
    operational_path: Path,
    threshold_path: Path,
    pass1_path: Path,
    pass2_path: Path,
    developer_id: str,
    issue_199_state: str,
    frozen_at_utc: str,
    policy_output: Path,
    attestation_output: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    if issue_199_state not in {"open", "closed"}:
        raise ValueError("issue_199_state must be open or closed")
    if policy_output.resolve() == attestation_output.resolve():
        raise ValueError("policy and attestation outputs must be distinct")
    if _git(repo_root, "status", "--porcelain"):
        raise ValueError("Stage 0 policy assembly requires a clean worktree")
    head = _git(repo_root, "rev-parse", "HEAD")
    origin_main = _git(repo_root, "rev-parse", "refs/remotes/origin/main")
    if head != origin_main:
        raise ValueError("Stage 0 policy requires the exact origin/main commit")
    operational, threshold, pass1, pass2 = _verify_review_chain(
        repo_root=repo_root,
        operational_path=operational_path,
        threshold_path=threshold_path,
        pass1_path=pass1_path,
        pass2_path=pass2_path,
        developer_id=developer_id,
    )
    source_state = operational.get("source_state")
    if not isinstance(source_state, Mapping):
        raise ValueError("operational source state is missing")
    if (
        source_state.get("git_head_sha") != head
        or source_state.get("origin_main_sha") != origin_main
        or source_state.get("dedicated_branch_internal_only") is not False
        or source_state.get("worktree_clean") is not True
        or source_state.get("runner_id") != RUNNER_ID
        or source_state.get("engine_implementation_sha256")
        != _engine_source_sha256(repo_root)
        or pass1.get("source_freeze_commit_sha") != head
        or pass2.get("source_freeze_commit_sha") != head
    ):
        raise ValueError("solo evidence is not bound to the current clean source")

    template = _read_json(template_path)
    policy = deepcopy(template)
    policy["freeze_status"] = "frozen_before_primary_execution"

    threshold_relative = str(threshold_path.relative_to(repo_root))
    threshold_file_sha256 = _sha256_path(threshold_path)
    metrics = threshold.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("threshold metric rows are missing")
    policy_thresholds = policy.get("acceptance_thresholds")
    if not isinstance(policy_thresholds, dict) or set(policy_thresholds) != set(metrics):
        raise ValueError("policy template threshold axes are cross-wired")
    for name, row in policy_thresholds.items():
        metric = metrics[name]
        if not isinstance(row, dict) or not isinstance(metric, Mapping):
            raise ValueError("threshold row is invalid")
        row["value"] = metric.get("proposed_threshold")
        row["provenance"] = {
            "basis": "public_development_corpus",
            "evidence_path": threshold_relative,
            "evidence_sha256": threshold_file_sha256,
            "excluded_sources": [
                "engineering_smoke",
                "fresh_internal_blind_holdout",
            ],
        }
    baseline = policy.get("baseline_comparison")
    if not isinstance(baseline, dict):
        raise ValueError("baseline policy is missing")
    baseline["noninferiority_margins"] = threshold.get(
        "baseline_noninferiority_margins"
    )
    baseline["provenance"] = {
        "basis": "vina_gnina_development_baseline",
        "evidence_path": threshold_relative,
        "evidence_sha256": threshold_file_sha256,
        "excluded_sources": [
            "engineering_smoke",
            "fresh_internal_blind_holdout",
        ],
    }

    source_freeze = policy.get("source_freeze")
    if not isinstance(source_freeze, dict):
        raise ValueError("source freeze template is missing")
    reviewed_evidence = pass2.get("reviewed_evidence")
    if not isinstance(reviewed_evidence, Mapping):
        raise ValueError("solo reviewed development evidence is missing")
    development_path = _repo_file(
        repo_root,
        reviewed_evidence.get("scorer_term_development_report_path"),
        name="scorer-term development report",
    )
    development_file_sha256 = _sha256_path(development_path)
    if development_file_sha256 != reviewed_evidence.get(
        "scorer_term_development_report_file_sha256"
    ):
        raise ValueError("scorer-term development report file hash is cross-wired")
    development = _read_json(development_path)
    _verify_self_hash(development, "report_sha256")
    if development.get("report_sha256") != reviewed_evidence.get(
        "scorer_term_development_report_sha256"
    ):
        raise ValueError("scorer-term development report receipt is cross-wired")
    case_ids = development.get("case_ids")
    scored_case_count = development.get("scored_case_count")
    if (
        development.get("analysis_scope")
        != "historical_contaminated_development_only"
        or development.get("contains_fresh_internal_blind_holdout") is not False
        or development.get("claimable") is not False
        or development.get("sufficient_for_track_decision") is not True
        or not isinstance(case_ids, list)
        or any(not isinstance(case_id, str) for case_id in case_ids)
        or type(scored_case_count) is not int
    ):
        raise ValueError("scorer-term development report is not profile-safe")
    development_provenance = stage0_execution_profile_development_provenance(
        development_report_path=str(development_path.relative_to(repo_root)),
        development_report_file_sha256=development_file_sha256,
        development_report_sha256=str(development["report_sha256"]),
        case_ids=case_ids,
        scored_case_count=scored_case_count,
        source_receipt_binding=stage0_development_source_receipt_binding(
            development,
            repo_root=repo_root,
        ),
    )
    source_freeze["execution_profile"] = stage0_fresh_execution_profile(
        development_provenance
    )
    source_freeze.update(
        {
            "git_head_sha": head,
            "origin_main_sha": origin_main,
            "integration_state": "exact_origin_main_commit",
            "unmerged_execution_is_internal_only": False,
        }
    )
    files = source_freeze.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("source freeze path template is missing")
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("source freeze row is invalid")
        path = _repo_file(repo_root, row.get("path"), name="source freeze file")
        row["sha256"] = _sha256_path(path)

    environment = policy.get("environment_freeze")
    operator_environment = operational.get("operator_environment")
    if not isinstance(environment, dict) or not isinstance(
        operator_environment, Mapping
    ):
        raise ValueError("operator environment is missing")
    native = operator_environment.get("native_backend")
    if not isinstance(native, Mapping):
        raise ValueError("native operator environment is missing")
    reviewed_artifact_bindings = {
        "base_wheel_sha256": operator_environment.get("base_wheel_sha256"),
        "native_cp310_wheel_sha256": operator_environment.get(
            "native_wheel_sha256"
        ),
        "base_wheel_sbom_sha256": operator_environment.get(
            "base_wheel_sbom_sha256"
        ),
        "native_wheel_sbom_sha256": operator_environment.get(
            "native_wheel_sbom_sha256"
        ),
    }
    if any(
        reviewed_evidence.get(field) != expected
        for field, expected in reviewed_artifact_bindings.items()
    ):
        raise ValueError("solo-reviewed wheel or SBOM binding is cross-wired")
    environment.update(
        {
            "versions": dict(operator_environment["versions"]),
            "gnina_sha256": operator_environment["gnina_sha256"],
            "host": dict(operator_environment["host"]),
            "cpu_policy": {
                "cpu_count": 1,
                "torch_intraop_threads": 1,
                "torch_interop_threads": 1,
            },
            "python_wheel": {
                "wheel_path": operator_environment["base_wheel_path"],
                "wheel_sha256": operator_environment["base_wheel_sha256"],
                "sbom_path": operator_environment["base_wheel_sbom_path"],
                "sbom_sha256": operator_environment[
                    "base_wheel_sbom_sha256"
                ],
            },
            "native_backend": {
                "backend": native["backend"],
                "distribution_version": native["distribution_version"],
                "wheel_path": operator_environment["native_wheel_path"],
                "wheel_sha256": operator_environment["native_wheel_sha256"],
                "sbom_path": operator_environment["native_wheel_sbom_path"],
                "sbom_sha256": operator_environment[
                    "native_wheel_sbom_sha256"
                ],
                "extension_path": native["extension_path"],
                "extension_sha256": native["extension_sha256"],
                "cargo_lock_sha256": native["cargo_lock_sha256"],
                "rustc_version": native["rustc_version"],
                "target_triple": native["target_triple"],
                "build_flags": native["build_flags"],
                "thread_count": 1,
            },
        }
    )

    retention = policy.get("artifact_retention")
    operational_retention = operational.get("artifact_retention")
    runbook = operational.get("operator_runbook")
    if not isinstance(retention, dict) or not isinstance(
        operational_retention, Mapping
    ) or not isinstance(runbook, Mapping):
        raise ValueError("artifact retention evidence is missing")
    retention.update(
        {
            "engine_case_rows": operational_retention["expected_engine_case_rows"],
            "engine_v2_candidate_diagnostic_slots": operational_retention[
                "expected_engine_v2_candidate_slots"
            ],
            "retention_root": runbook["output_root"],
            "minimum_free_bytes_before_run": operational_retention[
                "minimum_free_bytes_before_run"
            ],
        }
    )
    for field in (
        "retain_poses",
        "retain_logs",
        "retain_receipts",
        "retain_candidate_diagnostics",
        "retain_fresh_128_report",
        "retain_historical_300_development_report",
        "retain_environment_snapshot",
        "retain_source_freeze",
        "retain_external_binary_and_version_log",
        "retain_infrastructure_failure_report",
        "retain_result_review_receipt",
        "sha256_manifest_required",
        "owner_only_permissions_required",
        "partial_results_nonclaimable",
        "cache_cannot_promote_partial_results",
        "retain_until_independent_review_complete",
    ):
        retention[field] = True

    full_suite = policy.get("full_suite_classification")
    disposition = operational.get("full_suite_disposition")
    if not isinstance(full_suite, dict) or not isinstance(disposition, Mapping):
        raise ValueError("full-suite evidence is missing")
    classification_path, classification = _bound_artifact(
        repo_root,
        disposition,
        path_field="classification_receipt_path",
        sha_field="classification_receipt_sha256",
        name="full-suite classification",
    )
    reconciliation_path, reconciliation = _bound_artifact(
        repo_root,
        disposition,
        path_field="reconciliation_receipt_path",
        sha_field="reconciliation_receipt_sha256",
        name="full-suite reconciliation",
    )
    full_suite.update(
        {
            "historical_pr_run": classification["historical_pr_run"],
            "historical_reproduction": reconciliation["historical_reproduction"],
            "current_reproduction": {
                "failed": classification["current_reproduction"]["failed"],
                "errors": classification["current_reproduction"]["errors"],
            },
            "category_counts": classification["category_counts"],
            "all_outcomes_classified": True,
            "unclassified_count": 0,
            "actual_regression_review_complete": True,
            "engine_v2_required_suite_green": True,
            "official_tier_definitions_frozen": True,
            "execution_boundary": "official_tiered_suites",
            "classification_receipt_path": str(
                classification_path.relative_to(repo_root)
            ),
            "classification_receipt_sha256": _sha256_path(classification_path),
            "historical_count_reconciliation_review_complete": True,
            "historical_count_disposition": (
                "declared_pr_aggregate_unreproducible_and_non_authoritative"
            ),
            "reconciliation_receipt_path": str(
                reconciliation_path.relative_to(repo_root)
            ),
            "reconciliation_receipt_sha256": _sha256_path(reconciliation_path),
        }
    )

    ci = policy.get("ci_authority")
    operational_ci = operational.get("ci_authority")
    if not isinstance(ci, dict) or not isinstance(operational_ci, Mapping):
        raise ValueError("CI authority evidence is missing")
    inventory_path, inventory = _bound_artifact(
        repo_root,
        operational_ci,
        path_field="inventory_receipt_path",
        sha_field="inventory_receipt_sha256",
        name="CI authority inventory",
    )
    ci.update(
        {
            "authoritative_workflows": inventory["authoritative_workflows"],
            "new_feature_workflow_policy": (
                "consolidate_into_authoritative_workflows"
            ),
            "specialized_workflows_review_complete": True,
            "issue_199_status_reviewed": True,
            "issue_199_state_at_freeze": issue_199_state,
            "inventory_receipt_path": str(inventory_path.relative_to(repo_root)),
            "inventory_receipt_sha256": _sha256_path(inventory_path),
        }
    )

    frozen = _utc(frozen_at_utc, name="frozen_at_utc")
    second = _utc(pass2.get("reviewed_at_utc"), name="pass 2 reviewed_at_utc")
    if frozen < second:
        raise ValueError("policy freeze predates solo review pass 2")
    decisions = pass2.get("self_review_decisions")
    if not isinstance(decisions, Mapping) or any(
        value is not True for value in decisions.values()
    ):
        raise ValueError("solo self-review decisions are incomplete")
    governance = policy.get("governance")
    if not isinstance(governance, dict):
        raise ValueError("governance policy is missing")
    controls = {
        "automated_policy_verifier_required": True,
        "clean_frozen_commit_required": True,
        "external_review_required_before_public_claim": True,
        "immutable_artifact_manifest_required": True,
        "post_result_retuning_forbidden": True,
        "two_pass_self_review_required": True,
        "review_pass_minimum_separation_hours": 24,
    }
    review_pass_bindings = [
        {
            "review_pass": review_pass,
            "path": str(path.relative_to(repo_root)),
            "file_sha256": _sha256_path(path),
            "receipt_sha256": payload["receipt_sha256"],
            "reviewed_at_utc": payload["reviewed_at_utc"],
        }
        for review_pass, path, payload in (
            (1, pass1_path, pass1),
            (2, pass2_path, pass2),
        )
    ]
    governance.update(
        {
            "governance_mode": "solo_developer_controlled",
            "developer_id": developer_id,
            "blind_operator_id": developer_id,
            "independent_reviewer_id": "",
            "independent_review_complete": False,
            "execution_scope": "internal_provisional_evidence_only",
            "public_claims_allowed": False,
            "product_promotion_allowed": False,
            "product_execution_enabled": False,
            "self_review_decisions": dict(decisions),
            "compensating_controls": controls,
            "solo_review_passes": review_pass_bindings,
            "reviewed_evidence": dict(reviewed_evidence),
            "first_self_reviewed_at_utc": pass1["reviewed_at_utc"],
            "second_self_reviewed_at_utc": pass2["reviewed_at_utc"],
            "frozen_at_utc": frozen_at_utc,
        }
    )
    governance.pop("solo_attestation_path", None)
    governance.pop("solo_attestation_sha256", None)
    review_subject = compute_stage0_review_subject_sha256(policy)
    attestation: dict[str, object] = {
        "schema_id": ATTESTATION_SCHEMA_ID,
        "review_subject_sha256": review_subject,
        "developer_id": developer_id,
        "blind_operator_id": developer_id,
        "independent_review_complete": False,
        "external_review_required_before_public_claim": True,
        "self_review_decisions": dict(decisions),
        "compensating_controls": controls,
        "solo_review_passes": review_pass_bindings,
        "reviewed_evidence": dict(reviewed_evidence),
        "attested_at_utc": frozen_at_utc,
    }
    attestation_bytes = _canonical_bytes(attestation) + b"\n"
    attestation_sha256 = hashlib.sha256(attestation_bytes).hexdigest()
    governance["solo_attestation_path"] = str(
        attestation_output.relative_to(repo_root)
    )
    governance["solo_attestation_sha256"] = attestation_sha256
    policy["policy_sha256"] = compute_stage0_policy_sha256(policy)
    policy_bytes = _canonical_bytes(policy) + b"\n"
    _write_exclusive(attestation_output, attestation_bytes)
    _write_exclusive(policy_output, policy_bytes)
    return policy, attestation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--operational-evidence", required=True, type=Path)
    parser.add_argument("--threshold-evidence", required=True, type=Path)
    parser.add_argument("--self-review-pass-1", required=True, type=Path)
    parser.add_argument("--self-review-pass-2", required=True, type=Path)
    parser.add_argument("--developer-id", required=True)
    parser.add_argument("--issue-199-state", required=True, choices=("open", "closed"))
    parser.add_argument("--frozen-at-utc", required=True)
    parser.add_argument("--policy-output", required=True, type=Path)
    parser.add_argument("--attestation-output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    policy_output = _repo_output(
        repo_root, arguments.policy_output, name="policy output"
    )
    attestation_output = _repo_output(
        repo_root, arguments.attestation_output, name="attestation output"
    )
    policy, attestation = build_policy(
        repo_root=repo_root,
        template_path=arguments.template.resolve(),
        operational_path=arguments.operational_evidence.resolve(),
        threshold_path=arguments.threshold_evidence.resolve(),
        pass1_path=arguments.self_review_pass_1.resolve(),
        pass2_path=arguments.self_review_pass_2.resolve(),
        developer_id=arguments.developer_id,
        issue_199_state=arguments.issue_199_state,
        frozen_at_utc=arguments.frozen_at_utc,
        policy_output=policy_output,
        attestation_output=attestation_output,
    )
    print(
        json.dumps(
            {
                "attestation_sha256": _sha256_path(attestation_output),
                "policy_sha256": policy["policy_sha256"],
                "review_subject_sha256": attestation["review_subject_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
