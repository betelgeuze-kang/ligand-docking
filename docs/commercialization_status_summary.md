# Commercialization Status Summary (Human Index)

Generated index only. **Do not hand-edit green/closed claims here.**

| Source of truth | Path |
|-----------------|------|
| Readiness JSON packet | `runs/commercialization_readiness_current.json` |
| P0/P1 closure | `docs/p0_p1_closure_status.md` |
| P2 expansion | `docs/p2_expansion_plan.md` |
| Code gates | `api/simulation_scope.py`, `core/claim_boundary.py` |

## Current product scope (code-enforced)

- `/simulate` requires `runner_profile_id` (ligand HTVS / backmapping validated runners).
- Generic MD simulation is unsupported.
- Placeholder topology cannot promote to general-MD accuracy grades.

## Regenerate

```bash
python3 tools/accounting/build_commercialization_readiness_report.py
python3 -m pytest -q tests/unit/test_commercialization_report_parity.py tests/unit/test_p0_p1_closure.py
```

## Claim boundary

This file is a navigation index. Authoritative status lives in generated JSON packets and passing code-gate tests.
