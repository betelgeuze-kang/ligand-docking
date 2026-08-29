import json
from pathlib import Path

import pytest

from tools import verify_engine_v2_native_particle_mesh_ewald_composite_dynamics_direct_parent_force_scratch_v1 as verifier

ROOT = Path(__file__).resolve().parents[2]


def test_exact_profile_manifest_and_contracts() -> None:
    result = verifier.verify(ROOT)
    assert result["source_count"] == 252
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    implementation = profile["implementation"]
    assert implementation["successful_stateful_forceful_direct_parent_aos_storage_reused"]
    assert implementation["steady_state_direct_parent_force_storage_reused"]
    assert implementation["reciprocal_parent_force_storage_reused"] is False
    assert not any(profile["authority"].values())
    for key in ("allocation_free_claimed", "timing_claimed", "performance_claimed", "acceleration_claimed", "cross_lane_bit_parity_claimed", "unconditional_failure_storage_retention_claimed", "universal_failure_storage_retention_claimed", "all_failure_path_storage_retention_claimed"):
        assert implementation[key] is False


def test_exact_anchors_and_delta() -> None:
    assert verifier.ARCHITECTURE_PREDECESSOR["pull_request"] == 453
    assert verifier.PREDECESSOR["pull_request"] == 452
    assert verifier.INHERITED_PREDECESSOR["pull_request"] == 435
    assert len(verifier.EXPECTED_DELTA_PATHS) == 19
    assert verifier.current_delta_paths() == verifier.EXPECTED_DELTA_PATHS


def test_workflow_static_trigger_closure_and_bodies() -> None:
    assert len(verifier.REQUIRED_TRIGGER_PATHS) == 68
    assert len(set(verifier.REQUIRED_TRIGGER_PATHS)) == 68
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    verifier.require_workflow_contract(workflow)
    assert workflow == verifier.expected_workflow_document()
    assert workflow.count("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0") == 4


@pytest.mark.parametrize("job", ["immutable-evidence", "native-linux", "rust-boundaries", "macos-export-boundary"])
def test_workflow_job_body_mutation_fails_closed(tmp_path: Path, job: str) -> None:
    workflow = (ROOT / verifier.WORKFLOW_RELATIVE_PATH).read_text()
    body = verifier.job_body(workflow, job)
    mutated = workflow.replace(body, body + "      # sentinel drift\n", 1)
    target = tmp_path / verifier.WORKFLOW_RELATIVE_PATH
    target.parent.mkdir(parents=True)
    target.write_text(mutated)
    with pytest.raises(ValueError, match="workflow exact job body drift"):
        verifier.require_workflow_contract(mutated)


@pytest.mark.parametrize("relative,transform,anchor", [
    ("native/src/composite/particle_mesh_ewald_composite.cpp", verifier.expected_particle_mesh_ewald_composite_source, "    ewald::Evaluation direct_evaluation;\n"),
    ("native/src/composite/particle_mesh_ewald_composite_dynamics.cpp", verifier.expected_composite_dynamics_source, "bool forcefield_storage_overlaps(\n"),
    ("native/src/composite/particle_mesh_ewald_composite_dynamics.hpp", verifier.expected_composite_dynamics_header, '#include "../ewald/model.hpp"\n'),
    ("native/src/composite/particle_mesh_ewald_composite_evaluator.hpp", verifier.expected_composite_evaluator_header, '#include "../cpu/evaluator.hpp"\n'),
    ("rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite.cpp", verifier.expected_particle_mesh_ewald_composite_source, "    ewald::Evaluation direct_evaluation;\n"),
    ("rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.cpp", verifier.expected_composite_dynamics_source, "bool forcefield_storage_overlaps(\n"),
    ("rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_dynamics.hpp", verifier.expected_composite_dynamics_header, '#include "../ewald/model.hpp"\n'),
    ("rust/betelgeuze-sys/vendor/native/src/composite/particle_mesh_ewald_composite_evaluator.hpp", verifier.expected_composite_evaluator_header, '#include "../cpu/evaluator.hpp"\n'),
])
def test_frozen_production_transforms_and_sentinels(relative, transform, anchor) -> None:
    frozen = verifier.git("show", f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:{relative}").stdout.decode()
    assert transform(frozen) == (ROOT / relative).read_text()
    sentinel = "\n// unrelated-frozen-input-sentinel\n"
    assert transform(frozen + sentinel).endswith(sentinel)
    with pytest.raises(ValueError, match="transformation point drift"):
        transform(frozen.replace(anchor, "drifted anchor", 1))


def test_production_hashes_and_vendor_identity() -> None:
    verifier.require_direct_parent_force_scratch_contract(ROOT)


def test_predecessor_freezes() -> None:
    verifier.require_predecessor_workflow_freeze(ROOT)
    verifier.require_predecessor_unit_freeze(ROOT)


@pytest.mark.parametrize(
    "anchor",
    [
        "      - name: Materialize exact PR 452 architecture, PR 451 target, and PR 435 inherited Ewald evaluator\n",
        "      - name: Verify bounded successor evidence\n",
    ],
)
def test_predecessor_workflow_executes_exact_frozen_merge(
    anchor: str,
) -> None:
    frozen = verifier.git(
        "show",
        f"{verifier.ARCHITECTURE_PREDECESSOR['merge_commit']}:"
        f"{verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH.as_posix()}",
    ).stdout.decode()
    transformed = verifier.expected_frozen_predecessor_workflow(frozen)
    assert transformed == (
        ROOT / verifier.PREDECESSOR_WORKFLOW_RELATIVE_PATH
    ).read_text()
    for token in (
        "Materialize exact PR 453 evidence and reviewed head",
        'git checkout --detach --quiet "$frozen"',
        "trap 'git checkout --detach --quiet \"$current_sha\"' EXIT",
        verifier.ARCHITECTURE_PREDECESSOR["reviewed_head"],
        verifier.ARCHITECTURE_PREDECESSOR["merge_commit"],
        verifier.ARCHITECTURE_PREDECESSOR["merge_tree"],
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
    manifest = json.loads((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
    manifest["files"][0]["sha256"] = "0" * 64
    assert verifier.canonical_bytes(manifest) != (ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes()
    profile = json.loads((ROOT / verifier.PROFILE_RELATIVE_PATH).read_bytes())
    profile["authority"]["product_authority"] = True
    assert profile != verifier.build_profile((ROOT / verifier.SOURCE_MANIFEST_RELATIVE_PATH).read_bytes())
