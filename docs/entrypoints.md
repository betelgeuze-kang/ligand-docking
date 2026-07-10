# Entrypoints By Reviewer Type

This repository intentionally keeps several scientific and product lanes in one
place. Use this guide to choose the narrow starting point before reading deeper
status packets.

## Fast Routing

| Reviewer type | Start here | Then read | What this lane can claim now |
| --- | --- | --- | --- |
| Independent Engine v2 roadmap reviewer | `docs/independent_engine_v2_commercial_roadmap.ko.md` | `docs/independent_engine_v2_architecture.md`, `docs/independent_engine_v2_migration_matrix.md`, `config/independent_engine_v2_capabilities.yaml` | V2-0 internal CPU scaffold and long-term dependency/exit-gate plan only; scientific, docking, MD, GPU, and commercial claims remain blocked. |
| Restricted local-delivery reviewer | `README.md`, `docs/local_delivery_runbook.md` | `docs/local_delivery_bundle_schema.md`, `docs/local_delivery_claim_policy.md`, `docs/post_green_improvement_plan.md` | Guarded local delivery only for the documented restricted scope when the bundle validator and verdict gate are green. |
| Dependency/package reviewer | `docs/dependency_matrix.md` | `requirements-package.txt`, `requirements.txt`, `requirements-api.txt`, `requirements-dev.txt`, `pyproject.toml` | Dependency placement and install-surface intent. |
| Product API reviewer | `README.md#product-api-simulate` | `api/`, `config/api_validated_runner_profiles/README.md`, `docs/tier_beta_vertical_slice_current.md` | Validated-runner ligand HTVS/backmapping scoring API only; not generic MD simulation. |
| CASP17 lane reviewer | `casp17/WORKBENCH.md` | `casp17/CASP17_CURRENT_STATUS_REPORT.md`, `casp17/CASP17_WIN_TIER_GOAL.md`, `docs/casp17_participation_gate_2026-05-21.md` | Local readiness and operator-review scaffolding only; no CASP submission or win-tier claim. |
| CAMEO / competitive benchmark reviewer | `docs/competition_benchmark_status_current.md` | `docs/architecture_validation_test_packages.md`, `docs/cameo_transition_prd.md` | Local CAMEO/CASP readiness evidence; no public live-server or leaderboard claim unless separately proven. |
| Ligand HTVS reviewer | `docs/product_full_implementation_plan.md` | `betelgeuze_product/htvs_command.py`, `tools/build_ligand_scaleup_suite_status.py`, relevant `runs/*ligand*` evidence if present locally | Restricted tracked-suite evidence, not broad commercial discovery parity. |
| Backmapping / hbond reviewer | `docs/hbond_backmap_contract.md` | `betelgeuze_engine/backmapping/`, `betelgeuze_product/hbond_backmap_report.py`, local bundle hbond report attachments when present | Evidence-bundle chemistry/backmapping review surface when RDKit-backed evidence is available. |
| Wetlab T. cruzi PDE reviewer | `README.md#t-cruzi-pde-evidence-trail` | `docs/wetlab_validation_packet.md`, `docs/post_p0_evidence_closure_status.md`, `docs/wetlab_packets/README.md` | Selected all-atom computational evidence is green; wetlab-proven hit claim remains blocked. |
| GPCR hard-decoy reviewer | `docs/gpcr_hard_decoy_suite_contract.md` | `docs/gpcr_hard_decoy_suite_operator_runbook.md`, `docs/post_p0_evidence_closure_status.md`, `docs/broad_claim_unlock_roadmap.md` | Diagnostic and tracked ranking evidence only until broad GPCR unlock gates pass. |
| Broad-claim reviewer | `docs/broad_claim_unlock_roadmap.md` | `docs/local_delivery_claim_policy.md`, `docs/release_claim_evidence_ladder.md`, relevant claim-receipt artifacts | Broad GPCR, wetlab proof, and platform/router/scorer promotion are separate blocked checklists. |

## Lane Boundaries

- Independent Engine v2 and the legacy/restricted product lane have separate
  capability states. A green legacy delivery or product-operations receipt
  does not complete a v2 scientific, benchmark, GPU, or commercial gate.
- CASP17 uses only the repo's internal torch/coarse-grain physics path for the
  active lane. Do not use public/template structures, public target lookup,
  AlphaFold-family systems, or other-team models for active CASP17 work.
- CAMEO and CASP readiness documents are local operator gates unless a human
  owner explicitly approves registration, external submission, deployment, or
  publication.
- Product API review starts from validated runner profiles. Generic
  molecular-dynamics simulation through `/simulate` is intentionally unsupported.
- Wetlab PDE evidence supports computational readiness and selected all-atom
  closure, not experimental hit validation.
- GPCR hard-decoy work is a measured blocker-reduction lane. It is not automatic
  scorer/router/platform promotion.

## Clean-Clone Expectations

A clean clone contains source, tests, docs, schemas, templates, and lightweight
figures. It does not contain local `runs/`, generated trajectory arrays,
delivery bundles, model checkpoints, or local evidence caches. Reviewers should
expect local evidence-gate commands to fail closed until those artifacts are
regenerated or supplied as a reviewed bundle.

Use `README.md#clean-clone-evidence-reproduction` for the reproducibility
recipe.
