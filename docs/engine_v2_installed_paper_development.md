# Installed retained-paper development comparison

`betelgeuze-paper-development` executes an explicitly declared registered CPU
baseline/refined Cartesian comparison without FIT rows, predictors, experimental
value projection or source-role assignment. It uses the existing 1.3 workflow and
durable numerical journals. The native FIT intake, native v3/v4 admission and
1.2/1.3 solver source files are unchanged.

The protocol is `installed_paper_development_cartesian_protocol_v1`, with exactly
`schema_version`, `candidates` and `cartesian_solver`. Candidates are an ordered
list of `candidate_id`, `source`, `original_request` and `prepared_evidence`.
References have exactly absolute canonical `path` and SHA-256. The caller must
supply the protocol byte hash to every CLI operation. The requested denominator
is fixed by the complete list, including candidates with missing or rejected
preparation. Missing preparation is never replaced with synthetic inputs.

The source descriptor is `retained_paper_label_free_development_source_v1` and
requires normalized DOI, local PR compound and physical occurrence IDs, human
HTR6 target annotation, the reported binding-method context/pages, article and
identity-statement evidence pins, canonical chemical identity and the exact
null/false boundary. The identity statement separately pins its upstream source
evidence. The catalogue target annotation `CHEMBL3371` supplies no ChEMBL assay,
document or activity origin. Unknown, outcome, FIT and role fields are rejected.
The source descriptor and identity statement are operator-reviewed metadata,
not source authentication or an automatically reconstructed paper structure.

`derive_prepared_evidence(source_ref, original_request_ref, charge_origin_ref,
initial_pose_protocol=..., declared_model_evidence=...)` binds the unchanged
original registered request to graph/actual-coordinate stereo, original XML
decimal charge tokens and complete index map, pocket/1 Å cross-overlap screening,
and declared parameter/extension/cross contracts. Save its returned JSON under a
new path and pin its bytes in the protocol. This API assigns no dataset role and
does no force or score-term evaluation; scorer construction includes reference
intraligand arithmetic. The bound initial-pose protocol identifies the earlier
preparation procedure; the bridge checks its shared identity without replaying
pose generation or claiming all of that procedure's original screens.

Common-cohort checks bind DOI/method/article, initial-pose protocol, receptor
source/coordinates/construct, receptor cross rows, cross-model convention,
pocket/frame and original request settings including budgets and solver settings.
A cohort mismatch prevents every candidate from executing. Request conversion
to 1.3 is explicit and retained beside the original; solver limits cannot weaken
the existing 1.3 contract. There is no cross-chemical affinity ranking.

Source XML is used only for original charge tokens and atom mapping. Native
parameters are the declared computational model, with complete XML conversion
and global source-parameter equivalence explicitly unverified. In particular,
native cutoff/switch semantics must not be presented as global OpenMM NoCutoff
equivalence. Independent initial-point source/support receipts do not verify an
entire optimization trace, constrained dynamics or the assayed microstate.

From an environment containing the new wheel and compatible research dependencies:

```bash
betelgeuze-paper-development preflight --protocol /absolute/protocol.json \
  --expected-protocol-sha256 PROTOCOL_BYTE_SHA256
betelgeuze-paper-development run --protocol /absolute/protocol.json \
  --expected-protocol-sha256 PROTOCOL_BYTE_SHA256 --run-dir /absolute/new-run \
  --pause-after-objective-attempts 2
betelgeuze-paper-development resume --protocol /absolute/protocol.json \
  --expected-protocol-sha256 PROTOCOL_BYTE_SHA256 --run-dir /absolute/new-run
betelgeuze-paper-development verify --protocol /absolute/protocol.json \
  --expected-protocol-sha256 PROTOCOL_BYTE_SHA256 --run-dir /absolute/new-run
```

The pause applies independently to every ready candidate. Known checkpoint
continuation reuses its baseline receipt and reserved numerical journal. Unknown
score/force work is retained as `interrupted_unknown`; it is not zero and is never
automatically reissued. A surviving outer intent without durable child evidence
also remains unknown. Each child retains every invocation start/end, numerical
journal/checkpoint and score receipt. A completed invocation with earlier
unresolved numerical calls cannot become a completed/known-work bridge result.

Rows expose the raw attempt/convergence, baseline/refined observations, raw and
admitted per-arm selections, final baseline fallback, numerical/score/setup work
and inclusive timing scopes. `refinement_state` distinguishes no accepted change,
admitted converged refinement and rejected refinement; force convergence alone
does not establish admission. Exact completed resume/verify reopens all bindings
and durable receipts without new score/force calls or result rewrites. The paired
dimensionless pose score remains separate from energy and reported Ki. Assayed
state, source roles, independent measurement denominator, training, evaluation,
scientific qualification and product ranking remain null/false.

The focused synthetic suite covers source/coordinate/candidate swaps, authority
promotion, missing preparation, common-cohort mismatch, known checkpoint reuse
and unknown interruption costs. The portable installed probe has two phases:

```bash
python tests/ci/paper_development_wheel_probe.py prepare /absolute/probe-fixture
# Copy that script outside the checkout, then use the installed environment:
python -I /absolute/copied-probe.py execute /absolute/probe-fixture \
  --installed-root /absolute/installed-environment \
  --require-fresh-environment
```

Only preparation imports synthetic checkout fixtures. Execution requires the
wheel's console entry metadata and cannot import checkout tools/tests. It checks
preflight, two-candidate completion, preparation failure, deliberate pause/resume,
absolute refinement rejection, verify, immutable exact reuse and retained unknown
invocation work. These checks are installed-package arithmetic/orchestration
evidence, not physical accuracy, source clearance or an experimental denominator.

The 2024 paper's [source ledger](evidence/human_5ht6_ki_2024_source_ledger_v1.json),
[supplement review](research/human_5ht6_2024_supplement_review_20260930.md),
[Table S1 occurrence record](research/human_5ht6_2024_supplement_table1_occurrences_20260930.md)
and [bounded ChEMBL lookup](evidence/human_5ht6_2024_chembl_correspondence_lookup_v1.json)
retain their own roles, uncertainty, rights and completeness boundaries. They
remain distinct from this computational development route.
