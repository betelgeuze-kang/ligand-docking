from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

from betelgeuze_engine.product.implementation_provenance import (
    HTVS_IMPLEMENTATION_SOURCE_PATHS,
    ImplementationProvenanceError,
    build_implementation_source_manifest,
    validate_implementation_source_manifest,
)


def _source_tree(root: Path) -> None:
    for index, relative in enumerate(HTVS_IMPLEMENTATION_SOURCE_PATHS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"source-{index}\n".encode("utf-8"))


def test_manifest_is_ordered_content_bound_and_metadata_independent(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    first = build_implementation_source_manifest(tmp_path)

    assert [item["path"] for item in first["files"]] == list(
        HTVS_IMPLEMENTATION_SOURCE_PATHS
    )
    assert validate_implementation_source_manifest(first, root=tmp_path) == first
    source = tmp_path / HTVS_IMPLEMENTATION_SOURCE_PATHS[0]
    os.utime(source, (source.stat().st_atime + 100, source.stat().st_mtime + 100))
    source.chmod(0o600)
    assert build_implementation_source_manifest(tmp_path) == first

    source.write_bytes(b"changed\n")
    changed = build_implementation_source_manifest(tmp_path)
    assert changed["manifest_sha256"] != first["manifest_sha256"]
    assert changed["files"][0]["sha256"] != first["files"][0]["sha256"]


def test_manifest_missing_source_or_tampered_aggregate_fails_closed(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    (tmp_path / HTVS_IMPLEMENTATION_SOURCE_PATHS[-1]).unlink()
    with pytest.raises(ImplementationProvenanceError, match="source missing"):
        build_implementation_source_manifest(tmp_path)

    _source_tree(tmp_path)
    manifest = build_implementation_source_manifest(tmp_path)
    tampered = copy.deepcopy(manifest)
    tampered["files"][0]["sha256"] = "0" * 64
    with pytest.raises(ImplementationProvenanceError, match="manifest_sha256 mismatch"):
        validate_implementation_source_manifest(tampered, root=tmp_path)


def test_manifest_with_valid_aggregate_but_stale_source_fails_current_check(
    tmp_path: Path,
) -> None:
    _source_tree(tmp_path)
    manifest = build_implementation_source_manifest(tmp_path)
    (tmp_path / "core/refine_physics.py").write_text(
        "behavior changed\n", encoding="utf-8"
    )

    with pytest.raises(
        ImplementationProvenanceError,
        match="does not match current source tree",
    ):
        validate_implementation_source_manifest(manifest, root=tmp_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        "betelgeuze_engine/interactions/hbond_evidence.py",
        "betelgeuze_engine/backmapping/onsps.py",
        "betelgeuze_engine/product/runners/htvs_pipeline.py",
        "betelgeuze_engine/residual/__init__.py",
        "betelgeuze_engine/topology/__init__.py",
        "tools/product/stage2_skip_router.py",
        "tools/accounting/build_ligand_mapping_queue.py",
        "tools/generate_ligand_trajectory_engine.py",
        "train/train_pipeline.py",
    ],
)
def test_manifest_covers_behavior_critical_dependency_closure(
    tmp_path: Path,
    relative_path: str,
) -> None:
    assert relative_path in HTVS_IMPLEMENTATION_SOURCE_PATHS
    _source_tree(tmp_path)
    baseline = build_implementation_source_manifest(tmp_path)

    (tmp_path / relative_path).write_text(
        "behavior changed\n",
        encoding="utf-8",
    )
    changed = build_implementation_source_manifest(tmp_path)

    assert changed["manifest_sha256"] != baseline["manifest_sha256"]
