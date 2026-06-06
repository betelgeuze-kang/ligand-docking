#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from typing import Any, Dict, Optional, Sequence


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    cfg = _read_json(str(args.config_json))
    eval_payload = _read_json(str(args.eval_json))
    out_prefix = str(args.out_prefix).strip() or f"/home/betelgeuze/분자동역학/runs/idp_branch_report_{dt.date.today().isoformat()}"
    out_csv = f"{out_prefix}.csv"
    out_json = f"{out_prefix}.json"
    out_md = f"{out_prefix}.md"
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)

    rows = []
    for row in list(eval_payload.get("targets", [])):
        rg = _float(row.get("corrected_rg_mean", row.get("on_rg_mean", 0.0)))
        sasa = _float(row.get("corrected_sasa_proxy_mean", row.get("on_sasa_proxy_mean", 0.0)))
        helicity = _float(row.get("corrected_transient_helicity", row.get("on_transient_helicity", 0.0)))
        contact = _float(row.get("corrected_contact_persistence", row.get("on_contact_persistence", 0.0)))
        diversity = _float(row.get("corrected_ensemble_diversity", row.get("on_ensemble_diversity", 0.0)))
        llps = int(contact >= 0.05 and diversity >= 1.0 and rg >= 18.0)
        folded = int(helicity >= 0.28 and diversity <= 1.5 and sasa <= 900.0)
        rows.append(
            {
                "target": row.get("target", ""),
                "source": row.get("source", ""),
                "split_group": row.get("split_group", ""),
                "condition_group": row.get("condition_group", ""),
                "n_res": int(_float(row.get("n_res", 0))),
                "ionic_strength": _float(row.get("ionic_strength", 0.15)),
                "pH": _float(row.get("pH", 7.2)),
                "ptm_count": _float(row.get("ptm_count", 0.0)),
                "hydro_strength": _float(row.get("hydro_strength", 1.0)),
                "cooling_rate": _float(row.get("cooling_rate", 0.0)),
                "is_llps": llps,
                "is_folded": folded,
                "rg_mean": rg,
                "sasa_proxy_mean": sasa,
                "contact_persistence": contact,
                "transient_helicity": helicity,
                "ensemble_diversity": diversity,
                "overcollapse_rate": _float(row.get("on_overcollapse_rate", 0.0)),
                "virtual_hbond_contacts_mean": _float(row.get("on_virtual_hbond_contacts_mean", 0.0)),
                "virtual_hbond_mean_distance_A": _float(row.get("on_virtual_hbond_mean_distance_A", 0.0)),
                "anti_collapse_force_mean": _float(row.get("on_anti_collapse_force_mean", 0.0)),
                "anchor_source": row.get("corrected_anchor_source", row.get("baseline_anchor_source", "")),
                "anchor_rg_mean_error": _float(row.get("corrected_anchor_rg_mean_error", row.get("baseline_anchor_rg_mean_error", 0.0))),
                "anchor_sasa_proxy_mean_error": _float(row.get("corrected_anchor_sasa_proxy_mean_error", row.get("baseline_anchor_sasa_proxy_mean_error", 0.0))),
                "anchor_contact_persistence_error": _float(row.get("corrected_anchor_contact_persistence_error", row.get("baseline_anchor_contact_persistence_error", 0.0))),
                "anchor_transient_helicity_error": _float(row.get("corrected_anchor_transient_helicity_error", row.get("baseline_anchor_transient_helicity_error", 0.0))),
                "anchor_ensemble_diversity_error": _float(row.get("corrected_anchor_ensemble_diversity_error", row.get("baseline_anchor_ensemble_diversity_error", 0.0))),
                "residual_applied": int(bool(eval_payload.get("residual", {}).get("applied", False))),
                "baseline_target_pass": int(bool(row.get("target_pass", False))),
                "residual_target_pass": int(bool(row.get("residual_target_pass", row.get("target_pass", False)))),
            }
        )

    fieldnames = list(rows[0].keys()) if rows else ["target"]
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    payload = {
        "generated_at_local": dt.datetime.now().isoformat(timespec="seconds"),
        "config_json": str(args.config_json),
        "eval_json": str(args.eval_json),
        "row_count": int(len(rows)),
        "csv": out_csv,
        "residual_applied": bool(eval_payload.get("residual", {}).get("applied", False)),
        "llps_positive_count": int(sum(int(row["is_llps"]) for row in rows)),
        "folded_positive_count": int(sum(int(row["is_folded"]) for row in rows)),
        "split_group_count": int(len({str(row.get("split_group", "")) for row in rows})),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(
            "\n".join(
                [
                    "# IDP Branch Feature Report",
                    "",
                    f"- row_count: {payload['row_count']}",
                    f"- residual_applied: {payload['residual_applied']}",
                    f"- llps_positive_count: {payload['llps_positive_count']}",
                    f"- folded_positive_count: {payload['folded_positive_count']}",
                    f"- split_group_count: {payload['split_group_count']}",
                    f"- csv: `{out_csv}`",
                ]
            )
            + "\n"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build IDP branch-style feature report from evaluator outputs.")
    p.add_argument("--config-json", type=str, required=True)
    p.add_argument("--eval-json", type=str, required=True)
    p.add_argument("--out-prefix", type=str, default="")
    return p


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    payload = build_report(args)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
