# Engine V2 source-paired torsion-rescue development A/B

## Decision

Do not promote the current source-paired torsion-rescue lane. The exact-main,
same-source A/B prepared and scored the same 8/9 historical cases and all 512
candidates in both lanes. PoseBusters exact validity, native-like coverage, and
all recovery metrics were unchanged, while selection-eligible candidates
regressed from 31 to 30 and native-like selection-eligible candidates regressed
from 3 to 2. Both regressions occurred in `6T88_MWQ`.

All 28 allocated rescue candidates retained their parent coordinates. This
made 28 same-index rescue candidates differ from the baseline V3-refined
candidates across seven cases, but it created no new rescue-vs-parent
coordinate state and did not broaden recovery.

The decision is
`reject_current_lane_parent_coordinates_retained_and_selection_eligibility_regressed`;
the primary blocker is
`zero_torsion_variants_selected_and_all_28_rescue_slots_duplicate_parent_coordinates`.
V7 remains the active refiner. Stage 0 admission, fresh-128 execution, product
promotion, and public claims remain prohibited for this profile.

This evidence uses only the fixed historical contaminated-development slice.
Allocation used the authenticated per-case ligand/receptor structure and rotor
authority as intended, but did not consume RMSD, PoseBusters outcomes,
native-pose feedback, rank, score, case identity, prior outcomes,
cross-case/public-result data, or fresh-holdout data.

## Frozen evidence

| Item | Identity |
|---|---|
| Exact source commit for both lanes | `754bebb9ddc2fbffdaca5d4143ff515c3b38c032` |
| Input archive SHA-256 | `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c` |
| Source-identifier SHA-256 | `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6` |
| Ordered case-selection SHA-256 | `cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1` |
| Implementation SHA-256 | `295ef252343333e474aa70a46de1af3b740c318dbdcba7d873744f1e012d73ed` |
| Evaluation-pipeline SHA-256 | `3137682f5d211748ad0b37991f075898fc705823ae400928883f8d61ca822f5b` |
| Execution-environment SHA-256 | `e6f96f53ec1d0ce83f665f170b27d0727e98455153720c741122584d0cfadb79` |
| Generic interaction-refiner execution-policy config SHA-256 | `5e8b61d242abfe52e04df6de7f56a137b7736150e95d3e6b526e4269eb275337` |
| Rescue proposal profile | `betelgeuze.engine_v2_historical_development_source_paired_torsion_rescue/1.0.0` |
| Rescue proposal profile SHA-256 | `1930119181619f603f563e3e2aabc8b7ae1347b58e2fcf0a657a7b234f8bb8a6` |
| Baseline summary self-hash | `6f766ea21c8b71ea7d5b677cd215b212fa182eca9241df12b5e72bb08e33ec30` |
| Baseline analysis self-hash | `286780019c09397efa50afe7fa675995317d536e6b08caba78bcb96e1bc9ec7d` |
| Rescue summary self-hash | `8b1acfccd1658778cd7e538d6c6225dbcee30564e7265f8bb88145174cc51f3f` |
| Rescue analysis self-hash | `6f124ed76e39e052566ee4ae41469b10f0cddfd02120e4198a9d28b734d6c6a3` |
| A/B report schema | `betelgeuze.engine_v2_source_paired_torsion_rescue_development_ab/1.1.0` |
| A/B report self-hash | `fb94287855b8843cea7a28bb271018e2444688ff89381ea5a7a6483dd3c49133` |

The retained compact analysis-file SHA-256 values are
`0ad894b413c491b05263539d1860165c35caa74a1ee33f8e33bc0ec07acd3479`
for V7 and
`feea9a9042d08afebe39eedd7ec32a0e358c2dae726de0306097ecd020395e51`
for the rescue lane. The retained A/B report file SHA-256 is
`8e85942c882be73d6d7bdccca6854d2a7c6d9246d4b69a0d9d1eac24a999db00`;
these whole-file hashes are distinct from the schema-defined self-hashes.

Both lanes used the ordered cases `5SD5_HWI`, `5SIS_JSM`, `6M2B_EZO`,
`6M73_FNR`, `6T88_MWQ`, `6TW5_9M2`, `6TW7_NZB`, `6VTA_AKN`, and
`6WTN_RXT`.

## Admission and result

| Metric | Baseline V7 | Rescue | Change |
|---|---:|---:|---:|
| Cases / scored cases | 9 / 8 | 9 / 8 | 0 |
| Preparation failures | 1 | 1 | 0 |
| Successful candidates | 512 | 512 | 0 |
| PoseBusters-exact-valid candidates | 7 | 7 | 0 |
| Native-like candidates at 2 A | 4 | 4 | 0 |
| Native-like PoseBusters-exact-valid candidates | 2 | 2 | 0 |
| Selection-eligible candidates | 31 | 30 | -1 |
| Native-like selection-eligible candidates | 3 | 2 | -1 |
| Proposal-oracle recovery | 1/8 | 1/8 | 0 |
| Top-1 recovery | 1/8 | 1/8 | 0 |
| Top-5 recovery | 1/8 | 1/8 | 0 |
| Cases with a valid Top-1 | 3/8 | 3/8 | 0 |
| Cases with an invalid Top-1 | 5/8 | 5/8 | 0 |

The case and candidate denominators, implementation, evaluation pipeline, and
execution environment matched. Both analysis reports contained 512 candidates
and were sufficient for the track decision. Every scored case retained the
same minimum candidate RMSD, Top-1 proposal, Top-1 RMSD, Top-1 PoseBusters
validity, proposal-oracle recovery, Top-1 recovery, and Top-5 recovery. There
were no PoseBusters exact-validity gains or regressions and no recovery gains or
regressions.

