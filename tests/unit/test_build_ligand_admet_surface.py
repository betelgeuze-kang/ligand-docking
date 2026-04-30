from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_build_ligand_admet_surface_direct_script_imports_repo_tools(tmp_path: Path) -> None:
    scores_csv = tmp_path / "scores.csv"
    out_json = tmp_path / "admet_surface.json"
    scores_csv.write_text(
        "\n".join(
            [
                "target,ligand_id,smiles,ligand_mw,ligand_logp,ligand_h_donors,ligand_h_acceptors,ligand_rot_bonds,ligand_tpsa,ligand_qed",
                "EGFR_KINASE,aspirin,CC(=O)Oc1ccccc1C(=O)O,180.16,1.2,1,4,3,63.6,0.55",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "build_ligand_admet_surface.py"),
            "--scores-csv",
            str(scores_csv),
            "--out-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["summary"]["status"] == "ligand_admet_surface_ready"
    assert payload["summary"]["compound_count"] == 1
    assert out_json.with_suffix(".csv").exists()
    assert out_json.with_suffix(".md").exists()
