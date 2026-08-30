#!/usr/bin/env python3
"""Verify bounded native PME Rust-adapter transactional force-output elision."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import NoReturn

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-transactional-force-output-elision.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-owner-particle-assignment-scratch-reuse.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_transactional_force_output_elision_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_profile_v1_sources.json"
)
PREDECESSOR_DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1.md"
)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1.py"
)
CMAKE_RELATIVE_PATH = Path("native/CMakeLists.txt")
ADAPTER_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
)
VENDOR_ADAPTER_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
    "rust_evaluator.cpp"
)
NATIVE_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_reciprocal_rust_adapter_transactionality.cpp"
)
RUST_KERNEL_RELATIVE_PATH = Path(
    "rust/cpu-kernel/src/particle_mesh_reciprocal.rs"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_sources/1.0.0"
)
PUBLIC_PROFILE_ID = (
    "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)

PREDECESSOR = {
    "pull_request": 466,
    "reviewed_head": "88f4ac017d33d188409486dacd8deda1c0f298c4",
    "merge_commit": "0da08391d0487300e1df00ace32bb2954b380f88",
    "merge_tree": "6233b7c1ef87a108b49bc358ad5ed9f574d5832f",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "fd9e484e90da23c366ce6907f0382e940ff763afa5da8975b069e8bbc8478d9f"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "b273e229de1948396ebc52f35c9247cfcc8f70676870271b30d796628367ce8e"
    ),
    "source_manifest_entry_count": 326,
}
DIRECT_OUTPUT_PRECEDENT = {
    "pull_request": 457,
    "reviewed_head": "83ff887e4b9d5e4598023617ca2ed9a4bc87d031",
    "merge_commit": "f20d7a1480a06c29cee5411d84d1d39305f6b461",
    "merge_tree": "1db6841f4884cf0c2774212878b316f5a19d430d",
}

EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)
IMPLEMENTATION_DELTA_PATHS = (
    CMAKE_RELATIVE_PATH,
    ADAPTER_RELATIVE_PATH,
    VENDOR_ADAPTER_RELATIVE_PATH,
    NATIVE_TEST_RELATIVE_PATH,
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
    "bac322e95c839b3e16096421f411097420e632cd19185f720bd9c595eab7ea56"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "b9ce58e56f3e396e677a0b9af8847d02997a7592f65fcb4cf05a09f250b50d9e"
)
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = {
    CMAKE_RELATIVE_PATH: (
        "c25e3388df6c5108ec58a0ec3e552f58aaa7a9dde072ecc999510a659cf449a9"
    ),
    ADAPTER_RELATIVE_PATH: (
        "d57b30e843c33ba1fcd0d2ad34bad12be61105f5938d0a84ac15c7fca3510041"
    ),
    VENDOR_ADAPTER_RELATIVE_PATH: (
        "d57b30e843c33ba1fcd0d2ad34bad12be61105f5938d0a84ac15c7fca3510041"
    ),
}
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = {
    CMAKE_RELATIVE_PATH: (
        "2628fe8050f57a989a0663f876bc57fb0f20c577f3f605b333dab8cc94116de6"
    ),
    ADAPTER_RELATIVE_PATH: (
        "310295ae7c2439ea00a8dc230e7b8c6b75c91fcedfb987098b58c7d7f85f3dbf"
    ),
    VENDOR_ADAPTER_RELATIVE_PATH: (
        "310295ae7c2439ea00a8dc230e7b8c6b75c91fcedfb987098b58c7d7f85f3dbf"
    ),
    NATIVE_TEST_RELATIVE_PATH: (
        "0669560af3606699533bb07640e8fa4363398d7482c244554730dd9e877f3ad4"
    ),
}
UNCHANGED_RUST_KERNEL_SHA256 = (
    "04f9949e5ac70b7e4fdc2a6341c4108024db38ca3470c894a38eec7e6a5e8b6b"
)
FROZEN_UNCHANGED_PATHS = tuple(
    Path(path)
    for path in (
        "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h",
        "native/betelgeuze_engine.map",
        "native/betelgeuze_engine.exports",
        "native/tests/check_exports.cmake",
        "native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/betelgeuze-sys/src/lib.rs",
        "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.hpp",
        RUST_KERNEL_RELATIVE_PATH.as_posix(),
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


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail("frozen %s transformation point drift" % label)
    return source.replace(old, new, 1)


def source_region(source: str, start: str, end: str, label: str) -> str:
    if source.count(start) != 1:
        fail("%s start marker drift" % label)
    start_index = source.index(start)
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        fail("%s end marker drift" % label)
    return source[start_index:end_index]


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
        fail("PR 466 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 466 predecessor merge identity drift")
    if (
        git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
        != PREDECESSOR["merge_tree"]
    ):
        fail("PR 466 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 466 predecessor")
    profile_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix())
    ).stdout
    manifest_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(profile_raw) != PREDECESSOR["profile_sha256"]:
        fail("PR 466 predecessor profile digest drift")
    if sha(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        fail("PR 466 predecessor manifest digest drift")
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 466 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 326:
        fail("PR 466 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted(
        {row.get("path") for row in rows}
    ):
        fail("PR 466 predecessor manifest paths are not sorted and unique")
    if (ROOT / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out PR 466 predecessor profile drift")
    if (ROOT / PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out PR 466 predecessor manifest drift")
    reviewed_tree = reviewed_tree_if_present(PREDECESSOR)
    if reviewed_tree is not None and reviewed_tree != PREDECESSOR["merge_tree"]:
        fail("PR 466 reviewed-head tree drift")
    return manifest


def require_direct_output_precedent() -> None:
    merge = DIRECT_OUTPUT_PRECEDENT["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("PR 457 direct-output precedent is not a commit")
    if (
        git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
        != DIRECT_OUTPUT_PRECEDENT["merge_tree"]
    ):
        fail("PR 457 direct-output precedent tree drift")
    if (
        git("merge-base", "--is-ancestor", merge, PREDECESSOR["merge_commit"], check=False).returncode
        != 0
    ):
        fail("PR 457 direct-output precedent is not inherited by PR 466")
    reviewed_tree = reviewed_tree_if_present(DIRECT_OUTPUT_PRECEDENT)
    if reviewed_tree is not None and reviewed_tree != DIRECT_OUTPUT_PRECEDENT["merge_tree"]:
        fail("PR 457 reviewed-head tree drift")


def current_delta_paths() -> tuple[Path, ...]:
    merge = PREDECESSOR["merge_commit"]
    tracked = git("diff", "--name-only", merge, "--").stdout.decode().splitlines()
    untracked = git(
        "ls-files", "--others", "--exclude-standard"
    ).stdout.decode().splitlines()
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
    if len(result) != 333:
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
            "transactional_force_output_elision_current_sources_tests_evidence_"
            "pr466_target_and_pr457_direct_output_precedent"
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }


def build_profile(manifest_raw: bytes) -> dict:
    manifest = json.loads(manifest_raw)
    return {
        "schema_id": SCHEMA_ID,
        "profile_id": (
            "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
            "rust_reciprocal_provider_transactional_force_output_elision_"
            "development_v1"
        ),
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "direct_force_output_precedent": dict(DIRECT_OUTPUT_PRECEDENT),
        "abi": {
            "public_profile_id": PUBLIC_PROFILE_ID,
            "public_symbol_count": 13,
            "public_symbols": list(predecessor_verifier.PUBLIC_SYMBOLS),
            "public_abi_changed": False,
            "private_provider_abi_changed": False,
            "private_provider_abi_version": 1,
            "status_abi_changed": False,
            "checkpoint_format_changed": False,
            "checkpoint_magic": "BGPME001",
            "checkpoint_header_size_bytes": 104,
            "new_public_or_hidden_symbol_added": False,
            "existing_direct_output_symbol_remains_hidden": True,
        },
        "implementation": {
            "native_nonreuse_forceful_rust_adapter_uses_existing_direct_output_entry": True,
            "native_nonreuse_forceful_adapter_provider_internal_transactional_force_vec_allocation_elided": True,
            "elision_scope_is_only_nonreuse_forceful_native_cpp_adapter": True,
            "energy_only_uses_public_transactional_entry_with_forces_disabled": True,
            "reusable_forceful_workspace_route_preserved": True,
            "provider_force_source_triple_scratch_route_preserved": True,
            "cpp_lane_provider_independence_preserved": True,
            "call_local_cpp_force_soa_preserved": True,
            "late_direct_force_writes_are_disposable_before_adapter_commit": True,
            "evaluation_commit_occurs_after_status_error_and_finite_checks": True,
            "evaluation_pointer_capacity_size_and_bits_preserved_on_late_error": True,
            "raw_rust_transactional_entry_preserved": True,
            "raw_rust_transactional_force_vec_preserved": True,
            "raw_rust_transactional_success_only_commit_preserved": True,
            "raw_direct_force_channels_transactional_claimed": False,
            "public_raw_transactional_vec_removed_claimed": False,
            "provider_wide_transactional_force_allocation_elided_claimed": False,
            "all_force_allocations_elided_claimed": False,
            "cpp_call_local_soa_allocations_elided_claimed": False,
            "final_candidate_aos_allocation_elided_claimed": False,
            "soa_to_aos_copy_elided_claimed": False,
            "allocation_free_claimed": False,
            "provider_allocation_free_claimed": False,
            "steady_state_allocation_free_claimed": False,
            "allocation_failure_timing_invariance_claimed": False,
            "allocation_error_detail_invariance_claimed": False,
            "performance_claimed": False,
            "peak_memory_reduction_claimed": False,
            "acceleration_claimed": False,
            "scientific_claimed": False,
            "scientific_equivalence_claimed": False,
            "cross_lane_bit_parity_claimed": False,
            "product_claimed": False,
            "operational_readiness_claimed": False,
            "fake_provider_is_dispatch_and_commit_separation_test_double": True,
            "fake_provider_production_authority": False,
            "fake_provider_scientific_authority": False,
            "fake_provider_executes_real_rust_allocator": False,
            "fake_provider_executes_real_public_c_api": False,
            "fake_provider_executes_real_rust_panic_boundary": False,
            "fake_provider_proves_real_rust_scientific_transactionality": False,
            "changed_adapter_contract_asan_ubsan_evidence_limited_to_fake_provider": True,
            "real_rust_provider_sanitizer_execution_claimed": False,
            "macos_execution_claimed": False,
            "msvc_execution_claimed": False,
            "cmake_msvc_source_portability_reviewed": True,
            "rust_kernel_source_changed": False,
            "rust_kernel_sha256": UNCHANGED_RUST_KERNEL_SHA256,
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
            "source_manifest_entry_count": len(manifest["files"]),
        },
        "validation": {
            "exact_delta_path_count": 12,
            "implementation_delta_path_count": 4,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 333,
            "pull_request_trigger_path_count_exact": 150,
            "push_trigger_path_count_exact": 150,
            "pull_request_and_push_trigger_sets_symmetric": True,
            "canonical_vendor_adapter_byte_identical": True,
            "four_way_adapter_dispatch_exact": True,
            "final_candidate_commit_separation_exact": True,
            "unchanged_rust_raw_transactional_source_hash_exact": True,
            "existing_rust_kernel_focused_tests_required": True,
            "fake_provider_route_selection_exact": True,
            "fake_provider_late_error_isolation_exact": True,
            "fake_provider_evaluation_storage_retention_exact": True,
            "fake_provider_cpp_lane_separation_exact": True,
            "fake_provider_not_used_as_real_rust_semantics_evidence": True,
            "public_symbol_surfaces_exact": True,
            "hidden_symbol_absent_from_public_surfaces": True,
            "checkpoint_and_static_fingerprint_exact_predecessor_bytes": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
            "release_workflow_builds_standalone_adapter_test": True,
            "sanitizer_workflow_builds_standalone_adapter_test": True,
            "macos_workflow_engine_export_only": True,
            "reviewed_heads_optional_locally_and_exact_when_present": True,
        },
        "authority": dict(AUTHORITY),
        "operational_boundary": {
            "blockers": list(BLOCKERS),
            "unresolved_operational_decisions": 32,
        },
    }


SUCCESSOR_PATH_PAIRS = (
    (PREDECESSOR_WORKFLOW_RELATIVE_PATH, WORKFLOW_RELATIVE_PATH),
    (PREDECESSOR_PROFILE_RELATIVE_PATH, PROFILE_RELATIVE_PATH),
    (PREDECESSOR_MANIFEST_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH),
    (PREDECESSOR_DOC_RELATIVE_PATH, DOC_RELATIVE_PATH),
    (PREDECESSOR_VERIFIER_RELATIVE_PATH, VERIFIER_RELATIVE_PATH),
    (PREDECESSOR_UNIT_RELATIVE_PATH, UNIT_RELATIVE_PATH),
)

SUCCESSOR_MATERIALIZE = """      - name: Materialize exact PR 466 target and PR 457 direct-output precedent
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 0da08391d0487300e1df00ace32bb2954b380f88^{tree})" = "6233b7c1ef87a108b49bc358ad5ed9f574d5832f"
          git merge-base --is-ancestor 0da08391d0487300e1df00ace32bb2954b380f88 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/466/head
          test "$(git rev-parse FETCH_HEAD)" = "88f4ac017d33d188409486dacd8deda1c0f298c4"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6233b7c1ef87a108b49bc358ad5ed9f574d5832f"
          test "$(git rev-parse f20d7a1480a06c29cee5411d84d1d39305f6b461^{tree})" = "1db6841f4884cf0c2774212878b316f5a19d430d"
          git merge-base --is-ancestor f20d7a1480a06c29cee5411d84d1d39305f6b461 0da08391d0487300e1df00ace32bb2954b380f88
          git fetch --no-tags --depth=1 origin refs/pull/457/head
          test "$(git rev-parse FETCH_HEAD)" = "83ff887e4b9d5e4598023617ca2ed9a4bc87d031"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "1db6841f4884cf0c2774212878b316f5a19d430d"
