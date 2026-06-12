#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from tools.wetlab_allatom_refinement_utils import run_target_allatom_refinement_slice

TARGET_ID = "Cathepsin K"
DEFAULT_LANE_JSON = "runs/wetlab_cathepsin_k_allatom_refinement_lane_current.json"
DEFAULT_OUT_MD = "runs/wetlab_cathepsin_k_allatom_refinement_runner_current.md"
DEFAULT_TOP_K = 8


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Cathepsin K pseudo all-atom refinement slice.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--claim-readiness-json", default="")
    parser.add_argument("--equivalence-gate-json", default="")
    parser.add_argument("--python-bin", default=sys.executable or "python3")
    parser.add_argument("--execute", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_target_allatom_refinement_slice(
        lane_json=args.lane_json,
        target_id=TARGET_ID,
        out_md=args.out_md,
        top_k=max(1, int(args.top_k)),
        claim_readiness_json=str(args.claim_readiness_json),
        equivalence_gate_json=str(args.equivalence_gate_json),
        python_bin=str(args.python_bin),
        execute=bool(args.execute),
        slice_group="wetlab_allatom_refinement",
    )


if __name__ == "__main__":
    main()
