# CASP17 Competitive-Floor Evidence Round

- generated: `2026-05-25T23:17:38+09:00`
- round_status: `awaiting_import`
- apply_import/apply_row_fill: `False/False`
- import ready/applied/awaiting files/awaiting values: `0/0/180/270`
- intake patch candidates: `0`
- patch gate ready: `0`
- apply-plan planned/applied: `0/0`
- next action: enter proposed_value, evidence_ref, and operator_clearance in the import CSV

## Stages

| stage | status | ready | awaiting | blocked | applied | path | next action |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| `evidence_import` | `awaiting_import` | 0 | 450 | 0 | 0 | `casp17/casp17_competitive_floor_evidence_import_current.json` | enter proposed_value, evidence_ref, and operator_clearance in the import CSV |
| `value_ledger` | `awaiting_values` | 0 | 0 | 0 | 0 | `casp17/casp17_competitive_floor_value_ledger_current.json` | enter the cleared historical benchmark_id and cite the local target-selection evidence |
| `evidence_intake` | `awaiting_evidence` | 0 | 450 | 0 | 0 | `casp17/casp17_competitive_floor_evidence_intake_current.json` | fill benchmark_id in row_fill.csv from cleared local evidence |
| `row_fill_patch_gate` | `awaiting_evidence` | 0 | 450 | 0 | 0 | `casp17/casp17_competitive_floor_row_fill_patch_gate_current.json` | provide the missing cleared evidence, then rerun intake and this patch gate |
| `row_fill_apply_plan` | `awaiting_evidence` | 0 | 450 | 0 | 0 | `casp17/casp17_competitive_floor_row_fill_apply_plan_current.json` | wait for cleared evidence, then rerun intake and patch gate |

## Claim Boundary

Local competitive-floor evidence round only. It runs the local evidence import, value-ledger audit, evidence intake, row_fill patch gate, and row_fill apply-plan in order. It does not choose targets, clear no-leak provenance, fetch native structures, score native accuracy, run predictors, submit to CASP, or mutate row_fill.csv unless --apply-row-fill is explicitly provided.
