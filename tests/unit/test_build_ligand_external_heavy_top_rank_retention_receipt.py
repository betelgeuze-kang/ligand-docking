from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_ligand_external_heavy_top_rank_retention_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_receipt_compacts_top_rank_evidence_and_tracks_payload(tmp_path: Path) -> None:
    heavy = tmp_path / "heavy" / "product_run" / "stage2_trajectory_frames"
    (heavy / "shard_00000").mkdir(parents=True)
    (heavy / "shard_00000" / "a.npz").write_bytes(b"x" * 12)
    _write_json(
        tmp_path / "runs" / "dry.json",
        {
            "summary": {"status": "dry_run", "planned_delete_count": 1},
            "rows": [{"path": str(heavy), "status": "dry_run_delete", "size_bytes": 12, "age_days": 30.0}],
        },
    )
    _write_json(
        tmp_path / "runs" / "summary.json",
        {
            "pass": True,
            "rows_eval": 2,
            "eval_unique_keys": 2,
            "score_col": "score",
            "lower_better": True,
            "metrics": {"roc_auc": 1.0, "pr_auc": 1.0, "ef1": 2.0},
            "topk": [{"k": 1, "hit_rate": 1.0, "enrichment_factor": 2.0, "hits": 1}],
        },
    )
    (tmp_path / "runs" / "topk.csv").write_text("k,hit_rate,enrichment_factor,hits\n1,1.0,2.0,1\n", encoding="utf-8")
    (tmp_path / "runs" / "unique.csv").write_text(
        "target,ligand_id,score,is_binder\nT,L1,-9,1\nT,L2,3,0\n",
        encoding="utf-8",
    )
    _write_json(tmp_path / "runs" / "shortlist.json", {"selected_count": 4})

    payload = mod.build_receipt(
        root=tmp_path,
        run_name="product_run",
        heavy_payload_path=str(heavy),
        dry_run_json="runs/dry.json",
        ranking_summary_json="runs/summary.json",
        ranking_topk_csv="runs/topk.csv",
        ranking_unique_csv="runs/unique.csv",
        refine_shortlist_json="runs/shortlist.json",
        existing_receipt_json="config/out.json",
        top_n=1,
    )

    assert payload["summary"]["status"] == "ligand_external_heavy_top_rank_retention_ready_for_delete"
    assert payload["cleanup"]["pre_delete_file_count"] == 1
    assert payload["ranking"]["top_rows_retained_count"] == 1
    assert payload["ranking"]["top_rows"][0]["ligand_id"] == "L1"
    assert payload["ranking"]["metrics"]["roc_auc"] == 1.0


def test_receipt_preserves_previous_pre_delete_count_after_deletion(tmp_path: Path) -> None:
    heavy = tmp_path / "heavy" / "product_run" / "stage2_trajectory_frames"
    _write_json(
        tmp_path / "config" / "out.json",
        {"cleanup": {"pre_delete_file_count": 3, "pre_delete_size_bytes": 30}},
    )
    _write_json(
        tmp_path / "runs" / "dry.json",
        {"summary": {"status": "dry_run", "planned_delete_count": 1}, "rows": [{"path": str(heavy), "size_bytes": 30}]},
    )
    _write_json(tmp_path / "runs" / "summary.json", {"pass": True, "metrics": {}, "topk": []})
    (tmp_path / "runs" / "topk.csv").write_text("k,hit_rate,enrichment_factor,hits\n", encoding="utf-8")
    (tmp_path / "runs" / "unique.csv").write_text("target,ligand_id,score\nT,L1,-1\n", encoding="utf-8")
    _write_json(tmp_path / "runs" / "shortlist.json", {"selected_count": 1})

    payload = mod.build_receipt(
        root=tmp_path,
        run_name="product_run",
        heavy_payload_path=str(heavy),
        dry_run_json="runs/dry.json",
        ranking_summary_json="runs/summary.json",
        ranking_topk_csv="runs/topk.csv",
        ranking_unique_csv="runs/unique.csv",
        refine_shortlist_json="runs/shortlist.json",
        existing_receipt_json="config/out.json",
    )

    assert payload["summary"]["status"] == "ligand_external_heavy_payload_deleted_top_rank_retained"
    assert payload["cleanup"]["pre_delete_file_count"] == 3
    assert payload["cleanup"]["pre_delete_size_bytes"] == 30
