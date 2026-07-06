# PR38 Remote-Only Execution Checklist

Status: remote-only coordination checklist.

## Step 1 - PR39 CI runner hygiene

- Latest observed PR39 head: `a1287154cf1c5af17193c1d87f855f49c84c8313`.
- Observed remote workflows:
  - `product-api-worker`: success.
  - `product-image-smoke`: success.
- Next action: refresh PR39 description, keep CI-only claim boundary, then request review.

## Step 2 - PR38 split order

Remaining child PR order after PR39:

1. `source_of_truth_refresh`
2. `public_benchmark_phase2`
3. `pocketmd_lite_recovery`
4. `gpcr_hard_decoy_closure`
5. `operator_cockpit`
6. `f2g_f2h_preflight`
7. `docs_roadmap_sync`

Every child PR needs focused tests, `./scripts/ai-verify.sh`, and claim-boundary review.

## Step 3 - Source-of-truth refresh

Scope:

- reconcile roadmap and split-state wording;
- separate `main`, PR39-merged, and remaining PR38-draft states;
- keep restricted Tier-alpha and pre-paid-pilot boundaries explicit;
- avoid broad product, science, benchmark, or platform claim promotion.

## Step 4 - Benchmark and shadow templates

Prepare schema/checklist rows for:

- public benchmark receipts;
- same-input score evidence;
- reviewer metadata;
- restricted pilot shadow-case tracking.

Template readiness is not evidence closure.

## Step 5 - PocketMD Lite and GPCR cleanup

PocketMD Lite:

- keep read-only API/report posture;
- preserve missing protein-frame blockers;
- do not promote claim-grade wording until exact metrics exist.

GPCR hard-decoy:

- keep target/family-scoped wording;
- preserve broad GPCR/router/platform blockers;
- carry claim-lock evidence forward.

## Local execution still required

The following require owner/local evidence:

- source-of-truth regenerated artifacts;
- benchmark score/receipt rows;
- real restricted-pilot case rows;
- PocketMD Lite metric outputs;
- GPCR replay outputs;
- F2g/F2h authoritative surfaces.
