# Engine V2 public redocking Stage 0 status

## Current decision

`BLIND_RUN_BLOCKED`

The former 298-case primary holdout is invalidated: a hash-verified complete
300-case report existed before the numeric freeze, so all historical cases are
development-only. The replacement 128-case complement was selected from archive
member identities before its result values were inspected. The runner requires
a complete Stage 0 policy for that fresh internal holdout and rejects the old
298-case subset.

The canonical capability state is:

| Field | Value |
| --- | --- |
| Historical 300 | contaminated development |
| Fresh 128 | internal provisional blind |
| Fresh 128 executed | false |
| Active refiner | V7 |
| Product promotion | false |
| Public claim | false |

## Completed locally

- PR #211 diagnostic contract and its rc5 follow-ups were squash-merged to
  `main` as `6cd5c26d397de4189ee82c50a24503426a1721da`, including the change that
  excludes diagnostic-ledger time.
- The rc5 Python/Rust dual-backend implementation is present in the merged
  source. The Rust backend is explicit and fail-closed, candidate-local
  native failures retain typed codes, and the holdout runner refuses any
  backend other than `rust_cpu_required`.
- Candidate diagnostics now bind proposal mode, final-coordinate identity,
  exact failed PoseBusters checks, and translation-refinement receipts. The
  development analyzer reports allocation, recovery, validity, duplication,
  score, refinement, and failure decomposition by proposal mode.
- The frozen development policy retains a 37.5% uniform floor and caps each
  available guided mode at eight candidates. A narrowly labeled receptor-only
  Na/Mg/Ca/Co/Zn/Fe vdW proxy lane converts six previously untyped preparation
  failures into scored cases without claiming metal coordination; ligand
  metals remain unsupported.
- Interaction-aware rigid refinement v2 evaluates all candidates, applies
  deterministic backtracking, and bounds total translation at 2.25 Å. On
  three targeted non-holdout cases it raised valid candidates from 4 to 12 and
  eligible candidates from 46 to 67 without losing an oracle event. On the two
  historical oracle cases it improved the oracle from 1.96 to 1.58 Å and
  from 1.55 to 0.91 Å while raising valid candidates from zero to three and
  six, respectively.
- A bounded two/three-constraint `multi_anchor_hotspot` proposal mode is
  implemented for repeated guided cycles while retaining the frozen 37.5%
  uniform floor. The final 32-case development run allocated 84 multi-anchor
  candidates with no 2 Å or valid candidate, so the mode remains unpromoted.
- A `pocket_center_baseline` lane reserves eight of the former guided slots
  without consuming the random-uniform pool. Proposal mode and PRNG scheduling
  remain keyed to the absolute proposal index, so the retained indices are
  reproducible. Across the final 29 scored development cases, 232 centered
  candidates produced three native-like and 12 valid poses, including one
  incremental oracle case and one incremental valid-pose case. The lane is
  development-only and does not authorize a holdout run or product claim.
- Bounded translation/rotation refinement v3 is implemented with a hard pocket
  guard and typed rotation receipt. The V4 ensemble runner applies it only to
  receipt-bound variants while preserving their translation-only V2 sources.
  On the historical 32-case development slice this raised proposal-oracle 2 A
  recovery from 4/29 to 6/29 and exact valid candidates from 52 to 62 without
  reducing Top-1 or Top-5 recovery.
- The broad V5 clearance probe raised exact valid candidates to 77 and reduced
  invalid Top-1 from 72.41% to 65.52%, but regressed mean best-of-Top5 RMSD from
  3.51088 A to 3.56945 A and was not promoted. V6 instead selects expanded
  clearance only for a source-duplicate V3 variant or a receipt-bound near-clear
  variant at or below `2^-12` whose clearance objective strictly decreases
  from its own initial value. The policy uses
  no RMSD or PoseBusters result at runtime and retains the V2 source lane.
- The full V6 historical-development execution reproduced the receipt-only
  policy for all 1,856 candidates with zero scientific-field mismatches and
  retained self-hashed selection payloads for all 456 V3 variants. It selected
  93 clearance variants, raised exact valid candidates from 62 to 73,
  raised cases with any valid candidate from 9 to 13, reduced invalid Top-1
  from 72.41% to 65.52%, and improved mean oracle/Top-1/Top-5 RMSD by
  0.00424/0.13676/0.01500 A versus V4. Oracle and Top-1/Top-5 recovery counts
  stayed 6/1/3. Evidence SHA-256 is
  `1895e818b8e90261051b77359e3b7491fc49a8b0604b5bf5e130aca3a4a28224`.
