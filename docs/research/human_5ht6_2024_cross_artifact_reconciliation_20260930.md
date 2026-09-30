# 2024 human 5-HT6: additive cross-artifact reconciliation

This connects already audited public transcriptions at source checkout
`53476bce346e4ed9d0dc47ae1bb8e8d817da7abf`. The
[fixed result](../evidence/primary_5ht6_2024_cross_artifact_reconciliation_20260930_v1.json)
is a reproducible representation/semantic correspondence record. **Goal 1 remains
incomplete: roles and the independent-measurement denominator are null, all
training/calibration/evaluation admissions are false, and new independent
measurement credit is zero.**

The [canonical module](../../tools/product/primary_5ht6_2024_cross_artifact_reconciliation_v1.py)
and [repository CLI](../../tools/verify_primary_5ht6_2024_cross_artifact_reconciliation_v1.py)
verify exact byte counts and SHA-256 pins for seven existing repository inputs:
the main occurrence contract and inventory, endpoint transcription audit,
additive Table S1 transcription, Table 5 repeat-correspondence audit, and two
bounded identity/supplement reports. External paths declared by those inputs are
never followed. The endpoint audit's preparation/source-reference sections are
outside the semantic projection. The original PDF/ZIP, molecular requests,
structures, parameter bodies and protected contexts are not verification inputs.
This command does not refresh their source-byte or scientific verification.

| Separate representation denominator | Requested / retained or matched |
|---|---:|
| Main article declared occurrences | 205 / 205 |
| Printed primary human 5-HT6 mean/SD summaries linked to main occurrences | 78 / 78 |
| Table 6 repeat-report links | 6 / 6 |
| Previously untranscribed Table 5 repeats covered by the separate additive audit | 5 / 5 |
| Table S1 physical rows | 71 / 71 |
| Table S1 name-display spans | 89 / 89 |
| Table S1 rows with the same whitespace-normalized local PR label | 39 |
| Other or unresolved Table S1 literal rows | 32 |
| Failed required correspondence links | 0 |
| Independent experiments / measurements | unknown / null |
| New independent measurements credited | 0 |

The 205 main occurrences retain all 153 study-compound, nine binding-control,
four functional-reference, 37 reagent and two cited-only entries. The other or
unresolved Table S1 rows include the printed PR109 and 31 comparator/calibration
rows. They are retained, rather than being failed receptor-binding candidates.
Occurrence, name-display, endpoint-summary and repeat counts are separate
representation denominators and are never summed into an experimental cohort.

## Contract and preserved distinctions

Every primary endpoint link requires the same declared occurrence ID, printed
label and human radioligand-binding Ki endpoint. Numeric mean/SD strings and
their published units are preserved. The declared `uM`/`µM` unit correspondence
does not change a value. Historically untranscribed values stay untranscribed in
the original inventory; the separate newer endpoint summary is attached as a
link. NA, ND, NT, missing values and unrelated endpoint categories cannot become
numeric Ki or activity labels.

Each repeat binds its original occurrence, target and mean. The Table 6 absent
uncertainty remains absent; it does not inherit the primary SD as a newly
reported Table 6 result. The five Table 5 additive correspondences must agree
with the same primary summaries. All six links remain repeated reports with no
established independent remeasurement or chemical identity.

Table S1 links use local printed-label agreement only. They do not verify a
chemical graph, salt, tautomer, batch or assayed state. C18, IAM and HSA keep
their own endpoint ownership; the C18 pH labels stay chromatography conditions,
while receptor target, species and receptor-assay pH remain null. PR59's HSA
group stays blank, PR49's absence supplies no measurement, and name-display
repetitions do not add physical rows. The printed spelling variants and seven
additional literal names remain in the retained exception record.

The result retains these five dispute groups:

- PR9: table mean 0.318 ± 0.018 µM versus prose mean 0.133 µM; no corrected value
  or automatic merge.
- PR39: the separately pinned identity report's table-versus-synthesis ring-element
  conflict; corrected identity remains null.
