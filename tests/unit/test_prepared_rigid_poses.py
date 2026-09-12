"""Fresh synthetic pose batches; reference arithmetic remains separately written."""

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import pytest

from betelgeuze_engine.product import prepared_rigid_poses as poses
from tools.product import score_prepared_cross_interactions as consumer
from tests.unit.test_score_prepared_cross_interactions import (
    _prepared,
    _case,
    _assert_scalar_pair,
)


def _pose(name, shift=0.0):
    return {
        "pose_id": name,
        "rotation_matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        "translation_angstrom": [shift, 0.0, 0.0],
    }


def _request(tmp_path, reuse="request"):
    case = _case(_prepared(tmp_path / "source"))
    return {
        "schema_version": poses.SCHEMA,
        "prepared_input": case["prepared_input"],
        "evaluation": case["evaluation"],
        "execution": {
            "projection_partition": "source_order_v1",
            "preparation_reuse": reuse,
        },
        "poses": [_pose("reference"), _pose("shift", 0.5)],
    }


def test_real_consumer_reuse_and_fresh_parsing_have_exact_results_and_scalar_controls(
    tmp_path,
):
    request = _request(tmp_path)
    reused = consumer.evaluate_request(request)
    request["execution"]["preparation_reuse"] = "none"
    fresh = consumer.evaluate_request(request)
    assert (
        reused["denominator"]
        == fresh["denominator"]
        == {"requested": 2, "evaluated": 2, "failed": 0, "skipped": 0}
    )
    assert reused["preparation_observation"]["successful_loads"] == 1
    assert reused["preparation_observation"]["reuse_hits"] == 1
    assert fresh["preparation_observation"]["successful_loads"] == 2
    for a, b in zip(reused["rows"], fresh["rows"]):
        for key in (
            "sources",
            "quantities",
            "pair_accounting",
            "model",
            "pocket",
            "source_declarations",
        ):
            assert a["result"][key] == b["result"][key]
    _assert_scalar_pair(reused["rows"][0]["result"])
    shifted = reused["rows"][1]["result"]
    distance = 4.5
    a6 = (3.0 / distance) ** 6
    expected = 4 * 0.2 * (a6 * a6 - a6) + 332.063713299 * 0.2 * -0.3 * math.exp(
        -0.1 * distance
    ) / (4 * distance)
    assert shifted["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(
        expected, abs=1e-12
    )
    assert reused["rows"][1]["evaluated_ligand_coordinates_angstrom"] == [
        [4.5, 0.0, 0.0]
    ]


