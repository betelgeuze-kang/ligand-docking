# PoseBusters runner integration and stage diagnosis

This development experiment connects the prepared-receptor evaluator to the
actual Engine V2 runner, evaluates an exact subset-construction optimization,
and measures retained intermediate-stage RMSDs. It uses the sealed development
evidence from Actions run `41697499611` and its retained molecular runtime.

## Evaluation strategies

`PoseBustersEvaluatorContext` owns one case and one explicit strategy:

| Mode | Receptor categories | Pose-dependent distance subset |
| --- | --- | --- |
| `reference` | Original PoseBusters implementation | Original helper |
| `prepared_receptor` | Reused immutable category prototypes | Original helper |
| `prepared_subset` | Reused immutable category prototypes | Exact retained-atom and retained-bond copying, with explicit original-helper fallback |

The runner accepts an optional `evaluation_context`. Its default is `None`.
Existing CLI commands do not select the experimental strategy automatically.
The strategy identity binds its mode and implementation source files. The
context checks case and input identity before result-cache access, does not
clear the molecular energy LRU, and preserves the candidate-to-Top5 cache.
Volume callbacks belong to the evaluator instance; the global PoseBusters
registry is not patched.

The subset fast path applies only to admitted ordinary molecular objects and
boolean masks. It copies retained atoms and bonds in their original order,
preserving endpoint orientation, native typed properties, atom/PDB metadata,
conformer identity, and double-precision coordinates using RDKit operations.
It does not sanitize or update molecular property caches. Persistent molecule
or conformer properties, queries, unsupported chirality, bond stereo references,
and stereo/substance groups use the source-pinned original helper. Unexpected
fast-path errors propagate. The experiment records bonded and bondless
applications, fallback reasons, and source/retained/removed atom and bond counts.
The two pilot cases must exercise the bonded fast path with retained bonds.

Frozen molecular tests compare complete native binaries using
`AllProps | CoordsAsDouble`, including chirality, ring cuts, cached hydrogen
counts, typed properties, multiple conformers, and precise coordinates.
`tools/check_posebusters_subset_inputs.py` additionally audits every actual
distance mask for the two retained pilot Top5 sets against the original helper
and compares their complete reports. This deliberately duplicated audit is an
equivalence check; its execution times are not an independent speed benchmark.
The input bundle's preparation source and the currently executing source are
recorded separately when a later candidate checks an earlier immutable bundle.

## Fixed scientific scope

The cohort contains 32 development cases, original indices 2 through 33.
The two admission-smoke cases are excluded. Twenty-nine cases have 64 retained
candidates each: 1,856 final candidate records and 145 Top5 records. Three
preparation failures remain in the 32-case denominator and contribute no
fabricated poses. Preparation verifies sealed artifact inventories, input
hashes, coordinate lineage, and exact reconstructed SDF bytes.

The experiment has three parts:

1. **Runner replay:** evaluate each of the 29 saved Top5 sets under all three
   strategies. A repeated call checks reuse of the five cached outcomes.
2. **Complete docking:** regenerate candidates and run the actual search,
   refinement, evaluation, and selection pipeline for `6T88_MWQ` and
   `6YSP_PAL`, under each strategy in a fresh supervised process.
3. **Stage diagnosis:** measure `proposal_generated`, `post_v6`,
   `post_v7_optimization`, and `refinement_selected` coordinates from the
   original journals. These are 7,424 observations. Reuse is restricted to
   exactly identical coordinates inside the same case. The 1,856 selected
   records must match both original SDF hashes and historical RMSD binary64
   values before intermediate-stage conclusions are admitted.

The pilot uses the two complete-docking cases. The remaining 27 replay cases
are split into five shards. Stage diagnosis covers all 29 successful cases in
five independent shards. Missing, duplicate, corrupted, or failed results do
not reduce the required denominator.

## Admission and comparison

All strategies must match every ordered full-report cell, scalar type,
binary64 value, missing-value representation, dtype, and column. They must
also match historical RMSDs, chemical/geometric validity, failed-check IDs,
and retained pose bytes. No numerical tolerance is introduced.

Complete docking preserves the full scientific result projection, including
scores, score terms, refinement receipts, coordinate fingerprints, pose
hashes, RMSDs, and validity. Only these execution-specific paths are excluded
from historical row equality:

- `/runtime_seconds`
- `/engine_v2_diagnostics/diagnostic_evaluation_seconds`
- `/execution_command`
- `/execution_policy`

Source identity, protocol, prepared-input bundle, original worker argv,
environment snapshots, installed active package payloads, and process
receipts are retained and validated separately. The original runtime uses
Python 3.10.22, RDKit 2022.09.5, and PoseBusters 0.3.1 from retained wheels.
The original venv path is recreated to preserve the installed-payload check.

Complete-docking workers materialize their own verified copies of the four
input roles and honor the public runner's private, read-only directory/file
contract. Downloaded input artifacts are not modified to satisfy that contract.
Input hashes remain checked before, during, and after execution and cleanup.

Workers have explicit limits: 900 seconds for Top5 replay, 1,800 seconds for
new complete-docking measurements, and 600 seconds for stage RMSD measurement.
The original development run used 900 seconds for Engine V2; its limit is
recorded separately from the new experiment. Each new worker has a sampled
process-tree RSS limit of 6 GiB at 0.25-second intervals and an 8 MiB retained
log limit **per stream**. The supervisor records exit, cleanup, sampled RSS,
and any discarded log bytes. It does not claim cgroup containment or an exact
continuous RSS maximum.

## Entry points

`.github/workflows/posebusters_integration.yml` installs the frozen runtime,
runs mandatory molecular and regression tests, prepares and binds both input
artifacts, gates expanded runs on the pilot, and retains final aggregation.

- `python -m tools.run_posebusters_integration prepare --help`
- `python -m tools.run_posebusters_integration run-case --help`
- `python -m tools.run_posebusters_integration run-shard --help`
- `python -m tools.run_posebusters_integration aggregate --help`
- `python -m tools.trace_redocking_stage_rmsd prepare --help`
- `python -m tools.trace_redocking_stage_rmsd run-shard --help`
- `python -m tools.trace_redocking_stage_rmsd aggregate --help`

`tools/analyze_redocking_failures.py` independently classifies the original
development results. Stage RMSD measurement uses the original serialization,
decode, and PoseBusters RMSD policy. Intermediate physical validity is not
measured. A pose that is near-native at an intermediate stage is therefore
not automatically a chemically and geometrically valid docking success.

This experiment changes no search budget, scoring equation, fitted weight,
or success threshold. Performance conclusions require exact scientific
equivalence. Accuracy diagnosis separates observations from causal claims;
it does not establish improved accuracy or held-out generalization.
