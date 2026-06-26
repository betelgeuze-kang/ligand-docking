"""Benchmark contract schema: enums and typed dicts for benchmark results.

All definitions use only the standard library (enum + typing).
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, TypedDict


class BenchmarkMetric(str, Enum):
    """All recognized metric names across benchmark lanes."""

    # structure_prediction
    tm_score = "tm_score"
    lddt = "lddt"
    dockq = "dockq"
    confidence_calibration = "confidence_calibration"
    ood_abstention = "ood_abstention"

    # docking_pose
    rmsd_top1 = "rmsd_top1"
    rmsd_top5 = "rmsd_top5"
    chemistry_validity = "chemistry_validity"
    posebusters_pass = "posebusters_pass"

    # docking_enrichment
    ef1 = "ef1"
    bedroc = "bedroc"
    pr_auc = "pr_auc"
    spearman = "spearman"
    uncertainty_coverage = "uncertainty_coverage"

    # md
    force_finite_diff = "force_finite_diff"
    invariance = "invariance"
    energy_drift = "energy_drift"
    ensemble = "ensemble"
    reference_trajectory = "reference_trajectory"
    scaling = "scaling"

    # affinity
    rmse = "rmse"
    mae = "mae"
    spearman_affinity = "spearman_affinity"
    bar_mbar_overlap = "bar_mbar_overlap"
    convergence = "convergence"

    # operations
    gpu_e2e = "gpu_e2e"
    reproducibility_hash = "reproducibility_hash"
    throughput_latency = "throughput_latency"
    recovery = "recovery"
    security_tenant = "security_tenant"


class BenchmarkClaimState(str, Enum):
    """Claim promotion states controlling permitted language and actions."""

    blocked = "blocked"
    baseline_only = "baseline_only"
    restricted_local_allowed = "restricted_local_allowed"
    blocked_until_external_validation = "blocked_until_external_validation"
    claim_review_ready = "claim_review_ready"
    promoted = "promoted"


class BenchmarkLane(str, Enum):
    """Benchmark evaluation lanes."""

    structure_prediction = "structure_prediction"
    docking_pose = "docking_pose"
    docking_enrichment = "docking_enrichment"
    md = "md"
    affinity = "affinity"
    operations = "operations"


# Lane-to-metrics mapping for validation and discovery.
LANE_METRICS: Dict[BenchmarkLane, List[BenchmarkMetric]] = {
    BenchmarkLane.structure_prediction: [
        BenchmarkMetric.tm_score,
        BenchmarkMetric.lddt,
        BenchmarkMetric.dockq,
        BenchmarkMetric.confidence_calibration,
        BenchmarkMetric.ood_abstention,
    ],
    BenchmarkLane.docking_pose: [
        BenchmarkMetric.rmsd_top1,
        BenchmarkMetric.rmsd_top5,
        BenchmarkMetric.chemistry_validity,
        BenchmarkMetric.posebusters_pass,
    ],
    BenchmarkLane.docking_enrichment: [
        BenchmarkMetric.ef1,
        BenchmarkMetric.bedroc,
        BenchmarkMetric.pr_auc,
        BenchmarkMetric.spearman,
        BenchmarkMetric.uncertainty_coverage,
    ],
    BenchmarkLane.md: [
        BenchmarkMetric.force_finite_diff,
        BenchmarkMetric.invariance,
        BenchmarkMetric.energy_drift,
        BenchmarkMetric.ensemble,
        BenchmarkMetric.reference_trajectory,
        BenchmarkMetric.scaling,
    ],
    BenchmarkLane.affinity: [
        BenchmarkMetric.rmse,
        BenchmarkMetric.mae,
        BenchmarkMetric.spearman_affinity,
        BenchmarkMetric.bar_mbar_overlap,
        BenchmarkMetric.convergence,
    ],
    BenchmarkLane.operations: [
        BenchmarkMetric.gpu_e2e,
        BenchmarkMetric.reproducibility_hash,
        BenchmarkMetric.throughput_latency,
        BenchmarkMetric.recovery,
        BenchmarkMetric.security_tenant,
    ],
}


class ArtifactHashes(TypedDict):
    """SHA-256 hashes for provenance tracking."""

    result_artifact_sha256: str
    dataset_artifact_sha256: str
    model_artifact_sha256: str


class MetricThreshold(TypedDict):
    """A single metric threshold entry."""

    metric: str
    minimum: float


class DatasetManifestEntry(TypedDict):
    """Dataset manifest record for benchmark datasets."""

    dataset_id: str
    split_policy: str
    row_count: int
    source_hash: str
    source_url_or_path: str
    license: str


class BenchmarkResult(TypedDict):
    """A complete benchmark result record."""

    benchmark_id: str
    claim_scope: str
    dataset_id: str
    metrics: Dict[str, float]
    thresholds: Dict[str, float]
    artifact_hashes: ArtifactHashes
    timestamp: str
    status: str
