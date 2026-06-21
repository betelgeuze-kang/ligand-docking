# OpenCode task: promote backmapping scoring runner to engine-owned implementation

Web access: disabled.

You are an implementation worker. Codex owns final review, verification, commit/push decisions, and acceptance.

## Goal

Promote the product backmapping scoring runner so the canonical implementation lives in:

```text
betelgeuze_engine/product/runners/backmapping_scoring.py
```

The legacy product path must become a compatibility shim:

```text
tools/product/run_ligand_backmapping_scoring.py
```

The allowlisted root runner path must remain intact:

```text
tools/run_ligand_backmapping_scoring.py
```

## Constraints

- Do not read, print, summarize, or request `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not commit, push, delete unrelated files, deploy, publish, or mutate external state.
- Do not broaden the task into HTVS, GUI, Docker, CASP, or scientific claim promotion.
- Preserve existing behavior and CLI surface.
- Preserve `core/` as compatibility layer.
- Do not change active CASP17 boundaries.
- Prefer focused tests; do not run huge suites unless needed.

## Expected implementation shape

1. Move/copy the implementation currently in `tools/product/run_ligand_backmapping_scoring.py` into `betelgeuze_engine/product/runners/backmapping_scoring.py`.
2. Adjust repo-root path bootstrapping if needed because the file depth changes.
3. Replace `tools/product/run_ligand_backmapping_scoring.py` with a canonical module alias shim, similar in spirit to the current Top-K compatibility shim:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys as _sys

from betelgeuze_engine.product.runners import backmapping_scoring as _module
from betelgeuze_engine.product.runners.backmapping_scoring import *  # noqa: F401,F403

_sys.modules[__name__] = _module

if __name__ == "__main__":
    raise SystemExit(_module.main())
```

4. Update KPI/report/bundle tests or helpers only if they currently classify backmapping as adapter-owned. Existing Top-K engine-owned checks are a useful pattern, but do not duplicate more than needed.
5. Add/adjust a regression test proving:
   - engine module exposes `main` and `_frame_mmpbsa_proxy`;
   - `tools.product.run_ligand_backmapping_scoring` aliases the engine module;
   - the compatibility shim is not a self-implementation;
   - product runner no-core-import gate still passes.

## Verification to run

Run the narrowest useful checks:

```bash
python3 -m py_compile \
  betelgeuze_engine/product/runners/backmapping_scoring.py \
  tools/product/run_ligand_backmapping_scoring.py

python3 -m pytest -q tests/unit/test_engine_transition_shims.py
```

If KPI/bundle code changes, also run:

```bash
python3 -m pytest -q \
  tests/unit/test_build_ai_md_engine_kpi_report.py \
  tests/unit/test_build_ai_md_product_evidence_bundle.py
```

## Return summary

Return only a concise summary:

- files changed
- behavior changed
- tests run and result
- blockers or risks

Do not include full logs.
