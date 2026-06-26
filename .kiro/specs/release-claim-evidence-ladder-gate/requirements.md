# Requirements Document

## Introduction

PR #18 merged a read-only API surface, `/product/release-claim-evidence-ladder`, that
exposes a tiered release-claim evidence ladder with three tiers (`local_observed_green`,
`remote_green`, `runtime_green`). The surface fails closed by default
(`runtime_claim_allowed=false`) and reports `highest_supported_claim=none` when no evidence
artifact exists. The surface READS an artifact, but no producer currently writes that
artifact, so the surface always reports the fail-closed default.

This feature closes that gap with code-only work. It adds a builder that produces the
artifact the surface reads (`runs/release_claim_evidence_ladder_gate_current.json` plus
`.md` and `.csv` companions following repository convention), and it wires GitHub Actions
workflow-run attribution so that `remote_green` and `runtime_green` claims are backed by a
concrete `workflow_run` id and `head_sha` attributed to a specific commit SHA, rather than
unattributed assertions. The builder reuses and extends the existing remote-green evidence
machinery in `tools/product/release_ci_remote_green_evidence_contract.py` and
`tools/product/build_release_ci_remote_green_receipt.py` instead of duplicating it.

The builder is read-only accounting: it consumes evidence JSON supplied by the owner/CI,
validates and attributes that evidence, and never fabricates evidence, submits to GitHub,
opens network requests to mutate external state, or requires operator approval tokens to
run.

## Glossary

- **Claim_Ladder_Builder**: The new code-only tool that reads supplied evidence JSON,
  evaluates the tiered claim ladder, and writes the ladder gate artifact set.
- **Ladder_Artifact**: The output file set written by the Claim_Ladder_Builder:
  `runs/release_claim_evidence_ladder_gate_current.json` and its `.md` and `.csv`
  companions.
- **Claim_Ladder_Surface**: The existing read-only `/product/release-claim-evidence-ladder`
  API surface merged in PR #18 that reads the Ladder_Artifact.
- **Claim_Tier**: One of the ordered release-claim tiers: `local_observed_green` (rank 1),
  `remote_green` (rank 2), `runtime_green` (rank 3).
- **Highest_Supported_Claim**: The highest-ranked Claim_Tier whose evidence is present,
  valid, and attributed; `none` when no tier qualifies.
- **Local_Observed_Green**: The tier asserting local tests and builders pass, evidenced by
  supplied local evidence JSON.
- **Remote_Green**: The tier asserting GitHub workflow runs are green and attributed to a
  specific commit SHA.
- **Runtime_Green**: The tier asserting a ROCm/HIP runtime smoke is green and attributed to
  a specific GitHub workflow run.
- **Workflow_Run_Attribution**: The binding of a Claim_Tier's green claim to a concrete
  `workflow_run` id and `head_sha` value from supplied GitHub evidence JSON.
- **Merge_Commit_SHA**: The commit SHA for which a release claim is being evaluated,
  supplied as input to the Claim_Ladder_Builder.
- **Attributed_Run**: A supplied GitHub `workflow_run` record whose `head_sha` equals the
  Merge_Commit_SHA and whose status is `completed` with conclusion `success`.
- **Unattributed_Run**: A supplied GitHub `workflow_run` record whose `head_sha` does not
  equal the Merge_Commit_SHA, or a tier for which no matching `workflow_run` record exists.
- **Runtime_Claim_Allowed**: A boolean field in the Ladder_Artifact that is `true` only when
  the Runtime_Green tier is fully evidenced and attributed; `false` by default.
- **Evidence_Contract**: The existing read-only evidence machinery in
  `tools/product/release_ci_remote_green_evidence_contract.py` and
  `tools/product/build_release_ci_remote_green_receipt.py` that the builder reuses.
- **Read_Only_Accounting**: The operating mode where `execution_enabled=false` and
  `external_state_mutated=false`; the builder consumes and validates evidence without
  mutating external state.

## Requirements

### Requirement 1: Produce the ladder gate artifact consumed by the surface

**User Story:** As a release owner, I want a builder that writes the release-claim evidence
ladder artifact, so that the `/product/release-claim-evidence-ladder` surface reports real
evidence instead of the fail-closed default.

#### Acceptance Criteria

1. WHEN the Claim_Ladder_Builder is run, THE Claim_Ladder_Builder SHALL write
   `runs/release_claim_evidence_ladder_gate_current.json` containing the evaluated ladder
   result.
