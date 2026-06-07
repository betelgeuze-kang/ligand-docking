# CASP17 Internal Physics Participation Gate

Status date: 2026-05-25

## Current Decision

Use CASP17 as an external blind-evaluation opportunity, but keep every submission fail-closed.

- Current active lane: 100% internal `torch`/coarse-grain physics predictor.
- Scope: all current open selected protein targets materialized by the CASP17 watchlist.
- Current target count: 16.
- Newly included since the previous 14-target lane: `H1348` and `H1349`.
- External predictors, public/template structures, API structure services, and other-team models are not part of the active lane.
- CASP author code is runtime-only input. Do not store it in repo docs, state, configs, or generated examples.
- CASP portal upload/submission is R4 external state and requires explicit confirmation before execution.

## Current Evidence

The recursive internal-physics lane submission floor is locally green as of 2026-05-24 14:33 KST. The current selected TS set is the statistical-rotamer internal sidechain-only refinement layer. Win-tier/native-accuracy readiness remains fail-closed:

- `runs/casp17_target_watchlist_current.json`: 16 current open selected protein targets on 2026-05-24.
- `runs/casp17_sequence_packet_current.json`: 16/16 FASTA files materialized.
- `tools/run_casp17_internal_physics_baseline_predictor.py`: post-docking finalizer now enforces an interchain CA floor with chain-center expansion fallback.
- H1348/H1349 regenerated on the local ROCm GPU after the docking finalizer patch:
  - H1348: interchain CA clashes `0`, min interchain CA distance `3.472 A`, predicted CA contacts within 12 A `39`, internal interchain CA-separation/contact sanity `pass`.
  - H1349: interchain CA clashes `0`, min interchain CA distance `3.292 A`, predicted CA contacts within 12 A `130`, internal interchain CA-separation/contact sanity `pass`.
