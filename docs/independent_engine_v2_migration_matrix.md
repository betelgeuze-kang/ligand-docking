# Independent Engine v2 Migration Matrix

Status: migration contract; no deletion or release promotion is authorized by
this document.

## 1. Disposition vocabulary

- **Reuse:** move behind a v2-owned interface after focused validation.
- **Adapt:** preserve a legacy implementation temporarily through an explicit,
  provenance-labelled adapter; it is not a native v2 scientific result.
- **Replace:** retain tests or reference behavior while implementing a new v2
  component from first principles.
- **Archive:** exclude from every v2 product and scientific-claim path. Files
  remain available for reproducibility until a separately reviewed deletion.

No legacy code becomes scientifically valid merely because it is imported by
v2. Each row's exit gate must be satisfied independently.

## 2. Source-to-v2 matrix

| Existing path or area | Disposition | v2 destination | Required treatment and exit gate |
| --- | --- | --- | --- |
| `betelgeuze_engine/contracts/{state,result,claim}.py` | Reuse/adapt | `betelgeuze_engine_v2/contracts/` | Preserve claim/provenance semantics; use typed/frozen schema shells and unit validation. Tensor and nested-dict deep immutability, canonical serialization, and signed hashes remain release gates. The legacy state adapter fingerprints type arrays and coordinates, rejects silent type/order drift, and requires explicit claim-unsafe opt-in for coordinate/box updates that promise stable atom order. |
| `betelgeuze_ai_md/contracts/` | Reuse/adapt | product adapter outside scientific core | Keep canonical serialization, hashes, abstention, and evidence packaging; no legacy proxy value may be relabelled as v2 physics. |
| `betelgeuze_engine/topology/` | Replace with selective reuse | `betelgeuze_engine_v2/molecular/` | Keep identity/provenance ideas; require all-atom element, isotope, bond order, formal charge, residue, chain, stereo, and source accounting with no alanine/carbon fallback. |
| `betelgeuze_engine/physics/neighbor.py` | Reuse/adapt initially | `betelgeuze_engine_v2/geometry/` | Consume compact neighbor values through an adapter; fail closed on overflow/reference/NxN sources. Native v2 cell-list and Rust/HIP implementations require pair-set and distance parity. |
| Periodic neighbor-to-energy gradient path | Replace/incomplete | `betelgeuze_engine_v2/{geometry,ai,engine}.py` | V2-0 neighbor minimum-image geometry is tested, but AI raw-coordinate edge reconstruction is not periodic-safe. Energy and orchestration fail closed for periodic diagnostics until differentiable image shifts/displacements and boundary-crossing force tests pass. |
| `core/spatial.py` | Reference only | `betelgeuze_engine_v2/geometry/` | Preserve small fixtures; Python fallback is not a production scaling implementation. |
| `core/soa.py`, `core/zero_copy.py` | Reuse after audit | future `betelgeuze_engine_v2/runtime/` | Keep buffer-layout and zero-copy concepts after dtype, device, lifetime, aliasing, and gradient-boundary tests. |
| `core/rust_hip_backend.py`, `rust_engine/` | Reuse infrastructure; replace science kernels | future v2 runtime/backend | Keep build, FFI, compact-buffer, and launch scaffolding. Reimplement each scientific kernel and prove CPU/ROCm value, gradient, overflow, and determinism parity. |
| `betelgeuze_engine/physics/forcefield.py` and force-term plugin interfaces | Reuse interface ideas | future `betelgeuze_engine_v2/physics/` | Preserve composability and diagnostics; native v2 force terms require units, parameters, analytic/finite-difference force tests, invariance, and applicability contracts. |
| `core/allatom_forcefield.py`, `core/refine_physics.py` | Replace | future v2 force-field modules | Current heuristic parameters are reference proxies, not transferable production physics. Build an independent parameter schema and fitting/validation pipeline. |
| `core/explicit_solvent.py` | Replace | future v2 solvent/integrator modules | Fixed oxygen shell remains proxy-only. Implement topology-aware water/ions, PBC, long-range electrostatics, constraints, thermostat/barostat, and ensemble validation. |
| `core/integrator.py` | Replace with reference tests retained | future v2 dynamics modules | Implement independent minimizers and NVE/NVT/NPT integrators with checkpoint/restart, determinism, drift, temperature, pressure, and distribution tests. |
| `core/mm_gbsa.py`, `betelgeuze_engine/physics/mm_gbsa.py` | Archive as proxy; replace | future v2 free-energy modules | Do not migrate delta-G naming. Ensemble MM/GBSA requires calibrated parameters, sampling, uncertainty, and row-level holdout evidence. |
| `core/fep.py` | Archive as proxy; replace | future v2 alchemy modules | Static endpoint interpolation is not FEP. Require lambda ensembles, equilibration, overlap, BAR/MBAR, cycle closure, replicates, and uncertainty. |
| `betelgeuze_engine/biodiscovery/ligand_prep.py` | Reuse provenance; replace chemistry coverage | future v2 preparation | Preserve atom mapping and fail-closed blockers. Add protonation, tautomer, stereo, aromaticity, charge, metal/cofactor, and parameter-coverage gates. |
| `betelgeuze_engine/biodiscovery/protein_prep.py` | Replace | future v2 preparation | Replace CA/proxy preparation with all-atom PDB/mmCIF handling, altloc, assembly, missing atoms/residues, hydrogens, waters, metals, cofactors, and modified residues. |
| `betelgeuze_engine/biodiscovery/pose.py` and `core/pose_generation.py` | Replace; retain fixtures | future v2 docking search | Replace finite rigid grids with torsion-aware global search, local gradients, diverse top-k, constraints, flexible side chains, ensemble receptor, water/metal policies, and reproducible budgets. |
| `betelgeuze_engine/biodiscovery/scoring.py`, `screening.py` | Archive proxy ranking; replace | future v2 scoring | Preserve claim abstention. Replace fixed heuristic blends with independently parameterized physics plus separately validated AI residual energy and confidence. |
| `core/attention_layers.py` | Archive | none | Dense `[N,N]` attention violates the v2 non-attention and scaling boundary. It must not be reachable from v2. |
| `core/gnn_layers.py`, `core/ai_correction.py` | Archive as scientific baselines; maintain narrow legacy compatibility | `betelgeuze_engine_v2/ai/` | Replace non-equivariant/dense or incomplete behavior with bounded sparse SE(3), parity-aware energy components and exact gradients. V2-0 fixes legacy `ai_correction` batch handling for `[B,N,F]` residue features so the sparse runtime-input adapter remains operable, but that model remains frame-dependent and claim-unsafe and is not a v2 AI implementation. |
| `train/runtime_inputs.py`, `train/evaluator.py` | Adapt; v2 graph connected in V2-0 | `betelgeuze_engine_v2/geometry/` with legacy training-output adapter | `torch.cdist` was removed from these paths. Tensor shape `[B,N,K]` is retained, but global-KNN, padding-derived PE, and compact-radius/active-only PE semantics are **not checkpoint-compatible**. New schema-2.1 checkpoints carry the exact cutoff/capacity settings, `periodic=false`, and active-only PE semantics; train, every benchmark AI path, evaluator, and ONNX consumers use the same configuration and reject raw/old or configuration-mismatched checkpoints. Their shared loader also rejects empty, partial, type-mismatched, or shape-mismatched current-model state instead of reporting an uninitialized model as loaded. The benchmark keeps force-field neighbors separate and rebuilds checkpoint-compatible AI inputs. Evaluator LJ/overlap metrics consume unique sparse pairs and return fail-closed nonfinite values on overflow. This adapter does not promote the legacy model or proxy metrics to native v2 science. |
| `theory/branches/`, residual score/force prototypes | Archive or offline baseline | future v2 training experiments | Zero-output or heuristic specialists cannot enter v2 runtime. A learned component requires dataset provenance, ablation, uncertainty, and OOD gates. |
| `core/structure_metrics.py` internal proxies | Archive proxy names; replace | future v2 validation | Use exact published definitions or independently verified implementations; prevent proxy values from sharing official metric names. |
| `api/`, `betelgeuze_product/`, deployment and signed-report surfaces | Reuse after security/schema review | product layer outside v2 | Preserve tenant isolation, job state, path confinement, manifests, and recovery. Enable a v2 route only after scientific capability and customer-result schema gates pass. |
| Existing benchmark/evidence builders | Reuse schema ideas; replace empty evidence | future v2 validation/evidence | Require non-empty row-level results, failures, input/result hashes, command, seed, commit, environment, baseline version, and uncertainty. |
| No previous unified independent-engine entry point | New fail-closed reference | `betelgeuze_engine_v2/{engine,features}.py` | Connect v2 molecular validation, compact geometry, deterministic features, and AI primitives for internal CPU tests. Every result remains `claim_safe=false`; scientific, checkpoint, benchmark, GPU, product, and customer-runtime blockers remain explicit. |

