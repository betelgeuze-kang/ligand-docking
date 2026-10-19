# Prepared research job lifecycle

`betelgeuze-dock prepared-jobs` and `/product/prepared/jobs` use one local,
tenant-scoped authority for the bounded prepared Fourier development protocol.
Submitting work queues a job. A trusted local owner explicitly runs at most one
queued job with `betelgeuze-dock prepared-jobs owner-once`.

This is a research vertical slice. It does not unify every existing docking
backend or establish molecular accuracy, deployment readiness, or external-user
acceptance. The original Engine V2 CLI and numerical workflow remain separate.

## Local configuration and admission

Install the product wheel in a dedicated Linux CPU environment. Numerical work
requires the pinned CPU Torch dependency; HTTP additionally requires the API
dependencies. Help and queue/status operations do not import Torch or FastAPI.

The administrator configures these environment variables:

| Variable | Meaning |
| --- | --- |
| `BETELGEUZE_PREPARED_LIFECYCLE_ENABLED` | `1` enables this optional service. |
| `BETELGEUZE_PREPARED_LIFECYCLE_STATE_ROOT` | Absolute, locally owned private state directory. |
| `BETELGEUZE_PREPARED_LIFECYCLE_INPUT_ROOT` | Absolute, locally owned private admission directory. |
| `BETELGEUZE_PREPARED_LIFECYCLE_TENANT_ID` | Trusted CLI/owner tenant; defaults to `local`. |

State and admission directories must have mode `0700`. A trusted preparation
step puts the protocol and all five referenced input documents, including nested
source evidence, inside a private admission bundle. The Python-only
`register_admission` helper records its tenant, exact protocol digest, explicit
evidence kind, and optional initial pause. The public submit request accepts an
opaque admission identifier and an idempotency key; it accepts no filesystem
path, executable, environment override, or arbitrary model.

Before numerical dispatch the owner requires the existing namespace runtime
qualification receipt configured through
`API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_PATH` and
`API_VALIDATED_RUNNER_NAMESPACE_RECEIPT_SHA256`. A synthetic test fixture is not
host qualification. That receipt covers its explicit namespace properties only.

## Commands and HTTP operations

```text
betelgeuze-dock prepared-jobs plan ADMISSION
betelgeuze-dock prepared-jobs get-plan PLAN_ID
betelgeuze-dock prepared-jobs execute PLAN_ID --plan-sha256 SHA256 --idempotency-key KEY
betelgeuze-dock prepared-jobs submit ADMISSION --idempotency-key KEY
betelgeuze-dock prepared-jobs status EXECUTION_ID
betelgeuze-dock prepared-jobs cancel EXECUTION_ID --reason "operator request"
betelgeuze-dock prepared-jobs resume EXECUTION_ID
betelgeuze-dock prepared-jobs verify EXECUTION_ID
betelgeuze-dock prepared-jobs report EXECUTION_ID
betelgeuze-dock prepared-jobs compare EXECUTION_ID OTHER_EXECUTION_ID
betelgeuze-dock prepared-jobs artifacts EXECUTION_ID
betelgeuze-dock prepared-jobs artifact EXECUTION_ID ARTIFACT_ID
betelgeuze-dock prepared-jobs owner-once
```

| HTTP operation | Purpose |
| --- | --- |
| `POST /product/prepared/jobs/plans` | Retain a zero-force plan for an admitted input and bounded budget policy. |
| `GET /product/prepared/jobs/plans/{plan_id}` | Read the immutable public plan and its SHA256. |
| `POST /product/prepared/jobs/execute` | Queue `plan_id`, `plan_sha256`, and `idempotency_key` through the existing job authority. |
| `POST /product/prepared/jobs` | Queue an admitted job with `admission_id`, `idempotency_key`, and optional `budget_policy`. |
| `GET /product/prepared/jobs/{id}` | Read state, known work, model/units, budgets, and artifact descriptors. |
| `POST /product/prepared/jobs/{id}/cancel` | Request cancellation; optional bounded `reason`. |
| `POST /product/prepared/jobs/{id}/resume` | Explicitly queue a verified known pause. |
| `GET /product/prepared/jobs/{id}/verify` | Check retained generations, artifacts and the owning numerical journal without evaluating forces. |
| `GET /product/prepared/jobs/{id}/report` | Read a verified baseline/last-observed report, preserving unknown work and nonconvergence. |
| `POST /product/prepared/jobs/compare` | Compare retained results for every requested `execution_ids` entry; no automatic winner or ranking. |
| `GET /product/prepared/jobs/{id}/artifacts` | List immutable artifact descriptors. |
| `GET /product/prepared/jobs/{id}/artifacts/{artifact_id}` | Download hash-checked JSON with its digest as ETag. |

