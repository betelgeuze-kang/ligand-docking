# Finite paired PFK eight-DOF research

This tool compares one prepared PFKFB3 ligand under the recovered dry model
and that same model plus ligand–water interactions. P0, Qplus and Qminus are
three prescribed starts of the **same molecule**. They do not constitute an
independent test cohort, blind docking, or affinity validation.

The original repository and recovered archives are read-only. The plan binds
all 2,113 recovered dry/held-out files, all 2,250 recovered water files, the new
implementation commit and bytes, runtime versions, reference policy, and every
phase's limits. The builder refuses uncommitted implementation files. An old
approval or completed run is never used to authorize or resume this campaign.

The eight coordinates and optimizer are the unchanged recovered three
translations, three fixed-axis rotations and two bridge torsions. The model
retains the original full ligand/internal and protein–ligand calculation plus
the recovered conservative cross correction and untruncated internal Coulomb
correction. The wet arm adds the original pair kernel for a mobile ligand and
the exact 362-water checkpoint. Water oxygens and orientations are fixed during
ligand optimization. Fixed protein–water and water–water terms are constants;
they are omitted from the ligand objective and reported at terminal water
evaluation. Absolute dry/wet energies are different Hamiltonians and are not
used to select a winner.

Each dry and wet diagnostic uses 17 independently counted evaluations: the
center and both displacements of each of eight coordinates. The step is 1e-5;
each component must satisfy absolute error <= 1e-4 + 1e-4 * abs(analytic).
Both diagnostics and their root/independent reviews must pass before any
optimizer phase. Reference coordinates never enter objectives or selection.

Each of six fresh arms has at most 641 objectives and 600 accepted steps. The
ligand allowed-force threshold is 0.001 kcal/mol/angstrom. Raw and reaction
forces are reported separately. Each arm has a 2,400-second total wall/CPU
ceiling: new optimizer dispatches stop at 2,100 seconds and the final water
diagnostic has at most 300 seconds within the remaining total. In-flight work
is subject to the total limit. This is a different timing scope from the old
2,400-second optimizer-only budget. Every arm uses the same fixed CPU, one
intra-op/inter-op thread, 4 GiB address-space limit, 64 MiB per-file limit and
200 MiB sampled output-tree limit. Each diagnostic has 300 seconds.

The original byte-identical watchdog owns process-group supervision and
cleanup. Its historical route-metadata hooks are adapted to the new ledger and
the separately reviewed finite-difference gate; physics checks are unchanged.
Worker parent-death protection and kernel process limits complement sampled
group wall/CPU/RSS/tree checks. An explicit start is durable before every
physical call. A failed or unknown stage poisons the process, and attempted
phases are never automatically retried. A visible row cannot erase an observed
fsync failure. A successful process exit alone does not admit a phase: independent
journal pairing, physical stage census, terminal coverage, source verification,
and cleanup must also pass.

One water-global evaluation is budgeted for each retained ligand endpoint.
It uses that endpoint and the exact fixed 362-water state. Water torque is
compared with 0.001 kcal/mol/radian. Dry-arm torque is explicitly counterfactual
wet stress; it does not establish wet-objective stationarity. Restricted ligand
stationarity, raw ligand stationarity, and fixed-oxygen water rotational
stationarity remain separate. No water translation or hydration equilibrium
is claimed. No fresh baseline or replay force call is hidden in reporting.

The old crystal-reference assets were absent from the recovered packages.
The new metric uses newly fetched official 6HVI/GV5 bytes and a source-only
graph admission. The policy is frozen before fitting: proper unweighted
Kabsch on all 415 matched receptor C-alpha atoms, no reflections or outlier
removal, source-occupancy alternate selection with lexical ties, no ligand fit,
and all four admitted heavy-atom graph mappings. All four RMSDs are retained.
P0 no-harm (1e-6 angstrom margin) and Q improvement relative to its own start are
new comparative diagnostics, not replacements for historical qualification
gates. Ring planarity, force-field geometry changes and complete-denominator
contact distributions are diagnostic measurements. Chemical validity remains
unqualified/null.

The command interface is `plan`, `diagnostics`, `optimize`, `status`, and
`report` in `tools/run_pfk_paired_water_eight_dof.py`. A frozen plan's exact byte
SHA256 must be supplied independently on each invocation. `worker` is an
internal isolated subprocess entry point and refuses an unowned parent.
Reports include all six declared arms, including failures and not-run arms.
Objective, kernel, backward, graph, screen and geometry counters have separate
scopes; nested counters are never converted into a single equivalent EF cost.
Unknown totals remain null, and historical unknown costs remain historical.

Fresh128 and Stage0 are outside this experiment. The tool does not modify their
inputs, labels, denominators, thresholds, or execution state. This experiment
does not close the fixed D1 comparator study, lifecycle API, or external CPU
user pilot priorities.
