from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest


def test_get_product_architecture_validation_read_only(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("fastapi")
    product = importlib.import_module("api.product")
    report_path = tmp_path / "runs" / "architecture_validation_package_report_current.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "summary": {
                    "status": "architecture_validation_packages_in_progress",
                    "package_a_complete": True,
                    "package_b_complete": True,
                    "package_c_complete": False,
                    "open_required_test_ids": ["C-25"],
                    "overclaim_open_test_ids": [],
                    "evidence_depth_tier": "row_evidence_partial",
                    "overclaim_warning_count": 1,
                    "overclaim_hard_warning_count": 0,
                    "claim_boundary": "read-only",
                },
                "rows": [],
                "overclaim_warnings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    external_path = tmp_path / "runs" / "competition_external_operator_track_current.json"
    external_path.write_text(
        json.dumps({"summary": {"status": "operator_pending", "blocked_track_count": 2}}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(product, "ROOT", tmp_path)
    monkeypatch.setattr(product, "ARCHITECTURE_VALIDATION_REPORT_ARTIFACT", report_path)
    monkeypatch.setattr(product, "COMPETITION_EXTERNAL_OPERATOR_TRACK_ARTIFACT", external_path)

    payload = asyncio.run(product.get_product_architecture_validation())
    assert payload["architecture_validation_all_packages_complete"] is False
    assert payload["package_a_complete"] is True
    assert payload["evidence_depth_tier"] == "row_evidence_partial"
    assert payload["claim_promotion_allowed"] is False
    assert payload["execution_enabled"] is False
    assert payload["competition_external_blocked_track_count"] == 2
