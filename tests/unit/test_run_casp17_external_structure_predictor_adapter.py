from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_casp17_external_structure_predictor_adapter_runs_operator_template(tmp_path: Path) -> None:
    predictor = tmp_path / "predictor.py"
    fasta = tmp_path / "T8500.fasta"
    raw_pdb = tmp_path / "job/T8500_model_1.pdb"
    predictor.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import argparse",
                "p=argparse.ArgumentParser()",
                "p.add_argument('--raw-pdb', required=True)",
                "args=p.parse_args()",
                "Path(args.raw_pdb).parent.mkdir(parents=True, exist_ok=True)",
                "Path(args.raw_pdb).write_text('ATOM      1 CA  ALA A   1       1.000   1.000   1.000  1.00 70.00           C  \\nEND\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fasta.write_text(">T8500\nA\n", encoding="utf-8")

    subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_external_structure_predictor_adapter.py"),
            "--target-id",
            "T8500",
            "--fasta",
            str(fasta),
            "--out-dir",
            str(tmp_path / "job"),
            "--raw-pdb",
            str(raw_pdb),
            "--predictor-command-template",
            f"python3 {predictor} --raw-pdb {{raw_pdb}}",
        ],
        cwd=ROOT,
        check=True,
    )

    assert raw_pdb.exists()


def test_casp17_external_structure_predictor_adapter_blocks_missing_template(tmp_path: Path) -> None:
    fasta = tmp_path / "T8501.fasta"
    raw_pdb = tmp_path / "job/T8501_model_1.pdb"
    fasta.write_text(">T8501\nA\n", encoding="utf-8")

    run = subprocess.run(
        [
            "python3",
            str(ROOT / "tools/run_casp17_external_structure_predictor_adapter.py"),
            "--target-id",
            "T8501",
            "--fasta",
            str(fasta),
            "--out-dir",
            str(tmp_path / "job"),
            "--raw-pdb",
            str(raw_pdb),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert run.returncode == 2
    assert "missing predictor command template" in run.stdout
    assert raw_pdb.exists() is False
