from __future__ import annotations

import hashlib
from pathlib import Path
import stat

import pytest

from betelgeuze_engine_v2.benchmark import (
    public_posebusters_external_preparation as preparation_module,
)
from betelgeuze_engine_v2.benchmark import (
    public_posebusters_prepared_ligand_diagnostic as diagnostic_module,
)
from betelgeuze_engine_v2.benchmark import (
    public_posebusters_openbabel_charge_type_comparison as openbabel_comparison_module,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_corpus_audit import (
    _canonical_sha256,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_external_preparation import (
    POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256,
    PoseBustersExternalPreparationCase,
    PoseBustersExternalPreparationDependency,
    PoseBustersExternalPreparationReceipt,
    PoseBustersExternalPreparationRuntime,
    PoseBustersExternalPreparedArtifact,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_prepared_ligand_diagnostic import (
    PoseBustersPreparedLigandDiagnosticError,
    PoseBustersPreparedLigandRuntimeIdentity,
    PoseBustersPreparedLigandRuntimePayload,
    materialize_posebusters_prepared_ligand_comparison,
    materialize_posebusters_prepared_ligand_observation,
    verify_posebusters_prepared_ligand_comparison_receipt,
    verify_posebusters_prepared_ligand_observation_receipt,
)
from betelgeuze_engine_v2.benchmark.public_posebusters_openbabel_charge_type_comparison import (
    POSEBUSTERS_OPENBABEL_SOURCE_COMMIT,
    POSEBUSTERS_OPENBABEL_VERSION,
    POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
    POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
    PoseBustersOpenBabelComparisonError,
    PoseBustersOpenBabelRuntimeIdentity,
    PoseBustersOpenBabelRuntimePayload,
    materialize_posebusters_openbabel_charge_type_comparison,
    verify_posebusters_openbabel_charge_type_comparison_receipt,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _external_runtime() -> PoseBustersExternalPreparationRuntime:
    dependency = PoseBustersExternalPreparationDependency(
        distribution_name="fake_meeko",
        version="0.0.test",
        payload_sha256=_sha(b"fake Meeko payload"),
        payload_file_count=1,
        payload_size_bytes=19,
    )
    return PoseBustersExternalPreparationRuntime(
        python_implementation="CPython",
        python_version="3.10.0",
        python_cache_tag="cpython-310",
        python_executable_sha256=_sha(b"fake preparation Python"),
        python_executable_size_bytes=23,
        platform_system="Linux",
        platform_machine="x86_64",
        libc_name="glibc",
        libc_version="2.35",
        filesystem_encoding="utf-8",
        torch_version="2.6.0+test",
        dependencies=(dependency,),
    )


def _diagnostic_identity(version: str) -> PoseBustersPreparedLigandRuntimeIdentity:
    distribution_version = {
        "2022.09.5": "2022.9.5",
        "2025.09.6": "2025.9.6",
    }[version]
    payload = PoseBustersPreparedLigandRuntimePayload(
        distribution_name="rdkit-pypi" if version == "2022.09.5" else "rdkit",
        distribution_version=distribution_version,
        payload_sha256=_sha(f"RDKit {version} payload".encode()),
        payload_file_count=3,
        payload_size_bytes=47,
    )
    return PoseBustersPreparedLigandRuntimeIdentity(
        python_implementation="CPython",
        python_version="3.10.0",
        python_cache_tag="cpython-310",
        python_executable_sha256=_sha(f"Python {version}".encode()),
        python_executable_size_bytes=31,
        platform_system="Linux",
        platform_machine="x86_64",
        libc_name="glibc",
        libc_version="2.35",
        filesystem_encoding="utf-8",
        rdkit_version=version,
        rdkit_build=f"Linux|test|{version}",
        boost_version="1_85",
        rdkit_payload=payload,
    )


class _FakeChargeRuntime:
    def __init__(self, version: str, *, second_charge: float = -0.1) -> None:
        self.identity = _diagnostic_identity(version)
        self._second_charge = second_charge

    def compute_source_atoms(
        self,
        smiles: str,
    ) -> tuple[diagnostic_module._SourceAtomCharge, ...]:
        assert smiles == "CC"
        return (
            diagnostic_module._SourceAtomCharge(
                source_index=1,
                atomic_number=6,
                element_symbol="C",
                aromatic=False,
                charge=0.1,
                hydrogen_charges=(0.02, 0.02, 0.02),
            ),
            diagnostic_module._SourceAtomCharge(
                source_index=2,
                atomic_number=6,
                element_symbol="C",
                aromatic=False,
                charge=self._second_charge,
                hydrogen_charges=(0.01, 0.01, 0.01),
            ),
        )


def _openbabel_identity() -> PoseBustersOpenBabelRuntimeIdentity:
    payload = PoseBustersOpenBabelRuntimePayload(
        distribution_name="openbabel",
        distribution_version=POSEBUSTERS_OPENBABEL_VERSION,
        payload_sha256=_sha(b"fake Open Babel distribution payload"),
        payload_file_count=4,
        payload_size_bytes=97,
    )
    return PoseBustersOpenBabelRuntimeIdentity(
        python_implementation="CPython",
        python_version="3.10.12",
        python_cache_tag="cpython-310",
        python_executable_sha256=_sha(b"fake Open Babel Python"),
        python_executable_size_bytes=23,
        platform_system="Linux",
        platform_machine="x86_64",
        libc_name="glibc",
        libc_version="2.35",
        filesystem_encoding="utf-8",
        openbabel_release_version=POSEBUSTERS_OPENBABEL_VERSION,
        openbabel_source_commit=POSEBUSTERS_OPENBABEL_SOURCE_COMMIT,
        wheel_filename=POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
        wheel_sha256=POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
        wheel_size_bytes=12_640_387,
        distribution_payload=payload,
        charge_model_id="gasteiger",
    )


class _FakeOpenBabelRuntime:
    def __init__(self, *, fail: bool = False) -> None:
        self.identity = _openbabel_identity()
        self._fail = fail

    def observe_smiles(
        self,
        smiles: str,
    ) -> openbabel_comparison_module._OpenBabelMoleculeObservation:
        assert smiles == "CC"
        if self._fail:
            raise RuntimeError("synthetic independent implementation failure")
        return openbabel_comparison_module._OpenBabelMoleculeObservation(
            formal_charge=0,
            source_atoms=(
                openbabel_comparison_module._OpenBabelAtomObservation(
                    role="source_atom",
                    source_index=1,
                    parent_source_index=None,
                    parent_hydrogen_ordinal=None,
                    atomic_number=6,
                    element_symbol="C",
                    aromatic=False,
                    internal_atom_type="C3",
                    charge=0.155,
                    writer_charge_token="+0.155",
                    writer_charge=0.155,
                    writer_atom_type="C",
                ),
                openbabel_comparison_module._OpenBabelAtomObservation(
                    role="source_atom",
                    source_index=2,
                    parent_source_index=None,
                    parent_hydrogen_ordinal=None,
                    atomic_number=6,
                    element_symbol="C",
                    aromatic=False,
                    internal_atom_type="C3",
                    charge=-0.069,
                    writer_charge_token="-0.069",
                    writer_charge=-0.069,
                    writer_atom_type="C",
                ),
            ),
            retained_hydrogens=(),
        )


_LIGAND_PDBQT = (
    b"REMARK SMILES CC\n"
    b"REMARK SMILES IDX 1 1 2 2\n"
    b"ROOT\n"
    b"ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.160 C \n"
    b"ATOM      2  C   UNL     1       1.000   0.000   0.000  1.00  0.00    -0.070 CG0\n"
    b"ATOM      3  G   UNL     1       0.500   0.000   0.000  1.00  0.00     0.000 G0\n"
    b"ENDROOT\n"
    b"TORSDOF 0\n"
)
_RECEPTOR_PDBQT = b"REMARK synthetic receptor\nEND\n"


def _preparation_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, PoseBustersExternalPreparationReceipt]:
    artifact_root = tmp_path / "prepared"
    artifact_root.mkdir(mode=0o700)
    case_root = artifact_root / "1ABC_LIG"
    case_root.mkdir(mode=0o700)
    ligand_path = case_root / "ligand.pdbqt"
    receptor_path = case_root / "receptor.pdbqt"
    ligand_path.write_bytes(_LIGAND_PDBQT)
    receptor_path.write_bytes(_RECEPTOR_PDBQT)
    ligand_path.chmod(0o600)
    receptor_path.chmod(0o600)
    source_ligand_sha = _sha(b"source ligand")
    source_receptor_sha = _sha(b"source receptor")
    artifacts = (
        PoseBustersExternalPreparedArtifact(
            role="prepared_ligand_pdbqt",
            relative_path="1ABC_LIG/ligand.pdbqt",
            sha256=_sha(_LIGAND_PDBQT),
            size_bytes=len(_LIGAND_PDBQT),
            source_role="ligand_start_conformer_sdf",
            source_sha256=source_ligand_sha,
        ),
        PoseBustersExternalPreparedArtifact(
            role="prepared_receptor_pdbqt",
            relative_path="1ABC_LIG/receptor.pdbqt",
            sha256=_sha(_RECEPTOR_PDBQT),
            size_bytes=len(_RECEPTOR_PDBQT),
            source_role="receptor_pdb",
            source_sha256=source_receptor_sha,
        ),
    )
    rows = (
        PoseBustersExternalPreparationCase(
            case_id="1ABC_LIG",
            status="prepared",
            disposition_code="strict_preparation_succeeded",
            reference_scorer_scope_status=(
                "blocked_parameters_and_partial_charges_missing"
            ),
            reference_scorer_scope_blockers=("partial_charges_missing",),
            preparation_attempted=True,
            ligand_preparation_succeeded=True,
            receptor_preparation_succeeded=True,
            artifacts=artifacts,
            pocket_center_binary64_hex=("0x0.0p+0",) * 3,
            diagnostic_sha256=_sha(b""),
            diagnostic_size_bytes=0,
        ),
        PoseBustersExternalPreparationCase(
            case_id="2DEF_BAD",
            status="abstain_chemistry_scope",
            disposition_code="unsupported_chemistry_scope",
            reference_scorer_scope_status="unsupported_metal_or_cofactor",
            reference_scorer_scope_blockers=("unsupported_metal",),
        ),
    )
    source_members = (
        (
            "external_preparation",
            preparation_module._source_file_sha256(preparation_module.__file__),
        ),
    )
    receipt = PoseBustersExternalPreparationReceipt(
        corpus_audit_receipt_sha256=_sha(b"corpus"),
        archive_intake_receipt_sha256=_sha(b"intake"),
        archive_contract_sha256=_sha(b"archive contract"),
        implementation_source_sha256=_canonical_sha256(dict(source_members)),
        implementation_source_members=source_members,
        runtime_identity=_external_runtime(),
        configuration_sha256=(POSEBUSTERS_EXTERNAL_PREPARATION_CONFIGURATION_SHA256),
        case_rows=rows,
        metrics=preparation_module._summary_metrics(rows),
        artifact_set_sha256=preparation_module._artifact_set_sha256(rows),
    )
    receipt_path = tmp_path / "preparation.json"
    receipt.write_json(receipt_path)
    return receipt_path, artifact_root, receipt


def test_prepared_ligand_observation_retains_mapping_pseudoatom_and_abstention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2022.09.5"),
    )
    receipt = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:00:00Z",
    )

    evaluated, abstained = receipt.case_rows
    assert evaluated.status == "evaluated"
    assert evaluated.real_atom_count == 2
    assert evaluated.pseudoatom_count == 1
    assert evaluated.atom_type_counts == (("C", 1), ("CG0", 1), ("G0", 1))
    assert evaluated.all_real_atoms_within_charge_serialization_tolerance is True
    assert evaluated.all_atoms_element_type_compatible is True
    assert evaluated.all_aromatic_carbons_type_compatible is True
    assert evaluated.all_pseudoatoms_zero_charge is True
    assert evaluated.atom_rows[2].role == "macrocycle_closure_pseudoatom"
    assert evaluated.atom_rows[2].expected_gasteiger_charge_binary64_hex is None
    assert abstained.status == "abstain_chemistry_scope"
    payload = receipt.to_dict()
    assert payload["all_case_denominator"] == 2
    assert payload["real_pdbqt_atom_count"] == 2
    assert payload["macrocycle_pseudoatom_count"] == 1
    assert payload["independent_charge_oracle_executed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "observation.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_prepared_ligand_observation_receipt(
        output,
        preparation_path,
        artifact_root,
        expected_receipt_sha256=receipt.fingerprint_sha256,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(
        PoseBustersPreparedLigandDiagnosticError, match="already exists"
    ):
        receipt.write_json(output)


def test_prepared_ligand_observation_fails_closed_on_artifact_tampering(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2022.09.5"),
    )
    receipt = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:00:00Z",
    )
    output = tmp_path / "observation.json"
    receipt.write_json(output)
    ligand_path = artifact_root / "1ABC_LIG" / "ligand.pdbqt"
    ligand_path.write_bytes(ligand_path.read_bytes() + b"REMARK tampered\n")
    ligand_path.chmod(0o600)

    with pytest.raises(
        PoseBustersPreparedLigandDiagnosticError,
        match="external-preparation receipt failed exact verification",
    ):
        verify_posebusters_prepared_ligand_observation_receipt(
            output,
            preparation_path,
            artifact_root,
            expected_receipt_sha256=receipt.fingerprint_sha256,
            expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        )


def test_prepared_ligand_cross_version_comparison_is_explicitly_same_algorithm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2022.09.5"),
    )
    observation_2022 = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:00:00Z",
    )
    path_2022 = tmp_path / "observation-2022.json"
    observation_2022.write_json(path_2022)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2025.09.6"),
    )
    observation_2025 = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:01:00Z",
    )
    path_2025 = tmp_path / "observation-2025.json"
    observation_2025.write_json(path_2025)

    comparison = materialize_posebusters_prepared_ligand_comparison(
        path_2022,
        path_2025,
        expected_rdkit_2022_observation_sha256=(observation_2022.fingerprint_sha256),
        expected_rdkit_2025_observation_sha256=(observation_2025.fingerprint_sha256),
        observation_utc="2026-07-23T00:02:00Z",
    )
    payload = comparison.to_dict()
    assert payload["all_case_denominator"] == 2
    assert payload["comparable_case_count"] == 1
    assert payload["compared_real_atom_count"] == 2
    assert payload["bitwise_equal_expected_charge_count"] == 2
    assert payload["version_sensitivity_detected"] is False
    assert payload["independent_charge_implementation_comparison_performed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "comparison.json"
    comparison.write_json(output)
    verified = verify_posebusters_prepared_ligand_comparison_receipt(
        output,
        path_2022,
        path_2025,
        expected_receipt_sha256=comparison.fingerprint_sha256,
        expected_rdkit_2022_observation_sha256=(observation_2022.fingerprint_sha256),
        expected_rdkit_2025_observation_sha256=(observation_2025.fingerprint_sha256),
    )
    assert verified.fingerprint_sha256 == comparison.fingerprint_sha256


def test_prepared_ligand_comparison_reports_version_sensitivity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2022.09.5"),
    )
    observation_2022 = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:00:00Z",
    )
    path_2022 = tmp_path / "observation-2022.json"
    observation_2022.write_json(path_2022)
    monkeypatch.setattr(
        diagnostic_module,
        "_load_rdkit_runtime",
        lambda: _FakeChargeRuntime("2025.09.6", second_charge=-0.099),
    )
    observation_2025 = materialize_posebusters_prepared_ligand_observation(
        preparation_path,
        artifact_root,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        observation_utc="2026-07-23T00:01:00Z",
    )
    path_2025 = tmp_path / "observation-2025.json"
    observation_2025.write_json(path_2025)

    comparison = materialize_posebusters_prepared_ligand_comparison(
        path_2022,
        path_2025,
        expected_rdkit_2022_observation_sha256=(observation_2022.fingerprint_sha256),
        expected_rdkit_2025_observation_sha256=(observation_2025.fingerprint_sha256),
        observation_utc="2026-07-23T00:02:00Z",
    )
    payload = comparison.to_dict()
    assert payload["version_sensitivity_detected"] is True
    assert payload["bitwise_equal_expected_charge_count"] == 1
    assert float.fromhex(
        payload["maximum_absolute_expected_charge_delta_binary64_hex"]
    ) == pytest.approx(0.001)


