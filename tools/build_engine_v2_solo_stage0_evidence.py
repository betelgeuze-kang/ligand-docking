#!/usr/bin/env python3
"""Build a claim-safe solo Stage 0 evidence packet without opening the holdout."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
from typing import Mapping, Sequence

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    current_stage0_host_environment,
    current_stage0_native_backend,
    stage0_fresh_execution_runtime_arguments,
)
from tools.run_engine_v2_public_redocking_300 import (
    RUNNER_ID,
    _engine_source_sha256,
)


SCHEMA_ID = "betelgeuze.engine_v2_stage0_solo_operational_evidence/1.0.0"


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
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _verify_self_hash(payload: Mapping[str, object], field: str) -> None:
    projection = dict(payload)
    observed = projection.pop(field, None)
    expected = hashlib.sha256(_canonical_bytes(projection)).hexdigest()
    if observed != expected:
        raise ValueError(f"receipt self-hash mismatch: {field}")


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


def build_packet(
    *,
    repo_root: Path,
    classification_path: Path,
    reconciliation_path: Path,
    ci_inventory_path: Path,
    gnina_path: Path,
    native_wheel_path: Path,
    base_wheel_path: Path,
    developer_id: str,
    reviewed_at_utc: str,
) -> dict[str, object]:
    execution_arguments = stage0_fresh_execution_runtime_arguments()
    classification = _read_json(classification_path)
    reconciliation = _read_json(reconciliation_path)
    ci_inventory = _read_json(ci_inventory_path)
    _verify_self_hash(classification, "receipt_sha256")
    _verify_self_hash(reconciliation, "receipt_sha256")
    _verify_self_hash(ci_inventory, "receipt_sha256")
    rows = classification.get("rows")
    if not isinstance(rows, list):
        raise ValueError("classification rows are missing")
    actual_regressions = tuple(
        row
        for row in rows
        if isinstance(row, Mapping) and row.get("category") == "actual_regression"
    )
    if len(actual_regressions) != 49:
        raise ValueError("expected 49 conservatively classified regression rows")
    if (
        reconciliation.get("historical_and_current_row_multisets_equal") is not True
        or reconciliation.get("only_current_rows") != []
        or reconciliation.get("only_historical_rows") != []
    ):
        raise ValueError("historical/current full-suite rows are not reconciled")
    if not gnina_path.is_file() or not native_wheel_path.is_file() or not base_wheel_path.is_file():
        raise ValueError("operator binary or wheel is missing")
    reviewed = datetime.fromisoformat(reviewed_at_utc.replace("Z", "+00:00"))
    if reviewed.tzinfo is None or reviewed.utcoffset() != timezone.utc.utcoffset(reviewed):
        raise ValueError("reviewed_at_utc must be an explicit UTC timestamp")
    head = _git(repo_root, "rev-parse", "HEAD")
    origin_main = _git(repo_root, "rev-parse", "refs/remotes/origin/main")
    dirty = _git(repo_root, "status", "--porcelain")
    free_bytes = shutil.disk_usage(repo_root).free
    minimum_free_bytes = 20 * 1024**3
    if free_bytes < minimum_free_bytes:
        raise ValueError("less than 20 GiB is available for the frozen run")
    packet: dict[str, object] = {
        "schema_id": SCHEMA_ID,
        "reviewed_at_utc": reviewed_at_utc,
        "developer_id": developer_id,
        "source_state": {
            "git_head_sha": head,
            "origin_main_sha": origin_main,
            "engine_implementation_sha256": _engine_source_sha256(repo_root),
            "runner_id": RUNNER_ID,
            "dedicated_branch_internal_only": head != origin_main,
            "worktree_clean": dirty == "",
            "worktree_status_sha256": hashlib.sha256(dirty.encode("utf-8")).hexdigest(),
        },
        "full_suite_disposition": {
            "classification_receipt_path": str(classification_path.relative_to(repo_root)),
            "classification_receipt_sha256": _sha256_path(classification_path),
            "reconciliation_receipt_path": str(reconciliation_path.relative_to(repo_root)),
            "reconciliation_receipt_sha256": _sha256_path(reconciliation_path),
            "historical_and_current_row_multisets_equal": True,
            "current_only_row_count": 0,
            "historical_only_row_count": 0,
            "conservative_actual_regression_row_count": len(actual_regressions),
            "actual_regression_disposition": (
                "preexisting_unresolved_behavior_debt_not_attributed_to_the_current_"
                "engine_v2_change_and_retained_in_nightly_visibility"
            ),
            "monorepo_green_claimed": False,
            "engine_v2_required_boundary_may_be_evaluated_separately": True,
            "row_identities": [
                {
                    "classname": str(row["classname"]),
                    "name": str(row["name"]),
                    "kind": str(row["kind"]),
                    "message_sha256": str(row["message_sha256"]),
                }
                for row in actual_regressions
            ],
        },
        "suite_boundaries": {
            "execution_boundary": "official_tiered_suites",
            "fast": "every_pr_lint_type_and_focused_unit",
            "engine_required": "engine_v2_change_complete_deterministic_v2_suite",
            "package": "package_or_schema_change_wheel_clean_install_and_sbom",
            "integration": "main_or_merge_queue_engine_plus_selected_legacy_product",
            "nightly": "broad_monorepo_fixture_rich_with_explicit_typed_nonpassing_rows",
            "evidence": "manual_approval_benchmark_or_validation_execution",
            "fixture_outcomes": [
                "missing_fixture",
                "local_evidence_required",
                "host_capability_missing",
            ],
            "silent_skip_for_fixture_or_host_state_allowed": False,
        },
        "ci_authority": {
            "inventory_receipt_path": str(ci_inventory_path.relative_to(repo_root)),
            "inventory_receipt_sha256": _sha256_path(ci_inventory_path),
            "authoritative_workflows": list(ci_inventory["authoritative_workflows"]),
            "specialized_workflow_count": len(ci_inventory["specialized_workflows"]),
            "specialized_workflows_hidden": False,
            "new_feature_workflow_policy": "consolidate_into_authoritative_workflows",
            "issue_199_external_state_mutated": False,
        },
        "operator_environment": {
            "versions": {
                "python": platform.python_version(),
                "torch": metadata.version("torch"),
                "rdkit": metadata.version("rdkit-pypi"),
                "posebusters": metadata.version("posebusters"),
            },
            "host": current_stage0_host_environment(),
            "native_backend": current_stage0_native_backend(),
            "gnina_sha256": _sha256_path(gnina_path),
            "native_wheel_path": str(native_wheel_path.relative_to(repo_root)),
            "native_wheel_sha256": _sha256_path(native_wheel_path),
            "base_wheel_path": str(base_wheel_path.relative_to(repo_root)),
            "base_wheel_sha256": _sha256_path(base_wheel_path),
            "cpu_policy": {
                "cpu_count": 1,
                "torch_intraop_threads": 1,
                "torch_interop_threads": 1,
                "native_thread_count": 1,
            },
        },
        "operator_runbook": {
            "case_subset": "fresh-internal-blind-holdout",
            "engine_v2_scorer_backend": "rust_cpu_required",
            "output_root": ".betelgeuze/fresh-redocking-128",
            "single_execution_only": True,
            "cache_read_or_partial_promotion_allowed": False,
            "implicit_backend_fallback_allowed": False,
            "post_result_threshold_or_algorithm_tuning_allowed": False,
            "abort_on_infrastructure_or_integrity_failure": True,
            "quarantine_partial_outputs": True,
            "public_claims_allowed": False,
            "product_promotion_allowed": False,
            "execution_runtime_arguments": execution_arguments,
            "command_template": [
                "python3",
                "tools/run_engine_v2_public_redocking_300.py",
                "--case-subset",
                "fresh-internal-blind-holdout",
                "--stage0-policy",
                ".betelgeuze/stage0/frozen-solo-stage0-policy.json",
                "--engine-v2-scorer-backend",
                "rust_cpu_required",
                "--seed",
                str(execution_arguments["seed"]),
                "--timeout-seconds",
                str(execution_arguments["external_timeout_seconds"]),
                "--bootstrap-samples",
                str(execution_arguments["bootstrap_samples"]),
                "--start-index",
                str(execution_arguments["start_index"]),
                "--limit",
                str(execution_arguments["limit"]),
                "--output-root",
                ".betelgeuze/fresh-redocking-128",
            ],
        },
        "artifact_retention": {
            "expected_engine_case_rows": 384,
            "expected_engine_v2_candidate_slots": 8192,
            "minimum_free_bytes_before_run": minimum_free_bytes,
            "observed_free_bytes_at_review": free_bytes,
            "retain": [
                "poses",
                "logs",
                "receipts",
                "candidate_diagnostics",
                "fresh_128_report",
                "historical_development_report",
                "environment_snapshot",
                "source_freeze",
                "external_binary_version_log",
                "infrastructure_failure_report",
                "result_review_receipt",
            ],
            "sha256_manifest_required": True,
            "owner_only_permissions_required": True,
            "retain_until_external_review_complete": True,
        },
        "claim_boundaries": {
            "independent_review_complete": False,
            "internal_provisional_execution_only": True,
            "public_claim_requires_external_review": True,
            "product_promotion_requires_external_review": True,
            "gnina_binary_redistribution_allowed": False,
            "fresh_holdout_opened_or_executed_by_this_tool": False,
        },
    }
    packet["receipt_sha256"] = hashlib.sha256(_canonical_bytes(packet)).hexdigest()
    return packet


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classification", required=True, type=Path)
    parser.add_argument("--reconciliation", required=True, type=Path)
    parser.add_argument("--ci-inventory", required=True, type=Path)
    parser.add_argument("--gnina", required=True, type=Path)
    parser.add_argument("--native-wheel", required=True, type=Path)
    parser.add_argument("--base-wheel", required=True, type=Path)
    parser.add_argument("--developer-id", required=True)
    parser.add_argument("--reviewed-at-utc", required=True)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]
    packet = build_packet(
        repo_root=repo_root,
        classification_path=arguments.classification.resolve(),
        reconciliation_path=arguments.reconciliation.resolve(),
        ci_inventory_path=arguments.ci_inventory.resolve(),
        gnina_path=arguments.gnina.resolve(),
        native_wheel_path=arguments.native_wheel.resolve(),
        base_wheel_path=arguments.base_wheel.resolve(),
        developer_id=arguments.developer_id,
        reviewed_at_utc=arguments.reviewed_at_utc,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_bytes(_canonical_bytes(packet) + b"\n")
    print(packet["receipt_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
