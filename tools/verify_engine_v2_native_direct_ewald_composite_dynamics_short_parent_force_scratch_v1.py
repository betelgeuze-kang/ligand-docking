#!/usr/bin/env python3
"""Verify bounded short-parent force scratch reuse for direct-Ewald dynamics."""
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
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-parent-force-scratch.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_direct_ewald_composite_"
    "dynamics_short_parent_force_scratch_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_"
    "dynamics_short_system_scratch_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1_sources.json"
)
ARCHITECTURE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1.json"
)
ARCHITECTURE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1_sources.json"
)
INHERITED_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json"
)
INHERITED_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_sources/1.0.0"
)
PUBLIC_PROFILE_ID = (
    "betelgeuze.native_direct_ewald_composite_dynamics/1.0.0"
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
    "pull_request": 447,
    "reviewed_head": "5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6",
    "merge_commit": "3f68361985e57f4c5ee547ba690f4a6859bd8b34",
    "merge_tree": "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "8be1f7d28f936f78486bfabaf9fdfc2e1e334285864138639c796d36a454d3cb"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "85c17310e995b8eb22028083694f710414e523884a0ae9834b5258dfcb6c48fd"
    ),
    "source_manifest_entry_count": 208,
}
ARCHITECTURE_PREDECESSOR = {
    "pull_request": 448,
    "reviewed_head": "4ace5d02dd90618140baecfeba28fdf93f3b342f",
    "merge_commit": "5d4a55c85a80b62d38e79ea608e4850a6966ceeb",
    "merge_tree": "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73",
    "profile_path": ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "72982489ea675272607013d9495f36ea5f649eb94f57d35e6a37a9e8ebfef476"
    ),
    "source_manifest_path": ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "691792ba1f59fb314bd7c4dc8b6ae746f25629a840b9e64da6b3f54eba561028"
    ),
    "source_manifest_entry_count": 214,
}
INHERITED_PREDECESSOR = {
    "pull_request": 446,
    "reviewed_head": "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7",
    "merge_commit": "29edcd1ea18e9fb64b9d416a0d05d87e0485be4b",
    "merge_tree": "77f5298c291130f7ea86b96bd13b6bd9596f6850",
    "profile_path": INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "2c1a5c015cd4db903e359e6d18fb52ee70c583e1c2744409754b44352d201985"
    ),
    "source_manifest_path": INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "f1c41ad4ad774bd2d7ab1672df61792ad539f0c2c199b37511ed0f5783412467"
    ),
    "source_manifest_entry_count": 202,
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
        "native/src/composite/direct_ewald.cpp",
        "native/src/composite/direct_ewald_composite_dynamics.cpp",
        "native/src/composite/direct_ewald_composite_dynamics.hpp",
        "native/src/composite/evaluator.hpp",
        "native/tests/direct_ewald_composite_dynamics.cpp",
        "native/tests/direct_ewald_composite_dynamics_scratch.cpp",
        "native/tests/direct_ewald_composite_dynamics_scratch.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/direct_ewald.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "direct_ewald_composite_dynamics.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "direct_ewald_composite_dynamics.hpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/evaluator.hpp",
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
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1_sources.json",
    INHERITED_PROFILE_RELATIVE_PATH.as_posix(),
    INHERITED_MANIFEST_RELATIVE_PATH.as_posix(),
    PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    PROFILE_RELATIVE_PATH.as_posix(),
    SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.md",
    DOC_RELATIVE_PATH.as_posix(),
    "tools/__init__.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py",
    VERIFIER_RELATIVE_PATH.as_posix(),
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_v1.py",
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
    "bg_direct_ewald_composite_dynamics_abi_version",
    "bg_direct_ewald_composite_dynamics_abi_version_major",
    "bg_direct_ewald_composite_dynamics_abi_version_minor",
    "bg_direct_ewald_composite_dynamics_abi_version_string",
    "bg_direct_ewald_composite_dynamics_v1_profile_id",
    "bg_direct_ewald_composite_simulation_v1_create",
    "bg_direct_ewald_composite_simulation_v1_destroy",
    "bg_direct_ewald_composite_simulation_v1_get_particles",
    "bg_direct_ewald_composite_simulation_v1_get_absolute_step",
    "bg_context_integrate_direct_ewald_composite_v1",
    "bg_direct_ewald_composite_simulation_v1_checkpoint_size",
    "bg_direct_ewald_composite_simulation_v1_checkpoint_write",
    "bg_direct_ewald_composite_simulation_v1_checkpoint_load",
)
EXPECTED_TEST_SOURCE_SHA256 = (
    "8263e75fe72ce5fc6fbddae9805a421ed274e75e87c7d70224cac3c7fa7d42c0"
)
EXPECTED_TEST_HELPER_SOURCE_SHA256 = (
    "118e474c0e328f5e974a50273122c79f6d818d861a540f9fa6f8a8217cbc8244"
)
EXPECTED_TEST_HELPER_HEADER_SHA256 = (
    "ecfebeae3bed692c02fe017ae4f6ba4546bdf959892efaeaaef47a54fb5d6cd9"
)
EXPECTED_PRODUCTION_SOURCE_SHA256 = {
    "direct_ewald.cpp":
        "a0b468d6a5fc0f1e45d86d9d8191b846b22fc7f1f3522d7a7e3e2088c4d780ad",
    "direct_ewald_composite_dynamics.cpp":
        "ed6c3c1d0cddde8aab37720421463d177818e2a2a093b134a3b25c097f7d566f",
    "direct_ewald_composite_dynamics.hpp":
        "7d57561e4daa33ca51e6c15231866cdd5c8372f9a7ae4b37f5ce748e1f7563b4",
    "evaluator.hpp":
        "8e264457978f3f327ec49b170b261cfe6defe51070899481279e38826f2153ef",
}
EXPECTED_PREDECESSOR_WORKFLOW_SHA256 = (
    "91a8227441b71bd83521f481cff6009df8c8fd3509b043ecd0e876a2ab0c5eca"
)
EXPECTED_PREDECESSOR_UNIT_SHA256 = (
    "f4e99222d372ecbde39661abbfe6048f14e4ad3bb15d2a251e0a1a6db836ef51"
)

