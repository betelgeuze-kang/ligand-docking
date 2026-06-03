from __future__ import annotations

import json
from pathlib import Path

from tools import build_protected_ligand_heavy_payload_deep_review as mod


def _review(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    recent_big = root / "recent_big"
    recent_big.mkdir()
    (recent_big / "stage2_trajectory_frames").mkdir()
    (recent_big / "stage2_trajectory_frames" / "frame.bin").write_bytes(b"x" * 10)
    (recent_big / "stage3_delivery").mkdir()
    (recent_big / "stage3_delivery" / "summary.json").write_text("{}\n", encoding="utf-8")
    recent_small = root / "recent_small"
    recent_small.mkdir()
    (recent_small / "stage2_trajectory_frames").mkdir()
    (recent_small / "stage3_delivery").mkdir()
    return {
        "summary": {
            "status": "protected_cleanup_payload_review_ready",
            "protected_payload_row_count": 2,
            "protected_payload_size_gb": 0.0,
        },
        "rows": [
            {
                "path": str(recent_big),
                "source_dry_run_status": "kept_recent_slot",
                "source_dry_run_reason": "protected by keep-recent",
                "known_payload_size_gb": 0.0,
                "current_policy_action": "keep_protected",
            },
            {
                "path": str(recent_small),
                "source_dry_run_status": "kept_recent_slot",
                "source_dry_run_reason": "protected by keep-recent",
                "known_payload_size_gb": 0.0,
                "current_policy_action": "keep_protected",
            },
        ],
    }


def test_protected_ligand_heavy_payload_deep_review_splits_payload_and_siblings(tmp_path: Path) -> None:
    payload = mod.build_protected_ligand_heavy_payload_deep_review(_review(tmp_path))
    summary = payload["summary"]

    assert summary["status"] == "protected_ligand_heavy_payload_deep_review_ready"
    assert summary["known_payload_child_count"] == 2
    assert summary["preservation_sibling_count"] == 2
    assert summary["policy_change_required_for_deletion_count"] == 2
    assert summary["approval_promoted_count"] == 0
    assert summary["delete_executed"] is False
    assert summary["external_state_mutated"] is False
    roles = {row["child_name"]: row["child_role"] for row in payload["rows"]}
    assert roles["stage2_trajectory_frames"] == "known_payload_child"
    assert roles["stage3_delivery"] == "preservation_sibling"
    assert all(row["approval_promoted"] is False for row in payload["rows"])


def test_protected_ligand_heavy_payload_deep_review_tool_writes_outputs(tmp_path: Path) -> None:
    review_json = tmp_path / "review.json"
    out_json = tmp_path / "deep.json"
    out_csv = tmp_path / "deep.csv"
    out_md = tmp_path / "deep.md"
    review_json.write_text(json.dumps(_review(tmp_path / "runs")) + "\n", encoding="utf-8")

    mod.main(
        [
            "--protected-review-json",
            str(review_json),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ]
    )

    assert json.loads(out_json.read_text(encoding="utf-8"))["summary"]["known_payload_child_count"] == 2
    assert out_csv.read_text(encoding="utf-8").startswith("protected_path,child_path,")
    assert "Protected Ligand Heavy Payload Deep Review" in out_md.read_text(encoding="utf-8")
