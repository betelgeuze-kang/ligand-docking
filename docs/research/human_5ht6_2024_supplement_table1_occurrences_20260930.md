# 2024 human 5-HT6 supplement: typed Table S1 occurrences

The [additive typed sidecar](../evidence/human_5ht6_2024_supplement_table1_occurrences_v1.json) records **71 physical table rows: 45 numbered rows and 26 calibration rows** from `SI_Table1.pdf`, physical page 1. It preserves their printed names, positions, name spans and separate chromatography endpoint contexts. **New independent human 5-HT6 Ki credit is 0; the independent measurement denominator and assigned role remain null, admission is 0, and scientific qualification remains false.**

This artifact leaves the earlier 205-occurrence contract and 123-literal manifest unchanged. The [access receipt](../evidence/human_5ht6_2024_supplement_access_v1.json) and [bounded review receipt](../evidence/human_5ht6_2024_supplement_review_v1.json) remain separate evidence. The review document is bound to its committed bytes at `e70eb8e4d66f63c4a928b627a0f3fc0a41653133`: 6,358 bytes, SHA-256 `12046558f50371de2950e0b5877a687dc3c429d72c694c813f4b66382338d494`.

| Reviewed name scope | Physical rows | Layout LF byte lines | Endpoint ownership |
|---|---:|---|---|
| Numbered name column | 45, printed rows 1–45 | 5–49 | C18 at pH 2.6 / 7.4 / 10.5, IAM, HSA |
| C18 calibration block | 8 | 51–58 | C18 chromatography at the three printed pH values |
| IAM calibration block | 9 | 59–67 | IAM chromatography |
| HSA calibration block | 9 | 68–76 | HSA chromatography |

The layout is the exact output of `pdftotext -layout - -` (observed Poppler 22.02.0), 15,086 bytes, SHA-256 `b85979e353b171ad0961b80973600bca8c433f499da6dbdcc4e94c99dec3774a`. Split it on LF bytes only: its final form-feed byte is line 77. Row SHA values exclude the LF byte; name-span offsets are one-based byte positions with an inclusive end. Endpoint headers are on layout line 1 and subheaders on line 3. This source-specific parser fails if extraction bytes change.

Every row has one primary name display. IAM and HSA calibration rows also repeat the name beside their data panel, giving **89 name-display spans for 71 rows**. Those repeated displays are attached to the same physical row and do not create extra measurements. HSA repeats use lowercase while the primary names preserve initial capitalization. The typed name kinds (`study_literal_label`, `comparison_drug_name`, `calibration_standard_name`) describe printed table use; they assign no training, calibration or evaluation role.

Numbered rows contain 40 PR-coded names and five comparison drug names. Thirty-nine PR-coded names have a whitespace-only local-label match to prior PR1–PR78 labels; this is no chemical identity verification. `PR8` is preserved without a space in row 21. **`PR109` is visibly printed in row 22** and remains unresolved; it is not corrected to PR10, PR9 or another compound. **PR49 is absent from the numbered name column**; this absence does not imply a numerical result. **`PR 59` is row 31**, with numeric content in the three C18 groups and IAM, and a blank HSA group. Blank cells remain blank.

The five printed comparison names at rows 41–45 are `Venlafaxine`, `Mirtazapine`, `Amitriptyline`, `Desipramine`, `Mianserin`. The HSA calibration names `Trimetoprim` (block row 3, layout line 70) and `Propranolol` (block row 5, line 72) bring the separately reviewed additional-name list to seven. All seven are absent from the earlier other-literal manifest under casefold lookup. They are new literal occurrences in this additive record, with unverified chemical identity and graph inclusion unknown.

Printed variants remain distinct: `Colichicine` versus prior lead `colchicine`; `Acetanilidine` versus `acetanilide`; `Propiohenone` versus `propiophenone`; `Octanophenone` versus `octanonophenone`. The C18 block separately prints `Propiophenone`. These strings are neither corrected nor merged as chemical aliases. The earlier other-target PR78 versus main Table 6 PR77 conflict remains an unresolved correspondence in the pinned review; this Table1 transcription makes no relabeling.

Endpoint records retain printed stationary-phase ownership and the three chromatography pH labels. They set receptor target, species and receptor-assay pH to null. Numeric-content flags establish only whether a group has printed digits: this sidecar copies no retention values, derives no Ki, and does not assert complete t1/t2/t3 replicates. Twenty-five numbered rows have HSA numeric content; 20 have a blank HSA group. In particular, PR17 has HSA numeric content without a complete set of printed replicate cells. Calibration repetitions and retention replicates are not receptor-binding experiments.

