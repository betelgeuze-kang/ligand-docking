from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app
from benchmark.external_metric_scorecard import build_external_metric_scorecard
from core.claim_boundary import (
    CLAIM_SCOPE_RESTRICTED_LOCAL,
    TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
    TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
)


def test_external_metric_scorecard_blocks_placeholder_topology() -> None:
    payload = build_external_metric_scorecard(
        inputs=[
            {
                "row_id": "blocked_row",
                "target_id": "T1",
                "topology_fidelity": TOPOLOGY_FIDELITY_PLACEHOLDER_ALANINE,
                "dockq_proxy": 0.9,
            }
        ]
    )
    row = payload["rows"][0]
    assert row["row_status"] == "blocked"
    assert row["dockq_status"] == "blocked"
    assert payload["summary"]["claim_promotion_allowed"] is False
    assert payload["summary"]["claim_scope"] == CLAIM_SCOPE_RESTRICTED_LOCAL


def test_external_metric_scorecard_evaluates_sequence_mapped() -> None:
    payload = build_external_metric_scorecard(
        inputs=[
            {
                "row_id": "eval_row",
                "target_id": "HIV1_PROTEASE",
                "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
                "dockq_proxy": 0.35,
                "lddt_pli": 0.62,
                "molprobity_clashscore": 12.5,
            }
        ]
    )
    row = payload["rows"][0]
    assert row["row_status"] == "evaluated"
    assert row["dockq_status"] == "pass"
    assert row["lddt_pli_status"] == "pass"
    assert row["molprobity_status"] == "pass"
    assert row["metric_family"] == "external_structure_quality_bundle"


def test_external_metric_scorecard_missing_metrics() -> None:
    payload = build_external_metric_scorecard(
        inputs=[
            {
                "row_id": "missing_row",
                "target_id": "T2",
                "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
            }
        ]
    )
    row = payload["rows"][0]
    assert row["row_status"] == "missing"
    assert row["dockq_status"] == "missing"


def test_product_external_metrics_endpoint_missing_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import api.product_benchmark as product_benchmark_mod

    monkeypatch.setattr(product_benchmark_mod, "EXTERNAL_METRIC_SCORECARD_ARTIFACT", tmp_path / "missing.json")
    client = TestClient(app)
    response = client.get("/product/external-metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["status"].startswith("missing_")
    assert body["claim_promotion_allowed"] is False


def test_product_external_metrics_endpoint_with_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    scorecard = build_external_metric_scorecard(
        inputs=[
            {
                "row_id": "api_row",
                "target_id": "T3",
                "topology_fidelity": TOPOLOGY_FIDELITY_SEQUENCE_MAPPED,
                "dockq_proxy": 0.4,
            }
        ]
    )
    artifact = tmp_path / "external_metric_scorecard_current.json"
    artifact.write_text(json.dumps(scorecard), encoding="utf-8")
    import api.product_benchmark as product_benchmark_mod

    monkeypatch.setattr(product_benchmark_mod, "EXTERNAL_METRIC_SCORECARD_ARTIFACT", artifact)
    client = TestClient(app)
    response = client.get("/product/external-metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "external_metric_scorecard_ready"
    assert body["row_count"] == 1
    assert body["claim_promotion_allowed"] is False
