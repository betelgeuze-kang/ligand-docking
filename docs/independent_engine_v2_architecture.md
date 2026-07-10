# Independent Engine v2 Architecture

Status: implementation scaffold; not a scientific or product release claim
Scope: independent molecular representation, sparse equivariant AI, docking,
physics, molecular dynamics, and structure-analysis engine

## 1. Goal and independence boundary

Independent Engine v2 is the clean scientific core for an independently
operated protein-structure and ligand-analysis product. A customer execution
must not delegate pose search, force or energy evaluation, molecular dynamics,
free-energy estimation, or AI inference to Vina, GNINA, Smina, OpenMM, AMBER,
GROMACS, or another molecular solver.

Those programs may be used as **offline reference oracles** in development and
validation. Their results must be provenance-labelled and cannot be emitted as
v2 results. General Python infrastructure and hardware runtimes such as
PyTorch, Rust, and ROCm are implementation foundations, not scientific
backends.

The first v2 slice establishes contracts and mathematically safe primitives.
It does **not** establish docking accuracy, force-field validity, GPU parity,
benchmark parity, calibrated affinity, MD validity, or commercial readiness.

## 2. Package boundary

The new implementation lives under `betelgeuze_engine_v2/`. It may consume
legacy values only through explicit adapters. New v2 modules must not import
legacy proxy scoring, coarse topology, attention, or customer result emitters.

```text
betelgeuze_engine_v2/
├── engine.py        # fail-closed internal CPU reference orchestration
├── features.py      # deterministic all-atom feature construction
├── contracts/       # typed/frozen schema shells, versions and claim state
├── molecular/       # all-atom identities, bonds, stereo and validation
├── geometry/        # bounded sparse graphs; no dense N x N allocation
├── ai/
│   ├── sparse_graph.py
│   ├── energy.py    # invariant scalar residual energy
│   ├── torsion.py   # static torsion/topology propagation
│   ├── temporal.py  # recurrent state; fixed-window mode is explicit
│   └── physics_informed.py
└── physics/
    └── projection.py
```

Future modules add independently implemented force terms, integrators,
long-range electrostatics, docking search, refinement, validation, and report
adapters. Product APIs remain outside the engine and may consume a v2 result
only after the relevant scientific gate is satisfied.

The initial `IndependentEngineV2` orchestrator is an **internal CPU reference**
that connects validated molecular state, bounded geometry, deterministic
features, and the uncalibrated AI reference modules. Its output is always
`claim_safe=false` and carries checkpoint, scientific, benchmark, GPU, and
product blockers. Availability of this internal entry point does not enable a
customer route or any solver claim.

The legacy training adapter changes feature semantics from global KNN and
padding-influenced PE to bounded local-radius neighbors and active-only PE.
Shape compatibility is not checkpoint compatibility. V2-0 checkpoints embed a
runtime-input schema plus cutoff/capacity settings. Schema 2.1 also records
`periodic=false`; its benchmark path deliberately rebuilds the same non-periodic
compact-radius graph and active-only PE instead of reusing the force-field's
periodic/grid neighbor payload. Known train, benchmark, and ONNX consumers
reject old raw checkpoints or mismatched settings and require retraining. This
compatibility guard is not evidence that the legacy AI model is scientifically
valid in a periodic simulation. The shared loader also requires every current
model state key to be present and shape-compatible. Non-strict mode may ignore
retired extra checkpoint keys, but it cannot silently leave random current
weights. Dtype mismatches and non-finite tensors are rejected before mutation;
intentional partial transfer is a separate explicit development-only decision
and is not enabled by train, benchmark, or ONNX consumers.
Training checkpoints unwrap `torch.compile` to a canonical model key space, so
compile mode cannot leak `_orig_mod.*` prefixes that an ordinary consumer would
otherwise reject.

## 3. Canonical data flow

```text
validated all-atom molecular state
            │
            ▼
bounded cell-list / Verlet graph ─── torsion topology graph
            │                              │
            ├──── local SE(3) energy GNN ──┤
            │                              │
            └──── temporal GNN (streamed TBPTT for fixed window)┘
                           │
                 invariant scalar energy
                           │ exact VJP
                           ▼
                    conservative force
                           │
              structured orthogonal projection
                           │
                optimizer / integrator / docking
```

