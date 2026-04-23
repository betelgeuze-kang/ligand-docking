# IDP Kalman Feature/State Smoothing Plan

- status: `literature_anchor_default_mask_ready`
- scope: `feature_state_smoothing_only`
- coordinate_correction: `False`
- ranking_override: `False`
- gate_override: `False`
- default_feature_mask: `rg_sasa_only`

## Next Step

- Adopt rg_sasa_only as the default literature-anchor shadow mask, keep broader full-IDP corrected-path promotion blocked, and use future broader reruns only after provisional-anchor and corrected-path risks are reduced.

## Feature Groups

| group | features |
| --- | --- |
| contact_derived | on_contact_persistence, anchor_contact_persistence, contact_summary_features |
| distance_compactness_derived | mean_min_distance, compactness_score, condensation_score |
| state_branch_posteriors | branch_probabilities, state_probabilities, condition_group_posteriors |
| ensemble_summary | on_rg_mean, on_sasa_proxy_mean, on_ensemble_diversity, on_transient_helicity |

## Promotion Checkpoints

| checkpoint | status | state_changes | gate_changes | recommended_default | coverage |
| --- | --- | ---: | ---: | --- | --- |
| `tau_k18_baseline_replay_ensemble_only` | `pass` | 0 | 0 | `False` |  |
| `tau_k18_baseline_replay_rg_sasa_only` | `pass` | 0 | 0 | `True` |  |
| `literature_anchor_subset_rg_sasa_only` | `pass` | 0 | 0 | `True` | 7/7 |

## Insertion Points

| file | purpose |
| --- | --- |
| `tools/run_idp_3bead_evaluator.py` | Emit feature_state_v1 shadow telemetry after raw feature assembly without touching coordinates. |
| `tools/run_idp_3bead_holdout_pipeline.py` | Pass through feature_state_v1 shadow args into evaluator runs. |
| `runs/cross_family_residual_shadow_layer_current.md` | Report IDP as feature_state_smoothing_only in the global shell. |

## Telemetry

- `kf_applied`
- `kf_feature_count`
- `kf_mean_abs_delta`
- `kf_max_abs_delta`
- `kf_obs_noise_scale`
- `kf_process_noise_scale`
- `kf_shadow_status`
- `would_have_changed_state`
- `would_have_changed_gate`

## Guardrails

- `no_coordinate_correction`
- `no_raw_column_overwrite`
- `no_ranking_override`
- `no_gate_override`
- `kf_prefix_only_for_smoothed_columns`
- `delta_caps_and_disagreement_escalation`
