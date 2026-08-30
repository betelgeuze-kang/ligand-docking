#!/usr/bin/env python3
"""Verify one call-local reciprocal workspace reused across ordered phases."""
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
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-reciprocal-workspace-phase-reuse.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-rust-reciprocal-provider-spectrum-fft-line-buffer-consolidation.yml"
)
MACOS_RETRY_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json"
)
PREDECESSOR_DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.md"
)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py"
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
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_sources/1.0.0"
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
    "pull_request": 462,
    "reviewed_head": "e12c9fd82a0376bc7d83d6e83a28b9c950f321b5",
    "merge_commit": "761e979e36b048cc19f3ef3ff4a90d373e1e8315",
    "merge_tree": "222129db34948751bcadd391bde11943898b8f91",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "37c49e09578bd5ef369b3bdb19a119d7245fc236a898c27146c8b86276cda902"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "f60c398fb3d6d657264734712d08a84edadd67bfabac7c66ebb49ab94c5c31ba"
    ),
    "source_manifest_entry_count": 302,
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
    '.github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-rust-reciprocal-provider-reciprocal-workspace-phase-reuse.yml',
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
    "e78e45d36f56d22ae4dae0258b286fc186c1109dab9ccaa53ef74c5cdcbfea0b"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "b74cde97978b3a0c608f52b6fefd2dbf8279ac77828f08c2df7418c1c37ae780"
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
      - name: Materialize exact PR 462 target, PR 453 architecture, PR 440 inherited evaluator, and PR 380 direct-output precedent
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 761e979e36b048cc19f3ef3ff4a90d373e1e8315^{tree})" = "222129db34948751bcadd391bde11943898b8f91"
          git merge-base --is-ancestor 761e979e36b048cc19f3ef3ff4a90d373e1e8315 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/462/head
          test "$(git rev-parse FETCH_HEAD)" = "e12c9fd82a0376bc7d83d6e83a28b9c950f321b5"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "222129db34948751bcadd391bde11943898b8f91"
          test "$(git rev-parse 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          git merge-base --is-ancestor 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a 761e979e36b048cc19f3ef3ff4a90d373e1e8315
          git fetch --no-tags --depth=1 origin refs/pull/453/head
          test "$(git rev-parse FETCH_HEAD)" = "68607f1b4c1311755b565a2ace2e681695d7f764"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "b22c5fd115a5c8e28856872df57127ecdd28d9b5"
          test "$(git rev-parse 735883551510cbef91adc3e57dc131a1234b67fb^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          git merge-base --is-ancestor 735883551510cbef91adc3e57dc131a1234b67fb 35a8f0b0ba0e079bc2a1edee15d19ef2c2823f2a
          git fetch --no-tags --depth=1 origin refs/pull/440/head
          test "$(git rev-parse FETCH_HEAD)" = "098bce0d726dbed6e4bf7b533e0445f81e244ea2"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "6c2b6f3960b6df0592b78bb44e429389aa58bcbb"
          test "$(git rev-parse 6662f1b53829930a93de0f298b820d5a367cc3dc^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
          git merge-base --is-ancestor 6662f1b53829930a93de0f298b820d5a367cc3dc 761e979e36b048cc19f3ef3ff4a90d373e1e8315
          git fetch --no-tags --depth=1 origin refs/pull/380/head
          test "$(git rev-parse FETCH_HEAD)" = "c486e767b1452cffb9cfd998bc26d5e4403bbd76"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "5a2d296e891fe89f3d48c3c6d7b1deb61e81a177"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_v1.py
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-release --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-release -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-sanitize --target betelgeuze_engine_particle_mesh_reciprocal betelgeuze_engine_particle_mesh_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-sanitize -R '^betelgeuze_engine_(particle_mesh_reciprocal|particle_mesh_ewald_composite_dynamics)$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-cargo
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
          cmake -S . -B build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/particle-mesh-ewald-rust-reciprocal-provider-reciprocal-workspace-phase-reuse-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
        "rust-reciprocal-provider-reciprocal-workspace-phase-reuse\n\n"
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
        "rust-reciprocal-provider-reciprocal-workspace-phase-reuse-${{ github.ref }}\n"
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
            "reciprocal_workspace_phase_reuse_current_sources_tests_evidence_target_"
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
            "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_development_v1"
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
            "reciprocal_workspace_uses_one_call_local_complex_backing": True,
            "reciprocal_workspace_backing_length_is_mesh_plus_axis_sum": True,
            "reciprocal_workspace_spectrum_and_tail_contiguous_and_non_overlapping": True,
            "reciprocal_workspace_single_reserve_per_provider_evaluation": True,
            "reciprocal_workspace_tail_forward_fft_axis_inverse_phase_reuse": True,
            "reciprocal_workspace_tail_not_retained": True,
            "spectrum_fft_line_and_axis_reserves_consolidated": True,
            "two_call_local_cluster_reserves_reduced_to_one": True,
            "reciprocal_axis_data_separate_allocation_removed": True,
            "reciprocal_axis_data_encoded_in_complex_real_and_imaginary": True,
            "spectrum_nonfinite_scan_excludes_reciprocal_tail": True,
            "combined_allocation_error_detail_and_failure_timing_intentionally_changed": True,
            "status_abi_preserved": True,
            "reciprocal_axis_data_backing_length_is_sum_of_mesh_dimensions": True,
            "reciprocal_axis_data_x_y_z_slices_contiguous_and_non_overlapping": True,
            "reciprocal_axis_data_arithmetic_and_axis_order_preserved": True,
            "reciprocal_axis_data_not_retained": True,
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
            "reciprocal_workspace_capacity_equality_claimed": False,
            "reciprocal_workspace_storage_allocation_free_claimed": False,
            "persistent_reciprocal_workspace_reuse_claimed": False,
            "cross_call_reciprocal_workspace_reuse_claimed": False,
            "owner_reciprocal_workspace_reuse_claimed": False,
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
            "single_reciprocal_workspace_reserve_occurrence_exact": True,
            "reciprocal_workspace_checked_mesh_plus_axis_sum_exact": True,
            "reciprocal_workspace_split_lengths_offsets_and_non_overlap_exact": True,
            "reciprocal_workspace_phase_reborrows_non_overlapping_and_ordered": True,
            "second_reciprocal_workspace_occurrence_injection_succeeds_exact_bits": True,
            "first_reciprocal_workspace_oom_transactional_with_combined_detail": True,
            "combined_allocation_detail_and_failure_timing_change_explicitly_bounded": True,
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
        "refs/pull/462/head",
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
        "      - name: Materialize exact PR 461 target, PR 453 architecture, "
        "PR 440 inherited evaluator, and PR 380 direct-output precedent\n",
        "      - name: Verify bounded successor evidence\n",
        "frozen predecessor materialization",
    )
    new_materialize = """      - name: Materialize exact PR 462 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 761e979e36b048cc19f3ef3ff4a90d373e1e8315^{tree})" = "222129db34948751bcadd391bde11943898b8f91"
          git merge-base --is-ancestor 761e979e36b048cc19f3ef3ff4a90d373e1e8315 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/462/head
          test "$(git rev-parse FETCH_HEAD)" = "e12c9fd82a0376bc7d83d6e83a28b9c950f321b5"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "222129db34948751bcadd391bde11943898b8f91"
"""
    expected = replace_exact(
        expected, old_materialize, new_materialize, "predecessor materialization"
    )
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 462 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=761e979e36b048cc19f3ef3ff4a90d373e1e8315
          frozen_tree=222129db34948751bcadd391bde11943898b8f91
          current_sha="$(git rev-parse HEAD)"
          restore() {
            git checkout --detach --quiet "$current_sha"
          }
          trap restore EXIT
          test "$(git rev-parse "$frozen"^{tree})" = "$frozen_tree"
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD)" = "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_spectrum_fft_line_buffer_consolidation_v1.py
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
    addition = """PME_RUST_RECIPROCAL_PROVIDER_RECIPROCAL_WORKSPACE_PHASE_REUSE_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_reciprocal_workspace_phase_reuse_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_RECIPROCAL_WORKSPACE_PHASE_REUSE_EVIDENCE_PRESENT,
    reason=(
        "PME Rust reciprocal provider spectrum/FFT-line buffer consolidation "
        "evidence is verified from its exact frozen PR 462 object after "
        "reciprocal workspace phase-reuse evidence is present"
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
EXPECTED_PREDECESSOR_RUST_RECIPROCAL_SHA256 = (
    "0faf26257c71bcd1ba806c427b7dd493edf8e6393ab5083aefa2b2f53193f0df"
)
EXPECTED_RUST_RECIPROCAL_SHA256 = (
    "8a7c51bd992ceb1815bb33149699a74ee76a1dbc81ae096f25c776b318cba72e"
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


def require_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_contract(
    root: Path = ROOT,
) -> None:
    if IMPLEMENTATION_DELTA_PATHS != (RUST_RECIPROCAL_RELATIVE_PATH,):
        fail("reciprocal-workspace phase-reuse production path set drift")

    merge = PREDECESSOR["merge_commit"]
    for relative, digest in EXPECTED_PREDECESSOR_PRODUCTION_SHA256.items():
        raw = (root / relative).read_bytes()
        if sha(raw) != digest:
            fail(f"exact predecessor production drift: {relative}")
        if git("show", f"{merge}:{relative}").stdout != raw:
            fail(f"predecessor production path changed: {relative}")

    native_test_raw = (root / NATIVE_TEST_RELATIVE_PATH).read_bytes()
    if sha(native_test_raw) != EXPECTED_NATIVE_TEST_SHA256:
        fail("exact predecessor native regression drift")
    if git("show", f"{merge}:{NATIVE_TEST_RELATIVE_PATH.as_posix()}").stdout != native_test_raw:
        fail("predecessor native regression changed")

    if len(CANONICAL_VENDOR_MIRROR_PAIRS) != 4:
        fail("canonical/vendor mirror pair count drift")
    for relative in CANONICAL_VENDOR_MIRROR_PAIRS:
        canonical = root / "native/src" / relative
        vendor = root / "rust/betelgeuze-sys/vendor/native/src" / relative
        if canonical.read_bytes() != vendor.read_bytes():
            fail(f"canonical/vendor mirror drift: {relative}")

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

    predecessor_rust_raw = git(
        "show", f"{merge}:{RUST_RECIPROCAL_RELATIVE_PATH.as_posix()}"
    ).stdout
    if sha(predecessor_rust_raw) != EXPECTED_PREDECESSOR_RUST_RECIPROCAL_SHA256:
        fail("exact predecessor Rust source drift")
    rust_raw = (root / RUST_RECIPROCAL_RELATIVE_PATH).read_bytes()
    if sha(rust_raw) != EXPECTED_RUST_RECIPROCAL_SHA256:
        fail("exact reciprocal-workspace phase-reuse Rust source drift")
    if rust_raw == predecessor_rust_raw:
        fail("reciprocal-workspace phase-reuse Rust source did not change")

    rust = rust_raw.decode()
    production, separator, test_region = rust.partition("#[cfg(test)]\nmod tests")
    if not separator:
        fail("Rust test module boundary drift")
    for removed in (
        "SpectrumAndFftLineScratch",
        "ReciprocalAxisData",
        "struct ReciprocalAxisData",
        "fn spectrum_and_fft_line_scratch(",
        "fn reciprocal_axis_data(",
    ):
        if removed in production:
            fail(f"removed separate reciprocal allocation returned: {removed}")

    allocation_sites = source_region(
        production,
        "enum AllocationSite {\n",
        "\n\nimpl AllocationSite",
        "allocation-site enum",
    )
    for site in (
        "ParticleAssignments",
        "ReciprocalWorkspace",
        "ForceOutput",
        "NeutralitySort",
    ):
        if allocation_sites.count(site) != 1:
            fail(f"allocation-site enum drift: {site}")
    if allocation_sites.count(",") != 4:
        fail("allocation-site enum cardinality drift")
    exact_detail = (
        "particle-mesh spectrum, FFT line-scratch, and reciprocal axis-data "
        "allocation failed"
    )
    if production.count(exact_detail) != 1:
        fail("reciprocal-workspace allocation detail drift")

    workspace = source_region(
        production,
        "struct ReciprocalWorkspace {\n",
        "\n\n#[derive(Clone, Copy)]\nenum ForceStorageMode",
        "reciprocal workspace owner",
    )
    require_ordered_tokens(
        workspace,
        (
            "storage: Vec<Complex>",
            "fn new(validated: &ValidatedInput)",
            "let axis_data_count = reciprocal_axis_data_count(validated.dimensions);",
            ".mesh_point_count",
            ".checked_add(axis_data_count)",
            '.expect("validated reciprocal workspace count fits usize");',
            "let mut storage = Vec::new();",
            "fallible_reserve_exact(",
            "storage_count,",
            "AllocationSite::ReciprocalWorkspace,",
            "storage.resize(storage_count, Complex::default());",
            "Ok(Self { storage })",
            "fn reciprocal_axis_data_count(dimensions: [usize; 3]) -> usize",
            ".try_fold(0_usize, usize::checked_add)",
        ),
        "one checked mesh-plus-axis-sum backing reserve",
    )
    if (
        workspace.count("fallible_reserve_exact(") != 1
        or workspace.count("AllocationSite::ReciprocalWorkspace") != 1
        or workspace.count("Vec<Complex>") != 1
        or workspace.count(".checked_add(axis_data_count)") != 1
    ):
        fail("reciprocal workspace reserve topology drift")

    fft_transform = source_region(
        production,
        "    pub(crate) fn fft_3d(\n",
        "\n\n    fn fft_1d(",
        "caller-supplied FFT transform",
    )
    transform_3d = source_region(
        production,
        "    fn transform_3d_with(\n",
        "\n\n    pub(crate) const fn index(",
        "caller-supplied three-dimensional transform",
    )
    for label, region in (("fft_3d", fft_transform), ("transform_3d", transform_3d)):
        if "line: &mut [Complex]" not in region:
            fail(f"{label} caller scratch contract drift")
        for forbidden in ("Vec::", "Vec<", "reserve", "resize"):
            if forbidden in region:
                fail(f"{label} recreated owned FFT scratch: {forbidden}")
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
        production,
        "fn compute_with_transform<I: ReciprocalInput + ?Sized>(\n",
        "\n\nstruct ReciprocalOperator {",
        "shared reciprocal calculation",
    )
    require_ordered_tokens(
        compute,
        (
            "let validated = validate(input)?;",
            "AllocationSite::ParticleAssignments,",
            "let mut reciprocal_workspace =",
            "ReciprocalWorkspace::new(&validated)",
            "let line_count = validated.dimensions.into_iter().max().unwrap_or(0);",
            ".storage",
            ".split_at_mut(validated.mesh_point_count);",
            "spread_charges(spectrum, validated.dimensions, &assignments, charges);",
            "&mut reciprocal_tail[..line_count],",
            "fill_reciprocal_axis_data(",
            "&mut *reciprocal_tail,",
            "apply_reciprocal_operator(input, &validated, spectrum, &*reciprocal_tail);",
            "if matches!(",
            "&mut reciprocal_tail[..line_count],",
            "gather_forces(",
        ),
        "forward-scratch axis-data inverse-scratch phase order",
    )
    if (
        compute.count("ReciprocalWorkspace::new(&validated)") != 1
        or compute.count(".split_at_mut(validated.mesh_point_count)") != 1
        or compute.count("&mut reciprocal_tail[..line_count]") != 2
        or compute.count("fill_reciprocal_axis_data(") != 1
        or compute.count("apply_reciprocal_operator(") != 1
        or "fft_line_scratch" in compute
    ):
        fail("reciprocal workspace phase reborrow count drift")
    if (
        "spectrum\n            .iter()" not in compute
        or "reciprocal_tail.iter().any" in compute
        or "reciprocal_workspace.storage.iter" in compute
    ):
        fail("nonfinite scan must remain spectrum-only")

    axis_fill = source_region(
        production,
        "fn fill_reciprocal_axis_data(\n",
        "\n\nfn signed_mesh_index(",
        "in-place reciprocal-axis fill",
    )
    require_ordered_tokens(
        axis_fill,
        (
            "storage: &mut [Complex],",
            "debug_assert_eq!(storage.len(), reciprocal_axis_data_count(dimensions));",
            "let mut storage_index = 0;",
            "for axis in 0..3 {",
            "let dimension = dimensions[axis];",
            "let cell_length = cell_lengths[axis];",
            "for index in 0..dimension {",
            "let signed_index = signed_mesh_index(index, dimension);",
            "let wave = core::f64::consts::TAU * f64::from(signed_index) / cell_length;",
            "storage[storage_index] = Complex::new(wave * wave, (2.0 + libm::cos(angle)) / 3.0);",
            "storage_index += 1;",
            "debug_assert_eq!(storage_index, storage.len());",
        ),
        "x-y-z Complex real-imaginary axis fill",
    )
    for forbidden in ("Vec<", "Vec::", "reserve", ".push(", "unsafe"):
        if forbidden in axis_fill:
            fail(f"in-place reciprocal-axis fill owns forbidden storage: {forbidden}")

    reciprocal_operator = source_region(
        production,
        "fn apply_reciprocal_operator<I: ReciprocalInput + ?Sized>(\n",
        "\n\nfn mode_requires_log_rescue(",
        "reciprocal operator",
    )
    require_ordered_tokens(
        reciprocal_operator,
        (
            "reciprocal_axis_data: &[Complex],",
            ") -> ReciprocalOperator {",
            "reciprocal_axis_data.split_at(x_count);",
            "yz_axis_data.split_at(y_count);",
            "let dimension_data = [x_axis_data, y_axis_data, z_axis_data];",
            "let wave_squared = dimension_data[0][x].real",
            "+ dimension_data[1][y].real",
            "+ dimension_data[2][z].real;",
            "let assignment_modulus = dimension_data[0][x].imaginary",
            "* dimension_data[1][y].imaginary",
            "* dimension_data[2][z].imaginary;",
        ),
        "immutable x-y-z Complex axis consumer",
    )
    for forbidden in ("Vec<", "Vec::", "reserve", "AllocationSite::", "unsafe"):
        if forbidden in reciprocal_operator:
            fail(f"reciprocal operator recreated forbidden storage: {forbidden}")

    layout_test = source_region(
        test_region,
        "    fn reciprocal_workspace_has_exact_noncubic_spectrum_and_axis_tail_layout() {\n",
        "\n\n    #[test]\n    fn log_rescue_preserves_normal_and_subnormal_force_domains() {",
        "non-cubic reciprocal-workspace layout regression",
    )
    require_ordered_tokens(
        layout_test,
        (
            "let dimensions = [4, 8, 16];",
            "mesh_point_count: 512,",
            "ReciprocalWorkspace::new(&validated)",
            "assert_eq!(workspace.storage.len(), 540);",
            "split_at_mut(validated.mesh_point_count);",
            "assert_eq!(spectrum.len(), 512);",
            "assert_eq!(reciprocal_tail.len(), 28);",
            "fill_reciprocal_axis_data(reciprocal_tail, dimensions, cell_lengths);",
            "reciprocal_tail.split_at(dimensions[0]);",
            "yz_axis_data.split_at(dimensions[1]);",
            "datum.real.to_bits()",
            "datum.imaginary.to_bits()",
        ),
        "M512 A28 total540 offsets0-4-12 exact axis bits",
    )
    if ".capacity()" in layout_test:
        fail("fallible reserve capacity equality must not be claimed")

    phase_test = source_region(
        test_region,
        "    fn reciprocal_workspace_tail_reuses_fft_prefix_around_exact_axis_phase() {\n",
        "\n\n    #[test]\n    fn fft_reuses_one_line_scratch_overwrites_poison_and_remains_reversible() {",
        "reciprocal workspace phase-reuse regression",
    )
    require_ordered_tokens(
        phase_test,
        (
            "assert_eq!(line_count, 16);",
            "let tail_pointer = reciprocal_tail.as_ptr();",
            "reciprocal_tail.fill(Complex::new(f64::NAN, f64::NAN));",
            "false,",
            "&mut reciprocal_tail[..line_count],",
            "reciprocal_tail[line_count..]",
            "fill_reciprocal_axis_data(reciprocal_tail, dimensions, input.cell.lengths_angstrom);",
            "let axis_bits = reciprocal_tail",
            "apply_reciprocal_operator(&input, &validated, spectrum, reciprocal_tail);",
            "reciprocal_tail[..line_count].fill(Complex::new(f64::NAN, f64::NAN));",
            "true,",
            "&mut reciprocal_tail[..line_count],",
            "assert_eq!(reciprocal_tail.as_ptr(), tail_pointer);",
            "axis_bits[line_count..]",
        ),
        "forward poison axis overwrite inverse prefix tail-suffix preservation",
    )
    if ".capacity()" in phase_test:
        fail("phase-reuse regression must not assert allocator capacity equality")

    provider_test = source_region(
        test_region,
        "    fn provider_modes_share_one_reciprocal_workspace_and_leave_second_occurrence_pending() {\n",
        "\n\n    #[test]\n    fn first_reciprocal_workspace_oom_is_transactional_in_all_provider_modes() {",
        "all-provider reciprocal-workspace occurrence-two regression",
    )
    second = "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 2)"
    pending = "assert_injected_allocation_remains_pending(AllocationSite::ReciprocalWorkspace);"
    if (
        provider_test.count(second) != 3
        or provider_test.count(pending) != 3
        or provider_test.count("STATUS_OK") != 3
    ):
        fail("all-provider reciprocal-workspace occurrence-two coverage drift")
    for token in (
        "expected.reciprocal_space_kcal_per_mol.to_bits()",
        "expected.forces_kcal_per_mol_angstrom.iter().enumerate()",
        "for error in [&energy_only_error, &transactional_error, &direct_error]",
        "assert!(error.detail.iter().all(|byte| *byte == 0));",
        "assert_eq!(position_x.map(f64::to_bits), input_before[0]);",
        "assert_eq!(charges.map(f64::to_bits), input_before[3]);",
    ):
        if token not in provider_test:
            fail(f"all-provider exact result retention drift: {token}")

    oom_test = source_region(
        test_region,
        "    fn first_reciprocal_workspace_oom_is_transactional_in_all_provider_modes() {\n",
        "\n\n    #[test]\n    fn direct_provider_preflights_capacity_and_aliases_before_force_writes() {",
        "all-provider reciprocal-workspace first-OOM regression",
    )
    first = "AllocationFailureGuard::inject_at(AllocationSite::ReciprocalWorkspace, 1)"
    if oom_test.count(first) != 3 or oom_test.count("STATUS_OUT_OF_MEMORY") != 3:
        fail("all-provider reciprocal-workspace first-OOM coverage drift")
    if oom_test.count("AllocationSite::ReciprocalWorkspace.detail()") != 1:
        fail("combined reciprocal-workspace OOM detail coverage drift")
    for token in (
        "assert_eq!(transactional_x, [201.0, 201.0, 201.0, 201.0, 301.0]);",
        "assert_eq!(direct_x, [501.0, 501.0, 501.0, 501.0, 601.0]);",
        "assert_eq!(position_x.map(f64::to_bits), input_before[0]);",
        "assert_eq!(charges.map(f64::to_bits), input_before[3]);",
    ):
        if token not in oom_test:
            fail(f"first reciprocal-workspace OOM transaction drift: {token}")

    allocation_test = source_region(
        test_region,
        "    fn injected_allocation_failures_map_to_out_of_memory_without_output_commit() {\n",
        "\n\n    fn descriptor_bytes<T>(value: *const T) -> Vec<u8> {",
        "remaining allocation-site regression",
    )
    transactional_sites = """        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
            AllocationSite::ForceOutput,
        ] {"""
    force_free_sites = """        for site in [
            AllocationSite::NeutralitySort,
            AllocationSite::ParticleAssignments,
            AllocationSite::ReciprocalWorkspace,
        ] {"""
    if allocation_test.count(transactional_sites) != 1:
        fail("transactional allocation-site count must remain four")
    if allocation_test.count(force_free_sites) != 1:
        fail("energy-only allocation-site count must remain three")

    if (4 + 4 + 4) - max(4, 4, 4) != 8 or 8 * 16 != 128:
        fail("[4,4,4] P4096 gather live-payload counterexample arithmetic drift")
    for token in (
        "late_scientific_failure_keeps_energy_transactional_and_direct_forces_disposable",
        "ParticleMeshReciprocalErrorCodeV1::NonFiniteResult as i32",
        "A late scientific failure or panic may therefore modify force channels;",
        "energy remains transactional and is committed only on success.",
    ):
        if rust.count(token) != 1:
            fail(f"late scientific transaction boundary drift: {token}")

def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_rust_reciprocal_provider_reciprocal_workspace_phase_reuse_contract(root)
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
