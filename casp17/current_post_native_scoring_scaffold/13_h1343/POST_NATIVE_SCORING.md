# H1343 Current Post-Native Scoring Scaffold

- status: `post_native_scoring_scaffold_ready_native_pending`
- target class: `protein_heteromer_or_complex`
- candidate_pdb: `runs/casp17_predictions_sidechain_repacked_current/H1343TS.pdb`
- candidate_sha256: `ab34955dc3b6e6ce5a1b17cdc5f9fb5d86dff1d18e90179172756c2ad4dd4587`
- escrow_md: `casp17/current_prospective_strict_blind_escrow/h1343/ESCROW.md`
- timestamp_packet_status: `ready_for_external_timestamp`
- native_status: `official_native_release_pending`
- native_dropzone_dir: `casp17/current_post_native_scoring_scaffold/13_h1343/native_dropzone`
- metric rows: `9`
- blockers: `official_native_release_pending,native_file_missing`

## Metric Rows

| metric | family | status | expected output |
| --- | --- | --- | --- |
| `GDT_TS` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/gdt_ts/metric_result.json` |
| `lDDT` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/lddt/metric_result.json` |
| `TM-score` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/tm_score/metric_result.json` |
| `RMSD` | `geometry` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/rmsd/metric_result.json` |
| `GDT_HA` | `monomer_domain` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/gdt_ha/metric_result.json` |
| `MolProbity` | `model_quality` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/molprobity/metric_result.json` |
| `DockQ` | `complex_interface` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/dockq/metric_result.json` |
| `ICS` | `complex_interface` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/ics/metric_result.json` |
| `IPS` | `complex_interface` | `awaiting_official_native` | `casp17/current_post_native_scoring_scaffold/13_h1343/metrics/ips/metric_result.json` |

## Claim Boundary

CASP17 current post-native scoring scaffold only. It lays out native dropzones, chain-mapping templates, and expected metric-output rows for current escrow candidates after official native release. It does not fetch native structures, compute native accuracy, use post-release information for prediction, submit to CASP, or mark strict-blind competitive proof.
