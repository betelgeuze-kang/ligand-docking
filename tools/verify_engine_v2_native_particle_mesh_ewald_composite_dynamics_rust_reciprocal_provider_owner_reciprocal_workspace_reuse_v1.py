#!/usr/bin/env python3
"""Verify owner-private reciprocal-workspace reuse in the stateful Rust force route."""
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
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-owner-reciprocal-workspace-reuse.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-reciprocal-workspace-phase-reuse.yml"
)
MACOS_RETRY_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json"
)
PREDECESSOR_DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.md"
)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py"
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
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_sources/1.0.0"
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
    "pull_request": 463,
    "reviewed_head": "375e29d8fe43ca588366139fdb5ea0c1a4016b0f",
    "merge_commit": "a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c",
    "merge_tree": "84cdf4c64f8b41f99380700f0cdb090a852a3c03",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "ddf1aaf25370464dab2717f83ad4f746ce94cf0d4914adb198a1b57487f365e5"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "f659b995b298aa5a79977a99a50ad9853f7e0c2786ea9331f8471a0673e72ba5"
    ),
    "source_manifest_entry_count": 308,
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
DIRECT_FORCE_OUTPUT_PRECEDENT = {
    "pull_request": 380,
    "reviewed_head": "c486e767b1452cffb9cfd998bc26d5e4403bbd76",
    "merge_commit": "6662f1b53829930a93de0f298b820d5a367cc3dc",
    "merge_tree": "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177",
}

EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)
RUST_RECIPROCAL_RELATIVE_PATH = Path(
    "rust/cpu-kernel/src/particle_mesh_reciprocal.rs"
)
IMPLEMENTATION_DELTA_PATHS = tuple(
    Path(path)
    for path in (
        "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp",
        "native/src/particle_mesh_reciprocal/rust_evaluator.cpp",
        "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
        "native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.cpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h",
        RUST_RECIPROCAL_RELATIVE_PATH.as_posix(),
    )
)
NATIVE_TEST_RELATIVE_PATHS = tuple(
    Path(path)
    for path in (
        "native/tests/particle_mesh_ewald_composite_dynamics.cpp",
        "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp",
        "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp",
    )
)
EXPECTED_DELTA_PATHS = tuple(
    sorted(
        set(EVIDENCE_PATHS)
        | set(IMPLEMENTATION_DELTA_PATHS)
        | set(NATIVE_TEST_RELATIVE_PATHS)
        | {
            PREDECESSOR_WORKFLOW_RELATIVE_PATH,
            PREDECESSOR_UNIT_RELATIVE_PATH,
        },
        key=lambda path: path.as_posix(),
    )
)
REQUIRED_TRIGGER_PATHS = (
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-short-system-scratch.yml',
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-short-parent-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-short-parent-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-combined-force-soa.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-combined-force-soa.yml',
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-ewald-parent-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-direct-parent-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-reciprocal-parent-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-direct-force-soa.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-force-source-soa.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-borrowed-input-soa.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-fft-line-scratch-reuse.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-axis-data-buffer-consolidation.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-reciprocal-workspace-phase-reuse.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-owner-reciprocal-workspace-reuse.yml',
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-force-scratch.yml',
    '.github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-backend-preflight.yml',
    'CMakeLists.txt',
    'include/betelgeuze/**',
    'native/**',
    'native/src/particle_mesh_reciprocal/rust_provider.h',
    'rust/**',
    'rust/cpu-kernel/src/particle_mesh_reciprocal.rs',
    'rust_engine_v2/Cargo.lock',
    'rust_engine_v2/Cargo.toml',
    'config/engine_v2_direct_ewald_reference_profile_v1.json',
    'rust/reference-ewald/src/lib.rs',
    'config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1.json',
    'config/engine_v2_native_particle_mesh_reciprocal_cpu_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1_sources.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_profile_v1.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_profile_v1.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_ewald_parent_force_scratch_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_borrowed_input_soa_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_fft_line_scratch_reuse_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_direct_ewald_composite_dynamics_ewald_parent_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_borrowed_input_soa_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_fft_line_scratch_reuse_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json',
    'config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1_sources.json',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.md',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.md',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.md',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.md',
    'docs/engine_v2_native_direct_ewald_composite_dynamics_ewald_parent_force_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_borrowed_input_soa_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_fft_line_scratch_reuse_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.md',
    'docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.md',
    'tools/__init__.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py',
    'tools/verify_engine_v2_native_direct_ewald_composite_dynamics_ewald_parent_force_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_borrowed_input_soa_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_fft_line_scratch_reuse_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py',
    'tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_parent_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_combined_force_soa_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_combined_force_soa_v1.py',
    'tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_ewald_parent_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_reciprocal_parent_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_direct_force_soa_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_source_soa_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_borrowed_input_soa_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_fft_line_scratch_reuse_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py',
    'tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py',
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
    "95cd9eded39977cce81af4583acba539e70161d0e0bcf7298c589a14b80ede51"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "cd31d6055dea4aa8361bef42d6d84da8b7c41b96ce899e2900fee70fe79d1216"
)
EXPECTED_MACOS_RETRY_WORKFLOW_SHA256 = (
    "59c6089e4273c2324953ac0916671a8b9580391324cf7d15255a84cb450a9c66"
)

