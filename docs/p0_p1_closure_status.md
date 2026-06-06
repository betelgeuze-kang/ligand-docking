# P0/P1 Closure Status (2026-06-06)

**Status: CLOSED**

All checklist items in `docs/p0_p1_closure_plan.md` are complete.

## Commits (branch `codex/commercialization-accounting-closure`)

| Commit | Summary |
|--------|---------|
| `4bb45420` | Stop tracking generated runs artifacts and harness trace |
| `a7b1813d` | P0/P1 scope lock, claim guards, packaging, docs, tests |
| `9a554449` | `tools/accounting/` migration + `tools/build_*` shims |
| `d4d2b5ee` | Remaining commercialization branch integration |

## Verification (2026-06-06)

```bash
git status --short | wc -l          # 0
git check-ignore runs/ .betelgeuze/trace.jsonl
python3 -m pytest -q tests/unit/test_p0_p1_closure.py tests/unit/test_api_validated_runner_adapter.py
python3 -m venv /tmp/p1_5 && /tmp/p1_5/bin/pip install . && /tmp/p1_5/bin/betelgeuze-product --help
```

## Notes

- `Dockerfile.product` now uses `requirements-package.txt` + `pip install .` and copies `core/`. Runtime `docker build` was not executed (docker CLI unavailable).
- `api/product.py` remains large (handlers inline); accounting field builders live in `api/product_accounting.py` (386 lines).
