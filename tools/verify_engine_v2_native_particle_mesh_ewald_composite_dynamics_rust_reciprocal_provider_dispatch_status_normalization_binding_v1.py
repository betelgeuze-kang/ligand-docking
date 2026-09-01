#!/usr/bin/env python3
"""Verify direct normalization-boundary binding of native PME provider status."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
from typing import NoReturn

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_dispatch_status_normalization_binding"
)
WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-dispatch-status-normalization-binding"
)
# Preserve the semantic name while avoiding the top-stack reserved
# temporary-workflow filename fragment ``dispatch-``.
WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-status-normalization-binding"
)
PREDECESSOR_STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_dispatch_status_single_assignment"
)
PREDECESSOR_WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-dispatch-status-single-assignment"
)
PREDECESSOR_WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-status-single-assignment"
)

PROFILE_RELATIVE_PATH = Path("config/%s_profile_v1.json" % STEM)
SOURCE_MANIFEST_RELATIVE_PATH = Path("config/%s_profile_v1_sources.json" % STEM)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/%s.yml" % WORKFLOW_FILENAME_STEM
)
DOC_RELATIVE_PATH = Path("docs/%s_v1.md" % STEM)
UNIT_RELATIVE_PATH = Path("tests/unit/test_%s_v1.py" % STEM)
VERIFIER_RELATIVE_PATH = Path("tools/verify_%s_v1.py" % STEM)

PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/%s_profile_v1.json" % PREDECESSOR_STEM
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/%s_profile_v1_sources.json" % PREDECESSOR_STEM
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/%s.yml" % PREDECESSOR_WORKFLOW_FILENAME_STEM
)
PREDECESSOR_DOC_RELATIVE_PATH = Path("docs/%s_v1.md" % PREDECESSOR_STEM)
PREDECESSOR_UNIT_RELATIVE_PATH = Path("tests/unit/test_%s_v1.py" % PREDECESSOR_STEM)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_%s_v1.py" % PREDECESSOR_STEM
)

ADAPTER_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
)
VENDOR_ADAPTER_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
    "rust_evaluator.cpp"
)
ADAPTER_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_reciprocal_rust_adapter_transactionality.cpp"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_dispatch_status_normalization_binding_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_dispatch_status_normalization_binding_sources/1.0.0"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)
PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)
FORCE_PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)

PREDECESSOR = {
    "pull_request": 479,
    "reviewed_head": "f62a5f68a59a94ffe0d2b20900e1f8c4d82b6eb8",
    "merge_commit": "0f723b265c6366c0037d83d9ed9e934817fd9626",
    "merge_tree": "619ad7bf2e6b74b80e6e7594b5b3c91f5e72b514",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "7d968b533127c959c8e76daf8641fef6e831a31804ed747b547890a85ab935cb"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "58f21f9c120dbc5b6062eaec7478d34ca5f59ddea6d2aea64b07cf9e93392820"
    ),
    "source_manifest_entry_count": 405,
}

PREDECESSOR_EVIDENCE_SHA256 = {
    PREDECESSOR_WORKFLOW_RELATIVE_PATH: (
        "0520329cb6718fbf19c1ed52972ccf86aa4d677a71b83cb9aaf8842f8db3a3f4"
    ),
    PREDECESSOR_PROFILE_RELATIVE_PATH: PREDECESSOR["profile_sha256"],
    PREDECESSOR_MANIFEST_RELATIVE_PATH: PREDECESSOR["source_manifest_sha256"],
    PREDECESSOR_DOC_RELATIVE_PATH: (
        "73e5b9dc42ee4c89df2650133628de31a7a3ed0cdf95ce863f7a802a84c68353"
    ),
    PREDECESSOR_UNIT_RELATIVE_PATH: (
        "d1e2f8369fde3260be2a7e528745ca242cb7aed6d55deffc59c4733077e44aad"
    ),
    PREDECESSOR_VERIFIER_RELATIVE_PATH: (
        "cb490e57706a7056b1794de3d470a4e1f52621379e0c0515a81c15fda38401fa"
    ),
}
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = (
    "bfa3bac51db218b5eda83e93cabd1b13b7a7b1f386f9344ab5c28c75857c1669"
)
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = (
    "515f533a0300e2c88a4831fa7acc71db7647b51ac1e1d2162e3fb40651b1e227"
)
EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256 = (
    "4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03"
)

EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)
PREDECESSOR_EVIDENCE_PATHS = (
    PREDECESSOR_WORKFLOW_RELATIVE_PATH,
    PREDECESSOR_PROFILE_RELATIVE_PATH,
    PREDECESSOR_MANIFEST_RELATIVE_PATH,
    PREDECESSOR_DOC_RELATIVE_PATH,
    PREDECESSOR_UNIT_RELATIVE_PATH,
    PREDECESSOR_VERIFIER_RELATIVE_PATH,
)
IMPLEMENTATION_DELTA_PATHS = (
    ADAPTER_RELATIVE_PATH,
    VENDOR_ADAPTER_RELATIVE_PATH,
)
EXPECTED_DELTA_PATHS = tuple(
    sorted(
        set(EVIDENCE_PATHS)
        | set(IMPLEMENTATION_DELTA_PATHS)
        | {PREDECESSOR_WORKFLOW_RELATIVE_PATH, PREDECESSOR_UNIT_RELATIVE_PATH},
        key=lambda path: path.as_posix(),
    )
)

OLD_DISPATCH = """    const std::int32_t raw_status = [&]() -> std::int32_t {
        if (compute_forces) {
            bg_rust_particle_mesh_reciprocal_force_output_v1 provider_forces{};
            active_provider_force_scratch.x.resize(atom_count);
            active_provider_force_scratch.y.resize(atom_count);
            active_provider_force_scratch.z.resize(atom_count);
            provider_forces.struct_size =
                static_cast<std::uint32_t>(sizeof(provider_forces));
            provider_forces.abi_version =
                BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
            provider_forces.capacity = atom_count;
            provider_forces.x = active_provider_force_scratch.x.data();
            provider_forces.y = active_provider_force_scratch.y.data();
            provider_forces.z = active_provider_force_scratch.z.data();
            return bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch.reciprocal_workspace,
                &active_provider_force_scratch.neutrality_sort_scratch,
                &active_provider_force_scratch.particle_assignment_scratch,
                &provider_energy, &provider_forces, &provider_error);
        }
        return bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch.reciprocal_workspace,
            &active_provider_force_scratch.neutrality_sort_scratch,
            &active_provider_force_scratch.particle_assignment_scratch,
            &provider_energy, &provider_error);
    }();
    const bg_status status = normalize_provider_status(raw_status);
