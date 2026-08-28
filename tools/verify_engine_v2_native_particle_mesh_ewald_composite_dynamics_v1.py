#!/usr/bin/env python3
"""Verify stateful particle-mesh-Ewald composite dynamics v1 evidence."""
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
PROFILE_RELATIVE_PATH = Path("config/engine_v2_native_particle_mesh_ewald_composite_dynamics_profile_v1.json")
SOURCE_MANIFEST_RELATIVE_PATH = Path("config/engine_v2_native_particle_mesh_ewald_composite_dynamics_profile_v1_sources.json")
WORKFLOW_RELATIVE_PATH = Path(".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics.yml")
DOC_RELATIVE_PATH = Path("docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.md")
UNIT_RELATIVE_PATH = Path("tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py")
VERIFIER_RELATIVE_PATH = Path("tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py")
SCHEMA_ID = "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_profile/1.0.0"
SOURCE_SCHEMA_ID = "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_sources/1.0.0"
PROFILE_ID = "betelgeuze.native_particle_mesh_ewald_composite_dynamics/1.0.0"
PINNED_CHECKOUT_ACTION = "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
REQUIRED_TRIGGER_PATHS = (
    ".github/workflows/ci-engine-v2-native-direct-ewald-composite-dynamics-backend-preflight.yml",
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite-dynamics.yml",
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald-composite.yml",
    ".github/workflows/ci-engine-v2-native-particle-mesh-ewald.yml",
    "CMakeLists.txt", "include/betelgeuze/**", "native/**", "rust/**",
    "rust_engine_v2/Cargo.lock", "rust_engine_v2/Cargo.toml",
    "config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1_sources.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1.json",
    "config/engine_v2_native_direct_ewald_composite_dynamics_profile_v1_sources.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1_sources.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_profile_v1.json",
    "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_profile_v1_sources.json",
    "docs/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_cpu_v1.md",
    "docs/engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.md",
    "tools/__init__.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tools/verify_engine_v2_native_direct_ewald_composite_dynamics_v1.py",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
    "tools/verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py",
    "tests/unit/test_engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_cpu_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py",
    "tests/unit/test_engine_v2_native_particle_mesh_ewald_cpu_v1.py",
)
BASE = {"commit": "5c532668f9ed95b1159b899acf726eef8824b288", "tree": "515d0ea740426d6267a5b521acc451ea1492f282"}
PARENTS = (
    {"pull_request": 442, "merge_commit": "5f6f4e2642dbe5c1272b2a9710288db25db5164f", "merge_tree": "95f3d64a553f6c261d59a7ef8bd202561d51c45a", "reviewed_head": "8ce40276b58098186edc0dbde426c9b3be12f010", "profile_path": "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1.json", "profile_sha256": "375e9391bba5823ffe525f7f4748fbbf11a1c790f33171924719a7ec050476bc", "source_manifest_path": "config/engine_v2_native_particle_mesh_ewald_composite_cpu_profile_v1_sources.json", "source_manifest_sha256": "0a29fd2bb36becee1f307c137c3e006597f21c63d98bae07ceaaf76b5738f1f1", "source_manifest_entry_count": 114},
    {"pull_request": 443, "merge_commit": "5c532668f9ed95b1159b899acf726eef8824b288", "merge_tree": "515d0ea740426d6267a5b521acc451ea1492f282", "reviewed_head": "b785fd793c421c27730516453559a27b9cee6427", "profile_path": "config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1.json", "profile_sha256": "8ae38af90175e1e62eb54abb6727963a4439ece0fc4b622a4b0f4c9593c1a97f", "source_manifest_path": "config/engine_v2_native_direct_ewald_composite_dynamics_backend_preflight_profile_v1_sources.json", "source_manifest_sha256": "1aed00454380e70338428b11e347b7d47f28b2b5f46e5e843612dca0ac361432", "source_manifest_entry_count": 120},
)
EVIDENCE_PATHS = (WORKFLOW_RELATIVE_PATH, PROFILE_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH, DOC_RELATIVE_PATH, UNIT_RELATIVE_PATH, VERIFIER_RELATIVE_PATH)
IMPLEMENTATION_PATHS = tuple(Path(p) for p in (
    "CMakeLists.txt", "native/CMakeLists.txt", "native/betelgeuze_engine.exports", "native/betelgeuze_engine.map", "native/tests/check_exports.cmake",
    "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h", "native/src/composite/particle_mesh_ewald_composite.cpp", "native/src/composite/particle_mesh_ewald_composite_evaluator.hpp", "native/src/composite/particle_mesh_ewald_composite_dynamics.hpp", "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp", "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp", "native/tests/particle_mesh_ewald_composite_dynamics.cpp",
    "rust/betelgeuze-sys/Cargo.toml", "rust/betelgeuze-sys/build.rs", "rust/betelgeuze-sys/src/lib.rs", "rust/betelgeuze-sys/tests/layout.rs", "rust/betelgeuze-sys/tests/raw_smoke.rs", "rust/betelgeuze-sys/abi/particle_mesh_ewald_composite_dynamics_header_c11.c", "rust/betelgeuze-sys/abi/particle_mesh_ewald_composite_dynamics_layout_assertions.cpp",
    "rust/betelgeuze-runtime/src/lib.rs", "rust/betelgeuze-runtime/src/particle_mesh_ewald_composite_dynamics.rs", "rust/betelgeuze-runtime/tests/particle_mesh_ewald_composite_dynamics.rs",
    "rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_ewald_composite_dynamics.h", "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite.cpp", "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_evaluator.hpp", "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.hpp", "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.cpp", "rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp",
    "tools/verify_engine_v2_native_fixed64_cpu_profile_v7.py", "tools/__init__.py",
))
AUTHORITY = {k: False for k in ("acceleration_claim_authorized", "d1_d2_execution_authorized", "fresh_holdout_execution_authorized", "hip_device_execution_authorized", "historical_molecular_ab_execution_authorized", "molecular_execution_authorized", "performance_claim_authorized", "product_authority", "public_benchmark_authorized", "qualification_rerun_authorized", "reservation_authorized", "root_supervisor_install_authorized", "scientific_claim_authorized", "stage0_admission_authorized", "test_double_production_authority")}
BLOCKERS = ["external_reservation_endpoint_not_configured", "external_reservation_provider_not_operational", "external_reservation_trust_anchor_not_configured", "historical_execution_operational_authority_false"]
PUBLIC_SYMBOLS = tuple([
    "bg_particle_mesh_ewald_composite_dynamics_abi_version", "bg_particle_mesh_ewald_composite_dynamics_abi_version_major", "bg_particle_mesh_ewald_composite_dynamics_abi_version_minor", "bg_particle_mesh_ewald_composite_dynamics_abi_version_string", "bg_particle_mesh_ewald_composite_dynamics_v1_profile_id", "bg_particle_mesh_ewald_composite_simulation_v1_create", "bg_particle_mesh_ewald_composite_simulation_v1_destroy", "bg_particle_mesh_ewald_composite_simulation_v1_get_particles", "bg_particle_mesh_ewald_composite_simulation_v1_get_absolute_step", "bg_context_integrate_particle_mesh_ewald_composite_v1", "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_size", "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_write", "bg_particle_mesh_ewald_composite_simulation_v1_checkpoint_load",
])

