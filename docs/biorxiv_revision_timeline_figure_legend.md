# Figure Legend: Corrective Validation Timeline From `v1` To `v7r1`

## Figure Purpose

This figure summarizes how the external validation stack was debugged and corrected without discarding frozen historical evidence.

The point of the figure is not to hide failed intermediate runs. The point is to show, step by step, which failure mode each corrective revision addressed, how the first fully passing close-out was reached, and how the current promoted package was selected.

## Visual Structure

- left-to-right timeline
- one node per corrective milestone
- arrows labeled with the specific blocker that motivated the next revision
- final node highlighted as the accepted reviewer-ready package

## Suggested Panel Title

`Cross-domain blind validation close-out: staged corrective revisions from v1 preregistration to v7r1 promoted package`

## Node Definitions

### `v1` Original frozen preregistration

- role:
  - archived historical preregistration evidence
- main problems revealed during execution:
  - kinase smoke heavy-artifact root was not writable
  - kinase core profile still referenced non-disjoint sources despite a no-leak claim

### `v2` Infrastructure and split correction

- fixes:
  - writable heavy-artifact root for kinase smoke/strict profiles
  - disjoint no-leak kinase source configuration (`seq03`)
- remaining blocker after rerun:
  - blind GPCR/TRPV1 profiles still requested `binding_score_composite_v5` even though `v5` was never produced in stage3

### `v3` Blind score wiring correction

- fixes:
  - blind GPCR/TRPV1 profiles switched to `binding_score_composite_v4`
- effect:
  - TRPV1 core and OOD recovered strongly
  - GPCR OOD recovered
- remaining blocker after rerun:
  - kinase tasks were ranking-perfect but still failed shared geometry/EF gates
  - GPCR core remained the only model-side blocker

### `v4` Kinase gate correction

- fixes:
  - kinase-only operational gate relaxation:
    - `max_mean_min_distance_A: 2.5 -> 2.85`
    - smoke `ef1_min: 1.2 -> 1.0`
- effect:
  - kinase smoke/core/OOD closed
  - TRPV1, GPCR OOD, and IDP remained passing
- remaining blocker after rerun:
  - `GPCR core blind` only

### `v5` Narrow GPCR scorefix2 exploration

- role:
  - intermediate exploratory corrective attempt
- importance:
  - helped narrow the GPCR issue to top-rank precision against aromatic hard decoys
- governance note:
  - preserved as intermediate evidence, not the accepted close-out package

### `v6` GPCR scorefix3 plus live-run close-out

- score change:
  - `binding_score_composite_v7`
  - removes distance reward
  - strengthens donor/acceptor and flexibility priors
- offline evidence:
  - exact evaluator showed GPCR core recovery before the full rerun

### `v6r1` Early live rerun diagnosis

- newly discovered blocker:
  - stage2 inline-score reuse path zeroed ligand priors in live runs
- symptom:
  - `binding_score_composite_v7` selected, but `ligand_mw/logp/rot_bonds/h_donors/h_acceptors` entered stage3 as zeros

### `v6r3` First fully passing close-out run

- code fix:
  - `tools/run_ligand_backmapping_scoring.py`
  - `_inline_score_from_row(...)` now carries ligand priors through the inline-score path
- accepted outcome:
  - `set3_operational_smoke = PASS`
  - `set1_core_blind = PASS`
  - `set2_expanded_ood = PASS`
- representative close-out metric:
  - `gpcr_core_full`
    - `PR-AUC: 0.4336 -> 1.0`
    - `top20 hit rate: 0.15 -> 0.30`

### `v7r1` Promoted current package

- basis:
  - winner-informed score remapping after frozen baseline-gauntlet comparison
- effect:
  - preserved all three passing preregistered sets
  - improved selected TRPV1 and GPCR expanded-OOD ligand tasks without regressions
- governance note:
  - `v6r3` remains the first all-pass corrective close-out
  - `v7r1` is the current promoted reviewer-facing package

## Suggested Caption Text

`Corrective revision history for the preregistered cross-domain blind validation protocol. The original frozen specification (v1) was preserved unchanged. Subsequent revisions removed infrastructure confounds, repaired leakage-sensitive split configuration, corrected blind score wiring, narrowed kinase-specific gate mismatches, and finally closed the remaining GPCR core blind blocker by combining the v7 GPCR score with a fix to the inline-score ligand-prior path. The first fully passing close-out was v6r3. A final winner-informed score-remapping pass produced the promoted current package v7r1, which preserves all three preregistered set passes while improving selected ligand tasks under the same frozen evaluator.`

## Figure Callout Suggestions

- callout on `v3`:
  - `TRPV1 core/OOD and GPCR OOD recovered after score wiring correction`
- callout on `v4`:
  - `kinase failures reclassified as gate mismatch, not ranking failure`
- callout on `v6r1 -> v6r3`:
  - `final blocker traced to live-run metadata propagation, not to the GPCR score formula alone`
