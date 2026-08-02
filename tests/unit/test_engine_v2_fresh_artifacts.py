from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from betelgeuze_engine_v2.benchmark.fresh_artifacts import (
    FRESH_ARTIFACT_MANIFEST_FILENAME,
    FRESH_EXECUTION_ENVIRONMENT_FILENAME,
    FRESH_EXECUTION_LOG_FILENAME,
    FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME,
    FreshArtifactManifestError,
    build_fresh_artifact_manifest,
    verify_fresh_artifact_manifest_document,
    verify_fresh_artifact_set,
)


_D = "a" * 64
_COMPLETION = "fresh-redocking-run-once-completion.json"


def _write(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_bytes(payload)
    path.chmod(mode)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / ".betelgeuze" / "fresh-128"
    root.mkdir(parents=True, mode=0o700)
    root.chmod(0o700)
    _write(root / "fresh-redocking-run-once-reservation.json", b"{}\n")
    _write(root / "stage0-admission-receipt.json", b"{}\n")
    _write(root / FRESH_STAGE0_POLICY_SNAPSHOT_FILENAME, b"{}\n")
    _write(root / FRESH_EXECUTION_ENVIRONMENT_FILENAME, b"{}\n")
    _write(root / FRESH_EXECUTION_LOG_FILENAME, b"{}\n")
    _write(root / "fresh-redocking-internal-report.json", b"{}\n")
    _write(root / "private-external-binary" / _D, b"binary", mode=0o500)
    _write(root / "receipts" / "materializations" / "case-001.json", b"{}\n")
    _write(root / "receipts" / "engine_v2" / "case-001.json", b"{}\n")
    _write(root / "receipts" / "vina" / "case-001.json", b"{}\n")
    _write(root / "receipts" / "gnina" / "case-001.json", b"{}\n")
    _write(root / "poses" / "engine_v2" / "case-001.sdf", b"pose\n")
    for directory, _, _ in os.walk(root):
        Path(directory).chmod(0o700)
    return root


def _manifest(root: Path) -> dict[str, object]:
    return build_fresh_artifact_manifest(
        output_root=root,
        runner_id="fresh-runner/1",
        retention_root=".betelgeuze/fresh-128",
        reservation_sha256=_D,
        report_fingerprint_sha256=_D,
        report_file_sha256=_D,
        stage0_policy_sha256=_D,
        source_freeze_sha256=_D,
        execution_profile_sha256=_D,
        fresh_holdout_manifest_sha256=_D,
        completion_filename=_COMPLETION,
    )


def _reseal(payload: dict[str, object]) -> None:
    projection = dict(payload)
    projection.pop("manifest_sha256", None)
    payload["manifest_sha256"] = hashlib.sha256(
        json.dumps(
            projection,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()


def test_terminal_manifest_binds_the_closed_local_artifact_set(tmp_path: Path) -> None:
    root = _root(tmp_path)
    manifest = _manifest(root)

    assert (
        verify_fresh_artifact_manifest_document(manifest) == manifest["manifest_sha256"]
    )
    assert (
        verify_fresh_artifact_set(
            output_root=root,
            manifest=manifest,
            completion_filename=_COMPLETION,
        )
        == manifest["manifest_sha256"]
    )
    assert manifest["exactly_once_authority_granted"] is False
    assert manifest["scientific_validation_granted"] is False
    assert manifest["product_promotion_granted"] is False
    assert [row["relative_path"] for row in manifest["entries"]] == sorted(
        row["relative_path"] for row in manifest["entries"]
    )


def test_terminal_manifest_detects_post_manifest_byte_change(tmp_path: Path) -> None:
    root = _root(tmp_path)
    manifest = _manifest(root)
    target = root / "receipts" / "engine_v2" / "case-001.json"
    target.write_bytes(b'{"changed":true}\n')
    target.chmod(0o600)

    with pytest.raises(FreshArtifactManifestError, match="changed"):
        verify_fresh_artifact_set(
            output_root=root,
            manifest=manifest,
            completion_filename=_COMPLETION,
        )


def test_terminal_manifest_rejects_unexpected_file_symlink_and_hardlink(
    tmp_path: Path,
) -> None:
    unexpected_root = _root(tmp_path / "unexpected")
    _write(unexpected_root / "notes.txt", b"not evidence")
    with pytest.raises(FreshArtifactManifestError, match="unexpected"):
        _manifest(unexpected_root)

    symlink_root = _root(tmp_path / "symlink")
    os.symlink(
        symlink_root / "stage0-admission-receipt.json",
        symlink_root / "receipts" / "engine_v2" / "case-002.json",
    )
    with pytest.raises(FreshArtifactManifestError, match="regular file"):
        _manifest(symlink_root)

    hardlink_root = _root(tmp_path / "hardlink")
    source = hardlink_root / "receipts" / "engine_v2" / "case-001.json"
    target = hardlink_root / "receipts" / "engine_v2" / "case-002.json"
    os.link(source, target)
    with pytest.raises(FreshArtifactManifestError, match="ownership or bounds"):
        _manifest(hardlink_root)


def test_terminal_manifest_rejects_resealed_path_traversal(tmp_path: Path) -> None:
    manifest = _manifest(_root(tmp_path))
    tampered = deepcopy(manifest)
    entries = tampered["entries"]
    assert isinstance(entries, list)
    entries[0]["relative_path"] = "../escape"
    entries[0]["artifact_role"] = "local_attempt_reservation"
    tampered["artifact_set_sha256"] = hashlib.sha256(
        json.dumps(
            entries,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
    ).hexdigest()
    _reseal(tampered)

    with pytest.raises(FreshArtifactManifestError, match="not normalized"):
        verify_fresh_artifact_manifest_document(tampered)


def test_terminal_manifest_rejects_root_symlink(tmp_path: Path) -> None:
    root = _root(tmp_path / "real")
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)

    with pytest.raises(FreshArtifactManifestError, match="symlink"):
        _manifest(alias)


def test_terminal_manifest_excludes_only_terminal_files(tmp_path: Path) -> None:
    root = _root(tmp_path)
    _write(root / FRESH_ARTIFACT_MANIFEST_FILENAME, b"{}\n")
    _write(root / _COMPLETION, b"{}\n")

    manifest = _manifest(root)
    retained = {row["relative_path"] for row in manifest["entries"]}
    assert FRESH_ARTIFACT_MANIFEST_FILENAME not in retained
    assert _COMPLETION not in retained
