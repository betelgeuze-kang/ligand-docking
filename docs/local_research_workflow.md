# Local research workflow (development, Linux CPU)

This consumer composes the existing prepared rigid-pose completion journal (#517)
with the disk-backed streaming assay consumer (#516). It does not merge their
scientific meanings. Supplied rigid poses are evaluated; no new docking search,
MD, force-model training, ranking change or execution qualification is created.

Use the live prepared-development stack. The streaming implementation is reused
from #516 with its already-bounded list call and optional context helpers made compatible
with both live selector APIs. The owner still determines endpoint semantics;
errors raised by a helper body are not retried under another signature. No registry, frozen weights or V2 source is changed.

## Request

Create a JSON object with exactly these fields:

- `schema_version`: `local_research_workflow_request_v1`
- `backend`: `cpu` (explicit `hip_safe`/`hip_fast` returns blocked; no fallback)
- `prepared_request`: an existing `prepared_rigid_pose_cross_request_v1` object
- `assay_shadow`: `null`, or an object with absolute `ligand_csv`, `checkpoint`,
  exact byte `input_sha256`, registered `checkpoint_sha256` and integer
  `chunk_size` in 1..4096.

The assay catalogue is not assumed to identify the prepared physical ligand or
assay construct. Predictions never alter the pose request, score or rank. A bad
model or unsupported catalogue row preserves independent physical results and
returns a partial result (exit 2), not a successful AI qualification.

```sh
python -m betelgeuze_product.local_research_workflow --diagnose-only
python -m betelgeuze_product.local_research_workflow --diagnose-only --probe-rocm
python -m betelgeuze_product.local_research_workflow --request request.json --run-dir /private/new-run
python -m betelgeuze_product.local_research_workflow --request request.json --run-dir /private/new-run --resume
```

Run storage must be a new private directory for the first invocation. Resumes
check the request and implementation, then the existing physical journal checks
its input files, numerical environment and transitive source binding. Each
attempt gets a separate folder: completed/failed physical rows are restored,
uncommitted rows are recomputed, assay prediction is rerun. A recorded physical
failure is not retried under changed inputs. Start a new run after changing
models, input files, transforms, numerical configuration, environment or source.

The optional ROCm probe runs a tiny Torch HIP tensor calculation only when the
installed Torch reports a HIP build and an available device. A successful probe
is NOT evidence that the native fixed64 `hip_safe`/`hip_fast` provider is built,
qualified or used by prepared cross evaluation. No device is emulated; absence is
reported. This environment-independent diagnostic never enables CPU fallback.

Each attempt preserves full `physics.json`, optional streamed `assay-shadow.json`,
a small `report.json` and escaped offline `report.html`. Artifact byte hashes are
recorded. All output is private local development evidence, not authenticated
external approval. Process RSS is a lifetime high-water value, not stage memory
or VRAM. Timings declare their scope and exclude process startup/final summary
writing. Previous attempts remain separate; costs are not a single end-to-end
performance benchmark. Disk use scales with results and checkpoint state.

Tests use fresh synthetic molecules and synthetic checkpoint registration only
inside test fixtures. Hosted CPU CI checks real calculations, interrupted and
completed resume, separate shadow failures, input changes and unavailable GPU
handling. Actual AMD/native provider and MD qualification remain separate work.

## Guarantees and explicit limits

The standalone CLI lives in `betelgeuze_product`, whose initializer is lightweight.
Metadata-only diagnostics do not import the engine, Torch, NumPy or RDKit. The
physics stage loads the owning calculation code only when explicitly requested.
All writes are anchored to the open private run directory: renaming/replacing its
external path during execution does not redirect results. A persisted physics
intent prevents a deleted earlier journal from silently becoming a new run.
An incomplete journal initialization fails closed and requires a new run.

The initial hosted implementation ran 151 tests successfully and failed two new
checks: mismatched helper signatures between the live selector branches, and a
comparison that incorrectly required independently measured runtimes to match.
The adapter now chooses the declared helper signature without masking body errors;
regressions retain all physical values/provenance exactly and compare time fields
only as nonnegative observations with the same stated scope. Full-row equality
is still required when restoring the SAME persisted result.

The HTML report has an escaped small table of supplied poses and their separate
cross energies, with links to complete local JSON artifacts. It contains no script,
external assets, uploads or merged assay/physical score. Do not serve private run
folders publicly. Directory ownership/hashes protect local integrity, not an
independent scientific signature or hostile same-user modifications.
