#!/usr/bin/env python3
"""Build a claim-safe, time-separated solo Stage 0 self-review record."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


SCHEMA_ID = "betelgeuze.engine_v2_stage0_solo_self_review_pass/1.1.0"
OPERATIONAL_SCHEMA_ID = (
    "betelgeuze.engine_v2_stage0_solo_operational_evidence/1.0.0"
)
THRESHOLD_SCHEMA_ID = "betelgeuze.engine_v2_stage0_threshold_evidence/1.0.0"
DEVELOPMENT_SCHEMA_PREFIX = "betelgeuze.engine_v2_scorer_v1_development_analysis/"
GATE_NAMES = (
    "preparation_input_unsupported_rate",
    "candidate_generation_coverage",
    "proposal_oracle_2a_recovery",
    "top1_selection_failure_given_oracle",
    "top5_selection_failure_given_oracle",
    "invalid_top1_pose_rate",
    "case_level_failure_rate",
)
SELF_REVIEW_DECISIONS = (
    "ci_authority_self_review_completed",
    "contract_self_review_completed",
    "full_suite_classification_self_review_completed",
    "historical_216_3_reconciliation_self_review_completed",
    "legal_and_license_self_review_completed",
    "native_parity_gate_verified",
    "operator_runbook_self_review_completed",
    "primary_holdout_unopened_confirmed",
    "run_once_no_tuning_policy_accepted",
    "scientific_boundary_self_review_completed",
    "source_freeze_verified",
    "suite_boundaries_self_review_completed",
    "thresholds_frozen_before_execution_confirmed",
)


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


def _utc(value: str, *, name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be an explicit UTC timestamp")
    return parsed


def _git(repo_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _gate_results(threshold: Mapping[str, object]) -> dict[str, str]:
    metrics = threshold.get("metrics")
    if not isinstance(metrics, Mapping) or set(metrics) != set(GATE_NAMES):
        raise ValueError("threshold evidence does not contain the seven frozen gates")
    results: dict[str, str] = {}
    for name in GATE_NAMES:
        row = metrics[name]
        if not isinstance(row, Mapping):
            raise ValueError(f"threshold row is invalid: {name}")
        operator = row.get("operator")
        observed = row.get("observed_estimate")
        threshold_value = row.get("proposed_threshold")
        if operator not in {"min", "max"} or type(observed) not in (int, float) or type(
            threshold_value
        ) not in (int, float):
            raise ValueError(f"threshold row is incomplete: {name}")
        passed = (
            float(observed) >= float(threshold_value)
            if operator == "min"
            else float(observed) <= float(threshold_value)
        )
        results[name] = "pass" if passed else "fail"
    return results


def build_review(
    *,
    repo_root: Path,
    operational_path: Path,
    development_path: Path,
    threshold_path: Path,
    native_wheel_path: Path,
    base_wheel_path: Path,
    developer_id: str,
    review_pass: int,
    reviewed_at_utc: str,
    previous_pass_path: Path | None,
) -> dict[str, object]:
    if review_pass not in {1, 2}:
        raise ValueError("review_pass must be 1 or 2")
    reviewed = _utc(reviewed_at_utc, name="reviewed_at_utc")
    operational = _read_json(operational_path)
    development = _read_json(development_path)
    threshold = _read_json(threshold_path)
    if operational.get("schema_id") != OPERATIONAL_SCHEMA_ID:
        raise ValueError("operational evidence schema is invalid")
    if not str(development.get("schema_id", "")).startswith(
        DEVELOPMENT_SCHEMA_PREFIX
    ):
        raise ValueError("development analysis schema is invalid")
    if threshold.get("schema_id") != THRESHOLD_SCHEMA_ID:
        raise ValueError("threshold evidence schema is invalid")
    _verify_self_hash(operational, "receipt_sha256")
    _verify_self_hash(development, "report_sha256")
    _verify_self_hash(threshold, "evidence_sha256")
    if operational.get("developer_id") != developer_id:
        raise ValueError("operational evidence developer identity is cross-wired")
    source_state = operational.get("source_state")
    if not isinstance(source_state, Mapping):
        raise ValueError("operational source state is missing")
    head = _git(repo_root, "rev-parse", "HEAD")
    if source_state.get("git_head_sha") != head:
        raise ValueError("operational evidence is not bound to current HEAD")
    if source_state.get("worktree_clean") is not True:
        raise ValueError("operational evidence did not observe a clean worktree")
    if _git(repo_root, "status", "--porcelain"):
        raise ValueError("solo self-review requires a clean worktree")
    if development.get("contains_fresh_internal_blind_holdout") is not False:
        raise ValueError("development analysis contains the fresh holdout")
    for field in (
        "contains_engineering_smoke",
        "contains_primary_holdout",
        "contains_fresh_internal_blind_holdout",
    ):
        if threshold.get(field) is not False:
            raise ValueError(f"threshold evidence leak boundary is invalid: {field}")
    operator_environment = operational.get("operator_environment")
    if not isinstance(operator_environment, Mapping):
        raise ValueError("operator environment is missing")
    expected_base = operator_environment.get("base_wheel_sha256")
    expected_native = operator_environment.get("native_wheel_sha256")
    if _sha256_path(base_wheel_path) != expected_base:
        raise ValueError("base wheel is cross-wired")
    if _sha256_path(native_wheel_path) != expected_native:
        raise ValueError("native wheel is cross-wired")

    reviewed_evidence = {
        "operational_evidence_path": str(operational_path.relative_to(repo_root)),
        "operational_evidence_file_sha256": _sha256_path(operational_path),
        "operational_evidence_receipt_sha256": operational["receipt_sha256"],
        "scorer_term_development_report_path": str(
            development_path.relative_to(repo_root)
        ),
        "scorer_term_development_report_file_sha256": _sha256_path(
            development_path
        ),
        "scorer_term_development_report_sha256": development["report_sha256"],
        "threshold_evidence_path": str(threshold_path.relative_to(repo_root)),
        "threshold_evidence_file_sha256": _sha256_path(threshold_path),
        "threshold_evidence_sha256": threshold["evidence_sha256"],
        "base_wheel_path": str(base_wheel_path.relative_to(repo_root)),
        "base_wheel_sha256": expected_base,
        "native_wheel_path": str(native_wheel_path.relative_to(repo_root)),
        "native_cp310_wheel_sha256": expected_native,
    }
    first_reviewed = reviewed
    if review_pass == 2:
        if previous_pass_path is None:
            raise ValueError("review pass 2 requires --previous-pass")
        previous = _read_json(previous_pass_path)
        _verify_self_hash(previous, "receipt_sha256")
        if (
            previous.get("schema_id") != SCHEMA_ID
            or previous.get("review_pass") != 1
            or previous.get("developer_id") != developer_id
            or previous.get("source_freeze_commit_sha") != head
            or previous.get("reviewed_evidence") != reviewed_evidence
        ):
            raise ValueError("previous solo review pass is cross-wired")
        first_reviewed = _utc(
            str(previous.get("reviewed_at_utc", "")),
            name="previous reviewed_at_utc",
        )
        if reviewed - first_reviewed < timedelta(hours=24):
            raise ValueError("solo review passes must be separated by at least 24 hours")
    elif previous_pass_path is not None:
        raise ValueError("review pass 1 cannot bind a previous pass")

    gate_results = _gate_results(threshold)
    failed_gates = tuple(
        name for name, status in gate_results.items() if status == "fail"
    )
    blockers = [f"threshold_development_gate_failed:{name}" for name in failed_gates]
    if review_pass == 1:
        blockers.append("second_solo_review_not_time_eligible")
    blockers.extend(
        (
            "posebusters_exact_zenodo_license_metadata_requires_external_confirmation",
            "gnina_binary_redistribution_forbidden_without_gpl_compliance_review",
            "public_and_product_external_review_missing",
            "github_pr_211_not_merged",
            "github_issue_199_not_dispositioned",
        )
    )
    review: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "review_pass": review_pass,
        "reviewed_at_utc": reviewed_at_utc,
        "first_reviewed_at_utc": first_reviewed.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "next_review_not_before_utc": (
            (reviewed + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if review_pass == 1
            else None
        ),
        "developer_id": developer_id,
        "source_freeze_commit_sha": head,
        "source_worktree_clean": True,
        "reviewed_evidence": reviewed_evidence,
        "development_gate_results": gate_results,
        "self_review_decisions": {name: True for name in SELF_REVIEW_DECISIONS},
        "fresh_internal_blind_holdout_executed": False,
        "independent_review_complete": False,
        "internal_provisional_execution_admitted": False,
        "public_claims_allowed": False,
        "product_promotion_allowed": False,
        "product_execution_enabled": False,
        "legal_and_license_review": {
            "review_outcome": (
                "internal_execution_only_with_public_and_redistribution_gates"
            ),
            "legal_advice_claimed": False,
            "posebusters_public_sources_identify_cc_by_4_0": True,
            "posebusters_archive_readme_contains_license_text": False,
            "posebusters_external_confirmation_required": True,
            "posebusters_redistribution_allowed": False,
            "gnina_internal_benchmark_invocation_only": True,
            "gnina_binary_redistribution_allowed": False,
            "gnina_external_gpl_compliance_review_required": True,
        },
        "open_blockers": blockers,
        "notes": [
            "This is a compensating-control self-review, not independent attestation.",
            "Development-gate failures prohibit fresh holdout execution.",
            "No public, product, legal, or scientific-validation claim is made.",
        ],
    }
    review["receipt_sha256"] = hashlib.sha256(_canonical_bytes(review)).hexdigest()
    return review


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operational-evidence", required=True, type=Path)
    parser.add_argument("--development-diagnostics", required=True, type=Path)
    parser.add_argument("--threshold-evidence", required=True, type=Path)
    parser.add_argument("--native-wheel", required=True, type=Path)
    parser.add_argument("--base-wheel", required=True, type=Path)
    parser.add_argument("--developer-id", required=True)
    parser.add_argument("--review-pass", required=True, type=int, choices=(1, 2))
    parser.add_argument("--reviewed-at-utc", required=True)
    parser.add_argument("--previous-pass", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    review = build_review(
        repo_root=repo_root,
        operational_path=arguments.operational_evidence.resolve(),
        development_path=arguments.development_diagnostics.resolve(),
        threshold_path=arguments.threshold_evidence.resolve(),
        native_wheel_path=arguments.native_wheel.resolve(),
        base_wheel_path=arguments.base_wheel.resolve(),
        developer_id=arguments.developer_id,
        review_pass=arguments.review_pass,
        reviewed_at_utc=arguments.reviewed_at_utc,
        previous_pass_path=(
            None if arguments.previous_pass is None else arguments.previous_pass.resolve()
        ),
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(review) + b"\n")
    print(review["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
