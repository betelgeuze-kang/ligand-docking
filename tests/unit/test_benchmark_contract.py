from __future__ import annotations

from betelgeuze_product.benchmark_contract import (
    BENCHMARK_CONTRACT_SCHEMA_VERSION,
    REQUIRED_BENCHMARK_LANES,
    benchmark_contract_packet,
    validate_benchmark_scorecard_contract,
)


def test_benchmark_contract_lists_required_lanes_and_blocks_auto_promotion() -> None:
    packet = benchmark_contract_packet()

    assert packet["schema_version"] == BENCHMARK_CONTRACT_SCHEMA_VERSION
    assert packet["status"] == "product_scientific_benchmark_contract_ready"
    assert packet["lane_count"] == len(REQUIRED_BENCHMARK_LANES)
    assert packet["claim_promotion_allowed"] is False
    assert packet["row_level_evidence_required"] is True
    assert packet["artifact_hash_required"] is True
    assert packet["benchmark_executed"] is False
    lane_ids = {lane["lane_id"] for lane in packet["lanes"]}
    assert "pose_redocking_validity" in lane_ids
    assert "cross_docking_generalization" in lane_ids
    assert "virtual_screening_enrichment" in lane_ids
    assert "affinity_correlation_proxy" in lane_ids


def test_benchmark_contract_requires_row_level_evidence_and_artifact_hashes() -> None:
    packet = benchmark_contract_packet()

    for lane in packet["lanes"]:
        assert lane["row_level_evidence_required"] is True
        assert lane["artifact_hash_required"] is True
        assert lane["promotion_allowed"] is False
        assert lane["required_metrics"]
        assert lane["minimum_thresholds"]


def test_scorecard_contract_blocks_missing_lanes() -> None:
    result = validate_benchmark_scorecard_contract({"rows": []})

    assert result["status"] == "blocked_benchmark_scorecard_contract"
    assert result["review_ready"] is False
    assert "missing_benchmark_lanes" in result["blockers"]
    assert result["claim_promotion_allowed"] is False


def test_scorecard_contract_blocks_missing_metric_hash_and_row_evidence() -> None:
    first_lane = REQUIRED_BENCHMARK_LANES[0]
    result = validate_benchmark_scorecard_contract(
        {
            "rows": [
                {
                    "lane_id": first_lane["lane_id"],
                    "metrics": {first_lane["required_metrics"][0]: 1.0},
                    "artifact_sha256": "",
                    "row_level_evidence_present": False,
                }
            ]
        }
    )

    assert result["review_ready"] is False
    assert "missing_required_metrics" in result["blockers"]
    assert "missing_artifact_hashes" in result["blockers"]
    assert "missing_row_level_evidence" in result["blockers"]


def test_complete_scorecard_shape_is_review_ready_but_not_claim_promoted() -> None:
    rows = []
    for lane in REQUIRED_BENCHMARK_LANES:
        rows.append(
            {
                "lane_id": lane["lane_id"],
                "metrics": {metric: 1.0 for metric in lane["required_metrics"]},
                "artifact_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "row_level_evidence_present": True,
            }
        )

    result = validate_benchmark_scorecard_contract({"rows": rows})

    assert result["status"] == "benchmark_scorecard_contract_review_ready"
    assert result["review_ready"] is True
    assert result["claim_promotion_allowed"] is False
    assert result["blocker_count"] == 0
