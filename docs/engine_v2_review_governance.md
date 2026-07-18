# Engine v2 Review Governance

Changes to Engine v2 physics, validation trust, packaging, CI, or claim-policy
surfaces require repository branch protection in addition to CODEOWNERS routing.

For pull requests touching those paths, configure the protected `main` branch
to require:

- at least one approving review from a person other than the PR author;
- dismissal of stale approvals after new commits;
- approval from the applicable CODEOWNER;
- resolution of every review conversation;
- all required CI checks and an up-to-date head before merge;
- no administrator bypass for the protected evidence lane.

Cryptographic, authorization, POSIX-persistence, or execution-bootstrap changes
need a security reviewer. Numerical-method, force-field, minimization, or metric
changes need a numerical-methods reviewer. When one change spans both areas,
both reviews are required.

This repository file records the required policy but cannot prove that GitHub
branch protection is enabled, cannot create an independent reviewer identity,
and cannot replace an actual submitted human approval. Release evidence must
record the GitHub ruleset identity and the qualifying review submissions.
