from __future__ import annotations

from tools import build_tools_package_batch3_package_classification_plan as mod


def test_batch3_package_classification_plan_classifies_package_lane_rows() -> None:
    payload = mod.build_tools_package_batch3_package_classification_plan(
        lane_decomposition_packet={
            "summary": {"status": "tools_package_batch3_lane_decomposition_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/build_caix_launch_packet.py",
                    "decomposition_lane": "package_classification_required",
                },
                {
                    "tool_path": "tools/build_biorxiv_submission_assets.py",
                    "decomposition_lane": "package_classification_required",
                },
                {
                    "tool_path": "tools/prune_runs_files.py",
                    "decomposition_lane": "package_classification_required",
                },
                {
                    "tool_path": "tools/__init__.py",
                    "decomposition_lane": "package_classification_required",
                },
            ],
        }
    )

    summary = payload["summary"]
    assert summary["status"] == "tools_package_batch3_package_classification_plan_ready"
    assert summary["candidate_count"] == 4
    assert summary["classified_count"] == 4
    assert summary["unclassified_count"] == 0
    rows = {row["tool_path"]: row for row in payload["rows"]}
    assert rows["tools/build_caix_launch_packet.py"]["reclassified_package"] == "wetlab"
    assert rows["tools/build_biorxiv_submission_assets.py"]["target_path"] == (
        "tools/product/build_biorxiv_submission_assets.py"
    )
    assert rows["tools/prune_runs_files.py"]["target_path"] == "tools/cleanup/prune_runs_files.py"
    assert rows["tools/__init__.py"]["reclassified_package"] == "canonical_owner_review"
    assert rows["tools/__init__.py"]["target_path"] == ""


def test_batch3_package_classification_blocks_unknown_rows() -> None:
    payload = mod.build_tools_package_batch3_package_classification_plan(
        lane_decomposition_packet={
            "summary": {"status": "tools_package_batch3_lane_decomposition_plan_ready"},
            "rows": [
                {
                    "tool_path": "tools/mystery.py",
                    "decomposition_lane": "package_classification_required",
                }
            ],
        }
    )

    assert payload["summary"]["status"] == "blocked_tools_package_batch3_package_classification_plan"
    assert payload["summary"]["unclassified_count"] == 1
    assert payload["rows"][0]["classification_status"] == "manual_review_required"
