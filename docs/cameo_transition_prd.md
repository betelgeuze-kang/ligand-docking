# CAMEO Transition PRD

Status: draft
Date: 2026-06-03 KST

## Purpose

Move the project from a CASP17-submission-centered workstream to a sustainable
two-lane strategy:

1. CAMEO as the public blind-benchmark credibility lane.
2. Restricted local delivery as the near-term B2B pilot and revenue lane.

This PRD translates the `구현` assessment into an implementation plan. It does
not register a CAMEO server, submit predictions, send email, delete artifacts,
or broaden scientific claims.

## Source Documents

Internal:

- `구현`
- `README.md`
- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `.betelgeuze/cameo_transition_doc_audit_2026-06-03.md`

External CAMEO references checked on 2026-06-03:

- `https://cameo3d.org/help`
- `https://cameo3d.org/faq`
- `https://www.expasy.org/resources/cameo`

## Current State

### What Is Already Strong

- The repo already has a local-delivery molecular dynamics and ligand validation
  stack with reproducible gates.
- Restricted local delivery is the most mature product path for guarded B2B
  pilots.
- Current claim policy allows delivery-ready wording only for the restricted
  `kinase,gpcr,ion_channel` scope and only after bundle validation is green.
- CASP17 work has produced reusable infrastructure:
  - target intake and status boards
  - PDB/TS validation gates
  - model-selection and shape-guard logic
  - molecular viewer and object-library generation
  - operator decision-kit patterns

### What Is Not Ready

- `betelgeuze_cameo` now exists as an initial intake/ledger package, but it is
  not yet a full CAMEO production integration.
- A CAMEO receiver skeleton now exists, but prediction-email sender and
  result-fetcher surfaces do not exist yet.
- API syntax/import blockers have been repaired at the Python compile level.
  Runtime FastAPI endpoint tests require the separate `requirements-api.txt`
  dependency set.
- `api/tasks.py` now refuses to emit fake scientific output and fails closed
  until simulation execution is wired to the internal production pipeline.
- Transition cleanup tooling now has a dry-run classifier for the new
  CASP17-heavy transition targets and config-referenced ligand-heavy roots, but
  no archive, externalize, or delete action has been approved or executed.

### Implemented Foundation Slice

Current implementation artifacts:

- `betelgeuze_cameo/intake.py`: dependency-light CAMEO intake parsing, email
  redaction, fail-closed job record construction, and local ledger persistence.
- `betelgeuze_cameo/selector.py`: dependency-light CAMEO model1/top5 selector
  contract that blocks external model pools from internal-proof selection.
- `betelgeuze_cameo/format_validation.py`: dependency-light PDB/mmCIF format
  gate for selected CAMEO model files.
- `api/cameo.py`: FastAPI adapter for `/cameo/targets` POST/GET plus
  read-only `/cameo/operations`, `/cameo/architecture-validation`,
  `/cameo/official-results`, and `/cameo/registration-approval` status
  endpoints; the architecture-validation status surface carries the
  official-results intake handoff without fetching assessment pages.
- `tools/build_cameo_model1_selection_packet.py`: candidate CSV to model1/top5
  selection packet builder.
- `tools/build_cameo_format_validation_packet.py`: selected model CSV to
  PDB/mmCIF validation packet builder.
- `betelgeuze_cameo/handoff.py`: email-disabled CAMEO dry-run handoff contract
  that packages selected and format-validated model metadata without outbound
  delivery.
- `tools/build_cameo_dry_run_handoff_packet.py`: selection + format validation
  JSON to dry-run attachment manifest builder.
- `betelgeuze_cameo/performance.py`: official CAMEO result intake and
  model1-centered performance scorecard contract.
- `betelgeuze_cameo/architecture_validation.py`: links the local product
  architecture contract to the official CAMEO validation, threshold-policy,
  performance scorecard, official-results, and registration-approval evidence
  lanes.
- `betelgeuze_cameo/cli.py`: read-only local CAMEO status CLI for operator
  inspection of validation, operations, capability, official-results, and
  registration-readiness artifacts without external mutation; all-status
  aggregates CAMEO approval tokens, official-results intake state,
  validation/performance readiness, API dependency approval, receiver-smoke
  status, and registration/email approval state.
- `betelgeuze_cameo/official_results.py`: validates official CAMEO result rows
  and provenance before performance-scorecard use.
- `tools/build_cameo_official_results_intake_gate.py`: writes JSON/CSV/MD
  official-result intake gates and a fillable operator template without
  fetching external web pages.
- `betelgeuze_cameo/performance_policy.py`: defines the product-grade model1
  CAMEO threshold policy for future official result evaluation without
  fetching official results or using local native accuracy.
- `tools/build_cameo_performance_threshold_policy.py`: writes JSON/CSV/MD
  threshold-policy packets with explicit lDDT, TM-score, QS-score, and finite
  RMSD thresholds.
- `tools/build_cameo_performance_scorecard.py`: official result CSV +
  dry-run handoff JSON to CAMEO performance scorecard builder.
- `tools/build_cameo_architecture_validation_contract.py`: writes JSON/CSV/MD
  architecture-validation contracts that keep CAMEO product performance claims
  blocked until official evidence and registration approval are present.
- `betelgeuze_cameo/readiness.py`: fail-closed CAMEO validation readiness gate
  that audits selection, format, handoff, and official-result performance
  artifacts.
- `tools/build_cameo_validation_readiness_gate.py`: writes JSON/CSV/MD CAMEO
  validation readiness gates from current artifact paths.
- `tools/build_cameo_validation_repair_work_order.py`: writes the local command
  sequence needed to repair missing CAMEO selection, format, handoff, and
  performance artifacts.
- `betelgeuze_cameo/operator_inputs.py`: validates operator-filled CAMEO repair
  CSVs before any local rebuild command can be treated as ready.
- `tools/build_cameo_operator_input_kit.py`: writes placeholder CAMEO repair CSV
  templates and a manifest for operator input.
- `tools/build_cameo_operator_input_validation.py`: writes JSON/CSV/MD
  validation packets for filled CAMEO repair inputs.
- `tools/build_cameo_local_format_smoke_inputs.py`: writes a synthetic
  CAMEO dry-run smoke model plus filled candidates/models CSV rows for local
  input, selection, format, handoff, and readiness validation without using a
  native structure, CASP model, official result, or external state.
- `betelgeuze_cameo/repair_preflight.py`: validates the CAMEO repair work-order
  command sequence without executing selection, format, handoff, or performance
  rebuilds.
- `tools/build_cameo_repair_execution_preflight.py`: writes JSON/CSV/MD repair
  execution preflight packets from the repair work order and operator input
  validation artifact.
- `betelgeuze_cameo/capability_preflight.py`: audits CAMEO receiver capability,
  registration approval, outbound email, and prediction-generation policy before
  public server registration is allowed.
- `betelgeuze_cameo/receiver_smoke.py`: audits local CAMEO route presence and,
  when API dependencies are installed, TestClient POST 200 plus fail-closed
  ledger persistence.
- `betelgeuze_cameo/api_dependency.py`: audits the optional API server
  dependency profile needed for local CAMEO receiver runtime smoke.
- `tools/build_cameo_capability_preflight.py`: writes JSON/CSV/MD CAMEO
  capability preflight packets without registering, submitting, or sending
  email.
- `tools/build_cameo_receiver_smoke_contract.py`: writes JSON/CSV/MD receiver
  smoke contracts without starting a public server or opening an external port.
- `tools/build_cameo_api_dependency_readiness.py`: writes JSON/CSV/MD API
  dependency readiness packets without installing packages.
- `tools/build_cameo_runtime_repair_work_order.py`: writes JSON/CSV/MD
  approval-gated API dependency activation and local CAMEO smoke rerun command
  packets without installing packages, starting a server, or mutating external
  state.
- `tools/build_cameo_validation_operations_dossier.py`: consolidates CAMEO
  operator-input, validation-evidence, runtime-smoke, and public-registration
  readiness into a fail-closed operations dossier without installing packages,
  registering servers, submitting predictions, or sending email.
- `tools/build_cameo_public_registration_approval_gate.py`: validates CAMEO
  public endpoint, results/contact email, and registration/email approval
  tokens without registering a server or sending email.
- `tools/build_transition_cleanup_manifest.py`: dry-run heavy-artifact cleanup
  classifier for CASP17 external pools, legacy archives, trajectory frames,
  config-referenced ligand-heavy roots, build output, and local virtual
  environments.
- `betelgeuze_product/docking_request.py`: commercial molecular-structure and
  ligand-docking request contract with restricted-scope validation and local
  fail-closed ledger records.
- `betelgeuze_product/readiness.py`: product readiness gate that combines a
  docking request contract with local-delivery verdict evidence while keeping
  execution disabled.
- `betelgeuze_product/work_order.py`: product execution work-order contract
  that records operator-reviewed commands without executing docking or building
  bundles.
- `betelgeuze_product/capability_surface.py`: product capability surface
  contract that audits guarded molecular-structure analysis, ligand-docking,
  API/package, bundle, and claim guardrail coverage from local artifacts.
- `betelgeuze_product/service_boundary.py`: product service-boundary contract
  that audits API routes, CLI commands, console script metadata, and status
  artifact registry coherence without executing product actions.
- `betelgeuze_product/api_contract.py`: static product API contract that audits
  route declarations, request models, docking response keys, and read-only
  status safety flags without starting a server.
- `betelgeuze_product/delivery_evidence.py`: product delivery evidence contract
  that audits local-delivery gates, product handoff gates, and final
  bundle-claim readiness without emitting customer-facing delivery wording.
- `betelgeuze_product/pilot_packet.py`: product pilot packet contract that
  reconciles product handoff evidence, bundle contract, and optional final
  bundle validation evidence before restricted customer handoff.
- `api/product.py`: FastAPI adapter for `/product/capabilities`,
  `/product/architecture`, `/product/service-boundary`, `/product/api-contract`,
  `/product/operations`, `/product/license-decision`,
  `/product/license-options`, `/product/commercial-independence`,
  `/product/release-readiness`, `/product/structure/analyze`, and
  `/product/docking/jobs` POST/GET with execution disabled until the internal
  production pipeline is explicitly wired; commercial and release status
  surfaces also expose the license-decision handoff without choosing or writing
  a license.
- `api/goal.py`: FastAPI adapter for `/goal/status`, `/goal/readiness`,
  `/goal/actions`, `/goal/release-decision`, `/goal/burndown`, and
  `/goal/api-contract`, exposing the commercial product, CAMEO validation,
  CASP17 transition, and cleanup objective status from local artifacts only.
- `pyproject.toml`: installable local package metadata for the product,
  CAMEO-validation, and cleanup status CLIs: `betelgeuze-product`,
  `betelgeuze-cameo`, and `betelgeuze-cleanup`; the commercial-independence
  gate verifies those console scripts resolve to local CLI targets without
  installing the package.
- `tools/build_goal_readiness_rollup.py`: top-level rollup for commercial
  product execution, CAMEO validation, transition cleanup, and ligand-heavy
  cleanup readiness, including cleanup postcheck-contract status.
- `tools/build_goal_operator_action_board.py`: consolidated operator action
  board for CAMEO fill-in rows, product approval, cleanup approval tokens, and
  large review-only cleanup surfaces, with cleanup postcheck status propagation.
- `tools/build_goal_operator_intake_kit.py`: read-only operator intake kit that
  gathers the current CAMEO, product, cleanup, and protected-policy templates
  plus catalog-wide and current-action approval-token summaries into one local
  manifest without filling approvals.
- `tools/build_goal_release_decision_gate.py`: full-goal release gate that
  checks commercial product readiness, official CAMEO validation readiness, and
  cleanup postcheck/completion before any release-ready claim is allowed.
- `tools/build_goal_release_burndown_work_order.py`: release blocker burndown
  work order that maps product, CAMEO, cleanup, and final refresh blockers to
  existing approval-gated artifacts, postcheck refresh commands, and local
  command sources.
- `tools/build_goal_api_surface_contract.py`: static read-only contract for
  the `/goal` API family, route registration, local artifact sources, rollup
  keys, and fail-closed mutation flags without starting a server.
- `tools/build_product_execution_approval_gate.py`: product execution
  approval-token gate that validates exact operator approval for the current
  product execution work order without running docking.
- `tools/build_product_capability_surface_contract.py`: writes JSON/CSV/MD
  product capability surface contracts without running docking or generating
  scientific results.
- `tools/build_product_service_boundary_contract.py`: writes JSON/CSV/MD
  product service-boundary contracts from local source/package metadata without
  running docking, writing licenses, or mutating external state.
- `tools/build_product_api_contract.py`: writes JSON/CSV/MD API contract
  packets from local source metadata without starting a server or mutating
  external state.
- `tools/build_casp17_transition_surface_contract.py tools/build_cleanup_snapshot_preflight.py`: cleanup safety gate that checks
  approval-gated archive/externalize/delete rows for required snapshots,
  frozen candidate manifests, and postcheck readiness before cleanup execution.
- `tools/build_cleanup_snapshot_artifacts.py`: local cleanup snapshot artifact
  builder that writes metadata/listing JSON evidence for snapshot-required
  archive/externalize rows without executing cleanup.
- `tools/build_cleanup_execution_approval_dossier.py`: cleanup execution
  approval dossier that consolidates snapshot-backed transition cleanup rows,
  ligand-heavy stale payload candidates, and protected-not-promoted rows before
  any operator-approved execution.
- `tools/build_cleanup_payload_manifest_lock.py`: cleanup payload lock that
  computes stable per-row and manifest fingerprints for the current approval
  dossier before operator approval intake.
- `tools/build_cleanup_postcheck_contract.py`: row-specific postcheck contract
  that maps approval-ready cleanup rows and protected policy rows to required
  post-execution evidence plus global refresh commands without approving or
  executing cleanup.
- `api/cleanup.py`: read-only FastAPI adapter for `/cleanup/operations`,
  `/cleanup/approval-gate`, `/cleanup/postcheck`, `/cleanup/completion`,
  `/cleanup/payloads`, `/cleanup/protected-ligand-heavy-review`, and
  `/cleanup/protected-policy` cleanup status surfaces without deleting,
  archiving, externalizing, or mutating external state.
- `betelgeuze_cleanup/cli.py`: read-only local cleanup status CLI for
  operator inspection of approval, payload-lock, snapshot, protected-policy,
  ligand-heavy, postcheck, and completion artifacts; all-status aggregates
  cleanup approval tokens, reclaim/protected payload sizes, postcheck counts,
  and protected policy state without approving or executing cleanup.
- `tools/build_cleanup_operations_surface_contract.py`: cleanup API surface
  contract that verifies the read-only cleanup CLI plus cleanup operations,
  approval-gate, postcheck, completion, payload, protected ligand-heavy review,
  and protected-policy endpoints are registered and fail-closed.
- `tools/build_cleanup_execution_approval_gate.py`: operator approval-token
  gate that validates per-row cleanup decisions against the approval dossier
  and payload lock, then writes a fillable approval template without executing
  cleanup.
- `tools/build_cleanup_completion_gate.py`: final local cleanup completion
  evidence gate for cleanup authorization, transition cleanup completion,
  ligand-heavy cleanup completion, and protected policy resolution.
- `api/casp17.py`: read-only FastAPI adapter for `/casp17/upload` and
  `/casp17/transition` status surfaces that expose current CASP17 upload
  operator decisions, active-manifest stale-folder locks, and cleanup context
  without uploading, computing native accuracy, deleting, or mutating external
  state.
- `tools/build_casp17_transition_surface_contract.py`: CASP17 transition API
  surface contract that verifies the read-only upload/transition endpoints,
  CASP17 upload artifact references, cleanup artifact references, and
  fail-closed flags.
- `tools/build_large_cleanup_surface_drilldown.py`: read-only drilldown for
  large review-only cleanup surfaces, including current ligand-heavy dry-run
  status for known payload directories.
- `tools/build_protected_cleanup_payload_review.py`: read-only review packet
  for protected heavy payload rows that must not be promoted to deletion
  approval without an explicit cleanup-policy change.
- `tools/build_protected_ligand_heavy_payload_deep_review.py`: read-only deep
  review that splits protected ligand-heavy parent rows into known payload
  children and preservation siblings without promoting deletion.
- `tools/build_protected_cleanup_policy_decision_gate.py`: validates
  operator policy decisions for protected cleanup rows without promoting
  deletion or mutating external state.
- `tools/build_product_delivery_evidence_contract.py`: writes JSON/CSV/MD
  product delivery evidence contracts from existing local-delivery and product
  handoff artifacts.
- `tools/build_product_pilot_packet_contract.py`: writes JSON/CSV/MD pilot
  packet contracts without execution, bundle assembly, or customer wording.
- `tools/build_product_release_operations_dossier.py`: consolidates product
  readiness, commercial independence, license decision, execution approval,
  bundle contract, delivery evidence, and pilot packet state into a fail-closed
  release operations dossier without running docking, writing a license file,
  or assembling bundles.
- `betelgeuze_product/architecture.py`: consolidates product, CAMEO,
  CASP17-transition, and cleanup evidence into a fail-closed architecture
  contract for the commercial molecular-structure analysis and ligand-docking
  product.
- `tools/build_product_architecture_contract.py`: writes JSON/CSV/MD product
  architecture contracts without running docking, submitting predictions,
  deleting data, or mutating external state.
- `betelgeuze_product/commercial_independence.py`: audits local packaging,
  dependency, license, optional-profile separation, deployment, and product
  surface evidence before commercial independent-product claims are allowed.
- `tools/build_product_commercial_independence_gate.py`: writes JSON/CSV/MD
  commercial-independence gates without installing packages or mutating
  external state.
- `betelgeuze_product/license_decision.py`: validates operator-supplied license
  decision metadata before a separate LICENSE file creation review can happen.
- `betelgeuze_product/license_options.py`: summarizes operator-selectable
  license paths and the license-decision intake contract without legal advice,
  license choice, or LICENSE-file creation.
- `tools/build_product_license_decision_gate.py`: writes JSON/CSV/MD license
  decision gates and a fillable operator template without choosing or writing a
  license.
- `tools/build_product_license_decision_packet.py`: writes JSON/CSV/MD
  license decision option packets for operator review without choosing or
  writing a license.
- `betelgeuze_product/cli.py`: read-only local product CLI for capabilities,
  architecture, operations, commercial-independence, license-decision,
  license-options, release-readiness, and all-status JSON; all-status also
  aggregates product approval tokens and release-operation stage counts without
  running docking, writing a license, assembling bundles, or mutating external
  state.
- `betelgeuze_product/structure_analysis.py`: parses local PDB/mmCIF content
  or files for atom, chain, residue, water, and ligand-like HETATM summaries
  without fetching structures, predicting structures, running docking, or
  mutating external state.
- `betelgeuze_product/structure_report.py`: resolves product target-native CSV
  evidence into a parsed local structure-analysis report, including atom,
  chain, residue, pocket-center, and ligand-like HETATM counts without fetching
  structures or running docking.
- `tools/build_product_structure_analysis_report.py`: writes JSON/CSV/MD product
  structure-analysis reports from local target-native evidence.

Current verification:

