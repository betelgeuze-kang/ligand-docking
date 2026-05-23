# Betelgeuze Harness Run Log

## 2026-05-18T23:25:23+09:00

- Loaded `betelgeuze-harness` skill.
- Classified work as Deep / R3 because it touches commercialization gates, generated artifacts, docs, and verification-heavy evidence.
- Probed repo metadata, dirty worktree, current scorecards, delivery verdict, engine queue, family rollup, and commercialization reports.
- Initial finding: core A0/A1/local-delivery gates are green, but some high-level readiness/gap text still reads like older active-blocker language.

## 2026-05-18T23:36:03+09:00

- Patched readiness/gap/status builders so closed tracked local accounting no longer promotes parked/review-only caveats as active blockers.
- Split gap burndown `blocked_count` into active `blocked_count=0`, `raw_blocked_bucket_count=2`, and `parked_or_review_only_blocked_count=2`.
- Updated wetlab queue summary wording so green queues are not described as still queue-gated.
- Regenerated `runs/commercialization_readiness_current.*`, `runs/commercialization_gap_burndown_current.*`, and `commercialization_status_report.md`.
- Updated README and post-green docs with the current closed accounting semantics.
- Verified targeted smoke: `81 passed in 1.15s`.

## 2026-05-18T23:37:55+09:00

- Clarified GPCR A1 independent-repeat status in `commercialization_status_report.md`: ready-to-run, completed, result-pass, claim-lock, and result-state are now separate fields.
- Regenerated `commercialization_status_report.md`.
- Re-ran the same targeted smoke: `81 passed in 1.10s`.

## 2026-05-20T21:33:45+09:00

- Shifted active harness goal to CASP17 all-current-protein-target structure-prediction tooling.
- Added all-protein launch coverage for T/H protein targets, multimer support gating, external predictor adapter wiring, batch attempt orchestration, backend profile packet, and prediction coverage gate.
- Current local CASP17 target surface: `11` protein targets; launch coverage is `pass` with `11/11` ready rows when the external adapter profile is used.
- Current execution blocker remains fail-closed: `operator_predictor_command_template_missing`; no fake structure generation or CPU fallback was introduced.
- Regenerated CASP17 backend/profile/coverage/batch artifacts and verified targeted CASP17 suite: `59 passed in 12.16s`.

## 2026-05-20T22:54:49+09:00

- Refreshed official CASP17 target watchlist and sequences. Current open selected protein set is `12` targets: `H1321`, `H2324`, `T1331`, `H1335`, `H2312`, `T2313`, `H2338`, `H2339`, `H1340`, `H1343`, `H2319`, `T1342`.
- Kept `H1319` out of the current open submission set because the official human deadline is `2026-05-19`; its earlier local artifact remains non-current fallback evidence only.
- Ran the internal physics backend in `casp17_quality` mode for all `12` current open protein targets under `runs/casp17_prediction_jobs_quality_current`.
- Built quality TS files under `runs/casp17_predictions_quality_current`: `12/12` converted.
- Quality raw gate passed `12/12`; downstream import, validation, internal scorecard, and submission gate all passed.
- Current quality submission gate artifact: `runs/casp17_submission_gate_packet_quality_current.md`, reporting `12/12 submission_go` internally.
- External CASP portal upload/submission remains R4 and was not performed.

## 2026-05-20T22:58:18+09:00

- Tightened CASP TS conversion/validation around multichain format: converter now emits `PARENT N/A` and `TER` per atom-containing chain segment, matching CASP TS guidance for multichain models.
- Added regression coverage for multichain conversion and validation.
- Regenerated `runs/casp17_predictions_quality_current/*TS.pdb` and reran quality TS gate through import, validation, scorecard, and submission gate.
- Verified regenerated files have chain-count-matched `PARENT` and `TER` rows; quality submission gate remains `12/12 submission_go`.
- Verified CASP17 unit suite: `73 passed in 29.08s`.

## 2026-05-20T23:40:31+09:00

- Ran a recursive improvement loop on the 100% internal CASP17 physics lane for the current `12` open selected protein targets.
- Added stronger multichain docking/declash behavior, including a final closest-pair interchain CA separation pass; the H2339 residual C-D interchain clash blocker was closed.
- Added `--internal-emit-backbone-atoms` launch support and made the predictor emit an explicitly labeled CA-anchored compact pseudo-backbone so raw geometry gates can evaluate atom-rich artifacts without pretending to be all-atom refinement.
- Added `tools/build_casp17_internal_physics_accuracy_readiness_packet.py` plus unit coverage for the new proxy gate.
- Regenerated recursive raw PDBs and TS PDBs under `runs/casp17_prediction_jobs_recursive_current` and `runs/casp17_predictions_recursive_current`.
- Recursive raw gate passed `12/12` with GPU evidence required; TS gate converted `12/12` and completed import, validation, scorecard, and submission gate.
- Recursive internal submission gate reports `12/12 submission_go`; accuracy-readiness proxy reports `12/12 pass`.
- Verified focused tests: `15 passed in 17.71s`; full CASP17 targeted unit suite: `75 passed in 29.25s`.
- External CASP portal upload/submission remains R4 and was not performed.

## 2026-05-21T00:14:46+09:00

- Updated CASP17 docs to the current internal-only lane: `docs/casp17_participation_gate_2026-05-21.md`.
- Replaced the older external-adapter-as-primary wording with the active `internal_physics` recursive lane, current 12/12 artifacts, runtime-only author-code policy, pseudo-backbone claim boundary, verification commands, and R4 external submission confirmation block.
- Kept the legacy external adapter documented only as a fail-closed shim outside the current internal-only scope.