- V7 layers bounded rotations of authority-proven rotor subtrees after V6 and
  records receptor-plus-internal quartic-overlap moves in nested self-hashed
  receipts. Selecting every improving variant was rejected because mean
  Top-1/Top-5 RMSD regressed by 0.24398/0.20853 A. The frozen development
  hybrid selects only variants whose final receptor penalty is in `[2.0,4.0)`;
  the runtime rule uses no RMSD, PoseBusters result, validity label, or native
  pose and restores exact V6 coordinates outside the window.
- The V7 hybrid historical-development ledger raises exact valid candidates
  from 73 to 76, cases with any valid candidate from 13 to 14, and reduces
  invalid Top-1 from 65.52% to 62.07%. Mean oracle RMSD is unchanged while
  mean Top-1/Top-5 RMSD improves by 0.00785/0.00079 A; recovery counts remain
  6/1/3. Final-code execution of the six affected cases reproduced all seven
  selected indices and 384 candidate outcomes with zero strict mismatches.
  Monotonic selection-window pruning reduced torsion-trial evaluations from
  3,185 to 2,822 with identical outcomes. Generic penalties now compare source
  to final coordinates under one V7 objective, and accepted rotation counts
  include selected torsion steps while retaining rigid/torsion sub-counts. The
  unpruned full probe search runtime was
  descriptively 1.446x V6, so this remains a bounded validity improvement rather
  than a speed claim. Focused refinement/runner/benchmark/Stage 0 verification
  is `148 passed, 7 deselected`; lint, py_compile, diff-check, and orchestration
  smoke also pass. Evidence self-hash is
  `9c89ac550cfc8259cdb236ee9970242c4b06a6d720295078b106b7b9a4ee27e5`.
- The Stage 0 source-freeze contract names one V7 algorithm profile and binds
  runner `2.13.0`, candidate schema `1.6.0`, the complete binary64 V7 config,
  its `5e8b61d2...75337` fingerprint, and the result-independent `[2.0,4.0)`
  selection window. The torsion refiner is required in the source manifest,
  and the report validator consumes the same runner policy fields so an actual
  V7 report does not contradict its frozen execution policy.
- Solo self-review pass records now have a fail-closed generator that requires
  one clean commit/evidence identity and enforces at least 24 hours between
  pass 1 and pass 2 without claiming reviewer independence. A separate
  internal-only policy assembler verifies that hash chain, requires all seven
  development gates to pass, rebinds source/environment/suite/CI artifacts,
  and creates the policy and solo attestation with exclusive mode-0600 writes.
  It emits nothing when pass 2 or any scientific gate is incomplete.
- Separate CPython 3.10, 3.11, and 3.12 native wheels were built in the pinned
  manylinux 2.28 x86_64 image. Two isolated CPython 3.10 builds were
  byte-identical. The 64-candidate synthetic qualification fixture measured
  12.2x scorer speedup while preserving exact rank/Top-5 and 1e-12 term parity;
  this is engineering evidence, not development-corpus qualification.
- A fail-closed Stage 0 policy verifier covers seven acceptance axes, paired
  baseline CI interpretation, descriptive-only runtime, diagnostic branching,
  source hashes, exact environment, artifact counts, full-suite classification,
  governance mode, legal/scientific review decisions, and product isolation.
  It supports either three genuinely independent roles or an explicit
  `solo_developer_controlled` mode with two timestamped self-review passes,
  immutable evidence, no post-result tuning, and public/product promotion off.
- The runner validates Stage 0 before creating/quarantining output and validates
  the same receipt again before materializing a report or partial summary.
- Source freeze requires the admission/classification tools, runner, benchmark
  contract, docking sources, base packaging, native build/SBOM tools, and the
  complete Rust Cargo.lock/build/source closure. Environment freeze additionally
  binds the native wheel and extension hashes, Rust compiler/target/build flags,
  and one-thread execution policy.
- Full pytest was reproduced without holdout execution: `6574 passed`,
  `215 failed`, `3 errors`, `10 skipped`, `2 xfailed`.
- The exact PR #211 head was independently re-run in a detached worktree:
  `6570 passed`, `215 failed`, `3 errors`, `10 skipped`, `2 xfailed`. Its 218
  nonpassing rows exactly match the current reproduction. The PR-body `216/3`
  aggregate is therefore unreproduced and retained as a separate declared fact.
- All 218 nonpassing outcomes have a provisional row-level category and failure
  message SHA-256. The verifier recomputes row count, outcome-kind totals, and
  category totals from those rows. Raw failure text is not copied to the receipt.
- New Stage 0 tests are wired into the existing authoritative
  `ci-engine-v2-main` workflow; no additional workflow was created.
- The CI inventory exposes 43 Engine V2 workflows: three authoritative and 40
  specialized. Specialized workflows are not hidden or treated as approved.
