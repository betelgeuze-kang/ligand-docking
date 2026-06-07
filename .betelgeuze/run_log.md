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

## 2026-05-22T21:46:22+09:00

- Resumed after the CASP17 commit/push and shifted active local work to the open priority3 wet-lab render/export handoff.
- Regenerated the SARS-CoV-2 Mpro, CA IX, and T. cruzi PDE render suites.
- Patched priority3 gate refresh, runtime runbook, and execution console builders so a fully resolved serialized run hands off to partner send-round review instead of stale start/advance instructions.
- Patched partner export, outbound priority board, and send-round builders so external outreach remains behind explicit R4 confirmation language.
- Added the new target-specific condition/selectivity/assay/go-no-go/export artifacts to the DNDi/IPK, oncology, and READDI attachment lists.
- Regenerated partner export bundle, outbound priority board, partner send round, gate refresh, runtime runbook, and execution console artifacts.
- Verified focused wet-lab priority3/partner regression suite: `12 passed in 1.60s`.
- Verified broader priority3/partner/outbound regression suite: `27 passed in 2.70s`.
- No external partner dispatch, CASP submission, commit, or push was performed in this step.

## 2026-05-22T22:16:03+09:00

- Refreshed the official CASP17 target surface: current open selected protein targets are now `14`, not the previous `12`.
- Closed/excluded `H1321` and `H2324` from the current set and added `H1344`, `H2321`, `H1346`, and `H1347`.
- Materialized `14/14` current FASTA files and rebuilt the all-protein internal-physics launch packet.
- Improved the internal predictor with a target-leak-free FASTA composition compaction prior for hydrophobic, charged, net-charge, and breaker-rich chains.
- Fixed `run_casp17_prediction_batch_gate.py` so recursive prediction/import/validation/scorecard/submission paths can be passed through to target attempts.
- Regenerated internal raw PDBs and CASP TS files for the 14 current targets under the recursive current run directories.
- Rebuilt raw gate, TS gate, import, validation, scorecard, submission gate, and accuracy-readiness artifacts; final recursive gate reports `14/14 submission_go` and `14/14 accuracy_readiness pass`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` with the 2026-05-22 current target surface and evidence.
- Verified focused CASP17 predictor/batch/readiness tests: `10 passed in 8.61s`.
- Verified full CASP17 unit suite: `77 passed in 30.32s`.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-22T22:25:14+09:00

- Added `tools/build_casp17_structure_render_packet.py` to render current internal TS predictions as local 3D CA-trace PNG/SVG images, a contact sheet, and an HTML gallery.
- Generated `14/14` current CASP17 protein target renders under `runs/casp17_structure_renders_current`.
- Generated `runs/casp17_structure_render_contact_sheet_current.png`, `runs/casp17_structure_render_gallery_current.html`, and `runs/casp17_structure_render_packet_current.*`.
- Visually inspected the contact sheet and one multichain render; the image artifacts are nonblank and chain-colored.
- Updated CASP17 participation docs with the render command and visual-artifact evidence.
- Verified full CASP17 unit suite including the new render test: `78 passed in 30.34s`.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-22T22:45:08+09:00

- Added `tools/build_casp17_molecular_viewer_packet.py` for a local interactive molecular viewer packet over current internal TS PDBs.
- Added `tests/unit/test_build_casp17_molecular_viewer_packet.py` to verify target parsing, chain/residue/atom counts, embedded 3Dmol controls, Mol* URL handoff logic, and viewer-copy author redaction.
- Generated `runs/casp17_molecular_viewer_current.html` and `runs/casp17_molecular_viewer_packet_current.*`; the packet reports `14/14` ready and `0` blocked targets.
- Verified the embedded viewer copy redacts `AUTHOR` records while leaving source TS files untouched.
- Ran Chrome headless against the local HTML and generated `runs/casp17_molecular_viewer_smoke_current.png`; pixel checks confirmed a nonblank WebGL render.
- Updated CASP17 participation docs and harness state with the molecular viewer artifacts and limitations.
- Verified focused render/viewer tests: `2 passed in 0.64s`.
- Verified full CASP17 targeted unit suite: `79 passed in 30.88s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-22T22:50:30+09:00

- Upgraded the molecular viewer packet with CA geometry issue metrics and an optional issue overlay for CA continuity gaps and non-neighbor CA close contacts.
- Regenerated `runs/casp17_molecular_viewer_current.html` and `runs/casp17_molecular_viewer_packet_current.*`; the packet still reports `14/14` ready and `0` blocked targets.
- Current viewer-side geometry triage reports `0` CA continuity gaps and `2265` CA close-contact markers across the 14 current targets.
- Reran Chrome headless smoke on the upgraded viewer; `runs/casp17_molecular_viewer_smoke_current.png` is nonblank with `98,959` nonwhite pixels and `70,918` colorful pixels.
- Verified focused render/viewer tests: `2 passed in 0.64s`.
- Verified full CASP17 targeted unit suite: `79 passed in 30.43s`.
- Next internal accuracy target is reducing the close-contact markers; no local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-22T22:53:53+09:00

- Strengthened the internal predictor finalization path with a larger intrachain CA declash pass for newly generated models.
- Added regression coverage that verifies finalization reduces nonlocal CA close contacts while keeping CA continuity inside the local geometry window.
- Verified predictor-focused tests: `6 passed in 8.40s`.
- Verified full CASP17 targeted unit suite: `80 passed in 30.63s`.
- Current TS/viewer artifacts were not regenerated after this predictor change; regenerate the 14-target internal lane before comparing close-contact counts.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-22T23:34:59+09:00

- Strengthened the internal predictor finalization again with CA bond-window repair, best-model heavy intrachain polishing, and global closest-pair interchain separation.
- Regenerated all 14 current raw/backend artifacts under the recursive lane, then targeted-regenerated `H2312`, `H1346`, and `H1347` after accuracy-readiness proxy feedback.
- Rebuilt raw gate, TS gate, import, validation, scorecard, submission gate, and accuracy-readiness artifacts; current recursive evidence reports `14/14` raw pass, `14/14` TS converted, `14/14 submission_go`, and `14/14 accuracy_readiness pass`.
- Rebuilt the interactive molecular viewer and static render packets: viewer reports `14/14` ready, `0` CA continuity gaps, and `0` CA close-contact markers, reducing the previous viewer marker count from `2265` to `0`.
- Rebuilt `runs/casp17_structure_render_contact_sheet_current.png` and `runs/casp17_molecular_viewer_smoke_current.png`; browser smoke confirmed nonblank WebGL rendering with `99,730` thresholded nonwhite pixels and `71,513` colorful pixels at `1365x900`.
- Verified focused predictor/viewer/render tests: `9 passed in 10.28s`.
- Verified full CASP17 targeted unit suite: `81 passed in 31.11s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T00:11:48+09:00

- Added `tools/build_casp17_competitive_readiness_packet.py` and unit coverage to separate local CASP submission floor from competitive/win-tier readiness.
- Generated `runs/casp17_competitive_readiness_packet_current.*`; current result is `submission_readiness_status=pass`, `competitive_readiness_status=blocked`, `win_tier_readiness_status=blocked`, with seven explicit gaps: top-5 model depth, SCORE, QSCORE, monomer native benchmark, complex native benchmark, all-atom/sidechain quality, and confidence/model selection.
- Upgraded `tools/build_casp17_structure_render_packet.py` to emit high-resolution two-view `*_structure_publication.png` panels with chain-colored and confidence-colored projections, then rebuilt `14/14` render artifacts and the contact sheet.
- Upgraded `tools/build_casp17_molecular_viewer_packet.py` with labels and dark-view controls, then regenerated the embedded local viewer packet.
- Browser smoke of the regenerated viewer remained nonblank: `101,947` thresholded nonwhite pixels and `64,285` colorful pixels at `1365x900`.
- Verified focused competitive/viewer/render tests: `3 passed in 0.90s`.
- Verified full CASP17 targeted unit suite: `82 passed in 32.60s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T00:22:10+09:00

- Extended `tools/run_casp17_internal_physics_baseline_predictor.py` with optional ranked raw model emission, preserving the existing single-model raw output by default.
- Added `tools/build_casp17_ranked_model_depth_packet.py` and unit coverage to convert internal ranked raw candidates into MODEL-indexed TS candidate files.
- Generated T1331 top-5 ranked artifacts on the GPU under `runs/casp17_prediction_jobs_top5_current/T1331` and `runs/casp17_predictions_top5_current/T1331`; all five TS candidates have MODEL indices 1 through 5.
- Rebuilt `runs/casp17_ranked_model_depth_packet_current.*`; current ranked depth is `pass` for T1331 only, so `runs/casp17_competitive_readiness_packet_current.*` now reports top-5 ranked model depth as `partial` with `ranked-depth pass=1/14`.
- Validated T1331 top-5 models 1 through 5 through format, geometry, and confidence checks: `pass/pass/pass` for all five candidates.
- Patched the TS validator with an explicit `--allow-ranked-model-index` mode so standalone ranked MODEL 2-5 candidate artifacts can be checked without weakening the primary submission gate's MODEL 1 requirement.
- Verified focused ranked-depth/predictor/competitive/format tests: `13 passed in 12.48s`.
- Verified full CASP17 targeted unit suite: `85 passed in 34.51s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T00:28:32+09:00

- Strengthened `tools/build_casp17_ranked_model_depth_packet.py` so every ranked candidate is validated through TS format, geometry, and confidence gates inside the packet itself.
- Regenerated `runs/casp17_ranked_model_depth_packet_current.*` for T1331; it now reports `candidate_gate_pass_count=5/5` in addition to `converted_count=5/5`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; top-5 ranked depth remains `partial` because coverage is `1/14`, but the T1331 candidate gate evidence is now explicit as `candidate gates=5/5`.
- Verified focused ranked-depth/competitive/format tests: `5 passed in 0.45s`.
- Verified full CASP17 targeted unit suite: `85 passed in 34.97s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T00:34:04+09:00

