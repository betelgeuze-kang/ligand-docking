# Engine V2 standalone synthetic scientific core v3

`execute_repository_synthetic_d0_standalone_scientific_core` is the bounded
bridge between the package-owned synthetic D0 request and the fixed64
scientific pipeline. It accepts only the exact `DockingPipelineRequestV1`; the
caller cannot supply a source bundle, allocation, components, coordinates,
thresholds, weights, scores, terms, validity, ranks, results, or authority.

The executor owns this exact order and performs every execution boundary once:

1. derive and authenticate the repository synthetic D0 source adapter receipt;
2. construct the installed current-V7 refiner for fixed slots 24–43;
3. construct the installed Python-reference Scorer V1;
4. execute the fixed64 scientific pipeline;
5. seal the complete standalone receipt.

`StandaloneScientificCoreReceiptV1` embeds both the source-adapter receipt and
the scientific-pipeline receipt. It therefore preserves the exact request and
fixture admission, source and allocation identities, all stage receipt hashes,
64 ordered final candidate records, complete ScorerV1 terms, pose validity,
primary rank, valid-only rank, and every typed failure. Rejected or failed
slots remain in the denominator and are never retried or reallocated.

This receipt is the canonical result for `DockingPipeline`, CLI, Python API,
the exact D0 diagnostic benchmark adapter, and product shadow. That activation
is restricted to the exact package-owned repository synthetic D0 fixture. The
product-shadow surface may display evidence and allow an operator second
opinion, but it cannot mutate a rank or emit a customer pose.

Consumer activation grants no external reservation, real molecular execution,
historical A/B, Fresh-128, public benchmark, product mutation, customer-pose,
Stage 0, HIP, or scientific-claim authority. GitHub Actions and test doubles
remain non-production actors.

The frozen policy is
`config/engine_v2_standalone_scientific_core_v3.json`; the independent verifier
is `tools/verify_engine_v2_standalone_scientific_core_v3.py`.
The surface-routing boundary is frozen separately in
`config/engine_v2_standalone_scientific_consumer_activation_v3.json` and audited
by `tools/verify_engine_v2_standalone_scientific_consumer_activation_v3.py`.
