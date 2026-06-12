#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from tools.idp_3bead_common import (
    BRANCH_NAMES,
    STATE_NAMES,
    branch_label_from_profile,
    infer_branch_profile,
    normalize_branch_profile,
)
from tools.idp_branch_labeling import dynamic_labels, quantile_thresholds, row_rg_percentiles
from tools.product.idp_residual_common import FEATURE_NAMES, RANKING_HEAD_NAMES


STATE_TO_INDEX = {name: idx for idx, name in enumerate(STATE_NAMES)}
BRANCH_TO_INDEX = {name: idx for idx, name in enumerate(BRANCH_NAMES)}


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_dataset(args: argparse.Namespace) -> Dict[str, Any]:
    eval_payload = _read_json(str(args.eval_json))
    rows = list(eval_payload.get("targets", []))
    taxonomy = _read_json(str(args.taxonomy_json)) if str(args.taxonomy_json).strip() else {"targets": {}}
    tax_targets = dict(taxonomy.get("targets", {}) or {})
    rg_percentiles = row_rg_percentiles(rows)
    thresholds = quantile_thresholds(rows)

    feature_matrix: List[List[float]] = []
    branch_prior_matrix: List[List[float]] = []
    state_labels: List[int] = []
    branch_labels: List[int] = []
    llps_flags: List[float] = []
    aggregation_flags: List[float] = []
    ranking_targets: List[List[float]] = []
    row_dicts: List[Dict[str, Any]] = []
    target_ids: List[str] = []
    split_groups: List[str] = []

    for idx, row in enumerate(rows):
        target_name = str(row.get("target", ""))
        profile = normalize_branch_profile(row.get("branch_profile") or tax_targets.get(target_name) or infer_branch_profile({"name": target_name}))
        row["branch_profile"] = profile
        row["branch_label"] = branch_label_from_profile(profile)
        for branch_name, value in profile.items():
            row[f"branch_prior_{branch_name}"] = float(value)

        rg_pct = float(rg_percentiles.get(str(idx), 0.5))
        dominant_state, flags, ranking = dynamic_labels(row, rg_pct, thresholds)
        row["dominant_state_label"] = dominant_state
        row["aggregation_flag"] = int(flags["aggregation_flag"])
        row["llps_flag"] = int(flags["llps_flag"])
        row.update(ranking)

        feat = [float(row.get(name, 0.0) or 0.0) for name in FEATURE_NAMES]
        prior_row = [float(profile[name]) for name in BRANCH_NAMES]
        rank_row = [float(ranking[f"{name}_score"]) for name in RANKING_HEAD_NAMES]

        feature_matrix.append(feat)
        branch_prior_matrix.append(prior_row)
        state_labels.append(int(STATE_TO_INDEX[dominant_state]))
        branch_labels.append(int(BRANCH_TO_INDEX[branch_label_from_profile(profile)]))
        llps_flags.append(float(flags["llps_flag"]))
        aggregation_flags.append(float(flags["aggregation_flag"]))
        ranking_targets.append(rank_row)
        target_ids.append(target_name)
        split_groups.append(str(row.get("split_group", target_name)))

        row_dict = {"target": target_name, "split_group": split_groups[-1], "condition_group": str(row.get("condition_group", ""))}
        for name, value in zip(FEATURE_NAMES, feat):
            row_dict[name] = value
        for name, value in zip(BRANCH_NAMES, prior_row):
            row_dict[f"branch_prior_{name}"] = value
        row_dict["dominant_state_label"] = dominant_state
        row_dict["branch_label"] = branch_label_from_profile(profile)
        row_dict["aggregation_flag"] = int(flags["aggregation_flag"])
        row_dict["llps_flag"] = int(flags["llps_flag"])
        for name, value in ranking.items():
            row_dict[name] = value
        row_dicts.append(row_dict)

    pair_left: List[int] = []
    pair_right: List[int] = []
    pair_label: List[List[float]] = []
    group_to_indices: Dict[str, List[int]] = {}
    for idx, group in enumerate(split_groups):
        group_to_indices.setdefault(group, []).append(idx)
    for indices in group_to_indices.values():
        if len(indices) < 2:
            continue
        for i_pos, left in enumerate(indices):
            for right in indices[i_pos + 1:]:
                a = ranking_targets[left]
                b = ranking_targets[right]
                delta = [float(av - bv) for av, bv in zip(a, b)]
                if max(abs(v) for v in delta) < 1e-6:
                    continue
                label = [1.0 if v > 0.0 else 0.0 for v in delta]
                pair_left.append(int(left))
                pair_right.append(int(right))
                pair_label.append(label)
                pair_left.append(int(right))
                pair_right.append(int(left))
                pair_label.append([1.0 - x for x in label])

    out_prefix = str(args.out_prefix).strip() or f"/home/betelgeuze/분자동역학/runs/idp_branch_dataset_{dt.date.today().isoformat()}"
    out_csv = f"{out_prefix}_rows.csv"
    out_npz = f"{out_prefix}.npz"
    out_json = f"{out_prefix}_summary.json"
    out_md = f"{out_prefix}_summary.md"
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row_dicts[0].keys()) if row_dicts else ["target"])
        writer.writeheader()
        for row in row_dicts:
            writer.writerow(row)
    np.savez(
        out_npz,
        feature_matrix=np.asarray(feature_matrix, dtype=np.float32),
        branch_priors=np.asarray(branch_prior_matrix, dtype=np.float32),
        branch_labels=np.asarray(branch_labels, dtype=np.int64),
        state_labels=np.asarray(state_labels, dtype=np.int64),
        llps_flags=np.asarray(llps_flags, dtype=np.float32),
        aggregation_flags=np.asarray(aggregation_flags, dtype=np.float32),
        ranking_targets=np.asarray(ranking_targets, dtype=np.float32),
        pair_left=np.asarray(pair_left, dtype=np.int64),
        pair_right=np.asarray(pair_right, dtype=np.int64),
        pair_label=np.asarray(pair_label, dtype=np.float32),
        feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
        branch_names=np.asarray(BRANCH_NAMES, dtype=np.str_),
        state_names=np.asarray(STATE_NAMES, dtype=np.str_),
        ranking_head_names=np.asarray(RANKING_HEAD_NAMES, dtype=np.str_),
        target_ids=np.asarray(target_ids, dtype=np.str_),
        split_groups=np.asarray(split_groups, dtype=np.str_),
    )
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "eval_json": str(args.eval_json),
        "taxonomy_json": str(args.taxonomy_json),
        "rows_total": int(len(row_dicts)),
        "feature_dim": int(len(FEATURE_NAMES)),
        "branch_count": int(len(BRANCH_NAMES)),
        "state_count": int(len(STATE_NAMES)),
        "ranking_head_count": int(len(RANKING_HEAD_NAMES)),
        "pair_count": int(len(pair_left)),
        "branch_label_counts": {name: int(sum(1 for v in branch_labels if v == idx)) for name, idx in BRANCH_TO_INDEX.items()},
        "state_label_counts": {name: int(sum(1 for v in state_labels if v == idx)) for name, idx in STATE_TO_INDEX.items()},
        "llps_positive_count": int(sum(int(v > 0.5) for v in llps_flags)),
        "aggregation_positive_count": int(sum(int(v > 0.5) for v in aggregation_flags)),
        "out_csv": out_csv,
        "out_npz": out_npz,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Branch Dataset",
                    "",
                    f"- rows_total: {payload['rows_total']}",
                    f"- feature_dim: {payload['feature_dim']}",
                    f"- pair_count: {payload['pair_count']}",
                    f"- out_csv: `{out_csv}`",
                    f"- out_npz: `{out_npz}`",
                ]
            ) + "\n"
        )
    payload["out_json"] = out_json
    payload["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build branch/state/ranking dataset from IDP evaluator outputs.")
    p.add_argument("--eval-json", type=str, required=True)
    p.add_argument("--taxonomy-json", type=str, default="/home/betelgeuze/분자동역학/config/idp_branch_taxonomy_v1.json")
    p.add_argument("--out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_dataset(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
