#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os

from deploy.model_registry import rollback_model_version


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback the current product model registry pointer.")
    parser.add_argument("--model_name", required=True, help="Registry model name.")
    parser.add_argument(
        "--target-version",
        default="previous",
        help="Version to activate, or 'previous' to use the previous registry pointer.",
    )
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
    parser.add_argument(
        "--key-id",
        default=os.getenv("MODEL_REGISTRY_KEY_ID", "local-product-registry"),
        help="Signing key identifier recorded in registry index.",
    )
    args = parser.parse_args()

    index = rollback_model_version(
        model_name=args.model_name,
        target_version=args.target_version,
        registry_dir=args.registry_dir,
        signing_key=args.signing_key,
        key_id=args.key_id,
    )
    print(json.dumps(index, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
