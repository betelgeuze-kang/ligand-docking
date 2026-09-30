# Prepared cross-report rehash: bounded CPU audit (2026-09-29)

The prepared cross-interaction adapter already validates and hashes each
canonical source system. Its result builder used to hash both systems a second
time while constructing their self-verifying report documents. It now reuses
the validation digests for those documents. Both existing pre/post
`AllAtomSystem.assert_integrity` boundaries, coordinate hashes, source checks,
and numerical evaluation remain in place.

The before source was commit `939dd23716af46480874eac28da7b7e47602c395`
in a read-only Git archive; the after source was the modified worktree. Six
fresh, sequential CPU processes alternated before/after three times against
the same development request, SHA-256
`5e9d20fa9e0380d7eb6bbd126aca2d8c28845edfad5c09e68e6835d97321fdf9`.
Each used one OMP/MKL/OpenBLAS thread, disabled GPU visibility, compact JSON
output to a new path, and `/usr/bin/time -v` for full-process cost. The
request and raw run reports are retained outside the repository in the local
audit directory; this is a measured development case, not a distributable
benchmark dataset.

| Full-process observation | Before (3 runs) | After (3 runs) |
| --- | ---: | ---: |
| Wall time, seconds | 15.03, 15.27, 15.15 | 14.30, 14.28, 14.34 |
| Median wall time, seconds | 15.15 | 14.30 |
| Median user + system CPU, seconds | 15.12 | 14.26 |
| Peak RSS, KiB | 693628, 692488, 692996 | 692736, 691380, 691768 |

All six reports had exactly the same deterministic JSON content after
excluding only wall/CPU time observations, observed peak RSS, and the
intentionally changed adapter-source SHA-256. In particular, energies, forces,
source systems, pair accounting, denominators, and numeric statuses matched
exactly. The full audit inventory is at
`/mnt/193005ba-8531-4d0b-87c2-43c01ee2ce25/ligand_heavy_runs/engine-v2-current-cpu-baseline-ckBNbX8O/paired-before-after-audit.json`.

This is a roughly 0.85-second (5.6%) median reduction for one local CPU
request. It does not establish a general throughput improvement, molecular
accuracy, physical validity, or production qualification.
