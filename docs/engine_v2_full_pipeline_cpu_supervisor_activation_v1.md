# Engine V2 full-pipeline CPU supervisor activation v1

This change freezes the first packaged, roster-bound, non-consuming activation
layer for the full-pipeline CPU supervisor. It does not install the package,
does not launch the root service, does not run the performance preflight, and
does not consume an exactly-once qualification attempt.

## Exact source foundation

The contract is based on merged `main` commit
`2d03360e782ec9f06518b704ac4fb498fb3448e6` and tree
`e0dd19eb3efab258d88d192440b025d79b6c9802`. The complete Git commit object
and NUL-delimited tree manifest are independently re-hashed by the verifier.
It retains the frozen full-pipeline performance activation, profile, runtime
manifest, and predecessor supervisor contract as distinct bindings.

The supervisor source remains C++17 and has SHA-256
`ac476df202f01083e2d9ff34b64030de1d3fef13b2be09180e6a463cd47043c2`.
The default build still has an unconfigured client identity. A package build
may compile only the exact client UID, GID, and preflight SHA into the source;
the installation, runtime-launch, and qualification-consumption constants
remain compile-time false and cannot be changed by those parameters.

## Frozen package and roster

The committed x86-64 static ELF package is 2,069,736 bytes and has SHA-256
`a33a07fc8a9f55a843ead479cee5b46f8ef31cb6787141fb7e3d8a563efb1466`.
Two builds using the frozen GCC 11.4.0 executable and exact flags were
byte-identical. The verifier confirms ELF64/x86-64 executable identity, absence
of `PT_INTERP` and `PT_DYNAMIC`, package digest, and SPDX 2.3 SBOM bindings.
Git records the artifact with index mode `100755`, because Git cannot encode
`0555`; each authoritative workflow explicitly materializes mode `0555` before
verification. This is still repository-owned transport evidence, not a
root-owned installation receipt.

The package's non-operational `--describe-contract` entrypoint reports the
compiled `64042:64042` roster, `client_identity_configured=true`, and the exact
preflight SHA. The verifier compares those observable values with the roster
and activation contract; it does not infer the compile-time binding from an
opaque ELF digest alone. The recorded preflight macro argument includes the
literal C++ string quotes used in the compiler argv.

The desired execution-account roster is fixed at `64042:64042` with a private
primary group, no supplementary groups, `/nonexistent` home, and
`/usr/sbin/nologin`. Root remains the service identity. The account and group
are not provisioned by this repository, and no provisioning or collision-check
receipt exists. The current developer account is deliberately not reused: its
supplementary groups and administrative roles do not meet the private execution
account boundary.

## Sealed handoff preflight

The exact standalone handoff preflight has SHA-256
`67c2e6ace0a4585d7004508323dc9928ddf45ee24e4bc77fa0406be4331857a0`.
Before any downstream runtime or scientific module is loaded, it requires:

- the exact supervisor-derived argument vector and environment;
- a root `SO_PEERCRED` socket peer and live socket-derived `SO_PEERPIDFD`;
- one untruncated 464-byte `SOCK_SEQPACKET` handoff;
- exactly three `SCM_RIGHTS` descriptors received with
  `MSG_CMSG_CLOEXEC`;
- capture and close every delivered rights descriptor before rejecting a
  truncated, malformed, multi-message, or overfull ancillary payload;
- a byte-identical 464-byte mode-`0400` memfd receipt with all four write,
  grow, shrink, and seal locks;
- exact activation, preflight, profile, runtime, loader, interpreter, launch
  vector, and launch-environment digests;
- the rostered request UID/GID and current child PID;
- initial user/mount namespace descriptor type, owner, parent, device, and
  inode evidence through `NS_GET_NSTYPE`, `NS_GET_OWNER_UID`,
  `NS_GET_PARENT`, and `NS_GET_USERNS`.

The preflight also implements a 96-byte terminal parser that binds the terminal
receipt to the exact request nonce and request SHA-256. It does not accept a
caller-supplied command, environment, molecular input, scorer option, or result.

Even a valid handoff ends with exit 125 because the downstream performance
preflight binding is not admitted. Direct execution and GitHub Actions fail
before the handoff socket, namespace descriptors, runtime, or package is read.
Thus this parser can be reviewed and tested without creating a successful
activation receipt.

## Downstream identity chain

The versioned downstream contract requires all of the following to remain in
one identity chain:

```text
source foundation
  -> supervisor source and contract
  -> static package and SBOM
  -> client roster
  -> preflight source and runtime/profile bindings
  -> request SHA and nonce
  -> sealed handoff packet and namespace FDs
  -> non-consuming preflight evidence
  -> terminal receipt
  -> exactly-once qualification-state transition
```

No binding receipt or state transition is present in this change. Result-based
selection, missing stages, substituted package/roster identities, and terminal
cross-wiring are rejected. A later reviewed integration must bind the observed
supervisor binary digest from the kernel handoff to the committed package hash,
run the independently qualified preflight, and attach the terminal receipt to a
transactional exactly-once state machine.

## Remaining local blockers

The verifier intentionally returns six local blockers:

1. execution-account provisioning receipt missing;
2. root installation receipt missing;
3. independent namespace/trace qualification missing;
4. performance preflight not bound;
5. terminal downstream receipt missing; and
6. exactly-once runner not bound.

The package must not be copied to `/usr/local/libexec`, no systemd unit may be
created, and the supervisor socket must remain absent. Timeout, descendant
cleanup, peer death, replay, and ambiguous terminal behavior still require an
independent qualification before runtime launch can be considered.

## Authority boundary

Every installation, launch, qualification-consumption, reservation, molecular,
Fresh-128, Stage 0, product, benchmark, scientific-claim, and HIP authority bit
remains false. GitHub Actions and test doubles have no production authority or
production endpoint credentials.

The external authority verifier remains fail-closed with 32 unresolved fields
and exactly four blockers: provider not operational, endpoint not configured,
trust anchor not configured, and historical execution operational authority
false. The consumed native fixed64 CPU v7 qualification is not rerun. This
change performs no molecular A/B, D1/D2 execution, Fresh-128, public benchmark,
HIP device execution, product mutation, customer pose emission, or claim.

Static verification is safe:

```bash
chmod 0555 \
  packaging/engine-v2/full-pipeline-cpu-supervisor/1.0.0/engine-v2-full-pipeline-cpu-supervisor-v1
python3 tools/verify_engine_v2_full_pipeline_cpu_supervisor_activation_v1.py
```

That command verifies committed bytes and executes only the package description
and fail-closed entrypoint. It does not install or launch a service.
