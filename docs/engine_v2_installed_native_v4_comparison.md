# Installed receptor v4 fit comparison boundary

`betelgeuze-native-v4-source verify-source` rederives the bound ChEMBL receptor
Ki v4 intake from raw metadata, role declarations, the complete identity graph,
measurement captures, and supported primary correspondence records. Its receipt
reports source integrity; it does not authenticate the original experiment or
establish a physical target and ligand state.

`betelgeuze-native-v4-comparison` accepts a distinct
`installed_native_v4_fit_comparison_protocol_v1` document. Its `source` is the
exact `installed_native_v4_fit_source_reference_v1` object. The other fields are
`requests`, `budget_seconds_per_arm`, `max_engine_calls_per_arm`, `arm_order`,
`selection_seed`, and `tie_policy`, as in the installed four-arm protocol. The
candidate keys in `requests` must exactly equal the preassigned
`development_test` record IDs. This version requires every request value to be
`null`: a ChEMBL record ID or canonical SMILES alone does not bind a prepared
pose to the assayed ligand state, target structure, or assay conditions.

The source is reverified before run, resume, and read-only verification. Only
eligible `fit` exact-point Ki observations enter selector fitting. The native
Ridge arm uses the v4 trainer's fixed Morgan features, alpha 10, and inverse
replicate count per connected source component and canonical structure. The
similarity arms retain the four-arm comparator's nearest-neighbor rule. The
fit source never supplies evaluation outcomes. `comparison.json` retains
separate predicted endpoint and physical cross-energy quantities, actual engine
call counts, missing-input denominators, and false scientific/product authority
flags. A completed journal with zero engine calls establishes workflow integrity
and selector computation only.

The current bound v4 intake was reproduced with RDKit 2022.09.5; a different
RDKit canonicalization can fail the source/cache comparison. The installed
wheel test used an isolated interpreter with an explicit path to an already
installed 2022.09.5 dependency. This is an environment constraint, not a
general dependency installation or an independent source authentication.

To exercise the command after installing a compatible wheel, provide the
protocol and a new private output directory:

```bash
betelgeuze-native-v4-comparison run --protocol protocol.json --run-dir run
betelgeuze-native-v4-comparison verify-run --protocol protocol.json --run-dir run
betelgeuze-native-v4-comparison resume --protocol protocol.json --run-dir run
```

Actual receptor/ligand preparation, a provenance-checked candidate-to-pose
link, independent calibration and evaluation roles, and evaluation outcomes
remain prerequisites for testing a scientific ranking claim.
