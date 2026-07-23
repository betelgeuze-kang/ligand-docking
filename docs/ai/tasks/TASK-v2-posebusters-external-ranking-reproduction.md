# TASK — PoseBusters external-ranking reproduction contract

## Goal

Turn the fixed-policy 308-case Vina/GNINA/Smina ranking result into a
preregistered second-host rerun workflow without treating same-host exact
verification as independent evidence.

## Scope

- Bind the baseline ranking-intake, test-partition, evaluation, and exact wheel.
- Preregister distinct baseline host, external host, operator, executor, and
  single-use nonce identities before the external observation time.
- Require the external chain to reuse exact archive/preparation/family inputs
  while producing new engine execution/evaluation evidence roots.
- Compare all 924 engine/case outcomes, every retained failure, pose counts,
  labels, Top-K outcomes, fixed-policy scores, aggregate metrics, and family
  scopes under frozen tolerances.
- Retain external runtime identity and exact source-chain receipts.
- Keep physical-host independence and scientific/product claims closed until
  an out-of-band reviewer approves the rerun.

## Non-goals

- Do not invent an external host or executor identity.
- Do not execute customer-runtime Vina/GNINA/Smina on the baseline host.
- Do not accept a copied baseline receipt as an external rerun.
- Do not fit or select a scorer using PoseBusters labels.

## Likely Files Or Search Targets

- `betelgeuze_engine_v2/benchmark/public_posebusters_external_ranking_reproduction.py`
- benchmark exports, package entry points, CI, unit tests, and evidence docs

## Verification

- Synthetic 308-case two-chain tests, tamper/replay/identity rejection,
  failure-inclusive comparison, exact reconstruction, architecture, and wheel.

## Stop Conditions

- Follow `AGENTS.md`.
- Do not read or print `.env` files.
- Do not mutate external state without explicit human approval.

## Risk Level

R2
