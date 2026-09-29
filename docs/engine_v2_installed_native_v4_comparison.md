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

The opt-in `installed_native_v4_fit_prepared_comparison_protocol_v2` has the
same top-level fields and accepts a non-null bound request only when that
candidate's rederived v4 metadata record contains `prepared_state_origin`.
The origin is a `{path, sha256}` reference to an exact
`native_v4_candidate_prepared_structural_binding_v1` descriptor. The installed
source verifier checks its bounded fields, then comparison freeze reparses the
prepared GROMACS sources and requires exact equality with a fresh observation.
The observation binds the source record and assay metadata origins, isomeric
chemical identity, SDF atom graph and formal charge, prepared ligand and
receptor system hashes, receptor construct, pocket and evaluation parameters,
prepared state and coordinate-frame declarations, and force-field/charge
source identifiers and file hashes. Unresolved stereochemistry and a ligand
identity mismatch reject the request before scoring. A changed source, origin,
request, or runtime also rejects resume and read-only verification.
The prepared reader now validates and discards inert SDF data-field contents
before forming provenance. The full SDF hash remains bound, but the canonical
ligand-system digest changes from the earlier producer; old prepared origins,
pose reports, and journals require a fresh binding and cannot be reused as
current receipts.

`preflight-v2` checks a proposed v2 protocol before creating a run. It
rederives the source, requires at least two distinct selector-supported Ki
development chemicals, an origin-bound prepared request for every candidate,
one exact method/receptor/pocket/evaluation/frame cohort, and an engine-call
cap covering the pool. It also uses the supplied ligand coordinates and rigid
transforms to require at least one pose inside the declared pocket for each
candidate. A candidate with only out-of-pocket poses receives a typed blocker
before a runnable protocol is written; mixed valid/out-of-pocket pose sets may
still be attempted. This geometry check performs no energy calculation and
does not establish clash freedom, pose recovery, or numeric validity.
A ready receipt can write the canonical runnable
protocol with `--output-protocol`; a blocked receipt lists candidate-specific
reasons and creates no protocol file. Readiness only means that a provided-pose
comparison can be attempted. The current public intake has one distinct Ki
development chemical and no prepared origins, so it remains blocked.