"""

SUCCESSOR_VERIFY = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_transactional_force_output_elision_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_transactional_force_output_elision_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_transactional_force_output_elision_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_transactional_force_output_elision_v1.py"""

PREDECESSOR_MATERIALIZE = """      - name: Materialize exact PR 466 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 0da08391d0487300e1df00ace32bb2954b380f88^{tree})" = "6233b7c1ef87a108b49bc358ad5ed9f574d5832f"
          git merge-base --is-ancestor 0da08391d0487300e1df00ace32bb2954b380f88 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/466/head
          test "$(git rev-parse FETCH_HEAD)" = "88f4ac017d33d188409486dacd8deda1c0f298c4"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6233b7c1ef87a108b49bc358ad5ed9f574d5832f"
"""

PREDECESSOR_VERIFY = """      - name: Verify exact frozen PR 466 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=0da08391d0487300e1df00ace32bb2954b380f88
          frozen_tree=6233b7c1ef87a108b49bc358ad5ed9f574d5832f
          current_sha="$(git rev-parse HEAD)"
          restore() {
            git checkout --detach --quiet "$current_sha"
          }
          trap restore EXIT
          test "$(git rev-parse "$frozen"^{tree})" = "$frozen_tree"
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD)" = "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_particle_assignment_scratch_reuse_v1.py
          restore
          trap - EXIT"""


