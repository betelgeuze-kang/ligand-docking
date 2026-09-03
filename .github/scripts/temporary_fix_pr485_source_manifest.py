from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / (
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_v1.py"
)
UNIT = ROOT / (
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_v1.py"
)
DOC = ROOT / (
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_v1.md"
)

EXPECTED_SHA256 = {
    VERIFIER: "8dff071b125a379e8b35fbbdc88ba1874744462157587858911456569ce6a0ca",
    UNIT: "c42c8665b5e36ca74274eb70d0a4eb08c55fdb607f502d28265f6bf25bc1295b",
    DOC: "b765262703c10acc848f74575028e06ee4d8faf48d8059e1ace6e6ea49357004",
}


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"{label} anchor drift: found {source.count(old)}")
    return source.replace(old, new, 1)


def checked_text(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    observed = hashlib.sha256(content.encode("utf-8")).hexdigest()
    expected = EXPECTED_SHA256[path]
    if observed != expected:
        raise RuntimeError(
            f"refusing to patch {path.relative_to(ROOT)}: "
            f"expected {expected}, observed {observed}"
        )
    return content


def patch_verifier() -> None:
    source = checked_text(VERIFIER)
    source = replace_once(
        source,
        '''SUCCESSOR = {
    "pull_request": 485,
    "reviewed_head": "1d8dbe087c281c3688fdc98a84c54c93689b806a",
    "merge_commit": "cabe01debb2ab7653e323db410d1fdf4a1388ea2",
    "merge_tree": "5f4cda9b4f3faa1b77fdae024505b4f02122299a",
}

PREDECESSOR_EVIDENCE_SHA256 = {''',
        '''SUCCESSOR = {
    "pull_request": 485,
    "reviewed_head": "1d8dbe087c281c3688fdc98a84c54c93689b806a",
    "merge_commit": "cabe01debb2ab7653e323db410d1fdf4a1388ea2",
    "merge_tree": "5f4cda9b4f3faa1b77fdae024505b4f02122299a",
}

SOURCE_SNAPSHOT = {
    "merge_commit": "234edea066fcba2b51fd4df8338b696d2febc66e",
    "merge_tree": "ccd3792e60df668072e60ba454a4c9345616193a",
    "description": "post_pr485_delta_verifier_fix_source_snapshot",
}
LIVE_SOURCE_PATHS = frozenset(
    (
        WORKFLOW_RELATIVE_PATH,
        DOC_RELATIVE_PATH,
        UNIT_RELATIVE_PATH,
        VERIFIER_RELATIVE_PATH,
    )
)

PREDECESSOR_EVIDENCE_SHA256 = {''',
        "source snapshot constants",
    )
    source = replace_once(
        source,
        '''def frozen_bytes(path: Path) -> bytes:
    return git("show", "%s:%s" % (PREDECESSOR["merge_commit"], path)).stdout


def require_predecessor() -> dict:''',
        '''def frozen_bytes(path: Path) -> bytes:
    return git("show", "%s:%s" % (PREDECESSOR["merge_commit"], path)).stdout


def source_snapshot_bytes(path: Path) -> bytes:
    return git("show", "%s:%s" % (SOURCE_SNAPSHOT["merge_commit"], path)).stdout


def require_source_snapshot() -> None:
    merge = SOURCE_SNAPSHOT["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("source snapshot merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("source snapshot merge identity drift")
    tree = git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
    if tree != SOURCE_SNAPSHOT["merge_tree"]:
        fail("source snapshot merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from the frozen source snapshot")


def source_manifest_bytes(path: Path, root: Path = ROOT) -> bytes:
    if path in LIVE_SOURCE_PATHS:
        return (root / path).read_bytes()
    return source_snapshot_bytes(path)


def require_predecessor() -> dict:''',
        "source snapshot helpers",
    )
    source = replace_once(
        source,
        '''def discover_source_paths(root: Path = ROOT) -> list[Path]:
    manifest = require_predecessor()
    paths = {Path(row["path"]) for row in manifest["files"]}
    paths.update(IMPLEMENTATION_DELTA_PATHS)
    paths.update(
        (
            PREDECESSOR_PROFILE_RELATIVE_PATH,
            PREDECESSOR_MANIFEST_RELATIVE_PATH,
            WORKFLOW_RELATIVE_PATH,
            DOC_RELATIVE_PATH,
            UNIT_RELATIVE_PATH,
            VERIFIER_RELATIVE_PATH,
        )
    )
    paths.difference_update((PROFILE_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH))
    missing = [path.as_posix() for path in paths if not (root / path).is_file()]
    if missing:
        fail("missing source paths: %s" % missing)
    result = sorted(paths, key=lambda path: path.as_posix())
    if len(result) != 441:
        fail("derived source-manifest count drift: %d" % len(result))
    return result


def build_source_manifest(root: Path = ROOT) -> dict:
    rows = [
        {"path": path.as_posix(), "sha256": sha((root / path).read_bytes())}
        for path in discover_source_paths(root)
    ]
    return {
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": (
            "particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_"
            "validated_nonempty_input_soa_binding_current_sources_tests_"
            "evidence_pr484_target"
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }
''',
        '''def discover_source_paths(root: Path = ROOT) -> list[Path]:
    manifest = require_predecessor()
    require_source_snapshot()
    paths = {Path(row["path"]) for row in manifest["files"]}
    paths.update(IMPLEMENTATION_DELTA_PATHS)
    paths.update(
        (
            PREDECESSOR_PROFILE_RELATIVE_PATH,
            PREDECESSOR_MANIFEST_RELATIVE_PATH,
            WORKFLOW_RELATIVE_PATH,
            DOC_RELATIVE_PATH,
            UNIT_RELATIVE_PATH,
            VERIFIER_RELATIVE_PATH,
        )
    )
    paths.difference_update((PROFILE_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH))
    missing = []
    snapshot = SOURCE_SNAPSHOT["merge_commit"]
    for path in paths:
        if path in LIVE_SOURCE_PATHS:
            present = (root / path).is_file()
        else:
            present = (
                git(
                    "cat-file",
                    "-e",
                    "%s:%s" % (snapshot, path),
                    check=False,
                ).returncode
                == 0
            )
        if not present:
            missing.append(path.as_posix())
    if missing:
        fail("missing source paths: %s" % sorted(missing))
    result = sorted(paths, key=lambda path: path.as_posix())
    if len(result) != 441:
        fail("derived source-manifest count drift: %d" % len(result))
    return result


def build_source_manifest(root: Path = ROOT) -> dict:
    rows = [
        {"path": path.as_posix(), "sha256": sha(source_manifest_bytes(path, root))}
        for path in discover_source_paths(root)
    ]
    return {
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": (
            "particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_"
            "validated_nonempty_input_soa_binding_frozen_pr485_source_"
            "snapshot_current_evidence"
        ),
        "source_snapshot": dict(SOURCE_SNAPSHOT),
        "live_evidence_paths": sorted(
            path.as_posix() for path in LIVE_SOURCE_PATHS
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }
''',
        "source manifest construction",
    )
    source = replace_once(
        source,
        '''            "source_manifest_entry_count": len(manifest["files"]),
        }
    )''',
        '''            "source_manifest_entry_count": len(manifest["files"]),
            "source_manifest_non_evidence_paths_frozen_to_source_snapshot": True,
            "source_manifest_live_evidence_paths_current_checkout": True,
        }
    )''',
        "profile implementation flags",
    )
    source = replace_once(
        source,
        '''            "source_manifest_entry_count_exact": 441,
            "pull_request_trigger_path_count_exact": 258,''',
        '''            "source_manifest_entry_count_exact": 441,
            "source_manifest_frozen_path_count_exact": 437,
            "source_manifest_live_evidence_path_count_exact": 4,
            "source_snapshot_merge_commit": SOURCE_SNAPSHOT["merge_commit"],
            "source_snapshot_merge_tree": SOURCE_SNAPSHOT["merge_tree"],
            "source_manifest_descendant_stable": True,
            "pull_request_trigger_path_count_exact": 258,''',
        "profile validation snapshot fields",
    )
    source = replace_once(
        source,
        '''        "rollback_scratch_validation_and_commit_preserved",
    ):
        if implementation.get(key) is not True:''',
        '''        "rollback_scratch_validation_and_commit_preserved",
        "source_manifest_non_evidence_paths_frozen_to_source_snapshot",
        "source_manifest_live_evidence_paths_current_checkout",
    ):
        if implementation.get(key) is not True:''',
        "required implementation flags",
    )
    source = replace_once(
        source,
        '''    if manifest != build_source_manifest(root):
        fail("source manifest drift; run verifier with --refresh")
    if profile != build_profile(manifest_raw, root):''',
        '''    if manifest.get("source_snapshot") != SOURCE_SNAPSHOT:
        fail("source manifest snapshot identity drift")
    expected_live_paths = sorted(path.as_posix() for path in LIVE_SOURCE_PATHS)
    if manifest.get("live_evidence_paths") != expected_live_paths:
        fail("source manifest live-evidence path drift")
    if manifest != build_source_manifest(root):
        fail("source manifest drift; run verifier with --refresh")
    if profile != build_profile(manifest_raw, root):''',
        "manifest identity checks",
    )
    source = replace_once(
        source,
        '''        "32 unresolved operational decisions",
        "no\\nperformance, allocation, object-size, stack-size, acceleration, scientific",''',
        '''        "32 unresolved operational decisions",
        "frozen source snapshot",
        "current workflow, documentation, unit, and verifier",
        "unrelated descendant source changes",
        SOURCE_SNAPSHOT["merge_commit"],
        "no\\nperformance, allocation, object-size, stack-size, acceleration, scientific",''',
        "documentation snapshot requirements",
    )
    source = replace_once(
        source,
        '''        "predecessor_merge_tree": PREDECESSOR["merge_tree"],
    }''',
        '''        "predecessor_merge_tree": PREDECESSOR["merge_tree"],
        "source_snapshot_merge_commit": SOURCE_SNAPSHOT["merge_commit"],
        "source_snapshot_merge_tree": SOURCE_SNAPSHOT["merge_tree"],
        "live_evidence_path_count": len(LIVE_SOURCE_PATHS),
    }''',
        "verify result snapshot fields",
    )
    VERIFIER.write_text(source, encoding="utf-8")


def patch_unit() -> None:
    source = checked_text(UNIT)
    source = replace_once(
        source,
        '''    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]
''',
        '''    assert result["predecessor_merge_tree"] == verifier.PREDECESSOR["merge_tree"]
    assert result["source_snapshot_merge_commit"] == verifier.SOURCE_SNAPSHOT["merge_commit"]
    assert result["source_snapshot_merge_tree"] == verifier.SOURCE_SNAPSHOT["merge_tree"]
    assert result["live_evidence_path_count"] == 4
''',
        "unit verify result",
    )
    source = replace_once(
        source,
        '''        "rollback_scratch_validation_and_commit_preserved",
    ):
        assert implementation[key] is True''',
        '''        "rollback_scratch_validation_and_commit_preserved",
        "source_manifest_non_evidence_paths_frozen_to_source_snapshot",
        "source_manifest_live_evidence_paths_current_checkout",
    ):
        assert implementation[key] is True''',
        "unit implementation flags",
    )
    source = replace_once(
        source,
        '''    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
''',
        '''    assert manifest["source_snapshot"] == verifier.SOURCE_SNAPSHOT
    assert manifest["live_evidence_paths"] == sorted(
        path.as_posix() for path in verifier.LIVE_SOURCE_PATHS
    )
    assert manifest["evidence_paths"] == sorted(
        path.as_posix() for path in verifier.EVIDENCE_PATHS
    )
''',
        "unit manifest metadata",
    )
    source += '''


def test_source_manifest_freezes_non_evidence_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    frozen_path = verifier.ADAPTER_RELATIVE_PATH
    live_path = verifier.UNIT_RELATIVE_PATH
    (tmp_path / frozen_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / frozen_path).write_bytes(b"unrelated descendant implementation")
    (tmp_path / live_path).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / live_path).write_bytes(b"current live evidence")
    monkeypatch.setattr(
        verifier,
        "source_snapshot_bytes",
        lambda path: b"frozen historical bytes" if path == frozen_path else b"other",
    )

    assert verifier.source_manifest_bytes(frozen_path, tmp_path) == b"frozen historical bytes"
    assert verifier.source_manifest_bytes(live_path, tmp_path) == b"current live evidence"
'''
    UNIT.write_text(source, encoding="utf-8")


def patch_doc() -> None:
    source = checked_text(DOC)
    source = replace_once(
        source,
        '''## Authority boundary
''',
        '''## Descendant-stable source manifest

The 441-row manifest now distinguishes the frozen source snapshot from live
successor evidence. Non-evidence source rows are read from the exact post-PR
485 verifier-fix merge `234edea066fcba2b51fd4df8338b696d2febc66e`
and tree `ccd3792e60df668072e60ba454a4c9345616193a`. The current workflow,
documentation, unit, and verifier remain live checkout inputs and continue to
be hashed from the current source tree.

This prevents unrelated descendant source changes from contaminating the
historical PR 485 source contract while retaining semantic checks against the
current canonical and vendored adapters. The manifest is a frozen source
snapshot with current evidence, not a claim that later descendants are byte
identical to PR 485.

## Authority boundary
''',
        "documentation descendant-stable section",
    )
    DOC.write_text(source, encoding="utf-8")


def main() -> None:
    patch_verifier()
    patch_unit()
    patch_doc()


if __name__ == "__main__":
    main()
