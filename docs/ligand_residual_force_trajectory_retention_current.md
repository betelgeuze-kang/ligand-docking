# Ligand Residual Force Trajectory Retention

- status: `ligand_residual_force_trajectory_compaction_complete`
- stage2_root: `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames`
- queue_rows: `768`
- manifest_rows: `768`
- current_npz_count: `0`
- current_npz_size_human: `0.00 B`
- delete_recommended_count: `768`
- delete_recommended_size_human: `4.13 GiB`
- retained_top_rank_count: `60`
- preserved_evidence_file_count: `8`
- delete_manifest_json: `runs/ligand_residual_force_trajectory_cleanup_manifest_current.json`
- approval_token_required: `APPROVE_LIGAND_HEAVY_RUN_CLEANUP`
- delete_executed: `True`
- deleted_count: `768`
- deleted_size_human: `4.13 GiB`
- failed_count: `0`
- post_delete_npz_present_count: `0`

## Target Summary

| target | manifest rows | retained size | frames min | frames mean | frames max |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ADRB2_GPCR_BLIND` | `256` | `696.97 MiB` | `66` | `66.5625` | `84` |
| `HIV1_PROTEASE` | `256` | `593.25 MiB` | `66` | `110.15625` | `120` |
| `TRPV1_ION_CHANNEL_BLIND` | `256` | `2.87 GiB` | `66` | `85.125` | `120` |

## Top Retained Records

| target | rank | ligand_id | affinity_hint | quality | frames | generated_npz |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| `ADRB2_GPCR_BLIND` | `1` | `carvedilol` | `0.7181873626373626` | `0.0` | `84` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0001_carvedilol.npz` |
| `ADRB2_GPCR_BLIND` | `2` | `carazolol` | `0.5387810989010988` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0032_carazolol.npz` |
| `ADRB2_GPCR_BLIND` | `3` | `timolol` | `0.5098291648351648` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0035_timolol.npz` |
| `ADRB2_GPCR_BLIND` | `4` | `alprenolol` | `0.49180873626373617` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_norelax_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0037_alprenolol.npz` |
| `ADRB2_GPCR_BLIND` | `5` | `decoy_ADRB2_GPCR_BLIND_00002` | `0.4757669329670331` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0039_decoy_adrb2_gpcr_blind_00002.npz` |
| `ADRB2_GPCR_BLIND` | `6` | `propranolol` | `0.4684171208791208` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0034_propranolol.npz` |
| `ADRB2_GPCR_BLIND` | `7` | `decoy_ADRB2_GPCR_BLIND_00020` | `0.4404131494505496` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0057_decoy_adrb2_gpcr_blind_00020.npz` |
| `ADRB2_GPCR_BLIND` | `8` | `decoy_ADRB2_GPCR_BLIND_00014` | `0.4096580901098901` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0051_decoy_adrb2_gpcr_blind_00014.npz` |
| `ADRB2_GPCR_BLIND` | `9` | `pindolol` | `0.40680202197802195` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0036_pindolol.npz` |
| `ADRB2_GPCR_BLIND` | `10` | `decoy_ADRB2_GPCR_BLIND_00013` | `0.4009589681318681` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0018_decoy_adrb2_gpcr_blind_00013.npz` |
| `ADRB2_GPCR_BLIND` | `11` | `decoy_ADRB2_GPCR_BLIND_00010` | `0.3845155758241758` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0047_decoy_adrb2_gpcr_blind_00010.npz` |
| `ADRB2_GPCR_BLIND` | `12` | `decoy_ADRB2_GPCR_BLIND_00022` | `0.3596844725274726` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0059_decoy_adrb2_gpcr_blind_00022.npz` |
| `ADRB2_GPCR_BLIND` | `13` | `decoy_ADRB2_GPCR_BLIND_00021` | `0.3535743263736264` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0026_decoy_adrb2_gpcr_blind_00021.npz` |
| `ADRB2_GPCR_BLIND` | `14` | `decoy_ADRB2_GPCR_BLIND_00006` | `0.3534428681318681` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0043_decoy_adrb2_gpcr_blind_00006.npz` |
| `ADRB2_GPCR_BLIND` | `15` | `decoy_ADRB2_GPCR_BLIND_00011` | `0.3512273472527474` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0016_decoy_adrb2_gpcr_blind_00011.npz` |
| `ADRB2_GPCR_BLIND` | `16` | `decoy_ADRB2_GPCR_BLIND_00018` | `0.3472895186813187` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_norelax_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0023_decoy_adrb2_gpcr_blind_00018.npz` |
| `ADRB2_GPCR_BLIND` | `17` | `decoy_ADRB2_GPCR_BLIND_00017` | `0.3466462989010989` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_norelax_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0022_decoy_adrb2_gpcr_blind_00017.npz` |
| `ADRB2_GPCR_BLIND` | `18` | `decoy_ADRB2_GPCR_BLIND_00003` | `0.34101533296703296` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_norelax_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0008_decoy_adrb2_gpcr_blind_00003.npz` |
| `ADRB2_GPCR_BLIND` | `19` | `decoy_ADRB2_GPCR_BLIND_00001` | `0.3260607285714285` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0038_decoy_adrb2_gpcr_blind_00001.npz` |
| `ADRB2_GPCR_BLIND` | `20` | `decoy_ADRB2_GPCR_BLIND_00008` | `0.3252045593406593` | `0.0` | `66` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_gpcr_smoke_p0_n64_r1__adrb2_gpcr_blind_rep0013_decoy_adrb2_gpcr_blind_00008.npz` |
| `HIV1_PROTEASE` | `1` | `hiv_lopinavir_posaug_00042` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0044_hiv_lopinavir_posaug_00042.npz` |
| `HIV1_PROTEASE` | `2` | `hiv_lopinavir` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0002_hiv_lopinavir.npz` |
| `HIV1_PROTEASE` | `3` | `hiv_lopinavir_posaug_00027` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0029_hiv_lopinavir_posaug_00027.npz` |
| `HIV1_PROTEASE` | `4` | `hiv_lopinavir_posaug_00030` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0032_hiv_lopinavir_posaug_00030.npz` |
| `HIV1_PROTEASE` | `5` | `hiv_lopinavir_posaug_00033` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0035_hiv_lopinavir_posaug_00033.npz` |
| `HIV1_PROTEASE` | `6` | `hiv_lopinavir_posaug_00015` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0017_hiv_lopinavir_posaug_00015.npz` |
| `HIV1_PROTEASE` | `7` | `hiv_lopinavir_posaug_00003` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_norelax_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0005_hiv_lopinavir_posaug_00003.npz` |
| `HIV1_PROTEASE` | `8` | `hiv_lopinavir_posaug_00036` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_enum_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0038_hiv_lopinavir_posaug_00036.npz` |
| `HIV1_PROTEASE` | `9` | `hiv_lopinavir_posaug_00006` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_ligandonly_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0063_hiv_lopinavir_posaug_00006.npz` |
| `HIV1_PROTEASE` | `10` | `hiv_lopinavir_posaug_00018` | `0.9731318681318681` | `0.0` | `120` | `runs/residual_force_trajectory_regeneration_current/stage2_trajectory_frames/shard_00000/external_validation_2026_05_11_scaleup_1m_pilot_v1_gpu_set3_operational_smoke_kinase_smoke_p50_n64_r1__hiv1_protease_rep0020_hiv_lopinavir_posaug_00018.npz` |

## Claim Boundary

Ligand residual-force trajectory retention records compact target/ranking evidence for the regenerated NPZ bundles, then prepares an approval-gated manifest for deleting raw stage2 trajectory NPZ files. It does not change scientific claims, delete retained queue/summary/manifest evidence, touch git history, upload, push, run docking, or train models.