At the candidate level, proposal indices 8, 13, 18, and 23 changed coordinate
fingerprint between baseline and rescue in each of `5SD5_HWI`, `5SIS_JSM`,
`6T88_MWQ`, `6TW5_9M2`, `6TW7_NZB`, `6VTA_AKN`, and `6WTN_RXT`: 28
baseline-to-rescue changes total. These changes mean that rescue retained the
authenticated parent where baseline V3 had produced a refined child; they do
not mean rescue selected a new torsion state. `6M2B_EZO` had no such change,
and `6M73_FNR` was not scored.

The sole eligibility regression was proposal 13 in `6T88_MWQ`, which reduced
that case's selection-eligible and native-like selection-eligible counts by one.
Its RMSD changed from 1.6212813 A to 1.5761408 A while eligibility changed from
true to false. Headline native-like, PoseBusters exact-valid, proposal-oracle,
Top-1, and Top-5 outcomes nevertheless remained unchanged.

`6M73_FNR` retained the typed `unsupported_large_ring_system` preparation
failure. The sole proposal-oracle, Top-1, and Top-5 recovery remained
`6T88_MWQ`.

## Allocation and refinement diagnosis

The fixed allocator assigned four existing V3 child/parent pairs in each of
seven prepared rotor-bearing cases: 28 rescue slots in total. `6M2B_EZO` had an
authenticated authority rotor count of zero and received no rescue pair;
`6M73_FNR` did not reach allocation because preparation failed.

Of the 28 rescue candidates, 27 recorded a torsion evaluation and 26 reported
an available torsion variant. Zero variants were selected. All 28 final
coordinate fingerprints matched their retained parents. The rescue diagnostic
partition therefore reports 28/28 parent-coordinate duplicates, with 28
refinement attempts, 28 reduced-penalty outcomes, 0 rotated outcomes, and 28
translated outcomes. Reclassification reduced the ordinary V3 partition from
128 to 100 rows while preserving the 512-candidate denominator.

The rescue partition contains one native-like candidate, but it is a duplicate
of an already generated parent in the already recovered `6T88_MWQ`; it is not
a gain. The partition contains no PoseBusters-exact-valid or selection-eligible
candidate. These facts close the current lane without supporting a change to
V7.

## Descriptive runtime

| Accounted interval | Baseline V7 | Rescue | Observed change |
|---|---:|---:|---:|
| Receipt-accounted Engine V2 | 206.3132 s | 201.3395 s | -4.9737 s (-2.41%) |
| Diagnostic evaluation | 680.7825 s | 676.6548 s | -4.1277 s (-0.61%) |
| Combined accounted | 887.0957 s | 877.9942 s | -9.1015 s (-1.03%) |
| Wall elapsed | 948.1600 s | 938.1800 s | -9.9800 s (-1.05%) |

These are single-run historical-development observations only. They do not
establish a speedup or performance improvement. The rejected lane produced no
recovery or PoseBusters exact-validity gain and introduced the selection-
eligibility regression described above.

## Integrity, archive, and cleanup

The combined local evidence archive is
`.betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.tar.zst`.
It is mode `0600`, is 619,909 bytes, expands to a 20,756,480-byte tar stream,
and has SHA-256
`8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc`.
It contains 59 regular mode-`0600` files and no explicit directory members.

The member-manifest SHA-256 is
`7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21`;
the bundle-checksum sidecar SHA-256 is
`6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9`.
The Zstandard integrity check, bundle checksums, safe member-name/type and mode
checks, full temporary extraction, and all 59 restored member hashes passed.

The two final expanded run roots plus wall-time files measured 20,628,192
logical bytes. Only after restore verification were they removed. The broader
cleanup record, including superseded/debug roots, 12 Python bytecode-cache
directories, and the pytest cache, reclaimed 25,006,421 logical bytes. The two
compact analyses, corrected A/B report, verified archive, member manifest, and
bundle-checksum sidecar remain. All retained objects are local mutable run
state, not committed benchmark or scientific evidence.

## Scientific boundary and next action

The report explicitly retains `scientifically_validated=false`,
`claim_safe=false`, `stage0_eligible=false`,
`fresh_execution_authorized=false`, `public_claim_eligible=false`,
`primary_claim_eligible=false`, and `product_promotion_eligible=false`.
Fresh-128 remains unopened.

The bounded
[seven-case failure atlas](engine_v2_source_paired_failure_atlas.md) is now
complete. It separates five invalid Top-1 cases from two valid-but-nonnative
cases and records placement, refinement displacement, torsion, categorical
clearance, and selection-window evidence. In the uncovered subset, 24 rescue
candidates led to 23 evaluations, 22 available variants, and zero selections;
all 22 available optimized receptor penalties were at or above `4.0`, outside
the absolute `[2.0,4.0)` window. Scale mismatch remains an unconfirmed
hypothesis, not a conclusion.

The receipt-bound Phase 2.4
[scale-feasibility audit](engine_v2_receipt_bound_scale_feasibility_audit.md)
is complete. Heavy-atom normalization moves 7/22 available variants into the
same numeric interval, but that interval is not calibrated for the normalized
objective. Exact lexicographic ordering marks all 22 improved and is not a
bounded selector. Do not change the active policy until one rule is
predeclared. Any later intervention must be result-independent, bounded,
source-retaining, and genuinely coordinate-changing.
Scorer calibration, threshold relaxation, relabeling/filtering, V7 replacement,
and holdout execution remain out of scope.
