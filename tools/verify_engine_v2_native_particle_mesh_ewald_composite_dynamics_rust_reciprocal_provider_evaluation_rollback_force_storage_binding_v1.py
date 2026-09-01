#!/usr/bin/env python3
"""Verify native PME Rust-adapter evaluation rollback force-storage binding."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
from typing import NoReturn

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_state_binding_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_evaluation_rollback_force_storage_binding"
)
WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-evaluation-rollback-force-storage-binding"
)
WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-evaluation-rollback-force-storage-binding"
)
PREDECESSOR_STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_evaluation_rollback_state_binding"
)
PREDECESSOR_WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-evaluation-rollback-state-binding"
)
PREDECESSOR_WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-evaluation-rollback-state-binding"
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
    "rust_reciprocal_provider_evaluation_rollback_force_storage_binding_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_evaluation_rollback_force_storage_binding_sources/1.0.0"
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
    "pull_request": 481,
    "reviewed_head": "bae72aefcf609029c45211ecaa28de7d86d8bd4d",
    "merge_commit": "214f11daf45997826f142544bb02dc6c7831b8ee",
    "merge_tree": "d8360b665efa6c6292ea7a690a3839f6200e2396",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "6ca14b72687d4ddb6b80cf70f7ff012e4384ba9cb708a77c1b6673156ad71460"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "2e22e52cf8745fe2ab48de47bb4e5073a4fe80c05d311543fbec29b75a5fbbb8"
    ),
    "source_manifest_entry_count": 417,
}

PREDECESSOR_EVIDENCE_SHA256 = {
    PREDECESSOR_WORKFLOW_RELATIVE_PATH: (
        "00fa7314666d4c242de0e604b0ce22e17a1ad5466a107a49a128bcc0beedd87f"
    ),
    PREDECESSOR_PROFILE_RELATIVE_PATH: PREDECESSOR["profile_sha256"],
    PREDECESSOR_MANIFEST_RELATIVE_PATH: PREDECESSOR["source_manifest_sha256"],
    PREDECESSOR_DOC_RELATIVE_PATH: (
        "3504369ca0dbcad135d9c2b1cc1a00feaab81ceb7f0fc5f379f0e7d30068ce0d"
    ),
    PREDECESSOR_UNIT_RELATIVE_PATH: (
        "852f52a2a8e2323805587be24c91a88827897488738e4995dc8bb6bfc12ebda8"
    ),
    PREDECESSOR_VERIFIER_RELATIVE_PATH: (
        "e4c9b688e596f84694a44b76037380a93a179855aeaa7f4cad3673d91d2b2b5c"
    ),
}
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = (
    "3ac73fad9bc7c4852d640d6ef6c690fdf6490f961c16fcb4ff50e2e90b3d5941"
)
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = (
    "70ad84edb0a4458a5971e4e23aff6625908faa6f7eda21133fa7a47f6722aa2a"
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

OLD_FORCE_STORAGE_TYPE_BINDING = """static_assert(std::is_nothrow_move_assignable_v<Evaluation>);
static_assert(std::is_nothrow_swappable_v<decltype(Evaluation{}.forces)>);"""

NEW_FORCE_STORAGE_TYPE_BINDING = """using EvaluationForceStorage = decltype(Evaluation::forces);

