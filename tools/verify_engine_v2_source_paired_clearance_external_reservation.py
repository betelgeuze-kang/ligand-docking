#!/usr/bin/env python3
"""Verify the external one-shot reservation policy and report blockers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from betelgeuze_engine_v2.benchmark.source_paired_clearance_external_reservation import (  # noqa: E402
    ExternalReservationContractError,
    external_reservation_operational_blockers,
    verify_external_reservation_policy,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=(
            _REPO_ROOT
            / "config/engine_v2_source_paired_clearance_external_reservation.json"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        payload = json.loads(arguments.policy.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalReservationContractError(
            f"external reservation policy is unreadable: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ExternalReservationContractError(
            "external reservation policy must be an object"
        )
    policy_sha256 = verify_external_reservation_policy(payload)
    blockers = external_reservation_operational_blockers(payload)
    print(
        json.dumps(
            {
                "policy_sha256": policy_sha256,
                "external_reservation_operational": not blockers,
                "blockers": list(blockers),
                "historical_execution_operational": False,
                "fresh_holdout_execution_authorized": False,
                "product_execution_authorized": False,
                "public_or_scientific_claim_authorized": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExternalReservationContractError as error:
        print(f"external reservation policy rejected: {error}", file=sys.stderr)
        raise SystemExit(2) from error
