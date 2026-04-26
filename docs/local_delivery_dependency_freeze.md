# Local Delivery Dependency Freeze

## Purpose

The dependency freeze records the exact Python package state used by a local delivery so the same bundle can be rerun on the same machine class with the same interpreter. It complements the environment manifest: the manifest says where the run happened, and the lock says which Python packages were active there.

The lock applies to the local-delivery required dependency set only. API-only, train-only, deploy-only, and other optional packages must be tracked separately as optional/deferred evidence instead of being silently folded into the required set.

This is a reproducibility control for local deliveries, not a new packaging or release-engineering flow.

## When To Generate

Generate one requirements lock for every paid local delivery during the final preflight refresh, before environment manifest capture and before bundle assembly. Build it against the local-delivery required set, not against every extra package that happens to be installed.

```bash
python3 tools/build_local_delivery_requirements_lock.py
```

Regenerate the lock whenever:

- `requirements.txt` or `requirements-dev.txt` changes
- packages are installed, upgraded, removed, or resolved differently
- the delivery moves to a different interpreter or machine
- the final preflight refresh changes the runtime state

Do not assemble the bundle from a stale lock.

## How It Fits The Workflow

- `runs/local_delivery_environment_manifest_current.json` and `runs/local_delivery_environment_manifest_current.md` capture the machine and runtime baseline.
- `runs/local_delivery_requirements_lock_current.json`, `runs/local_delivery_requirements_lock_current.md`, and `runs/local_delivery_requirements_lock_current.txt` capture the resolved Python package state from that same environment.
- Preflight should build the requirements lock before the environment manifest so the manifest can reference and hash the lock artifacts.
- Bundle assembly should copy both current artifacts into the bundle and list them in `manifest.json` and `manifest.md`.

The `.txt` lock should preserve the exact resolved package list. The `.md` file should summarize provenance, source inputs, and any caveats.

## Current Recorded State

As of `2026-04-26`, the current lock is complete for the required local-delivery set: `installed_count=13`, `missing_count=0`, `loose_source_requirement_count=0`, and `requirements_lock_complete=true`. Seven API/train/deploy/optional packages remain deferred (`optional_missing_count=7`) and must not be counted as required coverage.

## Bundle Attachments

Attach the canonical dependency-freeze artifacts alongside the environment manifest in the bundle's `environment/` area:

- `environment/environment_manifest.json`
- `environment/environment_manifest.md`
- `environment/requirements_lock.json`
- `environment/requirements_lock.md`
- `environment/requirements_lock.txt`
- `checksums.sha256`

If the delivery used generated or patched requirement inputs, also attach the exact `requirements.txt` and `requirements-dev.txt` files that were frozen, or record their content hashes in the manifest.

## Missing Or Unpinned Requirements

- If a runtime requirement file is missing, restore it before freezing. A delivery cannot claim reproducibility without the source requirements.
- If the source files contain unpinned entries in the required local-delivery set, the lock must record the exact resolved versions from the current environment.
- If a package is only needed for API, train, deploy, or other optional flows, record it as optional/deferred evidence instead of counting it as required coverage or hiding it in the lock.
- If the lock cannot be built deterministically, note the gap in `known_exclusions` and keep the bundle out of delivery-ready status.
- Treat `requirements-dev.txt` as required only when dev tooling was part of the delivery run.

## Why This Exists

This is local-delivery reproducibility, not hosted production packaging.

It does not try to:

- define a multi-tenant runtime image
- replace release engineering for a hosted service
- broaden the commercialization claim
- make the repo production-ready on its own