def test_openbabel_comparison_is_independent_descriptive_and_exactly_verifiable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    runtime = _FakeOpenBabelRuntime()
    monkeypatch.setattr(
        openbabel_comparison_module,
        "_load_openbabel_runtime",
        lambda _wheel, *, expected_wheel_sha256: runtime,
    )
    receipt = materialize_posebusters_openbabel_charge_type_comparison(
        preparation_path,
        artifact_root,
        tmp_path / POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        expected_openbabel_wheel_sha256=POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
        observation_utc="2026-07-23T01:00:00Z",
    )

    evaluated, abstained = receipt.case_rows
    assert evaluated.status == "evaluated"
    assert evaluated.compared_atom_count == 2
    assert evaluated.pseudoatom_count == 1
    assert evaluated.type_match_count == 1
    assert evaluated.type_mismatch_count == 1
    assert evaluated.atom_rows[1].meeko_ad4_atom_type == "CG0"
    assert evaluated.atom_rows[1].openbabel_ad4_atom_type == "C"
    assert evaluated.atom_rows[2].role == "macrocycle_closure_pseudoatom"
    assert evaluated.atom_rows[2].openbabel_charge_binary64_hex is None
    assert abstained.status == "abstain_chemistry_scope"

    payload = receipt.to_dict()
    assert payload["all_case_denominator"] == 2
    assert payload["evaluated_case_count"] == 1
    assert payload["compared_real_pdbqt_atom_count"] == 2
    assert payload["ad4_atom_type_exact_match_count"] == 1
    assert payload["ad4_atom_type_mismatch_count"] == 1
    assert (
        payload[
            "independent_external_charge_implementation_comparison_performed"
        ]
        is True
    )
    assert (
        payload[
            "independent_external_ad4_type_implementation_comparison_performed"
        ]
        is True
    )
    assert payload["charge_accuracy_threshold_preregistered"] is False
    assert payload["charge_accuracy_pass"] is None
    assert payload["independent_charge_oracle_executed"] is False
    assert payload["claim_safe"] is False

    output = tmp_path / "openbabel-comparison.json"
    receipt.write_json(output)
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    verified = verify_posebusters_openbabel_charge_type_comparison_receipt(
        output,
        preparation_path,
        artifact_root,
        tmp_path / POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
        expected_receipt_sha256=receipt.fingerprint_sha256,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        expected_openbabel_wheel_sha256=POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
    )
    assert verified.fingerprint_sha256 == receipt.fingerprint_sha256
    with pytest.raises(PoseBustersOpenBabelComparisonError, match="already exists"):
        receipt.write_json(output)


