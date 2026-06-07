#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Any


def _mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _copy(src: Path, dst_dir: Path) -> dict[str, Any]:
    _mkdir(dst_dir)
    dst = dst_dir / src.name
    shutil.copy2(src, dst)
    return {
        "src": str(src.resolve()),
        "dst": str(dst.resolve()),
        "size_bytes": dst.stat().st_size,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-json", action="append", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--bundle-tag", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    bundle_dir = out_dir / f"blind_validation_bundle_{args.bundle_tag}"
    files_dir = bundle_dir / "files"
    _mkdir(files_dir)

    included: list[dict[str, Any]] = []
    for src_str in args.summary_json:
        src = Path(src_str)
        if not src.exists():
            raise FileNotFoundError(src)
        included.append(_copy(src, files_dir))
        md_src = src.with_suffix(".md")
        if md_src.exists():
            included.append(_copy(md_src, files_dir))

    manifest = {
        "bundle_tag": args.bundle_tag,
        "bundle_dir": str(bundle_dir.resolve()),
        "included_count": len(included),
        "files": included,
    }
    manifest_json = bundle_dir / "manifest.json"
    manifest_md = bundle_dir / "manifest.md"
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    manifest_md.write_text(
        "# Blind Validation Bundle\n\n"
        + f"- bundle_tag: {args.bundle_tag}\n"
        + f"- included_count: {len(included)}\n\n"
        + "## Files\n"
        + "\n".join(f"- `{row['dst']}`" for row in included)
        + "\n",
        encoding="utf-8",
    )
    zip_path = shutil.make_archive(str(out_dir / f"blind_validation_bundle_{args.bundle_tag}"), "zip", root_dir=bundle_dir)
    print(
        json.dumps(
            {
                "bundle_dir": str(bundle_dir.resolve()),
                "manifest_json": str(manifest_json.resolve()),
                "manifest_md": str(manifest_md.resolve()),
                "archive_zip": str(Path(zip_path).resolve()),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
