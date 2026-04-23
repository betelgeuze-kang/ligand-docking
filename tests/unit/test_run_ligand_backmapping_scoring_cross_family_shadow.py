from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from tools import run_ligand_backmapping_scoring as mod


def _shadow_args(family: str) -> argparse.Namespace:
    return argparse.Namespace(
        residual_prototype_enabled=True,
        residual_prototype_mode="shadow_only",
        residual_prototype_family=family,
        residual_prototype_spec_json="",
        residual_prototype_runtime_hook_ready=True,
        residual_prototype_max_abs_delta_score=1.5,
        residual_prototype_yellow_band_abs_delta_score=0.75,
    )


def test_apply_residual_prototype_shadow_ion_and_kinase_emit_noop_shadow_columns() -> None:
    result_df = pd.DataFrame(
        [
            {"ligand_id": "lig_a", "binding_score_composite_v7": -7.0},
            {"ligand_id": "lig_b", "binding_score_composite_v7": -6.0},
        ]
    )
    one = pd.Series([1.0, 0.5], dtype=float)
    zero = pd.Series([0.0, 0.0], dtype=float)

    for family in ["ion_channel", "kinase"]:
        out_df, meta = mod._apply_residual_prototype_shadow(
            result_df.copy(),
            _shadow_args(family),
            z_e=zero,
            z_d=one,
            z_s=zero,
            z_c=zero,
            z_aff=zero,
            z_logp=zero,
            z_rot=one,
            z_hd=one,
            z_ha=one,
        )
        assert meta["status"] == "shadow_ready_noop_family"
        assert meta["family"] == family
        assert meta["active_score_col"] == "binding_score_composite_v7"
        assert meta["shadow_score_col"] == "binding_score_composite_v7_residual_shadow"
        np.testing.assert_allclose(
            out_df["binding_score_composite_v7_residual_shadow"].to_numpy(dtype=float),
            out_df["binding_score_composite_v7"].to_numpy(dtype=float),
        )
        np.testing.assert_allclose(
            out_df["binding_score_composite_v7_residual_active"].to_numpy(dtype=float),
            out_df["binding_score_composite_v7"].to_numpy(dtype=float),
        )
        assert bool((out_df["residual_shadow_delta"] == 0.0).all()) is True
