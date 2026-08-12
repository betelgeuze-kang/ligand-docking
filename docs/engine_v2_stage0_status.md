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
- The separately tracked Stage 0 threshold proposal source map contains exactly 36
  source-report hashes: one `engine_v2`, `vina`, and `gnina` receipt identity
  for each of 12 historical cases. The gate-ledger validator now recomputes
  the identical case set for all three engines, requires non-smoke historical
  membership, and binds the sorted case IDs to
  `cba8259f2dd99b1b998903f4edffb4696f0bbdcb758f9c4df15573d29db2a621`.
  Nine IDs overlap the exact source-paired A/B cohort; the threshold-only IDs
  are `7A9E_R4W`, `7MWU_ZPM`, and `7OSO_0V1`. This authenticates the tracked
  source map only: its receipt payloads are not committed, and it neither
  defines nor authorizes a 15-case failure atlas. Its values remain
  `proposed_threshold`, not frozen Stage 0 execution thresholds. A later
  explicit reviewed freeze is required; on the present eight scored cases the
  proposal values would mean oracle recovery `>= 3/8` and invalid Top-1
  `<= 1/8`. The local one-shot A/B Go triggers `2/8` and `4/8` are separate
  experiment-decision criteria and cannot admit Stage 0. The narrative count
  15 is only `29 scored - 14 with any exact-valid candidate`; it is not an exact
  proposal-oracle-uncovered roster. Aggregate-report derivation remains a
  separate supported source mode: it requires absolute JSON paths and unique
  file digests but cannot reconstruct case IDs from filenames. Receipt and
  aggregate modes cannot be mixed, so adding a report cannot bypass an
  incomplete receipt cohort.
- The fail-closed
  [Phase 2.5 failure-cohort admission contract](engine_v2_phase25_failure_cohort_admission_contract.md)
  keeps the authenticated atlas at seven cases. Expansion requires an exact
  historical-only roster, complete per-case diagnostic receipts, a pinned
  archive, and deterministic proposal-oracle-uncovered derivation; neither the
  12-case threshold map nor the narrative remainder 15 satisfies that gate.
  Its machine-readable policy and CI verifier now bind the exact seven/nine-case
  rosters, cross-check the 12-case threshold proposal source map and contaminated-300
  registry, and freeze the local-refinement A/B stop rule. V9/V10 refinement
  work is prohibited until the separately activated, single nine-case clearance
  A/B reaches its frozen decision.
- The Stage 0 source-freeze contract names one V7 algorithm profile and binds
  runner `2.13.0`, candidate schema `1.6.0`, the complete binary64 V7 config,
  its `5e8b61d2...75337` fingerprint, and the result-independent `[2.0,4.0)`
  selection window. The torsion refiner is required in the source manifest,
  and the report validator consumes the same runner policy fields so an actual
  V7 report does not contradict its frozen execution policy.
- A separate self-hashed execution profile binds that algorithm profile to one
  exact fresh-run command: the complete fresh-128 slice (`start=0`, `limit=0`),
  seed `2026073000`, 2,000 bootstrap samples, 300-second external timeout,
  Rust CPU scorer, one-thread resources, and five retained poses. Its
  development provenance must use the exact
  Scorer-v1 analysis schema, contain at least eight scored historical
  contaminated cases, and authenticate every case to a current-source Engine
  V2 receipt, its frozen materialization/input hashes, and 64 typed candidate
  slots with zero fresh-case overlap. Admission reruns analyzer 1.2.0 and
  requires the complete report to match. The profile SHA-256 is carried by
  admission, all 384 case-execution receipts, and the final internal report;
  incomplete or mixed receipt ledgers fail closed.
- A compact development-gate ledger builder now consumes that authenticated
  Scorer-v1 report and its typed results, re-evaluates all seven gates against
  the tracked 12-case threshold proposal source map at
  `config/engine_v2_public_redocking_stage0_threshold_evidence.json`, whose
  pinned artifact SHA-256 is
  `8f6e548bae67e56dbe05e95ae4ac08f4af5b1eb7b8119adc09cb33e366a36ce3`.
  It records exact numerators, denominators, per-case observed blockers,
  PoseBusters failure counts, and proposal/refiner lineage digests. It does not
  duplicate candidate payloads, cannot authorize runtime or fresh execution,
  and labels unproven conformer/orientation causes
  `unresolved_requires_coordinate_replay`. The earlier exact-source nine-case
  V7 receipt bundle at `58b6f5f7e0fc7f2f19c64dee139befc142e05006`
  produced a self-hashed analysis and authenticated ledger; five of seven gates
  pass, while proposal-oracle recovery and invalid Top-1 remain blocked.
