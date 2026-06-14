from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import build_storage_essential_evidence_register as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_essential_evidence_register_classifies_protected_roots(tmp_path: Path) -> None:
    _write(tmp_path / "models" / "selected" / "best_model.pth", "model-weights")
    _write(tmp_path / "models" / "selected" / "checkpoint_manifest.json", "{}")
    _write(tmp_path / "casp17" / "final" / "target_model.pdb", "ATOM\n")
    _write(tmp_path / "casp17" / "viewer" / "target_viewer_current.html", "<html></html>")
    source = tmp_path / "runs" / "product_release_source_of_truth_gate_current.json"
    _write(
        source,
        json.dumps(
            {
                "rows": [
                    {
                        "artifact_id": "viewer",
                        "artifact_path": "casp17/viewer/target_viewer_current.html",
                    }
                ]
            }
        ),
    )

    payload = mod.build_storage_essential_evidence_register(
        root=tmp_path,
        source_of_truth_json=source.relative_to(tmp_path),
        hash_max_bytes=1024,
        hash_row_limit=10,
    )
    summary = payload["summary"]
    rows = {row["path"]: row for row in payload["rows"]}

    assert summary["status"] == "storage_essential_evidence_register_ready"
    assert summary["file_count"] == 4
    assert summary["delete_allowed_count"] == 0
    assert summary["external_state_mutated"] is False
    assert rows["models/selected/best_model.pth"]["evidence_role"] == "model_checkpoint_or_weight"
    assert rows["models/selected/checkpoint_manifest.json"]["evidence_priority"] == "high"
    assert rows["casp17/final/target_model.pdb"]["evidence_role"] == "casp17_structure_coordinate"
    assert rows["casp17/viewer/target_viewer_current.html"]["source_of_truth_reference_count"] == 1
    assert rows["casp17/viewer/target_viewer_current.html"]["delete_allowed_by_this_tool"] is False


def test_essential_evidence_register_defers_large_hashes(tmp_path: Path) -> None:
    _write(tmp_path / "models" / "large_model.pt", "123456789")
    _write(tmp_path / "casp17" / "README.md", "small")

    payload = mod.build_storage_essential_evidence_register(
        root=tmp_path,
        source_of_truth_json="runs/missing.json",
        hash_max_bytes=4,
        hash_row_limit=10,
    )
    rows = {row["path"]: row for row in payload["rows"]}

    assert payload["summary"]["source_of_truth_present"] is False
    assert rows["models/large_model.pt"]["sha256_status"] == "deferred_file_above_hash_max_bytes"
    assert rows["casp17/README.md"]["sha256_status"] == "deferred_file_above_hash_max_bytes"
    assert payload["summary"]["delete_executed"] is False
