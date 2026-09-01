#!/usr/bin/env python3
"""Verify native PME Rust-adapter validated non-empty input SoA binding."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import sys
from typing import NoReturn

from tools import (
    verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_v1
    as predecessor_verifier,
)


ROOT = Path(__file__).resolve().parents[1]
STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding"
)
WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-validated-nonempty-input-soa-binding"
)
WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-validated-nonempty-input-soa-binding"
)
PREDECESSOR_STEM = (
    "engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_error_output_reference_binding"
)
PREDECESSOR_WORKFLOW_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-error-output-reference-binding"
)
PREDECESSOR_WORKFLOW_FILENAME_STEM = (
    "ci-engine-v2-native-particle-mesh-ewald-composite-dynamics-"
    "rust-reciprocal-provider-error-output-reference-binding"
)

PROFILE_RELATIVE_PATH = Path("config/%s_profile_v1.json" % STEM)
SOURCE_MANIFEST_RELATIVE_PATH = Path("config/%s_profile_v1_sources.json" % STEM)
WORKFLOW_RELATIVE_PATH = Path(
    ".github/workflows/%s.yml" % WORKFLOW_FILENAME_STEM
)
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
    ".github/workflows/%s.yml" % PREDECESSOR_WORKFLOW_FILENAME_STEM
)
PREDECESSOR_DOC_RELATIVE_PATH = Path("docs/%s_v1.md" % PREDECESSOR_STEM)
PREDECESSOR_UNIT_RELATIVE_PATH = Path("tests/unit/test_%s_v1.py" % PREDECESSOR_STEM)
PREDECESSOR_VERIFIER_RELATIVE_PATH = Path(
    "tools/verify_%s_v1.py" % PREDECESSOR_STEM
)

ADAPTER_RELATIVE_PATH = Path(
    "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
)
VENDOR_ADAPTER_RELATIVE_PATH = Path(
    "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
    "rust_evaluator.cpp"
)
ADAPTER_TEST_RELATIVE_PATH = Path(
    "native/tests/particle_mesh_reciprocal_rust_adapter_transactionality.cpp"
)

SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_profile/1.0.0"
)
SOURCE_SCHEMA_ID = (
    "betelgeuze.engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_sources/1.0.0"
)
PINNED_CHECKOUT_ACTION = (
    "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
)
PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_energy_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)
FORCE_PRIVATE_SYMBOL = (
    "bg_rust_particle_mesh_reciprocal_evaluate_reusing_force_output_with_"
    "workspace_and_neutrality_sort_scratch_and_particle_assignment_scratch_v1"
)

PREDECESSOR = {
    "pull_request": 484,
    "reviewed_head": "3b3a64c29c419c2e9c49a8f3f740c307201a684d",
    "merge_commit": "57110c81ef1b65de034bb0a4d0fff70cb9a1445b",
    "merge_tree": "30155bc6d8f13421157f926e8721dc1bdbc0f39c",
    "profile_path": PREDECESSOR_PROFILE_RELATIVE_PATH.as_posix(),
    "profile_sha256": (
        "1d8f56829c150e90ef4659b5bd3b4762829fb0a744d98c3dde841dc82f5e5fb0"
    ),
    "source_manifest_path": PREDECESSOR_MANIFEST_RELATIVE_PATH.as_posix(),
    "source_manifest_sha256": (
        "58c82873431f1bfb0cc0421a5d9d448f517442c7818622e64ef1a4c2c0135c5b"
    ),
    "source_manifest_entry_count": 435,
}

PREDECESSOR_EVIDENCE_SHA256 = {
    PREDECESSOR_WORKFLOW_RELATIVE_PATH: (
        "462de6202eaee8ffa5d3c31954d097ce0403d251612fd093063a8b2fa6159d08"
    ),
    PREDECESSOR_PROFILE_RELATIVE_PATH: PREDECESSOR["profile_sha256"],
    PREDECESSOR_MANIFEST_RELATIVE_PATH: PREDECESSOR["source_manifest_sha256"],
    PREDECESSOR_DOC_RELATIVE_PATH: (
        "f4013816d6d00f4098d3106f5527bb1b8cfc62d37e89a69a81485918656229c8"
    ),
    PREDECESSOR_UNIT_RELATIVE_PATH: (
        "94d7061c106a9cd2be4cc06fe981a3a8bd00ed1ca6607632b245299dbdf647c6"
    ),
    PREDECESSOR_VERIFIER_RELATIVE_PATH: (
        "f00053cd0da2d8debd32d034f5c0d558dae645e105ae59624799d902b5364473"
    ),
}
EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256 = (
    "41e772e5015a29c89fc99d34f13eb3c9352678c28f207a087949ef09ab9bbbfd"
)
EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256 = (
    "5cd857c48bb7c3138f50d622772ae35bb0e79ccfd963bb8d12e2fac23761a201"
)
EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256 = (
    "4e106c951bb0bd666909a0cadcf703d34c0326519106ca9f7b70ddc07da3bf03"
)

EVIDENCE_PATHS = (
    WORKFLOW_RELATIVE_PATH,
    PROFILE_RELATIVE_PATH,
    SOURCE_MANIFEST_RELATIVE_PATH,
    DOC_RELATIVE_PATH,
    UNIT_RELATIVE_PATH,
    VERIFIER_RELATIVE_PATH,
)
PREDECESSOR_EVIDENCE_PATHS = (
    PREDECESSOR_WORKFLOW_RELATIVE_PATH,
    PREDECESSOR_PROFILE_RELATIVE_PATH,
    PREDECESSOR_MANIFEST_RELATIVE_PATH,
    PREDECESSOR_DOC_RELATIVE_PATH,
    PREDECESSOR_UNIT_RELATIVE_PATH,
    PREDECESSOR_VERIFIER_RELATIVE_PATH,
)
IMPLEMENTATION_DELTA_PATHS = (
    ADAPTER_RELATIVE_PATH,
    VENDOR_ADAPTER_RELATIVE_PATH,
)
EXPECTED_DELTA_PATHS = tuple(
    sorted(
        set(EVIDENCE_PATHS)
        | set(IMPLEMENTATION_DELTA_PATHS)
        | {PREDECESSOR_WORKFLOW_RELATIVE_PATH, PREDECESSOR_UNIT_RELATIVE_PATH},
        key=lambda path: path.as_posix(),
    )
)

OLD_VECTOR_INCLUDE = "#include <vector>\n"
OLD_DATA_OR_NULL_HELPER = """template <typename Value>
const Value *data_or_null(const std::vector<Value> &values) noexcept {
    return values.empty() ? nullptr : values.data();
}

