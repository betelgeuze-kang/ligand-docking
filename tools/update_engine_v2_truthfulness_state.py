#!/usr/bin/env python3
"""Render or verify current capability accounting after implementation closure."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES_PATH = ROOT / "betelgeuze_engine_v2" / "capabilities.py"
CAPABILITY_YAML_PATH = ROOT / "config" / "independent_engine_v2_capabilities.yaml"

_OLD_PYTHON_STATE = '''                current_state=(
                    "frozen_four_case_public_redocking_protocol_definition_"
                    "without_execution_or_results"
                ),'''
_NEW_PYTHON_STATE = '''                current_state=(
                    "frozen_four_case_public_redocking_protocol_with_"
                    "result_free_input_materializer_without_execution_or_results"
                ),'''
_OLD_PYTHON_BLOCKERS = '''        "symmetry_mapping_materializer_not_implemented",
        "reference_ligand_match_materializer_not_implemented",
'''

_OLD_YAML_STATE = (
    "    current_state: "
    "frozen_four_case_public_redocking_protocol_definition_without_execution_or_results\n"
)
_NEW_YAML_STATE = (
    "    current_state: "
    "frozen_four_case_public_redocking_protocol_with_"
    "result_free_input_materializer_without_execution_or_results\n"
)
_OLD_YAML_BLOCKERS = '''      - symmetry_mapping_materializer_not_implemented
      - reference_ligand_match_materializer_not_implemented
'''


class StateUpdateError(RuntimeError):
    """The expected capability source shape drifted."""


def _replace_exactly_once(source: str, old: str, new: str, *, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise StateUpdateError(f"{name} expected exactly one match, observed {count}")
    return source.replace(old, new, 1)


def render_capabilities(source: str) -> str:
    rendered = _replace_exactly_once(
        source,
        _OLD_PYTHON_STATE,
        _NEW_PYTHON_STATE,
        name="Python public benchmark current_state",
    )
    rendered = _replace_exactly_once(
        rendered,
        _OLD_PYTHON_BLOCKERS,
        "",
        name="Python superseded public benchmark blockers",
    )
    return rendered


def render_capability_yaml(source: str) -> str:
    rendered = _replace_exactly_once(
        source,
        _OLD_YAML_STATE,
        _NEW_YAML_STATE,
        name="YAML public benchmark current_state",
    )
    rendered = _replace_exactly_once(
        rendered,
        _OLD_YAML_BLOCKERS,
        "",
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

    if args.check:
        if (
            _NEW_PYTHON_STATE not in source_python
            or _OLD_PYTHON_BLOCKERS in source_python
            or _NEW_YAML_STATE not in source_yaml
            or _OLD_YAML_BLOCKERS in source_yaml
        ):
            raise StateUpdateError(
                "capability truthfulness state is stale; run with --write"
            )
        return 0

    if args.write:
        _write(CAPABILITIES_PATH, render_capabilities(source_python))
        _write(CAPABILITY_YAML_PATH, render_capability_yaml(source_yaml))
        return 0

    assert args.output_dir is not None
    output_root = args.output_dir.resolve()
    _write(
        output_root / "betelgeuze_engine_v2" / "capabilities.py",
        render_capabilities(source_python),
    )
    _write(
        output_root / "config" / "independent_engine_v2_capabilities.yaml",
        render_capability_yaml(source_yaml),
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except StateUpdateError as exc:
        raise SystemExit(str(exc)) from exc
