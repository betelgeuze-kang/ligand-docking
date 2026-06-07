# CASP17 Strict-Blind Source Gate Source Request

- request: `source_request_011` `out_of_scope_replace_candidate` `candidate_replacement_required`
- candidate: `HIST_COMPLEX_01_TCRUZI_PDE_EXTERNAL_PDEB1_010_CHEMBL4453005` `complex` rank `11`
- route: `first_slot_source_route_011` `out_of_scope_context_only_for_first_slot` blocker `native_authority_missing`
- prediction/native dates: `2026-05-17` / `-`
- current prediction: `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_current/01_tcruzi_pde_external_pdeb1_010_chembl4453005/protein_ligand_complex_minimized.pdb`
- current native: `runs/wetlab_tcruzi_pde_atomized_parameterization_minimization_current/01_tcruzi_pde_external_pdeb1_010_chembl4453005/protein_ligand_complex.pdb`
- native authority: `-`
- operator fields: `source_id,prediction_pdb,prediction_pdb_dropzone,prediction_created_at,native_release_date,prediction_created_at/native_release_date,native_authority_ref,creation_evidence_ref,no_leak_evidence_ref,method_summary,operator_clearance`
- next action: replace this out-of-scope candidate with a monomer candidate or move it to the proper complex/ligand lane

Local CASP17 strict-blind source-gate source request packet only. It converts fail-closed first-slot source routes into operator source-acquisition request folders. It does not fetch external archives, create prediction/native files, approve provenance, mutate source manifests, compute CASP metrics, push remotes, or submit to CASP.
