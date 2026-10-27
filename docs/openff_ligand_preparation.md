# Opt-in research-only ligand preparation

`benchmarks.oracles.ligand_preparation.openff_sage.prepare_sage_ligand(input_sdf, output_directory, *, forcefield_path)` is an explicitly invoked Python function. It is **not** registered in the default CLI and does not install anything. Importing the module requires only the standard library. Calling it imports native chemistry libraries and executes AmberTools subprocesses; a caller must independently authorize and enforce resource/process/filesystem limits. There is no boolean that grants runtime qualification.

The initial supported route is one explicit-hydrogen SDF molecule with one finite coordinate set and fully defined stereochemistry. Input state/order/coordinates are preserved. No implicit H addition, protonation or tautomer repair, undefined-stereo acceptance, fallback charges, or receptor preparation is supported. This first release does not promise general input coverage; strict rejection is preferable to silent chemical changes.

The backend is pinned to OpenMM8.4.0, OpenFF toolkit0.19.0, Interchange0.5.5, RDKit2026.3.1, and AmberTools26.0 in the current prefix. The supplied Sage2.2.1 file must match SHA256 `1b24deb47970bae2d179a5b4e023d4a57c9c78614fe431f1670e3f75e0012c3a`. AmberTools conda metadata must be present and selected antechamber/sqm executables must resolve inside that prefix. These checks record backend identity, not supply-chain or runtime isolation guarantees.

Each call computes fresh AM1-BCC charges using the supplied conformer, without normalization or cached charges. The accepted charge-sum tolerance is 1e−4 e relative to input formal charge. Unsupported chemistry or native failures propagate; partial evidence may remain in the exclusively created output directory. The final parameterization-result.json is written only after all checks pass.

Artifacts include original input SDF; chemical identity/coordinates; charge vector; original and unconstrained Sage XML; original and derived OpenMM Systems; every ordered torsion with source SMIRKS, multiplicity/idivf and proper/improper assignment; hashes, counts and derivation metadata. The model is nonperiodic NoCutoff, unconstrained, no GB. Constraints-handler removal is explicit. The static derived System removes only CMMotionRemover and disables the inactive NoCutoff switching flag; XML structure is checked against exactly this allowlist. No dynamics equivalence claim is made. Energy/force equality must be established independently before use of a new backend version.

The existing 6YQW_82I research-script artifact and its numerical validation are separate evidence from this refactored module. Refactor unit tests are policy/XML checks, not native chemistry validation. The earlier bounded rerun bound the previous frozen module below to this one fixture. The architecture relocation requires a separately recorded rerun of the new public entrypoints; it is not automatically covered by the prior module hash. No docking accuracy, receptor completeness, or new-input success-rate claim follows from ligand parameterization.

Input isotope labels are currently rejected explicitly. Original atom-map numbers are retained as companion provenance; System particle identity is the preserved atom index. Raw atom/bond/aromatic/stereo observations are retained; model aromaticity is compared after the declared MDL representation step, with separate raw-to-normalized chemistry/stereo invariance checks. Success JSON is published by same-directory temporary-write/rename only after all checks pass; consumers must still parse and validate the schema and referenced hashes.

Aromaticity is a declared representation policy: RDKit-default input flags are retained in the companion, while the expected parameterization representation uses the pinned OpenFF backend's MDL aromaticity convention. Differences in those flags are recorded, not presented as unchanged flags or protonation/tautomer changes. Atom identity, formal charge, stereochemistry, explicit hydrogen count, bond correspondence and coordinates must still agree. Disconnected graphs are rejected.

## Prior-layout delivered-code evidence (not relocated-entrypoint validation)

The independently reviewed module SHA256 `534231fe6e13df775333f9bdf54f6a509d1c0dec29a8553994319ee4cc957c06` completed one bounded public 6YQW_82I SDF preparation with fresh AM1-BCC in 3.455 s. It reproduced the original research run's System XML, charges and torsion-assignment hashes exactly. Twelve pure policy tests and independent representation-only mutation checks pass. A prior strict failure on mismatched aromaticity conventions is retained; the fix explicitly records and tests MDL representation handling, not chemical-state repair. This single-case result is not broad chemistry support or docking accuracy evidence. The public input is `6YQW_82I_ligand_start_conf.sdf` from the [PoseBusters paper data, Zenodo record 8278563](https://zenodo.org/records/8278563), SHA256 `43ff3d67c41ed93fc69e3734ec0061fbb79c7d570b7340e8041dc83268559624`. It contains 19 atoms (11 heavy, 8 H); crystal reference coordinates were not used. The API produced 19 bonds, 31 angles, 73 periodic torsion entries (55 proper, 18 improper) and 83 nonbonded exceptions without changing input coordinates.

The independently executed delivered-API capture/oracle comparison passed **120 direct checks**, including all **57 force components** at one coordinate set. It used one own-engine energy/force evaluation; no finite-difference rerun was included in this final API check. Maximum energy-component/total residual was `2.141575805580942e-11 kcal/mol`; maximum direct force residual was `3.375077994860476e-12 kcal/mol/Å`. Original versus derived OpenMM energy and all 57 force components had exactly zero measured difference. The input artifacts and checked repository source files remained unchanged. Independent reviewer recomputation of this final report is tracked separately.

These are ligand-only implementation/translation checks for one fixed model and one public case—not docking runs, pose-recovery results, a benchmark success rate, dynamics equivalence or generalization evidence. The incomplete 6YQW receptor was not prepared or used. Earlier research-script checks and this delivered-API rerun must not be counted as independent molecular cases. Generated result JSON and native environment binaries are not required publication artifacts.

## Research/product boundary

The native preparation module now lives exclusively at
`benchmarks/oracles/ligand_preparation/openff_sage.py`. Native capture lives at
`benchmarks/oracles/ligand_preparation/openmm_capture.py`; its public function is
`capture_openmm_ligand`. Both are opt-in research helpers, not default product
CLI integrations or provenance-bearing oracle adapters. They require a separately
authorized bounded caller and do not supply the oracle pack's pinned-child
containment. The existing oracle runner's qualification must not be inferred.

Product `betelgeuze_product.openmm_fourier_export.export_ligand` accepts only the
neutral snapshot data artifact, imports only the standard library, and neither
imports nor calls these research helpers. There is no compatibility shim at the
old product preparation path and no native capture export in the product module.
Model, chemical-state, and source-term checks are unchanged by relocation.


## Relocated-entrypoint validation (2026-10-27)

The actual research-package preparation and capture entry points, followed by the
stdlib-only product conversion, were rerun successfully using genuine pinned-main
parent packages. On the same one public 19-atom ligand, 120 direct comparison
channels passed: maximum energy residual 2.141575805580942e-11 kcal/mol and force
residual 3.375077994860476e-12 kcal/(mol angstrom). Original/derived E/F deltas
were zero; one own E/F call, six source queries and two capture/control queries
were used, without new finite-difference evaluations. Independent recomputation
confirmed these comparisons. This is not 120 independent molecules.

An initial preparation returned valid artifacts but its harness subsequently
failed while recording imports; that failed attempt is retained. A harness-only
recorder correction and clean retry completed successfully: two fresh AM1-BCC
preparations on the same molecule, not broader chemical coverage. Source code,
chemistry invariants and tolerances were unchanged. The original PR architecture
check failure is also retained; this relocation fixes placement rather than
weakening the unchanged guard. Local architecture checks are sparse, not full-repo
proof; exact-head hosted CI supplies the full-repository check. Research helpers
are not production-native integration or qualified contained-oracle execution.
No receptor, docking, optimization, accuracy or commercial claim is added.
