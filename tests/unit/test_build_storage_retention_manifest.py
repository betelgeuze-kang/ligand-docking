from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_storage_retention_manifest as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_storage_retention_manifest_flags_only_unreferenced_cleanup_candidates(tmp_path: Path) -> None:
    _write(tmp_path / "runs" / "release_current.json", "{}")
    _write(tmp_path / "logs" / "debug.log", "debug")
    _write(tmp_path / "models" / "selected.ckpt", "checkpoint")
    source_of_truth = tmp_path / "runs" / "product_release_source_of_truth_gate_current.json"
    source_of_truth.write_text(
        json.dumps(
            {
                "summary": {"status": "product_release_source_of_truth_gate_ready"},
                "rows": [
                    {
                        "artifact_id": "release",
                        "artifact_path": "runs/release_current.json",
                        "status": "pass",
                    },
                    {
                        "artifact_id": "model",
                        "artifact_path": "models/selected.ckpt",
                        "status": "pass",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = mod.build_storage_retention_manifest(
        root=tmp_path,
        source_of_truth_json=source_of_truth.relative_to(tmp_path),
        inventory_roots=(
            (
                "runs",
                "current_release_ledgers_and_generated_history",
                "keep_current_source_of_truth_ledgers_then_review_historical_bulk",
                "operator_review_manifest_required",
                "runs evidence",
            ),
            (
                "models",
                "model_checkpoint_assets",
                "keep_selected_checkpoint_receipts_and_review_training_intermediates",
                "operator_review_manifest_required",
                "model evidence",
            ),
            (
                "logs",
                "transient_logs",
                "preserve_summarized_evidence_then_delete_if_unreferenced",
                "delete_after_manifest_review",
                "logs",
            ),
        ),
    )
    summary = payload["summary"]
    rows = {row["path"]: row for row in payload["rows"]}

    assert summary["status"] == "storage_retention_manifest_ready"
    assert summary["source_of_truth_present"] is True
    assert summary["cleanup_candidate_count"] == 1
    assert summary["delete_allowed_count"] == 0
    assert summary["external_state_mutated"] is False
    assert rows["runs"]["source_of_truth_reference_count"] == 1
    assert rows["runs"]["cleanup_candidate"] is False
    assert rows["models"]["source_of_truth_reference_count"] == 1
    assert rows["models"]["cleanup_candidate"] is False
    assert rows["logs"]["source_of_truth_reference_count"] == 0
    assert rows["logs"]["cleanup_candidate"] is True
    assert rows["logs"]["delete_allowed_by_this_tool"] is False


def test_storage_retention_manifest_missing_source_of_truth_stays_read_only(tmp_path: Path) -> None:
    _write(tmp_path / ".pytest_cache" / "cache.txt", "cache")
    _write(tmp_path / "models" / "selected.ckpt", "checkpoint")

    payload = mod.build_storage_retention_manifest(
        root=tmp_path,
        source_of_truth_json="runs/missing.json",
        inventory_roots=(
            (
                "models",
                "model_checkpoint_assets",
                "keep_selected_checkpoint_receipts_and_review_training_intermediates",
                "operator_review_manifest_required",
                "model evidence",
            ),
            (
                ".pytest_cache",
                "regenerable_cache",
                "delete_when_disk_pressure_blocks_work",
                "regenerable_cache",
                "cache",
            ),
        ),
    )
    summary = payload["summary"]

    assert summary["source_of_truth_present"] is False
    assert summary["cleanup_candidate_count"] == 1
    assert summary["essential_evidence_manifest_required_count"] == 1
    rows = {row["path"]: row for row in payload["rows"]}
    assert rows["models"]["cleanup_candidate"] is False
    assert rows["models"]["essential_evidence_manifest_required"] is True
    assert rows[".pytest_cache"]["cleanup_candidate"] is True
    assert summary["delete_executed"] is False
    assert summary["archive_executed"] is False
    assert summary["externalize_executed"] is False
