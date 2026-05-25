# Betelgeuze Harness State

- updated_at: 2026-05-25T20:36:05+09:00
- mode: Deep
- risk: R3 local / R4 external CASP submission boundary
- goal: Keep CASP17 participation readiness current for the official open protein target surface using only the repo's internal torch/coarse-grain physics lane.
- constraints:
  - Do not revert unrelated dirty worktree changes.
  - Do not stage, commit, push, delete, submit to CASP, or mutate external state without explicit confirmation.
  - Do not use AlphaFold, ColabFold, ESMFold, OmegaFold, public/template structures, public PDB target lookups, or other-team models for the active CASP17 lane.
  - CASP author code is runtime-only input; do not store it in committed docs, configs, or state.

## Current Evidence

- Official CASP17 watchlist refreshed on 2026-05-24: 16 current open selected protein targets.
- Newly included since the previous 14-target lane: `H1348`, `H1349`.
- `runs/casp17_sequence_packet_current.json`: `16/16` FASTA files materialized.
- `tools/run_casp17_internal_physics_baseline_predictor.py` now applies a stronger post-docking interchain CA floor finalizer with chain-center expansion fallback.
- H1348/H1349 recursive raw jobs were regenerated on the local ROCm GPU after the docking finalizer patch:
  - H1348 assembly: interchain CA clashes `0`, min interchain CA distance `3.472 A`, predicted CA contacts within 12 A `39`, internal interchain CA-separation/contact sanity `pass`.
  - H1349 assembly: interchain CA clashes `0`, min interchain CA distance `3.292 A`, predicted CA contacts within 12 A `130`, internal interchain CA-separation/contact sanity `pass`.
- `runs/casp17_internal_physics_raw_gate_packet_recursive_current.json`: raw gate `pass`, `16/16`, GPU evidence required.
- `runs/casp17_internal_physics_accuracy_readiness_packet_recursive_current.json`: accuracy-readiness proxy `pass`, `16/16`.
- `runs/casp17_internal_physics_ts_gate_batch_recursive_current.json`: `completed_to_submission_gate`, `16/16` converted.
- `runs/casp17_submission_gate_packet_recursive_current.json`: `16/16 submission_go`.
- `runs/casp17_ranked_model_depth_packet_current.json`: ranked top-5 depth `pass`, `16/16`, candidate gates `80/80`.
- `runs/casp17_current_target_model_selection_packet_current.json`: internal top-5 selector `pass`, candidates `80`, materialization `pass`, selected TS files `16/16` in `runs/casp17_predictions_model_selected_current`, non-rank-1 selections `13/16`. This is current-target internal support only, not native-calibrated evidence.
- `runs/casp17_internal_score_record_packet_current.json`: SCORE records `16/16`, QSCORE records `13/13` multichain scored-copy files.
- Final selected TS set: `runs/casp17_predictions_statistical_rotamer_current/*TS.pdb`.
- Final statistical-rotamer gate:
  - `runs/casp17_prediction_import_packet_statistical_rotamer_current.json`: `16/16` imported.
  - `runs/casp17_prediction_validation_batch_statistical_rotamer_current.json`: format/geometry/confidence `16/16`.
  - `runs/casp17_internal_scorecard_batch_statistical_rotamer_current.json`: scorecard `16/16`.
  - `runs/casp17_submission_gate_packet_statistical_rotamer_current.json`: `16/16 submission_go`, no no-go rows.
- Model-selected top-5 support gate:
  - `runs/casp17_prediction_import_packet_model_selected_current.json`: `16/16` imported.
  - `runs/casp17_prediction_validation_batch_model_selected_current.json`: format/geometry/confidence `16/16`.
  - `runs/casp17_internal_scorecard_batch_model_selected_current.json`: scorecard `16/16`.
  - `runs/casp17_submission_gate_packet_model_selected_current.json`: `16/16 submission_go`, no no-go rows.
