# CAPRI Round 65 Readiness Packet

- generated: `2026-05-31T13:23:17+09:00`
- official source checked: `2026-05-31`
- source round: https://www.ebi.ac.uk/pdbe/complex-pred/capri/round/65/
- source active-round registration: https://www.ebi.ac.uk/pdbe/complex-pred/capri/
- status: `blocked_registration_role_selection`
- registration: `operator_input_required` ready fields `0/4`
- registration window: `2026-04-10 11:14` to `2026-06-01 midnight`
- registration days remaining: `1` urgency `immediate`
- targets active/closed/total: `11/2/13`
- scorer/predictor priority targets: `4/7`
- next action: confirm CASP ID, CAPRI registration, selected role, and submitter contact

## Position

CAPRI Round 65 is worth entering if CASP ID and CAPRI registration can be confirmed immediately. It is the 7th joint CASP-CAPRI Assembly Prediction challenge in the CASP17 season, and it maps directly to the CASP17 immune, nucleic-acid-complex, difficult-complex, and scoring/model-selection lanes.

## Registration Gate

| field | value | evidence | clearance | notes |
| --- | --- | --- | --- | --- |
| `casp_team_id` | `-` | `-` | `-` | 12-digit CASP Team ID for joint CASP-CAPRI predictor/server participation |
| `capri_registration_confirmed` | `-` | `-` | `-` | true after CAPRI Round 65 registration is confirmed |
| `selected_role` | `-` | `-` | `-` | predictor_server, scorer, or both |
| `submitter_contact` | `-` | `-` | `-` | operator/account owner contact for upload and confirmation receipts |

## Target Worklist

| CAPRI | CASP | status | role | readiness | prediction human end | scoring end | folder | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `T327` | `H1311` | `Closed` | `closed` | `closed_context` | `2026-05-13 17:00` | `2026-05-18 23:59` | `casp17/capri_round65/targets/T327_H1311` | closed; preserve only as schedule context |
| `T328` | `H2324` | `Closed` | `closed` | `closed_context` | `2026-05-21 17:00` | `2026-05-26 23:59` | `casp17/capri_round65/targets/T328_H2324` | closed; preserve only as schedule context |
| `T329` | `H2312` | `Scoring challenge` | `scorer` | `blocked_registration_role_selection` | `2026-05-27 17:00` | `2026-05-31 23:59` | `casp17/capri_round65/targets/T329_H2312` | emergency scorer preflight if registered and scoring files are available |
| `T330` | `T2313` | `Scoring challenge` | `scorer` | `blocked_registration_role_selection` | `2026-05-28 17:00` | `2026-06-01 23:59` | `casp17/capri_round65/targets/T330_T2313` | scorer preflight now; scoring closes on registration-deadline day |
| `T331` | `H2338` | `Scoring challenge` | `scorer` | `blocked_registration_role_selection` | `2026-05-29 17:00` | `2026-06-01 23:59` | `casp17/capri_round65/targets/T331_H2338` | scorer preflight now; scoring closes on registration-deadline day |
| `T332` | `H2339` | `Prediction (human only)` | `scorer` | `blocked_registration_role_selection` | `2026-05-30 17:00` | `2026-06-05 23:59` | `casp17/capri_round65/targets/T332_H2339` | prediction closed; scoring starts on registration-deadline day |
| `T333` | `H2319` | `Prediction (human only)` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-02 17:00` | `2026-06-06 23:59` | `casp17/capri_round65/targets/T333_H2319` | predictor if CASP ID is ready, then prepare scorer lane |
| `T334` | `H2321` | `Prediction (human only)` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-03 17:00` | `2026-06-08 23:59` | `casp17/capri_round65/targets/T334_H2321` | predictor if CASP ID is ready, then prepare scorer lane |
| `T335` | `H2335` | `Prediction challenge` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-10 17:00` | `2026-06-15 23:59` | `casp17/capri_round65/targets/T335_H2335` | human predictor priority, then scorer |
| `T336` | `H2340` | `Upcoming` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-15 17:00` | `2026-06-20 23:59` | `casp17/capri_round65/targets/T336_H2340` | predictor/server priority when target opens |
| `T337` | `H2343` | `Upcoming` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-15 17:00` | `2026-06-20 23:59` | `casp17/capri_round65/targets/T337_H2343` | predictor/server priority when target opens |
| `T338` | `T2342` | `Upcoming` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-16 17:00` | `2026-06-21 23:59` | `casp17/capri_round65/targets/T338_T2342` | predictor/server watch |
| `T339` | `H2344` | `Upcoming` | `predictor_then_scorer` | `blocked_registration_role_selection` | `2026-06-17 17:00` | `2026-06-22 23:59` | `casp17/capri_round65/targets/T339_H2344` | predictor/server watch |

## Format Preflight

- Use the target-specific CAPRI template.
- Submit only PDB format files.
- Put the CAPRI target number in the first line as a HEADER record.
- Keep MODEL records numbered and ordered correctly.
- End chains with TER, models with ENDMDL, and each submission with END.
- Preserve chain IDs and residue numbering from the template.
- Add PARENT records where templates are used; preserve MassiveFold REMARK provenance if applicable.
- Run the CAPRI online validator before treating any upload as ready.

## Claim Boundary

Local CAPRI Round 65 readiness packet only. It records official schedule and format gates, creates operator registration/role/preflight worklists, and does not register, download restricted target files, submit models, claim CAPRI/CASP scoring performance, or override online CAPRI validation.
