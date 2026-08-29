#!/usr/bin/env python3
"""Verify final-SoA force recording for stateful particle-mesh Ewald dynamics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-combined-force-soa.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-"
    "combined-force-soa.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_combined_force_soa_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1_sources.json"
)
ARCHITECTURE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1.json"
)
ARCHITECTURE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1_sources.json"
)
INHERITED_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json"
)
INHERITED_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_sources/1.0.0"
)
PUBLIC_PROFILE_ID = (
    "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)
MINIMAL_RUST_TOOLCHAIN_INSTALL = (
    "rustup toolchain install 1.93.0 --profile minimal"
)
RUST_BOUNDARY_TOOLCHAIN_INSTALL = (
    f"{MINIMAL_RUST_TOOLCHAIN_INSTALL} --component rustfmt --component clippy"
)

PREDECESSOR = {
    "pull_request": 450,
    "reviewed_head": "b0e26a8b2eea995a6038a484894808387486ff9e",
    "merge_commit": "75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330",
    "merge_tree": "03ccd07339b71eafa435a9b2012d2ab6a863d4d9",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "cc7c92719b832c847f213ea02b9a46e75bfd7e79b291c28af59b24f5b0478d3f"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "c19ec3eb610bc07978b7cb96b0368043f9084a91d344c8515fa75140bb27c7f6"
    ),
    "source_manifest_entry_count": 226,
}
ARCHITECTURE_PREDECESSOR = {
    "pull_request": 451,
    "reviewed_head": "b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475",
    "merge_commit": "0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a",
    "merge_tree": "124539c1d14f5cbc0f3d91d231d6a40736f58f5a",
    "profile_path": ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "50c50ba44f9d3ff32358454d0d9f81f2619265fdaa5a3e9fe9194f22848685b7"
    ),
    "source_manifest_path": ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "348ab691558af31b398c653d0c6399bc30c651bc7cc911edb35aedcda2ec9032"
    ),
    "source_manifest_entry_count": 232,
}
INHERITED_PREDECESSOR = {
    "pull_request": 445,
    "reviewed_head": "801a85d56846c464b3a618ecacca867cd12a8c9f",
    "merge_commit": "c53f7993ec06c4ac04a4907b40f179d12fbe309a",
    "merge_tree": "2bb25b756b802671bcfc5f3ac95b26df3b284956",
    "profile_path": INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "32129a32d0b351ac265fda21906e707cc708c664241715b4d0d92fa3cc013b62"
    ),
    "source_manifest_path": INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "d428b3f18d26382fbb7e5e8a48f3a114eb953b8708bec77c4f00ec6c0d1bcc3f"
    ),
    "source_manifest_entry_count": 194,
}

EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)
IMPLEMENTATION_DELTA_PATHS = tuple(
    Path(path)
    for path in (
        "native/src/composite/particle_mesh_ewald_composite.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp",
        "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp",
        "native/tests/particle_mesh_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_evaluator.hpp",
    )
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
REQUIRED_TRIGGER_PATHS = (
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-force-scratch.yml",
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml",
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-parent-force-scratch.yml",
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-short-parent-force-scratch.yml",
    PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix(),
    WORKFLOW_RELATIVE_PATH.as_posix(),
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-force-scratch.yml",
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-backend-preflight.yml",
    "CMakeLists.txt",
    "include/betelgeuze/**",
    "native/**",
    "rust/**",
    "rust_engine_v2/Cargo.lock",
    "rust_engine_v2/Cargo.toml",
    INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1_sources.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1_sources.json",
    PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    PROFILE_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.md",
    DOC_RELATIVE_PATH.as_posix(),
    "tools/__init__.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py",
    VERIFIER_RELATIVE_PATH.as_posix(),
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_system_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_parent_force_scratch_v1.py",
    PREDECESSOR_UNIT_RELATIVE_PATH.as_posix(),
    UNIT_RELATIVE_PATH.as_posix(),
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
EXPECTED_TEST_SOURCE_SHA256 = (
    "d9a38e4a47060e733df326e514d458f522bbdb72812be742c7b046e3a6ac863c"
)
EXPECTED_PRODUCTION_SOURCE_SHA256 = {
    "particle_mesh_ewald_composite.cpp":
        "f848b22f2fb4ef1d65ebde766c899fb4ed3e68a2f5f9dea5a1e3cdbd441e51f3",
    "particle_mesh_ewald_composite_dynamics.cpp":
        "444b2dec3203a02c45cea8bd1bc4bf172c603fec813fbdf0bd08222131f81325",
    "particle_mesh_ewald_composite_evaluator.hpp":
        "badcc79414bff3999742977e8f8e4e9edeacf87986a9bd09858b270077272d1e",
}
EXPECTED_PREDECESSOR_WORKFLOW_SHA256 = (
    "1c253d59b84e4d44551ed237979cba6bba30878126888b0c464ff4e670ca971e"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "cbd8d721d44a48d85d00775db2a08646ac9a38ca076808a12f744af36d3b66ed"
)

RUST_BOUNDARY_COMMAND_STEP = "\n".join(
    (
        "      - name: Existing Rust regression, docs, and clean packages",
        "        run: |",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --test layout --test raw_smoke",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --lib particle_mesh_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --test particle_mesh_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --doc particle_mesh_ewald_composite_dynamics",
        "          cargo doc --manifest-path rust/Cargo.toml --locked --no-deps --package betelgeuze-sys --package betelgeuze-runtime",
        "          cargo fmt --manifest-path rust/Cargo.toml --all -- --check",
        "          cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --package betelgeuze-runtime --all-targets -- -D warnings",
        "          cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked --config 'patch.crates-io.betelgeuze-cpu-kernel.path=\"rust/cpu-kernel\"'",
        "          BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1 BETELGEUZE_V7_SOURCE_ROOT=\"$GITHUB_WORKSPACE\" cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked --config 'patch.crates-io.betelgeuze-sys.path=\"rust/betelgeuze-sys\"' --config 'patch.crates-io.betelgeuze-cpu-kernel.path=\"rust/cpu-kernel\"' --config 'patch.crates-io.betelgeuze-docking-search.path=\"rust/betelgeuze-docking-search\"' --config 'patch.crates-io.betelgeuze-reference-physics.path=\"rust/reference-physics\"' --config 'patch.crates-io.betelgeuze-reference-dynamics.path=\"rust/reference-dynamics\"'",
    )
) + "\n"

EXPECTED_IMMUTABLE_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 20
    env:
      PYTHONDONTWRITEBYTECODE: "1"
      PYTEST_DISABLE_PLUGIN_AUTOLOAD: "1"
    steps:
      - name: Check out exact evidence graph
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
        with:
          persist-credentials: false
          clean: true
          fetch-depth: 0
      - name: Materialize exact PR 451 architecture, PR 450 target, and PR 445 inherited final SoA
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a^{tree})" = "124539c1d14f5cbc0f3d91d231d6a40736f58f5a"
          git merge-base --is-ancestor 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a HEAD
          git fetch --no-tags --depth=1 origin refs/pull/451/head
          test "$(git rev-parse FETCH_HEAD)" = "b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "124539c1d14f5cbc0f3d91d231d6a40736f58f5a"
          test "$(git rev-parse 75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330^{tree})" = "03ccd07339b71eafa435a9b2012d2ab6a863d4d9"
          git merge-base --is-ancestor 75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a
          git fetch --no-tags --depth=1 origin refs/pull/450/head
          test "$(git rev-parse FETCH_HEAD)" = "b0e26a8b2eea995a6038a484894808387486ff9e"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "03ccd07339b71eafa435a9b2012d2ab6a863d4d9"
          test "$(git rev-parse c53f7993ec06c4ac04a4907b40f179d12fbe309a^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
          git merge-base --is-ancestor c53f7993ec06c4ac04a4907b40f179d12fbe309a 75d3a4e2b7ba5b0f1dcf99007358f6f2c47c7330
          git fetch --no-tags --depth=1 origin refs/pull/445/head
          test "$(git rev-parse FETCH_HEAD)" = "801a85d56846c464b3a618ecacca867cd12a8c9f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py
"""