- `python3 -m py_compile api/main.py api/tasks.py api/cameo.py api/casp17.py api/cleanup.py api/goal.py api/product.py betelgeuze_cameo/intake.py betelgeuze_cameo/selector.py betelgeuze_cameo/format_validation.py betelgeuze_cameo/handoff.py betelgeuze_cameo/operator_inputs.py betelgeuze_cameo/repair_preflight.py betelgeuze_cameo/api_dependency.py betelgeuze_cameo/receiver_smoke.py betelgeuze_cameo/capability_preflight.py betelgeuze_cameo/official_results.py betelgeuze_cameo/architecture_validation.py betelgeuze_cameo/cli.py betelgeuze_cleanup/cli.py betelgeuze_product/docking_request.py betelgeuze_product/structure_analysis.py betelgeuze_product/structure_report.py betelgeuze_product/readiness.py betelgeuze_product/work_order.py betelgeuze_product/capability_surface.py betelgeuze_product/architecture.py betelgeuze_product/bundle_contract.py betelgeuze_product/delivery_evidence.py betelgeuze_product/pilot_packet.py betelgeuze_product/commercial_independence.py betelgeuze_product/license_decision.py betelgeuze_product/license_options.py betelgeuze_product/service_boundary.py betelgeuze_product/cli.py tools/build_transition_cleanup_manifest.py tools/build_cameo_model1_selection_packet.py tools/build_cameo_format_validation_packet.py tools/build_cameo_dry_run_handoff_packet.py tools/build_cameo_operator_input_validation.py tools/build_cameo_local_format_smoke_inputs.py tools/build_cameo_repair_execution_preflight.py tools/build_cameo_api_dependency_readiness.py tools/build_cameo_receiver_smoke_contract.py tools/build_cameo_capability_preflight.py tools/build_cameo_runtime_repair_work_order.py tools/build_cameo_official_results_intake_gate.py tools/build_cameo_performance_scorecard.py tools/build_cameo_validation_readiness_gate.py tools/build_cameo_validation_operations_dossier.py tools/build_cameo_architecture_validation_contract.py tools/build_cameo_public_registration_approval_gate.py tools/build_product_readiness_gate.py tools/build_product_structure_analysis_report.py tools/build_product_execution_work_order.py tools/build_product_execution_approval_gate.py tools/build_product_capability_surface_contract.py tools/build_product_architecture_contract.py tools/build_product_service_boundary_contract.py tools/build_product_bundle_contract.py tools/build_product_delivery_evidence_contract.py tools/build_product_pilot_packet_contract.py tools/build_product_release_operations_dossier.py tools/build_product_commercial_independence_gate.py tools/build_product_license_decision_gate.py tools/build_product_license_decision_packet.py tools/build_goal_api_surface_contract.py tools/build_goal_readiness_rollup.py tools/build_goal_operator_action_board.py tools/build_goal_operator_intake_kit.py tools/build_goal_release_decision_gate.py tools/build_goal_release_burndown_work_order.py tools/build_casp17_transition_surface_contract.py tools/build_cleanup_snapshot_preflight.py tools/build_cleanup_snapshot_artifacts.py tools/build_cleanup_execution_approval_dossier.py tools/build_cleanup_payload_manifest_lock.py tools/build_cleanup_postcheck_contract.py tools/build_cleanup_operations_surface_contract.py tools/build_cleanup_execution_approval_gate.py tools/build_cleanup_completion_gate.py tools/build_large_cleanup_surface_drilldown.py tools/build_protected_cleanup_payload_review.py tools/build_protected_ligand_heavy_payload_deep_review.py tools/build_protected_cleanup_policy_decision_gate.py`
- `python3 -m pytest -q tests/unit/test_betelgeuze_product_structure_analysis.py tests/unit/test_betelgeuze_product_structure_report.py tests/unit/test_betelgeuze_product_docking_request.py tests/unit/test_betelgeuze_product_readiness.py tests/unit/test_betelgeuze_product_work_order.py tests/unit/test_betelgeuze_product_capability_surface.py tests/unit/test_betelgeuze_product_service_boundary.py tests/unit/test_betelgeuze_product_cli.py tests/unit/test_build_product_capability_surface_contract.py tests/unit/test_build_product_architecture_contract.py tests/unit/test_build_product_service_boundary_contract.py tests/unit/test_build_product_execution_approval_gate.py tests/unit/test_betelgeuze_product_bundle_contract.py tests/unit/test_betelgeuze_product_delivery_evidence.py tests/unit/test_betelgeuze_product_pilot_packet.py tests/unit/test_betelgeuze_product_commercial_independence.py tests/unit/test_build_product_commercial_independence_gate.py tests/unit/test_betelgeuze_product_license_decision.py tests/unit/test_betelgeuze_product_license_options.py tests/unit/test_build_product_license_decision_gate.py tests/unit/test_build_product_release_operations_dossier.py tests/unit/test_api_product_import.py tests/unit/test_betelgeuze_cameo_intake.py tests/unit/test_betelgeuze_cameo_selector.py tests/unit/test_betelgeuze_cameo_format_validation.py tests/unit/test_betelgeuze_cameo_handoff.py tests/unit/test_betelgeuze_cameo_operator_inputs.py tests/unit/test_betelgeuze_cameo_repair_preflight.py tests/unit/test_betelgeuze_cameo_api_dependency.py tests/unit/test_betelgeuze_cameo_receiver_smoke.py tests/unit/test_betelgeuze_cameo_capability_preflight.py tests/unit/test_betelgeuze_cameo_cli.py tests/unit/test_betelgeuze_cameo_official_results.py tests/unit/test_betelgeuze_cameo_performance.py tests/unit/test_betelgeuze_cameo_readiness.py tests/unit/test_betelgeuze_cameo_architecture_validation.py tests/unit/test_betelgeuze_cleanup_cli.py tests/unit/test_api_cameo_import.py tests/unit/test_api_casp17_import.py tests/unit/test_api_cleanup_import.py tests/unit/test_api_goal_import.py tests/unit/test_build_cameo_api_dependency_readiness.py tests/unit/test_build_cameo_receiver_smoke_contract.py tests/unit/test_build_cameo_capability_preflight.py tests/unit/test_build_cameo_runtime_repair_work_order.py tests/unit/test_build_cameo_official_results_intake_gate.py tests/unit/test_build_cameo_validation_operations_dossier.py tests/unit/test_build_cameo_local_format_smoke_inputs.py tests/unit/test_build_cameo_public_registration_approval_gate.py tests/unit/test_build_casp17_transition_surface_contract.py tests/unit/test_build_transition_cleanup_manifest.py tests/unit/test_build_product_pilot_packet_contract.py tests/unit/test_build_goal_api_surface_contract.py tests/unit/test_build_goal_readiness_rollup.py tests/unit/test_build_goal_operator_action_board.py tests/unit/test_build_goal_operator_intake_kit.py tests/unit/test_build_goal_release_decision_gate.py tests/unit/test_build_goal_release_burndown_work_order.py tests/unit/test_build_cleanup_snapshot_preflight.py tests/unit/test_build_cleanup_snapshot_artifacts.py tests/unit/test_build_cleanup_execution_approval_dossier.py tests/unit/test_build_cleanup_payload_manifest_lock.py tests/unit/test_build_cleanup_operations_surface_contract.py tests/unit/test_api_cleanup_import.py tests/unit/test_build_cleanup_execution_approval_gate.py tests/unit/test_build_cleanup_completion_gate.py tests/unit/test_build_large_cleanup_surface_drilldown.py tests/unit/test_build_protected_cleanup_payload_review.py tests/unit/test_build_protected_ligand_heavy_payload_deep_review.py tests/unit/test_build_protected_cleanup_policy_decision_gate.py`

The FastAPI runtime endpoint test is skipped unless the API dependency set from
`requirements-api.txt` is installed. The current expanded verification also
includes `betelgeuze_cameo/performance_policy.py`,
`tools/build_cameo_performance_threshold_policy.py`,
`tests/unit/test_betelgeuze_cameo_performance_policy.py`, and
`tests/unit/test_build_cameo_performance_threshold_policy.py`. It also includes
`betelgeuze_product/api_contract.py`, `tools/build_product_api_contract.py`,
`tests/unit/test_betelgeuze_product_api_contract.py`, and
`tests/unit/test_build_product_api_contract.py`. It now also includes
`tools/build_cleanup_postcheck_contract.py`,
`tools/build_cleanup_completion_gate.py`,
`tests/unit/test_build_cleanup_postcheck_contract.py`, and
`tests/unit/test_build_cleanup_completion_gate.py`, plus
`tools/build_goal_api_surface_contract.py` and
`tests/unit/test_build_goal_api_surface_contract.py`. The current cleanup
focused pytest result is `46 passed, 1 skipped`; the current goal-level
focused pytest result is `31 passed, 1 skipped`; the current expanded
verification result is `212 passed, 5 skipped`.

## CAMEO Requirements Summary

Current official CAMEO behavior relevant to this repo:

- CAMEO is tied to the weekly PDB prerelease/release cycle.
- The prerelease sequence window starts Saturday around 03:00 UTC, and
  predictions close the following Wednesday at 00:00 UTC.
- CAMEO currently lists complex structures modeling (3D) as the active category;
  older single-chain 3D, QE, CP, and ligand-binding-site categories are
  discontinued.
- A target can contain one or more protein, peptide, DNA, or RNA sequences and
  optional ligands from the same prereleased PDB entry.
- CAMEO sends target information to registered servers by HTTP POST or GET.
- A server should return HTTP 200 immediately after receiving the target.
- Predictions are returned by email to the results address provided in the
  target submission.
- Up to five models can be returned; model 1 drives aggregate comparison on the
  website, while models 2-5 may still be scored.
- Polymer predictions can be returned as PDB or mmCIF. CAMEO also supports
  ligand-specific formats, but ligand modeling should be out of initial scope
  until the polymer receiver and model1 path are stable.

## Product Requirements

### P0: CAMEO Receiver Scaffold

The first CAMEO implementation must be intake-only and fail-closed.

Required behavior:

- Expose HTTP POST and GET intake endpoints.
- Return HTTP 200 quickly after syntactically valid intake.
- Persist a local job record with:
  - target identifier or CAMEO submission identifier
  - received timestamp
  - request method
  - source IP or forwarded source metadata when available
  - raw request checksum
  - parsed target sequences
  - provided results email, redacted in logs
  - declared capability lane
  - status
- Keep raw request bodies local and out of committed docs.
- Never send predictions or email automatically in P0.
- Never register or mutate a CAMEO account from code.
- Provide a local dry-run fixture for receiver tests.

Non-goals:

- no public CAMEO server registration
- no automated email submission
- no native accuracy claim
- no ligand/RNA/DNA production claim
- no public uptime claim

### P0: API Import Repair

The existing API must become importable before it can host CAMEO endpoints.

Required behavior:

- Fix invalid function annotations.
- Pass `request_data` explicitly into background tasks.
- Remove fake scientific result generation or replace it with a fail-closed
  `not_implemented` status.
- Add a focused smoke test proving the API module imports and the app object is
  constructible.

Acceptance evidence as of the current foundation slice:

- `python3 -m py_compile api/main.py api/tasks.py` passes.
- A unit test imports `api.main:app` when FastAPI is installed; otherwise it is
  skipped as an API optional-dependency test.
- No endpoint writes a fake PDB as a completed scientific result.

### P0: CAMEO Model1 Selector

CAMEO aggregate comparison is model1-centered, so the product needs a
deterministic model1/top5 handoff contract before outbound email is allowed.

Required behavior:

- Score local candidates by validation status, internal source policy,
  confidence, CA continuity, clash proxy, shape proxy, and rank prior.
- Select exactly one model1 when at least one internal validation-pass candidate
  exists.
- Select up to five models for downstream CAMEO attachment ordering.
- Block external model pools from becoming internal prediction proof even if
  their proxy score is higher.
- Record `native_or_external_accuracy_used=false` and
  `outbound_email_enabled=false`.

Acceptance evidence:

- `betelgeuze_cameo/selector.py` builds a fail-closed model1/top5 packet.
- `tools/build_cameo_model1_selection_packet.py` writes JSON/CSV/MD packets.
- `tests/unit/test_betelgeuze_cameo_selector.py` verifies internal model1
  selection and external-pool blocking.

### P0: CAMEO PDB/mmCIF Format Validation

Selected CAMEO model files must pass a local coordinate-format gate before any
dry-run packaging or future outbound email handoff.

Required behavior:

- Validate selected model1/top5 rows from the selector packet by default.
- Accept PDB and mmCIF coordinate files.
- Fail closed when files are missing, empty, unsupported, atomless, or contain
  unparseable coordinate records.
- Record model count, atom count, chain count, residue count, detected format,
  blockers, and warnings.
- Enforce the CAMEO top-five model limit at the format gate.
- Record `native_or_external_accuracy_used=false` and
  `outbound_email_enabled=false`.

Acceptance evidence:

- `betelgeuze_cameo/format_validation.py` validates PDB/mmCIF model files and
  builds a packet summary without using native or external accuracy.
- `tools/build_cameo_format_validation_packet.py` writes JSON/CSV/MD packets.
- `tests/unit/test_betelgeuze_cameo_format_validation.py` verifies passing PDB,
  failing atomless PDB, passing mmCIF, selected-row behavior, and tool output.

### P0: CAMEO Dry-Run Handoff Packet

After model1/top5 selection and PDB/mmCIF validation, the next public-benchmark
readiness step is an email-disabled handoff packet. This is a dry-run attachment
manifest, not a CAMEO submission.

Required behavior:

- Require `cameo_model1_selection_ready` and `cameo_format_validation_ready`
  inputs.
- Require exactly one validated model1 attachment.
- Allow only ranks 1 through 5.
- Package attachment filename, rank, candidate id, format, path, and basic
  coordinate counts.
- Record `native_or_external_accuracy_used=false`,
  `outbound_email_enabled=false`, and `external_state_mutated=false`.
- Record the future outbound email approval token without sending email.

Acceptance evidence:

- `betelgeuze_cameo/handoff.py` builds the dry-run handoff packet and blocks
  not-ready selection or format-validation inputs.
- `tools/build_cameo_dry_run_handoff_packet.py` writes JSON/CSV/MD dry-run
  handoff packets.
- `tests/unit/test_betelgeuze_cameo_handoff.py` verifies ready packaging,
  missing model1 blocking, not-ready input blocking, and tool output.

### P0: CAMEO Official Results Intake Gate

Official CAMEO metrics must enter the validation lane with provenance before
they are used as performance evidence. This intake gate validates
operator-provided rows; it does not fetch CAMEO web pages or infer official
results from local native accuracy.

Required behavior:

- Require at least one official CAMEO result row.
- Require target id, candidate id, model rank, official source kind, source
  URL, record id, retrieval timestamp, and assessment date.
- Accept source kinds only in `official_cameo`, `cameo_official`, or
  `cameo_assessment`.
- Require the source URL to be an HTTP(S) CAMEO URL.
- Require a ready model1 official result by default.
- Require at least one official metric among lDDT, TM-score, QS-score, and
  RMSD.
- Reject local/native/template accuracy columns as validation evidence.
- Keep `native_local_accuracy_used=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/official_results.py` builds the provenance-aware official
  result intake gate.
- `tools/build_cameo_official_results_intake_gate.py` writes JSON/CSV/MD
  packets and `runs/cameo_official_results_operator_template_current.csv`.
- `tests/unit/test_betelgeuze_cameo_official_results.py` verifies missing-row
  blocking, ready official model1 provenance, and local/unproven row blocking.
- `tests/unit/test_build_cameo_official_results_intake_gate.py` verifies CLI
  output and template creation.
- `runs/cameo_official_results_intake_gate_current.json` currently reports
  `status=blocked_cameo_official_results_intake`, `result_row_count=0`,
  `accepted_official_result_count=0`, `model1_official_result_ready=false`,
  `blocker_count=2`, `native_local_accuracy_used=false`,
  `official_cameo_results_used=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`. It also records
  `required_columns=target_id,candidate_id,cameo_model_rank,result_source_kind,result_source_url,result_record_id,retrieved_at_utc,assessment_date`,
  `official_metric_columns=lddt,tm_score,qs_score,rmsd_A`, and
  `disallowed_local_accuracy_columns=native_accuracy,local_accuracy,tm_against_native,lddt_against_native,rmsd_against_native,template_accuracy`
  so operator input cannot silently substitute local/native accuracy for
  official CAMEO assessment evidence.

### P0: CAMEO Performance Scorecard

The public benchmark lane needs a local evidence ledger for official CAMEO
results. It must separate official external benchmark evidence from local native
accuracy, and it must stay model1-centered.

Required behavior:

- Read an email-disabled CAMEO dry-run handoff packet.
- Accept official CAMEO result rows after the official-results intake gate has
  validated their source/provenance fields.
- Match official results to handoff ranks 1 through 5 and require model1 for
  model1-centered validation.
- Record lDDT, TM-score, QS-score, and RMSD when present.
- Evaluate product-grade model1 thresholds from a separate threshold-policy
  artifact without using local native structures.
- Record pending status when official result rows are not available yet.
- Keep `native_local_accuracy_used=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/performance_policy.py` builds the product-grade threshold
  policy and blocks permissive placeholder thresholds.
- `betelgeuze_cameo/performance.py` builds official CAMEO performance
  scorecards, blocks non-official result sources, and records threshold
  failures.
- `tools/build_cameo_performance_threshold_policy.py` writes JSON/CSV/MD
  threshold-policy packets.
- `tools/build_cameo_performance_scorecard.py` writes JSON/CSV/MD scorecards
  from dry-run handoff, optional official result CSV, and the threshold-policy
  packet.
- `tests/unit/test_betelgeuze_cameo_performance_policy.py`,
  `tests/unit/test_build_cameo_performance_threshold_policy.py`, and
  `tests/unit/test_betelgeuze_cameo_performance.py` verify product-grade
  defaults, placeholder blocking, pending status, official model1 acceptance,
  non-official blocking, threshold failure, and tool output including
  missing-handoff fail-closed output.
- `runs/cameo_performance_threshold_policy_current.json` currently reports
  `status=cameo_performance_threshold_policy_ready`,
  `threshold_policy_ready=true`, `profile_name=product_grade_model1`,
  `min_model1_lddt=0.7`, `min_model1_tm_score=0.5`,
  `min_model1_qs_score=0.0`, `max_model1_rmsd_A=5.0`, and
  `blocker_count=0`.
- `runs/cameo_performance_scorecard_current.json` currently reports
  `status=cameo_performance_pending_official_results`, `result_row_count=0`,
  `accepted_official_result_count=0`, `model1_official_result_count=0`,
  `threshold_policy_ready=true`, `threshold_profile_name=product_grade_model1`,
  `official_cameo_results_used=false`, `native_local_accuracy_used=false`, and
  `external_state_mutated=false`.

### P0: CAMEO Validation Readiness Gate

The product needs a single local gate that says whether the CAMEO validation
lane is actually ready, pending official results, or blocked by missing
artifacts.

Required behavior:

- Read current selection, format-validation, dry-run handoff, and performance
  scorecard artifacts.
- Fail closed when any required artifact is missing.
- Accept `cameo_performance_pending_official_results` only after selection,
  format validation, and handoff are ready.
- Report `cameo_validation_evidence_ready` only when official CAMEO performance
  evidence is ready.
- Preserve `native_or_external_accuracy_used=false`,
  `native_local_accuracy_used=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/readiness.py` builds the readiness gate and blocks missing
  artifacts or claim-boundary violations.
- `tools/build_cameo_validation_readiness_gate.py` writes JSON/CSV/MD readiness
  gates from current artifact paths.
- `tests/unit/test_betelgeuze_cameo_readiness.py` verifies missing-artifact
  blocking, pending-official-results status, evidence-ready status,
  claim-boundary blocking, and tool output.
- `runs/cameo_validation_readiness_gate_current.json` currently reports
  `status=cameo_validation_pending_official_results`, `missing_stage_count=0`,
  `blocker_count=0`, `ready_stage_count=4`, and
  `performance_status=cameo_performance_pending_official_results`; official
  CAMEO result rows remain the evidence blocker.
- `runs/cameo_validation_repair_work_order_current.json` currently reports
  `status=cameo_validation_repair_not_required`, `blocked_stage_count=0`, and
  `operator_input_missing_count=0` after the local smoke-input selection,
  format-validation, dry-run handoff, performance-pending, and readiness
  artifacts were regenerated.

### P0: CAMEO Architecture Validation Contract

The product architecture validation lane must explicitly tie product-readiness
claims to official CAMEO evidence. A local protocol can be connected before
registration, but product-release validation remains blocked until official
model1 CAMEO results and registration/email approvals exist.

Required behavior:

- Read the product architecture contract, CAMEO validation operations dossier,
  validation readiness gate, performance threshold-policy packet, performance
  scorecard, official-results intake, and public-registration approval gate.
- Report `local_validation_protocol_ready=true` only when the current product
  architecture, CAMEO operations/readiness surfaces, and product-grade
  threshold policy are present.
- Report `cameo_architecture_validation_ready=true` only when official CAMEO
  evidence, model1 scorecard evidence, official-results intake, and public
  registration authorization are all present.
- Preserve `server_registration_mutated=false`,
  `prediction_generation_enabled=false`, `outbound_email_enabled=false`,
  `native_local_accuracy_used=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/architecture_validation.py` builds the contract without
  registering servers, sending email, fetching assessment pages, or substituting
  local native accuracy.
- `tools/build_cameo_architecture_validation_contract.py` writes JSON/CSV/MD
  architecture-validation packets from current local evidence artifacts.
- `api/cameo.py` exposes `/cameo/architecture-validation` as a read-only
  status surface, including official-results intake status, accepted row count,
  model1 readiness, operator template path, required official-result columns,
  metric columns, and disallowed local/native accuracy columns.
- `tests/unit/test_betelgeuze_cameo_architecture_validation.py` verifies local
  protocol readiness, threshold-policy lane readiness, official-evidence
  release readiness, and CLI output.
- `tests/unit/test_api_cameo_import.py` verifies the API route and fail-closed
  flags, including official-results handoff fields on the architecture
  validation endpoint.
