"""Collector for real public docking benchmark cases (P1-8 input).

These tests exercise the assembly and fail-closed logic without touching the
network: metadata and deposited coordinates are injected, so what is under test
is the labelling contract, not RCSB availability.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "product" / "collect_public_docking_benchmark_cases.py"


@pytest.fixture(scope="module")
def collector():
    spec = importlib.util.spec_from_file_location(
        "collect_public_docking_benchmark_cases_under_test", MODULE_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _pocket_pdb(residue_names: list[str], *, ligand_comp_id: str = "LIG") -> str:
    """Deposited-style PDB: one ligand atom plus contacting residue atoms."""

    lines = [
        "HETATM    1  C1  %s A 500       0.000   0.000   0.000  1.00  0.00           C"
        % ligand_comp_id
    ]
    serial = 2
    for index, residue in enumerate(residue_names, start=1):
        lines.append(
            "ATOM  %5d  CA  %s A%4d    %8.3f%8.3f%8.3f  1.00  0.00           C"
            % (serial, residue, index, 1.0 + 0.1 * index, 0.5, 0.5)
        )
        serial += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


def test_pocket_polarity_buckets_from_measured_contacts(collector):
    polar = collector.measure_pocket_polarity(
        _pocket_pdb(["ARG", "ASP", "SER", "THR", "HIS"]), "LIG"
    )
    assert polar is not None
    assert polar.bucket == "polar_pocket_ge_0p60"
    assert polar.contact_residue_count == 5
    assert polar.ligand_atom_count == 1

    apolar = collector.measure_pocket_polarity(
        _pocket_pdb(["ALA", "VAL", "LEU", "ILE", "PHE"]), "LIG"
    )
    assert apolar is not None
    assert apolar.bucket == "apolar_pocket_lt_0p40"

    mixed = collector.measure_pocket_polarity(
        _pocket_pdb(["ARG", "ASP", "ALA", "VAL"]), "LIG"
    )
    assert mixed is not None
    assert mixed.bucket == "mixed_pocket_0p40_0p60"


def test_pocket_polarity_absent_ligand_is_not_defaulted(collector):
    # No HETATM for the requested component: the axis must not be guessed.
    assert collector.measure_pocket_polarity(_pocket_pdb(["ARG"], ligand_comp_id="XXX"), "LIG") is None


def test_pocket_polarity_requires_contact_shell(collector):
    far = (
        "HETATM    1  C1  LIG A 500       0.000   0.000   0.000  1.00  0.00           C\n"
        "ATOM      2  CA  ARG A   1      50.000  50.000  50.000  1.00  0.00           C\n"
        "END\n"
    )
    assert collector.measure_pocket_polarity(far, "LIG") is None


def test_ligand_chemistry_measured_by_rdkit(collector):
    chemistry = collector.measure_ligand_chemistry("CCN[C@H]1C[NH](S(=O)(=O)c2c1ccs2)CCOCC")
    if chemistry is None:
        chemistry = collector.measure_ligand_chemistry("c1ccccc1CCCCN")
    assert chemistry is not None
    assert chemistry.heavy_atom_count > 0
    assert chemistry.ring_count >= 1

    assert collector.measure_ligand_chemistry("") is None
    assert collector.measure_ligand_chemistry("not-a-smiles((((") is None


def test_charge_class_and_input_quality_labels(collector):
    assert collector._charge_class(1) == "cationic"
    assert collector._charge_class(-2) == "anionic"
    assert collector._charge_class(0) == "neutral"
    assert collector._input_quality(1.5) == "high_resolution_le_1p8a"
    assert collector._input_quality(2.1) == "good_resolution_le_2p2a"
    assert collector._input_quality(2.5) == "moderate_resolution_le_2p6a"
    assert collector._input_quality(3.1) == "low_resolution_gt_2p6a"
    assert collector._input_quality(None) == ""


def test_solvent_and_cofactor_components_cannot_become_case_ligands(collector):
    assert not collector._is_candidate_ligand({"comp_id": "GOL", "formula_weight": 92.09})
    assert not collector._is_candidate_ligand({"comp_id": "ZN", "formula_weight": 65.4})
    assert not collector._is_candidate_ligand({"comp_id": "HEM", "formula_weight": 616.5})
    # Missing weight is not defaulted to acceptable.
    assert not collector._is_candidate_ligand({"comp_id": "ABC", "formula_weight": None})
    assert collector._is_candidate_ligand({"comp_id": "ABC", "formula_weight": 383.5})


def test_metal_or_cofactor_label_reads_other_components(collector):
    components = [
        {"comp_id": "LIG"},
        {"comp_id": "ZN"},
        {"comp_id": "HEM"},
    ]
    assert collector._metal_or_cofactor_label(components, "LIG") == "metal_and_cofactor_present"
    assert collector._metal_or_cofactor_label([{"comp_id": "LIG"}, {"comp_id": "ZN"}], "LIG") == "metal_present"
    assert collector._metal_or_cofactor_label([{"comp_id": "LIG"}, {"comp_id": "FAD"}], "LIG") == "cofactor_present"
    assert collector._metal_or_cofactor_label([{"comp_id": "LIG"}, {"comp_id": "GOL"}], "LIG") == "absent"


def _metadata_entry(
    *,
    resolution: float | None,
    ligand_comp_id: str,
    smiles: str,
    accession: str,
    extra_comp_ids: tuple[str, ...] = (),
) -> dict:
    components = [
        {
            "comp_id": ligand_comp_id,
            "name": f"ligand {ligand_comp_id}",
            "formula_weight": 383.5,
            "smiles": smiles,
        }
    ]
    components.extend(
        {"comp_id": comp_id, "name": comp_id, "formula_weight": 65.4, "smiles": ""}
        for comp_id in extra_comp_ids
    )
    return {
        "resolution_a": resolution,
        "components": components,
        "uniprot_accessions": [accession],
    }


def test_build_cases_labels_every_axis_from_measured_data(collector):
    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6,
            ligand_comp_id="AAA",
            smiles="c1ccc(cc1)S(=O)(=O)NCCOCC",
            accession=accession,
            extra_comp_ids=("ZN",),
        )
    }
    cases, dropped = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(
            ["ARG", "ASP", "SER", "HIS"], ligand_comp_id="AAA"
        ),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    assert dropped == []
    assert len(cases) == 1
    case = cases[0]
    assert case.case_id == "pdb_1AAA_AAA_holo"
    assert case.target_id == "pdb:1AAA"
    assert case.ligand_id == "ccd:AAA"
    assert case.provenance_id == "rcsb_pdb_entry:1AAA#ligand=AAA"
    assert case.strata["target_family"] == "lyase_carbonic_anhydrase"
    assert case.strata["apo_or_holo"] == "holo_self_docking"
    assert case.strata["input_quality"] == "high_resolution_le_1p8a"
    assert case.strata["metal_or_cofactor_present"] == "metal_present"
    assert case.strata["pocket_polarity"] == "polar_pocket_ge_0p60"
    assert case.evidence["receptor_structure_url"].endswith("/1AAA.pdb")
    assert len(case.evidence["receptor_pdb_sha256"]) == 64
    # Every axis is populated; nothing is left blank for the suite contract.
    from betelgeuze_product.frozen_benchmark_suite import REQUIRED_STRATIFICATION_AXES

    assert set(case.strata) == set(REQUIRED_STRATIFICATION_AXES)
    assert all(case.strata[axis] for axis in REQUIRED_STRATIFICATION_AXES)


def test_uncurated_family_missing_resolution_and_missing_structure_are_dropped(collector):
    metadata = {
        "1UNC": _metadata_entry(
            resolution=1.5, ligand_comp_id="UNC", smiles="c1ccccc1CCN", accession="P99999"
        ),
        "1NOR": _metadata_entry(
            resolution=None, ligand_comp_id="NOR", smiles="c1ccccc1CCN", accession="P00918"
        ),
        "1NOS": _metadata_entry(
            resolution=1.5,
            ligand_comp_id="NOS",
            smiles="CCNCCc1ccc(O)cc1",
            accession="P00918",
        ),
        "1NOL": _metadata_entry(
            resolution=1.5, ligand_comp_id="GOL", smiles="OCC(O)CO", accession="P00918"
        ),
    }
    cases, dropped = collector.build_cases_from_metadata(
        accession_holo_entries={"P99999": ["1UNC"], "P00918": ["1NOR", "1NOS", "1NOL"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: None,
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    assert cases == []
    reasons = {record["reason"] for record in dropped}
    assert "target_family_not_curated_for_accession" in reasons
    assert "resolution_missing" in reasons
    assert "structure_download_unavailable" in reasons
    assert "no_drug_like_ligand_component" in reasons


def test_duplicate_ligand_component_is_dropped(collector):
    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6, ligand_comp_id="AAA", smiles="c1ccccc1CCOCC", accession=accession
        ),
        "1BBB": _metadata_entry(
            resolution=1.7, ligand_comp_id="AAA", smiles="c1ccccc1CCOCC", accession=accession
        ),
    }
    cases, dropped = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA", "1BBB"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(["ARG", "ALA"], ligand_comp_id="AAA"),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    assert [case.case_id for case in cases] == ["pdb_1AAA_AAA_holo"]
    assert any(record["reason"].startswith("duplicate_ligand_component") for record in dropped)


def test_apo_case_reuses_holo_ligand_and_records_source_entry(collector):
    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6, ligand_comp_id="AAA", smiles="c1ccccc1CCOCC", accession=accession,
            extra_comp_ids=("ZN",),
        ),
        "1APO": {"resolution_a": 2.4, "components": [], "uniprot_accessions": [accession]},
    }
    cases, _ = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA"]},
        accession_apo_entries={accession: ["1APO"]},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(["ARG", "ALA"], ligand_comp_id="AAA"),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=5,
    )
    apo = [case for case in cases if case.strata["apo_or_holo"] == "apo_cross_docking"]
    assert len(apo) == 1
    case = apo[0]
    assert case.case_id == "pdb_1APO_AAA_apo"
    assert "ligand_source_entry=1AAA" in case.provenance_id
    assert case.evidence["ligand_source_entry_id"] == "1AAA"
    assert case.strata["input_quality"] == "moderate_resolution_le_2p6a"
    # The apo receptor has no metal, so the label is measured on the apo entry.
    assert case.strata["metal_or_cofactor_present"] == "absent"
    # Pocket polarity is inherited but the provenance says where it was measured.
    assert case.evidence["pocket_polarity_measured_on"] == "1AAA"
    assert case.evidence["receptor_structure_url"].endswith("/1APO.pdb")
    assert len(case.evidence["receptor_pdb_sha256"]) == 64
    assert case.evidence["ligand_source_receptor_structure_url"].endswith("/1AAA.pdb")
    assert len(case.evidence["ligand_source_receptor_pdb_sha256"]) == 64


def test_apo_case_requires_a_holo_donor(collector):
    accession = "P00918"
    metadata = {"1APO": {"resolution_a": 2.0, "components": [], "uniprot_accessions": [accession]}}
    cases, _ = collector.build_cases_from_metadata(
        accession_holo_entries={},
        accession_apo_entries={accession: ["1APO"]},
        metadata=metadata,
        structure_loader=lambda entry_id: "",
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=5,
    )
    assert cases == []


def test_collection_blockers_fail_closed_on_small_single_bucket_set(collector):
    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6, ligand_comp_id="AAA", smiles="c1ccccc1CCOCC", accession=accession
        )
    }
    cases, _ = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(["ARG", "ALA"], ligand_comp_id="AAA"),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    blockers = collector.collection_blockers(cases)
    assert any(blocker.startswith("case_count_below_minimum") for blocker in blockers)
    assert any(blocker.startswith("stratification_axis_single_bucket") for blocker in blockers)


def test_packet_declares_no_docking_or_baseline_execution(collector):
    packet = collector.build_collection_packet([], [{"entry_id": "1XXX", "reason": "resolution_missing"}])
    summary = packet["summary"]
    assert summary["schema_version"] == "public_docking_benchmark_case_collection_v2"
    assert len(summary["case_set_hash"]) == 64
    assert summary["ready"] is False
    assert summary["docking_executed"] is False
    assert summary["metrics_computed"] is False
    assert summary["baseline_executed"] is False
    assert summary["external_state_mutated"] is False
    assert summary["synthetic_cases_used"] is False
    assert summary["dropped_reason_counts"] == {"resolution_missing": 1}
    markdown = collector.render_markdown(packet)
    assert "Public Docking Benchmark Case Collection" in markdown
    assert "resolution_missing" in markdown


def test_freeze_case_set_is_content_addressed_and_immutable(collector, tmp_path):
    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6,
            ligand_comp_id="AAA",
            smiles="c1ccccc1CCOCC",
            accession=accession,
        )
    }
    cases, dropped = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(["ARG", "ALA"], ligand_comp_id="AAA"),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    packet = collector.build_collection_packet(cases, dropped)
    frozen, manifest = collector.freeze_case_set(
        cases,
        packet,
        output_root=tmp_path,
        frozen_at_utc="2026-07-27T00:00:00Z",
    )
    assert frozen["summary"]["frozen_case_set"] is True
    assert frozen["summary"]["frozen_at_utc"] == "2026-07-27T00:00:00Z"
    assert manifest["immutable"] is True
    assert manifest["case_set_hash"] == packet["summary"]["case_set_hash"]

    cases_path = tmp_path / manifest["cases_csv"]
    receipt_path = tmp_path / manifest["collection_receipt_json"]
    markdown_path = tmp_path / manifest["collection_receipt_md"]
    assert cases_path.is_file()
    assert receipt_path.is_file()
    assert markdown_path.is_file()

    repeated, repeated_manifest = collector.freeze_case_set(
        cases,
        packet,
        output_root=tmp_path,
        frozen_at_utc="2099-01-01T00:00:00Z",
    )
    assert repeated["summary"]["frozen_at_utc"] == "2026-07-27T00:00:00Z"
    assert repeated_manifest == manifest

    receipt_path.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="frozen_snapshot_artifact_hash_mismatch"):
        collector.freeze_case_set(cases, packet, output_root=tmp_path)


def test_written_csv_matches_intake_required_columns(collector, tmp_path):
    import csv as csv_module

    from betelgeuze_product.frozen_benchmark_suite import REQUIRED_STRATIFICATION_AXES

    accession = "P00918"
    metadata = {
        "1AAA": _metadata_entry(
            resolution=1.6, ligand_comp_id="AAA", smiles="c1ccccc1CCOCC", accession=accession
        )
    }
    cases, _ = collector.build_cases_from_metadata(
        accession_holo_entries={accession: ["1AAA"]},
        accession_apo_entries={},
        metadata=metadata,
        structure_loader=lambda entry_id: _pocket_pdb(["ARG", "ALA"], ligand_comp_id="AAA"),
        max_cases=10,
        per_accession_holo_limit=5,
        per_accession_apo_limit=0,
    )
    target = tmp_path / "cases.csv"
    collector.write_cases_csv(target, cases)
    with target.open("r", encoding="utf-8", newline="") as handle:
        reader = csv_module.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    expected = [
        "case_id",
        "target_id",
        "ligand_id",
        "provenance_id",
        *REQUIRED_STRATIFICATION_AXES,
    ]
    assert fieldnames == expected
    assert len(rows) == 1
    assert all(rows[0][axis] for axis in REQUIRED_STRATIFICATION_AXES)


def test_determinism_of_case_order(collector):
    accession = "P00918"
    metadata = {
        "1BBB": _metadata_entry(
            resolution=1.6, ligand_comp_id="BBB", smiles="c1ccccc1CCOCC", accession=accession
        ),
        "1AAA": _metadata_entry(
            resolution=1.7, ligand_comp_id="AAA", smiles="c1ccc(cc1)CCCN", accession=accession
        ),
    }

    def run():
        cases, _ = collector.build_cases_from_metadata(
            accession_holo_entries={accession: ["1BBB", "1AAA"]},
            accession_apo_entries={},
            metadata=metadata,
            structure_loader=lambda entry_id: _pocket_pdb(
                ["ARG", "ALA"], ligand_comp_id="BBB" if entry_id == "1BBB" else "AAA"
            ),
            max_cases=10,
            per_accession_holo_limit=5,
            per_accession_apo_limit=0,
        )
        return [case.case_id for case in cases]

    first = run()
    assert first == sorted(first)
    assert first == run()
