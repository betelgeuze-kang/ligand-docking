#!/usr/bin/env python3
from __future__ import annotations

import argparse

from tools.wetlab_target_render_utils import write_artifact

DEFAULT_OUT_MD = "runs/caix_slow_shard_preset_current.md"


def build_payload() -> dict:
    profile_id = "caix_slow_shard_v1"
    rows = [
        {"flag": "--traj-prod-profile-intent", "value": profile_id, "purpose": "label the slow-shard profile in downstream summaries"},
        {"flag": "--traj-prod-stage2-preset", "value": "default", "purpose": "keep condition-aware enzyme on the generic preset family baseline"},
        {"flag": "--traj-prod-speedpack", "value": "", "purpose": "retain production speedpack path"},
        {"flag": "--traj-prod-light-artifacts", "value": "", "purpose": "avoid non-essential stage2 artifacts"},
        {"flag": "--traj-prod-early-stop-enabled", "value": "", "purpose": "allow earlier cutoff on obviously weak trajectories"},
        {"flag": "--traj-prod-min-frames-full", "value": "128", "purpose": "lower full-run frame floor for CA IX slow shards"},
        {"flag": "--traj-prod-early-stop-min-frames-full", "value": "112", "purpose": "allow early-stop check before the default 160-frame floor"},
        {"flag": "--traj-prod-early-stop-window", "value": "10", "purpose": "narrow slow-shard stabilization window"},
        {"flag": "--traj-prod-early-stop-max-mean-min-distance-A", "value": "5.0", "purpose": "surface likely stage6 failures earlier in stage2"},
        {"flag": "--traj-job-batch-autotune-candidates", "value": "4,8,16", "purpose": "bias toward larger job batches on broad CA IX shards"},
        {"flag": "--traj-writer-workers", "value": "2", "purpose": "reduce writer bottlenecks for shard-scale outputs"},
        {"flag": "--traj-dynamic-adress-max-protein-residues", "value": "170", "purpose": "tighten dynamic adress region for condition-aware enzyme runs"},
        {"flag": "--traj-dynamic-adress-fraction", "value": "0.12", "purpose": "slightly reduce active adress fraction for CA IX broad shards"},
    ]
    return {
        "summary": {
            "status": "caix_slow_shard_preset_ready",
            "target_id": "CA IX",
            "profile_id": profile_id,
            "flag_count": len(rows),
            "intended_use": "Use on CA IX shards that look slow or have recent stage6 gate trouble before trying stricter gate retuning.",
            "next_required_step": "Wire this profile into the throughput bridge so the tuned preflight/execute commands are emitted next to the default commands.",
        },
        "structured": {
            "runtime_profile_artifact": "runs/caix_broad_screen_runtime_profile_current.md",
            "throughput_bridge_artifact": "runs/wetlab_broad_screen_throughput_bridge_current.md",
        },
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the CA IX slow-shard preset overlay for throughput runs.")
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    write_artifact(args.out_md, "CA IX Slow-Shard Preset", build_payload())


if __name__ == "__main__":
    main()
