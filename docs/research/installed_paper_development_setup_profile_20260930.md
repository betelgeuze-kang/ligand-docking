# Synthetic installed paper-development CPU setup profile

The bridge now consumes the original adapter's verified preparation state once
inside one `_preparation` call. It reuses that call's receptor, ligand, declared
parameters and fixed environment for the preparation identity, charge, geometry
and cohort gates. Original and Cartesian admissions still construct their own
systems, authenticated authorities and scorers. No state persists across
candidates, freeze/preflight calls, run/resume or verification. This is a bounded
setup change; no solver, force, score, native graph or optimizer implementation
changed.

The [raw profile](../evidence/installed_paper_development_setup_profile_v1.json)
and [summary with archive pins](../evidence/installed_paper_development_setup_profile_summary_v1.json)
retain the source, input and environment identities, all raw timing attempts,
component calls/completed/failed counts, verified byte counts and exact semantic
comparison results. The source HEAD was
`24c3c3475174695ecd6a6d4b47b17440e7164553`; the baseline bridge SHA-256 was
`dfe8fd99a79608ae6edfcd387b100d03a4f2e5004fd2f8038be7855d98f75891` and the
candidate bridge SHA-256 is
`f9c7a9ee102875c1d738d9b33803ba0d3bc9f389d3ce0d288d9b1d173bea9f04`.

## Complete stage costs

The synthetic receptor has 4,376 atoms, with an authenticated subset of 974.
The two explicit synthetic ligand graphs have 39 and 43 atoms. The receptor is
made from water/methane graphs at duplicated analytic coordinates; ligands are
an alcohol and an amine at analytic coordinates. These inputs represent setup
size only, with no physical target or affinity interpretation. The synthetic
source DOI is `10.1234/synthetic`, and every role/admission boundary remains
null/false. The requested denominator is two in every completed stage.

Three repeats alternate baseline/candidate order. Each repeat performs complete
freeze and complete preflight with and without instrumentation on the same input
bytes and the same 225 original/Cartesian dependency source pins. The 24 primary
stage calls all completed with requested=2, prepared=2, failed=0. Guards recorded
no force, score-term, minimizer or OpenMM Context calls. Scorer construction's
reference intraligand arithmetic is included in setup cost.

| Complete stage, uninstrumented | Baseline median seconds | Candidate median seconds | Median reduction |
|---|---:|---:|---:|
| freeze | 14.315611192 | 13.425046099 | 6.2209% |
| preflight, including its freeze | 14.243262020 | 12.967053424 | 8.9601% |

Freeze ranges were 14.048605436–14.640076592 seconds for baseline and
11.373878950–13.652181072 seconds for candidate. Preflight ranges were
13.106988714–14.917452052 and 11.478099696–13.174467278 seconds respectively.
These are descriptive local synthetic setup measurements, with visible ambient
variation and no confidence interval or real campaign speedup claim.

The runtime was `/usr/bin/python3`, Python 3.10.12, Torch 2.6.0+rocm6.1, NumPy
1.26.4 and RDKit 2022.09.5 from the existing local dependency installation.
The launch was configured with empty GPU visibility and one Torch thread;
CPU binary64 construction, thread count and distribution versions are retained.
The measured environment receipt does not itself retain the CUDA/HIP/ROCR
visibility variable values or launch argv, so the visibility statement is a
launch-setting record rather than an independently reverified environment field.
This is CPU execution with a ROCm-capable imported Torch distribution; it is not
a pure CPU wheel measurement or evidence of HIP performance/parity. No dependency
environment was installed or modified.

## Profile counts and measurement overhead

Counts below are for **one complete freeze or one complete preflight**, including
both candidates. They are not the sum of freeze plus preflight.

| Component | Baseline calls | Candidate calls |
|---|---:|---:|
| verified canonical system decode | 12 | 8 |
| canonical system hash | 96 | 92 |
| scorer constructor | 4 | 4 |

Each decode still performs the canonical payload seal and reconstructed-system
identity checks. The optimization removes two receptor and two ligand decodes
across the pair, instead of skipping those loader checks. It retains the original
binding and separate Cartesian binding exactly. Hashing still freshly traverses
mutable tensor values, shape/dtype, provenance and nested metadata.

The signed instrumented-minus-uninstrumented median differences were -1.8029%
and -0.4801% for baseline/candidate freeze, and -2.6910% and +2.2452% for
baseline/candidate preflight. Ambient variation prevents isolating a fixed true
wrapper overhead from these measurements. Negative differences do not imply
negative overhead. No overhead was subtracted. Component wall/CPU timers are
inclusive and overlap; they must never be summed with each other or with the
complete stage costs. Imports, fixture generation and receipt serialization are
excluded from these stage timers; fixture generation has its own retained timer.

## Integrity and exact output evidence

