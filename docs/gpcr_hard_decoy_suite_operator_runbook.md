# GPCR Hard-Decoy Suite — Operator Input Runbook

Status: reference. Operator fill guide for the GPCR hard-decoy claim gate
(DRD2 / HTR2A / OPRM1).

Source of truth:
- Input template: `config/gpcr_hard_decoy_suite_input_template.csv`
- Materializer: `tools/product/build_gpcr_hard_decoy_suite_report.py`
- Gate/evaluator: `betelgeuze_product/gpcr_hard_decoy_suite.py`
- Contract: `docs/gpcr_hard_decoy_suite_contract.md`
- Claim wording: `.kiro/steering/claim_safe_wording.md`

## Purpose

The hard-decoy evaluator decides one question — *is broad GPCR/router claimable
yet?* — from per-target aggregate rows. This runbook tells an operator how to
fill `config/gpcr_hard_decoy_suite_input_template.csv` from the existing GPCR
diagnostics already in `runs/`, then run the materializer.

The template ships with the three required targets (DRD2, HTR2A, OPRM1) and
**empty metric cells**. Run as-is (unfilled), the gate fail-closes to
`broad_family_locked` — that is the correct default until real diagnostics are
copied in. This runbook never relaxes the gate; it only documents data entry.

## Columns (one row per target)

| column | required | meaning | source |
| --- | :--: | --- | --- |
| `target_id` | yes | `DRD2`, `HTR2A`, or `OPRM1` (fixed required set) | fixed |
| `positive_count` | yes | number of known positives evaluated | diagnostics packet |
| `ranking_pr_auc` | no | ranking PR-AUC point estimate | `runs/gpcr_ci_low_recovery_packet_*` |
| `ranking_pr_auc_ci_low` | no | bootstrap CI-low of PR-AUC (gate: `>= 0.45`) | `runs/gpcr_ci_low_recovery_packet_*` |
| `top20_hit_rate` | no | top-20 hit rate (gate: `>= 0.20`) | ranking diagnostics |
| `decoys_above_positive_count` | no | decoys ranked above the positive (gate: `== 0`) | `runs/gpcr_guarded_100k_rank_failure_diagnostics_*` |
| `positive_target_rank` | no | rank of the positive in the pool | rank-failure diagnostics |
| `positive_anchor_distance_a` | no | positive distance to the native anchor (Å) | `runs/gpcr_drd2_*` / anchor diagnostics |
| `top_decoy_anchor_distance_a` | no | best decoy distance to the native anchor (Å) | anchor diagnostics |
| `decoy_class_counts` | no | JSON object of decoy-class counts | decoy taxonomy diagnostics |

`decoy_class_counts` is a JSON-string cell. Allowed classes only:
`over_anchored`, `same_signature`, `multipolar`, `pose_distorted_valid_anchor`,
`valid_anchor_challenge`, `generic`. Example cell: `{"over_anchored": 3}`. An
unknown class fail-closes the materializer.

## Gate (fail-closed; do not relax)

A target is `green` only when **all** hold:
- `ranking_pr_auc_ci_low >= 0.45`
- `top20_hit_rate >= 0.20`
- `decoys_above_positive_count == 0`
- the positive is not out-anchored: if both anchor distances are present,
  `top_decoy_anchor_distance_a >= positive_anchor_distance_a`.

The broad GPCR/router family claim stays `broad_family_locked` until every
required target (DRD2, HTR2A, OPRM1) is green.

## Illustrative example (NOT real results)

The values below are illustrative only to show row shape; they are not measured
evidence and must not be cited. Replace with values copied from the diagnostics.

```
DRD2,1,0.30,0.02,0.10,5314,5315,3.25,2.48,"{""over_anchored"": 10}"
```

This row is blocked (CI-low/top20 below gate, decoys above positive, and a decoy
closer to the anchor than the positive → `decoy_over_anchored_vs_positive` with
root cause `anchor_separation_insufficient`).

## Run

```
python3 tools/product/build_gpcr_hard_decoy_suite_report.py \
  --input-csv config/gpcr_hard_decoy_suite_input_template.csv \
  --out-json runs/gpcr_hard_decoy_suite_current.json \
  --out-md   runs/gpcr_hard_decoy_suite_current.md \
  --out-csv  runs/gpcr_hard_decoy_suite_current.csv
```

Read `runs/gpcr_hard_decoy_suite_current.md` for the per-target gate decision,
blockers, and root-cause tags. The materializer runs no scoring, generates no
decoys, and never widens a claim; `broad_family_locked` is a successful, honest
result.
