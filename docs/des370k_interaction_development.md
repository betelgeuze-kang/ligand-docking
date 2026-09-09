# Native quantum interaction residual development

The first native experiment does **not** support promoting its fitted model.
It connects public, computed dimer interaction energies to the existing V2
cross evaluator and an energy-only shadow Ridge model. It does not estimate
experimental Ki/Kd/IC50, run protein-ligand docking, train quantum forces, or
change BioDiscovery ranking. The force-field core is unchanged.

## Source and evaluated state

- Original study: [Donchev et al., Scientific Data (2021)](https://doi.org/10.1038/s41597-021-00833-x).
- [Original Figshare collection](https://doi.org/10.6084/m9.figshare.c.5070644):
  CSV MD5 `de78d5478ece522bb6c71631c7082374`, 293,432,674 bytes.
- [Zenodo companion-MOL distribution](https://zenodo.org/records/5676266):
  archive SHA256 `34e36d0a6a19e67b51d17e466dc2cd98200101e4f42768c23f8c774edb94f5a0`,
  published MD5 `b2b2bf8bc0dd436cfc1ab159d86421fd`, 262,493,084 bytes.
  Its CSV matches the original Figshare checksum exactly.
- The original Figshare metadata/license says CC0; the Zenodo record says
  CC-BY-4.0 and includes the DESRES data license notice. The downloaded original
  notices and record metadata are retained together. This development execution
  does not assert that a customer's redistribution obligations were reviewed.

The target is `cbs_CCSD(T)_all`, the published composite CCSD(T)/CBS,
counterpoise-corrected gas-phase dimer **interaction** energy in kcal/mol.
`nn_CCSD(T)_all` is an AI prediction and is never used as a reference.
The source contains neither atomic partial charges nor per-atom quantum forces.
No experimental binding endpoint or total SPICE energy is substituted for this
interaction-energy target.

`des370k_interaction.py` retains source CSV coordinates and atom order, verifies
the companion MOL elements, monomer boundaries, explicit hydrogen atoms,
bonding and stereochemical SMILES agreement, and constructs existing canonical
V2 `AllAtomSystem` inputs. The 0.000051 Å MOL/CSV comparison tolerance accounts
only for MOL's four-decimal coordinate representation; CSV coordinates are
evaluated unchanged. The repackaged MOL files emit RDKit's 2D-tag/3D-coordinate
diagnostic; raw logs retain it and no coordinates are synthesized to resolve it.

The mandatory development parameter profile is
`v2_lb_lj_uff_atomic_values_gasteiger12_neutral_chno_v1`. It uses explicit
Gasteiger-Marsili graph charge assignment (12 iterations, parameter failure
raises), RDKit UFF **atomic** LJ values, and the existing V2 Lorentz-Berthelot
mixing rule. It is **not** UFF energy, OPLS, measured charges, or a validated
protein force field. It never replaces receptor charges in another route.
Missing atom parameters, hydrogen positions, protonation, bonds, or unsupported
chemistry cause rejection. There is no zero fill, preparation minimization,
external energy solver, or hydrogen-coordinate generation in this consumer.

The unchanged `v2_cross_interaction.evaluate_prepared_cross_interaction` owns
cross LJ/Coulomb energies and atom forces. The model uses a 20 Å cutoff,
18 Å switch start, dielectric 1, no screening and no periodic boundaries.
Internal energy, strain, solvation, affinity and quantum-force residuals remain
unevaluated. The explicit fragment envelope is not a protein pocket.

## Offline consumer and evidence ordering

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
CUDA_VISIBLE_DEVICES='' HIP_VISIBLE_DEVICES='' ROCR_VISIBLE_DEVICES='' \
python -m tools.product.run_des370k_residual_development \
  --archive /absolute/path/DES370K.zip --out /absolute/path/new-result-directory
```

The output directory must not already exist. The consumer verifies the pinned
archive, writes its plan, selects from geometry/identity metadata, scores native
coordinates, extracts only admitted fit labels, fits once, writes checkpoint
and all predictions, records their hashes, then extracts calibration/development
labels. The downloaded archive contains the labels throughout: this is an
auditable development access order, not a sealed external holdout or approval.
Original selected source rows, assigned roles, coordinates, atom parameters,
canonical states, individual forces, failure reasons and costs are retained.

The plan limits each monomer to neutral CHNO, 5–12 heavy atoms and at most 64
total atoms with explicit native hydrogens. Monomer connectivity identities,
with stereoisomers grouped, are hash-partitioned 60/20/20 into fit/calibration/
development. Cross-partition pairs are withheld; this is not scaffold or
tautomer-independent validation. Eight systems per role and twelve geometries
per system are selected by fixed metadata hashes, without energy or success
filtering. Duplicate geometry IDs reject **every** matching row.

`des370k_residual.py` uses 60 element-pair radial features plus the two baseline
energy components, with fit-only normalization and Ridge alpha=10. Features
become available after native-coordinate preparation and V2 evaluation; this
is not a pre-docking cheap selector. IDs/roles/labels are not interaction features.
The checkpoint has a distinct quantity/schema, source/runtime and plan hashes;
it cannot substitute for PR #512's score-proxy checkpoint or the experimental
Ki selector. Existing checkpoints are not migrated or relabeled.

All predictions remain shadow diagnostics. Maximum absolute standardized
feature value above 10 triggers a predeclared abstention; this is an incomplete,
uncalibrated domain diagnostic, not a probability or accuracy guarantee. The
baseline stays unchanged. Calibration rows are evaluated separately but no
uncertainty calibration or hyperparameter tuning is performed.

## First native result, 2026-09-09

The full source contains 370,959 rows / 3,691 dimer systems / 392 source SMILES.
All rows remain in `all-source-row-outcomes.jsonl`:

| Outcome | Rows |
|---|---:|
| Outside the predeclared monomer size range | 305,345 |
| Outside neutral CHNO chemistry | 41,336 |
| Monomers assigned to different partitions | 2,888 |
| System computation cap | 16,362 |
| Geometry computation cap | 4,740 |
| Selected and actually scored | 288 |

There were 96 requested/scored rows in each partition, with zero preparation
or numerical failures. Selected monomer identities numbered 7 fit, 7 calibration,
6 development, with zero overlap between partitions. These are only eight
dimer systems per partition; 96 correlated geometries are not 96 independent
chemical systems.

| Partition | AI-supported/requested | Baseline MAE, same supported rows | Shadow MAE, same supported rows |
|---|---:|---:|---:|
| Fit | 96/96 | 275.671 | 66.491 |
| Calibration | 71/96 | 110.734 | 241.338 |
| Development | 83/96 | 206.821 | 228.535 |

MAE units are kcal/mol. Calibration had 25 abstentions and development 13.
Across **all** 96 development rows, including OOD diagnostics, baseline/raw
shadow MAE was 1070.328/729.199; that aggregate reduction does not establish
quality at the supported coverage. Calibration all-row MAE worsened from
130.204 to 1045.011. No AI quality superiority is claimed.

Post hoc diagnosis, not a new admission rule: reference interaction energies
range roughly -12 to +47 kcal/mol, while the approximate baseline reaches
43,694 kcal/mol on compressed contacts. On the 77 attractive-reference
development geometries, baseline/raw-shadow MAE was 37.865/386.089. Native
dimer minimum-energy recovery was 1/8 systems for both baseline and raw shadow;
this is not symmetry-aware docking pose or active-ligand recovery. Improving the
declared physical baseline and chemical coverage is a higher priority than
scaling this fitted model or tuning against these exposed development results.

The actual 96-row fit took 0.0030 s wall/CPU; feature generation plus 288 shadow
predictions took 0.2635 s wall/CPU. The complete fresh process took 32.962 s wall;
the instrumented consumer portion took 30.401 s wall / 30.389 s CPU, peak RSS
991,040 KiB. Its 288 individual native bridges totaled 8.269 s wall, p50 0.0292 s,
p95 0.0348 s. Imports, archive scans, scoring, fitting, inference and reporting
have distinct scopes. These are one sequential CPU run, not an engine speedup,
cache/batch A/B, repeated cold/warm benchmark, GPU result or end-to-end screen.

The fixed checkpoint identity is
`be506a90743418ffe3a6205bafa14bdb3ae110ce6834aaba902a2fb6cd3e17e7`;
its serialized file SHA256 is
`38c11c6cb415539c5b2e25006ae7e770219043c76aafb47ee81ca01458c3b4f8`.
The frozen prediction file SHA256 is
`a8e78fa2c5112f46ae16a51cf0429756a885909557a9e2e512a1754c37ef1eb1`.

## Verification and remaining product gates

The first local regression executed 460 tests, zero failures/errors/skips,
including native-schema synthetic controls, real V2 invariance and scalar
formula controls, duplicate/evaluation admission rejection, and existing
prepared-state/CLI regressions. Early test-development runs retained a fixture
import error and an insufficiently out-of-domain test fixture; these were fixed
without relaxing the production threshold or existing guards.

A separately written scalar audit checked all 288 native energies/atomic
forces: maximum absolute differences 9.095e-12 kcal/mol and 5.821e-11
kcal/mol/Å. An independent dual Ridge solution reproduced the 96-row fit and
all 288 predictions to 5.276e-10 kcal/mol. This verifies implementation at the
same approximate model; it does not validate the parameter model or quantum
forces. Raw logs, JUnit, commands, dependency versions, source hashes and
individual comparisons are retained in the accompanying local evidence bundle.

A separate fresh process, using a copied source/input directory, recomputed all
288 native coordinates and shadow predictions with network, fitting, original
evidence paths, training records and evaluation-reference files blocked. Its
prediction JSON was byte-identical to the frozen file above (exit 0, one actual
consumer JUnit case, zero failures/skips). The first replay harness attempt
failed on decoding a byte-string temporary-file path during SciPy import;
the corrected harness retained all access restrictions. No model was refitted.

Actual public experimental Ki learning, experimental assay provenance and the
existing product selector remain separate work. This fragment experiment does
not close protein/receptor preparation, chemically matched experimental
structure joins, active-candidate recovery, calibrated uncertainty, validated
dynamics, or customer execution. Public data acquisition and local development
training were authorized; scientific validation and customer release remain
ungranted. No external reviewer, signature or approval receipt is implied.
