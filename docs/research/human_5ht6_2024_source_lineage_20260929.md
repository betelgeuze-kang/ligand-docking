# 2024 human 5-HT6 source lineage: endpoint and reference review

The retained 2024 paper contains reference and test-compound occurrences beyond
the existing PR49/PR58/PR59 ledger. Its Table 6 identifies **olanzapine as a
binding Ki reference and SB258585 as a functional KB reference**. This is a
concrete incompleteness in the three-row source-family review. It is not evidence
that any row was wrongly admitted: the historical result was
`identity_clear_review_required`, all assigned roles remain null, and admission
remains zero.

The new [metadata annotation](../evidence/human_5ht6_2024_full_source_lineage_v1.json)
preserves the original ledgers and receipts. Its current status is
`blocked_review / NOT_PROMOTED / NOT_QUALIFIED`. The filename names the
whole-source review objective; complete source-family clearance is **not**
claimed. This work used retained public sources and saved public candidate and
preflight metadata. No protected source-role universe, outcomes, model weights,
ChEMBL database, new download, model run or physical experiment was used.

## Source occurrences now made explicit

The primary source is DOI `10.3390/ijms251910287`. The retained university PDF
is 7,957,708 bytes, SHA-256
`4bd52d8bbb3c216b3d6976d17584a2d00b6608643df50278b80e7b94f4ab02ca`,
at `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-primary-20260929/2024.pdf`.
Its CC BY 4.0 notice is retained; intended training/product-use review is still
separate. PDF pages 7-11 and 39-40 were rendered and visually checked because
the retained `2024-layout.txt` contains repeated overprinted table text.

| Binding source | Physical PDF page | Printed test-compound IDs | Rows |
|---|---:|---|---:|
| Table 1 | 7 | PR1-PR12 | 12 |
| Table 2 | 8 | PR13-PR28 | 16 |
| Table 3 | 9 | PR29-PR38 | 10 |
| Table 4 | 10 | PR39-PR66 | 28 |
| Table 5 | 11 | PR67-PR78 | 12 |

These are 78 printed identifiers in the human 5-HT6 Ki tables, not 78 verified
chemical identities or admitted measurements. This annotation inventories the
IDs without expanding the original 30-row measurement ledger. The source's
PR65/PR66 table-versus-synthesis conflict remains unresolved.

Table 6 on page 11 contains PR49, PR66, PR68, PR71, PR73, PR76 and PR77. Its six
numeric test-compound Ki entries repeat the same compounds and means from
Tables 4-5; independent remeasurement is not established. PR66 has `ND` in the
extended panel's 5-HT6 columns. Neither that missing entry nor a repeated value
becomes a new independent Ki observation.

| Table 6 occurrence | Printed target and endpoint | Printed value, micromolar | Source treatment |
|---|---|---:|---|
| Olanzapine, footnote d | Human 5-HT6 binding Ki | 0.007 | Reference value; new measurement versus reused value unresolved |
| SB258585, footnote e | Human 5-HT6 functional KB | 0.0003 | Functional reference; never relabelled as binding Ki |
| PR49/PR68/PR71/PR73 | Human 5-HT6 functional KB | Recorded separately in the annotation | Four functional occurrences, outside the Ki ledger |
| PR76 | Human 5-HT6 functional EC50 | 0.199 | Agonist-response occurrence, outside the Ki ledger |

`NA` means the source's endpoint-specific “not active”; `ND` means not
determined; `NT` concerns the separate cytotoxicity test. None is a numeric
zero, a censored Ki value or an interchangeable active/inactive receptor label.
The other Table 6 reference names are ziprasidone, buspirone, SB269970 and
clozapine. Their printed targets are retained without importing them into the
human 5-HT6 binding endpoint.

Methods identify [3H]-LSD and methiothepine in the binding assay and 5-CT as
the functional agonist challenge. Section 3.2.2 cites reference 60, Cheng and
Prusoff (1973), for Ki conversion. Section 3.2.3 cites reference 56, Wichur et
al., *European Journal of Medicinal Chemistry* 225 (2021), 113783, for the
functional inhibition-curve calculation. These are method citations, not
established origins of the specific reference values. Table 6's lettered
footnotes identify names and supply no row-specific source-paper citation.
The original cited papers were not opened in this audit. In particular, the
earlier Biomolecules annotation of an SB-258585 cited Ki is not transferred
to this 2024 KB occurrence.

The annotation also catalogs the separate Tables 7-9 test IDs, cytotoxicity and
ADMET references, the 18 chromatography calibration standards named in Methods,
and additional receptor controls. This is a bounded text inventory, not complete
chemical graph mapping. Table 6 names ziprasidone for D2 while Methods name
risperidone; both declarations are preserved. The paper's supplement, including
Table S1 standards, was not reviewed, and a whole-family completeness claim
remains unavailable.

## What the current graph policy actually establishes

The reviewed implementation is
[`public_assay_components.py`](../../betelgeuze_product/public_assay_components.py)
at source HEAD `6ebaccafed8a9090b6bc1a620d7cd1ff153d5fd0`; its exact file hash
and the related builder/preflight hashes are in the annotation.

