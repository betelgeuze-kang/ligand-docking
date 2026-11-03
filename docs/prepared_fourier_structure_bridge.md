# Opt-in prepared Fourier / fixed-receptor structure bridge

## Explicit dependency, not an independent-main patch

This patch is a child of draft PR #615 (and its #614 structure-preserving core),
using current main `cpu_refinement_fourier_v1` evaluation and parameter modules.
It changes only the opt-in product provider; no protected engine source,
registration, default lane, preparation helper, solver, or runtime gate changes.
PR #617 preparation/export is a separate upstream dependency for genuine prepared
ligand artifacts, not an import into this bridge. Source identities must be frozen
again if any parent changes.

## Existing execution path

`FourierParameters.from_dict` + `FourierCrossParameters.from_dict`
→ `FixedReceptorEnergyForceProvider(authority, ligand, receptor, parameters, cross, ...)`
→ existing `FourierFixedEvaluator(parameters, FourierEnvironment(receptor, cross))`
→ existing `FourierInternalEvaluator` and fixed-receptor cross arithmetic
→ existing `StructurePreservingPoseRefiner` / `FixedReceptorStructureCoordinator`.

Only an exact matching Fourier parameter/cross pair or the existing exact legacy
pair is accepted. Mixed profiles are rejected. Data must already contain complete
ordered atom rows and genuine preparation provenance. The bridge performs no
parameterization, chemistry repair, charge assignment, native preparation import,
or defaulting of unavailable receptor parameters.

Bindings retain authority receipt/problem, exact original systems/topology,
receptor coordinate frame, cross parameter source and policy, evaluator/model,
implementation-source digest, graph bounds and evaluation budget. Hashes are
cross-wiring checks, not credentials or scientific qualification.

Input coordinates are angstrom; total energy is kcal/mol; raw unprojected ligand
forces are kcal/mol/angstrom. The producer's actual Fourier energy descriptor and
inherited `negative_coordinate_gradient_of_reference_force_field_energy` force
descriptor are retained verbatim in observations. The existing callback envelope
separately promises `negative_coordinate_gradient`; this is an adapter contract,
not a producer metadata rewrite. Synthetic finite differences check the composed
total force sign. Fourier has no explicit distance constraints; empty observations
mean only that none are declared, not chemical validity.

Output keeps ligand internal, cross Lennard–Jones, cross screened Coulomb and total
components. The coordinator retains endpoint observations and final-only internal
strain admission; projected stationarity is not Cartesian convergence. Every admitted
callback has success/failure/recoverable status and admitted/graph/physical-call
counter deltas; ledger length cannot exceed the admitted-call budget. Zero-work
binding/capacity denials are counted without allocating rows. Total callback
attempts = admitted attempts + preflight denials. History is in-memory,
synchronous, single-worker. Recovery is
only a valid model's geometric distance singularity, never incomplete parameters.

## Verification and scientific boundary

Local affected scope: **108 unique tests passed, 1 explicitly deselected**:
28 legacy fixed-provider,5 new Fourier-provider,32 generic structure-refiner and
43 pure-core tests. The deselected case is
`test_legacy_engine_import_does_not_load_opt_in_product_extensions`, whose child
process is forbidden by the local supervisor. It remains in the full hosted
workflow with no deselection. Earlier focused runs are repeated coverage, not
additional unique tests. Existing synthetic fixtures are unchanged.

The local one-thread CPU profile uses an existing environment and bounds address
space to2GiB, CPU120s, wall180s, output2MiB, file8MiB and FD64. No external chemistry
solver imports or child spawning are allowed. These are process limits, not a hard
process-tree RSS or escaped-descendant guarantee. The hosted workflow adds the
Fourier path/test triggers without removing existing boundary or import tests.

A separately reviewed research diagnostic used one frozen independent upstream
PoseBusters `6YQW_82I` start: identity rotation and heavy-centroid translation only.
The raw receptor's821 heavy atoms remain unchanged; the separately authorized
prepared copy has1 OXT and828 H additions,1650 atoms across101 observed residues.
Missing residues17–21 were not rebuilt. Receptor protonation/terminus choices and
all raw/prepared source hashes remain explicit in the separate evidence packet.
Crystal coordinates supplied only a declared pocket centroid; no reference
orientation, torsions, atomwise distances or ranking hints entered the evaluator.
The owning pocket is an explicit12Å sphere, not a claimed box implementation.

Exactly one combined own-engine E/F callback returned finite19×3 forces; no
optimizer, alternate start or retry ran. Total energy was771,979,086.2868018
kcal/mol, dominated by cross LJ771,979,028.9134226kcal/mol. This initial pose has a
**0.464151Å severe clash and is not a valid docking pose**. The unchanged0.35Å
floor is the existing ligand numerical applicability floor, not physical clash
validity and not a threshold lowered to admit this example.

A separate stdlib-only post-hoc scalar audit of the **same point** reproduced the
cross LJ sum exactly in Å/kcal and Coulomb within9e−14kcal/mol. Direct raw nm/kJ
arithmetic agreed to~6.5e−15 relative for LJ. All19 ligand XML parameter conversions
and1650 receptor raw-row conversions matched. The dominant ligand H/TYR106 CE1
contact accounts for~99.9784% of cross LJ. This rules out the tested row/unit
assembly discrepancy at this point, not forcefield suitability or general accuracy.

The diagnostic is not a new product execution approval, another independent case,
or evidence of docking success, mature-protein fidelity, potency, throughput,
production readiness or generalization. No calibration/scientific flag was
promoted. Further real refinement requires a separately frozen and released plan.
THRB HOLD and all existing admission boundaries remain unchanged.
