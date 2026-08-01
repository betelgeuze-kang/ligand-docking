# Engine V2 source-paired uncovered failure atlas

## Decision

The first bounded Phase 2.5 failure-atlas slice is complete for the seven
scored, proposal-oracle-uncovered cases in the exact historical nine-case
cohort. Five cases have an invalid Top-1 and two have a PoseBusters-exact-valid
but nonnative Top-1. The atlas does not recover a case, change coordinates,
change selection policy, or authorize another execution lane.

The strongest new descriptive signal is that all 22 available torsion variants
in the uncovered subset had an optimized receptor penalty at or above `4.0`;
none entered the absolute `[2.0,4.0)` selection window. This is evidence that
the absolute scale requires a dedicated audit, not proof that scale mismatch is
the root cause. Automatic threshold or policy changes remain forbidden. V7
remains the active refiner, and fresh-128 remains unopened.

This is a seven-case bounded slice of the broader historical failure-taxonomy
work, not a claim that every historical uncovered case has been classified.

## Evidence identity

| Item | Identity |
|---|---|
| Exact source commit of both input lanes | `754bebb9ddc2fbffdaca5d4143ff515c3b38c032` |
| Verified A/B evidence archive SHA-256 | `8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc` |
| Archive member-manifest SHA-256 | `7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21` |
| Archive bundle-checksum SHA-256 | `6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9` |
| Corrected A/B report file SHA-256 | `8e85942c882be73d6d7bdccca6854d2a7c6d9246d4b69a0d9d1eac24a999db00` |
| Corrected A/B report self-hash | `fb94287855b8843cea7a28bb271018e2444688ff89381ea5a7a6483dd3c49133` |
| Atlas schema | `betelgeuze.engine_v2_source_paired_failure_atlas/2.0.0` |
| Atlas self-hash | `6b659616074fee3b00ab89b999ba9459fbe80391ffce12e1510e740b49dcf06b` |
| Atlas file SHA-256 | `8dac00ebba0da5fcba4f30cd6eeb72f3518e0c8ea7bb6cf2dd1352e3fc45b9ca` |

The compact atlas is local mutable state at
`.betelgeuze/stage0-development/source-paired-failure-atlas-754bebb9-v2.json`.
It is mode `0600` and 49,092 bytes. It is not a committed benchmark result or
scientific claim.

## Construction and safety boundary

`tools/build_engine_v2_source_paired_failure_atlas.py` accepts the verified
archive, its member manifest and bundle checksum, and the corrected A/B report
member. The three reviewed bundle identities and exact 59-member count are
pinned. The builder bounds all three input files, decompresses the exact bytes
that were hashed, validates every archive-member hash, and never extracts the
archive to a filesystem directory. It rejects prohibited fresh-128 and
environment-file paths before reading them.

Both nine-receipt lanes are decoded with the production development-result
validator. The builder cross-checks proposal, refinement, ranked-result,
materialization, execution-command, policy, and input-artifact bindings against
the two summaries and compact analyses. It writes an exclusive mode-`0600`
output below `.betelgeuze`.

The authenticated invocation used for the recorded artifact was:

```bash
python3 tools/build_engine_v2_source_paired_failure_atlas.py \
  --archive .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.tar.zst \
  --members-sha256 .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.members.sha256 \
  --bundle-sha256 .betelgeuze/stage0-development/archives/v7-source-paired-torsion-rescue-754bebb9-ab.bundle.sha256 \
  --report-member .betelgeuze/stage0-development/source-paired-torsion-rescue-754bebb9-ab.json \
  --expected-archive-sha256 8bef33eba296989b795a11fd05a7e119124b066d91bec28a8b910d38a083fbcc \
  --expected-members-sha256 7f7f5273362a9457b022bc9b2b95c75625cdd259b1b1685aeb4b57d41d985e21 \
  --expected-bundle-sha256 6ee04e23e01a73bb643bb4d1fde240e06fd2916ea085e3652c11e2428bd432a9 \
  --expected-report-sha256 fb94287855b8843cea7a28bb271018e2444688ff89381ea5a7a6483dd3c49133 \
  --output .betelgeuze/stage0-development/source-paired-failure-atlas-754bebb9-v2.json
```

No fresh-holdout, engineering-smoke, or external/public-result data was opened
or used. The historical A/B outcomes were consumed only inside this diagnostic
boundary.

## Seven-case partition

`R/E/V/S` means allocated rescue candidates, evaluated candidates, available
variants, and selected variants.

