# HIST_PROTEIN_A_BDOMAIN Authoritative Chronology Audit

- status: `post_native_prediction_chronology_blocked`
- benchmark: `hist_seed_protein_a_bdomain`
- scope: `monomer`
- prediction candidate: `2026-02-19` `chronology_board_prediction_path_date`
- native authority date: `1996-06-28` `pdb_header_date:rcsb:1BDD;doi:10.2210/pdb1bdd/pdb`
- native authority: `authority_pass` `rcsb:1BDD;doi:10.2210/pdb1bdd/pdb`
- prediction after native authority: `True`
- blockers: `prediction_not_before_authoritative_native_date`
- next action: replace with a pre-native blind prediction artifact, or keep this row in a separate post-native retrospective lane with explicit no-template evidence

## Claim Boundary

Local CASP17 historical seed authoritative chronology audit only. It compares local/internal prediction-date candidates with native-authority dates parsed from already-audited native evidence. It does not clear no-leak provenance, certify a prediction was blind, approve use of public native structures/templates, mutate operator clearance CSVs, compute official CASP metrics, or submit to CASP.
