#!/usr/bin/env python3
"""Verify PME reciprocal-space parent force-storage reuse in stateful dynamics."""
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
    "reciprocal_parent_force_scratch_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-reciprocal-parent-force-scratch.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-direct-parent-force-scratch.yml"
)
MACOS_RETRY_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_reciprocal_parent_force_scratch_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_direct_parent_force_scratch_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "direct_parent_force_scratch_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "direct_parent_force_scratch_profile_v1_sources.json"
)
ARCHITECTURE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "ewald_parent_force_scratch_profile_v1.json"
)
ARCHITECTURE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "ewald_parent_force_scratch_profile_v1_sources.json"
)
INHERITED_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json"
)
INHERITED_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_sources/1.0.0"
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
    "pull_request": 454,
    "reviewed_head": "f4ab121fc91f3a195df938a9894433b78316408a",
    "merge_commit": "c51112868f1c7e91af7510eb5652407dab46e0df",
    "merge_tree": "288d00bb91b0e5ea11cc093a42d1041ce8bdc648",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "3c1a55ec47caacd80dda77dab2aac3c407a3f39148a245419a09da19bef30c31"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "7abf0980148092be439216c530ae2558a6fdfc5cc00fe2986121f33f61855b7f"
    ),
    "source_manifest_entry_count": 252,
}
ARCHITECTURE_PREDECESSOR = {
    "pull_request": 453,
    "reviewed_head": "68607f1b4c1311755b565a2ace2e681695d7f764",
    "merge_commit": "35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a",
    "merge_tree": "b22c5fd115a5c8e28856872df57127ecdd28d9b5",
    "profile_path": ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "e0749f0c16486e4ac726dadeb149080dfd15dd68905e874517f5d6981a18133b"
    ),
    "source_manifest_path": ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "b2aa88f0d544711461a18ec232667c3a213eaf04851b3301c6851d74b3cc5dcb"
    ),
    "source_manifest_entry_count": 246,
}
INHERITED_PREDECESSOR = {
    "pull_request": 440,
    "reviewed_head": "098bce0d726dbed6e4bf7b533e0445f81e244ea2",
    "merge_commit": "735883551510cbef91adc3e57dc131a1234b67fb",
    "merge_tree": "6c2b6f3960b6df0592b78bb44e429389aa58bcbb",
    "profile_path": INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "ea1a3c92bab2f6a9901aba9f296f7cb59aad2b9ebf4f5a0fa9bf35b7a0f153f7"
    ),
    "source_manifest_path": INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "2b60fd079ed8f2af6d023f0b57a0627b449dea4e4037d8ed6d323d4467c940a2"
    ),
    "source_manifest_entry_count": 68,
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
        "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp",
        "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp",
        "native/src/particle_mesh_reciprocal/cpp_evaluator.cpp",
        "native/src/particle_mesh_reciprocal/cpp_evaluator.hpp",
        "native/src/particle_mesh_reciprocal/rust_evaluator.cpp",
        "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
        "native/tests/particle_mesh_ewald_composite_dynamics.cpp",
        "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp",
        "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_evaluator.hpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
        "cpp_evaluator.cpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
        "cpp_evaluator.hpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
        "rust_evaluator.cpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
        "rust_evaluator.hpp",
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
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-"
    "combined-force-soa.yml",
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-combined-force-soa.yml",
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-ewald-parent-force-scratch.yml",
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
    "config/engine_v2_direct_ewald_reference_profile_v1.json",
    "rust/reference-ewald/src/lib.rs",
    INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json",
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
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1_sources.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1_sources.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_profile_v1_sources.json",
    PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    PROFILE_RELATIVE_PATH.as_posix(),
    PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_"
    "ewald_parent_force_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "direct_parent_force_scratch_v1.md",
    DOC_RELATIVE_PATH.as_posix(),
    "tools/__init__.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_"
    "ewald_parent_force_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "direct_parent_force_scratch_v1.py",
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
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "combined_force_soa_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "combined_force_soa_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "ewald_parent_force_scratch_v1.py",
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
EXPECTED_PREDECESSOR_WORKFLOW_SHA256 = (
    "86ca107c7eff51fddde0c5d3c6b1311b74dfba7ccb5c966e5e391b0347b89d2f"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "d29d7cda581f0d353a612f68a5b61212ce03ee831aac04258e7dfe9726e755f8"
)
EXPECTED_MACOS_RETRY_WORKFLOW_SHA256 = (
    "59c6089e4273c2324953ac0916671a8b9580391324cf7d15255a84cb450a9c66"
)

