# Censored concentration rank diagnostics

`betelgeuze_engine.product.censored_rank_metrics` computes descriptive concordance within one already authorized, frozen target/domain/assay/endpoint/unit cohort. It does not load labels, authorize access, train, calibrate, or change source roles. Callers must enforce those boundaries and exclude reference-self comparisons consistently across all arms before invocation.

Supply positive finite concentration endpoints with relation `=` or strict `>`. A measured value equal to a strict censor bound is known to be smaller; overlapping ranges and two right-censored endpoints are unordered. Other relations are rejected. Reported standard deviations are not confidence intervals and must remain in source records.

All arm scores must be higher-is-better. Missing IDs and `None` remain missing; unknown IDs, booleans and nonfinite numbers are errors. Counts retain the full candidate/pair denominator and distinguish endpoint ties, unknown endpoint order, score ties, missing scores, concordance and discordance. Score ties contribute one half; endpoint ties are excluded from ordered pairs. No comparable scores yields `None`, never zero.

Do not compare concordance across unequal pair coverage or claim AI value from an absent arm. This utility does not establish equal budgets, independent evaluation, affinity accuracy, or scientific qualification. Existing binary-label comparison/admission flows remain unchanged.
