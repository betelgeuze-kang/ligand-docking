#!/usr/bin/env python3
"""Verify bounded persistent short-system scratch reuse for direct-Ewald dynamics."""
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
    "short_system_scratch_profile_v1.json"
)
SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1_sources.json"
)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-short-system-scratch.yml"
)
PREDECESSOR_WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-"
    "dynamics-force-scratch.yml"
)
DOC_RELATIVE_PATH = Path(
    "docs/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_v1.md"
)
UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_direct_ewald_composite_"
    "dynamics_short_system_scratch_v1.py"
)
PREDECESSOR_UNIT_RELATIVE_PATH = Path(
    "tests/unit/test_engine_v2_native_direct_ewald_composite_"
    "dynamics_force_scratch_v1.py"
)
VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_v1.py"
)
PREDECESSOR_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1.json"
)
PREDECESSOR_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "force_scratch_profile_v1_sources.json"
)
ARCHITECTURE_PROFILE_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1.json"
)
ARCHITECTURE_MANIFEST_RELATIVE_PATH = Path(
    "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_profile_v1_sources.json"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_sources/1.0.0"
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
    "pull_request": 446,
    "reviewed_head": "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7",
    "merge_commit": "29edcd1ea18e9fb64b9d416a0d05d87e0485be4b",
    "merge_tree": "77f5298c291130f7ea86b96bd13b6bd9596f6850",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "2c1a5c015cd4db903e359e6d18fb52ee70c583e1c2744409754b44352d201985"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "f1c41ad4ad774bd2d7ab1672df61792ad539f0c2c199b37511ed0f5783412467"
    ),
    "source_manifest_entry_count": 202,
}
ARCHITECTURE_PREDECESSOR = {
    "pull_request": 443,
    "reviewed_head": "b785fd793c421c27730516453559a27b9cee6427",
    "merge_commit": "5c532668f9ed95b1159b899acf726eef8824b288",
    "merge_tree": "515d0ea740426d6267a5b521acc451ea1492f282",
    "profile_path": ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "8ae38af90175e1e62eb54abb6727963a4439ece0fc4b622a4b0f4c9593c1a97f"
    ),
    "source_manifest_path": ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "1aed00454380e70338428b11e347b7d47f28b2b5f46e5e843612dca0ac361432"
    ),
    "source_manifest_entry_count": 120,
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
    ARCHITECTURE_PROFILE_RELATIVE_PATH.as_posix(),
    ARCHITECTURE_MANIFEST_RELATIVE_PATH.as_posix(),
    PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    PROFILE_RELATIVE_PATH.as_posix(),
    SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
    "docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.md",
    DOC_RELATIVE_PATH.as_posix(),
    "tools/__init__.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py",
    VERIFIER_RELATIVE_PATH.as_posix(),
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "force_scratch_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_"
    "backend_preflight_v1.py",
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
    "7cbea77bf0d8a5509018d089365c40a391f2ed06ec9e372ab660df883eeb7b5f"
)
EXPECTED_TEST_HELPER_SOURCE_SHA256 = (
    "45f721544fc6cca5e3c64346d56af0102c4c06c90deca42345686502b8626f88"
)
EXPECTED_TEST_HELPER_HEADER_SHA256 = (
    "1dceaff8172dc9951e39b2b22561716bac17bc621288c2b551280696c93d0612"
)
EXPECTED_PRODUCTION_SOURCE_SHA256 = {
    "direct_ewald.cpp":
        "3e6abd2fa62c6144db0517dc2e9668f72ccf26b7a25fce17844a7c68bdfec053",
    "direct_ewald_composite_dynamics.cpp":
        "81e816377f54e0090408946dcc51d44d0bd2d29c4cb18f7e01b7b2db58202265",
    "direct_ewald_composite_dynamics.hpp":
        "83f36e18884f59fbae9477e5205dbbe6e5ba0dfb7be0dd08c7aed3bd563720bd",
    "evaluator.hpp":
        "71d01ddac0a8f601c3672757003c4cba9c5f8625821eff65435044e9b55ec3f3",
}

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
      - name: Materialize frozen PR 446 reviewed head
        run: |
          set -euo pipefail
          test "$(git rev-parse 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
          git merge-base --is-ancestor 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b HEAD
          git fetch --no-tags --depth=1 origin refs/pull/446/head
          test "$(git rev-parse FETCH_HEAD)" = "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_short_system_scratch_v1.py
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
          cmake -S . -B build/direct-ewald-short-system-scratch-release -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/direct-ewald-short-system-scratch-release --target betelgeuze_engine_direct_ewald_composite_dynamics --parallel 2
          ctest --test-dir build/direct-ewald-short-system-scratch-release -R '^betelgeuze_engine_(direct_ewald_composite_dynamics|export_allowlist)$' --output-on-failure
          cmake -S . -B build/direct-ewald-short-system-scratch-sanitize -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer'
          cmake --build build/direct-ewald-short-system-scratch-sanitize --target betelgeuze_engine_direct_ewald_composite_dynamics --parallel 2
          ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir build/direct-ewald-short-system-scratch-sanitize -R '^betelgeuze_engine_direct_ewald_composite_dynamics$' --output-on-failure
