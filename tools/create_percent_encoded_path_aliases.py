#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import quote


def _needs_alias(name: str) -> bool:
    return any(ord(ch) > 127 for ch in name)


def _encoded_name(name: str) -> str:
    return quote(name, safe="")


def create_aliases(root: Path, *, dry_run: bool = False) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.exists() or not _needs_alias(entry.name):
            continue
        encoded = _encoded_name(entry.name)
        if encoded == entry.name:
            continue
        alias = root / encoded
        if alias.exists() or alias.is_symlink():
            status = "already_present"
        else:
            status = "created"
            if not dry_run:
                os.symlink(entry, alias)
        actions.append(
            {
                "source": str(entry),
                "alias": str(alias),
                "status": status,
            }
        )
    return actions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create percent-encoded aliases for non-ASCII top-level paths so "
            "file-manager integrations that pass URL-escaped paths can still resolve them."
        )
    )
    parser.add_argument(
        "--root",
        default=str(Path.home()),
        help="Root directory to scan for non-ASCII top-level entries (default: $HOME).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report aliases without creating them.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    actions = create_aliases(root, dry_run=bool(args.dry_run))
    print(json.dumps({"root": str(root), "actions": actions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