- The merge-SHA V8 absolute-clearance A/B at
  `d6ba3afe9b30bfb35efe2c99c13e4e6df5f6ce27` selected 28 existing V3 torsion
  states and reduced protein minimum-distance/volume-overlap failures by 2/4,
  but exact valid candidates stayed 7/512 and invalid Top-1 stayed 5/8. It failed
  its predeclared improvement criterion and is not promoted. The only oracle and
  Top-1 recovery (`6T88_MWQ`) was preserved. Full evidence identities, descriptive
  runtime, archive hash, and the next-action boundary are recorded in
  [the V8 clearance development A/B](engine_v2_v8_clearance_development_ab.md).
- The initial fixed64 true-conformer A/B at
  `3dbe39c786dc00fe149d6f933b4186ab1ced1d89` failed source-compatibility
  admission at 1/9 prepared cases. After exact source-index,
  Kekule/aromatic-representation, declared-valence, and source-byte binding
  repairs, the exact same-SHA A/B at
  `7cfb0216a1476dfe903bd4b176fa5febe8061d7a` prepared and scored the same 8/9
  cases and 512 candidates in both lanes. Exact-valid candidates increased
  7 to 8 and native-like candidates 4 to 6, but both gains were confined to
  the already recovered `6T88_MWQ`; proposal-oracle, Top-1, and Top-5 recovery
  all stayed 1/8, valid Top-1 stayed 3/8, and Engine V2 runtime increased about
  60%. The profile is comparable but rejected for no recovery-breadth gain.
  The evidence, archive identities, and cleanup record are in
  [the true-conformer development A/B](engine_v2_true_conformer_development_ab.md).
- The exact-main source-paired torsion-rescue A/B at
  `754bebb9ddc2fbffdaca5d4143ff515c3b38c032` preserved the 9-case/8-scored-case
  cohort and 512-candidate denominator. All 28 allocated rescue candidates
  retained their parent coordinates, yielding 28 baseline-to-rescue coordinate
  changes but no new rescue-vs-parent state; `torsion_selected` was 0/28.
  PoseBusters exact validity stayed 7/512, native-like candidates stayed 4/512,
  and proposal-oracle, Top-1, and Top-5 recovery all stayed 1/8; selection
  eligibility nevertheless regressed 31 to 30 and native-like selection
  eligibility regressed 3 to 2 in `6T88_MWQ`. The 1.03% accounted-runtime
  decrease is a single-run observation, not a speed claim. The lane is rejected
  and closed; its evidence identities, descriptive runtime, verified archive,
  and cleanup record are in
  [the source-paired torsion-rescue development A/B](engine_v2_source_paired_torsion_rescue_development_ab.md).
- The companion
  [source-paired uncovered failure atlas](engine_v2_source_paired_failure_atlas.md)
  classifies the seven proposal-oracle-uncovered scored cases as five invalid
  Top-1 and two valid-but-nonnative Top-1 cases. Across those cases, 24 rescue
  slots produced 23 evaluations, 22 available variants, and zero selections;
  all 22 available optimized receptor penalties were at or above `4.0`, and
  none entered `[2.0,4.0)`. This is a descriptive scale signal only. It neither
  proves a scale root cause nor authorizes a policy change.
- The follow-up
  [receipt-bound scale-feasibility audit](engine_v2_receipt_bound_scale_feasibility_audit.md)
  binds heavy-atom counts to the exact ligand artifact hashes and evaluates
  only refinement objectives. Reusing the numeric `[2.0,4.0)` bounds after
  heavy-atom normalization places 7/22 available variants inside, but those
  bounds are not calibrated for the normalized objective. Exact lexicographic
  receptor/internal ordering marks all 22 improved and is non-discriminating;
  it also permits internal-penalty increases. No rule or policy was selected.
- Source-paired refinement receipt V1.1 adds forward-only minimum-vdW-surface-
  gap telemetry for the fixed rescue targets. It measures baseline V6 and
  optimized states after V7 selection, binds the radii policy and coordinate
  fingerprints, and enforces a one-million-pair call bound. Pair-bound skips
  record the bound atom counts and exact Cartesian product as unavailable
  telemetry while retaining the V7 result; a skip is valid only when that
  product exceeds the bound. It changes no allocation, candidate, coordinate,
  objective, or selection policy.
  Live cases require one uniform V1.1 receipt version and the frozen default
  vdW-policy fingerprint; V1 remains confined to the exact pinned-archive
  verifier. The pinned V1 historical archive remains clearance-unavailable and
  immutable. The separate historical-development
  [V1.1 clearance audit](engine_v2_source_paired_clearance_v11_audit.md) now
  authenticates 512 uniform V1.1 candidate receipts and 28 measured rescue
  targets with zero pair-bound skips. Across the 24 targets in the fixed seven-
  case uncovered cohort, minimum surface gap improves for 10, is equal for 13,
  and regresses for one; all gaps remain negative. Historical validity and
  recovery counts, zero torsion selections, and the 31-to-30 eligibility
  regression are unchanged. The new 59-member mode-0600 archive compresses
  21,367,212 expanded bytes to 505,161 bytes and is pinned to
  `7a2561f646f3cf5434de6c79ed797073ac1b7e034e4fcd2291755a58128f5e98`.
  This is descriptive telemetry only and selects no rule.