- `runs/casp17_internal_physics_raw_gate_packet_recursive_current.json`: raw gate `pass`, 16/16 contract/geometry/confidence pass with GPU evidence required.
- `runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json`: 16/16 accuracy-readiness proxy pass.
- `runs/casp17_internal_physics_ts_gate_batch_recursive_current.json`: 16/16 TS converted; import, validation, scorecard, and submission gate completed.
- `runs/casp17_submission_gate_packet_recursive_current.json`: 16/16 `submission_go` under the internal fail-closed gate.
- `runs/casp17_ranked_model_depth_packet_current.json`: 16/16 ranked top-5 depth pass, with 80/80 MODEL-indexed TS candidate format/geometry/confidence gates passing.
- `runs/casp17_current_target_model_selection_packet_current.json`: current-target internal top-5 selector is `pass` for 16/16 targets and 80 candidates. It now scores distance-map consensus, confidence, CA continuity, CA clash, and interface-contact proxies, materializes 16/16 selected TS files into `runs/casp17_predictions_model_selected_current`, and recommends non-rank-1 candidates for 13/16 targets. This is current-target internal support only; it is not native-calibrated evidence and does not replace the no-leak historical calibration requirement.
- `runs/casp17_internal_score_record_packet_current.json`: conservative internal SCORE records were added for 16/16 scored-copy TS files, and QSCORE records were added for 13/13 multichain scored-copy TS files.
- `runs/casp17_predictions_statistical_rotamer_current/*TS.pdb`: current selected TS files.
- `runs/casp17_prediction_import_packet_statistical_rotamer_current.json`: 16/16 final selected TS files imported.
- `runs/casp17_prediction_validation_batch_statistical_rotamer_current.json`: 16/16 final selected TS files pass format, geometry, and confidence validation.
- `runs/casp17_internal_scorecard_batch_statistical_rotamer_current.json`: 16/16 final selected TS files pass internal scorecard.
- `runs/casp17_submission_gate_packet_statistical_rotamer_current.json`: 16/16 final selected TS files are `submission_go`.
- `runs/casp17_prediction_import_packet_model_selected_current.json`, `runs/casp17_prediction_validation_batch_model_selected_current.json`, `runs/casp17_internal_scorecard_batch_model_selected_current.json`, and `runs/casp17_submission_gate_packet_model_selected_current.json`: the materialized model-selected top-5 lane also clears import, format, geometry, confidence, scorecard, and submission gate for 16/16 targets. It remains a selection-support lane until no-leak historical calibration decides whether to promote it over the statistical-rotamer selected set.
- `runs/casp17_predictions_model_selected_statistical_rotamer_current/*TS.pdb`: the materialized top-5-selected lane has now been run through the same residue-specific heavy-atom backmapping/refinement stack as the active statistical-rotamer lane: sidechain scaffold, sidechain repack, completion repair, steric relax, rotamer minimization, polar refinement, forcefield-style minimization, and statistical-rotamer packing proxy.
- Model-selected refined support packets are green for 16/16 targets: sidechain scaffold pass with mean heavy-atom completion `0.999427`, sidechain repack soft contacts `308 -> 253`, completion repair missing sidechain atoms `64 -> 0`, steric relax soft contacts `342 -> 6`, rotamer minimization pass, polar refinement soft contacts `6 -> 4`, forcefield minimization pass, and statistical-rotamer pass.
- `runs/casp17_all_atom_quality_packet_model_selected_current.json`: model-selected refined all-atom QC pass for 16/16, severe clashes `0`, total soft close contacts `4`, max soft clashscore `0.569` per 1000 atoms, mean heavy-atom completion `1.0`.
- `runs/casp17_sidechain_quality_packet_model_selected_current.json`: model-selected refined sidechain QC pass for 16/16, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`, mean rotamer angle deviation `18.718` degrees.
- `runs/casp17_prediction_import_packet_model_selected_refined_current.json`, `runs/casp17_prediction_validation_batch_model_selected_refined_current.json`, `runs/casp17_internal_scorecard_batch_model_selected_refined_current.json`, and `runs/casp17_submission_gate_packet_model_selected_refined_current.json`: the full heavy-atom model-selected refined lane clears import, format, geometry, confidence, scorecard, and submission gate for 16/16 targets. It is still a support lane until no-leak historical calibration decides whether to promote it.
- `runs/casp17_model_selected_refinement_comparison_packet_current.json`: active statistical-rotamer and model-selected refined lanes are compared target-by-target with gate status, sidechain/all-atom QC, CA shape metrics, source rank, and side-by-side 3D comparison boards. Both lanes pass local gates for 16/16 targets, but promotion is still `blocked_pending_no_leak_historical_calibration`. Current decision summary: review both lanes for 16/16, auto-promote 0/16. Mean active-minus-model-selected soft clash delta is `0.6875`, but several selected models have much larger radius of gyration, so native-free promotion remains unsafe.
- Straight-line PNG root cause: several earlier model-selected support candidates were not render failures; the selected PDB coordinates themselves were overextended because the native-free selector over-weighted consensus/low-clash/interface proxies and under-weighted global compactness. Examples from the older normalized support lane include T1342 model-selected CA radius of gyration `614.888 A` versus active `26.919 A`, T1331 `93.296 A` versus active `14.618 A`, and H2312 `349.09 A` versus active `33.556 A`.
- `tools/build_casp17_current_target_model_selection_packet.py` now includes a shape guard using CA span per residue, CA radius of gyration per residue, and chain-linearity penalties. The shape-guarded selector blocks linear/overextended candidates before recommendation while keeping the no-leak historical calibration requirement fail-closed.
- `tools/build_casp17_structure_shape_sanity_packet.py`: standalone pre-render/pre-submission CA-shape gate now scans any generated TS directory for overextended or line-like coordinates. It checks CA continuity, max CA gap, CA span per residue, CA radius of gyration per residue, chain linearity, and aggregate shape penalty. This makes the straight-line PNG issue a reusable gate instead of a one-off selector fix.
- `runs/casp17_current_target_model_selection_shape_guarded_current.json`: shape-guarded current-target selector `pass`, 80 candidates, 16/16 materialized selected TS files in `runs/casp17_predictions_model_selected_shape_guarded_current`, 14/16 rank-1 recommendations, 2/16 non-rank-1 recommendations, and 0 shape-blocked fallbacks. Previously problematic selections are now compact: T1342 uses rank 1 with span/Rg/end-to-end `208.3/47.6/137.1 A`; T1331 uses rank 2 with `79.3/20.8/42.6 A`; H2312 uses rank 1 with `140.6/31.0/79.0 A`.
- `runs/casp17_structure_shape_sanity_packet_model_selected_shape_guarded_current.json` and `runs/casp17_structure_shape_sanity_packet_current.json`: shape-guarded normalized lane shape sanity `pass`, `16/16`, blocked `0`, max observed span per residue `0.187694`, max observed Rg per residue `0.074113`, max observed chain linearity `0.095013`, max observed shape penalty `0.0`.
- `runs/casp17_structure_shape_sanity_packet_model_selected_normalized_legacy_current.json`: the older normalized model-selected support lane now fails this standalone shape gate as expected, `3/16` pass and `13/16` blocked, with blocked targets `H1335,H1343,H1344,H1346,H1347,H2312,H2319,H2321,H2338,H2339,T1331,T1342,T2313`. This artifact documents why old PNGs could look like straight lines and why the shape-guarded lane is now preferred for review renders.
- As of the 2026-05-25 refresh, the default `*_current` render, publication, image-quality, molecular-viewer, structure-shape, competitive-readiness, win-readiness, readiness-dashboard, and submission-gate artifacts have been regenerated from the shape-guarded coordinate directory `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`. This prevents old overextended model-selected PNGs from being mistaken for the active visual review surface.
- Current local submission floor: `runs/casp17_submission_gate_packet_current.json` reports shape sanity required/pass, `16/16 submission_go`, and no local no-go rows. This is a local format/QC gate only, not a CASP upload or official assessment result.
- Current win-tier bar: `runs/casp17_win_readiness_rubric_packet_current.json` remains `win_tier_level_status=blocked`; the current proven level is `review_quality` because no-leak historical native benchmarks, refinement-ablation evidence, sidechain-native benchmark rows, and model-selection calibration rows are still missing.
- `runs/casp17_predictions_model_selected_shape_guarded_statistical_rotamer_current/*TS.pdb`: the shape-guarded selected TS set has been run through the full internal heavy-atom stack: sidechain scaffold, repack, completion repair, extended steric relax, rotamer minimization, polar refinement, forcefield-style minimization, and statistical-rotamer packing proxy. Final stack packets are green for 16/16. Key internal metrics: scaffold mean heavy-atom completion `0.993003`; completion repair inserted `960` missing sidechain atoms and left `0`; extended steric relax reduced soft contacts `5823 -> 156`; statistical-rotamer final soft contacts stayed `154 -> 154`.
- `runs/casp17_all_atom_quality_packet_model_selected_shape_guarded_current.json`: shape-guarded all-atom QC `pass` for 16/16, heavy-atom completion `1.0`, severe clashes `0`, soft clashes `154`, mean soft clashscore `0.992` per 1000 atoms.
- `runs/casp17_sidechain_quality_packet_model_selected_shape_guarded_current.json`: shape-guarded sidechain QC `pass` for 16/16, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`, mean rotamer angle deviation `18.271` degrees.
- `runs/casp17_pdb_coordinate_frame_packet_model_selected_shape_guarded_current.json`: coordinate-frame normalization `pass` for 16/16, fixed-width parse errors `0 -> 0`, shifted targets `0`, normalized directory `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`.
- `runs/casp17_prediction_import_packet_model_selected_shape_guarded_current.json`, `runs/casp17_prediction_validation_batch_model_selected_shape_guarded_current.json`, `runs/casp17_internal_scorecard_batch_model_selected_shape_guarded_current.json`, and `runs/casp17_submission_gate_packet_model_selected_shape_guarded_current.json`: shape-guarded normalized lane clears import, format, geometry, confidence, scorecard, and submission gate for 16/16 targets, with `submission_go 16/16`. This remains a support lane until no-leak historical calibration decides promotion.
- `runs/casp17_model_selected_shape_guarded_refinement_comparison_packet_current.json`: active-vs-shape-guarded comparison `pass`, active/model-selected gates `16/16`, promotion still `blocked_pending_no_leak_historical_calibration`. Shape outliers are removed: H1335 model/active Rg ratio `0.929748`, H2312 `0.922547`, T1331 `1.424682`, and T1342 `1.768936`, replacing the prior 6x-23x overextended cases.
- `runs/casp17_sidechain_scaffold_packet_current.json`: sidechain scaffold pass for 16/16, mean heavy-atom completion `0.997793`.
- `runs/casp17_sidechain_repack_packet_current.json`: sidechain repack pass for 16/16; soft close contacts improved from `1756` to `1352`.
- `runs/casp17_sidechain_completion_repair_packet_current.json`: completion repair pass for 16/16; missing sidechain atoms after repair `0`.
- `runs/casp17_steric_relax_packet_current.json`: steric relax pass for 16/16; soft close contacts improved from `1788` to `18`.
- `runs/casp17_rotamer_minimization_packet_current.json`: rotamer minimization pass for 16/16; soft close contacts `18 -> 16`.
- `runs/casp17_polar_refinement_packet_current.json`: polar refinement pass for 16/16; soft close contacts `16 -> 15`.
- `runs/casp17_forcefield_minimization_packet_current.json`: forcefield-style minimization pass for 16/16; soft close contacts held `15 -> 15`.
- `runs/casp17_statistical_rotamer_packet_current.json`: statistical-rotamer packing proxy pass for 16/16; soft close contacts held `15 -> 15`.
- `runs/casp17_all_atom_quality_packet_current.json`: internal steric/completion QC pass for 16/16, severe clashes `0`, total soft close contacts `15`, max soft clashscore `0.427` per 1000 atoms.
- `runs/casp17_sidechain_quality_packet_current.json`: sidechain completeness/rotamer-frame QC pass for 16/16, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`.
- `runs/casp17_molecular_viewer_packet_current.json`: 16/16 final selected TS predictions embedded in the local molecular viewer packet; embedded PDB author records are redacted. The viewer is now internal-canvas-first and internal-only by default: external network handoff is disabled, no hosted 3Dmol/Mol* URL is emitted unless explicitly enabled, residue-class coloring/counts are embedded, fixed confidence bins are shown, internal QC overlay totals are wired in from render/review/all-atom/sidechain packets, and static fallbacks prefer the new presentation plate if the embedded canvas cannot parse/render the PDB.
- `runs/casp17_molecular_viewer_smoke_packet_current.json`: static internal-canvas viewer smoke is `pass` for 16/16 embedded targets; internal viewer symbols `8/8`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, and presentation-plate fallbacks `16/16`.
- `runs/casp17_structure_render_packet_current.json`: 16/16 local 3D structure renders from final statistical-rotamer TS coordinates; PyMOL base/confidence/QC/surface/review, residue-class, predicted CA interface-map, orthographic stereo-depth, turntable review strip, atlas-panel, molecular-plate, and presentation-plate coverage is 16/16 with 0 blocked rows. Predicted CA interface map summary: chain-pair rows `58`, contacts within 12 A `8486`.
- Render contact-sheet smoke checks are nonblank at 1680x1320; base, QC, surface, confidence, residue-class, predicted CA interface-map, stereo-depth, turntable, review, atlas, molecular-plate, and presentation-plate contact sheets are nonflat/colorful. The turntable contact sheet is present at `runs/casp17_structure_render_turntable_contact_sheet_current.png`, and sampled T1331 turntable review is visually usable with eight local orthographic/tilted inspection panels.
- `runs/casp17_publication_figure_packet_current.json`: high-resolution molecular publication figures are `pass` for 16/16 targets. The packet composes the existing local PyMOL/studio/stereo-depth/confidence/surface/QC/residue/interface/turntable panels into 3840x2160 review figures plus `runs/casp17_publication_figure_contact_sheet_current.png`; it also emits 16/16 molecular inspection posters, 16/16 molecular scene posters, 16/16 molecular review boards, 16/16 molecular showcases, `runs/casp17_molecular_inspection_poster_contact_sheet_current.png`, `runs/casp17_molecular_scene_poster_contact_sheet_current.png`, `runs/casp17_molecular_review_board_contact_sheet_current.png`, `runs/casp17_molecular_showcase_contact_sheet_current.png`, and the local no-network gallery `runs/casp17_molecular_inspection_gallery_current.html`. Minimum observed publication colorful pixels are `8,200,384`, sampled unique colors `810`, and luminance range `253.648`; minimum observed showcase colorful pixels are `8,190,016`, sampled unique colors `1058`, and luminance range `255.0`.
- `runs/casp17_structure_render_packet_model_selected_current.json`: full heavy-atom model-selected refined structures also have 16/16 local 3D render coverage, including PyMOL base/QC/surface/confidence, residue-class, interface-map, stereo-depth, turntable, molecular-plate, and presentation-plate outputs with 0 blocked rows. The sampled T1331 model-selected turntable visibly shows the selected non-rank-1 candidate's elongated topology, so this lane is useful for structural triage but remains unpromoted without native calibration.
- `runs/casp17_publication_figure_packet_model_selected_current.json` and `runs/casp17_structure_image_quality_packet_model_selected_current.json`: model-selected refined visual QC is `pass`, publication/review figures are 16/16, image-quality smoke is 256/256, stereo-depth renders are 16/16, turntable renders are 16/16, and publication/review images are 64/64.
- `runs/casp17_structure_render_packet_model_selected_shape_guarded_current.json`: shape-guarded normalized structures have 16/16 local 3D render coverage with PyMOL base/QC/surface/confidence, residue-class, interface-map, stereo-depth, turntable, molecular-plate, and presentation-plate outputs, blocked `0`. Rendered PyMOL base/QC/surface/confidence counts are each `16/16`; raw/rendered QC hotspots are `2797/576`, soft hotspots `165`.
- `runs/casp17_publication_figure_packet_model_selected_shape_guarded_current.json`: shape-guarded publication/review figures `pass`, 16/16 publication figures, 16/16 inspection posters, 16/16 scene posters, and 16/16 review boards. Minimum observed colorful pixels are `8200384`, unique colors `810`, and luminance range `253.648`.
- `runs/casp17_structure_image_quality_packet_model_selected_shape_guarded_current.json`: shape-guarded rendered-image smoke `pass`, images `256/256`, stereo-depth `16/16`, turntable `16/16`, publication/review images `64/64`, minimum estimated colorful pixels `1012075`, edge pixels `50050`, luminance range `93.823`.
- `runs/casp17_molecular_viewer_model_selected_shape_guarded_current.html` plus `runs/casp17_molecular_viewer_smoke_packet_model_selected_shape_guarded_current.json`: shape-guarded internal-canvas viewer smoke `pass`, `16/16`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`, HTML size `12951133` bytes.
- `runs/casp17_model_selected_refinement_comparison_current/*_lane_comparison_board.png` and `runs/casp17_model_selected_refinement_comparison_contact_sheet_current.png`: side-by-side active-vs-model-selected refined molecular comparison boards are available for 16/16 targets. Each board includes active and selected turntables, active and selected presentation plates, selected rank, selection score, soft-clash delta, CA radius of gyration, CA contact counts, lane decision, and fail-closed promotion status.
- `runs/casp17_structure_render_review_queue_current.json`: hotspot- and predicted-interface-prioritized 3D visual review queue is `ready` for 16/16 rendered targets, with atlas and interface-map panels linked for every target. QC metadata now separates raw hotspots from capped rendered markers: raw/rendered QC `2674/576`, soft `30/30`, low-confidence `2653/555`, and 16/16 targets are marker-truncated at the 36-marker cap. Predicted CA interface triage summary: interface maps `16/16`, chain-pair rows `58`, contacts within 12 A `8486`, top interface target `H1335`.
- `casp17/`: current local CASP17 data mirror is ready. `casp17/casp17_data_bundle_manifest_current.json` records 798 top-level artifacts, 796 mirrored `runs/casp17*` artifacts, 1 CASP17 doc artifact, 1 CASP17 config artifact, 5,924 files under mirrored artifacts, and 0 missing bundled artifacts. Exact byte size is tracked in the manifest. Original `runs/`, `docs/`, and `config/` paths remain intact.
- `runs/casp17_historical_benchmark_manifest_scaffold_current.json`: local manifest scaffold/checklist exists and currently fails closed as `blocked`; it emits one placeholder monomer row and one placeholder complex row, both requiring local prediction/native PDB files plus strict no-leak provenance columns. The scaffold CSV now exposes optional refinement-ablation layer path columns from `recursive_prediction_pdb` through `statistical_rotamer_prediction_pdb`.
- `runs/casp17_historical_benchmark_manifest_promotion_current.json`: local manifest promotion gate exists and currently fails closed as `blocked`; it promotes 0/2 scaffold rows, writes an empty header-only `runs/casp17_historical_benchmark_manifest_ready_current.csv`, blocks placeholder rows, excludes current CASP17 targets, and rejects rows without prediction/native date and provenance clearance evidence. Promotion preserves layer-specific ablation path columns into the ready manifest instead of dropping them.
- `runs/casp17_historical_input_preflight_packet_current.json`: local no-leak historical input preflight exists and currently fails closed as `blocked`; source mode is `scaffold`, candidate/historical-ready/ablation-ready counts are `2/0/0`, missing prediction/native/layer files are `2/2/20`, and both placeholder rows remain blocked before scoring.
- `runs/casp17_historical_input_workorder_packet_current.json`: local no-leak historical input workorder exists and is `ready`; it translates the blocked preflight into 2 operator workorders and writes `runs/casp17_historical_benchmark_manifest_operator_template_current.csv`. Current workorder counts are core/ablation/complete `2/0/0`, missing core files `4`, and missing ablation layer files `20`.
- `runs/casp17_historical_benchmark_packet_current.json`: local no-leak historical native benchmark harness exists and currently fails closed as `blocked` because `runs/casp17_historical_benchmark_manifest_current.csv` is missing. It has 0 benchmark rows, `sequence_exact_match_count=0/0`, `chain_exact_match_count=0/0`, and `manifest_blockers=manifest_missing`. When rows are present, the scorer now requires prediction/native chain IDs, scope chain count, residue-key overlap, and residue identity exactness before native proxy scores can count as pass evidence.
- `runs/casp17_refinement_ablation_packet_current.json`: local no-leak historical refinement-ablation harness exists and currently fails closed as `blocked` because the same no-leak historical benchmark manifest is missing. It is prepared to compare recursive, scored, sidechain-scaffold, sidechain-repacked, sidechain-completed, steric-relaxed, rotamer-minimized, polar-refined, forcefield-minimized, and statistical-rotamer layers against cleared historical natives, while keeping current CASP17 target natives out of scope.
- `runs/casp17_model_selection_calibration_scaffold_current.json`: model-selection calibration scaffold/checklist exists and currently fails closed as `blocked`; source mode is `placeholder_required_inputs`, candidate rows are `2`, ready rows are `0`, blocked rows are `2`, and the missing input is `runs/casp17_model_selection_calibration_current.csv`. It emits one required monomer row and one required complex row with no-leak clearance, selected/best rank, selected/best native metric, and selected/best internal score fields still required.
- `runs/casp17_model_selection_calibration_packet_current.json`: model-selection calibration packet exists and fails closed as `blocked`; SCORE coverage is `pass`, QSCORE coverage is `pass`, ranked top-5 candidate depth is `pass`, but historical exactness is `blocked` and calibration rows are `0/0` because `runs/casp17_model_selection_calibration_current.csv` is missing.
- `runs/casp17_competitive_readiness_packet_current.json`: submission floor `pass`, top-5 ranked depth `pass`, SCORE/QSCORE record coverage `pass`, all-atom/sidechain quality remains `partial` with scaffold, not-worse repack, missing-sidechain completion repair, sidechain-only steric relaxation, residue-class rotamer minimization, polar refinement, forcefield minimization, all-atom QC, and sidechain-quality proxy evidence, and competitive/win-tier readiness still `blocked` by five accuracy-quality gaps, including missing no-leak monomer/complex benchmark rows and blocked refinement-ablation evidence.
- `runs/casp17_win_readiness_rubric_packet_current.json`: submission-level status `pass`, review-quality status `pass`, competitive floor `partial`, and win-tier level `blocked`; requirement count is `9`, with first current gap all-atom steric quality, followed by missing no-leak monomer/complex native benchmarks, blocked refinement-ablation evidence, and confidence/model-selection calibration.
- `runs/casp17_win_tier_action_queue_packet_current.json`: win-tier action queue is `blocked` overall with `8` actions; `all_atom_quality_upgrade` is first and is `blocked_input` until sidechain-native benchmark evidence exists, while historical benchmark inputs, historical native scoring, refinement-ablation native evidence, model-selection calibration inputs/gate, and final CASP upload remain fail-closed.
- `runs/casp17_structure_image_quality_packet_current.json`: image-quality smoke is `pass` for 272/272 visual artifacts, including 192 render-panel images plus 80 publication/review/showcase images. Targets complete `16/16`, stereo-depth renders `16/16`, turntable review strips `16/16`, molecular plates `16/16`, presentation plates `16/16`, publication/review/showcase images `80/80`, minimum estimated colorful pixels `1,012,075`, minimum estimated edge pixels `50,050`, and minimum luminance range `93.823`.
- `runs/casp17_win_tier_threshold_packet_current.json`: operational threshold packet is `blocked_input`, current proven level `review_quality`, threshold rows pass/partial/blocked `5/1/7`, and the first threshold gap is `sidechain_native_quality/sidechain_native_lddt` with blocker `sidechain_native_benchmark_missing_or_blocked`. Current-target submission, top-5 depth, internal canvas viewer plus 16/16 stereo-depth and 16/16 turntable molecular visuals, molecular inspection/scene/review-board visuals, local severe-clash, and soft-clash thresholds pass; no-leak native/ablation/calibration thresholds remain blocked or partial. Complex win-tier evidence now requires both interface F1 and DockQ-like proxy rows.
- `runs/casp17_win_tier_benchmark_closure_plan_current.json`: no-leak benchmark closure plan is `ready` as a planning artifact and `blocked_input` as evidence. Competitive floor needs 10 monomer + 5 complex historical rows; win-tier needs 25 monomer + 15 complex rows. Current no-leak historical rows are 0/40, so the win-tier gap is 40 internal prediction PDBs, 40 native PDBs, 400 ablation-layer prediction PDBs, and 40 model-selection calibration rows. The expanded operator template is `runs/casp17_win_tier_benchmark_operator_template_current.csv`.
- `runs/casp17_win_tier_benchmark_operator_preflight_current.json`: expanded 40-row win-tier operator template is currently `blocked` as expected for placeholders: ready/blocked `0/40`, missing prediction/native/layer files `40/40/400`, calibration-blocked rows `40`, and threshold blockers `ready_total_below_threshold,ready_monomer_below_threshold,ready_complex_below_threshold`.
- `runs/casp17_win_tier_benchmark_operator_import_packet_current.json`: expanded benchmark import is fail-closed as `blocked`; candidate historical/calibration rows are `0/0`, candidate CSVs are header-only, and blockers are `operator_preflight_not_pass,ready_count_below_import_threshold`.
- `runs/casp17_win_tier_benchmark_activation_packet_current.json`: active benchmark/calibration activation is fail-closed as `blocked`; candidate historical/calibration CSV rows are `0/0`, operator import is blocked, active manifest/calibration files were not written, and blockers include empty candidate CSVs plus validated historical/calibration rows below threshold.
- `runs/casp17_win_tier_benchmark_operator_dashboard_current.json`: operator dashboard is `ready` as a local work surface and summarizes all 40 win-tier benchmark rows. Current ready/blocked rows are `0/40`; monomer/complex rows are `25/15`; target replacement, core prediction/native files, ablation layers, calibration fields, and no-leak provenance are each still needed for `40/40` rows. The dashboard now exposes required native metric profiles: monomer `TM,GDT_TS,CA_lDDT`, complex `TM,interface_F1,DockQ,QSbest,IPS`. The local no-network HTML dashboard is `runs/casp17_win_tier_benchmark_operator_dashboard_current.html`.
- `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.json`: operator evidence fill kit is `ready` and itemizes the 40-row no-leak benchmark work into 1,310 required evidence items, including 150 native metric gate rows. Current filled/missing evidence items are `0/1310`; missing classes are target identity `40`, core files `80`, ablation-layer files `400`, no-leak provenance fields `400`, calibration fields `240`, and native metric gates `150`. The local no-network HTML checklist is `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.html`.
- `runs/casp17_win_tier_benchmark_input_scaffold_current.json`: row-level input scaffold is `ready` and expands the 40 win-tier benchmark rows into 40 local row folders, 160 row-level README/required-file/provenance/calibration files, draft historical manifest CSV, and draft model-selection calibration CSV. Required file slots are prediction/native/ablation `40/40/400` (`480` total), with monomer/complex rows `25/15`.
- `runs/casp17_win_tier_benchmark_input_inventory_current.json`: input inventory is `blocked` as expected for the current placeholder scaffold. It scans the row-level required-files/provenance/calibration templates and reports ready/blocked rows `0/40`, present/missing required files `0/480`, prediction/native present `0/0`, ablation present/required `0/400`, provenance-ready rows `0`, and calibration-ready rows `0`.
- `runs/casp17_win_tier_benchmark_fill_priority_packet_current.json`: fill-priority plan is `ready` and orders the 40 no-leak benchmark input rows into the next operator batches. Competitive-floor batch rows are monomer/complex/total `10/5/15`, win-required rows are `40`, missing win evidence items remain `1310`, and the first action is to replace `hist_REQUIRED_MONOMER_001` placeholder identity with a cleared historical non-current CASP target.
- `runs/casp17_readiness_dashboard_current.json`: consolidated local dashboard is `ready` and summarizes submission/review/competitive/win-tier/external-boundary levels in one no-network HTML. Current proven level is `review_quality`, next unclosed level is `competitive_floor`, submission floor `pass`, review quality `pass`, model-selection review `partial`, competitive floor `partial`, win-tier `blocked`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, shape-guarded coordinate frame `pass 16/16`, shape sanity `pass 16/16`, shape-guarded image QC `272/272`, stereo-depth renders `16/16`, turntable review strips `16/16`, publication/review/showcase images `80/80`, review boards `16/16`, molecular showcases `16/16`, benchmark rows ready/total `0/40`, missing win-tier evidence `1310/1310`, input inventory present/missing files `0/480`, data bundle artifacts `798`, and HTML `runs/casp17_readiness_dashboard_current.html`.
- `runs/casp17_win_gap_closure_packet_current.json`: closure status is `blocked_input`; the highest proven level is `review_quality`, the next unclosed level is `competitive_floor`, the first open dimension is `all_atom_steric_quality`, first threshold gap is `sidechain_native_quality/sidechain_native_lddt`, and the first operator-input action is `historical_benchmark_inputs`. It now embeds the benchmark closure plan, operator preflight, and operator import: missing win rows `40/40`, required prediction/native/ablation/calibration `40/40/400/40`, operator ready/blocked `0/40`, and import candidate rows `0/0`.
- Predictor finalization now applies bond-window repair, best-model heavy intrachain polishing, and global interchain separation; the regenerated 16-target lane clears the local viewer issue overlay.
- Historical and sidechain-native benchmark scorers require full CA coverage by default, so subset-only prediction/native overlaps cannot pass win-tier evidence.
- CASP17 focused selection/activation/render/dashboard/bundle suite: 15 passed in 17.41s.
- CASP17 focused forcefield/model-selection/render/publication/image-quality/bundle suite: 12 passed in 17.75s.
- CASP17 focused comparison/bundle suite: 3 passed in 0.62s.
- CASP17 targeted unit suite: 165 passed in 55.62s after strict provenance, coverage, top-5 internal selection materialization, model-selected heavy-atom backmapping/refinement support lane generation, active-vs-model-selected visual comparison board generation, robust wide-coordinate PDB atom-line rewriting, render raw/display QC, residue-class/interface-map/stereo-depth/turntable/molecular-plate/presentation-plate render integration, molecular inspection/scene/review-board gallery gating, image-quality smoke gating, consolidated readiness dashboard generation, interface-aware review queue integration, CASP17 data-bundle mirroring, win-gap closure packet generation, historical input workorder generation, benchmark operator dashboard/import/activation/fill-kit/input-scaffold/input-inventory fail-closed gating, refinement-ablation manifest-column preservation, historical input preflight integration, complex DockQ/QSbest/IPS proxy benchmark gating, native metric gate enumeration, and static-first molecular viewer QC overlay integration.

## Claim Boundary

Safe wording before official CASP assessment:

> The repository is internally gated for CASP17 regular-group protein target submission using a 100% internal physics baseline, with all current open selected protein targets passing local format, geometry, confidence, scorecard, submission, and internal geometry/confidence readiness proxy gates.

Do not claim CASP17 ranking, native accuracy, experimental correctness, commercial parity, or accepted submission until no-leak benchmark evidence and official CASP evidence exist.

The emitted backbone atoms are explicitly labeled as a CA-anchored compact pseudo-backbone. The sidechain scaffold adds residue-specific heavy atoms plus local frame-rotamer candidate selection, the repack packet adds fail-closed not-worse local sidechain polish, the completion repair packet fills missing sidechain atoms as a pre-relax intermediate, the steric-relax packet adds sidechain-only clash relaxation with backbone fixed, the rotamer-minimization packet adds an internal residue-class rotamer-prior steric/polar greedy pass, the polar-refinement packet adds internal sidechain-only hbond/salt/steric fine-tuning, the forcefield-minimization packet adds short sidechain-only forcefield-style local minimization, and the all-atom/sidechain quality packets add internal steric/completion/rotamer-frame proxy QC. These are not Dunbrack/Richardson statistical rotamer-library validation, full all-atom energy minimization, official MolProbity scoring, or native accuracy evidence.

## Competitive Target Levels

There are two different bars:

1. Submission floor: local TS format, sequence/chain coverage, geometry, confidence, scorecard, submission gate, and visual sanity all pass. The current internal lane reaches this local floor.
2. Win-tier evidence: no-leak historical benchmark evidence that the method is competitive with recent top CASP systems. The current internal lane does not yet prove this.

Current win-tier target bands to build toward:

These are target acceptance bands for future no-leak historical benchmarks, not current measured CASP17 performance.

- Monomers/domains: mean TM-score around 0.90 on a historical no-leak CASP-like benchmark, GDT_TS/GDT_HA roughly 0.80-0.85+, high lDDT, low MolProbity/clash/sidechain errors, and correct-fold rate above 95%.
- Complexes/assemblies: average TM-score around 0.75-0.80 and DockQ around 0.55-0.60 on historical complex targets, with calibrated interface confidence, correct stoichiometry, and strong interface contact scores.
- Submission strategy: up to five genuinely diverse ranked models per target, with MODEL 1 selected by a calibrated internal ranking/EMA system.

Operational levels:

- `L0 blocked`: missing prediction file, sequence mismatch, format error, no GPU runtime evidence for production generation, or author/submission state not ready.
- `L1 local submission floor`: CASP TS format, one target per file, MODEL records <= 5, MODEL 1 selected, PARENT/TER records, B-factor confidence, SCORE/QSCORE where applicable, internal format/geometry/confidence/scorecard/submission gates, and visual sanity all pass.
- `L2 review-quality floor`: L1 plus nonblank molecular viewer, PyMOL base/surface/QC/confidence renders, high-resolution molecular inspection posters, molecular scene posters, molecular review boards, presentation plates, atlas/review panels, and review queue ready for every current target.
- `L3 competitive floor`: L2 plus ranked top-5 candidates, SCORE/QSCORE coverage, low all-atom clash burden, complete sidechains, and no-leak historical benchmark scaffolds ready.
- `L4 win-tier evidence`: L3 plus no-leak native-scored monomer and complex benchmarks in the target bands above, sidechain-native benchmark pass, calibrated selected-vs-oracle model ranking, and calibrated confidence/SCORE/QSCORE.

Current local gaps recorded in `runs/casp17_competitive_readiness_packet_current.*`:

- historical native-scored benchmark harness exists, but the no-leak manifest is missing, so monomer win-tier accuracy is still unproven
- historical native-scored complex/interface benchmark harness exists, but the no-leak manifest is missing, so complex/interface win-tier accuracy is still unproven
- sidechain scaffold/completion/relax/rotamer/polar/forcefield/QC exists and validates locally with local frame-rotamer candidate selection and internal steric/completion/rotamer-frame proxy QC, but it is not true rotamer-library packed, full energy-minimized, official MolProbity-calibrated all-atom refinement
- refinement-ablation harness exists, but no cleared historical layer rows exist yet, so final-vs-baseline improvement is unproven
- confidence is ensemble-variance based but not native-calibrated

## Registration Policy

Recommended operating state:

1. Use a regular prediction group for manual submissions.
2. Keep server registration blocked until a separate 72-hour automated server path has its own green gate.
3. Select tertiary structure prediction and assembly/quaternary prediction for the current protein/complex scope.
4. Keep the CASP author code out of committed files and pass it only through `--author-code` at execution time.

Official CASP17 references:

- Main experiment page: https://predictioncenter.org/casp17/
- Registration instructions: https://predictioncenter.org/casp17/registration.cgi
- Submission rules and format: https://predictioncenter.org/casp17/index.cgi?page=format

## Internal Go/No-Go Gate

A target can be submitted only when all required local checks pass:

- `deadline_class=regular`
- `target_id` is present.
- `submission_format=TS`
- `sequence_path` exists and exactly matches the predicted residue sequence.
- `prediction_file_path` exists.
- `format_check_status=pass`
- `model_generation_status=pass`
- `geometry_sanity_status=pass`
- `confidence_calibration_status=pass`
- `internal_scorecard_status=pass`
- Backend contract records `backend_kind=internal_physics`.
- GPU runtime evidence is present for production-quality generation.
- The final submission gate returns `submission_go`.
- The accuracy-readiness proxy returns `pass`.

Fail-closed rules:

- Missing target files block submission.
- Unknown or server-only deadline class blocks submission.
- A target-specific validation JSON with hard blockers blocks submission even if the CSV row says pass.
- A stale or blocked local delivery/accounting artifact blocks all target submission decisions.
- Any external/public/template/provenance ambiguity blocks the existing-structure attach lane.
- CASP portal upload remains blocked until the operator explicitly confirms the external-state action.

## Current Internal Physics Lane

Refresh the current target watchlist and sequences:

```bash
python3 tools/build_casp17_target_watchlist.py

python3 tools/build_casp17_sequence_packet.py \
  --intake-csv runs/casp17_target_intake_seed_current.csv
```

Build the internal-physics launch packet for all current protein targets:

```bash
python3 tools/build_casp17_prediction_import_packet.py \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --out-json runs/casp17_prediction_import_packet_recursive_current.json \
  --out-csv runs/casp17_prediction_import_packet_recursive_current.csv \
  --out-md runs/casp17_prediction_import_packet_recursive_current.md \
  --out-intake-csv runs/casp17_target_intake_prediction_imported_recursive_current.csv
```

For a fresh internal-physics re-run of every current open target, do not let an older import packet skip existing predictions. Use a nonexistent or empty import packet path for launch planning; the real import packet is regenerated by the TS gate after conversion.

```bash
python3 tools/build_casp17_prediction_launch_packet.py \
  --target-scope all_protein \
  --target-limit 0 \
  --backend-mode internal_physics \
  --backend-supports-multimer \
  --allow-deadline-close \
  --internal-quality-preset casp17_quality \
  --internal-emit-backbone-atoms \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --prediction-import-json runs/casp17_prediction_import_packet_recursive_force_empty_current.json \
  --out-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --out-csv runs/casp17_prediction_launch_packet_recursive_current.csv \
  --out-md runs/casp17_prediction_launch_packet_recursive_current.md
```

Run all ready targets through internal prediction and backend contract validation:

```bash
python3 tools/run_casp17_prediction_batch_gate.py \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --execute \
  --stop-after contract \
  --timeout-seconds 21600 \
  --target-limit 0 \
  --continue-on-error \
  --attempt-dir runs/casp17_prediction_recursive_contract_attempts_current \
  --out-json runs/casp17_prediction_recursive_contract_batch_current.json \
  --out-csv runs/casp17_prediction_recursive_contract_batch_current.csv \
  --out-md runs/casp17_prediction_recursive_contract_batch_current.md
```

If using `run_casp17_prediction_batch_gate.py` past `contract`, pass the recursive artifact paths through explicitly so import, validation, scorecard, and submission gate all inspect the same prediction directory:

```bash
python3 tools/run_casp17_prediction_batch_gate.py \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --execute \
  --stop-after submission_gate \
  --timeout-seconds 21600 \
  --target-limit 0 \
  --continue-on-error \
  --author-code <CASP_AUTHOR_CODE> \
  --attempt-dir runs/casp17_prediction_recursive_contract_attempts_current \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --import-json runs/casp17_prediction_import_packet_recursive_current.json \
  --import-csv runs/casp17_prediction_import_packet_recursive_current.csv \
  --import-md runs/casp17_prediction_import_packet_recursive_current.md \
  --imported-intake-csv runs/casp17_target_intake_prediction_imported_recursive_current.csv \
  --validation-dir runs/casp17_validations_recursive_current \
  --validation-json runs/casp17_prediction_validation_batch_recursive_current.json \
  --validation-csv runs/casp17_prediction_validation_batch_recursive_current.csv \
  --validation-md runs/casp17_prediction_validation_batch_recursive_current.md \
  --validated-intake-csv runs/casp17_target_intake_validated_recursive_current.csv \
  --scorecard-dir runs/casp17_internal_scorecards_recursive_current \
  --scorecard-json runs/casp17_internal_scorecard_batch_recursive_current.json \
  --scorecard-csv runs/casp17_internal_scorecard_batch_recursive_current.csv \
  --scorecard-md runs/casp17_internal_scorecard_batch_recursive_current.md \
  --scored-intake-csv runs/casp17_target_intake_scored_recursive_current.csv \
  --submission-gate-json runs/casp17_submission_gate_packet_recursive_current.json \
  --submission-gate-csv runs/casp17_submission_gate_packet_recursive_current.csv \
  --submission-gate-md runs/casp17_submission_gate_packet_recursive_current.md \
  --out-json runs/casp17_prediction_recursive_contract_batch_current.json \
  --out-csv runs/casp17_prediction_recursive_contract_batch_current.csv \
  --out-md runs/casp17_prediction_recursive_contract_batch_current.md
```

Run the raw gate:

```bash
python3 tools/build_casp17_internal_physics_raw_gate_packet.py \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --require-gpu \
  --out-dir runs/casp17_internal_physics_raw_validations_recursive_current \
  --out-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --out-csv runs/casp17_internal_physics_raw_gate_packet_recursive_current.csv \
  --out-md runs/casp17_internal_physics_raw_gate_packet_recursive_current.md
```

Convert raw PDBs to CASP TS and run downstream gates:

```bash
python3 tools/casp17/run_casp17_internal_physics_ts_gate_batch.py \
  --raw-gate-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --launch-packet-json runs/casp17_prediction_launch_packet_recursive_current.json \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_recursive_current \
  --out-dir runs/casp17_internal_physics_ts_gate_recursive_current \
  --author-code <CASP_AUTHOR_CODE> \
  --execute \
  --import-json runs/casp17_prediction_import_packet_recursive_current.json \
  --import-csv runs/casp17_prediction_import_packet_recursive_current.csv \
  --import-md runs/casp17_prediction_import_packet_recursive_current.md \
  --imported-intake-csv runs/casp17_target_intake_prediction_imported_recursive_current.csv \
  --validation-dir runs/casp17_validations_recursive_current \
  --validation-json runs/casp17_prediction_validation_batch_recursive_current.json \
  --validation-csv runs/casp17_prediction_validation_batch_recursive_current.csv \
  --validation-md runs/casp17_prediction_validation_batch_recursive_current.md \
  --validated-intake-csv runs/casp17_target_intake_validated_recursive_current.csv \
  --scorecard-dir runs/casp17_internal_scorecards_recursive_current \
  --scorecard-json runs/casp17_internal_scorecard_batch_recursive_current.json \
  --scorecard-csv runs/casp17_internal_scorecard_batch_recursive_current.csv \
  --scorecard-md runs/casp17_internal_scorecard_batch_recursive_current.md \
  --scored-intake-csv runs/casp17_target_intake_scored_recursive_current.csv \
  --submission-gate-json runs/casp17_submission_gate_packet_recursive_current.json \
  --submission-gate-csv runs/casp17_submission_gate_packet_recursive_current.csv \
  --submission-gate-md runs/casp17_submission_gate_packet_recursive_current.md \
  --out-json runs/casp17_internal_physics_ts_gate_batch_recursive_current.json \
  --out-csv runs/casp17_internal_physics_ts_gate_batch_recursive_current.csv \
  --out-md runs/casp17_internal_physics_ts_gate_batch_recursive_current.md
```

Run the accuracy-readiness proxy:

```bash
python3 tools/build_casp17_internal_physics_accuracy_readiness_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --raw-gate-json runs/casp17_internal_physics_raw_gate_packet_recursive_current.json \
  --ts-gate-json runs/casp17_internal_physics_ts_gate_batch_recursive_current.json \
  --submission-gate-json runs/casp17_submission_gate_packet_recursive_current.json \
  --job-dir runs/casp17_prediction_jobs_recursive_current \
  --require-backbone-atoms \
  --out-json runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json \
  --out-csv runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.csv \
  --out-md runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.md
```

Build local 3D structure render artifacts for visual review:

```bash
python3 tools/build_casp17_structure_render_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --out-dir runs/casp17_structure_renders_current \
  --contact-sheet runs/casp17_structure_render_contact_sheet_current.png \
  --qc-contact-sheet runs/casp17_structure_render_qc_contact_sheet_current.png \
  --surface-contact-sheet runs/casp17_structure_render_surface_contact_sheet_current.png \
  --confidence-contact-sheet runs/casp17_structure_render_confidence_contact_sheet_current.png \
  --residue-class-contact-sheet runs/casp17_structure_render_residue_class_contact_sheet_current.png \
  --interface-contact-sheet runs/casp17_structure_render_interface_contact_sheet_current.png \
  --review-contact-sheet runs/casp17_structure_render_review_contact_sheet_current.png \
  --atlas-contact-sheet runs/casp17_structure_render_atlas_contact_sheet_current.png \
  --molecular-plate-contact-sheet runs/casp17_structure_render_molecular_plate_contact_sheet_current.png \
  --presentation-plate-contact-sheet runs/casp17_structure_render_presentation_contact_sheet_current.png \
  --stereo-contact-sheet runs/casp17_structure_render_stereo_depth_contact_sheet_current.png \
  --out-html runs/casp17_structure_render_gallery_current.html \
  --out-json runs/casp17_structure_render_packet_current.json \
  --out-csv runs/casp17_structure_render_packet_current.csv \
  --out-md runs/casp17_structure_render_packet_current.md \
  --pymol-render \
  --require-pymol-render \
  --pymol-qc-render \
  --require-pymol-qc-render \
  --pymol-surface-render \
  --require-pymol-surface-render \
  --pymol-confidence-render \
  --require-pymol-confidence-render \
  --pymol-executable pymol \
  --pymol-width 1200 \
  --pymol-height 820 \
  --pymol-dpi 180
```

These renders are coordinate visualizations of internal predictions only. They are useful for visual triage and communication, but they are not experimental structures or official CASP accuracy evidence.

The renderer writes both high-resolution publication-style panels and darker molecular-view studio panels such as:

```text
runs/casp17_structure_renders_current/T1331_structure_publication.png
runs/casp17_structure_renders_current/T1331_structure_studio.png
runs/casp17_structure_renders_current/T1331_structure_residue_class.png
runs/casp17_structure_renders_current/T1331_structure_interface_map.png
runs/casp17_structure_renders_current/T1331_structure_pymol.png
runs/casp17_structure_renders_current/T1331_structure_confidence_pymol.png
runs/casp17_structure_renders_current/T1331_structure_surface_pymol.png
runs/casp17_structure_renders_current/T1331_structure_qc_pymol.png
runs/casp17_structure_renders_current/T1331_structure_stereo_depth.png
runs/casp17_structure_renders_current/T1331_structure_review_panel.png
runs/casp17_structure_renders_current/T1331_structure_molecular_plate.png
runs/casp17_structure_renders_current/T1331_structure_presentation_plate.png
runs/casp17_structure_renders_current/T1331_structure_atlas_panel.png
```

The publication panel contains chain-colored and confidence-colored views. The studio panel uses a shaded depth-sorted tube/sphere projection plus a sampled non-CA atomic overlay and confidence legend. The residue-class panel colors the same internal coordinates by hydrophobic, polar, charged, aromatic, special, and unknown residue classes for structure-biology triage without any external template or predictor. The interface map is a predicted-coordinate CA contact sanity view, not native DockQ/interface correctness evidence. The stereo-depth panel adds side-by-side orthographic CA projections with a small azimuth offset for depth inspection from the same internal TS coordinates. When `--pymol-render` is enabled, the packet also writes PyMOL PML scripts and ray-traced cartoon/stick/sphere PNGs, closer to a molecular viewer screenshot while staying entirely local and static. When `--pymol-confidence-render` is enabled, the packet adds a B-factor/pLDDT-style confidence-colored PyMOL render using only the existing TS coordinates and confidence column. When `--pymol-surface-render` is enabled, the packet adds a transparent molecular-surface inspection render with cartoon/CA context. When `--pymol-qc-render` is enabled, a second PyMOL render highlights capped soft close-contact and low-confidence residue hotspots for manual triage. The packet stores uncapped raw QC totals and top hotspot metadata separately from the capped rendered marker count, so the review queue can prioritize true QC burden while keeping images readable. The molecular plate combines orthographic internal coordinate views and QC summaries. The presentation plate is the highest-level static visual: it combines primary molecular render, confidence/surface/QC/residue/interface/atlas/stereo thumbnails, CASP local-readiness metrics, chemistry counts, and an internal CA geometry secondary-structure proxy strip. The atlas panel now includes the presentation plate with stereo depth, studio, residue-class, predicted CA interface map, confidence, surface, and QC views. This is still a visualization of the internal predicted coordinates, not an experimental structure or official CASP accuracy evidence.

Build the hotspot- and predicted-interface-prioritized render review queue and priority contact sheet:

```bash
python3 tools/build_casp17_structure_render_review_queue.py \
  --render-json runs/casp17_structure_render_packet_current.json \
  --top-n 6 \
  --contact-sheet runs/casp17_structure_render_review_priority_contact_sheet_current.png \
  --out-json runs/casp17_structure_render_review_queue_current.json \
  --out-csv runs/casp17_structure_render_review_queue_current.csv \
  --out-md runs/casp17_structure_render_review_queue_current.md \
  --out-html runs/casp17_structure_render_review_queue_current.html
```

The review queue is a local visual triage tool. It prioritizes targets by uncapped raw soft-contact and low-confidence hotspot totals from the render packet, while rendered QC marker overlays remain capped at 36 residues per target for readability. This is not official CASP accuracy evidence.

Build or refresh the local `casp17/` data mirror without moving the original runtime artifacts:

```bash
python3 tools/build_casp17_data_bundle.py \
  --runs-dir runs \
  --docs-dir docs \
  --config-dir config \
  --out-dir casp17 \
  --out-json casp17/casp17_data_bundle_manifest_current.json \
  --out-csv casp17/casp17_data_bundle_manifest_current.csv \
  --out-md casp17/README.md
```

This mirrors top-level `runs/casp17*` artifacts into `casp17/runs/`, mirrors CASP17 docs into `casp17/docs/`, mirrors CASP17 config/templates into `casp17/config/`, and writes a manifest. It is local-only: it does not fetch external structures, mutate CASP portal state, or change the original `runs/`, `docs/`, or `config/` paths used by the pipeline.

Build the submission-vs-win-tier readiness rubric:

```bash
python3 tools/build_casp17_win_readiness_rubric_packet.py \
  --competitive-readiness-json runs/casp17_competitive_readiness_packet_current.json \
  --structure-render-json runs/casp17_structure_render_packet_current.json \
  --all-atom-quality-json runs/casp17_all_atom_quality_packet_current.json \
  --rotamer-minimization-json runs/casp17_rotamer_minimization_packet_current.json \
  --polar-refinement-json runs/casp17_polar_refinement_packet_current.json \
  --sidechain-quality-json runs/casp17_sidechain_quality_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json \
  --model-selection-calibration-json runs/casp17_model_selection_calibration_packet_current.json \
  --out-json runs/casp17_win_readiness_rubric_packet_current.json \
  --out-csv runs/casp17_win_readiness_rubric_packet_current.csv \
  --out-md runs/casp17_win_readiness_rubric_packet_current.md
```

The rubric distinguishes:

- submission floor: official CASP TS formatting, per-target coverage, current local gates, top-5 ranked candidates, and visual sanity artifacts
- competitive floor: sidechain/all-atom steric quality, SCORE/QSCORE records, and model-depth evidence
- win tier: no-leak historical native-scored monomer and complex benchmarks, native-calibrated confidence/model selection, and stronger all-atom/sidechain refinement

Build the ordered win-tier action queue:

```bash
python3 tools/build_casp17_win_tier_action_queue_packet.py \
  --win-rubric-json runs/casp17_win_readiness_rubric_packet_current.json \
  --competitive-readiness-json runs/casp17_competitive_readiness_packet_current.json \
  --historical-scaffold-json runs/casp17_historical_benchmark_manifest_scaffold_current.json \
  --historical-promotion-json runs/casp17_historical_benchmark_manifest_promotion_current.json \
  --historical-input-preflight-json runs/casp17_historical_input_preflight_packet_current.json \
  --historical-input-workorder-json runs/casp17_historical_input_workorder_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --calibration-scaffold-json runs/casp17_model_selection_calibration_scaffold_current.json \
  --calibration-json runs/casp17_model_selection_calibration_packet_current.json \
  --render-json runs/casp17_structure_render_packet_current.json \
  --polar-refinement-json runs/casp17_polar_refinement_packet_current.json \
  --refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json \
  --out-json runs/casp17_win_tier_action_queue_packet_current.json \
  --out-csv runs/casp17_win_tier_action_queue_packet_current.csv \
  --out-md runs/casp17_win_tier_action_queue_packet_current.md
```

The action queue keeps submission/review pass evidence separate from win-tier blockers and marks CASP upload as R4 external state until explicit operator confirmation.

Build the static internal-canvas viewer smoke packet:

```bash
python3 tools/build_casp17_molecular_viewer_smoke_packet.py \
  --viewer-json runs/casp17_molecular_viewer_packet_current.json \
  --viewer-html runs/casp17_molecular_viewer_current.html \
  --out-json runs/casp17_molecular_viewer_smoke_packet_current.json \
  --out-csv runs/casp17_molecular_viewer_smoke_packet_current.csv \
  --out-md runs/casp17_molecular_viewer_smoke_packet_current.md
```

The smoke packet validates embedded target PDB counts, `AUTHOR` redaction, CASP TS headers, local presentation-plate fallback assets, internal canvas runtime symbols, and absence of hosted molecular viewer URLs. It is local artifact readiness evidence only, not browser rendering proof or native accuracy evidence.

Build 4K publication-style molecular figures from the current local render panels:

```bash
python3 tools/build_casp17_publication_figure_packet.py \
  --render-json runs/casp17_structure_render_packet_current.json \
  --out-dir runs/casp17_publication_figures_current \
  --contact-sheet runs/casp17_publication_figure_contact_sheet_current.png \
  --inspection-contact-sheet runs/casp17_molecular_inspection_poster_contact_sheet_current.png \
  --out-html runs/casp17_molecular_inspection_gallery_current.html \
  --out-json runs/casp17_publication_figure_packet_current.json \
  --out-csv runs/casp17_publication_figure_packet_current.csv \
  --out-md runs/casp17_publication_figure_packet_current.md
```

This packet creates one 3840x2160 local molecular figure, one molecular inspection poster, one hero-focused molecular scene poster, one molecular review board, and one molecular showcase per target, plus contact sheets and a local HTML gallery for rapid visual review. The inspection poster combines cartoon, stereo-depth, confidence, surface, QC, residue-class, interface-map, studio-depth, and atlas panels when available. The scene poster uses a polished local studio/PyMOL hero view with stereo-depth, confidence, surface, and residue/interface detail panels. The review board is a one-page structural inspection board that combines primary shape, stereo-depth, confidence, surface, QC, residue-class, interface, and atlas views. The showcase is a PyMOL/surface/studio/confidence/QC synthesis intended to look closer to a molecular-structure review program while remaining local-only. The gallery uses local relative image links only and no hosted JS/CSS/image URLs. It is a local image-quality and presentation-readiness artifact only; it does not prove native accuracy or official CASP ranking.

Build the operational submission/competitive/win-tier numeric threshold packet:

```bash
python3 tools/build_casp17_win_tier_threshold_packet.py \
  --win-rubric-json runs/casp17_win_readiness_rubric_packet_current.json \
  --competitive-readiness-json runs/casp17_competitive_readiness_packet_current.json \
  --molecular-viewer-json runs/casp17_molecular_viewer_packet_current.json \
  --molecular-viewer-smoke-json runs/casp17_molecular_viewer_smoke_packet_current.json \
  --structure-image-quality-json runs/casp17_structure_image_quality_packet_current.json \
  --publication-figure-json runs/casp17_publication_figure_packet_current.json \
  --all-atom-quality-json runs/casp17_all_atom_quality_packet_current.json \
  --sidechain-quality-json runs/casp17_sidechain_quality_packet_current.json \
  --sidechain-native-benchmark-json runs/casp17_sidechain_native_benchmark_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json \
  --model-selection-calibration-json runs/casp17_model_selection_calibration_packet_current.json \
  --out-json runs/casp17_win_tier_threshold_packet_current.json \
  --out-csv runs/casp17_win_tier_threshold_packet_current.csv \
  --out-md runs/casp17_win_tier_threshold_packet_current.md
```

The threshold packet is the machine-readable target band for "what level do we need to hit?" It currently records 27 numeric/operational rows: submission gate, top-5 depth, internal canvas visual review, local all-atom/sidechain QC, sidechain-native lDDT/RMSD, historical monomer TM/GDT_TS/CA_lDDT/fold-rate targets, historical complex TM/interface-F1/DockQ targets, refinement-ablation no-worse/improved/delta targets, and model-selection/confidence calibration. Current status is `blocked_input`, pass/partial/blocked `7/2/18`, with first threshold gap `local_all_atom_qc/max_soft_clashscore_per_1000_atoms`. The visual molecular review row now requires `runs/casp17_molecular_viewer_smoke_packet_current.json`, rendered image-quality smoke, `runs/casp17_publication_figure_packet_current.json`, 16/16 molecular inspection posters, 16/16 molecular scene posters, 16/16 molecular review boards, and 16/16 molecular showcases to pass.

Build the no-leak benchmark closure plan that expands the competitive/win-tier native-evidence gap into concrete row and file counts:

```bash
python3 tools/build_casp17_win_tier_benchmark_closure_plan.py \
  --threshold-json runs/casp17_win_tier_threshold_packet_current.json \
  --historical-workorder-json runs/casp17_historical_input_workorder_packet_current.json \
  --sidechain-native-json runs/casp17_sidechain_native_benchmark_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json \
  --model-selection-calibration-json runs/casp17_model_selection_calibration_packet_current.json \
  --out-json runs/casp17_win_tier_benchmark_closure_plan_current.json \
  --out-csv runs/casp17_win_tier_benchmark_closure_plan_current.csv \
  --out-md runs/casp17_win_tier_benchmark_closure_plan_current.md \
  --out-template-csv runs/casp17_win_tier_benchmark_operator_template_current.csv
```

The benchmark closure plan currently shows: competitive floor needs 15 no-leak historical rows, win-tier needs 40, current ready rows are 0, and the remaining win-tier operator inputs are 40 internal prediction PDBs, 40 local historical native PDBs, 400 per-layer ablation prediction PDBs, and 40 selected-vs-oracle calibration rows. This is a local planning artifact only; it does not fetch native structures, clear provenance, score accuracy, or submit to CASP.

Preflight the expanded operator template before promoting any historical benchmark rows:

```bash
python3 tools/build_casp17_win_tier_benchmark_operator_preflight.py \
  --operator-template-csv runs/casp17_win_tier_benchmark_operator_template_current.csv \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --min-ready-total 40 \
  --min-ready-monomer 25 \
  --min-ready-complex 15 \
  --out-json runs/casp17_win_tier_benchmark_operator_preflight_current.json \
  --out-csv runs/casp17_win_tier_benchmark_operator_preflight_current.csv \
  --out-md runs/casp17_win_tier_benchmark_operator_preflight_current.md
```

This preflight validates placeholder removal, non-current target IDs, local prediction/native PDB existence, no-leak provenance fields, all 10 ablation-layer PDB paths, and selected-vs-oracle calibration fields. The current template is intentionally blocked at `0/40` ready rows because the placeholders have not been replaced with cleared local historical benchmark data.

Build the fail-closed import packet that materializes candidate scorer CSVs only after the operator template preflight passes:

```bash
python3 tools/build_casp17_win_tier_benchmark_operator_import_packet.py \
  --operator-template-csv runs/casp17_win_tier_benchmark_operator_template_current.csv \
  --operator-preflight-json runs/casp17_win_tier_benchmark_operator_preflight_current.json \
  --min-ready-total 40 \
  --out-historical-manifest-csv runs/casp17_historical_benchmark_manifest_candidate_current.csv \
  --out-calibration-csv runs/casp17_model_selection_calibration_candidate_current.csv \
  --out-json runs/casp17_win_tier_benchmark_operator_import_packet_current.json \
  --out-csv runs/casp17_win_tier_benchmark_operator_import_packet_current.csv \
  --out-md runs/casp17_win_tier_benchmark_operator_import_packet_current.md
```

The current import packet is blocked because the operator preflight is blocked. It writes header-only candidate CSVs rather than promoting placeholder historical/native rows into active scoring inputs.

Build the operator dashboard that turns the 40-row benchmark template/preflight into a local work surface:

```bash
python3 tools/build_casp17_win_tier_benchmark_operator_dashboard.py \
  --operator-template-csv runs/casp17_win_tier_benchmark_operator_template_current.csv \
  --operator-preflight-json runs/casp17_win_tier_benchmark_operator_preflight_current.json \
  --operator-preflight-csv runs/casp17_win_tier_benchmark_operator_preflight_current.csv \
  --operator-import-json runs/casp17_win_tier_benchmark_operator_import_packet_current.json \
  --closure-json runs/casp17_win_gap_closure_packet_current.json \
  --out-json runs/casp17_win_tier_benchmark_operator_dashboard_current.json \
  --out-csv runs/casp17_win_tier_benchmark_operator_dashboard_current.csv \
  --out-md runs/casp17_win_tier_benchmark_operator_dashboard_current.md \
  --out-html runs/casp17_win_tier_benchmark_operator_dashboard_current.html
```

The dashboard is local-only. It does not fetch natives or clear provenance, but it makes the exact operator work visible row by row: replace placeholders with cleared historical targets, provide internal prediction/native PDBs, add 10 ablation-layer PDBs, complete selected-vs-oracle calibration fields, and fill strict no-leak provenance.

Build the closure packet that compresses the rubric/action queue/thresholds/benchmark plan/operator preflight into the current proven level and first operator input:

```bash
python3 tools/build_casp17_win_gap_closure_packet.py \
  --win-rubric-json runs/casp17_win_readiness_rubric_packet_current.json \
  --action-queue-json runs/casp17_win_tier_action_queue_packet_current.json \
  --historical-input-workorder-json runs/casp17_historical_input_workorder_packet_current.json \
  --structure-image-quality-json runs/casp17_structure_image_quality_packet_current.json \
  --data-bundle-json casp17/casp17_data_bundle_manifest_current.json \
  --win-tier-threshold-json runs/casp17_win_tier_threshold_packet_current.json \
  --benchmark-closure-plan-json runs/casp17_win_tier_benchmark_closure_plan_current.json \
  --benchmark-operator-preflight-json runs/casp17_win_tier_benchmark_operator_preflight_current.json \
  --benchmark-operator-import-json runs/casp17_win_tier_benchmark_operator_import_packet_current.json \
  --out-json runs/casp17_win_gap_closure_packet_current.json \
  --out-csv runs/casp17_win_gap_closure_packet_current.csv \
  --out-md runs/casp17_win_gap_closure_packet_current.md
```

The closure packet is the shortest current answer to "what level are we at and what closes the next level?": current proven level `review_quality`, next level `competitive_floor`, first blocker `sidechain_native_benchmark_missing_or_blocked`, first numeric threshold gap `sidechain_native_quality/sidechain_native_lddt`, first operator-input action `historical_benchmark_inputs`, benchmark missing win rows `40/40`, operator preflight ready/blocked `0/40`, and operator import candidate historical/calibration rows `0/0`.

Build residue-specific heavy-atom sidechain scaffold files for richer local visualization and QC:

```bash
python3 tools/build_casp17_sidechain_scaffold_packet.py \
  --source-dir runs/casp17_predictions_scored_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_sidechain_scaffold_current \
  --out-json runs/casp17_sidechain_scaffold_packet_current.json \
  --out-csv runs/casp17_sidechain_scaffold_packet_current.csv \
  --out-md runs/casp17_sidechain_scaffold_packet_current.md
```

This scaffold is claim-limited: it improves atom-level inspection, chooses among local frame-rotamer candidates, and catches severe local clashes, but it is not a substitute for statistical rotamer-library packing, all-atom minimization, or native-scored accuracy validation.

Build fail-closed not-worse sidechain repack/polish files:

```bash
python3 tools/build_casp17_sidechain_repack_packet.py \
  --source-dir runs/casp17_predictions_sidechain_scaffold_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_sidechain_repacked_current \
  --out-json runs/casp17_sidechain_repack_packet_current.json \
  --out-csv runs/casp17_sidechain_repack_packet_current.csv \
  --out-md runs/casp17_sidechain_repack_packet_current.md
```

The repack packet now uses sequential coordinate-aware greedy scoring, so each residue candidate is scored against previously selected local sidechain coordinates. It accepts local sidechain coordinate updates only when they do not regress soft close contacts or introduce severe clashes. It is a local heuristic polish layer, not statistical rotamer-library packing or energy minimization.

Build sidechain-only steric-relaxed files with backbone fixed:

```bash
python3 tools/build_casp17_steric_relax_packet.py \
  --source-dir runs/casp17_predictions_sidechain_repacked_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_steric_relaxed_current \
  --iterations 12 \
  --out-json runs/casp17_steric_relax_packet_current.json \
  --out-csv runs/casp17_steric_relax_packet_current.csv \
  --out-md runs/casp17_steric_relax_packet_current.md
```

The steric relax packet moves only non-backbone sidechain atoms and keeps a target-level not-worse guard: if severe clashes or soft close contacts regress, the target is reverted to its source coordinates. It is a local clash relaxation layer, not a full all-atom forcefield minimizer.

Build residue-class rotamer-prior sidechain minimization files:

```bash
python3 tools/build_casp17_rotamer_minimization_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --source-dir runs/casp17_predictions_steric_relaxed_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_rotamer_minimized_current \
  --out-json runs/casp17_rotamer_minimization_packet_current.json \
  --out-csv runs/casp17_rotamer_minimization_packet_current.csv \
  --out-md runs/casp17_rotamer_minimization_packet_current.md
```

The rotamer minimization packet moves only sidechain atoms and uses a target-level no-regression guard. It improves residue-class rotamer-prior deviation plus hbond-like and salt-bridge-like contact proxies while keeping severe clashes at zero and soft close contacts not worse. It is an internal residue-class heuristic, not Dunbrack/Richardson rotamer validation, official MolProbity, or native accuracy evidence.

Build sidechain-only polar refinement files:

```bash
python3 tools/build_casp17_polar_refinement_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --source-dir runs/casp17_predictions_rotamer_minimized_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_polar_refined_current \
  --out-json runs/casp17_polar_refinement_packet_current.json \
  --out-csv runs/casp17_polar_refinement_packet_current.csv \
  --out-md runs/casp17_polar_refinement_packet_current.md
```

The polar refinement packet moves only sidechain atoms and keeps a not-worse guard over severe clashes, soft clashes, and polar contacts. It improves hbond-like and salt-bridge-like proxies without moving the generated backbone. It is an internal sidechain heuristic, not a forcefield minimizer, not official MolProbity, and not native accuracy evidence.

Build short sidechain-only forcefield-style minimization files:

```bash
python3 tools/build_casp17_forcefield_minimization_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --source-dir runs/casp17_predictions_polar_refined_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_forcefield_minimized_current \
  --out-json runs/casp17_forcefield_minimization_packet_current.json \
  --out-csv runs/casp17_forcefield_minimization_packet_current.csv \
  --out-md runs/casp17_forcefield_minimization_packet_current.md
```

The forcefield minimization packet moves only sidechain atoms, uses short conservative updates, and keeps a not-worse guard over soft/severe clashes and internal forcefield energy. It is a local internal refinement heuristic, not full all-atom forcefield minimization, not official MolProbity, and not native accuracy evidence.

Build internal residue-frequency statistical rotamer packing proxy files:

```bash
python3 tools/build_casp17_statistical_rotamer_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --source-dir runs/casp17_predictions_forcefield_minimized_current \
  --sequence-dir runs/casp17_sequences_current \
  --out-dir runs/casp17_predictions_statistical_rotamer_current \
  --out-json runs/casp17_statistical_rotamer_packet_current.json \
  --out-csv runs/casp17_statistical_rotamer_packet_current.csv \
  --out-md runs/casp17_statistical_rotamer_packet_current.md
```

The statistical rotamer packet keeps backbone atoms fixed, moves only sidechain atoms, uses an internal residue-specific frequency-prior table stored in the repo, and keeps a not-worse guard over severe/soft clashes, internal forcefield energy, and mean prior penalty. It does not use external rotamer libraries, public/template/native structures, official MolProbity, or current-target native information.

Build internal MolProbity-style steric/completion QC for the statistical-rotamer files:

```bash
python3 tools/build_casp17_all_atom_quality_packet.py \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --sidechain-scaffold-json runs/casp17_sidechain_scaffold_packet_current.json \
  --out-json runs/casp17_all_atom_quality_packet_current.json \
  --out-csv runs/casp17_all_atom_quality_packet_current.csv \
  --out-md runs/casp17_all_atom_quality_packet_current.md
```

This QC packet checks local heavy-atom completion, severe inter-residue clashes, and a soft clashscore proxy. It is not an official MolProbity run and does not prove native sidechain accuracy.

Build sidechain completeness and rotamer-frame proxy QC:

```bash
python3 tools/casp17/build_casp17_sidechain_quality_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --out-json runs/casp17_sidechain_quality_packet_current.json \
  --out-csv runs/casp17_sidechain_quality_packet_current.csv \
  --out-md runs/casp17_sidechain_quality_packet_current.md
```

This sidechain-quality packet checks completeness, CB radial outliers, and a local rotamer-frame proxy. It is not external statistical rotamer-library validation or native sidechain accuracy evidence.

Gate the statistical-rotamer TS files through the standard import/validation/scorecard/submission sequence:

```bash
python3 tools/build_casp17_prediction_import_packet.py \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --out-json runs/casp17_prediction_import_packet_statistical_rotamer_current.json \
  --out-csv runs/casp17_prediction_import_packet_statistical_rotamer_current.csv \
  --out-md runs/casp17_prediction_import_packet_statistical_rotamer_current.md \
  --out-intake-csv runs/casp17_target_intake_prediction_imported_statistical_rotamer_current.csv

python3 tools/build_casp17_prediction_validation_batch.py \
  --intake-csv runs/casp17_target_intake_prediction_imported_statistical_rotamer_current.csv \
  --out-dir runs/casp17_prediction_validation_statistical_rotamer_current \
  --out-json runs/casp17_prediction_validation_batch_statistical_rotamer_current.json \
  --out-csv runs/casp17_prediction_validation_batch_statistical_rotamer_current.csv \
  --out-md runs/casp17_prediction_validation_batch_statistical_rotamer_current.md \
  --out-intake-csv runs/casp17_target_intake_validated_statistical_rotamer_current.csv

python3 tools/build_casp17_internal_scorecard_batch.py \
  --intake-csv runs/casp17_target_intake_validated_statistical_rotamer_current.csv \
  --out-dir runs/casp17_internal_scorecards_statistical_rotamer_current \
  --out-json runs/casp17_internal_scorecard_batch_statistical_rotamer_current.json \
  --out-csv runs/casp17_internal_scorecard_batch_statistical_rotamer_current.csv \
  --out-md runs/casp17_internal_scorecard_batch_statistical_rotamer_current.md \
  --out-intake-csv runs/casp17_target_intake_scored_statistical_rotamer_current.csv

python3 tools/build_casp17_submission_gate_packet.py \
  --intake-csv runs/casp17_target_intake_scored_statistical_rotamer_current.csv \
  --out-json runs/casp17_submission_gate_packet_statistical_rotamer_current.json \
  --out-csv runs/casp17_submission_gate_packet_statistical_rotamer_current.csv \
  --out-md runs/casp17_submission_gate_packet_statistical_rotamer_current.md
```

Build the local interactive molecular viewer packet for Mol*/3Dmol-style visual inspection:

```bash
python3 tools/build_casp17_molecular_viewer_packet.py \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --render-dir runs/casp17_structure_renders_current \
  --out-html runs/casp17_molecular_viewer_current.html \
  --out-json runs/casp17_molecular_viewer_packet_current.json \
  --out-csv runs/casp17_molecular_viewer_packet_current.csv \
  --out-md runs/casp17_molecular_viewer_packet_current.md
```

The generated HTML embeds sanitized PDB text so it can be opened directly as a local file. The embedded `AUTHOR` records are redacted in the viewer copy; original TS files remain unchanged. The Mol* button is disabled by default for the internal-only lane. If local 3Dmol/WebGL is unavailable or not configured, the viewer uses its own dependency-free internal canvas runtime for rotate/zoom molecular inspection, with the matching local PyMOL/static preview PNG retained as the final fallback.

The generated HTML is internal-canvas-first and internal-only by default. It does not emit a hosted 3Dmol URL; WebGL is enabled only when a local runtime bundle is supplied with `--viewer-js-path`, and the hosted Mol* handoff is disabled unless `--enable-external-molstar-link` is explicitly supplied. With the default command above, the local canvas runtime renders chain/residue/confidence/spectrum views plus issue overlays without external JavaScript; static previews are retained as a fail-closed visual fallback. The side panel exposes target metadata, chain summaries, residue-class counts, fixed B-factor confidence bins, interface CA contact summaries, and internal QC overlay totals from:

