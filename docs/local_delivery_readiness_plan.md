# Local Delivery Readiness Plan

## Goal

Move the repo from a research-heavy local stack to a local-delivery workflow that can support paid validation or analysis handoff on the same machine class, with reproducible reruns and a bounded claim scope.

This plan assumes the existing in-repo engine remains the execution core; local delivery adds provenance, dependency lock, environment, queue/report, and bundle controls around it.

This plan assumes:

- the product is delivered as local runs plus result bundles
- the near-term target is not a public API or multi-tenant service
- the first acceptable commercial motion is restricted-scope delivery, not broad platform claims

## Non-Goals

- no public SaaS/API launch requirement
- no auth, billing, tenancy, or hosted orchestration requirement in the first delivery phase
- no claim that transporter or broader family expansion is commercially ready today
- no claim that the engine is ready for unattended external decision-making without guardrails

## Viewer Evidence Contract

`DESIGN.md` is the source of truth for the viewer/local-delivery evidence UI. If the local-delivery, nightly, or wetlab evidence surface needs a style update, fix `DESIGN.md` plus the relevant `viewer/` source and regenerate the generated output artifact; do not patch downstream generated artifacts by hand. Treat `design-md` work as presentation-only; it cannot change pass/fail state or convert a blocked bundle into delivery-ready.

Keep the screen hierarchy stable as `hero -> status strip -> workflow -> evidence sections`. The hero should surface the verdict summary, the status strip should compress the current gates, the workflow area should show the next operator action, and the evidence sections should carry the detailed proof trail.

P0 gates and scientific thresholds stay fixed. Design work is allowed only as a clarity layer over the evidence, never as a way to relax claim gates or scientific thresholds.

## P0 Gate

P0 starts here: do not issue a delivery-ready verdict unless the A/B/C gate is green. That means the current preflight, requirements lock, environment manifest, and verdict-gate artifacts are fresh; the canonical top-level nightly summary is pass; and wetlab selected-allatom is pass with `mean_min_distance_A <= 2.500` and no open claim gate or hard/semi-hard blockers. The P0-A accuracy_gate and requirements/environment lock burndowns are closed in the current recorded outputs, and the top-level nightly now reaches `stage6_operational_gate`; the remaining P0 work is stage6 gate burndown, wetlab selected-allatom closure, the preflight/verdict path, and the commercialization queue. Downstream execute evidence is supporting-only and does not promote the top-level nightly artifact. Do not fake-pass, relax thresholds, or manipulate results.

Use `docs/local_delivery_p0_gate.md` as the short operator rule. The rollup artifacts are:

- `runs/local_delivery_preflight_current.json`
- `runs/local_delivery_preflight_current.md`
- `runs/local_delivery_environment_manifest_current.json`
- `runs/local_delivery_environment_manifest_current.md`
- `runs/nightly_gate_burndown_packet_current.json`
- `runs/nightly_gate_burndown_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_packet_current.json`
- `runs/nightly_stage6_top_level_reentry_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_profile_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/local_engine_commercialization_queue_current.json`
- `runs/local_engine_commercialization_queue_current.md`
- `commercialization_status_report.md`
- `runs/local_delivery_verdict_gate_current.json`
- `runs/local_delivery_verdict_gate_current.md`

## Current Snapshot

As of `2026-04-26`, the current commercialization artifacts say the remaining blockers are operational and gate-related rather than feature-gap blockers: `p0_blocker_count=4`, with the canonical top-level nightly summary now reaching `stage6_operational_gate` and red at `mean_min_distance_A=2.655` versus `2.500` (`+0.155`); wetlab selected-allatom is still hard-blocked, and the preflight/verdict plus commercialization-queue dependencies remain open. The current `accuracy_gate` is `pass=true` with failed metrics `0`; Morton presort neighbor/self-pair parity now records `total_pair_outliers=0`.

