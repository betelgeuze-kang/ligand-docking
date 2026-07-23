# TASK — Chemistry-aware pose validity

## Goal

Add a fail-closed pose-validity contract that binds element-specific
force-field nonbonded parameters, explicit partial charges, ligand topology
exclusions, and signed ligand strain to one exact docking proposal.

## Scope

- Reuse the reference docking scorer's Lorentz--Berthelot contact and screened
  Coulomb calculations without a second divergent implementation.
- Diagnose receptor--ligand and ligand-internal nonbonded clashes, retaining
  worst pairs and exact parameter/topology identities.
- Separate attractive and repulsive partial-charge interactions.
- Gate signed ligand strain and repulsive Coulomb by explicit caller thresholds.
- Fail closed for unsupported metals/cofactors and incomplete aromatic/stereo
  coverage; retain uncalibrated/public-validation blockers.
- Export the API and document its claim boundary.

## Non-goals

- Do not fit validity thresholds or ranking weights.
- Do not claim aromatic-specific, stereochemical, metal/cofactor, public
  benchmark, or scientific validation coverage.
- Do not replace the legacy geometry-only validity API.

## Verification

- Focused unit tests for element/parameter-dependent contacts, charge sign,
  strain, topology exclusions, exact identities, aromatic/stereo incompleteness,
  and metal/cofactor fail-closed behavior.
- Focused Ruff/format, compile, architecture, package, and diff checks.

## Risk Level

R2
