# Worker Slice: P0-5 pose-search gap scan

Web access: disabled.

## Goal
Review the current Tier-beta pose generation and scoring path and identify the smallest high-value implementation gap for P0-5 pose search.

## Scope
- Review only unless an obvious test-only expectation is stale. Prefer no edits.
- Do not stage, commit, push, delete, or mutate external state.
- Do not read or print `.env*`.

## Focus Files
- `betelgeuze_engine/biodiscovery/pose.py`
- `betelgeuze_engine/biodiscovery/screening.py`
- `betelgeuze_engine/biodiscovery/scoring.py`
- `tests/unit/test_tier_beta_vertical_slice.py`
- `tests/unit/test_biodiscovery_screening.py`

## Questions
- Does current pose generation implement SO(3) diversity, pocket translation grid, clash prefilter, beam scoring, local minimization, RMSD clustering, or chemically meaningful anchors?
- Which focused tests should Codex add for the next implementation slice?
- Are there any existing tests that would fail if pose generation becomes multi-transform search rather than one centered pose per conformer?

## Return
Concise summary only:
- Current gaps
- Suggested next test names
- Risk areas
