from __future__ import annotations

from pathlib import Path

from tools.product.run_refine_tier_residual_training_chain import run_refine_tier_residual_training_chain


def _write_stage5(path: Path, rows: int = 40) -> None:
    header = (
        "target,ligand_id,is_binder,role,reference_binding_kcal_mol,"
        "binding_score_composite_v7,mean_min_distance_A\n"
    )
    body = "\n".join(
        f"ADRB2_GPCR_BLIND,lig{i},{1 if i % 2 == 0 else 0},fit,"
        f"{-9.0 if i % 2 == 0 else -2.0},{-8.0 if i % 2 == 0 else -1.0},3.0"
        for i in range(rows)
    )
    path.write_text(header + body + "\n", encoding="utf-8")


def _write_stage3(path: Path, rows: int = 40) -> None:
    header = (
        "target,ligand_id,binding_energy_mmpbsa_kcal_mol_proxy,"
        "deltaG_mm_gbsa_kcal_mol,physics_refinement_confidence\n"
    )
    body = "\n".join(
        f"ADRB2_GPCR_BLIND,lig{i},{-6.0 - i * 0.01},{-5.0 - i * 0.01},{0.5 + (i % 5) * 0.08}"
        for i in range(rows)
    )
    path.write_text(header + body + "\n", encoding="utf-8")


def test_run_refine_tier_residual_training_chain(tmp_path: Path) -> None:
    stage5 = tmp_path / "htvs_stage5_ranking_rows.csv"
    stage3 = tmp_path / "htvs_stage3_scores.csv"
    _write_stage5(stage5)
    _write_stage3(stage3)

    summary = run_refine_tier_residual_training_chain(
        stage5_glob=str(stage5),
        stage3_csv=str(stage3),
        dataset_csv=str(tmp_path / "dataset.csv"),
        enriched_csv=str(tmp_path / "enriched.csv"),
        out_checkpoint=str(tmp_path / "model.pt"),
        out_summary_json=str(tmp_path / "chain.json"),
        min_rows=20,
        min_targets=1,
        epochs=2,
        hidden_dim=8,
        batch_size=8,
    )

    assert summary["refine_tier_training_chain_ready"] is True
    assert summary["enrichment"]["refine_tier_label_rows"] == 40
    assert Path(summary["out_checkpoint"]).exists()
