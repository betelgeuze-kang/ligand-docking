from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
Chem = pytest.importorskip("rdkit.Chem")
from rdkit.Chem import Lipinski, rdMolDescriptors  # noqa: E402

from tools import run_engine_v2_public_redocking_300 as runner  # noqa: E402
from tools.redocking_development_p1 import (  # noqa: E402
    DevelopmentObservation,
    DevelopmentObservationError,
)


@pytest.fixture
def serializer_modules(monkeypatch):
    # Dependency-injected unit test, not a frozen-version qualification. The
    # unchanged runtime version guard is exercised by the hosted frozen lane.
    monkeypatch.setattr(
        runner, "_load_rdkit_modules", lambda: (Chem, Lipinski, rdMolDescriptors)
    )


def _molecule(source: Path):
    molecule = Chem.MolFromSmiles("CCO")
    conformer = Chem.Conformer(3)
    for i, xyz in enumerate(((0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (2.8, 0.5, 0.0))):
        conformer.SetAtomPosition(i, xyz)
    molecule.AddConformer(conformer)
    source.write_text(Chem.MolToMolBlock(molecule), encoding="ascii")
    return molecule


def _fake_evaluator(monkeypatch):
    calls = []

    class Column:
        def __init__(self, values):
            self.values = values

        def tolist(self):
            return self.values

    class Report:
        columns = {"rmsd", *runner.CHEMICAL_COLUMNS, *runner.GEOMETRIC_COLUMNS}

        def __init__(self, molecules):
            self.molecules = molecules

        def __len__(self):
            return len(self.molecules)

        def __getitem__(self, column):
            return Column(
                [
                    float(m.GetProp("_Name").rsplit("_", 1)[-1]) / 100
                    if column == "rmsd"
                    else True
                    for m in self.molecules
                ]
            )

    class Evaluator:
        def __init__(self, *, config, top_n):
            assert config == "redock"
            self.top_n = top_n

        def bust(self, predicted, native, receptor, *, full_report):
            assert full_report and len(predicted) == self.top_n
            calls.append((len(predicted), native, receptor))
            return Report(predicted)

    monkeypatch.setattr(runner, "_load_posebusters", lambda: Evaluator)
    return calls


def test_actual_ranked_rdkit_bytes_produce_five_top5_cache_hits(
    tmp_path, monkeypatch, serializer_modules
):
    source = tmp_path / "source.sdf"
    molecule = _molecule(source)
    base = torch.tensor(molecule.GetConformer().GetPositions(), dtype=torch.float64)
    coordinates = tuple(base + i / 100 for i in range(64))
    records = runner._serialize_pose_records(source, coordinates, case_id="fixture")
    payload, hashes = runner._write_engine_v2_poses(
        tmp_path / "top5.sdf", source, coordinates[:5], case_id="fixture"
    )
    assert payload == b"".join(records[:5])
    assert hashes == tuple(hashlib.sha256(record).hexdigest() for record in records[:5])
    calls = _fake_evaluator(monkeypatch)
    events = []
    observer = DevelopmentObservation(
        "fixture", event_sink=events.append, evaluator_identity="a" * 64
    )
    inputs = {
        "native_payload": source.read_bytes(),
        "receptor_payload": Chem.MolToPDBBlock(molecule).encode("ascii"),
    }
    candidates = runner._posebusters_outcomes(
        b"".join(records),
        expected_pose_count=64,
        development_observation=observer,
        **inputs,
    )
    top5 = runner._posebusters_outcomes(
        payload, development_observation=observer, **inputs
    )
    fresh = runner._posebusters_outcomes(payload, **inputs)
    assert top5 == fresh == tuple(column[:5] for column in candidates)
    assert [n for n, _, _ in calls] == [64, 5]
    assert observer.summary()["evaluation_cache"]["reused_records"] == 5
    assert {e["stage"] for e in events} >= {
        "evaluation_input_decode",
        "evaluation_posebusters",
        "evaluation_report_validation",
    }


def test_prepared_reference_reuse_keeps_fresh_rdkit_objects(
    tmp_path, monkeypatch, serializer_modules
):
    source = tmp_path / "source.sdf"
    molecule = _molecule(source)
    coordinates = torch.tensor(
        molecule.GetConformer().GetPositions(), dtype=torch.float64
    )
    records = runner._serialize_pose_records(
        source, (coordinates,) * 5, case_id="fixture"
    )
    calls = _fake_evaluator(monkeypatch)
    observer = DevelopmentObservation(
        "fixture",
        event_sink=lambda e: None,
        evaluator_identity="a" * 64,
        reuse_evaluations=False,
    )
    inputs = {
        "native_payload": source.read_bytes(),
        "receptor_payload": Chem.MolToPDBBlock(molecule).encode("ascii"),
    }
    first = runner._posebusters_outcomes(
        b"".join(records), development_observation=observer, **inputs
    )
    calls[0][1].SetProp("evaluator_mutation", "must not escape")
    calls[0][2].SetProp("evaluator_mutation", "must not escape")
    second = runner._posebusters_outcomes(
        b"".join(records), development_observation=observer, **inputs
    )
    assert first == second
    assert calls[0][1] is not calls[1][1] and calls[0][2] is not calls[1][2]
    assert not calls[1][1].HasProp("evaluator_mutation") and not calls[1][2].HasProp(
        "evaluator_mutation"
    )
    assert observer.summary()["prepared_inputs"] == {"cache_hits": 1, "cache_misses": 1}


@pytest.mark.parametrize("bad", [(1,), (1, -1), (True, 2), [1, 2]])
def test_external_stdio_rejects_invalid_fd_contract_before_launch(bad):
    with pytest.raises(runner.PublicRedockingRunnerError, match="stdio"):
        runner._external_result(
            "fixture",
            "vina",
            {},
            binary=None,
            input_sha256s={},
            output=Path("unused"),
            seed=1,
            timeout_seconds=1,
            development_stdio=bad,
        )


@pytest.mark.parametrize("stdio", [None, (1, 2)])
def test_external_stdio_opt_in_preserves_default_and_routes_capture(
    tmp_path, monkeypatch, stdio
):
    case_id = runner.FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True)
    paths["native"].write_bytes(b"native fixture")
    paths["receptor"].write_bytes(b"receptor fixture")
    output = tmp_path / "poses.sdf"
    binary = tmp_path / "gnina"
    binary.write_bytes(b"fixture binary")
    binary.chmod(0o500)
    captured = []

    def launch(*args, **kwargs):
        captured.append(kwargs)
        output.write_bytes(b"fixture\n$$$$\n" * 5)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", launch)
    monkeypatch.setattr(
        runner,
        "_posebusters_outcomes",
        lambda *a, **k: (
            (1.0,) * 5,
            (True,) * 5,
            (True,) * 5,
            ((),) * 5,
        ),
    )
    with runner.PinnedExternalBinary(binary, runner._sha256_path(binary)) as pinned:
        row, _ = runner._external_result(
            case_id,
            "vina",
            paths,
            binary=pinned,
            input_sha256s={
                role: "a" * 64 for role in ("receptor", "reference", "native", "seed")
            },
            output=output,
            seed=11,
            timeout_seconds=300,
            development_stdio=stdio,
        )
    assert row.status == "success" and len(row.pose_artifact_sha256s) == 5
    expected = (runner.subprocess.DEVNULL,) * 2 if stdio is None else stdio
    assert (captured[0]["stdout"], captured[0]["stderr"]) == expected


