#!/bin/bash
set -euo pipefail

MODEL_PATH=${1:-}
MODEL_NAME=${2:-}
MODEL_VERSION=${3:-$(date -u +"%Y%m%dT%H%M%SZ")}
DOWNLOAD_PATH=${4:-"./models"}
MODEL_REGISTRY_DIR=${MODEL_REGISTRY_DIR:-"./model_registry"}

if [ -z "$MODEL_PATH" ] || [ -z "$MODEL_NAME" ]; then
  echo "Usage: $0 <model_path> <model_name> [model_version] [download_path]"
  echo "Requires MODEL_REGISTRY_SIGNING_KEY. Optional: MODEL_REGISTRY_DIR, MODEL_REGISTRY_KEY_ID."
  exit 1
fi

echo "Starting deployment pipeline for model: $MODEL_NAME"

echo "Publishing signed model artifact..."
python3 deploy/upload_model.py \
  --model_path "$MODEL_PATH" \
  --model_name "$MODEL_NAME" \
  --version "$MODEL_VERSION" \
  --registry-dir "$MODEL_REGISTRY_DIR"

echo "Downloading and verifying current model artifact..."
mkdir -p "$DOWNLOAD_PATH"
python3 deploy/download_model.py \
  --model_name "$MODEL_NAME" \
  --version_or_stage current \
  --registry-dir "$MODEL_REGISTRY_DIR" \
  --download_path "$DOWNLOAD_PATH"

echo "Model registry pointer now targets version: $MODEL_VERSION"
echo "Operator must restart/roll out the API server after smoke verification."

echo "Deployment pipeline completed successfully for model: $MODEL_NAME"
