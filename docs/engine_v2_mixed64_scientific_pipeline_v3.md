# Engine V2 fixed64 synthetic scientific core v3

`execute_synthetic_mixed64_scientific_pipeline` is the single sealed synthetic
scientific execution boundary for the current global-orientation fixed64 stack.
It accepts only an exact `Mixed64ProposalSourceBundleV1`, an unused exact
current-V7 refiner, and an exact Python-reference `ChemistryPoseScorerV1`.

The executor owns this immutable order and invokes every stage once:

1. source-bound fixed64 proposal production;
2. failure-aware pre-refinement geometric admission;
3. exact operational proposal materialization;
4. current V7 refinement plus full-Cartesian post-admission;
5. Scorer V1, element-aware pose validity, and stable primary/valid-only rank.

The source bundle owns the allocation. Callers cannot supply allocation,
candidate coordinates, thresholds, scorer weights, scores, terms, validity,
ranks, results, reservations, or authority. Every stage retains exactly 64
ordered slot records; rejected and failed slots remain typed evidence and are
never deleted, retried, or reallocated.

`Mixed64ScientificPipelineReceiptV1` binds the exact source and allocation
receipts, the five stage receipts, the pipeline implementation source SHA-256,
the complete final Scorer V1 terms and pose-validity evidence, and both stable
ranking views. Earlier full stage batches are not recursively duplicated in the
outer serialized receipt; their receipt SHA-256 values bind the chain, while the
complete final scoring batch remains directly available to consumers.

This contract is repository synthetic-fixture evidence only. It does not admit
the standalone, benchmark, API, or product-shadow consumers. It grants no
reservation, molecular cohort, historical A/B, Fresh-128, Stage 0, HIP,
customer-pose, product mutation, public benchmark, scientific claim, or
production authority. GitHub Actions and test doubles remain non-production
actors.

The frozen policy is
`config/engine_v2_mixed64_scientific_pipeline_v3.json`; the independent verifier
is `tools/verify_engine_v2_mixed64_scientific_pipeline_v3.py`.
