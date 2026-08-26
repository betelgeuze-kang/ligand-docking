# Engine V2 session-completion development foundations v1

This document describes the non-authoritative development tools added after the
ABI 1.21 native fixed64 foundation. They are designed to make the next
scientific and engineering steps executable without weakening Fresh-128,
Stage 0, benchmark, scientific, GPU, product, customer, or license boundaries.

## D1 development v2

Preferred entrypoint:

```bash
python tools/run_engine_v2_d1_development_v2.py \
  --manifest /absolute/d1/manifest.json \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --result-root /absolute/d1/results \
  --output /absolute/d1/reports/run-001.json
```

Persisted semantic replay:

```bash
python tools/verify_engine_v2_d1_development_v2.py \
  --report /absolute/d1/reports/run-001.json --pretty
```

Version 2 rejects non-string manifest paths before invoking the v1 analyzer and
replays every derivable 32-case summary, aggregate, scoring-regret, lane,
baseline new/lost recovery, denominator, and authority invariant.

## D1 source materialization

```bash
python tools/materialize_engine_v2_d1_case_results_v1.py \
  --manifest /absolute/d1/adapter-manifest.json \
  --source-root /absolute/d1/adapter-sources \
  --fresh-case-registry /absolute/private/fresh-case-ids.json \
  --output-root /absolute/d1/materialized
```

The adapter requires exactly 32 D1 cases, verifies zero Fresh-ID overlap,
retains exactly 64 candidate rows for every prepared case, computes Kabsch-
aligned symmetry-aware heavy-atom RMSD, and creates a transactional
materialization receipt. It does not execute docking.

## Deterministic 512-to-64 sampling funnel

```bash
python tools/run_engine_v2_sampling_funnel_v1.py \
  --profile config/engine_v2_sampling_funnel_v1.json \
  --input /absolute/proposal-pool-512.json \
  --output /absolute/funnel-result.json
```

The funnel uses result-independent lane quotas, bounded geometric rejection,
quality prefiltering, and deterministic farthest-point diversity. It accepts no
RMSD, native-pose, PoseBusters, or downstream-rank field and preserves quota
shortfall as typed output failures.

Profile schema 1.1 freezes global coordinate-identity deduplication as
`global_coordinate_sha256_first_pool_index`. Every generated row is encountered
in pool order before geometric filtering, so the first occurrence owns the
coordinate identity and every later occurrence remains in the 512-row ledger as
`duplicate_coordinate`. Per-lane evidence now records generated, upstream typed
failure, vdW rejection, pocket rejection, duplicate, total filtered, eligible,
selected, and shortfall counts.

The same selection is implemented without serialization dependencies in the
Rust search core as `run_native_sampling_funnel(...)`. The Rust receipt retains
all 512 typed inputs, all 512 decisions, the exact 64-row output, the canonical
profile hash, and every lane summary, then independently rederives itself. A
shared frozen fixture requires the Python reference and Rust CPU implementation
to select the same ordered 64 pool indices. This is the native preselection
core and grants no molecular or promotion authority.

The coordinate-bearing bridge is `NativeSamplingFunnelPayloadBatch` plus
`materialize_native_sampling_funnel_preselected_batch(...)`. It validates an
exact 512-row payload ledger against every funnel source, proposal, coordinate,
and typed-failure identity, then copies only the selected rows into exact
64-candidate x/y/z and quaternion x/y/z/w SoA channels. Lane shortfalls retain
their output slots with zero numerical sentinels that downstream inactive-row
semantics must ignore. The materialized receipt binds the funnel and payload
receipts and rederives every selected coordinate digest and canonical
quaternion.

`Fixed64PreselectedPipeline::run_preselected(...)` now consumes that exact
materialized batch without invoking a second proposal producer. The separate
constructor allocates its additional component handles only when this path is
explicitly requested, so existing `Fixed64Pipeline` callers retain their prior
construction and memory behavior. It composes the existing
public ABI 1.21 geometric-admission, rigid-refinement, torsion-V7,
ScorerV1/validity/stable-rank, and direct-RMSD kernels. The same full-Cartesian
geometric admission is applied both before refinement and to final refined
coordinates before ScorerV1. Lane shortfalls remain inactive typed rows, and
the exact source coordinates and quaternions are retained unchanged in the
result receipt.

