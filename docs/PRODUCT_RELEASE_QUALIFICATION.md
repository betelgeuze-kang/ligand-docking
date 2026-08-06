# Betelgeuze product-image release qualification

## Status

This contract defines how release evidence is verified. It does not authorize a
release, registry push, deployment, GPU parity claim, or scientific claim.

```text
product_release_authorized = false
registry_push_authorized = false
deployment_authorized = false
gpu_parity_claim_authorized = false
scientific_claim_authorized = false
```

The committed evidence file is an intentionally unqualified template. Missing
artifacts remain explicit blockers rather than being represented by build-time
readiness fixtures.

## Required technical evidence

A complete evidence packet must bind all of the following to one immutable image
digest and the frozen qualification policy.

### Image and dependencies

- immutable product-image and base-image `@sha256:` references;
- a complete transitive Python lock whose package rows are exact-pinned and
  contain SHA-256 hashes;
- an offline wheelhouse manifest;
- exact wheel bytes, reviewed package origins, RECORD identities, and licenses.

### SBOM, vulnerability, and license evidence

- source, Python wheel, native-extension, and container SBOMs;
- SPDX 2.3 or CycloneDX 1.6 document identity;
- vulnerability scanner database identity;
- no unexcepted high or critical finding;
- any exception must be reviewer-bound, current, and no longer than 30 days;
- no unknown, AGPL-3.0-only, or SSPL-1.0 package license;
- a retained third-party attribution artifact.

### Provenance and runtime

- an Ed25519-signed provenance attestation;
- exact builder, policy, material, and image-digest binding;
- runtime UID/GID `10001:10001`;
- read-only root filesystem;
- only `/app/logs`, `/app/runs`, and `/data` as writable mounts;
- no privileged execution.

### Hardware and recovery

- at least one reviewed CPU operational-compatibility receipt;
- at least one reviewed ROCm operational-compatibility receipt;
- explicit statement that compatibility is not scientific parity;
- a previous immutable digest;
- verified restore and incident-response procedures;
- registry retention of at least 30 days.

## Result semantics

The verifier separates technical completeness from release authority.

A complete, correctly signed packet produces:

```text
technical_evidence_complete = true
release_qualified = false
blockers = [human_release_authorization_missing]
```

This prevents a CI run, evidence-file edit, or signing test key from publishing
an image. Human approval, protected signing infrastructure, immutable registry
publication, deployment approval, and real hardware receipts remain separate
operations.

## Template verification

The committed template is safe to verify in read-only CI:

```bash
python tools/verify_product_release_qualification.py
```

It returns an explicit blocker list without requiring release artifacts or a
trusted public key.

A complete packet is verified with an artifact root and independently supplied
Ed25519 public key:

```bash
python tools/verify_product_release_qualification.py \
  --evidence /reviewed/release/evidence.json \
  --artifact-root /reviewed/release \
  --trusted-public-key-hex <64-hex-character-public-key>
```

## Non-goals

This contract does not create a transitive lock, download wheels, approve a ROCm
base image, query a live vulnerability database, generate or sign production
attestations, publish to a registry, deploy, run a GPU matrix, or establish
scientific parity. Those artifacts must be produced in separately reviewed
infrastructure and then verified against this contract.
