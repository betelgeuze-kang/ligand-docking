# Engine V2 full-pipeline CPU performance v1 activation

This contract freezes a non-consuming preflight boundary for
`engine_v2_full_pipeline_cpu_performance_v1`. It does not activate the exactly-once runner,
does not measure performance, and does not create an
attempt, reservation, molecular result, product action, or claim.

## Exact source foundation

The activation binds the exact merged-main foundation produced by PR #319:

- commit OID `38c16136a1e2cc126517ff9b50a05f06c5795adb`;
- SHA-256 of raw `git cat-file commit` bytes
  `1b478ee3b9737e9d50fc854fb4bde93cbd1efd48015a27df52199a698d17e82e`;
- tree OID `e36d1cf0915350556ac4202e11d6176fabf5e797`;
- SHA-256 of raw `git ls-tree -r --full-tree -z` output
  `69998e9df4740c927568b41e21eb8b94185d4fa3b9dd5fa37d71bcbbd5060579`.

The verifier re-reads those Git objects and separately hashes all twelve
required activation bindings: profile, profile verifier, measurement core,
inactive runner, native consumer, native CPU parity, host preflight, commit,
tree, standard-library import closure, pre-initialization executable closure,
and post-initialization executable-mapping closure. The
profile remains byte-identical at
`385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000`.
The preflight boundary additionally binds its own bootstrap, activation module,
and the exact performance sidecar that host preflight imports.

## Runtime closure

The runtime remains the exact cp310 artifact from main-push run `31785070195`,
attempt `1`, artifact `9213296947`. The non-consuming preflight uses the
account-owned virtual environment and requires CPython `-I -S -B`, the exact
interpreter and native-extension hashes, the frozen runtime inventory, and a
private effective account group.

Before any repository module is compiled, the preflight reads all required
module bytes through stable no-follow descriptors and authenticates their
SHA-256 identities. The same authenticated byte strings are then executed;
preloaded or second-read modules are rejected. Before that import boundary, the
complete activation document is compared recursively against an exact typed
projection, including all keys, runtime/foundation identities, closure
summaries, false authority, and the self-hashed bootstrap. Unknown fields and
Boolean/integer substitutions fail closed. The preflight opens the exact
native extension through a stable no-follow descriptor, authenticates its
bytes, copies them into an anonymous sealed memfd, sets mode `0500`, applies
the complete write/grow/shrink/seal lock set, and closes the owner-writable
source descriptor before native initialization. It loads only that immutable
snapshot through `/proc/self/fd` without creating a docking session, retains
and rechecks its seals, bytes, and metadata, and requires the loaded executable
mapping to match the same device and inode. The loaded submodule exports are
also projected onto the authenticated public package so subsequent canonical
consumer imports resolve the verified entrypoints. The preflight then
re-derives:

- 126 imported standard-library module identities, including 85 file-backed
  source or extension rows with their complete hashes and sizes;
- 79 declared bytecode-cache files with their paths, hashes, and sizes, so
  CPython's readable `.pyc` path cannot diverge from the frozen closure;
- 20 pre-initialization executable mappings before native initialization;
- 21 file-backed executable mappings, including the CPython executable, native
  sealed native-extension snapshot, CPython extension modules, C/C++
  runtimes, loader, and transitive system libraries;
- the exact `[vdso]` and `[vsyscall]` virtual executable mapping set.

The mappings come from the isolated process itself rather than `ldd`. Every
file-backed executable mapping is included regardless of filename or suffix,
including paths containing spaces. The map device/inode must equal the file
descriptor identity used for hashing. Ordinary deleted mappings and unexpected
anonymous executable mappings fail closed; the sole deleted-path exception is
the exact sealed memfd whose retained descriptor, zero link count, mode,
device/inode, bytes, and kernel seals are independently verified. No
caller-supplied expected digest is accepted. Added, missing, moved, or changed
module/mapping rows fail closed.

