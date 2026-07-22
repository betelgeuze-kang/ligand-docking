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
    public_posebusters_external_preparation as external_preparation_module,
    public_posebusters_vina_execution as vina_execution_module,
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


def _receptor(*, zinc: bool) -> bytes:
    rows = [
        (
            f"CRYST1{20.0:9.3f}{21.0:9.3f}{22.0:9.3f}"
            f"{80.0:7.2f}{90.0:7.2f}{90.0:7.2f} P 1           1"
        ),
        _pdb_atom(
            10014,
            "C1",
            "C",
            0.0,
            record="ATOM",
            residue="ALA",
        ),
        _pdb_atom(
            10015,
            "O1",
            "O",
            1.25,
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
                4.0,
                record="HETATM",
                residue="ZN",
            )
        )
        rows.append(
            _pdb_atom(
                10017,
                "C2",
                "C",
                5.0,
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
        uncompressed_size = sum(
            info.file_size for info in infos if not info.is_dir()
        )
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
    assert all(0.0 <= metric.confidence_interval_low <= metric.estimate for metric in metrics.values())
    assert all(metric.estimate <= metric.confidence_interval_high <= 1.0 for metric in metrics.values())
    payload = receipt.to_dict()
    assert payload["archive_extracted"] is False
    assert payload["external_stereo_oracle_present"] is False
    assert payload["pose_generation_performed"] is False
    assert payload["benchmark_executed"] is False
    assert payload["claim_safe"] is False


def test_corpus_audit_receipt_is_private_no_overwrite_and_exactly_reexecutable(
    tmp_path: Path,
) -> None:
    archive_path, selection_path, intake_path, contract = _fixture(
        tmp_path / "source"
    )
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


def test_native_geometry_preflight_is_all_case_claim_closed_and_reexecutable(
    tmp_path: Path,
) -> None:
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
    assert first.minimum_receptor_ligand_ratio_hex == 0.0.hex()
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
        receptor = (
            f"REMARK receptor source {_sha(receptor_pdb)}\nEND\n".encode("ascii")
        )
        ligand = (
            f"REMARK ligand source {_sha(ligand_start_sdf)}\nEND\n".encode("ascii")
        )
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
