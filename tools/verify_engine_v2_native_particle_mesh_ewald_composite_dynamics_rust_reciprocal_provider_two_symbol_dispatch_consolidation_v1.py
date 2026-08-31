#!/usr/bin/env python3
"""Verify native PME Rust-adapter two-symbol dispatch consolidation."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import NoReturn

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_conditional_call_local_scratch_lifecycle_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_two_symbol_dispatch_consolidation"
)
WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-two-symbol-dispatch-consolidation"
)
PREDECESSOR_STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_conditional_call_local_scratch_lifecycle"
)
PREDECESSOR_WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-conditional-call-local-scratch-lifecycle"
)

PROFILE_RELATIVE_PATH = Path("config/%s_profile_v1.json" % STEM)
SOURCE_MANIFEST_RELATIVE_PATH = Path("config/%s_profile_v1_sources.json" % STEM)
WORKFLOW_RELATIVE_PATH = Path(".github/workflows/%s.yml" % WORKFLOW_STEM)
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
    ".github/workflows/%s.yml" % PREDECESSOR_WORKFLOW_STEM
)
PREDECESSOR_DOC_RELATIVE_PATH = Path("docs/%s_v1.md" % PREDECESSOR_STEM)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_%s_v1.py" % PREDECESSOR_STEM
)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_%s_v1.py" % PREDECESSOR_STEM
)

COMPOSITE_RELATIVE_PATH = Path(
    "native/src/composite/particle_mesh_ewald_composite.cpp"
)
VENDOR_COMPOSITE_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/composite/"
    "particle_mesh_ewald_composite.cpp"
)
RECIPROCAL_API_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/api.cpp"
)
VENDOR_RECIPROCAL_API_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/api.cpp"
)
PARTICLE_MESH_EWALD_RELATIVE_PATH = Path(
    "native/src/composite/particle_mesh_ewald.cpp"
)
VENDOR_PARTICLE_MESH_EWALD_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald.cpp"
)
ADAPTER_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
)
VENDOR_ADAPTER_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
    "rust_evaluator.cpp"
)
PROVIDER_HEADER_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/rust_provider.h"
)
VENDOR_PROVIDER_HEADER_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
    "rust_provider.h"
)
RUST_KERNEL_RELATIVE_PATH = Path(
    "rust/cpu-kernel/src/particle_mesh_reciprocal.rs"
)
COMPOSITE_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
)
ADAPTER_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_reciprocal_rust_adapter_transactionality.cpp"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_two_symbol_dispatch_consolidation_"
    "profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_two_symbol_dispatch_consolidation_"
    "sources/1.0.0"
)
PUBLIC_PROFILE_ID = (
    "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
)
PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)
FORCE_PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)

PREDECESSOR = {
    "pull_request": 474,
    "reviewed_head": "35ae0586bd292e74fb9fd5a0146ece9fff9a6253",
    "merge_commit": "1d0d8123ddb120da8301e9c9725ac4098ef0480d",
    "merge_tree": "e2f14187838c32df1511201f35683c35a305f2eb",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "3b317a61cb01081dc355d82fd6a39b069ffe9e714127b080280655f3468acc5e"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "4a4e06a0b36ae569de68629bd977fbe8f23fb39fd350f78368effb100226cf28"
    ),
    "source_manifest_entry_count": 375,
}

PUBLIC_SYMBOLS = (
    "bg_particle_mesh_ewald_composite_dynamics_abi_version",
    "bg_particle_mesh_ewald_composite_dynamics_abi_version_major",
    "bg_particle_mesh_ewald_composite_dynamics_abi_version_minor",
    "bg_particle_mesh_ewald_composite_dynamics_abi_version_string",
    "bg_particle_mesh_ewald_composite_dynamics_v1_profile_id",
    "bg_particle_mesh_ewald_composite_simulation_v1_create",
    "bg_particle_mesh_ewald_composite_simulation_v1_destroy",
    "bg_particle_mesh_ewald_composite_simulation_v1_get_particles",
    "bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step",
    "bg_context_integrate_particle_mesh_ewald_composite_v1",
    "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size",
    "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write",
    "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load",
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
        | {
            PREDECESSOR_WORKFLOW_RELATIVE_PATH,
            PREDECESSOR_UNIT_RELATIVE_PATH,
        },
        key=lambda path: path.as_posix(),
    )
)

EXPECTED_PREDECESSOR_WORKFLOW_SHA256 = (
    "69b48f4249d25cd8cd8ac03f15c4c920ddc03c830eefe5cec77cfb7163887e5d"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "97f55bda2a42caca68791d98b5069f19a6a9493a8f48476e11231ec3bd2efafd"
)
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = {
    ADAPTER_RELATIVE_PATH: "b46148a13f79b32b42975d6a249e8f661408a909347fb45b26cff7484c4b8e71",
    VENDOR_ADAPTER_RELATIVE_PATH: "b46148a13f79b32b42975d6a249e8f661408a909347fb45b26cff7484c4b8e71",
}
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = {
    ADAPTER_RELATIVE_PATH: "a1c27435d29fc0bc31c748ed4b34ac3419c2134a23421431347587cebb210ae5",
    VENDOR_ADAPTER_RELATIVE_PATH: "a1c27435d29fc0bc31c748ed4b34ac3419c2134a23421431347587cebb210ae5",
}
EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256 = (
    "4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03"
)

FROZEN_UNCHANGED_PATHS = tuple(
    Path(path)
    for path in (
        "CMakeLists.txt",
        "native/CMakeLists.txt",
        "include/betelgeuze/particle_mesh_reciprocal.h",
        "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h",
        "native/betelgeuze_engine.map",
        "native/betelgeuze_engine.exports",
        "native/tests/check_exports.cmake",
        "rust/betelgeuze-sys/src/lib.rs",
        "native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/cpu-kernel/src/particle_mesh_reciprocal.rs",
        "native/tests/particle_mesh_ewald_composite_dynamics.cpp",
        "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
        "native/src/particle_mesh_reciprocal/api.cpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/api.cpp",
        "native/src/composite/particle_mesh_ewald.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald.cpp",
        "native/src/composite/particle_mesh_ewald_composite.cpp",
        "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.hpp",
    )
)

AUTHORITY = {
    key: False
    for key in (
        "acceleration_claim_authorized",
        "d1_d2_execution_authorized",
        "fresh_holdout_execution_authorized",
        "hip_device_execution_authorized",
        "historical_molecular_ab_execution_authorized",
        "molecular_execution_authorized",
        "performance_claim_authorized",
        "product_authority",
        "public_benchmark_authorized",
        "qualification_rerun_authorized",
        "reservation_authorized",
        "root_supervisor_install_authorized",
        "scientific_claim_authorized",
        "stage0_admission_authorized",
        "test_double_production_authority",
    )
}
BLOCKERS = [
    "external_reservation_endpoint_not_configured",
    "external_reservation_provider_not_operational",
    "external_reservation_trust_anchor_not_configured",
    "historical_execution_operational_authority_false",
]

canonical_bytes = predecessor_verifier.canonical_bytes
sha = predecessor_verifier.sha
git = predecessor_verifier.git


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def source_region(source: str, start: str, end: str, label: str) -> str:
    if source.count(start) != 1:
        fail("%s start marker drift" % label)
    start_index = source.index(start)
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        fail("%s end marker drift" % label)
    return source[start_index:end_index]


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail("%s replacement anchor drift" % label)
    return source.replace(old, new, 1)


def expected_predecessor_workflow() -> str:
    frozen_raw = git(
        "show",
        "%s:%s"
        % (PREDECESSOR["merge_commit"], PREDECESSOR_WORKFLOW_RELATIVE_PATH),
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_WORKFLOW_SHA256:
        fail("exact frozen PR 474 workflow digest drift")
    expected = frozen_raw.decode()
    evidence_wiring = (
        (PREDECESSOR_WORKFLOW_RELATIVE_PATH, WORKFLOW_RELATIVE_PATH),
        (PREDECESSOR_PROFILE_RELATIVE_PATH, PROFILE_RELATIVE_PATH),
        (PREDECESSOR_MANIFEST_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH),
        (PREDECESSOR_DOC_RELATIVE_PATH, DOC_RELATIVE_PATH),
        (PREDECESSOR_VERIFIER_RELATIVE_PATH, VERIFIER_RELATIVE_PATH),
        (PREDECESSOR_UNIT_RELATIVE_PATH, UNIT_RELATIVE_PATH),
    )
    for predecessor_path, successor_path in evidence_wiring:
        anchor = '      - "%s"\n' % predecessor_path.as_posix()
        if expected.count(anchor) != 2:
            fail("exact frozen PR 474 workflow trigger anchor drift: %s" % predecessor_path)
        expected = expected.replace(
            anchor,
            anchor + '      - "%s"\n' % successor_path.as_posix(),
        )
    old_region = source_region(
        expected,
        "      - name: Materialize exact PR 473 target and reviewed head\n",
        "\n\n  native-linux:\n",
        "exact frozen PR 474 immutable-evidence predecessor block",
    )
    new_region = """      - name: Materialize exact PR 474 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 1d0d8123ddb120da8301e9c9725ac4098ef0480d^{tree})" = "e2f14187838c32df1511201f35683c35a305f2eb"
          git merge-base --is-ancestor 1d0d8123ddb120da8301e9c9725ac4098ef0480d HEAD
          git fetch --no-tags --depth=1 origin refs/pull/474/head
          test "$(git rev-parse FETCH_HEAD)" = "35ae0586bd292e74fb9fd5a0146ece9fff9a6253"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "e2f14187838c32df1511201f35683c35a305f2eb"
      - name: Verify exact frozen PR 474 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=1d0d8123ddb120da8301e9c9725ac4098ef0480d
          frozen_tree=e2f14187838c32df1511201f35683c35a305f2eb
          current_sha="$(git rev-parse HEAD)"
          restore() { git checkout --detach --quiet "$current_sha"; }
          trap restore EXIT
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_conditional_call_local_scratch_lifecycle_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_conditional_call_local_scratch_lifecycle_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_conditional_call_local_scratch_lifecycle_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_conditional_call_local_scratch_lifecycle_v1.py
          restore
          trap - EXIT"""
    return replace_once(
        expected,
        old_region,
        new_region,
        "exact frozen PR 474 immutable-evidence block",
    )


def expected_predecessor_unit() -> str:
    frozen_raw = git(
        "show",
        "%s:%s" % (PREDECESSOR["merge_commit"], PREDECESSOR_UNIT_RELATIVE_PATH),
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_UNIT_SHA256:
        fail("exact frozen PR 474 unit digest drift")
    expected = frozen_raw.decode()
    expected = replace_once(
        expected,
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport pytest\n",
        "exact frozen PR 474 unit pytest import",
    )
    skip = """ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_TWO_SYMBOL_DISPATCH_CONSOLIDATION_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_two_symbol_dispatch_consolidation_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_TWO_SYMBOL_DISPATCH_CONSOLIDATION_EVIDENCE_PRESENT,
    reason=(
        "conditional call-local scratch lifecycle evidence is verified from "
        "its exact frozen PR 474 object after two-symbol dispatch consolidation "
        "evidence is present"
    ),
)"""
    return replace_once(
        expected,
        "ROOT = Path(__file__).resolve().parents[2]",
        skip,
        "exact frozen PR 474 unit successor skip",
    )


def require_ordered_tokens(
    source: str, tokens: tuple[str, ...], label: str
) -> None:
    cursor = -1
    for token in tokens:
        next_cursor = source.find(token, cursor + 1)
        if next_cursor <= cursor:
            fail("%s ordering drift: %s" % (label, token))
        cursor = next_cursor


def reviewed_tree_if_present(record: dict) -> str | None:
    result = git("cat-file", "-e", "%s^{commit}" % record["reviewed_head"], check=False)
    if result.returncode != 0:
        return None
    return git("rev-parse", "%s^{tree}" % record["reviewed_head"]).stdout.strip().decode()


def require_predecessor() -> dict:
    merge = PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("PR 474 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 474 predecessor merge identity drift")
    if git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode() != PREDECESSOR["merge_tree"]:
        fail("PR 474 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 474 predecessor")
    profile_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix())
    ).stdout
    manifest_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(profile_raw) != PREDECESSOR["profile_sha256"]:
        fail("PR 474 predecessor profile digest drift")
    if sha(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        fail("PR 474 predecessor manifest digest drift")
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 474 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 375:
        fail("PR 474 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted({row.get("path") for row in rows}):
        fail("PR 474 predecessor manifest paths are not sorted and unique")
    if (ROOT / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out PR 474 predecessor profile drift")
    if (ROOT / PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out PR 474 predecessor manifest drift")
    reviewed_tree = reviewed_tree_if_present(PREDECESSOR)
    if reviewed_tree is not None and reviewed_tree != PREDECESSOR["merge_tree"]:
        fail("PR 474 reviewed-head tree drift")
    return manifest


def current_delta_paths() -> tuple[Path, ...]:
    merge = PREDECESSOR["merge_commit"]
    tracked = git("diff", "--name-only", merge, "--").stdout.decode().splitlines()
    untracked = git("ls-files", "--others", "--exclude-standard").stdout.decode().splitlines()
    return tuple(
        sorted({Path(path) for path in tracked + untracked}, key=lambda path: path.as_posix())
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
    if len(result) != 381:
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
            "two_symbol_dispatch_consolidation_current_sources_tests_evidence_"
            "pr474_target"
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }


def build_profile(manifest_raw: bytes) -> dict:
    manifest = json.loads(manifest_raw)
    return {
        "schema_id": SCHEMA_ID,
        "profile_id": "%s_development_v1" % STEM,
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "abi": {
            "public_profile_id": PUBLIC_PROFILE_ID,
            "public_symbol_count": 13,
            "public_symbols": list(PUBLIC_SYMBOLS),
            "public_abi_changed": False,
            "new_public_symbol_added": False,
            "private_provider_abi_changed": False,
            "private_provider_abi_version": 1,
            "new_private_hidden_symbol_added": False,
            "reused_private_hidden_symbol": PRIVATE_SYMBOL,
            "private_hidden_symbol_absent_from_public_surfaces": True,
            "private_hidden_symbol_present_in_linux_linked_image": True,
            "private_hidden_symbol_absent_from_linux_dynamic_exports": True,
            "status_abi_changed": False,
            "checkpoint_format_changed": False,
            "checkpoint_magic": "BGPME001",
            "checkpoint_header_size_bytes": 104,
        },
        "implementation": {
            "scope_is_only_native_provider_dispatch_branch_and_callsite_consolidation": True,
            "five_adapter_branches_collapsed_to_two_compute_forces_branches": True,
            "dispatch_uses_compute_forces_only": True,
            "dispatch_predicates_exclude_reuse_and_output_metadata": True,
            "force_private_symbol_adapter_callsite_count_exact": 1,
            "energy_private_symbol_adapter_callsite_count_exact": 1,
            "provider_force_source_guard_precedes_dispatch": True,
            "reusable_owner_null_guard_precedes_dispatch": True,
            "force_descriptor_pointer_preparation_precedes_dispatch": True,
            "provider_validation_finiteness_rollback_and_commit_preserved": True,
            "native_adapter_test_exact_predecessor_bytes": True,
            "five_semantic_route_classes_preserved": True,
            "conditional_call_local_provider_force_scratch_enabled": True,
            "call_local_provider_force_scratch_emplaced_only_for_stateless_calls": True,
            "call_local_provider_force_scratch_disengaged_for_reusable_calls": True,
            "active_provider_force_scratch_uses_emplaced_owner_for_stateless_calls": True,
            "active_provider_force_scratch_uses_external_owner_for_reusable_calls": True,
            "call_local_optional_lifetime_spans_dispatch_validation_and_commit": True,
            "reusable_unused_call_local_destroy_callbacks_elided": True,
            "reusable_calls_have_zero_destroy_callbacks_before_external_owner_scope_exit": True,
            "external_reusable_owner_matching_destroy_callbacks_exactly_once_each_at_scope_exit": True,
            "reusable_forceful_lifecycle_tested_on_success_typed_failure_and_nonfinite_success": True,
            "reusable_energy_lifecycle_tested_on_success_and_typed_failure": True,
            "provider_force_source_success_lifecycle_tested": True,
            "stateless_call_local_destroy_lifecycle_preserved": True,
            "cxx17_optional_support_inherited": True,
            "stateless_energy_all_three_scratch_route_enabled": True,
            "stateless_energy_public_transactional_route_removed_from_adapter": True,
            "existing_all_three_scratch_energy_entry_reused": True,
            "new_rust_or_header_entry_added": False,
            "provider_force_source_all_three_scratch_route_preserved": True,
            "reusable_forceful_all_three_scratch_route_preserved": True,
            "reusable_force_free_all_three_scratch_energy_route_preserved": True,
            "stateless_forceful_all_three_scratch_route_preserved": True,
            "five_adapter_branches_remain_distinct": False,
            "adapter_uses_two_unique_provider_symbols": True,
            "call_local_provider_force_scratch_selected_for_stateless_calls": True,
            "stateless_energy_call_local_reciprocal_workspace_initially_empty": True,
            "stateless_energy_call_local_neutrality_sort_scratch_initially_empty": True,
            "stateless_energy_call_local_particle_assignment_scratch_initially_empty": True,
            "stateless_energy_three_descriptors_initially_exact_all_zero": True,
            "stateless_energy_three_descriptors_pairwise_distinct": True,
            "stateless_energy_call_local_force_xyz_remain_empty": True,
            "stateless_energy_three_descriptors_destroyed_before_return": True,
            "stateless_energy_matching_destroy_callbacks_exactly_once_each": True,
            "stateless_energy_lifecycle_tested_on_success_typed_failure_and_nonfinite_success": True,
            "stateless_scratch_lifetime_is_single_call": True,
            "persistent_scratch_reuse_claimed": False,
            "cross_call_scratch_reuse_claimed": False,
            "force_output_allocation_site_not_consumed_by_stateless_energy_route": True,
            "three_descriptors_and_full_backing_capacities_preflight_before_lease": True,
            "three_scratch_allocations_pairwise_disjointness_required": True,
            "three_scratch_empty_and_ready_states_accepted": True,
            "three_scratch_leased_and_malformed_states_rejected": True,
            "cold_allocation_order_neutrality_assignments_workspace": True,
            "cold_neutrality_failure_retains_three_empty_descriptors": True,
            "cold_assignment_failure_may_retain_ready_neutrality_scratch": True,
            "cold_workspace_failure_may_retain_ready_neutrality_and_assignment_scratch": True,
            "workspace_payload_is_derived_and_nontransactional": True,
            "neutrality_sort_payload_is_derived_and_nontransactional": True,
            "particle_assignment_payload_is_derived_and_nontransactional": True,
            "external_evaluation_is_success_only": True,
            "reusable_evaluation_force_storage_rollback_guard_preserved": True,
            "stateless_failure_preserves_evaluation_energy_bits": True,
            "stateless_failure_preserves_evaluation_force_address_capacity_size_and_bits": True,
            "provider_success_energy_finiteness_preflight_precedes_external_commit": True,
            "stateless_energy_late_typed_failure_exact_evaluation_rollback_tested": True,
            "stateless_nonfinite_energy_success_exact_evaluation_rollback_tested": True,
            "raw_public_transactional_peer_frozen": True,
            "production_composite_caller_exact_predecessor_bytes": True,
            "production_stateless_energy_caller_reaches_changed_adapter_route": True,
            "production_stateless_energy_caller_tests_enabled": True,
            "cpp_lane_provider_independence_preserved": True,
            "fake_provider_is_dispatch_and_commit_separation_test_double": True,
            "fake_provider_production_authority": False,
            "fake_provider_scientific_authority": False,
            "fake_provider_executes_real_rust_allocator": False,
            "fake_provider_executes_real_rust_panic_boundary": False,
            "real_rust_provider_sanitizer_execution_claimed": False,
            "workspace_payload_transactionality_claimed": False,
            "neutrality_sort_payload_transactionality_claimed": False,
            "particle_assignment_payload_transactionality_claimed": False,
            "call_local_scratch_transactionality_claimed": False,
            "error_output_transactionality_claimed": False,
            "concurrent_workspace_use_claimed": False,
            "concurrent_neutrality_sort_scratch_use_claimed": False,
            "concurrent_particle_assignment_scratch_use_claimed": False,
            "allocation_free_claimed": False,
            "allocation_count_claimed": False,
            "allocation_behavior_changed_claimed": False,
            "provider_allocation_free_claimed": False,
            "steady_state_allocation_free_claimed": False,
            "production_allocation_elision_claimed": False,
            "heap_allocation_elision_claimed": False,
            "provider_allocation_elision_claimed": False,
            "stack_storage_reduction_claimed": False,
            "scratch_storage_footprint_reduction_claimed": False,
            "object_size_reduction_claimed": False,
            "destroy_callback_performance_improvement_claimed": False,
            "branch_reduction_performance_improvement_claimed": False,
            "callsite_reduction_performance_improvement_claimed": False,
            "performance_claimed": False,
            "peak_memory_reduction_claimed": False,
            "acceleration_claimed": False,
            "scientific_claimed": False,
            "scientific_equivalence_claimed": False,
            "cross_lane_bit_parity_claimed": False,
            "molecular_execution_claimed": False,
            "hip_execution_claimed": False,
            "product_claimed": False,
            "operational_readiness_claimed": False,
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
            "source_manifest_entry_count": len(manifest["files"]),
        },
        "validation": {
            "exact_delta_path_count": 10,
            "implementation_delta_path_count": 2,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 381,
            "pull_request_trigger_path_count_exact": 198,
            "push_trigger_path_count_exact": 198,
            "pull_request_and_push_trigger_sets_symmetric": True,
            "canonical_vendor_composite_exact_predecessor_bytes": True,
            "canonical_vendor_adapter_byte_identical": True,
            "canonical_vendor_provider_header_byte_identical": True,
            "predecessor_adapter_exact_two_symbol_dispatch_transform": True,
            "conditional_optional_selection_exact_predecessor_bytes": True,
            "native_adapter_test_exact_predecessor_bytes": True,
            "native_adapter_test_five_semantic_classes_frozen": True,
            "reusable_zero_destroy_callback_assertion_count_exact": 6,
            "external_owner_scope_destroy_assertion_count_exact": 3,
            "stateless_lifecycle_assertion_count_exact": 6,
            "stateless_lifecycle_test_regions_exact_predecessor_bytes": True,
            "provider_validation_and_commit_exact_predecessor_bytes": True,
            "provider_force_scratch_destructor_exact_predecessor_bytes": True,
            "two_branch_two_symbol_adapter_dispatch_exact": True,
            "force_private_symbol_adapter_callsite_count_exact": 1,
            "energy_private_symbol_adapter_callsite_count_exact": 1,
            "dispatch_predicates_compute_forces_only": True,
            "provider_force_source_and_reusable_null_guards_precede_dispatch": True,
            "force_descriptor_pointer_preparation_precedes_dispatch": True,
            "stateless_energy_three_call_local_empty_descriptors_exact": True,
            "stateless_energy_destroy_callbacks_exact_once_before_return": True,
            "stateless_energy_success_error_nonfinite_lifecycle_tests_exact": True,
            "stateless_energy_exact_evaluation_rollback_tests_exact": True,
            "forceful_and_reusable_predecessor_coverage_preserved": True,
            "raw_public_transactional_peer_exact_predecessor_bytes": True,
            "public_transactional_provider_symbol_zero_adapter_call_sites": True,
            "direct_private_provider_symbol_zero_adapter_call_sites": True,
            "reusable_evaluation_force_storage_rollback_guard_exact_predecessor_bytes": True,
            "rust_provider_and_private_header_exact_predecessor_bytes": True,
            "production_composite_and_composite_test_exact_predecessor_bytes": True,
            "public_symbol_surfaces_exact": True,
            "private_hidden_symbol_absent_from_public_surfaces": True,
            "linux_private_hidden_symbol_local_and_not_dynamic": True,
            "checkpoint_and_static_fingerprint_exact_predecessor_bytes": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
            "release_workflow_builds_real_rust_and_adapter_tests": True,
            "release_and_sanitizer_cover_stateless_energy_reciprocal_pme_and_composite_callers": True,
            "sanitizer_claim_limited_to_native_and_fake_provider_boundaries": True,
            "macos_workflow_engine_export_only": True,
            "reviewed_head_optional_locally_and_exact_when_present": True,
        },
        "authority": dict(AUTHORITY),
        "operational_boundary": {
            "blockers": list(BLOCKERS),
            "unresolved_operational_decisions": 32,
        },
    }


def workflow_trigger_paths(workflow: str, event: str, end: str) -> tuple[str, ...]:
    region = source_region(
        workflow,
        "  %s:\n" % event,
        "  %s:\n" % end,
        "%s trigger" % event,
    )
    return tuple(re.findall(r'^      - "([^"]+)"$', region, re.MULTILINE))


def require_workflow_contract(root: Path = ROOT) -> None:
    successor = (root / WORKFLOW_RELATIVE_PATH).read_text()
    predecessor = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    if predecessor != expected_predecessor_workflow():
        fail("PR 474 predecessor workflow is not the exact frozen-object transformation")
    for workflow, expected_name in (
        (successor, WORKFLOW_STEM),
        (predecessor, PREDECESSOR_WORKFLOW_STEM),
    ):
        if workflow.count("name: %s\n" % expected_name) != 1:
            fail("workflow name drift: %s" % expected_name)
        pull_paths = workflow_trigger_paths(workflow, "pull_request", "push")
        push_paths = workflow_trigger_paths(workflow, "push", "workflow_dispatch")
        if len(pull_paths) != 198 or len(set(pull_paths)) != 198 or push_paths != pull_paths:
            fail("workflow 198-path symmetric trigger contract drift: %s" % expected_name)
        if set(path.as_posix() for path in EVIDENCE_PATHS) - set(pull_paths):
            fail("workflow successor evidence trigger drift: %s" % expected_name)
        if set(path.as_posix() for path in PREDECESSOR_EVIDENCE_PATHS) - set(pull_paths):
            fail("workflow predecessor evidence trigger drift: %s" % expected_name)
    jobs = re.findall(
        r"(?m)^  (immutable-evidence|native-linux|rust-boundaries|macos-export-boundary):$",
        successor,
    )
    if jobs != [
        "immutable-evidence",
        "native-linux",
        "rust-boundaries",
        "macos-export-boundary",
    ]:
        fail("successor workflow exact job set drift")
    if successor.count("uses: %s" % PINNED_CHECKOUT_ACTION) != 4:
        fail("successor workflow checkout pin count drift")
    for forbidden in (
        "--refresh",
        "pull_request_target:",
        "issue_comment:",
        "workflow_run:",
        "self-hosted",
        "sudo ",
        "secrets.",
        "id-token: write",
        "contents: write",
    ):
        if forbidden in successor:
            fail("forbidden workflow capability: %s" % forbidden)
    for token in (
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        PREDECESSOR["reviewed_head"],
        "python3 -m tools.verify_%s_v1" % STEM,
        "python3 -m pytest -q %s" % UNIT_RELATIVE_PATH.as_posix(),
        "betelgeuze_engine_particle_mesh_reciprocal_rust_adapter_transactionality",
        "cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel particle_mesh_reciprocal",
        "cargo fmt --manifest-path rust/Cargo.toml --all -- --check",
        "cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel --all-targets -- -D warnings",
        "-type f -name 'libbetelgeuze_engine.so.*' -print -quit",
        "nm --defined-only \"$engine_library\"",
        "nm -D --defined-only \"$engine_library\"",
        "grep -Fx '%s'" % PRIVATE_SYMBOL,
    ):
        if token not in successor:
            fail("successor workflow contract drift: %s" % token)
    release_region = source_region(
        successor,
        "          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-two-symbol-dispatch-consolidation-release ",
        "          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-two-symbol-dispatch-consolidation-sanitize ",
        "successor Release native validation",
    )
    sanitizer_region = source_region(
        successor,
        "          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-two-symbol-dispatch-consolidation-sanitize ",
        "\n\n  rust-boundaries:",
        "successor sanitizer native validation",
    )
    native_targets = (
        "--target betelgeuze_engine_particle_mesh_reciprocal "
        "betelgeuze_engine_particle_mesh_ewald "
        "betelgeuze_engine_particle_mesh_ewald_composite "
        "betelgeuze_engine_particle_mesh_reciprocal_rust_adapter_transactionality "
        "betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2"
    )
    release_tests = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald|"
        "particle_mesh_ewald_composite|"
        "particle_mesh_reciprocal_rust_adapter_transactionality|"
        "particle_mesh_ewald_composite_dynamics|export_allowlist)$'"
    )
    sanitizer_tests = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald|"
        "particle_mesh_ewald_composite|"
        "particle_mesh_reciprocal_rust_adapter_transactionality|"
        "particle_mesh_ewald_composite_dynamics)$'"
    )
    if release_region.count(native_targets) != 1 or release_region.count(release_tests) != 1:
        fail("successor Release caller build/test target set drift")
    if (
        sanitizer_region.count(native_targets) != 1
        or sanitizer_region.count(sanitizer_tests) != 1
    ):
        fail("successor sanitizer caller build/test target set drift")
    if (
        "--target betelgeuze_engine --parallel 2" not in successor
        or "'^betelgeuze_engine_export_allowlist$'" not in successor
    ):
        fail("macOS workflow must remain engine/export-only")
    for token in (
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        PREDECESSOR["reviewed_head"],
        "git checkout --detach --quiet \"$frozen\"",
        "python3 -m tools.verify_%s_v1" % PREDECESSOR_STEM,
        "python3 -m pytest -q %s" % PREDECESSOR_UNIT_RELATIVE_PATH.as_posix(),
        "trap restore EXIT",
    ):
        if token not in predecessor:
            fail("PR 474 predecessor workflow freeze drift: %s" % token)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    unit = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if unit != expected_predecessor_unit():
        fail("PR 474 predecessor unit is not the exact frozen-object transformation")
    constants = {
        node.value
        for node in ast.walk(ast.parse(unit))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for token in (
        "import pytest",
        "pytestmark = pytest.mark.skipif(",
    ):
        if unit.count(token) != 1:
            fail("PR 474 predecessor unit freeze drift: %s" % token)
    if PROFILE_RELATIVE_PATH.as_posix() not in constants:
        fail("PR 474 predecessor unit successor-profile path drift")
    if not any("exact frozen PR 474 object" in value for value in constants):
        fail("PR 474 predecessor unit frozen-object reason drift")
    if "is_file()" not in unit:
        fail("PR 474 predecessor unit skip is not successor-profile scoped")


def require_exact_source_hashes(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    for relative in IMPLEMENTATION_DELTA_PATHS:
        predecessor_raw = git("show", "%s:%s" % (merge, relative.as_posix())).stdout
        successor_raw = (root / relative).read_bytes()
        if sha(predecessor_raw) != EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256[relative]:
            fail("frozen PR 474 implementation digest drift: %s" % relative)
        if sha(successor_raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256[relative]:
            fail("successor implementation digest drift: %s" % relative)
        if predecessor_raw == successor_raw:
            fail("declared implementation path did not change: %s" % relative)
    frozen_adapter = git(
        "show", "%s:%s" % (merge, ADAPTER_RELATIVE_PATH.as_posix())
    ).stdout.decode()
    expected_adapter = replace_once(
        frozen_adapter,
        """    if (out_provider_force_source_result != nullptr) {
        raw_status = bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch->reciprocal_workspace,
            &active_provider_force_scratch->neutrality_sort_scratch,
            &active_provider_force_scratch->particle_assignment_scratch,
            &provider_energy, force_pointer, &provider_error);
    } else if (reuse_force_storage && compute_forces) {
        raw_status = bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch->reciprocal_workspace,
            &active_provider_force_scratch->neutrality_sort_scratch,
            &active_provider_force_scratch->particle_assignment_scratch,
            &provider_energy, force_pointer, &provider_error);
    } else if (reuse_force_storage) {
        raw_status =
            bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch->reciprocal_workspace,
                &active_provider_force_scratch->neutrality_sort_scratch,
                &active_provider_force_scratch->particle_assignment_scratch,
                &provider_energy, &provider_error);
    } else if (compute_forces) {
        raw_status = bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch->reciprocal_workspace,
            &active_provider_force_scratch->neutrality_sort_scratch,
            &active_provider_force_scratch->particle_assignment_scratch,
            &provider_energy, force_pointer, &provider_error);
    } else {
        raw_status =
            bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch->reciprocal_workspace,
                &active_provider_force_scratch->neutrality_sort_scratch,
                &active_provider_force_scratch->particle_assignment_scratch,
                &provider_energy, &provider_error);
    }
