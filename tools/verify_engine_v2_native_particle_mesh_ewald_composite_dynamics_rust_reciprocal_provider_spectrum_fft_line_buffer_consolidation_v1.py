#!/usr/bin/env python3
"""Verify one call-local Complex backing split into spectrum and FFT scratch."""
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
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-axis-data-buffer-consolidation.yml"
)
MACOS_RETRY_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1_sources.json"
)
PREDECESSOR_DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_axis_data_buffer_consolidation_v1.md"
)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py"
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
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_sources/1.0.0"
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
    "pull_request": 461,
    "reviewed_head": "d67a9335d5e03fed5d5fbb2f1a15e1ece670e975",
    "merge_commit": "33c7c418babe9f8f4822006cf726daf111459c7d",
    "merge_tree": "e8484675f7d9da011ac43165d907071950f3cf8e",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "33152ccf4589eaaf9c8b9be9ee6b901ed5ed4b631c3933ced40bd4f4171e1623"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "5379884390a9f9bdb220266ebb9ef3e62b4d1cfd79e749d3d74d01cfaeb8cd42"
    ),
    "source_manifest_entry_count": 296,
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
IMPLEMENTATION_DELTA_PATHS = (RUST_RECIPROCAL_RELATIVE_PATH,)
NATIVE_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_ewald_composite_dynamics.cpp"
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
    "157ef336e1669ddc2dda9bec6e6fb259fec50a3233c875719c6894b65bd8e810"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "3e2539904c0b409ef4bc048385a151ba308d19cac7779ba2b825dbeab5a6ab3a"
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
      - name: Materialize exact PR 461 target, PR 453 architecture, PR 440 inherited evaluator, and PR 380 direct-output precedent
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 33c7c418babe9f8f4822006cf726daf111459c7d^{tree})" = "e8484675f7d9da011ac43165d907071950f3cf8e"
          git merge-base --is-ancestor 33c7c418babe9f8f4822006cf726daf111459c7d HEAD
          git fetch --no-tags --depth=1 origin refs/pull/461/head
          test "$(git rev-parse FETCH_HEAD)" = "d67a9335d5e03fed5d5fbb2f1a15e1ece670e975"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "e8484675f7d9da011ac43165d907071950f3cf8e"
          test "$(git rev-parse 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          git merge-base --is-ancestor 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a 33c7c418babe9f8f4822006cf726daf111459c7d
          git fetch --no-tags --depth=1 origin refs/pull/453/head
          test "$(git rev-parse FETCH_HEAD)" = "68607f1b4c1311755b565a2ace2e681695d7f764"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          test "$(git rev-parse 735883551510cbef91adc3e57dc131a1234b67fb^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          git merge-base --is-ancestor 735883551510cbef91adc3e57dc131a1234b67fb 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a
          git fetch --no-tags --depth=1 origin refs/pull/440/head
          test "$(git rev-parse FETCH_HEAD)" = "098bce0d726dbed6e4bf7b533e0445f81e244ea2"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          test "$(git rev-parse 6662f1b53829930a93de0f298b820d5a367cc3dc^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
          git merge-base --is-ancestor 6662f1b53829930a93de0f298b820d5a367cc3dc 33c7c418babe9f8f4822006cf726daf111459c7d
          git fetch --no-tags --depth=1 origin refs/pull/380/head
          test "$(git rev-parse FETCH_HEAD)" = "c486e767b1452cffb9cfd998bc26d5e4403bbd76"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-release --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-release -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-sanitize --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-sanitize -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics)$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-cargo
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation\n\n"
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
        "rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation-${{ github.ref }}\n"
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
            NATIVE_TEST_RELATIVE_PATH,
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
            "spectrum_fft_line_buffer_consolidation_current_sources_tests_evidence_target_"
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
            "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_development_v1"
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
            "spectrum_and_fft_line_use_one_call_local_backing_buffer": True,
            "spectrum_and_fft_line_backing_length_is_mesh_plus_max_axis": True,
            "spectrum_and_fft_line_slices_contiguous_and_non_overlapping": True,
            "spectrum_and_fft_line_second_reserve_elided": True,
            "all_provider_modes_single_spectrum_and_fft_line_reserve": True,
            "spectrum_and_fft_line_storage_not_retained": True,
            "combined_allocation_error_detail_and_failure_timing_intentionally_changed": True,
            "status_abi_preserved": True,
            "reciprocal_axis_data_uses_one_call_local_backing_buffer": True,
            "reciprocal_axis_data_backing_length_is_sum_of_mesh_dimensions": True,
            "reciprocal_axis_data_x_y_z_slices_contiguous_and_non_overlapping": True,
            "reciprocal_axis_data_second_and_third_reserves_elided": True,
            "reciprocal_axis_data_arithmetic_and_axis_order_preserved": True,
            "reciprocal_axis_data_not_retained": True,
            "all_provider_modes_single_reciprocal_axis_data_reserve": True,
            "call_local_fft_line_scratch_shared_by_forward_and_inverse": True,
            "fft_line_scratch_length_is_max_mesh_axis": True,
            "fft_transform_arithmetic_and_axis_order_preserved": True,
            "fft_line_scratch_overwrites_poison_before_read": True,
            "fft_line_scratch_not_retained": True,
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
            "native_cpp_adapter_abi_preserved": True,
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
            "spectrum_fft_line_storage_allocation_free_claimed": False,
            "persistent_spectrum_fft_line_storage_reuse_claimed": False,
            "cross_call_spectrum_fft_line_storage_reuse_claimed": False,
            "owner_spectrum_fft_line_storage_reuse_claimed": False,
            "spectrum_fft_line_peak_memory_reduction_claimed": False,
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
            "single_spectrum_and_fft_line_reserve_occurrence_exact": True,
            "spectrum_and_fft_line_checked_total_exact": True,
            "spectrum_and_fft_line_slice_lengths_offsets_and_non_overlap_exact": True,
            "second_spectrum_and_fft_line_occurrence_injection_succeeds_exact_bits": True,
            "first_spectrum_and_fft_line_oom_transactional_with_combined_detail": True,
            "combined_allocation_detail_and_failure_timing_change_explicitly_bounded": True,
            "predecessor_axis_data_buffer_contract_inherited": True,
            "status_abi_unchanged": True,
            "single_reciprocal_axis_data_reserve_occurrence_exact": True,
            "reciprocal_axis_slice_lengths_offsets_and_non_overlap_exact": True,
            "reciprocal_axis_value_bits_and_x_y_z_order_preserved": True,
            "second_reciprocal_axis_data_occurrence_injection_succeeds_exact_bits": True,
            "first_reciprocal_axis_data_oom_transactional": True,
            "same_fft_scratch_identity_and_capacity_across_transforms": True,
            "fft_scratch_poison_overwritten_before_read": True,
            "direct_last_prewrite_axis_allocation_boundary_preserved": True,
            "fft_transform_order_and_arithmetic_preserved": True,
            "predecessor_borrowed_input_contract_inherited": True,
            "four_canonical_vendor_pairs_byte_identical": True,
            "predecessor_eight_production_paths_exact_and_unchanged": True,
            "predecessor_native_regression_path_exact_and_unchanged": True,
            "single_rust_production_path_delta_exact": True,
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
        "refs/pull/461/head",
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
        "      - name: Materialize exact PR 460 target, PR 453 architecture, "
        "PR 440 inherited evaluator, and PR 380 direct-output precedent\n",
        "      - name: Verify bounded successor evidence\n",
        "frozen predecessor materialization",
    )
    new_materialize = """      - name: Materialize exact PR 461 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 33c7c418babe9f8f4822006cf726daf111459c7d^{tree})" = "e8484675f7d9da011ac43165d907071950f3cf8e"
          git merge-base --is-ancestor 33c7c418babe9f8f4822006cf726daf111459c7d HEAD
          git fetch --no-tags --depth=1 origin refs/pull/461/head
          test "$(git rev-parse FETCH_HEAD)" = "d67a9335d5e03fed5d5fbb2f1a15e1ece670e975"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "e8484675f7d9da011ac43165d907071950f3cf8e"
"""
    expected = replace_exact(
        expected, old_materialize, new_materialize, "predecessor materialization"
    )
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 461 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=33c7c418babe9f8f4822006cf726daf111459c7d
          frozen_tree=e8484675f7d9da011ac43165d907071950f3cf8e
          current_sha="$(git rev-parse HEAD)"
          restore() {
            git checkout --detach --quiet "$current_sha"
          }
          trap restore EXIT
          test "$(git rev-parse "$frozen"^{tree})" = "$frozen_tree"
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD)" = "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_axis_data_buffer_consolidation_v1.py
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
    addition = """PME_RUST_RECIPROCAL_PROVIDER_SPECTRUM_FFT_LINE_BUFFER_CONSOLIDATION_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_SPECTRUM_FFT_LINE_BUFFER_CONSOLIDATION_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal provider axis-data buffer consolidation evidence is "
        "verified from its exact frozen PR 461 object after spectrum/FFT-line "
        "buffer consolidation evidence is present"
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
INTERNAL_FORCE_SOURCE_SYMBOLS = (
    "ProviderForceSourceResult",
    "evaluate_reusing_provider_force_storage",
)

EXPECTED_PREDECESSOR_PRODUCTION_SHA256 = {
    "native/src/composite/particle_mesh_ewald_composite.cpp": "85881e4847b52cb0c583d1a694f852061f7133bd7e6b5ef7d03b9126858990bd",
    "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp": "592903aa0699cec20b5e3d94d297c28692b27271cc25cc344fb258e93dbf8a0a",
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "10660b9c09a79eaaf61ace5f44c7b2656931c269c14f2d21fb89c70146dfae7d",
    "native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "8c1e7f9b8de7e4bdd6079f12b182932a2f502294b0e6ea20fc598eb010ecac38",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite.cpp": "85881e4847b52cb0c583d1a694f852061f7133bd7e6b5ef7d03b9126858990bd",
    "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_evaluator.hpp": "592903aa0699cec20b5e3d94d297c28692b27271cc25cc344fb258e93dbf8a0a",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.cpp": "10660b9c09a79eaaf61ace5f44c7b2656931c269c14f2d21fb89c70146dfae7d",
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_evaluator.hpp": "8c1e7f9b8de7e4bdd6079f12b182932a2f502294b0e6ea20fc598eb010ecac38",
}
EXPECTED_NATIVE_TEST_SHA256 = (
    "1aa3a9076d1a6c4416bb57eefbc0c9e8bd094d3a9fa6172a06e8633e94817ba8"
)
EXPECTED_RUST_RECIPROCAL_SHA256 = (
    "0faf26257c71bcd1ba806c427b7dd493edf8e6393ab5083aefa2b2f53193f0df"
)
CANONICAL_VENDOR_MIRROR_PAIRS = (
    "composite/particle_mesh_ewald_composite.cpp",
    "composite/particle_mesh_ewald_composite_evaluator.hpp",
    "particle_mesh_reciprocal/rust_evaluator.cpp",
    "particle_mesh_reciprocal/rust_evaluator.hpp",
)
FROZEN_PROVIDER_HEADER_PATHS = tuple(
    Path(path)
    for path in (
        "native/src/particle_mesh_reciprocal/rust_provider.h",
        "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/rust_provider.h",
    )
)
FROZEN_CHECKPOINT_FINGERPRINT_PATHS = tuple(
    Path(path)
    for path in (
        "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp",
        "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "particle_mesh_ewald_composite_dynamics.cpp",
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
        if source.count("bg_rust_particle_mesh_reciprocal_evaluate_v1(") != 1:
            fail(f"transactional provider declaration drift: {relative}")

    for relative in HIDDEN_SYMBOL_PUBLIC_SURFACES:
        source = (root / relative).read_text()
        for symbol in (HIDDEN_PROVIDER_SYMBOL, *INTERNAL_FORCE_SOURCE_SYMBOLS):
            if symbol in source:
                fail(f"internal provider symbol leaked into public surface: {relative}")

    rust = (root / "rust/cpu-kernel/src/particle_mesh_reciprocal.rs").read_text()
    definition = f'pub unsafe extern "C" fn {HIDDEN_PROVIDER_SYMBOL}('
    if rust.count(definition) != 1 or rust.count("#[no_mangle]\n" + definition) != 1:
        fail("hidden direct-output Rust symbol definition drift")


def require_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_contract(
    root: Path = ROOT,
) -> None:
    if IMPLEMENTATION_DELTA_PATHS != (RUST_RECIPROCAL_RELATIVE_PATH,):
        fail("spectrum/FFT-line buffer consolidation production path set drift")

    merge = PREDECESSOR["merge_commit"]
    for relative, digest in EXPECTED_PREDECESSOR_PRODUCTION_SHA256.items():
        path = root / relative
        raw = path.read_bytes()
        if sha(raw) != digest:
            fail(f"exact predecessor borrowed-input production drift: {relative}")
        if git("show", f"{merge}:{relative}").stdout != raw:
            fail(f"predecessor borrowed-input production path changed: {relative}")

    native_test_raw = (root / NATIVE_TEST_RELATIVE_PATH).read_bytes()
    if sha(native_test_raw) != EXPECTED_NATIVE_TEST_SHA256:
        fail("exact predecessor borrowed-input native regression drift")
    if (
        git("show", f"{merge}:{NATIVE_TEST_RELATIVE_PATH.as_posix()}").stdout
        != native_test_raw
    ):
        fail("predecessor borrowed-input native regression changed")

    if (
        len(CANONICAL_VENDOR_MIRROR_PAIRS) != 4
        or len(set(CANONICAL_VENDOR_MIRROR_PAIRS)) != 4
    ):
        fail("four canonical/vendor mirror pairs drift")
    for relative in CANONICAL_VENDOR_MIRROR_PAIRS:
        canonical = root / "native/src" / relative
        vendor = root / "rust/betelgeuze-sys/vendor/native/src" / relative
        if canonical.read_bytes() != vendor.read_bytes():
            fail(f"canonical/vendor borrowed-input mirror drift: {relative}")

    for relative in FROZEN_PROVIDER_HEADER_PATHS:
        if (root / relative).read_bytes() != git(
            "show", f"{merge}:{relative.as_posix()}"
        ).stdout:
            fail(f"provider header drift: {relative}")

    for relative in FROZEN_CHECKPOINT_FINGERPRINT_PATHS:
        if (root / relative).read_bytes() != git(
            "show", f"{merge}:{relative.as_posix()}"
        ).stdout:
            fail(f"checkpoint or static-fingerprint source drift: {relative}")

    require_hidden_provider_symbols(root)

    rust_raw = (root / RUST_RECIPROCAL_RELATIVE_PATH).read_bytes()
    if sha(rust_raw) != EXPECTED_RUST_RECIPROCAL_SHA256:
        fail("exact spectrum/FFT-line buffer consolidation Rust source drift")
    if git(
        "show", f"{merge}:{RUST_RECIPROCAL_RELATIVE_PATH.as_posix()}"
    ).stdout == rust_raw:
        fail("spectrum/FFT-line buffer consolidation Rust source did not change")

    rust = rust_raw.decode()
    production = rust.split("#[cfg(test)]\nmod tests", 1)[0]
    for removed in (
        "AllocationSite::Spectrum,",
        "AllocationSite::FftLineScratch,",
        "pub(crate) fn line_scratch(",
    ):
        if removed in production:
            fail(f"separate spectrum/FFT-line allocation returned: {removed}")

    combined_allocator = source_region(
        rust,
        "fn spectrum_and_fft_line_scratch(\n",
        "\n\n#[derive(Clone, Copy)]\nenum ForceStorageMode",
        "combined spectrum/FFT-line allocator",
    )
    require_ordered_tokens(
        combined_allocator,
        (
            "let line_count = validated.dimensions.into_iter().max().unwrap_or(0);",
            "let storage_count = validated",
            ".mesh_point_count",
            ".checked_add(line_count)",
            '.expect("validated spectrum and FFT line-scratch count fits usize");',
            "let mut storage = Vec::new();",
            "fallible_reserve_exact(",
            "storage_count,",
            "AllocationSite::SpectrumAndFftLineScratch,",
            "storage.resize(storage_count, Complex::default());",
            "Ok(storage)",
        ),
        "single checked spectrum/FFT-line backing reserve",
    )
    if (
        combined_allocator.count("fallible_reserve_exact(") != 1
        or combined_allocator.count("AllocationSite::SpectrumAndFftLineScratch") != 1
        or combined_allocator.count(".checked_add(line_count)") != 1
        or combined_allocator.count("storage.resize(") != 1
    ):
        fail("combined spectrum/FFT-line backing reserve count drift")

    fft_transform = source_region(
        rust,
        "    pub(crate) fn fft_3d(\n",
        "\n\n    fn fft_1d(",
        "caller-supplied FFT transform",
    )
    transform_3d = source_region(
        rust,
        "    fn transform_3d_with(\n",
        "\n\n    pub(crate) const fn index(",
        "caller-supplied three-dimensional transform",
    )
    for label, region in (("fft_3d", fft_transform), ("transform_3d", transform_3d)):
        if "line: &mut [Complex]" not in region:
            fail(f"{label} no longer receives caller scratch")
        for forbidden in ("Vec::", "Vec<", "reserve", "resize"):
            if forbidden in region:
                fail(f"{label} recreated FFT scratch: {forbidden}")
    require_ordered_tokens(
        transform_3d,
        (
            "for x in 0..x_count",
            "transform_1d(&mut line[..z_count], inverse);",
            "for x in 0..x_count",
            "transform_1d(&mut line[..y_count], inverse);",
            "for y in 0..y_count",
            "transform_1d(&mut line[..x_count], inverse);",
        ),
        "frozen z-y-x FFT axis order",
    )

    compute = source_region(
        rust,
        "fn compute_with_transform<I: ReciprocalInput + ?Sized>(\n",
        "\n\nstruct ReciprocalOperator {",
        "shared reciprocal calculation",
    )
    require_ordered_tokens(
        compute,
        (
            "let validated = validate(input)?;",
            "AllocationSite::ParticleAssignments,",
            "let mut spectrum_and_fft_line_storage =",
            "spectrum_and_fft_line_scratch(&validated)",
            "spectrum_and_fft_line_storage.split_at_mut(validated.mesh_point_count);",
            "debug_assert_eq!(",
            "fft_line_scratch.len(),",
            "validated.dimensions.into_iter().max().unwrap_or(0)",
            "spread_charges(spectrum, validated.dimensions, &assignments, charges);",
            "transform(spectrum, validated.dimensions, false, fft_line_scratch);",
            "let reciprocal = apply_reciprocal_operator(input, &validated, spectrum)?;",
            "transform(spectrum, validated.dimensions, true, fft_line_scratch);",
        ),
        "one split backing shared by ordered forward and inverse transforms",
    )
    if (
        compute.count("spectrum_and_fft_line_scratch(&validated)") != 1
        or compute.count(".split_at_mut(validated.mesh_point_count)") != 1
        or compute.count("transform(spectrum, validated.dimensions") != 2
        or "AllocationSite::Spectrum" in compute
        or "AllocationSite::FftLineScratch" in compute
    ):
        fail("shared calculation spectrum/FFT-line split or use count drift")

    reciprocal_operator = source_region(
        rust,
        "fn apply_reciprocal_operator<I: ReciprocalInput + ?Sized>(\n",
        "\n\nfn mode_requires_log_rescue(",
        "reciprocal-axis slice consumer",
    )
    require_ordered_tokens(
        reciprocal_operator,
        (
            "let dimension_data_storage = reciprocal_axis_data(",
            "validated.dimensions, cell.lengths_angstrom",
            "let [x_count, y_count, z_count] = validated.dimensions;",
            "dimension_data_storage.split_at(x_count);",
            "yz_axis_data.split_at(y_count);",
            "debug_assert_eq!(z_axis_data.len(), z_count);",
            "let dimension_data = [x_axis_data, y_axis_data, z_axis_data];",
            "let wave_squared = dimension_data[0][x].wave_squared",
            "+ dimension_data[1][y].wave_squared",
            "+ dimension_data[2][z].wave_squared;",
            "let assignment_modulus = dimension_data[0][x].assignment_modulus",
            "* dimension_data[1][y].assignment_modulus",
            "* dimension_data[2][z].assignment_modulus;",
        ),
        "single reciprocal-axis backing split before unchanged x-y-z arithmetic",
    )
    if (
        reciprocal_operator.count("reciprocal_axis_data(") != 1
        or reciprocal_operator.count(".split_at(") != 2
        or reciprocal_operator.count(".split_at_mut(") != 0
        or reciprocal_operator.count(
            "let dimension_data = [x_axis_data, y_axis_data, z_axis_data];"
        )
        != 1
    ):
        fail("reciprocal-axis immutable slice topology drift")
    for removed in (
        "let mut dimension_data = [Vec::new(), Vec::new(), Vec::new()];",
        "dimension_data.iter_mut()",
    ):
        if removed in reciprocal_operator:
            fail(f"per-axis owned allocation returned: {removed}")

    reciprocal_axis_allocator = source_region(
        rust,
        "fn reciprocal_axis_data(\n",
        "\n\nfn signed_mesh_index(",
        "single reciprocal-axis backing allocator",
    )
    require_ordered_tokens(
        reciprocal_axis_allocator,
        (
            "dimensions: [usize; 3],",
            "cell_lengths: [f64; 3],",
            "let data_count = dimensions",
            ".into_iter()",
            ".try_fold(0_usize, usize::checked_add)",
            '.expect("validated reciprocal axis-data count fits usize");',
            "let mut data = Vec::new();",
            "fallible_reserve_exact(&mut data, data_count, AllocationSite::ReciprocalAxisData)?;",
            "for axis in 0..3 {",
            "let dimension = dimensions[axis];",
            "let cell_length = cell_lengths[axis];",
            "for index in 0..dimension {",
            "let signed_index = signed_mesh_index(index, dimension);",
            "let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_length;",
            "let angle =",
            "bounded_usize_to_f64(dimension);",
            "data.push(ReciprocalAxisData {",
            "wave_squared: wave * wave,",
            "assignment_modulus: (2.0 + libm::cos(angle)) / 3.0,",
            "debug_assert_eq!(data.len(), data_count);",
            "Ok(data)",
        ),
        "one checked x-y-z reciprocal-axis backing allocation",
    )
    if (
        reciprocal_axis_allocator.count("fallible_reserve_exact(") != 1
        or reciprocal_axis_allocator.count("AllocationSite::ReciprocalAxisData")
        != 1
        or reciprocal_axis_allocator.count("for axis in 0..3") != 1
        or reciprocal_axis_allocator.count("data.push(ReciprocalAxisData {") != 1
    ):
        fail("single reciprocal-axis backing allocation or fill count drift")
    if "    dimension: usize,\n    cell_length: f64," in reciprocal_axis_allocator:
        fail("per-axis reciprocal-axis allocator signature returned")

    for removed in (
        "copy_validated_slice",
        "ProviderChannelCopy",
        "ProviderPositions",
    ):
        if removed in rust:
            fail(f"removed provider input-copy allocation returned: {removed}")

    borrowed_shape = source_region(
        rust,
        "struct BorrowedProviderInput<'a> {",
        "\n\nimpl ReciprocalInput for BorrowedProviderInput<'_>",
        "borrowed provider input shape",
    )
    for field in (
        "position_x: &'a [f64]",
        "position_y: &'a [f64]",
        "position_z: &'a [f64]",
        "charges_elementary: &'a [f64]",
        "cell: OrthorhombicCell",
        "settings: ParticleMeshReciprocalSettings",
    ):
        if borrowed_shape.count(field) != 1:
            fail(f"borrowed provider input field drift: {field}")
    for forbidden in ("Vec<", "*const", "*mut"):
        if forbidden in borrowed_shape:
            fail(f"borrowed provider input retained forbidden storage: {forbidden}")

    borrowed_channel = source_region(
        rust,
        "unsafe fn borrowed_provider_channel(",
        "\n\nunsafe fn provider_input<'a>(",
        "borrowed provider channel helper",
    )
    require_ordered_tokens(
        borrowed_channel,
        (
            "if system.atom_count == 0",
            "return &[];",
            "core::slice::from_raw_parts(pointer, system.atom_count)",
        ),
        "zero-count provider channel borrowing",
    )
    if borrowed_channel.count("core::slice::from_raw_parts") != 1:
        fail("borrowed provider channel raw-slice count drift")

    borrowed_constructor = source_region(
        rust,
        "unsafe fn provider_input<'a>(",
        "\n\nunsafe fn gather_forces_into_provider_output(",
        "borrowed provider input constructor",
    )
    for channel in (
        "borrowed_provider_channel(system, system.position_x)",
        "borrowed_provider_channel(system, system.position_y)",
        "borrowed_provider_channel(system, system.position_z)",
        "borrowed_provider_channel(system, system.charge)",
    ):
        if borrowed_constructor.count(channel) != 1:
            fail(f"borrowed provider channel construction drift: {channel}")
    if borrowed_constructor.count("borrowed_provider_channel(") != 4:
        fail("borrowed provider constructor channel count drift")
    for forbidden in ("Vec<", "Vec::", "reserve", ".collect", ".extend", "from_raw_parts"):
        if forbidden in borrowed_constructor:
            fail(f"provider constructor rematerializes input storage: {forbidden}")

    provider_candidate = source_region(
        rust,
        "struct ProviderCandidate {",
        "\n\n#[derive(Clone, Copy)]\nenum ProviderForceMode",
        "provider candidate ownership",
    )
    if "BorrowedProviderInput" in provider_candidate or "&'" in provider_candidate:
        fail("borrowed provider input escaped through ProviderCandidate")

    provider_impl = source_region(
        rust,
        "unsafe fn evaluate_provider_impl(",
        "\n\nunsafe fn validate_error_output(",
        "provider implementation",
    )
    borrow_call = "let input = unsafe { provider_input(&system, model) };"
    require_ordered_tokens(
        provider_impl,
        (
            "validate_header::<ParticleMeshReciprocalSystemV1>(",
            "if system.atom_count > MAX_PARTICLE_COUNT",
            "if output.capacity < system.atom_count",
            "require_disjoint_outputs(&mutable_ranges)?;",
            "for input_range in input_ranges.into_iter().flatten()",
            borrow_call,
            "let (reciprocal_space_kcal_per_mol, forces, force_output) = match force_mode",
        ),
        "complete provider preflight before call-local borrow and all-mode dispatch",
    )
    if provider_impl.count(borrow_call) != 1:
        fail("provider borrowed-input construction count drift")

    for shared in (
        "fn evaluate_with_force_option<I: ReciprocalInput + ?Sized>(",
        "fn evaluate_with_transform<I: ReciprocalInput + ?Sized>(",
        "fn compute_with_transform<I: ReciprocalInput + ?Sized>(",
        "fn apply_reciprocal_operator<I: ReciprocalInput + ?Sized>(",
        "fn validate<I: ReciprocalInput + ?Sized>(",
        "fn evaluate_with_direct_force_output<I: ReciprocalInput + ?Sized>(",
    ):
        if rust.count(shared) != 1:
            fail(f"owned/borrowed shared reciprocal pipeline drift: {shared}")

    allocation_enum = source_region(
        rust,
        "enum AllocationSite {",
        "\n}\n\nimpl AllocationSite",
        "remaining allocation sites",
    )
    for remaining in (
        "ParticleAssignments",
        "SpectrumAndFftLineScratch",
        "ReciprocalAxisData",
        "ForceOutput",
        "NeutralitySort",
    ):
        if allocation_enum.count(remaining) != 1:
            fail(f"remaining allocation site drift: {remaining}")
    for removed in ("    Spectrum,", "    FftLineScratch,"):
        if removed in allocation_enum:
            fail(f"separate allocation site returned: {removed.strip()}")

    allocation_details = source_region(
        rust,
        "impl AllocationSite {",
        "\n}\n\n#[derive(Clone, Copy, Debug, PartialEq, Eq)]\nstruct AllocationFailure",
        "allocation failure details",
    )
    if allocation_details.count(
        '"particle-mesh spectrum and FFT line-scratch allocation failed"'
    ) != 1:
        fail("combined spectrum/FFT-line allocation detail drift")
    for removed in (
        '"particle-mesh spectrum allocation failed"',
        '"FFT line-scratch allocation failed"',
    ):
        if removed in allocation_details:
            fail(f"separate allocation detail returned: {removed}")

    for test_contract in (
        "borrowed_provider_input_preserves_channel_identity_length_and_bits",
        "zero_count_provider_accepts_null_channels_without_forming_raw_slices",
        "owned_and_three_borrowed_output_modes_are_bit_identical_and_retain_inputs",
        "direct_provider_skips_force_allocation_and_preserves_outputs_on_earlier_oom",
        "direct_provider_preflights_capacity_and_aliases_before_force_writes",
        "late_scientific_failure_keeps_energy_transactional_and_direct_forces_disposable",
        "injected_allocation_failures_map_to_out_of_memory_without_output_commit",
        '"position_x", position_x.as_mut_ptr()',
        '"position_y", position_y.as_mut_ptr()',
        '"position_z", position_z.as_mut_ptr()',
        '"charge", charges.as_mut_ptr()',
    ):
        if rust.count(test_contract) != 1:
            fail(f"borrowed-input Rust regression contract drift: {test_contract}")
    if rust.count(
        "particle-mesh reciprocal output storage must not overlap input storage"
    ) != 2:
        fail("borrow-before-alias-rejection detail coverage drift")

    evaluator_header = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.hpp"
    ).read_text()
    header_contract = """struct ProviderForceSourceResult final {
    double reciprocal_space_kcal_per_mol = 0.0;
};
"""
    if evaluator_header.count(header_contract) != 1:
        fail("private provider force-source result shape drift")
    if evaluator_header.count("evaluate_reusing_provider_force_storage(") != 1:
        fail("private provider force-source evaluator declaration drift")

    evaluator = (
        root / "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
    ).read_text()
    for token in (
        "((out_evaluation == nullptr) ==\n         (out_provider_force_source_result == nullptr))",
        "out_provider_force_source_result != nullptr &&\n        (!compute_forces || !reuse_force_storage)",
        "compute_forces && reuse_force_storage && out_evaluation != nullptr",
        "if (out_evaluation != nullptr) {\n            candidate.forces.resize(atom_count);",
        "if (out_evaluation != nullptr) {\n        *out_evaluation = std::move(candidate);\n    } else {\n        *out_provider_force_source_result = ProviderForceSourceResult{",
        "bg_status evaluate_reusing_provider_force_storage(\n",
        "system, model, true, true, provider_force_scratch, nullptr,\n        out_result, out_error);",
    ):
        if evaluator.count(token) != 1:
            fail(f"provider force-source evaluator token drift: {token}")
    finite_scan = source_region(
        evaluator,
        "    if (compute_forces) {\n        if (out_evaluation != nullptr) {",
        "    if (out_evaluation != nullptr) {\n        *out_evaluation = std::move(candidate);",
        "provider force-source finite scan",
    )
    for token in (
        "std::isfinite(active_provider_force_scratch->x[atom])",
        "std::isfinite(active_provider_force_scratch->y[atom])",
        "std::isfinite(active_provider_force_scratch->z[atom])",
        "if (out_evaluation != nullptr)",
    ):
        if token not in finite_scan:
            fail(f"provider force-source finite-scan token missing: {token}")
    require_ordered_tokens(
        evaluator,
        (
            "const std::int32_t raw_status = direct_force_output",
            "if (!std::isfinite(provider_energy.reciprocal_space_kcal_per_mol))",
            "for (std::size_t atom = 0U; atom < atom_count; ++atom)",
            "*out_provider_force_source_result = ProviderForceSourceResult{",
        ),
        "provider finite validation and result commit",
    )

    composite = (
        root / "native/src/composite/particle_mesh_ewald_composite.cpp"
    ).read_text()
    rust_only_dispatch = """    const bool use_rust_reciprocal_provider_force_source =
        !cpp_lane && reuse_reciprocal_parent_force_storage;
    if (reuse_reciprocal_parent_force_storage && cpp_lane) {
        reciprocal_evaluation = reciprocal_parent_evaluation_scratch;
    }