RUST_BOUNDARY_COMMAND_STEP = "\n".join(
    (
        "      - name: Existing Rust regression, docs, and clean packages",
        "        run: |",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-sys --test layout --test raw_smoke",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --lib direct_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --test direct_ewald_composite_dynamics",
        "          cargo test --manifest-path rust/Cargo.toml --locked --package betelgeuze-runtime --doc direct_ewald_composite_dynamics",
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
      - name: Materialize exact PR 448 architecture, PR 447 target, and PR 446 inherited force scratch
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 5d4a55c85a80b62d38e79ea608e4850a6966ceeb^{tree})" = "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73"
          git merge-base --is-ancestor 5d4a55c85a80b62d38e79ea608e4850a6966ceeb HEAD
          git fetch --no-tags --depth=1 origin refs/pull/448/head
          test "$(git rev-parse FETCH_HEAD)" = "4ace5d02dd90618140baecfeba28fdf93f3b342f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73"
          test "$(git rev-parse 3f68361985e57f4c5ee547ba690f4a6859bd8b34^{tree})" = "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12"
          git merge-base --is-ancestor 3f68361985e57f4c5ee547ba690f4a6859bd8b34 5d4a55c85a80b62d38e79ea608e4850a6966ceeb
          git fetch --no-tags --depth=1 origin refs/pull/447/head
          test "$(git rev-parse FETCH_HEAD)" = "5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12"
          test "$(git rev-parse 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
          git merge-base --is-ancestor 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b 3f68361985e57f4c5ee547ba690f4a6859bd8b34
          git fetch --no-tags --depth=1 origin refs/pull/446/head
          test "$(git rev-parse FETCH_HEAD)" = "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_short_parent_force_scratch_v1.py
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
          cmake -S . -B build/direct-ewald-short-parent-force-scratch-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/direct-ewald-short-parent-force-scratch-release --target betelgeuze_engine_direct_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/direct-ewald-short-parent-force-scratch-release -R '^betelgeuze_engine_(direct_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/direct-ewald-short-parent-force-scratch-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/direct-ewald-short-parent-force-scratch-sanitize --target betelgeuze_engine_direct_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/direct-ewald-short-parent-force-scratch-sanitize -R '^betelgeuze_engine_direct_ewald_composite_dynamics$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/direct-ewald-short-parent-force-scratch-cargo
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
          cmake -S . -B build/direct-ewald-short-parent-force-scratch-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/direct-ewald-short-parent-force-scratch-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/direct-ewald-short-parent-force-scratch-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-direct-ewald-composite-dynamics-"
        "short-parent-force-scratch\n\n"
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
        "  group: ci-engine-v2-native-direct-ewald-composite-dynamics-"
        "short-parent-force-scratch-${{ github.ref }}\n"
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
    if profile.get("predecessor") != INHERITED_PREDECESSOR:
        fail("target predecessor no longer binds the inherited force-scratch predecessor")
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
        fail("inherited force-scratch predecessor is not an ancestor of target")
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
            "direct_ewald_composite_dynamics_stateful_short_parent_force_scratch_"
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
            "engine_v2_native_direct_ewald_composite_dynamics_"
            "short_parent_force_scratch_development_v1"
        ),
        "roadmap_issue": 434,
        "target_predecessor": dict(PREDECESSOR),
        "architecture_predecessor": dict(ARCHITECTURE_PREDECESSOR),
        "inherited_force_scratch_predecessor": dict(INHERITED_PREDECESSOR),
        "abi": {
            "public_profile_id": PUBLIC_PROFILE_ID,
            "public_symbol_count": 13,
            "public_symbols": list(PUBLIC_SYMBOLS),
            "checkpoint_magic": "BGDEC001",
            "checkpoint_header_size_bytes": 104,
            "abi_changed": False,
            "checkpoint_format_changed": False,
        },
        "implementation": {
            "owner_persistent_short_parent_evaluation_scratch": True,
            "stateful_scratch_and_cache_pointers_all_or_none": True,
            "steady_state_successful_forceful_short_parent_three_vector_storage_reuse": True,
            "force_free_stateful_local_evaluation_path": True,
            "force_free_short_parent_scratch_and_cache_unchanged": True,
            "stateless_local_evaluation_path_preserved": True,
            "dynamics_output_alias_guard_includes_short_parent_scratch": True,
            "short_parent_scratch_and_cache_are_derived_non_authoritative": True,
            "short_parent_scratch_serialized_in_checkpoint": False,
            "rust_validation_cache_serialized_in_checkpoint": False,
            "short_parent_scratch_bound_into_static_fingerprint": False,
            "rust_validation_cache_bound_into_static_fingerprint": False,
            "late_downstream_failure_storage_identity_checked": True,
            "unconditional_failure_storage_retention_claimed": False,
            "upstream_failure_storage_retention_claimed": False,
            "all_failure_path_storage_retention_claimed": False,
            "existing_short_system_scratch_contract_preserved": True,
            "existing_final_soa_force_output_storage_preserved": True,
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
            "three_short_parent_force_channels_pointer_and_capacity_retention": True,
            "scratch_nonalias_against_owner_short_system_and_final_output": True,
            "initial_create_and_zero_step_scratch_cache_stability": True,
            "same_lane_reserved_vs_peer_bit_identity": True,
            "checkpoint_a_to_b_load_a_preserves_derived_scratch_cache": True,
            "zero_step_preserves_stale_derived_scratch_cache": True,
            "forceful_post_load_resynchronizes_short_parent_forces": True,
            "repeated_late_downstream_failure_authoritative_transactionality": True,
            "late_downstream_failure_storage_identity": True,
            "active_scratch_output_alias_rejected": True,
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
        symbol.startswith("bg_direct_ewald_composite_dynamics_")
        or symbol.startswith("bg_direct_ewald_composite_simulation_v1_")
        or symbol == "bg_context_integrate_direct_ewald_composite_v1"
    )