RUST_BOUNDARY_COMMAND_STEP = "\n".join(
    (
        "      - name: Existing Rust and direct-output regression, docs, and clean packages",
        "        run: |",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --test layout --test raw_smoke",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --lib particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --test particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --doc particle_mesh_reciprocal",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --lib particle_mesh_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --test particle_mesh_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --doc particle_mesh_ewald_composite_dynamics",
        "          cargo doc --manifest-path rust/Cargo.toml --locked --no-deps --package betelgeuze-sys --package betelgeuze-runtime",
        "          cargo fmt --manifest-path rust/Cargo.toml --all -- --check",
        "          cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel --all-targets -- -D warnings",
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
      - name: Materialize exact PR 463 target, PR 453 architecture, PR 440 inherited evaluator, and PR 380 direct-output precedent
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c^{tree})" = "84cdf4c64f8b41f99380700f0cdb090a852a3c03"
          git merge-base --is-ancestor a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c HEAD
          git fetch --no-tags --depth=1 origin refs/pull/463/head
          test "$(git rev-parse FETCH_HEAD)" = "375e29d8fe43ca588366139fdb5ea0c1a4016b0f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "84cdf4c64f8b41f99380700f0cdb090a852a3c03"
          test "$(git rev-parse 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          git merge-base --is-ancestor 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c
          git fetch --no-tags --depth=1 origin refs/pull/453/head
          test "$(git rev-parse FETCH_HEAD)" = "68607f1b4c1311755b565a2ace2e681695d7f764"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          test "$(git rev-parse 735883551510cbef91adc3e57dc131a1234b67fb^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          git merge-base --is-ancestor 735883551510cbef91adc3e57dc131a1234b67fb 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a
          git fetch --no-tags --depth=1 origin refs/pull/440/head
          test "$(git rev-parse FETCH_HEAD)" = "098bce0d726dbed6e4bf7b533e0445f81e244ea2"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          test "$(git rev-parse 6662f1b53829930a93de0f298b820d5a367cc3dc^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
          git merge-base --is-ancestor 6662f1b53829930a93de0f298b820d5a367cc3dc a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c
          git fetch --no-tags --depth=1 origin refs/pull/380/head
          test "$(git rev-parse FETCH_HEAD)" = "c486e767b1452cffb9cfd998bc26d5e4403bbd76"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_v1.py
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-release --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-release -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-sanitize --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-sanitize -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics)$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-cargo
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-owner-reciprocal-workspace-reuse-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-owner-reciprocal-workspace-reuse\n\n"
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
        "rust-reciprocal-provider-owner-reciprocal-workspace-reuse-${{ github.ref }}\n"
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
    require_direct_force_output_precedent()
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