- Focused verification for the current placement/refinement/report slice is
  `131 passed`, with seven inotify host-capability tests deselected only after
  separate reproduction showed the Codex Electron process consuming the
  per-user watch limit. The Engine V2 architecture guard passed, all changed
  Python entry points compiled, and `git diff --check` passed.
- Phase 0-A evidence at exact `main` commit
  `2b98bc93481347ec0736efa7da1d632a28050101` contains two byte-identical V7
  Python rc5 wheel builds with SHA-256
  `e8637d971d92e6990689d0e164f08a860b50f3cfd0ed9472f86deb8cc8379679`.
  Its SPDX SBOM SHA-256 is
  `624838d774b61094f5d5866bbc221436bdb139f92500c3412a9608473943d73e`,
  and the SBOM records that exact wheel checksum. The Phase 0-B capability
  package change postdates those artifacts, so they are historical evidence,
  not the final Stage 0 base wheel/SBOM. Both must be rebuilt and rebound at the
  exact post-merge `main` commit together with the operator/native environment.
- Repository orchestration verifier: `./scripts/ai-verify.sh` passed from the
  main worktree that carries it.

## Blocking inputs

1. **Scientific development gates:** the latest V7 hybrid historical-development
   slice contains 29 scored cases, 1,856 candidates, and the same three typed
   unsupported large-ring preparation failures. Proposal-oracle recovery is
   6/29 (0.20690) against a 0.49375 floor; invalid Top-1 is 0.62069 against a
   0.20 ceiling. Conditional Top-1 and Top-5 selection failure are 0.83333 and
   0.50 against 0.50 and 0.20 ceilings. All four gates remain blocked, so fresh
   128-case execution and promotion remain prohibited. This execution was
   Engine-V2-only because the host inotify watch limit was exhausted; it does
   not claim a new Vina/GNINA comparison or invariance result.
2. **Proposal/scorer diagnosis:** all 1,856 successful candidate rows retain
   canonical binary64 values for all eight terms. The six oracle cases still
   yield only one Top-1 and three Top-5 recoveries, so the scorer-selection
   bottleneck remains. The report contains no fresh-holdout result.
3. **Refinement/validity diagnosis:** V7 increases exact valid candidates and
   valid-case coverage without regressing V6 aggregate RMSD, but only 14/29
   cases contain any valid candidate and invalid Top-1 remains 62.07%. Further
   validity work must generate valid candidates in uncovered cases rather than
   relabel, filter, or abstain around the current pool.
4. **Full-suite self-review:** a solo operational evidence builder dispositions the 49
   conservative `actual_regression` rows as pre-existing unresolved behavior
   debt and freezes the Engine-required/legacy/product/local-evidence tier
   boundaries. It must be regenerated after the final current-source wheel and
   clean commit exist, then bound by the self-review pass generator.
5. **Exact operator environment:** Python/Torch/RDKit/PoseBusters, GNINA,
   host, native extension, native wheel, Rust identity, and the reproducible
   base wheel are selected together by the operational builder. The environment
   is not frozen for execution until it is rebound to the clean source commit.
6. **Solo governance receipt:** the two self-review passes, separated by at
   least 24 hours, are not yet complete. This blocks internal execution but is
   satisfiable by the sole developer without claiming independence.
7. **Legal/license self-review:** the prior internal review keeps benchmark
   redistribution off and treats GNINA as an internal external-binary
   invocation with redistribution forbidden. It must be rebound in the new
   solo pass; genuine external review remains a later prerequisite for public
   claims.
8. **Issue/CI administration:** GitHub Issue #199 remains `open`. Its recorded
   Cut B reconstruction reduced 13 historical per-round/per-surface workflows
   to three authoritative workflows, and Cuts C/D were reconstructed as
   dependent drafts. The Issue exit condition is not satisfied because the
   replacement cuts are not recorded as merged/closed with independent review.
   The 40 specialized workflows also require an explicit reviewer disposition;
   the attestation has a separate CI-authority approval decision.
   No external issue, PR, required-check, or workflow state was mutated here.
9. **Later native tracks:** `cpp_hip_required` remains an explicit fail-closed
    unavailable backend. C++/HIP shadow work, Rust RMSD/clustering extraction,
    the native candidate executor, and bounded native parser are not admitted
    while current proposal and validity gates fail. Product shadow routing
    remains disabled.

## Exit condition

Stage 0 exits for internal provisional execution when the blocked template is
replaced by a policy with real development-evidence hashes and numeric values,
the full-suite and historical-count receipts have recorded self-review,
authoritative tier definitions are frozen, exact Python/Rust source, wheel,
extension, host, and binary identities match, the solo attestation is complete,
and the verifier returns `admitted: true`. The old `primary-blind-holdout`
always fails closed; `fresh-internal-blind-holdout` fails before output creation
until admission. Public claims and product promotion remain false until genuine
external review is later attached.
