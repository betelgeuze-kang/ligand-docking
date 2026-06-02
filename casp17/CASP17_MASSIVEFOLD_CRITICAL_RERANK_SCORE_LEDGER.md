# CASP17 MassiveFold Critical Rerank Score Ledger

- generated: `2026-06-01T22:41:00+09:00`
- status: `massivefold_critical_rerank_score_ledger_ready_external_only`
- ledger rows ready/blocked/total: `4/0/4`
- bands immediate/calibrate/watch: `0/2/2`
- RNA/protein-complex rows: `3/1`
- top risk: `R2350` `rna_hybrid` `64.686` `calibrate_before_model1_freeze` `run_targeted_probe_then_freeze_model1_if_consistent`
- next action: review the top score-ledger rows first and promote the scoring rule into model1 selection

## Ledger

| rank | target | group | score | band | action | gap | diversity | geometry | low-conf | interface | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2350` | `rna_hybrid` | `64.686` | `calibrate_before_model1_freeze` | `run_targeted_probe_then_freeze_model1_if_consistent` | `0.7708` | `1` | `0.2` | `0.1` | `0` | `casp17/massivefold_critical_rerank_score_ledger/01_rna_hybrid_r2350/SCORE_LEDGER.md` |
| `2` | `R2353` | `rna_hybrid` | `58.24` | `calibrate_before_model1_freeze` | `run_targeted_probe_then_freeze_model1_if_consistent` | `0.072` | `1` | `1` | `1` | `0` | `casp17/massivefold_critical_rerank_score_ledger/02_rna_hybrid_r2353/SCORE_LEDGER.md` |
| `3` | `H2312` | `protein_complex` | `48.165` | `critical_watch_with_targeted_probe` | `keep_in_critical_batch_and_rescore_after_probe` | `0.187` | `0.15` | `1` | `0.1` | `0.15` | `casp17/massivefold_critical_rerank_score_ledger/03_protein_complex_h2312/SCORE_LEDGER.md` |
| `4` | `R2352` | `rna_hybrid` | `30.586` | `critical_watch_with_targeted_probe` | `keep_in_critical_batch_and_rescore_after_probe` | `0.2908` | `0.5` | `0.2` | `0.1` | `0` | `casp17/massivefold_critical_rerank_score_ledger/04_rna_hybrid_r2352/SCORE_LEDGER.md` |

## Claim Boundary

CASP17 MassiveFold critical rerank score ledger only. Scores are no-native model-selection risk scores from external self-assessment features; they are not native accuracy, internal prediction proof, or CASP submission evidence.