def require_direct_force_output_precedent() -> None:
    merge = DIRECT_FORCE_OUTPUT_PRECEDENT["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("direct force-output precedent merge is not a commit")
    if git("rev-parse", f"{merge}^{{commit}}").stdout.strip().decode() != merge:
        fail("direct force-output precedent merge identity drift")
    if (
        git("rev-parse", f"{merge}^{{tree}}").stdout.strip().decode()
        != DIRECT_FORCE_OUTPUT_PRECEDENT["merge_tree"]
    ):
        fail("direct force-output precedent merge tree drift")
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
        fail("direct force-output precedent is not an ancestor of target")
    reviewed_tree = reviewed_head_tree_if_present(DIRECT_FORCE_OUTPUT_PRECEDENT)
    if (
        reviewed_tree is not None
        and reviewed_tree != DIRECT_FORCE_OUTPUT_PRECEDENT["merge_tree"]
    ):
        fail("direct force-output precedent reviewed-head tree drift")


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
            *NATIVE_TEST_RELATIVE_PATHS,
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
            "particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_"
            "owner_reciprocal_workspace_reuse_current_sources_tests_evidence_target_"
            "inherited_and_direct_output_precedent"
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
            "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_development_v1"
        ),
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "architecture_predecessor": dict(ARCHITECTURE_PREDECESSOR),
        "inherited_particle_mesh_reciprocal_predecessor": dict(INHERITED_PREDECESSOR),
        "direct_force_output_precedent": dict(DIRECT_FORCE_OUTPUT_PRECEDENT),
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
            "predecessor_call_local_reciprocal_workspace_contract_inherited": True,
            "owner_route_uses_one_persistent_complex_backing": True,
            "reciprocal_workspace_backing_length_is_mesh_plus_axis_sum": True,
            "reciprocal_workspace_spectrum_and_tail_contiguous_and_non_overlapping": True,
            "reciprocal_workspace_at_most_one_reserve_when_capacity_grows": True,
            "reciprocal_workspace_tail_forward_fft_axis_inverse_phase_reuse": True,
            "reciprocal_workspace_tail_not_retained": False,
            "spectrum_fft_line_and_axis_reserves_consolidated": True,
            "two_call_local_cluster_reserves_reduced_to_one": True,
            "reciprocal_axis_data_separate_allocation_removed": True,
            "reciprocal_axis_data_encoded_in_complex_real_and_imaginary": True,
            "spectrum_nonfinite_scan_excludes_reciprocal_tail": True,
            "predecessor_combined_allocation_detail_and_failure_timing_change_inherited": True,
            "status_abi_preserved": True,
            "reciprocal_axis_data_backing_length_is_sum_of_mesh_dimensions": True,
            "reciprocal_axis_data_x_y_z_slices_contiguous_and_non_overlapping": True,
            "reciprocal_axis_data_arithmetic_and_axis_order_preserved": True,
            "reciprocal_axis_data_not_retained": False,
            "call_local_fft_line_scratch_shared_by_forward_and_inverse": True,
            "fft_line_scratch_length_is_max_mesh_axis": True,
            "fft_transform_arithmetic_and_axis_order_preserved": True,
            "fft_line_scratch_overwrites_poison_before_read": True,
            "fft_line_scratch_not_retained": False,
            "all_hidden_rust_reciprocal_provider_modes_borrow_input_soa": True,
            "energy_only_provider_input_borrowed": True,
            "transactional_force_provider_input_borrowed": True,
            "direct_force_provider_input_borrowed": True,
            "provider_input_channels_borrowed_call_local": True,
            "provider_channel_copy_allocations_elided": True,
            "provider_position_aos_rematerialization_elided": True,
            "provider_input_borrow_after_complete_alias_preflight": True,
            "zero_count_null_channels_use_empty_slices": True,
            "borrowed_input_not_retained": True,
            "shared_owned_and_borrowed_calculation_pipeline": True,
            "remaining_fallible_workspaces_preserved": True,
            "energy_only_force_storage_disabled_preserved": True,
            "transactional_force_internal_vec_preserved": True,
            "direct_force_caller_owned_scratch_preserved": True,
            "transactional_energy_and_force_commit_preserved": True,
            "direct_energy_success_only_commit_preserved": True,
            "stateless_hidden_rust_provider_uses_call_local_borrowed_input": True,
            "stateful_force_free_hidden_rust_provider_uses_call_local_borrowed_input": True,
            "stateful_forceful_hidden_rust_provider_uses_call_local_borrowed_input": True,
            "public_bg_system_owned_storage_preserved": True,
            "public_native_cpp_adapter_abi_preserved": True,
            "rust_only_forceful_stateful_dispatch": True,
            "provider_force_source_result_is_private_internal_cpp_type": True,
            "provider_force_scratch_is_composite_local_force_source": True,
            "reciprocal_parent_aos_storage_untouched_on_rust_lane": True,
            "reciprocal_parent_empty_storage_preserved": True,
            "reciprocal_parent_stale_storage_and_bits_preserved": True,
            "fresh_rust_reciprocal_parent_aos_allocation_elided": True,
            "provider_soa_to_parent_aos_rematerialization_elided": True,
            "provider_force_source_finite_scan_precedes_composite_use": True,
            "composite_force_validation_two_pass_transactional": True,
            "final_force_soa_commit_after_full_preflight": True,
            "cpp_lane_reciprocal_parent_reuse_preserved": True,
            "stateless_path_preserved": True,
            "stateful_force_free_path_preserved": True,
            "existing_transactional_provider_entrypoint_preserved": True,
            "direct_provider_force_output_preserved": True,
            "provider_force_scratch_reuse_preserved": True,
            "direct_parent_force_storage_reuse_preserved": True,
            "short_parent_force_storage_reuse_preserved": True,
            "direct_local_reciprocal_bounds_remain_zero": True,
            "provider_force_source_serialized_in_checkpoint": False,
            "provider_force_source_bound_into_static_fingerprint": False,
            "checkpoint_format_changed": False,
            "static_fingerprint_changed": False,
            "public_abi_changed": False,
            "explicit_cpp_cpu_reference_lane": True,
            "explicit_rust_cpu_lane": True,
            "test_only_owner_introspection_not_exported": True,
            "private_provider_abi_extended": True,
            "private_workspace_descriptor_size_bytes": 72,
            "private_workspace_descriptor_zero_initializable": True,
            "private_workspace_descriptor_not_exported": True,
            "private_workspace_descriptor_not_checkpointed": True,
            "provider_force_scratch_noncopyable_and_nonmovable": True,
            "stateful_forceful_owner_workspace_route_only": True,
            "stateful_force_free_workspace_reuse_claimed": False,
            "stateless_workspace_reuse_claimed": False,
            "transactional_workspace_reuse_claimed": False,
            "concurrent_workspace_use_claimed": False,
            "cold_first_use_allocation_order_and_detail_preserved": True,
            "warm_same_shape_reciprocal_workspace_reserve_elided": True,
            "capacity_sufficient_shape_reuse_without_reserve": True,
            "growth_beyond_capacity_uses_one_workspace_reserve": True,
            "failed_workspace_growth_retains_prior_raw_parts_and_payload": True,
            "workspace_spectrum_cleared_before_additive_spread": True,
            "workspace_lease_restored_after_success_failure_and_panic": True,
            "workspace_complete_capacity_alias_preflight": True,
            "owner_dynamics_output_preflight_includes_complete_workspace_capacity": True,
            "integrate_output_alias_preflight_precedes_descriptor_reads": True,
            "particle_view_and_absolute_step_owner_overlap_precedes_access": True,
            "workspace_destroy_ready_exactly_once": True,
            "workspace_destroy_null_empty_double_and_detectably_malformed_fail_closed": True,
            "workspace_destroy_safety_contract_requires_private_rust_origin_canonical_ready": True,
            "independent_owners_use_independent_workspace_storage": True,
            "allocation_free_claimed": False,
            "provider_allocation_free_claimed": False,
            "steady_state_allocation_free_claimed": False,
            "all_remaining_allocations_elided_claimed": False,
            "all_remaining_reciprocal_allocations_elided_claimed": False,
            "transactional_force_internal_vec_allocation_elided_claimed": False,
            "neutrality_sort_allocation_elided_claimed": False,
            "particle_assignment_allocation_elided_claimed": False,
            "spectrum_allocation_elided_claimed": False,
            "fft_scratch_allocation_elided_claimed": False,
            "all_fft_scratch_allocations_elided_claimed": False,
            "reciprocal_workspace_capacity_equality_claimed": False,
            "reciprocal_workspace_storage_allocation_free_claimed": False,
            "persistent_reciprocal_workspace_reuse_claimed": True,
            "cross_call_reciprocal_workspace_reuse_claimed": True,
            "owner_reciprocal_workspace_reuse_claimed": True,
            "reciprocal_workspace_peak_memory_reduction_claimed": False,
            "direct_last_prewrite_axis_allocation_boundary_preserved_claimed": False,
            "allocation_error_detail_invariance_claimed": False,
            "allocation_failure_timing_invariance_claimed": False,
            "persistent_fft_scratch_reuse_claimed": False,
            "cross_call_fft_scratch_reuse_claimed": False,
            "owner_fft_scratch_reuse_claimed": False,
            "peak_memory_reduction_claimed": False,
            "reciprocal_axis_data_allocation_elided_claimed": False,
            "persistent_reciprocal_axis_data_reuse_claimed": False,
            "cross_call_reciprocal_axis_data_reuse_claimed": False,
            "owner_reciprocal_axis_data_reuse_claimed": False,
            "four_cube_p4096_axis_minus_max_complex_entries": 8,
            "four_cube_p4096_gather_live_payload_delta_bytes": 128,
            "universal_input_allocation_elision_claimed": False,
            "public_api_zero_copy_input_claimed": False,
            "public_bg_system_borrowed_ownership_claimed": False,
            "persistent_input_view_claimed": False,
            "cross_call_input_borrowing_claimed": False,
            "universal_repository_input_borrowing_claimed": False,
            "universal_reciprocal_parent_allocation_elision_claimed": False,
            "scientific_claimed": False,
            "scientific_equivalence_claimed": False,
            "timing_claimed": False,
            "performance_claimed": False,
            "acceleration_claimed": False,
            "product_claimed": False,
            "operational_readiness_claimed": False,
            "cross_lane_bit_parity_claimed": False,
            "reciprocal_failure_storage_retention_claimed": False,
            "scientific_failure_force_storage_retention_claimed": False,
            "unconditional_failure_storage_retention_claimed": False,
            "fixed64_cpu_v7_qualification_invoked": False,
            "hip_device_execution_invoked": False,
            "molecular_execution_invoked": False,
            "public_benchmark_invoked": False,
            "reservation_invoked": False,
            "source_manifest_entry_count": len(manifest["files"]),
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
        },
        "validation": {
            "predecessor_single_reciprocal_workspace_reserve_contract_inherited": True,
            "reciprocal_workspace_checked_mesh_plus_axis_sum_exact": True,
            "reciprocal_workspace_split_lengths_offsets_and_non_overlap_exact": True,
            "reciprocal_workspace_phase_reborrows_non_overlapping_and_ordered": True,
            "second_reciprocal_workspace_occurrence_injection_succeeds_exact_bits": True,
            "first_reciprocal_workspace_oom_transactional_with_combined_detail": True,
            "predecessor_combined_allocation_change_boundary_inherited": True,
            "predecessor_spectrum_fft_line_contract_inherited": True,
            "status_abi_unchanged": True,
            "separate_spectrum_fft_line_and_axis_allocation_sites_absent": True,
            "reciprocal_axis_slice_lengths_offsets_and_non_overlap_exact": True,
            "reciprocal_axis_value_bits_and_x_y_z_order_preserved": True,
            "same_tail_prefix_identity_across_forward_and_inverse_phases": True,
            "fft_scratch_poison_overwritten_before_read": True,
            "tail_axis_phase_overwrites_forward_poison_before_read": True,
            "inverse_prefix_overwrites_axis_phase_without_tail_suffix_drift": True,
            "capacity_equality_not_asserted": True,
            "four_cube_p4096_peak_counterexample_exact": True,
            "spectrum_only_nonfinite_scan_exact": True,
            "fft_transform_order_and_arithmetic_preserved": True,
            "predecessor_borrowed_input_contract_inherited": True,
            "predecessor_four_canonical_vendor_pairs_contract_inherited": True,
            "nine_production_path_delta_exact": True,
            "three_native_test_path_delta_exact": True,
            "four_modified_canonical_vendor_pairs_byte_identical": True,
            "predecessor_phase_reuse_contract_inherited": True,
            "removed_provider_copy_allocation_sites_absent": True,
            "borrowed_input_constructed_after_complete_preflight": True,
            "zero_count_raw_slice_formation_avoided": True,
            "borrowed_input_call_local_and_not_retained": True,
            "owned_and_borrowed_pipeline_shared_exact": True,
            "owned_and_three_borrowed_modes_bit_identical": True,
            "four_input_channel_aliases_fail_before_borrow": True,
            "provider_input_bits_retained_across_success_and_failure": True,
            "remaining_allocation_failure_boundaries_preserved": True,
            "exact_public_symbol_surfaces": True,
            "internal_force_source_symbols_absent_from_public_surfaces": True,
            "checkpoint_and_static_fingerprint_unchanged": True,
            "rust_only_stateful_forceful_dispatch_exact": True,
            "provider_soa_is_local_reciprocal_force_view": True,
            "reciprocal_parent_empty_and_stale_bits_preserved": True,
            "provider_force_source_finite_scan_exact": True,
            "composite_preflight_then_final_commit_order_exact": True,
            "cpp_stateless_and_force_free_routes_preserved": True,
            "provider_and_stateless_force_bits_compared": True,
            "direct_and_transactional_provider_contract_inherited": True,
            "late_scientific_failure_boundary_preserved": True,
            "synthetic_release_and_asan_ubsan": True,
            "standalone_reciprocal_release_and_asan_ubsan": True,
            "rust_cpu_kernel_focused_test_and_clippy": True,
            "rust_raw_safe_docs_fmt_clippy": True,
            "clean_rust_packages": True,
            "git_object_probes_lazy_fetch_disabled": True,
            "reviewed_head_optional_locally": True,
            "workflow_target_architecture_inherited_and_precedent_heads_explicitly_fetched": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
            "workspace_descriptor_layout_and_states_exact": True,
            "workspace_descriptor_and_complete_capacity_disjointness_exact": True,
            "owner_dynamics_output_complete_workspace_capacity_overlap_exact": True,
            "integrate_alias_checks_before_output_descriptor_reads_exact": True,
            "particle_view_and_absolute_step_owner_overlap_before_access_exact": True,
            "cold_first_use_oom_order_detail_and_transactionality_exact": True,
            "warm_same_shape_occurrence_one_pending_and_bits_exact": True,
            "capacity_sufficient_and_growth_reserve_boundaries_exact": True,
            "failed_growth_prior_workspace_retention_exact": True,
            "poisoned_retained_workspace_overwritten_before_read": True,
            "panic_unwind_restores_ready_workspace": True,
            "destroy_null_empty_double_detectably_malformed_and_ready_contract_exact": True,
            "stateless_transactional_force_free_and_cpp_routes_preserved": True,
            "owner_checkpoint_cpp_interleave_and_independence_exact": True,
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
        "      - name: Existing Rust and direct-output regression, docs, and clean packages\n"
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
        "refs/pull/463/head",
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
        "refs/pull/380/head",
        DIRECT_FORCE_OUTPUT_PRECEDENT["reviewed_head"],
        DIRECT_FORCE_OUTPUT_PRECEDENT["merge_commit"],
        DIRECT_FORCE_OUTPUT_PRECEDENT["merge_tree"],
        "pytest==8.3.5",
        "ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1",
        "cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked",
        "cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        'BETELGEUZE_V7_SOURCE_ROOT="$GITHUB_WORKSPACE"',
        "cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel particle_mesh_reciprocal",
        "cargo clippy --manifest-path rust/Cargo.toml --locked --package betelgeuze-cpu-kernel --all-targets -- -D warnings",
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
        (PREDECESSOR_DOC_RELATIVE_PATH, DOC_RELATIVE_PATH),
        (PREDECESSOR_VERIFIER_RELATIVE_PATH, VERIFIER_RELATIVE_PATH),
        (PREDECESSOR_UNIT_RELATIVE_PATH, UNIT_RELATIVE_PATH),
    )
    for predecessor, successor in successor_pairs:
        old = f'      - "{predecessor.as_posix()}"\n'
        new = old + f'      - "{successor.as_posix()}"\n'
        if expected.count(old) != 2:
            fail("frozen predecessor workflow successor trigger drift")
        expected = expected.replace(old, new)

    old_materialize = source_region(
        expected,
        "      - name: Materialize exact PR 462 target, PR 453 architecture, "
        "PR 440 inherited evaluator, and PR 380 direct-output precedent\n",
        "      - name: Verify bounded successor evidence\n",
        "frozen predecessor materialization",
    )
    new_materialize = """      - name: Materialize exact PR 463 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c^{tree})" = "84cdf4c64f8b41f99380700f0cdb090a852a3c03"
          git merge-base --is-ancestor a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c HEAD
          git fetch --no-tags --depth=1 origin refs/pull/463/head
          test "$(git rev-parse FETCH_HEAD)" = "375e29d8fe43ca588366139fdb5ea0c1a4016b0f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "84cdf4c64f8b41f99380700f0cdb090a852a3c03"
"""
    expected = replace_exact(
        expected, old_materialize, new_materialize, "predecessor materialization"
    )
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 463 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=a011c42d2c9902fb4e2ae2bf3f5ab4cffc86737c
          frozen_tree=84cdf4c64f8b41f99380700f0cdb090a852a3c03
          current_sha="$(git rev-parse HEAD)"
          restore() {
            git checkout --detach --quiet "$current_sha"
          }
          trap restore EXIT
          test "$(git rev-parse "$frozen"^{tree})" = "$frozen_tree"
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD)" = "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
          restore
          trap - EXIT