The V2-0 reference result currently records source provenance, schema IDs,
initialization seed, parameter fingerprint, feature/neighbor schema, device,
dtype, and claim blockers. Topology hashes, code commit, complete software
environment, calibrated checkpoint provenance, and signed execution manifests
remain future release requirements. Unsupported chemistry fails closed; it is
never silently replaced with carbon-only atoms, alanine residues, or
virtual-bead evidence. Frozen dataclasses do not imply deep immutability of
contained tensors or metadata dictionaries; serialization/hashing gates must
close that boundary before product use.

## 4. Linear-scaling contract

Let `N` be atom count, `E` the directed sparse-edge count, `K` the configured
maximum neighbors per atom, `L` network depth, `C` channel width, `r`
projection rank, and `W` temporal backpropagation window.

The short-range forward and reverse passes are `O(N)` only under all of these
conditions:

1. Fixed physical density and fixed cutoff permit `E <= K*N`.
2. `K` is finite and independent of `N`; overflow fails closed rather than
   falling back to all-pairs computation. Engine-owned geometry and sparse AI
   enforce a hard `K <= 256` cap; callers cannot raise it with `N`.
3. Cell-list construction and neighbor traversal use bounded occupancy or
   explicitly report overflow.
4. `L`, `C`, irreducible-representation order, radial basis count, candidate
   budget, refinement steps, and `W` do not grow with `N`. The reference local
   energy path additionally hard-caps layers at 16 and hidden width at 512.
5. Orthogonal projections use a hard rank cap of 16 or bounded local bases and
   never materialize an `N x N` projector.
6. No `torch.cdist`, dense adjacency, full attention, full Hessian, full
   Jacobian, global QR/SVD, or direct all-pairs electrostatics is used on the
   product path.

Under these assumptions, `E = O(N)` and a local layer costs `O(E)`. Reverse-mode
automatic differentiation traverses the same sparse operations, so its atom
count dependence is also `O(N)`. This is a conditional algorithmic contract,
not yet a measured performance claim. Constants may still be large.

### Periodic-boundary limitation in V2-0

The compact geometry builder tests orthorhombic minimum-image distances, but
the initial AI energy reference reconstructs edge displacement from raw
coordinates. That reconstruction does not yet carry the periodic image shift
through the energy/force autograd path. Consequently, the AI energy and CPU
reference orchestrator must fail closed when neighbor diagnostics declare a
periodic system.

Periodic execution remains blocked until the graph supplies differentiable
minimum-image displacement or image-shift data to the energy model and
finite-difference tests cross the unit-cell boundary. A passing neighbor-only
minimum-image test is not evidence of periodic energy or force correctness.

### Long-range physics

Short-range linearity does not make the whole physical solver unconditionally
linear:

| Method | Expected complexity | v2 policy |
| --- | ---: | --- |
| Direct Coulomb all-pairs | `O(N^2)` | prohibited outside tiny reference tests |
| PME | `O(N log N)` | acceptable truthful production option once validated |
| FMM | expected `O(N)` | claim requires fixed error tolerance, multipole order, bounded tree behavior, and scaling evidence |
| Fixed-cutoff screened electrostatics | `O(N)` | approximation must be named; not PME/FMM parity |

The public product must report the selected long-range method. It must not label
a PME execution as strict `O(N)` or an unvalidated FMM scaffold as production
linear scaling.

## 5. Equivariance and molecular chirality

The v2 energy model produces a scalar that is invariant to translation, proper
rotation, and permitted atom permutation. Forces are obtained as

`F_i = -dE_total / dr_i`

and therefore transform covariantly when the energy implementation is correct.

Molecular chirality prevents treating reflection as an interchangeable data
augmentation. The implementation uses SE(3)-equivariant coordinate behavior
with parity-aware features:

- R/S and E/Z stereo identifiers are canonical input features;
- signed triple products or equivalent pseudoscalar channels distinguish
  mirrored local environments;
- three local polar-vector branches form an explicit signed pseudoscalar; this
  is not yet a general irreducible-representation vector/pseudovector stack;
- reflection tests verify the declared parity behavior instead of requiring
  enantiomers to receive identical representations.

The term “E(3) GNN” in planning documents therefore means Euclidean geometric
message passing. The executable contract is more precise: proper-rotation
SE(3) equivariance plus explicit parity/chirality handling. A distance-only
model cannot be promoted as chirality-aware.

## 6. Non-attention AI components

### 6.1 Sparse energy GNN

The main AI contribution is an invariant residual energy,

`E_total = E_independent_physics + sum_i delta_e_i`,