- `runs/cameo_architecture_validation_contract_current.json` currently reports
  `status=blocked_cameo_architecture_validation_contract`,
  `local_validation_protocol_ready=true`,
  `cameo_architecture_validation_ready=false`, `lane_count=8`,
  `ready_lane_count=4`, `blocked_lane_count=1`,
  `approval_required_lane_count=3`,
  `performance_threshold_policy_ready=true`,
  `performance_threshold_profile_name=product_grade_model1`,
  `official_cameo_results_used=false`,
  `performance_scorecard_evidence_ready=false`, `official_results_ready=false`,
  `public_registration_authorized=false`, and
  `external_state_mutated=false`.
- `/cameo/architecture-validation` currently exposes the same official-results
  handoff with `official_results_gate_status=blocked_cameo_official_results_intake`,
  `official_results_result_row_count=0`, `official_results_accepted_count=0`,
  `official_model1_result_ready=false`, and the fillable
  `runs/cameo_official_results_operator_template_current.csv` template path.

### P0: CAMEO Operator Input Kit

The CAMEO repair lane needs fill-in templates so an operator can provide
candidate, selected-model, and official-result rows without guessing the local
CSV contracts. The kit is an input scaffold only; it is not a benchmark run.

Required behavior:

- Read the current CAMEO validation repair work order.
- Generate CSV templates for:
  - internal model1/top5 selector candidates
  - selected PDB/mmCIF model paths for format validation
  - official CAMEO assessment metrics after results are available
- Use `OPERATOR_FILL_*` placeholder values so accidental direct execution stays
  blocked rather than looking like valid evidence.
- Write a manifest and README that map each template to the downstream repair
  command argument.
- Preserve `action_executed=false`, `outbound_email_enabled=false`,
  `external_state_mutated=false`, and `native_local_accuracy_used=false`.

Acceptance evidence:

- `tools/build_cameo_operator_input_kit.py` writes template CSV files plus
  `manifest.json`, `manifest.csv`, and `README.md`.
- `tests/unit/test_build_cameo_operator_input_kit.py` verifies ready, blocked,
  and CLI output states.
- `runs/cameo_operator_input_kit_current/manifest.json` currently reports
  `status=cameo_operator_input_kit_ready`, `template_count=3`,
  `required_template_count=3`, and keeps all execution/email/external-state
  flags disabled.

### P0: CAMEO Operator Input Validation

Filled CAMEO operator CSVs must be checked before local artifact rebuild
commands are run. The validation gate blocks placeholder rows, unsupported
source kinds, missing model files, non-official CAMEO result sources, and local
native-accuracy evidence.

Required behavior:

- Read candidate, selected-model, and optional official-result CSV inputs.
- Require candidate rows to use internal prediction sources and
  `validation_status=pass`.
- Require selected model rows to have ranks 1 through 5, exactly one model1
  rank, and local PDB/mmCIF paths that exist.
- Accept official-result rows only when `result_source_kind` is an official
  CAMEO assessment source.
- Block `OPERATOR_FILL_*` placeholders before any artifact rebuild command.
- Preserve `action_executed=false`, `outbound_email_enabled=false`,
  `external_state_mutated=false`, and `native_local_accuracy_used=false`.

Acceptance evidence:

- `betelgeuze_cameo/operator_inputs.py` validates filled CAMEO operator CSV
  rows without executing selection, format validation, handoff, or performance
  commands.
- `tools/build_cameo_operator_input_validation.py` writes JSON/CSV/MD validation
  packets.
- `tests/unit/test_betelgeuze_cameo_operator_inputs.py` verifies filled-input
  readiness, placeholder blocking, and non-official result blocking.
- `tests/unit/test_build_cameo_operator_input_validation.py` verifies CLI
  output.
- `runs/cameo_operator_input_validation_current.json` currently reports
  `status=cameo_operator_inputs_ready_pending_official_results`,
  `blocker_count=0`, `candidate_row_count=1`, `model_row_count=1`, and
  `official_result_row_count=0` against the synthetic
  `cameo_dry_run` format-smoke input. It keeps
  `native_local_accuracy_used=false`, `outbound_email_enabled=false`, and
  leaves official performance evidence pending.

### P0: CAMEO Repair Execution Preflight

The CAMEO repair lane needs one more local gate between validated operator
inputs and artifact rebuild commands. This preflight checks the repair
work-order command rows and input-validation state, but it does not run the
commands.

Required behavior:

- Read the current CAMEO validation repair work order and operator input
  validation artifact.
- Require the repair work order to be ready before local rebuild commands can
  be marked runnable.
- Require operator input validation to be ready before selection, format,
  handoff, or performance rebuild commands can be marked runnable.
- Block any command row that still contains `OPERATOR_FILL_*` placeholders.
- Preserve `action_executed=false`, `outbound_email_enabled=false`,
  `external_state_mutated=false`, and `native_local_accuracy_used=false`.

Acceptance evidence:

- `betelgeuze_cameo/repair_preflight.py` validates the repair command sequence
  without executing selection, format validation, dry-run handoff, or
  performance scoring.
- `tools/build_cameo_repair_execution_preflight.py` writes JSON/CSV/MD preflight
  packets.
- `tests/unit/test_betelgeuze_cameo_repair_preflight.py` verifies ready command
  rows, placeholder blocking, and input-validation blocking.
- `tests/unit/test_build_cameo_repair_execution_preflight.py` verifies CLI
  output.
- `runs/cameo_repair_execution_preflight_current.json` currently reports
  `status=cameo_repair_execution_not_required`, `blocker_count=0`, and
  `input_blocker_count=0` because the local selection, format validation,
  dry-run handoff, and readiness artifacts are already regenerated from the
  filled smoke inputs. It still keeps execution disabled and does not run any
  repair command.

### P0: CAMEO Capability Policy

The first registered-capability design should be conservative.

Recommended initial capability:

- development server only
- protein/polymer complex receiver only
- no ligand production modeling
- no RNA/DNA production modeling until explicit support exists
- model1 selection required before any outbound prediction path

Policy:

- External/template/model-pool inputs must be separated from internal prediction
  proof.
- CASP17 MassiveFold and other external model pools may support review-only
  selector calibration, but must not become internal proof.
- Any registered CAMEO server must have an explicit operator approval gate.

### P0: CAMEO API Dependency Readiness

CAMEO receiver runtime smoke depends on the optional API server profile. This
readiness packet records whether that profile is importable without installing
or changing the environment.

Required behavior:

- Read `requirements-api.txt`.
- Check declared API profile imports such as `fastapi`, `uvicorn`, and
  `pydantic_settings`.
- Check the runtime smoke extra import `fastapi.testclient`.
- Preserve `package_install_executed=false`, `server_started=false`,
  `outbound_email_enabled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/api_dependency.py` builds the API dependency readiness
  contract.
- `tools/build_cameo_api_dependency_readiness.py` writes JSON/CSV/MD readiness
  packets.
- `tests/unit/test_betelgeuze_cameo_api_dependency.py` verifies blocked,
  ready, and missing-requirements states.
- `tests/unit/test_build_cameo_api_dependency_readiness.py` verifies CLI
  output.
- `runs/cameo_api_dependency_readiness_current.json` currently reports
  `status=blocked_cameo_api_dependency_readiness`,
  `declared_dependency_count=3`, `runtime_extra_count=1`,
  `missing_or_unimportable_count=4`, and
  `missing_or_unimportable=fastapi,uvicorn[standard],pydantic-settings,fastapi.testclient`.

### P0: CAMEO Runtime Repair Work Order

When the receiver smoke is blocked by missing API dependencies, the repair path
must be explicit, reviewable, and approval-gated. The runtime repair work order
records the package activation command and local smoke refresh commands without
executing them.

Required behavior:

- Read CAMEO API dependency readiness, receiver smoke, and capability preflight
  artifacts.
- Record an `approval_required` API dependency install or activation command
  only when API dependency readiness is blocked.
- Require `APPROVE_API_DEPENDENCY_INSTALL` before any package installation can
  be executed by an operator.
- Record local rerun commands for API dependency readiness, receiver smoke,
  capability preflight, goal rollup, and operator action board refresh.
- Preserve `package_install_executed=false`, `server_started=false`,
  `prediction_generation_enabled=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cameo_runtime_repair_work_order.py` writes JSON/CSV/MD runtime
  repair work orders without installing packages or starting a server.
- `tests/unit/test_build_cameo_runtime_repair_work_order.py` verifies the
  approval-gated install command, ready dependency profile behavior, and CLI
  output.
- `runs/cameo_runtime_repair_work_order_current.json` currently reports
  `status=cameo_runtime_repair_work_order_ready`,
  `source_api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `source_receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `source_capability_preflight_status=blocked_cameo_capability_preflight`,
  `missing_or_unimportable_count=4`, `install_approval_required=true`,
  `approval_token_required=APPROVE_API_DEPENDENCY_INSTALL`,
  `command_count=5`, `approval_required_command_count=1`,
  `package_install_executed=false`, `server_started=false`, and
  `external_state_mutated=false`.

### P0: CAMEO Validation Operations Dossier

The transition needs one CAMEO operations surface that tells an operator what
is blocked before any server registration, outbound email, or public prediction
submission is considered. The operations dossier consolidates the current
CAMEO input, validation, runtime, and capability artifacts without producing
new scientific evidence.

Required behavior:

- Read CAMEO operator input kit, operator input validation, repair execution
  preflight, validation readiness, official-results intake gate, runtime repair
  work order, API dependency readiness, receiver smoke, and capability preflight
  artifacts.
- Surface blocked stages for operator CSVs, repair command preflight,
  official-results intake, validation evidence, receiver smoke, and public
  registration/email.
- Require official CAMEO result evidence before marking validation ready.
- Surface `APPROVE_API_DEPENDENCY_INSTALL`,
  `APPROVE_CAMEO_SERVER_REGISTRATION`, and
  `APPROVE_CAMEO_OUTBOUND_EMAIL` as separate operator tokens.
- Expose the same token set plus official-results row counts, model1 official
  result readiness, API dependency approval, receiver-smoke status, and
  registration/email authorization state through the read-only CAMEO CLI
  all-status surface.
- Preserve `package_install_executed=false`, `server_started=false`,
  `server_registration_mutated=false`, `prediction_generation_enabled=false`,
  `outbound_email_enabled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cameo_validation_operations_dossier.py` writes JSON/CSV/MD
  CAMEO operations dossiers without executing runtime, registration, email, or
  prediction actions.
- `tests/unit/test_build_cameo_validation_operations_dossier.py` verifies
  blocked current-lane consolidation, approval-required registration behavior,
  and CLI output.
- `runs/cameo_validation_operations_dossier_current.json` currently reports
  `status=blocked_cameo_validation_operations_dossier`,
  `stage_count=6`, `blocked_stage_count=2`,
  `approval_required_stage_count=1`, `operator_input_required_count=0`,
  `approval_token_count=3`, `official_result_required=true`,
  `official_results_intake_status=blocked_cameo_official_results_intake`,
  `official_results_intake_ready=false`,
  `official_results_intake_blocker_count=2`,
  `official_model1_result_ready=false`,
  `public_registration_allowed=false`, `package_install_executed=false`,
  `server_registration_mutated=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.
- `betelgeuze_cameo/cli.py` all-status currently reports
  `status=blocked_cameo_cli_status_set`, `command_count=11`,
  `blocked_or_missing_command_count=7`, `approval_token_count=3`,
  `approval_tokens_required=APPROVE_API_DEPENDENCY_INSTALL,APPROVE_CAMEO_OUTBOUND_EMAIL,APPROVE_CAMEO_SERVER_REGISTRATION`,
  `official_result_required=true`, `official_results_result_row_count=0`,
  `official_results_accepted_count=0`, `official_model1_result_ready=false`,
  `api_install_approval_required=true`,
  `api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `public_registration_authorized=false`, and
  `registration_awaiting_operator_approval_row_count=1`.

### P0: CAMEO Receiver Smoke Contract

Development server readiness needs more than a static route check. The receiver
smoke contract keeps this local and fail-closed: it checks source route presence
and, when API dependencies are installed, uses FastAPI `TestClient` to verify a
POST 200 response plus local fail-closed ledger persistence.

Required behavior:

- Verify `api.main` includes the CAMEO router and `api.cameo` declares
  `/cameo/targets`.
- Read CAMEO API dependency readiness when present and skip runtime smoke until
  that dependency profile is ready.
- Run local TestClient POST smoke only when the API dependency set is present.
- Persist exactly one local smoke ledger record when runtime smoke runs.
- Require `prediction_generation_enabled=false` and
  `outbound_email_enabled=false` in the smoke ledger.
- Never start a public server, register CAMEO, submit predictions, send email,
  or mutate external state.

Acceptance evidence:

- `betelgeuze_cameo/receiver_smoke.py` builds the receiver smoke contract.
- `tools/build_cameo_receiver_smoke_contract.py` writes JSON/CSV/MD smoke
  packets.
- `tests/unit/test_betelgeuze_cameo_receiver_smoke.py` verifies runtime-pass,
  runtime-dependency-blocked, and static-only states.
- `tests/unit/test_build_cameo_receiver_smoke_contract.py` verifies CLI output.
- `runs/cameo_receiver_smoke_contract_current.json` currently reports
  `status=blocked_cameo_receiver_smoke`, `source_route_present=true`,
  `source_api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `api_dependency_ready=false`, `api_dependency_blocker_count=4`,
  `runtime_dependency_present=false`, `post_200_ok=false`,
  `ledger_written=false`, and `external_state_mutated=false`.

### P0: CAMEO Capability Preflight

The receiver scaffold can be inspected locally before public CAMEO registration,
but public server registration, prediction generation, and outbound email must
stay blocked until benchmark evidence and explicit approvals are present.

Required behavior:

- Verify the local receiver scaffold, `/cameo/targets` route registration, and
  read-only `/cameo/operations`, `/cameo/architecture-validation`,
  `/cameo/official-results`, and `/cameo/registration-approval` status routes.
- Read the receiver smoke contract when present and require runtime receiver
  smoke before development server readiness.
- Restrict the current development capability lane to
  `polymer_complex_receiver_dry_run`.
- Require `cameo_validation_evidence_ready` before public registration is
  allowed.
- Require `cameo_repair_execution_preflight_ready` before public registration
  is allowed.
- Require explicit `APPROVE_CAMEO_SERVER_REGISTRATION` and
  `APPROVE_CAMEO_OUTBOUND_EMAIL` tokens before public registration is allowed.
- Keep `outbound_email_enabled=false`, `prediction_generation_enabled=false`,
  `server_registration_mutated=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_cameo/capability_preflight.py` builds the fail-closed capability
  preflight contract.
- `tools/build_cameo_capability_preflight.py` writes JSON/CSV/MD preflight
  packets.
- `tests/unit/test_betelgeuze_cameo_capability_preflight.py` verifies
  development receiver readiness, blocked public-registration requests,
  receiver-smoke blocking, approval-ready public-registration preflight, and
  unsafe flag blocking.
- `tests/unit/test_build_cameo_capability_preflight.py` verifies CLI output and
  missing architecture-validation route blocking.
- `runs/cameo_capability_preflight_current.json` currently reports
  `status=blocked_cameo_capability_preflight`,
  `api_route_registered=true`, `api_operations_route_registered=true`,
  `source_api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `api_dependency_ready=false`, `api_dependency_blocker_count=4`,
  `source_receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `receiver_smoke_post_200_ok=false`,
  `receiver_smoke_blocker_count=1`,
  `public_registration_allowed=false`,
  `public_registration_blocker_count=4`, `outbound_email_enabled=false`,
  `prediction_generation_enabled=false`, and
  `server_registration_mutated=false`.

### P0: CAMEO Public Registration Approval Gate

Public CAMEO registration and result-email behavior require a separate
operator intake even after receiver smoke and official CAMEO validation evidence
are ready. This gate validates the endpoint, result/contact email metadata, and
registration/email approval tokens without registering a server or sending
email.

Required behavior:

- Read CAMEO capability preflight and CAMEO validation operations dossier.
- Require capability preflight to be public-registration ready.
- Require official CAMEO validation evidence and receiver smoke readiness.
- Write a fillable operator approval template with endpoint URL, results email,
  contact email, registration token, and outbound-email token fields.
- Require exact `APPROVE_CAMEO_SERVER_REGISTRATION` and
  `APPROVE_CAMEO_OUTBOUND_EMAIL` tokens before marking a row authorized for a
  separate registration review.
- Validate public endpoint URL and result/contact email shapes.
- Preserve `server_registration_mutated=false`, `outbound_email_enabled=false`,
  `prediction_generation_enabled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cameo_public_registration_approval_gate.py` writes JSON/CSV/MD
  public registration approval gates and a fillable template without
  registering or sending email.
- `api/cameo.py` exposes `/cameo/registration-approval` and the
  `/cameo/operations` registration fields as read-only operator surfaces for
  the registration template path, intake path, required columns, valid
  decisions, registration token, and outbound-email token.
- `tests/unit/test_build_cameo_public_registration_approval_gate.py` verifies
  current blocked state, separate-review authorization, bad metadata/token
  blocking, and CLI/template output.
- `tests/unit/test_api_cameo_import.py tests/unit/test_api_casp17_import.py` verifies the registration-approval API
  route and that it preserves `server_registration_mutated=false`,
  `outbound_email_enabled=false`, `prediction_generation_enabled=false`, and
  `external_state_mutated=false`.
- `runs/cameo_public_registration_approval_gate_current.json` currently reports
  `status=blocked_cameo_public_registration_approval_gate`,
  `capability_public_registration_ready=false`,
  `official_cameo_validation_evidence_ready=false`,
  `receiver_smoke_ready=false`, `operator_approval_csv_present=false`,
  `authorized_for_registration_review=false`, `blocked_row_count=1`,
  `blocker_count=5`, and blockers
  `cameo_capability_public_registration_not_ready,cameo_receiver_smoke_not_ready,official_cameo_validation_evidence_not_ready,operator_approval_csv_missing,operator_decision_missing`.
  It records `server_registration_mutated=false`, `outbound_email_enabled=false`,
  and `external_state_mutated=false`, and writes
  `runs/cameo_public_registration_operator_approval_template_current.csv`.

### P0: CASP17 Transition Surface Contract

CASP17 remains useful as a historical/current competition workbench, but the
new product direction should not depend on hidden CASP17 upload state. CASP17
upload and transition state need a read-only API surface that exposes current
operator-decision blockers, stale generated-folder locks, and cleanup context
without submitting to CASP or deleting anything.

Required behavior:

- Expose `/casp17/upload` and `/casp17/transition` as read-only status routes.
- Register the CASP17 router in `api/main.py`.
- Read current upload decision-rule, operator-action runway, and active
  manifest-lock artifacts.
- Surface stale generated folders as read-only until cleanup policy/approval
  explicitly promotes them.
- Surface large cleanup drilldown, protected cleanup review context, cleanup
  execution approval gate, cleanup postcheck contract, and cleanup completion
  gate state.
- Preserve `upload_executed=false`, `delete_executed=false`,
  `native_accuracy_computed=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `api/casp17.py` exposes the read-only CASP17 upload and transition routes;
  `/casp17/transition` also reports cleanup approval, postcheck, and completion
  gate state without promoting cleanup execution.
- `tools/build_casp17_transition_surface_contract.py` writes JSON/CSV/MD
  CASP17 transition surface contracts without uploading or cleanup execution.
- `tests/unit/test_api_casp17_import.py` verifies FastAPI route registration
  and current blocked/read-only CASP17 responses, including cleanup
  approval/postcheck/completion fields, when FastAPI is installed.
- `tests/unit/test_build_casp17_transition_surface_contract.py` verifies ready
  surface detection, unmounted-router blocking, CLI output, and disabled
  upload/delete/native-accuracy/external-mutation flags.
- `casp17/casp17_transition_surface_contract_current.json` currently reports
  `status=casp17_transition_surface_contract_ready`, `surface_ready=true`,
  `check_count=8`, `casp17_upload_endpoint_present=true`,
  `casp17_transition_endpoint_present=true`,
  `casp17_upload_artifacts_referenced=true`,
  `casp17_cleanup_artifacts_referenced=true`,
  `casp17_cleanup_gate_artifacts_referenced=true`,
  `casp17_fail_closed_flags_present=true`, `upload_executed=false`,
  `delete_executed=false`, `native_accuracy_computed=false`, and
  `external_state_mutated=false`.
- `/casp17/upload` currently reports 8 active current-upload rows awaiting
  operator decisions, 0 runtime-upload-ready rows, and 38 stale generated
  folders locked read-only by the active-manifest lock.
