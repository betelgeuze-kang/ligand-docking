# Engine V2 true-conformer development A/B

## Decision

Do not promote the current fixed 64-slot true-conformer profile. After the
source-index, aromatic-representation, and declared-valence compatibility
repairs, the exact post-merge A/B prepared and scored the same 8/9 historical
cases and all 512 candidates in each lane. The comparison is therefore
admissible, but the profile produced no proposal-oracle, Top-1, Top-5, or
previously-uncovered-case recovery gain. Its additional exact-valid and
native-like candidates were confined to `6T88_MWQ`, which V7 already recovered,
while Engine V2 runtime increased by about 60%.

V7 remains the active refiner. Stage 0 admission, fresh-128 execution, product
promotion, and public claims remain prohibited for this profile. This evidence
uses historical contaminated-development cases only; proposal generation did
not consume RMSD, PoseBusters outcomes, ranking outcomes, native-pose feedback,
external structure lookups, or fresh-holdout data.

## Frozen final evidence

| Item | Identity |
|---|---|
| Exact source commit for both lanes | `7cfb0216a1476dfe903bd4b176fa5febe8061d7a` |
| Baseline run-summary self-hash | `a78ce5b4ea1218e761b46b5d317204a368ebe2f34888c7324c6cebc1ffbefce3` |
| Baseline analysis self-hash | `400b9d6da01e93ba80058e80a6cc420259daf1a39de22c754ac351e65d524c49` |
| True-conformer run-summary self-hash | `553191f68d8920995da3758a9fbe70f16fdfc6ec5ddced73ad98bcd62107675b` |
| True-conformer analysis self-hash | `59062ec3f917ff764f3ea676c8eb89fc2fcd91a12a8c0d41b1b816c93e670b3e` |
| A/B report self-hash | `b0f76a233428d5a03038feedd87679992f8a2cf564597e1342373c4c608fe665` |
| Proposal profile | `betelgeuze.engine_v2_historical_development_fixed64_source_paired_true_conformer/1.0.0` |
| Proposal profile SHA-256 | `a684c032dea26d8c1cfe623d7d6cb0b5f29b060b23ad03418d7c2638cbf9acc5` |
| Conformer config SHA-256 | `ec80da0430a70af301feaefe86513fd2639cebdff937ac99553c892c0dd58868` |
| Source-bound ensemble schema | `betelgeuze.engine_v2_source_bound_prepared_conformer_ensemble/1.2.0` |
| Source-bound preparation policy | `betelgeuze.engine_v2_source_bound_deterministic_etkdgv3_energy_rmsd/1.2.0` |
| Source-index mapping schema | `betelgeuze.engine_v2_source_bound_rdkit_source_index_mapping/1.0.0` |
| Combined evidence archive | `.betelgeuze/stage0-development/archives/v7-true-conformer-7cfb0216-ab.tar.zst` |
| Archive SHA-256 | `43868c47ab1914cc9819917b09c04417a0200742028663451a2bc8eb065a5cc4` |
| Member-manifest SHA-256 | `d456320adc553aefda36ab0bd8a5b842e06df12000ca85798f0d44f1d21a2af0` |
| Bundle-checksum SHA-256 | `d57d296870e8cdb0ba163c2a50dd318bd0a8c913803bc87602c1ac1428a92dd7` |

The retained compact analysis-file SHA-256 values are
`34cf9b64c3b2bcc2a939d3e1412ca2a282a1fef3ed31804f2b6315bd96083fae`
for V7 and
`ccb82739355a53d227e739a9c0a01ebf853f94d04a2fc113973106e9a6766b4f`
for the true-conformer lane. The retained A/B report file SHA-256 is
`20f732d5203e1c09273148b26a70aa5e7e136d035ecc5641ec7dbb8fea71e11f`;
these whole-file hashes are distinct from each document's schema-defined
self-hash.

Both lanes used the ordered cases `5SD5_HWI`, `5SIS_JSM`, `6M2B_EZO`,
`6M73_FNR`, `6T88_MWQ`, `6TW5_9M2`, `6TW7_NZB`, `6VTA_AKN`, and
`6WTN_RXT`. Their selection SHA-256 is
`cd2c24c9c7d937865f40352375e8a17c6b83b0b0fab8c134218d2c29537493c1`.
The input archive and source-identifier SHA-256 values are respectively
`495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`
and `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`.

The implementation, evaluation-pipeline, and execution-environment identities
were byte-identical between lanes:

- implementation:
  `6deec6d6dcc1962fe9cce8dfb588846650570427a26bbc733f386c35dacf6812`;
- evaluation pipeline:
  `6402b0e8a3ceb0d5158a9ab33b1a687e528253d53e91fe7e81fd8af9a316223e`;
- execution environment:
  `603ded0fd817d170e2848bc6b6d54841debdeb13a628dea51da505984f988465`.

## Admission and acceptance