"""

EXPECTED_RUST_JOB_BODY = """    runs-on: ubuntu-latest
    timeout-minutes: 35
    env:
      CARGO_TARGET_DIR: ${{ github.workspace }}/build/direct-ewald-short-system-scratch-cargo
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
          cmake -S . -B build/direct-ewald-short-system-scratch-macos -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBG_ENABLE_HIP=OFF -DBG_ENABLE_HIP_SAFE=OFF
          cmake --build build/direct-ewald-short-system-scratch-macos --target betelgeuze_engine --parallel 2
          ctest --test-dir build/direct-ewald-short-system-scratch-macos -R '^betelgeuze_engine_export_allowlist$' --output-on-failure
"""


def expected_workflow_document() -> str:
    trigger_paths = "".join(
        f'      - "{path}"\n' for path in REQUIRED_TRIGGER_PATHS
    )
    preamble = (
        "name: ci-engine-v2-native-direct-ewald-composite-dynamics-"
        "short-system-scratch\n\n"
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
        "short-system-scratch-${{ github.ref }}\n"
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
        if type(row) is not dict or set(row) != {"byte_count", "path", "sha256"}:
            fail("frozen architecture manifest row shape drift")
        path = row["path"]
        digest = row["sha256"]
        byte_count = row["byte_count"]
        if (
            type(path) is not str
            or Path(path).is_absolute()
            or Path(path).as_posix() != path
            or ".." in Path(path).parts
            or type(byte_count) is not int
            or byte_count < 0
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
        fail("architecture predecessor is not an ancestor of the slice predecessor")

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
    head = git("rev-parse", "HEAD^{commit}").stdout.strip().decode()
    if git("merge-base", "--is-ancestor", merge, head, check=False).returncode != 0:
        fail("HEAD does not descend from the frozen predecessor")

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
    if canonical_bytes(json.loads(profile_raw)) != profile_raw:
        fail("frozen predecessor profile is not canonical JSON")
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
    require_architecture_predecessor()
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
            ARCHITECTURE_PROFILE_RELATIVE_PATH,
            ARCHITECTURE_MANIFEST_RELATIVE_PATH,
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
            "direct_ewald_composite_dynamics_owner_persistent_short_system_scratch_"
            "current_sources_tests_evidence_and_frozen_predecessor"
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
            "short_system_scratch_development_v1"
        ),
        "roadmap_issue": 434,
        "predecessor": dict(PREDECESSOR),
        "architecture_predecessor": dict(ARCHITECTURE_PREDECESSOR),
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
            "owner_persistent_short_system_scratch": True,
            "stateless_local_copy_path_preserved": True,
            "stateful_owner_scratch_pointer_path": True,
            "scratch_initialized_after_static_validation": True,
            "scratch_shape_and_unit_checked": True,
            "scratch_exact_positive_zero_charge_checked": True,
            "position_channels_refreshed_in_place": True,
            "steady_state_short_system_vector_assignment": False,
            "dynamics_output_alias_guard_includes_scratch": True,
            "scratch_serialized_in_checkpoint": False,
            "scratch_bound_into_static_fingerprint": False,
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
            "all_eight_scratch_channels_pointer_and_capacity_retention": True,
            "initial_and_zero_step_scratch_stability": True,
            "checkpoint_a_to_b_load_a_stale_then_resynchronized": True,
            "checkpoint_load_does_not_publish_scratch": True,
            "negative_zero_shape_and_unit_tamper_fail_closed": True,
            "repeated_late_failure_transactionality": True,
            "post_load_same_lane_report_and_checkpoint_identity": True,
            "exact_positive_zero_charge_bits": True,
            "rust_raw_safe_docs_fmt_clippy": True,
            "clean_rust_packages": True,
            "git_object_probes_lazy_fetch_disabled": True,
            "reviewed_head_optional_locally": True,
            "workflow_reviewed_head_explicitly_fetched": True,
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
        "refs/pull/446/head",
        PREDECESSOR["reviewed_head"],
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
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
    old_materialize = """      - name: Materialize frozen PR 445 reviewed head
        run: |
          set -euo pipefail
          test "$(git rev-parse c53f7993ec06c4ac04a4907b40f179d12fbe309a^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
          git merge-base --is-ancestor c53f7993ec06c4ac04a4907b40f179d12fbe309a HEAD
          git fetch --no-tags --depth=1 origin refs/pull/445/head
          test "$(git rev-parse FETCH_HEAD)" = "801a85d56846c464b3a618ecacca867cd12a8c9f"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "2bb25b756b802671bcfc5f3ac95b26df3b284956"