Before issuing a receipt, the live runtime independently replays admission,
rigid, torsion, refinement, ScorerV1, validity, rank, and clustering semantics
against the bound molecular contexts. A persisted receipt rederives every
component evidence digest, batch digest, row receipt, count, coordinate channel,
and final pipeline receipt; it also replays the self-contained rigid, torsion,
refinement, rank, and clustering policies. It does not claim to reconstruct the
omitted molecular admission, scorer, or validity contexts after persistence.
The payload and materialized
receipts now bind the exact ligand-system identity, and runtime composition
rejects a same-atom-count batch from another ligand. The persisted receipt also
retains the refinement modes and budgets, torsion eligibility and baseline
angles, RMSD threshold, rotor indices, and declared policies needed to replay
rigid, torsion, refinement, ranking, and clustering policy checks. Synthetic integration coverage
requires C++ reference and Rust CPU to preserve the same selected, valid,
representative, and Top-K slot orders. This is a synthetic/test-only common
composition boundary: molecular execution, reservation, benchmark, Stage 0,
Fresh-128, product, customer-pose, rank-mutation, scientific-claim, and
performance-claim authority all remain false.

### Source-bound native 512-row producer

`produce_native_sampling_pool(...)` removes the remaining caller-supplied
proposal-coordinate boundary ahead of the funnel. The Rust CPU implementation
constructs four contiguous 128-row lanes from `SearchInput` and
`Fixed64GeometricInput`:

- uniform SO(3) rotates centered source coordinates onto the pocket center;
- pocket-surface rotates centered source coordinates onto deterministically
  ID-ordered surface targets;
- single-anchor executes the existing compatible-anchor placement transform;
- multi-anchor executes the existing dual-anchor correction and placement, or
  preserves all 128 slots as typed failures when no compatible dual exists.

The low-discrepancy orientation seed is a digest of the complete canonical
search input and geometric-input receipt, rather than a separately accepted
producer seed. Ligand radii and receptor coordinates/radii must match across
the two inputs exactly. Every generated coordinate set is observed by
`evaluate_fixed64_geometric_metrics(...)`; its exact minimum vdW ratio, pocket
escape, and penetrating-pair fraction feed the result-independent funnel
quality state. The shape penalty is the dimensionless penetrating-pair count
divided by the exact ligand-receptor pair count. Anchor lanes add the
dimensionless half-one-minus mean alignment cosine and fit RMSD divided by the
frozen 0.75-angstrom dual tolerance; non-anchor lanes use zero anchor penalty.
The aggregate generated-candidate × ligand-atom × receptor-atom traversal must
fit the existing 16,777,216-pair bound before any proposal coordinates are
created.

The returned `NativeSamplingPoolBatch` retains the 512-row funnel receipt,
512-row coordinate payload, materialized 64-row batch, source/input identities,
exact executed pair count, and a composition receipt. `verifies_against(...)`
re-executes generation and all geometric observations from the two bound
inputs. Self-verification alone checks retained identities and nested receipts;
it does not reconstruct omitted inputs. This implementation and its tests are
synthetic engineering evidence only. It does not authorize molecular runs,
reservation, D1/Fresh-128, public benchmarks, Stage 0, product use, performance
claims, or scientific claims.

## CPU water-box development reference and native slice

```bash
python tools/run_engine_v2_water_box_reference_v1.py \
  --profile config/engine_v2_water_box_reference_v1.json \
  --steps 100 \
  --dt-fs 0.02 \
  --output /absolute/water-box-nve.json
```

This is a bounded CPU numerical reference for harmonic water, orthorhombic
minimum-image Lennard-Jones/Coulomb interactions, Velocity Verlet, energy
observation, and deterministic checkpoint state. It has no PME, NPT, ion,
protein, production-MD, free-energy, or performance authority.

The successor profile
`config/engine_v2_native_water_box_profile_v1.json` binds those frozen two-water
inputs to the canonical native ABI Coulomb constant and explicit cutoff/switch
settings. A standalone single-water evaluation and `DevelopmentWaterBoxV1`
construct the same atoms through the shared native `System`, `ForceField`, and
`Simulation` owners. Their public entry
points admit only the C++ reference and Rust CPU backends. Focused tests require
single-water and two-water energy/force parity, 100-step Velocity Verlet parity,
128-step seeded BAOAB parity, and bit-exact Rust checkpoint continuation. The compiled runtime
embeds the exact profile bytes and exposes their SHA-256 identity.