## 3. Migration sequence

| Phase | Scope | Exit condition |
| --- | --- | --- |
| V2-0 | Package boundary, contracts, molecular identity, sparse graph, non-attention AI primitives, projection, and legacy training/evaluator sparse adapter | CPU compile/tests pass, legacy training output shape is preserved without `torch.cdist`, and all product/science claims remain blocked. |
| V2-1 | Complete all-atom parsing and preparation | Supported PDB/mmCIF/SDF/SMILES round-trip without silent atom, bond, charge, stereo, water, metal, or cofactor loss. |
| V2-2 | Independent CPU short-range force field and minimization | Units, analytic/finite-difference force, invariance, conservation, parameter coverage, and applicability gates pass. |
| V2-3 | Independent torsion-aware docking and scoring | Fixed public pose/validity/ranking protocol runs with row-level evidence and predeclared thresholds. |
| V2-4 | Long-range electrostatics, constraints, solvent, NVE/NVT/NPT | PME `O(N log N)` or validated FMM contract is reported truthfully; reference and ensemble tests pass. |
| V2-5 | Residual-energy AI, torsion and temporal refinement, PINN losses | Leakage-free splits, ablations, equivariance/chirality, exact gradients, calibration, OOD abstention, and stability gates pass. |
| V2-6 | ROCm/HIP port | CPU/ROCm energy, force, gradient, ranking, overflow, determinism, memory, and scaling evidence pass on real hardware. |
| V2-7 | Product integration | Durable local execution, UI/reporting, recovery, security, installation, signed evidence, and accepted blind customer-shadow runs pass. |

