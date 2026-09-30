# PR59 common-frame computational preparation

PR59 now has a reproducible computational initial pose in the same 7XTB
receptor frame as PR49. Both registered inputs pass the original five geometry
conditions. The new PR59 graph, original decimal charge representation and
parameter/cross metadata also pass component checks. These results describe a
development input; assay microstate and receptor-state equivalence remain
unverified. No roles, admission, FIT rows, affinity labels or pose recovery
claims were added.

The [evidence index](../evidence/pr59_common_frame_development_v1.json) binds
the original sources, final input, second regeneration, full attempted-pose
histories, checks, source code and runtime context. Original SDF/GRO/XML and
every earlier PR49 artifact remain unchanged. Preparation ran from committed
context `fb62c4694` with the new tool still uncommitted; its archived source
hash records the implementation actually used.

The receptor is the exact source-mapped chemical canonical artifact used by
the aromatic-annotated PR49 request. All 2,124 observed receptor heavy atoms
still map once to model 1, label asym E, with exact source coordinates. The
2,249 generated hydrogens and three modeled heavy atoms retain that provenance.
The pocket is the centroid of the same 13 public 7XTB SRO501 heavy source atoms,
at (84.56507692307693, 110.49638461538461, 82.02238461538461) Å. SRO supplies
an anchor and a separate geometry control; it is not an observed PR59 pose.

The exact retained PR49 protocol is reused without weakening thresholds:
24 proper signed permutation orientations, the fixed offset grid and ordering,
then the same geometry-deficit differential-evolution fallback with seed
20260929 and fixed maximum budget. The first printed-coordinate pass is selected
without evaluating energy, force or assay data. Final PR59 preparation records
13,911 attempted poses and a proper rigid transform; maximum intraligand pair
distance drift after 0.0001 Å coordinate quantization is 0.0001141241 Å.

| Initial registered pose | Minimum all / heavy distance (Å) | Minimum all / heavy radius-sum ratio | Maximum heavy anchor radius (Å) |
| --- | ---: | ---: | ---: |
| PR49 | 1.52905 / 2.52937 | 0.60652 / 0.74393 | 6.87319 |
| PR59 | 1.44966 / 2.56184 | 0.60402 / 0.79560 | 8.41959 |
| Unchanged conditions | at least 1 / 2 | at least 0.60 / 0.72 | at most 10 |

PR59 has 43 atoms, 26 heavy atoms, 46 integer-order bonds and 17 generated
hydrogens. Every atom index, element, formal charge, isotope, explicit SDF
stereo field, bond order, hydrogen parent and CSV/GRO name alias is checked.
Sanitized source perception supplies 16 atom and 17 bond aromatic flags while
retaining the integer Kekule representation. The cleaned full graph and final
3D stereo identity match the original declared neutral computational graph.
The original XML charge tokens sum to 1.48e-16 e, within their 3.211e-15 e
print-resolution bound relative to formal total zero. This checks the source
representation and does not establish the assayed protonation or tautomer.

The original OpenFF221 XML retains its 17 constraints and is actually rejected
with `constrained_bond_terms_missing`. The separate declared unconstrained
model follows the same legitimate PR49 policy: regenerate with the pinned
OpenFF221 force field and its Constraints handler deregistered, reusing the
original serialized NAGL predicted charges. Its 46 harmonic bonds include
exactly the 17 original constrained pairs in addition to the 29 retained bonds.
Particle masses and every other serialized force block remain exact.
This is a distinct computational model; constrained dynamics equivalence is
not asserted. The strict converter translates every supported term and rejects
unsupported forces, virtual sites, offsets or semantics instead of dropping them.

The request retains PR49's receptor, pocket, frame, solver and all non-ligand
settings. Its cross file retains the same receptor atom rows and formula;
only the ligand topology and base-parameter bindings change. The fixed-receptor
cross model remains Lorentz–Berthelot LJ plus Coulomb with dielectric 4 and
quintic switching from 10 to 12 Å, without solvent. Ligand NoCutoff arithmetic
is represented only in the declared domain where every intraligand distance
stays below 90 Å at every evaluation. These assumptions are computational
declarations, not evidence of binding affinity or biological validity.

A second fresh execution in the retained PR49 preparation runtime reproduces
all 13,911 attempts, the rigid transform, SDF/GRO, unconstrained XML/offxml,
parameters/extensions/cross, correspondence and coordinate/topology payload.
Canonical source-path provenance changes with the new output location.
The versions match PR49: Python 3.11.16, NumPy 2.4.6, SciPy 1.17.1 and RDKit
2026.03.6. A separately retained preliminary system-Python geometry probe used
older versions and found 17,972 attempts; it was not used as the final model.
This records version-bound reproducibility and does not claim determinism
across library versions.

Ten actual-source checks verify original pins and both manifests, regeneration,
common settings and rejection of the original constrained model, unknown force,
changed charge block, wrong atom-name alias, wrong hydrogen parent and existing
output. Focused tests pass 25 cases plus three subtests: 18 new constraint-model
boundaries and seven retained geometry cases. Ruff and diff checks pass. All
36 v1.2/v1.3 solver source files remain unchanged. This preparation makes zero
force, score or fit calls; independent same-math numerics and any later native
development comparison have separate receipts and outcomes.

The final preparation took 16.65125 s, including its 7.84169 s geometry search.
The separate earlier geometry probe took 10.90565 s. The regeneration total is
bound in the evidence index. These are separate local scopes; the nested
geometry time must not be added to preparation again. They exclude source
development, independent numerical checks, fitting and installed execution.

Reproduce using the existing pinned external environment and a new output
directory; existing packets are never overwritten:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. OPENMM_CPU_THREADS=1 \
  /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-openff-runtime-y2epeamt/env/bin/python \
  tools/analysis/prepare_pr59_common_frame_development.py --output /absolute/new/output
```

The prior v4 geometry diagnostic deliberately leaves `pair_readiness=false`:
its geometry pass grants no native FIT admission. This preparation also leaves
scientific qualification, assayed/prepared-state equivalence, observed PR59
pose recovery, HIP parity and service readiness unverified. A separate
development comparison can report computation under its own explicit contract.
