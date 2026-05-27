# CASP17 Historical Seed Current-Target Prefill

- generated: `2026-05-28T03:10:28+09:00`
- prefill_status: `applied`
- mode: `apply`
- rows ready/applied/already/blocked/total: `0/15/0/0/15`
- current target collisions: `0`
- HIST prefix pass: `15`
- remaining open current-target fields: `0`
- operator clearance csv: `runs/casp17_historical_identity_seed_operator_clearance_current.csv`
- next action: set current_casp17_target=false

## Rows

| rank | target | status | existing | proposed | seed | collision | action | blockers |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `HIST_BBA5` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 2 | `HIST_CHIGNOLIN` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 3 | `HIST_CRAMBIN` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 4 | `HIST_FSD_1` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 5 | `HIST_GB1_MINI` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 6 | `HIST_PROTEIN_A_BDOMAIN` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 7 | `HIST_TRP_CAGE` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 8 | `HIST_UBIQUITIN_MINI` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 9 | `HIST_VILLIN_HP35` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 10 | `HIST_WW_DOMAIN_FIP35` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 11 | `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 12 | `HIST_COMPLEX_02_TCRUZI_PDE_EXTERNAL_PDEB1_043_CHEMBL2171451` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 13 | `HIST_COMPLEX_03_TCRUZI_PDE_EXTERNAL_PDEB1_025_CHEMBL4441871` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 14 | `HIST_COMPLEX_04_TCRUZI_PDE_EXTERNAL_PDEB1_032_CHEMBL4445930` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |
| 15 | `HIST_COMPLEX_05_TCRUZI_PDE_EXTERNAL_PDEB1_007_CHEMBL3764370` | `applied` | `REQUIRED_FALSE_CONFIRMATION` | `false` | `false` | `False` | set current_casp17_target=false | `-` |

## Claim Boundary

Local CASP17 seed current-target prefill only. It can set current_casp17_target=false when the seed row already says false, the target_id uses the local HIST_ prefix, and no current CASP17 target-id collision is present. It does not clear no-leak provenance, certify chronology, mutate any other operator fields, fetch native structures, score native accuracy, or submit to CASP.
