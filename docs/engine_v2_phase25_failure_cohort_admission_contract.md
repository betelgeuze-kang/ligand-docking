# Engine V2 Phase 2.5 failure-cohort admission contract

## Decision

Expansion of the Phase 2.5 uncovered-case atlas is not admitted. The only
currently admitted failure cohort is the exact seven-case
proposal-oracle-uncovered subset of the pinned nine-case source-paired A/B
archive:

- `5SD5_HWI`
- `5SIS_JSM`
- `6M2B_EZO`
- `6TW5_9M2`
- `6TW7_NZB`
- `6VTA_AKN`
- `6WTN_RXT`

This contract freezes an evidence boundary. It does not authorize another
historical run, a fresh-128 run, a taxonomy relabel, a refinement or selection
policy change, scorer calibration, promotion, or a scientific or product
claim.

## Current evidence boundary

| Evidence | Authenticated scope | Identity | Admission consequence |
|---|---|---|---|
| Source-paired A/B archive | 9 historical cases; 8 scored | case-ID SHA-256 `cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1`; source commit `754bebb9ddc2fbffdaca5d4143ff515c3b38c032`; archive SHA-256 `8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc` | Admits only the deterministically pinned seven-case uncovered subset above. |
| Failure atlas | 7 proposal-oracle-uncovered cases | schema `betelgeuze.engine_v2_source_paired_failure_atlas/2.1.0`; self-hash `58528986f293d96a8a4a3971ecc7abab436c7f27e768589cf0c22d8bc970c1d7` | Admits the ten-category representation, including unresolved statuses; it does not prove every cause. |
| Stage 0 threshold authority | 12 historical cases represented by 36 three-engine receipt hashes | case-ID SHA-256 `cba8259f2dd99b1b998903f4edffb4696f0bbdcb758f9c4df15573d29db2a621`; evidence self-hash `8f6e548bae67e56dbe05e95ae4ac08f4af5b1eb7b8119adc09cb33e366a36ce3` | Authenticates the tracked threshold source map only. Its receipt payloads are not committed, and the cohort is not an uncovered-case roster. |
| V7 narrative aggregate | 29 scored cases; 14 with any exact-valid candidate | arithmetic remainder `29 - 14 = 15`; no ordered roster, roster hash, or receipt archive | Does not identify 15 cases and is not equivalent to proposal-oracle-uncovered status. |

The threshold cohort contains the nine source-paired IDs plus `7A9E_R4W`,
`7MWU_ZPM`, and `7OSO_0V1`. Those three IDs must not be labeled failures or
added to the atlas from threshold membership alone. Likewise, the narrative
remainder 15 must not be combined with or subtracted from either authenticated
cohort to infer missing IDs.

## Admission requirements for a broader cohort

A broader Phase 2.5 cohort is admitted only when one immutable evidence bundle
satisfies every requirement below:

1. **Exact scope identity.** It records an ordered historical-development input
   roster, an ordered uncovered roster, both counts, and canonical SHA-256
   digests. Both rosters are disjoint from engineering-smoke and fresh-holdout
   identities.
2. **Execution identity.** It binds the exact source commit, algorithm profile,
   runner, candidate, diagnostic, result, refinement-receipt, scorer, pocket,
   charge, and proposal policies used for every case.
3. **Failure-complete receipts.** Every input case has authenticated result and
   diagnostic receipts, input and materialization identities, and the complete
   fixed candidate-slot denominator. Missing, duplicated, cross-wired, or
   mixed-version rows fail closed.
4. **Archive identity.** The archive file, member manifest, bundle checksum,
   member count, and every member digest are pinned and verified before any
   payload is classified.
5. **Deterministic uncovered derivation.** Proposal-oracle recovery is
   recomputed from the authenticated candidate diagnostics with the frozen
   `<= 2.0` angstrom criterion. The uncovered roster is derived from that
   result, not from exact-valid-pose counts, threshold membership, narrative
   arithmetic, or filenames.
6. **Taxonomy reconciliation.** Every admitted uncovered case has all ten
   category keys, one allowed status per category, deterministic zero-inclusive
   roll-ups, and a self-hash. Evidence-unsupported categories remain
   `unresolved`; absence of evidence is not converted into a causal label.
7. **Claim boundary.** The bundle declares historical contaminated development
   only, no fresh execution, no runtime or selection-policy authority, no
   promotion eligibility, and no public or scientific validation claim.

Receipt hashes without their authenticated payloads cannot satisfy items 3–6.
An aggregate count without an ordered roster cannot satisfy item 1. Failure of
any requirement leaves the admitted cohort unchanged at seven cases.

## Permitted next action

A later, separately reviewed historical-development evidence bundle may be
checked against this contract. Until such a bundle exists, implementation work
may improve evidence plumbing or validation, but it must not widen the atlas,
invent case identities, infer causal categories, or open any fresh-holdout
state.
