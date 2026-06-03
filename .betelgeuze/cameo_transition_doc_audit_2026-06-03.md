# CAMEO Transition Document Audit

Generated: 2026-06-03 KST

## Active Goal Interpretation

The active direction is the `구현` plan, not the older CASP17 submission-readiness goal.

Working conclusion:

- De-prioritize CASP17 as the main execution objective.
- Use CAMEO as the public blind-benchmark credibility lane.
- Use restricted local delivery plus ligand HTVS and wetlab triage as the near-term paid B2B pilot lane.
- Treat CASP17 artifacts as reusable review/gating/model-selection assets plus cleanup candidates, not as the primary product path.

## Documents Read

- `구현`
- `README.md`
- `docs/local_delivery_runbook.md`
- `docs/local_delivery_claim_policy.md`
- `tools/build_runs_cleanup_manifest.py`
- `api/main.py`
- `api/tasks.py`
- official CAMEO help/FAQ pages checked on 2026-06-03

## Repository Findings

### Product Lane

The local-delivery product path is the most mature near-term commercial surface.

Relevant evidence:

- `README.md` identifies the repo as a local-delivery molecular dynamics and ligand validation stack.
- `docs/local_delivery_runbook.md` says the current restricted local-delivery scope is green only for `kinase,gpcr,ion_channel`.
- `docs/local_delivery_claim_policy.md` forbids broad platform, transporter, CA2/PXR, IDP broader-promotion, unattended external-decision, and general commercialization claims.
- Existing packaging flow is already defined:
  - `tools/run_local_delivery_preflight.py`
  - `tools/build_local_delivery_bundle.py`
  - `tools/validate_local_delivery_bundle.py`

Interpretation:

- This is strong enough to package as a guarded pilot workflow.
- It is not strong enough to claim broad MD-platform parity or hosted SaaS readiness.

### CAMEO Lane

No repo-level CAMEO module, PRD, receiver, ingestion, result-email, or result-fetcher surface exists yet.

External CAMEO requirements observed from official docs:

- CAMEO submits targets by HTTP POST or GET.
- The server should return HTTP 200 immediately after receiving a target.
- Predictions are returned by email to the provided results address.
- Up to five models may be submitted; model 1 is the primary aggregate-comparison model.
- Accepted structure formats include PDB and mmCIF for polymer targets.
- Targets can include one or more protein, peptide, DNA, or RNA sequences and optional ligands from the same prereleased PDB entry.
- The deadline is tied to the weekly PDB release window.

Interpretation:

- The first CAMEO implementation should be a receiver and durable job-intake contract, not an accuracy claim.
- CAMEO PRD should explicitly decide initial capability scope, likely protein-only or protein-complex-only before ligands/RNA/DNA.
- A model1 selector contract is required early because model 1 drives aggregate comparison.

### API Lane

The API is currently not runnable.

Confirmed blocker:

- `python3 -m py_compile api/main.py api/tasks.py` fails on `api/main.py:36`.
- Both `api/main.py` and `api/tasks.py` use invalid `request_ dict` annotations.
- Both wrappers refer to `request_data` without defining it in scope.
- `api/tasks.py` writes `REMARK    FAKE RESULT FOR DEMONSTRATION`, so it is a mock path.

Interpretation:

- API repair is a true P0 before any CAMEO receiver or service claim.
- The first fix should make the API importable and fail honestly for unsupported simulation execution instead of writing fake scientific output.

### Cleanup Lane

Cleanup tooling exists but is currently focused on `runs/` external-validation archive batches, not the new largest CAMEO/CASP transition targets.

Existing tool:

- `tools/build_runs_cleanup_manifest.py`
- `tools/apply_runs_cleanup_manifest.py`

Gap:

- The `구현` plan names larger targets such as `casp17/massivefold_external_pool_intake`, `runs/archive`, repeated trajectory frames, `rust_engine/target`, and `.venv`.
- Current cleanup manifest logic does not yet encode the new `keep / archive / externalize / delete` policy for those CASP17-heavy paths.

Interpretation:

- Do not delete first.
- Build a transition cleanup manifest with sha256/size/reason/action rows.
- Keep final PDB/mmCIF, top representatives, manifests, validation reports, viewer indexes, and checksums.

### CASP17 Lane

CASP17 has extensive review-quality scaffolding, but win-tier/competitive proof is blocked.

Useful assets to preserve:

- model-selection and shape-guard logic
- TS/PDB/mmCIF validation patterns
- viewer and object-library generation
- scorecard/gate/report builder patterns
- operator decision-kit pattern

Assets to keep outside the new proof lane:

- MassiveFold/external pools
- other-team models
- official archive/native/reference artifacts
- current-target native lookups

Interpretation:

- CASP17 should become a source of reusable infrastructure and historical notes, not the main active submission target.

## Recommended P0 Order

1. Write `docs/cameo_transition_prd.md`.
2. Repair API importability:
   - fix function annotations
   - pass `request_data` correctly
   - remove or block fake-result writes
   - add a minimal import/API smoke test
3. Add a minimal CAMEO receiver skeleton:
   - HTTP POST/GET intake
   - immediate 200 response
   - persisted job record
   - no automatic external submission
   - explicit capability scope
4. Build a transition cleanup manifest:
   - classify `keep/archive/externalize/delete`
   - include CASP17 heavy paths
   - dry-run only first
5. Package B2B local-delivery pilot docs:
   - restricted scope only
   - bundle validator required
   - no broad platform or wetlab success claims

## Claim Boundaries

Allowed:

- restricted local-delivery pilot for `kinase,gpcr,ion_channel` when bundle validation is green
- CAMEO readiness work as receiver/scaffold/benchmark-integration planning
- CASP17-derived infrastructure reuse

Not allowed yet:

- CAMEO registered-server readiness
- broad MD engine parity with OpenMM/Schrodinger
- hosted multi-tenant SaaS readiness
- CASP17 win-tier/top-3 proof
- using MassiveFold/external pools as internal prediction proof
- deleting heavy artifacts without a manifest and operator approval

