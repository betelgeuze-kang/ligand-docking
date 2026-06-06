#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from deploy.model_registry import default_version, publish_model_artifact


def _metadata(path: str) -> dict[str, Any]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("metadata JSON must contain an object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a signed model artifact to the product model registry.")
    parser.add_argument("--model_path", required=True, help="Path to the model artifact file.")
    parser.add_argument("--model_name", required=True, help="Registry model name.")
    parser.add_argument("--version", default="", help="Registry version. Defaults to a UTC timestamp.")
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
        help="Signing key identifier recorded in manifests.",
    )
    parser.add_argument("--metadata-json", default="", help="Optional JSON object with operator metadata.")
    args = parser.parse_args()

    manifest = publish_model_artifact(
        model_path=args.model_path,
        model_name=args.model_name,
        version=args.version or default_version(),
        registry_dir=args.registry_dir,
        signing_key=args.signing_key,
        key_id=args.key_id,
        metadata=_metadata(args.metadata_json),
    )
    print(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
