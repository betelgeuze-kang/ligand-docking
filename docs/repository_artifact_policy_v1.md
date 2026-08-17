# Repository artifact policy v1

The repository already contains historical generated evidence and packaged
artifacts whose identities are referenced by scientific and qualification
receipts.  Rewriting that history would invalidate those references, so this
policy is deliberately **forward-only**.

The policy checks files added or modified by a pull request.  It does not scan
unchanged historical blobs and it never authorizes a history rewrite.

## Files that belong outside Git

New versions of the following should normally be published through GitHub
Releases, an OCI/package registry, Zenodo/object storage, or a model registry:

- wheels and native shared/static libraries;
- archives and compressed bundles;
- model checkpoints and serialized tensors;
- NumPy/HDF5 result arrays;
- generated run directories;
- large HTML/SVG reports;
- raw benchmark and qualification artifacts.

Git should retain the small manifest, SHA-256 identity, SBOM identity, release
or object-store locator, and the verifier required to consume the external
artifact.

## Guard behavior

`tools/check_repository_artifact_policy_v1.py` compares an explicit base and
head revision and checks only added or modified paths.

By default it rejects:

- changed files larger than 2 MiB;
- generated HTML, HTM, or SVG larger than 256 KiB;
- wheel, archive, library, model, NumPy, HDF5, and similar binary suffixes;
- files under `runs/`, `dist/`, `build/`, `target/`, `node_modules/`, or a local
  `.betelgeuze-engine-v2/` state directory;
- changed symbolic links.

The machine-readable policy is
`config/repository_artifact_policy_v1.json`.  Any exception must be an exact
reviewed path or path prefix in that policy; broad extension exceptions are not
allowed.

## Local use

```bash
python tools/check_repository_artifact_policy_v1.py \
  --base origin/main \
  --head HEAD \
  --pretty
```

A passing result means only that the changed paths satisfy the storage policy.
It does not validate scientific content, supply-chain provenance, licenses, or
release authority.

## Existing large history

The policy intentionally leaves existing history untouched.  A future history
rewrite would change commit, source-manifest, wheel, and qualification
identities across the repository and therefore requires a separate migration
plan, frozen mapping, review, and explicit owner approval.
