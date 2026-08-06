from __future__ import annotations

from pathlib import Path, PurePosixPath

from tools.verify_product_capability_registry import load_registry


_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY_PATH = _REPO_ROOT / "config/product_capability_registry.json"


def test_every_capability_evidence_source_exists_in_the_reviewed_tree() -> None:
    registry = load_registry(_REGISTRY_PATH)
    missing: list[str] = []
    for capability in registry["capabilities"]:
        for raw_path in capability["evidence_source_paths"]:
            relative = PurePosixPath(raw_path)
            observed = _REPO_ROOT.joinpath(*relative.parts)
            if not observed.is_file():
                missing.append(f"{capability['capability_id']}:{raw_path}")

    assert missing == []
