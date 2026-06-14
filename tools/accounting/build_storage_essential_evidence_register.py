#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.accounting.build_storage_retention_manifest import (
    DEFAULT_SOURCE_OF_TRUTH_JSON,
    _display,
    _human_size,
    _read_json,
    _resolve,
    _source_of_truth_references,
)
from tools.builder_table_utils import write_csv_rows

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTECTED_ROOTS = ("models", "casp17")
DEFAULT_OUT_JSON = "runs/storage_essential_evidence_register_current.json"
DEFAULT_OUT_CSV = "runs/storage_essential_evidence_register_current.csv"
DEFAULT_OUT_MD = "runs/storage_essential_evidence_register_current.md"
DEFAULT_HASH_MAX_BYTES = 1 * 1024 * 1024
DEFAULT_HASH_ROW_LIMIT = 200

MODEL_SUFFIXES = {".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".pkl"}
COORDINATE_SUFFIXES = {".pdb", ".cif", ".mmcif", ".bcif", ".sdf", ".mol2", ".xyz"}
TABLE_SUFFIXES = {".json", ".csv", ".md", ".tsv", ".txt", ".yaml", ".yml"}
VIEWER_SUFFIXES = {".html", ".htm", ".obj", ".mtl", ".glb", ".gltf"}

HIGH_VALUE_TOKENS = (
    "current",
    "final",
    "selected",
    "promoted",
    "best",
    "manifest",
    "validation",
    "viewer",
    "object",
    "atlas",
    "sha256",
    "scorecard",
    "ledger",
    "receipt",
    "gate",
    "preflight",
    "decision",
)

CLAIM_BOUNDARY = (
    "Essential evidence register only; it inventories protected local roots so a later cleanup can "
    "keep selected checkpoints, final structures, viewer/object artifacts, manifests, validation "
    "reports, and provenance. It does not delete, move, archive, externalize, rewrite git history, "
    "upload, commit, push, run docking, or mutate external state."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_mtime_utc(path: Path) -> str:
    try:
        return f"{path.stat().st_mtime:.6f}"
    except OSError:
        return ""


def _root_domain(rel_path: str) -> str:
    parts = Path(rel_path).parts
    if len(parts) == 2:
        return f"{parts[0]}/_root_files"
    if len(parts) > 2:
        return "/".join(parts[:2])
    return rel_path


def _text_has_any(text: str, tokens: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(token in lower for token in tokens)


def _role_for_path(rel_path: str) -> tuple[str, str, str]:
    path = Path(rel_path)
    suffix = path.suffix.lower()
    lower = rel_path.lower()
    root = path.parts[0] if path.parts else ""

    if root == "models":
        if suffix in MODEL_SUFFIXES:
            return (
                "model_checkpoint_or_weight",
                "keep_until_model_registry_and_selected_checkpoint_review",
                "Compact register must identify selected/promoted checkpoints before any stale checkpoint cleanup.",
            )
        if suffix in TABLE_SUFFIXES or _text_has_any(lower, ("manifest", "registry", "sha256", "readme")):
            return (
                "model_manifest_or_registry",
                "keep_as_checkpoint_provenance",
                "Model metadata and registries are evidence for checkpoint selection and regeneration.",
            )
        return (
            "model_support_file",
            "review_after_model_register",
            "Support file under models requires provenance review before cleanup.",
        )

    if root == "casp17":
        if suffix in COORDINATE_SUFFIXES:
            return (
                "casp17_structure_coordinate",
                "keep_final_or_candidate_coordinate_until_target_register_review",
                "CASP17 coordinate files can be final, representative, native, or candidate evidence.",
            )
        if suffix in VIEWER_SUFFIXES or _text_has_any(lower, ("viewer", "object", "atlas", "gallery")):
            return (
                "casp17_viewer_or_object_artifact",
                "keep_current_viewer_object_and_navigation_evidence",
                "Viewer/object artifacts support inspection and delivery evidence.",
            )
        if suffix in TABLE_SUFFIXES and _text_has_any(lower, HIGH_VALUE_TOKENS):
            return (
                "casp17_manifest_validation_or_receipt",
                "keep_current_manifest_validation_receipt_and_decision_evidence",
                "CASP17 manifests, gates, ledgers, receipts, and validation reports are product evidence.",
            )
        if "current" in lower:
            return (
                "casp17_current_support_artifact",
                "keep_current_support_artifact_until_deeper_register_review",
                "Current CASP17 support artifacts should not be deleted without a target-level register.",
            )
        return (
            "casp17_historical_or_support_payload",
            "review_after_casp17_target_register",
            "Historical/support payload may be cleanable only after final target evidence is registered.",
        )

    return (
        "protected_support_payload",
        "review_after_compact_register",
        "Protected storage root requires compact evidence review before cleanup.",
    )


def _evidence_priority(rel_path: str, role: str) -> str:
    lower = rel_path.lower()
    if _text_has_any(lower, ("current", "final", "selected", "promoted", "best", "validation", "manifest", "sha256")):
        return "high"
    if role in {
        "model_checkpoint_or_weight",
        "casp17_structure_coordinate",
        "casp17_viewer_or_object_artifact",
        "casp17_manifest_validation_or_receipt",
    }:
        return "medium"
    return "review"


def _source_refs_under(refs: list[str], rel_path: str) -> list[str]:
    prefix = rel_path.rstrip("/")
    return sorted(ref for ref in refs if ref == prefix or ref.startswith(f"{prefix}/"))


def _iter_files(root_path: Path, protected_root: str) -> list[Path]:
    base = root_path / protected_root
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*") if path.is_file())


def build_storage_essential_evidence_register(
    *,
    root: str | Path = ROOT,
    protected_roots: tuple[str, ...] = DEFAULT_PROTECTED_ROOTS,
    source_of_truth_json: str | Path = DEFAULT_SOURCE_OF_TRUTH_JSON,
    hash_max_bytes: int = DEFAULT_HASH_MAX_BYTES,
    hash_row_limit: int = DEFAULT_HASH_ROW_LIMIT,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    source_of_truth, source_of_truth_present = _read_json(source_of_truth_json, root=root_path)
    source_refs = _source_of_truth_references(source_of_truth)
    rows: list[dict[str, Any]] = []
    hashed_rows = 0

    for protected_root in protected_roots:
        for path in _iter_files(root_path, protected_root):
            rel_path = _display(path, root=root_path)
            size = path.stat().st_size
            role, keep_policy, reason = _role_for_path(rel_path)
            priority = _evidence_priority(rel_path, role)
            refs = _source_refs_under(source_refs, rel_path)
            sha256 = ""
            sha256_status = "deferred_large_or_limit"
            if size <= hash_max_bytes and hashed_rows < hash_row_limit:
                sha256 = _sha256(path)
                sha256_status = "recorded"
                hashed_rows += 1
            elif size > hash_max_bytes:
                sha256_status = "deferred_file_above_hash_max_bytes"
            else:
                sha256_status = "deferred_hash_row_limit_reached"

            rows.append(
                {
                    "path": rel_path,
                    "protected_root": protected_root,
                    "domain": _root_domain(rel_path),
                    "size_bytes": size,
                    "size_human": _human_size(size),
                    "mtime_epoch_utc": _file_mtime_utc(path),
                    "suffix": path.suffix.lower(),
                    "evidence_role": role,
                    "evidence_priority": priority,
                    "keep_policy": keep_policy,
                    "source_of_truth_reference_count": len(refs),
                    "source_of_truth_references": ";".join(refs[:10]),
                    "sha256": sha256,
                    "sha256_status": sha256_status,
                    "delete_allowed_by_this_tool": False,
                    "archive_executed": False,
                    "externalize_executed": False,
                    "external_state_mutated": False,
                    "reason": reason,
                }
            )

    role_counts = Counter(str(row["evidence_role"]) for row in rows)
    priority_counts = Counter(str(row["evidence_priority"]) for row in rows)
    root_counts = Counter(str(row["protected_root"]) for row in rows)
    root_sizes: dict[str, int] = defaultdict(int)
    domain_sizes: dict[str, int] = defaultdict(int)
    domain_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        size = int(row["size_bytes"])
        root_sizes[str(row["protected_root"])] += size
        domain_sizes[str(row["domain"])] += size
        domain_counts[str(row["domain"])] += 1

    domain_rows = [
        {
            "domain": domain,
            "file_count": domain_counts[domain],
            "size_bytes": size,
            "size_human": _human_size(size),
        }
        for domain, size in sorted(domain_sizes.items(), key=lambda item: (-item[1], item[0]))
    ]
    high_priority_rows = [row for row in rows if row["evidence_priority"] == "high"]
    referenced_rows = [row for row in rows if row["source_of_truth_reference_count"]]
    sha_recorded = sum(1 for row in rows if row["sha256_status"] == "recorded")
    largest = max(rows, key=lambda row: int(row["size_bytes"]), default={})

    summary = {
        "packet_type": "storage_essential_evidence_register",
        "status": "storage_essential_evidence_register_ready",
        "source_of_truth_json": _display(_resolve(source_of_truth_json, root=root_path), root=root_path),
        "source_of_truth_present": source_of_truth_present,
        "source_of_truth_reference_count": len(source_refs),
        "protected_roots": ";".join(protected_roots),
        "protected_root_count": len(protected_roots),
        "file_count": len(rows),
        "domain_count": len(domain_rows),
        "high_priority_file_count": len(high_priority_rows),
        "referenced_file_count": len(referenced_rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "total_size_human": _human_size(sum(int(row["size_bytes"]) for row in rows)),
        "models_file_count": root_counts.get("models", 0),
        "models_size_human": _human_size(root_sizes.get("models", 0)),
        "casp17_file_count": root_counts.get("casp17", 0),
        "casp17_size_human": _human_size(root_sizes.get("casp17", 0)),
        "sha256_recorded_count": sha_recorded,
        "sha256_deferred_count": len(rows) - sha_recorded,
        "hash_max_bytes": hash_max_bytes,
        "hash_row_limit": hash_row_limit,
        "delete_allowed_count": 0,
        "delete_executed": False,
        "archive_executed": False,
        "externalize_executed": False,
        "external_state_mutated": False,
        "largest_file_path": str(largest.get("path") or ""),
        "largest_file_size_human": str(largest.get("size_human") or ""),
        "role_counts": dict(sorted(role_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "claim_boundary": CLAIM_BOUNDARY,
        "next_required_step": (
            "Review high-priority rows and top domains, then mark selected checkpoints and final CASP17 target/viewer/validation evidence before deleting any historical payload."
        ),
    }
    return {"summary": summary, "domain_rows": domain_rows, "rows": rows}


def _write_json(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _write_markdown(path_like: str | Path, payload: dict[str, Any], *, root: Path) -> None:
    path = _resolve(path_like, root=root)
    s = payload["summary"]
    lines = [
        "# Storage Essential Evidence Register",
        "",
        f"- status: `{s['status']}`",
        f"- protected_roots: `{s['protected_roots']}`",
        f"- file_count: `{s['file_count']}`",
        f"- total_size_human: `{s['total_size_human']}`",
        f"- high_priority_file_count: `{s['high_priority_file_count']}`",
        f"- referenced_file_count: `{s['referenced_file_count']}`",
        f"- models_file_count: `{s['models_file_count']}`",
        f"- models_size_human: `{s['models_size_human']}`",
        f"- casp17_file_count: `{s['casp17_file_count']}`",
        f"- casp17_size_human: `{s['casp17_size_human']}`",
        f"- sha256_recorded_count: `{s['sha256_recorded_count']}`",
        f"- sha256_deferred_count: `{s['sha256_deferred_count']}`",
        f"- delete_executed: `{s['delete_executed']}`",
        f"- archive_executed: `{s['archive_executed']}`",
        f"- externalize_executed: `{s['externalize_executed']}`",
        f"- external_state_mutated: `{s['external_state_mutated']}`",
        "",
        "## Role Counts",
        "",
        "| role | count |",
        "| --- | ---: |",
    ]
    for role, count in s["role_counts"].items():
        lines.append(f"| `{role}` | `{count}` |")

    lines.extend(["", "## Top Domains", "", "| domain | files | size |", "| --- | ---: | ---: |"])
    for row in payload["domain_rows"][:20]:
        lines.append(f"| `{row['domain']}` | `{row['file_count']}` | `{row['size_human']}` |")

    lines.extend(
        [
            "",
            "## High-Priority Examples",
            "",
            "| path | role | size | sha256_status |",
            "| --- | --- | ---: | --- |",
        ]
    )
    high_rows = [row for row in payload["rows"] if row["evidence_priority"] == "high"]
    for row in high_rows[:30]:
        lines.append(
            f"| `{row['path']}` | `{row['evidence_role']}` | `{row['size_human']}` | `{row['sha256_status']}` |"
        )

    lines.extend(["", "## Claim Boundary", "", s["claim_boundary"], "", "## Next Step", "", f"- {s['next_required_step']}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a read-only essential evidence register for protected storage roots.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--protected-roots", default=",".join(DEFAULT_PROTECTED_ROOTS))
    parser.add_argument("--source-of-truth-json", default=DEFAULT_SOURCE_OF_TRUTH_JSON)
    parser.add_argument("--hash-max-bytes", type=int, default=DEFAULT_HASH_MAX_BYTES)
    parser.add_argument("--hash-row-limit", type=int, default=DEFAULT_HASH_ROW_LIMIT)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    root = Path(args.root)
    protected_roots = tuple(part.strip() for part in args.protected_roots.split(",") if part.strip())
    payload = build_storage_essential_evidence_register(
        root=root,
        protected_roots=protected_roots,
        source_of_truth_json=args.source_of_truth_json,
        hash_max_bytes=args.hash_max_bytes,
        hash_row_limit=args.hash_row_limit,
    )
    _write_json(args.out_json, payload, root=root)
    write_csv_rows(_resolve(args.out_csv, root=root), payload["rows"])
    _write_markdown(args.out_md, payload, root=root)


if __name__ == "__main__":
    main()
