# CASP17 MassiveFold RNA Model-Selection Input Packet

- generated: `2026-06-01T21:52:15+09:00`
- status: `massivefold_rna_model_selection_input_packet_ready_external_only`
- targets ready/blocked/total: `6/0/6`
- model1/top5 inputs: `6/30`
- missing artifacts: `0`
- R2345 guard: `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only`
- next action: feed external-only RNA model1/top5 pointers into self-assessment calibration and rerank experiments while preserving R2345 sequence quarantine and no-submission boundaries

## Targets

| target | status | model1/top5 | missing | guard | manifest | blockers |
| --- | --- | --- | --- | --- | --- | --- |
| `R2341` | `ready_external_model_selection_input` | `1/5` | `0` | `-` | `casp17/massivefold_rna_model_selection_inputs/r2341/input_manifest.csv` | `-` |
| `R2345` | `ready_external_model_selection_input` | `1/5` | `0` | `ignore_0930_pacific_invalid_dna_t_request_use_1130_replacement_only` | `casp17/massivefold_rna_model_selection_inputs/r2345/input_manifest.csv` | `-` |
| `R2350` | `ready_external_model_selection_input` | `1/5` | `0` | `-` | `casp17/massivefold_rna_model_selection_inputs/r2350/input_manifest.csv` | `-` |
| `R2351` | `ready_external_model_selection_input` | `1/5` | `0` | `-` | `casp17/massivefold_rna_model_selection_inputs/r2351/input_manifest.csv` | `-` |
| `R2352` | `ready_external_model_selection_input` | `1/5` | `0` | `-` | `casp17/massivefold_rna_model_selection_inputs/r2352/input_manifest.csv` | `-` |
| `R2353` | `ready_external_model_selection_input` | `1/5` | `0` | `-` | `casp17/massivefold_rna_model_selection_inputs/r2353/input_manifest.csv` | `-` |

## Claim Boundary

CASP17 MassiveFold RNA model-selection input packet only. It packages organizer-provided external model1/top5 pointers for accuracy-estimation and reranking experiments. It does not copy model coordinates, submit models, use native structures, or convert external pools into internal competitive-proof evidence.