Before any native constructor can run, the approved launcher starts the bound
runtime through the exact glibc dynamic loader. It clears the inherited
environment, inhibits the loader cache, fixes the library search path, disables
glibc hardware-capability variants, and preloads the exact absolute
`libstdc++`, `libgcc_s`, `libpthread`, `libm`, `libdl`, and `libc` paths required
by the frozen extension. The kernel-maintained `/proc/self/exe` must remain the
exact loader, while `/proc/self/cmdline` must byte-match the complete reviewed
loader option vector, runtime interpreter, `-I -S -B`, frozen stage-0 source,
bootstrap source path, frozen source SHA-256, and user arguments. There is no
caller-created completion token.

The stage-0 source authenticates the bootstrap through a stable no-follow read
before any bootstrap byte executes, copies those exact bytes into a mode-0400
memfd, applies all four write/grow/shrink/seal locks, and executes only that
authenticated immutable bootstrap snapshot. Direct pathname execution of the
bootstrap is unsupported and fails closed. The resulting 20-row executable
closure is fully hashed and compared with its frozen manifest before native
initialization.
After initialization, the verifier requires the pre/post mapping delta to be
exactly one row: the authenticated sealed native memfd. A newly discovered,
late-loaded, missing, or changed dependency rejects activation.
Any post-import rejection removes both the native public package and submodule
from `sys.modules` before control can return to a programmatic caller.

## Non-consuming preflight

Static contract verification is safe in CI and performs no native import:

```bash
python3 tools/verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py
```

The exact local non-consuming preflight must be launched by the reviewed
external stage-0 launcher. The following is the required argument shape;
`$FROZEN_STAGE0_SOURCE` is the exact ASCII source whose SHA-256 is in the
activation contract and whose literal code embeds the reviewed bootstrap
SHA-256. The artifact and runtime paths remain locations for independently
re-derived byte identities and cannot carry science input:

```bash
env -i CUDA_VISIBLE_DEVICES= HIP_VISIBLE_DEVICES= ROCR_VISIBLE_DEVICES= \
  LC_ALL=C PATH=/usr/bin:/bin \
  /usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 \
  --inhibit-cache \
  --library-path /usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu \
  --glibc-hwcaps-mask '' \
  --preload /exact/colon-separated/native/dependency/paths \
  --argv0 /exact/runtime/bin/python \
  /exact/runtime/bin/python -I -S -B -c "$FROZEN_STAGE0_SOURCE" \
  /exact/repository/tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py \
  --artifact-directory /exact/artifact/directory \
  --runtime-root /exact/runtime
```

GitHub Actions is rejected before any repository or native provider is loaded.
The supported command has no preliminary execution of the owner-writable
bootstrap pathname. Kernel process identity and the authenticated immutable
bootstrap snapshot jointly prove the loader and source boundary; no
caller-provided `LD_LIBRARY_PATH`, `LD_PRELOAD`, loader-cache choice, or ROCm
environment survives into the authenticated process.
The local result records immutable-snapshot and descriptor-bound native
initialization, `exact_loader_process_identity_validated=true`,
`immutable_bootstrap_snapshot_validated=true`, verified public package exports,
host preflight evidence, and explicit false fields for measurement,
qualification consumption, reservation, molecular execution, public benchmark,
HIP device execution, and product action.

A successful preflight only establishes that the reviewed activation bytes can
be loaded on the pinned host. A later PR must add and bind a transactional
account-scoped exactly-once runner. That later runner must create its attempt
before its execution-time preflight and persist an artifact plus terminal
decision before returning. This activation contract grants that runner no live
execution capability and is not performance evidence.

## Authority boundary

Every execution, reservation, Stage 0, Fresh-128, product, benchmark,
scientific-claim, and HIP authority field remains false. The separate external
reservation verifier and its four blockers are unchanged. This work does not
perform or authorize the historical nine-case A/B, D1/D2 molecular execution,
Fresh-128, a public benchmark, product mutation, customer pose emission, or a
GPU acceleration claim.
