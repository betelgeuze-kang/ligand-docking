# TASK-ID: v2-openmm-fixed-born-result-review-binding

## Goal

Bind the exact fixed-Born failure-disposition receipt into the signed OpenMM host review while preserving the rejected endpoint and the S0 8/8 gate.

## Scope

- Refreeze the host result-review contract with conditional failure-disposition inputs.
- Require and freshly verify the exact disposition receipt when native endpoint health is rejected.
- Require no failure-specific receipt when a future native endpoint is accepted.
- Sign disposition receipt/configuration/physics identity, completeness, and classification separately from endpoint acceptance.
- Carry the new host-review contract into S0 without allowing disposition completeness to satisfy its 8/8 admission rule.
- Add revocation/supersession handling for the disposition receipt.

## Likely Files

- `betelgeuze_engine_v2/offline/openmm_reference_result_review.py`
- `betelgeuze_engine_v2/offline/s0_production_evidence_bundle.py`
- focused result-review/S0 contract and runtime tests
- scientific status and roadmap documentation

## Verification

- The actual 6/8 native receipt plus exact disposition produces a signed rejected review with disposition verified and endpoint acceptance false.
- Missing, unexpected, cross-wired, revoked, superseded, or tampered disposition inputs fail closed.
- A rejected host review still cannot enter S0; accepted-host fixtures require the failure-specific path to be not applicable.
- Contract hashes, focused tests, Ruff, architecture, deterministic wheel, and installed contract/CLI checks.

## Stop Conditions

- Do not change endpoint-health thresholds, reinterpret disposition completion as endpoint acceptance, fabricate an accepted native receipt, provision trust material, invent a second host, or promote S0/S1/product claims.

## Risk Level

R3
