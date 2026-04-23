# Draft Discussion Points For bioRxiv

## Main interpretation

The current `v7r1` package should be interpreted as the endpoint of a reviewable corrective validation process rather than as a single favorable late-stage run. This distinction matters because the evidence bundle retains the frozen original preregistration, failed intermediate executions, preregistered acceptance logic, the first fully passing `v6r3` close-out, the baseline-gauntlet comparison, and the audited promoted package. The validation trail can therefore be inspected end to end rather than only at the final successful run.

## Why the close-out is credible

The corrective path did not rely on broad post hoc relaxation of the central performance claim. Instead, successive revisions addressed separable sources of failure: infrastructure instability, leakage-sensitive split configuration, score-column wiring mismatches, kinase-specific operational gate mismatch, and finally a GPCR live-run metadata propagation bug. A final winner-informed comparison step then improved selected non-GPCR ligand tasks without changing the pass/fail structure of the claim sets. This staged reduction in failure modes is important because it narrows interpretation. By `v6r3`, the residual blocker had been isolated to `gpcr_core_full`, and the key improvement came from restoring the intended score inputs rather than weakening the GPCR primary gate.

## Domain-level interpretation

The accepted package supports a cross-domain claim rather than a single-domain overfit result. `TRPV1` blind performance remained strong once blind-score wiring was corrected. Kinase ranking performance was consistently saturated, and the corrective change there primarily clarified that the original failures reflected gate mismatch rather than ranking collapse. The IDP stack remained stable throughout and passed under the frozen current release reference. The final GPCR close-out therefore served as the last model-side blocker, not as one of many unresolved domains.

## Smoke interpretation

The smoke set should not be overread as a substitute for the full claim set. Its role is reproducibility support. The accepted package explicitly preserves `raw_pass = false` where the full operational gate remains intentionally stricter than smoke interpretation, and it reports smoke acceptance through preregistered acceptance notes rather than silently rewriting task outcomes. This makes the smoke evidence transparent and prevents it from being confused with the core blind claim.

## Review-facing takeaway

The practical review-facing takeaway is that the final package does not ask the reader to trust a hidden tuning loop. Instead, it presents a frozen specification, a visible corrective history, an explicit baseline-gauntlet comparison, an audited promoted package, a completed three-scenario robustness battery, and a fully passing run across the three preregistered claim layers. That combination is the strongest argument for treating `v7r1` as a credible promoted validation package rather than as a selectively reported best-case snapshot.

## Robustness interpretation

The robustness battery strengthens that interpretation without erasing where the stack remains most sensitive. Across `embed_seed_shift1`, `decoy_seed_shift1`, and `decoy_pressure_12k`, all three preregistered sets still passed and no ligand task crossed from pass to fail. At the same time, the battery was not numerically flat: `embed_seed_shift1` was near-invariant, the hard-decoy perturbation scenarios produced the most visible drift, and `gpcr_core_full` showed the largest PR-AUC drop while still remaining comfortably within the passing regime. Kinase PR-AUC stayed flat across the completed scenarios and `TRPV1` remained stable with only small movement. This is the right kind of robustness result for the current claim. It supports package-level stability and domain-level interpretability while also showing that GPCR core blind remains the most perturbation-sensitive part of the ligand stack.

## Temporal-scaffold interpretation

The temporal scaffold should be read in the same spirit. It is not presented as a completed per-row temporal generalization study or as a true future-only benchmark. Instead, it is reported as a reviewer-auditable intermediate state: ligand rows are fully item-level ready, most IDP rows are item-level ready, and the remaining four IDP rows are explicitly policy-coded as either no-safe-public-anchor, fragment-anchor mismatch, or intentional dataset-level control. This is stronger than an unstructured “future work” placeholder because the unresolved set is now small, typed, and frozen in the current submission bundle, but it still does not justify calling the provisional temporal runner a fully realized temporal split.

## Claim-scope boundary

It is important to keep the claim boundary explicit. The accepted package supports a strong computational statement under frozen and preregistered evaluation, but it does not by itself establish prospective wet-lab hit discovery, orthogonal biochemical confirmation, medicinal-chemistry optimization, downstream therapeutic utility, or a fully completed item-level temporal generalization claim. The fairest description is therefore an audited cross-domain computational validation package with a separately documented robustness battery and a partially item-level temporal scaffold, not an experimentally validated screening platform. That distinction strengthens the paper because it aligns the stated claim with the actual evidence bundle.
