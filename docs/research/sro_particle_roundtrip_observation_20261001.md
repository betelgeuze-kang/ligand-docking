# Saved-state particle-unit-roundtrip observation, 2026-10-01

The specified particle-parameter roundtrip does **not change the total force
residual** at either stored case02 development state. The two OpenMM arms have
bit-identical total energies and all 78 ligand total force components. Initial
force error remains `4.761386662721634e-8`, above the unchanged `1e-8` gate;
last accepted error remains `2.035172030900867e-11` and passes that gate.
This narrows the tested hypothesis without establishing the remaining cause.

| Stored state | Particle arm | Max force-component error (kcal/mol/Å) | Atom / axis (zero based) | Original gate |
| --- | --- | ---: | --- | --- |
| initial | source XML | 4.761386662721634e-08 | 19 / z | fail |
| initial | native-unit roundtrip | 4.761386662721634e-08 | 19 / z | fail |
| last_accepted | source XML | 2.035172030900867e-11 | 6 / z | pass |
| last_accepted | native-unit roundtrip | 2.035172030900867e-11 | 6 / z | pass |

## Intervention and observations

Two saved states were evaluated once with two arms. Both use the frozen
OpenMM builder and Reference platform. Only CustomNonbondedForce particle
q/sigma/epsilon is replaced in the roundtrip arm. Source exceptions, bonded
terms, constraints, cutoff, expressions, force groups and particle order stay
identical, as verified by serialized system hashes with only those particle
fields neutralized. This is a new diagnostic, not a terminal campaign resume.

The inventory contains 26 ligand and 4,376 receptor particles. Every source
field converted into native units exactly matches its supplied native binary64
value. The return conversion changes seven sigma fields by one ULP: ligand
indices 16, 17, 23, 24, 25 and receptor indices 2232, 2290. Charges and epsilon
do not change. Cross total, cross LJ and cross Coulomb force/energy observations
are identical between arms. Initial internal force differs by at most
`6.7914424084492e-16`; that difference disappears in the assembled total.
Last accepted internal force is also identical. The total residual identity
closes with zero floating subtraction residual at both states.

The original arm's scalar energy/force errors exactly reproduce the prior
stored oracle record. Its current full vectors are new observations: the prior
oracle did not save those vectors. Native per-term forces are still absent;
new term arm differences cannot be labeled native term residuals. This result
does not rule out coordinate conversion, arithmetic ordering or every possible
unit-conversion mechanism. It gives no basis to rewrite the failed initial gate.

## Execution, validation and cost

All 4 context creations, 8 setPositions and 16 getState calls completed, with
zero error, unknown or undispatched calls. New native force, score and optimizer
calls are zero, and intrareceptor energy is not evaluated. Actual Python,
OpenMM, NumPy, platform, module hashes and the loaded dependency manifest match
the prior record. Python is isolated (`-I -B`), OpenMM is
`8.4.0.dev-4768436`, NumPy `1.26.4`, platform `Reference`.

The complete execute CLI took 2.740372640 seconds. The separately
measured metadata prepare CLI took 0.049795381 seconds. Within
execute, the receipt's entry scope took 2.442677104
seconds and its nested numerical scope 1.490429829
seconds. The entry scope starts after plan validation and ledger reservation;
it excludes final receipt serialization. These nested durations must not be
added. This protocol is not a speed or end-to-end service comparison.

The implementation's final 22 mock checks and isolated Ruff pass. Root's exact
CI-command validation also passes the 22 mock checks plus 14 repository workflow
trust checks. The earlier isolated pytest import failure retains its raw log.
The initial three E731 lint findings survive as a tool-output observation
only; their original raw file is unavailable. Checks were not weakened. The new
CI registers lint/mock checks without actual input reads or external artifact
upload. Local checks do not prove hosted CI completion or physics qualification.

An independent read-only review recomputed 312 native-minus-arm force
components, 36 vector summaries and 13,206 particle binary64 conversion
fields, and reconciled all 28 calls with 84 durable events. It performed
no new OpenMM or native evaluation and found no material arithmetic or
accounting issue. It checked the reported system-hash equality without
rebuilding systems. Its 6,168-byte receipt is retained at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-particle-roundtrip-read-only-review-20261001-_w3li0vz/read-only-review.json`, SHA
`5dec54f7d8a356f109c313948bb2b4921b0f13d4b0fd01479ff49ade93283180`.

## Reproducible evidence and remaining work

Plan SHA: `69663a95abd723345e650c47519aab72a42f8bd8c3f7ba6846ff39d30682d0c0`.
Executing diagnostic source SHA:
`f9d860e150542596457e546802ef8594365c112c424f8a1abf8e82a1734e9c3a`.
Receipt (8,783,916 bytes) SHA:
`4d392e37f9c6a933b980fd39cd48fbd0dc12df7f8c4bf01c025dbb3b76ba8dfc`.

Raw plan/source snapshots, message-safe execution logs, fsynced call ledger,
full vectors, particle hex/ULP/rational deltas and root reviews are retained at:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-particle-roundtrip-20261001-ri1tdoph`.
CI-command QA is retained at `/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-roundtrip-ci-command-qa-20261001-kf0j2543`.
The machine-readable [evidence summary](../evidence/sro_particle_roundtrip_observation_20261001_v1.json) links exact refs.
The [pre-execution plan](sro_particle_roundtrip_diagnostic_plan_20260930.md)
remains unchanged as its prior source snapshot.

The original five metadata/stored-observation pins remain unchanged, including
the terminal result. R2 remains completed 2 / failed 1 / unstarted 1, recovery
**0/4**. No ligand reference, protected Fresh-128, assay role, scientific
qualification, HIP claim or release authority is promoted. The two known
development states are not independent holdout samples.

The next planned diagnostic observes native cross/LJ/Coulomb vectors for
case02 initial only. It retains the original combined gradient, compares it
with one new unchanged baseline, and requires full binary64 equality.
Native internal separation and coordinate-unit/arithmetic-order interventions
remain later questions. Preserve original outputs, thresholds, identities,
role boundaries and honest call/cost accounting. The five-goal objective
remains incomplete.