- `/casp17/transition` currently reports
  `cleanup_execution_approval_gate_status=blocked_cleanup_execution_operator_approval_gate`,
  `cleanup_execution_awaiting_operator_approval_row_count=5`,
  `cleanup_execution_authorized_reclaim_size_gb=0.0`,
  `cleanup_execution_total_reclaim_size_gb=49.216`,
  `cleanup_postcheck_contract_ready=true`, `cleanup_postcheck_row_count=7`,
  `cleanup_postcheck_blocked_row_count=0`,
  `cleanup_completion_gate_status=blocked_cleanup_completion_gate`,
  `cleanup_completion_complete=false`, `cleanup_completion_blocked_stage_count=4`,
  and disabled upload/delete/external-mutation flags.

### P0: Transition Cleanup Manifest

Cleanup must be manifest-first.

Required behavior:

- Build a transition manifest with `keep`, `archive`, `externalize`, and
  `delete_candidate` actions.
- Include size, path, sha256 or directory hash strategy, reason, and protection
  status.
- Dry-run only until operator approval.
- Keep final PDB/mmCIF, top representatives, validation reports, manifests,
  viewer indexes, source code, and tests.
- Candidate heavy targets include:
  - `casp17/massivefold_external_pool_intake`
  - `runs/archive`
  - repeated trajectory frame directories
  - config-referenced `ligand_heavy_runs` roots
  - `rust_engine/target`
  - local virtual environments
- Config-referenced ligand-heavy roots must be review-only at the transition
  manifest level. Stale payload deletion planning belongs to
  `tools/cleanup_ligand_heavy_runs.py` dry-run output, which targets only known
  heavy payload directories after explicit approval.

Non-goal:

- no deletion, staging, commit, push, upload, or external archival without
  explicit operator approval.

Current dry-run evidence:

- `runs/transition_cleanup_manifest_current.json` records
  `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs` as a
  config-referenced ligand-heavy root with `size_gb=402.806` and
  `recommended_action=review_for_ligand_heavy_payload_cleanup`.
- `runs/transition_cleanup_work_order_current.json` converts the manifest into
  an approval-gated work order with `approval_gated_count=4`,
  `approval_gated_reclaim_size_gb=43.206`, `review_only_count=4`,
  `delete_enabled=false`, `action_executed=false`, and
  `external_state_mutated=false`.
- `runs/transition_cleanup_execution_preflight_current.json` validates those
  transition cleanup rows without deleting, moving, archiving, or externalizing
  anything. It currently reports
  `status=transition_cleanup_execution_preflight_ready`,
  `approval_gated_count=4`, `review_only_count=4`, `missing_noop_count=1`,
  `approval_gated_reclaim_size_gb=43.206`, and `blocker_count=0`.
- `runs/ligand_heavy_runs_cleanup_transition_dry_run_current.json` reports
  `planned_delete_count=40`, `planned_delete_bytes=6453908480`,
  `deleted_count=0`, and `execute=false`.
- `runs/ligand_heavy_cleanup_approval_packet_current.json` converts those
  dry-run candidates into an approval packet with `candidate_count=40`,
  `candidate_size_gb=6.011`, `delete_executed=false`, and required token
  `APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS`.
- `runs/ligand_heavy_cleanup_work_order_current.json` records the approval-gated
  execute command for those 40 payload directories with `delete_enabled=false`,
  `delete_executed=false`, `external_state_mutated=false`, and
  `candidate_size_gb=6.011`.
- `runs/large_cleanup_surface_drilldown_current.json` narrows the two large
  review-only surfaces into 247 rows. It currently reports
  `known_payload_row_count=43`, `known_payload_total_size_gb=406.131`,
  `dry_run_delete_payload_row_count=40`,
  `dry_run_delete_payload_size_gb=6.012`,
  `dry_run_protected_payload_row_count=2`, and
  `dry_run_protected_payload_size_gb=396.794`. The largest known payload is
  protected by the current ligand-heavy dry-run as `kept_recent_slot`, so it is
  not promoted to deletion approval without a separate operator policy change.
- `runs/protected_cleanup_payload_review_current.json` separately records those
  protected payload rows with `protected_payload_row_count=2`,
  `protected_payload_size_gb=396.794`,
  `large_protected_payload_row_count=1`,
  `large_protected_payload_size_gb=396.794`,
  `policy_change_required_count=2`, and `approval_promoted_count=0`.
- `runs/ligand_heavy_cleanup_execution_preflight_current.json` verifies the
  approval-gated execute command and all 40 payload-directory candidates without
  deleting anything. It currently reports
  `status=ligand_heavy_cleanup_execution_preflight_ready`,
  `existing_candidate_count=40`, `candidate_size_gb=6.011`,
  `blocker_count=0`, and `delete_executed=false`.

### P0: B2B Local-Delivery Pilot Packet

The commercial lane should package what is already claim-safe.

Required behavior:

- Keep the pilot scope restricted to `kinase,gpcr,ion_channel`.
- Use the existing local delivery bundle builder and validator, but keep the
  product-specific pilot packet in preflight state until the approved bundle is
  assembled and validator evidence exists.
- State that outputs are guarded validation artifacts, not broad platform
  commercialization proof.
- Include wetlab triage handoff only where current gates allow it.
- Avoid transporter, CA2/PXR, broad IDP, broad all-atom, and unattended
  decision-making claims.

Acceptance evidence:

- `betelgeuze_product/pilot_packet.py` reconciles product readiness, execution
  preflight, bundle contract, delivery evidence, and optional final bundle
  validator evidence.
- `tools/build_product_pilot_packet_contract.py` writes JSON/CSV/MD pilot
  packet contracts without running docking, assembling bundles, validating
  bundles, or emitting customer wording.
- `tests/unit/test_betelgeuze_product_pilot_packet.py` verifies preflight-ready
  state before assembly, final ready state after claim + validator pass, and
  blocking when delivery-ready claims appear without final bundle validation.
- `tests/unit/test_build_product_pilot_packet_contract.py` verifies CLI output.
- `runs/product_pilot_packet_contract_current.json` currently reports
  `status=product_pilot_packet_preflight_ready`,
  `pilot_delivery_ready=false`, `operator_approval_required=true`,
  `bundle_validation_present=false`, and `bundle_validation_passed=false`.

### P0: Commercial Docking Request Contract

The product surface must separate request intake from scientific execution until
the internal production pipeline is wired and current local-delivery gates are
green.

Required behavior:

- Accept molecular structure analysis plus ligand docking requests through a
  stable contract.
- Restrict initial commercial request scope to `kinase`, `gpcr`, and
  `ion_channel`.
- Require exactly one structure source: `pdb_id`, `pdb_path`, `pdb_content`,
  `mmcif_path`, or `mmcif_content`.
- Require at least one ligand row and a ligand source per row, such as `smiles`,
  `sdf_path`, `mol2_path`, `pdbqt_path`, `inchi`, or `compound_id`.
- Reject duplicate ligand ids and unsupported scope widening.
- Persist local ledger records with request checksum, validation result, scope,
  ligand count, and heavy-artifact policy.
- Keep `execution_enabled=false`, `docking_results_emitted=false`, and
  `external_state_mutated=false` until pipeline wiring and operator gates are
  explicit.

Acceptance evidence:

- `betelgeuze_product/docking_request.py` validates commercial docking request
  contracts and writes local fail-closed ledger records.
- `api/product.py` exposes `/product/capabilities`, `/product/operations`,
  `/product/license-decision`, `/product/license-options`,
  `/product/commercial-independence`, `/product/release-readiness`, and
  `/product/docking/jobs` POST/GET for product capability/readiness, operations
  status, operations stages, approval-token handoff, license-decision handoff,
  commercial-independence status, release-readiness status, and request intake
  without emitting fake docking results.
- `tests/unit/test_betelgeuze_product_docking_request.py` verifies allowed
  restricted-scope intake, scope-widening blocks, duplicate-ligand blocks,
  multiple-structure-source blocks, and ledger persistence.

### P0: Product Readiness Gate

The product lane needs a gate that joins request intake with current
local-delivery evidence before any execution work order or bundle assembly.

Required behavior:

- Accept a commercial docking request JSON or fail-closed job record.
- Reuse the docking request contract and local-delivery verdict gate evidence.
- Require `delivery_ready=true`, `verdict=delivery_ready`, zero P0/hard
  blockers, and fingerprinted local-delivery source artifacts.
- Preserve the restricted `kinase,gpcr,ion_channel` scope.
- Keep `execution_enabled=false`, `docking_results_emitted=false`, and
  `external_state_mutated=false`.
- Record the future execution approval token without running docking.

Acceptance evidence:

- `betelgeuze_product/readiness.py` builds a product readiness gate from a
  request and local-delivery verdict evidence.
- `tools/build_product_readiness_gate.py` writes JSON/MD readiness packets.
- `tests/unit/test_betelgeuze_product_readiness.py` verifies green request +
  verdict readiness, request/verdict blocking, fingerprint blocking, and tool
  output.
- `runs/product_readiness_gate_current.json` currently reports
  `status=product_handoff_ready` for a GPCR sample request while
  `execution_enabled=false`.

### P0: Product Architecture Contract

The product needs an architecture-level contract that shows the commercial
molecular-structure analysis and ligand-docking tool surface, the CAMEO
validation route, the CASP17 transition surface, and cleanup controls in one
fail-closed evidence packet.

Required behavior:

- Read product capability, product release, commercial-independence, CAMEO
  capability, CAMEO architecture-validation, product service-boundary, product
  API-contract, cleanup operations, cleanup approval, ligand-heavy cleanup, and
  CASP17 transition artifacts.
- Treat molecular-structure analysis and ligand docking as locally connected
  only when the request contract, execution preflight, HTVS command renderer,
  local pipeline entrypoint, and `/product/architecture` API surface exist.
- Treat the product service boundary as locally connected only when the
  service-boundary contract is ready, `/product/service-boundary` exists, and
  the product CLI/API/artifact registry agree on expected status surfaces.
- Treat the product API contract as locally connected only when
  `runs/product_api_contract_current.json` is ready and `/product/api-contract`
  exists.
- Treat CAMEO architecture validation as blocked or approval-gated until the
  CAMEO architecture-validation contract has official CAMEO evidence and public
  registration/email authorization.
- Treat ligand-heavy cleanup as approval-gated until exact cleanup approval is
  present, even when work order and preflight are ready.
- Preserve `execution_enabled=false`, `docking_results_emitted=false`,
  `cameo_submission_executed=false`, `casp_submission_executed=false`,
  `cleanup_executed=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/architecture.py` builds the product architecture
  contract from local evidence.
- `tools/build_product_architecture_contract.py` writes JSON/CSV/MD
  architecture packets without running docking, submitting predictions, or
  executing cleanup.
- `api/product.py` exposes `/product/architecture` as a read-only status
  surface and `/product/service-boundary` as the service-boundary status
  surface, plus `/product/api-contract` as the API-contract status surface.
- `betelgeuze_product/service_boundary.py` and
  `tools/build_product_service_boundary_contract.py` verify API routes, CLI
  command registry, artifact registry paths, and `betelgeuze-product` console
  script metadata.
- `betelgeuze_product/api_contract.py` and
  `tools/build_product_api_contract.py` verify product API route declarations,
  request model fields, docking response keys, read-only status safety flags,
  endpoint-specific architecture/release-operations domain keys, and
  commercial/release license-decision handoff keys.
- `tests/unit/test_build_product_architecture_contract.py` verifies local
  architecture readiness, service-boundary readiness, API-contract readiness,
  cleanup-postcheck propagation, approval-required lanes, token propagation,
  and disabled execution/submission/cleanup flags.
- `tests/unit/test_betelgeuze_product_service_boundary.py` and
  `tests/unit/test_build_product_service_boundary_contract.py` verify ready
  service-boundary contracts, missing-route blocking, and JSON/CSV/MD output.
- `tests/unit/test_betelgeuze_product_api_contract.py` and
  `tests/unit/test_build_product_api_contract.py` verify ready API contracts,
  missing-route/domain-key blocking, commercial license-handoff key blocking,
  and JSON/CSV/MD output.
- `runs/product_architecture_contract_current.json` currently reports
  `status=blocked_product_architecture_contract`,
  `local_architecture_surface_ready=true`,
  `architecture_release_ready=false`, `lane_count=11`,
  `ready_lane_count=8`, `blocked_lane_count=1`,
  `approval_required_lane_count=2`,
  `structure_analysis_product_surface_ready=true`,
  `ligand_docking_execution_contract_ready=true`,
  `product_service_boundary_ready=true`,
  `product_api_contract_ready=true`,
  `commercial_independence_ready=false`,
  `cameo_local_surface_ready=true`,
  `cameo_architecture_validation_protocol_ready=true`,
  `cameo_architecture_validation_ready=false`,
  `cleanup_control_surface_ready=true`,
  `cleanup_postcheck_contract_ready=true`,
  `cleanup_postcheck_row_count=7`,
  `cleanup_postcheck_blocked_row_count=0`,
  `cleanup_postcheck_global_refresh_command_count=9`,
  `ligand_heavy_cleanup_preflight_ready=true`,
  `casp17_transition_surface_ready=true`,
  `cleanup_execution_approved=false`, and
  `cleanup_reclaim_size_gb=49.216`.
- `runs/product_service_boundary_contract_current.json` currently reports
  `status=product_service_boundary_contract_ready`,
  `service_boundary_ready=true`, `check_count=4`, `pass_count=4`,
  `blocker_count=0`, `api_route_count=12`, `expected_api_route_count=12`,
  `cli_command_count=9`, `expected_cli_command_count=9`,
  `artifact_registry_mismatch_count=0`, and `console_script_ready=true`.
- `runs/product_api_contract_current.json` currently reports
  `status=product_api_contract_ready`, `api_contract_ready=true`,
  `check_count=5`, `pass_count=5`, `blocker_count=0`,
  `expected_route_count=12`, `missing_route_count=0`,
  `request_model_count=3`, `missing_request_model_field_count=0`,
  `docking_response_missing_key_count=0`,
  `status_response_missing_key_count=0`,
  `status_response_domain_missing_key_count=0`, `server_started=false`, and
  `external_state_mutated=false`.

### P0: Product Capability Surface Contract

The commercial product lane needs one explicit surface that says which parts of
the molecular-structure analysis and ligand-docking product are contract-ready,
and which parts remain gated by execution approval and final bundle validation.

Required behavior:

- Read product readiness, execution work order, execution preflight, bundle
  contract, delivery evidence, and pilot packet artifacts.
- Treat molecular-structure analysis intake as ready only when the request
  contract is passing for a restricted target family with a stable target id.
- Expose a local structure-analysis API endpoint that parses supplied PDB/mmCIF
  content or local files for atom, chain, residue, water, and ligand-like HETATM
  summaries without fetching structures or running docking.
- Treat ligand docking as ready only when ligand intake is bounded and the
  execution command contract is parser-checked with config evidence.
- Require API, structure-analysis endpoint, product capability endpoint,
  product architecture endpoint, product service-boundary endpoint, product
  API-contract endpoint, product operations endpoint, product license-decision endpoint,
  commercial-independence endpoint, release-readiness endpoint, package
  surfaces, and a read-only local product CLI to exist.
- Require local-delivery bundle, delivery-evidence, and pilot packet contracts
  to be present before the product surface is considered complete.
- Preserve `execution_enabled=false`, `docking_results_emitted=false`,
  `delivery_ready_claim_allowed=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/capability_surface.py` builds the fail-closed product
  capability surface contract from local artifacts.
- `betelgeuze_product/structure_analysis.py` parses local PDB/mmCIF structure
  sources and keeps execution/results/external mutation disabled.
- `betelgeuze_product/structure_report.py` and
  `tools/build_product_structure_analysis_report.py` produce
  `runs/product_structure_analysis_report_current.json` from local
  `config/real_drug_targets_blind_gpcr_adrb2_v1.csv` target-native evidence.
- `api/product.py` exposes `/product/structure/analyze` and links structure
  analysis summaries into docking-job ledger responses without emitting docking
  results.
- `tools/build_product_capability_surface_contract.py` writes JSON/CSV/MD
  capability surface packets without running docking or generating results.
- `betelgeuze_product/cli.py` exposes read-only local JSON status commands for
  capabilities, architecture, service-boundary, API-contract, operations,
  commercial-independence, license-decision, license-options,
  release-readiness, and all-status without running docking, writing licenses,
  assembling bundles, or mutating external state; all-status aggregates
  `approval_tokens_required`, `approval_token_count`, operations stage counts,
  capability/API readiness, architecture release readiness, license/execution
  authorization, bundle validation, delivery-ready claim, and pilot-delivery
  state for local operator handoff.
- `tests/unit/test_betelgeuze_product_structure_analysis.py` verifies PDB and
  mmCIF summaries, PDB ID reference recording without fetching, and missing-file
  blocking.
- `tests/unit/test_betelgeuze_product_structure_report.py` verifies target-native
  CSV resolution, local PDB parsing, missing-target blocking, and CLI outputs.
- `tests/unit/test_betelgeuze_product_capability_surface.py` verifies the ready
  guarded product surface and failed request-contract blocking.
- `tests/unit/test_betelgeuze_product_cli.py` verifies read-only CLI status
  JSON, missing-artifact blocking, all-status approval-token/stage aggregation,
  and disabled execution/results/license/bundle/external-mutation flags.
- `tests/unit/test_build_product_capability_surface_contract.py` verifies CLI
  output.
- `runs/product_capability_surface_contract_current.json` currently reports
  `status=product_capability_surface_contract_ready`,
  `capability_count=7`, `ready_capability_count=7`,
  `blocked_capability_count=0`,
  `structure_analysis_capability_ready=true`,
  `product_structure_analysis_report_ready=true`,
  `product_structure_analysis_atom_count=3804`,
  `product_structure_analysis_ligand_like_residue_count=17`,
  `ligand_docking_capability_ready=true`, `api_surface_ready=true`,
  `product_structure_analysis_endpoint_present=true`,
  `product_capability_endpoint_present=true`,
  `product_architecture_endpoint_present=true`,
  `product_service_boundary_endpoint_present=true`,
  `product_api_contract_endpoint_present=true`,
  `product_operations_endpoint_present=true`,
  `product_license_decision_endpoint_present=true`,
  `product_commercial_independence_endpoint_present=true`,
  `product_release_readiness_endpoint_present=true`,
  `product_cli_surface_present=true`,
  `guarded_claims_ready=true`,
  `execution_enabled=false`, `docking_results_emitted=false`,
  `delivery_ready_claim_allowed=false`, and `external_state_mutated=false`.

### P0: Product Execution Work Order

Once a product request reaches `product_handoff_ready`, execution still needs an
operator-reviewed work order. This step records the intended command, config,
future artifact paths, bundle command, and validator command without executing
anything.

Required behavior:

- Require `product_handoff_ready` readiness evidence.
- Require an operator-reviewed run command, or generate one from a
  config/profile JSON by mapping profile keys onto the actual
  `tools/run_ligand_htvs_pipeline.py` CLI.