- Model-selected full heavy-atom refinement support lane:
  - Final directory: `runs/casp17_predictions_model_selected_statistical_rotamer_current`.
  - The selected top-5 candidates were promoted from N/CA/C/O/CB support files through sidechain scaffold, repack, completion repair, steric relax, rotamer minimization, polar refinement, forcefield-style minimization, and statistical-rotamer packing proxy.
  - `runs/casp17_sidechain_scaffold_packet_model_selected_current.json`: `16/16 pass`, mean heavy-atom completion `0.999427`.
  - `runs/casp17_sidechain_repack_packet_model_selected_current.json`: `16/16 pass`, soft close contacts `308 -> 253`.
  - `runs/casp17_sidechain_completion_repair_packet_model_selected_current.json`: `16/16 pass`, missing sidechain atoms `64 -> 0`, pre-relax follow-up rows `5`.
  - `runs/casp17_steric_relax_packet_model_selected_current.json`: `16/16 pass`, soft close contacts `342 -> 6`.
  - `runs/casp17_rotamer_minimization_packet_model_selected_current.json`, `runs/casp17_polar_refinement_packet_model_selected_current.json`, `runs/casp17_forcefield_minimization_packet_model_selected_current.json`, and `runs/casp17_statistical_rotamer_packet_model_selected_current.json`: all `16/16 pass`; final soft close contacts `4`.
  - `runs/casp17_all_atom_quality_packet_model_selected_current.json`: all-atom QC `pass`, `16/16`, severe clashes `0`, soft clashes `4`, max soft clashscore per 1000 atoms `0.569`, mean heavy-atom completion `1.0`.
  - `runs/casp17_sidechain_quality_packet_model_selected_current.json`: sidechain QC `pass`, `16/16`, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`.
  - `runs/casp17_prediction_validation_batch_model_selected_refined_current.json` and `runs/casp17_submission_gate_packet_model_selected_refined_current.json`: format/geometry/confidence `16/16`, scorecard `16/16`, `submission_go 16/16`.
  - `runs/casp17_model_selected_refinement_comparison_packet_current.json`: active-vs-model-selected refined comparison `pass`, active gate pass `16/16`, model-selected gate pass `16/16`, review-both `16/16`, auto-promotion candidates `0/16`, promotion `blocked_pending_no_leak_historical_calibration`. Mean active-minus-model-selected soft-clash delta is `0.6875`, but selected candidates can have much larger CA radius of gyration, so native-free promotion remains blocked.
  - `runs/casp17_pdb_coordinate_frame_packet_model_selected_current.json`: coordinate-frame normalization `pass`, `16/16`, fixed-width PDB coordinate parse errors `356 -> 0`, shifted target count `1` (`T1342`, rigid x-shift `76.487 A`), normalized directory `runs/casp17_predictions_model_selected_coordinate_normalized_current`.
  - `runs/casp17_all_atom_quality_packet_model_selected_normalized_current.json` and `runs/casp17_sidechain_quality_packet_model_selected_normalized_current.json`: normalized model-selected QC remains `16/16 pass`, heavy-atom completion `1.0`, severe clashes `0`, soft clashes `4`, sidechain completion `1.0`, rotamer proxy pass `1.0`.
  - `runs/casp17_prediction_import_packet_model_selected_normalized_current.json`, `runs/casp17_prediction_validation_batch_model_selected_normalized_current.json`, `runs/casp17_internal_scorecard_batch_model_selected_normalized_current.json`, and `runs/casp17_submission_gate_packet_model_selected_normalized_current.json`: normalized model-selected lane passes import, format, geometry, confidence, scorecard, and `submission_go` for `16/16`.
- Shape-guarded model-selected support lane:
  - Root cause fixed for straight-line PNGs: the older model-selected support lane selected overextended coordinates for some targets because native-free selection rewarded consensus/low-clash/interface proxies without a hard global-shape guard. This was a PDB coordinate-selection issue, not a PNG renderer issue.
  - `tools/build_casp17_current_target_model_selection_packet.py` now scores CA span per residue, CA radius of gyration per residue, and chain linearity; overextended candidates are blocked before recommendation.
  - `tools/build_casp17_structure_shape_sanity_packet.py` now provides the same protection as a standalone pre-render/pre-submission gate for any generated TS directory.
  - `runs/casp17_current_target_model_selection_shape_guarded_current.json`: selector `pass`, 80 candidates, 16/16 materialized selected TS files in `runs/casp17_predictions_model_selected_shape_guarded_current`, rank-1 recommendations `14/16`, non-rank-1 recommendations `2/16`.
  - `runs/casp17_structure_shape_sanity_packet_model_selected_shape_guarded_current.json` and `runs/casp17_structure_shape_sanity_packet_current.json`: shape sanity `pass`, `16/16`, blocked `0`, max span/Rg/linearity `0.187694/0.074113/0.095013`, max shape penalty `0.0`.
  - `runs/casp17_structure_shape_sanity_packet_model_selected_normalized_legacy_current.json`: old normalized model-selected lane is now documented as shape-blocked, `3/16` pass and `13/16` blocked, confirming why old rendered PNGs could look linear.
  - Shape repair examples: T1342 changed from the older overextended model-selected span/Rg/end-to-end `2145.2/614.9/2145.1 A` to shape-guarded `208.3/47.6/137.1 A`; T1331 changed from `336.3/93.3/289.1 A` to `79.3/20.8/42.6 A`; H2312 changed from `1357.4/349.1/898.9 A` to `140.6/31.0/79.0 A`.
  - Final directory: `runs/casp17_predictions_model_selected_shape_guarded_statistical_rotamer_current`, normalized into `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`.
  - Heavy-atom/refinement stack: sidechain scaffold `16/16`, completion repair inserted `960` missing sidechain atoms and left `0`, extended steric relax `16/16` with soft close contacts `5823 -> 156`, rotamer minimization `16/16`, polar refinement `16/16`, forcefield minimization `16/16`, statistical rotamer `16/16`.
  - `runs/casp17_all_atom_quality_packet_model_selected_shape_guarded_current.json`: all-atom QC `pass`, `16/16`, heavy-atom completion `1.0`, severe clashes `0`, soft clashes `154`, mean soft clashscore per 1000 atoms `0.992`.
  - `runs/casp17_sidechain_quality_packet_model_selected_shape_guarded_current.json`: sidechain QC `pass`, `16/16`, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`, mean rotamer angle deviation `18.271`.
  - `runs/casp17_pdb_coordinate_frame_packet_model_selected_shape_guarded_current.json`: coordinate-frame normalization `pass`, `16/16`, fixed-width parse errors `0 -> 0`, shifted targets `0`.
  - Import/validation/scorecard/submission gate for the shape-guarded normalized lane: `16/16` imported, format/geometry/confidence `16/16`, scorecard `16/16`, and `submission_go 16/16`.
  - `runs/casp17_model_selected_shape_guarded_refinement_comparison_packet_current.json`: active-vs-shape-guarded comparison `pass`, active/model-selected gate pass `16/16`, review-both `14/16`, model-selected internal candidates `2/16`, promotion remains `blocked_pending_no_leak_historical_calibration`.