A separate immutable successor profile,
`config/engine_v2_native_water_box_constraints_profile_v1.json`, adds the six
rigid-water distance rows without mutating that base identity. The native CPU
lane now validates SHAKE/RATTLE position and radial-velocity residuals, the
12-degree-of-freedom report, 100-step NVE and 128-step seeded BAOAB C++/Rust
parity, and bit-exact checkpoint continuation. This is bounded synthetic CPU
development evidence and grants no molecular, production, scientific,
performance, Stage 0, Fresh-128, reservation, or HIP-device authority.

The next immutable successor,
`config/engine_v2_native_periodic_neighbor_list_profile_v1.json`, routes fully
periodic orthorhombic nonbonded work through deterministic C++ reference and
Rust CPU cell lists. It freezes inclusive-cutoff pair membership, wrapped-cell
deduplication, canonical pair order, and integer-box translation invariance;
atom-permutation invariance is checked after mapping forces back to source atom
identity. The search radius is `max(cutoff, minimum_pair_distance)`, so the
existing fail-closed minimum-distance check remains effective even outside the
cutoff. The independent all-pairs oracle remains the validation source.
Lists rebuild on every evaluation and carry no performance or acceleration
claim.

The next SHA-bound successor admits only explicit Na+ and Cl- identities from
the Joung/Cheatham TIP3P-targeted parameter table, converts the source
`Rmin/2` representation to the native sigma convention, and rejects every
other element/charge pair with a typed error. One charge-neutral static
two-water/Na+/Cl- fixture is checked against the independent all-pairs oracle
and both CPU backends. It is not a trajectory or scientific applicability
claim, and it does not authorize general ion preparation or long-range
electrostatics.

An immutable ion-dynamics successor binds that exact static fixture plus the
water-constraint and periodic-neighbor identities. A separate native owner
runs 100 constrained Velocity Verlet steps and a 32-step checkpoint
continuation. C++ reference and Rust CPU must retain the same 18-DOF report and
eight-atom state within one build, both ions must move, the six water
constraints remain within the existing residual bounds, and absolute step 132
must be restored exactly. This remains tiny synthetic CPU implementation
evidence with every authority field false.

An immutable typed-failure successor binds the ion-dynamics profile and emits
five ordered backend-tagged rows for nonfinite input, linearly dependent
constraints, absolute-step capacity overflow, OOM status mapping, and an
unsupported ion identity. Four rows execute deterministic rejection paths and
the capacity row must preserve the exact checkpoint and snapshot. The OOM row
tests only `BG_STATUS_OUT_OF_MEMORY` to `ErrorCode::OutOfMemory` mapping, with
no allocation attempt or production-resilience authority. Every scientific,
molecular, performance, product, reservation, benchmark, Fresh-128, and HIP
device authority remains false.

The next SHA-bound successor,
`config/engine_v2_native_periodic_neighbor_list_profile_v2.json`, retains one
buffered canonical pair slice in the native `Simulation` for fully periodic
C++ reference or Rust CPU dynamics. Its 1.0 angstrom skin is reusable only
while every atom is strictly below 0.5 angstrom from the unwrapped build
reference; the exact pair evaluator continues to enforce minimum-distance and
cutoff semantics. Cache changes share the integrate/minimize transaction,
checkpoint load invalidates the unpersisted derived state, and public
stateless/mixed/nonperiodic/HIP evaluation remains uncached. The profile has no
performance measurement or threshold and grants no performance or acceleration
authority.

The next SHA-bound successor,
`config/engine_v2_native_water_box_nvt_ensemble_profile_v1.json`, runs only the
two admitted CPU backends over eight fixed constrained-BAOAB seeds. After a
fixed 2,000-step burn-in, it retains 32 observations per seed at a 100-step
stride, emits an ordered backend-tagged receipt over the exact binary64 rows and
summary, and requires same-build repeatability, CPU-backend binary64 identity,
positive kinetic energy, nonzero temperature variance, and a broad 240–360 K
mean-temperature development bound. This is a deterministic tiny synthetic
validation, not equilibrium, production-MD,
performance, molecular-execution, scientific-claim, reservation, Stage 0,
Fresh-128, or HIP-device authority.

An immutable residual-distribution successor,
`config/engine_v2_native_water_box_nvt_constraint_residual_profile_v1.json`,
uses the exact same seeds, burn-in, stride, and sample count. It retains the
maximum position and radial-velocity constraint residual across all six frozen
rows for every observation, rederives their mean and maximum, and binds them to
an ordered backend-tagged receipt. Both CPU backends must produce bit-identical
rows within one build and remain within the existing `1e-10` position and
radial-velocity tolerances. This remains tiny synthetic implementation evidence
with every authority field false.