HTTP requires the authenticated principal supplied by ProductSecurityMiddleware.
A raw tenant header is insufficient. Other tenants receive the same not-found
response for jobs and admissions. The local owner command is an administrator
operation and has no public HTTP equivalent.

Plans freeze the registered input bytes, implementation and runtime identities,
solver bounds, model, force semantics, units and cumulative budget. Planning
checks registered byte identities and the bounded solver admission; the fixed
worker performs full molecular validation before its first evaluation. Planning
does not create an execution, reserve force work or import Torch. A changed
input, runtime, implementation or policy prevents stale-plan execution. CPU
placement is selected from the available CPUs at submission and does not change
the plan's numerical work or refresh its budget. Legacy submit and plan-bound
execute share the same idempotency and owner authority.

Verification and reporting use a fixed isolated child to read the owning
Fourier verifier and retained reporter. That fresh child initializes both Torch
thread pools to one before importing the owning verifier, matching the numerical
worker's frozen environment. Public requests do not change the API process's
global Torch settings. The read paths perform no optimization, graph
construction or force evaluation. Source, runtime and retained receipt checks
remain exact; moving the reader does not relax frozen environment matching.
Their measured read-only costs are separate from worker execution accounting;
they do not reset or consume numerical reservations. Each isolated owning read
has a 120-second controller wall deadline, 90 CPU seconds, one allowed CPU,
4 GiB address space and a 1 MiB file-size limit. Its request, stdout and stderr
are bounded at 1 MiB, 4 MiB and 64 KiB. These are ceilings, not measured cost or
RAM limits. Registry, artifact and pre/post journal scans run in the parent
outside that child envelope; there is no aggregate whole-request containment
claim. The response separates child CPU/RSS observations from parent request
wall time, and does not attribute process-wide parent CPU to a concurrent
request. Active work stays
unresolved. Unknown total work remains null even when an earlier known prefix
can be checked. A completed process is not evidence of numerical convergence.
Comparisons retain missing, forbidden, failed and unknown requested entries in
their denominator and make energy differences unavailable unless the exact
Hamiltonian and units are compatible. They confer no chemical validity, pose
selection or scientific qualification.

## State and recovery contract

The dedicated SQLite registry uses durable transactions, tenant-scoped
idempotency, fenced owner generations, invocation reservations, events, and
artifact descriptors. Repeating the same request returns the same execution;
reusing its key for another request fails with `IDEMPOTENCY_CONFLICT`.

An active job reports unresolved numerical state and a null total force count.
Cancel acknowledgment means `requested`; process-terminal confirmation requires
the actual contained process to exit and be reaped. A fully published completion
can win a concurrent cancellation request. A cancelled job with a verified known
pause can explicitly resume if its cumulative budget remains. Completed resume
is a no-op. Owner loss, incomplete publication, unverified containment, or an
unknown force census prevents automatic recovery and numerical reissue.

The fixed installed worker runs with isolated Python imports and checks its
owner token, generation, admission, implementation closure, installed origins,
runtime identity, affinity, and applied resource limits. Known numerical failure
is distinct from transport/publication uncertainty. A visible result followed by
nonzero worker exit does not establish a durable known result.

## Bounded resources and evidence

The only policy is `local_cpu_research_v1`: 300 cumulative charged wall/CPU
seconds, one CPU/thread, 4 GiB virtual address space, 64 MiB per file, 200 MiB
published output plus a sampled tree guard, 1 MiB bounded process capture, and
at most two numerical invocations. The original solver is restricted to 1–4
iterations and 0–3 backtracks. Its conservative force-call ceiling includes
baseline, initial optimization evaluation, all trials, and one optional restart;
the maximum is 19. Neither invocation nor resume refreshes the budget.

Address space is not a RAM/RSS limit. Sampling can overshoot the tree threshold.
The process execution timeout has separately bounded cleanup; owner accounting
includes setup, cleanup, and publication and can exceed that timeout. If actual
subtree CPU measurement is unavailable, the full reserved CPU cap is charged.
Unmeasured active/cleanup timing fields remain null.

Public results include model identity, coordinate/energy/raw-force units,
source digests, typed non-retryable errors, budget/census state, and immutable
artifact hashes. Private paths, command arguments, environment, and process
capture are not public artifacts. All outcomes remain `research_only: true`
and `qualified: false`. Installation, native containment, synthetic lifecycle,
real prepared evaluation, scientific comparison, and external-user acceptance
must be reported as distinct evidence.