- PR65/PR66: the original table-versus-synthesis identity assignment conflict.
- PR109: the literal Table S1 label remains unresolved and unmapped.
- Supplement other-target PR78 versus main Table 6 PR77: correspondence remains
  unresolved and no relabeling is performed.

All 13 historical main gap entries and 19 unchecked LF-line ranges remain in the
result. The historical main `supplement_reviewed=false` is explicitly historical;
the later Table S1 coverage is retained as an additive scope. Its six unreviewed
or unextended scope statements and the biological-curve count-only boundary
remain present. The 78 curve-label count supplies no newly transcribed curve
values, independent measurement denominator or source component.

## Run and verify

From this repository root, emit the deterministic record to a new external file:

```bash
python3 -B tools/verify_primary_5ht6_2024_cross_artifact_reconciliation_v1.py \
  --repo-root . > /tmp/5ht6-cross-artifact-rebuild.json
```

Verify the committed-form fixed record against all seven pins and a fresh rebuild:

```bash
python3 -B tools/verify_primary_5ht6_2024_cross_artifact_reconciliation_v1.py \
  --repo-root . \
  --verify-record docs/evidence/primary_5ht6_2024_cross_artifact_reconciliation_20260930_v1.json
```

The module also supports `python3 -B -m
tools.product.primary_5ht6_2024_cross_artifact_reconciliation_v1` with the same
arguments. Absent/changed input, noncanonical paths, duplicate JSON keys,
nonfinite constants, required membership changes, mismatched repeats, endpoint
mixing or authority promotion fail closed. A failure retains the requested
representation denominators and reports no successful reconciliation. The CLI
has no caller-supplied replacement pins or admission action.

## Local verification receipt

The actual CLI reports `PASS_fixed_public_transcription_record`, verifies seven
input pins and reproduces the fixed JSON byte for byte. The fixed result is
316,336 bytes, SHA-256
`509a9fd926c2ac785d1f972791553d4c836255fa5f8a634d1c040eee357d5dbd`.
The canonical module is 26,900 bytes, SHA-256
`dd7fce543c3c0e9b1569f8d690e381d95eda34eff341a31235b13287e26f700c`;
the wrapper is 408 bytes, SHA-256
`d66885978b13629023a19c7950aef26e29ee20404e0e4aa0e5cc45dc18f6bd7c`.

The [portable tests](../../tests/unit/test_primary_5ht6_2024_cross_artifact_reconciliation_v1.py)
passed **39 tests, zero failures/errors/skips**, using:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -B -m pytest \
  -q -c /dev/null --noconftest -p no:cacheprovider \
  tests/unit/test_primary_5ht6_2024_cross_artifact_reconciliation_v1.py
```

Their SHA-256 is
`318cd0dc62b44164f5af930e349be7061ec9f2c9f90339ef7175424b000a0930`
(9,741 bytes). Twenty-nine parametrized in-memory semantic mutations and the
additional focused cases cover dropped/duplicate members, physical-row aliasing,
wrong targets/endpoints, missingness imputation, role/identity/independence
promotion, suppressed disputes, wrong repeat references, blank-cell changes,
ambiguous JSON, absent or changed pins and fixed-result drift. Poisoned external
references demonstrate that this semantic projection does not traverse them.
These use already public audited transcriptions and inert mutations; no PDF,
network, molecular runtime or new assay observation is required. Ruff passes for
both modules and the test file. The local machine-readable verification receipt
is retained at `/tmp/ht6-cross-artifact-stage/verification-receipt.json`; this is
local software evidence, with no hosted CI claim.

This connects existing audit artifacts and preserves missing evidence. It does
not establish actual assay batch/microstate equality, raw repeats/per-row N,
construct/buffer pH, censored weak-binding coverage, material-specific rights
exceptions or independently sanctioned source-family and dataset-role decisions.
Those remain scientific/intake blockers. Separate SRO development starts and
the fixed historical nine-case cohort retain their own execution and evidence
boundaries; they supply no new independent holdout or endpoint admission here.