EXPECTED_NATIVE_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    steps:
      - name: Check out native sources
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
        with: {persist-credentials: false, clean: true, fetch-depth: 1}
      - name: Select frozen Rust toolchain
        run: |
          rustup toolchain install 1.93.0 --profile minimal
          rustup override set 1.93.0
      - name: Synthetic release and sanitizer regressions
        run: |
          cmake -S . -B build/particle-mesh-ewald-combined-force-soa-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-combined-force-soa-release --target betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/particle-mesh-ewald-combined-force-soa-release -R '^betelgeuze_engine_(particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/particle-mesh-ewald-combined-force-soa-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/particle-mesh-ewald-combined-force-soa-sanitize --target betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/particle-mesh-ewald-combined-force-soa-sanitize -R '^betelgeuze_engine_particle_mesh_ewald_composite_dynamics$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/particle-mesh-ewald-combined-force-soa-cargo
    steps:
      - name: Check out Rust sources
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
        with: {persist-credentials: false, clean: true, fetch-depth: 1}
      - name: Select frozen Rust components
        run: |
          rustup toolchain install 1.93.0 --profile minimal --component rustfmt --component clippy
          rustup override set 1.93.0
""" + RUST_BOUNDARY_COMMAND_STEP

EXPECTED_MACOS_JOB_BODY = """    runs-on: macos-15
    timeout-minutes: 30
    steps:
      - name: Check out export sources
        uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7.0.0
        with: {persist-credentials: false, clean: true, fetch-depth: 1}
      - name: Select frozen Rust toolchain
        run: |
          rustup toolchain install 1.93.0 --profile minimal
          rustup override set 1.93.0
      - name: Exact export regression
        run: |
          cmake -S . -B build/particle-mesh-ewald-combined-force-soa-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-combined-force-soa-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/particle-mesh-ewald-combined-force-soa-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "combined-force-soa\n\n"
        "on:\n"
        "  pull_request:\n"
        "    paths:\n"
        f"{trigger_paths}"
        "  push:\n"
        '    branches: ["main"]\n'
        "    paths:\n"
        f"{trigger_paths}"
        "  workflow_dispatch:\n\n"
        "permissions:\n"
        "  contents: read\n\n"
        "concurrency:\n"
        "  group: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "combined-force-soa-${{ github.ref }}\n"
        "  cancel-in-progress: true\n\n"
        "env:\n"
        '  CUDA_VISIBLE_DEVICES: ""\n'
        '  HIP_VISIBLE_DEVICES: ""\n'
        '  ROCR_VISIBLE_DEVICES: ""\n\n'
        "jobs:\n"
    )
    return (
        preamble
        + "  immutable-evidence:\n"
        + EXPECTED_IMMUTABLE_JOB_BODY
        + "\n  native-linux:\n"
        + EXPECTED_NATIVE_JOB_BODY
        + "\n  rust-boundaries:\n"
        + EXPECTED_RUST_JOB_BODY
        + "\n  macos-export-boundary:\n"
        + EXPECTED_MACOS_JOB_BODY
    )


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_environment() -> dict[str, str]:
    return {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }


def git(
    *args: str,
    check: bool = True,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", *args],
        cwd=ROOT,
        env=_git_environment(),
        input=input_bytes,
        capture_output=True,
        check=check,
    )


