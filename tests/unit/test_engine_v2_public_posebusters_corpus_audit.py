from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import zipfile

import pytest


pytest.importorskip("torch")

from betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit import (  # noqa: E402
    PoseBustersCorpusAuditError,
    _metric,
    materialize_posebusters_corpus_audit,
    verify_posebusters_corpus_audit_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_intake import (  # noqa: E402
    POSEBUSTERS_ARCHIVE_MEMBER_ROLES,
    POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES,
    PoseBustersArchiveContract,
    materialize_posebusters_archive_intake,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_native_geometry import (  # noqa: E402
    PoseBustersNativeGeometryError,
    materialize_posebusters_native_geometry,
    verify_posebusters_native_geometry_receipt,
)
from betelgeuze_engine_v2.benchmark import (  # noqa: E402
    public_posebusters_external_binary_execution as external_binary_module,
    public_posebusters_external_generated_pose_evaluation as external_generated_pose_module,
    public_posebusters_external_preparation as external_preparation_module,
    public_posebusters_generated_pose_evaluation as generated_pose_module,
    public_posebusters_internal_oracle_evaluation as internal_oracle_module,
    public_posebusters_rcsb_target_family_binding as rcsb_target_family_module,
    public_posebusters_target_cluster_binding as target_cluster_module,
    public_posebusters_vina_execution as vina_execution_module,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_binary_execution import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256,
    PoseBustersExternalBinaryCaseError,
    PoseBustersExternalBinaryExecutionError,
    PoseBustersExternalBinaryRuntimeIdentity,
    materialize_posebusters_external_binary_execution,
    verify_posebusters_external_binary_execution_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_generated_pose_evaluation import (  # noqa: E402
    PoseBustersExternalGeneratedPoseEvaluationError,
    materialize_posebusters_external_generated_pose_evaluation,
    verify_posebusters_external_generated_pose_evaluation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_generated_pose_evaluation import (  # noqa: E402
    POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256,
    POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS,
    PoseBustersGeneratedPoseEvaluationError,
    PoseBustersGeneratedPoseReportValue,
    PoseBustersGeneratedPoseRuntimeIdentity,
    materialize_posebusters_generated_pose_evaluation,
    verify_posebusters_generated_pose_evaluation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation import (  # noqa: E402
    POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256,
    PoseBustersExternalPreparationDependency,
    PoseBustersExternalPreparationError,
    PoseBustersExternalPreparationExecutionError,
    PoseBustersExternalPreparationReceipt,
    PoseBustersExternalPreparationRuntime,
    PoseBustersExternalPreparedBytes,
    materialize_posebusters_external_preparation,
    verify_posebusters_external_preparation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_vina_execution import (  # noqa: E402
    POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256,
    POSEBUSTERS_VINA_VERSION,
    PoseBustersVinaCaseExecutionError,
    PoseBustersVinaEngineIdentity,
    PoseBustersVinaExecutionBytes,
    PoseBustersVinaExecutionError,
    materialize_posebusters_vina_execution,
    verify_posebusters_vina_execution_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_internal_preparation import (  # noqa: E402
    PoseBustersInternalPreparationError,
    materialize_posebusters_internal_preparation,
    verify_posebusters_internal_preparation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_internal_execution import (  # noqa: E402
    PoseBustersInternalExecutionConfig,
    PoseBustersInternalExecutionError,
    materialize_posebusters_internal_execution,
    verify_posebusters_internal_execution_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_internal_rmsd_evaluation import (  # noqa: E402
    PoseBustersInternalRMSDConfig,
    materialize_posebusters_internal_rmsd_evaluation,
    verify_posebusters_internal_rmsd_evaluation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_internal_oracle_evaluation import (  # noqa: E402
    PoseBustersInternalOracleEvaluationError,
    materialize_posebusters_internal_oracle_evaluation,
    verify_posebusters_internal_oracle_evaluation_receipt,
)
from betelgeuze_engine_v2.benchmark.redocking_cli import (  # noqa: E402
    verify_redocking_diagnostic_report,
)
from betelgeuze_engine_v2.molecular import (  # noqa: E402
    all_atom_system_from_canonical_json,
    verify_rdkit_openff_prepared_system,
)


_CASE_IDS = ("1ABC_ABC", "2DEF_DEF")


def test_wilson_interval_contains_exact_boundary_estimates() -> None:
    all_success = _metric("all_success", 308, 308)
    no_success = _metric("no_success", 0, 308)

    assert all_success.estimate == 1.0
    assert all_success.confidence_interval_high == 1.0
    assert no_success.estimate == 0.0
    assert no_success.confidence_interval_low == 0.0


def _sha(source: bytes) -> str:
    return hashlib.sha256(source).hexdigest()


def _canonical_sha(value: object) -> str:
    source = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return _sha(source)


def _pdb_atom(
    serial: int,
    name: str,
    element: str,
    x: float,
    *,
    record: str,
    residue: str,
) -> str:
    return (
        f"{record:<6}{serial:5d} {name:<4}{'':1}{residue:>3} {'A':1}{1:4d}{'':1}   "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{10.0:6.2f}"
        f"          {element:>2}{'':>2}"
    )


def _receptor(*, zinc: bool, x_offset: float = 0.0) -> bytes:
    rows = [
        (
            f"CRYST1{20.0:9.3f}{21.0:9.3f}{22.0:9.3f}"
            f"{80.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1"
        ),
        _pdb_atom(
            10014,
            "C1",
            "C",
            x_offset,
            record="ATOM",
            residue="ALA",
        ),
        _pdb_atom(
            10015,
            "O1",
            "O",
            x_offset + 1.25,
            record="ATOM",
            residue="ALA",
        ),
        "CONECT1001510014",
    ]
    if zinc:
        rows.append(
            _pdb_atom(
                10016,
                "ZN",
                "ZN",
                x_offset + 4.0,
                record="HETATM",
                residue="ZN",
            )
        )
        rows.append(
            _pdb_atom(
                10017,
                "C2",
                "C",
                x_offset + 5.0,
                record="HETATM",
                residue="DEF",
            )
        )
    rows.append("END")
    return ("\n".join(rows) + "\n").encode("ascii")


def _sdf_atom(x: float, element: str) -> str:
    return (
        f"{x:10.4f}{0.0:10.4f}{0.0:10.4f} {element:<3}{0:2d}{0:3d}"
        "  0  0  0  0  0  0  0  0  0  0  0  0"
    )


def _ligand(*, explicit_hydrogen: bool, stereo_code: int, charge: int) -> bytes:
    atoms = [(0.0, "C"), (1.3, "O"), (2.6, "N")]
    bonds = [(1, 2, 1, stereo_code), (2, 3, 4, 0)]
    if explicit_hydrogen:
        atoms.append((-1.0, "H"))
        bonds.append((1, 4, 1, 0))
    rows = [
        "synthetic-ligand",
        "EngineV2",
        "PoseBusters corpus-audit fixture",
        f"{len(atoms):3d}{len(bonds):3d}  0  0  0  0            999 V2000",
        *(_sdf_atom(x, element) for x, element in atoms),
        *(
            f"{first:3d}{second:3d}{order:3d}{stereo:3d}  0  0  0"
            for first, second, order, stereo in bonds
        ),
        f"M  CHG  1   2  {charge}",
        "M  END",
        "$$$$",
    ]
    return ("\n".join(rows) + "\n").encode("ascii")


def _fixture(
    root: Path,
) -> tuple[Path, Path, Path, PoseBustersArchiveContract]:
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "posebusters.zip"
    selection_path = root / "selection.txt"
    intake_path = root / "intake.json"
    selection = ("\n".join(_CASE_IDS) + "\n").encode("ascii")
    selection_path.write_bytes(selection)
    readme = b"synthetic PoseBusters corpus-audit fixture\n"
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("posebusters_benchmark_set_ids.txt", selection)
        for case_index, case_id in enumerate(_CASE_IDS):
            charge = -1 if case_index == 0 else 5
            native = _ligand(
                explicit_hydrogen=False,
                stereo_code=1,
                charge=charge,
            )
            start = _ligand(
                explicit_hydrogen=True,
                stereo_code=(1 if case_index == 0 else 6),
                charge=charge,
            )
            sources = {
                "receptor_pdb": _receptor(zinc=case_index == 1),
                "reference_ligand_sdf": native,
                "reference_ligands_sdf": native,
                "ligand_start_conformer_sdf": start,
            }
            assert set(sources) == set(POSEBUSTERS_ARCHIVE_MEMBER_ROLES)
            for role in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
                member = (
                    f"posebusters_benchmark_set/{case_id}/"
                    f"{case_id}{POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES[role]}"
                )
                archive.writestr(member, sources[role])
    archive_source = archive_path.read_bytes()
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        uncompressed_size = sum(info.file_size for info in infos if not info.is_dir())
    contract = PoseBustersArchiveContract(
        dataset_id="synthetic_posebusters_corpus_audit",
        archive_sha256=_sha(archive_source),
        archive_size_bytes=len(archive_source),
        selection_sha256=_sha(selection),
        selection_size_bytes=len(selection),
        case_id_projection_sha256=_canonical_sha(list(_CASE_IDS)),
        selected_case_count=len(_CASE_IDS),
        archive_entry_count=len(infos),
        archive_uncompressed_size_bytes=uncompressed_size,
        archive_benchmark_case_count=len(_CASE_IDS),
        benchmark_root="posebusters_benchmark_set",
        embedded_case_list_member="posebusters_benchmark_set_ids.txt",
        embedded_case_list_sha256=_sha(selection),
        readme_member="README.txt",
        readme_sha256=_sha(readme),
    )
    intake = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )
    assert intake.ready_case_count == len(_CASE_IDS)
    intake.write_json(intake_path)
    return archive_path, selection_path, intake_path, contract


def _valid_internal_preparation_fixture(
    root: Path,
) -> tuple[Path, Path, Path, PoseBustersArchiveContract]:
    pytest.importorskip("rdkit")
    from rdkit import Chem
    from rdkit.Chem import AllChem

    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "posebusters.zip"
    selection_path = root / "selection.txt"
    intake_path = root / "intake.json"
    case_ids = ("1ABC_ABC",)
    selection = ("\n".join(case_ids) + "\n").encode("ascii")
    selection_path.write_bytes(selection)
    readme = b"synthetic internal-preparation fixture\n"
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 7301
    assert AllChem.EmbedMolecule(molecule, parameters) == 0
    ligand = (Chem.MolToMolBlock(molecule) + "$$$$\n").encode("ascii")
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("posebusters_benchmark_set_ids.txt", selection)
        case_id = case_ids[0]
        sources = {
            "receptor_pdb": _receptor(zinc=False, x_offset=8.0),
            "reference_ligand_sdf": ligand,
            "reference_ligands_sdf": ligand,
            "ligand_start_conformer_sdf": ligand,
        }
        for role in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
            member = (
                f"posebusters_benchmark_set/{case_id}/"
                f"{case_id}{POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES[role]}"
            )
            archive.writestr(member, sources[role])
    archive_source = archive_path.read_bytes()
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        uncompressed_size = sum(
            info.file_size for info in infos if not info.is_dir()
        )
    contract = PoseBustersArchiveContract(
        dataset_id="synthetic_posebusters_internal_preparation",
        archive_sha256=_sha(archive_source),
        archive_size_bytes=len(archive_source),
        selection_sha256=_sha(selection),
        selection_size_bytes=len(selection),
        case_id_projection_sha256=_canonical_sha(list(case_ids)),
        selected_case_count=len(case_ids),
        archive_entry_count=len(infos),
        archive_uncompressed_size_bytes=uncompressed_size,
        archive_benchmark_case_count=len(case_ids),
        benchmark_root="posebusters_benchmark_set",
        embedded_case_list_member="posebusters_benchmark_set_ids.txt",
        embedded_case_list_sha256=_sha(selection),
        readme_member="README.txt",
        readme_sha256=_sha(readme),
    )
    intake = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )
    intake.write_json(intake_path)
    return archive_path, selection_path, intake_path, contract


def test_corpus_audit_retains_all_cases_and_separates_scope_metrics(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path)

    receipt = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )

    assert len(receipt.case_rows) == 2
    assert receipt.audited_case_count == 2
    assert receipt.input_identity_ready is False
    assert tuple(role for role, _digest in receipt.implementation_source_members) == (
        "corpus_audit",
        "heavy_graph_audit",
        "pdb_connectivity_parser",
        "pdb_subset_parser",
        "posebusters_archive_intake",
        "public_materialization_graph_search",
        "reference_docking_scope",
        "sdf_v2000_parser",
    )
    first, second = receipt.case_rows
    assert first.receptor_polymer_atom_count == 2
    assert first.receptor_nonpolymer_atom_count == 0
    assert first.native_ligand_atom_count == 3
    assert first.start_ligand_atom_count == 4
    assert first.heavy_graph_comparison is not None
    assert first.heavy_graph_comparison.graph_match is True
    assert first.heavy_graph_comparison.directional_stereo_match is True
    assert first.native_raw_aromatic_bond_count == 1
    assert first.start_raw_aromatic_bond_count == 1
    assert first.reference_scorer_scope_blockers == (
        "parameters_and_partial_charges_missing",
    )
    assert second.receptor_nonwater_nonpolymer_residue_names == ("DEF", "ZN")
    assert second.metal_atomic_numbers == (30,)
    assert second.unsupported_receptor_atomic_numbers == (30,)
    assert second.native_ligand_maximum_absolute_atom_formal_charge == 5
    assert second.heavy_graph_comparison is not None
    assert second.heavy_graph_comparison.graph_match is True
    assert second.heavy_graph_comparison.directional_stereo_match is False
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    expected = {
        "corpus_audited_rate": 2,
        "heavy_connectivity_match_rate": 2,
        "raw_directional_bond_stereo_match_rate": 1,
        "raw_aromatic_bond_presence_rate": 2,
        "raw_aromatic_bond_count_match_rate": 2,
        "ligand_element_scope_rate": 2,
        "receptor_element_scope_rate": 1,
        "formal_charge_scope_rate": 1,
        "ligand_atom_capacity_scope_rate": 2,
        "metal_free_rate": 1,
        "nonwater_cofactor_free_rate": 1,
        "reference_scorer_chemistry_scope_rate": 1,
        "reference_scorer_admission_rate": 0,
    }
    assert {name: metric.numerator for name, metric in metrics.items()} == expected
    assert all(metric.denominator == 2 for metric in metrics.values())
    assert all(
        0.0 <= metric.confidence_interval_low <= metric.estimate
        for metric in metrics.values()
    )
    assert all(
        metric.estimate <= metric.confidence_interval_high <= 1.0
        for metric in metrics.values()
    )
    payload = receipt.to_dict()
    assert payload["archive_extracted"] is False
    assert payload["external_stereo_oracle_present"] is False
    assert payload["pose_generation_performed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False


def test_corpus_audit_receipt_is_private_no_overwrite_and_exactly_reexecutable(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    receipt = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    output = tmp_path / "receipts" / "corpus-audit.json"

    receipt.write_json(output)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_corpus_audit_receipt(
        output,
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(PoseBustersCorpusAuditError, match="already exists"):
        receipt.write_json(output)
    output.write_bytes(
        output.read_bytes().replace(b'"claim_safe":false', b'"claim_safe":true')
    )
    with pytest.raises(PoseBustersCorpusAuditError, match="exact reexecution"):
        verify_posebusters_corpus_audit_receipt(
            output,
            archive_path,
            selection_path,
            intake_path,
            contract=contract,
        )


def test_corpus_audit_fails_closed_when_intake_inputs_change(tmp_path: Path) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path)
    archive_path.write_bytes(archive_path.read_bytes() + b"tamper")

    with pytest.raises(
        PoseBustersCorpusAuditError,
        match="intake receipt did not verify",
    ):
        materialize_posebusters_corpus_audit(
            archive_path,
            selection_path,
            intake_path,
            contract=contract,
        )


def test_internal_preparation_retains_denominator_and_exact_canonical_artifacts(
    tmp_path: Path,
) -> None:
    pytest.importorskip("rdkit")
    archive_path, selection_path, intake_path, contract = (
        _valid_internal_preparation_fixture(tmp_path / "source")
    )
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "corpus.json"
    corpus.write_json(corpus_path)
    artifact_root = tmp_path / "canonical-inputs"
    receipt = materialize_posebusters_internal_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        artifact_root,
        contract=contract,
    )

    assert len(receipt.case_rows) == 1
    first = receipt.case_rows[0]
    assert first.status == "prepared"
    assert receipt.prepared_case_count == 1
    assert tuple(row.role for row in first.artifacts) == (
        "canonical_ligand_json",
        "canonical_receptor_json",
    )
    payload = receipt.to_dict()
    assert payload["all_case_denominator"] == 1
    assert payload["redocking_executed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False
    assert all(metric.denominator == 1 for metric in receipt.metrics)

    artifacts = {row.role: row for row in first.artifacts}
    receptor_source = (
        artifact_root / artifacts["canonical_receptor_json"].relative_path
    ).read_bytes()
    ligand_source = (
        artifact_root / artifacts["canonical_ligand_json"].relative_path
    ).read_bytes()
    receptor = all_atom_system_from_canonical_json(receptor_source)
    ligand = all_atom_system_from_canonical_json(ligand_source)
    assert receptor.cell is None
    ligand_receipt = verify_rdkit_openff_prepared_system(ligand)
    assert ligand_receipt["status"] == "prepared_diagnostic"
    assert ligand_receipt["readiness"]["diagnostic_redocking_ready"] is True

    receipt_path = tmp_path / "internal-preparation.json"
    receipt.write_json(receipt_path)
    verified = verify_posebusters_internal_preparation_receipt(
        receipt_path,
        artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600

    duplicate_path = tmp_path / "internal-preparation-duplicate.json"
    duplicate_path.write_bytes(
        receipt_path.read_bytes().replace(
            b'"schema_id":',
            b'"schema_id":"duplicate","schema_id":',
            1,
        )
    )
    with pytest.raises(
        PoseBustersInternalPreparationError,
        match="duplicate JSON key",
    ):
        verify_posebusters_internal_preparation_receipt(
            duplicate_path,
            artifact_root,
            archive_path,
            selection_path,
            intake_path,
            corpus_path,
            contract=contract,
        )

    ligand_path = artifact_root / artifacts["canonical_ligand_json"].relative_path
    ligand_path.write_bytes(ligand_path.read_bytes() + b" ")
    with pytest.raises(
        PoseBustersInternalPreparationError,
        match="artifact tree failed exact verification",
    ):
        verify_posebusters_internal_preparation_receipt(
            receipt_path,
            artifact_root,
            archive_path,
            selection_path,
            intake_path,
            corpus_path,
            contract=contract,
        )


def test_internal_preparation_retains_failure_and_scope_abstention_rows(
    tmp_path: Path,
) -> None:
    pytest.importorskip("rdkit")
    archive_path, selection_path, intake_path, contract = _fixture(
        tmp_path / "source"
    )
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "corpus.json"
    corpus.write_json(corpus_path)

    receipt = materialize_posebusters_internal_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        tmp_path / "canonical-inputs",
        contract=contract,
    )

    first, second = receipt.case_rows
    assert first.status == "preparation_failure"
    assert first.preparation_attempted is True
    assert first.error_code == "internal_canonical_preparation_failed"
    assert first.private_error_sha256
    assert first.private_error_byte_length > 0
    assert second.status == "abstain_chemistry_scope"
    assert second.preparation_attempted is False
    assert not second.artifacts
    assert receipt.prepared_case_count == 0
    metrics = {row.metric_id: row for row in receipt.metrics}
    assert metrics["scope_admission_rate"].numerator == 1
    assert metrics["preparation_attempt_rate"].numerator == 1
    assert metrics["canonical_preparation_success_rate"].numerator == 0
    assert metrics["preparation_failure_rate"].numerator == 1
    assert all(row.denominator == 2 for row in receipt.metrics)


def test_internal_execution_runs_prepared_case_and_is_exactly_reexecutable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("rdkit")
    archive_path, selection_path, intake_path, contract = (
        _valid_internal_preparation_fixture(tmp_path / "source")
    )
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    preparation_artifact_root = tmp_path / "canonical-inputs"
    preparation = materialize_posebusters_internal_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        preparation_artifact_root,
        contract=contract,
    )
    preparation_path = tmp_path / "receipts" / "internal-preparation.json"
    preparation.write_json(preparation_path)
    configuration = PoseBustersInternalExecutionConfig(
        candidate_count=3,
        top_k=2,
        max_torsions=2,
        translation_radius_angstrom=1.0,
        diversity_rmsd_angstrom=0.1,
        max_refinement_steps=0,
        base_seed=91,
    )
    output_artifact_root = tmp_path / "internal-redocking"

    receipt = materialize_posebusters_internal_execution(
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        output_artifact_root,
        contract=contract,
        configuration=configuration,
    )

    assert len(receipt.case_rows) == 1
    row = receipt.case_rows[0]
    assert row.status == "success"
    assert row.execution_attempted is True
    assert row.case_seed == configuration.case_seed(row.case_id)
    assert row.candidate_count == 3
    assert row.candidate_success_count + row.candidate_failure_count == 3
    assert row.artifact is not None
    report_path = output_artifact_root / row.artifact.relative_path
    report = verify_redocking_diagnostic_report(report_path.read_bytes())
    assert report["status"] == "diagnostic_complete"
    assert report["receipt_sha256"] == row.artifact.diagnostic_receipt_sha256
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert metrics["prepared_input_pair_rate"].numerator == 1
    assert metrics["internal_redocking_attempt_rate"].numerator == 1
    assert (
        metrics["internal_redocking_diagnostic_completion_rate"].numerator
        == 1
    )
    assert all(metric.denominator == 1 for metric in receipt.metrics)
    payload = receipt.to_dict()
    assert payload["internal_redocking_diagnostic_batch_executed"] is True
    assert payload["symmetry_aware_native_rmsd_evaluated"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    receipt_path = tmp_path / "receipts" / "internal-execution.json"
    receipt.write_json(receipt_path)
    verified = verify_posebusters_internal_execution_receipt(
        receipt_path,
        output_artifact_root,
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
        configuration=configuration,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600

    rmsd_configuration = PoseBustersInternalRMSDConfig(top_k=2)
    rmsd_receipt = materialize_posebusters_internal_rmsd_evaluation(
        receipt_path,
        output_artifact_root,
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
        execution_configuration=configuration,
        configuration=rmsd_configuration,
    )
    rmsd_row = rmsd_receipt.case_rows[0]
    assert rmsd_row.status == "evaluated"
    assert rmsd_row.native_to_start_symmetry_mapping_count >= 1
    assert len(rmsd_row.pose_results) == row.top_pose_count == 2
    assert all(pose.internal_pose_valid for pose in rmsd_row.pose_results)
    assert all(
        pose.direct_rmsd_angstrom >= 0.0
        for pose in rmsd_row.pose_results
    )
    rmsd_metrics = {
        metric.metric_id: metric for metric in rmsd_receipt.metrics
    }
    assert rmsd_metrics["direct_rmsd_evaluation_rate"].numerator == 1
    assert all(metric.denominator == 1 for metric in rmsd_receipt.metrics)
    rmsd_payload = rmsd_receipt.to_dict()
    assert rmsd_payload["connectivity_symmetry_aware_rmsd_evaluated"] is True
    assert rmsd_payload["complete_atom_stereo_symmetry_evaluated"] is False
    assert rmsd_payload["posebusters_external_oracle_executed"] is False
    assert rmsd_payload["benchmark_executed"] is False
    assert rmsd_payload["claim_safe"] is False

    rmsd_receipt_path = tmp_path / "receipts" / "internal-rmsd.json"
    rmsd_receipt.write_json(rmsd_receipt_path)
    verified_rmsd = verify_posebusters_internal_rmsd_evaluation_receipt(
        rmsd_receipt_path,
        receipt_path,
        output_artifact_root,
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
        execution_configuration=configuration,
        configuration=rmsd_configuration,
    )
    assert verified_rmsd.fingerprint_sha256 == rmsd_receipt.fingerprint_sha256
    assert stat.S_IMODE(rmsd_receipt_path.stat().st_mode) == 0o600

    successful_runtime = _InternalOracleRuntime(
        tuple(
            _successful_internal_oracle_outcome()
            for _pose in rmsd_row.pose_results
        )
    )
    monkeypatch.setattr(
        internal_oracle_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: successful_runtime,
    )
    oracle_common = {
        "internal_rmsd_receipt_path": rmsd_receipt_path,
        "execution_receipt_path": receipt_path,
        "execution_artifact_root": output_artifact_root,
        "preparation_receipt_path": preparation_path,
        "preparation_artifact_root": preparation_artifact_root,
        "archive_path": archive_path,
        "selection_path": selection_path,
        "intake_receipt_path": intake_path,
        "corpus_audit_receipt_path": corpus_path,
        "posebusters_wheel_path": tmp_path / "posebusters.whl",
        "scratch_root": tmp_path / "posebusters-scratch",
        "expected_internal_rmsd_receipt_sha256": (
            rmsd_receipt.fingerprint_sha256
        ),
        "contract": contract,
        "execution_configuration": configuration,
        "rmsd_configuration": rmsd_configuration,
    }
    oracle = materialize_posebusters_internal_oracle_evaluation(
        **oracle_common
    )
    oracle_row = oracle.case_rows[0]
    assert oracle_row.status == "evaluated"
    assert oracle_row.oracle_attempted is True
    assert len(oracle_row.pose_results) == 2
    assert all(
        pose.status == "evaluated" for pose in oracle_row.pose_results
    )
    assert all(
        pose.internal_oracle_direct_rmsd_delta_angstrom_binary64_hex
        for pose in oracle_row.pose_results
    )
    assert successful_runtime.calls == 1
    oracle_metrics = {metric.metric_id: metric for metric in oracle.metrics}
    assert (
        oracle_metrics["posebusters_complete_case_evaluation_rate"].numerator
        == 1
    )
    assert oracle_metrics["pose_evaluation_success_rate"].denominator == 2
    oracle_payload = oracle.to_dict()
    assert oracle_payload["all_case_denominator"] == 1
    assert oracle_payload["posebusters_redock_oracle_executed"] is True
    assert oracle_payload["benchmark_executed"] is False
    assert oracle_payload["claim_safe"] is False

    oracle_path = tmp_path / "receipts" / "internal-oracle.json"
    oracle.write_json(oracle_path)
    verified_oracle = verify_posebusters_internal_oracle_evaluation_receipt(
        oracle_path,
        **oracle_common,
    )
    assert verified_oracle.fingerprint_sha256 == oracle.fingerprint_sha256
    assert successful_runtime.calls == 2
    assert stat.S_IMODE(oracle_path.stat().st_mode) == 0o600
    oracle_path.write_bytes(oracle_path.read_bytes() + b" ")
    with pytest.raises(
        PoseBustersInternalOracleEvaluationError,
        match="does not match exact reexecution",
    ):
        verify_posebusters_internal_oracle_evaluation_receipt(
            oracle_path,
            **oracle_common,
        )

    partial_runtime = _InternalOracleRuntime(
        (
            _successful_internal_oracle_outcome(),
            _failed_internal_oracle_outcome(),
        )
    )
    monkeypatch.setattr(
        internal_oracle_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: partial_runtime,
    )
    partial = materialize_posebusters_internal_oracle_evaluation(
        **oracle_common
    )
    partial_row = partial.case_rows[0]
    assert partial_row.status == "partial_evaluation"
    assert tuple(pose.status for pose in partial_row.pose_results) == (
        "evaluated",
        "evaluation_failure",
    )
    assert partial_row.pose_results[1].error_code == (
        "posebusters_pose_evaluation_failed"
    )

    adapter_runtime = _FailingInternalOracleAdapterRuntime()
    monkeypatch.setattr(
        internal_oracle_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: adapter_runtime,
    )
    adapter_failure = materialize_posebusters_internal_oracle_evaluation(
        **oracle_common
    )
    adapter_row = adapter_failure.case_rows[0]
    assert adapter_row.status == "adapter_failure"
    assert adapter_row.selected_pose_count == 2
    assert adapter_row.oracle_attempted is False
    assert adapter_row.error_code == "internal_pose_reconstruction_failed"
    assert not adapter_row.pose_results
    adapter_metrics = {
        metric.metric_id: metric for metric in adapter_failure.metrics
    }
    assert adapter_metrics["pose_evaluation_success_rate"].numerator == 0
    assert adapter_metrics["pose_evaluation_success_rate"].denominator == 2

    report_path.write_bytes(report_path.read_bytes() + b" ")
    with pytest.raises(
        PoseBustersInternalExecutionError,
        match="artifact tree failed exact verification",
    ):
        verify_posebusters_internal_execution_receipt(
            receipt_path,
            output_artifact_root,
            preparation_path,
            preparation_artifact_root,
            archive_path,
            selection_path,
            intake_path,
            corpus_path,
            contract=contract,
            configuration=configuration,
        )


def test_internal_execution_retains_preparation_failure_and_abstention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("rdkit")
    archive_path, selection_path, intake_path, contract = _fixture(
        tmp_path / "source"
    )
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    preparation_artifact_root = tmp_path / "canonical-inputs"
    preparation = materialize_posebusters_internal_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        preparation_artifact_root,
        contract=contract,
    )
    preparation_path = tmp_path / "receipts" / "internal-preparation.json"
    preparation.write_json(preparation_path)

    execution_configuration = PoseBustersInternalExecutionConfig(
        candidate_count=1,
        top_k=1,
        max_torsions=0,
        max_refinement_steps=0,
    )
    receipt = materialize_posebusters_internal_execution(
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        tmp_path / "internal-redocking",
        contract=contract,
        configuration=execution_configuration,
    )

    first, second = receipt.case_rows
    assert first.status == "blocked_preparation_failure"
    assert first.execution_attempted is False
    assert second.status == "abstain_chemistry_scope"
    assert second.execution_attempted is False
    assert receipt.attempted_case_count == 0
    assert receipt.success_case_count == 0
    assert all(metric.denominator == 2 for metric in receipt.metrics)

    execution_path = tmp_path / "receipts" / "internal-execution.json"
    receipt.write_json(execution_path)
    rmsd_receipt = materialize_posebusters_internal_rmsd_evaluation(
        execution_path,
        tmp_path / "internal-redocking",
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
        execution_configuration=execution_configuration,
    )
    first_rmsd, second_rmsd = rmsd_receipt.case_rows
    assert first_rmsd.status == "blocked_execution"
    assert second_rmsd.status == "blocked_execution"
    assert rmsd_receipt.evaluated_case_count == 0
    assert rmsd_receipt.evaluated_pose_count == 0
    assert all(metric.denominator == 2 for metric in rmsd_receipt.metrics)

    rmsd_path = tmp_path / "receipts" / "internal-rmsd.json"
    rmsd_receipt.write_json(rmsd_path)
    blocked_runtime = _InternalOracleRuntime(())
    monkeypatch.setattr(
        internal_oracle_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: blocked_runtime,
    )
    oracle = materialize_posebusters_internal_oracle_evaluation(
        rmsd_path,
        execution_path,
        tmp_path / "internal-redocking",
        preparation_path,
        preparation_artifact_root,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        tmp_path / "posebusters.whl",
        tmp_path / "posebusters-scratch",
        expected_internal_rmsd_receipt_sha256=(
            rmsd_receipt.fingerprint_sha256
        ),
        contract=contract,
        execution_configuration=execution_configuration,
    )
    assert tuple(row.status for row in oracle.case_rows) == (
        "blocked_upstream",
        "blocked_upstream",
    )
    assert oracle.selected_pose_count == 0
    assert oracle.evaluated_pose_count == 0
    assert blocked_runtime.calls == 0
    assert all(
        metric.denominator == 2
        for metric in oracle.metrics
        if metric.denominator_scope == "all_cases"
    )


def test_native_geometry_preflight_is_all_case_claim_closed_and_reexecutable(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)

    receipt = materialize_posebusters_native_geometry(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
    )

    assert receipt.processed_case_count == 2
    first, second = receipt.case_rows
    assert first.status == "evaluated"
    assert first.minimum_receptor_ligand_ratio_hex == (0.0).hex()
    assert first.deep_penetration_free is False
    assert first.overlap_free is False
    assert first.ligand_self_overlap_free is True
    assert first.bond_delta_within_tolerance is True
    assert first.bounded_geometry_pass is False
    assert first.reference_ligand_residue_present_in_receptor is False
    assert first.bounded_geometry_and_reference_chemistry_scope is False
    assert second.status == "partial_unsupported_element"
    assert second.unsupported_atomic_numbers == (30,)
    assert second.receptor_ligand_geometry_evaluated is False
    assert second.reference_ligand_residue_present_in_receptor is True
    assert second.deep_penetration_free is None
    assert second.ligand_self_overlap_free is True
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert {name: metric.numerator for name, metric in metrics.items()} == {
        "case_processed_rate": 2,
        "receptor_ligand_element_geometry_evaluated_rate": 1,
        "deep_penetration_free_all_case_rate": 0,
        "overlap_free_all_case_rate": 0,
        "ligand_self_overlap_free_all_case_rate": 2,
        "native_start_bond_delta_within_tolerance_rate": 2,
        "bounded_geometry_pass_rate": 0,
        "reference_ligand_residue_absent_from_receptor_rate": 1,
        "reference_scorer_chemistry_scope_rate": 1,
        "bounded_geometry_and_reference_chemistry_scope_rate": 0,
        "complete_pose_validity_rate": 0,
    }
    assert all(metric.denominator == 2 for metric in metrics.values())
    payload = receipt.to_dict()
    assert payload["native_crystal_pose_positive_control"] is True
    assert payload["generated_pose_evaluated"] is False
    assert payload["posebusters_external_oracle_executed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "receipts" / "native-geometry.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_native_geometry_receipt(
        output,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        contract=contract,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(PoseBustersNativeGeometryError, match="already exists"):
        receipt.write_json(output)


def _fake_external_preparation_runtime() -> PoseBustersExternalPreparationRuntime:
    dependency = PoseBustersExternalPreparationDependency(
        distribution_name="fake_meeko",
        version="0.0.test",
        payload_sha256=_sha(b"fake dependency payload"),
        payload_file_count=1,
        payload_size_bytes=23,
    )
    return PoseBustersExternalPreparationRuntime(
        python_implementation="CPython",
        python_version="3.10.0",
        python_cache_tag="cpython-310",
        python_executable_sha256=_sha(b"fake python executable"),
        python_executable_size_bytes=22,
        platform_system="Linux",
        platform_machine="x86_64",
        libc_name="glibc",
        libc_version="2.35",
        filesystem_encoding="utf-8",
        torch_version="2.6.0+test",
        dependencies=(dependency,),
    )


class _SuccessfulExternalPreparationRuntime:
    configuration_sha256 = POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
    identity = _fake_external_preparation_runtime()

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
    ) -> PoseBustersExternalPreparedBytes:
        receptor = f"REMARK receptor source {_sha(receptor_pdb)}\nEND\n".encode("ascii")
        ligand = f"REMARK ligand source {_sha(ligand_start_sdf)}\nEND\n".encode("ascii")
        return PoseBustersExternalPreparedBytes(
            receptor_pdbqt=receptor,
            ligand_pdbqt=ligand,
            diagnostic_sha256=_sha(b""),
            diagnostic_size_bytes=0,
        )


class _FailingExternalPreparationRuntime:
    configuration_sha256 = POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256
    identity = _fake_external_preparation_runtime()

    def prepare(
        self,
        receptor_pdb: bytes,
        ligand_start_sdf: bytes,
    ) -> PoseBustersExternalPreparedBytes:
        assert receptor_pdb
        assert ligand_start_sdf
        raise PoseBustersExternalPreparationExecutionError(
            stage="receptor_preparation",
            error_code="strict_receptor_template_match_failed",
            error_type="PolymerCreationError",
            error_message_sha256=_sha(b"template matching failed"),
            failing_residue_keys=("A:12", "B:31"),
            ligand_preparation_succeeded=True,
            diagnostic_sha256=_sha(b"bounded diagnostic"),
            diagnostic_size_bytes=len(b"bounded diagnostic"),
        )


def test_external_preparation_materializes_only_candidate_and_exact_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    monkeypatch.setattr(
        external_preparation_module,
        "_load_meeko_runtime",
        lambda: _SuccessfulExternalPreparationRuntime(),
    )
    artifact_root = tmp_path / "prepared"

    receipt = materialize_posebusters_external_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        artifact_root,
        contract=contract,
    )

    assert receipt.attempted_case_count == 1
    assert receipt.prepared_case_count == 1
    assert receipt.failed_case_count == 0
    assert receipt.abstained_case_count == 1
    first, second = receipt.case_rows
    assert first.status == "prepared"
    assert first.ligand_preparation_succeeded is True
    assert first.receptor_preparation_succeeded is True
    assert len(first.pocket_center_binary64_hex) == 3
    assert tuple(artifact.role for artifact in first.artifacts) == (
        "prepared_ligand_pdbqt",
        "prepared_receptor_pdbqt",
    )
    assert second.status == "abstain_chemistry_scope"
    assert second.preparation_attempted is False
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert {name: metric.numerator for name, metric in metrics.items()} == {
        "upstream_corpus_ready_rate": 2,
        "reference_scorer_chemistry_candidate_rate": 1,
        "chemistry_scope_abstention_rate": 1,
        "strict_preparation_attempt_rate": 1,
        "strict_ligand_preparation_success_rate": 1,
        "strict_receptor_preparation_success_rate": 1,
        "prepared_input_pair_materialization_rate": 1,
        "strict_preparation_failure_rate": 0,
        "external_engine_execution_rate": 0,
        "docking_result_rate": 0,
    }
    assert all(metric.denominator == 2 for metric in metrics.values())
    assert stat.S_IMODE(artifact_root.stat().st_mode) == 0o700
    for artifact in first.artifacts:
        path = artifact_root / artifact.relative_path
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert _sha(path.read_bytes()) == artifact.sha256
    payload = receipt.to_dict()
    assert payload["archive_extracted"] is False
    assert payload["strict_bad_residue_deletion_allowed"] is False
    assert payload["external_engine_executed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    receipt_path = tmp_path / "receipts" / "external-preparation.json"
    receipt.write_json(receipt_path)
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    verified = verify_posebusters_external_preparation_receipt(
        receipt_path,
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        artifact_root,
        contract=contract,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(PoseBustersExternalPreparationError, match="already exists"):
        materialize_posebusters_external_preparation(
            archive_path,
            selection_path,
            intake_path,
            corpus_path,
            artifact_root,
            contract=contract,
        )

    ligand_path = artifact_root / first.artifacts[0].relative_path
    ligand_path.write_bytes(ligand_path.read_bytes() + b"tamper")
    with pytest.raises(
        PoseBustersExternalPreparationError,
        match="exact reexecution",
    ):
        verify_posebusters_external_preparation_receipt(
            receipt_path,
            archive_path,
            selection_path,
            intake_path,
            corpus_path,
            artifact_root,
            contract=contract,
        )


def test_external_preparation_retains_strict_template_failure_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    monkeypatch.setattr(
        external_preparation_module,
        "_load_meeko_runtime",
        lambda: _FailingExternalPreparationRuntime(),
    )

    receipt = materialize_posebusters_external_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        tmp_path / "failed-preparation",
        contract=contract,
    )

    first, second = receipt.case_rows
    assert first.status == "preparation_failure"
    assert first.error_code == "strict_receptor_template_match_failed"
    assert first.error_type == "PolymerCreationError"
    assert first.failing_residue_keys == ("A:12", "B:31")
    assert first.ligand_preparation_succeeded is True
    assert first.receptor_preparation_succeeded is False
    assert not first.artifacts
    assert second.status == "abstain_chemistry_scope"
    assert receipt.attempted_case_count == 1
    assert receipt.prepared_case_count == 0
    assert receipt.failed_case_count == 1
    assert receipt.abstained_case_count == 1
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert metrics["strict_ligand_preparation_success_rate"].numerator == 1
    assert metrics["strict_receptor_preparation_success_rate"].numerator == 0
    assert metrics["strict_preparation_failure_rate"].numerator == 1


def _fake_vina_engine_identity() -> PoseBustersVinaEngineIdentity:
    dependency = PoseBustersExternalPreparationDependency(
        distribution_name="vina",
        version=POSEBUSTERS_VINA_VERSION,
        payload_sha256=_sha(b"fake Vina distribution payload"),
        payload_file_count=3,
        payload_size_bytes=31,
    )
    return PoseBustersVinaEngineIdentity(
        preparation_runtime=_fake_external_preparation_runtime(),
        vina_dependency=dependency,
        vina_api_source_sha256=_sha(b"fake Vina Python API source"),
    )


class _SuccessfulVinaRuntime:
    identity = _fake_vina_engine_identity()

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> PoseBustersVinaExecutionBytes:
        assert receptor_pdbqt
        assert ligand_pdbqt
        assert len(pocket_center_binary64_hex) == 3
        poses = (
            b"MODEL 1\n"
            b"REMARK VINA RESULT: -7.000 0.000 0.000\n"
            b"ATOM      1  C   LIG A   1       0.000   0.000   0.000  0.00  0.00      0.000 C\n"
            b"ENDMDL\n"
        )
        return PoseBustersVinaExecutionBytes(
            poses_pdbqt=poses,
            energies_binary64_hex=(
                tuple(value.hex() for value in (-7.0, -7.1, 0.1, 0.0, -7.1)),
            ),
            diagnostic_sha256=_sha(b""),
            diagnostic_size_bytes=0,
        )


class _FailingVinaRuntime:
    identity = _fake_vina_engine_identity()

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> PoseBustersVinaExecutionBytes:
        assert receptor_pdbqt
        assert ligand_pdbqt
        assert len(pocket_center_binary64_hex) == 3
        raise PoseBustersVinaCaseExecutionError(
            stage="vina_execution",
            error_code="vina_execution_failed",
            error_type="RuntimeError",
            error_message_sha256=_sha(b"bounded Vina failure"),
            diagnostic_sha256=_sha(b"bounded diagnostic"),
            diagnostic_size_bytes=len(b"bounded diagnostic"),
        )


def _materialize_fake_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    runtime: object,
) -> tuple[Path, Path, PoseBustersExternalPreparationReceipt]:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    monkeypatch.setattr(
        external_preparation_module,
        "_load_meeko_runtime",
        lambda: runtime,
    )
    preparation_artifact_root = tmp_path / "prepared"
    preparation = materialize_posebusters_external_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        preparation_artifact_root,
        contract=contract,
    )
    preparation_path = tmp_path / "receipts" / "preparation.json"
    preparation.write_json(preparation_path)
    return preparation_path, preparation_artifact_root, preparation


def test_vina_execution_materializes_all_case_rows_and_exact_pose_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, preparation_artifact_root, preparation = (
        _materialize_fake_preparation(
            tmp_path,
            monkeypatch,
            runtime=_SuccessfulExternalPreparationRuntime(),
        )
    )
    monkeypatch.setattr(
        vina_execution_module,
        "_load_vina_runtime",
        lambda _scratch_root: _SuccessfulVinaRuntime(),
    )
    output_artifact_root = tmp_path / "vina-poses"
    scratch_root = tmp_path / "vina-scratch"
    receipt = materialize_posebusters_vina_execution(
        preparation_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )

    assert receipt.configuration_sha256 == (
        POSEBUSTERS_VINA_EXECUTION_CONFIGURATION_SHA256
    )
    assert receipt.attempted_case_count == 1
    assert receipt.success_case_count == 1
    assert receipt.engine_failure_case_count == 0
    first, second = receipt.case_rows
    assert first.status == "success"
    assert first.pose_count == 1
    assert first.pose_artifact is not None
    assert second.status == "abstain_chemistry_scope"
    assert second.engine_attempted is False
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert metrics["strict_prepared_input_pair_rate"].numerator == 1
    assert metrics["vina_engine_attempt_rate"].numerator == 1
    assert metrics["vina_engine_success_rate"].numerator == 1
    assert metrics["generated_pose_validity_evaluation_rate"].numerator == 0
    assert all(metric.denominator == 2 for metric in metrics.values())
    assert stat.S_IMODE(output_artifact_root.stat().st_mode) == 0o700
    pose_path = output_artifact_root / first.pose_artifact.relative_path
    assert stat.S_IMODE(pose_path.stat().st_mode) == 0o600
    assert _sha(pose_path.read_bytes()) == first.pose_artifact.sha256
    payload = receipt.to_dict()
    assert payload["external_engine_executed"] is True
    assert payload["vina_same_input_execution_performed"] is True
    assert payload["generated_pose_validity_evaluated"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    receipt_path = tmp_path / "receipts" / "vina.json"
    receipt.write_json(receipt_path)
    verified = verify_posebusters_vina_execution_receipt(
        receipt_path,
        preparation_path,
        preparation_artifact_root,
        output_artifact_root,
        scratch_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256

    pose_path.write_bytes(pose_path.read_bytes() + b"tamper")
    with pytest.raises(
        PoseBustersVinaExecutionError,
        match="exact verification",
    ):
        verify_posebusters_vina_execution_receipt(
            receipt_path,
            preparation_path,
            preparation_artifact_root,
            output_artifact_root,
            scratch_root,
            expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        )


@pytest.mark.parametrize(
    ("preparation_runtime", "vina_runtime", "first_status"),
    (
        (
            _SuccessfulExternalPreparationRuntime(),
            _FailingVinaRuntime(),
            "engine_failure",
        ),
        (
            _FailingExternalPreparationRuntime(),
            _SuccessfulVinaRuntime(),
            "blocked_preparation_failure",
        ),
    ),
)
def test_vina_execution_retains_engine_and_preparation_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preparation_runtime: object,
    vina_runtime: object,
    first_status: str,
) -> None:
    preparation_path, preparation_artifact_root, preparation = (
        _materialize_fake_preparation(
            tmp_path,
            monkeypatch,
            runtime=preparation_runtime,
        )
    )
    monkeypatch.setattr(
        vina_execution_module,
        "_load_vina_runtime",
        lambda _scratch_root: vina_runtime,
    )
    receipt = materialize_posebusters_vina_execution(
        preparation_path,
        preparation_artifact_root,
        tmp_path / "vina-poses",
        tmp_path / "vina-scratch",
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )

    first, second = receipt.case_rows
    assert first.status == first_status
    assert first.pose_artifact is None
    assert second.status == "abstain_chemistry_scope"
    assert receipt.success_case_count == 0
    assert receipt.engine_failure_case_count == int(first_status == "engine_failure")
    assert receipt.attempted_case_count == int(first_status == "engine_failure")
    assert not tuple((tmp_path / "vina-poses").iterdir())


def _external_binary_pose_output(engine_id: str) -> bytes:
    score_rows = (
        b"REMARK minimizedAffinity -7.000\n"
        if engine_id == "smina"
        else (
            b"REMARK minimizedAffinity -7.000\n"
            b"REMARK CNNscore 0.900\n"
            b"REMARK CNNaffinity 6.100\n"
        )
    )
    return (
        b"MODEL 1\n"
        + score_rows
        + b"ROOT\n"
        + b"ATOM      1  C   LIG A   1       0.000   0.000   0.000  0.00  0.00      0.000 C\n"
        + b"ENDROOT\n"
        + b"TORSDOF 0\n"
        + b"ENDMDL\n"
    )


def _fake_external_binary_identity(
    engine_id: str = "smina",
) -> PoseBustersExternalBinaryRuntimeIdentity:
    spec = external_binary_module._ENGINE_SPECS[engine_id]
    dependencies = ()
    if engine_id == "gnina":
        dependencies = tuple(
            external_binary_module.PoseBustersExternalBinaryDependency(
                requested_name=name,
                payload_name=name,
                sha256=_sha(f"fake {name}".encode("ascii")),
                size_bytes=len(name),
            )
            for name in external_binary_module._GNINA_REQUIRED_LIBRARIES
        )
    return PoseBustersExternalBinaryRuntimeIdentity(
        engine_id=engine_id,
        engine_version=spec["version"],
        version_output=spec["version_output"],
        executable_sha256=spec["executable_sha256"],
        executable_size_bytes=spec["executable_size_bytes"],
        source_url=spec["source_url"],
        source_release_date=spec["source_release_date"],
        dynamic_dependencies=dependencies,
        platform_system="Linux",
        platform_machine="x86_64",
        libc_name="glibc",
        libc_version="2.35",
    )


class _SuccessfulExternalBinaryRuntime:
    identity = _fake_external_binary_identity()

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> external_binary_module._ExternalExecutionBytes:
        assert receptor_pdbqt
        assert ligand_pdbqt
        assert len(pocket_center_binary64_hex) == 3
        poses = _external_binary_pose_output("smina")
        return external_binary_module._ExternalExecutionBytes(
            poses_pdbqt=poses,
            pose_scores=external_binary_module._parse_pose_output(
                "smina",
                poses,
            ),
            diagnostic_sha256=_sha(b"bounded Smina diagnostic"),
            diagnostic_size_bytes=len(b"bounded Smina diagnostic"),
        )


class _FailingExternalBinaryRuntime:
    identity = _fake_external_binary_identity()

    def execute(
        self,
        receptor_pdbqt: bytes,
        ligand_pdbqt: bytes,
        pocket_center_binary64_hex: tuple[str, ...],
    ) -> external_binary_module._ExternalExecutionBytes:
        assert receptor_pdbqt
        assert ligand_pdbqt
        assert len(pocket_center_binary64_hex) == 3
        raise PoseBustersExternalBinaryCaseError(
            stage="engine_execution",
            error_code="smina_execution_failed",
            error_type="RuntimeError",
            error_message_sha256=_sha(b"bounded Smina failure"),
            diagnostic_sha256=_sha(b"bounded Smina diagnostic"),
            diagnostic_size_bytes=len(b"bounded Smina diagnostic"),
        )


def test_external_binary_execution_materializes_all_rows_and_exact_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, preparation_artifact_root, preparation = (
        _materialize_fake_preparation(
            tmp_path,
            monkeypatch,
            runtime=_SuccessfulExternalPreparationRuntime(),
        )
    )
    monkeypatch.setattr(
        external_binary_module,
        "_load_runtime",
        lambda *_args: _SuccessfulExternalBinaryRuntime(),
    )
    output_artifact_root = tmp_path / "smina-poses"
    scratch_root = tmp_path / "smina-scratch"
    executable_path = tmp_path / "official-smina.static"
    common = {
        "engine_id": "smina",
        "preparation_receipt_path": preparation_path,
        "preparation_artifact_root": preparation_artifact_root,
        "output_artifact_root": output_artifact_root,
        "scratch_root": scratch_root,
        "executable_path": executable_path,
        "expected_preparation_receipt_sha256": (preparation.fingerprint_sha256),
    }

    receipt = materialize_posebusters_external_binary_execution(**common)

    assert (
        receipt.configuration_sha256
        == (POSEBUSTERS_EXTERNAL_BINARY_CONFIGURATION_SHA256["smina"])
    )
    assert receipt.attempted_case_count == 1
    assert receipt.success_case_count == 1
    assert receipt.engine_failure_case_count == 0
    assert receipt.generated_pose_count == 1
    first, second = receipt.case_rows
    assert first.status == "success"
    assert first.pose_scores[0].components_binary64_hex == ((-7.0).hex(),)
    assert second.status == "abstain_chemistry_scope"
    metrics = {metric.metric_id: metric for metric in receipt.metrics}
    assert metrics["smina_engine_success_rate"].numerator == 1
    assert metrics["generated_pose_validity_evaluation_rate"].numerator == 0
    pose_path = output_artifact_root / first.pose_artifact.relative_path
    assert stat.S_IMODE(output_artifact_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(pose_path.stat().st_mode) == 0o600
    assert pose_path.read_bytes() == _external_binary_pose_output("smina")
    payload = receipt.to_dict()
    assert payload["smina_same_input_execution_performed"] is True
    assert payload["gnina_same_input_execution_performed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    receipt_path = tmp_path / "receipts" / "smina-execution.json"
    receipt.write_json(receipt_path)
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    verified = verify_posebusters_external_binary_execution_receipt(
        execution_receipt_path=receipt_path,
        **common,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersExternalBinaryExecutionError,
        match="already exists",
    ):
        receipt.write_json(receipt_path)

    pose_path.write_bytes(pose_path.read_bytes() + b"tamper")
    with pytest.raises(
        PoseBustersExternalBinaryExecutionError,
        match="artifact tree does not match exact reexecution",
    ):
        verify_posebusters_external_binary_execution_receipt(
            execution_receipt_path=receipt_path,
            **common,
        )


def test_external_binary_execution_retains_engine_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, preparation_artifact_root, preparation = (
        _materialize_fake_preparation(
            tmp_path,
            monkeypatch,
            runtime=_SuccessfulExternalPreparationRuntime(),
        )
    )
    monkeypatch.setattr(
        external_binary_module,
        "_load_runtime",
        lambda *_args: _FailingExternalBinaryRuntime(),
    )

    receipt = materialize_posebusters_external_binary_execution(
        "smina",
        preparation_path,
        preparation_artifact_root,
        tmp_path / "smina-failure-poses",
        tmp_path / "smina-failure-scratch",
        tmp_path / "official-smina.static",
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )

    first, second = receipt.case_rows
    assert first.status == "engine_failure"
    assert first.error_code == "smina_execution_failed"
    assert first.pose_artifact is None
    assert second.status == "abstain_chemistry_scope"
    assert receipt.attempted_case_count == 1
    assert receipt.success_case_count == 0
    assert receipt.engine_failure_case_count == 1
    assert not tuple((tmp_path / "smina-failure-poses").iterdir())


def test_external_binary_pose_parser_and_smina_timing_normalization(
    tmp_path: Path,
) -> None:
    smina_scores = external_binary_module._parse_pose_output(
        "smina",
        _external_binary_pose_output("smina"),
    )
    gnina_scores = external_binary_module._parse_pose_output(
        "gnina",
        _external_binary_pose_output("gnina"),
    )

    assert smina_scores[0].components_binary64_hex == ((-7.0).hex(),)
    assert gnina_scores[0].components_binary64_hex == tuple(
        value.hex() for value in (-7.0, 0.9, 6.1)
    )
    runtime = external_binary_module._ExternalBinaryRuntime(
        engine_id="smina",
        executable_path=tmp_path / "smina.static",
        library_dirs=(),
        identity=_fake_external_binary_identity(),
        scratch_root=tmp_path / "diagnostic-scratch",
    )
    assert (
        runtime._diagnostic(
            b"Refine time 10.274\nLoop time 10.855\nkept\n",
            (),
        )
        == b"Refine time <SECONDS>\nLoop time <SECONDS>\nkept\n"
    )
    diagnostic = (
        b'Parse error on line 22 in file "<LIGAND>": ATOM syntax incorrect: '
        b'"CG0" is not a valid AutoDock type.\n'
    )
    failure = external_binary_module._classified_execution_failure(
        "gnina",
        1,
        diagnostic,
    )
    assert failure.stage == "engine_input_validation"
    assert failure.error_code == ("gnina_unsupported_prepared_autodock_atom_type")
    assert failure.error_type == "UnsupportedPreparedAutoDockAtomType"
    assert failure.diagnostic_sha256 == _sha(diagnostic)

    fallback = external_binary_module._classified_execution_failure(
        "smina",
        7,
        b"unclassified failure\n",
    )
    assert fallback.stage == "engine_execution"
    assert fallback.error_code == "smina_execution_failed"
    assert fallback.error_type == "CalledProcessError"


def _fake_generated_pose_runtime_identity() -> PoseBustersGeneratedPoseRuntimeIdentity:
    dependencies = tuple(
        PoseBustersExternalPreparationDependency(
            distribution_name=name,
            version=version,
            payload_sha256=_sha(f"fake {name} payload".encode("ascii")),
            payload_file_count=1,
            payload_size_bytes=len(name) + 16,
        )
        for name, version in sorted(
            generated_pose_module.POSEBUSTERS_GENERATED_POSE_DEPENDENCY_PINS.items()
        )
    )
    return PoseBustersGeneratedPoseRuntimeIdentity(
        preparation_runtime=_fake_external_preparation_runtime(),
        additional_dependencies=dependencies,
        posebusters_wheel_sha256=(
            generated_pose_module.POSEBUSTERS_GENERATED_POSE_WHEEL_SHA256
        ),
        posebusters_wheel_size_bytes=(
            generated_pose_module.POSEBUSTERS_GENERATED_POSE_WHEEL_SIZE_BYTES
        ),
        redock_configuration_sha256=(
            generated_pose_module.POSEBUSTERS_GENERATED_POSE_REDOCK_CONFIGURATION_SHA256
        ),
        posebusters_api_source_sha256=_sha(b"fake PoseBusters API source"),
        meeko_export_source_sha256=_sha(b"fake Meeko export source"),
    )


def _fake_generated_pose_report_values() -> tuple[
    PoseBustersGeneratedPoseReportValue,
    ...,
]:
    rows = [
        PoseBustersGeneratedPoseReportValue(
            ordinal=ordinal,
            source_name=source_name,
            output_id=generated_pose_module._output_id(source_name),
            occurrence=0,
            value_type="boolean",
            value=True,
        )
        for ordinal, source_name in enumerate(
            POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
        )
    ]
    for source_name, value in (
        ("rmsd", 1.5),
        ("kabsch_rmsd", 1.25),
        ("centroid_distance", 0.5),
        ("energy_ratio", 1.1),
    ):
        rows.append(
            PoseBustersGeneratedPoseReportValue(
                ordinal=len(rows),
                source_name=source_name,
                output_id=source_name,
                occurrence=0,
                value_type="binary64",
                value=value.hex(),
            )
        )
    return tuple(rows)


def _successful_internal_oracle_outcome(
) -> generated_pose_module._RuntimePoseOutcome:
    return generated_pose_module._RuntimePoseOutcome(
        status="evaluated",
        report_values=_fake_generated_pose_report_values(),
        all_non_rmsd_binary_tests_pass=True,
        identity_pass=True,
        intramolecular_geometry_pass=True,
        internal_energy_pass=True,
        intermolecular_distance_and_overlap_pass=True,
        rmsd_evaluated=True,
        rmsd_within_2_angstrom=True,
        direct_rmsd_angstrom_binary64_hex=(1.5).hex(),
        kabsch_rmsd_angstrom_binary64_hex=(1.25).hex(),
        centroid_distance_angstrom_binary64_hex=(0.5).hex(),
        energy_ratio_binary64_hex=(1.1).hex(),
        diagnostic_sha256=_sha(b"fake internal oracle diagnostic"),
        diagnostic_size_bytes=len(b"fake internal oracle diagnostic"),
    )


def _failed_internal_oracle_outcome(
) -> generated_pose_module._RuntimePoseOutcome:
    return generated_pose_module._RuntimePoseOutcome(
        status="evaluation_failure",
        error_stage="posebusters_redock",
        error_code="posebusters_pose_evaluation_failed",
        error_type="RuntimeError",
        error_message_sha256=_sha(b"bounded internal-oracle failure"),
        diagnostic_sha256=_sha(b"bounded internal-oracle diagnostic"),
        diagnostic_size_bytes=len(b"bounded internal-oracle diagnostic"),
    )


class _InternalOracleRuntime:
    identity = _fake_generated_pose_runtime_identity()

    def __init__(
        self,
        outcomes: tuple[generated_pose_module._RuntimePoseOutcome, ...],
    ) -> None:
        self._outcomes = outcomes
        self.calls = 0

    def evaluate_prepared_coordinate_case(
        self,
        ligand_start_sdf: bytes,
        source_atom_to_prepared_atom: tuple[int, ...],
        pose_coordinates_angstrom: list[list[list[float]]],
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
    ) -> tuple[generated_pose_module._RuntimePoseOutcome, ...]:
        self.calls += 1
        assert ligand_start_sdf
        assert receptor_pdb
        assert reference_ligands_sdf
        assert source_atom_to_prepared_atom
        assert len(set(source_atom_to_prepared_atom)) == len(
            source_atom_to_prepared_atom
        )
        assert len(pose_coordinates_angstrom) == len(self._outcomes)
        assert all(
            len(source_atom_to_prepared_atom) == len(coordinates)
            and max(source_atom_to_prepared_atom) < len(coordinates)
            for coordinates in pose_coordinates_angstrom
        )
        return self._outcomes


class _FailingInternalOracleAdapterRuntime:
    identity = _fake_generated_pose_runtime_identity()

    def evaluate_prepared_coordinate_case(
        self,
        ligand_start_sdf: bytes,
        source_atom_to_prepared_atom: tuple[int, ...],
        pose_coordinates_angstrom: list[list[list[float]]],
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
    ) -> tuple[generated_pose_module._RuntimePoseOutcome, ...]:
        assert ligand_start_sdf
        assert source_atom_to_prepared_atom
        assert pose_coordinates_angstrom
        assert receptor_pdb
        assert reference_ligands_sdf
        diagnostic = b"bounded internal coordinate reconstruction failure"
        raise generated_pose_module.PoseBustersGeneratedPoseCaseError(
            stage="internal_coordinate_reconstruction",
            error_code="internal_pose_reconstruction_failed",
            error_type="ValueError",
            error_message_sha256=_sha(diagnostic),
            diagnostic_sha256=_sha(diagnostic),
            diagnostic_size_bytes=len(diagnostic),
        )


class _SuccessfulGeneratedPoseRuntime:
    identity = _fake_generated_pose_runtime_identity()

    def evaluate_case(
        self,
        poses_pdbqt: bytes,
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
        expected_pose_count: int,
    ) -> tuple[generated_pose_module._RuntimePoseOutcome, ...]:
        assert poses_pdbqt
        assert receptor_pdb
        assert reference_ligands_sdf
        assert expected_pose_count == 1
        return (
            generated_pose_module._RuntimePoseOutcome(
                status="evaluated",
                report_values=_fake_generated_pose_report_values(),
                all_non_rmsd_binary_tests_pass=True,
                identity_pass=True,
                intramolecular_geometry_pass=True,
                internal_energy_pass=True,
                intermolecular_distance_and_overlap_pass=True,
                rmsd_evaluated=True,
                rmsd_within_2_angstrom=True,
                direct_rmsd_angstrom_binary64_hex=(1.5).hex(),
                kabsch_rmsd_angstrom_binary64_hex=(1.25).hex(),
                centroid_distance_angstrom_binary64_hex=(0.5).hex(),
                energy_ratio_binary64_hex=(1.1).hex(),
                diagnostic_sha256=_sha(b"fake PoseBusters diagnostic"),
                diagnostic_size_bytes=len(b"fake PoseBusters diagnostic"),
            ),
        )


class _FailingGeneratedPoseRuntime:
    identity = _fake_generated_pose_runtime_identity()

    def evaluate_case(
        self,
        poses_pdbqt: bytes,
        receptor_pdb: bytes,
        reference_ligands_sdf: bytes,
        expected_pose_count: int,
    ) -> tuple[generated_pose_module._RuntimePoseOutcome, ...]:
        assert poses_pdbqt
        assert receptor_pdb
        assert reference_ligands_sdf
        assert expected_pose_count == 1
        return (
            generated_pose_module._RuntimePoseOutcome(
                status="evaluation_failure",
                error_stage="posebusters_redock",
                error_code="posebusters_pose_evaluation_failed",
                error_type="RuntimeError",
                error_message_sha256=_sha(b"bounded generated-pose failure"),
                diagnostic_sha256=_sha(b"bounded generated-pose diagnostic"),
                diagnostic_size_bytes=len(b"bounded generated-pose diagnostic"),
            ),
        )


def _materialize_fake_generated_pose_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], object, object]:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    preparation_runtime = _SuccessfulExternalPreparationRuntime()
    monkeypatch.setattr(
        external_preparation_module,
        "_load_meeko_runtime",
        lambda: preparation_runtime,
    )
    preparation_artifact_root = tmp_path / "prepared"
    preparation = materialize_posebusters_external_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        preparation_artifact_root,
        contract=contract,
    )
    preparation_path = tmp_path / "receipts" / "preparation.json"
    preparation.write_json(preparation_path)
    monkeypatch.setattr(
        vina_execution_module,
        "_load_vina_runtime",
        lambda _scratch_root: _SuccessfulVinaRuntime(),
    )
    vina_artifact_root = tmp_path / "vina-poses"
    vina = materialize_posebusters_vina_execution(
        preparation_path,
        preparation_artifact_root,
        vina_artifact_root,
        tmp_path / "vina-scratch",
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )
    vina_path = tmp_path / "receipts" / "vina.json"
    vina.write_json(vina_path)
    wheel_path = tmp_path / "posebusters-0.6.5-py3-none-any.whl"
    common: dict[str, object] = {
        "archive_path": archive_path,
        "selection_path": selection_path,
        "intake_receipt_path": intake_path,
        "corpus_audit_receipt_path": corpus_path,
        "preparation_receipt_path": preparation_path,
        "preparation_artifact_root": preparation_artifact_root,
        "vina_receipt_path": vina_path,
        "vina_artifact_root": vina_artifact_root,
        "posebusters_wheel_path": wheel_path,
        "scratch_root": tmp_path / "posebusters-scratch",
        "expected_preparation_receipt_sha256": (preparation.fingerprint_sha256),
        "expected_vina_receipt_sha256": vina.fingerprint_sha256,
        "contract": contract,
    }
    return common, preparation, vina


def test_generated_pose_evaluation_retains_all_rows_metrics_and_exact_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common, _preparation, _vina = _materialize_fake_generated_pose_chain(
        tmp_path,
        monkeypatch,
    )
    monkeypatch.setattr(
        generated_pose_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: _SuccessfulGeneratedPoseRuntime(),
    )

    receipt = materialize_posebusters_generated_pose_evaluation(**common)

    assert receipt.configuration_sha256 == (
        POSEBUSTERS_GENERATED_POSE_CONFIGURATION_SHA256
    )
    assert receipt.generated_pose_count == 1
    assert receipt.evaluated_pose_count == 1
    assert receipt.physically_valid_pose_count == 1
    first, second = receipt.case_rows
    assert first.status == "evaluated"
    assert first.top_1_valid_rmsd_hit is True
    assert first.pose_results[0].report_sha256
    assert second.status == "abstain_chemistry_scope"
    metrics = {
        (metric.metric_id, metric.denominator_scope): metric
        for metric in receipt.metrics
    }
    assert (
        metrics[("posebusters_complete_case_evaluation_rate", "all_cases")].numerator
        == 1
    )
    assert (
        metrics[("top_1_rmsd_le_2_angstrom_rate", "vina_success_cases")].numerator == 1
    )
    assert metrics[("physically_valid_pose_rate", "generated_poses")].numerator == 1
    payload = receipt.to_dict()
    assert payload["posebusters_redock_oracle_executed"] is True
    assert payload["benchmark_executed"] is False
    assert payload["scientifically_validated"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "receipts" / "generated-pose-evaluation.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_generated_pose_evaluation_receipt(
        evaluation_receipt_path=output,
        **common,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersGeneratedPoseEvaluationError,
        match="already exists",
    ):
        receipt.write_json(output)
    output.write_bytes(
        output.read_bytes().replace(
            b'"claim_safe":false',
            b'"claim_safe":true',
        )
    )
    with pytest.raises(
        PoseBustersGeneratedPoseEvaluationError,
        match="exact reexecution",
    ):
        verify_posebusters_generated_pose_evaluation_receipt(
            evaluation_receipt_path=output,
            **common,
        )


def test_generated_pose_evaluation_retains_pose_failure_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common, _preparation, _vina = _materialize_fake_generated_pose_chain(
        tmp_path,
        monkeypatch,
    )
    monkeypatch.setattr(
        generated_pose_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: _FailingGeneratedPoseRuntime(),
    )

    receipt = materialize_posebusters_generated_pose_evaluation(**common)

    first, second = receipt.case_rows
    assert first.status == "evaluation_failure"
    assert first.pose_results[0].status == "evaluation_failure"
    assert first.pose_results[0].error_code == ("posebusters_pose_evaluation_failed")
    assert second.status == "abstain_chemistry_scope"
    metrics = {
        (metric.metric_id, metric.denominator_scope): metric
        for metric in receipt.metrics
    }
    assert (
        metrics[("posebusters_case_evaluation_failure_rate", "all_cases")].numerator
        == 1
    )
    assert metrics[("pose_evaluation_success_rate", "generated_poses")].numerator == 0


def _materialize_fake_external_generated_pose_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    execution_runtime: object,
) -> tuple[dict[str, object], object, object]:
    archive_path, selection_path, intake_path, contract = _fixture(tmp_path / "source")
    corpus = materialize_posebusters_corpus_audit(
        archive_path,
        selection_path,
        intake_path,
        contract=contract,
    )
    corpus_path = tmp_path / "receipts" / "corpus.json"
    corpus.write_json(corpus_path)
    monkeypatch.setattr(
        external_preparation_module,
        "_load_meeko_runtime",
        lambda: _SuccessfulExternalPreparationRuntime(),
    )
    preparation_artifact_root = tmp_path / "prepared"
    preparation = materialize_posebusters_external_preparation(
        archive_path,
        selection_path,
        intake_path,
        corpus_path,
        preparation_artifact_root,
        contract=contract,
    )
    preparation_path = tmp_path / "receipts" / "preparation.json"
    preparation.write_json(preparation_path)
    monkeypatch.setattr(
        external_binary_module,
        "_load_runtime",
        lambda *_args: execution_runtime,
    )
    execution_artifact_root = tmp_path / "smina-poses"
    execution = materialize_posebusters_external_binary_execution(
        "smina",
        preparation_path,
        preparation_artifact_root,
        execution_artifact_root,
        tmp_path / "smina-scratch",
        tmp_path / "official-smina.static",
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )
    execution_path = tmp_path / "receipts" / "smina-execution.json"
    execution.write_json(execution_path)
    common: dict[str, object] = {
        "engine_id": "smina",
        "archive_path": archive_path,
        "selection_path": selection_path,
        "intake_receipt_path": intake_path,
        "corpus_audit_receipt_path": corpus_path,
        "preparation_receipt_path": preparation_path,
        "preparation_artifact_root": preparation_artifact_root,
        "execution_receipt_path": execution_path,
        "execution_artifact_root": execution_artifact_root,
        "posebusters_wheel_path": (
            tmp_path / "posebusters-0.6.5-py3-none-any.whl"
        ),
        "scratch_root": tmp_path / "external-posebusters-scratch",
        "expected_preparation_receipt_sha256": (
            preparation.fingerprint_sha256
        ),
        "expected_execution_receipt_sha256": execution.fingerprint_sha256,
        "contract": contract,
    }
    return common, preparation, execution


def test_external_generated_pose_evaluation_retains_scores_and_exact_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    common, _preparation, _execution = (
        _materialize_fake_external_generated_pose_chain(
            tmp_path,
            monkeypatch,
            execution_runtime=_SuccessfulExternalBinaryRuntime(),
        )
    )
    monkeypatch.setattr(
        external_generated_pose_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: _SuccessfulGeneratedPoseRuntime(),
    )

    receipt = materialize_posebusters_external_generated_pose_evaluation(
        **common
    )

    assert receipt.engine_id == "smina"
    assert receipt.generated_pose_count == 1
    assert receipt.evaluated_pose_count == 1
    assert receipt.physically_valid_pose_count == 1
    first, second = receipt.case_rows
    assert first.status == "evaluated"
    assert first.top_1_valid_rmsd_hit is True
    assert first.pose_results[0].score_components_binary64_hex == (
        (-7.0).hex(),
    )
    assert first.pose_results[0].report_sha256
    assert second.status == "abstain_chemistry_scope"
    metrics = {
        (metric.metric_id, metric.denominator_scope): metric
        for metric in receipt.metrics
    }
    assert metrics[("top_1_rmsd_le_2_angstrom_rate", "all_cases")].denominator == 2
    assert (
        metrics[("top_1_rmsd_le_2_angstrom_rate", "smina_success_cases")].numerator
        == 1
    )
    assert metrics[("physically_valid_pose_rate", "generated_poses")].numerator == 1
    payload = receipt.to_dict()
    assert payload["score_component_order"] == [
        "minimized_affinity_kcal_per_mol"
    ]
    assert payload["posebusters_redock_oracle_executed"] is True
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "receipts" / "smina-posebusters.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_external_generated_pose_evaluation_receipt(
        evaluation_receipt_path=output,
        **common,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    output.write_bytes(
        output.read_bytes().replace(
            b'"claim_safe":false',
            b'"claim_safe":true',
        )
    )
    with pytest.raises(
        PoseBustersExternalGeneratedPoseEvaluationError,
        match="exact reexecution",
    ):
        verify_posebusters_external_generated_pose_evaluation_receipt(
            evaluation_receipt_path=output,
            **common,
        )


@pytest.mark.parametrize(
    ("execution_runtime", "evaluation_runtime", "expected_status"),
    (
        (
            _SuccessfulExternalBinaryRuntime(),
            _FailingGeneratedPoseRuntime(),
            "evaluation_failure",
        ),
        (
            _FailingExternalBinaryRuntime(),
            _SuccessfulGeneratedPoseRuntime(),
            "blocked_engine_failure",
        ),
    ),
)
def test_external_generated_pose_evaluation_retains_failure_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    execution_runtime: object,
    evaluation_runtime: object,
    expected_status: str,
) -> None:
    common, _preparation, _execution = (
        _materialize_fake_external_generated_pose_chain(
            tmp_path,
            monkeypatch,
            execution_runtime=execution_runtime,
        )
    )
    monkeypatch.setattr(
        external_generated_pose_module,
        "_load_posebusters_runtime",
        lambda _scratch_root, _wheel_path: evaluation_runtime,
    )

    receipt = materialize_posebusters_external_generated_pose_evaluation(
        **common
    )

    first, second = receipt.case_rows
    assert first.status == expected_status
    assert second.status == "abstain_chemistry_scope"
    if expected_status == "evaluation_failure":
        assert first.pose_results[0].error_code == (
            "posebusters_pose_evaluation_failed"
        )
    else:
        assert first.execution_error_code == "smina_execution_failed"
        assert not first.pose_results


def test_generated_pose_runtime_batches_all_case_conformers(
    tmp_path: Path,
) -> None:
    class _Columns:
        def __init__(self, values: tuple[str, ...]) -> None:
            self._values = values

        def tolist(self) -> list[str]:
            return list(self._values)

    class _ReportRow:
        def __init__(self, values: tuple[object, ...]) -> None:
            self._values = values

        def tolist(self) -> list[object]:
            return list(self._values)

    class _ILoc:
        def __init__(self, rows: tuple[tuple[object, ...], ...]) -> None:
            self._rows = rows

        def __getitem__(self, index: int) -> _ReportRow:
            return _ReportRow(self._rows[index])

    class _Report:
        def __init__(
            self,
            columns: tuple[str, ...],
            rows: tuple[tuple[object, ...], ...],
        ) -> None:
            self.columns = _Columns(columns)
            self.iloc = _ILoc(rows)
            self.shape = (len(rows), len(columns))

    columns = (
        *POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS,
        "rmsd",
        "kabsch_rmsd",
        "centroid_distance",
        "energy_ratio",
    )
    report_rows = tuple(
        (
            *(
                (rmsd <= 2.0 if name == "rmsd_≤_2å" else True)
                for name in POSEBUSTERS_GENERATED_POSE_SELECTED_COLUMNS
            ),
            rmsd,
            rmsd - 0.1,
            0.25,
            1.05,
        )
        for rmsd in (1.0, 3.0)
    )

    class _BatchEngine:
        calls: list[int] = []
        coordinate_rows: list[tuple[tuple[float, float, float], ...]] = []

        def __init__(self, *, config: str, max_workers: int) -> None:
            assert config == "redock"
            assert max_workers == 0

        def bust(
            self,
            poses: list[object],
            *,
            mol_true: Path,
            mol_cond: Path,
            full_report: bool,
        ) -> _Report:
            assert mol_true.is_file()
            assert mol_cond.is_file()
            assert full_report is True
            self.calls.append(len(poses))
            for pose in poses:
                conformer = getattr(pose, "coordinate_conformer", None)
                if conformer is not None:
                    self.coordinate_rows.append(tuple(conformer.positions))
            return _Report(columns, report_rows)

    class _PDBQTMolecule:
        def __init__(self, source: str, *, skip_typing: bool) -> None:
            assert source == "MODEL 1\nENDMDL\n"
            assert skip_typing is True

    class _Molecule:
        def GetNumConformers(self) -> int:
            return 2

        def GetConformer(self, index: int) -> object:
            assert index in (0, 1)
            return object()

    class _RDKitMolCreate:
        @staticmethod
        def from_pdbqt_mol(
            _molecule: object,
            *,
            only_cluster_leads: bool,
            keep_flexres: bool,
        ) -> list[_Molecule]:
            assert only_cluster_leads is False
            assert keep_flexres is False
            return [_Molecule()]

    class _CoordinateConformer:
        def __init__(self, atom_count: int) -> None:
            self.positions = [(0.0, 0.0, 0.0)] * atom_count

        def SetAtomPosition(
            self,
            index: int,
            value: tuple[float, float, float],
        ) -> None:
            self.positions[index] = value

    class _SourceMolecule:
        def GetNumAtoms(self) -> int:
            return 2

    class _Pose:
        def __init__(self) -> None:
            self._conformer_count = 0
            self.coordinate_conformer: _CoordinateConformer | None = None

        def RemoveAllConformers(self) -> None:
            self._conformer_count = 0

        def AddConformer(self, conformer: object, *, assignId: bool) -> int:
            assert assignId is True
            self._conformer_count = 1
            if isinstance(conformer, _CoordinateConformer):
                self.coordinate_conformer = conformer
            return 0

        def GetNumConformers(self) -> int:
            return self._conformer_count

    class _Chem:
        @staticmethod
        def MolFromMolBlock(
            _source: str,
            *,
            sanitize: bool,
            removeHs: bool,
            strictParsing: bool,
        ) -> _SourceMolecule:
            assert sanitize is True
            assert removeHs is False
            assert strictParsing is True
            return _SourceMolecule()

        @staticmethod
        def Mol(_molecule: object) -> _Pose:
            return _Pose()

        @staticmethod
        def Conformer(conformer: object) -> object:
            return (
                _CoordinateConformer(conformer)
                if isinstance(conformer, int)
                else conformer
            )

    class _Numpy:
        bool_ = bool
        integer = int
        floating = float

    class _Pandas:
        NA = object()

        @staticmethod
        def isna(_value: object) -> bool:
            return False

    runtime = generated_pose_module._PoseBustersRuntime(
        PoseBusters=_BatchEngine,
        PDBQTMolecule=_PDBQTMolecule,
        RDKitMolCreate=_RDKitMolCreate,
        Chem=_Chem,
        numpy_module=_Numpy,
        pandas_module=_Pandas,
        identity=_fake_generated_pose_runtime_identity(),
        scratch_root=tmp_path / "batch-scratch",
    )

    outcomes = runtime.evaluate_case(
        b"MODEL 1\nENDMDL\n",
        b"END\n",
        b"M  END\n$$$$\n",
        2,
    )

    assert _BatchEngine.calls == [2]
    assert tuple(row.status for row in outcomes) == ("evaluated", "evaluated")
    assert tuple(row.rmsd_within_2_angstrom for row in outcomes) == (True, False)
    assert all(row.intramolecular_geometry_pass for row in outcomes)
    assert all(row.intermolecular_distance_and_overlap_pass for row in outcomes)

    coordinate_outcomes = runtime.evaluate_prepared_coordinate_case(
        b"synthetic\n$$$$\n",
        (1, 0),
        (
            ((10.0, 0.0, 0.0), (20.0, 0.0, 0.0)),
            ((30.0, 1.0, 0.0), (40.0, 1.0, 0.0)),
        ),
        b"END\n",
        b"M  END\n$$$$\n",
    )

    assert _BatchEngine.calls == [2, 2]
    assert _BatchEngine.coordinate_rows == [
        ((20.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
        ((40.0, 1.0, 0.0), (30.0, 1.0, 0.0)),
    ]
    assert tuple(row.status for row in coordinate_outcomes) == (
        "evaluated",
        "evaluated",
    )

    with pytest.raises(
        generated_pose_module.PoseBustersGeneratedPoseCaseError,
        match="internal_pose_reconstruction_failed",
    ):
        runtime.evaluate_prepared_coordinate_case(
            b"synthetic\n$$$$\n",
            (1, 0),
            (((10.0, 0.0, 0.0), (20.0, 0.0, 0.0), (30.0, 0.0, 0.0)),),
            b"END\n",
            b"M  END\n$$$$\n",
        )
    assert _BatchEngine.calls == [2, 2]


def _target_cluster_receptor(residue_labels: tuple[str, ...]) -> bytes:
    rows = []
    for residue_index, residue_label in enumerate(residue_labels, start=1):
        rows.append(
            f"{'ATOM':<6}{residue_index:5d} {'CA':<4}{'':1}"
            f"{residue_label:>3} {'A':1}{residue_index:4d}{'':1}   "
            f"{float(residue_index):8.3f}{0.0:8.3f}{0.0:8.3f}"
            f"{1.0:6.2f}{10.0:6.2f}          {'C':>2}{'':>2}"
        )
    rows.append("END")
    return ("\n".join(rows) + "\n").encode("ascii")


def _write_target_cluster_evaluation_receipt(
    path: Path,
    *,
    engine: str,
    archive_intake_receipt_sha256: str,
) -> str:
    if engine == "vina":
        schema_id = generated_pose_module.POSEBUSTERS_GENERATED_POSE_EVALUATION_SCHEMA_ID
        case_schema_id = generated_pose_module.POSEBUSTERS_GENERATED_POSE_CASE_SCHEMA_ID
        source_role = "generated_pose_evaluation"
        source_path = Path(generated_pose_module.__file__)
        execution_receipt_key = "vina_receipt_sha256"
        execution_status_key = "vina_status"
        execution_pose_count_key = "vina_pose_count"
    else:
        schema_id = (
            external_generated_pose_module.
            POSEBUSTERS_EXTERNAL_GENERATED_POSE_EVALUATION_SCHEMA_ID
        )
        case_schema_id = (
            external_generated_pose_module.
            POSEBUSTERS_EXTERNAL_GENERATED_POSE_CASE_SCHEMA_ID
        )
        source_role = "external_generated_pose_evaluation"
        source_path = Path(external_generated_pose_module.__file__)
        execution_receipt_key = "execution_receipt_sha256"
        execution_status_key = "execution_status"
        execution_pose_count_key = "execution_pose_count"
    source_members = {source_role: _sha(source_path.read_bytes())}
    case_rows = []
    for index, case_id in enumerate(_CASE_IDS):
        hit = (engine, index) in {("vina", 0), ("smina", 1)}
        row = {
            "schema_id": case_schema_id,
            "case_id": case_id,
            execution_status_key: "success",
            execution_pose_count_key: 1,
            "status": "evaluated",
            "evaluated_pose_count": 1,
            "physically_valid_pose_count": int(hit),
            "top_1_valid": hit,
            "top_5_valid": hit,
            "top_1_rmsd_within_2_angstrom": hit,
            "top_5_rmsd_within_2_angstrom": hit,
            "top_1_valid_and_rmsd_within_2_angstrom": hit,
            "top_5_valid_and_rmsd_within_2_angstrom": hit,
        }
        if engine != "vina":
            row["engine_id"] = engine
        case_rows.append(row)
    payload = {
        "schema_id": schema_id,
        "archive_intake_receipt_sha256": archive_intake_receipt_sha256,
        "corpus_audit_receipt_sha256": "1" * 64,
        "preparation_receipt_sha256": "2" * 64,
        execution_receipt_key: ("3" if engine == "vina" else "4") * 64,
        "implementation_source_members": source_members,
        "implementation_source_sha256": _canonical_sha(source_members),
        "all_case_denominator": len(_CASE_IDS),
        "generated_pose_count": len(_CASE_IDS),
        "evaluated_pose_count": len(_CASE_IDS),
        "case_rows": case_rows,
        "target_family_metrics_present": False,
        "leakage_receipt_present": False,
        "benchmark_executed": False,
        "scientifically_validated": False,
    }
    if engine == "vina":
        payload["claim_safe"] = False
    else:
        payload["engine_id"] = engine
    receipt_sha256 = _canonical_sha(payload)
    complete = {**payload, "receipt_sha256": receipt_sha256}
    source = json.dumps(
        complete,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii") + b"\n"
    path.write_bytes(source)
    path.chmod(0o600)
    return receipt_sha256


def _target_cluster_fixture(
    root: Path,
) -> tuple[dict[str, object], tuple[str, str, str]]:
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "posebusters-target-clusters.zip"
    selection_path = root / "selection.txt"
    intake_path = root / "intake.json"
    selection = ("\n".join(_CASE_IDS) + "\n").encode("ascii")
    selection_path.write_bytes(selection)
    readme = b"synthetic target-cluster fixture\n"
    sequences = (
        ("ALA",) * 20,
        ("ALA",) * 19 + ("GLY",),
    )
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("posebusters_benchmark_set_ids.txt", selection)
        for case_id, sequence in zip(_CASE_IDS, sequences):
            native = _ligand(
                explicit_hydrogen=False,
                stereo_code=1,
                charge=-1,
            )
            sources = {
                "receptor_pdb": _target_cluster_receptor(sequence),
                "reference_ligand_sdf": native,
                "reference_ligands_sdf": native,
                "ligand_start_conformer_sdf": native,
            }
            for role in POSEBUSTERS_ARCHIVE_MEMBER_ROLES:
                archive.writestr(
                    f"posebusters_benchmark_set/{case_id}/"
                    f"{case_id}{POSEBUSTERS_ARCHIVE_ROLE_SUFFIXES[role]}",
                    sources[role],
                )
    archive_source = archive_path.read_bytes()
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        uncompressed = sum(
            info.file_size for info in infos if not info.is_dir()
        )
    contract = PoseBustersArchiveContract(
        dataset_id="synthetic_posebusters_target_clusters",
        archive_sha256=_sha(archive_source),
        archive_size_bytes=len(archive_source),
        selection_sha256=_sha(selection),
        selection_size_bytes=len(selection),
        case_id_projection_sha256=_canonical_sha(list(_CASE_IDS)),
        selected_case_count=len(_CASE_IDS),
        archive_entry_count=len(infos),
        archive_uncompressed_size_bytes=uncompressed,
        archive_benchmark_case_count=len(_CASE_IDS),
        benchmark_root="posebusters_benchmark_set",
        embedded_case_list_member="posebusters_benchmark_set_ids.txt",
        embedded_case_list_sha256=_sha(selection),
        readme_member="README.txt",
        readme_sha256=_sha(readme),
    )
    intake = materialize_posebusters_archive_intake(
        archive_path,
        selection_path,
        contract=contract,
    )
    intake.write_json(intake_path)
    evaluation_paths = tuple(root / f"{engine}.json" for engine in ("vina", "gnina", "smina"))
    evaluation_hashes = tuple(
        _write_target_cluster_evaluation_receipt(
            path,
            engine=engine,
            archive_intake_receipt_sha256=intake.fingerprint_sha256,
        )
        for engine, path in zip(("vina", "gnina", "smina"), evaluation_paths)
    )
    common: dict[str, object] = {
        "archive_path": archive_path,
        "selection_path": selection_path,
        "intake_receipt_path": intake_path,
        "vina_evaluation_receipt_path": evaluation_paths[0],
        "gnina_evaluation_receipt_path": evaluation_paths[1],
        "smina_evaluation_receipt_path": evaluation_paths[2],
        "expected_vina_evaluation_receipt_sha256": evaluation_hashes[0],
        "expected_gnina_evaluation_receipt_sha256": evaluation_hashes[1],
        "expected_smina_evaluation_receipt_sha256": evaluation_hashes[2],
        "contract": contract,
    }
    return common, evaluation_hashes


def test_target_cluster_edit_distance_and_short_chain_fail_closed() -> None:
    assert target_cluster_module._global_edit_distance((), ("ALA",)) == 1
    assert target_cluster_module._global_edit_distance(
        ("ALA", "GLY", "SER"),
        ("ALA", "ASP", "SER", "TYR"),
    ) == 2
    assert target_cluster_module._global_edit_distance(
        ("ALA",) * 20,
        ("ALA",) * 19 + ("GLY",),
    ) == 1
    with pytest.raises(
        target_cluster_module.PoseBustersTargetClusterBindingError,
        match="no comparison-eligible protein chain",
    ):
        target_cluster_module._parse_observed_target_chains(
            "1ABC_ABC",
            _target_cluster_receptor(("ALA",) * 19),
        )


def test_target_cluster_similarity_threshold_is_exact() -> None:
    def observed(
        case_id: str,
        sequence: tuple[str, ...],
    ) -> object:
        receptor = _target_cluster_receptor(sequence)
        chains, sequences = target_cluster_module._parse_observed_target_chains(
            case_id,
            receptor,
        )
        return target_cluster_module._ObservedCasePayload(
            case_id=case_id,
            pdb_id=case_id.split("_", 1)[0],
            receptor_sha256=_sha(receptor),
            chains=chains,
            residue_label_sequences=sequences,
        )

    reference = observed("1ABC_ABC", ("ALA",) * 20)
    exact_threshold = observed(
        "2DEF_DEF",
        ("ALA",) * 18 + ("GLY", "SER"),
    )
    _cases, links, families = target_cluster_module._cluster_observed_cases(
        (reference, exact_threshold)
    )
    assert len(links) == 1
    assert links[0].edit_distance == 2
    assert len(families) == 1

    below_threshold = observed(
        "2DEF_DEF",
        ("ALA",) * 17 + ("GLY", "SER", "TYR"),
    )
    _cases, links, families = target_cluster_module._cluster_observed_cases(
        (reference, below_threshold)
    )
    assert links == ()
    assert len(families) == 2


def test_target_cluster_binding_groups_cases_and_reexecutes_exactly(
    tmp_path: Path,
) -> None:
    common, _evaluation_hashes = _target_cluster_fixture(tmp_path / "source")
    receipt = target_cluster_module.materialize_posebusters_target_cluster_binding(
        **common
    )

    assert len(receipt.case_rows) == 2
    assert len(receipt.family_rows) == 1
    assert receipt.family_rows[0].member_case_ids == _CASE_IDS
    assert len(receipt.cluster_links) == 1
    assert receipt.cluster_links[0].edit_distance == 1
    assert receipt.cluster_links[0].maximum_chain_length == 20
    assert all(
        row.fit_or_training_manifest_status == "missing"
        for row in receipt.leakage_dispositions
    )
    metrics = {
        (row.engine_id, row.metric_id, row.denominator_scope): row
        for row in receipt.metrics
    }
    assert metrics[
        ("vina", "target_cluster_coverage_rate", "all_target_clusters")
    ].numerator == 1
    assert metrics[
        (
            "vina",
            "covered_target_cluster_with_any_top_1_rmsd_hit_rate",
            "vina_covered_target_clusters",
        )
    ].numerator == 1
    assert metrics[
        (
            "gnina",
            "covered_target_cluster_with_any_top_1_rmsd_hit_rate",
            "gnina_covered_target_clusters",
        )
    ].numerator == 0
    payload = receipt.to_dict()
    assert payload["biological_target_family_annotations_present"] is False
    assert payload["external_fit_training_leakage_audit_present"] is False
    assert payload["leakage_control_passed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "target-clusters.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = (
        target_cluster_module.verify_posebusters_target_cluster_binding_receipt(
            target_cluster_receipt_path=output,
            **common,
        )
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    output.chmod(0o644)
    with pytest.raises(
        target_cluster_module.PoseBustersTargetClusterBindingError,
        match="must remain mode 0600",
    ):
        target_cluster_module.verify_posebusters_target_cluster_binding_receipt(
            target_cluster_receipt_path=output,
            **common,
        )


def _raw_rcsb_target_entry(
    pdb_id: str,
    *,
    asym_ids: tuple[str, ...] = ("A",),
    auth_asym_ids: tuple[str, ...] = ("AAA",),
    uniprot_id: str = "P00001",
    pfam_rows: tuple[tuple[str, str], ...] = (("PF00001", "Family one"),),
) -> dict[str, object]:
    return {
        "rcsb_id": pdb_id,
        "polymer_entities": [
            {
                "rcsb_id": f"{pdb_id}_1",
                "rcsb_polymer_entity_container_identifiers": {
                    "asym_ids": list(asym_ids),
                    "auth_asym_ids": list(auth_asym_ids),
                    "entity_id": "1",
                    "entry_id": pdb_id,
                    "uniprot_ids": [uniprot_id] if uniprot_id else [],
                    "reference_sequence_identifiers": (
                        [
                            {
                                "database_accession": uniprot_id,
                                "database_name": "UniProt",
                                "provenance_source": "SIFTS",
                                "entity_sequence_coverage": 1.0,
                                "reference_sequence_coverage": 0.95,
                            }
                        ]
                        if uniprot_id
                        else []
                    ),
                },
                "rcsb_polymer_entity_annotation": [
                    *(
                        {
                            "annotation_id": pfam_id,
                            "name": name,
                            "provenance_source": "Pfam",
                            "type": "Pfam",
                            "assignment_version": "37.0",
                        }
                        for pfam_id, name in pfam_rows
                    ),
                    {
                        "annotation_id": "GO:0000001",
                        "name": "filtered non-Pfam annotation",
                        "provenance_source": "GO",
                        "type": "GO",
                        "assignment_version": "1",
                    },
                ],
            }
        ],
    }


def _rcsb_target_family_fixture(
    root: Path,
    *,
    first_asym_ids: tuple[str, ...] = ("A",),
) -> tuple[dict[str, object], object, object]:
    common, _evaluation_hashes = _target_cluster_fixture(root / "source")
    target_cluster = target_cluster_module.materialize_posebusters_target_cluster_binding(
        **common
    )
    target_cluster_path = root / "target-clusters.json"
    target_cluster.write_json(target_cluster_path)
    entries = (
        rcsb_target_family_module.normalize_rcsb_graphql_target_entry(
            _raw_rcsb_target_entry(
                "1ABC",
                asym_ids=first_asym_ids,
                pfam_rows=(("PF00001", "Family one"),),
            )
        ),
        rcsb_target_family_module.normalize_rcsb_graphql_target_entry(
            _raw_rcsb_target_entry(
                "2DEF",
                uniprot_id="P00002",
                pfam_rows=(
                    ("PF00001", "Family one"),
                    ("PF00002", "Family two"),
                ),
            )
        ),
    )
    batch = rcsb_target_family_module.make_rcsb_request_batch(
        0,
        ("1ABC", "2DEF"),
        entries,
    )
    snapshot = rcsb_target_family_module.PoseBustersRcsbTargetAnnotationSnapshot(
        observation_utc="2026-07-23T00:00:00Z",
        retrieval_tool_identity="rcsb-pdb-skill/rest_request.py:execute",
        retrieval_tool_sha256="a" * 64,
        request_batches=(batch,),
        entries=entries,
    )
    snapshot_path = root / "rcsb-target-annotations.json"
    snapshot.write_json(snapshot_path)
    binding_common: dict[str, object] = {
        "archive_path": common["archive_path"],
        "selection_path": common["selection_path"],
        "intake_receipt_path": common["intake_receipt_path"],
        "target_cluster_receipt_path": target_cluster_path,
        "annotation_snapshot_path": snapshot_path,
        "expected_target_cluster_receipt_sha256": (
            target_cluster.fingerprint_sha256
        ),
        "expected_annotation_snapshot_sha256": snapshot.fingerprint_sha256,
        "contract": common["contract"],
    }
    return binding_common, snapshot, target_cluster


def test_rcsb_target_family_binding_retains_multilabel_and_partition_metrics(
    tmp_path: Path,
) -> None:
    common, snapshot, target_cluster = _rcsb_target_family_fixture(tmp_path)
    loaded = rcsb_target_family_module.load_posebusters_rcsb_target_annotation_snapshot(
        common["annotation_snapshot_path"],
        expected_snapshot_sha256=snapshot.fingerprint_sha256,
    )
    assert loaded.fingerprint_sha256 == snapshot.fingerprint_sha256
    receipt = (
        rcsb_target_family_module.materialize_posebusters_rcsb_target_family_binding(
            **common
        )
    )

    assert tuple(row.mapping_status for row in receipt.case_rows) == (
        "complete",
        "complete",
    )
    assert tuple(row.pfam_ids for row in receipt.case_rows) == (
        ("PF00001",),
        ("PF00001", "PF00002"),
    )
    assert tuple(row.pfam_id for row in receipt.pfam_family_rows) == (
        "PF00001",
        "PF00002",
    )
    assert receipt.pfam_family_rows[0].member_case_ids == _CASE_IDS
    assert len(receipt.pfam_set_rows) == 2
    metrics = {
        (row.engine_id, row.family_kind, row.family_id, row.metric_id): row
        for row in receipt.metrics
    }
    assert metrics[
        (
            None,
            "all_case_annotation",
            "all_cases",
            "pfam_annotation_case_rate",
        )
    ].numerator == 2
    assert metrics[
        (
            "vina",
            "pfam_multi_label",
            "PF00001",
            "top_1_rmsd_hit_rate_all_family_members",
        )
    ].numerator == 1
    assert metrics[
        (
            "smina",
            "pfam_multi_label",
            "PF00002",
            "top_1_valid_rmsd_hit_rate_all_family_members",
        )
    ].numerator == 1
    payload = receipt.to_dict()
    assert payload["target_cluster_receipt_sha256"] == (
        target_cluster.fingerprint_sha256
    )
    assert payload["target_family_metrics_present"] is True
    assert payload["complete_target_family_annotation_coverage"] is False
    assert payload["external_fit_training_leakage_audit_present"] is False
    assert payload["leakage_control_passed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "rcsb-target-families.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = (
        rcsb_target_family_module.verify_posebusters_rcsb_target_family_binding_receipt(
            target_family_receipt_path=output,
            **common,
        )
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256


def test_rcsb_target_family_binding_does_not_infer_chain_aliases(
    tmp_path: Path,
) -> None:
    common, _snapshot, _target_cluster = _rcsb_target_family_fixture(
        tmp_path,
        first_asym_ids=("B",),
    )
    receipt = (
        rcsb_target_family_module.materialize_posebusters_rcsb_target_family_binding(
            **common
        )
    )

    first = receipt.case_rows[0]
    assert first.pocket_chain_ids == ("A",)
    assert first.mapping_status == "pocket_chain_unmapped"
    assert first.unmapped_chain_ids == ("A",)
    assert first.annotation_status == "not_applicable"
    assert first.pfam_ids == ()
    assert receipt.to_dict()["pocket_chain_mapping_failure_case_count"] == 1


def test_rcsb_target_family_binding_prefers_exact_asym_id_over_auth_collision(
) -> None:
    first = rcsb_target_family_module.PoseBustersRcsbPolymerEntity(
        rcsb_entity_id="7TE8_1",
        entity_id="1",
        asym_ids=("A", "C"),
        auth_asym_ids=("C", "D"),
        uniprot_ids=(),
        reference_sequences=(),
        pfam_annotations=(),
    )
    pfam = rcsb_target_family_module.PoseBustersRcsbPfamAnnotation(
        annotation_id="PF00002",
        name="Family two",
        provenance_source="Pfam",
        assignment_version="37.0",
    )
    second = rcsb_target_family_module.PoseBustersRcsbPolymerEntity(
        rcsb_entity_id="7TE8_2",
        entity_id="2",
        asym_ids=("B", "D"),
        auth_asym_ids=("A", "B"),
        uniprot_ids=(),
        reference_sequences=(),
        pfam_annotations=(pfam,),
    )
    entry = rcsb_target_family_module.PoseBustersRcsbTargetEntry(
        pdb_id="7TE8",
        status="active",
        polymer_entities=(first, second),
    )

    case, _annotations = rcsb_target_family_module._target_case_from_entry(
        case_id="7TE8_P0T",
        receptor_sha256="a" * 64,
        reference_ligand_sha256="b" * 64,
        pocket_chain_ids=("B", "D"),
        entry=entry,
    )

    assert case.mapping_status == "complete"
    assert case.mapped_entity_ids == ("7TE8_2",)
    assert case.pfam_ids == ("PF00002",)


def test_rcsb_target_annotation_snapshot_mode_and_hash_fail_closed(
    tmp_path: Path,
) -> None:
    common, snapshot, _target_cluster = _rcsb_target_family_fixture(tmp_path)
    snapshot_path = common["annotation_snapshot_path"]
    snapshot_path.chmod(0o644)
    with pytest.raises(
        rcsb_target_family_module.PoseBustersRcsbTargetFamilyBindingError,
        match="must remain mode 0600",
    ):
        rcsb_target_family_module.load_posebusters_rcsb_target_annotation_snapshot(
            snapshot_path,
            expected_snapshot_sha256=snapshot.fingerprint_sha256,
        )
    snapshot_path.chmod(0o600)
    with pytest.raises(
        rcsb_target_family_module.PoseBustersRcsbTargetFamilyBindingError,
        match="contract or identity is invalid",
    ):
        rcsb_target_family_module.load_posebusters_rcsb_target_annotation_snapshot(
            snapshot_path,
            expected_snapshot_sha256="f" * 64,
        )
