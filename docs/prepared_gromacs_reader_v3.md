# Prepared source reader v3: explicit protein residue insertion codes

`prepared_gromacs_components_v3` adds a narrow input profile for published protein topology residue tokens such as `446A`. It preserves the original token and matches it to PDB sequence number `446`, insertion code `A`, and the exact residue name. This does not assert that a noninteger residue token is valid standard GROMACS syntax. The reader remains a source-bound projection for the existing cross-interaction consumer, not a GROMACS preprocessor or preparation engine.

The request has the same required keys as v2. Set `schema_version` to `prepared_gromacs_components_v3` and provide each chain's existing ordered `molecule_itps` list. Every path/SHA/source ID remains required; a blank PDB chain ID remains explicit. The list is used in its original order, with molecule atom-index offsets and original source labels retained.

Only the protein `[ atoms ]` residue-number field accepts positive decimal digits optionally followed by exactly one ASCII letter. Suffix case is preserved and matched exactly. Ordinary integer tokens also receive explicit v3 metadata: `residue_number_token` contains the original text, and `insertion_code` is empty. For suffix-bearing tokens the latter contains the original letter. These fields are retained in each canonical atom's `prepared_gromacs_source` metadata alongside its original row, atom index, molecule source, charge and mass.

Residue identity uses `(sequence_number, insertion_code)` within a chain, with a consistent residue name and unique atom names within that identity. Thus `446 GLU` and `446A NME` can coexist, including repeated atom names across the distinct residues. A single residue identity cannot be split ambiguously between two listed molecule sources. Both the optional blank-element transfer and final canonical atom binding require exact sequence number, insertion code and residue name. Missing, mismatched, case-changed, multiple-letter or malformed suffixes reject; no cap is deleted, coordinate generated, or residue renumbered.

Ligand residue numbers, atom indices, charge-group indices, and bonded-table indices keep their integer requirements. Existing coordinate, source hash/postflight, complete atom/parameter mapping, inactive-POSRES, chemical-state, unit and element checks remain in force. No force/scoring code or Engine V2 file is changed. v3 provenance records this residue-identifier profile and explicitly denies standard-GROMACS validity for the noninteger token. It does not certify the source preparation, chemical state, assay mapping, or product qualification.

v1 and v2 still reject insertion-bearing residue tokens; their output dictionaries and source/canonical hashes remain unchanged. Regression checks retain existing 73 synthetic cases and add 39 controls, including the same sequence number with two insertion identities, both PDB binding paths, malformed/dropped suffixes, other integer fields and three parent-derived v1/v2 output-hash controls. Before implementation, 34 new-contract controls failed because v3 was unsupported and 5 new legacy controls passed; these are not 34 historical scientific failures. After implementation all 112 synthetic cases pass. No molecular energy, reference comparison, measured-label or protected-input run is part of these reader tests.

## Inert SDF data-field names in v3

v3 also accepts one bracketed ASCII unit token appended directly to the existing ASCII data-field name, for example `>  <IC50[uM]>  (1) `. The suffix begins with an ASCII letter and contains only ASCII letters and digits. Empty, nested, repeated, non-ASCII or control-containing suffixes and whitespace between the base name and suffix reject. Compound unit expressions are outside this narrow profile. v1/v2 and the default `_sdf_projection` call retain their original header grammar.

The complete field name, every value string and the full original SD data tail are retained in provenance. The mol block is unchanged. Values such as `-1`, `0` or `error-1` remain inert strings: they are not parsed, converted, validated as assay observations, or joined to a training label, score, potential energy or force. Published source metadata alone does not establish original assay correspondence. Changing only the value changes the source hash and provenance while leaving supplied canonical coordinates, atom charges, topology and parameters unchanged; provenance-bearing canonical system hashes consequently change. Duplicate fields, unbound metadata, content after a record terminator and multiple mol blocks still reject.

The SDF extension adds 26 fresh synthetic controls to the preceding 112 reader cases. On the previous v3 reader, 6 extension expectations fail because its header grammar rejects the new field name before the intended checks, and 20 pass. These counts describe a new input-contract extension, not six scientific defects. The complete reader regression now passes 138 cases, including the unchanged parent-derived v1/v2 output hashes and a label-isolation control; these tests run no energy calculation or measured-data training.

## Admitted public PFKFB3 development observation

The pinned OpenFF benchmark source `2020-07-06_pfkfb3/lig_38` exposes both
format cases: six terminal NME atoms use topology residue token `446A`, exactly
matching PDB sequence 446/insertion A, and the original SDF contains the inert
field `IC50[uM]`. The original v1 attempt failed at the residue token; the first
insertion-only v3 attempt then failed at the SD header. Both source failures and
a separate instrumentation error are retained. With final v3, the same source
file hashes, coordinate frame, atom order, charges and explicit evaluation
parameters pass the actual `tools.product.score_prepared_cross_interactions`
module. The request changes only its prepared-input version and expresses the
same one protein topology as an ordered molecule list.

