from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(row) for row in csv.DictReader(fh)]


def test_coverage_v1_candidate_config_extends_existing_non_adrb2_freeze() -> None:
    rows = _read_csv(ROOT / "config/gpcr_non_adrb2_positive_candidates_coverage_v1.csv")

    assert len(rows) == 7
    assert {row["role"] for row in rows} == {"far_ood_eval"}
    assert {row["curation_status"] for row in rows} == {"curated"}
    assert all(row["target_family"] == "gpcr" for row in rows)
    assert all(row["is_binder"] == "1" for row in rows)
    assert all("ADRB2" not in row["target"] for row in rows)
    assert {
        "CHEMBL234_DRD3_HUMAN",
        "CHEMBL251_ADORA2A_HUMAN",
        "CHEMBL231_HRH1_HUMAN",
        "CHEMBL236_OPRD1_HUMAN",
    }.issubset({row["target"] for row in rows})


def test_coverage_v1_native_sources_have_ligand_centroid_inputs() -> None:
    rows = _read_csv(ROOT / "config/gpcr_non_adrb2_native_sources_coverage_v1.csv")
    by_target = {row["target"]: row for row in rows}

    assert len(rows) == 7
    assert by_target["CHEMBL234_DRD3_HUMAN"]["pdb_id"] == "3PBL"
    assert by_target["CHEMBL234_DRD3_HUMAN"]["ligand_code"] == "ETQ"
    assert by_target["CHEMBL251_ADORA2A_HUMAN"]["ligand_code"] == "ADN"
    assert by_target["CHEMBL231_HRH1_HUMAN"]["ligand_code"] == "D7V"
    assert by_target["CHEMBL236_OPRD1_HUMAN"]["ligand_code"] == "EJ4"
    assert all(row["source_release"] == "RCSB_PDB" for row in rows)
