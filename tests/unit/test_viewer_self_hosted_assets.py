from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path.cwd()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_viewer_runtime_loads_only_local_vendor_assets() -> None:
    index = Path("viewer/index.html").read_text(encoding="utf-8")
    app = Path("viewer/app.js").read_text(encoding="utf-8")
    style = Path("viewer/style.css").read_text(encoding="utf-8")

    assert "vendor/molstar/4.5.0/molstar.css" in index
    assert "vendor/molstar/4.5.0/molstar.js" in index
    assert "vendor/plotly/2.35.2/plotly-2.35.2.min.js" in index
    assert "vendor/jszip/3.10.1/jszip.min.js" in index

    runtime_text = "\n".join([index, app, style])
    external_urls = [
        match.group(0)
        for match in re.finditer(r"https?://[^\"'\\s)>]+", runtime_text)
        if "www.w3.org/2000" not in match.group(0)
    ]
    assert external_urls == []
    assert "fonts.googleapis.com" not in runtime_text
    assert "cdn.jsdelivr.net" not in runtime_text
    assert "cdn.plot.ly" not in runtime_text
    assert "localhost:8765" not in runtime_text
    assert "127.0.0.1:8765" not in runtime_text
    assert "window.location.replace" not in index


def test_viewer_vendor_manifest_matches_local_files() -> None:
    manifest = json.loads(Path("viewer/vendor/manifest.json").read_text(encoding="utf-8"))
    notices_path = ROOT / manifest["third_party_notice_path"]
    notices = notices_path.read_text(encoding="utf-8")

    assert manifest["manifest_version"] == "viewer_vendor_assets_v1"
    assert manifest["license_review_status"] == "recorded_not_legal_approved"
    assert notices_path.is_file()
    assert len(manifest["assets"]) == 4
    for row in manifest["assets"]:
        path = ROOT / row["path"]
        assert path.is_file(), row["path"]
        assert path.stat().st_size == row["size_bytes"]
        assert _sha256(path) == row["sha256"]
        assert row["source_url"].startswith("https://")
        assert row["package"] in notices
        assert row["license_id"] in notices
        assert row["license_source_url"].startswith("https://")
        assert row["license_source_url"] in notices