- Current default CASP17 visual/submission surface:
  - The default `*_current` render, publication, image-quality, molecular-viewer, structure-shape, competitive-readiness, win-readiness, readiness-dashboard, and submission-gate packets were regenerated from the shape-guarded normalized coordinate directory `runs/casp17_predictions_model_selected_shape_guarded_coordinate_normalized_current`.
  - `runs/casp17_submission_gate_packet_current.json`: shape sanity required/pass and `16/16 submission_go`; this is local readiness only, not CASP upload or official performance evidence.
  - `runs/casp17_structure_render_packet_current.json`: shape-guarded `16/16` render coverage with PyMOL base/QC/surface/confidence `16/16`, review panels `16/16`, molecular plates `16/16`, presentation plates `16/16`, stereo-depth `16/16`, and turntable `16/16`.
  - `runs/casp17_publication_figure_packet_current.json`: shape-guarded high-resolution publication/review figures `pass`, publication figures `16/16`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`, molecular showcases `16/16`, minimum observed showcase colorful pixels `8190016`, showcase unique colors `1058`, showcase luminance range `255.0`.
  - `runs/casp17_structure_image_quality_packet_current.json`: shape-guarded rendered-image smoke `pass`, images `272/272`, publication/review/showcase images `80/80`, target completion `16/16`, minimum estimated colorful pixels `1012075`, edge pixels `50050`, luminance range `93.823`.
  - `runs/casp17_molecular_viewer_packet_current.json` and `runs/casp17_molecular_viewer_smoke_packet_current.json`: shape-guarded internal-canvas viewer ready/smoke-pass `16/16`, hosted molecular URL violations `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`.
  - `runs/casp17_competitive_readiness_packet_current.json`: submission readiness `pass`; competitive/win-tier readiness still `blocked`.
  - `runs/casp17_win_readiness_rubric_packet_current.json`: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`; first gap remains native-calibrated accuracy evidence rather than image generation.
