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

## Current Progress

- The sequence-5 reservation companion now binds a full raw sequence-1-through-4 prefix, a lane-local canonical nonce record, a custodian-signed intent, exact registry/witness authority material, realm-global uniqueness slots, dual commit-attestation signatures, and a strictly newer post-commit status snapshot.
- This closes only the local artifact contract. The signatures do not independently prove external serializable CAS, one-use slot consumption, non-equivocation, epoch continuity, or unique successor enforcement; same-prior-head sibling attestations remain possible and all actual-fact fields remain false.
- A verifier-only same-epoch external registry proof now checks fresh sequence-5 ancestry, a fixed-order chain of exactly three adjacent transaction-tagged sparse-Merkle leaf transitions, separated backend/head-observer signatures, supplied freshly reverified status-lineage-tail denials, exact backend identity, and equality with a caller-supplied expected native checkpoint. It verifies scoped backend-attestation, exact-transition, observer-signature, and caller-expectation-match facts only; it does not authenticate that expectation or prove a globally latest status head. Actual CAS, global one-use consumption, non-equivocation, epoch continuity, status-head CAS, and successor uniqueness remain false. No actual proof, registry, keys, or authenticated head receipt is provisioned.
- A separate verifier-only authenticated head/status receipt boundary snapshots its two nested inputs, reproduces the same raw proof at receipt time and against a strict post-receipt status descendant, verifies a role-separated external Ed25519 receipt over the exact proof/head/status/service/time/challenge projection, and applies the later tail's revocation/supersession rows. It proves bounded receipt authenticity, exact binding, and challenge equality only. Challenge freshness/one-use, global latest, CAS, non-equivocation, later-head consistency, and epoch continuity remain false, and no actual receipt/key/challenge/current-status descendant is provisioned.
- A same-epoch later-head verifier now re-verifies that receipt, checks every adjacent backend-signed checkpoint/state-root transition, verifies the observer over the complete path, and proves the anchor-attested transaction-tagged consumed-leaf encodings remain in the caller-pinned later root. Proof issue cannot predate the receipt, the signed observation is observer countersign completion, and a post-proof status tail is required for denials. Challenge freshness/one-use and actual slot consumption remain false. This is one-fork consistency only; sibling pins can each verify, so external non-equivocation, global latest, and epoch continuity stay false and no actual proof/status is provisioned.
- Next required evidence is fixed-policy witness-quorum non-equivocation, adjacent epoch-transition continuity, and environment/later custody, then an actually provisioned registry proof plus authenticated receipt/later-head proof/current status, 27/59 plus 14-case production receipts, second-host equality, restart/trajectory/external-implementation comparison, and independent human result approval.

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
