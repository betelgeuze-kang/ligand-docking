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

- PR #211 diagnostic contract is present on the dedicated
  `codex/m1-diagnostic-contract` worktree at `3935a1fa`, including the rc4
  follow-up that excludes diagnostic-ledger time.
- The rc5 Python/Rust dual-backend implementation is present in the same
  worktree. The Rust backend is explicit and fail-closed, candidate-local
  native failures retain typed codes, and the holdout runner refuses any
  backend other than `rust_cpu_required`.
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
- Repository orchestration verifier: `./scripts/ai-verify.sh` passed from the
  main worktree that carries it.

## Blocking inputs

1. **PR integration:** GitHub PR #211 is still `open`; it is not merged into
   `main`. Merge remains a human-owned external repository action.
2. **Scientific development gates:** a result-independent 12-case, non-smoke
   historical-development slice now binds the seven proposed acceptance values
   and Vina/GNINA margins. Ten cases reached scoring and two retained typed
   preparation failures. Preparation unsupported and case failure are both
   0.167 and conditional 64-slot coverage is 1.0, so those axes pass their
   proposed 0.20/0.90 gates. Proposal oracle is 0.30 against a 0.317 floor,
   invalid Top-1 is 0.80 against a 0.20 ceiling, and conditional Top-1 selection
   failure is 0.667 against a 0.50 ceiling. Conditional Top-5 selection failure
   is 0.0 and passes its 0.20 ceiling. Fresh 128 execution remains blocked by
   proposal, validity, and fine-ranking gates.
3. **Scorer term diagnosis:** 640 candidate rows across the ten scored cases
   retain canonical binary64 values for all eight weighted terms. `typed_vdw`
   dominates absolute scale and its removal changes Top-1 in 10/10 cases, but
   also removes every observed Top-5 recovery; it must not be weakened from
   this ablation alone. The development analysis is non-claimable and contains
   no fresh-holdout result. A non-negative constrained calibration candidate
   reduced pairwise violation only from 0.325 to 0.317 and left leave-one-oracle-
   case-out Top-1 at 1/3, so automatic scorer promotion remains false.
4. **Refinement diagnosis:** among the 50 retained development Top-5 poses,
   `minimum_distance_to_protein` failed 43 times and
   `volume_overlap_with_protein` failed 29 times; internal clash and internal
   energy each failed 10 times. Increasing translation bounds and adding
   bounded rigid rotation did not produce a valid pose in the diagnostic case
   and worsened chemical validity, so both experiments were reverted. The
   translation-only v1 refiner remains a baseline; a torsion/internal-geometry-
   aware v2 optimizer is required before this gate can close.
5. **Full-suite self-review:** the 49 conservative `actual_regression` rows
   need disposition, and official Engine-required/legacy/product/local-evidence
   tier definitions must be dispositioned. The unreproduced PR-body 216th failure
   also needs an explicit solo-review disposition as non-authoritative or its original JUnit
   must be recovered and classified.
6. **Exact operator environment:** final Python, Torch, RDKit, PoseBusters,
   GNINA binary SHA-256, CPU host, installed native extension SHA-256, native
   wheel SHA-256, and Rust build identity are not yet selected together.
7. **Solo governance receipt:** the two self-review passes, separated by at
   least 24 hours, are not yet complete. This blocks internal execution but is
   satisfiable by the sole developer without claiming independence.
8. **Legal/license self-review:** exact benchmark-file attribution/retention and
   GNINA binary/model conditions still need a recorded self-review. Genuine
   external review remains a later prerequisite for public claims.
9. **Issue/CI administration:** GitHub Issue #199 remains `open`. Its recorded
   Cut B reconstruction reduced 13 historical per-round/per-surface workflows
   to three authoritative workflows, and Cuts C/D were reconstructed as
   dependent drafts. The Issue exit condition is not satisfied because the
   replacement cuts are not recorded as merged/closed with independent review.
   The 40 specialized workflows also require an explicit reviewer disposition;
   the attestation has a separate CI-authority approval decision.
   No external issue, PR, required-check, or workflow state was mutated here.

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