"""
    new_materialize = """      - name: Materialize exact PR 446 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
          git merge-base --is-ancestor 29edcd1ea18e9fb64b9d416a0d05d87e0485be4b HEAD
          git fetch --no-tags --depth=1 origin refs/pull/446/head
          test "$(git rev-parse FETCH_HEAD)" = "5b3fb7ab339d21598ccd22c8c2fe89b38cc97fe7"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "77f5298c291130f7ea86b96bd13b6bd9596f6850"
"""
    old_verify = """      - name: Verify bounded successor evidence
        run: |
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py
"""
    new_verify = """      - name: Verify exact frozen PR 446 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=29edcd1ea18e9fb64b9d416a0d05d87e0485be4b
          current_sha="$(git rev-parse HEAD)"
          git checkout --detach --quiet "$frozen"
          trap 'git checkout --detach --quiet "$current_sha"' EXIT
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_direct_ewald_composite_dynamics_force_scratch_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 tools/verify_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py
          python3 -m pytest -q tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_force_scratch_v1.py
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
    merge = PREDECESSOR["merge_commit"]
    frozen = git(
        "show", f"{merge}:{PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}"
    ).stdout.decode()
    expected = expected_frozen_predecessor_workflow(frozen)
    current = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    if current != expected:
        fail("predecessor workflow freeze drift")


