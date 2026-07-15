from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import struct

import pytest

import betelgeuze_engine_v2 as package_root
import betelgeuze_engine_v2.forcefield as forcefield
from betelgeuze_engine_v2.forcefield import spice_c1c4_quantum_reference as module
from betelgeuze_engine_v2.forcefield.spice_c1c4_quantum_reference import (
    SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_BYTE_COUNT,
    SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256,
    SPICE_C1C4_QUANTUM_REFERENCE_ADMISSION_REPORT_SCHEMA_ID,
    SPICE_C1C4_QUANTUM_REFERENCE_CORE_SHA256,
    SPICE_C1C4_QUANTUM_REFERENCE_DOI,
    SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID,
    SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE,
    SPICE_C1C4_QUANTUM_REFERENCE_SPLIT_POLICY_ID,
    SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
    SpiceC1C4QuantumReferenceContractError,
    SpiceC1C4QuantumReferenceAdmissionReport,
    admit_spice_c1c4_quantum_reference_evidence,
    load_spice_c1c4_quantum_reference_evidence,
    serialize_spice_c1c4_quantum_reference_admission_report,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = (
    REPOSITORY_ROOT
    / "config"
    / "independent_engine_v2_v2_2_spice_c1c4_quantum_reference_evidence.json"
)
MODULE_PATH = (
    REPOSITORY_ROOT
    / "betelgeuze_engine_v2"
    / "forcefield"
    / "spice_c1c4_quantum_reference.py"
)


def _corpus_bytes() -> bytes:
    return CORPUS_PATH.read_bytes()


def _document() -> dict[str, object]:
    value = json.loads(_corpus_bytes())
    assert isinstance(value, dict)
    return value


def _canonical_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
        + b"\n"
    )


def _rehash(document: dict[str, object]) -> bytes:
    core = dict(document)
    core.pop("core_sha256", None)
    document["core_sha256"] = hashlib.sha256(_canonical_bytes(core)).hexdigest()
    return _canonical_bytes(document)


def _groups(document: dict[str, object]) -> list[dict[str, object]]:
    value = document["groups"]
    assert isinstance(value, list)
    assert all(isinstance(group, dict) for group in value)
    return value  # type: ignore[return-value]


def _records(group: dict[str, object]) -> list[dict[str, object]]:
    value = group["records"]
    assert isinstance(value, list)
    assert all(isinstance(record, dict) for record in value)
    return value  # type: ignore[return-value]


def test_frozen_corpus_loads_with_exact_release_and_hash_bindings() -> None:
    data = _corpus_bytes()
    corpus = load_spice_c1c4_quantum_reference_evidence(data)

    assert len(data) == SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_BYTE_COUNT == 251253
    assert (
        hashlib.sha256(data).hexdigest()
        == (SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256)
        == "ffa884e94f624b89ac8602cda8ff01f363f60838e4efc1c2a3c0a057bf94c0a3"
    )
    assert (
        corpus.core_sha256
        == SPICE_C1C4_QUANTUM_REFERENCE_CORE_SHA256
        == ("265c9883c06755cb845dd682b3b16634ea1f0d8ffd76dc60094b2224ab072dae")
    )
    assert corpus.artifact_sha256 == (SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256)
    assert corpus.artifact_byte_count == 251253
    assert tuple(group.group_id for group in corpus.groups) == (
        "c",
        "cc",
        "ccc",
        "cccc",
    )
    assert tuple(group.atom_count for group in corpus.groups) == (5, 8, 11, 14)
    assert len(corpus.records) == 200