"""
    return replace_exact(
        expected, old_verify, new_verify, "predecessor frozen verification"
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
    addition = """PME_RUST_RECIPROCAL_PROVIDER_OWNER_RECIPROCAL_WORKSPACE_REUSE_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_owner_reciprocal_workspace_reuse_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_OWNER_RECIPROCAL_WORKSPACE_REUSE_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal-provider reciprocal workspace phase-reuse "
        "evidence is verified from its exact frozen PR 463 object after "
        "owner reciprocal-workspace reuse evidence is present"
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


HIDDEN_PROVIDER_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1"
)
OWNER_WORKSPACE_PROVIDER_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1"
)
OWNER_WORKSPACE_DESTROY_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_workspace_destroy_v1"
)
INTERNAL_FORCE_SOURCE_SYMBOLS = (
    "ProviderForceSourceResult",
    "evaluate_reusing_provider_force_storage",
)

EXPECTED_PREDECESSOR_DELTA_SHA256 = {
    "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "17d236a95748a66514fe40d3f2070356268e1dfb3cf8d4ad5f2cc9260bcd6d44",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "10660b9c09a79eaaf61ace5f44c7b2656931c269c14f2d21fb89c70146dfae7d",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "8c1e7f9b8de7e4bdd6079f12b182932a2f502294b0e6ea20fc598eb010ecac38",
    "native/src/particle_mesh_reciprocal/rust_provider.h": "eabe645f9e4505c714b8aa2dd37d382a57c690822cfda5630c31a21a11a70466",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "17d236a95748a66514fe40d3f2070356268e1dfb3cf8d4ad5f2cc9260bcd6d44",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "10660b9c09a79eaaf61ace5f44c7b2656931c269c14f2d21fb89c70146dfae7d",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "8c1e7f9b8de7e4bdd6079f12b182932a2f502294b0e6ea20fc598eb010ecac38",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h": "eabe645f9e4505c714b8aa2dd37d382a57c690822cfda5630c31a21a11a70466",
    "rust/cpu-kernel/src/particle_mesh_reciprocal.rs": "8a7c51bd992ceb1815bb33149699a74ee76a1dbc81ae096f25c776b318cba72e",
    "native/tests/particle_mesh_ewald_composite_dynamics.cpp": "1aa3a9076d1a6c4416bb57eefbc0c9e8bd094d3a9fa6172a06e8633e94817ba8",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp": "419e0365314958aa35a623a1407bd7f82388e3692fb030273592c7230a6850f1",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp": "0b4a8ef7f7244b3dfbc7ff1f9b09a769c664f43132d995327674c131e14e42cc",
}
EXPECTED_SUCCESSOR_DELTA_SHA256 = {
    "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "bbe98c4a90f709c6d988358ab47041fba1b172488f3a2c3a102b5e380585e302",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "00e71a06b663bd72d8b1c2687f4e1fe52c1976eca9825f246b95894ec0fd25e0",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "b9f994a052253f5de4c6f720ccd0fa65426fe9e9cf85b57b54cb19c697ecc890",
    "native/src/particle_mesh_reciprocal/rust_provider.h": "c95dd2fc99517c97dfd10a3b5a42f217ddee94d919421799c173bb49b163c95c",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.cpp": "bbe98c4a90f709c6d988358ab47041fba1b172488f3a2c3a102b5e380585e302",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "00e71a06b663bd72d8b1c2687f4e1fe52c1976eca9825f246b95894ec0fd25e0",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "b9f994a052253f5de4c6f720ccd0fa65426fe9e9cf85b57b54cb19c697ecc890",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h": "c95dd2fc99517c97dfd10a3b5a42f217ddee94d919421799c173bb49b163c95c",
    "rust/cpu-kernel/src/particle_mesh_reciprocal.rs": "6ccd01975380aacfa65a0dd395a75e75e8b7772302c4fd3f86c8ee3c42b1f861",
    "native/tests/particle_mesh_ewald_composite_dynamics.cpp": "2ad76be9d3e9d590037e456b8629daa7f8e22c2706a5d4d61f51d1ed834b29ca",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp": "e7d5d3c039f38716324804ee4bb31728aa769581553910cbcae94411a4fd9ca9",
    "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp": "a9e53377e179d4598b71a89113b8e6d9d63fb5aef7d24839317659dc6a4ba8b8",
}
CANONICAL_VENDOR_MIRROR_PAIRS = (
    "composite/particle_mesh_ewald_composite_dynamics.cpp",
    "particle_mesh_reciprocal/rust_evaluator.cpp",
    "particle_mesh_reciprocal/rust_evaluator.hpp",
    "particle_mesh_reciprocal/rust_provider.h",
)
FROZEN_CHECKPOINT_FINGERPRINT_PATHS = tuple(
    Path(path)
    for path in (
        "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.hpp",
    )
)
HIDDEN_SYMBOL_PUBLIC_SURFACES = tuple(
    Path(path)
    for path in (
        "include/betelgeuze/particle_mesh_reciprocal.h",
        "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h",
        "native/src/particle_mesh_reciprocal/api.cpp",
        "native/betelgeuze_engine.map",
        "native/betelgeuze_engine.exports",
        "native/tests/check_exports.cmake",
        "rust/betelgeuze-sys/src/lib.rs",
    )
)


