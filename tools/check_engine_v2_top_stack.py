#!/usr/bin/env python3
"""Fail closed when the Engine v2 stacked CI boundary becomes self-modifying."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
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


class TopStackCheckError(RuntimeError):
    """The top-stack CI boundary is incomplete or self-modifying."""


def _check_workflow(path: Path) -> None:
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


def main() -> int:
    missing = []
    for name in TARGET_WORKFLOWS:
        path = WORKFLOW_ROOT / name
        if not path.is_file():
            missing.append(name)
            continue
        _check_workflow(path)
    if missing:
        raise TopStackCheckError(
            "required top-stack workflows are missing: " + ", ".join(missing)
        )
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