def test_source_qcarchive_and_quantum_spec_are_exactly_pinned() -> None:
    document = _document()
    source = document["source"]
    quantum = document["quantum_reference"]
    assert isinstance(source, dict)
    assert isinstance(quantum, dict)

    assert source == {
        "release_id": SPICE_C1C4_QUANTUM_REFERENCE_SOURCE_RELEASE,
        "doi": SPICE_C1C4_QUANTUM_REFERENCE_DOI,
        "landing_page_url": "https://doi.org/10.5281/zenodo.10975225",
        "artifact_name": "SPICE-2.0.1.hdf5",
        "download_url": (
            "https://zenodo.org/api/records/10975225/files/SPICE-2.0.1.hdf5/content"
        ),
        "artifact_byte_count": 37479271148,
        "artifact_upstream_md5": "bfba2224b6540e1390a579569b475510",
        "whole_file_authentication_status": (
            "upstream_reported_md5_only_not_locally_recomputed"
        ),
        "github_repository_url": "https://github.com/openmm/spice-dataset",
        "github_tag": "2.0.1",
        "github_commit": "b99b3f4d85585df6bdfeca5a56420c57ec6385f1",
        "upstream_license_declaration": "CC0-1.0",
        "license_human_review_status": "pending",
        "qcarchive_server_url": "https://ml.qcarchive.molssi.org",
        "qcarchive_dataset_id": 340,
        "qcarchive_dataset_type": "singlepoint",
        "qcarchive_dataset_name": SPICE_C1C4_QUANTUM_REFERENCE_SUBSET,
        "qcarchive_specification_name": "spec_4",
    }
    assert quantum["subset_id"] == SPICE_C1C4_QUANTUM_REFERENCE_SUBSET
    assert quantum["method"] == "wb97m-d3bj"
    assert quantum["basis"] == "def2-tzvppd"
    assert quantum["program"] == "psi4"
    assert quantum["program_version"] == "1.4.1"
    assert quantum["qcengine_version"] == "v0.20.1"
    assert quantum["driver"] == "gradient"
    assert quantum["keywords"] == {
        "maxiter": 200,
        "scf_properties": [
            "dipole",
            "quadrupole",
            "wiberg_lowdin_indices",
            "mayer_indices",
            "mbis_charges",
        ],
        "wcombine": False,
    }
    assert quantum["protocols"] == {"wavefunction": "orbitals_and_eigenvalues"}
    assert quantum["record_status"] == "complete"
    assert quantum["compute_history_count_per_record"] == 1
    assert quantum["qcarchive_crosscheck_status"] == (
        "all_200_energy_float64_exact_and_gradient_float32_cast_exact"
    )
    assert quantum["coordinate_unit"] == "bohr"
    assert quantum["energy_unit"] == "hartree"
    assert quantum["gradient_unit"] == "hartree/bohr"
    assert quantum["gradient_semantics"] == ("energy_derivative_not_labeled_as_force")


def test_exact_qcarchive_ids_and_binary_values_are_retained() -> None:
    corpus = load_spice_c1c4_quantum_reference_evidence(_corpus_bytes())
    first = corpus.groups[0].records[0]
    last = corpus.groups[-1].records[-1]

    assert first.record_id == "qcarchive:340:spec_4:c-0:94481376"
    assert first.qcarchive_entry_name == "c-0"
    assert first.qcarchive_record_id == 94481376
    assert first.qcarchive_molecule_id == 87536171
    assert first.qcarchive_molecule_hash == ("6419bfecf0c2e00e128713e8da81e1a99af0a79e")
    assert first.geometry_binary32_be_hex.startswith("3b28bba0bd307e27")
    assert first.energy_binary64_be_hex == "c044444574f2b6e9"
    assert first.gradient_binary32_be_hex.startswith("3b74c268ba6bfec9")
    assert first.record_payload_sha256 == (
        "ad7e80177895267af5792ed00a391f0d3a75faf93196533f1d159c10765ba864"
    )
    assert last.record_id == "qcarchive:340:spec_4:cccc-9:94490193"
    assert last.qcarchive_molecule_id == 87539780
    assert last.qcarchive_molecule_hash == ("1b0998e450e6d4c0c63026257e29de5bbc7789ed")
    assert last.energy_binary64_be_hex == "c063d09f80f7c071"


