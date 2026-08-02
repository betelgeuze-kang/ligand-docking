#!/usr/bin/env python3
"""Verify the permanent reservation, 384 rows, 8,192 slots, and completion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from betelgeuze_engine_v2.benchmark.fresh_run_verifier import (
    FreshRunVerificationError,
    verify_fresh_run_root,
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--repo-root",
        required=True,
        type=Path,
        help="exact repository containing the frozen manifest and Stage 0 source",
    )
    parser.add_argument(
        "--stage0-policy",
        required=True,
        type=Path,
        help="frozen Stage 0 policy to reverify as the external trust root",
    )
    parser.add_argument(
        "--gnina",
        required=True,
        type=Path,
        help="exact GNINA binary bound by the frozen Stage 0 policy",
    )
    arguments = parser.parse_args()
    try:
        receipt = verify_fresh_run_root(
            arguments.output_root,
            repo_root=arguments.repo_root,
            stage0_policy_path=arguments.stage0_policy,
            gnina_path=arguments.gnina,
        )
    except FreshRunVerificationError as exc:
        payload = {
            "verified": False,
            "error_code": "fresh_redocking_run_verification_failed",
            "message": str(exc),
            "claim_safe": False,
        }
        print(_canonical_bytes(payload).decode("ascii"))
        return 2
    payload = {
        "verified": True,
        **receipt.to_dict(),
    }
    print(_canonical_bytes(payload).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
