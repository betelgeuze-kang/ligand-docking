#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, Optional, Sequence


ROOT = "/home/betelgeuze/분자동역학"


def build(args: argparse.Namespace) -> Dict[str, Any]:
    with open(str(args.base_config_json), "r", encoding="utf-8") as f:
        base = json.load(f)
    with open(str(args.anchor_json), "r", encoding="utf-8") as f:
        anchors = dict(json.load(f).get("targets", {}))
    taxonomy_targets = {}
    taxonomy_json = str(args.taxonomy_json).strip()
    if taxonomy_json:
        with open(taxonomy_json, "r", encoding="utf-8") as f:
            taxonomy_targets = dict(json.load(f).get("targets", {}))

    runtime = dict(base.get("runtime", {}))
    if taxonomy_json:
        runtime["idp_branch_taxonomy_json"] = os.path.abspath(taxonomy_json)
    if str(args.force_policy_json).strip():
        runtime["idp_branch_force_policy_json"] = os.path.abspath(str(args.force_policy_json))
    gate = dict(base.get("gate", {}))
    gate.update(
        {
            "min_target_pass_fraction": 0.75,
            "max_failed_targets": 7,
            "min_branch_macro_f1": 0.75,
            "min_dominant_state_accuracy": 0.70,
            "min_llps_flag_pr_auc": 0.75,
            "min_aggregation_flag_pr_auc": 0.75,
            "min_compactness_rank_auc": 0.80,
            "min_helicity_rank_auc": 0.78,
            "min_condensation_rank_auc": 0.80,
        }
    )

    targets = []
    for target in list(base.get("targets", [])):
        name = str(target["name"])
        split_group = str(target.get("split_group", name))
        condition_group = str(target.get("condition_group", target.get("suffix", "base")))
        anchor_key = split_group if split_group in anchors else name
        if anchor_key not in anchors:
            raise KeyError(f"missing observable anchor for target: {anchor_key}")
        row = dict(target)
        row["split_group"] = split_group
        row["condition_group"] = condition_group
        row["observable_anchor"] = dict(anchors[anchor_key])
        taxonomy_key = split_group if split_group in taxonomy_targets else name
        if taxonomy_key in taxonomy_targets:
            row["branch_profile"] = dict(taxonomy_targets[taxonomy_key])
        targets.append(row)

    payload = {
        "version": str(args.version).strip() or "idp_3bead_benchmark_v3",
        "description": "Strict hold-out IDP/LLPS benchmark with split groups and observable anchor bands.",
        "runtime": runtime,
        "gate": gate,
        "targets": targets,
    }
    out_json = os.path.abspath(str(args.out_json).strip() or os.path.join(ROOT, "config", "idp_3bead_benchmark_v3.json"))
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return {"out_json": out_json, "target_count": len(targets)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build strict hold-out IDP benchmark config with anchor priors.")
    p.add_argument("--base-config-json", type=str, required=True)
    p.add_argument("--anchor-json", type=str, required=True)
    p.add_argument("--version", type=str, default="idp_3bead_benchmark_v3")
    p.add_argument("--out-json", type=str, default=os.path.join(ROOT, "config", "idp_3bead_benchmark_v3.json"))
    p.add_argument("--taxonomy-json", type=str, default=os.path.join(ROOT, "config", "idp_branch_taxonomy_v1.json"))
    p.add_argument("--force-policy-json", type=str, default=os.path.join(ROOT, "config", "idp_branch_force_policy_v1.json"))
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    print(json.dumps(build(args), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