""",
        """    if (compute_forces) {
        raw_status = bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
            &provider_system, &provider_model,
            &active_provider_force_scratch->reciprocal_workspace,
            &active_provider_force_scratch->neutrality_sort_scratch,
            &active_provider_force_scratch->particle_assignment_scratch,
            &provider_energy, force_pointer, &provider_error);
    } else {
        raw_status =
            bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1(
                &provider_system, &provider_model,
                &active_provider_force_scratch->reciprocal_workspace,
                &active_provider_force_scratch->neutrality_sort_scratch,
                &active_provider_force_scratch->particle_assignment_scratch,
                &provider_energy, &provider_error);
    }
""",
        "five-arm to two-symbol compute-forces dispatch",
    )
    for relative in (ADAPTER_RELATIVE_PATH, VENDOR_ADAPTER_RELATIVE_PATH):
        if (root / relative).read_text() != expected_adapter:
            fail("adapter is not the exact PR 474 two-symbol dispatch transform: %s" % relative)
    frozen_adapter_test = git(
        "show", "%s:%s" % (merge, ADAPTER_TEST_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(frozen_adapter_test) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("frozen PR 474 native adapter-test digest drift")
    if (root / ADAPTER_TEST_RELATIVE_PATH).read_bytes() != frozen_adapter_test:
        fail("native adapter test changed from exact PR 474 bytes")
    for canonical, vendor, label in (
        (RECIPROCAL_API_RELATIVE_PATH, VENDOR_RECIPROCAL_API_RELATIVE_PATH, "reciprocal API"),
        (PARTICLE_MESH_EWALD_RELATIVE_PATH, VENDOR_PARTICLE_MESH_EWALD_RELATIVE_PATH, "particle-mesh Ewald parent"),
        (COMPOSITE_RELATIVE_PATH, VENDOR_COMPOSITE_RELATIVE_PATH, "composite"),
        (ADAPTER_RELATIVE_PATH, VENDOR_ADAPTER_RELATIVE_PATH, "adapter"),
        (PROVIDER_HEADER_RELATIVE_PATH, VENDOR_PROVIDER_HEADER_RELATIVE_PATH, "provider header"),
    ):
        if (root / canonical).read_bytes() != (root / vendor).read_bytes():
            fail("canonical/vendor %s mirror drift" % label)
    for relative in FROZEN_UNCHANGED_PATHS:
        current = (root / relative).read_bytes()
        frozen = git("show", "%s:%s" % (merge, relative.as_posix())).stdout
        if current != frozen:
            fail("unchanged ABI/checkpoint/build source drift: %s" % relative)


def require_frozen_rust_contract(root: Path = ROOT) -> None:
    source = (root / RUST_KERNEL_RELATIVE_PATH).read_text()
    enum_region = source_region(
        source,
        "enum ProviderForceMode {",
        "\nfn reserved_is_zero",
        "provider force mode",
    )
    for token in (
        "Transactional(u8)",
        "EnergyWithWorkspace {",
        "EnergyWithWorkspaceAndNeutralitySortScratch {",
        "EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch {",
        "workspace: *mut ParticleMeshReciprocalWorkspaceV1",
        "neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1",
        "particle_assignment_scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1",
        "Direct {",
    ):
        if token not in enum_region:
            fail("provider mode drift: %s" % token)
    helper = source_region(
        source,
        "fn evaluate_energy_with_all_reusable_storage",
        "\nfn evaluate_with_direct_force_output_and_reusable_storage",
        "all-three-scratch energy helper",
    )
    for token in (
        "ForceStorageMode::Disabled",
        "Some(workspace)",
        "Some(neutrality_sort_scratch)",
        "Some(particle_assignment_scratch)",
        ".reciprocal_space_kcal_per_mol",
    ):
        if token not in helper:
            fail("all-three-scratch energy helper drift: %s" % token)
    for forbidden in ("ForceStorageMode::Direct", "ForceStorageMode::Transactional"):
        if forbidden in helper:
            fail("all-three-scratch energy helper gained force storage")
    provider = source_region(
        source,
        "unsafe fn evaluate_provider_impl(",
        "\nunsafe fn validate_error_output",
        "provider implementation",
    )
    require_ordered_tokens(
        provider,
        (
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch {",
            "Some(particle_assignment_scratch)",
            "let workspace_preflight =",
            "let neutrality_sort_scratch_preflight =",
            "let particle_assignment_scratch_preflight =",
            "require_disjoint_outputs(&mutable_ranges)?;",
            "for input_range in input_ranges.into_iter().flatten()",
            "alias_safety.set(true);",
            "ReciprocalWorkspaceLease::acquire(preflight)",
            "NeutralitySortScratchLease::acquire(preflight)",
            "ParticleAssignmentScratchLease::acquire(preflight)",
            "provider_input(&system, model)",
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch {",
            "evaluate_energy_with_all_reusable_storage(",
            "workspace.workspace_mut()",
            "neutrality_sort_scratch.scratch_mut()",
            "particle_assignment_scratch.scratch_mut()",
            "(energy, Vec::new(), None)",
        ),
        "all-three-scratch provider preflight and evaluation",
    )
    if (
        provider.count(
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch {"
        )
        < 3
    ):
        fail("all-three-scratch provider mode coverage drift")
    abi = source_region(
        source,
        'pub unsafe extern "C" fn %s(' % PRIVATE_SYMBOL,
        "\n/// Evaluate reciprocal-only order-4 particle-mesh electrostatics directly into",
        "all-three-scratch hidden ABI",
    )
    for token in (
        "system: *const ParticleMeshReciprocalSystemV1",
        "model: *const ParticleMeshReciprocalModelV1",
        "workspace: *mut ParticleMeshReciprocalWorkspaceV1",
        "neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1",
        "particle_assignment_scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1",
        "out_energy: *mut ParticleMeshReciprocalEnergyV1",
        "out_error: *mut ParticleMeshReciprocalErrorV1",
        ") -> i32",
        "catch_unwind(AssertUnwindSafe",
        "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratchAndParticleAssignmentScratch {",
        "ptr::null_mut()",
        "commit_candidate(candidate, out_energy)",
        "alias_safety.get()",
    ):
        if token not in abi:
            fail("all-three-scratch hidden ABI drift: %s" % token)
    for forbidden in ("out_forces", "ForceOutputV1"):
        if forbidden in abi:
            fail("all-three-scratch hidden ABI accepted force output: %s" % forbidden)
    for old_abi_symbol in (
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1",
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_v1",
    ):
        if source.count('pub unsafe extern "C" fn %s(' % old_abi_symbol) != 1:
            fail("predecessor hidden energy ABI was not preserved: %s" % old_abi_symbol)
    for test_name in (
        "energy_all_scratch_cold_warm_oom_and_interop_are_frozen",
        "energy_all_scratch_growth_late_error_and_panic_restore_three_leases",
        "energy_all_scratch_malformed_leased_and_full_capacity_aliases_fail_closed",
    ):
        if source.count("fn %s(" % test_name) != 1:
            fail("focused Rust test drift: %s" % test_name)
    for token in (
        "AllocationSite::NeutralitySort",
        "AllocationSite::ParticleAssignments",
        "AllocationSite::ReciprocalWorkspace",
        "AllocationSite::ForceOutput",
        "ReusableWorkspacePanicGuard::inject()",
        "PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED",
        "PARTICLE_MESH_RECIPROCAL_NEUTRALITY_SORT_SCRATCH_LEASED",
        "PARTICLE_MESH_RECIPROCAL_PARTICLE_ASSIGNMENT_SCRATCH_LEASED",
        "shared_descriptor",
        "forged_assignment",
        "capacity_tail_energy",
        "evaluate_energy_with_owner_workspace_and_neutrality_sort_scratch(",
        "evaluate_with_all_owner_reusable_storage(",
    ):
        if token not in source:
            fail("focused Rust ownership/transactionality anchor drift: %s" % token)


def require_rust_contract(root: Path = ROOT) -> None:
    require_frozen_rust_contract(root)
    source = (root / RUST_KERNEL_RELATIVE_PATH).read_text()
    abi = source_region(
        source,
        'pub unsafe extern "C" fn %s(' % FORCE_PRIVATE_SYMBOL,
        "\n/// Release a canonical owner-private reciprocal workspace allocation.",
        "existing all-three-scratch force ABI",
    )
    for token in (
        "system: *const ParticleMeshReciprocalSystemV1",
        "model: *const ParticleMeshReciprocalModelV1",
        "workspace: *mut ParticleMeshReciprocalWorkspaceV1",
        "neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1",
        "particle_assignment_scratch: *mut ParticleMeshReciprocalParticleAssignmentScratchV1",
        "out_energy: *mut ParticleMeshReciprocalEnergyV1",
        "out_forces: *mut ParticleMeshReciprocalForceOutputV1",
        "out_error: *mut ParticleMeshReciprocalErrorV1",
        "ProviderForceMode::Direct {",
        "workspace: Some(workspace)",
        "neutrality_sort_scratch: Some(neutrality_sort_scratch)",
        "particle_assignment_scratch: Some(particle_assignment_scratch)",
        "commit_candidate(candidate, out_energy)",
    ):
        if token not in abi:
            fail("existing all-three-scratch force ABI drift: %s" % token)
    for symbol in (
        PRIVATE_SYMBOL,
        FORCE_PRIVATE_SYMBOL,
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1",
    ):
        if source.count('pub unsafe extern "C" fn %s(' % symbol) != 1:
            fail("inherited private Rust ABI drift: %s" % symbol)


def require_native_contract(root: Path = ROOT) -> None:
    adapter = (root / ADAPTER_RELATIVE_PATH).read_text()
    body = source_region(
        adapter,
        "static bg_status evaluate_impl(",
        "\nbg_status evaluate(",
        "native Rust adapter",
    )
    all_scratch_force = FORCE_PRIVATE_SYMBOL + "("
    workspace_force = (
        "bg_rust_particle_mesh_reciprocal_"
        "evaluate_reusing_force_output_with_workspace_v1("
    )
    energy_all_scratch = PRIVATE_SYMBOL + "("
    direct = "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1("
    transactional = "bg_rust_particle_mesh_reciprocal_evaluate_v1("
    if body.count(energy_all_scratch) != 1:
        fail("adapter all-three-scratch energy route count drift")
    if body.count(transactional) != 0:
        fail("adapter retained public transactional energy route")
    if body.count(all_scratch_force) != 1:
        fail("adapter all-three-scratch force route count drift")
    if body.count(direct) != 0:
        fail("adapter retained stateless direct-force route")
    if body.count(workspace_force) != 0:
        fail("adapter retained workspace-only reusable force route")
    dispatch = source_region(
        body,
        "    std::int32_t raw_status;",
        "    const bg_status status = normalize_provider_status(raw_status);",
        "two-symbol compute-forces dispatch",
    )
    require_ordered_tokens(
        dispatch,
        (
            "if (compute_forces) {",
            all_scratch_force,
            "} else {",
            energy_all_scratch,
        ),
        "adapter exact two-branch two-symbol dispatch",
    )
    if dispatch.count("if (compute_forces) {") != 1 or dispatch.count("} else {") != 1:
        fail("adapter dispatch branch count drift")
    if dispatch.count(all_scratch_force) != 1 or dispatch.count(energy_all_scratch) != 1:
        fail("adapter dispatch call-expression count drift")
    for forbidden in (
        "reuse_force_storage",
        "out_provider_force_source_result",
        "out_evaluation",
        "else if",
    ):
        if forbidden in dispatch:
            fail("adapter dispatch predicate widened beyond compute_forces: %s" % forbidden)
    for token in (
        "&active_provider_force_scratch->reciprocal_workspace",
        "&active_provider_force_scratch->neutrality_sort_scratch",
        "&active_provider_force_scratch->particle_assignment_scratch",
    ):
        if dispatch.count(token) != 2:
            fail("two-symbol dispatch descriptor routing drift: %s" % token)
    if dispatch.count("&provider_energy, force_pointer, &provider_error") != 1:
        fail("two-symbol force dispatch output routing drift")
    if dispatch.count("&provider_energy, &provider_error") != 1:
        fail("two-symbol energy dispatch output routing drift")
    require_ordered_tokens(
        body,
        (
            "if (out_provider_force_source_result != nullptr &&",
            "if (reuse_force_storage && provider_force_scratch == nullptr)",
            "bg_rust_particle_mesh_reciprocal_force_output_v1 provider_forces{};",
            "std::optional<ProviderForceScratch> local_provider_force_scratch;",
            "provider_forces.x = active_provider_force_scratch->x.data();",
            "force_pointer = &provider_forces;",
            "std::int32_t raw_status;",
            "if (compute_forces) {",
            all_scratch_force,
            "} else {",
            energy_all_scratch,
            "const bg_status status = normalize_provider_status(raw_status);",
            "if (status != BG_STATUS_OK) {",
            "if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol)) {",
            "for (std::size_t atom = 0U; atom < atom_count; ++atom) {",
            "if (!std::isfinite(active_provider_force_scratch->x[atom])",
            "candidate.forces.resize(atom_count);",
            "candidate.forces[atom] = {",
            "evaluation_force_storage_rollback.commit();",
            "*out_evaluation = std::move(candidate);",
        ),
        "adapter guards, force preparation, two-symbol dispatch, validation, and commit",
    )
    if body.count("if (reuse_force_storage && provider_force_scratch == nullptr)") != 1:
        fail("adapter reusable owner null guard drift")

    local_scratch_setup = source_region(
        body,
        "std::optional<ProviderForceScratch> local_provider_force_scratch;",
        "\n    if (compute_forces) {",
        "conditional call-local provider-force scratch selection",
    )
    for token in (
        "std::optional<ProviderForceScratch> local_provider_force_scratch;",
        "ProviderForceScratch *active_provider_force_scratch = provider_force_scratch;",
        "if (!reuse_force_storage) {",
        "&local_provider_force_scratch.emplace();",
    ):
        if token not in local_scratch_setup:
            fail("conditional call-local scratch selection drift: %s" % token)
    if adapter.count("#include <optional>") != 1:
        fail("adapter optional include count drift")
    if body.count("std::optional<ProviderForceScratch>") != 1:
        fail("adapter optional owner count drift")
    if body.count("local_provider_force_scratch.emplace()") != 1:
        fail("adapter optional emplacement count drift")
    for forbidden in (
        "ProviderForceScratch local_provider_force_scratch;",
        "std::unique_ptr<ProviderForceScratch>",
        "std::make_unique<ProviderForceScratch>",
        "new ProviderForceScratch",
        "local_provider_force_scratch.reset()",
    ):
        if forbidden in adapter:
            fail("forbidden conditional scratch ownership form: %s" % forbidden)
    require_ordered_tokens(
        body,
        (
            "if (reuse_force_storage && provider_force_scratch == nullptr)",
            "std::optional<ProviderForceScratch> local_provider_force_scratch;",
            "if (!reuse_force_storage) {",
            "&local_provider_force_scratch.emplace();",
            "if (compute_forces) {",
            "std::int32_t raw_status;",
            "const bg_status status = normalize_provider_status(raw_status);",
            "if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol)) {",
            "evaluation_force_storage_rollback.commit();",
            "return BG_STATUS_OK;",
        ),
        "conditional owner lifetime through dispatch validation and commit",
    )
    force_branch = source_region(
        dispatch,
        "if (compute_forces) {",
        "} else {",
        "adapter consolidated force all-scratch branch",
    )
    for token in (
        all_scratch_force,
        "&provider_energy, force_pointer, &provider_error",
    ):
        if token not in force_branch:
            fail("consolidated force branch routing drift: %s" % token)
    energy_branch = source_region(
        dispatch,
        "} else {",
        "\n    }\n",
        "adapter consolidated force-free all-scratch branch",
    )
    for forbidden in ("force_pointer", ".x.resize", ".y.resize", ".z.resize"):
        if forbidden in energy_branch:
            fail("force-free all-three-scratch branch touched force output: %s" % forbidden)
    if "&active_provider_force_scratch->particle_assignment_scratch" not in energy_branch:
        fail("force-free all-three-scratch branch omitted assignment owner")
    for token in (
        energy_all_scratch,
        "&active_provider_force_scratch->reciprocal_workspace",
        "&active_provider_force_scratch->neutrality_sort_scratch",
        "&active_provider_force_scratch->particle_assignment_scratch",
        "&provider_energy, &provider_error",
    ):
        if token not in energy_branch:
            fail("consolidated energy descriptor routing drift: %s" % token)
    for forbidden in (
        "force_pointer",
        ".x.resize",
        ".y.resize",
        ".z.resize",
        transactional,
    ):
        if forbidden in energy_branch:
            fail("consolidated energy branch touched force/public route: %s" % forbidden)
    for old_energy_symbol in (
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1(",
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_v1(",
    ):
        if old_energy_symbol in body:
            fail("adapter reusable-energy branch retained predecessor call: %s" % old_energy_symbol)
    rollback = source_region(
        adapter,
        "class EvaluationForceStorageRollback final {",
        "\n\n}  // namespace",
        "Evaluation force-storage rollback guard",
    )
    for token in (
        "candidate_->forces.swap(output_->forces);",
        "~EvaluationForceStorageRollback() noexcept",
        "void commit() noexcept",
        "output_ = nullptr;",
        "candidate_ = nullptr;",
    ):
        if token not in rollback:
            fail("Evaluation rollback guard drift: %s" % token)
    frozen_adapter = git(
        "show",
        "%s:%s" % (PREDECESSOR["merge_commit"], ADAPTER_RELATIVE_PATH.as_posix()),
    ).stdout.decode()
    frozen_rollback = source_region(
        frozen_adapter,
        "class EvaluationForceStorageRollback final {",
        "\n\n}  // namespace",
        "frozen Evaluation force-storage rollback guard",
    )
    if rollback != frozen_rollback:
        fail("reusable Evaluation rollback guard changed from exact PR 474 bytes")

    frozen_body = source_region(
        frozen_adapter,
        "static bg_status evaluate_impl(",
        "\nbg_status evaluate(",
        "frozen native Rust adapter",
    )
    validation_and_commit = source_region(
        body,
        "    const bg_status status = normalize_provider_status(raw_status);",
        "\n    return BG_STATUS_OK;",
        "successor validation and commit",
    )
    frozen_validation_and_commit = source_region(
        frozen_body,
        "    const bg_status status = normalize_provider_status(raw_status);",
        "\n    return BG_STATUS_OK;",
        "frozen validation and commit",
    )
    if validation_and_commit != frozen_validation_and_commit:
        fail("provider validation or external commit changed from exact PR 474 bytes")
    for token in (
        "static_assert(std::is_nothrow_move_assignable_v<Evaluation>);",
        "static_assert(std::is_nothrow_swappable_v<decltype(Evaluation{}.forces)>);",
        "static_assert(std::is_nothrow_copy_assignable_v<std::array<double, 3>>);",
        "compute_forces && reuse_force_storage && out_evaluation != nullptr",
        '"Rust particle-mesh reciprocal provider returned non-finite force on success"',
    ):
        if token not in adapter:
            fail("adapter success-only Evaluation contract drift: %s" % token)

    reciprocal_api = (root / RECIPROCAL_API_RELATIVE_PATH).read_text()
    reciprocal_api_dispatch = source_region(
        reciprocal_api,
        "        Evaluation evaluation;\n        Error typed_error;",
        "\n        if (status != BG_STATUS_OK) {",
        "public reciprocal stateless dispatch",
    )
    require_ordered_tokens(
        reciprocal_api_dispatch,
        (
            "if (context->backend == BG_BACKEND_CPP_CPU_REFERENCE) {",
            "status = cpp_cpu::evaluate(",
            "*system, *model, out_forces != nullptr, &evaluation,",
            "} else {",
            "status = rust_cpu::evaluate(",
            "*system, *model, out_forces != nullptr, &evaluation,",
        ),
        "public reciprocal stateless energy/force caller",
    )

    particle_mesh_ewald = (root / PARTICLE_MESH_EWALD_RELATIVE_PATH).read_text()
    particle_mesh_ewald_dispatch = source_region(
        particle_mesh_ewald,
        "bg_status evaluate_parents(",
        "\n\n}  // namespace",
        "particle-mesh Ewald parent dispatch",
    )
    require_ordered_tokens(
        particle_mesh_ewald_dispatch,
        (
            "if (lane == BG_BACKEND_CPP_CPU_REFERENCE) {",
            "status = particle_mesh_reciprocal::cpp_cpu::evaluate(",
            "system, reciprocal_model, compute_forces,",
            "} else {",
            "status = particle_mesh_reciprocal::rust_cpu::evaluate(",
            "system, reciprocal_model, compute_forces,",
        ),
        "particle-mesh Ewald stateless energy/force caller",
    )

    composite = (root / COMPOSITE_RELATIVE_PATH).read_text()
    region = source_region(
        composite,
        "const bool reuse_reciprocal_parent_force_storage =",
        "\n    if (status != BG_STATUS_OK) {",
        "composite reciprocal dispatch",
    )
    require_ordered_tokens(
        region,
        (
            "const bool use_rust_reciprocal_provider_force_source =",
            "const bool reuse_rust_reciprocal_workspace =",
            "!cpp_lane && stateful_scratch && !compute_forces",
            "if (cpp_lane) {",
            "if (use_rust_reciprocal_provider_force_source) {",
            "evaluate_reusing_provider_force_storage(",
            "} else if (reuse_rust_reciprocal_workspace) {",
            "evaluate_reusing_force_storage(",
            "system, reciprocal_model, false,",
            "} else {",
            "particle_mesh_reciprocal::rust_cpu::evaluate(",
        ),
        "composite stateful force-free workspace dispatch",
    )

    adapter_header = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.hpp"
    ).read_text()
    provider_force_scratch = source_region(
        adapter_header,
        "struct ProviderForceScratch final {",
        "\n\nstruct ProviderForceSourceResult final {",
        "ProviderForceScratch call-local lifetime",
    )
    require_ordered_tokens(
        provider_force_scratch,
        (
            "std::vector<double> x;",
            "std::vector<double> y;",
            "std::vector<double> z;",
            "bg_rust_particle_mesh_reciprocal_workspace_v1 reciprocal_workspace{};",
            "neutrality_sort_scratch{};",
            "particle_assignment_scratch{};",
            "ProviderForceScratch() noexcept = default;",
            "~ProviderForceScratch() noexcept;",
        ),
        "call-local force and exact-zero descriptor fields",
    )
    destructor = source_region(
        adapter,
        "ProviderForceScratch::~ProviderForceScratch() noexcept {",
        "\n\nstatic bg_status evaluate_impl(",
        "ProviderForceScratch destructor",
    )
    require_ordered_tokens(
        destructor,
        (
            "bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_destroy_v1(",
            "&particle_assignment_scratch);",
            "bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_destroy_v1(",
            "&neutrality_sort_scratch);",
            "bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(",
            "&reciprocal_workspace);",
        ),
        "call-local scratch destruction",
    )
    frozen_destructor = source_region(
        frozen_adapter,
        "ProviderForceScratch::~ProviderForceScratch() noexcept {",
        "\n\nstatic bg_status evaluate_impl(",
        "frozen ProviderForceScratch destructor",
    )
    if destructor != frozen_destructor:
        fail("ProviderForceScratch destructor changed from exact PR 474 bytes")

    header = (root / PROVIDER_HEADER_RELATIVE_PATH).read_text()
    declaration = source_region(
        header,
        "%s(" % PRIVATE_SYMBOL,
        "\n\nint32_t\nbg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_v1(",
        "existing all-three-scratch energy provider declaration",
    )
    for token in (
        "const bg_rust_particle_mesh_reciprocal_system_v1 *system",
        "const bg_rust_particle_mesh_reciprocal_model_v1 *model",
        "bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace",
        "bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1",
        "*neutrality_sort_scratch",
        "bg_rust_particle_mesh_reciprocal_particle_assignment_scratch_v1",
        "*particle_assignment_scratch",
        "bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy",
        "bg_rust_particle_mesh_reciprocal_error_v1 *out_error",
    ):
        if token not in declaration:
            fail("all-three-scratch energy provider declaration drift: %s" % token)
    if "bg_rust_particle_mesh_reciprocal_force_output_v1" in declaration:
        fail("all-three-scratch energy declaration accepted force output")
    for inherited_declaration in (
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(",
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_v1(",
        "int32_t bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1(",
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_neutrality_sort_scratch_v1(",
        FORCE_PRIVATE_SYMBOL + "(",
    ):
        if header.count(inherited_declaration) != 1:
            fail("inherited private provider declaration drift: %s" % inherited_declaration)
    if header.count(
        "#define BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION UINT32_C(1)"
    ) != 1:
        fail("private provider ABI version drift")


def require_test_contract(root: Path = ROOT) -> None:
    adapter_test = (root / ADAPTER_TEST_RELATIVE_PATH).read_text()
    for token in (
        "verify_stateless_energy_all_scratch_branch_and_transactionality();",
        "verify_nonreuse_forceful_all_scratch_branch_and_transactional_peer();",
        "verify_late_stateless_all_scratch_failure_preserves_adapter_output();",
        "verify_nonfinite_stateless_all_scratch_success_preserves_adapter_output();",
        "require_only_stateless_energy_all_scratch_route();",
        "require_only_stateless_all_scratch_force_route();",
        "require_stateless_all_scratch_lifecycle();",
        "fake_provider.public_calls == 0U",
        "fake_provider.energy_all_scratch_calls == 1U",
        "fake_provider.triple_calls == 0U",
        "all_scratch_descriptors_were_empty",
        "all_scratch_descriptors_were_distinct",
        "workspace_descriptor_is_empty(",
        "neutrality_sort_scratch_descriptor_is_empty(",
        "particle_assignment_scratch_descriptor_is_empty(",
        "fake_provider.workspace_destroy_calls == 1U",
        "fake_provider.neutrality_sort_scratch_destroy_calls == 1U",
        "fake_provider.particle_assignment_scratch_destroy_calls == 1U",
        "fake_provider.matching_workspace_destroyed",
        "fake_provider.matching_neutrality_sort_scratch_destroyed",
        "fake_provider.matching_particle_assignment_scratch_destroyed",
        "stateless adapter did not supply initially EMPTY scratch descriptors",
        "stateless adapter did not destroy each call-local scratch descriptor exactly once",
        "fake_provider.return_late_energy_numerical_error = true;",
        "fake_provider.return_nonfinite_energy_on_success = true;",
        "require_same_snapshot(output, late_before);",
        "require_same_snapshot(output, nonfinite_before);",
        "stale non-finite stateless energy error",
        "std::numeric_limits<double>::quiet_NaN()",
        "bg_rust_particle_mesh_reciprocal_evaluate_v1(",
        "verify_reusable_forceful_all_scratch_branch_and_transactionality();",
        "require_only_all_scratch_force_route();",
        "require_no_reusable_provider_scratch_destruction();",
        "require_reusable_provider_scratch_destroyed_after_owner_scope();",
        "fake_provider.last_workspace == &scratch.reciprocal_workspace",
        "&scratch.neutrality_sort_scratch",
        "&scratch.particle_assignment_scratch",
        "fake_provider.force_output_failure_pending",
        "fake_provider.force_output_failure_consumed",
        "value.forces.data() == expected.force_storage",
        "value.forces.capacity() == expected.force_capacity",
        PRIVATE_SYMBOL + "(",
        FORCE_PRIVATE_SYMBOL + "(",
    ):
        if token not in adapter_test:
            fail("native stateless energy lifecycle test drift: %s" % token)

    route_helper = source_region(
        adapter_test,
        "void require_only_stateless_energy_all_scratch_route() {",
        "\nvoid require_only_stateless_all_scratch_force_route() {",
        "stateless energy route assertion",
    )
    for token in (
        "fake_provider.public_calls == 0U",
        "fake_provider.direct_calls == 0U",
        "fake_provider.workspace_calls == 0U",
        "fake_provider.energy_workspace_calls == 0U",
        "fake_provider.energy_workspace_neutrality_calls == 0U",
        "fake_provider.energy_all_scratch_calls == 1U",
        "fake_provider.triple_calls == 0U",
    ):
        if route_helper.count(token) != 1:
            fail("stateless energy route assertion drift: %s" % token)

    lifecycle_helper = source_region(
        adapter_test,
        "void require_stateless_all_scratch_lifecycle() {",
        "\nvoid require_no_reusable_provider_scratch_destruction() {",
        "stateless call-local all-scratch lifecycle assertion",
    )
    for token in (
        "fake_provider.all_scratch_descriptors_were_empty",
        "fake_provider.all_scratch_descriptors_were_distinct",
        "fake_provider.workspace_destroy_calls == 1U",
        "fake_provider.neutrality_sort_scratch_destroy_calls == 1U",
        "fake_provider.particle_assignment_scratch_destroy_calls == 1U",
        "fake_provider.matching_workspace_destroyed",
        "fake_provider.matching_neutrality_sort_scratch_destroyed",
        "fake_provider.matching_particle_assignment_scratch_destroyed",
    ):
        if lifecycle_helper.count(token) != 1:
            fail("stateless energy lifecycle assertion drift: %s" % token)

    stateless_energy_test = source_region(
        adapter_test,
        "void verify_stateless_energy_all_scratch_branch_and_transactionality() {",
        "\nvoid verify_nonreuse_forceful_all_scratch_branch_and_transactional_peer() {",
        "stateless energy success/error/non-finite test",
    )
    if stateless_energy_test.count("rust_cpu::evaluate(system, model, false") != 3:
        fail("stateless energy success/error/non-finite dispatch count drift")
    if stateless_energy_test.count(
        "require_only_stateless_energy_all_scratch_route();"
    ) != 3:
        fail("stateless energy route assertion count drift")
    if stateless_energy_test.count("require_stateless_all_scratch_lifecycle();") != 3:
        fail("stateless energy lifecycle assertion count drift")
    for token in (
        "fake_provider.force_output_failure_pending = true;",
        "fake_provider.force_output_failure_pending &&",
        "!fake_provider.force_output_failure_consumed",
        "!fake_provider.force_channels_written",
        "output.forces.empty()",
        "fake_provider.return_late_energy_numerical_error = true;",
        "require_same_snapshot(output, late_before);",
        "fake_provider.return_nonfinite_energy_on_success = true;",
        "require_same_snapshot(output, nonfinite_before);",
    ):
        if stateless_energy_test.count(token) != 1:
            fail("stateless energy transactionality assertion drift: %s" % token)

    fake_energy_provider = source_region(
        adapter_test,
        'extern "C" std::int32_t\n%s(' % PRIVATE_SYMBOL,
        '\n\nextern "C" std::int32_t\n%s(' % FORCE_PRIVATE_SYMBOL,
        "conditional call-local scratch lifecycle fake provider",
    )
    for token in (
        "++fake_provider.energy_all_scratch_calls;",
        "workspace_descriptor_is_empty(workspace)",
        "neutrality_sort_scratch_descriptor_is_empty(neutrality_sort_scratch)",
        "particle_assignment_scratch_descriptor_is_empty(",
        "fake_provider.all_scratch_descriptors_were_distinct =",
        "fake_provider.return_late_energy_numerical_error",
        "fake_provider.return_nonfinite_energy_on_success",
        "std::numeric_limits<double>::quiet_NaN()",
    ):
        if fake_energy_provider.count(token) != 1:
            fail("stateless energy fake-provider contract drift: %s" % token)

    reusable_lifecycle_helpers = source_region(
        adapter_test,
        "void require_no_reusable_provider_scratch_destruction() {",
        "\nvoid require_only_energy_all_scratch_route() {",
        "reusable provider scratch lifecycle helpers",
    )
    for token in (
        "fake_provider.workspace_destroy_calls == 0U",
        "fake_provider.neutrality_sort_scratch_destroy_calls == 0U",
        "fake_provider.particle_assignment_scratch_destroy_calls == 0U",
        "fake_provider.workspace_destroy_calls == 1U",
        "fake_provider.neutrality_sort_scratch_destroy_calls == 1U",
        "fake_provider.particle_assignment_scratch_destroy_calls == 1U",
        "fake_provider.matching_workspace_destroyed",
        "fake_provider.matching_neutrality_sort_scratch_destroyed",
        "fake_provider.matching_particle_assignment_scratch_destroyed",
        "before external owner scope exit",
        "destroyed exactly once",
        "destruction did not match its owner",
    ):
        if reusable_lifecycle_helpers.count(token) != 1:
            fail("reusable provider scratch lifecycle helper drift: %s" % token)
    if adapter_test.count("require_no_reusable_provider_scratch_destruction();") != 6:
        fail("reusable zero-destroy assertion count drift")
    if adapter_test.count(
        "require_reusable_provider_scratch_destroyed_after_owner_scope();"
    ) != 3:
        fail("external reusable owner destruction assertion count drift")
    if adapter_test.count("require_stateless_all_scratch_lifecycle();") != 6:
        fail("stateless call-local lifecycle assertion count drift")

    reusable_forceful = source_region(
        adapter_test,
        "void verify_reusable_forceful_all_scratch_branch_and_transactionality() {",
        "\nvoid verify_reusable_energy_workspace_branch_and_transactionality() {",
        "reusable forceful owner lifecycle",
    )
    reusable_energy = source_region(
        adapter_test,
        "void verify_reusable_energy_workspace_branch_and_transactionality() {",
        "\nvoid verify_reusable_energy_requires_scratch_owner() {",
        "reusable energy owner lifecycle",
    )
    provider_force_source = source_region(
        adapter_test,
        "void verify_provider_force_source_triple_branch() {",
        "\nvoid verify_cpp_lane_remains_provider_independent() {",
        "provider-force-source owner lifecycle",
    )
    for region, zero_count, label in (
        (reusable_forceful, 3, "reusable forceful"),
        (reusable_energy, 2, "reusable energy"),
        (provider_force_source, 1, "provider-force-source"),
    ):
        if region.count("require_no_reusable_provider_scratch_destruction();") != zero_count:
            fail("%s zero-destroy assertion count drift" % label)
        if region.count(
            "require_reusable_provider_scratch_destroyed_after_owner_scope();"
        ) != 1:
            fail("%s owner-scope destruction assertion count drift" % label)
        require_ordered_tokens(
            region,
            (
                "rust_cpu::ProviderForceScratch scratch;",
                "require_no_reusable_provider_scratch_destruction();",
                "require_reusable_provider_scratch_destroyed_after_owner_scope();",
            ),
            "%s conditional scratch lifetime" % label,
        )

    frozen_adapter_test = git(
        "show",
        "%s:%s"
        % (PREDECESSOR["merge_commit"], ADAPTER_TEST_RELATIVE_PATH.as_posix()),
    ).stdout.decode()
    transactional_peer = source_region(
        adapter_test,
        "double force_x[kAtomCount] = {901.0, 902.0};",
        "\n}\n\nvoid verify_",
        "stateless raw-public transactional peer block",
    )
    frozen_transactional_peer = source_region(
        frozen_adapter_test,
        "double force_x[kAtomCount] = {901.0, 902.0};",
        "\n}\n\nvoid verify_",
        "frozen raw-public transactional peer block",
    )
    if transactional_peer != frozen_transactional_peer:
        fail("raw-public transactional force-output peer block changed from PR 474")

    stateless_predecessor_tests = source_region(
        adapter_test,
        "void verify_stateless_energy_all_scratch_branch_and_transactionality() {",
        "\nvoid verify_reusable_forceful_all_scratch_branch_and_transactionality() {",
        "stateless predecessor lifecycle tests",
    )
    frozen_stateless_predecessor_tests = source_region(
        frozen_adapter_test,
        "void verify_stateless_energy_all_scratch_branch_and_transactionality() {",
        "\nvoid verify_reusable_forceful_all_scratch_branch_and_transactionality() {",
        "frozen stateless predecessor lifecycle tests",
    )
    if stateless_predecessor_tests != frozen_stateless_predecessor_tests:
        fail("stateless lifecycle tests changed from exact PR 474 bytes")

    composite_test = (root / COMPOSITE_TEST_RELATIVE_PATH).read_text()
    for token in (
        "stateful Rust force-free evaluation did not provision the reciprocal workspace",
        "stateful Rust force-free evaluation did not provision the neutrality-sort scratch",
        "stateful Rust force-free evaluation retained the wrong neutrality-sort payload",
        "stateful Rust force-free evaluation did not provision the particle-assignment scratch",
        "independent zero-step owners shared reusable Rust scratch storage",
        "warm zero-step integration replaced the owner reciprocal workspace",
        "warm zero-step integration replaced the owner neutrality-sort scratch",
        "warm zero-step integration replaced or resized the owner particle-assignment scratch",
        "stateful Rust forceful evaluation replaced or resized the zero-step reciprocal workspace",
        "stateful Rust forceful evaluation replaced, resized, or aliased the zero-step neutrality-sort scratch",
        "stateful Rust forceful evaluation replaced, resized, or aliased the zero-step particle-assignment scratch",
        "checkpoint(peer.get()) == before_zero",
        "warm owner workspace reuse changed zero-step report bits",
    ):
        if token not in composite_test:
            fail("native zero-step owner test drift: %s" % token)


def require_abi_and_authority_contract(root: Path = ROOT) -> None:
    predecessor_verifier.require_abi_and_authority_contract(root)
    public_surfaces = (
        Path("include/betelgeuze/particle_mesh_reciprocal.h"),
        Path("include/betelgeuze/particle_mesh_ewald_composite_dynamics.h"),
        Path("native/betelgeuze_engine.map"),
        Path("native/betelgeuze_engine.exports"),
        Path("native/tests/check_exports.cmake"),
        Path("rust/betelgeuze-sys/src/lib.rs"),
    )
    for relative in public_surfaces:
        if PRIVATE_SYMBOL in (root / relative).read_text():
            fail("private all-three-scratch symbol leaked: %s" % relative)


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    normalized_doc = " ".join(doc.split())
    for token in (
        "changes only the native C++ adapter provider-dispatch branch and callsite structure",
        "one `if (compute_forces)` force arm and one energy-only `else` arm",
        "force private symbol now has exactly one native-adapter callsite",
        "energy private symbol also has exactly one",
        "does not inspect `reuse_force_storage`, `out_provider_force_source_result`, or `out_evaluation`",
        "provider-force-source validity guard and reusable-owner null guard remain before dispatch",
        "Force vectors, the force descriptor, and `force_pointer` are still prepared before the consolidated force call",
        "provider-force-source, reusable forceful, reusable energy-only, stateless forceful, and stateless energy-only semantic classes",
        "Everything outside the five-arm dispatch block is frozen from exact PR 474 bytes",
        "function-scope `std::optional<ProviderForceScratch>` selection and lifetime",
        "native fake-provider adapter test is unchanged from exact PR 474 bytes",
        "six reusable zero-destroy checks, three external-owner scope destroy checks, and six stateless call-local lifecycle checks",
        "No Rust function, private header declaration, provider symbol, public symbol, provider ABI, status ABI, checkpoint format, production caller, or composite test changes",
        "zero native-adapter callsites",
        "Release and ASan/UBSan workflow lanes build the reciprocal, PME, composite, adapter-transactionality, and composite-dynamics targets",
        "does not execute the real Rust allocator or Rust panic boundary",
        "predecessor workflow detaches the exact PR 474 merge object",
        "branch and callsite consolidation only",
        "No allocation-free, allocation-count, allocation-behavior, heap-allocation-elision, provider-allocation-elision, stack-storage reduction, scratch-footprint reduction, object-size reduction, peak-memory reduction, performance, acceleration, scientific-equivalence, molecular, HIP, product, or operational claim",
        "Reducing source branches and repeated call expressions is not a runtime performance claim",
        "external_reservation_provider_not_operational",
        "historical_execution_operational_authority_false",
        "unresolved operational decisions remain 32",
    ):
        if token not in normalized_doc:
            fail("bounded documentation token drift: %s" % token)


def require_contracts(root: Path = ROOT) -> None:
    require_exact_source_hashes(root)
    require_rust_contract(root)
    require_native_contract(root)
    require_test_contract(root)
    require_abi_and_authority_contract(root)
    require_predecessor_unit_freeze(root)
    require_workflow_contract(root)
    require_docs_contract(root)
    observed = current_delta_paths()
    if observed != EXPECTED_DELTA_PATHS:
        fail(
            "successor delta path set drift: expected %s, observed %s"
            % (
                [path.as_posix() for path in EXPECTED_DELTA_PATHS],
                [path.as_posix() for path in observed],
            )
        )


def verify(root: Path = ROOT) -> dict:
    require_predecessor()
    require_contracts(root)
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest_raw != canonical_bytes(manifest) or manifest != build_source_manifest(root):
        fail("source manifest drift")
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    profile = json.loads(profile_raw)
    if profile_raw != canonical_bytes(profile) or profile != build_profile(manifest_raw):
        fail("profile drift")
    if profile["authority"] != AUTHORITY:
        fail("authority guard drift")
    if profile["operational_boundary"] != {
        "blockers": BLOCKERS,
        "unresolved_operational_decisions": 32,
    }:
        fail("operational boundary drift")
    return {
        "profile_sha256": sha(profile_raw),
        "source_manifest_sha256": sha(manifest_raw),
        "source_count": len(manifest["files"]),
        "delta_path_count": len(EXPECTED_DELTA_PATHS),
        "trigger_path_count": 198,
    }


def refresh(root: Path = ROOT) -> dict:
    require_predecessor()
    require_contracts(root)
    manifest_raw = canonical_bytes(build_source_manifest(root))
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    (root / PROFILE_RELATIVE_PATH).write_bytes(
        canonical_bytes(build_profile(manifest_raw))
    )
    return verify(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    result = refresh() if args.refresh else verify()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as error:
        print("verification failed: %s" % error, file=sys.stderr)
        raise SystemExit(1)
