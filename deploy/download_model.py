#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from deploy.model_registry import download_model_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify a signed product model artifact.")
    parser.add_argument("--model_name", required=True, help="Registry model name.")
    parser.add_argument(
        "--version_or_stage",
        required=True,
        help="Version, or one of current/latest/Production.",
    )
    parser.add_argument("--download_path", required=True, help="Local path to receive the model artifact.")
    parser.add_argument(
        "--registry-dir",
        default=os.getenv("MODEL_REGISTRY_DIR", "model_registry"),
        help="Filesystem model registry root.",
    )
    parser.add_argument(
        "--signing-key",
        default=os.getenv("MODEL_REGISTRY_SIGNING_KEY", ""),
        help="HMAC signing key. Prefer MODEL_REGISTRY_SIGNING_KEY.",
    )
    args = parser.parse_args()

    result = download_model_artifact(
        model_name=args.model_name,
        version_or_stage=args.version_or_stage,
        registry_dir=args.registry_dir,
        download_path=args.download_path,
        signing_key=args.signing_key,
    )
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
