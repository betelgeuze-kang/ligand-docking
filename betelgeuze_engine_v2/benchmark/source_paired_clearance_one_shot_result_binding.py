"""Require exact durable run-start and clean source state for result writes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys


SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID = (
    "betelgeuze.engine_v2_source_paired_clearance_one_shot_result_binding/1.0.0"
)


def _sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def install_source_paired_clearance_one_shot_result_binding() -> str:
    """Install durable run-start and exact clean-HEAD checks on result writes."""

    marker = "_betelgeuze_source_paired_clearance_one_shot_result_binding_sha256"
    existing = getattr(sys, marker, None)
    if isinstance(existing, str):
        return existing

    from . import source_paired_clearance_one_shot_ab as one_shot
    from . import source_paired_clearance_one_shot_result as result_module
    from .source_paired_clearance_one_shot_binding import (
        EXPECTED_ONE_SHOT_POLICY_SHA256,
        read_durable_receipt,
        require_clean_checkout,
    )

    original_writer = result_module.write_result_once
    if not getattr(original_writer, "_betelgeuze_durable_run_start_binding", False):

        def write_result_once(
            *,
            policy,
            run_start,
            result,
            repository_root,
        ) -> None:
            one_shot.verify_self_hash(
                policy,
                hash_field="policy_sha256",
                name="one-shot policy",
            )
            if policy.get("policy_sha256") != EXPECTED_ONE_SHOT_POLICY_SHA256:
                raise one_shot.OneShotABAuthorityError(
                    "result-writer policy identity is invalid"
                )
            output_root = one_shot.resolve_output_root(
                policy,
                repository_root=repository_root,
            )
            execution = one_shot._mapping(policy.get("execution"), name="execution")
            run_start_path = output_root / str(execution.get("run_start_filename"))
            try:
                durable_run_start = read_durable_receipt(
                    run_start_path,
                    repository_root=repository_root,
                    name="one-shot run-start",
                )
                observed_head = require_clean_checkout(repository_root)
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise one_shot.OneShotABAuthorityError(str(exc)) from exc
            if dict(run_start) != durable_run_start:
                raise one_shot.OneShotABAuthorityError(
                    "run-start argument does not equal the durable run-start"
                )
            if durable_run_start.get("source_commit_git_sha1") != observed_head:
                raise one_shot.OneShotABAuthorityError(
                    "run-start source commit does not equal the clean checkout HEAD"
                )
            original_writer(
                policy=policy,
                run_start=durable_run_start,
                result=result,
                repository_root=repository_root,
            )

        write_result_once._betelgeuze_durable_run_start_binding = True
        result_module.write_result_once = write_result_once

    receipt = _sha256(
        {
            "schema_id": SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID,
            "policy_self_hash_rechecked": True,
            "exact_durable_run_start_required": True,
            "clean_git_checkout_rechecked": True,
            "run_start_source_commit_must_equal_head": True,
            "result_write_remains_atomic_no_overwrite": True,
            "fresh_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )
    setattr(sys, marker, receipt)
    return receipt


__all__ = [
    "SOURCE_PAIRED_CLEARANCE_ONE_SHOT_RESULT_BINDING_SCHEMA_ID",
    "install_source_paired_clearance_one_shot_result_binding",
]
