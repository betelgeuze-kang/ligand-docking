# Engine v2 `0.3.0a1` Authenticated P0 Alpha

## Purpose

`0.3.0a1` integrates the bounded evidence and docking-identity stack into one
auditable release line. It is an internal scientific-engine alpha, not a
validated docking product.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.3.0a1
Python:       >=3.10,<3.13
PyTorch:      2.6.0
Execution:    CPU reference
```

## Release gates

- Python 3.10, 3.11, and 3.12 focused and complete Engine v2 tests;
- source, dependency, environment, candidate, numeric-policy, dtype, and RNG
  identity checks;
- two isolated builds with a byte-identical wheel SHA-256 at one source epoch;
- clean isolated install, `pip check`, and import outside the checkout;
- strict canonical molecular JSON round trips and deep immutability;
- authenticated docking problem and search-space derivation receipts;
- authenticated, capacity-bounded prepared-input steric-field translation plans
  with candidate-level placement receipts and a uniform fallback for unprepared
  input;
- installable RDKit ligand preparation with optional fail-closed OpenFF
  molecule admission, explicit stereo/aromatic/ring records, bounded
  protomer/tautomer diagnostics, and canonical no-overwrite output;
- failure-inclusive PoseBusters cohort preparation and internal diagnostic
  execution, with exact source/artifact/config/runtime bindings, per-case
  deterministic seeds, connectivity-symmetry direct receptor-frame Top-1/Top-K
  RMSD, all-case Wilson intervals, and exact local reexecution;
- source-bound RDKit reconstruction of internal selected poses followed by the
  pinned PoseBusters 0.6.5 `redock` full-report oracle, retaining every report
  value, physical-validity/RMSD flag, failure row, internal/oracle RMSD delta,
  and exact reexecution identity;
- a separate Engine-wheel/source/environment-bound observer that measures one
  exact oracle reexecution with full-chain batch and downstream-oracle-loop
  per-case wall duration plus sampled Linux RSS while preserving all failure
  and abstention rows;
- public evaluator report schema v2 with one mapping for RMSD and validity;
- fatal separation of internal evaluator defects from retained case failures.

## Frozen identity lineage

The P0 molecular-state changes are propagated through explicit supersession,
not silently accepted as the prior evidence contract:

- applicability record `1.2.0`:
  `cfc9d2a5f9ff4ee2539c3e15a8c0519788e26c447a71de4e994c53d4f78760a6`;
- energy/force protocol `1.2.0`:
  `0e34905c635b33b47a26cb459a93840166fc222c663d73af43d40d36814d7ee2`;
- artifact binding `1.2.0`:
  `b3341f3b98e29594cfcd727353553efa466116f275f5250c4ae944d624ef62b0`;
- OpenMM mapping `1.3.0`:
  `4f0163ff1ef9630d2fcac730cacae8ce6237ae0bf0ad53e031b93e17acc5eeda`;
- OpenMM host-review v7:
  `f7b57f08afd44e0ab7848c8ce75b08560d00cf381895aaeaf251e23cd3b81c7a`;
- two-host S0 bundle v6:
  `5eb28543fa9b11ac3559c20c72955c6c9c9adec757869975c71ef0207beee3a4`.

Historical local receipts remain attached to their superseded configurations.
This refreeze adds no production receipt, two-host reproduction, independent
approval, or scientific acceptance.

## Legacy route boundary

The legacy HIP/ROCm product runtime is not an Engine v2 customer route.
`hip_rocm_product_runtime.enabled=false` and
`customer_execution_enabled=false` remain fixed until a frozen CPU reference,
GPU parity evidence, and product qualification exist.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

The preparation adapter is a diagnostic molecular-ingest boundary. It does not
provide calibrated pKa selection, partial charges, OFFXML parameter assignment,
or real-molecule applicability evidence. The cohort chain measures bounded
connectivity-symmetry RMSD and can apply the pinned PoseBusters validity/RMSD
oracle to reconstructed internal poses, but no official full-cohort production
receipt is bundled. A separate companion reports failure-inclusive primary
target/chemistry strata and Wilson intervals, but no training-manifest OOD
audit. Another companion preregisters and exactly compares a putative
second-host oracle/runtime/strata chain, while deliberately withholding an
independent-rerun claim. The external runtime payload must bind a canonical
execution attestation whose host, operator, single-use nonce, and observed UTC
match the work order exactly, but those values remain self-declared: the
upstream receipts are unsigned self-hashes with no physical-host proof and no
nonce single-use registry review. Same-input external-engine
comparisons and independent scientific review remain absent. The runtime
companion supplies local wall-duration and sampled-RSS observations, but not a
kernel-enforced isolated peak, overhead-free timing, full-pipeline per-case
breakdown, operator signature, or physical-host proof.
The steric field uses fixed
uncalibrated radii and omits electrostatics, hydrogen bonding, desolvation,
solvent/cofactor response, and receptor flexibility. Accordingly, the release does not
establish chemical applicability, calibrated pose generation or scoring,
public redocking performance, GPU parity, product qualification, or customer
execution.
