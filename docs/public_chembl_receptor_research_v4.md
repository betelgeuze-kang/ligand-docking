# Receptor Ki research intake and fit

The explicit `native_chembl_receptor_research_v4` route feeds measured ChEMBL
human receptor radioligand-binding Ki into the existing Morgan/Ridge trainer.
It remains a ligand-only cheap selector. It supplies neither coordinate forces
nor an energy residual, calibrated uncertainty, docking refinement, or customer
execution. Existing product checkpoint consumers do not yet accept this schema.

The new intake resolves hash-bound metadata, original role assignments, whole
identity context, native activity captures, method descriptions and document
records. Before decoding an activity value it checks its preassigned fit role
against the complete graph. Every requested row remains in the ledger, including
withheld evaluation values, unsupported endpoints, ambiguous source examples,
duplicate flags, and method exclusions. A source metadata hash is not labelled
as the prospective split: the split digest binds the original role-file paths
and hashes, also retained in the training protocol.

Source 37 patent records require an explicit research profile. The default
literature-only source policy stays in effect for older versions. The two
supported primary table readers are US9067949B2 and US8569318B2. Intake reopens
bound HTML and native compound records, checks the original example aliases,
and recomputes numeric correspondence. Multiple aliases are not paired by
numeric value or row order. For the latter table an internally inconsistent
Ki/IC50 pair under its declared Cheng-Prusoff relation remains excluded.
Source 1 research articles require matching PMID article-type metadata; a bare
PUBLICATION type is insufficient. Nested evaluation policies remain restrictive
under both old and new admission profiles.

Database-curated nM is used only with the explicit development scope. The first
patent's printed `nm` disagreement and unverified assayed microstate are retained.
This is not literal primary-unit verification. Numeric-only source 37 comments
are retained as opaque annotations only when name/value correspondence is
verified; they are not interpreted as IDs, activity labels or physical evidence.
Text comments and duplicate flags still require resolution. Source attribution
and the declared ChEMBL CC-BY-SA-3.0 database licence remain in the intake;
no commercial legal determination is made.

The existing fit uses Morgan 1024-bit radius-2 chirality fingerprints and
Ridge alpha 10, Cholesky, without parameter search. V4 repeated observations
receive inverse count per connected source component and canonical isomeric
structure. The minimum five eligible observations and two fit components are
unchanged. Fitting freezes all metadata-candidate predictions before evaluation
values, retaining abstentions for unsupported chemistry, targets and endpoints.
This adapter currently rejects evaluation mode; no fit statistic constitutes
independent predictive validation.

## Migration and verification

V4 uses `public_chembl_receptor_development_v4` intake and
`public_chembl_cheap_selector_ridge_v4` checkpoints. Old serialized checkpoints
and their original source runtimes must remain together: strict implementation
hashes intentionally reject replay with modified source. No automatic migration,
weight rewrite, old-schema reinterpretation or product registration occurs.

Synthetic tests exercise malformed pointers, measured zero preservation, nested
source roles, source-profile boundaries, primary revalidation, cache tampering,
assay-method mismatch, an actual trainer/serialization round trip, and evaluation
value rejection before access. Existing source/measurement/trainer regressions
remain in the same CI job. These checks are engineering evidence, not an
independent scientist's review or a public benchmark qualification.

The local measured run, commands, source hashes, costs, JUnit and limitations
are recorded separately from repository tests in its immutable evidence bundle.
Its fit data are heavily source- and class-imbalanced; no generalization or
end-to-end speedup claim follows from completing the fit.
