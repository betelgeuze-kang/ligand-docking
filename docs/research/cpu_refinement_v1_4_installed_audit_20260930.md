# Prospective failure diagnostics: software and installed audit evidence

The new explicit `cpu_refinement_v1_4` path retains typed failure facts before
exception reduction and connects runner, durable journal, replay/inspection,
prepared numerical API and CLI. It reuses the 1.3 numerical kernel and budgets;
1.2/1.3, the native v4 wrapper and frozen SRO campaign remain unchanged.

## Recorded scopes

- **45 synthetic/mock tests pass** (5.60 seconds), plus Ruff for the six new
  modules and their test. Normal/resumed SD and L-BFGS accepted state, history
  and work match 1.3 in the tested toy cases. Failure stages, exact message
  fingerprints, malformed retained evidence, frame/input/binding mutations,
  private output and unknown pending reservations are covered. Independent
  static review found no remaining material issue.
- The source wheel contains all **531 staged owned Python/data members**, including
  the six new modules, with matching bytes. Outside the source checkout, **183
  imported owned modules** originate from the isolated install target. The
  installed audit's **238 implementation hashes** match both packaged bytes and
  current source. CLI help and raw JSON audit pass; tampered raw input is rejected
  with exit 2 and a fingerprint-only blocked envelope.
- The first isolated probe could not import torch because `-I` excluded its user
  site. Its failed log/command remain. The corrected probe explicitly adds the
  existing dependency site while reusing the same wheel/target, without rebuilding
  or installing dependencies. This establishes source-wheel inclusion and an
  independent-cwd CLI audit, not a clean dependency installation.

The installed probe uses five synthetic JSON role markers, intentionally not
canonical molecular models. It exercises raw-file identity and JSON format audit
only, with zero graph, force and score dispatches. Installed numerical execution,
optimizer checkpoint continuation and actual target validation are not covered by
this probe. The mocked prepared API tests do not substitute for those results.

The existing installed native v4 wrapper still uses 1.3. A future explicitly
reviewed request must opt into 1.4 to collect its new diagnostics. Message hashes
cannot reconstruct the missing R2 case 03 cause. The original experiment remains
completed 2 / failed 1 / unstarted 1 and recovery **0/4**. No original threshold,
source role, scientific admission or protected evaluation is changed.

## Retained evidence

Software QA is retained at:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-cpu-refinement-v1-4-failure-diagnostics-software-qa-20260930-6347ca2e`.
All 254 receipt artifact references were verified by raw SHA and byte length. The
238 implementation source pins and 41 existing v1.2/v1.3/SRO source pins remained
unchanged during software validation.

Installed audit is retained at:
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-v14-installed-audit-explicit-dependencies-20260930-m0w3eddj`.
Its receipt links the original build, install and failed probe at
`engine-v2-v14-installed-audit-smoke-20260930-p3sb7nw8`. Both attempts remain;
current source hashes are identical before and after the successful audit.

Evidence: [software and installed audit record](../evidence/cpu_refinement_v1_4_installed_audit_20260930_v1.json).
API/contract detail: [prospective failure diagnostics](cpu_refinement_failure_diagnostics_20260930.md).

Actual independent energy/force validation, endpoint admission, candidate-ordering
benefit, HIP parity and service readiness remain **NOT_QUALIFIED**. These scopes
advance the five-goal objective without completing it.