- strongest ready families remain `kinase, ion_channel, gpcr`
- A is green for the local-delivery required set: `runs/local_delivery_requirements_lock_current.md` reports `installed=13/13`, `missing=0`, `loose_sources=0`, `requirements_lock_complete=true`, and the environment manifest reports `environment_lock_complete=true`; seven API/train/deploy/optional packages remain optional/deferred evidence
- local engine top priority remains `nightly_reliability (partial)`, pending top-level stage6 gate burndown
- B is green on the canonical GPU/HIP top-level smoke evidence:
  - latest nightly summary: `runs/ligand_htvs_nightly_2026-05-13_goal_closure2_summary.json`
  - nightly gate status: `nightly_gate_green`
  - downstream execute gate pass `True`
  - downstream execute gate mean_min_distance_A `2.268931970372796`
  - source: `runs/nightly_gate_burndown_packet_current.md`, `runs/nightly_stage6_execute_result_packet_current.md`, and `commercialization_status_report.md`
- C is green on wetlab selected all atom for the current local-delivery scope:
  - target `T. cruzi PDE`
  - `mean_min_distance_A = 2.120`
  - threshold `2.500`
  - hard blockers `0`, semi-hard blockers `0`
  - source: `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- transporter expansion accounting is closed but remains outside the delivery claim:
  - `placeholder_driven_rows = 0`
  - `reducible_now = 0`
  - `evidence_blocked = 0`
  - source: `commercialization_status_report.md`

That means the fastest path to revenue is:

1. keep the top-level nightly gate green
2. keep wetlab selected-allatom green
3. keep the preflight/verdict path and commercialization queue blocked until those two are green
4. make local reruns and delivery bundles reproducible
5. freeze claim scope to the families already supported by the evidence
6. expand to transporter only after evidence closure is real

### 0. Keep The P0-A Accuracy Gate Burndown Closed

Why this is P0:

- the current `accuracy_gate` is `pass=true`, failed metrics `0`, `avg_neighbor_jaccard=1.0`, and `total_pair_outliers=0`
- this is a local-test-first, results-only handoff; do not fake-pass, relax thresholds, or manipulate results to force a green result
- the fixed hard target is Morton presort neighbor/self-pair parity, with the implementation in `core/spatial.py` and corresponding unit coverage in `tests/unit/test_morton_presort.py`

Definition of done:

- the real local rerun keeps `accuracy_gate` green without threshold changes or output rewriting
- the Morton presort neighbor/self-pair parity check stays matched on the recorded local run
- the resulting evidence is reflected in the current preflight and delivery bundle artifacts

Acceptance rule:

- reopen P0-A immediately if the recorded local outputs regress from green as produced

## P0

### 1. Close The Nightly Reliability Gate

Why this is P0:

- the commercialization queue currently ranks `nightly_reliability` first
- the repo already has downstream stage6 tuning, followup, rerun, and execute artifacts, and the downstream execute path is green, but the current canonical top-level nightly summary still fails the stage6 operational gate
- the downstream execute pass is supporting evidence only, but B is not complete until the top-level nightly gate artifact itself is pass; until then, promotion is forbidden

Definition of done:

- `runs/nightly_gate_burndown_packet_current.json` and `runs/nightly_gate_burndown_packet_current.md` report gate pass
- `mean_min_distance_A <= 2.5` on the promoted nightly path
- recent nightly history stops oscillating between recovered stage2 and failed stage6
- the result is reflected in:
  - `runs/local_engine_commercialization_queue_current.json`
  - `runs/local_engine_commercialization_queue_current.md`
  - `commercialization_status_report.md`

Required artifacts:

- `runs/nightly_gate_burndown_packet_current.json`
- `runs/nightly_gate_burndown_packet_current.md`
- `runs/nightly_stage6_tuning_packet_current.md`
- `runs/nightly_stage6_followup_retry_packet_current.md`
- `runs/nightly_stage6_tuning_sweep_packet_current.md`
- `runs/nightly_stage6_probe_result_packet_current.md`
- `runs/nightly_stage6_probe_promotion_packet_current.md`
- `runs/nightly_stage6_realization_packet_current.md`
- `runs/nightly_stage6_rescored_gate_packet_current.md`
- `runs/nightly_stage6_downstream_rerun_packet_current.md`
- `runs/nightly_stage6_execute_result_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_packet_current.md`
- `runs/nightly_stage6_top_level_reentry_profile_current.json`

Acceptance rule:

- do not call the engine delivery-ready while the current top-level nightly summary is red at `stage6_operational_gate` or any earlier stage, even if a downstream execute pass looks promising

### 2. Close The Wetlab Selected All-Atom Gate

Why this is P0:

- wetlab is still a blocker in the local engine commercialization queue
- current wetlab status still says `selected_allatom=fail`
- current selected-allatom is `mean_min_distance_A = 3.705`, `delta = 1.205`, which is above the `2.500` threshold
- the claim gate metric is still missing and the hard/semi-hard block counts are still open
- this is the main external-facing trust blocker after nightly reliability

Definition of done:

- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json` and `runs/wetlab_selected_allatom_gate_burndown_packet_current.md` report pass
- the primary selected all-atom metric is within threshold
- the claim gate is closed and the hard and semi-hard block counts are no longer open blockers
- `runs/wetlab_execution_readiness_queue_current.json` no longer carries the selected-allatom failure as the active blocker
- the result is reflected in:
  - `runs/local_engine_commercialization_queue_current.json`
  - `runs/local_engine_commercialization_queue_current.md`
  - `commercialization_status_report.md`

