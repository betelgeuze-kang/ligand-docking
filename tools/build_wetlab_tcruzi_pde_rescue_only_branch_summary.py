#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any

from tools.wetlab_rescue_only_branch_builder import (
    TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
    build_rescue_only_branch_summary_payload,
)
from tools.wetlab_target_render_utils import maybe_load_json, write_artifact

DEFAULT_REVIEW_SURFACE_JSON = "runs/wetlab_tcruzi_pde_rescue_review_surface_current.json"
DEFAULT_REVIEW_PACKET_JSON = "runs/wetlab_tcruzi_pde_promoted_top4_review_packet_current.json"
DEFAULT_OPERATOR_PACKET_JSON = "runs/wetlab_tcruzi_pde_rescue_operator_packet_current.json"
DEFAULT_BRANCH_RUNNER_JSON = "runs/wetlab_tcruzi_pde_rescue_only_branch_runner_current.json"
DEFAULT_THREE_BEAD_SLICE_JSON = "runs/wetlab_rescue_three_bead_slice_current.json"
DEFAULT_OUT_MD = "runs/wetlab_tcruzi_pde_rescue_only_branch_summary_current.md"


def build_payload(
    review_surface_payload: dict[str, Any],
    review_packet_payload: dict[str, Any],
    branch_runner_payload: dict[str, Any],
    three_bead_slice_payload: dict[str, Any] | None = None,
    operator_packet_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_rescue_only_branch_summary_payload(
        TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE,
        review_surface_payload,
        review_packet_payload,
        branch_runner_payload,
        three_bead_slice_payload,
        operator_packet_payload=operator_packet_payload,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the T. cruzi PDE rescue-only branch summary.")
    parser.add_argument("--review-surface-json", default=DEFAULT_REVIEW_SURFACE_JSON)
    parser.add_argument("--review-packet-json", default=DEFAULT_REVIEW_PACKET_JSON)
    parser.add_argument("--operator-packet-json", default=DEFAULT_OPERATOR_PACKET_JSON)
    parser.add_argument("--branch-runner-json", default=DEFAULT_BRANCH_RUNNER_JSON)
    parser.add_argument("--three-bead-slice-json", default=DEFAULT_THREE_BEAD_SLICE_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_payload(
        maybe_load_json(args.review_surface_json),
        maybe_load_json(args.review_packet_json),
        maybe_load_json(args.branch_runner_json),
        maybe_load_json(args.three_bead_slice_json),
        operator_packet_payload=maybe_load_json(args.operator_packet_json),
    )
    write_artifact(args.out_md, TCRUZI_PDE_RESCUE_ONLY_BRANCH_TEMPLATE.branch_summary_title, payload)


if __name__ == "__main__":
    main()
