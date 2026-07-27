from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest


torch = pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    BenchmarkCase,
    BenchmarkCaseResult,
    BenchmarkContractError,
    BenchmarkManifest,
    BenchmarkReport,
    BenchmarkRunContext,
    run_benchmark_manifest,
)
from betelgeuze_engine_v2.contracts import QuantityDescriptor  # noqa: E402
from betelgeuze_engine_v2.docking import (  # noqa: E402
    DockingBudget,
    DockingProposalError,
    TorsionSearchSpace,
    generate_bounded_docking_proposals,
    run_bounded_docking_search,
)
from betelgeuze_engine_v2.geometry import RadiusGraphConfig, build_compact_radius_graph  # noqa: E402
from betelgeuze_engine_v2.io import (  # noqa: E402
    PDBParseError,
    PDBParserLimits,
    SDFParseError,
    parse_pdb,
    parse_sdf_v2000,
)
from betelgeuze_engine_v2.physics import (  # noqa: E402
    EnergyTermResult,
    PhysicsTermRegistry,
    PhysicsTermRegistryError,
    sum_validated_physics_terms,
)


def _pdb_atom(
    serial: int,
    name: str,
    element: str,
    x: float,
    y: float,
    z: float,
    *,
    record: str = "HETATM",
    altloc: str = "",
) -> str:
    return (
        f"{record:<6}{serial:5d} {name:<4}{altloc:1}{'LIG':>3} {'L':1}{1:4d}{'':1}   "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{10.0:6.2f}          {element:>2}{'':>2}"
    )


def _valid_pdb() -> str:
    return "\n".join(
        [
            f"CRYST1{10.0:9.3f}{10.0:9.3f}{10.0:9.3f}{90.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1",
            _pdb_atom(1, "C1", "C", 0.2, 0.0, 0.0),
            _pdb_atom(2, "O1", "O", 1.4, 0.0, 0.0),
            "CONECT    1    2",
            "END",
        ]
    ) + "\n"


def _sdf_atom(x: float, y: float, z: float, element: str, charge_code: int = 0) -> str:
    return (
        f"{x:10.4f}{y:10.4f}{z:10.4f} {element:<3}{0:2d}{charge_code:3d}"
        "  0  0  0  0  0  0  0  0  0  0  0  0"
    )


def _valid_sdf() -> str:
    return "\n".join(
        [
            "bounded-ligand",
            "EngineV2",
            "strict V2000 fixture",
            f"{2:3d}{1:3d}  0  0  0  0            999 V2000",
            _sdf_atom(0.0, 0.0, 0.0, "C"),
            _sdf_atom(1.25, 0.0, 0.0, "O"),
            f"{1:3d}{2:3d}{1:3d}{0:3d}  0  0  0",
            "M  CHG  1   2  -1",
            "M  ISO  1   1  13",
            "M  END",
            "$$$$",
        ]
    ) + "\n"


def test_strict_pdb_parser_builds_verified_ingest_without_chemistry_promotion() -> None:
    system = parse_pdb(_valid_pdb(), source_id="pdb-fixture")
    assert system.atom_count == 2
    assert len(system.bonds) == 1
    assert system.bonds[0].source == "pdb_conect"
    assert system.cell is not None
    assert torch.allclose(system.cell.orthorhombic_lengths(), torch.tensor([10.0, 10.0, 10.0], dtype=torch.float64))
    assert system.provenance.provenance_verified is True
    assert system.provenance.chemistry_validated is False
    assert system.provenance.claim_safe is False
    assert system.metadata["parser_claim_grade"] == "bounded_strict_ingest_only"

    altloc = _valid_pdb().replace(_pdb_atom(1, "C1", "C", 0.2, 0.0, 0.0), _pdb_atom(1, "C1", "C", 0.2, 0.0, 0.0, altloc="B"))
    with pytest.raises(PDBParseError, match="alternate locations"):
        parse_pdb(altloc)
    with pytest.raises(PDBParseError, match="max_atoms"):
        parse_pdb(_valid_pdb(), limits=PDBParserLimits(max_atoms=1))
    with pytest.raises(PDBParseError, match="multiple PDB MODEL"):
        parse_pdb("MODEL        1\n" + _valid_pdb() + "MODEL        2\nENDMDL\n")


