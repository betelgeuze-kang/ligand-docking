import json
from pathlib import Path

from tools.casp17 import build_casp17_target_model_folders as mod


def _write_pdb(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "MODEL        1",
                "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 70.00           C  ",
                "ATOM      2  CA  GLY A   2       3.800   0.000   0.000  1.00 68.00           C  ",
                "ATOM      3  CA  SER B   1       0.000   5.000   0.000  1.00 69.00           C  ",
                "TER       4      SER B   1",
                "ENDMDL",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_build_casp17_target_model_folders_copies_target_artifacts(tmp_path):
    watchlist = tmp_path / "watchlist.json"
    watchlist.write_text(
        json.dumps(
            {
                "summary": {"packet_type": "casp17_target_watchlist"},
                "rows": [
                    {
                        "target_id": "T0001",
                        "description": "Example kinase / Fab complex",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                        "human_expiration": "2026-06-01",
                        "qa_expiration": "2026-06-04",
                    },
                    {
                        "target_id": "T0002",
                        "description": "Closed target",
                        "human_open": False,
                        "lane_recommendation": "difficult_protein_complexes",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    seq_dir = tmp_path / "seq"
    pred_dir = tmp_path / "pred"
    raw_job_dir = tmp_path / "jobs"
    render_dir = tmp_path / "renders"
    figure_dir = tmp_path / "figures"
    (seq_dir / "T0001.fasta").parent.mkdir(parents=True)
    (seq_dir / "T0001.fasta").write_text(">T0001\nAG\n", encoding="utf-8")
    _write_pdb(pred_dir / "T0001TS.pdb")
    _write_pdb(raw_job_dir / "T0001" / "T0001_model_1.pdb")
    (raw_job_dir / "T0001" / "backend_runtime.json").write_text('{"ok": true}\n', encoding="utf-8")
    render_dir.mkdir()
    (render_dir / "T0001_structure.png").write_bytes(b"png")
    figure_dir.mkdir()
    (figure_dir / "T0001_publication_figure.png").write_bytes(b"png")

    args = mod.parse_args(
        [
            "--target-watchlist-json",
            str(watchlist),
            "--sequence-dir",
            str(seq_dir),
            "--prediction-dir",
            str(pred_dir),
            "--raw-job-dir",
            str(raw_job_dir),
            "--render-dir",
            str(render_dir),
            "--figure-dir",
            str(figure_dir),
            "--out-dir",
            str(tmp_path / "out"),
            "--out-json",
            str(tmp_path / "packet.json"),
            "--out-csv",
            str(tmp_path / "packet.csv"),
            "--out-md",
            str(tmp_path / "packet.md"),
            "--out-object-csv",
            str(tmp_path / "objects.csv"),
            "--out-object-md",
            str(tmp_path / "objects.md"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["target_count"] == 1
    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["total_object_count"] == 2
    assert payload["summary"]["total_object_projection_files"] == 2
    assert payload["summary"]["total_object_viewer_files"] == 2
    assert payload["summary"]["total_object_protein_atom_count"] == 3
    assert payload["summary"]["total_object_coordinate_valid_count"] == 2
    row = payload["rows"][0]
    assert row["folder_name"] == "T0001_Example_kinase_Fab_complex"
    assert row["folder_status"] == "ready"
    assert row["model_source_kind"] == "final_selected"
    assert row["atom_count"] == 3
    assert row["protein_atom_count"] == 3
    assert row["coordinate_status"] == "valid"
    assert row["chain_count"] == 2
    assert row["residue_count"] == 3
    assert row["object_count"] == 2
    assert row["object_projection_count"] == 2
    assert row["object_viewer_count"] == 2
    assert Path(row["final_model_path"]).exists()
    assert Path(row["fasta_path"]).exists()
    assert Path(row["object_index_md"]).exists()
    assert Path(row["target_manifest_path"]).exists()
    assert Path(row["readme_path"]).exists()
    target_payload = payload["targets"][0]
    object_rows = target_payload["objects"]
    assert len(payload["object_rows"]) == 2
    assert {obj["object_id"] for obj in object_rows} == {"chain_A", "chain_B"}
    assert all(Path(obj["model_path"]).exists() for obj in object_rows)
    assert all(obj["protein_atom_count"] > 0 for obj in object_rows)
    assert all(obj["coordinate_status"] == "valid" for obj in object_rows)
    assert all(Path(obj["projection_svg_path"]).exists() for obj in object_rows)
    assert all(Path(obj["viewer_html_path"]).exists() for obj in object_rows)
    assert all(Path(obj["manifest_path"]).exists() for obj in object_rows)
    viewer_text = Path(object_rows[0]["viewer_html_path"]).read_text(encoding="utf-8")
    assert "<canvas id=\"viewer\"" in viewer_text
    assert "const atoms =" in viewer_text
    assert "http://" not in viewer_text
    assert "https://" not in viewer_text
    mod._write_csv(args.out_object_csv, payload["object_rows"])
    mod._write_object_md(args.out_object_md, payload)
    assert (tmp_path / "objects.csv").exists()
    assert (tmp_path / "objects.md").exists()


def test_build_casp17_target_model_folders_blocks_missing_model(tmp_path):
    watchlist = tmp_path / "watchlist.json"
    watchlist.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "H0001",
                        "description": "Antibody complex",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    seq_dir = tmp_path / "seq"
    seq_dir.mkdir()
    (seq_dir / "H0001.fasta").write_text(">H0001\nAA\n", encoding="utf-8")

    args = mod.parse_args(
        [
            "--target-watchlist-json",
            str(watchlist),
            "--sequence-dir",
            str(seq_dir),
            "--prediction-dir",
            str(tmp_path / "missing_predictions"),
            "--raw-job-dir",
            str(tmp_path / "missing_jobs"),
            "--render-dir",
            str(tmp_path / "missing_renders"),
            "--figure-dir",
            str(tmp_path / "missing_figures"),
            "--out-dir",
            str(tmp_path / "out"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["blocked_count"] == 1
    row = payload["rows"][0]
    assert row["folder_status"] == "blocked"
    assert "final_selected_model_missing" in row["blockers"]


def test_build_casp17_target_model_folders_can_use_raw_model_fallback(tmp_path):
    watchlist = tmp_path / "watchlist.json"
    watchlist.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "target_id": "H0003",
                        "description": "New antibody complex",
                        "human_open": True,
                        "lane_recommendation": "difficult_protein_complexes",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    seq_dir = tmp_path / "seq"
    raw_job_dir = tmp_path / "jobs"
    seq_dir.mkdir()
    (seq_dir / "H0003.fasta").write_text(">H0003\nAA\n", encoding="utf-8")
    _write_pdb(raw_job_dir / "H0003" / "H0003_model_1.pdb")

    args = mod.parse_args(
        [
            "--target-watchlist-json",
            str(watchlist),
            "--sequence-dir",
            str(seq_dir),
            "--prediction-dir",
            str(tmp_path / "missing_predictions"),
            "--raw-job-dir",
            str(raw_job_dir),
            "--render-dir",
            str(tmp_path / "missing_renders"),
            "--figure-dir",
            str(tmp_path / "missing_figures"),
            "--out-dir",
            str(tmp_path / "out"),
            "--allow-raw-model-fallback",
            "--generate-fallback-preview-assets",
        ]
    )

    payload = mod.build_payload(args)

    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["raw_fallback_target_count"] == 1
    assert payload["summary"]["generated_fallback_render_files"] == 1
    assert payload["summary"]["generated_fallback_figure_files"] == 1
    row = payload["rows"][0]
    assert row["folder_status"] == "ready"
    assert row["model_source_kind"] == "raw_internal_fallback"
    assert row["render_file_count"] == 1
    assert row["figure_file_count"] == 1
    assert row["object_count"] == 2
    assert not row["blockers"]
    assert Path(row["final_model_path"]).exists()
