# CASP17 Win-Tier Goal Addendum

This addendum is the durable goal objective extension for the active CASP17
internal-physics lane. It converts the operator-supplied CASP17 win-tier
criteria into repo-tracked targets, unlock gates, and benchmark bands.
The executable scorecard for this contract is
`runs/casp17_win_tier_goal_scorecard_current.md`.

Status note: CASP17 is still in season as of 2026-05-28. Final CASP17 winner
evidence does not exist yet, so competitive proof must be anchored to
historical CASP15/CASP16 official-like replay, with no current-target leakage.
These thresholds are planning targets and must be checked against official CASP
assessment pages before public claims.

## Active Goal Objective Lock

This file is the repo-tracked extension of the active CASP17 goal. The runtime
goal text remains the same, but CASP17 work is now judged against this contract:

- do not claim CASP17 win-tier performance until no-leak historical replay is
  closed with official-like metrics
- raise scaffold readiness from `65` to `90` by closing target identity,
  provenance, file, sidechain-native, and metric-surface gates
- raise competitive proof from `15-25` to `85-90` by matching normalized
  historical top-band evidence against CASP15/CASP16 references
- prioritize immune/protein complexes, organic ligand-protein complexes, and
  accuracy estimation/model selection before broad monomer-only expansion
- keep every current CASP17 target native-free and leakage-guarded; current
  target folders and object viewers are readiness artifacts, not native
  performance evidence

## Operator Objective Patch 2026-05-28

This section records the active goal extension supplied by the operator. The
goal is not to declare CASP17 performance before assessment exists; the goal is
to raise the lane from a review-quality scaffold into a no-leak, official-like,
category-aware benchmark system that can prove win-tier proximity.

The working target is:

- scaffold readiness: `65 -> 90`
- competitive proof: `15-25 -> 85-90`
- leaderboard interpretation: category `top-5` means competitive, `top-3`
  means winner-proximity, and `top-1/top-2` means actual win-tier

The goal must track these distinctions explicitly:

- scaffold `85-90` means the evidence machinery is closed, not that the model
  performance is already `90`
- performance `90` requires no-leak historical replay, official-like metrics,
  model1 and best-of-5 scoring, top-5 band evidence, and at least one priority
  category near top-3
- active CASP17 targets may be used only for local readiness and visual/object
  organization, never for native lookup or leakage-prone performance claims

## CASP17 Competitive Scope

CASP17 must be treated as more than monomer folding. The priority categories for
this lane are:

- immune and protein complexes
- organic ligand-protein complexes
- nucleic acids and mixed complexes
- conformational ensembles
- difficult protein structures and complexes
- accuracy estimation and model selection

Target naming is interpreted as:

- `T`: monomer or homomer
- `H`: protein heteromer
- `R`: RNA
- `D`: DNA
- `M`: hybrid complex
- `L`: ligand-only

CASP17 calendar anchors:

- target release start: 2026-04-27
- last target release: 2026-07-31
- modeling season end: 2026-08-31
- assessment window: 2026-08 through 2026-10
- result and invitation window: 2026-11 or later

Current-target examples that make the scope concrete include immune/protein
complexes such as astrovirus-antibody entries, Factor XIa antibody complexes,
HCMV gHgLgO-Fab, gp130 antibody complex, and hemagglutinin-antibody targets,
plus RNA/ligand and hybrid targets in the `R`, `M`, and `L` target families.

## Score Objectives

The active goal is not satisfied by artifact readiness alone. The lane must
move both scaffold readiness and competitive proof:

- CASP17 scaffold score: `65 -> 90`
- CASP17 competitive proof score: `15-25 -> 85-90`
- category leaderboard objective: `top-5` is competitive, `top-3` is
  winner-proximity, `top-1/top-2` is actual win-tier

Scaffold `85-90` means the benchmark and evidence machinery is closed. It is
not the same as performance `90`.

Performance `90` requires:

- no target identity leakage
- official-like metrics
- model1 and best-of-5 evaluation
- category-level top-5 historical band or better
- at least one priority category near the top-3 historical band

## Historical Winner Bands

Do not compare raw CASP15 and CASP16 z-score sums directly because the number
and mix of targets differ. Use winner-normalized score, plus the official-like
category cutoff.

CASP15 regular protein domains:

- winner: Yang-Server, 108 domains, SUM Zscore `90.4273`
- top groups: UM-TBM `89.2119`, PEZYFoldings `85.7980`, Yang `83.5439`,
  DFolding `73.3653`
- top-5 band: SUM Zscore `>= 73`
- top-3 band: SUM Zscore `>= 85`
- winner-proximity band: `>= 0.90` winner ratio, about `81`
- actual win-tier target: `85-90+`

CASP16 regular protein domains:

- winner: Yang-Server, 74 domains, SUM Zscore `40.8978`
- top groups: Yang `39.0158`, Yang-Multimer `36.3137`, MULTICOM `33.3714`,
  falcon2 `33.3229`
- top-5 band: SUM Zscore `>= 33.3`
- top-3 band: SUM Zscore `>= 36.3`
- winner-proximity band: `>= 0.90` winner ratio, about `36.8`
- actual win-tier target: `36-41`

CASP16 multimer and complex target band:

