from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_kiro_design_wrapper_injects_fixed_opus48_contract(tmp_path: Path) -> None:
    prompt = tmp_path / "kiro-design.md"
    prompt.write_text(
        "# Kiro Design\n\n## Goal\n\nPlan a tiny local-only implementation slice.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", "scripts/ai-design-kiro.sh", "--dry-run", str(prompt)],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stderr
    wrapped_prompt = (ROOT / ".betelgeuze/kiro_design_last_prompt.md").read_text(
        encoding="utf-8"
    )
    status = (ROOT / ".betelgeuze/kiro_design_last_status.txt").read_text(
        encoding="utf-8"
    )

    assert "Required model: Kiro Opus 4.8." in wrapped_prompt
    assert "KIRO_MODEL_CONFIRMED: Opus 4.8" in wrapped_prompt
    assert "If and only if the active Kiro model/session is Opus 4.8" in wrapped_prompt
    assert "You are in design-only mode." in wrapped_prompt
    assert "status=dry_run" in status
    assert "expected_model=Opus 4.8" in status
    assert "stdout_contract=first_non_empty_line_must_match_expected_marker" in status


def test_kiro_design_wrapper_blocks_model_substitution(tmp_path: Path) -> None:
    prompt = tmp_path / "kiro-design.md"
    prompt.write_text("# Kiro Design\n", encoding="utf-8")
    env = os.environ.copy()
    env["KIRO_EXPECTED_MODEL"] = "Sonnet"

    result = subprocess.run(
        ["bash", "scripts/ai-design-kiro.sh", "--dry-run", str(prompt)],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    assert result.returncode == 2
    assert "Kiro model is fixed to Opus 4.8" in result.stderr


def test_ai_verify_uses_unique_kiro_prompt_path() -> None:
    script = (ROOT / "scripts/ai-verify.sh").read_text(encoding="utf-8")

    assert "mktemp .betelgeuze/ai_verify_kiro_design_prompt." in script
    assert 'kiro_verify_prompt=".betelgeuze/ai_verify_kiro_design_prompt.md"' not in script
