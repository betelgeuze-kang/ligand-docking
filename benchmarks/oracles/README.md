# External oracle benchmark pack

This tree is the only source boundary allowed to import or execute OpenMM,
GROMACS, AutoDock Vina, or GNINA. It is validation infrastructure, never a
product dependency or customer execution path.

Every adapter accepts already-prepared, SHA-256-bound inputs; uses explicit
canonical units, seeds, thread counts, and argv; preserves engine identity and
native score semantics; and fails closed on missing binaries, timeouts,
nonzero exits, non-finite output, or hash drift. Normalized results always keep
all product and scientific-claim flags false. Vina affinity and GNINA CNN
scores are deliberately distinct fields and must not be compared as if they
were one physical observable.

The repository architecture check is:

```console
python3 tools/check_external_oracle_architecture.py --root .
```

Offline fixtures and fake-executable tests do not establish scientific
parity. Live rows additionally require pinned engine versions/binary hashes
and common prepared inputs. External-engine and model redistribution remains
subject to each upstream license.

## Linux execution containment

Provenance-bearing subprocesses run from pinned executable snapshots inside
private user, PID, mount, network, IPC, and UTS namespaces. Namespace PID 1 is
a pinned subreaper, so successful, failed, timed-out, `setsid`, and
double-forked solver descendants are killed and reaped before a result can be
returned. A Landlock ABI 3 write allowlist confines content mutations to a
private scratch directory and the adapter's explicit output directory;
seccomp additionally denies filesystem-metadata mutation, namespace escape,
cross-process write/inspection, and networking. `cwd`, `HOME`, temporary, and
XDG paths all point at the private scratch directory. Conservative per-process
address-space, descriptor, file-size, core-dump, queued-signal, and CPU limits,
plus a process-count ceiling, provide finite bounds when no delegated cgroup is
available.

The real execution path therefore requires Linux with unprivileged user
namespaces, util-linux `unshare`, Landlock ABI 3 or newer, procfs, and
`libseccomp.so.2`. Missing containment support is an execution failure. The
injectable low-level runner exists only for contract unit tests; public
provenance-bearing Vina, GNINA, GROMACS, and OpenMM entrypoints always execute
their byte-pinned artifacts through this containment path.

## OpenMM Reference fixture

`openmm.adapter.evaluate_harmonic_bond_reference` is the provenance-bearing
API. It accepts an `OracleRequest` whose only input role is `prepared_system`.
The adapter reconstructs the complete fixed two-particle system from the
request parameters, recomputes
`harmonic_bond_prepared_system_sha256(...)`, and rejects any digest mismatch.
The fixture's `request` object can therefore be passed directly to
`OracleRequest(**fixture["request"])`.

OpenMM has no single engine executable, and this evaluator executes NumPy when
materializing forces. The helper
`openmm_runtime_dependency_distributions_sha256()` therefore computes one
canonical composite digest over the actual bytes, metadata versions, included
paths, and sizes of the import/runtime closure for both installed dependency
distributions: `OpenMM` and `numpy`.
`openmm_reference_runtime_sha256()` is a compatibility alias for that same
composite digest. Record the digest when enrolling approved wheels, then
provide it as `expected_runtime_sha256`.

Schema `betelgeuze.openmm_runtime_dependency_distributions/3.0.0` defines that
closure so the same locked CPython-platform wheels have the same identity in
different virtual-environment paths. It includes canonical paths, sizes, and
byte hashes for source, native libraries, and package data inside each exact
site-packages search root. Each distribution's `METADATA` bytes and normalized
version remain pinned. It deliberately excludes:

- console scripts outside the search root, such as NumPy's generated `f2py`
  launcher with its environment-specific shebang;
- installed `__pycache__/*.pyc`, because the worker uses an empty private
  `-X pycache_prefix` together with `-B` and therefore never loads them; and
- pip installation records `RECORD`, `INSTALLER`, `REQUESTED`, and
  `direct_url.json`, whose bytes describe the installation path or installer
  rather than code loaded by the worker.

The adapter holds descriptors for every included closure artifact and journals
each relevant ancestor path component, which makes rename/swap/restore
mutations fail closed. It runs the Reference evaluation only in a clean
`python -I -S -B` child from bounded source bytes copied out of a pinned worker
descriptor into an immutable `python -c` argument. No regular-file descriptor
crosses the child trust boundary. The child
independently checks both metadata inventories, hashes both distributions
before and after execution, and verifies every loaded `openmm.*` and
`numpy.*` module origin. OpenMM, NumPy, or `simtk` modules preloaded in the
caller cannot enter the evaluation. The Python executable is byte-pinned and
recorded separately, while the composite runtime digest occupies the common
result contract's `executable_sha256` identity field. The returned
`HarmonicBondRun` contains the scalar `result`, an immutable canonical
`raw_state` child record and its digest, and an `OracleResult` `provenance`
object; all claim flags remain false.

This distribution digest does not claim to enumerate glibc, the dynamic
loader, kernel interfaces, or other system shared libraries. Those remain
part of the separately frozen Python/container execution environment for a
benchmark row and must be recorded by that environment's own image or system
identity.

`evaluate_harmonic_bond_smoke(**fixture["smoke_parameters"])` intentionally
does not produce provenance or pin distribution bytes. It is only a local
installation smoke check and must not be used for parity evidence.