def source_region(source: str, start: str, end: str, label: str) -> str:
    if source.count(start) != 1:
        fail(f"{label} start marker drift")
    start_index = source.index(start)
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        fail(f"{label} end marker drift")
    return source[start_index:end_index]


def require_ordered_tokens(source: str, tokens: tuple[str, ...], label: str) -> None:
    cursor = -1
    for token in tokens:
        next_cursor = source.find(token, cursor + 1)
        if next_cursor < 0 or next_cursor <= cursor:
            fail(f"{label} ordering drift: {token}")
        cursor = next_cursor


def require_hidden_provider_symbols(root: Path = ROOT) -> None:
    declaration = """int32_t bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error);
"""
    workspace_declaration = """int32_t
bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_workspace_v1(
    const bg_rust_particle_mesh_reciprocal_system_v1 *system,
    const bg_rust_particle_mesh_reciprocal_model_v1 *model,
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace,
    bg_rust_particle_mesh_reciprocal_energy_v1 *out_energy,
    bg_rust_particle_mesh_reciprocal_force_output_v1 *out_forces,
    bg_rust_particle_mesh_reciprocal_error_v1 *out_error);

void bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(
    bg_rust_particle_mesh_reciprocal_workspace_v1 *workspace);
"""
    for relative in (
        Path("native/src/particle_mesh_reciprocal/rust_provider.h"),
        Path(
            "rust/betelgeuze-sys/vendor/native/src/"
            "particle_mesh_reciprocal/rust_provider.h"
        ),
    ):
        source = (root / relative).read_text()
        if source.count(declaration) != 1:
            fail(f"hidden direct-output provider declaration drift: {relative}")
        if source.count(workspace_declaration) != 1:
            fail(f"hidden owner-workspace provider declaration drift: {relative}")
        if source.count("bg_rust_particle_mesh_reciprocal_evaluate_v1(") != 1:
            fail(f"transactional provider declaration drift: {relative}")

    for relative in HIDDEN_SYMBOL_PUBLIC_SURFACES:
        source = (root / relative).read_text()
        for symbol in (
            HIDDEN_PROVIDER_SYMBOL,
            OWNER_WORKSPACE_PROVIDER_SYMBOL,
            OWNER_WORKSPACE_DESTROY_SYMBOL,
            "bg_rust_particle_mesh_reciprocal_workspace_v1",
            *INTERNAL_FORCE_SOURCE_SYMBOLS,
        ):
            if symbol in source:
                fail(f"internal provider symbol leaked into public surface: {relative}")

    rust = (root / "rust/cpu-kernel/src/particle_mesh_reciprocal.rs").read_text()
    definition = f'pub unsafe extern "C" fn {HIDDEN_PROVIDER_SYMBOL}('
    if rust.count(definition) != 1 or rust.count("#[no_mangle]\n" + definition) != 1:
        fail("hidden direct-output Rust symbol definition drift")
    for symbol in (OWNER_WORKSPACE_PROVIDER_SYMBOL, OWNER_WORKSPACE_DESTROY_SYMBOL):
        definition = f'pub unsafe extern "C" fn {symbol}('
        if rust.count(definition) != 1 or rust.count("#[no_mangle]\n" + definition) != 1:
            fail(f"hidden owner-workspace Rust symbol definition drift: {symbol}")


