# Four-arm prepared comparison readiness diagnostic

`tools.analysis.prepared_comparison_readiness` reads an existing four-arm rank
`ready.json` receipt and its frozen protocol/result. It runs no comparison worker,
prediction, assay-label evaluation, pose generation, or preparation. Its own
module lives outside `tools/product/*.py`, so this module alone does not
change the comparison runner's frozen tool-file list. This PR also changes the
prepared GROMACS loader, which is part of the frozen runtime binding. A
`ready.json` made at an older commit cannot pass this command's exact-runtime
validation from the new checkout; keep its matching historical runtime for
reproduction. The diagnostic does not relax that check.

The command verifies the ready, plan, frozen input, comparison, current input
and runtime bytes, and each committed arm summary before reporting. It emits
the original requested pool, candidates with a non-null prepared request,
each arm's evaluated/scored, unsupported, failed and unprocessed IDs, and the
four-arm common scored set. A non-null request establishes presence only; it
does not validate preparation quality or assay/chemical-state correspondence.

Each arm's reported process wall time, available process CPU/peak RSS, and outer
engine-call count come from its committed completion and worker observations.
Committed row cost sums are separately labeled subsets of process cost. A
terminated worker may have no CPU or call observation; those values remain
`null`. For the D3 backend, nested force and score call sums include only
candidate reports that actually contain `d3_summary.work`; missing candidate
work is counted as unobserved when the outer call count exists. Rigid cross
backend force work is not reported by this diagnostic. No nested duration is
added to worker wall time.

Create a new receipt file in an existing output directory:

```bash
python -m tools.analysis.prepared_comparison_readiness report \
  --ready /absolute/path/to/rank-run/ready.json \
  --ready-sha256 SHA256_OF_READY_FILE \
  --output /absolute/path/to/new-readiness.json
```

The command prints the new file path and SHA-256 reference. Verify it against
the current original evidence with:

```bash
python -m tools.analysis.prepared_comparison_readiness verify \
  --report /absolute/path/to/new-readiness.json \
  --report-sha256 SHA256_OF_READINESS_FILE
```

The output is exclusive and does not overwrite existing files. Its payload is
hash-sealed and bound to the original ready/plan/frozen/comparison references,
protocol binding, diagnostic code bytes, and an aggregate byte hash of the
committed row and worker-observation files in each arm. Verification rebuilds
the report from the original evidence; changed sources, committed rows or code
fail closed. A new receipt only records the bytes present when it is created;
it is not an independent attestation of their earlier history.

This is a software coverage/cost diagnostic. Its `same_prepared_assay_state_verified`,
`heldout_blindness_verified`, `scientifically_validated` and `ai_advantage_claimed`
fields are always false; the eligible source-state join count and upstream costs
remain unknown. Equal budget caps do not establish equal consumed CPU work or
scientific value. The common scored set is an execution intersection, not an
eligible experimental cohort.
