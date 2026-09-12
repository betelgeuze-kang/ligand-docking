# Receptor method contradiction veto

The research ChEMBL receptor intake now rejects an explicit serotonin receptor
subtype in the native method description that contradicts the supported 5-HT6
catalogue target. Matching assay/document/target IDs and confidence 9 alone do not
resolve contradictory experimental metadata. Mixed subtype descriptions also fail.
This is a bounded contradiction detector, not a validated natural-language method
classifier: descriptions without a recognized subtype retain the previous curated
scope. Original descriptions, measurements and roles remain unchanged.

Fresh synthetic controls reproduce 11 failures before the fix and preserve three
positive/noncontradictory cases. The expanded repository regression passed 548 tests
with no failures or skips. A separate captured-development audit passed three tests,
including old-versus-new admission on the actual conflicting native method, frozen
prediction/checkpoint preservation, and the original 75-file WIP snapshot.

The input implementation hash changes. Existing frozen checkpoints continue to use
their original runtime; do not rewrite their implementation hashes or silently
migrate them to this source. No new fitting, score schema change, customer execution,
scientific qualification, or independent reviewer approval is granted by this fix.
