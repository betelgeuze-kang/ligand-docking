#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "viewer" / "index.html"
DEFAULT_MANIFEST = ROOT / "viewer" / "vendor" / "manifest.json"
DEFAULT_OUT = ROOT / "runs" / "viewer_asset_base_url_decision_current.json"


class _AssetReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        if tag.lower() == "script" and attr_map.get("src"):
            self.references.append({"tag": "script", "attr": "src", "url": attr_map["src"]})
        if tag.lower() == "link" and attr_map.get("href"):
            rel = attr_map.get("rel", "")
            if "stylesheet" in rel or attr_map["href"].startswith("vendor/"):
                self.references.append({"tag": "link", "attr": "href", "url": attr_map["href"]})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_external_or_absolute(url: str) -> bool:
    lowered = url.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("//")
        or lowered.startswith("/")
    )


def _strip_query_and_fragment(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0]


def _is_safe_document_relative(url: str) -> bool:
    if not url:
        return False
    if _is_external_or_absolute(url):
        return False
    path = _strip_query_and_fragment(url)
    return bool(path) and not path.startswith("../") and "/../" not in path and path != ".."


def _collect_runtime_references(index_path: Path) -> list[dict[str, str]]:
    parser = _AssetReferenceParser()
    parser.feed(index_path.read_text(encoding="utf-8"))
    return parser.references


def build_decision(*, index_path: Path = DEFAULT_INDEX, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    references = _collect_runtime_references(index_path) if index_path.is_file() else []
    index_dir = index_path.parent

    rows: list[dict[str, Any]] = []
    for ref in references:
        url = ref["url"]
        local_path = index_dir / _strip_query_and_fragment(url)
        rows.append(
            {
                **ref,
                "document_relative": _is_safe_document_relative(url),
                "external_or_absolute": _is_external_or_absolute(url),
                "local_path": _display_path(local_path),
                "local_file_present": local_path.is_file(),
            }
        )

    manifest_assets = manifest.get("assets") if isinstance(manifest.get("assets"), list) else []
    manifest_asset_paths = {str(row.get("path", "")) for row in manifest_assets if isinstance(row, dict)}
    vendor_ref_paths = {
        _display_path(index_dir / _strip_query_and_fragment(row["url"]))
        for row in rows
        if row["url"].startswith("vendor/")
    }

    all_references_relative = bool(rows) and all(row["document_relative"] for row in rows)
    all_reference_files_present = bool(rows) and all(row["local_file_present"] for row in rows)
    vendor_manifest_covered = bool(vendor_ref_paths) and vendor_ref_paths.issubset(manifest_asset_paths)
    same_directory_bundle_supported = all_references_relative and all_reference_files_present and vendor_manifest_covered

    blockers: list[str] = []
    if not rows:
        blockers.append("no_runtime_asset_references_found")
    if not all_references_relative:
        blockers.append("non_relative_or_external_runtime_reference")
    if not all_reference_files_present:
        blockers.append("runtime_reference_missing_local_file")
    if not vendor_manifest_covered:
        blockers.append("vendor_reference_not_covered_by_manifest")

    return {
        "summary": {
            "status": "viewer_asset_base_url_decision_pass" if not blockers else "blocked_viewer_asset_base_url_decision",
            "created_at_utc": _utc_now(),
            "index_path": _display_path(index_path),
            "manifest_path": _display_path(manifest_path),
            "runtime_reference_count": len(rows),
            "vendor_reference_count": len(vendor_ref_paths),
            "all_runtime_references_document_relative": all_references_relative,
            "all_runtime_reference_files_present": all_reference_files_present,
            "vendor_references_covered_by_manifest": vendor_manifest_covered,
            "same_directory_or_subpath_bundle_supported": same_directory_bundle_supported,
            "asset_base_url_override_required_for_standard_bundle": not same_directory_bundle_supported,
            "asset_base_url_override_required_for_relocated_index": True,
            "recommended_policy": (
                "serve viewer/index.html with viewer/style.css, viewer/app.js, and viewer/vendor/ preserved under "
                "the same directory; no asset base URL override is required for that standard bundle. If index.html "
                "is moved away from its sibling assets, rewrite paths or define a delivery-specific asset base URL."
            ),
            "blockers": blockers,
        },
        "runtime_references": rows,
        "claim_boundary": (
            "Viewer asset base URL decision packet only; verifies document-relative runtime asset paths for the "
            "current static bundle. It does not validate customer reverse proxy headers, CDN caching policy, or legal "
            "license approval."
        ),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a viewer asset base URL decision packet.")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-json", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    payload = build_decision(index_path=Path(args.index), manifest_path=Path(args.manifest))
    _write_json(Path(args.out_json), payload)
    print(json.dumps(payload["summary"], indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload["summary"]["status"] == "viewer_asset_base_url_decision_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