def test_all_binary_values_have_exact_shapes_are_finite_and_unique() -> None:
    corpus = load_spice_c1c4_quantum_reference_evidence(_corpus_bytes())
    geometry_hashes: set[str] = set()
    payload_hashes: set[str] = set()
    source_ids: set[str] = set()
    qcarchive_record_ids: set[int] = set()
    qcarchive_molecule_ids: set[int] = set()
    qcarchive_molecule_hashes: set[str] = set()

    for group in corpus.groups:
        for record in group.records:
            geometry = bytes.fromhex(record.geometry_binary32_be_hex)
            energy = bytes.fromhex(record.energy_binary64_be_hex)
            gradient = bytes.fromhex(record.gradient_binary32_be_hex)
            assert len(geometry) == group.atom_count * 3 * 4
            assert len(energy) == 8
            assert len(gradient) == group.atom_count * 3 * 4
            assert all(
                math.isfinite(value) for (value,) in struct.iter_unpack(">f", geometry)
            )
            assert math.isfinite(struct.unpack(">d", energy)[0])
            assert all(
                math.isfinite(value) for (value,) in struct.iter_unpack(">f", gradient)
            )
            geometry_hashes.add(record.geometry_sha256)
            payload_hashes.add(record.record_payload_sha256)
            source_ids.add(record.record_id)
            qcarchive_record_ids.add(record.qcarchive_record_id)
            qcarchive_molecule_ids.add(record.qcarchive_molecule_id)
            qcarchive_molecule_hashes.add(record.qcarchive_molecule_hash)

    assert len(geometry_hashes) == 200
    assert len(payload_hashes) == 200
    assert len(source_ids) == 200
    assert len(qcarchive_record_ids) == 200
    assert len(qcarchive_molecule_ids) == 200
    assert len(qcarchive_molecule_hashes) == 200


def test_source_array_hashes_cover_exact_source_order_bytes() -> None:
    corpus = load_spice_c1c4_quantum_reference_evidence(_corpus_bytes())
    expected = {
        "c": (
            "5e51aa7b5a92bc55c5ed748354e2bf276e62ed38ff6b53e2146ad285d3e90bb1",
            "fdfb9a790a01d89163c78acfead0b2ed321852b02aa5839c899b232934864a93",
            "235fb701e31f64467539ad57feeedac71235761432dd1451057fb4ed866d756f",
        ),
        "cc": (
            "25934750eb828dc436b96bcb3a7ac3ced2474ad0b9a76f99ab265b02575a7b11",
            "670e02f3617347843d0c4e913e84403776bc4531d51661491056e7dd1b0dc0e7",
            "5bb929b00b333ed00e096f0e1b4b71f65cfed3cb016fae76042b7567b9a22420",
        ),
        "ccc": (
            "4802ecb632be7f2245be9c6ba6248d9244c8c46b1f7d24f92b9c897021999665",
            "f589866974752c41f7d4005838273703f16e143e7a362376fb96b72604ef8978",
            "80145f7ca4297bf7dc7df12529567bb4e91a0dfa8a64c3ea3b74809a074616a2",
        ),
        "cccc": (
            "2fe76411ce91fd3c57ffc592d4712c46496c4f3fc0dde95cdc3e61cedc0b95a9",
            "1181069e78c8190aaa21095f07fa4beac400c3c18751a615779a87001a9206aa",
            "768fd1a07a9067d9bfc4ead711c0aaf7f5fbb2111c872d2464ba9ce010d7704e",
        ),
    }
    for group in corpus.groups:
        geometry = b"".join(
            bytes.fromhex(record.geometry_binary32_be_hex) for record in group.records
        )
        energy = b"".join(
            bytes.fromhex(record.energy_binary64_be_hex) for record in group.records
        )
        gradient = b"".join(
            bytes.fromhex(record.gradient_binary32_be_hex) for record in group.records
        )
        observed = tuple(
            hashlib.sha256(value).hexdigest() for value in (geometry, energy, gradient)
        )
        assert observed == expected[group.group_id]
        assert observed == (
            group.conformations_sha256,
            group.energies_sha256,
            group.gradients_sha256,
        )


