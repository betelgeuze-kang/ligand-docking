# TASK — Reference docking applicability and abstention

## Goal

Add an identity-bound, failure-inclusive applicability assessment in front of
the explicit-parameter reference docking scorer.

## Scope

- Retain all canonical-input, chemistry, parameter, and execution blockers
  instead of stopping at the first scorer-construction error.
- Classify unsupported metals, receptor cofactors, formal/partial-charge
  failures, parameter coverage, capacity, aromaticity, and declared stereo.
- Permit aromatic/stereo inputs only as incomplete diagnostics; never promote
  them to complete interaction coverage.
- Return either the exact assessment plus a constructed diagnostic scorer, or
  the exact assessment plus an explicit abstention.
- Export and document the claim-closed API.

## Non-goals

- Do not add atom typing, charge generation, parameter assignment, metal
  coordination, aromatic-specific terms, stereo validation, or fitted limits.
- Do not convert execution admission into scientific applicability.
- Do not change the existing scorer constructor or its exception behavior.

## Verification

- Focused unit tests for supported admission and combined metal, cofactor,
  aromatic, stereo, charge, parameter, identity, and capacity failures.
- Focused Ruff/format, compile, architecture, package, and deterministic wheel
  checks.

## Risk Level

R2
