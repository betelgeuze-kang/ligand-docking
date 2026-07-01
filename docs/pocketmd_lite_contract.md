# PocketMD Lite Contract (top-k pocket-local refinement)

Status: reference. Priority 5 (final) of the product-vision roadmap. Closes the
cascade.

Source of truth:
- Gate/grader: `betelgeuze_product/pocketmd_lite_contract.py` (dep-free)
- Stage3 contact/clash intake:
  `tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py`
- Report materializer: `tools/product/build_pocketmd_lite_report.py`
- Evidence work order: `tools/product/build_pocketmd_lite_refinement_work_order.py`
- Remaining evidence queue:
  `tools/product/build_pocketmd_lite_remaining_evidence_queue.py`
- Refinement engine: `core/refine_physics.py`, `core/mm_gbsa.py`,
  `betelgeuze_engine/biodiscovery/pose.py` (`clash_count`, `clash_cutoff_a`)
- Claim wording: `.kiro/steering/claim_safe_wording.md`

## The cascade

```
cheap O(N) global screening
  -> H-Bond BackMap (ONSPS-4) interpretable rescoring   (docs/hbond_backmap_contract.md)
  -> top-k pocket-local micro-refinement (PocketMD Lite) (this contract)
```

Refining every candidate with expensive local-min / micro-MD is not viable
(stage2 dominates wall-clock). PocketMD Lite refines only the **top-k**
(`rank_pct <= top_k_threshold_pct`, default 5%) and grades each refined candidate
into an uncertainty band.

## Selection

`is_refine_selected(family, rank_pct, top_k_threshold_pct)`: true only when
`rank_pct <= threshold` (default `0.05`). Non-selected candidates are
`coarse_only` (kept from cheap screening, not a refinement claim). A caller may
force `selected_for_refine` only for already-reviewed top-k handoff rows.

## Uncertainty bands (fail-closed)

| band | meaning | claim_safe |
| --- | --- | :--: |
| `green` | survived + persistence + no clash | yes |
| `yellow` | survived but borderline (weak persistence or residual clash) | no (review) |
| `red` | local-min did not survive | no |
| `abstain` | required refinement evidence missing | no |
| `coarse_only` | not selected for refinement | no |

A **green** band requires all of:
- `local_min_ligand_rmsd_a <= 2.0` (restrained local-min survival),
- `hbond_persistence >= 0.5`,
- `contact_persistence >= 0.5`,
- `initial_clash_count` or `pre_refine_clash_count` plus final `clash_count`
  so `clash_relief_count = initial_clash_count - clash_count` can be reported,
- `clash_count <= 0` (no residual clash after relief).

Any missing evidence -> `abstain` (never guess). Failed survival -> `red`.
Survived-but-borderline -> `yellow` with `review_flags`
(`residual_clash`, `weak_hbond_persistence`, `weak_contact_persistence`).
Thresholds are parameters; defaults are documented above.

## Per-candidate inputs

`build_pocketmd_lite_assessment(candidate, **thresholds)` requires `entry_id`;
optional `family`, `rank_pct`, `selected_for_refine`, `local_min_ligand_rmsd_a`,
`hbond_persistence`, `contact_persistence`, `initial_clash_count`
(`pre_refine_clash_count` alias), and `clash_count`.

## Batch KPIs

`build_pocketmd_lite_report(candidates)` rolls up `band_counts`, `refined_count`,
`coarse_only_count`, uncertainty posture, clash-relief reporting counts, and two
KPIs:
- `refine_claim_safe_rate` = green / refined,
- `abstention_rate` = abstain / refined.

## Materializer

`tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py` may be run
first when the current stage3 summary contains exact top-k contact/clash frame
evidence. It only fills:
- `contact_persistence` from `frame_contact_presence_fraction`,
- `clash_count=0` when `clash_count_mean_per_frame == 0` and
  `clash_frame_fraction == 0`.

It never infers `local_min_ligand_rmsd_a` or `hbond_persistence`; those remain
required PocketMD Lite evidence.

`tools/product/build_pocketmd_lite_report.py` reads
`config/pocketmd_lite_candidates_current.csv` and writes
`runs/pocketmd_lite_report_current.{json,md,csv}`. The current candidate CSV may
contain top-k rows before expensive refinement evidence exists; those rows
`abstain` until local-min survival, contact persistence, H-bond persistence,
baseline/final clash counts, and clash relief are supplied.

```
python3 tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py
python3 tools/product/build_pocketmd_lite_report.py
```

## Evidence work order

`tools/product/build_pocketmd_lite_refinement_work_order.py` reads the current
report and candidate CSV and writes
`runs/pocketmd_lite_refinement_work_order_current.{json,md,csv}`. It is also
read-only. Its role is to pin the exact top-k rows still missing:
- `local_min_ligand_rmsd_a`,
- `hbond_persistence`,
- `contact_persistence`,
- `initial_clash_count` (or `pre_refine_clash_count` input alias),
- `clash_count`.

`tools/product/build_pocketmd_lite_remaining_evidence_queue.py` additionally
joins the current top-k candidate CSV with the local stage3 summary and writes
`runs/pocketmd_lite_remaining_evidence_queue_current.{json,md,csv}`. It does
not calculate scientific metrics. It records the stage3 trajectory/protein
paths, local path availability, and the remaining claim-grade fields that must
be supplied before the report can move out of `abstain`.

After those fields are supplied to the candidate CSV, rerun:

```
python3 tools/product/build_pocketmd_lite_stage3_contact_clash_intake.py
python3 tools/product/build_pocketmd_lite_report.py
python3 tools/product/build_pocketmd_lite_refinement_work_order.py
python3 tools/product/build_pocketmd_lite_remaining_evidence_queue.py
```

## Out of scope

- Not all-atom MD and not a binding-affinity claim. The local-min / micro-MD
  computation runs under numpy/OpenMM/GPU/CI; this layer selects, grades, and
  governs. Green bands are interpretable refinement evidence, surfaced in the
  delivery evidence bundle alongside the H-Bond BackMap report.
