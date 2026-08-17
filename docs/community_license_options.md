# Community licensing options

This document is a decision aid.  It does not modify the repository's current
proprietary `LICENSE` and grants no permission by itself.

The stated goal of independent community validation requires some explicit
right to download, build, execute, benchmark, modify, and submit changes.  A
public repository without such a grant is source-visible but not open source.

## Option A — MPL-2.0 native core

Suggested split:

- native engine core and ABI: MPL-2.0;
- benchmark schemas and verifier tools: Apache-2.0;
- enterprise orchestration, hosted service, and selected UI: commercial;
- model weights: separate model license.

Advantages:

- external users may build, benchmark, modify, and redistribute the core;
- file-level copyleft keeps modifications to covered files available;
- proprietary applications may link to the core under defined conditions;
- suitable for an open-core commercial strategy.

Tradeoffs:

- repository boundaries and third-party notices must be maintained carefully;
- mixed-license distribution needs clear packaging.

## Option B — Apache-2.0 core

Advantages:

- easiest adoption in academic and commercial environments;
- explicit patent grant;
- simple integration with other permissive tools.

Tradeoffs:

- downstream modifications may remain closed;
- weaker leverage for a dual-license business model.

## Option C — AGPL-3.0 plus commercial license

Advantages:

- hosted modifications normally remain subject to source-sharing obligations;
- strong dual-license leverage for commercial hosting or embedding.

Tradeoffs:

- some companies and research platforms will not adopt AGPL dependencies;
- license compatibility review is more demanding.

## Option D — community evaluation license

A source-available evaluation license could permit:

- non-production build and execution;
- publication of benchmark results;
- local modification and pull requests;
- redistribution only of small patches, not full commercial products;
- no hosted service or resale.

Advantages:

- preserves more commercial control during pre-release validation;
- can be adopted before committing to an OSI-approved open-source model.

Tradeoffs:

- it is not open source;
- every institution may need legal review;
- adoption and independent reproduction will be lower than with standard
  licenses.

## Recommended staged decision

1. Publish benchmark schemas, small fixtures, reproduction receipts, and
   verifier tools under Apache-2.0.
2. Choose MPL-2.0 or AGPL/commercial dual licensing for the native engine after
   auditing all first- and third-party source boundaries.
3. Keep enterprise deployment, hosted orchestration, private customer adapters,
   and selected model weights under separate terms.
4. Add `THIRD_PARTY_NOTICES`, an SPDX inventory, and package-level license files
   before the first community binary release.

## Required owner decisions

Before replacing the current license, the owner should decide:

- whether hosted use must trigger source-sharing;
- whether proprietary embedding is a target revenue source;
- whether model weights are distributed with or separately from the engine;
- whether external contributors require a CLA, DCO, or assignment;
- whether patents or pending applications need explicit handling;
- which repository directories form the open core.

No option should be applied by an automated change without explicit owner
approval and a third-party license audit.
