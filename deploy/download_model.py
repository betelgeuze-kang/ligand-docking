#!/usr/bin/env python3
"""
Download a model from MLflow.
"""

import torch
import argparse
import os
import shutil

try:
    import mlflow
except ImportError:
    mlflow = None

def download_model(model_name, version_or_stage, download_path):
    """
    Downloads a model from MLflow.
    Args:
        model_name (str): Name of the registered model.
        version_or_stage (str): Version number (e.g., '1') or stage (e.g., 'Production').
        download_path (str): Local path to save the model.
    """
    if mlflow is None:
        raise ImportError("mlflow is required to download models. Install mlflow first.")

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
    mlflow.set_tracking_uri(tracking_uri)

    # Construct model URI
    if version_or_stage.isdigit():
        model_uri = f"models:/{model_name}/{version_or_stage}"
    else:
        # Stage (e.g., Production, Staging) - requires Model Registry
        model_uri = f"models:/{model_name}@{version_or_stage}"

    # Download model artifacts
    local_path = mlflow.artifacts.download_artifacts(artifact_uri=model_uri)
    print(f"Downloaded model artifacts to: {local_path}")

    # Find and copy the specific model file (e.g., model.pth) to the desired location
    # This depends on how the model was saved in MLflow
    # Example: Find and copy the .pth file
    model_file_found = False
    for root, dirs, files in os.walk(local_path):
        for file in files:
            if file.endswith('.pth'):
                source_path = os.path.join(root, file)
                dest_path = os.path.join(download_path, file)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(source_path, dest_path)
                print(f"Copied model file to: {dest_path}")
                model_file_found = True
                break # Stop after finding the first .pth file
        if model_file_found:
            break

    if not model_file_found:
        print(f"Warning: No .pth file found in downloaded artifacts: {local_path}")
        # Handle case where no model file is found
        # You might want to look for a specific file name or structure defined during upload
        # For example, if the model was saved using mlflow.pytorch.log_model with a specific artifact_path
        # You might need to adjust the path accordingly
        # Example: Look for 'model/data/model.pth' inside the downloaded artifacts
        expected_path = os.path.join(local_path, "model", "data", "model.pth")
        if os.path.exists(expected_path):
             dest_path = os.path.join(download_path, "model.pth")
             os.makedirs(os.path.dirname(dest_path), exist_ok=True)
             shutil.copy(expected_path, dest_path)
             print(f"Copied model file (from expected path) to: {dest_path}")
        else:
             print(f"Error: Expected model file not found at: {expected_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download a model from MLflow.')
    parser.add_argument('--model_name', type=str, required=True, help='Name of the registered model')
    parser.add_argument('--version_or_stage', type=str, required=True, help='Version (e.g., 1) or Stage (e.g., Production)')
    parser.add_argument('--download_path', type=str, required=True, help='Local path to save the model')

    args = parser.parse_args()

    download_model(args.model_name, args.version_or_stage, args.download_path)