- The source-paired clearance-selection policy is now predeclared, but remains
  caller-supplied-probe shadow logic with
  `activation_evidence_admissible=false`. It cannot activate coordinates or
  support the historical A/B until a new outer activation receipt binds the
  exact V1.1 source receipt, allocation and proposal identity, V6/optimized
  coordinates, clearance/objective/atom/pair/torsion evidence, and complete
  ScorerV1Terms score, term, and rank semantics. The historical PR #242 archive
  lacks that complete scoring receipt and cannot be reused for Top-1/Top-5
  meaning validation.
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

1. **Scientific development gates:** the exact current-source V7 non-smoke slice
   contains 8 scored cases, 512 candidates, and one typed unsupported-large-ring
   preparation failure in the fixed 9-case denominator. Candidate generation,
   case failure, preparation failure, and conditional Top-1/Top-5 selection all
   pass. Proposal-oracle recovery is 1/8 (0.125) against the tracked
   `0.31666666666666665` floor, and invalid Top-1 is 5/8 (0.625) against the 0.20
   ceiling. Five of seven gates pass; the remaining two block fresh-128 execution
   and promotion. This execution is Engine-V2-only and does not claim a new
   Vina/GNINA comparison or invariance result.
2. **Proposal/scorer diagnosis:** all 512 scored candidate rows retain canonical
   binary64 values for all eight terms. The sole oracle case is also the sole
   Top-1 and Top-5 recovery, so proposal coverage—not scorer calibration—is the
   immediate bottleneck. The report contains no fresh-holdout result.
3. **Refinement/validity diagnosis:** only 7/512 candidates across three cases
   are PoseBusters-exact-valid. The result-independent V8 clearance guard improved several
   individual protein-contact checks without creating a valid candidate or
   reducing invalid Top-1. The later source-paired torsion-rescue lane allocated
   28 candidates, selected zero torsion variants, and retained parent coordinates
   for all of them. It gained no recovery or PoseBusters exact validity and
   regressed selection eligibility 31 to 30 and native-like selection
   eligibility 3 to 2 in `6T88_MWQ`. Seven of eight scored cases remain
   proposal-oracle-uncovered: five have an invalid Top-1 and two have a valid
   but nonnative Top-1. Their completed failure atlas finds no selected torsion
   variant and places all 22 available optimized receptor penalties at or above
   `4.0`, outside `[2.0,4.0)`, while leaving conformer, native-relative
   orientation, pocket-boundary, ring, and physical-clearance causes unresolved.
   The completed receipt-bound scale audit finds 7/22 inside the same numeric
   interval only after heavy-atom normalization, while exact lexicographic
   ordering accepts all 22 and therefore does not provide a bounded selector.
   The result-independent clearance shadow rule is predeclared, but its current
   caller-supplied probe cannot serve as activation evidence. Add and review the
   source-bound activation receipt before the single predeclared historical
   A/B can receive separate execution authority; do not execute early, relabel,
   filter, abstain, relax
   thresholds, or open V9/V10 refinement work around the current pool.
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
8. **Issue/CI administration:** GitHub Issue #199 is closed after replacement
   Cuts A-D merged in order as PRs #200-#203 and the Engine V2 feature-stack
   PRs covered by that reconstruction were closed as superseded. Unrelated
   Dependabot PRs #168/#169 are outside that statement. Follow-on Stage 0 work
   is tracked by Issue #216. This administrative closure does not assert Stage 0 admission,
   scientific validity, independent public review, product promotion, or public
   claims. The 40 specialized Engine V2 workflows still require the separately
   modeled CI-authority disposition.
9. **Later native tracks:** `cpp_hip_required` remains an explicit fail-closed
    unavailable product backend. The non-authoritative native ABI now includes
    fixed64 allocation, deterministic SO(3), indexed placement,
    single-anchor placement, and an ABI 1.19 canonical 64-slot producer with
    one shared surface-aware admission batch and receipt-bound placement
    quaternions;
    C++, Rust CPU, `hip_safe`, and `hip_fast` paths are synthetic parity-test
    surfaces only and every execution, reservation, benchmark, product-rank,
    customer-pose, and claim authority bit remains false. These primitives are
    a synthetic native candidate executor but not an admitted molecular or
    Stage 0 executor. Rust RMSD/clustering,
    bounded native parsing, activation/downstream binding, and product shadow
    routing remain unavailable while the proposal, validity, and external
    authority gates fail.

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