def require_manifest_shape(raw: bytes, expected_count: int) -> dict:
    try:
        manifest = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("frozen predecessor manifest is invalid JSON") from error
    if type(manifest) is not dict or canonical_bytes(manifest) != raw:
        fail("frozen predecessor manifest is not canonical JSON")
    rows = manifest.get("files")
    if type(rows) is not list or len(rows) != expected_count:
        fail("frozen predecessor manifest count drift")
    paths: list[str] = []
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256"}:
            fail("frozen predecessor manifest row shape drift")
        path = row["path"]
        digest = row["sha256"]
        if (
            type(path) is not str
            or Path(path).is_absolute()
            or Path(path).as_posix() != path
            or ".." in Path(path).parts
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            fail("frozen predecessor manifest row value drift")
        paths.append(path)
    if paths != sorted(set(paths)):
        fail("frozen predecessor manifest paths are not sorted and unique")
    return manifest


def require_architecture_manifest_shape(raw: bytes, expected_count: int) -> dict:
    try:
        manifest = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("frozen architecture manifest is invalid JSON") from error
    if type(manifest) is not dict or canonical_bytes(manifest) != raw:
        fail("frozen architecture manifest is not canonical JSON")
    rows = manifest.get("files")
    if type(rows) is not list or len(rows) != expected_count:
        fail("frozen architecture manifest count drift")
    paths: list[str] = []
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256"}:
            fail("frozen architecture manifest row shape drift")
        path = row["path"]
        digest = row["sha256"]
        if (
            type(path) is not str
            or Path(path).is_absolute()
            or Path(path).as_posix() != path
            or ".." in Path(path).parts
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            fail("frozen architecture manifest row value drift")
        paths.append(path)
    if paths != sorted(set(paths)):
        fail("frozen architecture manifest paths are not sorted and unique")
    return manifest


def reviewed_head_tree_if_present(
    evidence: dict[str, object] = PREDECESSOR,
) -> str | None:
    reviewed = str(evidence["reviewed_head"])
    result = git(
        "cat-file",
        "--batch-check=%(objectname) %(objecttype)",
        check=False,
        input_bytes=f"{reviewed}\n".encode("ascii"),
    )
    if result.returncode != 0 or result.stderr:
        fail("optional reviewed-head object inspection failed")
    if result.stdout == f"{reviewed} missing\n".encode("ascii"):
        return None
    if result.stdout != f"{reviewed} commit\n".encode("ascii"):
        fail("locally present reviewed-head object is not the frozen commit")
    tree = git("show", "-s", "--format=%T", reviewed).stdout.strip().decode()
    if re.fullmatch(r"[0-9a-f]{40}", tree) is None:
        fail("locally present reviewed-head tree identity is invalid")
    return tree


def require_architecture_predecessor() -> dict:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("architecture predecessor merge is not a commit")
    if git("rev-parse", f"{merge}^{{commit}}").stdout.strip().decode() != merge:
        fail("architecture predecessor merge identity drift")
    tree = git("rev-parse", f"{merge}^{{tree}}").stdout.strip().decode()
    if tree != ARCHITECTURE_PREDECESSOR["merge_tree"]:
        fail("architecture predecessor merge tree drift")
    if (
        git(
            "merge-base",
            "--is-ancestor",
            PREDECESSOR["merge_commit"],
            merge,
            check=False,
        ).returncode
        != 0
    ):
        fail("target predecessor is not an ancestor of the architecture predecessor")
    head = git("rev-parse", "HEAD^{commit}").stdout.strip().decode()
    if git("merge-base", "--is-ancestor", merge, head, check=False).returncode != 0:
        fail("HEAD does not descend from the frozen architecture predecessor")

    profile_raw = git(
        "show", f"{merge}:{ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix()}"
    ).stdout
    manifest_raw = git(
        "show", f"{merge}:{ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(profile_raw) != ARCHITECTURE_PREDECESSOR["profile_sha256"]:
        fail("frozen architecture predecessor profile digest drift")
    if sha(manifest_raw) != ARCHITECTURE_PREDECESSOR["source_manifest_sha256"]:
        fail("frozen architecture predecessor manifest digest drift")
    if canonical_bytes(json.loads(profile_raw)) != profile_raw:
        fail("frozen architecture predecessor profile is not canonical JSON")
    architecture_profile = json.loads(profile_raw)
    if architecture_profile.get("architecture_predecessor") != PREDECESSOR:
        fail("architecture predecessor no longer binds the direct target predecessor")
    manifest = require_architecture_manifest_shape(
        manifest_raw,
        ARCHITECTURE_PREDECESSOR["source_manifest_entry_count"],
    )
    if (ROOT / ARCHITECTURE_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out architecture predecessor profile differs from frozen merge")
    if (ROOT / ARCHITECTURE_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out architecture predecessor manifest differs from frozen merge")
    reviewed_tree = reviewed_head_tree_if_present(ARCHITECTURE_PREDECESSOR)
    if (
        reviewed_tree is not None
        and reviewed_tree != ARCHITECTURE_PREDECESSOR["merge_tree"]
    ):
        fail("architecture predecessor reviewed-head tree drift")
    return manifest


def require_predecessor() -> dict:
    merge = PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("predecessor merge is not a commit")
    if git("rev-parse", f"{merge}^{{commit}}").stdout.strip().decode() != merge:
        fail("predecessor merge identity drift")
    tree = git("rev-parse", f"{merge}^{{tree}}").stdout.strip().decode()
    if tree != PREDECESSOR["merge_tree"]:
        fail("predecessor merge tree drift")
    if (
        git(
            "merge-base",
            "--is-ancestor",
            merge,
            ARCHITECTURE_PREDECESSOR["merge_commit"],
            check=False,
        ).returncode
        != 0
    ):
        fail("target predecessor is not an ancestor of the architecture predecessor")

    profile_raw = git(
        "show", f"{merge}:{PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix()}"
    ).stdout
    manifest_raw = git(
        "show", f"{merge}:{PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(profile_raw) != PREDECESSOR["profile_sha256"]:
        fail("frozen predecessor profile digest drift")
    if sha(manifest_raw) != PREDECESSOR["source_manifest_sha256"]:
        fail("frozen predecessor manifest digest drift")
    profile = json.loads(profile_raw)
    if canonical_bytes(profile) != profile_raw:
        fail("frozen predecessor profile is not canonical JSON")
    if profile.get("inherited_force_scratch_predecessor") != INHERITED_PREDECESSOR:
        fail("target predecessor no longer binds the inherited final-SoA predecessor")
    manifest = require_manifest_shape(
        manifest_raw, PREDECESSOR["source_manifest_entry_count"]
    )
    if (ROOT / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out predecessor profile differs from frozen merge")
    if (ROOT / PREDECESSOR_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out predecessor manifest differs from frozen merge")
    reviewed_tree = reviewed_head_tree_if_present(PREDECESSOR)
    if reviewed_tree is not None and reviewed_tree != PREDECESSOR["merge_tree"]:
        fail("reviewed-head tree drift")
    require_inherited_predecessor()
    require_architecture_predecessor()
    return manifest


def require_inherited_predecessor() -> dict:
    merge = INHERITED_PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("inherited predecessor merge is not a commit")
    if git("rev-parse", f"{merge}^{{commit}}").stdout.strip().decode() != merge:
        fail("inherited predecessor merge identity drift")
    if (
        git("rev-parse", f"{merge}^{{tree}}").stdout.strip().decode()
        != INHERITED_PREDECESSOR["merge_tree"]
    ):
        fail("inherited predecessor merge tree drift")
    if (
        git(
            "merge-base",
            "--is-ancestor",
            merge,
            PREDECESSOR["merge_commit"],
            check=False,
        ).returncode
        != 0
    ):
        fail("inherited final-SoA predecessor is not an ancestor of target")
    profile_raw = git(
        "show", f"{merge}:{INHERITED_PROFILE_RELATIVE_PATH.as_posix()}"
    ).stdout
    manifest_raw = git(
        "show", f"{merge}:{INHERITED_MANIFEST_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(profile_raw) != INHERITED_PREDECESSOR["profile_sha256"]:
        fail("inherited predecessor profile digest drift")
    if sha(manifest_raw) != INHERITED_PREDECESSOR["source_manifest_sha256"]:
        fail("inherited predecessor manifest digest drift")
    if canonical_bytes(json.loads(profile_raw)) != profile_raw:
        fail("inherited predecessor profile is not canonical JSON")
    manifest = require_manifest_shape(
        manifest_raw, INHERITED_PREDECESSOR["source_manifest_entry_count"]
    )
    if (ROOT / INHERITED_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out inherited predecessor profile differs from frozen merge")
    if (ROOT / INHERITED_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out inherited predecessor manifest differs from frozen merge")
    reviewed_tree = reviewed_head_tree_if_present(INHERITED_PREDECESSOR)
    if (
        reviewed_tree is not None
        and reviewed_tree != INHERITED_PREDECESSOR["merge_tree"]
    ):
        fail("inherited predecessor reviewed-head tree drift")
    return manifest


def current_delta_paths() -> tuple[Path, ...]:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    tracked = git("diff", "--name-only", merge, "--").stdout.decode().splitlines()
    untracked = git(
        "ls-files", "--others", "--exclude-standard"
    ).stdout.decode().splitlines()
    return tuple(
        sorted({Path(path) for path in tracked + untracked}, key=lambda p: p.as_posix())
    )


def discover_source_paths(root: Path = ROOT) -> list[Path]:
    require_predecessor()
    architecture_manifest = require_architecture_predecessor()
    paths = {Path(row["path"]) for row in architecture_manifest["files"]}
    paths.update(IMPLEMENTATION_DELTA_PATHS)
    paths.update(
        (
            PREDECESSOR_PROFILE_RELATIVE_PATH,
            PREDECESSOR_MANIFEST_RELATIVE_PATH,
            ARCHITECTURE_PROFILE_RELATIVE_PATH,
            ARCHITECTURE_MANIFEST_RELATIVE_PATH,
            INHERITED_PROFILE_RELATIVE_PATH,
            INHERITED_MANIFEST_RELATIVE_PATH,
            PREDECESSOR_WORKFLOW_RELATIVE_PATH,
            PREDECESSOR_UNIT_RELATIVE_PATH,
            WORKFLOW_RELATIVE_PATH,
            DOC_RELATIVE_PATH,
            UNIT_RELATIVE_PATH,
            VERIFIER_RELATIVE_PATH,
        )
    )
    paths.difference_update(
        (PROFILE_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH)
    )
    missing = [path.as_posix() for path in paths if not (root / path).is_file()]
    if missing:
        fail(f"missing source paths: {missing}")
    return sorted(paths, key=lambda path: path.as_posix())


def build_source_manifest(root: Path = ROOT) -> dict:
    rows = [
        {"path": path.as_posix(), "sha256": sha((root / path).read_bytes())}
        for path in discover_source_paths(root)
    ]
    return {
        "schema_id": SOURCE_SCHEMA_ID,
        "scope": (
            "particle_mesh_ewald_composite_dynamics_stateful_combined_force_soa_"
            "current_sources_tests_evidence_target_architecture_and_inherited_predecessors"
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
            "combined_force_soa_development_v1"
        ),
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "architecture_predecessor": dict(ARCHITECTURE_PREDECESSOR),
        "inherited_final_soa_predecessor": dict(INHERITED_PREDECESSOR),
        "abi": {
            "public_profile_id": PUBLIC_PROFILE_ID,
            "public_symbol_count": 13,
            "public_symbols": list(PUBLIC_SYMBOLS),
            "checkpoint_magic": "BGPME001",
            "checkpoint_header_size_bytes": 104,
            "abi_changed": False,
            "checkpoint_format_changed": False,
        },
        "implementation": {
            "stateful_force_output_pointer_required_iff_stateful_forceful": True,
            "successful_stateful_forceful_direct_final_soa_recording": True,
            "successful_stateful_forceful_combined_aos_materialization_eliminated": True,
            "successful_stateful_forceful_combined_aos_to_soa_copy_eliminated": True,
            "stateless_combined_aos_path_preserved": True,
            "stateful_force_free_path_preserved": True,
            "final_soa_force_storage_reused": True,
            "short_system_scratch_contract_preserved": True,
            "short_parent_force_scratch_contract_preserved": True,
            "short_parent_output_alias_rejected": True,
            "parent_shape_and_component_finiteness_checked_before_final_soa_write": True,
            "final_soa_resize_after_all_parent_validation": True,
            "late_direct_local_failure_precedes_final_soa_write": True,
            "final_soa_scratch_is_derived_non_authoritative": True,
            "final_soa_scratch_serialized_in_checkpoint": False,
            "final_soa_scratch_bound_into_static_fingerprint": False,
            "late_direct_local_failure_last_successful_final_soa_bits_preserved": True,
            "reciprocal_failure_storage_retention_claimed": False,
            "allocation_failure_storage_identity_claimed": False,
            "resize_failure_storage_retention_claimed": False,
            "unconditional_failure_storage_retention_claimed": False,
            "upstream_failure_storage_retention_claimed": False,
            "universal_failure_storage_retention_claimed": False,
            "all_failure_path_storage_retention_claimed": False,
            "explicit_cpp_cpu_reference_lane": True,
            "explicit_rust_cpu_lane": True,
            "test_only_owner_introspection_not_exported": True,
            "allocation_free_claimed": False,
            "timing_claimed": False,
            "performance_claimed": False,
            "acceleration_claimed": False,
            "cross_lane_bit_parity_claimed": False,
            "fixed64_cpu_v7_qualification_invoked": False,
            "hip_device_execution_invoked": False,
            "molecular_execution_invoked": False,
            "source_manifest_entry_count": len(manifest["files"]),
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
        },
        "validation": {
            "canonical_vendor_byte_identity": True,
            "exact_public_symbol_surfaces": True,
            "synthetic_release_and_asan_ubsan": True,
            "both_explicit_cpu_lanes": True,
            "three_final_soa_channels_pointer_capacity_and_size_retention": True,
            "same_lane_reserved_peer_and_stateless_force_bit_identity": True,
            "initial_create_and_zero_step_final_soa_stability": True,
            "checkpoint_a_to_b_load_a_preserves_stale_final_soa": True,
            "zero_step_preserves_stale_final_soa": True,
            "forceful_post_load_resynchronizes_final_soa": True,
            "repeated_late_direct_local_failure_authoritative_transactionality": True,
            "late_direct_local_failure_last_successful_final_soa_bits": True,
            "short_parent_final_soa_alias_rejected": True,
            "rust_raw_safe_docs_fmt_clippy": True,
            "clean_rust_packages": True,
            "git_object_probes_lazy_fetch_disabled": True,
            "reviewed_head_optional_locally": True,
            "workflow_architecture_target_and_inherited_heads_explicitly_fetched": True,
        },
        "authority": dict(AUTHORITY),
        "operational_boundary": {
            "blockers": list(BLOCKERS),
            "unresolved_operational_decisions": 32,
        },
    }


def is_dynamics_symbol(symbol: str) -> bool:
    return (
        symbol.startswith("bg_particle_mesh_ewald_composite_dynamics_")
        or symbol.startswith("bg_particle_mesh_ewald_composite_simulation_v1_")
        or symbol == "bg_context_integrate_particle_mesh_ewald_composite_v1"
    )


def extract_public_symbol_surfaces(
    root: Path = ROOT,
) -> dict[str, tuple[str, ...]]:
    header = (
        root / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h"
    ).read_text()
    dynamics = (
        root / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    checkpoint = (
        root / "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp"
    ).read_text()
    version_map = (root / "native/betelgeuze_engine.map").read_text()
    exports = (root / "native/betelgeuze_engine.exports").read_text()
    export_test = (root / "native/tests/check_exports.cmake").read_text()
    sys_source = (root / "rust/betelgeuze-sys/src/lib.rs").read_text()
    node = re.search(
        r"BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_1\.0 \{\n"
        r"[ \t]+global:\n(?P<body>.*?)\n"
        r"\} BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_1\.0;",
        version_map,
        re.DOTALL,
    )
    if node is None:
        fail("exact particle-mesh Ewald composite-dynamics ELF node or parent changed")
    export_block = re.search(
        r"set\(particle_mesh_ewald_composite_dynamics_v1_symbols\n"
        r"(?P<body>.*?)\n\)",
        export_test,
        re.DOTALL,
    )
    if export_block is None:
        fail("export regression particle-mesh Ewald dynamics group missing")
    mapping_tokens = (
        'list(FIND particle_mesh_ewald_composite_dynamics_v1_symbols "${unversioned}" particle_mesh_ewald_composite_dynamics_v1_index)',
        'set(expected_version "BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_1.0")',
    )
    if any(token not in export_test for token in mapping_tokens):
        fail("export regression particle-mesh Ewald dynamics version mapping changed")
    predicate = lambda values: tuple(
        value for value in values if is_dynamics_symbol(value)
    )
    return {
        "header": predicate(re.findall(r"\b(bg_[a-z0-9_]+)\s*\(", header)),
        "native": predicate(
            re.findall(
                r'extern "C" BG_API[^\n]*\n(bg_[a-z0-9_]+)\s*\(',
                dynamics + "\n" + checkpoint,
            )
        ),
        "linux_map": tuple(
            re.findall(
                r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$",
                node.group("body"),
            )
        ),
        "darwin_exports": predicate(
            line[1:] for line in exports.splitlines() if line.startswith("_")
        ),
        "check_exports": tuple(
            re.findall(
                r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+)[ \t]*$",
                export_block.group("body"),
            )
        ),
        "rust_sys": predicate(
            re.findall(r"\bpub fn (bg_[a-z0-9_]+)\s*\(", sys_source)
        ),
    }


def require_exact_public_symbols(root: Path = ROOT) -> None:
    if len(PUBLIC_SYMBOLS) != 13 or len(set(PUBLIC_SYMBOLS)) != 13:
        fail("particle-mesh Ewald composite-dynamics ABI symbol constant changed")
    for surface, symbols in extract_public_symbol_surfaces(root).items():
        if symbols != PUBLIC_SYMBOLS:
            fail(f"particle-mesh Ewald composite-dynamics public symbol set changed: {surface}")


def job_body(workflow: str, expected_name: str) -> str:
    headers = list(
        re.finditer(
            r'(?m)^  (?P<name>"[^"]+"|[A-Za-z0-9_-]+):[ \t]*(?:#.*)?$',
            workflow,
        )
    )
    matches = [
        (index, match)
        for index, match in enumerate(headers)
        if match.group("name").strip('"') == expected_name
    ]
    if len(matches) != 1:
        fail(f"workflow job header drift: {expected_name}")
    index, match = matches[0]
    end = headers[index + 1].start() if index + 1 < len(headers) else len(workflow)
    return workflow[match.end() + 1 : end]


def extract_run_commands(workflow: str) -> str:
    commands: list[str] = []
    in_run = False
    run_indent = 0
    for line in workflow.splitlines():
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if stripped.startswith("run:"):
            in_run = True
            run_indent = indent
            commands.append(stripped[4:])
            continue
        if in_run and stripped and indent <= run_indent:
            in_run = False
        if in_run:
            commands.append(stripped)
    return "\n".join(commands)


def require_workflow_contract(workflow: str) -> None:
    permission_headers = re.findall(
        r"(?m)^[ \t]*permissions:[ \t]*(?:#.*)?$", workflow
    )
    if (
        len(permission_headers) != 1
        or workflow.count("permissions:") != 1
        or workflow.count("permissions:\n  contents: read\n\nconcurrency:") != 1
        or re.search(
            r"(?m)^[ \t]+permissions:[ \t]*(?:#.*)?$", workflow
        )
        is not None
    ):
        fail("workflow must have exactly one global contents: read permission")
    if "write-all" in workflow or re.search(
        r"\b(?:actions|checks|contents|deployments|id-token|issues|packages|"
        r"pull-requests|security-events|statuses):\s*write\b",
        workflow,
    ):
        fail("workflow write permission is forbidden")
    if any(
        token in workflow
        for token in ("pull_request_target:", "workflow_run:", "self-hosted")
    ):
        fail("privileged workflow trigger or runner is forbidden")
    if re.search(
        r"(?m)^[ \t]*(?:if|continue-on-error|defaults):[ \t]*", workflow
    ):
        fail("conditional, continue-on-error, and run-default bypasses are forbidden")

    cpu_environment = (
        'env:\n  CUDA_VISIBLE_DEVICES: ""\n  HIP_VISIBLE_DEVICES: ""\n'
        '  ROCR_VISIBLE_DEVICES: ""\n\njobs:'
    )
    if workflow.count(cpu_environment) != 1:
        fail("workflow global CPU-only environment changed")
    for name in ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"):
        if workflow.count(name) != 1 or workflow.count(f'{name}: ""') != 1:
            fail(f"workflow must set global empty {name} exactly once")

    pull_match = re.search(
        r"^  pull_request:\n(?P<body>.*?)^  push:\n",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    push_match = re.search(
        r"^  push:\n(?P<body>.*?)^  workflow_dispatch:\n",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    if pull_match is None or push_match is None:
        fail("workflow trigger structure changed")
    expected_paths = sorted(REQUIRED_TRIGGER_PATHS)
    for label, match in (("pull_request", pull_match), ("push", push_match)):
        body = match.group("body")
        if "paths-ignore:" in body or body.count("    paths:\n") != 1:
            fail(f"workflow {label} must contain exactly one paths key")
        shape = (
            r'\A    paths:\n(?P<paths>(?:      - "[^"]+"\n)+)\Z'
            if label == "pull_request"
            else r'\A    branches: \["main"\]\n    paths:\n'
            r'(?P<paths>(?:      - "[^"]+"\n)+)\Z'
        )
        structured = re.fullmatch(shape, body)
        if structured is None:
            fail(f"workflow {label} path trigger structure drift")
        observed = re.findall(
            r'^      - "([^"]+)"$', structured.group("paths"), re.MULTILINE
        )
        if len(observed) != len(set(observed)) or sorted(observed) != expected_paths:
            fail(f"workflow {label} path trigger set drift")

    uses = re.findall(
        r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", workflow, re.MULTILINE
    )
    if uses != [PINNED_CHECKOUT_ACTION] * 4:
        fail("workflow actions must be exactly four pinned checkout uses")

    installs = [
        line.strip()
        for line in re.findall(r"(?m)^\s*rustup toolchain install .+$", workflow)
    ]
    if installs != [
        MINIMAL_RUST_TOOLCHAIN_INSTALL,
        RUST_BOUNDARY_TOOLCHAIN_INSTALL,
        MINIMAL_RUST_TOOLCHAIN_INSTALL,
    ]:
        fail("workflow Rust toolchain/component installation drift")

    native_body = job_body(workflow, "native-linux")
    rust_body = job_body(workflow, "rust-boundaries")
    macos_body = job_body(workflow, "macos-export-boundary")
    immutable_body = job_body(workflow, "immutable-evidence")
    jobs_region = workflow.split("\njobs:\n", 1)
    if len(jobs_region) != 2:
        fail("workflow jobs mapping drift")
    observed_jobs = [
        match.group("name").strip('"')
        for match in re.finditer(
            r'(?m)^  (?P<name>"[^"]+"|[A-Za-z0-9_-]+):[ \t]*(?:#.*)?$',
            jobs_region[1],
        )
    ]
    if observed_jobs != [
        "immutable-evidence",
        "native-linux",
        "rust-boundaries",
        "macos-export-boundary",
    ]:
        fail("workflow job set or ordering drift")
    minimal_step = (
        "      - name: Select frozen Rust toolchain\n"
        "        run: |\n"
        f"          {MINIMAL_RUST_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    rust_step = (
        "      - name: Select frozen Rust components\n"
        "        run: |\n"
        f"          {RUST_BOUNDARY_TOOLCHAIN_INSTALL}\n"
        "          rustup override set 1.93.0\n"
    )
    if native_body.count(minimal_step) != 1 or macos_body.count(minimal_step) != 1:
        fail("native and macOS jobs must own their minimal Rust toolchain steps")
    if rust_body.count(rust_step) != 1:
        fail("rust-boundaries must own the exact component installation step")
    command_name = (
        "      - name: Existing Rust regression, docs, and clean packages\n"
    )
    if rust_body.count(command_name) != 1:
        fail("rust-boundaries must contain exactly one named command step")
    if rust_body.count(rust_step + RUST_BOUNDARY_COMMAND_STEP) != 1:
        fail("Rust components must immediately precede the exact command step")

    if workflow.count("cmake -S . -B ") != 3:
        fail("workflow must contain exactly three CMake configurations")
    if (
        workflow.count("DBG_ENABLE_HIP=OFF") != 3
        or workflow.count("DBG_ENABLE_HIP_SAFE=OFF") != 3
        or "DBG_ENABLE_HIP=ON" in workflow
        or "DBG_ENABLE_HIP_SAFE=ON" in workflow
    ):
        fail("every CMake configuration must disable both HIP modes")
    configurations = re.findall(
        r"(?ms)^\s*cmake -S \. -B .*?(?=^\s*cmake --build )", workflow
    )
    if len(configurations) != 3:
        fail("workflow CMake configure-to-build structure drift")
    for configuration in configurations:
        if (
            configuration.count("DBG_ENABLE_HIP=OFF") != 1
            or configuration.count("DBG_ENABLE_HIP_SAFE=OFF") != 1
        ):
            fail("each CMake configuration must independently disable both HIP modes")

    required = (
        "pull_request:",
        "push:",
        "workflow_dispatch:",
        'branches: ["main"]',
        "refs/pull/451/head",
        ARCHITECTURE_PREDECESSOR["reviewed_head"],
        ARCHITECTURE_PREDECESSOR["merge_commit"],
        ARCHITECTURE_PREDECESSOR["merge_tree"],
        "refs/pull/450/head",
        PREDECESSOR["reviewed_head"],
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        "refs/pull/445/head",
        INHERITED_PREDECESSOR["reviewed_head"],
        INHERITED_PREDECESSOR["merge_commit"],
        INHERITED_PREDECESSOR["merge_tree"],
        "pytest==8.3.5",
        "ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1",
        "cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked",
        "cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        'BETELGEUZE_V7_SOURCE_ROOT="$GITHUB_WORKSPACE"',
        "^betelgeuze_engine_(particle_mesh_ewald_composite_dynamics|export_allowlist)$",
        "^betelgeuze_engine_particle_mesh_ewald_composite_dynamics$",
        "^betelgeuze_engine_export_allowlist$",
    )
    for token in required:
        if token not in workflow:
            fail(f"workflow missing {token}")

    command_text = extract_run_commands(workflow).lower()
    forbidden_commands = (
        "--refresh",
        "bg_require_hip_device",
        "qualification",
        "molecular",
        "benchmark",
        "supervisor",
        "reservation",
        "hipcc",
        "rocminfo",
    )
    if any(token in command_text for token in forbidden_commands):
        fail("workflow contains a forbidden execution token")
    if "--allow-dirty" in command_text:
        fail("dirty Rust package validation is forbidden")
    for package in (
        "betelgeuze-sys",
        "betelgeuze-cpu-kernel",
        "betelgeuze-docking-search",
        "betelgeuze-reference-physics",
        "betelgeuze-reference-dynamics",
    ):
        expected = 2 if package == "betelgeuze-cpu-kernel" else 1
        if command_text.count(f"patch.crates-io.{package}.path") != expected:
            fail(f"workflow package patch count drift: {package}")

    expected_bodies = {
        "immutable-evidence": EXPECTED_IMMUTABLE_JOB_BODY,
        "native-linux": EXPECTED_NATIVE_JOB_BODY,
        "rust-boundaries": EXPECTED_RUST_JOB_BODY,
        "macos-export-boundary": EXPECTED_MACOS_JOB_BODY,
    }
    observed_bodies = {
        "immutable-evidence": immutable_body,
        "native-linux": native_body,
        "rust-boundaries": rust_body,
        "macos-export-boundary": macos_body,
    }
    for name, expected_body in expected_bodies.items():
        if observed_bodies[name].rstrip() != expected_body.rstrip():
            fail(f"workflow exact job body drift: {name}")
    if workflow != expected_workflow_document():
        fail("workflow exact document drift")


def expected_frozen_predecessor_workflow(frozen: str) -> str:
    old_materialize = (
        "      - name: Materialize exact PR 450 architecture, PR 449 target, "
        "and PR 446 inherited final SoA\n"
    )
    old_verify = "      - name: Verify bounded successor evidence\n"
    native_boundary = "\n  native-linux:\n"
    if (
        frozen.count(old_materialize) != 1
        or frozen.count(old_verify) != 1
        or frozen.count(native_boundary) != 1
    ):
        fail("frozen predecessor workflow shape drift")
    materialize_start = frozen.index(old_materialize)
    native_start = frozen.index(native_boundary, materialize_start)
    if frozen.index(old_verify, materialize_start, native_start) < materialize_start:
        fail("frozen predecessor workflow verification order drift")
    replacement = """      - name: Materialize exact PR 451 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a^{tree})" = "124539c1d14f5cbc0f3d91d231d6a40736f58f5a"
          git merge-base --is-ancestor 0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a HEAD
          git fetch --no-tags --depth=1 origin refs/pull/451/head
          test "$(git rev-parse FETCH_HEAD)" = "b09f1dd125e1bb6aaf255cc2f3fb737ca4d9f475"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "124539c1d14f5cbc0f3d91d231d6a40736f58f5a"
      - name: Verify exact frozen PR 451 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=0d1e5fa1d2923139f0d070d5ec09ed29959cbc2a
          current_sha="$(git rev-parse HEAD)"
          git checkout --detach --quiet "$frozen"
          trap 'git checkout --detach --quiet "$current_sha"' EXIT
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py
          git checkout --detach --quiet "$current_sha"
          trap - EXIT
          test "$(git rev-parse HEAD)" = "$current_sha"
"""
    expected = frozen[:materialize_start] + replacement + frozen[native_start:]
    successor_pairs = (
        (PREDECESSOR_WORKFLOW_RELATIVE_PATH, WORKFLOW_RELATIVE_PATH),
        (ARCHITECTURE_PROFILE_RELATIVE_PATH, PROFILE_RELATIVE_PATH),
        (ARCHITECTURE_MANIFEST_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH),
        (Path("docs/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.md"), DOC_RELATIVE_PATH),
        (Path("tools/verify_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py"), VERIFIER_RELATIVE_PATH),
        (PREDECESSOR_UNIT_RELATIVE_PATH, UNIT_RELATIVE_PATH),
    )
    for predecessor, successor in successor_pairs:
        old = f'      - "{predecessor.as_posix()}"\n'
        new = old + f'      - "{successor.as_posix()}"\n'
        if expected.count(old) != 2:
            fail("frozen predecessor workflow successor trigger drift")
        expected = expected.replace(old, new)
    return expected


def require_predecessor_workflow_freeze(root: Path = ROOT) -> None:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", f"{merge}:{PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_WORKFLOW_SHA256:
        fail("pristine predecessor workflow digest drift")
    frozen = frozen_raw.decode()
    expected = expected_frozen_predecessor_workflow(frozen)
    current = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    if current != expected:
        fail("predecessor workflow freeze drift")


def expected_frozen_predecessor_unit(frozen: str) -> str:
    anchor = "ROOT = Path(__file__).resolve().parents[2]\n"
    addition = """PARTICLE_MESH_EWALD_COMBINED_FORCE_SOA_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PARTICLE_MESH_EWALD_COMBINED_FORCE_SOA_EVIDENCE_PRESENT,
    reason=(
        "direct Ewald composite dynamics combined-force SoA evidence is verified "
        "from its exact frozen object after particle-mesh Ewald combined-force SoA "
        "evidence is present"
    ),
)
"""
    if frozen.count(anchor) != 1:
        fail("frozen predecessor unit insertion point drift")
    return frozen.replace(anchor, anchor + addition, 1)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", f"{merge}:{PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_UNIT_SHA256:
        fail("pristine predecessor unit digest drift")
    frozen = frozen_raw.decode()
    expected = expected_frozen_predecessor_unit(frozen)
    current = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if current != expected:
        fail("predecessor unit freeze drift")


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail(f"frozen {label} transformation point drift")
    return source.replace(old, new, 1)


def expected_particle_mesh_ewald_source(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    bool compute_forces,
""",
        """    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    cpu::Evaluation *stateful_force_output,
    bool compute_forces,
""",
        "stateful final-SoA output parameter",
    )
    source = replace_exact(
        source,
        """    if ((short_parent_evaluation_scratch != nullptr) != stateful_scratch ||
        (inout_rust_cpu_forcefield_validated != nullptr) !=
            stateful_scratch) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite stateful scratch and validation-cache pointers must be all null or all non-null");
    }

    bg_system local_short_system;
""",
        """    if ((short_parent_evaluation_scratch != nullptr) != stateful_scratch ||
        (inout_rust_cpu_forcefield_validated != nullptr) !=
            stateful_scratch) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite stateful scratch and validation-cache pointers must be all null or all non-null");
    }
    const bool requires_stateful_force_output =
        stateful_scratch && compute_forces;
    if ((stateful_force_output != nullptr) !=
        requires_stateful_force_output) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite stateful force output must be non-null exactly for force-producing stateful evaluation");
    }
    if (stateful_force_output == short_parent_evaluation_scratch &&
        stateful_force_output != nullptr) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "particle-mesh composite final force output must not alias short-parent force scratch");
    }

    bg_system local_short_system;
""",
        "stateful final-SoA pointer matrix and alias guard",
    )
    source = replace_exact(
        source,
        """    Evaluation candidate;
    candidate.short_harmonic_bond =
        short_result.energy.harmonic_bond_kcal_per_mol;
    candidate.short_harmonic_angle =
        short_result.energy.harmonic_angle_kcal_per_mol;
    candidate.short_periodic_torsion =
        short_result.energy.periodic_torsion_kcal_per_mol;
    candidate.short_lennard_jones =
        short_result.energy.lennard_jones_kcal_per_mol;
    candidate.short_coulomb =
        short_result.energy.coulomb_kcal_per_mol;
    candidate.short_total = short_result.energy.total_kcal_per_mol;
    candidate.pme_real_space = direct_evaluation.energy.real_space;
    candidate.pme_reciprocal_space =
        reciprocal_evaluation.reciprocal_space_kcal_per_mol;
    candidate.pme_self = direct_evaluation.energy.self;
    candidate.pme_pair_correction =
        direct_evaluation.energy.pair_correction;
    candidate.pme_total =
        ((candidate.pme_real_space + candidate.pme_reciprocal_space) +
         candidate.pme_self) +
        candidate.pme_pair_correction;
    candidate.total = candidate.short_total + candidate.pme_total;
    if (!std::isfinite(candidate.total)) {
        commit_error(
            out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
            "particle-mesh Ewald composite total energy is not finite");
        return BG_STATUS_NUMERICAL_ERROR;
    }
    if (compute_forces) {
        candidate.forces.resize(atom_count);
        for (std::size_t atom = 0U; atom < atom_count; ++atom) {
            const std::array<double, 3> pme_force{{
                direct_evaluation.forces[atom][0] +
                    reciprocal_evaluation.forces[atom][0],
                direct_evaluation.forces[atom][1] +
                    reciprocal_evaluation.forces[atom][1],
                direct_evaluation.forces[atom][2] +
                    reciprocal_evaluation.forces[atom][2],
            }};
            candidate.forces[atom] = {{
                short_result.force_x[atom] + pme_force[0],
                short_result.force_y[atom] + pme_force[1],
                short_result.force_z[atom] + pme_force[2],
            }};
            if (std::any_of(
                    candidate.forces[atom].begin(),
                    candidate.forces[atom].end(),
                    [](double value) { return !std::isfinite(value); })) {
                commit_error(
                    out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
                    "particle-mesh Ewald composite force is not finite");
                return BG_STATUS_NUMERICAL_ERROR;
            }
        }
    }
""",
        """    Evaluation candidate;
    candidate.short_harmonic_bond =
        short_result.energy.harmonic_bond_kcal_per_mol;
    candidate.short_harmonic_angle =
        short_result.energy.harmonic_angle_kcal_per_mol;
    candidate.short_periodic_torsion =
        short_result.energy.periodic_torsion_kcal_per_mol;
    candidate.short_lennard_jones =
        short_result.energy.lennard_jones_kcal_per_mol;
    candidate.short_coulomb =
        short_result.energy.coulomb_kcal_per_mol;
    candidate.short_total = short_result.energy.total_kcal_per_mol;
    candidate.pme_real_space = direct_evaluation.energy.real_space;
    candidate.pme_reciprocal_space =
        reciprocal_evaluation.reciprocal_space_kcal_per_mol;
    candidate.pme_self = direct_evaluation.energy.self;
    candidate.pme_pair_correction =
        direct_evaluation.energy.pair_correction;
    candidate.pme_total =
        ((candidate.pme_real_space + candidate.pme_reciprocal_space) +
         candidate.pme_self) +
        candidate.pme_pair_correction;
    candidate.total = candidate.short_total + candidate.pme_total;
    if (!std::isfinite(candidate.total)) {
        commit_error(
            out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
            "particle-mesh Ewald composite total energy is not finite");
        return BG_STATUS_NUMERICAL_ERROR;
    }
    if (compute_forces) {
        for (std::size_t atom = 0U; atom < atom_count; ++atom) {
            const std::array<double, 3> pme_force{{
                direct_evaluation.forces[atom][0] +
                    reciprocal_evaluation.forces[atom][0],
                direct_evaluation.forces[atom][1] +
                    reciprocal_evaluation.forces[atom][1],
                direct_evaluation.forces[atom][2] +
                    reciprocal_evaluation.forces[atom][2],
            }};
            const std::array<double, 15> parent_and_combined_forces{{
                short_result.force_x[atom],
                short_result.force_y[atom],
                short_result.force_z[atom],
                direct_evaluation.forces[atom][0],
                direct_evaluation.forces[atom][1],
                direct_evaluation.forces[atom][2],
                reciprocal_evaluation.forces[atom][0],
                reciprocal_evaluation.forces[atom][1],
                reciprocal_evaluation.forces[atom][2],
                pme_force[0],
                pme_force[1],
                pme_force[2],
                short_result.force_x[atom] + pme_force[0],
                short_result.force_y[atom] + pme_force[1],
                short_result.force_z[atom] + pme_force[2],
            }};
            if (std::any_of(
                    parent_and_combined_forces.begin(),
                    parent_and_combined_forces.end(),
                    [](double value) { return !std::isfinite(value); })) {
                commit_error(
                    out_error, BG_DIRECT_EWALD_ERROR_NONFINITE_RESULT,
                    "particle-mesh Ewald composite parent, intermediate, or combined force is not finite");
                return BG_STATUS_NUMERICAL_ERROR;
            }
        }
        if (stateful_force_output != nullptr) {
            stateful_force_output->force_x.resize(atom_count);
            stateful_force_output->force_y.resize(atom_count);
            stateful_force_output->force_z.resize(atom_count);
            for (std::size_t atom = 0U; atom < atom_count; ++atom) {
                const std::array<double, 3> pme_force{{
                    direct_evaluation.forces[atom][0] +
                        reciprocal_evaluation.forces[atom][0],
                    direct_evaluation.forces[atom][1] +
                        reciprocal_evaluation.forces[atom][1],
                    direct_evaluation.forces[atom][2] +
                        reciprocal_evaluation.forces[atom][2],
                }};
                stateful_force_output->force_x[atom] =
                    short_result.force_x[atom] + pme_force[0];
                stateful_force_output->force_y[atom] =
                    short_result.force_y[atom] + pme_force[1];
                stateful_force_output->force_z[atom] =
                    short_result.force_z[atom] + pme_force[2];
            }
        } else {
            candidate.forces.resize(atom_count);
            for (std::size_t atom = 0U; atom < atom_count; ++atom) {
                const std::array<double, 3> pme_force{{
                    direct_evaluation.forces[atom][0] +
                        reciprocal_evaluation.forces[atom][0],
                    direct_evaluation.forces[atom][1] +
                        reciprocal_evaluation.forces[atom][1],
                    direct_evaluation.forces[atom][2] +
                        reciprocal_evaluation.forces[atom][2],
                }};
                candidate.forces[atom] = {{
                    short_result.force_x[atom] + pme_force[0],
                    short_result.force_y[atom] + pme_force[1],
                    short_result.force_z[atom] + pme_force[2],
                }};
            }
        }
    }
""",
        "validated particle-mesh final-SoA recording with stateless AoS fallback",
    )
    return replace_exact(
        source,
        """            lane, *system, *forcefield, *direct_model,
            *reciprocal_model, nullptr, nullptr, nullptr,
            out_forces != nullptr, &evaluation, out_error);
""",
        """            lane, *system, *forcefield, *direct_model,
            *reciprocal_model, nullptr, nullptr, nullptr, nullptr,
            out_forces != nullptr, &evaluation, out_error);
""",
        "stateless null final-SoA output",
    )


def expected_evaluator_header(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """/*
 * The caller must first establish validate_static_compatibility(). All three
 * scratch/cache pointers must be null for the stateless path or non-null for
 * the stateful path. A non-null short-system scratch must be independent,
 * deep-owned, shape/unit matched, and contain exact +0.0 charges; only its
 * positions are refreshed. Force-producing stateful calls reuse the short
 * parent's Evaluation storage. Force-free calls leave that storage and the
 * Rust validation cache untouched. Failed calls need not restore private
 * derived scratch/cache contents.
 */
""",
        """/*
 * The caller must first establish validate_static_compatibility(). The three
 * private scratch/cache pointers must be null for the stateless path or
 * non-null for the stateful path. The stateful force output must be non-null
 * exactly for a force-producing stateful call. A non-null short-system
 * scratch must be independent, deep-owned, shape/unit matched, and contain
 * exact +0.0 charges; only its positions are refreshed. Force-producing
 * stateful calls reuse the short parent's Evaluation storage and write the
 * final force directly to the supplied SoA Evaluation after all parent and
 * combined force values have been validated. Stateless force-producing calls
 * retain the composite AoS force result. Force-free calls leave the private
 * force storage and Rust validation cache untouched. Failed calls need not
 * restore private derived scratch/cache contents.
 */
""",
        "documented stateful final-SoA contract",
    )
    return replace_exact(
        source,
        """    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    bool compute_forces,
""",
        """    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    cpu::Evaluation *stateful_force_output,
    bool compute_forces,
""",
        "evaluator stateful final-SoA output parameter",
    )


def expected_dynamics_source(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """           system_storage_overlaps(simulation.system, output) ||
           forcefield_storage_overlaps(simulation.forcefield, output) ||
           vector_storage_overlaps(simulation.constraints, output);
""",
        """           system_storage_overlaps(simulation.system, output) ||
           forcefield_storage_overlaps(simulation.forcefield, output) ||
           vector_storage_overlaps(simulation.constraints, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.x, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.y, output) ||
           vector_storage_overlaps(
               simulation.force_evaluation_scratch.z, output);
""",
        "final-SoA owner output alias guard",
    )
    source = replace_exact(
        source,
        """        &provider->owner->short_parent_evaluation_scratch,
        &simulation->rust_cpu_forcefield_validated, compute_forces,
""",
        """        &provider->owner->short_parent_evaluation_scratch,
        &simulation->rust_cpu_forcefield_validated,
        compute_forces ? out_evaluation : nullptr, compute_forces,
""",
        "stateful force output binding",
    )
    source = replace_exact(
        source,
        """    cpu::Evaluation candidate;
    if (compute_forces) {
        candidate.force_x = std::move(out_evaluation->force_x);
        candidate.force_y = std::move(out_evaluation->force_y);
        candidate.force_z = std::move(out_evaluation->force_z);
    }
    candidate.energy.struct_size =
        static_cast<uint32_t>(sizeof(candidate.energy));
    candidate.energy.abi_version = BG_ABI_VERSION;
    candidate.energy.unit_system = simulation->system.unit_system;
    candidate.energy.harmonic_bond_kcal_per_mol =
        combined.short_harmonic_bond;
    candidate.energy.harmonic_angle_kcal_per_mol =
        combined.short_harmonic_angle;
    candidate.energy.periodic_torsion_kcal_per_mol =
        combined.short_periodic_torsion;
    candidate.energy.lennard_jones_kcal_per_mol =
        combined.short_lennard_jones;
    candidate.energy.coulomb_kcal_per_mol = combined.pme_total;
    candidate.energy.total_kcal_per_mol = combined.total;
    if (compute_forces) {
        const std::size_t atom_count = combined.forces.size();
        candidate.force_x.resize(atom_count);
        candidate.force_y.resize(atom_count);
        candidate.force_z.resize(atom_count);
        for (std::size_t atom = 0; atom < atom_count; ++atom) {
            candidate.force_x[atom] = combined.forces[atom][0];
            candidate.force_y[atom] = combined.forces[atom][1];
            candidate.force_z[atom] = combined.forces[atom][2];
        }
    }
    *out_evaluation = std::move(candidate);
""",
        """    bg_energy_components_v1 committed_energy{};
    committed_energy.struct_size =
        static_cast<uint32_t>(sizeof(committed_energy));
    committed_energy.abi_version = BG_ABI_VERSION;
    committed_energy.unit_system = simulation->system.unit_system;
    committed_energy.harmonic_bond_kcal_per_mol =
        combined.short_harmonic_bond;
    committed_energy.harmonic_angle_kcal_per_mol =
        combined.short_harmonic_angle;
    committed_energy.periodic_torsion_kcal_per_mol =
        combined.short_periodic_torsion;
    committed_energy.lennard_jones_kcal_per_mol =
        combined.short_lennard_jones;
    committed_energy.coulomb_kcal_per_mol = combined.pme_total;
    committed_energy.total_kcal_per_mol = combined.total;
    out_evaluation->energy = committed_energy;
""",
        "remove dynamics combined AoS to final SoA conversion",
    )
    return replace_exact(
        source,
        """            &candidate->short_parent_evaluation_scratch,
            &candidate->simulation->rust_cpu_forcefield_validated, false,
""",
        """            &candidate->short_parent_evaluation_scratch,
            &candidate->simulation->rust_cpu_forcefield_validated, nullptr,
            false,
""",
        "create-time null final-SoA output",
    )


def require_exact_regression_source(test: bytes) -> None:
    if sha(test) != EXPECTED_TEST_SOURCE_SHA256:
        fail("exact particle-mesh Ewald dynamics regression source drift")


def require_combined_force_soa_contract(root: Path = ROOT) -> None:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    transforms = (
        ("particle_mesh_ewald_composite.cpp", expected_particle_mesh_ewald_source),
        ("particle_mesh_ewald_composite_dynamics.cpp", expected_dynamics_source),
        ("particle_mesh_ewald_composite_evaluator.hpp", expected_evaluator_header),
    )
    observed_production: dict[str, str] = {}
    for name, transform in transforms:
        native_path = Path("native/src/composite") / name
        vendor_path = (
            Path("rust/betelgeuze-sys/vendor/native/src/composite") / name
        )
        native = (root / native_path).read_text()
        vendor = (root / vendor_path).read_text()
        frozen_native = git(
            "show", f"{merge}:{native_path.as_posix()}"
        ).stdout.decode()
        frozen_vendor = git(
            "show", f"{merge}:{vendor_path.as_posix()}"
        ).stdout.decode()
        if native != transform(frozen_native):
            fail(f"canonical bounded combined-force SoA transform drift: {name}")
        if vendor != transform(frozen_vendor):
            fail(f"vendored bounded combined-force SoA transform drift: {name}")
        if native != vendor:
            fail(f"canonical and vendored source differ: {name}")
        observed_production[name] = sha(native.encode())
    if observed_production != EXPECTED_PRODUCTION_SOURCE_SHA256:
        fail("exact particle-mesh Ewald combined-force SoA production hashes drift")

    composite_source = (
        root / "native/src/composite/particle_mesh_ewald_composite.cpp"
    ).read_text()
    contract_tokens = (
        "cpu::Evaluation *stateful_force_output,",
        "const bool requires_stateful_force_output =",
        "stateful_scratch && compute_forces;",
        "(stateful_force_output != nullptr) !=",
        "stateful_force_output == short_parent_evaluation_scratch",
        "const std::array<double, 15> parent_and_combined_forces{{",
        "parent_and_combined_forces.begin(),",
        "parent_and_combined_forces.end(),",
        "if (stateful_force_output != nullptr) {",
        "stateful_force_output->force_x.resize(atom_count);",
        "stateful_force_output->force_y.resize(atom_count);",
        "stateful_force_output->force_z.resize(atom_count);",
        "} else {\n            candidate.forces.resize(atom_count);",
        "nullptr, nullptr,\n            out_forces != nullptr, &evaluation, out_error);",
    )
    if any(token not in composite_source for token in contract_tokens):
        fail("particle-mesh Ewald final-SoA routing or validation drift")
    if composite_source.count("candidate.forces.resize(atom_count);") != 1:
        fail("stateless combined AoS fallback count drift")
    validation = composite_source.index(
        "const std::array<double, 15> parent_and_combined_forces{{"
    )
    final_write = composite_source.index(
        "stateful_force_output->force_x.resize(atom_count);", validation
    )
    if validation >= final_write:
        fail("final SoA write no longer follows complete parent validation")
    direct_local_status = composite_source.index(
        "if (status != BG_STATUS_OK) {",
        composite_source.index("ewald::Evaluation direct_evaluation;"),
    )
    if direct_local_status >= final_write:
        fail("late direct-local failure no longer precedes final SoA write")
    if composite_source.count("cpu::Evaluation *stateful_force_output") != 1:
        fail("stateful final-SoA output parameter count drift")

    dynamics_source = (
        root / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    dynamics_tokens = (
        "simulation.force_evaluation_scratch.x, output",
        "simulation.force_evaluation_scratch.y, output",
        "simulation.force_evaluation_scratch.z, output",
        "compute_forces ? out_evaluation : nullptr,",
        "bg_energy_components_v1 committed_energy{};",
        "out_evaluation->energy = committed_energy;",
    )
    if any(token not in dynamics_source for token in dynamics_tokens):
        fail("dynamics final-SoA binding, energy commit, or alias guard drift")
    provider_region = dynamics_source.split(
        "bg_status evaluate_composite_provider(", 1
    )[1].split("bg_status validate_particle_view_descriptor(", 1)[0]
    forbidden_provider_tokens = (
        "cpu::Evaluation candidate;",
        "candidate.force_x",
        "candidate.force_y",
        "candidate.force_z",
        "combined.forces",
        "*out_evaluation = std::move(candidate);",
    )
    if any(token in provider_region for token in forbidden_provider_tokens):
        fail("stateful provider rematerialized or copied combined AoS forces")

    test = (
        root / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_bytes()
    require_exact_regression_source(test)
    test_text = test.decode()
    test_tokens = (
        "force_scratch_bits(",
        "stateless_force_bits(",
        "PME stateful SoA force bits differed from stateless AoS bits",
        "PME SoA force output differed from the peer bits",
        "state-B integration did not refresh final force scratch",
        "checkpoint reload unexpectedly rewrote stale final force scratch",
        "zero-step restart changed stale final force scratch bits",
        "forceful restart did not resynchronize final force scratch",
        "late direct-local failure overwrote the last successful final force bits",
        "absolute-step output aliased final force scratch",
    )
    if any(token not in test_text for token in test_tokens):
        fail("combined-force SoA regression coverage drift")

    checkpoint_sources = (
        (root / "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp").read_text()
        + (root / "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp").read_text()
    )
    if "stateful_force_output" in checkpoint_sources:
        fail("stateful final-SoA output pointer entered checkpoint or owner layout")


def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_combined_force_soa_contract(root)
    require_predecessor_workflow_freeze(root)
    require_predecessor_unit_freeze(root)
    require_workflow_contract((root / WORKFLOW_RELATIVE_PATH).read_text())
    observed_delta = current_delta_paths()
    if observed_delta != EXPECTED_DELTA_PATHS:
        fail(
            "successor delta path set drift: "
            f"expected {[p.as_posix() for p in EXPECTED_DELTA_PATHS]}, "
            f"observed {[p.as_posix() for p in observed_delta]}"
        )


def verify(root: Path = ROOT) -> dict:
    require_predecessor()
    require_contracts(root)
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    if (
        manifest_raw != canonical_bytes(manifest)
        or manifest != build_source_manifest(root)
    ):
        fail("source manifest drift")
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    profile = json.loads(profile_raw)
    if profile_raw != canonical_bytes(profile) or profile != build_profile(manifest_raw):
        fail("profile drift")
    return {
        "profile_sha256": sha(profile_raw),
        "source_manifest_sha256": sha(manifest_raw),
        "source_count": len(manifest["files"]),
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
        print(f"verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