- Require at least one exact config/profile path.
- Produce a local-delivery bundle command template and validator command.
- Keep `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.
- Record `APPROVE_PRODUCT_DOCKING_EXECUTION` as the future execution approval
  token.

Acceptance evidence:

- `betelgeuze_product/htvs_command.py` renders HTVS profile JSON into parser
  valid `run_ligand_htvs_pipeline.py` commands and records skipped or
  unsupported profile keys.
- `betelgeuze_product/work_order.py` builds execution work-order packets and
  blocks missing command/config fields.
- `tools/build_product_execution_work_order.py` writes JSON/CSV/MD work-order
  packets.
- `tests/unit/test_betelgeuze_product_htvs_command.py` verifies parser-valid
  profile command rendering and profile-driven work-order generation.
- `tests/unit/test_betelgeuze_product_work_order.py` verifies ready work order,
  missing field blocking, readiness blocking, and tool output.
- `runs/product_execution_work_order_current.json` currently reports
  `status=product_execution_work_order_ready`,
  `profile_command_generated=true`, `profile_command_rendered_count=85`, and
  `profile_command_unsupported_count=0` while `execution_enabled=false` and
  `bundle_assembled=false`.

### P0: Product Execution Preflight

The work order also needs a command-contract preflight before any approval token
is acted on. This catches invalid run commands, stale planned artifacts, and
missing config inputs without running docking.

Required behavior:

- Read a `product_execution_work_order_ready` packet.
- Validate the execution command against `tools/run_ligand_htvs_pipeline.py`
  argument parsing and block unknown arguments.
- Validate exact config/profile paths and required local inputs such as ligand
  and target-native CSVs.
- Warn, but do not execute, when a config requests `dry_run=false`.
- Block planned post-execution artifact paths that already exist before the
  approved run.
- Keep `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/execution_preflight.py` builds fail-closed execution
  preflight packets from work orders.
- `tools/build_product_execution_preflight.py` writes JSON/CSV/MD preflight
  packets.
- `tests/unit/test_betelgeuze_product_execution_preflight.py` verifies parser
  valid commands, invalid `--profile` commands, missing config inputs, and tool
  output.
- `runs/product_execution_preflight_current.json` currently reports
  `status=product_execution_preflight_ready`, `unknown_arg_count=0`,
  `blocker_count=0`, and `validated_without_execution=true`; execution remains
  disabled pending `APPROVE_PRODUCT_DOCKING_EXECUTION`.

### P0: Product Execution Operator Approval Gate

The product lane must not run docking merely because the command contract is
valid. This gate validates a row-specific operator approval CSV against the
current product execution preflight and work order before any execution path can
be authorized.

Required behavior:

- Read the product execution preflight and product execution work order.
- Write a fillable operator approval template for the current product target,
  family, bundle tag, and required approval token.
- Read an operator approval CSV when present and require exact row identity
  (`target_id`, `family`, `bundle_tag`), `operator_decision`, and matching
  `operator_approval_token=APPROVE_PRODUCT_DOCKING_EXECUTION`.
- Allow `skip` decisions without authorizing execution.
- Block missing approval CSV, missing decisions, token mismatch, duplicate
  rows, unknown approval rows, missing execution/bundle/validator commands, and
  invalid source execution/result/external-state flags.
- Preserve `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_product_execution_approval_gate.py` writes JSON/CSV/MD
  approval-gate packets and a CSV template without running product execution.
- `tests/unit/test_build_product_execution_approval_gate.py` verifies missing
  approval CSV blocking, exact-token authorization, token mismatch and unknown
  row blocking, template output, CLI output, and disabled execution/result/
  external-mutation flags.
- `runs/product_execution_approval_gate_current.json` currently reports
  `status=blocked_product_execution_operator_approval_gate`,
  `target_id=ADRB2`, `family=gpcr`, `bundle_tag=product_gpcr_adrb2`,
  `operator_approval_csv_present=false`, `authorized_for_execution=false`,
  `authorized_row_count=0`, `awaiting_operator_approval_row_count=1`,
  `blocked_row_count=1`, `approval_token_required=APPROVE_PRODUCT_DOCKING_EXECUTION`,
  and `blocker_count=2` with blockers
  `operator_approval_csv_missing,operator_decision_missing`. It writes
  `runs/product_execution_operator_approval_template_current.csv` and records
  `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.

### P0: Product Bundle Contract

The commercial product lane also needs a bundle handoff contract before
execution approval. This step validates that the recorded
`build_local_delivery_bundle.py` command and the matching
`validate_local_delivery_bundle.py` command are parseable and point at the
expected output location, without assembling the bundle.

Required behavior:

- Read the product execution work order and execution preflight artifacts.
- Require both artifacts to be ready and execution-disabled.
- Parse the recorded local-delivery bundle command against the actual
  `tools/build_local_delivery_bundle.py` CLI.
- Require an internal-review verdict before execution; block delivery-ready
  claims until approved execution has produced result artifacts.
- Verify config paths exist and planned artifacts are only recorded, not used as
  completed results.
- Verify the bundle validation command targets the expected bundle output
  directory.
- Keep `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/bundle_contract.py` validates the bundle command contract
  without running or assembling anything.
- `tools/build_product_bundle_contract.py` writes JSON/CSV/MD contract packets.
- `tests/unit/test_betelgeuze_product_bundle_contract.py` verifies ready
  contract, pre-execution delivery-ready claim blocking, and validation-dir
  mismatch blocking.
- `tests/unit/test_build_product_bundle_contract.py` verifies CLI output.
- `runs/product_bundle_contract_current.json` currently reports
  `status=product_bundle_contract_ready`, `bundle_parser_status=parsed`,
  `bundle_unknown_arg_count=0`,
  `bundle_validation_command_matches=true`, and `bundle_assembled=false`.

### P0: Product Delivery Evidence Contract

The product lane needs a customer-claim boundary after command and bundle
contracts are ready. Current local-delivery evidence can be green while this
specific product bundle is still unassembled. This contract keeps those states
separate.

Required behavior:

- Read product readiness, product execution preflight, product bundle contract,
  local-delivery verdict gate, local-delivery preflight, environment manifest,
  requirements lock, engine provenance, commercialization queue, nightly gate,
  and wetlab selected-allatom gate artifacts.
- Require restricted product family scope: `kinase`, `gpcr`, or `ion_channel`.
- Require current local-delivery evidence to be green, fingerprinted, and
  queue-clear.
- Require nightly and wetlab guardrails to be green.
- Keep `delivery_ready_claim_allowed=false` until the product bundle is
  assembled and the final bundle validator passes.
- Preserve `execution_enabled=false`, `docking_results_emitted=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/delivery_evidence.py` builds the fail-closed evidence
  contract.
- `tools/build_product_delivery_evidence_contract.py` writes JSON/CSV/MD
  evidence contract packets.
- `tests/unit/test_betelgeuze_product_delivery_evidence.py` verifies
  pre-approval readiness with customer claim disallowed, post-bundle claim
  allowance, and blocked out-of-scope/bad-verdict states.
- `tests/unit/test_build_product_delivery_evidence_contract.py` verifies CLI
  output.
- `runs/product_delivery_evidence_contract_current.json` currently reports
  `status=product_delivery_evidence_contract_ready`,
  `evidence_pass_count=12`, `evidence_check_count=12`,
  `delivery_ready_claim_allowed=false`, `bundle_assembled=false`, and
  `bundle_validation_passed=false`.

### P0: Product Release Operations Dossier

The product lane needs a single operations surface that explains why
`product_handoff_ready` is not yet a commercial independent-product release.
This dossier consolidates capability-surface readiness, execution approval,
bundle contract, final bundle validation, delivery evidence, and pilot packet
state without executing docking or assembling bundles.

Required behavior:

- Read product readiness, product capability surface, product architecture
  contract, execution preflight, execution work order, execution approval gate,
  bundle contract, delivery evidence, and pilot packet artifacts.
- Require `product_capability_surface_contract_ready` before treating the
  structure-analysis and ligand-docking product surface as complete.
- Require `product_architecture_contract_ready` before treating release
  operations as complete across product, CAMEO, CASP17 transition, and cleanup
  lanes.
- Surface execution preflight/work-order readiness, operator execution approval,
  bundle contract readiness, bundle assembly/final validation, and
  delivery-ready claim status as separate stages.
- Surface `approval_tokens_required`, `approval_token_count`, and the release
  operation stage rows through `/product/operations` for operator handoff.
- Require `APPROVE_PRODUCT_DOCKING_EXECUTION` before any product execution can
  be considered authorized.
- Keep `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, `delivery_ready_claim_allowed=false`, and
  `external_state_mutated=false` until downstream evidence proves otherwise.

Acceptance evidence:

- `tools/build_product_release_operations_dossier.py` writes JSON/CSV/MD
  product release operations dossiers without running docking, writing a
  license file, assembling bundles, validating completed bundles, or emitting
  scientific results.
- `tests/unit/test_build_product_release_operations_dossier.py` verifies the
  blocked current product lane, ready post-bundle behavior, and CLI output.
- `runs/product_release_operations_dossier_current.json` currently reports
  `status=blocked_product_release_operations_dossier`,
  `stage_count=9`, `blocked_stage_count=4`,
  `approval_required_stage_count=2`,
  `capability_surface_ready=true`,
  `architecture_contract_ready=false`,
  `source_architecture_status=blocked_product_architecture_contract`,
  `architecture_local_surface_ready=true`,
  `architecture_release_ready=false`,
  `architecture_blocked_lane_count=1`,
  `architecture_approval_required_lane_count=2`,
  `product_service_boundary_ready=true`,
  `product_api_contract_ready=true`,
  `cameo_architecture_validation_ready=false`,
  `cleanup_postcheck_contract_ready=true`,
  `structure_analysis_capability_ready=true`,
  `ligand_docking_capability_ready=true`,
  `product_api_surface_ready=true`,
  `commercial_independence_ready=false`,
  `license_present=false`,
  `source_license_decision_packet_status=product_license_decision_packet_ready`,
  `license_decision_option_count=5`,
  `license_decision_packet_ready=true`,
  `license_authorized_for_file_creation_review=false`,
  `approval_tokens_required=APPROVE_PRODUCT_DOCKING_EXECUTION,APPROVE_PRODUCT_LICENSE_FILE_CREATION`,
  `approval_token_count=2`,
  `authorized_for_execution=false`, `bundle_assembled=false`,
  `bundle_validation_passed=false`, `delivery_ready_claim_allowed=false`,
  `pilot_delivery_ready=false`, `execution_enabled=false`,
  `docking_results_emitted=false`, and `external_state_mutated=false`.
- `/product/release-readiness` also exposes the current license handoff
  directly: `license_present=false`,
  `license_decision_status=blocked_product_license_decision_gate`,
  `license_decision_packet_status=product_license_decision_packet_ready`,
  `license_decision_packet_ready=true`, `license_decision_option_count=5`,
  `license_authorized_for_file_creation_review=false`, and
  `license_file_written=false`.

### P0: Product Commercial Independence Gate

The product lane also needs evidence that the repo can support commercial
independent-product claims, not only local scientific preflight claims. This
gate audits packaging and dependency evidence without installing packages or
running docking.

Required behavior:

- Require a non-empty license artifact before commercial distribution claims.
- Require a non-empty core `requirements.txt`.
- Require exact runtime dependency pins or direct references for reproducible
  handoff.
- Require external API SDKs to be absent from the core runtime dependency set.
- Require API, deployment, training, and optional hardware-extension profiles to
  remain separated from the core runtime requirements.
- Require a deployment profile or container manifest.
- Require `api/product.py`, the `betelgeuze_product` package surface, and the
  read-only local product CLI surface.
- Preserve `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/commercial_independence.py` builds the fail-closed
  commercial-independence gate from local repository files.
- `tools/build_product_commercial_independence_gate.py` writes JSON/CSV/MD
  packets without installing packages or mutating external state.
- `api/product.py` exposes `/product/commercial-independence` as a read-only
  status surface that includes the current license-decision gate status,
  license option packet status/count, operator template/intake paths, required
  license-decision fields, and the exact approval token without writing a
  license file.
- `tests/unit/test_betelgeuze_product_commercial_independence.py` verifies a
  ready pinned tree, missing-license/loose-runtime/external-API blocking, and
  optional-profile separation blocking.
- `tests/unit/test_build_product_commercial_independence_gate.py` verifies CLI
  output.
- `runs/product_commercial_independence_gate_current.json` currently reports
  `status=blocked_product_commercial_independence_gate`, `blocker_count=1`,
  `loose_runtime_dependency_count=0`,
  `external_api_runtime_dependencies=[]`, and
  `optional_profiles_separated=true`, `core_product_surface_present=true`, and
  `product_cli_surface_present=true`; commercial independent-product claims now
  remain blocked only on explicit license evidence.
- `/product/commercial-independence` currently reports
  `license_decision_packet_status=product_license_decision_packet_ready`,
  `license_decision_packet_ready=true`, `license_decision_option_count=5`,
  `commercial_gate_only_license_blocked=true`,
  `approval_token_required=APPROVE_PRODUCT_LICENSE_FILE_CREATION`, and
  `license_file_written=false`.

### P0: Product License Decision Packet

The commercial-independence blocker is now narrow enough for an operator license
choice. The packet prepares that choice without making it.

Required behavior:

- Read the product commercial-independence gate and product license-decision
  gate.
- Confirm that `license_file_present` is the only commercial-independence
  blocker before presenting license paths as immediately actionable.
- Present common operator-selectable paths including permissive, copyleft, and
  proprietary options with review focus and text-source hints.
- Point the operator to `product_license_decision_operator_intake.csv` and the
  existing exact approval token.
- Preserve `license_file_written=false`, `legal_advice_provided=false`,
  `execution_enabled=false`, `docking_results_emitted=false`,
  `bundle_assembled=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/license_options.py` builds the license decision packet
  without choosing a license, giving legal advice, or writing a LICENSE file.
- `tools/build_product_license_decision_packet.py` writes JSON/CSV/MD license
  option packets from existing commercial/license gate artifacts.
- `api/product.py` exposes `/product/license-options` and includes the packet
  status in `/product/operations`, `/product/commercial-independence`, and
  `/product/release-readiness`.
- `tests/unit/test_betelgeuze_product_license_options.py` verifies ready
  option packets, non-license commercial blocker behavior, and CLI output.
- `tests/unit/test_api_product_import.py` verifies the license-options API route
  and fail-closed flags.
- `runs/product_license_decision_packet_current.json` currently reports
  `status=product_license_decision_packet_ready`, `option_count=5`,
  `blocker_count=0`, `commercial_gate_only_license_blocked=true`,
  `license_decision_gate_status=blocked_product_license_decision_gate`,
  `operator_intake_csv_present=false`, `license_file_written=false`,
  `legal_advice_provided=false`, and `external_state_mutated=false`.

### P0: Product License Decision Gate

The remaining commercial-independence blocker is a legal/business decision, not
a technical dependency issue. This gate creates the operator-review surface for
that decision without choosing a license or writing a `LICENSE` file.

Required behavior:

- Read the product commercial-independence gate.
- Require the commercial-independence gate to be blocked only by the missing
  license file.
- Require an operator intake CSV with `decision=create_license_file`.
- Require the exact token `APPROVE_PRODUCT_LICENSE_FILE_CREATION`.
- Require SPDX/source, rights-holder, and effective-year metadata before any
  license-file creation review can be authorized.
- Preserve `license_file_written=false`, `execution_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `betelgeuze_product/license_decision.py` validates the license decision
  contract without choosing or writing a license.
- `tools/build_product_license_decision_gate.py` writes JSON/CSV/MD packets and
  `runs/product_license_decision_operator_template_current.csv`.
- `api/product.py` exposes `/product/license-decision` and the
  `/product/operations` license fields as read-only operator surfaces for the
  template path, intake path, required fields, required decision, and approval
  token.
- `tests/unit/test_betelgeuze_product_license_decision.py` verifies missing
  intake blocking, exact-token ready behavior, and bad-token/non-license-blocker
  blocking.
- `tests/unit/test_build_product_license_decision_gate.py` verifies CLI output
  and template creation.
- `tests/unit/test_api_product_import.py` verifies the license-decision API
  route and that it preserves `license_file_written=false`,
  `execution_enabled=false`, and `external_state_mutated=false`.
- `runs/product_license_decision_gate_current.json` currently reports
  `status=blocked_product_license_decision_gate`,
  `authorized_for_license_file_creation_review=false`, `blocker_count=4`,
  `operator_intake_csv_present=false`,
  `approval_token_required=APPROVE_PRODUCT_LICENSE_FILE_CREATION`,
  `commercial_gate_only_license_blocked=true`, `license_file_written=false`,
  and `external_state_mutated=false`.

### P0: Goal Readiness Rollup

The objective spans commercial product execution, CAMEO architecture
validation, and cleanup. A top-level rollup should state the real current state
without implying completion.

Required behavior:

- Read product readiness + execution preflight + product bundle contract,
  product architecture contract,
  CAMEO validation readiness, CAMEO repair work order, CAMEO operator input kit
  manifest, CAMEO operator input validation, CAMEO repair execution preflight,
  transition cleanup work order + execution preflight, and ligand-heavy cleanup
  work order + execution
  preflight.
- Mark the whole objective blocked if any lane is blocked.
- Mark operator approval pending for lanes that are ready but intentionally
  execution-disabled.
- Preserve `execution_enabled=false`, `action_executed=false`,
  `delete_executed=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.
- Sum reclaimable cleanup size from transition cleanup and ligand-heavy cleanup
  work orders.

Acceptance evidence:

- `tools/build_goal_readiness_rollup.py` writes JSON/CSV/MD rollups and keeps
  all execution/deletion/email flags disabled.
- `tests/unit/test_build_goal_readiness_rollup.py` verifies blocked CAMEO
  rollup, approval-pending rollup, missing product preflight blocking, and CLI
  output.
- `runs/goal_readiness_rollup_current.json` currently reports
  `status=blocked_goal_readiness`, `lane_count=5`,
  `blocked_lane_count=1`, `external_results_pending_count=1`,
  `operator_approval_pending_count=3`, and `total_reclaim_size_gb=49.217`.
  Its product lane records `bundle_contract_status=product_bundle_contract_ready`.
  It also records
  `delivery_evidence_status=product_delivery_evidence_contract_ready`,
  `delivery_ready_claim_allowed=false`, and
  `delivery_evidence_warning_count=2`. Its product lane now also records
  `pilot_packet_status=product_pilot_packet_preflight_ready`,
  `pilot_delivery_ready=false`, and `pilot_packet_warning_count=2`.
  Its product architecture lane records
  `observed_status=blocked_product_architecture_contract`,
  `local_architecture_surface_ready=true`,
  `architecture_release_ready=false`, `blocker_count=1`,
  `architecture_approval_required_lane_count=2`,
  `structure_analysis_product_surface_ready=true`,
  `ligand_docking_execution_contract_ready=true`,
  `cleanup_control_surface_ready=true`, and
  `casp17_transition_surface_ready=true`.
  Its transition cleanup lane records
  `transition_cleanup_preflight_status=transition_cleanup_execution_preflight_ready`.
  Its ligand-heavy cleanup lane records
  `cleanup_execution_preflight_status=ligand_heavy_cleanup_execution_preflight_ready`.
  Its CAMEO lane also records
  `repair_work_order_status=cameo_validation_repair_not_required` and
  `repair_operator_input_missing_count=0`, while
  `operator_input_kit_status=cameo_operator_input_kit_ready` and
  `operator_input_validation_status=cameo_operator_inputs_ready_pending_official_results`
  record that the local smoke input path is filled and validated while official
  result rows remain pending.
  It also records
  `repair_execution_preflight_status=cameo_repair_execution_not_required`
  and `repair_execution_preflight_blocker_count=0`, so the local CAMEO
  selection/format/handoff chain is no longer placeholder-blocked. Its CAMEO
  lane also records
  `capability_preflight_status=blocked_cameo_capability_preflight`,
  `api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `api_dependency_ready=false`, `api_dependency_blocker_count=4`,
  `receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `receiver_smoke_post_200_ok=false`, `receiver_smoke_blocker_count=1`,
  `public_registration_allowed=false`, and `public_registration_blocker_count=4`.
  The rollup also records
  `cleanup_postcheck_contract_status=cleanup_postcheck_contract_ready`,
  `cleanup_postcheck_contract_ready=true`, `cleanup_postcheck_row_count=7`,
  `cleanup_postcheck_blocked_row_count=0`, and
  `cleanup_postcheck_global_refresh_command_count=9`.
  It also records
  `product_cli_status_set_status=blocked_product_cli_status_set`,
  `product_cli_approval_token_count=2`,
  `product_cli_operations_blocked_stage_count=4`,
  `product_cli_authorized_for_execution=false`,
  `product_cli_delivery_ready_claim_allowed=false`,
  `cameo_cli_status_set_status=blocked_cameo_cli_status_set`,
  `cameo_cli_approval_token_count=3`,
  `cameo_cli_official_result_required=true`,
  `cameo_cli_receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `cleanup_cli_status_set_status=blocked_cleanup_cli_status_set`,
  `cleanup_cli_approval_token_count=4`,
  `cleanup_cli_approval_reclaim_size_gb=49.216`,
  `cleanup_cli_postcheck_contract_ready=true`,
  `cleanup_cli_protected_payload_size_gb=396.794`, and
  `cleanup_cli_protected_policy_change_required_count=2`.

### P0: Goal Operator Action Board

The objective now spans multiple approval-gated and input-gated lanes. The
operator should not have to infer the next action from scattered JSON files.
The action board is a local-only consolidation layer; it does not approve or
execute anything.

Required behavior:

- Read the current goal readiness rollup, product execution preflight, product
  bundle contract, product delivery evidence contract, product pilot packet,
  product release operations dossier, CAMEO runtime repair work order, CAMEO
  validation operations dossier, CAMEO operator input kit, CAMEO operator input
  validation, CAMEO repair execution preflight, transition cleanup execution
  preflight, and ligand-heavy cleanup execution preflight.
- Surface priority-1 CAMEO operator CSV rows before repair commands.
- Surface product execution approval and pilot handoff status separately from
  cleanup approval tokens.
- Surface product license decision intake separately from product execution
  approval.
- Surface product license option packet review separately from the license
  intake gate so the operator can choose a license path before filling CSV
  metadata.
- Surface approval-gated cleanup rows with their tokens and reclaim sizes.
- Surface large review-only cleanup paths that need narrower classification
  before deletion can be approval-gated.
- Preserve `execution_enabled=false`, `action_executed=false`,
  `delete_executed=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_goal_operator_action_board.py` writes JSON/CSV/MD action boards
  from existing local artifacts only and summarizes the full-goal release gate
  without adding a self-referential release action row.
