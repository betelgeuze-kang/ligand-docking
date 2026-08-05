# Engine V2 one-shot full candidate evidence

## Decision

The historical clearance-selection A/B no longer accepts three compact
hash-manifest files as scientific evidence. Result materialization requires one
complete two-arm bundle containing all eight scored case activation receipts and
all 1,024 candidate receipts.

This contract does not reserve, start, or run the experiment.

## Bundle contents

The full bundle binds:

- the exact run-start receipt;
- the execution-environment identity;
- the reviewed source commit;
- the one-shot and activation policy identities;
- one complete Rust CPU scorer backend receipt;
- eight case-level execution-binding wrappers;
- eight complete selection-activation receipts;
- 512 baseline candidate receipts;
- 512 experimental candidate receipts;
- independently derived baseline and experimental summaries; and
- independently derived cross-arm changed-slot evidence.

Each case wrapper repeats the run-start, environment, source commit, policy,
activation-policy, scorer-backend, and case identities. A case receipt from a
different run cannot be inserted without violating the wrapper and bundle
bindings.

## Independent reconstruction

For every candidate the verifier reconstructs the canonical:

1. `ScorerV1Terms`;
2. `PoseValidityResult`;
3. internal-validity evidence;
4. PoseBusters evidence and its complete required check set;
5. authenticated RMSD evidence;
6. candidate receipt; and
7. 64-row arm ranking receipt.

It also rechecks the case-source authority, source-proposal receipt, allocation
receipt, current-V7 lineage, activation snapshot, activated state, target
candidate duplication, target/non-target mutation boundary, and all authority
flags.

A list of candidate receipt hashes is not accepted. Summary booleans are not
trusted. The compact arm and cross-arm inputs used by the result writer are
derived after the complete bundle passes verification.

## Exact denominator

The bundle must contain the ordered scored cohort:

```text
5SD5_HWI
5SIS_JSM
6M2B_EZO
6T88_MWQ
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
```

For each case, both arms must contain proposal indices `0..63` exactly once.
The resulting denominator is:

```text
8 cases × 64 candidates × 2 arms = 1,024 candidate rows
```

Missing rows, duplicate rows within an arm, case substitution, arm-role
substitution, stale run bindings, backend substitution, non-target mutation,
changed-slot omission, and summary substitution fail closed.

## Cross-arm reconstruction

For each corresponding slot the verifier requires identical:

- candidate ID and proposal index;
- source-proposal identity;
- scorer authority input, context, configuration, and backend;
- validity authority input, problem, context, configuration, and implementation;
- PoseBusters implementation, configuration, version, mode, native pose, and
  receptor identities; and
- RMSD implementation, configuration, method, native pose, receptor, atom
  mapping, and symmetry identities.

Only a frozen activation target with `selection_applied=true` may change its
scientific projection. Every selected replacement produces one derived changed
slot receipt. A non-target difference is rejected.

## CLI

After the already-separated reservation and run-start steps, result writing uses
one argument:

```bash
python tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py \
  write-result \
  --full-evidence /absolute/path/to/full-two-arm-evidence.json
```

The CLI derives both arm summaries and the cross-arm verdict inputs from that
file. It no longer accepts caller-authored arm-summary JSON files.

## Authority boundary

```text
historical execution authority is not created here
fresh holdout execution authorized = false
Stage 0 admission authority = false
profile promotion authority = false
product execution authorized = false
customer pose emission authorized = false
public or scientific claim authorized = false
```

Actual historical execution remains separately blocked by reservation,
cross-clone lifetime authority, reviewed operator infrastructure, and human
scientific/security approval.