def test_openbabel_comparison_retains_all_failure_rows_without_atom_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preparation_path, artifact_root, preparation = _preparation_fixture(tmp_path)
    runtime = _FakeOpenBabelRuntime(fail=True)
    monkeypatch.setattr(
        openbabel_comparison_module,
        "_load_openbabel_runtime",
        lambda _wheel, *, expected_wheel_sha256: runtime,
    )
    receipt = materialize_posebusters_openbabel_charge_type_comparison(
        preparation_path,
        artifact_root,
        tmp_path / POSEBUSTERS_OPENBABEL_WHEEL_FILENAME,
        expected_preparation_receipt_sha256=preparation.fingerprint_sha256,
        expected_openbabel_wheel_sha256=POSEBUSTERS_OPENBABEL_WHEEL_SHA256,
        observation_utc="2026-07-23T01:01:00Z",
    )
    failed, abstained = receipt.case_rows
    assert failed.status == "comparison_failure"
    assert failed.comparison_attempted is True
    assert failed.error_code == "openbabel_charge_type_comparison_failed"
    assert failed.error_type == "RuntimeError"
    assert abstained.status == "abstain_chemistry_scope"
    payload = receipt.to_dict()
    assert payload["all_case_denominator"] == 2
    assert payload["comparison_failure_case_count"] == 1
    assert payload["compared_real_pdbqt_atom_count"] == 0
    assert payload["mean_absolute_charge_delta_binary64_hex"] is None
    assert payload["maximum_absolute_charge_delta_binary64_hex"] is None
    assert len(payload["metrics"]) == 4
    assert (
        payload[
            "independent_external_charge_implementation_comparison_performed"
        ]
        is False
    )
