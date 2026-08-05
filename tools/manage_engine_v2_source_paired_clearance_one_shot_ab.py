#!/usr/bin/env python3
"""Manage the frozen one-shot historical clearance A/B authority.

This command never runs docking. An external operator/runtime must generate the
complete baseline, experimental, and cross-arm evidence JSON documents after a
successful ``reserve`` and ``start`` sequence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (  # noqa: E402
    EXPECTED_OUTPUT_ROOT,
    OneShotABAuthorityError,
    authorization_decision,
    create_run_start_receipt,
    load_json_document,
    reserve_one_shot_execution,
    resolve_output_root,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_evidence import (  # noqa: E402
    verify_external_evidence_file,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result import (  # noqa: E402
    build_result_document,
    write_result_once,
)


def _json(path: Path, *, name: str) -> dict[str, Any]:
    return load_json_document(path.resolve(), name=name)


def _source_documents(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _json(
            repo_root / "config/engine_v2_source_paired_clearance_one_shot_ab.json",
            name="one-shot policy",
        ),
        _json(
            repo_root / "config/engine_v2_phase25_cohort_admission.json",
            name="Phase 2.5 cohort policy",
        ),
        _json(
            repo_root / "config/engine_v2_source_paired_clearance_activation.json",
            name="clearance activation policy",
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_REPO_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Verify authority without writing state.")

    reserve = subparsers.add_parser("reserve", help="Atomically reserve run ordinal one.")
    reserve.add_argument("--source-commit", required=True)
    reserve.add_argument("--operator-id", required=True)
    reserve.add_argument("--execution-environment-sha256", required=True)

    subparsers.add_parser("start", help="Atomically create the run-start receipt.")

    write_result = subparsers.add_parser(
        "write-result",
        help="Bind externally generated two-arm evidence and write result once.",
    )
    write_result.add_argument("--baseline-arm", type=Path, required=True)
    write_result.add_argument("--baseline-evidence", type=Path, required=True)
    write_result.add_argument("--experimental-arm", type=Path, required=True)
    write_result.add_argument("--experimental-evidence", type=Path, required=True)
    write_result.add_argument("--cross-arm", type=Path, required=True)
    write_result.add_argument("--cross-arm-evidence", type=Path, required=True)
    return parser


def _load_fixed_receipt(
    output_root: Path,
    filename: str,
    *,
    name: str,
) -> dict[str, Any]:
    return _json(output_root / filename, name=name)


def main() -> int:
    arguments = _parser().parse_args()
    repo_root = arguments.repo_root.resolve(strict=True)
    policy, phase25, activation = _source_documents(repo_root)
    output_root = resolve_output_root(policy, repository_root=repo_root)

    if arguments.command == "status":
        decision = authorization_decision(
            policy,
            phase25_policy=phase25,
            activation_policy=activation,
            repository_root=repo_root,
        )
        print(
            json.dumps(
                {
                    "policy_sha256": policy["policy_sha256"],
                    "durable_output_root": EXPECTED_OUTPUT_ROOT.as_posix(),
                    "authorized_if_reserved_now": decision.authorized,
                    "blockers": list(decision.blockers),
                    "fresh_holdout_execution_authorized": False,
                    "product_execution_authorized": False,
                    "public_or_scientific_claim_authorized": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if arguments.command == "reserve":
        receipt = reserve_one_shot_execution(
            policy=policy,
            phase25_policy=phase25,
            activation_policy=activation,
            repository_root=repo_root,
            source_commit_git_sha1=arguments.source_commit,
            operator_id=arguments.operator_id,
            execution_environment_sha256=arguments.execution_environment_sha256,
        )
        print(receipt["receipt_sha256"])
        return 0

    reservation = _load_fixed_receipt(
        output_root,
        "execution-reservation.json",
        name="one-shot reservation",
    )
    if arguments.command == "start":
        receipt = create_run_start_receipt(
            policy=policy,
            reservation=reservation,
            repository_root=repo_root,
        )
        print(receipt["receipt_sha256"])
        return 0

    if arguments.command == "write-result":
        run_start = _load_fixed_receipt(
            output_root,
            "run-start.json",
            name="one-shot run-start",
        )
        baseline = _json(arguments.baseline_arm, name="baseline arm summary")
        experimental = _json(
            arguments.experimental_arm,
            name="experimental arm summary",
        )
        cross_arm = _json(arguments.cross_arm, name="cross-arm evidence summary")
        required_cross_keys = {
            "changed_slot_count",
            "changed_slots_sha256",
            "cross_arm_evidence_sha256",
            "result_dependent_allocation_observed",
            "selected_penetrating_without_validity_change_count",
            "shadow_eligible_candidate_count",
            "source_control_preserved",
        }
        if set(cross_arm) != required_cross_keys:
            raise OneShotABAuthorityError("cross-arm input key set is invalid")

        verify_external_evidence_file(
            arguments.baseline_evidence,
            role="baseline_arm",
            run_start=run_start,
            summary=baseline,
        )
        verify_external_evidence_file(
            arguments.experimental_evidence,
            role="experimental_arm",
            run_start=run_start,
            summary=experimental,
        )
        verify_external_evidence_file(
            arguments.cross_arm_evidence,
            role="cross_arm",
            run_start=run_start,
            summary=cross_arm,
        )

        result = build_result_document(
            run_start=run_start,
            baseline_arm=baseline,
            experimental_arm=experimental,
            source_control_preserved=cross_arm["source_control_preserved"],
            result_dependent_allocation_observed=cross_arm[
                "result_dependent_allocation_observed"
            ],
            shadow_eligible_candidate_count=cross_arm[
                "shadow_eligible_candidate_count"
            ],
            selected_penetrating_without_validity_change_count=cross_arm[
                "selected_penetrating_without_validity_change_count"
            ],
            changed_slot_count=cross_arm["changed_slot_count"],
            changed_slots_sha256=cross_arm["changed_slots_sha256"],
            cross_arm_evidence_sha256=cross_arm["cross_arm_evidence_sha256"],
        )
        write_result_once(
            policy=policy,
            run_start=run_start,
            result=result,
            repository_root=repo_root,
        )
        print(result["result_sha256"])
        return 0

    raise OneShotABAuthorityError("unknown one-shot command")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OneShotABAuthorityError as error:
        print(f"one-shot clearance A/B authority rejected: {error}", file=sys.stderr)
        raise SystemExit(2) from error
