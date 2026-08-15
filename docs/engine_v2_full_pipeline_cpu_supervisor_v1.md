# Engine V2 full-pipeline CPU supervisor v1

This change supplies a reviewable but non-operational native Linux supervisor
foundation for the frozen full-pipeline CPU profile. It is not an activation receipt,
qualification result, performance result, reservation, or product
authority. The binary must not be installed, provisioned as root, or used to
launch the preflight under this contract.

## Frozen foundation

The source is based on merged main commit
`c15b46e4a93e157826677165642b8788b75f20c7` and tree
`28361485778537401731d6d085480ae6e613dbc5`. It binds the unchanged activation,
preflight, profile, runtime-scope manifest, root-owned dynamic loader, and
root-owned CPython executable by SHA-256. The predecessor activation remains
non-consuming and still reports that no operational trusted supervisor exists.
This source contract does not modify that predecessor or make its unreachable
Python stage-0 path reachable.

The source contains three compile-time false gates: installation, runtime
launch, and qualification consumption. The client UID and GID are also
unconfigured fail-closed sentinels in the default build. A separately reviewed
package may supply the exact client UID/GID and preflight SHA as compile-time
definitions, but those definitions cannot alter the three false gates. No
environment variable, request field, GitHub Actions input, or command-line
option can turn those gates on. The only successful commands are
`--describe-contract` and the non-service primitive self-test; every service
invocation exits 125 before namespace inspection, socket creation, fork, or
exec.

## Fixed protocol

The future local transport is an absent-only root-owned `AF_UNIX` /
`SOCK_SEQPACKET` socket. A request has exactly 192 bytes and exactly three
`SCM_RIGHTS` descriptors:

1. the exact preflight source;
2. the artifact directory;
3. the runtime directory.

`SO_PEERCRED` fixes the requesting PID, UID, and GID before any descriptor is
used. Linux `SO_PEERPIDFD` obtains the pidfd from that same socket peer without
a PID-reuse lookup window. The request carries a nonzero 32-byte nonce plus the
exact activation, preflight, profile, and runtime manifest digests. It cannot
supply a command, executable path, environment, scoring input, molecular input,
or result-dependent option.

The service derives the loader vector and environment internally. It hashes
stable no-follow descriptors, copies the authenticated preflight into a sealed
memfd with mode `0444`, and retains all four `F_SEAL_*` write/size/seal locks.
The read-only mode permits the rostered post-drop UID to reopen the inherited
source through `/proc/self/fd/190`; the seals, not root-only mode bits, enforce
immutability. The child receives only six fixed descriptor numbers after `close_range`: source snapshot,
artifact directory, runtime directory, handoff socket, loader, and interpreter.
The loader is entered with descriptor-bound `execveat(..., AT_EMPTY_PATH)`.
Descriptors 0, 1, and 2 are first rebound to a root-opened and device-verified
`/dev/null`; the child also receives a private umask and `/` working directory.
No inherited root-service stdio is used as an input or evidence channel.

## Kernel-attested execution chain

The intended independently provisioned service opens its own initial user and
mount namespace descriptors before accepting a request. It checks exact
namespace inode identities and uses `NS_GET_NSTYPE`, `NS_GET_OWNER_UID`,
`NS_GET_PARENT`, and `NS_GET_USERNS`. `/proc` paths are only a way for that
already trusted service to obtain kernel namespace or executable descriptors;
procfs path strings are not authoritative evidence.

After fork, the child calls `PTRACE_TRACEME` and stops before dropping root
credentials. The root parent then installs `PTRACE_O_TRACEEXEC`,
`PTRACE_O_EXITKILL`, and fork/vfork/clone tracing. Only after that continuous
trace boundary exists may the child clear groups, set the rostered UID/GID,
enable no-new-privileges, disable dumpability, and enter the exact loader.
The parent verifies the first exec event against the opened loader descriptor.
A second exec is rejected.

At the verified exec stop, the root peer sends a 464-byte handoff plus three
kernel descriptors: a sealed memfd receipt, the initial user namespace, and the
initial mount namespace. The child-side socket was created while the peer was
root, so `SO_PEERCRED` and the inherited socket endpoint bind the handoff to the
independently provisioned service rather than to a caller-owned pathname. A
96-byte terminal message binds the nonce, request digest, exit disposition, and
containment flags. The handoff also carries the actual supervisor binary digest
and the independently re-derived SHA-256 identities of the complete NUL-delimited
launch vector and environment. Peer pidfd and connection liveness remain required
until that terminal message is emitted.

## Deliberately incomplete lifecycle

The implementation source is present, but all of the following remain false or
absent:

- a packaged and frozen binary identity;
- a root-owned installation manifest or systemd unit;
- the distinct execution-account UID/GID roster;
- independent initial-namespace and continuous-trace qualification;
- activation/preflight parsing of the kernel handoff;
- an exactly-once qualification-state transaction;
- an operational socket or successful preflight receipt.

The separately reviewed
`engine_v2_full_pipeline_cpu_supervisor_activation_v1` successor freezes the
roster, static package, SBOM, and child-side handoff parser while keeping every
authority bit false. It does not revise this source-only contract into an
installation receipt. A later operational integration must still provision and
attest the service, qualify timeout, descendant cleanup, peer death, replay,
namespace/trace behavior, and ambiguous terminal handling, then bind the
performance preflight and exactly-once state transition before the one-shot CPU
qualification runner can be considered.

## Compile-only verification

CI may compile the source and execute only its static description and
fail-closed entrypoint:

```bash
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -Werror -static -s \
  -Wl,--build-id=none \
  native/tools/engine_v2_full_pipeline_cpu_supervisor_v1.cpp \
  -o /tmp/engine-v2-full-pipeline-cpu-supervisor-v1
/tmp/engine-v2-full-pipeline-cpu-supervisor-v1 --describe-contract
/tmp/engine-v2-full-pipeline-cpu-supervisor-v1 --self-test-primitives
# Any service invocation exits 125 and creates no socket.
```

The static verifier re-hashes the complete source and predecessor objects,
requires all authority fields to remain false, and verifies authoritative CI
wiring. CI does not use `sudo`, bind the service socket, run the preflight,
write qualification state, or consume an attempt.

Reservation, historical or fresh molecular execution, public benchmark,
Stage 0 admission, product execution, HIP device execution, and acceleration
claims remain prohibited. The external-authority verifier and its four blockers
are unchanged.
