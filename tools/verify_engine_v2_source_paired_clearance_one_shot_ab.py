#!/usr/bin/env python3
"""Verify the exact historical one-shot clearance A/B authority."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.benchmark.source_paired_clearance_one_shot_ab import (  # noqa: E402
    authorization_decision,
    load_json_document,
    resolve_output_root,
    verify_one_shot_policy,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_REPO_ROOT,
        help="Exact checkout root that owns the frozen durable evidence path.",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=_REPO_ROOT
        / "config/engine_v2_source_paired_clearance_one_shot_ab.json",
    )
    parser.add_argument(
        "--phase25-policy",
        type=Path,
        default=_REPO_ROOT / "config/engine_v2_phase25_cohort_admission.json",
    )
    parser.add_argument(
        "--activation-policy",
        type=Path,
        default=_REPO_ROOT
        / "config/engine_v2_source_paired_clearance_activation.json",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo_root = args.repo_root.resolve(strict=True)
    policy = load_json_document(args.policy.resolve(), name="one-shot policy")
    phase25 = load_json_document(
        args.phase25_policy.resolve(), name="Phase 2.5 cohort policy"
    )
    activation = load_json_document(
        args.activation_policy.resolve(), name="clearance activation policy"
    )
    verify_one_shot_policy(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
    )
    output_root = resolve_output_root(policy, repository_root=repo_root)
    decision = authorization_decision(
        policy,
        phase25_policy=phase25,
        activation_policy=activation,
        repository_root=repo_root,
    )
    print(
        {
            "policy_sha256": policy["policy_sha256"],
            "durable_output_root": output_root.relative_to(repo_root).as_posix(),
            "authorized_if_reserved_now": decision.authorized,
            "blockers": list(decision.blockers),
            "fresh_holdout_execution_authorized": False,
            "product_execution_authorized": False,
            "public_or_scientific_claim_authorized": False,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
