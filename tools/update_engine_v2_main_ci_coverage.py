#!/usr/bin/env python3
"""Render or verify canonical Engine v2 main-CI coverage for current contracts."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci-engine-v2-main.yml"

_TRIGGER_CAPABILITY_ANCHOR = (
    '      - "config/independent_engine_v2_capabilities.yaml"\n'
)
_TRIGGER_CAPABILITY_ADDITION = (
    '      - "config/independent_engine_v2_truthfulness_policy.json"\n'
)
_TRIGGER_TOOL_ANCHOR = '      - "tools/check_engine_v2_architecture.py"\n'
_TRIGGER_TOOL_ADDITIONS = (
    '      - "tools/check_engine_v2_truthfulness.py"\n'
    '      - "tools/update_engine_v2_truthfulness_state.py"\n'
    '      - "tools/update_engine_v2_main_ci_coverage.py"\n'
)
_TRIGGER_WORKFLOW_ANCHOR = (
    '      - ".github/workflows/ci-engine-v2-public-benchmark-protocol.yml"\n'
)
_TRIGGER_WORKFLOW_ADDITION = (
    '      - ".github/workflows/ci-engine-v2-truthfulness.yml"\n'
)

_SPARSE_CAPABILITY_ANCHOR = (
    "            config/independent_engine_v2_capabilities.yaml\n"
)
_SPARSE_CAPABILITY_ADDITION = (
    "            config/independent_engine_v2_truthfulness_policy.json\n"
)
_SPARSE_TOOL_ANCHOR = "            tools/check_engine_v2_architecture.py\n"
_SPARSE_TOOL_ADDITIONS = (
    "            tools/check_engine_v2_truthfulness.py\n"
    "            tools/update_engine_v2_truthfulness_state.py\n"
    "            tools/update_engine_v2_main_ci_coverage.py\n"
)
_SPARSE_TEST_ANCHOR = (
    "            tests/unit/test_engine_v2_public_benchmark_protocol.py\n"
)
_SPARSE_TEST_ADDITIONS = (
    "            tests/unit/test_engine_v2_public_benchmark_materializer.py\n"
    "            tests/unit/test_engine_v2_docking_integrity.py\n"
    "            tests/unit/test_engine_v2_docking_root_positions.py\n"
    "            tests/unit/test_engine_v2_docking_validity_selection.py\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_dependency_identity.py\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_preimport_binding.py\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_bootstrap_e2e.py\n"
    "            tests/unit/test_engine_v2_truthfulness.py\n"
)
_SPARSE_DOC_ANCHOR = "            docs/engine_v2_status.md\n"
_SPARSE_DOC_ADDITION = "            docs/engine_v2_truthfulness.md\n"
_SPARSE_WORKFLOW_ANCHOR = (
    "            .github/workflows/ci-engine-v2-public-benchmark-protocol.yml\n"
)
_SPARSE_WORKFLOW_ADDITION = (
    "            .github/workflows/ci-engine-v2-truthfulness.yml\n"
)

_COMPILE_OLD = (
    "          python -m compileall -q betelgeuze_engine_v2 "
    "tools/build_engine_v2_wheel.py tools/check_engine_v2_architecture.py\n"
)
_COMPILE_NEW = (
    "          python -m compileall -q betelgeuze_engine_v2 "
    "tools/build_engine_v2_wheel.py tools/check_engine_v2_architecture.py "
    "tools/check_engine_v2_truthfulness.py "
    "tools/update_engine_v2_truthfulness_state.py "
    "tools/update_engine_v2_main_ci_coverage.py\n"
    "          python tools/update_engine_v2_main_ci_coverage.py --check\n"
    "          python tools/update_engine_v2_truthfulness_state.py --check\n"
    "          python tools/check_engine_v2_truthfulness.py\n"
)

_PYTEST_ANCHOR = (
    "            tests/unit/test_engine_v2_public_benchmark_protocol.py \\\n"
)
_PYTEST_ADDITIONS = (
    "            tests/unit/test_engine_v2_public_benchmark_materializer.py \\\n"
    "            tests/unit/test_engine_v2_docking_integrity.py \\\n"
    "            tests/unit/test_engine_v2_docking_root_positions.py \\\n"
    "            tests/unit/test_engine_v2_docking_validity_selection.py \\\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_dependency_identity.py \\\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_preimport_binding.py \\\n"
    "            tests/unit/test_engine_v2_reference_minimization_validation_bootstrap_e2e.py \\\n"
    "            tests/unit/test_engine_v2_truthfulness.py \\\n"
)


class MainCICoverageError(RuntimeError):
    """The canonical Engine v2 main workflow drifted from required coverage."""


def _ensure_after(
    source: str,
    *,
    anchor: str,
    additions: str,
    expected_count: int,
    name: str,
) -> str:
    addition_count = source.count(additions)
    if addition_count == expected_count:
        return source
    if addition_count != 0:
        raise MainCICoverageError(
            f"{name} is partially present: observed {addition_count}, expected {expected_count}"
        )
    anchor_count = source.count(anchor)
    if anchor_count != expected_count:
        raise MainCICoverageError(
            f"{name} anchor count is {anchor_count}, expected {expected_count}"
        )
    return source.replace(anchor, anchor + additions)


def render_main_workflow(source: str) -> str:
    rendered = _ensure_after(
        source,
        anchor=_TRIGGER_CAPABILITY_ANCHOR,
        additions=_TRIGGER_CAPABILITY_ADDITION,
        expected_count=2,
        name="truthfulness policy trigger",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_TRIGGER_TOOL_ANCHOR,
        additions=_TRIGGER_TOOL_ADDITIONS,
        expected_count=2,
        name="truthfulness tool triggers",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_TRIGGER_WORKFLOW_ANCHOR,
        additions=_TRIGGER_WORKFLOW_ADDITION,
        expected_count=2,
        name="truthfulness workflow triggers",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_SPARSE_CAPABILITY_ANCHOR,
        additions=_SPARSE_CAPABILITY_ADDITION,
        expected_count=1,
        name="truthfulness policy sparse checkout",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_SPARSE_TOOL_ANCHOR,
        additions=_SPARSE_TOOL_ADDITIONS,
        expected_count=1,
        name="truthfulness tools sparse checkout",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_SPARSE_TEST_ANCHOR,
        additions=_SPARSE_TEST_ADDITIONS,
        expected_count=1,
        name="new Engine v2 regression tests sparse checkout",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_SPARSE_DOC_ANCHOR,
        additions=_SPARSE_DOC_ADDITION,
        expected_count=1,
        name="truthfulness documentation sparse checkout",
    )
    rendered = _ensure_after(
        rendered,
        anchor=_SPARSE_WORKFLOW_ANCHOR,
        additions=_SPARSE_WORKFLOW_ADDITION,
        expected_count=1,
        name="truthfulness workflow sparse checkout",
    )
    if rendered.count(_COMPILE_NEW) == 1:
        pass
    elif rendered.count(_COMPILE_OLD) == 1:
        rendered = rendered.replace(_COMPILE_OLD, _COMPILE_NEW, 1)
    else:
        raise MainCICoverageError(
            "canonical compile/check step is missing, duplicated, or partially updated"
        )
    rendered = _ensure_after(
        rendered,
        anchor=_PYTEST_ANCHOR,
        additions=_PYTEST_ADDITIONS,
        expected_count=1,
        name="new Engine v2 regression tests execution",
    )
    return rendered


def require_main_workflow_coverage(source: str) -> None:
    rendered = render_main_workflow(source)
    if rendered != source:
        raise MainCICoverageError(
            "canonical Engine v2 main workflow is stale; run with --write"
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render or verify canonical Engine v2 main-CI coverage.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = WORKFLOW_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise MainCICoverageError(
            f"cannot read {WORKFLOW_PATH}"
        ) from exc
    rendered = render_main_workflow(source)
    if args.check:
        require_main_workflow_coverage(source)
        return 0
    if args.write:
        WORKFLOW_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        return 0
    assert args.output is not None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except MainCICoverageError as exc:
        raise SystemExit(str(exc)) from exc
