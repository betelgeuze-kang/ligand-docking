from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def test_build_pxr_local_candidate_source_helper(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    config = tmp_path / "config"
    replacement_csv = runs / "pxr_packet_replacement_workbook_current.csv"
    provenance_csv = config / "biorxiv_temporal_ligand_provenance_v1.csv"

    _write_csv(
        replacement_csv,
        [
            "packet",
            "packet_step",
            "current_ligand_id",
            "current_role",
            "replacement_is_binder",
        ],
        [
            ["core", "core_fit_binder_01", "pxr_fit_ligand_01", "fit", "1"],
            ["ood", "ood_eval_non_binder_01", "pxr_ood_decoy_01", "far_ood_eval", "0"],
        ],
    )
    _write_csv(
        provenance_csv,
        [
            "set_id",
            "task_id",
            "domain",
            "profile_json",
            "ligand_csv",
            "eval_split_csv",
            "target",
            "ligand_id",
            "role",
            "is_binder",
            "source_label",
            "source_release",
            "provenance_date",
            "publication_year",
            "release_date",
            "provenance_granularity",
            "provenance_url",
            "curation_status",
            "notes",
        ],
        [
            [
                "set_temporal_core_blind",
                "gpcr_core_full",
                "gpcr",
                "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3.json",
                "config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv",
                "config/ligand_eval_splits_blind_gpcr_adrb2_v1.csv",
                "ADRB2_GPCR_BLIND",
                "carazolol",
                "far_ood_eval",
                "1",
                "gpcr_blind_proxy_v1",
                "gpcr_blind_proxy_v1",
                "1983",
                "1983",
                "2026-03-10",
                "item_publication",
                "https://example.org/carazolol",
                "item_publication_chembl_api",
                "note",
            ],
            [
                "set_temporal_core_blind",
                "gpcr_core_full",
                "gpcr",
                "config/ligand_htvs_blind_gpcr_adrb2_v4_scorefix3.json",
                "config/ligand_binding_reference_blind_gpcr_adrb2_v1.csv",
                "config/ligand_eval_splits_blind_gpcr_adrb2_v1.csv",
                "ADRB2_GPCR_BLIND",
                "acetaminophen",
                "far_ood_eval",
                "0",
                "gpcr_blind_proxy_v1",
                "gpcr_blind_proxy_v1",
                "1980",
                "1980",
                "2026-03-10",
                "item_publication",
                "https://example.org/acetaminophen",
                "item_publication_chembl_api",
                "note",
            ],
        ],
    )

    out_json = runs / "pxr_local_candidate_source_helper_current.json"
    out_csv = runs / "pxr_local_candidate_source_helper_current.csv"
    out_md = runs / "pxr_local_candidate_source_helper_current.md"
    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_pxr_local_candidate_source_helper.py"),
            "--replacement-csv",
            str(replacement_csv),
            "--provenance-csv",
            str(provenance_csv),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["helper_row_count"] == 2
    assert payload["summary"]["template_source_release_count"] == 1

    rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8")))
    assert len(rows) == 2
    assert rows[0]["template_ligand_id"] == "carazolol"
    assert rows[1]["template_ligand_id"] == "acetaminophen"
    assert rows[0]["hint_tier"] == "named_ligand_item_publication_template"

    md_text = out_md.read_text(encoding="utf-8")
    assert "PXR Local Candidate Source Helper" in md_text
    assert "core_fit_binder_01" in md_text