@pytest.mark.parametrize(
    "patch",
    [
        {"rotation_matrix": [[-1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        {"rotation_matrix": [[2.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        {"rotation_matrix": [[1.0, 0.1, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        {"rotation_matrix": [[math.nan, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]},
        {"translation_angstrom": [True, 0.0, 0.0]},
        {"translation_angstrom": [0.0, 0.0]},
        {"pose_id": ""},
    ],
)
def test_invalid_transforms_are_failed_rows_not_low_scores(tmp_path, patch):
    request = _request(tmp_path)
    request["poses"][0].update(patch)
    result = consumer.evaluate_request(request)
    assert result["denominator"] == {
        "requested": 2,
        "evaluated": 1,
        "failed": 1,
        "skipped": 0,
    }
    assert "result" not in result["rows"][0]
    assert result["rows"][0]["reason"]
    json.dumps(result, allow_nan=False)


def test_duplicate_ids_fail_both_and_missing_execution_does_not_pollute_json(tmp_path):
    request = _request(tmp_path)
    request["poses"][1]["pose_id"] = "reference"
    result = consumer.evaluate_request(request)
    assert result["denominator"]["failed"] == 2
    assert all("duplicate pose_id" in r["reason"] for r in result["rows"])
    request = _request(tmp_path / "other")
    request["execution"]["preparation_reuse"] = math.nan
    result = consumer.evaluate_request(request)
    assert result["denominator"]["failed"] == 2 and result["execution"] is None
    json.dumps(result, allow_nan=False)


def test_pocket_exit_and_overlap_retain_requested_coordinates(tmp_path):
    request = _request(tmp_path)
    request["poses"] = [_pose("outside", 100), _pose("overlap", -4)]
    result = consumer.evaluate_request(request)
    assert result["denominator"] == {
        "requested": 2,
        "evaluated": 0,
        "failed": 2,
        "skipped": 0,
    }
    assert result["rows"][0]["evaluated_ligand_coordinates_angstrom"] == [
        [104.0, 0.0, 0.0]
    ]
    assert result["rows"][1]["evaluated_ligand_coordinates_angstrom"] == [
        [0.0, 0.0, 0.0]
    ]
    assert result["preparation"]["source_receptor_coordinates_angstrom"] == [
        [0.0, 0.0, 0.0]
    ]


def test_source_change_after_calculation_invalidates_result_and_reuse(
    tmp_path, monkeypatch
):
    request = _request(tmp_path)
    original = poses.evaluate_prepared_cross_interaction
    path = Path(request["prepared_input"]["protein_pdb"]["path"])

    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        path.write_text(path.read_text() + "REMARK changed\n")
        return result

    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", changed)
    result = consumer.evaluate_request(request)
    assert result["denominator"]["failed"] == 2
    assert result["rows"][0]["evaluation_completed"]
    assert all("source SHA-256 mismatch" in r["reason"] for r in result["rows"])
    assert all("result" not in r for r in result["rows"])


def test_parameter_mutation_cannot_contaminate_reused_preparation(
    tmp_path, monkeypatch
):
    request = _request(tmp_path)
    request["poses"][1] = _pose("second")
    original = poses.evaluate_prepared_cross_interaction

    def mutate(receptor, ligand, rp, lp, **kwargs):
        result = original(receptor, ligand, rp, lp, **kwargs)
        rp[0]["epsilon_kcal_per_mol"] = 99.0
        return result

    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", mutate)
    result = consumer.evaluate_request(request)
    assert result["denominator"]["evaluated"] == 2
    assert (
        result["rows"][0]["result"]["quantities"]
        == result["rows"][1]["result"]["quantities"]
    )


def test_reused_canonical_state_mutation_is_not_resealed_by_transform(
    tmp_path, monkeypatch
):
    request = _request(tmp_path)
    original = poses.evaluate_prepared_cross_interaction

    def mutate(receptor, ligand, rp, lp, **kwargs):
        result = original(receptor, ligand, rp, lp, **kwargs)
        receptor.coordinates.add_(1.0)
        return result

    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", mutate)
    result = consumer.evaluate_request(request)
    assert result["denominator"]["failed"] == 2
    assert all("result" not in r for r in result["rows"])


def test_source_failure_keeps_all_pose_rows(tmp_path):
    request = _request(tmp_path)
    request["prepared_input"]["protein_pdb"]["sha256"] = "0" * 64
    result = consumer.evaluate_request(request)
    assert result["denominator"] == {
        "requested": 2,
        "evaluated": 0,
        "failed": 2,
        "skipped": 0,
    }
    assert result["preparation"] is None


def test_explicit_zero_parameters_remain_evaluated_zero_and_unknown_terms_null(
    tmp_path,
):
    request = _request(tmp_path)
    source = request["prepared_input"]
    refs = [
        source["protein_chains"][0]["molecule_itp"],
        source["ligand_itp"],
        source["protein_atomtypes"],
        source["ligand_atomtypes"],
    ]
    for ref in refs:
        path = Path(ref["path"])
        text = (
            path.read_text()
            .replace("0.2 12.011", "0.0 12.011")
            .replace("-0.3 12.011", "0.0 12.011")
            .replace("0.836800", "0.000000")
        )
        path.write_text(text)
        ref["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = consumer.evaluate_request(request)
    assert result["denominator"]["evaluated"] == 2
    for row in result["rows"]:
        q = row["result"]["quantities"]
        assert q["cross_total_kcal_per_mol"] == 0.0
        assert q["ligand_cross_forces_kcal_per_mol_angstrom"] == [[0.0, 0.0, 0.0]]
        assert q["affinity"] is None and q["residual"] is None


def test_proper_rotation_moves_supplied_bonded_atoms_and_matches_scalar_energy(
    tmp_path,
):
    request = _request(tmp_path)
    source = request["prepared_input"]
    sdf = Path(source["ligand_sdf"]["path"])
    lines = sdf.read_text().splitlines()
    lines[3] = "  2  1  0  0  0  0            999 V2000"
    atom = lines[4]
    second = f"{4.0:10.4f}{1.5:10.4f}{0.0:10.4f}" + atom[30:]
    lines[5:5] = [second, "  1  2  1  0  0  0  0"]
    sdf.write_text("\n".join(lines) + "\n")
    gro = Path(source["ligand_gro"]["path"])
    lines = gro.read_text().splitlines()
    lines[1] = "2"
    lines.insert(3, f"{1:5d}{'LIG':<5s}{'C2':>5s}{2:5d}{0.4:8.3f}{0.15:8.3f}{0.0:8.3f}")
    gro.write_text("\n".join(lines) + "\n")
    itp = Path(source["ligand_itp"]["path"])
    itp.write_text(itp.read_text() + "2 C 1 LIG C2 1 -0.3 12.011\n[ bonds ]\n1 2 1\n")
    for name in ("ligand_sdf", "ligand_gro", "ligand_itp"):
        source[name]["sha256"] = hashlib.sha256(
            Path(source[name]["path"]).read_bytes()
        ).hexdigest()
    request["poses"] = [
        {
            "pose_id": "rotated",
            "rotation_matrix": [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
            "translation_angstrom": [0.0, 0.0, 0.0],
        }
    ]
    result = consumer.evaluate_request(request)
    assert result["denominator"]["evaluated"] == 1, result["rows"]
    row = result["rows"][0]
    assert row["evaluated_ligand_coordinates_angstrom"] == [
        [4.75, 0.75, 0.0],
        [3.25, 0.75, 0.0],
    ]
    energies = []
    for x, y, z in row["evaluated_ligand_coordinates_angstrom"]:
        distance = math.sqrt(x * x + y * y + z * z)
        a6 = (3.0 / distance) ** 6
        energies.append(
            4 * 0.2 * (a6 * a6 - a6)
            + 332.063713299 * 0.2 * -0.3 * math.exp(-0.1 * distance) / (4 * distance)
        )
    assert row["result"]["quantities"]["cross_total_kcal_per_mol"] == pytest.approx(
        math.fsum(energies), abs=1e-12
    )


def test_module_cli_returns_partial_failure_and_no_external_solver(tmp_path):
    request = _request(tmp_path)
    request["poses"].append(_pose("outside", 100))
    input_path = tmp_path / "request.json"
    output = tmp_path / "output.json"
    input_path.write_text(json.dumps(request))
    before = hashlib.sha256(input_path.read_bytes()).hexdigest()
    root = Path(__file__).resolve().parents[2]
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(root),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.product.score_prepared_cross_interactions",
            "--request",
            str(input_path),
            "--output",
            str(output),
            "--output-format",
            "compact",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 2, result.stderr
    decoded = json.loads(output.read_text())
    assert decoded["denominator"] == {
        "requested": 3,
        "evaluated": 2,
        "failed": 1,
        "skipped": 0,
    }
    assert not decoded["external_solver_called"]
    assert hashlib.sha256(input_path.read_bytes()).hexdigest() == before


def test_geometry_preserves_source_zero_and_observes_transformed_overlap(tmp_path):
    request = _request(tmp_path)
    request["poses"][1] = _pose("overlap", -4)
    report = consumer.evaluate_request(request)
    original = report["preparation"]["source_geometry_observation"]
    assert original["status"] == "observed"
    assert original["coordinate_origin"] == "supplied_preparation_unchanged"
    assert original["groups"]["cross"]["pair_count_within_radius"] == 0
    first, second = report["rows"]
    assert (
        first["pose_geometry_observation"]["groups"]["cross"][
            "pair_count_within_radius"
        ]
        == 0
    )
    observed = second["pose_geometry_observation"]
    assert observed["groups"]["cross"]["pair_count_within_radius"] == 1
    assert (
        observed["coordinate_origin"]
        == "computed_rigid_transform_of_supplied_preparation"
    )
    assert observed["groups"]["cross"]["closest_pairs"][0]["distance_angstrom"] == 0
    assert (
        not observed["physical_validity_assessed"]
        and not observed["affects_score_or_admission"]
    )
    assert second["status"] == "failed" and "result" not in second
    assert first["status"] == "evaluated"
    _assert_scalar_pair(first["result"])


def test_geometry_short_internal_source_pair_remains_visible_in_real_consumer(
    tmp_path, monkeypatch
):
    from tests.unit.test_v2_prepared_cross_interaction import _system, _parameters

    request = _request(tmp_path)
    receptor = _system([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]], [0.2, 0.2])
    ligand = _system([[4.0, 0.0, 0.0]], [-0.3])
    provenance = {
        "sources": {},
        "original_topologies": {
            name: {"sections": {"bonds": []}}
            for name in ("protein_chain_0", "protein_chain_1", "ligand_itp")
        },
        "receptor_source_bond_adjacency": [],
        "ligand_source_bond_adjacency": [],
    }
    monkeypatch.setattr(
        poses,
        "load_prepared_gromacs_components",
        lambda _: (
            receptor,
            ligand,
            _parameters(receptor),
            _parameters(ligand),
            provenance,
        ),
    )
    result = consumer.evaluate_request(request)
    assert result["denominator"]["evaluated"] == 2
    observations = [result["preparation"]["source_geometry_observation"]] + [
        r["pose_geometry_observation"] for r in result["rows"]
    ]
    for observation in observations:
        group = observation["groups"]["receptor"]
        assert (
            group["pair_count_within_radius"]
            == group["non_direct_bond_pair_count"]
            == 1
        )
        assert group["closest_non_direct_bond_pairs"][0]["distance_angstrom"] == 0.5
        assert not observation["physical_validity_assessed"]


def test_geometry_unavailable_diagnostic_does_not_become_zero_or_skip_physics(
    tmp_path, monkeypatch
):
    from betelgeuze_engine.product import prepared_source_geometry as geometry

    def unavailable(*args):
        raise RuntimeError("synthetic observer unavailable")

    monkeypatch.setattr(geometry, "observe_prepared_source_geometry", unavailable)
    result = consumer.evaluate_request(_request(tmp_path))
    assert result["denominator"]["evaluated"] == 2
    observations = [result["preparation"]["source_geometry_observation"]] + [
        r["pose_geometry_observation"] for r in result["rows"]
    ]
    for observation in observations:
        assert observation["status"] == "unavailable" and observation["groups"] is None
        assert observation["error_type"] == "RuntimeError"
        assert "synthetic observer unavailable" in observation["detail"]
        assert not observation["affects_score_or_admission"]
    _assert_scalar_pair(result["rows"][0]["result"])


def test_geometry_missing_pose_is_explicitly_unavailable(tmp_path):
    request = _request(tmp_path)
    request["poses"][0]["translation_angstrom"] = [True, 0, 0]
    report = consumer.evaluate_request(request)
    missing = report["rows"][0]["pose_geometry_observation"]
    assert missing["status"] == "unavailable" and missing["groups"] is None
    assert missing["reason"] == "pose_not_constructed"
    assert report["rows"][1]["pose_geometry_observation"]["status"] == "observed"


def test_geometry_observer_mutation_cannot_reseal_source_or_reach_physics(
    tmp_path, monkeypatch
):
    from betelgeuze_engine.product import prepared_source_geometry as geometry

    original = geometry.observe_prepared_source_geometry
    calls = []

    def changed(receptor, ligand, provenance):
        observed = original(receptor, ligand, provenance)
        receptor.coordinates.add_(1.0)
        return observed

    def unexpected(*args, **kwargs):
        calls.append(True)
        raise AssertionError("physics reached after source mutation")

    monkeypatch.setattr(geometry, "observe_prepared_source_geometry", changed)
    monkeypatch.setattr(poses, "evaluate_prepared_cross_interaction", unexpected)
    result = consumer.evaluate_request(_request(tmp_path))
    assert result["denominator"]["failed"] == 2
    assert calls == []
    assert all("result" not in row for row in result["rows"])
