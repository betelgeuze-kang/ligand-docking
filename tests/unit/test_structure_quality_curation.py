from pathlib import Path

from tools import curate_structure_quality as cur


def _write_pdb(path: Path, n_res: int, bfactor: float, add_afdb_header: bool) -> None:
    lines = []
    if add_afdb_header:
        lines.append("REMARK 999 ALPHAFOLD PREDICTION\n")
    serial = 1
    for i in range(1, n_res + 1):
        x = float(i)
        y = float(i + 1)
        z = float(i + 2)
        lines.append(
            f"ATOM  {serial:5d}  CA  ALA A{i:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00{bfactor:6.2f}           C\n"
        )
        serial += 1
    lines.append("END\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_curate_structure_rows_plddt_filter_and_weight(tmp_path):
    afdb_high = tmp_path / "AF-high.pdb"
    afdb_low = tmp_path / "AF-low.pdb"
    exp_file = tmp_path / "exp_native.pdb"
    _write_pdb(afdb_high, n_res=10, bfactor=95.0, add_afdb_header=True)
    _write_pdb(afdb_low, n_res=10, bfactor=40.0, add_afdb_header=True)
    _write_pdb(exp_file, n_res=10, bfactor=20.0, add_afdb_header=False)

    parser = cur.build_parser()
    args = parser.parse_args(
        [
            "--pdb-glob",
            str(tmp_path / "*.pdb"),
            "--min-ca-residues",
            "8",
            "--min-ca-coverage",
            "0.0",
            "--plddt-medium-threshold",
            "70",
            "--plddt-min-threshold",
            "50",
            "--weight-high",
            "1.0",
            "--weight-medium",
            "0.6",
            "--weight-low",
            "0.2",
            "--experimental-weight",
            "0.9",
        ]
    )
    rows, summary = cur.curate_structure_rows(args)
    by_name = {Path(r["source_file"]).name: r for r in rows}

    assert summary["rows"] == 3
    assert by_name["AF-high.pdb"]["include"] == 1
    assert abs(float(by_name["AF-high.pdb"]["sample_weight"]) - 1.0) < 1e-9
    assert by_name["AF-low.pdb"]["include"] == 0
    assert by_name["AF-low.pdb"]["sample_weight"] == 0.0
    assert by_name["exp_native.pdb"]["has_plddt"] == 0
    assert by_name["exp_native.pdb"]["include"] == 1
    assert abs(float(by_name["exp_native.pdb"]["sample_weight"]) - 0.9) < 1e-9


def test_curate_structure_rows_ca_coverage_filter(tmp_path):
    chig = tmp_path / "chignolin.pdb"
    _write_pdb(chig, n_res=5, bfactor=95.0, add_afdb_header=False)

    parser = cur.build_parser()
    args = parser.parse_args(
        [
            "--pdb-file",
            str(chig),
            "--min-ca-residues",
            "4",
            "--min-ca-coverage",
            "0.9",
        ]
    )
    rows, _summary = cur.curate_structure_rows(args)
    assert len(rows) == 1
    row = rows[0]
    assert row["target"] == "Chignolin"
    assert row["include"] == 0
    assert "low_ca_coverage" in str(row["exclude_reason"])


def test_curate_structure_rows_manifest_input_with_target_and_kind_hints(tmp_path):
    generic = tmp_path / "generic_name.pdb"
    _write_pdb(generic, n_res=10, bfactor=95.0, add_afdb_header=False)
    manifest = tmp_path / "sources.csv"
    manifest.write_text(
        "target,path,source_kind\n"
        f"Chignolin,{generic},afdb\n",
        encoding="utf-8",
    )

    parser = cur.build_parser()
    args = parser.parse_args(
        [
            "--manifest-csv",
            str(manifest),
            "--min-ca-residues",
            "8",
            "--min-ca-coverage",
            "0.0",
            "--plddt-medium-threshold",
            "70",
            "--plddt-min-threshold",
            "50",
        ]
    )
    rows, summary = cur.curate_structure_rows(args)
    assert summary["input_mode"] == "manifest"
    assert summary["manifest_rows"] == 1
    assert summary["missing_files_from_manifest"] == 0
    assert len(rows) == 1
    row = rows[0]
    assert row["target"] == "Chignolin"
    assert row["source_kind"] == "afdb"
    assert row["has_plddt"] == 1
    assert row["include"] == 1