def test_latched_observation_failure_is_not_published_as_preparation_failure(
    tmp_path, monkeypatch
):
    case_id = runner.FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]

    def broken_sink(event):
        raise OSError("journal unavailable")

    observer = DevelopmentObservation(
        case_id, event_sink=broken_sink, evaluator_identity="a" * 64
    )

    def failure(*args, **kwargs):
        try:
            observer.core_event("fixture", "start", {})
        except DevelopmentObservationError:
            pass  # Simulate a component's existing broad candidate exception handler.
        raise runner.EngineV2PreparationFailure("input_parse_unsupported", "fixture")

    monkeypatch.setattr(runner, "_engine_v2_pose_coordinates", failure)
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    with pytest.raises(DevelopmentObservationError, match="sink"):
        runner._engine_v2_result(
            case_id,
            paths,
            input_sha256s={
                role: "a" * 64 for role in ("receptor", "reference", "native", "seed")
            },
            output=tmp_path / "poses.sdf",
            seed=11,
            development_observation=observer,
        )


def test_observation_rejects_other_numerical_variants_before_inputs():
    observer = DevelopmentObservation(
        "fixture", event_sink=lambda e: None, evaluator_identity="a" * 64
    )
    with pytest.raises(runner.PublicRedockingRunnerError, match="unchanged V7"):
        runner._engine_v2_pose_coordinates(
            "fixture",
            {},
            seed=1,
            development_observation=observer,
            development_v8_clearance_variant=True,
        )


