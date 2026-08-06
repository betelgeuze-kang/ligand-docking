# Betelgeuze product identity and canonical workflow

## Canonical names

| Role | Canonical name | Meaning |
| --- | --- | --- |
| Brand | **Betelgeuze** | Company and umbrella technology brand |
| Customer product | **Betelgeuze Docking** | Restricted local docking validation and evidence delivery product |
| Scientific engine | **Engine V2** | Research and validation engine; not automatically a customer route |
| Evidence review UI | **Evidence Desk** | Human review, uncertainty, provenance, and export surface |
| Research surfaces | **Research Validation Lanes** | Benchmark, Stage 0, shadow, and experimental capabilities |

The product must not use `Engine V2 implemented` as a synonym for `customer
ready`, and it must not use a legacy restricted-lane result as evidence that the
Engine V2 redocking or global-orientation lane is scientifically validated.

## Positioning

Supported positioning:

> Betelgeuze Docking is a local-first restricted docking validation and
> audit-ready evidence delivery product for explicitly supported target and
> chemistry lanes.

Unsupported positioning:

> Betelgeuze is a blanket docking, all-atom MD, FEP, or commercial-suite
> replacement.

The unsupported positioning remains forbidden even when individual technical
components, synthetic contracts, smoke tests, or internal benchmark rows are
green.

## Source of truth

`config/product_capability_registry.json` is the machine-readable source for:

- implementation lane;
- scientific status;
- benchmark status;
- product status;
- customer-execution status;
- default enablement;
- claim scope;
- allowed wording;
- forbidden wording;
- blockers; and
- evidence source paths.

It is intentionally **not** a runtime routing authority. Product routing must
remain in separately reviewed code and may only consume a capability after the
registry and the routing policy agree. A registry edit alone cannot enable a
customer path.

## Canonical customer workflow

```text
Prepare → Validate → Propose → Score → Select → Review → Export
```

### 1. Prepare

Inputs:

- receptor structure;
- ligand or ligand library;
- declared pocket or pocket-selection policy;
- pH and chemistry preparation policy;
- run manifest and tenant identity.

Outputs:

- immutable input identities;
- preparation transformations;
- declared assumptions;
- unsupported or unresolved chemistry; and
- a preparation receipt.

No scientific or product success is established at this step.

### 2. Validate

The support gate checks:

- structural completeness relevant to the pocket;
- atom, bond, charge, stereochemistry, tautomer, and protonation status;
- metal, cofactor, water, altloc, and missingness policy;
- supported target and chemistry lane; and
- required execution environment.

The outcome is either a typed supported path or a structured abstention. The
system must never silently guess unsupported chemistry to avoid an abstention.

### 3. Propose

The route-selected proposal engine creates a failure-complete candidate set.
Candidate generation must not consume native/reference poses, post hoc RMSD,
benchmark outcomes, or scoring feedback unless an explicitly separate diagnostic
oracle lane is used.

Every candidate slot must retain:

- source and configuration identity;
- proposal mode;
- conformer and orientation identity;
- coordinate identity;
- acceptance or rejection status; and
- structured rejection reason.

### 4. Score

Scoring consumes the sealed candidate set. It records complete decomposed terms,
backend identity, parameter/source provenance, numerical policy, and validity
context. A score is not calibrated affinity unless a separate calibrated
contract explicitly proves that claim.

### 5. Select

Selection is deterministic and separated from candidate generation. Reports must
show at least:

- selected Top-1 and Top-K;
- valid Top-1 status;
- proposal oracle when reference evaluation is permitted;
- valid proposal oracle;
- ranking/selection regret; and
- abstention or failure class.

Reference metrics belong to post-generation evaluation and cannot influence the
candidate set under evaluation.

### 6. Review

Evidence Desk presents:

- structures and candidate poses;
- physical and chemical validity;
- key interaction explanations;
- uncertainty and applicability domain;
- preparation changes;
- benchmark and claim scope;
- provenance and receipt chain; and
- explicit blockers.

Internal authority fields and hashes remain available in an Audit view rather
than dominating the primary scientist workflow.

### 7. Export

Export produces:

- selected structures;
- machine-readable result manifest;
- human-readable summary;
- replay command and environment identity;
- complete evidence bundle; and
- claim-gated wording.

The exporter must derive positive wording from the capability registry and
benchmark ledger. It must never convert a diagnostic, research-only, locked, or
unvalidated capability into a customer claim.

## Current capability interpretation

### Restricted local delivery

The legacy restricted docking lane is the only registry row currently marked
claim-safe, and only for target-specific guarded wording. It is not default
enabled and remains operator controlled.

### Engine V2 redocking

Engine V2 redocking is implemented but Stage 0 blocked. Fresh holdout remains
unexecuted, and customer execution, product default, and claims remain disabled.

### Engine V2 global orientation

The first global-orientation implementation is synthetic-only. It proves a
deterministic bounded proposal contract and separated metrics, not molecular
accuracy or generalization.

### Broad GPCR, PocketMD, public benchmark, and full MD/FEP

These remain family locked, diagnostic, incomplete, or unsupported as specified
in the registry. None may be enabled or advertised through wording drift.

## Change-control rules

A capability may move toward customer use only through a reviewed change that:

1. updates immutable evidence and source paths;
2. passes the registry verifier and tamper tests;
3. updates the benchmark ledger where applicable;
4. updates routing code in a separate explicit change;
5. documents rollback and abstention behavior;
6. obtains scientific, security, and product approval; and
7. leaves unrelated broad claims fail-closed.

A status document, synthetic test, UI toggle, or implementation flag alone can
never authorize a product route.
