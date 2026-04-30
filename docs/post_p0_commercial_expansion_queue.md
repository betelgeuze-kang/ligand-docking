# Post-P0 Commercial Expansion Queue

## Purpose

This queue starts after the current restricted `kinase`, `ion_channel`, and `gpcr` P0 delivery claim. It is planning-only and does not widen the current delivery verdict. The first active queue item is GPCR scale-up recovery because the current 100k claim remains blocked.

## Boundary

- P0 delivery wording stays limited to `kinase`, `ion_channel`, and `gpcr`.
- Transporter, CA2/PXR, and IDP broader-promotion artifacts may be reviewed or staged, but they do not authorize broader delivery-ready wording.
- The queue below is the next commercial follow-up path, not a new claim boundary.

## Priority Queue

0. GPCR scale-up recovery
   - Keep `claim_safe=false` while `gpcr_core_full` remains the primary 100k blocker.
   - The current blocker is PR-AUC/top20 regression, not a documentation issue.
   - The `chembl50_v4` endpoint is locked-decoy apply-safe, but router promotion remains blocked until a real 100k rerun/compare is green.

     ```bash
     python3 tools/build_gpcr_100k_failure_analysis.py
     python3 tools/build_gpcr_apply_safe_endpoint.py
     python3 tools/build_gpcr_residual_chembl50_v4_endpoint_note.py
     python3 tools/build_ligand_scaleup_benchmark_summary.py
     ```

   - If the raw 100k ranking CSV inputs are absent, `build_gpcr_100k_failure_analysis.py` must emit `blocked_missing_csv_inputs`; do not infer recovery from the previous snapshot alone.
   - Source of truth: `runs/ligand_scaleup_benchmark_summary_current.json` plus `runs/gpcr_100k_failure_analysis_current.json`.

1. PDE translation quality
   - Keep the T. cruzi PDE rescue/translation lane honest.
   - Use the local translation annotator, rescue/validate pair, and translation-quality packet before any expensive rerun:

     ```bash
     python3 tools/build_wetlab_rescue_three_bead_candidates.py
     python3 tools/run_wetlab_tcruzi_pde_allatom_rescue.py --top-k 8 --filter-mode strict_then_near_fill --execute
     python3 tools/validate_wetlab_tcruzi_pde_allatom_rescue_attempt.py
     python3 tools/build_wetlab_tcruzi_pde_allatom_review_packet.py
     python3 tools/build_wetlab_tcruzi_pde_translation_quality_packet.py
     python3 tools/build_local_delivery_verdict_gate.py
     ```

   - Do not widen claims while `translation_quality_ready=false` or the rescue attempt is incomplete.
   - Source of truth: `runs/wetlab_tcruzi_pde_translation_quality_packet_current.md`.

2. Transporter AQP1 / GLUT1 evidence closure
   - Sequence AQP1 first, then GLUT1.
   - Use the validate-only scaffold check and the transporter readiness rollup:

     ```bash
     python3 tools/run_transporter_membrane_scaffold_check.py
     python3 tools/build_transporter_membrane_readiness.py
     python3 tools/build_family_expansion_status_rollup.py
     python3 tools/build_family_evidence_acquisition_queue.py
     ```

   - Keep `AQP1` and `GLUT1` dry-run/template-only until the ligand packets are frozen and donor policy is explicit.
   - Source docs: `docs/transporter_membrane_runnable_scaffold_notes.md`, `docs/transporter_membrane_expansion_scaffold_plan.md`.

3. CA2 / PXR packet closure
   - Close the packet work before any broader family wording:

     ```bash
     python3 tools/build_ca2_packet_replacement_workbook.py
     python3 tools/build_ca2_packet_replacement_readiness.py
     python3 tools/build_pxr_ligand_packet_fill_workbook.py
     python3 tools/validate_pxr_packet_fill_readiness.py
     python3 tools/build_partial_authoritative_quickstart_packet.py
     ```

   - CA2 stays review-only negative closure until the packet fields are frozen.
   - PXR stays partial-authoritative until quantitative provenance is filled.
   - Source docs: `docs/non_kinase_enzyme_ca2_runnable_packet_plan.md`, `docs/non_kinase_enzyme_ca2_ligand_packet_p0_plan.md`, `docs/nuclear_receptor_pxr_ligand_packet_fill_workbook.md`.

4. IDP broader-promotion boundaries
   - Keep broader promotion blocked while the bounded lane is evaluated.
   - Use the broader-promotion review and resolution helpers:

     ```bash
     python3 tools/build_idp_broader_promotion_review_packet.py
     python3 tools/build_idp_broader_promotion_resolution.py
     python3 tools/build_idp_commercial_pretest_packet.py
     python3 tools/build_pretest_execution_readiness.py
     ```

   - The admitted one-wider shadow lane is still not broader commercialization.
   - Source helpers: `tools/build_idp_broader_promotion_review_packet.py`, `tools/build_idp_broader_promotion_resolution.py`.

## What This Queue Does Not Do

- It does not change the current P0 verdict.
- It does not promote transporter, CA2/PXR, or IDP broader-promotion evidence into delivery-ready wording.
- It does not replace the current local-delivery gate, claim policy, or verdict validation flow.
