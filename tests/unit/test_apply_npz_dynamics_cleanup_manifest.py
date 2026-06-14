from __future__ import annotations

import json
from pathlib import Path

from tools.accounting import apply_npz_dynamics_cleanup_manifest as mod


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _manifest(path: Path, rel_file: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "summary": {"status": "npz_dynamics_cleanup_manifest_ready"},
                "rows": [
                    {
                        "path": rel_file,
                        "size_bytes": 3,
                        "disposition": "delete_after_json_manifest_approval",
                        "delete_recommended": True,
                    },
                    {
                        "path": "runs/keep/keep.npz",
                        "size_bytes": 4,
                        "disposition": "keep_referenced_current_evidence",
                        "delete_recommended": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def test_apply_npz_cleanup_manifest_dry_run_does_not_delete(tmp_path: Path) -> None:
    rel = "runs/old/file.npz"
    _write(tmp_path / rel, "old")
    manifest = tmp_path / "runs" / "npz_dynamics_cleanup_manifest_current.json"
    _manifest(manifest, rel)

    payload = mod.apply_npz_dynamics_cleanup_manifest(root=tmp_path, manifest_json=manifest.relative_to(tmp_path))

    assert (tmp_path / rel).exists()
    assert payload["summary"]["delete_executed"] is False
    assert payload["summary"]["pending_count"] == 1


def test_apply_npz_cleanup_manifest_execute_requires_token(tmp_path: Path) -> None:
    rel = "runs/old/file.npz"
    _write(tmp_path / rel, "old")
    manifest = tmp_path / "runs" / "npz_dynamics_cleanup_manifest_current.json"
    _manifest(manifest, rel)

    payload = mod.apply_npz_dynamics_cleanup_manifest(
        root=tmp_path,
        manifest_json=manifest.relative_to(tmp_path),
        execute=True,
        approval_token=mod.APPROVAL_TOKEN,
    )

    assert not (tmp_path / rel).exists()
    assert payload["summary"]["delete_executed"] is True
    assert payload["summary"]["deleted_count"] == 1
    assert payload["summary"]["external_state_mutated"] is False