def extract_public_symbol_surfaces(
    root: Path = ROOT,
) -> dict[str, tuple[str, ...]]:
    header = (
        root / "include/betelgeuze/direct_ewald_composite_dynamics.h"
    ).read_text()
    dynamics = (
        root / "native/src/composite/direct_ewald_composite_dynamics.cpp"
    ).read_text()
    checkpoint = (
        root / "native/src/composite/direct_ewald_composite_checkpoint.cpp"
    ).read_text()
    version_map = (root / "native/betelgeuze_engine.map").read_text()
    exports = (root / "native/betelgeuze_engine.exports").read_text()
    export_test = (root / "native/tests/check_exports.cmake").read_text()
    sys_source = (root / "rust/betelgeuze-sys/src/lib.rs").read_text()
    node = re.search(
        r"BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1\.0 \{\n"
        r"[ \t]+global:\n(?P<body>.*?)\n"
        r"\} BETELGEUZE_DIRECT_EWALD_COMPOSITE_1\.0;",
        version_map,
        re.DOTALL,
    )
    if node is None:
        fail("exact direct-Ewald composite-dynamics ELF node or parent changed")
    export_block = re.search(
        r"set\(direct_ewald_composite_dynamics_v1_symbols\n"
        r"(?P<body>.*?)\n\)",
        export_test,
        re.DOTALL,
    )
    if export_block is None:
        fail("export regression direct-Ewald dynamics group missing")
    mapping_tokens = (
        'list(FIND direct_ewald_composite_dynamics_v1_symbols "${unversioned}" direct_ewald_composite_dynamics_v1_index)',
        'set(expected_version "BETELGEUZE_DIRECT_EWALD_COMPOSITE_DYNAMICS_1.0")',
    )
    if any(token not in export_test for token in mapping_tokens):
        fail("export regression direct-Ewald dynamics version mapping changed")
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
        fail("direct-Ewald composite-dynamics ABI symbol constant changed")
    for surface, symbols in extract_public_symbol_surfaces(root).items():
        if symbols != PUBLIC_SYMBOLS:
            fail(f"direct-Ewald composite-dynamics public symbol set changed: {surface}")


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
        "refs/pull/448/head",
        ARCHITECTURE_PREDECESSOR["reviewed_head"],
        ARCHITECTURE_PREDECESSOR["merge_commit"],
        ARCHITECTURE_PREDECESSOR["merge_tree"],
        "refs/pull/447/head",
        PREDECESSOR["reviewed_head"],
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        "refs/pull/446/head",
        INHERITED_PREDECESSOR["reviewed_head"],
        INHERITED_PREDECESSOR["merge_commit"],
        INHERITED_PREDECESSOR["merge_tree"],
        "pytest==8.3.5",
        "ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1",
        "cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked",
        "cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        'BETELGEUZE_V7_SOURCE_ROOT="$GITHUB_WORKSPACE"',
        "^betelgeuze_engine_(direct_ewald_composite_dynamics|export_allowlist)$",
        "^betelgeuze_engine_direct_ewald_composite_dynamics$",
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
    old_materialize = """      - name: Materialize exact PR 447 architecture and PR 445 target
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 3f68361985e57f4c5ee547ba690f4a6859bd8b34^{tree})" = "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12"
          git merge-base --is-ancestor 3f68361985e57f4c5ee547ba690f4a6859bd8b34 HEAD
          git fetch --no-tags --depth=1 origin refs/pull/447/head
          test "$(git rev-parse FETCH_HEAD)" = "5d4d238a2eea2765b6ac5d5d3f596487bd5b8cd6"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "1fc25fdc53ae1d2303a6fe6abe279e520fc13f12"
          test "$(git rev-parse c53f7993ec06c4ac04a4907b40f179d12fbe309a^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
          git merge-base --is-ancestor c53f7993ec06c4ac04a4907b40f179d12fbe309a 3f68361985e57f4c5ee547ba690f4a6859bd8b34
          git fetch --no-tags --depth=1 origin refs/pull/445/head
          test "$(git rev-parse FETCH_HEAD)" = "801a85d56846c464b3a618ecacca867cd12a8c9f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
"""
    new_materialize = """      - name: Materialize exact PR 448 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 5d4a55c85a80b62d38e79ea608e4850a6966ceeb^{tree})" = "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73"
          git merge-base --is-ancestor 5d4a55c85a80b62d38e79ea608e4850a6966ceeb HEAD
          git fetch --no-tags --depth=1 origin refs/pull/448/head
          test "$(git rev-parse FETCH_HEAD)" = "4ace5d02dd90618140baecfeba28fdf93f3b342f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "1b6ebb2ef465f22070f38db8eaaa23e10b7a5b73"
"""
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 448 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=5d4a55c85a80b62d38e79ea608e4850a6966ceeb
          current_sha="$(git rev-parse HEAD)"
          git checkout --detach --quiet "$frozen"
          trap 'git checkout --detach --quiet "$current_sha"' EXIT
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_short_system_scratch_v1.py
          git checkout --detach --quiet "$current_sha"
          trap - EXIT
          test "$(git rev-parse HEAD)" = "$current_sha"