def test_strict_pdb_parser_can_explicitly_ignore_nonperiodic_crystal_metadata() -> None:
    nonorthorhombic = _valid_pdb().replace(
        f"{90.0:7.2f}{90.0:7.2f}{90.0:7.2f}",
        f"{90.0:7.2f}{105.0:7.2f}{90.0:7.2f}",
    )
    with pytest.raises(PDBParseError, match="orthorhombic"):
        parse_pdb(nonorthorhombic)

    system = parse_pdb(nonorthorhombic, unit_cell_policy="ignore")
    assert system.cell is None
    assert system.provenance.metadata["unit_cell_policy"] == "ignore"
    assert system.provenance.metadata["ignored_record_counts"]["CRYST1"] == 1


def test_strict_sdf_parser_accepts_explicit_charge_isotope_and_rejects_multi_record() -> None:
    system = parse_sdf_v2000(_valid_sdf(), source_id="sdf-fixture")
    assert system.atom_count == 2
    assert len(system.bonds) == 1
    assert system.atoms[0].isotope_mass_number == 13
    assert system.atoms[1].formal_charge == -1
    assert system.provenance.provenance_verified is True
    assert system.provenance.chemistry_validated is False
    assert system.provenance.claim_safe is False

    with pytest.raises(SDFParseError, match="multiple SDF molecule"):
        parse_sdf_v2000(_valid_sdf() + _valid_sdf())
    with pytest.raises(SDFParseError, match="V3000"):
        parse_sdf_v2000(_valid_sdf().replace("V2000", "V3000"))
    with pytest.raises(SDFParseError, match="data fields"):
        parse_sdf_v2000(_valid_sdf().replace("M  END\n$$$$", "M  END\n> <NAME>\nvalue\n$$$$"))


ENERGY = QuantityDescriptor(
    name="energy",
    unit="kcal/mol",
    semantics="unit_test_independent_physics_energy",
    physical_quantity=True,
    calibrated=True,
    reference_method="unit_fixture",
)
FORCE = QuantityDescriptor(
    name="force",
    unit="kcal/mol/angstrom",
    semantics="unit_test_independent_physics_force",
    physical_quantity=True,
    calibrated=True,
    reference_method="unit_fixture",
)


class _ConstantPhysics:
    def __init__(self, provider_id: str, value: float):
        self.provider_id = provider_id
        self.provider_version = "1.0.0"
        self.value = float(value)

    def evaluate(self, system, neighbors):
        del neighbors
        batch, atoms = system.coordinates.shape[:2]
        return EnergyTermResult(
            name=self.provider_id,
            energy=torch.full((batch,), self.value, dtype=system.coordinates.dtype),
            forces=torch.zeros((batch, atoms, 3), dtype=system.coordinates.dtype),
            energy_descriptor=ENERGY,
            force_descriptor=FORCE,
            validated_for_composition=True,
            provenance_sha256=("a" if self.provider_id == "term-a" else "b") * 64,
        )


class _FailingPhysics:
    provider_id = "term-fail"
    provider_version = "1.0.0"

    def evaluate(self, system, neighbors):
        del system, neighbors
        raise RuntimeError("synthetic provider failure")


def test_physics_registry_sums_validated_terms_and_preserves_failure_rows() -> None:
    system = parse_sdf_v2000(_valid_sdf())
    neighbors = build_compact_radius_graph(
        system.coordinates,
        RadiusGraphConfig(cutoff_angstrom=3.0, max_neighbors=2, max_atoms_per_cell=4),
    )
    registry = PhysicsTermRegistry(max_terms=4)
    registry.register(_ConstantPhysics("term-a", 1.25))
    registry.register(_ConstantPhysics("term-b", 2.75))
    good = registry.evaluate(system, neighbors)
    assert good.complete
    total = sum_validated_physics_terms(good)
    assert total.energy.tolist() == pytest.approx([4.0])
    assert total.validated_for_composition is True
    assert len(good.registry_fingerprint_sha256) == 64

    registry.register(_FailingPhysics())
    mixed = registry.evaluate(system, neighbors)
    assert mixed.complete is False
    assert len(mixed.rows) == 3
    assert mixed.failed_rows[0].provider_id == "term-fail"
    assert mixed.failed_rows[0].error_code == "RuntimeError"
    with pytest.raises(PhysicsTermRegistryError, match="failure rows"):
        sum_validated_physics_terms(mixed)
    with pytest.raises(PhysicsTermRegistryError, match="duplicate"):
        registry.register(_ConstantPhysics("term-a", 0.0))


