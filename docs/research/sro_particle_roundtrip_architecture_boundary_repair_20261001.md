# SRO particle roundtrip diagnostic: architecture boundary repair

Hosted CI for parent HEAD `22f52e90aba43e945d14be69332cada318a75680`
reported one failure in `offline-contract-and-boundary`, job `110008732064`, run
`36750835357`. The complete job log identifies the architecture step's first
actionable error at the diagnostic source's line 102:
`product_dynamic_code_execution_unresolved: exec/eval target is not statically provable`.
This is a product dependency-boundary failure. It is not a molecular numerical
failure or independent scientific qualification.

The diagnostic was located under `tools/research`, which is part of the product
tool roots and Docker's `COPY tools` closure. It loads a separately hash-verified
frozen oracle through dynamic execution. The repair moves the same 40372 source
bytes to `benchmarks/oracles/sro_particle_roundtrip_diagnostic_v1.py`; SHA-256
remains `f9d860e150542596457e546802ef8594365c112c424f8a1abf8e82a1734e9c3a`.
Only the current test fallback and the current CI path/lint target change to the
new route. The architecture checker, allowlists, Docker rules, package rules and
all source/role/authorization guards remain unchanged.

This repair does not repoint historical executed plans, source pins or evidence
references. Their original copies remain valid evidence of their own runs. The
existing plan document and frozen endpoint oracle source are pinned before and
after the repair. No real numerical rerun, preparation, original molecular body,
protected evaluation read, tolerance change or campaign resume is performed.

The new integration regressions use the actual diagnostic source bytes and
unchanged repository packaging metadata in temporary fixtures. The same source
still fails when placed in the former product root; it is excluded from product
roots in the benchmark route. A product module importing the relocated oracle
is rejected. Actual Docker inclusion rules exclude the new file, while mutations
that reinclude benchmarks, copy them into Docker or remove the wheel exclusion
are detected by the unchanged packaging guard. The workflow registers only the
two pinned setup actions, pinned pytest/Ruff installation, isolated lint and
the mock test command; it registers zero uploads or real diagnostic execution.

Exact failure evidence is preserved separately at:

`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-pr566-ci-22f52e90-20261001-v1`

Repair source snapshots, raw commands/logs and the final validation receipt are
preserved at:

`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-sro-particle-roundtrip-architecture-repair-20261001-v1`

Completed local QA:

| Check | Result | Subprocess wall seconds |
| --- | --- | ---: |
| Isolated Ruff, only diagnostic source and particle test | PASS | 0.026728029999503633 |
| Particle and workflow trust-boundary tests | 41 passed in 11.57s | 11.712728157001038 |
| Exact repository architecture CLI guard | PASS | 127.23845926600006 |
| Existing architecture regression suite | 108 passed in 119.16s | 144.5528099969997 |
| Owned diff whitespace check | PASS | 0.008804901999610593 |

These 149 checks and scan times are static/mock software evidence. They are not
target force/energy observations, a computational speedup or a hosted pass on a
future repaired commit. The retained plan document SHA remains
`d3cdfdc5d89ecec219d73f2737f0a4709134e028be2068ea57dc67bf356d38c6`;
the frozen endpoint oracle SHA remains
`9a1598e8f94e98ff691a435e8f6a43835a9408c58e9da07051fdd7a56e90f1e1`.
Unchanged architecture and packaging controls are independently pinned in the
before/after manifests.

The adjacent `docs/evidence/sro_particle_roundtrip_architecture_boundary_repair_20261001_v1.json`
records the completed local QA, source pins and boundary. Local static/mock QA
does not claim a hosted pass at a later commit, a numerical cause, or scientific
qualification.