See `docs/engine_v2_native_water_box_v1.md` for the frozen development metrics
and remaining scientific boundaries.

## HIP D1 benchmark result verification

```bash
python tools/verify_engine_v2_hip_d1_benchmark_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json
```

This verifies the committed 1.5 profile and its self-hash only. The profile is
deliberately `frozen_non_authoritative_manifest_not_bound`; passing `--result`
is rejected until an owner-controlled successor binds the exact private D1
manifest SHA-256 and its owner-selected ordered-case SHA-256, then reseals the
profile. The bound successor must also carry the owner-sealed ordered
64-candidate identity digest for every selected case. Profile verification does
not authorize D1 materialization, molecular execution, or HIP-device execution.

Self-hashing alone is not authorization. The verifier's repository-reviewed
authorized-bound-profile and authorized-result SHA-256 sets are intentionally
empty. A future owner-approved manifest/profile and completed result each need
an explicit code-reviewed digest pin before result verification can succeed;
an operator-selected path or recomputed self-hash cannot grant that trust.

Before those pins are reviewed, the same verifier can fully validate an exact
candidate result against an exact manifest-bound profile:

```bash
python tools/verify_engine_v2_hip_d1_benchmark_v1.py \
  --profile /absolute/manifest-bound-profile.json \
  --candidate-result /absolute/completed-result.json
```

Candidate mode exists only to break the digest-review cycle: it recomputes the
complete result, receipt, parity, trace, transfer, failure-probe, identity, and
performance-gate evidence before reviewers pin the resulting profile and
result digests. It still requires a manifest-bound profile, but it does not
require either repository allowlist entry. Its output uses
`candidate_valid`, never `verified`; reports both digest-pin states; and keeps
result verification, device execution, and every claim authority false. The
ordinary `--result` path remains the only repository-authorized verification
path and still requires both exact digest pins.

Once those external prerequisites and authorization exist, the same command
accepts `--result /absolute/hip-d1-result.json`. A valid result must retain the
ordered 32-case, 64-candidate cohort on `rust_cpu`, `hip_safe`, and `hip_fast`
for `gfx1030` and at least one newer architecture. It records six exact parity
digests (decision, typed failure, score order, validity, rank, and clustering),
all 192 slot-major score/proposal-RMSD/final-RMSD positions per case, a stable
repeat, case/context/transfer timing samples, RSS/VRAM, H2D/D2H bytes, complete
ROCprofiler kernel traces, typed failure probes, and GPU/toolchain/artifact
identities. The five non-failure discrete digests are recomputed from ordered
decision, score-order, validity, rank, and cluster structures; the typed-failure
digest is recomputed from the 64 structured status rows. Score order is also
recomputed from ascending finite score with slot-index tie-breaking. Scored
decisions are restricted to `scored_valid` or `scored_invalid` and must agree
with the corresponding boolean validity entry. Structured ranks preserve the
native one-based `stable_rank` convention. The
cluster structure also preserves native membership semantics: valid scored
candidates use contiguous one-based cluster IDs, invalid scored candidates use
zero, and typed failures remain null. New one-based cluster IDs must be first
encountered in ascending order while traversing validity-filtered stable rank,
matching native representative discovery. The
newer GPU must be in the profile's explicit architecture
allowlist (including alphanumeric targets such as `gfx90a`), and every
architecture needs a distinct hashed device serial. The verifier derives case
p50/p95, candidate throughput, transfer
p50, context p50, kernel totals, and the predeclared strict `hip_fast` median
gate. CPU fallback, denominator deletion, non-finite values, evidence field
drift, or any execution/scientific/benchmark/product authority is rejected.
Each architecture row also records the CPU model, physical-core/logical-thread
topology, benchmark thread count, affinity, governor, turbo state, NUMA policy,
and hashed execution environment used by the `rust_cpu` speed-gate reference.
Each candidate's scientific triple must be entirely finite or entirely JSON
`null` for a typed failure; partial triples and non-finite numbers are rejected,
and proposal/final RMSD values must be nonnegative. Failures therefore remain
in the 64-slot denominator. Every representative case must
also retain at least the profile-defined minimum of one scored candidate, which
prevents an all-failure cohort from satisfying the benchmark contract.
Structured status rows cover all 64 slots, their canonical digest is recomputed,
and null triples are permitted exactly at slots whose status is `typed_failure`.