- `tools/build_goal_operator_intake_kit.py` writes a read-only JSON/CSV/README
  kit under `runs/goal_operator_intake_kit_current/`, copying only operator
  template CSVs and surfacing expected intake paths, approval tokens, and the
  product commercial-independence gate behind license intake, plus the
  read-only `/goal/status` and `/goal/api-contract` review surface. It reports
  catalog-wide approval tokens separately from approval tokens surfaced by the
  current action board, and distinguishes current-action operator inputs from
  deferred inputs gated by unmet prerequisites.
- `tests/unit/test_build_goal_operator_action_board.py` verifies CAMEO input
  blockers, CAMEO receiver runtime-smoke blockers, API dependency install
  approval-token promotion, CAMEO rebuild command blockers, product approval,
  ligand-heavy cleanup approval, transition cleanup approval, large review-only
  cleanup rows, release gate summary propagation, and release burndown summary
  propagation, cleanup snapshot preflight summary propagation, and cleanup
  execution approval dossier/gate summary propagation, and product execution
  approval-gate summary propagation, product license decision gate and option
  packet summary propagation, product release operations dossier summary
  propagation, CAMEO official-results intake plus validation operations
  dossier summary propagation, and goal operator intake-kit plus goal API
  surface review summary propagation.
- `tests/unit/test_build_goal_operator_intake_kit.py` verifies kit summary
  counts, token surfacing, product commercial-independence/license blocker
  surfacing, current-action approval token surfacing, goal API review
  surfacing, current/deferred operator-input separation, missing-template
  blocking, and template-copy output.
- `runs/goal_operator_action_board_current.json` currently reports
  `status=operator_actions_required`, `action_count=11`,
  `blocked_or_required_action_count=2`, `approval_required_count=7`,
  `review_required_count=0`, `approval_reclaim_size_gb=49.216`,
  `large_review_size_gb=0`, and
  `large_cleanup_review_resolved_by_drilldown_count=2`. It also links the large cleanup drilldown
  with `large_cleanup_drilldown_status=large_cleanup_surface_drilldown_ready`,
  `large_cleanup_dry_run_delete_payload_size_gb=6.012`, and
  `large_cleanup_dry_run_protected_payload_size_gb=396.794`, so protected
  payloads are surfaced separately from approval-gated reclaim. It also records
  `protected_cleanup_review_status=protected_cleanup_payload_review_ready`,
  `protected_cleanup_payload_size_gb=396.794`,
  `protected_cleanup_policy_change_required_count=2`, and
  `protected_cleanup_approval_promoted_count=0`. It also records
  `protected_ligand_heavy_deep_review_status=protected_ligand_heavy_payload_deep_review_ready`,
  `protected_ligand_heavy_known_payload_child_count=2`,
  `protected_ligand_heavy_known_payload_child_size_gb=396.794`,
  `protected_ligand_heavy_preservation_sibling_count=2`, and
  `protected_ligand_heavy_policy_change_required_for_deletion_count=2`, so the
  protected 396.794 GB child payload is surfaced for policy decision without
  approval promotion. It also records
  `protected_cleanup_policy_decision_gate_status=blocked_protected_cleanup_policy_decision_gate`,
  `protected_cleanup_policy_resolved=false`,
  `protected_cleanup_policy_awaiting_decision_row_count=2`,
  `protected_cleanup_policy_change_requested_row_count=0`, and
  `protected_cleanup_policy_decision_blocked_row_count=2`. It also records
  `cleanup_cli_status_set_status=blocked_cleanup_cli_status_set`,
  `cleanup_cli_command_count=16`,
  `cleanup_cli_blocked_or_missing_command_count=3`,
  `cleanup_cli_approval_required_command_count=2`,
  `cleanup_cli_approval_token_count=4`,
  `cleanup_cli_approval_tokens_required=APPROVE_ARCHIVE_LEGACY_RUNS,APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS,APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS,APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS`,
  `cleanup_cli_approval_reclaim_size_gb=49.216`,
  `cleanup_cli_authorized_reclaim_size_gb=0.0`,
  `cleanup_cli_awaiting_operator_approval_row_count=5`,
  `cleanup_cli_postcheck_contract_ready=true`,
  `cleanup_cli_postcheck_row_count=7`,
  `cleanup_cli_postcheck_blocked_row_count=0`,
  `cleanup_cli_protected_payload_size_gb=396.794`,
  `cleanup_cli_protected_policy_change_required_count=2`, and
  `cleanup_cli_protected_policy_resolved=false`. It also records
  `cleanup_snapshot_preflight_status=cleanup_snapshot_preflight_ready`,
  `cleanup_snapshot_blocked_row_count=0`,
  `cleanup_snapshot_missing_count=0`,
  `cleanup_snapshot_required_count=2`, and
  `cleanup_snapshot_approval_gated_size_gb=49.216`. It also records
  `cleanup_execution_approval_dossier_status=cleanup_execution_approval_dossier_ready`,
  `cleanup_execution_approval_dossier_approval_row_count=5`,
  `cleanup_execution_approval_dossier_snapshot_backed_approval_row_count=2`,
  `cleanup_execution_approval_dossier_snapshot_artifact_count=2`,
  `cleanup_execution_approval_dossier_snapshot_ready_count=2`,
  `cleanup_execution_approval_dossier_snapshot_listing_truncated_count=1`,
  `cleanup_execution_approval_dossier_snapshot_total_entry_count=201224`, and
  `cleanup_execution_approval_dossier_snapshot_set_fingerprint_sha256=04c2f2561bcbe091ba3146a767a2481419b40883c81833cdc6a44477b28bdce0`.
  It also records
  `cleanup_execution_approval_gate_status=blocked_cleanup_execution_operator_approval_gate`,
  `cleanup_execution_authorized_row_count=0`,
  `cleanup_execution_awaiting_operator_approval_row_count=5`,
  `cleanup_execution_blocked_row_count=5`,
  `cleanup_execution_total_reclaim_size_gb=49.216`, and
  `cleanup_execution_operator_approval_csv_present=false`. It also records
  `cleanup_postcheck_contract_status=cleanup_postcheck_contract_ready`,
  `cleanup_postcheck_contract_ready=true`, `cleanup_postcheck_row_count=7`,
  `cleanup_postcheck_approval_row_count=5`,
  `cleanup_postcheck_protected_policy_row_count=2`,
  `cleanup_postcheck_blocked_row_count=0`, and
  `cleanup_postcheck_global_refresh_command_count=9`. It also records
  `cleanup_completion_gate_status=blocked_cleanup_completion_gate`,
  `cleanup_completion_complete=false`,
  `cleanup_completion_blocked_stage_count=4`,
  `cleanup_completion_approval_ready=false`,
  `cleanup_completion_transition_cleanup_complete=false`,
  `cleanup_completion_ligand_heavy_cleanup_complete=false`, and
  `cleanup_completion_protected_policy_resolved=false`. It also records
  `goal_release_decision_gate_status=blocked_goal_release_decision`,
  `goal_release_allowed=false`, `goal_release_blocker_count=13`,
  `goal_release_check_count=15`,
  `source_goal_api_surface_contract_status=goal_api_surface_contract_ready`,
  `goal_api_surface_ready=true`, `goal_api_surface_check_count=7`,
  `goal_api_surface_blocker_count=0`,
  `goal_api_surface_missing_endpoint_count=0`,
  `goal_api_surface_missing_status_key_count=0`,
  `commercial_independent_product_ready=false`,
  `cameo_architecture_validation_ready=false`, and
  `cleanup_objective_ready=false`. It also records
  `goal_release_burndown_work_order_status=goal_release_burndown_work_order_ready`,
  `goal_release_burndown_release_blocker_check_count=13`,
  `goal_release_burndown_work_item_count=9`,
  `goal_release_burndown_approval_required_item_count=5`,
  `goal_release_burndown_official_results_required_item_count=1`,
  `goal_release_burndown_operator_input_required_item_count=0`,
  `goal_release_burndown_policy_decision_required_item_count=1`,
  `goal_release_burndown_postcheck_required_item_count=0`, and
  `goal_release_burndown_approval_token_count=5`. It also records
  `goal_operator_intake_kit_status=goal_operator_intake_kit_ready`,
  `goal_operator_intake_kit_entry_count=8`,
  `goal_operator_intake_kit_operator_input_required_count=7`,
  `goal_operator_intake_kit_current_action_required_count=6`,
  `goal_operator_intake_kit_deferred_operator_input_count=1`,
  `goal_operator_intake_kit_template_copied_count=6`,
  `goal_operator_intake_kit_template_missing_count=0`, and
  `goal_operator_intake_kit_approval_token_count=9`. It also records
  `goal_operator_intake_kit_current_action_approval_token_count=7` and
  `goal_operator_intake_kit_current_action_approval_tokens=APPROVE_API_DEPENDENCY_INSTALL,APPROVE_ARCHIVE_LEGACY_RUNS,APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS,APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS,APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS,APPROVE_PRODUCT_DOCKING_EXECUTION,APPROVE_PRODUCT_LICENSE_FILE_CREATION`,
  separating currently surfaced action approvals from later CAMEO
  registration/email approvals. It also records
  `goal_operator_intake_kit_product_commercial_independence_status=blocked_product_commercial_independence_gate`,
  `goal_operator_intake_kit_product_commercial_independence_blocker_count=1`,
  and
  `goal_operator_intake_kit_product_commercial_independence_license_present=false`,
  so the operator can see that license evidence remains the commercial
  independence blocker before filling the license intake. The intake kit adds
  a read-only `goal_api_status_surface` row with `kit_status=ready`,
  `api_endpoints=/goal/status;/goal/api-contract`, and
  `source_gate_status=goal_api_surface_contract_ready`; action board summary
  also records
  `goal_operator_intake_kit_goal_api_surface_contract_status=goal_api_surface_contract_ready`,
  `goal_operator_intake_kit_goal_api_surface_ready=true`, and
  `goal_operator_intake_kit_goal_api_surface_check_count=7`. It also records
  `cameo_runtime_repair_work_order_status=cameo_runtime_repair_work_order_ready`,
  `cameo_runtime_install_approval_required=true`,
  `cameo_runtime_approval_token_required=APPROVE_API_DEPENDENCY_INSTALL`, and
  `cameo_runtime_repair_command_count=5`. It also records
  `cameo_validation_operations_dossier_status=blocked_cameo_validation_operations_dossier`,
  `cameo_validation_operations_blocked_stage_count=2`,
  `cameo_validation_operations_approval_required_stage_count=1`,
  `cameo_validation_operations_operator_input_required_count=0`,
  `cameo_validation_operations_official_result_required=true`,
  `cameo_validation_operations_official_results_intake_status=blocked_cameo_official_results_intake`,
  `cameo_validation_operations_official_results_intake_ready=false`, and
  `cameo_validation_operations_official_results_intake_blocker_count=2`. It
  also records
  `cameo_cli_status_set_status=blocked_cameo_cli_status_set`,
  `cameo_cli_command_count=11`,
  `cameo_cli_blocked_or_missing_command_count=7`,
  `cameo_cli_approval_required_command_count=2`,
  `cameo_cli_approval_token_count=3`,
  `cameo_cli_approval_tokens_required=APPROVE_API_DEPENDENCY_INSTALL,APPROVE_CAMEO_OUTBOUND_EMAIL,APPROVE_CAMEO_SERVER_REGISTRATION`,
  `cameo_cli_official_result_required=true`,
  `cameo_cli_official_results_result_row_count=0`,
  `cameo_cli_official_results_accepted_count=0`,
  `cameo_cli_official_model1_result_ready=false`,
  `cameo_cli_api_install_approval_required=true`,
  `cameo_cli_api_dependency_status=blocked_cameo_api_dependency_readiness`,
  `cameo_cli_receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `cameo_cli_public_registration_authorized=false`, and
  `cameo_cli_registration_awaiting_operator_approval_row_count=1`. It also
  records
  `cameo_official_results_intake_gate_status=blocked_cameo_official_results_intake`,
  `cameo_official_results_intake_result_row_count=0`,
  `cameo_official_results_intake_accepted_count=0`,
  `cameo_official_results_intake_model1_ready=false`, and
  `cameo_official_results_intake_blocker_count=2`. It also records
  `cameo_validation_operations_public_registration_allowed=false`. It also records
  `cameo_public_registration_approval_gate_status=blocked_cameo_public_registration_approval_gate`,
  `cameo_public_registration_authorized_for_registration_review=false`,
  `cameo_public_registration_operator_approval_csv_present=false`, and
  `cameo_public_registration_blocked_row_count=1`. It also records
  `product_pilot_packet_status=product_pilot_packet_preflight_ready` and
  `product_pilot_delivery_ready=false`. It also records
  `product_execution_approval_gate_status=blocked_product_execution_operator_approval_gate`,
  `product_execution_authorized_for_execution=false`,
  `product_execution_authorized_row_count=0`,
  `product_execution_awaiting_operator_approval_row_count=1`,
  `product_execution_blocked_row_count=1`, and
  `product_execution_operator_approval_csv_present=false`. It also records
  `product_license_decision_gate_status=blocked_product_license_decision_gate`,
  `product_license_decision_packet_status=product_license_decision_packet_ready`,
  `product_license_decision_option_count=5`,
  `product_license_decision_packet_ready=true`,
  `product_license_authorized_for_file_creation_review=false`,
  `product_license_operator_intake_csv_present=false`, and
  `product_license_blocker_count=4`. It also records
  `product_cli_status_set_status=blocked_product_cli_status_set`,
  `product_cli_command_count=9`,
  `product_cli_blocked_or_missing_command_count=5`,
  `product_cli_approval_token_count=2`,
  `product_cli_approval_tokens_required=APPROVE_PRODUCT_DOCKING_EXECUTION,APPROVE_PRODUCT_LICENSE_FILE_CREATION`,
  `product_cli_operations_stage_count=9`,
  `product_cli_operations_blocked_stage_count=4`,
  `product_cli_operations_approval_required_stage_count=2`,
  `product_cli_capability_surface_ready=true`,
  `product_cli_structure_analysis_capability_ready=true`,
  `product_cli_ligand_docking_capability_ready=true`,
  `product_cli_product_api_surface_ready=true`,
  `product_cli_architecture_release_ready=false`,
  `product_cli_commercial_independence_ready=false`,
  `product_cli_license_present=false`,
  `product_cli_license_authorized_for_file_creation_review=false`,
  `product_cli_authorized_for_execution=false`,
  `product_cli_bundle_assembled=false`,
  `product_cli_bundle_validation_passed=false`,
  `product_cli_delivery_ready_claim_allowed=false`, and
  `product_cli_pilot_delivery_ready=false`. It also records
  `product_release_operations_dossier_status=blocked_product_release_operations_dossier`,
  `product_release_operations_blocked_stage_count=4`,
  `product_release_operations_approval_required_stage_count=2`,
  `product_release_operations_architecture_contract_ready=false`,
  `product_release_operations_architecture_release_ready=false`,
  `product_release_operations_architecture_blocked_lane_count=1`,
  `product_release_operations_architecture_approval_required_lane_count=2`,
  `product_release_operations_cleanup_postcheck_contract_ready=true`,
  `product_release_operations_commercial_independence_ready=false`,
  `product_release_operations_license_present=false`,
  `product_release_operations_license_decision_packet_ready=true`,
  `product_release_operations_license_decision_option_count=5`,
  `product_release_operations_license_authorized_for_file_creation_review=false`,
  `product_release_operations_authorized_for_execution=false`,
  `product_release_operations_bundle_assembled=false`,
  `product_release_operations_bundle_validation_passed=false`,
  `product_release_operations_delivery_ready_claim_allowed=false`, and
  `product_release_operations_pilot_delivery_ready=false`. All
  execution/deletion/email/external
  mutation flags remain disabled.

### P0: Goal Release Decision Gate

The full objective must not be treated as achieved just because individual
preflight lanes are present. The release decision gate is the final local
evidence check before any commercial-product, CAMEO-validation, or cleanup
completion claim can be made.

Required behavior:

- Read the product pilot packet, product commercial-independence gate, CAMEO
  validation readiness, CAMEO capability preflight, CAMEO public registration
  approval gate, goal readiness rollup, goal operator action board, transition
  cleanup execution preflight, ligand-heavy cleanup execution preflight,
  protected cleanup payload review, protected cleanup policy decision gate, and
  cleanup completion gate.
- Require `pilot_delivery_ready=true`, final bundle validation, and
  `delivery_ready_claim_allowed=true` for product pilot readiness.
- Require `product_commercial_independence_gate_ready` before commercial
  independent-product release readiness can be claimed.
- Require `cameo_validation_evidence_ready`, official CAMEO results, and public
  CAMEO registration allowance or a ready CAMEO public registration approval
  gate for architecture-validation readiness.
- Require a clear operator action board, completed transition cleanup, completed
  ligand-heavy cleanup, a ready cleanup postcheck contract, and resolved
  protected-cleanup policy rows for cleanup readiness. Protected policy is
  resolved either when the protected review has no pending rows or when the
  policy decision gate records explicit keep decisions for all protected rows.
  When present, `cleanup_completion_gate_ready` can provide the consolidated
  cleanup completion evidence for transition, ligand-heavy, and protected-policy
  checks, but the postcheck contract must still be ready before release.
- Preserve `execution_enabled=false`, `action_executed=false`,
  `delete_executed=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_goal_release_decision_gate.py` writes JSON/CSV/MD release
  decision gates from existing local artifacts only.
- `tests/unit/test_build_goal_release_decision_gate.py` verifies blocked
  current-state behavior, all-lanes-complete behavior, explicit protected keep
  policy resolution, cleanup completion gate acceptance, product commercial
  independence blocking, cleanup postcheck blocking, goal API surface contract
  blocking, and CLI output.
- `runs/goal_release_decision_gate_current.json` currently reports
  `status=blocked_goal_release_decision`, `release_allowed=false`,
  `commercial_independent_product_ready=false`,
  `cameo_architecture_validation_ready=false`,
  `cleanup_objective_ready=false`, `blocker_count=13`, and `check_count=15`.
  It also records `source_product_pilot_status=product_pilot_packet_preflight_ready`,
  `source_product_architecture_status=blocked_product_architecture_contract`,
  `product_architecture_local_surface_ready=true`,
  `product_architecture_release_ready=false`,
  `source_product_commercial_independence_status=blocked_product_commercial_independence_gate`,
  `product_commercial_independence_ready=false`,
  `source_cameo_validation_status=cameo_validation_pending_official_results`,
  `source_cameo_capability_status=blocked_cameo_capability_preflight`,
  `source_cameo_public_registration_approval_gate_status=blocked_cameo_public_registration_approval_gate`,
  `cameo_public_registration_authorized_for_registration_review=false`,
  `source_goal_rollup_status=blocked_goal_readiness`,
  `source_goal_api_surface_contract_status=goal_api_surface_contract_ready`,
  `goal_api_surface_ready=true`, `goal_api_surface_check_count=7`,
  `goal_api_surface_blocker_count=0`,
  `source_operator_action_board_status=operator_actions_required`,
  `operator_action_count=11`, `operator_approval_required_count=7`,
  `operator_review_required_count=0`,
  `approval_reclaim_size_gb=49.216`,
  `product_cli_status_set_status=blocked_product_cli_status_set`,
  `product_cli_approval_token_count=2`,
  `product_cli_operations_blocked_stage_count=4`,
  `product_cli_authorized_for_execution=false`,
  `product_cli_delivery_ready_claim_allowed=false`,
  `cameo_cli_status_set_status=blocked_cameo_cli_status_set`,
  `cameo_cli_approval_token_count=3`,
  `cameo_cli_official_result_required=true`,
  `cameo_cli_receiver_smoke_status=blocked_cameo_receiver_smoke`,
  `cleanup_cli_status_set_status=blocked_cleanup_cli_status_set`,
  `cleanup_cli_approval_token_count=4`,
  `cleanup_cli_approval_reclaim_size_gb=49.216`,
  `cleanup_cli_postcheck_contract_ready=true`,
  `cleanup_cli_protected_payload_size_gb=396.794`, and
  `cleanup_cli_protected_policy_change_required_count=2`. It also records
  `protected_cleanup_payload_size_gb=396.794`, and
  `protected_cleanup_policy_change_required_count=2`. It also records
  `protected_cleanup_known_payload_child_count=2`,
  `protected_cleanup_known_payload_child_size_gb=396.794`,
  `protected_cleanup_preservation_sibling_count=2`, and
  `protected_cleanup_policy_change_required_for_deletion_count=2`, so the
  release blocker now names the protected child payload requiring an explicit
  keep/policy-change decision. It also records
  `protected_cleanup_policy_decision_gate_status=blocked_protected_cleanup_policy_decision_gate`
  and `protected_cleanup_policy_resolved=false`. It also records
  `cleanup_postcheck_contract_status=cleanup_postcheck_contract_ready`,
  `cleanup_postcheck_contract_ready=true`, `cleanup_postcheck_row_count=7`,
  `cleanup_postcheck_blocked_row_count=0`, and
  `cleanup_postcheck_global_refresh_command_count=9`; the
  `cleanup_postcheck_contract_ready` release check currently passes. It also
  records
  `cleanup_completion_gate_status=blocked_cleanup_completion_gate` and
  `cleanup_completion_complete=false`. All
  execution/deletion/email/external mutation flags remain disabled.

### P0: Goal Release Burndown Work Order

The release decision gate is intentionally strict, but a strict gate is not
enough unless the remaining blockers can be sequenced into operator-reviewable
work. The burndown work order maps release blockers to existing local work
orders, approval tokens, and refresh commands without executing any command.

Required behavior:

- Read the release decision gate, operator action board, product execution work
  order, product pilot packet, CAMEO validation repair work order, CAMEO runtime
  repair work order, CAMEO capability preflight, transition cleanup work order,
  ligand-heavy cleanup work order, protected cleanup payload review, and
  cleanup postcheck contract.
- Convert each failing release gate row into a `P1` product, `P2` CAMEO, `P3`
  cleanup, or `P4` evidence-refresh work item.
- Preserve existing approval tokens such as `APPROVE_PRODUCT_DOCKING_EXECUTION`,
  `APPROVE_API_DEPENDENCY_INSTALL`, `APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS`, and
  `APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS`.
- Keep protected cleanup policy rows as policy-decision items rather than
  promoting them to deletion.
- Convert a failed `cleanup_postcheck_contract_ready` release check into a
  postcheck refresh work item with the local postcheck and goal-gate rebuild
  commands.
- Preserve `execution_enabled=false`, `action_executed=false`,
  `delete_executed=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_goal_release_burndown_work_order.py` writes JSON/CSV/MD
  burndown work orders from existing local artifacts only.
- `tests/unit/test_build_goal_release_burndown_work_order.py` verifies blocked
  release blocker mapping, all-clear release behavior, approval token
  preservation, cleanup postcheck blocker mapping, goal API surface contract
  refresh mapping, and CLI output.
- `runs/goal_release_burndown_work_order_current.json` currently reports
  `status=goal_release_burndown_work_order_ready`,
  `source_release_gate_status=blocked_goal_release_decision`,
  `source_release_allowed=false`, `source_release_blocker_count=13`,
  `release_blocker_check_count=13`,
  `work_item_count=9`, `approval_required_item_count=5`,
  `operator_input_required_item_count=0`,
  `official_results_required_item_count=1`,
  `policy_decision_required_item_count=1`,
  `postcheck_required_item_count=0`, and `approval_token_count=5`. It also
  records `cleanup_postcheck_contract_status=cleanup_postcheck_contract_ready`,
  `cleanup_postcheck_contract_ready=true`, `cleanup_postcheck_row_count=7`, and
  `cleanup_postcheck_blocked_row_count=0`. It
  records
  `product_cli_status_set_status=blocked_product_cli_status_set`,
  `product_cli_approval_token_count=2`,
  `product_cli_operations_blocked_stage_count=4`,
  `cameo_cli_status_set_status=blocked_cameo_cli_status_set`,
  `cameo_cli_approval_token_count=3`,
  `cameo_cli_official_result_required=true`,
  `cleanup_cli_status_set_status=blocked_cleanup_cli_status_set`,
  `cleanup_cli_approval_token_count=4`,
  `cleanup_cli_approval_reclaim_size_gb=49.216`,
  `cleanup_cli_postcheck_contract_ready=true`, and
  `cleanup_cli_protected_payload_size_gb=396.794`. It
  records `approval_tokens_required=APPROVE_API_DEPENDENCY_INSTALL,APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS,APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS,APPROVE_PRODUCT_DOCKING_EXECUTION,APPROVE_PRODUCT_LICENSE_FILE_CREATION`.
  All execution/deletion/email/external mutation flags remain disabled.

### P0: Goal API Status Surface

The top-level goal state should be available through the local API as well as
through JSON/CSV/MD artifacts and CLIs. This endpoint family is read-only and
must not convert operator-visible blockers into approvals or execution.

Required behavior:

- Register `/goal/status`, `/goal/readiness`, `/goal/actions`,
  `/goal/release-decision`, `/goal/burndown`, and `/goal/api-contract`.
- Read only current local goal artifacts: readiness rollup, operator action
  board, operator intake kit manifest, release decision gate, and release
  burndown work order.
- Surface product/CAMEO/cleanup CLI rollup fields, approval tokens, official
  result requirements, protected cleanup sizes, and release blockers in one
  `/goal/status` response.
- Surface the current goal API surface contract through `/goal/api-contract`
  and include its status in `/goal/status`.
- Preserve `execution_enabled=false`, `action_executed=false`,
  `delete_executed=false`, `archive_executed=false`,
  `externalize_executed=false`, `upload_executed=false`,
  `docking_results_emitted=false`, `prediction_generation_enabled=false`,
  `server_registration_mutated=false`, `outbound_email_enabled=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `api/goal.py` registers read-only goal endpoints and reads only existing
  local artifacts.
