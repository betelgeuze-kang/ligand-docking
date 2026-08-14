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
account-owned virtual environment only as an authenticated site-package
inventory. The executable target is the root-owned `/usr/bin/python3.10`
regular file, never an account-owned virtual-environment symlink. CPython must
run with `-I -S -B`, the exact interpreter and native-extension hashes, the
frozen runtime inventory, and a private effective account group.

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

Before any native constructor can run, a root-provisioned static native launcher
at
`/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-preflight-launcher-v1`
starts the root-owned `/usr/bin/python3.10` target through the exact glibc dynamic loader.
The launcher is a direct parent process, is root-owned at mode
`0555`, contains no `PT_DYNAMIC` or `PT_INTERP`, sets dumpability off and
no-new-privileges on, removes inherited descriptors, resets signal state, and
remains alive until the child terminates. The child validates the launcher's
exact parent path/inode, root-controlled directory chain, static ELF structure,
command line, zero capabilities, absent tracer, UID/GID, and stable process
start identity. This outside-the-repository process boundary anchors the exact
preflight digest before any account-owned bootstrap byte can execute.
Before numeric UID/GID zero is treated as host-root authority, the native
launcher, embedded stage 0, and Python preflight each require the exact initial
host user and mount namespaces. The frozen identity maps are
`0 0 4294967295`; the namespace identities are `user:[4026531837]` and
`mnt:[4026531841]`. An unprivileged user namespace or private mount/chroot tree
therefore fails closed before account-owned source is read.
The reviewed exact-host build uses `g++ -std=c++17 -O2 -Wall -Wextra
-Wpedantic -Werror -static -s -Wl,--build-id=none`; its frozen binary SHA-256
is `43fe19fd75f2b9ae37b124004a4b77ff59a7bcad772e53945af64216874c91a5`.
The preflight hashes the actual parent executable and requires that digest in
the activation contract, in addition to checking root ownership and static ELF
structure. The contract separately freezes the SHA-256 of the complete launcher
source, and the static verifier hashes every source byte rather than accepting
selected snippets as a source-to-binary provenance claim.

The launcher clears the inherited
environment, inhibits the loader cache, fixes the library search path, disables
glibc hardware-capability variants, and preloads the exact absolute
`libstdc++`, `libgcc_s`, `libpthread`, `libm`, `libdl`, and `libc` paths required
by the frozen extension. The kernel-maintained `/proc/self/exe` must remain the
exact loader, while `/proc/self/cmdline` must byte-match the complete reviewed
loader option vector, root-owned interpreter target, `-I -S -B`, frozen
stage-0 source, bootstrap source path, and forwarded preflight arguments. The
launcher source embeds the reviewed bootstrap SHA-256 twice: once as a compiled
identity and once in the exact stage-0 literal. A caller cannot select or render
that digest, and there is no caller-created completion token.

The stage-0 source first requires its direct parent executable to be the frozen
root-provisioned launcher, then authenticates the bootstrap through a stable
no-follow read before any bootstrap byte executes, copies those exact bytes into a mode-0400
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

The exact local non-consuming preflight must be launched by the reviewed,
root-provisioned static native launcher. Repository code is not authorized to
install or replace that root-owned trust anchor. Until an independent host
administrator compiles the reviewed source and installs the exact binary at the
frozen path with root ownership and mode `0555`, local preflight execution is
intentionally unavailable and fails closed. The artifact and runtime paths
remain locations for independently re-derived byte identities and cannot carry
science input:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static -s \
  -Wl,--build-id=none \
  native/tools/engine_v2_full_pipeline_cpu_preflight_launcher_v1.cpp \
  -o /independent/staging/engine-v2-preflight-launcher-v1
sha256sum /independent/staging/engine-v2-preflight-launcher-v1
# An independent host administrator verifies both the contract's complete source
# SHA-256 and exact-host binary SHA-256, then installs these exact bytes as
# root:root mode 0555 at the frozen /usr/local/libexec path.
```

Only after that independent provisioning step is the following invocation
supported:

```bash
/usr/local/libexec/betelgeuze-engine-v2-full-pipeline-cpu-preflight-launcher-v1 \
  /exact/repository/tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py -- \
  --artifact-directory /exact/artifact/directory \
  --runtime-root /exact/runtime
```

GitHub Actions is rejected before any repository or native provider is loaded.
The supported command has no preliminary execution of the owner-writable
bootstrap pathname. The root-owned launcher parent, kernel process identity,
and authenticated immutable bootstrap snapshot jointly prove the launcher,
loader, interpreter, and source boundary; no
caller-provided `LD_LIBRARY_PATH`, `LD_PRELOAD`, loader-cache choice, or ROCm
environment survives into the authenticated process.
The local result records immutable-snapshot and descriptor-bound native
initialization, `trusted_root_launcher_parent_validated=true`,
`trusted_root_launcher_source_sha256=<contract digest>`,
`initial_host_namespaces_validated=true`,
`root_owned_interpreter_target_validated=true`,
`exact_loader_process_identity_validated=true`, and
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