def add_successor_triggers(workflow: str) -> str:
    result = workflow
    for predecessor, successor in SUCCESSOR_PATH_PAIRS:
        old = '      - "%s"\n' % predecessor.as_posix()
        new = old + '      - "%s"\n' % successor.as_posix()
        if result.count(old) != 2:
            fail("frozen predecessor workflow trigger drift: %s" % predecessor)
        result = result.replace(old, new)
    return result


def expected_successor_workflow(frozen: str) -> str:
    expected = add_successor_triggers(frozen)
    expected = replace_exact(
        expected,
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-owner-particle-assignment-scratch-reuse",
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-transactional-force-output-elision",
        "successor workflow name",
    )
    expected = replace_exact(
        expected,
        "group: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-owner-particle-assignment-scratch-reuse-"
        "${{ github.ref }}",
        "group: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-transactional-force-output-elision-"
        "${{ github.ref }}",
        "successor concurrency group",
    )
    old_build = (
        "build/particle-mesh-ewald-rust-reciprocal-provider-"
        "owner-particle-assignment-scratch-reuse"
    )
    new_build = (
        "build/particle-mesh-ewald-rust-reciprocal-provider-"
        "transactional-force-output-elision"
    )
    if expected.count(old_build) != 10:
        fail("successor workflow build-directory count drift")
    expected = expected.replace(old_build, new_build)
    old_materialize = source_region(
        expected,
        "      - name: Materialize exact PR 465 target, PR 453 architecture, "
        "PR 440 inherited evaluator, and PR 380 direct-output precedent\n",
        "      - name: Verify bounded successor evidence\n",
        "successor immutable materialization",
    )
    expected = replace_exact(
        expected, old_materialize, SUCCESSOR_MATERIALIZE, "successor materialization"
    )
    old_verify = source_region(
        expected,
        "      - name: Verify bounded successor evidence\n",
        "\n\n  native-linux:\n",
        "successor verification",
    )
    expected = replace_exact(
        expected, old_verify, SUCCESSOR_VERIFY, "successor verification"
    )
    old_target = (
        "--target betelgeuze_engine_particle_mesh_reciprocal "
        "betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2"
    )
    new_target = (
        "--target betelgeuze_engine_particle_mesh_reciprocal "
        "betelgeuze_engine_particle_mesh_reciprocal_rust_adapter_transactionality "
        "betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2"
    )
    if expected.count(old_target) != 2:
        fail("successor workflow native target count drift")
    expected = expected.replace(old_target, new_target)
    release_regex = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|"
        "particle_mesh_ewald_composite_dynamics|export_allowlist)$'"
    )
    release_replacement = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|"
        "particle_mesh_reciprocal_rust_adapter_transactionality|"
        "particle_mesh_ewald_composite_dynamics|export_allowlist)$'"
    )
    sanitize_regex = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|"
        "particle_mesh_ewald_composite_dynamics)$'"
    )
    sanitize_replacement = (
        "'^betelgeuze_engine_(particle_mesh_reciprocal|"
        "particle_mesh_reciprocal_rust_adapter_transactionality|"
        "particle_mesh_ewald_composite_dynamics)$'"
    )
    expected = replace_exact(
        expected, release_regex, release_replacement, "successor release regex"
    )
    expected = replace_exact(
        expected, sanitize_regex, sanitize_replacement, "successor sanitizer regex"
    )
    return expected


