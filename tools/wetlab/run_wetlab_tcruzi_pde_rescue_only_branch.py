#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools import build_wetlab_tcruzi_pde_rescue_operator_packet as operator_packet_mod
from tools import build_wetlab_tcruzi_pde_promoted_top4_review_packet as packet_mod
from tools.wetlab_rescue_only_branch_builder import (
    TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
    build_rescue_only_branch_summary_payload,
    build_rescue_only_branch_runner_payload,
    materialize_rescue_only_branch,
)
from tools.wetlab_target_render_utils import load_json, write_artifact

DEFAULT_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_HARD_TARGET_RESCUE_RUNNER_JSON = "runs/wetlab_hard_target_rescue_runner_current.json"
DEFAULT_THREE_BEAD_SLICE_JSON = "runs/wetlab_rescue_three_bead_slice_current.json"
DEFAULT_REVIEW_PACKET_MD = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.md"
DEFAULT_OPERATOR_PACKET_MD = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.md"
DEFAULT_BRANCH_SUMMARY_MD = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_rescue_only_branch_runner_current.md"


def run(
    *,
    review_surface_json: str,
    hard_target_rescue_runner_json: str,
    three_bead_slice_json: str,
    review_packet_md: str,
    operator_packet_md: str,
    branch_summary_md: str,
    out_md: str,
):
    review_surface_payload = load_json(review_surface_json)
    hard_target_rescue_runner_payload = load_json(hard_target_rescue_runner_json)
    three_bead_slice_payload = load_json(three_bead_slice_json)

    review_packet_payload, branch_runner_payload, _ = materialize_rescue_only_branch(
        TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
        review_surface_payload,
        hard_target_rescue_runner_payload,
        three_bead_slice_payload,
        review_packet_builder=packet_mod.build_payload,
    )
    operator_packet_payload = operator_packet_mod.build_payload(review_packet_payload)
    branch_runner_payload = build_rescue_only_branch_runner_payload(
        TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
        review_packet_payload,
        hard_target_rescue_runner_payload,
        three_bead_slice_payload,
    )
    branch_summary_payload = build_rescue_only_branch_summary_payload(
        TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
        operator_packet_payload=operator_packet_payload,
    )

    write_artifact(review_packet_md, TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE.review_packet_title, review_packet_payload)
    write_artifact(operator_packet_md, TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE.operator_packet_title, operator_packet_payload)
    write_artifact(out_md, TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE.branch_runner_title, branch_runner_payload)
    write_artifact(branch_summary_md, TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE.branch_summary_title, branch_summary_payload)
    return branch_runner_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the dedicated T. cruzi PDE rescue-only branch runner and summary from the current rescue evidence.")
    parser.add_argument("--review-surface-json", default=DEFAULT_REVIEW_SURFACE_JSON)
    parser.add_argument("--hard-target-rescue-runner-json", default=DEFAULT_HARD_TARGET_RESCUE_RUNNER_JSON)
    parser.add_argument("--three-bead-slice-json", default=DEFAULT_THREE_BEAD_SLICE_JSON)
    parser.add_argument("--review-packet-md", default=DEFAULT_REVIEW_PACKET_MD)
    parser.add_argument("--operator-packet-md", default=DEFAULT_OPERATOR_PACKET_MD)
    parser.add_argument("--branch-summary-md", default=DEFAULT_BRANCH_SUMMARY_MD)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run(
        review_surface_json=args.review_surface_json,
        hard_target_rescue_runner_json=args.hard_target_rescue_runner_json,
        three_bead_slice_json=args.three_bead_slice_json,
        review_packet_md=args.review_packet_md,
        operator_packet_md=args.operator_packet_md,
        branch_summary_md=args.branch_summary_md,
        out_md=args.out_md,
    )


if __name__ == "__main__":
    main()
