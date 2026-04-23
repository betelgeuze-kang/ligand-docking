#!/usr/bin/env python3
"""
Upload a trained model to MLflow or a model registry.
"""

import torch
import argparse
import os

try:
    import mlflow
except ImportError:
    mlflow = None

def upload_model(model_path, model_name, conda_env_path=None):
    """
    Uploads a model to MLflow.
    Args:
        model_path (str): Path to the saved model file (e.g., .pth).
        model_name (str): Name to register the model under in MLflow.
        conda_env_path (str, optional): Path to conda environment file.
    """
    if mlflow is None:
        raise ImportError("mlflow is required to upload models. Install mlflow first.")

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)

    # Load model (specific loading logic depends on how it was saved)
    # Example: If saved with torch.save(model.state_dict(), ...)
    # model_artifact = torch.load(model_path)
    # Example: If saved with torch.save(model, ...) (full model)
    model_artifact = torch.load(model_path, map_location='cpu') # Load on CPU for registration

    # Log model
    with mlflow.start_run():
        mlflow.pytorch.log_model(
            pytorch_model=model_artifact,
            artifact_path="model",
            conda_env=conda_env_path,
            code_paths=["core/", "theory/", "api/"] # Include relevant code
        )
        model_uri = f"runs:/{mlflow.active_run().info.run_id}/model"
        print(f"Model logged to MLflow: {model_uri}")

    # Register model (optional, requires Model Registry)
    # client = mlflow.MlflowClient()
    # client.create_model_version(name=model_name, source=model_uri)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Upload a model to MLflow.')
    parser.add_argument('--model_path', type=str, required=True, help='Path to the saved model file (.pth)')
    parser.add_argument('--model_name', type=str, required=True, help='Name to register the model')
    parser.add_argument('--conda_env', type=str, help='Path to conda environment file (optional)')

    args = parser.parse_args()

    upload_model(args.model_path, args.model_name, args.conda_env)