def test_split_is_target_independent_pair_atomic_and_has_no_overlap() -> None:
    corpus = load_spice_c1c4_quantum_reference_evidence(_corpus_bytes())
    document = _document()
    split = document["split"]
    assert isinstance(split, dict)
    assert split["policy_id"] == SPICE_C1C4_QUANTUM_REFERENCE_SPLIT_POLICY_ID
    assert split["assignment_key"] == "ascending_pair_sha256_then_pair_id"
    assert split["target_value_independent"] is True
    assert split["source_pair_definition"] == (
        "numeric_qcarchive_entry_suffix_modulo_25"
    )
    assert split["source_pair_membership"] == (
        "entry_suffixes_pair_id_and_pair_id_plus_25"
    )
    assert split["per_group_pair_counts"] == {
        "fit": 15,
        "selection": 5,
        "holdout": 5,
    }
    assert split["record_overlap_allowed"] is False
    assert split["geometry_overlap_allowed"] is False
    assert split["source_pair_overlap_allowed"] is False
    assert split["same_molecular_graph_cross_partition_policy"] == (
        "allowed_only_for_within_chemistry_unseen_conformation_evidence"
    )

    exact_pair_sets = {
        "c": {
            "fit": {0, 2, 3, 6, 7, 9, 10, 11, 12, 14, 15, 17, 19, 20, 24},
            "selection": {5, 8, 16, 18, 22},
            "holdout": {1, 4, 13, 21, 23},
        },
        "cc": {
            "fit": {0, 1, 5, 6, 9, 10, 12, 13, 15, 17, 18, 21, 22, 23, 24},
            "selection": {7, 8, 11, 16, 20},
            "holdout": {2, 3, 4, 14, 19},
        },
        "ccc": {
            "fit": {2, 3, 5, 7, 8, 9, 10, 11, 13, 14, 15, 17, 22, 23, 24},
            "selection": {6, 18, 19, 20, 21},
            "holdout": {0, 1, 4, 12, 16},
        },
        "cccc": {
            "fit": {0, 2, 4, 5, 8, 9, 11, 12, 13, 14, 15, 16, 17, 20, 22},
            "selection": {7, 18, 21, 23, 24},
            "holdout": {1, 3, 6, 10, 19},
        },
    }
    domain = b"SPICE-2.0.1:C1-C4:pair-split:v1"
    for group in corpus.groups:
        ordered_pair_ids = sorted(
            range(25),
            key=lambda pair_id: (
                hashlib.sha256(
                    domain
                    + b"\0"
                    + group.group_id.lower().encode("ascii")
                    + b"\0"
                    + str(pair_id).encode("ascii")
                ).digest(),
                pair_id,
            ),
        )
        observed_pair_sets = {
            partition: {
                record.source_pair_id
                for record in group.records
                if record.partition == partition
            }
            for partition in ("fit", "selection", "holdout")
        }
        assert observed_pair_sets == exact_pair_sets[group.group_id]
        assert observed_pair_sets == {
            "fit": set(ordered_pair_ids[:15]),
            "selection": set(ordered_pair_ids[15:20]),
            "holdout": set(ordered_pair_ids[20:]),
        }
        for pair_id in range(25):
            pair_rows = [
                record for record in group.records if record.source_pair_id == pair_id
            ]
            assert len(pair_rows) == 2
            assert {
                int(record.qcarchive_entry_name.rsplit("-", 1)[1])
                for record in pair_rows
            } == {pair_id, pair_id + 25}
            assert len({record.partition for record in pair_rows}) == 1
        assert Counter(record.partition for record in group.records) == {
            "fit": 30,
            "selection": 10,
            "holdout": 10,
        }
    assert Counter(record.partition for record in corpus.records) == {
        "fit": 120,
        "selection": 40,
        "holdout": 40,
    }


