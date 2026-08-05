# Product image and dependency supply-chain policy

## Scope

This policy hardens product image construction and direct dependency profiles.
It does not qualify the product for release, sign an image, publish to a
registry, deploy a workload, validate ROCm parity, or authorize scientific
claims.

## Development and release builds

Development builds retain the existing ROCm image tag as a compatibility
fallback. Release builds must set:

```text
PRODUCT_IMAGE_RELEASE_BUILD=1
PRODUCT_ROCM_BASE=<approved-image>@sha256:<64-hex-digest>
RUSTUP_INIT_SHA256=<64-hex-digest-of-the-pinned-installer-script>
```

The Dockerfile fails closed in release mode when either digest is absent. The
Rustup bootstrap URL is pinned to rustup tag `1.29.0` commit
`28d1352dbcb436d3111c3594b9e1588e94950464`; the Rust toolchain is pinned to
`1.93.0`.

A tag-based development build is not a reproducible release artifact and must
not be signed or promoted.

## Multi-stage and runtime identity

The builder stage contains compilers, Rust, headers, and build tools. The runtime
stage copies only the application tree and virtual environment into the same
ROCm base family. Runtime uses UID/GID `10001:10001`, creates owner-only `/data`,
`/app/logs`, and `/app/runs`, and does not grant world-writable permissions.

The image no longer creates a build-time `independent_engine_roadmap_closed`
fixture. Missing runtime evidence therefore leaves dispatch fail-closed rather
than manufacturing readiness during image construction.

## Dependency profiles

- `requirements-api-runtime.txt` contains exact direct runtime pins.
- `requirements-api.txt` includes the runtime profile and adds exact-pinned test
  tooling only.
- `requirements-deploy.txt` exact-pins the optional deployment tracker.
- the product image installs the runtime API profile, not pytest.
- pip itself is pinned during image construction, and `pip check` runs in both
  builder and runtime stages.

These files are direct-dependency pins, not a complete transitive hash lock.
Until a generated, reviewed `--require-hashes` lock and wheelhouse are available,
the image is not eligible for signed release status.

## Build context

`.dockerignore` excludes repository-generated `runs/`, `.betelgeuze/`, Git
metadata, caches, local environments, model weights, archives, and other local
artifacts. Runtime evidence must enter through reviewed volumes or explicit
artifacts, never implicitly through the Docker build context.

## Dependency monitoring

Dependabot monitors:

- GitHub Actions;
- Python direct dependencies; and
- Docker base references.

Dependabot only proposes updates. Each update still requires compatibility,
security, scientific-boundary, and exact-head CI review.

## Remaining release blockers

The following are intentionally recorded as not implemented:

- complete transitive dependency hashes and an offline wheelhouse;
- SBOM generation and attachment;
- container vulnerability scanning;
- dependency license scanning;
- approved ROCm base image digest inventory;
- release signing and provenance attestation;
- registry publication and deployment authorization; and
- runtime ROCm/GPU parity qualification.

None of those capabilities may be inferred from this guardrail PR.
