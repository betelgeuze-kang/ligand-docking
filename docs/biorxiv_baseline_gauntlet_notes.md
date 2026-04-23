# bioRxiv Baseline Gauntlet Notes

## Scope

- baseline close-out used for comparison: `runs/external_validation_blind_runs/external_validation_blind_runs_2026-03-22_biorxiv_v6r3`
- comparison bundle: `runs/biorxiv_baseline_comparison_current/summary.json`
- compared score columns: `proxy`, `distance_only`, `composite_v2`, `v3`, `v4`, `v6`, `v7`

## Main Readout

- ligand tasks compared: `9`
- current score remained the primary winner in `5/9` tasks
- non-current winners appeared in `4/9` tasks

## Winner-Informed Mapping

- `GPCR core`: keep `binding_score_composite_v7`
- `GPCR expanded OOD`: upgrade from `binding_score_composite_v4` to `binding_score_composite_v7`
- `TRPV1 core`: upgrade from `binding_score_composite_v4` to `binding_score_composite_v7`
- `TRPV1 expanded OOD`: upgrade from `binding_score_composite_v4` to `binding_score_composite_v6`
- `Kinase`: keep `binding_energy_mmpbsa_kcal_mol_proxy`

## Interpretation

The `v6r3` package served as the first reviewer-ready full-pass baseline. The baseline gauntlet did not invalidate it. Instead, it showed that the accepted package still left a small amount of score-selection headroom in ligand tasks, especially for `TRPV1` and `GPCR` expanded OOD. The follow-up candidate spec therefore kept the validated kinase path untouched and only changed the ligand score mappings where the gauntlet showed a clear ranking-layer gain under frozen evaluator inputs. The resulting `v7r1` rerun preserved all set passes and is now the promoted current package.

## Follow-Up Candidate

- candidate spec: `config/external_validation_biorxiv_blind_sets_v7_bestofgauntlet1.json`
- launch helper: `tools/run_biorxiv_external_validation_bestofgauntlet_candidate.py`

## Caveat

The gauntlet is stage5-based. It reuses frozen labels, splits, and bootstraps, but it does not replay every task-level acceptance override. The `v7_bestofgauntlet1` candidate therefore had to be checked end-to-end in the full external-validation pipeline before replacing `v6r3`. That full rerun closed successfully as `2026-03-22_biorxiv_v7r1`.