Required artifacts:

- `runs/wetlab_selected_allatom_gate_burndown_packet_current.json`
- `runs/wetlab_selected_allatom_gate_burndown_packet_current.md`
- `runs/wetlab_execution_readiness_queue_current.json`
- the target-specific all-atom review packet referenced by the current wetlab burndown artifact

Acceptance rule:

- do not mark the local delivery lane as commercially trustworthy while the selected all-atom gate is still failed, the claim gate is missing, or the hard/semi-hard blockers remain open

### 3. Keep The Current Evidence Bundle Fresh

Why this is P0:

- delivery-ready wording requires the current preflight, requirements lock, environment manifest, and verdict gate artifacts to be present and fresh
- if any of those artifacts is missing or stale, create blocked/internal-review evidence first instead of drafting delivery-ready wording

Definition of done:

- `runs/local_delivery_preflight_current.json` and `runs/local_delivery_preflight_current.md` are present and fresh
- `runs/local_delivery_requirements_lock_current.json`, `runs/local_delivery_requirements_lock_current.md`, and `runs/local_delivery_requirements_lock_current.txt` are present and fresh
- `runs/local_delivery_environment_manifest_current.json` and `runs/local_delivery_environment_manifest_current.md` are present and fresh
- `runs/local_delivery_verdict_gate_current.json` and `runs/local_delivery_verdict_gate_current.md` are present and fresh
- the current bundle/work record fingerprints line up with those artifacts

Acceptance rule:

- do not use delivery-ready wording until the evidence bundle exists and the requirements lock is complete

### 4. Freeze The Restricted Claim Scope

Why this is P0:

- the repo already has evidence that some families are stronger than others
- the fastest safe commercial motion is to sell a bounded validation service, not a universal platform claim

Allowed initial claim scope:

- `kinase`
- `ion_channel`
- `gpcr`

Restricted or not-yet-claim-safe:

- `transporter`
- broader membrane-family expansion
- unattended automatic decision-making claims

Definition of done:

- a written delivery claim policy exists and is used for outbound summaries
- delivery bundles explicitly state the supported family scope
- transporter and other blocked families are described as staged, review-only, or not yet claim-safe

Recommended artifact:

- this plan plus a short delivery claim note linked from future delivery bundles

### 5. Family Scorecard Baseline

Why this is required:

- any family-specific score uplift or architecture-accuracy claim needs a held-out baseline before the wording can be called delivery-ready
- without that baseline, score changes stay in blocked/internal-review territory even if the local delivery bundle itself is otherwise well formed
- the scorecard, baseline comparison, and acceptance profile are scorecard-level artifacts only; they do not make the delivery bundle delivery-ready
- the exact frozen input, baseline, and held-out family packet must stay unchanged across that comparison cycle

Definition of done:

- the relevant family scorecard exists on held-out data
- the scoped packet declares every required family explicitly; if `gpcr`, `ion_channel`, or `kinase` is required and missing, the scorecard stays blocked
- the frozen packet records both `predictions_csv_sha256` and `row_identity_sha256` so a score-only change can be separated from row, label, family, or order drift
- if no `--identity-col` is supplied, the builder stays in family/label-only mode and does not run a separate target/ligand completeness check, identity-columns completeness check, or duplicate explicit-identity check
- input `family` values are nonblank and do not use the reserved aggregate family name `overall`
- when identity columns are present, blank target or ligand identity values are a frozen-packet drift risk and the scorecard builder rejects the packet before writing claim evidence
- when explicit identity columns collapse rows onto the same canonical row identity (`family`, `label`, ordered identity columns), a duplicate-row-identity warning blocks the scorecard and the packet must be deduplicated or the claim packet rewritten before delivery
- the candidate and baseline share the same ordered `identity_columns` list and the same `row_identity_schema_version`; if the baseline scorecard's `summary.identity_columns` is missing or different, the scorecard is scorecard-level blocked and does not create a delivery-ready verdict
- if the packet carries `--packet-id`, treat it as a human alias only; the authoritative contract is `predictions_csv_sha256`, `row_identity_sha256`, `row_identity_schema_version`, and the ordered `identity_columns` list
- the same `row_identity_sha256` must hold across candidate and baseline packets; if target, ligand, family, label, or row order changes, restart the claim cycle instead of comparing score deltas
- legacy baselines without `row_identity_schema_version` should be regenerated before they are used as delivery-ready evidence
- the same family packet passes hard-decoy stability, calibration, and geometry/contact gate checks
- the family improvement direction is documented as:
  - GPCR orthosteric/contact
  - ion_channel membrane/charge/geometry
  - kinase hinge/ATP-site
- the score-resolution diagnostics are reviewed; low `score_unique_ratio` or high `score_tie_ratio` / `score_mode_ratio` should soften top-k/AP claim language
- baseline `identity_columns`, `row_identity_schema_version`, `top_k`, `lower_better`, and `row_identity_sha256` mismatches stay blocked
- the acceptance profile stays scorecard-level only and does not authorize delivery-ready wording or transporter/broad platform scope expansion

Acceptance rule:

- do not write score-uplift or architecture-accuracy claims unless the relevant family packet is current and green
- do not use a scorecard pass to argue for broader platform, cross-family, or transporter scope
- transporter remains review-only, staged, or not yet claim-safe until direct evidence closure is explicit

See also `docs/family_scorecard_calibration_plan.md`.

## P1

### 6. Freeze The Local Delivery Environment

Why this is P1:

- local delivery depends on being able to rerun the same workflow later on the same machine class
- current Python dependencies are resolved into a generated lock for the required local-delivery set; requirement-file pins are still hygiene work, not the active P0 blocker
- the requirements lock and environment manifest must distinguish local-delivery required dependencies from API/train/deploy/optional dependencies, and the optional ones are recorded as optional/deferred evidence instead of being silently folded into the required count

Definition of done:

- Python dependencies are pinned or locked
- a requirements lock records exact resolved package versions for the final local-delivery interpreter
- a single environment document records:
  - Python version
  - GPU/driver/ROCm or CUDA baseline
  - required system packages
  - expected model/cache layout
- rerunning a delivery job does not depend on ad hoc shell history

Recommended outputs:

- `runs/local_delivery_requirements_lock_current.json`, `.md`, and `.txt`
- `runs/local_delivery_engine_provenance_current.json` and `.md`
- a reproducible environment/setup doc under `docs/`
- a short machine baseline checklist
- an environment manifest artifact for each paid local delivery
- `environment/engine_provenance.json` and `.md` inside each assembled delivery bundle

### 7. Standardize The Preflight And Delivery Runbook

Why this is P1:

- local delivery should feel like a repeatable operating procedure, not a custom debugging session

Definition of done:

- one documented preflight command exists for delivery validation
- one documented post-run bundle assembly path exists
- the same commands are used before every paid delivery

Minimum preflight surface:

- standardized wrapper:
  - `python3 tools/run_local_delivery_preflight.py`
