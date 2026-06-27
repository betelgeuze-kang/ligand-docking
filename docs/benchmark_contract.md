# Benchmark Contract

This document defines the formal schema for benchmark results, dataset manifests,
metric enumerations, artifact hashes, and claim states used across the
Betelgeuze product benchmark infrastructure.

## 1. Benchmark Result Schema (JSON)

Each benchmark result record conforms to the following shape:

```json
{
  "benchmark_id": "string (unique identifier for this benchmark run)",
  "claim_scope": "string (which product claim this result supports)",
  "dataset_id": "string (references the dataset manifest entry)",
  "metrics": {
    "<metric_name>": "<float or structured value>"
  },
  "thresholds": {
    "<metric_name>": "<float minimum required value>"
  },
  "artifact_hashes": {
    "result_artifact_sha256": "string (hex SHA-256 of the result artifact)",
    "dataset_artifact_sha256": "string (hex SHA-256 of the dataset artifact)",
    "model_artifact_sha256": "string (hex SHA-256 of the model artifact)"
  },
  "timestamp": "string (ISO 8601 UTC timestamp)",
  "status": "string (one of the claim states below)"
}
```

### Field Descriptions

| Field | Type | Description |
|---|---|---|
| `benchmark_id` | string | Unique identifier for the benchmark run |
| `claim_scope` | string | Product claim scope this result supports |
| `dataset_id` | string | Reference to a dataset manifest entry |
| `metrics` | dict | Observed metric values keyed by metric name |
| `thresholds` | dict | Minimum threshold values keyed by metric name |
| `artifact_hashes` | dict | SHA-256 hashes for provenance (see Section 4) |
| `timestamp` | string | ISO 8601 UTC timestamp of the run |
| `status` | string | Claim state (see Section 5) |

## 2. Dataset Manifest Format

Each dataset used in benchmarking is registered via a manifest entry:

```json
{
  "dataset_id": "string (unique dataset identifier)",
  "split_policy": "string (e.g. time_split, cluster_split, random_split)",
  "row_count": "integer (number of rows/samples in the dataset)",
  "source_hash": "string (hex SHA-256 of the dataset source file)",
  "source_url_or_path": "string (URL or filesystem path to the dataset)",
  "license": "string (SPDX license identifier or description)"
}
```

| Field | Type | Description |
|---|---|---|
| `dataset_id` | string | Unique identifier for the dataset |
| `split_policy` | string | How train/test splits are constructed |
| `row_count` | int | Number of data points |
| `source_hash` | string | SHA-256 of the source data file |
| `source_url_or_path` | string | Location of the dataset |
| `license` | string | License governing the dataset |

## 3. Metric Names and Definitions by Lane

### structure_prediction

| Metric | Description |
|---|---|
| `tm_score` | TM-score for structural alignment |
| `lddt` | Local Distance Difference Test |
| `dockq` | DockQ score for complex quality |
| `confidence_calibration` | Calibration of predicted confidence |
| `ood_abstention` | Out-of-distribution abstention rate |

### docking_pose

| Metric | Description |
|---|---|
| `rmsd_top1` | RMSD of top-1 predicted pose vs crystal |
| `rmsd_top5` | RMSD of best-of-top-5 predicted poses |
| `chemistry_validity` | Fraction of chemically valid poses |
| `posebusters_pass` | PoseBusters validity pass rate |

### docking_enrichment

| Metric | Description |
|---|---|
| `ef1` | Enrichment Factor at 1% |
| `bedroc` | Boltzmann-Enhanced Discrimination of ROC |
| `pr_auc` | Precision-Recall Area Under Curve |
| `spearman` | Spearman rank correlation |
| `uncertainty_coverage` | Uncertainty-aware coverage metric |

### md

| Metric | Description |
|---|---|
| `force_finite_diff` | Force vs finite-difference gradient agreement |
| `invariance` | Rotational/translational invariance check |
| `energy_drift` | Energy conservation drift over trajectory |
| `ensemble` | Ensemble distribution accuracy |
| `reference_trajectory` | Agreement with reference MD trajectory |
| `scaling` | Computational scaling behavior |

### affinity

| Metric | Description |
|---|---|
| `rmse` | Root Mean Square Error of predicted affinities |
| `mae` | Mean Absolute Error |
| `spearman_affinity` | Spearman correlation for affinity ranking |
| `bar_mbar_overlap` | BAR/MBAR phase-space overlap metric |
| `convergence` | Free energy convergence indicator |

### operations

| Metric | Description |
|---|---|
| `gpu_e2e` | GPU end-to-end clean-container benchmark |
| `reproducibility_hash` | Bitwise reproducibility hash check |
| `throughput_latency` | Throughput and latency measurement |
| `recovery` | Recovery from failure/restart behavior |
| `security_tenant` | Security and tenant isolation test |

## 4. Required Artifact Hashes

Every benchmark result must include the following SHA-256 hash fields to
establish provenance and reproducibility:

| Field | Description |
|---|---|
| `result_artifact_sha256` | SHA-256 of the benchmark result artifact file |
| `dataset_artifact_sha256` | SHA-256 of the dataset artifact used |
| `model_artifact_sha256` | SHA-256 of the model checkpoint/artifact used |

These hashes tie each claim to exact, immutable artifacts. Any mismatch
invalidates the result.

## 5. Claim States

Claim states control what language and actions are permitted based on
evidence quality. These match the states defined in
`docs/scientific_benchmark_contract.md`.

| State | Meaning |
|---|---|
| `blocked` | No customer or public claim allowed |
| `baseline_only` | May be described as an internal baseline, not a validated product capability |
| `restricted_local_allowed` | Allowed only inside scoped local pilot language |
| `blocked_until_external_validation` | Requires independent/public/prospective evidence before promotion |
| `claim_review_ready` | Evidence complete enough for human owner review, not automatic promotion |
| `promoted` | Human-approved and backed by row-level evidence |
