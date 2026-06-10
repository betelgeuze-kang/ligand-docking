# Science Lane Blocker Dual Count Design

## Problem

CA2 (`ca2_direct_conflict_row_count=5`) and PXR (`pxr_must_defer_count=3`) retain non-zero science-lane counts by design. Those totals are honest audit signals, not delivery blockers. A single headline count conflates:

- **Parked / review-only** — documented no-claim posture; operator has explicitly deferred or conflict is catalogued without open swap work.
- **Active blocker** — replacement verification, exact-evidence intake, or workbook patch still open.

Dual counts preserve the legacy totals while separating burndown-relevant work from parked science policy.

## Semantics

| Field | Meaning |
| --- | --- |
| `*_row_count` / `*_count` | Legacy total (unchanged) |
| `*_parked_review_only_count` | Rows with closed operator posture or documented conflict-only lane |
| `*_active_blocker_count` | Rows with open verification, replacement, or exact-evidence work |

Invariant: `parked + active == total` (reconciled in `science_lane_blocker_accounting.py`).

Rollup convenience:

- `science_lane_parked_review_only_count` = CA2 parked + PXR parked
- `science_lane_active_blocker_count` = CA2 active + PXR active

## CA2 classification

Source artifacts:

- `runs/ca2_reviewer_workbench_current.json` — `operator_review_bucket=conflict_review`
- `runs/ca2_conflict_replacement_shortlist_current.json` — `replacement_status`

Rules (`dual_count_ca2_direct_conflicts`):

1. **Active** when shortlist `replacement_status` is `proposed_pending_verification` or `alternate_pending_verification`.
2. **Parked** when workbench `next_required_action=keep_review_only_conflict_documented`.
3. Otherwise **active** (default open work).
4. If workbench rows are missing, all totals count as **active** (conservative).

Replacement shortlist builder (`build_ca2_conflict_replacement_shortlist.py`) proposes functional surrogates with blank kcal and patches workbook/verification sheets pending CHEMBL205 negative verification.

## PXR classification

Source artifacts:

- `runs/pxr_pending_resolution_commit_packet_current.json` — `manual_commit_class=must_remain_deferred`
- `runs/pxr_defer_exact_evidence_operator_fill_guide_current.json` — operator fill guide rows (CSV supplement: `runs/pxr_defer_exact_evidence_intake_supplement_current.csv`)

Rules (`dual_count_pxr_must_defer`):

1. **Parked** when intake has `conflict_resolution_decision` in `{KEEP_DEFERRED, KEEP_BLOCKED}` and `review_decision` in `{KEEP_BLOCKED, KEEP_DEFERRED}`.
2. Otherwise **active** (operator still owes exact evidence or resolution).
3. If commit rows are missing, all totals count as **active**.

Operator fill guide (`build_pxr_defer_exact_evidence_operator_fill_guide.py`) pre-fills supplement rows with `KEEP_DEFERRED` / `KEEP_BLOCKED` and documents per-ligand evidence requirements. Never promote from activity proxy alone.

## Rollup emission

Dual counts are computed in:

- `build_execution_handoff_dashboard.py` (primary)
- `build_commercialization_gap_burndown.py` (pass-through from execution summary)
- `build_family_packet_catalog.py` (recompute from family artifacts)

Shared logic: `tools/accounting/science_lane_blocker_accounting.py`.

## Operator workflow

1. Run `build_ca2_conflict_replacement_shortlist.py --apply-workbook-patch`.
2. Run `build_pxr_defer_exact_evidence_operator_fill_guide.py`.
3. Regenerate execution handoff → gap burndown → family packet catalog.

Expected steady state with current policy: CA2 active=5 parked=0; PXR active=0 parked=3; `science_lane_active_blocker_count=5`, `science_lane_parked_review_only_count=3`.
