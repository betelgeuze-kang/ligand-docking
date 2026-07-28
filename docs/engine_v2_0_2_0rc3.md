# Engine v2 `0.2.0rc3` Public Redocking Evidence-Correctness Release Candidate

## Purpose

`0.2.0rc3` binds the frozen 300-case public redocking work surface to exact
case inputs, seeds, commands, implementation/evaluator/environment identities,
and fresh sealed execution receipts. It is an internal diagnostic release
candidate, not benchmark validation or a docking-performance claim.

## Supported environment

```text
Distribution: betelgeuze-engine-v2
Version:      0.2.0rc3
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
- exact same-case seed equality against the frozen base-plus-index seed;
- four frozen case-input hashes from a verified archive materialization;
- immutable descriptor-based external-binary execution identity;
- boot-ID-dependent timed-cache policy, with row-cache reads disabled;
- typed failure codes and complete failure denominators;
- sealed result rows that bind pose bytes and evaluator outcomes to one fresh
  execution identity;
- two observed cases isolated as engineering smoke and the remaining 298 cases
  reserved as the primary blind holdout.

## Evidence boundary

The repository contains the runner and verification contracts, but no committed
300-case report or primary-holdout result. Local self-hashes detect accidental
or post-construction mutation; they are not signatures or independent
provenance attestations. Numeric acceptance thresholds remain to be frozen in a
separate protocol change before an untouched holdout run.

## Promotion boundary

- `claim_safe=false`
- `scientifically_validated=false`
- `benchmark_validated=false`
- `customer_execution_enabled=false`

The engineering-smoke subset does not establish public benchmark performance,
scientific validity, product qualification, or customer readiness.
