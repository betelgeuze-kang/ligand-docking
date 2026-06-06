# P2 External Metric Contract

Status: active (2026-06-06)  
Scope: **restricted local-delivery** (`kinase`, `gpcr`, `ion_channel`) regression only.

## Inputs

| Field | Required | Notes |
|-------|----------|-------|
| `row_id` | yes | Stable row identifier |
| `target_id` | yes | Target label |
| `topology_fidelity` | yes | `sequence_mapped` or `placeholder_alanine` |
| `dockq_proxy` | no | Complex interface quality proxy (0–1) |
| `lddt_pli` | no | Ligand local distance difference test (0–1) |
| `molprobity_clashscore` | no | Lower is better; all-atom exported structures only |

## Outputs

Scorecard JSON (`runs/external_metric_scorecard_current.json`):

- `summary.claim_scope` = `restricted_local_delivery`
- `summary.claim_promotion_allowed` = **always false** for P2
- Per-row `row_status`: `blocked` | `missing` | `evaluated`
- Per-metric `*_status`: `blocked` | `missing` | `pass` | `fail`

## Fail-closed rules

1. `topology_fidelity=placeholder_alanine` → row **blocked** (no general-MD claim).
2. Missing all metric values → row **missing** (not pass).
3. Scorecard never promotes broad platform or OpenMM/Schrödinger parity wording.

## Builder

```bash
python3 tools/product/build_external_metric_scorecard.py \
  --input-json config/p2_external_metric_inputs.example.json \
  --out-json runs/external_metric_scorecard_current.json
```

## Claim boundary

Aligned with `core/claim_boundary.py` and P0/P1 manifest fidelity gates.
