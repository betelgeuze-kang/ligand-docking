# CAPRI Round 65 Format Preflight

- generated: `2026-05-31T13:32:26+09:00`
- status: `blocked_format_preflight`
- active/closed/total: `11/2/13`
- local pass/blocked/checked: `0/11/0`
- missing template/candidate: `11/11`
- first blocked: `T329`
- next action: place target_template.pdb and candidate_submission.pdb, then rerun local format preflight
- source format: https://www.ebi.ac.uk/pdbe/complex-pred/capri/capri-format/
- source CASP-CAPRI: https://www.ebi.ac.uk/pdbe/complex-pred/capri/casp-capri/

## Target Rows

| CAPRI | CASP | role | status | models | atoms | template | candidate | blockers |
| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |
| `T327` | `H1311` | `closed` | `closed_context` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T327_H1311/target_template.pdb` | `casp17/capri_round65/format_preflight/T327_H1311/candidate_submission.pdb` | `closed_target` |
| `T328` | `H2324` | `closed` | `closed_context` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T328_H2324/target_template.pdb` | `casp17/capri_round65/format_preflight/T328_H2324/candidate_submission.pdb` | `closed_target` |
| `T329` | `H2312` | `scorer` | `blocked_format_preflight` | 0/10 | 0 | `casp17/capri_round65/format_preflight/T329_H2312/target_template.pdb` | `casp17/capri_round65/format_preflight/T329_H2312/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T330` | `T2313` | `scorer` | `blocked_format_preflight` | 0/10 | 0 | `casp17/capri_round65/format_preflight/T330_T2313/target_template.pdb` | `casp17/capri_round65/format_preflight/T330_T2313/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T331` | `H2338` | `scorer` | `blocked_format_preflight` | 0/10 | 0 | `casp17/capri_round65/format_preflight/T331_H2338/target_template.pdb` | `casp17/capri_round65/format_preflight/T331_H2338/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T332` | `H2339` | `scorer` | `blocked_format_preflight` | 0/10 | 0 | `casp17/capri_round65/format_preflight/T332_H2339/target_template.pdb` | `casp17/capri_round65/format_preflight/T332_H2339/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T333` | `H2319` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T333_H2319/target_template.pdb` | `casp17/capri_round65/format_preflight/T333_H2319/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T334` | `H2321` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T334_H2321/target_template.pdb` | `casp17/capri_round65/format_preflight/T334_H2321/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T335` | `H2335` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T335_H2335/target_template.pdb` | `casp17/capri_round65/format_preflight/T335_H2335/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T336` | `H2340` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T336_H2340/target_template.pdb` | `casp17/capri_round65/format_preflight/T336_H2340/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T337` | `H2343` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T337_H2343/target_template.pdb` | `casp17/capri_round65/format_preflight/T337_H2343/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T338` | `T2342` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T338_T2342/target_template.pdb` | `casp17/capri_round65/format_preflight/T338_T2342/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |
| `T339` | `H2344` | `predictor_server` | `blocked_format_preflight` | 0/100 | 0 | `casp17/capri_round65/format_preflight/T339_H2344/target_template.pdb` | `casp17/capri_round65/format_preflight/T339_H2344/candidate_submission.pdb` | `target_template_pdb_missing,candidate_submission_pdb_missing` |

## Claim Boundary

Local CAPRI Round 65 format preflight only. It checks submission-file presence and basic CAPRI PDB format rules before online upload. It does not download restricted CAPRI templates, submit models, replace the CAPRI validator, or certify final CASP/CAPRI acceptance.
