# CAPRI Round 65 T333 / H2319

- status: `Prediction (human only)`
- recommended role: `predictor_then_scorer`
- readiness: `blocked_registration_role_selection`
- prediction: `2026-05-19 17:30` to `2026-06-02 17:00`
- scoring: `2026-06-03 09:00` to `2026-06-06 23:59`
- action: predictor if CASP ID is ready, then prepare scorer lane
- blockers: `operator_registration_required,role_selection_required,capri_template_required`

## Preflight

- confirm registration and role
- fetch the target-specific CAPRI template
- validate HEADER, MODEL numbering, TER/ENDMDL/END records, chain IDs, and residue numbering
- run CAPRI online validation before submission