RUST_BOUNDARY_COMMAND_STEP = "\n".join(
    (
        "      - name: Existing Rust regression, docs, and clean packages",
        "        run: |",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --test layout --test raw_smoke",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --lib particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --test particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --doc particle_mesh_reciprocal",
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
      - name: Materialize exact PR 454 target, PR 453 architecture, and PR 440 inherited reciprocal evaluator
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse c51112868f1c7e91af7510eb5652407dab46e0df^{tree})" = "288d00bb91b0e5ea11cc093a42d1041ce8bdc648"
          git merge-base --is-ancestor c51112868f1c7e91af7510eb5652407dab46e0df HEAD
          git fetch --no-tags --depth=1 origin refs/pull/454/head
          test "$(git rev-parse FETCH_HEAD)" = "f4ab121fc91f3a195df938a9894433b78316408a"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "288d00bb91b0e5ea11cc093a42d1041ce8bdc648"
          test "$(git rev-parse 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          git merge-base --is-ancestor 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a c51112868f1c7e91af7510eb5652407dab46e0df
          git fetch --no-tags --depth=1 origin refs/pull/453/head
          test "$(git rev-parse FETCH_HEAD)" = "68607f1b4c1311755b565a2ace2e681695d7f764"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          test "$(git rev-parse 735883551510cbef91adc3e57dc131a1234b67fb^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          git merge-base --is-ancestor 735883551510cbef91adc3e57dc131a1234b67fb 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a
          git fetch --no-tags --depth=1 origin refs/pull/440/head
          test "$(git rev-parse FETCH_HEAD)" = "098bce0d726dbed6e4bf7b533e0445f81e244ea2"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_v1.py
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
          cmake -S . -B build/particle-mesh-ewald-reciprocal-parent-force-scratch-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-reciprocal-parent-force-scratch-release --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/particle-mesh-ewald-reciprocal-parent-force-scratch-release -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/particle-mesh-ewald-reciprocal-parent-force-scratch-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/particle-mesh-ewald-reciprocal-parent-force-scratch-sanitize --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/particle-mesh-ewald-reciprocal-parent-force-scratch-sanitize -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics)$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/particle-mesh-ewald-reciprocal-parent-force-scratch-cargo
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
          cmake -S . -B build/particle-mesh-ewald-reciprocal-parent-force-scratch-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-reciprocal-parent-force-scratch-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/particle-mesh-ewald-reciprocal-parent-force-scratch-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "reciprocal-parent-force-scratch\n\n"
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
        "reciprocal-parent-force-scratch-${{ github.ref }}\n"
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
            merge,
            PREDECESSOR["merge_commit"],
            check=False,
        ).returncode
        != 0
    ):
        fail("architecture predecessor is not an ancestor of the target predecessor")
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
    if architecture_profile.get("schema_id") != (
        "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
        "ewald_parent_force_scratch_profile/1.0.0"
    ):
        fail("architecture predecessor schema drift")
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
            ARCHITECTURE_PREDECESSOR["merge_commit"],
            merge,
            check=False,
        ).returncode
        != 0
    ):
        fail("architecture predecessor is not an ancestor of target")
    head = git("rev-parse", "HEAD^{commit}").stdout.strip().decode()
    if git("merge-base", "--is-ancestor", merge, head, check=False).returncode != 0:
        fail("HEAD does not descend from the frozen target predecessor")

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
    if profile.get("abi", {}).get("public_profile_id") != PUBLIC_PROFILE_ID:
        fail("target predecessor particle-mesh Ewald ABI identity drift")
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
        fail("inherited reciprocal predecessor is not an ancestor of target")
    profile_raw = git(
        "show", f"{merge}:{INHERITED_PROFILE_RELATIVE_PATH.as_posix()}"
    ).stdout
    manifest_raw = git(
        "show", f"{merge}:{INHERITED_MANIFEST_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(profile_raw) != INHERITED_PREDECESSOR["profile_sha256"]:
        fail("inherited predecessor profile digest drift")
    if sha(manifest_raw) != INHERITED_PREDECESSOR["source_manifest_sha256"]:
        fail("inherited reciprocal source-manifest digest drift")
    reference_profile = json.loads(profile_raw)
    if reference_profile.get("schema_id") != (
        "betelgeuze.engine_v2_native_particle_mesh_reciprocal_cpu_profile/1.0.0"
    ):
        fail("inherited reciprocal evaluator profile schema drift")
    manifest = json.loads(manifest_raw)
    if canonical_bytes(manifest) != manifest_raw:
        fail("inherited reciprocal manifest is not canonical JSON")
    rows = manifest.get("files")
    if (
        type(rows) is not list
        or len(rows) != INHERITED_PREDECESSOR["source_manifest_entry_count"]
    ):
        fail("inherited reciprocal manifest count drift")
    inherited_paths: list[str] = []
    for row in rows:
        if type(row) is not dict or set(row) != {
            "byte_count",
            "path",
            "sha256",
        }:
            fail("inherited reciprocal manifest row shape drift")
        path = row["path"]
        digest = row["sha256"]
        if (
            type(row["byte_count"]) is not int
            or row["byte_count"] < 0
            or type(path) is not str
            or Path(path).is_absolute()
            or Path(path).as_posix() != path
            or ".." in Path(path).parts
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            fail("inherited reciprocal manifest row value drift")
        inherited_paths.append(path)
    if inherited_paths != sorted(set(inherited_paths)):
        fail("inherited reciprocal manifest paths are not sorted and unique")
    if (ROOT / INHERITED_PROFILE_RELATIVE_PATH).read_bytes() != profile_raw:
        fail("checked-out inherited predecessor profile differs from frozen merge")
    if (ROOT / INHERITED_MANIFEST_RELATIVE_PATH).read_bytes() != manifest_raw:
        fail("checked-out inherited reciprocal manifest differs from frozen merge")
    reviewed_tree = reviewed_head_tree_if_present(INHERITED_PREDECESSOR)
    if (
        reviewed_tree is not None
        and reviewed_tree != INHERITED_PREDECESSOR["merge_tree"]
    ):
        fail("inherited predecessor reviewed-head tree drift")
    return manifest


def current_delta_paths() -> tuple[Path, ...]:
    merge = PREDECESSOR["merge_commit"]
    tracked = git("diff", "--name-only", merge, "--").stdout.decode().splitlines()
    untracked = git(
        "ls-files", "--others", "--exclude-standard"
    ).stdout.decode().splitlines()
    return tuple(
        sorted({Path(path) for path in tracked + untracked}, key=lambda p: p.as_posix())
    )


def discover_source_paths(root: Path = ROOT) -> list[Path]:
    predecessor_manifest = require_predecessor()
    paths = {Path(row["path"]) for row in predecessor_manifest["files"]}
    paths.update(IMPLEMENTATION_DELTA_PATHS)
    paths.update(
        (
            PREDECESSOR_PROFILE_RELATIVE_PATH,
            PREDECESSOR_MANIFEST_RELATIVE_PATH,
            INHERITED_PROFILE_RELATIVE_PATH,
            INHERITED_MANIFEST_RELATIVE_PATH,
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
            "particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_"
            "current_sources_tests_evidence_target_and_inherited_reciprocal_predecessors"
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
            "reciprocal_parent_force_scratch_development_v1"
        ),
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "architecture_predecessor": dict(ARCHITECTURE_PREDECESSOR),
        "inherited_particle_mesh_reciprocal_predecessor": dict(INHERITED_PREDECESSOR),
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
            "successful_stateful_forceful_reciprocal_parent_aos_storage_reused": True,
            "steady_state_reciprocal_parent_force_storage_reused": True,
            "reciprocal_parent_force_scratch_is_derived_non_authoritative": True,
            "reciprocal_parent_force_scratch_serialized_in_checkpoint": False,
            "reciprocal_parent_force_scratch_bound_into_static_fingerprint": False,
            "cpp_reciprocal_gather_reuses_supplied_aos_vector": True,
            "rust_reciprocal_provider_soa_remains_local": True,
            "reciprocal_internal_soa_storage_reused": False,
            "reciprocal_mesh_storage_reused": False,
            "direct_parent_force_storage_reuse_preserved": True,
            "direct_local_reciprocal_bounds_remain_zero": True,
            "stateful_force_free_path_preserved": True,
            "stateless_path_preserved": True,
            "owner_overlap_rejected_before_descriptor_dereference": True,
            "reciprocal_failure_storage_retention_claimed": False,
            "allocation_failure_storage_identity_claimed": False,
            "resize_failure_storage_retention_claimed": False,
            "unconditional_failure_storage_retention_claimed": False,
            "upstream_failure_storage_retention_claimed": False,
            "universal_failure_storage_retention_claimed": False,
            "all_failure_path_storage_retention_claimed": False,
            "checkpoint_buffer_aliasing_claimed": False,
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
            "reciprocal_parent_pointer_capacity_and_size_retention": True,
            "same_lane_reserved_peer_and_stateless_reciprocal_parent_force_bit_identity": True,
            "initial_create_and_zero_step_stability": True,
            "checkpoint_load_retains_stale_derived_reciprocal_scratch": True,
            "next_forceful_step_exactly_resynchronizes_reciprocal_scratch": True,
            "interior_owner_alias_rejected_before_dereference": True,
            "standalone_reciprocal_release_and_asan_ubsan": True,
            "rust_raw_safe_docs_fmt_clippy": True,
            "clean_rust_packages": True,
            "git_object_probes_lazy_fetch_disabled": True,
            "reviewed_head_optional_locally": True,
            "workflow_architecture_target_and_inherited_heads_explicitly_fetched": True,
            "macos_locked_cargo_exact_signature_retry_bounded": True,
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
        "refs/pull/454/head",
        PREDECESSOR["reviewed_head"],
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        "refs/pull/453/head",
        ARCHITECTURE_PREDECESSOR["reviewed_head"],
        ARCHITECTURE_PREDECESSOR["merge_commit"],
        ARCHITECTURE_PREDECESSOR["merge_tree"],
        "refs/pull/440/head",
        INHERITED_PREDECESSOR["reviewed_head"],
        INHERITED_PREDECESSOR["merge_commit"],
        INHERITED_PREDECESSOR["merge_tree"],
        "pytest==8.3.5",
        "ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1",
        "cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked",
        "cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        'BETELGEUZE_V7_SOURCE_ROOT="$GITHUB_WORKSPACE"',
        "^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics|export_allowlist)$",
        "^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics)$",
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
    expected = frozen
    successor_pairs = (
        (PREDECESSOR_WORKFLOW_RELATIVE_PATH, WORKFLOW_RELATIVE_PATH),
        (PREDECESSOR_PROFILE_RELATIVE_PATH, PROFILE_RELATIVE_PATH),
        (PREDECESSOR_MANIFEST_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH),
        (
            Path(
                "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
                "direct_parent_force_scratch_v1.md"
            ),
            DOC_RELATIVE_PATH,
        ),
        (
            Path(
                "tools/verify_engine_v2_native_particle_mesh_ewald_composite_"
                "dynamics_direct_parent_force_scratch_v1.py"
            ),
            VERIFIER_RELATIVE_PATH,
        ),
        (PREDECESSOR_UNIT_RELATIVE_PATH, UNIT_RELATIVE_PATH),
    )
    for predecessor, successor in successor_pairs:
        old = f'      - "{predecessor.as_posix()}"\n'
        new = old + f'      - "{successor.as_posix()}"\n'
        if expected.count(old) != 2:
            fail("frozen predecessor workflow successor trigger drift")
        expected = expected.replace(old, new)

    inherited_anchor = (
        '      - "rust/reference-ewald/src/lib.rs"\n'
    )
    inherited_addition = (
        f'      - "{INHERITED_PROFILE_RELATIVE_PATH.as_posix()}"\n'
        f'      - "{INHERITED_MANIFEST_RELATIVE_PATH.as_posix()}"\n'
    )
    if expected.count(inherited_anchor) != 2:
        fail("frozen predecessor workflow inherited trigger drift")
    expected = expected.replace(
        inherited_anchor, inherited_anchor + inherited_addition
    )

    old_materialize = """      - name: Materialize exact PR 453 architecture, PR 452 target, and PR 435 inherited Ewald evaluator
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          git merge-base --is-ancestor 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a HEAD
          git fetch --no-tags --depth=1 origin refs/pull/453/head
          test "$(git rev-parse FETCH_HEAD)" = "68607f1b4c1311755b565a2ace2e681695d7f764"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          test "$(git rev-parse 8f371847d62c03efe99d1e3593c9c0473adcf968^{tree})" = "aa1ba05928e142f06dac11b31e323bb3e247bb17"
          git merge-base --is-ancestor 8f371847d62c03efe99d1e3593c9c0473adcf968 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a
          git fetch --no-tags --depth=1 origin refs/pull/452/head
          test "$(git rev-parse FETCH_HEAD)" = "998c8cf68838d5492aec0da1973f3e1f92953ff1"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "aa1ba05928e142f06dac11b31e323bb3e247bb17"
          test "$(git rev-parse ba008fcaa75891bca45e7b3d33b67449d80fb7d4^{tree})" = "0530a50af2cceeff02341ccb6fab141fd8c43726"
          git merge-base --is-ancestor ba008fcaa75891bca45e7b3d33b67449d80fb7d4 8f371847d62c03efe99d1e3593c9c0473adcf968
          git fetch --no-tags --depth=1 origin refs/pull/435/head
          test "$(git rev-parse FETCH_HEAD)" = "b94e4c008db1c8414f5d0f24fa266c85c828d13c"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "0530a50af2cceeff02341ccb6fab141fd8c43726"
"""
    new_materialize = """      - name: Materialize exact PR 454 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse c51112868f1c7e91af7510eb5652407dab46e0df^{tree})" = "288d00bb91b0e5ea11cc093a42d1041ce8bdc648"
          git merge-base --is-ancestor c51112868f1c7e91af7510eb5652407dab46e0df HEAD
          git fetch --no-tags --depth=1 origin refs/pull/454/head
          test "$(git rev-parse FETCH_HEAD)" = "f4ab121fc91f3a195df938a9894433b78316408a"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "288d00bb91b0e5ea11cc093a42d1041ce8bdc648"
"""
    expected = replace_exact(
        expected,
        old_materialize,
        new_materialize,
        "frozen predecessor workflow materialization",
    )
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 454 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=c51112868f1c7e91af7510eb5652407dab46e0df
          frozen_tree=288d00bb91b0e5ea11cc093a42d1041ce8bdc648
          current_sha="$(git rev-parse HEAD)"
          test "$(git rev-parse "$frozen^{commit}")" = "$frozen"
          test "$(git rev-parse "$frozen^{tree}")" = "$frozen_tree"
          git checkout --detach --quiet "$frozen"
          trap 'git checkout --detach --quiet "$current_sha"' EXIT
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py
          git checkout --detach --quiet "$current_sha"
          trap - EXIT
          test "$(git rev-parse HEAD)" = "$current_sha"
"""
    return replace_exact(
        expected,
        old_verify,
        new_verify,
        "frozen predecessor workflow execution",
    )


def require_predecessor_workflow_freeze(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", f"{merge}:{PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_WORKFLOW_SHA256:
        fail("pristine predecessor workflow digest drift")
    expected = expected_frozen_predecessor_workflow(frozen_raw.decode())
    current = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    if current != expected:
        fail("predecessor workflow freeze drift")


def expected_frozen_predecessor_unit(frozen: str) -> str:
    anchor = "ROOT = Path(__file__).resolve().parents[2]\n"
    addition = """PME_RECIPROCAL_PARENT_FORCE_SCRATCH_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "reciprocal_parent_force_scratch_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RECIPROCAL_PARENT_FORCE_SCRATCH_EVIDENCE_PRESENT,
    reason=(
        "PME direct-parent force-scratch evidence is verified from its exact "
        "frozen PR 454 object after reciprocal-parent force-scratch evidence "
        "is present"
    ),
)
"""
    if frozen.count(anchor) != 1:
        fail("frozen predecessor unit insertion point drift")
    return frozen.replace(anchor, anchor + addition, 1)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", f"{merge}:{PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(frozen_raw) != EXPECTED_PREDECESSOR_UNIT_SHA256:
        fail("pristine predecessor unit digest drift")
    expected = expected_frozen_predecessor_unit(frozen_raw.decode())
    current = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if current != expected:
        fail("predecessor unit freeze drift")


def replace_exact(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail(f"frozen {label} transformation point drift")
    return source.replace(old, new, 1)


def replace_count_exact(
    source: str, old: str, new: str, count: int, label: str
) -> str:
    if source.count(old) != count:
        fail(f"frozen {label} transformation point drift")
    return source.replace(old, new)


def expected_macos_lock_transient_retry_workflow(frozen: str) -> str:
    source = replace_exact(
        frozen,
        "      - name: Exact export regression\n        run: |\n",
        "      - name: Exact export regression\n"
        "        shell: bash\n"
        "        run: |\n",
        "macOS locked-Cargo explicit Bash shell",
    )
    old = """          cmake --build build/direct-ewald-short-system-scratch-macos --target betelgeuze_engine --parallel 2
"""
    new = """          build_log="$RUNNER_TEMP/direct-ewald-short-system-scratch-macos-build.log"
          set -o pipefail
          set +e
          cmake --build build/direct-ewald-short-system-scratch-macos --target betelgeuze_engine --parallel 2 2>&1 | tee "$build_log"
          build_pipeline_status=("${PIPESTATUS[@]}")
          set -e
          test "${#build_pipeline_status[@]}" -eq 2
          build_status="${build_pipeline_status[0]}"
          tee_status="${build_pipeline_status[1]}"
          if [ "$tee_status" -ne 0 ]; then
            exit "$tee_status"
          fi
          if [ "$build_status" -ne 0 ]; then
            if ! grep -Fq "xcrun_db-" "$build_log" ||
               ! grep -Fq "errno=Invalid argument" "$build_log" ||
               ! grep -Fq "cannot update the lock file" "$build_log" ||
               ! grep -Fq "because --locked was passed" "$build_log"; then
              exit "$build_status"
            fi
            retry_tmp="$(mktemp -d "$RUNNER_TEMP/direct-ewald-short-system-scratch.XXXXXX")"
            export TMPDIR="$retry_tmp"
            host_target="$(rustc -vV | sed -n 's/^host: //p')"
            test -n "$host_target"
            cargo metadata --manifest-path rust/Cargo.toml --locked --filter-platform "$host_target" --format-version 1 >/dev/null
            cmake --build build/direct-ewald-short-system-scratch-macos --target betelgeuze_engine --parallel 2
          fi
"""
    return replace_exact(
        source, old, new, "macOS locked-Cargo hosted-runner retry"
    )


def require_macos_lock_transient_retry_workflow(root: Path = ROOT) -> None:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    frozen_raw = git(
        "show", f"{merge}:{MACOS_RETRY_WORKFLOW_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(frozen_raw) != EXPECTED_MACOS_RETRY_WORKFLOW_SHA256:
        fail("pristine macOS retry workflow digest drift")
    expected = expected_macos_lock_transient_retry_workflow(
        frozen_raw.decode()
    )
    current = (root / MACOS_RETRY_WORKFLOW_RELATIVE_PATH).read_text()
    if current != expected:
        fail("macOS locked-Cargo hosted-runner retry workflow drift")


def expected_cpp_evaluator_header(frozen: str) -> str:
    anchor = """[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

"""
    addition = """[[nodiscard]] bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

"""
    return replace_exact(
        frozen,
        anchor,
        anchor + addition,
        "C++ reciprocal evaluator reuse declaration",
    )


def expected_rust_evaluator_header(frozen: str) -> str:
    anchor = """[[nodiscard]] bg_status evaluate(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

"""
    addition = """[[nodiscard]] bg_status evaluate_reusing_force_storage(
    const bg_system &system,
    const bg_particle_mesh_reciprocal_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
    Error *out_error);

"""
    return replace_exact(
        frozen,
        anchor,
        anchor + addition,
        "Rust reciprocal evaluator reuse declaration",
    )


EXPECTED_RECIPROCAL_PARENT_FORCE_SCRATCH_SHA256 = {
    "native/src/composite/particle_mesh_ewald_composite.cpp": "5c4b62b3e6de4e62c322f7a7aafad553ffb509cd545c9cb02e6583829d9d5324",
    "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "8849c13b8ae608a9eef02991036e39b3abce62826f08ddbfda05a1becaeb0b7d",
    "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp": "04f7bb7b5322c63e1e3622042f296af0bfba290ebed4d38cb29c862ef2bad86e",
    "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp": "b942237ad59f974bf9b09906e8449cddedaef5d5f61b6197391e4bef5a7126d9",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.cpp": "a83114cd49382cc1308fe3539d31ee6f48c563e9d195f1ba57874867af861711",
    "native/src/particle_mesh_reciprocal/cpp_evaluator.hpp": "96a9d76925a1ccf7230f219ec29a23128ef67e2e472a774aef89a076efd5a79b",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "c19520a6d77ff6e8d1e6a356a5d133f1a9229d9a8367fa2a12726cc7a6cb326c",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "5d953ebb3d5bb2087be8a7eb5ea674d53e8b8f02c36830153f3c0e45f7469705",
    "native/tests/particle_mesh_ewald_composite_dynamics.cpp": "07276e4219ebc6fb97197b04c5581a3c9b0b209cb3c5c9d95b8798e3f28187f7",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp": "d6b3ea9f33d6f0d0d5d025926740411d3eb4e29b61107c39f10baf19182ed5a7",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp": "123d9b4817c27f04277a58ea2e51a049f094b96adb5c5d7d8a36541f389706e1",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite.cpp": "5c4b62b3e6de4e62c322f7a7aafad553ffb509cd545c9cb02e6583829d9d5324",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "8849c13b8ae608a9eef02991036e39b3abce62826f08ddbfda05a1becaeb0b7d",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.hpp": "04f7bb7b5322c63e1e3622042f296af0bfba290ebed4d38cb29c862ef2bad86e",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_evaluator.hpp": "b942237ad59f974bf9b09906e8449cddedaef5d5f61b6197391e4bef5a7126d9",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/cpp_evaluator.cpp": "a83114cd49382cc1308fe3539d31ee6f48c563e9d195f1ba57874867af861711",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/cpp_evaluator.hpp": "96a9d76925a1ccf7230f219ec29a23128ef67e2e472a774aef89a076efd5a79b",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "c19520a6d77ff6e8d1e6a356a5d133f1a9229d9a8367fa2a12726cc7a6cb326c",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "5d953ebb3d5bb2087be8a7eb5ea674d53e8b8f02c36830153f3c0e45f7469705",
}


def require_reciprocal_parent_force_scratch_contract(
    root: Path = ROOT,
) -> None:
    for relative, digest in EXPECTED_RECIPROCAL_PARENT_FORCE_SCRATCH_SHA256.items():
        if sha((root / relative).read_bytes()) != digest:
            fail(f"exact PME reciprocal-parent force scratch source drift: {relative}")

    pairs = (
        "composite/particle_mesh_ewald_composite.cpp",
        "composite/particle_mesh_ewald_composite_dynamics.cpp",
        "composite/particle_mesh_ewald_composite_dynamics.hpp",
        "composite/particle_mesh_ewald_composite_evaluator.hpp",
        "particle_mesh_reciprocal/cpp_evaluator.cpp",
        "particle_mesh_reciprocal/cpp_evaluator.hpp",
        "particle_mesh_reciprocal/rust_evaluator.cpp",
        "particle_mesh_reciprocal/rust_evaluator.hpp",
    )
    for relative in pairs:
        canonical = root / "native/src" / relative
        vendor = (
            root
            / "rust/betelgeuze-sys/vendor/native/src"
            / relative
        )
        if canonical.read_bytes() != vendor.read_bytes():
            fail(f"canonical/vendor reciprocal-parent source drift: {relative}")

    merge = PREDECESSOR["merge_commit"]
    for relative in IMPLEMENTATION_DELTA_PATHS:
        frozen = git("show", f"{merge}:{relative.as_posix()}").stdout
        if frozen == (root / relative).read_bytes():
            fail(
                "PME reciprocal-parent implementation path did not change: "
                f"{relative.as_posix()}"
            )

    for relative, transform in (
        (
            "native/src/particle_mesh_reciprocal/cpp_evaluator.hpp",
            expected_cpp_evaluator_header,
        ),
        (
            "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
            expected_rust_evaluator_header,
        ),
        (
            "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
            "cpp_evaluator.hpp",
            expected_cpp_evaluator_header,
        ),
        (
            "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
            "rust_evaluator.hpp",
            expected_rust_evaluator_header,
        ),
    ):
        frozen = git("show", f"{merge}:{relative}").stdout.decode()
        if transform(frozen) != (root / relative).read_text():
            fail(f"frozen-input reciprocal evaluator header drift: {relative}")

    cpp = (
        root / "native/src/particle_mesh_reciprocal/cpp_evaluator.cpp"
    ).read_text()
    rust = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
    ).read_text()
    composite = (
        root / "native/src/composite/particle_mesh_ewald_composite.cpp"
    ).read_text()
    tests = (
        root / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    for token in (
        "void gather_forces(",
        "result->resize(assignments.size());",
        "(*result)[atom][derivative_axis]",
        "candidate.forces.swap(out_evaluation->forces);",
        "evaluate_reusing_force_storage(",
    ):
        if token not in cpp:
            fail(f"C++ reciprocal AoS reuse token missing: {token}")
    for token in (
        "candidate.forces.swap(out_evaluation->forces);",
        "std::vector<double> force_x;",
        "std::vector<double> force_y;",
        "std::vector<double> force_z;",
        "evaluate_reusing_force_storage(",
    ):
        if token not in rust:
            fail(f"Rust reciprocal final-AoS reuse token missing: {token}")
    for token in (
        "reciprocal_parent_evaluation_scratch",
        "reuse_reciprocal_parent_force_storage",
        "const particle_mesh_reciprocal::Evaluation &reciprocal_result",
    ):
        if token not in composite:
            fail(f"PME reciprocal-parent dispatch token missing: {token}")
    for token in (
        "reserve_particle_mesh_ewald_composite_reciprocal_parent_force_scratch(",
        "integration replaced PME reciprocal-parent force scratch storage",
        "PME reciprocal-parent scratch differed from same-lane peer bits",
        "PME reciprocal-parent scratch differed from stateless reciprocal force bits",
        "checkpoint reload unexpectedly rewrote stale PME reciprocal-parent scratch",
        "forceful restart did not resynchronize PME reciprocal-parent scratch",
        "absolute-step output aliased PME reciprocal-parent force scratch",
        "particle-view output aliased PME reciprocal-parent force scratch",
    ):
        if token not in tests:
            fail(f"PME reciprocal-parent test contract token missing: {token}")


def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_reciprocal_parent_force_scratch_contract(root)
    require_predecessor_workflow_freeze(root)
    require_predecessor_unit_freeze(root)
    require_macos_lock_transient_retry_workflow(root)
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