static_assert(std::is_nothrow_move_assignable_v<Evaluation>);
static_assert(std::is_nothrow_swappable_v<EvaluationForceStorage>);"""

OLD_ROLLBACK_CLASS = """class EvaluationForceStorageRollback final {
  public:
    EvaluationForceStorageRollback(
        Evaluation *output,
        Evaluation &candidate) noexcept
        : output_(output), candidate_(candidate) {
        if (output_ != nullptr) {
            candidate_.forces.swap(output_->forces);
        }
    }

    EvaluationForceStorageRollback(
        const EvaluationForceStorageRollback &) = delete;
    EvaluationForceStorageRollback &operator=(
        const EvaluationForceStorageRollback &) = delete;

    ~EvaluationForceStorageRollback() noexcept {
        if (output_ != nullptr) {
            candidate_.forces.swap(output_->forces);
        }
    }

    void commit() noexcept {
        output_ = nullptr;
    }

  private:
    Evaluation *output_;
    Evaluation &candidate_;
};"""

NEW_ROLLBACK_CLASS = """class EvaluationForceStorageRollback final {
  public:
    EvaluationForceStorageRollback(
        Evaluation *output,
        EvaluationForceStorage &candidate_forces) noexcept
        : output_(output), candidate_forces_(candidate_forces) {
        if (output_ != nullptr) {
            candidate_forces_.swap(output_->forces);
        }
    }

    EvaluationForceStorageRollback(
        const EvaluationForceStorageRollback &) = delete;
    EvaluationForceStorageRollback &operator=(
        const EvaluationForceStorageRollback &) = delete;

    ~EvaluationForceStorageRollback() noexcept {
        if (output_ != nullptr) {
            candidate_forces_.swap(output_->forces);
        }
    }

    void commit() noexcept {
        output_ = nullptr;
    }

  private:
    Evaluation *output_;
    EvaluationForceStorage &candidate_forces_;
};"""

OLD_ROLLBACK_CONSTRUCTION = """    Evaluation candidate;
    EvaluationForceStorageRollback evaluation_force_storage_rollback{
        compute_forces && reuse_force_storage ? out_evaluation : nullptr,
        candidate};
