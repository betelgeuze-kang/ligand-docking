# Engine V2 generated state bundle v1

The repository no longer commits one combined, dated current-state snapshot.
That design mixed implementation facts with manual authority and became stale
whenever implementation changed outside its path-scoped workflow.

`tools/generate_engine_v2_state_bundle_v1.py` now derives three separate JSON
documents for the exact checked-out commit and tree:

- `engine_v2_implementation_state_v1.json` inventories package versions,
  public ABIs, the 512-to-64 sampler, ScorerV1, the fixed64 pipeline, backend
  build surfaces, comparator adapters, and D1 repository output-path presence;
- `engine_v2_authority_state_v1.json` is the validated projection of the
  manually reviewed fail-closed authority source;
- `engine_v2_release_manifest_v1.json` binds the other two documents and
  remains an unreleased source snapshot with no artifacts.

The implementation document is generated rather than committed because a
tracked file cannot contain the commit and tree that include itself without a
self-reference. The `ci-engine-v2-current-state` workflow runs on every push to
`main` and uploads the exact-SHA bundle as a 30-day workflow artifact.

## Authority boundary

The manual source is `config/engine_v2_authority_state_v1.json`. Version 1
requires every execution and claim field to remain exactly `false`, preserves
the consumed non-authoritative CPU-v7 guard, and fixes the current operational
blockers and unresolved-decision count. A promotion requires a reviewed
successor schema; changing implementation files or generating this bundle can
never grant authority.

The generator cross-checks the authority source against the capability ledger,
Stage 0 status, D1 development profile, CPU-v7 result, and external-reservation
operations decision. It performs no molecular, reservation, benchmark,
Fresh-128, HIP-device, supervisor, or qualification execution.

## Version interpretation

The Python distribution and native extension are independently versioned
surfaces. The generated inventory records both values and the Python package's
exact native dependency requirement; it does not infer that different version
numbers are a mismatch or a release.

## Local generation

From a clean checkout:

```bash
python tools/generate_engine_v2_state_bundle_v1.py \
  --output-dir /tmp/engine-v2-state-bundle
```

CI may pass both `--source-commit` and `--source-tree`; the generator verifies
that they equal a completely clean checkout's `HEAD` and `HEAD^{tree}`. Verified
generation also requires the running script to resolve to the repository's
tracked generator without symlinked repository path components and compares
every consumed worktree file with its exact `HEAD` blob. The Rust CPU backend
inventory recursively follows repository-local native bridge includes and
Cargo path dependencies and literal Rust file inputs. It validates the current
supported declarative form of the Cargo manifests, lockfile, Cargo command,
CMake source globs and dependencies, and native include-search roots; it is not
a general Cargo, CMake, Rust, or C++ semantic parser. Unsupported target
indirection, non-literal Rust file inputs, C++ raw strings, and macro-expanded
native includes fail closed. The Rust backend record is a source-and-build-
surface declaration, not linked-binary provenance: this generator does not
execute CMake, Cargo, or a linker and records
`binary_provenance_evaluated: false`. Repository Cargo configuration and
source inputs outside the workflow-covered `rust/`, `native/src/`, and
`include/` boundaries are rejected. CI exercises the minimum Python 3.10 path
with `tomli==2.2.1`; Python 3.11 and later use the standard-library `tomllib`.
Generated documents are written outside the checkout so a second clean
generation can be compared. The output directory must not already exist, and
repeated generation from the same source identity is byte-exact.
