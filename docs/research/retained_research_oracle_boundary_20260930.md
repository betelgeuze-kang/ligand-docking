# Retained OpenMM research scripts and product boundary

The previously failing `development-protocol` job passed its unit, format and
architecture stages before the external-oracle guard rejected 14 direct OpenMM
imports in nine retained research scripts. The scripts hold preparation and
same-math numerical validation for 5-HT6 development; they are not product
entrypoints. Every script is byte-identical to the pre-change HEAD.

The guard now names exactly these nine paths as research oracle scripts. The
classification exempts their own OpenMM calls but denies direct and transitive
product imports. Docker exclusions apply after the broad tools inclusion and
the image-mode guard rejects their presence even if Docker rules change.
Unregistered new docs/tools OpenMM scripts are still rejected. Product package
and dependency exclusions remain enforced.

All 101 local architecture tests pass, including new mutation tests for the
above boundaries. The originally failing `python3
tools/check_external_oracle_architecture.py` command also returns zero locally.
The [evidence index](../evidence/retained_research_oracle_boundary_v1.json)
binds the scripts, checker, Docker rules, tests and retained JUnit file. Hosted
CI for the new commit remains a separate gate. This correction does not change
any molecular result or establish product or scientific qualification.
