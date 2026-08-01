# Engine V2 V8 clearance development A/B

## Decision

Do not promote V8. The exact merge-SHA experiment preserved the fixed cohort,
candidate denominator, preparation failure, and the only oracle/Top-1 recovery,
but it did not reduce invalid Top-1 from the V7 baseline. V7 remains the active
Stage 0 refiner. Fresh-128 execution, product promotion, and public claims remain
prohibited.

This is historical contaminated-development evidence only. V8 selection used no
RMSD, PoseBusters result, native-pose outcome, or ranking score.

## Frozen evidence

| Item | Identity |
|---|---|
| V7 source commit | `58b6f5f7e0fc7f2f19c64dee139befc142e05006` |
| V7 run-summary self-hash | `3d1fd6bb6bd24749d9e617bd5f6c49c76389f083175393885b40f10814db03dd` |
| V7 analysis self-hash | `8b4874118d1c8ab4c9302f85c5ea7320bf4bf5d3a8b84ad91644e7ee002e4028` |
| V7 gate-ledger self-hash | `0e6686659b34769ea3cf913332708ae91d0212d9d06cd7387a207be7d311f3b3` |
| V8 source commit | `d6ba3afe9b30bfb35efe2c99c13e4e6df5f6ce27` |
| V8 run-summary self-hash | `df5b2db982afe091107626af142caad5115a32c4e0366832640348973e57212e` |
| V8 analysis self-hash | `cf1bcdac637ce5c33988e5d3f37eccfd6d51182d862501c6fe83492cb78a4947` |
| Combined evidence archive | `.betelgeuze/stage0-development/archives/v7-v8-d6ba3afe-clearance-ab.tar.zst` |
| Archive SHA-256 | `4be857ecb5647634505c5f65450d4b08d85be0830b98857f56649db475920ac3` |
| Member-manifest SHA-256 | `41b5d58c62703148a896d93ae1cfce359a841ef425a78af72e3e77eada2f1886` |
| Bundle-checksum SHA-256 | `0cfeb7993e32ec64b7b01e7746ec5ad4975d03ef4c95ed5db12c31468506de25` |

The archive is mode `0600`, is 558,597 bytes, expands to a 23,941,120-byte
deterministic tar stream, and passed `zstd -t`. It contains both complete run
roots, both Scorer-v1 analyses, the authenticated V7 gate ledger, and the frozen
threshold-evidence input. The archive is local mutable run state and is not a
committed benchmark result.

Separate mode-`0600` member-manifest and bundle-checksum sidecars were added
before expanded-state cleanup. A temporary full extraction passed all 58 member
hashes; the sidecars also passed their bundle checksum.

Both runs used the same ordered cases:
`5SD5_HWI`, `5SIS_JSM`, `6M2B_EZO`, `6M73_FNR`, `6T88_MWQ`,
`6TW5_9M2`, `6TW7_NZB`, `6VTA_AKN`, and `6WTN_RXT`.
The declared all-case budget is 576 slots; the preparation failure contributes
no scored candidates, leaving the predeclared scored denominator of 512.
Independent receipt-level recomputation matched both analysis reports, all 18
engine-to-materialization bindings, source identities, case ordering, and every
metric below without an evidence-integrity discrepancy.

## Acceptance result

| Guard | V7 | V8 | Required | Result |
|---|---:|---:|---:|---|
| Scored candidate denominator | 512 | 512 | exactly 512 | pass |
| Preparation failures | 1/9 | 1/9 | no more than 1/9 | pass |
| Invalid Top-1 | 5/8 | 5/8 | V8 no more than 4/8 | **fail** |
| Proposal-oracle recovery | 1/8 | 1/8 | at least 1/8 | pass |
| `6T88_MWQ` Top-1 recovery and validity | true | true | both true | pass |
| Full Top-1 recovery | 1/8 | 1/8 | preserve baseline | pass |
| Full Top-5 recovery | 1/8 | 1/8 | preserve baseline | pass |

The five invalid Top-1 cases remain `5SD5_HWI`, `5SIS_JSM`, `6M2B_EZO`,
`6TW5_9M2`, and `6TW7_NZB`. Every case retained the same Top-1 proposal index.
The unsupported-large-ring preparation failure `6M73_FNR` was retained in the
all-case denominator and was neither retried nor excluded.

## Geometry and validity observations

V8 selected 28 of the existing 128 source-paired V3 slots. The per-case selected
counts were 2, 1, 0, 0, 5, 5, 5, 2, and 8 in the frozen case order. Exactly those
28 candidates changed coordinates and score; no other candidate changed.

The selected states produced these PoseBusters transitions:

- `minimum_distance_to_protein`: 2 fail-to-pass, 0 pass-to-fail;
- `volume_overlap_with_protein`: 4 fail-to-pass, 0 pass-to-fail;
- `internal_energy`: 2 fail-to-pass, 0 pass-to-fail;
- `internal_steric_clash`: 2 fail-to-pass and 1 pass-to-fail.

Aggregate protein minimum-distance failures decreased from 502 to 500 and
protein volume-overlap failures from 449 to 445. Nevertheless, exact valid
candidates stayed 7/512 across the same three cases. There were zero invalid-to-
valid transitions and zero valid-to-invalid transitions. Strict clearance
improvement alone therefore did not create coverage in any uncovered case.
Total PoseBusters failure labels decreased from 1,573 to 1,564, but this did not
change candidate-level validity.

## Descriptive runtime

The receipt-accounted Engine V2 runtime increased from 205.9990 to 213.9644
seconds: +7.9653 seconds, or 1.0387x (+3.87%). Candidate diagnostic time increased
from 684.6067 to 694.3361 seconds: +9.7294 seconds, or 1.0142x (+1.42%). Their
sum increased from 890.6057 to 908.3005 seconds: +17.6948 seconds, or 1.0199x
(+1.99%). These are single-run descriptive measurements, not a speed claim.

## Stage 0 boundary and next action

The Stage 0 development-ledger builder rejected the V8 receipt policy with
`development_source_receipt_policy_invalid`. That rejection is expected: the
tracked Stage 0 authority binds V7 and must not accept a development experiment
as if it were the frozen active policy. The verifier and ledger allowlist remain
unchanged.

Do not relax the V8 clearance guard or the validity threshold. This narrow
selection-only intervention is closed as insufficient. The subsequent
true-conformer and source-paired torsion-rescue experiments also failed to
broaden recovery; the latter selected zero torsion variants, duplicated parent
coordinates for all 28 rescue outputs, and regressed selection eligibility.
The subsequent
[seven-case uncovered failure atlas](engine_v2_source_paired_failure_atlas.md)
is complete. It records five invalid Top-1 and two valid-but-nonnative cases;
all 22 available uncovered-case torsion variants remained at or above the
absolute window maximum and zero were selected. Current work should first run
the atlas-defined receipt-bound scale-feasibility audit, then define at most one
result-independent, bounded, genuinely coordinate-changing proposal
intervention. Scorer calibration remains premature because proposal-oracle
coverage is still only 1/8 in this fixed slice.
