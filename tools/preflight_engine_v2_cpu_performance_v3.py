#!/usr/bin/env python3
"""Run the read-only, non-consuming CPU performance v3 host preflight."""

from __future__ import annotations

import argparse
import hashlib
import json

from betelgeuze_engine_v2.docking.performance_host_preflight_v3 import (
    derive_host_preflight_evidence_v3,
)
from tools.verify_engine_v2_cpu_performance_profile_v3 import (
    verify_cpu_performance_profile_v3,
)


def _receipt_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def run_non_consuming_preflight() -> dict[str, object]:
    """Inspect the exact host path without launching or reserving work."""

    profile = dict(verify_cpu_performance_profile_v3())
    host = derive_host_preflight_evidence_v3().to_dict()
    projection: dict[str, object] = {
        "authority": dict(profile["authority"]),
        "consumes_qualification": False,
        "execution_authorized": False,
        "host": host,
        "launches_measurements": False,
        "molecular_execution": False,
        "persists_result": False,
        "profile_id": profile["profile_id"],
        "profile_sha256": profile["profile_sha256"],
        "qualified": host["qualified"],
        "reservation_created": False,
        "schema_id": (
            "betelgeuze.engine_v2_cpu_performance_non_consuming_preflight/3.0.0"
        ),
    }
    return {**projection, "preflight_receipt_sha256": _receipt_sha256(projection)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-qualified",
        action="store_true",
        help="return non-zero when the read-only host preflight is not qualified",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    result = run_non_consuming_preflight()
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 1 if arguments.require_qualified and result["qualified"] is not True else 0


if __name__ == "__main__":
    raise SystemExit(main())
