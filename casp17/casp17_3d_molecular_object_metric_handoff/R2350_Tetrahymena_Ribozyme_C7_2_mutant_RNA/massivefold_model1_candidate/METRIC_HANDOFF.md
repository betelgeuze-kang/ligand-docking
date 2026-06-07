# R2350_Tetrahymena_Ribozyme_C7_2_mutant_RNA / massivefold_model1_candidate Metric Handoff

- status: `ready_review_only`
- metric family: `rna_hybrid`
- metric evidence: `awaiting_strict_blind_native_metric_evidence`
- metrics: `lDDT|TM-score|RMSD|MolProbity`
- atlas object: `casp17/casp17_3d_molecular_object_atlas/R2350_Tetrahymena_Ribozyme_C7_2_mutant_RNA/massivefold_model1_candidate`
- model: `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/model.cif`
- viewer: `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/viewer.html`
- projection: `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/projection.svg`
- top5 manifest: `casp17/massivefold_representative_rerank/r2350/top5_manifest.csv`
- escrow: `casp17/massivefold_freeze_candidate_escrow/09_rna_hybrid_r2350/FREEZE_ESCROW.md`
- competitive proof eligible: `false`
- blockers: `-`
- notes: `rna_hybrid_metric_extension_required`

## Metric Requirements

| metric | input contract | evidence |
| --- | --- | --- |
| `lDDT` | `prediction/native residue mapping` | `awaiting_strict_blind_native_metric_evidence` |
| `TM-score` | `prediction/native nucleic-acid or hybrid residue mapping` | `awaiting_strict_blind_native_metric_evidence` |
| `RMSD` | `prediction/native nucleic-acid or hybrid residue mapping` | `awaiting_strict_blind_native_metric_evidence` |
| `MolProbity` | `prediction coordinate geometry validation` | `awaiting_strict_blind_native_metric_evidence` |

## Claim Boundary

CASP17 3D molecular object metric handoff only. It maps organized 3D object folders to win-tier metric requirements for review. It does not copy model coordinates, compute native accuracy, serialize a CASP author code, claim strict-blind competitive proof, or submit to CASP.
