# Engine V2 source-paired clearance one-shot A/B

## Status

```text
authority_contract_implemented: true
complete_candidate_artifact_audit_implemented: true
historical_ab_execution_authorized: true
maximum_lifetime_run_count: 1
molecular_runner_implemented_here: false
external_operator_reservation_required: true
fresh_holdout_execution_authorized: false
stage0_admission_authority: false
profile_promotion_authority: false
product_execution_authorized: false
customer_pose_emission_authorized: false
public_or_scientific_claim_authorized: false
```

This contract authorizes one historical contaminated-development comparison only.
It does not execute docking in GitHub or in the package. An external reviewed
runtime must generate the complete two-arm evidence after atomically reserving
run ordinal one.

## Frozen source authorities

| Authority | Identity |
| --- | --- |
| Phase 2.5 cohort policy | `betelgeuze.engine_v2_phase25_cohort_admission/1.3.0` / `b4c5530dc4766500dbbc854875cfb39baadad94196c63be6150514879993d211` |
| Clearance activation policy | `betelgeuze.engine_v2_source_paired_clearance_activation_policy/1.2.0` / `988d0bb47bfa6ff934887e1e12b5a512b55aaf40033a04963d141c4ffefe212c` |
| Clearance selection policy | `e5936f33d5aec54aae67f519e5cf6dffcc61181237270adb3e367a5f65cb29ad` |
| One-shot policy | `betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_policy/1.1.0` / `b9d2dc1c716c0f954ba5a9f30ecc08168eb29331293b8df5c08fa67ca7ae377f` |
| Verdict receipt | `betelgeuze.engine_v2_source_paired_clearance_one_shot_ab_verdict/1.1.0` |
| Required scorer backend | `rust_cpu_required` |

The source-binding layer independently verifies the Phase 2.5 and activation
policy self-hashes and keeps all fresh, product, customer-pose, Stage 0,
promotion, and public/scientific authority false.

## Corrected frozen decision semantics

A research Go requires all six invariants:

- no preparation-failure regression;
- no Top-1 or Top-5 recovery regression;
- exactly 512 candidates in each arm;
- source controls preserved;
- complete score-term semantics verified;
- no result-dependent allocation.

After all invariants pass, **any one** primary criterion is sufficient:

- a new exact-valid candidate in a previously uncovered case;
- proposal-oracle recovery of at least `2/8`;
- invalid Top-1 at most `4/8`.

The hard No-Go keys are:

- `required_invariant_failed`;
- `all_primary_go_criteria_failed`;
- `existing_recovery_regression`;
- `selected_state_remains_penetrating_without_posebusters_validity_change`.

Hard No-Go has precedence. Historical diagnostic fields remain nonblocking and
cannot override another successful primary criterion.

A Go authorizes only a separate fixed development decision study. A No-Go closes
the local torsion/clearance refinement epic and directs the next scientific track
to deterministic global orientation and surface-aware placement. Neither result
opens fresh-128, Stage 0, product execution, pose delivery, promotion, or claims.

## Exact cohort and denominator

The input roster is fixed in this order:

```text
5SD5_HWI
5SIS_JSM
6M2B_EZO
6M73_FNR
6T88_MWQ
6TW5_9M2
6TW7_NZB
6VTA_AKN
6WTN_RXT
```

`6M73_FNR` remains the typed preparation failure. The other eight cases retain
64 candidate slots in each arm:

```text
baseline current V7:      8 × 64 = 512 candidate receipts
experimental activation:  8 × 64 = 512 candidate receipts
combined scored rows:               1,024
```

Vina, GNINA, fresh-128, smoke cases, aliases, and result-driven allocation are
outside this execution authority.

## Exact clean-checkout and durable-state boundary

All authority state is confined to:

```text
.betelgeuze/engine_v2_source_paired_clearance_one_shot_ab/
├── execution-reservation.json
├── run-start.json
└── result.json
```

Every evidence directory below `.betelgeuze` must be mode `0700`; every receipt
is mode `0600` and created with exclusive no-overwrite semantics. Symlinked,
escaping, missing, wrong-mode, or substituted durable roots and receipts fail
closed.

Authorization, reservation, run-start, and result writing require the exact clean
Git checkout. The operator's source SHA must equal the observed lowercase
40-character `HEAD`. Run-start reopens and compares the exact durable reservation,
then rechecks clean `HEAD`. Result writing reopens and compares the exact durable
run-start, then rechecks clean `HEAD` again. Reconstructed in-memory receipts,
missing Git metadata, installed-wheel-only execution, dirty files, or checkout
movement cannot consume or finalize the one-shot authority.

### Lifetime uniqueness boundary

