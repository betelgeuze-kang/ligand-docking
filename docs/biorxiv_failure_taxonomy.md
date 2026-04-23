# Failure Taxonomy

## Purpose

This note records the main failure classes that appeared during the corrective validation path and distinguishes model-side failures from infrastructure, governance, and packaging failures.

## Taxonomy

### 1. Infrastructure Failure

- Example:
  - non-writable heavy-artifact roots during early kinase smoke execution
- Interpretation:
  - not evidence of ranking failure
- Corrective pattern:
  - move to writable storage and freeze the heavy-artifact root explicitly

### 2. Split Or Leakage Failure

- Example:
  - early leakage-sensitive kinase split configuration before the disjoint profile close-out
- Interpretation:
  - protocol/setup failure rather than a valid architecture comparison
- Corrective pattern:
  - replace with disjoint/frozen source pools and rerun under a new spec

### 3. Score Wiring Failure

- Example:
  - blind GPCR/TRPV1 profiles requesting score columns that were not actually produced in the live path
- Interpretation:
  - live evaluation path not matching the intended frozen score definition
- Corrective pattern:
  - align profile score columns with generated outputs and preserve the fix in a new rerun spec

### 4. Operational-Gate Mismatch

- Example:
  - kinase failures under otherwise saturated ranking quality
- Interpretation:
  - acceptance thresholds not well matched to the intended domain readout
- Corrective pattern:
  - narrow gate correction without weakening unrelated claim layers

### 5. Live-Run Metadata Propagation Bug

- Example:
  - GPCR inline-score ligand priors missing during the live run, despite the intended `v7` score design
- Interpretation:
  - true model-side correction could not manifest because required ligand priors were not propagated
- Corrective pattern:
  - fix metadata propagation in the live scorer path and rerun the affected claim layer

### 6. Provenance Gap

- Example:
  - remaining IDP synthetic temporal rows without safe construct-matched public anchors
- Interpretation:
  - provenance boundary, not performance failure
- Corrective pattern:
  - keep rows dataset-level and label the residual policy explicitly rather than overclaiming item-level readiness

## Current State

Under the promoted current package:

- infrastructure failures are resolved
- split/leakage failures are resolved in the accepted claim path
- score wiring failures are resolved
- kinase gate mismatch is resolved for the accepted blind/OOD/smoke path
- the GPCR live-run metadata propagation bug is resolved
- the only unresolved temporal rows are policy-coded provenance gaps rather than hidden technical failures
