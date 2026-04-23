#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from tools.idp_residual_common import ANCHOR_METRIC_NAMES, FEATURE_NAMES, TARGET_NAMES


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_dataset(args: argparse.Namespace) -> Dict[str, Any]:
    eval_payload = _read_json(str(args.eval_json))
    rows = list(eval_payload.get("targets", []))
    feature_matrix: List[List[float]] = []
    target_matrix: List[List[float]] = []
    anchor_lo_matrix: List[List[float]] = []
    anchor_hi_matrix: List[List[float]] = []
    anchor_mask_matrix: List[List[float]] = []
    row_dicts: List[Dict[str, Any]] = []
    for row in rows:
        feat = [float(row.get(name, 0.0) or 0.0) for name in FEATURE_NAMES]
        targ = [float(row.get(name, 0.0) or 0.0) for name in TARGET_NAMES]
        anchor_lo_row: List[float] = []
        anchor_hi_row: List[float] = []
        anchor_mask_row: List[float] = []
        for metric_name in ANCHOR_METRIC_NAMES:
            lo = row.get(f"baseline_anchor_{metric_name}_lo")
            hi = row.get(f"baseline_anchor_{metric_name}_hi")
            if lo is None or hi is None:
                anchor_lo_row.append(0.0)
                anchor_hi_row.append(0.0)
                anchor_mask_row.append(0.0)
            else:
                anchor_lo_row.append(float(lo))
                anchor_hi_row.append(float(hi))
                anchor_mask_row.append(1.0)
        feature_matrix.append(feat)
        target_matrix.append(targ)
        anchor_lo_matrix.append(anchor_lo_row)
        anchor_hi_matrix.append(anchor_hi_row)
        anchor_mask_matrix.append(anchor_mask_row)
        row_dict = {"target": row.get("target", "")}
        for name, value in zip(FEATURE_NAMES, feat):
            row_dict[name] = value
        for name, value in zip(TARGET_NAMES, targ):
            row_dict[name] = value
        for name, value in zip(ANCHOR_METRIC_NAMES, anchor_lo_row):
            row_dict[f"anchor_{name}_lo"] = value
        for name, value in zip(ANCHOR_METRIC_NAMES, anchor_hi_row):
            row_dict[f"anchor_{name}_hi"] = value
        for name, value in zip(ANCHOR_METRIC_NAMES, anchor_mask_row):
            row_dict[f"anchor_{name}_mask"] = value
        row_dicts.append(row_dict)

    out_prefix = str(args.out_prefix).strip() or f"/home/betelgeuze/분자동역학/runs/idp_residual_dataset_{dt.date.today().isoformat()}"
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
        targets=np.asarray(target_matrix, dtype=np.float32),
        anchor_lo_matrix=np.asarray(anchor_lo_matrix, dtype=np.float32),
        anchor_hi_matrix=np.asarray(anchor_hi_matrix, dtype=np.float32),
        anchor_mask_matrix=np.asarray(anchor_mask_matrix, dtype=np.float32),
        feature_names=np.asarray(FEATURE_NAMES, dtype=np.str_),
        target_names=np.asarray(TARGET_NAMES, dtype=np.str_),
        anchor_metric_names=np.asarray(ANCHOR_METRIC_NAMES, dtype=np.str_),
        target_ids=np.asarray([str(row.get("target", "")) for row in rows], dtype=np.str_),
    )
    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "eval_json": str(args.eval_json),
        "rows_total": int(len(row_dicts)),
        "feature_dim": int(len(FEATURE_NAMES)),
        "target_dim": int(len(TARGET_NAMES)),
        "anchor_metric_dim": int(len(ANCHOR_METRIC_NAMES)),
        "out_csv": out_csv,
        "out_npz": out_npz,
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Residual Dataset",
                    "",
                    f"- rows_total: {payload['rows_total']}",
                    f"- feature_dim: {payload['feature_dim']}",
                    f"- target_dim: {payload['target_dim']}",
                    f"- anchor_metric_dim: {payload['anchor_metric_dim']}",
                    f"- out_csv: `{out_csv}`",
                    f"- out_npz: `{out_npz}`",
                ]
            )
            + "\n"
        )
    payload["out_json"] = out_json
    payload["out_md"] = out_md
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build observable-residual dataset from IDP 3-bead evaluator outputs.")
    p.add_argument("--eval-json", type=str, required=True)
    p.add_argument("--out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_dataset(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
