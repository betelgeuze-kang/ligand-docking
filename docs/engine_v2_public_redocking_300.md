# Engine V2 public redocking 300-case contract

> Historical-status correction (2026-07-29): a complete 300-case, 900-row
> report predating the numeric Stage 0 freeze was found and hash-verified.
> Consequently, all 300 cases in this document are development/diagnostic data
> and the former 298-case `primary_blind_holdout` designation is invalidated.
> The runner rejects that historical subset. The result-blind replacement is
> the 128-case complement frozen in
> `config/engine_v2_fresh_redocking_holdout_manifest.json`; it may be used only
> as `fresh-internal-blind-holdout` under solo-development Stage 0 controls.
> It remains internal/provisional until genuine external review exists.

## Scope

This is a frozen, offline evaluation contract plus a local execution tool. The
library contract does not download structures or publish results. The tool
requires operator-supplied copies of the hash-verified public archive, the
published 308-case identifier document, and an exact GNINA binary.

The source is the public PoseBusters paper data:

- paper: `https://doi.org/10.1039/D3SC04185A`
- data record: `https://zenodo.org/records/8278563`
- source license: `CC-BY-4.0`
- paper-data archive SHA-256:
  `495a8f432ee5612c0dfa3cc582829f112bfca3c29dddc2db2c3a8dc7609e721c`
- published 308-case identifier document SHA-256:
  `a69a7b6b9a5a52531933078ef983e6c069e3a987a1d7a733bd7d72cbe1793de6`

The journal reports a 308-case subset after excluding crystal-contact cases
from the original 428-case archive. The Engine V2 contract uses exactly 300 of
those 308 cases to remain within the stated 100–300-case evaluation envelope.
Selection is performed before results by sorting
`SHA256("betelgeuze-engine-v2-posebusters-300-v1:" + case_id)` and retaining the
lowest 300 keys. The final case list is stored in source and protected by its
own SHA-256.

All historical 300 selected cases are now contaminated development data. The
legacy `primary_blind_holdout` scope remains in old receipts only so the runner
can reject it explicitly; it is not a claimable partition. `5SAK_ZRY` and
`5SB2_1K2` remain labeled engineering smoke, and the other historical cases may
be used only for non-claimable development diagnostics. The disjoint frozen
128-case complement is the sole `fresh_internal_blind_holdout` and must not be
opened until Stage 0 admission succeeds.

## Comparable-input and output policy

Every engine must provide exactly one ordered row for every frozen case:

- `engine_v2`
- `vina`
- `gnina`

Each successful row contains exactly five score-ranked poses, each with:

- symmetry-aware heavy-atom RMSD in the fixed receptor frame;
- geometric validity;
- chemical validity;
- exact pose-artifact SHA-256.

Each failed row retains a failure code and runtime. Missing poses turn the
entire engine/case row into a failure, so Top-3 or Top-5 cannot silently use a
smaller candidate budget.

The engines share the frozen receptor, starting conformer, crystal-ligand
pocket source, case seed, one enforced CPU, and five retained output poses.
The frozen, report-validated case seed is
`2026072700 + frozen_case_index`. Public report construction parses `--seed`
from all three retained commands and requires all three values to equal that
case's verified materialization receipt.

The complete archive is SHA-256 verified through one opened file descriptor.
For every case it yields a `VerifiedCaseMaterialization` value binding the exact
archive members and SHA-256 values for `protein.pdb`, `ligands.sdf`,
`ligand.sdf`, and `ligand_start_conf.sdf`. Each value must match the
archive-derived, frozen 300-case receipt manifest and its aggregate SHA-256.
Row reconstruction must supply these values in frozen case order; arbitrary
dictionaries, canonical receipt identities that differ from the manifest, and
agreeing substituted hashes from all three engines are rejected. The Python
type is a validated value object, not an authentication authority, and its
object-creation provenance is not authenticated.

Result rows have a separate fail-closed boundary. The public report builder
does not accept `PublicRedockingCaseResult` values or dictionaries. The runner
must seal each fresh result as an exact
`VerifiedPublicRedockingCaseExecution` receipt. That receipt binds the complete
success or typed-failure row, runtime, five evaluator outcomes and pose hashes
when successful, the case materialization receipt, implementation, evaluation
pipeline, execution environment, command, policy, and disabled cache-read
state. Report construction rechecks every receipt, requires one environment
identity, and cross-checks its implementation, evaluator, and materialization
identities against the report. Replacing a raw row or mutating a sealed row is
therefore rejected before metrics are derived. This in-process typed boundary
prevents unsupported public-API reconstruction; it is not a signature or an
independent execution attestation against a malicious writer running with the
same Python/process authority.

