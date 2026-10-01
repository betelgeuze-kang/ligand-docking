# Candidate comparison resume (CPU research development)

The existing `run` and `verify` commands retain their existing formats.
The explicit candidate-journal workflow accepts the same prepared 1.2 or
fixed-receptor request and supports both existing comparison budget modes:

```bash
python -m betelgeuze_product.cpu_refinement_v1_2 run-resumable request.json --output new-run --stop-after 2
python -m betelgeuze_product.cpu_refinement_v1_2 run-resumable request.json --output new-run --resume
python -m betelgeuze_product.cpu_refinement_v1_2 verify-resumable new-run
```

`--stop-after` is an absolute committed candidate count across baseline then
refined arms. It grants no new budget. Resume requires the original request,
source inputs, implementation and runtime. Original source checkpoints are not
migrated. Completed results return their retained report without recomputation
or overwriting. Verification is read-only and works without source input files.

Candidate records retain original numerical work. The summary distinguishes
reused historical score/force calls from new calls and explicitly counts
interrupted attempts whose pre-commit cost is unknown. Startup, verification,
validity checks and publication overhead are outside these candidate call totals;
they must not be interpreted as whole-run cost or elapsed-time equivalence.

The report contains the retained request binding, implementation manifest and
portable candidate summary. Verification cross-checks components, coordinates,
pose observations, budgets, failure rows, costs and selection. It does not rerun
physics, attest historical execution, or provide a cryptographic signature.

An interruption after report publication but before its completion marker can
finish publication without repeating candidate computation. With a matching retained
request, report/complete `.partial` files are preserved under content-hashed
`interrupted-*` names before publication is retried. Archive bytes are checked on
each resume; unknown files, symlinks, corrupt archives and more than 64 archives
are rejected. Initial request/binding/intent publication still fails closed:
these do not establish enough identity to infer the intended run. Keep such
files for diagnosis rather than deleting or editing them to force resume.

Source CLI tests are development evidence. Installed-wheel execution, supported
Python CI, full overhead accounting and scientific preparation/assay qualification
remain separate work. No scientific, GPU, customer or release qualification is
granted by this workflow.
