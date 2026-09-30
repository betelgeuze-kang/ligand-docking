# Existing human 5-HT6 development source: bounded metadata result

Two exact ChEMBL Ki queries supply **no additional molecule accession** for the
existing reserved development source. Extending its preparation descriptor or
source adapter cannot create the missing second candidate.

| Exact filter | Total records / received | Distinct molecule accessions | Additional |
|---|---:|---:|---:|
| Assay CHEMBL5734474, Ki | 1/1 | 1 | 0 |
| Document CHEMBL5727345, target CHEMBL3371, Ki | 1/1 | 1 | 0 |

Both return activity 27765488, molecule CHEMBL5095172, compound record 4373762,
and `next=null`. The complete denominators apply only to these two filters.
They do not establish chemical-graph equivalence, method/construct matching,
activity values or the absence of candidates in other sources.

The original US10441590B2 `development_test / evaluation_only` reservation is
unchanged. Numeric outcomes, free-text assay descriptions and primary patent
content were excluded. Source roles were not reassigned and no preflight,
training, molecular calculation or new admission was performed.

Before reserved access, a nonreserved CHEMBL25 projection probe rejected three
responses because of server-added aliases or overly strict alias checks. The
successful probe sampled 10/152 records, leaving 142 intentionally unfetched;
this denominator is separate from the complete 1/1 reserved queries. The guard
allows nine requested metadata fields plus short nonnumeric type/relation/units
aliases, removes those aliases before saving, and rejects unknown/value/comment
fields. Requests used the ChEMBL skill helper. Stored response hashes refer to
sanitized JSON, not original HTTP bytes. All failed probe receipts are retained.

The final query receipt is dated 2026-09-29T15:45:14.811670Z. The
[packet](/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-reserved-metadata-sb8m9_a9/README.md) and
[evidence index](../evidence/human_5ht6_reserved_metadata_query_v1.json)
retain requests, responses, pagination and the original reservation linkage.

The next source step must resolve a genuinely available primary candidate's
identity, source-family roles, endpoint/method correspondence and prepared state.
Existing [2024 occurrence work](human_5ht6_2024_occurrences_20260930.md)
helps bind retained source spans, but counts of mentions or repeat reports do
not replace independent measurements. These queries should not be repeated as
if they were an unfinished acquisition path.
