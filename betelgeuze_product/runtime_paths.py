from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def repo_root() -> Path:
    env_root = str(os.environ.get("BETELGEUZE_REPO_ROOT", "") or "").strip()
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(path_like: str | Path) -> Path:
    path = Path(path_like)
    if path.is_absolute():
        return path
    return repo_root() / path
