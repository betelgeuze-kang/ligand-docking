# H-Bond BackMap (ONSPS-4) — Product Contract

Status: reference. Product-differentiating feature surface.

Source of truth:
- Engine: `betelgeuze_engine/backmapping/onsps.py` (numpy/RDKit)
- Report/governance: `betelgeuze_product/hbond_backmap_report.py` (dependency-free)
- Claim wording: `.kiro/steering/claim_safe_wording.md`,
  `docs/BENCHMARK_LEDGER_CURRENT.md`

## What it is

H-Bond BackMap keeps the fast, cheap 2-bead coarse screening path but
reconstructs up to **four O/N/P/S donor/acceptor sites** (ONSPS-4) so that
results can be **H-bond-aware and interpretable**. It is a differentiator
because it adds chemical interpretability to a coarse representation without
paying full all-atom cost.

```
2-bead trajectory frame + SMILES + pocket context
        |
   ONSPS-4 polar-site reconstruction (RDKit ETKDG + chemistry roles)
        |
   up to 4 O/N/P/S donor/acceptor beads (Kabsch-aligned into the pocket frame)
        |
   H-bond-aware rescoring evidence + claim-safe report
```

## Claim boundary (must hold)

H-Bond BackMap is **local interpretability evidence**, not a docking-accuracy or
binding-affinity claim, and not a substitute for all-atom MD. The report never
states "more accurate". A candidate is **`claim_safe`** only when:

- the engine produced an **RDKit-ETKDG** mapping (`mapping_source = rdkit_etkdg`),
- the 2-bead input geometry is valid (`input_bead_count >= 2`,
  `backmap_status = ok`), and
- at least one polar site was mapped (`mapped_site_count > 0`).

Otherwise the report is **`evidence_only`** with a structured reason and is never
presented as a positive H-bond claim. Known evidence-only reasons:

| reason_code | meaning |
| --- | --- |
| `onsps_fallback_not_claim_safe` | RDKit unavailable/failed; a SMILES character fallback was used |
| `no_onsps_sites` | no O/N/P/S donor/acceptor sites found |
| `invalid_two_bead_geometry` | the 2-bead input frame was empty/malformed |

## Report fields (per candidate)

`build_hbond_backmap_report(evidence, *, entry_id, two_bead_vs_four_bead_delta, hbond_angle_score)`:

- `evidence_tier`: `claim_safe` | `evidence_only`
- `claim_safe`: bool
- `mapped_site_count`, `site_count`, `max_onsps_sites`
- `donor_count`, `acceptor_count`, `polar_site_elements`
- `mapping_source`, `backmap_status`
- `reason_code`, `reason_detail` (structured; empty when claim_safe)
- `two_bead_vs_four_bead_delta` (optional; from the rescoring path)
- `hbond_angle_score` (optional; from `onsps.hbond_angle_score`)
- `claim_boundary`

## Batch report (candidate table / KPI)

`build_hbond_backmap_batch_report(rows)` aggregates per-candidate reports into a
summary with the product KPI:

- `claim_safe_rate` — fraction of candidates with a claim-safe H-bond
  reconstruction (the **H-Bond BackMap claim-safe rate** KPI),
- `claim_safe_count` / `evidence_only_count`,
- `total_donor_sites` / `total_acceptor_sites`,
- `evidence_only_reason_counts` — why candidates fell back.

## GUI / evidence-bundle usage

- Show the per-candidate H-Bond BackMap overlay (donor/acceptor sites) only when
  `evidence_tier = claim_safe`; render `evidence_only` rows distinctly with the
  `reason_code`.
- Surface `claim_safe_rate` on the candidate table header as a quality signal.
- Include the report rows in the delivery evidence bundle so reviewers can audit
  which candidates had interpretable H-bond reconstruction.

## Out of scope

- No accuracy/affinity claim, no all-atom MD substitution.
- Engine wiring that emits `two_bead_vs_four_bead_delta` from the live rescoring
  path runs under numpy/RDKit and is validated in CI, not in this contract layer.
