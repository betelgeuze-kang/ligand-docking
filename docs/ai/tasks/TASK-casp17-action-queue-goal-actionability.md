# TASK-casp17-action-queue-goal-actionability

## Goal

Make the CASP17 win-tier action queue explicitly distinguish local goal-mode work
from operator-input and R4-confirmation blockers.

## Scope

- Add fail-closed row-level actionability fields.
- Add summary counts and the first locally actionable action ID.
- Cover blocked-input, local-ready/repair, passed, R4, and unknown statuses.

## Non-goals

- Do not fetch or populate historical/native inputs.
- Do not run predictors, tune models, submit to CASP, or authorize commands.
- Do not regenerate committed/current CASP17 packets in this slice.

## Likely Files Or Search Targets

- `tools/casp17/build_casp17_win_tier_action_queue_packet.py`
- `tests/unit/test_build_casp17_win_tier_action_queue_packet.py`

## Verification

- `python3 -m pytest -q tests/unit/test_build_casp17_win_tier_action_queue_packet.py`
- `./scripts/ai-verify.sh`

## Stop Conditions

- Preserve all existing dirty worktree changes.
- Unknown action statuses must remain non-actionable.
- Stop if classification requires new scientific evidence or operator authority.

## Risk Level

R2
