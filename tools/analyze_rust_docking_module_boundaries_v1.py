#!/usr/bin/env python3
"""Create a review aid for splitting the large Rust docking runtime.

This is a lexical inventory, not a Rust parser.  It intentionally reports only
column-zero top-level items and grants no authority to move code automatically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

# Match common top-level Rust declarations, including pub(crate), unsafe/async
# functions, extern functions, generic impl blocks, and associated constants.
ITEM = re.compile(
    r"^(?P<prefix>pub(?:\([^)]*\))?\s+)?"
    r"(?:(?:async|unsafe)\s+)*(?:extern\s+\"[^\"]+\"\s+)?"
    r"(?P<kind>struct|enum|trait|impl|fn|const|static|type)\s+"
    r"(?P<name>(?:r#)?[A-Za-z_][A-Za-z0-9_]*|<[^\n{]+>)",
    re.MULTILINE,
)

GROUPS = {
    "prepared_input": ("Prepared", "Input", "Owned"),
    "producer": ("Producer", "Proposal", "Source", "Allocation"),
    "admission": ("Geometric", "Admission"),
    "rigid": ("Rigid", "Quaternion"),
    "torsion": ("Torsion", "Rotor"),
    "scorer": ("Scorer", "Score"),
    "validity": ("Validity", "Pose"),
    "ranking": ("Rank", "TopK"),
    "clustering": ("Cluster", "Rmsd", "RMSD"),
    "receipts": ("Receipt", "Sha256", "Projection", "Hash"),
    "ffi": ("Raw", "Descriptor", "as_raw", "from_raw"),
}


class ModuleBoundaryError(ValueError):
    """The requested Rust source cannot be inventoried safely."""


def classify(name: str) -> str:
    for group, fragments in GROUPS.items():
        if any(fragment in name for fragment in fragments):
            return group
    return "orchestration_or_types"


def analyze(path: Path) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ModuleBoundaryError(f"cannot read Rust source: {exc}") from exc
    if len(raw) > 16 * 1024 * 1024:
        raise ModuleBoundaryError("Rust source exceeds the 16 MiB analysis limit")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ModuleBoundaryError("Rust source is not UTF-8") from exc

    lines = text.splitlines()
    items = []
    for match in ITEM.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        name = match.group("name")
        items.append(
            {
                "line": line,
                "kind": match.group("kind"),
                "name": name,
                "suggested_module": classify(name),
            }
        )

    groups: dict[str, list[dict[str, object]]] = {}
    for item in items:
        groups.setdefault(str(item["suggested_module"]), []).append(item)

    return {
        "schema_id": "betelgeuze.rust_docking_module_boundary_analysis/1.0.0",
        "path": str(path),
        "source_sha256": __import__("hashlib").sha256(raw).hexdigest(),
        "line_count": len(lines),
        "byte_count": len(raw),
        "top_level_item_count": len(items),
        "groups": groups,
        "limitations": {
            "lexical_inventory_only": True,
            "automatic_source_move_allowed": False,
            "macro_expansion_observed": False,
        },
        "authority": {
            "abi_change_authorized": False,
            "receipt_change_authorized": False,
            "scientific_change_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("rust/betelgeuze-runtime/src/docking.rs"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = analyze(args.path)
    except ModuleBoundaryError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            raise SystemExit("output must be absent")
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