The runner writes each case into an owner-only directory and makes the four
inputs read-only (`0500` directory, `0400` files). It opens all four exactly
once with `O_NOFOLLOW` and checks path/inode/hash identity. Engine V2 and RDKit
read those descriptors directly. PoseBusters receives RDKit molecules decoded
from the pinned SDF/PDB bytes with the exact 0.3.1 redock loading policy.
Engine V2 pose serialization is reopened once with `O_NOFOLLOW`; the exact
pinned bytes from that read are used both for the five pose hashes and for
PoseBusters evaluation. The evaluator never reopens the pose pathname, so a
directory-entry replacement cannot cross-wire hashes from one payload with
RMSD/validity from another.
GNINA/Open Babel requires `.pdb`/`.sdf` suffixes to select a format, so each
external launch receives suffix-bearing, read-only hard links to the same
pinned inodes through an inherited private-directory descriptor. The alias
directory and every link are revalidated around each launch; a Linux inotify
watch makes any alias entry, input inode, write, or attribute mutation
fail closed, including swap-and-restore. Logical canonical paths remain in
retained commands. Descriptor and pathname identity are checked again before
persisting a row and before exact-file cleanup. A pathname swap cannot select
different input bytes for a consumer.

Their exact pocket geometry is not equal: Engine V2 uses a sphere derived from
the crystal ligand, while Vina and GNINA use the corresponding ligand-derived
axis-aligned autobox. Their internal search effort is also not equal: Engine V2
scores 64 bounded guided proposals and exports the best five, while the
external engines use their own `exhaustiveness=1` search. The report therefore records
`same_ranked_pose_count: true` and `same_pocket_source: true`, but keeps
`same_pocket_geometry`, `same_search_effort_budget`, and
`search_effort_comparable` false. Paired recovery deltas are descriptive under
these explicit settings, not equal-region or equal-compute performance claims.

For Engine V2, the diagnostic contract retains all 64 predeclared candidate
slots in proposal-index order. Every successful candidate binds its proposal
mode, proposal and final-coordinate fingerprints, Scorer v1 scalar, score-term
receipt, H-bond count, canonical pose artifact, symmetry-aware RMSD, and
PoseBusters geometric/chemical validity. It also retains the exact ordered
PoseBusters check IDs that failed and the interaction-aware rigid-translation
refinement receipt, including initial/final clash penalty, accepted steps,
original validity, and total translation. Failed slots retain their proposal mode when placement
reached that point.
Failed slots retain a search error and remain in the denominator. The
score-ranked first five candidate diagnostics must reproduce the published
five-pose result row exactly; a separately substituted diagnostic or result row
is rejected even if it is resealed as a fresh execution receipt.

The guided allocator keeps at least 37.5% of the 64 slots for uniform fallback
and caps each available guided mode at eight slots. This is a deterministic
development policy, not a learned selector. Report and development-analysis
rows separate allocation, native-like recovery, validity, exact duplicates,
oracle contribution, score distribution, refinement response, and failed
PoseBusters checks by proposal mode. Repeated donor/acceptor or charge cycles
may use the explicit `multi_anchor_hotspot` mode, which fits two or three
bounded polar, charge, or hydrophobic constraints while preserving the 24-slot
uniform floor. This mode is provisional and has no automatic promotion path.

Runtime covers each engine invocation through ranked-pose serialization and
stops before the shared PoseBusters evaluator. Torch intra-op and inter-op
threads are both fixed to one for Engine V2, and both external modes receive
`--cpu 1`. The external timeout is part of the policy, engine identity, and
per-case row receipt; changing it produces a different receipt. Runtime
deltas remain descriptive because the search regions and algorithms differ.
They are not process-boundary comparable: each external case includes fresh
process startup and model loading, while Engine V2 reuses one imported Python
process. The report therefore records `runtime_boundary_comparable: false`.
The all-candidate Engine V2 diagnostic serialization and PoseBusters pass is
timed separately and subtracted from Engine V2 runtime, so diagnostic
instrumentation does not inflate the engine runtime row.
Row receipts also include a SHA-256-only execution-environment identity
covering the boot session, OS/kernel, machine architecture, Python executable,
Torch, logical CPU count, CPU affinity/model, selected runtime-variable hashes,
and loaded shared-file identities. A missing boot-session ID is never replaced
with a hostname.
More strongly, the current runner never reads row JSON back as a cache: an
adjacent self-hash cannot authenticate runtime or evaluator outcomes. Every
invocation therefore produces fresh timed rows, whether or not a boot ID is
available.