def expected_frozen_predecessor_workflow(frozen: str) -> str:
    expected = add_successor_triggers(frozen)
    old_materialize = source_region(
        expected,
        "      - name: Materialize exact PR 465 target, PR 453 architecture, "
        "PR 440 inherited evaluator, and PR 380 direct-output precedent\n",
        "      - name: Verify bounded successor evidence\n",
        "predecessor immutable materialization",
    )
    expected = replace_exact(
        expected,
        old_materialize,
        PREDECESSOR_MATERIALIZE,
        "predecessor materialization",
    )
    old_verify = source_region(
        expected,
        "      - name: Verify bounded successor evidence\n",
        "\n\n  native-linux:\n",
        "predecessor verification",
    )
    return replace_exact(
        expected, old_verify, PREDECESSOR_VERIFY, "predecessor frozen verification"
    )


def expected_frozen_predecessor_unit(frozen: str) -> str:
    anchor = "ROOT = Path(__file__).resolve().parents[2]\n"
    addition = """PME_RUST_RECIPROCAL_PROVIDER_TRANSACTIONAL_FORCE_OUTPUT_ELISION_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_transactional_force_output_elision_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_TRANSACTIONAL_FORCE_OUTPUT_ELISION_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal-provider owner particle-assignment scratch evidence "
        "is verified from its exact frozen PR 466 object after transactional "
        "force-output elision evidence is present"
    ),
)
"""
    return replace_exact(frozen, anchor, anchor + addition, "predecessor unit")