"""
OLD_PROVIDER_SYSTEM_BINDINGS = """    provider_system.position_x = data_or_null(system.position_x);
    provider_system.position_y = data_or_null(system.position_y);
    provider_system.position_z = data_or_null(system.position_z);
    provider_system.charge = data_or_null(system.charge);"""
NEW_PROVIDER_SYSTEM_BINDINGS = """    provider_system.position_x = system.position_x.data();
    provider_system.position_y = system.position_y.data();
    provider_system.position_z = system.position_z.data();
    provider_system.charge = system.charge.data();"""

sha = predecessor_verifier.sha
git = predecessor_verifier.git
canonical_bytes = predecessor_verifier.canonical_bytes


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def replace_once(source: str, old: str, new: str, label: str) -> str:
    if source.count(old) != 1:
        fail("%s replacement anchor drift" % label)
    return source.replace(old, new, 1)


def source_region(source: str, start: str, end: str, label: str) -> str:
    if source.count(start) != 1:
        fail("%s start marker drift" % label)
    start_index = source.index(start)
    end_index = source.find(end, start_index + len(start))
    if end_index < 0:
        fail("%s end marker drift" % label)
    return source[start_index:end_index]


def frozen_bytes(path: Path) -> bytes:
    return git("show", "%s:%s" % (PREDECESSOR["merge_commit"], path)).stdout


def require_predecessor() -> dict:
    merge = PREDECESSOR["merge_commit"]
    if git("cat-file", "-t", merge).stdout.strip() != b"commit":
        fail("PR 484 predecessor merge is not a commit")
    if git("rev-parse", "%s^{commit}" % merge).stdout.strip().decode() != merge:
        fail("PR 484 predecessor merge identity drift")
    tree = git("rev-parse", "%s^{tree}" % merge).stdout.strip().decode()
    if tree != PREDECESSOR["merge_tree"]:
        fail("PR 484 predecessor merge tree drift")
    if git("merge-base", "--is-ancestor", merge, "HEAD", check=False).returncode != 0:
        fail("HEAD does not descend from exact PR 484 predecessor")
    for path, expected_sha in PREDECESSOR_EVIDENCE_SHA256.items():
        if sha(frozen_bytes(path)) != expected_sha:
            fail("exact frozen PR 484 evidence digest drift: %s" % path)
    profile_raw = frozen_bytes(PREDECESSOR_PROFILE_RELATIVE_PATH)
    manifest_raw = frozen_bytes(PREDECESSOR_MANIFEST_RELATIVE_PATH)
    profile = json.loads(profile_raw)
    manifest = json.loads(manifest_raw)
    if canonical_bytes(profile) != profile_raw or canonical_bytes(manifest) != manifest_raw:
        fail("PR 484 predecessor evidence is not canonical JSON")
    rows = manifest.get("files")
    if not isinstance(rows, list) or len(rows) != 435:
        fail("PR 484 predecessor manifest count drift")
    if [row.get("path") for row in rows] != sorted(
        {row.get("path") for row in rows}
    ):
        fail("PR 484 predecessor manifest paths are not sorted and unique")
    for path in (
        PREDECESSOR_PROFILE_RELATIVE_PATH,
        PREDECESSOR_MANIFEST_RELATIVE_PATH,
        PREDECESSOR_DOC_RELATIVE_PATH,
        PREDECESSOR_VERIFIER_RELATIVE_PATH,
    ):
        if (ROOT / path).read_bytes() != frozen_bytes(path):
            fail("checked-out PR 484 predecessor evidence drift: %s" % path)
    reviewed = PREDECESSOR["reviewed_head"]
    if git("cat-file", "-e", "%s^{commit}" % reviewed, check=False).returncode == 0:
        reviewed_tree = git("rev-parse", "%s^{tree}" % reviewed).stdout.strip().decode()
        if reviewed_tree != PREDECESSOR["merge_tree"]:
            fail("PR 484 reviewed-head tree drift")
    return manifest


def current_delta_paths() -> tuple[Path, ...]:
    tracked = git(
        "diff", "--name-only", PREDECESSOR["merge_commit"], "--"
    ).stdout.decode().splitlines()
    untracked = git(
        "ls-files", "--others", "--exclude-standard"
    ).stdout.decode().splitlines()
    return tuple(
        sorted({Path(path) for path in tracked + untracked}, key=lambda p: p.as_posix())
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
    if len(result) != 441:
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
            "validated_nonempty_input_soa_binding_current_sources_tests_"
            "evidence_pr484_target"
        ),
        "evidence_paths": sorted(path.as_posix() for path in EVIDENCE_PATHS),
        "files": rows,
    }


def build_profile(manifest_raw: bytes, root: Path = ROOT) -> dict:
    manifest = json.loads(manifest_raw)
    profile = json.loads((root / PREDECESSOR_PROFILE_RELATIVE_PATH).read_bytes())
    profile["schema_id"] = SCHEMA_ID
    profile["profile_id"] = "%s_development_v1" % STEM
    profile["target_predecessor"] = dict(PREDECESSOR)
    implementation = profile["implementation"]
    for stale_key in ("scope_is_only_native_error_output_reference_binding",):
        implementation.pop(stale_key, None)
    implementation.update(
        {
            "scope_is_only_native_validated_nonempty_input_soa_binding": True,
            "input_soa_empty_system_validation_precedes_provider_descriptor": True,
            "input_soa_count_validation_precedes_provider_descriptor": True,
            "input_soa_four_channels_nonempty_at_descriptor_binding": True,
            "input_soa_four_channels_equal_length_at_descriptor_binding": True,
            "input_soa_position_x_direct_data_binding": True,
            "input_soa_position_y_direct_data_binding": True,
            "input_soa_position_z_direct_data_binding": True,
            "input_soa_charge_direct_data_binding": True,
            "input_soa_legacy_nullable_helper_removed": True,
            "input_soa_vector_include_removed": True,
            "input_soa_provider_descriptor_field_order_preserved": True,
            "input_soa_caller_owned_addresses_preserved": True,
            "input_soa_caller_owned_lifetime_spans_provider_dispatch": True,
            "provider_system_input_pointers_non_null_by_validation": True,
            "raw_provider_zero_count_abi_semantics_preserved": True,
            "public_and_private_provider_abi_preserved": True,
            "error_output_reference_binding_preserved": True,
            "five_semantic_route_dispatch_preserved": True,
            "rollback_scratch_validation_and_commit_preserved": True,
            "validated_nonempty_input_soa_binding_performance_improvement_claimed": False,
            "validated_nonempty_input_soa_runtime_lifetime_enforcement_claimed": False,
            "validated_nonempty_input_soa_raw_provider_nullability_changed_claimed": False,
            "validated_nonempty_input_soa_object_layout_equivalence_claimed": False,
            "source_manifest_path": SOURCE_MANIFEST_RELATIVE_PATH.as_posix(),
            "source_manifest_sha256": sha(manifest_raw),
            "source_manifest_entry_count": len(manifest["files"]),
        }
    )
    validation = profile["validation"]
    for stale_key in (
        "predecessor_adapter_exact_error_output_reference_binding_transform",
        "adapter_outside_error_output_binding_exact_predecessor_bytes",
    ):
        validation.pop(stale_key, None)
    validation.update(
        {
            "exact_delta_path_count": 10,
            "implementation_delta_path_count": 2,
            "successor_evidence_path_count": 6,
            "predecessor_freeze_wiring_path_count": 2,
            "source_manifest_entry_count_exact": 441,
            "pull_request_trigger_path_count_exact": 258,
            "push_trigger_path_count_exact": 258,
            "predecessor_adapter_exact_error_output_reference_binding_bytes": True,
            "adapter_exact_validated_nonempty_input_soa_transform": True,
            "adapter_outside_input_soa_binding_exact_predecessor_bytes": True,
            "legacy_vector_include_count_exact": 0,
            "legacy_data_or_null_helper_count_exact": 0,
            "legacy_data_or_null_call_count_exact": 0,
            "direct_provider_input_data_binding_count_exact": 4,
            "position_x_direct_data_binding_count_exact": 1,
            "position_y_direct_data_binding_count_exact": 1,
            "position_z_direct_data_binding_count_exact": 1,
            "charge_direct_data_binding_count_exact": 1,
            "empty_system_validation_count_exact": 1,
            "input_count_validation_channel_count_exact": 4,
            "empty_system_validation_precedes_provider_descriptor": True,
            "input_count_validation_precedes_provider_descriptor": True,
            "direct_input_bindings_follow_provider_descriptor_metadata": True,
            "direct_input_bindings_precede_provider_dispatch": True,
            "public_wrappers_exact_predecessor_bytes": True,
            "dispatch_rollback_scratch_validation_commit_exact_predecessor_bytes": True,
            "canonical_vendor_adapter_byte_identical": True,
            "native_adapter_test_exact_predecessor_bytes": True,
            "predecessor_workflow_detaches_exact_merge_object": True,
            "predecessor_unit_skips_only_when_successor_profile_exists": True,
        }
    )
    return profile


def expected_predecessor_workflow() -> str:
    expected = frozen_bytes(PREDECESSOR_WORKFLOW_RELATIVE_PATH).decode()
    for predecessor_path, successor_path in zip(
        PREDECESSOR_EVIDENCE_PATHS, EVIDENCE_PATHS, strict=True
    ):
        anchor = '      - "%s"\n' % predecessor_path.as_posix()
        if expected.count(anchor) != 2:
            fail("exact PR 484 workflow trigger anchor drift: %s" % predecessor_path)
        expected = expected.replace(
            anchor, anchor + '      - "%s"\n' % successor_path.as_posix()
        )
    old_region = source_region(
        expected,
        "      - name: Materialize exact PR 483 target and reviewed head\n",
        "\n\n  native-linux:\n",
        "exact PR 484 immutable-evidence block",
    )
    new_region = """      - name: Materialize exact PR 484 evidence and reviewed head
        shell: bash
        run: |
          set -euo pipefail
          test "$(git rev-parse 57110c81ef1b65de034bb0a4d0fff70cb9a1445b^{tree})" = "30155bc6d8f13421157f926e8721dc1bdbc0f39c"
          git merge-base --is-ancestor 57110c81ef1b65de034bb0a4d0fff70cb9a1445b HEAD
          git fetch --no-tags --depth=1 origin refs/pull/484/head
          test "$(git rev-parse FETCH_HEAD)" = "3b3a64c29c419c2e9c49a8f3f740c307201a684d"
          test "$(git rev-parse FETCH_HEAD^{tree})" = "30155bc6d8f13421157f926e8721dc1bdbc0f39c"
      - name: Verify exact frozen PR 484 evidence
        shell: bash
        run: |
          set -euo pipefail
          frozen=57110c81ef1b65de034bb0a4d0fff70cb9a1445b
          frozen_tree=30155bc6d8f13421157f926e8721dc1bdbc0f39c
          current_sha="$(git rev-parse HEAD)"
          restore() { git checkout --detach --quiet "$current_sha"; }
          trap restore EXIT
          git checkout --detach --quiet "$frozen"
          test "$(git rev-parse HEAD^{tree})" = "$frozen_tree"
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_profile_v1.json >/dev/null
          python3 -m json.tool config/engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_profile_v1_sources.json >/dev/null
          python3 -m pip install pytest==8.3.5
          python3 -m tools.verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_v1
          python3 -m pytest -q tests/unit/test_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_error_output_reference_binding_v1.py
          restore
          trap - EXIT"""
    return replace_once(
        expected, old_region, new_region, "exact PR 484 predecessor workflow transform"
    )


def expected_predecessor_unit() -> str:
    expected = frozen_bytes(PREDECESSOR_UNIT_RELATIVE_PATH).decode()
    expected = replace_once(
        expected,
        "from pathlib import Path\n",
        "from pathlib import Path\n\nimport pytest\n",
        "exact PR 484 unit pytest import",
    )
    skip = """ROOT = Path(__file__).resolve().parents[2]
