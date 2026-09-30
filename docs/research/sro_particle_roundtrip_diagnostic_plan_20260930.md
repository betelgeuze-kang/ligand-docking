# Prospective SRO particle round-trip diagnostic v1

This is a new numerical observation of frozen `perturbed_02` saved `initial` and
`last_accepted` states. No actual numerical execution has occurred when this plan
document is published. Synthetic/mocked QA is a separate implementation receipt.
The terminal R2 campaign remains `completed=2 / failed=1 / unstarted=1`, recovery
`0/4`. Its code, packets, thresholds, denominator, receipts and terminal result
are frozen. This experiment does not resume or rerun that campaign.

## Question and controlled intervention

At the same saved coordinates, what ligand force difference is observed between
the source XML particle q/sigma/epsilon arm and the native-unit-to-OpenMM-unit
round-trip arm? The original arm uses the frozen benchmark `OpenMMBoundary.build`
without arithmetic edits. Both arms call that same builder. The second arm then
sets only the existing CustomNonbondedForce per-particle q/sigma/epsilon values:
`charge_e`, `sigma_angstrom / 10`, `epsilon_kcal_per_mol * 4.184` in binary64.
Native fields come from the original approved parameters/cross JSON, not from a
new source-XML conversion. All ligand and receptor particles are inventoried.

Source exceptions remain source exceptions, including their q products, sigma,
epsilon, excluded pairs and order. Bonded terms, constraint policy, force groups,
cutoff, switch expression, interaction groups, particle order, units, sign and
Reference platform are fixed. Serialized system hashes with only custom particle
q/sigma/epsilon neutralized must agree across arms before any context is created.
There are no native evaluator, scorer, optimizer or intrareceptor energy calls.

## Input roles and read phases

