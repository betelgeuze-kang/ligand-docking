# Product Rollout Runbook

Use `deploy/product_rollout.py` to plan image build, optional push, and compose or
K8s rollout commands. The script is dry-run by default and requires the explicit
approval token `APPROVE_PRODUCT_ROLLOUT` before it can mutate external state.

Dry-run plan:

```bash
python3 deploy/product_rollout.py \
  --mode k8s \
  --image micf-api:product \
  --publish-image registry.example.com/micf-api:2026-06-06 \
  --push \
  --out-json runs/product_rollout_plan_current.json
```

Execute only after operator review of target, action, impact, risk, rollback, and
verification:

```bash
PRODUCT_ROLLOUT_APPROVAL_TOKEN=APPROVE_PRODUCT_ROLLOUT \
python3 deploy/product_rollout.py \
  --mode k8s \
  --image micf-api:product \
  --publish-image registry.example.com/micf-api:2026-06-06 \
  --push \
  --execute
```

Rollback:

- Redeploy the previous image digest recorded in the release bundle.
- Run `deploy/rollback_model.py` if the model registry pointer changed.
- Verify `/metrics`, `/product/api-contract`, `/product/service-boundary`, and
  `/product/operations`.
