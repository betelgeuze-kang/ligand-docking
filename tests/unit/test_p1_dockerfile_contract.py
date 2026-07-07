from __future__ import annotations

import re
from pathlib import Path


def test_product_dockerfile_copy_sources_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = root / "Dockerfile.product"
    text = dockerfile.read_text(encoding="utf-8")

    assert "ARG PRODUCT_ROCM_BASE=" in text
    assert "PRODUCT_API_AUTH_REQUIRED=1" in text
    assert "API_VALIDATED_RUNNER_ENABLED=0" in text
    assert "python tools/build_rust_hip_engine.py" in text

    missing: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("COPY "):
            continue
        parts = re.split(r"\s+", stripped)
        # This Dockerfile uses simple COPY forms without flags.
        if len(parts) < 3 or parts[1].startswith("--"):
            continue
        sources = parts[1:-1]
        for source in sources:
            if any(ch in source for ch in "*?["):
                continue
            if not (root / source).exists():
                missing.append(source)
    assert missing == []
