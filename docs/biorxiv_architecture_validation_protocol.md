# bioRxiv Architecture Validation Protocol

## Purpose

This protocol freezes a cross-domain validation design for architecture-level performance reporting across four domains:

- `GPCR`
- `Ion channel`
- `Kinase/Protease`
- `IDP`

The goal is to produce a package that is credible enough for preprint-era external review. That means the rules are declared before execution, the data sources are frozen, and smoke-vs-full interpretations are written down explicitly.

## Protocol Freeze

- active rerun spec: `config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json`
- active frozen_at_local: `2026-03-22T00:00:00+09:00`
- archived original spec: `config/external_validation_biorxiv_blind_sets_v1.json`
- archived frozen_at_local: `2026-03-21T03:15:00+09:00`
- current full IDP release baseline:
  - `runs/idp_3bead_release_manifest_current.json`
- current smoke IDP reference:
  - `runs/idp_3bead_release_smoke_current.json`
- current promoted external-validation run:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v7r1`
- current promoted reviewer-ready package:
  - `runs/biorxiv_external_validation_package_current.zip`

## Current Accepted Snapshot

- promoted run tag:
  - `2026-03-22_biorxiv_v7r1`
- accepted package audit:
  - `runs/biorxiv_external_validation_audit_current.json`
  - `pass = true`
- set outcomes:
  - `set3_operational_smoke = PASS`
  - `set1_core_blind = PASS`
  - `set2_expanded_ood = PASS`

This means the current reviewer-facing claim set is no longer a partial or corrective record. It is a completed cross-domain validation package with all three preregistered sets passing under the promoted `v7_bestofgauntlet1` spec. The preceding `v6r3` run remains the first fully passing corrective close-out in the revision trail.

## Why There Is A v2

`v1` is preserved as historical preregistration evidence. We are not overwriting it.

`v2` exists because two confounds were discovered during execution:

1. `kinase_smoke` used a non-writable heavy-artifact root:
   - `/media/betelgeuze/ubuntu-1/md_runs`
2. `kinase_core_full` pointed at `config/ligand_htvs_commercial_validation_no_leak_v2_seq02.json`, which still referenced expanded ligand/reference/meta sources rather than the disjoint sources implied by the no-leak claim.

`v2` fixes those confounds by:

- moving the kinase smoke/strict profiles to a writable heavy-artifact root:
  - `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs`
- introducing `config/ligand_htvs_commercial_validation_no_leak_v2_seq03.json`, which uses:
  - `config/ligand_binding_reference_disjoint_v2.csv`
  - `config/ligand_meta_disjoint_v2.csv`
  - `config/ligand_eval_splits_disjoint_v2.csv`

The important governance rule is that `v1` remains intact and reviewable, while `v2` becomes the explicit corrective rerun spec.

## Why Three Sets

We are separating three kinds of evidence instead of collapsing them into one mixed benchmark.

1. `Core Blind Set`
- main performance claim
- strongest currently frozen blind or release-grade evidence across the four domains

2. `Expanded OOD Set`
- generalization stress set
- same architecture, broader blind ligand spaces, strict external-style kinase/protease profile

3. `Operational Smoke Set`
- fast reproducibility support
- not the main claim set
- used to show that the frozen stack reruns cleanly across the same domain mix

## Governance Rules

### Anti-Leakage

- No target swaps after freeze.
- No ligand/control swaps after freeze.
- No threshold edits after freeze unless they are already documented in the preregistered acceptance policy.
- No IDP candidate-specific truth relabeling. Corrected evaluation must use frozen-label sources from the current release manifest.

### Acceptance Rules

#### Ligand Full Sets

- accept task outcome as reported by the produced stress summary
- do not reinterpret failed full operational gates post hoc

#### Ligand Smoke Set

- `n=64` smoke runs are allowed to fail `stage6_operational_gate` only on `ranking_eval_unique_keys`
- if the following are true:
  - `stage5_ranking_eval.ok = true`
  - `stage45_eval_integrity.ok = true`
  - the only failed stage6 metric is `ranking_eval_unique_keys`
- then the run is accepted as a smoke pass
- raw pass remains preserved as `false`
- acceptance is recorded explicitly in the manifest as a smoke-only override note

#### IDP Full Set

- primary acceptance:
  - `all_fold_pass = true`
  - release regression `pass = true`
- `combined_gate_pass` is reported, but interpreted with branch-conditioned combined metrics already frozen in the current release logic

#### IDP Smoke Set

- use fresh current smoke rerun
- acceptance is based on the smoke summary and regression output

## Primary Readouts by Domain

### GPCR

- blind stress summary
- ranking summaries copied into the set package
- stage5 ranking outputs retained for submission review

### Ion Channel

- same structure as GPCR
- TRPV1 blind and smoke outputs are retained as direct artifacts

### Kinase/Protease

- external-style ligand validation profiles
- strict and core profiles separated between set1 and set2

### IDP

- full release manifest, regression, report, and combined gate artifacts for full sets
- fresh current smoke rerun for the smoke set

## Submission Package Requirements

Each set must publish:

- `manifest.json`
- `manifest.md`
- copied task artifacts inside `files/`
- zipped bundle
- explicit per-task pass fields
- raw return code and log path for each executed task
- acceptance note when smoke override logic is used

## Claim Scope

### Allowed Primary Claims

- architecture-level blind performance on the full cross-domain core set
- generalization behavior on the expanded OOD set
- reproducibility support on the operational smoke set

### Not Allowed as Primary Claims

- smoke-only full-scale performance claims
- post hoc threshold tuning justified by a single candidate result
- wet-lab efficacy claims

## How To Run

Validate spec first:

```bash
python3 tools/run_external_validation_blind_sets.py \
  --set-spec-json config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json \
  --validate-only
```

Direct runner:

```bash
python3 tools/run_external_validation_blind_sets.py \
  --set-spec-json config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json \
  --tag 2026-03-22_biorxiv_v7r1 \
  --sets set3_operational_smoke,set1_core_blind,set2_expanded_ood
```

One-shot runner plus final package build:

```bash
python3 tools/run_biorxiv_external_validation_current.py \
  --set-spec-json config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json \
  --tag 2026-03-22_biorxiv_v7r1 \
  --sets set3_operational_smoke,set1_core_blind,set2_expanded_ood
```

Resume a stale one-shot run:

```bash
python3 tools/resume_biorxiv_external_validation.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-21_biorxiv_v1
```

Write a recovery plan for a stale or partial run:

```bash
python3 tools/recover_biorxiv_external_validation.py \
  --run-root runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-21_biorxiv_v1
```

## Output Layout

- root bundle dir:
  - `runs/external_validation_blind_runs/external_validation_blind_runs_<tag>/`
- wrapper stage logs:
  - `validation_stage.log`
  - `package_stage.log`
- per-set bundle:
  - `set1_core_blind/`
  - `set2_expanded_ood/`
  - `set3_operational_smoke/`
- each set contains copied domain artifacts and a zip file ready for sharing

## Practical Interpretation

This protocol is designed to be conservative and reviewable.

- The full sets carry the main claim.
- The smoke set is explicitly limited to reproducibility support.
- Domain-specific acceptance mismatches are documented instead of hidden.
- Submission artifacts are frozen enough that another reader can inspect exactly what was run and what was accepted.
