#!/usr/bin/env python3
"""Audit every GitHub Actions workflow for immutable external action pins."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Sequence

import yaml

WORKFLOW_DIR = Path(".github/workflows")
FULL_SHA_ACTION = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _external_uses(value: Any) -> str:
    uses = str(value or "").strip()
    if not uses or uses.startswith("./") or uses.startswith("docker://"):
        return ""
    return uses


def _job_action_references(job: dict[str, Any]) -> Iterable[tuple[str, str]]:
    reusable = _external_uses(job.get("uses"))
    if reusable:
        yield "job", reusable
    steps = job.get("steps", [])
    if not isinstance(steps, list):
        return
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        uses = _external_uses(step.get("uses"))
        if uses:
            yield f"step-{index}", uses


def audit_all_action_pins(root: str | Path) -> list[str]:
    """Return stable errors for every mutable external Action reference."""

    workflow_dir = Path(root) / WORKFLOW_DIR
    errors: list[str] = []
    for path in sorted(workflow_dir.glob("*.y*ml")):
        workflow = _load(path)
        jobs = workflow.get("jobs", {})
        if not isinstance(jobs, dict):
            errors.append(f"{path.name}:jobs_not_mapping")
            continue
        for job_id, raw_job in jobs.items():
            if not isinstance(raw_job, dict):
                errors.append(f"{path.name}:{job_id}:job_not_mapping")
                continue
            for location, uses in _job_action_references(raw_job):
                if FULL_SHA_ACTION.fullmatch(uses) is None:
                    errors.append(
                        f"{path.name}:{job_id}:{location}:action_not_sha_pinned:{uses}"
                    )
    return sorted(set(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = audit_all_action_pins(args.root)
    if errors:
        print("github_action_pin_status=blocked")
        for error in errors:
            print(f"violation={error}")
        return 1
    print("github_action_pin_status=pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
