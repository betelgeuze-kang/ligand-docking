#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import json
import os
from typing import Any, Dict, List, Optional, Sequence


CONDITIONS = [
    {"suffix": "base", "ionic_strength": 0.15, "pH": 7.2, "ptm_count": 0.0, "hydro_strength": 1.0, "cooling_rate": 0.0},
    {"suffix": "low_salt", "ionic_strength": 0.05, "pH": 7.2, "ptm_count": 0.0, "hydro_strength": 1.0, "cooling_rate": 0.0},
    {"suffix": "high_salt", "ionic_strength": 0.35, "pH": 7.0, "ptm_count": 0.0, "hydro_strength": 0.95, "cooling_rate": 0.0},
    {"suffix": "acidic", "ionic_strength": 0.15, "pH": 6.2, "ptm_count": 0.0, "hydro_strength": 1.0, "cooling_rate": -0.15},
    {"suffix": "ptm_rich", "ionic_strength": 0.18, "pH": 7.2, "ptm_count": 3.0, "hydro_strength": 1.05, "cooling_rate": 0.0},
    {"suffix": "hydro_boost", "ionic_strength": 0.15, "pH": 7.4, "ptm_count": 1.0, "hydro_strength": 1.2, "cooling_rate": 0.1},
]


def build(args: argparse.Namespace) -> Dict[str, Any]:
    with open(str(args.base_config_json), "r", encoding="utf-8") as f:
        base = json.load(f)
    anchors = {}
    anchor_path = str(args.anchor_json or "").strip()
    if anchor_path:
        with open(anchor_path, "r", encoding="utf-8") as f:
            anchors = dict(json.load(f).get("targets", {}))
    out = copy.deepcopy(base)
    targets: List[Dict[str, Any]] = []
    for t_idx, target in enumerate(list(base.get("targets", []))):
        base_seed = int(target.get("seed", 23))
        base_name = str(target.get("name", f"target_{t_idx+1}"))
        anchor = anchors.get(base_name, {})
        for c_idx, cond in enumerate(CONDITIONS):
            row = dict(target)
            row["name"] = f"{target['name']}_{cond['suffix']}"
            row["seed"] = int(base_seed + (t_idx * 100) + c_idx)
            row.update(cond)
            row["split_group"] = base_name
            row["condition_group"] = str(cond["suffix"])
            if anchor:
                row["observable_anchor"] = copy.deepcopy(anchor)
            targets.append(row)
    out["version"] = str(args.version).strip() or "idp_3bead_benchmark_v2"
    out["description"] = "Expanded real IDP/LLPS benchmark matrix with environment sweeps and residual comparison."
    out["targets"] = targets
    out_json = os.path.abspath(str(args.out_json).strip() or "/home/betelgeuze/분자동역학/config/idp_3bead_benchmark_v2.json")
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return {"out_json": out_json, "target_count": len(targets)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build expanded IDP 3-bead benchmark matrix config.")
    p.add_argument("--base-config-json", type=str, required=True)
    p.add_argument("--anchor-json", type=str, default="")
    p.add_argument("--version", type=str, default="idp_3bead_benchmark_v2")
    p.add_argument("--out-json", type=str, default="/home/betelgeuze/분자동역학/config/idp_3bead_benchmark_v2.json")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
