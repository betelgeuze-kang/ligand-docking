# CAPRI Round 65 T339 / H2344

- status: `Upcoming`
- recommended role: `predictor_then_scorer`
- readiness: `blocked_registration_role_selection`
- prediction: `2026-06-03 17:30` to `2026-06-17 17:00`
- scoring: `2026-06-18 09:00` to `2026-06-22 23:59`
- action: predictor/server watch
- blockers: `operator_registration_required,role_selection_required,capri_template_required`

## Preflight

- confirm registration and role
- fetch the target-specific CAPRI template
- validate HEADER, MODEL numbering, TER/ENDMDL/END records, chain IDs, and residue numbering
- run CAPRI online validation before submission
