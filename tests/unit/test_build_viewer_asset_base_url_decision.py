from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import build_viewer_asset_base_url_decision as mod


def test_viewer_asset_base_url_decision_passes_current_bundle() -> None:
    payload = mod.build_decision()
    summary = payload["summary"]

    assert summary["status"] == "viewer_asset_base_url_decision_pass"
    assert summary["same_directory_or_subpath_bundle_supported"] is True
    assert summary["asset_base_url_override_required_for_standard_bundle"] is False
    assert summary["asset_base_url_override_required_for_relocated_index"] is True
    assert summary["runtime_reference_count"] >= 5
    assert summary["vendor_reference_count"] == 4
    assert summary["blockers"] == []
    assert all(row["document_relative"] for row in payload["runtime_references"])
    assert all(row["local_file_present"] for row in payload["runtime_references"])


def test_viewer_asset_base_url_decision_blocks_external_asset(tmp_path: Path) -> None:
    viewer_dir = tmp_path / "viewer"
    vendor_dir = viewer_dir / "vendor" / "x"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "asset.js").write_text("console.log('ok');\n", encoding="utf-8")
    index = viewer_dir / "index.html"
    index.write_text(
        """
        <html><head>
          <script src="https://cdn.example.invalid/x.js"></script>
          <script src="vendor/x/asset.js"></script>
        </head></html>
        """,
        encoding="utf-8",
    )
    manifest = viewer_dir / "vendor" / "manifest.json"
    manifest.write_text(
        json.dumps({"assets": [{"path": str((vendor_dir / "asset.js").relative_to(tmp_path))}]}),
        encoding="utf-8",
    )

    payload = mod.build_decision(index_path=index, manifest_path=manifest)

    assert payload["summary"]["status"] == "blocked_viewer_asset_base_url_decision"
    assert "non_relative_or_external_runtime_reference" in payload["summary"]["blockers"]
    assert payload["summary"]["asset_base_url_override_required_for_standard_bundle"] is True


def test_viewer_asset_base_url_decision_cli_writes_json(tmp_path: Path) -> None:
    out_json = tmp_path / "decision.json"

    result = subprocess.run(
        [sys.executable, "tools/build_viewer_asset_base_url_decision.py", "--out-json", str(out_json)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "viewer_asset_base_url_decision_pass"
    assert "same_directory_or_subpath_bundle_supported" in result.stdout
