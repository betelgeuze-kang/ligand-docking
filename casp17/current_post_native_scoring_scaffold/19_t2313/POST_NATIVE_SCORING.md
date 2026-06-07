# T2313 Current Post-Native Scoring Scaffold

- status: `post_native_scoring_scaffold_ready_native_pending`
- target class: `monomer_or_homomer`
- candidate_pdb: `runs/casp17_predictions_sidechain_repacked_current/T2313TS.pdb`
- candidate_sha256: `0d39c9f8f772fc5b4311c54da8dd08aee4212a432170845c7ed6fd7e37ef7d8a`
- escrow_md: `casp17/current_prospective_strict_blind_escrow/t2313/ESCROW.md`
- timestamp_packet_status: `ready_for_external_timestamp`
- native_status: `official_native_release_pending`
- native_dropzone_dir: `casp17/current_post_native_scoring_scaffold/19_t2313/native_dropzone`
- metric rows: `6`
- blockers: `official_native_release_pending,native_file_missing`

## Metric Rows

| metric | family | status | expected output |
| --- | --- | --- | --- |
| `GDT_TS` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/gdt_ts/metric_result.json` |
| `lDDT` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/lddt/metric_result.json` |
| `TM-score` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/tm_score/metric_result.json` |
| `RMSD` | `geometry` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/rmsd/metric_result.json` |
| `GDT_HA` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/gdt_ha/metric_result.json` |
| `MolProbity` | `model_quality` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/19_t2313/metrics/molprobity/metric_result.json` |

## Claim Boundary

CASP17 current post-native scoring scaffold only. It lays out native dropzones, chain-mapping templates, and expected metric-output rows for current escrow candidates after official native release. It does not fetch native structures, compute native accuracy, use post-release information for prediction, submit to CASP, or mark strict-blind competitive proof.