```text
runs/casp17_structure_render_packet_current.json
runs/casp17_structure_render_review_queue_current.json
runs/casp17_all_atom_quality_packet_current.json
runs/casp17_sidechain_quality_packet_current.json
```

The current viewer packet summary is `16/16 ready`, external network default `disabled`, default runtime `internal_canvas_runtime`, raw/rendered QC hotspots `2674/576`, raw low-confidence hotspots `2653`, raw soft hotspots `30`, all-atom soft clashes `15`, and marker-truncated targets `16/16`.

The viewer computes lightweight CA inspection overlays and displays internal QC packet evidence. Treat this as local geometry/visual-triage evidence only, not as official CASP accuracy evidence.

Build the no-leak historical benchmark manifest scaffold/checklist. This command is local-only and fail-closed; it does not fetch native structures or use current CASP targets. It shows which local historical prediction/native files and provenance-clearance decisions are still missing:

```bash
python3 tools/build_casp17_historical_benchmark_manifest_scaffold.py \
  --prediction-dir runs/casp17_historical_benchmark_predictions_current \
  --native-dir runs/casp17_historical_benchmark_natives_current \
  --existing-manifest-csv runs/casp17_historical_benchmark_manifest_current.csv \
  --out-json runs/casp17_historical_benchmark_manifest_scaffold_current.json \
  --out-csv runs/casp17_historical_benchmark_manifest_scaffold_current.csv \
  --out-md runs/casp17_historical_benchmark_manifest_scaffold_current.md
```

