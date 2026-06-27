# Betelgeuze Product Vision (current)

Status: reference. This document turns the benchmark ledger and product contracts into a concrete development direction. It is intentionally claim-safe: it describes what may be built and sold without promoting locked benchmark lanes.

Primary source-of-truth documents:

- `docs/BENCHMARK_LEDGER_CURRENT.md`
- `docs/hbond_backmap_contract.md`
- `docs/gpcr_hard_decoy_suite_contract.md`
- `docs/topk_cascade_architecture_plan.md`
- `docs/local_delivery_claim_policy.md`

## One-line product vision

**Betelgeuze is a local-first molecular docking and structure-analysis appliance that combines fast O(N) coarse screening, O/N/P/S H-Bond BackMap, bounded residual rescoring, top-k pocket refinement, and benchmark-governed claim gates to emit audit-ready evidence bundles without promoting unsupported broad claims.**

## Product identity

Betelgeuze is not positioned as a blanket Schrödinger/OpenMM/Desmond/FEP+ replacement. The current product identity is narrower and stronger:

- local/private execution first,
- ROCm/HIP-first acceleration with fallback-capable backend boundaries,
- restricted kinase / selected GPCR / ion-channel docking and ranking triage,
- O/N/P/S H-bond-aware backmapping to recover chemical interpretability from coarse ligand representations,
- bounded residual AI over physics-derived features,
- benchmark ledger and claim gates that prevent overstatement.

## Claim posture

### Claimable today, with scope boundary

- Restricted local delivery / alpha product wording for guarded kinase, selected GPCR, and ion-channel workflows.
- Tracked lane-specific ranking records such as GPCR A1 independent repeat, ADRB2 target-specific pharmacophore, 1M restricted scale-up quality, frozen-evaluator package preservation, and restricted OpenMM/structure/PDE scorecard green.
- Internal smoke and 1M speed records only as diagnostic/regression/scale evidence.
- H-Bond BackMap as local interpretability evidence when `claim_safe=true`.

### Not claimable yet

- Broad GPCR/router generalization.
- Broad all-atom MD, calibrated solvent/FEP, or AMBER/CHARMM/OpenMM/Desmond parity.
- CASP17 top-tier / win-tier proof.
- Prospective wet-lab hit discovery.
- Full commercial platform replacement.

## Development thesis

The winning path is not to make every ligand all-atom and expensive from the start. The winning path is:

```text
Input structure + ligand library
        |
Structure / ligand health check
        |
Fast O(N) coarse screening
        |
H-Bond BackMap for O/N/P/S polar-site reconstruction
        |
Family-aware bounded residual rescoring
        |
Top-k pocket-local refinement / local-min / micro-MD
        |
Benchmark + uncertainty + claim gate
        |
Evidence bundle + GUI/report
```

This architecture keeps local PC / workstation operation realistic: most candidates stay on the cheap path, while top-k candidates receive increasingly interpretable and expensive treatment.

## Differentiators

### 1. Benchmark Ledger

The benchmark ledger is not marketing copy. It is the source of truth that tells the product which rows are external-safe, which rows are locked, and which phrases are forbidden.

Product implication: customer-facing reports should be generated from ledger-safe wording, not ad hoc result text.

### 2. H-Bond BackMap

H-Bond BackMap keeps the fast 2-bead/coarse path but reconstructs up to four O/N/P/S donor/acceptor sites so the result is interpretable. It is not an accuracy claim by itself; it is a chemical-explanation layer.

Product implication: every top-k candidate table should show `claim_safe`, mapped donor/acceptor count, reason code, and 2-bead-vs-4-bead delta.

### 3. GPCR hard-decoy suite

Broad GPCR remains locked until DRD2, HTR2A, OPRM1, and future required targets clear CI-low/top20 and target-internal decoy separation. This is the next major science blocker.

Product implication: broad GPCR wording should stay impossible in reports until the hard-decoy suite returns `family_claim_safe=true`.

### 4. Top-k cascade

The product must avoid expensive work on every ligand. It should select candidates with cheap global evidence, then apply H-Bond BackMap, residual correction, and pocket-local refinement only to the candidates that justify it.

Product implication: GUI and reports must show where each candidate stopped: baseline, backmapped, residual-rescored, refined, or abstained.

## Roadmap

### Phase 0 — Source-of-truth hardening

