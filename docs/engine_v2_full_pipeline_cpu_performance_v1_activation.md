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

## Trusted execution blocker

The reviewed root-launcher design is not an operational trust anchor. Namespace
identity read through `/proc` remains inside the caller's mutable mount tree,
and an ordinary non-setuid `execve` can restore child dumpability before Python
validation. Neither signal is permitted to grant runtime authority.

The native launcher artifact is therefore a non-operational fail-closed stub.
It contains no `fork`, `execve`, `ptrace`, or `/proc` path and always exits 125.
Its complete source and reproducible static binary remain SHA-256-bound so that
any accidental execution path fails the static verifier. The static verifier
hashes every source byte. Installation and runtime launch are both unauthorized.

The Python preflight independently freezes
`_TRUSTED_INITIAL_NAMESPACE_EXEC_SUPERVISOR_OPERATIONAL = False`. After the
earlier GitHub Actions rejection, this gate fails before any namespace, process,
repository, runtime, or native-provider path is read. The embedded stage-0,
exact loader vector, immutable bootstrap, and closure logic remain reviewable
future constraints, but they are unreachable in this activation.

A separate activation PR must supply an independently provisioned supervisor
that provides all of the following before this gate may change:

- mount-independent initial user/mount namespace attestation;
- a signed or kernel-attested handoff binding the exact launcher, preflight,
  loader, interpreter, arguments, and environment;
- trace exclusion that remains continuous across every `exec` transition;
- fail-closed revocation and lifecycle evidence outside caller-owned paths.

Path-based `/proc` checks may remain defense in depth after that handoff, but
the contract explicitly records that they are not authoritative evidence.

## Non-consuming preflight

Static contract verification is safe in CI and performs no native import:

```bash
python3 tools/verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py
```

The launcher stub may be built only to reproduce its frozen binary identity. It
must not be installed or used to launch the preflight:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static -s \
  -Wl,--build-id=none \
  native/tools/engine_v2_full_pipeline_cpu_preflight_launcher_v1.cpp \
  -o /independent/staging/engine-v2-preflight-launcher-v1
sha256sum /independent/staging/engine-v2-preflight-launcher-v1
# Executing this audit artifact exits 125; installation is unauthorized.
```

GitHub Actions is rejected before any repository or native provider is loaded.
Every non-GitHub invocation that reaches the script's runtime gate then fails
before `/proc` evidence or any additional repository, runtime, native, or
molecular input is read. The account-controlled preflight file has necessarily
already been loaded and cannot establish its own trust boundary. Consequently
this PR can produce no successful local preflight receipt. A later supervisor PR
must first close the two execution-boundary blockers; a still later runner PR
must bind a transactional account-scoped exactly-once attempt. This activation
contract grants neither capability and is not performance evidence.

## Authority boundary

Every execution, reservation, Stage 0, Fresh-128, product, benchmark,
scientific-claim, and HIP authority field remains false. The separate external
reservation verifier and its four blockers are unchanged. This work does not
perform or authorize the historical nine-case A/B, D1/D2 molecular execution,
Fresh-128, a public benchmark, product mutation, customer pose emission, or a
GPU acceleration claim.
