# Product Full Implementation Plan

Status: active direction document  
Owner lane: product engineering + commercial evidence  
Related: `docs/complete_commercial_product_gap_analysis.md`, `docs/architecture_validation_test_packages.md`, `docs/local_delivery_claim_policy.md`

## Purpose

This document is the **master implementation plan** for evolving the repository from
accounting-strong restricted delivery to a fully independent commercial product.
It defines workstreams, dependencies, completion criteria, and claim boundaries.

**No calendar deadlines** — phases complete when their Definition of Done is met.

Track live progress in `.betelgeuze/work_queue.md`.

---

## North Star (4 axes)

| Axis | Target |
|---|---|
| Scientific precision | Defensible pose / ΔG / complex metrics on public sets |
| Functional completeness | Structure → analysis → docking → score → refine → bundle |
| Independent execution | Zero external docking/MD engines (RDKit informatics allowed) |
| Commercial operations | Self-hosted deploy, reproducibility, SLA, honest claim boundaries |

## Product tiers

| Tier | Scope | Execution | Science | Claim |
|---|---|---|---|---|
| **α** | gpcr / ion_channel / kinase | API → queue → worker → bundle (profile-based) | 2-bead HTVS + refine proxy | Restricted local delivery pilot |
| **β** | Tier α | Same | refine stable + Package B subsets | Externally defensible numbers |
| **γ** | breadth expansion | Hosted TLS/pager/rollout | all-atom + FEP scaffold | General platform (gated) |

**Current baseline:** Tier α accounting largely closed; execution wiring and science depth in progress.

---

## Fixed principles

1. Accounting green ≠ science complete (`evidence_depth` / overclaim guards stay on).
2. Fail-closed default: `runner_profile_id`, scope guard, abstention, `execution_enabled=false` at API layer unless env + readiness both true.
3. Two-tier physics: **fast** (2-bead O(N) screening) → **refine** (top-K MM-GBSA / all-atom local).
4. AI = bounded corrector on physical core; labels from refine tier when production_guarded.
5. Package order: **A → B → C live** (B before C live claims).
6. `restricted_unattended_execution_ready` ≠ `general_platform_claim_allowed`.

---

## Workstream map

```
WS0  Evidence & claim governance (maintain)
WS1  Shared prerequisites PRE-01..07
WS2  Execution wiring E5                    ← Tier α unlock
WS3  Delivery & bundle surface
WS4  Fast tier physics E1
WS5  Refine tier physics E2–E4              ← Tier β science core
WS6  Docking completeness (pose/pocket/ΔG)
WS7  Structure analysis surface
WS8  AI residual production
WS9  Hosted / deploy ops
WS10 Package B external defense             ← Tier β trust
WS11 Package C live competition             ← Tier γ credibility
WS12 Scope breadth expansion
WS13 Product UX & results
WS14 Legal & repo hygiene
```

**Parallel OK:** WS2 ↔ WS4–WS5  
**Sequential:** WS10 before WS11 live claims

---

## WS0 — Evidence & claim governance

**Direction:** Extend summary-vs-row audits; keep `claim_promotion_allowed=false` default; split Package A/B/C operator reports per run tag + git SHA.

**DoD:** No required test closes on summary-only evidence when rows are blocked.

**Artifacts:** `build_architecture_validation_evidence_depth.py`, architecture validation report, `/product/architecture-validation`.

---

## WS1 — Shared prerequisites

**Direction:** Regeneration orchestrators fail hard when PRE artifacts stale.

**DoD:** Preflight red blocks bundle/delivery/execution promotion.

**Entry:** `tools/build_local_delivery_environment_manifest.py`, accuracy parity, nightly stage6.

---

## WS2 — Execution wiring (Tier α)

**Direction:**

1. Profile promotion: `build_api_runner_profile_promotion_readiness.py` → blocked 0.
2. Runtime: api-server + api-worker + api-docking-dispatch (`deploy/docker-compose.product.yml`).
3. Env: `API_VALIDATED_RUNNER_ENABLED=1` only when `restricted_unattended_execution_ready`.
4. E2E evidence: `build_api_docking_dispatch_e2e_evidence.py` (A-40).
5. Gate: `build_restricted_unattended_execution_readiness.py`.

**DoD:** Restricted scope: authenticated client → job → dispatch → worker → signed manifest; rollback via profile `enabled=false`.

**Do not:** Open generic `/simulate`; bypass scope guard; flip global platform claims.

---

## WS3 — Delivery & bundle surface

**Direction:** Bundle carries claim boundary, evidence tier, runner_profile_id, gate fingerprints.

**DoD:** `validate_local_delivery_bundle.py` + verdict gate mismatch 0 = only delivery-ready path.

---

## WS4 — Fast tier physics

**Direction:** Remove placeholder alanine topology; sequence-mapped CG; multi-start; stage policy labels.

**DoD:** A-01 blind HTVS operational gate pass maintained.

---

## WS5 — Refine tier physics

**Direction:**

