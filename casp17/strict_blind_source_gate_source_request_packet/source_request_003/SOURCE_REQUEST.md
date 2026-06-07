# CASP17 Strict-Blind Source Gate Source Request

- request: `source_request_003` `awaiting_pre_native_source_or_replacement` `pre_native_prediction_source_required`
- candidate: `HIST_CRAMBIN` `monomer` rank `3`
- route: `first_slot_source_route_003` `in_scope_current_candidate_disqualified_post_native` blocker `prediction_not_before_native`
- prediction/native dates: `2026-02-19` / `1981-04-30`
- current prediction: `data/internal_structures_refined/nightly/2026-02-19-ops-full-dashboard-r1/visual_post_internal_post_crambin_sample000_step00020.pdb`
- current native: `casp17/historical_seed_native_replacement_candidates/03_hist_crambin/native_candidate_1CRN.pdb`
- native authority: `rcsb:1CRN;doi:10.2210/pdb1crn/pdb`
- operator fields: `source_id,prediction_pdb,prediction_pdb_dropzone,prediction_created_at,native_release_date,prediction_created_at/native_release_date,native_authority_ref,creation_evidence_ref,no_leak_evidence_ref,method_summary,operator_clearance`
- next action: attach a prediction artifact created before the authoritative native release date, with timestamp and no-leak evidence

Local CASP17 strict-blind source-gate source request packet only. It converts fail-closed first-slot source routes into operator source-acquisition request folders. It does not fetch external archives, create prediction/native files, approve provenance, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP.
