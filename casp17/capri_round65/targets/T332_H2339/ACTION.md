# CAPRI Round 65 T332 / H2339

- status: `Prediction (human only)`
- recommended role: `scorer`
- readiness: `blocked_registration_role_selection`
- prediction: `2026-05-15 17:30` to `2026-05-30 17:00`
- scoring: `2026-06-01 09:00` to `2026-06-05 23:59`
- action: prediction closed; scoring starts on registration-deadline day
- blockers: `operator_registration_required,role_selection_required,capri_template_required`

## Preflight

- confirm registration and role
- fetch the target-specific CAPRI template
- validate HEADER, MODEL numbering, TER/ENDMDL/END records, chain IDs, and residue numbering
- run CAPRI online validation before submission
