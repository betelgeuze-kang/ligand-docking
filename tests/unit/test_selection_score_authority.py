from __future__ import annotations

import copy
import json

import pandas as pd
import pytest

from betelgeuze_engine.product.runners.topk_delivery import _select_topk
from betelgeuze_engine.product.selection_score_authority import (
    SelectionScoreAuthority,
    SelectionScoreAuthorityError,
    load_authority_summary,
    rank_selection_frame,
    resolve_selection_score_authority,
    topk_eligible_frame,
)


def _opposite_v7_v3_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "queue_id": "q-v7",
                "target": "A",
                "ligand_id": "v7_winner",
                "binding_score_composite_v7": -9.0,
                "binding_score_composite_v3": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -7.0,
                "stability_score": 0.5,
            },
            {
                "queue_id": "q-v3",
                "target": "A",
                "ligand_id": "v3_winner",
                "binding_score_composite_v7": -1.0,
                "binding_score_composite_v3": -9.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -8.0,
                "stability_score": 0.6,
            },
        ]
    )


def test_backmapping_and_topk_authority_choose_same_v7_top1() -> None:
    scores = _opposite_v7_v3_frame()
    backmapping_authority = resolve_selection_score_authority(scores)
    backmapping_ranked = rank_selection_frame(scores, backmapping_authority)
    topk_authority = resolve_selection_score_authority(
        scores,
        declared_authority=backmapping_authority.to_dict(),
    )
    selected, _ = _select_topk(
        scores,
        authority=topk_authority,
        topk_global=1,
        topk_per_target=0,
        selection_mode="global_only",
    )

    assert backmapping_authority.to_dict() == topk_authority.to_dict()
    assert backmapping_ranked.iloc[0]["ligand_id"] == "v7_winner"
    assert selected.iloc[0]["ligand_id"] == "v7_winner"


def test_requested_missing_score_column_fails_without_fallback() -> None:
    with pytest.raises(SelectionScoreAuthorityError, match="requested score column"):
        resolve_selection_score_authority(
            _opposite_v7_v3_frame(),
            requested_score_column="binding_score_composite_v8",
        )


def test_residual_active_authority_requires_apply_capable_mode() -> None:
    scores = _opposite_v7_v3_frame().assign(
        binding_score_composite_v7_residual_active=[-1.0, -10.0]
    )
    base = resolve_selection_score_authority(
        scores,
        residual_metadata={
            "active_score_col": "binding_score_composite_v7",
            "mode": "shadow_only",
            "status": "shadow_ready",
        },
    )
    applied = resolve_selection_score_authority(
        scores,
        residual_metadata={
            "active_score_col": "binding_score_composite_v7_residual_active",
            "mode": "apply",
            "status": "apply_ready",
        },
    )

    assert base.residual_mode == "base"
    assert base.score_column == "binding_score_composite_v7"
    assert applied.residual_mode == "apply"
    assert applied.score_column == "binding_score_composite_v7_residual_active"
    with pytest.raises(SelectionScoreAuthorityError, match="apply-capable"):
        resolve_selection_score_authority(
            scores,
            residual_metadata={
                "active_score_col": "binding_score_composite_v7_residual_active",
                "mode": "shadow_only",
                "status": "shadow_ready",
            },
        )


def test_direction_ties_and_primary_nan_follow_one_policy() -> None:
    scores = pd.DataFrame(
        [
            {
                "ligand_id": "b",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -5.0,
                "stability_score": 0.5,
            },
            {
                "ligand_id": "nan",
                "binding_score_composite_v7": None,
                "binding_energy_mmpbsa_kcal_mol_proxy": -100.0,
                "stability_score": 1.0,
            },
            {
                "ligand_id": "a",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -5.0,
                "stability_score": 0.5,
            },
            {
                "ligand_id": "proxy_tie_winner",
                "binding_score_composite_v7": -1.0,
                "binding_energy_mmpbsa_kcal_mol_proxy": -6.0,
                "stability_score": 0.1,
            },
        ]
    )
    authority = resolve_selection_score_authority(scores)
    ranked = rank_selection_frame(scores, authority)
    eligible = topk_eligible_frame(ranked, authority)

    assert ranked["ligand_id"].tolist() == ["proxy_tie_winner", "a", "b", "nan"]
    assert eligible["ligand_id"].tolist() == ["proxy_tie_winner", "a", "b"]

    descending = SelectionScoreAuthority.create(
        score_column="quality",
        score_direction="descending",
        source_stage="unit_quality_stage",
    )
    quality_ranked = rank_selection_frame(
        pd.DataFrame([{"ligand_id": "low", "quality": 0.1}, {"ligand_id": "high", "quality": 0.9}]),
        descending,
    )
    assert quality_ranked["ligand_id"].tolist() == ["high", "low"]


def test_policy_hash_is_deterministic_and_rejects_tampering(tmp_path) -> None:
    first = resolve_selection_score_authority(_opposite_v7_v3_frame())
    second = resolve_selection_score_authority(_opposite_v7_v3_frame())
    assert first.policy_sha256 == second.policy_sha256

    tampered = copy.deepcopy(first.to_dict())
    tampered["source_stage"] = "tampered_stage"
    with pytest.raises(SelectionScoreAuthorityError, match="policy_sha256 mismatch"):
        SelectionScoreAuthority.from_mapping(tampered)

    summary_path = tmp_path / "stage3_summary.json"
    summary_path.write_text(
        json.dumps({"selection_score_authority": first.to_dict()}),
        encoding="utf-8",
    )
    loaded = SelectionScoreAuthority.from_mapping(load_authority_summary(str(summary_path)))
    assert loaded.to_dict() == first.to_dict()
