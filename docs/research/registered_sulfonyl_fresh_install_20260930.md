# Sulfonyl input compatibility and fresh installed replay

The registered binding previously rejected ordinary sulfonyl-containing PR49
because the pinned RDKit profile reports its sulfur as an unspecified potential
square-planar center. The binding now recognizes only the neutral, untagged
S(VI) graph with two equivalent terminal oxo atoms and two single bonds. Both
source identity and actual coordinates use the same policy. Original identity,
the raw count of one, charge, isotopes, explicit hydrogen completeness and graph
hashes are retained. True unspecified tetrahedral/E/Z stereo, isotope-distinct
oxo atoms, sulfoxides, metals and specified/unknown unsupported non-tetrahedral
stereo remain rejected. No global RDKit switch or frozen identity helper changed.

The final source passes 120 affected binding, comparison and adapter tests;
the binding subset has 84 tests. These counts overlap and must not be added.
Ruff passes on the two changed files. An independent review found no blocking
code issue and checked 23 standalone RDKit positive/negative cases. This fixes
an input rejection; it does not grant experimental-source or training admission.

## Fresh installation and public CLI

A new Python 3.10 environment has `include-system-site-packages = false` and no
shared dependency `.pth`. Five previously verified large wheels (274,345,386
bytes) were reused; 40 missing runtime/bootstrap wheels (84,567,844 bytes) were
acquired. All 44 runtime distributions have fixed versions and installation
ownership under the new environment. The older shared-environment replay is
retained as historical evidence.

The new wheel SHA-256 is
`5467efdb3b237f75a29c756733c9c225fcc4a8a5e487bf32fade6e92541da379`.
All 514 package Python sources and 516 owned package files match source, wheel
and installation. It was installed offline with the full dependency resolver,
44-version constraints and the `native-v4-fit-replay-v1` extra. `pip check`
passes; an independent ownership review confirms that no runtime version or
representative dependency entry file changed during product installation.

Outside the checkout, the public registered-comparison CLI passes its synthetic
two-candidate, four-arm preflight/run/verify/resume probe. It records six initial
force calls, twelve score calls and zero optimization steps because both
synthetic molecules begin at model equilibrium. Completed reuse preserves the
result bytes and starts zero new worker, force or score calls. Insufficient
budget and swapped candidate requests are rejected through both preflight and
direct execution. The CLI probe itself takes 17.788345 seconds; enclosing build,
regression, install and probe stages take 47.141975 seconds. These are separate
scopes, not a service benchmark.

The probe has no sulfur and therefore cannot alone validate the sulfonyl fix.
A separate outside-checkout identity diagnostic using the fresh installed helper
passes 11/11 cases with zero score/force calls: original declared +1 SRO passes,
its neutral counterfactual rejects, unchanged PR49 still rejects missing aromatic
annotations, and the source-mapped PR49 derivative passes with the original
identity/count intact. Seven additional synthetic cases verify ordinary sulfonyl
acceptance and actual planar geometry, count, specified stereo, unassigned
tetrahedral and isotope rejection. Actual graph/coordinate hashes, import paths,
before/after source pins and unchanged RDKit flags are recorded. These are graph
identity checks, not full experimental-source admission or physical validation.

The original build receipt incorrectly predeclared a concurrent SRO run.
`execution-context-correction.json` preserves and corrects that flag using the
actual timestamps: SRO ended at 18:24:17 UTC; product validation began at
18:25:59 UTC. The earlier dependency bootstrap did overlap SRO. No runtime
speedup claim is made from either observation.

Fresh installed synthetic comparison/reuse is now demonstrated. Mid-minimizer
restart, independent real candidate admission, scientific ranking, HIP parity,
and complete preparation-through-delivery service validation remain incomplete.

[Evidence index](../evidence/registered_sulfonyl_fresh_install_v1.json)
