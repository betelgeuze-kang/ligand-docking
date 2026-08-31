#!/usr/bin/env python3
"""Verify stateful Rust zero-step owner neutrality-sort scratch reuse."""
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
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_zero_step_neutrality_sort_scratch_reuse"
)
WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-owner-zero-step-neutrality-sort-scratch-reuse"
)
PREDECESSOR_STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse"
)
PREDECESSOR_WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-owner-zero-step-reciprocal-workspace-reuse"
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
    "rust_reciprocal_provider_owner_zero_step_neutrality_sort_scratch_reuse_"
    "profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_zero_step_neutrality_sort_scratch_reuse_"
    "sources/1.0.0"
)
PUBLIC_PROFILE_ID = (
    "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
)
PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_and_"
    "neutrality_sort_scratch_v1"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)

PREDECESSOR = {
    "pull_request": 468,
    "reviewed_head": "a4842999511768d8b306e5699e96f1d4e13d11b8",
    "merge_commit": "2fc5debf2717b0068927a725736d4caa4ca85016",
    "merge_tree": "b66dc386d742471766eeb9ebc78d6d56952e9132",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "54689a50a034f6963b3c3528901ed003fea2055ba39484ae2dd24fee3fded9e8"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "f29c2d548deda8785c99c6a88f9e93763226f5771e2cf0a90804cfff26f7e0db"
    ),
    "source_manifest_entry_count": 339,
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
IMPLEMENTATION_DELTA_PATHS = (
    ADAPTER_RELATIVE_PATH,
    PROVIDER_HEADER_RELATIVE_PATH,
    COMPOSITE_TEST_RELATIVE_PATH,
    ADAPTER_TEST_RELATIVE_PATH,
    VENDOR_ADAPTER_RELATIVE_PATH,
    VENDOR_PROVIDER_HEADER_RELATIVE_PATH,
    RUST_KERNEL_RELATIVE_PATH,
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
    "375656ef6fdb7b4d5b2bc9ada9684df35db91fe36347901fc0f1be9ee128c9a2"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "e4746d36b6b2e1a818579c40c49e8011c57fd5d47532ee97523fd995ebfad018"
)
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = {
    ADAPTER_RELATIVE_PATH: "eefa90fb3c35a5d6d79ae45cf49447d2b16b84a49ca8ac43523d363c1059c692",
    PROVIDER_HEADER_RELATIVE_PATH: "a8ab27b7ce6f5b6d92b9dd01bbdd0bf39ed356b7e4abbad3a3f9f7a2978680e2",
    COMPOSITE_TEST_RELATIVE_PATH: "f8b16a09047dbe8c41d654546ab77f38b2e3e46b8994b9648281df8e74e29edc",
    ADAPTER_TEST_RELATIVE_PATH: "01b62c21d1544cfafb29c31fe8a8c45cf5d13578e0e3dd55095107ee4a761e7b",
    VENDOR_ADAPTER_RELATIVE_PATH: "eefa90fb3c35a5d6d79ae45cf49447d2b16b84a49ca8ac43523d363c1059c692",
    VENDOR_PROVIDER_HEADER_RELATIVE_PATH: "a8ab27b7ce6f5b6d92b9dd01bbdd0bf39ed356b7e4abbad3a3f9f7a2978680e2",
    RUST_KERNEL_RELATIVE_PATH: "cad9fa655f6eb9e5f8453368dfa587168a4d10d09a827109c103401635f76ccd",
}
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = {
    ADAPTER_RELATIVE_PATH: "777c74792ff0801766066be75dc8a52a9a9ba870d21490c612462a6e30de8ac5",
    PROVIDER_HEADER_RELATIVE_PATH: "423735fc73fd93d23bbe29896836c4c2fcaa653cd00084a91c5af6638c748bb0",
    COMPOSITE_TEST_RELATIVE_PATH: "9014ca21d552646d4a6b27089fed330ba4356ca0867bb740ede0a86f9e3bf81a",
    ADAPTER_TEST_RELATIVE_PATH: "15cabc382b06c6aeada18d923ea34ded6255f8e908a3d6c1daef1d21271f39af",
    VENDOR_ADAPTER_RELATIVE_PATH: "777c74792ff0801766066be75dc8a52a9a9ba870d21490c612462a6e30de8ac5",
    VENDOR_PROVIDER_HEADER_RELATIVE_PATH: "423735fc73fd93d23bbe29896836c4c2fcaa653cd00084a91c5af6638c748bb0",
    RUST_KERNEL_RELATIVE_PATH: "27348e959fd4707ec3f6f6830c040f2b180b4138c0c6fd6a669761f58647137b",
}

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
        "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
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
        fail("exact frozen PR 468 workflow digest drift")
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
            fail("exact frozen PR 468 workflow trigger anchor drift: %s" % predecessor_path)
        expected = expected.replace(
            anchor,
            anchor + '      - "%s"\n' % successor_path.as_posix(),
        )
    old_region = source_region(
        expected,
        "      - name: Materialize exact PR 467 target and reviewed head\n",
        "\n\n  native-linux:\n",
        "exact frozen PR 468 immutable-evidence predecessor block",
    )
    new_region = """      - name: Materialize exact PR 468 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 2fc5debf2717b0068927a725736d4caa4ca85016^{tree})" = "b66dc386d742471766eeb9ebc78d6d56952e9132"
          git merge-base --is-ancestor 2fc5debf2717b0068927a725736d4caa4ca85016 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/468/head
          test "$(git rev-parse FETCH_HEAD)" = "a4842999511768d8b306e5699e96f1d4e13d11b8"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b66dc386d742471766eeb9ebc78d6d56952e9132"
      - name: Verify exact frozen PR 468 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=2fc5debf2717b0068927a725736d4caa4ca85016
          frozen_tree=b66dc386d742471766eeb9ebc78d6d56952e9132
          current_sha="$(git rev-parse HEAD)"
          restore() { git checkout --detach --quiet "$current_sha"; }
          trap restore EXIT
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_zero_step_reciprocal_workspace_reuse_v1.py
          restore
          trap - EXIT"""
    return replace_once(
        expected,
        old_region,
        new_region,
        "exact frozen PR 468 immutable-evidence block",
    )