Current scaffold status is `blocked`: no ready local historical rows exist yet. The scaffold emits one required monomer row and one required complex row as placeholders; both require local prediction/native PDB files, `leakage_clearance=no_leak`, and strict no-leak provenance before they can be copied into the scoring manifest.

The scaffold and ready manifest include optional refinement-ablation layer columns:

```text
recursive_prediction_pdb,scored_prediction_pdb,sidechain_scaffold_prediction_pdb,sidechain_repacked_prediction_pdb,sidechain_completed_prediction_pdb,steric_relaxed_prediction_pdb,rotamer_minimized_prediction_pdb,polar_refined_prediction_pdb,forcefield_minimized_prediction_pdb,statistical_rotamer_prediction_pdb
```

These columns are not required for basic historical scoring, but they let a ready no-leak row carry exact per-layer prediction PDB paths into the refinement-ablation packet.

Promote only ready no-leak historical rows into a scoring-manifest candidate. This promotion gate also rejects placeholder rows and current CASP17 target IDs, so current-target data cannot accidentally become historical benchmark calibration evidence:

```bash
python3 tools/build_casp17_historical_benchmark_manifest_promotion.py \
  --scaffold-csv runs/casp17_historical_benchmark_manifest_scaffold_current.csv \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --out-manifest-csv runs/casp17_historical_benchmark_manifest_ready_current.csv \
  --out-json runs/casp17_historical_benchmark_manifest_promotion_current.json \
  --out-csv runs/casp17_historical_benchmark_manifest_promotion_current.csv \
  --out-md runs/casp17_historical_benchmark_manifest_promotion_current.md
```