Biological curves are outside this typed-occurrence extension. The inherited review count of 78 printed 5-HT6 binding curve labels is retained only as a count. There is no new curve transcription, digitized value, independent Ki remeasurement, source component, or measurement denominator. The synthesis and remaining rights/chemical review limits stay as stated in the earlier review.

The [verifier](../../tools/analysis/verify_human_5ht6_2024_supplement_table1_v1.py) requires an explicit caller sidecar SHA, the retained ZIP, the prior external literal manifest, and all pinned repository receipts. It reads PDF bytes from the ZIP in memory, checks every member SHA and ZIP CRC, then compares fixed layout bytes, all row/name spans, row order, endpoint ownership and numeric-content presence. It rejects absent inputs and byte changes, as well as promotion or mutation of typed rows. It does not emit chemical graphs or run protected-context preflight. It does not newly verify human visual interpretation, copyright exceptions or scientific eligibility.

The [local verification receipt](../evidence/human_5ht6_2024_supplement_table1_verification_v1.json) records the actual source-backed execution and 11 rejected local mutation/missing-input cases. No hosted CI source-verification result is claimed. The source PDF is not bundled; CI without the original ZIP and manifest must fail this command, rather than substitute a synthetic fixture or report source verification.

Reproduce from the isolated repository root with the retained paths available:

```bash
python3 tools/analysis/verify_human_5ht6_2024_supplement_table1_v1.py \
  --sidecar docs/evidence/human_5ht6_2024_supplement_table1_occurrences_v1.json \
  --expected-sidecar-sha256 5cdbced83cadd78ba2ce48317975d581c0b98bad466b3bd7c0c81a3fa12fb234 \
  --archive /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/5ht6-primary-20260929/2024-supplement-s001.zip \
  --literal-manifest /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-5ht6-identity-manifest-mq_dyte7/identity-manifest.json \
  --repo-root .
```

Sidecar SHA-256: `5cdbced83cadd78ba2ce48317975d581c0b98bad466b3bd7c0c81a3fa12fb234`. Verifier SHA-256: `c066011782c130636fce4f4f7005b1465c54e4ec676ddc87f763f85ab84d193c`. The official ZIP is 16,820,378 bytes, SHA-256 `f27fbee99054e7b3d866e1e46164961758d4c5fd3c031e871aff9c454f3a8363`; its Table1 member is 545,203 bytes, SHA-256 `d4998be58c84f82a42291db53370620caa313c7431f5fabf7f0a4194e3e65f8d`. Access receipt SHA-256 is `c0727e764f69a6ae436bcaf78d732343f2d75135e34e9180e93c097ef419987e`; review receipt SHA-256 is `7cceca45b8d899d0a001b5a1e7ed71b68914fa75078713790ec1d551b05b30ad`.

Source attribution: Zaręba, P.; Drabczyk, A.K.; Wnorowski, A.; Maj, M.; Malarz, K.; Rurka, P.; Latacz, G.; Duszyńska, B.; Ciura, K.; Greber, K.E.; Boguszewska-Czubara, A.; Śliwa, P.; Kuliś, J. *Low-Basicity 5-HT6 Receptor Ligands from the Group of Cyclic Arylguanidine Derivatives and Their Antiproliferative Activity Evaluation*. International Journal of Molecular Sciences 2024, 25, 10287, [DOI 10.3390/ijms251910287](https://doi.org/10.3390/ijms251910287), [official supplementary ZIP](https://res.mdpi.com/d_attachment/ijms/ijms-25-10287/article_deploy/ijms-25-10287-s001.zip). © 2024 by the authors; licensee MDPI, Basel, Switzerland. The retained article p1 gives [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); [MDPI policy](https://www.mdpi.com/openaccess) supplies the supplement-use context recorded in the pinned review. The original PDF is not republished here.

Modification notice: names, headers and positions from Table1 are transcribed into typed JSON; presence flags and local grouping are added; numeric values are omitted. Printed spelling, case and spacing are retained without editorial corrections. CC BY evidence remains conditional on applicable third-party exceptions, licensor-held rights and intended-use attribution/modification notices. The asset exception audit is incomplete; this does not issue blanket training/product rights clearance or promote scientific eligibility.