The operator-supplied GNINA executable is copied into a private `0700`
directory under the output root, using its SHA-256 as the staged filename. The
runner opens that non-writable file once and launches both version probes and
engine processes through Linux `/proc/self/fd/<fd>` with the descriptor
inherited explicitly. Retained commands continue to identify the logical
SHA-256-named staged path. The path and open descriptor must retain the same
device/inode identity, non-writable mode, and SHA-256 before and after every
external-engine launch and immediately before report materialization. A
pathname swap therefore cannot select another inode for launch; persistent or
verification-boundary-visible path, inode, mode, or hash changes abort the
evidence run. Transient same-inode mutation by root or a malicious process with
the same UID is outside this local POSIX threat model.

The output root and every managed descendant are opened component by component
with `O_DIRECTORY | O_NOFOLLOW`; the output root is owner-only `0700`.
Descriptor-anchored atomic writes cannot traverse a symlink ancestor. External
pose output is created through an inherited pose-directory descriptor, and
temporary external-input aliases are removed by exact directory-FD operations.
At the start of every invocation, an existing canonical
`public-redocking-report.json` is atomically renamed to a unique retained stale
artifact before any preflight can fail; the canonical name stays absent until
a new all-300 run succeeds. Existing Engine V2 pose output is quarantined the
same way before a fresh case attempt, so a failure row cannot coexist with an
old canonical success pose.
Input cleanup unlinks only the four expected filenames before removing an
already verified empty case directory. Unexpected entries abort cleanup.

The exact Torch build must be one of the repository's pinned 2.6.0,
2.6.0+cpu, or 2.6.0+rocm6.1 build identifiers and is retained in every Engine
V2 row and engine identity.

Engine V2 preparation assigns explicit claim-blocked charges before Scorer v1:

- ligand atoms use RDKit 2022.09.5 Gasteiger charges with 12 iterations,
  including implicit-hydrogen charge and an exact formal-charge conservation
  correction;
- receptor atoms use a deterministic standard-residue formal-charge proxy for
  Asp, Glu, Lys, Arg, and protonated His, while preserving explicit input
  formal charges elsewhere.

These charge methods are functionality-enabling proxies, not calibrated
force-field charges or scientific validation. The offline benchmark exports
the five lowest-score successfully computed Engine V2 proposals even when the
product-path validity filter would reject them; the shared PoseBusters
geometric and chemical validity columns retain those failures instead of
turning them into missing cases.

## Required outputs

The scorecard emits deterministic percentile-bootstrap confidence intervals
for:

- symmetry-aware Top-1, Top-3, and Top-5 RMSD success at 2 Å;
- Top-1, Top-3, and Top-5 joint RMSD plus geometric/chemical validity success;
- top-pose geometric and chemical validity;
- full-case failure rate;
- median runtime;
- heavy-atom size subgroups: 1–20, 21–40, and 41+;
- rotor subgroups: 0, 1–4, and 5+;
- ring subgroups: acyclic, one ring, and two or more rings;
- Engine V2 preparation and complete partial-charge coverage;
- Engine V2 candidate-generation coverage across the fixed 64-slot
  denominator;
- Engine V2 proposal-oracle and validity-aware proposal-oracle recovery;
- Engine V2 Top-1 scoring-regret and Top-5 selection-regret event rates and
  median RMSD regret;
- Engine V2 donor/acceptor feature coverage and Top-1 realized H-bond rate;
- paired Engine V2 deltas against Vina and GNINA for recovery, valid recovery,
  failure rate, and runtime.

Heavy-atom count, rotor subgroup, and ring subgroup are frozen from each
source-bound ligand artifact using RDKit 2022.09.5, strict
`Lipinski.NumRotatableBonds`, and `rdMolDescriptors.CalcNumRings`. The
heavy-atom/rotor profile rows, ligand-artifact SHA-256 values, and case-ordered
ring counts have separate aggregate SHA-256 identities. Engine V2 admission
and its chemistry-aware rotor policy remain separate execution outcomes; an
unsupported macrocycle must become a failure row rather than being removed
from the denominator.

