"""Tests for betelgeuze_product.benchmark_schema."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure package root is importable without conftest/install.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from betelgeuze_product.benchmark_schema import (
    ArtifactHashes,
    BenchmarkClaimState,
    BenchmarkLane,
    BenchmarkMetric,
    BenchmarkResult,
    DatasetManifestEntry,
    LANE_METRICS,
    MetricThreshold,
)


# ---------- Enum membership tests ----------


def test_benchmark_metric_has_all_structure_prediction_metrics():
    expected = {"tm_score", "lddt", "dockq", "confidence_calibration", "ood_abstention"}
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_has_all_docking_pose_metrics():
    expected = {"rmsd_top1", "rmsd_top5", "chemistry_validity", "posebusters_pass"}
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_has_all_docking_enrichment_metrics():
    expected = {"ef1", "bedroc", "pr_auc", "spearman", "uncertainty_coverage"}
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_has_all_md_metrics():
    expected = {
        "force_finite_diff",
        "invariance",
        "energy_drift",
        "ensemble",
        "reference_trajectory",
        "scaling",
    }
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_has_all_affinity_metrics():
    expected = {"rmse", "mae", "spearman_affinity", "bar_mbar_overlap", "convergence"}
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_has_all_operations_metrics():
    expected = {
        "gpu_e2e",
        "reproducibility_hash",
        "throughput_latency",
        "recovery",
        "security_tenant",
    }
    actual = {m.value for m in BenchmarkMetric}
    assert expected.issubset(actual)


def test_benchmark_metric_total_count():
    # 5 + 4 + 5 + 6 + 5 + 5 = 30
    assert len(BenchmarkMetric) == 30


def test_benchmark_claim_state_members():
    expected = {
        "blocked",
        "baseline_only",
        "restricted_local_allowed",
        "blocked_until_external_validation",
        "claim_review_ready",
        "promoted",
    }
    actual = {s.value for s in BenchmarkClaimState}
    assert actual == expected


def test_benchmark_lane_members():
    expected = {
        "structure_prediction",
        "docking_pose",
        "docking_enrichment",
        "md",
        "affinity",
        "operations",
    }
    actual = {lane.value for lane in BenchmarkLane}
    assert actual == expected


# ---------- LANE_METRICS consistency tests ----------


def test_lane_metrics_covers_all_lanes():
    assert set(LANE_METRICS.keys()) == set(BenchmarkLane)


def test_lane_metrics_covers_all_metrics():
    all_metrics_in_lanes = set()
    for metrics in LANE_METRICS.values():
        all_metrics_in_lanes.update(metrics)
    assert all_metrics_in_lanes == set(BenchmarkMetric)


def test_lane_metrics_no_duplicates_across_lanes():
    seen: set[BenchmarkMetric] = set()
    for metrics in LANE_METRICS.values():
        for m in metrics:
            assert m not in seen, f"Duplicate metric {m} across lanes"
            seen.add(m)


# ---------- TypedDict instantiation tests ----------


def test_artifact_hashes_instantiation():
    hashes: ArtifactHashes = {
        "result_artifact_sha256": "abc123",
        "dataset_artifact_sha256": "def456",
        "model_artifact_sha256": "789ghi",
    }
    assert hashes["result_artifact_sha256"] == "abc123"
    assert hashes["dataset_artifact_sha256"] == "def456"
    assert hashes["model_artifact_sha256"] == "789ghi"


def test_metric_threshold_instantiation():
    threshold: MetricThreshold = {"metric": "tm_score", "minimum": 0.8}
    assert threshold["metric"] == "tm_score"
    assert threshold["minimum"] == 0.8


def test_dataset_manifest_entry_instantiation():
    entry: DatasetManifestEntry = {
        "dataset_id": "casf2016_time_split",
        "split_policy": "time_split",
        "row_count": 285,
        "source_hash": "a1b2c3d4e5f6",
        "source_url_or_path": "/data/casf2016.tar.gz",
        "license": "CC-BY-4.0",
    }
    assert entry["dataset_id"] == "casf2016_time_split"
    assert entry["row_count"] == 285


def test_benchmark_result_instantiation():
    result: BenchmarkResult = {
        "benchmark_id": "bench-001",
        "claim_scope": "docking_pose_accuracy",
        "dataset_id": "casf2016_time_split",
        "metrics": {"rmsd_top1": 1.5, "rmsd_top5": 1.2},
        "thresholds": {"rmsd_top1": 2.0, "rmsd_top5": 2.0},
        "artifact_hashes": {
            "result_artifact_sha256": "aaa",
            "dataset_artifact_sha256": "bbb",
            "model_artifact_sha256": "ccc",
        },
        "timestamp": "2026-01-15T10:30:00Z",
        "status": "claim_review_ready",
    }
    assert result["benchmark_id"] == "bench-001"
    assert result["status"] == "claim_review_ready"
    assert result["artifact_hashes"]["model_artifact_sha256"] == "ccc"


# ---------- Enum string behavior ----------


def test_metric_enum_is_str():
    assert isinstance(BenchmarkMetric.tm_score, str)
    assert BenchmarkMetric.tm_score == "tm_score"


def test_claim_state_enum_is_str():
    assert isinstance(BenchmarkClaimState.promoted, str)
    assert BenchmarkClaimState.promoted == "promoted"


def test_lane_enum_is_str():
    assert isinstance(BenchmarkLane.md, str)
    assert BenchmarkLane.md == "md"