The repository code enforces one run inside the exact reviewed durable evidence
store. Copying the repository or deleting that store cannot create a second
scientifically authoritative run. Cross-clone lifetime uniqueness therefore
requires an external immutable reservation ledger or equivalent reviewed operator
control. Until that external authority exists, the local policy must not be
represented as globally enforcing one run across every copy of the repository.

## Complete candidate-level evidence contract

The historical result writer accepts exactly one external evidence file:

```text
full-comparison-evidence.json
```

Hash-only arm summaries, caller-declared candidate counts, caller-declared
Top-1/Top-5 sets, and separate cross-arm summary files are not accepted by the
operator CLI.

The complete artifact contains:

1. the exact eight full
   `SourcePairedClearanceSelectionActivationReceiptV1` case receipts;
2. 512 baseline candidate bindings;
3. 512 experimental candidate bindings; and
4. run, source, environment, arm, case, and proposal-index bindings for every
   candidate receipt.

Each full case receipt must retain and revalidate:

- the frozen archive-member and authenticated-input source authority;
- the complete 64-slot source proposal receipt;
- the complete current-V7 lineage;
- the pre-score activation snapshot and selected/retained state;
- all eight `ScorerV1Terms` values and their exact binary64 decomposition;
- context-bound internal-validity observations;
- all 22 PoseBusters checks under `posebusters==0.3.1`, mode `redock`;
- authenticated symmetry-aware RMSD evidence;
- raw score, deterministic rank, Top-1, and Top-5 identity; and
- exact target/non-target cross-arm behavior.

The full-artifact verifier independently reconstructs:

- the exact `(case_id, arm, proposal_index)` grid;
- candidate and case receipt uniqueness;
- score ordering and ranks;
- Top-1 and Top-5 recovery sets;
- exact-valid and proposal-oracle case sets;
- invalid selected Top-1 case sets;
- changed-slot identities;
- shadow-eligible and penetrating-without-validity-change counts; and
- the compact arm, cross-arm, and final verdict documents.

Missing rows, duplicate rows, fabricated nested receipts, source cross-wires,
non-target changes, cross-run reuse, cross-arm reuse outside the frozen contract,
or caller-declared summary drift fail closed.

The complete artifact is opened with `O_NOFOLLOW`, bounded to 512 MiB, and pinned
by descriptor identity, mode, size, and modification time throughout the read.
The artifact itself remains development evidence; it does not make the scorer an
affinity model or make the result claim-safe.

## Operator sequence

### 1. Verify status

```bash
python tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py \
  --repo-root "$PWD" status
```

### 2. Reserve run ordinal one

```bash
source_commit="$(git rev-parse --verify 'HEAD^{commit}')"
python tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py \
  --repo-root "$PWD" reserve \
  --source-commit "$source_commit" \
  --operator-id <reviewed-operator-id> \
  --execution-environment-sha256 <64-char-sha256>
```

The environment identity must bind the exact Python, Torch, RDKit, PoseBusters,
Rust/native wheel, host, CPU/thread policy, and reviewed source checkout.

### 3. Create run-start receipt

Do not modify or advance the checkout after reservation.

```bash
python tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py \
  --repo-root "$PWD" start
```

No molecular output should be created before this succeeds.

### 4. External molecular execution and full artifact construction

The reviewed external runner must use the source-bound clearance activation
snapshots, retain all 1,024 full candidate receipts, and construct one
self-hashed full-comparison artifact bound to the durable run-start identity.

Repository code provides the pure constructor and verifier:

```text
build_full_comparison_evidence_artifact(...)
verify_full_comparison_evidence_artifact(...)
```

These functions do not run docking and do not reserve execution.

### 5. Atomically derive and bind the result

```bash
python tools/manage_engine_v2_source_paired_clearance_one_shot_ab.py \
  --repo-root "$PWD" write-result \
  --full-evidence full-comparison-evidence.json
```

The CLI accepts no baseline-arm, experimental-arm, cross-arm, or hash-only
summary arguments. `result.json` is written once only after complete artifact,
durable state, source, denominator, and result bindings pass and the verdict is
independently rederived.

## Claim boundary

The result always retains:

```text
fresh_holdout_execution_authorized = false
stage0_admission_authority = false
profile_promotion_authority = false
product_execution_authorized = false
customer_pose_emission_authorized = false
public_or_scientific_claim_authorized = false
```

The historical result is diagnostic development evidence only. It cannot be used
to claim calibrated docking, independent validation, customer readiness,
ROCm/HIP acceleration, affinity, free energy, or broad product superiority.

## CI boundary

The bounded one-shot workflow is read-only, checks out the exact PR head, and is
registered in the Engine V2 CI authority inventory. It compiles the full artifact
verifier, runs the original authority/result contracts and full-artifact tamper
suite, and proves that the operator CLI exposes only `--full-evidence` for result
binding. Stage 0's frozen authoritative workflow set remains unchanged.
