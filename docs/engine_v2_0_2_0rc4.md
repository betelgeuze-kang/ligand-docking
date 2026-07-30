# Engine v2 `0.2.0rc4` Public Redocking Diagnostic-Contract Release Candidate

## Purpose

`0.2.0rc4` freezes the failure-decomposition contract required before the first
298-case blind-holdout run. It retains the fixed 64-candidate Engine V2 search
denominator and binds preparation, charge, H-bond feature, proposal-oracle,
validity, and scoring-regret evidence to fresh execution receipts. It is an
internal diagnostic release candidate, not benchmark validation or a
docking-performance claim.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.2.0rc4
Python:       >=3.10,<3.13
PyTorch:      2.6.0
Execution:    CPU reference
```

## Release gates

- Python 3.10, 3.11, and 3.12 tests;
- Ruff, Pyright, architecture, and legacy-import guards;
- two isolated builds with a byte-identical wheel SHA-256 at the same source
  epoch;
- PEP 561 metadata, clean isolated install, and `pip check`;
- SPDX 2.3 SBOM binding the wheel SHA-256;
- exact same-case seed equality and four frozen input-artifact hashes;
- immutable external-binary and common execution-environment identities;
- typed preparation, search, and incomplete-ranked-pose failure outcomes;
- one sealed 64-slot candidate ledger per Engine V2 case;
- exact score-ranked Top-5 linkage to retained candidate rows;
- complete-denominator diagnostic metrics for preparation, charge, H-bond
  features, search oracle, validity, scoring regret, and frozen
  size/rotor/ring subgroups;
- two observed cases isolated and reverified as engineering smoke;
- the remaining 298 cases kept untouched until this contract is committed,
  reviewed, and green in CI.

## Evidence boundary

The repository contains the runner and verification contracts, but no committed
300-case report or primary-holdout result. All-candidate PoseBusters evaluation
is retained as diagnostic evidence and excluded from the engine runtime
boundary. Local self-hashes detect mutation but are not independent
attestations.

The first 298-case execution is for diagnostic failure decomposition, and its
results must not become a tuning set. Before that first execution, Stage 0 must
freeze numeric acceptance thresholds, paired-baseline CI interpretation,
diagnostic branch rules, source hashes, the exact runtime, artifact retention,
full-suite classification, and independent reviewer/operator attestations.
Threshold provenance must use an exact-contract public development corpus and
Vina/GNINA development-baseline evidence; published literature may justify the
method but cannot substitute for the bound development artifact. The evidence
must exclude the two engineering-smoke cases and the 298 primary cases. An
unfrozen field blocks the holdout runner before it creates or quarantines any
output.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

The engineering-smoke subset and the first diagnostic blind run do not
establish public benchmark performance, scientific validity, product
qualification, or customer readiness.
