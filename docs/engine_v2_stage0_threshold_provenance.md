# Engine V2 Stage 0 threshold-provenance decision

## Decision

Numeric acceptance values now have a local development-evidence proposal, but
Stage 0 remains `UNADMITTED/BLOCKED`. The bound 12-case non-smoke historical
development slice is recorded in
`config/engine_v2_public_redocking_stage0_threshold_evidence.json`; none of the
fresh 128 results were inspected. The proposal is not a public validation claim
and cannot become an admitted freeze while its scientific gates fail.

## What the primary publication supports

The PoseBusters paper defines a 308-complex benchmark and evaluates pose
recovery at RMSD at most 2 Å together with physical validity. It reports that
AutoDock Vina reaches approximately 58% on the difficult PoseBusters Benchmark
set and emphasizes that RMSD-only success can hide physically implausible
poses. The paper also makes its tabulated results available through Zenodo
record 8278563.

Primary sources:

- [PoseBusters paper and benchmark results](https://pubs.rsc.org/en/content/articlehtml/2024/sc/d3sc04185a)
- [PoseBusters paper data record](https://zenodo.org/records/8278563)

This supports retaining separate RMSD, validity-aware recovery, and failure
metrics. It does not justify copying 58% into the Engine V2 acceptance policy:
the repository protocol uses a different selected 300-case cohort, preparation
path, pocket geometry, candidate/search budget, retained Top-5 contract, Vina
invocation, and bootstrap analysis. The paper also compares Vina and Gold, not
the exact GNINA-rescore mode frozen by this repository.

## Required evidence before numeric freeze

| Policy axis | Acceptable pre-holdout basis | Current state |
| --- | --- | --- |
| Preparation/input unsupported ceiling | Separate public development corpus with the exact preparation lane and a frozen applicability taxonomy | Proposed max 0.20; observed 0.167 |
| 64-slot candidate coverage floor | Exact-protocol development execution; measured only after preparation succeeds | Proposed min 0.90; observed 1.0 |
| Proposal-oracle 2 Å floor | Exact 64-candidate diagnostics on a non-smoke, non-holdout development corpus | Proposed min 0.317; observed 0.30; failing |
| Top-1/Top-5 conditional selection-failure ceilings | Same development candidate ledgers used for oracle recovery, with scorer fixed | Proposed max 0.50/0.20; observed 0.667/0.0; Top-1 failing |
| Invalid-pose ceiling | Same-protocol PoseBusters 0.3.1 development evaluation; measured after preparation succeeds | Proposed max 0.20; observed 0.80; failing |
| Case-level failure ceiling | Same environment and exact runner on development cases | Proposed max 0.20; observed 0.167 |
| Vina/GNINA paired margins | Same-case development baseline plus a frozen non-inferiority margin and 95% CI rule | Proposed -0.10 Top-1/Top-5 margins; holdout CI not run |

The complete historical 300-case execution is now development-only and may be
rerun under rc5 to derive exact diagnostic evidence. None of the disjoint fresh
128 cases may be used. A minimum eight-case non-smoke slice can establish the
mechanical Stage 0 gate for internal provisional execution, but is not stable
scientific validation for every subgroup; the full historical 300 remains the
preferred follow-up development corpus. Every threshold row must bind the
evidence file SHA-256, declare its stage-specific denominator, and explicitly
list `fresh_internal_blind_holdout` as an excluded source.

## Legal boundary

The publication and its data-availability statement identify the Zenodo data
record, while the repository protocol declares its source-data license as
CC-BY-4.0. That declaration is not a legal determination. In solo mode the
developer records an explicit license/attribution self-review for internal use;
a qualified external reviewer must still verify the exact record/file license,
GNINA binary/model redistribution conditions, and intended artifact retention
before any public claim or product promotion.
