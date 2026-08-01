# Engine V2 receipt-bound scale-feasibility audit

## Decision

The bounded Phase 2.4 descriptive audit is complete for the exact seven
historical proposal-oracle-uncovered cases. It does not select or change a
rule.

All 22 available torsion variants remain outside the raw V7 `[2.0,4.0)`
receptor-penalty window. Dividing the same objective by an artifact-bound
ligand heavy-atom count moves 7/22 variants into the same numeric interval, but
that interval has not been calibrated or frozen for the normalized objective.
This is scale sensitivity, not evidence that those seven variants should be
selected.

Exact lexicographic `(receptor penalty, internal penalty)` ordering classifies
all 22 available variants as improved. It therefore has no discrimination in
this slice, and it can accept an internal-penalty increase whenever receptor
penalty decreases. The aggregate internal-penalty median rose from 0.3976 to
0.5784 even though all lexicographic tuples improved. No automatic policy
change, threshold relaxation, V7 replacement, or new execution is authorized.

## Evidence identity

| Item | Identity |
|---|---|
| Exact source commit of both input lanes | `754bebb9ddc2fbffdaca5d4143ff515c3b38c032` |
| Verified archive SHA-256 | `8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc` |
| Member-manifest SHA-256 | `7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21` |
| Bundle-checksum SHA-256 | `6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9` |
| Corrected A/B report self-hash | `fb94287855b8843cea7a28bb271018e2444688ff89381ea5a7a6483dd3c49133` |
| Authenticated failure-atlas self-hash | `58528986f293d96a8a4a3971ecc7abab436c7f27e768589cf0c22d8bc970c1d7` |
| Frozen heavy-atom profile manifest SHA-256 | `57e9e27bd3d8a0752b81c0ce326c4f198bcf41b0529fb75dde3afe12fd67453b` |
| Heavy-atom profile binding SHA-256 | `507d5532cfe658aa2befb5b470f9c8d334a0dd917975f944473f6e67e06ed48b` |
| Audit schema | `betelgeuze.engine_v2_receipt_bound_scale_feasibility_audit/1.0.0` |
| Audit self-hash | `181d99ccfc73caff969542e349ed3bd91839518a846a02592814a3136bec1c63` |
| Audit file SHA-256 | `af5a61a18795a3bed65310ad8d6a02cce540fc94d0fb3cf22f58e7af7ba11905` |

The compact local artifact is
`.betelgeuze/stage0-development/receipt-bound-scale-feasibility-audit-754bebb9-v2.json`.
It is mode `0600` and 18,737 bytes. It is mutable diagnostic state, not a
committed benchmark result or scientific claim.

This identity refresh changes only the authenticated upstream failure-atlas
schema/self-hash after its taxonomy contract was made explicit. All scale
counts, distributions, conclusions, and policy boundaries are unchanged.

## Scope and outcome boundary

The exact seven-case cohort was previously selected from historical RMSD and
PoseBusters outcomes by the authenticated failure atlas. This audit recomputes
that outcome-derived cohort boundary from the pinned 59-member archive. Outcome
data is therefore consumed for cohort authentication, but not for the scale
calculation or comparison of candidate rules.

After the cohort is fixed, the scale calculation reads only these
selection-side inputs:

- fixed seven-case membership;
- source-paired allocation and parent lineage;
- torsion evaluated, variant-available, and selected flags;
- binary64 `baseline_v6` and `optimized` receptor/internal objectives;
- the frozen `[2.0,4.0)` V7 window identity;
- frozen heavy-atom counts whose ligand artifact SHA-256 must equal each
  authenticated result/materialization native-artifact hash.

It does not use RMSD, PoseBusters outcomes, ranking scores, scorer-term vectors,
native coordinates, Top-1 identity, or recovery in normalization,
lexicographic comparison, or window counts. Proposal-level coordinates,
fingerprints, movements, and outcome fields are not emitted.

## Scale comparison

The 24 allocated candidates produced 23 evaluations, 22 available variants,
and zero selections.

| Objective | Baseline min / median / max | Optimized min / median / max |
|---|---:|---:|
| Raw receptor penalty | 4.9406 / 152.3584 / 534.2886 | 4.4410 / 91.8689 / 430.6713 |
| Heavy-atom-normalized receptor penalty | 0.1235 / 4.8046 / 18.4237 | 0.1110 / 3.3409 / 16.3260 |
| Raw internal penalty | 0 / 0.3976 / 132.5852 | 0 / 0.5784 / 116.7390 |