- Refinement/QC packets are green for 16 targets:
  - sidechain scaffold `16/16`, mean heavy-atom completion `0.997793`.
  - sidechain repack `16/16`, soft close contacts `1756 -> 1352`.
  - sidechain completion repair `16/16`, missing sidechain atoms after repair `0`.
  - steric relax `16/16`, soft close contacts `1788 -> 18`.
  - rotamer minimization `16/16`, soft close contacts `18 -> 16`.
  - polar refinement `16/16`, soft close contacts `16 -> 15`.
  - forcefield minimization `16/16`, soft close contacts `15 -> 15`.
  - statistical rotamer `16/16`, soft close contacts `15 -> 15`.
  - all-atom quality `16/16`, severe clashes `0`, soft clashes `15`, max soft clashscore per 1000 atoms `0.427`.
  - sidechain quality `16/16`, complete sidechain fraction `1.0`, rotamer proxy pass fraction `1.0`.
- Viewer/render evidence is current for the final statistical-rotamer TS set:
  - `runs/casp17_molecular_viewer_packet_current.json`: `16/16` ready; embedded PDB author records redacted; static fallback previews prefer the new presentation plate when the embedded canvas cannot parse/render the PDB.
  - Molecular viewer default is now internal-canvas-first/internal-only: external network default `disabled`, hosted Mol* handoff disabled, no hosted 3Dmol URL emitted, default runtime `internal_canvas_runtime`, and optional local 3Dmol/WebGL is used only when a local JS bundle is supplied.
  - The internal canvas viewer parses embedded sanitized PDB text in-browser and supports rotate, zoom, spin, center, cartoon/trace/stick/sphere, chain/confidence/residue/spectrum coloring, issue overlays, chain labels, and final static preview fallback without external JavaScript.
  - Molecular viewer side panel now embeds residue-class counts, fixed B-factor confidence bins, chain/interface CA contact summaries, low-confidence residue list, and internal QC overlay totals from render/review/all-atom/sidechain packets: raw/rendered QC hotspots `2674/576`, raw low-confidence hotspots `2653`, raw soft hotspots `30`, all-atom soft clashes `15`, marker-truncated targets `16/16`.
  - `runs/casp17_structure_render_packet_current.json`: base/PyMOL/confidence/QC/surface/residue-class/predicted-CA-interface/stereo-depth/turntable/review/atlas/molecular-plate/presentation-plate renders `16/16`, blocked `0`.
  - Structure render packet now emits `*_structure_residue_class.png`, `*_structure_interface_map.png`, `*_structure_stereo_depth.png`, `*_structure_turntable.png`, `*_structure_molecular_plate.png`, and `*_structure_presentation_plate.png` for `16/16` targets, plus `runs/casp17_structure_render_residue_class_contact_sheet_current.png`, `runs/casp17_structure_render_interface_contact_sheet_current.png`, `runs/casp17_structure_render_stereo_depth_contact_sheet_current.png`, `runs/casp17_structure_render_turntable_contact_sheet_current.png`, `runs/casp17_structure_render_molecular_plate_contact_sheet_current.png`, and `runs/casp17_structure_render_presentation_contact_sheet_current.png`; the presentation plate combines primary molecular render, confidence/surface/QC/residue/interface/atlas/stereo/turntable thumbnails, CASP local-readiness metrics, chemistry counts, and internal CA secondary-structure proxy strips.
  - Predicted CA interface-map summary: chain-pair rows `58`, contacts within 12 A `8486`. This is internal-coordinate sanity/triage evidence, not native DockQ/interface correctness evidence.
  - QC metadata now separates raw hotspot totals from capped rendered markers: raw/display QC hotspots `2674/576`, soft raw/display `30/30`, low-confidence raw/display `2653/555`, with `16/16` targets marked as marker-truncated at the 36-marker cap.
  - Pixel smoke for base, QC, surface, confidence, residue-class, predicted CA interface-map, stereo-depth, review, atlas, molecular-plate, presentation-plate, and priority contact sheets was nonblank; the stereo-depth contact sheet is `1680x1320` with nonflat RGB extrema, sampled T1331 stereo-depth render is `3000x1500` with nonflat RGB extrema, and the priority sheet had `1,744,263` colorful pixels.
  - `runs/casp17_publication_figure_packet_current.json`: publication-style molecular figures `pass`, `16/16`, 3840x2160 figures, 16/16 molecular inspection posters, 16/16 molecular scene posters, 16/16 molecular review boards, contact sheets `runs/casp17_publication_figure_contact_sheet_current.png`, `runs/casp17_molecular_inspection_poster_contact_sheet_current.png`, `runs/casp17_molecular_scene_poster_contact_sheet_current.png`, and `runs/casp17_molecular_review_board_contact_sheet_current.png`, local gallery `runs/casp17_molecular_inspection_gallery_current.html`, minimum observed publication colorful pixels `8197632`, sampled unique colors `618`, luminance range `253.057`; minimum observed inspection colorful pixels `7564352`, sampled unique colors `1168`, luminance range `255.0`; minimum observed scene colorful pixels `7366272`, sampled unique colors `1844`, luminance range `255.0`; minimum observed review-board colorful pixels `7343488`, sampled unique colors `1251`, luminance range `255.0`.
  - `runs/casp17_structure_render_packet_model_selected_current.json`: model-selected refined structures have 16/16 render coverage with PyMOL base/QC/surface/confidence, residue-class, interface-map, stereo-depth, turntable, molecular-plate, and presentation-plate outputs; blocked `0`.
  - `runs/casp17_publication_figure_packet_model_selected_current.json`: model-selected refined publication/review figures `pass`, `16/16`.
  - `runs/casp17_structure_image_quality_packet_model_selected_current.json`: model-selected refined image-quality smoke `pass`, images `256/256`, stereo-depth `16/16`, turntable `16/16`, publication/review images `64/64`.
  - `runs/casp17_model_selected_refinement_comparison_current/*_lane_comparison_board.png`: 16/16 side-by-side active/model-selected refined comparison boards with turntables, presentation plates, selected rank, selection score, CA shape/contact metrics, lane decision, and fail-closed promotion status.
  - `runs/casp17_molecular_viewer_packet_model_selected_normalized_current.json` and `runs/casp17_molecular_viewer_smoke_packet_model_selected_normalized_current.json`: normalized heavy-atom model-selected viewer is `16/16` ready/smoke-pass, internal canvas runtime enabled, hosted molecular URLs `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`, HTML `runs/casp17_molecular_viewer_model_selected_normalized_current.html`.
  - `runs/casp17_structure_render_packet_model_selected_shape_guarded_current.json`: shape-guarded render coverage `16/16`, PyMOL base/QC/surface/confidence `16/16`, residue-class/interface/stereo-depth/turntable/molecular-plate/presentation-plate `16/16`, blocked `0`, raw/rendered QC hotspots `2797/576`.
  - `runs/casp17_publication_figure_packet_model_selected_shape_guarded_current.json`: shape-guarded publication/review figures `pass`, `16/16`, inspection posters `16/16`, scene posters `16/16`, review boards `16/16`, min observed colorful pixels `8200384`, min observed unique colors `810`, luminance range `253.648`.
  - `runs/casp17_structure_image_quality_packet_model_selected_shape_guarded_current.json`: shape-guarded image-quality smoke `pass`, images `256/256`, stereo-depth `16/16`, turntable `16/16`, publication/review images `64/64`, minimum estimated colorful pixels `1012075`, edge pixels `50050`, luminance range `93.823`.
  - `runs/casp17_molecular_viewer_model_selected_shape_guarded_current.html` and `runs/casp17_molecular_viewer_smoke_packet_model_selected_shape_guarded_current.json`: internal-canvas viewer smoke `pass`, `16/16`, hosted molecular URLs `0`, author redaction `16/16`, PDB headers `16/16`, presentation fallbacks `16/16`.
  - `runs/casp17_structure_render_review_queue_current.json`: review queue `ready`, `16/16`, atlas/interface-map panels linked for every target, raw/rendered QC hotspots `2674/576`, interface maps `16/16`, interface chain-pair rows `58`, predicted CA contacts within 12 A `8486`, top interface target `H1335`.
