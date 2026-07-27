#!/usr/bin/env python3
"""Fail closed when the Engine v2 stacked CI boundary becomes incomplete.

The checker enforces a read-only workflow set, rejects temporary/self-modifying
CI, and requires the aggregate top-stack workflow to run both on pull requests
and on the exact post-merge ``main`` head without path filters.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
TOP_STACK_WORKFLOW = "ci-engine-v2-top-stack.yml"
TARGET_WORKFLOWS = (
    "ci-engine-v2-public-benchmark-protocol.yml",
    "ci-engine-v2-package.yml",
    "ci-engine-v2-top-stack.yml",
)
REDUNDANT_STACK_WORKFLOWS = (
    "ci-engine-v2-truthfulness.yml",
    "ci-engine-v2-evidence-contracts.yml",
    "ci-engine-v2-offline-public-evaluator.yml",
    "ci-engine-v2-trusted-revocation.yml",
    "ci-engine-v2-runtime-path-integrity.yml",
    "ci-engine-v2-source-snapshot.yml",
    "ci-engine-v2-authenticated-public-evaluator.yml",
    "ci-engine-v2-evidence-contracts-v3.yml",
    "ci-engine-v2-correctness-round1.yml",
    "ci-engine-v2-evaluator-round2.yml",
    "ci-engine-v2-molecular-round3.yml",
    "ci-engine-v2-docking-authority-round4.yml",
    "ci-engine-v2-release-integration-round5.yml",
    "ci-engine-v2-pocket-placement-round6.yml",
    "ci-engine-v2-element-contact-round8.yml",
    "ci-engine-v2-interpretable-scorer-round10.yml",
    "ci-engine-v2-interpretable-result-round12.yml",
    "ci-engine-v2-canonical-cli-round14.yml",
    "ci-engine-v2-sparse-base-validity-round16.yml",
    "ci-engine-v2-cli-result-verifier-round18.yml",
    "ci-engine-v2-cli-result-verifier-package-round19.yml",
    "ci-engine-v2-search-fingerprint-material-round20.yml",
    "ci-engine-v2-reference-pocket-round22.yml",
    "ci-engine-v2-reference-pocket-release-round23.yml",
    "ci-engine-v2-input-bound-verifier-round24.yml",
    "ci-engine-v2-input-bound-verifier-release-round25.yml",
    "ci-engine-v2-execution-parameter-attestation-round26.yml",
    "ci-engine-v2-execution-parameter-release-round27.yml",
    "ci-engine-v2-scorer-source-observation-round28.yml",
    "ci-engine-v2-scorer-source-observation-release-round29.yml",
)
FORBIDDEN_SOURCE_FRAGMENTS = (
    "contents: write",
    "actions: write",
    "persist-credentials: true",
    "git push",
    "git commit",
    "--write",
)
FORBIDDEN_NAME_FRAGMENTS = (
    "sync-once",
    "finalize-once",
    "rebuild-once",
    "dispatch-",
    "debug-",
    "codex-",
)
_REQUIRED_TOP_STACK_TRIGGER = (
    'on:\n'
    '  pull_request:\n'
    '  push:\n'
    '    branches: ["main"]\n'
    '  workflow_dispatch:\n'
)


class TopStackCheckError(RuntimeError):
    """The top-stack CI boundary is incomplete or self-modifying."""


def _check_workflow(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    if "permissions:\n  contents: read" not in source:
        raise TopStackCheckError(f"{path.name} is not explicitly read-only")
    for fragment in FORBIDDEN_SOURCE_FRAGMENTS:
        if fragment in source:
            raise TopStackCheckError(
                f"{path.name} contains forbidden fragment {fragment!r}"
            )
    if "actions/checkout@" in source and "persist-credentials: false" not in source:
        raise TopStackCheckError(
            f"{path.name} checkout does not disable credential persistence"
        )
    return source


def _check_top_stack_trigger(source: str) -> None:
    if _REQUIRED_TOP_STACK_TRIGGER not in source:
        raise TopStackCheckError(
            "top-stack workflow must run on pull requests, exact main pushes, "
            "and manual dispatch"
        )
    trigger_section = source.split("permissions:", 1)[0]
    if "paths:" in trigger_section or "paths-ignore:" in trigger_section:
        raise TopStackCheckError(
            "top-stack workflow trigger must not have path-filter gaps"
        )


def main() -> int:
    missing = []
    top_stack_source = ""
    for name in TARGET_WORKFLOWS:
        path = WORKFLOW_ROOT / name
        if not path.is_file():
            missing.append(name)
            continue
        source = _check_workflow(path)
        if name == TOP_STACK_WORKFLOW:
            top_stack_source = source
    if missing:
        raise TopStackCheckError(
            "required top-stack workflows are missing: " + ", ".join(missing)
        )
    _check_top_stack_trigger(top_stack_source)
    redundant = sorted(
        name for name in REDUNDANT_STACK_WORKFLOWS if (WORKFLOW_ROOT / name).exists()
    )
    if redundant:
        raise TopStackCheckError(
            "redundant Engine v2 stack workflows remain: " + ", ".join(redundant)
        )
    temporary = sorted(
        path.name
        for path in WORKFLOW_ROOT.glob("*.yml")
        if any(fragment in path.name for fragment in FORBIDDEN_NAME_FRAGMENTS)
        and "engine-v2" in path.name
    )
    if temporary:
        raise TopStackCheckError(
            "temporary Engine v2 workflows remain: " + ", ".join(temporary)
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TopStackCheckError as exc:
        raise SystemExit(str(exc)) from exc
