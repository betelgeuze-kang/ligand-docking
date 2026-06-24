# Cursor Worker Slice: RDKit-Missing Synthetic Smoke

You are Cursor Agent acting as an implementation worker. Default model: Composer 2.5. Codex owns risk boundaries, targeted review, verification, and final acceptance.

## Task

Implement the next objective item: make the generated-pose smoke path safe in lightweight CI where RDKit is not installed.

Current context:
- `tools/accounting/build_pdbbind_casf_pose_affinity_results.py` now has optional `--generate-poses`.
- It currently imports `from rdkit import Chem` at module import time.
- Tests in `tests/unit/test_build_pdbbind_casf_pose_affinity_results.py` use RDKit fixtures for normal replay/generated mode.
- Objective asks specifically for RDKit-missing lightweight CI synthetic smoke handling.

Implement the smallest correct fix:
- The builder module must remain importable if RDKit is absent.
- Replay mode may still fail closed or block row-level RMSD if real RDKit-pickled ligands cannot be parsed, but it must not crash at import.
- Generated-pose smoke mode must produce an explicit no-RDKit diagnostic/blocker instead of raising an unhandled exception.
- Add a synthetic unit test that simulates RDKit unavailable without requiring an actual RDKit-free environment. Prefer monkeypatching module globals such as `Chem` and `generate_conformers`.
- Existing RDKit-backed tests should still pass when RDKit is installed.

## Files In Scope

- `tools/accounting/build_pdbbind_casf_pose_affinity_results.py`
- `tests/unit/test_build_pdbbind_casf_pose_affinity_results.py`

## Acceptance Criteria

- `python3 -m pytest tests/unit/test_build_pdbbind_casf_pose_affinity_results.py -q` passes.
- The new synthetic no-RDKit test proves:
  - builder behavior does not require a top-level RDKit import
  - generated-pose smoke reports `rdkit_unavailable` or an equivalent explicit diagnostic
  - `prediction_generation_enabled` remains `True` in generated smoke mode
  - no external state is mutated or downloaded
- Do not broaden into private payload, outbox, secure API E2E, workflow, PR, merge, Docker, or ROCm work.

## Verification

Run:

```bash
python3 -m pytest tests/unit/test_build_pdbbind_casf_pose_affinity_results.py -q
python3 -m ruff check tools/accounting/build_pdbbind_casf_pose_affinity_results.py tests/unit/test_build_pdbbind_casf_pose_affinity_results.py
```

## Web Access

Web access: disabled

## Constraints

- Follow `AGENTS.md`.
- Do not expand scope.
- Do not read or print `.env`, `.env.*`, `*.env`, or `*.env.*`.
- Do not stage, commit, push, delete, deploy, publish, release, production migration, billing, cloud mutation, secret rotation, permission escalation, or CASP submission commands.
- Preserve active CASP17 no-leak/internal-physics boundaries.

## Return Format

Return at most 80 lines:

- changed files
- tests/checks run with pass/fail status
- failed test names, if any
- key diff summary in 10 bullets or fewer
- blockers or risks
- web sources consulted, only if web access was enabled