- `tools/build_goal_api_surface_contract.py` writes JSON/CSV/MD goal API
  surface contracts from local source files only.
- `api/main.py` includes the goal router.
- `tests/unit/test_api_goal_import.py` verifies route registration, current
  summary propagation, CLI status propagation, row counts, approval-token
  surfacing, and disabled mutation flags when FastAPI TestClient is available.
- `tests/unit/test_build_goal_api_surface_contract.py` verifies current-source
  readiness, unmounted-router blocking, missing status-key blocking, and CLI
  output.
- The current `/goal/status` contract reports
  `status=blocked_goal_release_decision`,
  `readiness_status=blocked_goal_readiness`,
  `operator_action_board_status=operator_actions_required`,
  `operator_intake_kit_status=goal_operator_intake_kit_ready`,
  `goal_api_surface_contract_status=goal_api_surface_contract_ready`,
  `goal_api_surface_ready=true`,
  `release_allowed=false`, `release_blocker_count=13`,
  `operator_action_count=11`, `operator_approval_required_count=7`,
  `approval_token_count=9`, `approval_reclaim_size_gb=49.216`,
  `protected_cleanup_payload_size_gb=396.794`,
  `product_cli_status_set_status=blocked_product_cli_status_set`,
  `cameo_cli_status_set_status=blocked_cameo_cli_status_set`, and
  `cleanup_cli_status_set_status=blocked_cleanup_cli_status_set`.
- `runs/goal_api_surface_contract_current.json` currently reports
  `status=goal_api_surface_contract_ready`, `surface_ready=true`,
  `check_count=7`, `pass_count=7`, `blocker_count=0`,
  `expected_endpoint_count=6`, `missing_endpoint_count=0`,
  `missing_artifact_source_count=0`, `missing_status_key_count=0`,
  `missing_fail_closed_flag_count=0`, and
  `goal_api_contract_endpoint_reads_contract=true`.

### P0: Cleanup Snapshot Preflight

Approval-gated cleanup should not run until large archive/externalize rows have
reviewable snapshot artifacts and stale-delete rows have frozen candidate
manifests. This preflight keeps the cleanup lane safe while still moving toward
actual disk reclamation.

Required behavior:

- Read the transition cleanup work order, ligand-heavy cleanup execution
  preflight, and ligand-heavy cleanup work order.
- Require snapshot artifacts for `archive` and `externalize` rows before
  cleanup execution approval can be treated as safe.
- Treat regenerable local delete candidates as snapshot-optional but still
  postcheck-required.
- Treat ligand-heavy stale payload cleanup as frozen-manifest-ready only when
  the execution preflight is ready and contains candidate rows.
- Preserve `snapshot_created=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_casp17_transition_surface_contract.py tools/build_cleanup_snapshot_preflight.py` writes JSON/CSV/MD snapshot
  preflight packets from existing local artifacts only.
- `tests/unit/test_build_cleanup_snapshot_preflight.py` verifies missing
  archive/externalize snapshot blocking, pass behavior when required snapshots
  exist, frozen ligand-heavy candidate manifests, and CLI output.
- `runs/cleanup_snapshot_preflight_current.json` currently reports
  `status=cleanup_snapshot_preflight_ready`, `row_count=5`,
  `blocked_row_count=0`, `snapshot_required_count=2`,
  `snapshot_missing_count=0`, `frozen_manifest_ready_count=5`,
  `approval_token_count=4`, and `approval_gated_size_gb=49.216`. It records
  `snapshot_created=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Cleanup Snapshot Artifacts

Snapshot-required cleanup rows need reviewable local evidence before the
preflight can clear. This builder creates the missing metadata/listing
artifacts while keeping cleanup execution, deletion, archive movement, and
externalization disabled.

Required behavior:

- Read the cleanup snapshot preflight packet.
- For each `snapshot_required=true` row, walk the local target path and write a
  JSON snapshot artifact containing entry counts, file/dir/symlink counts,
  total file bytes, a bounded listing, a truncated-listing flag, and a metadata
  fingerprint. The top-level artifact summary must also expose a deterministic
  snapshot-set fingerprint over the row metadata and per-row fingerprints.
- Block the artifact row if the target path is missing or cannot be statted.
- Preserve `delete_executed=false` and `external_state_mutated=false`; only
  local snapshot evidence files may be written.

Acceptance evidence:

- `tools/build_cleanup_snapshot_artifacts.py` writes JSON/CSV/MD artifact
  summaries and per-row snapshot JSON artifacts from existing local paths only.
- `tests/unit/test_build_cleanup_snapshot_artifacts.py` verifies successful
  local snapshot creation, missing-target blocking, listing truncation, CLI
  output, snapshot-set fingerprinting, and disabled cleanup/external-mutation
  flags.
- `runs/cleanup_snapshot_artifacts_current.json` currently reports
  `status=cleanup_snapshot_artifacts_ready`, `snapshot_artifact_count=2`,
  `snapshot_ready_count=2`, `snapshot_blocked_count=0`,
  `listing_truncated_count=1`, `total_entry_count=201224`,
  `total_file_count=199360`, `total_dir_count=1312`, and
  `snapshot_set_fingerprint_sha256=04c2f2561bcbe091ba3146a767a2481419b40883c81833cdc6a44477b28bdce0`.
  The generated
  artifacts are
  `runs/cleanup_snapshots/casp17_external_pool__externalize__casp17_massivefold_external_pool_intake.snapshot.json`
  with `entry_count=1561`, `file_count=1485`,
  `listing_truncated=false`, and fingerprint prefix `d4e7a47418e1`; and
  `runs/cleanup_snapshots/legacy_runs_archive__archive__runs_archive.snapshot.json`
  with `entry_count=199663`, `file_count=197875`,
  `listing_truncated=true`, and fingerprint prefix `e56cd030432d`. It records
  `snapshot_created=true`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Cleanup Execution Approval Dossier

Once snapshots and frozen manifests are ready, cleanup still must not execute
until row-specific approval tokens are reviewed. The dossier consolidates the
approval-ready rows and the protected rows so that the operator sees both the
reclaim opportunity and the payloads that must stay out of deletion.

Required behavior:

- Read transition cleanup execution preflight, cleanup snapshot preflight,
  cleanup snapshot artifacts, ligand-heavy cleanup execution preflight, and
  protected cleanup payload review.
- Include snapshot-backed `archive` and `externalize` rows with metadata
  fingerprint, entry-count, file-count, and listing-truncation references.
- Include regenerable local delete candidates and ligand-heavy stale payload
  candidates as approval-required rows.
- Include protected cleanup rows as `policy_blocked_not_promoted`, with no
  approval token and no deletion promotion.
- Preserve `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cleanup_execution_approval_dossier.py` writes JSON/CSV/MD
  approval dossiers from existing local evidence only.
- `tests/unit/test_build_cleanup_execution_approval_dossier.py` verifies
  ready evidence consolidation, missing snapshot blocking, protected row
  non-promotion, snapshot-set summary propagation, CLI output, and disabled
  execution/external-mutation flags.
- `runs/cleanup_execution_approval_dossier_current.json` currently reports
  `status=cleanup_execution_approval_dossier_ready`,
  `approval_row_count=5`, `blocked_approval_row_count=0`,
  `protected_not_promoted_row_count=2`,
  `snapshot_backed_approval_row_count=2`,
  `snapshot_artifact_count=2`, `snapshot_ready_count=2`,
  `snapshot_fingerprint_count=2`, `snapshot_listing_truncated_count=1`,
  `snapshot_truncated_approval_row_count=1`,
  `snapshot_total_entry_count=201224`, `snapshot_total_file_count=199360`,
  `snapshot_set_fingerprint_sha256=04c2f2561bcbe091ba3146a767a2481419b40883c81833cdc6a44477b28bdce0`,
  `approval_reclaim_size_gb=49.216`,
  `protected_payload_size_gb=396.794`,
  `ligand_heavy_candidate_count=40`, `approval_token_count=4`, and
  `approval_tokens_required=APPROVE_ARCHIVE_LEGACY_RUNS,APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS,APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS,APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS`.
  It records `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Cleanup Payload Manifest Lock

Cleanup approval intake must be tied to the exact current payload rows, not
only to path strings. This lock computes stable per-row fingerprints from the
cleanup approval dossier and emits a manifest fingerprint for the full approval
surface.

Required behavior:

- Read the cleanup execution approval dossier.
- Canonicalize approval and protected-not-promoted rows by lane, action, path,
  token, size, candidate count, snapshot evidence, and promotion status.
- Compute a SHA-256 fingerprint for every row and a manifest-level SHA-256
  fingerprint for the complete cleanup approval surface.
- Block lock creation when the dossier is not ready, row identity is missing,
  an approval token is missing, duplicate lock keys exist, or a
  snapshot-required row lacks a snapshot fingerprint.
- Preserve `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cleanup_payload_manifest_lock.py` writes JSON/CSV/MD lock
  packets without executing cleanup.
- `tests/unit/test_build_cleanup_payload_manifest_lock.py` verifies ready
  fingerprint generation, missing snapshot-fingerprint blocking, CLI output,
  and disabled execution/external-mutation flags.
- `runs/cleanup_payload_manifest_lock_current.json` currently reports
  `status=cleanup_payload_manifest_lock_ready`, `row_count=7`,
  `approval_row_count=5`, `protected_not_promoted_row_count=2`,
  `locked_row_count=7`, `blocked_row_count=0`,
  `approval_payload_fingerprint_count=5`, and
  `payload_manifest_fingerprint_sha256=d211e15cdd9f9698df0c5c61c42db88caa5006a95f689a887ba72aed40783542`.
  It records `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Cleanup Operations API Surface

Cleanup needs the same operator-visible read-only surface as the product and
CAMEO lanes. The cleanup API must summarize approval state, reclaimable payload
size, protected payload policy state, and completion state without executing or
promoting any cleanup row.

Required behavior:

- Expose `/cleanup/operations`, `/cleanup/approval-gate`, `/cleanup/postcheck`,
  `/cleanup/completion`, `/cleanup/payloads`,
  `/cleanup/protected-ligand-heavy-review`, and `/cleanup/protected-policy` as
  read-only status routes.
- Surface cleanup approval template path, intake path, required columns, valid
  decisions, required approval tokens, payload fingerprints, and current gate
  rows without approving or executing cleanup.
- Register the cleanup router in `api/main.py`.
- Preserve `execution_enabled=false`, `delete_enabled=false`,
  `delete_executed=false`, and `external_state_mutated=false`.
- Keep protected payload rows policy-blocked until explicit operator policy
  decisions are supplied.
- Expose cleanup approval-token, reclaim-size, protected-payload, postcheck,
  and completion summaries through local cleanup CLI all-status and read-only
  API status surfaces.

Acceptance evidence:

- `api/cleanup.py` exposes the read-only cleanup routes, including the
  `/cleanup/approval-gate` operator approval surface, the
  `/cleanup/postcheck` post-execution evidence contract surface, and the
  `/cleanup/completion` final cleanup evidence surface, plus the
  `/cleanup/protected-ligand-heavy-review` protected payload split surface.
- `tools/build_cleanup_operations_surface_contract.py` writes JSON/CSV/MD
  cleanup API surface contracts without executing cleanup.
- `betelgeuze_cleanup/cli.py` all-status currently aggregates
  `approval_token_count=4`,
  `approval_tokens_required=APPROVE_ARCHIVE_LEGACY_RUNS,APPROVE_DELETE_REGENERABLE_LOCAL_ARTIFACTS,APPROVE_DELETE_STALE_LIGAND_HEAVY_PAYLOADS,APPROVE_EXTERNALIZE_HEAVY_ARTIFACTS`,
  `approval_reclaim_size_gb=49.216`,
  `protected_payload_size_gb=396.794`,
  `protected_policy_change_required_count=2`,
  `postcheck_contract_ready=true`, `postcheck_row_count=7`, and
  `postcheck_blocked_row_count=0`.
- `tests/unit/test_build_cleanup_operations_surface_contract.py` verifies ready
  surface detection, unmounted-router blocking, CLI output, and disabled
  deletion/external-mutation flags.
- `tests/unit/test_api_cleanup_import.py` verifies FastAPI route registration
  and current blocked read-only responses, including approval-gate template,
  required columns, valid decisions, token exposure, postcheck fields, and
  completion fields when FastAPI is installed.
- `runs/cleanup_operations_surface_contract_current.json` currently reports
  `status=cleanup_operations_surface_contract_ready`, `surface_ready=true`,
  `check_count=11`,
  `cleanup_operations_endpoint_present=true`,
  `cleanup_approval_gate_endpoint_present=true`,
  `cleanup_postcheck_endpoint_present=true`,
  `cleanup_completion_endpoint_present=true`,
  `cleanup_payloads_endpoint_present=true`,
  `cleanup_protected_ligand_heavy_review_endpoint_present=true`,
  `cleanup_protected_policy_endpoint_present=true`,
  `delete_executed=false`, and `external_state_mutated=false`.

### P0: Cleanup Execution Operator Approval Gate

Cleanup execution must remain blocked until an operator provides exact
row-specific decisions and approval tokens. This gate turns the dossier into a
fillable CSV template with payload fingerprints and validates any filled CSV
without running cleanup.

Required behavior:

- Read the cleanup execution approval dossier.
- Read the cleanup payload manifest lock and require
  `cleanup_payload_manifest_lock_ready` for CLI approval-gate evaluation.
- Write a fillable operator approval template for all `approval_required` rows.
- Read an operator approval CSV when present and require exact row identity
  (`lane`, `recommended_action`, `path`), matching `payload_fingerprint_sha256`,
  `operator_decision`, and matching `operator_approval_token` before any row is
  marked authorized.
- Allow `skip` decisions without treating them as execution authorization.
- Block duplicate approval rows, approval rows not present in the dossier,
  missing decisions, payload-fingerprint mismatches, token mismatches, and any
  attempt to approve `policy_blocked_not_promoted` protected rows.
- Preserve `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cleanup_execution_approval_gate.py` writes JSON/CSV/MD
  approval-gate packets and a CSV template with payload fingerprints without
  executing cleanup.
- `tests/unit/test_build_cleanup_execution_approval_gate.py` verifies missing
  approval CSV blocking, exact-token authorization, skip decisions, protected
  approval-attempt blocking, payload-fingerprint mismatch blocking, template
  output, CLI output, and disabled execution/external-mutation flags.
- `runs/cleanup_execution_approval_gate_current.json` currently reports
  `status=blocked_cleanup_execution_operator_approval_gate`,
  `source_payload_lock_status=cleanup_payload_manifest_lock_ready`,
  `payload_lock_required=true`,
  `operator_approval_csv_present=false`, `approval_row_count=5`,
  `authorized_row_count=0`, `awaiting_operator_approval_row_count=5`,
  `blocked_row_count=5`, `protected_not_promoted_row_count=2`,
  `authorized_reclaim_size_gb=0`, `total_reclaim_size_gb=49.216`,
  `protected_payload_size_gb=396.794`, `blocker_count=6`, and blockers
  `operator_approval_csv_missing,operator_decision_missing`. It writes
  `runs/cleanup_execution_operator_approval_template_current.csv` and records
  `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Cleanup Postcheck Contract

Approved cleanup must have explicit row-specific postcheck evidence before any
cleanup completion claim is allowed. This contract maps every approval-ready
cleanup row and protected policy row to the required post-execution proof and
refresh commands while remaining read-only.

Required behavior:

- Read the cleanup execution approval dossier, payload manifest lock, operator
  approval gate, and protected cleanup policy gate.
