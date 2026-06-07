"""Evaluate 4-bead ONSPS cascade blind gate metrics on scored stage3 rows."""

from __future__ import annotations

import ast
from typing import Any

import numpy as np
import pandas as pd


def _as_float_list(value: Any) -> list[float]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, (list, tuple)):
        return [float(x) for x in value if x is not None and str(x).strip() != ""]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple)):
            return [float(x) for x in parsed]
    except (SyntaxError, ValueError, TypeError):
        pass
    return []


def evaluate_four_bead_gate(
    scores_df: pd.DataFrame,
    *,
    enabled: bool = True,
    delta_backmap_max: float = 2.5,
    topo_correction_delta_max: float = 1.0,
    no_pass_to_fail_vs_2bead: bool = True,
    onsps_hbond_angle_score_min: float = 0.0,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "enabled": bool(enabled),
        "pass": True,
        "failed_metrics": [],
        "warnings": [],
        "four_bead_row_count": 0,
        "delta_backmap_max_observed": None,
        "topo_correction_delta_max_observed": None,
        "onsps_angle_min_observed": None,
        "pass_to_fail_regression_count": 0,
    }
    if not enabled:
        summary["pass"] = True
        summary["skipped"] = True
        return summary
    if scores_df is None or scores_df.empty:
        summary["pass"] = False
        summary["failed_metrics"].append(
            {"metric": "four_bead_scores_present", "value": 0, "threshold": ">0"}
        )
        return summary

    mask = pd.Series(False, index=scores_df.index)
    if "ligand_model_pass2" in scores_df.columns:
        mask = mask | scores_df["ligand_model_pass2"].astype(str).eq("4bead_onsps_hbond")
    if "ligand_model" in scores_df.columns:
        mask = mask | scores_df["ligand_model"].astype(str).eq("4bead_onsps_hbond")
    bead_df = scores_df.loc[mask].copy()
    summary["four_bead_row_count"] = int(len(bead_df))
    if bead_df.empty:
        summary["warnings"].append("four_bead_cascade_enabled but no 4bead rows observed in scores")
        return summary

    delta_vals: list[float] = []
    topo_vals: list[float] = []
    angle_mins: list[float] = []
    regression_count = 0
    for _, row in bead_df.iterrows():
        score_2bead = row.get("score_2bead", row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
        score_4bead = row.get("score_4bead", row.get("binding_energy_mmpbsa_kcal_mol_proxy"))
        try:
            s2 = float(score_2bead)
            s4 = float(score_4bead)
        except (TypeError, ValueError):
            s2 = float("nan")
            s4 = float("nan")
        if np.isfinite(s2) and np.isfinite(s4):
            delta = float(s4 - s2)
            delta_vals.append(abs(delta))
            if bool(no_pass_to_fail_vs_2bead) and s4 > s2 + float(delta_backmap_max):
                regression_count += 1
        topo = row.get("topo_correction_delta", row.get("delta_backmap"))
        try:
            topo_f = abs(float(topo))
            topo_vals.append(topo_f)
        except (TypeError, ValueError):
            pass
        angles = _as_float_list(row.get("onsps_angle_scores"))
        if angles:
            angle_mins.append(float(min(angles)))

    if delta_vals:
        max_delta = float(max(delta_vals))
        summary["delta_backmap_max_observed"] = max_delta
        if max_delta > float(delta_backmap_max):
            summary["failed_metrics"].append(
                {
                    "metric": "four_bead_delta_backmap_max",
                    "value": max_delta,
                    "threshold": float(delta_backmap_max),
                }
            )
    if topo_vals:
        max_topo = float(max(topo_vals))
        summary["topo_correction_delta_max_observed"] = max_topo
        if max_topo > float(topo_correction_delta_max):
            summary["failed_metrics"].append(
                {
                    "metric": "four_bead_topo_correction_delta_max",
                    "value": max_topo,
                    "threshold": float(topo_correction_delta_max),
                }
            )
    if angle_mins:
        min_angle = float(min(angle_mins))
        summary["onsps_angle_min_observed"] = min_angle
        if min_angle < float(onsps_hbond_angle_score_min):
            summary["failed_metrics"].append(
                {
                    "metric": "onsps_hbond_angle_score_min",
                    "value": min_angle,
                    "threshold": float(onsps_hbond_angle_score_min),
                }
            )
    summary["pass_to_fail_regression_count"] = int(regression_count)
    if bool(no_pass_to_fail_vs_2bead) and regression_count > 0:
        summary["failed_metrics"].append(
            {
                "metric": "four_bead_no_pass_to_fail_vs_2bead",
                "value": int(regression_count),
                "threshold": 0,
            }
        )
    summary["pass"] = len(summary["failed_metrics"]) == 0
    return summary
