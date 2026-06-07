# CASP17 MassiveFold Model1 Freeze Decision Packet

- generated: `2026-06-01T23:18:08+09:00`
- status: `massivefold_model1_freeze_decision_packet_ready_external_only`
- decisions ready/blocked/total: `4/0/4`
- freeze ready/blocked: `3/1`
- conditional/watch/manual-review: `2/1/1`
- RNA/protein-complex: `3/1`
- first freeze-ready: `R2350` `rna_hybrid` `freeze_ready_external_only_conditional`
- first blocked: `R2352` `rna_hybrid` `freeze_blocked_manual_review`
- decision_rule_id: `no_native_model1_freeze_decision_v1`
- next action: feed freeze-ready decisions into the external-only model-selection ledger; keep manual-review targets blocked

## Decisions

| rank | target | group | probe result | margin | freeze decision | final model1 | alternate | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2350` | `rna_hybrid` | `probe_pass_model1_retained` | `0.64247` | `freeze_ready_external_only_conditional` | `Model_20_af3_woPaired_af3_seed_612441_sample_0_pred_640.cif` | `-` | `casp17/massivefold_model1_freeze_decisions/01_rna_hybrid_r2350/FREEZE_DECISION.md` |
| `2` | `R2353` | `rna_hybrid` | `probe_pass_model1_retained` | `0.78355` | `freeze_ready_external_only_conditional` | `Model_7_af3_woPaired_af3_seed_634615_sample_2_pred_387.cif` | `-` | `casp17/massivefold_model1_freeze_decisions/02_rna_hybrid_r2353/FREEZE_DECISION.md` |
| `3` | `H2312` | `protein_complex` | `probe_pass_model1_retained` | `0.10755` | `freeze_ready_external_only_watch` | `Model_7550_afm_basic_model_5_multimer_v1_pred_11.pdb` | `-` | `casp17/massivefold_model1_freeze_decisions/03_protein_complex_h2312/FREEZE_DECISION.md` |
| `4` | `R2352` | `rna_hybrid` | `probe_fail_model1_displaced` | `-0.23587` | `freeze_blocked_manual_review` | `-` | `Model_7_af3_woPaired_woTemplates_af3_seed_26386_sample_2_pred_237.cif` | `casp17/massivefold_model1_freeze_decisions/04_rna_hybrid_r2352/FREEZE_DECISION.md` |

## Claim Boundary

CASP17 MassiveFold model1 freeze decision packet only. Decisions are external no-native model-selection controls derived from probe outcomes. They are not native accuracy, internal prediction proof, or CASP submission evidence.
