# TASK-ID: v2-s0-production-evidence-bundle

## Goal

Define a fail-closed S0 evidence bundle that can prove two-host 27/59 and 14-case production results, external implementation comparison, and independent human approval before S1.

## Scope

- Bind exact production receipts for both protocols from two separately attested CPU host instances and reject duplicate-host, protocol, commit, source, dependency, seed, case, or nonce cross-wiring.
- Add the missing 27/59 post-result dispositions or incorporate equivalent full receipt review into the bundle.
- Bind the minimization comparison receipt, all failure rows, checkpoint details, and host-to-host physics projections under predefined exact/tolerance rules.
- Define an offline external-implementation receipt with solver name/version/build/binary/dependency/environment identity, deterministic input mapping, units/atom order/term semantics, energy-force/minimization outputs, and comparison dispositions.
- Require canonical transport, custody hashes, revocation/supersession inputs, four-role separation, and final Ed25519 approval from an independent human reviewer.
- Keep S1 admission false unless every required artifact verifies and the final outcome is accepted.

## Non-goals

- No bundled keys, trust stores, production receipts, external solver runtime dependency, execution, publication, fitting, S1 chemistry validation, or product promotion.

## Likely Files Or Search Targets

- New S0 comparison/bundle modules and tests under `betelgeuze_engine_v2/physics/`
- Existing energy-force/minimization receipt and result-review modules
- Capability, status, roadmap, CI, and public API records

## Verification

- Full valid bundle plus missing/duplicate host, receipt/nonce/source/dependency/seed cross-wire, failure-row omission, external mapping/unit/order tamper, signature, role, revocation, supersession, and S1-gate tests.
- Both protocol chains, Ruff, capability/YAML equality, architecture guard, and `git diff --check`.

## Stop Conditions

- Follow `AGENTS.md`; do not read `.env` files or mutate external state.
- Stop before provisioning keys, running production, selecting a solver result, or promoting S1 without explicit human authority and actual verified artifacts.

## Risk Level

R4