Current promotion status is `blocked`: 0 rows promoted, 2 rows blocked. The ready manifest is header-only. Do not copy it to `runs/casp17_historical_benchmark_manifest_current.csv` until the promotion packet is `ready`.

Build the historical input preflight packet. This local-only packet chooses the best available source in order: active manifest, ready manifest, scaffold, then scanned local directories. It reports whether core historical benchmark inputs and the optional 10-layer refinement-ablation inputs are ready to promote, activate, or score:

```bash
python3 tools/build_casp17_historical_input_preflight_packet.py \
  --scaffold-csv runs/casp17_historical_benchmark_manifest_scaffold_current.csv \
  --ready-manifest-csv runs/casp17_historical_benchmark_manifest_ready_current.csv \
  --active-manifest-csv runs/casp17_historical_benchmark_manifest_current.csv \
  --target-watchlist-json runs/casp17_target_watchlist_current.json \
  --out-json runs/casp17_historical_input_preflight_packet_current.json \
  --out-csv runs/casp17_historical_input_preflight_packet_current.csv \
  --out-md runs/casp17_historical_input_preflight_packet_current.md
```

Current input preflight status is `blocked`: source mode `scaffold`, historical-ready rows `0`, ablation-ready rows `0`, missing prediction/native/layer files `2/2/20`, and first blocker `hist_REQUIRED_MONOMER`.