- CASP17 data bundle:
  - `tools/build_casp17_data_bundle.py` mirrors current local CASP17 data into `casp17/` without moving or deleting original `runs/`, `docs/`, and `config/` paths.
  - `casp17/casp17_data_bundle_manifest_current.json`: bundle `ready`, top-level artifacts `798`, mirrored `runs/casp17*` artifacts `796`, mirrored doc artifacts `1`, mirrored config artifacts `1`, files under mirrored artifacts `5924`, missing bundled artifacts `0`; exact byte size is tracked in the manifest.
  - `casp17/README.md` documents the local-only claim boundary: no external data fetch, no CASP submission, no native/current-target accuracy claim.
- Readiness packets:
  - `runs/casp17_competitive_readiness_packet_current.json`: `submission_readiness_status=pass`, competitive/win-tier still `blocked`, `competitive_gap_count=5`; refinement-ablation native evidence is an explicit blocked gap.
  - `runs/casp17_win_readiness_rubric_packet_current.json`: submission-level `pass`, review-quality `pass`, competitive floor `partial`, win-tier `blocked`, requirement count `9`.
  - `runs/casp17_win_tier_action_queue_packet_current.json`: action queue `blocked`, action count `8`; first not-pass action is `all_atom_quality_upgrade`, and `refinement_ablation_native_evidence` is `blocked_input` with `manifest_missing`.
  - `runs/casp17_win_tier_threshold_packet_current.json`: operational threshold packet `blocked_input`, current proven level `review_quality`, threshold rows pass/partial/blocked `7/2/18` across `27` rows, first threshold gap `local_all_atom_qc/max_soft_clashscore_per_1000_atoms`; visual molecular review now also requires the publication-figure packet, 16/16 stereo-depth renders, 16/16 turntable review strips, 16/16 molecular inspection posters, 16/16 molecular scene posters, 16/16 molecular review boards, and 16/16 molecular showcases to pass. Complex win-tier evidence includes separate interface F1 and DockQ-like proxy threshold rows.
  - `runs/casp17_win_tier_benchmark_closure_plan_current.json`: closure plan `ready`, benchmark evidence `blocked_input`, competitive rows required `10/5/15`, win rows required `25/15/40`, current rows `0/0/0`, missing win rows `25/15/40`, required prediction/native/ablation/calibration `40/40/400/40`, operator template `runs/casp17_win_tier_benchmark_operator_template_current.csv`.
  - `runs/casp17_win_tier_benchmark_operator_preflight_current.json`: operator preflight `blocked`, rows ready/blocked `0/40`, missing prediction/native/layer files `40/40/400`, calibration-blocked rows `40`, provenance/core blocked rows `40`, threshold blockers `ready_total_below_threshold,ready_monomer_below_threshold,ready_complex_below_threshold`.
  - `runs/casp17_win_tier_benchmark_operator_import_packet_current.json`: operator import `blocked`, preflight ready/blocked `0/40`, candidate historical/calibration rows `0/0`, blockers `operator_preflight_not_pass,ready_count_below_import_threshold`; candidate CSVs are header-only.
  - `runs/casp17_win_tier_benchmark_activation_packet_current.json`: activation gate `blocked`, active files written `false`, candidate historical/calibration rows `0/0`, validated historical/calibration rows `0/0`, blockers include empty candidate CSVs and operator import not pass.
  - `runs/casp17_win_tier_benchmark_operator_dashboard_current.json`: operator dashboard `ready` as a local work surface, rows ready/blocked `0/40`, monomer/complex `25/15`, needs target/core/ablation/calibration/provenance `40/40/40/40/40`, metric profiles monomer `TM,GDT_TS,CA_lDDT` and complex `TM,interface_F1,DockQ,QSbest,IPS`, HTML `runs/casp17_win_tier_benchmark_operator_dashboard_current.html`.
  - `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.json`: evidence fill kit `ready`, benchmark rows `40`, required evidence items `1310`, filled/missing `0/1310`, missing classes target identity/core/ablation/provenance/calibration/native-metric-gates `40/80/400/400/240/150`, HTML `runs/casp17_win_tier_benchmark_evidence_fill_kit_current.html`.
  - `runs/casp17_win_tier_benchmark_input_scaffold_current.json`: input scaffold `ready`, 40 row folders, 160 row-level scaffold files, monomer/complex `25/15`, required prediction/native/ablation files `40/40/400`, required total files `480`, draft historical manifest `runs/casp17_historical_benchmark_manifest_draft_from_operator_current.csv`, draft calibration `runs/casp17_model_selection_calibration_draft_from_operator_current.csv`.
  - `runs/casp17_win_tier_benchmark_input_inventory_current.json`: input inventory `blocked`, ready/blocked rows `0/40`, present/missing required files `0/480`, prediction/native/ablation present `0/0/0` of `40/40/400`, provenance/calibration ready rows `0/0`.
  - `runs/casp17_win_tier_benchmark_fill_priority_packet_current.json`: fill priority `ready`, row count `40`, competitive batch monomer/complex/total `10/5/15`, win-required rows `40`, missing win evidence items `1310`, first priority target `REQUIRED_MONOMER_001`.
  - `runs/casp17_readiness_dashboard_current.json`: readiness dashboard `ready`, current proven level `review_quality`, next unclosed `competitive_floor`, levels pass-or-ready/blocked-or-partial `2/4`, first not-pass level `model_selection_review`, first gap `no_leak_historical_calibration_required_for_model_selected_promotion`, shape-guarded coordinate frame `pass 16/16` with fixed-width errors `0 -> 0`, shape sanity `pass 16/16`, model-selection comparison `pass`, promotion `blocked_pending_no_leak_historical_calibration`, shape-guarded viewer smoke `pass 16/16`, shape-guarded image QC `272/272`, stereo-depth renders `16/16`, turntable renders `16/16`, publication/review/showcase images `80/80`, review boards `16/16`, molecular showcases `16/16`, benchmark rows ready/total `0/40`, missing evidence `1310/1310`, input scaffold `ready` with `480` required file slots, input inventory `blocked` with present/missing files `0/480`, data bundle artifacts `798`, HTML `runs/casp17_readiness_dashboard_current.html`.
  - `runs/casp17_win_gap_closure_packet_current.json`: closure `blocked_input`, current proven level `review_quality`, next unclosed level `competitive_floor`, first open dimension `all_atom_steric_quality`, first threshold gap `sidechain_native_quality/sidechain_native_lddt`, first operator input action `historical_benchmark_inputs`, benchmark missing win rows `40/40`, required prediction/native/ablation/calibration `40/40/400/40`, operator preflight ready/blocked `0/40`, operator import candidate rows `0/0`, data bundle artifacts `521`.
  - `runs/casp17_structure_image_quality_packet_current.json`: image-quality smoke `pass`, images `272/272`, targets complete `16/16`, stereo-depth renders `16/16`, turntable renders `16/16`, molecular plates `16/16`, presentation plates `16/16`, publication/review/showcase images `80/80`, minimum estimated colorful pixels `1012075`, minimum estimated edge pixels `50050`, minimum luminance range `93.823`.