"""
    if frozen.count(old_materialize) != 1 or frozen.count(old_verify) != 1:
        fail("frozen predecessor workflow shape drift")
    return frozen.replace(old_materialize, new_materialize, 1).replace(
        old_verify, new_verify, 1
    )


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
    addition = """DIRECT_EWALD_SHORT_PARENT_FORCE_SCRATCH_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_parent_force_scratch_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    DIRECT_EWALD_SHORT_PARENT_FORCE_SCRATCH_EVIDENCE_PRESENT,
    reason=(
        "particle-mesh Ewald composite dynamics short-system scratch evidence "
        "is verified from its exact frozen object after direct-Ewald "
        "short-parent force scratch evidence is present"
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


def expected_direct_ewald_source(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    bool compute_forces,
""",
        """    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    bool compute_forces,
""",
        "short-parent evaluator parameters",
    )
    source = replace_exact(
        source,
        """            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no direct-Ewald composite evaluator");
    }

    bg_system local_short_system;
""",
        """            return fail(
                BG_STATUS_UNSUPPORTED_BACKEND,
                "selected backend has no direct-Ewald composite evaluator");
    }

    const bool stateful_scratch = short_system_scratch != nullptr;
    if ((short_parent_evaluation_scratch != nullptr) != stateful_scratch ||
        (inout_rust_cpu_forcefield_validated != nullptr) !=
            stateful_scratch) {
        return fail(
            BG_STATUS_INTERNAL_ERROR,
            "composite stateful scratch and validation-cache pointers must be all null or all non-null");
    }

    bg_system local_short_system;