"""

NEW_ROLLBACK_CONSTRUCTION = """    Evaluation candidate;
    EvaluationForceStorageRollback evaluation_force_storage_rollback{
        compute_forces && reuse_force_storage ? out_evaluation : nullptr,
        candidate.forces};
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
        fail("PR 481 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 481 predecessor merge identity drift")
    tree = git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
    if tree != PREDECESSOR["merge_tree"]:
        fail("PR 481 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 481 predecessor")
    for path, expected_sha in PREDECESSOR_EVIDENCE_SHA256.items():
        if sha(frozen_bytes(path)) != expected_sha:
            fail("exact frozen PR 481 evidence digest drift: %s" % path)
    profile_raw = frozen_bytes(PREDECESSOR_PROFILE_RELATIVE_PATH)
    manifest_raw = frozen_bytes(PREDECESSOR_MANIFEST_RELATIVE_PATH)
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 481 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 417:
        fail("PR 481 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted(
        {row.get("path") for row in rows}
    ):
        fail("PR 481 predecessor manifest paths are not sorted and unique")
    for path in (
        PREDECESSOR_PROFILE_RELATIVE_PATH,
        PREDECESSOR_MANIFEST_RELATIVE_PATH,
        PREDECESSOR_DOC_RELATIVE_PATH,
        PREDECESSOR_VERIFIER_RELATIVE_PATH,
    ):
        if (ROOT / path).read_bytes() != frozen_bytes(path):
            fail("checked-out PR 481 predecessor evidence drift: %s" % path)
    reviewed = PREDECESSOR["reviewed_head"]
    if git("cat-file", "-e", "%s^{commit}" % reviewed, check=False).returncode == 0:
        reviewed_tree = git("rev-parse", "%s^{tree}" % reviewed).stdout.strip().decode()
        if reviewed_tree != PREDECESSOR["merge_tree"]:
            fail("PR 481 reviewed-head tree drift")
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
    if len(result) != 423:
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
            "evaluation_rollback_force_storage_binding_current_sources_tests_evidence_"
            "pr481_target"
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
    for stale_key in (
        "scope_is_only_native_evaluation_rollback_state_binding",
        "evaluation_rollback_candidate_is_non_null_reference",
        "evaluation_rollback_candidate_reference_bound_once",
        "evaluation_rollback_candidate_uses_reference_member_access",
        "evaluation_rollback_state_binding_performance_improvement_claimed",
    ):
        implementation.pop(stale_key, None)
    implementation.update(
        {
            "scope_is_only_native_evaluation_rollback_force_storage_binding": True,
            "evaluation_rollback_candidate_force_storage_type_alias_exact": True,
            "evaluation_rollback_candidate_force_storage_type_derived_from_evaluation_member": True,
            "evaluation_rollback_candidate_force_storage_nothrow_swap_assertion_exact": True,
            "evaluation_rollback_candidate_force_storage_is_non_null_reference": True,
            "evaluation_rollback_candidate_force_storage_reference_bound_once": True,
            "evaluation_rollback_whole_candidate_reference_parameter_removed": True,
            "evaluation_rollback_whole_candidate_reference_member_removed": True,
            "evaluation_rollback_candidate_force_storage_uses_direct_reference_access": True,
            "evaluation_rollback_callsite_passes_candidate_force_storage": True,
            "evaluation_rollback_candidate_declaration_precedes_guard": True,
            "evaluation_rollback_candidate_force_storage_lifetime_order_preserved": True,
            "evaluation_rollback_output_pointer_is_sole_activation_and_commit_sentinel": True,
            "evaluation_rollback_initial_swap_and_destructor_restore_preserved": True,
            "evaluation_rollback_commit_disarms_via_output_only": True,
            "evaluation_rollback_copy_deletion_preserved": True,
            "five_semantic_route_rollback_activation_truth_table_preserved": True,
            "dispatch_status_normalization_binding_preserved": True,
            "evaluation_rollback_force_storage_binding_performance_improvement_claimed": False,
            "evaluation_rollback_force_storage_reference_performance_improvement_claimed": False,
            "evaluation_rollback_force_storage_object_layout_equivalence_claimed": False,
            "evaluation_rollback_force_storage_runtime_lifetime_enforcement_claimed": False,
            "evaluation_rollback_guard_is_force_storage_only_claimed": False,
            "evaluation_rollback_candidate_reference_performance_improvement_claimed": False,
            "evaluation_rollback_enabled_parameter_removal_performance_improvement_claimed": False,
            "evaluation_rollback_object_layout_equivalence_claimed": False,
            "evaluation_rollback_reference_runtime_lifetime_enforcement_claimed": False,
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
            "source_manifest_entry_count": len(manifest["files"]),
        }
    )
    validation = profile["validation"]
    for stale_key in (
        "predecessor_adapter_exact_evaluation_rollback_state_binding_transform",
        "evaluation_rollback_state_binding_source_exact",
        "adapter_outside_evaluation_rollback_state_regions_exact_predecessor_bytes",
        "rollback_candidate_reference_declaration_count_exact",
        "rollback_candidate_reference_member_access_count_exact",
        "rollback_candidate_reference_initializer_count_exact",
        "rollback_candidate_reference_callsite_count_exact",
    ):
        validation.pop(stale_key, None)
    validation.update(
        {
            "exact_delta_path_count": 10,
            "implementation_delta_path_count": 2,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 423,
            "pull_request_trigger_path_count_exact": 240,
            "push_trigger_path_count_exact": 240,
            "predecessor_adapter_exact_evaluation_rollback_force_storage_binding_transform": True,
            "evaluation_rollback_force_storage_binding_source_exact": True,
            "adapter_outside_evaluation_rollback_force_storage_regions_exact_predecessor_bytes": True,
            "rollback_force_storage_type_binding_region_exact": True,
            "dispatch_status_normalization_region_exact_predecessor_bytes": True,
            "rollback_class_count_exact": 1,
            "rollback_candidate_pointer_declaration_count_exact": 0,
            "rollback_candidate_pointer_member_access_count_exact": 0,
            "rollback_candidate_null_assignment_count_exact": 0,
            "rollback_candidate_conditional_initializer_count_exact": 0,
            "rollback_candidate_address_callsite_count_exact": 0,
            "rollback_force_storage_alias_count_exact": 1,
            "rollback_force_storage_alias_static_assert_count_exact": 1,
            "rollback_legacy_force_storage_type_expression_count_exact": 0,
            "rollback_whole_candidate_reference_declaration_count_exact": 0,
            "rollback_force_storage_reference_declaration_count_exact": 2,
            "rollback_force_storage_reference_initializer_count_exact": 1,
            "rollback_force_storage_reference_member_access_count_exact": 2,
            "rollback_whole_candidate_callsite_count_exact": 0,
            "rollback_force_storage_callsite_count_exact": 1,
            "rollback_enabled_parameter_count_exact": 0,
            "rollback_output_enabled_initializer_count_exact": 0,
            "rollback_output_direct_initializer_count_exact": 1,
            "rollback_callsite_activation_conditional_count_exact": 1,
            "rollback_output_null_assignment_count_exact": 1,
            "rollback_output_nonnull_guard_count_exact": 2,
            "rollback_copy_deletion_count_exact": 2,
            "rollback_force_swap_count_exact": 2,
            "rollback_guard_construction_count_exact": 1,
            "rollback_commit_call_count_exact": 1,
            "rollback_candidate_declaration_precedes_guard": True,
            "rollback_guard_precedes_optional_scratch_declaration": True,
            "rollback_activation_predicate_exact": True,
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
            fail("exact PR 481 workflow trigger anchor drift: %s" % predecessor_path)
        expected = expected.replace(
            anchor, anchor + '      - "%s"\n' % successor_path.as_posix()
        )
    old_region = source_region(
        expected,
        "      - name: Materialize exact PR 480 target and reviewed head\n",
        "\n\n  native-linux:\n",
        "exact PR 481 immutable-evidence block",
    )
    new_region = """      - name: Materialize exact PR 481 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 214f11daf45997826f142544bb02dc6c7831b8ee^{tree})" = "d8360b665efa6c6292ea7a690a3839f6200e2396"
          git merge-base --is-ancestor 214f11daf45997826f142544bb02dc6c7831b8ee HEAD
          git fetch --no-tags --depth=1 origin refs/pull/481/head
          test "$(git rev-parse FETCH_HEAD)" = "bae72aefcf609029c45211ecaa28de7d86d8bd4d"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "d8360b665efa6c6292ea7a690a3839f6200e2396"
      - name: Verify exact frozen PR 481 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=214f11daf45997826f142544bb02dc6c7831b8ee
          frozen_tree=d8360b665efa6c6292ea7a690a3839f6200e2396
          current_sha="$(git rev-parse HEAD)"
          restore() { git checkout --detach --quiet "$current_sha"; }
          trap restore EXIT
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_state_binding_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_state_binding_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_state_binding_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_evaluation_rollback_state_binding_v1.py
          restore
          trap - EXIT"""
    return replace_once(
        expected, old_region, new_region, "exact PR 481 predecessor workflow transform"
    )


def expected_predecessor_unit() -> str:
    expected = frozen_bytes(PREDECESSOR_UNIT_RELATIVE_PATH).decode()
    expected = replace_once(
        expected,
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport pytest\n",
        "exact PR 481 unit pytest import",
    )
    skip = """ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_EVALUATION_ROLLBACK_FORCE_STORAGE_BINDING_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_evaluation_rollback_force_storage_binding_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_EVALUATION_ROLLBACK_FORCE_STORAGE_BINDING_EVIDENCE_PRESENT,
    reason=(
        "evaluation rollback-state binding evidence is verified from its exact "
        "frozen PR 481 object after rollback force-storage binding evidence is present"
    ),
)"""
    return replace_once(
        expected,
        "ROOT = Path(__file__).resolve().parents[2]",
        skip,
        "exact PR 481 unit successor skip",
    )


def expected_successor_workflow() -> str:
    old_hyphen = "rust-reciprocal-provider-evaluation-rollback-state-binding"
    new_hyphen = "rust-reciprocal-provider-evaluation-rollback-force-storage-binding"
    old_underscore = "rust_reciprocal_provider_evaluation_rollback_state_binding"
    new_underscore = "rust_reciprocal_provider_evaluation_rollback_force_storage_binding"
    expected = frozen_bytes(PREDECESSOR_WORKFLOW_RELATIVE_PATH).decode()
    expected = expected.replace(old_hyphen, new_hyphen)
    expected = expected.replace(old_underscore, new_underscore)
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
        ("Materialize exact PR 480 target", "Materialize exact PR 481 target"),
        ("3b301c25c019e132c8dabba10894d09d5ef25e98", PREDECESSOR["merge_commit"]),
        ("eacae3fe0453ccb1c8769d8e1753e3f22cd5ccca", PREDECESSOR["merge_tree"]),
        ("refs/pull/480/head", "refs/pull/481/head"),
        ("9b5277aae0ba1335de04b37ad76b9b9e66db26df", PREDECESSOR["reviewed_head"]),
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
        fail("PR 481 predecessor workflow is not the exact frozen-object transform")
    if successor != expected_successor_workflow():
        fail("successor workflow is not the exact PR 481-derived transform")
    expected_names = {
        PREDECESSOR_WORKFLOW_RELATIVE_PATH: PREDECESSOR_WORKFLOW_STEM,
        WORKFLOW_RELATIVE_PATH: WORKFLOW_STEM,
    }
    for path, expected_name in expected_names.items():
        workflow = (root / path).read_text()
        pull_paths = workflow_trigger_paths(workflow, "pull_request", "push")
        push_paths = workflow_trigger_paths(workflow, "push", "workflow_dispatch")
        if len(pull_paths) != 240 or len(set(pull_paths)) != 240:
            fail("workflow 240-path unique pull-request trigger drift: %s" % path)
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
        "refs/pull/481/head",
        PREDECESSOR["reviewed_head"],
    ):
        if token not in predecessor:
            fail("PR 481 predecessor workflow freeze drift: %s" % token)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    source = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if source != expected_predecessor_unit():
        fail("PR 481 predecessor unit is not the exact frozen-object transform")
    tree = ast.parse(source)
    constants = {
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance((value := node.value), str)
    }
    if not any("PR 481 object" in value for value in constants):
        fail("PR 481 predecessor unit frozen-object reason drift")
    if source.count("pytest.mark.skipif(") != 1:
        fail("PR 481 predecessor unit skip drift")


def require_adapter_contract(root: Path = ROOT) -> None:
    frozen = frozen_bytes(ADAPTER_RELATIVE_PATH)
    if sha(frozen) != EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256:
        fail("exact PR 481 adapter digest drift")
    frozen_source = frozen.decode()
    expected = replace_once(
        frozen_source,
        OLD_FORCE_STORAGE_TYPE_BINDING,
        NEW_FORCE_STORAGE_TYPE_BINDING,
        "evaluation rollback force-storage type binding",
    )
    expected = replace_once(
        expected,
        OLD_ROLLBACK_CLASS,
        NEW_ROLLBACK_CLASS,
        "evaluation rollback class force-storage binding",
    )
    expected = replace_once(
        expected,
        OLD_ROLLBACK_CONSTRUCTION,
        NEW_ROLLBACK_CONSTRUCTION,
        "evaluation rollback construction force-storage binding",
    )
    for path in IMPLEMENTATION_DELTA_PATHS:
        raw = (root / path).read_bytes()
        if sha(raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256:
            fail("successor adapter digest drift: %s" % path)
        if raw.decode() != expected:
            fail("adapter is not the exact PR 481 force-storage transform: %s" % path)
    canonical = (root / ADAPTER_RELATIVE_PATH).read_text()
    vendor = (root / VENDOR_ADAPTER_RELATIVE_PATH).read_text()
    if canonical != vendor:
        fail("canonical/vendor adapter byte identity drift")
    rollback = source_region(
        canonical,
        "class EvaluationForceStorageRollback final {\n",
        "\n\n}  // namespace",
        "evaluation rollback class",
    )
    construction = source_region(
        canonical,
        "    Evaluation candidate;\n",
        "    std::optional<ProviderForceScratch>",
        "evaluation rollback construction",
    )
    if rollback.count("class EvaluationForceStorageRollback final {") != 1:
        fail("evaluation rollback class count drift")
    if canonical.count(
        "using EvaluationForceStorage = decltype(Evaluation::forces);"
    ) != 1:
        fail("rollback force-storage alias count drift")
    if canonical.count(
        "static_assert(std::is_nothrow_swappable_v<EvaluationForceStorage>);"
    ) != 1:
        fail("rollback force-storage alias assertion count drift")
    if canonical.count("decltype(Evaluation{}.forces)") != 0:
        fail("legacy rollback force-storage type expression remains")
    if rollback.count("Evaluation *candidate") != 0:
        fail("nullable rollback candidate declaration remains")
    if rollback.count("Evaluation &candidate") != 0:
        fail("whole rollback candidate reference remains")
    if rollback.count("EvaluationForceStorage &candidate_forces") != 2:
        fail("rollback force-storage reference declaration count drift")
    if rollback.count("candidate_->") != 0 or rollback.count("candidate_.") != 0:
        fail("whole rollback candidate member access remains")
    if rollback.count("candidate_ = nullptr;") != 0:
        fail("rollback candidate null assignment remains")
    if rollback.count("candidate_(enabled ? candidate : nullptr)") != 0:
        fail("conditional rollback candidate initializer remains")
    if rollback.count("candidate_(candidate)") != 0:
        fail("whole rollback candidate initializer remains")
    if rollback.count("candidate_forces_(candidate_forces)") != 1:
        fail("rollback force-storage reference initializer count drift")
    if rollback.count("bool enabled") != 0:
        fail("redundant rollback enabled parameter remains")
    if rollback.count("output_(enabled ? output : nullptr)") != 0:
        fail("enabled-based rollback output initializer remains")
    if rollback.count(
        ": output_(output), candidate_forces_(candidate_forces)"
    ) != 1:
        fail("direct rollback force-storage initializer count drift")
    if rollback.count("output_ = nullptr;") != 1:
        fail("rollback output disarm count drift")
    if rollback.count("if (output_ != nullptr)") != 2:
        fail("rollback output active-guard count drift")
    if rollback.count("= delete;") != 2:
        fail("rollback copy-deletion count drift")
    if rollback.count("candidate_forces_.swap(output_->forces);") != 2:
        fail("rollback force-swap count drift")
    if construction.count("Evaluation candidate;") != 1:
        fail("rollback candidate local declaration count drift")
    if construction.count(
        "EvaluationForceStorageRollback evaluation_force_storage_rollback{"
    ) != 1:
        fail("rollback guard construction count drift")
    if "out_evaluation, &candidate," in construction:
        fail("rollback candidate address callsite remains")
    if construction.count("\n        candidate};") != 0:
        fail("whole rollback candidate callsite remains")
    if construction.count("\n        candidate.forces};") != 1:
        fail("rollback force-storage callsite count drift")
    activation = (
        "compute_forces && reuse_force_storage ? out_evaluation : nullptr"
    )
    if construction.count(activation) != 1:
        fail("rollback callsite activation predicate drift")
    if "out_evaluation != nullptr" in construction:
        fail("redundant rollback output metadata predicate remains")
    if canonical.count("evaluation_force_storage_rollback.commit();") != 1:
        fail("rollback success commit count drift")
    dispatch = source_region(
        canonical,
        "    const bg_status status = normalize_provider_status([&]() -> std::int32_t {\n",
        "    provider_error.detail[",
        "normalization-bound dispatch",
    )
    frozen_dispatch = source_region(
        frozen_source,
        "    const bg_status status = normalize_provider_status([&]() -> std::int32_t {\n",
        "    provider_error.detail[",
        "exact PR 481 normalization-bound dispatch",
    )
    if dispatch != frozen_dispatch:
        fail("dispatch-status normalization region changed from exact PR 481")
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
        fail("exact PR 481 native adapter test digest drift")
    if sha(test_raw) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("native adapter test changed from exact PR 481 bytes")


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    required = (
        "exact PR 481 predecessor",
        "`using EvaluationForceStorage = decltype(Evaluation::forces)`",
        "`EvaluationForceStorage &candidate_forces_`",
        "passes `candidate.forces`",
        "sole activation and commit sentinel",
        "declared before the guard and outlives the force-storage reference",
        "does not provide runtime lifetime enforcement",
        "does not claim that the entire guard is force-storage-only",
        "initial swap, failure rollback, and success-only commit behavior are preserved",
        "five inherited semantic routes remain",
        "canonical and vendored adapters",
        "fake-provider transactionality test still covers all five route classes",
        "No public header, Rust provider, provider ABI, linked symbol, checkpoint",
        "four blockers",
        "32 unresolved operational decisions",
        "no performance, allocation, object-size, stack-size, acceleration, scientific",
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
        "scope_is_only_native_evaluation_rollback_force_storage_binding",
        "evaluation_rollback_candidate_force_storage_type_alias_exact",
        "evaluation_rollback_candidate_force_storage_type_derived_from_evaluation_member",
        "evaluation_rollback_candidate_force_storage_nothrow_swap_assertion_exact",
        "evaluation_rollback_candidate_force_storage_is_non_null_reference",
        "evaluation_rollback_candidate_force_storage_reference_bound_once",
        "evaluation_rollback_whole_candidate_reference_parameter_removed",
        "evaluation_rollback_whole_candidate_reference_member_removed",
        "evaluation_rollback_candidate_force_storage_uses_direct_reference_access",
        "evaluation_rollback_callsite_passes_candidate_force_storage",
        "evaluation_rollback_candidate_declaration_precedes_guard",
        "evaluation_rollback_candidate_force_storage_lifetime_order_preserved",
        "evaluation_rollback_activation_predicate_localized_at_callsite",
        "evaluation_rollback_activation_uses_compute_forces_and_reuse_force_storage_only",
        "evaluation_rollback_output_pointer_is_sole_activation_and_commit_sentinel",
        "evaluation_rollback_initial_swap_and_destructor_restore_preserved",
        "evaluation_rollback_commit_disarms_via_output_only",
        "evaluation_rollback_copy_deletion_preserved",
        "five_semantic_route_rollback_activation_truth_table_preserved",
        "dispatch_status_normalization_binding_preserved",
    ):
        if implementation.get(key) is not True:
            fail("implementation evidence drift: %s" % key)
    false_claims = (
        "evaluation_rollback_force_storage_binding_performance_improvement_claimed",
        "evaluation_rollback_force_storage_reference_performance_improvement_claimed",
        "evaluation_rollback_force_storage_object_layout_equivalence_claimed",
        "evaluation_rollback_force_storage_runtime_lifetime_enforcement_claimed",
        "evaluation_rollback_guard_is_force_storage_only_claimed",
        "evaluation_rollback_candidate_reference_performance_improvement_claimed",
        "evaluation_rollback_enabled_parameter_removal_performance_improvement_claimed",
        "evaluation_rollback_object_layout_equivalence_claimed",
        "evaluation_rollback_reference_runtime_lifetime_enforcement_claimed",
        "reference_binding_performance_improvement_claimed",
        "nullability_elision_performance_improvement_claimed",
        "object_size_reduction_claimed",
        "stack_storage_reduction_claimed",
        "allocation_free_claimed",
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
        "trigger_path_count": 240,
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
