from pathlib import Path

from tools import render_chimerax_movies as rc


def test_render_chimerax_movies_writes_scripts_without_execute(tmp_path):
    pdb = tmp_path / "toy.pdb"
    pdb.write_text(
        "\n".join(
            [
                "REMARK TEST",
                "ATOM      1  CA  GLY A   1      11.104   9.104  10.104  1.00 20.00           C",
                "END",
                "",
            ]
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "movies"
    args = rc.build_parser().parse_args(
        [
            "--pdb",
            str(pdb),
            "--out-dir",
            str(out_dir),
            "--out-json",
            str(tmp_path / "summary.json"),
            "--out-csv",
            str(tmp_path / "summary.csv"),
            "--no-execute",
        ]
    )
    summary = rc.run(args)
    assert summary["ok"] is True
    assert int(summary["render_rows"]) == 1
    cxc = out_dir / "toy.cxc"
    assert cxc.exists()
    script = cxc.read_text(encoding="utf-8")
    assert "color byattribute bfactor palette alphafold" in script
    assert "movie encode" in script
    row = summary["rows"][0]
    assert row["asset_kind"] == "chimerax_turntable"
    assert row["asset_status"] == "turntable_script_ready"
    assert row["recommended_action"] == "render_turntable_mp4"
    assert row["render_command_hint"].endswith(f"--nogui {str(cxc)}")
