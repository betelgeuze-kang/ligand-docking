"""Installed native receptor v4 fit comparison with an opt-in structural bridge.

The v1 protocol remains null-only. V2 accepts prepared requests only when a
source-record origin matches the rederived structural observation. Neither
version claims that the prepared state matches the assayed physical state.
V3 adds source-bound registered-pose D3 with a distinct dimensionless score.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import installed_synthetic_comparison as comparison


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=(
        "run", "resume", "verify-run", "preflight-v2", "preflight-v3", "preflight-v4"))
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output-protocol", type=Path)
    args = parser.parse_args(argv)
    protocol = comparison._read_protocol(args.protocol)
    if protocol.get("schema_version") not in {
        comparison.NATIVE_PROTOCOL, comparison.NATIVE_PROTOCOL_V2, comparison.NATIVE_PROTOCOL_V3,
        comparison.NATIVE_PROTOCOL_V4,
    }:
        raise ValueError("native_v4_comparison_requires_native_protocol")
    if args.action in {"preflight-v2", "preflight-v3", "preflight-v4"}:
        if args.run_dir is not None:
            parser.error(args.action + " does not use --run-dir")
        from .installed_native_v4_protocol_preflight import preflight_v2, preflight_v3, preflight_v4

        outcome = (preflight_v4(protocol) if args.action == "preflight-v4" else
                   preflight_v3(protocol) if args.action == "preflight-v3"
                   else preflight_v2(protocol))
        if outcome["status"] == "ready" and args.output_protocol is not None:
            comparison._publish(args.output_protocol, outcome["protocol"])
            outcome["output_protocol"] = str(args.output_protocol)
        print(json.dumps(
            {key: value for key, value in outcome.items() if key != "protocol"},
            sort_keys=True, allow_nan=False,
        ))
        return 0 if outcome["status"] == "ready" else 2
    if args.run_dir is None or args.output_protocol is not None:
        parser.error("run, resume, and verify-run require --run-dir and no --output-protocol")
    if args.action == "verify-run":
        outcome = comparison.verify_run(protocol, args.run_dir)
    else:
        result = comparison.run(protocol, args.run_dir, resume=args.action == "resume")
        outcome = {
            "schema_version": ("installed_native_v4_registered_cartesian_comparison_cli_v4"
                               if protocol["schema_version"] == comparison.NATIVE_PROTOCOL_V4 else
                               "installed_native_v4_registered_comparison_cli_v3"
                               if protocol["schema_version"] == comparison.NATIVE_PROTOCOL_V3 else
                               "installed_native_v4_fit_prepared_comparison_cli_v2"
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
