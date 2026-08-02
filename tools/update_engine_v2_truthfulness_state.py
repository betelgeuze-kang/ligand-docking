#!/usr/bin/env python3
"""Render or verify current capability accounting after implementation closure."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "betelgeuze_engine_v2" / "capabilities.py"
CAPABILITY_YAML_PATH = ROOT / "config" / "independent_engine_v2_capabilities.yaml"

_OLD_PYTHON_STATE = """                current_state=(
                    "frozen_four_case_public_redocking_protocol_definition_"
                    "without_execution_or_results"
                ),"""
_NEW_PYTHON_STATE = """                current_state=(
                    "historical_300_case_contaminated_development_with_fresh_"
                    "128_case_internal_provisional_blind_unexecuted_and_"
                    "active_v7_refiner"
                ),"""
_OLD_PYTHON_BLOCKERS = """        "symmetry_mapping_materializer_not_implemented",
        "reference_ligand_match_materializer_not_implemented",
"""

_OLD_YAML_STATE = (
    "    current_state: "
    "frozen_four_case_public_redocking_protocol_definition_without_execution_or_results\n"
)
_NEW_YAML_STATE = (
    "    current_state: "
    "historical_300_case_contaminated_development_with_fresh_"
    "128_case_internal_provisional_blind_unexecuted_and_active_v7_refiner\n"
)
_OLD_YAML_BLOCKERS = """      - symmetry_mapping_materializer_not_implemented
      - reference_ligand_match_materializer_not_implemented
"""


class StateUpdateError(RuntimeError):
    """The expected capability source shape drifted."""


def _replace_or_require_canonical(source: str, old: str, new: str, *, name: str) -> str:
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == 1 and new_count == 0:
        return source.replace(old, new, 1)
    if old_count == 0 and new_count == 1:
        return source
    raise StateUpdateError(
        f"{name} is ambiguous: legacy={old_count}, canonical={new_count}"
    )


def _remove_or_require_absent(source: str, old: str, *, name: str) -> str:
    count = source.count(old)
    if count == 1:
        return source.replace(old, "", 1)
    if count == 0:
        return source
    raise StateUpdateError(f"{name} expected at most one match, observed {count}")


def render_capabilities(source: str) -> str:
    rendered = _replace_or_require_canonical(
        source,
        _OLD_PYTHON_STATE,
        _NEW_PYTHON_STATE,
        name="Python public benchmark current_state",
    )
    rendered = _remove_or_require_absent(
        rendered,
        _OLD_PYTHON_BLOCKERS,
        name="Python superseded public benchmark blockers",
    )
    return rendered


def render_capability_yaml(source: str) -> str:
    rendered = _replace_or_require_canonical(
        source,
        _OLD_YAML_STATE,
        _NEW_YAML_STATE,
        name="YAML public benchmark current_state",
    )
    rendered = _remove_or_require_absent(
        rendered,
        _OLD_YAML_BLOCKERS,
        name="YAML superseded public benchmark blockers",
    )
    return rendered


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StateUpdateError(f"cannot read {path}") from exc


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render or verify Engine v2 capability truthfulness state.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--output-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    source_python = _read(CAPABILITIES_PATH)
    source_yaml = _read(CAPABILITY_YAML_PATH)

    rendered_python = render_capabilities(source_python)
    rendered_yaml = render_capability_yaml(source_yaml)

    if args.check:
        if rendered_python != source_python or rendered_yaml != source_yaml:
            raise StateUpdateError(
                "capability truthfulness state is stale; run with --write"
            )
        return 0

    if args.write:
        _write(CAPABILITIES_PATH, rendered_python)
        _write(CAPABILITY_YAML_PATH, rendered_yaml)
        return 0

    assert args.output_dir is not None
    output_root = args.output_dir.resolve()
    _write(
        output_root / "betelgeuze_engine_v2" / "capabilities.py",
        rendered_python,
    )
    _write(
        output_root / "config" / "independent_engine_v2_capabilities.yaml",
        rendered_yaml,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except StateUpdateError as exc:
        raise SystemExit(str(exc)) from exc