not an unconstrained force vector. Exact differentiation supplies the residual
force. This preserves energy/force consistency and avoids a force-only model
being described as conservative without proof.

Messages are exchanged only across bounded sparse edges. There is no
Transformer, softmax attention, global pair tensor, `torch_geometric`, or
external equivariant-model dependency in the baseline implementation.

### 6.2 Torsion GNN and Temporal GNN are separate

`TorsionTopologyGNN` operates on a static bond/torsion tree. It propagates
rotatable-bond context and supports recursive forward kinematics plus a reverse
adjoint. It must not walk every torsion's descendant atoms independently,
which can become `O(N^2)`.

`TemporalStateGNN` operates across simulation or refinement steps using bounded
recurrent state. One-step cost is `O(N)`. A history-free rollout with truncated
backpropagation and final-state/chunk loss costs and retains `O(W*N)` state for
fixed window `W`. Returning every state intentionally retains `O(T*N)` memory,
and a loss over that history has `O(T*N)` backward work. Full-history rollout
is therefore outside the fixed-memory claim.

Combining these concerns behind a single ambiguous “T-GNN” name is prohibited
in code, evidence, and product reports.

### 6.3 PINN role

Physics-informed learning is a loss and release-gate layer, not the numerical
MD solver. It may combine:

- energy and force supervision;
- translation, proper-rotation, permutation, and declared-parity checks;
- net-force and net-torque residuals;
- force/energy finite-difference consistency;
- bond, angle, virial, pressure, and short-rollout residuals;
- uncertainty calibration and out-of-domain abstention.

PINN loss success cannot substitute for an independently implemented
integrator, force field, ensemble test, or public benchmark. Force-label
training may require higher-order differentiation; sparsity preserves the
conditional atom-count order but not a small runtime or memory constant.

## 7. Orthogonal projection and its adjoint

For a full-column-rank basis `B` with shape `(D, r)`, projection onto its span
is applied as

`P(v) = B @ solve(B.T @ B, B.T @ v)`

and projection onto the complement as

`Q(v) = v - P(v)`.

The dense `D x D` matrices `P` and `Q` are never materialized. With hard-capped
fixed `r`, application costs `O(D*r^2 + r^3)` and the vector adjoint uses the
same symmetric projector at that order. Rank-deficient or ill-conditioned
bases fail closed: a Moore-Penrose projector changes rank at that boundary and
does not provide the claimed exact basis gradient.

If `B` depends on coordinates, an exact gradient also includes derivatives of
the basis. Detaching `B` changes the mathematical operator and must be exposed
as an approximation. Exact v2 training leaves the basis in the autograd graph
and validates gradients against finite differences. Global QR/SVD over atom
axes and dense constraint pseudoinverses are excluded from the linear claim.

Approved initial projection uses include translation-mode removal, bounded
local frames, net-force/net-torque correction with a constant-size solve, and
fixed-rank separation of analytic and learned residual subspaces. Constraint
projection is linear only when graph degree and solver iteration count are
bounded.

## 8. Validation ladder and blocked claims

Implementation gates are intentionally independent:

1. **Contract gate:** schema validation, units, topology identity, no silent
   fallback.
2. **Mathematical gate:** sparse-bound checks, equivariance/parity tests,
   energy/force finite differences, projection-adjoint checks.
3. **Scientific gate:** all-atom force terms, energy conservation, ensemble
   properties, docking pose validity, calibrated uncertainty.
4. **Benchmark gate:** row-level public holdouts, dataset hashes, commands,
   seeds, baseline versions, confidence intervals, and failure rows.
5. **GPU gate:** CPU/ROCm energy, force, gradient, ranking, determinism,
   overflow, memory, and scaling parity on real hardware.
6. **Product gate:** versioned execution, reports, recovery, security, offline
   deployment, and accepted customer-shadow evidence.

Until the respective gate passes, all of the following remain blocked:

- GPU acceleration or CPU/ROCm parity claims;
- strict end-to-end `O(N)` claims;
- docking accuracy or external-tool parity claims;
- calibrated binding affinity, MM/GBSA, FEP, or wet-lab hit claims;
- validated all-atom MD or protein-structure prediction claims;
- periodic AI energy, force, docking-refinement, or MD claims;
- independent commercial-solver, broad-platform, or customer-ready claims.

Accounting, compilation, and unit-test success establish implementation
progress only. They do not promote scientific or product capability.