Each failure probe has a globally distinct execution identity and embeds a
predeclared typed stimulus, a structured observation bound to that stimulus and
execution, and a recomputed probe receipt. Its backend and typed code must match
the requested probe, and all canonical SHA-256 bindings are recomputed. Each
representative backend embeds a self-bound execution receipt naming the
requested and observed backend, ordered cohort, fallback status, and profiler
trace plus the canonical per-case wall-time and output digests. Primary and
repeat executions use distinct globally unique run identities, separate timing
samples, separate GPU traces/summaries, and separate receipts; repeat outputs
are bound to the repeat receipt rather than accepted as unproven copied fields.
Each normalized profiler and transfer trace embeds its corresponding run
identity, so primary evidence cannot be copied into the repeat slot and
rehashed. Primary and repeat context-construction samples are separately bound
into their matching receipts and reported as separate derived p50 metrics.
Primary and repeat RSS/VRAM peaks are likewise separate and receipt-bound before
being reported.
Every backend receipt also binds a canonical executable-bundle digest covering
the architecture row's wheel, native extension, and native binary, so CPU and
HIP evidence cannot be attributed to a different claimed build.
Requested/observed backend identity and CPU-fallback state are recorded and
validated independently for each run and bound into the corresponding receipt.
The repository-pinned result digest binds both receipts, timings, and all
remaining evidence fields. The speed gate counts only cases that beat the CPU
reference in both the primary and repeat executions.
GPU profiler evidence contains the complete normalized ordered dispatch
rows; the verifier recomputes their canonical digest and rejects any per-kernel
count or runtime summary not derived from those rows. Every ordered case and
every required timing-sample index must occur in the normalized trace, so a
rehashed truncated trace is rejected. Each timed sample must also contain the
owner-defined ordered stage contract: initial admission, rigid refinement,
torsion refinement, post-refinement admission, scoring, pose validity, stable
ranking, and RMSD clustering. A trace retaining only one arbitrary dispatch
per sample is therefore incomplete, and each stable stage ID must name its
profile-pinned normalized HIP kernel rather than an operator-selected label.
Kernel runtime summaries use a relative-only consistency tolerance, while
reported totals are always derived
from the normalized trace rather than copied from submitted summaries. For each
case/sample pair, the sum of dispatch runtimes must not exceed its enclosing
wall-time sample.
GPU H2D/D2H bytes and timing samples are likewise rederived from normalized,
ordered memory-copy event traces whose hashes are bound into the corresponding
primary or repeat execution receipt. Each direction must cover every ordered
case and every timing-sample index; multiple copy events for the same direction
and timed sample remain distinct in the trace while their bytes and runtimes are
aggregated for the derived sample. The combined per-sample transfer runtime must
fit its enclosing wall-time sample. Profiler identity requires a
parsed non-whitespace `rocprofiler-sdk` version suffix.
Derived sums and medians use overflow-safe finite arithmetic, including a
stable even-sample midpoint that preserves positive subnormal values; any
non-finite derived metric is rejected rather than serialized as `Infinity`.

The verifier only checks supplied evidence. It never runs a GPU and a passing
artifact still grants no acceleration, scientific, benchmark, or product
claim authority.

### HIP D1 owner identity binding

```bash
python tools/bind_engine_v2_hip_d1_profile_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json
```

Profile-only mode validates the complete frozen 1.5 profile and reports that
the committed profile is unbound and result verification is unauthorized. It
does not read molecular inputs or grant permission to materialize or execute
them.

After the owner independently selects a licensed private D1 cohort, the same
tool can consume a self-hashed binding request and write an absent bound-profile
successor. The request contains the exact base-profile SHA-256, exact private
manifest SHA-256, 32 ordered unique case IDs, and an exact ordered list of 64
unique candidate identities for every case. Candidate identities are retained
only long enough to derive the profile's per-case canonical SHA-256 map; the
private identities are not copied into the output profile. The request also
contains the full authority map with every value literally `false`.

```bash
python tools/bind_engine_v2_hip_d1_profile_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json \
  --binding-request /absolute/owner-binding-request.json \
  --output /absolute/absent-bound-profile.json
```

