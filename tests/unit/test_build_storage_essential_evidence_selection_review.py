from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_storage_essential_evidence_selection_review as mod


def _write_register(path: Path) -> None:
    rows = [
        {
            "path": "models/a/best_a.pth",
            "domain": "models/a",
            "size_bytes": 100,
            "evidence_role": "model_checkpoint_or_weight",
            "evidence_priority": "high",
            "source_of_truth_reference_count": 0,
            "sha256_status": "deferred_file_above_hash_max_bytes",
        },
        {
            "path": "models/a/manifest.json",
            "domain": "models/a",
            "size_bytes": 10,
            "evidence_role": "model_manifest_or_registry",
            "evidence_priority": "high",
            "source_of_truth_reference_count": 0,
            "sha256_status": "recorded",
        },
        {
            "path": "casp17/targets_current/t1/model.pdb",
            "domain": "casp17/targets_current",
            "size_bytes": 60,
            "evidence_role": "casp17_structure_coordinate",
            "evidence_priority": "medium",
            "source_of_truth_reference_count": 1,
            "sha256_status": "recorded",
        },
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "storage_essential_evidence_register_ready",
                    "file_count": len(rows),
                    "total_size_human": "170.00 B",
                },
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )


def test_selection_review_prioritizes_top_domains(tmp_path: Path) -> None:
    register = tmp_path / "runs" / "storage_essential_evidence_register_current.json"
    _write_register(register)

    payload = mod.build_storage_essential_evidence_selection_review(
        root=tmp_path,
        register_json=register.relative_to(tmp_path),
        top_domain_limit=2,
    )
    summary = payload["summary"]
    rows = payload["rows"]

    assert summary["status"] == "storage_essential_evidence_selection_review_ready"
    assert summary["source_register_present"] is True
    assert summary["review_domain_count"] == 2
    assert summary["cleanup_allowed_count"] == 0
    assert summary["delete_executed"] is False
    assert rows[0]["domain"] == "models/a"
    assert rows[0]["review_action_id"] == "model_checkpoint_selection_review"
    assert rows[0]["keep_before_cleanup"] is True
    assert rows[1]["domain"] == "casp17/targets_current"
    assert rows[1]["review_action_id"] == "casp17_final_target_register_review"


def test_selection_review_missing_register_stays_read_only(tmp_path: Path) -> None:
    payload = mod.build_storage_essential_evidence_selection_review(
        root=tmp_path,
        register_json="runs/missing.json",
    )
    summary = payload["summary"]

    assert summary["source_register_present"] is False
    assert summary["review_domain_count"] == 0
    assert summary["cleanup_allowed_count"] == 0
    assert summary["external_state_mutated"] is False