The proposal oracle is the minimum PoseBusters symmetry-aware RMSD across all
successfully generated Engine V2 candidates. Top-1 scoring regret is
`score-rank-1 RMSD - proposal-oracle RMSD`; Top-5 selection regret is
`best score-ranked Top-5 RMSD - proposal-oracle RMSD`. Their event rates use
the full case denominator and count cases where the oracle reaches 2 Å but the
respective selected set does not. Median RMSD regret uses cases with the
required candidate outcomes. These are failure-decomposition diagnostics, not
performance acceptance thresholds.

Complete charge coverage requires a finite explicit partial charge for every
prepared receptor and ligand atom. H-bond feature coverage requires at least
one complementary ligand-donor/receptor-acceptor or
ligand-acceptor/receptor-donor pair in the fixed Scorer v1 context. It is a
feature-availability diagnostic, not evidence that a native interaction is
correctly reproduced.

Receptor Na, Mg, Ca, Co, Zn, and Fe atoms may enter a narrowly declared
non-coordination vdW proxy lane so their presence does not become an untyped
preparation failure. The diagnostics count proxy ions and state explicitly
that coordination is not modeled. Ligand metals remain unsupported and fail
closed into a separate applicability lane.

Missing Engine V2 proposals and incomplete five-pose serialization raise the
typed `IncompleteRankedPoseSet` case failure. The evidence code is selected
from the exception class, not from mutable error-message substrings. Frozen
report failure codes also include `engine_v2_input_unsupported`, which the
runner emits for typed PDB/SDF/Unicode input-parse failures.

The report binds exact engine version, full Engine V2 Python source-closure or
external binary SHA-256, command, CPU/timeout policy, cohort fingerprint, policy
fingerprint, all 300 verified materialization receipts, all 900 engine/case
execution receipts and their derived rows, profiles, and metric rows. Evaluator or
artifact-I/O failures abort the run instead of being counted as engine
failures; this includes atomic pose writes, output pinning, regular-file checks,
and serialized-pose round-trip checks. Report construction independently rejects
row-level CPU, Torch
thread, exact Torch build, timeout, or engine-mode command fields that
contradict the report policy and engine identity. Case-specific receptor,
ligand, and pocket/autobox path basenames are tied to the retained case ID.
PoseBusters validity cells must all be evaluated Python booleans before any row
reduction; missing, errored, or non-boolean cells abort the evidence run instead
of becoming truthy or being masked by an earlier failure. Before rerunning an
invalidated external receipt, the runner moves any old pose file to a
timestamped `.stale-*` evidence file and requires the new process to create a
fresh output.

## Local execution

The evaluator is frozen to NumPy 1.26.4, pandas 2.3.3, PyYAML 6.0.3, RDKit
2022.09.5, and PoseBusters 0.3.1. All five installed distribution versions and
the aggregate SHA-256 over every installed-file record are verified before case
execution and included in the evaluation-pipeline identity. Install the older
RDKit distribution first and install PoseBusters without dependency resolution
so pip does not replace it with a newer `rdkit` distribution:

```bash
python3 -m pip install numpy==1.26.4 pandas==2.3.3 PyYAML==6.0.3 \
  rdkit-pypi==2022.9.5
python3 -m pip install --no-deps posebusters==0.3.1
```

The fresh 128-case internal provisional blind holdout cannot be run from the
protocol file alone. The current machine authority is the tracked
`config/engine_v2_public_redocking_stage0_threshold_evidence.json`, whose frozen
inner `evidence_sha256` is
`8f6e548bae67e56dbe05e95ae4ac08f4af5b1eb7b8119adc09cb33e366a36ce3`.
That artifact was derived from 12 historical development cases and freezes the
proposal-oracle floor at `0.31666666666666665`. The separate V7 narrative that
used a `0.49375` floor is not the current machine authority; this mismatch is a
blocker until reviewed replacement evidence and policy bindings are frozen.
The threshold-evidence template is therefore only an input to such a reviewed
replacement, not an interchangeable runtime artifact. The verifier
cross-checks all seven proposed threshold values and both paired-baseline
margins against the tracked authority; a generic literature note or unrelated
file hash cannot satisfy the gate. Then copy
`config/engine_v2_public_redocking_stage0_freeze.template.json`, bind the
evidence path/SHA-256, and fill the remaining fields. The solo policy builder
constructs one self-hashed execution profile from the exact Scorer-v1
development report and its current-source Engine V2 case receipts. Admission
requires the exact analysis schema, at least eight scored contaminated cases,
the complete typed 64-slot diagnostics, frozen materialization/input hashes,
and a mechanically disjoint fresh cohort. The verifier reruns analyzer 1.2.0
from those receipts and requires the entire report to match; a self-described
report is rejected. Before changing proposal or refinement behavior, build the
compact development-gate ledger from a current-source V7 report:

```bash
python3 tools/build_engine_v2_stage0_development_gate_ledger.py \
  --repo-root . \
  --development-report .betelgeuze/stage0-development/v7-analysis.json \
  --expected-development-report-sha256 OPERATOR_REVIEWED_SHA256 \
  --threshold-evidence \
    config/engine_v2_public_redocking_stage0_threshold_evidence.json \
  --expected-threshold-evidence-sha256 \
    8f6e548bae67e56dbe05e95ae4ac08f4af5b1eb7b8119adc09cb33e366a36ce3 \
  --output .betelgeuze/stage0-development/v7-gate-ledger.json
```

The output is canonical, self-hashed, exclusive mode-0600 state under
`.betelgeuze/`; owned output-parent directories are normalized to mode 0700.
It stores exact gate counts and per-case observed blocker IDs,
but compresses full candidate and refinement lineage into SHA-256 identities;
the authenticated source receipts remain the detailed evidence. Fresh or smoke
cases, report drift, receipt relabeling, and threshold claim-boundary drift fail
closed. Geometry causes that cannot be proved from diagnostics remain
`unresolved_requires_coordinate_replay`.

Print the SHA-only host snapshot:

```bash
python3 tools/verify_engine_v2_public_redocking_stage0.py \
  --policy /path/to/stage0-freeze.json \
  --print-host-environment-json
```

Copy this OS/kernel/CPU-affinity/model/Python-executable/runtime-variable
snapshot into `environment_freeze.host`; runtime-variable values are never
printed. Stage 0 supports two governance branches: a genuinely independent
three-role attestation, or the internal-only `solo_developer_controlled` path
with two immutable self-review passes separated by at least 24 hours. The solo
path is the current internal execution route and cannot support public claims
or product promotion. Before attaching a three-role attestation, compute the
exact review-subject hash:

```bash
python3 tools/verify_engine_v2_public_redocking_stage0.py \
  --policy /path/to/stage0-freeze.json \
  --print-review-subject-sha256
```

For independent governance, the reviewer supplies that hash, distinct
author/reviewer/operator identities, every required decision, and a UTC
timestamp in an independent attestation. For solo governance, use the
fail-closed solo evidence, self-review, and policy builders; they bind both
time-separated passes and emit the internal-only attestation without claiming
reviewer independence. Then compute or verify the policy's canonical self-hash:

```bash
python3 tools/verify_engine_v2_public_redocking_stage0.py \
  --policy /path/to/stage0-freeze.json \
  --print-computed-policy-sha256
```

After writing that value to `policy_sha256`, verify the complete freeze against
the exact repository source and GNINA binary:

```bash
python3 tools/verify_engine_v2_public_redocking_stage0.py \
  --policy /path/to/stage0-freeze.json \
  --output-root .betelgeuze/public-redocking-300 \
  --gnina /path/to/gnina
```

The verifier is deliberately fail-closed. It requires all seven metric axes,
paired Vina/GNINA non-inferiority margins and CI rules, descriptive-only
runtime treatment, diagnostic branch rules, non-smoke/non-holdout provenance
artifacts, source hashes, exact Python/Torch/RDKit/PoseBusters/GNINA identity,
900 engine rows, 19,200 candidate slots, row-level classification of the
reproduced full-suite outcomes, explicit reconciliation of the declared
`216 failed / 3 errors` aggregate, legal/license review, and either distinct
author/reviewer/operator roles with an independent attestation or the bounded
two-pass solo governance contract. An unreproduced declared row may never be
synthesized to make the counts match. The template is not runnable evidence and
must remain blocked while any value is unknown.

Run against operator-supplied source artifacts and a local GNINA executable:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --gnina /path/to/gnina \
  --stage0-policy /path/to/stage0-freeze.json \
  --output-root .betelgeuze/public-redocking-300
