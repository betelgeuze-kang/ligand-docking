#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_JSON = "runs/tools_package_separation_work_order_current.json"
DEFAULT_OUT_CSV = "runs/tools_package_separation_work_order_current.csv"
DEFAULT_OUT_MD = "runs/tools_package_separation_work_order_current.md"

TARGET_PACKAGES = ("product", "cameo", "casp17", "wetlab", "cleanup", "gpcr_replay")
CLAIM_BOUNDARY = (
    "Tools package separation work order only; it inventories top-level tools/*.py files, proposes package buckets, "
    "and records import/test-reference risk before any move. It does not move files, rewrite imports, delete, archive, "
    "commit, push, or mutate external state."
)

PACKAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cameo": ("cameo",),
    "cleanup": ("cleanup", "archive", "externalize", "transition_cleanup"),
    "casp17": ("casp17", "casp", "massivefold", "lddt", "bisyrmsd", "dockq"),
    "wetlab": (
        "wetlab",
        "tcruzi",
        "cruzi",
        "cruzain",
        "dengue",
        "plpro",
        "stk17b",
        "lbdhodh",
        "krs1",
        "assay",
    ),
    "gpcr_replay": ("gpcr", "drd2", "oprm1", "htr2a", "adrb2", "a1_", "rank_rescue"),
    "product": (
        "product",
        "api_",
        "license",
        "public_benchmark",
        "lit_pcba",
        "rocm",
        "residual",
        "model_registry",
        "ligand_htvs",
        "ligand_scaleup",
        "ligand_trajectory",
        "transporter",
        "aqp",
        "glut1",
        "pxr",
        "ca2",
    ),
}


def _resolve(path_like: str | Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else ROOT / path


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _classify(stem: str) -> tuple[str, str]:
    normalized = stem.lower()
    for package in TARGET_PACKAGES:
        for keyword in PACKAGE_KEYWORDS[package]:
            if keyword in normalized:
                return package, keyword
    return "other_review", "no_keyword_match"


def _internal_tool_import_count(path: Path) -> int:
    text = _file_text(path)
    if not text:
        return 0
    return text.count("from tools import ") + text.count("from tools.") + text.count("import tools.") + text.count("tools.")


def _corpus(root: Path, *, recursive: bool = True) -> str:
    if not root.exists():
        return ""
    paths = root.rglob("*.py") if recursive else root.glob("*.py")
    return "\n".join(_file_text(path) for path in paths)


def _reference_count_from_corpus(path: Path, corpus: str) -> int:
    module_name = path.stem
    filename = path.name
    return (
        _count_token_occurrences(corpus, filename)
        + _count_token_occurrences(corpus, f"tools.{module_name}")
        + _count_token_occurrences(corpus, f"import {module_name}")
    )


def _token_boundary_ok(corpus: str, start: int, end: int) -> bool:
    before = corpus[start - 1] if start > 0 else ""
    after = corpus[end] if end < len(corpus) else ""
    if before and (before.isalnum() or before in {"_", ".", "-"}):
        return False
    if after and (after.isalnum() or after == "_"):
        return False
    return True


def _count_token_occurrences(corpus: str, token: str) -> int:
    count = 0
    start = 0
    while True:
        idx = corpus.find(token, start)
        if idx < 0:
            return count
        end = idx + len(token)
        if _token_boundary_ok(corpus, idx, end):
            count += 1
        start = end


def build_tools_package_separation_work_order(*, root: str | Path = ROOT, include_reference_counts: bool = True) -> dict[str, Any]:
    root_path = Path(root).resolve()
    tools_dir = root_path / "tools"
    test_dir = root_path / "tests"
    tool_files = sorted(path for path in tools_dir.glob("*.py") if path.is_file())
    test_corpus = _corpus(test_dir) if include_reference_counts else ""
    tool_corpus = _corpus(tools_dir, recursive=False) if include_reference_counts else ""
    rows: list[dict[str, Any]] = []
    for path in tool_files:
        package, matched_keyword = _classify(path.stem)
        internal_tool_import_count = _internal_tool_import_count(path)
        test_reference_count = _reference_count_from_corpus(path, test_corpus)
        tool_reference_count = _reference_count_from_corpus(path, tool_corpus)
        has_argparse = "argparse" in _file_text(path)
        risk_score = internal_tool_import_count + test_reference_count + max(tool_reference_count - 1, 0)
        if package == "other_review":
            risk_score += 2
        migration_batch = "batch_1_low_reference" if risk_score == 0 else ("batch_2_review" if risk_score <= 3 else "batch_3_high_reference")
        rows.append(
            {
                "tool_path": str(path.relative_to(root_path)),
                "proposed_package": package,
                "matched_keyword": matched_keyword,
                "migration_batch": migration_batch,
                "risk_score": risk_score,
                "internal_tool_import_count": internal_tool_import_count,
                "test_reference_count": test_reference_count,
                "tool_reference_count": tool_reference_count,
                "has_argparse_cli": has_argparse,
                "move_executed": False,
                "import_rewrite_executed": False,
                "external_state_mutated": False,
            }
        )

    package_counts = Counter(row["proposed_package"] for row in rows)
    batch_counts = Counter(row["migration_batch"] for row in rows)
    high_risk_count = sum(1 for row in rows if row["migration_batch"] == "batch_3_high_reference")
    status = "tools_package_separation_work_order_ready" if rows else "blocked_tools_package_separation_work_order"
    summary = {
        "packet_type": "tools_package_separation_work_order",
        "status": status,
        "tool_file_count": len(rows),
        "target_package_count": len(TARGET_PACKAGES),
        "classified_target_package_count": sum(package_counts.get(package, 0) for package in TARGET_PACKAGES),
        "other_review_count": package_counts.get("other_review", 0),
        "package_counts": dict(sorted(package_counts.items())),
        "batch_counts": dict(sorted(batch_counts.items())),
        "batch_1_low_reference_count": batch_counts.get("batch_1_low_reference", 0),
        "batch_2_review_count": batch_counts.get("batch_2_review", 0),
        "batch_3_high_reference_count": high_risk_count,
        "reference_counts_included": include_reference_counts,
        "move_executed": False,
        "import_rewrite_executed": False,
        "delete_executed": False,
        "archive_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review batch_1_low_reference rows first, then move tools by package with import rewrite tests in a separate approved refactor."
            if rows
            else "Create tools/*.py inventory before package separation planning."
        ),
    }
    package_rows = [
        {
            "proposed_package": package,
            "tool_count": package_counts.get(package, 0),
            "target_package": package in TARGET_PACKAGES,
            "move_executed": False,
            "external_state_mutated": False,
        }
        for package in [*TARGET_PACKAGES, "other_review"]
        if package_counts.get(package, 0)
    ]
    return {"summary": summary, "package_rows": package_rows, "rows": rows}


