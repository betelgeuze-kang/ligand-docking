# CASP17 MassiveFold Freeze-Candidate Format Preflight

- generated: `2026-06-02T02:16:54+09:00`
- status: `massivefold_freeze_candidate_format_preflight_ready_external_only`
- preflight ready/blocked/total: `10/0/10`
- freeze existing/probe: `2/8`
- RNA/protein-complex: `4/6`
- selected pdb/cif: `6/4`
- packaged pdb/cif: `0/10`
- target/ext/model/viewer/projection/top5: `10/10/10/10/10/10`
- first preflight: `H2319` `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb`
- proof eligible: `False` policy `do_not_mark_as_internal_prediction`
- next action: run official CASP rule checks only after operator resolves watch/manual actions and approves formatting

## Freeze Candidates

| rank | target | class | selected model | ext | bytes | viewer | preflight | blockers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `H2319` | `freeze_candidate_after_probe` | `Model_1_afm_basic_model_4_multimer_v3_pred_25.pdb` | `.pdb` | `628803` | `casp17/massivefold_representative_viewers/h2319/selection_125_afm_basic_v3_model_1/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/01_protein_complex_h2319/FORMAT_PREFLIGHT.md` | `-` |
| `2` | `H2321` | `freeze_candidate_after_probe` | `Model_3_afm_dropout_full_model_2_multimer_v3_pred_48.pdb` | `.pdb` | `639495` | `casp17/massivefold_representative_viewers/h2321/selection_086_afm_dropout_full_v3_model_3/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/02_protein_complex_h2321/FORMAT_PREFLIGHT.md` | `-` |
| `3` | `H2335` | `freeze_candidate_after_probe` | `Model_7830_afm_basic_model_5_multimer_v1_pred_39.pdb` | `.pdb` | `1170207` | `casp17/massivefold_representative_viewers/h2335/selection_030_afm_basic_v1_model_7830/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/03_protein_complex_h2335/FORMAT_PREFLIGHT.md` | `-` |
| `4` | `H2338` | `freeze_candidate_after_probe` | `Model_2_afm_dropout_full_model_4_multimer_v3_pred_64.pdb` | `.pdb` | `659340` | `casp17/massivefold_representative_viewers/h2338/selection_029_afm_dropout_full_v3_model_2/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/04_protein_complex_h2338/FORMAT_PREFLIGHT.md` | `-` |
| `5` | `H2339` | `freeze_candidate_after_probe` | `Model_135_afm_basic_model_5_multimer_v1_pred_62.pdb` | `.pdb` | `657639` | `casp17/massivefold_representative_viewers/h2339/selection_111_afm_basic_v1_model_135/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/05_protein_complex_h2339/FORMAT_PREFLIGHT.md` | `-` |
| `6` | `R2341` | `freeze_candidate_after_probe` | `Model_2_af3_basic_af3_seed_672131_sample_4_pred_869.cif` | `.cif` | `319897` | `casp17/massivefold_representative_viewers/r2341/selection_031_basic_model_2/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/06_rna_hybrid_r2341/FORMAT_PREFLIGHT.md` | `-` |
| `7` | `R2345` | `freeze_candidate_after_probe` | `Model_4_af3_woUnpaired_af3_seed_418984_sample_3_pred_713.cif` | `.cif` | `111063` | `casp17/massivefold_representative_viewers/r2345/selection_013_woUnpaired_model_4/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/07_rna_hybrid_r2345/FORMAT_PREFLIGHT.md` | `-` |
| `8` | `T2313` | `freeze_candidate_after_probe` | `Model_5_afm_woTemplates_model_4_multimer_v3_pred_28.pdb` | `.pdb` | `1170531` | `casp17/massivefold_representative_viewers/t2313/selection_085_afm_woTemplates_v3_model_5/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/08_protein_complex_t2313/FORMAT_PREFLIGHT.md` | `-` |
| `9` | `R2350` | `freeze_candidate_existing` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `.cif` | `661942` | `casp17/massivefold_representative_viewers/r2350/selection_020_woPaired_model_20/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/09_rna_hybrid_r2350/FORMAT_PREFLIGHT.md` | `-` |
| `10` | `R2353` | `freeze_candidate_existing` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `.cif` | `670369` | `casp17/massivefold_representative_viewers/r2353/selection_021_woPaired_model_7/viewer.html` | `casp17/massivefold_freeze_candidate_format_preflight/10_rna_hybrid_r2353/FORMAT_PREFLIGHT.md` | `-` |

## Claim Boundary

CASP17 MassiveFold freeze-candidate format preflight only. It checks local external-only model candidate files, viewers, projections, target IDs, and top5 manifests before any operator-approved CASP rule check. It is not native accuracy, not internal prediction proof, not a CASP submission, and not permission to submit.
