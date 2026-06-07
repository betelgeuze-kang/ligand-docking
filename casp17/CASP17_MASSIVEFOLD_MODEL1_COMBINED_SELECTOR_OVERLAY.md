# CASP17 MassiveFold Model1 Combined Selector Overlay

- generated: `2026-06-02T01:09:40+09:00`
- status: `massivefold_model1_combined_selector_overlay_ready_external_only`
- overlay ready/blocked/total: `15/0/15`
- baseline capture/non-capture: `0.500` `0.500`
- freeze-ready/not-freeze-ready: `2/13`
- manual/interface/weak-probe/probe-required/review-watch/unknown: `1/1/0/11/0/0`
- RNA/protein-complex overlays: `6/9`
- first overlay: `R2352` `selector_blocked_manual_review` `do_not_freeze_model1_external_only`
- first freeze-ready: `R2350` `carry_model1_as_external_only_freeze_ready`
- proof eligible: `False` policy `do_not_mark_as_internal_prediction`
- next action: run targeted no-native probes for overlay probe-required targets and keep strict-blind proof separate

## Overlay Worklist

| rank | target | group | decision | action | probe | margin | risk | review |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `1` | `R2352` | `rna_hybrid` | `selector_blocked_manual_review` | `do_not_freeze_model1_external_only` | `probe_fail_model1_displaced` | `-0.23587` | `critical_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/01_rna_hybrid_r2352/SELECTOR_OVERLAY.md` |
| `2` | `H2312` | `protein_complex` | `selector_hold_interface_review` | `keep_model1_hold_until_interface_review` | `probe_pass_model1_retained` | `0.10755` | `critical_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/02_protein_complex_h2312/SELECTOR_OVERLAY.md` |
| `3` | `H1311` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/03_protein_complex_h1311/SELECTOR_OVERLAY.md` |
| `4` | `H2319` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/04_protein_complex_h2319/SELECTOR_OVERLAY.md` |
| `5` | `H2321` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/05_protein_complex_h2321/SELECTOR_OVERLAY.md` |
| `6` | `H2324` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/06_protein_complex_h2324/SELECTOR_OVERLAY.md` |
| `7` | `H2335` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/07_protein_complex_h2335/SELECTOR_OVERLAY.md` |
| `8` | `H2338` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/08_protein_complex_h2338/SELECTOR_OVERLAY.md` |
| `9` | `H2339` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/09_protein_complex_h2339/SELECTOR_OVERLAY.md` |
| `10` | `R2341` | `rna_hybrid` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/10_rna_hybrid_r2341/SELECTOR_OVERLAY.md` |
| `11` | `R2345` | `rna_hybrid` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `watch_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/11_rna_hybrid_r2345/SELECTOR_OVERLAY.md` |
| `12` | `R2351` | `rna_hybrid` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `high_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/12_rna_hybrid_r2351/SELECTOR_OVERLAY.md` |
| `13` | `T2313` | `protein_complex` | `selector_probe_required` | `run_targeted_no_native_probe_before_freeze` | `-` | `-` | `watch_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/13_protein_complex_t2313/SELECTOR_OVERLAY.md` |
| `14` | `R2350` | `rna_hybrid` | `baseline_calibrated_freeze_ready` | `carry_model1_as_external_only_freeze_ready` | `probe_pass_model1_retained` | `0.64247` | `critical_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/14_rna_hybrid_r2350/SELECTOR_OVERLAY.md` |
| `15` | `R2353` | `rna_hybrid` | `baseline_calibrated_freeze_ready` | `carry_model1_as_external_only_freeze_ready` | `probe_pass_model1_retained` | `0.78355` | `critical_model1_margin` | `casp17/massivefold_model1_combined_selector_overlay/15_rna_hybrid_r2353/SELECTOR_OVERLAY.md` |

## Claim Boundary

CASP17 MassiveFold model1 combined selector overlay only. It applies a baseline-calibrated no-native model-selection policy to external MassiveFold model1/top5 ledgers. It is not native accuracy, internal prediction proof, a CASP submission, or permission to submit without operator approval.