"""

NEW_DISPATCH = """    const bg_status status = normalize_provider_status([&]() -> std::int32_t {
        if (compute_forces) {
            bg_rust_particle_mesh_reciprocal_force_output_v1 provider_forces{};
            active_provider_force_scratch.x.resize(atom_count);
            active_provider_force_scratch.y.resize(atom_count);
            active_provider_force_scratch.z.resize(atom_count);
            provider_forces.struct_size =
                static_cast<std::uint32_t>(sizeof(provider_forces));
            provider_forces.abi_version =
                BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION;
            provider_forces.capacity = atom_count;
            provider_forces.x = active_provider_force_scratch.x.data();
            provider_forces.y = active_provider_force_scratch.y.data();
            provider_forces.z = active_provider_force_scratch.z.data();
            return bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch.reciprocal_workspace,
                &active_provider_force_scratch.neutrality_sort_scratch,
                &active_provider_force_scratch.particle_assignment_scratch,
                &provider_energy, &provider_forces, &provider_error);
        }
        return bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch.reciprocal_workspace,
            &active_provider_force_scratch.neutrality_sort_scratch,
            &active_provider_force_scratch.particle_assignment_scratch,
            &provider_energy, &provider_error);
    }());
"""

sha = predecessor_verifier.sha
git = predecessor_verifier.git
canonical_bytes = predecessor_verifier.canonical_bytes


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail("%s replacement anchor drift" % label)
    return source.replace(old, new, 1)


def source_region(source: str, start: str, end: str, label: str) -> str:
    if source.count(start) != 1:
        fail("%s start marker drift" % label)
    start_index = source.index(start)
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        fail("%s end marker drift" % label)
    return source[start_index:end_index]


def frozen_bytes(path: Path) -> bytes:
    return git("show", "%s:%s" % (PREDECESSOR["merge_commit"], path)).stdout


def require_predecessor() -> dict:
    merge = PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("PR 479 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 479 predecessor merge identity drift")
    tree = git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
    if tree != PREDECESSOR["merge_tree"]:
        fail("PR 479 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 479 predecessor")
    for path, expected_sha in PREDECESSOR_EVIDENCE_SHA256.items():
        if sha(frozen_bytes(path)) != expected_sha:
            fail("exact frozen PR 479 evidence digest drift: %s" % path)
    profile_raw = frozen_bytes(PREDECESSOR_PROFILE_RELATIVE_PATH)
    manifest_raw = frozen_bytes(PREDECESSOR_MANIFEST_RELATIVE_PATH)
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 479 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 405:
        fail("PR 479 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted(
        {row.get("path") for row in rows}
    ):
        fail("PR 479 predecessor manifest paths are not sorted and unique")
    for path in (
        PREDECESSOR_PROFILE_RELATIVE_PATH,
        PREDECESSOR_MANIFEST_RELATIVE_PATH,
        PREDECESSOR_DOC_RELATIVE_PATH,
        PREDECESSOR_VERIFIER_RELATIVE_PATH,
    ):
        if (ROOT / path).read_bytes() != frozen_bytes(path):
            fail("checked-out PR 479 predecessor evidence drift: %s" % path)
    reviewed = PREDECESSOR["reviewed_head"]
    if git("cat-file", "-e", "%s^{commit}" % reviewed, check=False).returncode == 0:
        reviewed_tree = git("rev-parse", "%s^{tree}" % reviewed).stdout.strip().decode()
        if reviewed_tree != PREDECESSOR["merge_tree"]:
            fail("PR 479 reviewed-head tree drift")
    return manifest


def current_delta_paths() -> tuple[Path, ...]:
    tracked = git(
        "diff", "--name-only", PREDECESSOR["merge_commit"], "--"
    ).stdout.decode().splitlines()
    untracked = git(
        "ls-files", "--others", "--exclude-standard"
    ).stdout.decode().splitlines()
    return tuple(
        sorted({Path(path) for path in tracked + untracked}, key=lambda p: p.as_posix())
    )


def discover_source_paths(root: Path = ROOT) -> list[Path]:
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
    if len(result) != 411:
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
            "dispatch_status_normalization_binding_current_sources_tests_evidence_"
            "pr479_target"
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }


def build_profile(manifest_raw: bytes, root: Path = ROOT) -> dict:
    manifest = json.loads(manifest_raw)
    profile = json.loads((root / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes())
    profile["schema_id"] = SCHEMA_ID
    profile["profile_id"] = "%s_development_v1" % STEM
    profile["target_predecessor"] = dict(PREDECESSOR)
    implementation = profile["implementation"]
    implementation.pop("scope_is_only_native_dispatch_status_single_assignment", None)
    implementation.update(
        {
            "scope_is_only_native_dispatch_status_normalization_binding": True,
            "provider_status_normalized_at_initialization_boundary": True,
            "standalone_raw_dispatch_status_binding_removed": True,
            "unchecked_provider_status_lifetime_confined_to_dispatch_expression": True,
            "normalized_dispatch_status_is_const": True,
            "dispatch_iife_directly_consumed_by_status_normalization": True,
            "dispatch_status_initialized_exactly_once": True,
            "dispatch_status_is_const": True,
            "dispatch_status_uses_explicit_return_type_iife": True,
            "dispatch_status_iife_immediately_invoked": True,
            "uninitialized_dispatch_status_removed": True,
            "dispatch_status_branch_assignments_removed": True,
            "force_branch_returns_force_provider_status": True,
            "energy_branch_returns_energy_provider_status": True,
            "force_descriptor_branch_localization_preserved": True,
            "provider_error_descriptor_remains_common_to_both_dispatch_branches": True,
            "post_dispatch_validation_and_commit_preserved": True,
            "single_assignment_performance_improvement_claimed": False,
            "iife_performance_improvement_claimed": False,
            "const_status_performance_improvement_claimed": False,
            "normalization_binding_performance_improvement_claimed": False,
            "raw_status_lifetime_reduction_performance_improvement_claimed": False,
            "direct_normalization_performance_improvement_claimed": False,
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
            "source_manifest_entry_count": len(manifest["files"]),
        }
    )
    validation = profile["validation"]
    for stale_key in (
        "predecessor_adapter_exact_dispatch_status_single_assignment_transform",
        "predecessor_adapter_exact_force_descriptor_branch_localization_transform",
        "relocated_force_descriptor_preparation_exact_predecessor_bytes",
        "adapter_dispatch_exact_after_branch_local_preparation_normalization",
        "energy_branch_exact_predecessor_bytes",
    ):
        validation.pop(stale_key, None)
    validation.update(
        {
            "exact_delta_path_count": 10,
            "implementation_delta_path_count": 2,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 411,
            "pull_request_trigger_path_count_exact": 228,
            "push_trigger_path_count_exact": 228,
            "predecessor_adapter_exact_dispatch_status_normalization_binding_transform": True,
            "dispatch_status_const_declaration_count_exact": 1,
            "standalone_raw_status_declaration_count_exact": 0,
            "raw_status_identifier_count_exact": 0,
            "normalized_status_const_declaration_count_exact": 1,
            "normalize_provider_status_call_count_exact": 1,
            "normalize_provider_status_iife_argument_count_exact": 1,
            "unchecked_provider_status_post_dispatch_binding_count_exact": 0,
            "dispatch_status_uninitialized_declaration_count_exact": 0,
            "dispatch_status_branch_assignment_count_exact": 0,
            "dispatch_status_iife_count_exact": 1,
            "dispatch_status_iife_explicit_return_type_count_exact": 1,
            "dispatch_status_provider_return_count_exact": 2,
            "force_branch_provider_return_count_exact": 1,
            "energy_branch_provider_return_count_exact": 1,
            "provider_error_common_scope_exact_predecessor_bytes": True,
            "force_descriptor_branch_localization_preserved_by_exact_dispatch_transform": True,
            "post_dispatch_validation_and_commit_exact_predecessor_bytes": True,
            "canonical_vendor_adapter_byte_identical": True,
            "native_adapter_test_exact_predecessor_bytes": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
        }
    )
    return profile


def expected_predecessor_workflow() -> str:
    expected = frozen_bytes(PREDECESSOR_WORKFLOW_RELATIVE_PATH).decode()
    for predecessor_path, successor_path in zip(
        PREDECESSOR_EVIDENCE_PATHS, EVIDENCE_PATHS, strict=True
    ):
        anchor = '      - "%s"\n' % predecessor_path.as_posix()
        if expected.count(anchor) != 2:
            fail("exact PR 479 workflow trigger anchor drift: %s" % predecessor_path)
        expected = expected.replace(
            anchor, anchor + '      - "%s"\n' % successor_path.as_posix()
        )
    old_region = source_region(
        expected,
        "      - name: Materialize exact PR 478 target and reviewed head\n",
        "\n\n  native-linux:\n",
        "exact PR 479 immutable-evidence block",
    )
    new_region = """      - name: Materialize exact PR 479 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 0f723b265c6366c0037d83d9ed9e934817fd9626^{tree})" = "619ad7bf2e6b74b80e6e7594b5b3c91f5e72b514"
          git merge-base --is-ancestor 0f723b265c6366c0037d83d9ed9e934817fd9626 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/479/head
          test "$(git rev-parse FETCH_HEAD)" = "f62a5f68a59a94ffe0d2b20900e1f8c4d82b6eb8"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "619ad7bf2e6b74b80e6e7594b5b3c91f5e72b514"
      - name: Verify exact frozen PR 479 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=0f723b265c6366c0037d83d9ed9e934817fd9626
          frozen_tree=619ad7bf2e6b74b80e6e7594b5b3c91f5e72b514
          current_sha="$(git rev-parse HEAD)"
          restore() { git checkout --detach --quiet "$current_sha"; }
          trap restore EXIT
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_dispatch_status_single_assignment_v1.py
          restore
          trap - EXIT"""
    return replace_once(
        expected, old_region, new_region, "exact PR 479 predecessor workflow transform"
    )


def expected_predecessor_unit() -> str:
    expected = frozen_bytes(PREDECESSOR_UNIT_RELATIVE_PATH).decode()
    expected = replace_once(
        expected,
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport pytest\n",
        "exact PR 479 unit pytest import",
    )
    skip = """ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_DISPATCH_STATUS_NORMALIZATION_BINDING_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_dispatch_status_normalization_binding_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_DISPATCH_STATUS_NORMALIZATION_BINDING_EVIDENCE_PRESENT,
    reason=(
        "dispatch status single-assignment evidence is verified from its exact frozen "
        "PR 479 object after status normalization binding evidence is present"
    ),
)"""
    return replace_once(
        expected,
        "ROOT = Path(__file__).resolve().parents[2]",
        skip,
        "exact PR 479 unit successor skip",
    )


def expected_successor_workflow() -> str:
    old_hyphen = "rust-reciprocal-provider-dispatch-status-single-assignment"
    new_hyphen = "rust-reciprocal-provider-dispatch-status-normalization-binding"
    old_underscore = "rust_reciprocal_provider_dispatch_status_single_assignment"
    new_underscore = "rust_reciprocal_provider_dispatch_status_normalization_binding"
    expected = frozen_bytes(PREDECESSOR_WORKFLOW_RELATIVE_PATH).decode()
    expected = expected.replace(old_hyphen, new_hyphen)
    expected = expected.replace(old_underscore, new_underscore)
    predecessor_workflow_path = (
        ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
        "dynamics-rust-reciprocal-provider-status-single-assignment.yml"
    )
    if expected.count(predecessor_workflow_path) != 2:
        fail("successor predecessor workflow path anchor drift")
    expected = expected.replace(
        predecessor_workflow_path, WORKFLOW_RELATIVE_PATH.as_posix()
    )
    for predecessor_path, successor_path in zip(
        PREDECESSOR_EVIDENCE_PATHS, EVIDENCE_PATHS, strict=True
    ):
        anchor = '      - "%s"\n' % successor_path.as_posix()
        if expected.count(anchor) != 2:
            fail("successor workflow trigger anchor drift: %s" % successor_path)
        expected = expected.replace(
            anchor, '      - "%s"\n' % predecessor_path.as_posix() + anchor
        )
    replacements = (
        ("Materialize exact PR 478 target", "Materialize exact PR 479 target"),
        ("e02cb7721e50d35f0a8680cec12ac24801450bba", PREDECESSOR["merge_commit"]),
        ("6369559489af14a8bfe604ab6af2cdc9b298e722", PREDECESSOR["merge_tree"]),
        ("refs/pull/478/head", "refs/pull/479/head"),
        ("c61fd0637c25cbb09c762f6ed5dea70814bf7145", PREDECESSOR["reviewed_head"]),
    )
    for old, new in replacements:
        if old not in expected:
            fail("successor workflow predecessor pin anchor drift: %s" % old)
        expected = expected.replace(old, new)
    return expected


def workflow_trigger_paths(workflow: str, event: str, end: str) -> tuple[str, ...]:
    region = source_region(
        workflow, "  %s:\n" % event, "  %s:\n" % end, "%s trigger" % event
    )
    return tuple(re.findall(r'^      - "([^"]+)"$', region, flags=re.MULTILINE))


def require_workflow_contract(root: Path = ROOT) -> None:
    predecessor = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    successor = (root / WORKFLOW_RELATIVE_PATH).read_text()
    if predecessor != expected_predecessor_workflow():
        fail("PR 479 predecessor workflow is not the exact frozen-object transform")
    if successor != expected_successor_workflow():
        fail("successor workflow is not the exact PR 479-derived transform")
    expected_names = {
        PREDECESSOR_WORKFLOW_RELATIVE_PATH: PREDECESSOR_WORKFLOW_STEM,
        WORKFLOW_RELATIVE_PATH: WORKFLOW_STEM,
    }
    for path, expected_name in expected_names.items():
        workflow = (root / path).read_text()
        pull_paths = workflow_trigger_paths(workflow, "pull_request", "push")
        push_paths = workflow_trigger_paths(workflow, "push", "workflow_dispatch")
        if len(pull_paths) != 228 or len(set(pull_paths)) != 228:
            fail("workflow 228-path unique pull-request trigger drift: %s" % path)
        if push_paths != pull_paths:
            fail("workflow pull-request/push trigger symmetry drift: %s" % path)
        if workflow.count("name: %s\n" % expected_name) != 1:
            fail("workflow name drift: %s" % path)
        if workflow.count(PINNED_CHECKOUT_ACTION) != 4:
            fail("workflow checkout pin drift: %s" % path)
        if "--refresh" in workflow:
            fail("workflow must not refresh evidence: %s" % path)
    for path in EVIDENCE_PATHS + PREDECESSOR_EVIDENCE_PATHS:
        token = '      - "%s"\n' % path.as_posix()
        if successor.count(token) != 2:
            fail("successor workflow evidence trigger drift: %s" % path)
        if predecessor.count(token) != 2:
            fail("predecessor workflow successor trigger drift: %s" % path)
    for token in (
        "git checkout --detach --quiet \"$frozen\"",
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        "refs/pull/479/head",
        PREDECESSOR["reviewed_head"],
    ):
        if token not in predecessor:
            fail("PR 479 predecessor workflow freeze drift: %s" % token)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    source = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if source != expected_predecessor_unit():
        fail("PR 479 predecessor unit is not the exact frozen-object transform")
    tree = ast.parse(source)
    constants = {
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance((value := node.value), str)
    }
    if not any("PR 479 object" in value for value in constants):
        fail("PR 479 predecessor unit frozen-object reason drift")
    if source.count("pytest.mark.skipif(") != 1:
        fail("PR 479 predecessor unit skip drift")


def require_adapter_contract(root: Path = ROOT) -> None:
    frozen = frozen_bytes(ADAPTER_RELATIVE_PATH)
    if sha(frozen) != EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256:
        fail("exact PR 479 adapter digest drift")
    frozen_source = frozen.decode()
    expected = replace_once(
        frozen_source, OLD_DISPATCH, NEW_DISPATCH, "dispatch status normalization binding"
    )
    for path in IMPLEMENTATION_DELTA_PATHS:
        raw = (root / path).read_bytes()
        if sha(raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256:
            fail("successor adapter digest drift: %s" % path)
        if raw.decode() != expected:
            fail("adapter is not the exact PR 479 normalization-binding transform: %s" % path)
    canonical = (root / ADAPTER_RELATIVE_PATH).read_text()
    vendor = (root / VENDOR_ADAPTER_RELATIVE_PATH).read_text()
    if canonical != vendor:
        fail("canonical/vendor adapter byte identity drift")
    dispatch = source_region(
        canonical,
        "    const bg_status status = normalize_provider_status([&]() -> std::int32_t {\n",
        "    provider_error.detail[",
        "normalization-bound dispatch",
    )
    if canonical.count("raw_status") != 0:
        fail("standalone raw dispatch status binding remains")
    if dispatch.count("const bg_status status = normalize_provider_status(") != 1:
        fail("normalized status direct-binding declaration count drift")
    if dispatch.count("normalize_provider_status(") != 1:
        fail("dispatch normalization call count drift")
    if dispatch.count("[&]() -> std::int32_t {") != 1 or dispatch.count("}());") != 1:
        fail("explicit-return-type immediately-invoked lambda drift")
    if dispatch.count("if (compute_forces)") != 1 or "else" in dispatch:
        fail("two-return compute-forces dispatch shape drift")
    if dispatch.count("return " + FORCE_PRIVATE_SYMBOL + "(") != 1:
        fail("force provider status return count drift")
    if dispatch.count("return " + PRIVATE_SYMBOL + "(") != 1:
        fail("energy provider status return count drift")
    energy_branch = dispatch[dispatch.index("        return " + PRIVATE_SYMBOL) :]
    if "provider_forces" in energy_branch:
        fail("energy branch gained a force descriptor reference")
    if dispatch.count("bg_rust_particle_mesh_reciprocal_force_output_v1 provider_forces{};") != 1:
        fail("force descriptor branch-local declaration drift")
    test_raw = (root / ADAPTER_TEST_RELATIVE_PATH).read_bytes()
    if sha(frozen_bytes(ADAPTER_TEST_RELATIVE_PATH)) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("exact PR 479 native adapter test digest drift")
    if sha(test_raw) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("native adapter test changed from exact PR 479 bytes")


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    required = (
        "exact PR 479 predecessor",
        "explicit `std::int32_t` return type",
        "immediately invoked",
        "`const bg_status status`",
        "direct argument to `normalize_provider_status`",
        "zero standalone `raw_status` bindings",
        "unchecked provider status exists only inside the dispatch expression",
        "force descriptor remains local to the force branch",
        "common `provider_error` descriptor",
        "post-dispatch validation, rollback, and commit remain exact PR 479 bytes",
        "four blockers",
        "32 unresolved operational decisions",
        "No performance, acceleration, scientific, molecular, HIP, product, or operational claim",
    )
    for token in required:
        if token not in doc:
            fail("documentation contract drift: %s" % token)


def require_profile_and_manifest(root: Path = ROOT) -> tuple[dict, dict]:
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    profile = json.loads(profile_raw)
    if canonical_bytes(manifest) != manifest_raw or canonical_bytes(profile) != profile_raw:
        fail("successor evidence is not canonical JSON")
    if manifest != build_source_manifest(root):
        fail("source manifest drift; run verifier with --refresh")
    if profile != build_profile(manifest_raw, root):
        fail("profile drift; run verifier with --refresh")
    implementation = profile["implementation"]
    for key in (
        "scope_is_only_native_dispatch_status_normalization_binding",
        "provider_status_normalized_at_initialization_boundary",
        "standalone_raw_dispatch_status_binding_removed",
        "unchecked_provider_status_lifetime_confined_to_dispatch_expression",
        "normalized_dispatch_status_is_const",
        "dispatch_iife_directly_consumed_by_status_normalization",
        "dispatch_status_initialized_exactly_once",
        "dispatch_status_is_const",
        "dispatch_status_uses_explicit_return_type_iife",
        "dispatch_status_iife_immediately_invoked",
        "uninitialized_dispatch_status_removed",
        "dispatch_status_branch_assignments_removed",
        "force_branch_returns_force_provider_status",
        "energy_branch_returns_energy_provider_status",
        "force_descriptor_branch_localization_preserved",
        "provider_error_descriptor_remains_common_to_both_dispatch_branches",
        "post_dispatch_validation_and_commit_preserved",
    ):
        if implementation.get(key) is not True:
            fail("implementation evidence drift: %s" % key)
    false_claims = (
        "single_assignment_performance_improvement_claimed",
        "iife_performance_improvement_claimed",
        "const_status_performance_improvement_claimed",
        "normalization_binding_performance_improvement_claimed",
        "raw_status_lifetime_reduction_performance_improvement_claimed",
        "direct_normalization_performance_improvement_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "molecular_execution_claimed",
        "hip_execution_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    )
    for key in false_claims:
        if implementation.get(key) is not False:
            fail("forbidden claim drift: %s" % key)
    if any(profile["authority"].values()):
        fail("authority boundary drift")
    boundary = profile["operational_boundary"]
    if len(boundary.get("blockers", [])) != 4:
        fail("operational blocker count drift")
    if boundary.get("unresolved_operational_decisions") != 32:
        fail("unresolved operational decision count drift")
    return profile, manifest


def require_contracts(root: Path = ROOT) -> None:
    require_predecessor()
    delta = current_delta_paths()
    if delta != EXPECTED_DELTA_PATHS:
        fail(
            "exact delta path drift: expected=%s actual=%s"
            % (
                [path.as_posix() for path in EXPECTED_DELTA_PATHS],
                [path.as_posix() for path in delta],
            )
        )
    require_workflow_contract(root)
    require_predecessor_unit_freeze(root)
    ast.parse((root / UNIT_RELATIVE_PATH).read_text())
    ast.parse((root / VERIFIER_RELATIVE_PATH).read_text())
    require_adapter_contract(root)
    require_docs_contract(root)


def verify(root: Path = ROOT) -> dict:
    require_contracts(root)
    profile, manifest = require_profile_and_manifest(root)
    return {
        "schema_id": profile["schema_id"],
        "source_count": len(manifest["files"]),
        "delta_path_count": len(EXPECTED_DELTA_PATHS),
        "implementation_delta_path_count": len(IMPLEMENTATION_DELTA_PATHS),
        "trigger_path_count": 228,
        "predecessor_pull_request": PREDECESSOR["pull_request"],
        "predecessor_merge_tree": PREDECESSOR["merge_tree"],
    }


def refresh(root: Path = ROOT) -> dict:
    require_contracts(root)
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    profile = build_profile(manifest_raw, root)
    (root / PROFILE_RELATIVE_PATH).write_bytes(canonical_bytes(profile))
    return verify(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="refresh canonical profile and manifest"
    )
    args = parser.parse_args()
    result = refresh(ROOT) if args.refresh else verify(ROOT)
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