def test_admission_report_promotes_only_dataset_evidence_integrity() -> None:
    report = admit_spice_c1c4_quantum_reference_evidence(_corpus_bytes())

    assert report.schema_id == (SPICE_C1C4_QUANTUM_REFERENCE_ADMISSION_REPORT_SCHEMA_ID)
    assert report.evidence_schema_id == SPICE_C1C4_QUANTUM_REFERENCE_SCHEMA_ID
    assert report.source_release == "SPICE 2.0.1"
    assert report.source_doi == "10.5281/zenodo.10975225"
    assert report.subset_id == SPICE_C1C4_QUANTUM_REFERENCE_SUBSET
    assert (report.group_count, report.record_count) == (4, 200)
    assert report.unique_geometry_count == 200
    assert (
        report.fit_record_count,
        report.selection_record_count,
        report.holdout_record_count,
    ) == (120, 40, 40)
    assert (
        report.fit_pair_count,
        report.selection_pair_count,
        report.holdout_pair_count,
    ) == (60, 20, 20)
    assert report.exact_record_overlap_count == 0
    assert report.geometry_overlap_count == 0
    assert report.qcarchive_molecule_id_overlap_count == 0
    assert report.source_pair_overlap_count == 0
    assert report.molecular_graph_overlap_count == 4
    assert report.molecular_graph_disjoint is False
    assert report.time_disjoint is False
    assert report.release_disjoint is False
    assert report.generic_validation_split is False
    assert report.claim_scope == ("within_same_four_graphs_unseen_conformations_only")
    assert report.dataset_evidence_integrity is True
    assert report.license_human_reviewed is False
    assert report.source_whole_file_authenticated is False
    assert report.candidate_fitting_performed is False
    assert report.candidate_parameter_set_available is False
    assert report.parameter_family_sufficiency_assessed is False
    assert report.reference_validation_performed is False
    assert report.production_parameters_available is False
    assert report.parameterability_assessed is False
    assert report.parameterizable is False
    assert report.physics_ready is False
    assert report.runtime_eligible is False
    assert report.execution_authorized is False
    assert report.claim_safe is False


def test_admission_report_is_factory_only_and_serialization_replays_evidence() -> None:
    data = _corpus_bytes()
    report = admit_spice_c1c4_quantum_reference_evidence(data)
    kwargs = asdict(report)
    with pytest.raises(TypeError, match="factory-only"):
        SpiceC1C4QuantumReferenceAdmissionReport(_factory_token=object(), **kwargs)

    payload = serialize_spice_c1c4_quantum_reference_admission_report(data)
    assert payload == _canonical_bytes(kwargs)
    assert payload.endswith(b"\n")
    assert json.loads(payload) == kwargs

    document = _document()
    document["core_sha256"] = "0" * 64
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="self-hash"):
        serialize_spice_c1c4_quantum_reference_admission_report(
            _canonical_bytes(document)
        )


def test_monomer_targets_explicitly_do_not_evidence_lj_or_charges() -> None:
    document = _document()
    gaps = document["family_evidence_gaps"]
    nonpromotion = document["nonpromotion"]
    assert isinstance(gaps, dict)
    assert isinstance(nonpromotion, dict)

    assert gaps["partial_charge"] == (
        "not_evidenced_by_total_monomer_energy_and_gradient_targets"
    )
    assert gaps["lennard_jones"] == (
        "not_evidenced_by_isolated_monomer_energy_and_gradient_targets"
    )
    assert gaps["bond"] == "no_decomposition_or_fit_performed"
    assert gaps["angle"] == "no_decomposition_or_fit_performed"
    assert gaps["proper_torsion"] == "no_decomposition_or_fit_performed"
    assert gaps["improper_torsion"] == "not_identified_or_fit"
    assert gaps["absolute_cross_molecule_energy_fitting"] == (
        "prohibited_without_reference_energy_or_relative_energy_protocol"
    )
    assert nonpromotion["parameter_family_sufficiency_assessed"] is False
    assert nonpromotion["production_parameters_available"] is False