def _write_markdown(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = _resolve(path_like)
    s = payload["summary"]
    lines = [
        "# Tools Package Separation Work Order",
        "",
        f"- status: `{s['status']}`",
        f"- tool_file_count: `{s['tool_file_count']}`",
        f"- classified_target_package_count: `{s['classified_target_package_count']}`",
        f"- other_review_count: `{s['other_review_count']}`",
        f"- batch_1_low_reference_count: `{s['batch_1_low_reference_count']}`",
        f"- batch_2_review_count: `{s['batch_2_review_count']}`",
        f"- batch_3_high_reference_count: `{s['batch_3_high_reference_count']}`",
        f"- reference_counts_included: `{s['reference_counts_included']}`",
        f"- move_executed: `{s['move_executed']}`",
        f"- import_rewrite_executed: `{s['import_rewrite_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Package Counts",
        "",
        "| package | tools | target |",
        "| --- | ---: | --- |",
    ]
    for row in payload["package_rows"]:
        lines.append(f"| `{row['proposed_package']}` | `{row['tool_count']}` | `{row['target_package']}` |")
    lines.extend(
        [
            "",
            "## Migration Rows",
            "",
            "| tool | package | batch | risk | test refs | tool refs | imports |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in payload["rows"][:200]:
        lines.append(
            f"| `{row['tool_path']}` | `{row['proposed_package']}` | `{row['migration_batch']}` | "
            f"`{row['risk_score']}` | `{row['test_reference_count']}` | `{row['tool_reference_count']}` | "
            f"`{row['internal_tool_import_count']}` |"
        )
    if len(payload["rows"]) > 200:
        lines.append(f"| `...` | `truncated_in_markdown` | `{len(payload['rows']) - 200} additional rows in CSV/JSON` | `0` | `0` | `0` | `0` |")
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only tools package separation work order.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--include-reference-counts", action="store_true")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    payload = build_tools_package_separation_work_order(root=args.root, include_reference_counts=args.include_reference_counts)
    _write_json(args.out_json, payload)
    write_csv_rows(_resolve(args.out_csv), payload["rows"])
    _write_markdown(args.out_md, payload)


if __name__ == "__main__":
    main()