The original adapter `_admit(_request(request))` is the same path previously
reached by its `input_binding`. Its canonical loader, authority/scorer constructor
and original input/source exit verification remain active. The bridge preserves
its stricter canonical path and single-link raw checks. It freshly verifies the
original source manifest and bytes, receptor fixed identity and ligand authority
identity at preparation exit. Nested article, identity-statement, original charge
XML and preparation evidence bytes are reopened after the Cartesian binding.
Neither a path nor a DOI supplies cache authority.

The 24 primary comparisons comprise **12 complete freeze-output comparisons
and 12 public preflight-summary comparisons**. Freeze comparisons declare only
the changed bridge `runtime_sha256`; all other returned fields, including
requests, bindings, coordinate hex, preparation gates, cohorts, candidate
order/counts and null boundaries, match. Preflight does not return that complete
frozen payload: its public summary matches after excluding `frozen_sha256`.
Those 12 preflight observations therefore do not separately establish equality
of each call's hidden coordinates or bindings. The separate full-freeze raw
pair below directly identifies `runtime_sha256` as its sole payload difference.
These are implementation identity differences, **not timing fields**; there
are no timing fields inside frozen output. The original profile summary's
`all_24_semantic_comparisons_equal` flag retains these distinct comparison scopes.

Two additional full-freeze calls retained both complete raw output objects and
verified that the only raw difference is `runtime_sha256`. Their 12.683455164
and 11.230120931-second capture timings are separate from the primary 24-call
summary. The immutable new
[external archive manifest](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-paper-setup-profile-20260930-wk8rnmr3/manifest.json)
pins the synthetic inputs, baseline and candidate source snapshots, measured
script, raw profiles, full output JSON and compressed full output JSON. Its
SHA-256 is `8a1226aef9830e552088a8013fad6c6feb522ac5a0b1b426e95b0eb619407680`.

The existing whole-freeze window in which a later candidate can change an earlier
candidate's input after that earlier candidate's admission is unchanged. Reuse
is restricted to one preparation and does not lengthen that window. As before,
malformed shared source evidence can abort the whole freeze at the next source
gate outside the per-candidate preparation catch.

## Validation and retained failures

The final focused suite passed **42 tests in 14.95 seconds**, with original
completion/resume/unknown-work assertions retained. New tests verify local reuse
and fresh subsequent calls, exact binding identity, coordinate/tensor/metadata
mutation rejection, same-path byte replacement, nested XML/article/identity and
late source changes, canonical seal rejection, duplicate/nonfinite JSON, and
canonical path/symlink admission. Ruff passed on the bridge, unit tests and
reproduction script. An independent read-only review verified all 220 archive payload hashes,
the source pins, script AST equivalence, compressed raw-output equality and
the timing arithmetic, finding no introduced trust-check weakening. It narrowed
the preflight output and environment-record claims above; it performed no tests
or molecular calls.

An intermediate suite had 35 passes and two failures because
`MolecularIntegrityError` is a RuntimeError and escaped the previous preparation
blocker catch. The final code catches only that specific integrity exception in
addition to the prior exception list, preserving the requested candidate
denominator before row admission. A subsequent suite passed 37 tests before the
five parser/path cases were added. These failed and successful attempts remain
in the summary and archive, rather than being erased.

The [initial baseline profile](../evidence/installed_paper_development_setup_profile_initial_v1.json)
completed four calls. An [intermediate paired profile](../evidence/installed_paper_development_setup_profile_interrupted_v1.json)
was intentionally stopped before repairing the integrity catch: one baseline
freeze completed and the next setup call was interrupted. The interrupted
prepared/failed counts and elapsed time remain unknown, not zero, and that
partial run is excluded from the primary summary.

## Reproduction

The [reproduction script](../../benchmarks/oracles/profile_installed_paper_development_setup_v1.py) is a
formatting-only version of the archived measured script. Their ASTs match exactly,
and their distinct raw hashes are pinned in the summary. The new tool lives in the existing external-oracle research boundary. Its
raw bytes are unchanged by the directory relocation. The retained numerical
scripts stay byte-identical at their historical paths with explicit product
import and Docker-image exclusions. Use a new output path:

```bash
env CUDA_VISIBLE_DEVICES='' HIP_VISIBLE_DEVICES='' ROCR_VISIBLE_DEVICES='' \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 \
  benchmarks/oracles/profile_installed_paper_development_setup_v1.py \
  --baseline-source /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-paper-setup-profile-20260930-wk8rnmr3/baseline-snapshots/installed_paper_development_comparison.py \
  --output /tmp/new-synthetic-paper-setup-profile --repeats 3
```

Original archived receipts, installed wheels, real preparation inputs and real
runs were untouched. No Fresh-128 data, label admission, training, scientific
qualification or native/source-parameter equivalence changed.
