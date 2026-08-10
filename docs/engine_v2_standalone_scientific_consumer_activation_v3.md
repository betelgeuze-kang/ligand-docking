# Engine V2 standalone scientific consumer activation v3

Status: exact repository-synthetic D0 consumers activated; all product,
molecular, benchmark, Stage 0, HIP, and scientific-claim authority remains
false.

The canonical activation policy is
`config/engine_v2_standalone_scientific_consumer_activation_v3.json`. It binds
the exact standalone scientific-core policy, receipt schema, repository fixture
request SHA-256, fixed denominator 64, and Top-5. Its scope is only
`exact_repository_synthetic_d0_only`.
The embedded source-adapter, scientific-pipeline, and scoring-batch receipts
remain non-authoritative and keep their own consumer/execution flags false;
only this outer synthetic-surface policy records the narrowly scoped activation.

The following surfaces share one route:

1. `DockingPipeline.run` calls the bounded standalone scientific executor once;
2. `betelgeuze-dock dock` serializes that exact result;
3. the Python API, diagnostic benchmark, and product shadow each call the
   no-argument `DockingPipeline().run(request)` route once; and
4. consumer envelopes embed the core receipt without replacing candidate rows,
   ranking, selection, or blockers.

`betelgeuze-dock verify` independently checks the current scientific receipt's
available self-hashes and cross-bindings and rederives its fixed-64 counts,
Scorer-v1 evidence, pose-validity evidence, primary ranking, and valid-only
ranking. This remains structural consistency verification. It is not a
signature, source attestation, external execution authorization, or scientific
validation.

Product shadow may display evidence and allow an operator second opinion. It
cannot alter the existing rank, emit a customer pose, mutate product state, or
make a production/scientific claim. The diagnostic benchmark cannot admit
Historical, Fresh-128, public, or arbitrary cases.

Migration: canonical callers that previously inspected
`DockingPipelineResultV1.candidate_evidence` must use
`StandaloneScientificCoreReceiptV1.scientific_pipeline_receipt.final_scoring_batch.records`.
The profile field is now `pipeline_profile`, the denominator field is
`candidate_denominator`, and both `top_proposal_indices` and
`top_valid_proposal_indices` are preserved. Consumer envelopes advance to
schema `1.3.0`; legacy V1 verification remains available only for existing
serialized evidence and internal regression tests.

The canonical verifier is:

```text
python3 tools/verify_engine_v2_standalone_scientific_consumer_activation_v3.py
```

It audits the canonical JSON plus the pipeline, consumer, CLI verify, and report
routes. It fails closed if a surface bypasses the shared core, adds another core
call, removes the exact receipt check, adds an authority/execution call, or
enables rank rewriting. Passing this verifier grants no external authority.

The following remain explicitly forbidden until their separate gates close:

- external reservation or molecular cohort execution;
- Historical 9-case A/B or Fresh-128;
- public benchmark execution;
- Stage 0 admission;
- product execution, mutation, automatic rank changes, or customer pose output;
- HIP execution or acceleration claims; and
- public or scientific claims.
