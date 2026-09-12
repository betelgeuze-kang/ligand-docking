# PubChem assay identity in development source graphs

The existing component graph accepts an explicit `PubChem AID` as a namespaced
source-assay key. Positive integers and their canonical decimal strings identify
the same assay. Malformed identifiers fail closed. ChEMBL and PubChem numeric
identifiers never alias implicitly. An absent/null AID retains the old behavior.

The existing v2 node schema already supports source-assay keys; no schema version
is renamed. Contexts without PubChem AID keep identical component results. Source
implementation hashes change, so frozen checkpoints must retain their original
runtime. Never rewrite a checkpoint hash to manufacture compatibility.

A bibliographic reference in an assay description is not automatically its
measurement publication. Keep method/background citations separate until their
relationship is established. Assay-level non-overlap cannot establish compound,
scaffold, chemical-state or full source independence. Chemical metadata and role
reservation must precede outcome acquisition.

Validation includes new synthetic reservation propagation and malformed-ID cases,
existing ChEMBL/patent component tests, and a recorded replay of 168182 prior nodes
plus two captured PubChem assay descriptions. This grants no scientific validation
or customer execution approval and does not admit new fit observations.