## 4. Compatibility rules during migration

1. `betelgeuze_engine_v2` may import a legacy compact-neighbor value only through
   a narrow adapter. This exception does not authorize other legacy imports.
2. A v2 result must record whether any adapted value was used; legacy runtime
   checkpoints require an exact runtime-input schema/configuration match.
3. Legacy proxy and v2 scientific values use different capability identifiers
   and result-schema versions.
4. Product dispatch defaults to disabled for v2 until a capability-specific
   release gate is accepted.
5. External solvers may generate labelled comparison evidence only. They are
   not v2 customer-runtime dependencies.
6. Archive status is a routing decision, not permission to delete files or
   historical evidence.

## 5. Immediate completion definition

The initial refactor is complete only as a **scaffold** when:

- new modules compile on Python 3.11 CPU;
- focused molecular, sparse-graph, equivariance, chirality, torsion, temporal,
  PINN-loss, projection-adjoint, and fail-closed orchestrator tests pass;
- tests demonstrate no dense projector or dense all-pairs requirement for the
  covered primitives;
- periodic neighbor inputs are rejected by AI energy/orchestration until the
  minimum-image displacement gradient path is implemented and validated;
- the capability file keeps GPU, benchmark, scientific, and product execution
  claims blocked;
- no legacy customer route is silently switched to v2.
- the internal CPU reference result cannot be mistaken for a calibrated,
  benchmarked, GPU-backed, or customer-safe result.

These conditions do not complete the later all-atom force field, docking, MD,
free-energy, benchmark, GPU, or commercial phases.
