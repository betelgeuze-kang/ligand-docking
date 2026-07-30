#!/usr/bin/env python3
"""Verify the result-independent Engine V2 public-redocking Stage 0 freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from betelgeuze_engine_v2.benchmark.blind_stage0 import (
    Stage0AdmissionError,
    compute_stage0_policy_sha256,
    compute_stage0_review_subject_sha256,
    current_stage0_host_environment,
    verify_stage0_admission,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--gnina", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        help="exact frozen retention root; required for admission verification",
    )
    parser.add_argument(
        "--print-computed-policy-sha256",
        action="store_true",
        help="print the canonical self-hash for a filled policy without admitting it",
    )
    parser.add_argument(
        "--print-review-subject-sha256",
        action="store_true",
        help="print the hash an independent attestation must review",
    )
    parser.add_argument(
        "--print-host-environment-json",
        action="store_true",
        help="print the SHA-only host snapshot to freeze in the policy",
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.print_host_environment_json:
        print(json.dumps(current_stage0_host_environment(), sort_keys=True))
        return 0
    if (
        arguments.print_computed_policy_sha256
        or arguments.print_review_subject_sha256
    ):
        try:
            payload = json.loads(arguments.policy.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            print(json.dumps({"admitted": False, "blockers": ["stage0_policy_unreadable"]}))
            return 2
        if not isinstance(payload, dict):
            print(json.dumps({"admitted": False, "blockers": ["stage0_policy_not_object"]}))
            return 2
        print(
            compute_stage0_review_subject_sha256(payload)
            if arguments.print_review_subject_sha256
            else compute_stage0_policy_sha256(payload)
        )
        return 0
    try:
        receipt = verify_stage0_admission(
            arguments.policy,
            repo_root=arguments.repo_root.resolve(),
            gnina_path=(arguments.gnina.resolve() if arguments.gnina else None),
            output_root=(
                arguments.output_root.resolve() if arguments.output_root else None
            ),
        )
    except Stage0AdmissionError as exc:
        print(
            json.dumps(
                {"admitted": False, "blockers": list(exc.blockers)},
                sort_keys=True,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "admitted": True,
                "execution_profile_sha256": receipt.execution_profile_sha256,
                "operator_id": receipt.operator_id,
                "policy_sha256": receipt.policy_sha256,
                "reviewer_id": receipt.reviewer_id,
                "source_freeze_sha256": receipt.source_freeze_sha256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
