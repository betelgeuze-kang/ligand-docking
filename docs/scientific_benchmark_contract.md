# Scientific Benchmark Contract

Status: benchmark and claim-promotion contract
Principle: every promoted claim requires versioned thresholds, row-level evidence, and a fail-closed result.

## Contract Shape

Thresholds should be versioned YAML with:

- `benchmark_id`
- `claim_scope`
- `dataset_split_policy`
- `metrics`
- `minimum_thresholds`
- `row_level_evidence_required`
- `artifact_hash_required`
- `external_state_mutated: false`
- `promotion_allowed`
- `blockers`

Summary-only green is not enough. A scorecard can support operator review, but product or science claim promotion requires row-level evidence tied to exact artifacts, commands, seeds, and hashes.

## Required Lanes

| Lane | Required metrics | Promotion blocker until |
|---|---|---|
| structure prediction | blind split TM-score, lDDT, DockQ for complexes, confidence calibration, OOD abstention | independent blind evidence and calibrated confidence rows exist |
| docking pose | CASF/PDBbind/PoseBusters-style time/cluster split, top-1/top-5 RMSD < 2A, chemistry validity | pose and target rows are complete and leak-checked |
| docking enrichment/ranking | EF1, BEDROC, PR-AUC, Spearman where applicable, uncertainty coverage | public holdout and negative/decoy rows exist |
| MD | force finite-difference, invariance, energy drift, ensemble checks, reference trajectory, scaling | exact topology and reference checks pass |
| affinity/free energy | held-out RMSE/MAE/Spearman, uncertainty coverage, BAR/MBAR overlap, convergence | calibrated Delta G/FEP evidence passes; wetlab claim remains separate |
| operations | clean-container GPU E2E, reproducibility hash, throughput/latency, recovery, security/tenant tests | hosted stack proves durable queue, quota, auth, isolation, and rollback |

## Claim States

| State | Meaning |
|---|---|
| `blocked` | No customer or public claim allowed. |
| `baseline_only` | May be described as an internal baseline, not a validated product capability. |
| `restricted_local_allowed` | Allowed only inside scoped local pilot language. |
| `blocked_until_external_validation` | Requires independent/public/prospective evidence before promotion. |
| `claim_review_ready` | Evidence complete enough for human owner review, not automatic promotion. |
| `promoted` | Human-approved and backed by row-level evidence. |

## Immediate Gate

`config/product_capability_matrix.yaml` is the current local gate. `scripts/verify_product_capability_matrix.py` blocks:

- AlphaFold parity language
- broad platform claims
- calibrated Delta G/FEP claims
- wetlab-hit claims
- scientific-validity green inferred only from accounting green
- execution or external mutation flags in the matrix