1. `config/ligand_engine_production.json` stage3b refine cascade.
2. `core/refine_physics.py`, `mm_gbsa.py`, `allatom_forcefield.py`.
3. top-K only via `run_ligand_physics_refinement.py`.
4. Calibration via `core/score_calibration.py`.
5. FEP scaffold after MM-GBSA Spearman defense (Tier γ).

**DoD:** Refine improves ranking Spearman on held-out slice; B-31 ready.

---

## WS6 — Docking completeness

**Direction:** `core/pocket_detection.py`, `core/pose_generation.py` → HTVS materialization; pose clustering; failure taxonomy (B-02 phase 3).

**DoD:** SMILES + PDB → ensemble → ranked shortlist → refine without external engines.

---

## WS7 — Structure analysis

**Direction:** Quality report (clash, Ramachandran), TM/LDDT proxy, multichain/membrane prep.

**DoD:** Arbitrary PDB → standard quality + alignment JSON.

---

## WS8 — AI residual production

**Direction:** Refine labels → `build_refine_tier_residual_training_dataset.py`; family models; shadow→assist→production_guarded.

**DoD:** production_guarded uses refine labels; assist gate + no ranking regression.

---

## WS9 — Hosted ops

**Direction:** TLS ingress smoke, pager delivery, rollout/rollback drill, tenant quota SLI/SLO.

**DoD:** Real deploy environment passes deploy → health → synthetic job → rollback.

---

## WS10 — Package B external defense (Tier β)

**Direction:** B-02 PDBbind/CASF subset + taxonomy; B-11 BM5; B-21 speedpack A/B; B-31 MM-GBSA validation; GPCR CI-low ≥ 0.45.

**Orchestrator:** `tools/product/run_package_b_external_defense_regeneration.py`

**DoD:** Reproducible public-set report + CI-low threshold for claim promotion review.

---

## WS11 — Package C live competition (Tier γ)

**Direction:** CAMEO multi-target intake; registration/email operator track; CASP strict-blind replay internal only.

**Orchestrator:** `tools/run_competition_benchmark_regeneration.py`

**DoD:** Official CAMEO intake ≥ N targets + operator evidence; disclaimers on all competition outputs.

---

## WS12 — Scope breadth

**Direction:** Transporter → CA2/PXR → IDP → general platform (each with quantitative evidence).

**DoD:** Blocked claim scopes 0; allowed families ≥ 6 before platform flag.

---

## WS13 — Product UX

**Direction:** Customer report with pose, ΔG interval, abstention, evidence links; job status API.

**DoD:** Non-expert can interpret bundle without operator runbook.

---

## WS14 — Legal & hygiene

**Direction:** License/redistribution decision; cleanup execution; tools/ batch3 separation.

**DoD:** Documented legal path + cleanup executed.

---

## Tier α runtime unlock (operator)

```bash
# 1) Configure deploy env (copy example, set secrets, keep API_VALIDATED_RUNNER_ENABLED=1)
cp deploy/docker-compose.product.env.example deploy/docker-compose.product.env

# 2) Start 3-process stack (api-server + api-worker + api-docking-dispatch)
./deploy/run_tier_alpha_product_stack.sh

# 3) Local smoke (no docker required): live ledger evidence_mode=live_job
python3 tools/run_tier_alpha_adrb2_dispatch_smoke.py

# 4) Regenerate readiness + architecture report
python3 tools/run_product_full_implementation_regeneration.py
# or include smoke in one chain:
python3 tools/run_product_full_implementation_regeneration.py --run-dispatch-smoke
```

Exit: `restricted_unattended_execution_runtime_ready=true`, E2E `evidence_mode=live_job`.

| Orchestrator | Scope |
|---|---|
| `tools/run_product_full_implementation_regeneration.py` | Tier α product wiring + capability + architecture report |
| `tools/run_package_b_external_defense_regeneration.py` | Tier β Package B refresh |
| `tools/run_competition_benchmark_regeneration.py` | Package C competition lane |

```bash
python3 tools/run_product_full_implementation_regeneration.py
python3 tools/run_package_b_external_defense_regeneration.py
python3 tools/run_competition_benchmark_regeneration.py
```

---

## Master Definition of Done

| Area | Metric |
|---|---|
| Precision | DockQ / pose RMSD / LDDT-PLI on public sets |
| Free energy | MM-GBSA ΔG vs experiment Spearman |
| Independence | External docking/MD calls = 0 |
| Execution | Restricted API E2E |
| Benchmark | CASF/PDBbind/BM5 reproducible reports |
| GPCR | scaleup CI-low ≥ 0.45 |
| Ops | TLS/pager/rollout/rollback pass |
| Scope | blocked claims = 0 (platform promotion) |
| Trust | abstention/uncertainty in bundle + API |

---

## Claim boundary (always)

- Tier α: restricted `gpcr`, `ion_channel`, `kinase` delivery with bundle evidence only.
- Tier β: public benchmark numbers with proxy disclaimers where applicable.
- Tier γ: competition comparison only after Package C operator evidence.
- Never: accounting green = Schrödinger parity; local replay = official CASP ranking.