def test_runtime_module_has_no_network_hdf5_or_array_dependency() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    assert imported_roots.isdisjoint(
        {"fsspec", "h5py", "numpy", "requests", "qcportal"}
    )


@pytest.mark.parametrize("value", [bytearray(b"{}"), memoryview(b"{}"), "{}"])
def test_loader_requires_exact_bytes(value: object) -> None:
    with pytest.raises(TypeError, match="exact bytes"):
        load_spice_c1c4_quantum_reference_evidence(value)  # type: ignore[arg-type]


def test_loader_rejects_empty_oversized_and_non_ascii_payloads() -> None:
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="empty"):
        load_spice_c1c4_quantum_reference_evidence(b"")
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="fixed byte limit"
    ):
        load_spice_c1c4_quantum_reference_evidence(b" " * (512 * 1024 + 1))
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="ASCII"):
        load_spice_c1c4_quantum_reference_evidence(_corpus_bytes() + b"\xc3\xa9")


def test_loader_rejects_duplicate_keys_and_nonstandard_constants() -> None:
    duplicate = _corpus_bytes().replace(
        b'{"artifact_purpose":',
        b'{"schema_id":"duplicate","artifact_purpose":',
        1,
    )
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="duplicate"):
        load_spice_c1c4_quantum_reference_evidence(duplicate)

    nonstandard = _corpus_bytes().replace(b"37479271148", b"NaN", 1)
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="non-standard JSON constant"
    ):
        load_spice_c1c4_quantum_reference_evidence(nonstandard)


def test_loader_rejects_noncanonical_json_and_top_level_key_changes() -> None:
    document = _document()
    pretty = json.dumps(document, indent=2, ensure_ascii=True).encode("ascii")
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="canonical"):
        load_spice_c1c4_quantum_reference_evidence(pretty)

    missing = _document()
    missing.pop("evidence_scope")
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="keys mismatch"):
        load_spice_c1c4_quantum_reference_evidence(_canonical_bytes(missing))

    unexpected = _document()
    unexpected["unexpected"] = False
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="keys mismatch"):
        load_spice_c1c4_quantum_reference_evidence(_canonical_bytes(unexpected))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "doi"), "10.0/tampered"),
        (("source", "artifact_byte_count"), 1),
        (("source", "qcarchive_dataset_id"), 341),
        (("quantum_reference", "basis"), "def2-svp"),
        (("split", "target_value_independent"), False),
        (("coverage", "record_count"), 199),
        (("nonpromotion", "runtime_eligible"), True),
        (("family_evidence_gaps", "lennard_jones"), "sufficient"),
    ],
)
def test_loader_rejects_frozen_metadata_and_nonpromotion_tampering(
    path: tuple[str, str], value: object
) -> None:
    document = _document()
    section = document[path[0]]
    assert isinstance(section, dict)
    section[path[1]] = value
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="frozen evidence contract"
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_self_hash_tampering() -> None:
    document = _document()
    document["core_sha256"] = "0" * 64
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="self-hash"):
        load_spice_c1c4_quantum_reference_evidence(_canonical_bytes(document))


