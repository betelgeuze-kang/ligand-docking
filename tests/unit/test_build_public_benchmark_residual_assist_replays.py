from __future__ import annotations

import json
from pathlib import Path

from tools.product import build_public_benchmark_residual_assist_comparisons as comparisons_mod
from tools.product import build_public_benchmark_residual_assist_replays as replays_mod


def _public_contract() -> dict[str, object]:
    return {
        "summary": {
            "status": "product_public_benchmark_contract_ready",
            "public_benchmark_validation_ready": True,
            "required_suite_count": 1,
        },
        "rows": [
            {
                "suite_id": "suite_replay",
                "benchmark_family": "family",
                "status": "ready",
                "scorecard_json": "runs/suite_replay_scorecard_current.json",
                "primary_metric": "ROC_AUC",
                "primary_metric_value": 0.8,
                "primary_metric_threshold": 0.6,
                "regression_baseline_ref": "suite_replay:baseline",
            }
        ],
    }


def _shadow_packet() -> dict[str, object]:
    return {"summary": {"no_customer_facing_ranking_change": True}}


def _scorecard(tmp_path: Path) -> None:
    payload = {
        "summary": {"primary_metric_value": 0.82},
        "evaluator": {"metrics": {"ROC_AUC": 0.82}},
    }
    path = tmp_path / "runs" / "suite_replay_scorecard_current.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_public_benchmark_residual_assist_replays_manifest_ready(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(replays_mod, "ROOT", tmp_path)
    _scorecard(tmp_path)

    payload = replays_mod.build_public_benchmark_residual_assist_replays(
        public_benchmark_packet=_public_contract(),
        residual_shadow_packet=_shadow_packet(),
    )

    summary = payload["summary"]
    assert summary["status"] == "public_benchmark_residual_assist_replays_manifest_ready"
    assert summary["ready_suite_count"] == 1
    replay = json.loads((tmp_path / "runs/suite_replay_residual_assist_replay_current.json").read_text(encoding="utf-8"))
    assert replay["summary"]["assist_replay_ready"] is True
    assert replay["summary"]["residual_assist_applied"] is True


def test_public_benchmark_residual_assist_comparisons_use_replay_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(replays_mod, "ROOT", tmp_path)
    monkeypatch.setattr(comparisons_mod, "ROOT", tmp_path)
    _scorecard(tmp_path)
    replays_mod.build_public_benchmark_residual_assist_replays(
        public_benchmark_packet=_public_contract(),
        residual_shadow_packet=_shadow_packet(),
    )

    payload = comparisons_mod.build_public_benchmark_residual_assist_comparisons(
        public_benchmark_packet=_public_contract(),
        gpcr_assist_selection_packet={"summary": {"assist_candidate_ready": True}},
    )

    summary = payload["summary"]
    assert summary["assist_applied_suite_count"] == 1
    assert summary["abstain_noop_suite_count"] == 0
    comparison = json.loads((tmp_path / "runs/suite_replay_residual_assist_comparison_current.json").read_text(encoding="utf-8"))
    assert comparison["summary"]["residual_assist_applied"] is True
    assert comparison["summary"]["assist_route_decision"] == "shadow_identity_replay"
