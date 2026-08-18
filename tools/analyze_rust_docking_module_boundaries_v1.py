#!/usr/bin/env python3
"""Create a review aid for splitting the large Rust docking runtime.

The analyzer is read-only. It classifies top-level items into suggested modules
without changing ABI, receipts, scientific behavior, visibility, or authority.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ITEM = re.compile(
    r"^(?P<prefix>pub(?:\([^)]*\))?\s+)?"
    r"(?P<kind>struct|enum|trait|impl|fn|const|static|type)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)

GROUPS = {
    "prepared_input": ("Prepared", "Input", "Owned", "Cardinality"),
    "producer": ("Producer", "Proposal", "Source", "Allocation"),
    "admission": ("Geometric", "Admission"),
    "rigid": ("Rigid", "Quaternion", "Rotation"),
    "torsion": ("Torsion", "Rotor"),
    "scorer": ("Scorer", "Score"),
    "validity": ("Validity", "Pose"),
    "ranking": ("Rank", "TopK", "Topk"),
    "clustering": ("Cluster", "Rmsd", "RMSD"),
    "receipts": ("Receipt", "Sha256", "Projection", "Hash"),
    "ffi": ("Raw", "Descriptor", "as_raw", "from_raw", "Handle"),
}


def classify(name: str) -> str:
    for group, fragments in GROUPS.items():
        if any(fragment in name for fragment in fragments):
            return group
    return "orchestration_or_types"


def analyze(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
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
                "public": match.group("prefix") is not None,
                "suggested_module": classify(name),
            }
        )
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["suggested_module"], []).append(item)
    return {
        "schema_id": "betelgeuze.rust_docking_module_boundary_analysis/1.0.0",
        "path": str(path),
        "line_count": len(lines),
        "byte_count": len(text.encode("utf-8")),
        "top_level_item_count": len(items),
        "groups": groups,
        "recommended_sequence": [
            "constants_enums_pod_errors",
            "prepared_input_validation_and_owned_storage",
            "receipt_and_projection_canonicalization",
            "scorer_validity_ranking_clustering_replay",
            "producer_admission_rigid_torsion_replay",
            "orchestration_and_public_exports",
        ],
        "authority": {
            "abi_change_authorized": False,
            "receipt_change_authorized": False,
            "scientific_change_authorized": False,
            "performance_change_authorized": False,
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
    report = analyze(args.path)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            raise SystemExit("output must be absent")
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
