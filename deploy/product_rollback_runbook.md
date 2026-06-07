# Product Rollback Runbook

- Keep the previous image digest and requirements-lock checksum beside each release bundle.
- Keep `MODEL_REGISTRY_SIGNING_KEY` and `MODEL_REGISTRY_KEY_ID` in operator-managed
  secret storage; never commit them to git or release evidence bundles.
- Roll back the signed model registry pointer before restarting services:

```bash
MODEL_REGISTRY_SIGNING_KEY="$MODEL_REGISTRY_SIGNING_KEY" \
python3 deploy/rollback_model.py \
  --model_name "$MODEL_NAME" \
  --target-version previous \
  --registry-dir "${MODEL_REGISTRY_DIR:-./model_registry}"
```

- Verify the restored artifact before service rollout:

```bash
MODEL_REGISTRY_SIGNING_KEY="$MODEL_REGISTRY_SIGNING_KEY" \
python3 deploy/download_model.py \
  --model_name "$MODEL_NAME" \
  --version_or_stage current \
  --registry-dir "${MODEL_REGISTRY_DIR:-./model_registry}" \
  --download_path "${MODEL_DOWNLOAD_PATH:-./models}"
```

- Redeploy the previous image digest and restore the previous `runs/` evidence bundle.
- Do not promote residual production mode during rollback; keep `default_residual_mode=shadow` unless a separate promotion gate is green.
- Verify `/metrics`, `/product/api-contract`, `/product/service-boundary`, and `/product/operations` after rollback.
- If artifact signature verification fails, keep the API server on the previous known-good
  image and do not restart workers against the suspect model artifact.
