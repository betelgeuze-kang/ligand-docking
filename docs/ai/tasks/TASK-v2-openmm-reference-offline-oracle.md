# TASK-ID: v2-openmm-reference-offline-oracle

## Goal

Freeze OpenMM 8.4.0.post2 `Reference` as an offline external implementation receipt for supported S0 energy/force and minimization-trace evaluations.

## Scope

- Deterministically map the 27/59 protocol's 47 pass variants to OpenMM Reference with exact atom order, units, orthorhombic PBC, exclusions, scaled pairs, switching, and five component force groups; retain 12 Engine-contract failure variants as explicit `not_applicable_engine_contract` dispositions.
- Re-evaluate every supported 14-case operational trace coordinate with OpenMM Reference energy/force and record fixed-Born self/pair components separately.
- Use native harmonic bond/angle/periodic torsion where semantics match and frozen CustomForce expressions for screened electrostatics, switched LJ, scaled pairs, ordered-star improper, and fixed-radius Born terms.
- Bind OpenMM name/version/platform, `_openmm` binary, Python wrapper, dependency/environment identity, mapping manifest, exact inputs, outputs, failures, and canonical receipt SHA-256.
- Predefine energy max/RMS `<=1e-10 kcal/mol` and force max/RMS `<=1e-8 kcal/mol/angstrom`; do not substitute OpenMM CPU results or tune after production observations.
- Treat OpenMM native minimization as a separate endpoint benchmark; do not equate its L-BFGS/constraint path with Engine Armijo/Jacobi traces or checkpoint equality.

## Non-goals

- No customer runtime dependency, external fail-closed contract emulation, OpenMM CPU parity claim, production execution, native-trace equivalence, fitting, S1, or product/scientific promotion.

## Likely Files Or Search Targets

- New offline OpenMM mapping/oracle/receipt modules outside the product runtime path
- Frozen energy-force/minimization materializers and focused external-oracle tests
- S0 bundle, capability, roadmap, CI, and dependency identity records

## Verification

- All 47 pass variants and supported trace steps; component/total energy-force, self/pair, unit/order/exclusion/PBC checks; missing variant, mapping, binary/version/platform, atom-order, unit, digest, and failure-disposition tamper tests.
- Ruff, both protocol chains, architecture guard, capability/YAML equality, and `git diff --check`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files, fetch data, install packages, or mutate external state.
- Stop if only a non-Reference platform is available or a mapping changes the frozen Engine protocol.

## Risk Level

R3
