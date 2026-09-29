# Next implementation: versioned Cartesian refinement and durable restart

The completed SRO development comparison supports implementing an explicit
Cartesian SD/L-BFGS product path. This document records a source-reviewed design,
not an implemented API or a new validated solver. Keep the existing projected
1.2 solver, request/report/checkpoint identities and default routing unchanged.

The first path should cover the unconstrained, binary64 CPU, nonperiodic
fixed-receptor model used by the successful experiment. Reject unsupported
constraints before numerical work, including constraints already satisfied by
the starting structure. Do not drop terms, substitute projected force for raw
force, or silently convert old requests/checkpoints.

## Complete implementation boundary

1. Define new request, algorithm, plan, work, checkpoint and result identities.
   Separate pose-generation budget from accepted-step and explicit objective
   budgets: the old docking step limit is 256, whereas the completed SD arm
   accepted 262 steps. Count initial, rejected and failed objective attempts.
2. Share one objective boundary between Cartesian SD and L-BFGS. Preserve the
   demonstrated capped displacement, Armijo rule, ordered history, curvature
   threshold and restart semantics. Keep the corrected evaluator and original
   registered coordinates/parameters, with the complete new source scope pinned.
3. Persist trial intent, returned arrays and committed solver transitions.
   Checkpoints include energy/components/full forces, ordered curvature pairs,
   line-search state, consumed budgets and journal prefix. Reconstruct curvature
   pairs from saved coordinate/force transitions and verify the direction;
   resealing a hash must not make an altered history valid.
4. Connect the new solver through refinement, run/verify/resume, installed
   adapter and native-comparison version dispatch. Keep source/charge/stereo
   admission, full candidate/failure denominators, unchanged selection checks
   and baseline fallback. An external result file is not a product checkpoint.

Cooperative pause occurs only at a committed transition. A finished trial whose
checkpoint publication was interrupted can be recovered by replaying recorded
arithmetic. An intent without a returned result retains reserved budget and
unknown work; the first version should explicitly reject automatic continuation
from that uncertain state. Never reset the candidate allowance on restart.

Continuation verification can require an additional force evaluation. Declare
the optimizer objective ceiling and a finite restart-verification allowance
separately, reserve their combined physical-force ceiling, and report both.
The same optimizer trajectory and the same total actual invocation count are
different comparisons. If the total force ceiling must remain exactly 417,
verification consumes it and may prevent reaching the uninterrupted endpoint.
Completed-result reuse must still perform zero new force/score calls.

Completion requires independent quadratic/direction checks, exact logical
pause/resume replay, rejected-trial and crash recovery boundaries, resealed
history/full-force/budget mutation rejection, installed API execution and
unchanged legacy behavior. The real SRO numerical result must then be reproduced
through the new installed product path under a separately fixed protocol.
Do not infer physical, affinity, pose-recovery, HIP or service qualification.

[Source-line review and evidence](../evidence/cartesian_refinement_integration_design_v1.json)