For strict V2000 SDF, single-bond stereo codes 1, 4, and 6 retain the **first
bond atom** as the directed wedge endpoint, as specified in the [BIOVIA CTfile
format](https://discover.3ds.com/sites/default/files/2020-08/biovia_ctfileformats_2020.pdf).
Canonical bond endpoints may be sorted, but SDF export and source-bound
conformer preparation must preserve and verify that original direction.
Missing or invalid direction metadata fails validation. A retained wedge is
only a declaration: coordinate stereochemistry is unverified and cannot make a
scientific or product claim ready. Nonstereo prepared v1/v2 identities remain
unchanged; a legacy directed-bond canonical record without its source endpoint
must be reparsed from authenticated SDF bytes.

`candidate_prepared_identity_bound` in v2 records this structural integrity
check. The source origin is a declaration bound into the rederived intake, not
independent evidence that its receptor construct or microstate was used in the
assay. `same_prepared_assay_state_verified`, `source_authenticated`,
`scientifically_validated`, and `product_ranking_enabled` remain false. The
current public v4 intake's three development candidates have no such source
origin, so their v2 requests remain null and their engine-call count remains
zero. A descriptor supplied only in the comparison protocol cannot create the
missing source link. The v1 protocol and null-only behavior are unchanged;
existing checkpoint verification remains bound to its original code/runtime.

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

An evaluated v2 pose report must also match its frozen candidate request when
`run`, `resume`, or `verify-run` summarizes it. The installed verifier reparses
the bound prepared files and reconstructs the requested rigid pose, then checks
the saved pose identity, coordinates, receptor and ligand source systems,
parameters, model, pocket, and declarations. This is a parent-side integrity
check outside the equal worker budgets, included in the original run's summary
wall time. It does not authenticate the assay state or assess physical validity.

The versioned `native-v4-fit-replay-v1` wheel extra supports Python 3.10,
`rdkit-pypi==2022.9.5` (RDKit runtime `2022.09.5`), `scipy==1.12.0`,
`scikit-learn==1.7.2`, and `torch==2.6.0`. The wheel's base requirements pin
NumPy to `1.26.4`. The smaller `native-v4-source-replay-v1` extra installs
RDKit for source verification only. The general `research` and
`assay-development` extras pin RDKit 2026.3.6 and are incompatible with this
replay profile. Both native v4 console commands check Python and the installed
RDKit distribution and runtime versions before importing or opening the bound
source. A direct Python module call is outside this installed CLI profile.

For a fresh installed replay, build the product wheel with a dedicated Python
3.10 build environment, then install its fit extra into a different fresh venv.
The CPU PyTorch wheel satisfies the extra's `torch==2.6.0` requirement without
bringing in the PyPI CUDA packages. Use an absolute private directory for
`AUDIT`, and run the build command from the repository root:

```bash
python3.10 -m venv "$AUDIT/build-venv"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/build-venv/bin/python" -m pip install \
  pip==25.2 setuptools==75.8.2 wheel==0.45.1 build==1.3.0
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/build-venv/bin/python" -m build \
  --wheel --no-isolation --outdir "$AUDIT/wheels"
python3.10 -m venv "$AUDIT/replay-venv"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/python" -m pip install pip==25.2
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/python" -m pip install \
  --index-url https://download.pytorch.org/whl/cpu 'torch==2.6.0+cpu'
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/python" -m pip install \
  "$AUDIT/wheels/betelgeuze_md_product-0.1.0-py3-none-any.whl[native-v4-fit-replay-v1]"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/python" -m pip check
```

Confirm `include-system-site-packages = false` in `pyvenv.cfg`, and use
`python -I` to inspect that `rdkit`, `torch`, and `betelgeuze_product` resolve
under the new venv. With a bound `source-reference.json` and the prespecified
`protocol.json`, run the installed commands with no `PYTHONPATH` or user site:

```bash
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/betelgeuze-native-v4-source" \
  verify-source source-reference.json > "$AUDIT/source-verification.json"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/betelgeuze-native-v4-comparison" \
  preflight-v2 --protocol v2-draft.json --output-protocol protocol.json \
  > "$AUDIT/protocol-preflight.json"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/betelgeuze-native-v4-comparison" \
  run --protocol protocol.json --run-dir "$AUDIT/comparison"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/betelgeuze-native-v4-comparison" \
  verify-run --protocol protocol.json --run-dir "$AUDIT/comparison"
env -u PYTHONPATH -u PYTHONUSERBASE "$AUDIT/replay-venv/bin/betelgeuze-native-v4-comparison" \
  resume --protocol protocol.json --run-dir "$AUDIT/comparison"
```

The 2026-09-28 local replay used the integrated source commit `58ecae6ae`
plus this profile change and the bound public summary SHA-256
`6c9e8ae2e18e5591fea41c3c1bce533131c7b6f514c2185bd92eab719611ffa4`.
The validated product wheel SHA-256 was
`6a5d00eda2f0a8a4e65f0a23d4f2a5073ae7cc2b5f15a4770b398c236167038f`.
The private audit directory
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-clean-native-v4-replay-20260928`
contains the full resolver freeze, hashes of the five direct numeric/runtime
wheels, source receipt, journal, and CLI results. The fresh venv had no system
site packages, user site, or inherited `PYTHONPATH`; `pip check` passed.

The installed source rederived 258 rows: 255 preassigned fit, zero calibration,
and three development candidates; 196 fit observations were point eligible.
The four-arm run committed, read zero evaluation labels, and made zero engine
calls. One candidate had a supported selector prediction, and the other two
remained unsupported. The three selector arms' predictions and order matched
the earlier installed receipt exactly. `verify-run` returned `verified`, and
completed-run `resume` returned `committed`. The fresh CPU torch wheel transfer
was 178.6 MB; the installed venv occupied 1.5 GB on this host. These are
installation observations, not run or scientific performance measurements.

Independent evidence connecting the prepared receptor construct and ligand
microstate to the assay, independent calibration and evaluation roles, and
evaluation outcomes remain prerequisites for testing a scientific ranking
claim.

## PR #566 exact package-code replay (2026-09-28)

A later isolated Python 3.10 replay used package-code commit
`3ad331560c29a3e158aa28de95f3d871e11be119` and a newly built wheel with
SHA-256 `33494fafeeea725aa4031d0f3164462157d20e505f0f87fd4af68112ab71d47d`.
The subsequent `1da3014dfab316cf83688e57a18b13f5e2095778` commit adds only
a development-only research decision document and verifier; compared with the
replayed commit, package source bytes are unchanged. The sealed local receipt at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr566-stereo-readiness-20260928/final-receipt.json`
records the environment, hashes, source verification, installed SDF wedge check,
and run/verify/resume results. It is local software evidence, not a CI result.

The installed source verifier rederived 258 metadata rows: 255 fit and three
development records, with 196 point-eligible fit observations and zero
evaluation labels read. Public v1 and v2 run/verify/resume completed with zero
engine calls. A separately source-linked **synthetic** v2 candidate made one
engine call in each engine-bearing arm, then verified and resumed. An unlinked
real candidate failed before a run directory was created. The read-only
[comparison readiness diagnostic](native_v4_comparison_readiness.md) found
three requested records but one distinct Ki chemical identity, zero prepared
or method-consistent records, and zero four-arm common scored records. No
actual-target ranking comparison, assay-state verification, or scientific
qualification follows from this replay.