def workflow_trigger_paths(workflow: str, event: str, end: str) -> tuple[str, ...]:
    region = source_region(
        workflow,
        "  %s:\n" % event,
        "  %s:\n" % end,
        "%s trigger" % event,
    )
    return tuple(re.findall(r'^      - "([^"]+)"$', region, re.MULTILINE))


def require_workflow_contract(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_WORKFLOW_SHA256:
        fail("pristine PR 466 workflow digest drift")
    frozen = frozen_raw.decode()
    successor = (root / WORKFLOW_RELATIVE_PATH).read_text()
    predecessor = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    if successor != expected_successor_workflow(frozen):
        fail("successor workflow exact document drift")
    if predecessor != expected_frozen_predecessor_workflow(frozen):
        fail("PR 466 predecessor workflow freeze drift")
    pull_paths = workflow_trigger_paths(successor, "pull_request", "push")
    push_paths = workflow_trigger_paths(successor, "push", "workflow_dispatch")
    if (
        len(pull_paths) != 150
        or len(set(pull_paths)) != 150
        or push_paths != pull_paths
    ):
        fail("workflow 150-path symmetric trigger contract drift")
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
        fail("workflow exact job set drift")
    if successor.count("uses: %s" % PINNED_CHECKOUT_ACTION) != 4:
        fail("workflow checkout pin count drift")
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
    if (
        "cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-"
        "transactional-force-output-elision-macos --target betelgeuze_engine "
        "--parallel 2"
    ) not in successor:
        fail("macOS workflow must remain engine/export-only")


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_UNIT_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_UNIT_SHA256:
        fail("pristine PR 466 unit digest drift")
    current = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if current != expected_frozen_predecessor_unit(frozen_raw.decode()):
        fail("PR 466 predecessor unit freeze drift")


def require_exact_source_hashes(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    for relative, predecessor_digest in EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256.items():
        predecessor_raw = git("show", "%s:%s" % (merge, relative.as_posix())).stdout
        successor_raw = (root / relative).read_bytes()
        if sha(predecessor_raw) != predecessor_digest:
            fail("frozen PR 466 implementation digest drift: %s" % relative)
        if sha(successor_raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256[relative]:
            fail("successor implementation digest drift: %s" % relative)
        if predecessor_raw == successor_raw:
            fail("declared implementation path did not change: %s" % relative)
    if git(
        "cat-file",
        "-e",
        "%s:%s" % (merge, NATIVE_TEST_RELATIVE_PATH.as_posix()),
        check=False,
    ).returncode == 0:
        fail("standalone adapter test unexpectedly exists in PR 466")
    if (
        sha((root / NATIVE_TEST_RELATIVE_PATH).read_bytes())
        != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256[NATIVE_TEST_RELATIVE_PATH]
    ):
        fail("standalone adapter test digest drift")
    if (root / ADAPTER_RELATIVE_PATH).read_bytes() != (
        root / VENDOR_ADAPTER_RELATIVE_PATH
    ).read_bytes():
        fail("canonical/vendor adapter mirror drift")
    for relative in FROZEN_UNCHANGED_PATHS:
        current = (root / relative).read_bytes()
        frozen = git("show", "%s:%s" % (merge, relative.as_posix())).stdout
        if current != frozen:
            fail("unchanged ABI/checkpoint/Rust source drift: %s" % relative)
    if sha((root / RUST_KERNEL_RELATIVE_PATH).read_bytes()) != UNCHANGED_RUST_KERNEL_SHA256:
        fail("unchanged Rust kernel digest drift")


def require_adapter_contract(root: Path = ROOT) -> None:
    source = (root / ADAPTER_RELATIVE_PATH).read_text()
    start = source.index("static bg_status evaluate_impl(")
    end = source.index("\nbg_status evaluate(", start)
    body = source[start:end]
    triple = (
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_"
        "with_workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1("
    )
    workspace = (
        "bg_rust_particle_mesh_reciprocal_"
        "evaluate_reusing_force_output_with_workspace_v1("
    )
    direct = "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1("
    public = "bg_rust_particle_mesh_reciprocal_evaluate_v1("
    for symbol in (triple, workspace, direct, public):
        if body.count(symbol) != 1:
            fail("adapter four-way call count drift: %s" % symbol)
    require_ordered_tokens(
        body,
        (
            "if (out_provider_force_source_result != nullptr) {",
            triple,
            "} else if (reuse_force_storage && compute_forces) {",
            workspace,
            "} else if (compute_forces) {",
            direct,
            "} else {",
            public,
            "UINT8_C(0), &provider_energy, force_pointer, &provider_error",
            "const bg_status status = normalize_provider_status(raw_status);",
            "if (status != BG_STATUS_OK) {",
            "if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol)) {",
            "candidate.reciprocal_space_kcal_per_mol =",
            "if (compute_forces) {",
            "if (!std::isfinite(active_provider_force_scratch->x[atom])",
            "candidate.forces[atom] = {",
            "*out_evaluation = std::move(candidate);",
        ),
        "adapter dispatch and commit separation",
    )
    for forbidden in (
        "const bool direct_force_output",
        "compute_forces ? UINT8_C(1) : UINT8_C(0)",
    ):
        if forbidden in body:
            fail("removed adapter transactional dispatch remains: %s" % forbidden)
    for token in (
        "ProviderForceScratch local_provider_force_scratch;",
        "reuse_force_storage ? provider_force_scratch",
        ": &local_provider_force_scratch;",
        "candidate.forces.swap(out_evaluation->forces);",
        "if (compute_forces && reuse_force_storage && out_evaluation != nullptr)",
    ):
        if body.count(token) != 1:
            fail("call-local SoA or reusable-route separation drift: %s" % token)
    if body.count("*out_evaluation = std::move(candidate);") != 1:
        fail("adapter final Evaluation commit count drift")


def require_unchanged_rust_contract(root: Path = ROOT) -> None:
    rust = (root / RUST_KERNEL_RELATIVE_PATH).read_text()
    public_region = source_region(
        rust,
        'pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_v1(',
        "/// Evaluate reciprocal-only order-4 particle-mesh electrostatics directly into",
        "raw transactional provider",
    )
    direct_region = source_region(
        rust,
        'pub unsafe extern "C" fn bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(',
        "/// Evaluate through the direct-force provider while leasing an owner-private",
        "raw direct provider",
    )
    for token in (
        "ProviderForceMode::Transactional(compute_forces)",
        "commit_candidate(candidate, out_energy)",
    ):
        if token not in public_region:
            fail("unchanged raw transactional Rust contract drift: %s" % token)
    for token in (
        "ProviderForceMode::Direct {",
        "workspace: None",
        "neutrality_sort_scratch: None",
        "particle_assignment_scratch: None",
        "commit_candidate(candidate, out_energy)",
    ):
        if token not in direct_region:
            fail("unchanged raw direct Rust contract drift: %s" % token)
    for token in (
        "fallible_reserve_exact(&mut forces, assignments.len(), AllocationSite::ForceOutput)?;",
        "fn direct_provider_skips_force_allocation_and_preserves_outputs_on_earlier_oom()",
        "fn late_scientific_failure_keeps_energy_transactional_and_direct_forces_disposable()",
    ):
        if token not in rust:
            fail("unchanged Rust allocator/test anchor drift: %s" % token)


def require_native_test_and_cmake_contract(root: Path = ROOT) -> None:
    test = (root / NATIVE_TEST_RELATIVE_PATH).read_text()
    cmake = (root / CMAKE_RELATIVE_PATH).read_text()
    for token in (
        "verify_energy_only_public_branch();",
        "verify_nonreuse_forceful_direct_branch_and_transactional_peer();",
        "verify_late_direct_failure_preserves_adapter_output();",
        "verify_reusable_forceful_workspace_branch();",
        "verify_provider_force_source_triple_branch();",
        "verify_cpp_lane_remains_provider_independent();",
        "require_same_snapshot(output, before);",
        "fake_provider.force_output_failure_pending",
        "fake_provider.force_output_failure_consumed",
        "bg_rust_particle_mesh_reciprocal_evaluate_v1(",
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(",
    ):
        if token not in test:
            fail("standalone fake-provider regression drift: %s" % token)
    target = "betelgeuze_engine_particle_mesh_reciprocal_rust_adapter_transactionality"
    if cmake.count("add_executable(\n        %s" % target) != 1:
        fail("standalone adapter CMake target drift")
    for token in (
        "tests/particle_mesh_reciprocal_rust_adapter_transactionality.cpp",
        "src/particle_mesh_reciprocal/rust_evaluator.cpp",
        "src/particle_mesh_reciprocal/cpp_evaluator.cpp",
        "NAME %s" % target,
        "-fsanitize=address,undefined",
    ):
        if token == "-fsanitize=address,undefined":
            continue
        if token not in cmake:
            fail("standalone adapter CMake wiring drift: %s" % token)
    target_region = source_region(
        cmake,
        "    add_executable(\n        %s\n" % target,
        "\n    add_executable(\n        betelgeuze_engine_particle_mesh_ewald\n",
        "standalone adapter CMake target",
    )
    if "target_link_libraries(" in target_region or "betelgeuze_engine\n" in target_region:
        fail("standalone fake-provider target linked the product engine")
    public_surfaces = (
        "include/betelgeuze/particle_mesh_reciprocal.h",
        "native/betelgeuze_engine.map",
        "native/betelgeuze_engine.exports",
        "rust/betelgeuze-sys/src/lib.rs",
    )
    for relative in public_surfaces:
        if "FakeProviderState" in (root / relative).read_text():
            fail("fake-provider hook leaked into public/product surface: %s" % relative)


def require_abi_and_authority_contract(root: Path = ROOT) -> None:
    predecessor_verifier.require_exact_public_symbols(root)
    provider_header = (
        root / "native/src/particle_mesh_reciprocal/rust_provider.h"
    ).read_text()
    if (
        provider_header.count(
            "#define BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION UINT32_C(1)"
        )
        != 1
    ):
        fail("private provider ABI version drift")
    hidden = "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1"
    for relative in (
        Path("include/betelgeuze/particle_mesh_reciprocal.h"),
        Path("include/betelgeuze/particle_mesh_ewald_composite_dynamics.h"),
        Path("native/betelgeuze_engine.map"),
        Path("native/betelgeuze_engine.exports"),
        Path("native/tests/check_exports.cmake"),
        Path("rust/betelgeuze-sys/src/lib.rs"),
    ):
        if hidden in (root / relative).read_text():
            fail("existing hidden direct-output symbol leaked: %s" % relative)


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    for token in (
        "non-reuse force-producing native Rust adapter",
        "call-local C++ SoA",
        "raw Rust transactional entry remains unchanged",
        "fake provider is only a route-selection and commit-separation test double",
        "does not execute the real Rust allocator",
        "does not prove production or scientific transactionality",
        "changed adapter contract, ASan/UBSan evidence is limited to the fake-provider adapter target",
        "macOS and MSVC execution is not claimed",
        "No performance, acceleration, scientific-equivalence, or product claim",
        "external_reservation_provider_not_operational",
        "unresolved operational decisions remain 32",
    ):
        if token not in doc:
            fail("bounded documentation token drift: %s" % token)


def require_contracts(root: Path = ROOT) -> None:
    require_direct_output_precedent()
    require_exact_source_hashes(root)
    require_adapter_contract(root)
    require_unchanged_rust_contract(root)
    require_native_test_and_cmake_contract(root)
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
        "trigger_path_count": 150,
    }


def refresh(root: Path = ROOT) -> dict:
    require_predecessor()
    require_contracts(root)
    manifest_raw = canonical_bytes(build_source_manifest(root))
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    (root / PROFILE_RELATIVE_PATH).write_bytes(canonical_bytes(build_profile(manifest_raw)))
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
