# Prespecified candidate-policy ordering, version 2

The existing comparison runner accepts the unchanged v1 protocol and an opt-in `prepared_candidate_comparison_protocol_v2`. V1 retains the original source-order engine, ID-based predicted ties, fixed arm order, score meanings, evaluation thresholds and failure accounting. Historic results are not recomputed or resealed.

V2 requires all v1 fields plus exactly:

- `tie_policy`: `seeded_pool_order`;
- `selection_seed`: a non-boolean integer in 0..4294967295;
- `arm_order`: an explicit permutation of `similarity`, `engine`, `ai_engine`, `similarity_engine`.

For equal predictions, the runner orders candidates by SHA-256 of canonical `{seed,pool_index}` and then the original pool ordinal, not by their record names. Larger predictions still precede smaller ones. The unprioritized engine retains source order. Pool, seed and arm order are frozen with original inputs before outcomes are read. Renaming IDs consistently without reordering the pool does not change tied physical candidate selection. Reordering the source pool is a different predeclared experiment. This removes one naming artifact; it does not establish a universally unbiased selection policy. Plan multiple independent seeds and arm-order repetitions before outcomes, and report their variability rather than select the best run afterward.

The actual worker sequence follows `arm_order`. All four workers retain the same wall budget and the original engine call caps; failed/late/unprocessed candidates remain in the denominator. Final-score ties still use the unchanged fractional expected-hit metrics. Cold fit, model reuse and completed-journal resume remain distinct. All protocol fields must still match to reuse a prior model; no new exception to fit-source or evaluation guards is added.

Pure similarity workers now import only the prediction/feature path, not Torch or the molecular engine. Common parent preflight can still load those owners to bind the whole experiment; that common cost remains separately measured. Other arms load their actual CPU dependencies inside their measured budget. This is an import-boundary improvement, not a measured molecular speedup. Source hashes change, so existing comparisons require the original implementation for resume; no migration or force option is introduced.

The new 17 synthetic cases check v1 compatibility, ID-independent v2 ties across four seeds, malformed order rejection, binding changes, a real isolated similarity worker with Torch/engine imports forbidden, and actual four-arm V2 computation followed by exact completed resume. Original comparison tests remain enabled. No new public data, model registry entry, learning-quality claim, GPU, docking search, MD or scientific/customer qualification is introduced.
