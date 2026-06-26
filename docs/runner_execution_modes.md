# Runner Execution Modes

Status: reference (fail-closed).

Source of truth: `api/runner_profile_contract.py`
(`validate_runner_profile_execution_contract`).

Every validated runner profile must declare an explicit **execution mode** that
defines what the runner is allowed to do. The contract is fail-closed: missing
or ambiguous declarations resolve to `unspecified` and are never eligible for
customer docking dispatch.

## Modes

| mode | constant | customer submissions | synthetic input | production claim | customer pose emission |
| --- | --- | --- | --- | --- | --- |
| `smoke` | `EXECUTION_MODE_SMOKE` | must be `false` | allowed | must be `false` | must be `false` |
| `restricted-production` | `EXECUTION_MODE_RESTRICTED_PRODUCTION` | allowed | must be `false` | explicit boolean | explicit boolean |
| `unspecified` | (fallback) | `false` | `false` | `false` | `false` |

`ALLOWED_EXECUTION_MODES = {smoke, restricted-production}`. Any other value
raises `PermissionError`.

### Required explicit booleans

For an explicit mode, all of the following must be present as real booleans
(`_required_bool` raises `PermissionError` otherwise):

- `customer_submission_allowed`
- `synthetic_input_allowed`
- `production_claim_allowed`
- `customer_pose_emission_allowed`

### Mode rules (enforced)

- **smoke**: internal only. Rejects `customer_submission_allowed`,
  `production_claim_allowed`, and `customer_pose_emission_allowed` if any is
  `true`. Synthetic input (e.g. a single labelled synthetic ligand) is permitted
  precisely because this lane is non-customer and non-claim.
- **restricted-production**: customer-facing intake lane. Rejects
  `synthetic_input_allowed = true` — production runs must use real customer
  inputs. Production claims and customer pose emission remain individually gated
  by their explicit booleans and stay fail-closed by default.
- **unspecified**: returned only when `require_explicit=False` for legacy ad-hoc
  profiles. All capabilities are `false`; such a profile can never be used for
  customer docking dispatch.

## Returned contract

`validate_runner_profile_execution_contract` returns:

```json
{
  "execution_contract_explicit": true,
  "execution_mode": "restricted-production",
  "customer_submission_allowed": true,
  "synthetic_input_allowed": false,
  "production_claim_allowed": false,
  "customer_pose_emission_allowed": false
}
```

## Relationship to the docking pipeline

- The execution contract is attached to the dispatch manifest, so the worker
  lane is explicit before any compute is scheduled
  (see `docs/product_docking_state_machine.md`, Layer 2).
- Smoke-profile records cannot carry customer docking submissions; customer
  records cannot run under the smoke profile.
- Broad scientific claims and customer pose emission remain disabled until the
  relevant explicit booleans are set under `restricted-production` **and** the
  release evidence ladder is satisfied
  (see `docs/release_claim_evidence_ladder.md`).
