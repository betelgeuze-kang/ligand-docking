# Commercialization Productization Gap Audit - 2026-05-06

## Scope

This audit adds a productization layer on top of the existing scientific commercialization reports. The current restricted local-delivery claim can remain separate, but the repository is not ready for commercial product exposure as an API, hosted service, or unattended customer workflow.

## New Critical Gaps

| priority | gap | evidence | commercial risk | next required step |
| --- | --- | --- | --- | --- |
| P0 | API server cannot import | `python3 -m py_compile api/main.py api/tasks.py` fails; `api/main.py:36` and `api/tasks.py:12` have invalid `request_ dict` annotations | Any hosted/API claim is false; service cannot boot | Fix signatures, add import smoke test, and gate commercial readiness on API import |
| P0 | API task returns fake/demo output instead of running the engine | `api/tasks.py:32` raises `NotImplementedError` for PDB content; `api/tasks.py:44-55` sleeps and writes `FAKE RESULT FOR DEMONSTRATION` | Customers could receive non-scientific output while the job is marked completed | Wire to a real validated runner or keep `/simulate` disabled behind a fail-closed feature flag |
| P0 | Job state is in-memory and not restart-safe | `api/main.py:16-17` uses a process-local dict; status is split into local JSON files | Job loss, duplicate runs, no audit trail, weak incident recovery | Use durable queue/state storage with idempotent job records and signed result manifests |
| P0 | No API security boundary | `api/models.py:7-12` accepts raw PDB content and `ai_model_path`; no auth, tenancy, rate limit, payload size, path allowlist, or CORS policy exists in `api/main.py` | Data exposure, path abuse, denial of service, and uncontrolled model selection | Add authentication, authorization, request limits, model allowlist, path normalization, and audit logging before exposure |
| P1 | Monitoring config references endpoints that do not exist | `monitoring/prometheus.yml:30-34` scrapes `/metrics`; no FastAPI metrics endpoint is present; `monitoring/alertmanager.yml:9` contains a placeholder webhook | Operations may look monitored while no useful service metrics or alerts fire | Add `/metrics`, alert rules, secret injection, and a smoke test that Prometheus targets are scrapeable |
| P1 | Deployment is a skeleton, not a release system | `deploy/deploy_pipeline.sh` has restart/registry steps commented out; `deploy/upload_model.py` loads arbitrary local artifacts with `torch.load`; no Dockerfile/Compose/CI files were found | No reproducible rollout, rollback, artifact attestation, or environment parity | Add container image, pinned runtime, model registry contract, rollout/rollback, and signed artifact checks |
| P1 | Viewer depends on external CDNs and localhost fallbacks | `viewer/index.html:17-26` loads Mol*, Plotly, JSZip, and fonts from CDNs; `viewer/app.js:6516-6519` falls back to `127.0.0.1:8765`/`localhost:8765` | Offline/local-delivery and customer network policies can break the UI; localhost assumptions leak into user flow | Vendor/pin assets or bundle them, and make asset base URL explicit per delivery bundle |
| P1 | All-atom/AdResS topology path still has placeholders | `core/topology.py:45-47`, `core/topology.py:100-111`, and `core/topology.py:163-179` use all-alanine, zero AA coordinates, or random neighbor data | Broad all-atom/AdResS production claims would overstate implementation maturity | Keep all-atom/AdResS out of commercial wording until sequence/structure-derived topology and deterministic neighbor data are implemented |
| P2 | Online local-teacher loop is simulated | `train/local_teacher.py:76-109` documents missing QM/high-res MD integration and returns random forces/energy | Unattended online-learning or precision-refinement claims are not supportable | Replace with a real precision backend adapter or disable the lane in commercial configurations |
| P2 | Training/pretraining still contains mock runtime inputs in some paths | `train/pretrain_spice.py:110-122` and `train/meta_trainer.py:48-52` create mock topology/neighbor/PE inputs | Model provenance and train/eval parity remain weak for product claims | Require manifest-backed runtime inputs for production training and label mock paths as research-only |
| P2 | Test coverage is broad but misses exposed service surfaces | `tests/` has about 800 test files, but no direct API/deploy/Prometheus import or endpoint smoke tests were found; API py_compile currently fails | Existing green gates can miss customer-facing breakage | Add API import/endpoint tests, deploy dry-run tests, and monitoring scrape tests to the commercial gate |

## Existing Scientific Claim Blockers Still Stand

- GPCR scale-up/router promotion remains blocked by CI-low/top20 ranking quality, despite positive freeze, leakage audit, scoreability, and family-held-out green status.
- Transporter AQP1/GLUT1 remains parked/review-only outside the delivery claim until direct negative evidence and quantitative provenance close.
- CA2 remains prep-only with replacement workbook readiness blocked.
- PXR remains partial-authoritative/prep-only until quantitative provenance and `replacement_reference_binding_kcal_mol` closure complete.
- IDP broader promotion remains blocked outside the bounded admitted shadow-safe lane.

## Commercial Boundary Update

Current wording should distinguish three layers:

- `restricted_local_delivery`: can stay governed by the existing local bundle/verdict gates.
- `scientific_expansion`: remains blocked by GPCR scale-up, transporter, CA2/PXR, and broader IDP evidence gaps.
- `hosted_or_customer_api_product`: blocked now, independent of scientific gates, because API, deployment, monitoring, security, and service persistence are not production-ready.

## Immediate Fix Order

1. Add a fail-closed productization gate that runs `python3 -m py_compile api/main.py api/tasks.py` and refuses any API/hosted commercial status if it fails.
2. Disable or clearly mark `/simulate` as non-commercial until it calls a real validated runner and cannot emit fake/demo results.
3. Add minimal API security and durable job persistence before any network exposure.
4. Make Prometheus/Alertmanager real: expose metrics, remove placeholder webhook config, and test scrapeability.
5. Add a reproducible deployment surface with containerization, pinned dependencies, model artifact attestation, rollback, and CI.