- Historical benchmark intake is stricter now:
  - `tools/build_casp17_historical_benchmark_manifest_scaffold.py` requires no-leak provenance columns in addition to local prediction/native PDB paths.
  - Required provenance includes `prediction_created_at`, `native_release_date`, prediction-before-native-release confirmation, no public/template/native leak, no other-team model, no post-release information, non-current-CASP17 target status, and operator clearance.
  - Historical and sidechain-native benchmark scorers now require full CA coverage by default, so subset-only prediction/native overlaps cannot pass win-tier evidence.
  - Historical complex benchmark rows now record interface contact precision/recall/F1, IPS/Jaccard proxy, QSbest-like contact overlap, interface iRMSD, and DockQ-like proxy; complex win-tier thresholding consumes the DockQ-like proxy separately from interface F1.
  - `tools/build_casp17_refinement_ablation_packet.py` now exists to compare recursive/scored/scaffold/repack/steric/rotamer/polar/forcefield/statistical-rotamer layers against cleared no-leak historical natives and record final-vs-baseline TM/GDT/lDDT/RMSD/interface deltas.
  - `runs/casp17_historical_benchmark_manifest_scaffold_current.json` and promotion packet remain `blocked`, with 0 ready/promoted rows.
  - Historical scaffold and ready-manifest CSV headers now expose optional refinement-ablation layer path columns from `recursive_prediction_pdb` through `statistical_rotamer_prediction_pdb`, and promotion preserves those layer-specific columns for ablation scoring.
  - `runs/casp17_historical_input_preflight_packet_current.json` now reports source mode `scaffold`, candidate/historical-ready/ablation-ready `2/0/0`, missing prediction/native/layer files `2/2/20`, and preflight status `blocked`.
  - `runs/casp17_historical_input_workorder_packet_current.json` now translates the blocked preflight into operator workorders: status `ready`, workorders/core/ablation/complete `2/2/0/0`, missing core files `4`, missing ablation layer files `20`, and operator template `runs/casp17_historical_benchmark_manifest_operator_template_current.csv`.
  - `runs/casp17_win_tier_action_queue_packet_current.json` now includes the workorder status in the historical benchmark input action: workorder `ready`, core workorders `2`, template path present.
  - `runs/casp17_refinement_ablation_packet_current.json` remains `blocked`, with `manifest_blockers=manifest_missing`, `benchmark_count=0`, and `layer_count=10`.