"""
    if composite.count(rust_only_dispatch) != 1:
        fail("Rust-only stateful forceful force-source dispatch drift")
    provider_call = """        status = use_rust_reciprocal_provider_force_source
            ? particle_mesh_reciprocal::rust_cpu::
                  evaluate_reusing_provider_force_storage(
                      system, reciprocal_model,
                      rust_reciprocal_provider_force_scratch,
                      &rust_reciprocal_provider_result,
                      &reciprocal_error)
            : particle_mesh_reciprocal::rust_cpu::evaluate(
                  system, reciprocal_model, compute_forces,
                  reciprocal_evaluation, &reciprocal_error);
"""
    if composite.count(provider_call) != 1:
        fail("Rust provider force-source/stateless-force-free branch drift")
    if composite.count("reciprocal_evaluation = reciprocal_parent_evaluation_scratch;") != 1:
        fail("reciprocal-parent AoS assignment count drift")

    composite_finite = source_region(
        composite,
        "bool rust_reciprocal_provider_force_source_is_valid(\n",
        "\nbool short_system_scratch_shape_matches(\n",
        "composite provider force-source finite validation",
    )
    for token in (
        "force_source.x.size() != atom_count",
        "force_source.y.size() != atom_count",
        "force_source.z.size() != atom_count",
        "const std::array<const std::vector<double> *, 3> force_channels",
        "return !std::isfinite(value);",
    ):
        if token not in composite_finite:
            fail(f"composite provider finite-validation token missing: {token}")

    local_view = """    const auto reciprocal_force_at = [&](std::size_t atom) {
        if (use_rust_reciprocal_provider_force_source) {
            return std::array<double, 3>{{
                rust_reciprocal_provider_force_scratch->x[atom],
                rust_reciprocal_provider_force_scratch->y[atom],
                rust_reciprocal_provider_force_scratch->z[atom],
            }};
        }
        return reciprocal_result.forces[atom];
    };