| Guard or metric | Baseline V7 | True conformer | Change | Result |
|---|---:|---:|---:|---|
| Scored cases | 8/9 | 8/9 | 0 | pass |
| Preparation failures | 1/9 | 1/9 | 0 | pass |
| Scored candidates | 512 | 512 | 0 | pass |
| Exact-valid candidates | 7 | 8 | +1 | descriptive gain |
| Native-like candidates at 2 A | 4 | 6 | +2 | descriptive gain |
| Proposal-oracle recovery | 1/8 | 1/8 | 0 | preserved, no gain |
| Top-1 recovery | 1/8 | 1/8 | 0 | preserved, no gain |
| Top-5 recovery | 1/8 | 1/8 | 0 | preserved, no gain |
| Cases with a valid Top-1 | 3/8 | 3/8 | 0 | no gain |
| Track-decision sufficiency | true | true | — | comparison admissible |

Both lane-level admission gates pass, so this is a like-for-like geometry
comparison. Promotion still fails because no previously uncovered case gained
an exact-valid candidate and no recovery metric gained breadth. There were no
recovery regressions.

## Findings

The compatibility repair binds every RDKit atom to an explicit source index,
accepts only exact bonds or the narrow source-Kekule-to-RDKit-aromatic
representation equivalence, and verifies the source projection after
sanitization. Declared V2000 valence is accepted only for codes 1 through 14
when it exactly equals the raw bond-order sum. The preparation object also
retains the exact source SDF bytes and re-derives the projection during every
verification, preventing a caller from mutating and merely rehashing a
detached projection.

Source-bound preparation succeeded for 8/9 cases. `6M73_FNR` remained the sole
failure in both lanes: baseline classified the unsupported large ring during
preparation, while the true-conformer evidence failed closed at
`source_bound_conformer_preparation` and the result row recorded
`docking_context_preparation_failed`.

All candidate-count gains occurred in the already recovered `6T88_MWQ` case:
its exact-valid count increased from 4 to 5, native-like count from 4 to 6, and
proposal oracle improved from 1.5761 A to 1.3789 A. Its Top-1 and Top-5
recoveries were unchanged. Among uncovered cases, minimum candidate RMSD
improved for `6M2B_EZO` (3.0490 to 2.6831 A), `6TW5_9M2` (4.2930 to
3.4047 A), and `6VTA_AKN` (4.3947 to 4.0484 A), but none crossed the 2 A
recovery boundary or gained an exact-valid candidate. `5SD5_HWI` changed from
4.2813 to 4.2879 A; `5SIS_JSM`, `6TW7_NZB`, and `6WTN_RXT` were unchanged.

## Descriptive runtime

| Accounted interval | Baseline V7 | True conformer | Change |
|---|---:|---:|---:|
| Engine V2 runtime | 208.0599 s | 332.8229 s | +124.7631 s (+60.0%) |
| Diagnostic evaluation | 684.4314 s | 685.0692 s | +0.6378 s |
| Combined | 892.4913 s | 1,017.8921 s | +125.4008 s (+14.0%) |

The denominator and execution identity are equal, but these are single-run,
historical-development timings. They are descriptive engineering evidence,
not a general performance claim. The extra Engine V2 cost produced no recovery
breadth gain.

## Integrity, archive, and cleanup

All 49 top-level provenance documents, eight nested proposal receipts, and
eight source-bound ensemble receipt domains passed their hash and cross-link
checks. The A/B report self-hash also passed. The deterministic mode-`0600`
archive is 737,275 bytes, expands to a 19,671,040-byte tar stream, and contains
66 regular files plus 15 directories. Its Zstandard integrity check, bundle
checksums, safe member-name/type checks, full temporary extraction, and all 66
member hashes passed.

After the restore check, the two expanded run roots and code caches were
removed, reclaiming 22,690,845 logical bytes. The verified archive and its two
checksum sidecars remain, while the two compact analyses and the A/B report
remain outside the archive for direct inspection. This is local mutable run
state, not a committed benchmark result.

## Initial compatibility attempt

The earlier exact-source attempt at
`3dbe39c786dc00fe149d6f933b4186ab1ced1d89` prepared only `6VTA_AKN`, scored
64 candidates, and was rejected before geometry comparison. Seven cases
exposed the source Kekule/aromatic representation mismatch and one exposed the
declared-valence compatibility boundary. That failed-closed run led to the
source-index and source-byte-bound repairs; it is retained only as diagnostic
history in
`.betelgeuze/stage0-development/archives/v7-true-conformer-3dbe39c7-ab.tar.zst`
with archive SHA-256
`48e8c4e1d2cd47723d1933e5030fb0dd79d11c04eb59c788b5c978bf51fb4110`.

## Next bounded action

Do not freeze or promote this true-conformer profile and do not change the
scorer. Preserve V7 and continue only on historical contaminated development
with a result-independent, hard-capped torsion-rescue variant lane for source
families beyond the current V3-only eligibility, informed by explicit
uncovered-case cause classification. Fresh-128 data remains unopened.