- leading reported range: top group about `15.4` z-score, Yang-Multimer about
  `14.5`
- high-quality reported count reference: Yang-Multimer `10/44`, AF3-server
  post-CASP baseline `7/44`
- DockQ acceptable: `>= 0.23`
- DockQ medium: `>= 0.49`
- DockQ high quality: `>= 0.80`

CASP16 ligand target band:

- participant-level mean LDDT-PLI: about `0.69`
- AF3 post-CASP baseline mean LDDT-PLI: about `0.80`
- best observed affinity Kendall tau: about `0.42`
- experiment-noise-aware theoretical maximum: about `0.73`

## Immediate Unlock Work

The current workbench can claim target folders, object folders, viewers, folder
audit, and model review readiness. The competitive floor is still locked. The
first operator action remains `historical_benchmark_inputs`; the first fill
action is replacing placeholder target and benchmark IDs with cleared
historical non-CASP17 protein targets.

Close these gates before claiming scaffold `85-90`:

1. Historical non-CASP17 target identity clearance.
2. Native PDB, prediction PDB, and no-leak provenance.
3. Competitive-floor 15-row batch fully filled.
4. Required files `480/480` present.
5. Sidechain-native benchmark `40/40` pass.
6. Metric surface generated for GDT_TS, lDDT, TM-score, RMSD, GDT_HA,
   MolProbity, DockQ, ICS, IPS, LDDT-PLI, and BiSyRMSD.
7. Normalized winner-ratio comparison against CASP15/CASP16 official top
   groups.

## Category Performance Targets

Prioritize immune/protein complexes, organic ligand-protein complexes, and
accuracy estimation/model selection. Difficult monomer/domain remains important,
but the cost and risk are higher because AF2/AF3/optimized-MSA lanes are very
strong in that regime.

### Difficult Monomer And Domain

Historical replay goal:

- CASP16 domain replay winner-normalized z-score `>= 0.90`
- top-5 cutoff or better
- near-zero catastrophic hard-target misses
- model1 within `5-10%` of best-of-5

Raw metric planning targets:

- easy/medium domains: GDT_TS `85-90`, lDDT `0.80-0.85`, TM-score `0.85-0.90`
- hard or shallow-MSA domains: GDT_TS `65-75`, TM-score `0.70-0.80`
- catastrophic fold miss, for example GDT_TS `< 50`, should be almost absent

### Immune And Protein Complexes

Complex target goals:

- DockQ `>= 0.23` acceptable on `90%+` of targets
- DockQ `>= 0.49` medium on `70-80%` of targets
- DockQ `>= 0.80` high quality on `50-60%+` of general complexes
- DockQ `>= 0.80` high quality on `40-50%+` of hard immune/antibody targets
- model1 selection gap from best-of-5 must remain small

Operational requirements:

- preserve plausible stoichiometry candidates before phase-2 stoichiometry
  release
- rerank quickly after experimental stoichiometry is provided
- avoid repeated cases where best-of-5 contains a near-native model but model1
  selects the wrong interface

### Organic Ligand-Protein Complexes

Pose goals:

- mean LDDT-PLI `>= 0.70` for CASP16 best-participant level
- mean LDDT-PLI `>= 0.80` for AF3 post-CASP baseline level
- BiSyRMSD `<= 2.0 A` hit fraction `>= 60-70%`
- stable holo-like receptor pocket, BB-RMSD, and LDDT-lp around the ligand site

Affinity goals:

- Kendall tau `>= 0.42` for CASP16 best-observed participant level
- Kendall tau `>= 0.55` for strong win-tier candidacy
- Kendall tau `>= 0.65` for very strong performance, with experimental noise
  caveats

### Accuracy Estimation And Model Selection

This is a priority lane because governance, evidence tracking, fingerprinting,
and metric consistency can translate directly into competitive model selection.

Targets:

- top1 selection accuracy from best-of-5 to model1 `>= 70%`
- high correlation between predicted confidence and actual GDT_TS, DockQ, and
  LDDT-PLI
- low high-confidence false-positive rate
- rerank near-native candidates upward from large AF/MassiveFold-style pools
- flag wrong stoichiometry, bad interface, ligand mispose, and hallucinated
  contacts as low confidence

## Source Anchors To Recheck

These links are source anchors for the goal contract and must be rechecked
before any public claim or leaderboard comparison:

- CASP17 scope, categories, registration, and target-suggestion schedule:
  `https://predictioncenter.org/casp17/`
- CASP17 target list and naming convention:
  `https://predictioncenter.org/casp17/targetlist.cgi`
- CASP15 GDT_TS z-score table:
  `https://predictioncenter.org/casp15/zscores_final.cgi`
- CASP16 GDT_TS z-score table:
  `https://predictioncenter.org/casp16/zscores_final.cgi`
- CASP16 multimer z-score table:
  `https://predictioncenter.org/casp16/zscores_multimer.cgi`
- CASP16 ligand pose/affinity assessment paper:
  `https://pmc.ncbi.nlm.nih.gov/articles/PMC12750038/`

## Claim Boundary

This addendum is a goal and benchmark contract. It does not claim CASP17
submission success, native accuracy, or leaderboard standing until the evidence
gates above are closed with no-leak provenance and official-like metrics.
