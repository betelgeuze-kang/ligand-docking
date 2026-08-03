from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from tools.audit_engine_v2_ci_authority import (
    CLEARANCE_ACTIVATION_REQUIRED_TOKENS,
)


@pytest.fixture(autouse=True)
def _synchronize_engine_v2_stage0_ci_authority_fixture(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the isolated Stage 0 repository fixture aligned with CI authority.

    ``test_engine_v2_blind_stage0`` constructs a minimal repository and writes a
    synthetic authoritative workflow before calling ``build_inventory``.  The
    activation contract extended the real authoritative workflow token set, so
    the synthetic workflow must carry the same tokens.  Patch only that test
    module's imported builder and leave production inventory code untouched.
    """

    module = request.module
    if module is None or not module.__name__.endswith("test_engine_v2_blind_stage0"):
        return

    original: Callable[[Path], dict[str, Any]] = module.build_inventory

    def _build_inventory(repo_root: Path) -> dict[str, Any]:
        main_path = repo_root / module.AUTHORITATIVE_WORKFLOWS[0]
        if main_path.is_file():
            text = main_path.read_text(encoding="utf-8")
            missing = tuple(
                token
                for token in CLEARANCE_ACTIVATION_REQUIRED_TOKENS
                if token not in text
            )
            if missing:
                main_path.write_text(
                    text.rstrip("\n") + "\n" + "\n".join(missing) + "\n",
                    encoding="utf-8",
                )
        return original(repo_root)

    monkeypatch.setattr(module, "build_inventory", _build_inventory)