- Keep `betelgeuze_product/benchmark_ledger.py` as the curated benchmark source of truth.
- Regenerate `docs/BENCHMARK_LEDGER_CURRENT.md` when benchmark entries change.
- Add CI checks that prevent non-claim scopes from being green or externally claimable.
- Keep product docs linked to the ledger instead of duplicating free-form claims.

Exit criteria:

- Every headline metric has a claim scope, gate status, leakage status, allowed wording, and disallowed wording.
- External-safe statements can be generated or validated from the ledger.

### Phase 1 — Restricted local alpha

Scope:

- kinase,
- selected GPCR lanes,
- ion-channel/TRPV1 lanes,
- H-Bond BackMap report surface,
- evidence bundle and GUI/report integration.

Exit criteria:

- A local run emits a candidate ranking table, H-Bond BackMap report, benchmark-safe claim text, and evidence bundle.
- Locked rows remain visible as blockers but cannot appear as positive claims.

### Phase 2 — Public benchmark harness

Priority public benchmark work:

- CASF/PDBBind pose-success harness,
- symmetry-aware ligand RMSD,
- PoseBusters-style pose validity checks,
- Vina/GNINA comparison adapter using the same inputs and metrics,
- DUD-E or LIT-PCBA enrichment comparison where licensing/data handling permits.

Exit criteria:

- Public benchmark results can be regenerated with a manifest and compared fairly to baseline tools.
- Pose success and enrichment claims have source artifacts, not just local summaries.

### Phase 3 — GPCR hard-decoy closure

Priority targets:

- DRD2,
- HTR2A,
- OPRM1.

Required signals:

- `ranking_pr_auc_ci_low >= 0.45`,
- `top20_hit_rate >= 0.20`,
- `decoys_above_positive_count == 0`,
- no positive out-anchored by top decoys.

Exit criteria:

- `docs/gpcr_hard_decoy_suite_contract.md` gate returns a green family rollup.
- Broad GPCR/router claim stays locked until the family rollup and benchmark ledger both allow it.

### Phase 4 — PocketMD Lite / top-k refinement

Product goal:

- refine only top-k candidates,
- use pocket-local all-atom/proxy refinement or micro-MD,
- report local-min survival, contact persistence, H-bond persistence, clash relief, and uncertainty.

Exit criteria:

- top-k refinement improves report interpretability without breaking local runtime constraints,
- unsupported chemistry abstains with structured reason codes,
- broad all-atom/FEP wording remains locked.

### Phase 5 — Full commercial expansion

Only after public and prospective evidence closes:

- calibrated all-atom parameterization,
- solvent/FEP calibration,
- transporter/CA2/PXR expansion,
- prospective wet-lab loop,
- enterprise/on-prem scheduling, RBAC/OIDC, object store, and audit dashboards.

## Product KPIs

| KPI | current posture | alpha target | beta target |
| --- | --- | --- | --- |
| Restricted local delivery gate | green | keep green | keep green |
| GPCR A1 CI-low | 0.7612 tracked lane | keep >= 0.70 | expand to additional tracked lanes |
| Broad GPCR CI-low | locked / low | >= 0.45 on hard-decoy suite | >= 0.55 on broader held-out suite |
| H-Bond BackMap claim-safe rate | report surface ready | visible per batch | gated by family / chemistry class |
| CASF/PDBBind pose success | harness needed | first public subset | full public benchmark matrix |
| Vina/GNINA comparison | adapter needed | fair subset comparison | repeatable public matrix |
| Pocket-local refinement survival | not broad-claimable | top-k diagnostic | product gate candidate |
| Full all-atom/FEP parity | blocked | blocked | blocked until calibrated evidence |

## Messaging template

Allowed short description:

> Betelgeuze is a local-first restricted docking and structure-analysis appliance for guarded kinase, selected GPCR, and ion-channel workflows. It combines fast coarse screening, O/N/P/S H-Bond BackMap, bounded residual rescoring, and benchmark-governed claim gates to produce audit-ready evidence bundles.

Required caveat:

> Broad GPCR/router, full all-atom MD/FEP, CASP17 win-tier, and general commercial replacement claims remain fail-closed until their benchmark gates and evidence receipts close.

## Immediate next work

1. Keep benchmark ledger generation and docs in sync.
2. Wire H-Bond BackMap report rows into candidate-level output and GUI/report surfaces.
3. Build the CASF/PDBBind public benchmark harness and Vina/GNINA comparison adapter.
4. Convert DRD2/HTR2A/OPRM1 diagnostics into the GPCR hard-decoy suite input table.
5. Add PocketMD Lite as a top-k-only refinement/reporting lane.