"""
    if composite.count(local_view) != 1:
        fail("provider SoA local reciprocal-force view drift")

    preflight_start = composite.find(
        "    if (compute_forces) {\n        for (std::size_t atom = 0U; atom < atom_count; ++atom) {",
        composite.index("const auto reciprocal_force_at"),
    )
    commit_start = composite.find(
        "        if (stateful_force_output != nullptr) {",
        preflight_start,
    )
    if preflight_start < 0 or commit_start < 0 or commit_start <= preflight_start:
        fail("composite two-pass force transaction markers drift")
    preflight = composite[preflight_start:commit_start]
    if "parent_and_combined_forces" not in preflight or "std::any_of(" not in preflight:
        fail("composite full force preflight drift")
    for forbidden in (
        "stateful_force_output->force_x[atom] =",
        "stateful_force_output->force_y[atom] =",
        "stateful_force_output->force_z[atom] =",
    ):
        if forbidden in preflight:
            fail(f"final force write moved before full preflight: {forbidden}")
    require_ordered_tokens(
        composite[preflight_start:],
        (
            "parent_and_combined_forces",
            "std::any_of(",
            "if (stateful_force_output != nullptr)",
            "stateful_force_output->force_x.resize(atom_count);",
            "stateful_force_output->force_x[atom] =",
            "*out_evaluation = std::move(candidate);",
        ),
        "composite preflight and final force-SoA commit",
    )

    evaluator_doc = (
        root / "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp"
    ).read_text()
    for token in (
        "The C++ lane also reuses the reciprocal parent's Evaluation",
        "The Rust lane instead consumes the provider-facing reciprocal SoA",
        "leaves reciprocal-parent Evaluation storage\n * untouched",
        "Stateless force-producing calls retain the composite AoS force result.",
        "Force-free calls leave the private force storage",
    ):
        if token not in evaluator_doc:
            fail(f"C++/Rust/stateless/force-free contract documentation drift: {token}")

    native_test = native_test_raw.decode()
    for token in (
        "for (const bg_backend lane : {BG_BACKEND_CPP_CPU_REFERENCE})",
        "auto cpp_context = make_context(BG_BACKEND_CPP_CPU_REFERENCE);",
        "new Rust-lane PME reciprocal-parent force scratch was not empty",
        "C++ seed retained the wrong PME reciprocal-parent scratch size",
        "checkpoint load populated empty peer reciprocal-parent force scratch",
        "Rust integration rewrote stale reciprocal-parent force bits",
        "state-B Rust integration rewrote stale reciprocal-parent forces",
        "forceful Rust restart rewrote stale reciprocal-parent force bits",
        "Rust reciprocal-provider scratch differed from stateless reciprocal force bits",
        "checkpoint(simulation.get()) == before_alias",
    ):
        if token not in native_test:
            fail(f"provider force-source native regression token missing: {token}")

    rust = (root / "rust/cpu-kernel/src/particle_mesh_reciprocal.rs").read_text()
    test_region = rust.split("#[cfg(test)]\nmod tests", 1)[1]
    for token, expected_count in (
        ("fft_reuses_one_line_scratch_overwrites_poison_and_remains_reversible", 1),
        ("shared_fft_line_scratch_overwrites_poison_without_pipeline_bit_drift", 1),
        ("line_scratch.fill(Complex::new(f64::NAN, f64::NAN));", 3),
        ("assert_eq!(line_scratch.as_ptr(), line_pointer);", 2),
        ("assert_eq!(line_scratch.capacity(), line_capacity);", 2),
        ("frozen_provider_energy_and_twelve_force_bits_match", 1),
        ("injected_allocation_failures_map_to_out_of_memory_without_output_commit", 1),
    ):
        if test_region.count(token) != expected_count:
            fail(f"inherited FFT line-scratch regression contract drift: {token}")

    combined_layout_test = source_region(
        test_region,
        "    fn noncubic_spectrum_and_fft_line_storage_has_exact_contiguous_split() {\n",
        "\n\n    #[test]\n    fn fft_reuses_one_line_scratch_overwrites_poison_and_remains_reversible() {",
        "combined spectrum/FFT-line non-cubic layout regression",
    )
    require_ordered_tokens(
        combined_layout_test,
        (
            "dimensions: [4, 8, 16],",
            "mesh_point_count: 512,",
            "let mut storage = spectrum_and_fft_line_scratch(&validated)",
            "assert_eq!(storage.len(), 528);",
            "let storage_pointer = storage.as_ptr();",
            "storage.split_at_mut(validated.mesh_point_count);",
            "assert_eq!(spectrum.len(), 512);",
            "assert_eq!(fft_line_scratch.len(), 16);",
            "assert_eq!(spectrum.as_ptr(), storage_pointer);",
            "storage_pointer.add(512)",
        ),
        "checked mesh-plus-max-axis split lengths and pointer adjacency",
    )
    if (
        combined_layout_test.count("spectrum_and_fft_line_scratch(&validated)") != 1
        or combined_layout_test.count(".split_at_mut(validated.mesh_point_count)") != 1
        or combined_layout_test.count("storage_pointer.add(512)") != 1
    ):
        fail("combined spectrum/FFT-line layout coverage drift")

    provider_combined_test = source_region(
        test_region,
        "    fn provider_modes_share_one_spectrum_and_fft_line_storage_and_leave_second_occurrence_pending()\n",
        "\n\n    #[test]\n    fn direct_provider_preflights_capacity_and_aliases_before_force_writes() {",
        "all-provider combined spectrum/FFT-line occurrence regression",
    )
    combined_second_occurrence = (
        "AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 2)"
    )
    combined_pending = (
        "assert_injected_allocation_remains_pending(AllocationSite::SpectrumAndFftLineScratch);"
    )
    if (
        provider_combined_test.count(combined_second_occurrence) != 3
        or provider_combined_test.count(combined_pending) != 3
        or provider_combined_test.count("STATUS_OK") != 3
    ):
        fail("all-provider combined allocation occurrence coverage drift")
    for token, expected_count in (
        ("expected.reciprocal_space_kcal_per_mol.to_bits()", 3),
        ("expected.forces_kcal_per_mol_angstrom.iter().enumerate()", 1),
        ("transactional_x[particle].to_bits(),\n                expected_force[0].to_bits()", 1),
        ("transactional_y[particle].to_bits(),\n                expected_force[1].to_bits()", 1),
        ("transactional_z[particle].to_bits(),\n                expected_force[2].to_bits()", 1),
        ("assert_eq!(direct_x[particle].to_bits(), expected_force[0].to_bits());", 1),
        ("assert_eq!(direct_y[particle].to_bits(), expected_force[1].to_bits());", 1),
        ("assert_eq!(direct_z[particle].to_bits(), expected_force[2].to_bits());", 1),
        ("assert_eq!(transactional_x[4].to_bits(), 301.0_f64.to_bits());", 1),
        ("assert_eq!(transactional_y[4].to_bits(), 302.0_f64.to_bits());", 1),
        ("assert_eq!(transactional_z[4].to_bits(), 303.0_f64.to_bits());", 1),
        ("assert_eq!(direct_x[4].to_bits(), 601.0_f64.to_bits());", 1),
        ("assert_eq!(direct_y[4].to_bits(), 602.0_f64.to_bits());", 1),
        ("assert_eq!(direct_z[4].to_bits(), 603.0_f64.to_bits());", 1),
        ("for error in [&energy_only_error, &transactional_error, &direct_error]", 1),
        ("ParticleMeshReciprocalErrorCodeV1::None as i32", 1),
        ("assert!(error.detail.iter().all(|byte| *byte == 0));", 1),
        ("assert_eq!(position_x.map(f64::to_bits), input_before[0]);", 1),
        ("assert_eq!(position_y.map(f64::to_bits), input_before[1]);", 1),
        ("assert_eq!(position_z.map(f64::to_bits), input_before[2]);", 1),
        ("assert_eq!(charges.map(f64::to_bits), input_before[3]);", 1),
    ):
        if provider_combined_test.count(token) != expected_count:
            fail(f"all-provider combined exact-output contract drift: {token}")

    axis_layout_test = source_region(
        test_region,
        "    fn reciprocal_axes_share_one_contiguous_noncubic_backing() {\n",
        "\n\n    #[test]\n    fn log_rescue_preserves_normal_and_subnormal_force_domains() {",
        "reciprocal-axis backing layout regression",
    )
    require_ordered_tokens(
        axis_layout_test,
        (
            "let dimensions = [4, 8, 16];",
            "let cell_lengths = [18.0, 20.0, 22.0];",
            "let storage = reciprocal_axis_data(dimensions, cell_lengths)",
            "assert_eq!(storage.len(), dimensions.into_iter().sum::<usize>());",
            "let (x_axis_data, yz_axis_data) = storage.split_at(dimensions[0]);",
            "let (y_axis_data, z_axis_data) = yz_axis_data.split_at(dimensions[1]);",
            "[x_axis_data.len(), y_axis_data.len(), z_axis_data.len()]",
            "x_axis_data.as_ptr().wrapping_add(x_axis_data.len())",
            "y_axis_data.as_ptr()",
            "y_axis_data.as_ptr().wrapping_add(y_axis_data.len())",
            "z_axis_data.as_ptr()",
            "let axes = [x_axis_data, y_axis_data, z_axis_data];",
            "for (axis, axis_data) in axes.into_iter().enumerate() {",
            "let signed_index = signed_mesh_index(index, dimensions[axis]);",
            "cell_lengths[axis]",
            "bounded_usize_to_f64(dimensions[axis]);",
            "assert_eq!(datum.wave_squared.to_bits(), (wave * wave).to_bits());",
            "datum.assignment_modulus.to_bits()",
            "((2.0 + libm::cos(angle)) / 3.0).to_bits()",
        ),
        "non-cubic reciprocal-axis lengths offsets and exact values",
    )
    if (
        axis_layout_test.count(
            "x_axis_data.as_ptr().wrapping_add(x_axis_data.len())"
        )
        != 1
        or axis_layout_test.count(
            "y_axis_data.as_ptr().wrapping_add(y_axis_data.len())"
        )
        != 1
    ):
        fail("reciprocal-axis slice adjacency coverage drift")

    provider_axis_test = source_region(
        test_region,
        "    fn provider_modes_share_one_reciprocal_axis_backing_and_leave_second_occurrence_pending() {\n",
        "\n\n    #[test]\n    fn provider_modes_share_one_spectrum_and_fft_line_storage_and_leave_second_occurrence_pending()\n",
        "all-provider reciprocal-axis occurrence regression",
    )
    axis_second_occurrence = (
        "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 2)"
    )
    axis_pending = (
        "assert_injected_allocation_remains_pending(AllocationSite::ReciprocalAxisData);"
    )
    if (
        provider_axis_test.count(axis_second_occurrence) != 3
        or provider_axis_test.count(axis_pending) != 3
        or provider_axis_test.count("STATUS_OK") != 3
    ):
        fail("all-provider reciprocal-axis second-occurrence coverage drift")
    for token in (
        "for actual_energy in [&energy_only, &transactional_energy, &direct_energy]",
        "expected.reciprocal_space_kcal_per_mol.to_bits()",
        "expected.forces_kcal_per_mol_angstrom.iter().enumerate()",
        "transactional_x[particle].to_bits(),\n                expected_force[0].to_bits()",
        "transactional_y[particle].to_bits(),\n                expected_force[1].to_bits()",
        "transactional_z[particle].to_bits(),\n                expected_force[2].to_bits()",
        "assert_eq!(direct_x[particle].to_bits(), expected_force[0].to_bits());",
        "assert_eq!(direct_y[particle].to_bits(), expected_force[1].to_bits());",
        "assert_eq!(direct_z[particle].to_bits(), expected_force[2].to_bits());",
        "assert_eq!(transactional_x[4].to_bits(), 401.0_f64.to_bits());",
        "assert_eq!(transactional_y[4].to_bits(), 402.0_f64.to_bits());",
        "assert_eq!(transactional_z[4].to_bits(), 403.0_f64.to_bits());",
        "assert_eq!(direct_x[4].to_bits(), 701.0_f64.to_bits());",
        "assert_eq!(direct_y[4].to_bits(), 702.0_f64.to_bits());",
        "assert_eq!(direct_z[4].to_bits(), 703.0_f64.to_bits());",
        "for error in [&energy_only_error, &transactional_error, &direct_error]",
        "ParticleMeshReciprocalErrorCodeV1::None as i32",
        "assert!(error.detail.iter().all(|byte| *byte == 0));",
        "assert_eq!(position_x.map(f64::to_bits), input_before[0]);",
        "assert_eq!(position_y.map(f64::to_bits), input_before[1]);",
        "assert_eq!(position_z.map(f64::to_bits), input_before[2]);",
        "assert_eq!(charges.map(f64::to_bits), input_before[3]);",
    ):
        if provider_axis_test.count(token) != 1:
            fail(f"all-provider reciprocal-axis exact-output contract drift: {token}")

    direct_prewrite_test = source_region(
        test_region,
        "    fn direct_provider_skips_force_allocation_and_preserves_outputs_on_earlier_oom() {\n",
        "\n\n    #[test]\n    fn provider_modes_share_one_reciprocal_axis_backing_and_leave_second_occurrence_pending() {",
        "direct reciprocal-axis last-prewrite boundary",
    )
    if direct_prewrite_test.count(
        "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 1)"
    ) != 1:
        fail("direct reciprocal-axis first-occurrence boundary drift")
    direct_axis_oom = direct_prewrite_test[
        direct_prewrite_test.index("        let mut energy = initialized_energy(701.0);") :
        direct_prewrite_test.index("        let mut energy = initialized_energy(1_001.0);")
    ]
    for token in (
        "output.capacity = 4;",
        "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 1)",
        "assert_eq!(status, STATUS_OUT_OF_MEMORY);",
        "energy.reciprocal_space_kcal_per_mol.to_bits(),\n            701.0_f64.to_bits()",
    ):
        if direct_axis_oom.count(token) != 1:
            fail(f"direct reciprocal-axis first-occurrence OOM drift: {token}")
    if test_region.count(axis_second_occurrence) != 3:
        fail("reciprocal-axis occurrence-two injection count drift")
    if test_region.count(
        "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalAxisData, 3)"
    ) != 0:
        fail("removed reciprocal-axis third occurrence returned")
    for sentinel in (
        "assert_eq!(force_x, [801.0, 801.0, 801.0, 801.0, 901.0]);",
        "assert_eq!(force_y, [802.0, 802.0, 802.0, 802.0, 902.0]);",
        "assert_eq!(force_z, [803.0, 803.0, 803.0, 803.0, 903.0]);",
    ):
        if direct_prewrite_test.count(sentinel) != 1:
            fail(f"last direct pre-write OOM sentinel drift: {sentinel}")
    for token in (
        "assert_eq!(position_x.map(f64::to_bits), input_before[0]);",
        "assert_eq!(position_y.map(f64::to_bits), input_before[1]);",
        "assert_eq!(position_z.map(f64::to_bits), input_before[2]);",
        "assert_eq!(charges.map(f64::to_bits), input_before[3]);",
    ):
        if direct_axis_oom.count(token) != 1:
            fail(f"direct reciprocal-axis OOM input-retention drift: {token}")

    direct_combined_oom = direct_prewrite_test[
        direct_prewrite_test.index("        let mut energy = initialized_energy(1_001.0);") :
    ]
    for token in (
        "output.capacity = 4;",
        "AllocationFailureGuard::inject_at(AllocationSite::SpectrumAndFftLineScratch, 1)",
        "assert_eq!(status, STATUS_OUT_OF_MEMORY);",
        "AllocationSite::SpectrumAndFftLineScratch.detail()",
        "energy.reciprocal_space_kcal_per_mol.to_bits(),\n            1_001.0_f64.to_bits()",
        "assert_eq!(force_x, [1_101.0, 1_101.0, 1_101.0, 1_101.0, 1_201.0]);",
        "assert_eq!(force_y, [1_102.0, 1_102.0, 1_102.0, 1_102.0, 1_202.0]);",
        "assert_eq!(force_z, [1_103.0, 1_103.0, 1_103.0, 1_103.0, 1_203.0]);",
        "assert_eq!(position_x.map(f64::to_bits), input_before[0]);",
        "assert_eq!(position_y.map(f64::to_bits), input_before[1]);",
        "assert_eq!(position_z.map(f64::to_bits), input_before[2]);",
        "assert_eq!(charges.map(f64::to_bits), input_before[3]);",
    ):
        if direct_combined_oom.count(token) != 1:
            fail(f"direct combined-allocation OOM boundary drift: {token}")
    if test_region.count(combined_second_occurrence) != 3:
        fail("combined allocation occurrence-two injection count drift")
    for token in (
        "late_scientific_failure_keeps_energy_transactional_and_direct_forces_disposable",
        "ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32",
        "assert_ne!(direct_x, [401.0; 4]);",
        "A late scientific failure or panic may therefore modify force channels;",
        "energy remains transactional and is committed only on success.",
    ):
        if rust.count(token) != 1:
            fail(f"late direct-provider transaction boundary drift: {token}")

def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_contract(root)
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