- Added `tools/run_casp17_ranked_model_depth_batch.py` and unit coverage to run ranked top-5 generation across target lists, then rebuild the ranked-depth packet with candidate gates.
- Ran the real GPU batch for `T1331,T2313,H2321`: T1331 was skipped as existing, T2313 and H2321 completed, and no target failed.
- Regenerated `runs/casp17_ranked_model_depth_batch_current.*` and `runs/casp17_ranked_model_depth_packet_current.*`; current top-5 evidence is `3/14` targets and `15/15` candidate format/geometry/confidence gates pass.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; top-5 ranked model depth remains `partial`, now with `ranked-depth pass=3/14` and `candidate gates=15/15`.
- Verified focused ranked-depth batch/packet/competitive/format tests: `6 passed in 3.11s`.
- Verified full CASP17 targeted unit suite: `86 passed in 37.94s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T00:55:28+09:00

- Completed the 14-target internal ranked top-5 depth run: `runs/casp17_ranked_model_depth_packet_current.*` now reports `ranked_depth_status=pass`, `14/14` targets, and `70/70` candidate format/geometry/confidence gates.
- Fixed ranked-depth builder behavior so a failed candidate gate no longer blocks conversion of later ranked candidates, and strengthened predictor ranked selection with final CA geometry/compactness/PDB-coordinate quality scoring.
- Added `tools/add_casp17_internal_score_records.py` and unit coverage to create a scored-copy TS lane with conservative internal SCORE/QSCORE records without mutating the original recursive TS predictions.
- Generated `runs/casp17_predictions_scored_current/*TS.pdb`; SCORE exists on `14/14` TS files and QSCORE exists on `11/11` multichain TS files, with an explicit uncalibrated-confidence claim boundary.
- Ran scored-copy import, validation, scorecard, and submission gate packets; scored-copy TS files pass `14/14` format, geometry, confidence, scorecard, and internal submission gate.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` against the scored-copy prediction dir; submission floor, top-5 depth, SCORE coverage, and QSCORE coverage pass, while win-tier readiness remains blocked by four accuracy-quality gaps.
- Verified focused ranked-depth/SCORE/competitive/predictor/format tests: `17 passed in 15.07s`.
- Verified full CASP17 targeted unit suite: `89 passed in 37.48s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:03:32+09:00

- Upgraded `tools/build_casp17_structure_render_packet.py` with a static studio render output: `*_structure_studio.png` uses a dark molecular-view background, depth-sorted shaded tube projection, CA sphere highlights, and confidence legend.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, and `runs/casp17_structure_render_contact_sheet_current.png` from `runs/casp17_predictions_scored_current`.
- Current render packet reports `14/14` rendered targets and `14/14` studio PNG paths.
- Visual inspection of `runs/casp17_structure_renders_current/H1335_structure_studio.png` confirmed a nonblank, higher-contrast molecular-style render.
- Pixel smoke for `runs/casp17_structure_render_contact_sheet_current.png`: nonflat `1680x1320`, `2,046,767` dark pixels and `139,927` colorful pixels.
- Verified focused render/viewer/competitive tests: `3 passed in 1.20s`.
- Verified full CASP17 targeted unit suite: `89 passed in 36.84s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:17:31+09:00

- Added `tools/build_casp17_sidechain_scaffold_packet.py` and unit coverage to create residue-specific heavy-atom scaffold TS copies from the scored internal CA/backbone lane without claiming native-calibrated all-atom refinement.
- Generated `runs/casp17_predictions_sidechain_scaffold_current/*TS.pdb` and `runs/casp17_sidechain_scaffold_packet_current.*`; current scaffold status is `pass`, with `14/14` scaffold pass, `14/14` downstream validation pass, min heavy-atom completion `0.931672`, mean completion `0.95585`, `93,894` emitted heavy atoms, and `4,543` severe sidechain atoms pruned before validation.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*` and `runs/casp17_molecular_viewer_current.html` from `runs/casp17_predictions_sidechain_scaffold_current`, so the interactive viewer now opens the sidechain-rich local TS copies while still redacting embedded `AUTHOR` records.
- Updated `tools/build_casp17_competitive_readiness_packet.py` so sidechain scaffold evidence advances `all_atom_and_sidechain_quality` to `partial` while keeping `competitive_readiness_status=blocked` and `win_tier_readiness_status=blocked`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; submission floor, top-5 depth, SCORE, and QSCORE coverage remain `pass`, all-atom/sidechain quality is `partial`, and remaining competitive gaps stay at `4`.
- Verified py_compile for the sidechain scaffold and competitive readiness tools.
- Verified focused sidechain scaffold / competitive readiness / viewer tests: `4 passed in 0.41s`.
- Verified full CASP17 targeted unit suite: `91 passed in 37.52s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:29:46+09:00

- Upgraded the sidechain scaffold builder with local frame-rotamer candidate selection: each residue sidechain is sampled across six internal frame rotations and selected by a spatial-grid clash/core-orientation score.
- Aborted an initial naive full-target scaffold run after it showed O(N^2) behavior on large targets, then replaced the scoring loop with a `1.7 A` spatial grid so only nearby placed atoms and CA points are compared.
- Regenerated `runs/casp17_sidechain_scaffold_packet_current.*`; current scaffold status remains `pass`, with `14/14` scaffold pass, `14/14` downstream validation pass, min heavy-atom completion improved to `0.991277`, mean completion `0.997778`, emitted heavy atoms `98,188`, severe sidechain prune count reduced to `249`, and local frame-rotamer selections `11,761/70,566`.
- Updated generated TS `REMARK CASP17 SIDECHAIN_SCAFFOLD` text to state the local frame-rotamer selection claim boundary explicitly.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*` from `runs/casp17_predictions_sidechain_scaffold_current`; viewer readiness remains `14/14`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; all-atom/sidechain quality remains `partial` with local frame-rotamer evidence, and competitive/win-tier readiness remains fail-closed as `blocked`.
- Verified py_compile for the sidechain scaffold and competitive readiness tools.
- Verified focused sidechain scaffold / competitive readiness / viewer tests: `4 passed in 0.42s`.
- Verified full CASP17 targeted unit suite: `91 passed in 37.17s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:37:02+09:00

- Added `tools/build_casp17_all_atom_quality_packet.py` and unit coverage for internal MolProbity-style steric/completion QC over the sidechain-scaffold TS files.
- The QC packet checks heavy-atom completion, severe inter-residue clashes, and a soft close-contact clashscore proxy while keeping the claim boundary explicit: not official MolProbity, not energy-minimized all-atom refinement, and not native accuracy evidence.
- Generated `runs/casp17_all_atom_quality_packet_current.*` from `runs/casp17_predictions_sidechain_scaffold_current`; current result is `14/14` pass, min heavy-atom completion `0.991277`, mean completion `0.997778`, max soft clashscore `40.226` per 1000 atoms, mean soft clashscore `13.885`, total soft close contacts `1,502`, and total severe inter-residue clashes `0`.
- Updated `tools/build_casp17_competitive_readiness_packet.py` so the all-atom/sidechain row includes all-atom QC coverage, max soft clashscore, and severe clash evidence while remaining `partial` rather than claiming win-tier readiness.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; submission floor remains `pass`, all-atom/sidechain quality remains `partial` with stronger QC evidence, and competitive/win-tier readiness remains fail-closed as `blocked`.
- Verified py_compile for the all-atom quality and competitive readiness tools.
- Verified focused all-atom quality / sidechain scaffold / competitive readiness / viewer tests: `5 passed in 0.53s`.
- Verified full CASP17 targeted unit suite: `92 passed in 37.29s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:43:12+09:00

- Upgraded `tools/build_casp17_structure_render_packet.py` so dark studio renders include a sampled non-CA atomic overlay when the input PDB has sidechain scaffold atoms.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, and `runs/casp17_structure_render_contact_sheet_current.png` from `runs/casp17_predictions_sidechain_scaffold_current`.
- Current render packet reports `14/14` rendered targets from sidechain-scaffold TS files, atom counts ranging from `2,340` to `14,368`, and `98,188` total rendered atoms across the current target set.
- Pixel smoke for `runs/casp17_structure_render_contact_sheet_current.png`: nonflat `1680x1320`, `2,055,275` dark pixels and `135,679` colorful pixels.
- Pixel smoke for `runs/casp17_structure_renders_current/T1331_structure_studio.png`: nonflat `2200x1400`, `2,849,837` dark pixels and `209,477` colorful pixels.
- Verified py_compile for the structure render packet.
- Verified focused render / all-atom quality / sidechain scaffold / competitive readiness / viewer tests: `6 passed in 1.47s`.
- Verified full CASP17 targeted unit suite: `92 passed in 37.41s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T01:58:01+09:00

- Added `tools/build_casp17_sidechain_repack_packet.py` and unit coverage for local internal sidechain repack/polish over the sidechain-scaffold TS files.
- The repack lane samples local sidechain rotations, radial scales, and small polish shifts, then accepts coordinate updates only when the target does not regress soft close contacts or introduce severe clashes.
- An initial real run reduced total soft close contacts from `1,502` to `388` but introduced severe clashes on `10` targets, so the tool was strengthened with a fail-closed not-worse guard that reverts unsafe targets to scaffold coordinates.
- Regenerated `runs/casp17_sidechain_repack_packet_current.*`; current status is `14/14` pass, with `4` targets accepting coordinate updates, `10` guard reverts, `10,840` retained coordinate updates, and total soft close contacts reduced from `1,502` to `1,343`.
- Regenerated `runs/casp17_all_atom_quality_packet_current.*` from `runs/casp17_predictions_sidechain_repacked_current`; all-atom QC remains `14/14` pass, mean soft clashscore improved to `11.966`, and severe inter-residue clashes remain `0`.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*` and `runs/casp17_structure_render_packet_current.*` from `runs/casp17_predictions_sidechain_repacked_current`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; all-atom/sidechain quality remains `partial` with scaffold, repack, and all-atom QC evidence, and competitive/win-tier readiness remains fail-closed as `blocked`.
- Pixel smoke for `runs/casp17_structure_render_contact_sheet_current.png`: nonflat `1680x1320`, `2,055,276` dark pixels and `135,649` colorful pixels.
- Pixel smoke for `runs/casp17_structure_renders_current/H1347_structure_studio.png`: nonflat `2200x1400`, `2,791,821` dark pixels and `254,810` colorful pixels.
- Verified py_compile for the sidechain repack and competitive readiness tools.
- Verified focused sidechain repack / render / all-atom quality / competitive readiness / viewer tests: `6 passed in 1.50s`.
- Verified full CASP17 targeted unit suite: `93 passed in 37.37s`.
- No local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:11:14+09:00

- Added `tools/build_casp17_historical_benchmark_packet.py` and unit coverage for local no-leak historical native benchmark proxy scoring.
- The benchmark packet accepts a manifest of local historical prediction/native PDB pairs, checks leakage clearance, aligns matched CA atoms, and reports RMSD, TM-score proxy, GDT_TS/GDT_HA proxy, CA-lDDT proxy, and complex interface-contact F1 proxy.
- Generated `runs/casp17_historical_benchmark_packet_current.*`; current result is fail-closed `blocked` because `runs/casp17_historical_benchmark_manifest_current.csv` is missing, with `benchmark_count=0`, `blocked_count=1`, and `manifest_blockers=manifest_missing`.
- Updated `tools/build_casp17_competitive_readiness_packet.py` so monomer and complex win-tier rows consume the historical benchmark packet, while SCORE/QSCORE rows now accurately distinguish record presence from native calibration.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; submission floor remains `pass`, top-5 depth and SCORE/QSCORE record coverage remain `pass`, historical benchmark evidence is linked, and competitive/win-tier readiness remains `blocked` by four accuracy-quality gaps.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the benchmark harness, blocked manifest status, commands, and latest verification evidence.
- Verified py_compile for the historical benchmark and competitive readiness tools.
- Verified focused historical benchmark / competitive readiness tests: `5 passed in 0.46s`.
- Verified focused competitive readiness regression after SCORE/QSCORE wording cleanup: `3 passed in 0.20s`.
- Verified full CASP17 targeted unit suite: `96 passed in 37.81s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:20:11+09:00

- Extended `tools/build_casp17_structure_render_packet.py` with optional PyMOL headless ray-render support while preserving the existing trace, publication, and studio render outputs.
- The PyMOL layer writes per-target PML scripts plus `*_structure_pymol.png` cartoon/stick/sphere ray-traced images from the same sidechain-repacked internal predicted TS coordinates; this is visualization only, not predictor input or accuracy evidence.
- Added unit coverage with a fake PyMOL executable so the optional render integration is tested without requiring PyMOL in every test environment.
- Verified real local PyMOL smoke for T1331, then regenerated the full current render packet from `runs/casp17_predictions_sidechain_repacked_current`.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, and `runs/casp17_structure_render_contact_sheet_current.png`; current render packet reports `14/14` rendered targets, PyMOL rendered `14/14`, blocked `0`, skipped `0`.
- PyMOL/contact-sheet pixel smoke: contact sheet `1680x1320`, dark `2,046,548`, colorful `184,706`; `H1347_structure_pymol.png` `1600x1060`, dark `1,548,301`, colorful `153,370`; `T1331_structure_pymol.png` `1600x1060`, dark `1,582,368`, colorful `122,460`.
- Updated CASP17 participation docs and harness state with the PyMOL render command, artifacts, smoke evidence, and visualization-only claim boundary.
- Verified py_compile for the structure render packet.
- Verified focused structure render tests: `2 passed in 1.78s`.
- Verified full CASP17 targeted unit suite: `97 passed in 38.79s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:26:22+09:00

- Added `tools/build_casp17_historical_benchmark_manifest_scaffold.py` and unit coverage to turn the win-tier benchmark manifest gap into a local scaffold/checklist.
- The scaffold reads an existing manifest when present, otherwise scans `runs/casp17_historical_benchmark_predictions_current` and `runs/casp17_historical_benchmark_natives_current`; if no local files exist it emits fail-closed required monomer/complex placeholder rows.
- Generated `runs/casp17_historical_benchmark_manifest_scaffold_current.*`; current scaffold status is `blocked`, source mode `placeholder_required_inputs`, candidate rows `2`, ready `0`, blocked `2`.
- Regenerated `runs/casp17_historical_benchmark_packet_current.*`; current benchmark packet remains fail-closed `blocked` because `runs/casp17_historical_benchmark_manifest_current.csv` is still missing.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*`; submission floor remains `pass`, while competitive/win-tier readiness remains `blocked` by four accuracy-quality gaps.
- Updated CASP17 participation docs and harness state with the manifest scaffold command, artifact evidence, and next input requirements.
- Verified py_compile for the manifest scaffold tool.
- Verified focused historical benchmark manifest scaffold tests: `3 passed in 0.20s`.
- Verified focused historical benchmark manifest scaffold / benchmark / competitive readiness tests: `8 passed in 0.63s`.
- Verified full CASP17 targeted unit suite: `100 passed in 39.04s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:32:22+09:00

- Added `tools/build_casp17_historical_benchmark_manifest_promotion.py` and unit coverage to promote only ready no-leak historical scaffold rows into a scoring-manifest candidate.
- The promotion gate rejects placeholder rows, missing files, uncleared leakage rows, invalid scopes, and target IDs that are currently open CASP17 targets in `runs/casp17_target_watchlist_current.json`.
- Generated `runs/casp17_historical_benchmark_manifest_promotion_current.*`; current promotion status is `blocked`, source rows `2`, promoted `0`, blocked `2`, monomer/complex promoted `0/0`.
- Generated `runs/casp17_historical_benchmark_manifest_ready_current.csv`; it is header-only because no historical benchmark row is ready to promote.
- Regenerated `runs/casp17_historical_benchmark_packet_current.*` and `runs/casp17_competitive_readiness_packet_current.*`; submission floor remains `pass`, while historical benchmark and competitive/win-tier readiness remain fail-closed `blocked`.
- Updated CASP17 participation docs and harness state with the promotion command, current artifact evidence, and the rule not to overwrite the active scoring manifest until promotion is ready.
- Verified py_compile for the manifest promotion tool.
- Verified focused historical benchmark manifest promotion tests: `3 passed in 0.21s`.
- Verified focused historical benchmark manifest promotion / scaffold / benchmark / competitive readiness tests: `11 passed in 0.81s`.
- Verified full CASP17 targeted unit suite: `103 passed in 38.41s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:41:03+09:00

- Upgraded `tools/build_casp17_sidechain_repack_packet.py` from independent residue scoring to sequential coordinate-aware greedy sidechain scoring, so each residue candidate is scored against previously selected local sidechain coordinates.
- Regenerated `runs/casp17_sidechain_repack_packet_current.*`; current status remains `14/14` pass, soft close contacts improved from `1,502` to `1,098`, guard reverts dropped to `5`, retained coordinate updates increased to `24,732`, and improved residues increased to `5,408`.
- Regenerated `runs/casp17_all_atom_quality_packet_current.*`; all-atom QC remains `14/14` pass, total severe inter-residue clashes remain `0`, total soft close contacts are `1,098`, and mean soft clashscore improved to `8.891`.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*`, `runs/casp17_competitive_readiness_packet_current.*`, and PyMOL-backed `runs/casp17_structure_render_packet_current.*` from the new sidechain-repacked coordinates.
- PyMOL/contact-sheet smoke after repack: contact sheet `1680x1320`, dark `2,046,153`, colorful `185,116`; `H1347_structure_pymol.png` `1600x1060`, dark `1,548,128`, colorful `153,292`; `T1331_structure_pymol.png` `1600x1060`, dark `1,580,899`, colorful `123,960`.
- Competitive readiness remains honest: submission floor `pass`, competitive/win-tier readiness `blocked`, because native-scored no-leak historical benchmark evidence is still missing.
- Verified focused sequential sidechain repack / all-atom quality / render / competitive readiness / viewer tests: `8 passed in 2.30s`.
- Verified full CASP17 targeted unit suite: `103 passed in 38.86s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T02:57:27+09:00

- Extended `tools/build_casp17_structure_render_packet.py` with optional PyMOL QC overlay rendering via `--pymol-qc-render` and `--require-pymol-qc-render`.
- The QC overlay writes per-target `*_structure_qc_pymol.pml` and `*_structure_qc_pymol.png` artifacts, highlighting capped soft close-contact and low-confidence residue hotspots for manual visual triage.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, `runs/casp17_structure_render_contact_sheet_current.png`, and the new `runs/casp17_structure_render_qc_contact_sheet_current.png` from `runs/casp17_predictions_sidechain_repacked_current`.
- Current render summary: `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL QC renders, `0` blocked rows, `504` capped QC hotspot markers total.
- Pixel smoke after QC overlay integration: base contact sheet `1680x1320`, `2,064,093` dark pixels and `152,475` colorful pixels; QC contact sheet `1680x1320`, `2,078,379` dark pixels and `108,334` colorful pixels; `H1347_structure_qc_pymol.png` `1600x1060`, `1,560,202` dark pixels and `116,631` colorful pixels; `T1331_structure_qc_pymol.png` `1600x1060`, `1,581,001` dark pixels and `117,015` colorful pixels.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the PyMOL QC overlay command, artifacts, smoke evidence, and visualization-only claim boundary.
- Verified py_compile for the structure render packet.
- Verified focused structure render tests: `2 passed in 1.86s`.
- Verified full CASP17 targeted unit suite: `103 passed in 38.95s`.
- No external data fetch, local HTTP server, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T03:11:42+09:00

- Added `tools/build_casp17_win_readiness_rubric_packet.py` and unit coverage to make the submission-floor, competitive-floor, review-quality, and win-tier bars explicit in a fail-closed packet.
- The rubric records CASP17 format/source references plus operational win-tier target bands: monomer native-scored high-accuracy benchmarks, complex interface benchmarks, confidence/model-selection calibration, and stronger all-atom steric/sidechain refinement.
- Extended `tools/build_casp17_structure_render_packet.py` with side-by-side `*_structure_review_panel.png` images that place the base PyMOL molecular render beside the QC overlay with marker legend and compact target metrics.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, `runs/casp17_structure_render_contact_sheet_current.png`, `runs/casp17_structure_render_qc_contact_sheet_current.png`, and the new `runs/casp17_structure_render_review_contact_sheet_current.png`.
- Current render summary: `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL QC renders, `14/14` review panels, `0` blocked rows, `504` capped QC hotspot markers total.
- Generated `runs/casp17_win_readiness_rubric_packet_current.*`; current status is submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`, with first gap `all_atom_steric_quality`.
- Pixel smoke after review-panel integration: base contact sheet `1680x1320`, `2,064,092` dark pixels and `152,473` colorful pixels; QC contact sheet `1680x1320`, `2,078,379` dark pixels and `108,338` colorful pixels; review contact sheet `1680x1320`, `2,040,575` dark pixels and `137,270` colorful pixels; `H1347_structure_review_panel.png` `2400x1350`, `2,893,548` dark pixels and `293,897` colorful pixels; `T1331_structure_review_panel.png` `2400x1350`, `2,953,449` dark pixels and `267,155` colorful pixels.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the win-readiness rubric, review-panel command/artifacts, smoke evidence, and visualization-only claim boundary.
- Verified py_compile for the structure render and win-readiness rubric tools.
- Verified focused structure render / win-readiness rubric tests: `4 passed in 2.18s`.
- Verified full CASP17 targeted unit suite: `105 passed in 39.24s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T03:27:00+09:00

- Added `tools/build_casp17_steric_relax_packet.py` and unit coverage for sidechain-only local steric relaxation over generated TS coordinates.
- The relax lane keeps backbone atoms fixed, moves only non-backbone sidechain atoms by bounded steps, and reverts a target if severe clashes or soft close contacts regress.
- Generated `runs/casp17_predictions_steric_relaxed_current/*TS.pdb` and `runs/casp17_steric_relax_packet_current.*`; current status is `14/14` pass, soft close contacts improved from `1,098` to `21`, coordinate updates `1,070`, moved atoms `1,070`, and revert guard `0`.
- Regenerated `runs/casp17_all_atom_quality_packet_current.*` from `runs/casp17_predictions_steric_relaxed_current`; all-atom QC remains `14/14` pass, max soft clashscore improved to `0.557` per 1000 atoms, mean soft clashscore improved to `0.184`, total soft close contacts are `21`, and severe clashes remain `0`.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*` and `runs/casp17_molecular_viewer_current.html` from steric-relaxed predictions.
- Regenerated PyMOL-backed `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, and base/QC/review contact sheets from steric-relaxed predictions.
- Current render summary: `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL QC renders, `14/14` review panels, `0` blocked rows, `504` capped QC hotspot markers total, and soft-contact QC hotspot markers reduced to `38`.
- Pixel smoke after steric relaxation: base contact sheet `1680x1320`, `2,064,069` dark pixels and `152,483` colorful pixels; QC contact sheet `1680x1320`, `2,077,100` dark pixels and `108,685` colorful pixels; review contact sheet `1680x1320`, `2,039,856` dark pixels and `137,400` colorful pixels; `H1347_structure_review_panel.png` `2400x1350`, `2,893,179` dark pixels and `294,023` colorful pixels; `T1331_structure_review_panel.png` `2400x1350`, `2,952,876` dark pixels and `267,589` colorful pixels.
- Updated `tools/build_casp17_competitive_readiness_packet.py` so all-atom/sidechain evidence explicitly includes `runs/casp17_steric_relax_packet_current.*`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked` pending no-leak native benchmarks and native-calibrated model selection.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the steric relax lane, improved all-atom QC metrics, regenerated render artifacts, and claim boundaries.
- Verified py_compile for the steric relax and competitive readiness tools.
- Verified focused steric relax / competitive readiness tests: `4 passed in 0.33s`.
- Verified focused steric relax / competitive readiness / render / win-readiness rubric tests: `8 passed in 2.47s`.
- Verified full CASP17 targeted unit suite: `106 passed in 39.37s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T03:52:30+09:00

- Added `tools/build_casp17_sidechain_completion_repair_packet.py` and unit coverage for local missing-sidechain atom completion using CA-frame templates.
- Added `tools/build_casp17_sidechain_quality_packet.py` and unit coverage for internal sidechain completeness, CB radial, and rotamer-frame proxy QC.
- Regenerated `runs/casp17_sidechain_completion_repair_packet_current.*`; current status is `14/14` pass, inserted sidechain atoms `249`, missing sidechain atoms after repair `0`, and `12` targets are marked `needs_steric_relax` as explicit pre-relax intermediates.
- Regenerated `runs/casp17_steric_relax_packet_current.*`; current status is `14/14` pass, soft close contacts improved from `418` to `30`, coordinate updates `381`, moved atoms `381`, severe clashes after relaxation `0`, and revert guard `0`.
- Regenerated `runs/casp17_all_atom_quality_packet_current.*`; all-atom QC remains `14/14` pass, min heavy-atom completion is `1.0`, max soft clashscore is `0.88` per 1000 atoms, mean soft clashscore is `0.239`, total soft close contacts are `30`, and severe clashes remain `0`.
- Generated `runs/casp17_sidechain_quality_packet_current.*`; sidechain-quality proxy QC is `14/14` pass, min complete sidechain fraction `1.0`, min rotamer proxy pass fraction `1.0`, max CB radial outlier fraction `0.0`, mean rotamer angle deviation `18.162` degrees.
- Updated `tools/build_casp17_competitive_readiness_packet.py` and `tools/build_casp17_win_readiness_rubric_packet.py` so all-atom/sidechain evidence includes the sidechain-quality packet; fixed rubric SCORE/QSCORE row-name compatibility.
- Regenerated PyMOL-backed `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, and base/QC/review contact sheets from the sidechain-completed steric-relaxed predictions.
- Current render summary: `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL QC renders, `14/14` review panels, `0` blocked rows, `98,437` rendered atoms, `504` capped QC hotspot markers total, and `48` soft-contact hotspot markers.
- Pixel smoke after sidechain completion/relax render refresh: base contact sheet `1680x1320`, `2,068,539` dark pixels and `155,106` colorful pixels; QC contact sheet `1680x1320`, `2,061,519` dark pixels and `110,059` colorful pixels; review contact sheet `1680x1320`, `2,023,993` dark pixels and `137,250` colorful pixels.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked` pending no-leak native benchmarks and native-calibrated model selection.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the sidechain completion repair, sidechain-quality QC, refreshed render artifacts, and current claim boundaries.
- Verified py_compile for sidechain completion repair, sidechain quality, competitive readiness, and win-readiness rubric tools.
- Verified focused sidechain completion / sidechain quality / competitive readiness / win-readiness rubric / steric relax tests: `8 passed in 0.74s`.
- Verified full CASP17 targeted unit suite: `108 passed in 39.94s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T04:20:19+09:00

- Added `tools/build_casp17_rotamer_minimization_packet.py` and unit coverage for internal residue-class rotamer-prior steric/polar sidechain minimization.
- The rotamer minimization lane starts from `runs/casp17_predictions_steric_relaxed_current`, moves only sidechain atoms, and keeps a target-level no-regression guard for severe/soft clashes.
- Generated `runs/casp17_predictions_rotamer_minimized_current/*TS.pdb` and `runs/casp17_rotamer_minimization_packet_current.*`; current status is `14/14` pass, minimized residues `11,761`, improved residues `6,158`, coordinate updates `20,991`, soft close contacts `30 -> 30`, mean rotamer-prior deviation `29.858 -> 14.538` degrees, hbond-like contacts `261,663 -> 297,034`, salt-bridge-like contacts `2,214 -> 2,772`, and revert guard `7`.
- Regenerated all-atom and sidechain-quality QC from `runs/casp17_predictions_rotamer_minimized_current`; all-atom QC remains `14/14` pass with min heavy-atom completion `1.0`, max soft clashscore `0.88`, mean soft clashscore `0.239`, total soft close contacts `30`, and severe clashes `0`; sidechain-quality proxy remains `14/14` pass with mean rotamer angle deviation `18.484` degrees.
- Gated the rotamer-minimized TS set through import, validation, scorecard, and submission packets; `runs/casp17_submission_gate_packet_rotamer_minimized_current.json` reports `14/14 submission_go`.
- Regenerated the molecular viewer from rotamer-minimized TS files; `runs/casp17_molecular_viewer_packet_current.json` reports `14/14` ready from `runs/casp17_predictions_rotamer_minimized_current`.
- Regenerated PyMOL-backed render artifacts from rotamer-minimized TS files; current render summary is `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL QC renders, `14/14` review panels, `0` blocked rows, `98,437` rendered atoms, `504` capped QC hotspot markers total, and `48` soft-contact hotspot markers.
- Pixel smoke after rotamer minimization: base contact sheet `1680x1320`, `2,038,043` dark pixels and `189,656` colorful pixels; QC contact sheet `1680x1320`, `2,031,603` dark pixels and `156,747` colorful pixels; review contact sheet `1680x1320`, `1,972,023` dark pixels and `187,333` colorful pixels; `H1347_structure_review_panel.png` `2400x1350`, `2,865,415` dark pixels and `364,948` colorful pixels; `T1331_structure_review_panel.png` `2400x1350`, `2,917,579` dark pixels and `330,137` colorful pixels.
- Updated `tools/build_casp17_competitive_readiness_packet.py` and `tools/build_casp17_win_readiness_rubric_packet.py` so all-atom/sidechain evidence includes rotamer minimization, hbond-like/salt-like proxy contacts, and the no-regression guard.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked` pending no-leak native benchmarks and native-calibrated model selection.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the rotamer-minimized active artifacts, rotamer-minimized submission gate, refreshed render evidence, and claim boundaries.
- Verified py_compile for rotamer minimization, competitive readiness, win-readiness rubric, structure render, and molecular viewer tools.
- Verified focused rotamer minimization / competitive readiness / win-readiness rubric / structure render / molecular viewer tests: `9 passed in 2.58s`.
- Verified full CASP17 targeted unit suite: `109 passed in 39.61s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T04:31:53+09:00

- Strengthened `tools/build_casp17_historical_benchmark_packet.py` so no-leak native benchmark rows are no longer coordinate-only evidence.
- Historical benchmark rows now record prediction/native CA counts, chain counts, matched chain count, coordinate pairing mode, sequence identity match fraction, `sequence_exact_match`, and `chain_exact_match`.
- The scorer now blocks benchmark pass status for prediction/native chain-ID mismatch, monomer scope with multichain structures, complex scope without multichain structures, missing chain/residue key overlap, and residue identity mismatch before TM/GDT/lDDT/interface-contact proxy metrics can count.
- Added unit coverage for sequence mismatch and chain mismatch blocking while keeping the no-leak aligned fixture passing.
- Regenerated `runs/casp17_historical_benchmark_packet_current.*`; it remains fail-closed `blocked` because `runs/casp17_historical_benchmark_manifest_current.csv` is missing, now with sequence-exact rows `0/0` and chain-exact rows `0/0`.
- Regenerated `runs/casp17_historical_benchmark_manifest_scaffold_current.*` and `runs/casp17_historical_benchmark_manifest_promotion_current.*`; scaffold remains `blocked`, promotion remains `blocked`, and the ready manifest remains header-only.
- Updated `tools/build_casp17_competitive_readiness_packet.py` and `tools/build_casp17_win_readiness_rubric_packet.py` so historical benchmark evidence surfaces sequence-exact and chain-exact counts when rows exist.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the historical benchmark exactness gate and current fail-closed artifact status.
- Verified py_compile for historical benchmark, competitive readiness, and win-readiness rubric tools.
- Verified focused historical benchmark exactness / manifest / competitive readiness / win-readiness rubric tests: `15 passed in 1.15s`.
- Verified full CASP17 targeted unit suite: `111 passed in 40.12s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T04:42:03+09:00

- Added `tools/build_casp17_model_selection_calibration_packet.py` and unit coverage to split SCORE/QSCORE record coverage from native-calibrated selected-vs-oracle model selection evidence.
- The new calibration packet reads SCORE/QSCORE coverage, ranked top-5 depth, historical benchmark exactness, and an optional no-leak calibration CSV with selected/best model ranks, native metrics, internal scores, and leakage clearance.
- Generated `runs/casp17_model_selection_calibration_packet_current.*`; current status is fail-closed `blocked`, with SCORE coverage `pass`, QSCORE coverage `pass`, ranked top-5 depth `pass`, historical exactness `blocked`, calibration rows `0/0`, and blocker `calibration_csv_missing`.
- Updated `tools/build_casp17_competitive_readiness_packet.py` and `tools/build_casp17_win_readiness_rubric_packet.py` so confidence/model-selection evidence is driven by the calibration packet rather than treating SCORE/QSCORE record presence as native calibration.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the calibration packet command, calibration CSV contract, current fail-closed artifact status, and claim boundary.
- Verified py_compile for model-selection calibration, competitive readiness, and win-readiness rubric tools.
- Verified focused model-selection calibration / competitive readiness / win-readiness rubric / historical benchmark tests: `12 passed in 0.96s`.
- Verified full CASP17 targeted unit suite: `114 passed in 40.16s`.
- Verified `git diff --check`: clean.
- No CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T04:55:27+09:00

- Added `tools/build_casp17_model_selection_calibration_scaffold.py` and unit coverage to make the selected-vs-oracle calibration gap operational instead of a vague missing CSV.
- The scaffold reads an existing calibration CSV when present, otherwise uses passing no-leak historical benchmark rows when available; with the current empty native benchmark state it emits one required monomer placeholder and one required complex placeholder.
- Generated `runs/casp17_model_selection_calibration_scaffold_current.*`; current status is fail-closed `blocked`, source mode `placeholder_required_inputs`, candidate rows `2`, ready rows `0`, blocked rows `2`, and blocker `existing_calibration_csv_missing`.
- Regenerated `runs/casp17_model_selection_calibration_packet_current.*`; current status remains `blocked`, with SCORE coverage `pass`, QSCORE coverage `pass`, ranked top-5 depth `pass`, historical exactness `blocked`, and calibration rows `0/0`.
- Regenerated `runs/casp17_competitive_readiness_packet_current.*` and `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass`, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the calibration scaffold command, current artifact status, required columns, and claim boundary.
- Verified py_compile for model-selection calibration scaffold, calibration packet, competitive readiness, and win-readiness rubric tools.
- Verified focused model-selection calibration scaffold / calibration packet / competitive readiness / win-readiness rubric / historical benchmark tests: `15 passed in 1.14s`.
- Verified full CASP17 targeted unit suite: `117 passed in 40.11s`.
- Verified `git diff --check`: clean.
- No external data fetch, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T05:17:12+09:00

- Extended `tools/build_casp17_structure_render_packet.py` with optional PyMOL transparent molecular-surface inspection renders via `--pymol-surface-render` and `--require-pymol-surface-render`.
- The surface render writes per-target `*_structure_surface_pymol.pml` and `*_structure_surface_pymol.png` artifacts with a transparent surface plus cartoon/CA context; the review panel now places base, surface, and QC views side by side.
- Updated `tools/build_casp17_win_readiness_rubric_packet.py` so review-quality pass evidence requires base PyMOL, surface PyMOL, QC PyMOL, and review-panel coverage for every current target.
- Regenerated `runs/casp17_structure_render_packet_current.*`, `runs/casp17_structure_render_gallery_current.html`, `runs/casp17_structure_render_contact_sheet_current.png`, `runs/casp17_structure_render_qc_contact_sheet_current.png`, `runs/casp17_structure_render_surface_contact_sheet_current.png`, and `runs/casp17_structure_render_review_contact_sheet_current.png` from `runs/casp17_predictions_rotamer_minimized_current`.
- Current render summary: `14/14` base renders, `14/14` PyMOL renders, `14/14` PyMOL surface renders, `14/14` PyMOL QC renders, `14/14` three-panel review panels, `0` blocked rows, `504` capped QC hotspot markers total, and `48` soft-contact hotspot markers.
- Pixel smoke after surface render integration: base contact sheet `1680x1320`, `2,045,919` dark pixels and `172,652` colorful pixels; QC contact sheet `1680x1320`, `2,055,143` dark pixels and `135,749` colorful pixels; surface contact sheet `1680x1320`, `1,836,855` dark pixels and `351,624` colorful pixels; review contact sheet `1680x1320`, `1,917,648` dark pixels and `254,224` colorful pixels.
- Per-target surface smoke: `H1347_structure_surface_pymol.png` `1200x820`, `732,678` dark pixels and `226,258` colorful pixels; `T1331_structure_surface_pymol.png` `1200x820`, `784,132` dark pixels and `204,009` colorful pixels; `H1347_structure_review_panel.png` `3000x1500`, `3,483,808` dark pixels and `892,441` colorful pixels.
- Regenerated `runs/casp17_win_readiness_rubric_packet_current.*`; submission-level remains `pass`, review-quality remains `pass` with surface render evidence, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the surface render command, artifacts, smoke evidence, and current claim boundary.
- Verified py_compile for structure render and win-readiness rubric tools.
- Verified focused structure render / win-readiness rubric tests: `4 passed in 2.29s`.
- Verified full CASP17 targeted unit suite: `117 passed in 40.36s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T05:26:32+09:00

- Added `tools/build_casp17_win_tier_action_queue_packet.py` and unit coverage to turn the current win-tier rubric into an ordered execution queue.
- Generated `runs/casp17_win_tier_action_queue_packet_current.*`; current status is `blocked`, with `all_atom_quality_upgrade` as the first `ready_internal_development` action and historical benchmark inputs/scoring, model-selection calibration inputs/gate, and final R4 submission confirmation still fail-closed.
- Added `tools/build_casp17_structure_render_review_queue.py` and unit coverage to prioritize visual review by capped soft-contact and low-confidence hotspot counts.
- Generated `runs/casp17_structure_render_review_queue_current.*`, `runs/casp17_structure_render_review_queue_current.html`, and `runs/casp17_structure_render_review_priority_contact_sheet_current.png`.
- Current visual review queue is `ready` for `14/14` rendered targets, with total QC/soft/low-confidence hotspots `504/48/466`; top priority targets are `H1335`, `H2312`, `T1342`, `T2313`, `H1343`, and `H1346`.
- Pixel smoke for `runs/casp17_structure_render_review_priority_contact_sheet_current.png`: nonflat `1440x1242`, `1,438,229` dark pixels and `311,242` colorful pixels.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the action queue, review queue, priority contact sheet, top visual triage targets, and claim boundaries.
- Verified py_compile for win-tier action queue, structure render review queue, structure render, and win-readiness rubric tools.
- Verified focused win-tier action queue / structure render review queue / structure render / win-readiness rubric tests: `6 passed in 2.58s`.
- Verified full CASP17 targeted unit suite: `119 passed in 40.54s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, or push was performed in this step.

## 2026-05-23T05:57:12+09:00

- Added and regenerated the polar-refined selected TS layer via `tools/build_casp17_polar_refinement_packet.py`.
- Current polar refinement status is `14/14` pass: refined residues `11,761`, improved residues `4,435`, coordinate updates `19,061`, soft close contacts `30 -> 29`, hbond-like contacts `297,034 -> 299,059`, salt-bridge-like contacts `2,772 -> 2,933`, total polar contact delta `2,186`, and not-worse guard `1`.
- Regenerated all-atom and sidechain-quality QC from `runs/casp17_predictions_polar_refined_current`; all-atom QC is `14/14` pass with min heavy-atom completion `1.0`, max soft clashscore `0.88`, mean soft clashscore `0.234`, total soft close contacts `29`, and severe clashes `0`; sidechain-quality proxy is `14/14` pass with mean rotamer angle deviation `18.49` degrees.
- Gated the polar-refined TS set through import, validation, scorecard, and submission gate; `runs/casp17_submission_gate_packet_polar_refined_current.json` reports `14/14 submission_go`.
- Regenerated PyMOL-backed render artifacts from `runs/casp17_predictions_polar_refined_current`; render coverage is `14/14` for base/surface/QC/review panels with `0` blocked rows.
- Updated the molecular viewer so local static PyMOL previews are shown when 3Dmol/WebGL is unavailable, and regenerated `runs/casp17_molecular_viewer_current.html` from polar-refined TS files.
- Chrome headless viewer smoke now shows the fallback preview instead of a blank viewer when WebGL fails: `727,836` thresholded nonwhite pixels and `59,478` colorful pixels at `1365x900`.
- Regenerated competitive readiness, win-readiness rubric, and win-tier action queue packets with polar-refinement evidence; submission-level and review-quality remain `pass`, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the polar-refined selected TS set, viewer fallback, refreshed render evidence, and current claim boundaries.
- Verified py_compile for polar refinement, competitive readiness, win-readiness rubric, win-tier action queue, and molecular viewer tools.
- Verified focused polar refinement / competitive readiness / win-readiness rubric / win-tier action queue / molecular viewer tests: `8 passed in 0.70s`.
- Verified full CASP17 targeted unit suite: `120 passed in 41.32s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-23T06:32:45+09:00

- Added `tools/build_casp17_forcefield_minimization_packet.py` and unit coverage for short sidechain-only forcefield-style local minimization over generated CASP17 TS coordinates.
- The new minimizer keeps backbone atoms fixed, moves only sidechain atoms, uses conservative force/anchor steps, and fail-closes with a not-worse guard over severe/soft clashes and internal forcefield energy.
- Regenerated `runs/casp17_predictions_forcefield_minimized_current/*TS.pdb` and `runs/casp17_forcefield_minimization_packet_current.*`; current status is `14/14` pass, sidechain atoms `47,917`, coordinate updates `12,044`, forcefield energy delta `744.884284`, soft close contacts `29 -> 29`, hbond-like contacts `299,059 -> 299,229`, salt-bridge-like contacts `2,933 -> 2,935`, hydrophobic contacts `767,271 -> 768,582`, and not-worse guard `7`.
- Regenerated all-atom and sidechain-quality QC from `runs/casp17_predictions_forcefield_minimized_current`; all-atom QC remains `14/14` pass with severe clashes `0`, total soft close contacts `29`, mean soft clashscore `0.234`, and min heavy-atom completion `1.0`; sidechain-quality proxy remains `14/14` pass with mean rotamer angle deviation `18.48` degrees.
- Gated the forcefield-minimized TS set through import, validation, scorecard, and submission gate; `runs/casp17_submission_gate_packet_forcefield_minimized_current.json` reports `14/14 submission_go`.
- Regenerated `runs/casp17_molecular_viewer_current.html` from forcefield-minimized TS files and refreshed PyMOL base/surface/QC/review renders plus review queue from the same coordinates.
- Pixel smoke after forcefield render refresh: base contact sheet `1680x1320`, `2,037,953` dark pixels and `166,518` colorful pixels; QC contact sheet `1680x1320`, `2,031,533` dark pixels and `130,773` colorful pixels; surface contact sheet `1680x1320`, `1,842,128` dark pixels and `336,653` colorful pixels; review contact sheet `1680x1320`, `1,868,768` dark pixels and `254,287` colorful pixels; priority review sheet `1440x1242`, `1,401,262` dark pixels and `310,648` colorful pixels.
- Chrome headless viewer smoke showed the nonblank fallback molecular preview with `727,998` thresholded nonwhite pixels and `59,885` colorful pixels at `1365x900`.
- Regenerated competitive readiness, win-readiness rubric, and win-tier action queue packets with forcefield-minimization evidence; submission-level and review-quality remain `pass`, competitive floor remains `partial`, and win-tier remains `blocked`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the forcefield-minimized selected TS set, refreshed render evidence, and current claim boundaries.
- Verified py_compile for forcefield minimization, competitive readiness, win-readiness rubric, win-tier action queue, molecular viewer, and structure render tools.
- Verified focused forcefield minimization / competitive readiness / win-readiness rubric / win-tier action queue / molecular viewer / structure render tests: `10 passed in 2.88s`.
- Verified full CASP17 targeted unit suite: `121 passed in 41.32s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-23T07:04:12+09:00

- Added `tools/build_casp17_statistical_rotamer_packet.py` and unit coverage for an internal residue-frequency statistical rotamer packing proxy over the generated CASP17 TS coordinates.
- The new packet keeps backbone atoms fixed, moves only sidechain atoms, uses a repo-local residue-specific frequency-prior table, and fail-closes with a not-worse guard over severe/soft clashes, internal forcefield energy, and mean frequency-prior penalty.
- Regenerated `runs/casp17_predictions_statistical_rotamer_current/*TS.pdb` and `runs/casp17_statistical_rotamer_packet_current.*`; current status is `14/14` pass, evaluated residues `11,761`, packed residues `1,442`, candidates `47,707`, frequency-prior penalty `1.423887 -> 1.40721`, forcefield energy delta `7,628.811384`, soft close contacts `29 -> 29`, hbond-like contacts `299,229 -> 310,302`, salt-bridge-like contacts `2,935 -> 3,177`, hydrophobic contacts `768,582 -> 773,613`, and not-worse guard `6`.
- Regenerated all-atom and sidechain-quality QC from `runs/casp17_predictions_statistical_rotamer_current`; all-atom QC remains `14/14` pass with severe clashes `0`, total soft close contacts `29`, mean soft clashscore `0.234`, max soft clashscore `0.88`, and min heavy-atom completion `1.0`; sidechain-quality proxy remains `14/14` pass with mean rotamer angle deviation `18.542` degrees.
- Gated the statistical-rotamer TS set through import, validation, scorecard, and submission gate; `runs/casp17_submission_gate_packet_statistical_rotamer_current.json` reports `14/14 submission_go`.
- Regenerated `runs/casp17_molecular_viewer_current.html` from statistical-rotamer TS files and refreshed PyMOL base/surface/QC/review renders from the same coordinates.
- Pixel smoke after statistical-rotamer render refresh: base contact sheet `1680x1320`, `2,217,600` thresholded nonwhite pixels and `183,048` colorful pixels; QC contact sheet `1680x1320`, `2,217,600` thresholded nonwhite pixels and `150,043` colorful pixels; surface contact sheet `1680x1320`, `2,217,600` thresholded nonwhite pixels and `351,850` colorful pixels; review contact sheet `1680x1320`, `2,217,600` thresholded nonwhite pixels and `277,583` colorful pixels.
- Chrome headless viewer smoke showed the nonblank fallback molecular preview with `753,006` thresholded nonwhite pixels and `63,083` colorful pixels at `1365x900`.
- Regenerated competitive readiness, win-readiness rubric, and win-tier action queue packets with statistical-rotamer evidence; submission-level and review-quality remain `pass`, competitive floor remains `partial`, and win-tier remains `blocked`. The first remaining quality action is now native-scored sidechain/MolProbity-style benchmark evidence.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the statistical-rotamer selected TS set, refreshed render evidence, submission-gate artifact, and current claim boundaries.
- Verified py_compile for statistical rotamer packing, competitive readiness, win-readiness rubric, and win-tier action queue tools.
- Verified focused statistical rotamer / competitive readiness / win-readiness rubric / win-tier action queue tests: `7 passed in 0.62s`.
- Verified full CASP17 targeted unit suite after statistical-rotamer integration: `122 passed in 41.83s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T13:15:00+09:00

- Refreshed the CASP17 target surface to 16 current open selected protein targets; new targets since the previous 14-target lane are `H1348` and `H1349`.
- Materialized sequences for `16/16` targets and rebuilt the 16-target internal-physics launch packet.
- Added a stronger post-docking interchain CA floor finalizer to `tools/run_casp17_internal_physics_baseline_predictor.py`, including chain-center expansion fallback for large multichain assemblies.
- Added/kept focused predictor coverage requiring multichain no-clash geometry and an interchain CA minimum distance above the proxy floor.
- Regenerated H1348/H1349 recursive raw jobs on the local ROCm GPU after the docking finalizer patch.
- H1348 final recursive assembly metrics: interchain CA clashes `0`, minimum interchain CA distance `3.472 A`, interchain contacts within 12 A `39`, interface plausibility `pass`.
- H1349 final recursive assembly metrics: interchain CA clashes `0`, minimum interchain CA distance `3.292 A`, interchain contacts within 12 A `130`, interface plausibility `pass`.
- Regenerated recursive raw gate and accuracy-readiness packets: both are `16/16 pass`.
- Regenerated recursive TS conversion/import/validation/scorecard/submission gate: `16/16` converted and `16/16 submission_go`.
- Regenerated H1348/H1349 ranked top-5 jobs with the patched finalizer and rebuilt full ranked-depth packet: `16/16 pass`, `80/80` candidate gates.
- Regenerated the final statistical-rotamer selected TS set and full downstream gate: `16/16` import, format, geometry, confidence, scorecard, and submission gate pass.
- Regenerated refinement/QC packets from the final selected TS set: scaffold, repack, completion repair, steric relax, rotamer minimization, polar refinement, forcefield minimization, statistical rotamer, sidechain quality, and all-atom quality all pass `16/16`.
- Final all-atom QC: severe clashes `0`, total soft close contacts `15`, max soft clashscore `0.427` per 1000 atoms.
- Regenerated the molecular viewer packet from final statistical-rotamer TS files: `16/16 ready`, embedded PDB author records redacted.
- Regenerated PyMOL base/QC/surface/review renders from final statistical-rotamer TS files: `16/16` rendered, blocked `0`.
- Pixel-smoked the four final contact sheets; all are nonblank `1680x1320` PNGs with colorful pixel counts at least `2,154,459`.
- Regenerated the visual review queue: `16/16 ready`, total QC/soft/low-confidence hotspots `576/30/555`.
- Regenerated competitive readiness, win-readiness rubric, and win-tier action queue: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`; first remaining gap is no-leak sidechain-native benchmark evidence.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` to 2026-05-24 / 16-target current evidence.
- Verified focused predictor finalizer regression: `9 passed in 10.49s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T13:24:02+09:00

- Redacted registered author-code patterns from Betelgeuze trace history and verified no registered author code remained in `.betelgeuze`, docs, tools, or tests.
- Verified py_compile for the touched CASP17 predictor/readiness tools.
- Verified focused predictor/sidechain-native/competitive/win-readiness/action-queue tests: `18 passed in 11.26s`.
- Verified full CASP17 targeted unit suite: `125 passed in 39.26s`.
- Verified `git diff --check`: clean.
- Current claim boundary is unchanged: 16-target local submission floor is green, while win-tier/native-accuracy readiness remains fail-closed pending no-leak historical/native benchmark and calibration evidence.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T13:29:58+09:00

- Strengthened historical benchmark intake and promotion gates to require explicit no-leak provenance columns, not just `leakage_clearance=no_leak`.
- The strict provenance gate now requires prediction method, prediction creation date, native release date, prediction-before-native-release confirmation, no public/template/native leak, no other-team model, no post-release information, non-current-CASP17 target status, and operator clearance.
- Regenerated historical scaffold, promotion, historical benchmark, sidechain-native benchmark, model-selection calibration scaffold/packet, competitive readiness, win-readiness rubric, and win-tier action queue artifacts.
- Current historical scaffold/promotion remain fail-closed: 0 ready/promoted rows and placeholder rows blocked by missing local files and missing provenance evidence.
- Verified py_compile for strict historical benchmark/readiness tools.
- Verified focused strict historical benchmark provenance/readiness tests: `27 passed in 2.10s`.
- Verified full CASP17 targeted unit suite: `127 passed in 38.72s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T13:34:33+09:00

- Strengthened historical and sidechain-native benchmark scorers to require full prediction/native CA coverage by default.
- Added coverage metrics and blockers: `prediction_ca_coverage`, `native_ca_coverage`, `prediction_ca_coverage_below_threshold`, and `native_ca_coverage_below_threshold`.
- Added unit coverage proving partial residue overlap blocks historical/native and sidechain-native benchmark pass status.
- Regenerated historical benchmark, sidechain-native benchmark, model-selection calibration, competitive readiness, win-readiness rubric, and action queue artifacts.
- Verified py_compile for strict historical benchmark/readiness tools.
- Verified focused strict historical benchmark provenance/coverage/readiness tests: `29 passed in 2.31s`.
- Verified full CASP17 targeted unit suite: `129 passed in 39.49s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T14:00:53+09:00

- Switched active orchestration posture to Hive Mind v12 + Life Science Research routing after the user explicitly requested the plugins and agentic swarm work.
- Spawned two read-only explorer agents: one audited CASP submission-floor vs win-tier evidence gaps, and one audited molecular render improvement options.
- Implemented higher-quality molecular review artifacts in `tools/build_casp17_structure_render_packet.py`:
  - added PyMOL B-factor/pLDDT-style confidence render support with `--pymol-confidence-render` and require gate.
  - added per-target `atlas_panel_png_path` combining studio, confidence, surface, and QC views.
  - added confidence and atlas contact sheets.
- Updated `tools/build_casp17_structure_render_review_queue.py` to require/link atlas panels in the review queue.
- Regenerated 16-target render artifacts from `runs/casp17_predictions_statistical_rotamer_current` with PyMOL base/QC/surface/confidence require gates.
- Current render packet: rendered `16/16`, PyMOL confidence `16/16`, atlas panels `16/16`, blocked `0`.
- Current review queue: `ready`, `16/16`, total QC/soft/low-confidence hotspots `576/30/555`.
- Pixel-smoked base, QC, surface, confidence, review, atlas, and priority contact sheets; all were nonblank and colorful.
- Verified focused render/review queue tests: `3 passed in 4.24s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T14:33:27+09:00

- Continued under the explicitly requested Hive Mind + Life Science Research posture.
- Integrated the render-audit recommendation to split QC hotspot discovery into raw totals and capped rendered markers.
- `tools/build_casp17_structure_render_packet.py` now keeps PyMOL QC marker overlays capped at 36 residues per target while recording uncapped raw QC totals, raw/rendered aliases, truncation flags, confidence cutoffs, closest-contact partner metadata, and top hotspot details.
- `tools/build_casp17_structure_render_review_queue.py` now scores visual triage priority from raw QC totals when present, while still reporting rendered marker counts for image readability.
- Regenerated the 16-target statistical-rotamer render packet with PyMOL base/QC/surface/confidence require gates: all render layers remain `16/16`, blocked `0`.
- Current QC render metadata: raw/rendered QC hotspots `2674/576`, raw/rendered soft hotspots `30/30`, raw/rendered low-confidence hotspots `2653/555`, and marker truncation recorded for `16/16` targets.
- Regenerated the visual review queue: `ready`, `16/16`, top raw-QC priorities now start with `H1335`, `H2312`, `H1343`, `T1342`, `H2338`, `H2339`, `H1349`, and `H1346`.
- Pixel-smoked base, QC, surface, confidence, review, atlas, and priority contact sheets; all were nonblank and colorful. The 1680x1320 sheets had colorful pixels at least `2,212,722`; the priority sheet had `1,783,434` colorful pixels.
- Verified py_compile for the structure render packet and review queue.
- Verified focused render/review queue tests: `4 passed in 5.80s`.
- Verified full CASP17 targeted unit suite: `130 passed in 41.68s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T14:39:50+09:00

- Added `tools/build_casp17_refinement_ablation_packet.py`, a no-leak historical ablation lane for measuring whether internal refinement layers improve native proxy metrics.
- The ablation packet compares recursive/scored/sidechain-scaffold/sidechain-repacked/sidechain-completed/steric-relaxed/rotamer-minimized/polar-refined/forcefield-minimized/statistical-rotamer predictions against cleared historical natives, records per-layer TM/GDT/lDDT/RMSD/interface proxy metrics, and records final-vs-baseline deltas.
- The lane is fail-closed by design: it reads only `runs/casp17_historical_benchmark_manifest_current.csv` or explicit layer-specific local paths and does not fetch or infer current CASP17 target natives.
- Added unit coverage proving a no-leak fixture passes when the final layer improves and proving missing manifest input stays blocked.
- Generated `runs/casp17_refinement_ablation_packet_current.*`; current status is `blocked`, `manifest_blockers=manifest_missing`, `benchmark_count=0`, `layer_count=10`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and `.betelgeuze/state.md` with the new ablation command, layer directory contract, current blocked artifact, and claim boundary.
- Verified py_compile for the refinement ablation packet.
- Verified focused refinement-ablation tests: `2 passed in 0.28s`.
- Verified full CASP17 targeted unit suite: `132 passed in 41.97s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T14:54:04+09:00

- Integrated refinement-ablation evidence into competitive readiness, win-readiness rubric, and win-tier action queue.
- `runs/casp17_competitive_readiness_packet_current.json` now reports `competitive_gap_count=5`, with `refinement_ablation_native_evidence=blocked`.
- `runs/casp17_win_readiness_rubric_packet_current.json` now has 9 requirements and keeps win-tier `blocked` until no-leak refinement-ablation evidence passes.
- `runs/casp17_win_tier_action_queue_packet_current.json` now has 8 actions and includes `refinement_ablation_native_evidence=blocked_input` with `manifest_missing`.
- Updated docs and state to keep submission-floor pass evidence separate from unproven native-accuracy/win-tier claims.
- Verified py_compile for the competitive readiness, win-readiness rubric, and action-queue tools.
- Verified focused competitive/win-readiness/action-queue refinement-ablation wiring tests: `6 passed in 0.51s`.
- Verified full CASP17 targeted unit suite: `132 passed in 41.58s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T15:00:42+09:00

- Strengthened the no-leak historical benchmark manifest lane so refinement-ablation layer prediction paths survive scaffold and promotion.
- `tools/build_casp17_historical_benchmark_manifest_scaffold.py` now preserves non-status extra manifest columns and exposes optional layer path columns from `recursive_prediction_pdb` through `statistical_rotamer_prediction_pdb`.
- `tools/build_casp17_historical_benchmark_manifest_promotion.py` now preserves those layer-specific columns in `runs/casp17_historical_benchmark_manifest_ready_current.csv`, while still only requiring the core historical/provenance columns.
- Regenerated historical scaffold, promotion, refinement-ablation, competitive readiness, win-readiness rubric, and win-tier action-queue artifacts; current no-leak historical input remains fail-closed with 0 ready/promoted rows and `manifest_missing`.
- Verified py_compile for the historical scaffold, promotion, and refinement-ablation tools.
- Verified focused historical manifest/refinement-ablation tests: `10 passed in 0.73s`.
- Verified full CASP17 targeted unit suite: `132 passed in 41.86s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T15:10:09+09:00

- Added `tools/build_casp17_historical_input_preflight_packet.py` to diagnose no-leak historical benchmark and refinement-ablation inputs before scoring.
- The preflight chooses active manifest, ready manifest, scaffold, then scanned local dirs; it reports core prediction/native/provenance readiness separately from 10-layer ablation prediction coverage.
- Added unit coverage for blocked placeholder scaffold rows, ready-manifest rows that are ready to activate with full layer coverage, and active-manifest rows that are historical-ready but ablation-incomplete.
- Regenerated `runs/casp17_historical_input_preflight_packet_current.*`; current status is `blocked`, source mode `scaffold`, candidate/historical-ready/ablation-ready `2/0/0`, missing prediction/native/layer files `2/2/20`.
- Wired the preflight summary into `tools/build_casp17_win_tier_action_queue_packet.py`, so the historical benchmark input action reports `preflight=blocked`, `historical_ready=0`, `ablation_ready=0`, and `missing_layer_files=20`.
- Regenerated the win-tier action queue and updated CASP17 docs/state.
- Verified py_compile for the historical input preflight and action-queue tools.
- Verified focused historical input preflight/action-queue tests: `4 passed in 0.35s`.
- Verified full CASP17 targeted unit suite: `135 passed in 41.33s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T15:26:40+09:00

- Continued under the explicitly requested Hive Mind + Life Science Research posture and used two read-only explorer agents to audit CASP17 viewer smoke coverage and molecular-inspection gaps.
- Hardened `tools/build_casp17_molecular_viewer_packet.py` for the 100% internal lane:
  - removed hosted 3Dmol/Mol* network use from the default generated HTML.
  - added optional local 3Dmol runtime support through `--viewer-js-path`.
  - kept hosted Mol* handoff disabled unless `--enable-external-molstar-link` is explicitly supplied.
  - added residue-class coloring/counts, fixed B-factor confidence bins, per-residue low-confidence lists, chain-pair/interface CA summaries, and internal QC overlay totals from render/review/all-atom/sidechain packets.
- Regenerated `runs/casp17_molecular_viewer_packet_current.*` and `runs/casp17_molecular_viewer_current.html` from the final statistical-rotamer TS set.
- Current molecular viewer packet: `16/16 ready`, external network default `disabled`, WebGL runtime `not_configured_static_preview_fallback`, raw/rendered QC hotspots `2674/576`, raw low-confidence hotspots `2653`, raw soft hotspots `30`, all-atom soft clashes `15`, marker-truncated targets `16/16`.
- Verified the generated HTML has no `https://` matches by default.
- Verified py_compile for the molecular viewer packet.
- Verified focused molecular viewer/render/review queue tests: `5 passed in 5.96s`.
- Verified full CASP17 targeted unit suite: `135 passed in 41.69s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T15:44:40+09:00

- Continued the CASP17 submission-floor / win-tier gap work and pushed the 3D image lane further toward review-grade molecular inspection.
- Upgraded `tools/build_casp17_structure_render_packet.py` with a residue-class molecular map:
  - adds hydrophobic, polar, positive, negative, aromatic, special, and unknown residue-class coloring.
  - writes `*_structure_residue_class.png` for each rendered target.
  - writes `runs/casp17_structure_render_residue_class_contact_sheet_current.png`.
  - expands the atlas panel to include studio, residue-class, confidence, surface, QC, and PyMOL structure views.
- Regenerated render, review queue, and molecular viewer artifacts from `runs/casp17_predictions_statistical_rotamer_current`.
- Current render packet: `16/16` rendered, residue-class panels `16/16`, PyMOL base/QC/surface/confidence `16/16`, review panels `16/16`, atlas panels `16/16`, blocked `0`.
- Current QC evidence remains raw/rendered hotspots `2674/576`, raw soft hotspots `30`, raw low-confidence hotspots `2653`, marker-truncated targets `16/16`.
- Pixel-smoked base, QC, surface, confidence, residue-class, review, atlas, and priority contact sheets; all were nonblank/colorful. The 1680x1320 sheets had colorful pixels at least `2,166,322`; the priority review sheet had `1,751,295`.
- Verified py_compile for the structure render packet.
- Verified focused molecular viewer/render/review queue tests: `5 passed in 7.14s`.
- Verified full CASP17 targeted unit suite: `135 passed in 43.54s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T16:13:26+09:00

- Continued under the explicitly requested Hive Mind + Life Science Research posture and used one read-only agentic sidecar to audit CASP leakage/overclaim risk for predicted-coordinate interface maps.
- Upgraded `tools/build_casp17_structure_render_packet.py` with predicted CA interface contact maps:
  - writes `*_structure_interface_map.png` for each rendered target.
  - writes `runs/casp17_structure_render_interface_contact_sheet_current.png`.
  - records per-target and summary chain-pair counts, predicted CA contacts within 8 A/12 A, minimum interchain CA distance, and JSON interface summaries.
  - keeps HTML/MD/JSON wording bounded to internal predicted coordinates and not official CASP/native interface accuracy evidence.
- Strengthened render tests so the interface fixture has real non-clashing interchain CA contacts, the gallery exposes the claim boundary, and default gallery HTML has no external `http://`/`https://` URLs.
- Regenerated render, review queue, and molecular viewer artifacts from `runs/casp17_predictions_statistical_rotamer_current`.
- Current render packet: `16/16` rendered, residue-class panels `16/16`, predicted CA interface maps `16/16`, PyMOL base/QC/surface/confidence `16/16`, review panels `16/16`, atlas panels `16/16`, blocked `0`.
- Current interface-map summary: chain-pair rows `58`, predicted CA contacts within 12 A `8486`.
- Pixel-smoked base, QC, surface, confidence, residue-class, predicted CA interface-map, review, atlas, and priority contact sheets; all were nonblank/colorful. The 1680x1320 sheets had colorful pixels at least `2,167,656`; the priority review sheet had `1,751,295`.
- Verified py_compile for the structure render packet.
- Verified focused molecular viewer/render/review queue tests: `5 passed in 7.79s`.
- Verified full CASP17 targeted unit suite: `135 passed in 47.18s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T16:20:27+09:00

- Continued the CASP17 review-quality lane without changing selected TS submission files or external state.
- Upgraded `tools/build_casp17_structure_render_review_queue.py` so the review queue is now hotspot- and predicted-interface-prioritized:
  - records separate `qc_review_score`, `interface_review_score`, and combined `review_priority_score`.
  - carries `interface_map_png_path`, predicted CA interface pair count, 8 A/12 A contacts, minimum interchain CA distance, and interface summary JSON into JSON/CSV/MD/HTML rows.
  - links interface maps from the HTML review queue and uses atlas panels for the priority contact sheet when available.
  - keeps the claim boundary explicit: predicted CA interface priority is a triage aid, not official CASP/native interface accuracy or DockQ evidence.
- Regenerated `runs/casp17_structure_render_review_queue_current.*` and `runs/casp17_structure_render_review_priority_contact_sheet_current.png`.
- Current review queue: `16/16 ready`, interface maps `16/16`, interface chain-pair rows `58`, predicted CA contacts within 12 A `8486`, top interface target `H1335`.
- Pixel-smoked the regenerated priority sheet: `1440x1242`, colorful pixels `1,744,263`, no external URLs in the review queue HTML.
- Regenerated the molecular viewer packet after the review queue update.
- Verified py_compile for the review queue tool.
- Verified focused molecular viewer/render/review queue tests: `5 passed in 7.92s`.
- Verified full CASP17 targeted unit suite: `135 passed in 44.57s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, commit, staging, or push was performed in this step.

## 2026-05-24T16:25:48+09:00

- Followed the user's request to gather the current CASP17 data into a `casp17/` folder while preserving the original pipeline paths.
- Added `tools/build_casp17_data_bundle.py`, a local-only CASP17 data mirror/manifest builder:
  - mirrors top-level `runs/casp17*` artifacts into `casp17/runs/`.
  - mirrors CASP17 docs into `casp17/docs/`.
  - writes `casp17/casp17_data_bundle_manifest_current.json`, `.csv`, and `casp17/README.md`.
  - keeps the original `runs/` and `docs/` paths intact so existing CASP17 tools/tests keep working.
- Added `tests/unit/test_build_casp17_data_bundle.py` covering normal mirroring and manifest-only behavior.
- Generated the current data mirror: bundle `ready`, top-level artifacts `432`, mirrored `runs/casp17*` artifacts `431`, mirrored docs `1`, files under mirrored artifacts `3232`, size `310637444` bytes (`du -sh casp17`: `307M`), missing bundled artifacts `0`.
- Verified py_compile for the data bundle tool.
- Verified focused CASP17 data bundle tests: `2 passed in 0.19s`.
- Verified full CASP17 targeted unit suite, including the new bundle tests: `137 passed in 45.18s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T16:35:25+09:00

- Returned to the win-tier blocker after the `casp17/` data mirror and added an operator workorder layer for no-leak historical/native inputs.
- Added `tools/build_casp17_historical_input_workorder_packet.py`:
  - reads `runs/casp17_historical_input_preflight_packet_current.json`.
  - writes `runs/casp17_historical_input_workorder_packet_current.{json,csv,md}`.
  - writes `runs/casp17_historical_benchmark_manifest_operator_template_current.csv`.
  - converts blocked preflight rows into concrete operator actions without clearing provenance, activating manifests, scoring accuracy, fetching native structures, or submitting to CASP.
- Added `tests/unit/test_build_casp17_historical_input_workorder_packet.py` for blocked placeholder rows, ablation-only rows, operator template output, and missing-preflight behavior.
- Wired the workorder summary into `tools/build_casp17_win_tier_action_queue_packet.py`; the historical benchmark input action now reports workorder status, core workorder count, and template CSV path.
- Generated current workorder artifacts: workorder `ready`, rows `2`, core/ablation/complete `2/0/0`, missing core files `4`, missing ablation layer files `20`, operator template `runs/casp17_historical_benchmark_manifest_operator_template_current.csv`.
- Regenerated `runs/casp17_win_tier_action_queue_packet_current.*`; action queue remains `blocked`, but historical benchmark input evidence now includes workorder `ready`, core workorders `2`, and the operator template path.
- Refreshed `casp17/` mirror after adding the new workorder artifacts: bundle `ready`, top-level artifacts `436`, mirrored `runs/casp17*` artifacts `435`, files under mirrored artifacts `3236`, size `310659061` bytes, missing bundled artifacts `0`.
- Verified py_compile for the workorder and action queue tools.
- Verified focused historical input workorder/action queue tests: `3 passed in 0.29s`.
- Verified full CASP17 targeted unit suite: `139 passed in 45.09s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T17:05:56+09:00

- Continued the CASP17 submission-vs-win-tier and molecular visualization improvement loop.
- Upgraded `tools/build_casp17_structure_render_packet.py` with high-resolution molecular inspection plates:
  - writes `*_structure_molecular_plate.png` for each rendered target.
  - writes `runs/casp17_structure_render_molecular_plate_contact_sheet_current.png`.
  - plate combines orthographic chain/confidence/residue-class CA views with model inventory, confidence distribution, residue-class counts, predicted interface contacts, and QC hotspot totals.
  - added `--reuse-existing-pymol-renders` so unchanged PyMOL PNGs can be reused while regenerating local plate/gallery metadata.
- Updated `tools/build_casp17_molecular_viewer_packet.py` so static fallback previews prefer the molecular plate before PyMOL/studio previews.
- Updated `tools/build_casp17_win_readiness_rubric_packet.py` so review-quality pass evidence now requires molecular plates in addition to base PyMOL, surface, QC, and review panels.
- Regenerated render, review queue, molecular viewer, win-readiness rubric, win-tier action queue, and `casp17/` bundle artifacts.
- Current render packet: `16/16` rendered, PyMOL base/QC/surface/confidence `16/16`, residue-class/interface/review/atlas/molecular-plate panels `16/16`, blocked `0`.
- Pixel-smoked the molecular-plate contact sheet and sample T1331/H1335 plates: contact sheet colorful pixels `1,575,226`; sample plates `4,696,527`/`4,893,103`.
- Current win-readiness remains intentionally fail-closed at win tier: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`, first gap `all_atom_steric_quality`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `437`, mirrored `runs/casp17*` artifacts `436`, files under mirrored artifacts `3253`, size `330687840` bytes, missing bundled artifacts `0`.
- Verified py_compile for touched CASP17 render/viewer/readiness/bundle tools.
- Verified focused render/viewer/win-readiness/action-queue/bundle tests: `9 passed in 9.83s`.
- Verified full CASP17 targeted unit suite: `139 passed in 50.80s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T17:19:00+09:00

- Refreshed the requested `casp17/` local data mirror so current CASP17 artifacts are gathered under one folder while preserving the original pipeline paths.
- Regenerated `runs/casp17_structure_image_quality_packet_current.*` before bundling; image-quality smoke is `pass`, with `144/144` images passing, `16/16` targets complete, `16/16` molecular plates passing, and minimum estimated colorful pixels `2149950`.
- Regenerated `runs/casp17_win_readiness_rubric_packet_current.*` and `runs/casp17_win_tier_action_queue_packet_current.*`; submission-level and review-quality remain `pass`, competitive floor remains `partial`, and win-tier remains fail-closed `blocked`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `441`, mirrored `runs/casp17*` artifacts `440`, mirrored docs `1`, files under mirrored artifacts `3257`, size `330816037` bytes (`du -sh casp17`: `326M`), missing bundled artifacts `0`.
- Verified py_compile for the win-readiness and bundle tools.
- Verified focused structure-image/win-readiness/action-queue/data-bundle tests: `7 passed in 0.67s`.
- Verified full CASP17 targeted unit suite: `142 passed in 48.46s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T17:32:48+09:00

- Continued the CASP17 submission-level / win-tier gap work and upgraded the static molecular image lane.
- Added presentation-grade structure plates to `tools/build_casp17_structure_render_packet.py`:
  - writes `*_structure_presentation_plate.png` for every rendered target.
  - writes `runs/casp17_structure_render_presentation_contact_sheet_current.png`.
  - combines primary molecular render, confidence/surface/QC/residue/interface/atlas thumbnails, CASP local-readiness metrics, chemistry counts, and an internal CA geometry secondary-structure proxy strip.
- Updated image-quality smoke to include `presentation_plate_png_path`, and updated the molecular viewer static fallback order to prefer presentation plates before molecular plates/PyMOL/studio previews.
- Regenerated render, review queue, molecular viewer, structure image-quality, win-readiness, and action-queue artifacts from `runs/casp17_predictions_statistical_rotamer_current`.
- Current render packet: `16/16` rendered, presentation plates `16/16`, molecular plates `16/16`, atlas panels `16/16`, blocked `0`.
- Current image-quality packet: `pass`, images `160/160`, targets complete `16/16`, presentation plates `16/16`, molecular plates `16/16`, minimum estimated colorful pixels `2149950`.
- Pixel-smoked the presentation contact sheet and sample T1331/H1335 presentation plates: contact sheet colorful pixels `2,195,325`; sample plates `8,194,350`/`8,189,275`.
- Molecular viewer packet remains `16/16 ready`; first static fallback preview is now `runs/casp17_structure_renders_current/T1331_structure_presentation_plate.png`.
- Win-readiness remains intentionally fail-closed at win tier: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`, first gap `all_atom_steric_quality`.
- Verified py_compile for touched CASP17 render/image-quality/viewer tools.
- Verified focused structure-render/image-quality/molecular-viewer tests: `6 passed in 12.81s`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `442`, mirrored `runs/casp17*` artifacts `441`, mirrored docs `1`, files under mirrored artifacts `3274`, size `354965869` bytes (`du -sh casp17`: `349M`), missing bundled artifacts `0`.
- Verified focused render/image-quality/viewer/win-readiness/data-bundle tests: `10 passed in 13.76s`.
- Verified full CASP17 targeted unit suite: `142 passed in 50.01s`.
- No external predictor, public/template structure lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T17:42:51+09:00

- Added `tools/build_casp17_win_gap_closure_packet.py` and unit coverage to compress the win-readiness rubric plus action queue into the current proven level, next unclosed level, first blocker, and first operator-input action.
- Generated `runs/casp17_win_gap_closure_packet_current.{json,csv,md}` from the current local CASP17 artifacts.
- Current closure packet: closure `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first open dimension `all_atom_steric_quality`, first action `all_atom_quality_upgrade`, first operator-input action `historical_benchmark_inputs`, historical missing core files `4`, historical missing ablation layer files `20`, image-quality `160/160`, presentation plates `16/16`.
- Updated CASP17 docs and harness state to make the closure packet the compact answer to "what level are we at and what closes the next level?"
- Refreshed `casp17/` mirror after adding closure artifacts: bundle `ready`, top-level artifacts `445`, mirrored `runs/casp17*` artifacts `444`, mirrored docs `1`, files under mirrored artifacts `3277`, size `354996789` bytes (`du -sh casp17`: `349M`), missing bundled artifacts `0`.
- Verified py_compile for the closure packet tool.
- Verified focused closure packet test: `1 passed in 0.14s`.
- Verified focused win-gap-closure/data-bundle tests: `3 passed in 0.32s`.
- Verified full CASP17 targeted unit suite: `143 passed in 51.23s`.
- No external predictor, public/template structure lookup, native fetch, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T18:00:00+09:00

- Continued the CASP17 submission-level / win-tier closure loop and upgraded the molecular viewer from static-first fallback to an internal canvas runtime.
- Reconfirmed official CASP17 submission constraints from the Prediction Center: TS atomic-coordinate submissions are one target per file, up to five TS models, model 1 receives primary assessment focus, mandatory TS header fields remain required, B-factor should carry 0-100 pLDDT-style confidence, and H targets require multichain predictions.
- Updated `tools/build_casp17_molecular_viewer_packet.py`:
  - embeds a dependency-free `internalCanvas` molecular runtime in the generated HTML.
  - parses embedded sanitized PDB text in-browser.
  - supports rotate, zoom, spin, center, cartoon/trace/stick/sphere, chain/confidence/residue/spectrum coloring, issue overlays, chain labels, and static preview fallback.
  - keeps external network disabled by default and keeps optional local 3Dmol/WebGL support only when a local bundle is supplied.
- Updated `tests/unit/test_build_casp17_molecular_viewer_packet.py` to assert default `webgl_runtime=internal_canvas_runtime`, canvas parser/rendering symbols, author redaction, no hosted 3Dmol/Mol* URL, and retained static fallback preview.
- Regenerated `runs/casp17_molecular_viewer_packet_current.{json,csv,md}` and `runs/casp17_molecular_viewer_current.html`.
- Current molecular viewer packet: `16/16 ready`, `webgl_runtime=internal_canvas_runtime`, external network `disabled`, internal canvas runtime enabled, static preview fallback enabled, raw/rendered QC hotspots `2674/576`, raw low-confidence hotspots `2653`, all-atom soft clashes `15`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` and mirrored it into `casp17/docs/` via bundle refresh.
- Regenerated `runs/casp17_win_gap_closure_packet_current.*`; closure remains `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first open blocker `sidechain_native_benchmark_missing_or_blocked`, and data bundle artifact count `445`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `445`, mirrored `runs/casp17*` artifacts `444`, mirrored docs `1`, files under mirrored artifacts `3277`, size `355012277` bytes, missing bundled artifacts `0`.
- Verified py_compile for molecular viewer, data bundle, and win-gap closure tools.
- Verified focused molecular-viewer/data-bundle/win-gap tests: `4 passed in 0.43s`.
- Verified full CASP17 targeted unit suite: `143 passed in 50.04s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T18:10:00+09:00

- Continued the CASP17 submission-level / win-tier closure loop by making the "what level must we hit?" target bands machine-readable.
- Added `tools/build_casp17_win_tier_threshold_packet.py`:
  - writes `runs/casp17_win_tier_threshold_packet_current.{json,csv,md}`.
  - encodes 12 operational rows spanning submission gate, top-5 depth, internal canvas visual review, local all-atom QC, sidechain-native lDDT, historical monomer row count/TM target, historical complex row count/interface-F1 target, refinement ablation not-worse rate, and selected-vs-oracle model-selection loss.
  - records competitive/win-tier thresholds while preserving the claim boundary: no current-target native accuracy proof, no native fetch, no external predictor, no CASP submission.
- Added `tests/unit/test_build_casp17_win_tier_threshold_packet.py`.
- Wired the threshold packet into `tools/build_casp17_win_gap_closure_packet.py` and updated `tests/unit/test_build_casp17_win_gap_closure_packet.py`.
- Current threshold packet: `blocked_input`, current proven level `review_quality`, threshold rows pass/partial/blocked `5/1/6`, first threshold gap `sidechain_native_quality/sidechain_native_lddt`, first threshold blocker `sidechain_native_benchmark_missing_or_blocked`.
- Current closure packet now includes threshold status: closure `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first threshold gap `sidechain_native_quality/sidechain_native_lddt`.
- Updated `docs/casp17_participation_gate_2026-05-21.md` with the threshold packet command and current threshold summary.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `448`, mirrored `runs/casp17*` artifacts `447`, mirrored docs `1`, files under mirrored artifacts `3280`, size `355038697` bytes, missing bundled artifacts `0`.
- Verified py_compile for threshold, closure, and win-readiness tools.
- Verified focused threshold/closure/win-readiness tests: `4 passed in 0.43s`.
- Verified full CASP17 targeted unit suite: `144 passed in 51.05s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, CASP portal upload/submission, destructive move/delete, commit, staging, or push was performed in this step.

## 2026-05-24T18:23:56+09:00

- Followed the request to gather current CASP17 data under `casp17/` while preserving original pipeline paths.
- Updated `tools/build_casp17_data_bundle.py` so the local mirror now includes:
  - top-level `runs/casp17*` artifacts under `casp17/runs/`.
  - CASP17 docs under `casp17/docs/`.
  - CASP17 config/template files under `casp17/config/`.
- Refreshed `casp17/README.md`, `casp17/casp17_data_bundle_manifest_current.json`, and `casp17/casp17_data_bundle_manifest_current.csv`.
- Current bundle: `ready`, top-level artifacts `452`, runs artifacts `450`, docs artifacts `1`, config artifacts `1`, files `3284`, bytes `355056475`, missing bundled artifacts `0`.
- Verified `python3 -m py_compile tools/build_casp17_data_bundle.py`.
- Verified `python3 -m pytest tests/unit/test_build_casp17_data_bundle.py -q`: `2 passed`.
- Verified `git diff --check`: clean.
- No destructive move/delete, external data fetch, CASP submission, staging, commit, or push was performed.

## 2026-05-24T18:32:14+09:00

- Continued the CASP17 submission-level / win-tier and 3D molecular-image improvement loop.
- Added `tools/build_casp17_publication_figure_packet.py`:
  - composes one 3840x2160 publication-style molecular figure per target from existing local PyMOL/studio/confidence/surface/QC/residue/interface panels.
  - writes `runs/casp17_publication_figures_current/`, `runs/casp17_publication_figure_contact_sheet_current.png`, and packet JSON/CSV/MD.
  - fail-closes on missing hero images, too few insets, weak dimensions, colorfulness, unique-color count, or luminance range.
- Added `tests/unit/test_build_casp17_publication_figure_packet.py`.
- Wired `runs/casp17_publication_figure_packet_current.json` into `tools/build_casp17_win_tier_threshold_packet.py`, so the visual molecular review threshold now requires internal canvas viewer smoke, rendered image-quality smoke, and 4K publication figures.
- Regenerated publication figures: `16/16 pass`, minimum observed colorful pixels `8236864`, sampled unique colors `559`, luminance range `253.057`.
- Regenerated threshold and closure packets; current proven level remains `review_quality`, next level remains `competitive_floor`, and first threshold gap remains `sidechain_native_quality/sidechain_native_lddt` with blocker `sidechain_native_benchmark_missing_or_blocked`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `457`, mirrored `runs/casp17*` artifacts `455`, docs artifacts `1`, config artifacts `1`, files `3304`, bytes `387247394`, missing bundled artifacts `0`.
- Verified py_compile for publication-figure, threshold, closure, and data-bundle tools.
- Verified focused publication/threshold/closure/data-bundle tests: `6 passed in 1.01s`.
- Verified full CASP17 targeted unit suite: `148 passed in 51.76s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T18:41:31+09:00

- Continued the CASP17 win-tier closure loop by turning the native-evidence blocker into concrete row/file counts.
- Added `tools/build_casp17_win_tier_benchmark_closure_plan.py`:
  - reads the win-tier threshold packet plus historical/sidechain-native/refinement-ablation/model-selection packets.
  - computes competitive required rows `10` monomer + `5` complex and win-tier required rows `25` monomer + `15` complex.
  - writes `runs/casp17_win_tier_benchmark_closure_plan_current.{json,csv,md}`.
  - writes expanded operator template `runs/casp17_win_tier_benchmark_operator_template_current.csv` with 40 placeholder no-leak benchmark rows, ablation-layer PDB columns, and model-selection calibration columns.
- Current benchmark closure plan: planning artifact `ready`, evidence `blocked_input`, current no-leak rows `0/40`, missing win rows `25/15/40`, required prediction/native/ablation/calibration `40/40/400/40`.
- Wired the benchmark closure plan into `tools/build_casp17_win_gap_closure_packet.py`, so the top-level closure packet now reports missing win rows and required prediction/native/ablation/calibration counts.
- Regenerated `runs/casp17_win_gap_closure_packet_current.*`: closure remains `blocked_input`, current proven level `review_quality`, next unclosed `competitive_floor`, benchmark missing win rows `40/40`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `461`, mirrored `runs/casp17*` artifacts `459`, docs artifacts `1`, config artifacts `1`, files `3308`, bytes `387322152`, missing bundled artifacts `0`.
- Verified py_compile for benchmark-closure and win-gap-closure tools.
- Verified focused benchmark-closure/win-gap-closure/data-bundle tests: `5 passed in 0.47s`.
- Verified full CASP17 targeted unit suite: `150 passed in 51.42s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-25T01:35:00+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop by turning the straight-line PNG diagnosis into a reusable gate.
- Added `tools/build_casp17_structure_shape_sanity_packet.py`, a standalone CA-shape sanity packet for generated TS directories. It checks CA continuity, max CA gap, CA span per residue, CA radius of gyration per residue, chain linearity, and aggregate shape penalty before render/submission promotion.
- Wired shape sanity into `tools/build_casp17_readiness_dashboard.py`; a blocked shape-sanity packet now blocks the local submission floor instead of allowing a visually broken but format-valid lane to proceed.
- Generated current shape-guarded shape sanity artifacts:
  - `runs/casp17_structure_shape_sanity_packet_model_selected_shape_guarded_current.*`
  - `runs/casp17_structure_shape_sanity_packet_current.*`
  - result `pass`, `16/16`, blocked `0`, max observed span/Rg/linearity `0.187694/0.074113/0.095013`, max shape penalty `0.0`.
- Generated the legacy normalized model-selected diagnostic artifact `runs/casp17_structure_shape_sanity_packet_model_selected_normalized_legacy_current.*`; it fails as expected with `3/16` pass and `13/16` blocked, documenting the previous straight-line render root cause.
- Refreshed `runs/casp17_readiness_dashboard_current.*`; dashboard remains `ready`, submission floor `pass`, shape sanity `pass 16/16`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, data bundle artifacts `794`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `794`, mirrored `runs/casp17*` artifacts `792`, files `5904`, bytes `1433129089`, missing bundled artifacts `0`.
- Added unit coverage for the new shape-sanity packet and dashboard integration.
- Verified focused shape-sanity/model-selection/readiness/data-bundle tests: `7 passed in 0.61s`.
- Verified py_compile for the touched shape-sanity, model-selection, and readiness dashboard tools.
- Verified `git diff --check`: clean.

## 2026-05-24T22:13:30+09:00

- Promoted stereo-depth renders from ordinary image artifacts into explicit CASP17 review-quality evidence.
- Updated `tools/build_casp17_structure_image_quality_packet.py` so the summary reports `stereo_depth_count` and `stereo_depth_pass_count`.
- Updated `tools/build_casp17_win_tier_threshold_packet.py` so visual molecular review requires stereo-depth coverage for every current target before the `review_quality` threshold can pass.
- Updated `tools/build_casp17_readiness_dashboard.py` so JSON/MD/HTML dashboard evidence surfaces stereo-depth pass/total.
- Regenerated structure image-quality, win-tier threshold, win-gap closure, readiness dashboard, and `casp17/` bundle artifacts.
- Current image-quality smoke: `pass`, images `240/240`, targets complete `16/16`, stereo-depth renders `16/16`, publication/review images `64/64`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Current readiness dashboard: `ready`, proven level `review_quality`, next unclosed `competitive_floor`, stereo-depth renders `16/16`, benchmark rows ready/total `0/40`, missing win-tier evidence `1310/1310`.
- Current `casp17/` mirror: `ready`, top-level artifacts `496`, mirrored `runs/casp17*` artifacts `494`, docs artifacts `1`, config artifacts `1`, files `3566`, bytes `524865724`, missing bundled artifacts `0`.
- Verified final `casp17/` manifest/source parity: source `runs/casp17*` artifacts `494`, bundled `casp17/runs/casp17*` artifacts `494`, missing `0`, extra `0`.
- Verified py_compile for structure-image-quality, readiness-dashboard, and win-tier threshold tools.
- Verified focused stereo-depth image-quality/readiness/threshold/win-gap/data-bundle tests: `7 passed in 0.82s`.
- Verified data-bundle unit tests after the final mirror refresh: `2 passed in 0.18s`.
- Verified full CASP17 targeted unit suite: `160 passed in 59.24s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T22:05:31+09:00

- Continued the CASP17 submission-level/win-tier and molecular-image quality loop.
- Added an orthographic stereo-depth render layer to `tools/build_casp17_structure_render_packet.py`:
  - per-target `*_structure_stereo_depth.png` side-by-side CA projections with a small azimuth offset for local depth inspection.
  - `runs/casp17_structure_render_stereo_depth_contact_sheet_current.png`.
  - render packet summary now reports `stereo_depth_count=16`.
- Wired stereo-depth panels into publication/inspection/review composition and image-quality smoke:
  - `tools/build_casp17_publication_figure_packet.py` now uses stereo-depth panels when available.
  - `tools/build_casp17_structure_image_quality_packet.py` now checks `stereo_depth_png_path` by default.
- Regenerated render, publication-figure, image-quality, review-queue, readiness-dashboard, win-gap, and `casp17/` bundle artifacts.
- Current image-quality smoke: `pass`, `240/240` images, `16/16` stereo-depth renders, `16/16` targets complete, publication/review images `64/64`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Current readiness dashboard: `ready`, proven level `review_quality`, next unclosed `competitive_floor`, image QC `240/240`, benchmark rows ready/total `0/40`, missing win-tier evidence `1310/1310`.
- Current `casp17/` mirror: `ready`, top-level artifacts `496`, mirrored `runs/casp17*` artifacts `494`, docs artifacts `1`, config artifacts `1`, files `3566`, bytes `524865106`, missing bundled artifacts `0` (`du -sh casp17`: `509M`).
- Verified final `casp17/` manifest/source parity: source `runs/casp17*` artifacts `494`, bundled `casp17/runs/casp17*` artifacts `494`, missing `0`, extra `0`.
- Verified focused render/publication/image-quality tests: `7 passed in 14.95s`.
- Verified focused structure-render font regression: `3 passed in 13.06s`.
- Verified focused render/publication/image-quality/readiness/data-bundle tests: `10 passed in 15.09s`.
- Verified full CASP17 targeted unit suite: `160 passed in 54.31s`.
- Verified py_compile for the touched CASP17 render/image-quality/readiness/data-bundle tools.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T18:48:58+09:00

- Continued the CASP17 win-tier closure loop by adding a fail-closed preflight for the expanded 40-row benchmark operator template.
- Added `tools/build_casp17_win_tier_benchmark_operator_preflight.py`:
  - validates placeholder removal, duplicate benchmark/target IDs, current CASP17 target exclusion, local prediction/native PDB files, no-leak provenance fields, all 10 ablation-layer PDB paths, and selected-vs-oracle calibration fields.
  - writes `runs/casp17_win_tier_benchmark_operator_preflight_current.{json,csv,md}`.
- Added `tests/unit/test_build_casp17_win_tier_benchmark_operator_preflight.py`.
- Ran the preflight on `runs/casp17_win_tier_benchmark_operator_template_current.csv`; blocked is expected while placeholders remain:
  - rows ready/blocked `0/40`.
  - missing prediction/native/layer files `40/40/400`.
  - calibration-blocked rows `40`.
  - provenance/core blocked rows `40`.
- Wired operator preflight into `tools/build_casp17_win_gap_closure_packet.py`.
- Regenerated `runs/casp17_win_gap_closure_packet_current.*`; closure remains `blocked_input`, current proven level `review_quality`, benchmark operator preflight ready/blocked `0/40`.
- Verified py_compile for operator-preflight and win-gap-closure tools.
- Verified focused operator-preflight/win-gap-closure/data-bundle tests: `5 passed in 0.45s`.
- Verified full CASP17 targeted unit suite: `152 passed in 54.62s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T19:06:55+09:00

- Continued the CASP17 submission-level / win-tier closure loop after gathering current CASP17 artifacts under `casp17/`.
- Added and exercised `tools/build_casp17_win_tier_benchmark_operator_import_packet.py` as the fail-closed bridge from a preflight-passing 40-row operator template into candidate historical benchmark and model-selection calibration CSV inputs.
- Current operator import packet is intentionally `blocked`: operator preflight status `blocked`, ready/blocked `0/40`, candidate historical/calibration rows `0/0`, blockers `operator_preflight_not_pass,ready_count_below_import_threshold`; candidate CSVs are header-only.
- Updated `tools/build_casp17_win_gap_closure_packet.py` and its test so the top-level closure packet reports operator import status, candidate row counts, candidate CSV paths, and import blockers.
- Regenerated `runs/casp17_win_gap_closure_packet_current.*`; closure remains `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first open blocker `sidechain_native_benchmark_missing_or_blocked`, benchmark missing win rows `40/40`, operator preflight ready/blocked `0/40`, and operator import rows `0/0`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `469`, mirrored `runs/casp17*` artifacts `467`, docs artifacts `1`, config artifacts `1`, files `3316`, bytes `387475858`, missing bundled artifacts `0`.
- Verified py_compile for operator-import, win-gap-closure, and data-bundle tools.
- Verified focused operator-import/win-gap-closure/data-bundle tests: `5 passed in 0.46s`.
- Verified full CASP17 targeted unit suite: `154 passed in 51.49s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T19:11:48+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Upgraded `tools/build_casp17_publication_figure_packet.py` so each target now gets a 3840x2160 molecular inspection poster in addition to the existing publication figure.
- The inspection poster combines local cartoon, confidence, surface, QC, residue-class, interface-map, studio-depth, and atlas panels when available, then applies local contrast/sharpness polish for clearer structural review.
- Added a local no-network molecular inspection gallery, `runs/casp17_molecular_inspection_gallery_current.html`, with target cards linking the high-resolution poster and publication figure for each target.
- Regenerated `runs/casp17_publication_figure_packet_current.*`, `runs/casp17_publication_figures_current/*_molecular_inspection_poster.png`, `runs/casp17_molecular_inspection_poster_contact_sheet_current.png`, and `runs/casp17_molecular_inspection_gallery_current.html`.
- Current publication/inspection packet: `16/16 pass`, inspection posters `16/16`, minimum observed inspection colorful pixels `8124800`, sampled unique colors `1032`, luminance range `255.0`.
- Tightened `tools/build_casp17_win_tier_threshold_packet.py` so the visual molecular review threshold now requires inspection poster coverage equal to the current target count.
- Regenerated `runs/casp17_win_tier_threshold_packet_current.*` and `runs/casp17_win_gap_closure_packet_current.*`; current proven level remains `review_quality`, next unclosed level remains `competitive_floor`, and first threshold gap remains `sidechain_native_quality/sidechain_native_lddt`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `471`, mirrored `runs/casp17*` artifacts `469`, docs artifacts `1`, config artifacts `1`, files `3334`, bytes `429865295`, missing bundled artifacts `0`.
- Verified focused publication-figure/threshold/win-gap/data-bundle tests: `6 passed in 1.31s`.
- Verified full CASP17 targeted unit suite: `154 passed in 52.11s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T19:31:52+09:00

- Continued the CASP17 win-tier closure loop by adding a local operator dashboard for the 40-row no-leak historical benchmark intake.
- Added `tools/build_casp17_win_tier_benchmark_operator_dashboard.py` and unit coverage.
- Generated `runs/casp17_win_tier_benchmark_operator_dashboard_current.{json,csv,md,html}` from the expanded benchmark template, operator preflight, operator import, and win-gap closure packet.
- Current dashboard: `ready` local work surface, rows ready/blocked `0/40`, monomer/complex rows `25/15`, needs target/core/ablation/calibration/provenance `40/40/40/40/40`.
- The dashboard HTML is local-only and no-network: `runs/casp17_win_tier_benchmark_operator_dashboard_current.html`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `475`, mirrored `runs/casp17*` artifacts `473`, docs artifacts `1`, config artifacts `1`, files `3338`, bytes `430112487`, missing bundled artifacts `0`.
- Verified py_compile for the dashboard tool.
- Verified focused benchmark-operator dashboard/preflight/import/win-gap/data-bundle tests: `8 passed in 0.75s`.
- Verified full CASP17 targeted unit suite: `155 passed in 59.62s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T19:47:31+09:00

- Gathered the current CASP17 data artifacts under the existing `casp17/` local mirror while preserving original pipeline paths.
- Generated `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.{json,csv,md,html}` from the 40-row win-tier operator template and dashboard.
- Current evidence fill kit: `ready`, benchmark rows `40`, required evidence items `1160`, filled/missing `0/1160`, missing classes target identity/core/ablation/provenance/calibration `40/80/400/400/240`.
- Refreshed `casp17/README.md`, `casp17/casp17_data_bundle_manifest_current.json`, and `casp17/casp17_data_bundle_manifest_current.csv`.
- Current bundle: `ready`, top-level artifacts `479`, mirrored `runs/casp17*` artifacts `477`, docs artifacts `1`, config artifacts `1`, files `3342`, bytes `431195054`, missing bundled artifacts `0`.
- The mirrored fill-kit files are present under `casp17/runs/`, including `casp17/runs/casp17_win_tier_benchmark_evidence_fill_kit_current.html`.
- Verified py_compile for the data-bundle and evidence fill-kit tools.
- Verified focused data-bundle/evidence fill-kit tests: `3 passed in 0.32s`.
- Verified `git diff --check`: clean.
- No destructive move/delete, external data fetch, current target-native lookup, CASP submission, staging, commit, or push was performed.

## 2026-05-24T19:58:48+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Upgraded `tools/build_casp17_publication_figure_packet.py` with a third high-resolution visual layer: one 3840x2160 molecular scene poster per target, using local studio/PyMOL hero imagery plus confidence/surface/residue/interface detail panels.
- Regenerated `runs/casp17_publication_figure_packet_current.*`, `runs/casp17_publication_figures_current/*_molecular_scene_poster.png`, `runs/casp17_molecular_scene_poster_contact_sheet_current.png`, and the local gallery.
- Current publication/inspection/scene packet: `16/16 pass`, inspection posters `16/16`, scene posters `16/16`, minimum observed scene colorful pixels `8175680`, sampled unique colors `1740`, luminance range `255.0`.
- Tightened `tools/build_casp17_win_tier_threshold_packet.py` so visual molecular review now requires scene poster coverage as well as internal viewer, image-quality smoke, publication figures, and inspection posters.
- Regenerated `runs/casp17_win_tier_threshold_packet_current.*` and `runs/casp17_win_gap_closure_packet_current.*`; current proven level remains `review_quality`, next unclosed level remains `competitive_floor`, and first threshold gap remains `sidechain_native_quality/sidechain_native_lddt`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `480`, mirrored `runs/casp17*` artifacts `478`, docs artifacts `1`, config artifacts `1`, files `3359`, bytes `468536628`, missing bundled artifacts `0`.
- Verified py_compile for publication-figure, threshold, win-gap closure, and data-bundle tools.
- Verified focused publication/threshold/win-gap/data-bundle tests: `6 passed in 1.68s`.
- Verified full CASP17 targeted unit suite: `156 passed in 51.74s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:05:19+09:00

- Continued the CASP17 review-quality / win-tier evidence hardening loop.
- Extended `tools/build_casp17_structure_image_quality_packet.py` so the independent visual smoke packet now reads `runs/casp17_publication_figure_packet_current.json` and gates publication figures, molecular inspection posters, and molecular scene posters alongside the existing render-panel images.
- Regenerated `runs/casp17_structure_image_quality_packet_current.*`; image-quality smoke is `pass`, images `208/208`, targets complete `16/16`, publication/review images `48/48`, molecular plates `16/16`, presentation plates `16/16`, and minimum estimated colorful pixels `2149950`.
- Regenerated `runs/casp17_win_tier_threshold_packet_current.*` and `runs/casp17_win_gap_closure_packet_current.*`; review-quality remains `pass`, current proven level remains `review_quality`, next unclosed level remains `competitive_floor`, and first threshold gap remains `sidechain_native_quality/sidechain_native_lddt`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `480`, mirrored `runs/casp17*` artifacts `478`, docs artifacts `1`, config artifacts `1`, files `3359`, bytes `468579217`, missing bundled artifacts `0`.
- Verified py_compile for structure-image-quality, threshold, win-gap closure, and data-bundle tools.
- Verified focused structure-image-quality/threshold/win-gap/data-bundle tests: `6 passed in 0.64s`.
- Verified full CASP17 targeted unit suite: `156 passed in 51.74s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:12:19+09:00

- Continued the CASP17 submission/review/win-tier status consolidation loop.
- Added `tools/build_casp17_readiness_dashboard.py`, a local no-network dashboard that combines submission floor, review-quality visual QC, competitive-floor threshold gap, win-tier benchmark/evidence gaps, and the external submission boundary into JSON/CSV/MD/HTML.
- Added `tests/unit/test_build_casp17_readiness_dashboard.py`.
- Generated `runs/casp17_readiness_dashboard_current.{json,csv,md,html}`.
- Current readiness dashboard: `ready`, current proven level `review_quality`, next unclosed level `competitive_floor`, levels pass-or-ready/blocked-or-partial `2/3`, image QC `208/208`, publication/review images `48/48`, benchmark rows ready/total `0/40`, missing evidence items `1160/1160`, first not-pass level `competitive_floor`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `484`, mirrored `runs/casp17*` artifacts `482`, docs artifacts `1`, config artifacts `1`, files `3363`, bytes `468597148`, missing bundled artifacts `0`.
- Verified py_compile for readiness-dashboard and data-bundle tools.
- Verified focused readiness-dashboard/data-bundle tests: `3 passed in 0.30s`.
- Verified full CASP17 targeted unit suite: `157 passed in 52.26s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:22:03+09:00

- Gathered the current CASP17 artifacts into the `casp17/` local mirror again after the latest visual-QC hardening, preserving original `runs/`, `docs/`, and `config/` paths.
- Updated the structure image-quality packet and readiness dashboard documentation to include the new edge/sharpness and luminance gates.
- Current image-quality smoke: `pass`, images `208/208`, publication/review images `48/48`, minimum estimated colorful pixels `2149950`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Current readiness dashboard: `ready`, proven level `review_quality`, next unclosed level `competitive_floor`, image QC `208/208`, benchmark rows ready/total `0/40`, missing evidence items `1160/1160`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Refreshed `casp17/README.md`, `casp17/casp17_data_bundle_manifest_current.json`, and `casp17/casp17_data_bundle_manifest_current.csv`.
- Current bundle: `ready`, top-level artifacts `484`, mirrored `runs/casp17*` artifacts `482`, docs artifacts `1`, config artifacts `1`, files `3363`, bytes `468640521`, missing bundled artifacts `0`.
- Verified focused structure-image-quality/readiness-dashboard/win-gap/data-bundle tests: `6 passed in 0.67s`.
- Verified full CASP17 targeted unit suite: `157 passed in 51.81s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:35:32+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Added a fourth high-resolution visual layer to `tools/build_casp17_publication_figure_packet.py`: one 3840x2160 molecular review board per target, combining primary shape, confidence, surface, QC, residue-class, interface-map, and atlas views into a one-page structural inspection image.
- Regenerated `runs/casp17_publication_figure_packet_current.*`, `runs/casp17_publication_figures_current/*_molecular_review_board.png`, `runs/casp17_molecular_review_board_contact_sheet_current.png`, and the local gallery.
- Current publication/inspection/scene/review-board packet: `16/16 pass`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`, minimum observed review-board colorful pixels `8108480`, sampled unique colors `1069`, luminance range `255.0`.
- Tightened visual review gates so `tools/build_casp17_structure_image_quality_packet.py`, `tools/build_casp17_win_tier_threshold_packet.py`, and `tools/build_casp17_readiness_dashboard.py` all include the new review-board artifacts.
- Regenerated `runs/casp17_structure_image_quality_packet_current.*`; image-quality smoke is `pass`, images `224/224`, publication/review images `64/64`, targets complete `16/16`, minimum estimated colorful pixels `2149950`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Regenerated `runs/casp17_win_tier_threshold_packet_current.*`, `runs/casp17_readiness_dashboard_current.*`, and `runs/casp17_win_gap_closure_packet_current.*`; current proven level remains `review_quality`, next unclosed level remains `competitive_floor`, and first threshold gap remains `sidechain_native_quality/sidechain_native_lddt`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `485`, mirrored `runs/casp17*` artifacts `483`, docs artifacts `1`, config artifacts `1`, files `3380`, bytes `513103137`, missing bundled artifacts `0`.
- Verified py_compile for publication-figure, structure-image-quality, threshold, and readiness-dashboard tools.
- Verified focused publication/structure-image-quality/threshold/readiness-dashboard/win-gap/data-bundle tests: `9 passed in 2.35s`.
- Verified full CASP17 targeted unit suite: `157 passed in 51.66s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:47:15+09:00

- Continued the CASP17 competitive/win-tier benchmark closure loop.
- Upgraded `tools/build_casp17_historical_benchmark_packet.py` so complex rows now emit CASP-style interface proxy evidence:
  - native/predicted/shared interface contact counts.
  - interface contact precision/recall/F1 proxy.
  - IPS/Jaccard-style interface patch proxy.
  - QSbest-like contact-overlap proxy.
  - interface iRMSD and DockQ-like proxy.
- Tightened complex win-tier thresholding in `tools/build_casp17_win_tier_threshold_packet.py`: complex interface evidence now has a separate `complex_dockq` row in addition to `complex_interface_f1`.
- Updated `tools/build_casp17_competitive_readiness_packet.py`, `tools/build_casp17_win_readiness_rubric_packet.py`, and `tools/build_casp17_win_tier_action_queue_packet.py` to surface DockQ/QSbest/IPS proxy evidence when no-leak complex benchmark rows are present.
- Corrected the competitive-readiness default prediction directory to the current selected TS set, `runs/casp17_predictions_statistical_rotamer_current`, so SCORE/QSCORE coverage is evaluated on the submission-candidate layer.
- Regenerated historical benchmark, competitive readiness, win readiness, action queue, threshold, win-gap closure, readiness dashboard, and `casp17/` bundle artifacts.
- Current historical benchmark remains fail-closed because `runs/casp17_historical_benchmark_manifest_current.csv` is missing: rows `0`, blockers `manifest_missing`, mean complex DockQ/QSbest proxies `0.0/0.0`.
- Current threshold packet: `blocked_input`, current proven level `review_quality`, pass/partial/blocked `5/1/7`, first threshold gap `sidechain_native_quality/sidechain_native_lddt`.
- Current competitive readiness: `submission_readiness_status=pass`, SCORE records `16/16`, QSCORE records `13/13`, `competitive_gap_count=5`, win-tier remains fail-closed.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `485`, mirrored `runs/casp17*` artifacts `483`, docs artifacts `1`, config artifacts `1`, files `3380`, bytes `513105743`, missing bundled artifacts `0`.
- Verified py_compile for historical benchmark, competitive readiness, win-readiness, action-queue, and threshold tools.
- Verified focused historical benchmark/competitive/win-readiness/action-queue/threshold/win-gap/readiness tests: `15 passed in 1.50s`.
- Verified full CASP17 targeted unit suite: `158 passed in 51.63s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T20:59:26+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Hardened the win-tier benchmark operator dashboard so each row and summary now exposes the required native metric profile: monomer `TM,GDT_TS,CA_lDDT`, complex `TM,interface_F1,DockQ,QSbest,IPS`.
- Hardened the evidence fill kit's native metric gate handling with finite-number checks and regenerated `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.*`.
- Current evidence fill kit: `ready`, benchmark rows `40`, required evidence items `1310`, filled/missing `0/1310`, missing classes target/core/ablation/provenance/calibration/native-metric-gates `40/80/400/400/240/150`.
- Regenerated the operator dashboard, structure image-quality smoke, win-gap closure packet, readiness dashboard, and `casp17/` mirror.
- Current image-quality smoke remains `pass`: `224/224` images, publication/review images `64/64`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- Current readiness dashboard remains `ready`: proven level `review_quality`, next unclosed level `competitive_floor`, benchmark rows ready/total `0/40`, missing win-tier evidence `1310/1310`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `485`, mirrored `runs/casp17*` artifacts `483`, docs artifacts `1`, config artifacts `1`, files `3380`, bytes `513217825`, missing bundled artifacts `0`.
- Verified py_compile for fill-kit, operator-dashboard, win-gap closure, readiness-dashboard, and data-bundle tools.
- Verified focused metric fill-kit/operator-dashboard/win-gap/readiness/data-bundle/image-quality tests: `8 passed in 0.92s`.
- Verified full CASP17 targeted unit suite: `158 passed in 52.01s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T21:11:31+09:00

- Continued the CASP17 competitive-floor/win-tier closure loop by turning the 40-row no-leak benchmark gap into concrete row-level input workspaces.
- Added `tools/build_casp17_win_tier_benchmark_input_scaffold.py` and unit coverage.
- Generated `runs/casp17_win_tier_benchmark_input_scaffold_current.{json,csv,md}` plus `runs/casp17_win_tier_benchmark_input_scaffold_current/`.
- Current input scaffold: `ready`, row folders `40`, row-level README/required-files/provenance/calibration files `160`, monomer/complex rows `25/15`, required prediction/native/ablation file slots `40/40/400`, total required file slots `480`, missing evidence `1310/1310`, native metric gates `150`.
- Generated draft operator CSVs for manual fill-in without promoting them as passed evidence: `runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv` and `runs/casp17_model_selection_calibration_draft_from_operator_current.csv`.
- Updated `tools/build_casp17_readiness_dashboard.py` so the consolidated dashboard now surfaces input-scaffold status, row count, required file slots, and draft CSV paths.
- Regenerated readiness dashboard, win-gap closure, and `casp17/` mirror.
- Current readiness dashboard remains `ready`: proven level `review_quality`, next unclosed level `competitive_floor`, image QC `224/224`, benchmark rows ready/total `0/40`, missing win-tier evidence `1310/1310`, input scaffold `ready` with `480` required file slots.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `491`, mirrored `runs/casp17*` artifacts `489`, docs artifacts `1`, config artifacts `1`, files `3545`, bytes `513714357`, missing bundled artifacts `0`.
- Verified py_compile for input scaffold, readiness dashboard, data bundle, and win-gap closure tools.
- Verified focused input-scaffold/readiness-dashboard/data-bundle/win-gap tests: `5 passed in 0.57s`.
- Verified full CASP17 targeted unit suite: `159 passed in 57.23s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T21:37:19+09:00

- Gathered the current CASP17 data artifacts into the `casp17/` local mirror again, preserving original `runs/`, `docs/`, and `config/` paths.
- Current `casp17/` mirror: `ready`, top-level artifacts `495`, mirrored `runs/casp17*` artifacts `493`, mirrored docs `1`, mirrored config `1`, files under mirrored artifacts `3549`, bytes `513965861`, missing bundled artifacts `0` (`du -sh casp17`: `501M`).
- Confirmed the bundle includes the current input-inventory packet: `blocked`, ready/blocked rows `0/40`, present/missing required files `0/480`, prediction/native/ablation present `0/0/0` of `40/40/400`, provenance/calibration ready rows `0/0`.
- Updated the CASP17 participation doc and harness state to point at the current bundle counts and input-inventory status.
- Verified final `casp17/` manifest/source parity: source `runs/casp17*` artifacts `493`, bundled `casp17/runs/casp17*` artifacts `493`, missing `0`, extra `0`.
- Verified data-bundle unit tests after the final mirror refresh: `2 passed in 0.20s`.
- Verified focused input-inventory/readiness-dashboard/data-bundle/input-scaffold tests: `5 passed in 0.55s`.
- Verified full CASP17 targeted unit suite: `160 passed in 52.37s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T22:52:00+09:00

- Continued the CASP17 internal-only accuracy/readiness loop under the Hive Mind harness.
- Added turntable molecular review strips to the structure render packet and wired them through publication figures, image-quality smoke, win-tier thresholds, readiness dashboard, and the local `casp17/` bundle.
- Regenerated visual artifacts: structure renders `16/16`, turntable strips `16/16`, publication/review figures `16/16`, image-quality smoke `256/256`, readiness dashboard `ready`, current proven level `review_quality`, next unclosed level `competitive_floor`.
- Upgraded `tools/build_casp17_current_target_model_selection_packet.py` with CA-clash/interface proxy scoring and selected-model materialization into `runs/casp17_predictions_model_selected_current`.
- Current top-5 selector: `pass`, candidates `80`, materialized selected TS files `16/16`, non-rank-1 selected candidates `13/16`.
- Verified the model-selected support lane through import, validation, scorecard, and submission gate: `16/16` import, format, geometry, confidence, scorecard, and `submission_go`.
- Added fail-closed active benchmark/calibration activation tooling and generated `runs/casp17_win_tier_benchmark_activation_packet_current.json`; activation remains `blocked`, active files written `false`, candidate historical/calibration rows `0/0`, because operator import and no-leak benchmark rows are not ready.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `521`, mirrored `runs/casp17*` artifacts `519`, docs artifacts `1`, config artifacts `1`, files `3780`, bytes `559255898`, missing bundled artifacts `0`.
- Verified py_compile for the touched CASP17 selection, activation, render, publication, image-quality, threshold, readiness, win-gap, and bundle tools.
- Verified focused selection/activation/render/dashboard/bundle tests: `15 passed in 17.41s`.
- Verified full CASP17 targeted unit suite: `163 passed in 56.69s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-24T23:32:00+09:00

- Continued the CASP17 internal-only accuracy/readiness loop by closing the CA-CB-only gap in the model-selected support lane.
- Ran the top-5-selected structures through the internal heavy-atom backmapping/refinement stack into `runs/casp17_predictions_model_selected_statistical_rotamer_current`.
- Model-selected refined stack status:
  - sidechain scaffold `16/16`, mean heavy-atom completion `0.999427`.
  - sidechain repack `16/16`, soft close contacts `308 -> 253`.
  - completion repair `16/16`, missing sidechain atoms `64 -> 0`, pre-relax rows `5`.
  - steric relax `16/16`, soft close contacts `342 -> 6`.
  - rotamer minimization, polar refinement, forcefield minimization, and statistical-rotamer packing proxy all `16/16`.
  - final all-atom QC `pass`, severe clashes `0`, soft clashes `4`, max soft clashscore per 1000 atoms `0.569`, mean heavy-atom completion `1.0`.
  - final sidechain QC `pass`, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`.
- Verified the full heavy-atom model-selected refined lane through import, validation, scorecard, and submission gate: `16/16` import, format, geometry, confidence, scorecard, and `submission_go`.
- Fixed robust PDB ATOM rewriting for wide-coordinate sidechain updates in rotamer, forcefield, and statistical-rotamer passes so malformed source suffixes cannot corrupt occupancy/B-factor fields.
- Generated model-selected refined 3D visual artifacts:
  - structure render packet `16/16`, turntable `16/16`, stereo-depth `16/16`, presentation plates `16/16`.
  - publication/review figures `16/16`.
  - image-quality smoke `256/256`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `605`, mirrored `runs/casp17*` artifacts `603`, docs artifacts `1`, config artifacts `1`, files `4524`, bytes `767892609`, missing bundled artifacts `0`.
- Verified py_compile for touched CASP17 rotamer/forcefield/statistical-rotamer, model-selection, render, publication, image-quality, and data-bundle tools.
- Verified focused forcefield/model-selection/render/publication/image-quality/bundle tests: `12 passed in 17.75s`.
- Verified full CASP17 targeted unit suite: `164 passed in 63.73s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-25T00:05:00+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Added `tools/build_casp17_pdb_coordinate_frame_packet.py` with unit coverage to catch and repair generated TS PDB coordinate-frame overflow that breaks fixed-width PDB parsing.
- Normalized the model-selected refined heavy-atom lane into `runs/casp17_predictions_model_selected_coordinate_normalized_current`.
- Coordinate-frame normalization result: `pass`, `16/16`, fixed-width parse errors `356 -> 0`, shifted targets `1`; T1342 received a rigid x-shift of `76.487 A`, preserving geometry while making strict PDB coordinate fields parseable.
- Regenerated normalized model-selected QC and gates:
  - all-atom QC `16/16 pass`, heavy-atom completion `1.0`, severe clashes `0`, soft clashes `4`.
  - sidechain QC `16/16 pass`, sidechain completion `1.0`, rotamer proxy pass `1.0`.
  - import, validation, scorecard, and submission gate all `16/16`; normalized model-selected submission gate `submission_go 16/16`.
- Regenerated the normalized model-selected local molecular viewer:
  - `runs/casp17_molecular_viewer_model_selected_normalized_current.html`.
  - viewer smoke `pass`, `16/16`, internal canvas symbols `8/8`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`.
- Extended `tools/build_casp17_readiness_dashboard.py` so readiness now records coordinate-frame status, model-selected comparison/promotion status, and molecular viewer smoke status.
- Current readiness dashboard: `ready`, current proven level `review_quality`, levels pass-or-ready/blocked-or-partial `2/4`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, coordinate frame `pass 16/16`, model comparison `pass`, promotion `blocked_pending_no_leak_historical_calibration`, viewer smoke `pass 16/16`, image QC `256/256`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `649`, mirrored `runs/casp17*` artifacts `647`, files `4672`, bytes `822918831`, missing bundled artifacts `0`.
- Verified py_compile for coordinate-frame, readiness-dashboard, molecular-viewer, viewer-smoke, and data-bundle tools.
- Verified focused coordinate-frame/readiness/viewer/bundle tests: `7 passed in 0.81s`.
- Verified full CASP17 targeted unit suite: `166 passed in 56.79s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-25T00:24:00+09:00

- Continued the CASP17 molecular-image quality loop by aligning static render/review artifacts with the normalized heavy-atom model-selected PDB lane.
- Regenerated normalized model-selected structure renders from `runs/casp17_predictions_model_selected_coordinate_normalized_current` into `runs/casp17_structure_renders_model_selected_normalized_current`.
- Normalized render packet: `runs/casp17_structure_render_packet_model_selected_normalized_current.json`, render coverage `16/16`, PyMOL base/QC/surface/confidence `16/16`, residue-class/interface/stereo-depth/turntable/molecular-plate/presentation-plate `16/16`, blocked `0`, raw/rendered QC hotspots `2654/576`, soft hotspots `4`.
- Regenerated normalized model-selected publication/review figures: `runs/casp17_publication_figure_packet_model_selected_normalized_current.json`, `16/16 pass`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`, min observed colorful pixels `8205952`, min observed unique colors `445`, luminance range `254.422`.
- Regenerated normalized model-selected image-quality smoke: `runs/casp17_structure_image_quality_packet_model_selected_normalized_current.json`, `pass`, images `256/256`, stereo-depth `16/16`, turntable `16/16`, publication/review images `64/64`, minimum estimated edge pixels `2025`, minimum luminance range `29.141`.
- Refreshed readiness dashboard against normalized image artifacts: `ready`, current proven level `review_quality`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, normalized image QC `256/256`, data bundle artifacts `678`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `678`, mirrored `runs/casp17*` artifacts `676`, files `5083`, bytes `961069806`, missing bundled artifacts `0`.
- Verified focused normalized render/publication/image/readiness/bundle tests: `10 passed in 17.81s`.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-25T01:19:11+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop after diagnosing straight-line PNGs.
- Root cause: the old model-selected support lane selected overextended PDB coordinates for some targets; this was not a PNG renderer problem. The native-free selector rewarded consensus/low-clash/interface proxies without a hard global-shape guard.
- Added shape-guard scoring to `tools/build_casp17_current_target_model_selection_packet.py`: CA span per residue, CA radius of gyration per residue, chain linearity, and fail-closed blocking of linear/overextended candidates before recommendation.
- Generated `runs/casp17_current_target_model_selection_shape_guarded_current.*`: selector `pass`, 80 candidates, materialized selected TS files `16/16`, rank-1 recommendations `14/16`, non-rank-1 recommendations `2/16`.
- Shape repair examples:
  - T1342 old normalized model-selected span/Rg/end-to-end `2145.2/614.9/2145.1 A` -> shape-guarded `208.3/47.6/137.1 A`.
  - T1331 old `336.3/93.3/289.1 A` -> shape-guarded `79.3/20.8/42.6 A`.
  - H2312 old `1357.4/349.1/898.9 A` -> shape-guarded `140.6/31.0/79.0 A`.
- Ran the shape-guarded selected structures through the internal heavy-atom stack into `runs/casp17_predictions_model_selected_shape_guarded_statistical_rotamer_current` and normalized them into `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`.
- Shape-guarded refinement stack status: sidechain scaffold `16/16`, completion repair inserted missing sidechain atoms `960 -> 0`, extended steric relax soft contacts `5823 -> 156`, rotamer minimization `16/16`, polar refinement `16/16`, forcefield minimization `16/16`, statistical rotamer `16/16`.
- Shape-guarded QC/gates: all-atom QC `pass 16/16`, severe clashes `0`, soft clashes `154`, heavy-atom completion `1.0`; sidechain QC `pass 16/16`; coordinate frame `pass 16/16`; import/validation/scorecard/submission gate all `16/16`, `submission_go 16/16`.
- Generated shape-guarded molecular render and review artifacts:
  - structure render `16/16`, PyMOL base/QC/surface/confidence each `16/16`, residue-class/interface/stereo-depth/turntable/molecular-plate/presentation-plate each `16/16`, blocked `0`.
  - publication/review figures `pass 16/16`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`.
  - image-quality smoke `pass`, images `256/256`, publication/review images `64/64`, minimum estimated colorful pixels `1012075`, edge pixels `50050`, luminance range `93.823`.
  - internal-canvas molecular viewer smoke `pass 16/16`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`.
- Generated `runs/casp17_model_selected_shape_guarded_refinement_comparison_packet_current.*`: active-vs-shape-guarded comparison `pass`, active/model-selected gates `16/16`, model-selected internal candidates `2/16`, review-both `14/16`, promotion still `blocked_pending_no_leak_historical_calibration`.
- Generated `runs/casp17_win_tier_benchmark_fill_priority_packet_current.*`: fill priority `ready`, row count `40`, competitive-floor batch monomer/complex/total `10/5/15`, win-required rows `40`, missing win evidence `1310`.
- Refreshed readiness dashboard against the shape-guarded lane: `ready`, current proven level `review_quality`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, shape-guarded image QC `256/256`, data bundle artifacts `785`.
- Refreshed `casp17/` mirror: bundle `ready`, top-level artifacts `785`, mirrored `runs/casp17*` artifacts `783`, files `5895`, bytes `1433059908`, missing bundled artifacts `0`.
- Verified py_compile for `tools/build_casp17_current_target_model_selection_packet.py` and `tools/build_casp17_win_tier_benchmark_fill_priority_packet.py`.
- Verified focused shape/fill-priority/dashboard/image/bundle tests: `9 passed in 0.95s`.
- Redacted the registered author-code pattern from `.betelgeuze/trace.jsonl`; remaining author-like strings in tools/tests are dummy `0000-0000-0000` fixtures or vendored UUID/documentation examples.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, destructive move/delete, staging, commit, or push was performed.

## 2026-05-25T06:56:37+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop.
- Integrated the standalone structure shape-sanity gate into orchestration:
  - `tools/run_casp17_target_attempt_gate.py` now runs `scorecard -> shape_sanity -> submission_gate`.
  - `tools/run_casp17_prediction_batch_gate.py` now forwards shape-sanity JSON/CSV/MD paths into each target attempt.
  - `tools/build_casp17_submission_gate_packet.py` consumes `--shape-sanity-json`, so line-like/overextended coordinates can block an otherwise locally formatted row before CASP submission review.
- Regenerated the default `*_current` visual/submission surface from `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`.
- Current visual packets:
  - structure render `16/16`, PyMOL base/QC/surface/confidence `16/16`, review panels `16/16`, molecular plates `16/16`, presentation plates `16/16`, stereo-depth `16/16`, turntable `16/16`.
  - publication figures `16/16`, molecular inspection posters `16/16`, molecular scene posters `16/16`, molecular review boards `16/16`.
  - image-quality smoke `pass`, images `256/256`, publication/review images `64/64`, target completion `16/16`, minimum estimated colorful pixels `968275`, edge pixels `50050`, luminance range `90.525`.
  - internal-canvas molecular viewer smoke `pass`, `16/16`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`.
- Current local submission gate:
  - `runs/casp17_submission_gate_packet_current.json`: shape sanity required/pass, `16/16 submission_go`, no local no-go rows.
- Current readiness:
  - competitive readiness submission floor `pass`, but competitive/win-tier readiness remains `blocked`.
  - win-readiness rubric: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`.
  - readiness dashboard: current proven level `review_quality`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`.
- Verified focused shape-sanity/orchestration/submission tests: `14 passed in 1.12s`.
- Verified existing-structure attach/submission compatibility after the shape-sanity wiring: `13 passed in 1.19s`.
- Verified full CASP17 targeted unit suite: `171 passed in 57.00s`.
- Refreshed readiness dashboard and `casp17/` mirror after the default current visual/submission surface update: bundle `ready`, top-level artifacts `797`, mirrored `runs/casp17*` artifacts `795`, docs artifacts `1`, config artifacts `1`, files `5907`, bytes `1412222432`, missing bundled artifacts `0`; dashboard data bundle artifacts `797`.
- Verified focused data-bundle tests: `2 passed in 0.18s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, staging, commit, or push was performed.

## 2026-05-25T20:36:05+09:00

- Continued the CASP17 submission-level / win-tier and molecular-image quality loop before the requested commit/push.
- Expanded `tools/build_casp17_win_tier_threshold_packet.py` from 13 to 27 operational threshold rows and added a target-level guide for `submission_floor`, `review_quality`, `competitive_floor`, and `win_tier`.
- Current threshold packet: `blocked_input`, current proven level `review_quality`, pass/partial/blocked `7/2/18`, first threshold gap `local_all_atom_qc/max_soft_clashscore_per_1000_atoms`; win-tier still requires no-leak historical/native, ablation, selection, and confidence calibration evidence.
- Added molecular-showcase image composition to `tools/build_casp17_publication_figure_packet.py` and wired showcase images through structure image-quality and readiness dashboard summaries.
- Regenerated current visual/readiness artifacts:
  - publication figures `pass`, `16/16` publication, inspection, scene, review-board, and molecular-showcase images.
  - image-quality smoke `pass`, `272/272`, publication/review/showcase images `80/80`, target completion `16/16`, min edge pixels `50050`, luminance range `93.823`.
  - readiness dashboard `ready`, current proven level `review_quality`, first not-pass `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, molecular showcases `16/16`, data bundle artifacts `798`.
  - `casp17/` mirror bundle `ready`, top-level artifacts `798`, mirrored `runs/casp17*` artifacts `796`, files `5924`, missing bundled artifacts `0`.
- Verified focused molecular-showcase/threshold/readiness image tests: `6 passed in 2.51s`.
- Verified full CASP17 targeted unit suite: `171 passed in 61.03s`.
- Verified `git diff --check`: clean.
- No external predictor, public/template structure lookup, current target-native lookup, native fetch, CASP portal upload/submission, commit, or push had been performed at the time of this log entry.