| Case | Failure class | Top-1 mode / RMSD Å | Best candidate mode / RMSD Å | Observed Top-1 blocker | R/E/V/S |
|---|---|---:|---:|---|---:|
| `5SD5_HWI` | invalid Top-1 | uniform fallback / 4.5404 | V3 rigid / 4.2813 | protein minimum distance, volume overlap, internal energy | 4/4/3/0 |
| `5SIS_JSM` | invalid Top-1 | V3 rigid / 4.8520 | pocket baseline / 2.7156 | protein minimum distance | 4/4/4/0 |
| `6M2B_EZO` | invalid Top-1 | pocket baseline / 3.0490 | pocket baseline / 3.0490 | protein minimum distance; no authority rotor | 0/0/0/0 |
| `6TW5_9M2` | invalid Top-1 | pocket baseline / 5.5977 | pocket baseline / 4.2930 | protein minimum distance | 4/4/4/0 |
| `6TW7_NZB` | invalid Top-1 | uniform fallback / 6.9877 | uniform fallback / 3.6251 | protein minimum distance | 4/4/4/0 |
| `6VTA_AKN` | valid, nonnative Top-1 | V3 rigid / 7.5852 | uniform fallback / 4.3947 | one rescue evaluation became window-unreachable | 4/3/3/0 |
| `6WTN_RXT` | valid, nonnative Top-1 | V3 rigid / 4.6287 | uniform fallback / 2.8828 | no selected torsion variant | 4/4/4/0 |

The recovered case `6T88_MWQ` and preparation failure `6M73_FNR` are excluded
from this uncovered-case table but remain bound in the fixed nine-case input
identity.

## Scale and motion observations

Across the uncovered subset, torsion rescue allocated 24 candidates, evaluated
23, produced 22 available variants, and selected zero. The selection reasons
were 22 `v6_retained_outside_final_receptor_penalty_window` and two
`v6_baseline_retained_no_torsion_objective_reduction`. The available optimized
receptor-penalty bands were exactly:

- below `2.0`: 0;
- `[2.0,4.0)`: 0;
- at or above `4.0`: 22.

Per-case median source-proposal-to-final translation norms span 1.6532–2.0963
Å. Median accepted axis-angle vector norms are zero in all seven cases. Median
evaluated torsion paths in the six rotor-bearing cases span 0.3436–1.5708
radians. These are receipt-derived refinement displacements; they are not
native-referenced translation or orientation errors.

All 28 allocated candidates in the full scored cohort still duplicated their
retained parent coordinates, and zero torsion variants were selected. The
atlas therefore does not reinterpret baseline-to-rescue coordinate differences
as new conformers.

## Cause taxonomy and limitations

Observed evidence supports these narrow labels:

- receptor minimum-distance failure at Top-1 in all five invalid-Top-1 cases;
- additional volume-overlap and internal-energy failures in `5SD5_HWI`;
- no authority rotor in `6M2B_EZO`;
- valid but nonnative placement in `6VTA_AKN` and `6WTN_RXT`;
- unsuccessful bounded torsion rescue in the six rotor-bearing uncovered cases.

The receipts do not independently identify absence of a good conformer, native-
relative global orientation error, numeric pocket-boundary error, ring-conformer
failure, or physical minimum clearance. PoseBusters check IDs provide
categorical failures but not a numeric clearance, and the receptor penalty is
only an objective proxy. Those categories remain
`unresolved_requires_coordinate_replay` or the more specific unresolved status
recorded per case; they must not be promoted to causal conclusions.

## Next bounded action

Do not widen the torsion lane, relax `[2.0,4.0)`, or calibrate the scorer from
this atlas. The follow-up receipt-bound
[scale-feasibility audit](engine_v2_receipt_bound_scale_feasibility_audit.md)
is complete. It finds 7/22 inside the same numeric interval after heavy-atom
normalization, while exact receptor/internal lexicographic ordering marks all
22 improved. The former is uncalibrated and the latter is non-discriminating;
neither is selected automatically. Accepted-pair, clash-atom,
maximum-penetration, and absolute-clearance alternatives remain unavailable.

One bounded selection rule must be predeclared before a historical-development
A/B. Any later proposal intervention must remain
result-independent, hard-capped, source-retaining, and genuinely coordinate-
changing. Fresh execution, scorer calibration, relabeling/filtering, V7
replacement, product promotion, and public claims remain out of scope.
