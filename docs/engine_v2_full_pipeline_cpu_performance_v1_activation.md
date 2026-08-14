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

The verifier re-reads those Git objects and separately hashes all eleven
required activation bindings: profile, profile verifier, measurement core,
inactive runner, native consumer, native CPU parity, host preflight, commit,
tree, standard-library import closure, and dynamic-library closure. The
profile remains byte-identical at
`385fb713cca8f39353f138115749abdfc9768b02222e13111a418360be30a000`.

## Runtime closure

The runtime remains the exact cp310 artifact from main-push run `31785070195`,
attempt `1`, artifact `9213296947`. The non-consuming preflight uses the
account-owned virtual environment and requires CPython `-I -S -B`, the exact
interpreter and native-extension hashes, the frozen runtime inventory, and a
private effective account group.

After all required repository modules are loaded from bounded source bytes, the
preflight initializes the exact native extension without creating a docking
session. It then re-derives:

- 125 imported standard-library module identities, including 84 file-backed
  rows with their complete hashes and sizes;
- 20 actually mapped shared libraries, including the native extension,
  CPython extension modules, C/C++ runtimes, loader, and transitive system
  libraries.

The mappings come from the isolated process itself rather than `ldd`, and no
caller-supplied expected digest is accepted. Added, missing, moved, or changed
module/library rows fail closed.

## Non-consuming preflight

Static contract verification is safe in CI and performs no native import:

```bash
python3 tools/verify_engine_v2_full_pipeline_cpu_performance_v1_activation.py
```

The exact local non-consuming preflight must be launched with the bound
runtime interpreter. The artifact and runtime paths are accepted only as
locations for independently re-derived byte identities; they cannot carry
science input:

```bash
/exact/runtime/bin/python -I -S -B \
  tools/preflight_engine_v2_full_pipeline_cpu_performance_v1_activation.py \
  --artifact-directory /exact/artifact/directory \
  --runtime-root /exact/runtime
```

GitHub Actions is rejected before any repository or native provider is loaded.
The local result records import and native-initialization evidence, host
preflight evidence, and explicit false fields for measurement, qualification
consumption, reservation, molecular execution, public benchmark, HIP device
execution, and product action.

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