PME_RUST_RECIPROCAL_PROVIDER_VALIDATED_NONEMPTY_INPUT_SOA_BINDING_EVIDENCE_PRESENT = (
    ROOT
    / "config/engine_v2_native_particle_mesh_ewald_composite_dynamics_"
    "rust_reciprocal_provider_validated_nonempty_input_soa_binding_profile_v1.json"
).is_file()
pytestmark = pytest.mark.skipif(
    PME_RUST_RECIPROCAL_PROVIDER_VALIDATED_NONEMPTY_INPUT_SOA_BINDING_EVIDENCE_PRESENT,
    reason=(
        "error-output reference binding evidence is verified from its exact frozen PR 484 "
        "object after validated non-empty input SoA binding evidence is present"
    ),
)"""
    return replace_once(
        expected,
        "ROOT = Path(__file__).resolve().parents[2]",
        skip,
        "exact PR 484 unit successor skip",
    )


def expected_successor_workflow() -> str:
    old_hyphen = "rust-reciprocal-provider-error-output-reference-binding"
    new_hyphen = "rust-reciprocal-provider-validated-nonempty-input-soa-binding"
    old_underscore = "rust_reciprocal_provider_error_output_reference_binding"
    new_underscore = "rust_reciprocal_provider_validated_nonempty_input_soa_binding"
    expected = frozen_bytes(PREDECESSOR_WORKFLOW_RELATIVE_PATH).decode()
    expected = expected.replace(old_hyphen, new_hyphen)
    expected = expected.replace(old_underscore, new_underscore)
    for predecessor_path, successor_path in zip(
        PREDECESSOR_EVIDENCE_PATHS, EVIDENCE_PATHS, strict=True
    ):
        anchor = '      - "%s"\n' % successor_path.as_posix()
        if expected.count(anchor) != 2:
            fail("successor workflow trigger anchor drift: %s" % successor_path)
        expected = expected.replace(
            anchor, '      - "%s"\n' % predecessor_path.as_posix() + anchor
        )
    replacements = (
        ("Materialize exact PR 483 target", "Materialize exact PR 484 target"),
        ("e51f10d6034bc9abf86017b879a5b777834cb3db", PREDECESSOR["merge_commit"]),
        ("9e9fc3099422870ddb03d5ff01874480ba9c71be", PREDECESSOR["merge_tree"]),
        ("refs/pull/483/head", "refs/pull/484/head"),
        ("9138a05e9730b1892ee56a3133ffc48f8439ee92", PREDECESSOR["reviewed_head"]),
    )
    for old, new in replacements:
        if old not in expected:
            fail("successor workflow predecessor pin anchor drift: %s" % old)
        expected = expected.replace(old, new)
    return expected


def workflow_trigger_paths(workflow: str, event: str, end: str) -> tuple[str, ...]:
    region = source_region(
        workflow, "  %s:\n" % event, "  %s:\n" % end, "%s trigger" % event
    )
    return tuple(re.findall(r'^      - "([^"]+)"$', region, flags=re.MULTILINE))


def require_workflow_contract(root: Path = ROOT) -> None:
    predecessor = (root / PREDECESSOR_WORKFLOW_RELATIVE_PATH).read_text()
    successor = (root / WORKFLOW_RELATIVE_PATH).read_text()
    if predecessor != expected_predecessor_workflow():
        fail("PR 484 predecessor workflow is not the exact frozen-object transform")
    if successor != expected_successor_workflow():
        fail("successor workflow is not the exact PR 484-derived transform")
    expected_names = {
        PREDECESSOR_WORKFLOW_RELATIVE_PATH: PREDECESSOR_WORKFLOW_STEM,
        WORKFLOW_RELATIVE_PATH: WORKFLOW_STEM,
    }
    for path, expected_name in expected_names.items():
        workflow = (root / path).read_text()
        pull_paths = workflow_trigger_paths(workflow, "pull_request", "push")
        push_paths = workflow_trigger_paths(workflow, "push", "workflow_dispatch")
        if len(pull_paths) != 258 or len(set(pull_paths)) != 258:
            fail("workflow 258-path unique pull-request trigger drift: %s" % path)
        if push_paths != pull_paths:
            fail("workflow pull-request/push trigger symmetry drift: %s" % path)
        if workflow.count("name: %s\n" % expected_name) != 1:
            fail("workflow name drift: %s" % path)
        if workflow.count(PINNED_CHECKOUT_ACTION) != 4:
            fail("workflow checkout pin drift: %s" % path)
        if "--refresh" in workflow:
            fail("workflow must not refresh evidence: %s" % path)
    for path in EVIDENCE_PATHS + PREDECESSOR_EVIDENCE_PATHS:
        token = '      - "%s"\n' % path.as_posix()
        if successor.count(token) != 2:
            fail("successor workflow evidence trigger drift: %s" % path)
        if predecessor.count(token) != 2:
            fail("predecessor workflow successor trigger drift: %s" % path)
    for token in (
        "git checkout --detach --quiet \"$frozen\"",
        PREDECESSOR["merge_commit"],
        PREDECESSOR["merge_tree"],
        "refs/pull/484/head",
        PREDECESSOR["reviewed_head"],
    ):
        if token not in predecessor:
            fail("PR 484 predecessor workflow freeze drift: %s" % token)


def require_predecessor_unit_freeze(root: Path = ROOT) -> None:
    source = (root / PREDECESSOR_UNIT_RELATIVE_PATH).read_text()
    if source != expected_predecessor_unit():
        fail("PR 484 predecessor unit is not the exact frozen-object transform")
    tree = ast.parse(source)
    constants = {
        value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance((value := node.value), str)
    }
    if not any("PR 484 object" in value for value in constants):
        fail("PR 484 predecessor unit frozen-object reason drift")
    if source.count("pytest.mark.skipif(") != 1:
        fail("PR 484 predecessor unit skip drift")



def expected_successor_adapter() -> str:
    frozen_source = frozen_bytes(ADAPTER_RELATIVE_PATH).decode()
    if frozen_source.count(OLD_VECTOR_INCLUDE) != 1:
        fail("exact PR 484 vector include anchor drift")
    if frozen_source.count(OLD_DATA_OR_NULL_HELPER) != 1:
        fail("exact PR 484 nullable input helper anchor drift")
    if frozen_source.count(OLD_PROVIDER_SYSTEM_BINDINGS) != 1:
        fail("exact PR 484 provider-system input binding anchor drift")
    expected = replace_once(
        frozen_source,
        OLD_VECTOR_INCLUDE,
        "",
        "validated non-empty input vector include removal",
    )
    expected = replace_once(
        expected,
        OLD_DATA_OR_NULL_HELPER,
        "",
        "validated non-empty input nullable helper removal",
    )
    expected = replace_once(
        expected,
        OLD_PROVIDER_SYSTEM_BINDINGS,
        NEW_PROVIDER_SYSTEM_BINDINGS,
        "validated non-empty input direct SoA binding",
    )
    return expected


def require_validated_nonempty_input_soa_contract(root: Path = ROOT) -> None:
    frozen = frozen_bytes(ADAPTER_RELATIVE_PATH)
    if sha(frozen) != EXPECTED_PREDECESSOR_IMPLEMENTATION_SHA256:
        fail("exact PR 484 adapter digest drift")
    expected = expected_successor_adapter()
    for path in IMPLEMENTATION_DELTA_PATHS:
        raw = (root / path).read_bytes()
        if sha(raw) != EXPECTED_SUCCESSOR_IMPLEMENTATION_SHA256:
            fail("successor adapter digest drift: %s" % path)
        if raw.decode() != expected:
            fail("adapter is not the exact PR 484 validated-input transform: %s" % path)

    canonical = (root / ADAPTER_RELATIVE_PATH).read_text()
    vendor = (root / VENDOR_ADAPTER_RELATIVE_PATH).read_text()
    if canonical != vendor:
        fail("canonical/vendor adapter byte identity drift")
    evaluate_impl = source_region(
        canonical,
        "static bg_status evaluate_impl(\n",
        "\nbg_status evaluate(\n",
        "evaluate_impl",
    )
    frozen_wrappers = source_region(
        frozen.decode(),
        "\nbg_status evaluate(\n",
        "\n}  // namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu",
        "exact PR 484 public wrappers",
    )
    wrappers = source_region(
        canonical,
        "\nbg_status evaluate(\n",
        "\n}  // namespace betelgeuze::native::particle_mesh_reciprocal::rust_cpu",
        "public wrappers",
    )
    if wrappers != frozen_wrappers:
        fail("public wrappers changed from exact PR 484 bytes")
    if canonical.count("#include <vector>") != 0:
        fail("legacy vector include remains")
    if canonical.count("data_or_null") != 0:
        fail("legacy nullable input helper or call remains")
    direct_bindings = (
        "provider_system.position_x = system.position_x.data();",
        "provider_system.position_y = system.position_y.data();",
        "provider_system.position_z = system.position_z.data();",
        "provider_system.charge = system.charge.data();",
    )
    for binding in direct_bindings:
        if evaluate_impl.count(binding) != 1:
            fail("direct provider input binding drift: %s" % binding)
    if evaluate_impl.count("atom_count == 0U") != 1:
        fail("empty-system validation count drift")
    count_validation_tokens = (
        "system.position_y.size() != atom_count",
        "system.position_z.size() != atom_count",
        "system.charge.size() != atom_count",
        "model.atom_count != atom_count",
    )
    for token in count_validation_tokens:
        if evaluate_impl.count(token) != 1:
            fail("input count validation drift: %s" % token)
    empty_validation = evaluate_impl.index("if (atom_count == 0U) {")
    count_validation = evaluate_impl.index(
        "if (system.position_y.size() != atom_count ||"
    )
    descriptor = evaluate_impl.index(
        "bg_rust_particle_mesh_reciprocal_system_v1 provider_system{};"
    )
    atom_count_binding = evaluate_impl.index(
        "provider_system.atom_count = atom_count;"
    )
    first_input_binding = evaluate_impl.index(direct_bindings[0])
    last_input_binding = evaluate_impl.index(direct_bindings[-1])
    provider_dispatch = evaluate_impl.index(
        "const bg_status status = normalize_provider_status("
    )
    if not (
        empty_validation
        < count_validation
        < descriptor
        < atom_count_binding
        < first_input_binding
        < last_input_binding
        < provider_dispatch
    ):
        fail("validated non-empty input descriptor ordering drift")
    if evaluate_impl.count("Error &output_error = *out_error;") != 1:
        fail("inherited error-output reference binding drift")
    for token in (
        "BG_PARTICLE_MESH_RECIPROCAL_ERROR_EMPTY_SYSTEM",
        "BG_PARTICLE_MESH_RECIPROCAL_ERROR_CAPACITY_EXCEEDED",
        "BG_PARTICLE_MESH_RECIPROCAL_ERROR_CHARGE_COUNT_MISMATCH",
        "static_cast<bg_particle_mesh_reciprocal_error_code>(",
        "provider_error.detail",
        "evaluation_force_storage_rollback.commit();",
    ):
        if evaluate_impl.count(token) < 1:
            fail("inherited validation/mapping/commit drift: %s" % token)
    test_raw = (root / ADAPTER_TEST_RELATIVE_PATH).read_bytes()
    if sha(frozen_bytes(ADAPTER_TEST_RELATIVE_PATH)) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("exact PR 484 native adapter test digest drift")
    if sha(test_raw) != EXPECTED_PREDECESSOR_ADAPTER_TEST_SHA256:
        fail("native adapter test changed from exact PR 484 bytes")


def require_docs_contract(root: Path = ROOT) -> None:
    doc = (root / DOC_RELATIVE_PATH).read_text()
    required = (
        "exact PR 484\npredecessor",
        "`atom_count == 0U`",
        "all four input channels have the same positive length",
        "`std::vector::data()` pointers",
        "`data_or_null` empty-vector branch",
        "same caller-owned vector storage",
        "raw provider ABI",
        "does not add runtime lifetime enforcement",
        "exactly four helper calls",
        "canonical and vendored adapters",
        "all five semantic dispatch routes",
        "output-force rollback",
        "success-only external commit",
        "fake-provider transactionality test still covers all five route",
        "successor adapter SHA-256",
        "441 sorted unique paths",
        "258 unique\nsymmetric pull-request and push trigger paths",
        "four blockers",
        "32 unresolved operational decisions",
        "no\nperformance, allocation, object-size, stack-size, acceleration, scientific",
    )
    for token in required:
        if token not in doc:
            fail("documentation contract drift: %s" % token)


def require_profile_and_manifest(root: Path = ROOT) -> tuple[dict, dict]:
    manifest_raw = (root / SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    profile_raw = (root / PROFILE_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    profile = json.loads(profile_raw)
    if canonical_bytes(manifest) != manifest_raw or canonical_bytes(profile) != profile_raw:
        fail("successor evidence is not canonical JSON")
    if manifest != build_source_manifest(root):
        fail("source manifest drift; run verifier with --refresh")
    if profile != build_profile(manifest_raw, root):
        fail("profile drift; run verifier with --refresh")
    implementation = profile["implementation"]
    for key in (
        "scope_is_only_native_validated_nonempty_input_soa_binding",
        "input_soa_empty_system_validation_precedes_provider_descriptor",
        "input_soa_count_validation_precedes_provider_descriptor",
        "input_soa_four_channels_nonempty_at_descriptor_binding",
        "input_soa_four_channels_equal_length_at_descriptor_binding",
        "input_soa_position_x_direct_data_binding",
        "input_soa_position_y_direct_data_binding",
        "input_soa_position_z_direct_data_binding",
        "input_soa_charge_direct_data_binding",
        "input_soa_legacy_nullable_helper_removed",
        "input_soa_vector_include_removed",
        "input_soa_provider_descriptor_field_order_preserved",
        "input_soa_caller_owned_addresses_preserved",
        "input_soa_caller_owned_lifetime_spans_provider_dispatch",
        "provider_system_input_pointers_non_null_by_validation",
        "raw_provider_zero_count_abi_semantics_preserved",
        "public_and_private_provider_abi_preserved",
        "error_output_reference_binding_preserved",
        "five_semantic_route_dispatch_preserved",
        "rollback_scratch_validation_and_commit_preserved",
        "evaluation_rollback_candidate_force_storage_type_alias_exact",
        "evaluation_rollback_candidate_force_storage_type_derived_from_evaluation_member",
        "evaluation_rollback_candidate_force_storage_nothrow_swap_assertion_exact",
        "evaluation_rollback_candidate_force_storage_is_non_null_reference",
        "evaluation_rollback_candidate_force_storage_reference_bound_once",
        "evaluation_rollback_whole_candidate_reference_parameter_removed",
        "evaluation_rollback_whole_candidate_reference_member_removed",
        "evaluation_rollback_candidate_force_storage_uses_direct_reference_access",
        "evaluation_rollback_callsite_passes_candidate_force_storage",
        "evaluation_rollback_candidate_declaration_precedes_guard",
        "evaluation_rollback_candidate_force_storage_lifetime_order_preserved",
        "evaluation_rollback_output_force_storage_type_alias_exact",
        "evaluation_rollback_output_force_storage_type_derived_from_evaluation_member",
        "evaluation_rollback_output_force_storage_is_nullable_pointer",
        "evaluation_rollback_output_force_storage_pointer_bound_once",
        "evaluation_rollback_whole_output_pointer_parameter_removed",
        "evaluation_rollback_whole_output_pointer_member_removed",
        "evaluation_rollback_output_force_storage_uses_direct_pointer_dereference",
        "evaluation_rollback_callsite_passes_output_force_storage_address",
        "evaluation_rollback_callsite_address_formation_guarded_by_nonnull_output",
        "evaluation_rollback_activation_predicate_localized_at_callsite",
        "evaluation_rollback_activation_uses_compute_forces_reuse_and_nonnull_output",
        "evaluation_rollback_provider_force_source_null_output_short_circuits_address_formation",
        "evaluation_rollback_output_force_storage_pointer_is_sole_activation_and_commit_sentinel",
        "evaluation_rollback_commit_disarms_via_output_force_storage_pointer_only",
        "evaluation_rollback_retained_guard_state_is_force_storage_only",
        "evaluation_rollback_initial_swap_and_destructor_restore_preserved",
        "evaluation_rollback_copy_deletion_preserved",
        "five_semantic_route_rollback_activation_truth_table_preserved",
        "dispatch_status_normalization_binding_preserved",
    ):
        if implementation.get(key) is not True:
            fail("implementation evidence drift: %s" % key)
    false_claims = (
        "validated_nonempty_input_soa_binding_performance_improvement_claimed",
        "validated_nonempty_input_soa_runtime_lifetime_enforcement_claimed",
        "validated_nonempty_input_soa_raw_provider_nullability_changed_claimed",
        "validated_nonempty_input_soa_object_layout_equivalence_claimed",
        "error_output_reference_binding_performance_improvement_claimed",
        "error_output_reference_runtime_lifetime_enforcement_claimed",
        "error_output_nullability_elision_claimed",
        "error_output_object_layout_equivalence_claimed",
        "evaluation_rollback_output_force_storage_binding_performance_improvement_claimed",
        "evaluation_rollback_output_force_storage_pointer_performance_improvement_claimed",
        "evaluation_rollback_output_force_storage_object_layout_equivalence_claimed",
        "evaluation_rollback_output_force_storage_runtime_lifetime_enforcement_claimed",
        "evaluation_rollback_output_pointer_narrowing_allocation_improvement_claimed",
        "evaluation_rollback_force_storage_binding_performance_improvement_claimed",
        "evaluation_rollback_force_storage_reference_performance_improvement_claimed",
        "evaluation_rollback_force_storage_object_layout_equivalence_claimed",
        "evaluation_rollback_force_storage_runtime_lifetime_enforcement_claimed",
        "evaluation_rollback_candidate_reference_performance_improvement_claimed",
        "evaluation_rollback_enabled_parameter_removal_performance_improvement_claimed",
        "evaluation_rollback_object_layout_equivalence_claimed",
        "evaluation_rollback_reference_runtime_lifetime_enforcement_claimed",
        "reference_binding_performance_improvement_claimed",
        "nullability_elision_performance_improvement_claimed",
        "object_size_reduction_claimed",
        "stack_storage_reduction_claimed",
        "allocation_free_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "scientific_claimed",
        "scientific_equivalence_claimed",
        "molecular_execution_claimed",
        "hip_execution_claimed",
        "product_claimed",
        "operational_readiness_claimed",
    )
    for key in false_claims:
        if implementation.get(key) is not False:
            fail("forbidden claim drift: %s" % key)
    if any(profile["authority"].values()):
        fail("authority boundary drift")
    boundary = profile["operational_boundary"]
    if len(boundary.get("blockers", [])) != 4:
        fail("operational blocker count drift")
    if boundary.get("unresolved_operational_decisions") != 32:
        fail("unresolved operational decision count drift")
    return profile, manifest


def require_contracts(root: Path = ROOT) -> None:
    require_predecessor()
    delta = current_delta_paths()
    if delta != EXPECTED_DELTA_PATHS:
        fail(
            "exact delta path drift: expected=%s actual=%s"
            % (
                [path.as_posix() for path in EXPECTED_DELTA_PATHS],
                [path.as_posix() for path in delta],
            )
        )
    require_workflow_contract(root)
    require_predecessor_unit_freeze(root)
    ast.parse((root / UNIT_RELATIVE_PATH).read_text())
    ast.parse((root / VERIFIER_RELATIVE_PATH).read_text())
    require_validated_nonempty_input_soa_contract(root)
    require_docs_contract(root)


def verify(root: Path = ROOT) -> dict:
    require_contracts(root)
    profile, manifest = require_profile_and_manifest(root)
    return {
        "schema_id": profile["schema_id"],
        "source_count": len(manifest["files"]),
        "delta_path_count": len(EXPECTED_DELTA_PATHS),
        "implementation_delta_path_count": len(IMPLEMENTATION_DELTA_PATHS),
        "trigger_path_count": 258,
        "predecessor_pull_request": PREDECESSOR["pull_request"],
        "predecessor_merge_tree": PREDECESSOR["merge_tree"],
    }


def refresh(root: Path = ROOT) -> dict:
    require_contracts(root)
    manifest = build_source_manifest(root)
    manifest_raw = canonical_bytes(manifest)
    (root / SOURCE_MANIFEST_RELATIVE_PATH).write_bytes(manifest_raw)
    profile = build_profile(manifest_raw, root)
    (root / PROFILE_RELATIVE_PATH).write_bytes(canonical_bytes(profile))
    return verify(root)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="refresh canonical profile and manifest"
    )
    args = parser.parse_args()
    result = refresh(ROOT) if args.refresh else verify(ROOT)
    json.dump(result, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