Build the historical input workorder packet. This local-only packet turns the blocked preflight rows into operator workorders and a manifest template CSV. It does not clear provenance or activate a manifest:

```bash
python3 tools/build_casp17_historical_input_workorder_packet.py \
  --preflight-json runs/casp17_historical_input_preflight_packet_current.json \
  --out-json runs/casp17_historical_input_workorder_packet_current.json \
  --out-csv runs/casp17_historical_input_workorder_packet_current.csv \
  --out-md runs/casp17_historical_input_workorder_packet_current.md \
  --out-template-csv runs/casp17_historical_benchmark_manifest_operator_template_current.csv
```

Current workorder status is `ready`: 2 core-input workorders, 0 ablation-only workorders, 0 complete rows, missing core files `4`, missing ablation layer files `20`, and the operator template CSV is ready to edit only after no-leak review.

Build the no-leak historical benchmark packet. Populate the manifest only with local historical prediction/native pairs that are cleared as no-leak:

```bash
python3 tools/build_casp17_historical_benchmark_packet.py \
  --manifest-csv runs/casp17_historical_benchmark_manifest_current.csv \
  --out-json runs/casp17_historical_benchmark_packet_current.json \
  --out-csv runs/casp17_historical_benchmark_packet_current.csv \
  --out-md runs/casp17_historical_benchmark_packet_current.md
```

Required manifest columns:

```text
benchmark_id,target_id,scope,split,prediction_pdb,native_pdb,leakage_clearance
```

Required no-leak provenance columns:

```text
prediction_method,prediction_created_at,native_release_date,prediction_generated_before_native_release,public_template_or_native_used_for_prediction,other_team_model_used,post_release_information_used,current_casp17_target,operator_clearance
```

Use `scope=monomer` or `scope=complex`. Use `leakage_clearance=no_leak` only when the benchmark pair is cleared as non-current-target, non-template, non-public-leakage evidence. The prediction date must be before the native release date, and the leak flags must be false.

The benchmark scorer is intentionally stricter than a coordinate-only RMSD check. A passing row must have:

- prediction/native chain IDs matching exactly
- monomer rows with single-chain prediction/native structures
- complex rows with multichain prediction/native structures
- overlapping chain/residue CA keys rather than order-only fallback
- exact residue identity match fraction of 1.0 by default
- full prediction/native CA coverage by default
- enough matched CA atoms to meet `--min-ca-count`

Only after those exactness checks pass are TM/GDT/lDDT/interface-contact F1, IPS/Jaccard, QSbest-like, and DockQ-like proxy metrics allowed to count toward win-tier evidence.

Build the no-leak historical refinement-ablation packet. This is the evidence lane that asks whether each internal refinement layer improves native proxy metrics on cleared historical targets, without touching current CASP17 target native data:

```bash
python3 tools/casp17/build_casp17_refinement_ablation_packet.py \
  --manifest-csv runs/casp17_historical_benchmark_manifest_current.csv \
  --out-json runs/casp17_refinement_ablation_packet_current.json \
  --out-csv runs/casp17_refinement_ablation_packet_current.csv \
  --out-md runs/casp17_refinement_ablation_packet_current.md
```

Default layer directories are:

```text
runs/casp17_historical_ablation_predictions_current/recursive
runs/casp17_historical_ablation_predictions_current/scored
runs/casp17_historical_ablation_predictions_current/sidechain_scaffold
runs/casp17_historical_ablation_predictions_current/sidechain_repacked
runs/casp17_historical_ablation_predictions_current/sidechain_completed
runs/casp17_historical_ablation_predictions_current/steric_relaxed
runs/casp17_historical_ablation_predictions_current/rotamer_minimized
runs/casp17_historical_ablation_predictions_current/polar_refined
runs/casp17_historical_ablation_predictions_current/forcefield_minimized
runs/casp17_historical_ablation_predictions_current/statistical_rotamer
```

Each directory should contain local no-leak historical predictions named `<TARGET_ID>TS.pdb` or `<TARGET_ID>.pdb`, matching the `target_id` in the promoted historical manifest. Rows can also provide layer-specific manifest columns such as `recursive_prediction_pdb` or `prediction_pdb_recursive`. The packet compares `--baseline-layer recursive` to `--final-layer statistical_rotamer` by default, records raw layer metrics, then records final-vs-baseline TM/GDT/lDDT/RMSD/interface deltas. Current status is `blocked` with `manifest_blockers=manifest_missing`.

Build the model-selection calibration scaffold/checklist. This is local-only and fail-closed; it does not fetch natives, compute oracle metrics, clear leakage, or use current CASP17 target native data:

```bash
python3 tools/build_casp17_model_selection_calibration_scaffold.py \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --existing-calibration-csv runs/casp17_model_selection_calibration_current.csv \
  --out-json runs/casp17_model_selection_calibration_scaffold_current.json \
  --out-csv runs/casp17_model_selection_calibration_scaffold_current.csv \
  --out-md runs/casp17_model_selection_calibration_scaffold_current.md
```

Current scaffold status is `blocked`: no ready local calibration rows exist yet. The scaffold emits one required monomer row and one required complex row as placeholders; only rows with `calibration_ready_status=ready` should be copied into `runs/casp17_model_selection_calibration_current.csv`.

Build the model-selection calibration packet. This is fail-closed until no-leak historical top-5 calibration rows exist:

```bash
python3 tools/build_casp17_model_selection_calibration_packet.py \
  --score-record-json runs/casp17_internal_score_record_packet_current.json \
  --ranked-depth-json runs/casp17_ranked_model_depth_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --calibration-csv runs/casp17_model_selection_calibration_current.csv \
  --out-json runs/casp17_model_selection_calibration_packet_current.json \
  --out-csv runs/casp17_model_selection_calibration_packet_current.csv \
  --out-md runs/casp17_model_selection_calibration_packet_current.md
```

Required calibration CSV columns:

```text
benchmark_id,scope,selected_model_rank,best_model_rank,selected_native_metric,best_native_metric,selected_score,best_score,leakage_clearance
```

The calibration packet keeps current-target SCORE/QSCORE coverage separate from native calibration. It only turns green when historical benchmark exactness passes and the no-leak calibration CSV proves selected-vs-oracle model loss is below the configured threshold.

Build the competitive readiness packet:

```bash
python3 tools/build_casp17_competitive_readiness_packet.py \
  --prediction-dir runs/casp17_predictions_statistical_rotamer_current \
  --submission-gate-json runs/casp17_submission_gate_packet_statistical_rotamer_current.json \
  --sidechain-scaffold-json runs/casp17_sidechain_scaffold_packet_current.json \
  --sidechain-repack-json runs/casp17_sidechain_repack_packet_current.json \
  --steric-relax-json runs/casp17_steric_relax_packet_current.json \
  --rotamer-minimization-json runs/casp17_rotamer_minimization_packet_current.json \
  --polar-refinement-json runs/casp17_polar_refinement_packet_current.json \
  --forcefield-minimization-json runs/casp17_forcefield_minimization_packet_current.json \
  --statistical-rotamer-json runs/casp17_statistical_rotamer_packet_current.json \
  --all-atom-quality-json runs/casp17_all_atom_quality_packet_current.json \
  --sidechain-quality-json runs/casp17_sidechain_quality_packet_current.json \
  --historical-benchmark-json runs/casp17_historical_benchmark_packet_current.json \
  --refinement-ablation-json runs/casp17_refinement_ablation_packet_current.json \
  --model-selection-calibration-json runs/casp17_model_selection_calibration_packet_current.json
```

This packet intentionally keeps `submission_readiness_status` separate from `win_tier_readiness_status`.

Build conservative internal SCORE/QSCORE scored-copy TS files:

```bash
python3 tools/add_casp17_internal_score_records.py \
  --source-dir runs/casp17_predictions_recursive_current \
  --out-dir runs/casp17_predictions_scored_current
```

Then gate the scored-copy files before considering them for submission:

```bash
python3 tools/build_casp17_prediction_import_packet.py \
  --intake-csv runs/casp17_target_intake_seed_with_sequences_current.csv \
  --prediction-dir runs/casp17_predictions_scored_current \
  --out-json runs/casp17_prediction_import_packet_scored_current.json \
  --out-csv runs/casp17_prediction_import_packet_scored_current.csv \
  --out-md runs/casp17_prediction_import_packet_scored_current.md \
  --out-intake-csv runs/casp17_target_intake_prediction_imported_scored_current.csv

python3 tools/build_casp17_prediction_validation_batch.py \
  --intake-csv runs/casp17_target_intake_prediction_imported_scored_current.csv \
  --out-dir runs/casp17_validations_scored_current \
  --out-json runs/casp17_prediction_validation_batch_scored_current.json \
  --out-csv runs/casp17_prediction_validation_batch_scored_current.csv \
  --out-md runs/casp17_prediction_validation_batch_scored_current.md \
  --out-intake-csv runs/casp17_target_intake_validated_scored_current.csv

python3 tools/build_casp17_internal_scorecard_batch.py \
  --intake-csv runs/casp17_target_intake_validated_scored_current.csv \
  --out-dir runs/casp17_internal_scorecards_scored_current \
  --out-json runs/casp17_internal_scorecard_batch_scored_current.json \
  --out-csv runs/casp17_internal_scorecard_batch_scored_current.csv \
  --out-md runs/casp17_internal_scorecard_batch_scored_current.md \
  --out-intake-csv runs/casp17_target_intake_scored_scored_current.csv

python3 tools/build_casp17_submission_gate_packet.py \
  --intake-csv runs/casp17_target_intake_scored_scored_current.csv \
  --out-json runs/casp17_submission_gate_packet_scored_current.json \
  --out-csv runs/casp17_submission_gate_packet_scored_current.csv \
  --out-md runs/casp17_submission_gate_packet_scored_current.md
```

Build ranked MODEL 1-5 depth for all current protein targets:

```bash
python3 tools/run_casp17_ranked_model_depth_batch.py \
  --sequence-dir runs/casp17_sequences_current \
  --job-root runs/casp17_prediction_jobs_top5_current \
  --ranked-ts-dir runs/casp17_predictions_top5_current \
  --author-code <CASP_AUTHOR_CODE> \
  --model-count 5 \
  --quality-preset fast \
  --ensemble-size 8 \
  --device auto \
  --execute \
  --skip-existing
```

The current top-5 artifact covers all 16 current targets: `ranked-depth pass=16/16`, with `80/80` candidate format/geometry/confidence gates passing. The scored-copy artifact covers SCORE on `16/16` TS files and QSCORE on `13/13` multichain TS files, but those values are conservative internal estimates, not native-calibrated CASP accuracy evidence.

## Single-Target Internal Predictor

For local debug or targeted re-run:

```bash
python3 tools/run_casp17_internal_physics_baseline_predictor.py \
  --target-id T1331 \
  --fasta runs/casp17_sequences_current/T1331.fasta \
  --out-dir runs/casp17_prediction_jobs_recursive_current/T1331 \
  --raw-pdb runs/casp17_prediction_jobs_recursive_current/T1331/T1331_model_1.pdb \
  --runtime-json runs/casp17_prediction_jobs_recursive_current/T1331/backend_runtime.json \
  --metrics-json runs/casp17_prediction_jobs_recursive_current/T1331/internal_physics_metrics.json \
  --device auto \
  --quality-preset casp17_quality \
  --emit-backbone-atoms
```

CPU execution is test/smoke-only. Production-quality CASP17 generation should keep GPU evidence required.

## Existing-Structure Attach Lane

The existing-structure lane remains available only for internally generated target-specific structures with cleared provenance. It is not the active 100% internal physics submission lane.

```bash
python3 tools/build_casp17_existing_structure_file_checklist.py \
  --write-provenance-scaffold

python3 tools/build_casp17_existing_structure_intake_builder.py \
  --structure-dir runs/casp17_existing_structures_current \
  --provenance-csv runs/casp17_existing_structure_provenance_current.csv \
  --author-code <CASP_AUTHOR_CODE>
```

Required provenance clearance:

- internal target-specific generation
- `public_or_external_source_used=false`
- `other_team_structure_used=false`
- `post_release_structure_used=false`

## Legacy External Adapter

`tools/run_casp17_external_structure_predictor_adapter.py` is retained as a fail-closed integration shim, but it is not part of the current internal-only CASP17 lane. Do not use it for the current submission set unless the work is explicitly re-scoped away from the 100% internal-physics policy.

