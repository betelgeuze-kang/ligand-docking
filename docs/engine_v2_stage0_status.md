# Engine V2 public redocking Stage 0 status

## Current decision

`BLIND_RUN_BLOCKED`

The former 298-case primary holdout is invalidated: a hash-verified complete
300-case report existed before the numeric freeze, so all historical cases are
development-only. The replacement 128-case complement was selected from archive
member identities before its result values were inspected. The runner requires
a complete Stage 0 policy for that fresh internal holdout and rejects the old
298-case subset.

## Completed locally

- PR #211 diagnostic contract and its local rc5 follow-ups are present on the
  dedicated `codex/m1-diagnostic-contract` worktree, including the change that
  excludes diagnostic-ledger time.
- The rc5 Python/Rust dual-backend implementation is present in the same
  worktree. The Rust backend is explicit and fail-closed, candidate-local
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
  implemented for repeated guided cycles while retaining exactly 24 uniform
  slots. Targeted checks preserved the observed oracle cases, but the mode
  itself produced no 2 Å candidate, so it remains unpromoted.
- Solo self-review pass records now have a fail-closed generator that requires
  one clean commit/evidence identity and enforces at least 24 hours between
  pass 1 and pass 2 without claiming reviewer independence.
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
- Focused verification: `144 passed`, with seven inotify host-capability tests
  excluded after separate reproduction and classification.
- The current diagnostic/ion/allocation slice added nine focused passing tests,
  passed the Engine V2 architecture guard, compiled all changed Python entry
  points, and passed `git diff --check`.
- The final Python rc5 wheel was built twice with identical SHA-256
  `2ec932023df7497bf06bbb7e7a207912242613e14c367d91db293d513c9a2c6c`;
  a local clean-install import with the previously qualified CPython 3.10
  native wheel succeeded.
- Repository orchestration verifier: `./scripts/ai-verify.sh` passed from the
  main worktree that carries it.

## Blocking inputs

1. **PR integration:** GitHub PR #211 is still `open`; it is not merged into
   `main`. Merge remains a human-owned external repository action.
2. **Scientific development gates:** the last homogeneous, non-smoke 32-case
   historical-development slice binds the seven proposed acceptance values and
   Vina/GNINA margins. Twenty-nine cases reached scoring and the three failures
   are typed unsupported large-ring systems. Preparation unsupported and case
   failure are both 0.09375 against a 0.14375 ceiling, and conditional 64-slot
   coverage is 1.0 against a 0.90 floor. Proposal oracle is 0.06897 against a
   0.49375 floor and invalid Top-1 is 0.79310 against a 0.20 ceiling, so both
   fail. Conditional Top-1 selection failure is exactly 0.50 against a 0.50
   ceiling and Top-5 selection failure is 0.0 against a 0.20 ceiling. Fresh 128
   execution remains blocked by proposal and validity gates. That report binds
   the pre-v2 implementation and therefore remains diagnostic history. A
   current-source non-claimable track-decision slice now contains nine total
   cases, eight scored cases, and 512 candidate rows under one implementation
   hash. Preparation unsupported and case failure are both 0.1111 against a
   0.20 ceiling; coverage is 1.0 against 0.90. Proposal oracle is 0.25 against
   a 0.4556 floor and invalid Top-1 is 0.625 against a 0.20 ceiling, so Stage 0
   still fails. Conditional Top-1 selection failure is 0.50 against 0.50 and
   Top-5 selection failure is 0.0 against 0.20.
3. **Proposal/scorer diagnosis:** 1,856 successful candidate rows across the
   29 scored cases retain canonical binary64 values for all eight terms. Only
   uniform fallback produced 2 Å candidates: 2/1,168, contributing both oracle
   successes. No guided mode produced a 2 Å candidate. The adaptive allocation
   improved the paired common-case oracle event count from one to two and mean
   oracle RMSD by 0.20 Å, but it remains far below promotion level. Automatic
   proposal or scorer promotion remains false, and the report contains no
   fresh-holdout result. In the current-source slice, all native-like candidates
   still came from uniform fallback. The multi-anchor lane produced 28
   candidates with zero native-like and zero valid candidates, so it is retained
   only as an explicit unpromoted development lane.
4. **Refinement/validity diagnosis:** refinement reduced its declared clash
   penalty in 1,819/1,856 candidates, yet `minimum_distance_to_protein` failed
   1,837 times and `volume_overlap_with_protein` failed 1,727 times. Internal
   clash failed 515 times and internal energy failed 562 times. The
   translation-only v1 objective therefore does not close PoseBusters validity.
   Interaction-aware v2 improves targeted validity but does not close the gate;
   internal-geometry and rotational refinement remain unimplemented, and the
   current source has not passed a homogeneous development validity gate.
5. **Full-suite self-review:** a solo operational evidence builder dispositions the 49
   conservative `actual_regression` rows as pre-existing unresolved behavior
   debt and freezes the Engine-required/legacy/product/local-evidence tier
   boundaries. It must be regenerated after the final current-source wheel and
   clean commit exist, then bound by the self-review pass generator.
6. **Exact operator environment:** Python/Torch/RDKit/PoseBusters, GNINA,
   host, native extension, native wheel, Rust identity, and the reproducible
   base wheel are selected together by the operational builder. The environment
   is not frozen for execution until it is rebound to the clean source commit.
7. **Solo governance receipt:** the two self-review passes, separated by at
   least 24 hours, are not yet complete. This blocks internal execution but is
   satisfiable by the sole developer without claiming independence.
8. **Legal/license self-review:** the prior internal review keeps benchmark
   redistribution off and treats GNINA as an internal external-binary
   invocation with redistribution forbidden. It must be rebound in the new
   solo pass; genuine external review remains a later prerequisite for public
   claims.
9. **Issue/CI administration:** GitHub Issue #199 remains `open`. Its recorded
   Cut B reconstruction reduced 13 historical per-round/per-surface workflows
   to three authoritative workflows, and Cuts C/D were reconstructed as
   dependent drafts. The Issue exit condition is not satisfied because the
   replacement cuts are not recorded as merged/closed with independent review.
   The 40 specialized workflows also require an explicit reviewer disposition;
   the attestation has a separate CI-authority approval decision.
   No external issue, PR, required-check, or workflow state was mutated here.
10. **Later native tracks:** `cpp_hip_required` remains an explicit fail-closed
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
