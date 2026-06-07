import io
import json
import tarfile
from pathlib import Path

from tools.casp17 import build_casp17_official_archive_first_baseline_model_pool as mod


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _add_tar_member(archive: tarfile.TarFile, name: str, content: str) -> None:
    data = content.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def _pdb(atom_offset: int) -> str:
    return (
        "PFRMAT TS\n"
        "TARGET T9999\n"
        "MODEL 1\n"
        f"ATOM  {atom_offset:5d}  CA  ALA A   1       0.000   0.000   0.000  1.00 50.00           C\n"
        f"ATOM  {atom_offset + 1:5d}  CB  ALA A   1       1.000   0.000   0.000  1.00 50.00           C\n"
        "END\n"
    )


def test_extracts_first_baseline_model_pool(tmp_path):
    tarball = tmp_path / "T9999.tar.gz"
    with tarfile.open(tarball, "w:gz") as archive:
        for group in ("001", "002"):
            for model_number in range(1, 6):
                _add_tar_member(
                    archive,
                    f"T9999/T9999TS{group}_{model_number}",
                    _pdb(atom_offset=int(group) * 100 + model_number),
                )
        _add_tar_member(archive, "T9999/T9999TS001_6", _pdb(atom_offset=999))
    native = tmp_path / "9XYZ.pdb"
    native.write_text("ATOM      1  CA  GLY A   1       0.0   0.0   0.0\n", encoding="utf-8")
    acquisition_json = tmp_path / "acquisition.json"
    _write_json(
        acquisition_json,
        {
            "summary": {
                "official_archive_first_baseline_acquisition_audit_status": (
                    "official_archive_first_baseline_acquired"
                ),
                "first_baseline_candidate_id": "official_archive_baseline_001",
                "first_competition": "CASP16",
                "first_target_id": "T9999",
                "first_native_pdb_code": "9XYZ",
                "competitive_proof_eligible": False,
                "strict_blind_intake_policy": "do_not_import_as_internal_prediction",
                "tarball_path": str(tarball),
                "native_pdb_path": str(native),
                "tarball_model_count": 11,
                "native_pdb_atom_count": 1,
            }
        },
    )
    args = mod.parse_args(
        [
            "--acquisition-json",
            str(acquisition_json),
            "--out-dir",
            str(tmp_path / "pool"),
            "--out-json",
            str(tmp_path / "pool.json"),
            "--out-csv",
            str(tmp_path / "pool.csv"),
            "--out-md",
            str(tmp_path / "POOL.md"),
        ]
    )
    payload = mod.build_payload(args)
    mod.write_outputs(args, payload)

    summary = payload["summary"]
    assert summary["official_archive_first_baseline_model_pool_status"] == (
        "official_archive_first_baseline_model_pool_ready"
    )
    assert summary["first_target_id"] == "T9999"
    assert summary["model_file_count"] == 11
    assert summary["ready_model_count"] == 11
    assert summary["model1_count"] == 2
    assert summary["group_count"] == 2
    assert summary["complete_top5_group_count"] == 2
    assert summary["top5_model_count"] == 10
    assert summary["extra_model_count"] == 1
    assert summary["competitive_proof_eligible"] is False
    assert payload["rows"][0]["model_id"] == "T9999TS001_1"
    assert payload["rows"][0]["atom_count"] == 2
    assert (tmp_path / "pool" / "model1_manifest.csv").exists()
    assert (tmp_path / "pool" / "top5_manifest.csv").exists()
    assert (tmp_path / "pool" / "extracted_models" / "T9999" / "all_models" / "T9999TS001_1.pdb").exists()
    assert "Claim Boundary" in (tmp_path / "POOL.md").read_text(encoding="utf-8")
