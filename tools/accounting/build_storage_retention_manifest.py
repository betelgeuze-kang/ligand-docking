#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_OF_TRUTH_JSON = "runs/product_release_source_of_truth_gate_current.json"
DEFAULT_OUT_JSON = "runs/storage_retention_manifest_current.json"
DEFAULT_OUT_CSV = "runs/storage_retention_manifest_current.csv"
DEFAULT_OUT_MD = "runs/storage_retention_manifest_current.md"

DEFAULT_INVENTORY_ROOTS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "runs",
        "current_release_ledgers_and_generated_history",
        "keep_current_source_of_truth_ledgers_then_review_historical_bulk",
        "operator_review_manifest_required",
        "Generated run ledgers and historical payloads are mixed; do not delete wholesale.",
    ),
    (
        "data",
        "input_reference_data",
        "keep_dataset_evidence_or_manifest_before_offload",
        "operator_review_manifest_required",
        "Reference/input data require provenance review before any cleanup or offload.",
    ),
    (
        "models",
        "model_checkpoint_assets",
        "keep_selected_checkpoint_receipts_and_review_training_intermediates",
        "operator_review_manifest_required",
        "Model assets need registry, sha256, and checkpoint provenance before cleanup.",
    ),
    (
        "casp17",
        "casp17_current_evidence_and_historical_probes",
        "keep_final_target_object_viewer_manifests_then_review_historical_probes",
        "operator_review_manifest_required",
        "CASP17 current target/object/viewer evidence must be preserved.",
    ),
    (
        ".git",
        "git_history",
        "keep_git_history",
        "do_not_rewrite_without_explicit_separate_approval",
        "Repository history is not a cleanup target in normal product retention work.",
    ),
    (
        "logs",
        "transient_logs",
        "preserve_summarized_evidence_then_delete_if_unreferenced",
        "delete_after_manifest_review",
        "Logs can be cleaned only after any needed summary is preserved.",
    ),
    (
        ".pytest_cache",
        "regenerable_cache",
        "delete_when_disk_pressure_blocks_work",
        "regenerable_cache",
        "Pytest cache is regenerable and not product evidence.",
    ),
    (
        "__pycache__",
        "regenerable_cache",
        "delete_when_disk_pressure_blocks_work",
        "regenerable_cache",
        "Python bytecode cache is regenerable and not product evidence.",
    ),
    (
        "test-results",
        "transient_test_output",
        "preserve_relevant_summary_then_delete_if_unreferenced",
        "delete_after_manifest_review",
        "Test output directories are not source-of-truth evidence unless referenced by current gates.",
    ),
    (
        "tmp",
        "transient_workspace_scratch",
        "delete_if_unreferenced_and_not_user_payload",
        "delete_after_manifest_review",
        "Repository-local scratch should not store essential evidence.",
    ),
)

PATH_KEY_FRAGMENTS = (
    "path",
    "paths",
    "artifact",
    "artifacts",
    "json",
    "csv",
    "md",
    "manifest",
    "template",
    "intake",
    "source",
)

CLAIM_BOUNDARY = (
    "Storage retention manifest only; it inventories local paths and current source-of-truth references "
    "to support a later operator-approved cleanup review. It does not delete, move, archive, externalize, "
    "rewrite git history, upload, commit, push, or mutate external state."
)


def _resolve(path_like: str | Path, *, root: Path = ROOT) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else root / path


def _display(path: Path, *, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path_like: str | Path, *, root: Path) -> tuple[dict[str, Any], bool]:
    path = _resolve(path_like, root=root)
    if not path.is_file():
        return {}, False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (payload if isinstance(payload, dict) else {}), True