def _search_space() -> TorsionSearchSpace:
    local_offsets = torch.tensor(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        dtype=torch.float64,
    )
    return TorsionSearchSpace(
        local_offsets=local_offsets,
        parent=torch.tensor([-1, 0, 1, 2], dtype=torch.long),
        local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 4, dtype=torch.float64),
        rotatable_mask=torch.tensor([False, False, True, True]),
    )


class _InternalScorer:
    scorer_id = "internal-coordinate-spread"
    scorer_version = "1.0.0"
    validated_for_docking_ranking = False

    def score(self, proposal):
        if proposal.proposal_index == 3:
            raise RuntimeError("synthetic scoring failure")
        centered = proposal.coordinates - proposal.coordinates.mean(dim=0, keepdim=True)
        return centered.square().sum()


def test_bounded_docking_search_is_deterministic_and_keeps_failed_candidates() -> None:
    budget = DockingBudget(
        candidate_count=8,
        top_k=3,
        max_torsions=2,
        translation_radius_angstrom=2.0,
        seed=19,
    )
    first = generate_bounded_docking_proposals(_search_space(), budget)
    second = generate_bounded_docking_proposals(_search_space(), budget)
    assert [row.fingerprint_sha256 for row in first] == [row.fingerprint_sha256 for row in second]
    assert len(first) == 8

    result = run_bounded_docking_search(
        _search_space(),
        budget,
        _InternalScorer(),
        diversity_rmsd_angstrom=0.05,
    )
    assert len(result.rows) == 8
    assert result.failure_count == 1
    assert result.rows[3].status == "failure"
    assert result.rows[3].error_code == "RuntimeError"
    assert len(result.top_rows) == 3
    assert result.claim_safe is False
    assert "scorer_not_validated_for_docking_ranking" in result.blockers

    with pytest.raises(DockingProposalError, match="torsions"):
        generate_bounded_docking_proposals(
            _search_space(),
            replace(budget, max_torsions=1),
        )
    with pytest.raises(ValueError, match="cycle"):
        TorsionSearchSpace(
            local_offsets=torch.zeros((3, 3), dtype=torch.float64),
            parent=torch.tensor([-1, 2, 1], dtype=torch.long),
            local_axes=torch.tensor([[0.0, 0.0, 1.0]] * 3, dtype=torch.float64),
            rotatable_mask=torch.tensor([False, True, True]),
        )


def test_benchmark_manifest_preserves_one_ordered_row_per_case(tmp_path: Path) -> None:
    cases = tuple(
        BenchmarkCase(
            case_id=f"case-{index}",
            input_sha256=str(index + 1) * 64,
            task="pose_scoring_fixture",
            target_id="T",
            ligand_id=f"L{index}",
        )
        for index in range(3)
    )
    manifest = BenchmarkManifest(
        benchmark_id="bounded-fixture",
        dataset_name="unit",
        dataset_version="1",
        cases=cases,
        protocol_id="unit-protocol-v1",
    )
    context = BenchmarkRunContext(
        code_commit="a" * 40,
        environment_fingerprint_sha256="b" * 64,
        command=("python", "run_fixture.py"),
        seed=100,
    )

    def evaluator(case, seed):
        if case.case_id == "case-1":
            raise RuntimeError("synthetic benchmark failure")
        return BenchmarkCaseResult(
            metrics={"score": float(seed)},
            artifact_sha256="c" * 64,
        )

    report = run_benchmark_manifest(manifest, context, evaluator)
    assert report.complete
    assert report.success_count == 2
    assert report.failure_count == 1
    assert [row.case_id for row in report.rows] == ["case-0", "case-1", "case-2"]
    assert report.rows[1].status == "failure"
    assert report.rows[1].error_code == "RuntimeError"
    assert report.rows[1].metadata["failure_preserved"] is True
    assert report.claim_safe is False
    written = report.write_json(tmp_path / "report.json")
    assert written.exists()
    assert '"failure_count": 1' in written.read_text(encoding="utf-8")

    with pytest.raises(BenchmarkContractError, match="exactly one ordered row"):
        BenchmarkReport(manifest=manifest, context=context, rows=report.rows[:-1])