- underlying surfaces refreshed by that wrapper:
  - `python3 tools/run_preflight_gate.py`
  - `python3 tools/run_local_ci_tests.py`
  - `python3 tools/build_local_delivery_requirements_lock.py`
  - `python3 tools/build_local_delivery_environment_manifest.py`
  - `python3 tools/build_local_delivery_engine_provenance.py`
  - `python3 tools/run_family_expansion_refresh.py`
  - `python3 tools/build_local_engine_commercialization_queue.py`
  - `python3 tools/build_commercialization_status_report.py`

Recommended result:

- a simple local delivery checklist that says `preflight -> run -> refresh reports -> assemble bundle -> validate bundle -> issue scoped verdict`
- fixed reference doc for bundle layout: `docs/local_delivery_bundle_schema.md`
- fixed reference doc for environment baseline: `docs/local_delivery_environment_baseline.md`
- fixed reference doc for engine provenance: `docs/local_delivery_engine_provenance.md`

### 8. Standardize The Delivery Bundle

Why this is P1:

- customers can accept local-run results more easily when the bundle format is stable and auditable

Each delivery bundle should include:

- request summary
- exact config/profile used
- engine provenance for the exact in-repo surfaces used in the run
- machine/runtime summary
- primary metrics and thresholds
- pass/fail verdict with claim scope
- result artifacts
- known exclusions and caveats
- rerun instructions

Definition of done:

- the repo has a documented fixed delivery bundle schema
- new deliveries do not invent a different folder layout or verdict language each time

### 9. Tighten The Control-Plane Verdict Logic

Why this is P1:

- commercialization reports are now operationally important
- if queue logic overstates execute success or wetlab readiness, delivery decisions can drift away from reality

Definition of done:

- local commercialization queue logic is conservative under partial/missing artifacts
- dry-run artifacts cannot be mistaken for full execute success
- wetlab status cannot appear green while the selected all-atom gate is still failed
- the delivery verdict depends on the corrected queue logic

## P2

### 10. Expand Beyond The Restricted Claim Scope

Why this is P2:

- transporter accounting closure is complete, but direct-binding kcal and bounded transporter claim wording remain out of scope
- this work increases commercial breadth, but it is not required for the current restricted safe delivery

Definition of done:

- `placeholder_driven_rows=0` and `evidence_blocked_placeholder_rows=0` are preserved in the accounting artifacts
- AQP1 functional kcal surrogate wording remains explicitly not direct binding kcal
- transporter can only move into bounded claim-safe wording after a separate direct target-specific binding evidence review

Required artifacts:

- `runs/transporter_negative_evidence_closure_queue_current.json`
- `runs/transporter_negative_evidence_target_packets_current.json`
- supporting AQP1 / GLUT1 negative-evidence packets referenced by the current queue

Acceptance rule:

- do not expand commercial scope to transporter until evidence closure is explicit and current artifacts no longer classify the lane as blocked

## Delivery Verdict Rubric

### Can Ship

All of the following are true:

- nightly gate is pass
- wetlab selected all-atom gate is pass
- preflight and local CI are green
- delivery bundle format is complete
- verdict is restricted to supported family scope

### Can Ship With Restricted Scope Only

All of the following are true:

- nightly gate is pass
- wetlab selected all-atom gate is pass
- transporter remains blocked
- outbound language is explicitly limited to `kinase`, `ion_channel`, and `gpcr`

### Do Not Ship

Any of the following are true:

- nightly gate is still failed in the canonical top-level summary
- wetlab selected all-atom gate is still failed
- preflight is red
- rerun environment is not reproducible
- delivery verdict depends on artifacts known to be ambiguous or overstated

## Practical Sequence

1. Close `nightly_reliability` via top-level stage6 gate burndown and a green canonical summary.
2. Close `wetlab_selected_allatom`.
3. Freeze restricted claim scope and outbound wording.
4. Pin environment, capture engine provenance, and document the machine baseline.
5. Standardize the local preflight and delivery bundle.
6. Tighten commercialization/control-plane verdict logic.
7. Expand to transporter only after evidence closure is real.

## Immediate Working Rule

Until P0 is closed, the repo should be described as:

- a strong local validation stack for selected families
- not yet a broad commercial platform
- not yet ready for transporter-commercial claims
- not yet safe to describe as fully delivery-ready without manual guardrails
