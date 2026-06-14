from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_ligand_heavy_run_retention_receipt as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_retention_receipt_records_delete_rows_and_retained_evidence(tmp_path: Path) -> None:
    manifest = {
        "summary": {
            "candidate_count": 3,
            "candidate_size_human": "10.00 MiB",
            "delete_recommended_count": 1,
            "delete_recommended_size_bytes": 1024,
            "delete_recommended_size_human": "1.00 KiB",
            "top_rank_keep_count": 2,
            "top_rank_keep_size_human": "2.00 KiB",
            "review_required_count": 0,
            "review_required_size_human": "0.00 B",
        },
        "rows": [
            {
                "path": "runs/old_stage3_scores.csv",
                "cleanup_class": "raw_stage3_scores",
                "path_type": "file",
                "size_bytes": 1024,
                "size_human": "1.00 KiB",
                "disposition": "delete_after_top_rank_manifest_approval",
                "reason": "old raw payload has compact evidence",
                "delete_recommended": True,
                "preserved_evidence_count": 2,
                "preserved_evidence": "runs/old_stage5_ranking_topk.csv;runs/old_stage5_ranking_summary.json",
            }
        ],
    }
    execution = {
        "summary": {
            "status": "ligand_heavy_run_cleanup_execution_complete",
            "deleted_count": 1,
            "deleted_size_bytes": 1024,
            "deleted_size_human": "1.00 KiB",
            "failed_count": 0,
            "missing_count": 0,
            "local_filesystem_mutated": True,
        },
        "rows": [{"path": "runs/old_stage3_scores.csv", "status": "deleted"}],
    }
    manifest_path = tmp_path / "runs" / "manifest.json"
    execution_path = tmp_path / "runs" / "execution.json"
    _write_json(manifest_path, manifest)
    _write_json(execution_path, execution)

    payload = mod.build_ligand_heavy_run_retention_receipt(
        root=tmp_path,
        manifest_json="runs/manifest.json",
        execution_json="runs/execution.json",
        existing_receipt_json=None,
    )

    summary = payload["summary"]
    assert summary["status"] == "ligand_heavy_run_retention_receipt_execution_recorded"
    assert summary["execution_deleted_count"] == 1
    assert summary["cumulative_execution_deleted_count"] == 1
    assert summary["external_state_mutated"] is False
    assert payload["retained_top_rank_or_compact_evidence"] == [
        "runs/old_stage5_ranking_topk.csv",
        "runs/old_stage5_ranking_summary.json",
    ]
    assert payload["delete_records"][0]["execution_status"] == "deleted"


def test_retention_receipt_is_ready_without_execution(tmp_path: Path) -> None:
    manifest = {
        "summary": {"delete_recommended_count": 0},
        "rows": [],
    }
    _write_json(tmp_path / "runs" / "manifest.json", manifest)

    payload = mod.build_ligand_heavy_run_retention_receipt(
        root=tmp_path,
        manifest_json="runs/manifest.json",
        execution_json="runs/missing_execution.json",
        existing_receipt_json=None,
    )

    assert payload["summary"]["status"] == "ligand_heavy_run_retention_receipt_ready"
    assert payload["summary"]["execution_present"] is False


def test_retention_receipt_merges_existing_delete_records(tmp_path: Path) -> None:
    manifest = {
        "summary": {
            "delete_recommended_count": 1,
            "delete_recommended_size_bytes": 512,
            "delete_recommended_size_human": "512.00 B",
        },
        "rows": [
            {
                "path": "runs/new.log",
                "cleanup_class": "transient_ligand_run_log_or_lock",
                "path_type": "file",
                "size_bytes": 512,
                "size_human": "512.00 B",
                "disposition": "delete_after_top_rank_manifest_approval",
                "reason": "transient log",
                "delete_recommended": True,
                "preserved_evidence_count": 1,
                "preserved_evidence": "runs/new_summary.json",
            }
        ],
    }
    execution = {
        "summary": {
            "status": "ligand_heavy_run_cleanup_execution_complete",
            "deleted_count": 1,
            "deleted_size_bytes": 512,
            "deleted_size_human": "512.00 B",
            "failed_count": 0,
            "missing_count": 0,
        },
        "rows": [{"path": "runs/new.log", "status": "deleted"}],
    }
    existing_receipt = {
        "delete_records": [
            {
                "path": "runs/old_stage3_scores.csv",
                "cleanup_class": "raw_stage3_scores",
                "path_type": "file",
                "size_bytes": 1024,
                "size_human": "1.00 KiB",
                "disposition": "delete_after_top_rank_manifest_approval",
                "reason": "old raw payload",
                "preserved_evidence_count": 1,
                "preserved_evidence": ["runs/old_stage5_ranking_topk.csv"],
                "execution_status": "deleted",
            }
        ]
    }
    _write_json(tmp_path / "runs" / "manifest.json", manifest)
    _write_json(tmp_path / "runs" / "execution.json", execution)
    _write_json(tmp_path / "config" / "receipt.json", existing_receipt)

    payload = mod.build_ligand_heavy_run_retention_receipt(
        root=tmp_path,
        manifest_json="runs/manifest.json",
        execution_json="runs/execution.json",
        existing_receipt_json="config/receipt.json",
    )

    summary = payload["summary"]
    assert summary["execution_deleted_count"] == 1
    assert summary["cumulative_execution_deleted_count"] == 2
    assert summary["delete_record_count"] == 2
    assert [row["path"] for row in payload["delete_records"]] == [
        "runs/old_stage3_scores.csv",
        "runs/new.log",
    ]
    assert payload["retained_top_rank_or_compact_evidence"] == [
        "runs/old_stage5_ranking_topk.csv",
        "runs/new_summary.json",
    ]