def test_evaluation_source_binding_includes_observation_for_both_profiles(
    tmp_path, monkeypatch
):
    sources = {
        "betelgeuze_engine_v2/benchmark/public_redocking_benchmark.py": b"benchmark fixture",
        "tools/run_engine_v2_public_redocking_300.py": b"runner fixture",
        "tools/redocking_development_p1.py": b"observation version A",
    }
    for relative, payload in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    monkeypatch.setattr(
        runner,
        "__file__",
        str(tmp_path / "tools/run_engine_v2_public_redocking_300.py"),
    )
    monkeypatch.setattr(
        runner, "_evaluator_distribution_payload_sha256s", lambda: {"fixture": "a" * 64}
    )
    legacy = runner._evaluation_pipeline_sha256(
        tmp_path, evaluator_versions={"fixture": "1"}
    )
    DevelopmentObservation(
        "fixture", event_sink=lambda e: None, evaluator_identity=legacy
    )
    assert (
        runner._evaluation_pipeline_sha256(
            tmp_path, evaluator_versions={"fixture": "1"}
        )
        == legacy
    )
    observation_path = tmp_path / "tools/redocking_development_p1.py"
    observation_path.write_bytes(b"observation version B")
    assert (
        runner._evaluation_pipeline_sha256(
            tmp_path, evaluator_versions={"fixture": "1"}
        )
        != legacy
    )
    observation_path.unlink()
    with pytest.raises(OSError):
        runner._evaluation_pipeline_sha256(
            tmp_path, evaluator_versions={"fixture": "1"}
        )


def test_synthetic_full_runner_retains_64_lineages_and_reuses_selected_five(
    tmp_path, monkeypatch, serializer_modules
):
    case_id = runner.FROZEN_PUBLIC_REDOCKING_CASE_IDS[0]
    paths = runner._case_paths(tmp_path / "inputs", case_id)
    paths["directory"].mkdir(parents=True)
    molecule = Chem.AddHs(_molecule(paths["native"]), addCoords=True)
    payload = (Chem.MolToMolBlock(molecule) + "\n$$$$\n").encode("ascii")
    for role in ("native", "reference", "seed"):
        paths[role].write_bytes(payload)
    receptor = Chem.MolFromSmiles("C")
    conformer = Chem.Conformer(1)
    conformer.SetAtomPosition(0, (6.0, 0.0, 0.0))
    receptor.AddConformer(conformer)
    paths["receptor"].write_bytes(Chem.MolToPDBBlock(receptor).encode("ascii"))
    calls, events = _fake_evaluator(monkeypatch), []
    observer = DevelopmentObservation(
        case_id, event_sink=events.append, evaluator_identity="a" * 64
    )
    row = runner._engine_v2_result(
        case_id,
        paths,
        input_sha256s=runner._input_sha256s(paths),
        output=tmp_path / "poses.sdf",
        seed=runner.frozen_public_redocking_case_seed(case_id),
        development_observation=observer,
    )
    assert row.status == "success"
    assert len(row.pose_artifact_sha256s) == 5
    assert len(row.engine_v2_diagnostics.candidates) == 64
    assert [count for count, _, _ in calls] == [64]
    assert observer.summary()["evaluation_cache"]["reused_records"] == 5
    assert observer.summary()["incomplete_stages"] == []
    for stage in (
        "proposal_generated",
        "post_v6",
        "post_v7_optimization",
        "refinement_selected",
    ):
        captured = [
            e["details"]
            for e in events
            if e["stage"] == stage and e["phase"] == "snapshot"
        ]
        assert len(captured) == 64
        assert sorted(c["proposal_index"] for c in captured) == list(range(64))
    final = [e["details"] for e in events if e["stage"] == "final_ranked"]
    assert [e["rank_1based"] for e in final] == list(range(1, 6))
    assert (
        tuple(e["evaluated_pose_record_sha256"] for e in final)
        == row.pose_artifact_sha256s
    )
    scored = next(e["details"] for e in events if e["stage"] == "scored_candidates")
    assert len(scored["candidates"]) == scored["candidate_count"] == 64


def test_frozen_posebusters_top5_reuse_matches_fresh_evaluation(tmp_path):
    # Full evaluator integration is required in the pinned Linux workflow;
    # other development environments report this qualification as unavailable.
    pytest.importorskip("posebusters")
    from rdkit import rdBase

    if rdBase.rdkitVersion != runner.RDKit_VERSION:
        pytest.skip("requires frozen RDKit 2022.09.5 evaluator profile")
    source = tmp_path / "source.sdf"
    molecule = _molecule(source)
    coordinates = torch.tensor(
        molecule.GetConformer().GetPositions(), dtype=torch.float64
    )
    records = runner._serialize_pose_records(
        source, tuple(coordinates + i / 100 for i in range(6)), case_id="fixture"
    )
    observer = DevelopmentObservation(
        "fixture", event_sink=lambda e: None, evaluator_identity="a" * 64
    )
    inputs = {
        "native_payload": source.read_bytes(),
        "receptor_payload": Chem.MolToPDBBlock(molecule).encode("ascii"),
    }
    runner._posebusters_outcomes(
        b"".join(records),
        expected_pose_count=6,
        development_observation=observer,
        **inputs,
    )
    cached = runner._posebusters_outcomes(
        b"".join(records[:5]), development_observation=observer, **inputs
    )
    fresh = runner._posebusters_outcomes(b"".join(records[:5]), **inputs)
    assert cached == fresh
    assert observer.summary()["evaluation_cache"]["reused_records"] == 5