def _size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        result = subprocess.run(
            ["du", "-sb", str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return int(result.stdout.split()[0])
    except (OSError, subprocess.CalledProcessError, IndexError, ValueError):
        if path.is_file():
            return path.stat().st_size
        total = 0
        for child in path.rglob("*"):
            try:
                if child.is_file() or child.is_symlink():
                    total += child.lstat().st_size
            except OSError:
                continue
        return total


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def _looks_like_local_path(value: str) -> bool:
    text = value.strip()
    if not text or text.startswith(("http://", "https://", "mailto:")):
        return False
    if any(char.isspace() for char in text):
        return False
    return "/" in text or text.startswith(".") or "." in Path(text).name


def _path_parts(value: Any) -> list[str]:
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            output.extend(_path_parts(item))
        return output
    if isinstance(value, dict):
        output: list[str] = []
        for item in value.values():
            output.extend(_path_parts(item))
        return output
    text = _text(value)
    if not text:
        return []
    return [part.strip() for part in text.replace(",", ";").split(";") if _looks_like_local_path(part)]


def _collect_path_values(value: Any, *, parent_key: str = "") -> list[str]:
    output: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(fragment in key_text for fragment in PATH_KEY_FRAGMENTS):
                output.extend(_path_parts(item))
            if isinstance(item, (dict, list)):
                output.extend(_collect_path_values(item, parent_key=key_text))
    elif isinstance(value, list):
        for item in value:
            output.extend(_collect_path_values(item, parent_key=parent_key))
    return output


def _source_of_truth_references(source_of_truth: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()
    for ref in _collect_path_values(source_of_truth):
        normalized = ref.lstrip("./")
        if normalized in seen:
            continue
        seen.add(normalized)
        refs.append(normalized)
    return refs


def _refs_under_path(refs: list[str], rel_path: str) -> list[str]:
    prefix = rel_path.rstrip("/")
    return sorted(ref for ref in refs if ref == prefix or ref.startswith(f"{prefix}/"))


def _disposition_is_cleanup_candidate(disposition: str) -> bool:
    return disposition in {
        "delete_after_manifest_review",
        "regenerable_cache",
    }


def build_storage_retention_manifest(
    *,
    root: str | Path = ROOT,
    source_of_truth_json: str | Path = DEFAULT_SOURCE_OF_TRUTH_JSON,
    inventory_roots: tuple[tuple[str, str, str, str, str], ...] = DEFAULT_INVENTORY_ROOTS,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    source_of_truth, source_of_truth_present = _read_json(source_of_truth_json, root=root_path)
    refs = _source_of_truth_references(source_of_truth)
    rows: list[dict[str, Any]] = []
    for rel_path, retention_class, keep_policy, cleanup_disposition, reason in inventory_roots:
        path = _resolve(rel_path, root=root_path)
        exists = path.exists()
        size = _size_bytes(path)
        path_refs = _refs_under_path(refs, rel_path)
        cleanup_candidate = bool(
            exists
            and _disposition_is_cleanup_candidate(cleanup_disposition)
            and not path_refs
        )
        essential_evidence_manifest_required = bool(
            exists
            and cleanup_disposition == "operator_review_manifest_required"
            and not path_refs
        )
        operator_approval_required = bool(
            exists
            and cleanup_disposition
            in {"operator_review_manifest_required", "delete_after_manifest_review"}
        )
        rows.append(
            {
                "path": rel_path,
                "exists": exists,
                "size_bytes": size,
                "size_human": _human_size(size),
                "retention_class": retention_class,
                "keep_policy": keep_policy,
                "cleanup_disposition": cleanup_disposition,
                "cleanup_candidate": cleanup_candidate,
                "essential_evidence_manifest_required": essential_evidence_manifest_required,
                "source_of_truth_reference_count": len(path_refs),
                "source_of_truth_references": ";".join(path_refs[:20]),
                "source_of_truth_references_truncated": len(path_refs) > 20,
                "operator_approval_required": operator_approval_required,
                "delete_allowed_by_this_tool": False,
                "archive_executed": False,
                "externalize_executed": False,
                "external_state_mutated": False,
                "reason": reason,
            }
        )
    existing_rows = [row for row in rows if row["exists"]]
    cleanup_rows = [row for row in rows if row["cleanup_candidate"]]
    essential_manifest_rows = [row for row in rows if row["essential_evidence_manifest_required"]]
    referenced_rows = [row for row in rows if row["source_of_truth_reference_count"]]
    largest = max(existing_rows, key=lambda row: int(row["size_bytes"]), default={})
    cleanup_candidate_size = sum(int(row["size_bytes"]) for row in cleanup_rows)
    essential_manifest_size = sum(int(row["size_bytes"]) for row in essential_manifest_rows)
    summary = {
        "packet_type": "storage_retention_manifest",
        "status": "storage_retention_manifest_ready",
        "source_of_truth_json": _display(_resolve(source_of_truth_json, root=root_path), root=root_path),
        "source_of_truth_present": source_of_truth_present,
        "source_of_truth_reference_count": len(refs),
        "inventory_path_count": len(rows),
        "existing_path_count": len(existing_rows),
        "referenced_path_count": len(referenced_rows),
        "cleanup_candidate_count": len(cleanup_rows),
        "cleanup_candidate_size_bytes": cleanup_candidate_size,
        "cleanup_candidate_size_human": _human_size(cleanup_candidate_size),
        "essential_evidence_manifest_required_count": len(essential_manifest_rows),
        "essential_evidence_manifest_required_size_bytes": essential_manifest_size,
        "essential_evidence_manifest_required_size_human": _human_size(essential_manifest_size),
        "essential_evidence_manifest_required_paths": ";".join(row["path"] for row in essential_manifest_rows),
        "operator_approval_required_count": sum(1 for row in rows if row["operator_approval_required"]),
        "delete_allowed_count": 0,
        "largest_path": _text(largest.get("path")),
        "largest_path_size_bytes": int(largest.get("size_bytes") or 0),
        "largest_path_size_human": _text(largest.get("size_human")),
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Build compact essential-evidence manifests for protected review paths before any cleanup request."
            if essential_manifest_rows
            else "Review cleanup_candidate rows and preserve compact manifests before requesting operator approval."
            if cleanup_rows
            else "No unreferenced cleanup candidate was found in the configured inventory roots; inspect deeper manifests before deleting large evidence roots."
        ),
    }
    return {"summary": summary, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Storage Retention Manifest",
        "",
        f"- status: `{s['status']}`",
        f"- source_of_truth_json: `{s['source_of_truth_json']}`",
        f"- source_of_truth_present: `{s['source_of_truth_present']}`",
        f"- source_of_truth_reference_count: `{s['source_of_truth_reference_count']}`",
        f"- inventory_path_count: `{s['inventory_path_count']}`",
        f"- existing_path_count: `{s['existing_path_count']}`",
        f"- referenced_path_count: `{s['referenced_path_count']}`",
        f"- cleanup_candidate_count: `{s['cleanup_candidate_count']}`",
        f"- cleanup_candidate_size_human: `{s['cleanup_candidate_size_human']}`",
        f"- essential_evidence_manifest_required_count: `{s['essential_evidence_manifest_required_count']}`",
        f"- essential_evidence_manifest_required_size_human: `{s['essential_evidence_manifest_required_size_human']}`",
        f"- largest_path: `{s['largest_path']}`",
        f"- largest_path_size_human: `{s['largest_path_size_human']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Paths",
        "",
        "| path | size | class | disposition | refs | cleanup_candidate | essential_manifest_required |",
        "| --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['path']}` | `{row['size_human']}` | `{row['retention_class']}` | "
            f"`{row['cleanup_disposition']}` | `{row['source_of_truth_reference_count']}` | "
            f"`{row['cleanup_candidate']}` | `{row['essential_evidence_manifest_required']}` |"
        )
    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only storage retention manifest.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--source-of-truth-json", default=DEFAULT_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    payload = build_storage_retention_manifest(
        root=root,
        source_of_truth_json=args.source_of_truth_json,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