`document_keys` consumes explicit DOI, PMID, ChEMBL document and patent fields.
It does not traverse bibliographies. `node_from_raw` hashes the supplied
document and chemical keys. `component_index` joins supplied nodes that share
any typed key. Those keys do not distinguish binding Ki from functional KB,
test compounds from reference controls, or independently measured values from
repeated ones. The policy operates on the supplied metadata before endpoint
selection. This describes existing mechanics; it does not decide which
reference/reagent occurrences should be supplied.

The original paper builder emits only ledger rows. The prior Biomolecules
diagnostic explicitly added its Table 1 SB-258585 reference as a separate node.
Neither builder is a general whole-paper citation parser. Consequently, adding
a bibliography citation alone must not be described as a verified new graph
edge. Also, `public_assay_preflight.py` leaves training, calibration and
independent-evaluation permissions false even for `identity_clear_review_required`.
No admission bug or policy change is demonstrated here.

There is a narrower, **conditional public key trace**:

1. If the printed 2024 Table 6 SB258585 reference is included as an occurrence
   node, its explicit 2024 DOI shares the document key with PR49/PR58/PR59.
2. If the retained PubChem CID 3248571 identity is used for that name link, its
   canonical key matches the already retained public Biomolecules SB-258585
   reference node. This does not verify its assayed salt or microstate.
3. The saved 13-candidate Biomolecules family preflight records that reference
   node as `blocked_identity`, in a component of 135,178 nodes with 1,336 reserved
   nodes. These are the historical receipt's counts, not an expanded 2024 result.

The annotation records the exact public document/canonical keys, candidate ID
and historical receipt hash. It does **not** load or reconstruct the terminal
protected path, execute a new full preflight, assign a new component ID, change
the blocked-row count, or relabel the three historical 2024 results. The outcome
is `blocked_review`: the narrower three-row result cannot certify the full
source family. Whether assay controls, reagents and cited-only comparisons
belong in the same inclusion scope requires a separately frozen contract;
the observed connection is not a reason to remove a reference after seeing
outcomes.

## Verification and remaining work

The artifact binds 13 retained inputs by SHA-256 and byte count. Checks covered
the original PDF, ledger and identity-response pins; the visual table/method
review; the 78 unique IDs and Table 6 endpoint ownership; the matching saved
reference candidate and its recorded blocked result; and the current policy
functions. Original ledger roles remain null and original file hashes are
unchanged. JSON integrity, input hashes, table-ID coverage, historical-record
bindings and the public key trace were checked separately after writing the
annotation. No product implementation changed, so no new implementation test
or mirrored documentation test was added.

The 13 pinned inputs are the 2024 PDF and its retained text; the original
2024 and five-paper ledgers; the historical five-paper preflight and retrospective
plan; the public SB258585 identity response, Biomolecules candidate metadata
and saved family preflight; and the four inspected component, preflight and
candidate-builder source files. Exact paths, bytes and hashes are in `inputs`.
The retrospective plan is metadata; no checkpoint or prediction file was
opened for this annotation. From this repository root, the retained-input hashes
can be checked without importing the product or reading another file set:

```bash
python3 -B - <<'PY'
from pathlib import Path
import hashlib
import json

root = Path.cwd()
path = root / "docs/evidence/human_5ht6_2024_full_source_lineage_v1.json"
packet = json.loads(path.read_text())
for name, item in packet["inputs"].items():
    source = Path(item["path"])
    raw = (source if source.is_absolute() else root / source).read_bytes()
    assert len(raw) == item["byte_count"], name
    assert hashlib.sha256(raw).hexdigest() == item["sha256"], name
print("retained_input_hashes_verified=", len(packet["inputs"]), sep="")
print("annotation_sha256=", hashlib.sha256(path.read_bytes()).hexdigest(), sep="")
PY
```

This verifies the declared retained bytes, not the truth of source transcriptions,
historical execution or scientific qualification. Changed policy source files
will correctly fail the old hash check; they require a new review version,
not resealing this annotation to a later implementation.

All 30 original outcomes were already visible before the prior retrospective
diagnostic. This audit also displayed the public 2024 binding tables; neither
those values nor a new subset of the same source can be called an untouched
blind holdout for this workflow. Fit/calibration/independent-evaluation admission
remains zero. Existing PR49/7XTB preparation and CPU comparison remain separate
development evidence, with no observed PR49 reference pose or validated Ki
ranking.

The next substantive source task is to define an explicit occurrence-inclusion
contract for test compounds, reference controls, assay reagents and cited-only
comparisons, then complete the source/supplement identity manifest under that
contract. Keep endpoint relations separate and freeze the rules independently
of observed outcomes before seeking a fresh sanctioned role/preflight decision.
Strong-data completion still needs permitted independent source components,
assayed chemical/construct correspondence, intended-use rights review, and
fit/calibration/evaluation roles fixed before an allowed new evaluation cohort's
outcomes are opened. This annotation closes the identified review omission;
it does not manufacture those missing data or require restoring the large
ChEMBL database.