def expected_frozen_predecessor_unit(frozen: str) -> str:
    anchor = "ROOT = Path(__file__).resolve().parents[2]\n"
    addition = """DIRECT_EWALD_SHORT_SYSTEM_SCRATCH_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_direct_ewald_composite_dynamics_"
    "short_system_scratch_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    DIRECT_EWALD_SHORT_SYSTEM_SCRATCH_EVIDENCE_PRESENT,
    reason=(
        "direct-Ewald force-scratch evidence is verified from its exact frozen "
        "object after short-system scratch evidence is present"
    ),
)
"""
    if frozen.count(anchor) != 1:
        fail("frozen predecessor unit insertion point drift")
    return frozen.replace(anchor, anchor + addition, 1)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
    frozen = git(
        "show", f"{merge}:{PREDECESSOR_UNIT_RELATIVE_PATH.as_posix()}"
    ).stdout.decode()
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
        """}

}  // namespace

bg_status validate_static_compatibility(
""",
        """}

bool short_system_scratch_shape_matches(
    const bg_system &system,
    const bg_system &scratch) noexcept {
    return scratch.unit_system == system.unit_system &&
           scratch.position_x.size() == system.position_x.size() &&
           scratch.position_y.size() == system.position_y.size() &&
           scratch.position_z.size() == system.position_z.size() &&
           scratch.velocity_x.size() == system.velocity_x.size() &&
           scratch.velocity_y.size() == system.velocity_y.size() &&
           scratch.velocity_z.size() == system.velocity_z.size() &&
           scratch.mass.size() == system.mass.size() &&
           scratch.charge.size() == system.charge.size();
}

}  // namespace

bg_status validate_static_compatibility(
""",
        "short-system shape helper",
    )
    source = replace_exact(
        source,
        """    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
    Evaluation *out_evaluation,
""",
        """    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bg_system *short_system_scratch,
    bool compute_forces,
    Evaluation *out_evaluation,
""",
        "short-system evaluator parameter",
    )
    source = replace_exact(
        source,
        """    bg_system short_system = system;
    std::fill(short_system.charge.begin(), short_system.charge.end(), 0.0);
""",
        """    bg_system local_short_system;
    bg_system *short_system = short_system_scratch;
    if (short_system == nullptr) {
        local_short_system = system;
        std::fill(
            local_short_system.charge.begin(),
            local_short_system.charge.end(),
            0.0);
        short_system = &local_short_system;
    } else {
        if (!short_system_scratch_shape_matches(system, *short_system) ||
            std::any_of(
                short_system->charge.begin(),
                short_system->charge.end(),
                [](double charge) {
                    return !double_bits_equal(charge, 0.0);
                })) {
            return fail(
                BG_STATUS_INTERNAL_ERROR,
                "stateful composite short-system scratch shape, units, or zero-charge invariant drifted");
        }
        std::copy(
            system.position_x.begin(), system.position_x.end(),
            short_system->position_x.begin());
        std::copy(
            system.position_y.begin(), system.position_y.end(),
            short_system->position_y.begin());
        std::copy(
            system.position_z.begin(), system.position_z.end(),
            short_system->position_z.begin());
    }
""",
        "short-system in-place refresh",
    )
    source = replace_exact(
        source,
        """    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = cpu::evaluate(
            short_system, forcefield, compute_forces, &short_evaluation);
    } else {
        status = rust_cpu::evaluate(
            short_system, forcefield, compute_forces, &short_evaluation);
    }
""",
        """    if (context.backend == BG_BACKEND_CPP_CPU_REFERENCE) {
        status = cpu::evaluate(
            *short_system, forcefield, compute_forces, &short_evaluation);
    } else {
        status = rust_cpu::evaluate(
            *short_system, forcefield, compute_forces, &short_evaluation);
    }
""",
        "short-system evaluator dereferences",
    )
    return replace_exact(
        source,
        """            *context, *system, *forcefield, *model, compute_forces,
            &evaluation, &typed_error);
""",
        """            *context, *system, *forcefield, *model, nullptr, compute_forces,
            &evaluation, &typed_error);
""",
        "stateless null scratch",
    )


def expected_evaluator_header(frozen: str) -> str:
    return replace_exact(
        frozen,
        """/* The caller must first establish validate_handle_compatibility(). */
[[nodiscard]] bg_status evaluate_prevalidated(
    const bg_context &context,
    const bg_system &system,
    const bg_forcefield &forcefield,
    const bg_direct_ewald_model_v1 &model,
    bool compute_forces,
""",
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
        "evaluator header contract",
    )


def expected_dynamics_header(frozen: str) -> str:
    return replace_exact(
        frozen,
        """    std::unique_ptr<bg_simulation> simulation;
    bg_direct_ewald_model_v1 model;
    std::array<uint8_t, 32> static_fingerprint{};
""",
        """    std::unique_ptr<bg_simulation> simulation;
    bg_direct_ewald_model_v1 model;
    bg_system short_system_scratch;
    std::array<uint8_t, 32> static_fingerprint{};
""",
        "owner scratch member",
    )


