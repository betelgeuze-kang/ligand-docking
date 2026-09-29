# Bounded 2024 human 5-HT6 source-occurrence inventory

The retained article mentions study compounds, assay controls, functional
references and reagents in several contexts. Counting these mentions as
independent binding measurements would inflate the cohort and could mix Ki
with KB, EC50 or cytotoxicity IC50. The new source audit keeps these contexts
separate and binds each declared occurrence to retained source bytes.

## Implemented scope

`tools/product/primary_5ht6_2024_occurrences_v1.py` verifies caller-pinned
contract and inventory JSON, five retained source hashes, and twenty article
spans using one-based inclusive LF byte lines. Numeric and missingness tokens
also require the reviewed row and token positions. It rejects changed source
bytes, dropped required occurrences, duplicate physical-span aliases, endpoint
category changes, missing unresolved issues and attempts to promote source roles
or admission. The existing source ledgers are inputs and are not rewritten.

The actual retained-source invocation reproduces **205 occurrences**, comprising
153 study-compound, 9 binding-control, 4 functional-reference, 37 reagent and
2 cited-only occurrences. There are **78 printed primary test IDs**, not 205
independent compounds or measurements. Six Table 6 Ki entries repeat earlier
reports. Five repeat links lack transcribed primary numeric values and are
explicitly marked unverified; no independent remeasurement is inferred.

PR49/PR59 means and SDs have bound source positions. NA, ND and NT remain
distinct source tokens and never become numeric values or inactive labels.
Olanzapine binding Ki and SB258585 functional KB remain different endpoint
contexts, with unresolved new-measurement versus reused-reference origins.

## Evidence and limits

The portable semantic-mutation tests and workflow trust-boundary tests pass
**57 tests, zero failures/errors/skips**. Isolated Ruff passes. A separate static
review found no actionable defect in this bounded implementation and checked
the declared source-row associations. The root's actual-source CLI invocation
reproduces the earlier receipt exactly as JSON. These are distinct checks and
their counts are not independent scientific observations.

- [Contract](../evidence/human_5ht6_2024_occurrence_contract_v1.json)
- [Inventory](../evidence/human_5ht6_2024_occurrences_v1.json)
- [Portable test and CI verification](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-occurrence-integration-20260930-v9mwd0ts/verification.json)
- [Actual source audit](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-occurrence-integration-20260930-v9mwd0ts/actual-source-root.json)
- [Exact CLI arguments and source pins](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-occurrence-integration-20260930-v9mwd0ts/actual-source-root-run.json)
- [Independent static review scope](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-occurrence-integration-20260930-v9mwd0ts/independent-static-review.json)

The verifier establishes retained-byte and declared-inventory consistency. It
does not establish transcription truth, complete article or supplement coverage,
chemical identity, independent source components or eligibility. The unreviewed
line ranges, unreviewed supplement and thirteen unresolved issue categories
remain explicit. The PR65/PR66 synthesis/table identity conflict is retained.
All source roles remain null, graph inclusion unknown, independent-measurement
denominator unknown, and admission/full-source clearance false. No protected
context discovery, new preflight, training or molecular calculation is performed.

This is a repository research tool, not a newly installed product entry point.
The existing installed CPU execution receipts retain their own implementation
and package hashes. Next source work must resolve actual family/identity/intake
eligibility and comparable endpoints; another inventory count cannot substitute
for those requirements.
