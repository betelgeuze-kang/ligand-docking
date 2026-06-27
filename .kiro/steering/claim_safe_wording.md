---
inclusion: always
---

# Claim-Safe Wording Rules

These rules govern how Betelgeuze benchmark results and product capabilities are
described in any external-facing text (README, docs, PR descriptions, investor
or customer messaging). They exist because the repo intentionally holds both
strong evidence and blocked/reject evidence at different claim layers; conflating
them produces overclaims.

Authoritative scope ledger: `docs/BENCHMARK_LEDGER_CURRENT.md` /
`betelgeuze_product/benchmark_ledger.py`. When in doubt, cite a ledger entry and
use its `allowed_external_wording`; never exceed its `claim_boundary`.

## Hard rules

1. **"Commercial-tool level" only for the restricted ranking lane.**
   PR-AUC 0.8719 / CI-low 0.7612 / top20 1.00 is a GPCR A1 / ADRB2
   *restricted, frozen-evaluator, out-of-fold* result. Do NOT generalize it to
   broad GPCR/router, full docking pose/free-energy parity, or "commercial-tool
   parity" without that scope qualifier.

2. **"ROCm-first, backend-fallback-capable" — not "AMD-only native".**
   The engine uses a Rust/HIP backend when available and falls back to
   PyTorch/CPU otherwise (`FORCE_RUST_HIP` / config `require` can harden it).
   Describe it as "ROCm/HIP-first, CPU/PyTorch-fallback-capable".

3. **"encrypted-at-rest when configured" — not unconditional "end-to-end encrypted".**
   The private payload store separates raw customer input from the public
   ledger and encrypts at rest *when the store is configured*; it fail-closed
   no-ops otherwise. Deployment must treat store configuration as a release
   preflight hard gate.

4. **All-atom MD: "internal united-atom/proxy refine tier exists".**
   Do NOT call it AMBER/CHARMM/OpenMM/Desmond-grade calibrated all-atom MD.
   Parameter calibration is `internal_proxy_uncalibrated`.

5. **Broad GPCR / full all-atom MD / FEP / general Schrödinger-class parity stay
   claim-locked** until public benchmark + hard-decoy evidence closes
   (`ranking_pr_auc_ci_low >= 0.45`, `top20_hit_rate >= 0.20` on the relevant
   panel). CASP17 competitive proof is `scaffold_only` (fail-closed) until native
   structures publish.

## Product positioning (approved)

Betelgeuze is a **ROCm-first, local-private molecular docking & structure-analysis
appliance**: fast O(N) coarse screening, O/N/P/S H-bond backmapping (ONSPS-4),
bounded residual rescoring, top-k pocket-local refinement, and benchmark-governed
claim gates that emit auditable evidence bundles. It is NOT positioned as a
general-purpose docking/MD platform or a Schrödinger replacement.

## Never

- Threshold relaxation, fake-pass wording, or manual metric editing.
- Presenting internal smoke / regression-guardrail numbers (e.g. nightly
  ROC-AUC/PR-AUC/EF1/BEDROC at their maxima) as external hard-benchmark claims.
- Treating a stale/missing `runs/` artifact as green; assume blocked/internal-review.