def fail(message: str) -> NoReturn:
    raise ValueError(message)

def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()

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

def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["/usr/bin/git", "--no-replace-objects", *args], cwd=ROOT, env=_git_environment(), text=True, capture_output=True, check=check)

def reviewed_head_tree_if_present(reviewed: str) -> str | None:
    result = subprocess.run(
        ["/usr/bin/git", "--no-replace-objects", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        input=f"{reviewed}\n".encode("ascii"),
        env=_git_environment(),
    )
    if result.returncode != 0 or result.stderr:
        fail("optional reviewed-head Git object inspection failed")
    if result.stdout == f"{reviewed} missing\n".encode("ascii"):
        return None
    if result.stdout != f"{reviewed} commit\n".encode("ascii"):
        fail("locally present reviewed-head object is not the frozen commit")
    tree = git("show", "-s", "--format=%T", reviewed).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", tree) is None:
        fail("locally present reviewed-head tree identity is invalid")
    return tree

def require_parent_manifest(raw: bytes, expected_count: int) -> dict:
    try:
        manifest = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("frozen parent manifest is invalid JSON") from error
    if type(manifest) is not dict or canonical_bytes(manifest) != raw:
        fail("frozen parent manifest is not canonical JSON")
    rows = manifest.get("files")
    if type(rows) is not list or len(rows) != expected_count:
        fail("frozen parent manifest count drift")
    paths: list[str] = []
    for row in rows:
        if type(row) is not dict or set(row) != {"byte_count", "path", "sha256"}:
            fail("frozen parent manifest row shape drift")
        path = row["path"]; digest = row["sha256"]; size = row["byte_count"]
        if type(path) is not str or Path(path).is_absolute() or Path(path).as_posix() != path or ".." in Path(path).parts:
            fail("frozen parent manifest path invalid")
        if type(size) is not int or size < 0 or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            fail("frozen parent manifest row value invalid")
        paths.append(path)
    if paths != sorted(set(paths)):
        fail("frozen parent manifest paths not sorted unique")
    return manifest

def require_parents() -> None:
    head = git("rev-parse", "HEAD^{commit}").stdout.strip()
    if git("cat-file", "-t", BASE["commit"]).stdout.strip() != "commit": fail("base is not a commit")
    if git("rev-parse", f"{BASE['commit']}^{{tree}}").stdout.strip() != BASE["tree"]: fail("base tree drift")
    if git("merge-base", "--is-ancestor", BASE["commit"], head, check=False).returncode != 0: fail("HEAD does not descend from base")
    for p in PARENTS:
        commit = p["merge_commit"]
        if git("cat-file", "-t", commit).stdout.strip() != "commit": fail("parent merge is not a commit")
        if git("rev-parse", f"{commit}^{{commit}}").stdout.strip() != commit: fail("missing frozen merge")
        if git("rev-parse", f"{commit}^{{tree}}").stdout.strip() != p["merge_tree"]: fail("frozen merge tree drift")
        if git("merge-base", "--is-ancestor", commit, head, check=False).returncode != 0: fail("HEAD does not descend from parent merge")
        for key in ("profile_path", "source_manifest_path"):
            raw = git("show", f"{commit}:{p[key]}").stdout.encode()
            expected = p["profile_sha256" if key == "profile_path" else "source_manifest_sha256"]
            if sha(raw) != expected: fail(f"frozen {key} drift")
            current = (ROOT / p[key]).read_bytes()
            if current != raw: fail(f"checked-out immutable {key} differs from frozen merge")
            if key == "profile_path":
                if canonical_bytes(json.loads(raw)) != raw: fail("frozen parent profile is not canonical JSON")
            else:
                require_parent_manifest(raw, p["source_manifest_entry_count"])
        reviewed_tree = reviewed_head_tree_if_present(p["reviewed_head"])
        if reviewed_tree is not None and reviewed_tree != p["merge_tree"]:
            fail("reviewed-head tree drift")

def discover_source_paths(root: Path = ROOT) -> list[Path]:
    paths: set[Path] = set(IMPLEMENTATION_PATHS)
    paths.update((DOC_RELATIVE_PATH, UNIT_RELATIVE_PATH, VERIFIER_RELATIVE_PATH, WORKFLOW_RELATIVE_PATH))
    for p in PARENTS:
        manifest = json.loads((root / p["source_manifest_path"]).read_bytes())
        paths.update(Path(row["path"]) for row in manifest["files"])
        paths.update((Path(p["profile_path"]), Path(p["source_manifest_path"])))
    paths.difference_update((PROFILE_RELATIVE_PATH, SOURCE_MANIFEST_RELATIVE_PATH))
    missing = [p.as_posix() for p in paths if not (root / p).is_file()]
    if missing: fail(f"missing source paths: {missing}")
    return sorted(paths, key=lambda p: p.as_posix())

def build_source_manifest(root: Path = ROOT) -> dict:
    rows = [{"path": p.as_posix(), "sha256": sha((root / p).read_bytes())} for p in discover_source_paths(root)]
    return {"schema_id": SOURCE_SCHEMA_ID, "scope": "pme_composite_dynamics_v1_current_sources_build_tests_evidence_and_frozen_parents", "evidence_paths": sorted(p.as_posix() for p in EVIDENCE_PATHS), "files": rows}

def build_profile(manifest_raw: bytes) -> dict:
    manifest = json.loads(manifest_raw)
    return {
        "schema_id": SCHEMA_ID, "profile_id": PROFILE_ID, "roadmap_issue": 434, "successor_base": BASE, "parents": list(PARENTS),
        "abi": {"abi_version": 1, "abi_version_major": 1, "abi_version_minor": 0, "abi_version_string": "1.0.0", "profile_id": PROFILE_ID, "header": "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h", "public_symbol_count": 13, "public_symbols": list(PUBLIC_SYMBOLS), "symbol_version_node": "BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_1.0", "checkpoint_magic": "BGPME001", "checkpoint_header_size_bytes": 104},
        "implementation": {"deep_owned_model": True, "shared_integrator_and_transactional_rollback": True, "explicit_cpp_cpu_reference_lane": True, "explicit_rust_cpu_lane": True, "auto_and_hip_requests_rejected": True, "hip_to_cpu_fallback": False, "ignored_direct_reciprocal_bounds_normalized_in_fingerprint": True, "same_lane_checkpoint_exact_only": True, "cross_lane_bit_parity_claimed": False, "fixed64_cpu_v7_qualification_invoked": False, "hip_device_execution_invoked": False, "molecular_execution_invoked": False, "source_manifest_entry_count": len(manifest["files"]), "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(), "source_manifest_sha256": sha(manifest_raw)},
        "validation": {"canonical_vendor_byte_identity": True, "c11_public_header_probe": True, "cpp_layout_probe": True, "release_sanitizer_and_export_tests": True, "rust_raw_safe_docs_fmt_clippy": True, "checkpoint_transactional_rollback": True, "git_object_probes_lazy_fetch_disabled": True, "reviewed_heads_optional_locally": True, "workflow_reviewed_heads_explicitly_fetched": True},
        "authority": AUTHORITY, "operational_boundary": {"blockers": BLOCKERS, "unresolved_operational_decisions": 32},
    }

def is_dynamics_symbol(symbol: str) -> bool:
    return (
        symbol.startswith("bg_particle_mesh_ewald_composite_dynamics_")
        or symbol.startswith("bg_particle_mesh_ewald_composite_simulation_v1_")
        or symbol == "bg_context_integrate_particle_mesh_ewald_composite_v1"
    )

def extract_public_symbol_surfaces(root: Path = ROOT) -> dict[str, tuple[str, ...]]:
    header = (root / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h").read_text()
    dynamics = (root / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp").read_text()
    checkpoint = (root / "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp").read_text()
    version_map = (root / "native/betelgeuze_engine.map").read_text()
    exports = (root / "native/betelgeuze_engine.exports").read_text()
    export_test = (root / "native/tests/check_exports.cmake").read_text()
    sys_source = (root / "rust/betelgeuze-sys/src/lib.rs").read_text()
    node = re.search(
        r"BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_1\.0 \{\n"
        r"[ \t]+global:\n(?P<body>.*?)\n"
        r"\} BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_1\.0;",
        version_map, re.DOTALL,
    )
    if node is None:
        fail("exact PME composite-dynamics ELF node or parent changed")
    export_block = re.search(
        r"set\(particle_mesh_ewald_composite_dynamics_v1_symbols\n(?P<body>.*?)\n\)",
        export_test, re.DOTALL,
    )
    if export_block is None:
        fail("export regression PME dynamics group missing")
    mapping_tokens = (
        'list(FIND particle_mesh_ewald_composite_dynamics_v1_symbols "${unversioned}" particle_mesh_ewald_composite_dynamics_v1_index)',
        'set(expected_version "BETELGEUZE_PARTICLE_MESH_EWALD_COMPOSITE_DYNAMICS_1.0")',
    )
    if any(token not in export_test for token in mapping_tokens):
        fail("export regression PME dynamics version mapping changed")
    predicate = lambda values: tuple(value for value in values if is_dynamics_symbol(value))
    return {
        "header": predicate(re.findall(r"\b(bg_[a-z0-9_]+)\s*\(", header)),
        "native": predicate(re.findall(r'extern "C" BG_API[^\n]*\n(bg_[a-z0-9_]+)\s*\(', dynamics + "\n" + checkpoint)),
        "linux_map": tuple(re.findall(r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+);[ \t]*$", node.group("body"))),
        "darwin_exports": predicate(line[1:] for line in exports.splitlines() if line.startswith("_")),
        "check_exports": tuple(re.findall(r"(?m)^[ \t]+(bg_[A-Za-z0-9_]+)[ \t]*$", export_block.group("body"))),
        "rust_sys": predicate(re.findall(r"\bpub fn (bg_[a-z0-9_]+)\s*\(", sys_source)),
    }

def require_exact_public_symbols(root: Path = ROOT) -> None:
    if len(PUBLIC_SYMBOLS) != 13 or len(set(PUBLIC_SYMBOLS)) != 13:
        fail("PME composite-dynamics ABI symbol constant changed")
    for surface, symbols in extract_public_symbol_surfaces(root).items():
        if symbols != PUBLIC_SYMBOLS:
            fail(f"PME composite-dynamics public symbol set changed: {surface}")

def require_workflow_contract(workflow: str) -> None:
    permission_headers = re.findall(r"(?m)^[ \t]*permissions:[ \t]*(?:#.*)?$", workflow)
    if (
        len(permission_headers) != 1
        or workflow.count("permissions:") != 1
        or workflow.count("permissions:\n  contents: read\n\nconcurrency:") != 1
        or re.search(r"(?m)^[ \t]+permissions:[ \t]*(?:#.*)?$", workflow) is not None
    ):
        fail("workflow must have exactly one global contents: read permission")
    if "write-all" in workflow:
        fail("workflow write-all permission is forbidden")
    if re.search(r"\b(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|security-events|statuses):\s*write\b", workflow):
        fail("workflow write permission is forbidden")
    if "pull_request_target:" in workflow or "workflow_run:" in workflow or "self-hosted" in workflow:
        fail("privileged workflow trigger or runner is forbidden")
    cpu_environment = (
        'env:\n'
        '  CUDA_VISIBLE_DEVICES: ""\n'
        '  HIP_VISIBLE_DEVICES: ""\n'
        '  ROCR_VISIBLE_DEVICES: ""\n\n'
        'jobs:'
    )
    if workflow.count(cpu_environment) != 1:
        fail("workflow global CPU-only environment changed")
    pull_match = re.search(r"^  pull_request:\n(?P<body>.*?)^  push:\n", workflow, re.MULTILINE | re.DOTALL)
    push_match = re.search(r"^  push:\n(?P<body>.*?)^  workflow_dispatch:\n", workflow, re.MULTILINE | re.DOTALL)
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
            else r'\A    branches: \["main"\]\n    paths:\n(?P<paths>(?:      - "[^"]+"\n)+)\Z'
        )
        structured = re.fullmatch(shape, body)
        if structured is None:
            fail(f"workflow {label} path trigger structure drift")
        observed = re.findall(r'^      - "([^"]+)"$', structured.group("paths"), re.MULTILINE)
        if len(observed) != len(set(observed)) or sorted(observed) != expected_paths:
            fail(f"workflow {label} path trigger set drift")
    for name in ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"):
        if workflow.count(name) != 1 or workflow.count(f'{name}: ""') != 1:
            fail(f"workflow must set global empty {name} exactly once")
    uses = re.findall(r"^\s*uses:\s*(\S+)\s*(?:#.*)?$", workflow, re.MULTILINE)
    if uses != [PINNED_CHECKOUT_ACTION] * 4:
        fail("workflow actions must be exactly four pinned checkout uses")
    if workflow.count("cmake -S . -B ") != 3:
        fail("workflow must contain exactly three CMake configurations")
    if workflow.count("DBG_ENABLE_HIP=OFF") != 3 or workflow.count("DBG_ENABLE_HIP_SAFE=OFF") != 3:
        fail("every CMake configuration must disable both HIP modes")
    if "DBG_ENABLE_HIP=ON" in workflow or "DBG_ENABLE_HIP_SAFE=ON" in workflow:
        fail("HIP-enabled configuration is forbidden")
    configurations = re.findall(r"(?ms)^\s*cmake -S \. -B .*?(?=^\s*cmake --build )", workflow)
    if len(configurations) != 3:
        fail("workflow CMake configure-to-build structure drift")
    for configuration in configurations:
        if configuration.count("DBG_ENABLE_HIP=OFF") != 1 or configuration.count("DBG_ENABLE_HIP_SAFE=OFF") != 1:
            fail("each CMake configuration must independently disable both HIP modes")
    required = (
        "pull_request:", "push:", "workflow_dispatch:", 'branches: ["main"]',
        WORKFLOW_RELATIVE_PATH.as_posix(), "tools/__init__.py",
        "tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_v1.py",
        "refs/pull/442/head", "refs/pull/443/head", "pytest==8.3.5",
        "cargo package --manifest-path rust/betelgeuze-sys/Cargo.toml --locked",
        "cargo package --manifest-path rust/betelgeuze-runtime/Cargo.toml --locked",
        "BETELGEUZE_V7_NON_AUTHORITATIVE_PACKAGE_BUILD=1",
        'BETELGEUZE_V7_SOURCE_ROOT="$GITHUB_WORKSPACE"',
    )
    for token in required:
        if token not in workflow:
            fail(f"workflow missing {token}")
    forbidden_anywhere = ("--refresh", "BG_REQUIRE_HIP_DEVICE", "qualification", "molecular", "benchmark", "supervisor", "reservation", "hipcc", "rocminfo")
    in_run = False; run_indent = 0; commands: list[str] = []
    for line in workflow.splitlines():
        stripped = line.lstrip(); indent = len(line) - len(stripped)
        if stripped.startswith("run:"):
            in_run = True; run_indent = indent; commands.append(stripped[4:]); continue
        if in_run and stripped and indent <= run_indent: in_run = False
        if in_run: commands.append(stripped)
    command_text = "\n".join(commands).lower()
    if any(word.lower() in command_text for word in forbidden_anywhere):
        fail("workflow contains forbidden execution token")
    if "--allow-dirty" in command_text:
        fail("dirty package validation is forbidden")
    for patch in ("betelgeuze-sys", "betelgeuze-cpu-kernel", "betelgeuze-docking-search", "betelgeuze-reference-physics", "betelgeuze-reference-dynamics"):
        if command_text.count(f"patch.crates-io.{patch}.path") != (2 if patch == "betelgeuze-cpu-kernel" else 1):
            fail(f"workflow package patch count drift: {patch}")

def require_contracts(root: Path = ROOT) -> None:
    header = (root / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h").read_text()
    native = (root / "native/src/composite/particle_mesh_ewald_composite_dynamics.cpp").read_text()
    checkpoint = (root / "native/src/composite/particle_mesh_ewald_composite_checkpoint.cpp").read_text()
    runtime = (root / "rust/betelgeuze-runtime/src/particle_mesh_ewald_composite_dynamics.rs").read_text()
    combined = header + native
    for symbol in PUBLIC_SYMBOLS:
        if symbol not in combined: fail(f"missing ABI symbol {symbol}")
    for token in ("BGPME001", "104"):
        if token not in header + checkpoint + runtime: fail(f"missing checkpoint token {token}")
    require_exact_public_symbols(root)
    if (root / "include/betelgeuze/particle_mesh_ewald_composite_dynamics.h").read_bytes() != (root / "rust/betelgeuze-sys/vendor/include/betelgeuze/particle_mesh_ewald_composite_dynamics.h").read_bytes(): fail("vendor header drift")
    for name in ("particle_mesh_ewald_composite.cpp", "particle_mesh_ewald_composite_dynamics.cpp", "particle_mesh_ewald_composite_checkpoint.cpp", "particle_mesh_ewald_composite_dynamics.hpp", "particle_mesh_ewald_composite_evaluator.hpp"):
        if (root / "native/src/composite" / name).read_bytes() != (root / "rust/betelgeuze-sys/vendor/native/src/composite" / name).read_bytes(): fail(f"vendor {name} drift")
    workflow = (root / WORKFLOW_RELATIVE_PATH).read_text()
    require_workflow_contract(workflow)

def verify(root: Path = ROOT) -> dict:
    require_parents(); require_contracts(root)
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest_raw != canonical_bytes(manifest) or manifest != build_source_manifest(root): fail("source manifest drift")
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes(); profile = json.loads(profile_raw)
    if profile_raw != canonical_bytes(profile) or profile != build_profile(manifest_raw): fail("profile drift")
    return {"profile_sha256": sha(profile_raw), "source_manifest_sha256": sha(manifest_raw), "source_count": len(manifest["files"])}

def refresh(root: Path = ROOT) -> dict:
    require_parents(); require_contracts(root)
    manifest_raw = canonical_bytes(build_source_manifest(root)); (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    (root / PROFILE_RELATIVE_PATH).write_bytes(canonical_bytes(build_profile(manifest_raw)))
    return verify(root)

def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--refresh", action="store_true"); args = parser.parse_args()
    result = refresh() if args.refresh else verify(); print(json.dumps(result, sort_keys=True)); return 0

if __name__ == "__main__":
    try: raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"verification failed: {error}", file=sys.stderr); raise SystemExit(1)