The output changes only the manifest/case/candidate binding fields, status,
blockers, and profile self-hash. It is checked again by the canonical HIP D1
profile verifier before publication and is written with an absent-only atomic
link. A generated profile remains unauthorized until its exact digest is added
to the verifier's repository-reviewed bound-profile allowlist in a separate
code review. The binder cannot edit that allowlist, cannot authorize a result,
cannot launch a command or device, and reports molecular/device execution and
authority as false in its self-hashed receipt.

### HIP D1 measurement-journal normalization

```bash
python tools/normalize_engine_v2_hip_d1_measurement_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json
```

Profile-only mode reports the committed blockers and performs no execution.
After an independently authorized owner-controlled wrapper records a complete
sample-relative nanosecond journal, the same tool accepts `--journal` and an
absent `--output` path. It requires the exact ordered 32-case and minimum
sample coverage, the profile-pinned eight-stage sequence and kernel names,
positive bounded event intervals, both H2D and D2H coverage for every sample,
and aggregate dispatch/transfer runtime no greater than the enclosing wall
sample. It emits the exact normalized profiler 1.3 and transfer 1.2 fragments,
their canonical hashes, derived kernel summaries, byte totals, and per-sample
transfer timings accepted by the result verifier.

The journal is one strict JSON object with the 1.0 schema ID, exact profile and
execution-run hashes, one of `hip_safe` or `hip_fast`, 32 ordered case IDs, the
all-false profile authority map, and case-major samples. Sample indices start at
zero and remain contiguous independently for each case; counts may exceed the
profile minimum. Each sample contains `wall_time_nanoseconds`, ordered
`dispatches`, and ordered `transfers`. Dispatch and transfer rows carry positive
`start_offset_nanoseconds` and `end_offset_nanoseconds` relative to that sample;
dispatches additionally carry `stage_id` and `kernel_name`, while transfers
carry `direction` and `bytes`.

```bash
python tools/normalize_engine_v2_hip_d1_measurement_v1.py \
  --profile config/engine_v2_hip_d1_benchmark_profile_v1.json \
  --journal /absolute/owner-recorded-run.json \
  --output /absolute/absent-normalized-run.json
```

The normalizer cannot launch a command or device, cannot overwrite an output,
and carries the same all-false authority map as the profile. A journal is
measurement evidence only; it is not an execution authorization receipt and
cannot bind the currently unmaterialized D1 manifest or populate either empty
repository authorization allowlist.

### HIP D1 candidate-result assembly

After an independently authorized owner wrapper has completed the full
result-shaped evidence draft, the repository can recompute its redundant
bindings without launching another workload:

```bash
python tools/assemble_engine_v2_hip_d1_candidate_result_v1.py \
  --profile /absolute/manifest-bound-profile.json \
  --draft /absolute/owner-recorded-result-draft.json \
  --output /absolute/absent-candidate-result.json
```

The assembler requires a valid manifest-bound profile and treats the draft as
owner-recorded evidence, not as authority. It recomputes the ordered cohort and
per-case candidate digests, structured parity digests, normalized trace hashes
and kernel summaries, primary transfer byte/time aggregates, failure-probe
hashes and receipts, primary/repeat backend receipts, and final result
self-hash. A nested failure observation must already bind its exact stimulus;
the assembler rejects a cross-wire instead of rewriting owner evidence.

Before linking the absent output, the tool runs the canonical complete
`--candidate-result` validation against a temporary file. Invalid identity,
science/parity, repeat, trace, transfer, failure, speed-gate, or authority
evidence therefore leaves no output. The assembly receipt binds the exact
source-draft and candidate-result hashes, but reports result verification,
device/molecular execution, and every authority as false. It cannot add a
repository digest pin, invoke a command or device, overwrite an artifact, or
turn a candidate into a verified result.

## Maintenance tools

```bash
python tools/inventory_github_actions_pins_v1.py --root . --output actions.json
python tools/analyze_rust_docking_module_boundaries_v1.py \
  --path rust/betelgeuze-runtime/src/docking/mod.rs \
  --output docking-boundaries.json
```

The first tool inventories mutable action refs and risky workflow contexts. The
second generates a read-only extraction map for the large Rust docking module.
Neither tool changes workflows, ABI, receipts, scientific behavior, or release
authority.

## External boundaries

The following remain outside this repository-only development surface:

- real D1 results until the licensed/private 32-case inputs are supplied;
- Fresh-128 access or execution;
- ROCm device execution, VRAM, ROCprofiler, and multi-architecture timing;
- commercial Glide/GOLD execution;
- wet-lab validation;
- production release signing or deployment;
- replacement of the proprietary license without explicit owner approval.
