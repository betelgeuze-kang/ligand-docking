from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

from tools.product.build_public_benchmark_product_preflight import build_preflight


def _tar_with_file(path: Path, member_name: str, source: Path) -> None:
    mode = "w:xz" if path.suffix == ".xz" else "w:gz"
    with tarfile.open(path, mode) as tar:
        tar.add(source, arcname=member_name)


def test_pdbbind_product_preflight_reports_unextracted_and_adapter_missing(tmp_path: Path) -> None:
    dataset = tmp_path / "pdbbind"
    dataset.mkdir()
    probe = tmp_path / "probe.txt"
    probe.write_text("x", encoding="utf-8")
    _tar_with_file(dataset / "CASF-2016_scoring.tar.xz", "data_5_sdf/1abc", probe)
    _tar_with_file(dataset / "CASF-2016_docking.tar.xz", "data_5_sdf/1abc_1", probe)

    payload = build_preflight(
        argparse.Namespace(
            suite_id="pdbbind_casf_pose_affinity",
            dataset_artifact=str(dataset),
            result_artifact=str(tmp_path / "missing.csv"),
            product_provenance_json="",
            out_json=str(tmp_path / "preflight.json"),
            out_md=str(tmp_path / "preflight.md"),
        )
    )

    blockers = payload["summary"]["blockers"]
    assert "pdbbind_casf_archives_not_extracted" in blockers
    assert "pdbbind_casf_product_pose_affinity_adapter_missing" not in blockers
    assert payload["summary"]["adapter_present"] is True
    assert payload["summary"]["approval_token_required"] == "APPROVE_PRODUCT_DOCKING_EXECUTION"


def test_protein_protein_product_preflight_detects_triplets_and_adapter_gap(tmp_path: Path) -> None:
    case = tmp_path / "bm5" / "HADDOCK-ready" / "1ABC"
    case.mkdir(parents=True)
    for suffix in ["target", "l_u", "r_u"]:
        (case / f"1ABC_{suffix}.pdb").write_text("ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n", encoding="utf-8")

    payload = build_preflight(
        argparse.Namespace(
            suite_id="protein_protein_docking_benchmark_v5",
            dataset_artifact=str(tmp_path / "bm5"),
            result_artifact=str(tmp_path / "missing.csv"),
            product_provenance_json="",
            out_json=str(tmp_path / "preflight.json"),
            out_md=str(tmp_path / "preflight.md"),
        )
    )

    assert payload["summary"]["complete_triplet_probe_count"] == 1
    assert "protein_protein_product_complex_docking_adapter_missing" not in payload["summary"]["blockers"]
    assert payload["summary"]["adapter_present"] is True


def test_casp_archive_product_preflight_reports_extraction_gap(tmp_path: Path) -> None:
    dataset = tmp_path / "casp"
    dataset.mkdir()
    probe = tmp_path / "T0001.pdb"
    probe.write_text("ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n", encoding="utf-8")
    _tar_with_file(dataset / "casp.targets.tar.gz", "T0001.pdb", probe)

    payload = build_preflight(
        argparse.Namespace(
            suite_id="casp_archive_structure_regression",
            dataset_artifact=str(dataset),
            result_artifact=str(tmp_path / "missing.csv"),
            product_provenance_json="",
            out_json=str(tmp_path / "preflight.json"),
            out_md=str(tmp_path / "preflight.md"),
        )
    )

    assert payload["summary"]["archive_count"] == 1
    assert "casp_archive_targets_not_extracted" in payload["summary"]["blockers"]
    assert "casp_archive_structure_regression_adapter_missing" not in payload["summary"]["blockers"]
    assert payload["summary"]["adapter_present"] is True


def test_casp_archive_product_preflight_detects_nested_extracted_targets(tmp_path: Path) -> None:
    dataset = tmp_path / "casp"
    nested = dataset / "extracted" / "casp.targets"
    nested.mkdir(parents=True)
    probe = tmp_path / "T0001.pdb"
    probe.write_text("ATOM      1  CA  GLY A   1       0.0   0.0   0.0  1.00 10.00           C\n", encoding="utf-8")
    _tar_with_file(dataset / "casp.targets.tar.gz", "T0001.pdb", probe)
    (nested / "T0001.pdb").write_text(probe.read_text(encoding="utf-8"), encoding="utf-8")

    payload = build_preflight(
        argparse.Namespace(
            suite_id="casp_archive_structure_regression",
            dataset_artifact=str(dataset),
            result_artifact=str(tmp_path / "missing.csv"),
            product_provenance_json="",
            out_json=str(tmp_path / "preflight.json"),
            out_md=str(tmp_path / "preflight.md"),
        )
    )

    assert payload["summary"]["extracted_pdb_count"] == 1
    assert "casp_archive_targets_not_extracted" not in payload["summary"]["blockers"]
    assert "casp_archive_structure_regression_adapter_missing" not in payload["summary"]["blockers"]
    assert payload["summary"]["adapter_present"] is True
