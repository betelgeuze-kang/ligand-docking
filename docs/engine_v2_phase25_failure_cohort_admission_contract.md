# Engine V2 Phase 2.5 failure-cohort admission contract

## Decision

Expansion of the Phase 2.5 uncovered-case atlas is not admitted. The admitted
cohort remains the exact seven proposal-oracle-uncovered cases derived from the
pinned nine-case source-paired historical-development A/B.

The machine-readable source of truth is
[`config/engine_v2_phase25_cohort_admission.json`](../config/engine_v2_phase25_cohort_admission.json).
It binds the ordered rosters and their hashes, evidence identities, expansion
requirements, claim boundary, and local-refinement experiment stop rule. This
document is explanatory and cannot widen or override that policy.

## Evidence classes remain distinct

| Evidence class | Scope | Failure-atlas cohort membership authority |
| --- | --- | --- |
| Failure atlas | 7 proposal-oracle-uncovered cases from the pinned 9-case A/B | Exact current membership only |
| Stage 0 threshold proposal source map | 12 cases / 36 three-engine receipt hashes | None; this is a proposed-threshold evidence map, not a failure roster or execution-threshold freeze |
| V7 narrative remainder | `29 scored - 14 with any exact-valid candidate = 15` | None; no ordered roster or authenticated payload exists |

Threshold membership must not be relabeled as failure-atlas membership. The
narrative remainder must not be combined with or subtracted from either
authenticated cohort to infer case identities.

The 12-case artifact identity is pinned only for this Phase 2.5 cross-check.
Its numeric fields remain named `proposed_threshold`; they are not frozen Stage
0 execution thresholds and grant no execution authority. If those proposal
values are later explicitly reviewed and frozen against the present eight
scored-case denominator, proposal-oracle recovery would require at least `3/8`
and invalid Top-1 would require at most `1/8`. The one-shot local A/B triggers
of `2/8` and `4/8` are experiment Go criteria only and cannot admit Stage 0.
Legacy protocol prose that calls the same JSON a "current machine authority",
and the ledger-builder symbol `_require_frozen_threshold_binding`, refer only
to its pinned artifact identity. They do not override policy schema 1.3.0,
freeze its `proposed_threshold` values, or grant execution-threshold authority.

## Expansion gate

A broader cohort requires one immutable historical-development evidence bundle
that satisfies every structured requirement in the policy:

- exact ordered input and uncovered rosters within the pinned contaminated-300
  registry, with no smoke or fresh-holdout overlap;
- complete execution, implementation, evaluation-pipeline, and environment
  identities;
- failure-complete receipts and the fixed candidate denominator;
- a pinned archive, manifest, checksum, member count, and member digests;
- predeclared deterministic proposal-oracle derivation at `<= 2.0` angstrom;
- ten-category taxonomy reconciliation with unsupported causes left
  `unresolved`;
- historical-development-only, no-execution, no-promotion, and no-claim
  governance.

Receipt hashes without authenticated payloads, or aggregate counts without an
ordered roster, fail closed. A later evidence bundle needs separate review;
this contract itself authorizes no run.

## Local-refinement stop rule

The predeclared clearance rule remains shadow-only until a separately reviewed
activation receipt exists. No V9 or V10 refinement PR is admitted before the
single source-paired nine-case A/B completes. That A/B must retain the 512-slot
denominator, source control, full score-term verification, and all nonregression
guards in the policy. The machine policy pins the exact PR #243 policy SHA,
nine-case archive and ordered roster, seven previously uncovered cases,
`6M73_FNR` preparation failure, and existing `6T88_MWQ` Top-1/Top-5 recovery.
Go requires all invariants, at least one primary gain, and no No-Go trigger. A
No-Go trigger has precedence and closes the local torsion/clearance refinement
epic.

## CI enforcement

Run:

```bash
python3 tools/verify_engine_v2_phase25_cohort_admission.py
```

The verifier checks the policy self-hash, exact seven/nine-case rosters, the
pinned threshold-proposal source-map artifact and contaminated-300 registry
identities, the non-authoritative 15-case remainder, and the frozen A/B stop
rule. The authoritative Engine V2 workflow runs the same verifier and its
focused tests.
