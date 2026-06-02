import json
from pathlib import Path

from tools import build_casp17_massivefold_freeze_candidate_protein_library as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _touch(path: Path, text: str = "artifact\n") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_massivefold_freeze_candidate_protein_library_builds_name_folders(
    tmp_path: Path,
) -> None:
    h_dir = tmp_path / "h2319"
    r_dir = tmp_path / "r2341"
    escrow_json = tmp_path / "freeze_escrow.json"
    queue_json = tmp_path / "queue.json"
    folders_json = tmp_path / "folders.json"
    official_csv = tmp_path / "official.csv"
    out_dir = tmp_path / "library"

    _write_json(
        escrow_json,
        {
            "summary": {
                "massivefold_freeze_candidate_escrow_status": (
                    "massivefold_freeze_candidate_escrow_ready_external_only"
                )
            },
            "rows": [
                {
                    "escrow_status": "freeze_candidate_escrow_ready_external_only",
                    "target_group": "protein_complex",
                    "target_id": "H2319",
                    "decision_class": "freeze_candidate_after_probe",
                    "model_path": _touch(h_dir / "model.cif", "ATOM H2319\n"),
                    "model_sha256": "sha-h2319",
                    "viewer_html": _touch(h_dir / "viewer.html"),
                    "projection_svg": _touch(h_dir / "projection.svg"),
                    "top5_manifest_csv": _touch(h_dir / "top5.csv"),
                    "top5_manifest_sha256": "top5-h2319",
                    "escrow_md": _touch(h_dir / "FREEZE_ESCROW.md"),
                    "native_status": "official_native_release_pending",
                },
                {
                    "escrow_status": "freeze_candidate_escrow_ready_external_only",
                    "target_group": "rna_hybrid",
                    "target_id": "R2341",
                    "decision_class": "freeze_candidate_existing",
                    "model_path": _touch(r_dir / "model.cif", "ATOM R2341\n"),
                    "model_sha256": "sha-r2341",
                    "viewer_html": _touch(r_dir / "viewer.html"),
                    "projection_svg": _touch(r_dir / "projection.svg"),
                    "top5_manifest_csv": _touch(r_dir / "top5.csv"),
                    "top5_manifest_sha256": "top5-r2341",
                    "escrow_md": _touch(r_dir / "FREEZE_ESCROW.md"),
                    "native_status": "official_native_release_pending",
                },
            ],
        },
    )
    _write_json(
        queue_json,
        {
            "rows": [
                {
                    "target_id": "H2319",
                    "protein_name": "Human astrovirus VA1 capsid spike antibody 7C8 complex",
                    "official_human_expiration": "2026-06-03",
                    "official_qa_expiration": "2026-06-06",
                }
            ]
        },
    )
    _write_json(folders_json, {"rows": []})
    official_csv.write_text(
        "\n".join(
            [
                "Target;Type;Res;Oligo.State;Entry Date; Server Exp.;Human Exp.;QA Exp.;Cancellation Date;Description",
                "H2319;complex;300;heteromer;2026-05-01;2026-05-04;2026-06-03;2026-06-06;;Official H2319 name",
                "R2341;RNA;100;monomer;2026-05-01;2026-05-04;2026-06-04;2026-06-07;;RRE core",
                "",
            ]
        ),
        encoding="utf-8",
    )

    args = mod.parse_args(
        [
            "--freeze-candidate-escrow-json",
            str(escrow_json),
            "--current-upload-queue-json",
            str(queue_json),
            "--target-model-folders-json",
            str(folders_json),
            "--official-targetlist-csv",
            str(official_csv),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "library.json"),
            "--out-csv",
            str(tmp_path / "library.csv"),
            "--out-md",
            str(tmp_path / "LIBRARY.md"),
            "--out-html",
            str(tmp_path / "library.html"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    rows = {row["target_id"]: row for row in payload["rows"]}
    assert summary["massivefold_freeze_candidate_protein_library_status"] == (
        "massivefold_freeze_candidate_protein_library_ready_external_only"
    )
    assert summary["protein_ready_count"] == 2
    assert summary["protein_blocked_count"] == 0
    assert summary["object_ready_count"] == 2
    assert summary["model_link_count"] == 2
    assert summary["viewer_link_count"] == 2
    assert summary["projection_link_count"] == 2
    assert summary["top5_link_count"] == 2
    assert summary["escrow_link_count"] == 2
    assert summary["model_sha256_count"] == 2
    assert summary["top5_sha256_count"] == 2
    assert summary["current_name_count"] == 1
    assert summary["official_name_count"] == 2
    assert summary["rna_hybrid_count"] == 1
    assert summary["protein_complex_count"] == 1
    assert summary["competitive_proof_eligible_count"] == 0
    assert summary["author_serialized_count"] == 0
    assert rows["H2319"]["protein_name_source"] == "current_upload_queue"
    assert rows["R2341"]["protein_name"] == "RRE core"
    assert rows["R2341"]["protein_name_source"] == "official_targetlist"
    assert rows["H2319"]["competitive_proof_eligible"] == "false"

    h_folder = Path(rows["H2319"]["library_protein_folder"])
    h_object = Path(rows["H2319"]["library_object_folder"])
    assert (h_folder / "README.md").is_file()
    assert (h_folder / "protein_manifest.json").is_file()
    assert (h_object / "README.md").is_file()
    assert (h_object / "object_manifest.json").is_file()
    assert not (h_object / "model.cif").exists()
    assert (tmp_path / "library.json").is_file()
    assert (tmp_path / "library.csv").is_file()
    assert (tmp_path / "LIBRARY.md").is_file()
    assert (tmp_path / "library.html").is_file()
    assert "AUTHOR " not in (tmp_path / "library.json").read_text(encoding="utf-8")


def test_massivefold_freeze_candidate_protein_library_blocks_missing_links(
    tmp_path: Path,
) -> None:
    escrow_json = tmp_path / "freeze_escrow.json"
    official_csv = tmp_path / "official.csv"
    _write_json(
        escrow_json,
        {
            "rows": [
                {
                    "escrow_status": "freeze_candidate_escrow_blocked",
                    "target_group": "rna_hybrid",
                    "target_id": "R2350",
                    "model_path": str(tmp_path / "missing.cif"),
                    "top5_manifest_csv": str(tmp_path / "missing.csv"),
                }
            ]
        },
    )
    official_csv.write_text(
        "Target;Type;Res;Oligo.State;Entry Date; Server Exp.;Human Exp.;QA Exp.;Cancellation Date;Description\n",
        encoding="utf-8",
    )
    args = mod.parse_args(
        [
            "--freeze-candidate-escrow-json",
            str(escrow_json),
            "--current-upload-queue-json",
            str(tmp_path / "queue.json"),
            "--target-model-folders-json",
            str(tmp_path / "folders.json"),
            "--official-targetlist-csv",
            str(official_csv),
            "--out-dir",
            str(tmp_path / "library"),
        ]
    )
    payload = mod.build_payload(args)

    assert payload["summary"]["massivefold_freeze_candidate_protein_library_status"] == (
        "massivefold_freeze_candidate_protein_library_partial_external_only"
    )
    assert payload["summary"]["protein_blocked_count"] == 1
    assert "freeze_candidate_escrow_not_ready" in payload["rows"][0]["blockers"]
    assert "model_file_missing" in payload["rows"][0]["blockers"]
    assert "top5_manifest_missing" in payload["rows"][0]["blockers"]
    assert "official_description_missing" in payload["rows"][0]["blockers"]