- Require payload fingerprints for approval-ready rows and preserve protected
  rows as policy-blocked, not promoted to deletion.
- Emit one row per approval-required cleanup row and protected policy row.
- Record a row-specific `required_postcheck`,
  `postcheck_refresh_command`, and `global_refresh_required=true`.
- Publish the global refresh sequence that must run after approved cleanup
  execution and before cleanup completion is claimed.
- Preserve `execution_enabled=false`, `delete_executed=false`,
  `archive_executed=false`, `externalize_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_cleanup_postcheck_contract.py` writes JSON/CSV/MD postcheck
  packets without executing cleanup.
- `api/cleanup.py` exposes `/cleanup/postcheck` and summarizes postcheck
  status, row count, blockers, global refresh commands, and disabled execution
  flags.
- `tests/unit/test_build_cleanup_postcheck_contract.py` verifies ready
  postcheck row generation, missing payload-lock blocking, and CLI output.
- `tests/unit/test_api_cleanup_import.py` verifies the read-only postcheck API
  response when FastAPI is installed.
- `runs/cleanup_postcheck_contract_current.json` currently reports
  `status=cleanup_postcheck_contract_ready`,
  `postcheck_contract_ready=true`, `row_count=7`, `approval_row_count=5`,
  `protected_policy_row_count=2`, `blocked_row_count=0`,
  `global_refresh_command_count=9`,
  `approval_reclaim_size_gb=49.216`,
  `protected_payload_size_gb=396.794`, `execution_enabled=false`,
  `delete_executed=false`, `archive_executed=false`,
  `externalize_executed=false`, and `external_state_mutated=false`.

### P0: Cleanup Completion Gate

Release needs a single cleanup completion surface instead of inferring
completion from several preflight packets. This gate audits whether cleanup was
authorized, whether row-specific postcheck evidence is ready, whether
transition cleanup and ligand-heavy cleanup have explicit post-execution
evidence, and whether protected cleanup policy has been resolved.

Required behavior:

- Read cleanup execution approval gate, cleanup postcheck contract, transition
  cleanup execution evidence, ligand-heavy cleanup execution evidence, and
  protected cleanup policy decision gate.
- Require `cleanup_execution_operator_approval_gate_ready` with no awaiting or
  blocked approval rows.
- Require `cleanup_postcheck_contract_ready` with postcheck rows, no blocked
  postcheck rows, and global refresh commands recorded.
- Require `transition_cleanup_execution_complete` with explicit external-state
  mutation evidence for approved archive/externalize/delete actions.
- Require `ligand_heavy_cleanup_execution_complete` with
  `delete_executed=true`.
- Require protected policy resolution through the protected cleanup policy
  decision gate.
- Preserve `execution_enabled=false`, `delete_executed=false`, and
  `external_state_mutated=false` in the gate itself.

Acceptance evidence:

- `tools/build_cleanup_completion_gate.py` writes JSON/CSV/MD cleanup
  completion gates without executing cleanup.
- `api/cleanup.py` exposes `/cleanup/completion` as a read-only projection of
  the current cleanup completion gate, including postcheck counts and disabled
  execution/mutation flags.
- `tests/unit/test_build_cleanup_completion_gate.py` verifies current blocked
  pre-execution state, blocked-postcheck behavior, all-evidence-complete state,
  and CLI output.
- `runs/cleanup_completion_gate_current.json` currently reports
  `status=blocked_cleanup_completion_gate`, `cleanup_complete=false`,
  `stage_count=5`, `blocked_stage_count=4`, `approval_ready=false`,
  `postcheck_contract_ready=true`, `postcheck_row_count=7`,
  `postcheck_blocked_row_count=0`, `postcheck_global_refresh_command_count=9`,
  `transition_cleanup_complete=false`,
  `ligand_heavy_cleanup_complete=false`,
  `protected_policy_resolved=false`, `authorized_reclaim_size_gb=0`,
  `total_reclaim_size_gb=49.216`,
  `protected_payload_size_gb=396.794`, `delete_executed=false`, and
  `external_state_mutated=false`.

### P0: Large Cleanup Surface Drilldown

Large review-only cleanup surfaces need a finer local classifier before any
approval-gated deletion path can be proposed. This step turns broad directories
into run-level and payload-level rows while preserving the current dry-run
protection reasons.

Required behavior:

- Read the current goal operator action board and ligand-heavy cleanup dry-run.
- Inspect only rows marked `review_large_cleanup_surface`.
- Split directory surfaces into immediate children and direct known payload
  directories such as `stage2_trajectory_frames` and `stage2_traj_frames`.
- Attach any existing ligand-heavy dry-run status and reason for each known
  payload path.
- Distinguish `dry_run_delete` payload rows from `kept_*` protected payload
  rows.
- Preserve `delete_enabled=false`, `delete_executed=false`,
  `action_executed=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_large_cleanup_surface_drilldown.py` writes JSON/CSV/MD drilldown
  packets without deleting, moving, archiving, externalizing, or uploading.
- `tests/unit/test_build_large_cleanup_surface_drilldown.py` verifies known
  payload child detection, known payload surface detection, dry-run delete
  status, keep-recent protection status, and CLI output.
- `runs/large_cleanup_surface_drilldown_current.json` currently reports
  `status=large_cleanup_surface_drilldown_ready`, `row_count=247`,
  `known_payload_total_size_gb=406.131`,
  `dry_run_delete_payload_size_gb=6.012`, and
  `dry_run_protected_payload_size_gb=396.794`.

### P0: Protected Cleanup Payload Review

The large cleanup drilldown intentionally keeps protected payload rows out of
approval-gated deletion. This review packet makes that boundary explicit for
the few-hundred-GB payloads.

Required behavior:

- Read the current large cleanup surface drilldown.
- Include only rows whose dry-run status is protected, such as `kept_*`.
- Mark every protected row as requiring an explicit cleanup-policy change before
  deletion approval can be proposed.
- Keep `approval_promoted_count=0`, `delete_enabled=false`,
  `delete_executed=false`, `action_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_protected_cleanup_payload_review.py` writes JSON/CSV/MD review
  packets without deleting, moving, archiving, externalizing, or uploading.
- `tests/unit/test_build_protected_cleanup_payload_review.py` verifies
  protected-only selection, policy-change-required flags, no approval
  promotion, and CLI output.
- `runs/protected_cleanup_payload_review_current.json` currently reports
  `status=protected_cleanup_payload_review_ready`,
  `protected_payload_row_count=2`, `protected_payload_size_gb=396.794`,
  `large_protected_payload_row_count=1`,
  `large_protected_payload_size_gb=396.794`,
  `policy_change_required_count=2`, and `approval_promoted_count=0`.

### P0: Protected Ligand-Heavy Payload Deep Review

Protected parent run rows can hide the actual heavy payload under a direct
payload child while also containing preservation siblings such as delivery
artifacts. This deep review splits those children before any cleanup-policy
decision so the operator can decide on payload-only cleanup without treating the
whole run folder as disposable.

Required behavior:

- Read the protected cleanup payload review.
- For each protected path, split direct known payload children such as
  `stage2_trajectory_frames` from preservation siblings such as
  `stage3_delivery`.
- Mark known payload children as requiring a policy change before deletion.
- Keep preservation siblings out of deletion policy-change accounting.
- Preserve `approval_promoted_count=0`, `delete_enabled=false`,
  `delete_executed=false`, `action_executed=false`, and
  `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_protected_ligand_heavy_payload_deep_review.py` writes
  JSON/CSV/MD deep-review packets without deleting, moving, archiving,
  externalizing, or uploading.
- `api/cleanup.py` exposes `/cleanup/protected-ligand-heavy-review` and
  `/cleanup/payloads` includes the deep-review summary.
- `tests/unit/test_build_protected_ligand_heavy_payload_deep_review.py`
  verifies payload-child versus preservation-sibling separation, no approval
  promotion, and CLI output.
- `runs/protected_ligand_heavy_payload_deep_review_current.json` currently
  reports `status=protected_ligand_heavy_payload_deep_review_ready`,
  `deep_review_row_count=4`, `known_payload_child_count=2`,
  `known_payload_child_size_gb=396.794`,
  `preservation_sibling_count=2`, `preservation_sibling_size_gb=0.0`,
  `largest_known_payload_child_size_gb=396.794`,
  `policy_change_required_for_deletion_count=2`, and
  `approval_promoted_count=0`.

### P0: Protected Cleanup Policy Decision Gate

Protected cleanup rows should not silently block release forever, but they also
must not be promoted to deletion merely because they are large. This gate lets
an operator explicitly keep protected rows, request a cleanup-policy change, or
defer the decision without authorizing deletion.

Required behavior:

- Read the protected cleanup payload review.
- Write a fillable policy-decision template for protected rows.
- Accept only `keep_protected`, `request_policy_change`, or `defer` decisions.
- Treat explicit `keep_protected` decisions for every protected row as policy
  resolved for release-gate purposes.
- Reject approval tokens in this policy gate; deletion approval belongs only in
  a later cleanup approval packet after an explicit policy change.
- Preserve `approval_promoted=false`, `delete_enabled=false`,
  `delete_executed=false`, and `external_state_mutated=false`.

Acceptance evidence:

- `tools/build_protected_cleanup_policy_decision_gate.py` writes JSON/CSV/MD
  policy decision gates and a fillable policy template without promoting
  deletion or mutating external state.
- `tests/unit/test_build_protected_cleanup_policy_decision_gate.py` verifies
  missing policy CSV blocking, explicit keep resolution, policy-change request
  blocking, approval-token rejection, ligand-heavy child payload context, and
  CLI/template output.
- `runs/protected_cleanup_policy_decision_gate_current.json` currently reports
  `status=blocked_protected_cleanup_policy_decision_gate`,
  `operator_policy_csv_present=false`, `protected_payload_row_count=2`,
  `protected_payload_size_gb=396.794`,
  `protected_ligand_heavy_deep_review_status=protected_ligand_heavy_payload_deep_review_ready`,
  `known_payload_child_count=2`, `known_payload_child_size_gb=396.794`,
  `preservation_sibling_count=2`,
  `policy_change_required_for_deletion_count=2`,
  `policy_resolved=false`,
  `awaiting_policy_decision_row_count=2`,
  `policy_change_requested_row_count=0`, `blocked_row_count=2`, and
  `blocker_count=3` with blockers
  `operator_policy_csv_missing,operator_policy_decision_missing`. It records
  `delete_executed=false` and `external_state_mutated=false`, and writes
  `runs/protected_cleanup_policy_decision_template_current.csv` with
  child-payload evidence columns but no approval-token column.

## Architecture Target

The longer-term package split should be:

- `betelgeuze_engine`: force field, integrator, topology, spatial/backend code.
- `betelgeuze_pipeline`: orchestration, candidate generation, selector, gates.
- `betelgeuze_cameo`: receiver, parser, job ledger, exporter, email handoff,
  result-fetcher.
- `betelgeuze_product`: commercial request contracts, local-delivery intake,
  ligand HTVS request gating, and wetlab triage bundle handoff.
- external artifact storage: heavy PDB/mmCIF/tar/trajectory/model artifacts.

The repo should keep source, tests, configs, manifests, and checksums. It should
not keep heavy generated artifacts as committed product state.

## Milestones

### M1: Decision And Scaffold

- Add this PRD.
- Add API import repair.
- Add CAMEO receiver skeleton and tests.
- Add transition cleanup manifest builder or extend existing cleanup tooling.

### M2: Receiver Dry Run

- Accept fixture POST/GET target submissions.
- Persist job ledger rows.
- Parse polymer sequence payloads.
- Produce a local dry-run "received" report.
- Keep prediction generation and outbound email disabled.

### M3: Internal Prediction Wiring

- Connect receiver jobs to an internal pipeline entry point.
- Emit local PDB/mmCIF candidates.
- Add CAMEO-specific PDB/mmCIF validation gates.
- Add model1 selector report.
- Keep outbound email disabled unless explicitly approved.

### M4: Development Server Readiness

- Add uptime and 200-response smoke checks.
- Add results-email dry-run packaging.
- Add operator approval gate for CAMEO registration.
- Add an external-state preflight that fails closed until registration details,
  endpoint URL, contact email, and operator approval are present.

### M5: Public Benchmark Operation

- Register only after M4 is green.
- Run as a development server first.
- Promote to public only after stable intake, prediction, email, and evaluation
  cycles prove reliability.

## Risks

- CAMEO currently emphasizes complex structures, while this repo's most mature
  production lane is restricted local delivery and ligand triage.
- Automated CAMEO participation requires uptime and email behavior that the
  current API does not yet support.
- Model1 selection is critical and not yet packaged as a product-grade service.
- Heavy CASP17 artifacts can slow iteration if not externalized.
- Over-claiming broad MD or commercial parity would conflict with current
  local-delivery claim policy.

## Immediate Next Commands

Suggested local verification before code work:

```bash
python3 -m py_compile api/main.py api/tasks.py api/cameo.py api/casp17.py api/cleanup.py api/goal.py api/product.py betelgeuze_cameo/intake.py betelgeuze_cameo/selector.py betelgeuze_cameo/format_validation.py betelgeuze_cameo/handoff.py betelgeuze_cameo/operator_inputs.py betelgeuze_cameo/repair_preflight.py betelgeuze_cameo/api_dependency.py betelgeuze_cameo/receiver_smoke.py betelgeuze_cameo/capability_preflight.py betelgeuze_cameo/official_results.py betelgeuze_cameo/architecture_validation.py betelgeuze_product/docking_request.py betelgeuze_product/structure_analysis.py betelgeuze_product/structure_report.py betelgeuze_product/readiness.py betelgeuze_product/work_order.py betelgeuze_product/capability_surface.py betelgeuze_product/architecture.py betelgeuze_product/bundle_contract.py betelgeuze_product/delivery_evidence.py betelgeuze_product/pilot_packet.py betelgeuze_product/commercial_independence.py betelgeuze_product/license_decision.py betelgeuze_product/license_options.py betelgeuze_product/service_boundary.py betelgeuze_product/cli.py tools/build_transition_cleanup_manifest.py tools/build_cameo_model1_selection_packet.py tools/build_cameo_format_validation_packet.py tools/build_cameo_dry_run_handoff_packet.py tools/build_cameo_operator_input_validation.py tools/build_cameo_local_format_smoke_inputs.py tools/build_cameo_repair_execution_preflight.py tools/build_cameo_api_dependency_readiness.py tools/build_cameo_receiver_smoke_contract.py tools/build_cameo_capability_preflight.py tools/build_cameo_runtime_repair_work_order.py tools/build_cameo_official_results_intake_gate.py tools/build_cameo_performance_scorecard.py tools/build_cameo_validation_readiness_gate.py tools/build_cameo_validation_operations_dossier.py tools/build_cameo_architecture_validation_contract.py tools/build_cameo_public_registration_approval_gate.py tools/build_product_readiness_gate.py tools/build_product_structure_analysis_report.py tools/build_product_execution_work_order.py tools/build_product_execution_approval_gate.py tools/build_product_capability_surface_contract.py tools/build_product_architecture_contract.py tools/build_product_service_boundary_contract.py tools/build_product_bundle_contract.py tools/build_product_delivery_evidence_contract.py tools/build_product_pilot_packet_contract.py tools/build_product_release_operations_dossier.py tools/build_product_commercial_independence_gate.py tools/build_product_license_decision_gate.py tools/build_product_license_decision_packet.py tools/build_goal_readiness_rollup.py tools/build_goal_operator_action_board.py tools/build_goal_operator_intake_kit.py tools/build_goal_release_decision_gate.py tools/build_goal_release_burndown_work_order.py tools/build_casp17_transition_surface_contract.py tools/build_cleanup_snapshot_preflight.py tools/build_cleanup_snapshot_artifacts.py tools/build_cleanup_execution_approval_dossier.py tools/build_cleanup_payload_manifest_lock.py tools/build_cleanup_postcheck_contract.py tools/build_cleanup_operations_surface_contract.py tools/build_cleanup_execution_approval_gate.py tools/build_cleanup_completion_gate.py tools/build_large_cleanup_surface_drilldown.py tools/build_protected_cleanup_payload_review.py tools/build_protected_ligand_heavy_payload_deep_review.py tools/build_protected_cleanup_policy_decision_gate.py
```

Expected current result: pass.

Suggested first implementation slice:

```bash
python3 -m pytest -q tests/unit/test_betelgeuze_product_structure_analysis.py tests/unit/test_betelgeuze_product_structure_report.py tests/unit/test_betelgeuze_product_docking_request.py tests/unit/test_betelgeuze_product_readiness.py tests/unit/test_betelgeuze_product_work_order.py tests/unit/test_betelgeuze_product_capability_surface.py tests/unit/test_betelgeuze_product_service_boundary.py tests/unit/test_betelgeuze_product_cli.py tests/unit/test_build_product_capability_surface_contract.py tests/unit/test_build_product_architecture_contract.py tests/unit/test_build_product_service_boundary_contract.py tests/unit/test_build_product_execution_approval_gate.py tests/unit/test_betelgeuze_product_bundle_contract.py tests/unit/test_betelgeuze_product_delivery_evidence.py tests/unit/test_betelgeuze_product_pilot_packet.py tests/unit/test_betelgeuze_product_commercial_independence.py tests/unit/test_build_product_commercial_independence_gate.py tests/unit/test_betelgeuze_product_license_decision.py tests/unit/test_betelgeuze_product_license_options.py tests/unit/test_build_product_license_decision_gate.py tests/unit/test_build_product_release_operations_dossier.py tests/unit/test_api_product_import.py tests/unit/test_betelgeuze_cameo_intake.py tests/unit/test_betelgeuze_cameo_selector.py tests/unit/test_betelgeuze_cameo_format_validation.py tests/unit/test_betelgeuze_cameo_handoff.py tests/unit/test_betelgeuze_cameo_operator_inputs.py tests/unit/test_betelgeuze_cameo_repair_preflight.py tests/unit/test_betelgeuze_cameo_api_dependency.py tests/unit/test_betelgeuze_cameo_receiver_smoke.py tests/unit/test_betelgeuze_cameo_capability_preflight.py tests/unit/test_betelgeuze_cameo_official_results.py tests/unit/test_betelgeuze_cameo_performance.py tests/unit/test_betelgeuze_cameo_readiness.py tests/unit/test_betelgeuze_cameo_architecture_validation.py tests/unit/test_api_cameo_import.py tests/unit/test_api_casp17_import.py tests/unit/test_api_cleanup_import.py tests/unit/test_api_goal_import.py tests/unit/test_build_cameo_api_dependency_readiness.py tests/unit/test_build_cameo_receiver_smoke_contract.py tests/unit/test_build_cameo_capability_preflight.py tests/unit/test_build_cameo_runtime_repair_work_order.py tests/unit/test_build_cameo_official_results_intake_gate.py tests/unit/test_build_cameo_validation_operations_dossier.py tests/unit/test_build_cameo_local_format_smoke_inputs.py tests/unit/test_build_cameo_public_registration_approval_gate.py tests/unit/test_build_casp17_transition_surface_contract.py tests/unit/test_build_transition_cleanup_manifest.py tests/unit/test_build_product_pilot_packet_contract.py tests/unit/test_build_goal_readiness_rollup.py tests/unit/test_build_goal_operator_action_board.py tests/unit/test_build_goal_operator_intake_kit.py tests/unit/test_build_goal_release_decision_gate.py tests/unit/test_build_goal_release_burndown_work_order.py tests/unit/test_build_cleanup_snapshot_preflight.py tests/unit/test_build_cleanup_snapshot_artifacts.py tests/unit/test_build_cleanup_execution_approval_dossier.py tests/unit/test_build_cleanup_payload_manifest_lock.py tests/unit/test_build_cleanup_operations_surface_contract.py tests/unit/test_build_cleanup_execution_approval_gate.py tests/unit/test_build_cleanup_completion_gate.py tests/unit/test_build_large_cleanup_surface_drilldown.py tests/unit/test_build_protected_cleanup_payload_review.py tests/unit/test_build_protected_ligand_heavy_payload_deep_review.py tests/unit/test_build_protected_cleanup_policy_decision_gate.py
```

Expected current result: `212 passed, 5 skipped`; the FastAPI runtime endpoint
test is skipped unless `requirements-api.txt` is installed. The latest expanded
verification includes the CAMEO performance threshold-policy module, builder,
and tests; the product API-contract module, builder, and tests; and the cleanup
postcheck/completion contracts, goal API surface contract, and goal-level postcheck/API
propagation tests in addition to the command skeleton above.

## Completion Definition

This PRD is complete when it has been reviewed against:

- current repo state
- official CAMEO help/FAQ requirements
- local delivery claim policy
- CASP17 artifact boundaries

The transition itself is complete only when M1-M5 are implemented and verified.
