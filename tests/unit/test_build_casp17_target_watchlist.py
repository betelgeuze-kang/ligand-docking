from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _write_source(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "Target;Type;Res;Oligo.State;Entry Date; Server Exp.;Human Exp.;QA Exp.;Cancellation Date;Description",
                "H1340;Prot;686;UNK;2026-05-18;2026-05-21;2026-06-01;2026-06-04;-;Parahenipavirus F protein /antibody complex",
                "T1400;Prot/Ligand;300;A1;2026-05-18;2026-05-21;2026-06-02;2026-06-05;-;Kinase inhibitor complex",
                "R2341;NucA;186;A1;2026-05-18;2026-05-20;2026-06-01;-;-;RRE core",
                "H1332;Prot;704;UNK;2026-05-11;2026-05-14;2026-05-25;2026-05-28;2026-05-18;Canceled - preprint",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_build_casp17_target_watchlist_and_intake_seed(tmp_path: Path) -> None:
    source_csv = tmp_path / "targets.csv"
    _write_source(source_csv)
    out_json = tmp_path / "runs/watch.json"
    out_csv = tmp_path / "runs/watch.csv"
    out_md = tmp_path / "runs/watch.md"
    intake_seed = tmp_path / "runs/intake_seed.csv"

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/build_casp17_target_watchlist.py"),
            "--input-csv",
            str(source_csv),
            "--today",
            "2026-05-19",
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-md",
            str(out_md),
            "--out-intake-seed-csv",
            str(intake_seed),
        ],
        cwd=ROOT,
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["raw_target_count"] == 4
    assert payload["summary"]["selected_lane_open_target_count"] == 2
    assert payload["summary"]["primary_ligand_open_target_count"] == 1
    assert payload["summary"]["secondary_difficult_open_target_count"] == 1
    assert payload["summary"]["top_selected_targets"] == ["T1400", "H1340"]

    rows = {row["target_id"]: row for row in payload["rows"]}
    assert rows["T1400"]["lane_recommendation"] == "organic_ligand_protein_complexes"
    assert rows["H1340"]["lane_recommendation"] == "difficult_protein_complexes"
    assert rows["R2341"]["lane_recommendation"] == "out_of_scope_nucleic_acid_or_hybrid"
    assert rows["H1332"]["lane_recommendation"] == "out_of_scope_cancelled"

    with intake_seed.open("r", encoding="utf-8", newline="") as handle:
        seed_rows = list(csv.DictReader(handle))
    assert [row["target_id"] for row in seed_rows] == ["T1400", "H1340"]
    assert seed_rows[0]["prediction_file_path"] == ""
    assert seed_rows[0]["prediction_import_status"] == "missing"
    assert seed_rows[0]["geometry_validation_json_path"] == ""
    assert seed_rows[0]["confidence_validation_json_path"] == ""
    assert seed_rows[0]["internal_scorecard_json_path"] == ""
    assert seed_rows[0]["format_check_status"] == "missing"
    assert seed_rows[0]["parameterization_status"] == "missing"
    assert seed_rows[1]["parameterization_status"] == "not_applicable"

    md_text = out_md.read_text(encoding="utf-8")
    assert "CASP17 Target Watchlist" in md_text
    assert "Top Open Selected-Lane Targets" in md_text
