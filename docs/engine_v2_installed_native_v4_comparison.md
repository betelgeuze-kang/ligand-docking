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

Actual receptor/ligand preparation, a provenance-checked candidate-to-pose
link, independent calibration and evaluation roles, and evaluation outcomes
remain prerequisites for testing a scientific ranking claim.
