"""Canonical result binding for the historical one-shot clearance A/B."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import source_paired_clearance_one_shot_result_legacy as _legacy
from .source_paired_clearance_one_shot_ab import (
    EXPECTED_POLICY_SHA256,
    OneShotABAuthorityError,
    _mapping,
    _write_exclusive_json,
    resolve_output_root,
    verify_self_hash,
)
from .source_paired_clearance_one_shot_binding import (
    read_durable_receipt,
    require_clean_checkout,
)


ARM_SUMMARY_SCHEMA_ID = _legacy.ARM_SUMMARY_SCHEMA_ID
RESULT_SCHEMA_ID = _legacy.RESULT_SCHEMA_ID
EXPECTED_BASELINE_PROFILE_ID = _legacy.EXPECTED_BASELINE_PROFILE_ID
EXPECTED_EXPERIMENTAL_PROFILE_ID = _legacy.EXPECTED_EXPERIMENTAL_PROFILE_ID
build_arm_summary = _legacy.build_arm_summary
build_result_document = _legacy.build_result_document
verify_arm_summary = _legacy.verify_arm_summary
verify_result_document = _legacy.verify_result_document


def write_result_once(
    *,
    policy: Mapping[str, Any],
    run_start: Mapping[str, Any],
    result: Mapping[str, Any],
    repository_root: Path,
) -> None:
    """Consume the exact durable run-start and write one verified result."""

    verify_self_hash(policy, hash_field="policy_sha256", name="one-shot policy")
    if policy.get("policy_sha256") != EXPECTED_POLICY_SHA256:
        raise OneShotABAuthorityError("writer policy identity is invalid")
    execution = _mapping(policy.get("execution"), name="execution")
    output_root = resolve_output_root(policy, repository_root=repository_root)
    run_start_path = output_root / str(execution.get("run_start_filename"))
    try:
        durable_run_start = read_durable_receipt(
            run_start_path,
            repository_root=repository_root,
            name="one-shot run-start",
        )
        observed_head = require_clean_checkout(repository_root)
    except (OSError, RuntimeError) as exc:
        raise OneShotABAuthorityError(str(exc)) from exc
    if dict(run_start) != durable_run_start:
        raise OneShotABAuthorityError(
            "run-start argument does not equal the durable run-start"
        )
    if durable_run_start.get("source_commit_git_sha1") != observed_head:
        raise OneShotABAuthorityError(
            "run-start source commit does not equal the clean checkout HEAD"
        )
    verify_result_document(result, run_start=durable_run_start)
    _write_exclusive_json(
        output_root / str(execution.get("result_filename")),
        result,
        repository_root=repository_root,
    )


__all__ = [
    "ARM_SUMMARY_SCHEMA_ID",
    "EXPECTED_BASELINE_PROFILE_ID",
    "EXPECTED_EXPERIMENTAL_PROFILE_ID",
    "RESULT_SCHEMA_ID",
    "build_arm_summary",
    "build_result_document",
    "verify_arm_summary",
    "verify_result_document",
    "write_result_once",
]
