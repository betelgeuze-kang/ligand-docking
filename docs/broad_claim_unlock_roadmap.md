# Broad Claim Unlock Roadmap

The restricted local-delivery scope is green only when the current verdict gate
and bundle validator pass for the documented restricted scope. Broader claims
remain separate. This roadmap keeps the unlock work split so one green lane does
not accidentally promote another.

## Current Baseline

| Claim area | Current posture | Do not claim yet |
| --- | --- | --- |
| Restricted local delivery | Green when `runs/local_delivery_verdict_gate_current.json` and bundle validation are green for the restricted scope | General commercialization across all families. |
| Broad GPCR | Blocked / diagnostic outside tracked green evidence | Broad GPCR family parity, Schrodinger-class discovery parity, or hard-decoy generalization. |
| Wetlab proof | Computational selected-allatom evidence green; experimental proof not established | Wetlab-proven T. cruzi PDE hit or therapeutic activity. |
| Platform/router/scorer promotion | Separated from accuracy scorecard | Automatic router/scorer/platform deployment or unattended decision-making. |

## Broad GPCR Unlock Checklist

Required before any broad GPCR claim:

- Freeze the intended family-held-out GPCR packet and record target/ligand row
  identity, row hash, and leakage audit.
- Demonstrate ranking quality on the full guarded hard-decoy surface, not only a
  target-specific or selected-slice repair.
- Meet the predeclared PR-AUC, PR-AUC CI-low, top-k, and family-held-out gates
  with source-consistent artifacts.
- Keep positive coverage, hard-decoy construction, scoring version, and leakage
  audit tied to the same packet.
- Attach a current broad-claim review receipt such as the GPCR broad-claim
  readiness/review artifacts produced by the `build_gpcr_*` tools.
- Preserve rejected/shadow runs as negative evidence and do not overwrite them
  with the first favorable run.

Unlock wording only after all of the above are current and green:

`Broad GPCR claim review is green for the named frozen packet and acceptance
profile.`

## Wetlab Proof Unlock Checklist

Required before any wetlab-proven hit claim:

- Keep the current computational PDE selected-allatom evidence separate from
  experimental proof.
- Obtain prospective wetlab assay results through an approved external workflow.
- Record assay protocol, compound identity, source, concentration series,
  controls, replicate policy, and raw-to-summary transformation.
- Validate the wetlab intake packet and preserve failed or ambiguous assay rows.
- Tie the wetlab result back to the exact computational candidate identity
  without changing thresholds after the result is known.
- Update the claim policy and evidence ladder only after the wetlab packet is
  review-ready.

Unlock wording only after all of the above are current and green:

`Wetlab evidence supports the named candidate under the recorded assay protocol.`

Do not shorten this to a broad therapeutic or clinical claim.

## Platform / Router / Scorer Promotion Checklist

Required before automatic promotion or platform-deployment claims:

- Keep scorer deployment, router promotion, and platform readiness as separate
  gates even when the accuracy scorecard is green.
- Validate API runner profile enablement and promotion receipts for each profile.
- Prove signed runner metadata, source-artifact freshness, replay hash stability,
  and bundle-validation consistency.
- Confirm production deployment guardrails: authorization, operator approval,
  queue state, rollback path, monitoring, and no external mutation without human
  approval.
- Attach a current product evidence bundle and ensure it stays blocked when any
  clean-container, signed-manifest, runtime-proof, or claim-policy input is
  missing.
- Preserve the restricted local-delivery wording until the platform/router/scorer
  promotion gate explicitly passes.

Unlock wording only after all of the above are current and green:

`The named validated runner profile is promotion-ready under the recorded
operator-approved platform gate.`

This still does not imply unattended broad drug-discovery operation.

## Reviewer Rule

If a broad claim depends on more than one lane, every lane must have its own
current receipt. Do not use a green restricted delivery verdict to unlock broad
GPCR, wetlab proof, or platform/router/scorer promotion.