The fixed root is:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-guard-repair-four-case-20260930-p76d71f6`.

1. Code review and mock QA: owned diagnostic/test/document source and the frozen
   benchmark source only; synthetic data supplies all molecular test bodies.
2. Metadata preparation: fixed R2 `plan.json`, `oracle-input-spec.json`, case02
   `native/endpoint-states.json` and `oracle/numerical-receipt.json` are read as
   metadata or stored numerical observations. Their pins and semantic binding
   are preserved. Numerical file paths, byte sizes and hashes are checked without
   opening molecular bodies. Source/test/document snapshots and plan are written
   directly to a new MNT directory. Preparation rejects any output inside R2.
3. Only after root review authorizes execution: the original ligand/receptor XML,
   original parameters/extensions/cross JSON and approved receptor canonical
   coordinates are opened with exact bound refs. The six numerical roles must be
   exact, their paths must match the reviewed fixed metadata, and source XML and
   parameter hashes must match frozen constants before the first numerical body
   read. Existing XML/domain validators are reused. The original ligand canonical
   body and protected Fresh-128/reference/evaluation_only/stability_control data
   are forbidden. The receptor canonical body supplies only numerical coordinates.

Pins use bounded no-follow regular-file reads, before/after identity checks and
SHA256. The frozen oracle executes the exact verified raw source bytes; cached
bytecode and read-to-import substitution are not used. All plan refs are checked
again after execution. No source or output may overwrite the frozen campaign.

## Source, system and state pins

The prospective JSON plan records every ref as absolute path, bytes and full
SHA256. It also pins the diagnostic, tests, plan document and frozen oracle source
snapshots and executing Python binary. Reviewed numerical source hashes are:

| Role | SHA256 |
| --- | --- |
| frozen oracle | `9a1598e8f94e98ff691a435e8f6a43835a9408c58e9da07051fdd7a56e90f1e1` |
| ligand XML | `6446b0f2babfab9748fc445653d8cd2453e5d98ad1483320da197e55192734ea` |
| receptor XML | `7c5aeeeafed880dfee5f294fc34b6a0e2ec5a31d9482245b5cab93c10d4d1cc6` |
| original parameters | `16d3b25e6492ae8500771d60d6fe5b5db12089b8c7fa64d3f25a6f1230fad217` |
| original extensions | `871c1a252c87c0b4f134c8b572f009f99658fea88f1076c9ee3fe1461a0871f6` |
| original cross parameters | `226cb9f4be87b40d312e4b3bdb0dbc785bd6d6e87daa68e2f6abec76dde22d52` |
| receptor numerical coordinates | `2c0970bcaf9e994f382e0f0c0fdacbfd1359bef60a10b879f757b31628658c4c` |
| saved case02 endpoints | `f6bb712b6530cdc2b25549a2f051df7b62f46bea248d54c09a179ed0364fa81e` |
| saved case02 oracle receipt | `1f18b0c87de396ab330886094fa3085edecc98a7085ef60bf5acff60002184c7` |

The original protocol SHA is
`5977f12ee7e35710e6a8eb09a19337ff579750f2573fa442d31b89fe3a94ca23`;
manifest SHA is
`4fa96ef4a8457fd20e8bce67dafa380c08b01e15765bcfbb0a1eb67634815dc3`.
Case02 derived system SHA is
`5b8ae90bb1df526ebe32f2d78be5681744e15b3a43efc887ceb49f80a8f4403b`;
topology SHA is
`4d6026f9df8d4cba21f80048f2e3b199a548f531f7cff09ca7f534d3205338f6`.
The plan includes request/binding hashes and exact stored observation, coordinate
and native total force hashes for each state. Newly built arm systems gain full
serialization and all-nonintervened-field hashes in the execution receipt.

## One-time protocol and accounting

The protocol reserves 4 contexts, 8 setPositions calls and 16 getState calls:
two arms, two states, internal total / cross total / cross LJ / cross Coulomb.
The complete 28-call ledger is reserved and fsynced before numerical dispatch.
Each call records reservation, a durable unknown start, completion or error,
wall time and process CPU time. A killed start remains unknown. Reserved calls
not reached remain not dispatched. Errors do not imply known internal work.
Context release is measured separately. Receipt status `completed` means the
diagnostic collected its observations; it does not mean numerical gates passed.
An execution failure produces a failed receipt and a nonzero CLI exit status.
Each execution output must be new; no diagnostic resume or retry into an old
output directory is supported.

Leaf calls, numerical enclosing cost and entry enclosing cost are nested scopes.
They must not be added. Process CPU time is local process time, not a guarantee
of total host CPU cost, speedup or campaign CPU consumption. Completed getState
observations remain marked as actual observations if later validation fails.

Every particle field records original/OpenMM, native, converted-source/native
and round-trip/OpenMM binary64 hex, each value's ULP size, distances in the same
units, changed-field identity and exact rational round-trip-minus-original delta.
Every state/arm stores 26 ligand vectors and energy for all four observations and
their assembled total, with maximum component and atom/axis. The total native
minus arm residual and round-trip minus original arm delta are both retained.
The algebraic residual identity and its floating subtraction roundoff are saved.

## Interpretation limits

The stored case02 initial oracle comparison failed at force component error
`4.761386662721634e-08`; last accepted error was `2.035172030900867e-11`.
The original `1e-8` energy/component/force gate and the frozen failure conclusion
remain unchanged. A different arm can satisfy that gate in this new observation
without retrospectively changing R2 status.

The earlier oracle did not retain its force vectors. New original-arm vectors
are new prospective observations, not recovered original oracle vectors. Native
term force vectors are absent. Internal/cross/LJ/Coulomb arm deltas describe
differences between the two new OpenMM arms and cannot be called native term
residuals. Residual reduction alone does not establish root cause. This experiment
does not establish pose recovery, source admission, source XML equivalence,
physical accuracy, qualification, release readiness or speedup.

## Reviewable commands

Root supplies a new absolute MNT PLAN_DIR and runs the finalized owned source:

```bash
/usr/bin/python3 -I -B /ABS/OWNED/SOURCE/sro_particle_roundtrip_diagnostic_v1.py prepare \
  --r2 /mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-guard-repair-four-case-20260930-p76d71f6 \
  --output /ABS/NEW/MNT/PLAN_DIR \
  --test-source /ABS/OWNED/TEST/test_sro_particle_roundtrip_diagnostic_v1.py \
  --document-source /ABS/OWNED/DOC/sro_particle_roundtrip_diagnostic_plan_20260930.md
```

After inspecting that plan and its returned exact SHA, root authorizes one run:

```bash
/usr/bin/python3 -I -B /ABS/NEW/MNT/PLAN_DIR/source/sro_particle_roundtrip_diagnostic_v1.py execute \
  --plan /ABS/NEW/MNT/PLAN_DIR/plan.json --plan-sha256 FULL_REVIEWED_SHA256 \
  --output /ABS/NEW/MNT/EXECUTION_DIR --numerical-phase-authorized
```

Source/test pins and raw synthetic QA stdout/stderr/JUnit must remain in their
new MNT QA directory. They must not exist solely in `/tmp`. No Git operations
are part of this diagnostic assignment. Actual numerical execution is still
absent until a separately authorized execution receipt exists.
