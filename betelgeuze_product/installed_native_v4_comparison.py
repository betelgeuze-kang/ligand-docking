"""Installed native receptor v4 fit comparison with an opt-in structural bridge.

The v1 protocol remains null-only. V2 accepts prepared requests only when a
source-record origin matches the rederived structural observation. Neither
version claims that the prepared state matches the assayed physical state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import installed_synthetic_comparison as comparison


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "resume", "verify-run"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    protocol = comparison._read_protocol(args.protocol)
    if protocol.get("schema_version") not in {
        comparison.NATIVE_PROTOCOL, comparison.NATIVE_PROTOCOL_V2,
    }:
        raise ValueError("native_v4_comparison_requires_native_protocol")
    if args.action == "verify-run":
        outcome = comparison.verify_run(protocol, args.run_dir)
    else:
        result = comparison.run(protocol, args.run_dir, resume=args.action == "resume")
        outcome = {
            "schema_version": ("installed_native_v4_fit_prepared_comparison_cli_v2"
                               if protocol["schema_version"] == comparison.NATIVE_PROTOCOL_V2
                               else "installed_native_v4_fit_comparison_cli_v1"),
            "status": "committed", "exit_code": 0,
            "binding": result["binding"], "pool_count": len(result["pool"]),
            "arms": {arm: result["arms"][arm]["denominator"]
                     for arm in comparison.ARMS},
            "source_authenticated": False,
            "scientifically_validated": False,
        }
    print(json.dumps(outcome, sort_keys=True, allow_nan=False))
    return outcome["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
