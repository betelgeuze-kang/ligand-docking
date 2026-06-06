# P0/P1 Closure Status (2026-06-06)

Implementation pass completed for code/test/doc items below. See `docs/p0_p1_closure_plan.md` for the original plan.

## Closed

| Item | Evidence |
|------|----------|
| P0-1 scope lock | `runner_profile_id` required in `api/models.py`; `/simulate` returns 400/422 without profile; `api/simulation_scope.py`; README API section |
| P0-2 claim guards | `core/claim_boundary.py`, `core/topology.py` fidelity metadata, `api/result_manifest.py` required fields + promotion gate |
| P1-3 accounting isolation | `api/product_accounting.py` (386 lines); `tools/accounting/` (1188 builders + README + `build_target_packet.py`); shims at `tools/build_*.py` |
| P1-5 packaging | `pyproject.toml` includes `api*`, `core*`; `requirements-package.txt`; `betelgeuze_product/runtime_paths.py`; CLIs use `repo_root()` |
| Tests | `tests/unit/test_p0_p1_closure.py` + existing validated-runner tests green |

## Metrics (Phase E4)

| Metric | Before | After |
|--------|--------|-------|
| `api/product.py` lines | 9353 | 8978 |
| `api/product_accounting.py` | — | 386 |
| Top-level `tools/build_*.py` | 1187 impl | 1188 shims → `tools/accounting/` |

## Partial / Follow-up

| Item | Status | Reason |
|------|--------|--------|
| P1-4 git clean tree | Partial | `.gitignore` extended; `runs/` + `.betelgeuze/trace.jsonl` untracked from index; ~2105 pre-existing WIP changes remain in working tree (not part of this pass) |
| Phase A3/A4 commits | Not done | User commit policy: batch commit of legacy WIP still required separately |
| Dockerfile.product verify | Not run | Requires container build in this environment |

## Verification commands

```bash
python3 -c "import api.main"
python3 -m pytest -q tests/unit/test_p0_p1_closure.py tests/unit/test_api_validated_runner_adapter.py
python3 -m venv /tmp/p1_5 && /tmp/p1_5/bin/pip install . && /tmp/p1_5/bin/betelgeuze-product --help
git check-ignore runs/foo_current.json .betelgeuze/trace.jsonl
```
