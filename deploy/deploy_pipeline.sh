#!/bin/bash
# deploy_pipeline.sh

MODEL_PATH=$1
MODEL_NAME=$2
VERSION_OR_STAGE=${3:-"Production"} # Default to Production stage if not provided
DOWNLOAD_PATH=${4:-"./models"} # Default download path

if [ -z "$MODEL_PATH" ] || [ -z "$MODEL_NAME" ]; then
  echo "Usage: $0 <model_path> <model_name> [version_or_stage] [download_path]"
  exit 1
fi

echo "Starting deployment pipeline for model: $MODEL_NAME"

# Step 1: Upload model to MLflow
echo "Uploading model..."
python deploy/upload_model.py --model_path "$MODEL_PATH" --model_name "$MODEL_NAME"
if [ $? -ne 0 ]; then
  echo "Model upload failed!"
  exit 1
fi

# Step 2: (Optional) Tag/Register model in MLflow as Production/Staging
# This step depends on MLflow Model Registry setup and permissions
# mlflow models create-version --name $MODEL_NAME --source runs:/<run_id>/model --tags key=value
# mlflow models transition-stage --name $MODEL_NAME --version <version> --stage Production

# Step 3: Download model to API server location
echo "Downloading model to API server..."
mkdir -p "$DOWNLOAD_PATH"
python deploy/download_model.py --model_name "$MODEL_NAME" --version_or_stage "$VERSION_OR_STAGE" --download_path "$DOWNLOAD_PATH"
if [ $? -ne 0 ]; then
  echo "Model download failed!"
  exit 1
fi

# Step 4: Restart API server (if running in container, rebuild/restart container)
# This step depends on how the API server is deployed (Docker Compose, Kubernetes, etc.)
# Example for Docker Compose:
# echo "Restarting API server..."
# docker-compose restart api-server
# Or, if using Kubernetes:
# kubectl rollout restart deployment/api-server-deployment

echo "Deployment pipeline completed successfully for model: $MODEL_NAME"
