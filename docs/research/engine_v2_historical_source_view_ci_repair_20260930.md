# Engine V2 historical source view — CI failure repair

Commit `3e5c18f5182782c165e4ba828e6d091b33f68183` fails the same historical
source-view check on Python 3.10, 3.11 and 3.12. The actual hosted traceback is
`unreviewed live Python source drift: betelgeuze_engine_v2/physics/reference_parameter_applicability.py`.
The canonical test suite is not reached, so its missing `engine-v2-main.log`
artifact is a secondary symptom. Do not infer a molecular failure from that upload error.

Commit `47806adee` refreshed two SHA strings in the H5 applicability review:
the reviewed canonical serializer and the reviewed applicability record. Reverting
only those two strings reproduces the complete historical source bytes exactly.
The 187 Python source paths are unchanged. Relative to the historical source,
there are the six already reviewed deltas and this one omitted metadata delta.

The repair changes two test files. The test-only historical view names the exact
current applicability source SHA `f8ce56bb37c4f8dd369adec91e8835f503acb2f0016df366ad2a41a917f88296`
and current 187-file manifest `4977c5bc7c3e0a424203aeccd7fb2a370fbd4cfab1e1ff2f9e7b2a74ae80dc19`.
The existing mutation test now also changes the newly named source and requires rejection.

The historical fixture, manifest and protocol seals remain unchanged. Runtime
sources are byte-identical to the failed head. All current bytes, the exact path
set and regular-file checks remain required. The original frozen protocol still
rejects current sources; only its historical metadata view verifies. This does
not execute historical code or authorize current code under that old protocol.

Local validation passes the actual source-view CLI, **43 protocol tests with zero
failures/errors/skips**, Ruff for the two changed test files and diff checks.
Source and test hashes are identical before and after validation. This separate
suite is not added to the earlier 199-pass/31-subtest result. Its full logs and
JUnit are retained alongside all three hosted failures and the local pre-repair
failure. Hosted CI for the subsequent commit must be evaluated separately.

An independent readonly reviewer reproduced the raw hashes, exact two-string
equivalence and 187-path manifest. No campaign restart, molecular computation,
scientific threshold change or historical reseal is part of this repair.
The [terminal SRO result](sro_operational_guard_repair_terminal_20260930.md) remains
two completed cases, one failure, one unstarted case and recovery **0/4**.
The earlier 58 frozen-source lint errors remain unresolved.

Full source pins, validation and durable archive references are in the
[evidence record](../evidence/engine_v2_historical_source_view_ci_repair_20260930_v1.json).
