# Security Policy

## Supported code

Security fixes are developed against the current `main` branch and any release or
maintenance branch that the repository owner explicitly identifies as supported.
Historical donor branches and superseded pull requests are reference material only
and are not supported deployment surfaces.

The independent Engine v2 package, product API, worker, validated-runner path,
container/deployment assets, GitHub Actions workflows, and evidence/artifact
verification code have different trust boundaries. A green check in one lane does
not qualify another lane.

## Reporting a vulnerability

Do not disclose a suspected vulnerability in a public issue, discussion, pull
request, benchmark artifact, or generated evidence bundle.

Use GitHub's private vulnerability-reporting flow from the repository **Security**
tab when it is available. If that flow is unavailable, contact the repository owner
through a private GitHub channel before sharing exploit details or sensitive
artifacts publicly.

Include, when possible:

- the affected commit, branch, release, route, workflow, or runner profile;
- a minimal reproduction that does not contain customer or regulated data;
- expected and observed behavior;
- impact and prerequisite assumptions;
- whether the issue crosses tenant, process, filesystem, container, runner, or
  artifact-signing boundaries;
- suggested mitigations, if known.

Do not test against third-party systems, customer data, shared runners, production
credentials, or external services without explicit written authorization.

## Security-sensitive areas

Reports are especially useful for:

- authentication, tenant identity, object authorization, and privacy redaction;
- queue admission, leases, attempt tokens, terminal publication, and SQLite
  concurrency or rollback behavior;
- validated-runner namespace, process-tree, environment, network, filesystem, and
  resource containment;
- path traversal, symlink or hard-link handling, TOCTOU behavior, artifact digest
  verification, signatures, receipts, and evidence freshness;
- untrusted pull-request workflows, self-hosted runners, mutable Actions references,
  dependency or container supply-chain integrity, and secret exposure;
- parser resource exhaustion, malformed molecular inputs, archive expansion, and
  denial-of-service conditions;
- native, Rust, HIP, CUDA, ROCm, and other memory-safety boundaries.

Scientific disagreement or an unvalidated model result is not automatically a
software vulnerability. However, a bug that bypasses a fail-closed claim gate,
mislabels proxy output as validated physical evidence, drops failed benchmark rows,
or enables an unauthorized execution path should be reported privately as an
integrity or authorization issue.

## Response and disclosure

The repository owner will determine scope, reproduce the issue, prepare a fix and
regression test, and coordinate disclosure appropriate to the affected surface.
Please allow remediation and downstream notification before public disclosure.

A security fix must not silently promote scientific, benchmark, GPU, customer, or
commercial claim flags. Those transitions require their own reviewed evidence.
