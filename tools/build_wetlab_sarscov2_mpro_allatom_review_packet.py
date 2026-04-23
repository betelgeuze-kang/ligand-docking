#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_allatom_refinement_utils import build_target_allatom_review_packet
from tools.wetlab_target_render_utils import load_json, write_artifact

TARGET_ID = "SARS-CoV-2 Mpro"
DEFAULT_LANE_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.json"
DEFAULT_RUNNER_JSON = "runs/wetlab_sarscov2_mpro_allatom_refinement_runner_current.json"
DEFAULT_OUT_MD = "runs/wetlab_sarscov2_mpro_allatom_review_packet_current.md"


def build_payload(
    lane_payload: dict[str, Any],
    runner_payload: dict[str, Any],
    *,
    claim_readiness_json: str = "",
    equivalence_gate_json: str = "",
) -> dict[str, Any]:
    payload = build_target_allatom_review_packet(
        target_id=TARGET_ID,
        lane_payload=lane_payload,
        runner_payload=runner_payload,
        lane_label="sarscov2_mpro_allatom_top32_refinement",
        branch_mode="promote_tuned_branch_with_allatom_review",
        default_lane_reopen_allowed=False,
        claim_readiness_json=claim_readiness_json,
        equivalence_gate_json=equivalence_gate_json,
    )
    payload.setdefault("structured", {})
    payload["structured"]["allatom_refinement_lane_artifact"] = "runs/wetlab_sarscov2_mpro_allatom_refinement_lane_current.md"
    payload["structured"]["allatom_runner_artifact"] = "runs/wetlab_sarscov2_mpro_allatom_refinement_runner_current.md"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the SARS-CoV-2 Mpro pseudo all-atom review packet.")
    parser.add_argument("--lane-json", default=DEFAULT_LANE_JSON)
    parser.add_argument("--runner-json", default=DEFAULT_RUNNER_JSON)
    parser.add_argument("--claim-readiness-json", default="")
    parser.add_argument("--equivalence-gate-json", default="")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        load_json(args.lane_json),
        load_json(args.runner_json),
        claim_readiness_json=str(args.claim_readiness_json),
        equivalence_gate_json=str(args.equivalence_gate_json),
    )
    write_artifact(args.out_md, "Wet-Lab SARS-CoV-2 Mpro All-Atom Review Packet", payload)


if __name__ == "__main__":
    main()
