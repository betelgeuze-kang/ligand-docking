#!/usr/bin/env python3
"""Inventory GitHub Actions pins and high-risk workflow contexts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)
SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def inspect(root: Path) -> dict:
    workflows = root / ".github/workflows"
    rows = []
    for path in sorted(workflows.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        actions = []
        for token in USES.findall(text):
            if token.startswith("./"):
                kind, pinned = "local", True
                owner_action, ref = token, None
            elif token.startswith("docker://"):
                kind, pinned = "docker", "@sha256:" in token
                owner_action, ref = token, None
            elif "@" in token:
                owner_action, ref = token.rsplit("@", 1)
                kind, pinned = "remote", SHA.fullmatch(ref) is not None
            else:
                owner_action, ref = token, None
                kind, pinned = "invalid", False
            actions.append({
                "uses": token, "kind": kind, "ref": ref,
                "exact_sha_pinned": pinned,
            })
        rows.append({
            "path": str(path.relative_to(root)),
            "pull_request_target": "pull_request_target:" in text,
            "self_hosted": "self-hosted" in text,
            "sparse_checkout": "sparse-checkout:" in text,
            "workflow_call": "workflow_call:" in text,
            "actions": actions,
            "mutable_remote_count": sum(
                item["kind"] == "remote" and not item["exact_sha_pinned"]
                for item in actions
            ),
        })
    return {
        "schema_id": "betelgeuze.github_actions_pin_inventory/1.0.0",
        "workflow_count": len(rows),
        "workflows": rows,
        "mutable_remote_total": sum(row["mutable_remote_count"] for row in rows),
        "authority": {
            "workflow_update_authorized": False,
            "release_authorized": False,
            "scientific_claim_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.root.resolve())
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            raise SystemExit("output must be absent")
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 1 if report["mutable_remote_total"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
