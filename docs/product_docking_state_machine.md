# Product Docking State Machine

Status: reference (fail-closed). Reflects the code as of this document.

Source of truth:
- `betelgeuze_product/docking_request.py` — `build_docking_job_record` (intake)
- `betelgeuze_product/job_orchestration.py` — status/queue/worker transitions,
  `_queue_status`, `_status_progress_contract_ready`, cancel/retry
- `betelgeuze_product/job_terminal_state.py` — `apply_terminal_job_state`
- `api/docking_dispatch.py` — bridge to the durable queue
- `api/job_store.py` — `SQLiteJobStore` durable queue + outbox

The product docking pipeline has **two coordinated state layers**. Every state
is fail-closed: `execution_enabled` and `docking_results_emitted` are always
`False` at this layer, and no scientific results are claimed.

## Layer 1 — Product docking job ledger (per-job JSON file)

This is the customer/operator-facing record under
`results/product_docking_jobs/<job_id>.json`.

### `status` values

| status | meaning | `queue_status` |
| --- | --- | --- |
| `accepted_fail_closed` | intake passed contract validation; queued | `queued_fail_closed` |
| `blocked_contract_validation` | intake failed validation; not queued | `blocked_contract_validation` |
| `running_fail_closed` | a worker holds a lease | `worker_lease_active_fail_closed` |
| `failed_fail_closed` | worker reported failure (retryable unless limit reached) | `failed_retryable_fail_closed` |
| `cancel_requested_fail_closed` | operator requested cancellation | `cancel_requested_fail_closed` |
| `retry_requested_fail_closed` | operator requested a retry | `retry_requested_fail_closed` / `retry_attempt_recorded_fail_closed` |
| `completed_fail_closed` | worker reported completion (terminal) | `completed_fail_closed` |

### Supporting fields

- `worker_state`: `not_started_fail_closed` → `leased_fail_closed` /
  `active_fail_closed` → `completed_fail_closed` / `failed_retryable_fail_closed`;
  `cancel_acknowledged_fail_closed` when a leased job is cancelled.
- `progress_state`: `ledger_intake_recorded` → `worker_heartbeat_recorded` →
  `worker_dispatch_completed` (success) or `worker_failed_retryable` (failure);
  plus `cancel_requested_fail_closed`, `retry_requested_fail_closed`,
  `retry_attempt_recorded`.
- `progress_percent`: `0.0` at intake, `100.0` only on
  `completed_fail_closed`, clamped to `<= 99.0` on failure.

`job_orchestration._status_progress_contract_ready` enforces that the tuple
`(status, progress_state, current_step, worker_state, queue_status,
progress_percent)` is internally consistent for every transition. An
inconsistent record reports `status_progress_contract_ready = false`.

### Transitions

```
                       intake (build_docking_job_record)
                                   |
                validation pass    |    validation fail
                                   v
        accepted_fail_closed                 blocked_contract_validation (terminal-ish)
                |
        dispatch eligible (Layer 2 enqueue)
                |
        running_fail_closed  <----- worker lease/heartbeat
            |        |    \
   completed     failed    cancel_requested_fail_closed
  _fail_closed  _fail_closed
   (terminal)      |
                   v
            retry_requested_fail_closed --> retry child job (new root-linked record)
```

- Cancel: `cancel_job_record` sets `cancel_requested_fail_closed`, marks
  `cancellable=false`, keeps `retryable=true`, and acknowledges the worker lease
  if one was held.
- Retry: bounded by `MAX_RETRY_ATTEMPTS = 3`
  (`retry_policy = operator_requested_retry_child_preserves_request_sha256_max_3`).
  A retry child preserves the original `request_sha256` and links via
  `root_job_id` / `parent_job_id`.
- Terminal: `apply_terminal_job_state` writes `completed_fail_closed` or
  `failed_fail_closed` and sets `terminal_state=true` in
  `status_transition_contract`.

### Workflow controls (customer actions)

`workflow_control_links` always exposes `self`, `history`, `cancel`, `retry`.
`workflow_allowed_actions` is derived from `cancellable` / `retryable` /
`retry_limit_reached`; disabled actions are listed in
`workflow_disabled_actions`.

## Layer 2 — Durable SQLite queue (`SQLiteJobStore`)

The dispatcher bridges an eligible ledger record into the durable queue via
`api/docking_dispatch.enqueue_docking_job` →
`SQLiteJobStore.create_job_if_absent`.

### `simulation_jobs.status`

`submitted` → `running` (leased) → `completed` | `failed` | `retry_ready`.

- `acquire_next_job` leases a `submitted`/`retry_ready` job (or a `running` job
  whose lease expired), bumping `attempt_count` and setting a lease.
- `heartbeat_job` extends the lease; `release_job_for_retry` moves to
  `retry_ready` (or `failed` once `attempt_count >= max_attempts`).
- `create_job_if_absent` is idempotent: a duplicate dispatch never resets a
  running/completed row.

### Transactional outbox

Durable state changes emit rows into `simulation_job_outbox` in the **same
transaction**:

- `job_created` on creation (`create_job` and `create_job_if_absent`).
- `job_status_changed` on terminal/retry transitions.

Outbox rows are `pending` → `delivered` (`mark_outbox_event_delivered`) or
`recovered` (`mark_outbox_event_recovered`). Outbox payloads are sanitized
(`sanitize_request_for_ledger`) and error strings are redacted to a SHA-256
summary, so raw customer inputs never enter the outbox.

## Cross-layer synchronization

- Layer 1 `running_fail_closed` corresponds to Layer 2 `running` (leased).
- Layer 1 `completed_fail_closed` / `failed_fail_closed` are written by
  `apply_terminal_job_state` from the Layer 2 simulation status.
- The ledger remains the source of truth for the customer-facing API response
  (see `docs/` API response contract); the queue is the source of truth for
  worker scheduling and durable recovery.