def require_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_contract(
    root: Path = ROOT,
) -> None:
    expected_production = {
        Path(path) for path in EXPECTED_SUCCESSOR_DELTA_SHA256 if not path.startswith("native/tests/")
    }
    expected_tests = {
        Path(path) for path in EXPECTED_SUCCESSOR_DELTA_SHA256 if path.startswith("native/tests/")
    }
    if set(IMPLEMENTATION_DELTA_PATHS) != expected_production or len(expected_production) != 9:
        fail("owner reciprocal-workspace production path set drift")
    if set(NATIVE_TEST_RELATIVE_PATHS) != expected_tests or len(expected_tests) != 3:
        fail("owner reciprocal-workspace native test path set drift")
    if set(EXPECTED_PREDECESSOR_DELTA_SHA256) != set(EXPECTED_SUCCESSOR_DELTA_SHA256):
        fail("predecessor/successor exact source hash path set drift")

    merge = PREDECESSOR["merge_commit"]
    for relative, predecessor_digest in EXPECTED_PREDECESSOR_DELTA_SHA256.items():
        predecessor_raw = git("show", f"{merge}:{relative}").stdout
        if sha(predecessor_raw) != predecessor_digest:
            fail(f"frozen PR 463 source digest drift: {relative}")
        successor_raw = (root / relative).read_bytes()
        if sha(successor_raw) != EXPECTED_SUCCESSOR_DELTA_SHA256[relative]:
            fail(f"owner reciprocal-workspace source digest drift: {relative}")
        if predecessor_raw == successor_raw:
            fail(f"declared successor source path did not change: {relative}")

    if len(CANONICAL_VENDOR_MIRROR_PAIRS) != 4:
        fail("modified canonical/vendor mirror-pair count drift")
    for relative in CANONICAL_VENDOR_MIRROR_PAIRS:
        canonical = root / "native/src" / relative
        vendor = root / "rust/betelgeuze-sys/vendor/native/src" / relative
        if canonical.read_bytes() != vendor.read_bytes():
            fail(f"modified canonical/vendor mirror drift: {relative}")

    for relative in FROZEN_CHECKPOINT_FINGERPRINT_PATHS:
        if (root / relative).read_bytes() != git(
            "show", f"{merge}:{relative.as_posix()}"
        ).stdout:
            fail(f"checkpoint or static-fingerprint source drift: {relative}")

    composite_paths = (
        Path("native/src/composite/particle_mesh_ewald_composite_dynamics.cpp"),
        Path(
            "rust/betelgeuze-sys/vendor/native/src/composite/"
            "particle_mesh_ewald_composite_dynamics.cpp"
        ),
    )
    for relative in composite_paths:
        composite = (root / relative).read_text()
        frozen_composite = git("show", f"{merge}:{relative.as_posix()}").stdout.decode()
        static_start = "std::array<uint8_t, 32> compute_static_fingerprint(\n"
        static_end = "\nbg_status validate_owner_invariant(\n"
        if source_region(
            composite, static_start, static_end, f"static fingerprint {relative}"
        ) != source_region(
            frozen_composite,
            static_start,
            static_end,
            f"frozen static fingerprint {relative}",
        ):
            fail(f"static-fingerprint computation drift: {relative}")

        workspace_overlap = source_region(
            composite,
            "bool rust_reciprocal_workspace_storage_overlaps(\n",
            "\nbool counted_storage_overlaps(\n",
            f"workspace owner-overlap preflight {relative}",
        )
        require_ordered_tokens(
            workspace_overlap,
            (
                "static_assert(kElementSize == 2U * sizeof(double));",
                "if (workspace.length > workspace.capacity) {",
                "if (workspace.capacity == 0U) {",
                "return workspace.storage != nullptr || workspace.length != 0U;",
                "workspace.storage == nullptr ||",
                "workspace.capacity >",
                "workspace.storage, workspace.capacity * kElementSize, output);",
            ),
            f"full-capacity workspace owner-overlap preflight {relative}",
        )
        owner_overlap = source_region(
            composite,
            "bool owner_storage_overlaps(\n",
            "\nbg_status validate_typed_error_descriptor(\n",
            f"owner storage overlap {relative}",
        )
        if owner_overlap.count("rust_reciprocal_workspace_storage_overlaps(") != 1:
            fail(f"owner workspace backing overlap integration drift: {relative}")

        integrate_outputs = source_region(
            composite,
            "bg_status validate_integrate_outputs(\n",
            "\nclass DynamicStateRollback final {",
            f"integrate output preflight {relative}",
        )
        require_ordered_tokens(
            integrate_outputs,
            (
                "if (out_error == nullptr || !pointer_is_aligned(out_error)) {",
                "if (out_report != nullptr && !pointer_is_aligned(out_report)) {",
                "ByteRange error_range;",
                "owner_storage_overlaps(*simulation, error_range)",
                "ByteRange report_range;",
                "owner_storage_overlaps(*simulation, report_range)",
                "bg_status status = validate_typed_error_descriptor(*out_error);",
                "status = validate_report_descriptor(*out_report);",
            ),
            f"alias-before-descriptor-read integrate output preflight {relative}",
        )

        particle_view = source_region(
            composite,
            'extern "C" BG_API bg_status BG_CALL\n'
            "bg_particle_mesh_ewald_composite_simulation_v1_get_particles(\n",
            '\nextern "C" BG_API bg_status BG_CALL\n'
            "bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(\n",
            f"particle-view owner-overlap preflight {relative}",
        )
        require_ordered_tokens(
            particle_view,
            (
                "ByteRange view_range;",
                "owner_storage_overlaps(*simulation, view_range)",
                "validate_particle_view_descriptor(*out_view)",
            ),
            f"particle-view alias-before-descriptor-read preflight {relative}",
        )
        absolute_step = source_region(
            composite,
            'extern "C" BG_API bg_status BG_CALL\n'
            "bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step(\n",
            '\nextern "C" BG_API bg_status BG_CALL\n'
            "bg_context_integrate_particle_mesh_ewald_composite_v1(\n",
            f"absolute-step owner-overlap preflight {relative}",
        )
        require_ordered_tokens(
            absolute_step,
            (
                "ByteRange step_range;",
                "owner_storage_overlaps(*simulation, step_range)",
                "validate_owner_invariant(*simulation)",
                "bg_simulation_get_absolute_step(",
            ),
            f"absolute-step owner-overlap-before-write preflight {relative}",
        )
    require_hidden_provider_symbols(root)

    header = (root / "native/src/particle_mesh_reciprocal/rust_provider.h").read_text()
    evaluator_hpp = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.hpp"
    ).read_text()
    evaluator_cpp = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
    ).read_text()
    rust = (root / RUST_RECIPROCAL_RELATIVE_PATH).read_text()
    native_test = (
        root / "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
    ).read_text()
    scratch_cpp = (
        root / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    scratch_hpp = (
        root / "native/tests/particle_mesh_ewald_composite_dynamics_scratch.hpp"
    ).read_text()

    for token in (
        "BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_EMPTY",
        "BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_READY",
        "BG_RUST_PARTICLE_MESH_RECIPROCAL_WORKSPACE_STATE_LEASED",
        "typedef struct bg_rust_particle_mesh_reciprocal_workspace_v1",
        OWNER_WORKSPACE_PROVIDER_SYMBOL,
        OWNER_WORKSPACE_DESTROY_SYMBOL,
    ):
        if token not in header:
            fail(f"private workspace provider header contract drift: {token}")
    for token in (
        "bg_rust_particle_mesh_reciprocal_workspace_v1 reciprocal_workspace{};",
        "ProviderForceScratch(const ProviderForceScratch &) = delete;",
        "ProviderForceScratch(ProviderForceScratch &&) = delete;",
        "~ProviderForceScratch() noexcept;",
    ):
        if evaluator_hpp.count(token) != 1:
            fail(f"owner-private C++ workspace contract drift: {token}")
    for token in (
        "sizeof(bg_rust_particle_mesh_reciprocal_workspace_v1) == 72U",
        "static_assert(!std::is_copy_constructible_v<ProviderForceScratch>);",
        "static_assert(!std::is_move_constructible_v<ProviderForceScratch>);",
        OWNER_WORKSPACE_PROVIDER_SYMBOL,
        OWNER_WORKSPACE_DESTROY_SYMBOL,
    ):
        if token not in evaluator_cpp:
            fail(f"C++ workspace dispatch/layout contract drift: {token}")

    require_ordered_tokens(
        rust,
        (
            "if storage_count > self.storage.capacity() {",
            "fallible_reserve_exact(",
            "self.storage.resize(storage_count, Complex::default());",
            "self.storage.fill(Complex::default());",
        ),
        "capacity-aware reciprocal workspace prepare",
    )
    workspace_preflight = source_region(
        rust,
        "unsafe fn preflight_workspace_descriptor(\n",
        "\nfn ranges_overlap(",
        "Rust workspace descriptor preflight",
    )
    require_ordered_tokens(
        workspace_preflight,
        (
            "if workspace_descriptor_is_empty(workspace) {",
            "validate_header::<ParticleMeshReciprocalWorkspaceV1>(",
            "if workspace.length > workspace.capacity {",
            "let backing_range = if workspace.capacity == 0 {",
            "checked_range(",
            "workspace.capacity,",
            "let snapshot = if workspace.state == PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY",
        ),
        "Rust canonical descriptor and full-capacity backing preflight",
    )
    provider_impl = source_region(
        rust,
        "unsafe fn evaluate_provider_impl(\n",
        "\nunsafe fn validate_error_output(\n",
        "Rust provider implementation",
    )
    require_ordered_tokens(
        provider_impl,
        (
            "let workspace_preflight = if let Some(descriptor_range)",
            "let mutable_ranges = [",
            "workspace_preflight.map(|workspace| workspace.descriptor_range)",
            "workspace_preflight.and_then(|workspace| workspace.backing_range)",
            "require_disjoint_outputs(&mutable_ranges)?;",
            "for input_range in input_ranges.into_iter().flatten() {",
            "if workspace_preflight.is_some() {\n        alias_safety.set(true);",
            "reciprocal workspace is already leased",
            "let mut workspace_lease = workspace_preflight.map(|preflight| {",
            "ReciprocalWorkspaceLease::acquire(preflight)",
            "let input = unsafe { provider_input(&system, model) };",
        ),
        "Rust alias-before-lease-and-borrow provider boundary",
    )
    lease_acquire = source_region(
        rust,
        "impl ReciprocalWorkspaceLease {\n",
        "\nimpl Drop for ReciprocalWorkspaceLease {",
        "Rust workspace lease acquisition",
    )
    require_ordered_tokens(
        lease_acquire,
        (
            "unsafe { Vec::from_raw_parts(storage, length, capacity) }",
            "PARTICLE_MESH_RECIPROCAL_WORKSPACE_LEASED,",
        ),
        "Rust exact Vec ownership acquisition and LEASED publication",
    )
    lease_drop = source_region(
        rust,
        "impl Drop for ReciprocalWorkspaceLease {\n",
        "\nconst fn empty_workspace_descriptor()",
        "Rust workspace lease restoration",
    )
    require_ordered_tokens(
        lease_drop,
        (
            "let mut storage = ManuallyDrop::new(workspace.storage);",
            "if self.restore_empty_if_unallocated && capacity == 0 {",
            "ptr::write(self.descriptor, empty_workspace_descriptor())",
            "PARTICLE_MESH_RECIPROCAL_WORKSPACE_READY,",
        ),
        "Rust EMPTY-or-READY workspace lease restoration",
    )
    workspace_destroy = source_region(
        rust,
        "#[no_mangle]\npub unsafe extern \"C\" fn "
        "bg_rust_particle_mesh_reciprocal_workspace_destroy_v1(\n",
        "\n#[cfg(test)]\nmod tests {",
        "Rust workspace destroy",
    )
    require_ordered_tokens(
        workspace_destroy,
        (
            "preflight_workspace_descriptor(workspace, descriptor_range)",
            "let WorkspaceSnapshot::Ready {",
            "ranges_overlap(range, descriptor_range)",
            "ptr::write(workspace, empty_workspace_descriptor())",
            "drop(unsafe { Vec::from_raw_parts(storage, length, capacity) });",
        ),
        "Rust fail-closed exact-once workspace destroy",
    )
    for token in (
        "struct ReciprocalWorkspaceLease",
        "impl Drop for ReciprocalWorkspaceLease",
        "preflight_workspace_descriptor(",
        "workspace.capacity",
        "reciprocal workspace is already leased",
        "workspace_descriptor_is_empty",
        "WorkspaceSnapshot::Ready",
        OWNER_WORKSPACE_PROVIDER_SYMBOL,
        OWNER_WORKSPACE_DESTROY_SYMBOL,
        "owner_workspace_cold_oom_warm_reuse_and_stateless_allocation_are_frozen",
        "owner_workspace_poison_shrink_growth_and_failed_growth_are_deterministic",
        "owner_workspace_panic_restores_ready_lease_and_next_call_succeeds",
        "owner_workspace_malformed_busy_and_alias_cases_fail_closed",
    ):
        if token not in rust:
            fail(f"Rust owner-workspace lease/regression contract drift: {token}")
    cold_order = """        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
        ] {"""
    cold_owner_test = source_region(
        rust,
        "    #[test]\n"
        "    fn owner_workspace_cold_oom_warm_reuse_and_stateless_allocation_are_frozen() {\n",
        "\n    #[test]\n"
        "    fn owner_workspace_poison_shrink_growth_and_failed_growth_are_deterministic() {\n",
        "cold owner-workspace allocation regression",
    )
    if cold_owner_test.count(cold_order) != 1:
        fail("cold owner-workspace allocation order regression drift")
    if rust.count(
        '"particle-mesh spectrum, FFT line-scratch, and reciprocal axis-data allocation failed"'
    ) != 1:
        fail("cold owner-workspace allocation detail drift")
    if rust.count(
        "assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);"
    ) < 3:
        fail("warm/capacity-sufficient workspace reserve boundary coverage drift")
    if rust.count("ProviderForceMode::Direct(None),") != 1:
        fail("established stateless direct provider workspace boundary drift")
    if rust.count("ProviderForceMode::Direct(Some(workspace)),") != 1:
        fail("owner-workspace direct provider dispatch boundary drift")
    if rust.count("AllocationSite::ReciprocalWorkspace") < 8:
        fail("reciprocal-workspace allocation injection coverage drift")

    for token in (
        "require_empty_rust_reciprocal_workspace",
        "require_ready_rust_reciprocal_workspace",
        "require_same_rust_reciprocal_workspace_storage",
        "independent owners shared Rust reciprocal workspace storage",
        "stateful Rust force-free evaluation populated the reciprocal workspace",
        "checkpoint reload replaced the owner-private Rust reciprocal workspace",
    ):
        if token not in native_test:
            fail(f"native owner-workspace regression drift: {token}")
    for token in (
        "workspace_struct_size",
        "workspace_abi_version",
        "workspace_state",
        "workspace_storage",
        "workspace_length",
        "workspace_capacity",
        "workspace_reserved",
    ):
        if token not in scratch_cpp or token not in scratch_hpp:
            fail(f"test-only workspace snapshot drift: {token}")
    return

def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_rust_reciprocal_provider_owner_reciprocal_workspace_reuse_contract(root)
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
