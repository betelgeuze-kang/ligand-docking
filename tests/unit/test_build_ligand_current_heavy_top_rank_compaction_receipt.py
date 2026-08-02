from __future__ import annotations

import os
from pathlib import Path

from tools.accounting import build_ligand_current_heavy_top_rank_compaction_receipt as mod


NOW = 1_800_000_000.0


def _write_old(path: Path, text: str, *, age_days: int = 30) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    ts = NOW - age_days * 86_400
    os.utime(path, (ts, ts))


def test_current_heavy_compaction_keeps_top_rows_without_deleting(tmp_path: Path) -> None:
    csv_path = tmp_path / "runs" / "gpcr_cationic_demo_shadow_replay_scores_current.csv"
    _write_old(
        csv_path,
        "\n".join(
            [
                "target,ligand_id,binding_score_composite_v7_residual_shadow,base_score",
                "T,L1,-3.0,-1.0",
                "T,L2,-7.0,-2.0",
                "T,L3,-5.0,-3.0",
            ]
        )
        + "\n",
    )
    _write_old(
        tmp_path / "runs" / "wetlab_broad_screen_compound_universe_current.csv",
        "ligand_id\nA\n",
    )

    payload = mod.build_ligand_current_heavy_top_rank_compaction_receipt(
        root=tmp_path,
        min_size_bytes=1,
        top_n=2,
        now=NOW,
    )

    assert payload["summary"]["status"] == "ligand_current_heavy_top_rank_compaction_ready"
    assert payload["summary"]["candidate_count"] == 1
    assert payload["summary"]["top_rows_retained_count"] == 2
    row = payload["rows"][0]
    assert row["score_col"] == "binding_score_composite_v7_residual_shadow"
    assert row["delete_status"] == "pending_delete_after_top_rank_retention"
    assert row["top_rows"][0]["ligand_id"] == "L2"
    assert row["top_rows"][1]["ligand_id"] == "L3"
    assert csv_path.exists()
    assert (tmp_path / row["top_rank_output_csv"]).is_file()
    assert payload["skipped_large_files"][0]["reason"] == "skipped_non_run_input_or_inventory_payload"


def test_current_heavy_compaction_prefers_guarded_claim_review_score(tmp_path: Path) -> None:
    guarded_col = "binding_score_composite_v7_htr2a_oprm1_drd2_weakbase_false_support_shadow"
    csv_path = tmp_path / "runs" / "gpcr_drd2_weakbase_false_support_shadow_replay_scores_current.csv"
    _write_old(
        csv_path,
        "\n".join(
            [
                f"target,ligand_id,binding_score_composite_v7_residual_shadow,{guarded_col}",
                "T,L1,-100.0,-1.0",
                "T,L2,-2.0,-9.0",
                "T,L3,-3.0,-5.0",
            ]
        )
        + "\n",
    )

    payload = mod.build_ligand_current_heavy_top_rank_compaction_receipt(
        root=tmp_path,
        min_size_bytes=1,
        top_n=2,
        now=NOW,
    )

    row = payload["rows"][0]
    assert row["score_col"] == guarded_col
    assert row["top_rows"][0]["ligand_id"] == "L2"
    assert row["top_rows"][0]["score_col"] == guarded_col
    assert row["top_rows"][0]["score_value"] == "-9.0"


def test_current_heavy_compaction_deletes_only_with_valid_approval(tmp_path: Path) -> None:
    csv_path = tmp_path / "runs" / "gpcr_cationic_demo_feature_cache_current.csv"
    _write_old(
        csv_path,
        "\n".join(
            [
                "target,ligand_id,base_score,feature_cache_status",
                "T,L1,-1.0,ok",
                "T,L2,-9.0,ok",
            ]
        )
        + "\n",
    )

    payload = mod.build_ligand_current_heavy_top_rank_compaction_receipt(
        root=tmp_path,
        min_size_bytes=1,
        top_n=1,
        execute=True,
        approval_token=mod.APPROVAL_TOKEN,
        now=NOW,
    )

    assert payload["summary"]["deleted_count"] == 1
    assert payload["summary"]["local_filesystem_mutated"] is True
    assert payload["rows"][0]["delete_status"] == "deleted"
    assert payload["rows"][0]["top_rows"][0]["ligand_id"] == "L2"
    assert not csv_path.exists()
    assert (tmp_path / payload["rows"][0]["top_rank_output_csv"]).is_file()


def test_current_heavy_compaction_accepts_ligand_refine_scores_without_gpcr_name(tmp_path: Path) -> None:
    csv_path = (
        tmp_path
        / "runs"
        / "external_validation_2026-05-12_ligandonly_kinase_core_stage3_refine_scores.csv"
    )
    _write_old(
        csv_path,
        "\n".join(
            [
                "queue_id,target,ligand_id,ligand_smiles,binding_score_composite_v7,internal_refine_proxy_score,export_rank",
                "Q1,EGFR,L1,C,-11.0,-8.0,2",
                "Q2,EGFR,L2,CC,-20.0,-12.0,1",
                "Q3,EGFR,L3,CCC,-5.0,-3.0,3",
            ]
        )
        + "\n",
    )

    payload = mod.build_ligand_current_heavy_top_rank_compaction_receipt(
        root=tmp_path,
        min_size_bytes=1,
        top_n=2,
        now=NOW,
    )

    assert payload["summary"]["candidate_count"] == 1
    row = payload["rows"][0]
    assert row["path"].endswith("stage3_refine_scores.csv")
    assert row["score_col"] == "binding_score_composite_v7"
    assert row["top_rows"][0]["ligand_id"] == "L2"
    assert row["top_rows"][0]["queue_id"] == "Q2"
    assert row["top_rows"][0]["internal_refine_proxy_score"] == "-12.0"
    assert row["delete_status"] == "pending_delete_after_top_rank_retention"
