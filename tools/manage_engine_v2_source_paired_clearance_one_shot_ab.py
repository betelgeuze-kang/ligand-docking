#!/usr/bin/env python3
"""Manage the frozen one-shot historical clearance A/B authority.

This command never runs docking. An external operator/runtime must generate one
complete comparison-evidence artifact after a successful ``reserve`` and
``start`` sequence. Compact summaries are independently derived from that full
artifact; caller-supplied hash-only summaries are not accepted.
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
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_full_evidence import (  # noqa: E402
    build_result_document_from_full_evidence_file,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_external_gate import (  # noqa: E402
    combine_one_shot_and_external_decisions,
    require_external_historical_execution_authority,
)
from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_result import (  # noqa: E402
    write_result_once,
)


def _json(path: Path, *, name: str) -> dict[str, Any]:
    return load_json_document(path.resolve(), name=name)


def _source_documents(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
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
        _json(
            repo_root
            / "config/engine_v2_source_paired_clearance_external_reservation.json",
            name="external reservation policy",
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
        help=(
            "Independently audit one complete candidate-level evidence artifact "
            "and atomically write the derived compact result."
        ),
    )
    write_result.add_argument(
        "--full-evidence",
        type=Path,
        required=True,
        help=(
            "One self-hashed comparison artifact containing all eight full case "
            "receipts and 1,024 run-bound candidate wrappers."
        ),
    )
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
    policy, phase25, activation, external_reservation = _source_documents(repo_root)
    output_root = resolve_output_root(policy, repository_root=repo_root)

    if arguments.command == "status":
        decision = combine_one_shot_and_external_decisions(
            authorization_decision(
                policy,
                phase25_policy=phase25,
                activation_policy=activation,
                repository_root=repo_root,
            ),
            external_policy=external_reservation,
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
        require_external_historical_execution_authority(external_reservation)
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

    require_external_historical_execution_authority(external_reservation)
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
        result = build_result_document_from_full_evidence_file(
            arguments.full_evidence.resolve(strict=True),
            run_start=run_start,
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
