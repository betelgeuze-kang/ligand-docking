# CASP17 MassiveFold Model1 Selection Calibration Gate

- generated: `2026-06-01T22:48:10+09:00`
- status: `massivefold_model1_selection_calibration_gate_ready_external_only`
- freeze_gate_status: `model1_freeze_blocked_by_calibration`
- gates ready/blocked/total: `4/0/4`
- hold/watch/probe-required/freeze-ready: `2/2/4/0`
- RNA/protein-complex gates: `3/1`
- first gate: `R2350` `rna_hybrid` `64.686` `hold_model1_freeze_probe_required` `top5_rerank_consistency_probe`
- selection_rule_id: `no_native_model1_selection_gate_v1`
- next action: run required no-native probes before freezing model1 for the gated critical targets

## Gates

| rank | target | group | score | decision | blocker | probe | exit criterion | packet |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2350` | `rna_hybrid` | `64.686` | `hold_model1_freeze_probe_required` | `calibration_required_before_freeze` | `top5_rerank_consistency_probe` | model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore | `casp17/massivefold_model1_selection_calibration_gate/01_rna_hybrid_r2350/CALIBRATION_GATE.md` |
| `2` | `R2353` | `rna_hybrid` | `58.24` | `hold_model1_freeze_probe_required` | `calibration_required_before_freeze` | `top5_rerank_consistency_probe` | model1 remains top candidate after gap, diversity, geometry, and low-confidence rescore | `casp17/massivefold_model1_selection_calibration_gate/02_rna_hybrid_r2353/CALIBRATION_GATE.md` |
| `3` | `H2312` | `protein_complex` | `48.165` | `conditional_watch_probe_before_final_model1` | `critical_watch_requires_rescore` | `lightweight_rescore_probe` | no new high-risk flag appears after targeted no-native rescore | `casp17/massivefold_model1_selection_calibration_gate/03_protein_complex_h2312/CALIBRATION_GATE.md` |
| `4` | `R2352` | `rna_hybrid` | `30.586` | `conditional_watch_probe_before_final_model1` | `critical_watch_requires_rescore` | `lightweight_rescore_probe` | no new high-risk flag appears after targeted no-native rescore | `casp17/massivefold_model1_selection_calibration_gate/04_rna_hybrid_r2352/CALIBRATION_GATE.md` |

## Claim Boundary

CASP17 MassiveFold model1 selection calibration gate only. It converts external no-native rerank score ledger rows into model1 freeze, hold, and probe decisions for accuracy-estimation workflow. It does not use native structures, copy coordinates, create internal competitive-proof evidence, or submit models.
