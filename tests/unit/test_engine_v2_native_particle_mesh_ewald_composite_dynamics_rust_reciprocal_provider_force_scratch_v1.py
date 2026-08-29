import json
from pathlib import Path

import pytest

from tools import verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_rust_reciprocal_provider_force_scratch_v1 as verifier

ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 266
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    validation = profile["validation"]
    assert implementation[
        "successful_stateful_forceful_rust_reciprocal_provider_force_soa_storage_reused"
    ]
    assert implementation[
        "steady_state_rust_reciprocal_provider_force_soa_storage_reused"
    ]
    assert implementation["cpp_lane_rust_reciprocal_provider_force_scratch_unused"]
    assert implementation[
        "cpp_lane_stale_rust_reciprocal_provider_force_scratch_preserved"
    ]
    assert implementation["reciprocal_parent_force_storage_reuse_preserved"]
    assert implementation["direct_parent_force_storage_reuse_preserved"]
    assert implementation["rust_reciprocal_provider_soa_remains_local"] is False
    assert implementation[
        "rust_reciprocal_provider_internal_aos_storage_reused"
    ] is False
    assert implementation["rust_reciprocal_provider_mesh_storage_reused"] is False
    assert implementation[
        "rust_reciprocal_provider_other_workspace_reused"
    ] is False
    assert validation["cpp_lane_unused_and_stale_scratch_preservation"]
    assert validation["macos_locked_cargo_exact_signature_retry_bounded"]
    assert not any(profile["authority"].values())
    for key in (
        "allocation_free_claimed",
        "timing_claimed",
        "performance_claimed",
        "acceleration_claimed",
        "cross_lane_bit_parity_claimed",
        "checkpoint_buffer_aliasing_claimed",
        "unconditional_failure_storage_retention_claimed",
        "universal_failure_storage_retention_claimed",
        "all_failure_path_storage_retention_claimed",
    ):
        assert implementation[key] is False


def test_exact_anchors_and_delta() -> None:
    assert verifier.PREDECESSOR["pull_request"] == 455
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 440
    assert len(verifier.IMPLEMENTATION_DELTA_PATHS) == 15
    assert len(verifier.EXPECTED_DELTA_PATHS) == 23
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 84
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 84
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert (
        workflow.count(
            "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
        )
        == 4
    )


@pytest.mark.parametrize(
    "job",
    [
        "immutable-evidence",
        "native-linux",
        "rust-boundaries",
        "macos-export-boundary",
    ],
)
def test_workflow_job_body_mutation_fails_closed(job: str) -> None:
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    body = verifier.job_body(workflow, job)
    mutated = workflow.replace(body, body + "      # sentinel drift\n", 1)
    with pytest.raises(ValueError, match="workflow exact job body drift"):
        verifier.require_workflow_contract(mutated)


@pytest.mark.parametrize(
    "relative,transform",
    [
        (
            "native/src/particle_mesh_reciprocal/rust_evaluator.hpp",
            verifier.expected_rust_evaluator_header,
        ),
        (
            "rust/betelgeuze-sys/vendor/native/src/particle_mesh_reciprocal/"
            "rust_evaluator.hpp",
            verifier.expected_rust_evaluator_header,
        ),
    ],
)
def test_frozen_header_transforms_and_sentinels(relative, transform) -> None:
    frozen = verifier.git(
        "show", f"{verifier.PREDECESSOR['merge_commit']}:{relative}"
    ).stdout.decode()
    assert transform(frozen) == (ROOT / relative).read_text()
    sentinel = "\n// unrelated-frozen-input-sentinel\n"
    assert transform(frozen + sentinel).endswith(sentinel)
    with pytest.raises(ValueError, match="transformation point drift"):
        transform(
            frozen.replace(
                '#include "cpp_evaluator.hpp"\n',
                '#include "drifted.hpp"\n',
                1,
            )
        )


def test_provider_sources_frozen_and_binding_order() -> None:
    merge = verifier.PREDECESSOR["merge_commit"]
    for relative, digest in verifier.FROZEN_PROVIDER_SOURCE_SHA256.items():
        frozen = verifier.git("show", f"{merge}:{relative}").stdout
        assert verifier.sha(frozen) == digest
        assert frozen == (ROOT / relative).read_bytes()
    source = (
        ROOT / "native/src/particle_mesh_reciprocal/rust_evaluator.cpp"
    ).read_text()
    resize = source.index("active_provider_force_scratch->x.resize(atom_count);")
    capacity = source.index("provider_forces.capacity = atom_count;")
    data = source.index("provider_forces.x = active_provider_force_scratch->x.data();")
    assert resize < capacity < data


def test_production_hashes_and_vendor_identity() -> None:
    verifier.require_rust_reciprocal_provider_force_scratch_contract(ROOT)


def test_predecessor_freezes() -> None:
    verifier.require_predecessor_workflow_freeze(ROOT)
    verifier.require_predecessor_unit_freeze(ROOT)
    verifier.require_macos_lock_transient_retry_workflow(ROOT)


def test_macos_locked_cargo_transient_retry_remains_exact() -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
        f"{verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_macos_lock_transient_retry_workflow(frozen)
    assert transformed == (
        ROOT / verifier.MACOS_RETRY_WORKFLOW_RELATIVE_PATH
    ).read_text()
    for token in (
        "        shell: bash",
        'build_pipeline_status=("${PIPESTATUS[@]}")',
        'tee_status="${build_pipeline_status[1]}"',
        'grep -Fq "xcrun_db-"',
        'grep -Fq "errno=Invalid argument"',
        'grep -Fq "cannot update the lock file"',
        'grep -Fq "because --locked was passed"',
        'cargo metadata --manifest-path rust/Cargo.toml --locked',
    ):
        assert token in transformed


@pytest.mark.parametrize(
    "anchor",
    [
        (
            "      - name: Materialize exact PR 454 target, PR 453 "
            "architecture, and PR 440 inherited reciprocal evaluator\n"
        ),
        "      - name: Verify bounded successor evidence\n",
    ],
)
def test_predecessor_workflow_executes_exact_frozen_merge(anchor: str) -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_frozen_predecessor_workflow(frozen)
    assert transformed == (
        ROOT / verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH
    ).read_text()
    for token in (
        "Materialize exact PR 455 evidence and reviewed head",
        'git checkout --detach --quiet "$frozen"',
        "trap 'git checkout --detach --quiet \"$current_sha\"' EXIT",
        verifier.PREDECESSOR["reviewed_head"],
        verifier.PREDECESSOR["merge_commit"],
        verifier.PREDECESSOR["merge_tree"],
    ):
        assert token in transformed
    sentinel = "\n# unrelated-frozen-workflow-sentinel\n"
    assert verifier.expected_frozen_predecessor_workflow(
        frozen + sentinel
    ).endswith(sentinel)
    with pytest.raises(ValueError, match="transformation point drift"):
        verifier.expected_frozen_predecessor_workflow(
            frozen.replace(anchor, "      - name: drifted predecessor step\n", 1)
        )


def test_manifest_and_profile_mutations_are_noncanonical() -> None:
    manifest_raw = (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    manifest = json.loads(manifest_raw)
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != manifest_raw
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile(manifest_raw)
