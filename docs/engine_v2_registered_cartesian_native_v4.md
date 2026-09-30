# Source-bound Cartesian registered comparison v4

The opt-in `installed_native_v4_registered_cartesian_comparison_protocol_v4`
executes one supplied registered pose per candidate through the durable CPU
Cartesian 1.3 workflow. It requires the existing eight v3 protocol fields plus
an explicit `cartesian_solver` document from
`cpu_refinement_v1_3.contracts.SolverConfig.to_dict()`. Its frozen/result/CLI,
verification and preflight schemas have separate v4 identities. The original
v3 protocol continues to execute its original 1.2 registered policy adapter.

Both `preflight-v4` and direct execution first run the unchanged v3 candidate
admission: original source roles, human 5-HT6 Ki method, complete candidate
denominator, two distinct chemical identities, XML decimal-charge sources,
actual-coordinate stereochemistry, initial overlap/pocket checks and one common
receptor/pocket/parameter/settings cohort. Every source descriptor stays bound
to its original `cpu_registered_pose_fixed_receptor_request/1.0.0` request.
Only after these checks does `prepare_cartesian_request` explicitly convert the
request; the new workflow's `input_binding` binds the converted execution.
Frozen receipts retain `original_requests` and `original_source_inputs` beside
the converted `requests` and `source_inputs`. There is no reinterpretation or
resealing of the old source descriptor to claim Cartesian source admission.

```python
from betelgeuze_product import installed_native_v4_cartesian_comparison as v4
from betelgeuze_product.cpu_refinement_v1_3.contracts import SolverConfig

protocol["schema_version"] = v4.PROTOCOL
protocol["cartesian_solver"] = SolverConfig().to_dict()
```

```bash
betelgeuze-native-v4-comparison preflight-v4 --protocol draft.json --output-protocol protocol.json
betelgeuze-native-v4-comparison run --protocol protocol.json --run-dir comparison
betelgeuze-native-v4-comparison verify-run --protocol protocol.json --run-dir comparison
betelgeuze-native-v4-comparison resume --protocol protocol.json --run-dir comparison
```

These commands retain the existing Python 3.10 / RDKit 2022.09.5 native replay
gate. The Cartesian workflow enforces its own request restrictions, including
the raw force tolerance, ligand strain cap, unperturbed registered pose and
convergence-required refinement selection. An admissible original baseline can
remain selected when refinement is unconverged. Similarity-only output remains
the synthetic/source FIT selector's negative-log molar endpoint prediction;
the molecular arms retain
`uncalibrated_explicit_graph_scorer_dimensionless_minimize`. Internal/cross
energy changes and this dimensionless score remain separate observations.

Each molecular candidate reserves an outer call before execution and retains
its own `<candidate-hash>.cartesian` directory. The solver separates optimizer
objective/graph/force calls, restart verification/graph/force calls, failed calls,
known completed calls and unresolved pending attempts. Score reservations and
committed baseline/refined score receipts are distinct. Candidate summaries
retain numerical timing scopes, score-evaluation work and invocation setup/work;
their inclusive/nested durations must not be added to enclosing arm wall time.

The outer arm has one immutable deadline and one worker lease. `resume` forfeits
an interrupted arm's remaining budget and replays its saved evidence; it cannot
start a replacement candidate or reset that candidate's solver budget. This
outer comparison does not automatically continue an interrupted minimizer.
Unreturned candidates appear in `cartesian_partial_work`. Known journal prefixes
and committed score calls are preserved while pending numerical/score work
remains unknown. If worker completion is missing, the total missing-report call
denominator remains null and known candidate reservations are a separate lower
bound. All requested candidates remain in every arm's status denominator.

Completed verification and comparison resume start no worker and execute no
optimizer, force evaluator or scorer. Input parsing, live geometry/term replay,
scorer construction and its reference arithmetic still consume verification
time. Neither operation writes new invocation receipts to completed candidates.

The 1.2 and 1.3 package source files are unchanged byte for byte. Their solver
checkpoint source closures remain intact. Native comparison receipts also bind
the full installed package runtime. Adding this opt-in bridge changes that
package identity: an older v3 comparison receipt must be verified with its
original wheel/runtime; a new wheel does not silently accept or reseal it.

The local synthetic receipt is
[native_v4_cartesian_comparison_synthetic_v4.json](evidence/native_v4_cartesian_comparison_synthetic_v4.json).
Two synthetic candidates across four arms produced six force calls and twelve
score calls; the fixture began at declared bond/angle equilibrium and required
no accepted refinement step. Completed reuse performed zero new molecular or
worker calls. The wheel ran outside the checkout with shared installed
dependencies (`fresh_dependency_environment=false`). This is a software receipt
and orchestration check. It does not establish real-source admission, physical
accuracy, useful refinement, affinity/ranking benefit or scientific/product
qualification. Acquisition, real preparation, real-label training and real-case
comparison costs are not measured by this probe. Synthetic selector fit and
inference are included in arm wall/setup time, without a separate training
timing claim. The CI extension requests a fresh dependency environment, but no
hosted CI result is claimed by the local receipt.

A subsequent [local fresh-install receipt](evidence/native_v4_cartesian_fresh_install_v1.json)
uses the same immutable wheel in a new Python 3.10 virtual environment with
`include-system-site-packages = false`, CPU PyTorch 2.6.0+cpu and the declared
`native-v4-fit-replay-v1` extra. `pip check` and the installed-package probe
passed. The two-candidate/four-arm run made six force and twelve score calls;
completed verify/resume made zero new worker, force or score calls. The call-cap
and swapped-candidate preflights were rejected. Its 260 probe files, complete
package list, wheel hash and execution receipt are retained. After verification,
the disposable 1.5 GB virtual environment was removed to reclaim space; the
installed-package path in its original probe is historical, not a currently
present environment. This establishes a local clean installation and synthetic
execution on one host, not a hosted CI pass or service qualification.

The immutable wheel, synthetic input/result files and run journals are preserved
under the receipt's `archive_root` with an `archive-manifest.json` of file sizes
and hashes. The original bound requests contain absolute `/tmp` paths. Exact
checkpoint replay therefore requires restoring those archived inputs to their
original paths and using the same wheel/dependency/runtime profile; relocating
and resealing them would create a new experiment. The source checkout HEAD is
context for the uncommitted implementation, while byte comparisons bind the
executed wheel to those tested source files.