```

Use the two already observed cases for engineering smoke:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --gnina /path/to/gnina \
  --output-root .betelgeuze/public-redocking-300 \
  --case-subset engineering-smoke
```

Historical `engineering-smoke`, `contaminated-development`, and `all` subsets
are development-only and cannot be promoted. The runner rejects
`--case-subset primary-blind-holdout`. The only blind execution scope is
`--case-subset fresh-internal-blind-holdout`; it requires `--stage0-policy` and
the exact frozen seed, timeout, bootstrap count, and Rust CPU scorer:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/fresh-128-archive \
  --source-identifiers /path/to/frozen-source-identifiers \
  --gnina /path/to/gnina \
  --stage0-policy /path/to/stage0-freeze.json \
  --output-root .betelgeuze/fresh-redocking-128 \
  --case-subset fresh-internal-blind-holdout \
  --engine-v2-scorer-backend rust_cpu_required \
  --seed 2026073000 \
  --timeout-seconds 300 \
  --bootstrap-samples 2000 \
  --start-index 0 \
  --limit 0
```

To rematerialize the exact historical non-smoke development slice used for
current-source Engine V2 receipt authentication, run the internal engine only:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root .betelgeuze/stage0-development/current-source-nine \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only
```

This narrow lane rejects GNINA, Vina, Stage 0 admission, every other selection,
the two engineering-smoke cases, and all frozen holdout cases. Engine V2 reads
hash-verified, write-sealed Linux memfd snapshots, so the lane creates neither
external aliases nor inotify watches. Its dedicated single-engine summary is
development evidence only: it contains no paired-baseline metrics and every
claim, validation, and promotion flag remains false.

To compare the development-only V8 clearance guard against the retained V7
evidence, use a different output root and add the explicit variant flag:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root .betelgeuze/stage0-development/v8-clearance-nine \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --development-v8-clearance-variant
```

V8 preserves the same 64-candidate budget, proposal lineage, scorer, and exact
historical case denominator. It retains V7 output unless an already evaluated
torsion state outside the V7 `[2.0,4.0)` selection window strictly improves the
minimum receptor van-der-Waals surface gap while the raw minimum distance and
receptor/internal objectives do not regress. Selection does not consume RMSD,
PoseBusters, native-pose, or ranking-score results. The flag is rejected outside
the exact sealed nine-case development lane, produces a distinct nonclaimable
summary, and cannot satisfy Stage 0 admission. V7 remains the active Stage 0
profile until a later evidence review explicitly promotes and refreezes a
replacement; fresh-128 execution remains prohibited.

To execute the fixed 64-slot source-bound true-conformer profile, use another
new output root and the mutually exclusive true-conformer flag:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root .betelgeuze/stage0-development/true-conformer-nine \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --development-true-conformer-profile
```

This lane requires the proposal batch, guided receipt, and full fixed-profile
provenance receipt as one authenticated triplet. It writes a separate
development-only case receipt for every case and rejects any use outside the
exact historical slice. The initial exact-SHA experiment failed closed before
geometry comparison because source-bound conformer preparation failed for 8/9
cases. After source-index, aromatic-representation, declared-valence, and
source-byte binding repairs, the post-compatibility exact-SHA rerun prepared
and scored the same 8/9 cases and 512 candidates as V7. Exact-valid candidates
increased 7 to 8 and native-like candidates 4 to 6, but only inside the already
recovered `6T88_MWQ`; proposal-oracle, Top-1, and Top-5 recovery all remained
1/8 while Engine V2 runtime increased about 60%. The profile is therefore
comparable but rejected for no recovery-breadth gain. See
[`engine_v2_true_conformer_development_ab.md`](engine_v2_true_conformer_development_ab.md).

The completed bounded torsion-rescue experiment reused the ordinary
source-paired V3 proposal objects while changing only which existing child rows
could enter torsion rescue. It remains reproducible only on the same historical
nine-case Engine-V2-only slice, in another new output root:

```bash
python3 tools/run_engine_v2_public_redocking_300.py \
  --archive /path/to/posebusters_paper_data.zip \
  --source-identifiers /path/to/posebusters_pdb_ccd_ids.txt \
  --output-root .betelgeuze/stage0-development/source-paired-torsion-rescue-nine \
  --case-subset all \
  --start-index 2 \
  --limit 9 \
  --development-engine-v2-only \
  --development-source-paired-torsion-rescue
```