def expected_dynamics_source(frozen: str) -> str:
    source = replace_exact(
        frozen,
        """    if (fixed_storage_overlaps(&owner, sizeof(owner), output) ||
        model_storage_overlaps(owner.model, output)) {
""",
        """    if (fixed_storage_overlaps(&owner, sizeof(owner), output) ||
        model_storage_overlaps(owner.model, output) ||
        system_storage_overlaps(owner.short_system_scratch, output)) {
""",
        "owner scratch overlap",
    )
    source = replace_exact(
        source,
        """        simulation->forcefield,
        provider->owner->model,
        compute_forces,
""",
        """        simulation->forcefield,
        provider->owner->model,
        &provider->owner->short_system_scratch,
        compute_forces,
""",
        "stateful owner scratch pointer",
    )
    source = replace_exact(
        source,
        """        if (status != BG_STATUS_OK) {
            return status;
        }

        bg_context validation_context{};
""",
        """        if (status != BG_STATUS_OK) {
            return status;
        }
        candidate->short_system_scratch = candidate->simulation->system;
        std::fill(
            candidate->short_system_scratch.charge.begin(),
            candidate->short_system_scratch.charge.end(),
            0.0);

        bg_context validation_context{};
""",
        "create-time scratch initialization",
    )
    return replace_exact(
        source,
        """            candidate->simulation->forcefield,
            candidate->model,
            false,
""",
        """            candidate->simulation->forcefield,
            candidate->model,
            &candidate->short_system_scratch,
            false,
""",
        "create-time scratch validation",
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


def require_short_system_scratch_contract(root: Path = ROOT) -> None:
    merge = PREDECESSOR["merge_commit"]
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
            fail(f"canonical bounded short-system transform drift: {name}")
        if vendor != transform(frozen_vendor):
            fail(f"vendored bounded short-system transform drift: {name}")
        if native != vendor:
            fail(f"canonical and vendored source differ: {name}")
        observed_production[name] = sha(native.encode())
    if observed_production != EXPECTED_PRODUCTION_SOURCE_SHA256:
        fail("exact direct-Ewald production source hashes drift")

    direct_source = (
        root / "native/src/composite/direct_ewald.cpp"
    ).read_text()
    stateful_region = direct_source.split(
        "    bg_system *short_system = short_system_scratch;\n", 1
    )[1].split("\n\n    cpu::Evaluation", 1)[0]
    forbidden_assignments = (
        "short_system->position_x =",
        "short_system->position_y =",
        "short_system->position_z =",
        "*short_system = system",
    )
    if any(token in stateful_region for token in forbidden_assignments):
        fail("steady-state short-system storage replacement is forbidden")
    for axis in ("x", "y", "z"):
        token = (
            f"system.position_{axis}.begin(), system.position_{axis}.end(),\n"
            f"            short_system->position_{axis}.begin()"
        )
        if direct_source.count(token) != 1:
            fail(f"position-{axis} in-place refresh contract drift")
    if direct_source.count(
        "return !double_bits_equal(charge, 0.0);"
    ) != 1:
        fail("exact positive-zero short-system invariant drift")
    if direct_source.count(
        "*context, *system, *forcefield, *model, nullptr, compute_forces"
    ) != 1:
        fail("stateless null scratch path drift")

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
        "simulation->short_system_scratch",
        "scratch.position_x.data()",
        "scratch.position_y.data()",
        "scratch.position_z.data()",
        "scratch.velocity_x.data()",
        "scratch.velocity_y.data()",
        "scratch.velocity_z.data()",
        "scratch.mass.data()",
        "scratch.charge.data()",
        "scratch.position_x.capacity()",
        "scratch.charge.capacity()",
        "short_system_scratch.position_x.pop_back();",
        "short_system_scratch.charge.front() = charge;",
    )
    if any(token not in helper for token in helper_tokens):
        fail("test-only scratch introspection contract drift")
    test_tokens = (
        "verify_short_system_scratch_reuse();",
        "verify_short_system_scratch_drift_fails_closed();",
        "verify_late_typed_ewald_failure_rolls_back();",
        "BG_BACKEND_CPP_CPU_REFERENCE",
        "BG_BACKEND_RUST_CPU",
        "new short-system scratch layout was invalid",
        "zero-step evaluation replaced short-system scratch storage",
        "integration replaced short-system scratch storage",
        "checkpoint reload unexpectedly rewrote private scratch state",
        "checkpoint reload did not create stale short-system scratch",
        "post-checkpoint scratch resynchronization changed report bits",
        "post-checkpoint scratch resynchronization changed checkpoint bits",
        "post-checkpoint short-system scratch positions were stale",
        "short-system scratch unit drift did not fail closed",
        "short-system scratch shape drift did not fail closed",
        "short-system scratch negative-zero charge did not fail closed",
        "late direct-Ewald failure replaced short-system scratch storage",
        "short_system_scratch_position_bits",
        "set_direct_ewald_composite_short_system_scratch_charge_for_test",
        "-0.0",
        "attempt < 2U",
        "!is_complete<bg_direct_ewald_composite_simulation_v1>::value",
    )
    if any(token not in test for token in test_tokens):
        fail("short-system scratch regression coverage drift")
    if test.count("verify_short_system_scratch_reuse();") != 1:
        fail("short-system scratch regression invocation count drift")
    if test.count("verify_short_system_scratch_drift_fails_closed();") != 1:
        fail("short-system tamper regression invocation count drift")
    if test.count("verify_late_typed_ewald_failure_rolls_back();") != 1:
        fail("late typed-failure regression invocation count drift")

    helper_api_tokens = (
        "direct_ewald_composite_short_system_scratch_snapshot",
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
    require_short_system_scratch_contract(root)
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
