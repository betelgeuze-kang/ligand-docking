from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest


def _load_module(monkeypatch, artifact_path: Path):
    pytest.importorskip("fastapi")
    import importlib

    mod = importlib.import_module("api.product_gpcr_hard_decoy")
    monkeypatch.setattr(mod, "GPCR_HARD_DECOY_SUITE_ARTIFACT", artifact_path)
    return mod


def _write_artifact(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "packet_type": "gpcr_hard_decoy_suite_report",
                "schema_version": "gpcr_hard_decoy_suite_report_v1",
                "materializer_status": "materialized",
                "summary": {
                    "schema_version": "gpcr_hard_decoy_suite_v1",
                    "status": "broad_family_locked",
                    "family_claim_safe": False,
                    "required_target_ids": ["DRD2", "HTR2A", "OPRM1"],
                    "target_count": 3,
                    "green_target_ids": ["HTR2A"],
                    "blocked_target_ids": ["DRD2", "OPRM1"],
                    "missing_required_target_ids": [],
                    "first_blocked_required_target": "DRD2",
                    "gate": {"ci_low_min": 0.45, "top20_min": 0.2},
                    "claim_boundary": "GPCR hard-decoy suite contract ...",
                    "execution_enabled": False,
                    "external_state_mutated": False,
                    "docking_results_emitted": False,
                },
                "targets": [
                    {"target_id": "DRD2", "gate_status": "blocked", "claim_safe": False},
                    {"target_id": "HTR2A", "gate_status": "green", "claim_safe": True},
                    {"target_id": "OPRM1", "gate_status": "blocked", "claim_safe": False},
                ],
                "claim_boundary": "GPCR hard-decoy suite contract ...",
            }
        ),
        encoding="utf-8",
    )


def test_gpcr_hard_decoy_route_missing_artifact_fail_closed(tmp_path, monkeypatch) -> None:
    mod = _load_module(monkeypatch, tmp_path / "nope.json")
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "missing_gpcr_hard_decoy_suite_report"
    assert payload["family_claim_safe"] is False
    assert payload["required_target_ids"] == ["DRD2", "HTR2A", "OPRM1"]
    assert payload["missing_required_target_ids"] == ["DRD2", "HTR2A", "OPRM1"]
    assert payload["first_blocked_required_target"] == "DRD2"
    assert payload["target_count"] == 0
    assert payload["targets"] == []
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_gpcr_hard_decoy_route_present_artifact_response(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    _write_artifact(artifact)
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "broad_family_locked"
    assert payload["schema_version"] == "gpcr_hard_decoy_suite_v1"
    assert payload["family_claim_safe"] is False
    assert payload["green_target_ids"] == ["HTR2A"]
    assert payload["blocked_target_ids"] == ["DRD2", "OPRM1"]
    assert payload["first_blocked_required_target"] == "DRD2"
    assert payload["gate"] == {"ci_low_min": 0.45, "top20_min": 0.2}
    assert len(payload["targets"]) == 3
    assert payload["execution_enabled"] is False
    assert payload["docking_results_emitted"] is False
    assert payload["external_state_mutated"] is False


def test_gpcr_hard_decoy_route_does_not_promote_broad_claim(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    _write_artifact(artifact)
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    # Locked family must stay non-claimable.
    assert payload["family_claim_safe"] is False
    assert payload["status"] == "broad_family_locked"

    # Missing-artifact claim boundary explicitly disclaims promotion.
    missing_mod = _load_module(monkeypatch, tmp_path / "gone.json")
    missing_payload = asyncio.run(missing_mod.get_product_gpcr_hard_decoy_suite_report())
    boundary = missing_payload["claim_boundary"]
    assert "does not run scoring" in boundary
    assert "generate decoys" in boundary
    assert "relax thresholds" in boundary
    assert "promote broad-GPCR claims" in boundary


def test_gpcr_hard_decoy_route_invalid_json_fail_closed(tmp_path, monkeypatch) -> None:
    artifact = tmp_path / "gpcr_hard_decoy_suite_current.json"
    artifact.write_text("{ not valid json", encoding="utf-8")
    mod = _load_module(monkeypatch, artifact)
    payload = asyncio.run(mod.get_product_gpcr_hard_decoy_suite_report())

    assert payload["status"] == "missing_gpcr_hard_decoy_suite_report"
    assert payload["family_claim_safe"] is False