""",
        "all-or-none stateful scratch contract",
    )
    source = replace_exact(
        source,
        """    cpu::Evaluation short_evaluation;
    bg_status status = BG_STATUS_OK;
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = cpu::evaluate(
            *short_system, forcefield, compute_forces, &short_evaluation);
    } else {
        status = rust_cpu::evaluate(
            *short_system, forcefield, compute_forces, &short_evaluation);
    }
    if (status != BG_STATUS_OK) {
        return status;
    }
    if (!short_energy_is_valid(short_evaluation)) {
""",
        """    cpu::Evaluation local_short_evaluation;
    cpu::Evaluation *short_evaluation = &local_short_evaluation;
    const bool reuse_short_parent_force_storage =
        stateful_scratch && compute_forces;
    if (reuse_short_parent_force_storage) {
        short_evaluation = short_parent_evaluation_scratch;
    }
    bg_status status = BG_STATUS_OK;
    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = reuse_short_parent_force_storage
            ? cpu::evaluate_reusing_force_storage(
                  *short_system, forcefield, true, short_evaluation)
            : cpu::evaluate(
                  *short_system, forcefield, compute_forces,
                  short_evaluation);
    } else {
        status = reuse_short_parent_force_storage
            ? rust_cpu::evaluate_reusing_force_storage(
                  *short_system,
                  forcefield,
                  true,
                  inout_rust_cpu_forcefield_validated,
                  short_evaluation)
            : rust_cpu::evaluate(
                  *short_system, forcefield, compute_forces,
                  short_evaluation);
    }
    if (status != BG_STATUS_OK) {
        return status;
    }
    const cpu::Evaluation &short_result = *short_evaluation;
    if (!short_energy_is_valid(short_result)) {
""",
        "stateful short-parent force reuse",
    )
    if source.count("short_evaluation.") != 13:
        fail("frozen short-parent result reference count drift")
    source = source.replace("short_evaluation.", "short_result.")
    return replace_exact(
        source,
        """            *context, *system, *forcefield, *model, nullptr, compute_forces,
            &evaluation, &typed_error);
""",
        """            *context, *system, *forcefield, *model, nullptr, nullptr, nullptr,
            compute_forces, &evaluation, &typed_error);
""",
        "stateless null scratch and cache",
    )


def expected_evaluator_header(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """#include "../ewald/cpp_evaluator.hpp"

#include <array>
""",
        """#include "../cpu/evaluator.hpp"
#include "../ewald/cpp_evaluator.hpp"

#include <array>
#include <cstdint>
""",
        "short-parent evaluator includes",
    )
    return replace_exact(
        source,
        """/*
 * The caller must first establish validate_handle_compatibility(). A null
 * short-system scratch preserves the stateless local-copy path. A non-null
 * scratch must be independent, deep-owned, shape/unit matched, and contain
 * exact +0.0 charges; only its positions are refreshed, and failed calls need
 * not restore its private derived contents.
 */