2. WHEN the Claim_Ladder_Builder is run, THE Claim_Ladder_Builder SHALL write a `.md`
   companion at `runs/release_claim_evidence_ladder_gate_current.md` summarizing the ladder
   result.
3. WHEN the Claim_Ladder_Builder is run, THE Claim_Ladder_Builder SHALL write a `.csv`
   companion at `runs/release_claim_evidence_ladder_gate_current.csv` containing one row per
   Claim_Tier.
4. THE Ladder_Artifact JSON SHALL include the fields `highest_supported_claim`,
   `runtime_claim_allowed`, and a per-tier evaluation result for each Claim_Tier.
5. THE Ladder_Artifact JSON SHALL include the field `external_state_mutated` set to `false`.
6. THE Ladder_Artifact JSON SHALL include the field `execution_enabled` set to `false`.
7. WHERE the Claim_Ladder_Surface reads `runs/release_claim_evidence_ladder_gate_current.json`,
   THE Ladder_Artifact JSON SHALL provide the `highest_supported_claim` and
   `runtime_claim_allowed` fields with the value types the Claim_Ladder_Surface expects.

### Requirement 2: Fail-closed defaults when evidence is missing

**User Story:** As a release owner, I want the ladder to fail closed when evidence is
missing, so that no release claim is asserted without supporting evidence.

#### Acceptance Criteria

1. IF no evidence artifact exists for any Claim_Tier, THEN THE Claim_Ladder_Builder SHALL set
   `highest_supported_claim` to `none`.
2. THE Claim_Ladder_Builder SHALL set `runtime_claim_allowed` to `false` by default.
3. WHEN the Runtime_Green tier is not fully evidenced and attributed, THE Claim_Ladder_Builder
   SHALL set `runtime_claim_allowed` to `false`.
4. IF a supplied evidence input is missing, empty, or not a JSON object, THEN THE
   Claim_Ladder_Builder SHALL treat the corresponding Claim_Tier as not supported.
5. IF a supplied evidence input fails Evidence_Contract shape validation, THEN THE
   Claim_Ladder_Builder SHALL treat the corresponding Claim_Tier as not supported and record
   the validation error in the Ladder_Artifact.

### Requirement 3: Tiered claim ladder semantics

**User Story:** As a release owner, I want each tier evaluated in rank order, so that the
reported highest claim never exceeds what the evidence supports.

#### Acceptance Criteria

1. THE Claim_Ladder_Builder SHALL evaluate the Claim_Tiers in the fixed rank order
   `local_observed_green` (rank 1), `remote_green` (rank 2), `runtime_green` (rank 3).
2. WHEN local tests and builders evidence is present, valid, and reports success, THE
   Claim_Ladder_Builder SHALL mark the Local_Observed_Green tier as supported.
3. WHEN GitHub workflow run evidence contains an Attributed_Run for the Remote_Green tier,
   THE Claim_Ladder_Builder SHALL mark the Remote_Green tier as supported.
4. WHEN ROCm/HIP runtime smoke evidence contains an Attributed_Run for the Runtime_Green
   tier, THE Claim_Ladder_Builder SHALL mark the Runtime_Green tier as supported.
5. THE Claim_Ladder_Builder SHALL set `highest_supported_claim` to the highest-ranked
   Claim_Tier that is marked supported.
6. IF a higher-ranked Claim_Tier is supported WHILE a lower-ranked Claim_Tier is not
   supported, THEN THE Claim_Ladder_Builder SHALL record the lower-tier gap in the
   Ladder_Artifact and SHALL set `highest_supported_claim` to the highest contiguous
   supported tier starting from rank 1.
7. THE Claim_Ladder_Builder SHALL set `runtime_claim_allowed` to `true` only when the
   Runtime_Green tier is marked supported.

### Requirement 4: GitHub workflow-run attribution

**User Story:** As a release owner, I want each green tier bound to a concrete workflow run
and commit SHA, so that remote and runtime claims are backed by attributed run evidence
rather than unattributed assertions.

#### Acceptance Criteria

1. THE Claim_Ladder_Builder SHALL accept a Merge_Commit_SHA input identifying the commit for
   which the release claim is evaluated.
2. WHEN evaluating the Remote_Green tier, THE Claim_Ladder_Builder SHALL bind the tier's
   green claim to a `workflow_run` id and `head_sha` from the supplied GitHub workflow run
   evidence.