Reusing the current numeric bounds only as a descriptive comparison gives:

| Comparison | Inside `[2.0,4.0)` | Outside |
|---|---:|---:|
| Raw optimized receptor penalty | 0 | 22 |
| Heavy-atom-normalized optimized receptor penalty | 7 | 15 |

The normalized 7/22 count is not an acceptance result. The current numbers were
frozen for the raw quartic objective, not for a per-heavy-atom objective.

Exact lexicographic ordering gives 22 improved, zero equal, and zero regressed
variants. That rule is descriptive here and remains unfrozen.

## Availability inventory

| Alternative | Status |
|---|---|
| Ligand heavy-atom normalization | Available; count and ligand artifact hash are both bound |
| Total ligand atom count | Available for inventory only; not substituted for heavy atoms |
| Exact receptor-then-internal lexicographic ordering | Available from canonical binary64 objectives |
| Accepted receptor-pair normalization | Unavailable; count is absent from receipts |
| Clash-atom normalization | Unavailable; count is absent from receipts |
| Maximum local penetration | Unavailable; value is absent from receipts |
| Absolute numeric geometric clearance | Unavailable in the pinned V1 archive; V1.1 instruments future source-paired receipts only |
| Scorer-v1 term normalization | Ineligible; ranking terms are a different objective contract |

No V8 clearance receipt is cross-joined. It belongs to a separate rejected
source/policy lane and cannot be mixed with this source-paired V7 archive.

The source-paired receipt contract now has a forward-only V1.1 telemetry
extension. For each of the at most four fixed rescue targets it records the
minimum ligand-receptor vdW surface gap for the baseline V6 and otherwise
unmaterialized optimized coordinates, the coordinate fingerprints, and the
radii-policy hash. The policy hash must equal the frozen default vdW-contact
policy fingerprint. The value is the minimum of
`distance - ligand_radius - receptor_radius` in angstrom, encoded as canonical
finite binary64 hex. Negative values remain valid penetration measurements.
The measurement runs only after V7 has fixed its selection, is bounded to one
million ligand-receptor pairs per call, and cannot alter allocation, objective,
coordinates, or `[2.0,4.0)` selection. A larger full Cartesian pair count keeps
the V7 result and emits empty telemetry with the authenticated
`full_cartesian_pair_count_exceeds_fixed_bound` reason instead of failing the
candidate.

That extension does not retroactively make clearance available in this audit:
the pinned archive contains V1 receipts. A separate reviewed historical-
development rerun and newly pinned archive are required before clearance can be
compared here.

Live source-paired diagnostics require one uniform V1.1 receipt version per
case. Legacy V1 is accepted only by the exact pinned-archive verification path;
removing V1.1 telemetry fields cannot downgrade a live candidate.

## Reproduction

```bash
python3 tools/build_engine_v2_receipt_bound_scale_feasibility_audit.py \
  --archive .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.tar.zst \
  --members-sha256 .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.members.sha256 \
  --bundle-sha256 .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.bundle.sha256 \
  --report-member .betelgeuze/stage0-development/source-paired-torsion-rescue-754bebb9-ab.json \
  --expected-archive-sha256 8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc \
  --expected-members-sha256 7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21 \
  --expected-bundle-sha256 6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9 \
  --expected-report-sha256 fb94287855b8843cea7a28bb271018e2444688ff89381ea5a7a6483dd3c49133 \
  --output .betelgeuze/stage0-development/receipt-bound-scale-feasibility-audit-754bebb9-v2.json
```

## Next bounded action

The audit narrows the choice but does not make it. The next admissible evidence
step is a separately reviewed historical-development rerun that emits V1.1
telemetry and pins a new authenticated archive. Only after that receipt set is
audited may a later task predeclare one result-independent rule for one
historical-development A/B. That rule must state its numeric tolerance and
decide explicitly whether internal penalty may increase when receptor penalty
decreases. It must remain source-retaining, hard-capped, and genuinely
coordinate-changing.

Do not fit a normalized threshold from these seven cases, reuse `[2.0,4.0)` as
if it were calibrated after normalization, correlate alternatives with RMSD or
PoseBusters outcomes, relax current gates, or open the frozen holdout.