The selected source is one of 40 metadata candidates. Source/chemical/citation
reservation checks keep all 40 in the original denominator, with one fixed-pose
calculation and 39 not selected for coordinate calculation. The source catalogue
has one connected study component; a random within-study split is not independent
validation. Existing source roles, reserved development/calibration links and
protected inputs remain unchanged.

The supplied protein has 6,749 atoms and the ligand 51. All 344,199 possible cross
pairs remain requested; 16,101 are within the declared 10 Angstrom cutoff, with
switch start 8 Angstrom, dielectric 1 and no screening. The unchanged V2 kernel
returns LJ -62.340932520975294, Coulomb 21.64863302961398 and total
-40.69229949136131 kcal/mol. These are cross potential terms, not IC50, affinity,
binding free energy or a learned residual. Internal energy, strain, solvation,
residual and affinity remain null.

A separately written scalar evaluator consumes the exact exported coordinates
and parameters. Under a tolerance fixed before evaluation (absolute 1e-8), its
maximum energy difference is 1.14e-13 kcal/mol and maximum difference across all
20,400 receptor/ligand force components is 2.46e-13 kcal/mol/Angstrom. All cutoff
pair indices match exactly, including all zero-force components. This is a
numerical comparison of the declared model; it does not establish force-field
accuracy, docking recovery or an external scientific approval.

The original experimental structure 6HVI/GV5 has 30 ligand heavy atoms and no
observed ligand hydrogens. Four complete chemical-graph atom mappings give a
minimum direct heavy-atom RMSD of 0.28736 Angstrom for the supplied prepared
ligand; no ligand-only fitting is used. A diagnostic rigid fit on 408 matched
protein CA atoms gives 0.29022 Angstrom. This compares the supplied preparation
with its source structure, not a newly generated docking pose. Preparation
includes protein truncation, added ACE/NME caps and computed H coordinates;
source crystal POP/F6P/FLC/DMS are absent and water counts differ. Supplied water
files are retained separately but are outside this cross-only calculation.
The separately published 2024 protein LJ lookup is not proven coeval with the
original preparation. No source atom was removed or moved to pass a check.

The instrumented CPU process took 15.910 seconds including startup/output; command
main wall/CPU were 13.712/13.706 seconds, peak RSS 793,228 KiB. These are one-process
observations, not p50/p95, cache/batch speedup, GPU measurements or a comparison
with the scalar evaluator's much narrower timing scope. Regressions on the final
reader, geometry, cross kernel and actual consumer modules total 370 passes,
zero failures/errors/skips. Earlier real source-format failures remain separate
from these synthetic passes and the final one-case numerical comparison.

The public curated records report 40 positive IC50 values in micromolar units,
all with raw `error=-1`; the pinned dataset README defines unreported errors as
null. Negative errors are therefore preserved and unusable as a measured
standard deviation. Assay relation, original paper compound/table correspondence
and experimental conditions remain unverified. The SDF property and curated row
are retained as source metadata, with no conversion into energy/force labels,
no new training, and no customer or calibrated-probability promotion.

Reproducibility identities: OpenFF commit
`fe6f96916b2e28f9c14398d77c838d6515e931b0`; final reader SHA256
`b8a4372d1b7d5b2064d1acecb270a09cc334722e74ddeff01fd338b1f1a25ec9`;
unchanged cross adapter SHA256
`12d2cd72e091e7e8682d7a721896246ff1eb1006bca8357e8cba76a2b3afdcc7`;
exported evaluated-result SHA256
`0d8f9b94473840a03455e0c7955613195cfc5763c01bae8d309b735aeef23fb2`.
The local evidence bundle retains source bytes/licenses, all commands and exit
codes, environment/module identities, raw logs, JUnit, all evaluated arrays and
the unchanged predeclared scalar comparison protocol. Checkpoint and score-unit
migration: none. Input v3 is an explicit opt-in; v1/v2 behavior is preserved.

Sources: [pinned OpenFF data and license](https://github.com/openforcefield/protein-ligand-benchmark/tree/fe6f96916b2e28f9c14398d77c838d6515e931b0),
[RCSB 6HVI](https://www.rcsb.org/structure/6HVI),
[original paper DOI](https://doi.org/10.1002/cmdc.201800569),
[separate protein parameter archive](https://zenodo.org/records/10495732).
