# Commercialization Status Summary (Human Index)

Generated index only. **Do not hand-edit green/closed claims here.**

Status is reported on four separate axes and must never be collapsed into one
"readiness" verdict. The authoritative axis values live in the generated
four-axis packet below; every other row in this table is lane-specific detail
that may not be read as a status promotion on any axis.

| Source of truth | Path |
|-----------------|------|
| Four-axis product status (authoritative) | `docs/PRODUCT_MATURITY_STATUS_CURRENT.md` / `runs/product_maturity_status_current.json` |
| Readiness JSON packet | `runs/commercialization_readiness_current.json` |
| P0/P1 closure | `docs/p0_p1_closure_status.md` |
| P2 expansion | `docs/p2_expansion_plan.md` |
| Engine · AI refinement roadmap | `docs/independent_engine_ai_refinement_roadmap.md` (**CLOSED**) |
| Code gates | `api/simulation_scope.py`, `core/claim_boundary.py` |

## Status axes (reported separately, never merged)

- `distribution_version`: what artifact version exists.
- `scientific_maturity`: what the science actually supports.
- `benchmark_maturity`: what the benchmark evidence actually covers.
- `product_maturity`: what may be offered to whom.

A green result on one axis does not raise any other axis. Axis values are
operator-maintained in `config/product_maturity_status_current.json` and
rendered by `tools/product/build_product_maturity_status.py`.

## Current product scope (code-enforced)

- `/simulate` requires `runner_profile_id` (ligand HTVS / backmapping validated runners).
- Generic MD simulation is unsupported.
- Placeholder topology cannot promote to general-MD accuracy grades.

## Regenerate

```bash
python3 tools/product/build_product_maturity_status.py
python3 tools/accounting/build_commercialization_readiness_report.py
python3 -m pytest -q tests/unit/test_product_maturity_status.py tests/unit/test_commercialization_report_parity.py tests/unit/test_p0_p1_closure.py
```

## Claim boundary

This file is a navigation index. Authoritative status lives in generated JSON packets and passing code-gate tests.
