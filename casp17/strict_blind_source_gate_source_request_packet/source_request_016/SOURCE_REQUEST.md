# CASP17 Strict-Blind Source Gate Source Request

- request: `source_request_016` `out_of_scope_replace_candidate` `candidate_replacement_required`
- candidate: `HIST_COMPLEX_06_TCRUZI_PDE_EXTERNAL_PDEB1_017_CHEMBL3765606` `complex` rank `16`
- route: `first_slot_source_route_016` `out_of_scope_context_only_for_first_slot` blocker `native_authority_missing`
- prediction/native dates: `-` / `-`
- current prediction: `-`
- current native: `-`
- native authority: `-`
- operator fields: `source_id,prediction_pdb,prediction_pdb_dropzone,prediction_created_at,native_release_date,prediction_created_at/native_release_date,native_authority_ref,creation_evidence_ref,no_leak_evidence_ref,method_summary,operator_clearance`
- next action: replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane

Local CASP17 strict-blind source-gate source request packet only. It converts fail-closed first-slot source routes into operator source-acquisition request folders. It does not fetch external archives, create prediction/native files, approve provenance, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP.
