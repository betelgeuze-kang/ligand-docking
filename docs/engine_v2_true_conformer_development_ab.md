# Engine V2 true-conformer development A/B

## Decision

Do not promote the current fixed 64-slot true-conformer profile. On the exact
merge SHA, the baseline prepared 8/9 cases while the true-conformer lane
prepared only 1/9. The experiment therefore failed source-compatibility
admission before a cohort-level geometry comparison was possible. V7 remains
the active refiner; Stage 0, fresh execution, product promotion, and public
claims remain prohibited for this profile.

This is historical contaminated-development evidence only. The preparation
diagnostic replay consumed the charged seed artifact and the frozen conformer
config. It did not consume native-pose outcomes, RMSD, PoseBusters results,
ranking scores, external structure lookups, or fresh-holdout data.

## Frozen evidence

| Item | Identity |
|---|---|
| Exact source commit for both lanes | `3dbe39c786dc00fe149d6f933b4186ab1ced1d89` |
| Baseline run-summary self-hash | `fd48e17ba4d8c5814b93119dc138a13990f068742c98c665f96a0e462e68cb97` |
| Baseline analysis self-hash | `ef58efff27f0cb33fa982085370853514c42730812211a3ed916457c0f27c0d2` |
| True-conformer run-summary self-hash | `1c7cd9dc4784bab3058b9364e3d5269cec5a7e2aafdce534cd8865a817ed7787` |
| True-conformer analysis self-hash | `b709c28e89d15a8eb384995fd6c27ff4ddcac9a45cf3d1d1f4d61867d3be5a57` |
| A/B report self-hash | `9bd94393c06afbbe8cc6f7cb4fed8ad4acff251918a1cf6e47dae11b180c1470` |
| Proposal profile | `betelgeuze.engine_v2_historical_development_fixed64_source_paired_true_conformer/1.0.0` |
| Proposal profile SHA-256 | `a684c032dea26d8c1cfe623d7d6cb0b5f29b060b23ad03418d7c2638cbf9acc5` |
| Conformer config SHA-256 | `ec80da0430a70af301feaefe86513fd2639cebdff937ac99553c892c0dd58868` |
| Combined evidence archive | `.betelgeuze/stage0-development/archives/v7-true-conformer-3dbe39c7-ab.tar.zst` |
| Archive SHA-256 | `48e8c4e1d2cd47723d1933e5030fb0dd79d11c04eb59c788b5c978bf51fb4110` |
| Member-manifest SHA-256 | `671147889eb6f2a0df01b4848d09bdb36a79d0d174a21e9c8147a2bd176af155` |
| Bundle-checksum SHA-256 | `1fd04bf7370351682300ddbdc3e05ee726274542c0eb8ec48f265d4297cb06d5` |

Both lanes used the same ordered cases: `5SD5_HWI`, `5SIS_JSM`, `6M2B_EZO`,
`6M73_FNR`, `6T88_MWQ`, `6TW5_9M2`, `6TW7_NZB`, `6VTA_AKN`, and
`6WTN_RXT`. Their ordered selection SHA-256 is
`cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1`.
The input archive and source-identifier hashes were respectively
`495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`
and `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`.

The implementation, evaluation-pipeline, and execution-environment identities
were byte-identical between lanes. All 18 engine receipts, all 18
materialization receipts, both summaries, both analyses, all nine
true-conformer case receipts, and the one prepared nested proposal receipt
passed self-hash verification.

The prepared ensemble document uses its schema-specific receipt domain:
`receipt_sha256` covers the receipt body before the serialization-only
`conformers` rows are appended. Its stored digest,
`3733af7410a553c056068183432128dba2abaf6547b4daa6a91fa1de41b8e472`,
matched that projection; it is not a generic whole-document self-hash.

## Acceptance result

| Guard | Baseline | True conformer | Required | Result |
|---|---:|---:|---:|---|
| Scored cases | 8/9 | 1/9 | at least 8/9 | **fail** |
| Preparation failures | 1/9 | 8/9 | no more than 1/9 | **fail** |
| Scored candidate denominator | 512 | 64 | exactly 512 | **fail** |
| Exact valid candidates | 7 | 2 | descriptive only | not comparable |
| Proposal-oracle recovery | 1/8 | 0/1 | preserve baseline | **fail** |
| Full Top-1 recovery | 1/8 | 0/1 | preserve baseline | **fail** |
| Full Top-5 recovery | 1/8 | 0/1 | preserve baseline | **fail** |
| Analyzer track-decision sufficiency | true | false | true | **fail** |

The true-conformer analyzer result is intentionally insufficient for a track
decision. Aggregate validity and recovery values are recorded for integrity,
not interpreted as a like-for-like performance comparison.

## Source-compatibility finding

Eight case receipts correctly recorded `proposal_evidence_status=not_prepared`
and `proposal_failure_stage=source_bound_conformer_preparation`. A direct replay
with the same charged seed and frozen config classified the failures as:

- seven cases: RDKit sanitization changed the source atom order or topology;
- one case, `6M73_FNR`: the source SDF used unsupported non-default atom fields;
- one case, `6VTA_AKN`: preparation succeeded with eight selected conformers.

The adapter therefore fails closed, as designed, but its current input
compatibility is too narrow for this historical cohort. Relaxing source-order,
topology, stereo, or source-field evidence is not an acceptable shortcut.

## Only common prepared case

`6VTA_AKN` was the only case prepared in both lanes. Both lanes produced 64
successful candidates and two exact-valid candidates. The baseline Top-1 was
proposal 11 at 7.5852 Å; the true-conformer Top-1 was proposal 35 at 8.8616 Å.
Both Top-1 poses were valid, but neither lane recovered within 2 Å and neither
Top-5 recovered. The minimum candidate RMSD changed from 4.3947 Å to 4.0484 Å,
while the minimum valid-candidate RMSD changed from 5.4389 Å to 8.8481 Å.
This single shared case is diagnostic only and cannot support a performance
claim.

## Descriptive runtime

The baseline recorded 204.6712 seconds of Engine V2 runtime and 685.0352
seconds of diagnostic evaluation, totaling 889.7065 seconds. The
true-conformer run recorded 111.3974 and 44.6487 seconds, totaling 156.0461
seconds. These totals are not comparable because eight true-conformer cases
stopped before proposal generation. They must not be interpreted as a speedup.

## Storage and verification

The deterministic archive is mode `0600`, is 311,163 bytes, expands to a
7,598,080-byte tar stream, and contains 59 regular files. `zstd -t`, the bundle
checksum, a temporary full extraction, and all 59 member hashes passed. The
member manifest and bundle checksum are separate mode-`0600` sidecars. The
archive is local mutable run state and is not a committed benchmark result.

After restore verification, the duplicate expanded A/B roots, the superseded
single-V7 archive, and local Python/test/lint caches were removed. This
reclaimed 42,976,565 logical bytes (40.986 MiB) measured immediately before
removal. Both canonical A/B archives and their checksum sidecars, plus the
compact current analyses and A/B report, were retained.

## Next bounded action

Do not change the scorer or consume fresh data. The next proposal-preparation
slice must preserve exact source identity while admitting the observed source
representations:

1. bind an explicit source-index mapping across RDKit sanitization rather than
   requiring sanitization to leave the parsed topology projection unchanged;
2. classify and safely preserve the required V2000 non-default atom fields;
3. add synthetic regression fixtures for both representations without storing
   benchmark structures in the repository;
4. rerun this exact historical nine-case lane before evaluating geometry or
   considering any profile freeze.
