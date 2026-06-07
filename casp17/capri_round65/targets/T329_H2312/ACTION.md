# CAPRI Round 65 T329 / H2312

- status: `Scoring challenge`
- recommended role: `scorer`
- readiness: `blocked_registration_role_selection`
- prediction: `2026-05-13 17:30` to `2026-05-27 17:00`
- scoring: `2026-05-28 09:00` to `2026-05-31 23:59`
- action: emergency scorer preflight if registered and scoring files are available
- blockers: `operator_registration_required,role_selection_required,capri_template_required`

## Preflight

- confirm registration and role
- fetch the target-specific CAPRI template
- validate HEADER, MODEL numbering, TER/ENDMDL/END records, chain IDs, and residue numbering
- run CAPRI online validation before submission