## Verification

Current expected checks:

```bash
python3 -m pytest tests/unit/test_run_casp17_internal_physics_baseline_predictor.py \
  tests/unit/test_add_casp17_internal_score_records.py \
  tests/unit/test_build_casp17_all_atom_quality_packet.py \
  tests/unit/test_build_casp17_historical_benchmark_manifest_scaffold.py \
  tests/unit/test_build_casp17_historical_benchmark_manifest_promotion.py \
  tests/unit/test_build_casp17_historical_benchmark_packet.py \
  tests/unit/test_build_casp17_refinement_ablation_packet.py \
  tests/unit/test_build_casp17_model_selection_calibration_scaffold.py \
  tests/unit/test_build_casp17_model_selection_calibration_packet.py \
  tests/unit/test_build_casp17_ranked_model_depth_packet.py \
  tests/unit/test_run_casp17_ranked_model_depth_batch.py \
  tests/unit/test_build_casp17_polar_refinement_packet.py \
  tests/unit/test_build_casp17_forcefield_minimization_packet.py \
  tests/unit/test_build_casp17_molecular_viewer_packet.py \
  tests/unit/test_build_casp17_win_tier_action_queue_packet.py \
  tests/unit/test_build_casp17_competitive_readiness_packet.py \
  tests/unit/test_build_casp17_win_readiness_rubric_packet.py \
  tests/unit/test_build_casp17_prediction_launch_packet.py \
  tests/unit/test_build_casp17_internal_physics_accuracy_readiness_packet.py \
  tests/unit/test_convert_casp17_ts_prediction_from_pdb.py -q

python3 -m pytest tests/unit/test_*casp17*.py -q
```

Current known-good result:

- py_compile for the touched CASP17 predictor/readiness tools: pass.
- focused predictor/sidechain-native/competitive/win-readiness/action-queue suite: `18 passed in 11.26s`.
- focused strict historical benchmark provenance/coverage/readiness suite: `29 passed in 2.31s`.
- focused molecular viewer/render/review queue tests: `5 passed in 7.92s`.
- focused CASP17 data bundle tests: `2 passed in 0.19s`.
- focused historical input workorder/action queue tests: `3 passed in 0.29s`.
- focused benchmark-operator dashboard/preflight/import/win-gap/data-bundle tests: `8 passed in 0.75s`.
- focused data-bundle/evidence fill-kit tests: `3 passed in 0.32s`.
- focused render/image-quality/viewer/win-readiness/data-bundle tests: `10 passed in 13.76s`.
- focused readiness-dashboard/data-bundle tests: `3 passed in 0.30s`.
- focused metric fill-kit/operator-dashboard/win-gap/readiness/data-bundle/image-quality tests: `8 passed in 0.92s`.
- focused input-scaffold/readiness-dashboard/data-bundle/win-gap tests: `5 passed in 0.57s`.
- focused input-inventory/readiness-dashboard/data-bundle/input-scaffold tests: `5 passed in 0.55s`.
- full CASP17 targeted unit suite: `160 passed in 54.31s`.
- `git diff --check`: clean.
- latest model-selected coordinate-frame normalization: `runs/casp17_pdb_coordinate_frame_packet_model_selected_current.json` pass, `16/16`, fixed-width PDB coordinate parse errors `356 -> 0`, shifted targets `1` (`T1342`, rigid x-shift `76.487 A`), normalized directory `runs/casp17_predictions_model_selected_coordinate_normalized_current`.
- latest model-selected normalized all-atom/sidechain QC: both pass, `16/16`, heavy-atom completion `1.0`, severe clashes `0`, soft clashes `4`, sidechain completion `1.0`, rotamer proxy pass `1.0`.
- latest model-selected normalized import/validation/scorecard/submission gate: `16/16` import, format, geometry, confidence, scorecard, and `submission_go`.
- latest model-selected normalized molecular viewer: `runs/casp17_molecular_viewer_model_selected_normalized_current.html`, smoke `pass`, `16/16`, internal canvas symbols `8/8`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`.
- latest model-selected normalized render packet: `runs/casp17_structure_render_packet_model_selected_normalized_current.json`, render coverage `16/16`, PyMOL base/QC/surface/confidence `16/16`, residue-class/interface/stereo-depth/turntable/molecular-plate/presentation-plate `16/16`, blocked `0`, raw/rendered QC hotspots `2654/576`, soft hotspots `4`.
- latest model-selected normalized publication figures: `runs/casp17_publication_figure_packet_model_selected_normalized_current.json`, `16/16 pass`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`, min observed colorful pixels `8205952`, min observed unique colors `445`, luminance range `254.422`.
- latest model-selected normalized image-quality smoke: `runs/casp17_structure_image_quality_packet_model_selected_normalized_current.json`, `pass`, images `256/256`, stereo-depth `16/16`, turntable `16/16`, publication/review images `64/64`, minimum estimated edge pixels `2025`, minimum luminance range `29.141`.
- latest readiness dashboard: `ready`, current proven level `review_quality`, levels pass-or-ready/blocked-or-partial `2/4`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, coordinate frame `pass 16/16`, model-selection comparison `pass`, promotion `blocked_pending_no_leak_historical_calibration`, viewer smoke `pass 16/16`, normalized image QC `256/256`, data bundle artifacts `678`.
- latest local `casp17/` data mirror: `ready`, top-level artifacts `678`, mirrored `runs/casp17*` artifacts `676`, files `5083`, bytes `961069806`, missing bundled artifacts `0`.
- latest focused coordinate-frame/readiness/viewer/bundle suite: `7 passed in 0.81s`.
- latest focused normalized render/publication/image/readiness/bundle suite: `10 passed in 17.81s`.
- latest full CASP17 targeted unit suite: `171 passed in 61.03s`.
- focused predictor finalizer regression: `9 passed in 10.49s`.
- final recursive raw gate: `16/16 pass`, GPU evidence required.
- final accuracy-readiness proxy: `16/16 pass`.
- final recursive TS gate: `16/16` converted, `16/16 submission_go`.
- final ranked top-5 depth: `16/16 pass`, `80/80` candidate gates.
- final statistical-rotamer TS gate: `16/16` import, format, geometry, confidence, scorecard, and submission gate pass.
- final all-atom quality packet: `16/16 pass`, severe clashes `0`, total soft close contacts `15`, max soft clashscore `0.427` per 1000 atoms.
- final sidechain quality packet: `16/16 pass`, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`.
- final molecular viewer packet: `16/16 ready`, embedded PDB author records redacted, external network default `disabled`, default runtime `internal_canvas_runtime`, static fallback previews prefer presentation plates, raw/rendered QC hotspots `2674/576`, raw low-confidence hotspots `2653`, raw soft hotspots `30`.
- final molecular viewer smoke packet: `16/16 pass`, internal canvas symbols `8/8`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`.
- final PyMOL/render packet: `16/16` base/QC/surface/confidence/residue-class/predicted-CA-interface/stereo-depth/review/atlas/molecular-plate/presentation-plate renders, blocked `0`; predicted CA interface contacts within 12 A `8486`; raw/rendered QC hotspots `2674/576`; stereo-depth contact sheet `runs/casp17_structure_render_stereo_depth_contact_sheet_current.png`; presentation contact sheet `runs/casp17_structure_render_presentation_contact_sheet_current.png`.
- final publication figure packet: `16/16 pass`, 3840x2160 figures, 16/16 molecular inspection posters, 16/16 molecular scene posters, 16/16 molecular review boards, contact sheets `runs/casp17_publication_figure_contact_sheet_current.png`, `runs/casp17_molecular_inspection_poster_contact_sheet_current.png`, `runs/casp17_molecular_scene_poster_contact_sheet_current.png`, and `runs/casp17_molecular_review_board_contact_sheet_current.png`, local gallery `runs/casp17_molecular_inspection_gallery_current.html`, min observed publication colorful pixels `8,215,296`, sampled unique colors `572`, luminance range `253.057`, min observed inspection colorful pixels `7,842,368`, sampled unique colors `955`, luminance range `255.0`, min observed scene colorful pixels `7,789,824`, sampled unique colors `1614`, luminance range `255.0`, min observed review-board colorful pixels `7,706,624`, sampled unique colors `1296`, luminance range `255.0`.
- final review queue: `16/16 ready`, interface maps `16/16`, interface chain-pair rows `58`, predicted CA contacts within 12 A `8486`, top interface target `H1335`.
- final threshold packet: `blocked_input`, current proven level `review_quality`, threshold rows pass/partial/blocked `5/1/7`, first threshold gap `sidechain_native_quality/sidechain_native_lddt`, first threshold blocker `sidechain_native_benchmark_missing_or_blocked`; complex win-tier rows now include both interface F1 and DockQ-like proxy thresholds.
- final benchmark closure plan: `ready` planning artifact, evidence `blocked_input`, competitive rows required `10/5/15`, win rows required `25/15/40`, current rows `0/0/0`, missing win rows `25/15/40`, required prediction/native/ablation/calibration `40/40/400/40`.
- final benchmark operator preflight: `blocked`, ready/blocked `0/40`, missing prediction/native/layer files `40/40/400`, calibration-blocked rows `40`.
- final benchmark operator import: `blocked`, candidate historical/calibration rows `0/0`, blockers `operator_preflight_not_pass,ready_count_below_import_threshold`; candidate CSVs are header-only.
- final benchmark operator dashboard: `ready` local work surface, rows ready/blocked `0/40`, monomer/complex `25/15`, needs target/core/ablation/calibration/provenance `40/40/40/40/40`, metric profiles monomer `TM,GDT_TS,CA_lDDT` and complex `TM,interface_F1,DockQ,QSbest,IPS`, HTML `runs/casp17_win_tier_benchmark_operator_dashboard_current.html`.
- final benchmark evidence fill kit: `ready`, 40 rows, 1,310 required evidence items, filled/missing `0/1310`, missing classes target identity/core/ablation/provenance/calibration/native-metric-gates `40/80/400/400/240/150`, HTML `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.html`.
- final benchmark input scaffold: `ready`, 40 row folders, 160 row-level scaffold files, monomer/complex `25/15`, required prediction/native/ablation files `40/40/400`, total required files `480`, draft manifest `runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv`, draft calibration `runs/casp17_model_selection_calibration_draft_from_operator_current.csv`.
- final benchmark input inventory: `blocked`, ready/blocked rows `0/40`, present/missing required files `0/480`, prediction/native present `0/0`, ablation present/required `0/400`, provenance-ready rows `0`, calibration-ready rows `0`.
- final readiness dashboard: `ready`, current proven level `review_quality`, next unclosed `competitive_floor`, levels pass-or-ready/blocked-or-partial `2/3`, visual QC `240/240`, publication/review images `64/64`, review boards `16/16`, benchmark rows ready/total `0/40`, missing evidence `1310/1310`, input scaffold `ready` with `480` required file slots, input inventory present/missing files `0/480`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`, HTML `runs/casp17_readiness_dashboard_current.html`.
- final contact-sheet pixel smoke: base, QC, surface, confidence, residue-class, predicted CA interface-map, stereo-depth, review, atlas, molecular-plate, and presentation-plate contact sheets were nonblank/colorful; stereo-depth contact sheet is `1680x1320` with nonflat RGB extrema and sampled T1331 stereo-depth render is `3000x1500` with nonflat RGB extrema; priority review sheet `1,744,263`.
- final historical input workorder: `ready`, 2 workorders, core/ablation/complete `2/0/0`, missing core files `4`, missing ablation layer files `20`, operator template `runs/casp17_historical_benchmark_manifest_operator_template_current.csv`.
- final local `casp17/` data mirror: `ready`, 496 top-level artifacts, 494 mirrored `runs/casp17*` artifacts, 3,566 files, original `runs/`, `docs/`, and `config/` paths preserved; exact byte count is tracked in `casp17/casp17_data_bundle_manifest_current.json`.
- final structure image-quality packet: `pass`, 240/240 images, 16/16 targets complete, 16/16 stereo-depth renders, 16/16 molecular plates, 16/16 presentation plates, 64/64 publication/review images, minimum estimated colorful pixels `2149950`, minimum estimated edge pixels `50050`, minimum luminance range `90.525`.
- final competitive readiness: `submission_readiness_status=pass`, `competitive_gap_count=5`, win-tier remains fail-closed.
- final win-readiness rubric: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`, requirement count `9`; first gap `all_atom_steric_quality`.
- final win-gap closure packet: closure `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first open dimension `all_atom_steric_quality`, first operator-input action `historical_benchmark_inputs`, benchmark missing win rows `40/40`, operator preflight ready/blocked `0/40`, operator import candidate rows `0/0`.

## External Submission Confirmation

Before uploading to CASP, prepare and confirm:

```text
Target: CASP17 Prediction Center portal
Action: upload/submit the selected gated TS set, currently runs/casp17_predictions_statistical_rotamer_current/*TS.pdb
Impact: official CASP17 prediction submission under the registered group
Risk: external irreversible or hard-to-reverse submission record
Rollback: only whatever replace/withdraw behavior CASP portal supports
Verification: CASP receipt/status and target list match the 16 current statistical-rotamer TS files
```
