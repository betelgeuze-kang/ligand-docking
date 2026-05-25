# Competitive-Floor Batch Row 11: hist_REQUIRED_COMPLEX_001

- target placeholder: `REQUIRED_COMPLEX_001`
- expected scope: `complex`
- metric profile: `TM,interface_F1,DockQ,QSbest,IPS`
- source row folder: `runs/casp17_win_tier_benchmark_input_scaffold_current/row_026_REQUIRED_COMPLEX_001`
- copied row folder: `casp17/competitive_floor_batch_current/priority_011_REQUIRED_COMPLEX_001/row_scaffold`
- metadata template: `casp17/competitive_floor_batch_current/priority_011_REQUIRED_COMPLEX_001/row_metadata_template.csv`
- single-file fill template: `casp17/competitive_floor_batch_current/priority_011_REQUIRED_COMPLEX_001/row_fill_template.csv`
- missing evidence items: `34`
- next action: Replace placeholder target identity and row metadata in runs/casp17_win_tier_benchmark_input_scaffold_current/row_026_REQUIRED_COMPLEX_001 with a cleared historical non-current CASP target.

## Fill Checklist

- Replace placeholder target/benchmark IDs with a cleared historical non-current CASP protein target.
- Copy `row_fill_template.csv` to `row_fill.csv` and fill that one file if you want the fastest path into operator preflight.
- Fill `row_metadata.csv` from the metadata template with the cleared historical benchmark ID, target ID, scope, and split.
- Add the internal prediction PDB generated before native release.
- Add the released historical native PDB only after no-leak provenance review.
- Add all 10 layer-specific internal ablation prediction PDBs.
- Fill no-leak provenance fields, including false confirmations for public/template/native use, other-team model use, post-release information use, and current CASP17 target use.
- Fill selected/best top-5 rank, native metric, and internal score calibration fields.
- Re-run input inventory, operator preflight/import, historical benchmark, model-selection calibration, refinement ablation, and readiness dashboard.

## Claim Boundary

Local competitive-floor batch packet only. It organizes the first no-leak historical benchmark rows to fill; it does not fetch natives, clear provenance, score accuracy, use external predictors, or submit to CASP.