def expected_predecessor_unit() -> str:
    frozen_raw = git(
        "show",
        "%s:%s" % (PREDECESSOR["merge_commit"], PREDECESSOR_UNIT_RELATIVE_PATH),
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_UNIT_SHA256:
        fail("exact frozen PR 468 unit digest drift")
    expected = frozen_raw.decode()
    expected = replace_once(
        expected,
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport pytest\n",
        "exact frozen PR 468 unit pytest import",
    )
    skip = """ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_OWNER_ZERO_STEP_NEUTRALITY_SORT_REUSE_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_zero_step_neutrality_sort_scratch_reuse_"
    "profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_OWNER_ZERO_STEP_NEUTRALITY_SORT_REUSE_EVIDENCE_PRESENT,
    reason=(
        "owner zero-step reciprocal workspace reuse evidence is verified from "
        "its exact frozen PR 468 object after zero-step neutrality-sort scratch "
        "reuse evidence is present"
    ),
)"""
    return replace_once(
        expected,
        "ROOT = Path(__file__).resolve().parents[2]",
        skip,
        "exact frozen PR 468 unit successor skip",
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
        fail("PR 468 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 468 predecessor merge identity drift")
    if git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode() != PREDECESSOR["merge_tree"]:
        fail("PR 468 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 468 predecessor")
    profile_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix())
    ).stdout
    manifest_raw = git(
        "show", "%s:%s" % (merge, PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix())
    ).stdout
    if sha(profile_raw) != PREDECESSOR["profile_sha256"]:
        fail("PR 468 predecessor profile digest drift")
    if sha(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        fail("PR 468 predecessor manifest digest drift")
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 468 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 339:
        fail("PR 468 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted({row.get("path") for row in rows}):
        fail("PR 468 predecessor manifest paths are not sorted and unique")
    if (ROOT / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out PR 468 predecessor profile drift")
    if (ROOT / PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out PR 468 predecessor manifest drift")
    reviewed_tree = reviewed_tree_if_present(PREDECESSOR)
    if reviewed_tree is not None and reviewed_tree != PREDECESSOR["merge_tree"]:
        fail("PR 468 reviewed-head tree drift")
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
    if len(result) != 345:
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
            "owner_zero_step_neutrality_sort_scratch_reuse_current_sources_"
            "tests_evidence_pr468_target"
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
            "private_provider_abi_changed": True,
            "private_provider_abi_version": 1,
            "new_private_hidden_symbol_added": True,
            "new_private_hidden_symbol": PRIVATE_SYMBOL,
            "private_hidden_symbol_absent_from_public_surfaces": True,
            "private_hidden_symbol_present_in_linux_linked_image": True,
            "private_hidden_symbol_absent_from_linux_dynamic_exports": True,
            "status_abi_changed": False,
            "checkpoint_format_changed": False,
            "checkpoint_magic": "BGPME001",
            "checkpoint_header_size_bytes": 104,
        },
        "implementation": {
            "scope_is_only_stateful_rust_force_free_composite_evaluation": True,
            "zero_step_integrator_uses_stateful_force_free_provider": True,
            "stateful_rust_force_free_owner_reciprocal_workspace_reused": True,
            "stateful_rust_force_free_owner_neutrality_sort_scratch_reused": True,
            "workspace_and_neutrality_hidden_energy_entry_added": True,
            "predecessor_workspace_only_hidden_energy_entry_preserved": True,
            "workspace_and_neutrality_entry_accepts_no_force_descriptor": True,
            "workspace_and_neutrality_entry_accepts_no_particle_assignment_scratch": True,
            "workspace_and_neutrality_mode_is_explicit": True,
            "workspace_and_neutrality_mode_uses_force_storage_disabled": True,
            "workspace_and_neutrality_mode_uses_shared_provider_preflight_and_leases": True,
            "workspace_and_neutrality_descriptors_and_full_capacities_alias_preflight_before_lease": True,
            "workspace_and_neutrality_pairwise_disjointness_required": True,
            "workspace_and_neutrality_empty_and_ready_states_accepted": True,
            "workspace_and_neutrality_leased_and_malformed_states_rejected": True,
            "workspace_and_neutrality_drops_restore_empty_after_cold_unallocated_failure": True,
            "workspace_and_neutrality_drops_restore_ready_after_success_error_or_panic": True,
            "energy_output_committed_only_on_success": True,
            "workspace_payload_is_derived_and_nontransactional": True,
            "neutrality_sort_payload_is_derived_and_nontransactional": True,
            "cold_allocation_order_neutrality_assignments_workspace": True,
            "cold_allocation_error_details_preserved": True,
            "later_cold_failure_may_retain_ready_neutrality_scratch": True,
            "force_output_allocation_skipped": True,
            "warm_capacity_sufficient_workspace_reserve_elided": True,
            "warm_capacity_sufficient_neutrality_reserve_elided": True,
            "call_local_particle_assignment_allocation_preserved": True,
            "workspace_growth_oom_preserves_ready_raw_parts_and_payload": True,
            "neutrality_growth_oom_preserves_ready_raw_parts_and_payload": True,
            "owner_force_channels_untouched_by_force_free_entry": True,
            "owner_particle_assignment_scratch_untouched_by_force_free_entry": True,
            "independent_owner_workspace_allocations_disjoint": True,
            "independent_owner_neutrality_sort_allocations_disjoint": True,
            "energy_forceful_workspace_and_neutrality_interoperation_preserved": True,
            "zero_step_report_and_checkpoint_bits_preserved": True,
            "stateful_forceful_triple_scratch_route_preserved": True,
            "reusable_forceful_workspace_route_preserved": True,
            "nonreuse_forceful_direct_route_preserved": True,
            "stateless_force_free_transactional_route_preserved": True,
            "cpp_lane_provider_independence_preserved": True,
            "fake_provider_is_dispatch_and_commit_separation_test_double": True,
            "fake_provider_production_authority": False,
            "fake_provider_scientific_authority": False,
            "fake_provider_executes_real_rust_allocator": False,
            "fake_provider_executes_real_rust_panic_boundary": False,
            "real_rust_provider_sanitizer_execution_claimed": False,
            "neutrality_sort_scratch_reuse_claimed": True,
            "particle_assignment_scratch_reuse_claimed": False,
            "workspace_payload_transactionality_claimed": False,
            "neutrality_sort_payload_transactionality_claimed": False,
            "concurrent_workspace_use_claimed": False,
            "concurrent_neutrality_sort_scratch_use_claimed": False,
            "allocation_free_claimed": False,
            "provider_allocation_free_claimed": False,
            "steady_state_allocation_free_claimed": False,
            "local_particle_assignment_allocation_elided_claimed": False,
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
            "exact_delta_path_count": 15,
            "implementation_delta_path_count": 7,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 345,
            "pull_request_trigger_path_count_exact": 162,
            "push_trigger_path_count_exact": 162,
            "pull_request_and_push_trigger_sets_symmetric": True,
            "canonical_vendor_composite_exact_predecessor_bytes": True,
            "canonical_vendor_adapter_byte_identical": True,
            "canonical_vendor_provider_header_byte_identical": True,
            "five_way_adapter_dispatch_exact": True,
            "stateful_rust_force_free_composite_dispatch_exact": True,
            "rust_workspace_and_neutrality_mode_and_abi_exact": True,
            "rust_alias_oom_panic_transactionality_tests_exact": True,
            "native_adapter_route_and_commit_tests_exact": True,
            "native_zero_step_owner_reuse_tests_exact": True,
            "public_symbol_surfaces_exact": True,
            "private_hidden_symbol_absent_from_public_surfaces": True,
            "linux_private_hidden_symbol_local_and_not_dynamic": True,
            "checkpoint_and_static_fingerprint_exact_predecessor_bytes": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
            "release_workflow_builds_real_rust_and_adapter_tests": True,
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
        fail("PR 468 predecessor workflow is not the exact frozen-object transformation")
    for workflow, expected_name in (
        (successor, WORKFLOW_STEM),
        (predecessor, PREDECESSOR_WORKFLOW_STEM),
    ):
        if workflow.count("name: %s\n" % expected_name) != 1:
            fail("workflow name drift: %s" % expected_name)
        pull_paths = workflow_trigger_paths(workflow, "pull_request", "push")
        push_paths = workflow_trigger_paths(workflow, "push", "workflow_dispatch")
        if len(pull_paths) != 162 or len(set(pull_paths)) != 162 or push_paths != pull_paths:
            fail("workflow 162-path symmetric trigger contract drift: %s" % expected_name)
        if set(path.as_posix() for path in EVIDENCE_PATHS) - set(pull_paths):
            fail("workflow successor evidence trigger drift: %s" % expected_name)
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
            fail("PR 468 predecessor workflow freeze drift: %s" % token)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    unit = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if unit != expected_predecessor_unit():
        fail("PR 468 predecessor unit is not the exact frozen-object transformation")
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
            fail("PR 468 predecessor unit freeze drift: %s" % token)
    if PROFILE_RELATIVE_PATH.as_posix() not in constants:
        fail("PR 468 predecessor unit successor-profile path drift")
    if not any("exact frozen PR 468 object" in value for value in constants):
        fail("PR 468 predecessor unit frozen-object reason drift")
    if "is_file()" not in unit:
        fail("PR 468 predecessor unit skip is not successor-profile scoped")


def require_exact_source_hashes(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    for relative in IMPLEMENTATION_DELTA_PATHS:
        predecessor_raw = git("show", "%s:%s" % (merge, relative.as_posix())).stdout
        successor_raw = (root / relative).read_bytes()
        if sha(predecessor_raw) != EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256[relative]:
            fail("frozen PR 468 implementation digest drift: %s" % relative)
        if sha(successor_raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256[relative]:
            fail("successor implementation digest drift: %s" % relative)
        if predecessor_raw == successor_raw:
            fail("declared implementation path did not change: %s" % relative)
    for canonical, vendor, label in (
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


def require_rust_contract(root: Path = ROOT) -> None:
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
        "neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1",
        "Direct {",
    ):
        if token not in enum_region:
            fail("provider mode drift: %s" % token)
    helper = source_region(
        source,
        "fn evaluate_energy_with_workspace_and_neutrality_sort_scratch",
        "\nfn evaluate_with_direct_force_output_and_reusable_storage",
        "workspace-plus-neutrality energy helper",
    )
    for token in (
        "ForceStorageMode::Disabled",
        "Some(workspace)",
        "Some(neutrality_sort_scratch)",
        "None",
        ".reciprocal_space_kcal_per_mol",
    ):
        if token not in helper:
            fail("workspace-plus-neutrality energy helper drift: %s" % token)
    for forbidden in ("ForceStorageMode::Direct", "ForceStorageMode::Transactional"):
        if forbidden in helper:
            fail("workspace-plus-neutrality energy helper gained force storage")
    provider = source_region(
        source,
        "unsafe fn evaluate_provider_impl(",
        "\nunsafe fn validate_error_output",
        "provider implementation",
    )
    require_ordered_tokens(
        provider,
        (
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratch {",
            "} => (Some(workspace), Some(neutrality_sort_scratch), None)",
            "let workspace_preflight =",
            "let neutrality_sort_scratch_preflight =",
            "require_disjoint_outputs(&mutable_ranges)?;",
            "for input_range in input_ranges.into_iter().flatten()",
            "alias_safety.set(true);",
            "ReciprocalWorkspaceLease::acquire(preflight)",
            "NeutralitySortScratchLease::acquire(preflight)",
            "provider_input(&system, model)",
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratch { .. } => {",
            "evaluate_energy_with_workspace_and_neutrality_sort_scratch(",
            "neutrality_sort_scratch.scratch_mut()",
            "(energy, Vec::new(), None)",
        ),
        "workspace-plus-neutrality provider preflight and evaluation",
    )
    if (
        provider.count(
            "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratch { .. } => 0"
        )
        != 1
    ):
        fail("workspace-plus-neutrality provider compute-forces mode drift")
    abi = source_region(
        source,
        'pub unsafe extern "C" fn %s(' % PRIVATE_SYMBOL,
        "\n/// Evaluate reciprocal-only order-4 particle-mesh electrostatics directly into",
        "workspace-plus-neutrality hidden ABI",
    )
    for token in (
        "system: *const ParticleMeshReciprocalSystemV1",
        "model: *const ParticleMeshReciprocalModelV1",
        "workspace: *mut ParticleMeshReciprocalWorkspaceV1",
        "neutrality_sort_scratch: *mut ParticleMeshReciprocalNeutralitySortScratchV1",
        "out_energy: *mut ParticleMeshReciprocalEnergyV1",
        "out_error: *mut ParticleMeshReciprocalErrorV1",
        ") -> i32",
        "catch_unwind(AssertUnwindSafe",
        "ProviderForceMode::EnergyWithWorkspaceAndNeutralitySortScratch {",
        "ptr::null_mut()",
        "commit_candidate(candidate, out_energy)",
        "alias_safety.get()",
    ):
        if token not in abi:
            fail("workspace-plus-neutrality hidden ABI drift: %s" % token)
    for forbidden in ("out_forces", "ParticleAssignmentScratch"):
        if forbidden in abi:
            fail(
                "workspace-plus-neutrality hidden ABI accepted forbidden scratch/output: %s"
                % forbidden
            )
    old_abi_symbol = "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1"
    if source.count('pub unsafe extern "C" fn %s(' % old_abi_symbol) != 1:
        fail("predecessor workspace-only hidden ABI was not preserved")
    for test_name in (
        "energy_workspace_and_neutrality_scratch_cold_warm_oom_and_interop_are_frozen",
        "energy_workspace_and_neutrality_scratch_growth_late_error_and_panic_restore_leases",
        "energy_workspace_and_neutrality_scratch_malformed_leased_and_full_capacity_aliases_fail_closed",
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
        "shared_descriptor",
        "forged_scratch",
        "forged_workspace",
        "capacity_tail_energy",
        "evaluate_energy_with_owner_workspace(",
        "evaluate_with_owner_reusable_storage(",
    ):
        if token not in source:
            fail("focused Rust ownership/transactionality anchor drift: %s" % token)


def require_native_contract(root: Path = ROOT) -> None:
    adapter = (root / ADAPTER_RELATIVE_PATH).read_text()
    body = source_region(
        adapter,
        "static bg_status evaluate_impl(",
        "\nbg_status evaluate(",
        "native Rust adapter",
    )
    triple = (
        "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_"
        "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1("
    )
    workspace_force = (
        "bg_rust_particle_mesh_reciprocal_"
        "evaluate_reusing_force_output_with_workspace_v1("
    )
    energy_workspace_neutrality = PRIVATE_SYMBOL + "("
    direct = "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1("
    transactional = "bg_rust_particle_mesh_reciprocal_evaluate_v1("
    for symbol in (
        triple,
        workspace_force,
        energy_workspace_neutrality,
        direct,
        transactional,
    ):
        if body.count(symbol) != 1:
            fail("adapter five-way call count drift: %s" % symbol)
    require_ordered_tokens(
        body,
        (
            "if (out_provider_force_source_result != nullptr) {",
            triple,
            "} else if (reuse_force_storage && compute_forces) {",
            workspace_force,
            "} else if (reuse_force_storage) {",
            energy_workspace_neutrality,
            "&active_provider_force_scratch->reciprocal_workspace",
            "&active_provider_force_scratch->neutrality_sort_scratch",
            "} else if (compute_forces) {",
            direct,
            "} else {",
            transactional,
            "const bg_status status = normalize_provider_status(raw_status);",
            "if (status != BG_STATUS_OK) {",
            "if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol)) {",
            "*out_evaluation = std::move(candidate);",
        ),
        "adapter five-way dispatch and commit",
    )
    if body.count("if (reuse_force_storage && provider_force_scratch == nullptr)") != 1:
        fail("adapter reusable owner null guard drift")
    energy_branch = source_region(
        body,
        "} else if (reuse_force_storage) {",
        "} else if (compute_forces) {",
        "adapter force-free workspace-plus-neutrality branch",
    )
    for forbidden in ("force_pointer", ".x.resize", ".y.resize", ".z.resize"):
        if forbidden in energy_branch:
            fail("force-free workspace-plus-neutrality branch touched force output: %s" % forbidden)
    old_energy_symbol = (
        "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1("
    )
    if old_energy_symbol in body:
        fail("adapter reusable-energy branch retained the predecessor workspace-only call")

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

    header = (root / PROVIDER_HEADER_RELATIVE_PATH).read_text()
    declaration = source_region(
        header,
        "%s(" % PRIVATE_SYMBOL,
        "\n\nint32_t\nbg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_and_neutrality_sort_scratch_v1",
        "private provider declaration",
    )
    for token in (
        "const bg_rust_particle_mesh_reciprocal_system_v1 *system",
        "const bg_rust_particle_mesh_reciprocal_model_v1 *model",
        "bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace",
        "bg_rust_particle_mesh_reciprocal_neutrality_sort_scratch_v1",
        "*neutrality_sort_scratch",
        "bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy",
        "bg_rust_particle_mesh_reciprocal_error_v1 *out_error",
    ):
        if token not in declaration:
            fail("private provider declaration drift: %s" % token)
    for forbidden in ("out_forces", "particle_assignment"):
        if forbidden in declaration:
            fail("private workspace-plus-neutrality declaration broadened: %s" % forbidden)
    old_declaration = (
        "int32_t bg_rust_particle_mesh_reciprocal_evaluate_energy_with_workspace_v1("
    )
    if header.count(old_declaration) != 1:
        fail("predecessor workspace-only private declaration drift")
    if header.count(
        "#define BG_RUST_PARTICLE_MESH_RECIPROCAL_PROVIDER_ABI_VERSION UINT32_C(1)"
    ) != 1:
        fail("private provider ABI version drift")


def require_test_contract(root: Path = ROOT) -> None:
    adapter_test = (root / ADAPTER_TEST_RELATIVE_PATH).read_text()
    for token in (
        "energy_workspace_calls",
        "energy_workspace_neutrality_calls",
        "verify_reusable_energy_workspace_branch_and_transactionality();",
        "verify_reusable_energy_requires_scratch_owner();",
        "require_only_energy_workspace_neutrality_route();",
        "fake_provider.energy_workspace_calls == 0U",
        "fake_provider.energy_workspace_neutrality_calls == 1U",
        "fake_provider.last_workspace == &scratch.reciprocal_workspace",
        "&scratch.neutrality_sort_scratch",
        "fake_provider.return_late_energy_numerical_error = true;",
        "require_same_snapshot(output, before);",
        "scratch.x == x && scratch.y == y && scratch.z == z",
        "std::memcmp(&scratch.particle_assignment_scratch, &assignment",
        PRIVATE_SYMBOL + "(",
    ):
        if token not in adapter_test:
            fail("native adapter route/commit test drift: %s" % token)
    composite_test = (root / COMPOSITE_TEST_RELATIVE_PATH).read_text()
    for token in (
        "stateful Rust force-free evaluation did not provision the reciprocal workspace",
        "stateful Rust force-free evaluation did not provision the neutrality-sort scratch",
        "stateful Rust force-free evaluation retained the wrong neutrality-sort payload",
        "stateful Rust force-free evaluation populated the particle-assignment scratch",
        "independent zero-step owners shared workspace or neutrality-sort storage",
        "warm zero-step integration replaced the owner reciprocal workspace",
        "warm zero-step integration replaced the owner neutrality-sort scratch",
        "stateful Rust forceful evaluation replaced or resized the zero-step reciprocal workspace",
        "stateful Rust forceful evaluation replaced, resized, or aliased the zero-step neutrality-sort scratch",
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
            fail("private workspace-plus-neutrality symbol leaked: %s" % relative)


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    normalized_doc = " ".join(doc.split())
    for token in (
        "stateful Rust force-free",
        "owner's reciprocal workspace and neutrality-sort scratch",
        PRIVATE_SYMBOL,
        "EnergyWithWorkspaceAndNeutralitySortScratch",
        "ForceStorageMode::Disabled",
        "whole backing capacity",
        "success-only",
        "allocation order remains neutrality sorting, call-local particle assignment, then reciprocal workspace preparation",
        "Workspace and neutrality payloads are derived scratch and are not transactional",
        "call-local particle-assignment allocation remains",
        "Force x/y/z and the owner particle-assignment descriptor are untouched",
        "not allocation-free",
        "fake provider is only a route-selection and commit-separation test double",
        "Rust provider itself is not sanitizer-instrumented",
        "No performance, acceleration, scientific-equivalence, molecular, HIP, or product claim",
        "external_reservation_provider_not_operational",
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
        "trigger_path_count": 162,
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