def test_loader_rejects_group_identity_topology_and_count_tampering() -> None:
    mutations = (
        ("group_id", "methane"),
        ("atom_count", 4),
        ("source_record_count", 49),
        ("molecular_charge", 1.0),
        ("molecular_multiplicity", 3),
    )
    for key, value in mutations:
        document = _document()
        _groups(document)[0][key] = value
        with pytest.raises(SpiceC1C4QuantumReferenceContractError):
            load_spice_c1c4_quantum_reference_evidence(_rehash(document))

    document = _document()
    _groups(document)[0]["connectivity"] = [[0, 1, 2.0]]
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="connectivity"):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_hex_width_nonfinite_and_value_hash_tampering() -> None:
    document = _document()
    record = _records(_groups(document)[0])[0]
    geometry = record["geometry_binary32_be_hex"]
    assert isinstance(geometry, str)
    record["geometry_binary32_be_hex"] = geometry[:-2]
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="hexadecimal width"
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))

    document = _document()
    record = _records(_groups(document)[0])[0]
    geometry = record["geometry_binary32_be_hex"]
    assert isinstance(geometry, str)
    record["geometry_binary32_be_hex"] = "7f800000" + geometry[8:]
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="non-finite"):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))

    document = _document()
    _records(_groups(document)[0])[0]["energy_sha256"] = "0" * 64
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="energy_sha256"):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_record_payload_and_group_source_hash_tampering() -> None:
    document = _document()
    _records(_groups(document)[0])[0]["record_payload_sha256"] = "0" * 64
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="record_payload_sha256"
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))

    document = _document()
    hashes = _groups(document)[0]["source_array_sha256"]
    assert isinstance(hashes, dict)
    hashes["conformations"] = "0" * 64
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="source_array_sha256"
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_target_independent_partition_tampering() -> None:
    document = _document()
    group = _groups(document)[0]
    records = _records(group)
    fit = next(record for record in records if record["partition"] == "fit")
    holdout = next(record for record in records if record["partition"] == "holdout")
    fit["partition"] = "holdout"
    holdout["partition"] = "fit"
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError,
        match="source pair .* crosses partitions",
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_source_pair_id_tampering() -> None:
    document = _document()
    record = _records(_groups(document)[0])[0]
    pair_id = record["source_pair_id"]
    assert isinstance(pair_id, int)
    record["source_pair_id"] = (pair_id + 1) % 25
    with pytest.raises(SpiceC1C4QuantumReferenceContractError, match="source_pair_id"):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_loader_rejects_qcarchive_identity_and_coverage_tampering() -> None:
    document = _document()
    first = _records(_groups(document)[0])[0]
    first["qcarchive_specification_name"] = "spec_5"
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError, match="specification_name"
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))

    document = _document()
    records = _records(_groups(document)[0])
    first = records[0]
    second = records[1]
    second["qcarchive_record_id"] = first["qcarchive_record_id"]
    second["record_id"] = (
        f"qcarchive:340:spec_4:{second['qcarchive_entry_name']}:"
        f"{second['qcarchive_record_id']}"
    )
    with pytest.raises(
        SpiceC1C4QuantumReferenceContractError,
        match="QCArchive record ID coverage",
    ):
        load_spice_c1c4_quantum_reference_evidence(_rehash(document))


def test_public_digest_alias_mutation_cannot_redefine_frozen_acceptance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_SHA256", "0" * 64
    )
    monkeypatch.setattr(module, "SPICE_C1C4_QUANTUM_REFERENCE_CORE_SHA256", "1" * 64)
    monkeypatch.setattr(module, "SPICE_C1C4_QUANTUM_REFERENCE_ARTIFACT_BYTE_COUNT", 1)
    corpus = load_spice_c1c4_quantum_reference_evidence(_corpus_bytes())
    assert corpus.artifact_sha256 == (
        "ffa884e94f624b89ac8602cda8ff01f363f60838e4efc1c2a3c0a057bf94c0a3"
    )


def test_public_api_is_forcefield_only_and_runtime_disconnected() -> None:
    for name in module.__all__:
        assert getattr(forcefield, name) is getattr(module, name)
        assert name not in package_root.__all__
        assert not hasattr(package_root, name)

    engine_source = (REPOSITORY_ROOT / "betelgeuze_engine_v2" / "engine.py").read_text(
        encoding="utf-8"
    )
    assert "spice_c1c4_quantum_reference" not in engine_source
    assert "SPICE_C1C4_QUANTUM_REFERENCE" not in engine_source
