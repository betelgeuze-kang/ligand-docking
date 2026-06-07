"""Apply top-K force-residual shortlist hook to scored result rows."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import torch

from theory.force_residual_shortlist import refine_forces_shortlist, should_apply_force_residual


def apply_force_residual_shortlist_hook(
    result_df: pd.DataFrame,
    *,
    top_k_fraction: float = 0.05,
    score_col: str = "binding_score_composite_v7",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if result_df.empty or score_col not in result_df.columns:
        return result_df, {"applied": False, "reason": "empty_or_missing_score_col"}
    out = result_df.copy()
    out["force_residual_applied"] = False
    out["force_residual_delta_score"] = 0.0
    out["force_residual_hbond_mean"] = 0.0
    out["force_residual_hydrophobic_mean"] = 0.0
    sorted_df = out.sort_values(score_col, ascending=True, na_position="last").reset_index(drop=True)
    total = int(len(sorted_df))
    applied_count = 0
    for rank_index, row in sorted_df.iterrows():
        if not should_apply_force_residual(
            rank_index=int(rank_index),
            total_count=total,
            top_k_fraction=float(top_k_fraction),
        ):
            continue
        rep = row.get("representative_ligand_xyz")
        if rep is None or (isinstance(rep, float) and np.isnan(rep)):
            continue
        lig = np.asarray(rep, dtype=np.float32)
        if lig.ndim != 2 or lig.shape[0] <= 0:
            continue
        c = torch.tensor(lig.reshape(1, lig.shape[0], 3), dtype=torch.float32)
        n = int(lig.shape[0])
        nb_idx = torch.arange(n, dtype=torch.long).reshape(1, n, 1).expand(1, n, min(4, n))
        nb_dist = torch.ones(1, n, min(4, n), dtype=torch.float32) * 3.0
        nb_mask = torch.ones(1, n, min(4, n), dtype=torch.float32)
        f_core = torch.zeros_like(c)
        _, meta = refine_forces_shortlist(c, (nb_idx, nb_dist, nb_mask), f_core)
        delta = -0.02 * (
            float(meta.get("hbond_mean_force", 0.0)) + float(meta.get("hydrophobic_mean_force", 0.0))
        )
        qid = str(row.get("queue_id", ""))
        mask = out["queue_id"].astype(str) == qid if "queue_id" in out.columns else out.index == row.name
        out.loc[mask, "force_residual_applied"] = True
        out.loc[mask, "force_residual_delta_score"] = float(delta)
        out.loc[mask, "force_residual_hbond_mean"] = float(meta.get("hbond_mean_force", 0.0))
        out.loc[mask, "force_residual_hydrophobic_mean"] = float(meta.get("hydrophobic_mean_force", 0.0))
        if score_col in out.columns:
            out.loc[mask, score_col] = pd.to_numeric(out.loc[mask, score_col], errors="coerce") + float(delta)
        applied_count += 1
    summary = {
        "applied": bool(applied_count > 0),
        "applied_count": int(applied_count),
        "top_k_fraction": float(top_k_fraction),
        "score_col": str(score_col),
    }
    return out, summary