[[nodiscard]] bg_status evaluate_prevalidated(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    bool compute_forces,
""",
        """/*
 * The caller must first establish validate_handle_compatibility(). All three
 * scratch/cache pointers must be null for the stateless path or non-null for
 * the stateful path. A non-null short-system scratch must be independent,
 * deep-owned, shape/unit matched, and contain exact +0.0 charges; only its
 * positions are refreshed. Force-producing stateful calls reuse the short
 * parent's Evaluation storage. Force-free calls leave that storage and the
 * Rust validation cache untouched. Failed calls need not restore private
 * derived scratch/cache contents.
 */
[[nodiscard]] bg_status evaluate_prevalidated(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    cpu::Evaluation *short_parent_evaluation_scratch,
    uint8_t *inout_rust_cpu_forcefield_validated,
    bool compute_forces,
""",
        "short-parent evaluator header contract",
    )


def expected_dynamics_header(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include "../dynamics/dynamics.hpp"
""",
        """#include "betelgeuze/direct_ewald_composite_dynamics.h"

#include "../cpu/evaluator.hpp"
#include "../dynamics/dynamics.hpp"
""",
        "owner short-parent evaluator include",
    )
    return replace_exact(
        source,
        """    std::unique_ptr<bg_simulation> simulation;
    bg_direct_ewald_model_v1 model;
    bg_system short_system_scratch;
    std::array<uint8_t, 32> static_fingerprint{};
""",
        """    std::unique_ptr<bg_simulation> simulation;
    bg_direct_ewald_model_v1 model;
    bg_system short_system_scratch;
    betelgeuze::native::cpu::Evaluation short_parent_evaluation_scratch;
    std::array<uint8_t, 32> static_fingerprint{};
""",
        "owner short-parent scratch member",
    )


def expected_dynamics_source(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """bool forcefield_storage_overlaps(
""",
        """bool evaluation_storage_overlaps(
    const cpu::Evaluation &evaluation,
    const ByteRange &output) noexcept {
    return vector_storage_overlaps(evaluation.force_x, output) ||
           vector_storage_overlaps(evaluation.force_y, output) ||
           vector_storage_overlaps(evaluation.force_z, output);
}

bool forcefield_storage_overlaps(
""",
        "short-parent scratch overlap helper",
    )
    source = replace_exact(
        source,
        """    if (fixed_storage_overlaps(&owner, sizeof(owner), output) ||
        model_storage_overlaps(owner.model, output) ||
        system_storage_overlaps(owner.short_system_scratch, output)) {
""",
        """    if (fixed_storage_overlaps(&owner, sizeof(owner), output) ||
        model_storage_overlaps(owner.model, output) ||
        system_storage_overlaps(owner.short_system_scratch, output) ||
        evaluation_storage_overlaps(
            owner.short_parent_evaluation_scratch, output)) {
""",
        "owner short-parent scratch overlap",
    )
    source = replace_exact(
        source,
        """        simulation->forcefield,
        provider->owner->model,
        &provider->owner->short_system_scratch,
        compute_forces,
""",
        """        simulation->forcefield,
        provider->owner->model,
        &provider->owner->short_system_scratch,
        &provider->owner->short_parent_evaluation_scratch,
        &simulation->rust_cpu_forcefield_validated,
        compute_forces,
""",
        "stateful short-parent scratch and cache pointers",
    )
    return replace_exact(
        source,
        """            candidate->simulation->forcefield,
            candidate->model,
            &candidate->short_system_scratch,
            false,
""",
        """            candidate->simulation->forcefield,
            candidate->model,
            &candidate->short_system_scratch,
            &candidate->short_parent_evaluation_scratch,
            &candidate->simulation->rust_cpu_forcefield_validated,
            false,
""",
        "create-time force-free scratch and cache pointers",
    )


def require_exact_regression_sources(
    test: str,
    helper: str,
    header: str,
) -> None:
    observed = {
        "direct-Ewald dynamics regression": sha(test.encode()),
        "scratch helper": sha(helper.encode()),
        "scratch helper header": sha(header.encode()),
    }
    expected = {
        "direct-Ewald dynamics regression": EXPECTED_TEST_SOURCE_SHA256,
        "scratch helper": EXPECTED_TEST_HELPER_SOURCE_SHA256,
        "scratch helper header": EXPECTED_TEST_HELPER_HEADER_SHA256,
    }
    for label, expected_digest in expected.items():
        if observed[label] != expected_digest:
            fail(f"exact {label} source drift")


def require_short_parent_force_scratch_contract(root: Path = ROOT) -> None:
    merge = ARCHITECTURE_PREDECESSOR["merge_commit"]
    transforms = (
        ("direct_ewald.cpp", expected_direct_ewald_source),
        (
            "direct_ewald_composite_dynamics.cpp",
            expected_dynamics_source,
        ),
        (
            "direct_ewald_composite_dynamics.hpp",
            expected_dynamics_header,
        ),
        ("evaluator.hpp", expected_evaluator_header),
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
            fail(f"canonical bounded short-parent force-scratch transform drift: {name}")
        if vendor != transform(frozen_vendor):
            fail(f"vendored bounded short-parent force-scratch transform drift: {name}")
        if native != vendor:
            fail(f"canonical and vendored source differ: {name}")
        observed_production[name] = sha(native.encode())
    if observed_production != EXPECTED_PRODUCTION_SOURCE_SHA256:
        fail("exact direct-Ewald production source hashes drift")

    direct_source = (
        root / "native/src/composite/direct_ewald.cpp"
    ).read_text()
    direct_tokens = (
        "const bool stateful_scratch = short_system_scratch != nullptr;",
        "(short_parent_evaluation_scratch != nullptr) != stateful_scratch",
        "(inout_rust_cpu_forcefield_validated != nullptr) !=",
        "cpu::Evaluation local_short_evaluation;",
        "cpu::Evaluation *short_evaluation = &local_short_evaluation;",
        "stateful_scratch && compute_forces;",
        "short_evaluation = short_parent_evaluation_scratch;",
        "cpu::evaluate_reusing_force_storage(",
        "rust_cpu::evaluate_reusing_force_storage(",
        "inout_rust_cpu_forcefield_validated,",
        "const cpu::Evaluation &short_result = *short_evaluation;",
        "*context, *system, *forcefield, *model, nullptr, nullptr, nullptr,",
    )
    if any(token not in direct_source for token in direct_tokens):
        fail("short-parent stateful/stateless evaluator routing drift")
    if direct_source.count("? cpu::evaluate_reusing_force_storage(") != 1:
        fail("C++ stateful forceful reuse path drift")
    if direct_source.count("? rust_cpu::evaluate_reusing_force_storage(") != 1:
        fail("Rust stateful forceful reuse path drift")
    if direct_source.count("? cpu::evaluate(") != 0:
        fail("ordinary C++ short-parent evaluation must remain the local fallback")
    if direct_source.count(": cpu::evaluate(") != 1:
        fail("C++ force-free/stateless local evaluation path drift")
    if direct_source.count(": rust_cpu::evaluate(") != 1:
        fail("Rust force-free/stateless local evaluation path drift")
    if any(
        token in direct_source
        for token in (
            "*short_parent_evaluation_scratch =",
            "short_parent_evaluation_scratch->force_x =",
            "short_parent_evaluation_scratch->force_y =",
            "short_parent_evaluation_scratch->force_z =",
        )
    ):
        fail("short-parent force scratch storage replacement is forbidden")

    dynamics_source = (
        root / "native/src/composite/direct_ewald_composite_dynamics.cpp"
    ).read_text()
    dynamics_header = (
        root / "native/src/composite/direct_ewald_composite_dynamics.hpp"
    ).read_text()
    dynamics_tokens = (
        "bool evaluation_storage_overlaps(",
        "vector_storage_overlaps(evaluation.force_x, output)",
        "vector_storage_overlaps(evaluation.force_y, output)",
        "vector_storage_overlaps(evaluation.force_z, output)",
        "owner.short_parent_evaluation_scratch, output",
        "&provider->owner->short_parent_evaluation_scratch,",
        "&simulation->rust_cpu_forcefield_validated,",
        "&candidate->short_parent_evaluation_scratch,",
        "&candidate->simulation->rust_cpu_forcefield_validated,",
    )
    if any(token not in dynamics_source for token in dynamics_tokens):
        fail("dynamics owner, provider, create, or output-alias binding drift")
    if dynamics_header.count(
        "betelgeuze::native::cpu::Evaluation short_parent_evaluation_scratch;"
    ) != 1:
        fail("private owner short-parent Evaluation member drift")
    fingerprint_region = dynamics_source.split(
        "std::array<uint8_t, 32> compute_static_fingerprint(", 1
    )[1].split("bg_status validate_owner_invariant(", 1)[0]
    if (
        "short_parent_evaluation_scratch" in fingerprint_region
        or "rust_cpu_forcefield_validated" in fingerprint_region
    ):
        fail("derived short-parent scratch/cache entered the static fingerprint")

    header = (
        root / "native/tests/direct_ewald_composite_dynamics_scratch.hpp"
    ).read_text()
    helper = (
        root / "native/tests/direct_ewald_composite_dynamics_scratch.cpp"
    ).read_text()
    test = (
        root / "native/tests/direct_ewald_composite_dynamics.cpp"
    ).read_text()
    require_exact_regression_sources(test, helper, header)
    if (
        header.count(
            '#include "betelgeuze/direct_ewald_composite_dynamics.h"'
        )
        != 1
        or "../src/" in header
        or re.search(r"\bbg_simulation\b", header) is not None
        or re.search(r"\bbg_system\b", header) is not None
    ):
        fail("test helper header no longer preserves public owner opacity")
    if helper.count(
        '#include "../src/composite/direct_ewald_composite_dynamics.hpp"'
    ) != 1:
        fail("test helper implementation owner binding drift")
    if helper.count("simulation->simulation->force_evaluation_scratch") != 2:
        fail("existing force-scratch test helper binding drift")
    helper_tokens = (
        "reserve_direct_ewald_composite_short_parent_force_scratch(",
        "simulation->short_parent_evaluation_scratch",
        "direct_ewald_composite_short_parent_force_scratch_snapshot(",
        "scratch.force_x.data()",
        "scratch.force_y.data()",
        "scratch.force_z.data()",
        "scratch.force_x.capacity()",
        "scratch.force_y.capacity()",
        "scratch.force_z.capacity()",
        "simulation->simulation->rust_cpu_forcefield_validated",
    )
    if any(token not in helper for token in helper_tokens):
        fail("test-only short-parent scratch introspection contract drift")
    test_tokens = (
        "verify_short_parent_force_scratch_reuse();",
        "verify_late_typed_ewald_failure_rolls_back();",
        "BG_BACKEND_CPP_CPU_REFERENCE",
        "BG_BACKEND_RUST_CPU",
        "new short-parent force scratch was not empty",
        "short-parent force scratch reserve did not materialize storage",
        "short-parent force scratch channels aliased",
        "short-parent scratch aliased final force scratch",
        "short-parent scratch aliased short-system scratch",
        "short-parent scratch aliased authoritative owner storage",
        "zero-step integration changed short-parent scratch storage",
        "zero-step integration changed Rust validation cache",
        "integration replaced short-parent force scratch storage",
        "short-parent force evaluation retained the wrong Rust validation flag",
        "checkpoint reload unexpectedly rewrote short-parent scratch/cache",
        "zero-step restart changed stale short-parent scratch/cache",
        "forceful restart did not resynchronize short-parent force scratch",
        "absolute-step output aliased short-parent force scratch",
        "late direct-Ewald failure replaced short-parent force scratch storage",
        "late direct-Ewald failure retained the wrong Rust validation flag",
        "short_parent_force_scratch_bits",
        "attempt < 2U",
        "!is_complete<bg_direct_ewald_composite_simulation_v1>::value",
    )
    if any(token not in test for token in test_tokens):
        fail("short-parent force scratch regression coverage drift")
    if test.count("verify_short_parent_force_scratch_reuse();") != 1:
        fail("short-parent force scratch regression invocation count drift")
    if test.count("verify_late_typed_ewald_failure_rolls_back();") != 1:
        fail("late typed-failure regression invocation count drift")

    helper_api_tokens = (
        "direct_ewald_composite_short_system_scratch_snapshot",
        "direct_ewald_composite_short_parent_force_scratch_snapshot",
        "reserve_direct_ewald_composite_short_parent_force_scratch",
        "set_direct_ewald_composite_short_system_scratch_unit_for_test",
        "truncate_direct_ewald_composite_short_system_scratch_for_test",
        "set_direct_ewald_composite_short_system_scratch_charge_for_test",
    )
    public_surfaces = "\n".join(
        (
            (root / "include/betelgeuze/direct_ewald_composite_dynamics.h").read_text(),
            (root / "native/betelgeuze_engine.map").read_text(),
            (root / "native/betelgeuze_engine.exports").read_text(),
            (root / "rust/betelgeuze-sys/src/lib.rs").read_text(),
        )
    )
    if any(token in public_surfaces for token in helper_api_tokens):
        fail("test-only scratch introspection leaked into a public symbol surface")

    checkpoint_sources = "\n".join(
        (
            (root / "native/src/composite/direct_ewald_composite_checkpoint.cpp").read_text(),
            (
                root
                / "rust/betelgeuze-sys/vendor/native/src/composite/"
                "direct_ewald_composite_checkpoint.cpp"
            ).read_text(),
        )
    )
    if (
        "short_parent_evaluation_scratch" in checkpoint_sources
        or "rust_cpu_forcefield_validated" in checkpoint_sources
    ):
        fail("derived short-parent scratch/cache entered checkpoint serialization")

    for relative in (
        "native/CMakeLists.txt",
        "native/src/composite/direct_ewald_composite_checkpoint.cpp",
        "rust/betelgeuze-sys/vendor/native/src/composite/"
        "direct_ewald_composite_checkpoint.cpp",
        "include/betelgeuze/direct_ewald_composite_dynamics.h",
        "native/betelgeuze_engine.map",
        "native/betelgeuze_engine.exports",
        "rust/betelgeuze-sys/src/lib.rs",
    ):
        path = Path(relative)
        frozen = git("show", f"{merge}:{path.as_posix()}").stdout
        if (root / path).read_bytes() != frozen:
            fail(f"ABI, checkpoint, export, or CMake predecessor drift: {path}")


def require_contracts(root: Path = ROOT) -> None:
    require_exact_public_symbols(root)
    require_short_parent_force_scratch_contract(root)
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
