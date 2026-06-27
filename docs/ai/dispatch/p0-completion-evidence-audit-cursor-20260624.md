# Cursor Worker Slice: P0 Completion Evidence Audit

Web access: disabled.

You are a scoped Cursor audit worker in the ligand-docking worktree. You are not alone in the codebase: do not edit, revert, stage, commit, push, delete, deploy, dispatch workflows, edit branch protection, or mutate external state. Do not read or print `.env*` files. Work with the existing dirty tree.

Goal: audit current evidence for the active P0 objective without changing files.

Scope:

1. Read current code/tests/docs/artifacts only as needed for P0-1 through P0-5:
   - P0-1 Langevin integrator
   - P0-2 remote Release CI green evidence
   - P0-3 small public gold benchmark
   - P0-4 ligand chemistry
   - P0-5 pose search
2. For each P0 item, classify evidence as one of:
   - proved by current files/tests/artifacts
   - partially proved
   - contradicted
   - missing
3. Identify the single highest-value next local patch that would move the real objective forward without external mutation.

Constraints:

- Read-only audit. Do not modify files.
- Do not rely on receipt existence alone; inspect whether tests/artifacts cover the stated requirement.
- Keep claim boundaries intact. Do not suggest unblocking calibrated affinity, FEP parity, wetlab hit, broad platform, or AlphaFold parity claims.

Return:

- Concise per-P0 audit.
- Highest-value local patch recommendation with likely files/tests.
- Any external-state blockers that cannot be locally closed.