3. WHEN evaluating the Runtime_Green tier, THE Claim_Ladder_Builder SHALL bind the tier's
   green claim to a `workflow_run` id and `head_sha` from the supplied GitHub workflow run
   evidence.
4. IF the Merge_Commit_SHA has no Attributed_Run for a tier, THEN THE Claim_Ladder_Builder
   SHALL mark that tier as not supported and SHALL record an `unattributed` block reason in
   the Ladder_Artifact.
5. IF a supplied `workflow_run` record has a `head_sha` that differs from the
   Merge_Commit_SHA, THEN THE Claim_Ladder_Builder SHALL exclude that record from
   attribution for the tier.
6. WHEN a tier is marked supported, THE Claim_Ladder_Builder SHALL record the attributing
   `workflow_run` id and `head_sha` in the per-tier evaluation result.
7. THE Claim_Ladder_Builder SHALL set `highest_supported_claim` no higher than the highest
   tier for which an Attributed_Run is present.

### Requirement 5: Reuse existing remote-green evidence machinery

**User Story:** As a maintainer, I want the builder to reuse the existing evidence contract
and receipt code, so that remote-green evaluation logic is not duplicated.

#### Acceptance Criteria

1. THE Claim_Ladder_Builder SHALL import and call the existing evaluation functions in
   `tools/product/release_ci_remote_green_evidence_contract.py` for evidence shape
   validation.
2. THE Claim_Ladder_Builder SHALL import and call the existing evaluation functions in
   `tools/product/build_release_ci_remote_green_receipt.py` for remote-green receipt
   evaluation.
3. WHERE the existing Evidence_Contract defines evidence input specifications, THE
   Claim_Ladder_Builder SHALL consume those specifications rather than redefining evidence
   input paths.
4. THE Claim_Ladder_Builder SHALL record in the Ladder_Artifact the Evidence_Contract schema
   version used for evaluation.

### Requirement 6: Read-only accounting boundaries

**User Story:** As a repository owner, I want the builder to remain read-only accounting, so
that running it never mutates external state or requires approval tokens.

#### Acceptance Criteria

1. THE Claim_Ladder_Builder SHALL set `execution_enabled` to `false` in the Ladder_Artifact.
2. THE Claim_Ladder_Builder SHALL set `external_state_mutated` to `false` in the
   Ladder_Artifact.
3. THE Claim_Ladder_Builder SHALL run without requiring an operator approval token.
4. THE Claim_Ladder_Builder SHALL read evidence only from local JSON files supplied as
   inputs.
5. THE Claim_Ladder_Builder SHALL write output files only under the `runs/` directory.
6. THE Claim_Ladder_Builder SHALL include a claim-boundary statement in the Ladder_Artifact
   declaring that the builder does not submit to GitHub, open network requests to mutate
   external state, dispatch workflows, change branch protection, create tags, deploy,
   publish, or submit to CASP.
7. WHEN the Claim_Ladder_Builder consumes supplied evidence, THE Claim_Ladder_Builder SHALL
   treat the evidence as externally supplied input and SHALL NOT generate workflow run
   records or runtime smoke results that were not present in the supplied evidence.

### Requirement 7: Round-trip serialization of the ladder artifact

**User Story:** As a maintainer, I want the ladder result to serialize and deserialize
without loss, so that the surface reads exactly what the builder evaluated.

#### Acceptance Criteria

1. THE Claim_Ladder_Builder SHALL serialize the evaluated ladder result to JSON.
2. WHEN the serialized Ladder_Artifact JSON is read back, THE parsed ladder result SHALL
   equal the evaluated ladder result (round-trip property).
3. THE Ladder_Artifact JSON SHALL be written with deterministic key ordering so that
   identical evidence inputs produce identical serialized output.

### Requirement 8: Builder idempotence and determinism

**User Story:** As a maintainer, I want repeated builder runs on the same evidence to
produce the same artifact, so that the gate result is reproducible.

#### Acceptance Criteria

1. WHEN the Claim_Ladder_Builder is run twice on identical evidence inputs, THE
   Claim_Ladder_Builder SHALL produce identical `highest_supported_claim` and
   `runtime_claim_allowed` values (idempotence).
2. WHEN the Claim_Ladder_Builder is run twice on identical evidence inputs, THE
   Claim_Ladder_Builder SHALL write byte-identical Ladder_Artifact JSON content.
3. THE Claim_Ladder_Builder SHALL exclude wall-clock-dependent values from the
   reproducibility-relevant fields of the Ladder_Artifact.