- Verification:
  - py_compile passed for the touched CASP17 predictor/readiness tools.
  - Focused predictor/sidechain-native/competitive/win-readiness/action-queue tests: `18 passed in 11.26s`.
  - Focused strict historical benchmark provenance/coverage/readiness tests: `29 passed in 2.31s`.
  - Focused refinement-ablation tests: `2 passed in 0.28s`.
  - Focused competitive/win-readiness/action-queue refinement-ablation wiring tests: `6 passed in 0.51s`.
  - Focused historical input preflight/action-queue tests: `4 passed in 0.35s`.
  - Focused render/review queue tests: `4 passed in 5.80s`.
  - Focused win-gap-closure/data-bundle tests: `3 passed in 0.32s`.
  - Focused render/image-quality/viewer/win-readiness/data-bundle tests: `10 passed in 13.76s`.
  - Focused molecular viewer/render/review queue tests: `5 passed in 7.92s`.
  - Focused historical input workorder/action queue tests: `3 passed in 0.29s`.
  - Focused benchmark-closure/win-gap-closure/data-bundle tests: `5 passed in 0.47s`.
  - Focused benchmark operator preflight/win-gap-closure/data-bundle tests: `5 passed in 0.45s`.
  - Focused benchmark-operator dashboard/preflight/import/win-gap/data-bundle tests: `8 passed in 0.75s`.
  - Focused data-bundle/evidence fill-kit tests: `3 passed in 0.32s`.
  - Focused structure-image-quality/threshold/win-gap/data-bundle tests: `6 passed in 0.64s`.
  - Focused readiness-dashboard/data-bundle tests: `3 passed in 0.30s`.
  - Focused historical benchmark/competitive/win-readiness/action-queue/threshold/win-gap/readiness tests: `15 passed in 1.50s`.
  - Focused publication/structure-image-quality/threshold/readiness-dashboard/win-gap/data-bundle tests: `9 passed in 2.35s`.
  - Focused metric fill-kit/operator-dashboard/win-gap/readiness/data-bundle/image-quality tests: `8 passed in 0.92s`.
  - Focused input-scaffold/readiness-dashboard/data-bundle/win-gap tests: `5 passed in 0.57s`.
  - Focused input-inventory/readiness-dashboard/data-bundle/input-scaffold tests: `5 passed in 0.55s`.
  - Focused stereo-depth image-quality/readiness/threshold/win-gap/data-bundle tests: `7 passed in 0.82s`.
  - Focused selection/activation/render/dashboard/bundle tests after top-5 materialization: `15 passed in 17.41s`.
  - Focused forcefield/model-selection/render/publication/image-quality/bundle tests after model-selected heavy-atom refinement: `12 passed in 17.75s`.
  - Focused model-selected comparison/data-bundle tests: `3 passed in 0.62s`.
  - Focused coordinate-frame/readiness/viewer/bundle tests: `7 passed in 0.81s`.
  - Focused normalized render/publication/image/readiness/bundle tests: `10 passed in 17.81s`.
  - Focused shape/fill-priority/dashboard/image/bundle tests: `9 passed in 0.95s`.
  - Focused shape-sanity/model-selection/readiness/data-bundle tests: `7 passed in 0.61s`.
  - `git diff --check`: clean.
  - Registered author-code pattern redacted from `.betelgeuze/trace.jsonl`; remaining author-like matches are dummy fixtures or vendored examples.
  - Latest `casp17/` mirror refresh reports source/bundled CASP17 artifacts in sync via manifest, missing bundled artifacts `0`; focused data-bundle coverage is included in the `7 passed in 0.81s` suite above.
  - Focused molecular-showcase/threshold/readiness image tests: `6 passed in 2.51s`.
  - Full CASP17 targeted unit suite: `171 passed in 61.03s`.
  - `git diff --check`: clean.
  - No registered author code remained in `.betelgeuze`, docs, tools, or tests; remaining generic code-like matches are dummy test placeholders, vendored UUID examples, or search-output trace snippets.

## Remaining Gap

The CASP17 local submission floor is green for the current 16 open protein targets. Win-tier/native-accuracy readiness remains fail-closed because no local no-leak historical benchmark manifest, refinement-ablation layer evidence, sidechain-native benchmark, or model-selection calibration CSV has been populated.

Next action:

1. Populate cleared local historical prediction/native pairs in `runs/casp17_historical_benchmark_predictions_current` and `runs/casp17_historical_benchmark_natives_current`.
2. Run the historical manifest scaffold and promotion tools.
3. Promote only ready no-leak rows into `runs/casp17_historical_benchmark_manifest_current.csv`.
4. Run historical native benchmark, sidechain-native benchmark, and model-selection calibration packets.
5. Populate historical ablation layer directories or layer-specific manifest prediction columns and run `tools/build_casp17_refinement_ablation_packet.py`.
6. Use those native-scored historical and ablation metrics to tune SCORE/QSCORE/model selection and interface sampling.

No CASP portal upload/submission, commit, staging, push, external predictor, public/template structure lookup, or public target-native lookup was performed.