The allocator keeps exactly 64 candidates and all original proposal objects
and coordinates. When the authenticated ligand authority contains a rotor, it
selects at most four existing V3 target-parent pairs by rounded even spacing
over ordered target indices. Selected children receive the distinct
`uniform_torsion_rescue_variant` lineage; their retained
`uniform_fallback` parents remain unchanged and cannot overlap the ordinary V3
target-parent union. Allocation does not consume RMSD, PoseBusters, native
coordinates, score, rank, case identity, or prior outcome data.

One hashed provenance receipt binds the fixed policy, authenticated allocation,
baseline and reclassified guided receipts, and all 64 candidate IDs, proposal
fingerprints, coordinate fingerprints, and torsion-metadata hashes. The refiner
derives both eligible child sets from that typed allocation and verifies its
authority receipt, rotor count, policy, and denominator. Success and
whole-search failure diagnostics retain the same proposal receipt and the full
mode/source/parent ledger; source-paired refinement receipts are cross-checked
against it. The flag is mutually exclusive with V8 and true-conformer
development, is rejected outside the exact historical slice, and remains
nonclaimable, non-promotable, and ineligible for Stage 0 or fresh-128 execution.
The exact-main same-source A/B allocated 28 rescue candidates but selected no
torsion variant; all 28 rescue outputs duplicated their retained parents.
Native-like and PoseBusters-exact-valid counts stayed 4/512 and 7/512, and
proposal-oracle, Top-1, and Top-5 recovery stayed 1/8. Selection-eligible
candidates regressed 31 to 30 and native-like selection-eligible candidates
regressed 3 to 2 in `6T88_MWQ`, so the lane was rejected. The 1.03% accounted
runtime decrease is a single-run historical observation, not a speed claim. See
[`engine_v2_source_paired_torsion_rescue_development_ab.md`](engine_v2_source_paired_torsion_rescue_development_ab.md).
The compact companion
[failure atlas](engine_v2_source_paired_failure_atlas.md) records the seven
remaining proposal-oracle-uncovered cases and the observed `24/23/22/0`
rescue/evaluation/available/selected partition. It does not change the runner,
selection window, active profile, or claim boundary.

Argument drift is rejected before output creation. The policy is verified
again before report materialization, and its execution-profile SHA-256 must be
present in every case receipt and the complete 384-row internal report ledger.
The fresh 128 has not been executed, and the active refiner is V7. Product
promotion and public claims remain false. Historical partial summaries created
with `--limit` remain non-claimable and cannot later be promoted by cache reuse.
Every partial-summary filename includes a digest of the exact ordered case
selection, so equal-length slices cannot overwrite one another.

For backward report-schema compatibility, historical 300-case reports and
partial summaries may still serialize `primary_blind_holdout` or
`primary_blind_holdout_partial` as an `analysis_scope`. Those are legacy field
values only: every such artifact is contaminated development evidence, remains
`claim_safe=false` (and partial summaries remain
`primary_claim_eligible=false`), and cannot authorize or identify a blind run.
Fresh-128 reports use only `fresh_internal_blind_holdout`.

Per-case receipts reject changed input bytes, materialization
receipts, seeds, commands, implementation hashes, evaluator/environment
identities, result outcomes, or source identities. Partial summaries retain
both the derived rows and their sealed execution receipts.

The SHA-256 stored beside a local row detects corruption and binds the declared
content to its local execution identities, but it is not a signature: a
malicious writer with the same filesystem authority can replace both a row and
its checksum. The runner therefore never accepts it for cache reuse. Likewise,
report fingerprints and validated Python values provide content consistency,
not independent provenance attestation. Claim-bearing use still requires
controlled execution, retained artifacts, and independent review; the generated
report remains `claim_safe: false`.

## Current boundary

No raw structure, prepared input, external-engine output, Engine V2 output, or
benchmark result is committed by this change. A constructed report records
`benchmark_executed: true` because all 900 schema-valid, failure-complete rows
exist for the historical contaminated 300-case development cohort. It does not
mean that the fresh 128-case internal provisional blind holdout was executed;
that state remains false. This field is not an authenticated process-execution
attestation. The report continues to state:

```text
scientifically_validated: false
benchmark_validated: false
product_qualified: false
claim_safe: false
```

Actual execution is local under the frozen policy. The runner verifies and
materializes the archive itself and retains per-case command/input/result
receipts. A completed report still requires scientific review before any claim.
